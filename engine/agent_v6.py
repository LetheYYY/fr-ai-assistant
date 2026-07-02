"""Agent v6 — Skill Architecture + Agent Loop

10个Skills:
  1.skill_analyze_requirement  需求理解
  2.skill_generate_sql         SQL生成  
  3.skill_validate_sql         SQL验证
  4.skill_build_skeleton       CPT骨架
  5.skill_self_check           L1-L3自检
  6.skill_apply_style          样式美化
  7.skill_deploy_cpt           部署
  8.skill_check_connectivity   连通性
  9.skill_rag_search           RAG检索
  10.skill_parse_file          文件解析

Agent Loop: Thought → Action → Observation → 循环
"""

import sys, os, json, re, time
sys.path.insert(0, r'os.path.dirname(os.path.abspath(__file__))')

from cpt_builder_v5 import build_cpt, save_and_deploy
from sql_engine import SQLEngine
from checker import check as self_check

API_KEY = 'sk-79778f1a65f1484f81e863beb2ade2ee'
FR_DIR = r'/path/to/fr/reportlets'
OUT_DIR = r'os.path.dirname(os.path.abspath(__file__))\output'
os.makedirs(OUT_DIR, exist_ok=True)


def llm(prompt, temp=0.1, max_t=800):
    from openai import OpenAI
    c = OpenAI(api_key=API_KEY, base_url='https://api.deepseek.com')
    r = c.chat.completions.create(model='deepseek-chat', messages=[{'role':'user','content':prompt}], temperature=temp, max_tokens=max_t, timeout=25)
    return r.choices[0].message.content


# ========== 10 SKILLS ==========

def skill_analyze_requirement(user_input):
    """Skill 1: 分析需求 → 提取结构化参数"""
    prompt = f"""从需求中提取FineReport报表参数。输出JSON:
{{"title":"报表标题","columns":[{{"name":"列名","field":"字段","type":"VARCHAR/NUMBER/DATE"}}],"group_by":"分组字段","aggregates":{{"字段":"SUM/COUNT"}},"needs_chart":false,"chart_type":null,"needs_condition":false,"needs_param":false,"needs_summary":false}}

需求: {user_input}"""
    raw = llm(prompt, 0)
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    return json.loads(m.group()) if m else {"title": user_input[:20], "columns": []}


def skill_generate_sql(columns, requirement=''):
    """Skill 2: 规则引擎生成SQL"""
    e = SQLEngine()
    result = e.generate_sql(columns, ['procurement'])
    return result['sql']


def skill_validate_sql(sql_text):
    """Skill 3: 在真实MySQL验证SQL"""
    import paramiko
    try:
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect('10.10.10.140', username='ubuntu', password='ubuntu', timeout=5)
        safe_sql = sql_text.replace('"', '\\"')
        cmd = f'echo ubuntu | sudo -S mysql -e "USE ceshi; EXPLAIN {safe_sql}" 2>&1'
        i, o, e = c.exec_command(cmd)
        out = o.read().decode(errors='replace')
        c.close()
        return {'valid': 'id' in out.lower() or 'select_type' in out.lower(), 'output': out[:200]}
    except Exception as ex:
        return {'valid': False, 'error': str(ex)[:200]}


def skill_build_skeleton(params):
    """Skill 4: 生成CPT骨架"""
    return build_cpt(params)  # pass params dict directly




def skill_self_check(cpt_xml):
    """Skill 5: 三级自检"""
    return self_check(cpt_xml)


def skill_apply_style(cpt_xml, style='default'):
    """Skill 6: 应用样式（预留）"""
    return cpt_xml


def skill_deploy_cpt(cpt_xml, title):
    """Skill 7: 部署到FineReport"""
    return save_and_deploy(cpt_xml, title)


def skill_check_connectivity():
    """Skill 8: 数据库连通性"""
    return SQLEngine().check_connectivity()


def skill_rag_search(query, top_k=5):
    """Skill 9: RAG检索"""
    import sys; sys.path.insert(0, r'C:\workspace\01_knowledge')
    from rag_engine import RAGEngine
    return RAGEngine().search(query, top_k)


def skill_parse_file(filepath):
    """Skill 10: 解析Excel/图片"""
    from analyze_upload import parse_excel, parse_image
    ext = os.path.splitext(filepath)[1].lower()
    if ext in ('.xlsx', '.xls'):
        return parse_excel(filepath)
    elif ext in ('.png', '.jpg', '.jpeg'):
        return parse_image(filepath)
    return None


# ========== AGENT LOOP ==========

