## Summary of changes

<!-- One sentence describing what this PR does. -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation
- [ ] Refactor / cleanup

## Checklist

- [ ] `bash -n ratholectl ratholenode common.sh` passes
- [ ] `shellcheck -S warning ratholectl ratholenode` passes (or deviations are justified)
- [ ] `python3 -m py_compile hub.py hubcmds.py` passes (if Python files changed)
- [ ] `bash rathole-manager/test-harness.sh` passes (if bash logic changed)
- [ ] Files have **LF** line endings (no CRLF)
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] No hardcoded version numbers in user-visible strings
- [ ] No secrets (certs, tokens, state.json) committed
