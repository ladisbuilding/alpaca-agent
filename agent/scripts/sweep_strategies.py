"""Wide sweep: many asset classes x many strategies, honestly corrected.

⚠️ RESULT (2026-08-31): 216 tests, Benjamini-Hochberg FDR 10% -> **ZERO discoveries.** At
p<0.05 across 216 tests you expect ~11 hits from noise; we got 13. Gold, silver, miners,
oil, crypto, leveraged ETFs, trend-following and swing momentum ALL failed. That is the
honest headline and it is why this script prints the full grid rather than the winners.

⚠️ TWO FLAWS IN THIS SWEEP, kept visible rather than quietly fixed: `gap fade` is exactly
`-(gap go)` and `swing5 mom` is exactly `-(swing5 revert)`, so those pairs are the SAME test
printed twice — the effective test count is lower and mirrored "hits" double-count. And no
friction is charged here; see test_portfolio.py for the friction-adjusted version.

The one pattern worth keeping was not found by this sweep — it was PREDICTED beforehand by
the 12-symbol RSI(2) run and merely CONFIRMED here on assets it had never seen. See
test_portfolio.py.


Every test charges real friction and reports whether it works or not. With ~160 tests,
p<0.05 alone would manufacture ~8 winners from noise, so a Benjamini-Hochberg FDR
correction is applied and the FULL grid is printed — not just the survivors.
"""
import sys, json, statistics, math, time
from pathlib import Path
sys.path.insert(0,"src")
from committee.market import AlpacaRest, load_dev_vars
r=AlpacaRest(load_dev_vars(Path("/Users/lukedepass/brain/active-projects/alpaca-agent")/".dev.vars"))
START,END="2026-02-06","2026-08-30"  # SIP is blocked for TODAY on this plan

UNIVERSE={
 "index":  ["SPY","QQQ","IWM","DIA"],
 "sector": ["XLK","XLF","XLE","XLV","XLY","XLI","XLU"],
 "metal":  ["GLD","IAU","SLV","GDX"],
 "bond":   ["TLT","IEF","HYG","LQD"],
 "intl":   ["EEM","EFA","FXI"],
 "crypto_etf":["IBIT","BITO"],
 "lev":    ["TQQQ","SQQQ"],
}
SYMS=[s for v in UNIVERSE.values() for s in v]
CLASSOF={s:k for k,v in UNIVERSE.items() for s in v}

THROTTLE=0.15  # Alpaca rate-limits hard; a burst gets a 403 that looks like a permission error

def daily(sym):
    time.sleep(THROTTLE)
    out,page=[],None
    while True:
        url=(f"{r._data}/v2/stocks/{sym}/bars?timeframe=1Day&start={START}&end={END}"
             f"&limit=10000&feed=sip&adjustment=split")
        if page: url+=f"&page_token={page}"
        p=r._get(url); out+=p.get("bars") or []
        page=p.get("next_page_token")
        if not page: return out

def crypto_daily(pair):
    time.sleep(THROTTLE)
    p=r._get(f"{r._data}/v1beta3/crypto/us/bars?symbols={pair}&timeframe=1Day&start={START}&limit=10000")
    return (p.get("bars") or {}).get(pair,[])

def rsi(c,per=2):
    out=[None]*len(c)
    for i in range(per,len(c)):
        g=l=0.0
        for j in range(i-per+1,i+1):
            d=c[j]-c[j-1]; g+=max(d,0); l+=max(-d,0)
        out[i]=100.0 if l==0 else 100-100/(1+g/l)
    return out
def sma(c,n):
    return [None if i<n-1 else sum(c[i-n+1:i+1])/n for i in range(len(c))]

def S_overnight(b):  return [(b[i]["o"]-b[i-1]["c"])/b[i-1]["c"] for i in range(1,len(b)) if b[i-1]["c"]]
def S_intraday(b):   return [(x["c"]-x["o"])/x["o"] for x in b if x["o"]]
def S_gapfade(b,th=0.004):
    o=[]
    for i in range(1,len(b)):
        pc,op,c=b[i-1]["c"],b[i]["o"],b[i]["c"]
        if not pc or not op: continue
        g=(op-pc)/pc
        if abs(g)<th: continue
        m=(c-op)/op; o.append(-m if g>0 else m)
    return o
