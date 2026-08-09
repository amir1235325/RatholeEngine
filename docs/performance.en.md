# Speed and Stability Guide — Beyond the Tunnel

This guide covers every place you can improve speed and stability after the tunnel (rathole + kcp) is working. Ordered from **highest impact** to lowest. Apply each change separately and test.

> Architecture reminder: User → TLS/443/domain → nginx (Iran) → rathole-server → tunnel (websocket or kcp) → node → Xray → internet.
> Four tunable points: **tunnel**, **kernel on both servers**, **Xray on node**, **user client**. nginx is just a lightweight proxy in the path.

---

## 0) Find the Bottleneck First

```bash
# Kernel: is BBR enabled? (both servers)
sysctl net.ipv4.tcp_congestion_control      # should be: bbr

# Realtime CPU/network usage
top -d1            # is xray, nginx, or kcptun pinning CPU?

# Packet loss / path stability server-to-server
mtr -rwc 30 <other-server-IP>
```

- High `mtr` loss → **path problem**; kcp/FEC (tunnel) helps, not Xray tuning.
- High CPU → **encryption/multiplex bottleneck**; go to the Xray section.
- Neither, still slow → likely **node IP throttled**.

---

## 1) Xray — Highest Impact on Gaming / Streaming

### 1-1) Disable mux (most important for real-time traffic)
mux combines multiple streams on one connection; a heavy stream blocks the rest (head-of-line blocking).
In the **client** config and in the outbound:
```json
"mux": { "enabled": false }
```

### 1-2) Avoid double encryption
The user↔Iran path already has TLS and the tunnel also encrypts. Keep Xray inbounds on the node lightweight:
- VLESS + WS with `"security": "none"` (TLS=off) on the node — rathole/nginx already terminate TLS.
- Extra TLS only where camouflage requires it (e.g., game services with a real cert).

### 1-3) sockopt on node outbound (exit to internet)
```json
"streamSettings": {
  "sockopt": {
    "tcpNoDelay": true,
    "tcpFastOpen": true,
    "tcpKeepAliveIdle": 30,
    "mark": 0
  }
}
```

### 1-4) Fast DNS on the node (prevent slow resolves)
In the Xray node config:
```json
"dns": { "servers": ["1.1.1.1", "8.8.8.8", "localhost"] }
```
And a sensible `domainStrategy` on the outbound. If sites are slow on IPv6, use `"domainStrategy": "UseIPv4"`.

### 1-5) Buffer and log level
```json
"policy": { "levels": { "0": { "bufferSize": 512 } } },
"log": { "loglevel": "warning" }
```
- `loglevel: warning` (not `debug`) — debug I/O log eats CPU.
- Larger `bufferSize` for better throughput on large files/video.

### 1-6) Keep Xray up to date
New versions have TCP/Vision optimisations. If very old, update.

---

## 2) Kernel on Both Servers — Automated with `tune`

```bash
ratholectl tune     # on Iran server
ratholenode tune    # on foreign node
```

Sets these without a reboot or tunnel interruption:
- **BBR + fq** (modern congestion control; biggest kernel win).
- **Large UDP buffers** (`rmem_max/wmem_max=25 MB`) — required for high-throughput kcp.
- file-max / conntrack_max / somaxconn / backlog — eliminates 502s under burst.
- tcp_fastopen, mtu_probing, slow_start_after_idle=0.

Verify:
```bash
sysctl net.ipv4.tcp_congestion_control net.core.rmem_max
```

---

## 3) Tunnel and FEC Profile

```bash
# On Iran server:
ratholectl kcp on 443 balanced      # QUIC camouflage + ~30% redundancy (default)
ratholectl kcp on 443 lossy         # high loss on path → more parity
ratholectl kcp on 443 aggressive    # lowest latency (fast3 mode, large window)

# On node (same profile):
ratholenode kcp on <IRAN_IP>:443 <KEY> <profile>
```

- **balanced:** normal starting point.
- **lossy:** if you still buffer and `mtr` shows high loss (e.g., >8%).
- **aggressive:** if bandwidth is sufficient and you want only latency/stability (parity 4, aggressive mode).
- Disable and return to websocket/443: `ratholenode kcp off`.

Camouflage: **port 443 on UDP** looks like QUIC/HTTP3 to DPI; no conflict with nginx (TCP/443).
If the network throttles international UDP, either `kcp off` or go to the obfs layer (see below).

---

## 4) nginx — Rarely the Bottleneck

Already configured: `proxy_buffering off`, `tcp_nodelay`, long timeouts, high `worker_connections` (from `tune`).
Notes:
- On the data path it is pure passthrough; not much to squeeze.
- If `nginx -t` passes and `doctor` is green, nginx is not a speed issue.
- Can disable access logging for high-traffic data locations to reduce I/O: `access_log off;` in the data `location`.

---

## 5) User Client (subscription config)

- **mux=off** (important).
- If the client has multiple configs, use the **kcp** one for real-time apps.
- In v2rayNG/Nekogram: enable `TCP no delay`, disable `Mux`, keep concurrency low.
- Mobile users switching between WiFi and cellular: `tcpKeepAlive` helps keep connections alive across switches.

---

## 6) Node IP

- If all the above is done and still slow, the **node IP is likely throttled/dirty**.
- Try a cleaner node/IP. With `upstream`, you can add a second node in parallel and split users between them.
- Run `mtr` from the node to the destination (e.g., instagram.com), not just node↔Iran.

---

## 7) Stronger Camouflage (optional, manual)

If UDP/443 isn't enough and the network interferes with kcp:
- Tool: `udp2raw` (on both servers) — wraps UDP to look like TCP with obfuscation.
- Not automated in the scripts yet (to avoid untested complexity). Ask if you want a `kcp obfs on` subcommand added and sandbox-tested.

---

## Summary: Order of Actions

1. `tune` on both servers + verify BBR is active.
2. `mux=off` and sockopt in Xray/client.
3. Tunnel: `kcp on 443 balanced` → test → switch to `lossy`/`aggressive` if needed.
4. Fast DNS on node.
5. Still slow → cleaner node/IP, or obfs.

Apply each step separately so you know what actually helped.

---

## See Also

- [`transport-modes.en.md`](transport-modes.en.md) — KCP profiles and all transport modes
- [`architecture.en.md`](architecture.en.md) — system architecture
- [CLI Reference (Wiki)](https://github.com/loopy-iri/RatholeEngine/wiki/CLI-Reference) — `ratholectl tune`, `kcp`, `ratholenode tune`
