[app]

title = ZMUX
package.name = zmux
package.domain = com.zaba
source.dir = .
source.include_exts = py,png,jpg,html,css,json,js
version = 1.0.0

# Icon
icon.filename = %(source.dir)s/assets/logo.png

# Presplash
presplash.filename = %(source.dir)s/assets/presplash.png
presplash_color = #0d1117

# WebView shell for terminal UI
p4a.bootstrap = webview
p4a.port = 5000

# Core requirements - minimal for terminal
requirements = python3,flask,waitress,packaging,certifi

orientation = portrait
fullscreen = 0

# Android specific
android.archs = armeabi-v7a, arm64-v8a
android.accept_sdk_license = True
android.api = 34
android.minapi = 26
android.ndk_api = 26
android.permissions = INTERNET
android.allow_backup = False
android.orientation = portrait

# Adaptive Icon
android.adaptive_icon_background = #0d1117
android.adaptive_icon_foreground = %(source.dir)s/assets/logo.png

# Presplash color
android.presplash_color = #0d1117
android.presplash = %(source.dir)s/assets/presplash.png

[buildozer]
log_level = 2
warn_on_root = 1

# Reproducible ZMUX runtime contract
p4a.commit = 5c192d7b7308487c2d3e3fcae63deba3131e7cb2
android.ndk = 28c
