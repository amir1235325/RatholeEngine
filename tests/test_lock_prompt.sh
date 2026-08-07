#!/usr/bin/env bash
# ghofl-e state nabayad hengam-e entezar baraye tayp-e karbar negah dashte shavad.
# regression: `ratholectl menu`/`init` kol-e halghe-ye taamoli ra zir-e ghofl negah midasht,
# pas har ratholectl-e digar 30s gir mikard va baad BI-GHOFL edame midad.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
pass=0; fail=0
ok(){ echo "  ok  - $1"; pass=$((pass+1)); }
no(){ echo "  FAIL- $1"; fail=$((fail+1)); }

TD="$(mktemp -d)"; trap 'rm -rf "$TD"' EXIT
LOCK="$TD/l"

# hamsan-e rth_with_lock + rth_read-e vaghei (faghat bakhsh-e ghofl).
cat >"$TD/lib.sh" <<'EOF'
warn(){ echo "[*] $*" >&2; }
RTH_LOCK_HELD=0
rth_lock_pause(){ if [ "${RTH_LOCK_HELD:-0}" = 1 ]; then flock -u 9 2>/dev/null || true; fi; }
rth_lock_resume(){ if [ "${RTH_LOCK_HELD:-0}" = 1 ]; then
  flock -w 30 9 2>/dev/null || warn "ghofl-e state pas az javab azad nashod (30s); edame midaham."; fi; }
with_lock(){
  { exec 9>"$LOCK"; } 2>/dev/null || { "$@"; return $?; }
  if flock -w 3 9; then RTH_LOCK_HELD=1; else warn "ghofl-e state azad nashod (30s); edame midaham."; fi
  "$@"; local rc=$?
  RTH_LOCK_HELD=0; exec 9>&-; return $rc
}
EOF

# A: montazer-e karbar (prompt) — 4s. B: yek mutator-e kootah.
( LOCK="$LOCK"; . "$TD/lib.sh"
  prompt(){ rth_lock_pause; sleep 4; rth_lock_resume; }
  with_lock prompt ) & apid=$!
sleep 0.7
start=$(date +%s)
outB="$( LOCK="$LOCK"; . "$TD/lib.sh"; m(){ echo ran; }; with_lock m 2>&1 )"
el=$(( $(date +%s) - start ))
wait "$apid" 2>/dev/null

[ "$el" -lt 3 ] && ok "mutator hengam-e prompt-e A gir nakard (${el}s)" \
                || no "mutator ${el}s gir kard — ghofl hanooz zir-e prompt negah dashte mishavad"
case "$outB" in *"azad nashod"*) no "hoshdar-e timeout-e ghofl chap shod: $outB";;
                *) ok "hich hoshdar-e timeout-i chap nashod";; esac
case "$outB" in *ran*) ok "mutator ejra shod";; *) no "mutator ejra nashod";; esac

# bedoon-e pause (raftar-e ghadimi) BAYAD gir konad — yaani test vaghean chizi ra misanjad.
( LOCK="$LOCK"; . "$TD/lib.sh"
  hold(){ sleep 4; } ; with_lock hold ) & hpid=$!
sleep 0.7
s2=$(date +%s)
( LOCK="$LOCK"; . "$TD/lib.sh"; m(){ :; }; with_lock m ) >/dev/null 2>&1
e2=$(( $(date +%s) - s2 ))
wait "$hpid" 2>/dev/null
[ "$e2" -ge 3 ] && ok "control: bedoon-e pause vaghean gir mikonad (${e2}s)" \
                || no "control gir nakard (${e2}s) — test bi-maani ast"

# ghofl bayad dar har do fayl hamahang bashad.
grep -q 'rth_lock_pause' rathole-manager/common.sh && ok "rth_read ghofl ra pause mikonad" \
  || no "rth_read pause nadarad"
grep -q 'RTH_LOCK_HELD=1' rathole-manager/ratholectl && ok "ratholectl RTH_LOCK_HELD ra set mikonad" \
  || no "ratholectl RTH_LOCK_HELD ra set nemikonad (pause bi-asar mishavad)"

echo "  --> pass=$pass fail=$fail"
[ "$fail" -eq 0 ]
