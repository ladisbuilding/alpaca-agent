"""How far back does the data go, and does the edge decay year by year?

RSI(2) is Larry Connors' published rule from the 2000s. If it has been arbitraged away, that
should show as a year-by-year decline — which is a far cheaper question to answer than two
weeks of paper fills, and it attacks the biggest weakness in the 6-month result.
"""
import sys, statistics, time, collections, math
from pathlib import Path
sys.path.insert(0,"src")
from committee.market import AlpacaRest, load_dev_vars
r=AlpacaRest(load_dev_vars(Path("/Users/lukedepass/brain/active-projects/alpaca-agent")/".dev.vars"))
B=["LQD","HYG","TLT","IEF","EFA","EEM","IWM"]
def bars(sym,start,end):
    out,page=[],None
    while True:
        u=(f"{r._data}/v2/stocks/{sym}/bars?timeframe=1Day&start={start}&end={end}"
           f"&limit=10000&feed=sip&adjustment=split")
        if page: u+=f"&page_token={page}"
        p=r._get(u); out+=p.get("bars") or []
        page=p.get("next_page_token")
        if not page: return out
# how far back?
probe=bars("SPY","2000-01-01","2026-08-30")
print(f"earliest SPY daily bar available: {probe[0]['t'][:10]}  ({len(probe)} sessions)\n")
START=probe[0]["t"][:10]

def rsi_series(c,per=2):
    o=[None]*len(c)
    for i in range(per,len(c)):
        g=l=0.0
        for j in range(i-per+1,i+1):
            d=c[j]-c[j-1]; g+=max(d,0); l+=max(-d,0)
        o[i]=50.0 if (l==0 and g==0) else (100.0 if l==0 else 100-100/(1+g/l))
    return o

byyear=collections.defaultdict(list)
per_asset=collections.defaultdict(list)
for s in B:
    time.sleep(0.15)
    d=bars(s,START,"2026-08-30")
    if len(d)<300: print(f"  {s}: only {len(d)} bars"); continue
    c=[b["c"] for b in d]; t=[b["t"][:10] for b in d]
    rr=rsi_series(c)
    for i in range(len(d)-1):
        if rr[i] is None: continue
        sign = 1 if rr[i]<10 else (-1 if rr[i]>90 else 0)
        if not sign: continue
        ret=sign*(c[i+1]-c[i])/c[i] - 0.0004   # 4bp friction
        byyear[t[i][:4]].append(ret); per_asset[s].append(ret)
    print(f"  {s}: {len(d)} sessions from {t[0]}")

def stat(x):
    m=statistics.mean(x); sd=statistics.pstdev(x) or 1e-9
    return m, m/(sd/len(x)**0.5), sum(1 for v in x if v>0)/len(x)
print(f"\n{'year':<7}{'n':>6}{'mean':>10}{'hit':>7}{'t':>8}")
for y in sorted(byyear):
    if len(byyear[y])<30: continue
    m,t_,h=stat(byyear[y])
    print(f"{y:<7}{len(byyear[y]):>6}{m:>+9.3%}{h:>7.0%}{t_:>+8.2f}")
allr=[v for x in byyear.values() for v in x]
m,t_,h=stat(allr)
print(f"\n  ALL YEARS  n={len(allr)}  mean {m:+.3%}  hit {h:.0%}  t={t_:+.2f}")
