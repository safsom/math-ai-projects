"""Group comparisons, headline-cone summaries and metric correlations.

Units of analysis
  project : a directory-level unit (OpenAI: OAI/<Area>/<Topic>; mathlib: Mathlib/<A>/<B>;
            human research projects: first-level subdirectory; StrongPNT / ten-proofs: file).
            Only projects with >= 20 theorems are compared.
  cone    : every in-corpus declaration reachable from a headline theorem.

Statistics
  per group: median over projects with a 95% percentile bootstrap CI (projects resampled,
  4000 reps); pooled value over all declarations of the group; OpenAI-vs-human and
  OpenAI-vs-mathlib Mann-Whitney U tests on project values with Benjamini-Hochberg q-values.

Usage: python3 analysis.py EXTDIR RESULTSDIR
"""
import json
import pickle
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).parent))
from agg import METRICS, summarize  # noqa: E402

EXT, RES = Path(sys.argv[1]), Path(sys.argv[2])
RES.mkdir(exist_ok=True)
NM = pickle.load(open(EXT / "names.pkl", "rb"))
names = NM["names"]
cols = ["corpus", "group", "project", "name_id", "short", "kind", "is_thm", "is_concept", "n_body_tok", "n_sig_tok",
        "n_users", "n_thm_stmt_users", "t_enum", "t_auto", "t_struct", "n_num", "cert_25", "casebash",
        "grounding", "numbered", "uninformative", "vocab_share", "n_name_tok", "ns_inherit", "refs_own",
        "refs_lib", "refs_other", "sig_refs_own", "sig_refs_lib", "body_dup", "body_dup_eligible", "skel_dup",
        "skel_dup_eligible", "reinvents_mathlib", "sig_dup_cross_project", "sig_eligible", "prop_users",
        "prop_hits", "n_unresolved_q", "n_dot_resolved", "private", "sig_eligible"]
df = pd.read_parquet(EXT / "metrics.parquet", columns=list(dict.fromkeys(cols)))
print("loaded", len(df), flush=True)
GROUPS = ["openai_math", "openai_ten", "human_research", "other_ai", "mathlib"]
KEYS = list(METRICS)

# ------------------------------------------------------------- projects -----
zl = pd.read_csv(RES / "compression_by_project.csv")
zmap = {(r.corpus, r.project): r.zlib_ratio for r in zl.itertuples()}
prows = []
for (corpus, project), c in df.groupby(["corpus", "project"], observed=True, sort=False):
    s = summarize(c)
    s.update(corpus=corpus, project=project, group=c.group.iat[0], zlib_ratio=zmap.get((corpus, project), np.nan))
    prows.append(s)
P = pd.DataFrame(prows)
P.to_csv(RES / "project_metrics.csv", index=False)
Pq = P[P.n_thm >= 20].copy()
print("projects", len(P), "eligible", len(Pq), Pq.group.value_counts().to_dict(), flush=True)

# ------------------------------------------------------------- groups -------
rng = np.random.default_rng(20261009)


def boot_median(x, reps=4000):
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    if len(x) < 2:
        return (np.nan, np.nan)
    idx = rng.integers(0, len(x), size=(reps, len(x)))
    med = np.median(x[idx], axis=1)
    return tuple(np.percentile(med, [2.5, 97.5]))


pooled = {}
for g in GROUPS:
    pooled[g] = summarize(df[df.group.values == g])
    pooled[g]["zlib_ratio"] = np.nan
grows = []
for k in KEYS:
    for g in GROUPS:
        v = Pq.loc[Pq.group == g, k].astype(float)
        lo, hi = boot_median(v)
        grows.append(dict(metric=k, group=g, n_projects=int(v.notna().sum()), median=float(np.nanmedian(v)) if v.notna().any() else np.nan,
                          ci_lo=lo, ci_hi=hi, pooled=pooled[g].get(k, np.nan)))
G = pd.DataFrame(grows)


def bh(p):
    p = np.asarray(p, dtype=float)
    ok = ~np.isnan(p)
    q = np.full_like(p, np.nan)
    pv = p[ok]
    o = np.argsort(pv)
    r = pv[o] * len(pv) / (np.arange(len(pv)) + 1)
    r = np.minimum.accumulate(r[::-1])[::-1]
    qq = np.empty_like(pv)
    qq[o] = np.minimum(r, 1)
    q[ok] = qq
    return q


tests = []
for other in ("human_research", "mathlib"):
    for k in KEYS:
        a = Pq.loc[Pq.group == "openai_math", k].dropna().astype(float).values
        b = Pq.loc[Pq.group == other, k].dropna().astype(float).values
        if len(a) >= 3 and len(b) >= 3:
            u = stats.mannwhitneyu(a, b, alternative="two-sided")
            ia = rng.integers(0, len(a), size=(4000, len(a)))
            ib = rng.integers(0, len(b), size=(4000, len(b)))
            dd = np.median(a[ia], axis=1) - np.median(b[ib], axis=1)
            tests.append(dict(metric=k, vs=other, n_oai=len(a), n_other=len(b), diff=np.median(a) - np.median(b),
                              diff_lo=np.percentile(dd, 2.5), diff_hi=np.percentile(dd, 97.5),
                              auc=u.statistic / (len(a) * len(b)), p=u.pvalue))
