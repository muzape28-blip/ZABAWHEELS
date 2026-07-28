# Security and Supply Chain

> **Status:** Pre-Alpha (M0)

## Mandatory Security Measures (Since M0)

- ✅ **HTTPS only** — all download URLs use HTTPS
- ✅ **SHA-256 for source** — every pinned source has a hash
- ✅ **SHA-256 for wheel** — every artifact has a hash
- ✅ **Pinned GitHub Actions** — all actions pinned with commit SHA
- ✅ **No untrusted shell input** — workflow inputs validated
- ✅ **No arbitrary package build** — package allowlist enforced
- ✅ **ZIP traversal protection** — inspect_wheel.py checks paths
- ✅ **Staging directory** — wheels extracted to staging before commit
- ✅ **Atomic installation** — transactional install with rollback
- ✅ **License record** — every package records upstream license
- ✅ **Exact source URL** — no ambiguous source references
- ✅ **Patch storage** — all patches stored in repository
- ✅ **Build log availability** — CI logs preserved as artifacts
- ✅ **Wrong ABI rejection** — ZabaPip rejects mismatched ABI before extraction
- ✅ **Wrong runtime rejection** — ZabaPip rejects mismatched runtime_id
- ✅ **Hash mismatch rejection** — ZabaPip rejects hash mismatch
- ✅ **No credentials in repo** — .gitignore blocks credential files

## Future Security Measures

- ⬜ **Sigstore keyless signing** — artifact signing
- ⬜ **GitHub artifact attestations** — provenance
- ⬜ **SBOM (SPDX or CycloneDX)** — software bill of materials
- ⬜ **Reproducible build comparison** — deterministic builds
- ⬜ **Vulnerability advisory** — CVE tracking
- ⬜ **Revocation list** — revoked artifacts indexed
- ⬜ **Dependency vulnerability scanning** — upstream CVEs

## Threat Model

| Threat | Mitigation |
|---|---|
| Source upstream replaced | Source SHA-256 pinning |
| Release artifact tampered | Artifact SHA-256 + (future: Sigstore) |
| Hash mismatch | ZabaPip rejects mismatched hash |
| Wheel path traversal | inspect_wheel.py path check |
| Wrong-ABI wheel causes crash | ELF inspection + ABI check |
| Native library links to private API | DT_NEEDED inspection |
| Malicious package writes outside install root | Staging + atomic commit |
| Workflow injection | Pinned actions + validated inputs |
| Compromised GitHub Action | SHA pinning + allowlist |
| Dependency confusion | ZABAWHEELS index + priority |
| Rollback to vulnerable package | Revocation + replacement metadata |

## Installer Security Policy

ZabaPip MUST NOT:
- Run `setup.py` from arbitrary packages on device
- Compile sdist on phone
- Execute uncontrolled post-install scripts
- Disable TLS verification
- Ignore hash mismatch
- Overwrite old package before verifying candidate

## No Silent Fallback

If a package is unavailable or fails, ZabaPip must show the real reason:

```text
Package numpy 2.x not available for:
  Runtime : zabacode-pyXXX-api26-p4aXXX-r1
  ABI     : armeabi-v7a
  Status  : planned
```

Never silently:
- Install wrong version
- Use wrong ABI wheel
- Assume import succeeds without test
- Show fake progress
- Claim permissions or dependencies exist
