#!/usr/bin/env python3
"""Check GMMK Pro keymap behavior (OS-toggle LED feedback, Cmd+Q delay) against the real keymap and QMK code."""

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile


CHECK = r'''
#include <assert.h>
#include <stdio.h>
#include KEYMAP_SOURCE
#include "nvm_eeconfig.h"
#include "nvm_os_detection.h"
#include "eeprom.h"

keymap_config_t keymap_config = {0};
layer_state_t layer_state;
layer_state_t default_layer_state = 1;
static unsigned resets;
static uint8_t pixels[RGB_MATRIX_LED_COUNT][3];
void advance_time(uint32_t ms);
void set_time(uint32_t ms);
static bool host_q;    // Whether the host currently sees Q held down.
static uint8_t mods;
void eeconfig_update_user(uint32_t raw) { nvm_eeconfig_update_user(raw); }
void soft_reset_keyboard(void) { ++resets; }
void register_code(uint8_t key) { if (key == KC_Q) host_q = true; }
void unregister_code(uint8_t key) { if (key == KC_Q) host_q = false; }
uint8_t get_mods(void) { return mods; }
bool layer_state_is(uint8_t layer) { return (layer_state & ((layer_state_t)1 << layer)) != 0; }
void set_single_default_layer(uint8_t layer) {
    default_layer_state = default_layer_state_set_user((layer_state_t)1 << layer);
}
void set_single_persistent_default_layer(uint8_t layer) {
    set_single_default_layer(layer);
    nvm_eeconfig_update_default_layer(default_layer_state);
}
led_t host_keyboard_led_state(void) { return (led_t){0}; }
void rgb_matrix_set_color(int led, uint8_t r, uint8_t g, uint8_t b) {
    assert(led >= 0 && led < RGB_MATRIX_LED_COUNT);
    pixels[led][0] = r; pixels[led][1] = g; pixels[led][2] = b;
}
void rgb_matrix_set_color_all(uint8_t r, uint8_t g, uint8_t b) {
    for (int led = 0; led < RGB_MATRIX_LED_COUNT; ++led) rgb_matrix_set_color(led, r, g, b);
}
static void frame(uint8_t r, uint8_t g, uint8_t b) {
    assert(!rgb_matrix_indicators_user());
    for (unsigned led = 0; led < RGB_MATRIX_LED_COUNT; ++led) {
        assert(pixels[led][0] == r && pixels[led][1] == g && pixels[led][2] == b);
    }
}
static void toggle(void) {
    keyrecord_t record = {0};
    record.event.pressed = true;
    assert(!process_record_user(QK_OS_TOG, &record));
    record.event.pressed = false;
    assert(!process_record_user(QK_OS_TOG, &record));
}
static void persisted(bool disabled) {
    assert(nvm_os_detection_read_disabled() == disabled);
}
// Like QMK core: a key the keymap does not consume is registered or unregistered on the host.
static void q(bool pressed) {
    keyrecord_t record = {0};
    record.event.pressed = pressed;
    if (process_record_user(KC_Q, &record)) {
        if (pressed) register_code(KC_Q); else unregister_code(KC_Q);
    }
}
static void other_key(void) {
    keyrecord_t record = {0};
    record.event.pressed = true;
    process_record_user(KC_W, &record);
}
static void cmd_q_checks(void) {
    set_time(1000); // The delayed press treats a zero start time as idle.
    set_single_default_layer(MAC_BASE);
    user_config.cmd_q_delay_enabled = true;
    const uint8_t cmd = MOD_BIT(KC_LCMD), ctrl = MOD_BIT(KC_LCTL);

    mods = cmd | ctrl;
    q(true);
    assert(host_q);
    mods = cmd; // Ctrl released before Q, as when locking with Ctrl+Cmd+Q.
    q(false);
    assert(!host_q);
    puts("Ctrl+Cmd+Q: releasing Ctrl before Q still releases Q on the host");

    mods = 0;
    q(true);
    mods = cmd;
    q(false);
    assert(!host_q);
    puts("Q held before Cmd: the release still reaches the host");

    mods = cmd;
    q(true);
    advance_time(CMD_Q_DELAY);
    matrix_scan_user();
    assert(!host_q);
    q(false);
    advance_time(CMD_Q_DELAY * 2);
    matrix_scan_user();
    assert(!host_q);
    puts("Cmd+Q released before the delay is never sent");

    q(true);
    advance_time(CMD_Q_DELAY + 1);
    matrix_scan_user();
    assert(host_q);
    mods = 0; // Cmd released before Q.
    q(false);
    assert(!host_q);
    puts("Cmd+Q held past the delay is sent once and released with Q");

    mods = cmd;
    q(true);
    other_key();
    advance_time(CMD_Q_DELAY * 2);
    matrix_scan_user();
    assert(!host_q);
    q(false);
    assert(!host_q);
    puts("Another key cancels a pending Cmd+Q");
    mods = 0;
}
int main(void) {
    timer_init(); // Feedback must work even at tick zero.
    toggle();
    persisted(true);
    frame(RGB_RED);
    advance_time(FLASHING_EFFECT_INTERVAL);
    frame(RGB_OFF);
    advance_time(EFFECTS_DURATION + 1);
    matrix_scan_user();
    assert(resets == 0);
    puts("Disable: immediate persisted OFF, red flashing, no reboot");

    keyrecord_t layer_key = {0};
    layer_key.event.pressed = true;
    assert(!process_record_user(DF_MACB, &layer_key));
    assert(default_layer_state == ((layer_state_t)1 << MAC_BASE));
    frame(RGB_WHITE);
    puts("Manual Fn+Caps layer switch retains white feedback while detection is disabled");

    toggle();
    persisted(false);
    frame(RGB_GREEN);
    assert(!process_detected_host_os_user(OS_UNSURE));
    assert(default_layer_state == ((layer_state_t)1 << MAC_BASE));
    frame(RGB_GREEN); // A pre-restart detection result must not replace the feedback.
    advance_time(EFFECTS_DURATION - 1);
    matrix_scan_user();
    assert(resets == 0);
    advance_time(1);
    matrix_scan_user();
    assert(resets == 1);
    matrix_scan_user();
    assert(resets == 1);
    puts("Enable: persisted ON, green feedback, exactly one reboot after the animation");

    toggle(); // Off again.
    toggle(); // Schedule enable.
    frame(RGB_GREEN);
    advance_time(EFFECTS_DURATION / 2);
    toggle(); // Disable before the restart deadline.
    persisted(true);
    frame(RGB_RED);
    advance_time(EFFECTS_DURATION + 1);
    matrix_scan_user();
    assert(resets == 1);
    puts("Rapid re-disable cancels the pending enable reboot");

    keyrecord_t held_key = {0};
    held_key.event.pressed = true;
    assert(!process_record_user(QK_OS_TOG, &held_key));
    persisted(false);
    frame(RGB_GREEN);
    advance_time(EFFECTS_DURATION + 1);
    matrix_scan_user();
    assert(resets == 1); // Do not reboot while the toggle key is physically held.
    held_key.event.pressed = false;
    assert(!process_record_user(QK_OS_TOG, &held_key));
    matrix_scan_user();
    assert(resets == 2);
    persisted(false);
    puts("Enable waits for key release even after its animation has finished");
    toggle(); // OFF again before the rollover case.

    set_time(UINT32_MAX - 10);
    toggle();
    frame(RGB_GREEN);
    advance_time(EFFECTS_DURATION - 1);
    matrix_scan_user();
    assert(resets == 2);
    advance_time(1);
    matrix_scan_user();
    assert(resets == 3);
    persisted(false);
    puts("Reboot timing remains correct across timer rollover");

    cmd_q_checks();
}
'''


