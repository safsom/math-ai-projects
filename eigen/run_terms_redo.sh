#!/bin/zsh
# Second proof-term pass (unfolded ranks, proof-applied redexes) for the stages the first chain ran
# before the binary was patched. Waits for the first chain to finish.
cd /Users/safsom/Projects/math-ai-projects/eigen
until grep -q "TERMS ALL DONE" out_terms/chain.log; do sleep 300; done
export GESTURE_CUTS=1 GESTURE_TERMS=1 DRIVER=run_driver3.sh
L=out_terms_v2/chain.log
mkdir -p out_terms_v2 out_terms_v2_iso
for j in SphereEversion oai_olean iso mathlib; do
  echo "$(date +%T) start $j" >> $L
  ./run_driver3.sh job_terms2_$j.json out_terms_v2/run_$j.log
  echo "$(date +%T) done $j rc=$?" >> $L
done
echo "$(date +%T) start Carleson (isolated)" >> $L
python3 run_isolated.py job_terms2_CarlesonIso.json out_terms_v2/run_CarlesonIso.log >> $L 2>&1
echo "$(date +%T) REDO ALL DONE" >> $L
