#!/usr/bin/env bash
# CLI smoke tests for scripts/memory, scripts/user-memory, and scripts/space-memory.
# Usage: ./tests/run_tests.sh
# Optional integration: MEMORY_INTEGRATION=1 KBase_AuthTicket=... ./tests/run_tests.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MEMORY="${MEMORY_SCRIPT:-$ROOT/scripts/memory}"
USER_MEMORY="${USER_MEMORY_SCRIPT:-$ROOT/scripts/user-memory}"
SPACE_MEMORY="${SPACE_MEMORY_SCRIPT:-$ROOT/scripts/space-memory}"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

failures=0

die() {
  echo -e "${RED}FAIL:${NC} $*" >&2
  failures=$((failures + 1))
}

pass() {
  echo -e "${GREEN}OK:${NC} $*"
}

require_jq() {
  if ! command -v jq &>/dev/null; then
    echo "SKIP: jq not installed (required by memory CLI)" >&2
    exit 0
  fi
}

run_isolated_script() {
  local script="$1"
  local home="$2"
  shift 2
  env -i PATH="$PATH" HOME="$home" bash "$script" "$@"
}

tmp_home() {
  mktemp -d "${TMPDIR:-/tmp}/memory-test-home.XXXXXX"
}

fake_curl_bin() {
  local bin_dir
  bin_dir=$(mktemp -d "${TMPDIR:-/tmp}/memory-test-bin.XXXXXX")
  cat >"$bin_dir/curl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

url=""
body=""
read_body_next=0
for arg in "$@"; do
  if [[ "$read_body_next" == "1" ]]; then
    body="$arg"
    read_body_next=0
    continue
  fi

  case "$arg" in
    http*) url="$arg" ;;
    -d) read_body_next=1 ;;
  esac
done

if [[ -n "${FAKE_CURL_LOG:-}" ]]; then
  {
    printf 'URL:%s\n' "$url"
    printf 'BODY:%s\n' "$body"
  } >>"$FAKE_CURL_LOG"
fi

case "$url" in
  */auth/status*)
    if [[ -n "${FAKE_AUTH_RESPONSE:-}" ]]; then
      printf '%s' "$FAKE_AUTH_RESPONSE"
    else
      printf '{"status":"200","data":{"name":"测试用户","empId":"123456"}}'
    fi
    ;;
  */workspace-memory/spaces|*/workspace-memory/spaces\?*)
    printf '{"status":"200","data":[{"id":5,"name":"KBase 工程空间","description":"KBase 团队共享记忆","tenant":"workspace_5","creatorEmpId":"123456","roleCode":"owner","accessLevel":"readwrite","status":"active","memberCount":3,"members":null,"gmtCreate":"2026-05-25T06:13:37.000+00:00","gmtModified":"2026-05-25T06:13:37.000+00:00"}]}'
    ;;
  */smart-search*|*/search/hierarchical*)
    printf '{"status":"200","data":[{"id":"vec-1","content":"found","memoryId":"mem-1","score":0.8,"sourceNode":{"id":14862,"memoryId":"source-mem-1","name":"记忆","path":"/其他/记忆","nodeType":"memory","score":0.0,"enhanced":false,"parentPath":"/其他/"},"retrievalCount":null,"firstRetrievedAt":null,"lastRetrievedAt":null,"thumbsUpCount":null,"thumbsDownCount":null,"isStale":null,"heatScore":null}]}'
    ;;
  */smart-ingest*|*/smart-update*|*/update*|*/delete*)
    printf '{"status":"200","data":{"writeSuccess":true,"targetNode":{"path":"/研发流程"}}}'
    ;;
  */tree*)
    printf '{"status":"200","data":[{"id":1,"memoryId":"mem-1","name":"空间共识","path":"/空间共识/","nodeType":"folder","description":"AI 每次对话都要知道的空间记忆背景","targetType":"workspace","targetId":"/空间共识/","tenant":"workspace_5","sortOrder":4,"parentId":null,"gmtCreate":"2026-05-25T06:13:37.000+00:00","gmtModified":"2026-05-25T06:13:37.000+00:00","prompt":null,"compressPrompt":null,"staffId":null,"repoId":null,"children":[{"id":2,"memoryId":"mem-2","name":"记忆","path":"/空间共识/记忆","nodeType":"memory","description":"保存空间记忆背景","targetType":"workspace","tenant":"workspace_5"}]}]}'
    ;;
  *)
    printf '{"status":"200","data":[]}'
    ;;
