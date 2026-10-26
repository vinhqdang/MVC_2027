import sys, re, math, html, os
sys.path.insert(0, '/tmp/claude-0/work')
from parse import load

WS = {}
for ln in open('/tmp/claude-0/work/ws.txt'):
    k, v = ln.split('=')
    WS[k.strip()] = float(v)
PARAM_USED = set()
WS.update({'Slip.th': 0.05, 'Slip.k': 10.0, 'Slip.vmin': 1.0, 'Steer.Kd': 0.0})

SKIP = {'Scope', 'Display', 'Terminator', 'Record'}


def cname(n):
    return n.replace('.', '_')


def expr2c(e):
    e = e.strip()
    def sub(m):
        tok = m.group(0)
        if re.fullmatch(r'\d+(\.\d*)?([eE][-+]?\d+)?', tok):
            return tok if ('.' in tok or 'e' in tok.lower()) else tok + '.0'
        PARAM_USED.add(tok)
        return 'P_' + cname(tok)
    # numbers with exponent handled: tokenise
    out = re.sub(r'[A-Za-z_][A-Za-z_0-9\.]*|\d+\.?\d*(?:[eE][-+]?\d+)?', sub, e)
    out = out.replace('^', '**')
    return '(' + out + ')'


def vecexpr(e):
    e = e.strip()
    if e.startswith('['):
        return [expr2c(x) for x in e.strip('[]').split()]
    return [expr2c(e)]


class Ctx:
    def __init__(s):
        s.code = []
        s.nv = 0
        s.nx = 0
        s.nd = 0
        s.pending = []     # thunks producing derivative statements
        s.mem = []         # (d idx, thunk)
        s.logs = {}
        s.gotos = {}       # global tag -> (inst, sid)

    def var(s):
        s.nv += 1
        return 'v%d' % s.nv

    def emit(s, e):
        v = s.var()
        s.code.append('double %s = %s;' % (v, e))
        return v


