"""Write the two driver jobs: (A) mathlib theorems + human libraries, (B) a stratified OpenAI sample."""
import json, math, os, random, re
import pandas as pd
from make_job import job as oai_job

HERE = os.path.dirname(os.path.abspath(__file__))
IMP = re.compile(r"^\s*(?:public\s+)?import\s+(?:all\s+)?([\w.']+)", re.M)

def library_modules(root, top):
    mods = {}
    for dp, dn, fn in os.walk(os.path.join(root, top)):
        for f in fn:
            if f.endswith('.lean'):
                p = os.path.join(dp, f)
                m = os.path.relpath(p, root)[:-5].replace('/', '.')
                src = open(p, encoding='utf-8', errors='replace').read()
                mods[m] = dict(path=p, imports=[i for i in IMP.findall(src[:20000]) if i.startswith(top + '.')])
    order, seen = [], set()
    def visit(m):
        if m in seen or m not in mods: return
        seen.add(m)
        for i in mods[m]['imports']: visit(i)
        order.append(m)
    for m in sorted(mods): visit(m)
    return [dict(mod=m, path=mods[m]['path']) for m in order]

human = [dict(name=f'human.{top}', modules=library_modules(f'{HERE}/human/{d}', top))
         for d, top in [('SphereEversion', 'SphereEversion'), ('carleson', 'Carleson')]]
A = dict(out=f'{HERE}/out', imports=['Mathlib'], mathlibNames=f'{HERE}/mathlib_thm_names.txt', projects=human)
json.dump(A, open('job_A.json', 'w'))
print('job A:', [(p['name'], len(p['modules'])) for p in human])

pool = pd.read_csv('compile_pool.csv')
rng = random.Random(20261010)
target = 90
share = pool.groupby('area').size()
picks = []
for area, n in share.items():
    k = min(n, max(3, round(target * n / len(pool))))
    picks += rng.sample(sorted(pool[pool.area == area].project), k)
B = oai_job(sorted(picks), f'{HERE}/out', '')
json.dump(B, open('job_B.json', 'w'))
sel = pool[pool.project.isin(picks)]
print('job B:', len(picks), 'projects,', sel.clines.sum(), 'closure lines,', sum(len(p['modules']) for p in B['projects']), 'module runs; imports', B['imports'])
print(sel.groupby('area').size().to_string())
