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

**my own invariant caught me**
> gave the auditor agent the "trading" toolset so it could read orders
>
> then the assertion i'd written one file earlier failed: only ONE role may be able to trade
>
> turns out `account` scope alone exposes fills + portfolio history and zero order tools
>
> auditor reads fills now. which is better anyway
>
> orders are intent. fills are what happened

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

**the bear agent works**
> first real run of my bear agent. fed it an iron condor to attack
>
> it pulled live quotes, found my deltas were stale (-0.23 not -0.15), computed realized vol
> vs implied, and noticed NVDA reports ON expiry day
>
> verdict: KILL
>
> then: "book is empty, so no correlation objection — i'll concede that one"
>
> it argued honestly. that's the part i wasn't sure i'd get

**what one opinion costs**
> one bear agent turn: 131,836 tokens in, 7,806 out. about 86 cents
>
> the input is nearly all option chain dumps
>
> six roles per cycle, every 30 min, 6.5 hour session... ~$65/day
>
> turns out "let the llm read the whole chain" has a price

**caching took the cost from $400 to $40**
> first agent turn cost 86 cents. mostly option chain dumps getting re-sent every loop iteration
>
> added prompt cache breakpoints on the tools + system block
>
> full 8-role cycle now: $0.24. 9,699 fresh input tokens vs 41,430 cache reads
>
> 81% hit rate. same model, same quality

**check the cheap thing first**
> my committee spends ~$3 in llm calls debating a trade
>
> the deterministic risk gates cost $0 and run in microseconds
>
> so the gates run FIRST. if the structure is already blocked, nobody debates it
>
> "every candidate was refused before debate — no model tokens spent arguing about
> structures that could not be taken"

**my bear agent talked the committee out of a trade** ⭐ THE POST
> first full debate my agents ever ran. iron condor on SPY
>
> bull argued for it — but corrected its own scout first: "actual leg IVs are 11.1-15.4%,
> not 21-23%"
>
> bear went after the vol number: the 13-day window STARTS AFTER the two biggest days in
> the sample. extend it to 16 and realized goes 7.5% → 11.4%
>
> "sold call IV is 11.08%. you are selling the near wing at or below trailing realized.
> that is not variance premium"
>
> then the PM re-ran it independently on 30 sessions, agreed, and passed
>
> they talked me out of my own strategy

**my auditor agent found a bug in my risk code. on an empty account** ⭐
> wired up the auditor last. gave it read-only access to fills, nothing else
>
> ran it on an account with zero trades. expected "nothing to report"
>
> instead: "buying_power = $400,000 but options_buying_power = $100,000. defined-risk
> options are cash-secured. a sizing gate reading buying_power would over-size 4x"
>
> checked. my gate was reading the wrong field. it would have authorised 4x the risk
>
> found on an empty book, before a single trade

**it also told me what it couldn't see**
> the auditor's last section was titled "audit gap i cannot close"
>
> "i have no tool for open positions or working orders. i verified zero fills; i INFERRED
> zero positions. that inference is strong but it is an inference"
>
> it's scoped to account data only, on purpose
>
> and it said so instead of bluffing

**the scout was wrong and the committee caught it**
> built the whole thing on "sell premium when IV is rich vs realized"
>
> my own agents just demonstrated that on current data IV is at or BELOW realized
>
> the edge i designed around might not be there
>
> better to find that from a bear agent on monday than from the p&l on friday

**the word "not" cost me a trade** ⭐
> my bear agent wrote: "it's symmetric, not adverse, so not a kill"
>
> then: "ALLOW, 1 lot"
>
> my PM said TAKE
>
> my code recorded: BLOCKED BY COMMITTEE
>
> because i'd written `if "KILL" in text.upper()`
>
> the word kill appeared. inside a sentence saying the opposite

**my agent told me my strategy doesn't work** ⭐⭐
> spent a day testing four options strategies
>
> selling premium: IV is 1.06x realized. you're not being paid
> buying spreads: mid IS fair value. EV = minus friction
> my old ORB backtest: sharpe 1.58 in-sample → 0.75 out of sample
> ORB held overnight: hit rate 46-51%. pure noise
>
> four tests, four negatives
>
> i'd rather find that in a backtest on monday than in the p&l on friday

**a timezone bug that would have cost the whole afternoon**
> gate said "within 15 min of the close" at 15:48
>
> 15:48 UTC. the container runs in UTC. that's 11:48 in new york
>
> mid-session
>
> it would have blocked every afternoon trade of the competition and the reason
> string would have looked completely plausible

**i measured my edge at $3.85. it costs $4.00 to collect it** ⭐⭐ THE POST
> my opening-range signal has a real edge. +0.026R per trade on QQQ
>
> through a single ATM option that's **$3.85 per contract**
>
> the bid-ask on that option is 2 cents. cross it twice: **$4.00**
>
> so the edge is real, and it is worth fifteen cents less than the cost of taking it
>
> TSLA has 4x the edge. and a 26 cent spread. net -$35
>
> that's not bad luck. that's what an efficient market looks like up close

