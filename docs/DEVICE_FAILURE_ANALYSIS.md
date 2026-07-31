# Analisis Kegagalan On-Device ZMUX (2026-07-31)

> **Konteks:** Laporan pengujian perangkat nyata pertama (Infinix Smart 9 HD,
> ARMv7 / `lib/arm` — `armeabi-v7a`). Semua pengujian sebelumnya berjalan di
> x86_64 Linux (lihat peringatan di `docs/POST_FIX_REPORT.md`), jadi tiga
> kegagalan berikut adalah data on-device pertama yang menyentuh path proot,
> storage, dan zpip.
>
> Metode: deep research ke sumber primer (AOSP bionic linker, NDK docs,
> python-for-android pinned commit, pyjnius 1.7.0, termux-packages, komunitas
> yang meng-embed proot di APK) sebelum menulis fix. Setiap klaim punya
> referensi.

---

## Ringkasan

| # | Perintah | Error | Akar masalah |
|---|----------|-------|--------------|
| 1 | `linux apk add git openssh-client` | `CANNOT LINK EXECUTABLE ".../lib/arm/libproot.so": library "libtalloc.so.2" not found` | Nama file talloc di APK (`libtalloc.so`) ≠ nama yang diminta linker (`libtalloc.so.2`, SONAME talloc) |
| 2 | `zmux-setup-storage` | `ClassNotFoundException: org.kivy.android.PythonActivity` di `DexPathList[[directory "."]]` | `autoclass()` pyjnius dipanggil dari worker thread → JNI `FindClass` jatuh ke system class loader |
| 3 | `zpip install nano` sukses, `nano` gagal | `nano` bukan executable; nama jatuh ke Python → error | PyPI `nano` adalah library Django, BUKAN editor GNU nano; dan GNU nano butuh TTY yang ZMUX tidak punya |

---

## 1. `linux apk add` → `libtalloc.so.2 not found`

### Gejala

```
- CANNOT LINK EXECUTABLE "/data/app/~~...==/com.zaba.zmux-...==/lib/arm/libproot.so":
  library "libtalloc.so.2" not found: needed by main executable
```

### Riset & akar masalah