class Inst:
    def __init__(s, ctx, sysname, path, parent=None, inport_fn=None):
        s.ctx = ctx
        s.path = path
        s.blocks, lines = load(sysname)
        s.src = {}
        for a, b in lines:
            s.src[b] = a
        s.memo = {}
        s.inport_fn = inport_fn
        s.children = {}
        s.local_goto = {}
        for sid, o in s.blocks.items():
            if o.type == 'Goto':
                tag = o.p['GotoTag']
                s.local_goto[tag] = sid
                if o.p.get('TagVisibility', 'local') == 'global':
                    ctx.gotos[tag] = (s, sid)
        for sid, o in s.blocks.items():
            if o.type == 'SubSystem':
                def mk(sid=sid):
                    return lambda k: s.inp(sid, k)
                s.children[sid] = Inst(ctx, o.sub, path + '/' + o.name, s, mk())

    def inp(s, sid, n):
        key = '%s#in:%d' % (sid, n)
        a = s.src[key]
        sid2, port = a.split('#out:')
        return s.out(sid2, int(port))

    def ninp(s, sid):
        o = s.blocks[sid]
        return o.nin

    def out(s, sid, port):
        key = (sid, port)
        if key in s.memo:
            r = s.memo[key]
            if r is None:
                raise RuntimeError('algebraic loop at %s/%s' % (s.path, s.blocks[sid].name))
            return r
        s.memo[key] = None
        r = s.eval(sid, port)
        s.memo[key] = r
        return r

    def getall(s, sid):
        o = s.blocks[sid]
        return [s.inp(sid, k) for k in range(1, (o.nin or 0) + 1)]

    def eval(s, sid, port):
        c = s.ctx
        o = s.blocks[sid]
        t = o.type
        p = o.p
        if t == 'Inport':
            return s.inport_fn(int(p.get('Port', '1')))
        if t == 'Constant':
            return [c.emit(x) for x in vecexpr(p['Value'])]
        if t == 'Ground':
            return [c.emit('0')]
        if t == 'Clock':
            return [c.emit('t')]
        if t == 'Gain':
            u = s.inp(sid, 1)
            g = expr2c(p['Gain'])
            return [c.emit('%s*%s' % (g, x)) for x in u]
        if t == 'Sum':
            sg = p.get('Inputs', '++')
            sg = sg.replace('|', '')
            if sg.isdigit():
                sg = '+' * int(sg)
            ins = [s.inp(sid, k + 1) for k in range(len(sg))]
            w = max(len(i) for i in ins)
            res = []
            for j in range(w):
                ex = ''
                for sgn, i in zip(sg, ins):
                    x = i[j] if len(i) > 1 else i[0]
                    ex += ('+' if sgn == '+' else '-') + x
                res.append(c.emit(ex))
            return res
        if t == 'Product':
            sg = p.get('Inputs', '2')
            if sg.isdigit():
                sg = '*' * int(sg)
            ins = [s.inp(sid, k + 1) for k in range(len(sg))]
            w = max(len(i) for i in ins)
            res = []
            for j in range(w):
                ex = '1.0'
                for sgn, i in zip(sg, ins):
                    x = i[j] if len(i) > 1 else i[0]
                    ex += ('*' if sgn == '*' else '/') + '(' + x + ')'
                res.append(c.emit(ex))
            return res
        if t == 'Math':
            u = s.inp(sid, 1)
            op = p['Operator']
            f = {'sqrt': 'sqrt(%s)', 'square': '(%s)*(%s)'}[op]
            return [c.emit(f.replace('%s', x)) for x in u]
        if t == 'Trigonometry':
            op = p.get('Operator', 'sin')
            if op == 'atan2':
                a, b = s.inp(sid, 1), s.inp(sid, 2)
                return [c.emit('atan2(%s,%s)' % (a[0], b[0]))]
            u = s.inp(sid, 1)
            return [c.emit('%s(%s)' % (op, x)) for x in u]
        if t == 'Abs':
            return [c.emit('fabs(%s)' % x) for x in s.inp(sid, 1)]
        if t == 'MinMax':
            ins = s.getall(sid)
            fn = 'fmax' if p['Function'] == 'max' else 'fmin'
            ex = ins[0][0]
            for i in ins[1:]:
                ex = '%s(%s,%s)' % (fn, ex, i[0])
            return [c.emit(ex)]
        if t == 'Saturate':
            ub, lb = expr2c(p['UpperLimit']), expr2c(p['LowerLimit'])
            if s.path.endswith('Velocity pattern'):
                nm = 'SAT_%s' % sid
                WS[nm + '_ub'] = float(p['UpperLimit']); WS[nm + '_lb'] = float(p['LowerLimit'])
                PARAM_USED.add(nm + '_ub'); PARAM_USED.add(nm + '_lb')
                ub, lb = 'P_' + nm + '_ub', 'P_' + nm + '_lb'
            return [c.emit('fmin(fmax(%s,%s),%s)' % (x, lb, ub)) for x in s.inp(sid, 1)]
        if t == 'Switch':
            a, b, d = s.inp(sid, 1), s.inp(sid, 2), s.inp(sid, 3)
            th = expr2c(p.get('Threshold', '0'))
            op = {'u2 > Threshold': '>', 'u2 >= Threshold': '>=', 'u2 ~= 0': '!='}[p.get('Criteria', 'u2 >= Threshold')]
            if op == '!=':
                th = '0'
            return [c.emit('((%s) %s %s ? (%s) : (%s))' % (b[0], op, th, x, y)) for x, y in zip(a, d)]
        if t == 'Mux':
            r = []
            for i in s.getall(sid):
                r += i
            return r
        if t == 'Demux':
            u = s.inp(sid, 1)
            n = o.nout if o.nout else int(p['Outputs'])
            w = len(u) // n
            assert w * n == len(u), (s.path, o.name, len(u), n)
            return u[(port - 1) * w:port * w]
        if t == 'Memory':
            n = None
            i = c.nd; c.nd += 1
            def th(i=i, s=s, sid=sid):
                u = s.inp(sid, 1)
                c.code.append('Dn[%d] = %s;' % (i, u[0]))
            c.pending.append(th)
            return [c.emit('D[%d]' % i)]
        if t == 'Integrator':
            i = c.nx; c.nx += 1
            c.inits.append((i, expr2c(p.get('InitialCondition', '0'))))
            def th(i=i, s=s, sid=sid):
                u = s.inp(sid, 1)
                c.code.append('dX[%d] = %s;' % (i, u[0]))
            c.pending.append(th)
            return [c.emit('X[%d]' % i)]
        if t == 'TransferFcn':
            num = [float(eval(expr2c(x).replace('P_', 'WSP_'), {}, WSNS)) for x in p.get('Numerator', '[1]').strip('[]').split()]
            den = [float(eval(expr2c(x).replace('P_', 'WSP_'), {}, WSNS)) for x in p['Denominator'].strip('[]').split()]
            assert len(den) == 2
            if len(num) == 1:
                num = [0.0, num[0]]
            n1, n0 = num
            d1, d0 = den
            i = c.nx; c.nx += 1
            c.inits.append((i, '0'))
            def th(i=i, s=s, sid=sid, d0=d0, d1=d1):
                u = s.inp(sid, 1)
                c.code.append('dX[%d] = (%s-(%.17g)*X[%d])/(%.17g);' % (i, u[0], d0, i, d1))
            c.pending.append(th)
            if n1 == 0:
                return [c.emit('(%.17g)*X[%d]' % (n0 - n1 * d0 / d1, i))]
            u = s.inp(sid, 1)
            return [c.emit('(%.17g)*%s + (%.17g)*X[%d]' % (n1 / d1, u[0], n0 - n1 * d0 / d1, i))]
        if t == 'Reference':
            q = o.xml.find('InstanceData')
            ip = {pp.get('Name'): pp.text for pp in q.findall('P')}
            slope, start, ic = float(ip['slope']), float(ip['start']), float(ip['InitialOutput'])
            nm = 'RAMP_%s' % sid
            WS[nm + '_slope'] = slope; WS[nm + '_start'] = start
            PARAM_USED.add(nm + '_slope'); PARAM_USED.add(nm + '_start')
            return [c.emit('(t>P_%s_start ? %.17g+P_%s_slope*(t-P_%s_start) : %.17g)' % (nm, ic, nm, nm, ic))]
        if t == 'From':
            tag = p['GotoTag']
            if tag in s.local_goto:
                g = (s, s.local_goto[tag])
            else:
                g = c.gotos[tag]
            return g[0].inp(g[1], 1)
        if t == 'SubSystem':
            ch = s.children[sid]
            # find Outport with Port==port
            for osid, ob in ch.blocks.items():
                if ob.type == 'Outport' and int(ob.p.get('Port', '1')) == port:
                    return ch.inp(osid, 1)
            raise RuntimeError('no outport')
        if t == 'S-Function':
            tag = p['Tag']
            ins = s.getall(sid)
            return sf_call(c, tag, [i[0] for i in ins], port)
        if t == 'M-S-Function':
            u = s.inp(sid, 1)
            vs = [c.var() for _ in range(3)]
            c.code.append('double %s,%s,%s; lambda_method(%s,%s,%s,%s,%s,&%s,&%s,&%s);' % (
                vs[0], vs[1], vs[2], u[0], u[1], u[2], u[3], u[4], vs[0], vs[1], vs[2]))
            return vs
        if t == 'ToWorkspace':
            return None
        raise RuntimeError('unsupported ' + t + ' ' + o.name)

    def visit_logs(s):
        for sid, o in s.blocks.items():
            if o.type == 'ToWorkspace':
                s.ctx.logs[o.p['VariableName']] = s.inp(sid, 1)[0]
            if o.type == 'SubSystem':
                s.children[sid].visit_logs()


