[app]
title = BLE Receiver
package.name = blereceiver
package.domain = org.bleremote
source.dir = .
source.include_exts = py,ttf,json
version = 0.1
requirements = python3,kivy==2.3.0,pyjnius,android,arabic-reshaper,python-bidi
orientation = portrait
fullscreen = 1
android.permissions = BLUETOOTH,BLUETOOTH_ADMIN,BLUETOOTH_SCAN,BLUETOOTH_CONNECT,BLUETOOTH_ADVERTISE,ACCESS_FINE_LOCATION,RECEIVE_BOOT_COMPLETED
android.api = 34
android.minapi = 21
android.archs = arm64-v8a
android.add_src = java
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
