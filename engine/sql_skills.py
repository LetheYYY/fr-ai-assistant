
"""SQL Skill Set — 13个标准化SQL技能

每个Skill独立可调用、可组合:
  发现: sql_discover / sql_describe / sql_primary_keys / sql_relations
  查询: sql_select / sql_join / sql_aggregate / sql_where / sql_order
  填报: sql_insert / sql_update / sql_delete
  DDL:  sql_create_table
  验证: sql_validate / sql_explain
  参数: sql_parameterize  
"""

import re, json, paramiko
from collections import defaultdict

HOST = '10.10.10.140'
USER = 'ubuntu'
PASS = 'ubuntu'
DB = 'ceshi'


def _exec(cmd):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=5)
    _, o, e = c.exec_command(cmd)
    return o.read().decode(errors='replace'), e.read().decode(errors='replace')


def _mysql(sql):
    safe = sql.replace('"', '\\"')
    safe = safe.replace('\n', ' ')
    cmd = 'echo %s | sudo -S mysql -e "USE %s; %s" 2>&1' % (PASS, DB, safe)
    out, err = _exec(cmd)
    return out.strip(), err.strip()


# ============================================================
# 发现类 Skills (无需LLM，$0成本)
# ============================================================

def sql_discover():
    """Skill 1: 发现所有表"""
    cmd = 'echo %s | sudo -S mysql -e "SHOW TABLES FROM %s" 2>&1' % (PASS, DB)
    out, _ = _exec(cmd)
    tables = []
    for line in out.split('\n'):
        line = line.strip()
        if line and not line.startswith('Tables') and 'sudo' not in line and 'password' not in line:
            tables.append(line)
    return {'tables': tables, 'count': len(tables)}


def sql_describe(table):
    """Skill 2: 发现表的所有字段"""
    out, err = _mysql('DESCRIBE %s' % table)
    cols = []
    for line in out.split('\n')[1:]:
        parts = [p.strip() for p in line.split('\t') if p.strip()]
        if len(parts) >= 2:
            cols.append({
                'field': parts[0],
                'type': parts[1],
                'null': parts[2] if len(parts) > 2 else 'YES',
                'key': parts[3] if len(parts) > 3 else '',
                'default': parts[4] if len(parts) > 4 else ''
            })
    return {'table': table, 'columns': cols, 'count': len(cols)}


def sql_primary_keys(table):
    """Skill 3: 获取主键"""
    cols = sql_describe(table)['columns']
    pks = [c['field'] for c in cols if c.get('key') == 'PRI']
    return {'table': table, 'primary_keys': pks}


def sql_relations():
    """Skill 4: 推断表间外键关系"""
    tables = sql_discover()['tables']
    relations = []
    fk_patterns = ['dept_id', 'order_id', 'customer_id', 'product_id', 'user_id',
                   'category_id', 'project_id', 'contract_id', 'owner_id']
    for t in tables:
        cols = sql_describe(t)['columns']
        for c in cols:
            f = c['field']
            if f.endswith('_id') or f in fk_patterns:
                to_table = f.replace('_id', '')
                relations.append({
                    'from_table': t, 'from_field': f,
                    'to_table': to_table, 'to_field': 'id',
                    'suggested_join': 'JOIN [%s] ON [%s].%s = [%s].id' % (to_table, t, f, to_table)
                })
    return {'relations': relations, 'count': len(relations)}


# ============================================================
# 查询类 Skills (确定性规则 + LLM fallback)
# ============================================================

def sql_select(table, columns=None, top=None):
    """Skill 5: 生成SELECT语句"""
    if columns is None:
        desc = sql_describe(table)
        columns = [c['field'] for c in desc['columns']]
    fields = ', '.join(columns)
    sql = 'SELECT %s FROM [%s]' % (fields, table)
    if top:
        sql += ' LIMIT %d' % top
    return {'sql': sql, 'type': 'SELECT', 'table': table, 'fields': columns}


def sql_join(main_table, joins):
    """Skill 6: 生成JOIN查询
    
    joins = [
        {'type': 'LEFT', 'table': 'orders', 'on': 'users.id = orders.user_id'},
        {'type': 'INNER', 'table': 'products', 'on': 'orders.product_id = products.id'},
    ]
    """
    cols = sql_describe(main_table)['columns']
    fields = ['a.%s' % c['field'] for c in cols]
    
    sql = 'SELECT %s\nFROM [%s] a' % (', '.join(fields), main_table)
    
    for j in joins:
        jt = j.get('type', 'INNER')
        jtbl = j['table']
        jon = j['on']
        alias = chr(98 + joins.index(j))  # b, c, d...
        sql += '\n  %s JOIN [%s] %s ON %s' % (jt, jtbl, alias, jon)
    
    return {'sql': sql, 'type': 'JOIN', 'main_table': main_table, 'join_count': len(joins)}


def sql_aggregate(table, group_by, aggregates):
    """Skill 7: 生成聚合查询
    
    aggregates = {'amount': 'SUM', 'count': 'COUNT'}
    """
    select_parts = list(group_by)
    for field, func in aggregates.items():
        select_parts.append('%s(%s) AS %s_%s' % (func, field, func.lower(), field))
    
    sql = 'SELECT %s\nFROM [%s]\nGROUP BY %s\nORDER BY %s' % (
        ', '.join(select_parts), table, ', '.join(group_by), ', '.join(group_by))
    return {'sql': sql, 'type': 'AGGREGATE', 'group_fields': group_by, 'agg_fields': list(aggregates.keys())}


