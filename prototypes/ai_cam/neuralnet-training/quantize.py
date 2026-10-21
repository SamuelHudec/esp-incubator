"""Calibrate INT8, validate it, and export a fixed graph as portable C arrays."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import subprocess
import tempfile
import time
import numpy as np
import torch
from torch import nn
from data import Faces
from model import load_model, decode, iou


def install_model(source, destination):
    """Replace firmware weights atomically, preserving them if copying fails."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix='.tmp', delete=False) as f:
            temporary = Path(f.name)
            with source.open('rb') as model:
                shutil.copyfileobj(model, f)
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def round_away(x):
    return np.sign(x)*np.floor(np.abs(x)+.5)


def folded_layers(model):
    layers=[]
    modules=list(model.backbone.children())
    for i in range(0,len(modules),3):
        conv,bn,relu=modules[i:i+3]
        assert isinstance(conv,nn.Conv2d) and isinstance(bn,nn.BatchNorm2d) and isinstance(relu,nn.ReLU)
        layers.append((torch.nn.utils.fusion.fuse_conv_bn_eval(conv,bn),True))
    layers.append((model.head,False))
    return layers


def calibrate(model, dataset, count, seed):
    layers=folded_layers(model)
    maxima=[np.zeros(c.out_channels if not relu else 1) for c,relu in layers]
    indices=random.Random(seed).sample(range(len(dataset)),min(count,len(dataset)))
    max_fusion_error=0.
    with torch.inference_mode():
        for index in indices:
            x=dataset[index][0][None]
            original=model(x)
            for j,(conv,relu) in enumerate(layers):
                x=conv(x)
                if relu: x=x.relu()
                peak=x.abs().amax().reshape(1) if relu else x.abs().amax(dim=(0,2,3))
                maxima[j]=np.maximum(maxima[j],peak.numpy())
            max_fusion_error=max(max_fusion_error,float((x-original).abs().max()))
    result=[];input_scale=1/127;hi,wi=96,128
    for (conv,relu),peak in zip(layers,maxima):
        weight=conv.weight.detach().numpy().astype(np.float64)
        weight_scale=np.maximum(np.abs(weight).max(axis=(1,2,3))/127,1e-12)
        qw=round_away(weight/weight_scale[:,None,None,None]).clip(-127,127).astype(np.int8)
        bias=conv.bias.detach().numpy() if conv.bias is not None else np.zeros(conv.out_channels)
        qb=round_away(bias/(input_scale*weight_scale))
        bound=np.abs(qb)+127*np.abs(qw.astype(np.int64)).sum(axis=(1,2,3))
        if not np.isfinite(bound).all() or np.any(bound>np.iinfo(np.int32).max):
            raise ValueError('INT32 accumulator could overflow')
        output_scale=np.maximum(peak/127,1e-12)
        ratios=input_scale*weight_scale/output_scale
        multipliers=[];shifts=[]
        for ratio in ratios:
            mantissa,exponent=math.frexp(float(ratio))
            multiplier=int(math.floor(mantissa*(1<<31)+.5));shift=31-exponent
            if multiplier==(1<<31): multiplier//=2;shift-=1
            if not 0<=shift<=62:
                raise ValueError('Scale ratio cannot be represented by supported integer shifts')
            multipliers.append(multiplier);shifts.append(shift)
        for limit,mult,shift in zip(bound,multipliers,shifts):
            if int(limit)*mult+(1<<max(shift-1,0)) > np.iinfo(np.int64).max:
                raise ValueError('INT64 requantization could overflow')
        k=conv.kernel_size[0];stride=conv.stride[0];pad=conv.padding[0]
        ho=(hi+2*pad-k)//stride+1;wo=(wi+2*pad-k)//stride+1
        result.append(dict(ci=conv.in_channels,co=conv.out_channels,hi=hi,wi=wi,ho=ho,wo=wo,
                           kernel=k,stride=stride,padding=pad,groups=conv.groups,relu=int(relu),
                           weights=qw,bias=qb.astype(np.int32),multiplier=np.array(multipliers,dtype=np.int32),
                           shift=np.array(shifts,dtype=np.int32),output_scale=output_scale))
        input_scale=float(output_scale[0]);hi,wi=ho,wo
    return result,indices,max_fusion_error


