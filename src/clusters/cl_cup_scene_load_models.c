// cluster-entries: cup_scene_load_models
/* Installed cluster cup_scene_load_models (tools/cluster_install.py from output/cluster_pilot_zx/cup_scene_load_models.c); entries are patched at their original addresses by build_overlay.py --clusters. */
#include "mfl_tier2.h"
#include "mfl_fix.h"
/* DECLS-BEGIN */
/* DECLS-END */
/*00401f80*/ extern int __cdecl load_map_model(undefined4 p0);
/*00402b90*/ extern int clump_from_geometry_a();
/*00402ee0*/ extern int clump_from_geometry_b();
/*005dd380*/ extern undefined4 g_cup_scene_5dd380;
/*0064cbe8*/ extern undefined4 g_cup_64cbe8;
#define CUP_SCENE_TABLE_BYTES (0x7c)
#define CUP_SCENE_ENTRY_DWORDS (0x1a)
#define CUP_ENTRY_MODEL_ID_INDEX (0xe)
#define CUP_ENTRY_CLUMP_A_INDEX (0x10)
#define CUP_ENTRY_CLUMP_B_INDEX (0x14)
#define CUP_CLUMP_A_COUNT (4)
#define CUP_CLUMP_B_COUNT (6)

/* cup_scene_load_models */

/* "loads the models listed at 0x5DD380 through load_map_model and computes their bounds" */

/*
 * Loads the cup scene models. Walks the model id table at g_cup_scene_5dd380
 * (CUP_SCENE_TABLE_BYTES bytes of dwords). For each id it loads the model, stores
 * the id and the model handle in a CUP_SCENE_ENTRY_DWORDS-dword entry at
 * g_cup_64cbe8, computes the bounds (cup_scene_compute_bounds, inferred), then
 * fills the clump slots of that entry. Takes no parameters, returns nothing.
 */
static int cup_scene_compute_bounds_r(int * p0);
extern void cup_scene_compute_bounds(void);
void cup_scene_load_models(void)

{
  undefined4 value;
  int remaining;
  uint byte_offset;
  undefined4 *entry;
  undefined4 *dest;
  
  entry = &g_cup_64cbe8;
  byte_offset = 0;
  /* one iteration per model id in the table: load it, compute bounds, fill its clumps */
  do {
    value = *(undefined4 *)((char *)&g_cup_scene_5dd380 + byte_offset);
    entry[CUP_ENTRY_MODEL_ID_INDEX] = value;
    value = load_map_model(value);
    *entry = value;
    cup_scene_compute_bounds_r(entry);
    dest = entry + CUP_ENTRY_CLUMP_A_INDEX;
    remaining = CUP_CLUMP_A_COUNT;
    /* clump slots A: CUP_CLUMP_A_COUNT results of clump_from_geometry_a (inferred) */
    do {
      value = clump_from_geometry_a();
      *dest = value;
      dest = dest + 1;
      remaining = remaining + -1;
    } while (remaining != 0);
    /* clump slots B: CUP_CLUMP_B_COUNT results of clump_from_geometry_b (inferred) */
    dest = entry + CUP_ENTRY_CLUMP_B_INDEX;
    remaining = CUP_CLUMP_B_COUNT;
    do {
      value = clump_from_geometry_b();
      *dest = value;
      dest = dest + 1;
      remaining = remaining + -1;
    } while (remaining != 0);
    byte_offset = byte_offset + 4;
    entry = entry + CUP_SCENE_ENTRY_DWORDS;
  } while (byte_offset < CUP_SCENE_TABLE_BYTES);
  return;
}

/*004a43d0*/ extern undefined __cdecl game_open_piz(char *p0);
/*004a4440*/ extern int game_close_piz();
/*0042fa80*/ extern char * course_content_path_build();
/*004c3bf0*/ extern int FUN_004c3bf0(void *p0, undefined4 p1, undefined4 p2);
int mfl_custom_track_outline_entry[CUP_SCENE_ENTRY_DWORDS];

/* The outline of the Crazy Town track (mfl_custom_track.c): one more entry, built as the loop above builds the game's own, from
   OUTLINE.DFF of the track's archive. */
void mfl_custom_track_outline_load(void)
{
  int *entry = mfl_custom_track_outline_entry;
  int k;

  if (!mfl_custom_track_archive_present()) return;
  game_open_piz(course_content_path_build(MFL_CUSTOM_TRACK_ARCHIVE));
  entry[CUP_ENTRY_MODEL_ID_INDEX] = -1;
  entry[0] = FUN_004c3bf0("OUTLINE.DFF", 0, 0);
  if (entry[0] != 0) {
    cup_scene_compute_bounds_r(entry);
    for (k = 0; k < CUP_CLUMP_A_COUNT; k++) entry[CUP_ENTRY_CLUMP_A_INDEX + k] = clump_from_geometry_a();
    for (k = 0; k < CUP_CLUMP_B_COUNT; k++) entry[CUP_ENTRY_CLUMP_B_INDEX + k] = clump_from_geometry_b();
  }
  game_close_piz();
}

/* cup_scene_compute_bounds_r: C -> original cup_scene_compute_bounds (registers esi) */
__declspec(naked) int cup_scene_compute_bounds_r(int * p0)
{
    __asm {
        push esi
        mov esi, dword ptr [esp + 8]
        call cup_scene_compute_bounds
        pop esi
        ret
    }
}
