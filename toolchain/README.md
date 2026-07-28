# Toolchain contract

This directory defines the reproducible ZMUX Android runtime and package source
inputs.

| File | Purpose |
|---|---|
| `runtime-lock.json` | CPython 3.14.2, p4a commit, NDK 28c, API levels, Buildozer and host tools |
| `source-lock.json` | Version, source location, deterministic SHA-256 and license for each package |
| `Dockerfile` | Package cross-compilation environment |

The active runtime generation is:

```text
zmux-py314-api26-p4a5c192d7b7308-r1
```

`app/buildozer.spec` is the executable source of this APK contract. The app's
`GET /api/runtime` endpoint reports values observed while running. Before a
native wheel is promoted, the device report must agree with this lock; a
mismatch creates a new runtime generation instead of weakening matching.

## Rules

- Every native wheel names one exact `runtime_id` and ABI.
- Changes to CPython, p4a, NDK, API, SOABI or extension suffix create `-r2`,
  `-r3`, and so on.
- Old wheel artifacts are immutable.
- No placeholder, floating dependency or guessed ABI is accepted for a
  candidate/stable native wheel.
