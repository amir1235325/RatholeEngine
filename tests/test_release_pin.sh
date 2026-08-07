#!/usr/bin/env bash
# regression: nasb-e YEK NOSKHE-YE KHAS (release pinning).
#
# bug: pin kardan-e noskhe FAGHAT ba motghayer-e mohiti `RATHOLE_RELEASE` momken bood، vali dar
# dastoor-e mostanad-shode `RATHOLE_RELEASE=v1 curl ... | sudo bash` an motghayer be CURL
# michasbad (na be bash-e sudo-shode) va `sudo` ham ba env_reset pak-ash mikonad — pas karbar
# amalan HICH rahi baraye nasb-e yek noskhe-ye khas nadasht. hala flag-e `--release` hast.
set -uo pipefail

ok(){ echo "ok - $*"; }
fail(){ echo "not ok - $*" >&2; exit 1; }

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
TEST_TMP_ROOT="${TEST_TMP_ROOT:-${TMPDIR:-/tmp}}"
D="$(mktemp -d "${TEST_TMP_ROOT%/}/test-relpin.XXXXXX")"; trap 'rm -rf "$D"' EXIT INT TERM

# install.sh ra ta ghabl az main() bar midarim va resolve_dl ra mostaghim test mikonim:
# az `fetch`/shabake khabari nist، pas test offline va sari ast.
sed 's/\r$//' "$REPO_ROOT/install.sh" | sed '/^main "\$@"$/d' > "$D/lib.sh"

run(){ # $1..= argv-e install.sh ; khorooji: "REL|DL"
  ( set +e
    # shellcheck disable=SC1090
    set -- "$@"
    id(){ echo 0; }            # need-root check ra rad kon
    export -f id 2>/dev/null || true
    source "$D/lib.sh" >/dev/null 2>&1
    resolve_dl >/dev/null 2>&1
    printf '%s|%s' "${REL:-}" "${DL:-}"
  )
}

# ---- 1: --release <tag> bayad masir-e download-e haman tag ra bedahad ----
out="$(run --release v1.8.0 --panel)"
[ "${out%%|*}" = "v1.8.0" ] || fail "--release v1.8.0 pin nashod (REL=${out%%|*})"
case "${out#*|}" in
  */releases/download/v1.8.0) ok "--release v1.8.0 → releases/download/v1.8.0" ;;
  *) fail "masir-e download eshtebah ast: ${out#*|}" ;;
esac

# ---- 2: --release=<tag> (shekl-e chasbide) ham bayad kar konad ----
out="$(run --release=v1.7.0 --update)"
[ "${out%%|*}" = "v1.7.0" ] || fail "--release=v1.7.0 pin nashod (REL=${out%%|*})"
ok "--release=v1.7.0 (shekl-e chasbide) kar mikonad"

# ---- 3: bedoon-e flag bayad hamchenan latest bashad (raftar-e ghabli nashkanad) ----
out="$(run --panel)"
[ "${out%%|*}" = "latest" ] || fail "pishfarz digar latest nist (REL=${out%%|*})"
case "${out#*|}" in
  */releases/latest/download) ok "bedoon-e flag → releases/latest/download (raftar-e ghabli hefz shod)" ;;
  *) fail "masir-e pishfarz eshtebah ast: ${out#*|}" ;;
esac

# ---- 4: --stable bayad be latest naghshe shavad ----
out="$(run --stable --update)"
[ "${out%%|*}" = "latest" ] || fail "--stable be latest naghshe nashod (REL=${out%%|*})"
ok "--stable → latest"

# ---- 5: tag-e mokharreb bayad RAD shavad (dar URL miayad) ----
for bad in "../../etc/passwd" "v1.0;rm -rf /" "latest/../../x"; do
  out="$(run --release "$bad" --panel)"
  case "${out#*|}" in
    *"$bad"*) fail "tag-e namotabar rad nashod: $bad" ;;
  esac
done
ok "tag-haye namotabar (path-traversal/tazrigh) rad mishavand"

# ---- 6: argument-haye digar bayad DAST-NAKHORDE be bootstrap beravand ----
# ba'd az pars-e --release، "$@" bayad faghat argument-haye bootstrap bashad.
res="$( set +e
  id(){ echo 0; }; export -f id 2>/dev/null || true
  set -- --release v1.8.0 --panel --domain d.example --fullchain /a --key /b
  source "$D/lib.sh" >/dev/null 2>&1
  printf '%s' "$*" )"
[ "$res" = "--panel --domain d.example --fullchain /a --key /b" ] \
  || fail "argument-haye bootstrap avaz shodand: [$res]"
ok "argument-haye bootstrap (--panel/--domain/...) dast-nakhorde mimanand"

# ---- 7: ratholectl/ratholenode update ham bayad tag bepaziranad ----
for f in ratholectl ratholenode; do
  grep -qE 'v\[0-9\]\*\|\[0-9\]\*\) rel="\$1"' "$REPO_ROOT/rathole-manager/$f" \
    || fail "$f update yek tag-e khas (vX.Y.Z) ra nemipazirad"
  grep -q "tag-e noskhe namotabar" "$REPO_ROOT/rathole-manager/$f" \
    || fail "$f tag ra ghabl az gozashtan dar URL etebar-sanji nemikonad"
done
ok "ratholectl/ratholenode update <tag> ra mipaziranad va etebar-sanji mikonad"

# ---- 8: pin bayad be bootstrap/update.sh forward shavad (vagarna be latest barmigardad) ----
grep -q 'export RATHOLE_GH="$GH" RATHOLE_RELEASE="$REL"' "$REPO_ROOT/install.sh" \
  || fail "install.sh noskhe-ye pin-shode ra be bootstrap forward nemikonad"
ok "noskhe-ye pin-shode be bootstrap/update.sh forward mishavad"

echo "hameye test-haye release-pin pas shodand."
