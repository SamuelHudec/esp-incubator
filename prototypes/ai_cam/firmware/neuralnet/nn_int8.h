#ifndef NN_INT8_H
#define NN_INT8_H
#include <stdint.h>
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
/* CHW activations; OIHW weights, local input channels for grouped convolution.
 * Symmetric INT8 [-127,127], zero point 0; hidden output ReLU [0,127]. */
typedef struct {
    int ci, co, hi, wi, ho, wo, kernel, stride, padding, groups, relu;
    const int8_t *weights;
    const int32_t *bias;
    const int32_t *multiplier;
    const int32_t *shift;
} nn_layer;
/* Caller supplies disjoint input/output buffers of the declared layer sizes.
 * Export validates INT32 accumulation and INT64 requantization bounds. */
void nn_conv(const nn_layer *layer, const int8_t *input, int8_t *output);
#ifdef __cplusplus
}
#endif
#endif
