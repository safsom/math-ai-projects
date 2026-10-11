"""Per-declaration metrics from decls.parquet + edges.npz.

Adds, per declaration:
  graph:    n_users, n_thm_stmt_users, n_proof_users (in-corpus, distinct citing decls)
  derivation: refs_own, refs_lib (core+batteries+mathlib), refs_other (distinct targets)
  naming:   n_name_tok, numbered, uninformative, vocab_share, grounding (share of name tokens
            found in the names of constants the statement mentions), ns_inherit
  dup:      body_dup, skel_dup, sig_dup_cross_project, reinvents_mathlib
  brute:    numeral_density, cert (numeral-dense or kernel computation), casebash
and per in-corpus concept (def/type with >=2 theorem statement users):
  propagation = share of those theorems whose name contains the concept's name.

Usage: python3 metrics.py EXTDIR
"""
import pickle
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from leanparse import name_tokens  # noqa: E402

EXT = Path(sys.argv[1])
NM = pickle.load(open(EXT / "names.pkl", "rb"))
names, ncorp, CORP = NM["names"], NM["ncorp"], NM["corpora"]
KINDS = NM["kinds"]
df = pd.read_parquet(EXT / "decls.parquet")
E = np.load(EXT / "edges.npz")
src, dst, where = E["src"], E["dst"], E["where"]
print("loaded", len(df), len(src), flush=True)

GROUP = {"oai": "openai_math", "tenproofs": "openai_ten", "mathlib": "mathlib", "carleson": "human_research",
         "sphere": "human_research", "pfr": "human_research", "flt": "human_research", "strongpnt": "other_ai"}
LIB = {CORP.index(c) for c in ("core", "batteries", "mathlib")}
df["corpus"] = [CORP[c] for c in df["corpus_code"]]
df["group"] = df["corpus"].map(GROUP)
df["kind"] = [KINDS[k] for k in df["kind_id"]]
df["project"] = [NM["projects"][p] for p in df["project_id"]]
THM = {"theorem", "lemma"}
DEF = {"def", "abbrev", "irreducible_def", "opaque"}
TYP = {"structure", "class", "inductive", "class_inductive", "coinductive"}
df["is_thm"] = df["kind"].isin(THM)
df["is_def"] = df["kind"].isin(DEF)
df["is_type"] = df["kind"].isin(TYP)
df["is_concept"] = df["is_def"] | df["is_type"]

# ------------------------------------------------ name id -> decl row -------
name2row = np.full(len(names), -1, dtype=np.int64)
ok = df["name_id"].values >= 0
name2row[df["name_id"].values[ok]] = np.nonzero(ok)[0]
# generated names (structure fields, ctors, eq lemmas) -> nearest declared prefix
missing = np.unique(dst[name2row[dst] < 0])
# build dict only for analysed decl names to resolve prefixes
an_names = {names[i]: r for i, r in zip(df["name_id"].values[ok], np.nonzero(ok)[0])}
fix = {}
for j in missing:
    n = names[j]
    while "." in n:
        n = n.rsplit(".", 1)[0]
        r = an_names.get(n)
        if r is not None:
            fix[j] = r
            break
for j, r in fix.items():
    name2row[j] = r
del an_names
drow = name2row[dst]
corp_of_row = df["corpus_code"].values
src_corp = corp_of_row[src]
incorp = (drow >= 0) & (drow != src) & (corp_of_row[np.where(drow >= 0, drow, 0)] == src_corp)
print("in-corpus edges", incorp.sum(), "generated-name fixes", len(fix), flush=True)

# ------------------------------------------------ usage counts --------------
ic = pd.DataFrame({"s": src[incorp].astype(np.int32), "d": drow[incorp].astype(np.int32),
                   "w": where[incorp]}).drop_duplicates()
