"""Project-level energy statistics. Writes data/out/*.csv and data/out/summary.json."""
import json
import os
import pickle
import re

import numpy as np
import pandas as pd
from scipy import stats

CORPORA = ['mathlib', 'openai', 'tenproofs', 'carleson', 'flt', 'pfr', 'sphere', 'strongpnt']
HUMAN = {'carleson', 'flt', 'pfr', 'sphere'}
UPSTREAM = {'Mathlib', 'ToMathlib', 'ForMathlib'}
MIN_THM = 20
B = 4000
rng = np.random.default_rng(20261009)
os.makedirs('data/out', exist_ok=True)


def group_of(corpus, project):
    if corpus == 'mathlib':
        return 'mathlib'
    if corpus == 'openai':
        return 'openai'
    if corpus == 'tenproofs':
        return 'openai-ten'
    if corpus == 'strongpnt':
        return 'strongpnt'
    return 'human-upstream' if project.split('/')[-1] in UPSTREAM else 'human'


def area_of(corpus, project):
    parts = project.split('/')
    return parts[1] if corpus in ('openai', 'mathlib') and len(parts) > 1 else None


# ---------- load ----------
T = pd.read_pickle('data/text_energy.pkl')
P = pd.read_pickle('data/premise_energy.pkl')
proj = pd.concat([pd.DataFrame(pickle.load(open(f'data/decls_{c}.pkl', 'rb'))['projects']) for c in CORPORA])
proj['cert_mass'] = proj.cert_chars / proj.chars.clip(lower=1)

# premise rows are in the same order as the decl pickles; text rows are grouped by fold for mathlib,
# so join on (corpus, project, full, kind) occurrence index.
for df in (T, P):
    df['occ'] = df.groupby(['corpus', 'project', 'full', 'kind']).cumcount()
D = T.merge(P[['corpus', 'project', 'full', 'kind', 'occ', 'E_prem', 'n_ref', 'n_lib', 'n_bespoke',
               'E_libsurp', 'n_unresolved']], on=['corpus', 'project', 'full', 'kind', 'occ'], how='left')
D['last'] = D.full.fillna('').str.split('.').str[-1]
D['numbered'] = D['last'].str.contains(r'\d', regex=True)
D['is_thm'] = D.kind.isin(['theorem', 'lemma'])


def agg(g):
    s = lambda c: g[c].sum()
    thm = g[g.is_thm]
    return pd.Series({
        'n_sampled': len(g),
        'e_tok': s('E_struct') / s('n_tok'),
        'e_name': s('E_n') / max(1, s('n_n')),
        'e_op': s('E_o') / max(1, s('n_o')),
        'e_num': s('E_k') / max(1, s('n_k')),
        'e_proof': s('E_proof') / max(1, s('n_proof')),
        'share_name': s('n_n') / s('n_tok'),
        'share_op': s('n_o') / s('n_tok'),
        'share_num': s('n_k') / s('n_tok'),
        'c_name': s('E_n') / s('n_tok'),
        'c_op': s('E_o') / s('n_tok'),
        'c_num': s('E_k') / s('n_tok'),
        'c_end': s('E_e') / s('n_tok'),
        'c_unk': s('E_unk') / s('n_tok'),
        'oov': s('n_unk') / s('n_tok'),
        'lit_share': s('E_lit') / max(1e-9, s('E_total')),
        'tok_per_thm': thm.n_tok.median() if len(thm) else np.nan,
        'E_thm': thm.E_total.median() if len(thm) else np.nan,
        'E_thm_struct': thm.E_struct.median() if len(thm) else np.nan,
        'E_decl_mean': g.E_total.mean(),
        'e_prem': s('E_prem') / max(1, s('n_ref')),
        'bespoke_share': s('n_bespoke') / max(1, s('n_ref')),
        'lib_surp': s('E_libsurp') / max(1, s('n_lib')),
        'refs_per_tok': s('n_ref') / s('n_tok'),
        'numbered': g.numbered[g.full.fillna('') != ''].mean(),
    })


Pj = D.groupby(['corpus', 'project']).apply(agg).reset_index()
Pj = Pj.merge(proj[['corpus', 'project', 'n_decls', 'n_thm', 'n_def', 'chars', 'cert_mass']],
              on=['corpus', 'project'])
