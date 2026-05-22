#!/usr/bin/env python3
"""
Issue #338 — Auswertung des Open-Meteo Abruf-Zählers.

Liest die append-only JSONL (data/diagnostics/openmeteo_calls.jsonl) und gibt
eine Aufschlüsselung der Abrufe nach Quelle, Endpoint und Stunde sowie die
Status-Quote (200 / 429 / sonstige) aus.

Nur stdlib — keine externen Abhängigkeiten.

Usage:
    python3 scripts/analyze_openmeteo_calls.py [PFAD_ZUR_JSONL]

Default-Pfad: data/diagnostics/openmeteo_calls.jsonl
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

DEFAULT_PATH = Path("data/diagnostics/openmeteo_calls.jsonl")


def _load(path: Path) -> list[dict]:
    if not path.exists():
        print(f"Keine Logdatei gefunden: {path}")
        return []
    rows: list[dict] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _hour_of(ts: str) -> str:
    """Stunde (HH) aus einem ISO-8601-Zeitstempel; '??' wenn unparsebar."""
    try:
        from datetime import datetime
        return datetime.fromisoformat(ts).strftime("%H")
    except (ValueError, TypeError):
        # Fallback: Zeichen 11-13 des ISO-Strings (YYYY-MM-DDTHH...)
        if isinstance(ts, str) and len(ts) >= 13 and ts[10] in ("T", " "):
            return ts[11:13]
        return "??"


def _print_breakdown(title: str, counter: Counter, total: int) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    if not counter:
        print("  (keine Daten)")
        return
    for key, count in counter.most_common():
        pct = (count / total * 100.0) if total else 0.0
        print(f"  {count:6d}  {pct:5.1f}%  {key}")


def analyze(path: Path) -> int:
    rows = _load(path)
    total = len(rows)

    print("=" * 60)
    print(f"Open-Meteo Abruf-Zähler — {path}")
    print("=" * 60)
    print(f"\nGesamt-Abrufe: {total}")

    if total == 0:
        return 0

    by_source: Counter = Counter(str(r.get("source", "unbekannt")) for r in rows)
    by_endpoint: Counter = Counter(str(r.get("endpoint", "?")) for r in rows)
    by_hour: Counter = Counter(_hour_of(str(r.get("ts", ""))) for r in rows)

    # Status-Quote: 200 / 429 / sonstige
    status_counter: Counter = Counter()
    for r in rows:
        status = r.get("status")
        if status == 200:
            status_counter["200 (Erfolg)"] += 1
        elif status == 429:
            status_counter["429 (Limit)"] += 1
        else:
            status_counter[f"sonstige ({status})"] += 1

    _print_breakdown("Nach source (Quelle)", by_source, total)
    _print_breakdown("Nach endpoint", by_endpoint, total)
    # Stunden chronologisch sortiert ausgeben
    print("\nNach Stunde")
    print("-----------")
    for hour in sorted(by_hour):
        count = by_hour[hour]
        pct = count / total * 100.0
        print(f"  {count:6d}  {pct:5.1f}%  {hour}:00")
    _print_breakdown("Status-Quote", status_counter, total)

    return 0


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_PATH
    return analyze(path)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
