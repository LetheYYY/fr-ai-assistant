"""CPT Builder — 核心引擎：需求 → CPT XML"""
import json, re, os
from jinja2 import Template
from lxml import etree

SOP_PATH = r'C:\workspace\01_knowledge\parsed\cluster_summaries.json'
OUT_DIR = r'os.path.dirname(os.path.abspath(__file__))\output'
os.makedirs(OUT_DIR, exist_ok=True)

# ============== Jinja2 Templates ==============

BASE = Template('''<?xml version="1.0" encoding="UTF-8"?>
<WorkBook xmlVersion="20211223" releaseVersion="11.5.0">
<Report class="com.fr.report.worksheet.WorkSheet" name="sheet1">
<ReportPageAttr><HR/><FR/><HC/><FC/><USE REPEAT="false" PAGE="false" WRITE="false"/></ReportPageAttr>
<ColumnPrivilegeControl/><RowPrivilegeControl/>
<RowHeight defaultValue="723900"><![CDATA[{{ row_heights }}]]></RowHeight>
<ColumnWidth defaultValue="2743200"><![CDATA[{{ col_widths }}]]></ColumnWidth>
<CellElementList>
{{ cells_xml }}
</CellElementList>
<ReportAttrSet>
<ReportSettings headerHeight="0" footerHeight="0"><PaperSetting/><FollowingTheme background="true"/></ReportSettings>
<Header reportPageType="0"><Background name="NullBackground"/><LeftList/><CenterList/><RightList/></Header>
<Footer reportPageType="0"><Background name="NullBackground"/><LeftList/><CenterList/><RightList/></Footer>
</ReportAttrSet>
<PrivilegeControl/>
</Report>
{{ param_panel }}
<StyleList>
<Style style_name="默认" full="true" border_source="-1" imageLayout="1">
<FRFont name="simhei" style="0" size="72"/><Background name="NullBackground"/><Border/>
</Style>
{{ head_styles }}
</StyleList>
<DesensitizationList/>
<DesignerVersion DesignerVersion="LAA"/>
<PreviewType PreviewType="2"/>
<TemplateThemeAttrMark class="com.fr.base.iofile.attr.TemplateThemeAttrMark">
<TemplateThemeAttrMark name="兼容主题" dark="false"/>
</TemplateThemeAttrMark>
</WorkBook>''')

STYLE_L = Template('''<Style style_name="Head" full="true" border_source="2" horizontal_alignment="0" imageLayout="1">
<FRFont name="SimSun" style="0" size="72"/><Background name="NullBackground"/><Border>
<Top style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Top>
<Bottom style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Bottom>
<Left style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Left>
</Border></Style>''')

STYLE_M = Template('''<Style style_name="Head" full="true" border_source="10" horizontal_alignment="0" imageLayout="1">
<FRFont name="SimSun" style="0" size="72"/><Background name="NullBackground"/><Border>
<Top style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Top>
<Bottom style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Bottom>
</Border></Style>''')

STYLE_R = Template('''<Style style_name="Head" full="true" border_source="8" horizontal_alignment="0" imageLayout="1">
<FRFont name="SimSun" style="0" size="72"/><Background name="NullBackground"/><Border>
<Top style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Top>
<Bottom style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Bottom>
<Right style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Right>
</Border></Style>''')

TITLE_CELL = Template('''<C c="0" r="0" cs="{{ cols }}" s="0"><O><![CDATA[{{ title }}]]></O><PrivilegeControl/><Expand/></C>''')

HEADER_CELL = Template('''<C c="{{ c }}" r="1" s="2"><O><![CDATA[{{ name }}]]></O><PrivilegeControl/><Expand>{{ sort_attr }}</Expand></C>''')

DATA_CELL = Template('''<C c="{{ c }}" r="2" s="0"><O t="DSColumn"><Attributes dsName="{{ ds }}" columnName="{{ field }}"/><Complex/><RG class="com.fr.report.cell.cellattr.core.group.{{ grouper }}"/><Parameters/>{{ sort_attr }}</O><PrivilegeControl/><Expand dir="0"/></C>''')

CHART_CELL = Template('''<C c="0" r="0" cs="{{ cols }}" rs="15" s="0"><O t="CC"><LayoutAttr selectedIndex="0"/><ChangeAttr enable="false" changeType="button" timeInterval="5"/><Chart name="默认" chartClass="{{ chart_class }}"><Chart class="{{ chart_class }}"><GI><AttrBackground><Background name="NullBackground"/></AttrBackground><AttrBorder><Attr lineStyle="0"/></AttrBorder></GI><ChartAttr isJSDraw="true" isStyleGlobal="false"/><Title4VanChart><Title><GI><AttrBackground><Background name="NullBackground"/></AttrBackground></GI><O><![CDATA[{{ title }}]]></O><TextAttr><Attr alignText="0"><FRFont name="Microsoft YaHei UI" style="0" size="16"/></Attr></TextAttr></Title></Title4VanChart><Plot4VanChart/></Chart></Chart></O><PrivilegeControl/><Expand/></C>''')

