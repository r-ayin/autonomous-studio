VERSION="4.0.0"
BASE_URL="${MEMORY_BASE_URL:-https://km.aone.alibaba-inc.com/api/open/v2/memory}"
AUTH_BASE_URL="${MEMORY_AUTH_BASE_URL:-https://km.aone.alibaba-inc.com/api/open/v2/auth}"
WORKSPACE_BASE_URL="${MEMORY_WORKSPACE_BASE_URL:-https://km.aone.alibaba-inc.com/api/open/v2/workspace-memory}"
CONFIG_FILE="${HOME}/.memory/config.json"
# Open memory APIs accept optional invokeSource for audit; default identifies Skill usage.
MEMORY_INVOKE_SOURCE="${MEMORY_INVOKE_SOURCE:-Skill}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

error() {
  echo -e "${RED}Error: $1${NC}" >&2
  exit 1
}

warn() {
  echo -e "${YELLOW}Warning: $1${NC}" >&2
}

info() {
  echo -e "${BLUE}$1${NC}" >&2
}

success() {
  echo -e "${GREEN}OK: $1${NC}" >&2
}

require_jq() {
  if ! command -v jq &>/dev/null; then
    error "jq is required but not installed. Install it with: brew install jq"
  fi
}

with_invoke_source_param() {
  local url="$1"
  local separator='?'
  local encoded_invoke_source
  if [[ "$url" == *\?* ]]; then
    separator='&'
  fi
  encoded_invoke_source=$(printf '%s' "${MEMORY_INVOKE_SOURCE}" | jq -sRr @uri)
  echo "${url}${separator}invokeSource=${encoded_invoke_source}"
}

read_config_auth_ticket() {
  local auth_ticket=""

  if [ -f "$CONFIG_FILE" ]; then
    auth_ticket=$(grep -o '"authTicket":"[^"]*"' "$CONFIG_FILE" 2>/dev/null | cut -d'"' -f4 || true)
  fi

  echo "$auth_ticket"
}

get_auth_ticket_optional() {
  local auth_ticket=""

  if [ -n "${KBase_AuthTicket:-}" ]; then
    auth_ticket="$KBase_AuthTicket"
  else
    auth_ticket=$(read_config_auth_ticket)
  fi

  echo "$auth_ticket"
}

get_auth_ticket() {
  local auth_ticket
  auth_ticket=$(get_auth_ticket_optional)

  if [ -z "$auth_ticket" ]; then
    error "Memory not configured. Please run: memory setup"
  fi

  echo "$auth_ticket"
}

api_get_response_with_ticket() {
  local url="$1"
  local auth_ticket="$2"

  curl -s -X GET "$(with_invoke_source_param "$url")" \
    -H "authTicket: $auth_ticket"
}

api_get_response() {
  local url="$1"
  local auth_ticket
  auth_ticket=$(get_auth_ticket)

  api_get_response_with_ticket "$url" "$auth_ticket"
}

api_post_json_response() {
  local url="$1"
  local json_body="$2"
  local auth_ticket
  auth_ticket=$(get_auth_ticket)

  curl -s -X POST "$(with_invoke_source_param "$url")" \
    -H "authTicket: $auth_ticket" \
    -H 'Content-Type: application/json' \
    -d "$json_body"
}

check_v2_response() {
  local response="$1"

  if ! echo "$response" | jq empty 2>/dev/null; then
    error "Invalid response from server"
  fi

  local status
  status=$(echo "$response" | jq -r '.status')

  if [ "$status" != "200" ]; then
    local message
    message=$(echo "$response" | jq -r '.message // "Unknown error"')
    error "API error: $message"
  fi
}

print_response_data() {
  local response="$1"
  echo "$response" | jq -r '.data'
}

print_search_response_data() {
  local response="$1"
  echo "$response" | jq -r '
    def strip_search_metadata:
      if type == "array" then
        map(strip_search_metadata)
      elif type == "object" then
        with_entries(.value |= strip_search_metadata)
        | del(
          .memoryId,
          .retrievalCount,
          .firstRetrievedAt,
          .lastRetrievedAt,
          .thumbsUpCount,
          .thumbsDownCount,
          .isStale,
          .heatScore,
          .sourceNode.id,
          .sourceNode.score,
          .sourceNode.enhanced,
          .sourceNode.parentPath
        )
      else
        .
      end;
    .data | strip_search_metadata
  '
}

