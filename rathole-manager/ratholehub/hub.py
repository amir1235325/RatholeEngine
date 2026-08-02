#!/usr/bin/env python3
# ratholehub — panel mrkzi mdirit tunnel rathole/kcp (REST API + UI)
# - bedoon vabstgi pip (fght stdlib)
# - pshtshnh: ejra-ye ratholectl/ratholenode rooye serverha az trigh SSH (kelid)
# - rooye 127.0.0.1 mishnvd; nginx zir damnhi TLS srvsh midahad (yek port/yek damnh hefz mishavad)
#
# tanzimat:  /etc/ratholehub/config.json   , inventory: /etc/ratholehub/inventory.json
# mtghirhai mhiti baraye tst lvkal: RATHOLEHUB_CONF, RATHOLEHUB_INV, RATHOLEHUB_MOCK=1
import os, sys, json, hmac, hashlib, time, subprocess, re, secrets, threading, shlex, shutil


from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

CONF_PATH = os.environ.get("RATHOLEHUB_CONF", "/etc/ratholehub/config.json")
INV_PATH  = os.environ.get("RATHOLEHUB_INV",  "/etc/ratholehub/inventory.json")
MOCK      = os.environ.get("RATHOLEHUB_MOCK") == "1"
AUDIT_PATH = os.environ.get("RATHOLEHUB_AUDIT", "/etc/ratholehub/audit.log")

# ---------- tanzimat va inventory ----------
# RLock (na Lock) ta helper-haye atomic betavanand read-modify-write ra yekja
# ghofl konand va daroon-esh save_config/set_inventory (ke khodeshan ghofl migirand) seda bezanand.
_lock = threading.RLock()

# mhdvdsazi nrkhe tlashe vrvd (zde brute-force). kelid = IP.
_LOGIN_FAILS = {}
_LOGIN_MAX = 5            # hdaksr tlashe namvfgh
_LOGIN_WINDOW = 300       # pnjrhi sanihai
_login_lock = threading.Lock()

def login_allowed(ip):
    now = time.time()
    with _login_lock:
        fails = [t for t in _LOGIN_FAILS.get(ip, []) if now - t < _LOGIN_WINDOW]
        _LOGIN_FAILS[ip] = fails
        return len(fails) < _LOGIN_MAX

def login_record_fail(ip):
    now = time.time()
    with _login_lock:
        fails = [t for t in _LOGIN_FAILS.get(ip, []) if now - t < _LOGIN_WINDOW]
        fails.append(now)
        _LOGIN_FAILS[ip] = fails

def login_reset(ip):
    with _login_lock:
        _LOGIN_FAILS.pop(ip, None)

# mghadir pishfrze naamn ke hrgz nbaid dar mohit vaghai estefade shavand.
_INSECURE_TOKEN = "changeme"
_INSECURE_PW_SHA = hashlib.sha256(b"admin").hexdigest()

