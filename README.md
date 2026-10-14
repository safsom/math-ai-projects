# Machine-written Lean, measured

How do AI-written Lean proofs differ from human-written ones, at scale? We extracted and compiled a large corpus
on one 8 GB laptop and measured the elaborated proof terms directly, using classical proof-theoretic quantities
(cuts, cut elimination, sharing, logical rank) as instruments.

**Corpora.** Baseline: mathlib (commit `d13f23b`), the largest body of human-formalized Lean, with its own
conventions and quirks. AI-written: OpenAI's `openai/math` (96 randomly drawn projects compiled, 36k theorems),
and, as independent replications, sphere packing (Math Inc's Gauss), Putnam 2025 (AxiomProver) and IMO 2025
(Aristotle). Human research code (Carleson, sphere eversion) serves as a second human reference. Projects, not
theorems, are the unit for group tests (projects with ≥ 20 theorems); per-proof measures use proofs of ≥ 10 steps
(mathlib 143k, OpenAI 26k).

## Approach

1. **Text is not enough.** Under a 5-gram model of mathlib's source, OpenAI text costs 7.00 vs 5.15 bits/token
   (AUC 0.94), but 76% of the gap is identifiers. Text shows how proofs are *named*, not how they *work*.
2. **Gestures.** Each elaborated proof term is walked in full and every node abstracted to a *gesture*: the rule
   applied, names erased, types cut to their head connective (e.g. `core:Eq.trans(=,=)⇒=`), with hypotheses
   labelled by use count (0 / 1 / ω). Corpora are compared by their gesture mix against a size-matched null.
3. **Cuts.** A cut is a proof that is named, then used (`have`, a proof `let`, a β-redex). Each proof is normalized
   with exact tree sizes: as written, cut-free, and in its optimal layout. Cut compression splits as
   κ = χ − ρ: χ is what sharing *could* save, ρ is pure layout redundancy.
4. **Proof terms.** Every cut is eliminated by substitution under hash-consing (the blowup is never built). This
   brackets the best achievable sharing χ* between an explicit layout (χ_lb) and the full DAG (χ_DAG).

## Main findings

**1. AI provers write redundant intermediate claims, and it is not because there is more to share.**

| | mathlib | human | OpenAI | sphere packing | Putnam 2025 |
|---|---|---|---|---|---|
| proofs with a cut | 17% | 33% | 47% | 53% | 73% |
| χ, compressibility (bits/proof) | 0.029 | 0.063 | 0.035 | 0.021 | 0.056 |
| ρ, layout redundancy (bits/proof) | 0.015 | 0.028 | **0.071** | **0.189** | **0.174** |
| proofs larger *with* their cuts | 13% | 26% | 40% | 49% | 67% |

OpenAI vs mathlib projects: ρ AUC 0.95 (p = 2·10⁻⁴⁴); vs human code AUC 0.85 (p = 4·10⁻⁵). χ is not higher.
All three other AI systems show the same signature.

**2. Authors realize very different shares of the compression their proofs contain.** Realized share
= Σχ_author / Σχ_lb, a conservative estimate. mathlib **73%**, human research 61%, OpenAI **31%**, Putnam 30%,
sphere packing 14%. This is not a length effect. Within cut-free size bins (mathlib / OpenAI):

| size (nodes) | 30–99 | 100–299 | 300–999 | 1000+ |
|---|---|---|---|---|
| mathlib | 63% | 77% | 71% | 75% |
| OpenAI | 49% | 39% | 23% | 30% |

Across projects, OpenAI vs mathlib: AUC 0.25, p = 6·10⁻¹⁵.

**3. AI proofs use a different mix of inferences, beyond layout.** OpenAI's gesture mix is 280 bits (Gaussian KL)
from mathlib's, against 49 bits for random mathlib project sets of the same size: **5.8× the null** (human research
code: 1.9×). Under each layout control it stays well above the null: proofs only 5.5×, optimal-layout proofs only 4.6×,
cut-free proofs only 4.8×.

**4. The instruments behave as theory predicts.**
- κ ≤ Σ log₂(uses) and χ_DAG ≤ log₂(max copies) hold for **100%** of proofs in every corpus.
- Rank ladder: a created proof redex needs a cut of logical rank ≥ 1 (the source of Statman/Orevkov-type
  blowups). It holds for **99.6%** of 1,100 mathlib cases, with definitions unfolded.
- Real libraries sit in the elementary regime: sharing could halve a proof in 2.1% of mathlib proofs, and created
  redexes appear in 0.8%.

## Controls

- **Size-matched nulls:** each divergence is compared with random mathlib project sets of the same size.
- **Layout controls:** every compiled analysis is rerun on proofs in optimal layout and on proofs with no cuts.
- **Size bins** for the realized share.
- **Replication** across three independent AI systems.
- **Two independent passes:** the cut pass (normalization) and the term pass (hashing) agree on exact cut-free
  size for 98.5% of mathlib. The exceptions are a predicted class (created redexes).
- **Reproducibility across compilation modes:** OpenAI theorems compiled two ways (one shared environment and module by module)
  give identical term measures for 99.8% of 2,879 and identical gesture multisets for 97.2% of 4,089.
- **Split-half recovery** of the leading divergence direction: 0.95.
- **Hand-computed regression test:** `eigen/tests/terms_toy`.
- **Manual checking:** a sample of proofs was checked by hand.

## Limitations

- **OpenAI coverage:** the compiled sample is 96 of 524 projects. Rank figures cover 12% of its proofs.
- **Version drift:** the AI corpora were written for older Lean versions, and 11–20% of Putnam and sphere-packing
  theorems fail under this mathlib, which biases towards shorter proofs. IMO 2025 (29 proofs) is too small to report.
- **Hidden propositions:** statements that are propositions only after unfolding are read as data
  (0.13 per 100 cuts).
- **No pre-registration:** analysis choices were made on this data.

## Layout

- `eigen/`: Lean 4 extraction (`lean3/`: gestures, exact cut normal forms, proof-term pass), job files, run logs,
  analyses and result JSONs.
- `energy/`: text model (motivation).
- `synthesis/`: `build.py` renders `report.html`, the full lab notebook, including exploratory and revised results
  not listed above.
- `references.bib`: related work, every entry checked against doi.org, the arXiv API or the source repository.

Corpora are not included and remain under their own licences (sources and commits in `references.bib`).
Lean 4.34.1.

## Citation

```bibtex
@misc{aryal2026machinelean,
  author       = {Aryal, Safal},
  title        = {Machine-Written {L}ean, Measured: Layout, Compression and Inference Mix in {AI}-Written Proofs},
  year         = {2026},
  howpublished = {\url{https://github.com/safsom/math-ai-projects}},
  note         = {Code and analyses written with Claude (Anthropic)}
}
```

Ideas and research direction: Safal Aryal. Code and analyses: Claude (Anthropic), at Safal's direction (see `AUTHORS`).
