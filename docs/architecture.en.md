# Architecture — Three Roles and the Central Design Principle

`rathole-manager` is a multi-location reverse-tunnel system built on **rathole + Nginx**. A single Iran server — behind one domain, one certificate, one port 443 — fronts many foreign "nodes" that connect back over a reverse tunnel. User traffic is routed to nodes **by URL path** (`map $uri $backend_port` in nginx).

![Architecture overview](assets/architecture.svg)

*Everything on one port/domain behind Nginx; foreign nodes connect to the Iran server via reverse tunnel.*

---

## Three Roles, Three Programs

| Role | Program | Responsibility |
|------|---------|----------------|
| **Iran panel** | [`ratholectl`](../rathole-manager/ratholectl) (bash) | rathole **server** + nginx. Owns node inventory. Generates `server.toml` + `rathole.conf`. |
| **Foreign node** | [`ratholenode`](../rathole-manager/ratholenode) (bash) | rathole **client**. Generates `client.toml`. |
| **Hub** | [`ratholehub/hub.py`](../rathole-manager/ratholehub/hub.py) (Python, stdlib only) | Central web panel driving multiple Iran servers/nodes over SSH. Details: [`hub.en.md`](hub.en.md). |

`common.sh` is sourced by both bash tools (colors/logging, `kcp_profile`, `install_kcptun`, `apply_sysctl_tuning`, `fakeweb_service`).

---

## Core Principle: State → Regenerate → Hot-Reload

Every mutation follows this pattern — **never hand-edit generated configs**; change state and regenerate:

![State→Regenerate→Reload cycle](assets/state-regenerate-reload.svg)

- **ratholectl:** state is `/etc/rathole-manager/state.json` (jq-manipulated). Commands mutate state, then call `regenerate()` → `gen_server_toml()` + `gen_nginx_conf()` → `nginx -t` → reload. Configs are written **in place (inode preserved)** so rathole's `config_watcher` hot-reloads without dropping active tunnels. Auto-reverts to `.rathole-good.bak` if `nginx -t` fails.
- **ratholenode:** state is `/etc/rathole/node.env` + `/etc/rathole/services.conf`. `gen_client()` builds `client.toml`; `reload_svc` prefers hot-reload over restart (restart only for transport changes like kcp on/off).

---

## Path == Node Name == Nginx Map == Xray Inbound

A node's `name` is simultaneously its URL path, its nginx `map` entry, and the Xray inbound path on the node. These three must stay identical. Each node has a data service; adding `--api-port` also creates a `<name>_api` service (bound to `127.0.0.1`) for panel↔node management over the tunnel.

---

## Transport Modes

The same tunnel can carry traffic **five** ways (websocket+TLS default, kcp, plain, noise, backhaul) plus game/SNI mode and two user ingress modes (direct-IP, proxy). Full details: [`transport-modes.en.md`](transport-modes.en.md).

---

## User Ingress Modes

Beyond standard path-routing on 443, two alternative user entry points exist:

- **direct-IP:** a separate HTTP port (default 8081) where users connect directly to the Iran server IP. Node selection uses a hidden header (`X-Cdn-Id: <node_name>`) instead of URL path. The tunnel between Iran↔node is untouched.
- **proxy:** a `/<name>/` path on the same 443 that `proxy_pass`es to any upstream — **without going through rathole**. For independent services that don't need a tunnel.

---

## Multi-Domain and IP Certificate

One Iran server can serve multiple domains — each with its own nginx server block on the same port 443:

```bash
ratholectl domain add cdn.example.ir [--certbot]
ratholectl domain primary cdn.example.ir
```

For users connecting directly via IP (no domain), a self-signed cert for the IP can be created and trusted on the node:

```bash
ratholectl ip-cert <IPv4>                           # Iran: create self-signed cert
ratholenode set-main <ip>:443 <ip> /path/to/cert    # Node: trust the cert
```

---

## See Also

- [`transport-modes.en.md`](transport-modes.en.md) — all transport/ingress modes with commands
- [`hub.en.md`](hub.en.md) — Hub panel, REST API, security model
- [`traffic-flow.md`](traffic-flow.md) — packet path layer by layer (Persian)
- [`performance.en.md`](performance.en.md) — tuning beyond the tunnel
- [`README.fa.md`](README.fa.md) — full CLI reference and install flows (Persian)
- [`install-manual.md`](install-manual.md) — full manual install walkthrough (English)
- [Wiki — CLI Reference](https://github.com/loopy-iri/RatholeEngine/wiki/CLI-Reference)
