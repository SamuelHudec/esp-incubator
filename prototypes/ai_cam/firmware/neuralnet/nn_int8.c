#include "nn_int8.h"

/* Shared exact fixed-point conversion for both convolution paths. */
static int8_t nn_requantize(int32_t acc, int32_t multiplier, int shift, int low) {
    int64_t value = (int64_t)acc * multiplier;
    if (shift > 0) {
        int64_t half = (int64_t)1 << (shift-1);
        value = value >= 0 ? (value + half) >> shift : -((-value + half) >> shift);
    }
    if (value < low) value = low;
    if (value > 127) value = 127;
    return (int8_t)value;
}

/* Four adjacent CHW pixels share weight loads and channel-address arithmetic.
 * No scratch allocation, padding checks or kernel loops for pointwise layers. */
static void nn_pointwise(const nn_layer *l, const int8_t *input, int8_t *output) {
    const int pixels = l->hi*l->wi;
    const int low = l->relu ? 0 : -127;
    for (int oc=0; oc<l->co; ++oc) {
        const int8_t *weights=l->weights+oc*l->ci;
        int8_t *dst=output+oc*pixels;
        const int32_t bias=l->bias[oc], multiplier=l->multiplier[oc];
        const int shift=l->shift[oc];
        int pos=0;
        for (; pos+3<pixels; pos+=4) {
            int32_t a=bias,b=bias,c=bias,d=bias;
            const int8_t *src=input+pos;
            for (int ic=0; ic<l->ci; ++ic,src+=pixels) {
                const int32_t w=weights[ic];
                a+=src[0]*w;b+=src[1]*w;c+=src[2]*w;d+=src[3]*w;
            }
            dst[pos]=nn_requantize(a,multiplier,shift,low);
            dst[pos+1]=nn_requantize(b,multiplier,shift,low);
            dst[pos+2]=nn_requantize(c,multiplier,shift,low);
            dst[pos+3]=nn_requantize(d,multiplier,shift,low);
        }
        for (; pos<pixels; ++pos) {
            int32_t acc=bias;
            for (int ic=0; ic<l->ci; ++ic) acc+=input[ic*pixels+pos]*(int32_t)weights[ic];
            dst[pos]=nn_requantize(acc,multiplier,shift,low);
        }
    }
}

void nn_conv(const nn_layer *l, const int8_t *input, int8_t *output) {
    if (l->kernel==1 && l->stride==1 && l->padding==0 && l->groups==1 &&
        l->hi==l->ho && l->wi==l->wo) {
        nn_pointwise(l,input,output);
        return;
    }
    const int local_ci = l->ci / l->groups;
    const int local_co = l->co / l->groups;
    for (int oc = 0; oc < l->co; ++oc) {
        for (int oy = 0; oy < l->ho; ++oy) {
            for (int ox = 0; ox < l->wo; ++ox) {
                int32_t acc = l->bias[oc];
                for (int ic = 0; ic < local_ci; ++ic) {
                    int channel = (oc / local_co) * local_ci + ic;
                    for (int ky = 0; ky < l->kernel; ++ky) {
                        int iy = oy * l->stride + ky - l->padding;
                        if (iy < 0 || iy >= l->hi) continue;
                        for (int kx = 0; kx < l->kernel; ++kx) {
                            int ix = ox * l->stride + kx - l->padding;
                            if (ix < 0 || ix >= l->wi) continue;
                            int wi = ((oc * local_ci + ic) * l->kernel + ky) * l->kernel + kx;
                            acc += (int32_t)input[(channel*l->hi+iy)*l->wi+ix] * l->weights[wi];
                        }
                    }
                }
                output[(oc*l->ho+oy)*l->wo+ox] = nn_requantize(
                    acc,l->multiplier[oc],l->shift[oc],l->relu ? 0 : -127);
            }
        }
    }
}
