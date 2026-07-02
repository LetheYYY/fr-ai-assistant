"""RAG Pipeline — BM25关键词检索 + LLM重排序（零模型下载）

策略: 
  1. BM25关键词匹配（确定性，零成本）→ Top-10候选
  2. LLM重排序（选Top-3最相关）→ 低成本
  3. 增强Prompt → LLM回答
"""

import os, json, re
from collections import defaultdict

RAG_DOCS = r'C:\workspace\01_knowledge\rag_docs'
SOP_PATH = r'C:\workspace\01_knowledge\parsed\cluster_summaries.json'
DS_PATH  = r'C:\workspace\01_knowledge\parsed\datasource_catalog.json'


class RAGEngine:
    def __init__(self):
        self.documents = []       # [{'title','content','category'}]
        self.keywords_index = defaultdict(set)  # keyword → doc_ids
        self._load_all()

    def _load_all(self):
        """加载全部知识"""
        # 46篇文档
        for root, _, files in os.walk(RAG_DOCS):
            for f in files:
                if f.endswith('.md') and f != '_index.json':
                    path = os.path.join(root, f)
                    with open(path, 'r', encoding='utf-8') as fp:
                        content = fp.read()
                    title = f.replace('.md', '')
                    cat = os.path.basename(root)
                    doc_id = len(self.documents)
                    self.documents.append({'title': title, 'cat': cat, 'content': content, 'id': doc_id})
                    self._index_doc(doc_id, content)

        # 71个SOP
        with open(SOP_PATH, 'r', encoding='utf-8') as f:
            sops = json.load(f)
        for sop in sops:
            sop_data = sop.get('sop', {})
            text = json.dumps(sop_data, ensure_ascii=False)
            title = sop_data.get('sop_name', sop.get('cluster_id', ''))
            doc_id = len(self.documents)
            self.documents.append({'title': title, 'cat': 'SOP', 'content': text, 'id': doc_id})
            self._index_doc(doc_id, text)

        # 286数据源
        with open(DS_PATH, 'r', encoding='utf-8') as f:
            ds = json.load(f)
        for name, info in ds.items():
            text = f"数据源: {name} 表: {info.get('tables', [])} 字段: {info.get('columns', [])}"
            doc_id = len(self.documents)
            self.documents.append({'title': name, 'cat': 'datasource', 'content': text, 'id': doc_id})
            self._index_doc(doc_id, text)

        print(f'RAG引擎加载: {len(self.documents)} 条知识 ({len(self.documents)-len(ds)-len(sops)}文档 + {len(sops)}SOP + {len(ds)}数据源)')

    def _index_doc(self, doc_id, text):
        """提取关键词建立索引"""
        # Extract meaningful Chinese words (2-4 chars)
        words = set(re.findall(r'[\u4e00-\u9fff]{2,4}', text))
        # Also English words
        words.update(re.findall(r'[A-Z][a-z]+|[a-z]{3,}', text))
        for w in words:
            self.keywords_index[w.lower()].add(doc_id)

    def search(self, query, top_k=10):
        """BM25风格关键词检索"""
        qwords = set(re.findall(r'[\u4e00-\u9fff]{2,4}', query))
        qwords.update(re.findall(r'[A-Z][a-z]+|[a-z]{3,}', query))

        scores = defaultdict(float)
        for w in qwords:
            w = w.lower()
            docs = self.keywords_index.get(w, set())
            for did in docs:
                scores[did] += 1

        ranked = sorted(scores.items(), key=lambda x: -x[1])[:top_k]
        return [self.documents[did] for did, _ in ranked]

    def ask(self, question, use_llm=True):
        """用RAG增强回答"""
        # Step 1: 检索
        hits = self.search(question, top_k=8)

        # Step 2: LLM重排序
        if use_llm and hits:
            hits = self._llm_rerank(question, hits)

        # Step 3: 构建增强Prompt
        context = "\n\n---\n\n".join(
            f"【{h['cat']}】{h['title']}\n{h['content'][:500]}"
            for h in hits[:3]
        )

        if use_llm:
            return self._llm_answer(question, context)

        return {'hits': len(hits), 'top': hits[:3], 'query': question}

    def _llm_rerank(self, query, candidates):
        """LLM选最相关的Top-3"""
        from openai import OpenAI
        c = OpenAI(api_key='sk-79778f1a65f1484f81e863beb2ade2ee', base_url='https://api.deepseek.com')
        
        items = "\n".join(
            f"[{i}] [{h['cat']}] {h['title']}: {h['content'][:100]}"
            for i, h in enumerate(candidates[:8])
        )
        prompt = f"从以下候选知识中选出与问题最相关的3个（只输出编号如0,2,5）:\n问题:{query}\n候选:\n{items}"

        try:
            r = c.chat.completions.create(
                model='deepseek-chat',
                messages=[{'role':'user','content':prompt}],
                temperature=0, max_tokens=50, timeout=15
            )
            indices = re.findall(r'\d+', r.choices[0].message.content)
            reranked = []
            for i in indices:
                idx = int(i)
                if 0 <= idx < len(candidates):
                    reranked.append(candidates[idx])
                    if len(reranked) >= 3:
                        break
            return reranked if reranked else candidates[:3]
        except:
            return candidates[:3]

    def _llm_answer(self, question, context):
        """LLM基于知识库回答"""
        from openai import OpenAI
        c = OpenAI(api_key='sk-79778f1a65f1484f81e863beb2ade2ee', base_url='https://api.deepseek.com')

        prompt = f"""你是FineReport报表专家。基于以下知识库回答问题。如知识库不足则基于你自身的FineReport专业知识补充。

知识库:
{context}

问题: {question}

请给出专业、具体的回答（含XML示例或配置步骤）。"""

        r = c.chat.completions.create(
            model='deepseek-chat',
            messages=[{'role':'user','content':prompt}],
            temperature=0.3, max_tokens=800, timeout=25
        )
        return {
            'answer': r.choices[0].message.content,
            'context': context,
        }


# ===== 快速使用 =====
_engine = None

def ask(question):
    global _engine
    if _engine is None:
        _engine = RAGEngine()
    return _engine.ask(question)


if __name__ == '__main__':
    engine = RAGEngine()

    tests = [
        "如何配置数据连接",
        "条件属性怎么设置高亮",
        "分组报表的FunctionGrouper怎么用",
        "饼图如何配置",
        "填报控件有哪些类型",
    ]

    for q in tests:
        print(f'\n{"="*60}')
        print(f'Q: {q}')
        result = engine.ask(q)
        if isinstance(result, dict) and 'answer' in result:
            print(f'A: {result["answer"][:400]}...')
        else:
            print(f'Hits: {result["hits"]}')
            for h in result.get('top', [])[:3]:
                print(f'  - [{h["cat"]}] {h["title"]}')

    print(f'\n{"="*60}')
    print('RAG引擎就绪。调用: from rag_engine import ask; ask("你的问题")')
