"""Measurement checks on headline-result cones (OpenAI math).

1. Overlap: how much cones share declarations (non-independence).
2. Split-half reliability: each cone's declarations split at random into two
   halves (20 repetitions); metric computed on each half; Spearman correlation
   across cones, Spearman-Brown corrected.
3. Disattenuated correlations and eigen-structure on project-independent cones
   (one cone per project, the largest), to test whether low inter-correlation
   is real or noise.

Usage: python3 reliability.py EXTDIR RESULTSDIR
"""
import pickle
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from agg import summarize  # noqa: E402

EXT, RES = Path(sys.argv[1]), Path(sys.argv[2])
NM = pickle.load(open(EXT / "names.pkl", "rb"))
names = NM["names"]
cols = ["corpus", "group", "project", "name_id", "is_thm", "is_concept", "n_body_tok", "n_sig_tok", "n_users",
        "n_thm_stmt_users", "t_enum", "t_auto", "t_struct", "n_num", "cert_25", "casebash", "grounding", "numbered",
        "uninformative", "vocab_share", "n_name_tok", "ns_inherit", "refs_own", "refs_lib", "refs_other",
        "sig_refs_own", "sig_refs_lib", "body_dup", "body_dup_eligible", "skel_dup", "skel_dup_eligible",
        "reinvents_mathlib", "sig_dup_cross_project", "sig_eligible", "prop_users", "prop_hits", "n_unresolved_q",
        "n_dot_resolved"]
df = pd.read_parquet(EXT / "metrics.parquet", columns=cols)
oai = (df.group == "openai_math").values
E = np.load(EXT / "edges.npz")
src, dst = E["src"], E["dst"]
name2row = np.full(len(names), -1, dtype=np.int64)
ok = df["name_id"].values >= 0
name2row[df["name_id"].values[ok]] = np.nonzero(ok)[0]
row_of = {names[i]: r for i, r in zip(df["name_id"].values[ok], np.nonzero(ok)[0]) if oai[r]}
for j in np.unique(dst[name2row[dst] < 0]):
    n = names[j]
    while "." in n:
        n = n.rsplit(".", 1)[0]
        r = row_of.get(n)
        if r is not None:
            name2row[j] = r
            break
drow = name2row[dst]
m = (drow >= 0) & (drow != src) & oai[src] & oai[np.where(drow >= 0, drow, 0)]
s_, d_ = src[m], drow[m]
o = np.argsort(s_, kind="stable")
s_, d_ = s_[o], d_[o]
indptr = np.searchsorted(s_, np.arange(len(df) + 1))
del src, dst, drow, E

heads = re.findall(r'declaration:\s*"?([^"\n]+?)"?\s*$', open("/tmp/oai-math/lean/formalization.yaml").read(), re.M)
members = {}
for h in heads:
    r = row_of.get(h)
    if r is None:
        continue
    seen = np.zeros(len(df), dtype=bool)
    seen[r] = True
    st = [r]
    while st:
        x = st.pop()
        nb = d_[indptr[x]:indptr[x + 1]]
        nb = nb[~seen[nb]]
        seen[nb] = True
        st.extend(nb.tolist())
    members[h] = np.nonzero(seen)[0]
print("cones", len(members), flush=True)

# 1. overlap
hs = list(members)
proj = {h: df.project.iat[members[h][0]] for h in hs}
sets = {h: set(members[h].tolist()) for h in hs}
pairs, shared_any = [], 0
for i, a in enumerate(hs):
    for b in hs[i + 1:]:
        inter = len(sets[a] & sets[b])
        if inter:
            pairs.append((a, b, inter / min(len(sets[a]), len(sets[b])), proj[a] == proj[b]))
ov = pd.DataFrame(pairs, columns=["a", "b", "overlap_min", "same_project"])
ov.to_csv(RES / "cone_overlap.csv", index=False)
print("overlapping pairs", len(ov), "with >50% overlap", int((ov.overlap_min > 0.5).sum()),
      "distinct projects", len(set(proj.values())), flush=True)

# 2. split-half reliability
KEYS = ["concepts_per_100_thm", "live_concept_share", "single_use_lemma_share", "cert_token_share",
        "casebash_token_share", "auto_per_1k", "struct_per_1k", "numbered_share", "uninformative_share",
        "grounding", "propagation", "skel_dup_share", "library_ref_share", "proof_to_statement"]
rng = np.random.default_rng(7)
elig = [h for h in hs if df.is_thm.values[members[h]].sum() >= 40]
rel = {k: [] for k in KEYS}
for rep in range(20):
    A, B = [], []
    for h in elig:
        idx = members[h].copy()
        rng.shuffle(idx)
        half = len(idx) // 2
        A.append(summarize(df.iloc[idx[:half]]))
        B.append(summarize(df.iloc[idx[half:]]))
    A, B = pd.DataFrame(A), pd.DataFrame(B)
    for k in KEYS:
        r = pd.Series(A[k]).rank().corr(pd.Series(B[k]).rank())
        rel[k].append(2 * r / (1 + r) if np.isfinite(r) else np.nan)
R = pd.DataFrame({k: [np.nanmean(v), np.nanpercentile(v, 5), np.nanpercentile(v, 95)] for k, v in rel.items()},
                 index=["reliability", "p05", "p95"]).T
R.to_csv(RES / "split_half_reliability.csv")
print(R.round(3).to_string(), flush=True)

# 3. disattenuated structure on one cone per project (largest)
C = pd.read_csv(RES / "cones.csv")
C = C[(C.group == "openai_math") & (C.found == True) & (C.n_thm >= 40)]
C = C.sort_values("n_decls", ascending=False).drop_duplicates("project")
X = C[KEYS].astype(float).rank()
rho = X.corr()
relv = R["reliability"].clip(lower=0.05)
dis = rho / np.sqrt(np.outer(relv, relv))
dis = dis.clip(-1, 1)
dv = dis.values.copy()
np.fill_diagonal(dv, 1)
dis = pd.DataFrame(dv, index=dis.index, columns=dis.columns)
dis.to_csv(RES / "cone_corr_disattenuated.csv")
w = np.linalg.eigvalsh(rho.values)[::-1]
wd = np.linalg.eigvalsh(dis.values)[::-1]
print("independent cones", len(C))
print("eigen share raw", (w / w.sum()).round(3)[:4], "disattenuated", (wd / wd.sum()).round(3)[:4])
# parallel analysis: eigenvalues from shuffled columns
pa = []
for _ in range(500):
    Xs = X.apply(lambda c: rng.permutation(c.values))
    pa.append(np.linalg.eigvalsh(Xs.corr().values)[::-1])
pa = np.percentile(np.array(pa), 95, axis=0)
print("raw eigenvalues", w.round(2)[:5], "parallel-analysis 95th", pa.round(2)[:5])
pd.DataFrame({"eig_raw": w, "eig_disattenuated": wd, "eig_null95": pa}).to_csv(RES / "eigen.csv", index=False)