PARAM_PANEL = Template('''<ReportParameterAttr><Attributes showWindow="true" delayPlaying="true" windowPosition="1" align="0" useParamsTemplate="true" currentIndex="0"/><PWTitle><![CDATA[参数]]></PWTitle></ReportParameterAttr>''')

SUMMARY_CELL = Template('''<C c="{{ c }}" r="3" s="0"><O t="DSColumn"><Attributes dsName="{{ ds }}" columnName="{{ field }}"/><Complex/><RG class="com.fr.report.cell.cellattr.core.group.SummaryGrouper"><FN><![CDATA[com.fr.data.util.function.SumFunction]]></FN></RG><Parameters/></O><PrivilegeControl/><Expand dir="0"/></C>''')


# ============== Decision Tree Router ==============

TYPE_KEYWORDS = {
    '图表报表': ['图表', '柱状图', '饼图', '折线图', '甘特图', '仪表盘', '散点图', '雷达图', '漏斗图'],
    '填报报表': ['填报', '提交', '录入', '填写', '表单', '调查表'],
    '参数报表': ['参数', '筛选', '过滤', '查询', '下拉框', '下拉复选框'],
    '交叉报表': ['交叉', '矩阵', '行列转换', '双向'],
    '分组报表': ['分组', '按.*汇总', '按.*统计', '按.*合计', '小计', '组内'],
    '行式报表': ['明细', '列表', '清单'],
}

def classify_requirement(text):
    """从自然语言需求中推断报表类型和参数"""
    result = {'report_type': '行式报表', 'has_param': False, 'has_chart': False, 
              'has_summary': False, 'has_condition': False, 'chart_type': None}
    scores = {}
    for rtype, keywords in TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if re.search(kw, text))
        if score > 0:
            scores[rtype] = score
    if scores:
        result['report_type'] = max(scores, key=scores.get)
    if any(kw in text for kw in ['参数', '筛选', '过滤', '查询', '下拉', '选择']):
        result['has_param'] = True
    if any(kw in text for kw in ['图', 'Chart', 'chart', '饼', '柱', '线', '仪表', '散点', '雷达']):
        result['has_chart'] = True
    if any(kw in text for kw in ['汇总', '合计', '总计', '求和', '平均', '小计', '统计']):
        result['has_summary'] = True
    if any(kw in text for kw in ['标红', '高亮', '预警', '条件', '背景色', '颜色']):
        result['has_condition'] = True
    # Detect chart type
    chart_map = {'柱状图':'BarChart','饼图':'PieChart','折线图':'LineChart',
                 '甘特图':'GanttChart','漏斗图':'FunnelChart','散点图':'ScatterChart',
                 '雷达图':'RadarChart','仪表盘':'GaugeChart'}
    for cn, cc in chart_map.items():
        if cn in text:
            result['chart_type'] = f'com.fr.plugin.chart.vanchart.VanChart'
            break
    return result


def extract_params_with_llm(text):
    """用 LLM 从需求中提取结构化参数"""
    from openai import OpenAI
    client = OpenAI(api_key='sk-79778f1a65f1484f81e863beb2ade2ee', base_url='https://api.deepseek.com')
    prompt = f"""从需求中提取报表参数，输出JSON:
{{"title":"报表标题","columns":[{{"name":"中文列名","field":"英文字段名"}}],"datasource":"数据源名称","group_by":"分组字段","summary_field":"汇总字段","chart_title":"图表标题"}}

需求: {text}"""
    try:
        r = client.chat.completions.create(model='deepseek-chat', messages=[{'role':'user','content':prompt}], temperature=0, max_tokens=400, timeout=15)
        raw = r.choices[0].message.content
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            return json.loads(m.group())
    except:
        pass
    return {"title": text[:20], "columns": [{"name":"示例列","field":"example"}], "datasource": "ds1"}


# ============== CPT Builder ==============

