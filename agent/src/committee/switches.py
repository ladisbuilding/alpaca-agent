"""Per-strategy kill switches.

A single global on/off is too blunt for a running book. The situation this exists for is one
we are actually in: **the income sleeve has been measured to have no edge** (IV/RV 1.05-1.22),
while the directional sleeve is still worth running. With a global switch the only way to stand
down premium selling is to stop the whole agent.

Worse, a global kill also stops *management* — and a position you have stopped managing is
strictly more dangerous than one you never opened. Standing down a strategy must never mean
abandoning what it already holds.

So each family has a mode:

    ACTIVE      normal — may open and is managed
    EXIT_ONLY   no new entries; existing positions still managed and closed on the rules
    KILLED      no new entries; existing positions flattened at the next cycle

Set via the `STRATEGY_MODES` env var so it is changed by config, not a rebuild:

    STRATEGY_MODES="income:exit_only,directional:active"

Pattern borrowed from `IgorGanapolsky/trading`, which runs exactly this shape:
*"New iron-condor entries are killed; existing residual IC legs are exit-only."*
"""

from __future__ import annotations

from enum import Enum


class Mode(str, Enum):
    ACTIVE = "active"
    EXIT_ONLY = "exit_only"
    KILLED = "killed"


# Which family a structure belongs to. The committee reasons in sleeves, the broker reasons in
# structures, and this is the mapping between them.
FAMILY_OF: dict[str, str] = {
    "iron_condor": "income",
    "put_credit_spread": "income",
    "call_credit_spread": "income",
    "call_debit_spread": "directional",
    "put_debit_spread": "directional",
    "calendar_call": "calendar",
    "calendar_put": "calendar",
}

FAMILIES = ("income", "directional", "calendar")


class Switches:
    """Which families may open, which are being wound down, which are being flattened."""

    def __init__(self, modes: dict[str, Mode] | None = None, *, global_kill: bool = False) -> None:
        self._modes = {f: Mode.ACTIVE for f in FAMILIES}
        self._modes.update(modes or {})
        self.global_kill = global_kill

    @staticmethod
    def parse(spec: str | None, *, global_kill: bool = False) -> "Switches":
        """Parse "income:exit_only,directional:active".

        An unparseable entry is ignored rather than fatal — a typo in an env var should not
        stop a trading session, and the effective modes are reported on every cycle so a
        silently-ignored typo is visible rather than mysterious.
        """
        modes: dict[str, Mode] = {}
        for part in (spec or "").split(","):
            part = part.strip()
            if not part or ":" not in part:
                continue
            family, _, raw = part.partition(":")
            family, raw = family.strip().lower(), raw.strip().lower()
            if family not in FAMILIES:
                continue
            try:
                modes[family] = Mode(raw)
            except ValueError:
                continue
        return Switches(modes, global_kill=global_kill)

    def family(self, strategy: str) -> str:
        return FAMILY_OF.get(strategy, "directional")

    def mode(self, strategy: str) -> Mode:
        if self.global_kill:
            return Mode.KILLED
        return self._modes[self.family(strategy)]

    def may_open(self, strategy: str) -> bool:
        return self.mode(strategy) is Mode.ACTIVE

    def must_flatten(self, strategy: str) -> bool:
        return self.mode(strategy) is Mode.KILLED

    def block_reason(self, strategy: str) -> str | None:
        """Why a new entry in this strategy is refused, in words worth logging."""
        mode = self.mode(strategy)
        if mode is Mode.ACTIVE:
            return None
        family = self.family(strategy)
        if self.global_kill:
            return "Global kill switch engaged — no new positions in any strategy."
        if mode is Mode.EXIT_ONLY:
            return (
                f"The {family} sleeve is EXIT-ONLY: no new entries, existing positions still "
                "managed and closed on the rules."
            )
        return f"The {family} sleeve is KILLED: no new entries, and open positions are being flattened."

    def describe(self) -> str:
        if self.global_kill:
            return "GLOBAL KILL — no new positions, everything flattening"
        return " · ".join(f"{f}={self._modes[f].value}" for f in FAMILIES)

    @property
    def all_active(self) -> bool:
        return not self.global_kill and all(m is Mode.ACTIVE for m in self._modes.values())
