# common.sh — tavabe eshteraki beyn ratholectl, ratholenode va nsabha
# in file tvst source frakhvani mishvd; be tnhaii ejra nemishavad.

# noskhe-ye rathole-manager (panel/node/hub). moqe-e release in adad ba tag hamahang mishavad.
# package.sh/CI mitavanad in ra be tag-e vaghei stamp konad; agar dast taghir dadi، bedoon 'v' bezar.
MANAGER_VERSION="1.6.3"

c_g(){ printf '\033[1;32m%s\033[0m' "$*"; }
c_r(){ printf '\033[1;31m%s\033[0m' "$*"; }
c_y(){ printf '\033[1;33m%s\033[0m' "$*"; }
log(){ printf '%s %s\n' "$(c_g '[+]')" "$*"; }
warn(){ printf '%s %s\n' "$(c_y '[*]')" "$*"; }
err(){ printf '%s %s\n' "$(c_r '[!]')" "$*" >&2; }
die(){ err "$*"; exit 1; }
ask_yn(){ local p="$1" a; read -rp "$p [y/N]: " a; [[ "$a" =~ ^[Yy]$ ]]; }
need_root(){ [ "$(id -u)" -eq 0 ] || die "bayad ba root ejra shavad (sudo)."; }

# mirror-haye ghproxy baraye dor-zadan-e filtering-e Iran (hamsan-e install.sh/install-panel.sh).
RTH_MIRRORS=("" "https://ghproxy.net/" "https://gh-proxy.com/" "https://mirror.ghproxy.com/")

# akharin tag-e pre-release (beta/rc/alpha) ra peyda mikonad. $1 = slug-e owner/repo.
# CHERA atom va na API: masir-e `releases/latest/download` dar GitHub pre-release ha ra
# NADIDE migirad, pas baraye beta bayad tag-e daghigh ra bedanim. api.github.com az mirror-haye
# ghproxy obur nemikonad vali github.com/<slug>/releases.atom mikonad — va atom ham be jq niaz
# nadarad (dar node-e taze-nasb momken ast jq nabashad). tartib-e atom: jadidtarin aval.
resolve_beta_tag(){
  local gh="$1" m out tag
  for m in "${RTH_MIRRORS[@]}"; do
    out="$(curl -fsSL --connect-timeout 15 --retry 1 "${m}https://github.com/${gh}/releases.atom" 2>/dev/null)" || continue
    tag="$(printf '%s' "$out" \
      | grep -oE 'releases/tag/v[0-9A-Za-z._-]+' \
      | sed 's#.*releases/tag/##' \
      | grep -E -- '-(beta|rc|alpha)' \
      | head -n1)"
    [ -n "$tag" ] && { printf '%s\n' "$tag"; return 0; }
  done
  return 1
}

# neveshtan-e amn-e in-place ba lock-e sidecar (hefz inode baraye hot-reload-e rathole).
# $1 = file-e movaqqat (generated); $2 = file-e live (masir-e vaghei config).
# agar src khali bashad (0 byte) rad mikonad ta rathole config-e naghes nabinad.
# flock hamishe mojood nist (image-e minimal bedoon-e util-linux، MSYS/Git-Bash). ghablan
# nabudanash BI-SEDA ghofl ra az beyn mibord: `flock: command not found` be stderr miraft
# vali subshell rc=0 barmigardand — pas `|| return 1` fael nemishod va config BEDOON-e ghofl
# neveshte mishod. do neveshtan-e hamzaman → config-e nim-kare ke rathole hot-reload mikonad.
# pas yek bar tashkhis midahim va agar nabood az mkdir (atomic dar POSIX) ghofl misazim.
_RTH_HAS_FLOCK=""
_rth_has_flock(){
  [ -n "$_RTH_HAS_FLOCK" ] || { command -v flock >/dev/null 2>&1 && _RTH_HAS_FLOCK=1 || _RTH_HAS_FLOCK=0; }
  [ "$_RTH_HAS_FLOCK" = 1 ]
}

