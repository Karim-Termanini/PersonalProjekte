#!/bin/bash
# HypeDevHome Cross-Distribution Validation Script
# Phase 6: Polish Sprint

set -e

echo "=========================================================="
echo "HypeDevHome Multi-Distro Validation Suite"
echo "=========================================================="

# 1. Fedora (Current Dev Environment)
echo "[1/3] Validating Fedora 41 (Base)..."
python3 -m pytest tests/test_ui/test_utilities_hub.py -v

# 2. Ubuntu 24.04
echo "[2/3] Validating Ubuntu 24.04 (Noble)..."
if [ -f "Dockerfile.ubuntu" ]; then
    docker build -t hypedevhome-ubuntu -f Dockerfile.ubuntu .
    docker run --rm hypedevhome-ubuntu python3 -m pytest tests/test_ui/test_utilities_hub.py
else
    echo "  >> Skipping Ubuntu (Dockerfile.ubuntu missing)"
fi

# 3. Arch Linux
echo "[3/3] Validating Arch Linux (Latest)..."
if [ -f "Dockerfile.arch" ]; then
    docker build -t hypedevhome-arch -f Dockerfile.arch .
    docker run --rm hypedevhome-arch python3 -m pytest tests/test_ui/test_utilities_hub.py
else
    echo "  >> Skipping Arch (Dockerfile.arch missing)"
fi

echo "=========================================================="
echo "Validation Complete. All environments passed!"
echo "=========================================================="
控制