print_tree_response_data() {
  local response="$1"
  echo "$response" | jq -r '
    def strip_tree_metadata:
      if type == "array" then
        map(strip_tree_metadata)
      elif type == "object" then
        with_entries(.value |= strip_tree_metadata)
        | del(
          .targetType,
          .targetId,
          .tenant,
          .sortOrder,
          .parentId,
          .description,
          .gmtCreate,
          .gmtModified,
          .prompt,
          .compressPrompt,
          .staffId,
          .repoId
        )
        | with_entries(select(.value != null))
      else
        .
      end;
    .data | strip_tree_metadata
  '
}

print_space_list_response_data() {
  local response="$1"
  echo "$response" | jq -r '
    .data
    | if type == "array" then
        map(
          del(.creatorEmpId, .gmtCreate, .gmtModified, .members)
          | with_entries(select(.value != null))
        )
      else
        .
      end
  '
}

require_no_extra_args() {
  local usage="$1"
  shift
  if [ "$#" -gt 0 ]; then
    error "Usage: $usage"
  fi
}

auth_status_response() {
  local auth_ticket="$1"
  api_get_response_with_ticket "${AUTH_BASE_URL}/status" "$auth_ticket"
}

is_auth_status_ready() {
  local response="$1"
  echo "$response" | jq -e '
    .status == "200"
    and (.data | type == "object")
    and (.data.name | type == "string" and length > 0)
    and (.data.empId | type == "string" and length > 0)
  ' >/dev/null 2>&1
}

cmd_setup() {
  info "Memory Service Setup v${VERSION}"
  echo ""

  local current_auth_ticket
  current_auth_ticket=$(get_auth_ticket_optional)
  if [ -n "$current_auth_ticket" ]; then
    local current_response
    current_response=$(auth_status_response "$current_auth_ticket")
    if is_auth_status_ready "$current_response"; then
      success "Memory auth is already configured"
      print_response_data "$current_response"
      exit 0
    fi
  fi

  if [ -n "${KBase_AuthTicket:-}" ]; then
    warn "KBase_AuthTicket is set, but authentication failed."
  fi

  info "Get your authTicket from: https://kbase.alibaba-inc.com/#/private-token"
  echo ""
  local auth_ticket
  if ! read -p "Enter your authTicket: " -r auth_ticket; then
    echo
    error "authTicket cannot be empty"
  fi
  echo

  if [ -z "$auth_ticket" ]; then
    error "authTicket cannot be empty"
  fi

  local response
  response=$(auth_status_response "$auth_ticket")
  if ! is_auth_status_ready "$response"; then
    error "authTicket is invalid or expired. Please get a new Private Token and try again."
  fi

  mkdir -p "$(dirname "$CONFIG_FILE")"
  echo "{\"authTicket\":\"$auth_ticket\"}" >"$CONFIG_FILE"
  chmod 600 "$CONFIG_FILE"
  success "Configuration saved to $CONFIG_FILE"

  success "Memory auth is ready"
  print_response_data "$response"
  echo
  if [ -n "${KBase_AuthTicket:-}" ] && [ "$KBase_AuthTicket" != "$auth_ticket" ]; then
    warn "KBase_AuthTicket is still set and has priority over $CONFIG_FILE."
    warn "If later commands still fail, update or unset KBase_AuthTicket."
  fi
}

memory_usage() {
  cat <<EOF
Memory auth CLI v${VERSION}

USAGE:
  memory <command> [arguments]

COMMANDS:
  memory setup        Configure authTicket
  memory auth         Show current OpenAPI identity
  memory auth status  Show current OpenAPI identity
  memory help         Show this help message

MEMORY COMMANDS:
  user-memory <command>   Read/write personal memories
  space-memory <command>  Read/write space memories

CONFIGURATION:
  Priority: KBase_AuthTicket env var > ~/.memory/config.json
  Get authTicket from: https://kbase.alibaba-inc.com/#/private-token
EOF
}

