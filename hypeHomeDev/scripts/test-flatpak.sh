#!/bin/bash

# test-flatpak.sh - Test Flatpak build process
# This script validates the Flatpak manifest and tests the build process

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if Flatpak is installed
check_flatpak() {
    if ! command -v flatpak &> /dev/null; then
        log_error "Flatpak is not installed"
        log_info "Please install Flatpak first:"
        log_info "  Fedora: sudo dnf install flatpak flatpak-builder"
        log_info "  Ubuntu: sudo apt install flatpak flatpak-builder"
        log_info "  Arch: sudo pacman -S flatpak flatpak-builder"
        return 1
    fi
    
    if ! command -v flatpak-builder &> /dev/null; then
        log_error "flatpak-builder is not installed"
        log_info "Please install flatpak-builder:"
        log_info "  Fedora: sudo dnf install flatpak-builder"
        log_info "  Ubuntu: sudo apt install flatpak-builder"
        log_info "  Arch: sudo pacman -S flatpak-builder"
        return 1
    fi
    
    log_success "Flatpak tools are available"
    return 0
}

# Validate manifest syntax
validate_manifest() {
    log_info "Validating Flatpak manifest syntax..."
    
    if [[ ! -f "com.github.hypedevhome.yml" ]]; then
        log_error "Manifest file not found: com.github.hypedepvhome.yml"
        return 1
    fi
    
    # Basic YAML syntax check
    if ! python3 -c "import yaml; yaml.safe_load(open('com.github.hypedevhome.yml'))" 2>/dev/null; then
        log_error "Manifest has invalid YAML syntax"
        return 1
    fi
    
    # Check required fields
    local required_fields=("app-id" "runtime" "runtime-version" "sdk" "command")
    for field in "${required_fields[@]}"; do
        if ! grep -q "^${field}:" com.github.hypedevhome.yml; then
            log_error "Manifest missing required field: $field"
            return 1
        fi
    done
    
    log_success "Manifest syntax is valid"
    return 0
}

# Check for Flathub remote
check_flathub() {
    log_info "Checking Flathub remote..."
    
    if flatpak remote-list | grep -q flathub; then
        log_success "Flathub remote is configured"
    else
        log_warning "Flathub remote is not configured"
        log_info "Adding Flathub remote..."
        if flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo; then
            log_success "Flathub remote added"
        else
            log_error "Failed to add Flathub remote"
            return 1
        fi
    fi
    
    return 0
}

# Test build with --stop-at option (dry run)
test_build_dry_run() {
    log_info "Testing Flatpak build (dry run)..."
    
    local build_dir="builddir-test"
    local repo_dir="repo-test"
    
    # Clean up any previous test directories
    rm -rf "$build_dir" "$repo_dir"
    
    # Run flatpak-builder with --stop-at to test dependencies
    if flatpak-builder --stop-at=python3 "$build_dir" com.github.hypedevhome.yml; then
        log_success "Dry run completed successfully"
        rm -rf "$build_dir" "$repo_dir"
        return 0
    else
        log_error "Dry run failed"
        # Keep build directory for debugging
        log_info "Build directory kept for debugging: $build_dir"
        return 1
    fi
}

# Check required files for Flatpak
check_required_files() {
    log_info "Checking required files for Flatpak..."
    
    local missing_files=()
    
    # Check for desktop file
    if [[ ! -f "data/com.github.hypedevhome.desktop" ]]; then
        missing_files+=("data/com.github.hypedevhome.desktop")
    fi
    
    # Check for metainfo file
    if [[ ! -f "data/com.github.hypedevhome.metainfo.xml" ]]; then
        missing_files+=("data/com.github.hypedevhome.metainfo.xml")
    fi
    
    # Check for icons
    if [[ ! -f "assets/icons/com.github.hypedevhome.svg" ]]; then
        missing_files+=("assets/icons/com.github.hypedevhome.svg")
    fi
    
    if [[ ! -f "assets/icons/com.github.hypedevhome-symbolic.svg" ]]; then
        missing_files+=("assets/icons/com.github.hypedevhome-symbolic.svg")
    fi
    
    if [[ ${#missing_files[@]} -gt 0 ]]; then
        log_warning "Missing files for Flatpak:"
        for file in "${missing_files[@]}"; do
            log_info "  - $file"
        done
        log_info "These will need to be created before building the Flatpak"
        return 1
    else
        log_success "All required files are present"
        return 0
    fi
}

# Main function
main() {
    log_info "Starting Flatpak build test..."
    
    # Check prerequisites
    if ! check_flatpak; then
        log_error "Flatpak prerequisites not met"
        exit 1
    fi
    
    # Validate manifest
    if ! validate_manifest; then
        exit 1
    fi
    
    # Check Flathub
    if ! check_flathub; then
        log_warning "Continuing without Flathub (some tests may fail)"
    fi
    
    # Check required files
    check_required_files
    
    # Test build (dry run)
    if test_build_dry_run; then
        log_success "Flatpak build test passed!"
        echo ""
        echo "Next steps for actual build:"
        echo "1. Create missing files (see warnings above)"
        echo "2. Run full build: flatpak-builder --repo=repo builddir com.github.hypedevhome.yml"
        echo "3. Install: flatpak --user install hypedevhome-repo com.github.hypedevhome"
        echo "4. Run: flatpak run com.github.hypedevhome"
    else
        log_error "Flatpak build test failed"
        exit 1
    fi
}

# Run main function
main "$@"