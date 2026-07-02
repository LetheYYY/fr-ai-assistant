"""
CPT Jinja2 模板库 — 10个核心报表骨架模板
每个模板对应一种 CPT 结构模式
"""
from jinja2 import Template

# ============================================================
# 基础骨架：WorkBook 外层 + ReportPageAttr + StyleList
# ============================================================

WORKBOOK_SKELETON = Template('''<?xml version="1.0" encoding="UTF-8"?>
<WorkBook xmlVersion="20211223" releaseVersion="11.5.0">
<Report class="com.fr.report.worksheet.WorkSheet" name="sheet1">
<ReportPageAttr>
<HR/><FR/><HC/><FC/>
<USE REPEAT="false" PAGE="false" WRITE="false"/>
</ReportPageAttr>
<ColumnPrivilegeControl/>
<RowPrivilegeControl/>
<RowHeight defaultValue="723900">
<![CDATA[{{ row_heights }}]]>
</RowHeight>
<ColumnWidth defaultValue="2743200">
<![CDATA[{{ col_widths }}]]>
</ColumnWidth>
<CellElementList>
{{ cell_elements }}
</CellElementList>
<ReportAttrSet>
<ReportSettings headerHeight="0" footerHeight="0">
<PaperSetting/>
<FollowingTheme background="true"/>
</ReportSettings>
<Header reportPageType="0"><Background name="NullBackground"/><LeftList/><CenterList/><RightList/></Header>
<Footer reportPageType="0"><Background name="NullBackground"/><LeftList/><CenterList/><RightList/></Footer>
</ReportAttrSet>
<PrivilegeControl/>
</Report>
{{ parameter_panel }}
{{ style_list }}
<DesensitizationList/>
<DesignerVersion DesignerVersion="LAA"/>
<PreviewType PreviewType="2"/>
<StrongestControlAttr class="com.fr.widgettheme.control.attr.WidgetDisplayEnhanceMarkAttr">
<StrongestControlAttr widgetEnhance="false"/>
</StrongestControlAttr>
<TemplateThemeAttrMark class="com.fr.base.iofile.attr.TemplateThemeAttrMark">
<TemplateThemeAttrMark name="兼容主题" dark="false"/>
</TemplateThemeAttrMark>
</WorkBook>''')


# ============================================================
# 样式：默认 + Head 三变体
# ============================================================

DEFAULT_STYLE_LIST = '''<StyleList>
<Style style_name="默认" full="true" border_source="-1" imageLayout="1">
<FRFont name="simhei" style="0" size="72"/>
<Background name="NullBackground"/>
<Border/>
</Style>
<Style style_name="Head_Left" full="true" border_source="2" horizontal_alignment="0" imageLayout="1">
<FRFont name="SimSun" style="0" size="72"/>
<Background name="NullBackground"/>
<Border>
<Top style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Top>
<Bottom style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Bottom>
<Left style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Left>
</Border>
</Style>
<Style style_name="Head_Center" full="true" border_source="10" horizontal_alignment="0" imageLayout="1">
<FRFont name="SimSun" style="0" size="72"/>
<Background name="NullBackground"/>
<Border>
<Top style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Top>
<Bottom style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Bottom>
</Border>
</Style>
<Style style_name="Head_Right" full="true" border_source="8" horizontal_alignment="0" imageLayout="1">
<FRFont name="SimSun" style="0" size="72"/>
<Background name="NullBackground"/>
<Border>
<Top style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Top>
<Bottom style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Bottom>
<Right style="1"><color><FineColor color="-6697729" hor="-1" ver="-1"/></color></Right>
</Border>
</Style>
</StyleList>'''


# ============================================================
# 参数面板
# ============================================================

PARAM_PANEL_TEMPLATE = Template('''<ReportParameterAttr>
<Attributes showWindow="true" delayPlaying="true" windowPosition="1" align="0" useParamsTemplate="true" currentIndex="0"/>
<PWTitle><![CDATA[参数]]></PWTitle>
</ReportParameterAttr>''')


# ============================================================
# 单元格模板
# ============================================================

# 标题行：合并N列
TITLE_CELL = Template('''<C c="0" r="0" cs="{{ col_count }}" s="0">
<O><![CDATA[{{ title }}]]></O>
<PrivilegeControl/>
<Expand/>
</C>''')