auth_usage() {
  cat <<EOF
USAGE:
  memory auth
  memory auth status
EOF
}

cmd_auth_status() {
  local usage="$1"
  shift
  require_no_extra_args "$usage" "$@"

  local auth_ticket
  auth_ticket=$(get_auth_ticket_optional)
  if [ -z "$auth_ticket" ]; then
    cmd_setup
    return
  fi

  local response
  response=$(auth_status_response "$auth_ticket")

  if is_auth_status_ready "$response"; then
    print_response_data "$response"
    return
  fi

  cmd_setup
}

cmd_auth() {
  if [ "$#" -eq 0 ]; then
    cmd_auth_status "memory auth"
    return
  fi

  local command="$1"
  shift

  case "$command" in
    status)
      cmd_auth_status "memory auth status" "$@"
      ;;
    help|--help|-h)
      auth_usage
      ;;
    *)
      error "Unknown auth command: $command\nRun 'memory auth help' for usage"
      ;;
  esac
}

memory_main() {
  require_jq

  local command="${1:-help}"
  shift || true

  case "$command" in
    setup)
      cmd_setup "$@"
      ;;
    auth)
      cmd_auth "$@"
      ;;
    help|--help|-h)
      memory_usage
      ;;
    *)
      error "Unknown command: $command\nRun 'memory help' for usage"
      ;;
  esac
}

user_memory_usage() {
  cat <<EOF
User memory CLI v${VERSION}

USAGE:
  user-memory <command> [arguments]

COMMANDS:
  user-memory tree
  user-memory search <query> [memoriesPerNode] [totalLimit] [--scope-paths <p1,p2>] [--scope-path <path>]
  user-memory add <content> [--infer] [--target-path <path>]
  user-memory update <id> <content>
  user-memory delete <id>
  user-memory help

AUTH:
  Run 'memory auth' first when authentication is not configured.
EOF
}

cmd_user_tree() {
  require_no_extra_args "user-memory tree" "$@"

  local response
  response=$(api_get_response "${BASE_URL}/tree")
  check_v2_response "$response"
  print_tree_response_data "$response"
}

cmd_user_add() {
  local content=""
  local enable_inference="false"
  local target_path=""

  while [ $# -gt 0 ]; do
    case "$1" in
      --infer)
        enable_inference="true"
        shift
        ;;
      --target-path|--targetPath|--path)
        if [ $# -lt 2 ] || [[ "$2" == --* ]]; then
          error "user-memory add requires a value for $1"
        fi
        target_path="$2"
        shift 2
        ;;
      --target-path=*|--targetPath=*|--path=*)
        target_path="${1#*=}"
        shift
        ;;
      --*)
        error "Unknown option for user-memory add: $1"
        ;;
      *)
        [ -z "$content" ] && content="$1" || content="$content $1"
        shift
        ;;
    esac
  done

  if [ -z "$content" ]; then
    error "Usage: user-memory add <content> [--infer] [--target-path <path>]"
  fi

  local json_body
  json_body=$(jq -n --arg c "$content" --argjson ei "$enable_inference" \
    '{content: $c, enableInference: $ei}')
  if [ -n "$target_path" ]; then
    json_body=$(echo "$json_body" | jq --arg tp "$target_path" '. + {targetPath: $tp}')
  fi

  local response
  response=$(api_post_json_response "${BASE_URL}/smart-ingest" "$json_body")
  check_v2_response "$response"

  local write_success target_path
  write_success=$(echo "$response" | jq -r '.data.writeSuccess')
  target_path=$(echo "$response" | jq -r '.data.targetNode.path')

  if [ "$write_success" = "true" ]; then
    success "User memory saved to ${target_path}"
  else
    error "User memory write failed at ${target_path}"
  fi

  print_response_data "$response"
}

