#!/usr/bin/env bash
# ghar-dad-e patch-e core-e backhaul: bayad rooye rev-e PIN-shode tamiz eemal shavad va
# natije-ash HAMAN chizi bashad ke entezar darim (uTLS + ALPN-e mahdood + hazf-e crypto/tls).
#
# CHERA in test: agar upstream file/khat ra jabeja konad، `git apply` sakhtegi shekast mikhorad
# va bayad SARIH befahmim — na inke release yek binary-e BEDOON-e patch (asar-angosht-e Go)
# montasher konad va kasi motevajeh nashavad.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../core-backhaul/upstream.env
source "$ROOT/core-backhaul/upstream.env"

command -v git >/dev/null 2>&1 || { echo "1..0 # skip git nist"; exit 0; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

git clone -q "$BACKHAUL_UPSTREAM_REPO" "$tmp/src"
git -C "$tmp/src" checkout -q "$BACKHAUL_UPSTREAM_REV"

# rev-e PIN-shode bayad haman tag-e elam-shode bashad (jelogiri az drift-e bi-seda)
tag_rev="$(git -C "$tmp/src" rev-parse "$BACKHAUL_UPSTREAM_TAG^{}")"
[ "$tag_rev" = "$BACKHAUL_UPSTREAM_REV" ] || {
  echo "not ok - rev-e PIN-shode ba $BACKHAUL_UPSTREAM_TAG yeki nist ($tag_rev)" >&2; exit 1; }

# ---- ghabl az patch: upstream VAGHEAN crypto/tls-e bedoon-e asar-angosht darad ----
grep -qF 'InsecureSkipVerify: true' "$tmp/src/internal/client/transport/shared.go" \
  || { echo "not ok - farz-e patch (InsecureSkipVerify) dar upstream nist" >&2; exit 1; }
# upstream az ghabl User-Agent-e morurgar mifrestad — pas patch-e ma faghat lazem ast baraye
# asar-angosht-e TLS، na hedar-ha. agar in az beyn beravad bayad befahmim.
grep -qF 'headers.Add("User-Agent"' "$tmp/src/internal/client/transport/shared.go" \
  || { echo "not ok - upstream dige User-Agent nemifrestad (farz-e ma avaz shode)" >&2; exit 1; }

# ---- patch bayad tamiz eemal shavad ----
for patch in "$ROOT"/core-backhaul/patches/*.patch; do
  git -C "$tmp/src" apply --check "$patch" \
    || { echo "not ok - patch tamiz eemal nemishavad: $(basename "$patch")" >&2; exit 1; }
  git -C "$tmp/src" apply "$patch"
done

S="$tmp/src/internal/client/transport/shared.go"
U="$tmp/src/internal/client/transport/utls.go"

# ---- baad az patch: ghar-dad ----
[ -f "$U" ] || { echo "not ok - utls.go sakhte nashod" >&2; exit 1; }
grep -qF 'utls.HelloChrome_Auto' "$U" || { echo "not ok - profile-e Chrome estefade nashode" >&2; exit 1; }
grep -qF 'InsecureSkipVerify: true' "$U" || { echo "not ok - raftar-e upstream (verify nakardan) hefz nashode" >&2; exit 1; }
# ALPN bayad be http/1.1 mahdood shavad vagarna server HTTP/2 mozakere mikonad va
# WebSocket-e HTTP/1.1-e Upgrade mishkanad ("bogus greeting" / "malformed HTTP response").
grep -qF '"http/1.1"' "$U" || { echo "not ok - ALPN be http/1.1 mahdood nashode" >&2; exit 1; }
grep -qF 'ALPNExtension' "$U" || { echo "not ok - extension-e ALPN eslah nashode" >&2; exit 1; }

# masir-e WSS bayad az uTLS obur konad، na az TLS-e dakheli-ye gorilla
grep -qF 'NetDialTLSContext' "$S" || { echo "not ok - WSS hanooz az TLS-e gorilla estefade mikonad" >&2; exit 1; }
grep -qF 'uTLSHandshake' "$S" || { echo "not ok - uTLSHandshake seda nemishavad" >&2; exit 1; }
grep -qF 'crypto/tls' "$S" && { echo "not ok - crypto/tls hanooz import shode (bayad hazf shavad)" >&2; exit 1; }

# masir-e ws/wsmux (bedoon-e TLS) NABAYAD dast bekhorad
grep -qF 'wsURL = fmt.Sprintf("ws://%s%s", addr, path)' "$S" \
  || { echo "not ok - masir-e ws-e bedoon-e TLS taghir karde" >&2; exit 1; }

# ---- build.sh bayad har do target va barresi-ha ra dashte bashad ----
grep -qF 'CGO_ENABLED=0' "$ROOT/core-backhaul/build.sh" || { echo "not ok - build static nist" >&2; exit 1; }
grep -qF 'refraction-networking/utls' "$ROOT/core-backhaul/build.sh" || { echo "not ok - build utls ra check nemikonad" >&2; exit 1; }
grep -qF 'rev-parse HEAD' "$ROOT/core-backhaul/build.sh" || { echo "not ok - build rev ra tayid nemikonad" >&2; exit 1; }

# ---- install_backhaul bayad core-e mahalli ra TARJIH dahad ----
grep -qF 'install_backhaul_core' "$ROOT/rathole-manager/common.sh" || { echo "not ok - install_backhaul_core nist" >&2; exit 1; }
grep -qF 'sha256sum -c SHA256SUMS' "$ROOT/rathole-manager/common.sh" || { echo "not ok - core bedoon-e checksum nasb mishavad" >&2; exit 1; }

echo 'ok - ghar-dad-e patch-e core-e backhaul bargharar ast'
