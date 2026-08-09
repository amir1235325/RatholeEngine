# Contributing to RatholeEngine

Thank you for contributing. This is a Bash + Python stdlib project — no build system, no package manager.

## Quick start

```bash
git clone https://github.com/loopy-iri/RatholeEngine
cd RatholeEngine
```

## Running tests

```bash
# Full sandboxed end-to-end test (stubs root/nginx/systemctl — no real services needed):
bash rathole-manager/test-harness.sh

# Individual test scripts (in tests/):
bash tests/test_lock_prompt.sh
bash tests/test_release_pin.sh
# etc.
```

The test harness requires a `jq-linux` binary beside the scripts and hardcodes `BASE=/mnt/d/...` (WSL path). On a real Linux box, set `BASE` to a temp dir you own.

## CI checks (run before opening a PR)

```bash
# Shell syntax check:
bash -n rathole-manager/ratholectl
bash -n rathole-manager/ratholenode
bash -n rathole-manager/common.sh

# Shellcheck (install: apt install shellcheck / brew install shellcheck):
shellcheck -S warning rathole-manager/ratholectl
shellcheck -S warning rathole-manager/ratholenode

# Python syntax:
python3 -m py_compile rathole-manager/ratholehub/hub.py
python3 -m py_compile rathole-manager/ratholehub/hubcmds.py
```

CI runs all of the above on every push and PR.

## Code conventions

**Bash:**
- Scripts use `set -uo pipefail` (intentionally **not** `-e`) — the `jq | while read` pattern returns nonzero and would abort under `-e`; errors are handled explicitly with `die`.
- Config writes must preserve the inode (`cat > tmpfile && mv tmpfile dest`, never `> dest` directly) so rathole's `config_watcher` hot-reloads without dropping active tunnels.
- Temp files go through `rth_mktemp`/`rth_mktempd` (auto-cleaned via trap).
- Comments: default to none. Add one only when the **why** is non-obvious.
- Log strings and variable names follow **Finglish** (Persian transliterated to Latin, e.g. `tvlid khodkar` = auto-generate). Match the surrounding style when editing.

**Python (hub):**
- `hub.py` + `hubcmds.py` — stdlib only, no pip.
- Every new server action must be added to `build_iran_cmd`/`build_node_cmd` **and** the action allow-list, and every argument must be validated with a `RE_*` regex. Never interpolate user input into a shell string.

**Line endings:** LF only. `package.sh` strips `\r` defensively, but please don't introduce CRLF.

**Secrets:** `state.json`, `node.env`, `services.conf`, `config.json`, certs/keys are gitignored. Never commit them.

## Pull requests

1. Open an issue first for large features or breaking changes — saves everyone time.
2. Keep PRs focused. One logical change per PR.
3. Update the relevant section of `CHANGELOG.md` under `[Unreleased]`.
4. Make sure CI passes (shellcheck + `bash -n` + `py_compile`).

## Release process (maintainers only)

1. Move `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD` in `CHANGELOG.md`.
2. Add a new empty `[Unreleased]` section above it.
3. Push tag `vX.Y.Z` — the release workflow builds `rathole-manager.zip` and publishes the GitHub Release automatically, using the CHANGELOG section as the release body.
