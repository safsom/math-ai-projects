#!/bin/zsh
# Cut-statistics extraction: compiled projects from .olean files, then mathlib, then OpenAI (shared mode).
cd /Users/safsom/Projects/math-ai-projects/eigen
export GESTURE_CUTS=1
for j in SphereEversion Carleson oai_olean mathlib; do
  echo "$(date +%T) start $j"
  ./run_driver2.sh job_cut_$j.json out_cut/run_$j.log
  echo "$(date +%T) done $j rc=$?"
done
echo "$(date +%T) start oai"
DRIVER=run_driver2.sh python3 watchdog.py job_cut_oai.json
echo "$(date +%T) ALL DONE"
