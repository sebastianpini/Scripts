#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"

  if [[ "$haystack" != *"$needle"* ]]; then
    fail "expected output to contain: $needle"
  fi
}

run_successfully() {
  local output

  if ! output="$("$@" 2>&1)"; then
    printf '%s\n' "$output" >&2
    fail "command failed: $*"
  fi

  printf '%s\n' "$output"
}

mkdir -p "$TMP_DIR/env" "$TMP_DIR/bin"
cp "$ROOT_DIR/ninja" "$TMP_DIR/ninja"
cp "$ROOT_DIR/run-with-env.sh" "$TMP_DIR/run-with-env.sh"
chmod +x "$TMP_DIR/ninja" "$TMP_DIR/run-with-env.sh"

cat > "$TMP_DIR/env/default.env" <<'EOF'
NINJA_ONE_INSTANCE=default.example.test
NINJA_ONE_CLIENT_ID=default-client
NINJA_ONE_CLIENT_SECRET=default-secret
NINJA_ONE_SCOPE="monitoring management"
EOF

cat > "$TMP_DIR/env/demo-eu.env" <<'EOF'
NINJA_ONE_INSTANCE=demo-eu.example.test
NINJA_ONE_CLIENT_ID=demo-eu-client
NINJA_ONE_CLIENT_SECRET=demo-eu-secret
NINJA_ONE_SCOPE="monitoring management"
EOF

cat > "$TMP_DIR/bin/python3" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'instance=%s\n' "$NINJA_ONE_INSTANCE"
printf 'script=%s\n' "$1"
shift
printf 'args=%s\n' "$*"
EOF
chmod +x "$TMP_DIR/bin/python3"

DEFAULT_OUTPUT="$(PATH="$TMP_DIR/bin:$PATH" run_successfully "$TMP_DIR/ninja" last-login --enabled-only)"
assert_contains "$DEFAULT_OUTPUT" "instance=default.example.test"
assert_contains "$DEFAULT_OUTPUT" "script=scripts/python/ninjaone-technician-inactive-login-report/technician_last_login_report.py"
assert_contains "$DEFAULT_OUTPUT" "args=--enabled-only"

EXPLICIT_OUTPUT="$(PATH="$TMP_DIR/bin:$PATH" run_successfully "$TMP_DIR/ninja" demo-eu org-summary)"
assert_contains "$EXPLICIT_OUTPUT" "instance=demo-eu.example.test"
assert_contains "$EXPLICIT_OUTPUT" "script=scripts/python/ninjaone-organization-device-summary-report/organization_device_summary_report.py"

HELP_OUTPUT="$(run_successfully "$TMP_DIR/ninja" help)"
assert_contains "$HELP_OUTPUT" "./ninja <script> [args...]"
assert_contains "$HELP_OUTPUT" "./ninja <env> <script> [args...]"
