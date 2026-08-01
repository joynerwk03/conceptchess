#!/bin/sh
# Build the compiled core into a shared library loaded via ctypes.
# macOS -> libcengine.dylib, Linux/WSL2 -> libcengine.so (engine/core.py,
# core/eval_check.py and core/perft_check.py pick the same name by platform).
# CC defaults to `cc` (clang on macOS, gcc on Ubuntu/WSL2); -pthread is needed
# for Lazy SMP and -lm for math.h when linking on Linux (both no-ops on macOS).
set -e
cd "$(dirname "$0")"
case "$(uname -s)" in
  Darwin) OUT=libcengine.dylib ;;
  *)      OUT=libcengine.so ;;
esac
${CC:-cc} -O3 -march=native -shared -fPIC -pthread -o "$OUT" cengine.c -lm
echo "built core/$OUT"
