#!/bin/zsh
# usage: run_driver.sh JOB.json LOGFILE
# Runs the driver (driver/) on a job, against the mathlib built in ../mathlib4. Set GESTURE_CUTS=1 GESTURE_TERMS=1
# for the cut and proof-term records.
HERE=${0:A:h}
ML=${HERE:h}/mathlib4
TOOLCHAIN=$HOME/.elan/toolchains/leanprover--lean4---v4.34.1
export LEAN_BIN=$TOOLCHAIN/bin/lean
export LEAN_PATH=$(for p in Cli batteries Qq aesop proofwidgets importGraph LeanSearchClient plausible; do printf '%s:' $ML/.lake/packages/$p/.lake/build/lib/lean; done)$ML/.lake/build/lib/lean
export LEAN_BACKTRACE=0
ulimit -s 65520 2>/dev/null || ulimit -s hard
# peak memory goes to the log: BSD time takes -l, GNU time -v
[[ $(uname) == Darwin ]] && TF=-l || TF=-v
exec /usr/bin/time $TF $HERE/driver/.lake/build/bin/gestures "$1" > "$2" 2>&1