def sf_call(c, tag, ins, port):
    # outputs: port 1 dummy, rest real
    if tag.endswith('1'):
        # longitudinal misalignment
        return [c.emit('sf_longmis(%s)' % ins[0])]
    if tag.endswith('3'):
        v = c.emit('sf_dwpt(%s,%s)' % (ins[0], ins[1]))
        return [v]
    # 2: wheel velocity and slip angle
    key = 'sf2_' + '_'.join(ins)
    if key not in c.sfmemo:
        vs = [c.var() for _ in range(8)]
        c.code.append('double %s; sf_wheelvel(%s,%s);' % (','.join(vs), ','.join(ins), ','.join('&' + v for v in vs)))
        c.sfmemo[key] = vs
    vs = c.sfmemo[key]
    return [vs[port - 2]]


class WSObj:
    pass


WSNS = {}
for k, v in WS.items():
    WSNS['WSP_' + cname(k)] = v


def build():
    pass
    c = Ctx()
    c.inits = []
    c.sfmemo = {}
    root = Inst(c, 'system_root', '', None, None)
    root.visit_logs()
    while c.pending:
        th = c.pending.pop(0)
        th()
    return c, root


import numpy as np
xx = [-400,-350,-300,-250,-200,-150,-100,-50,0,50,100,150,200,250,300,350,400]
z000=[18.366,18.12075,18.2285,18.62175,19.4505,22.78625,21.99725,18.1625,12.584]
z050=[16.16075,15.495,15.44675,15.71575,18.70275,19.3575,18.8615,15.5565,10.6605]
z100=[9.85675,9.60925,10.05325,10.28375,11.30575,13.352,13.16575,10.59525,6.935]
z150=[4.81875,4.1325,4.1535,5.24425,6.22225,7.28925,6.64025,5.4515,3.44175]
def _row(z):
    f=list(reversed(z)); del f[8]; return f+z
