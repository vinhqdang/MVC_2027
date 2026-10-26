import sys, os, shutil
sys.path.insert(0, '/tmp/claude-0/work')
import xml.etree.ElementTree as ET
from dsl import Sys
import mk_slip

def make(dst='/tmp/claude-0/work/slxv2'):
    S = mk_slip.make(dst) if False else None
    # reuse mk_slip to build base into dst
    base = mk_slip.make(dst)
    # steering damping subsystem: -Steer.Kd * gamma
    g = Sys(9200)
    sen = g.inport('Sensor')
    dm = g.demux('Sensor demux', 12, sen)
    k = g.gain('yaw rate damping', '-Steer.Kd', (dm, 1))
    g.outport('delta_damp', k)
    g.save(base + 'system_9200.xml')
    tree = ET.parse(base + 'system_4486.xml'); root = tree.getroot()
    # remove line 6111#out:5 -> 4467
    for ln in list(root.findall('Line')):
        src = [p.text for p in ln.findall('P') if p.get('Name') == 'Src'][0]
        if src == '6111#out:5': root.remove(ln)
        if src == '4485#out:1': root.remove(ln)
    def blk(typ, name, sid, pc, params, sub=None):
        b = ET.SubElement(root, 'Block', BlockType=typ, Name=name, SID=sid)
        if pc: ET.SubElement(b, 'PortCounts', pc)
        ET.SubElement(b, 'P', Name='Position').text = '[430, 300, 470, 340]'
        ET.SubElement(b, 'P', Name='ZOrder').text = '100000'
        for kk, v in params.items(): ET.SubElement(b, 'P', Name=kk).text = v
        if sub: ET.SubElement(b, 'System', Ref=sub)
    blk('SubSystem', 'Steering damping', '9199', {'in': '1', 'out': '1'}, {}, 'system_9200')
    blk('Sum', 'Add delta', '9198', {'in': '2', 'out': '1'}, {'IconShape': 'rectangular', 'Inputs': '++'})
    def line(src, dsts):
        le = ET.SubElement(root, 'Line')
        ET.SubElement(le, 'P', Name='Src').text = src
        if len(dsts) == 1: ET.SubElement(le, 'P', Name='Dst').text = dsts[0]
        else:
            for d in dsts:
                br = ET.SubElement(le, 'Branch'); ET.SubElement(br, 'P', Name='Dst').text = d
    line('4485#out:1', ['6243#in:1', '6111#in:1', '9099#in:1', '9199#in:1'])
    line('6111#out:5', ['9198#in:1'])
    line('9199#out:1', ['9198#in:2'])
    line('9198#out:1', ['4467#in:1'])
    ET.indent(root, space='  ')
    tree.write(base + 'system_4486.xml', encoding='utf-8', xml_declaration=True)
    return base
if __name__ == '__main__': print(make())
