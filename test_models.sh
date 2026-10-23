#!/bin/sh
# Build every sample model inside the sandbox image and check that the measuring models hold what they
# say. Local only: CI builds the sandbox image but does not run the models.
#
#   ./test_models.sh                      rebuild the image, run every model
#   ./test_models.sh --no-build cup ...   reuse the image, run only the named models
set -e
cd "$(dirname "$0")"
image=catalog-sandbox:local
if [ "$1" = "--no-build" ]; then
  shift
else
  podman build -q -f containers/Containerfile.sandbox -t "$image" . >/dev/null
fi
exec podman run --rm --network none -v "$PWD:/repo:ro" --entrypoint /venvs/sandbox/bin/python "$image" /repo/sandbox/checks/check_models.py "$@"
