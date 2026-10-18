# Studying proof data with proof theory: the case of AI-generated mathematics

Code, job files, tests and results for the paper *Studying proof data with proof theory: the case of AI-generated mathematics* by Safal R. Aryal
([report/report.pdf](report/report.pdf)).

The paper compiles 96 projects from OpenAI's library of AI-written mathematics
([openai/math](https://github.com/openai/math)), three smaller AI-written corpora (sphere packing by Math Inc's Gauss,
the 2025 Putnam solutions by AxiomProver, and the 2025 IMO solutions by Aristotle) and two human research projects
(Carleson and sphere eversion) against the same version of mathlib. It then measures the proof terms that Lean's
kernel checks. The structure of proofs has rarely been measured empirically, let alone at this scale, so much of the
work is in building measures that can be trusted. Where theorems constrain them, the measures are checked against
those theorems. They are also checked against how much mathlib differs from itself, and against controls for how the
corpora were compiled and for the output of automated tactics.

Many of the quantities themselves are not new. Work on improving automated provers already computes the size of proof
terms, the length of proofs and the steps that do no work, as targets to optimize: for example
[PACT](https://arxiv.org/abs/2102.06203), [ImProver](https://arxiv.org/abs/2410.04753),
[ProofOptimizer](https://arxiv.org/abs/2510.15700), [LeanPolish](https://arxiv.org/abs/2609.38384) and
[Proof-Refactor](https://arxiv.org/abs/2606.03743). The aim here is to turn such quantities into measurements of proofs
themselves, which can eventually be used to study properties of proofs. The paper's section "What is already
measured" gives the full list.

## Findings

Three results hold up under the controls in the paper.

| | OpenAI | mathlib |
|---|---|---|
| distance of the gesture mix from mathlib, as a multiple of a size-matched null | 5.8 | (reference) |
| ... with each call to automation collapsed into one step | 3.4 to 3.9 | (reference) |
| proofs that are larger with their intermediate claims than without them | 40% | 13% |
| realized share of the available compression | 31% | 73% |
| ... on proofs that call no automation | 55% | 86% |

- **Gestures.** The mix of proof steps in OpenAI's proofs is 5.8 times as far from mathlib's as random sets of
  mathlib projects are from the rest of mathlib. About a third of this comes from the certificates that tactics such
  as `ring` and `omega` write into proof terms. The rest survives when those certificates are collapsed into single
  steps, and when only proofs in their optimal layout are kept. The gesture study does not control for subject matter.
- **Redundant claims.** OpenAI's proofs state many intermediate claims (cuts) that do no work. Its layout redundancy
  is higher than mathlib's in almost every project (AUC 0.95), and this does not change on proofs that call no
  automation (AUC 0.94).
- **Realized compression.** OpenAI's proofs realize less of the compression available to them, meaning the amount
  by which a proof could be shortened by proving each repeated piece once and reusing it. They also write cuts that
  save nothing. Both hold on proofs that call no automation, though the realized gap is smaller there (AUC 0.36
  against 0.25).

Two first impressions did not hold up. OpenAI's proofs are longer mostly because they call more automation. Its
slight excess in compressibility comes entirely from automation: on proofs without it, OpenAI is no more compressible
than mathlib (p = 0.14).

## What is measured

- **Text energy** (`energy/`): bits per token of each project's source under a 5-gram Kneser–Ney model of mathlib.
  This mostly measures naming: 76% of OpenAI's gap to mathlib is carried by identifiers.
- **Gestures and eigenproofs** (`eigen/`): every node of a proof term with names erased, types cut to their head
  connective, and hypotheses labelled by use (never, once, more than once). Corpora are compared by the
  Kullback–Leibler divergence of their projects' gesture mixes. This divergence splits into directions, called
  *eigenproofs*, and is judged against a null of random mathlib projects of the same number.
- **Cuts** (`eigen/cuts_exact.py`): for each proof, the exact sizes of the proof as written, its cut-free form and
  its optimal layout, computed by hash-consing without building the cut-free form. From these come the cut
  compression κ, the compressibility χ and the layout redundancy ρ, in bits.
- **Realized compression** (`eigen/terms_analysis.py`): a second pass that eliminates every cut by substitution and
  finds repeated subproofs by canonical hashing. The realized share is what the author's cuts achieve, out of what an
  explicit layout of the cut-free proof could achieve.
- **Checks against theorems.** Two bounds on κ and χ_DAG follow from how cut elimination copies steps. The *rank
  ladder* also follows: a created proof redex needs a cut of logical rank at least one. All three hold on every proof
  in every corpus. The ladder first failed, which is how two errors in the instrument were found, and later three
  more (see "Checking the instruments" in the paper).

## Repository layout

| path | contents |
|---|---|
| `report/` | the paper (`report.tex`, `references.bib`, `report.pdf`) and `figures/make_figures.py`, which draws every figure from the result files below |
| `energy/` | the text study: lexer, Kneser–Ney model, corpus sampling, scoring, project statistics, and `data/out/` with its results. `data/mathlib_env.tsv.gz` is the elaborated mathlib environment the premise statistics resolve names against |
| `eigen/driver/` | the Lean program (Lean 4.34.1) that elaborates each file and writes the gestures, cut sizes and proof-term measures of every theorem |
| `eigen/jobs/` | the exact jobs behind the paper. Stage 1 (`isolated_*`) compiles the human projects and nine OpenAI projects module by module. Stage 2 (`terms_*`) is the final pass over every corpus. Paths are written as `@ROOT@` (see `localize_jobs.py`) |
| `eigen/tests/terms_toy/` | regression test: small theorems whose sizes, ranks and redex counts were worked out by hand |
| `eigen/*.py` | the analyses (listed in `run_analyses.sh`, in order) |
| `eigen/out_final/`, `out_cut/`, `out_terms/`, `out_ai_ready/` | the result files behind every table and figure in the paper |
| `eigen/mathlib_thm_names.txt` | the 254,147 mathlib theorems extracted |

## Quick start

These steps need no corpora and no mathlib build.

```sh
pip install numpy pandas scipy statsmodels matplotlib

# redraw the figures from the result files, and rebuild the paper
python3 report/figures/make_figures.py
cd report && latexmk -pdf report.tex && cd ..

# build the driver (elan installs Lean 4.34.1 from lean-toolchain) and run the regression test
cd eigen/driver && lake build && cd ..
python3 tests/terms_toy/check.py        # prints "ok"
```

## Full reproduction

The extraction takes about a day on a laptop (the OpenAI pass alone takes two hours, and building mathlib takes
longer). It was run on a MacBook Air with 8 GB of memory. The scripts assume zsh, which is the default on macOS.

### 1. Sources

Clone mathlib at OpenAI's pinned commit into `mathlib4/` and build it:

```sh
git clone https://github.com/leanprover-community/mathlib4 mathlib4
cd mathlib4 && git checkout d13f23b723b8a846827a245b89c10fc7d3f11612 && lake exe cache get && lake build && cd ..
```

Then clone each corpus at the commit used:

| path | repository | commit | used by |
|---|---|---|---|
| `corpora/openai_math` | [openai/math](https://github.com/openai/math) | `fd4aeeb2ee4f` | text, compiled |
| `corpora/ai/Sphere-Packing-Lean` | [math-inc/Sphere-Packing-Lean](https://github.com/math-inc/Sphere-Packing-Lean) | `1e98fb493088` | text, compiled |
| `corpora/ai/Putnam2025` | [AxiomMath/Putnam2025](https://github.com/AxiomMath/Putnam2025) | `2653cded72f5` | text, compiled |
| `corpora/ai/IMO2025` | [harmonic-ai/IMO2025](https://github.com/harmonic-ai/IMO2025) | `72b62405a176` | text, compiled |
| `eigen/human/carleson` | [fpvandoorn/carleson](https://github.com/fpvandoorn/carleson) | `306ae5b29300` | compiled |
| `eigen/human/SphereEversion` | [leanprover-community/sphere-eversion](https://github.com/leanprover-community/sphere-eversion) | `9c53f91e2a28` | compiled |
| `corpora/fpvandoorn_carleson` | [fpvandoorn/carleson](https://github.com/fpvandoorn/carleson) | `8972acdfd953` | text |
| `corpora/leanprover-community_sphere-eversion` | [leanprover-community/sphere-eversion](https://github.com/leanprover-community/sphere-eversion) | `df3e74a3fbe1` | text |
| `corpora/ImperialCollegeLondon_FLT` | [ImperialCollegeLondon/FLT](https://github.com/ImperialCollegeLondon/FLT) | `f6c6a2fe9796` | text |
| `corpora/teorth_pfr` | [teorth/pfr](https://github.com/teorth/pfr) | `ce7ac95e620a` | text |
| `corpora/math-inc_strongpnt` | [math-inc/strongpnt](https://github.com/math-inc/strongpnt) | `2f5835c32231` | text |
| `corpora/openai_ten-proofs` | [openai/ten-proofs](https://github.com/openai/ten-proofs) | `94bc0feb6a9f` | text |

The human projects were compiled at a later commit than the one their text was read from.

### 2. Text study

```sh
cd energy
python3 corpus.py mathlib openai tenproofs carleson flt pfr sphere strongpnt    # sample declarations
python3 order_select.py                                                        # optional: n-gram order by held-out cross-entropy
python3 score_text.py                                                          # text energy (mathlib by held-out fold)
gunzip -k data/mathlib_env.tsv.gz && python3 premise.py
python3 analysis.py && python3 decomp.py                                       # project statistics; the 76% split
cd ..
```

`python3 corpus.py ai_spherepacking ai_putnam2025 ai_imo2025 && python3 score_ai.py ai_spherepacking ai_putnam2025 ai_imo2025`
adds the text energy of the other AI corpora.

### 3. Extraction

```sh
cd eigen
python3 localize_jobs.py      # writes jobs/local/ with this checkout's path
./run_all.sh                  # stage 1, then the final pass; progress in out_terms_v4/chain.log
```

`run_all.sh` sets `GESTURE_CUTS=1 GESTURE_TERMS=1`, without which the driver writes gestures only. A module that
stalls is skipped after a time limit and recorded. The streaming runs (`run_stream.py`) and the module-by-module runs
(`run_isolated.py`) restart the driver when it stalls or runs out of memory.

### 4. Analyses and figures

```sh
./run_analyses.sh             # about an hour; needs energy/data/text_energy.pkl from step 2
```

This links the final pass's records into the directories the analyses read (`link_outputs.py`). It then runs every
analysis in the paper and redraws the figures. `python3 chk_ladder.py out_terms_v4/mathlib.jsonl` reports the rank
ladder on its own.

## How the results were checked

- The regression test in `eigen/tests/terms_toy` was written before the proof-term pass was run on any corpus.
- The proof-term pass went through four versions, described in the paper. Every corpus was run with the fourth, which
  is the driver in `eigen/driver`. The gesture and cut records it writes are identical to those of the earlier
  drivers on every one of the 311,674 mathlib and OpenAI records.
- Starting from the final pass's records, `run_analyses.sh` was run on a fresh copy of this repository. It reproduces
  every result file here, and so every number in the paper, up to floating-point noise. The only other differences are
  the example proofs the result files quote, which need the corpora's source checked out.
- `eigen/out_ai_ready/failures.json` (the share of sphere packing, Putnam and IMO theorems that no longer compile) was
  tallied during the runs. No script here regenerates it.
- Compiling nine OpenAI projects module by module instead of in one shared environment leaves the gestures of 97.2%
  of 4,089 theorems unchanged (`compare_iso.py`), and the proof-term sizes of 99.8% of 2,879 proofs.

## Authorship

The paper, questions, measures and controls are Safal R. Aryal's. The code was written by Claude Code, Anthropic's coding
agent, working at the author's direction, as the paper describes. The corpora analysed are not included here and remain under
their own licences.

## Licence

The code and result files in this repository are released under the MIT licence (see `LICENSE`). The corpora it
analyses are not included and remain under their own licences.

## Citation

```bibtex
@software{aryal2026code,
  author = {Aryal, Safal R.},
  title  = {math-ai-projects: Code and results for ``Studying proof data with proof theory: the case of AI-generated mathematics''},
  url    = {https://github.com/safsom/math-ai-projects},
  year   = {2026}
}
```
