# ZMUX Android application

ZMUX is the installable Android deliverable in this repository. It is based on
the modular WebView/Python core from the owner's ZABACODE project and is now
integrated with this repository's runtime contract and transactional ZabaPip.

Key properties:

- application title: `ZMUX`
- Android application id: `ai.arena.zmux`
- version: `1.0.0`
- minimum/target API: 26/34
- ABIs: `armeabi-v7a`, `arm64-v8a`
- offline Ace editor and Python execution
- zero telemetry
- runtime fingerprint endpoint: `GET /api/runtime`
- allowlisted package command endpoint: `POST /api/zpip`
- package commands: `search`, `info`, `install`, `list`, `verify`, `uninstall`, `doctor`

The package module remains named `zabacode` internally for compatibility with
existing imports. This does not affect the APK label, application id, artifact
name, or UI branding.
