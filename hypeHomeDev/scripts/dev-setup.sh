#!/bin/bash

# dev-setup.sh - Development environment setup script for HypeDevHome
# This script sets up Docker, Flatpak, and the development environment

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_warning "Running as root is not recommended. Some operations may fail."
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Detect operating system
detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$ID
        OS_VERSION=$VERSION_ID
        log_info "Detected OS: $NAME $VERSION"
    elif [[ $(uname) == "Darwin" ]]; then
        OS="macos"
        log_info "Detected OS: macOS"
    else
        OS="unknown"
        log_warning "Could not detect OS. Some features may not work."
    fi
}

# Install Docker based on OS
install_docker() {
    log_info "Checking Docker installation..."
    
    if command -v docker &> /dev/null; then
        log_success "Docker is already installed"
        return 0
    fi
    
    log_info "Docker not found. Installing..."
    
    case $OS in
        fedora|rhel|centos)
            sudo dnf install -y docker docker-compose
            sudo systemctl enable --now docker
            sudo usermod -aG docker $USER
            ;;
        ubuntu|debian)
            sudo apt-get update
            sudo apt-get install -y docker.io docker-compose
            sudo systemctl enable --now docker
            sudo usermod -aG docker $USER
            ;;
        arch|manjaro)
            sudo pacman -S --noconfirm docker docker-compose
            sudo systemctl enable --now docker
            sudo usermod -aG docker $USER
            ;;
        macos)
            log_info "Please install Docker Desktop from https://www.docker.com/products/docker-desktop/"
            log_info "After installation, restart your terminal and run this script again."
            exit 1
            ;;
        *)
            log_error "Unsupported OS for automatic Docker installation"
            log_info "Please install Docker manually from https://docs.docker.com/get-docker/"
            exit 1
            ;;
    esac
    
    if command -v docker &> /dev/null; then
        log_success "Docker installed successfully"
    else
        log_error "Docker installation failed"
        exit 1
    fi
}

# Install Flatpak based on OS
install_flatpak() {
    log_info "Checking Flatpak installation..."
    
    if command -v flatpak &> /dev/null; then
        log_success "Flatpak is already installed"
    else
        log_info "Flatpak not found. Installing..."
        
        case $OS in
            fedora|rhel|centos)
                sudo dnf install -y flatpak flatpak-builder
                ;;
            ubuntu|debian)
                sudo apt-get update
                sudo apt-get install -y flatpak flatpak-builder
                ;;
            arch|manjaro)
                sudo pacman -S --noconfirm flatpak flatpak-builder
                ;;
            macos)
                log_warning "Flatpak is not available on macOS. Flatpak builds will not work."
                return 1
                ;;
            *)
                log_warning "Unsupported OS for automatic Flatpak installation"
                return 1
                ;;
        esac
        
        if command -v flatpak &> /dev/null; then
            log_success "Flatpak installed successfully"
        else
            log_warning "Flatpak installation failed. Flatpak builds will not work."
            return 1
        fi
    fi
    
    # Add Flathub remote if not present
    if flatpak remote-list | grep -q flathub; then
        log_info "Flathub remote already configured"
    else
        log_info "Adding Flathub remote..."
        flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
        log_success "Flathub remote added"
    fi
}

# Build Docker image
build_docker_image() {
    log_info "Building Docker image..."
    
    if ! docker build -t hypedevhome-dev .; then
        log_error "Docker build failed"
        exit 1
    fi
    
    log_success "Docker image built successfully"
}

# Verify Docker setup
verify_docker() {
    log_info "Verifying Docker setup..."
    
    if ! docker run --rm hypedevhome-dev python3 --version; then
        log_error "Docker verification failed"
        exit 1
    fi
    
    log_success "Docker setup verified"
}

# Verify Flatpak tools
verify_flatpak() {
    log_info "Verifying Flatpak tools..."
    
    if command -v flatpak &> /dev/null; then
        if flatpak --version; then
            log_success "Flatpak tools verified"
        else
            log_warning "Flatpak verification failed"
        fi
    else
        log_warning "Flatpak not available"
    fi
}

# Create config directory
create_config_dir() {
    log_info "Creating config directory..."
    
    CONFIG_DIR="$HOME/.config/dev-home"
    if [[ ! -d "$CONFIG_DIR" ]]; then
        mkdir -p "$CONFIG_DIR"
        log_success "Config directory created: $CONFIG_DIR"
    else
        log_info "Config directory already exists: $CONFIG_DIR"
    fi
}

# Print next steps
print_next_steps() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}SETUP COMPLETE!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Start development environment:"
    echo "   $ docker-compose up dev"
    echo ""
    echo "2. Run the application in Docker:"
    echo "   $ docker-compose exec dev python -m src.main"
    echo ""
    echo "3. For GUI applications, ensure your display is accessible:"
    echo "   - X11: xhost +local:docker"
    echo "   - Wayland: Ensure permissions for /run/user/1000"
    echo ""
    echo "4. Build Flatpak (if Flatpak is installed):"
    echo "   $ flatpak-builder --repo=repo builddir com.github.hypedevhome.yml"
    echo ""
    echo "5. Run tests:"
    echo "   $ docker-compose exec dev pytest"
    echo ""
    echo "For more information, see README.md"
    echo ""
}

# Main execution
main() {
    log_info "Starting HypeDevHome development environment setup..."
    
    check_root
    detect_os
    
    log_info "Installing required tools..."
    install_docker
    install_flatpak
    
    log_info "Building development environment..."
    build_docker_image
    verify_docker
    verify_flatpak
    
    create_config_dir
    
    print_next_steps
    
    log_success "Setup completed successfully!"
}

# Run main function
main "$@"