esac
SH
  chmod +x "$bin_dir/curl"
  echo "$bin_dir"
}

require_jq

# --- help and dispatch ---
out=$(run_isolated_script "$MEMORY" "$(tmp_home)" help 2>&1) || true
if ! echo "$out" | grep -q "memory auth"; then
  die "memory help should mention auth"
elif ! echo "$out" | grep -q "user-memory"; then
  die "memory help should mention user-memory"
elif ! echo "$out" | grep -q "space-memory"; then
  die "memory help should mention space-memory"
elif echo "$out" | grep -q "smart-search"; then
  die "memory help should not expose old smart-search command"
else
  pass "memory help lists auth and split memory CLIs"
fi

out=$(run_isolated_script "$USER_MEMORY" "$(tmp_home)" help 2>&1) || true
if ! echo "$out" | grep -q "user-memory search"; then
  die "user-memory help should mention search"
elif ! echo "$out" | grep -q "user-memory add"; then
  die "user-memory help should mention add"
else
  pass "user-memory help lists personal memory commands"
fi

out=$(run_isolated_script "$SPACE_MEMORY" "$(tmp_home)" help 2>&1) || true
if ! echo "$out" | grep -q "space-memory list"; then
  die "space-memory help should mention list"
elif ! echo "$out" | grep -q "space-memory search"; then
  die "space-memory help should mention search"
elif ! echo "$out" | grep -q "space-memory add"; then
  die "space-memory help should mention add"
else
  pass "space-memory help lists space memory commands"
fi

code=0
out=$(run_isolated_script "$MEMORY" "$(tmp_home)" tree 2>&1) || code=$?
if [[ "$code" -eq 0 ]]; then
  die "memory tree should not be available after CLI split"
elif ! echo "$out" | grep -qi "unknown command"; then
  die "memory tree should fail with unknown command"
else
  pass "memory no longer exposes memory tree command"
fi

code=0
out=$(run_isolated_script "$MEMORY" "$(tmp_home)" not_a_real_command 2>&1) || code=$?
if [[ "$code" -eq 0 ]]; then
  die "unknown memory command should exit non-zero"
elif ! echo "$out" | grep -qi "unknown command"; then
  die "unknown memory command should mention Unknown command"
else
  pass "unknown memory command fails clearly"
fi

code=0
out=$(run_isolated_script "$USER_MEMORY" "$(tmp_home)" not_a_real_command 2>&1) || code=$?
if [[ "$code" -eq 0 ]]; then
  die "unknown user-memory command should exit non-zero"
elif ! echo "$out" | grep -qi "unknown user-memory command"; then
  die "unknown user-memory command should mention command type"
else
  pass "unknown user-memory command fails clearly"
fi

code=0
out=$(run_isolated_script "$SPACE_MEMORY" "$(tmp_home)" not_a_real_command 2>&1) || code=$?
if [[ "$code" -eq 0 ]]; then
  die "unknown space-memory command should exit non-zero"
elif ! echo "$out" | grep -qi "unknown space-memory command"; then
  die "unknown space-memory command should mention command type"
else
  pass "unknown space-memory command fails clearly"
fi

# --- auth required paths and usage ---
h=$(tmp_home)
code=0
out=$(run_isolated_script "$USER_MEMORY" "$h" search "anything" 2>&1) || code=$?
if [[ "$code" -eq 0 ]]; then
  die "user-memory search without config should fail"
elif ! echo "$out" | grep -q "Memory not configured"; then
  die "user-memory search without config should say Memory not configured"
