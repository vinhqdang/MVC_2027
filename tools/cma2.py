import sys, json, time, numpy as np
sys.path.insert(0,'/tmp/claude-0/work')
import opt
opt.TAG='slxv2'
opt.SCEN.update({'wind3':{'Wind.force':3000.0,'Wind.moment':300.0,'Wind.time_start':20.0,'Wind.time_stop':40.0},
 'v28':{'SAT_4950_ub':25.0,'SAT_4950_lb':-25.0,'SAT_5571_ub':25.0,'SAT_5571_lb':-25.0},
 'ice2':{'Road.Mu_l':0.12,'Road.L_in':12.5,'Road.L_out':60.0}})
from opt import *
import cma
iters=int(sys.argv[1]); out=sys.argv[2]
VARS=[('Slip.th',0.01,0.15,0),('Slip.k',5,80,1),('tdisF',0.2,0.45,0),('Steer.Kp_pos',0.1,2.0,1),('Steer.Kp_yaw',0.5,4.0,1),('Steer.Kd',0.0,1.5,0),('Slip.vmin',0.3,3.0,1)]
X0=[0.26,0.9,0.52,0.6,0.55,0.15,0.5]
NAMES=('ex','alt1','alt2','wind3','ice2','v28')
XMIN={'ex':2000,'alt1':2000,'alt2':2025,'wind3':2000,'ice2':2000,'v28':2500}
def to_over(x):
    o={'flag.DYC':0,'flag.current':1}
    for (n,lo,hi,lg),u in zip(VARS,x):
        u=min(max(u,0),1)
        o[n]=float(np.exp(np.log(lo)+u*(np.log(hi)-np.log(lo))) if lg else lo+u*(hi-lo))
    f=o.pop('tdisF'); o['tdis_FR']=f; o['tdis_FL']=f; o['tdis_RR']=0.5-f; o['tdis_RL']=0.5-f
    return o
def cost(pool,x):
    r=evaluate(pool,to_over(x),NAMES); c=0
    for n,(oo,p) in r.items():
        if n=='v28':
            c+= 0 if (oo[4]<1.0 and oo[5]>=XMIN[n]) else 1e4
            continue
        pen=0
        if oo[4]>3 or oo[5]<XMIN[n] or not np.isfinite(p): pen=1e4
        c+=min(p,1e5)+pen
    return c/5
if __name__=='__main__':
    pool=make_pool('slxv2',4)
    es=cma.CMAEvolutionStrategy(X0,0.15,{'popsize':8,'seed':5,'bounds':[0,1],'verbose':-9})
    best=(1e99,None); t0=time.time()
    for it in range(iters):
        xs=es.ask(); cs=[cost(pool,x) for x in xs]; es.tell(xs,cs)
        i=int(np.argmin(cs))
        if cs[i]<best[0]: best=(cs[i],list(xs[i]))
        print(it,round(best[0],2),round(min(cs),2),round(time.time()-t0),flush=True)
        json.dump({'cost':best[0],'x':best[1],'over':to_over(best[1])},open(out,'w'))
