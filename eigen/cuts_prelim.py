"""Preliminary compression signals from the 0/1/ω class labels already in the gesture counts.

Per proof (auxiliaries folded into their parent, as in analyze.py): counts of cuts by class
(cut:τ:0 dead, cut:τ:1 linear, cut:τ:ω shared, cut:β unlabelled β-redex) and of hypotheses by class
(λh:τ:m), against the proof's size in steps (DAG nodes). Output: out_final/cuts_prelim.json.
"""
import collections, glob, json, os, re
import numpy as np
from analyze import user_name, strip_internal, GENERATED, HUMAN_REACH, project_and_group

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out_final')
CUT = re.compile(r'^cut:(.*):([01ω])$')
HYP = re.compile(r'^λh:(.*):([01ω])$')
FIELDS = ['c0', 'c1', 'cw', 'cb', 'h0', 'h1', 'hw', 'n']


def feats(u):
    f = dict.fromkeys(FIELDS, 0)
    for g, v in u.items():
        m = CUT.match(g)
        if m:
            f['c' + m.group(2).replace('ω', 'w')] += v
        elif g == 'cut:β':
            f['cb'] += v
        else:
            m = HYP.match(g)
            if m:
                f['h' + m.group(2).replace('ω', 'w')] += v
    return f


def corpus_records():
    by = collections.defaultdict(lambda: collections.defaultdict(lambda: dict.fromkeys(FIELDS, 0)))
    def add(corpus, proj, parent, r):
        x = by[corpus][(proj, parent)]
        for k, v in feats(r['u']).items():
            x[k] += v
        x['n'] += r['nodes']
    for r in map(json.loads, open(os.path.join(OUT, 'mathlib.jsonl'))):
        if r['sorry'] or r['tr']:
            continue
        add('mathlib', project_and_group('mathlib', r['m'])[0], r['parent'], r)
    paths = [(p, 'openai') for p in glob.glob(os.path.join(OUT, 'OAI.*.jsonl'))]
    paths += [(p, 'human') for p in glob.glob(os.path.join(os.environ.get('HOUT', OUT), 'human.*.jsonl'))]
    for path, corpus in paths:
        base = os.path.basename(path)[:-6]
        if base.endswith(('.log', '.trace')):
            continue
        reach = set(HUMAN_REACH.get(base, [])) if corpus == 'human' else None
        seen = set()
        for r in map(json.loads, open(path)):
            u = user_name(r['n'])
            if r['n'] in seen or r['sorry'] or r['tr'] or (GENERATED.search(u) and strip_internal(u) == u):
                continue
            if corpus == 'openai' and r['p'] != base:
                continue
            if reach is not None and r['m'] not in reach:
                continue
            seen.add(r['n'])
            proj = project_and_group(corpus, r['m'])[0]
            add(corpus, proj, strip_internal(u), r)
    return by


def auc(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    r = np.argsort(np.argsort(np.concatenate([a, b]), kind='mergesort'))
    # average ranks for ties
    allv = np.concatenate([a, b])
    order = np.argsort(allv, kind='mergesort')
    ranks = np.empty(len(allv))
    sv = allv[order]
    i = 0
    while i < len(sv):
        j = i
        while j + 1 < len(sv) and sv[j + 1] == sv[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    ra = ranks[:len(a)].sum()
    return (ra - len(a) * (len(a) + 1) / 2) / (len(a) * len(b))


def main():
    by = corpus_records()
    res = dict(pooled={}, project_median={}, auc={}, by_size={})
    proj_vals = {}
    for corpus, recs in by.items():
        R = [r for r in recs.values() if r['n'] >= 10]
        tot = {k: sum(r[k] for r in R) for k in FIELDS}
        C = tot['c0'] + tot['c1'] + tot['cw'] + tot['cb']
        H = tot['h0'] + tot['h1'] + tot['hw']
        res['pooled'][corpus] = dict(
            proofs=len(R), steps=tot['n'],
            cuts_per_100=100 * C / tot['n'], labelled_cuts_per_100=100 * (C - tot['cb']) / tot['n'],
            share_dead=tot['c0'] / max(1, C - tot['cb']), share_linear=tot['c1'] / max(1, C - tot['cb']),
            share_shared=tot['cw'] / max(1, C - tot['cb']), beta_share_of_cuts=tot['cb'] / max(1, C),
            shared_cuts_per_100=100 * tot['cw'] / tot['n'],
            hyp_per_100=100 * H / tot['n'], hyp_dead=tot['h0'] / H, hyp_linear=tot['h1'] / H, hyp_shared=tot['hw'] / H,
            proofs_with_cut=float(np.mean([(r['c0'] + r['c1'] + r['cw'] + r['cb']) > 0 for r in R])),
            proofs_with_shared_cut=float(np.mean([r['cw'] > 0 for r in R])))
        # project-level rates (projects with >= 20 proofs)
        P = collections.defaultdict(list)
        for (proj, _), r in recs.items():
            if r['n'] >= 10:
                P[proj].append(r)
        vals = collections.defaultdict(list)
        for proj, rs in P.items():
            if len(rs) < 20:
                continue
            n = sum(r['n'] for r in rs)
            lab = sum(r['c0'] + r['c1'] + r['cw'] for r in rs)
            vals['cuts_per_100'].append(100 * sum(r['c0'] + r['c1'] + r['cw'] + r['cb'] for r in rs) / n)
            vals['shared_cuts_per_100'].append(100 * sum(r['cw'] for r in rs) / n)
            vals['linear_cuts_per_100'].append(100 * sum(r['c1'] for r in rs) / n)
            vals['dead_cuts_per_100'].append(100 * sum(r['c0'] for r in rs) / n)
            vals['beta_per_100'].append(100 * sum(r['cb'] for r in rs) / n)
            vals['share_shared'].append(sum(r['cw'] for r in rs) / lab if lab else np.nan)
            vals['hyp_dead'].append(sum(r['h0'] for r in rs) / max(1, sum(r['h0'] + r['h1'] + r['hw'] for r in rs)))
            vals['hyp_shared'].append(sum(r['hw'] for r in rs) / max(1, sum(r['h0'] + r['h1'] + r['hw'] for r in rs)))
        proj_vals[corpus] = vals
        res['project_median'][corpus] = {k: float(np.nanmedian(v)) for k, v in vals.items()} | {'projects': len(vals['cuts_per_100'])}
        # size-stratified: shared-cut rate by proof size bin
        bins = [10, 30, 100, 300, 1000, 10 ** 9]
        rows = []
        for lo, hi in zip(bins, bins[1:]):
            rs = [r for r in R if lo <= r['n'] < hi]
            if rs:
                n = sum(r['n'] for r in rs)
                rows.append(dict(lo=lo, hi=hi, proofs=len(rs),
                                 shared_per_100=100 * sum(r['cw'] for r in rs) / n,
                                 linear_per_100=100 * sum(r['c1'] for r in rs) / n,
                                 dead_per_100=100 * sum(r['c0'] for r in rs) / n,
                                 beta_per_100=100 * sum(r['cb'] for r in rs) / n))
        res['by_size'][corpus] = rows
    for other in ('mathlib', 'human'):
        res['auc'][f'openai_vs_{other}'] = {k: float(auc([x for x in proj_vals['openai'][k] if x == x],
                                                         [x for x in proj_vals[other][k] if x == x]))
                                            for k in proj_vals['openai']}
    json.dump(res, open(os.path.join(OUT, 'cuts_prelim.json'), 'w'), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
