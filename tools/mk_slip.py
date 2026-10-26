import sys, os, shutil, re
sys.path.insert(0, '/tmp/claude-0/work')
import xml.etree.ElementTree as ET
from dsl import Sys

def make(dst='/tmp/claude-0/work/slxmod'):
    if os.path.exists(dst): shutil.rmtree(dst)
    shutil.copytree('/tmp/claude-0/slx', dst)
    S = os.path.join(dst, 'simulink/systems/')
    # ---- slip control subsystem
    g = Sys(9100)
    sen = g.inport('Sensor')
    tin = [g.inport(n) for n in ('T_FR', 'T_FL', 'T_RR', 'T_RL')]
    dm = g.demux('Sensor demux', 12, sen)
    gamma, Vx = (dm, 1), (dm, 9)
    wh = {'FR': ((dm, 5), +1), 'FL': ((dm, 6), -1), 'RR': ((dm, 7), +1), 'RL': ((dm, 8), -1)}
    zero = g.const('zero', '0'); one = g.const('one', '1')
    vmin = g.const('vmin', 'Slip.vmin'); th = g.const('slip threshold', 'Slip.th')
    outs = []
    for (name, (w, sgn)), t in zip(wh.items(), tin):
        Vw = g.gain('Vw_' + name, 'Wheel.R', w)
        corr = g.gain('yawcorr_' + name, '%sVehicle.d/2' % ('' if sgn > 0 else '-'), gamma)
        Vr = g.sum('Vref_' + name, '++', Vx, corr)
        aw = g.abs('abs Vw_' + name, Vw); ar = g.abs('abs Vr_' + name, Vr)
        den = g.minmax('den_' + name, 'max', aw, ar, vmin)
        sl = g.sum('slip diff_' + name, '+-', Vw, Vr)
        lam = g.prod('lambda_' + name, '*/', sl, den)
        al = g.abs('abs lambda_' + name, lam)
        ex = g.sum('excess_' + name, '+-', al, th)
        ex2 = g.minmax('excess+_' + name, 'max', ex, zero)
        kg = g.gain('kgate_' + name, '-Slip.k', ex2)
        gt = g.sum('gate_' + name, '++', one, kg)
        gt2 = g.minmax('gate+_' + name, 'max', gt, zero)
        outs.append(g.prod('T_lim_' + name, '**', t, gt2))
    for n, o in zip(('T_FR', 'T_FL', 'T_RR', 'T_RL'), outs): g.outport(n, o)
    g.save(S + 'system_9100.xml')
    # ---- patch top strategy system
    tree = ET.parse(S + 'system_4486.xml'); root = tree.getroot()
    # remove lines from demux 6224
    for ln in list(root.findall('Line')):
        src = [p.text for p in ln.findall('P') if p.get('Name') == 'Src'][0]
        if src.startswith('6224#out:') or src == '4485#out:1':
            root.remove(ln)
    blk = ET.SubElement(root, 'Block', BlockType='SubSystem', Name='Slip control', SID='9099')
    ET.SubElement(blk, 'PortCounts', {'in': '5', 'out': '4'})
    ET.SubElement(blk, 'P', Name='Position').text = '[420, 440, 520, 560]'
    ET.SubElement(blk, 'P', Name='ZOrder').text = '100000'
    ET.SubElement(blk, 'System', Ref='system_9100')
    def line(src, dsts):
        le = ET.SubElement(root, 'Line')
        ET.SubElement(le, 'P', Name='Src').text = src
        if len(dsts) == 1: ET.SubElement(le, 'P', Name='Dst').text = dsts[0]
        else:
            for d in dsts:
                br = ET.SubElement(le, 'Branch'); ET.SubElement(br, 'P', Name='Dst').text = d
    line('4485#out:1', ['6243#in:1', '6111#in:1', '9099#in:1'])
    for k in range(1, 5): line('6224#out:%d' % k, ['9099#in:%d' % (k + 1)])
    for k, o in zip(range(1, 5), ('4477', '4479', '4481', '4483')): line('9099#out:%d' % k, ['%s#in:1' % o])
    ET.indent(root, space='  ')
    tree.write(S + 'system_4486.xml', encoding='utf-8', xml_declaration=True)
    return S
if __name__ == '__main__':
    print(make())