cmd_user_search() {
  local query=""
  local memories_per_node="3"
  local total_limit="10"
  local positional_index=0
  local -a scope_paths=()

  while [ $# -gt 0 ]; do
    case "$1" in
      --scope-path|--scopePath)
        if [ $# -lt 2 ] || [[ "$2" == --* ]]; then
          error "user-memory search requires a value for $1"
        fi
        scope_paths+=("$2")
        shift 2
        ;;
      --scope-path=*|--scopePath=*)
        scope_paths+=("${1#*=}")
        shift
        ;;
      --scope-paths|--scopePaths)
        if [ $# -lt 2 ] || [[ "$2" == --* ]]; then
          error "user-memory search requires a value for $1"
        fi
        IFS=',' read -r -a parsed_scope_paths <<<"$2"
        for scope_path in "${parsed_scope_paths[@]}"; do
          [ -n "$scope_path" ] && scope_paths+=("$scope_path")
        done
        shift 2
        ;;
      --scope-paths=*|--scopePaths=*)
        local raw_scope_paths="${1#*=}"
        IFS=',' read -r -a parsed_scope_paths <<<"$raw_scope_paths"
        for scope_path in "${parsed_scope_paths[@]}"; do
          [ -n "$scope_path" ] && scope_paths+=("$scope_path")
        done
        shift
        ;;
      --memories-per-node|--memoriesPerNode)
        if [ $# -lt 2 ] || [[ "$2" == --* ]]; then
          error "user-memory search requires a value for $1"
        fi
        memories_per_node="$2"
        shift 2
        ;;
      --memories-per-node=*|--memoriesPerNode=*)
        memories_per_node="${1#*=}"
        shift
        ;;
      --total-limit|--totalLimit)
        if [ $# -lt 2 ] || [[ "$2" == --* ]]; then
          error "user-memory search requires a value for $1"
        fi
        total_limit="$2"
        shift 2
        ;;
      --total-limit=*|--totalLimit=*)
        total_limit="${1#*=}"
        shift
        ;;
      --*)
        error "Unknown option for user-memory search: $1"
        ;;
      *)
        case "$positional_index" in
          0) query="$1" ;;
          1) memories_per_node="$1" ;;
          2) total_limit="$1" ;;
          *) error "Usage: user-memory search <query> [memoriesPerNode] [totalLimit] [--scope-paths <path1,path2>] [--scope-path <path>]" ;;
        esac
        positional_index=$((positional_index + 1))
        shift
        ;;
    esac
  done

  if [ -z "$query" ]; then
    error "Usage: user-memory search <query> [memoriesPerNode] [totalLimit] [--scope-paths <path1,path2>] [--scope-path <path>]"
  fi

  local json_body
  json_body=$(jq -n --arg q "$query" --argjson mpn "$memories_per_node" --argjson tl "$total_limit" \
    '{query: $q, memoriesPerNode: $mpn, totalLimit: $tl}')
  if [ ${#scope_paths[@]} -gt 0 ]; then
    local scope_paths_json
    scope_paths_json=$(printf '%s\n' "${scope_paths[@]}" | jq -R . | jq -s .)
    json_body=$(echo "$json_body" | jq --argjson sp "$scope_paths_json" '. + {scopePaths: $sp}')
  fi

  local response
  response=$(api_post_json_response "${BASE_URL}/search/hierarchical" "$json_body")
  check_v2_response "$response"
  print_search_response_data "$response"
}

cmd_user_update() {
  local id="${1:-}"
  shift || true
  local content=""

  if [ -z "$id" ]; then
    error "Usage: user-memory update <id> <content>"
  fi

  while [ $# -gt 0 ]; do
    case "$1" in
      --*)
        error "Unknown option for user-memory update: $1"
        ;;
      *)
        [ -z "$content" ] && content="$1" || content="$content $1"
        shift
        ;;
    esac
  done

  if [ -z "$content" ]; then
    error "Usage: user-memory update <id> <content>"
  fi

  local json_body
  json_body=$(jq -n --arg i "$id" --arg c "$content" '{id: $i, content: $c}')

  local response
  response=$(api_post_json_response "${BASE_URL}/update" "$json_body")
  check_v2_response "$response"

  local write_success target_path
  write_success=$(echo "$response" | jq -r '.data.writeSuccess')
  target_path=$(echo "$response" | jq -r '.data.targetNode.path')

  if [ "$write_success" = "true" ]; then
    success "User memory updated at ${target_path}"
  else
    error "User memory update failed at ${target_path}"
  fi

  print_response_data "$response"
}

