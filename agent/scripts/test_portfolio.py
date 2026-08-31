"""Three streams, sized in dollars, with friction — and their correlation.

$300/day out of one strategy means pushing risk until the drawdown is ugly. Out of several
UNCORRELATED streams it means sizing each modestly. Correlation is therefore the number that
decides, so it is measured rather than assumed.
"""
import sys, json, statistics, math, collections, time
from pathlib import Path
sys.path.insert(0,"src")
from committee.market import AlpacaRest, load_dev_vars
r=AlpacaRest(load_dev_vars(Path("/Users/lukedepass/brain/active-projects/alpaca-agent")/".dev.vars"))
START,END="2026-02-06","2026-08-30"
ETF_FRICTION=0.0004  # ~4bp round trip, generous for these names

def daily(sym):
    time.sleep(0.12); out,page=[],None
    while True:
        u=(f"{r._data}/v2/stocks/{sym}/bars?timeframe=1Day&start={START}&end={END}"
           f"&limit=10000&feed=sip&adjustment=split")
        if page: u+=f"&page_token={page}"
        p=r._get(u); out+=p.get("bars") or []
        page=p.get("next_page_token")
        if not page: return out
def rsi(c,per=2):
    o=[None]*len(c)
    for i in range(per,len(c)):
        g=l=0.0
        for j in range(i-per+1,i+1):
            d=c[j]-c[j-1]; g+=max(d,0); l+=max(-d,0)
        o[i]=100.0 if l==0 else 100-100/(1+g/l)
    return o

BASKET=["LQD","HYG","TLT","IEF","EFA","EEM","IWM"]
POS=20000  # dollars per signal
daymap=collections.defaultdict(float)
sig=0
for s in BASKET:
    b=daily(s); c=[x["c"] for x in b]; rr=rsi(c,2)
    for i in range(len(b)-1):
        if rr[i] is None: continue
        m=(c[i+1]-c[i])/c[i]
        if rr[i]<10:   daymap[b[i+1]["t"][:10]] += (m-ETF_FRICTION)*POS; sig+=1
        elif rr[i]>90: daymap[b[i+1]["t"][:10]] += (-m-ETF_FRICTION)*POS; sig+=1
days=sorted(daymap)
d=[daymap[k] for k in days]
eq=0;peak=0;mdd=0
for x in d:
    eq+=x;peak=max(peak,eq);mdd=min(mdd,eq-peak)
m=statistics.mean(d); sd=statistics.pstdev(d) or 1e-9
print(f"STREAM: RSI(2) reversion, {len(BASKET)} bond/intl/small ETFs, ${POS:,}/signal, {ETF_FRICTION:.2%} friction")
print(f"  {sig} signals over {len(days)} active days ({sig/120:.1f}/day across the basket)")
print(f"  mean ${m:+,.0f}/active-day   median ${statistics.median(d):+,.0f}")
print(f"  spread over ALL 120 trading days: ${sum(d)/120:+,.0f}/day")
print(f"  sd ${sd:,.0f}   worst ${min(d):+,.0f}   maxDD ${mdd:+,.0f}")
print(f"  Sharpe {m/sd*math.sqrt(252):.2f}   losing days {sum(1 for x in d if x<0)/len(d):.0%}")
json.dump({k:daymap[k] for k in days}, open("/tmp/stream_rsi.json","w"))

# correlation with the gap-and-go stream
gaps=json.loads(Path("/tmp/gaps.json").read_text()); mins=json.loads(Path("/tmp/mins.json").read_text())
OR=5
def run(b,slip=0.0031):
    if len(b)<OR+5: return None
    hi=max(x["h"] for x in b[:OR]); lo=min(x["l"] for x in b[:OR])
    if hi<=lo: return None
    for i in range(OR,len(b)):
        if b[i]["h"]>hi:
            e=hi*(1+slip); rk=e-lo
            if rk<=0: return None
            tg=e+2.0*rk
            for x in b[i:]:
                if x["l"]<=lo: return (lo*(1-slip)-e)/rk
                if x["h"]>=tg: return (tg*(1-slip)-e)/rk
            return (b[-1]["c"]*(1-slip)-e)/rk
    return None
g=collections.defaultdict(float)
for x in gaps:
    bb=mins.get(f"{x['sym']}|{x['date']}")
    if not bb: continue
    v=run(bb)
    if v is not None: g[x["date"]] += v*284
common=sorted(set(daymap)&set(g))
if len(common)>20:
    a=[daymap[k] for k in common]; b2=[g[k] for k in common]
    ma,mb=statistics.mean(a),statistics.mean(b2)
    cov=sum((x-ma)*(y-mb) for x,y in zip(a,b2))/len(a)
    cor=cov/((statistics.pstdev(a) or 1e-9)*(statistics.pstdev(b2) or 1e-9))
    print(f"\n  CORRELATION with gap-and-go over {len(common)} shared days: {cor:+.3f}")
    tot=[x+y for x,y in zip(a,b2)]
    mt=statistics.mean(tot); st=statistics.pstdev(tot) or 1e-9
    print(f"  combined: ${mt:+,.0f}/day  sd ${st:,.0f}  Sharpe {mt/st*math.sqrt(252):.2f}")
    print(f"  (gap-and-go alone Sharpe {mb/(statistics.pstdev(b2) or 1e-9)*math.sqrt(252):.2f}, RSI alone {ma/(statistics.pstdev(a) or 1e-9)*math.sqrt(252):.2f})")
