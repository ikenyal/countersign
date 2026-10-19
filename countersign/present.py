"""How the demo prints: plain log lines by default, or a slower, colored layout for recording a video.

    python -m countersign.agent --video pushed routine unconfirmed

Only the printing changes. The gate's decisions are the same in both modes.
"""
from __future__ import annotations

import sys
import threading
import time

_LOCK = threading.Lock()

VIDEO = False
PAUSE = 0.9

_C = {"dim": "2", "bold": "1", "green": "32", "red": "31", "yellow": "33", "cyan": "36", "white": "97"}


def c(text: str, *styles: str) -> str:
    if not VIDEO:
        return text
    return "".join(f"\033[{_C[s]}m" for s in styles) + text + "\033[0m"


def pause(n: float = 1.0) -> None:
    if VIDEO:
        time.sleep(PAUSE * n)


def scenario(name: str, change: str, affected: list[str], human: str | None, task: str) -> None:
    if not VIDEO:
        print(f"\n=== {name} ===\n  {task}")
        return
    print("\n" + c(f" COUNTERSIGN  ·  {name} ", "bold", "white") + "\n")
    print(f"  {c('Settled', 'dim')}   {change}")
    print(f"  {c('Affects', 'dim')}   {', '.join(affected)}")
    if human:
        print(f"  {c('Human', 'dim')}     {c(chr(34) + human + chr(34), 'yellow')}")
    print()
    pause(2)


def searched(query: str, ids: list[str]) -> None:
    if not VIDEO:
        print(f"  [search] {query!r} -> {ids}")
        return
    with _LOCK:  # the agent may search in parallel; keep each line whole
        sys.stdout.write(c(f"  agent searches records: {query}", "dim") + "\n")
        sys.stdout.flush()
    pause(0.4)


def gate_start() -> None:
    if VIDEO:
        print("\n" + c("  The agent wants to close. The gate checks:", "bold") + "\n")
        pause(1)


def step(n: int, title: str) -> None:
    if VIDEO:
        print(f"  {c(str(n), 'bold', 'cyan')}  {c(title, 'bold')}")
        pause(0.6)


def line(ok: bool | None, label: str, detail: str = "", log: str | None = None) -> None:
    """One check result. ok=True ✓, False ✗, None neutral."""
    if not VIDEO:
        if log:
            print(log)
        return
    mark = {True: c("✓", "green"), False: c("✗", "red", "bold"), None: c("·", "dim")}[ok]
    print(f"       {mark}  {label:<34} {c(detail, 'dim') if ok is not False else c(detail, 'red')}")
    pause(0.5)


def verdict(hand_back: bool, reasons: list[str]) -> None:
    if not VIDEO:
        if hand_back:
            print(f"  [gate] -> HAND BACK to the humans: {'; '.join(reasons)}")
        return
    print()
    if hand_back:
        print("  " + c(" HAND BACK to the humans ", "bold", "red"))
        for r in reasons:
            print(c(f"     · {r}", "red"))
    else:
        print("  " + c(" CLOSE: the agents may settle this ", "bold", "green"))
    print()
    pause(2)


def prepared(ready: str, decide: str, ask: str) -> None:
    if not VIDEO:
        print(f"  [prepared] ready: {ready[:160]}\n             decide: {decide[:160]}\n             ask: {ask[:200]}")
        return
    print(c("  Prepared for the humans", "bold"))
    print(f"     {c('Decide', 'dim')}  {decide}")
    print(f"     {c('Ask', 'dim')}     {ask[:200]}")
    print()
    pause(2)


def committed(summary: str) -> None:
    if VIDEO:
        print(c("  ✔ Agreement committed. Nobody opened a calendar.", "green", "bold") + "\n")
        pause(2)


def agent_says(text: str) -> None:
    if not VIDEO:
        print(f"  [agent] {text[:500]}")
        return
    if text:
        print(c("  Agent to its human:", "dim") + f" {text[:300]}\n")
        pause(2)