def load_json(path, default):
    """khvandn JSON. fght "nbvde file" bhsvrt default brmigrdd;
    faile khrab/ghirghablkhvandn khata midahad ta ba kanfige pishfrze naamn ejra nshvim."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception as e:
        raise RuntimeError("khvandn %s shekast khord (file khrab ya bedoon dstrsi?): %s" % (path, e))


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
def _strip_ansi(s):
    return _ANSI.sub("", s or "")

def get_config():
    cfg = load_json(CONF_PATH, {
        "api_token": _INSECURE_TOKEN,
        "admin_password_sha256": _INSECURE_PW_SHA,
        "listen_host": "127.0.0.1", "listen_port": 8088,
        "ssh_key_path": "", "ssh_opts": ["-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
                                          "-o", "StrictHostKeyChecking=accept-new"],
        "bundle_dir": "/opt/ratholehub/bundle",
    })
    cfg["_insecure"] = (cfg.get("api_token") == _INSECURE_TOKEN
                        or cfg.get("admin_password_sha256") == _INSECURE_PW_SHA)
    return cfg

def get_inventory():
    inv = load_json(INV_PATH, [])
    return inv if isinstance(inv, list) else []

def set_inventory(inv):
    with _lock:
        save_json(INV_PATH, inv)

def update_inventory(mutator):
    # read-modify-write-e atomic: kolle chrkhe zir-e _lock ta do darkhast-e hamzaman
    # (ThreadingHTTPServer) update-e hamdigar ra pak nakonand. mutator(inv) -> inv-e jadid.
    with _lock:
        inv = get_inventory()
        new_inv = mutator(inv)
        if new_inv is not None:
            save_json(INV_PATH, new_inv)
        return new_inv

def save_config(cfg):
    # fildhai dakhli (ba _ shrva) zkhirh nmishvnd.
    clean = {k: v for k, v in cfg.items() if not k.startswith("_")}
    with _lock:
        save_json(CONF_PATH, clean)
        try:
            os.chmod(CONF_PATH, 0o600)
        except Exception:
            pass

def update_config(mutator):
    # read-modify-write-e atomic baraye config (mesl update_inventory).
    with _lock:
        cfg = get_config()
        new_cfg = mutator(cfg)
        save_config(new_cfg if new_cfg is not None else cfg)
        return new_cfg if new_cfg is not None else cfg

def audit_log(user, server, action, cmd, rc):
    # sbte append-only az har amliate nvshtari baraye rdgiri.
    try:
        line = json.dumps({
            "ts": int(time.time()), "user": user, "server": server,
            "action": action, "cmd": cmd, "rc": rc,
        }, ensure_ascii=False)
        os.makedirs(os.path.dirname(AUDIT_PATH), exist_ok=True)
        with _lock:
            with open(AUDIT_PATH, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:
        pass  # log nbaid masir asli ra bshknd

def read_audit(limit=100):
    try:
        with open(AUDIT_PATH, encoding="utf-8") as f:
            lines = f.readlines()[-limit:]
        out = []
        for ln in lines:
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
        out.reverse()
        return out
    except FileNotFoundError:
        return []
    except Exception:
        return []

# ---------- vaziat-e khod-e server-e hub (uptime/load/mem/disk/serviceha) ----------
_HUB_START = time.time()

# noskhe-i ke hub «akharin» midanad: az MANAGER_VERSION-e common.sh (bundle ke deploy mishavad)
# khande mishavad ta ba noskhe-ye nasb-shode rooye har server moghayese shavad. fallback: rشته-ye sabet.
HUB_FALLBACK_VERSION = "1.4.7"
def hub_manager_version():
    cands = []
    try:
        cands.append(os.path.join(get_config().get("bundle_dir", ""), "rathole-manager", "common.sh"))
        cands.append(os.path.join(get_config().get("bundle_dir", ""), "common.sh"))
    except Exception:
        pass
    cands += ["/opt/ratholehub/bundle/rathole-manager/common.sh",
              "/usr/local/bin/common.sh", "/etc/rathole-manager/common.sh"]
    for p in cands:
        try:
            if p and os.path.isfile(p):
                with open(p, encoding="utf-8", errors="ignore") as f:
                    m = re.search(r'^\s*MANAGER_VERSION="?([^"\s]+)"?', f.read(), re.M)
                    if m:
                        return m.group(1)
        except Exception:
            continue
    return HUB_FALLBACK_VERSION

def hub_status():
    # hame-ye bakhsh-ha best-effort hastand; rooye system-haye bedoon /proc ya systemctl
    # (masalan test-e local rooye Windows/Mac) faghat field-haye mojood barmigardand.
    st = {"time": int(time.time()), "mock": MOCK,
          "hub_uptime": int(time.time() - _HUB_START),
          "python": "%d.%d.%d" % sys.version_info[:3]}
    try:
        with open("/proc/uptime") as f:
            st["uptime"] = int(float(f.read().split()[0]))
    except Exception:
        pass
    try:
        st["load"] = [round(x, 2) for x in os.getloadavg()]
    except Exception:
        pass
    try:
        mi = {}
        with open("/proc/meminfo") as f:
            for ln in f:
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    mi[k.strip()] = int(v.strip().split()[0])
        if mi.get("MemTotal"):
            st["mem_total_kb"] = mi["MemTotal"]
            st["mem_avail_kb"] = mi.get("MemAvailable", 0)
    except Exception:
        pass
    try:
        du = shutil.disk_usage("/")
        st["disk_total"] = du.total
        st["disk_free"] = du.free
    except Exception:
        pass
    svcs = {}
    if shutil.which("systemctl"):
        for u in ("ratholehub", "nginx"):
            try:
                r = subprocess.run(["systemctl", "is-active", u],
                                   capture_output=True, text=True, timeout=5)
                svcs[u] = (r.stdout or "").strip() or "unknown"
            except Exception:
                svcs[u] = "unknown"
    st["services"] = svcs
    st["latest_version"] = hub_manager_version()
    return st

# ---------- aatbarsnji vrvdi + whitelist dstvrha ----------
# in bakhsh be hubcmds.py montaghel shod (file-e kuchak va ghabel-e morur, bedoon vabastegi
# be baghi-ye hub) — ba `from hubcmds import *` haman nam-ha dar in namespace mimanand
# ta baghi-ye kod (va test-ha) bedoon taghir kar konand.
from hubcmds import (  # noqa: F401  (nam-ha dar sartasar-e hub estefade mishavand)
    RE_NAME, RE_HOST, RE_PORT, RE_PROFILE, RE_IPPORT, RE_KEY, RE_B64, RE_ID, RE_PW,
    RE_EMAIL, RE_PATH, RE_SLUG, RE_HEADER, RE_BH_SRV, RE_BH_CLI, RE_BH_TOK, RE_CHAN,
    build_iran_cmd, build_node_cmd, build_cmd, WRITE_ACTIONS, _diag,
)

# ---------- ejra-ye az rah dvr (SSH) ----------
def run_on_server(server, cmd_args, timeout=120):
    if MOCK:
        return mock_run(server, cmd_args)
    cfg = get_config()
    ssh = _ssh_base(cfg, server) + cmd_args  # har arg jda; ssh ba space be shl rimvt midahad
    try:
        p = subprocess.run(ssh, capture_output=True, text=True, timeout=timeout)
        return {"rc": p.returncode, "out": _strip_ansi(p.stdout), "err": _strip_ansi(p.stderr)}
    except subprocess.TimeoutExpired:
        return {"rc": 124, "out": "", "err": "SSH timeout"}
    except Exception as e:
        return {"rc": 1, "out": "", "err": str(e)}

def _ssh_base(cfg, server):
    ssh = ["ssh"] + list(cfg.get("ssh_opts", []))
    if cfg.get("ssh_key_path"):
        ssh += ["-i", cfg["ssh_key_path"]]
    ssh += ["-p", str(server.get("ssh_port", 22)),
            "%s@%s" % (server.get("ssh_user", "root"), server["host"]), "--"]
    return ssh

def iran_main_server(s):
    # maghsad-e daghigh-e tunnel-e asli (SERVER=domain:443) ra az yek server-e Iran migirad.
    # dar halat-e pishfarz (ws+TLS) node bayad be DOMAIN vasl shavad (na host/IP-e SSH), chon
    # ratholenode az SERVER ham remote_addr va ham SNI ra misazad. domain ra az 'status --json'
    # migirim; agar darnayamad be host-e inventory fallback mikonim.
    # bazgasht: (server_str, domain)  — masalan ("rp01.l1t.ir:443", "rp01.l1t.ir")
    domain = ""
    try:
        st = run_on_server(s, ["ratholectl", "status", "--json"])
        d = json.loads(st.get("out", "") or "{}")
        domain = str(d.get("domain", "") or "").strip()
    except (ValueError, TypeError):
        domain = ""
    if domain and RE_HOST.match(domain):
        return "%s:443" % domain, domain
    host = str(s.get("host", ""))
    return ("%s:443" % host if host else ""), ""

def deploy_to_server(server):
    # apdit az GitHub: install.sh-e akharin Release ra rooye server migirad (ba mirror-haye
    # ghproxy baraye dor zadan-e filtering) va ba --update ejra mikonad. digar be bundle-e
    # mahalli-ye hub vabaste nist — server hamishe akharin noskhe-ye montasher-shode ra migirad.
    if MOCK:
        _chan = str(get_config().get("update_channel", "stable"))
        return {"rc": 0, "out": "[mock deploy→%s] github install.sh --update (kanal=%s)" % (server.get("name"), _chan), "err": ""}
    cfg = get_config()
    # slug az config (sabet، na vorodi-ye karbar) va ba regex etebarsanji mishavad.
    gh = str(cfg.get("gh_repo", "loopy-iri/RatholeEngine"))
    if not RE_SLUG.match(gh):
        return {"rc": 1, "out": "", "err": "gh_repo namotabar dar config: %r" % gh}
    # kanal-e apdit az config (default stable). faghat stable/beta mojaz ast (RE_CHAN).
    # CHERA MOHEM: 'stable' → releases/latest/download ke pre-release ha ra NADIDE migirad.
    # agar server rooye beta bashad va bدون in latest=noskhe-ye stable-e ghadimi tar bashad،
    # apdit an ra DOWNGRADE mikonad va backhaul/features-e jadid ra kharab mikonad. baraye
    # server-haye beta bayad kanal='beta' bashad ta tag-e daghigh (releases.atom) resolve shavad.
    chan = str(cfg.get("update_channel", "stable"))
    if not RE_CHAN.match(chan):
        return {"rc": 1, "out": "", "err": "update_channel namotabar dar config: %r (stable|beta)" % chan}
    base = _ssh_base(cfg, server)
    # yek script-e khoddATka ke rooye server ejra mishavad. tanha meghdar-haye tazrigh-shode
    # slug (RE_SLUG) va kanal (RE_CHAN) hastand — har do etebarsanji-shode. mirror-ha hamsan-e install.sh.
    # baraye kanal-e beta: tag-e pre-release ra rooye KHODE server az releases.atom peyda mikonim
    # (api.github.com az mirror obur nemikonad vali releases.atom mikonad — hamsan-e resolve_beta_tag).
    remote = r'''set -e
GH="%s"
CHAN="%s"
MIRRORS=("" "https://ghproxy.net/" "https://gh-proxy.com/" "https://mirror.ghproxy.com/")
REL="latest"
if [ "$CHAN" = "beta" ]; then
  TAG=""
  for M in "${MIRRORS[@]}"; do
    AT="$(curl -fsSL --connect-timeout 15 --retry 1 "${M}https://github.com/${GH}/releases.atom" 2>/dev/null)" || continue
    TAG="$(printf '%%s' "$AT" | grep -oE 'releases/tag/v[0-9A-Za-z._-]+' | sed 's#.*releases/tag/##' | grep -E -- '-(beta|rc|alpha)' | head -n1 || true)"
    [ -n "$TAG" ] && break
  done
  [ -n "$TAG" ] || { echo "hich noskhe-ye beta peyda nashod (releases.atom)" >&2; exit 1; }
  REL="$TAG"
fi
if [ "$REL" = "latest" ]; then PATH_SEG="releases/latest/download/install.sh"; else PATH_SEG="releases/download/${REL}/install.sh"; fi
T="$(mktemp)"
trap 'rm -f "$T"' EXIT
ok=0
for M in "${MIRRORS[@]}"; do
  if curl -fsSL --connect-timeout 20 --retry 2 "${M}https://github.com/${GH}/${PATH_SEG}" -o "$T" 2>/dev/null; then ok=1; break; fi
done
[ "$ok" = 1 ] || { echo "download install.sh az hameye mirror-ha shekast khord (filtering?)" >&2; exit 1; }
RATHOLE_GH="$GH" RATHOLE_RELEASE="$REL" bash "$T" --update
''' % (gh, chan)
    try:
        r = subprocess.run(base + ["bash", "-c", remote],
                           capture_output=True, text=True, timeout=600)
        return {"rc": r.returncode, "out": _strip_ansi(r.stdout), "err": _strip_ansi(r.stderr)}
    except subprocess.TimeoutExpired:
        return {"rc": 124, "out": "", "err": "SSH timeout (apdit-e GitHub bish az 600s tool keshid)"}
    except Exception as e:
        return {"rc": 1, "out": "", "err": str(e)}

# ---------- provision khodkar (ba ramz SSH → nصب kelid + deploy + sabt) ----------
def ensure_hub_key():
    # motmaen mishavad hub yek jft-kelid SSH darad; agar nabashad misazad va masir ra dar config zakhire mikonad.
    cfg = get_config()
    kp = cfg.get("ssh_key_path") or "/etc/ratholehub/id_ed25519"
    pub = kp + ".pub"
    if not (os.path.exists(kp) and os.path.exists(pub)):
        os.makedirs(os.path.dirname(kp), exist_ok=True)
        # agar yeki az do file nesfe-nim bashad, pak kon ta ssh-keygen gير nakonad
        for f in (kp, pub):
            try: os.remove(f)
            except OSError: pass
        r = subprocess.run(["ssh-keygen", "-t", "ed25519", "-N", "", "-C", "ratholehub", "-f", kp, "-q"],
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0 or not os.path.exists(pub):
            raise RuntimeError("ssh-keygen shekast: " + (r.stderr or r.stdout or "?"))
        try: os.chmod(kp, 0o600)
        except OSError: pass
    if cfg.get("ssh_key_path") != kp:
        # atomic: faghat ssh_key_path ra rooye naskhe-ye taze bezan (na kolle cfg-e bayat)
        # ta ba _config_save-e hamzaman (masalan taghir-e ramz) race nakonad.
        def _set_kp(c):
            c["ssh_key_path"] = kp
            return c
        update_config(_set_kp)
    with open(pub, "r", encoding="utf-8") as f:
        return kp, f.read().strip()

def provision_server(d):
    # vorodi: name, role, host, ssh_user, ssh_port, ssh_password
    # marahel: 1) nصب kelid-e omoomi-ye hub rooye server ba ramz  2) deploy (scp + update.sh)  3) sabt dar inventory
    name = str(d.get("name", "")); role = str(d.get("role", ""))
    host = str(d.get("host", "")); user = str(d.get("ssh_user", "root"))
    port = str(d.get("ssh_port", "22")); pw = str(d.get("ssh_password", ""))
    if not RE_NAME.match(name) or role not in ("iran", "node") or not RE_HOST.match(host) \
       or not RE_NAME.match(user) or not RE_PORT.match(port):
        return {"rc": 1, "out": "", "err": "field-haye namotabar (name/role/host/user/port)"}
    if not pw:
        return {"rc": 1, "out": "", "err": "ramz SSH lazem ast"}
    if any(s.get("name") == name for s in get_inventory()):
        return {"rc": 1, "out": "", "err": "in nam az ghabl vojood darad"}
    server = {"name": name, "role": role, "host": host, "ssh_user": user, "ssh_port": int(port)}
    # baraye node: server-e Iran-e main ra moshakhas kon (vorodi iran_server ya, agar
    # faghat yek server Iran dar hub bashad, hamon). in tunnel-e asli (SERVER) ra baad az
    # deploy tanzim mikonad ta node digar «?» nashan nadahad.
    iran_host = ""; iran_srv = None
    if role == "node":
        want = str(d.get("iran_server", "")).strip()
        irs = [s for s in get_inventory() if s.get("role") == "iran"]
        if want:
            match = next((s for s in irs if s.get("name") == want or s.get("host") == want), None)
            if match:
                iran_host = str(match.get("host", "")); iran_srv = match
            elif RE_HOST.match(want):
                iran_host = want
        elif len(irs) == 1:
            iran_host = str(irs[0].get("host", "")); iran_srv = irs[0]
    if MOCK:
        update_inventory(lambda inv: inv + [server] if not any(s.get("name") == name for s in inv) else inv)
        return {"rc": 0, "out": "[mock provision→%s] kelid nصب shod + deploy + be hub ezafe shod" % name, "err": ""}
    if not shutil.which("sshpass"):
        return {"rc": 1, "out": "", "err": "sshpass rooye hub nصب nist. nصب kon: apt install -y sshpass"}
    try:
        kp, pubkey = ensure_hub_key()
    except Exception as e:
        return {"rc": 1, "out": "", "err": str(e)}
    logs = []
    opts = ["-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=12", "-o", "NumberOfPasswordPrompts=1"]
    target = "%s@%s" % (user, host)
    # 1) nصب kelid-e omoomi dar authorized_keys (idempotent — dobare ezafe nemikonad)
    q = shlex.quote(pubkey)
    remote = ("set -e; umask 077; mkdir -p ~/.ssh; touch ~/.ssh/authorized_keys; "
              "chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys; "
              "grep -qF %s ~/.ssh/authorized_keys || printf '%%s\\n' %s >> ~/.ssh/authorized_keys" % (q, q))
    try:
        r = subprocess.run(["sshpass", "-p", pw, "ssh"] + opts + ["-p", port, target, remote],
                           capture_output=True, text=True, timeout=45)
    except subprocess.TimeoutExpired:
        return {"rc": 124, "out": "", "err": "timeout dar atesal ba ramz (host/port/firewall?)"}
    except Exception as e:
        return {"rc": 1, "out": "", "err": str(e)}
    logs.append("== nصب kelid SSH ==\n" + (_strip_ansi(r.stdout) or "(ok)") +
                (("\n[stderr] " + _strip_ansi(r.stderr)) if r.stderr.strip() else ""))
    if r.returncode != 0:
        emsg = r.stderr.strip() or r.stdout.strip() or "khata"
        low = emsg.lower()
        if "permission denied" in low or "authentication" in low:
            emsg = "ramz/karbar eshtebah ast ya vorod ba ramz roo server baste ast (PasswordAuthentication)."
        return {"rc": r.returncode, "out": "\n\n".join(logs), "err": "nصب kelid shekast khord: " + emsg}
    # 2) deploy ba kelid (scp scripts + update.sh) — server hanoz dar inventory nist pas mostaghim server dict ra midahim
    dep = deploy_to_server(server)
    logs.append("== deploy (github-update) ==\n" + (dep.get("out", "") or "") +
                (("\n[stderr] " + dep.get("err", "")) if dep.get("err") else ""))
    # 2.5) baraye node: tunnel-e asli (SERVER) ra be server-e Iran vasl kon ta «?» nashan nadahad.
    # maghsad = DOMAIN-e omoomi-ye Iran (na host/IP-e SSH) ta SNI ba cert bekhanad va tunnel bala biad.
    if role == "node" and iran_host and dep.get("rc") == 0:
        main_srv = (iran_main_server(iran_srv)[0] if iran_srv else "") or (iran_host + ":443")
        sset = run_on_server(server, ["ratholenode", "set", "SERVER", main_srv])
        logs.append("== tunnel-e asli → %s ==\n" % main_srv + (sset.get("out", "") or "") +
                    (("\n[stderr] " + sset.get("err", "")) if sset.get("err") else ""))
    elif role == "node" and not iran_host:
        logs.append("== [هشدار] server Iran-e main tanzim nashod — dar safhe-ye node ba «tanzim tunnel asli» vaslesh kon. ==")
    # 3) sabt dar inventory (hata agar deploy naghes bood, kelid nصب shode va etesal ba kelid barقarار ast)
    # 3) sabt dar inventory (hata agar deploy naghes bood, kelid nصب shode va etesal ba kelid barقarار ast)
    update_inventory(lambda inv: inv + [server] if not any(s.get("name") == name for s in inv) else inv)
    logs.append("== be hub ezafe shod: %s (%s) — az in pas atesal ba kelid ast ==" % (name, role))
    note = "" if dep.get("rc") == 0 else "\n[هشدار] deploy kamel nashod (rc=%s)؛ mitavani baad dokme «apdit» ra bezani." % dep.get("rc")
    return {"rc": 0, "out": "\n\n".join(logs) + note, "err": ""}

def mock_run(server, cmd_args):
    # prefix-e mohafez ('timeout N ...') baraye tatbigh-e mock bi-marbut ast — bardar.
    # (dar vaghe-iat SSH an ra ejra mikonad؛ inja faghat naghshe-ye dastoor mohem ast.)
    if len(cmd_args) >= 3 and cmd_args[0] == "timeout":
        cmd_args = cmd_args[2:]
    j = " ".join(cmd_args)
    role = server.get("role")

    if j == "ratholectl ls":
        return {"rc": 0, "out":
                "NAME           PORT     INBOUND      API        TRANSPORT  SNI              USER PATH\n"
                "--------------------------------------------------------------------------------\n"
                "trk01          1005     8444         -          backhaul   -                https://d/trk01\n"
                "trk02          1006     8445         9001       ws         -                https://d/trk02\n"
                "noisenode      1008     8447         -          noise      -                https://d/noisenode\n"
                "gamenodetrk    1007     2101         7001       ws         gmtrk.l1t.ir     https://d/gamenodetrk", "err": ""}
    if cmd_args[:2] == ["ratholectl", "show"] and len(cmd_args) >= 3:
        nm = cmd_args[2]
        return {"rc": 0, "out":
            "──────── dstvr nasb rooye node kharej (curl yek-khatti) ────────\n"
            "curl -fsSL https://raw.githubusercontent.com/loopy-iri/RatholeEngine/main/install.sh | sudo bash -s -- --node -- \\\n"
            "  --server rp01.l1t.ir:443 --name %s --token a0370655deadbeefcafe1234 --inbound-port 8444\n"
            "────────────────────────────────────────" % nm, "err": ""}
    if j == "ratholectl version":
        return {"rc": 0, "out": "manager_version=1.4.7\nrole=panel\nrathole_version=0.5.0", "err": ""}
    if j == "ratholenode version":
        return {"rc": 0, "out": "manager_version=1.4.6\nrole=node\nrathole_version=0.5.0", "err": ""}
    if cmd_args[:2] == ["ratholectl", "ip-cert"]:
        return {"rc": 0, "out": "WSS-e self-signed faal shod.", "err": ""}
    if cmd_args[:2] == ["ratholectl", "ip-cert-show"]:
        return {"rc": 0, "out": "-----BEGIN CERTIFICATE-----\nTU9DSw==\n-----END CERTIFICATE-----\n", "err": ""}
    if j == "ratholectl status --json":
        return {"rc": 0, "out": json.dumps({
            "domain": "rp01.l1t.ir", "public_ip": "5.202.4.40",
            "transport": "websocket+TLS (443)",
            "ports": {"control": 2333, "fake": 8080, "sub": 2096, "internal": 8443,
                      "plain": None, "direct": None, "hub": 8088, "noise": 2334,
                      "backhaul": 3080},
            "direct_header": "X-Cdn-Id",
            "cert": {"fullchain": "/etc/letsencrypt/live/rp01.l1t.ir/fullchain.pem",
                     "key": "/etc/letsencrypt/live/rp01.l1t.ir/privkey.pem",
                     "exists": "yes", "expiry": "Oct 12 09:00:00 2026 GMT", "self_signed": "no"},
            "services": {"rathole_server": "yes", "nginx": "yes", "nginx_config_ok": "yes",
                         "noise": "yes", "backhaul": "yes"},
            "sni_count": 1, "node_count": 2,
            "nodes": [{"name": "trk01", "port": 1005, "inbound_port": 8444, "api_local_port": None,
                       "sni": None, "transport": "backhaul"},
                      {"name": "gamenodetrk", "port": 1007, "inbound_port": 2101, "api_local_port": 7001,
                       "sni": "gmtrk.l1t.ir", "transport": None}]
        }), "err": ""}
    if j == "ratholectl backhaul show":
        return {"rc": 0, "out":
            "──────── faalsazi backhaul (SMUX core) rooye node kharej ────────\n"
            "rooye node in ra bezan (tunnel-e mux az haman domain/443 obur miknd):\n"
            "  ratholenode backhaul on rp01.l1t.ir 4e9c1f7a2b8d6053ae71cc94f20d3b6857aa19ef wssmux balanced\n"
            "────────────────────────────────────────", "err": ""}
    if j == "ratholectl backhaul status":
        return {"rc": 0, "out": "backhaul (SMUX core): roshan  backhaul-server ru-ye 127.0.0.1:3080 "
                "(server=wsmux / client=wssmux, profile=balanced, az nginx/443)  (node-ha: 1)\n"
                "  node-haye backhaul: trk01", "err": ""}
    if j == "ratholenode backhaul status":
        return {"rc": 0, "out": "backhaul client: active  → rp01.l1t.ir:443 (transport=wssmux, profile=balanced)", "err": ""}
    if j == "ratholectl paths":
        return {"rc": 0, "out": "──────── masir-e config-ha va file-ha ────────\n"
                "  ✓  state.json             /etc/rathole-manager/state.json\n"
                "  ✓  server.toml            /etc/rathole/server.toml\n"
                "  ✓  nginx rathole.conf     /etc/nginx/conf.d/rathole.conf\n"
                "  ✓  cert fullchain         /etc/letsencrypt/live/rp01.l1t.ir/fullchain.pem", "err": ""}
    if j == "ratholectl kcp status":
        return {"rc": 0, "out": "kcp: roshan  UDP :443 → 127.0.0.1:2333  (profile: balanced)\n"
                "  estetar: UDP/443 ~ QUIC/HTTP3\n  service: active\n  gvshdadn UDP:443: blh", "err": ""}
    if j == "ratholectl game ls":
        return {"rc": 0, "out": "NAME           SNI                    DATA     NODE-INBOUND\n"
                "------------------------------------------------------------\n"
                "gmtrk          gmtrk.l1t.ir           1007     8444", "err": ""}
    if j == "ratholectl doctor":
        return {"rc": 0, "out": "OK rathole-server faal ast\nOK nginx faal ast\n"
                "OK  node trk01 rooye port 1005 amade ast\n"
                "WARN node gamenodetrk rooye port 1007 gvsh nmidhd (klaint node vsl nist?)\n"
                "khlash: OK=3  FAIL=1", "err": ""}
    if cmd_args[:2] == ["ratholectl", "logs"] or cmd_args[:3] == ["ratholenode", "logs", "all"]:
        # nemune-ye kutah: sakhtar-e vaghei + neshan dadan-e inke token-ha REDACT shode-and.
        return {"rc": 0, "out":
                "\n===== kolli =====\n"
                "naghsh      : %s\nratholectl  : manager_version=1.6.3\n"
                "\n===== unit: rathole-server  (halat: active/enabled) =====\n"
                "Jul 31 12:00:01 rp01 rathole[811]: control channel established\n"
                "\n===== state.json (/etc/rathole-manager/state.json) =====\n"
                "{\"domain\":\"rp01.l1t.ir\",\"nodes\":[{\"name\":\"trk01\",\"token\":\"***REDACTED***\"}]}\n"
                "\n===== payan =====" % ("panel (Iran)" if role == "iran" else "node (kharej)"),
                "err": ""}
    if j == "ratholenode ls":
        return {"rc": 0, "out": "tunnel be: rp01.l1t.ir:443  (hame serviceha rooye yek channel kontroli)\n"
                "SERVICE          INBOUND    TOKEN\n-------------------------------------------\n"
                "trk01            1101       a0370655…\ngamenodetrk      2101       32eb742b…", "err": ""}
    if j == "ratholenode kcp status":
        return {"rc": 0, "out": "halat tunnel: kcp\n  local: 127.0.0.1:29900   remote(UDP): 5.202.4.40:443   profile: balanced\n"
                "  estetar: UDP/443 ~ QUIC/HTTP3\n  kcp-client: active\n  rathole-client: active", "err": ""}
    if j == "ratholenode upstream ls":
        return {"rc": 0, "out": "tunnel asli (main): rp01.l1t.ir:443  [tunnel=kcp]\n"
                "upstream 'iran2nobody': rp02.btli.ir:443  [tunnel=ws]\n    trk01b|***|1102", "err": ""}
    if j == "ratholectl noise status":
        return {"rc": 0, "out": "noise (ramznegari-shode): roshan  rathole-noise rooye port-e omomi 2334  (node-haye noise: 1)\n"
                "  node-haye noise: gamenodetrk\n"
                "  gvshdadn TCP:2334: blh\n  rathole-noise: active", "err": ""}
    if j == "ratholectl noise show":
        return {"rc": 0, "out": "──────── faalsazi halat noise rooye node kharej ────────\n"
                "  ratholenode noise on 5.202.4.40:2334 Qm9ndXNMb2NrS2V5RXhhbXBsZUJhc2U2NFBhZGRpbmc= Noise_NK_25519_ChaChaPoly_BLAKE2s\n"
                "bazgsht: ratholenode noise off", "err": ""}
    if j == "ratholectl plain status":
        return {"rc": 0, "out": "plain (bedoon TLS): roshan  listener HTTP rooye port 8880\n"
                "  gvshdadn TCP:8880: blh", "err": ""}
    if j == "ratholectl direct status":
        return {"rc": 0, "out": "direct-IP (header-based): roshan   port 8081   header: X-Cdn-Id\n"
                "  gvshdadn TCP:8081: blh\n  node-ha:  trk01 -> \"X-Cdn-Id: trk01\"", "err": ""}
    if j.startswith("ratholenode set SERVER "):
        return {"rc": 0, "out": "tanzim shod: SERVER = %s\n[mock] tunnel-e asli be-ruz shod." % cmd_args[-1], "err": ""}
    return {"rc": 0, "out": "[mock] %s → %s" % (role, j), "err": ""}


# ---------- parser hai khorooji CLI → dadhi sakhtarmnd ----------
def parse_iran_ls(text):
    nodes = []
    for line in (text or "").splitlines():
        t = line.rstrip()
        s = t.strip()
        if not s or s.startswith("NAME") or set(s) <= set("-"):
            continue
        p = t.split()
        if len(p) >= 2 and p[1].isdigit():
            # sotoon-haye jadid (transport/sni) az CLI-e taze miayand; ba CLI-e ghadimi
            # (bedoon-e in do sotoon) ham sazgar bemanim: age nabashand, path hamon p[4] ast.
            n = {"name": p[0], "port": p[1], "inbound": p[2] if len(p) > 2 else "",
                 "api": p[3] if len(p) > 3 else "-"}
            if len(p) >= 7:  # NAME PORT INBOUND API TRANSPORT SNI PATH
                tr = p[4]
                n["transport"] = None if tr in ("ws", "-", "") else tr
                n["sni"] = None if p[5] in ("-", "") else p[5]
                n["path"] = p[6]
            else:            # CLI-e ghadimi: p[4]=PATH
                n["path"] = p[4] if len(p) > 4 else ""
            nodes.append(n)
    return nodes

def parse_kcp_status(text):
    text = text or ""
    enabled = ("roshan" in text) or (re.search(r"halat tunnel[:：]?\s*kcp", text) is not None)
    port = None; profile = None; mode = None
    m = re.search(r"UDP\s*:?(\d+)", text)
    if m: port = m.group(1)
    m = re.search(r"profile[:：]?\s*([A-Za-z]+)", text)
    if m: profile = m.group(1)
    m = re.search(r"halat tunnel[:：]?\s*(\w+)", text)
    if m: mode = m.group(1)
    stealth = "QUIC" in text
    return {"enabled": enabled, "port": port, "profile": profile, "mode": mode, "stealth": stealth}

def parse_kcp_connect(text):
    # az khorooji "ratholectl kcp show" khat "ratholenode kcp on <IP>:<port> <key> <profile>" ra darmiavarad.
    for line in (text or "").splitlines():
        m = re.search(r"ratholenode\s+kcp\s+on\s+(\S+:\d+)\s+([A-Fa-f0-9]{8,64})\s+(\w+)", line)
        if m:
            return {"remote": m.group(1), "key": m.group(2), "profile": m.group(3)}
    return None

def parse_kcp_key(text):
    # key ra mostaghel az tashkhis IP darmiavarad (rooye Iran curl baraye IP momken ast kar nakonad).
    m = re.search(r"ratholenode\s+kcp\s+on\s+\S+\s+([A-Fa-f0-9]{8,64})\s+\w+", text or "")
    if m:
        return m.group(1)
    m = re.search(r"\b([A-Fa-f0-9]{24,64})\b", text or "")  # fallback: token hex
    return m.group(1) if m else None

def parse_noise_connect(text):
    # az khorooji "ratholectl noise show" khat "ratholenode noise on <IP>:<port> <pubkey> [pattern]" ra darmiavarad.
    for line in (text or "").splitlines():
        m = re.search(r"ratholenode\s+noise\s+on\s+\S+:(\d+)\s+([A-Za-z0-9+/]{40,64}={0,2})(?:\s+(\S+))?", line)
        if m:
            return {"port": m.group(1), "pubkey": m.group(2), "pattern": m.group(3) or ""}
    return None


def parse_backhaul_connect(text):
    # az khorooji "ratholectl backhaul show" khat
    # "ratholenode backhaul on <domain> <token> <transport> <profile>" ra darmiavarad.
    for line in (text or "").splitlines():
        # NOKTE: 'wssmux' bayad GHABL az 'wss' biayad — alternation-e Python chap-be-rast ast va
        # ba (wss|wssmux) faghat 'wss' match mishavad va 'mux ...' baghi mimanad (profile gom mishavad).
        m = re.search(r"ratholenode\s+backhaul\s+on\s+(\S+)\s+([A-Fa-f0-9]{16,64})\s+(wssmux|wsmux|wss|ws)"
                      r"(?:\s+(balanced|lossy|aggressive))?", line)
        if m:
            return {"domain": m.group(1), "token": m.group(2),
                    "transport": m.group(3), "profile": m.group(4) or "balanced"}
    return None

def parse_version(text):
    # khorooji-ye "ratholectl/ratholenode version" (print_version) → manager/rathole version.
    t = text or ""
    out = {"manager": "", "rathole": ""}
    m = re.search(r"manager_version=(\S+)", t)
    if m: out["manager"] = m.group(1)
    m = re.search(r"rathole_version=(\S+)", t)
    if m: out["rathole"] = m.group(1)
    return out

def parse_node_connect(text):
    # az khorooji "ratholectl show <name>" (print_node_install) name/token/inbound-e vaghei
    # ra darmiavarad — token dar 'ls' mask ast, pas az inja migirim.
    t = text or ""
    out = {}
    m = re.search(r"--name\s+([A-Za-z0-9_-]{1,40})", t)
    if m: out["name"] = m.group(1)
    m = re.search(r"--token\s+([A-Za-z0-9._=+/-]{6,255})", t)
    if m: out["token"] = m.group(1)
    m = re.search(r"--inbound-port\s+(\d{1,5})", t)
    if m: out["inbound"] = m.group(1)
    m = re.search(r"--api-token\s+([A-Za-z0-9._=+/-]{6,255})", t)
    if m: out["api_token"] = m.group(1)
    m = re.search(r"--api-inbound-port\s+(\d{1,5})", t)
    if m: out["api_inbound"] = m.group(1)
    return out if (out.get("token") and out.get("inbound") and out.get("name")) else None

def parse_noise_status(text):
    # khorooji-ye "ratholectl/ratholenode noise status" ra parse mikonad → enabled/port/count/nodes/mode.
    text = text or ""
    enabled = ("roshan" in text) or (re.search(r"halat tunnel[:：]?\s*noise", text) is not None)
    port = None; count = None; nodes = []; mode = None
    m = re.search(r"port-e omomi\s*(\d+)", text)
    if m: port = m.group(1)
    if not port:
        m = re.search(r":(\d+)", text)   # fallback (samt-e node: remote IP:PORT)
        if m: port = m.group(1)
    m = re.search(r"node-haye noise[:：]?\s*(\d+)", text)
    if m: count = m.group(1)
    m = re.search(r"node-haye noise[:：]\s*([A-Za-z0-9_,\s-]+)$", text, re.M)
    if m:
        nodes = [x.strip() for x in m.group(1).split(",") if x.strip() and not x.strip().isdigit()]
    m = re.search(r"halat tunnel[:：]?\s*(\w+)", text)
    if m: mode = m.group(1)
    return {"enabled": enabled, "port": port, "count": count, "nodes": nodes, "mode": mode}

def parse_game_ls(text):
    out = []
    for line in (text or "").splitlines():
        s = line.strip()
        if not s or s.startswith("NAME") or set(s) <= set("-"):
            continue
        p = line.split()
        if len(p) >= 2:
            out.append({"name": p[0], "sni": p[1], "data": p[2] if len(p) > 2 else "",
                        "inbound": p[3] if len(p) > 3 else ""})
    return out


def parse_plain_status(text):
    # khorooji-ye "ratholectl plain status" → enabled/port. (ingress: masir-e ws bedoon TLS)
    text = text or ""
    enabled = "roshan" in text
    port = None
    m = re.search(r"port\s+(\d+)", text)
    if m: port = m.group(1)
    return {"enabled": enabled, "port": port}

def parse_direct_status(text):
    # khorooji-ye "ratholectl direct status" → enabled/port/header. (ingress: header-routing bedoon TLS)
    text = text or ""
    enabled = "roshan" in text
    port = None; header = None
    m = re.search(r"port\s+(\d+)", text)
    if m: port = m.group(1)
    m = re.search(r"header[:：]\s+([A-Za-z0-9-]+)", text)
    if m: header = m.group(1)
    return {"enabled": enabled, "port": port, "header": header or "X-Cdn-Id"}

def parse_doctor(text):
    # alave bar shomaresh OK/FAIL, vaziat har node ra ham darmiavarad
    # (khatt-haye "OK node X rooye port P amade ast" / "WARN node X ... gvsh nmidhd")
    # ta graph/panel betavanad har edge ra sabz/ghermez konad.
    text = re.sub(r"\x1b\[[0-9;]*m", "", text or "")  # hazf-e rang-haye ANSI (agar tty bood)
    nodes = {}
    for line in text.splitlines():
        m = re.match(r"\s*(OK|WARN|FAIL)\s+node\s+([A-Za-z0-9_-]+)\s+rooye\s+port", line)
        if m:
            nodes[m.group(2)] = "ok" if m.group(1) == "OK" else "warn"
    m = re.search(r"OK=(\d+)\s+FAIL=(\d+)", text)
    if m:
        return {"ok": int(m.group(1)), "fail": int(m.group(2)), "nodes": nodes}
    return {"ok": text.count("OK "), "fail": text.count("FAIL"), "nodes": nodes}

def parse_node_ls(text):
    svcs = []; server = None
    for line in (text or "").splitlines():
        t = line.strip()
        m = re.search(r"tunnel be[:：]\s*(\S+)", t)
        if m:
            server = m.group(1); continue
        if not t or t.startswith("SERVICE") or set(t) <= set("-"):
            continue
        p = t.split()
        if len(p) >= 2 and p[1].isdigit():
            svcs.append({"name": p[0], "inbound": p[1]})
    return {"server": server, "services": svcs}

# ---- parse-e khoruji JSON-e adaptive state (bedoon-e secret-ha) ----
# faqat field-haye motalab-e shenakhte-shode ra bar-migardanad.
_ADAPTIVE_ALLOWED_KEYS = frozenset({
    "time", "current", "classification", "latency_ms", "consecutive_failures",
})

def parse_adaptive_state(raw):
    """raw: string ya dict. -> dict ba field-haye motabar ya {'classification':'unknown'}."""
    import json as _json
    try:
        if isinstance(raw, str):
            d = _json.loads(raw)
        elif isinstance(raw, dict):
            d = raw
        else:
            return {"classification": "unknown"}
        # tanha field-haye motalab-e shenakhte-shode ra bar-migardanad
        result = {k: v for k, v in d.items() if k in _ADAPTIVE_ALLOWED_KEYS}
        if "classification" not in result:
            result["classification"] = "unknown"
        return result
    except Exception:
        return {"classification": "unknown"}

def parse_upstream_ls(text):
    main = None; ups = []; cur = None
    for line in (text or "").splitlines():
        t = line.strip()
        if not t:
            continue
        mt = re.search(r"\[tunnel=(\w+)\]", t)
        um = re.search(r"upstream '([^']+)'", t)
        if um and mt:
            srv = re.search(r"'[^']+'\s*[:：]?\s*(\S+)\s*\[tunnel=", t)
            cur = {"id": um.group(1), "server": (srv.group(1) if srv else ""), "tunnel": mt.group(1), "services": []}
            ups.append(cur); continue
        if ("main" in t) and mt:
            srv = re.search(r"[:：]\s*(\S+)\s*\[tunnel=", t)
            main = {"server": (srv.group(1) if srv else ""), "tunnel": mt.group(1)}; cur = None; continue
        if "|" in t and cur is not None:
            parts = t.split("|")
            if len(parts) >= 2:
                cur["services"].append({"name": parts[0].strip(), "inbound": parts[-1].strip()})
    return {"main": main, "upstreams": ups}

# ---------- token/nshst ----------
def make_session_token(cfg):
    # kvki nshst = hmac( api_token , expiry )
    exp = str(int(time.time()) + 86400)
    sig = hmac.new(cfg["api_token"].encode(), exp.encode(), hashlib.sha256).hexdigest()
    return "%s.%s" % (exp, sig)

def check_session(cfg, token):
    try:
        exp, sig = token.split(".", 1)
        if int(exp) < time.time(): return False
        good = hmac.new(cfg["api_token"].encode(), exp.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(good, sig)
    except Exception:
        return False

def authed(cfg, headers, cookies):
    # Bearer token (baraye API kharji) ya kvki nshst (baraye UI)
    auth = headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return hmac.compare_digest(auth[7:].strip(), cfg["api_token"])
    tok = cookies.get("rhsession", "")
    return check_session(cfg, tok)

# ---------- HTTP handler ----------
class Handler(BaseHTTPRequestHandler):
    server_version = "ratholehub/0.1"

    def _cookies(self):
        raw = self.headers.get("Cookie", "")
        out = {}
        for part in raw.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1); out[k] = v
        return out

    def _send(self, code, body, ctype="application/json", extra_headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if "json" in ctype or "html" in ctype else ""))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _body_json(self):
        try:
            n = int(self.headers.get("Content-Length", "0"))
            # saghf-e andaze-ye body (1 MiB) ta yek Content-Length-e bozorg rooye masir-e
            # ehraz-nashode (masalan /api/login) hafeze ra por nakonad.
            if n > 1048576:
                return {}
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def log_message(self, *a):
        pass  # sakt

    # ---- GET ----
    def do_GET(self):
        cfg = get_config()
        path = urlparse(self.path).path
        if path == "/" or path == "/hub/" or path == "/hub":
            body, ctype = ui_asset("index.html")
            if body is None:
                return self._send(500, {"error": "ui/index.html peyda nashod (nasb-e naghes?)"})
            return self._send(200, body, ctype)
        # asset-haye UI — ham zir '/' va ham zir '/hub/' (nginx hub ra zir /hub/ mizanad).
        # faghat nam-e file-e akhar estefade mishavad va bayad dar UI_FILES bashad.
        if "/ui/" in path:
            body, ctype = ui_asset(path.rsplit("/", 1)[-1])
            if body is not None:
                # asset-ha ba mtime cache mishavand; be client no-cache midahim ta baad az
                # apdit-e hub noskhe-ye ghadimi dar marorgar namanad.
                return self._send(200, body, ctype, {"Cache-Control": "no-cache"})
            return self._send(404, {"error": "not found"})
        if path in ("/api/health", "/hub/api/health"):
            return self._send(200, {"ok": True, "mock": MOCK})
        p = path.replace("/hub", "", 1) if path.startswith("/hub/api") else path
        if not authed(cfg, self.headers, self._cookies()):
            return self._send(401, {"error": "unauthorized"})
        if p == "/api/servers":
            return self._send(200, get_inventory())
        if p == "/api/hubstatus":
            return self._send(200, hub_status())
        if p == "/api/config":
            return self._config_view()
        if p == "/api/audit":
            q = parse_qs(urlparse(self.path).query)
            try: lim = max(1, min(500, int(q.get("limit", ["100"])[0])))
            except Exception: lim = 100
            return self._send(200, read_audit(lim))
        m = re.match(r"^/api/servers/([A-Za-z0-9_-]+)/status$", p)
        if m:
            return self._status(m.group(1))
        m = re.match(r"^/api/servers/([A-Za-z0-9_-]+)/discover$", p)
        if m:
            return self._discover(m.group(1))
        m = re.match(r"^/api/servers/([A-Za-z0-9_-]+)/overview$", p)
        if m:
            return self._overview(m.group(1))
        m = re.match(r"^/api/servers/([A-Za-z0-9_-]+)/details$", p)
        if m:
            return self._details(m.group(1))
        m = re.match(r"^/api/servers/([A-Za-z0-9_-]+)/kcpconnect$", p)
        if m:
            return self._kcpconnect(m.group(1))
        m = re.match(r"^/api/servers/([A-Za-z0-9_-]+)/noiseconnect$", p)
        if m:
            return self._noiseconnect(m.group(1))
        m = re.match(r"^/api/servers/([A-Za-z0-9_-]+)/backhaulconnect$", p)
        if m:
            return self._backhaulconnect(m.group(1))
        m = re.match(r"^/api/servers/([A-Za-z0-9_-]+)/nodeconnect/([A-Za-z0-9_-]+)$", p)
        if m:
            return self._nodeconnect(m.group(1), m.group(2))
        m = re.match(r"^/api/servers/([A-Za-z0-9_-]+)/mainconnect$", p)
        if m:
            return self._mainconnect(m.group(1))
        return self._send(404, {"error": "not found"})


    # ---- POST/DELETE ----
    def do_POST(self):
        cfg = get_config()
        path = urlparse(self.path).path
        p = path.replace("/hub", "", 1) if path.startswith("/hub/api") else path
        if p == "/api/login":
            # kelid-e rate-limit ba X-Real-IP (mesl _user); posht-e nginx TCP-peer
            # hamishe 127.0.0.1 ast pas yek bucket-e global mishavad va hame ra ghofl mikonad.
            ip = self.headers.get("X-Real-IP") or (self.client_address[0] if self.client_address else "?")
            if not login_allowed(ip):
                return self._send(429, {"error": "too many attempts; try later"})
            data = self._body_json()
            pw = str(data.get("password", "")).encode()
            if hmac.compare_digest(hashlib.sha256(pw).hexdigest(), cfg["admin_password_sha256"]):
                login_reset(ip)
                tok = make_session_token(cfg)
                return self._send(200, {"ok": True, "token": cfg["api_token"]},
                                  extra_headers={"Set-Cookie": "rhsession=%s; HttpOnly; SameSite=Strict; Path=/" % tok})
            login_record_fail(ip)
            return self._send(401, {"error": "bad password"})

        if not authed(cfg, self.headers, self._cookies()):
            return self._send(401, {"error": "unauthorized"})

        if p == "/api/servers":
            return self._add_server(self._body_json())
        if p == "/api/provision":
            return self._provision(self._body_json())
        if p == "/api/config":
            return self._config_save(self._body_json())

        m = re.match(r"^/api/servers/([A-Za-z0-9_-]+)/action$", p)
        if m:
            return self._action(m.group(1), self._body_json())
        if p == "/api/ip-tls/prepare":
            return self._prepare_ip_tls(self._body_json())
        return self._send(404, {"error": "not found"})

    def do_PUT(self):
        cfg = get_config()
        p = urlparse(self.path).path
        p = p.replace("/hub", "", 1) if p.startswith("/hub/api") else p
        if not authed(cfg, self.headers, self._cookies()):
            return self._send(401, {"error": "unauthorized"})
        m = re.match(r"^/api/servers/([A-Za-z0-9_-]+)$", p)
        if m:
            return self._edit_server(m.group(1), self._body_json())
        return self._send(404, {"error": "not found"})

    def do_DELETE(self):
        cfg = get_config()
        p = urlparse(self.path).path
        p = p.replace("/hub", "", 1) if p.startswith("/hub/api") else p
        if not authed(cfg, self.headers, self._cookies()):
            return self._send(401, {"error": "unauthorized"})
        m = re.match(r"^/api/servers/([A-Za-z0-9_-]+)$", p)
        if m:
            name = m.group(1)
            update_inventory(lambda inv: [s for s in inv if s.get("name") != name])
            return self._send(200, {"ok": True})
        return self._send(404, {"error": "not found"})

    # ---- helpers ----
    def _find(self, name):
        for s in get_inventory():
            if s.get("name") == name:
                return s
        return None

    def _user(self):
        # hvite tghribi baraye audit: IP klaint (psht nginx, X-Real-IP).
        return self.headers.get("X-Real-IP") or (self.client_address[0] if self.client_address else "?")

    def _add_server(self, d):
        name = str(d.get("name", "")); role = str(d.get("role", ""))
        host = str(d.get("host", "")); user = str(d.get("ssh_user", "root"))
        port = str(d.get("ssh_port", "22"))
        if not RE_NAME.match(name) or role not in ("iran", "node") or not RE_HOST.match(host) \
           or not RE_NAME.match(user) or not RE_PORT.match(port):
            return self._send(400, {"error": "invalid fields"})
        # check-and-append atomic zir-e yek ghofl ta do add-e hamzaman ham-digar ra pak nakonand.
        with _lock:
            inv = get_inventory()
            if any(s.get("name") == name for s in inv):
                return self._send(409, {"error": "name exists"})
            inv.append({"name": name, "role": role, "host": host,
                        "ssh_user": user, "ssh_port": int(port)})
            set_inventory(inv)
        return self._send(200, {"ok": True})

    def _provision(self, d):
        # nصب khodkar: ba ramz SSH vasl mishavad, kelid-e hub ra nصب mikonad,
        # scriptha ra deploy mikonad va server ra be hub ezafe mikonad.
        res = provision_server(d)
        audit_log(self._user(), str(d.get("name", "?")), "provision",
                  "provision role=%s host=%s" % (d.get("role", "?"), d.get("host", "?")), res.get("rc"))
        code = 200 if res.get("rc") == 0 else 400
        return self._send(code, res)

    def _config_view(self):

        # hrgz ramz/token ra brnmigrdanim; fght mtaditai bikhtr.
        cfg = get_config()
        tok = cfg.get("api_token", "")
        return self._send(200, {
            "listen_host": cfg.get("listen_host"),
            "listen_port": cfg.get("listen_port"),
            "ssh_key_path": cfg.get("ssh_key_path"),
            "ssh_opts": cfg.get("ssh_opts"),
            "insecure": cfg.get("_insecure", False),
            "api_token_hint": (tok[:4] + "…" + tok[-4:]) if len(tok) >= 8 else "(unset)",
            "mock": MOCK,
        })

    def _config_save(self, d):
        # tghiire ramz admin va/ya chrkhshe token API az dakhl panel.
        # kolle read-modify-write zir-e _lock ta ba ensure_hub_key/save-e digar race nakonad.
        with _lock:
            cfg = get_config()
            changed = []
            new_pw = d.get("new_password")
            if new_pw is not None:
                cur = str(d.get("current_password", "")).encode()
                if not hmac.compare_digest(hashlib.sha256(cur).hexdigest(), cfg.get("admin_password_sha256", "")):
                    return self._send(403, {"error": "current password incorrect"})
                if not RE_PW.match(str(new_pw)):
                    return self._send(400, {"error": "password must be 6-128 chars"})
                cfg["admin_password_sha256"] = hashlib.sha256(str(new_pw).encode()).hexdigest()
                changed.append("password")
            new_token = None
            if d.get("rotate_token"):
                new_token = secrets.token_hex(24)
                cfg["api_token"] = new_token
                changed.append("api_token")
            # ssh_key_path: masir-e file (reshte). ssh_opts: HATMAN list-e reshte
            # (chvn _ssh_base list(...)-esh mikonad; reshte be karaktr-ha shekaste mishavad).
            if "ssh_key_path" in d and isinstance(d["ssh_key_path"], str):
                cfg["ssh_key_path"] = d["ssh_key_path"]; changed.append("ssh_key_path")
            if "ssh_opts" in d:
                v = d["ssh_opts"]
                if not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
                    return self._send(400, {"error": "ssh_opts must be a list of strings"})
                cfg["ssh_opts"] = v; changed.append("ssh_opts")
            if not changed:
                return self._send(400, {"error": "nothing to change"})
            save_config(cfg)
        audit_log(self._user(), "-", "config_save", ",".join(changed), 0)
        out = {"ok": True, "changed": changed}
        if new_token:
            out["api_token"] = new_token  # tnha bar namayesh token jadid
        return self._send(200, out)

    def _edit_server(self, name, d):
        # viraishe mtaditai atsal (host/user/port) bedoon hazf/afzoodan dvbarh.
        # aval hame-ye field-ha ra etebar-sanji va jam mikonim, sps atomic emal mikonim.
        changes = {}
        if "host" in d:
            if not RE_HOST.match(str(d["host"])): return self._send(400, {"error": "bad host"})
            changes["host"] = str(d["host"])
        if "ssh_user" in d:
            if not RE_NAME.match(str(d["ssh_user"])): return self._send(400, {"error": "bad user"})
            changes["ssh_user"] = str(d["ssh_user"])
        if "ssh_port" in d:
            if not RE_PORT.match(str(d["ssh_port"])): return self._send(400, {"error": "bad port"})
            changes["ssh_port"] = int(d["ssh_port"])
        if "role" in d:
            if d["role"] not in ("iran", "node"): return self._send(400, {"error": "bad role"})
            changes["role"] = d["role"]
        found = {}
        with _lock:
            inv = get_inventory()
            target = None
            for srv in inv:
                if srv.get("name") == name:
                    target = srv; break
            if not target:
                return self._send(404, {"error": "server not found"})
            target.update(changes)
            found = dict(target)
            set_inventory(inv)
        audit_log(self._user(), name, "edit_server", "metadata", 0)
        return self._send(200, {"ok": True, "server": found})

    def _prepare_ip_tls(self, d):
        iran_name = str(d.get("iran", "")); node_name = str(d.get("node", ""))
        if not RE_NAME.match(iran_name) or not RE_NAME.match(node_name):
            return self._send(400, {"error": "invalid server name"})
        iran = self._find(iran_name); node = self._find(node_name)
        if not iran or iran.get("role") != "iran" or not node or node.get("role") != "node":
            return self._send(400, {"error": "iran/node pair not found"})
        ip = str(iran.get("host", ""))
        try:
            import ipaddress
            ipaddress.IPv4Address(ip)
        except ValueError:
            return self._send(400, {"error": "Iran inventory host must be an IPv4 address"})
        # ip-cert yek vhost/default cert-e IP ezafe mikonad; domain va cert-e omoomi-ye panel ra
        # avaz nemikonad. in invariant baraye node-haye domain-based-e mojood zaroori ast.
        made = run_on_server(iran, ["ratholectl", "ip-cert", ip])
        if made.get("rc") != 0:
            return self._send(200, {"ok": False, **made})
        pub = run_on_server(iran, ["ratholectl", "ip-cert-show", ip])
        pem = pub.get("out", "")
        if (pub.get("rc") != 0 or len(pem) > 65536 or
                not pem.startswith("-----BEGIN CERTIFICATE-----") or
                not pem.rstrip().endswith("-----END CERTIFICATE-----")):
            return self._send(200, {"ok": False, "rc": pub.get("rc", 1), "out": "", "err": "public certificate read failed"})
        cfg = get_config(); trust = "/etc/rathole/ip-root-ca.crt"
        if MOCK:
            rc, err = 0, ""
        else:
            remote = _ssh_base(cfg, node) + ["install", "-D", "-m", "0644", "/dev/stdin", trust]
            try:
                put = subprocess.run(remote, input=pem, capture_output=True, text=True, timeout=30)
                rc, err = put.returncode, _strip_ansi(put.stderr)
            except subprocess.TimeoutExpired:
                rc, err = 124, "SSH timeout while installing public certificate"
            except Exception as e:
                rc, err = 1, str(e)
        audit_log(self._user(), node_name, "ip_tls_prepare", "install public certificate for %s" % ip, rc)
        if rc != 0:
            return self._send(200, {"ok": False, "rc": rc, "out": "", "err": err})
        return self._send(200, {"ok": True, "rc": 0, "server": "%s:443" % ip,
                                "tls_hostname": ip, "tls_trusted_root": trust})

    def _action(self, name, d):
        s = self._find(name)
        if not s:
            return self._send(404, {"error": "server not found"})
        action = str(d.get("action", "")); args = d.get("args", {}) or {}
        if action == "deploy":
            res = deploy_to_server(s)
            audit_log(self._user(), name, "deploy", "github-update (install.sh --update)", res.get("rc"))
            return self._send(200, {"server": name, "cmd": "github-update (install.sh --update)", **res})
        cmd = build_cmd(s.get("role"), action, args)
        if not cmd:
            return self._send(400, {"error": "unknown or invalid action"})
        res = run_on_server(s, cmd)
        if action in WRITE_ACTIONS:
            audit_log(self._user(), name, action, " ".join(cmd), res.get("rc"))
        return self._send(200, {"server": name, "cmd": " ".join(cmd), **res})

    def _overview(self, name):
        s = self._find(name)
        if not s:
            return self._send(404, {"error": "server not found"})
        role = s.get("role")
        ov = {"server": name, "role": role, "host": s.get("host"), "reachable": True}
        def R(args):
            return run_on_server(s, args)
        if role == "iran":
            r = R(["ratholectl", "ls"])
            # HAR rc-e gheyre-sefr (255=SSH fail, 124=timeout, 'Connection refused',
            # 'No route to host', 'Host key verification failed', ...) yani server dar dastras
            # nist ya command shekast khord — na faghat do zir-reshte-ye khass.
            if r.get("rc") not in (0, None):
                ov["reachable"] = False; ov["error"] = r.get("err", "") or ("rc=%s" % r.get("rc")); return self._send(200, ov)
            ov["nodes"] = parse_iran_ls(r.get("out", ""))
            ov["kcp"] = parse_kcp_status(R(["ratholectl", "kcp", "status"]).get("out", ""))
            ov["noise"] = parse_noise_status(R(["ratholectl", "noise", "status"]).get("out", ""))
            ov["plain"] = parse_plain_status(R(["ratholectl", "plain", "status"]).get("out", ""))
            ov["direct"] = parse_direct_status(R(["ratholectl", "direct", "status"]).get("out", ""))
            ov["game"] = parse_game_ls(R(["ratholectl", "game", "ls"]).get("out", ""))
            # doctor DAR overview: hatman ba mohafez-e timeout. probe-haye websocket-e doctor
            # mitavanand samt-e server gir konand (101 = connection-e baz mimanad) va an vaght
            # HAR bar-shodan-e safhe 120 sanie block mishod + yek process-e yatim rooye server
            # ja migozasht. build_iran_cmd("doctor") khodesh `timeout 60` ra ezafe mikonad.
            ov["health"] = parse_doctor(R(build_iran_cmd("doctor", {})).get("out", ""))
            ov["version"] = parse_version(R(["ratholectl", "version"]).get("out", ""))
            # status --json hameye port-ha (fake/sub/control/internal/hub/plain/noise/
            # backhaul/direct) ra yekja midahad — UI baraye safhe-ye tanzimat va check-e
            # tadakhol-e port be an niaz darad. shekast-e parse nabayad overview ra bekoshad.
            try:
                raw = R(["ratholectl", "status", "--json"]).get("out", "") or "{}"
                ov["status"] = json.loads(raw)
            except Exception as e:
                import traceback
                print(f"[hub] status --json parse failed for {name}: {e}")
                print(f"[hub] raw output: {raw[:200]}")
                traceback.print_exc()
                ov["status"] = {}
        else:
            r = R(["ratholenode", "ls"])
            if r.get("rc") not in (0, None):
                ov["reachable"] = False; ov["error"] = r.get("err", "") or ("rc=%s" % r.get("rc")); return self._send(200, ov)
            nls = parse_node_ls(r.get("out", ""))
            ov["main_server"] = nls["server"]; ov["services"] = nls["services"]
            # Node-haye jadid JSON-e normalized midahand; node-haye ghadimi fallback-e parser ra negah midarand.
            try:
                raw = R(["ratholenode", "status", "--json"]).get("out", "") or "{}"
                node_status = json.loads(raw)
                if isinstance(node_status, dict) and "main" in node_status:
                    ov["status"] = node_status
                    ov["main_tunnel"] = node_status.get("main", {}).get("transport", "ws")
            except Exception:
                ov["status"] = {}
            ov["kcp"] = parse_kcp_status(R(["ratholenode", "kcp", "status"]).get("out", ""))
            ov["noise"] = parse_noise_status(R(["ratholenode", "noise", "status"]).get("out", ""))
            ups = parse_upstream_ls(R(["ratholenode", "upstream", "ls"]).get("out", ""))
            ov["upstreams"] = ups["upstreams"]
            if not ov.get("main_tunnel"):
                ov["main_tunnel"] = (ups.get("main") or {}).get("tunnel", ov["kcp"].get("mode", "ws"))
            ov["version"] = parse_version(R(["ratholenode", "version"]).get("out", ""))
        return self._send(200, ov)

    def _details(self, name):
        s = self._find(name)
        if not s:
            return self._send(404, {"error": "server not found"})
        role = s.get("role")
        if role == "iran":
            cmds = [("ls", ["ratholectl", "ls"]), ("kcp status", ["ratholectl", "kcp", "status"]),
                    ("noise status", ["ratholectl", "noise", "status"]),
                    # doctor inja ham ba mohafez: in safhe timeout=30 darad، pas dastoor-e
                    # gir-karde bayad SAMT-E SERVER ham baste shavad، na faghat SSH-e mahalli.
                    ("game ls", ["ratholectl", "game", "ls"]), ("doctor", _diag(["ratholectl", "doctor"], 25))]
        else:
            cmds = [("show", ["ratholenode", "show"]), ("kcp status", ["ratholenode", "kcp", "status"]),
                    ("noise status", ["ratholenode", "noise", "status"]),
                    ("upstream ls", ["ratholenode", "upstream", "ls"]), ("logs", ["ratholenode", "logs", "40"])]
        parts = []
        for label, c in cmds:
            r = run_on_server(s, c, timeout=30)
            body = (r.get("out", "") or "").rstrip()
            if r.get("err"):
                body += ("\n[stderr] " + r["err"].rstrip())
            parts.append("===== %s =====\n%s" % (label, body or "(khali)"))
        return self._send(200, {"server": name, "text": "\n\n".join(parts)})

    def _kcpconnect(self, name):
        # az server Iran khatte etesal KCP (remote/key/profile daghigh) ra migirad ta
        # form node bedoon typo por shavad (elate asli 'dasti kar mikard vali panel na').
        s = self._find(name)
        if not s:
            return self._send(404, {"error": "server not found"})
        if s.get("role") != "iran":
            return self._send(400, {"error": "kcpconnect fght baraye server iran ast"})
        # 1) az 'kcp show' faghat key ra migirim (tashkhis IP rooye Iran ba curl momken ast shekast bokhorad).
        show = run_on_server(s, ["ratholectl", "kcp", "show"])
        info = parse_kcp_connect(show.get("out", ""))
        key = (info or {}).get("key") or parse_kcp_key(show.get("out", ""))
        # 2) port/profile/enabled ra az 'kcp status' migirim (motmaen-tar).
        st = parse_kcp_status(run_on_server(s, ["ratholectl", "kcp", "status"]).get("out", ""))
        port = st.get("port") or (info or {}).get("remote", ":443").split(":")[-1] or "443"
        profile = st.get("profile") or (info or {}).get("profile") or "balanced"
        if not key:
            return self._send(200, {"ok": False, "error": "kcp roshan nist ya key peida nashod",
                                    "raw": show.get("out", "") + show.get("err", "")})
        # 3) remote = host-e inventory (haman IP-i ke hub baa an be Iran vasl mishavad) + port-e KCP.
        remote = "%s:%s" % (s.get("host"), port)
        return self._send(200, {"ok": True, "remote": remote, "key": key, "profile": profile})

    def _noiseconnect(self, name):
        # az server Iran khatte etesal noise (port + pubkey) ra migirad ta form node bedoon typo por shavad.
        s = self._find(name)
        if not s:
            return self._send(404, {"error": "server not found"})
        if s.get("role") != "iran":
            return self._send(400, {"error": "noiseconnect fght baraye server iran ast"})
        show = run_on_server(s, ["ratholectl", "noise", "show"])
        info = parse_noise_connect(show.get("out", ""))
        if not info or not info.get("pubkey"):
            return self._send(200, {"ok": False, "error": "noise roshan nist ya pubkey peida nashod",
                                    "raw": show.get("out", "") + show.get("err", "")})
        # remote = host-e inventory + port-e noise (az khatte connect).
        remote = "%s:%s" % (s.get("host"), info.get("port", "2334"))
        return self._send(200, {"ok": True, "remote": remote, "pubkey": info["pubkey"],
                                "pattern": info.get("pattern", "")})

    def _backhaulconnect(self, name):
        # az server Iran khatte etesal backhaul (domain + token + transport + profile) ra migirad
        # ta form-e node bedoon-e typo por shavad — token dasti copy nashavad.
        s = self._find(name)
        if not s:
            return self._send(404, {"error": "server not found"})
        if s.get("role") != "iran":
            return self._send(400, {"error": "backhaulconnect fght baraye server iran ast"})
        show = run_on_server(s, ["ratholectl", "backhaul", "show"])
        info = parse_backhaul_connect(show.get("out", ""))
        if not info or not info.get("token"):
            return self._send(200, {"ok": False, "error": "backhaul roshan nist ya token peida nashod",
                                    "raw": show.get("out", "") + show.get("err", "")})
        status = {}
        try:
            status = json.loads(run_on_server(s, ["ratholectl", "status", "--json"]).get("out", "") or "{}")
        except Exception:
            pass
        bh = (status.get("features") or {}).get("backhaul") or {}
        mode = bh.get("mode", "nginx_tls")
        transport = bh.get("transport", info.get("transport", "wssmux"))
        if mode == "direct_ip":
            remote = "%s:%s" % (status.get("public_ip") or s.get("host"), bh.get("port") or "")
            client_transport = transport
        else:
            remote = info.get("domain")
            client_transport = info.get("transport", "wssmux")
        return self._send(200, {"ok": True, "domain": info.get("domain", ""), "remote_addr": remote,
                                "mode": mode, "token": info["token"], "transport": client_transport,
                                "tls": mode == "nginx_tls", "encrypted": mode == "nginx_tls",
                                "profile": info.get("profile", "balanced")})

    def _nodeconnect(self, name, node):
        # az server Iran, meshkhassat-e yek node (name/token/inbound) ra migirad ta betavan
        # ba yek dokme rooye node-e kharej (ya upstream-esh) be-onvan service sim-keshi kard.
        # token dar 'ls' mask ast — pas az 'ratholectl show <node>' migirim.
        s = self._find(name)
        if not s:
            return self._send(404, {"error": "server not found"})
        if s.get("role") != "iran":
            return self._send(400, {"error": "nodeconnect fght baraye server iran ast"})
        if not RE_NAME.match(node):
            return self._send(400, {"error": "name-e node namotabar"})
        show = run_on_server(s, ["ratholectl", "show", node])
        info = parse_node_connect(show.get("out", ""))
        if not info:
            return self._send(200, {"ok": False, "error": "node peida nashod ya token/inbound darnayamad",
                                    "raw": show.get("out", "") + show.get("err", "")})
        return self._send(200, {"ok": True, "name": info["name"], "token": info["token"],
                                "inbound": info["inbound"],
                                "api_token": info.get("api_token", ""),
                                "api_inbound": info.get("api_inbound", "")})

    def _mainconnect(self, name):
        # az server Iran, MAGHSAD-e daghigh-e tunnel-e asli (SERVER) ra migirad ta hangam-e
        # «tanzim tunnel asli» rooye node meghdar-e dorost set shavad. dar halat-e pishfarz
        # (ws+TLS) node bayad be DOMAIN-e omoomi vasl shavad (na host/IP-e SSH-e inventory),
        # chon ratholenode az SERVER ham remote_addr va ham hostname/SNI ra misazad — agar
        # SNI ba cert nakhanad, tunnel bala nemiayad. domain ra az 'status --json' migirim.
        s = self._find(name)
        if not s:
            return self._send(404, {"error": "server not found"})
        if s.get("role") != "iran":
            return self._send(400, {"error": "mainconnect fght baraye server iran ast"})
        server, domain = iran_main_server(s)
        dial_ip = "%s:443" % s.get("host", "") if s.get("host") else ""
        return self._send(200, {"ok": bool(server), "server": server,
                                "domain": domain, "tls_hostname": domain,
                                "dial_ip": dial_ip, "host": s.get("host", "")})

    def _discover(self, name):
        s = self._find(name)
        if not s:
            return self._send(404, {"error": "server not found"})
        if s.get("role") != "iran":
            return self._send(400, {"error": "discover fght baraye server iran ast"})

        res = run_on_server(s, ["ratholectl", "ls"])
        nodes = []
        for line in (res.get("out", "") or "").splitlines():
            t = line.strip()
            if not t or t.startswith("NAME") or set(t) <= set("- "):
                continue
            parts = t.split()
            if parts and parts[0] not in nodes:
                nodes.append(parts[0])
        return self._send(200, {"server": name, "nodes": nodes, "raw": res.get("out", "")})

    def _status(self, name):
        s = self._find(name)
        if not s:
            return self._send(404, {"error": "server not found"})
        role = s.get("role")
        checks = (["status", "doctor", "kcp_status", "plain_status", "direct_status", "noise_status", "backhaul_status"]
                  if role == "iran" else ["status", "kcp_status", "plain_status", "noise_status", "backhaul_status", "watchdog_status", "adaptive_status", "upstream_ls"])
        out = {}
        for act in checks:
            cmd = build_cmd(role, act, {})
            out[act] = run_on_server(s, cmd) if cmd else {"rc": 1, "err": "n/a"}
        return self._send(200, {"server": name, "role": role, "checks": out})


# ---------- UI (az disk، na inline) ----------
# UI (HTML/CSS/JS/i18n) be pooshe-ye ui/ montaghel shod ta ba highlight/lint-e vaghei
# virayesh shavad. hanooz "faghat stdlib" ast — hich vabastegi-ye pip ezafe nashod.
#
# AMNIAT: masir HARGEZ az vorodi-ye karbar sakhte nemishavad. yek naghshe-ye SABET az
# masir-e URL be nam-e file darim؛ har chiz-e digar 404 migirad. pas '../' ya masir-e
# motlagh nemitavanad az pooshe-ye ui/ birun beravad.
UI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui")
UI_FILES = {
    "index.html": "text/html",
    "app.css":    "text/css",
    "app.js":     "application/javascript",
    "i18n.js":    "application/javascript",
}
_ui_cache = {}
_ui_lock = threading.Lock()


def ui_asset(name):
    # (body_bytes, content_type) ya (None, None) agar name dar whitelist nabashad.
    ctype = UI_FILES.get(name)
    if ctype is None:
        return None, None
    path = os.path.join(UI_DIR, name)
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None, None
    with _ui_lock:
        hit = _ui_cache.get(name)
        if hit and hit[0] == mtime:
            return hit[1], ctype
    try:
        with open(path, "rb") as f:
            body = f.read()
    except OSError:
        return None, None
    with _ui_lock:
        _ui_cache[name] = (mtime, body)
    return body, ctype


def main():
    cfg = get_config()
    host = os.environ.get("RATHOLEHUB_HOST", cfg.get("listen_host", "127.0.0.1"))
    port = int(os.environ.get("RATHOLEHUB_PORT", cfg.get("listen_port", 8088)))
    if cfg.get("_insecure"):
        sys.stderr.write(
            "\n[!!] hoshdar amniati: token/rmze pishfrze naamn faal ast.\n"
            "     ghabl az gharar dadn panel psht nginx, config.json ra ba mghadir ghvi bsaz:\n"
            "       api_token, admin_password_sha256\n\n")
    httpd = ThreadingHTTPServer((host, port), Handler)
    print("ratholehub rooye http://%s:%d (mock=%s)" % (host, port, MOCK))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()


if __name__ == "__main__":
    main()
