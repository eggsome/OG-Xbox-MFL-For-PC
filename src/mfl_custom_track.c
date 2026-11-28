/* mfl_custom_track.c: the track "Crazy Town", a 16th row of the event list (new code, not an original function).
 *
 * The game knows 28 courses (g_course_table) and lists 15 events; both tables and everything indexed by them (progress, records, best
 * times, sounds per course id) have no room for more.  So the new track is no new course to the game:
 *   - in the list it is a cursor position below the last row; g_career_row stays on that row (the "host"), a flag says the cursor is
 *     one further down.  Progress, records and the vehicle choice are the host row's.
 *   - while the flag is set, the race setup's three records of the host row (one per variant, 15 apart) are replaced by copies that
 *     name the base course (MFL_CUSTOM_TRACK_BASE), so every reader of the setup loads that course id;
 *   - course_table_select / course_table_find_entry then answer the base id with the record below: the archive name CrazyTwn (the
 *     game opens archives by their 8.3 name: at most 8 characters) and no course callbacks.  The sound bank stays the base course's: sound_load_course_audio asks for the name under
 *     mfl_custom_track_hold.
 *   - the track's own results (mfl_custom_track_save_*): one "row" of the game state (progress, records, record block, best times,
 *     enabled flags) is kept here and exchanged with the host row's while the track is selected, so the game's code reads and writes
 *     the track's values in the host row's place.  The save file gets the host's real values in the game's block (first 0x42334 bytes,
 *     unchanged format) and the track's row in a section appended after it:
 *         "MFLX", u32 version (1), u32 tracks, then per track: char name[16], u32 size, the row (struct Row)
 *     The original game reads only the first block; a file without the section gives the track its defaults.
 */
#include "mfl_tier2.h"
#include "mfl_fix.h"
#include <stdio.h>
#include <string.h>

/*0050b5e0*/ extern void nop_stub(void);
/*0069cbd4*/ extern int g_event_type;
/*0069d688*/ extern int g_career_row;
/*008d8b14*/ extern char *g_race_setup;
/*007eebc0*/ extern struct GameState g_game_state;
/*00609a58*/ extern int g_menu_609a58;      /* the vehicle choice of each list row */
/*005dd9b4*/ extern char g_gamesave_5dd9b4[];      /* the save file's name */
/*0042f860*/ extern int __cdecl texdict_load_named_b(char *p0, undefined4 p1, undefined4 p2);
/*004a43d0*/ extern undefined __cdecl game_open_piz(char *p0);
/*004a4440*/ extern int game_close_piz();
/*004d5e10*/ extern struct RwTexDictionary * RwTexDictionarySetCurrent(struct RwTexDictionary *p0);
/*00485240*/ extern RwBool RwTexDictionaryDestroy_004d5ac0(struct RwTexDictionary *p0);
/*004d5d90*/ extern void *__cdecl RwTexDictionaryFindNamedTexture(void *dictionary, const char *name);
/*0042fa80*/ extern char * course_content_path_build();
extern void game_path_to_8_3_upper(char *out, const char *path);

#define SETUP_ENTRIES 4        /* race setup: the event record pointers start here */
#define SETUP_VARIANTS 3       /* a row's records: row, row + 15, row + 30 */
#define SETUP_ROWS 15
#define EVENT_RECORD_INTS 5    /* course id, four vehicle models */
#define NOP ((uint)nop_stub)

static struct CourseEntry track = {
  "CrazyTwn", MFL_CUSTOM_TRACK_BASE,
  { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 }      /* filled by callbacks_init: the pattern of a course without specials (SuperG_N) */
};
static int selected;
static int held;
static const char *track_entry_name(void) { return track.name; }
static int host_row;
static char *patched_setup;                       /* the setup whose records are replaced now (0: none) */
static int patched_row;
static int *saved[SETUP_VARIANTS];
static int records[SETUP_VARIANTS][EVENT_RECORD_INTS];

