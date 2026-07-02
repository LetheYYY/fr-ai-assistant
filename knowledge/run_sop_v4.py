"""Batch SOP generator v4 - accumulate in memory, save once at end"""
import json, time, re
from openai import OpenAI

SUMMARIES = r'C:\workspace\01_knowledge\parsed\cluster_summaries.json'
API_KEY = 'sk-79778f1a65f1484f81e863beb2ade2ee'

SYS = '你是FineReport专家。输出单行纯JSON不包含其他内容:{"sop_name":"名称","report_type":"类型","one_line_desc":"描述","trigger":"触发条件","steps":[{"s":"步骤","c":"检查"}],"mistakes":["错误"]}。类型从:行式报表/分组报表/交叉报表/图表报表/填报报表/参数报表/复合报表中选。写3-8步。'

client = OpenAI(api_key=API_KEY, base_url='https://api.deepseek.com')

with open(SUMMARIES, encoding='utf-8') as f:
    items = json.load(f)

total = len(items)

for i, item in enumerate(items):
    cid = item['cluster_id']
    print(f'[{i+1}/{total}] {cid} ...', end=' ', flush=True)
    
    try:
        r = client.chat.completions.create(
            model='deepseek-chat',
            messages=[{'role':'system','content':SYS},{'role':'user','content':item['summary_text'][:1000]}],
            temperature=0.1, max_tokens=500, timeout=30
        )
        raw = r.choices[0].message.content.strip()
        
        # Try to parse JSON
        sop = None
        # Direct parse
        try:
            sop = json.loads(raw)
        except:
            # Find JSON in response
            m = re.search(r'\{[^{}]*"sop_name"[^{}]*\}', raw)
            if m:
                try:
                    sop = json.loads(m.group())
                except:
                    pass
        
        if sop:
            item['sop'] = sop
            print('OK')
        else:
            item['sop'] = {'raw': raw[:500]}
            print('FAIL')
    except Exception as e:
        item['sop'] = {'error': str(e)[:200]}
        print(f'ERR: {e}')
    
    time.sleep(0.15)

# Save once at the end
with open(SUMMARIES, 'w', encoding='utf-8') as f:
    json.dump(items, f, ensure_ascii=False, indent=2)

ok = sum(1 for it in items if it.get('sop') and isinstance(it['sop'], dict) and 'sop_name' in it['sop'])
print(f'\nDone: {ok}/{total} SOPs OK, saved to {SUMMARIES}')