ZZ=[_row(z150),_row(z100),_row(z050),_row(z000),_row(z050),_row(z100),_row(z150)]

HELPERS = r'''
#include <math.h>
#include <stdlib.h>
#include <string.h>
static void lambda_method(double V,double Vw,double alpha,double mu,double Fz,double*oFx,double*oFy,double*olam){
  double Fx,Fy,lx; double B=10,C=1.9,D=1,E=0.97;
  if (fabs(V)<0.05){
    if (fabs(Vw)<0.05){lx=0;Fx=0;Fy=0;}
    else{ lx=1.0; double t1=B*(1-E)*1+E*atan(B*1); double t2=C*atan(t1); Fx=D*sin(t2)*mu*Fz; Fy=0;}
  } else {
    double Vv1=cos(alpha)*V, Vv2=sin(alpha)*V;
    double Vs1=Vw-Vv1, Vs2=-Vv2;
    double nV=sqrt(Vv1*Vv1+Vv2*Vv2), nW=fabs(Vw);
    double den=fmax(nV,nW);
    double l1=Vs1/den,l2=Vs2/den;
    double nl=sqrt(l1*l1+l2*l2); if(nl>1.0)nl=1.0;
    if (fabs(Vs1)<1e-6){lx=0;Fx=0;Fy=0;}
    else{
      lx=Vs1/fmax(fabs(Vv1),fabs(Vw));
      if(fabs(lx)>1.0) lx = lx>0?1.0:-1.0;
      double t1=B*(1-E)*nl+E*atan(B*nl); double t2=C*atan(t1);
      double nVs=sqrt(Vs1*Vs1+Vs2*Vs2);
      double Fm=mu*Fz*D*sin(t2);
      Fx=Fm*Vs1/nVs; Fy=Fm*Vs2/nVs;
    }
  }
  *oFx=Fx;*oFy=Fy;*olam=lx;
}
static double sf_longmis(double u){
  double delta=-0.4;
  if (u<=500.1) delta=-0.4;
  if (u>=1498.9) delta=0.4;
  if (u>500.1 && u<1498.9){
    for(int i=1;i<=500;i++){ double pc=500.5+2*(i-1); double dx=u-pc; if(fabs(dx)<0.4) delta=dx; }
  }
  return delta;
}
static const double XX[17]={%XX%};
static const double YY[7]={-150,-100,-50,0,50,100,150};
static const double ZZ[7][17]={%ZZ%};
static double sf_dwpt(double u1,double u2){
  double L1=142.326e-6,L2=54.2047e-6,R1=85.02/1000,R2=39.88/1000,f=85000;
  double w=2*3.14159265358979323846*f, Q1=w*L1/R1, Q2=w*L2/R2;
  double eta=0;
  if (fabs(u1)<=380 && fabs(u2)<=70){
    int i=0; while(i<15 && u1>=XX[i+1]) i++;
    int j=0; while(j<5 && u2>=YY[j+1]) j++;
    double tx=(u1-XX[i])/(XX[i+1]-XX[i]), ty=(u2-YY[j])/(YY[j+1]-YY[j]);
    double Lm=1e-6*((1-ty)*((1-tx)*ZZ[j][i]+tx*ZZ[j][i+1])+ty*((1-tx)*ZZ[j+1][i]+tx*ZZ[j+1][i+1]));
    double k=Lm/sqrt(L1*L2);
    eta=k*k*Q1*Q2/((1+sqrt(1+Q1*Q2*k*k))*(1+sqrt(1+Q1*Q2*k*k)));
  }
  return eta;
}
static void sf_wheelvel(double delta_f,double beta,double V,double gamma,double delta_r,double df,double dr,double lf,double lr,
  double*V_fr,double*V_fl,double*V_rr,double*V_rl,double*a_fr,double*a_fl,double*a_rr,double*a_rl){
  double sb=V*sin(beta), cb=V*cos(beta);
  *V_fl=sqrt(pow(sb+gamma*lf,2)+pow(cb-gamma*df/2,2));
  *V_fr=sqrt(pow(sb+gamma*lf,2)+pow(cb+gamma*df/2,2));
  *V_rl=sqrt(pow(sb-gamma*lr,2)+pow(cb-gamma*dr/2,2));
  *V_rr=sqrt(pow(sb-gamma*lr,2)+pow(cb+gamma*dr/2,2));
  *a_fl=atan((sb+gamma*lf)/(cb-gamma*df/2))-delta_f;
  *a_fr=atan((sb+gamma*lf)/(cb+gamma*df/2))-delta_f;
  *a_rl=atan((sb-gamma*lr)/(cb-gamma*dr/2))-delta_r;
  *a_rr=atan((sb-gamma*lr)/(cb+gamma*dr/2))-delta_r;
}
'''