# 表头单元格（左边缘，s=1）
HEADER_LEFT = Template('''<C c="{{ col_idx }}" r="1" s="1">
<O><![CDATA[{{ label }}]]></O>
<PrivilegeControl/>
<Expand dir="0"><cellSortAttr/></Expand>
</C>''')

# 表头单元格（中间，s=2）
HEADER_CENTER = Template('''<C c="{{ col_idx }}" r="1" s="2">
<O><![CDATA[{{ label }}]]></O>
<PrivilegeControl/>
<Expand dir="0"><cellSortAttr/></Expand>
</C>''')

# 表头单元格（右边缘，s=3）
HEADER_RIGHT = Template('''<C c="{{ col_idx }}" r="1" s="3">
<O><![CDATA[{{ label }}]]></O>
<PrivilegeControl/>
<Expand dir="0"><cellSortAttr/></Expand>
</C>''')

# 数据行 DSColumn（纵向扩展 + FunctionGrouper）
DATA_CELL_VERTICAL = Template('''<C c="{{ col_idx }}" r="2" s="0">
<O t="DSColumn">
<Attributes dsName="{{ ds_name }}" columnName="{{ field_name }}"/>
<Complex/>
<RG class="com.fr.report.cell.cellattr.core.group.FunctionGrouper"/>
<Parameters/>
<cellSortAttr/>
</O>
<PrivilegeControl/>
<Expand dir="0"/>
</C>''')

# 数据行 DSColumn（横向扩展）
DATA_CELL_HORIZONTAL = Template('''<C c="{{ col_idx }}" r="2" s="0">
<O t="DSColumn">
<Attributes dsName="{{ ds_name }}" columnName="{{ field_name }}"/>
<Complex/>
<RG class="com.fr.report.cell.cellattr.core.group.FunctionGrouper"/>
<Parameters/>
</O>
<PrivilegeControl/>
<Expand dir="1"/>
</C>''')

# 汇总单元格（SummaryGrouper + SUM）
SUMMARY_CELL = Template('''<C c="{{ col_idx }}" r="3" s="0">
<O t="DSColumn">
<Attributes dsName="{{ ds_name }}" columnName="{{ field_name }}"/>
<Complex/>
<RG class="com.fr.report.cell.cellattr.core.group.SummaryGrouper">
<FN><![CDATA[com.fr.data.util.function.SumFunction]]></FN>
</RG>
<Parameters/>
</O>
<PrivilegeControl/>
<Expand dir="0"/>
</C>''')

# 图表单元格
CHART_CELL = Template('''<C c="{{ col_idx }}" r="{{ row_idx }}" cs="{{ col_span }}" rs="{{ row_span }}" s="0">
<O t="CC">
<LayoutAttr selectedIndex="0"/>
<ChangeAttr enable="false" changeType="button" timeInterval="5"/>
<Chart name="{{ chart_title }}" chartClass="com.fr.plugin.chart.vanchart.VanChart">
<Chart class="com.fr.plugin.chart.vanchart.VanChart">
<GI>
<AttrBackground><Background name="NullBackground"/><Attr shadow="false"/></AttrBackground>
<AttrBorder><Attr lineStyle="0" isRoundBorder="false" roundRadius="0"/><newColor borderColor="-1118482"/></AttrBorder>
<AttrAlpha><Attr alpha="1.0"/></AttrAlpha>
</GI>
<ChartAttr isJSDraw="true" isStyleGlobal="false"/>
<Title4VanChart>
<Title>
<GI>
<AttrBackground><Background name="NullBackground"/><Attr shadow="false"/></AttrBackground>
<AttrBorder><Attr lineStyle="0" isRoundBorder="false" roundRadius="0"/><newColor borderColor="-6908266"/></AttrBorder>
<AttrAlpha><Attr alpha="1.0"/></AttrAlpha>
</GI>
<O><![CDATA[{{ chart_title }}]]></O>
<TextAttr><Attr alignText="0"><FRFont name="Microsoft YaHei UI" style="0" size="14"/></Attr></TextAttr>
</Title>
</Title4VanChart>
<Legend4VanChart>
<Legend>
<GI><AttrBackground><Background name="NullBackground"/></AttrBackground><AttrBorder><Attr lineStyle="0"/></AttrBorder></GI>
<O><![CDATA[]]></O>
<TextAttr><Attr alignText="0"><FRFont name="Microsoft YaHei UI" style="0" size="12"/></Attr></TextAttr>
</Legend>
</Legend4VanChart>
<Plot4VanChart>
<ChartData4VanChart>
<Data4VanChart>
<Category>
<![CDATA[{{ chart_category }}]]>
</Category>
<Series>
<![CDATA[{{ chart_series }}]]>
</Series>
</Data4VanChart>
</ChartData4VanChart>
</Plot4VanChart>
</Chart>
</Chart>
</O>
<PrivilegeControl/>
<Expand/>
</C>''')

