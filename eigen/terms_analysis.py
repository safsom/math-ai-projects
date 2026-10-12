"""Studies on the proof-term pass (out_terms*, GESTURE_TERMS=1).

1. Intrinsic compression. For each proof, the cut-free form S (tree size) is bracketed:
     chi_author = log2(N3/N4)      what the author's own cuts, optimally kept, save
     chi_lb     = log2(S/G)         an explicit cut layout found greedily (new cuts allowed); max'd with chi_author
     chi_ub     = log2(S/D)         sharing every repeated subproof for free (the DAG)
   so chi_author <= chi* <= chi_ub with chi* the best layout. Realization = chi_author / chi_lb.
2. Rank ladder. Each cut's formula rank (implications to the left) by use class; created redexes
   (a substituted proof-function applied to a proof) can only come from a cut of rank >= 1.
   Checked: chi_ub <= log2(max multiplicity), kappa <= sum log2(uses) over cuts.
3. Invariance. The 9 OpenAI projects compiled both in one shared environment and module by module:
   the same theorem's cut layout can differ while its cut-free form does not.
Writes out_terms/terms_results.json.
"""
import collections, glob, json, math, os, sys
import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from analyze import user_name, strip_internal, GENERATED, project_and_group, HUMAN_REACH  # noqa: E402

OT = os.environ.get('OT', os.path.join(HERE, 'out_terms'))
OTI = os.environ.get('OTI', os.path.join(HERE, 'out_terms_iso'))
OTA = os.environ.get('OTA', os.path.join(HERE, 'out_terms_ai'))
OT2 = os.environ.get('OT2', os.path.join(HERE, 'out_terms_v2'))
OT3 = os.environ.get('OT3', os.path.join(HERE, 'out_terms_v3'))
OTA3 = os.environ.get('OTA3', os.path.join(HERE, 'out_terms_v3_ai'))
OTI2 = os.path.join(HERE, 'out_terms_v2_iso')
OTI3 = os.path.join(HERE, 'out_terms_v3_iso')
MIN = 10
lg = math.log2


def files():
    out = [(os.path.join(OT, 'mathlib.jsonl'), 'mathlib')]
    out += [(p, 'openai') for p in sorted(glob.glob(os.path.join(OT, 'OAI.*.jsonl')))]
    out += [(p, 'human') for p in sorted(glob.glob(os.path.join(OT, 'human.*.jsonl')))]
    out += [(os.path.join(OTA, c, c + '.jsonl'), c) for c in ('spherepacking', 'putnam2025', 'imo2025')]
    # later passes replace earlier ones where they exist: v2 unfolded ranks and proof-applied redexes,
    # v3 a Prop test that unfolds definitions and the count of hidden-proposition cuts
    def newest(p):
        for old, new in ((OT, OT3), (OTA, OTA3), (OT, OT2)):
            q = p.replace(old, new, 1)
            if p.startswith(old) and os.path.exists(q):
                return q
        # OpenAI projects recompiled module by module in a later pass: same terms for 99.8% of theorems (see invariance)
        b = os.path.basename(p)
        for d in (OTI3, OTI2):
            q = os.path.join(d, b)
            if b.startswith('OAI.') and os.path.exists(q) and os.path.getsize(q) > 0:
                return q
        return p
    out = [(newest(p), c) for p, c in out]
    return [(p, c) for p, c in out if os.path.exists(p) and not p.endswith(('.log.jsonl', '.trace.jsonl'))]


