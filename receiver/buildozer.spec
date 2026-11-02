[app]

title = BLE Remote Receiver
package.name = bleremotereceiver
package.domain = org.bleremote

source.dir = .
source.include_exts = py,png,jpg,kv,json,ttf

version = 1.0

requirements = python3,kivy,pyjnius

orientation = portrait
fullscreen = 0

android.permissions = BLUETOOTH,BLUETOOTH_ADMIN,ACCESS_FINE_LOCATION,BLUETOOTH_SCAN,BLUETOOTH_CONNECT,BLUETOOTH_ADVERTISE

android.api = 35
android.minapi = 23
android.targetapi = 35

android.archs = arm64-v8a, armeabi-v7a

android.accept_sdk_license = True

android.allow_backup = True

[buildozer]

log_level = 2
warn_on_root = 1
