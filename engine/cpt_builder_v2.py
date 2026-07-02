"""CPT Builder v2 — 含数据库配置生成"""
import json, re, os
from jinja2 import Template
from lxml import etree

OUT_DIR = r'os.path.dirname(os.path.abspath(__file__))\output'
os.makedirs(OUT_DIR, exist_ok=True)

def _llm(prompt):
    from openai import OpenAI
    c = OpenAI(api_key='sk-79778f1a65f1484f81e863beb2ade2ee', base_url='https://api.deepseek.com')
    r = c.chat.completions.create(model='deepseek-chat', messages=[{'role':'user','content':prompt}], temperature=0, max_tokens=500, timeout=15)
    raw = r.choices[0].message.content
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    return json.loads(m.group()) if m else {}

def generate(requirement, output_name=None):
    """主入口"""
    print(f'\n{"="*60}')
    print(f'Requirement: {requirement[:80]}...')
    
    # 1. Extract params + SQL in one LLM call
    prompt = f"""从需求中提取FineReport参数和SQL，输出JSON:
{{"title":"标题","columns":[{{"name":"中文列名","field":"英文"}}],"type":"行式/分组/图表/填报/参数","has_param":true/false,"has_chart":true/false,"has_summary":true/false,
"database":"数据库名","table":"表名","sql":"SELECT语句","note":"备注"}}

需求: {requirement}"""
    try:
        params = _llm(prompt)
        if not params:
            raise Exception("LLM failed")
    except:
        params = {"title": requirement[:20], "columns": [{"name":"列1","field":"col1"}], "type":"行式", "database":"fine_report_db", "table":"report_table", "sql":"SELECT * FROM report_table"}
    
    print(f'  Type: {params.get("type","?")}')
    print(f'  Title: {params.get("title","?")}')
    print(f'  Columns: {len(params.get("columns",[]))}')
    print(f'  Database: {params.get("database","?")}')
    print(f'  Table: {params.get("table","?")}')
    print(f'  SQL: {params.get("sql","?")[:100]}...')
    
    # 2. Build CPT XML
    cols = params.get('columns', [])
    n = len(cols) if cols else 3
    cells = []
    
    # Title
    cells.append(f'<C c="0" r="0" cs="{n}" s="0"><O><![CDATA[{params["title"]}]]></O><PrivilegeControl/><Expand/></C>')
    
    # Headers
    for i, col in enumerate(cols):
        cells.append(f'<C c="{i}" r="1" s="2"><O><![CDATA[{col["name"]}]]></O><PrivilegeControl/><Expand dir="0"><cellSortAttr/></Expand></C>')
    
    # Data rows
    for i, col in enumerate(cols):
        field = col.get('field', f'field_{i}')
        cells.append(f'<C c="{i}" r="2" s="0"><O t="DSColumn"><Attributes dsName="ds1" columnName="{field}"/><Complex/><RG class="com.fr.report.cell.cellattr.core.group.FunctionGrouper"/><Parameters/><cellSortAttr/></O><PrivilegeControl/><Expand dir="0"/></C>')
    
    # Summary
    if params.get('has_summary'):
        sum_field = cols[0].get('field', 'field_0')
        cells.append(f'<C c="0" r="3" s="0"><O t="DSColumn"><Attributes dsName="ds1" columnName="{sum_field}"/><Complex/><RG class="com.fr.report.cell.cellattr.core.group.SummaryGrouper"><FN><![CDATA[com.fr.data.util.function.SumFunction]]></FN></RG><Parameters/></O><PrivilegeControl/><Expand dir="0"/></C>')
    
    cells_xml = '\n'.join(cells)
    
    param_panel = '<ReportParameterAttr><Attributes showWindow="true" delayPlaying="true" windowPosition="1" align="0" useParamsTemplate="true" currentIndex="0"/><PWTitle><![CDATA[参数]]></PWTitle></ReportParameterAttr>' if params.get('has_param') else ''
    
    cpt_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<WorkBook xmlVersion="20211223" releaseVersion="11.5.0">