def measures(r):
    N0, N1, N2, N3, N4 = r['cN']
    S, D, G = r['tS'], r['tD'], r['tG']
    uses = [c[1] if c[1] or len(c) < 5 else min(c[4], 1) for c in r['cuts']]
    ca = lg(N3 / N4) if N4 else 0.0
    lb = max(lg(S / G), ca)
    ub = lg(S / D)
    rk = r.get('rk', [0] * 12)
    rku = r.get('rku')
    maxr = lambda h: max((i for i in range(4) if sum(h[3 * i:3 * i + 3])), default=-1)
    return dict(N0=N0, N3=N3, S=S, D=D, kappa=lg(N3 / N0), chi_author=ca, chi_lb=lb, chi_ub=max(ub, lb),
                ub_raw=ub, missed=lb - ca, resid=r['tResid'], occmax=lg(max(r['tOccMax'], 1)),
                prod_bound=sum(lg(max(u, 1)) for u in uses), named=r['tNamed'], shared=r['tShared'],
                rk=rk, agree=abs(S - N3) <= 0.01 * N3 + 1,
                # second pass only: rank with definitions unfolded, and created redexes applied to a proof
                hidden=r.get('tHidden'), ver=3 if 'tHidden' in r else 2 if rku is not None else 1,
                rku=rku, residP=r.get('tResidP'), maxrank_u=maxr(rku) if rku else None,
                maxrank_u_shared=max((i for i in range(4) if rku[3 * i + 2]), default=-1) if rku else None,
                # first-order estimate of kappa: each cut copies its proof (uses - 1) more times
                kappa_est=sum(lg(1 + max(u - 1, 0) * c[2] / N0) for u, c in zip(uses, r['cuts'])))


def load():
    data = collections.defaultdict(list)
    for path, corpus in files():
        base = os.path.basename(path)[:-6]
        reach = set(HUMAN_REACH.get(base, [])) if corpus == 'human' else None
        for line in open(path):
            r = json.loads(line)
            if 'tS' not in r or r.get('tt') or r['sorry'] or r.get('ctr') or r['tr']:
                continue
            if corpus == 'openai' and r['p'] != base:
                continue
            if reach is not None and r['m'] not in reach:
                continue
            u = user_name(r['n'])
            if strip_internal(u) != u or GENERATED.search(u) or r['cN'][0] < MIN:
                continue
            m = measures(r)
            m['proj'] = project_and_group(corpus, r['m'])[0]
            m['n'] = r['n']
            data[corpus].append(m)
    return data


def ladder(M):
    """Compression by the highest unfolded rank among a proof's shared cuts (-1: no shared cut)."""
    out = {}
    for k in (-1, 0, 1, 2, 3):
        S = [m for m in M if m['maxrank_u_shared'] == k]
        if len(S) >= 5:
            out[str(k)] = dict(n=len(S), chi_author=float(np.mean([m['chi_author'] for m in S])),
                               chi_lb=float(np.mean([m['chi_lb'] for m in S])), chi_ub=float(np.mean([m['chi_ub'] for m in S])),
                               chi_ub_p99=float(np.percentile([m['chi_ub'] for m in S], 99)),
                               residP=float(np.mean([bool(m['residP']) for m in S])))
    return out


