#!/usr/bin/env bash
# test_nginx_control_path.sh — task 4: barresi masir-e makhfi control-e WebSocket
set -euo pipefail

ok(){ echo "ok - $*"; }
fail(){ echo "not ok - $*" >&2; exit 1; }
REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
TEST_TMP_ROOT="${TEST_TMP_ROOT:-${TMPDIR:-/tmp}}"

# ---- 1: ensure_control_path: masir jadid ya az state ----------------------------
(
  TMP_DIR="$(mktemp -d "${TEST_TMP_ROOT}/.test-nginx.XXXXXX")"; TMP_STATE="$TMP_DIR/state.json"; trap 'rm -rf "$TMP_DIR"' EXIT
  printf '%s\n' '{"domain":"x.test","cert_fullchain":"/fc","cert_key":"/k","control_port":2333,"fake_port":8080,"sub_port":2096,"data_port_start":1001,"api_port_start":7001,"nodes":[]}' > "$TMP_STATE"

  export RATHOLECTL_LIB_ONLY=1
  source "$REPO_ROOT/rathole-manager/ratholectl"
  trap 'rm -rf "$TMP_DIR"' EXIT
  STATE="$TMP_STATE"
  NGINX_CONF="$TMP_DIR/rathole.conf"

  ensure_control_path > "$TMP_DIR/path.out"
  p="$(cat "$TMP_DIR/path.out")"
  echo "$p" | grep -qE '^/_rh/[0-9a-f]{32}$' || { echo "bad path: $p" >&2; exit 1; }
  ensure_control_path > "$TMP_DIR/path2.out"
  p2="$(cat "$TMP_DIR/path2.out")"
  [ "$p" = "$p2" ] || { echo "path taghir kard: $p -> $p2" >&2; exit 1; }
  echo "ok - ensure_control_path masir-e motabar sakhte va cache kard: $p"
)
ok "ensure_control_path yek path-e /_rh/<hex32> sakhte va dar state cache kard"

# ---- 2: WS_PATH-e ghadimi inert ast va CONTROL_PATH masir ra tazrigh mikonad --------
(
  export RATHOLENODE_LIB_ONLY=1
  ROOT2="$(mktemp -d)"; trap 'rm -rf "$ROOT2"' EXIT
  source "$REPO_ROOT/rathole-manager/ratholenode"
  trap 'rm -rf "$ROOT2"' EXIT
  ENV_FILE="$ROOT2/node.env"; SVC_FILE="$ROOT2/services.conf"; CLIENT_TOML="$ROOT2/client.toml"
  : > "$SVC_FILE"

  # (a) WS_PATH-e ghadimi hich asari nadarad (var-e morde)
  printf 'SERVER=panel.example:443\nWS_PATH=/_rh/aabbccddeeff00112233445566778899\n' > "$ENV_FILE"
  gen_client
  ! grep -q '^path = ' "$CLIENT_TOML" || {
    echo "WS_PATH-e ghadimi nabayad path tolid konad:" >&2; cat "$CLIENT_TOML" >&2; exit 1; }

  # (b) bedoon-e CONTROL_PATH → hich path (raftar-e pishfarz-e sazgar ba node-haye ghadimi)
  printf 'SERVER=panel.example:443\n' > "$ENV_FILE"
  gen_client
  ! grep -q '^path = ' "$CLIENT_TOML" || {
    echo "bedoon-e CONTROL_PATH nabayad path tolid shavad:" >&2; cat "$CLIENT_TOML" >&2; exit 1; }

  # (c) CONTROL_PATH=/ → hich path (ma'adel-e pishfarz)
  printf 'SERVER=panel.example:443\nCONTROL_PATH=/\n' > "$ENV_FILE"
  gen_client
  ! grep -q '^path = ' "$CLIENT_TOML" || {
    echo "CONTROL_PATH=/ nabayad path tolid konad:" >&2; cat "$CLIENT_TOML" >&2; exit 1; }

  # (d) CONTROL_PATH=/_rh/<hex> → path daghighan hamin miayad
  printf 'SERVER=panel.example:443\nCONTROL_PATH=/_rh/deadbeefdeadbeef0011223344556677\n' > "$ENV_FILE"
  gen_client
  grep -qF 'path = "/_rh/deadbeefdeadbeef0011223344556677"' "$CLIENT_TOML" || {
    echo "CONTROL_PATH be TOML tazrigh nashod:" >&2; cat "$CLIENT_TOML" >&2; exit 1; }
)
ok "client.toml: WS_PATH inert; path faghat vaghti CONTROL_PATH-e ghayr-'/' bashad miayad"

