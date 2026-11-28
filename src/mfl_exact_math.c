/* mfl_exact_math.c: exact square roots for the game's code (new code in the place of four RenderWare functions).
 *
 * The PC game's RenderWare has _rwSqrt and _rwInvSqrt read a table: results good to about 4 parts in 100000.  RwV3dLength and
 * RwV3dNormalize are built on them, and the game calls all four (524 places in the C sources: the car physics, the cameras, the
 * weapons ...).  The Xbox version's RenderWare uses the processor's square root (sqrtss), exact to float precision; first seen in
 * triangle_normal, where the PC game leaves |normal| = 1.000043 and the Xbox version 1.000000 for the same triangle.
 *
 * These definitions take the place of the imports from mflrw.dll for every call from the exe.  The library's own calls of its
 * table versions (inside mflrw.dll: rendering, collision trees, the crash physics) are not changed.
 */
#include "mfl_tier2.h"
#include "mfl_fix.h"

#include <math.h>

RwReal _rwSqrt(const RwReal num)
{
  return (RwReal)sqrt((double)num);
}

RwReal _rwInvSqrt(const RwReal num)
{
  return (RwReal)(1.0 / sqrt((double)num));
}

RwReal RwV3dLength(struct RwV3d *in)
{
  return (RwReal)sqrt((double)in->x * in->x + (double)in->y * in->y + (double)in->z * in->z);
}

/* out = in at unit length; returns the length of in (a zero vector stays zero, as with the table version) */
RwReal RwV3dNormalize(struct RwV3d *out, struct RwV3d *in)
{
  double length = sqrt((double)in->x * in->x + (double)in->y * in->y + (double)in->z * in->z);
  double scale = length > 0.0 ? 1.0 / length : 0.0;

  out->x = (RwReal)(in->x * scale);
  out->y = (RwReal)(in->y * scale);
  out->z = (RwReal)(in->z * scale);
  return (RwReal)length;
}
