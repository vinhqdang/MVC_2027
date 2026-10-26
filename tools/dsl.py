import xml.etree.ElementTree as ET, itertools, re, os, shutil
SID0 = 9000
class Sys:
    """Builds a Simulink system XML from basic blocks."""
    def __init__(s, sidbase):
        s.sid = sidbase; s.blocks = []; s.lines = []; s.z = 0; s.n = {}
        s.inports = 0; s.outports = 0
    def _new(s):
        s.sid += 1; return str(s.sid)
    def add(s, typ, name, params=None, nin=None, nout=1, pos=None, sub=None):
        sid = s._new()
        s.blocks.append(dict(type=typ, name=name, sid=sid, params=params or {}, nin=nin, nout=nout, pos=pos, sub=sub))
        return sid
    def inport(s, name):
        s.inports += 1
        p = {'Port': str(s.inports)} if s.inports > 1 else {}
        return s.add('Inport', name, p, None, None)
    def outport(s, name, src):
        s.outports += 1
        p = {'Port': str(s.outports)} if s.outports > 1 else {}
        o = s.add('Outport', name, p, None, None)
        s.conn(src, (o, 1)); return o
    def const(s, name, val): return s.add('Constant', name, {'Value': str(val)}, None, 1)
    def gain(s, name, g, src):
        b = s.add('Gain', name, {'Gain': str(g)}, 1, 1); s.conn(src, (b, 1)); return b
    def sum(s, name, signs, *srcs):
        b = s.add('Sum', name, {'IconShape': 'rectangular', 'Inputs': signs}, len(signs), 1)
        for i, x in enumerate(srcs): s.conn(x, (b, i + 1))
        return b
    def prod(s, name, ops, *srcs):
        p = {'Inputs': ops} if ops != '**' else {}
        b = s.add('Product', name, p, len(ops), 1)
        for i, x in enumerate(srcs): s.conn(x, (b, i + 1))
        return b
    def minmax(s, name, fn, *srcs):
        b = s.add('MinMax', name, {'Function': fn, 'Inputs': str(len(srcs))}, len(srcs), 1)
        for i, x in enumerate(srcs): s.conn(x, (b, i + 1))
        return b
    def abs(s, name, src):
        b = s.add('Abs', name, {}, 1, 1); s.conn(src, (b, 1)); return b
    def sat(s, name, lo, hi, src):
        b = s.add('Saturate', name, {'UpperLimit': str(hi), 'LowerLimit': str(lo)}, 1, 1); s.conn(src, (b, 1)); return b
    def switch(s, name, u1, u2, u3, thr, crit='u2 > Threshold'):
        b = s.add('Switch', name, {'Criteria': crit, 'Threshold': str(thr)}, 3, 1)
        s.conn(u1, (b, 1)); s.conn(u2, (b, 2)); s.conn(u3, (b, 3)); return b
    def math(s, name, op, src):
        b = s.add('Math', name, {'Operator': op}, 1, 1); s.conn(src, (b, 1)); return b
    def mux(s, name, *srcs):
        b = s.add('Mux', name, {'Inputs': str(len(srcs))}, len(srcs), 1)
        for i, x in enumerate(srcs): s.conn(x, (b, i + 1))
        return b
    def demux(s, name, n, src):
        b = s.add('Demux', name, {'Outputs': str(n)}, 1, n); s.conn(src, (b, 1)); return b
    def integ(s, name, src, ic='0'):
        p = {} if ic == '0' else {'InitialCondition': ic}
        b = s.add('Integrator', name, p, 1, 1); s.conn(src, (b, 1)); return b
    def tf(s, name, num, den, src):
        b = s.add('TransferFcn', name, {'Numerator': num, 'Denominator': den}, 1, 1); s.conn(src, (b, 1)); return b
    def subsystem(s, name, ref, nin, nout):
        return s.add('SubSystem', name, {}, nin, nout, sub=ref)
    def conn(s, src, dst):
        if isinstance(src, str): src = (src, 1)
        s.lines.append((src, dst))
    def xml(s):
        root = ET.Element('System')
        ET.SubElement(root, 'P', Name='Location').text = '[100, 100, 1600, 900]'
        # simple layered layout by creation order
        for i, b in enumerate(s.blocks):
            x = 40 + (i % 14) * 110; y = 40 + (i // 14) * 70
            be = ET.SubElement(root, 'Block', BlockType=b['type'], Name=b['name'], SID=b['sid'])
            if b['nin'] is not None or b['nout'] is not None:
                if b['type'] not in ('Inport', 'Outport') :
                    pc = {}
                    if b['nin']: pc['in'] = str(b['nin'])
                    if b['nout']: pc['out'] = str(b['nout'])
                    ET.SubElement(be, 'PortCounts', **pc)
            h = 30 if b['type'] not in ('Mux', 'Demux', 'Sum', 'Product', 'MinMax', 'Switch', 'SubSystem') else max(30, 15 * max(b['nin'] or 1, b['nout'] or 1))
            ET.SubElement(be, 'P', Name='Position').text = '[%d, %d, %d, %d]' % (x, y, x + 40, y + h)
            ET.SubElement(be, 'P', Name='ZOrder').text = '100000'
            for k, v in b['params'].items():
                ET.SubElement(be, 'P', Name=k).text = v
            if b['sub']:
                ET.SubElement(be, 'System', Ref=b['sub'])
        groups = {}
        for src, dst in s.lines:
            groups.setdefault(src, []).append(dst)
        z = 0
        for src, dsts in groups.items():
            z += 1
            le = ET.SubElement(root, 'Line')
            ET.SubElement(le, 'P', Name='ZOrder').text = str(z)
            ET.SubElement(le, 'P', Name='Src').text = '%s#out:%d' % src
            if len(dsts) == 1:
                ET.SubElement(le, 'P', Name='Dst').text = '%s#in:%d' % dsts[0]
            else:
                for d in dsts:
                    z += 1
                    br = ET.SubElement(le, 'Branch')
                    ET.SubElement(br, 'P', Name='ZOrder').text = str(z)
                    ET.SubElement(br, 'P', Name='Dst').text = '%s#in:%d' % d
        ET.indent(root, space='  ')
        return ET.tostring(root, encoding='unicode')
    def save(s, path):
        open(path, 'w', encoding='utf-8').write('<?xml version="1.0" encoding="utf-8"?>\n' + s.xml() + '\n')
