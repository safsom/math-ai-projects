"""Write the jobs in jobs/ with this checkout's path in place of @ROOT@ (into jobs/local/)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
src = os.path.join(HERE, 'jobs')
dst = os.path.join(src, 'local')
os.makedirs(dst, exist_ok=True)
for f in sorted(os.listdir(src)):
    if f.endswith('.json'):
        open(os.path.join(dst, f), 'w').write(open(os.path.join(src, f)).read().replace('@ROOT@', ROOT))
        print(os.path.join(dst, f))
