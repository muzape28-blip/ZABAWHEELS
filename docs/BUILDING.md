# Building ZMUX

## Prerequisites

- Ubuntu 22.04 (or compatible Linux)
- Java 17 (Temurin)
- Python 3.10+
- Buildozer 1.5.0
- Android SDK & NDK

## Quick Build

```bash
cd app
pip install buildozer==1.5.0 Cython==0.29.33 setuptools==68.2.2 wheel==0.41.2
buildozer android debug
```

Output: `app/bin/zmux-1.0.0-*.apk`

## CI Build (GitHub Actions)

Push to `main` or `arena/*` branch triggers automatic APK build.

Artifacts:
- `zmux-1.0.0-universal-debug.apk`
- `SHA256SUMS`
- `build-contract.json`

## Build Contract

| Component | Version |
|-----------|---------|
| Buildozer | 1.5.0 |
| Cython | 0.29.33 |
| p4a commit | 5c192d7b7308487c2d3e3fcae63deba3131e7cb2 |
| NDK | 28c |
| Java | 17 (Temurin) |
| Python host | 3.10 |
| Target API | 34 |
| Min API | 26 |
| ABIs | armeabi-v7a, arm64-v8a |

## Local Development

```bash
cd app
pip install flask waitress packaging certifi
python main.py
# Terminal at http://127.0.0.1:5000
```

## Testing

```bash
cd app
pip install pytest
pytest tests/ -v
```
