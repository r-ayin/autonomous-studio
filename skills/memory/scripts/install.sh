#!/bin/bash

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() {
  echo -e "${BLUE}$1${NC}"
}

success() {
  echo -e "${GREEN}✓ $1${NC}"
}

warn() {
  echo -e "${YELLOW}$1${NC}"
}

echo "Memory CLI Installation"
echo "======================="
echo ""

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
COMMON_FILE="${SCRIPT_DIR}/lib/memory-common.sh"
CLI_SCRIPTS=(memory user-memory space-memory)

if [ ! -f "$COMMON_FILE" ]; then
  echo "Error: common library not found at $COMMON_FILE"
  exit 1
fi

for script_name in "${CLI_SCRIPTS[@]}"; do
  if [ ! -f "${SCRIPT_DIR}/${script_name}" ]; then
    echo "Error: script not found at ${SCRIPT_DIR}/${script_name}"
    exit 1
  fi
done

# Determine install location
if [ -w "/usr/local/bin" ]; then
  INSTALL_DIR="/usr/local/bin"
else
  INSTALL_DIR="${HOME}/.local/bin"
  mkdir -p "$INSTALL_DIR"
fi

already_installed="false"
for script_name in "${CLI_SCRIPTS[@]}"; do
  if [ -f "${INSTALL_DIR}/${script_name}" ]; then
    already_installed="true"
  fi
done

if [ "$already_installed" = "true" ]; then
  info "Memory CLI is already installed at ${INSTALL_DIR}"
  read -p "Do you want to reinstall/update? (y/N): " -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 0
  fi
fi

mkdir -p "${INSTALL_DIR}/memory-lib"
cp "$COMMON_FILE" "${INSTALL_DIR}/memory-lib/memory-common.sh"

for script_name in "${CLI_SCRIPTS[@]}"; do
  cp "${SCRIPT_DIR}/${script_name}" "${INSTALL_DIR}/${script_name}"
  chmod +x "${INSTALL_DIR}/${script_name}"
done

success "Memory CLI installed to ${INSTALL_DIR}"
echo ""

# Check if in PATH
if echo "$PATH" | grep -q "$INSTALL_DIR"; then
  success "Installation complete! Run 'memory help' to get started."
else
  warn "Note: ${INSTALL_DIR} is not in your PATH"
  echo ""
  echo "Add this to your ~/.zshrc or ~/.bashrc:"
  echo ""
  echo "  export PATH=\"${INSTALL_DIR}:\$PATH\""
  echo ""
  echo "Then reload your shell: source ~/.zshrc"
fi

echo ""
info "Next steps:"
echo "  1. Get your authTicket from https://kbase.alibaba-inc.com/#/private-token"
echo "  2. Run: memory setup"
echo "  3. Use: user-memory help or space-memory help"
