import sys, json, numpy as np, multiprocessing as mp
sys.path.insert(0,'/tmp/claude-0/work')
from simlib import Sim, show
TAG='slxmod'
_sm=None
def init(tag):
    global _sm; _sm=Sim(tag)
# scenarios: dict overrides on driving condition / speed profile / wind
SCEN={
 'ex':{},
 'alt1':{'Road.Mu_l':0.35,'Road.L_in':30.0,'Road.L_out':80.0,'Wind.force':-1800.0,'Wind.time_start':60.0,'Wind.time_stop':72.0,'Wind.moment':-180.0,
         'Road.M_in':900.0,'Road.M_out':960.0,'Road.Mu_m':0.5},
 'alt2':{'Road.Mu_l':0.2,'Road.L_in':200.0,'Road.L_out':260.0,'RAMP_4949_slope':2.0,'RAMP_6031_slope':0.5,'RAMP_6031_start':30.0,'Wind.force':2200.0,'Wind.time_start':30.0,'Wind.time_stop':45.0,'Wind.moment':220.0},
}
def ev(args):
    over,name=args
    o=dict(over); o.update(SCEN[name])
    # strategy parameters take priority except scenario keys
    out,phi,_=_sm.run(dict(over,**{k:v for k,v in SCEN[name].items()}))
    return name,out,phi
def evaluate(pool,over,names=('ex','alt1','alt2')):
    res=pool.map(ev,[(over,n) for n in names])
    return {n:(o,p) for n,o,p in res}
def make_pool(tag=TAG,n=4):
    return mp.Pool(n,initializer=init,initargs=(tag,))
