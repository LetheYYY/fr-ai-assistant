"""CPT 三级自检器

L1: XML语法（标签闭合、属性合法）
L2: 结构完整性（PrivilegeControl、RG、Expand、样式引用）
L3: 语义正确性（字段引用、分组规则、数据源匹配）
"""
import re, json
from lxml import etree
from collections import Counter


def check(cpt_xml, datasource_catalog_path=None):
    """三级检查入口。返回 (passed, issues_by_level)"""
    issues = {"L1": [], "L2": [], "L3": []}

    # L1: Parse XML
    try:
        root = etree.fromstring(cpt_xml.encode('utf-8'))
    except Exception as e:
        issues["L1"].append(f"XML解析失败: {e}")
        return False, issues

    # L1: Root tag
    tag = root.tag.split('}')[-1] if '}' in root.tag else root.tag
    if tag != 'WorkBook':
        issues["L1"].append(f"根元素应为WorkBook, 实际为{tag}")

    # L1: Required children
    required = ['Report', 'StyleList']
    found = set()
    for child in root:
        t = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        found.add(t)
    for r in required:
        if r not in found:
            issues["L1"].append(f"缺少必要元素: {r}")

    # L2: Cell structure
    cells = root.findall('.//C')
    if not cells:
        issues["L2"].append("没有单元格定义")

    ds_cols = []
    summary_cols = []
    style_indices = set()
    for cell in cells:
        c = int(cell.get('c', 0))
        r = int(cell.get('r', 0))
        cell_id = f"C({c},{r})"

        # PrivilegeControl
        if cell.find('PrivilegeControl') is None:
            issues["L2"].append(f"{cell_id} 缺少PrivilegeControl")

        # O element
        o = cell.find('O')
        if o is None:
            issues["L2"].append(f"{cell_id} 缺少O元素")

        # Expand check
        expand = cell.find('Expand')
        if expand is None:
            issues["L2"].append(f"{cell_id} 缺少Expand")

        # Style index
        s = cell.get('s', '')
        if s:
            style_indices.add(int(s))

        # DSColumn checks
        if o is not None and o.get('t') == 'DSColumn':
            ds_cols.append(cell_id)
            attrs = o.find('.//Attributes')
            if attrs is None:
                issues["L2"].append(f"{cell_id} DSColumn缺少Attributes")
            rg = o.find('.//RG')
            if rg is None:
                issues["L2"].append(f"{cell_id} DSColumn缺少分组规则RG")

            # SummaryGrouper check
            cls = rg.get('class', '') if rg is not None else ''
            if 'SummaryGrouper' in cls:
                summary_cols.append(cell_id)
                fn = o.find('.//FN')
                if fn is None or not fn.text:
                    issues["L2"].append(f"{cell_id} SummaryGrouper缺少聚合函数FN")

        # Chart check
        if o is not None and o.get('t') == 'CC':
            chart = o.find('.//Chart')
            if chart is None:
                issues["L2"].append(f"{cell_id} CC类型缺少Chart元素")

        # Formula check
        if o is not None and o.get('t') == 'Formula':
            if not o.text or not o.text.strip():
                issues["L2"].append(f"{cell_id} Formula缺少公式内容")

    # Style reference check
    styles = root.findall('.//Style')
    defined_styles = set(range(len(styles)))
    orphan_styles = style_indices - defined_styles
    if orphan_styles:
        issues["L2"].append(f"引用了不存在的样式索引: {orphan_styles}")

    # L3: Semantic checks
    # Extract SQL from TableDataMap
    tdm = root.find('.//TableDataMap')
    sql_text = ''
    if tdm is not None:
        query = tdm.find('.//Query')
        if query is not None and query.text:
            sql_text = query.text.strip()

    if sql_text and ds_cols:
        # Extract columns from SELECT clause
        select_part = sql_text.upper().split('FROM')[0] if 'FROM' in sql_text.upper() else sql_text
        # Get AS aliases and raw column names
        sql_columns = set()
        for part in select_part.replace('SELECT', '').split(','):
            part = part.strip()
            if ' AS ' in part.upper():
                alias = part.upper().split(' AS ')[-1].strip()
                sql_columns.add(alias)
            else:
                # Remove table prefix
                col = part.split('.')[-1].strip()
                sql_columns.add(col)

        # Check DSColumn fields exist in SQL
        for cell in cells:
            o = cell.find('O')
            if o is not None and o.get('t') == 'DSColumn':
                attrs = o.find('.//Attributes')
                if attrs is not None:
                    field = attrs.get('columnName', '').upper()
                    if field and field not in sql_columns:
                        c = cell.get('c', '?')
                        r = cell.get('r', '?')
                        issues["L3"].append(f"C({c},{r}) 字段'{field}'在SQL SELECT中未找到")

        # Check GROUP BY matches FunctionGrouper
        group_fields = set()
        if 'GROUP BY' in sql_text.upper():
            gb = sql_text.upper().split('GROUP BY')[1].split('ORDER BY')[0] if 'ORDER BY' in sql_text.upper() else sql_text.upper().split('GROUP BY')[1]
            for f in gb.split(','):
                group_fields.add(f.strip())

        if group_fields and ds_cols:
            for cell in cells:
                o = cell.find('O')
                if o is not None and o.get('t') == 'DSColumn':
                    attrs = o.find('.//Attributes')
                    rg = o.find('.//RG')
                    if attrs is not None and rg is not None:
                        cls = rg.get('class', '')
                        field = attrs.get('columnName', '').upper()
                        if 'FunctionGrouper' in cls and field not in group_fields:
                            c = cell.get('c', '?')
                            r = cell.get('r', '?')
                            issues["L3"].append(f"C({c},{r}) 使用了FunctionGrouper但字段'{field}'不在GROUP BY中")

    # Dataset name consistency
    ds_names = set()
    for cell in cells:
        o = cell.find('O')
        if o is not None and o.get('t') == 'DSColumn':
            attrs = o.find('.//Attributes')
            if attrs is not None:
                ds = attrs.get('dsName', '')
                if ds:
                    ds_names.add(ds)
    if len(ds_names) > 1:
        issues["L3"].append(f"使用了多个数据源: {ds_names}（建议统一）")

    # Parameter panel check
    param_panel = root.find('.//ReportParameterAttr')
    has_params = param_panel is not None and len(param_panel) > 0
    if has_params:
        param_names = set()
        for cell in cells:
            o = cell.find('O')
            if o is not None:
                for attr in o.findall('.//Attributes'):
                    ds = attr.get('dsName', '')
                    col = attr.get('columnName', '')
                    # Check if there are parameter references in SQL
                    if sql_text and f'${{{col}}}' in sql_text:
                        param_names.add(col)

    # Summary: count issues
    total_issues = sum(len(v) for v in issues.values())
    passed = total_issues == 0

    return passed, issues


def print_report(passed, issues):
    """打印检查报告"""
    print("\n" + "=" * 50)
    print("CPT 三级自检报告")
    print("=" * 50)

    for level in ["L1", "L2", "L3"]:
        count = len(issues[level])
        icon = "✅" if count == 0 else "⚠️" if count <= 3 else "❌"
        level_name = {"L1": "XML语法", "L2": "结构完整性", "L3": "语义正确性"}
        print(f"{icon} {level_name[level]}: {count}个问题")
        for issue in issues[level]:
            print(f"   - {issue}")

    total = sum(len(v) for v in issues.values())
    if total == 0:
        print("\n✅ 全部检查通过")
    else:
        print(f"\n共 {total} 个问题需要处理")

    return total == 0


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        path = sys.argv[1]
        with open(path, 'r', encoding='utf-8') as f:
            xml = f.read()
        passed, issues = check(xml)
        print_report(passed, issues)
