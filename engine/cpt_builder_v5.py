"""CPT Builder v5 — 全功能覆盖

支持的单元格类型:
  static_text, DSColumn, CC(chart), Formula, BiasTextPainter,
  SubReport, I(image), XMLable(widget)

支持的行为:
  Expand(纵向/横向/不扩展), Grouper(Function/Summary/Custom),
  Condition, Hyperlink, cellSortAttr, Widget, PrivilegeControl

支持的报表结构:
  标题行, 表头行, 数据行, 汇总行, 图表区域, 参数面板
"""

import json, re, os
from lxml import etree

OUT = r'os.path.dirname(os.path.abspath(__file__))\output'
FR = r'/path/to/fr/reportlets'
CATALOG = None
_MYSQL_HOST = '10.10.10.140'

os.makedirs(OUT, exist_ok=True)


# ==================== 目录加载 ====================

def load_catalog():
    global CATALOG
    if CATALOG is None:
        try:
            with open(r'C:\workspace\01_knowledge\parsed\datasource_catalog.json', encoding='utf-8') as f:
                CATALOG = json.load(f)
        except:
            CATALOG = {}
    return CATALOG


def get_real_tables():
    """从真实数据库获取表列表"""
    try:
        import paramiko
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(_MYSQL_HOST, username='ubuntu', password='ubuntu', timeout=5)
        i, o, e = c.exec_command("echo ubuntu | sudo -S mysql -e 'USE ceshi; SHOW TABLES;' 2>&1")
        out = o.read().decode(errors='replace')
        c.close()
        tables = [l.strip() for l in out.split('\n') if l.strip() and not l.startswith('Tables_in') and not 'sudo' in l]
        return [t for t in tables if t]
    except:
        return []


def get_table_columns(table_name):
    """获取真实表的列信息"""
    try:
        import paramiko
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(_MYSQL_HOST, username='ubuntu', password='ubuntu', timeout=5)
        cmd = f"echo ubuntu | sudo -S mysql -e 'USE ceshi; DESCRIBE {table_name};' 2>&1"
        i, o, e = c.exec_command(cmd)
        out = o.read().decode(errors='replace')
        c.close()
        cols = []
        for line in out.split('\n')[1:]:
            parts = line.split('\t')
            if len(parts) >= 2:
                cols.append({'field': parts[0], 'type': parts[1]})
        return cols
    except:
        return []


# ==================== XML 片段生成器 ====================

def cell_title(title, col_span):
    return f'<C c="0" r="0" cs="{col_span}" s="0"><O><![CDATA[{title}]]></O><PrivilegeControl/><Expand/></C>'

def cell_header(col_idx, label, is_first=False, is_last=False):
    s = "1" if is_first else ("3" if is_last else "2")
    return f'<C c="{col_idx}" r="1" s="{s}"><O><![CDATA[{label}]]></O><PrivilegeControl/><Expand dir="0"><cellSortAttr/></Expand></C>'

def cell_dscolumn(col_idx, field, ds='ds1', grouper='FunctionGrouper', expand='0'):
    rg = f'<RG class="com.fr.report.cell.cellattr.core.group.{grouper}"/>'
    if grouper == 'SummaryGrouper':
        rg = f'<RG class="com.fr.report.cell.cellattr.core.group.{grouper}"><FN><![CDATA[com.fr.data.util.function.SumFunction]]></FN></RG>'
    return f'<C c="{col_idx}" r="2" s="0"><O t="DSColumn"><Attributes dsName="{ds}" columnName="{field}"/><Complex/>{rg}<Parameters/><cellSortAttr/></O><PrivilegeControl/><Expand dir="{expand}"/></C>'

def cell_formula(col_idx, row, formula_text):
    return f'<C c="{col_idx}" r="{row}" s="0"><O t="Formula"><![CDATA[{formula_text}]]></O><PrivilegeControl/><Expand/></C>'

def cell_static(col_idx, row, text):
    return f'<C c="{col_idx}" r="{row}" s="0"><O><![CDATA[{text}]]></O><PrivilegeControl/><Expand/></C>'

def cell_summary(col_idx, field, ds='ds1', fn='SumFunction'):
    return f'<C c="{col_idx}" r="3" s="0"><O t="DSColumn"><Attributes dsName="{ds}" columnName="{field}"/><Complex/><RG class="com.fr.report.cell.cellattr.core.group.SummaryGrouper"><FN><![CDATA[com.fr.data.util.function.{fn}]]></FN></RG><Parameters/></O><PrivilegeControl/><Expand dir="0"/></C>'

def cell_condition(col_idx, row, condition_text):
    """条件属性：如 value()>1000000 标红"""
    return f'<C c="{col_idx}" r="{row}" s="0"><Condition class="com.fr.data.condition.ListCondition"><![CDATA[{condition_text}]]></Condition></C>'

