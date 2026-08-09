# Changelog (English)

All notable changes are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/); versioning follows [SemVer](https://semver.org/).

---

## [Unreleased]

## [1.8.3] - 2026-08-07

### Fixed
- **State lock was held during user input (regression from v1.6.3).** `menu` (the default `ratholectl` command) and `init` both waited for user input while holding the global lock. This caused: (1) any other `ratholectl` call (e.g. a hub SSH action) to block for 30 seconds; (2) after that timeout, execution continued **without the lock**, bypassing the lost-update/TOCTOU protection the lock was built for. Fixed by releasing the lock before `read` and re-acquiring it after the answer. One fix in `rth_read` — all 25 prompts go through the same path. Test: `tests/test_lock_prompt.sh`.

## [1.8.2] - 2026-08-07

### Added
- **Pin a specific release version with a flag.** Previously the only way was `RATHOLE_RELEASE=v1.7.0 curl ... | sudo bash`, which doesn't work: the variable goes to `curl` and `sudo` strips it. Now `install.sh` accepts `--release <tag|latest|beta>` (and `--release=` form); it prompts if not provided (Enter = latest). The pin is forwarded to bootstrap so `--update` stays on the same version. `ratholectl update <tag>` / `ratholenode update <tag>` also accept a tag. Test: `tests/test_release_pin.sh`.

### Fixed
- **Install silently hung after option selection.** Two causes: (1) in `rth_with_lock`, `exec 9>"$RTH_LOCK" 2>/dev/null` without grouping made the stderr redirect permanent — all `err`/`die` messages were silently lost; (2) TTY was not forwarded to `ratholectl init` so domain prompts didn't work under `curl | bash`. Tests: `test_stderr_visible.sh`, `test_tty_prompt.sh`, `test_init_interactive.sh`.

## [1.8.1] - 2026-08-02

### Fixed
- **Existing nodes never received the uTLS core.** `install_backhaul` started with `[ -x "$bin" ] && return 0` — before checking whether the patched core was already installed. Any node that already had `/usr/local/bin/backhaul-client` silently kept the old binary without uTLS after update. Now the SHA256 of the core is checked first; no-op if identical, replaces if different. After update, re-run `ratholenode backhaul on ...` to apply (running binary is not replaced until service restart). Test: `tests/test_core_backhaul_patch.sh`.

## [1.8.0] - 2026-08-02

### Added
- **Custom backhaul core with Chrome TLS fingerprint (uTLS).** The upstream backhaul binary uses Go's `crypto/tls` which has its own JA3/JA4 fingerprint — DPI can distinguish a Go client from a browser even when the User-Agent is faked. Our patch replaces only the TLS layer. ALPN is intentionally limited to `http/1.1` (Chrome also advertises `h2`, which causes the server to negotiate HTTP/2 and break the HTTP/1.1 WebSocket Upgrade — caught in real e2e testing). The patched binary is preferred from the local bundle; falls back to upstream download only if absent.
- **Backhaul direct-IP with self-signed TLS.** `ratholectl backhaul on <port> wssmux <profile> direct_ip` — backhaul terminates TLS itself (nginx is not in the path) using the cert from `ratholectl ip-cert <IPv4>`. Previously direct-IP was unencrypted; now the token is not on the wire. Note: the client does not verify the cert (`InsecureSkipVerify`) — passive eavesdropping is prevented; active MITM is not. Both CLI and hub state this clearly.
- **License changed to AGPL-3.0-or-later** (previously MIT). Versions up to v1.7.0 remain under MIT. Practical note (AGPL §13): if you modify RatholeEngine and let others use it over a network (e.g. run a modified `ratholehub` for them), you must provide them the source of your version. See `NOTICE`.

### Fixed
- `tls`/`encrypted` in `status --json` and hub's `backhaul show` were hardcoded to the mode string — so direct-IP + `wssmux` was incorrectly reported as "unencrypted". Now uses the transport field. New `verified` field distinguishes "encrypted" from "cert-verified".

## [1.7.0] - 2026-08-02

### Fixed
- **Install hung silently for hours during init.** Two bugs: (1) `read -rp` on a non-terminal stdin that's not yet closed (slow/filtered curl|bash from inside Iran, SSH channel, hub) waits forever — and bash `read -p` only writes the prompt when stdin is a terminal, so the user saw nothing. (2) `[ -r /dev/tty ]` was used as "we have a TTY" indicator, which is always true (device node is always readable). Fix: all prompts go through a common helper that actually opens `/dev/tty` and has a time limit (`RTH_READ_TIMEOUT`, default 300s). Without TTY, the answer is always "no" (safe default). Test: `tests/test_tty_prompt.sh`.
- **`certbot` ran without a time limit during `init`** — while nginx was stopped. From inside Iran (ACME is often filtered/slow) it could hang for hours. Now bounded (`RATHOLE_CERTBOT_TIMEOUT`, 300s).
- **Install downloads hung on stalled TCP connections** — DPI establishes the connection then stalls the stream. `--connect-timeout` doesn't catch this. Added `--speed-limit`/`--speed-time` (slow-but-progressing transfers are not killed).

### Added
- **Tunnel over bare IP (no domain).** `ratholectl ip-cert <IPv4> [days]` creates a self-signed IP-SAN cert and makes it the `default_server` vhost — the main domain/cert is untouched. Includes `ip-cert-show` (print public cert for trusting on node) and `ip-cert-off`. The private key never leaves the Iran server.
- **`ratholenode set-main <server:port> [tls_hostname] [trusted_root]`** — atomically sets the dial endpoint, SNI/cert hostname, and trust root. The node can dial an IP but verify the cert with the correct hostname; certificate verification is never disabled.
- **`ratholenode status --json`** — transport, endpoint, SNI, TLS/encryption, service state as normalized JSON (consumed by hub, with fallback for older nodes).
- **Backhaul direct-IP mode** — `ratholectl backhaul on <port> <ws|wsmux> <profile> direct_ip` binds on `0.0.0.0` without nginx. Port 443 is rejected (conflicts with nginx). Warns that TLS is absent in this mode.

## [1.6.3] - 2026-07-31

### Fixed
- **Missing `state.json` after a failed jq write.** `state_set` didn't check jq's output and did `mv` unconditionally. With `set -uo pipefail` (intentionally not `-e`), a failed jq didn't abort — so a bad jq path, full disk, or half-written state silently replaced `state.json` with an empty file, wiping all nodes/tokens/ports. Now a failed jq or empty output is rejected before `mv`.
- **Lost lock in `rth_commit_config` on systems without `flock`** — `flock: command not found` went to stderr but the subshell returned rc=0, so the `|| return 1` never fired and config was written without the lock. Added a portable `mkdir`-based fallback.

## [1.6.0] - 2026-07

### Added
- **Hub UI rewrite** — UI moved out of the inline string in `hub.py` into `ratholehub/ui/` (`index.html`, `app.css`, `app.js`, `i18n.js`). Sidebar + hash-router, bilingual (Persian/English), responsive, smart auto-refresh (every 20s, active page only).
- **Security module `hubcmds.py`** — action→argv map and `RE_*` argument regexes extracted into a small standalone module for easier auditing.
- **Exclusive transport select per node** in hub UI — replaces five independent on/off switches with a single exclusive select (`ws`/`kcp`/`plain`/`noise`/`backhaul`) that coordinates both sides.
- **Proxy ingress** — `ratholectl proxy add <name> <http(s)://host:port>`: a `/<name>/` path on 443 that `proxy_pass`es to any upstream without going through rathole.
- **Port management section** in hub server page.

## [1.5.0] - 2026-07

### Added
- **Adaptive Failover** — `ratholenode adaptive on`: timer-driven probes classify the carrier (`dns_failed` / `tcp_timeout` / `tls_failed` / `ws_rejected` / `ws_timeout` / `healthy`) and auto-switch `ws` → `kcp` with threshold/hysteresis/cooldown. State sanitized: no token/key/WS_PATH in `adaptive-state.json`.
- **Secret WebSocket control path** — control channel moved from `/` to `/_rh/<32 hex>`. Only that exact path routes to rathole; all others keep fake-site behavior. `ratholectl control-path show/rotate`.
- **Direct-IP ingress** — `ratholectl direct on`: a plain HTTP port where node selection comes from a hidden header instead of URL path.