rth_commit_config(){
  local src="$1" dst="$2" lock="${2}.lock"
  [ -s "$src" ] || { err "config-e jadid khali ast: $src"; return 1; }
  mkdir -p "$(dirname "$dst")"
  if _rth_has_flock; then
    (
      flock -x 9
      cat "$src" > "$dst"
    ) 9>"$lock" || return 1
  else
    # fallback-e portable: mkdir atomic ast. ta ~5 sanie montazer mimanim؛ agar ghofl azad
    # nashod (masalan process-e ghabli mord va lockdir mande) HOSHDAR midahim va edame —
    # gir kardan-e hamishegi bad-tar az neveshtan-e bedoon-e ghofl ast.
    local d="${dst}.lockd" i=0 held=0 rc=0
    while [ "$i" -lt 50 ]; do
      if mkdir "$d" 2>/dev/null; then held=1; break; fi
      i=$((i+1)); sleep 0.1 2>/dev/null || sleep 1
    done
    [ "$held" -eq 1 ] || warn "ghofl-e '$dst' azad nashod (timeout); bedoon-e ghofl minevisam."
    cat "$src" > "$dst" || rc=1
    [ "$held" -eq 1 ] && rmdir "$d" 2>/dev/null
    [ "$rc" -eq 0 ] || return 1
  fi
  rm -f "$src"
}


# chap-e noskhe — ham baraye ensan ham machine-parseable (hub 'manager_version=' ra migirad).
# $1=role (panel|node|hub) faghat baraye namayesh; rathole-version az binari khande mishavad.
print_version(){
  local role="${1:-?}" rv
  rv="$(rathole --version 2>/dev/null | head -n1 | awk '{print $NF}')"
  [ -n "$rv" ] || rv="-"
  echo "manager_version=${MANAGER_VERSION}"
  echo "role=${role}"
  echo "rathole_version=${rv}"
}

# profile FEC → "datashard parityshard mode sndwnd rcvwnd"
kcp_profile(){
  case "${1:-balanced}" in
    balanced)   echo "10 3 fast2 2048 2048" ;;
    lossy)      echo "10 5 fast2 2048 2048" ;;
    aggressive) echo "10 4 fast3 4096 4096" ;;
    *) return 1 ;;
  esac
}

# nasb kcptun (server|client)
install_kcptun(){
  local role="$1" bin="/usr/local/bin/kcptun-$1" ver="${KCPTUN_VER:-v20260129}" base="${KCPTUN_BASE:-https://github.com/ossfork/kcptun/releases/download}" arch tmp url
  [ -x "$bin" ] && return 0
  case "$(uname -m)" in x86_64) arch=amd64 ;; aarch64) arch=arm64 ;; armv7l) arch=armv7 ;; *) die "memari poshtibani nemishavad." ;; esac
  command -v curl >/dev/null 2>&1 || die "curl lazem ast."
  log "download kcptun ${ver} ($role)..."
  tmp="$(mktemp -d)"
  url="${base}/${ver}/kcptun_linux_${arch}.tar.gz"
  curl -fsSL "$url" -o "$tmp/k.tgz" || { rm -rf "$tmp"; die "download kcptun shekast khord."; }
  tar -xzf "$tmp/k.tgz" -C "$tmp" || { rm -rf "$tmp"; die "baz kardan arshiv kcptun shekast khord."; }
  install -m755 "$tmp/${role}_linux_${arch}" "$bin" || { rm -rf "$tmp"; die "nasb bainri kcptun shekast khord."; }
  rm -rf "$tmp"
  log "kcptun-$role nasb shod: $bin"
}

# profile mux-e backhaul (SMUX) → "mux_con mux_version mux_framesize mux_recievebuffer mux_streambuffer connection_pool"
# HAR DO taraf (server/client) bayad haman profile ra dashte bashand ta parametrhaye SMUX yeksan bemanad.
# nokte: 'mux_con' faghat samt-e server mani darad va 'connection_pool' faghat samt-e client —
# har taraf field-e marbut be khodash ra minevisad va baghi ra dor mirizad.
backhaul_mux_profile(){
  case "${1:-balanced}" in
    balanced)   echo "8 1 32768 4194304 65536 8" ;;
    lossy)      echo "4 1 32768 4194304 65536 6" ;;
    aggressive) echo "16 2 65536 8388608 131072 12" ;;
    *) return 1 ;;
  esac
}

