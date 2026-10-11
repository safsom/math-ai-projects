"""Compression of proofs by cut elimination, measured in bits, split by resource class.

Inputs: out_cut/*.jsonl from the driver with GESTURE_CUTS=1. Each theorem has tree sizes N0..N3
(proof nodes, shared subterms counted at every use) of four normal forms: as written; dead cuts
(k = 0) eliminated; cuts with k <= 1 eliminated; all cuts eliminated.

Unit. One bit of cut compression means the cut-free proof is twice as large as the proof as written:
    kappa = log2(N3 / N0) = sigma - w - l
    w     = log2(N0 / N1)  weakening overhead: proofs built and never used
    l     = log2(N1 / N2)  linear overhead: the cost of naming a proof used once
    sigma = log2(N3 / N2)  contraction gain: what sharing a proof k >= 2 times saves
Intrinsic, independent of where the author put cuts (N4 keeps exactly the cuts that pay for themselves):
    chi   = log2(N3 / N4)  compressibility: bits the proof's own sharing can save at best
    rho   = log2(N0 / N4)  layout redundancy: bits the written cut layout spends above that optimum
so kappa = chi - rho.
The same unit is used one level up, where a project's local lemmas are the cuts and each reference
is a use: inlining every lemma into the results that need it gives the project's cut-free size.
"""
import collections, glob, json, math, os, sys
import numpy as np
from scipy import stats
from analyze import user_name, strip_internal, GENERATED, HUMAN_REACH, project_and_group, AI_CORPORA, AI_OUT
from cuts_prelim import auc

HERE = os.path.dirname(os.path.abspath(__file__))
CUT = os.path.join(HERE, 'out_cut')
RES = os.environ.get('CUTS_RES', os.path.join(CUT, 'results.json'))
MIN = 10  # proofs with at least this many nodes as written


def lg(a, b):
    return math.log2(a) - math.log2(b) if a and b else float('nan')


def load():
    """corpus -> project -> {theorem name: record}"""
    out = collections.defaultdict(lambda: collections.defaultdict(dict))
    files = [(os.path.join(CUT, 'mathlib.jsonl'), 'mathlib')]
    files += [(p, 'openai') for p in sorted(glob.glob(os.path.join(CUT, 'OAI.*.jsonl')))]
    files += [(p, 'human') for p in sorted(glob.glob(os.path.join(CUT, 'human.*.jsonl')))]
    files += [(os.path.join(AI_OUT, c, c + '.jsonl'), c) for c in AI_CORPORA]
    for path, corpus in files:
        if not os.path.exists(path) or path.endswith(('.log.jsonl', '.trace.jsonl')):
            continue
        base = os.path.basename(path)[:-6]
        reach = set(HUMAN_REACH.get(base, [])) if corpus == 'human' else None
        for line in open(path):
            r = json.loads(line)
            if 'cN' not in r or r['sorry'] or r['ctr'] or r['tr']:
                continue
            if corpus == 'openai' and r['p'] != base:
                continue
            if reach is not None and r['m'] not in reach:
                continue
            if corpus == 'flt' and r['m'].startswith('Theorems.'):
                continue  # one-line wrappers around the P2M.Sol proofs
            u = user_name(r['n'])
            proj = project_and_group(corpus, r['m'])[0]
            parent = r.get('parent') or strip_internal(u)
            out[corpus][proj][r['n']] = dict(
                N=r['cN'], dag=r['cdag'], cuts=r['cuts'], ncuts=r['ncuts'], refs0=r['refs0'], refs3=r['refs3'],
                parent=parent, aux=strip_internal(u) != u, gen=bool(GENERATED.search(u)) and strip_internal(u) == u)
    return out


def uses(c):
    """Effective use count of a cut: proof-position uses; a proof used only inside types or data counts once."""
    return c[1] if c[1] or len(c) < 5 else min(c[4], 1)