class FineReportAgent:
    def __init__(self):
        self.context = {}    # 当前会话状态
        self.history = []    # Thought-Action-Observation 记录

    def run(self, user_input):
        """主入口：根据输入类型路由到对应工作流"""
        # Route: File
        if os.path.isfile(user_input):
            return self._workflow_file(user_input)
        # Route: Question
        if any(kw in user_input for kw in ['如何', '怎么', '什么是', '为什么']):
            return self._workflow_qa(user_input)
        # Route: Generate
        return self._workflow_generate(user_input)

    def _workflow_generate(self, requirement):
        """6步CPT生成流程"""
        log = []
        self.context['req'] = requirement

        # === Step 1: 分析需求 ===
        log.append({'step': 1, 'thought': '分析用户需求，提取报表参数', 'action': 'skill_analyze_requirement'})
        params = skill_analyze_requirement(requirement)
        log[-1]['observation'] = f"标题={params['title']}, 列数={len(params.get('columns',[]))}"
        print(f"[Step1] {params['title']} ({len(params.get('columns',[]))}列)")

        if not params.get('columns'):
            return {'error': '无法解析需求中的列信息', 'log': log}

        # === Step 2: 生成SQL ===
        log.append({'step': 2, 'thought': '基于真实数据库生成SQL', 'action': 'skill_generate_sql'})
        sql = skill_generate_sql(params['columns'], requirement)
        params['sql'] = sql
        log[-1]['observation'] = f"SQL: {sql[:100]}..."
        print(f"[Step2] SQL: {sql[:80]}...")

        # === Step 3: 验证SQL ===
        log.append({'step': 3, 'thought': '验证SQL在真实数据库能否执行', 'action': 'skill_validate_sql'})
        val = skill_validate_sql(sql)
        log[-1]['observation'] = 'SQL有效' if val['valid'] else f"SQL问题: {val.get('error','')}"
        print(f"[Step3] SQL valid: {val['valid']}")
        if not val['valid']:
            # 尝试修正
            params['sql'] = sql.replace('FROM [procurement]', 'FROM procurement')
            val2 = skill_validate_sql(params['sql'])
            log[-1]['observation'] += f" | 修正后: {'OK' if val2['valid'] else '仍失败'}"

        # === Step 4: 构建骨架 ===
        log.append({'step': 4, 'thought': '生成CPT XML骨架', 'action': 'skill_build_skeleton'})
        cpt_xml = skill_build_skeleton(params)
        log[-1]['observation'] = f"CPT大小: {len(cpt_xml)}B"
        print(f"[Step4] CPT: {len(cpt_xml)}B")

        # === Step 5: 自检 ===
        log.append({'step': 5, 'thought': '三级自检(L1-L3)', 'action': 'skill_self_check'})
        check_result = skill_self_check(cpt_xml)
        issues_count = sum(len(v) for v in check_result.values()) if isinstance(check_result, dict) else 0
        log[-1]['observation'] = f"{'无问题' if issues_count==0 else f'{issues_count}个问题'}"
        print(f"[Step5] Check: {issues_count} issues")

        # === Step 6: 部署 ===
        log.append({'step': 6, 'thought': '保存并部署到FineReport', 'action': 'skill_deploy_cpt'})
        path = skill_deploy_cpt(cpt_xml, params['title'])
        log[-1]['observation'] = f"部署到: {path}"
        print(f"[Step6] Deployed: {path}")

        return {
            'status': 'ok',
            'title': params['title'],
            'columns': len(params.get('columns', [])),
            'sql': sql,
            'cpt_path': path,
            'issues': issues_count,
            'log': log,
        }

    def _workflow_file(self, filepath):
        """文件上传工作流"""
        log = [{'step': 1, 'thought': '解析上传文件', 'action': 'skill_parse_file'}]
        data = skill_parse_file(filepath)
        ext = os.path.splitext(filepath)[1].lower()
        log[-1]['observation'] = f"解析成功" if data else "解析失败"

        # 转为生成流程
        if data and 'headers' in data:
            return self._workflow_generate(f"报表包含这些列: {', '.join(data['headers'])}")
        return {'error': '无法解析文件', 'log': log}

    def _workflow_qa(self, question):
        """知识问答工作流"""
        log = [{'step': 1, 'thought': 'RAG检索相关知识', 'action': 'skill_rag_search'}]
        results = skill_rag_search(question, 5)
        log[-1]['observation'] = f"检索到 {len(results)} 条相关知识"

        context = "\n".join(f"[{r['cat']}] {r['title']}" for r in results[:3])
        prompt = f"""你是FineReport专家。基于知识回答。
相关知识: {context}
问题: {question}"""

        log.append({'step': 2, 'thought': 'LLM基于知识库回答', 'action': 'llm_answer'})
        answer = llm(prompt, 0.3, 800)
        log[-1]['observation'] = f"回答长度: {len(answer)}"

        return {'status': 'ok', 'answer': answer, 'sources': [r['title'] for r in results[:3]], 'log': log}


# ========== CLI ==========

if __name__ == '__main__':
    agent = FineReportAgent()
    print("=" * 50)
    print(" 帆软数字员工 Agent v6 (Skill架构)")
    print(" 10 Skills + Agent Loop")
    print("=" * 50)

    if len(sys.argv) > 1:
        result = agent.run(' '.join(sys.argv[1:]))
        for step in result.get('log', []):
            print(f"\n[Step{step['step']}] {step['thought']}")
            print(f"  Action: {step['action']}")
            print(f"  Result: {step['observation']}")
        if result.get('answer'):
            print('\n' + result['answer'])
        elif result.get('cpt_path'):
            print(f"\nCPT: {result['cpt_path']}")
    else:
        while True:
            try:
                u = input("\n> ").strip()
                if u in ('quit', 'exit', 'q'): break
                if not u: continue
                r = agent.run(u)
                if r.get('answer'):
                    print('\n' + r['answer'][:500])
                elif r.get('cpt_path'):
                    print(f"\n✅ {r['title']} ({r['columns']}列)")
                    print(f"   SQL: {r.get('sql','')[:80]}...")
                    print(f"   CPT: {r['cpt_path']}")
                    print(f"   问题: {r.get('issues',0)}")
                elif r.get('error'):
                    print(f"❌ {r['error']}")
            except KeyboardInterrupt: break
            except Exception as e: print(f"Error: {e}")
