#include "nn_pipeline.h"
#include <math.h>

static float clip(float x) { return fminf(1.0f,fmaxf(0.0f,x)); }
/* Exact 5:2 area downsample. Half-pixel overlap weights are [2,2,1]
 * or [1,2,2]; their 2-D sum is 25. Grayscale is rounded before resizing,
 * as in the reference. An odd denominator cannot produce half-integer ties. */
static void nn_preprocess_qvga(const uint8_t *bgr, int8_t *output) {
    for (int y=0; y<96; ++y) {
        const int sy=(y*5)/2;
        const int wy[3]={y%2 ? 1:2,2,y%2 ? 2:1};
        for (int x=0; x<128; ++x) {
            const int sx=(x*5)/2;
            const int wx[3]={x%2 ? 1:2,2,x%2 ? 2:1};
            unsigned sum=0;
            for (int dy=0; dy<3; ++dy) {
                const uint8_t *p=bgr+((sy+dy)*320+sx)*3;
                for (int dx=0; dx<3; ++dx,p+=3) {
                    unsigned gray=(3735*p[0]+19235*p[1]+9798*p[2]+16384)>>15;
                    sum+=gray*wx[dx]*wy[dy];
                }
            }
            unsigned gray=(sum+12)/25;
            output[y*128+x]=(int8_t)((gray*127+127)/255);
        }
    }
}
int nn_preprocess_bgr(const uint8_t *bgr, int width, int height, int8_t *output) {
    if (!bgr || !output || width<128 || height<96 || width>4096 || height>4096) return -1;
    if (width==320 && height==240) {
        nn_preprocess_qvga(bgr,output);
        return 0;
    }
    float sx=width/128.0f, sy=height/96.0f;
    for (int y=0;y<96;y++) for (int x=0;x<128;x++) {
        float left=x*sx,right=(x+1)*sx,top=y*sy,bottom=(y+1)*sy,sum=0;
        for(int iy=(int)top;iy<(int)ceilf(bottom);iy++) {
            float wy=fminf(bottom,iy+1.0f)-fmaxf(top,(float)iy);
            for(int ix=(int)left;ix<(int)ceilf(right);ix++) {
                float wx=fminf(right,ix+1.0f)-fmaxf(left,(float)ix);
                const uint8_t *p=bgr+((size_t)iy*width+ix)*3;
                int gray=(3735*p[0]+19235*p[1]+9798*p[2]+16384)>>15;
                sum+=gray*wx*wy;
            }
        }
        int gray=(int)lrintf(sum/(sx*sy));
        if(gray<0) gray=0;
        if(gray>255) gray=255;
        output[y*128+x]=(int8_t)((gray*127+127)/255);
    }
    return 0;
}
int8_t *nn_run(const nn_layer *layers,int count,int8_t *a,int8_t *b,void (*yield_fn)(void)) {
    for(int i=0;i<count;i++) {
        nn_conv(layers+i,a,b);
        int8_t *tmp=a;a=b;b=tmp;
        if(yield_fn) yield_fn();
    }
    return a;
}
static float overlap(nn_box a,nn_box b) {
    float area=fmaxf(0,fminf(a.x2,b.x2)-fmaxf(a.x1,b.x1))*fmaxf(0,fminf(a.y2,b.y2)-fmaxf(a.y1,b.y1));
    float total=(a.x2-a.x1)*(a.y2-a.y1)+(b.x2-b.x1)*(b.y2-b.y1)-area;
    return area/fmaxf(total,1e-9f);
}
int nn_decode(const int8_t *head,const float *scales,float threshold,float nms,
              nn_box *scratch,nn_box *output,int capacity) {
    if(!head || !scales || !scratch || !output || capacity<1 || !(threshold>0 && threshold<1) || !(nms>=0 && nms<=1)) return -1;
    int count=0;
    for(int i=0;i<192;i++) {
        float score=1.0f/(1.0f+expf(-head[i]*scales[0]));
        if(score<threshold) continue;
        float cx=(i%16+.5f)/16,cy=(i/16+.5f)/12;
        nn_box b={clip(cx-head[192+i]*scales[1]),clip(cy-head[384+i]*scales[2]),
                  clip(cx+head[576+i]*scales[3]),clip(cy+head[768+i]*scales[4]),score};
        if(b.x2<=b.x1 || b.y2<=b.y1) continue;
        /* Stable descending insertion matches Python's row-major tie order. */
        int j=count;
        while(j>0 && scratch[j-1].score<b.score) {scratch[j]=scratch[j-1];j--;}
        scratch[j]=b;count++;
    }
    int kept=0;
    for(int i=0;i<count && kept<capacity;i++) {
        int suppress=0;
        for(int j=0;j<kept;j++) if(overlap(scratch[i],output[j])>nms) {suppress=1;break;}
        if(!suppress) output[kept++]=scratch[i];
    }
    return kept;
}
