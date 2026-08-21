"""RED — #1848 A2: der Ortsvergleich speichert und liest die Ausblick-Auswahl
als Kennungen.

SPEC: docs/specs/modules/feat_1848_a2_ausblick_kennungen.md — AC-9
KONTEXT: docs/context/feat-1848-a2-outlook-kennungen.md

Echter Rundlauf ueber die Persistenz: Preset-Datei in ``briefings/`` (so legt
die Go-API sie ab — ``display_config`` ist dort ein opakes Blob mit flachem
Merge, es gibt keine Go-seitige Normalisierung, R-A2-6) ->
``load_compare_presets()`` -> ``resolve_compare_render_options()`` ->
``render_compare_email()``. Derselbe Weg, den Vorschau und Versand teilen
(``compare_preview_service.py:204``).

Kern-Schicht: echte DTOs, echter Renderpfad, kein Netz, kein Mock-Framework.
Pfadregel #1409.
"""
from __future__ import annotations

import json
import re
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _pfad in (REPO_ROOT, REPO_ROOT / "src"):
    if str(_pfad) not in sys.path:
        sys.path.insert(0, str(_pfad))

AUSWAHL = ["temperature", "wind"]

# Eine Spannen-Zelle ist genau "Zahl/Zahl" — die Einheit "km/h" enthaelt zwar
# ebenfalls einen Schraegstrich, passt auf dieses Muster aber nicht.
_SPANNE = re.compile(r"^-?\d+(?:[.,]\d+)?/-?\d+(?:[.,]\d+)?$")


def _kennungen(auswahl):
    """Kennungsfolge — unabhaengig von der Traegerform der Eintraege."""
    if auswahl is None:
        return None
    return [e if isinstance(e, str)
            else (e.get("metric_id") if isinstance(e, dict) else e)
            for e in auswahl]


def _abgelegtes_preset(tmp_path, auswahl) -> tuple[str, str]:
    """Legt ein Vergleichs-Preset genau so ab, wie es auf der Platte liegt."""
    user_id = f"a2-cmp-{uuid.uuid4().hex[:8]}"
    preset_id = f"cp-{uuid.uuid4().hex[:8]}"
    ordner = Path(tmp_path) / "users" / user_id / "briefings"
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / f"{preset_id}.json").write_text(json.dumps({
        "id": preset_id,
        "kind": "vergleich",
        "name": "Ausblick-Kennungen",
        "user_id": user_id,
        "location_ids": ["innsbruck"],
        "schedule": "daily",
        "profil": "SUMMER_TREKKING",
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-01-01T00:00:00Z",
        "display_config": {"outlook_metrics": list(auswahl)},
    }), encoding="utf-8")
    return user_id, preset_id


def test_ac9_ortsvergleich_rundlauf_temperatur_als_spanne_wind_als_einzelwert(tmp_path):
    """AC-9: Given ein Ortsvergleich, in dem der Nutzer 'Temperatur' und
    'Wind' fuer den Ausblick waehlt / When er speichert und anschliessend die
    Vorschau oeffnet / Then zeigt die Vorschau eine Temperatur-Spalte als
    Spanne und eine Wind-Spalte als Einzelwert — die Auswahl kommt also
    unveraendert durch Speichern und Wiederlesen zurueck.

    Die beiden Groessen sind bewusst gemischt: ``temperature`` traegt zwei
    Auswertungen (Tief UND Hoch, die zu EINER Spannen-Spalte verschmelzen),
    ``wind`` genau eine. Ein Ableiter, der jeder Kennung dieselbe Spaltenform
    gibt, faellt hier auf.
    """
    from app.loader import compare_preset_to_dict, load_compare_presets
    from output.renderers.comparison import render_compare_email
    from services.report_config_resolver import resolve_compare_render_options
    from tests.tdd.test_compare_outlook_metric_selection import (
        _body_rows, _headers, _outlook_tables, _result,
    )

    user_id, preset_id = _abgelegtes_preset(tmp_path, AUSWAHL)

    presets = load_compare_presets(user_id, data_root=tmp_path)
    assert len(presets) == 1 and presets[0].id == preset_id, (
        f"Das abgelegte Preset liess sich nicht wieder laden: {presets!r}"
    )
    roh = compare_preset_to_dict(presets[0])
    assert roh["display_config"]["outlook_metrics"] == AUSWAHL, (
        "Die gespeicherte Auswahl kam als "
        f"{roh['display_config']['outlook_metrics']!r} statt {AUSWAHL!r} von "
        "der Platte zurueck (AC-9)."
    )

    opts = resolve_compare_render_options(roh)
    assert opts.outlook_enabled, (
        f"Die Kennungsauswahl {AUSWAHL!r} hat den Ausblick-Block abgeschaltet "
        "(outlook_enabled=False). Eine gefuellte Auswahl kollabiert im "
        "Aufloeser zu [] und wirkt dadurch wie 'bewusst geleert' (AC-9, M5)."
    )
    assert _kennungen(opts.outlook_metrics) == AUSWAHL, (
        f"Aufgeloest wurde {opts.outlook_metrics!r} statt {AUSWAHL!r} — die "
        "Auswahl kommt nicht unveraendert durch Speichern und Wiederlesen "
        "zurueck (AC-9)."
    )

    html, _text = render_compare_email(
        _result(), outlook_enabled=opts.outlook_enabled,
        outlook_metrics=opts.outlook_metrics,
    )
    tabellen = _outlook_tables(html)
    assert tabellen, (
        "Die Vergleichs-Mail enthaelt keine Ausblick-Tabelle (AC-9)."
    )
    kopf = _headers(tabellen[0])
    zeilen = _body_rows(tabellen[0])
    assert len(kopf) == 3 and zeilen, (
        f"Die Ausblick-Tabelle hat die Kopfzeile {kopf!r}. Aus zwei Kennungen "
        "muessen genau zwei Wert-Spalten entstehen (neben 'Tag') — Tief und "
        "Hoch der Temperatur gehoeren in dieselbe Zelle (AC-9)."
    )

    temperatur, wind = zeilen[0][1], zeilen[0][2]
    assert _SPANNE.match(temperatur), (
        f"Die Temperatur-Zelle lautet {temperatur!r} statt einer Spanne der "
        f"Form '6/18'. Gesamte Zeile: {zeilen[0]!r} (AC-9)."
    )
    assert not _SPANNE.match(wind), (
        f"Die Wind-Zelle lautet {wind!r} und hat die Form einer Spanne. "
        "'wind' traegt genau eine Auswertung und muss ein Einzelwert bleiben "
        f"(AC-9). Gesamte Zeile: {zeilen[0]!r}"
    )