else
  pass "user-memory search without auth/config errors as expected"
fi

h=$(tmp_home)
code=0
out=$(run_isolated_script "$USER_MEMORY" "$h" tree 2>&1) || code=$?
if [[ "$code" -eq 0 ]]; then
  die "user-memory tree without config should fail"
elif ! echo "$out" | grep -q "Memory not configured"; then
  die "user-memory tree without config should say Memory not configured"
else
  pass "user-memory tree without auth/config errors as expected"
fi

h=$(tmp_home)
code=0
out=$(run_isolated_script "$SPACE_MEMORY" "$h" list 2>&1) || code=$?
if [[ "$code" -eq 0 ]]; then
  die "space-memory list without config should fail"
elif ! echo "$out" | grep -q "Memory not configured"; then
  die "space-memory list without config should say Memory not configured"
else
  pass "space-memory list without auth/config errors as expected"
fi

h=$(tmp_home)
code=0
out=$(run_isolated_script "$SPACE_MEMORY" "$h" tree 5 2>&1) || code=$?
if [[ "$code" -eq 0 ]]; then
  die "space-memory tree without config should fail"
elif ! echo "$out" | grep -q "Memory not configured"; then
  die "space-memory tree without config should say Memory not configured"
else
  pass "space-memory tree without auth/config errors as expected"
fi

h=$(tmp_home)
code=0
out=$(printf '' | run_isolated_script "$MEMORY" "$h" auth 2>&1) || code=$?
if [[ "$code" -eq 0 ]]; then
  die "memory auth without config/input should fail"
elif ! echo "$out" | grep -q "Memory Service Setup"; then
  die "memory auth without config should start setup"
elif ! echo "$out" | grep -q "authTicket cannot be empty"; then
  die "memory auth without config/input should fail on empty authTicket"
elif echo "$out" | grep -q "API error"; then
  die "memory auth without config should not expose API error"
else
  pass "memory auth without auth/config starts setup"
fi

h=$(tmp_home)
code=0
out=$(run_isolated_script "$USER_MEMORY" "$h" search 2>&1) || code=$?
if [[ "$code" -eq 0 ]]; then
  die "user-memory search with missing query should fail"
elif ! echo "$out" | grep -qi "usage"; then
  die "user-memory search with missing query should show usage"
else
  pass "user-memory search missing query shows usage"
fi

h=$(tmp_home)
code=0
out=$(run_isolated_script "$USER_MEMORY" "$h" add 2>&1) || code=$?
if [[ "$code" -eq 0 ]]; then
  die "user-memory add with missing content should fail"
elif ! echo "$out" | grep -qi "usage"; then
  die "user-memory add with missing content should show usage"
else
  pass "user-memory add missing content shows usage"
fi

h=$(tmp_home)
code=0
out=$(run_isolated_script "$USER_MEMORY" "$h" update 2>&1) || code=$?
if [[ "$code" -eq 0 ]]; then
  die "user-memory update with missing args should fail"
elif ! echo "$out" | grep -qi "usage"; then
  die "user-memory update with missing args should show usage"
else
  pass "user-memory update missing args shows usage"
fi

h=$(tmp_home)
code=0
out=$(run_isolated_script "$USER_MEMORY" "$h" delete 2>&1) || code=$?
if [[ "$code" -eq 0 ]]; then
  die "user-memory delete with no id should fail"
elif ! echo "$out" | grep -qi "usage"; then
  die "user-memory delete with no id should show usage"
else
  pass "user-memory delete missing id shows usage"
fi

h=$(tmp_home)
code=0
out=$(run_isolated_script "$SPACE_MEMORY" "$h" tree 2>&1) || code=$?
if [[ "$code" -eq 0 ]]; then
  die "space-memory tree missing spaceId should fail"
elif ! echo "$out" | grep -qi "usage"; then
  die "space-memory tree missing spaceId should show usage"
else
  pass "space-memory tree missing spaceId shows usage"
fi

