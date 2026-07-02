"""RAG Pipeline — 知识向量化 + Milvus入库 + 检索

流程:
  1. 加载所有知识文档 (46篇MD + 71个SOP + 286数据源)
  2. BGE-large-zh 向量化
  3. Milvus创建Collection并写入
  4. 检索测试
"""

import os, json, time, sys
from sentence_transformers import SentenceTransformer
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType

# ============ 配置 ============
MILVUS_HOST = '10.10.10.140'
MILVUS_PORT = '19530'
COLLECTION_NAME = 'finereport_knowledge'
EMBEDDING_DIM = 1024  # BGE-large-zh: 1024维

DOC_PATHS = [
    (r'C:\workspace\01_knowledge\rag_docs', 'documentation', '.md'),
    (r'C:\workspace\01_knowledge\parsed', 'sop', 'cluster_summaries.json'),
    (r'C:\workspace\01_knowledge\parsed', 'datasource', 'datasource_catalog.json'),
]

# ============ 加载Embedding模型 ============
print('Loading BGE model...')
model = SentenceTransformer('BAAI/bge-large-zh-v1.5', device='cpu')
print(f'Model loaded, dim={model.get_sentence_embedding_dimension()}')

# ============ 文档加载器 ============

def load_markdown_docs(base_dir):
    """加载markdown知识文档"""
    docs = []
    for root, dirs, files in os.walk(base_dir):
        for f in files:
            if f.endswith('.md') and f != '_index.json':
                path = os.path.join(root, f)
                cat = os.path.basename(root)
                with open(path, 'r', encoding='utf-8') as fp:
                    content = fp.read()
                # 提取标题
                title = f.replace('.md', '').replace('_', '/')
                docs.append({
                    'id': f'doc_{len(docs)}',
                    'title': title,
                    'category': cat,
                    'content': content[:3000],  # 截断长文档
                    'type': 'documentation',
                    'source': f
                })
    return docs


def load_sop_docs(json_path):
    """加载SOP节点"""
    docs = []
    with open(json_path, 'r', encoding='utf-8') as f:
        items = json.load(f)
    for item in items:
        sop = item.get('sop', {})
        if sop and isinstance(sop, dict):
            text = f"{sop.get('sop_name','')} - {sop.get('one_line_desc','')}"
            text += f" 类型:{sop.get('report_type','')} 触发:{sop.get('trigger','')}"
            steps = sop.get('steps', [])
            for st in steps[:5]:
                text += f" 步骤:{st.get('s','')}"
            docs.append({
                'id': f'sop_{len(docs)}',
                'title': sop.get('sop_name', item.get('cluster_id', '')),
                'category': 'SOP',
                'content': text[:2000],
                'type': 'sop',
                'source': item.get('cluster_id', '')
            })
    return docs


def load_datasource_docs(json_path):
    """加载数据源知识"""
    docs = []
    with open(json_path, 'r', encoding='utf-8') as f:
        catalog = json.load(f)
    for ds_name, info in catalog.items():
        if ds_name.startswith(('Embedded', 'File')):
            continue
        text = f"数据源:{ds_name} 连接:{info.get('connections',[])}"
        text += f" 表:{info.get('tables',[])[:10]}"
        text += f" 字段:{info.get('columns',[])[:20]}"
        docs.append({
            'id': f'ds_{len(docs)}',
            'title': ds_name,
            'category': 'datasource',
            'content': text[:1500],
            'type': 'datasource',
            'source': ds_name
        })
    return docs


# ============ 向量化 ============

def embed_docs(docs, batch_size=32):
    """批量向量化"""
    texts = [d['content'] for d in docs]
    # BGE需要query前缀提升检索质量
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=True, batch_size=batch_size)
    return embeddings


# ============ Milvus操作 ============

