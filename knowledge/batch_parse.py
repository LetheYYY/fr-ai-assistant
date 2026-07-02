"""批量解析所有CPT文件"""
import sys, os, json, time
sys.path.insert(0, r'C:\workspace\01_knowledge')
from cpt_parser import safe_parse

BASE = r'D:\FineReport_11.0\webapps\webroot\WEB-INF\reportlets\doc'
OUT_DIR = r'C:\workspace\01_knowledge\parsed'
os.makedirs(OUT_DIR, exist_ok=True)

t0 = time.time()
results, errors = [], []

for root, dirs, files in os.walk(BASE):
    for f in files:
        if not f.endswith('.cpt'):
            continue
        path = os.path.join(root, f)
        rel = os.path.relpath(root, BASE).replace(os.sep, '/')
        cat = rel if rel != '.' else 'root'
        r = safe_parse(path, cat)
        results.append(r)
        if not r['parsed_ok']:
            errors.append(r)
        if len(results) % 200 == 0:
            print(f'{len(results)} files parsed...')

# Write results
jsonl_path = os.path.join(OUT_DIR, 'cpt_features.jsonl')
with open(jsonl_path, 'w', encoding='utf-8') as f:
    for r in results:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')

err_path = os.path.join(OUT_DIR, 'parse_errors.jsonl')
with open(err_path, 'w', encoding='utf-8') as f:
    for e in errors:
        f.write(json.dumps(e, ensure_ascii=False) + '\n')

# Summary
ok = sum(1 for r in results if r['parsed_ok'])
elapsed = time.time() - t0
summary = {
    'total_files': len(results),
    'parsed_ok': ok,
    'parse_failed': len(results) - ok,
    'elapsed_seconds': round(elapsed, 1),
    'files_per_second': round(len(results) / elapsed, 1),
    'output_jsonl': jsonl_path,
    'output_errors': err_path,
}

summary_path = os.path.join(OUT_DIR, 'feature_summary.json')
with open(summary_path, 'w', encoding='utf-8') as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print(f"\nDone! {ok}/{len(results)} OK, {len(errors)} errors, {elapsed:.1f}s")
print(f"Output: {jsonl_path}")
