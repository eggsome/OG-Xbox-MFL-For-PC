// cluster-entries: joypad_device_setup
/* Installed cluster joypad_device_setup (tools/cluster_install.py from output/cluster_pilot_h3/joypad_device_setup.c); entries are patched at their original addresses by build_overlay.py --clusters. */
#include "mfl_tier2.h"
#include "mfl_fix.h"
/*004c6600*/ extern void bitset_clear_first_n(void *p0, int p1);      /* bzero-like: (buffer, byte count) */
/*005dd330*/ extern float float_1_0;
/*005e64a4*/ extern float k_f_0;
/*005de1ac*/ extern float k_f_0_125;
/*005e12e0*/ extern float k_f_0_13333334;
/*00770f60*/ extern float g_app_770f60;
extern double fabs(double);
extern double sqrt(double);
/* joypad_device_setup */
/* compile: /GS */

/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */
/* "DirectInput joypad: creates the device, sets data format, axis ranges and dead zones (1.5 KB)"
    */

typedef struct { float x, y; } V2;
typedef int (__stdcall *DiDeviceCall1)(int *self);
typedef int (__stdcall *DiDeviceGetState)(int *self, int size, void *state);

/* DirectInput DIJOYSTATE (0x50 bytes) as the device returns it */
struct JoyState {
  int lX;
  int lY;
  int lZ;
  int lRx;
  int lRy;
  int lRz;
  int slider[2];
  uint pov[4];
  char buttons[32];
};

#define JOYPAD_SLOT_STRIDE 0x112      /* size of one joypad slot in g_dinput_76ed20, in undefined4 units */
#define TRIGGER_DEAD_ZONE 30          /* as the Xbox version's pad read: a trigger amount of 30 or less (of 255) is 0, a larger one is taken as it is */
#define DIPROP_GUIDANDPATH ((const void *)12)
/*0076ed20*/ extern undefined4 g_dinput_76ed20;
extern __declspec(dllimport) void *__stdcall LoadLibraryA(const char *name);
extern __declspec(dllimport) void *__stdcall GetProcAddress(void *module, const char *name);
typedef int (__stdcall *DiDeviceGetProperty)(int *self, const void *property, void *header);
typedef unsigned int (__stdcall *XInputGetStateFn)(unsigned int user, void *state);
unsigned char mfl_pad_triggers[4][2];

/* DirectInput DIPROPGUIDANDPATH (0x228 bytes): the device's interface path */
struct GuidAndPath {
  unsigned int size;
  unsigned int header_size;
  unsigned int object;
  unsigned int how;
  unsigned char guid_class[16];
  unsigned short path[260];
};

/* XInput XINPUT_STATE (0x10 bytes) */
struct XInputState {
  unsigned int packet;
  unsigned short buttons;
  unsigned char left_trigger;
  unsigned char right_trigger;
  short sticks[4];
};

/* 1 when the DirectInput device is an XInput pad: its interface path has "IG_" in it (the test Microsoft documents) */
static int pad_is_xinput(int *dev)
{
  struct GuidAndPath prop;
  int i;

  prop.size = sizeof(prop);
  prop.header_size = 16;
  prop.object = 0;
  prop.how = 0;      /* DIPH_DEVICE */
  if (((DiDeviceGetProperty)*(int *)(*dev + 0x14))(dev, DIPROP_GUIDANDPATH, &prop) < 0) {      /* GetProperty */
    return 0;
  }
  for (i = 0; i < 257 && prop.path[i] != 0; i++) {
    if ((prop.path[i] | 0x20) == 'i' && (prop.path[i + 1] | 0x20) == 'g' && prop.path[i + 2] == '_') {
      return 1;
    }
  }
  return 0;
}

/* DirectInput shows the two triggers of an XInput pad as one axis, so they are read through XInput (xinput9_1_0.dll, loaded on the first poll;
   without it nothing changes).  Stores the amounts 0..255 of pad's accelerate (right trigger) and brake (left trigger), as the Xbox version
   takes them.  The n-th DirectInput pad that is an XInput pad is taken to be XInput user n: the two lists have no common key. */