cmd_user_delete() {
  local id="${1:-}"
  shift || true

  if [ -z "$id" ]; then
    error "Usage: user-memory delete <id>"
  fi
  require_no_extra_args "user-memory delete <id>" "$@"

  local json_body
  json_body=$(jq -n --arg i "$id" '{id: $i}')

  local response
  response=$(api_post_json_response "${BASE_URL}/delete" "$json_body")
  check_v2_response "$response"

  local write_success target_path
  write_success=$(echo "$response" | jq -r '.data.writeSuccess')
  target_path=$(echo "$response" | jq -r '.data.targetNode.path')

  if [ "$write_success" = "true" ]; then
    success "User memory deleted from ${target_path}"
  else
    error "User memory delete failed at ${target_path}"
  fi

  print_response_data "$response"
}

user_memory_main() {
  require_jq

  local command="${1:-help}"
  shift || true

  case "$command" in
    tree)
      cmd_user_tree "$@"
      ;;
    add)
      cmd_user_add "$@"
      ;;
    search)
      cmd_user_search "$@"
      ;;
    update)
      cmd_user_update "$@"
      ;;
    delete)
      cmd_user_delete "$@"
      ;;
    help|--help|-h)
      user_memory_usage
      ;;
    *)
      error "Unknown user-memory command: $command\nRun 'user-memory help' for usage"
      ;;
  esac
}

space_memory_usage() {
  cat <<EOF
Space memory CLI v${VERSION}

USAGE:
  space-memory <command> [arguments]

COMMANDS:
  space-memory list
  space-memory tree <spaceId>
  space-memory search <spaceId> <query> [memoriesPerNode] [totalLimit]
  space-memory add <spaceId> <content> [--infer] [--target-path <path>]
  space-memory update <spaceId> <id> <content>
  space-memory delete <spaceId> <id>
  space-memory help

AUTH:
  Run 'memory auth' first when authentication is not configured.
EOF
}

cmd_space_list() {
  require_no_extra_args "space-memory list" "$@"

  local response
  response=$(api_get_response "${WORKSPACE_BASE_URL}/spaces")
  check_v2_response "$response"
  print_space_list_response_data "$response"
}

cmd_space_tree() {
  local space_id="${1:-}"
  shift || true
  if [ -z "$space_id" ]; then
    error "Usage: space-memory tree <spaceId>"
  fi
  require_no_extra_args "space-memory tree <spaceId>" "$@"

  local response
  response=$(api_get_response "${WORKSPACE_BASE_URL}/spaces/${space_id}/tree")
  check_v2_response "$response"
  print_tree_response_data "$response"
}

cmd_space_add() {
  local space_id="${1:-}"
  shift || true
  local content=""
  local enable_inference="false"
  local target_path=""

  if [ -z "$space_id" ]; then
    error "Usage: space-memory add <spaceId> <content> [--infer] [--target-path <path>]"
  fi

  while [ $# -gt 0 ]; do
    case "$1" in
      --infer)
        enable_inference="true"
        shift
        ;;
      --target-path|--targetPath|--path)
        if [ $# -lt 2 ] || [[ "$2" == --* ]]; then
          error "space-memory add requires a value for $1"
        fi
        target_path="$2"
        shift 2
        ;;
      --target-path=*|--targetPath=*|--path=*)
        target_path="${1#*=}"
        shift
        ;;
      --*)
        error "Unknown option for space-memory add: $1"
        ;;
      *)
        [ -z "$content" ] && content="$1" || content="$content $1"
        shift
        ;;
    esac
  done

  if [ -z "$content" ]; then
    error "Usage: space-memory add <spaceId> <content> [--infer] [--target-path <path>]"
  fi

  local json_body
  json_body=$(jq -n --arg c "$content" --argjson ei "$enable_inference" \
    '{content: $c, enableInference: $ei}')
  if [ -n "$target_path" ]; then
    json_body=$(echo "$json_body" | jq --arg tp "$target_path" '. + {targetPath: $tp}')
  fi

  local response
  response=$(api_post_json_response "${WORKSPACE_BASE_URL}/spaces/${space_id}/smart-ingest" "$json_body")
  check_v2_response "$response"

  local write_success target_path
  write_success=$(echo "$response" | jq -r '.data.writeSuccess')
  target_path=$(echo "$response" | jq -r '.data.targetNode.path')

  if [ "$write_success" = "true" ]; then
    success "Space memory saved to ${target_path}"
  else
    error "Space memory write failed at ${target_path}"
  fi

  print_response_data "$response"
}

