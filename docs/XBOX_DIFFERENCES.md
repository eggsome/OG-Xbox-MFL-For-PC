# Differences between the PC and Xbox versions

What this fork found when comparing the PC game (`MFL.exe`) with the Xbox version (`default.xbe`), and what it changes. PC addresses are those of `src/symbols.txt`; Xbox addresses are virtual addresses in `default.xbe`.

| Difference | PC game | Xbox version | Changed in |
|---|---|---|---|
| Triggers | accelerate / brake are 0 or 255 from the bound buttons (`controller_action_pressed`, `0x4a6f80`) | the trigger's amount 0..255; 30 or less counts as 0 | `cl_controller_action_pressed.c`, `cl_joypad_device_setup.c` |
| Stick and D-pad | 16 steps per axis, dead zone 35 %, average of the last 8 frames (`joypad_device_setup`, `0x4a49c0`) | this frame's deflection / 128, no average; analog dead zone 0.45; D-pad moves the analog value by 0.05 per frame; a menu direction counts from half deflection (input build at `0x1108bf`) | `cl_controller_poll_player.c`, `cl_joypad_device_setup.c`, `mfl_settings_menu.c` |
| Rumble | requests are filed (`player_rumble`, `0x4a1680`; `input_player_rumble_set`, `0x4a16e0`) but never sent, and `controller_poll_player` (`0x4a5680`) clears them every frame | played once per poll by `0x1107b0`: pattern 1 = left `0x6e` + right `0xc8`; 2 = left at the strength; 3 = left at the strength + right `0xc8`; 4 = the two in turn | `mfl_rumble.c`, `cl_controller_poll_player.c` |
| Square roots | RenderWare's table versions: `_rwSqrt` (`0x4d5410`), `_rwInvSqrt` (`0x4d5470`), and `RwV3dNormalize` / `RwV3dLength` built on them; good to about 4 parts in 100,000 | the processor's `sqrtss`, exact to float precision (e.g. `0x1499c9`, in the pair of `triangle_normal`) | `mfl_exact_math.c`, `tools/delink/link_ours.sh` |
| Ground alignment | a car is turned towards the ground normal when the cosine between them is below 0.999 (2.6 degrees), in `car_wheel_contact_update` (`0x47d840`) | below 0.9999 (0.8 degrees): `fcomp` at `0x14d21b`, in the paired function at `0x14ca00` | `cl_car_wheel_contact_update.c` |
| Button pictures | control codes 8..0xc of a text map to PC font characters (`ui_rt2d_text_map_special_chars`, `0x42bd20`); a gamepad is a texture of `pc.txd` (`ui_keyboard_icon_find`, `0x430eb0`) | they map to the A, B, START, Y, X characters of the Xbox font (`0x1cea90`); a gamepad is the font's controller picture drawn as a text (`0x1b11a5`..`0x1b12bc`) | `cl_ui_rt2d_text_map_special_chars.c`, `an_hk_913.c`, `tools/xbox_font.py` |

## How the two were compared

**Static comparison** (`tools/xbox_compare/`). Both executables were disassembled and every PC function of the car physics and control call tree was paired with its Xbox function by mnemonic histogram, referenced float constants and instruction sequence. The two were built by different compilers, so the code is not byte identical. For each pair the float constants, compare immediates and the data tables they refer to were compared.

Found the same in both: frame timing (1/60 s steps, the same snapping of the frame time), steering, drivetrain, forces, wheel contact, car against car and against the track, the crash physics' gravity, and every initialised table the physics refers to. The ground alignment constant is the one that differs.

**Recorded comparison** (`--debug` on PC, `tools/xemu/` on Xbox). The same race start was recorded in both versions: on PC with the `--debug` log, on Xbox with gdb on xemu's debug port at the alignment decision (`0x14d217`). This is how the square roots were found:

| At the first alignment of a car | Xbox | PC |
|---|---|---|
| length of the car's up vector | 1.000000 | 0.999989 |
| length of the ground normal | 1.000000 | 1.000043 |
| angle the car is turned by | 1.790 degrees | 1.732 degrees |

With the PC threshold that error is far inside the margin. With the Xbox threshold it is as large as the margin and a standing car never settles: 299 corrections of one car in a recording where the Xbox version made 3. With exact square roots the PC game also reads 1.790 degrees and makes 3 corrections.

## Limits of the comparison

- The static comparison covered game functions only. Library code was left out, which is why it missed the square roots; they were found from the recordings.
- About 60 gameplay functions have no Xbox pair yet (`cand.py` lists candidates; some are inlined on Xbox).
- RenderWare's own calls of the table square roots inside the library (rendering, collision trees, the crash physics) are unchanged.
- The trigger and rumble code address a pad by its position in the device list, which need not agree between DirectInput and XInput with more than one pad attached.