def cell_chart(chart_title, chart_type='BarChart', col_span=10, row_span=16):
    return f'''<C c="0" r="1" cs="{col_span}" rs="{row_span}" s="0">
<O t="CC"><LayoutAttr selectedIndex="0"/><ChangeAttr enable="false" changeType="button" timeInterval="5"/>
<Chart name="默认" chartClass="com.fr.plugin.chart.vanchart.VanChart">
<Chart class="com.fr.plugin.chart.vanchart.VanChart">
<GI><AttrBackground><Background name="NullBackground"/><Attr shadow="false"/></AttrBackground><AttrBorder><Attr lineStyle="0"/></AttrBorder></GI>
<ChartAttr isJSDraw="true" isStyleGlobal="false"/>
<Title4VanChart><Title><GI><AttrBackground><Background name="NullBackground"/></AttrBackground><AttrBorder><Attr lineStyle="0"/></AttrBorder></GI>
<O><![CDATA[{chart_title}]]></O><TextAttr><Attr alignText="0"><FRFont name="Microsoft YaHei UI" style="0" size="16"/></Attr></TextAttr></Title></Title4VanChart>
<Plot4VanChart/>
</Chart></Chart></O><PrivilegeControl/><Expand/></C>'''

def cell_hyperlink(col_idx, row, text, url):
    return f'<C c="{col_idx}" r="{row}" s="0"><O><![CDATA[{text}]]></O><PrivilegeControl/><Hyperlink><LinkType>Web</LinkType><Target>{url}</Target></Hyperlink><Expand/></C>'

def cell_image(col_idx, row, image_path, col_span=1, row_span=1):
    return f'<C c="{col_idx}" r="{row}" cs="{col_span}" rs="{row_span}" s="0"><O t="I"><Image><![CDATA[{image_path}]]></Image></O><PrivilegeControl/><Expand/></C>'

def cell_widget(col_idx, row, widget_type='ComboBox', widget_name='widget1'):
    return f'<C c="{col_idx}" r="{row}" s="0"><O t="XMLable"><Widget class="com.fr.form.ui.{widget_type}" widgetName="{widget_name}"/></O><PrivilegeControl/><Expand/></C>'

def cell_bias_text(col_idx, row, text):
    return f'<C c="{col_idx}" r="{row}" s="0"><O t="BiasTextPainter"><IsBackSlash value="false"/><![CDATA[{text}]]></O><PrivilegeControl/><Expand/></C>'


# ==================== 完整 CPT 组装 ====================