static void pad_triggers_read(undefined4 *pad)
{
  static XInputGetStateFn get_state;
  static int dll_tried;
  static signed char xinput_user[4];      /* per pad: 0 = not looked at yet, -1 = not an XInput pad, else its XInput user + 1 */
  struct XInputState state;
  void *dll;
  int index;
  int user;
  int i;

  index = (int)(pad - &g_dinput_76ed20) / JOYPAD_SLOT_STRIDE;
  if (index >= 4) return;      /* the per-pad tables hold 4 pads (MFL_FIX_PAD_LIMIT) */
  if (!dll_tried) {
    dll_tried = 1;
    dll = LoadLibraryA("xinput9_1_0.dll");
    if (dll != 0) get_state = (XInputGetStateFn)GetProcAddress(dll, "XInputGetState");
  }
  if (get_state == 0) return;
  if (xinput_user[index] == 0) {
    user = -1;
    if (pad_is_xinput((int *)*pad)) {
      user = 1;
      for (i = 0; i < index; i++) {
        if (xinput_user[i] > 0) user++;
      }
    }
    xinput_user[index] = (signed char)user;
  }
  if (xinput_user[index] < 0) return;
  if (get_state((unsigned int)(xinput_user[index] - 1), &state) != 0) {      /* not connected */
    state.left_trigger = 0;
    state.right_trigger = 0;
  }
  mfl_pad_triggers[index][0] = (unsigned char)(state.right_trigger > TRIGGER_DEAD_ZONE ? state.right_trigger : 0);
  mfl_pad_triggers[index][1] = (unsigned char)(state.left_trigger > TRIGGER_DEAD_ZONE ? state.left_trigger : 0);
}

void joypad_device_setup_n(undefined4 *pad)