T = pd.DataFrame(tests)
T["q"] = np.nan
for other in T.vs.unique():
    m = T.vs == other
    T.loc[m, "q"] = bh(T.loc[m, "p"].values)
G.to_csv(RES / "group_summary.csv", index=False)
T.to_csv(RES / "tests.csv", index=False)
print("groups done", flush=True)

# ------------------------------------------------------------- cones --------
E = np.load(EXT / "edges.npz")
src, dst = E["src"], E["dst"]
name2row = np.full(len(names), -1, dtype=np.int64)
ok = df["name_id"].values >= 0
name2row[df["name_id"].values[ok]] = np.nonzero(ok)[0]
# generated names -> declaring row (same rule as metrics.py)
row_of = {names[i]: r for i, r in zip(df["name_id"].values[ok], np.nonzero(ok)[0])}
for j in np.unique(dst[name2row[dst] < 0]):
    n = names[j]
    while "." in n:
        n = n.rsplit(".", 1)[0]
        r = row_of.get(n)
        if r is not None:
            name2row[j] = r
            break
drow = name2row[dst]
corp = df["corpus"].astype("category").cat.codes.values
m = (drow >= 0) & (drow != src)
m &= corp[np.where(drow >= 0, drow, 0)] == corp[src]
s_, d_ = src[m], drow[m]
o = np.argsort(s_, kind="stable")
s_, d_ = s_[o], d_[o]
indptr = np.searchsorted(s_, np.arange(len(df) + 1))
del src, dst, drow, E, s_


def yaml_decls(path):
    return re.findall(r'declaration:\s*"?([^"\n]+?)"?\s*$', open(path).read(), re.M)


heads = [("openai_math", n) for n in yaml_decls("/tmp/oai-math/lean/formalization.yaml")]
heads += [("openai_ten", n) for n in yaml_decls("/tmp/ten-proofs/formalization.yaml")]
heads += [("human_research", n) for n in ("classical_carleson", "metric_carleson", "sphere_eversion", "PFR_conjecture")]
heads += [("other_ai", "Strong_PNT")]
crow = []
for grp, n in heads:
    r = row_of.get(n)
    if r is None:
        cands = [k for k in row_of if k.endswith("." + n)]
        r = row_of[cands[0]] if len(cands) == 1 else None
    if r is None:
        crow.append(dict(group=grp, headline=n, found=False))
        continue
    seen = np.zeros(len(df), dtype=bool)
    seen[r] = True
    stack = [r]
    while stack:
        x = stack.pop()
        nb = d_[indptr[x]:indptr[x + 1]]
        nb = nb[~seen[nb]]
        seen[nb] = True
        stack.extend(nb.tolist())
    c = df[seen]
    sm = summarize(c, head_row=r)
    sm.update(group=grp, headline=n, found=True, corpus=df.corpus.iat[r], project=df.project.iat[r])
    crow.append(sm)
C = pd.DataFrame(crow)
C.to_csv(RES / "cones.csv", index=False)
print("cones", int(C.found.sum()), "of", len(C), flush=True)

# ------------------------------------------------------------- coherence ----
CORE = ["concepts_per_100_thm", "live_concept_share", "single_use_lemma_share", "cert_token_share",
        "casebash_token_share", "auto_per_1k", "struct_per_1k", "numbered_share", "uninformative_share",
        "grounding", "propagation", "skel_dup_share", "library_ref_share", "proof_to_statement"]
oc = C[(C.group == "openai_math") & C.found & (C.n_thm >= 20)]
rho = oc[CORE].astype(float).corr(method="spearman")
rho.to_csv(RES / "cone_spearman_openai.csv")
pp = Pq[Pq.group == "openai_math"][CORE].astype(float).corr(method="spearman")
pp.to_csv(RES / "project_spearman_openai.csv")

# ------------------------------------------------------------- examples -----
ex = {}
for k in ("cert_token_share", "casebash_token_share", "numbered_share", "grounding", "live_concept_share"):
    t = oc.sort_values(k, ascending=False)[["headline", "project", "n_decls", "tokens", k]]
    ex[k] = {"top": t.head(5).to_dict("records"), "bottom": t.tail(5).to_dict("records")}
# sample theorem names per group (for the naming section)
samp = {}
for g in GROUPS:
    t = df[(df.group.values == g) & df.is_thm.values & (df.name_id.values >= 0)]
    samp[g] = t.sample(12, random_state=1)["short"].tolist()
json.dump({"examples": ex, "name_samples": samp, "metric_defs": METRICS,
           "sizes": {g: {"decls": int((df.group == g).sum()), "theorems": int(((df.group == g) & df.is_thm).sum()),
                         "projects": int((P.group == g).sum()), "projects_ge20": int((Pq.group == g).sum())} for g in GROUPS},
           "diagnostics": {g: {"unresolved_q_per_decl": pooled[g]["unresolved_per_decl"],
                               "dot_resolved_per_decl": pooled[g]["dot_resolved_per_decl"]} for g in GROUPS}},
          open(RES / "extras.json", "w"), indent=1, default=float)
print("done", flush=True)
