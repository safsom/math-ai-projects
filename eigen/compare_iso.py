"""Shared-environment vs isolated compilation of the same OpenAI theorems.

Per theorem (auxiliary _proof_N/_simp_N lemmas folded into their parent, as in analyze.py): are the gesture multiset (u), the parent-child bigrams (b) and the size identical?
Pooled: Jensen-Shannon divergence of the coarse gesture mix between the two compilations.
"""
import collections, glob, json, math, os, sys
os.environ.setdefault('MERGE_ARITH', '1')
from analyze import coarse, user_name, strip_internal, GENERATED

HERE = os.path.dirname(os.path.abspath(__file__))
ISO = sys.argv[1] if len(sys.argv) > 1 else f'{HERE}/out_iso'


def project_of(m):
    p = m.split('.')
    return '.'.join(p[:3]) if len(p) > 3 else '.'.join(p[:2]) + '._root'


def records(path):
    out, seen = {}, set()
    if os.path.exists(path):
        for r in map(json.loads, open(path)):
            u = user_name(r['n'])
            if r['n'] in seen or (GENERATED.search(u) and strip_internal(u) == u):
                continue
            seen.add(r['n'])
            k = (project_of(r['m']), strip_internal(u))
            x = out.setdefault(k, dict(u=collections.Counter(), b=collections.Counter(), sorry=False))
            x['u'].update({coarse(g): c for g, c in r['u'].items()})
            x['b'].update(r['b'])
            x['sorry'] |= r['sorry']
    return out


iso = {}
for p in glob.glob(f'{ISO}/OAI.*.jsonl'):
    if not p.endswith(('.log.jsonl', '.trace.jsonl')):
        iso.update(records(p))
# projects that stalled in the shared run were recovered from this isolated run, so they are not a comparison
RECOVERED = {p['name'] for p in json.load(open(f'{HERE}/jobs/isolated_openai_retry.json'))['projects']}
projs = sorted({k[0] for k in iso} - RECOVERED)
rows, pool_s, pool_i = [], collections.Counter(), collections.Counter()
diffs = collections.Counter()
for proj in projs:
    shared = records(f'{HERE}/out_final/{proj}.jsonl')
    keys_i = {k for k in iso if k[0] == proj}
    keys_s = {k for k in shared if k[0] == proj}
    both = keys_i & keys_s
    same_u = same_b = 0
    for k in both:
        a, b = shared[k], iso[k]
        same_u += a['u'] == b['u'] and a['sorry'] == b['sorry']
        same_b += a['b'] == b['b']
        if a['u'] != b['u']:
            for g, c in (b['u'] - a['u']).items():
                diffs['+' + g] += c
            for g, c in (a['u'] - b['u']).items():
                diffs['-' + g] += c
        if not a['sorry'] and not b['sorry']:
            pool_s.update(a['u'])
            pool_i.update(b['u'])
    rows.append((proj, len(keys_s), len(keys_i), len(both), same_u, same_b,
                 sum(iso[k]['sorry'] for k in keys_i), sum(shared[k]['sorry'] for k in keys_s)))


def js(p, q):
    P, Q = sum(p.values()), sum(q.values())
    d = 0.0
    for g in set(p) | set(q):
        a, b = p[g] / P, q[g] / Q
        m = (a + b) / 2
        d += (a * math.log2(a / m) if a else 0) + (b * math.log2(b / m) if b else 0)
    return d / 2


print(f'{"project":45s} shared  iso  both  same-u  same-b  sorry(iso/shared)')
for r in rows:
    print(f'{r[0]:45s} {r[1]:6d} {r[2]:5d} {r[3]:5d} {r[4]:7d} {r[5]:7d}  {r[6]}/{r[7]}')
T = [sum(r[i] for r in rows) for i in range(1, 8)]
print(f'{"TOTAL":45s} {T[0]:6d} {T[1]:5d} {T[2]:5d} {T[3]:7d} {T[4]:7d}  {T[5]}/{T[6]}')
if T[2]:
    print(f'identical gesture multiset: {T[3] / T[2]:.4f}; identical bigrams: {T[4] / T[2]:.4f}')
    print(f'pooled coarse-gesture JS divergence shared vs isolated: {js(pool_s, pool_i):.2e} bits '
          f'({sum(pool_s.values())} vs {sum(pool_i.values())} nodes)')
    print('largest per-gesture differences (+ = more in isolated):')
    for g, c in diffs.most_common(15):
        print(f'  {c:6d} {g}')

if T[2] and len(sys.argv) > 2:
    json.dump(dict(projects=[r[0] for r in rows if r[3]], n=T[2], same_u=T[3], same_b=T[4], sorry_iso=T[5], sorry_shared=T[6],
                   js_bits=js(pool_s, pool_i), nodes_shared=sum(pool_s.values()), nodes_iso=sum(pool_i.values())),
              open(sys.argv[2], 'w'), indent=1)