cmd_space_search() {
  local space_id="${1:-}"
  shift || true
  local query="${1:-}"
  shift || true
  local memories_per_node="${1:-3}"
  [ $# -gt 0 ] && shift || true
  local total_limit="${1:-10}"
  [ $# -gt 0 ] && shift || true

  if [ -z "$space_id" ] || [ -z "$query" ]; then
    error "Usage: space-memory search <spaceId> <query> [memoriesPerNode] [totalLimit]"
  fi
  require_no_extra_args "space-memory search <spaceId> <query> [memoriesPerNode] [totalLimit]" "$@"

  local json_body
  json_body=$(jq -n --arg q "$query" --argjson mpn "$memories_per_node" --argjson tl "$total_limit" \
    '{query: $q, memoriesPerNode: $mpn, totalLimit: $tl}')

  local response
  response=$(api_post_json_response "${WORKSPACE_BASE_URL}/spaces/${space_id}/smart-search" "$json_body")
  check_v2_response "$response"
  print_search_response_data "$response"
}

cmd_space_update() {
  local space_id="${1:-}"
  shift || true
  local id="${1:-}"
  shift || true
  local content=""

  if [ -z "$space_id" ] || [ -z "$id" ]; then
    error "Usage: space-memory update <spaceId> <id> <content>"
  fi

  while [ $# -gt 0 ]; do
    case "$1" in
      --*)
        error "Unknown option for space-memory update: $1"
        ;;
      *)
        [ -z "$content" ] && content="$1" || content="$content $1"
        shift
        ;;
    esac
  done

  if [ -z "$content" ]; then
    error "Usage: space-memory update <spaceId> <id> <content>"
  fi

  local json_body
  json_body=$(jq -n --arg i "$id" --arg c "$content" '{id: $i, content: $c}')

  local response
  response=$(api_post_json_response "${WORKSPACE_BASE_URL}/spaces/${space_id}/smart-update" "$json_body")
  check_v2_response "$response"

  local write_success target_path
  write_success=$(echo "$response" | jq -r '.data.writeSuccess')
  target_path=$(echo "$response" | jq -r '.data.targetNode.path')

  if [ "$write_success" = "true" ]; then
    success "Space memory updated at ${target_path}"
  else
    error "Space memory update failed at ${target_path}"
  fi

  print_response_data "$response"
}

cmd_space_delete() {
  local space_id="${1:-}"
  shift || true
  local id="${1:-}"
  shift || true

  if [ -z "$space_id" ] || [ -z "$id" ]; then
    error "Usage: space-memory delete <spaceId> <id>"
  fi
  require_no_extra_args "space-memory delete <spaceId> <id>" "$@"

  local json_body
  json_body=$(jq -n --arg i "$id" '{id: $i}')

  local response
  response=$(api_post_json_response "${WORKSPACE_BASE_URL}/spaces/${space_id}/delete" "$json_body")
  check_v2_response "$response"

  local write_success target_path
  write_success=$(echo "$response" | jq -r '.data.writeSuccess')
  target_path=$(echo "$response" | jq -r '.data.targetNode.path')

  if [ "$write_success" = "true" ]; then
    success "Space memory deleted from ${target_path}"
  else
    error "Space memory delete failed at ${target_path}"
  fi

  print_response_data "$response"
}

space_memory_main() {
  require_jq

  local command="${1:-help}"
  shift || true

  case "$command" in
    list|ls|spaces)
      cmd_space_list "$@"
      ;;
    tree)
      cmd_space_tree "$@"
      ;;
    add)
      cmd_space_add "$@"
      ;;
    search)
      cmd_space_search "$@"
      ;;
    update)
      cmd_space_update "$@"
      ;;
    delete)
      cmd_space_delete "$@"
      ;;
    help|--help|-h)
      space_memory_usage
      ;;
    *)
      error "Unknown space-memory command: $command\nRun 'space-memory help' for usage"
      ;;
  esac
}