h=$(tmp_home)
code=0
out=$(run_isolated_script "$SPACE_MEMORY" "$h" add 123 2>&1) || code=$?
if [[ "$code" -eq 0 ]]; then
  die "space-memory add missing content should fail"
elif ! echo "$out" | grep -qi "usage"; then
  die "space-memory add missing content should show usage"
else
  pass "space-memory add missing content shows usage"
fi

h=$(tmp_home)
code=0
out=$(run_isolated_script "$SPACE_MEMORY" "$h" search 123 2>&1) || code=$?
if [[ "$code" -eq 0 ]]; then
  die "space-memory search missing query should fail"
elif ! echo "$out" | grep -qi "usage"; then
  die "space-memory search missing query should show usage"
else
  pass "space-memory search missing query shows usage"
fi

h=$(tmp_home)
code=0
out=$(run_isolated_script "$SPACE_MEMORY" "$h" update 123 2>&1) || code=$?
if [[ "$code" -eq 0 ]]; then
  die "space-memory update missing args should fail"
elif ! echo "$out" | grep -qi "usage"; then
  die "space-memory update missing args should show usage"
else
  pass "space-memory update missing args shows usage"
fi

h=$(tmp_home)
code=0
out=$(run_isolated_script "$SPACE_MEMORY" "$h" delete 123 2>&1) || code=$?
if [[ "$code" -eq 0 ]]; then
  die "space-memory delete missing id should fail"
elif ! echo "$out" | grep -qi "usage"; then
  die "space-memory delete missing id should show usage"
else
  pass "space-memory delete missing id shows usage"
fi

# --- fake API checks ---
fake_bin=$(fake_curl_bin)
fake_log=$(mktemp "${TMPDIR:-/tmp}/memory-test-curl.XXXXXX")
h=$(tmp_home)
code=0
out=$(env -i PATH="$fake_bin:$PATH" HOME="$h" KBase_AuthTicket="ticket" FAKE_CURL_LOG="$fake_log" \
  bash "$MEMORY" auth 2>&1) || code=$?
if [[ "$code" -ne 0 ]]; then
  die "memory auth with fake API should succeed: $out"
elif ! echo "$out" | grep -q "123456"; then
  die "memory auth should print response data"
elif ! grep -q "/auth/status" "$fake_log"; then
  die "memory auth should call auth status endpoint"
else
  pass "memory auth calls expected endpoint"
fi

: >"$fake_log"
code=0
out=$(env -i PATH="$fake_bin:$PATH" HOME="$h" KBase_AuthTicket="ticket" FAKE_CURL_LOG="$fake_log" \
  bash "$MEMORY" auth status 2>&1) || code=$?
if [[ "$code" -ne 0 ]]; then
  die "memory auth status should succeed: $out"
elif ! echo "$out" | grep -q "123456"; then
  die "memory auth status should print response data"
elif ! grep -q "/auth/status" "$fake_log"; then
  die "memory auth status should call auth status endpoint"
else
  pass "memory auth status calls expected endpoint"
fi

: >"$fake_log"
code=0
out=$(printf '' | env -i PATH="$fake_bin:$PATH" HOME="$h" KBase_AuthTicket="ticket" FAKE_CURL_LOG="$fake_log" \
  FAKE_AUTH_RESPONSE='{"status":"401","message":"认证失败，请提供 authTicket"}' \
  bash "$MEMORY" auth 2>&1) || code=$?
if [[ "$code" -eq 0 ]]; then
  die "memory auth with invalid response should fail"
elif ! echo "$out" | grep -q "Memory Service Setup"; then
  die "memory auth with invalid response should start setup"
elif echo "$out" | grep -q "API error"; then
  die "memory auth with invalid response should not expose API error"
elif echo "$out" | grep -q "认证失败"; then
  die "memory auth with invalid response should not expose backend auth message"
else
  pass "memory auth invalid response starts setup without raw API error"
fi

h=$(tmp_home)
: >"$fake_log"
code=0
out=$(printf 'ticket\n' | env -i PATH="$fake_bin:$PATH" HOME="$h" FAKE_CURL_LOG="$fake_log" \
  bash "$MEMORY" setup 2>&1) || code=$?
