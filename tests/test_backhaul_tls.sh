#!/usr/bin/env bash
# backhaul: TLS-e self-signed dar halat-e direct-IP (bedoon-e nginx).
#
# ghaede: nginx_tls → nginx TLS ra terminate mikonad، pas server HATMAN bedoon-e TLS ast
# (ws/wsmux) va HARGEZ nabayad tls_cert benevisad. direct_ip → nginx dar masir nist، pas
# khod-e backhaul ba wss/wssmux TLS ra terminate mikonad va tls_cert/tls_key (ke backhaul
# baraye in transport-ha ELZAMI midanad) bayad az gvahi-ye `ratholectl ip-cert` biayad.
set -uo pipefail

ok(){ echo "ok - $*"; }
fail(){ echo "not ok - $*" >&2; exit 1; }

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
TEST_TMP_ROOT="${TEST_TMP_ROOT:-${TMPDIR:-/tmp}}"
command -v jq >/dev/null 2>&1 || { echo "1..0 # skip jq nist"; exit 0; }

D="$(mktemp -d "${TEST_TMP_ROOT%/}/test-bhtls.XXXXXX")"; trap 'rm -rf "$D"' EXIT INT TERM

export RATHOLECTL_LIB_ONLY=1
# shellcheck disable=SC1090
source "$REPO_ROOT/rathole-manager/ratholectl"
trap 'rm -rf "$D"' EXIT INT TERM

STATE="$D/state.json"
BH_TOML="$D/backhaul-server.toml"
# gvahi-ye saakhtegi (mohtava mohem nist — faghat vojood-e file check mishavad)
FC="$D/fullchain.pem"; KEY="$D/privkey.pem"
printf 'cert\n' > "$FC"; printf 'key\n' > "$KEY"

mkstate(){ # $1=transport $2=exposure $3=with_ip_tls(1|0)
  jq -n --arg tr "$1" --arg ex "$2" --arg fc "$FC" --arg key "$KEY" --argjson ip "$3" \
    '{domain:"d.example", nodes:[{name:"n1",port:1001,inbound_port:8443,token:"t",transport:"backhaul"}],
      backhaul_port:3080, backhaul_transport:$tr, backhaul_token:"deadbeef", backhaul_profile:"balanced",
      backhaul_exposure:$ex}
     + (if $ip==1 then {ip_tls:{ip:"1.2.3.4",fullchain:$fc,key:$key,self_signed:true}} else {} end)' \
    > "$STATE"
}

# ---- 1: nginx_tls + wsmux → bind roo-ye loopback، BEDOON-e tls_cert ----------------
mkstate wsmux nginx_tls 1
gen_backhaul_server_toml >/dev/null 2>&1
grep -q '^bind_addr = "127.0.0.1:3080"' "$BH_TOML" || fail "nginx_tls bayad roo-ye 127.0.0.1 bind konad"
! grep -q '^tls_cert' "$BH_TOML" || fail "nginx_tls nabayad tls_cert benevisad (TLS roo-ye nginx terminate mishavad)"
ok "nginx_tls: bind roo-ye 127.0.0.1 va bedoon-e tls_cert"

# ---- 2: direct_ip + wsmux (bedoon-e ramz) → bind-e omoomi، bedoon-e tls_cert -------
mkstate wsmux direct_ip 1
gen_backhaul_server_toml >/dev/null 2>&1
grep -q '^bind_addr = "0.0.0.0:3080"' "$BH_TOML" || fail "direct_ip bayad roo-ye 0.0.0.0 bind konad"
! grep -q '^tls_cert' "$BH_TOML" || fail "ws/wsmux TLS nadarad، nabayad tls_cert benevisad"
ok "direct_ip + wsmux: bind-e omoomi، bedoon-e tls_cert"

# ---- 3: direct_ip + wssmux → tls_cert/tls_key az ip-cert --------------------------
mkstate wssmux direct_ip 1
gen_backhaul_server_toml >/dev/null 2>&1
grep -q '^bind_addr = "0.0.0.0:3080"' "$BH_TOML" || fail "direct_ip bayad roo-ye 0.0.0.0 bind konad"
grep -q "^transport = \"wssmux\"" "$BH_TOML" || fail "transport bayad wssmux bemanad"
grep -q "^tls_cert = \"$FC\"" "$BH_TOML" || { cat "$BH_TOML" >&2; fail "tls_cert az ip-cert neveshte nashod"; }
grep -q "^tls_key = \"$KEY\"" "$BH_TOML"  || fail "tls_key az ip-cert neveshte nashod"
# kelid-e khosusi NABAYAD dar khod-e config copy shode bashad — faghat MASIR
! grep -q '^key$' "$BH_TOML" || fail "mohtava-ye kelid-e khosusi dar config nasht karde"
ok "direct_ip + wssmux: tls_cert/tls_key be gvahi-ye ip-cert eshare mikonand"

# ---- 4: direct_ip + wssmux BEDOON-e ip-cert → bayad die konad (na config-e naghes) --
mkstate wssmux direct_ip 0
rm -f "$BH_TOML"
if ( gen_backhaul_server_toml >/dev/null 2>&1 ); then
  fail "bedoon-e gvahi bayad die konad (backhaul tls_cert ra elzami midanad)"
fi
[ ! -s "$BH_TOML" ] || fail "config-e naghes (bedoon-e tls_cert) neveshte shod"
ok "bedoon-e ip-cert: die mikonad va config-e naghes namineveshtad"

# ---- 5: gvahi-ye gom-shode (state hast vali file nist) → die --------------------
mkstate wssmux direct_ip 1
rm -f "$FC" "$BH_TOML"
if ( gen_backhaul_server_toml >/dev/null 2>&1 ); then
  fail "gvahi-ye gom-shode bayad die konad"
fi
ok "gvahi-ye gom-shode roo-ye disk rad mishavad"

echo "hameye test-haye backhaul-TLS pas shodand."
