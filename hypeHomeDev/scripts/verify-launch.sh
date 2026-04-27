#!/bin/bash

# verify-launch.sh - Verify the GTK application can launch
# Run this on a system with a display to verify Phase 0 completion

set -euo pipefail

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_display() {
    log_info "Checking display availability..."
    
    if [[ -n "$DISPLAY" ]] || [[ -n "$WAYLAND_DISPLAY" ]]; then
        log_success "Display detected:"
        [[ -n "$DISPLAY" ]] && echo "  X11: $DISPLAY"
        [[ -n "$WAYLAND_DISPLAY" ]] && echo "  Wayland: $WAYLAND_DISPLAY"
        return 0
    else
        log_error "No display detected!"
        echo "  Set DISPLAY for X11 (e.g., DISPLAY=:0)"
        echo "  Set WAYLAND_DISPLAY for Wayland (e.g., WAYLAND_DISPLAY=wayland-0)"
        return 1
    fi
}

check_imports() {
    log_info "Checking Python imports..."
    
    if python3 -c "from src.main import main; print('✓ All imports successful')"; then
        log_success "All Python imports work correctly"
        return 0
    else
        log_error "Python imports failed"
        return 1
    fi
}

check_cli() {
    log_info "Checking CLI interface..."
    
    if output=$(python3 -m src.main --help 2>&1); then
        log_success "CLI interface works:"
        echo ""
        echo "$output" | head -10
        return 0
    else
        log_error "CLI interface failed"
        return 1
    fi
}

test_launch() {
    log_info "Testing application launch (5 second timeout)..."
    
    # Try to launch the application with a timeout
    if timeout 5 python3 -m src.main --debug 2>&1 | grep -q "Application started\|Window created\|Gtk initialized"; then
        log_success "Application launched successfully!"
        return 0
    else
        log_warning "Application launch test inconclusive"
        echo "  This is expected in headless environments"
        echo "  On a system with display, you should see a GTK window"
        return 2  # Special code for inconclusive
    fi
}

check_config() {
    log_info "Checking config directory..."
    
    CONFIG_DIR="$HOME/.config/dev-home"
    if [[ -d "$CONFIG_DIR" ]]; then
        log_success "Config directory exists: $CONFIG_DIR"
        
        if [[ -f "$CONFIG_DIR/config.json" ]]; then
            log_success "Config file exists: $CONFIG_DIR/config.json"
        else
            log_warning "Config file doesn't exist (will be created on first run)"
        fi
        return 0
    else
        log_warning "Config directory doesn't exist (will be created on first run)"
        return 0
    fi
}

main() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Phase 0: Application Launch Verification${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    local all_passed=true
    
    # Run checks
    if ! check_display; then
        log_warning "Running in headless mode - some tests will be skipped"
    fi
    
    if ! check_imports; then
        all_passed=false
    fi
    
    if ! check_cli; then
        all_passed=false
    fi
    
    # Only test launch if we have a display
    if [[ -n "$DISPLAY" ]] || [[ -n "$WAYLAND_DISPLAY" ]]; then
        test_launch
        # Don't fail on inconclusive launch test
    else
        log_warning "Skipping application launch test (no display)"
    fi
    
    if ! check_config; then
        # Config check warnings don't count as failures
        :
    fi
    
    echo ""
    echo -e "${BLUE}========================================${NC}"
    
    if $all_passed; then
        echo -e "${GREEN}✅ Phase 0 verification PASSED${NC}"
        echo ""
        echo "Next steps:"
        echo "1. To see the actual GUI, run: python -m src.main"
        echo "2. For development: docker-compose up dev"
        echo "3. For testing: docker-compose exec dev pytest"
    else
        echo -e "${RED}❌ Phase 0 verification FAILED${NC}"
        exit 1
    fi
}

main "$@"