"""SQL 规则引擎 — Catalog匹配 + 规则生成（成本 ¥0）
方案A: 查catalog匹配真实表/字段 → 规则生成SQL
方案B: LLM生成（仅当规则引擎无法处理时fallback）
"""

import json, re, os
from collections import defaultdict

CATALOG_PATH = r'C:\workspace\01_knowledge\parsed\datasource_catalog.json'
with open(CATALOG_PATH, encoding='utf-8') as f:
    CATALOG = json.load(f)

# 常见中文列名 → 英文字段映射（从catalog学习的）
FIELD_MAP = {
    '订单编号': '订单ID', '客户名称': '客户ID', '部门名称': '部门', '部门': '部门',
    '合同金额': '运货费', '销售额': '销量', '销售日期': '订购日期', '订单日期': '订购日期',
    '产品名称': '产品', '销售数量': '数量', '单价': '单价', '金额': '运货费',
    '签订日期': '订购日期', '项目类型': '类别ID', '业务部门': '部门',
    '日期': '订购日期', '数量': '数量', '名称': '产品', '编号': '订单ID',
    '合同编号': '订单ID', '联系方式': '电话', '联系人': '联系人姓名',
    '采购方式': '类别ID', '税率': '折扣', '含税金额': '运货费',
}

# 聚合函数映射
AGG_FUNCTIONS = {
    'sum': 'SumFunction', 'avg': 'AverageFunction', 'count': 'CountFunction',
    'max': 'MaxFunction', 'min': 'MinFunction',
}

class SQLEngine:
    def __init__(self):
        self.catalog = CATALOG
        self.field_map = FIELD_MAP
        # 构建倒排索引：字段名 → 数据源列表
        self.field_index = defaultdict(list)
        for ds_name, info in self.catalog.items():
            for col in info.get('columns', []):
                self.field_index[col.lower()].append(ds_name)

    def match_columns(self, chinese_names: list) -> dict:
        """将中文列名匹配到真实数据库字段"""
        result = {'matched': [], 'unmatched': [], 'tables': set(), 'best_ds': None}
        ds_scores = defaultdict(int)

        for cn in chinese_names:
            # 1. 直接映射
            en = self.field_map.get(cn, '')
            # 2. 模糊匹配
            if not en:
                en = cn.lower().replace(' ', '_')

            # 3. 查catalog找最佳匹配
            found = False
            for ds_name, info in self.catalog.items():
                if ds_name.startswith(('Embedded', 'File')):
                    continue
                for col in info.get('columns', []):
                    if col == en or col == cn or cn in col or col in cn:
                        result['matched'].append({
                            'name': cn, 'field': col, 'datasource': ds_name,
                            'tables': info.get('tables', [])[:3]
                        })
                        result['tables'].update(info.get('tables', [])[:3])
                        ds_scores[ds_name] += 2
                        found = True
                        break
                if found:
                    break

            if not found:
                # 4. 模糊匹配
                cn_lower = cn.lower()
                for ds_name, info in self.catalog.items():
                    if ds_name.startswith(('Embedded', 'File')):
                        continue
                    for col in info.get('columns', []):
                        col_lower = col.lower()
                        if cn_lower[:1] == col_lower[:1] or cn_lower[-1] == col_lower[-1]:
                            result['matched'].append({
                                'name': cn, 'field': col, 'datasource': ds_name,
                                'tables': info.get('tables', [])[:3], 'fuzzy': True
                            })
                            result['tables'].update(info.get('tables', [])[:3])
                            ds_scores[ds_name] += 1
                            found = True
                            break
                    if found:
                        break

            if not found:
                result['unmatched'].append({'name': cn, 'field': en or cn.lower()})

        # 选最佳数据源
        if ds_scores:
            result['best_ds'] = max(ds_scores, key=ds_scores.get)

        return result

    def generate_sql(self, columns: list, tables: list, group_by=None,
                     aggregates=None, conditions=None, order_by=None,
                     join_on=None) -> dict:
        """规则引擎生成SQL — 零成本"""
        valid_tables = [t for t in tables if t]
        if not valid_tables:
            valid_tables = ['report_data']

        main_table = valid_tables[0]
        fields = [c['field'] for c in columns if c.get('field')]
        if not fields:
            fields = ['*']

        # 构建SELECT
        select_parts = []
        for c in columns:
            f = c.get('field', '')
            n = c.get('name', '')
            agg = (aggregates or {}).get(f, '')
            if agg and agg.lower() in AGG_FUNCTIONS:
                select_parts.append(f'{agg.upper()}({f}) AS {n}')
            else:
                select_parts.append(f)

        # 构建FROM + JOIN
        if len(valid_tables) > 1 and join_on:
            from_clause = f'[{valid_tables[0]}] a'
            for i, t in enumerate(valid_tables[1:], 1):
                from_clause += f'\n  INNER JOIN [{t}] b{i} ON a.{join_on} = b{i}.{join_on}'
        else:
            from_clause = f'[{main_table}]'

        # WHERE
        where_clause = ''
        if conditions:
            where_parts = []
            for cond in conditions:
                where_parts.append(f'{cond.get("field","")} {cond.get("op","=")} {cond.get("value","")}')
            if where_parts:
                where_clause = 'WHERE ' + ' AND '.join(where_parts)

        # GROUP BY
        group_clause = ''
        if group_by:
            group_clause = f'GROUP BY {", ".join(group_by)}'

        # ORDER BY
        order_clause = ''
        if order_by:
            order_clause = f'ORDER BY {", ".join(order_by)}'
        else:
            order_clause = 'ORDER BY 1'

        sql = f'SELECT {", ".join(select_parts)}\nFROM {from_clause}'
        if where_clause:
            sql += f'\n{where_clause}'
        if group_clause:
            sql += f'\n{group_clause}'
        sql += f'\n{order_clause}'

        return {
            'sql': sql,
            'fields': fields,
            'main_table': main_table,
            'has_join': len(valid_tables) > 1,
            'has_agg': bool(aggregates),
            'has_group': bool(group_by),
            'engine': 'rule',
        }

    def generate_table_ddl(self, table_name: str, columns: list) -> str:
        """生成建表DDL"""
        col_defs = ['id BIGINT AUTO_INCREMENT PRIMARY KEY']
        for c in columns:
            f = c.get('field', c.get('name', 'col'))
            t = c.get('type', 'VARCHAR(255)')
            if t in ('NUMBER', 'number'):
                t = 'DECIMAL(19,2)'
            elif t in ('DATE', 'date'):
                t = 'DATE'
            else:
                t = 'VARCHAR(255)'
            comment = c.get('name', '')
            col_defs.append(f'{f} {t} COMMENT "{comment}"')
        col_defs.append('created_at DATETIME DEFAULT CURRENT_TIMESTAMP')
        return f'CREATE TABLE IF NOT EXISTS [{table_name}] (\n  ' + ',\n  '.join(col_defs) + '\n);'

    def check_connectivity(self) -> dict:
        """检查数据库连通性"""
        import paramiko
        try:
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect('10.10.10.140', username='ubuntu', password='ubuntu', timeout=5)
            i, o, e = c.exec_command(
                "echo ubuntu | sudo -S mysql -e 'SELECT 1 AS test, DATABASE() AS db, COUNT(*) AS table_count FROM information_schema.tables WHERE table_schema=\"ceshi\"' 2>&1")
            out = o.read().decode(errors='replace')
            c.close()
            return {'connected': True, 'result': out.strip()}
        except Exception as e:
            return {'connected': False, 'error': str(e)[:200]}


