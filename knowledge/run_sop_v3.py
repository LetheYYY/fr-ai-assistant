"""Batch SOP generator v3 - simplified JSON output"""
import json, time, re
from openai import OpenAI

SUMMARIES = r'C:\workspace\01_knowledge\parsed\cluster_summaries.json'
API_KEY = 'sk-79778f1a65f1484f81e863beb2ade2ee'

SYS = '你是FineReport专家。输出单行JSON:{"sop_name":"名称","report_type":"类型","one_line_desc":"描述","trigger":"触发条件","steps":[{"s":"步骤","c":"检查"}],"mistakes":["错误"]}。类型从行式报表/分组报表/交叉报表/图表报表/填报报表/参数报表/复合报表中选。3-8步。只输出JSON。'

client = OpenAI(api_key=API_KEY, base_url='https://api.deepseek.com')

with open(SUMMARIES, encoding='utf-8') as f:
    items = json.load(f)

total = len(items)
ok_count = 0

for i, item in enumerate(items):
    cid = item['cluster_id']
    if item.get('sop') and isinstance(item['sop'], dict) and 'sop_name' in item['sop']:
        print(f'[{i+1}/{total}] {cid} (cached)')
        ok_count += 1
        continue
    
    print(f'[{i+1}/{total}] {cid}...', end=' ', flush=True)
    
    try:
        r = client.chat.completions.create(
            model='deepseek-chat',
            messages=[{'role':'system','content':SYS},{'role':'user','content':item['summary_text'][:800]}],
            temperature=0.1, max_tokens=350, timeout=25
        )
        raw = r.choices[0].message.content.strip()
        sop = None
        try:
            sop = json.loads(raw)
        except:
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if m:
                try:
                    c = m.group()
                    c = re.sub(r',\s*}', '}', c)
                    c = re.sub(r',\s*]', ']', c)
                    sop = json.loads(c)
                except:
                    pass
        
        if sop:
            item['sop'] = sop
            ok_count += 1
            print('OK')
        else:
            item['sop'] = {'raw': raw[:400]}
            print('FAIL')
    except Exception as e:
        item['sop'] = {'error': str(e)[:200]}
        print('ERR')
    
    time.sleep(0.15)
    with open(SUMMARIES, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

print(f'\nDone: {ok_count}/{total}')
