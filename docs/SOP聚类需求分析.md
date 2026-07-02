# CPT 结构聚类 — SOP 需求分析文档

> 版本: v1.0 | 日期: 2026-06-17 | 依赖: Step1 cpt_features.jsonl

---

## 一、目标

将 1,309 个 CPT 按结构相似度聚类为 **80~120 个结构子类**，每个子类代表一种 CPT 结构模式。

为后续 LLM 生成 SOP 描述提供高质量的分组基础。

---

## 二、输入数据

来源：`C:\workspace\01_knowledge\parsed\cpt_features.jsonl`（Step1 产出）
格式：1309 行 JSONL，每行为一个 CPT 的完整五层特征向量。

---

## 三、聚类策略：两阶段分治

### 3.1 为什么不用一次全局 KMeans？

| 问题 | 说明 |
|------|------|
| 特征尺度差异大 | total_cells (max 4781) vs has_chart (0/1) 不在同一量级 |
| 语义差异大 | 图表报表(CC 类型) 和 行式报表(DSColumn) 结构完全不同 |
| 分类混杂 | 强行混聚会把"1个Chart Cell的甘特图"和"1个Cell的图片报表"聚到一起——它们结构相同但语义完全不同 |

### 3.2 两阶段策略

```
阶段 1: 目录标签预分类（确定性，$0）
  → 按 category_l1 (顶层目录) 分为 8 个大组
  → 每组内部再做精细化分

阶段 2: 组内 KMeans 聚类（确定性，$0）
  → 每个大组内部，提取结构特征向量，做 KMeans
  → K 值通过肘部法则自动确定
  → 输出: 每个子类的中心点 + 成员列表 + 统计摘要
```

---

## 四、特征选择

### 4.1 聚类使用的特征维度（15维）

从五层特征中精选以下与**结构模式**最相关的数值特征：

| 维度 | 字段 | 来源层 | 说明 |
|------|------|--------|------|
| 1 | total_cells | cells | 单元格总数 |
| 2 | static_text_count | cells.o_types | 静态文本数 |
| 3 | dscolumn_count | cells.o_types | 数据绑定数 |
| 4 | formula_count | cells.o_types | 公式数 |
| 5 | chart_count | cells.o_types | 图表数 |
| 6 | empty_o_count | cells.o_types | 空O元素数 |
| 7 | merge_cells | cells | 合并单元格数 |
| 8 | expand_vertical_count | behavior | 纵向扩展数 |
| 9 | expand_horizontal_count | behavior | 横向扩展数 |
| 10 | expand_none_count | behavior | 无扩展数 |
| 11 | function_grouper_count | behavior | 函数分组数 |
| 12 | summary_grouper_count | behavior | 汇总分组数 |
| 13 | has_condition_attr | behavior | 有条件属性(0/1) |
| 14 | has_hyperlink | behavior | 有超链接(0/1) |
| 15 | has_widget | behavior | 有控件(0/1) |

> 不包含：file_path、category、xml_version、style_count 等元信息。聚类只关心**结构**，不关心来源。

### 4.2 特征归一化

- 计数值（cells_*）→ MinMaxScaler 归一化到 [0, 1]
- 布尔值（has_*）→ 保持 0/1
- 对于 Chart 类别：额外加权 chart_count 维度（×2），确保图表类型不和其他类型混淆

---

## 五、K 值确定：肘部法则

对每组跑 K=2 到 K=min(20, n/5)，计算 inertia（簇内平方和）：

```
K 值选择规则:
  - 优先找肘部点（inertia 下降速率突变处）
  - 若肘部不明显，取 n/8（平均每个簇 8 个样本）
  - K 上限 = min(20, n/3)
  - K 下限 = 2
```

---

## 六、输出数据格式

### 6.1 主输出: 聚类结果

```
C:\workspace\01_knowledge\parsed\clusters.json
```

```json
{
  "total_clusters": 105,
  "total_samples": 1309,
  "groups": {
    "Chart": {
      "total": 442,
      "n_clusters": 18,
      "clusters": [
        {
          "cluster_id": "Chart_01",
          "size": 25,
          "label": "基础柱状图",
          "centroid": {...},
          "members": [
            {"file": "Chart/BarChart/...", "title": "..."},
            ...
          ],
          "feature_summary": {
            "avg_cells": 1.2,
            "chart_count": 25,
            "dominant_o_type": "CC",
            ...
          }
        },
        ...
      ]
    },
    "Primary": {...},
    ...
  }
}
```

### 6.2 辅助输出

| 文件 | 用途 |
|------|------|
| `clusters.json` | 完整聚类结果 |
| `clusters_summary.csv` | Excel可读的汇总表 |
| `cluster_stats.json` | 每组的inertia/轮廓系数 |

---

## 七、技术栈

| 库 | 用途 |
|----|------|
| **scikit-learn** | KMeans 聚类、MinMaxScaler、silhouette_score |
| **numpy** | 特征矩阵运算 |
| **json** | 读写 JSON/JSONL |
| **matplotlib** (可选) | 肘部法则可视化（保存PNG不弹窗） |

---

## 八、聚类质量评估

### 8.1 定量指标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 轮廓系数 (Silhouette) | > 0.3 | 越高越好，负值说明聚类错误 |
| inertia 下降率 | 肘部明显 | 肘部点=最优K |
| 簇大小均衡度 | 无极端值 | 避免某个簇只有1个样本 |

### 8.2 人工抽检（每簇抽1个）

每个簇随机抽取1个成员，人工/LLM判断：
- 该簇的成员是否结构相似？
- 簇标签是否符合特征汇总？

---

## 九、验收标准

- [ ] 1309 个样本全部分配到某个簇（无遗漏）
- [ ] 总簇数在 80~120 之间
- [ ] 每个簇 >= 3 个成员（无不合理的小簇）
- [ ] 同簇内成员的 top-3 O类型一致
- [ ] 每个簇生成结构特征摘要
- [ ] 能在 30 秒内完成全量聚类