# ---- 3: generated nginx — domain + IP-SAN default cert ---------------------------
(
  TMP_DIR="$(mktemp -d "${TEST_TMP_ROOT%/}/test-nginx.XXXXXX")"; trap 'rm -rf "$TMP_DIR"' EXIT
  export RATHOLECTL_LIB_ONLY=1
  source "$REPO_ROOT/rathole-manager/ratholectl"
  trap 'rm -rf "$TMP_DIR"' EXIT

  STATE="$TMP_DIR/state.json"
  NGINX_CONF="$TMP_DIR/rathole.conf"
  STREAM_CONF="$TMP_DIR/stream/rathole-stream.conf"
  fc="$TMP_DIR/domain.crt"; key="$TMP_DIR/domain.key"
  ipfc="$TMP_DIR/ip.crt"; ipkey="$TMP_DIR/ip.key"
  : > "$fc"; : > "$key"; : > "$ipfc"; : > "$ipkey"
  jq -n --arg fc "$fc" --arg key "$key" --arg ifc "$ipfc" --arg ikey "$ipkey" \
    '{domain:"x.test",cert_fullchain:$fc,cert_key:$key,control_port:2333,
      control_path:"/_rh/deadbeefdeadbeef0011223344556677",fake_port:8080,sub_port:2096,
      data_port_start:1001,api_port_start:7001,nodes:[],
      ip_tls:{ip:"1.2.3.4",fullchain:$ifc,key:$ikey,self_signed:true}}' > "$STATE"
  gen_nginx_conf

  [ "$(grep -c 'listen 443 ssl http2 default_server;' "$NGINX_CONF")" -eq 1 ] || fail "IP TLS default_server-e yagane nist"
  grep -qF "ssl_certificate     $ipfc;" "$NGINX_CONF" || fail "cert-e IP dar block-e default nist"
  grep -qF "server_name x.test;" "$NGINX_CONF" || fail "domain-e asli az config hazf shode"
  grep -qF "ssl_certificate     $fc;" "$NGINX_CONF" || fail "cert-e omoomi-ye domain hefz nashode"
  [ "$(grep -c 'location = /_rh/deadbeefdeadbeef0011223344556677' "$NGINX_CONF")" -eq 2 ] || fail "control path dar har do vhost nist"
)
ok "nginx-e generated cert-e IP ra default va cert-e domain ra SNI-specific negah midarad"

# ---- 4: game/SNI — 443 stream default -> internal IP TLS -------------------------
(
  TMP_DIR="$(mktemp -d "${TEST_TMP_ROOT%/}/test-nginx.XXXXXX")"; trap 'rm -rf "$TMP_DIR"' EXIT
  export RATHOLECTL_LIB_ONLY=1
  source "$REPO_ROOT/rathole-manager/ratholectl"
  trap 'rm -rf "$TMP_DIR"' EXIT

  STATE="$TMP_DIR/state.json"
  NGINX_CONF="$TMP_DIR/rathole.conf"
  STREAM_CONF="$TMP_DIR/stream/rathole-stream.conf"
  fc="$TMP_DIR/domain.crt"; key="$TMP_DIR/domain.key"
  ipfc="$TMP_DIR/ip.crt"; ipkey="$TMP_DIR/ip.key"
  : > "$fc"; : > "$key"; : > "$ipfc"; : > "$ipkey"
  ensure_stream_include(){ :; }
  jq -n --arg fc "$fc" --arg key "$key" --arg ifc "$ipfc" --arg ikey "$ipkey" \
    '{domain:"x.test",cert_fullchain:$fc,cert_key:$key,control_port:2333,
      control_path:"/_rh/deadbeefdeadbeef0011223344556677",fake_port:8080,sub_port:2096,
      internal_port:8443,data_port_start:1001,api_port_start:7001,
      nodes:[{name:"game",port:1001,inbound_port:443,token:"t",sni:"game.test"}],
      ip_tls:{ip:"1.2.3.4",fullchain:$ifc,key:$ikey,self_signed:true}}' > "$STATE"
  gen_nginx_conf

  grep -qF 'listen 127.0.0.1:8443 ssl default_server;' "$NGINX_CONF" || fail "IP TLS default-e listener-e dakhli nist"
  grep -qF 'default   127.0.0.1:8443;' "$STREAM_CONF" || fail "stream default be listener-e dakhli nemiravad"
  grep -qF 'game.test                    127.0.0.1:1001;' "$STREAM_CONF" || fail "SNI-e game be node route nashode"
)
ok "game/SNI: 443 stream, bare-IP ra be IP-cert-e dakhli va SNI-e game ra be node mifrestad"

