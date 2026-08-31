"""⚠️⚠️⚠️ RESULT: THE INCOME SLEEVE LOSES MONEY. 2024-01 to 2026-08, n=354.

                          n    mean/condor   win     t
    ungated             354      -$26.56     62%   -2.54
    regime-gated         70      -$35.56     63%   -1.74   <- the GATE makes it WORSE

    IWM  gross          120      +$20.01     72%   +1.27
    IWM  net            120      -$11.99     68%   -0.76
    QQQ  gross          116      -$20.42     56%   -1.05   <- negative BEFORE costs
    SPY  gross          118       -$7.97     64%   -0.42

⭐⭐⭐ **The regime engine has no demonstrable value.** Gating on "premium is rich" made the
result WORSE in every case. That engine is the centrepiece of this system.

⭐ Only IWM shows any gross edge (+$20/condor, 72% win) — the volatility risk premium, faintly.
**QQQ is negative even before friction**, so the universe included a name with no edge at all.
And $32 of round-trip friction exceeds the +$20 gross edge on the best of the three.

⚠️ ONE HONEST NUANCE, not a rescue: the two condors this account actually closed returned +$21
and +$12 NET, close to IWM's GROSS figure — suggesting the limit orders got price improvement
rather than crossing. Unlike a low-float gapper, resting inside the spread on liquid ETF
options is realistic. **But n=2 is not evidence**, and it is the same open question that
gap-and-go died on.

Backtest the INCOME SLEEVE — the only strategy on this account that has made money,
and the only one never tested. 2024-01 to 2026-08, the full option-bar history available.

Tests the strategy's actual CLAIM, not just the structure: that the regime read (breach rate
below 32% fair value => premium is rich) identifies when selling pays. So it runs BOTH
unconditionally and gated, and compares.

⚠️ Friction is CROSSED on all four legs at entry and exit, at the spread measured on live
chains today ($0.04/leg median for these names, ~$16/contract per side). Historical option
QUOTES are not available from this plan, so today's spread is applied to 2024 trades — the
same bias flagged for gap-and-go, and in the same direction if spreads have tightened.
"""
import sys, json, statistics, time
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0,"src")
from committee.market import AlpacaRest, load_dev_vars
r=AlpacaRest(load_dev_vars(Path("/Users/lukedepass/brain/active-projects/alpaca-agent")/".dev.vars"))

# ⚠️ PER SYMBOL, measured today on 0.10-0.22 delta, 2-9 DTE. Pooling these would charge SPY
# four times its real cost and flatter IWM — and friction is what decides every one of these.
SPREAD_PER_LEG = {"SPY": 0.010, "QQQ": 0.040, "IWM": 0.040}
DTE_MIN, DTE_MAX = 2, 9
WING = 5                   # dollars between short and long strike
FAIR_BREACH = 0.32
SELLER_EDGE_BELOW = 0.25

def daily(sym, start, end):
    out,page=[],None
    while True:
        u=(f"{r._data}/v2/stocks/{sym}/bars?timeframe=1Day&start={start}&end={end}"
           f"&limit=10000&feed=sip&adjustment=split")
        if page: u+=f"&page_token={page}"
        p=r._get(u); out+=p.get("bars") or []
        page=p.get("next_page_token")
        if not page: return out

def occ(sym, exp: date, right: str, strike: float) -> str:
    return f"{sym}{exp:%y%m%d}{right}{int(round(strike*1000)):08d}"

def opt_close(symbols, d: date):
    """Close price for each contract on date d."""
    out={}
    for i in range(0,len(symbols),40):
        part=",".join(symbols[i:i+40])
        try:
            p=r._get(f"{r._data}/v1beta1/options/bars?symbols={part}&timeframe=1Day"
                     f"&start={d.isoformat()}&end={d.isoformat()}&limit=1000")
        except Exception: continue
        for k,v in (p.get("bars") or {}).items():
            if v: out[k]=v[0]["c"]
    return out

def fridays(a: date, b: date):
    d=a
    while d<=b:
        if d.weekday()==4: yield d
        d+=timedelta(days=1)

results={"all":[], "gated":[]}
bysym={}
for sym in ("SPY","QQQ","IWM"):
    bars=daily(sym,"2023-09-01","2026-08-30")
    closes={date.fromisoformat(b["t"][:10]): b["c"] for b in bars}
    days=sorted(closes)
    idx={d:i for i,d in enumerate(days)}
    for entry in days:
        if entry < date(2024,1,22) or entry.weekday()!=0:  # Mondays only
            continue
        # nearest Friday expiry inside the DTE window
        exp=next((f for f in fridays(entry+timedelta(days=DTE_MIN), entry+timedelta(days=DTE_MAX))), None)
        if not exp or exp not in closes: continue
        i=idx[entry]; dte=(exp-entry).days
        hist=[closes[d] for d in days[max(0,i-70):i+1]]
        if len(hist)<40: continue
        # regime read, exactly as regime.py does it: breach rate at the traded horizon
        sess=max(1,int(dte*5/7))
        rets=[(hist[j]-hist[j-sess])/hist[j-sess] for j in range(sess,len(hist))]
        if len(rets)<25: continue
        sigma=statistics.pstdev(rets)
        spot=closes[entry]
        short_dist=sigma*spot          # ~1 sigma out, the 16-delta proxy
        ks=round(spot-short_dist); kc=round(spot+short_dist)
        legs=[occ(sym,exp,"P",ks),occ(sym,exp,"P",ks-WING),
              occ(sym,exp,"C",kc),occ(sym,exp,"C",kc+WING)]
        px=opt_close(legs,entry); time.sleep(0.05)
        if len(px)<4: continue
        credit=(px[legs[0]]-px[legs[1]]+px[legs[2]]-px[legs[3]])*100
        if credit<=0: continue
        settle=closes[exp]
        loss=(max(0,ks-settle)-max(0,ks-WING-settle)+max(0,settle-kc)-max(0,settle-kc-WING))*100
        friction=SPREAD_PER_LEG[sym]*100*4*2  # cross 4 legs, open AND close
        pnl=credit-loss-friction
        breach=sum(1 for x in rets if abs(x)>sigma)/len(rets)
        results["all"].append(pnl)
        bysym.setdefault(sym,{"all":[],"gated":[],"gross":[]})["all"].append(pnl)
        bysym[sym]["gross"].append(credit-loss)
        if breach < SELLER_EDGE_BELOW:
            results["gated"].append(pnl); bysym[sym]["gated"].append(pnl)
    print(f"  {sym} done", flush=True)

def rep(name,xs):
    if len(xs)<20: print(f"  {name:<34} n={len(xs)} too few"); return
    m=statistics.mean(xs); sd=statistics.pstdev(xs) or 1e-9
    t=m/(sd/len(xs)**0.5)
    print(f"  {name:<34} n={len(xs):>4}  mean ${m:+7.2f}/condor  win {sum(1 for v in xs if v>0)/len(xs):.0%}  t={t:+5.2f}  total ${sum(xs):+,.0f}")
print(f"\nIncome sleeve, 2024-01 to 2026-08, friction CROSSED on all 4 legs both ways:")
rep("sell every week (ungated)", results["all"])
rep("only when regime says RICH", results["gated"])
print()
for sym,v in sorted(bysym.items()):
    rep(f"{sym} net (after friction)", v["all"])
    rep(f"{sym} GROSS (no friction)", v["gross"])
    rep(f"{sym} regime-gated", v["gated"])
    print()
