# Proof style in OpenAI's Lean library: first study

Syntactic, corpus-scale measurement of proof-style attributes in OpenAI's `openai/math` and `openai/ten-proofs` Lean libraries, compared against mathlib (at OpenAI's pinned revision), four human research formalizations (Carleson, FLT, PFR, sphere eversion) and StrongPNT.

## Pipeline

| Step | Script | Output |
|---|---|---|
| Parse | `leanparse.py` | comment/string stripping, namespace/open tracking, declaration splitting, identifiers, tactics |
| Extract (2 passes) | `extract.py OUT` | name table, then per-declaration features and resolved references |
| Assemble | `build.py OUT` | `decls.parquet`, `edges.npz`, `names.pkl` |
| Metrics | `metrics.py OUT` | `metrics.parquet` (usage counts, derivation, naming, duplication, brute force) |
| Compression | `compress.py results/compression_by_project.csv` | window-normalized zlib ratio per project |
| Statistics | `analysis.py OUT results` | project metrics, group medians with bootstrap CIs, tests, headline cones, correlations |
| Regimes | `strata.py OUT results` | pooled metrics for OpenAI's conceptual core vs certificate shell |

`agg.py` holds the single definition of every attribute, used for projects, cones and groups.

Corpora are expected at `/tmp/oai-math`, `/tmp/ten-proofs` and `/tmp/corpora/*` (clone commands in the session log; revisions pinned from OpenAI's `lake-manifest.json`). A full run takes about 30 minutes on 2 cores with 7 GB of RAM.

## Results

`results/` holds every table behind the dashboard: `group_summary.csv`, `tests.csv`, `project_metrics.csv`, `cones.csv`, `cone_spearman_openai.csv`, `strata_pooled.csv`, `compression_by_project.csv`, plus the tidy `ds_*.csv` files the dashboard reads.

## Known limits

No elaboration: dependencies are syntactic lower bounds; generalised field notation (`h.foo`) is resolved only when `foo` is unique in its corpus and absent from mathlib. The mathlib-restatement detector was dropped from reporting (mostly false positives).