{
  struct JoyState js;
  V2 v;
  float *pf;
  float *px;
  float *py;
  float stick_x;
  float stick_y;
  float dead_zone_or_len2;
  int *dev;
  int hr;
  int loop_count;
  undefined4 *hist_a;
  undefined4 *hist_b;
  float *hist_f;
  int i;
  undefined4 stick_x_bits;

  pf = (float *)pad;
  /* pad: joypad device object (esi); +0x0 IDirectInputDevice, floats [0xb2],[0xb3] = stick x/y, history ring of earlier samples is shifted down each poll, final stick is the 8-sample average (* 0.125) */
  dev = (int *)*pad;
  hr = ((DiDeviceCall1)*(int *)(*dev + 100))(dev);      /* Poll */
  if (hr < 0) {
    hr = ((DiDeviceCall1)*(int *)(*dev + 0x1c))(dev);      /* Acquire */
    while (hr == -0x7ff8ffe2) {
      hr = ((DiDeviceCall1)*(int *)(*dev + 0x1c))(dev);
    }
  }
  hr = ((DiDeviceGetState)*(int *)(*dev + 0x24))(dev, 0x50, &js);      /* GetDeviceState */
  if (hr < 0) {
    return;
  }
  hist_a = pad + 0xd0;
  hist_b = pad + 0x111;
  loop_count = 0xf;
  do {
    *hist_b = hist_b[-1];
    hist_b[-0x10] = hist_b[-0x11];
    *hist_a = hist_a[-2];
    hist_a[1] = hist_a[-1];
    hist_a[0x20] = hist_a[0x1e];
    hist_a[0x21] = hist_a[0x1f];
    hist_b = hist_b + -1;
    hist_a = hist_a + -2;
    loop_count = loop_count + -1;
  } while (loop_count != 0);
  pad[0xf2] = 0;
  pad[0xb3] = 0;
  pad[0xb2] = 0;
  pad[0xd3] = 0;
  pad[0xd2] = 0;
  bitset_clear_first_n(pad + 0x102,0x20);
  for (i = 0; i < 16; i++) {
    if (js.buttons[i] < 0) {
      ((byte *)pad)[0x408 + (i >> 3)] |= (byte)(1 << (i & 7));
    }
  }
  pad_triggers_read(pad);
  pf[0xb2] = (float)(js.lX >> 12) * k_f_0_13333334 - float_1_0;
  pf[0xb3] = float_1_0 - (float)(js.lY >> 12) * k_f_0_13333334;
  if ((short)js.pov[0] != -1) {
    switch (js.pov[0]) {
    case 0:
      pad[0xb2] = 0;
      pad[0xb3] = 0x3f800000;
      break;
    case 4500:
      pad[0xb2] = 0x3f800000;
      pad[0xb3] = 0x3f800000;
      break;
    case 9000:
      pad[0xb2] = 0x3f800000;
      pad[0xb3] = 0;
      break;
    case 13500:
      pad[0xb2] = 0x3f800000;
      pad[0xb3] = 0xbf800000;
      break;
    case 18000:
      pad[0xb2] = 0;
      pad[0xb3] = 0xbf800000;
      break;
    case 22500:
      pad[0xb2] = 0xbf800000;
      pad[0xb3] = 0xbf800000;
      break;
    case 27000:
      pad[0xb2] = 0xbf800000;
      pad[0xb3] = 0;
      break;
    case 31500:
      pad[0xb2] = 0xbf800000;
      pad[0xb3] = 0x3f800000;
      break;
    }
  }
  dead_zone_or_len2 = g_app_770f60;
  stick_x = (fabs(pf[0xb2]) < dead_zone_or_len2) ? k_f_0 : pf[0xb2];
  pf[0xb2] = stick_x;
  stick_y = (fabs(pf[0xb3]) < dead_zone_or_len2) ? k_f_0 : pf[0xb3];
  pf[0xb3] = stick_y;
  v = *(V2 *)&pf[0xb2];
  dead_zone_or_len2 = v.x * v.x + v.y * v.y;
  if (dead_zone_or_len2 > float_1_0) {
    dead_zone_or_len2 = float_1_0 / sqrt(dead_zone_or_len2);
    pf[0xb2] = stick_x * dead_zone_or_len2;
    pf[0xb3] = stick_y * dead_zone_or_len2;
  }
  hr = 7;
  hist_f = (float *)(pad + 0xa0);
  do {
    *hist_f = hist_f[-2];
    hist_f[1] = hist_f[-1];
    hist_f[0x10] = hist_f[0xe];
    hist_f[0x11] = hist_f[0xf];
    hist_f = hist_f + -2;
    hr = hr + -1;
  } while (hr != 0);
  stick_x_bits = pad[0xb2];
  pad[0x93] = pad[0xb3];
  pad[0x92] = stick_x_bits;
  pad[0xb2] = 0;
  pad[0xb3] = 0;
  pad[0xb2] = stick_x_bits;
  pad[0xb3] = pad[0x93];
  px = &pf[0xb2];
  py = &pf[0xb3];
  px[0] = pf[0x94] + px[0];
  py[0] = pf[0x95] + py[0];
  px[0] = pf[0x96] + px[0];
  py[0] = pf[0x97] + py[0];
  px[0] = pf[0x98] + px[0];
  py[0] = pf[0x99] + py[0];
  px[0] = pf[0x9a] + px[0];
  py[0] = pf[0x9b] + py[0];
  px[0] = pf[0x9c] + px[0];
  py[0] = pf[0x9d] + py[0];
  px[0] = pf[0x9e] + px[0];
  py[0] = pf[0x9f] + py[0];
  px[0] = px[0] + pf[0xa0];
  py[0] = pf[0xa1] + py[0];
  pf[0xb2] = pf[0xb2] * k_f_0_125;
  pf[0xb3] = pf[0xb3] * k_f_0_125;
  return;
}

/* entry thunk at the original address of joypad_device_setup: register inputs (esi) -> natural C joypad_device_setup_n; ret 0 */
__declspec(naked) void joypad_device_setup(void)
{
    __asm {
        push esi
        call joypad_device_setup_n
        add esp, 4
        ret
    }
}
