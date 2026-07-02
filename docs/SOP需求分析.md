# CPT 样本解析器 — SOP 需求分析文档

> 版本: v1.0 | 日期: 2026-06-17 | 项目: 帆软数字员工 - CPT知识库构建

---

## 一、项目背景与目标

### 1.1 数据来源

从 FineReport 11.0 安装目录获取 **1,309 个官方 CPT 示例模板**：

| 分类 | 数量 | 说明 |
|------|------|------|
| Chart | 442 | 图表(甘特图/饼图/散点图/漏斗图...) |
| SpecialSubject | 189 | 专题(超链接/排序/折叠树/Excel导入导出) |
| Advanced | 177 | 高级功能 |
| JS | 148 | JavaScript 交互 |
| Form | 140 | 填报报表 |
| Parameter | 106 | 参数查询 |
| Primary | 102 | 基础报表(行式/分组/交叉/自由) |
| phone | 5 | 移动端 |
| **合计** | **1,309** | |

### 1.2 目标

将 1,309 个 CPT 解析为结构化特征向量，为聚类、SOP 分类、RAG 提供数据基础。

### 1.3 核心原则

**代码做 90%，LLM 只做 10%** — 解析和特征提取全部确定性代码（¥0），仅子类描述用 LLM。

---

## 二、CPT 文件结构分析（基于200个抽样）

### 2.1 xmlVersion 分布

| 版本 | 数量 | 占比 |
|------|------|------|
| 20170720 | 102 | 51.0% |
| 20140501 | 38 | 19.0% |
| 20110221 | 13 | 6.5% |
| 20211223 | 12 | 6.0% |
| 20141222 | 8 | 4.0% |
| 20131111 | 8 | 4.0% |
| 20151125 | 6 | 3.0% |
| 20130114 | 12 | 6.0% |

### 2.2 releaseVersion 分布

| 版本 | 数量 | 占比 |
|------|------|------|
| 10.0.0 | 66 | 33.0% |
| 11.0.0 | 39 | 19.5% |
| 7.1.1 | 38 | 19.0% |
| 8.0.0 | 14 | 7.0% |
| N/A | 13 | 6.5% |
| 7.0.3 | 11 | 5.5% |
| 9.0.0 | 9 | 4.5% |

### 2.3 顶层元素出现率

| 元素 | 出现率 | 说明 |
|------|--------|------|
| Report | 100% | 必有 |
| StyleList | 100% | 必有 |
| TableDataMap | 97.5% | v11 中缺失 |
| DesignerVersion | 93.0% | 设计器版本 |
| PreviewType | 93.0% | 预览方式 |
| ReportParameterAttr | 92.5% | 参数面板 |
| TemplateIdAttMark | 52.0% | 模板ID标记 |
| TemplateThemeAttrMark | 19.5% | 主题标记(v11) |
| ReportWebAttr | 13.0% | Web工具栏配置 |
| ElementCaseMobileAttr | 12.5% | 移动端配置 |

### 2.4 单元格类型分布（O 元素的 t 属性）

| 类型 | 数量 | 占比 | 说明 |
|------|------|------|------|
| static_text | 1020 | 45.3% | 静态文本(无 t 属性) |
| DSColumn | 885 | 39.3% | 数据集字段绑定 |
| XMLable | 224 | 10.0% | 填报控件 |
| Formula | 76 | 3.4% | 公式单元格 |
| CC | 25 | 1.1% | 图表(Chart Component) |
| BiasTextPainter | 17 | 0.8% | 斜线表头 |
| SubReport | 6 | 0.3% | 子报表 |
| I | 2 | 0.1% | 图片 |

### 2.5 扩展方向分布

| 方向 | 数量 | 占比 | 说明 |
|------|------|------|------|
| none(无Expand) | 1641 | 67.5% | 静态单元格 |
| dir=0(纵向) | 711 | 29.2% | 纵向扩展 |
| dir=1(横向) | 79 | 3.3% | 横向扩展 |

### 2.6 分组规则分布

| 类型 | 数量 | 占比 | 说明 |
|------|------|------|------|
| FunctionGrouper | 756 | 87.7% | 函数分组(默认) |
| SummaryGrouper | 102 | 11.8% | 汇总分组(含聚合函数) |
| CustomGrouper | 4 | 0.5% | 自定义分组 |

### 2.7 单元格数量统计

| 指标 | 值 |
|------|-----|
| 最小值 | 1 |
| 最大值 | 235 |
| 平均值 | 12 |

