# doc-compliance-test
"""Sonnen-Plausibilitaet des Briefing-Mail-Pruefers (#1432).

Zwei Fehlerbilder, eine Ursache: Jede Stundentabelle steht doppelt im HTML
(Desktop-Fassung + byte-identische Handy-Fassung aus demselben
_render_html_table-Aufruf). Der Pruefer summierte ueber ALLE Tabellenbloecke:

1. Roh-Modus: Summe exakt verdoppelt -> falscher Alarm bei korrekter Mail
   (Beleg #1432: "Pill 552 min vs. Tabelle 1104 min", 1104 = 2 x 552).
2. Emoji-Modus (Standardfall): Spalte ohne 'X h'-Zahlen -> Pruefung wurde
   uebersprungen und hat faktisch nie etwas geprueft.

Erwartung nach Fix: identische Tabellenbloecke werden dedupliziert (echte
Mehr-Etappen-Tabellen mit unterschiedlichen Zeitzellen summieren weiter),
und im Emoji-Modus greift eine Obergrenzen-Pruefung ueber die Sonne-Spalte.

Prueft den PRUEFER (Werkzeug-Compliance), kein Produkt-Verhalten — daher
``# doc-compliance-test``; die HTML-Prueflinge sind synthetisch.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_HERE = Path(__file__).resolve()
_VALIDATOR = _HERE.parents[2] / ".claude" / "hooks" / "briefing_mail_validator.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("bmv1432", str(_VALIDATOR))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _tbl(rows: list[tuple[str, str]]) -> str:
    trs = "".join(f"<tr><td>{t}</td><td>{s}</td></tr>" for t, s in rows)
    return (
        "<table><tr><th>Zeit</th><th>Sonne</th></tr>" + trs + "</table>"
    )


def _mail(pill_min: int, desktop_tables: list[str]) -> str:
    """Baut das Renderer-Muster nach: Pill + je Tabelle Desktop- UND
    byte-identische Mobile-Fassung (nur anders gewickelt)."""
    parts = [f"<span>Sonne {pill_min} min</span>"]
    for tbl in desktop_tables:
        parts.append('<div class="section desktop-only">' + tbl + "</div>")
        parts.append(
            '<div class="mobile-compact">'
            '<div style="overflow-x:auto;">' + tbl + "</div></div>"
        )
    return "".join(parts)


def test_doppelt_gerenderte_tabelle_zaehlt_einfach():
    """Given Pill 552 min und eine 9.2-h-Tabelle in Desktop- UND
    Mobile-Fassung / When der Pruefer die Plausibilitaet prueft / Then
    meldet er KEINEN Widerspruch (#1432 Fall 1: vorher 1104 vs. 552)."""
    v = _load_validator()
    tbl = _tbl([("09:00", "4.6 h"), ("10:00", "4.6 h")])
    errors = v._check_metric_plausibility(_mail(552, [tbl]))
    assert errors == []


def test_zwei_echte_etappen_summieren_weiter():
    """Given zwei VERSCHIEDENE Etappen-Tabellen (andere Zeitzellen) mit je
    4.6 h / When der Pruefer prueft / Then summiert er beide (Dedup frisst
    keine echten Etappen): Pill 552 ist stimmig, Pill 300 widerspricht."""
    v = _load_validator()
    t1 = _tbl([("09:00", "2.3 h"), ("10:00", "2.3 h")])
    t2 = _tbl([("13:00", "2.3 h"), ("14:00", "2.3 h")])
    assert v._check_metric_plausibility(_mail(552, [t1, t2])) == []
    errors = v._check_metric_plausibility(_mail(300, [t1, t2]))
    assert len(errors) == 1 and "Sonne" in errors[0]


def test_emoji_modus_obergrenze_greift():
    """Given Pill 552 min, aber die Sonne-Spalte zeigt nur 4 Emoji-Stunden
    (Obergrenze 240 min) / When der Pruefer prueft / Then schlaegt er an
    (#1432 Fall 2: vorher blind uebersprungen)."""
    v = _load_validator()
    tbl = _tbl(
        [("09:00", "☀️"), ("10:00", "🌤️"), ("11:00", "⛅"), ("12:00", "🌥️")]
    )
    errors = v._check_metric_plausibility(_mail(552, [tbl]))
    assert len(errors) == 1 and "Sonne" in errors[0]


def test_emoji_modus_plausible_pille_bleibt_stumm():
    """Given Pill 180 min bei 8 sonnenfaehigen Emoji-Stunden plus Nacht-,
    Wolken- und Leerzellen / When der Pruefer prueft / Then bleibt er stumm
    (Nacht/dichte Wolken/Leer zaehlen nicht als Fehl-Obergrenze)."""
    v = _load_validator()
    tbl = _tbl(
        [(f"{h:02d}:00", "☀️") for h in range(9, 17)]
        + [("06:00", "☁️"), ("21:00", "🌙"), ("22:00", "–")]
    )
    errors = v._check_metric_plausibility(_mail(180, [tbl]))
    assert errors == []
