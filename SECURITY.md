# Security Policy

## Scope

This policy covers vulnerabilities in:
- `rathole-manager/ratholectl` and `rathole-manager/ratholenode` (bash scripts)
- `rathole-manager/ratholehub/hub.py` and `hubcmds.py` (web panel)
- Install/update scripts (`install.sh`, `bootstrap.sh`, `update.sh`, etc.)

Out of scope: vulnerabilities in upstream binaries (`rathole`, `backhaul`, `kcptun`). Report those to their respective projects.

## Reporting a Vulnerability

**Do not open a public GitHub issue for security bugs.**

Report privately via:
- **Telegram:** [@l8PY4NET](https://t.me/l8PY4NET) (preferred — fastest response)
- **GitHub Security Advisories:** use "Report a vulnerability" on the [Security tab](https://github.com/loopy-iri/RatholeEngine/security/advisories/new)

Include:
- A description of the vulnerability and its impact
- Steps to reproduce
- Affected version(s)
- Any suggested fix (optional but appreciated)

## Response

We aim to respond within **72 hours** and release a fix within **7 days** for critical issues. You will be credited in the release notes unless you prefer otherwise.

## Known Design Constraints

- The `direct-IP` listener has no TLS and no authentication by design — confidentiality is handled by the proxy layer inside the tunnel (VLESS/VMess UUID etc.). This is documented behavior, not a vulnerability.
- The `hub` REST API stores the admin password as a bcrypt hash in `config.json` (chmod 600). The API token is a random hex string. Guessing/brute-forcing is the attacker's problem, not ours — but if you find a bypass, that *is* in scope.
- `backhaul` with `wssmux`/`direct_ip` uses `InsecureSkipVerify` — this is documented. Passive eavesdropping is prevented; active MITM is not. This is a known trade-off, not a vulnerability.
