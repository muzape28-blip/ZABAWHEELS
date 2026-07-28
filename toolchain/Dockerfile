# =============================================================================
# ZABAWHEELS Build Environment
# =============================================================================
# This Dockerfile defines the cross-compilation environment for building
# Android native wheels for Zabacode.
#
# IMPORTANT: This is a placeholder for M0. The actual build environment
# will be finalized after M1 (runtime fingerprint and toolchain freeze).
#
# The build image MUST match the toolchain pinned in runtime-lock.json.

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
    && rm -rf /var/lib/apt/lists/*

# Install Python build tools
RUN pip3 install --no-cache-dir \
    setuptools \
    wheel \
    cython \
    pyyaml \
    jsonschema

# Android NDK — version will be pinned after M1
# ENV NDK_VERSION=r26d
# ENV ANDROID_NDK_HOME=/opt/android-ndk
# RUN wget -q https://dl.google.com/android/repository/android-ndk-${NDK_VERSION}-linux.zip \
#     && unzip -q android-ndk-${NDK_VERSION}-linux.zip -d /opt \
#     && rm android-ndk-${NDK_VERSION}-linux.zip

# python-for-android — commit will be pinned after M1
# ENV P4A_COMMIT=XXXX
# RUN git clone https://github.com/kivy/python-for-android.git /opt/p4a \
#     && cd /opt/p4a \
#     && git checkout ${P4A_COMMIT}

# Working directory
WORKDIR /build

# Default command
CMD ["/bin/bash"]
