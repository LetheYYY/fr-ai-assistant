"""CPT Builder v4 - 基于真实数据源，生成即用型 CPT（含嵌入SQL）"""
import json, re, os

OUT_DIR = r'os.path.dirname(os.path.abspath(__file__))\output'
CATALOG_PATH = r'C:\workspace\01_knowledge\parsed\datasource_catalog.json'
os.makedirs(OUT_DIR, exist_ok=True)

# 加载数据源目录
with open(CATALOG_PATH, encoding='utf-8') as f:
    CATALOG = json.load(f)

# 提取最常用的真实列名集合（ds1为主）
KNOWN_COLUMNS = set()
KNOWN_TABLES = set()
for ds in ['ds1', 'ds2', 'ds3', 'ds4']:
    if ds in CATALOG:
        KNOWN_COLUMNS.update(CATALOG[ds].get('columns', []))
        KNOWN_TABLES.update(CATALOG[ds].get('tables', []))

KNOWN_COLUMNS = sorted(KNOWN_COLUMNS)
KNOWN_TABLES = sorted(KNOWN_TABLES)

# 常用中文列名 → 英文字段名映射（从catalog中学习到的）
FIELD_HINTS = {
    '订单编号': '订单ID', '客户名称': '客户ID', '部门名称': '部门',
    '合同金额': '运货费', '销售额': '销量', '销售日期': '订购日期',
    '产品名称': '产品', '销售数量': '数量', '单价': '单价',
    '签订日期': '订购日期', '项目类型': '类别ID', '业务部门': '部门',
    '日期': '订购日期', '金额': '运货费', '数量': '数量',
}

def match_columns(requirement):
    """用 LLM 将用户需求中的列名匹配到真实数据库列"""
    from openai import OpenAI
    c = OpenAI(api_key='sk-79778f1a65f1484f81e863beb2ade2ee', base_url='https://api.deepseek.com')
    
    prompt = f"""将需求中的列名映射到可用数据库字段。输出纯JSON数组。

可用表: {KNOWN_TABLES[:30]}
可用字段: {KNOWN_COLUMNS[:100]}
已知映射: {json.dumps(FIELD_HINTS, ensure_ascii=False)}

需求: {requirement}

输出格式: [{{"name":"中文列名","field":"英文字段名","table":"来源表","type":"字段类型"}}]
如果找不到精确匹配，用最接近的英文字段名。"""

    try:
        r = c.chat.completions.create(
            model='deepseek-chat',
            messages=[{'role':'user','content':prompt}],
            temperature=0, max_tokens=500, timeout=15
        )
        raw = r.choices[0].message.content
        m = re.search(r'\[.*\]', raw, re.DOTALL)
        if m:
            return json.loads(m.group())
    except:
        pass
    
    # Fallback: simple column generation
    words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', requirement)
    return [{"name": w, "field": w.lower().replace(' ','_')[:20], "table": "report_data", "type": "VARCHAR"} for w in words if len(w) > 1]


