#!/bin/zsh
# Every analysis in the paper, from the final pass's records (run_all.sh) and the text study (../energy).
# Takes about an hour. Results land in out_final/, out_cut/ and out_terms/; then the figures are redrawn.
cd ${0:A:h}
set -e
python3 link_outputs.py
G=out_final
# gestures and eigenproofs (omega and lia merged; then counted apart)
GOUT=$G RESNAME=analysis_merged MERGE_ARITH=1 python3 analyze.py
GOUT=$G RESNAME=analysis_merged python3 stats_eigen.py
GOUT=$G RESNAME=analysis python3 analyze.py
GOUT=$G RESNAME=analysis python3 stats_eigen.py
# every AI corpus on OpenAI's eigenproof basis
GOUT=$G RESNAME=analysis_all MERGE_ARITH=1 WITH_AI=1 python3 analyze.py
GOUT=$G RESNAME=analysis_all python3 stats_corpora.py
# cut measures, and the layout-controlled subsets of the gesture analysis
python3 cuts_exact.py
python3 recheck_cuts.py
for v in analysis_proofs analysis_rho0 analysis_nocut; do GOUT=$G RESNAME=$v python3 stats_eigen.py; done
python3 recheck_ep.py
# tooling: automation and rewriting collapsed, and the control for tactic mix
python3 strip_study.py
for v in analysis_noauto analysis_noauto_norw analysis_author; do GOUT=$G RESNAME=$v python3 stats_eigen.py; done
python3 tactic_mix.py
# proof terms: realized compression, rank ladder, invariance
python3 terms_analysis.py
python3 terms_extra.py
python3 chk_ladder.py out_terms_v4/mathlib.jsonl
# shared against module-by-module compilation of the same OpenAI projects
python3 compare_iso.py out_iso out_final/iso_compare.json
python3 ../report/figures/make_figures.py