Pj['group'] = [group_of(c, p) for c, p in zip(Pj.corpus, Pj.project)]
Pj['area'] = [area_of(c, p) for c, p in zip(Pj.corpus, Pj.project)]
Pj['regime'] = np.where((Pj.group == 'openai') & (Pj.cert_mass >= 0.3), 'certificate', 'core')
Pj['E_project'] = Pj.E_decl_mean * Pj.n_decls  # extensive: bits to compose the whole project
Pj = Pj[Pj.n_thm >= MIN_THM].copy()

# area-matched excess over mathlib (held-out mathlib projects in the same top-level area)
ml = Pj[Pj.group == 'mathlib']
for col in ['e_tok', 'e_prem', 'e_name', 'e_op']:
    area_med = ml.groupby('area')[col].median()
    Pj[f'd_{col}'] = Pj[col] - Pj.area.map(area_med).fillna(ml[col].median())
Pj.to_csv('data/out/projects.csv', index=False)

METRICS = {
    'e_tok': ('Specific energy', 'bits per token under mathlib\'s 5-gram model (long numerals excluded)'),
    'd_e_tok': ('Area-matched excess energy', 'bits per token above the median held-out mathlib project in the same area'),
    'e_name': ('Name energy', 'bits per identifier piece'),
    'e_op': ('Syntax energy', 'bits per operator, keyword-symbol or bracket'),
    'e_proof': ('Proof energy', 'bits per token in proofs only'),
    'oov': ('Coined words', 'share of tokens outside mathlib\'s vocabulary'),
    'E_thm_struct': ('Energy per theorem', 'median bits to write one theorem, statement and proof (numeral digits excluded)'),
    'tok_per_thm': ('Theorem length', 'median tokens per theorem'),
    'lit_share': ('Literal share', 'share of all bits spent spelling numerals of 4+ digits'),
    'e_prem': ('Premise energy', 'bits per resolved constant reference under mathlib\'s reference distribution'),
    'bespoke_share': ('Bespoke references', 'share of references to constants not in mathlib'),
    'lib_surp': ('Library surprisal', 'bits per mathlib constant referenced (rarely used lemmas cost more)'),
}
GROUPS = ['mathlib', 'openai', 'human', 'human-upstream', 'openai-ten', 'strongpnt']


def boot_median(x):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if len(x) < 2:
        return (np.median(x) if len(x) else np.nan, np.nan, np.nan)
    bs = np.median(rng.choice(x, (B, len(x))), axis=1)
    return np.median(x), np.quantile(bs, 0.025), np.quantile(bs, 0.975)


rows = []
for m, (label, defn) in METRICS.items():
    for g in GROUPS + ['openai-core', 'openai-certificate']:
        if g.startswith('openai-') and g not in ('openai-ten',):
            sub = Pj[(Pj.group == 'openai') & (Pj.regime == g.split('-')[1])]
        else:
            sub = Pj[Pj.group == g]
        med, lo, hi = boot_median(sub[m])
        rows.append(dict(metric=m, label=label, definition=defn, group=g, n=len(sub), median=med, lo=lo, hi=hi))
G = pd.DataFrame(rows)
G.to_csv('data/out/group_metrics.csv', index=False)