def int_conv(x, layer):
    k=layer['kernel'];s=layer['stride'];p=layer['padding']
    padded=np.pad(x.astype(np.int64),((0,0),(p,p),(p,p)))
    patches=np.lib.stride_tricks.sliding_window_view(padded,(k,k),axis=(1,2))[:,::s,::s]
    weight=layer['weights'].astype(np.int64)
    if layer['groups']==1:
        acc=np.einsum('cyxkl,ockl->oyx',patches,weight,optimize=True)
    elif layer['groups']==layer['ci']==layer['co']:
        acc=np.einsum('cyxkl,ckl->cyx',patches,weight[:,0],optimize=True)
    else:
        raise ValueError('Unsupported groups')
    acc+=layer['bias'][:,None,None]
    product=acc*layer['multiplier'][:,None,None].astype(np.int64)
    shift=layer['shift'][:,None,None].astype(np.int64)
    half=np.where(shift>0,np.left_shift(np.int64(1),np.maximum(shift-1,0)),0)
    rounded=np.sign(product)*np.right_shift(np.abs(product)+half,shift)
    return rounded.clip(0 if layer['relu'] else -127,127).astype(np.int8)


def integer_forward(x,layers):
    outputs=[]
    for layer in layers:
        x=int_conv(x,layer);outputs.append(x)
    return outputs


def input_int8(tensor):
    return round_away(tensor.numpy()*127).clip(0,127).astype(np.int8)


def write_c(layers,out):
    def array(name,ctype,values):
        flat=np.asarray(values).reshape(-1)
        text=[]
        for i in range(0,len(flat),24):
            text.append('    '+', '.join(str(int(v)) for v in flat[i:i+24]))
        return f'static const {ctype} {name}[] = {{\n'+',\n'.join(text)+'\n};\n'
    content=['#ifndef NN_MODEL_H\n#define NN_MODEL_H\n#include "nn_int8.h"\n']
    for i,layer in enumerate(layers):
        for key,ctype in [('weights','int8_t'),('bias','int32_t'),('multiplier','int32_t'),('shift','int32_t')]:
            content.append(array(f'nn_{i}_{key}',ctype,layer[key]))
    content.append('static const nn_layer nn_layers[] = {\n')
    for i,l in enumerate(layers):
        fields=[str(l[k]) for k in ['ci','co','hi','wi','ho','wo','kernel','stride','padding','groups','relu']]
        fields += [f'nn_{i}_{k}' for k in ['weights','bias','multiplier','shift']]
        content.append('    {'+', '.join(fields)+'},\n')
    content.append('};\n#define NN_LAYER_COUNT '+str(len(layers))+'\n#define NN_INPUT_SIZE 12288\n#define NN_OUTPUT_SIZE 960\n#define NN_BUFFER_SIZE 24576\n')
    content.append('static const float nn_output_scales[5] = {'+', '.join(f'{v:.9e}f' for v in layers[-1]['output_scale'])+'};\n#endif\n')
    (out/'nn_model.h').write_text(''.join(content))


def verify_c(layers,x,out):
    compiler=shutil.which('cc')
    if compiler is None:
        raise RuntimeError('A C compiler (cc) is required for integer parity verification')
    src=Path(__file__).resolve().parent.parent/'firmware'/'neuralnet'
    with tempfile.TemporaryDirectory(prefix='nn-verify-') as directory:
        work=Path(directory)
        (work/'verify.c').write_text('''#include "nn_model.h"
    #include <stdio.h>
    static int8_t a[NN_BUFFER_SIZE], b[NN_BUFFER_SIZE];
    int main(void) {
        if (fread(a,1,NN_INPUT_SIZE,stdin) != NN_INPUT_SIZE) return 1;
        int8_t *in=a,*out=b;
        for (int i=0;i<NN_LAYER_COUNT;i++) {
            nn_conv(&nn_layers[i],in,out);
            size_t n=(size_t)nn_layers[i].co*nn_layers[i].ho*nn_layers[i].wo;
            if (fwrite(out,1,n,stdout)!=n) return 2;
            int8_t *tmp=in;in=out;out=tmp;
        }
        return 0;
    }
    ''')
        subprocess.run([compiler,'-std=c99','-O2','-Wall','-Wextra','-Werror',str(work/'verify.c'),
                        '-I'+str(out.resolve()),'-I'+str(src),str(src/'nn_int8.c'),'-o',str(work/'verify')],check=True)
        rng=np.random.default_rng(42)
        for test in [x,np.zeros_like(x),np.full_like(x,127),rng.integers(0,128,x.shape,dtype=np.int8)]:
            expected=b''.join(t.tobytes() for t in integer_forward(test,layers))
            actual=subprocess.run([str(work/'verify')],input=test.tobytes(),capture_output=True,check=True).stdout
            if expected!=actual: raise AssertionError('C/Python layer outputs differ')
    np.savez(out/'golden.npz',input=x,**{f'layer_{i}':v for i,v in enumerate(integer_forward(x,layers))})


