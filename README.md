# ZABAWHEELS

> **ZMUX Android Python IDE + curated Android wheelhouse**
> **Status:** APK pipeline implemented; native package verification remains experimental
> **Target:** Android ARMv7 and ARM64 (API 26+)

---

## Apa itu ZABAWHEELS?

Repository ini sekarang menghasilkan aplikasi Android **ZMUX** sekaligus menyediakan recipe, build contract, manifest, dan index wheel Android terkurasi. ZMUX memuat editor Python offline dan ZabaPip v2 transaksional. Package pure Python universal dapat dipasang setelah verifikasi SHA-256; package native hanya diterima bila runtime ID dan ABI-nya tepat.

ZABAWHEELS bukan mirror PyPI. Ini adalah **curated wheelhouse** — lebih baik menyediakan lima package yang benar-benar stabil daripada lima puluh package dengan status yang tidak jelas.

## Alur Utama

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

## Prinsip Dasar

| Prinsip | Arti |
|---|---|
| **Truth-first** | Setiap status package harus punya arti yang jelas. Build sukses ≠ working on Android. |
| **Runtime-locked** | Setiap native wheel hanya kompatibel dengan runtime contract tertentu. |
| **ARMv7-first** | ARMv7 adalah target device verification awal. ARM64 tetap dibangun via CI. |
| **CI builds, phone validates** | HP bukan mesin build. HP adalah laboratorium runtime. |
| **No silent fallback** | Jika package gagal, tampilkan penyebab sebenarnya. |

## Status Package

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

## APK ZMUX

Workflow **Build ZMUX APK** membangun APK universal ARMv7 + ARM64 dengan nama artifact `zmux`. Isinya adalah `zmux-1.0.0-universal-debug.apk`, checksum, dan build contract. Lihat [panduan build](docs/BUILDING.md).

> APK debug belum merupakan rilis produksi. Runtime/toolchain sudah dipin, tetapi package native belum boleh disebut stabil sebelum ada device report nyata. Lihat [status roadmap yang jujur](ROADMAP_STATUS.md).

## Struktur Repository

```text
ZABAWHEELS/
├── .github/           # Issue templates & CI workflows
├── toolchain/         # Runtime lock, source lock, build image
├── packages/          # Package recipes & source
├── scripts/           # Build, inspect, manifest, index scripts
├── schemas/           # JSON schema validation
├── index/             # Package index per channel
├── tests/             # Repository validation tests
└── docs/              # Documentation
```

Lihat [ZABAWHEELS.md](ZABAWHEELS.md) untuk roadmap lengkap.

## Milestone Roadmap

| Milestone | Tujuan | Status |
|---|---|---|
| M0 | Membentuk Repository | ✅ Implemented |
| M1 | Runtime Fingerprint & Toolchain Freeze | ✅ Build contract locked |
| M2 | Native Feasibility Spike | 🟡 Recipe ready; device test required |
| M3 | Build Factory di GitHub Actions | ✅ ZMUX APK pipeline |
| M4 | Package Manifest & Index | ✅ Implemented |
| M5 | ZabaPip v2 | ✅ Implemented + tested |
| M6 | Package Native Pihak Ketiga Pertama | 🟡 Blocked by honest M2 device gate |
| M7–M12 | Package Ladder → Stable v1 | 🟡 Engineering delivered; external device/release evidence pending |

## Perangkat Verifikasi

| Perangkat | ABI | Android | Peran |
|---|---|---|---|
| Infinix Smart 9 HD | armeabi-v7a | 14 Go | Device verification utama |

## Kontribusi

Lihat [CONTRIBUTING.md](CONTRIBUTING.md) untuk panduan kontribusi.

## License

Source code, script, recipe, dan dokumentasi ZABAWHEELS dilisensikan di bawah [GNU AGPL-3.0](LICENSE).  
Wheel hasil build mengikuti license package upstream masing-masing.
