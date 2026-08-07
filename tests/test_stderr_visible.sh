#!/usr/bin/env bash
# regression: khata-haye ratholectl/ratholenode bayad be karbar BERESAND.
#
# bug-e asli: `exec 9>"$RTH_LOCK" 2>/dev/null` — `exec`-e bedoon-e command redirect ra DAEMI
# mikonad، pas stderr-e KOL-e process be /dev/null miraft va hameye err/die BI-SEDA gom
# mishodand. alamat: `install-panel.sh` faghat «init shekast khord» chap mikard va rahnama-ye
# «ba --domain ejra kon» — ke daghighan hamon chizi bood ke karbar be an niaz dasht — nadide
# gom mishod. (ta vaghti has_tty DOROGH migoft، in masir-e khata aslan ejra nemishod.)
set -uo pipefail

ok(){ echo "ok - $*"; }
fail(){ echo "not ok - $*" >&2; exit 1; }

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
TEST_TMP_ROOT="${TEST_TMP_ROOT:-${TMPDIR:-/tmp}}"
D="$(mktemp -d "${TEST_TMP_ROOT%/}/test-stderr.XXXXXX")"; trap 'rm -rf "$D"' EXIT INT TERM

# ---- 1: hich script nabayad `exec <fd>>file 2>/dev/null` dashte bashad ----
# (redirect-e daemi. shekl-e dorost: `{ exec 9>file; } 2>/dev/null`)
for f in rathole-manager/ratholectl rathole-manager/ratholenode rathole-manager/common.sh; do
  if grep -nE '^[^#]*\bexec [0-9]+>[^;]*2>/dev/null' "$REPO_ROOT/$f" | grep -qv '{ exec'; then
    grep -nE '^[^#]*\bexec [0-9]+>[^;]*2>/dev/null' "$REPO_ROOT/$f" >&2
    fail "$f: 'exec N>file 2>/dev/null' stderr-e kol-e process ra khafe mikonad"
  fi
done
ok "hich ja redirect-e daemi-ye stderr rooye exec nist"

# ---- 2: raftar-e vaghei — ghofl gerefte shavad VALI stderr salem bemanad ----
# tabe-e ghofl ra az khod-e file barmidarim ta test ba noskhe-ye zende hamgam bemanad.
extract_lock(){ sed -n '/^RTH_LOCK=/,/^}/p' "$REPO_ROOT/$1"; }

for cli in ratholectl ratholenode; do
  cat > "$D/probe.sh" <<EOF
set -uo pipefail
warn(){ printf '%s\n' "WARN:\$*" >&2; }
$(extract_lock "rathole-manager/$cli")
boom(){ echo "STDOUT-MARKER"; echo "STDERR-MARKER" >&2; return 7; }
RTH_LOCK="$D/probe.lock"
rth_with_lock boom
echo "rc=\$?"
EOF
  out="$(bash "$D/probe.sh" 2>"$D/err.txt")"
  err="$(cat "$D/err.txt")"
  printf '%s' "$out" | grep -q 'STDOUT-MARKER' || fail "$cli: stdout gom shod"
  printf '%s' "$out" | grep -q 'rc=7'          || fail "$cli: exit code-e tabe hefz nashod"
  printf '%s' "$err" | grep -q 'STDERR-MARKER' \
    || fail "$cli: STDERR khafe shod — karbar payam-e khata ra nemibinad"
  ok "$cli: rth_with_lock stderr ra hefz mikonad (va rc ra pas midahad)"
done

# ---- 3: fd-e ghofl bayad VAGHEAN gerefte shavad (fix nabayad ghofl ra kharab konad) ----
cat > "$D/lockprobe.sh" <<EOF
set -uo pipefail
warn(){ :; }
$(extract_lock "rathole-manager/ratholectl")
RTH_LOCK="$D/l2.lock"
check(){ [ -e /proc/self/fd/9 ] && echo "FD9-OPEN" || echo "FD9-MISSING"; }
rth_with_lock check
EOF
if [ -d /proc/self/fd ]; then
  bash "$D/lockprobe.sh" 2>/dev/null | grep -q 'FD9-OPEN' \
    || fail "fd-e ghofl baz nashod — ghofl-e hamzamani az beyn rafte"
  ok "fd-e ghofl hamchenan baz mishavad (ghofl salem ast)"
fi

echo "hameye test-haye namayan-budan-e khata pas shodand."
