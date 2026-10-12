# Machine-written Lean, measured

How do AI-written Lean proofs differ from human-written ones, at scale? This repository measures it on a
large corpus extracted, compiled and analysed on one 8 GB laptop. The full write-up is
[`synthesis/report.html`](synthesis/report.html) (download and open locally).

**Baseline.** mathlib (commit `d13f23b`) is the reference: it is the largest body of human-formalized Lean,
though it has its own conventions and quirks. Comparison corpora: OpenAI's `openai/math` library
(524 projects as text, a random 96 compiled), human research projects (Carleson, sphere eversion, PFR, FLT),
and three other AI corpora: sphere packing (Math Inc's Gauss), Putnam 2025 (AxiomProver) and IMO 2025 (Aristotle).
Projects, not theorems, are the unit of comparison; group tests use projects with ≥ 20 theorems.

## Process and findings

**1. Text is not enough.** A 5-gram Kneser–Ney model of mathlib's source scores the median OpenAI project at
7.00 bits/token against 5.15 for held-out mathlib (AUC 0.94). But 76% of that gap is identifiers, and text
energy barely tracks proof structure (Spearman 0.14 against compiled energy within mathlib). A text model sees
how proofs are *named*, not how they *work*.

**2. Gestures.** So each elaborated proof term is abstracted into a tree of *gestures*: the inference rule
applied, names erased, types cut to their head connective (e.g. `core:Eq.trans(=,=)⇒=`), with each hypothesis
labelled by how often it is used (0 / 1 / ω, the resource classes of linear logic). A structural n-gram model
(each gesture given its parent) is trained on mathlib.
- OpenAI's gesture mix is 280 bits (Gaussian KL) from mathlib's, against 49 for random mathlib project sets of
  the same size: **5.8× the null** (human research code: 1.9×).
- The generalized eigenvectors of the two covariances ("eigenproofs") split that divergence exactly. The top one
  is integer-arithmetic certificates stitched into equation chains (`have h : a = b := by omega`):
  6.3% of OpenAI theorems lie beyond +2 mathlib SD, against 0.7% of mathlib's. It is stronger still in the
  competition provers (39% of AxiomProver's Putnam theorems).

**3. Cut layout.** A *cut* is a named-then-used proof (`have`, a proof `let`, a β-redex). Normalizing every
proof five ways with exact sizes splits cut compression κ = χ − ρ into what sharing *could* save (χ) and pure
layout redundancy (ρ).
- 47% of OpenAI proofs contain a cut (mathlib 17%), but they are not more compressible (χ 0.035 vs 0.029 bits).
  They are **more redundant**: ρ 0.071 vs 0.015 bits (AUC 0.95, p = 2·10⁻⁴⁴). 40% of OpenAI proofs are larger
  with their cuts than without.
- Every AI corpus shares this: ρ = 0.19 (sphere packing), 0.17 (Putnam), 0.16 (IMO).
- Re-running everything on proofs in optimal layout, the divergence survives (4.6× the null), and OpenAI's
  compiled energy rises above mathlib's (AUC 0.63, from a 0.53 tie). The top eigenproof is mostly layout:
  76% of its excess comes from redundant-layout proofs.

**4. Proof terms.** A final pass eliminates every cut by substitution, without ever building the result
(hash-consed), and brackets the best achievable sharing χ* between an explicit layout and the full DAG.
Measured on 143k mathlib proofs and 33k from the other corpora (proofs of ≥ 10 steps):
- **Authors realize very different shares of the compression their proofs contain:** mathlib 73%,
  human research 61%, OpenAI 31%, Putnam 30%, IMO 33%, sphere packing 14%. This is not a length effect: in every
  size bin from 30 nodes up, mathlib realizes more (OpenAI vs mathlib across projects: AUC 0.25, p = 6·10⁻¹⁵).
- Classical bounds check out on real proofs: κ ≤ Σ log₂(uses) and χ_DAG ≤ log₂(max copies) hold for 100% of
  proofs in every corpus. The rank ladder (a created proof redex needs a cut of logical rank ≥ 1) holds for
  99.6% of 1,100 mathlib cases.
- Real libraries sit in the elementary regime: most cuts have rank 0, created redexes appear in 0.8% of mathlib
  proofs, and sharing could halve a proof in only 2.1% of them. The big misses are computational
  (e.g. `CartanMatrix.E₈_det`: 562k nodes cut-free, 21k with explicit sharing).

**Caveats.** The OpenAI compiled sample is 96 of 524 projects (the later term passes cover 12% of its proofs).
The AI corpora were written for older Lean versions and 11–67% of their theorems fail under this mathlib, so the
IMO column is indicative only. Erdős 90 and Anthropic's FLT were not compiled. The n-gram models are
deliberately simple.

## Layout

- `proofstudy/`: first exploratory study.
- `energy/`: text and premise energy (5-gram models).
- `eigen/`: Lean 4 extraction (`lean3/`: gestures, cut normal forms, proof-term pass), eigenproofs and all
  later analyses; `eigen/tests/terms_toy/` holds the hand-computed regression test.
- `synthesis/`: `build.py` produces `report.html` from the result files.
- `references.bib`: related work (proof theory, cut introduction, grammar compression, library mining,
  AI provers, corpora at the exact commits analysed). Every entry is checked against doi.org, the arXiv
  API or the source repository.

Corpora are not included and remain under their own licences (see `references.bib` for sources and commits).
Built against Lean 4.34.1.

## Citation

```bibtex
@misc{aryal2026machinelean,
  author       = {Aryal, Safal},
  title        = {Machine-Written {L}ean, Measured: Text, Gestures, Cut Layout and Compression in {AI}-Written Proofs},
  year         = {2026},
  howpublished = {\url{https://github.com/safsom/math-ai-projects}},
  note         = {Code and analyses written with Claude (Anthropic)}
}
```

Ideas and research direction: Safal Aryal. Code and analyses: Claude (Anthropic), at Safal's direction (see `AUTHORS`).
