"""
CPT 解析器 — 五层解剖模型

将 FineReport .cpt 文件解析为结构化特征向量。
每层提取确定性特征，不依赖 LLM。

Layer 0: 元信息层 (xmlVersion, releaseVersion, 顶层元素清单)
Layer 1: 结构层 (行列规模, Sheet数量, 模块存在性)
Layer 2: 单元格层 (类型分布, 合并单元格)
Layer 3: 行为层 (扩展方向, 分组规则, 条件属性, 超链接)
Layer 4: 语义层 (数据源, 字段名, 标题, 样式)
"""

import os, json, time
from lxml import etree
from collections import Counter


class CPTParser:
    """单个 CPT 文件的五层解析器"""

    def __init__(self, filepath: str, category: str = ""):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.category = category
        self.tree = None
        self.root = None

    def parse(self) -> dict:
        """主入口：解析文件，返回完整特征字典"""
        t0 = time.time()
        result = {
            "filepath": self.filepath,
            "filename": self.filename,
            "category": self.category,
            "parsed_ok": False,
            "errors": []
        }
        try:
            self.tree = etree.parse(self.filepath)
            self.root = self.tree.getroot()
            result["meta"] = self._parse_meta()
            result["structure"] = self._parse_structure()
            result["cells"] = self._parse_cells()
            result["behavior"] = self._parse_behavior()
            result["semantic"] = self._parse_semantic()
            result["parsed_ok"] = True
        except Exception as e:
            result["errors"].append(f"Parse error: {str(e)[:200]}")

        result["parse_time_ms"] = round((time.time() - t0) * 1000, 1)
        return result

    # ---- Layer 0: 元信息 ----
    def _parse_meta(self) -> dict:
        root = self.root
        tag = self._strip_ns(root.tag)
        top_children = {}
        for child in root:
            t = self._strip_ns(child.tag)
            top_children[t] = top_children.get(t, 0) + 1
        return {
            "root_tag": tag,
            "xml_version": root.get("xmlVersion", ""),
            "release_version": root.get("releaseVersion", ""),
            "top_children": top_children
        }

    # ---- Layer 1: 结构 ----
    def _parse_structure(self) -> dict:
        root = self.root
        reports = root.findall("Report")
        sheet_names = [r.get("name", "") for r in reports]
        cells = root.findall(".//C")
        rows_set, cols_set = set(), set()
        for cell in cells:
            r = int(cell.get("r", 0))
            c = int(cell.get("c", 0))
            rs = int(cell.get("rs", 1))
            cs = int(cell.get("cs", 1))
            for ri in range(r, r + rs):
                rows_set.add(ri)
            for ci in range(c, c + cs):
                cols_set.add(ci)

        row_height_el = root.find(".//RowHeight")
        col_width_el = root.find(".//ColumnWidth")
        rh_default = row_height_el.get("defaultValue", "") if row_height_el is not None else ""
        cw_default = col_width_el.get("defaultValue", "") if col_width_el is not None else ""

        top_names = [self._strip_ns(c.tag) for c in root]

        return {
            "sheet_count": len(reports),
            "sheet_names": sheet_names,
            "max_row": max(rows_set) + 1 if rows_set else 0,
            "max_col": max(cols_set) + 1 if cols_set else 0,
            "total_cells": len(cells),
            "row_height_default": rh_default,
            "col_width_default": cw_default,
            "has_table_data_map": "TableDataMap" in top_names,
            "has_report_web_attr": "ReportWebAttr" in top_names,
            "has_mobile_attr": "ElementCaseMobileAttr" in top_names,
            "has_parameter_attr": "ReportParameterAttr" in top_names,
            "has_theme_mark": "TemplateThemeAttrMark" in top_names,
        }

    # ---- Layer 2: 单元格 ----
    def _parse_cells(self) -> dict:
        cells = self.root.findall(".//C")
        o_types = Counter()
        merge_count = 0
        style_indices = Counter()

        for cell in cells:
            o = cell.find("O")
            if o is not None:
                t = o.get("t", "static_text")
                o_types[t] += 1
            else:
                o_types["empty_o"] += 1

            if int(cell.get("cs", 1)) > 1 or int(cell.get("rs", 1)) > 1:
                merge_count += 1

            s = cell.get("s", "")
            if s:
                style_indices[s] += 1

        return {
            "total": len(cells),
            "o_types": dict(o_types),
            "merge_cells": merge_count,
            "style_indices": dict(style_indices),
            "unique_styles": len(style_indices)
        }

    # ---- Layer 3: 行为 ----
    def _parse_behavior(self) -> dict:
        cells = self.root.findall(".//C")
        expand_dirs = Counter()
        grouper_types = Counter()
        has_condition = False
        has_hyperlink = False
        has_widget = False
        has_cell_sort = False

        for cell in cells:
            expand = cell.find("Expand")
            if expand is not None:
                d = expand.get("dir", "none")
                expand_dirs[d] += 1
                if expand.find("cellSortAttr") is not None:
                    has_cell_sort = True

            rg = cell.find(".//RG")
            if rg is not None:
                cls = rg.get("class", "")
                grouper_types[self._short_class(cls)] += 1

            if cell.find(".//Condition") is not None:
                has_condition = True
            if cell.find(".//Hyperlink") is not None:
                has_hyperlink = True
            if cell.find(".//Widget") is not None:
                has_widget = True

        return {
            "expand_dirs": dict(expand_dirs),
            "grouper_types": dict(grouper_types),
            "has_condition_attr": has_condition,
            "has_hyperlink": has_hyperlink,
            "has_widget": has_widget,
            "has_cell_sort": has_cell_sort,
        }

    # ---- Layer 4: 语义 ----
    def _parse_semantic(self) -> dict:
        root = self.root
        # Data source info
        dscolumn_cells = root.findall('.//C/O[@t="DSColumn"]/..')
        ds_names, col_names = set(), []
        for cell in dscolumn_cells:
            attrs = cell.find('.//Attributes')
            if attrs is not None:
                dn = attrs.get("dsName", "")
                cn = attrs.get("columnName", "")
                if dn: ds_names.add(dn)
                if cn: col_names.append(cn)

        # Titles and headers
        cells = root.findall(".//C")
        titles, headers = [], []
        for cell in cells:
            r = int(cell.get("r", 0))
            o = cell.find("O")
            if o is not None and o.get("t", "static_text") == "static_text":
                text = (o.text or "").strip()
                if text:
                    if r == 0:
                        titles.append(text)
                    elif r == 1:
                        headers.append(text)

        # Style info
        styles = root.findall(".//Style")
        has_image_bg, has_custom_border = False, False
        font_names = set()
        for style in styles:
            bg = style.find('.//Background')
            if bg is not None and bg.get("name") == "ImageBackground":
                has_image_bg = True
            border = style.find('.//Border')
            if border is not None and len(border) > 0:
                has_custom_border = True
            font = style.find('.//FRFont')
            if font is not None:
                fn = font.get("name", "")
                if fn: font_names.add(fn)

        # Chart info
        chart_cells = root.findall('.//C/O[@t="CC"]/..')
        chart_types = set()
        for cell in chart_cells:
            chart_el = cell.find('.//Chart')
            if chart_el is not None:
                cc = chart_el.get("chartClass", "")
                if cc: chart_types.add(self._short_class(cc))

        return {
            "datasource_names": sorted(ds_names),
            "column_names": col_names,
            "title_candidates": titles,
            "header_texts": headers,
            "style_count": len(styles),
            "font_names": sorted(font_names),
            "has_image_background": has_image_bg,
            "has_custom_border": has_custom_border,
            "chart_types": sorted(chart_types),
            "has_chart": len(chart_cells) > 0,
        }

    # ---- 工具方法 ----
    @staticmethod
    def _strip_ns(tag: str) -> str:
        return tag.split("}")[-1] if "}" in tag else tag

    @staticmethod
    def _short_class(full_class: str) -> str:
        return full_class.split(".")[-1] if full_class else "unknown"


def safe_parse(filepath: str, category: str = "") -> dict:
    """带异常保护的解析入口"""
    try:
        return CPTParser(filepath, category).parse()
    except Exception as e:
        return {
            "filepath": filepath,
            "filename": os.path.basename(filepath),
            "category": category,
            "parsed_ok": False,
            "errors": [f"Fatal: {str(e)[:300]}"],
            "parse_time_ms": 0
        }


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        result = safe_parse(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "")
        print(json.dumps(result, ensure_ascii=False, indent=2))
