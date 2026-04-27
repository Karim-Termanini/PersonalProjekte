#!/bin/bash
# HypeDevHome - GitHub Self-hosted Runner Setup Script (Fedora)
# Usage: ./setup_runner.sh --url <REPO_URL> --token <RUNNER_TOKEN>

set -e

# 1. Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --url) REPO_URL="$2"; shift ;;
        --token) REPO_TOKEN="$2"; shift ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

if [[ -z "$REPO_URL" || -z "$REPO_TOKEN" ]]; then
    echo "Usage: $0 --url <REPO_URL> --token <RUNNER_TOKEN>"
    exit 1
fi

echo "=========================================================="
echo "HypeDevHome: GitHub Runner Setup"
echo "=========================================================="

# 2. Create runner directory
RUNNER_DIR="$HOME/actions-runner"
echo "[1/4] Creating directory: $RUNNER_DIR"
mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"

# 3. Download and extract (Fetching latest version automatically)
# Current stable as of this script: 2.333.1
VERSION="2.333.1" 
TARGET="actions-runner-linux-x64-${VERSION}.tar.gz"

if [ ! -f "$TARGET" ]; then
    echo "[2/4] Downloading GitHub Runner v${VERSION}..."
    curl -o "$TARGET" -L "https://github.com/actions/runner/releases/download/v${VERSION}/actions-runner-linux-x64-${VERSION}.tar.gz"
fi

echo "[3/4] Extracting runner binaries..."
tar xzf "./$TARGET"

# 4. Configure the runner
echo "[4/4] Connecting to GitHub ($REPO_URL)..."
./config.sh --url "$REPO_URL" --token "$REPO_TOKEN" --unattended --replace

# 5. Install as a systemd service
echo "=========================================================="
echo "Installing Systemd Service..."
sudo ./svc.sh install
sudo ./svc.sh start

echo "=========================================================="
echo "Setup Complete! Your runner is now active."
echo "Check your GitHub Repository -> Settings -> Actions -> Runners"
echo "=========================================================="
控制
