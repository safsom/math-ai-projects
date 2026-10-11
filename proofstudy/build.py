"""Assemble pass-2 chunks into one declaration table + an integer edge list,
chunk by chunk with compact dtypes (the full corpus has ~3.9M declarations).

Outputs (in OUTDIR):
  decls.parquet  one row per declaration (analysed corpora only)
  edges.npz      src (decl row), dst (name id), where (0=statement,1=proof), dcorp (corpus code)
  names.pkl      names list (index = name id), corpus code per name, files, projects, namespaces
"""
import gzip
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

OUT = Path(sys.argv[1])
tables = pickle.load(open(OUT / "tables.pkl", "rb"))
CORP = list(tables)
code = {c: i for i, c in enumerate(CORP)}

names, ncorp, nid = [], [], {}
for c in CORP:
    for n in sorted(tables[c]):
        if n not in nid:
            nid[n] = len(names)
            names.append(n)
            ncorp.append(code[c])
del tables

files, projects, nss = {}, {}, {}
KINDS = {}


def intern(d, k):
    v = d.get(k)
    if v is None:
        v = d[k] = len(d)
    return v


def h64(x):
    return np.uint64(int(x, 16)).astype(np.int64) if x else np.int64(0)


writer = None
src_parts, dst_parts, where_parts, dc_parts = [], [], [], []
base = 0
for p in sorted(OUT.glob("p2_*.pkl.gz")):
    with gzip.open(p, "rb") as fh:
        r, e = pickle.load(fh)
    s, d, w, dc = [], [], [], []
    for i, (sr, br) in enumerate(e):
        for k, c in sr:
            j = nid.get(k)
            if j is not None:
                s.append(base + i); d.append(j); w.append(0); dc.append(code[c])
        for k, c in br:
            j = nid.get(k)
            if j is not None:
                s.append(base + i); d.append(j); w.append(1); dc.append(code[c])
    src_parts.append(np.array(s, dtype=np.int32)); dst_parts.append(np.array(d, dtype=np.int32))
    where_parts.append(np.array(w, dtype=np.int8)); dc_parts.append(np.array(dc, dtype=np.int8))
    del e, s, d, w, dc
    df = pd.DataFrame(r)
    del r
    df.drop(columns=["sig_text"], inplace=True)
    df["file_id"] = df["path"].map(lambda x: intern(files, x)).astype(np.int32)
    df["project_id"] = df["project"].map(lambda x: intern(projects, x)).astype(np.int32)
    df["ns_id"] = df["ns"].map(lambda x: intern(nss, x)).astype(np.int32)
    df["corpus_code"] = df["corpus"].map(code).astype(np.int8)
    df["kind_id"] = df["kind"].map(lambda x: intern(KINDS, x)).astype(np.int8)
    df["name_id"] = df["name"].map(lambda x: nid.get(x, -1) if x else -1).astype(np.int32)
    for hcol in ("body_hash", "skel_hash", "sig_hash"):
        df[hcol] = df[hcol].map(h64).astype(np.int64)
    df.drop(columns=["path", "project", "ns", "corpus", "kind", "name"], inplace=True)
    for col in df.columns:
        if df[col].dtype == np.int64 and not col.endswith("hash"):
            df[col] = df[col].astype(np.int32)
    t = pa.Table.from_pandas(df, preserve_index=False)
    if writer is None:
        schema = t.schema
        writer = pq.ParquetWriter(OUT / "decls.parquet", schema)
    writer.write_table(t.cast(schema))
    base += len(df)
    del df, t
    print(p.name, base, flush=True)
writer.close()

np.savez_compressed(OUT / "edges.npz", src=np.concatenate(src_parts), dst=np.concatenate(dst_parts),
                    where=np.concatenate(where_parts), dcorp=np.concatenate(dc_parts))
inv = lambda d: [k for k, _ in sorted(d.items(), key=lambda kv: kv[1])]
pickle.dump({"names": names, "ncorp": np.array(ncorp, dtype=np.int8), "corpora": CORP,
             "files": inv(files), "projects": inv(projects), "namespaces": inv(nss), "kinds": inv(KINDS)},
            open(OUT / "names.pkl", "wb"), protocol=5)
print("decls", base, "edges", sum(len(x) for x in src_parts), "names", len(names))
