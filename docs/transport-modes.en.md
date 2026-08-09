# Transport Modes — one tunnel, many carriers

The same reverse tunnel can carry traffic **five** different ways (plus game/SNI L4, direct-IP ingress, and proxy ingress). Switching modes **never** changes user services, tokens, or URL paths — only the *carrier* between the Iran server and foreign node changes.

> **Each node's carrier is exclusive.** All five transport commands write the same single variable (`TUNNEL` in `node.env`), so the last command wins — they don't stack. The hub reflects this with a single exclusive select per node that coordinates both sides.

![Transport modes](assets/transport-modes.svg)

> **Core invariant:** TLS is terminated only by nginx. The rathole-server transport is always `tls = false`; the default client uses `tls = true` over WebSocket to nginx/443.

---

## 1) WebSocket + TLS (default)

- Client connects to `wss://domain:443`.
- nginx splits root `/` with `$http_upgrade` between the **fake site** and the **rathole control channel** (rathole always uses `/` for control; the path is not configurable in rathole).
- TLS terminates on nginx (Let's Encrypt cert). The actual WebSocket control path is `/_rh/<32 hex>` (secret control path, v1.5.0+) — only that exact path routes to rathole; everything else falls through to fake/data behavior.

---

## 2) KCP — parallel UDP+FEC path

- An additive **parallel path** via kcptun over UDP+FEC for lossy links (mitigates TCP-over-TCP).
- Does **not** touch the server/nginx/443 stack — adds a second ingress path.
- Profiles (`balanced`/`lossy`/`aggressive`) must match on both ends (defined in `common.sh:kcp_profile`).
- Multi-Iran: each upstream gets its own independent kcp instance (`rathole-kcp-up-<id>`, local ports from 29901).
- Camouflage: UDP/443 looks like QUIC/HTTP3 to DPI; no conflict with TCP/443.

```bash
# Iran server
ratholectl kcp on [port] [profile]   # default: 443, balanced
ratholectl kcp off | status | show

# Foreign node
ratholenode kcp on <ip:port> <key> [profile]
ratholenode kcp off | status
```

---

## 3) Plain — WebSocket without TLS

- A separate HTTP listener (default port 8880) for unencrypted WebSocket.
- Lighter than the default path, but no nginx TLS on this path.

```bash
ratholectl plain on [port]   # Iran
ratholectl plain off | status

ratholenode plain on <ip:port>   # Node
ratholenode plain off | status
```

---

## 4) Noise — encrypted, no TLS/cert

- A **second rathole instance** (`rathole-noise`) on a separate public TCP port (default 2334).
- Transport: Noise protocol (X25519 + ChaChaPoly — the same crypto as WireGuard).
- Private key stays on the Iran server; the public key is distributed to nodes.
- Noise nodes are moved from `server.toml` to `noise-server.toml` — the two rathole processes cannot share the same `bind_addr`.

```bash
# Iran server
ratholectl noise on [port]             # generates keypair, prints node command
ratholectl noise node <name> on        # move this node to noise transport
ratholectl noise node <name> off       # move back to default transport
ratholectl noise off | status

# Foreign node
ratholenode noise on <ip:port> <pubkey> [pattern]
ratholenode noise off | status
```

---

## 5) Backhaul — SMUX multiplexer (same nginx/443)

A **separate Go binary** (`Musixal/Backhaul`, patched with uTLS Chrome fingerprint since v1.8) alongside rathole. Multiplexes many user connections onto one stream via **SMUX** — for busy/lossy links where rathole has no mux.

**Single-port/single-domain is preserved:** `backhaul-server` listens on `127.0.0.1:<port>` (default 3080) and nginx proxies the **hardcoded** `/channel` (control) and `/tunnel` (data) paths to it on the same 443.

**Key invariants:**
- Server transport is always the non-TLS variant (`ws`/`wsmux`); client always TLS (`wss`/`wssmux`). `backhaul_client_transport` in `common.sh` maps between them; both sides reject the wrong variant.
- `tcpmux` is **not supported** — it's raw TCP and cannot traverse the L7 nginx.
- `backhaul` is a node's `.transport` value (like `noise`) — never a separate flag. A backhaul node is removed from `server.toml`; otherwise both rathole-server and backhaul-server try to bind the same `127.0.0.1:<port>` and the second one dies.
- Port mapping: `"127.0.0.1:<iran_port>=<node_inbound_port>"` — keeps the port that `map $uri` points at unchanged, so user routing never moves.
- The mux profile (`balanced`/`lossy`/`aggressive`) must match on both ends. `mux_con` is server-only; `connection_pool` is client-only.
- **uTLS (v1.8+):** the patched binary sends a Chrome JA3/JA4 TLS fingerprint instead of the Go stdlib fingerprint. ALPN is forced to `http/1.1` — the Chrome profile also advertises `h2` which would cause nginx to negotiate HTTP/2, breaking the HTTP/1.1 WebSocket Upgrade.

```bash
# Iran server
ratholectl backhaul on [port] [transport] [profile]
# transport: wsmux (default) | wssmux (for direct-IP backhaul)
ratholectl backhaul node <name> on    # move this node to backhaul
ratholectl backhaul node <name> off
ratholectl backhaul off | status | show   # show prints the ready ratholenode command

# Foreign node (use the line from `ratholectl backhaul show`)
ratholenode backhaul on <domain> <token> [transport] [profile]
ratholenode backhaul off | status
```

---

## 6) Game / SNI — L4 passthrough

When any node has an `sni`, port 443 switches to nginx **stream/SNI** mode (L4 passthrough) and the L7 path/WS vhost moves to an internal port (`internal_port`, default 8443).

- TLS for game traffic terminates on the **node** (real cert, VLESS+TLS+Vision) — Iran just passes bytes.
- Regular path-routed users see no change; they still reach `https://domain/nodename`.

```bash
ratholectl game add <name> <node_tls_port> <sni>
ratholectl game rm <name> | ls
ratholectl game cert <sni>    # fetch Let's Encrypt cert + print transfer command
```

---

## 7) Direct-IP — header-based routing (ingress, not a tunnel carrier)

> This is a **user ingress mode**, not a tunnel transport. The tunnel between Iran↔node is unchanged; this just opens an alternative user entry point.

- A separate **plain HTTP port** (default 8081) where users connect **directly to the Iran server IP** — no domain, no nginx TLS.
- Routing decision comes from a **hidden header** (default `X-Cdn-Id`) whose value is the node name. The `Host` header is only a decoy and has no routing role.
- nginx uses two `map` directives (header→local rathole port, then port-or-fallback→backend) and a `proxy_pass`. Requests without a known header fall through to the **fake site**.
- **Port sharing with plain:** if `direct_port == plain_port`, only one server block is built; a recognized header wins and an unknown/empty header falls to `$backend_port`.
- SNI nodes are excluded (they are L4 passthrough on 443 and have no local L7 listener for plain HTTP).

```bash
ratholectl direct on [--port P] [--header H]   # default: 8081, X-Cdn-Id
ratholectl direct off | status
ratholectl direct show [name]    # prints ready client config (Xray/V2Ray WS without TLS)
```

⚠ **Security:** this listener has no TLS, no auth, and is public. Confidentiality and auth are handled by the proxy inside the tunnel (VLESS/VMess UUID etc.). The header is a **routing hint + camouflage**, not a secret credential — anyone who knows a node name can reach its inbound (which applies its own auth). Opening `direct_port` on a public interface is flagged explicitly to the operator.

---

## 8) Proxy — non-tunnel reverse proxy on the same 443

For an independent tunnel or service that rathole does not manage, `proxy` creates a `/<name>/` path on the same 443 that `proxy_pass`es to any upstream — without going through rathole.

- Upstream must be `http(s)://host:port` — no path, no query, strict regex (it goes directly into nginx config).
- **Shared namespace with nodes:** both live in `map $uri`; `proxy add` is rejected if the name matches an existing node, and vice versa. Names `sub`/`hub`/`channel`/`tunnel` are reserved.

```bash
ratholectl proxy add <name> <http(s)://host:port>
ratholectl proxy rm <name> | ls
```

---

## 9) Adaptive Failover (v1.5.0+)

An **automatic layer** on top of modes 1–5. Switches the active carrier without operator intervention.

- **Bounded probes:** every `ADAPTIVE_INTERVAL` seconds (default 30), one WebSocket RFC 6455 probe to `WS_PATH`. Classification: `dns_failed` → `tcp_timeout` → `tls_failed` → `ws_rejected` → `ws_timeout` → `healthy`.
- **Threshold/hysteresis:** switch after `ADAPTIVE_FAILURES` (default 3) consecutive failures; return after `ADAPTIVE_RECOVERIES` (default 5) consecutive successes + cooldown.
- **Cooldown:** `ADAPTIVE_COOLDOWN` (default 300 s) between consecutive switches.
- **Priority order:** `ws` → `kcp`. `plain` is only considered with `ALLOW_INSECURE=1` in `node.env`.
- **Auto-rollback:** if the probe fails after switching too, the previous config is restored.
- **State sanitization:** `/etc/rathole/adaptive-state.json` (mode 0600) only stores `time`, `current`, `classification`, `latency_ms`, `consecutive_failures` — no token/key/WS_PATH.

```bash
ratholenode adaptive on [--interval N] [--failures N] [--recoveries N]
ratholenode adaptive off | status
ratholenode adaptive test [--json]
```

---

## 10) Secret WebSocket Control Path (v1.5.0+)

The rathole control channel moved from `/` to `/_rh/<32 hex>` so DPI cannot distinguish it from the fake site.

- nginx: only `location = /_rh/<secret>` with `$http_upgrade` routes to the control port; all other paths keep their fake/data behavior.
- Management: `ratholectl control-path show` (masked) / `rotate` (generates new path, grace period for nodes to update).
- Node: `WS_PATH` in `node.env`, inserted as `path = "/_rh/..."` in `client.toml`.

```bash
ratholectl control-path show
ratholectl control-path rotate
```

---

**Key rule:** in modes 1–5, services/tokens/user paths remain untouched; only the tunnel carrier changes. For packet-level traffic flow details, see [`traffic-flow.md`](traffic-flow.md).

---

## See also

- [CLI Reference (Wiki)](https://github.com/loopy-iri/RatholeEngine/wiki/CLI-Reference) — full command signatures
- [Workflow Guides (Wiki)](https://github.com/loopy-iri/RatholeEngine/wiki/Workflow-Guides) — step-by-step: direct-IP setup, backhaul migration, multi-domain, multi-upstream
- [`transport-modes.md`](transport-modes.md) — Persian version of this document
- [`hub.en.md`](hub.en.md) — Hub panel documentation (English)
