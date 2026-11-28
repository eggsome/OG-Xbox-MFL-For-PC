/* mfl_debug_log.c: a running record of the inputs and the state of the game, for looking at a session afterwards
 * (new code, not an original function).  Off unless the game is started with --debug.
 *
 * One line per frame (mfl_debug_log_frame, from app_frame_wait) and one line per event (mfl_debug_log_text: rumble requests, what is
 * sent to a pad).  The lines go to mfl-debug-A.txt in the game's folder for two minutes, then to mfl-debug-B.txt for two minutes,
 * then A again (overwritten), so the last two to four minutes of any session are on disk; the file is flushed once a second.
 *
 *   F <frame> t=<ms since start> app=<app state> phase=<race phase> page=<menu page id> ev=<event type> mode=<game mode> ticks=<frame ticks>
 *   P<n> dev=<0 none 1 pad 2 keys>/<joystick> raw=<stick x>,<stick y>,<d-pad bits> in=<left right up down accelerate brake fire drop
 *        pause select back next> ax=<analog x>,<analog y> rum=<request>,<enabled>,<frames>,<pattern>,<strength>
 *   C<n> act=<active> mode=<mode> rwp=<in crash physics> pos= up= fwd= vel= (x,y,z each) spd=<speed> wic=<wheels in contact>
 *        cc=<contact count> wd=<the four wheels' contact distances> wc=<their in_contact>
 * P lines for the players with a device, C lines for the active cars.
 */
#include "mfl_tier2.h"
#include "mfl_fix.h"

#include <stdio.h>
#include <string.h>
extern __declspec(dllimport) char *__stdcall GetCommandLineA(void);
/*004a41f0*/ extern int timer_ticks(void);
/*00652f68*/ extern int g_race_phase;
/*0076e7f4*/ extern int g_app_state;
/*0069cbd0*/ extern int g_menu_current;
/*0069d2e0*/ extern struct MenuRecord g_menu_records[14];
/*0069cbd4*/ extern int g_event_type;
/*007ef7b8*/ extern int game_mode;
/*007ef7e8*/ extern int g_frame_ticks;
/*007e7740*/ extern struct ControllerCfg g_controller_cfg[4];
/*007ef820*/ extern struct PlayerInput g_player_inputs[12];
/*007f01fc*/ extern struct PlayerSlot g_player_slots[4];
/*008b06e0*/ extern struct Car player_car[16];

#define TICKS_PER_MS 3000            /* timer_ticks() runs at 3,000,000 per second */
#define FILE_MS 120000               /* two minutes per file */

static FILE *out;
static int started, start_ticks, file_start_ms, which, frame, last_flush_ms;

int mfl_debug_log_on(void)
{
  static int on = -1;

  if (on < 0) on = strstr(GetCommandLineA(), "--debug") != 0;
  return on;
}

static int now_ms(void)
{
  if (!started) { started = 1; start_ticks = timer_ticks(); }
  return (int)((unsigned int)(timer_ticks() - start_ticks) / TICKS_PER_MS);
}

static FILE *file(void)
{
  int ms = now_ms();

  if (out != 0 && ms - file_start_ms >= FILE_MS) {
    fclose(out);
    out = 0;
    which = !which;
  }
  if (out == 0) {
    out = fopen(which ? "mfl-debug-B.txt" : "mfl-debug-A.txt", "w");
    file_start_ms = ms;
    if (out != 0) fprintf(out, "# mfl debug log, file started at t=%d ms, frame %d\n", ms, frame);
  }
  return out;
}

void mfl_debug_log_text(const char *text)
{
  FILE *f;

  if (!mfl_debug_log_on()) return;
  f = file();
  if (f != 0) fprintf(f, "E %d t=%d %s\n", frame, now_ms(), text);
}

void mfl_debug_log_frame(void)
{
  FILE *f;
  int ms, p, c, page;

  if (!mfl_debug_log_on()) return;
  f = file();
  ms = now_ms();
  if (f == 0) return;
  frame++;
  page = g_menu_current >= 0 && g_menu_current < 14 ? g_menu_records[g_menu_current].page_id : -1;
  fprintf(f, "F %d t=%d app=%d phase=%d page=%d ev=%d mode=%d ticks=%d\n", frame, ms, g_app_state, g_race_phase, page, g_event_type, game_mode, g_frame_ticks);
  for (p = 0; p < 4; p++) {
    const struct PlayerInput *in = &g_player_inputs[p];
    int x = 0, y = 0, d = 0;

    if (g_controller_cfg[p].device == 0) continue;
    if (g_controller_cfg[p].device == 1 && g_controller_cfg[p].joystick < 4) {
      x = mfl_pad_raw[g_controller_cfg[p].joystick].x; y = mfl_pad_raw[g_controller_cfg[p].joystick].y; d = mfl_pad_raw[g_controller_cfg[p].joystick].dpad;
    }
    fprintf(f, "P%d dev=%d/%d raw=%d,%d,%d in=%d %d %d %d %d %d %d %d %d %d %d %d ax=%.3f,%.3f rum=%d,%d,%d,%d,%d\n", p,
            (int)g_controller_cfg[p].device, (int)g_controller_cfg[p].joystick, x, y, d,
            in->left, in->right, in->up, in->down, in->accelerate, in->brake, in->fire, in->drop, in->pause, in->menu_select, in->menu_back, in->menu_next,
            in->analog_x, in->analog_y, (int)in->rumble_request, (int)in->rumble_enabled, (int)in->rumble_duration, (int)in->rumble_motor, (int)in->rumble_strength);
  }
  for (c = 0; c < 16; c++) {
    const struct Car *car = &player_car[c];
    const float *m = car->matrices + (car->matrix_current & 1) * 16;

    if (car->active == 0) continue;
    fprintf(f, "C%d act=%d mode=%d rwp=%d pos=%.3f,%.3f,%.3f up=%.4f,%.4f,%.4f fwd=%.4f,%.4f,%.4f vel=%.3f,%.3f,%.3f spd=%.2f wic=%.0f cc=%d wd=%.3f,%.3f,%.3f,%.3f wc=%d%d%d%d\n", c,
            (int)car->active, (int)car->mode, car->rwp_object != 0, m[12], m[13], m[14], m[4], m[5], m[6], m[8], m[9], m[10],
            car->velocity[0], car->velocity[1], car->velocity[2], car->speed, car->wheels_in_contact, car->contact_count,
            car->wheels[0].contact_distance, car->wheels[1].contact_distance, car->wheels[2].contact_distance, car->wheels[3].contact_distance,
            car->wheels[0].in_contact, car->wheels[1].in_contact, car->wheels[2].in_contact, car->wheels[3].in_contact);
  }
  if (ms - last_flush_ms >= 1000) {
    fflush(f);
    last_flush_ms = ms;
  }
}