def build_v10_cpt(title, columns, table_name, sql, db_name="FRDemo"):
    """生成 v10 格式 CPT（含 TableDataMap + SQL）"""
    n = len(columns)
    
    # TableDataMap
    tdm = f'''<TableDataMap>
<TableData name="ds1" class="com.fr.data.impl.DBTableData">
<Parameters/>
<Attributes maxMemRowCount="-1"/>
<Connection class="com.fr.data.impl.NameDatabaseConnection">
<DatabaseName><![CDATA[{db_name}]]></DatabaseName>
</Connection>
<Query><![CDATA[{sql}]]></Query>
<PageQuery><![CDATA[]]></PageQuery>
</TableData>
</TableDataMap>'''
    
    # Cells
    cells = []
    # Title
    cells.append(f'<C c="0" r="0" cs="{n}" s="0"><O><![CDATA[{title}]]></O><PrivilegeControl/><Expand/></C>')
    # Headers
    for i, col in enumerate(columns):
        cells.append(f'<C c="{i}" r="1" s="1"><O><![CDATA[{col["name"]}]]></O><PrivilegeControl/><Expand dir="0"><cellSortAttr/></Expand></C>')
    # Data rows
    for i, col in enumerate(columns):
        cells.append(f'<C c="{i}" r="2" s="0"><O t="DSColumn"><Attributes dsName="ds1" columnName="{col["field"]}"/><Complex/><RG class="com.fr.report.cell.cellattr.core.group.FunctionGrouper"/><Parameters/><cellSortAttr/></O><PrivilegeControl/><Expand dir="0"/></C>')
    
    cells_xml = '\n'.join(cells)
    
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<WorkBook xmlVersion="20170720" releaseVersion="10.0.0">
{tdm}
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
<ReportParameterAttr><Attributes showWindow="true" delayPlaying="true" windowPosition="1" align="0" useParamsTemplate="true" currentIndex="0"/><PWTitle><![CDATA[参数]]></PWTitle></ReportParameterAttr>
<StyleList><Style style_name="默认" full="true" border_source="-1" imageLayout="1"><FRFont name="simhei" style="0" size="72"/><Background name="NullBackground"/><Border/></Style><Style style_name="Head" full="true" border_source="2" horizontal_alignment="0" imageLayout="1"><FRFont name="SimSun" style="0" size="72"/><Background name="NullBackground"/><Border><Top style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Top><Bottom style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Bottom><Left style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Left></Border></Style></StyleList>
<DesensitizationList/>
<DesignerVersion DesignerVersion="LAA"/>
<PreviewType PreviewType="2"/>
<TemplateThemeAttrMark class="com.fr.base.iofile.attr.TemplateThemeAttrMark"><TemplateThemeAttrMark name="兼容主题" dark="false"/></TemplateThemeAttrMark>
</WorkBook>'''


def generate(requirement, output_name=None):
    """主入口"""
    print(f'\n{"="*60}')
    print(f'Requirement: {requirement[:80]}...')
    
    # Step 1: Match columns to real DB
    columns = match_columns(requirement)
    tables = set(c.get('table','') for c in columns if c.get('table'))
    table = tables.pop() if tables else 'report_data'
    fields = [c['field'] for c in columns]
    
    print(f'  Columns: {len(columns)} -> matched {len(tables)} table(s)')
    for col in columns:
        print(f'    {col["name"]} -> {col["field"]} ({col.get("table","?")})')
    
    # Step 2: Generate SQL from real columns
    from openai import OpenAI
    c = OpenAI(api_key='sk-79778f1a65f1484f81e863beb2ade2ee', base_url='https://api.deepseek.com')
    sql_prompt = f"""为FineReport生成SQL查询。数据库:FRDemo。表:{list(tables)}。字段:{fields}。
用户需求:{requirement}。只输出SQL语句，不要解释。"""
    try:
        r = c.chat.completions.create(model='deepseek-chat', messages=[{'role':'user','content':sql_prompt}], temperature=0, max_tokens=200, timeout=15)
        sql = r.choices[0].message.content.strip()
        if sql.startswith('```'): 
            sql = re.sub(r'```\w*','', sql).strip()
    except:
        sql = f"SELECT {', '.join(fields)} FROM [{table}]"
    
    print(f'  SQL: {sql[:120]}...')
    
    # Step 3: Extract title
    title_match = re.search(r'一个[^，,。]*[报表|统计|图表|汇总|明细|表单]', requirement)
    title = title_match.group() if title_match else requirement[:15]
    title = title.lstrip('一个').rstrip('做')
    
    # Step 4: Build CPT
    cpt_xml = build_v10_cpt(title, columns, table, sql)
    
    # Step 5: Save
    if output_name is None:
        output_name = re.sub(r'[^\w]','_', title[:30]) + '.cpt'
    if not output_name.endswith('.cpt'):
        output_name += '.cpt'
    
    cpt_path = os.path.join(OUT_DIR, output_name)
    with open(cpt_path, 'w', encoding='utf-8') as f:
        f.write(cpt_xml)
    
    # Also save companion JSON with setup info
    setup = {
        "datasource": "ds1",
        "database": "FRDemo",
        "sql": sql,
        "table": table,
        "columns": columns,
        "note": "此CPT为v10格式，SQL已内嵌。在FineReport 11中可直接打开预览。如FRDemo数据库中无此表，请修改TableDataMap中的SQL语句。"
    }
    json_path = os.path.join(OUT_DIR, output_name.replace('.cpt', '_setup.json'))
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(setup, f, ensure_ascii=False, indent=2)
    
    print(f'  CPT: {cpt_path} ({len(cpt_xml)} bytes)')
    print(f'  Setup: {json_path}')
    
    return {'cpt': cpt_path, 'sql': sql, 'db': 'FRDemo', 'table': table, 'columns': columns}


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        generate(' '.join(sys.argv[1:]))
    else:
        for req in [
            "做一个销售订单明细报表，包含订单编号、客户名称、产品名称、销售数量、订单日期五列",
            "按产品类别分组统计销售额，包含产品类别和销售总额两列",
        ]:
            generate(req)