/* one list row of the game state */
#define ROW_PROGRESS 18
#define ROW_RECORDS 5
#define ROW_BLOCK 40           /* the row's share of the 600 bytes between the records and the best times */
#define ROW_TIMES 3
struct Row {
  uint progress[ROW_PROGRESS];
  int records[ROW_RECORDS];
  uint best_minutes[ROW_TIMES];
  uint best_seconds[ROW_TIMES];
  float best_fraction[ROW_TIMES];
  char block[ROW_BLOCK];
  byte enabled[ROW_PROGRESS];
  byte pad[2];
};
struct SaveSection {
  char magic[4];
  uint version;
  uint tracks;
  char name[16];
  uint size;
  struct Row row;
};
#define SAVE_MAIN_SIZE 0x42334
#define PROGRESS_OPEN 1
#define PROGRESS_DONE 2

static struct Row other;                 /* not swapped: the track's row; swapped: the host row's (the track's is in the game state) */
static uint track_real_progress[ROW_PROGRESS];      /* the track's progress as the save gets it while unlock_all forces the live words */
static int vehicle_other;
static int swapped;
static int swapped_row;
static int row_ready;
static struct SaveSection section;       /* gathered for the next write / read by the last load */
static int section_loaded;

static void row_get(const struct GameState *g, int row, struct Row *r)
{
  memcpy(r->progress, &g->progress[row * ROW_PROGRESS], sizeof r->progress);
  memcpy(r->records, &g->records[row * ROW_RECORDS], sizeof r->records);
  memcpy(r->best_minutes, &g->best_minutes[row * ROW_TIMES], sizeof r->best_minutes);
  memcpy(r->best_seconds, &g->best_seconds[row * ROW_TIMES], sizeof r->best_seconds);
  memcpy(r->best_fraction, &g->best_fraction[row * ROW_TIMES], sizeof r->best_fraction);
  memcpy(r->block, &g->_gap_564[row * ROW_BLOCK], sizeof r->block);
  memcpy(r->enabled, &g->enabled[row * ROW_PROGRESS], sizeof r->enabled);
  r->pad[0] = r->pad[1] = 0;
}

static void row_put(struct GameState *g, int row, const struct Row *r)
{
  memcpy(&g->progress[row * ROW_PROGRESS], r->progress, sizeof r->progress);
  memcpy(&g->records[row * ROW_RECORDS], r->records, sizeof r->records);
  memcpy(&g->best_minutes[row * ROW_TIMES], r->best_minutes, sizeof r->best_minutes);
  memcpy(&g->best_seconds[row * ROW_TIMES], r->best_seconds, sizeof r->best_seconds);
  memcpy(&g->best_fraction[row * ROW_TIMES], r->best_fraction, sizeof r->best_fraction);
  memcpy(&g->_gap_564[row * ROW_BLOCK], r->block, sizeof r->block);
  memcpy(&g->enabled[row * ROW_PROGRESS], r->enabled, sizeof r->enabled);
}

static int forced(void)
{
#if MFL_FIX_UNLOCK_ALL || MFL_FIX_PREFS
  return mfl_unlock_all_forced();
#else
  return 0;
#endif
}

/* a track nobody has played: every mode open, no records, no times */
static void row_defaults(struct Row *r)
{
  int k;

  memset(r, 0, sizeof *r);
  for (k = 0; k < ROW_PROGRESS; k++) { r->progress[k] = PROGRESS_OPEN; r->enabled[k] = 1; }
  for (k = 0; k < ROW_RECORDS; k++) r->records[k] = -1;
}

/* the track's row as loaded (or its defaults) becomes the one kept here; the game state holds the game's own rows */
static void row_install(const struct Row *r)
{
  int k;

  other = *r;
  memcpy(track_real_progress, r->progress, sizeof track_real_progress);
  if (forced()) {
    for (k = 0; k < ROW_PROGRESS; k++) other.progress[k] = PROGRESS_DONE;
  }
  vehicle_other = 0;
  swapped = 0;
  row_ready = 1;
}

