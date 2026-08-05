#!/bin/bash
# Pull prerequisite Python packages from an S3 bucket and install them offline.
# No internet/PyPI access is needed — all packages come from S3.
#
# Usage:
#   bin/s3-pull-install.sh <s3-bucket-path>
#   bin/s3-pull-install.sh s3://my-bucket/adoc-toolkit/packages
#
# Prerequisites:
#   - AWS CLI configured with valid credentials
#   - uv or pip installed
#   - Python 3.10+

set -e

cd "$(dirname "$0")/.."

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_error()   { echo -e "${RED}Error: $1${NC}" >&2; }
print_success() { echo -e "${GREEN}$1${NC}"; }
print_info()    { echo -e "${YELLOW}$1${NC}"; }

LOCAL_PKG_DIR="packages"
S3_PATH="${1}"

if [[ -z "$S3_PATH" ]]; then
    print_error "S3 bucket path is required."
    echo ""
    echo "Usage: bin/s3-pull-install.sh <s3-bucket-path>"
    echo "Example: bin/s3-pull-install.sh s3://my-bucket/adoc-toolkit/packages"
    exit 1
fi

if ! command -v aws &> /dev/null; then
    print_error "AWS CLI not found. Please install it first."
    exit 1
fi

if [[ ! -f "pyproject.toml" ]]; then
    print_error "pyproject.toml not found. Run this from the project root."
    exit 1
fi

mkdir -p "$LOCAL_PKG_DIR"

print_info "Step 1/3: Downloading packages from $S3_PATH ..."

aws s3 sync "$S3_PATH/" "$LOCAL_PKG_DIR/" --exclude ".*"

PKG_COUNT=$(ls -1 "$LOCAL_PKG_DIR"/*.whl "$LOCAL_PKG_DIR"/*.tar.gz 2>/dev/null | wc -l | tr -d ' ')
if [[ "$PKG_COUNT" -eq 0 ]]; then
    print_error "No packages found in $S3_PATH"
    exit 1
fi

print_success "Downloaded $PKG_COUNT package(s) from S3."

print_info "Step 2/3: Creating virtual environment (if needed)..."

if command -v uv &> /dev/null; then
    if [[ ! -d ".venv" ]]; then
        uv venv
        print_success "Virtual environment created."
    else
        print_info "Virtual environment already exists."
    fi
else
    if [[ ! -d ".venv" ]]; then
        python3 -m venv .venv
        print_success "Virtual environment created."
    else
        print_info "Virtual environment already exists."
    fi
fi

print_info "Step 3/3: Installing packages offline from local cache..."

if command -v uv &> /dev/null; then
    uv pip install --no-index --find-links "$LOCAL_PKG_DIR" -e "."
else
    .venv/bin/pip install --no-index --find-links "$LOCAL_PKG_DIR" -e "."
fi

print_success "All packages installed successfully!"

echo ""
print_success "Done! adoc-toolkit is ready to use."
echo ""
echo "Run the toolkit with:"
echo "  uv run adoc-toolkit"
echo "  # or"
echo "  .venv/bin/adoc-toolkit"
