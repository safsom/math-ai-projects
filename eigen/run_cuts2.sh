#!/bin/zsh
cd /Users/safsom/Projects/math-ai-projects/eigen
until grep -q "ALL DONE" out_cut/chain.log; do sleep 30; done
export GESTURE_CUTS=1
echo "$(date +%T) start Carleson isolated" >> out_cut/chain.log
python3 run_isolated.py job_cut_CarlesonIso.json out_cut/run_CarlesonIso.log > out_cut/wrapper_carleson.log 2>&1
echo "$(date +%T) CARLESON DONE" >> out_cut/chain.log
