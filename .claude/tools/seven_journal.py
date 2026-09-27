#!/usr/bin/env python3
"""Lese-Werkzeug fuer die seven.io-Journale (nur GET, versendet nie etwas).

Zweck: Premium-SMS-Eingang und -Ausgang pruefen, ohne den Schluessel in einen
Befehl zu schreiben (Issue #2417, AC-27). Der Schluessel kommt aus der
Konfiguration (GZ_SEVEN_API_KEY), wird nie ausgegeben; Rufnummern erscheinen
gekuerzt auf die letzten drei Ziffern.

Aufruf:
    uv run python3 .claude/tools/seven_journal.py inbound [--since 2026-09-27] [--limit 20]
    uv run python3 .claude/tools/seven_journal.py outbound --since 2026-09-27
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx
from dotenv import dotenv_values

JOURNAL_URL = "https://gateway.seven.io/api/journal/{kind}"
# Worktrees haben keine eigene .env -- dann die des Hauptcheckouts.
ENV_CANDIDATES = [Path.cwd() / ".env", Path("/home/hem/gregor_zwanzig/.env")]


def _api_key() -> str:
    key = os.environ.get("GZ_SEVEN_API_KEY")
    for path in ENV_CANDIDATES:
        if key:
            break
        if path.is_file():
            key = dotenv_values(path).get("GZ_SEVEN_API_KEY")
    if not key:
        sys.exit("GZ_SEVEN_API_KEY nicht gefunden (Umgebung oder .env).")
    return key


def _mask(value) -> str:
    text = str(value or "")
    digits = text.lstrip("+")
    return "…" + digits[-3:] if digits.isdigit() else text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("kind", choices=["inbound", "outbound"])
    parser.add_argument("--since", help="date_from, JJJJ-MM-TT")
    parser.add_argument("--until", help="date_to, JJJJ-MM-TT")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    params: dict = {"limit": args.limit}
    if args.since:
        params["date_from"] = args.since
    if args.until:
        params["date_to"] = args.until
    response = httpx.get(
        JOURNAL_URL.format(kind=args.kind),
        headers={"X-Api-Key": _api_key()},
        params=params,
        timeout=20,
    )
    if response.status_code != 200:
        print(f"HTTP {response.status_code}: {response.text[:200]}")
        return 1
    data = response.json()
    if not isinstance(data, list):
        print(str(data)[:300])
        return 1
    for m in data:
        print(
            m.get("id"), m.get("timestamp"),
            f"{_mask(m.get('from'))} -> {_mask(m.get('to'))}",
            repr(m.get("text")),
            m.get("dlr") or "",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
