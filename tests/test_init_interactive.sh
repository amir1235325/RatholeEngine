#!/usr/bin/env bash
# regression: nasb-e TAAMOLI-ye panel bayad betavanad domain ra beporsad.
#
# bug: `install-panel.sh` tty ra dorost peyda mikonad (TTY_DEV) vali `ratholectl` yek process-e
# JODAst ke tty ra AZ NO tashkhis midahad. zir-e `curl|bash` stdin-e ma pipe ast، pas `init`
# hich rahi baraye porsidan nadasht va ba «bedoon-e domain momken nist» mimord — HATTA vaghti
# karbar VAGHEAN posht-e terminal neshaste bood. alamat: «[!] init shekast khord».
set -uo pipefail

ok(){ echo "ok - $*"; }
fail(){ echo "not ok - $*" >&2; exit 1; }

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
P="$REPO_ROOT/rathole-manager/install-panel.sh"

# ---- 1: init-e taamoli bayad stdin ra be TTY_DEV vasl konad ----
grep -qF 'ratholectl init < "$TTY_DEV"' "$P" \
  || fail "install-panel.sh tty ra be 'ratholectl init'-e taamoli vasl nemikonad — init nemitavanad beporsad"
ok "init-e taamoli stdin-e khod ra az TTY_DEV migirad"

# ---- 2: masir-e ghayr-taamoli (ba flag) nabayad avaz shode bashad ----
grep -qF 'ratholectl init "${INIT_ARGS[@]}"' "$P" \
  || fail "masir-e ghayr-taamoli (--domain ...) az beyn rafte"
ok "masir-e ghayr-taamoli (--domain ...) dast-nakhorde ast"

# ---- 3: raftar-e vaghei rooye pty — karbar domain tayp mikonad ----
command -v script >/dev/null 2>&1 || { echo "1..0 # skip 'script' nist"; exit 0; }
command -v jq >/dev/null 2>&1 || { echo "1..0 # skip jq nist"; exit 0; }

TEST_TMP_ROOT="${TEST_TMP_ROOT:-${TMPDIR:-/tmp}}"
D="$(mktemp -d "${TEST_TMP_ROOT%/}/test-initpty.XXXXXX")"; trap 'rm -rf "$D"' EXIT INT TERM

# ratholectl-e sandbox-shode (bedoon-e root/systemd/nginx)
sed -e "s#^STATE=.*#STATE=\"$D/state.json\"#" \
    -e "s#^SERVER_TOML=.*#SERVER_TOML=\"$D/server.toml\"#" \
    -e "s#^NGINX_CONF=.*#NGINX_CONF=\"$D/rathole.conf\"#" \
    -e 's/\r$//' "$REPO_ROOT/rathole-manager/ratholectl" > "$D/ratholectl"
chmod +x "$D/ratholectl"
mkdir -p "$D/share"
sed 's/\r$//' "$REPO_ROOT/rathole-manager/common.sh" > "$D/common.sh"
# need_root/systemctl/nginx ra khonsa kon
mkdir -p "$D/bin"
for c in systemctl nginx certbot; do printf '#!/bin/sh\nexit 0\n' > "$D/bin/$c"; chmod +x "$D/bin/$c"; done
printf '#!/bin/sh\nexit 0\n' > "$D/bin/id"; chmod +x "$D/bin/id"   # id -u → 0? na: bebin zir

# ratholectl need_root ra az common.sh migirad؛ RATHOLE_TEST_ROOT ra nadarad، pas ba fakeroot-e
# sabok: PATH-e id ra avaz nemikonim (khatarnak) — be jash ejra ba subshell-i ke need_root ra
# override mikonad. az RATHOLECTL_LIB_ONLY estefade mikonim ta cmd_init ra mostaghim seda konim.
cat > "$D/run.sh" <<EOF
set -uo pipefail
export PATH="$D/bin:\$PATH"
export RATHOLECTL_LIB_ONLY=1
STATE="$D/state.json"; SERVER_TOML="$D/server.toml"; NGINX_CONF="$D/rathole.conf"
source "$D/ratholectl"
need_root(){ :; }
regenerate(){ echo "REGENERATE-CALLED"; }
cmd_init
EOF

# tartib-e soal-ha: AVVAL «file-e backup baraye restore» (khali = nasb-e taze)، BAAD domain،
# baad baghi ke hameh pishfarz darand (+ porsesh-e certbot chon cert-e pishfarz vojood nadarad).
# HAMEYE khat-ha YEKJA ferestade mishavand — NA ba sleep. tty dar halat-e canonical har `read`
# ra faghat YEK khat midahad، pas in ghati ast؛ noskhe-ye sleep-dar zir-e bar flaky bood.
INPUT="$D/input.txt"
{ printf '\n'; printf 'pty.example\n'; for _ in 1 2 3 4 5 6 7 8 9; do printf '\n'; done; } > "$INPUT"
out="$(script -qec "bash $D/run.sh" /dev/null < "$INPUT" 2>&1 | tr -d '\r')"
printf '%s' "$out" | grep -q 'damnh (masalan' || { printf '%s\n' "$out" >&2; fail "prompt-e domain chap nashod"; }
[ -f "$D/state.json" ] || { printf '%s\n' "$out" >&2; fail "state.json sakhte nashod — init nemitavanad beporsad"; }
got="$(jq -r '.domain' "$D/state.json" 2>/dev/null)"
[ "$got" = "pty.example" ] || fail "domain-e tayp-shode zabt nashod (got='$got')"
ok "rooye pty: domain porside shod va dar state zakhire shod"

echo "hameye test-haye init-e taamoli pas shodand."