is_thm = df["is_thm"].values
df["n_users"] = ic.groupby("d")["s"].nunique().reindex(range(len(df)), fill_value=0).values
st = ic[(ic.w == 0) & is_thm[ic.s.values]]
df["n_thm_stmt_users"] = st.groupby("d")["s"].nunique().reindex(range(len(df)), fill_value=0).values
pr = ic[ic.w == 1]
df["n_proof_users"] = pr.groupby("d")["s"].nunique().reindex(range(len(df)), fill_value=0).values
df["n_out_incorpus"] = ic.groupby("s")["d"].nunique().reindex(range(len(df)), fill_value=0).values
st = st[["s", "d"]].copy()
del ic, pr
import gc; gc.collect()

# ------------------------------------------------ derivation ----------------
dcorp = E["dcorp"]
own = dcorp == src_corp
lib = np.isin(dcorp, list(LIB)) & ~own
oth = ~own & ~lib
for lab, m in (("refs_own", own), ("refs_lib", lib), ("refs_other", oth)):
    df[lab] = np.bincount(src[m], minlength=len(df)).astype(np.int32)
sig_m = where == 0
df["sig_refs_own"] = np.bincount(src[sig_m & own], minlength=len(df)).astype(np.int32)
df["sig_refs_lib"] = np.bincount(src[sig_m & lib], minlength=len(df)).astype(np.int32)
sig_src, sig_dst = src[sig_m], dst[sig_m]
del own, lib, oth, src_corp, drow, incorp, dcorp, src, dst, where, sig_m, E, name2row
gc.collect()
print("derivation done", flush=True)

# ------------------------------------------------ naming --------------------
_UNINF = re.compile(r"(^|_)(aux|key|step|claim|part|case|lemma|helper|tmp|main|core|sub|foo|bar|technical|"
                    r"auxiliary|basic|fact|thm|lem|prop|cor|piece|chunk|block|final|stage|phase)\d*($|_)", re.I)
_NUM = re.compile(r"(\d+[a-z]?|_[a-z]\d+)$|\d{2,}")
short = []
nid_vals = df["name_id"].values
for i in nid_vals:
    short.append(names[i].rsplit(".", 1)[-1] if i >= 0 else "")
df["short"] = short
tokcache = {}


def toks(s):
    t = tokcache.get(s)
    if t is None:
        t = tokcache[s] = tuple(name_tokens(s))
    return t


name_tok = [toks(s) if s else () for s in short]
df["n_name_tok"] = np.array([len(t) for t in name_tok], dtype=np.int16)
df["n_name_chars"] = df["short"].str.len().astype(np.int16)
df["numbered"] = [bool(_NUM.search(x)) for x in short]
df["uninformative"] = [bool(_UNINF.search(x)) for x in short]
# mathlib theorem-name vocabulary (tokens used >= 5 times)
mlc = CORP.index("mathlib")
voc = Counter()
for t, k, c in zip(name_tok, df["is_thm"].values, df["corpus_code"].values):
    if c == mlc and k:
        voc.update(t)
vocab = {w for w, n in voc.items() if n >= 5}
df["vocab_share"] = [sum(w in vocab for w in t) / len(t) if t else np.nan for t in name_tok]
print("naming basic done; mathlib vocab", len(vocab), flush=True)

# statement grounding: share of a theorem's name tokens that appear among the
# tokens of the (short) names of constants its statement refers to
order = np.argsort(sig_src, kind="stable")
ssrc = sig_src[order]
sdst = sig_dst[order]
del sig_src, sig_dst, order
bounds = np.searchsorted(ssrc, np.arange(len(df) + 1))
ntok_of_name = {}


def name_id_tokens(j):
    t = ntok_of_name.get(j)
    if t is None:
        t = ntok_of_name[j] = frozenset(toks(names[j].rsplit(".", 1)[-1]))
    return t


ground = np.full(len(df), np.nan, dtype=np.float32)
nsinh = np.zeros(len(df), dtype=bool)
ns_last = [NM["namespaces"][k].rsplit(".", 1)[-1] for k in df["ns_id"].values]
thm_rows = np.nonzero(df["is_thm"].values & (nid_vals >= 0))[0]
for r in thm_rows:
    a, b = bounds[r], bounds[r + 1]
    t = name_tok[r]
    if a == b or not t:
        continue
    pool = set()
    lasts = set()
    for j in sdst[a:b]:
        pool |= name_id_tokens(j)
        lasts.add(names[j].rsplit(".", 1)[-1])
    ground[r] = sum(w in pool for w in t) / len(t)
    nsinh[r] = ns_last[r] in lasts
