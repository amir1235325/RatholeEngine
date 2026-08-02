#!/usr/bin/env bash
# regression: porsesh-haye taamoli-ye nasb nabayad HARGEZ ta abad gir konand.
#
# bug-e asli: `read -rp` rooye stdin-e GHEYR-terminal ke hanooz baste nashode (curl|bash ba
# link-e kond/filter-shode، kanal-e SSH، hub) TA ABAD montazer mimanad — va bash prompt ra ham
# chap NEMIKONAD (prompt-e `read -p` faghat baraye vorodi-ye terminal neveshte mishavad).
# natije: nasb dar marhale-ye «tanzimat avlih (init)» bi-hich payami saat-ha motevaghef mishod.
# hamchenin `[ -r /dev/tty ]` DOROGH migoyad: hatta bedoon-e controlling terminal TRUE ast.
set -uo pipefail

ok(){ echo "ok - $*"; }
fail(){ echo "not ok - $*" >&2; exit 1; }

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
TEST_TMP_ROOT="${TEST_TMP_ROOT:-${TMPDIR:-/tmp}}"
D="$(mktemp -d "${TEST_TMP_ROOT%/}/test-tty.XXXXXX")"; trap 'rm -rf "$D"' EXIT INT TERM

command -v mkfifo >/dev/null 2>&1 || { echo "1..0 # skip mkfifo nist"; exit 0; }
command -v timeout >/dev/null 2>&1 || { echo "1..0 # skip timeout nist"; exit 0; }

# stdin-e «baz vali bi-kar»: FIFO ra baz negah midarim va hichi nemnevisim.
FIFO="$D/stdin.fifo"; mkfifo "$FIFO"
exec 8<>"$FIFO"

# har script yek helper-e porsesh darad; block-e vaghei ra az khod-e file barmidarim ta test
# ba noskhe-ye zende hamgam bemanad (na ba copy-e bayat).
extract(){ # $1=file $2=start-regex $3=end-regex
  sed -n "/$2/,/$3/p" "$1" | sed 's/\r$//'
}

check(){ # $1=label $2=script-file-ba-helper $3=farakhani $4=setsid|ctty
  local label="$1" helper="$2" call="$3" mode="$4" pre=() out
  cp "$helper" "$D/run.sh"
  printf '%s\necho REACHED_END\n' "$call" >> "$D/run.sh"
  [ "$mode" = setsid ] && pre=(setsid -w)
  out="$(RTH_READ_TIMEOUT=3 timeout 20 "${pre[@]}" bash "$D/run.sh" <"$FIFO" 2>&1)"
  printf '%s' "$out" | grep -q REACHED_END \
    || fail "$label [$mode]: bedoon-e javab gir kard (hang) — nasb motevaghef mishavad"
  ok "$label [$mode]: gir nakard"
}

# --- install-panel.sh (mostaghel، ghabl az nasb-e common.sh ejra mishavad) ---
extract "$REPO_ROOT/rathole-manager/install-panel.sh" '^TTY_DEV=""' '^ask_yn()' > "$D/panel.sh"
grep -q 'ask_yn()' "$D/panel.sh" || fail "helper-e porsesh dar install-panel.sh peyda nashod"
check "install-panel.sh/ask_yn" "$D/panel.sh" 'ask_yn "tst?" || true' setsid
check "install-panel.sh/ask_yn" "$D/panel.sh" 'ask_yn "tst?" || true' ctty

# --- common.sh (manba-e moshtarak-e ratholectl/ratholenode) ---
{ printf 'die(){ echo "$*" >&2; exit 1; }\nc_r(){ printf %%s "$*"; }\nc_g(){ printf %%s "$*"; }\nc_y(){ printf %%s "$*"; }\n'
  printf 'log(){ :; }\nwarn(){ :; }\nerr(){ :; }\n'
  extract "$REPO_ROOT/rathole-manager/common.sh" '^RTH_TTY=""' '^ask_yn()'
} > "$D/common-helper.sh"
grep -q 'rth_read()' "$D/common-helper.sh" || fail "rth_read dar common.sh peyda nashod"
check "common.sh/rth_read"  "$D/common-helper.sh" 'rth_read v "tst: "; echo "v=[$v]"' setsid
check "common.sh/rth_read"  "$D/common-helper.sh" 'rth_read v "tst: "; echo "v=[$v]"' ctty
check "common.sh/ask_yn"    "$D/common-helper.sh" 'ask_yn "tst?" || true' setsid

# --- bedoon-e tty javab bayad «na» bashad (pishfarz-e amn baraye porsesh-e makhrab) ---
cp "$D/common-helper.sh" "$D/run.sh"
printf 'ask_yn "hazf shavad?" && echo ANSWER=YES || echo ANSWER=NO\n' >> "$D/run.sh"
res="$(RTH_READ_TIMEOUT=3 timeout 20 setsid -w bash "$D/run.sh" <"$FIFO" 2>&1)"
printf '%s' "$res" | grep -q 'ANSWER=NO' || fail "bedoon-e tty javab bayad 'na' bashad, na: $res"
ok "bedoon-e tty javab-e ask_yn 'na' ast (pishfarz-e amn)"

# --- `[ -r /dev/tty ]` nabayad be onvane shakhes-e tty estefade shavad (DOROGH migoyad) ---
for f in rathole-manager/common.sh rathole-manager/install-panel.sh rathole-manager/ratholectl \
         rathole-manager/ratholehub/install-hub.sh rathole-manager/uninstall-panel.sh \
         rathole-manager/uninstall-node.sh bootstrap.sh; do
  # faghat KOD — khat-haye tozihi (ke in bug ra sharh midahand) rad mishavand.
  ! grep -v '^[[:space:]]*#' "$REPO_ROOT/$f" | grep -q -- '-r /dev/tty' \
    || fail "$f hanooz az '[ -r /dev/tty ]' estefade mikonad (hatta bedoon-e ctty TRUE ast)"
done
ok "hich script az shakhes-e ghalat '[ -r /dev/tty ]' estefade nemikonad"

exec 8>&-
echo "hameye test-haye tty-prompt pas shodand."
