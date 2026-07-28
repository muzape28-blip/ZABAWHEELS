# Building ZMUX and package artifacts

## GitHub APK build

The supported APK build is `.github/workflows/build-zmux-apk.yml`. It uses the
contract in `toolchain/runtime-lock.json` and emits an artifact named **zmux**.
Every Action is pinned to a full commit SHA.

Trigger it from GitHub Actions or with:

```sh
gh workflow run build-zmux-apk.yml --ref arena/019faae9-zabawheels
```

On success, download:

```sh
gh run download <run-id> -n zmux
sha256sum -c SHA256SUMS
```

Artifact contents:

```text
zmux-1.0.0-universal-debug.apk
SHA256SUMS
build-contract.json
```

The debug APK uses Android's generated debug signing key and is intended for
testing. A production release must use a protected signing secret and must not
store the keystore in Git.

## Local APK build

A Linux host with Java 17 and Android build prerequisites is required:

```sh
cd app
python3.10 -m pip install \
  buildozer==1.5.0 Cython==0.29.33 \
  setuptools==68.2.2 wheel==0.41.2
buildozer -v android debug
```

Do not change p4a, NDK, Python, API, or architecture independently. Such a
change creates a new runtime generation and invalidates native-wheel matching.

## Validation

```sh
python scripts/validate_recipes.py
python scripts/verify_source_lock.py
python -m pytest tests app/tests -q
```

## Native package gate

The native package process remains truth-first:

```text
recipe + pinned source
  -> cross-build
  -> wheel/ELF inspection
  -> experimental artifact
  -> install/import/restart/uninstall on Android
  -> device report
  -> candidate/stable promotion
```

A successful APK build proves the application and embedded runtime build. It
does **not** by itself prove that a separately downloaded native wheel can be
loaded. `zaba-native-smoke` therefore remains `recipe-ready` until a real-device
report completes M2.