df["grounding"] = ground
df["ns_inherit"] = nsinh
del ntok_of_name, ssrc, sdst, bounds, ground, nsinh, ns_last, name_tok
gc.collect()
print("grounding done", flush=True)

# concept-name propagation: for in-corpus concepts with >=2 theorem statement users
conc = df["is_concept"].values
pe = st[conc[st.d.values]]
lower = lambda s: s[:1].lower() + s[1:]
prop_hit = np.zeros(len(pe), dtype=bool)
dn = [lower(short[d]) for d in pe.d.values]
sn = [short[s] for s in pe.s.values]
for k, (a, b) in enumerate(zip(dn, sn)):
    if not a:
        continue
    ta, tb = toks(a), toks(b)
    if not ta or len(ta) > len(tb):
        continue
    L = len(ta)
    prop_hit[k] = any(tb[i:i + L] == ta for i in range(len(tb) - L + 1))
pe = pe.assign(hit=prop_hit)
pc = pe.groupby("d").agg(users=("s", "nunique"), hits=("hit", "sum"))
pc = pc[pc.users >= 2]
df["prop_users"] = pc["users"].reindex(range(len(df))).values
df["prop_hits"] = pc["hits"].reindex(range(len(df))).values
print("propagation done", len(pc), flush=True)

# ------------------------------------------------ duplication ----------------
cc = df["corpus_code"].values
for col, mincol, thr, out in (("body_hash", "n_body_tok", 20, "body_dup"), ("skel_hash", "n_body_tok", 30, "skel_dup")):
    m = df["is_thm"].values & (df[mincol].values >= thr) & (df[col].values != 0)
    key = pd.Series(list(zip(cc[m], df[col].values[m])))
    cnt = key.map(key.value_counts())
    v = np.zeros(len(df), dtype=bool)
    v[np.nonzero(m)[0]] = cnt.values >= 2
    df[out] = v
    df[out + "_eligible"] = m
# statement duplicates across projects within a corpus, and verbatim reinvention of mathlib statements
m = df["is_thm"].values & (df["n_sig_tok"].values >= 8) & (df["sig_hash"].values != 0)
sub = df.loc[m, ["corpus_code", "sig_hash", "project_id"]]
nproj = sub.groupby(["corpus_code", "sig_hash"])["project_id"].nunique()
df["sig_dup_cross_project"] = False
df.loc[m, "sig_dup_cross_project"] = sub.set_index(["corpus_code", "sig_hash"]).index.map(nproj).values >= 2
mlh = set(df.loc[m & (cc == mlc), "sig_hash"].values)
df["reinvents_mathlib"] = False
df.loc[m & (cc != mlc), "reinvents_mathlib"] = df.loc[m & (cc != mlc), "sig_hash"].isin(mlh).values
df["sig_eligible"] = m
print("duplication done", flush=True)

# ------------------------------------------------ brute force ----------------
bt = df["n_body_tok"].values.astype(np.float64)
df["numeral_density"] = np.where(bt > 0, df["n_num"].values / np.maximum(bt, 1), np.nan)
for thr in (0.15, 0.25, 0.40):
    df[f"cert_{int(thr*100)}"] = ((bt >= 50) & (df["numeral_density"].values >= thr)) | (df["t_decide"].values > 0)
df["casebash"] = df["is_thm"].values & ((df["t_fin_cases"].values + df["t_interval_cases"].values) > 0) & \
                 ((df["t_allgoals"].values > 0) | (df["t_decide"].values > 0))
df["heavy_hint"] = df["nlinarith_hint_max"].values >= 5

keep = [c for c in df.columns if c not in ("kind_id",)]
df[keep].to_parquet(EXT / "metrics.parquet")
pickle.dump({"vocab_size": len(vocab)}, open(EXT / "metrics_meta.pkl", "wb"))
print("wrote metrics", df.shape, flush=True)