def emit_c(path, c, extra_params=(), pdef='/tmp/claude-0/work/pdef.json'):
    names = sorted(PARAM_USED | set(extra_params))
    out = [HELPERS.replace('%XX%', ','.join(str(x) for x in xx)).replace('%ZZ%', ','.join('{' + ','.join(repr(v) for v in r) + '}' for r in ZZ))]
    for n in names:
        out.append('static double P_%s = %r;' % (cname(n), WS.get(n, 0.0)))
    import json; json.dump({n: WS.get(n, 0.0) for n in names}, open(pdef, 'w'))
    out.append('const char* PNAMES = "%s";' % ' '.join(names))
    out.append('int NP = %d;' % len(names))
    out.append('static double* PTR[] = {%s};' % ','.join('&P_' + cname(n) for n in names))
    lognames = sorted(c.logs)
    out.append('const char* LNAMES = "%s";' % ' '.join(lognames))
    out.append('int NL = %d;' % len(lognames))
    out.append('#define NX %d\n#define ND %d' % (c.nx, c.nd))
    out.append('static void evalf(double t,const double*X,const double*D,double*dX,double*Dn,double*L){')
    out += c.code
    for i, n in enumerate(lognames):
        out.append('L[%d]=%s;' % (i, c.logs[n]))
    out.append('}')
    inits = ';'.join('X[%d]=%s' % (i, e) for i, e in c.inits)
    out.append('static void init(double*X){ %s; }' % inits)
    out.append(DRIVER.replace('%LIDX%', '\n'.join('#define LI_%s %d' % (n, i) for i, n in enumerate(lognames))))
    open(path, 'w').write('\n'.join(out))

DRIVER = r'''
%LIDX%
/* returns: out[0..3]=Phi1..4 raw, out[4]=max|Y|, out[5]=final X, out[6]=min Vx after 10 s, out[7]=ok flag */
double XF[NX];
int run(const double* pv, double* out, double* logbuf, int decim, double Tsim, double Ts){
  for(int i=0;i<NP;i++) *PTR[i]=pv[i];
  double X[NX],Xs[NX],k1[NX],k2[NX],k3[NX],D[ND],Dn[ND],Dm[ND],L[NL],Ld[NL];
  memset(D,0,sizeof D);
  init(X);
  long N=(long)floor(Tsim/Ts+0.5);
  double e1=0,e2=0,e3=0,e4=0,maxy=0,minv=1e9; double tt=0;
  long nlog=0;
  for(long k=0;k<=N;k++){
    double t=k*Ts;
    evalf(t,X,D,k1,Dn,L); memcpy(Dm,Dn,sizeof Dn);
    e1+=L[LI_P_in]; 
    e2+=L[LI_lambda_FL]*L[LI_lambda_FL]+L[LI_lambda_FR]*L[LI_lambda_FR]+L[LI_lambda_RL]*L[LI_lambda_RL]+L[LI_lambda_RR]*L[LI_lambda_RR];
    double eta=L[LI_DWPT_efficient]/100.0; e3+=(1-eta)*(1-eta);
    e4+=L[LI_ay]*L[LI_ay];
    if (fabs(L[LI_Pos_Y])>maxy) maxy=fabs(L[LI_Pos_Y]);
    if (t>10 && L[LI_Vx]<minv) minv=L[LI_Vx];
    if (!(maxy<1e6)) { out[7]=0; break; }
    if (logbuf && (k%decim)==0){ for(int i=0;i<NL;i++) logbuf[nlog*NL+i]=L[i]; nlog++; }
    if (k==N) break;
    for(int i=0;i<NX;i++) Xs[i]=X[i]+0.5*Ts*k1[i];
    evalf(t+0.5*Ts,Xs,D,k2,Dn,Ld);
    for(int i=0;i<NX;i++) Xs[i]=X[i]+0.75*Ts*k2[i];
    evalf(t+0.75*Ts,Xs,D,k3,Dn,Ld);
    for(int i=0;i<NX;i++) X[i]+=Ts*(2.0/9*k1[i]+1.0/3*k2[i]+4.0/9*k3[i]);
    memcpy(D,Dm,sizeof D);
  }
  memcpy(XF,X,sizeof X);
  out[0]=e1*Ts/3600; out[1]=e2*Ts; out[2]=e3*Ts; out[3]=e4*Ts; out[4]=maxy; out[5]=L[LI_Pos_X]; out[6]=minv; out[7]=1;
  return (int)nlog;
}
'''