def proof_measures(t):
    N0, N1, N2, N3, N4 = t['N']
    gains = [(uses(c) - 1) * c[2] - c[1] - 1 for c in t["cuts"]]  # elimination minus keeping, in nodes
    return dict(N0=N0, N3=N3, N4=N4, dag=t['dag'], kappa=lg(N3, N0), w=lg(N0, N1), l=lg(N1, N2), sigma=lg(N3, N2),
                chi=lg(N3, N4), rho=lg(N0, N4),
                implicit=lg(N0, t['dag']), cuts=t['ncuts'],
                k0=sum(1 for c in t['cuts'] if uses(c) == 0), k1=sum(1 for c in t['cuts'] if uses(c) == 1),
                kw=sum(1 for c in t['cuts'] if uses(c) >= 2), profitable=sum(g > 0 for g in gains),
                beta=sum(1 for c in t['cuts'] if c[0] == 'beta'))


def project_measures(recs):
    """Lemma level: local theorems as cuts, references as uses (within the project)."""
    names = set(recs)
    U = collections.Counter()
    for t in recs.values():
        for L, c in t['refs0'].items():
            if L in names:
                U[L] += c
    memo = {}

    def SS(n, stack=()):
        if n in memo:
            return memo[n]
        if n in stack:  # mutual references should not occur; guard anyway
            return recs[n]['N'][3]
        t = recs[n]
        s = t['N'][3]
        for L, c in t['refs3'].items():
            if L in names and L != n:
                s += c * (SS(L, stack + (n,)) - 1)
        memo[n] = s
        return s

    roots = [n for n in recs if U[n] == 0]
    S0 = sum(t['N'][0] for t in recs.values())
    S3 = sum(t['N'][3] for t in recs.values())
    Sstar = sum(SS(n) for n in roots)
    lin_refs = sum(U[n] for n in recs if U[n] == 1)
    cls = collections.Counter('root' if U[n] == 0 else 'linear' if U[n] == 1 else 'shared' for n in recs)
    return dict(theorems=len(recs), roots=len(roots), lemma_linear=cls['linear'], lemma_shared=cls['shared'],
                S0=S0, S3=S3, log2_Sstar=math.log2(Sstar) if Sstar else float('nan'),
                kappa_in_proof=lg(S3, S0), kappa_lemma=lg(Sstar, S3), kappa_total=lg(Sstar, S0),
                lemma_sigma=lg(Sstar, S3 - lin_refs),
                mean_uses_shared=float(np.mean([U[n] for n in recs if U[n] >= 2])) if cls['shared'] else 0.0)


def summarize(vals):
    a = np.array([v for v in vals if v == v], float)
    if not len(a):
        return {}
    return dict(n=len(a), mean=float(a.mean()), median=float(np.median(a)),
                q10=float(np.quantile(a, .1)), q90=float(np.quantile(a, .9)), pos=float((a > 0).mean()))