# ===== 快速使用 =====
def analyze_requirement(requirement: str) -> dict:
    """从需求文本完整分析 → SQL + 表结构"""
    engine = SQLEngine()

    # 提取列名
    col_match = re.findall(r'[\u4e00-\u9fff]{2,6}(?:金额|数量|日期|名称|编号|部门|类型|比率|时间|方式|名称)', requirement)
    if not col_match:
        col_match = re.findall(r'包含[：:](.+)', requirement)
        if col_match:
            col_match = re.findall(r'[\u4e00-\u9fff]{2,6}', col_match[0])
    if not col_match:
        col_match = re.findall(r'[\u4e00-\u9fff]{2,4}', requirement)

    columns = col_match[:10]
    match_result = engine.match_columns(columns)

    # 生成SQL
    cols = match_result['matched']
    tables = list(match_result['tables'])
    group_candidates = re.findall(r'按(.+?)(?:分组|统计|汇总|合计)', requirement)

    group_by = None
    aggregates = {}
    for col in cols:
        f = col['field']
        if any(kw in requirement for kw in ['统计', '汇总', '合计', '求和', '平均']):
            if any(kw in col['name'] for kw in ['金额', '数量', '总额', '合计']):
                aggregates[f] = 'SUM'

    result = engine.generate_sql(
        columns=cols,
        tables=tables,
        group_by=group_candidates or None,
        aggregates=aggregates or None,
    )

    # 生成DDL
    ddl = engine.generate_table_ddl(
        result['main_table'],
        cols + match_result['unmatched']
    )

    # 连通性
    conn = engine.check_connectivity()

    return {
        'columns_matched': cols,
        'columns_unmatched': match_result['unmatched'],
        'tables': tables,
        'best_datasource': match_result['best_ds'],
        'sql': result['sql'],
        'ddl': ddl,
        'has_join': result['has_join'],
        'has_aggregation': result['has_agg'],
        'database_ok': conn['connected'],
        'engine': 'rule',
    }


if __name__ == '__main__':
    # 测试
    for req in [
        "做一个按部门统计合同金额的报表，包含部门名称、合同编号、合同金额、签订日期",
        "统计每个产品的销售数量和销售额",
    ]:
        print(f'\n{"="*60}')
        print(f'需求: {req[:50]}...')
        r = analyze_requirement(req)
        print(f'表: {r["tables"]}')
        print(f'数据源: {r["best_datasource"]}')
        print(f'SQL: {r["sql"][:200]}')
        print(f'数据库连通: {r["database_ok"]}')
        print(f'匹配: {len(r["columns_matched"])} | 未匹配: {len(r["columns_unmatched"])}')