**i was measuring my own edge at the wrong horizon** ⭐⭐ THE POST
> my agent stood down for two days. "no premium edge anywhere"
>
> it was right about the number and i'd given it the wrong number
>
> i compared annualised IV to 30-DAY realised vol. correct for a monthly structure.
> useless for the 2-day ones i actually trade
>
> measured properly: IWM prices a 1.1% move. the underlying exceeds it 22% of the time.
> fair value is 32%
>
> the edge was there the whole time. my ruler was the wrong length

**an implied move is a 1-sigma move**
> stopped comparing volatility numbers. started counting
>
> the market prices a move. how often does the underlying actually exceed it?
>
> should be ~32% if it's fair. IWM: 11%. SPY: 22%. QQQ: 30%
>
> two of those are sellers getting overpaid. one is fairly priced
>
> and QQQ — the fair one — is what my scouts kept nominating

**my screener's first pick was a trap** ⭐⭐
> gave my agent a real market screener instead of three tickers i'd hardcoded
>
> first run it ranked NVDA the richest premium in the market. breach rate 0%. implied
> 2-day move 8.8%
>
> NVDA reported earnings that afternoon
>
> a backward-looking statistic cannot see a scheduled event. it wasn't rich premium,
> it was the market pricing a known unknown
>
> now: implied detaching >2.5x from realised DISQUALIFIES instead of ranking first

**my scouts had never once scouted**
> asked why my agent traded QQQ/SPY/IWM. answer: because i typed them into a config on day one
>
> then i checked the logs. the premium scout made ZERO tool calls
>
> it had get_market_movers, get_most_active_stocks and get_news the whole time
>
> a screener sitting in the toolbox, never opened, while the agent was capped at my
> first guess

**twelve tests, one winner, and that is the problem** ⭐⭐
> tested four technical signals out of sample. one cleared costs
>
> which should make you suspicious, not excited. twelve tests, one hit at p<0.05 is
> exactly what noise produces
>
> so i tested it across 12 symbols instead of one. pooled t = 1.79. below the bar
>
> but it works on IWM, EEM, TLT and dies on QQQ, XLK, MSFT. small caps, emerging,
> bonds — where the arbitrage is thin. flat where it isn't
>
> noise doesn't usually sort itself that neatly. suggestive, not proven

**the overnight anomaly decayed**
> "nearly all market gains happen overnight." documented t-stat ~17. the grandmother
> of all anomalies
>
> tested it on the last 140 sessions: +0.08% a night, 58% hit rate... t = 1.04
>
> real direction, no significance left
>
> its own source warned it deteriorated after 2010. it did

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

**a worker can't fetch another worker**
> my dashboard's SSR loader fetched my api worker. 404
>
> same url from curl: 200
>
> worker-to-worker on workers.dev loops back to the caller. needs a service binding
>
> the tell was my own error handling: i'd written catch → return null, so a broken
> fetch rendered as "no data yet"
>
> looked like the agent had done nothing. it had done plenty

**typography as a speaker label**
> the dashboard uses three typefaces and each one means something
>
> bodoni for the masthead. serif for what the agents argue. mono for the deterministic layer
>
> so when a risk gate kills a trade, the verdict is set in mono and stamped across the argument
>
> code overriding rhetoric, visible in the type

**testing the alarm would have disabled the alarm**
> forced my new watchdog to fire, just to prove it could
>
> the email had bad grammar. fine, fixed it
>
> the email was indistinguishable from a real alert. worse, fixed it
>
> and the test run wrote the cooldown row. so running a drill would have suppressed
> the next hour of REAL alerts
>
> testing the alarm disabled the alarm. never would have seen it by reading the code

**the alert you need isn't the one you think**
> was about to wire up error reporting for my trading agent
>
> then realised the failure that would actually cost me the week doesn't throw
>
> cron stops. container won't boot. every run returns "skipped". silence
>
> so i built a watchdog for ABSENCE instead. "i expected a sitting by now and didn't get one"
>
> then forced it to fire, because an alert that's never fired isn't an alert

**my dashboard was hiding the best part**
> the agent refuses most trades before any debate happens. deterministic gates run first,
> they're cheap
>
> which meant my dashboard showed... a list of refusals. every time
>
> the actual debate transcripts were sitting in the database, invisible, because the page
> only ever rendered the LATEST sitting
>
> the most interesting thing it produces and you couldn't see it

**"bounded" is not the same as "capped"**
> asked myself what my unattended trading agent could cost if it misbehaved
>
> every loop IS bounded. 8 iterations per turn, 8k tokens, 2 trades, 13 runs a day
>
> so worst case is finite: ~$140/day instead of the ~$25 i actually see
>
> finite isn't the same as capped though. added a per-cycle ceiling and a daily one
>
> and the note in the code: "a sitting that costs this much is misbehaving, not working hard"

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
