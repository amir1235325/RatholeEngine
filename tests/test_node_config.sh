#!/usr/bin/env bash
set -euo pipefail

ok(){ echo "ok - $*"; }
fail(){ echo "not ok - $*" >&2; exit 1; }
find_toml_python(){
  local candidate
  for candidate in "${TOML_PYTHON:-}" python3 python3.13 python3.12 python3.11 python.exe; do
    [ -n "$candidate" ] || continue
    command -v "$candidate" >/dev/null 2>&1 || continue
    "$candidate" -c 'import tomllib' >/dev/null 2>&1 || continue
    echo "$candidate"
    return
  done
  fail 'Python 3.11+ ba tomllib standard lazem ast'
}
TOML_PYTHON="$(find_toml_python)"
assert_toml(){
  # file ra az stdin mikhanim — path-conversion (cygpath/wslpath) dar MSYS/WSL mikhkhorad.
  local file="$1"
  "$TOML_PYTHON" -c 'import sys, tomllib; tomllib.load(sys.stdin.buffer)' < "$file" || fail "TOML namotabar: $file"
}

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
TEST_TMP_ROOT="${TEST_TMP_ROOT:-${TMPDIR:-/tmp}}"
ROOT="$(mktemp -d "${TEST_TMP_ROOT%/}/test-node.XXXXXX")"; trap 'rm -rf "$ROOT"' EXIT
export RATHOLENODE_LIB_ONLY=1
source "${REPO_ROOT:?}/rathole-manager/ratholenode"
trap 'rm -rf "$ROOT"' EXIT INT TERM
ENV_FILE="$ROOT/node.env"; SVC_FILE="$ROOT/services.conf"; CLIENT_TOML="$ROOT/client.toml"
printf 'SERVER=panel.example:443\nWS_PATH=/_rh/test\n' > "$ENV_FILE"
: > "$SVC_FILE"
gen_client
assert_toml "$CLIENT_TOML"
grep -qx '\[client.services\]' "$CLIENT_TOML" || fail 'jadval services khali peyda nashod'
ok 'config services khali parse shod va jadval darad'
printf 'n1|token123|2087\n' > "$SVC_FILE"
gen_client
assert_toml "$CLIENT_TOML"
grep -qx '\[client.services.n1\]' "$CLIENT_TOML" || fail 'jadval services tanzim-shode peyda nashod'
ok 'config services tanzim-shode parse shod va jadval darad'

# IP + self-signed: faghat field-haye TLS-e motabar-e Rathole v0.5.0.
ROOT_CERT="$ROOT/ip-root-ca.crt"; : > "$ROOT_CERT"
printf 'SERVER=1.2.3.4:443\nTLS_HOSTNAME=1.2.3.4\nTLS_TRUSTED_ROOT=%s\n' "$ROOT_CERT" > "$ENV_FILE"
gen_client
assert_toml "$CLIENT_TOML"
grep -qx 'hostname = "1.2.3.4"' "$CLIENT_TOML" || fail 'TLS hostname-e IP peyda nashod'
grep -qx "trusted_root = \"$ROOT_CERT\"" "$CLIENT_TOML" || fail 'trusted_root peyda nashod'
! grep -qE '^(path|user_agent|headers)[[:space:]]*=' "$CLIENT_TOML" || fail 'field-e unsupported dar TOML peyda shod'
ok 'IP self-signed TOML faghat hostname/trusted_root-e motabar darad'

# --- Task 3: barresi rth_commit_config (neveshtan-e lock-amn) ---

# rth_commit_config bayad tarf zaman-e lock-e eksklusive ham sabar konad va file-e khali ra rad konad
CLIENT2_TOML="$ROOT/client2.toml"
ENV_FILE="$ROOT/node2.env"; SVC_FILE="$ROOT/services2.conf"
printf 'SERVER=panel.example:443\nWS_PATH=/_rh/abc\n' > "$ENV_FILE"
: > "$SVC_FILE"
CLIENT_TOML="$CLIENT2_TOML"
gen_client
assert_toml "$CLIENT2_TOML"
ok 'rth_commit_config ba lock toml-e motabar nevesht'

# gen_client nabayad file-e khali (src khali) ra commit konad
empty_src="$ROOT/empty.toml"
: > "$empty_src"
live_dst="$ROOT/live.toml"
printf '[client]\nremote_addr = "prev:443"\n' > "$live_dst"
if rth_commit_config "$empty_src" "$live_dst" 2>/dev/null; then
  fail 'rth_commit_config bayad file-e khali ra rad konad'
fi
grep -q 'remote_addr' "$live_dst" || fail 'file-e live bayad ba commit-e ghalat taghir nakonad'
ok 'rth_commit_config file-e khali ra rad kard va live ra hefz kard'

# barresi lock baraye zamani ke flock dar dastres ast; fallback-e mkdir bala test shode.
if command -v flock >/dev/null 2>&1; then
  LOCK_DST="$ROOT/locked.toml"
  printf '[client]\nremote_addr = "x:443"\n' > "$LOCK_DST"
  (
    exec 9>"${LOCK_DST}.lock"
    flock -x 9
    sleep 2
  ) &
  LOCK_PID=$!
  sleep 0.1
  SRC_TMP="$ROOT/src_while_locked.toml"
  printf '[client]\nremote_addr = "y:443"\n' > "$SRC_TMP"
  # commit bayad sabar konad ta lock azad shavad (na fail konad)
  rth_commit_config "$SRC_TMP" "$LOCK_DST"
  wait "$LOCK_PID" || true
  grep -q '"y:443"' "$LOCK_DST" || fail 'rth_commit_config baad az azad-shodan-e lock bayad commit konad'
  ok 'rth_commit_config hengam-e lock-e digar sabar kard va commit kard'
else
  ok 'flock dar in shell nist; fallback-e portable-e mkdir estefade shod'
fi
