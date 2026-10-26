import sys, os, subprocess, json
tag = sys.argv[1] if len(sys.argv) > 1 else 'orig'
if tag != 'orig': os.environ['SLXSYS'] = '/tmp/claude-0/work/%s/simulink/systems/' % tag
sys.path.insert(0, '/tmp/claude-0/work')
import gen
c, r = gen.build()
gen.emit_c('/tmp/claude-0/work/sim_%s.c' % tag, c, pdef='/tmp/claude-0/work/pdef_%s.json' % tag)
subprocess.check_call('gcc -O2 -shared -fPIC -o /tmp/claude-0/work/sim_%s.so /tmp/claude-0/work/sim_%s.c -lm' % (tag, tag), shell=True)
print('built', tag, c.nx, c.nd, len(c.code))