def measure(predictions, truths, threshold):
    tp=fp=fn=0
    for pred,truth in zip(predictions,truths):
        truth=np.asarray(truth).reshape(-1,4);used=set()
        for detection in decode(torch.from_numpy(pred.astype(np.float32)),threshold):
            overlaps=iou(detection[:4],truth)
            for i in used: overlaps[i]=-1
            match=int(overlaps.argmax()) if len(overlaps) else -1
            if match>=0 and overlaps[match]>=.5: tp+=1;used.add(match)
            else: fp+=1
        fn+=len(truth)-len(used)
    return dict(tp=tp,fp=fp,fn=fn,precision=tp/max(tp+fp,1),recall=tp/max(tp+fn,1))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint',required=True)
    parser.add_argument('--data',required=True,help='Autolabel dataset directory')
    parser.add_argument('--out',help='New output directory, default checkpoint directory/int8')
    parser.add_argument('--calibration-count',type=int,default=128)
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--threshold',type=float,default=.5)
    args=parser.parse_args()
    if args.calibration_count<1 or not 0<args.threshold<1: parser.error('Invalid count or threshold')
    torch.set_num_threads(4)
    manifest=Path(args.data).resolve()/'dataset.json'
    train=Faces(manifest,split='train');val=Faces(manifest,split='val')
    if train.image_paths() & val.image_paths(): raise ValueError('Calibration/validation overlap')
    model=load_model(args.checkpoint)
    out=Path(args.out) if args.out else Path(args.checkpoint).parent/'int8'
    out=out.resolve();out.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter()
    layers,indices,fusion_error=calibrate(model,train,args.calibration_count,args.seed)
    write_c(layers,out)
    verify_c(layers,input_int8(train[indices[0]][0]),out)
    floating=[];integer=[];truths=[]
    with torch.inference_mode():
        for i in range(len(val)):
            x,_,_,boxes=val[i]
            floating.append(model(x[None])[0].numpy())
            raw=integer_forward(input_int8(x),layers)[-1]
            integer.append(raw*layers[-1]['output_scale'][:,None,None])
            truths.append(boxes)
            if (i+1)%25==0: print(f'Validation {i+1}/{len(val)}',flush=True)
    report=dict(checkpoint=str(Path(args.checkpoint).resolve()),
                checkpoint_sha256=hashlib.sha256(Path(args.checkpoint).read_bytes()).hexdigest(),
                calibration_images=[train.records[i]['image'] for i in indices],
                dataset=str(manifest),dataset_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                seed=args.seed,torch_version=str(torch.__version__),numpy_version=np.__version__,
                threshold=args.threshold,
                fusion_max_abs_error=fusion_error,c_python_parity='all layers exact on four inputs',
                float_metrics=measure(floating,truths,args.threshold),
                int8_metrics=measure(integer,truths,args.threshold),
                head_mean_abs_error=float(np.abs(np.asarray(floating)-np.asarray(integer)).mean()),
                weight_bytes=sum(l['weights'].nbytes for l in layers),
                integer_parameter_bytes=sum(l[k].nbytes for l in layers for k in ['weights','bias','multiplier','shift']),
                activation_buffers_bytes=2*24576,
                output_scales=layers[-1]['output_scale'].tolist(),
                seconds=time.perf_counter()-started,
                note='Validation against teacher pseudo-labels; no ESP32 runtime benchmark.')
    (out/'report.json').write_text(json.dumps(report,indent=2))
    destination=Path(__file__).resolve().parent.parent/'firmware'/'neuralnet'/'nn_model.h'
    install_model(out/'nn_model.h',destination)
    print(json.dumps(report|{'calibration_images':len(indices)},indent=2))
    print(f'Firmware model updated: {destination}\nCheckpoint: {Path(args.checkpoint).resolve()}')


if __name__=='__main__':
    main()
