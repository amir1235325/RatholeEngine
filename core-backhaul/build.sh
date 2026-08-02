#!/usr/bin/env bash
# core-backhaul/build.sh — sakht-e binary-e backhaul-e patch-shode (uTLS ClientHello-ye Chrome).
# estefade: bash core-backhaul/build.sh <target> <output-dir>
#   target: linux-amd64 | linux-arm64
#
# CHERA in patch: backhaul-e upstream az crypto/tls-e Go estefade mikonad ke asar-angosht-e
# (JA3/JA4) mokhtas-e khodesh darad — DPI mitavanad «client-e Go» ra az morurgar tafkik konad،
# hatta vaghti hedar-haye HTTP (User-Agent va ...) kamelan tabiei bashand (upstream an-ha ra darad).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=upstream.env
source "$ROOT/core-backhaul/upstream.env"

[ "$#" -eq 2 ] || {
  echo "usage: $0 <target> <output-dir>" >&2
  exit 2
}

target="$1"
output_dir="$2"
case " $BACKHAUL_CORE_TARGETS " in
  *" $target "*) ;;
  *) echo "target-e core mojaz nist: $target" >&2; exit 2 ;;
esac
case "$target" in
  linux-amd64) goos=linux; goarch=amd64 ;;
  linux-arm64) goos=linux; goarch=arm64 ;;
  *) echo "target nashenakhte: $target" >&2; exit 2 ;;
esac

command -v go >/dev/null 2>&1 || { echo "go toolchain lazem ast." >&2; exit 1; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

git clone -q "$BACKHAUL_UPSTREAM_REPO" "$tmp/src"
git -C "$tmp/src" checkout -q "$BACKHAUL_UPSTREAM_REV"
actual_rev="$(git -C "$tmp/src" rev-parse HEAD)"
[ "$actual_rev" = "$BACKHAUL_UPSTREAM_REV" ] || {
  echo "commit-e upstream motabegh nist: $actual_rev != $BACKHAUL_UPSTREAM_REV" >&2
  exit 1
}

for patch in "$ROOT"/core-backhaul/patches/*.patch; do
  git -C "$tmp/src" apply --check "$patch"
  git -C "$tmp/src" apply "$patch"
done

# utls ba version-e PIN-shode ezafe mishavad (patch faghat file-haye .go ra dast mizanad ta
# shekanande-ye go.sum nabashad). GOFLAGS=-mod=mod ta go get dar CI ham kar konad.
( cd "$tmp/src" && GOFLAGS=-mod=mod go get "github.com/refraction-networking/utls@$BACKHAUL_UTLS_VERSION" && GOFLAGS=-mod=mod go mod tidy )

# test-e regression-e patch (ke ALPN dorost mahdood shode va utls-e vaghei seda mishavad)
( cd "$tmp/src" && go vet ./internal/client/transport/ )

# CGO_ENABLED=0: binary-e static va ghabel-e cross-build bedoon-e toolchain-e C.
# v0.6.5 package-e main ra dar RISHE darad (cmd/ yek library ast) — pas '.' build mishavad.
( cd "$tmp/src" && CGO_ENABLED=0 GOOS="$goos" GOARCH="$goarch" \
    go build -trimpath -ldflags "-s -w" -o "$tmp/backhaul" . )

binary="$tmp/backhaul"
[ -s "$binary" ] || { echo "binary-e core sakhte nashod" >&2; exit 1; }

# ---- barresi-ha: bayad VAGHEAN utls dashte bashad va patch eemal shode bashad ----
go version -m "$binary" | grep -qF "github.com/refraction-networking/utls" || {
  echo "utls dar binary link nashode — patch eemal nashod?" >&2
  exit 1
}
# baraye target-e hamin mashin، ejra-pazir budan va version ra ham check kon
if [ "$goarch" = "$(go env GOHOSTARCH)" ] && [ "$goos" = "$(go env GOHOSTOS)" ]; then
  chmod +x "$binary"
  ver_out="$("$binary" -v 2>&1 | head -1)"
  [ "$ver_out" = "$BACKHAUL_UPSTREAM_TAG" ] || {
    echo "version-e core motabegh nist: got='$ver_out' expected='$BACKHAUL_UPSTREAM_TAG'" >&2
    exit 1
  }
fi

mkdir -p "$output_dir"
install -m 0755 "$binary" "$output_dir/backhaul"
echo "ok - backhaul core $BACKHAUL_ENGINE_VERSION baraye $target sakhte shod (utls $BACKHAUL_UTLS_VERSION)"
