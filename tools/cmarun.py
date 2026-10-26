import sys, json, time, numpy as np
sys.path.insert(0,'/tmp/claude-0/work')
from opt import *
import cma
tag=sys.argv[1]; iters=int(sys.argv[2]); out=sys.argv[3]
# variable spec: name, lo, hi, log?
VARS=[('Slip.th',0.01,0.15,0),('Slip.k',2,60,1),('tdisF',0.2,0.45,0),('Steer.Kp_pos',0.003,0.15,1),('Steer.Kp_yaw',0.05,1.0,1)]
XMIN={'ex':2000,'alt1':2000,'alt2':2025}
def to_over(x):
    o={'flag.DYC':0,'flag.current':1}
    for (n,lo,hi,lg),u in zip(VARS,x):
        u=min(max(u,0),1)
        v=np.exp(np.log(lo)+u*(np.log(hi)-np.log(lo))) if lg else lo+u*(hi-lo)
        o[n]=v
    f=o.pop('tdisF'); o['tdis_FR']=f; o['tdis_FL']=f; o['tdis_RR']=0.5-f; o['tdis_RL']=0.5-f
    return o
def cost(pool,x):
    o=to_over(x); r=evaluate(pool,o)
    c=0
    for n,(oo,p) in r.items():
        pen=0
        if oo[4]>4.5 or oo[5]<XMIN[n] or not np.isfinite(p): pen=1e4+max(0,XMIN[n]-oo[5])*10
        c+=min(p,1e5)+pen
    return c/len(r)
if __name__=='__main__':
    pool=make_pool(tag,4)
    es=cma.CMAEvolutionStrategy([0.3]*len(VARS),0.3,{'popsize':8,'seed':3,'bounds':[0,1],'verbose':-9})
    best=(1e99,None); t0=time.time()
    for it in range(iters):
        xs=es.ask()
        cs=[cost(pool,x) for x in xs]
        es.tell(xs,cs)
        i=int(np.argmin(cs))
        if cs[i]<best[0]: best=(cs[i],list(xs[i]))
        print(it,round(best[0],2),round(min(cs),2),round(time.time()-t0),flush=True)
        json.dump({'cost':best[0],'x':best[1],'over':to_over(best[1])},open(out,'w'))