# transport-e client az roo-ye transport-e server: TLS FAGHAT ru-ye nginx terminate mishavad,
# pas server hamishe variant-e bedoon-e TLS ast (ws/wsmux) va client variant-e TLS-dar (wss/wssmux)
# ra be nginx:443 mizanad — daghighan haman invariant-e rathole (server tls=false, client tls=true).
backhaul_client_transport(){
  case "${1:-wsmux}" in
    ws)    echo "wss" ;;
    wsmux) echo "wssmux" ;;
    *) return 1 ;;
  esac
}

# nasb backhaul (server|client). binary-e Go tak-fail ast; role faghat dar esm-e khoruji tafavot darad.
# ba halqe-ye mirror ta az dakhel Iran (filtr/thrim github) ham javab begirad — haman elgo-ye install-panel.
install_backhaul(){
  local role="$1" bin="/usr/local/bin/backhaul-$1" ver="${BACKHAUL_VER:-v0.6.5}" arch tmp ok=0 m
  [ -x "$bin" ] && return 0
  case "$(uname -m)" in x86_64) arch=amd64 ;; aarch64) arch=arm64 ;; *) die "memari poshtibani nemishavad." ;; esac
  command -v curl >/dev/null 2>&1 || die "curl lazem ast."
  log "download backhaul ${ver} ($role)..."
  tmp="$(mktemp -d)"
  for m in "" "https://ghproxy.net/" "https://gh-proxy.com/" "https://mirror.ghproxy.com/"; do
    if curl -fsSL --connect-timeout 20 --retry 2 "${m}https://github.com/Musixal/Backhaul/releases/download/${ver}/backhaul_linux_${arch}.tar.gz" -o "$tmp/bh.tgz" 2>/dev/null; then ok=1; break; fi
    warn "in mnba javab nadad, mnba-ye badi..."
  done
  [ "$ok" -eq 1 ] || { rm -rf "$tmp"; die "download backhaul az hame-ye mnaba shekast khord."; }
  tar -xzf "$tmp/bh.tgz" -C "$tmp" || { rm -rf "$tmp"; die "baz kardan arshiv backhaul shekast khord."; }
  local src; src="$(find "$tmp" -maxdepth 2 -type f -name 'backhaul*' ! -name '*.tar.gz' | head -n1)"
  [ -n "$src" ] || { rm -rf "$tmp"; die "binary-e backhaul dar arshiv peyda nashod."; }
  install -m755 "$src" "$bin" || { rm -rf "$tmp"; die "nasb binary backhaul shekast khord."; }
  rm -rf "$tmp"
  log "backhaul-$role nasb shod: $bin"
}

# tanzimat sysctl (BBR + file limits + conntrack)
apply_sysctl_tuning(){
  modprobe nf_conntrack 2>/dev/null || true
  cat >/etc/sysctl.d/99-rathole-tune.conf <<'TUNE'
net.core.default_qdisc=fq
net.ipv4.tcp_congestion_control=bbr
net.ipv4.tcp_mtu_probing=1
net.ipv4.tcp_slow_start_after_idle=0
net.ipv4.tcp_fastopen=3
fs.file-max=2097152
net.core.somaxconn=65535
net.core.netdev_max_backlog=16384
net.ipv4.tcp_max_syn_backlog=65535
net.ipv4.ip_local_port_range=1024 65535
net.netfilter.nf_conntrack_max=1048576
net.core.rmem_max=26214400
net.core.wmem_max=26214400
net.core.rmem_default=26214400
net.core.wmem_default=26214400
TUNE
  sysctl --system >/dev/null 2>&1 || true
  log "BBR=$(sysctl -n net.ipv4.tcp_congestion_control 2>/dev/null)  conntrack_max=$(sysctl -n net.netfilter.nf_conntrack_max 2>/dev/null || echo n/a)"
}

