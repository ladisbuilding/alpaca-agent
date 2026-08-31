"""Was our friction problem a STRATEGY problem or a STRUCTURE problem?

A Reddit thread on SPX condors makes a structural claim worth testing: sell 45 DTE, take
profit at 50%. Same four legs and the same per-leg spread as our 2-9 DTE version — but on a
credit roughly 6x larger, so the fixed toll is a far smaller share of the trade.

    SPY  2-9 DTE   spread 2.4% of mid,  median leg $0.49
    SPY 35-55 DTE  spread 1.0% of mid,  median leg $3.15

Tested against our own 2-9 DTE result on identical machinery: 2024-01 to 2026-08, friction
crossed on all four legs at entry AND exit.
"""
import sys, statistics, time
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0,"src")
from committee.market import AlpacaRest, load_dev_vars
r=AlpacaRest(load_dev_vars(Path("/Users/lukedepass/brain/active-projects/alpaca-agent")/".dev.vars"))
SPREAD={"SPY":0.030,"QQQ":0.120,"IWM":0.060}   # measured today at 35-55 DTE
WING=10; TAKE_PROFIT=0.50
def daily(sym,a,b):
    out,page=[],None
    while True:
        u=(f"{r._data}/v2/stocks/{sym}/bars?timeframe=1Day&start={a}&end={b}&limit=10000&feed=sip&adjustment=split")
        if page: u+=f"&page_token={page}"
        p=r._get(u); out+=p.get("bars") or []
        page=p.get("next_page_token")
        if not page: return out
def occ(s,e,rt,k): return f"{s}{e:%y%m%d}{rt}{int(round(k*1000)):08d}"
def bars_range(syms,a,b):
    out={}
    for i in range(0,len(syms),40):
        try:
            p=r._get(f"{r._data}/v1beta1/options/bars?symbols={','.join(syms[i:i+40])}"
                     f"&timeframe=1Day&start={a}&end={b}&limit=10000")
        except Exception: continue
        for k,v in (p.get("bars") or {}).items(): out[k]={x["t"][:10]:x["c"] for x in v}
    return out
def third_friday(y,m):
    d=date(y,m,15)
    while d.weekday()!=4: d+=timedelta(days=1)
    return d
res={}
for sym in ("SPY","QQQ","IWM"):
    bars=daily(sym,"2023-09-01","2026-08-30")
    cl={date.fromisoformat(b["t"][:10]):b["c"] for b in bars}
    days=sorted(cl); idx={d:i for i,d in enumerate(days)}
    pnls=[]
    for d0 in days:
        if d0<date(2024,1,22) or d0.weekday()!=0: continue
        exp=None
        for off in (1,2,3):
            y,m=d0.year,d0.month+off
            while m>12: y,m=y+1,m-12
            f=third_friday(y,m)
            if 35<=(f-d0).days<=55: exp=f; break
        if not exp or exp not in cl: continue
        i=idx[d0]; hist=[cl[x] for x in days[max(0,i-70):i+1]]
        if len(hist)<40: continue
        sess=int((exp-d0).days*5/7)
        rets=[(hist[j]-hist[j-sess])/hist[j-sess] for j in range(sess,len(hist))] if sess<len(hist) else []
        if len(rets)<15: continue
        sig=statistics.pstdev(rets); spot=cl[d0]
        ks=round(spot-sig*spot); kc=round(spot+sig*spot)
        legs=[occ(sym,exp,"P",ks),occ(sym,exp,"P",ks-WING),occ(sym,exp,"C",kc),occ(sym,exp,"C",kc+WING)]
        px=bars_range(legs,d0.isoformat(),exp.isoformat()); time.sleep(0.05)
        if len(px)<4: continue
        k0=d0.isoformat()
        if not all(k0 in px[l] for l in legs): continue
        credit=(px[legs[0]][k0]-px[legs[1]][k0]+px[legs[2]][k0]-px[legs[3]][k0])*100
        if credit<=0: continue
        fr=SPREAD[sym]*100*4      # one side; charged again on exit
        # walk forward: take profit at 50% of credit, else settle at expiry
        exited=None
        for dd in days[i+1:]:
            if dd>exp: break
            kk=dd.isoformat()
            if not all(kk in px[l] for l in legs): continue
            val=(px[legs[0]][kk]-px[legs[1]][kk]+px[legs[2]][kk]-px[legs[3]][kk])*100
            if val <= credit*(1-TAKE_PROFIT):
                exited=credit-val-2*fr; break
        if exited is None:
            s=cl[exp]
            loss=(max(0,ks-s)-max(0,ks-WING-s)+max(0,s-kc)-max(0,s-kc-WING))*100
            exited=credit-loss-2*fr
        pnls.append(exited)
    res[sym]=pnls
    print(f"  {sym} done ({len(pnls)})", flush=True)
print(f"\n45 DTE, take profit at 50%, friction crossed both ways (2024-01 -> 2026-08):")
for sym,v in res.items():
    if len(v)<15: print(f"  {sym}: n={len(v)} too few"); continue
    m=statistics.mean(v); sd=statistics.pstdev(v) or 1e-9
    print(f"  {sym:<5} n={len(v):>4}  mean ${m:+7.2f}/condor  win {sum(1 for x in v if x>0)/len(v):.0%}  t={m/(sd/len(v)**0.5):+5.2f}  total ${sum(v):+,.0f}")
allv=[x for v in res.values() for x in v]
if len(allv)>20:
    m=statistics.mean(allv); sd=statistics.pstdev(allv) or 1e-9
    print(f"  {'ALL':<5} n={len(allv):>4}  mean ${m:+7.2f}/condor  win {sum(1 for x in allv if x>0)/len(allv):.0%}  t={m/(sd/len(allv)**0.5):+5.2f}")
