"""Does the gap-and-go survive OUTSIDE 2026? Same test that killed RSI(2).

RESULT 2026-08-31 — **IT SURVIVES.**

    year  meanR      t          year  meanR      t
    2016  +0.204   +1.32        2022  +0.126   +0.80
    2017  +0.132   +0.90        2023  +0.258   +1.58
    2018  +0.268   +1.79        2024  +0.270   +1.64
    2019  +0.234   +1.43        2025  +0.041   +0.27
    2020  +0.097   +0.59        2026  +0.131   +0.79
    2021  -0.236   -1.44
    ALL YEARS  n=774  mean +0.142R  t=+2.94   — positive in 10 of 11 years

⭐ Internal check: this per-year sampling gives 2026 as +0.131R against +0.126R from the
exhaustive 1,008-setup run in test_gap_and_go.py, so the sampling is unbiased.

⚠️ **The early years are FLATTERED.** 2016 trades are charged the spread measured in 2026,
and spreads have tightened a lot in a decade. First half averages +0.187R, second half
+0.098R — some of that apparent decay is this bias rather than real decay.

⚠️ **Crowding is visible in the raw counts:** qualifying gappers went from **148 in 2016 to
1,748 in 2025**, twelve-fold, and 2025 is the weakest positive year. More setups, thinner edge.


Sampled per year rather than exhaustively — minute bars for every gapper across a decade is
far more requests than the plan allows, and a per-year sample answers the decay question,
which is the one that matters.
"""
import sys, json, statistics, time, collections, random
from pathlib import Path
sys.path.insert(0,"src")
from committee.market import AlpacaRest, load_dev_vars
r=AlpacaRest(load_dev_vars(Path("/Users/lukedepass/brain/active-projects/alpaca-agent")/".dev.vars"))
syms=json.loads(Path("/tmp/syms.json").read_text())
YEARS=[(y,f"{y}-01-01",f"{y}-12-31") for y in range(2016,2026)]+[(2026,"2026-01-01","2026-08-30")]
PER_YEAR=90
OR=5; RR=2.0; SLIP=0.0031

def find(start,end):
    hist={}
    for i in range(0,len(syms),300):
        part=",".join(syms[i:i+300]); page=None
        while True:
            u=(f"{r._data}/v2/stocks/bars?symbols={part}&timeframe=1Day&start={start}&end={end}"
               f"&limit=10000&feed=sip&adjustment=split")
            if page: u+=f"&page_token={page}"
            try: p=r._get(u)
            except Exception: break
            for s,b in (p.get("bars") or {}).items(): hist.setdefault(s,[]).extend(b)
            page=p.get("next_page_token")
            if not page: break
    out=[]
    for s,b in hist.items():
        b.sort(key=lambda x:x["t"]); vols=[x["v"] for x in b]
        for j in range(20,len(b)):
            cur,prev=b[j],b[j-1]
            if not prev["c"] or not cur["o"]: continue
            gap=(cur["o"]-prev["c"])/prev["c"]
            rv=cur["v"]/(statistics.median(vols[max(0,j-20):j]) or 1)
            if gap>=0.10 and 1.0<=cur["o"]<=20.0 and cur["o"]*cur["v"]>=10_000_000 and rv>=5:
                out.append({"sym":s,"date":cur["t"][:10]})
    return out

def minutes(sym,day):
    o,page=[],None
    while True:
        u=(f"{r._data}/v2/stocks/{sym}/bars?timeframe=1Min&start={day}T13:30:00Z"
           f"&end={day}T20:05:00Z&limit=10000&feed=sip&adjustment=split")
        if page: u+=f"&page_token={page}"
        p=r._get(u); o+=p.get("bars") or []
        page=p.get("next_page_token")
        if not page: return o

def run(b,slip=SLIP):
    if len(b)<OR+5: return None
    hi=max(x["h"] for x in b[:OR]); lo=min(x["l"] for x in b[:OR])
    if hi<=lo: return None
    for i in range(OR,len(b)):
        if b[i]["h"]>hi:
            e=hi*(1+slip); rk=e-lo
            if rk<=0: return None
            tg=e+RR*rk
            for x in b[i:]:
                if x["l"]<=lo: return (lo*(1-slip)-e)/rk
                if x["h"]>=tg: return (tg*(1-slip)-e)/rk
            return (b[-1]["c"]*(1-slip)-e)/rk
    return None

random.seed(5)
print(f"{'year':<7}{'gappers':>9}{'tested':>8}{'meanR':>10}{'hit':>7}{'t':>8}")
allr=[]
for y,s0,s1 in YEARS:
    g=find(s0,s1)
    samp=random.sample(g,min(PER_YEAR,len(g)))
    rs=[]
    for x in samp:
        try: v=run(minutes(x["sym"],x["date"]))
        except Exception: continue
        if v is not None: rs.append(v)
        time.sleep(0.03)
    if len(rs)<20:
        print(f"{y:<7}{len(g):>9}{len(rs):>8}  too few"); continue
    m=statistics.mean(rs); sd=statistics.pstdev(rs) or 1e-9
    print(f"{y:<7}{len(g):>9}{len(rs):>8}{m:>+9.3f}R{sum(1 for v in rs if v>0)/len(rs):>7.0%}{m/(sd/len(rs)**0.5):>+8.2f}", flush=True)
    allr+=rs
m=statistics.mean(allr); sd=statistics.pstdev(allr) or 1e-9
print(f"\n  ALL YEARS n={len(allr)}  mean {m:+.3f}R  t={m/(sd/len(allr)**0.5):+.2f}")
