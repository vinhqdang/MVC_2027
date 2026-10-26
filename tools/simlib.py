import ctypes, numpy as np, json
SIG = [1, 60, 3, 10]
class Sim:
    def __init__(s, tag='orig'):
        s.lib = ctypes.CDLL('/tmp/claude-0/work/sim_%s.so' % tag)
        s.PN = ctypes.c_char_p.in_dll(s.lib, 'PNAMES').value.decode().split()
        s.LN = ctypes.c_char_p.in_dll(s.lib, 'LNAMES').value.decode().split()
        s.WS = json.load(open('/tmp/claude-0/work/pdef_%s.json' % tag))
        s.WS.setdefault('Sim.Ts', 0.0002); s.WS.setdefault('Sim.Tsim', 120.0)
        s.lib.run.argtypes = [ctypes.POINTER(ctypes.c_double)] * 3 + [ctypes.c_int, ctypes.c_double, ctypes.c_double]
    def run(s, over=None, logs=False, decim=50, strategy=None, tsim=None):
        ws = dict(s.WS)
        if strategy == 1: ws['flag.DYC'] = 0; ws['flag.current'] = 0
        if strategy == 2: ws['flag.DYC'] = 1; ws['flag.current'] = 1
        if over: ws.update(over)
        if not (over and 'tdis_RL' in over):
            ws['tdis_RL'] = 1 - (ws['tdis_FR'] + ws['tdis_FL'] + ws['tdis_RR'])
        pv = np.array([ws[n] for n in s.PN], dtype=np.float64)
        out = np.zeros(8)
        Ts = ws['Sim.Ts']; Tsim = tsim or ws['Sim.Tsim']
        P = lambda a: a.ctypes.data_as(ctypes.POINTER(ctypes.c_double))
        NL = len(s.LN)
        if logs:
            n = int(Tsim / Ts / decim) + 2
            buf = np.zeros(n * NL)
            k = s.lib.run(P(pv), P(out), P(buf), decim, Tsim, Ts)
            L = {nm: buf[:k * NL].reshape(k, NL)[:, i] for i, nm in enumerate(s.LN)}
        else:
            s.lib.run(P(pv), P(out), None, 1, Tsim, Ts); L = None
        return out, float(np.dot(SIG, out[:4])), L
def show(out, phi):
    return 'Phi1..4 %s maxY %.2f X %.0f minV %.2f  PHI %.2f' % (np.round(out[:4], 3), out[4], out[5], out[6], phi)
if __name__ == '__main__':
    import sys
    sm = Sim(sys.argv[1] if len(sys.argv) > 1 else 'orig')
    for st in (1, 2):
        o, p, _ = sm.run(strategy=st); print(st, show(o, p))