static void row_swap(int row)
{
  struct Row t;
  int v;

  if (!row_ready) {
    row_defaults(&t);
    row_install(&t);
  }
  row_get(&g_game_state, row, &t);
  row_put(&g_game_state, row, &other);
  other = t;
  v = (&g_menu_609a58)[row];
  (&g_menu_609a58)[row] = vehicle_other;
  vehicle_other = v;
  swapped = !swapped;
  swapped_row = row;
}

/* gamesave_gather, after its copy (and after mfl_unlock_all_unforce): the save block gets the host row's own values, the section the
   track's.  Progress while unlock_all forces it: the block's words are the real ones already, the track's come from track_real_progress. */
void mfl_custom_track_save_gather(void *save_block)
{
  struct GameState *save = (struct GameState *)save_block;
  struct Row track, host;

  if (!row_ready) {
    row_defaults(&track);
    row_install(&track);
  }
  if (swapped) {
    row_get(save, swapped_row, &track);
    host = other;
    if (forced()) memcpy(host.progress, track.progress, sizeof host.progress);      /* mfl_unlock_all_unforce has put the host's real words there */
    row_put(save, swapped_row, &host);
  }
  else {
    track = other;
  }
  if (forced()) memcpy(track.progress, track_real_progress, sizeof track.progress);
  else memcpy(track_real_progress, track.progress, sizeof track_real_progress);
  memset(&section, 0, sizeof section);
  memcpy(section.magic, "MFLX", 4);
  section.version = 1;
  section.tracks = 1;
  strcpy(section.name, track_entry_name());
  section.size = sizeof section.row;
  section.row = track;
}

/* gamesave_write, after the game's block is written: the section goes behind it */
void mfl_custom_track_save_write(const char *path)
{
  FILE *f = fopen(path, "r+b");

  if (f == 0) return;
  if (fseek(f, SAVE_MAIN_SIZE, SEEK_SET) == 0) fwrite(&section, 1, sizeof section, f);
  fclose(f);
}

/* gamesave_load, after the game's block is read */
void mfl_custom_track_save_read(const char *path)
{
  struct SaveSection s;
  FILE *f = fopen(path, "rb");

  section_loaded = 0;
  if (f == 0) return;
  if (fseek(f, SAVE_MAIN_SIZE, SEEK_SET) == 0 && fread(&s, 1, sizeof s, f) == sizeof s && memcmp(s.magic, "MFLX", 4) == 0 &&
      s.version == 1 && s.tracks >= 1 && s.size == sizeof s.row && strncmp(s.name, track_entry_name(), sizeof s.name) == 0) {
    section = s;
    section_loaded = 1;
  }
  fclose(f);
}

/* gamesave_apply, last step: the game state is the loaded one (no row exchanged), the track's row the loaded section's or the defaults */
void mfl_custom_track_save_apply(void)
{
  struct Row r;

  if (section_loaded) r = section.row;
  else row_defaults(&r);
  row_install(&r);
  mfl_custom_track_sync();
}

static void callbacks_init(void)
{
  static const char has[13] = { 1, 1, 1, 0, 1, 1, 1, 1, 0, 1, 1, 0, 0 };
  int k;

  for (k = 0; k < 13; k++) track.callbacks[k] = has[k] ? NOP : 0;
}

/* is the track's archive there?  (looked for once, by the name game_open_piz opens) */
int mfl_custom_track_archive_present(void)
{
  static int present = -1;
  char name[64];
  FILE *f;

  if (present < 0) {
    game_path_to_8_3_upper(name, course_content_path_build(MFL_CUSTOM_TRACK_ARCHIVE));
    f = fopen(name, "rb");
    present = f != 0;
    if (f != 0) fclose(f);
  }
  return present;
}

/* the two pictures of the event list (the game's own: TrackImages.txd of sfx.piz), from the track's archive */
static struct RwTexDictionary *pictures;

