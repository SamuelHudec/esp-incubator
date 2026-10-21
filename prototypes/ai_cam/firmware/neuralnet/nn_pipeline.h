#ifndef NN_PIPELINE_H
#define NN_PIPELINE_H
#include "nn_int8.h"
#ifdef __cplusplus
extern "C" {
#endif
#define NN_CANDIDATES 192
typedef struct { float x1,y1,x2,y2,score; } nn_box;
/* Downsample BGR888 to 128x96 grayscale INT8. Source must be >= target size.
 * Caller supplies 12288 output bytes. Area integration rounds grayscale before
 * resizing, matching the Python order; rounding at half values may differ by 1. */
int nn_preprocess_bgr(const uint8_t *bgr, int width, int height, int8_t *output);
/* Both activation buffers must have capacity for every layer (24576 here).
 * Optional yield callback runs between layers, e.g. to allow RTOS idle time. */
int8_t *nn_run(const nn_layer *layers, int count, int8_t *a, int8_t *b, void (*yield_fn)(void));
/* Caller provides 192 scratch boxes, separate output with capacity >=1. */
int nn_decode(const int8_t *head, const float *scales, float threshold, float nms,
              nn_box *scratch, nn_box *output, int capacity);
#ifdef __cplusplus
}
#endif
#endif