def build_cpt(params):
    """根据结构化参数生成完整 CPT XML"""
    cols = len(params.get('columns', []))
    if cols == 0:
        cols = 3
    
    # Row heights: title row taller
    heights = ['1143000'] + ['723900'] * 50
    # Column widths: first col wider
    widths = ['8033657'] + ['6966857'] + ['2743200'] * max(0, cols - 2)
    
    # Build cells
    cells = []
    # Title
    cells.append(TITLE_CELL.render(title=params.get('title','报表'), cols=cols))
    
    # Headers
    for i, col in enumerate(params.get('columns', [])):
        cells.append(HEADER_CELL.render(c=i, name=col['name'], sort_attr='<cellSortAttr/>' if i < 3 else ''))
    
    # Data rows
    for i, col in enumerate(params.get('columns', [])):
        grouper = 'FunctionGrouper'
        if col.get('group_by'):
            grouper = 'FunctionGrouper'
        cells.append(DATA_CELL.render(c=i, field=col['field'], ds=params.get('datasource','ds1'), grouper=grouper, sort_attr='<cellSortAttr/>' if i < 3 else ''))
    
    # Summary row
    if params.get('has_summary'):
        sum_field = params.get('summary_field', params['columns'][0]['field'])
        cells.append(SUMMARY_CELL.render(c=0, field=sum_field, ds=params.get('datasource','ds1')))
    
    # Chart
    if params.get('has_chart'):
        chart_class = params.get('chart_class', 'com.fr.plugin.chart.vanchart.VanChart')
        chart_title = params.get('chart_title', params.get('title','图表'))
        cells = [CHART_CELL.render(cols=cols, title=chart_title, chart_class=chart_class)] + cells[1:]
    
    cells_xml = '\n'.join(cells)
    
    # Parameter panel
    param_p = PARAM_PANEL.render() if params.get('has_param') else ''
    
    # Styles
    if cols >= 3:
        head_styles = STYLE_L.render() + '\n' + STYLE_M.render() + '\n' + STYLE_R.render()
    else:
        head_styles = STYLE_L.render()
    
    cpt = BASE.render(row_heights=','.join(heights), col_widths=','.join(widths), cells_xml=cells_xml, param_panel=param_p, head_styles=head_styles)
    
    # Validate
    try:
        etree.fromstring(cpt.encode('utf-8'))
    except Exception as e:
        print(f'  XML validation warning: {e}')
    
    return cpt


def validate_and_fix(cpt_xml):
    """校验 CPT XML 并自动修复常见问题"""
    try:
        root = etree.fromstring(cpt_xml.encode('utf-8'))
    except Exception as e:
        print(f'  XML parse error: {e}')
        return cpt_xml
    
    # Rule 1: Every C must have PrivilegeControl
    for cell in root.iter('C'):
        if cell.find('PrivilegeControl') is None:
            pc = etree.SubElement(cell, 'PrivilegeControl')
    
    # Rule 2: DSColumn cells must have RG and Expand
    for cell in root.findall('.//C'):
        o = cell.find('O')
        if o is not None and o.get('t') == 'DSColumn':
            if o.find('RG') is None:
                rg = etree.SubElement(o, 'RG')
                rg.set('class', 'com.fr.report.cell.cellattr.core.group.FunctionGrouper')
            if cell.find('Expand') is None:
                expand = etree.SubElement(cell, 'Expand')
                expand.set('dir', '0')
    
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + etree.tostring(root, encoding='unicode')


# ============== Main API ==============

def generate_cpt(requirement: str, output_name: str = None) -> dict:
    """主入口：输入自然语言需求，输出 CPT 文件"""
    print(f'\n{"="*60}')
    print(f'Requirement: {requirement[:80]}...')
    
    # Step 1: Classify
    meta = classify_requirement(requirement)
    print(f'  Report type: {meta["report_type"]}')
    
    # Step 2: Extract params
    params = extract_params_with_llm(requirement)
    params.update(meta)
    print(f'  Title: {params.get("title","?")}')
    print(f'  Columns: {len(params.get("columns",[]))}')
    
    # Step 3: Build CPT
    cpt_xml = build_cpt(params)
    
    # Step 4: Validate and fix
    cpt_xml = validate_and_fix(cpt_xml)
    
    # Step 5: Save
    if output_name is None:
        output_name = re.sub(r'[^\w]','_', params.get('title','report')[:30])
    if not output_name.endswith('.cpt'):
        output_name += '.cpt'
    out_path = os.path.join(OUT_DIR, output_name)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(cpt_xml)
    
    print(f'  Saved: {out_path}')
    print(f'  Size: {len(cpt_xml)} bytes')
    
    return {'path': out_path, 'xml': cpt_xml, 'params': params}


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        req = ' '.join(sys.argv[1:])
        generate_cpt(req)
    else:
        # Test with sample requirements
        tests = [
            "做一个合同采购管理报表，包含项目类型、业务部门、通知时间、合同金额，需要按部门分组，能按日期筛选",
            "做一个销售数据柱状图，按月统计销售额，按地区分组",
            "做一个员工信息填报表单，包含姓名、部门、入职日期、工资",
        ]
        for t in tests:
            result = generate_cpt(t)
            print(f'\nPreview (first 500 chars):')
            print(result['xml'][:500])
