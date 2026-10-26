import re, xml.etree.ElementTree as ET, os
D=os.environ.get('SLXSYS','/tmp/claude-0/slx/simulink/systems/')
class Blk: pass
def load(name):
    t=ET.parse(D+name+'.xml').getroot()
    blocks={}; lines=[]
    for b in t.findall('Block'):
        o=Blk(); o.type=b.get('BlockType'); o.name=b.get('Name'); o.sid=b.get('SID')
        o.p={p.get('Name'):(p.text or '') for p in b.findall('P')}
        pc=b.find('PortCounts'); o.nin=int(pc.get('in',0)) if pc is not None else None
        o.nout=int(pc.get('out',0)) if pc is not None else None
        s=b.find('System'); o.sub=s.get('Ref') if s is not None else None
        o.xml=b
        blocks[o.sid]=o
    def walk2(br,s):
        for p in br.findall('P'):
            if p.get('Name')=='Dst': lines.append((s,p.text))
        for sub in br.findall('Branch'): walk2(sub,s)
    for l in t.findall('Line'):
        s=None
        for p in l.findall('P'):
            if p.get('Name')=='Src': s=p.text
        walk2(l,s)
    return blocks,lines