if [[ "$code" -ne 0 ]]; then
  die "memory setup with manual auth should succeed: $out"
elif ! echo "$out" | grep -q "Configuration saved"; then
  die "memory setup should save config"
elif [[ "$(cat "$h/.memory/config.json")" != '{"authTicket":"ticket"}' ]]; then
  die "memory setup should write authTicket"
else
  pass "memory setup saves verified config"
fi

: >"$fake_log"
code=0
out=$(env -i PATH="$fake_bin:$PATH" HOME="$h" KBase_AuthTicket="ticket" FAKE_CURL_LOG="$fake_log" \
  bash "$USER_MEMORY" tree 2>&1) || code=$?
if [[ "$code" -ne 0 ]]; then
  die "user-memory tree with fake API should succeed: $out"
elif ! echo "$out" | grep -q "/空间共识/记忆"; then
  die "user-memory tree should print tree data"
elif echo "$out" | grep -q "targetType"; then
  die "user-memory tree should omit internal node metadata"
elif echo "$out" | grep -q "description"; then
  die "user-memory tree should omit description"
elif ! grep -q "/memory/tree" "$fake_log"; then
  die "user-memory tree should call personal tree endpoint"
else
  pass "user-memory tree omits internal node metadata and calls expected endpoint"
fi

: >"$fake_log"
code=0
out=$(env -i PATH="$fake_bin:$PATH" HOME="$h" KBase_AuthTicket="ticket" FAKE_CURL_LOG="$fake_log" \
  bash "$SPACE_MEMORY" list 2>&1) || code=$?
if [[ "$code" -ne 0 ]]; then
  die "space-memory list with fake API should succeed: $out"
elif ! echo "$out" | grep -q "KBase 工程空间"; then
  die "space-memory list should print authorized spaces"
elif ! echo "$out" | grep -q '"id": 5'; then
  die "space-memory list should include space id"
elif echo "$out" | grep -q "creatorEmpId"; then
  die "space-memory list should omit creatorEmpId"
elif echo "$out" | grep -q "gmtCreate"; then
  die "space-memory list should omit gmtCreate"
elif ! grep -q "/workspace-memory/spaces" "$fake_log"; then
  die "space-memory list should call workspace spaces endpoint"
else
  pass "space-memory list calls expected endpoint and omits internal metadata"
fi

: >"$fake_log"
code=0
out=$(env -i PATH="$fake_bin:$PATH" HOME="$h" KBase_AuthTicket="ticket" FAKE_CURL_LOG="$fake_log" \
  bash "$SPACE_MEMORY" tree 5 2>&1) || code=$?
if [[ "$code" -ne 0 ]]; then
  die "space-memory tree with fake API should succeed: $out"
elif ! echo "$out" | grep -q "/空间共识/记忆"; then
  die "space-memory tree should print tree data"
elif echo "$out" | grep -q "targetType"; then
  die "space-memory tree should omit internal node metadata"
elif echo "$out" | grep -q "description"; then
  die "space-memory tree should omit description"
elif ! grep -q "/workspace-memory/spaces/5/tree" "$fake_log"; then
  die "space-memory tree should call workspace tree endpoint"
else
  pass "space-memory tree omits internal node metadata and calls expected endpoint"
fi

: >"$fake_log"
code=0
out=$(env -i PATH="$fake_bin:$PATH" HOME="$h" KBase_AuthTicket="ticket" FAKE_CURL_LOG="$fake_log" \
  bash "$USER_MEMORY" search "kbase工程" 2>&1) || code=$?
if [[ "$code" -ne 0 ]]; then
  die "user-memory search with fake API should succeed: $out"
elif ! echo "$out" | grep -q "vec-1"; then
  die "user-memory search should print response data"
elif echo "$out" | grep -q "retrievalCount"; then
  die "user-memory search should omit retrieval metadata"
elif echo "$out" | grep -q "memoryId"; then
  die "user-memory search should omit memoryId"