---

## 三、五层解剖模型

```
Layer 0: 元信息层
  - xmlVersion, releaseVersion
  - 顶层元素清单(有哪些模块)

Layer 1: 结构层
  - Sheet 数量、行列规模
  - 是否有 TableDataMap / ReportWebAttr / ElementCaseMobileAttr

Layer 2: 单元格层
  - 单元格总数、合并单元格
  - 单元格类型分布(static_text/DSColumn/Formula/CC...)
  - 样式索引分布

Layer 3: 行为层
  - 扩展方向(Expand dir)
  - 分组规则(RG: FunctionGrouper/SummaryGrouper...)
  - 条件属性(Condition)
  - 超链接(Hyperlink)
  - 参数控件(Widget)

Layer 4: 语义层
  - 报表类型标签(来自目录名)
  - 标题文本/表头文本
  - 数据源名称列表
  - 参数字段列表
  - 样式特征(背景图/边框/字体)
```

---

## 四、技术栈

| 库 | 版本 | 用途 |
|----|------|------|
| **lxml** | 4.x | XML 解析，XPath 查询 |
| **numpy** | 1.26+ | 特征矩阵存储 |
| **json** | 内置 | JSON/JSONL 序列化 |
| **csv** | 内置 | CSV 导出 |
| **collections.Counter** | 内置 | 频率统计 |
| **os/glob/pathlib** | 内置 | 文件遍历 |

> 不需要 sentence-transformers、torch、langchain。这是纯确定性代码。

---

## 五、特征向量设计（50维）

### 5.1 字段定义

#### 元信息（6维）

| 字段 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| file_path | str | 相对路径 | - |
| category | str | 功能分类(Primary/DetailReport) | "unknown" |
| file_name | str | 文件名 | - |
| xml_version | str | xmlVersion属性值 | "N/A" |
| release_version | str | releaseVersion属性值 | "N/A" |
| parsed_ok | bool | 是否解析成功 | false |

#### 结构（7维）

| 字段 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| has_table_data_map | bool | 是否有TableDataMap | false |
| has_report_web_attr | bool | 是否有ReportWebAttr | false |
| has_mobile_attr | bool | 是否有移动端配置 | false |
| has_parameter_panel | bool | 是否有参数面板 | false |
| has_designer_version | bool | 是否有设计器版本 | false |
| has_preview_type | bool | 是否有预览设置 | false |
| template_theme | str | 主题名称 | "N/A" |

#### 单元格统计（10维）

| 字段 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| total_cells | int | 单元格总数 | 0 |
| static_text_count | int | 静态文本数 | 0 |
| dscolumn_count | int | 数据集字段数 | 0 |
| formula_count | int | 公式数 | 0 |
| chart_count | int | 图表数(CC) | 0 |
| bias_text_count | int | 斜线表头数 | 0 |
| sub_report_count | int | 子报表数 | 0 |
| image_count | int | 图片数(I) | 0 |
| xmlable_count | int | 填报控件数 | 0 |
| empty_o_count | int | 空O元素数 | 0 |

#### 行为统计（8维）

| 字段 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| expand_vertical_count | int | 纵向扩展数(dir=0) | 0 |
| expand_horizontal_count | int | 横向扩展数(dir=1) | 0 |
| expand_none_count | int | 无扩展数 | 0 |
| function_grouper_count | int | 函数分组数 | 0 |
| summary_grouper_count | int | 汇总分组数 | 0 |
| custom_grouper_count | int | 自定义分组数 | 0 |
| has_condition_attr | bool | 是否有条件属性 | false |
| has_hyperlink | bool | 是否有超链接 | false |
| has_widget | bool | 是否有控件 | false |

#### 语义（10维）

| 字段 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| datasource_names | list[str] | 数据源名称列表 | [] |
| column_names | list[str] | 字段名列表(DSColumn) | [] |
| title_candidates | list[str] | 标题候选(大字号静态文本) | [] |
| header_texts | list[str] | 表头文本(row=1的static_text) | [] |
| style_count | int | 样式数量 | 0 |
| font_names | list[str] | 使用的字体名 | [] |
| has_image_background | bool | 是否使用图片背景 | false |
| has_custom_border | bool | 是否使用自定义边框 | false |

#### 辅助（5维）