# service systemd fakeweb (web fik sadh ba python3)
fakeweb_service(){
  local svc="$1" port="${2:-8081}" action="${3:-start}"
  command -v python3 >/dev/null 2>&1 || die "python3 nasb nist (apt install -y python3)."
  mkdir -p /var/www/rathole-fake
  [ -f /var/www/rathole-fake/index.html ] || cat > /var/www/rathole-fake/index.html <<'HTML'
<!doctype html><html><head><meta charset="utf-8"><title>Welcome</title></head>
<body style="font-family:sans-serif"><h1>It works!</h1><p>Default web page.</p></body></html>
HTML
  case "$action" in
    start)
      cat > "/etc/systemd/system/${svc}.service" <<UNIT
[Unit]
Description=rathole fake web ($svc)
After=network.target
[Service]
ExecStart=/usr/bin/python3 -m http.server ${port} --bind 127.0.0.1 --directory /var/www/rathole-fake
Restart=always
RestartSec=2
[Install]
WantedBy=multi-user.target
UNIT
      systemctl daemon-reload
      systemctl enable --now "$svc" >/dev/null 2>&1
      log "web fik ($svc) rooye 127.0.0.1:${port} bala amad." ;;
    stop)   systemctl stop "$svc" 2>/dev/null && log "motevaghef shod." || warn "ejra naboodan." ;;
    rm)     systemctl disable --now "$svc" 2>/dev/null || true; rm -f "/etc/systemd/system/${svc}.service"; systemctl daemon-reload; log "hazf shod." ;;
    status) systemctl --no-pager status "$svc" | sed -n '1,8p' || true ;;
  esac
}
# ---------------------------------------------------------------------------
# jam-avari-ye log baraye eshkal-zodai (`ratholectl logs` / `ratholenode logs`)
# ---------------------------------------------------------------------------
# HOSHDAR-E AMNIATI: khorooji-ye in tavabe maamoolan dar chat/issue paste mishavad.
# har chizi ke token/kelid/ramz ast BAYAD az inja rad shavad. rth_redact tanha
# darvaze-ye khorooj ast — har file-e jadidi ke ezafe mikoni HATMAN az an rad kon.
rth_redact(){
  sed -E \
    -e 's/("(token|api_token|bh_token|backhaul_token|admin_password_sha256|password|secret|private_key|local_private_key|remote_public_key|noise_private_key)"[[:space:]]*:[[:space:]]*")[^"]*"/\1***REDACTED***"/g' \
    -e 's/^([[:space:]]*(token|default_token|password|secret|private_key|local_private_key|remote_public_key)[[:space:]]*=[[:space:]]*")[^"]*"/\1***REDACTED***"/' \
    -e 's/^([[:space:]]*(TOKEN|BH_TOKEN|NOISE_KEY|PASSWORD|API_TOKEN)=).*/\1***REDACTED***/' \
    -e 's#(/_rh/)[A-Fa-f0-9]{8,}#\1***REDACTED***#g' \
    -e 's/([?&](token|password|secret)=)[^&"[:space:]]*/\1***REDACTED***/g'
}

# yek bakhsh-e onvan-dar dar khorooji-ye log
rth_sec(){ printf '\n===== %s =====\n' "$*"; }

# log-e yek unit-e systemd (agar vojood dashte bashad)
rth_unit_log(){ # $1=unit  $2=tedad khat
  local u="$1" n="${2:-80}"
  systemctl list-unit-files "$u.service" >/dev/null 2>&1 || return 0
  [ -f "/etc/systemd/system/$u.service" ] || [ -f "/lib/systemd/system/$u.service" ] || return 0
  rth_sec "unit: $u  (halat: $(systemctl is-active "$u" 2>/dev/null || echo unknown)/$(systemctl is-enabled "$u" 2>/dev/null || echo n/a))"
  journalctl -u "$u" -n "$n" --no-pager 2>/dev/null | rth_redact || true
}

# mohtava-ye yek file-e config (redact-shode)
rth_file_dump(){ # $1=barchasb  $2=masir  [$3=hadaksar khat]
  local label="$1" p="$2" n="${3:-200}"
  [ -f "$p" ] || { rth_sec "$label ($p) — NIST"; return 0; }
  rth_sec "$label ($p)"
  head -n "$n" "$p" 2>/dev/null | rth_redact || true
}
