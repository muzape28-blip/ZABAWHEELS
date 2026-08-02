#!/usr/bin/env bash
# Provision a repository-local Android build toolchain for ZMUX.
#
# Requires outbound network access. Everything except generated build output
# lives under .toolchain/ so it does not modify the system Python or require
# global Buildozer installation.
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
TOOLS="${ROOT}/.toolchain"
SDK="${TOOLS}/android-sdk"
JDK="${TOOLS}/jdk-17"
GRADLE="${TOOLS}/gradle-8.7"
VENV="${TOOLS}/buildozer-venv"
CMDLINE_VERSION="11076708"

need() { command -v "$1" >/dev/null 2>&1 || { echo "missing required command: $1" >&2; exit 1; }; }
for command in curl unzip tar python3 git; do need "$command"; done

mkdir -p "$TOOLS" "$SDK/cmdline-tools"

if [[ ! -x "$JDK/bin/java" ]]; then
  echo "Downloading Temurin JDK 17..."
  archive="$TOOLS/temurin-jdk17.tar.gz"
  curl --fail --location --retry 3 --output "$archive" \
    "https://api.adoptium.net/v3/binary/latest/17/ga/linux/x64/jdk/hotspot/normal/eclipse"
  rm -rf "$JDK"
  mkdir -p "$JDK"
  tar -xzf "$archive" -C "$JDK" --strip-components=1
fi

if [[ ! -x "$SDK/cmdline-tools/latest/bin/sdkmanager" ]]; then
  echo "Downloading Android command-line tools..."
  archive="$TOOLS/commandlinetools.zip"
  curl --fail --location --retry 3 --output "$archive" \
    "https://dl.google.com/android/repository/commandlinetools-linux-${CMDLINE_VERSION}_latest.zip"
  rm -rf "$SDK/cmdline-tools/latest"
  mkdir -p "$SDK/cmdline-tools/latest"
  unzip -q "$archive" -d "$TOOLS/cmdline-unpack"
  mv "$TOOLS/cmdline-unpack/cmdline-tools"/* "$SDK/cmdline-tools/latest/"
  rmdir "$TOOLS/cmdline-unpack/cmdline-tools" "$TOOLS/cmdline-unpack"
fi

if [[ ! -x "$GRADLE/bin/gradle" ]]; then
  echo "Downloading Gradle 8.7..."
  archive="$TOOLS/gradle-8.7-bin.zip"
  curl --fail --location --retry 3 --output "$archive" \
    "https://services.gradle.org/distributions/gradle-8.7-bin.zip"
  unzip -q "$archive" -d "$TOOLS"
fi

export JAVA_HOME="$JDK"
export ANDROID_HOME="$SDK"
export ANDROID_SDK_ROOT="$SDK"
export PATH="$JAVA_HOME/bin:$SDK/cmdline-tools/latest/bin:$GRADLE/bin:$PATH"

sdkmanager --sdk_root="$SDK" --licenses < /dev/null || true
sdkmanager --sdk_root="$SDK" \
  "platform-tools" "platforms;android-34" "build-tools;34.0.0" \
  "ndk;28.1.13356709" "cmdline-tools;latest"

if [[ ! -x "$VENV/bin/buildozer" ]]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --upgrade pip wheel setuptools
  "$VENV/bin/pip" install "buildozer==1.5.0" "cython<3.1"
fi

cat <<EOF
Android toolchain is ready.

Activate it with:
  export JAVA_HOME="$JAVA_HOME"
  export ANDROID_HOME="$ANDROID_HOME"
  export ANDROID_SDK_ROOT="$ANDROID_SDK_ROOT"
  export PATH="$JAVA_HOME/bin:$SDK/cmdline-tools/latest/bin:$GRADLE/bin:$PATH"

Generate/build the ZMUX Android project:
  cd "$ROOT/app"
  "$VENV/bin/buildozer" android debug
EOF
