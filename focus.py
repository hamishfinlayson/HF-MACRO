"""
focus.py - FOCUS LIST and PARKED SHELF (PC version only).

We can't develop everything at once. Every strategy, ingredient and risk check is sorted into:
  🎯 FOCUS  - winning, close to break-even against a coin toss, or profitable: keep developing these.
  🅿️ PARKED - clearly losing for now. Nothing is deleted: each one is saved with the date, its numbers,
              the settings it was tested with and why it was parked, so we can come back to it later.

Rules (decided with Hamish):
  Strategies : keep if it beats the coin toss (✅), OR its edge over the coin toss is above -0.2% a week,
               OR its average week made a profit.
  Ingredients: keep if its verdict isn't ❌ (confirmed, reverse, promising or recent), OR it made money on
               the unseen period.
  Risk checks: keep if it helped (✅), made trades safer (🛡) or was mixed (🟡); park if it made things
               worse (❌) or never triggered (➖).
Anything you bring back by hand stays in focus until you park it again.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

PATH = Path(__file__).parent / "data" / "focus.json"
COIN_LIMIT = -0.2          # % a week: edge over the coin toss above this stays in focus


def load():
    try:
        return json.loads(PATH.read_text())
    except Exception:
        return {"parked": {}, "restored": []}


def save(state):
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(state, indent=1, default=str))


def item_id(kind, name, cls):
    return f"{kind}|{name}|{cls}"


def _num(x):
    try:
        x = float(x)
        return x if np.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def rule_strategy(avg_week, vs_coin, vs_coin_p):
    avg_week, vs_coin, p = _num(avg_week), _num(vs_coin), _num(vs_coin_p)
    if vs_coin is not None and vs_coin > 0 and p is not None and p < 0.05:
        return True, "beats the coin toss (unlikely to be luck)"
    if vs_coin is not None and vs_coin > COIN_LIMIT:
        return True, f"edge over the coin toss {vs_coin:+.2f}% a week (above {COIN_LIMIT}%)"
    if avg_week is not None and avg_week > 0:
        return True, f"made a profit ({avg_week:+.2f}% a week)"
    why = []
    if vs_coin is not None:
        why.append(f"{vs_coin:+.2f}% a week vs the coin toss")
    if avg_week is not None:
        why.append(f"average week {avg_week:+.2f}%")
    return False, "lost money and trailed the coin toss: " + ", ".join(why) if why else "no usable results"


def rule_ingredient(verdict, unseen_edge):
    v = str(verdict)
    if v[:1] in ("✅", "🔄", "🟡", "⚠"):
        return True, v
    e = _num(unseen_edge)
    if e is not None and e > 0:
        return True, f"{v}, but made {e:+.3f}% a week on the unseen period"
    return False, v + (f" (unseen {e:+.3f}% a week)" if e is not None else "")


def rule_risk(verdict):
    v = str(verdict)
    if v[:1] in ("✅", "🛡", "🟡"):
        return True, v
    return False, v


def sync(kind, rows, settings=None):
    """
    rows: list of dicts with name, cls, keep, reason and any numbers. Parks new losers, unparks items
    that have improved, never auto-parks something brought back by hand. Returns rows with a 'status'.
    """
    state = load()
    today = pd.Timestamp.now().strftime("%Y-%m-%d")
    out = []
    for r in rows:
        iid = item_id(kind, r["name"], r["cls"])
        restored = iid in state["restored"]
        if r["keep"] or restored:
            state["parked"].pop(iid, None)
            status = "🎯 Focus" + (" (brought back)" if restored and not r["keep"] else "")
        else:
            nums = {k: (_num(v) if not isinstance(v, str) else v) for k, v in r.items()
                    if k not in ("keep", "name", "cls", "reason")}
            state["parked"][iid] = dict(kind=kind, name=r["name"], cls=r["cls"], parked_on=today, reason=r["reason"],
                                        numbers=nums, settings=str(settings or ""))
            status = "🅿️ Parked"
        out.append({**r, "status": status})
    save(state)
    return out


def bring_back(iid):
    state = load()
    state["parked"].pop(iid, None)
    if iid not in state["restored"]:
        state["restored"].append(iid)
    save(state)


def park(iid, kind, name, cls, reason="parked by hand"):
    state = load()
    if iid in state["restored"]:
        state["restored"].remove(iid)
    state["parked"][iid] = dict(kind=kind, name=name, cls=cls, parked_on=pd.Timestamp.now().strftime("%Y-%m-%d"),
                                reason=reason, numbers={}, settings="")
    save(state)


def parked_table():
    p = load()["parked"]
    if not p:
        return pd.DataFrame()
    return pd.DataFrame([dict(id=k, kind=v["kind"], name=v["name"], cls=v["cls"], parked_on=v["parked_on"],
                              reason=v["reason"]) for k, v in p.items()]).sort_values(["kind", "cls", "name"])


def is_parked(kind, name, cls):
    return item_id(kind, name, cls) in load()["parked"]


def focus_keys(cls, keys):
    """Ingredients for the model, without the parked ones."""
    parked = load()["parked"]
    return [k for k in keys if item_id("Ingredient", k, cls) not in parked]