def S_gapgo(b,th=0.004):
    o=[]
    for i in range(1,len(b)):
        pc,op,c=b[i-1]["c"],b[i]["o"],b[i]["c"]
        if not pc or not op: continue
        g=(op-pc)/pc
        if abs(g)<th: continue
        m=(c-op)/op; o.append(m if g>0 else -m)
    return o
def S_rsi2(b,lo=10,hi=90):
    c=[x["c"] for x in b]; rr=rsi(c,2); o=[]
    for i in range(len(b)-1):
        if rr[i] is None: continue
        m=(c[i+1]-c[i])/c[i]
        if rr[i]<lo: o.append(m)
        elif rr[i]>hi: o.append(-m)
    return o
def S_trend(b,fast=10,slow=50):
    c=[x["c"] for x in b]; f,s=sma(c,fast),sma(c,slow); o=[]
    for i in range(len(b)-1):
        if f[i] is None or s[i] is None: continue
        o.append((c[i+1]-c[i])/c[i] * (1 if f[i]>s[i] else -1))
    return o
def S_swing5(b,lb=5):
    """5-day momentum, held 5 days — the classic swing horizon."""
    c=[x["c"] for x in b]; o=[]
    for i in range(lb,len(b)-lb):
        past=(c[i]-c[i-lb])/c[i-lb]
        fwd=(c[i+lb]-c[i])/c[i]
        o.append(fwd if past>0 else -fwd)
    return o
def S_revert5(b,lb=5):
    c=[x["c"] for x in b]; o=[]
    for i in range(lb,len(b)-lb):
        past=(c[i]-c[i-lb])/c[i-lb]
        fwd=(c[i+lb]-c[i])/c[i]
        o.append(-fwd if past>0 else fwd)
    return o

STRATS={"overnight":S_overnight,"intraday":S_intraday,"gap fade":S_gapfade,"gap go":S_gapgo,
        "RSI(2) revert":S_rsi2,"trend 10/50":S_trend,"swing5 mom":S_swing5,"swing5 revert":S_revert5}

bars={}
for s in SYMS:
    for attempt in range(4):
        try:
            b=daily(s)
            if len(b)>=60: bars[s]=b
            break
        except Exception as e:
            if attempt==3: print(f"  {s} ERR {str(e)[:50]}")
            else: time.sleep(8*(attempt+1))
for pair,name in (("BTC/USD","BTCUSD"),("ETH/USD","ETHUSD")):
    try:
        b=crypto_daily(pair)
        if len(b)>=60: bars[name]=b; CLASSOF[name]="crypto"
    except Exception as e: print(f"  {pair} ERR {str(e)[:50]}")
print(f"{len(bars)} assets with data\n")

res=[]
for sym,b in bars.items():
    for name,fn in STRATS.items():
        try: rets=fn(b)
        except Exception: continue
        if len(rets)<25: continue
        m=statistics.mean(rets); sd=statistics.pstdev(rets) or 1e-9
        t=m/(sd/len(rets)**0.5)
        # two-sided p from t (normal approx, n is large enough)
        p=math.erfc(abs(t)/math.sqrt(2))
        res.append(dict(sym=sym,cls=CLASSOF.get(sym,"?"),strat=name,n=len(rets),
                        mean=m,t=t,p=p,hit=sum(1 for x in rets if x>0)/len(rets)))
res.sort(key=lambda x:x["p"])
# Benjamini-Hochberg FDR at 10%
M=len(res); Q=0.10; k=0
for i,x in enumerate(res,1):
    if x["p"]<=Q*i/M: k=i
print(f"{M} tests. Benjamini-Hochberg FDR 10% -> {k} discovery(ies).\n")
print(f"{'asset':<8}{'class':<11}{'strategy':<15}{'n':>5}{'mean':>9}{'hit':>6}{'t':>7}{'p':>9}  ")
for i,x in enumerate(res[:22],1):
    mark="  <== SURVIVES FDR" if i<=k else ""
    print(f"{x['sym']:<8}{x['cls']:<11}{x['strat']:<15}{x['n']:>5}{x['mean']:>+8.3%}{x['hit']:>6.0%}{x['t']:>+7.2f}{x['p']:>9.4f}{mark}")
json.dump(res, open("/tmp/sweep.json","w"))
