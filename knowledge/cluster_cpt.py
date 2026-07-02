"""CPT 结构聚类 — 两阶段分治

阶段1: 目录标签预分类 (8大组)
阶段2: 组内 KMeans 聚类 (自动确定K值 - 肘部法则)
"""

import sys, os, json, math
from collections import Counter, defaultdict
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

INPUT = r'C:\workspace\01_knowledge\parsed\cpt_features.jsonl'
OUT_DIR = r'C:\workspace\01_knowledge\parsed'
os.makedirs(OUT_DIR, exist_ok=True)

FEATURE_KEYS = [
    'total_cells', 'static_text_count', 'dscolumn_count', 'formula_count',
    'chart_count', 'xmlable_count', 'empty_o_count', 'merge_cells',
    'expand_vertical_count', 'expand_horizontal_count', 'expand_none_count',
    'function_grouper_count', 'summary_grouper_count',
    'has_condition_attr', 'has_hyperlink', 'has_widget'
]


def load_data():
    """从 JSONL 加载特征，构建特征向量"""
    records = []
    with open(INPUT, encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            if not r['parsed_ok']:
                continue
            ct = r['cells']['o_types']
            ed = r['behavior']['expand_dirs']
            gt = r['behavior']['grouper_types']
            feat = {
                'total_cells': r['cells']['total'],
                'static_text_count': ct.get('static_text', 0),
                'dscolumn_count': ct.get('DSColumn', 0),
                'formula_count': ct.get('Formula', 0),
                'chart_count': ct.get('CC', 0),
                'xmlable_count': ct.get('XMLable', 0),
                'empty_o_count': ct.get('empty_o', 0),
                'merge_cells': r['cells']['merge_cells'],
                'expand_vertical_count': ed.get('0', 0),
                'expand_horizontal_count': ed.get('1', 0),
                'expand_none_count': ed.get('none', 0),
                'function_grouper_count': gt.get('FunctionGrouper', 0),
                'summary_grouper_count': gt.get('SummaryGrouper', 0),
                'has_condition_attr': 1 if r['behavior']['has_condition_attr'] else 0,
                'has_hyperlink': 1 if r['behavior']['has_hyperlink'] else 0,
                'has_widget': 1 if r['behavior']['has_widget'] else 0,
            }
            r['_features'] = feat
            records.append(r)
    return records


def group_by_category(records):
    """按一级目录分组"""
    groups = defaultdict(list)
    for r in records:
        cat_l1 = r['category'].split('/')[0] if r['category'] else 'root'
        groups[cat_l1].append(r)
    return dict(groups)


def build_feature_matrix(records):
    """构建特征矩阵并标准化"""
    X = np.array([[r['_features'][k] for k in FEATURE_KEYS] for r in records], dtype=np.float64)
    # Log-transform count features
    for i, key in enumerate(FEATURE_KEYS):
        if key.endswith('_count') and key != 'merge_cells':
            X[:, i] = np.log1p(X[:, i])
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    return X_scaled


def find_optimal_k(n_records):
    """K = sqrt(n), min 3, max 20"""
    return max(3, min(20, int(math.sqrt(n_records))))


def cluster_group(records, group_name):
    """对一组记录进行KMeans聚类"""
    n = len(records)
    if n <= 5:
        summary = _make_cluster_summary(records, group_name, 1)
        return [summary], 1

    X = build_feature_matrix(records)
    k = find_optimal_k(n)
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = km.fit_predict(X)

    clusters = defaultdict(list)
    for i, r in enumerate(records):
        clusters[int(labels[i])].append(r)

    results = []
    for cid, members in sorted(clusters.items()):
        summary = _make_cluster_summary(members, group_name, cid + 1)
        results.append(summary)

    return results, k


def _make_cluster_summary(members, group_name, cid):
    """生成单个簇的统计摘要"""
    feat_avg = {}
    for key in FEATURE_KEYS:
        vals = [m['_features'][key] for m in members]
        feat_avg[key] = round(float(np.mean(vals)), 2)

    all_otypes = Counter()
    for m in members:
        for k, v in m['cells']['o_types'].items():
            all_otypes[k] += v
    dom_type = all_otypes.most_common(1)[0][0] if all_otypes else 'unknown'

    titles = []
    for m in members[:5]:
        ts = m['semantic'].get('title_candidates', [])
        if ts:
            titles.append(ts[0])

    return {
        'cluster_id': f'{group_name}_{cid:02d}',
        'size': len(members),
        'label': f'{group_name}-{dom_type}',
        'dominant_o_type': dom_type,
        'feature_avg': feat_avg,
        'sample_titles': titles[:3],
        'member_files': [m['filepath'] for m in members]
    }


def main():
    print('Loading...')
    records = load_data()
    print(f'{len(records)} records loaded')

    groups = group_by_category(records)
    total_clusters = 0
    output_groups = {}

    for gname in sorted(groups.keys()):
        recs = groups[gname]
        print(f'{gname}: {len(recs)} records -> ', end='')
        clusters, k = cluster_group(recs, gname)
        total_clusters += k
        print(f'{k} clusters')
        output_groups[gname] = {
            'total': len(recs),
            'n_clusters': k,
            'clusters': clusters
        }

    output = {
        'total_clusters': total_clusters,
        'total_samples': len(records),
        'groups': output_groups
    }

    out_path = os.path.join(OUT_DIR, 'clusters.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'\nTotal: {total_clusters} clusters')
    print(f'Saved: {out_path}')
    return output


if __name__ == '__main__':
    main()