1. **`libproot.so` punya `DT_NEEDED = "libtalloc.so.2"`.** PRoot di-link ke
   talloc (allocator-nya), dan build talloc Samba (`wscript` talloc 2.4.2)
   menghasilkan SONAME `libtalloc.so.2` — terlihat eksplisit: library compat
   ditulis `soname='libtalloc.so.1'`, berarti library utama adalah major-2
   ([sumber wscript](https://github.com/deepin-community/talloc/blob/2.4.2-1deepin1/wscript)).

2. **Linker Android mencocokkan `DT_NEEDED` dengan nama file PERSIS.** Bionic
   mencari file bernama `libtalloc.so.2` di `LD_LIBRARY_PATH` + direktori
   sistem; fallback `name + ".so"` hanya berlaku kalau namanya *sudah*
   berakhiran `.so`, jadi `libtalloc.so.2` tidak pernah dicocokkan dengan
   `libtalloc.so` ([NDK docs](https://android.googlesource.com/platform/bionic/+/master/android-changes-for-ndk-developers.md):
   "A DT_NEEDED entry should be the same as the needed library's SONAME").

3. **Yang dikemas di APK adalah `libtalloc.so`, bukan `libtalloc.so.2`.**
   `scripts/build_proot_android.py` menyalin `sysroot/lib/libtalloc.so` (symlink
   dev di host) ke `out/libtalloc.so` via `shutil.copy2` — isi file-nya benar,
   tapi **namanya** tidak sesuai SONAME. Ditambah lagi, Android Gradle
   jniLibs tidak andal menyimpan file yang namanya tidak berakhiran `.so`
   (kasus komunitas: [r/termux — "how to include libtalloc.so.2 in jnilibs"](https://www.reddit.com/r/termux/comments/1kjuxcw/how_to_include_libtallocso2_in_jnilibs_of_my_app/)).

4. **Bukan masalah `LD_LIBRARY_PATH`.** `python_shell._exec_linux()` sudah
   menggabungkan `linuxenv.proot_env()` yang men-set
   `LD_LIBRARY_PATH=nativeLibraryDir` (lewat fallback `/proc/self/maps`, karena
   pyjnius di worker thread gagal — lihat bagian 2). Error tetap muncul karena
   file dengan nama `libtalloc.so.2` memang tidak ada di direktori itu.
   Kasus identik yang tidak terselesaikan: [restic-android #202](https://github.com/lhns/restic-android/issues/202)
   (`libdata_proot.so` + `libtalloc.so.2`).

### Fix yang diterapkan

- **`scripts/build_proot_android.py`** — dua hal baru:
  1. `patch_talloc_names()`: menulis ulang string `libtalloc.so.2` →
     `libtalloc.so\0` **di dalam ELF** (`libproot.so` NEEDED + `libtalloc.so`
     SONAME). Panjang byte sama, semua offset ELF tetap valid — trik yang
     dipakai komunitas (sed patch) untuk meng-embed proot di APK.
  2. `verify_needed()`: setelah build, `llvm-readelf -d` membuktikan semua
     `DT_NEEDED` terpenuhi oleh file yang dikemas (+ library sistem Android).
     Kalau talloc suatu saat naik ke `libtalloc.so.3`, **build gagal lebih
     dulu** di CI, bukan di HP pengguna.
- **`app/zmux/linuxenv.py`** — self-heal runtime `_ensure_talloc_compat()`:
  kalau `libtalloc.so` ada di `nativeLibraryDir` tapi `libtalloc.so.2` tidak
  (APK lama), salin ke direktori runtime yang bisa ditulis dan tambahkan ke
  depan `LD_LIBRARY_PATH`. Ini menyembuhkan APK lama tanpa rebuild, dan jadi
  sabuk-pengaman kalau packaging jniLibs menjatuhkan file versi-SONAME.

---

## 2. `zmux-setup-storage` → `ClassNotFoundException: org.kivy.android.PythonActivity`

### Gejala

```
[session error] JVM exception occurred: java.lang.ClassNotFoundException:
Didn't find class "org.kivy.android.PythonActivity" on path:
DexPathList[[directory "."],nativeLibraryDirectories=[/system/lib, ...]]
```

### Riset & akar masalah

1. **`DexPathList[[directory "."]]` = system class loader, bukan class loader
   aplikasi.** Kelas `org.kivy.android.PythonActivity` ADA di APK (app-nya
   jalan — webview bootstrap memakai kelas itu sebagai activity utama;
   [PythonActivity.java webview bootstrap](https://github.com/kivy/python-for-android/blob/5c192d7b7308487c2d3e3fcae63deba3131e7cb2/pythonforandroid/bootstraps/webview/build/src/main/java/org/kivy/android/PythonActivity.java)).
   Yang gagal adalah *penemuan* kelas itu dari thread tertentu.

2. **JNI `FindClass` di thread tanpa Java frame aplikasi memakai system class
   loader.** Kutipan langsung [Android perf-jni FAQ](https://developer.android.com/training/articles/perf-jni#faq_FindClass)
   (juga dikutip di [p4a issue #2533](https://github.com/kivy/python-for-android/issues/2533)):

   > "If you call FindClass from this thread, the JavaVM will start in the
   > 'system' class loader instead of the one associated with your application,
   > so attempts to find app-specific classes will fail."

   ZMUX menjalankan semua perintah di **worker thread**
   (`pty_session._exec_loop` — thread Python = pthread yang di-attach ke JVM
   tanpa Java frame aplikasi). `storage.request_permissions()` memanggil
   modul p4a `android.permissions`, yang melakukan
   `autoclass('org.kivy.android.PythonActivity')` langsung dari thread itu
   ([permissions.py p4a pinned](https://github.com/kivy/python-for-android/blob/5c192d7b7308487c2d3e3fcae63deba3131e7cb2/pythonforandroid/recipes/android/src/android/permissions.py))
   → ClassNotFoundException. Error yang sama persis dilaporkan untuk
   webview bootstrap di p4a #2533 dan [Stack Overflow](https://stackoverflow.com/questions/79215732/).

3. **Kenapa `linux-setup` tidak ikut gagal?** `linuxenv.native_library_dir()`
   membungkus `autoclass` dengan `try/except` dan jatuh ke pemindaian
   `/proc/self/maps` — jadi kegagalan Java-nya tertelan diam-diam.

4. **Mengapa "resolve lebih awal" menyembuhkan:** pyjnius menyimpan kelas yang
   sudah di-resolve di registry `MetaJavaClass` ([reflect.py pyjnius 1.7.0](https://github.com/kivy/pyjnius/blob/1.7.0/jnius/reflect.py)) —
   `autoclass()` berikutnya mengembalikan wrapper yang di-cache tanpa
   menyentuh `FindClass`. Webview bootstrap menjalankan Python di
   `PythonThread`; di thread utama itu ada Java frame aplikasi
   (`PythonMain.run`), jadi `FindClass` berhasil di sana.

### Fix yang diterapkan

- **`app/zmux/javabridge.py` (baru)** — `prime()` dipanggil sekali di
  `app/main.py` (thread utama Python, sebelum server/thread lain hidup),
  me-resolve `org.kivy.android.PythonActivity` dan meng-cache-nya. Akses
  berikutnya dari thread mana pun aman.
- **`app/zmux/storage.py`** — tidak lagi memakai modul p4a
  `android.permissions` (yang punya `autoclass` di import-time dan proxy
  `PythonJavaClass` — dua-duanya butuh `FindClass`). Sekarang memanggil
  `mActivity.requestPermissions([...])` langsung lewat bridge yang sudah
  di-prime; kalau bridge tidak tersedia, pesan error yang jujur (bukan
  traceback JVM).
- **`app/zmux/linuxenv.py`** — `native_library_dir()` mencoba bridge yang
  di-prime lebih dulu, baru pyjnius, baru `/proc/self/maps`.

---

## 3. `zpip install nano` sukses, `nano` gagal

### Riset & akar masalah

1. **`nano` di PyPI bukan editor.** Metadata PyPI
   ([pypi.org/pypi/nano/json](https://pypi.org/pypi/nano/json)):
   `"summary": "Does less! Loosely coupled mini-apps for django"` —
   library Django, tanpa console-script bernama `nano`. zpip dengan benar
   meng-install-nya (wheel universal lolos smoke test), tapi tidak ada
   executable `nano` yang muncul di PATH.
2. **Jadi `nano` jatuh ke Python.** `_is_external_command("nano")` → tidak
   ditemukan → dievaluasi sebagai Python → error membingungkan
   (`NameError`/`command not found`).
3. **Bahkan GNU nano yang asli tidak bisa jalan.** ZMUX adalah virtual
   terminal tanpa PTY (`/dev/ptmx`, `openpty` tidak dipakai) — sudah
   didokumentasikan di README: vim/htop/nano/less butuh TTY sejati. Jadi
   tidak ada "fix" yang membuat nano interaktif jalan; yang benar adalah
   edukasi + petunjuk pengganti.

### Fix yang diterapkan

- **`app/zmux/zpip.py`** — `PYPI_TOOL_COLLISIONS` + `_tool_collision_warning()`:
  `zpip install nano` tetap sukses (paketnya nyata) tapi mencetak WARNING
  jelas: "PyPI's 'nano' adalah library Django, BUKAN editor GNU nano".
- **`app/zmux/python_shell.py` + `pty_session.py`** — daftar
  `KNOWN_TUI_COMMANDS` (nano, vim, vi, emacs, htop, top, less, more, micro,
  joe, mcedit, ranger, screen, tmux): kalau nama itu diketik dan tidak ada
  executable-nya, terminal menjawab jujur "butuh TTY sungguhan, ZMUX tidak
  punya PTY" + alternatif (Python `open(...).write(...)`, `cat > file`)
  — bukan `NameError` yang membingungkan.

---

## File yang diubah

| File | Perubahan |
|------|-----------|
| `scripts/build_proot_android.py` | Patch NEEDED/SONAME talloc + verifikasi `DT_NEEDED` (build gagal lebih dulu kalau ada drift) |
| `app/zmux/javabridge.py` | Baru — bridge Java yang di-prime di main thread, aman dipakai thread mana pun |
| `app/main.py` | `javabridge.prime()` saat startup |
| `app/zmux/linuxenv.py` | Pakai bridge dulu; self-heal `libtalloc.so.2` untuk APK lama |
| `app/zmux/storage.py` | Request permission via `mActivity` langsung, tanpa modul p4a yang rawan `FindClass` |
| `app/zmux/python_shell.py`, `pty_session.py` | Hint jujur untuk TUI tanpa PTY |
| `app/zmux/zpip.py` | WARNING kolisi nama PyPI (nano) |
| `app/tests/*` | +30 test baru (javabridge, self-heal talloc, storage bridge, TUI hint, warning zpip) |

Status test: **348 passed, 23 skipped** (skip = integrasi proot/rootfs yang
butuh harness khusus).

---

## Yang perlu dilakukan user (setelah APK baru)

1. Install ulang APK hasil build baru (build-zmux-apk workflow otomatis
   menjalankan `patch_talloc_names` + `verify_needed`).
2. Verifikasi:
   ```bash
   gates                    # G2 proot-exec harus PASS sekarang
   linux apk add git openssh-client
   zmux-setup-storage       # tidak boleh ClassNotFoundException lagi
   ```
3. Untuk nano: jangan `zpip install nano` (itu library Django) —
   gunakan Python untuk edit file, atau `cat > file`. TUI tidak akan pernah
   interaktif di ZMUX (tanpa PTY).

## Catatan verifikasi yang belum selesai

- Self-heal `libtalloc.so.2` (jalur APK lama) baru teruji unit-level di
  desktop; butuh konfirmasi di perangkat.
- `gates` G1 (ptmx) belum lolos → PTY engine masih di luar scope.
- Permission dialog di Android 10+ adalah no-op (manifest hanya deklarasi
  `maxSdkVersion=28`); `~/storage/app` (app-external) tetap bisa di-link
  tanpa permission.
