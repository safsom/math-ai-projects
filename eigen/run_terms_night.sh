#!/bin/zsh
# Night order (replaces the tail of run_terms.sh and run_terms_redo.sh): finish the OpenAI stage,
# then the small AI corpora, the second pass of the short stages, sphere packing, Carleson last.
# One job at a time (8 GB machine).
cd /Users/safsom/Projects/math-ai-projects/eigen
export GESTURE_CUTS=1 GESTURE_TERMS=1 DRIVER=run_driver3.sh
L=out_terms/chain.log; L2=out_terms_v2/chain.log
mkdir -p out_terms_v2 out_terms_v2_iso out_terms_ai
while pgrep -f "watchdog.py job_terms_oai.json" > /dev/null; do sleep 60; done
echo "$(date +%T) done oai" >> $L
for c in putnam2025 imo2025; do
  echo "$(date +%T) start $c" >> $L
  TERMS_DIR=$PWD/out_terms_ai/$c/terms python3 run_stream.py job_terms_$c.json >> $L 2>&1
  echo "$(date +%T) done $c" >> $L
done
for j in SphereEversion oai_olean iso mathlib; do
  echo "$(date +%T) start $j" >> $L2
  ./run_driver3.sh job_terms2_$j.json out_terms_v2/run_$j.log
  echo "$(date +%T) done $j rc=$?" >> $L2
done
c=spherepacking
echo "$(date +%T) start $c" >> $L
TERMS_DIR=$PWD/out_terms_ai/$c/terms python3 run_stream.py job_terms_$c.json >> $L 2>&1
echo "$(date +%T) done $c" >> $L
echo "$(date +%T) TERMS ALL DONE" >> $L
echo "$(date +%T) start Carleson (isolated)" >> $L2
python3 run_isolated.py job_terms2_CarlesonIso.json out_terms_v2/run_CarlesonIso.log >> $L2 2>&1
echo "$(date +%T) REDO ALL DONE" >> $L2