# 静态文本单元格（通用）
STATIC_CELL = Template('''<C c="{{ col_idx }}" r="{{ row_idx }}" s="0">
<O><![CDATA[{{ text }}]]></O>
<PrivilegeControl/>
<Expand/>
</C>''')


# ============================================================
# 完整报表骨架（组装好的）
# ============================================================

def build_detail_report(title, columns, ds_name="ds1"):
    """行式报表：标题 + 表头 + 数据行"""
    n = len(columns)
    cells = []
    # 标题行
    cells.append(TITLE_CELL.render(title=title, col_count=n))
    # 表头行
    for i, col in enumerate(columns):
        if i == 0:
            cells.append(HEADER_LEFT.render(col_idx=i, label=col['label']))
        elif i == n - 1:
            cells.append(HEADER_RIGHT.render(col_idx=i, label=col['label']))
        else:
            cells.append(HEADER_CENTER.render(col_idx=i, label=col['label']))
    # 数据行
    for i, col in enumerate(columns):
        cells.append(DATA_CELL_VERTICAL.render(col_idx=i, ds_name=ds_name, field_name=col['field']))
    
    row_heights = ','.join(['1143000'] + ['723900'] * 50)
    col_widths = ','.join(['2743200'] * (n + 5))
    
    return WORKBOOK_SKELETON.render(
        row_heights=row_heights,
        col_widths=col_widths,
        cell_elements='\n'.join(cells),
        parameter_panel=PARAM_PANEL_TEMPLATE.render(),
        style_list=DEFAULT_STYLE_LIST
    )


def build_group_report(title, columns, group_field, ds_name="ds1"):
    """分组报表：标题 + 表头 + 分组数据行 + 汇总行"""
    n = len(columns)
    cells = []
    cells.append(TITLE_CELL.render(title=title, col_count=n))
    
    for i, col in enumerate(columns):
        if i == 0:
            cells.append(HEADER_LEFT.render(col_idx=i, label=col['label']))
        elif i == n - 1:
            cells.append(HEADER_RIGHT.render(col_idx=i, label=col['label']))
        else:
            cells.append(HEADER_CENTER.render(col_idx=i, label=col['label']))
    
    for i, col in enumerate(columns):
        cells.append(DATA_CELL_VERTICAL.render(col_idx=i, ds_name=ds_name, field_name=col['field']))
    
    # 汇总行
    for i, col in enumerate(columns):
        if col.get('aggregate'):
            cells.append(SUMMARY_CELL.render(col_idx=i, ds_name=ds_name, field_name=col['field']))
        else:
            cells.append(STATIC_CELL.render(col_idx=i, row_idx=3, text=''))
    
    row_heights = ','.join(['1143000'] + ['723900'] * 50)
    col_widths = ','.join(['2743200'] * (n + 5))
    
    return WORKBOOK_SKELETON.render(
        row_heights=row_heights,
        col_widths=col_widths,
        cell_elements='\n'.join(cells),
        parameter_panel=PARAM_PANEL_TEMPLATE.render(),
        style_list=DEFAULT_STYLE_LIST
    )


def build_chart_report(title, chart_title, chart_category, chart_series, col_span=9, row_span=16):
    """图表报表：一个大图表单元格"""
    cells = []
    cells.append(TITLE_CELL.render(title=title, col_count=1))
    cells.append(CHART_CELL.render(
        col_idx=0, row_idx=1, col_span=col_span, row_span=row_span,
        chart_title=chart_title, chart_category=chart_category, chart_series=chart_series
    ))
    
    row_heights = ','.join(['1143000'] + ['723900'] * 50)
    col_widths = ','.join(['2743200'] * 20)
    
    return WORKBOOK_SKELETON.render(
        row_heights=row_heights,
        col_widths=col_widths,
        cell_elements='\n'.join(cells),
        parameter_panel=PARAM_PANEL_TEMPLATE.render(),
        style_list=DEFAULT_STYLE_LIST
    )

# Aliases for builder compatibility
DATA_CELL = DATA_CELL_VERTICAL
HEADER_CELL = HEADER_LEFT
