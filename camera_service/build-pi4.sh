#!/usr/bin/env sh
set -eu

GOOS="${GOOS:-linux}"
GOARCH="${GOARCH:-arm64}"
GOARM="${GOARM:-}"
OUTPUT="${OUTPUT:-dist/axocare-camera-pi4}"

mkdir -p "$(dirname "$OUTPUT")"

if [ -n "$GOARM" ]; then
  export GOARM
fi

export CGO_ENABLED=0
export GOOS
export GOARCH

go build -trimpath -ldflags="-s -w" -o "$OUTPUT" .

echo "Built $OUTPUT for $GOOS/$GOARCH${GOARM:+ GOARM=$GOARM}"
