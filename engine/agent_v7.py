"""Agent v7 — 全流程RAG增强

CPT生成前必须经过RAG检索：
  Step1: RAG检索相似报表模式 + SOP节点
  Step2: RAG检索表关系 + 数据源知识
  Step3: 结合检索结果生成SQL（含JOIN关系）
  Step4: 生成CPT骨架（含最佳实践）
  Step5: 自检 + RAG检索常见错误
  Step6: 部署
"""

import sys, os, json, re
sys.path.insert(0, r'os.path.dirname(os.path.abspath(__file__))')
sys.path.insert(0, r'C:\workspace\01_knowledge')

from rag_engine import RAGEngine
from sql_skills import (sql_discover, sql_describe, sql_primary_keys,
                         sql_relations, sql_select, sql_aggregate, sql_where,
                         sql_validate, sql_create_table)
from cpt_builder_v5 import build_cpt, save_and_deploy
from checker import check as self_check

API_KEY = 'sk-79778f1a65f1484f81e863beb2ade2ee'
FR_DIR = r'/path/to/fr/reportlets'
OUT_DIR = r'os.path.dirname(os.path.abspath(__file__))\output'
os.makedirs(OUT_DIR, exist_ok=True)

rag = RAGEngine()


def llm(prompt, temp=0.1, max_t=800):
    from openai import OpenAI
    c = OpenAI(api_key=API_KEY, base_url='https://api.deepseek.com')
    r = c.chat.completions.create(model='deepseek-chat',
        messages=[{'role':'user','content':prompt}], temperature=temp, max_tokens=max_t, timeout=25)
    return r.choices[0].message.content


def generate_cpt(requirement):
    """全流程RAG增强的CPT生成"""
    print("=" * 60)
    print("Requirement:", requirement[:80])
    
    # ====== Step 1: RAG检索相似报表模式 + 需求分析 ======
    print("\n[Step1] RAG Search: similar reports...")
    similar = rag.search(requirement, top_k=5)
    sop_knowledge = "\n".join(
        "[%s] %s" % (d['cat'], d['content'][:300])
        for d in similar if d['cat'] in ('SOP', 'documentation')
    )
    print("  Found %d similar patterns" % len(similar))
    for d in similar[:3]:
        print("    - [%s] %s" % (d['cat'], d['title'][:50]))
    
    # Step 1b: LLM分析需求（带RAG上下文）
    prompt = f"""分析以下报表需求。参考类似案例。输出JSON:
{{"title":"标题","columns":[{{"name":"列名","field":"字段","type":"VARCHAR/NUMBER/DATE"}}],
"group_by":"分组字段","aggregates":{{}},"description":"业务描述","report_type":"行式/分组/交叉/图表/填报/参数"}}

类似案例:\n{sop_knowledge[:1500]}
需求: {requirement}"""
    
    raw = llm(prompt, 0)
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    params = json.loads(m.group()) if m else {"title": requirement[:20], "columns": []}
    print("  Title: %s (%d cols)" % (params['title'], len(params.get('columns', []))))
    
    if not params.get('columns'):
        return {'error': 'Cannot parse columns'}
    
    # ====== Step 2: RAG检索表关系 + 数据源 ======
    print("\n[Step2] RAG Search: table relations...")
    ds_knowledge = rag.search("数据库表 字段 " + " ".join(
        c['name'] for c in params.get('columns', [])), top_k=3)
    table_info = "\n".join(d['content'][:300] for d in ds_knowledge if d['cat'] == 'datasource')
    
    # 发现真实表
    tables = sql_discover()['tables']
    print("  Real DB tables:", tables)
    
    # ====== Step 3: 生成SQL（含表关系） ======
    print("\n[Step3] Generate SQL with relations...")
    cols = params['columns']
    col_names = [c['name'] for c in cols]
    
    sql_prompt = f"""基于真实数据库表生成SQL。数据库有这些表: {tables}。
需求字段: {col_names}
类似案例SQL模式: {table_info[:1000]}

输出JSON: {{"sql":"完整SQL","tables_used":["表1"],"joins":[],"notes":"说明"}}"""
    
    raw = llm(sql_prompt, 0)
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    sql_info = json.loads(m.group()) if m else {}
    sql = sql_info.get('sql', sql_select(tables[0] if tables else 'procurement', 
                                          [c['field'] for c in cols])['sql'])
    params['sql'] = sql
    params['tables_used'] = sql_info.get('tables_used', [tables[0]] if tables else [])
    print("  SQL:", sql[:120])
    print("  Tables:", params['tables_used'])
    
    # SQL验证
    val = sql_validate(sql)
    print("  Valid:", val.get('valid', False))
    
    # ====== Step 4: 生成CPT骨架 ======
    print("\n[Step4] Build CPT skeleton...")
    cpt_xml = build_cpt(params)
    print("  Size: %dB" % len(cpt_xml))
    
    # ====== Step 5: 自检 + RAG检索常见错误 ======
    print("\n[Step5] Self-check + RAG errors...")
    check_result = self_check(cpt_xml)
    issues = sum(len(v) for v in check_result.values()) if isinstance(check_result, dict) else 0
    
    if issues > 0:
        # RAG检索常见错误修复方案
        error_patterns = rag.search("常见错误 " + params.get('report_type', '报表'), top_k=2)
        print("  Issues: %d (RAG fixing hints found)" % issues)
    else:
        print("  No issues")
    
    # ====== Step 6: 部署 ======
    print("\n[Step6] Deploy...")
    path = save_and_deploy(cpt_xml, params['title'])
    print("  Saved:", path)
    
    return {
        'status': 'ok',
        'title': params['title'],
        'columns': len(cols),
        'sql': sql,
        'tables': params['tables_used'],
        'cpt_path': path,
        'rag_sources': [d['title'] for d in similar[:3]],
        'issues': issues,
    }


# ===== Test =====
if __name__ == '__main__':
    result = generate_cpt("做一个按部门统计合同金额的财务报表，包含部门名称和合同金额两列")
    print("\n" + "=" * 60)
    print("DONE: %s (%d cols, %d issues)" % (
        result.get('title', '?'),
        result.get('columns', 0),
        result.get('issues', 0)
    ))
    print("RAG Sources:", result.get('rag_sources', []))
    print("CPT Path:", result.get('cpt_path', '?'))
