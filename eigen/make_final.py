"""out_final: the shared-mode sample in out/ plus the three projects recovered by the isolated retry (job_I2; Geometry.Arnold still stalls and stays out)."""
import glob, json, os
from make_job import project_of
HERE = os.path.dirname(os.path.abspath(__file__))
src, dst = f'{HERE}/out', f'{HERE}/out_final'
os.makedirs(dst, exist_ok=True)
new = [p['name'] for p in json.load(open(f'{HERE}/job_I2_used.json'))['projects']]
for f in os.listdir(src):
    if f.startswith('analysis') or os.path.exists(f'{dst}/{f}'):
        continue
    os.symlink(f'{src}/{f}', f'{dst}/{f}')
for p in new:
    recs = []
    for f in glob.glob(f'{HERE}/out_iso/OAI.*.jsonl'):
        if f.endswith(('.log.jsonl', '.trace.jsonl')):
            continue
        for r in map(json.loads, open(f)):
            if project_of(r['m']) == p:
                r['p'] = p
                recs.append(json.dumps(r) + '\n')
    for suffix in ('.jsonl', '.log.jsonl'):
        if os.path.islink(f'{dst}/{p}{suffix}'):
            os.remove(f'{dst}/{p}{suffix}')
    open(f'{dst}/{p}.jsonl', 'w').writelines(recs)
    print(p, len(recs), 'records,', sum(json.loads(l)['sorry'] for l in recs), 'sorry')