def summarize(M):
    a = lambda k: np.array([m[k] for m in M], float)
    ca, lb, ub = a('chi_author'), a('chi_lb'), a('chi_ub')
    rk = np.array([m['rk'] for m in M]).sum(0).reshape(4, 3)  # rank x (0, 1, w)
    shared = rk[:, 2].sum()
    return dict(
        proofs=len(M), agree=float(a('agree').mean()),
        chi_author=float(ca.mean()), chi_lb=float(lb.mean()), chi_ub=float(ub.mean()),
        realized=float(ca.sum() / lb.sum()) if lb.sum() else None,
        missed=float((lb - ca).mean()), missed_ge1=float(((lb - ca) >= 1).mean()),
        lb_ge1=float((lb >= 1).mean()), ub_ge1=float((ub >= 1).mean()),
        resid_share=float((a('resid') > 0).mean()), resid_per_proof=float(a('resid').mean()),
        rank_hist=rk.tolist(), shared_rank_ge1=float(rk[1:, 2].sum() / shared) if shared else None,
        cuts_rank_ge1=float(rk[1:].sum() / rk.sum()) if rk.sum() else None,
        occmax_median=float(np.median(a('occmax'))), occmax_p99=float(np.percentile(a('occmax'), 99)),
        # rank ladder (second-pass records): a created proof redex needs a cut of rank >= 1
        ladder_n=sum(1 for m in M if m['residP']),
        ladder_holds=float(np.mean([m['maxrank_u'] >= 1 for m in M if m['residP']])) if any(m['residP'] for m in M) else None,
        rank_hist_u=np.array([m['rku'] for m in M if m['rku']]).sum(0).reshape(4, 3).tolist() if any(m['rku'] for m in M) else None,
        ladder_u=ladder(M),
        v2_share=float(np.mean([m['rku'] is not None for m in M])),
        v3_share=float(np.mean([m['ver'] == 3 for m in M])),
        hidden_share=float(np.mean([m['hidden'] > 0 for m in M if m['ver'] == 3])) if any(m['ver'] == 3 for m in M) else None,
        hidden_per_cut=float(sum(m['hidden'] for m in M if m['ver'] == 3) / max(1, sum(sum(m['rku']) for m in M if m['ver'] == 3)))
        if any(m['ver'] == 3 for m in M) else None,
        residP_share=float(np.mean([bool(m['residP']) for m in M if m['rku'] is not None])) if any(m['rku'] is not None for m in M) else None,
        cuts_rank_ge1_u=(lambda h: float(h[1:].sum() / h.sum()) if h.sum() else None)(np.array([m['rku'] for m in M if m['rku']]).sum(0).reshape(4, 3))
        if any(m['rku'] for m in M) else None,
        shared_rank_ge1_u=(lambda h: float(h[1:, 2].sum() / h[:, 2].sum()) if h[:, 2].sum() else None)(np.array([m['rku'] for m in M if m['rku']]).sum(0).reshape(4, 3))
        if any(m['rku'] for m in M) else None,
        kappa_est_spearman=float(stats.spearmanr([m['kappa'] for m in M if m['kappa'] > 0], [m['kappa_est'] for m in M if m['kappa'] > 0])[0])
        if sum(m['kappa'] > 0 for m in M) > 10 else None,
        kappa_le_est=float(np.mean([m['kappa'] <= m['kappa_est'] + 1e-9 for m in M if m['kappa'] > 0])) if any(m['kappa'] > 0 for m in M) else None,
        # the inequalities
        ub_le_occmax=float((a('ub_raw') <= a('occmax') + 1e-9).mean()),
        kappa_le_prod=float((a('kappa') <= a('prod_bound') + 1e-9).mean()),
        author_le_ub=float((ca <= a('ub_raw') + 1e-9).mean()),
        tightness_median=float(np.median([m['kappa'] / m['prod_bound'] for m in M if m['prod_bound'] > 0 and m['kappa'] > 0]))
        if any(m['prod_bound'] > 0 and m['kappa'] > 0 for m in M) else None)


def project_table(M, keys=('chi_author', 'chi_lb', 'chi_ub', 'missed')):
    P = collections.defaultdict(list)
    for m in M:
        P[m['proj']].append(m)
    out = {}
    for p, ms in P.items():
        if len(ms) >= 20:
            ca = sum(x['chi_author'] for x in ms)
            lb = sum(x['chi_lb'] for x in ms)
            out[p] = {k: float(np.mean([x[k] for x in ms])) for k in keys}
            out[p]['realized'] = ca / lb if lb else np.nan
            out[p]['resid'] = float(np.mean([x['resid'] > 0 for x in ms]))
    return out


def auc(a, b):
    a, b = [x for x in a if x == x], [x for x in b if x == x]
    if len(a) < 3 or len(b) < 3:
        return None
    u, p = stats.mannwhitneyu(a, b, alternative='two-sided')
    return dict(auc=float(u / (len(a) * len(b))), p=float(p), n=(len(a), len(b)))