<Report class="com.fr.report.worksheet.WorkSheet" name="sheet1">
<ReportPageAttr><HR/><FR/><HC/><FC/><USE REPEAT="false" PAGE="false" WRITE="false"/></ReportPageAttr>
<ColumnPrivilegeControl/><RowPrivilegeControl/>
<RowHeight defaultValue="723900"><![CDATA[1143000,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900,723900]]></RowHeight>
<ColumnWidth defaultValue="2743200"><![CDATA[8033657,6966857,2743200,2743200,2743200,2743200,2743200,2743200,2743200,2743200,2743200]]></ColumnWidth>
<CellElementList>
{cells_xml}
</CellElementList>
<ReportAttrSet><ReportSettings headerHeight="0" footerHeight="0"><PaperSetting/><FollowingTheme background="true"/></ReportSettings><Header reportPageType="0"><Background name="NullBackground"/><LeftList/><CenterList/><RightList/></Header><Footer reportPageType="0"><Background name="NullBackground"/><LeftList/><CenterList/><RightList/></Footer></ReportAttrSet><PrivilegeControl/>
</Report>
{param_panel}
<StyleList><Style style_name="默认" full="true" border_source="-1" imageLayout="1"><FRFont name="simhei" style="0" size="72"/><Background name="NullBackground"/><Border/></Style><Style style_name="Head" full="true" border_source="2" horizontal_alignment="0" imageLayout="1"><FRFont name="SimSun" style="0" size="72"/><Background name="NullBackground"/><Border><Top style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Top><Bottom style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Bottom><Left style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Left></Border></Style></StyleList>
<DesensitizationList/><DesignerVersion DesignerVersion="LAA"/><PreviewType PreviewType="2"/>
<TemplateThemeAttrMark class="com.fr.base.iofile.attr.TemplateThemeAttrMark"><TemplateThemeAttrMark name="兼容主题" dark="false"/></TemplateThemeAttrMark>
</WorkBook>'''
    
    # 3. Validate and save
    try:
        root = etree.fromstring(cpt_xml.encode('utf-8'))
        cpt_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + etree.tostring(root, encoding='unicode')
    except:
        pass
    
    if output_name is None:
        output_name = re.sub(r'[^\w]','_', params.get('title','report')[:30])
    if not output_name.endswith('.cpt'):
        output_name += '.cpt'
    
    cpt_path = os.path.join(OUT_DIR, output_name)
    with open(cpt_path, 'w', encoding='utf-8') as f:
        f.write(cpt_xml)
    
    # 4. Save dataset config JSON
    ds = {
        "datasource_name": "ds1",
        "database": params.get("database", "fine_report_db"),
        "table": params.get("table", "report_table"),
        "sql": params.get("sql", f"SELECT * FROM {params.get('table','report_table')}"),
        "columns": params.get("columns", []),
        "note": params.get("note", ""),
        "fine_report_setup": {
            "step1": "在FineReport决策平台 → 管理系统 → 数据连接 中创建数据源",
            "step2": "在报表设计器 → 模板数据集 中添加ds1，粘贴上述SQL",
            "step3": "确认SQL中的表名和字段名与实际数据库一致"
        }
    }
    ds_path = os.path.join(OUT_DIR, output_name.replace('.cpt', '_dataset.json'))
    with open(ds_path, 'w', encoding='utf-8') as f:
        json.dump(ds, f, ensure_ascii=False, indent=2)
    
    print(f'  CPT: {cpt_path}')
    print(f'  Dataset: {ds_path}')
    
    return {
        'cpt_path': cpt_path,
        'dataset_path': ds_path,
        'database': params.get('database', ''),
        'sql': params.get('sql', ''),
        'table': params.get('table', ''),
        'columns': params.get('columns', [])
    }


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        generate(' '.join(sys.argv[1:]))
    else:
        for req in [
            "做一个销售明细表，包含产品名称、销售数量、单价、销售日期四列",
            "按地区分组统计销售额，包含地区、销售额两列，要有汇总行",
            "做一个合同管理报表按部门分组，包含合同编号、项目类型、合同金额、签订日期，需要参数筛选",
        ]:
            generate(req)