def setup_milvus():
    """连接Milvus并创建Collection"""
    connections.connect(host=MILVUS_HOST, port=MILVUS_PORT)
    print(f'Connected to Milvus @ {MILVUS_HOST}:{MILVUS_PORT}')

    # 删除旧Collection
    if Collection(COLLECTION_NAME).name:
        Collection(COLLECTION_NAME).drop()
        print(f'Dropped old collection: {COLLECTION_NAME}')

    # 定义Schema
    fields = [
        FieldSchema(name='id', dtype=DataType.VARCHAR, max_length=64, is_primary=True),
        FieldSchema(name='title', dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name='category', dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name='content', dtype=DataType.VARCHAR, max_length=4000),
        FieldSchema(name='type', dtype=DataType.VARCHAR, max_length=32),
        FieldSchema(name='embedding', dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM),
    ]
    schema = CollectionSchema(fields, description='FineReport RAG Knowledge Base')

    collection = Collection(COLLECTION_NAME, schema)
    print(f'Created collection: {COLLECTION_NAME}')

    # 创建索引 (HNSW, 高性能ANN)
    index_params = {
        'metric_type': 'COSINE',
        'index_type': 'HNSW',
        'params': {'M': 16, 'efConstruction': 200}
    }
    collection.create_index('embedding', index_params)
    print('Index created (HNSW/COSINE)')

    return collection


def insert_to_milvus(collection, docs, embeddings):
    """批量写入Milvus"""
    batch_size = 100
    total = len(docs)

    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch_docs = docs[start:end]
        batch_emb = embeddings[start:end]

        entities = [
            [d['id'] for d in batch_docs],
            [d['title'] for d in batch_docs],
            [d['category'] for d in batch_docs],
            [d['content'] for d in batch_docs],
            [d['type'] for d in batch_docs],
            batch_emb.tolist(),
        ]
        collection.insert(entities)
        print(f'  Inserted {end}/{total}')

    collection.flush()
    print(f'Flushed. Total entities: {collection.num_entities}')


def search_test(collection, query='分组报表怎么做', top_k=5):
    """检索测试"""
    print(f'\n=== 检索测试: "{query}" ===')
    collection.load()

    query_emb = model.encode([query], normalize_embeddings=True)
    search_params = {'metric_type': 'COSINE', 'params': {'ef': 100}}

    results = collection.search(
        data=query_emb.tolist(),
        anns_field='embedding',
        param=search_params,
        limit=top_k,
        output_fields=['title', 'category', 'type']
    )

    for i, hits in enumerate(results):
        for j, hit in enumerate(hits):
            doc = hit.entity
            print(f'  {j+1}. [{doc.type}] {doc.title} ({doc.category}) score={hit.score:.3f}')

    return results


# ============ 主流程 ============

def main():
    t0 = time.time()

    # 1. 加载文档
    print('\n=== 1. 加载文档 ===')
    all_docs = []
    all_docs.extend(load_markdown_docs(DOC_PATHS[0][0]))
    all_docs.extend(load_sop_docs(DOC_PATHS[1][0] + '/' + DOC_PATHS[1][2]))
    all_docs.extend(load_datasource_docs(DOC_PATHS[2][0] + '/' + DOC_PATHS[2][2]))
    print(f'Total docs: {len(all_docs)}')
    print(f'  Markdown: {sum(1 for d in all_docs if d["type"]=="documentation")}')
    print(f'  SOP: {sum(1 for d in all_docs if d["type"]=="sop")}')
    print(f'  Datasource: {sum(1 for d in all_docs if d["type"]=="datasource")}')

    # 2. 向量化
    print('\n=== 2. 向量化 ===')
    embeddings = embed_docs(all_docs)
    print(f'Embeddings shape: {embeddings.shape}')

    # 3. Milvus入库
    print('\n=== 3. Milvus入库 ===')
    collection = setup_milvus()
    insert_to_milvus(collection, all_docs, embeddings)

    # 4. 检索测试
    print('\n=== 4. 检索测试 ===')
    search_test(collection, '如何做分组报表')
    search_test(collection, '图表怎么配置')
    search_test(collection, '条件属性高亮')

    elapsed = time.time() - t0
    print(f'\n=== 完成！耗时 {elapsed:.1f}s ===')
    print(f'知识库: {len(all_docs)} 条记录, {EMBEDDING_DIM}维向量')
    print(f'Milvus: {MILVUS_HOST}:{MILVUS_PORT}, Collection: {COLLECTION_NAME}')


if __name__ == '__main__':
    main()