def main():
    data = load()
    res = dict(per_proof={}, pooled={}, project={}, project_median={}, auc={}, by_size={}, lemma={}, cut_k={})
    proj_rates = {}
    for corpus, projs in data.items():
        P = []
        for proj, recs in projs.items():
            for n, t in recs.items():
                if not t['aux'] and not t['gen'] and t['N'][0] >= MIN:
                    P.append((proj, proof_measures(t)))
        M = [m for _, m in P]
        res['per_proof'][corpus] = {k: summarize([m[k] for m in M]) for k in ('kappa', 'w', 'l', 'sigma', 'chi', 'rho', 'implicit')}
        withcut = [m for m in M if m['cuts'] > 0]
        res['per_proof'][corpus]['given_cut'] = {k: summarize([m[k] for m in withcut]) for k in ('kappa', 'sigma', 'chi', 'rho')}
        res['per_proof'][corpus]['proofs'] = len(M)
        res['per_proof'][corpus]['with_cut'] = float(np.mean([m['cuts'] > 0 for m in M]))
        res['per_proof'][corpus]['with_profitable_cut'] = float(np.mean([m['profitable'] > 0 for m in M]))
        # rates per 100 steps use the proof's shared (DAG) size, like every other step count in the report
        tot = {k: sum(m[k] for m in M) for k in ('N0', 'dag', 'cuts', 'k0', 'k1', 'kw', 'profitable', 'beta')}
        logs = {k: sum(math.log2(m[a]) - math.log2(m[b]) for m in M) for k, (a, b) in {}.items()}
        N = collections.defaultdict(int)
        for proj, recs in projs.items():
            for t in recs.values():
                if not t['aux'] and not t['gen'] and t['N'][0] >= MIN:
                    for i in range(5):
                        N[i] += t['N'][i]
        W = np.array([m['N0'] for m in M], float)
        wmean = lambda k: float(np.average([m[k] for m in M], weights=W))
        res['pooled'][corpus] = dict(
            steps=N[0], proofs=len(M),
            # bits per proof, proofs weighted by their size as written (ratios of summed sizes are
            # dominated by the few proofs whose cut-free form is exponentially large)
            kappa=wmean('kappa'), w=wmean('w'), l=wmean('l'), sigma=wmean('sigma'), chi=wmean('chi'), rho=wmean('rho'),
            kappa_mean=float(np.mean([m['kappa'] for m in M])), chi_mean=float(np.mean([m['chi'] for m in M])),
            rho_mean=float(np.mean([m['rho'] for m in M])),
            chi_ge1=float(np.mean([m['chi'] >= 1 for m in M])), chi_ge10=float(np.mean([m['chi'] >= 10 for m in M])),
            kappa_neg=float(np.mean([m['kappa'] < 0 for m in M])), kappa_pos=float(np.mean([m['kappa'] > 0 for m in M])),
            w_sumratio=lg(N[0], N[1]), l_sumratio=lg(N[1], N[2]), rho_sumratio=lg(N[0], N[4]),
            cuts_per_100=100 * tot['cuts'] / tot['dag'], dead_per_100=100 * tot['k0'] / tot['dag'],
            linear_per_100=100 * tot['k1'] / tot['dag'], shared_per_100=100 * tot['kw'] / tot['dag'],
            profitable_per_100=100 * tot['profitable'] / tot['dag'],
            share=dict(dead=tot['k0'] / max(1, tot['cuts']), linear=tot['k1'] / max(1, tot['cuts']),
                       shared=tot['kw'] / max(1, tot['cuts'])),
            beta_share=tot['beta'] / max(1, tot['cuts']),
            profitable_share_of_shared=tot['profitable'] / max(1, tot['kw']))
        # distribution of exact use counts, and of the size of the proof being cut
        ks = collections.Counter()
        sv_by = collections.defaultdict(list)
        for proj, recs in projs.items():
            for t in recs.values():
                for c in t['cuts']:
                    kind, k, sv = c[0], uses(c), c[2]
                    ks[min(k, 10)] += 1
                    sv_by['0' if k == 0 else '1' if k == 1 else 'ω'].append(sv)
        res['cut_k'][corpus] = dict(k_hist={str(k): v for k, v in sorted(ks.items())},
                                    sv_median={c: float(np.median(v)) for c, v in sv_by.items() if v})
        # by size
        bins = [10, 30, 100, 300, 1000, 10 ** 12]
        res['by_size'][corpus] = []
        for lo, hi in zip(bins, bins[1:]):
            mm = [m for m in M if lo <= m['N0'] < hi]
            if mm:
                res['by_size'][corpus].append(dict(lo=lo, hi=hi, proofs=len(mm),
                    kappa_median=float(np.nanmedian([m['kappa'] for m in mm])),
                    kappa_mean=float(np.mean([m['kappa'] for m in mm])), chi_mean=float(np.mean([m['chi'] for m in mm])),
                    rho_mean=float(np.mean([m['rho'] for m in mm])), chi_ge1=float(np.mean([m['chi'] >= 1 for m in mm])),
                    sigma_mean=float(np.nanmean([m['sigma'] for m in mm])),
                    l_mean=float(np.nanmean([m['l'] for m in mm])),
                    with_profitable=float(np.mean([m['profitable'] > 0 for m in mm]))))
        # project level
        rates = collections.defaultdict(list)
        per_proj = {}
        for proj, recs in projs.items():
            pm = [m for p, m in P if p == proj]
            if len(pm) < 20:
                continue
            pj = project_measures(recs)
            n0 = sum(m['dag'] for m in pm)
            pj.update(proofs=len(pm), kappa_median=float(np.nanmedian([m['kappa'] for m in pm])),
                      kappa_mean=float(np.nanmean([m['kappa'] for m in pm])), chi_mean=float(np.nanmean([m['chi'] for m in pm])),
                      rho_mean=float(np.nanmean([m['rho'] for m in pm])),
                      kappa_pooled=float(np.average([m['kappa'] for m in pm], weights=[m['N0'] for m in pm])),
                      chi_pooled=float(np.average([m['chi'] for m in pm], weights=[m['N0'] for m in pm])),
                      rho_pooled=float(np.average([m['rho'] for m in pm], weights=[m['N0'] for m in pm])),
                      chi_ge1=float(np.mean([m['chi'] >= 1 for m in pm])),
                      with_cut=float(np.mean([m['cuts'] > 0 for m in pm])),
                      sigma_mean=float(np.nanmean([m['sigma'] for m in pm])), l_mean=float(np.nanmean([m['l'] for m in pm])),
                      shared_per_100=100 * sum(m['kw'] for m in pm) / n0, linear_per_100=100 * sum(m['k1'] for m in pm) / n0,
                      profitable_per_100=100 * sum(m['profitable'] for m in pm) / n0)
            per_proj[proj] = pj
            for k in ('kappa_mean', 'chi_mean', 'rho_mean', 'kappa_pooled', 'chi_pooled', 'rho_pooled', 'with_cut', 'chi_ge1', 'sigma_mean', 'l_mean', 'shared_per_100', 'linear_per_100', 'profitable_per_100',
                      'kappa_in_proof', 'kappa_lemma', 'kappa_total', 'lemma_sigma'):
                rates[k].append(pj[k])
            rates['lemma_shared_frac'].append(pj['lemma_shared'] / pj['theorems'])
            rates['lemma_linear_frac'].append(pj['lemma_linear'] / pj['theorems'])
        res['project'][corpus] = per_proj
        res['project_median'][corpus] = {k: float(np.nanmedian(v)) for k, v in rates.items()} | {'projects': len(per_proj)}
        proj_rates[corpus] = rates
    for c in proj_rates:
        for other in ('mathlib', 'human'):
            if c != other and other in proj_rates and c != 'mathlib' and len(proj_rates[c]['kappa_mean']) >= 3:
                res['auc'][f'{c}_vs_{other}'] = {k: float(auc([x for x in proj_rates[c][k] if x == x],
                                                              [x for x in proj_rates[other][k] if x == x]))
                                                 for k in proj_rates[c]}
                res.setdefault('p', {})[f'{c}_vs_{other}'] = {
                    k: float(stats.mannwhitneyu([x for x in proj_rates[c][k] if x == x],
                                                [x for x in proj_rates[other][k] if x == x]).pvalue)
                    for k in proj_rates[c]}
    json.dump(res, open(RES, 'w'), indent=1)
    names = dict(mathlib='mathlib (held out)', openai='OpenAI math', human='Human research', flt='FLT (Claude)',
                 spherepacking='Sphere packing (Gauss)', erdos90='Erdős 90 (GPT-5.6)', putnam2025='Putnam 2025 (AxiomProver)',
                 imo2025='IMO 2025 (Aristotle)')
    cols = [dict(key=c, name=names.get(c, c)) for c in names if c in res['pooled']]
    pmed = {c: v for c, v in res['project_median'].items()}
    json.dump(dict(columns=cols, per_proof={c: dict(with_cut=v['with_cut']) for c, v in res['per_proof'].items()},
                   pooled=res['pooled'], project_median=pmed, auc=res['auc'], p=res.get('p', {}), cut_k=res['cut_k']),
              open(os.environ.get('CUTS_REPORT', os.path.join(CUT, 'report_cuts.json')), 'w'), indent=1, default=float)
    import pandas as pd
    for stat in ('mean', 'pos'):
        print(stat, pd.DataFrame({c: {k: v.get(stat) for k, v in d.items() if isinstance(v, dict) and 'n' in v} for c, d in res['per_proof'].items()}).round(3), sep='\n')
    print('given a cut (median)', pd.DataFrame({c: {k: v.get('median') for k, v in d['given_cut'].items()} for c, d in res['per_proof'].items()}).round(3), sep='\n')
    print(pd.DataFrame({c: {k: v for k, v in d.items() if not isinstance(v, dict)} for c, d in res['pooled'].items()}).round(3))
    print(pd.DataFrame(res['project_median']).round(3))
    print(pd.DataFrame(res['auc']).round(2))
    print(json.dumps(res['cut_k'], indent=0))


if __name__ == '__main__':
    main()
