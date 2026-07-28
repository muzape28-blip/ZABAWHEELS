# Contributing to ZABAWHEELS

Thank you for your interest in ZABAWHEELS! This project is a curated Android wheelhouse for Zabacode, and contributions are welcome.

## Status

⚠️ ZABAWHEELS is in **pre-alpha** (M0). Infrastructure is being set up. The build pipeline is not yet functional — cross-compilation requires M1 gate completion.

## How to Contribute

### Requesting a Package

1. Use the [Package Request](https://github.com/muzape28-blip/ZABAWHEELS/issues/new?template=package-request.yml) issue template.
2. Fill in all required fields: name, version, upstream URL, license, build system, dependencies.
3. Package requests are evaluated based on ARMv7 feasibility, license clarity, and build simplicity.

### Reporting a Build Failure

1. Use the [Build Failure](https://github.com/muzape28-blip/ZABAWHEELS/issues/new?template=build-failure.yml) issue template.
2. Include the package name, version, runtime ID, ABI, and the full error log.

### Submitting a Device Test Report

1. Use the [Device Test Report](https://github.com/muzape28-blip/ZABAWHEELS/issues/new?template=device-test.yml) issue template.
2. Be honest — a "fail" result is more valuable than a false "pass".
3. Include your device model, ABI, Android version, and test results.
4. ARM64 reports are especially welcome (we don't have an ARM64 device yet).

### Adding a Recipe

1. Copy `packages/package-template/recipe.yaml` as a starting point.
2. Fill in all required fields (no placeholders in stable recipes).
3. Create a directory under `packages/<package-name>/` with:
   - `recipe.yaml` — build definition
   - `patches/` — any Android-specific patches (optional)
4. Submit via pull request.
5. Recipe must pass `python scripts/validate_recipes.py --package <name>`.

### Improving Documentation

- Documentation is in `docs/` and at the top of scripts.
- All changes via pull request.
- Keep documentation honest about status — don't claim things work if they don't.

## Rules

### Truth-first

- Every status must mean something real.
- "Build successful" ≠ "working on Android".
- Don't add `device-verified` unless you actually tested on a device.
- Don't add `stable` unless all gates passed.

### No Binary in Git

- Wheel files (*.whl) are NEVER committed to Git.
- Use GitHub Releases for artifact hosting.
- Use GitHub Pages for the index.
- Build output goes through CI, not through commits.

### No Credentials

- Never commit .env, .pem, .key, .token, or credentials files.
- No PAT embedded in workflows or applications.
- GitHub Actions use GITHUB_TOKEN for publishing.

### Security

- All GitHub Actions must be pinned with commit SHA.
- No arbitrary package build from user input.
- Package allowlist is enforced.
- Source must have version and SHA-256.

### Patches

- All patches are stored in `packages/<name>/patches/`.
- Patches must be listed in recipe.yaml.
- Patches are applied in order listed.
- Patch purpose must be documented.

## Development Setup

```sh
# Clone repository
git clone https://github.com/muzape28-blip/ZABAWHEELS.git
cd ZABAWHEELS

# Install Python dependencies
pip install pyyaml jsonschema pytest

# Validate repository structure
python scripts/validate_recipes.py

# Run tests
python -m pytest tests/ -v
```

## Workflow from Phone

This project is designed for development from a single Android phone:

```text
1. Edit recipe via HP/Arena
2. Push to GitHub
3. GitHub Actions runs build
4. CI produces candidate artifact
5. ZabaPip developer mode reads experimental index
6. Install candidate on Infinix
7. Run smoke test
8. Export device report
9. Upload report to issue or PR
10. Promote candidate to stable
```

The phone doesn't need to run NDK, C compiler, or build tools. The phone validates runtime behavior.

## License

- ZABAWHEELS source code, scripts, recipes, documentation: GNU AGPL-3.0
- Wheel artifacts follow the license of their upstream package
- Every package must record its upstream license in recipe.yaml
