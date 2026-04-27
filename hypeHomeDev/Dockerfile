# Dockerfile for HypeDevHome development environment
# Base: Fedora 41 — chosen for stable GTK4/Libadwaita support and Flatpak integration
FROM fedora:41

# Install system dependencies
RUN dnf update -y && \
    dnf install -y \
    # Python and build tools
    python3 \
    python3-devel \
    python3-pip \
    python3-wheel \
    # GTK4 and Libadwaita development
    gtk4-devel \
    libadwaita-devel \
    gobject-introspection-devel \
    # Build tools
    gcc \
    gcc-c++ \
    make \
    pkgconfig \
    # Flatpak build tools
    flatpak \
    flatpak-builder \
    # Additional useful tools
    git \
    vim \
    wget \
    curl \
    # Clean up to reduce image size
    && dnf clean all

# Install Python testing tools via pip (not available as Fedora packages)
RUN pip3 install --no-cache-dir --break-system-packages \
    pytest \
    pytest-cov \
    ruff \
    mypy

# Create a non-root user for security
RUN useradd -m -s /bin/bash dev && \
    echo "dev ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Set working directory
WORKDIR /app

# Copy project files (will be mounted as volume in development)
COPY . /app

# Set environment variables for GTK4
ENV DISPLAY=:0
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Install Python dependencies from pyproject.toml (if exists)
RUN if [ -f "pyproject.toml" ]; then \
        pip3 install --no-cache-dir --break-system-packages -e ".[dev]"; \
    fi

# Switch to non-root user
USER dev

# Default command (can be overridden)
CMD ["bash"]

# Documentation for running with GUI:
# For X11: docker run -it --rm -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix <image>
# For Wayland: docker run -it --rm -e WAYLAND_DISPLAY=$WAYLAND_DISPLAY -v $XDG_RUNTIME_DIR:$XDG_RUNTIME_DIR <image>
# For development: docker run -it --rm -v $(pwd):/app -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix <image>