elif echo "$out" | grep -q "parentPath"; then
  die "user-memory search should omit sourceNode internal metadata"
elif ! grep -q "/memory/search/hierarchical" "$fake_log"; then
  die "user-memory search should call personal search endpoint"
else
  pass "user-memory search omits metadata and calls expected endpoint"
fi

: >"$fake_log"
code=0
out=$(env -i PATH="$fake_bin:$PATH" HOME="$h" KBase_AuthTicket="ticket" FAKE_CURL_LOG="$fake_log" \
  bash "$USER_MEMORY" add "个人偏好" --infer --target-path "/偏好习惯/记忆" 2>&1) || code=$?
if [[ "$code" -ne 0 ]]; then
  die "user-memory add with fake API should succeed: $out"
elif ! echo "$out" | grep -q "writeSuccess"; then
  die "user-memory add should print response data"
elif ! grep -q "/memory/smart-ingest" "$fake_log"; then
  die "user-memory add should call personal smart-ingest endpoint"
elif ! grep -q '"enableInference": true' "$fake_log"; then
  die "user-memory add should send enableInference=true"
elif ! grep -q '"targetPath": "/偏好习惯/记忆"' "$fake_log"; then
  die "user-memory add should send targetPath"
else
  pass "user-memory add calls expected endpoint and body"
fi

: >"$fake_log"
code=0
out=$(env -i PATH="$fake_bin:$PATH" HOME="$h" KBase_AuthTicket="ticket" FAKE_CURL_LOG="$fake_log" \
  bash "$USER_MEMORY" update vec-1 "更新后的内容" 2>&1) || code=$?
if [[ "$code" -ne 0 ]]; then
  die "user-memory update with fake API should succeed: $out"
elif ! grep -q "/memory/update" "$fake_log"; then
  die "user-memory update should call personal update endpoint"
elif ! grep -q '"id": "vec-1"' "$fake_log"; then
  die "user-memory update should send id"
elif ! grep -q '"content": "更新后的内容"' "$fake_log"; then
  die "user-memory update should send content"
else
  pass "user-memory update calls expected endpoint and body"
fi

: >"$fake_log"
code=0
out=$(env -i PATH="$fake_bin:$PATH" HOME="$h" KBase_AuthTicket="ticket" FAKE_CURL_LOG="$fake_log" \
  bash "$USER_MEMORY" delete vec-1 2>&1) || code=$?
if [[ "$code" -ne 0 ]]; then
  die "user-memory delete with fake API should succeed: $out"
elif ! grep -q "/memory/delete" "$fake_log"; then
  die "user-memory delete should call personal delete endpoint"
elif ! grep -q '"id": "vec-1"' "$fake_log"; then
  die "user-memory delete should send id"
else
  pass "user-memory delete calls expected endpoint and body"
fi

: >"$fake_log"
code=0
out=$(env -i PATH="$fake_bin:$PATH" HOME="$h" KBase_AuthTicket="ticket" FAKE_CURL_LOG="$fake_log" \
  bash "$SPACE_MEMORY" search 123 "发布流程" 2 4 2>&1) || code=$?
if [[ "$code" -ne 0 ]]; then
  die "space-memory search with fake API should succeed: $out"
elif ! echo "$out" | grep -q "vec-1"; then
  die "space-memory search should print response data"
elif echo "$out" | grep -q "retrievalCount"; then
  die "space-memory search should omit retrieval metadata"
elif echo "$out" | grep -q "memoryId"; then
  die "space-memory search should omit memoryId"
elif echo "$out" | grep -q "parentPath"; then
  die "space-memory search should omit sourceNode internal metadata"
elif ! grep -q "/workspace-memory/spaces/123/smart-search" "$fake_log"; then
  die "space-memory search should call workspace smart-search endpoint"
elif ! grep -q '"query": "发布流程"' "$fake_log"; then
  die "space-memory search should send query in request body"
