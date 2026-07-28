# ZABAWHEELS — Architecture & Development Roadmap

> **Status:** Planning / Pre-Alpha  
> **Dokumen:** Roadmap utama ZABAWHEELS  
> **Tanggal:** 29 Juli 2026  
> **Target utama:** Zabacode pada Android ARMv7 dan ARM64  
> **Perangkat verifikasi awal:** Infinix Smart 9 HD, ARMv7, Android 14 Go

---

## Daftar Isi

1. [Latar Belakang](#1-latar-belakang)
2. [Visi Proyek](#2-visi-proyek)
3. [Batasan dan Non-Goals](#3-batasan-dan-non-goals)
4. [Prinsip Dasar](#4-prinsip-dasar)
5. [Arsitektur Dua Repository](#5-arsitektur-dua-repository)
6. [Struktur Repository ZABAWHEELS](#6-struktur-repository-zabawheels)
7. [Compatibility Contract](#7-compatibility-contract)
8. [Release Channel](#8-release-channel)
9. [Milestone Roadmap](#9-milestone-roadmap)
10. [Package Lifecycle](#10-package-lifecycle)
11. [Testing Matrix](#11-testing-matrix)
12. [Security dan Supply Chain](#12-security-dan-supply-chain)
13. [Hosting dan Penyimpanan](#13-hosting-dan-penyimpanan)
14. [Workflow Harian dari HP](#14-workflow-harian-dari-hp)
15. [Risk Register](#15-risk-register)
16. [Urutan Prioritas](#16-urutan-prioritas)
17. [Definition of Done](#17-definition-of-done)
18. [Kesimpulan](#18-kesimpulan)
19. [Referensi Teknis](#19-referensi-teknis)

---

# 1. Latar Belakang

Zabacode membutuhkan lingkungan package Python Android yang nyata agar dapat berkembang menjadi IDE dan interpreter yang mendekati pengalaman Pydroid. Package pure Python umumnya dapat dipasang langsung, tetapi package seperti NumPy, Pillow, Pandas, SciPy, Lxml, dan Cryptography mengandung native extension yang harus dikompilasi khusus untuk Android.

Wheel Linux biasa tidak dapat digunakan begitu saja karena:

- Linux desktop umumnya menggunakan `glibc`, sedangkan Android menggunakan `Bionic`.
- Native extension harus cocok dengan versi dan ABI CPython.
- Binary harus dibangun untuk ABI perangkat yang benar.
- Android memiliki aturan dynamic linker, API level, dan keamanan executable yang berbeda.
- ARMv7 tidak termasuk target utama wheel Android modern berbasis PEP 738.

Kondisi pengembangan awal:

- Developer utama hanya memiliki Infinix Smart 9 HD ARMv7.
- Build berat dilakukan menggunakan GitHub Actions.
- HP digunakan sebagai perangkat verifikasi runtime nyata.
- Zabacode menggunakan Buildozer dan python-for-Android.
- Tidak boleh ada package, output, status, permission, atau keberhasilan palsu.

Karena itu, ZABAWHEELS dibangun sebagai **curated Android wheelhouse untuk runtime Zabacode**, bukan sebagai mirror seluruh PyPI.

---

# 2. Visi Proyek

## 2.1 Tujuan utama

ZABAWHEELS adalah repository recipe, build pipeline, manifest, dan artifact wheel Android terkurasi untuk Zabacode.

Alur utamanya:

```text
Source package
      ↓
Cross-compile di GitHub Actions
      ↓
Validasi wheel, ELF, metadata, dan dependency
      ↓
Publikasi wheel + manifest + SHA-256
      ↓
ZabaPip memilih wheel yang kompatibel
      ↓
Install dan import di Android
```

Target pengalaman pengguna:

```sh
zpip search numpy
zpip info numpy
zpip install numpy
zpip verify numpy
zpip uninstall numpy
```

Hasil instalasi harus dapat dibuktikan:

```python
import numpy

print(numpy.__version__)
print(numpy.array([1, 2, 3]).sum())
```

## 2.2 Sasaran jangka panjang

- Menyediakan package native Android yang benar-benar bekerja di Zabacode.
- Mempertahankan dukungan ARMv7 selama masih realistis.
- Menyediakan build ARM64 melalui CI.
- Membuat setiap package dapat diaudit dan direproduksi.
- Mengintegrasikan package manager nyata dengan ZMUX.
- Menyediakan status kompatibilitas berdasarkan hasil test, bukan klaim.
- Membuka peluang kontribusi recipe dan device testing dari komunitas.

---

# 3. Batasan dan Non-Goals

ZABAWHEELS v0.x tidak bertujuan untuk:

- Menjadi mirror seluruh PyPI.
- Menyaingi jumlah package Pydroid dalam waktu singkat.
- Menyediakan APT, Termux, atau package Linux umum.
- Mengompilasi native package langsung di HP pengguna.
- Mendukung semua versi Python secara bersamaan.
- Mendukung semua versi dari setiap package.
- Menganggap build sukses sebagai bukti package berjalan.
- Mengklaim ARM64 teruji sebelum ada device report ARM64.
- Memasang source distribution dan mengompilasinya secara otomatis di HP.
- Mengganti nama wheel Linux menjadi wheel Android.
- Menjalankan executable hasil download dari direktori writable.
- Meniru output instalasi atau command yang sebenarnya gagal.

Prinsip scope awal:

> Lebih baik menyediakan lima package yang benar-benar stabil daripada lima puluh package dengan status yang tidak jelas.

---

# 4. Prinsip Dasar

## 4.1 Truth-first

Setiap status package harus mempunyai arti yang jelas.

| Status | Arti |
|---|---|
| `planned` | Baru direncanakan |
| `researching` | Kompatibilitas sedang diteliti |
| `recipe-ready` | Recipe dan patch awal tersedia |
| `building` | Proses build sedang dijalankan |
| `built` | Cross-compilation selesai |
| `inspected` | ELF dan metadata telah diperiksa |
| `installable` | Installer berhasil memasang artifact |
| `imported` | Package berhasil di-import |
| `smoke-passed` | Fungsi dasar berhasil dijalankan |
| `device-verified` | Diuji pada perangkat nyata |
| `stable` | Lulus seluruh gate untuk runtime tertentu |
| `broken` | Terbukti tidak bekerja |
| `blocked` | Terhalang upstream, toolchain, atau dependency |
| `deprecated` | Tidak lagi direkomendasikan |
| `revoked` | Artifact ditarik karena masalah keamanan atau kerusakan serius |

`Build successful` tidak sama dengan `working on Android`.

## 4.2 Runtime-locked

Setiap native wheel hanya dianggap kompatibel dengan runtime contract tertentu:

```text
Python version
+ Python ABI/SOABI
+ Android ABI
+ p4a commit
+ NDK version
+ minimum Android API
+ native dependencies
= satu compatibility contract
```

## 4.3 ARMv7-first, bukan ARMv7-only

ARMv7 menjadi target device verification awal karena perangkat utama menggunakan ARMv7. ARM64 tetap dibangun melalui CI, tetapi status harus dibedakan:

```text
ARMv7 : device-verified
ARM64 : build-only / unverified
```

Status ARM64 hanya boleh dinaikkan setelah menerima hasil test perangkat nyata atau emulator yang valid.

## 4.4 CI builds, phone validates

| Komponen | Tanggung jawab |
|---|---|
| Infinix Smart 9 HD | Runtime test ARMv7 nyata |
| GitHub Actions | Cross-compile, lint, static inspection, artifact publishing |
| ZABAWHEELS | Recipe, patch, manifest, index, build provenance |
| ZABACODE | Installer, resolver, runtime fingerprint, diagnostic, ZMUX integration |
| Arena Agent | Implementasi, audit, CI, dokumentasi, dan review |
| Komunitas | Pengujian ABI dan perangkat tambahan |

HP bukan mesin build utama. HP adalah laboratorium runtime.

## 4.5 No silent fallback

Jika package tidak tersedia atau gagal, sistem harus menampilkan penyebab sebenarnya.

Contoh:

```text
Package numpy 2.x tidak tersedia untuk:
  Runtime : zabacode-pyXXX-api26-p4aXXX-r1
  ABI     : armeabi-v7a
  Status  : planned
```

Sistem tidak boleh diam-diam:

- Memasang versi yang salah.
- Menggunakan wheel ABI lain.
- Menganggap import berhasil tanpa test.
- Menampilkan progress palsu.
- Mengklaim permission atau dependency tersedia.

---

# 5. Arsitektur Dua Repository

## 5.1 Repository ZABAWHEELS

Bertanggung jawab atas:

- Toolchain lock.
- Runtime compatibility definition.
- Source package lock.
- Build recipes.
- Upstream patches.
- Cross-compilation.
- ELF inspection.
- Wheel metadata verification.
- Package manifest.
- Compatibility index.
- Release artifact.
- Device-test record.
- Package revocation.

## 5.2 Repository ZABACODE

Bertanggung jawab atas:

- Runtime fingerprint exporter.
- ZabaPip installer.
- Dependency resolver.
- Package selection berdasarkan ABI dan runtime.
- Download dan SHA-256 verification.
- Transactional installation.
- Import smoke test.
- Uninstall dan rollback.
- Package diagnostics.
- ZMUX command integration.
- UI package manager.

## 5.3 Diagram integrasi

```text
┌──────────────────────────────┐
│         ZABAWHEELS           │
│ recipes → CI → release/index │
└──────────────┬───────────────┘
               │ HTTPS + manifest + SHA-256
               ▼
┌──────────────────────────────┐
│           ZABACODE           │
│ ZabaPip → verify → install   │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Python runtime pada Android  │
│ ARMv7 / ARM64                │
└──────────────────────────────┘
```

---

# 6. Struktur Repository ZABAWHEELS

```text
ZABAWHEELS/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── package-request.yml
│   │   ├── build-failure.yml
│   │   └── device-test.yml
│   └── workflows/
│       ├── validate-recipe.yml
│       ├── build-smoke.yml
│       ├── build-package.yml
│       ├── test-wheel.yml
│       ├── publish-candidate.yml
│       ├── publish-stable.yml
│       └── generate-index.yml
│
├── toolchain/
│   ├── runtime-lock.json
│   ├── source-lock.json
│   ├── Dockerfile
│   └── README.md
│
├── packages/
│   ├── zaba-native-smoke/
│   │   ├── recipe.yaml
│   │   ├── pyproject.toml
│   │   ├── src/
│   │   └── tests/
│   ├── package-template/
│   │   ├── recipe.yaml
│   │   └── patches/
│   ├── pillow/
│   ├── numpy/
│   └── matplotlib/
│
├── scripts/
│   ├── build.py
│   ├── inspect_wheel.py
│   ├── inspect_elf.py
│   ├── generate_manifest.py
│   ├── generate_index.py
│   ├── verify_dependencies.py
│   └── promote_release.py
│
├── schemas/
│   ├── runtime.schema.json
│   ├── recipe.schema.json
│   ├── package-manifest.schema.json
│   └── device-report.schema.json
│
├── index/
│   ├── experimental/
│   ├── candidate/
│   └── stable/
│
├── tests/
│   ├── test_recipes.py
│   ├── test_manifests.py
│   ├── test_index.py
│   └── test_wheel_security.py
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── BUILDING.md
│   ├── COMPATIBILITY.md
│   ├── DEVICE_TESTING.md
│   ├── PACKAGE_LIFECYCLE.md
│   └── SECURITY.md
│
├── CONTRIBUTING.md
├── LICENSE
└── README.md
```

File `.whl`, debug symbol besar, dan build output tidak disimpan di Git history.

---

# 7. Compatibility Contract

## 7.1 Runtime ID

Setiap generasi runtime memiliki identifier unik.

Contoh format:

```text
zabacode-py312-api26-p4a1-r1
```

Format konseptual:

```text
zabacode-py<python>-api<minapi>-p4a<revision>-r<generation>
```

`py312` hanya contoh. Versi sebenarnya harus diambil dari APK dan dikunci setelah runtime probe.

## 7.2 Runtime manifest

```json
{
  "schema_version": 1,
  "runtime_id": "zabacode-pyXXX-api26-p4aXXX-r1",
  "python": {
    "implementation": "CPython",
    "version": "BELUM_DIPERIKSA",
    "soabi": "BELUM_DIPERIKSA",
    "ext_suffix": "BELUM_DIPERIKSA"
  },
  "android": {
    "min_api": 26,
    "target_api": 34,
    "abis": [
      "armeabi-v7a",
      "arm64-v8a"
    ]
  },
  "toolchain": {
    "p4a_commit": "BELUM_DIPIN",
    "ndk_version": "BELUM_DIPIN",
    "ndk_api": 26,
    "clang_version": "BELUM_DIPERIKSA"
  }
}
```

Placeholder tidak boleh dipakai dalam stable runtime manifest.

## 7.3 Perubahan yang menghasilkan runtime generation baru

- Upgrade minor CPython.
- Perubahan SOABI atau extension suffix.
- Upgrade p4a yang memengaruhi ABI.
- Perubahan NDK besar.
- Perubahan minimum NDK/API.
- Perubahan struktur native library.
- Perubahan mekanisme dynamic loading.
- Perubahan build flags yang memengaruhi ABI atau CPU requirement.

Wheel lama tidak boleh ditimpa menggunakan binary dengan contract baru.

## 7.4 Runtime fingerprint yang wajib dikumpulkan

```python
import os
import platform
import struct
import sys
import sysconfig

report = {
    "python_version": sys.version,
    "implementation": platform.python_implementation(),
    "machine": platform.machine(),
    "pointer_bits": struct.calcsize("P") * 8,
    "platform": sysconfig.get_platform(),
    "soabi": sysconfig.get_config_var("SOABI"),
    "ext_suffix": sysconfig.get_config_var("EXT_SUFFIX"),
    "executable": sys.executable,
    "android_api": os.environ.get("ANDROID_API")
}
```

Diagnostic final juga perlu mengumpulkan:

- Device ABI list.
- Android release dan API level.
- App version.
- Page size.
- Lokasi `user_packages`.
- Daftar extension suffix yang diterima Python.
- Runtime library path.
- Filesystem dan dynamic loading capability.

---

# 8. Release Channel

## 8.1 Experimental

Digunakan untuk build mentah:

- Belum diuji di perangkat.
- Boleh gagal import.
- Tidak ditampilkan kepada pengguna biasa.
- Hanya tersedia melalui developer mode.
- Bisa dihapus atau diganti tanpa jaminan kompatibilitas.

## 8.2 Candidate

Syarat minimum:

- Build sukses.
- ELF telah diperiksa.
- Metadata wheel valid.
- Dependency telah dicatat.
- SHA-256 tersedia.
- Installer dapat membaca manifest.
- Sedang menunggu atau menjalani device test.

## 8.3 Stable

Syarat minimum:

- Install berhasil.
- Import berhasil.
- Smoke test berhasil.
- Restart interpreter tetap berhasil.
- Restart aplikasi tetap berhasil.
- Uninstall atau rollback berhasil.
- Tidak membuat aplikasi crash.
- Device report disimpan.
- Source, patch, hash, dan license tercatat.

## 8.4 Revoked

Artifact dapat ditarik jika ditemukan:

- Kerentanan keamanan.
- Hash atau source provenance bermasalah.
- Crash serius.
- Data corruption.
- Wrong-ABI artifact.
- Dependency native yang tidak lengkap.

Contoh metadata:

```json
{
  "revoked": true,
  "reason": "Crashes on ARMv7 Android 14",
  "replacement": "1.2.1",
  "severity": "high"
}
```

---

# 9. Milestone Roadmap

## M0 — Membentuk Repository

### Tujuan

Membuat fondasi proyek tanpa langsung mengompilasi package besar.

### Tugas

- Membuat repository public bernama `ZABAWHEELS`.
- Menambahkan README dan tujuan proyek.
- Menambahkan license untuk source builder.
- Membuat struktur direktori awal.
- Menambahkan issue template.
- Mengaktifkan GitHub Actions.
- Mengaktifkan GitHub Releases.
- Menyiapkan GitHub Pages untuk package index.
- Menambahkan branch protection pada `main`.
- Mem-pin GitHub Actions menggunakan commit SHA.
- Melarang wheel binary masuk Git history.
- Menambahkan `.gitignore` untuk output build.
- Menambahkan basic schema validation.

### License

License ZABAWHEELS hanya mencakup:

- Script builder.
- Recipe buatan proyek.
- Dokumentasi.
- Patch buatan proyek.

Wheel hasil build mengikuti license package upstream. Setiap package harus mencatat:

- Nama upstream.
- Source URL.
- Versi.
- Source SHA-256.
- License upstream.
- Patch yang diterapkan.
- Build instructions.

### Gate M0

- Repository dapat di-clone.
- CI validation dasar berjalan.
- Tidak ada binary besar di Git.
- README menjelaskan status experimental.
- Tidak ada credential atau PAT di repository.

---

## M1 — Runtime Fingerprint dan Toolchain Freeze

### Tujuan

Mengetahui runtime Zabacode yang sebenarnya, bukan menebaknya.

### Perubahan di ZABACODE

Tambahkan diagnostic exporter untuk menghasilkan runtime report lengkap.

### Toolchain yang harus dipin

- Buildozer.
- python-for-Android commit.
- CPython version.
- Android NDK version.
- Android SDK/API.
- NDK API.
- Cython.
- Setuptools.
- Wheel.
- Pip.
- Host Python CI.

### Keputusan versi Python

Jangan memilih Python 3.12, 3.13, atau 3.14 berdasarkan asumsi.

Urutan keputusan:

1. Periksa versi runtime APK saat ini.
2. Periksa stabilitas build ARMv7.
3. Periksa ketersediaan recipe package target.
4. Pilih satu minor Python.
5. Pin versi dan toolchain.
6. Bangun ulang APK.
7. Verifikasi fingerprint tidak berubah.
8. Baru mulai menghasilkan native wheel.

ARMv7 bukan target resmi utama PEP 738, sehingga jalur ARMv7 akan bersifat Zabacode/p4a-specific.

### Gate M1

Tersedia satu `runtime-lock.json` dengan nilai nyata dari APK. Tidak boleh ada placeholder.

---

## M2 — Native Feasibility Spike

### Tujuan

Membuktikan bahwa Zabacode dapat:

1. Mengunduh wheel native ARMv7.
2. Memverifikasi wheel.
3. Mengekstrak wheel ke app-private storage.
4. Meng-import extension `.so`.
5. Menjalankan fungsi native.
6. Tetap bekerja setelah restart.

### Package pertama

```text
zaba-native-smoke
```

API minimal:

```python
import zaba_native_smoke

assert zaba_native_smoke.add(20, 22) == 42
assert zaba_native_smoke.runtime_info()["abi"] == "armeabi-v7a"
```

Package ini tidak membutuhkan dependency eksternal.

### Pemeriksaan CI

- Validasi struktur ZIP/wheel.
- Periksa `WHEEL` metadata.
- Periksa `METADATA`.
- Periksa `RECORD`.
- Jalankan `file` pada `.so`.
- Jalankan `readelf -h`.
- Jalankan `readelf -d`.
- Verifikasi ELF architecture.
- Verifikasi `DT_NEEDED`.
- Cari text relocation.
- Cari dependency ke private Android libraries.
- Hitung SHA-256.
- Periksa file traversal.
- Periksa duplicate atau unexpected file.

Wheel ARMv7 tidak boleh:

- Berisi ELF x86.
- Berisi ELF ARM64.
- Link terhadap glibc.
- Link ke private Android API.
- Memiliki text relocation.
- Bergantung pada `.so` yang tidak tersedia.
- Mengandung unsafe archive path.

### Device test pada Infinix

1. Install APK debug Zabacode.
2. Export runtime report.
3. Download smoke wheel.
4. Verifikasi SHA-256.
5. Install ke staging directory.
6. Pindahkan secara atomik.
7. Jalankan import.
8. Panggil fungsi `add`.
9. Restart interpreter.
10. Import ulang.
11. Restart aplikasi.
12. Import ulang.
13. Uninstall package.
14. Pastikan import gagal secara bersih.
15. Install ulang.
16. Pastikan package kembali berfungsi.

### Keputusan Gate M2

#### Hasil A — Native loading berhasil

Lanjutkan model runtime wheel repository.

#### Hasil B — Native loading gagal karena batasan Android/runtime

Jangan membuat workaround palsu. Gunakan strategi alternatif:

- Runtime install hanya untuk pure Python.
- Native package dibundel ketika APK dibangun.
- Optional native package pack atau flavor APK.
- ZabaPip menandai package native sebagai `requires-rebuild`.

M2 menentukan apakah model instalasi native seperti Pydroid memungkinkan pada arsitektur Zabacode saat ini.

---

## M3 — Build Factory di GitHub Actions

### Tujuan

Mengubah eksperimen manual menjadi proses reproducible.

### Workflow input

```text
package
version
runtime_id
abi
channel
```

Contoh:

```text
package    = zaba-native-smoke
version    = 0.1.0
runtime_id = zabacode-pyXXX-api26-p4aXXX-r1
abi        = armeabi-v7a
channel    = experimental
```

### Tahapan CI

```text
validate recipe
    ↓
download pinned source
    ↓
verify source SHA-256
    ↓
prepare exact toolchain
    ↓
cross-compile
    ↓
build wheel
    ↓
inspect ELF
    ↓
validate metadata
    ↓
generate manifest
    ↓
upload workflow artifact
```

### Aturan keamanan CI

- Pull request dari fork tidak boleh memublikasikan release.
- Publishing hanya dilakukan protected workflow.
- Package recipe harus berada dalam allowlist.
- Raw shell command tidak boleh menjadi workflow input.
- Source wajib memiliki version dan hash.
- GitHub Actions dipin menggunakan commit SHA.
- Release menggunakan `GITHUB_TOKEN`.
- PAT tidak ditanam di aplikasi atau workflow.
- Cache key mencakup p4a, Python, NDK, ABI, dan package version.
- Build log dan manifest wajib disimpan.

### Gate M3

Dua build dari source dan toolchain yang sama menghasilkan artifact yang fungsional identik. Jika hash berbeda karena timestamp atau metadata, penyebabnya harus diketahui dan didokumentasikan.

---

## M4 — Package Manifest dan Index

### Tujuan

Membuat ZabaPip dapat menemukan package yang tepat.

Untuk tahap awal, gunakan custom JSON index. Jangan bergantung penuh pada PEP 503 karena jalur ARMv7 bukan target standar Android wheel modern.

### Struktur URL

```text
https://<owner>.github.io/ZABAWHEELS/index/v1/
├── runtimes.json
└── runtimes/
    └── zabacode-pyXXX-api26-p4aXXX-r1/
        ├── packages.json
        ├── armeabi-v7a.json
        └── arm64-v8a.json
```

### Contoh package manifest

```json
{
  "schema_version": 1,
  "name": "zaba-native-smoke",
  "version": "0.1.0",
  "runtime_id": "zabacode-pyXXX-api26-p4aXXX-r1",
  "python_tag": "cpXXX",
  "abi": "armeabi-v7a",
  "android_min_api": 26,
  "channel": "candidate",
  "artifact": {
    "filename": "zaba_native_smoke-0.1.0-....whl",
    "url": "https://github.com/.../releases/download/...",
    "size": 12345,
    "sha256": "..."
  },
  "dependencies": [],
  "native": {
    "has_extensions": true,
    "needed_libraries": [
      "libpythonX.Y.so",
      "libc.so",
      "libm.so"
    ]
  },
  "source": {
    "url": "https://github.com/...",
    "sha256": "...",
    "license": "MIT"
  },
  "verification": {
    "build_passed": true,
    "elf_inspected": true,
    "device_tested": true,
    "tested_devices": [
      {
        "model": "Infinix Smart 9 HD",
        "abi": "armeabi-v7a",
        "android": "14",
        "result": "pass"
      }
    ]
  }
}
```

### Gate M4

- Index dapat diakses tanpa token.
- SHA-256 cocok dengan artifact.
- Tidak ada private URL.
- Schema validation lulus.
- Tidak ada dua artifact ambigu untuk runtime yang sama.
- Experimental, candidate, dan stable terpisah.
- Wrong-runtime package tidak muncul sebagai compatible.

---

## M5 — ZabaPip v2

### Tujuan

Mengganti direct wheel extractor sederhana dengan installer transaksional.

### Alur instalasi

```text
User meminta package
       ↓
Normalisasi nama
       ↓
Baca runtime fingerprint
       ↓
Ambil index yang kompatibel
       ↓
Pilih versi dan ABI
       ↓
Resolve dependencies
       ↓
Download ke cache sementara
       ↓
Verifikasi TLS + SHA-256
       ↓
Validasi wheel
       ↓
Ekstrak ke staging
       ↓
Import smoke test
       ↓
Atomic commit
       ↓
Catat installed manifest
```

### Transactional installation

Jangan mengekstrak langsung ke `user_packages`.

Gunakan struktur:

```text
cache/downloads/
staging/<transaction-id>/
user_packages/
installed/
```

Jika import gagal:

```text
hapus staging
kembalikan versi lama
laporkan error asli
```

### Installed database

```json
{
  "numpy": {
    "version": "x.y.z",
    "runtime_id": "...",
    "abi": "armeabi-v7a",
    "files": [
      "numpy/__init__.py",
      "numpy/core/....so"
    ],
    "sha256": "...",
    "installed_at": "..."
  }
}
```

### Command awal

```sh
zpip search numpy
zpip info numpy
zpip install numpy
zpip list
zpip verify numpy
zpip uninstall numpy
zpip doctor
```

Tidak menyediakan:

```sh
apt
pkg
sudo
```

### Dependency resolver v1

Cukup mendukung:

- Exact version.
- Minimum/maximum version sederhana.
- Dependency DAG.
- Cycle detection.
- Package conflict.
- Already-installed detection.
- Upgrade/downgrade eksplisit.

Tidak perlu langsung menyamai seluruh pip resolver.

### Gate M5

- Install bersifat atomic.
- Kegagalan tidak merusak package lama.
- Uninstall hanya menghapus file milik package terkait.
- Hash mismatch ditolak.
- Wrong ABI ditolak.
- Wrong runtime ditolak.
- Storage penuh menghasilkan error bersih.
- Tidak ada error yang ditelan dengan `except: pass`.

---

## M6 — Package Native Pihak Ketiga Pertama

### Tujuan

Membuktikan pipeline bekerja untuk package pihak ketiga, bukan hanya smoke package buatan sendiri.

### Kandidat

- `xxhash`
- `ujson`
- `regex`
- Native extension kecil tanpa dependency kompleks

Pemilihan final dilakukan setelah survey build system, license, dan kompatibilitas ARMv7.

### Kriteria

- Source terbuka.
- License jelas.
- Build system sederhana.
- Tidak membutuhkan Fortran.
- Tidak membutuhkan banyak shared library.
- Mempunyai smoke test kecil.
- Ukuran wheel kecil.
- Secara teknis masih mendukung ARMv7.

### Gate M6

Package harus:

- Berhasil build.
- Berhasil install.
- Berhasil import.
- Menjalankan fungsi native.
- Bertahan setelah restart.
- Berhasil uninstall.
- Tidak menambah crash Zabacode.

Setelah M6, ZABAWHEELS dapat disebut sebagai technical proof-of-concept yang berhasil.

---

## M7 — Package Ladder

Package dikerjakan berdasarkan tingkat kompleksitas.

### Tier 0 — Pure Python

Tidak perlu dibangun ulang jika tersedia wheel universal:

```text
py3-none-any.whl
```

ZABAWHEELS cukup menyediakan compatibility metadata atau membiarkan ZabaPip menggunakan PyPI dengan verifikasi yang aman.

Contoh:

- Requests.
- SymPy.
- Rich.
- Click.
- BeautifulSoup.
- Package pure Python lain.

### Tier 1 — Native ringan

- `xxhash`.
- `ujson`.
- `regex`.
- Package kompresi sederhana.
- Extension C kecil.

### Tier 2 — Native user-facing

#### Pillow

Smoke test:

```python
from PIL import Image

img = Image.new("RGB", (100, 100), "red")
img.save("test.png")
```

Periksa:

- JPEG.
- PNG.
- Zlib.
- FreeType jika disertakan.
- File save/load.
- Memory usage ARMv7.

#### NumPy

Smoke test:

```python
import numpy as np

a = np.array([1, 2, 3])
assert int(a.sum()) == 6
assert np.dot(a, a) == 14
```

Periksa:

- BLAS backend.
- CPU instruction compatibility.
- Import time.
- RAM.
- Array operations.
- Save/load `.npy`.
- Thread count.

### Tier 3 — Scientific stack

Setelah NumPy stabil:

- Matplotlib.
- Pandas.
- OpenCV subset jika realistis.

Matplotlib smoke test:

```python
import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt

plt.plot([1, 2, 3])
plt.savefig("plot.png")
```

Pandas smoke test:

```python
import pandas as pd

df = pd.DataFrame({"a": [1, 2, 3]})
assert int(df["a"].sum()) == 6
```

### Tier 4 — Heavy/experimental

Dikerjakan terakhir:

- SciPy.
- Cryptography.
- Lxml.
- Scikit-learn.
- OpenCV full.
- Package berbasis Rust kompleks.
- Package dengan Fortran atau BLAS besar.

Tier 4 tidak menjadi syarat rilis awal.

---

## M8 — Integrasi ZMUX

### Tujuan

Menjadikan ZMUX antarmuka nyata terhadap ZabaPip.

### Command

```sh
zmux> zpip search numpy
zmux> zpip install numpy
zmux> python
>>> import numpy
```

### Aturan

- `zpip` adalah internal command dispatcher.
- Jangan membuat executable shim di app-data.
- Jangan mengaku sebagai `apt` atau `pkg`.
- Output harus berasal dari installer sebenarnya.
- Progress berasal dari byte download dan state sebenarnya.
- Exit code harus benar.
- Pengguna dapat membatalkan download/install.
- Cancel harus menjalankan rollback.

### Contoh output jujur

```text
ZMUX: numpy 2.x tidak tersedia untuk:
  Runtime : zabacode-pyXXX-api26-p4aXXX-r1
  ABI     : armeabi-v7a

Available status: planned
```

Jika ARM64 belum diuji:

```text
Warning: wheel ini berhasil dibangun untuk ARM64 tetapi belum
terverifikasi pada perangkat ARM64 fisik.
```

---

## M9 — Alpha Release

### Target

```text
ZABAWHEELS v0.1.0-alpha
```

### Isi minimum

- Runtime terkunci.
- Native smoke wheel.
- Satu package native pihak ketiga.
- Custom package index.
- ZabaPip transactional installer.
- SHA-256 verification.
- Install/uninstall/rollback.
- Device report ARMv7.
- Dokumentasi build.
- Tidak ada mock.

### Bukan syarat alpha

- NumPy.
- Pandas.
- SciPy.
- ARM64 device verification.
- Full pip resolver.
- Puluhan package.

Alpha pertama membuktikan infrastrukturnya, bukan jumlah package.

---

## M10 — Scientific Preview

### Target

```text
ZABAWHEELS v0.2.0-scientific-preview
```

### Isi

- Pillow ARMv7.
- NumPy ARMv7.
- Matplotlib jika NumPy stabil.
- Package compatibility UI.
- Download resume.
- Disk-space estimator.
- Dependency conflict report.
- Package verification command.
- Export diagnostic report.

### Gate NumPy

NumPy tidak boleh dianggap stabil hanya karena berhasil import. Wajib menguji:

- Array creation.
- Dot product.
- Random operations.
- Save/load.
- Repeated imports.
- App restart.
- Interpreter restart.
- Memory pressure.
- Penggunaan selama 20–30 menit.
- Beberapa ukuran array.

---

## M11 — ARM64 dan Community Testing

### Tujuan

Mengurangi ketergantungan pada satu perangkat tanpa meninggalkan ARMv7.

### Langkah

- Build ARM64 melalui CI.
- Label awal sebagai `build-only`.
- Mencari tester ARM64.
- Membuat format device report sederhana.
- Tidak mengumpulkan telemetry otomatis.
- Pengguna mengirim report secara manual.
- Tidak menyimpan data pribadi.

Contoh report:

```json
{
  "package": "numpy",
  "version": "x.y.z",
  "runtime_id": "...",
  "device": {
    "model": "...",
    "abi": "arm64-v8a",
    "android": "..."
  },
  "tests": {
    "install": "pass",
    "import": "pass",
    "smoke": "pass",
    "restart": "pass",
    "uninstall": "pass"
  }
}
```

Untuk ARM64, penggunaan Android wheel standard dan `cibuildwheel` dapat dievaluasi. Jalur resmi modern berfokus pada `arm64_v8a` dan `x86_64`, bukan ARMv7.

---

## M12 — Stable v1

### Target

```text
ZABAWHEELS v1.0.0
```

### Syarat minimum

- Toolchain fully pinned.
- Runtime compatibility contract stabil.
- Native install terbukti aman.
- ZabaPip transactional.
- Index versioned.
- Source dan output hash tersedia.
- License inventory tersedia.
- Build provenance tersedia.
- ARMv7 device verification.
- Minimal satu ARM64 device verification.
- Recovery/rollback terbukti.
- Package status transparan.
- Dokumentasi contributor tersedia.
- Tidak ada mock atau gimmick.

Jumlah package bukan ukuran utama v1.

---

# 10. Package Lifecycle

Setiap package melewati lifecycle berikut:

```text
REQUESTED
    ↓
RESEARCHED
    ↓
RECIPE READY
    ↓
BUILDING
    ↓
BUILT
    ↓
ELF INSPECTED
    ↓
CANDIDATE
    ↓
DEVICE TESTED
    ↓
STABLE
```

Jalur kegagalan:

```text
BUILD FAILED
IMPORT FAILED
RUNTIME INCOMPATIBLE
BLOCKED UPSTREAM
DEPRECATED
REVOKED
```

## Isi issue package

```text
Package:
Version:
Upstream:
License:
Source hash:
Build system:
Native dependencies:
Python versions:
Target ABI:
Expected wheel size:
Known Android issues:
Smoke test:
Current status:
```

## Promotion policy

- `experimental → candidate`: build dan static inspection lulus.
- `candidate → stable`: device test dan lifecycle test lulus.
- `stable → revoked`: ditemukan masalah keamanan atau kerusakan serius.

Promosi harus melalui pull request atau protected workflow dengan audit trail.

---

# 11. Testing Matrix

## 11.1 Target awal

| Dimensi | Nilai |
|---|---|
| Device | Infinix Smart 9 HD |
| ABI | armeabi-v7a |
| OS | Android 14 Go |
| App minimum API | 26 |
| App target API | 34 |
| Python | Ditentukan setelah runtime probe |
| p4a | Dipin setelah runtime probe |
| Channel | Experimental |

Perbedaan penting:

```text
Compiled for API 26+
```

tidak sama dengan:

```text
Tested on Android API 26
```

Jika pengujian dilakukan pada Infinix Android 14, status yang jujur adalah:

```text
Minimum API declared : 26
Device tested        : Android 14
```

## 11.2 Static tests

- Schema validation.
- Metadata validation.
- Wheel filename validation.
- Source hash verification.
- Output hash generation.
- ELF architecture inspection.
- Dynamic dependency inspection.
- License verification.
- Path traversal detection.
- Duplicate file detection.
- Unexpected executable detection.
- Text relocation detection.
- Private Android API dependency detection.

## 11.3 Installation tests

- Fresh install.
- Reinstall.
- Upgrade.
- Downgrade.
- Wrong ABI.
- Wrong runtime.
- Corrupted download.
- Hash mismatch.
- Storage full.
- Interrupted download.
- Interrupted extraction.
- Rollback.

## 11.4 Runtime tests

- Import.
- Basic function.
- Repeated import.
- Interpreter restart.
- App restart.
- Error reporting.
- Memory usage.
- File I/O.
- Uninstall.
- Reinstall after uninstall.

## 11.5 Performance tests ARMv7

- Import latency.
- Peak memory usage.
- Package installation time.
- Package extraction time.
- UI responsiveness.
- Output queue behavior.
- Repeated operations.
- Long-running session stability.

---

# 12. Security dan Supply Chain

## 12.1 Wajib sejak awal

- HTTPS only.
- SHA-256 untuk source.
- SHA-256 untuk wheel.
- GitHub Actions dipin dengan commit SHA.
- Tidak menerima untrusted shell input.
- Tidak menyediakan arbitrary package build dari user input.
- Package allowlist.
- ZIP traversal protection.
- Staging directory.
- Atomic installation.
- Rollback.
- License record.
- Exact source URL.
- Patch disimpan di repository.
- Build log tersedia.
- Wrong ABI dan wrong runtime ditolak sebelum extraction.

## 12.2 Tahap berikutnya

- Sigstore keyless signing.
- GitHub artifact attestations.
- SBOM SPDX atau CycloneDX.
- Reproducible build comparison.
- Vulnerability advisory.
- Revocation list.
- Dependency vulnerability scanning.

## 12.3 Threat model utama

- Source upstream diganti.
- Release artifact disusupi.
- Hash mismatch.
- Wheel mengandung path traversal.
- Wrong-ABI wheel menyebabkan crash.
- Native library link ke private API.
- Malicious package menulis di luar install root.
- Workflow injection.
- Compromised GitHub Action.
- Dependency confusion.
- Rollback ke package rentan.

## 12.4 Installer policy

ZabaPip tidak boleh:

- Menjalankan `setup.py` dari package arbitrary pada perangkat.
- Mengompilasi sdist pada HP.
- Mengeksekusi post-install script yang tidak terkontrol.
- Menonaktifkan TLS verification.
- Mengabaikan hash mismatch.
- Menimpa package lama sebelum candidate terverifikasi.

---

# 13. Hosting dan Penyimpanan

## 13.1 Git repository

Hanya menyimpan:

- Recipe.
- Patch.
- Manifest.
- Script.
- Schema.
- Dokumentasi.
- Small test source.

## 13.2 GitHub Actions artifact

Digunakan untuk:

- Experimental build.
- Candidate sementara.
- Debug symbols.
- Build logs.
- Intermediate reports.

## 13.3 GitHub Releases

Digunakan untuk:

- Candidate yang akan diuji pada device.
- Stable wheel.
- Manifest.
- `SHA256SUMS`.
- License bundle.
- Build report.
- SBOM pada tahap lanjutan.

## 13.4 GitHub Pages

Digunakan untuk:

- Package index.
- Runtime list.
- Compatibility status.
- Documentation.
- Revocation metadata.

Binary wheel tidak dimasukkan langsung ke Git history.

---

# 14. Workflow Harian dari HP

Alur yang cocok untuk pengembangan menggunakan satu HP:

```text
1. Edit recipe atau source melalui HP/Arena
2. Push ke GitHub
3. GitHub Actions melakukan build
4. CI menghasilkan candidate artifact
5. ZabaPip developer mode membaca experimental index
6. Install candidate pada Infinix
7. Jalankan smoke test
8. Export device report
9. Upload report ke issue atau pull request
10. Promote candidate menjadi stable
```

HP tidak perlu menjalankan:

- Android NDK.
- C compiler.
- Rust compiler.
- CMake.
- NumPy build.
- SciPy build.

HP melakukan tugas paling bernilai: membuktikan binary benar-benar berjalan pada ARMv7 Android nyata.

---

# 15. Risk Register

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Python/p4a berubah | Seluruh native wheel dapat rusak | Runtime lock dan generation ID |
| Native `.so` gagal load | Model runtime native repository gagal | M2 smoke gate dan fallback build-time pack |
| ARMv7 ditinggalkan upstream | Package baru semakin sulit | Pin version, patch, dan dokumentasi |
| Dependency terlalu kompleks | Maintenance build berat | Package tiers dan allowlist |
| RAM HP terbatas | Crash/OOM | Memory test, package sizing, output limits |
| Wheel salah ABI | Import crash | Manifest dan ELF inspection |
| Supply-chain attack | Remote code execution | Source/output hashes dan pinned Actions |
| Release storage membesar | Repository sulit dirawat | GitHub Releases, bukan Git history |
| ARM64 tidak teruji | Bug pada pengguna ARM64 | Label unverified dan community tester |
| License bermasalah | Distribusi harus dihentikan | License inventory per artifact |
| Installer gagal di tengah jalan | Environment corrupt | Staging, atomic commit, rollback |
| Native dependency hilang | `dlopen` gagal | `DT_NEEDED` inspection dan runtime smoke test |
| Runtime tidak reproducible | Wheel sulit dirawat | Pin p4a, CPython, NDK, dan build image |
| API index berubah | Client lama rusak | Versioned schema dan index URL |
| Artifact stable ternyata rusak | Pengguna terdampak | Revocation mechanism dan replacement metadata |

---

# 16. Urutan Prioritas

Urutan yang tidak boleh dibalik:

```text
1. Buat repository
2. Buat runtime probe
3. Pin runtime dan toolchain
4. Bangun native smoke wheel
5. Test import pada Infinix
6. Putuskan native runtime feasible atau tidak
7. Otomatiskan build
8. Buat index
9. Buat ZabaPip v2
10. Build package native kecil
11. Pillow
12. NumPy
13. Matplotlib dan Pandas
14. ARM64 device testing
15. SciPy dan package berat
```

Jangan memulai NumPy sebelum langkah 1–10 selesai.

## Prioritas release

### v0.0.x — Infrastructure spike

- Runtime fingerprint.
- Toolchain lock.
- Native smoke wheel.

### v0.1.0-alpha — Technical proof

- Smoke package.
- Satu native package pihak ketiga.
- Installer transaksional.
- ARMv7 device report.

### v0.2.0 — Scientific preview

- Pillow.
- NumPy.
- Matplotlib jika memungkinkan.

### v0.x — Ecosystem expansion

- Pandas.
- More native packages.
- ARM64 verification.
- Better resolver.

### v1.0.0 — Stable infrastructure

- Stable contract.
- Multi-device verification.
- Security provenance.
- Recovery dan revocation.

---

# 17. Definition of Done

## ZABAWHEELS v0.1 dianggap berhasil jika

```text
✓ Repository public dan transparan
✓ Runtime Zabacode teridentifikasi
✓ Toolchain dipin
✓ Native smoke wheel ARMv7 berhasil dibangun
✓ Wheel berhasil di-install
✓ Extension berhasil di-import pada Infinix
✓ Fungsi native menghasilkan hasil yang benar
✓ Package bertahan setelah app restart
✓ Uninstall bekerja
✓ SHA-256 diverifikasi
✓ Satu package native pihak ketiga bekerja
✓ Semua status berasal dari test nyata
✓ Tidak ada mock atau output palsu
```

## Definition of Done per stable package

```text
✓ Source URL dan source SHA-256 tercatat
✓ License tercatat
✓ Recipe dan patch tersedia
✓ Build log tersedia
✓ Wheel SHA-256 tersedia
✓ ELF architecture benar
✓ Dynamic dependencies valid
✓ Metadata valid
✓ Install berhasil
✓ Import berhasil
✓ Smoke test berhasil
✓ Interpreter restart berhasil
✓ App restart berhasil
✓ Uninstall berhasil
✓ Device report tersedia
✓ Runtime ID dan ABI eksplisit
```

---

# 18. Kesimpulan

Target pertama ZABAWHEELS bukan:

> "Kita sudah mempunyai NumPy."

Target pertama yang benar adalah:

> "Kita sudah membuktikan bahwa native wheel ARMv7 yang dibangun oleh CI dapat dipasang, diverifikasi, di-import, dijalankan, dihapus, dan dipulihkan secara aman oleh Zabacode pada perangkat Android nyata."

Jika native smoke wheel lulus seluruh Gate M2 pada Infinix Smart 9 HD, fondasi teknis repository wheel ARMv7 sudah terbukti. Setelah itu, penambahan package menjadi proses engineering bertahap, bukan lagi eksperimen apakah konsepnya mungkin.

Jika M2 membuktikan bahwa runtime native installation tidak mungkin atau terlalu rapuh, proyek tetap berguna. ZABAWHEELS dapat beralih menjadi:

- Repository pure-Python package terverifikasi.
- Native build-pack untuk APK.
- Recipe dan compatibility database.
- Optional APK flavor dengan scientific packages prebundled.

Apa pun hasilnya, sistem harus tetap transparan dan tidak mengulangi kesalahan implementasi ZMUX lama yang menggunakan mock, shim gimmick, atau output palsu.

---

# 19. Referensi Teknis

- Python-for-Android — Recipes:  
  https://python-for-android.readthedocs.io/en/latest/recipes.html

- Python-for-Android — Documentation:  
  https://python-for-android.readthedocs.io/

- PEP 738 — Adding Android as a supported platform:  
  https://peps.python.org/pep-0738/

- Python Packaging User Guide — Platform compatibility tags:  
  https://packaging.python.org/en/latest/specifications/platform-compatibility-tags/

- cibuildwheel — Android platform documentation:  
  https://cibuildwheel.pypa.io/en/latest/platforms/

- Android NDK — ABI documentation:  
  https://developer.android.com/ndk/guides/abis

- Android 10 behavior changes — executable files and W^X:  
  https://developer.android.com/about/versions/10/behavior-changes-10

---

**Dokumen ini menjadi roadmap utama ZABAWHEELS sampai repository baru dibuat dan setiap placeholder runtime diganti dengan hasil fingerprint APK yang nyata.**
