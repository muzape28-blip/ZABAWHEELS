# =============================================================================
# ZABAWHEELS Build Environment — Cross-compile Android native wheels
# =============================================================================
# This Dockerfile defines the cross-compilation environment for building
# Android native wheels for ZMUX.
#
# The build image matches the toolchain pinned in runtime-lock.json.
# NDK 28c + Buildozer 1.5.0 + p4a @ 5c192d7b7308
#
# Usage:
#   docker build -t zmux-builder toolchain/
#   docker run --rm -v $(pwd):/build zmux-builder \
#     python3 scripts/build.py --package zaba-native-smoke --version 0.1.0 \
#     --abi armeabi-v7a --channel experimental

FROM ubuntu:22.04

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install base dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    python3 \
    python3-pip \
    python3-dev \
    wget \
    unzip \
    openjdk-17-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

# Install Python build tools
RUN pip3 install --no-cache-dir --break-system-packages \
    setuptools==68.2.2 \
    wheel==0.41.2 \
    Cython==0.29.33 \
    pyyaml \
    buildozer==1.5.0 \
    pip==23.2.1

# Android NDK 28c — pinned to runtime-lock.json
ENV NDK_VERSION=r28c
ENV ANDROID_NDK_HOME=/opt/android-ndk
RUN wget -q https://dl.google.com/android/repository/android-ndk-${NDK_VERSION}-linux.zip \
    && unzip -q android-ndk-${NDK_VERSION}-linux.zip -d /opt \
    && rm android-ndk-${NDK_VERSION}-linux.zip

# python-for-android — pinned to runtime-lock.json
# We clone p4a so buildozer can use it for building the Python distribution.
# The actual cross-compile is done by build.py using NDK directly.
ENV P4A_COMMIT=5c192d7b7308487c2d3e3fcae63deba3131e7cb2
RUN git clone https://github.com/kivy/python-for-android.git /opt/p4a \
    && cd /opt/p4a \
    && git checkout ${P4A_COMMIT}

# Environment variables for buildozer/p4a
ENV ANDROID_SDK_ROOT=/root/.buildozer/android/platform/android-sdk
ENV ANDROID_HOME=/root/.buildozer/android/platform/android-sdk
ENV P4A_DIR=/opt/p4a

# Working directory
WORKDIR /build

# Default: run build.py
ENTRYPOINT ["python3", "scripts/build.py"]