def build_cpt(params):
    """params = {title, columns, sql, table, features:{chart, condition, formula, hyperlink, widget, summary, image, bias, param}, styles}"""
    cols = params.get('columns', [])
    n = len(cols) if cols else 3
    title = params.get('title', '报表')
    sql = params.get('sql', '')
    table = params.get('table', 'report_data')
    db = params.get('db', 'FRDemo')
    feat = params.get('features', {})
    ds = params.get('datasource', 'ds1')

    cells = []

    # 标题行
    cells.append(cell_title(title, n))

    # 图表模式：只放图表
    if feat.get('chart'):
        chart_title = feat.get('chart_title', title)
        cells = [cell_title(title, 1), cell_chart(chart_title, feat.get('chart_type', 'BarChart'))]
        n = 1
    else:
        # 表头行
        for i, col in enumerate(cols):
            cells.append(cell_header(i, col['name'], i == 0, i == n - 1))

        # 数据行
        for i, col in enumerate(cols):
            grouper = 'FunctionGrouper'
            if col.get('aggregate'):
                grouper = 'SummaryGrouper'

            if feat.get('formula') and col.get('formula'):
                cells.append(cell_formula(i, 2, col['formula']))
            elif feat.get('bias') and i == 0:
                cells.append(cell_bias_text(i, ' | '.join(c['name'] for c in cols)))
            elif feat.get('widget') and col.get('widget'):
                cells.append(cell_widget(i, 2, col.get('widget_type', 'ComboBox'), col.get('widget_name', f'w{i}')))
            else:
                cells.append(cell_dscolumn(i, col['field'], ds, grouper, col.get('expand', '0')))

        # 汇总行
        if feat.get('summary'):
            for i, col in enumerate(cols):
                if col.get('aggregate'):
                    cells.append(cell_summary(i, col['field'], ds, col.get('agg_fn', 'SumFunction')))
                else:
                    cells.append(cell_static(i, 3, ''))

        # 条件属性
        if feat.get('condition'):
            cond_spec = feat.get('condition_spec', {})
            for i, col in enumerate(cols):
                if col['field'] in cond_spec:
                    cells.append(cell_condition(i, 2, cond_spec[col['field']]))

        # 超链接
        if feat.get('hyperlink'):
            for i, col in enumerate(cols):
                if col.get('hyperlink'):
                    cells.append(cell_hyperlink(i, 2, col['name'], col['hyperlink']))

        # 图片
        if feat.get('image'):
            img_spec = feat.get('image_spec', {})
            if img_spec:
                cells.append(cell_image(0, 1, img_spec.get('path', ''), n, 1))

    # 参数面板
    param = ''
    if feat.get('param') or params.get('has_param'):
        param = '<ReportParameterAttr><Attributes showWindow="true" delayPlaying="true" windowPosition="1" align="0" useParamsTemplate="true" currentIndex="0"/><PWTitle><![CDATA[参数]]></PWTitle></ReportParameterAttr>'

    # TableDataMap
    tdm = ''
    if sql:
        tdm = f'''<TableDataMap><TableData name="{ds}" class="com.fr.data.impl.DBTableData">
<Parameters/><Attributes maxMemRowCount="-1"/>
<Connection class="com.fr.data.impl.NameDatabaseConnection"><DatabaseName><![CDATA[{db}]]></DatabaseName></Connection>
<Query><![CDATA[{sql}]]></Query><PageQuery><![CDATA[]]></PageQuery></TableData></TableDataMap>'''

    # 样式
    styles = _build_styles(feat.get('styles', 'default'))

    # 组装
    cpt = f'''<?xml version="1.0" encoding="UTF-8"?>
<WorkBook xmlVersion="20170720" releaseVersion="10.0.0">
{tdm}
<Report class="com.fr.report.worksheet.WorkSheet" name="sheet1">
<ReportPageAttr><HR/><FR/><HC/><FC/><USE REPEAT="false" PAGE="false" WRITE="false"/></ReportPageAttr>
<ColumnPrivilegeControl/><RowPrivilegeControl/>
<RowHeight defaultValue="723900"><![CDATA[{','.join(['1143000']+['723900']*50)}]]></RowHeight>
<ColumnWidth defaultValue="2743200"><![CDATA[{','.join(['8033657','6966857']+['2743200']*max(0,n-2))}]]></ColumnWidth>
<CellElementList>
{chr(10).join(cells)}
</CellElementList>
<ReportAttrSet><ReportSettings headerHeight="0" footerHeight="0"><PaperSetting/><FollowingTheme background="true"/></ReportSettings>
<Header reportPageType="0"><Background name="NullBackground"/><LeftList/><CenterList/><RightList/></Header>
<Footer reportPageType="0"><Background name="NullBackground"/><LeftList/><CenterList/><RightList/></Footer></ReportAttrSet><PrivilegeControl/></Report>
{param}
{styles}
<DesensitizationList/><DesignerVersion DesignerVersion="LAA"/><PreviewType PreviewType="2"/>
<TemplateThemeAttrMark class="com.fr.base.iofile.attr.TemplateThemeAttrMark"><TemplateThemeAttrMark name="兼容主题" dark="false"/></TemplateThemeAttrMark>
</WorkBook>'''
    return cpt


def _build_styles(style_key='default'):
    """预设样式模板"""
    base = '''<StyleList>
<Style style_name="默认" full="true" border_source="-1" imageLayout="1">
<FRFont name="simhei" style="0" size="72"/><Background name="NullBackground"/><Border/>
</Style>'''

    if style_key == 'blue':
        return base + '''<Style style_name="Head" full="true" border_source="2" horizontal_alignment="0" imageLayout="1">
<FRFont name="Microsoft YaHei" style="0" size="72"/><Background name="ColorBackground" color="-16750900"/>
<Border><Top style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Top>
<Bottom style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Bottom>
<Left style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Left></Border></Style></StyleList>'''
    else:
        return base + '''<Style style_name="Head" full="true" border_source="2" horizontal_alignment="0" imageLayout="1">
<FRFont name="SimSun" style="0" size="72"/><Background name="NullBackground"/>
<Border><Top style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Top>
<Bottom style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Bottom>
<Left style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Left></Border></Style></StyleList>'''


# ==================== 保存部署 ====================

def save_and_deploy(cpt_xml, title):
    safe = re.sub(r'[^\w\u4e00-\u9fff]', '_', title)[:30]
    path = os.path.join(OUT, safe + '.cpt')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(cpt_xml)
    try:
        import shutil
        shutil.copy2(path, os.path.join(FR, safe + '.cpt'))
    except:
        pass
    return path


if __name__ == '__main__':
    params = {
        'title': '测试全功能报表',
        'columns': [
            {'name': '部门', 'field': 'business_dept'},
            {'name': '合同金额', 'field': 'contract_amount_tax', 'aggregate': True},
        ],
        'table': 'procurement',
        'sql': 'SELECT business_dept, SUM(contract_amount_tax) FROM procurement GROUP BY business_dept',
        'features': {'summary': True, 'param': True, 'condition': True},
    }
    cpt = build_cpt(params)
    print(save_and_deploy(cpt, '全功能测试'))
    print('OK')