def bh(p):
    p = np.asarray(p)
    o = np.argsort(p)
    q = p[o] * len(p) / (np.arange(len(p)) + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty_like(q)
    out[o] = np.minimum(q, 1)
    return out


tests = []
for ref in ['mathlib', 'human']:
    for m in METRICS:
        a = Pj.loc[Pj.group == 'openai', m].dropna().to_numpy()
        b = Pj.loc[Pj.group == ref, m].dropna().to_numpy()
        u, p = stats.mannwhitneyu(a, b, alternative='two-sided')
        diffs = np.median(rng.choice(a, (B, len(a))), 1) - np.median(rng.choice(b, (B, len(b))), 1)
        tests.append(dict(vs=ref, metric=m, label=METRICS[m][0], n_openai=len(a), n_ref=len(b),
                          diff=np.median(a) - np.median(b), lo=np.quantile(diffs, .025),
                          hi=np.quantile(diffs, .975), auc=u / (len(a) * len(b)), p=p))
Tt = pd.DataFrame(tests)
Tt['q'] = bh(Tt.p)
Tt.to_csv('data/out/tests.csv', index=False)

# Does energy track the other style proxies across OpenAI projects?
oa = Pj[Pj.group == 'openai']
cols = ['e_tok', 'e_prem', 'oov', 'bespoke_share', 'lib_surp', 'cert_mass', 'numbered', 'lit_share', 'tok_per_thm']
corr = oa[cols].rank().corr()
corr.to_csv('data/out/corr_openai.csv')

# Size control: regress specific energy on group with log size and area fixed effects
import statsmodels.formula.api as smf  # noqa: E402
reg = Pj[Pj.group.isin(['mathlib', 'openai', 'human'])].copy()
reg['logtok'] = np.log10(reg.n_decls * reg.tok_per_thm.fillna(reg.tok_per_thm.median()))
reg['area_f'] = reg.area.fillna('none')
reg['cert'] = (reg.regime == 'certificate').astype(int)
fits = {}
for y in ['e_tok', 'e_prem']:
    f = smf.ols(f'{y} ~ C(group, Treatment("mathlib")) + logtok + cert', data=reg).fit(cov_type='HC3')
    fits[y] = {k: [float(f.params[k]), float(f.bse[k]), float(f.pvalues[k])] for k in f.params.index}

# Pooled values (all sampled declarations, token-weighted)
pool = D.assign(group=[group_of(c, p) for c, p in zip(D.corpus, D.project)])
pooled = pool.groupby('group').apply(lambda g: pd.Series({
    'decls': len(g), 'e_tok': g.E_struct.sum() / g.n_tok.sum(), 'lit_share': g.E_lit.sum() / g.E_total.sum(),
    'e_prem': g.E_prem.sum() / g.n_ref.sum(), 'bespoke_share': g.n_bespoke.sum() / g.n_ref.sum()}))
pooled.to_csv('data/out/pooled.csv')

summary = dict(n_projects=Pj.groupby('group').size().to_dict(), regression=fits,
               pooled=pooled.reset_index().to_dict('records'))
json.dump(summary, open('data/out/summary.json', 'w'), indent=1, default=float)
pd.set_option('display.width', 200)
print(Pj.groupby('group').size())
print(G[G.group.isin(['mathlib', 'openai', 'openai-core', 'openai-certificate', 'human', 'human-upstream'])]
      .pivot(index='label', columns='group', values='median').round(3))
print(Tt.round(4))
print(json.dumps(fits, indent=1))
print(corr.round(2))

# Per-area comparison (OpenAI vs held-out mathlib, same top-level area)
ar = Pj[Pj.group.isin(['mathlib', 'openai']) & Pj.area.notna()]
areas = ar.groupby(['area', 'group']).e_tok.agg(['median', 'size']).unstack('group')
areas.columns = [f'{a}_{b}' for a, b in areas.columns]
areas = areas.dropna()
areas = areas[(areas.size_openai >= 3) & (areas.size_mathlib >= 3)].sort_values('median_openai')
areas.to_csv('data/out/areas.csv')
print(areas.round(2))

# Example declarations: OpenAI core theorems of typical length at low / median / high specific energy
import lexer  # noqa: E402
dd = pickle.load(open('data/decls_openai.pkl', 'rb'))['decls']
key = {(d['project'], d['full'], d['kind']): d for d in dd}
ex = D[(D.corpus == 'openai') & D.is_thm & ~D.cert & D.n_tok.between(40, 90)].copy()
ex['e'] = ex.E_struct / ex.n_tok
qs = ex.e.quantile([0.02, 0.5, 0.98]).to_numpy()
picks = []
for label, qv in zip(['low', 'median', 'high'], qs):
    r = ex.iloc[(ex.e - qv).abs().argsort()[:1]].iloc[0]
    d = key.get((r.project, r.full, r.kind))
    picks.append(dict(label=label, project=r.project, name=r.full, bits_per_tok=r.e, bits=r.E_struct,
                      tokens=r.n_tok, text=d['text'] if d else ''))
json.dump(picks, open('data/out/examples.json', 'w'), indent=1, default=float)
