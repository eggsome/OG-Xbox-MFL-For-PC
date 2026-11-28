// cluster-entries: ui_rt2d_text_map_special_chars
/* Installed cluster ui_rt2d_text_map_special_chars (tools/cluster_install.py from output/cluster_pilot11/ui_rt2d_text_map_special_chars.c); entries are patched at their original addresses by build_overlay.py --clusters. */
#include "mfl_tier2.h"

/* the Xbox font's character of each control code of a text: 8 = A, 9 = B, 0xa = START, 0xb = Y, 0xc = X (as the Xbox version maps them) */
#define GLYPH_CODE_8 0x80
#define GLYPH_CODE_9 0x83
#define GLYPH_CODE_A 0x84
#define GLYPH_CODE_B 0x81
#define GLYPH_CODE_C 0x82
/* ui_rt2d_text_map_special_chars */

/* "maps the special control codes 8..0xB of a counted wide string to font glyph codes" */

void ui_rt2d_text_map_special_chars_n(ushort *text, short *out)

{
  ushort count;
  short ch;
  short *out_cursor;
  uint left;
  
  count = *text;
  if (0 < (short)count) {
    left = (uint)count;
    out_cursor = out;
    do {
      ch = *(short *)((int)text + (2 - (int)out) + (int)out_cursor);
      if (ch == 8) {
        ch = GLYPH_CODE_8;
      }
      else if (ch == 9) {
        ch = GLYPH_CODE_9;
      }
      else if (ch == 10) {
        ch = GLYPH_CODE_A;
      }
      else if (ch == 0xb) {
        ch = GLYPH_CODE_B;
      }
      else if (ch == 0xc) {
        ch = GLYPH_CODE_C;
      }
      else if (ch == 0xd) {
        ch = 0x87;
      }
      else if (ch == 0xe) {
        ch = 0x8f;
      }
      *out_cursor = ch;
      out_cursor = out_cursor + 1;
      left = left - 1;
    } while (left != 0);
    out[(short)count] = 0;
    return;
  }
  out[(short)count] = 0;
  return;
}

/* entry thunk at the original address of ui_rt2d_text_map_special_chars: register inputs (eax,ebx) -> natural C ui_rt2d_text_map_special_chars_n; ret 0 */
__declspec(naked) void ui_rt2d_text_map_special_chars(void)
{
    __asm {
        push ebx
        push eax
        call ui_rt2d_text_map_special_chars_n
        add esp, 8
        ret
    }
}
