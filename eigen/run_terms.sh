#!/bin/zsh
# Proof-term pass: every corpus with GESTURE_TERMS=1, terms of compiled projects saved under */terms.
cd /Users/safsom/Projects/math-ai-projects/eigen
export GESTURE_CUTS=1 GESTURE_TERMS=1 DRIVER=run_driver3.sh
L=out_terms/chain.log
mkdir -p out_terms out_terms_iso out_terms_ai
for j in SphereEversion oai_olean iso mathlib; do
  echo "$(date +%T) start $j" >> $L
  ./run_driver3.sh job_terms_$j.json out_terms/run_$j.log
  echo "$(date +%T) done $j rc=$?" >> $L
done
echo "$(date +%T) start Carleson (oleans)" >> $L
./run_driver3.sh job_terms_Carleson.json out_terms/run_Carleson.log
if [ ! -s out_terms/human.Carleson.jsonl ]; then
  echo "$(date +%T) Carleson oleans failed; isolated" >> $L
  python3 run_isolated.py job_terms_CarlesonIso.json out_terms/run_CarlesonIso.log >> $L 2>&1
fi
echo "$(date +%T) done Carleson" >> $L
echo "$(date +%T) start oai" >> $L
TERMS_DIR=$PWD/out_terms/terms python3 watchdog.py job_terms_oai.json >> $L 2>&1
echo "$(date +%T) done oai" >> $L
for c in putnam2025 imo2025 spherepacking; do
  echo "$(date +%T) start $c" >> $L
  TERMS_DIR=$PWD/out_terms_ai/$c/terms python3 run_stream.py job_terms_$c.json >> $L 2>&1
  echo "$(date +%T) done $c" >> $L
done
echo "$(date +%T) TERMS ALL DONE" >> $L