void mfl_custom_track_pictures_load(void)
{
  if (!mfl_custom_track_archive_present()) return;
  game_open_piz(course_content_path_build(MFL_CUSTOM_TRACK_ARCHIVE));
  pictures = (struct RwTexDictionary *)texdict_load_named_b("PICTURES.TXD", 0, 0);
  RwTexDictionarySetCurrent((struct RwTexDictionary *)0);
  game_close_piz();
}

void mfl_custom_track_pictures_free(void)
{
  if (pictures != 0) RwTexDictionaryDestroy_004d5ac0(pictures);
  pictures = 0;
}

void *mfl_custom_track_picture(int item)
{
  if (!selected || pictures == 0) return 0;
  return RwTexDictionaryFindNamedTexture(pictures, item == 0 ? "CrazyTown1" : "CrazyTown2");
}

/* the outline of the loading screen: an entry as the game's cup scene table has one per course (clusters/cl_cup_scene_load_models.c) */
int *mfl_custom_track_outline(void)
{
  return selected && mfl_custom_track_outline_entry[0] != 0 ? mfl_custom_track_outline_entry : 0;
}

/* The host row's second and third variants can be mirrored events: the game then swaps left and right of every player's input and
   shows the picture mirrored.  The track is never played mirrored: called wherever the game switches mirror mode on. */
void mfl_custom_track_no_mirror(void)
{
  if (selected) g_game_state.mirror_mode = 0;
}

int mfl_custom_track_listed(void)
{
  if (!mfl_custom_track_archive_present()) return 0;
  return (g_event_type >= EVENT_MULTIPLAYER_6 && g_event_type <= 8) || (g_event_type >= EVENT_QUICK_RACE_11 && g_event_type <= EVENT_QUICK_RACE_13);
}

int mfl_custom_track_selected(void)
{
  return selected;
}

void mfl_custom_track_select(int on)
{
  selected = on;
  host_row = g_career_row;
  mfl_custom_track_sync();
}

static void restore(void)
{
  int v;

  if (patched_setup == 0) return;
  for (v = 0; v < SETUP_VARIANTS; v++) {
    int **slot = (int **)(patched_setup + SETUP_ENTRIES + (patched_row + v * SETUP_ROWS) * 4);

    if (*slot == records[v]) *slot = saved[v];
  }
  patched_setup = 0;
}

void mfl_custom_track_sync(void)
{
  int v, k;

  if (selected && (!mfl_custom_track_listed() || g_career_row != host_row)) selected = 0;
  if (selected) g_game_state.mirror_mode = 0;      /* never mirrored (the host row's list icons may ask for it): see mfl_custom_track_no_mirror */
  if (swapped && (!selected || swapped_row != host_row)) row_swap(swapped_row);      /* the host row's own results back */
  if (selected && !swapped) row_swap(host_row);                                      /* the track's results in their place */
  if (patched_setup != 0 && (!selected || patched_setup != g_race_setup || patched_row != host_row)) restore();
  if (!selected || patched_setup != 0 || g_race_setup == 0) return;
  callbacks_init();
  for (v = 0; v < SETUP_VARIANTS; v++) {
    int **slot = (int **)(g_race_setup + SETUP_ENTRIES + (host_row + v * SETUP_ROWS) * 4);

    saved[v] = *slot;
    if (*slot == 0) continue;
    for (k = 0; k < EVENT_RECORD_INTS; k++) records[v][k] = (*slot)[k];
    records[v][0] = MFL_CUSTOM_TRACK_BASE;
    *slot = records[v];
  }
  patched_setup = g_race_setup;
  patched_row = host_row;
}

struct CourseEntry *mfl_custom_track_entry(unsigned int course_id)
{
  return selected && !held && course_id == MFL_CUSTOM_TRACK_BASE ? &track : 0;
}

void mfl_custom_track_hold(int on)
{
  held = on;
}

const unsigned short *mfl_custom_track_text(int id)
{
  static const unsigned short name[] = { 10, 'C', 'r', 'a', 'z', 'y', ' ', 'T', 'o', 'w', 'n', 0 };

  (void)id;
  return name;
}
