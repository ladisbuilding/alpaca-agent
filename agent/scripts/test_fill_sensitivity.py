"""Does the edge survive if wide-spread names fill the way wide-spread names actually fill?

The whole result lives in the widest quintile (median spread 1.63%, p90 3.22%). The model
charges HALF the quoted spread, which assumes a fill at the midpoint of a thin, fast-moving
quote. That is the most generous possible assumption in exactly the region carrying the edge.
"""
import json, statistics
from pathlib import Path
gaps=json.loads(Path("/tmp/gaps.json").read_text())
mins=json.loads(Path("/tmp/mins.json").read_text())
spreads=json.loads(Path("/tmp/spreads.json").read_text())
OR,RR=5,2.0
def run(b,slip):
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
def sweep(mult, cap=None, label=""):
    out=[]
    for g in gaps:
        k=f"{g['sym']}|{g['date']}"
        b=mins.get(k); sp=spreads.get(k)
        if not b or sp is None: continue
        if cap is not None and sp>cap: continue
        r=run(b, sp*mult)
        if r is not None: out.append(r)
    if len(out)<30: print(f"  {label:<46} n={len(out)}  too few"); return
    m=statistics.mean(out); sd=statistics.pstdev(out) or 1e-9
    t=m/(sd/len(out)**0.5)
    days=120
    print(f"  {label:<46} n={len(out):>4}  mean {m:+.3f}R  t={t:>+5.2f}  ${m*len(out)/days*284:>6.0f}/day")
print("Slippage charged per side, as a multiple of the measured quoted spread:\n")
sweep(0.5, None, "0.5x spread (mid fill) — the original model")
sweep(1.0, None, "1.0x spread (cross the full spread)")
sweep(1.5, None, "1.5x spread (cross + adverse move)")
print()
sweep(1.0, 0.02, "1.0x spread, skip anything wider than 2%")
sweep(1.0, 0.03, "1.0x spread, skip anything wider than 3%")
sweep(1.5, 0.02, "1.5x spread, skip anything wider than 2%")