elif ! grep -q '"memoriesPerNode": 2' "$fake_log"; then
  die "space-memory search should send memoriesPerNode in request body"
elif ! grep -q '"totalLimit": 4' "$fake_log"; then
  die "space-memory search should send totalLimit in request body"
else
  pass "space-memory search calls expected endpoint and body"
fi

: >"$fake_log"
code=0
out=$(env -i PATH="$fake_bin:$PATH" HOME="$h" KBase_AuthTicket="ticket" FAKE_CURL_LOG="$fake_log" \
  bash "$SPACE_MEMORY" add 123 "发布前完成灰度验证" --infer --target-path "/研发流程" 2>&1) || code=$?
if [[ "$code" -ne 0 ]]; then
  die "space-memory add with fake API should succeed: $out"
elif ! echo "$out" | grep -q "writeSuccess"; then
  die "space-memory add should print response data"
elif ! grep -q "/workspace-memory/spaces/123/smart-ingest" "$fake_log"; then
  die "space-memory add should call workspace smart-ingest endpoint"
elif ! grep -q '"enableInference": true' "$fake_log"; then
  die "space-memory add should send enableInference=true"
elif ! grep -q '"targetPath": "/研发流程"' "$fake_log"; then
  die "space-memory add should send targetPath"
else
  pass "space-memory add calls expected endpoint and body"
fi

: >"$fake_log"
code=0
out=$(env -i PATH="$fake_bin:$PATH" HOME="$h" KBase_AuthTicket="ticket" FAKE_CURL_LOG="$fake_log" \
  bash "$SPACE_MEMORY" update 123 vec-1 "更新后的内容" 2>&1) || code=$?
if [[ "$code" -ne 0 ]]; then
  die "space-memory update with fake API should succeed: $out"
elif ! grep -q "/workspace-memory/spaces/123/smart-update" "$fake_log"; then
  die "space-memory update should call workspace smart-update endpoint"
elif ! grep -q '"id": "vec-1"' "$fake_log"; then
  die "space-memory update should send id"
elif ! grep -q '"content": "更新后的内容"' "$fake_log"; then
  die "space-memory update should send content"
else
  pass "space-memory update calls expected endpoint and body"
fi

: >"$fake_log"
code=0
out=$(env -i PATH="$fake_bin:$PATH" HOME="$h" KBase_AuthTicket="ticket" FAKE_CURL_LOG="$fake_log" \
  bash "$SPACE_MEMORY" delete 123 vec-1 2>&1) || code=$?
if [[ "$code" -ne 0 ]]; then
  die "space-memory delete with fake API should succeed: $out"
elif ! grep -q "/workspace-memory/spaces/123/delete" "$fake_log"; then
  die "space-memory delete should call workspace delete endpoint"
elif ! grep -q '"id": "vec-1"' "$fake_log"; then
  die "space-memory delete should send id"
else
  pass "space-memory delete calls expected endpoint and body"
fi

# --- optional live API checks ---
if [[ "${MEMORY_INTEGRATION:-}" == "1" ]]; then
  if [[ -z "${KBase_AuthTicket:-}" ]]; then
    echo "SKIP integration: set KBase_AuthTicket" >&2
  else
    h=$(tmp_home)
    mkdir -p "$h/.memory"
    echo "{\"authTicket\":\"$KBase_AuthTicket\"}" >"$h/.memory/config.json"
    chmod 600 "$h/.memory/config.json"
    code=0
    out=$(env -i PATH="$PATH" HOME="$h" bash "$USER_MEMORY" search "cli smoke integration" 1 2>&1) || code=$?
    if [[ "$code" -ne 0 ]]; then
      die "integration user-memory search failed: $out"
    else
      pass "integration user-memory search returns OK"
    fi
  fi
else
  echo "(integration tests skipped; set MEMORY_INTEGRATION=1 KBase_AuthTicket=... to run)"
fi

if [[ "$failures" -gt 0 ]]; then
  echo -e "${RED}$failures test(s) failed${NC}" >&2
  exit 1
fi
echo "All CLI smoke tests passed."
