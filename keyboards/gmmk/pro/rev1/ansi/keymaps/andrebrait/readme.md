# andrebrait's GMMK Pro layout

This is pretty much the stock layout with a few things moved around.
It basically reflects my needs for both Delete and Insert being readily available for coding, as well as a full Home/PgUp/PgDwn/End column.

The differences are as follows:

- Dedicated MacOS and Windows/Linux layers
  - Switching between them by pressing Fn + CAPS LOCK
- VIA is disabled; the keymap is compiled into firmware
- Disabled Mouse Keys (to fix issues with KVM switches and also because they're not used here anyway)
- RGB turns off after 20 minutes of inactivity
- RGB turns off when USB is suspended
- Every actionable Fn-layer key is highlighted: blue on Windows/Linux and white on macOS, including Fn + B and Fn + T
- Layer 0:
  - Delete -> Insert
  - Page Up -> Delete
  - Page Down -> Home
- Layer 1 (accessed by pressing Fn):
  - Fn + Insert -> Pause
  - Fn + Delete -> Scroll Lock
  - Fn + Esc -> Clear EEPROM
  - Fn + (Left) CMD (macOS layout) -> Toggle the CMD + Q delay
  - Fn + T -> Toggle OS detection persistently; red flashes indicate OFF, green flashes indicate ON
  - Fn + B -> Hold to temporarily bypass OS-layer changes and automatic OS-detection resets

On the Mac layer, pressing CMD + Q will not immediately send the combination.\
There's a configurable delay (defaults to 1 second) to send it.\
This is done mainly to prevent hitting CMD + Q by mistake when alternating between applications with CMD + Tab.

This keymap also includes CAPS LOCK ON indicator.\
All left and right side LEDs, and the Caps key LED will turn solid red while CAPS LOCK is ON.

## Toggling OS detection

Press Fn + T on either the Windows/Linux or macOS Fn layer to toggle OS detection. The keycode is `QK_OS_DETECTION_TOGGLE`, with the short alias `QK_OS_TOG`. Detection is enabled by default.

Disabling takes effect immediately without a reboot and flashes red using the same effect as the other toggle keys. It keeps the currently selected layer and stops OS fingerprinting, automatic OS-detection resets, and report callbacks; `detected_host_os()` returns `OS_UNSURE` while disabled. Fn + Caps Lock remains available to switch manually between Windows/Linux and macOS layers.

Enabling saves the setting and flashes green for `EFFECTS_DURATION` (two seconds by default), then restarts the keyboard once after the toggle key is released to collect a fresh USB fingerprint. Keyboard scanning continues during the animation. Holding the key past the animation postpones the restart until release, preventing it from toggling again at boot. Toggling OFF again before the restart cancels it. The disabled flag is stored in the existing EEPROM keymap configuration and survives restarts and power loss. Fn + Esc or another EEPROM reset restores detection to enabled.

Holding Fn + B pauses OS-detection decisions and cancels automatic reset requests without changing the persistent toggle. USB fingerprint collection continues in the background so a pending OS-layer decision can resume after release; canceled resets are not delayed until release. A later stable configured REPORT session and a new USB transition can arm another reset.

KVMs that keep the keyboard powered may require a real keyboard restart to force USB descriptor assembly and detect the new host. This build keeps that automatic restart: a stable configured REPORT-protocol session arms it even when no OS fingerprint is available. USB reinitialization remembers eligibility from the previous session and waits for 250 ms without USB state notifications or any descriptor request before restarting, even if the new host requests no strings. Device, configuration, HID, and report-descriptor assembly all postpone the restart rather than being mistaken for inactivity. BOOT protocol clears eligibility and cancels queued resets. Single-report mode reports the first stable result once per keyboard boot, not once per USB enumeration.

BIOS/UEFI may use the default REPORT protocol and legitimately make no string-descriptor requests, so BOOT cancellation alone is not a guarantee against boot loops. The enabled EEPROM reboot guard permits three automatic restart requests at firmware uptime strictly below 1000 ms, then blocks further automatic restarts until USB remains continuously configured for 5000 ms. A permitted request at or beyond 1000 ms clears the consecutive count, but a count already at the limit stays blocked until the stable-link interval completes. These are firmware-uptime measurements, not elapsed wall time between reboots. Slower loops require adjusting `OS_DETECTION_BOOT_LOOP_GUARD_FAST_MS` in `config.h`. Manual reboot, bootloader entry, and Fn + T re-enabling remain available.

## Production configuration

OS-detection debugging and the USB console are disabled. The diagnostic Fn + I, Fn + O, and Fn + P bindings have been removed; those positions are inactive on both Fn layers and are not highlighted.

The reboot guard remains enabled independently of debugging. Its seven-byte EEPROM record now follows the core, keyboard, and user settings directly. Moving from the debug build resets the previous guard history because its address changes; the persistent OS-detection toggle and other keyboard preferences keep their existing addresses.

The hosted LED-feedback regression can be run with `python3 tests/os_detection_led_feedback.py --firmware ../qmk_firmware`. It checks red/green frames, disabled-mode manual-layer feedback, persistence, deferred restart timing, held-key safety, cancellation, and timer rollover against this keymap and QMK.
