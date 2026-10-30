"""Independently reconstruct CAD connectivity and compare with canonical pins.

Reads the serialized EasyEDA primitives, not generator drawing objects. Checks
for missing pins, wrong labels, dangling nets and unintended geometric shorts.
This is a connectivity check, not circuit simulation or hardware verification.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
canonical_path=Path(sys.argv[2]) if len(sys.argv)>2 else ROOT/'docs/full-v02-netlist.json'
canonical=json.loads(canonical_path.read_text())
source=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'hardware/easyeda/lighthouse-v02-project.json'
project=json.loads(source.read_text())
if 'schematics' not in project:
    project={'schematics':[{'dataStr':project}]}
expected={(p['ref'],k):v for p in canonical['parts'] for k,v in p['pins'].items()}
parent={}
def find(x):
    parent.setdefault(x,x)
    if parent[x]!=x:parent[x]=find(parent[x])
    return parent[x]
def join(x,y):parent[find(x)]=find(y)
pins={};labels=[]
for i,sheet in enumerate(project['schematics']):
    doc=sheet['dataStr']
    shapes=(json.loads(doc) if isinstance(doc,str) else doc)['shape']
    if 'continuous' in source.name:
        assert not any(s.startswith(('N~','F~')) for s in shapes),'Continuous drawing must not rely on implicit labels/flags'
    seg=[];points=set()
    def point(x,y):
        p=(i,float(x),float(y));points.add(p);find(p);return p
    for s in shapes:
        fields=s.split('~')
        if fields[0]=='LIB':
            sub=s.split('#@$')[1:]
            prefix=[x.split('~')[12] for x in sub if x.startswith('T~P~')]
            assert len(prefix)==1,sub
            ref=prefix[0]
            for x in sub:
                if x.startswith('P~'):
                    conf=x.split('^^')[0].split('~')
                    key=(ref,conf[3]);assert key not in pins,key
                    pins[key]=point(conf[4],conf[5])
        elif fields[0]=='W':
            coords=list(map(float,fields[1].split()))
            ps=[point(*coords[n:n+2]) for n in range(0,len(coords),2)]
            seg.extend(zip(ps,ps[1:]))
        elif fields[0]=='N':
            p=point(fields[1],fields[2]);labels.append((p,fields[5]));join(p,('net',fields[5]))
        elif fields[0]=='J':point(fields[1],fields[2])
    for a,b in seg:
        assert a[1]==b[1] or a[2]==b[2],(a,b)
        for p in points:
            if (a[1]==b[1]==p[1] and min(a[2],b[2])<=p[2]<=max(a[2],b[2])) or (a[2]==b[2]==p[2] and min(a[1],b[1])<=p[1]<=max(a[1],b[1])):
                join(a,p)
assert set(pins)==set(expected),(set(expected)-set(pins),set(pins)-set(expected))
groups=defaultdict(list)
for key,p in pins.items():groups[find(p)].append(key)
for keys in groups.values():
    netset={expected[k] for k in keys}
    assert len(netset)==1,('SHORT',netset,keys)
    net=next(iter(netset))
    wanted={k for k,v in expected.items() if v==net}
    assert set(keys)==wanted,('OPEN',net,keys,wanted-set(keys))
for p,label in labels:
    for key in groups.get(find(p),[]):
        assert expected[key]==label,('WRONG LABEL',label,key,expected[key])
print(f'PASS: {len(pins)} CAD pins match {len(set(expected.values()))} canonical nets; no opens or shorts found.')