def invariance():
    """Same theorems, shared vs module-by-module compilation."""
    iso = {}
    for p in glob.glob(os.path.join(OTI, 'OAI.*.jsonl')):
        if p.endswith(('.log.jsonl', '.trace.jsonl')):
            continue
        for line in open(p):
            r = json.loads(line)
            if 'tS' in r and not r.get('tt') and not r['sorry']:
                iso[r['n']] = r
    if not iso:
        return None
    pairs = []
    for p in glob.glob(os.path.join(OT, 'OAI.*.jsonl')):
        if p.endswith(('.log.jsonl', '.trace.jsonl')):
            continue
        for line in open(p):
            r = json.loads(line)
            u = user_name(r['n'])
            if strip_internal(u) != u or GENERATED.search(u):   # auxiliary proofs are numbered differently in the two modes
                continue
            if r['n'] in iso and 'tS' in r and not r.get('tt') and not r['sorry'] and r['cN'][0] >= MIN:
                a, b = measures(r), measures(iso[r['n']])
                a['ncuts'], b['ncuts'] = len(r['cuts']), len(iso[r['n']]['cuts'])
                pairs.append((a, b))
    if not pairs:
        return None
    same = lambda k: float(np.mean([abs(a[k] - b[k]) < 1e-12 for a, b in pairs]))
    layout_changed = [(a, b) for a, b in pairs if a['N0'] != b['N0']]
    return dict(n=len(pairs), same_N0=same('N0'), same_S=same('S'), same_D=same('D'),
                same_kappa=same('kappa'), same_chi_lb=same('chi_lb'), same_chi_ub=same('chi_ub'),
                layout_changed=len(layout_changed),
                cutfree_same_given_layout_changed=float(np.mean([a['S'] == b['S'] and a['D'] == b['D'] for a, b in layout_changed]))
                if layout_changed else None,
                # a change outside the cuts moves written and cut-free size by the same amount
                change_outside_cuts=float(np.mean([a['N0'] - b['N0'] == a['S'] - b['S'] and a['ncuts'] == b['ncuts'] for a, b in layout_changed]))
                if layout_changed else None,
                changed_median_rel=float(np.median([abs(a['N0'] / b['N0'] - 1) for a, b in layout_changed])) if layout_changed else None,
                mad_chi_lb=float(np.mean([abs(a['chi_lb'] - b['chi_lb']) for a, b in pairs])),
                mad_kappa=float(np.mean([abs(a['kappa'] - b['kappa']) for a, b in pairs])))


def main():
    data = load()
    res = dict(corpora={c: summarize(M) for c, M in data.items()})
    PT = {c: project_table(M) for c, M in data.items()}
    res['project_median'] = {c: {k: float(np.nanmedian([v[k] for v in T.values()])) for k in ('chi_author', 'chi_lb', 'chi_ub', 'missed', 'realized', 'resid')}
                             for c, T in PT.items() if T}
    res['project_n'] = {c: len(T) for c, T in PT.items()}
    res['tests'] = {}
    for c in PT:
        for ref in ('mathlib', 'human'):
            if c != ref and ref in PT and PT[c]:
                res['tests'][f'{c}_vs_{ref}'] = {k: auc([v[k] for v in PT[c].values()], [v[k] for v in PT[ref].values()])
                                                 for k in ('chi_author', 'chi_lb', 'chi_ub', 'missed', 'realized', 'resid')}
    # realized share within proof-size bins, so that longer AI proofs are compared with mathlib proofs of the same size
    bins = [10, 30, 100, 300, 1000, None]
    res['realized_by_size'] = {'bins': bins[:-1], 'corpora': {}}
    for c, M in data.items():
        row = []
        for lo, hi in zip(bins, bins[1:]):
            S = [m for m in M if m['S'] >= lo and (hi is None or m['S'] < hi)]
            lb = sum(m['chi_lb'] for m in S)
            row.append(dict(n=len(S), realized=sum(m['chi_author'] for m in S) / lb if lb > 0 and len(S) >= 30 else None,
                            chi_ub=float(np.mean([m['chi_ub'] for m in S])) if len(S) >= 30 else None,
                            chi_lb=float(np.mean([m['chi_lb'] for m in S])) if len(S) >= 30 else None))
        res['realized_by_size']['corpora'][c] = row
    res['invariance'] = invariance()
    json.dump(res, open(os.path.join(OT, 'terms_results.json'), 'w'), indent=1)
    import pandas as pd
    print(pd.DataFrame(res['corpora']).T.drop(columns=['rank_hist', 'rank_hist_u']).round(3).T.to_string())
    print(json.dumps(res['project_median'], indent=0))
    print(json.dumps(res['invariance'], indent=0))


if __name__ == '__main__':
    main()