def main():
    userspace = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware', type=Path, default=userspace.parent / 'qmk_firmware')
    args = parser.parse_args()
    firmware = args.firmware.resolve()
    keymap = userspace / 'keyboards/gmmk/pro/rev1/ansi/keymaps/andrebrait'
    board = json.loads((firmware / 'keyboards/gmmk/pro/rev1/ansi/keyboard.json').read_text())
    includes = ['platforms/test', 'platforms', 'tmk_core', 'tmk_core/protocol', 'quantum',
                'quantum/keymap_extras', 'quantum/process_keycode', 'quantum/send_string',
                'quantum/sequencer', 'quantum/logging', 'quantum/nvm', 'quantum/nvm/eeprom',
                'quantum/rgb_matrix', 'quantum/rgb_matrix/animations', 'lib/printf/src/printf',
                'drivers', 'drivers/battery']
    sources = ['quantum/os_detection.c', 'quantum/nvm/eeprom/nvm_eeconfig.c',
               'quantum/nvm/eeprom/nvm_os_detection.c', 'quantum/bitwise.c', 'platforms/timer.c',
               'platforms/test/timer.c', 'platforms/test/eeprom.c']
    with tempfile.TemporaryDirectory(prefix='qmk-led-feedback-') as temporary:
        temporary = Path(temporary)
        header = temporary / 'keyboard.h'
        subprocess.run(['qmk', 'generate-keyboard-h', '-kb', 'gmmk/pro/rev1/ansi', '-o', str(header)],
                       cwd=firmware, env=dict(os.environ, QMK_HOME=str(firmware)), check=True)
        source = temporary / 'check.c'
        source.write_text(CHECK)
        binary = temporary / 'check'
        flags = ['-std=gnu11', '-O2', '-ffunction-sections', '-fdata-sections', '-fshort-enums',
                 '-DNO_PRINT', '-DOS_DETECTION_ENABLE', '-DRGB_MATRIX_ENABLE', '-DNKRO_ENABLE',
                 '-DEEPROM_CUSTOM', '-DEEPROM_SIZE=1024',
                 f'-DMATRIX_ROWS={len(board["matrix_pins"]["rows"])}',
                 f'-DMATRIX_COLS={len(board["matrix_pins"]["cols"])}',
                 f'-DRGB_MATRIX_LED_COUNT={len(board["rgb_matrix"]["layout"])}',
                 f'-DQMK_KEYBOARD_H="{header}"', f'-DKEYMAP_SOURCE="{keymap / "keymap.c"}"',
                 '-include', str(keymap / 'config.h')]
        flags.extend(f'-I{firmware / path}' for path in includes)
        linker = '-Wl,-dead_strip' if sys.platform == 'darwin' else '-Wl,--gc-sections'
        command = shlex.split(os.environ.get('CC', 'cc')) + flags + [str(source)]
        command.extend(str(firmware / path) for path in sources)
        subprocess.run(command + [linker, '-o', str(binary)], cwd=firmware, check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    main()
