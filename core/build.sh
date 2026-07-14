#!/bin/sh
# Build the compiled core into a shared library loaded via ctypes.
set -e
cd "$(dirname "$0")"
clang -O3 -march=native -shared -fPIC -o libcengine.dylib cengine.c
echo "built core/libcengine.dylib"
