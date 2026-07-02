"""SOP 生成器 — 从聚类结果生成 SOP 描述

对每个核心簇（size >= 3），提取统计摘要，调用 LLM 生成 SOP 节点描述。
如果未配置 API Key，则生成摘要文本供手动/后续批量调用。
"""

import json, os, sys
from collections import Counter

CLUSTERS_PATH = r'C:\workspace\01_knowledge\parsed\clusters.json'
FEATURES_PATH = r'C:\workspace\01_knowledge\parsed\cpt_features.jsonl'
OUT_PATH = r'C:\workspace\01_knowledge\parsed\cluster_summaries.json'

SOP_SYSTEM_PROMPT = """你是 FineReport 报表专家。请根据以下 CPT 模板簇的结构特征摘要，生成一个 SOP（标准操作流程）节点。

## 输出格式（严格遵守）

```json
{
  "cluster_id": "簇ID",
  "sop_name": "SOP节点名称（简短，如 行式报表-纵向扩展-参数筛选）",
  "report_type": "报表类型（行式报表/分组报表/交叉报表/图表报表/填报报表/参数报表/复合报表）",
  "one_line_desc": "一句话功能描述",
  "trigger_condition": "何时触发此SOP（如：用户需要展示明细列表且需要参数筛选）",
  "required_inputs": ["需要的输入参数1", "需要的输入参数2"],
  "steps": [
    {"step": 1, "action": "操作描述", "xml_template": "该步骤生成的CPT XML片段示例", "check": "检查项"},
    {"step": 2, "action": "...", "xml_template": "...", "check": "..."}
  ],
  "common_mistakes": ["常见错误1", "常见错误2"],
  "related_clusters": ["关联的簇ID"]
}
```

## 规则
1. steps 控制在 3-8 步
2. xml_template 必须是有效的 CPT XML 片段（<C> 元素）
3. common_mistakes 至少列出 2 个
4. 基于提供的特征数据，不要编造不存在的功能
"""


def load_clusters():
    with open(CLUSTERS_PATH, encoding='utf-8') as f:
        return json.load(f)


def cluster_to_text(c):
    """将簇的统计特征转为自然语言摘要，供 LLM 理解"""
    fa = c['feature_avg']
    lines = []
    lines.append(f"簇ID: {c['cluster_id']}")
    lines.append(f"样本数: {c['size']}")
    lines.append(f"主单元格类型: {c['dominant_o_type']}")
    lines.append(f"样本标题示例: {c['sample_titles'][:3]}")

    # Structure
    lines.append(f"\n结构特征:")
    lines.append(f"  平均 {fa['total_cells']:.0f} 个单元格, {fa['merge_cells']:.0f} 个合并单元格")
    lines.append(f"  单元格类型分布: 静态文本~{fa['static_text_count']:.0f}, DSColumn~{fa['dscolumn_count']:.0f}, 公式~{fa['formula_count']:.0f}, 图表~{fa['chart_count']:.1f}, XMLable~{fa['xmlable_count']:.0f}")

    # Behavior
    lines.append(f"\n行为特征:")
    lines.append(f"  扩展方向: 纵向~{fa['expand_vertical_count']:.0f}, 横向~{fa['expand_horizontal_count']:.0f}, 无扩展~{fa['expand_none_count']:.0f}")
    lines.append(f"  分组规则: FunctionGrouper~{fa['function_grouper_count']:.0f}, SummaryGrouper~{fa['summary_grouper_count']:.0f}")
    flags = []
    if fa['has_condition_attr'] >= 0.5: flags.append("条件属性")
    if fa['has_hyperlink'] >= 0.5: flags.append("超链接")
    if fa['has_widget'] >= 0.5: flags.append("控件")
    lines.append(f"  功能标签: {', '.join(flags) if flags else '无特殊标签'}")

    # File count
    lines.append(f"\n成员文件({len(c['member_files'])}个): {', '.join(c['member_files'][:5])}")
    if len(c['member_files']) > 5:
        lines.append(f"  ...及另外{len(c['member_files'])-5}个文件")

    return '\n'.join(lines)


def generate_summaries(clusters_data, use_llm=False, api_key=None):
    """生成簇摘要，可选调用 LLM"""
    results = []

    for gname, gdata in sorted(clusters_data['groups'].items()):
        for c in gdata['clusters']:
            if c['size'] < 3:  # Skip small clusters
                continue

            summary_text = cluster_to_text(c)
            item = {
                'cluster_id': c['cluster_id'],
                'group': gname,
                'size': c['size'],
                'feature_summary': c['feature_avg'],
                'summary_text': summary_text,
                'sop': None  # Will be filled by LLM
            }

            if use_llm and api_key:
                item['sop'] = call_llm(summary_text, api_key)
                print(f'  [LLM] {c["cluster_id"]} OK')

            results.append(item)

    return results


def call_llm(summary_text, api_key):
    """调用 DeepSeek API 生成 SOP"""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SOP_SYSTEM_PROMPT},
                {"role": "user", "content": f"请为以下CPT模板簇生成SOP节点:\n\n{summary_text}"}
            ],
            temperature=0.3,
            max_tokens=800
        )
        content = response.choices[0].message.content
        # Try to parse JSON from response
        try:
            # Extract JSON from markdown code block
            if '```json' in content:
                start = content.index('```json') + 7
                end = content.index('```', start)
                content = content[start:end].strip()
            sop = json.loads(content)
            return sop
        except:
            return {"raw_response": content}
    except Exception as e:
        return {"error": str(e)[:200]}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--api-key', type=str, default=None, help='DeepSeek API Key')
    parser.add_argument('--dry-run', action='store_true', help='只生成摘要，不调用LLM')
    args = parser.parse_args()

    data = load_clusters()
    use_llm = bool(args.api_key) and not args.dry_run

    print(f'Generating summaries for {sum(1 for g in data["groups"].values() for c in g["clusters"] if c["size"] >= 3)} core clusters...')
    if use_llm:
        print('Mode: LLM (DeepSeek API)')
    else:
        print('Mode: Dry-run (summaries only, no LLM)')

    results = generate_summaries(data, use_llm=use_llm, api_key=args.api_key)

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f'\nSaved {len(results)} cluster summaries to {OUT_PATH}')
    if not use_llm:
        print(f'\nTo generate SOPs with LLM, run:')
        print(f'  python sop_generator.py --api-key YOUR_DEEPSEEK_KEY')


if __name__ == '__main__':
    main()
