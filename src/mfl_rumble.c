/* mfl_rumble.c: gamepad rumble as the Xbox version plays it (new code, not an original function).
 *
 * The game asks for rumble by writing into the player's input record: rumble_request = 1, rumble_motor = a pattern 1..4,
 * rumble_duration = frames, rumble_strength = 0..255 (player_rumble, input_player_rumble_set); a record with rumble_enabled = 0 gets
 * no requests.  The Xbox version's pad code (0x1107b0 of default.xbe, called at the end of each pad's poll) plays them, once per poll:
 *     pattern 0             both motors off
 *     pattern 1             left motor 0x6e, right motor 0xc8
 *     pattern 2             left motor = strength, right motor off
 *     pattern 3             left motor = strength, right motor 0xc8
 *     pattern 4             odd frames left: right motor 0xc8 alone; even frames left: left motor = strength alone
 *   each for `duration` polls (one less per poll); at 0 the pattern becomes 0.  A motor byte b is the XInput speed b << 8.
 * The PC game has the requests but no player for them, and its poll clears the whole record; here the six rumble words are carried
 * over from the previous record as the Xbox poll does, and the pattern goes to the XInput pad with the player's joystick number.
 */
#include "mfl_tier2.h"
#include "mfl_fix.h"

/* only names the original exe imports have import libraries: LoadLibraryA comes through GetProcAddress, as in mfl_resources.c */
extern __declspec(dllimport) void *__stdcall GetModuleHandleA(const char *name);
extern __declspec(dllimport) void *__stdcall GetProcAddress(void *module, const char *name);
typedef void *(__stdcall *load_library_fn)(const char *name);

struct vibration { unsigned short left, right; };
typedef unsigned long (__stdcall *set_state_fn)(unsigned long user, struct vibration *v);
static set_state_fn set_state;
static int looked;
static struct vibration sent[4];

static void motors(unsigned int pad, unsigned int left, unsigned int right)
{
  static const char *const k_dll[] = { "xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll" };
  struct vibration v;
  int k;

  if (pad >= 4) return;
  if (!looked) {
    load_library_fn load_library = (load_library_fn)GetProcAddress(GetModuleHandleA("kernel32.dll"), "LoadLibraryA");

    looked = 1;
    for (k = 0; load_library != 0 && k < 3 && set_state == 0; k++) {
      void *dll = load_library(k_dll[k]);

      if (dll != 0) set_state = (set_state_fn)GetProcAddress(dll, "XInputSetState");
    }
  }
  v.left = (unsigned short)(left << 8);
  v.right = (unsigned short)(right << 8);
  if (set_state == 0 || (v.left == sent[pad].left && v.right == sent[pad].right)) return;      /* only changes are sent */
  sent[pad] = v;
  set_state(pad, &v);
}

void mfl_rumble_poll(struct PlayerInput *now, const struct PlayerInput *previous, int gamepad, unsigned int joystick)
{
  now->rumble_request = previous->rumble_request;      /* the poll has just cleared `now`: the rumble words live on, as on Xbox */
  now->rumble_enabled = gamepad ? 1 : previous->rumble_enabled;      /* always on for a pad: the PC game wiped this word every frame, so its save
                                                                         files hold 0 and its menus have no entry to switch it back on */
  now->rumble_duration = previous->rumble_duration;
  now->rumble_motor = previous->rumble_motor;
  now->rumble_strength = previous->rumble_strength;
  if (!gamepad) return;
  if (now->rumble_request == 0 || now->rumble_motor > 4) {
    motors(joystick, 0, 0);
    return;
  }
  if (now->rumble_motor == 0) {
    motors(joystick, 0, 0);
    return;
  }
  if ((int)now->rumble_duration <= 0) {
    now->rumble_motor = 0;
    now->rumble_duration = 0;
    return;
  }
  switch (now->rumble_motor) {
  case 1: motors(joystick, 0x6e, 0xc8); break;
  case 2: motors(joystick, now->rumble_strength & 0xff, 0); break;
  case 3: motors(joystick, now->rumble_strength & 0xff, 0xc8); break;
  default:
    if (now->rumble_duration & 1) motors(joystick, 0, 0xc8);
    else motors(joystick, now->rumble_strength & 0xff, 0);
    break;
  }
  now->rumble_duration = now->rumble_duration - 1;
}