# ---- 5: control_path == "/" nabayad 'location = /'-e tekrari besazad ---------------
# regression: block-e ekhtesasi-ye ctrl_path ba 'location = /'-e rishh yeksan mishod →
# do location-e yeksan dar yek server block → `nginx -t` fail → regenerate revert mikard.
(
  TMP_DIR="$(mktemp -d "${TEST_TMP_ROOT%/}/test-nginx.XXXXXX")"; trap 'rm -rf "$TMP_DIR"' EXIT
  export RATHOLECTL_LIB_ONLY=1
  source "$REPO_ROOT/rathole-manager/ratholectl"
  trap 'rm -rf "$TMP_DIR"' EXIT
  STATE="$TMP_DIR/state.json"; NGINX_CONF="$TMP_DIR/rathole.conf"
  STREAM_CONF="$TMP_DIR/stream/rathole-stream.conf"
  fc="$TMP_DIR/d.crt"; key="$TMP_DIR/d.key"; : > "$fc"; : > "$key"
  jq -n --arg fc "$fc" --arg key "$key" \
    '{domain:"x.test",cert_fullchain:$fc,cert_key:$key,control_port:2333,
      control_path:"/",fake_port:8080,sub_port:2096,
      data_port_start:1001,api_port_start:7001,nodes:[]}' > "$STATE"
  gen_nginx_conf
  n="$(grep -c '^\s*location = / {' "$NGINX_CONF")"
  [ "$n" -eq 1 ] || fail "ba control_path='/' tedad location = / bayad 1 bashad, vali $n bood"
  # rishh hanooz websocket ra be control port miferestad (sazgari ba node-haye ghadimi)
  grep -qF 'websocket    2333;' "$NGINX_CONF" || fail "map-e rishh websocket ra be control nemiferestad"
)
ok "control_path='/' faghat yek 'location = /' misazad (bedoon-e tadakhol-e nginx)"

# ---- 6: upstream client.toml ham CONTROL_PATH-e khodesh ra migirad ----------------
# har upstream yek server-e Iran-e JODA ast, pas control_path-e mostaghel darad.
(
  export RATHOLENODE_LIB_ONLY=1
  ROOT3="$(mktemp -d)"; trap 'rm -rf "$ROOT3"' EXIT
  source "$REPO_ROOT/rathole-manager/ratholenode"
  trap 'rm -rf "$ROOT3"' EXIT
  UP_DIR="$ROOT3/upstreams"; mkdir -p "$UP_DIR"
  up_toml(){ echo "$ROOT3/client-$1.toml"; }
  rth_commit_config(){ mv -f "$1" "$2"; }

  # (a) bedoon-e CONTROL_PATH → hich path
  printf 'SERVER=iran2.example:443\nHOST=iran2.example\n' > "$UP_DIR/ir2.env"
  : > "$ROOT3/up-ir2.conf"; up_svc(){ echo "$ROOT3/up-$1.conf"; }
  gen_up_client ir2
  ! grep -q '^path = ' "$ROOT3/client-ir2.toml" || {
    echo "upstream bedoon-e CONTROL_PATH nabayad path bedahad:" >&2; cat "$ROOT3/client-ir2.toml" >&2; exit 1; }

  # (b) ba CONTROL_PATH-e khodesh → haman path
  printf 'SERVER=iran2.example:443\nHOST=iran2.example\nCONTROL_PATH=/_rh/00112233445566778899aabbccddeeff\n' > "$UP_DIR/ir2.env"
  gen_up_client ir2
  grep -qF 'path = "/_rh/00112233445566778899aabbccddeeff"' "$ROOT3/client-ir2.toml" || {
    echo "CONTROL_PATH-e upstream tazrigh nashod:" >&2; cat "$ROOT3/client-ir2.toml" >&2; exit 1; }
)
ok "upstream: har server-e Iran control_path-e mostaghel-e khodash ra migirad"

echo "---"
echo "hameye nginx/control-path assertion-ha PASS shod"
