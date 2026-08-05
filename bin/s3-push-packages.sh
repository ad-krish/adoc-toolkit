#!/bin/bash
# Push all prerequisite Python packages (wheels) to an S3 bucket.
# This downloads all dependencies from PyPI and uploads them to S3,
# enabling offline installation on machines without internet access.
#
# Usage:
#   bin/s3-push-packages.sh <s3-bucket-path>
#   bin/s3-push-packages.sh s3://my-bucket/adoc-toolkit/packages
#
# Prerequisites:
#   - AWS CLI configured with valid credentials
#   - uv or pip installed
#   - Internet access (to download from PyPI)

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
    echo "Usage: bin/s3-push-packages.sh <s3-bucket-path>"
    echo "Example: bin/s3-push-packages.sh s3://my-bucket/adoc-toolkit/packages"
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

# Clean previous downloads
rm -rf "$LOCAL_PKG_DIR"
mkdir -p "$LOCAL_PKG_DIR"

print_info "Step 1/3: Downloading all dependency wheels..."

if command -v uv &> /dev/null; then
    uv pip download -r pyproject.toml --dest "$LOCAL_PKG_DIR"
else
    pip download -r <(python3 -c "
import tomllib, pathlib
data = tomllib.loads(pathlib.Path('pyproject.toml').read_text())
for dep in data.get('project', {}).get('dependencies', []):
    print(dep)
") --dest "$LOCAL_PKG_DIR"
fi

PKG_COUNT=$(ls -1 "$LOCAL_PKG_DIR"/*.whl "$LOCAL_PKG_DIR"/*.tar.gz 2>/dev/null | wc -l | tr -d ' ')
if [[ "$PKG_COUNT" -eq 0 ]]; then
    print_error "No packages were downloaded."
    exit 1
fi

print_success "Downloaded $PKG_COUNT package(s) to $LOCAL_PKG_DIR/"

print_info "Step 2/3: Uploading packages to $S3_PATH ..."

aws s3 sync "$LOCAL_PKG_DIR/" "$S3_PATH/" --exclude ".*"

print_success "Uploaded $PKG_COUNT package(s) to $S3_PATH"

print_info "Step 3/3: Verifying upload..."
REMOTE_COUNT=$(aws s3 ls "$S3_PATH/" 2>/dev/null | wc -l | tr -d ' ')
print_success "Verification: $REMOTE_COUNT file(s) found in S3."

echo ""
print_success "Done! Packages are available at: $S3_PATH"
echo ""
echo "To install on a target machine, run:"
echo "  bin/s3-pull-install.sh $S3_PATH"
