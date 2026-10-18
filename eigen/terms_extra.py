"""Follow-up studies on one proof-term output file (default mathlib).

1. Rank ladder: created redexes need a cut of rank >= 1. Check it, and compare how much a proof
   can compress (chi_ub) by the highest rank among its cuts.
2. Missed sharing: where the explicit layout beats the author's, how much tree is saved and by
   which proofs (refactoring candidates); split into extra sharing of the author's own cuts vs new cuts.
3. Bound tightness: how close kappa comes to the product bound sum log2(uses), by cut count.
Writes out_terms/terms_extra_<name>.json.
"""
import collections, json, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from terms_analysis import measures, MIN  # noqa: E402
from analyze import user_name, strip_internal, GENERATED  # noqa: E402

path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'out_terms_v4', 'mathlib.jsonl')
name = os.path.basename(path)[:-6]
lg = math.log2

rows = []
for line in open(path):
    r = json.loads(line)
    if 'tS' not in r or r.get('tt') or r['sorry'] or r.get('ctr') or r['tr']:
        continue
    u = user_name(r['n'])
    if strip_internal(u) != u or GENERATED.search(u) or r['cN'][0] < MIN:
        continue
    m = measures(r)
    rk = np.array(m['rk']).reshape(4, 3)
    m['maxrank'] = int(max((i for i in range(4) if rk[i].sum()), default=-1))  # -1: no cuts
    m['maxrank_shared'] = int(max((i for i in range(4) if rk[i, 2]), default=-1))
    m['ncuts'] = len(r['cuts'])
    m['m'] = r['m']; m['n'] = r['n']
    m['G'] = r['tG']
    rows.append(m)

res = dict(file=name, proofs=len(rows))

# 1. rank ladder
R = [m for m in rows if m['resid'] > 0]
res['resid_proofs'] = len(R)
res['resid_with_rank_ge1_cut'] = float(np.mean([m['maxrank'] >= 1 for m in R])) if R else None
res['resid_violations'] = [m['n'] for m in R if m['maxrank'] < 1][:20]
lad = {}
for k in (-1, 0, 1, 2, 3):
    S = [m for m in rows if m['maxrank_shared'] == k]
    if S:
        ub = np.array([m['chi_ub'] for m in S])
        lb = np.array([m['chi_lb'] for m in S])
        ca = np.array([m['chi_author'] for m in S])
        lad[str(k)] = dict(n=len(S), chi_author=float(ca.mean()), chi_lb=float(lb.mean()), chi_ub=float(ub.mean()),
                           ub_p99=float(np.percentile(ub, 99)), ub_max=float(ub.max()),
                           author_p99=float(np.percentile(ca, 99)), author_max=float(ca.max()),
                           resid_share=float(np.mean([m['resid'] > 0 for m in S])))
res['ladder_by_max_shared_rank'] = lad

# 2. missed sharing
tot_S = sum(m['S'] for m in rows)
tot_author = sum(m['N3'] / 2 ** m['chi_author'] for m in rows)   # N4
tot_G = sum(min(m['S'] / 2 ** m['chi_lb'], m['N3'] / 2 ** m['chi_author']) for m in rows)
tot_D = sum(m['D'] for m in rows)
res['totals'] = dict(cutfree=tot_S, author_layout=tot_author, explicit_layout=tot_G, dag=tot_D,
                     saving_author=1 - tot_author / tot_S, saving_explicit=1 - tot_G / tot_S, saving_dag=1 - tot_D / tot_S)
miss = sorted(rows, key=lambda m: -(m['N3'] / 2 ** m['chi_author'] - m['S'] / 2 ** m['chi_lb']))
res['top_missed'] = [dict(n=m['n'], m=m['m'], cutfree=m['S'], author=round(m['N3'] / 2 ** m['chi_author']),
                          explicit=round(m['S'] / 2 ** m['chi_lb']), dag=m['D'], missed_bits=round(m['missed'], 2),
                          named=m['named'], shared=m['shared']) for m in miss[:25]]
by_mod = collections.Counter()
for m in rows:
    by_mod[m['m'].rsplit('.', 1)[0]] += max(0.0, m['N3'] / 2 ** m['chi_author'] - m['S'] / 2 ** m['chi_lb'])
res['missed_by_dir'] = by_mod.most_common(15)

# 3. tightness of kappa <= sum log2 uses
T = collections.defaultdict(list)
for m in rows:
    if m['prod_bound'] > 0:
        T[min(m['ncuts'], 10)].append(m['kappa'] / m['prod_bound'])
res['tightness_by_ncuts'] = {str(k): dict(n=len(v), median=float(np.median(v)), p90=float(np.percentile(v, 90)))
                             for k, v in sorted(T.items())}

json.dump(res, open(os.path.join(HERE, 'out_terms', f'terms_extra_{name}.json'), 'w'), indent=1)
print(json.dumps({k: v for k, v in res.items() if k not in ('top_missed',)}, indent=1)[:6000])
for t in res['top_missed'][:12]:
    print(t)
