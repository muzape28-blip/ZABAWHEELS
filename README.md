# ZABAWHEELS

> **Curated Android wheelhouse for Zabacode**  
> **Status:** Experimental / Pre-Alpha  
> **Target:** Zabacode runtime on Android ARMv7 and ARM64

---

## Apa itu ZABAWHEELS?

ZABAWHEELS adalah repository recipe, build pipeline, manifest, dan artifact wheel Android terkurasi untuk [Zabacode](https://github.com/muzape28-blip/ZABACODE). Package pure Python umumnya dapat dipasang langsung, tetapi package dengan native extension (NumPy, Pillow, Pandas, dll.) harus dikompilasi khusus untuk Android.

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

## ⚠️ Peringatan Experimental

Proyek ini berada pada tahap **pre-alpha**. Semua artifact, API, dan status dapat berubah tanpa pemberitahuan. Jangan menggunakannya pada environment produksi.

- Runtime ID belum dipin (menunggu fingerprint APK nyata).
- Tidak ada package native yang sudah stabil.
- Build pipeline masih dalam pengembangan.

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
| M0 | Membentuk Repository | 🟡 In Progress |
| M1 | Runtime Fingerprint & Toolchain Freeze | ⬜ Planned |
| M2 | Native Feasibility Spike | ⬜ Planned |
| M3 | Build Factory di GitHub Actions | ⬜ Planned |
| M4 | Package Manifest & Index | ⬜ Planned |
| M5 | ZabaPip v2 | ⬜ Planned |
| M6 | Package Native Pihak Ketiga Pertama | ⬜ Planned |
| M7–M12 | Package Ladder → Stable v1 | ⬜ Planned |

## Perangkat Verifikasi

| Perangkat | ABI | Android | Peran |
|---|---|---|---|
| Infinix Smart 9 HD | armeabi-v7a | 14 Go | Device verification utama |

## Kontribusi

Lihat [CONTRIBUTING.md](CONTRIBUTING.md) untuk panduan kontribusi.

## License

Source code, script, recipe, dan dokumentasi ZABAWHEELS dilisensikan di bawah [GNU AGPL-3.0](LICENSE).  
Wheel hasil build mengikuti license package upstream masing-masing.
