#!/usr/bin/env bash
#
# MQTTForge - one-shot build script (Linux / macOS / WSL / Git Bash)
#
#   ./build.sh               run tests, then build sdist + wheel
#   ./build.sh --no-tests    skip the test phase
#
# Produces:
#   dist/mqttforge-<version>.tar.gz   (source distribution)
#   dist/mqttforge-<version>-py3-none-any.whl  (universal wheel)
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
RUN_TESTS=1
for arg in "$@"; do
  case "$arg" in
    --no-tests) RUN_TESTS=0 ;;
    -h|--help)  echo "usage: $0 [--no-tests]"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

echo "==> environment"
"$PYTHON" --version

if [ "$RUN_TESTS" -eq 1 ]; then
  echo "==> running test suite"
  "$PYTHON" -m unittest discover -s tests -q
  echo "==> running end-to-end self-test"
  "$PYTHON" -m mqttforge selftest
fi

echo "==> cleaning previous artifacts"
rm -rf build dist ./*.egg-info

echo "==> building sdist + wheel"
if "$PYTHON" -m build --help >/dev/null 2>&1; then
  "$PYTHON" -m build
else
  echo "    'build' module not found - falling back to pip wheel"
  "$PYTHON" -m pip wheel . --no-deps -w dist
fi

echo "==> artifacts"
ls -la dist

echo "==> smoke test"
"$PYTHON" -m mqttforge --version

echo "==> build complete"