def sql_where(table, conditions):
    """Skill 8: 生成WHERE条件
    
    conditions = [
        {'field': 'amount', 'op': '>', 'value': '10000'},
        {'field': 'status', 'op': '=', 'value': 'active'},
    ]
    """
    cols = sql_describe(table)['columns']
    fields = [c['field'] for c in cols]
    
    where_parts = []
    for cond in conditions:
        val = cond['value']
        if isinstance(val, str) and not val.isdigit():
            val = "'%s'" % val
        where_parts.append('%s %s %s' % (cond['field'], cond['op'], val))
    
    sql = 'SELECT %s\nFROM [%s]\nWHERE %s' % (', '.join(fields), table, ' AND '.join(where_parts))
    return {'sql': sql, 'type': 'WHERE', 'conditions': conditions}


def sql_order(table, order_fields):
    """Skill 9: 生成ORDER BY"""
    cols = sql_describe(table)['columns']
    fields = [c['field'] for c in cols]
    
    orders = []
    for of in order_fields:
        direction = of.get('dir', 'ASC')
        orders.append('%s %s' % (of['field'], direction))
    
    sql = 'SELECT %s\nFROM [%s]\nORDER BY %s' % (', '.join(fields), table, ', '.join(orders))
    return {'sql': sql, 'type': 'ORDER', 'order_by': order_fields}


# ============================================================
# 填报类 Skills
# ============================================================

def sql_insert(table, data):
    """Skill 10: 生成INSERT语句
    
    data = {'name': '测试', 'amount': 100}
    """
    fields = list(data.keys())
    values = []
    for v in data.values():
        if isinstance(v, str):
            values.append("'%s'" % v)
        else:
            values.append(str(v))
    
    sql = 'INSERT INTO [%s] (%s) VALUES (%s)' % (table, ', '.join(fields), ', '.join(values))
    return {'sql': sql, 'type': 'INSERT'}


def sql_update(table, data, where_field, where_value):
    """Skill 11: 生成UPDATE语句"""
    sets = []
    for k, v in data.items():
        if isinstance(v, str):
            sets.append("%s='%s'" % (k, v))
        else:
            sets.append("%s=%s" % (k, v))
    
    if isinstance(where_value, str):
        where_value = "'%s'" % where_value
    
    sql = 'UPDATE [%s] SET %s WHERE %s=%s' % (table, ', '.join(sets), where_field, where_value)
    return {'sql': sql, 'type': 'UPDATE'}


def sql_delete(table, where_field, where_value):
    """Skill 12: 生成DELETE语句"""
    if isinstance(where_value, str):
        where_value = "'%s'" % where_value
    
    sql = 'DELETE FROM [%s] WHERE %s=%s' % (table, where_field, where_value)
    return {'sql': sql, 'type': 'DELETE'}


# ============================================================
# DDL与验证类 Skills
# ============================================================

def sql_create_table(table_name, columns):
    """Skill 13: 生成建表DDL
    
    columns = [
        {'name': 'id', 'type': 'BIGINT', 'extra': 'AUTO_INCREMENT PRIMARY KEY'},
        {'name': 'name', 'type': 'VARCHAR(255)', 'extra': 'NOT NULL'},
        {'name': 'amount', 'type': 'DECIMAL(19,2)', 'extra': 'DEFAULT 0.00'},
    ]
    """
    col_defs = []
    for c in columns:
        def_str = '%s %s' % (c['name'], c['type'])
        if c.get('extra'):
            def_str += ' ' + c['extra']
        col_defs.append(def_str)
    
    sql = 'CREATE TABLE IF NOT EXISTS [%s] (\n  %s\n)' % (table_name, ',\n  '.join(col_defs))
    return {'sql': sql, 'type': 'CREATE_TABLE', 'columns': len(columns)}


def sql_validate(sql_text):
    """Skill 14: 在MySQL上验证SQL (EXPLAIN)"""
    try:
        out, err = _mysql('EXPLAIN %s' % sql_text)
        return {
            'valid': 'id' in out.lower() or 'select_type' in out.lower(),
            'output': out[:300],
            'error': err[:200] if err else ''
        }
    except:
        return {'valid': False, 'error': 'Connection failed'}


def sql_parameterize(sql_text, params):
    """Skill 15: 将SQL参数化(${param})
    
    params = ['start_date', 'end_date', 'department']
    """
    param_sql = sql_text
    for p in params:
        param_sql += '\n  AND %s = \'${%s}\'' % (p, p)
    return {'sql': param_sql, 'params': params}


def sql_execute(sql_text):
    """Skill 16: 直接执行SQL并返回结果"""
    out, err = _mysql(sql_text)
    return {'result': out[:1000], 'error': err[:200]}


# ============================================================
# 批量导出所有skill注册表
# ============================================================

SKILL_REGISTRY = {
    'sql_discover':       sql_discover,
    'sql_describe':       sql_describe,
    'sql_primary_keys':   sql_primary_keys,
    'sql_relations':      sql_relations,
    'sql_select':         sql_select,
    'sql_join':           sql_join,
    'sql_aggregate':      sql_aggregate,
    'sql_where':          sql_where,
    'sql_order':          sql_order,
    'sql_insert':         sql_insert,
    'sql_update':         sql_update,
    'sql_delete':         sql_delete,
    'sql_create_table':   sql_create_table,
    'sql_validate':       sql_validate,
    'sql_parameterize':   sql_parameterize,
    'sql_execute':        sql_execute,
}

