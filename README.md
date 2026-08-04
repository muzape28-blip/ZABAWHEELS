# ZMUX

<p align="center">
  <strong>Alpine Linux terminal for Android.</strong><br>
  ZMUX, TERMINAL LINUX FOR YOU.
</p>

<p align="center">
  <img src="app/assets/logo.png" width="124" alt="ZMUX Z prompt logo">
</p>

<p align="center">
  <a href="https://github.com/muzape28-blip/ZABAWHEELS/actions/workflows/build-zmux-apk.yml"><img src="https://github.com/muzape28-blip/ZABAWHEELS/actions/workflows/build-zmux-apk.yml/badge.svg" alt="Build ZMUX APK"></a>
  <a href="https://github.com/muzape28-blip/ZABAWHEELS/actions/workflows/validate.yml"><img src="https://github.com/muzape28-blip/ZABAWHEELS/actions/workflows/validate.yml/badge.svg" alt="Validate repository"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0-52e878?style=flat-square" alt="AGPL-3.0 license"></a>
  <img src="https://img.shields.io/badge/Android-8.0%2B-0d1117?style=flat-square&logo=android&logoColor=52e878" alt="Android 8.0 or newer">
  <img src="https://img.shields.io/badge/ABI-armv7%20%7C%20arm64-0d1117?style=flat-square" alt="ARMv7 and ARM64">
</p>

---

## What is ZMUX?

ZMUX is a lightweight Android terminal whose user-facing environment is **Alpine Linux**. It starts an Alpine login shell through **PRoot** on a genuine `/dev/ptmx` PTY, then connects it to a keyboard-aware xterm.js interface.

> **Package workflow:** use Alpine `apk` and Python virtual environments inside Alpine. The historical ZABAWHEELS/`zpip` wheelhouse pipeline is retained only for migration and legacy artifact reproducibility; it is not the recommended user package path.

```text
Android keyboard / touch UI
        ↓
xterm.js + local WebSocket
        ↓
real PTY (/dev/ptmx)
        ↓
PRoot
        ↓
Alpine Linux: /bin/sh, apk, git, nano, Python, pip…
```

It is designed for practical mobile workflows:

- `apk add`, `git clone`, `nano`, `python3`, `pip`, `ssh`, and shell scripting;
- persistent projects in `~/projects`;
- opt-in Android Documents/Downloads/shared-storage access under `~/storage`;
- compact tabs, horizontal virtual keys, and soft-keyboard-aware layout;
- ARMv7-friendly operation on entry-level Android devices.

> **Not Android root.** ZMUX provides a real Linux *userspace* inside the app sandbox. It does not provide kernel access, systemd, Docker, kernel modules, or unrestricted Android filesystem access.

---

## Highlights

| Area | What ZMUX provides |
|---|---|
| **Real terminal** | `/dev/ptmx` PTY, terminal resize, foreground `SIGINT`, `isatty()`, shell echo, and normal interactive behavior. |
| **Alpine-first** | `apk`, BusyBox shell, Git, Nano, Python, virtual environments, and standard Linux paths. |
| **Mobile UI** | One-row swipeable virtual keys, compact tabs, soft-keyboard-aware viewport, scrollback, and safe output wrapping. |
| **Projects** | Persistent `~/projects` workspace that survives Alpine rootfs repair/reinstall. |
| **Android storage** | `zmux-setup-storage` bridges Android permissions into Alpine links such as `~/storage/documents` and `~/storage/downloads`. |
| **Security** | Loopback-only HTTP/WebSocket transport, session token, verified Alpine rootfs, app-private default storage, and no Android root requirement. |
| **Builds** | Universal `armeabi-v7a` + `arm64-v8a` APK builds with pinned toolchain inputs. |

---

## Quick start

### 1. Install Alpine

On the first launch, ZMUX shows an Alpine setup prompt:

```sh
alpine-setup> linux-setup
```

The minirootfs is downloaded, SHA-512 verified, extracted atomically, and ZMUX opens the shell automatically:

```sh
zmux@alpine:~$
```

### 2. Install useful tools

```sh
apk add nano git python3 py3-pip py3-virtualenv openssh-client
```

### 3. Create a project

```sh
cd ~/projects
mkdir hello-zmux
cd hello-zmux
nano README.md
```

### 4. Use Python safely with a virtual environment

```sh
python3 -m venv ~/.venv
. ~/.venv/bin/activate
python3 -m pip install colorama
python3 -c "import colorama; print('colorama OK')"
```

### 5. Access Android files

```sh
zmux-setup-storage
cd ~/storage/documents
ls
```

The command requests Android storage access where required and exposes reachable locations inside Alpine:

```text
~/storage/app
~/storage/shared
~/storage/downloads
~/storage/documents
~/storage/dcim
~/storage/pictures
~/storage/music
~/storage/movies
```

Use `~/projects` for active work. Use `~/storage/*` to import/export files with Android.

---

## Terminal controls

The virtual key bar stays on **one horizontally swipeable row** so it does not consume the terminal when the phone keyboard is open.

```text
ESC  CTRL  Tab  ↑  ↓  ←  →  Home  End  ^C  ^D  ⌫  …
```

Useful shortcuts:

| Key | Action |
|---|---|
| `CTRL` then `C` | Interrupt the foreground command, e.g. `ping` |
| `CTRL` then `D` | End input / exit a shell program |
| `ESC` | Essential for Vim, Nano, and shell programs |
| Arrow keys | Navigate command history, Nano, Vim, and shell input |

---

## Verified on a real ARMv7 device

Current device validation on an Infinix Smart 9 HD-class Android device includes:

```text
✓ Alpine real PTY shell
✓ apk package installation
✓ Nano full-screen editor
✓ Git clone over HTTPS
✓ Python 3 + venv + pip
✓ pip install colorama + import verification
✓ Android Documents/Downloads storage access from Alpine
✓ Multiple terminal sessions
✓ ping + Ctrl+C foreground SIGINT
✓ Soft keyboard, wrapping, scrollback, and horizontal key bar
```

Example real workflow:

```sh
apk add python3 nano git py3-pip py3-virtualenv
cd ~/projects
git clone https://github.com/muzape28-blip/ZABAWHEELS
python3 -m venv ~/.venv
. ~/.venv/bin/activate
python3 -m pip install colorama
```

---

## Install the APK

Download the latest successful **Build ZMUX APK** artifact from [GitHub Actions](https://github.com/muzape28-blip/ZABAWHEELS/actions/workflows/build-zmux-apk.yml).

The `zmux` artifact contains:

```text
zmux-1.0.0-universal-debug.apk
SHA256SUMS
build-contract.json
```

> When replacing a debug APK, Android may require uninstalling an older build if its signing identity differs. Back up `~/projects` first if you plan to uninstall the app.

---

## Build from source

The reproducible GitHub Actions workflow is the recommended build path. For a local build environment, use the repository-local bootstrap script on a machine with outbound network access:

```bash
./scripts/bootstrap_android_toolchain.sh

cd app
../.toolchain/buildozer-venv/bin/buildozer android debug
```

The build creates a universal ARMv7 + ARM64 APK and cross-compiles the Android PRoot bridge.

---

## Developer API boundary

The interactive terminal is driven by the authenticated WebSocket connected to the Alpine PTY. REST terminal-session endpoints such as `/api/exec`, `/api/status`, and `/api/prompt` are retained for legacy compatibility and should not be used for new terminal UX.

If a legacy client must call `/api/exec`, send an explicit language value:

```json
{"command": "echo hello", "language": "command"}
{"command": "print(21 + 21)", "language": "python"}
{"command": "echo old flow", "language": "legacy-auto"}
```

See [docs/REST_COMPATIBILITY.md](docs/REST_COMPATIBILITY.md) and [docs/REST_EXEC_LANGUAGE_MIGRATION.md](docs/REST_EXEC_LANGUAGE_MIGRATION.md).

---

## Honest limitations

- PRoot adds overhead; heavy native compilation is slow on low-end ARMv7 devices.
- Local filesystem access follows Android permission and scoped-storage rules.
- Android root, Docker, systemd, kernel modules, and full kernel isolation are outside ZMUX's scope.
- Alpine uses `musl`; some prebuilt glibc binaries or Python native wheels may not work. Prefer Alpine `apk` packages first, then use `pip` inside a virtual environment when appropriate.

---

## Roadmap

After Alpine PTY, storage, keyboard, and lifecycle hardening are complete, planned updates include:

- terminal appearance profiles and low-resource mode;
- named terminal sessions;
- Nano-oriented helper controls;
- GitHub-aware project workflow built around real Alpine Git;
- tmux onboarding/helper path;
- honest `apk` / venv / pip package recommendation UI;
- optional Debian compatibility environment after Alpine remains stable.

See [CHANGELOG.md](CHANGELOG.md) for the full planned-update notes.

---

## Documentation

### Documentation map

- [docs/README.md](docs/README.md) — Alpine-first documentation index and current-vs-legacy map
- [CHANGELOG.md](CHANGELOG.md) — changes and planned updates
- [CONTRIBUTING.md](CONTRIBUTING.md) — contribution guide

### Current technical docs

- [docs/PROOT_ALPINE.md](docs/PROOT_ALPINE.md) — Alpine/PRoot design
- [docs/BUILDING.md](docs/BUILDING.md) — APK build path
- [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) — runtime compatibility contract
- [docs/SECURITY.md](docs/SECURITY.md) — security model
- [docs/DEVICE_TESTING.md](docs/DEVICE_TESTING.md) — device test matrix
- [docs/REST_COMPATIBILITY.md](docs/REST_COMPATIBILITY.md) — REST vs WebSocket terminal boundary
- [docs/REST_EXEC_LANGUAGE_MIGRATION.md](docs/REST_EXEC_LANGUAGE_MIGRATION.md) — legacy `/api/exec` language migration guide

### Legacy package pipeline

- [docs/LEGACY_PACKAGE_PIPELINE.md](docs/LEGACY_PACKAGE_PIPELINE.md) — why ZABAWHEELS wheelhouse tooling is still retained for migration/historical artifacts

### Historical docs

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — application architecture plus legacy host-console/API history
- [docs/DEVICE_FAILURE_ANALYSIS.md](docs/DEVICE_FAILURE_ANALYSIS.md) — real-device failure analysis

---

## License

[AGPL-3.0](LICENSE)

<p align="center"><strong>ZMUX</strong> — a focused Alpine Linux terminal for Android.</p>