| 字段 | 类型 | 说明 |
|------|------|------|
| xml_byte_size | int | 文件大小(bytes) |
| top_level_elements | list[str] | 顶层子元素标签列表 |
| sheet_count | int | Sheet数量 |
| cell_cs_values | list[int] | colspan值列表 |
| cell_rs_values | list[int] | rowspan值列表 |

### 5.2 输出示例（单条JSON）

```json
{
  "meta": {
    "file_path": "Primary/CrossReport/Cross.cpt",
    "category": "Primary/CrossReport",
    "file_name": "Cross.cpt",
    "xml_version": "20170720",
    "release_version": "10.0.0",
    "parsed_ok": true
  },
  "structure": {
    "has_table_data_map": false,
    "has_report_web_attr": false,
    "has_mobile_attr": false,
    "has_parameter_panel": true,
    "has_designer_version": true,
    "has_preview_type": true,
    "template_theme": "N/A"
  },
  "cells": {
    "total_cells": 42,
    "static_text_count": 8,
    "dscolumn_count": 15,
    "formula_count": 3,
    "chart_count": 0,
    "bias_text_count": 0,
    "sub_report_count": 0,
    "image_count": 0,
    "xmlable_count": 0,
    "empty_o_count": 16
  },
  "behavior": {
    "expand_vertical_count": 15,
    "expand_horizontal_count": 5,
    "expand_none_count": 22,
    "function_grouper_count": 10,
    "summary_grouper_count": 5,
    "custom_grouper_count": 0,
    "has_condition_attr": false,
    "has_hyperlink": true,
    "has_widget": false
  },
  "semantic": {
    "datasource_names": ["ds1", "ds2"],
    "column_names": ["产品", "销量", "销售员", "地区"],
    "title_candidates": ["地区销售概况"],
    "header_texts": ["产品", "销售员", "地区", "销售总额"],
    "style_count": 3,
    "font_names": ["simhei", "SimSun"],
    "has_image_background": false,
    "has_custom_border": true
  },
  "raw": {
    "xml_bytes": 15432,
    "top_level_elements": ["Report", "ReportParameterAttr", "StyleList"],
    "sheet_count": 1,
    "cell_cs_values": [4],
    "cell_rs_values": [2]
  }
}
```

---

## 六、输出文件

| 文件 | 路径 | 用途 |
|------|------|------|
| cpt_features.jsonl | C:\workspace\01_knowledge\parsed\ | 完整特征矩阵(1309行) |
| parse_errors.jsonl | C:\workspace\01_knowledge\parsed\ | 解析失败文件列表 |
| feature_summary.json | C:\workspace\01_knowledge\parsed\ | 全局统计摘要 |

---

## 七、模块架构

```
01_knowledge/
├── cpt_parser.py           # 核心解析器
│   ├── class CPTParser:
│   │   ├── parse(path) -> dict          # 全量解析入口
│   │   ├── _parse_meta(root) -> dict    # Layer 0
│   │   ├── _parse_structure(root) -> dict # Layer 1
│   │   ├── _parse_cells(root) -> dict   # Layer 2
│   │   ├── _parse_behavior(root) -> dict # Layer 3
│   │   └── _parse_semantic(root) -> dict # Layer 4
│   │
│   └── def safe_parse(file) -> dict    # 带异常保护
│
├── batch_parse.py          # 批量执行
└── verify_parse.py         # 结果验证
```

### 错误处理

| 场景 | 处理 |
|------|------|
| XML解析失败 | 记录错误，parsed_ok=false |
| 缺失子元素 | 使用默认值(0/空/false) |
| 编码问题 | UTF-8 → GBK 降级尝试 |
| 特殊字符 | lxml recover=True 容错模式 |

---

## 八、性能预估

| 指标 | 值 |
|------|-----|
| 单文件解析 | 2-5ms |
| 1309文件总耗时 | ~10-15秒 |
| 内存峰值 | <100MB |
| 输出JSONL | ~2-3MB |

---

## 九、验收标准

- [ ] JSONL 1309行 (每行一个CPT)
- [ ] parsed_ok > 99%
- [ ] 所有特征字段非空
- [ ] category正确反映目录层级
- [ ] 20秒内完成全量解析
- [ ] feature_summary.json包含全局统计

---

## 十、后续步骤

1. **Step 1**: 运行 parser → 输出特征矩阵 (本次)
2. **Step 2**: 基于特征矩阵 KMeans 聚类 → ~120 子类
3. **Step 3**: LLM 生成子类 SOP 描述 (¥0.07)
4. **Step 4**: 构建决策树 + Jinja2 模板骨架
