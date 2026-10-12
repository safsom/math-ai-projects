#!/bin/zsh
# usage: run_driver.sh JOB.json LOGFILE
ML=/Users/safsom/Projects/math-ai-projects/mathlib4
export LEAN_BIN=$HOME/.elan/toolchains/leanprover--lean4---v4.34.1/bin/lean
export LEAN_PATH=$(for p in Cli batteries Qq aesop proofwidgets importGraph LeanSearchClient plausible; do printf '%s:' $ML/.lake/packages/$p/.lake/build/lib/lean; done)$ML/.lake/build/lib/lean
export LEAN_BACKTRACE=0
ulimit -s 65520 2>/dev/null || ulimit -s hard
exec /usr/bin/time -l /Users/safsom/Projects/math-ai-projects/eigen/lean3b/.lake/build/bin/gestures "$1" > "$2" 2>&1
