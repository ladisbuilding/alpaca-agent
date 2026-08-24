# Tweet bank — alpaca-agent

Running log of things worth posting, captured as they happen. Draw from this during the event.

## ⚠️ Timing rule — read before posting

The engagement track counts *"posts shared on X or LinkedIn **during the hackathon**"* —
**28 Aug – 4 Sep 2026**. Anything posted before Friday probably does **not** qualify.

So: this file is a **bank**, not a queue. Pre-kickoff findings get *re-told* during the window
("day 1: here's what I found while prepping…"). Post freely once it opens — you submit only the
best 5, so volume is free upside.

**Every submitted post must tag both:** `@lablabai` and `@AlpacaHQ`
(LinkedIn: lablab.ai and Alpaca).

Voice: lowercase, fragments, ellipses. Not marketing copy. A real thing that happened, told plainly.

## The angle — "watch my agent think", not "watch me code"

The brief says share progress *"while you build"*, and the field will post
"day 3, got order routing working". We pre-build instead, so during the window the agent is
**already trading** — and the content becomes its live decisions, refusals, debates and P&L.
Strictly better material, and the track is judged partly on engagement *generated*.

Pre-building is about being **ready at 8am Friday**, not about being **done**. An agent live from
the open gets ~5.5 scored trading days; one shipped Wednesday gets ~2.5. The dashboard, video, deck
and tuning all still happen during the week — and all of it is postable.

---

## Tier 1 — strongest. Real surprises with a concrete number.

**greeks-at-n=2** *(the best one so far — a mistake almost made, which always reads better than a win)*
> almost bought a $99/mo data sub for nothing
>
> asked alpaca's options api for 2 contracts. no greeks. looked exactly like a paywall
>
> widened it to 1000 → 282 contracts came back WITH greeks
>
> the blanks were deep ITM. free the whole time
>
> a field missing at n=2 isn't an absent feature...

**the agents that physically cannot trade**
> the bull and bear agents in my trading committee can't place a trade
>
> not "prompted not to". can't
>
> alpaca's mcp server takes ALPACA_TOOLSETS. spin them up without `trading` and the tool
> just isn't in their context
>
> only the executor gets it, after the risk gates pass
>
> risk control at the infra layer beats risk control in a system prompt

**the least-privilege thing, now with numbers**
> proved it instead of claiming it
>
> research agents (scouts, bull, bear, risk officer): 39 mcp tools. zero can place an order
>
> executor: 41 tools, 6 of them can trade
>
> same server, different ALPACA_TOOLSETS
>
> the bear agent isn't *told* not to trade. it has no hands

**paper p&l lies**
> a bot of mine once reported $2,015 profit. 100% win rate
>
> audited it. real number was $89
>
> a 5 min dedup window re-entered the same trade every 6 min. 15 decisions became 72 "trades"
>
> building the auditor agent first this time. if the number looks amazing it's a bug

**best-of-288 is not a backtest**
> found my old QQQ backtest. sharpe 3.31, looked incredible
>
> read closer. 3.31 was the best of a 288-combination param sweep
>
> the walk-forward validation ran on the *baseline* params. sharpe 1.9
>
> i'd been quoting the number that proves nothing

## Tier 2 — good. Process and judgment.

**p&l is 1 of 5**
> assumed a 6 day trading contest was a variance lottery. optimal play = yolo
>
> actually read the judging criteria. p&l is one of five
>
> tech implementation, originality, presentation, engagement are the other four
>
> completely different game. building something good is actually rewarded

**alpaca's own docs say the quiet part**
> alpaca's reference architecture for trading agents:
>
> "risk checks run as deterministic code, unit-tested, with no model in the loop"
>
> their own guide tells you not to let the llm near the risk layer
>
> and: "paper trading results do not predict live performance". from the sponsor

**the gate that catches a lying strategy**
> wrote a risk gate that recomputes a trade's max loss from the geometry of its own legs
>
> if the strategy claims less risk than the structure implies → blocked
>
> because every % based cap downstream is sizing off that number
>
> a strategy that under-reports its risk sails through everything else

**dedup window = the opportunity's lifecycle**
> the dedup window shouldn't be a round number you picked
>
> it should be however long the opportunity actually lives
>
> same structure, same strikes, same expiry = same opportunity until that expiry passes
>
> not "5 minutes because 5 is a nice number"

**found the bug in my own risk gate**
> wrote a gate that recomputes a trade's max loss from its own geometry
>
> then it flagged my iron condor builder
>
> turns out i was summing both wings. a condor can only lose on ONE side, the strikes
> don't overlap
>
> my own safety check caught me overstating risk 2x. worked exactly as intended, just
> not on who i expected

**conservative fills by default**
> the strategy prices every structure at the worst realistic fill. sell at bid, buy at ask
>
> not mid
>
> if it only clears the threshold at mid it won't clear it live
>
> paper trading flatters you enough already

## Tier 3 — filler. Fine if a day is quiet.

- only 3 paper accounts per alpaca login. burned one on dev, one stays sealed for the submission
- $100k paper account means no PDT. the rule that killed this strategy for me in february just... doesn't apply
- 29 tests on the risk gates before a single line of agent code. the gates are the product
- every refusal gets logged with a reason string. "why it didn't trade" is more interesting than "why it did"
- 2,080 people enrolled. most won't submit. the funnel is the real denominator

## Not yet — hold until it actually happens

- **"my bear agent talked the committee out of a trade"** + the real transcript.
  This is the single best post available and it needs a *real* debate log. Save it for day 2–3.
- first live fill through mcp
- the day the daily loss limit halts it, if it does
- final honest p&l vs what a naive count would have claimed

---

## Log

**2026-08-24 (later)** — added: found-bug-in-own-gate, conservative-fills. Strategy layer live
against the real QQQ chain; 59 tests.

**2026-08-24** — bank started. Captured: greeks-at-n=2, ALPACA_TOOLSETS least-privilege,
best-of-288, paper-p&l-lies, p&l-is-1-of-5, misreported-risk gate, dedup lifecycle.
Risk gate module written, 29 tests passing.
