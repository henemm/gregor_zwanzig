"""RED test for Bug #1257: catalog metric_id → AlertMetric forward mapping.

Two vocabularies exist without a translator: the metric catalog (`gust`,
`precipitation`, `temperature`, ...) and `AlertMetric` (`wind_gust`,
`precipitation_sum`, ...). `_ALERT_METRIC_TO_CATALOG_ID` in
`src/services/weather_change_detection.py` already provides the backward
mapping (AlertMetric → tuple of catalog ids). The fix introduces an explicit,
named FORWARD mapping `catalog_id_to_alert_metrics()` (catalog id → set of
alertable AlertMetric values), computed as the inverse of
`_ALERT_METRIC_TO_CATALOG_ID`, filtered to the Go-side alertable vocabulary
(`AlertableMetrics`): wind_gust, precipitation_sum, temperature_min,
temperature_max, snow_line, thunder_level.

This test MUST fail right now with an ImportError, because
`catalog_id_to_alert_metrics` does not exist yet (TDD RED, Phase 5).

No mocks — deterministic core-layer test against the real module dict.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.metric_catalog import get_metric
from app.models import AlertMetric
from services.weather_change_detection import (
    _ALERT_METRIC_TO_CATALOG_ID,
    catalog_id_to_alert_metrics,
)

# Go-side alertable vocabulary (AlertableMetrics), mirrored here to detect drift.
_ALERTABLE_METRIC_VALUES = {
    "wind_gust",
    "precipitation_sum",
    "temperature_min",
    "temperature_max",
    "snow_line",
    "thunder_level",
}


def test_gust_maps_to_wind_gust():
    assert catalog_id_to_alert_metrics()["gust"] == {"wind_gust"}


def test_precipitation_maps_to_precipitation_sum():
    assert catalog_id_to_alert_metrics()["precipitation"] == {"precipitation_sum"}


def test_thunder_maps_to_thunder_level():
    assert catalog_id_to_alert_metrics()["thunder"] == {"thunder_level"}


def test_temperature_maps_to_both_min_and_max():
    assert catalog_id_to_alert_metrics()["temperature"] == {
        "temperature_min",
        "temperature_max",
    }


def test_snowfall_limit_maps_to_snow_line():
    assert catalog_id_to_alert_metrics()["snowfall_limit"] == {"snow_line"}


def test_freezing_level_maps_to_snow_line():
    assert catalog_id_to_alert_metrics()["freezing_level"] == {"snow_line"}


def test_forward_mapping_is_exact_inverse_of_backward_mapping():
    """Drift guard: forward mapping must equal the computed inverse of
    _ALERT_METRIC_TO_CATALOG_ID, filtered to the alertable vocabulary.

    This keeps Go (AlertableMetrics) and Python (_ALERT_METRIC_TO_CATALOG_ID)
    in sync automatically — if either side changes without updating the other,
    this test fails.
    """
    expected: dict[str, set[str]] = {}
    for metric, catalog_ids in _ALERT_METRIC_TO_CATALOG_ID.items():
        if metric.value not in _ALERTABLE_METRIC_VALUES:
            continue
        for catalog_id in catalog_ids:
            expected.setdefault(catalog_id, set()).add(metric.value)

    assert catalog_id_to_alert_metrics() == expected

    # Sanity: every value produced is a real AlertMetric value in the
    # alertable vocabulary, and non-alertable metrics (e.g. CAPE, VISIBILITY,
    # FRESH_SNOW, *_CHANGE) never leak into the forward mapping.
    all_values = {v for values in catalog_id_to_alert_metrics().values() for v in values}
    assert all_values <= _ALERTABLE_METRIC_VALUES
    assert all_values == {m.value for m in AlertMetric} & _ALERTABLE_METRIC_VALUES


# ─────────────────────────────────────────────────────────────────────────────
# Issue #1387: DRITTE Schicht — die Frontend-Bruecke.
#
# Dieselbe Abbildung (Katalog-ID -> alarmfaehige Metrik) existiert dreimal:
# Python (catalog_id_to_alert_metrics oben), Go
# (internal/model/trip.go::catalogIDToAlertMetrics) und Frontend
# (ROUTE_CORRIDOR_CATALOG_IDS) — letztere entscheidet, welche Metriken der
# Reiter "Wertebereiche" unter "+ Metrik" anbietet. Die Frontend-Kopie war
# gedriftet (freezing_level fehlte -> Nullgradgrenze aktiviert, aber kein
# Schneefallgrenzen-Bereich waehlbar). Ohne Waechter driftet sie wieder.
#
# Deckungsgrad, ehrlich benannt:
#   - Python <-> Frontend: ab hier testgeprueft (die Tests unten).
#   - Go: weiterhin eine VON HAND gespiegelte Kopie OHNE automatische Pruefung.
#     Auch _ALERTABLE_METRIC_VALUES (Zeilen 31-39, Go-Vokabular AlertableMetrics)
#     ist ein von Hand gespiegeltes Python-Literal — kein Test liest oder
#     fuehrt Go-Quelltext aus. Aenderungen an der Go-Tabelle muessen weiterhin
#     manuell hierher und ins Frontend nachgezogen werden.
#
# Geprueft wird die BEDEUTUNG: geparste Schluessel/Werte der TS-Konstante gegen
# catalog_id_to_alert_metrics() — kein blosser String-Presence-Check.
# ─────────────────────────────────────────────────────────────────────────────

_REPO = Path(__file__).resolve().parents[2]
_FE_BRIDGE = (
    _REPO / "frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts"
)

# Begruendete, benannte Ausnahme (KEIN stiller Filter): "temperature_cold" ist
# der interne Kaeltealarm-Eintrag des Katalogs mit selectable=False
# (src/app/metric_catalog.py) — er erscheint nie im Reiter "Wetter-Metriken",
# kann also nie aktiviert werden und braucht darum keine Frontend-Bruecke.
# Wird er je selectable, schlaegt test_frontend_exception_is_still_justified an.
_FE_BRIDGE_EXCEPTIONS = {"temperature_cold"}

# Zweite, eigens begruendete Ausnahme (Issue #1425 S2 Teil 2, Scheibe B; die
# obige passt NICHT, denn sie verlangt "nicht selectable" — Gewitter bleibt im
# Wetter-Metriken-Reiter waehlbar):
#
# Fuer Gewitter laufen die beiden Bruecken ab dieser Scheibe bewusst
# auseinander. Die Wertebereiche-Zeile zieht auf den ordinalen Katalog-Eintrag
# `thunder_level_max` (kein/mittel/hoch) um — ein Prozent-Bereich 0-100 gegen
# einen Ordinal-Stundenwert 0/1/2 markierte vorher gerade DANN, wenn Gewitter
# herrschte (Umkehrung). Die Alarm-Empfindlichkeit bleibt unveraendert unter
# `thunder_level` in `metric_alert_levels` — einer seit #1371 von
# `trip.corridors[]` vollstaendig entkoppelten Persistenz.
#
# Eine Ausnahme ohne Waechter waere ein Freifahrtschein: sobald eine der drei
# Bedingungen unten kippt, ist sie hinfaellig bzw. zu breit und
# test_thunder_exception_is_still_justified schlaegt an.
_FE_BRIDGE_THUNDER_EXCEPTION = {"thunder"}

_ALL_FE_BRIDGE_EXCEPTIONS = _FE_BRIDGE_EXCEPTIONS | _FE_BRIDGE_THUNDER_EXCEPTION

# Namentliches Register: Ausnahme-Menge -> der Waechter, der ihre Begruendung
# prueft. Nur was hier steht, darf in _ALL_FE_BRIDGE_EXCEPTIONS landen.
_GUARDED_FE_BRIDGE_EXCEPTIONS = {
    "_FE_BRIDGE_EXCEPTIONS": (
        _FE_BRIDGE_EXCEPTIONS,
        "test_frontend_exception_is_still_justified",
    ),
    "_FE_BRIDGE_THUNDER_EXCEPTION": (
        _FE_BRIDGE_THUNDER_EXCEPTION,
        "test_thunder_exception_is_still_justified",
    ),
}


def _fe_bridge_exceptions() -> set[str]:
    """Gibt die Bruecken-Ausnahmen NUR heraus, wenn jede aus einer bewachten
    Menge stammt (Adversary-Befund F002, MEDIUM).

    Platzierung, bewusst KEIN eigener Test: ein eigener Test liesse sich
    abwaehlen (`-k`, `-m`, Skip) oder schlicht loeschen, waehrend die Ausnahme
    in test_frontend_bridge_matches_python_forward_mapping weiterwirkt und dort
    Drift verdeckt — genau die Luecke, um die es geht. Als einziger Zugriffsweg
    auf die Ausnahmen laeuft die Pruefung dagegen immer dann, wenn die Ausnahme
    ueberhaupt Wirkung entfaltet: Wer ausnimmt, hat das Register passiert.
    """
    registered: set[str] = set().union(
        *(ids for ids, _ in _GUARDED_FE_BRIDGE_EXCEPTIONS.values())
    )
    hint = (
        "Jede von der Frontend-Bruecke ausgenommene Katalog-ID verdeckt fuer "
        "diese ID JEDE kuenftige Drift. Darum sind drei Schritte Pflicht — "
        "Vorbild ist der Gewitter-Fall:\n"
        "  1. eigene Ausnahme-Menge mit Begruendungs-Kommentar anlegen "
        "(Vorbild: _FE_BRIDGE_THUNDER_EXCEPTION),\n"
        "  2. eigenen Rechtfertigungs-Waechter schreiben, der rot wird, sobald "
        "der Grund entfaellt (Vorbild: "
        "test_thunder_exception_is_still_justified),\n"
        "  3. Menge UND Waechter in _GUARDED_FE_BRIDGE_EXCEPTIONS eintragen — "
        "erst dann darf die ID in _ALL_FE_BRIDGE_EXCEPTIONS stehen.\n"
        f"Bewacht sind derzeit: "
        f"{ {n: g for n, (_, g) in _GUARDED_FE_BRIDGE_EXCEPTIONS.items()} }"
    )
    assert _ALL_FE_BRIDGE_EXCEPTIONS == registered, (
        "_ALL_FE_BRIDGE_EXCEPTIONS ist nicht mehr exakt die Vereinigung der "
        "bewachten Ausnahme-Mengen.\n"
        f"  unbewacht ausgenommen: {sorted(_ALL_FE_BRIDGE_EXCEPTIONS - registered)}\n"
        f"  bewacht, aber nicht angewandt: {sorted(registered - _ALL_FE_BRIDGE_EXCEPTIONS)}\n"
        + hint
    )
    for name, (_, guard) in _GUARDED_FE_BRIDGE_EXCEPTIONS.items():
        assert guard in globals(), (
            f"Das Register nennt fuer {name} den Waechter '{guard}' — den gibt "
            "es in dieser Datei nicht (umbenannt oder geloescht?). Eine "
            "Ausnahme ohne lebenden Waechter ist ein Freifahrtschein.\n" + hint
        )
    return _ALL_FE_BRIDGE_EXCEPTIONS


def _read_ts_block(name: str) -> str:
    src = _FE_BRIDGE.read_text(encoding="utf-8")
    match = re.search(rf"const {name}[^=]*=\s*[\{{\[](.*?)\n[\}}\]];", src, re.DOTALL)
    assert match, f"{name} nicht in {_FE_BRIDGE.name} gefunden — Umbenennung?"
    return re.sub(r"//[^\n]*", "", match.group(1))


def _frontend_bridge() -> dict[str, set[str]]:
    """ROUTE_CORRIDOR_CATALOG_IDS aus dem TS-Quelltext als Daten lesen.

    Schluessel duerfen mit ODER ohne Anfuehrungszeichen geschrieben sein
    (`freezing_level:` wie `'freezing_level':`) — sonst wuerde eine spaetere
    Prettier-/Lint-Regel den Waechter falsch-rot machen statt echte Drift zu
    melden (Adversary-Befund F001, LOW).
    """
    body = _read_ts_block("ROUTE_CORRIDOR_CATALOG_IDS")
    parsed = {
        key: set(re.findall(r"['\"]([^'\"]+)['\"]", values))
        for key, values in re.findall(r"['\"]?(\w+)['\"]?\s*:\s*\[([^\]]*)\]", body)
    }
    assert parsed, "ROUTE_CORRIDOR_CATALOG_IDS liess sich nicht parsen"
    return parsed


def test_frontend_bridge_matches_python_forward_mapping():
    """Katalog-ID -> alarmfaehige Metrik: Frontend == Python, ID fuer ID.

    (Go bleibt eine handgespiegelte Kopie ohne automatische Pruefung — s.
    Block-Kommentar oben.)
    """
    exceptions = _fe_bridge_exceptions()
    expected = {
        cid: metrics
        for cid, metrics in catalog_id_to_alert_metrics().items()
        if cid not in exceptions
    }
    actual = {
        cid: metrics
        for cid, metrics in _frontend_bridge().items()
        if cid not in exceptions
    }
    assert actual == expected, (
        "ROUTE_CORRIDOR_CATALOG_IDS (corridorEditorState.ts) weicht von "
        "catalog_id_to_alert_metrics() ab — fehlende Katalog-IDs verschwinden "
        f"lautlos aus '+ Metrik'.\nFrontend: {actual}\nBackend:  {expected}"
    )


def test_frontend_bridge_targets_exist_in_route_metric_defs():
    """Jede Ziel-Metrik der Bruecke hat auch eine Zeilen-Definition."""
    defined = set(re.findall(r"metric:\s*'([^']+)'", _read_ts_block("ROUTE_METRIC_DEFS")))
    targets = {m for metrics in _frontend_bridge().values() for m in metrics}
    assert targets <= defined, (
        f"Bruecke zeigt auf Metriken ohne ROUTE_METRIC_DEFS-Eintrag: {targets - defined}"
    )


def test_frontend_exception_is_still_justified():
    """Die Ausnahme gilt nur, solange sie im Katalog nicht waehlbar ist."""
    assert _FE_BRIDGE_EXCEPTIONS == {"temperature_cold"}, (
        "_FE_BRIDGE_EXCEPTIONS wurde erweitert auf "
        f"{sorted(_FE_BRIDGE_EXCEPTIONS)}. Diese Menge traegt GENAU EINE "
        "Begruendung: 'temperature_cold' ist nicht selectable. Wer eine weitere "
        "Katalog-ID von der Frontend-Bruecke ausnimmt, verdeckt damit fuer diese "
        "ID jede kuenftige Drift — deshalb sind drei Schritte Pflicht:\n"
        "  1. eigene Ausnahme-Menge anlegen (Vorbild: "
        "_FE_BRIDGE_THUNDER_EXCEPTION) statt diese hier aufzublaehen,\n"
        "  2. den Grund als Kommentar darueber schreiben (warum die Bruecke "
        "fuer genau diese ID entfallen darf),\n"
        "  3. einen eigenen Rechtfertigungs-Waechter schreiben, der rot wird, "
        "sobald der Grund entfaellt (Vorbild: "
        "test_thunder_exception_is_still_justified).\n"
        "Danach diese Zusicherung UNVERAENDERT lassen."
    )
    for catalog_id in _FE_BRIDGE_EXCEPTIONS:
        assert not get_metric(catalog_id).selectable, (
            f"'{catalog_id}' ist jetzt selectable — die Ausnahme in "
            "_FE_BRIDGE_EXCEPTIONS ist hinfaellig, Frontend-Bruecke ergaenzen."
        )


def _route_metric_def_ids() -> set[str]:
    return set(re.findall(r"metric:\s*'([^']+)'", _read_ts_block("ROUTE_METRIC_DEFS")))


def test_thunder_exception_is_still_justified():
    """Waechter zur Gewitter-Ausnahme (Issue #1425 S2 Teil 2, Scheibe B).

    Sie ist NUR gerechtfertigt, solange alle drei Bedingungen gelten:

    1. Die Wertebereiche-Seite fuehrt Gewitter nicht mehr ueber die Bruecke —
       weder als Bruecken-Schluessel `thunder` noch als fest verdrahtete
       Zeilen-Definition `thunder_level` (sonst waere die Ausnahme UNNOETIG und
       wuerde echte Drift verdecken).
    2. Es gibt tatsaechlich den ordinalen Katalog-Ersatz, auf den die Zeile
       umgezogen ist: `thunder_level_max` mit `metric_id == "thunder"` und
       `kind == "ordinal"` (sonst zeigte die Zeile ins Leere).
    3. Die Alarm-Seite fuehrt Gewitter unveraendert unter `thunder_level`
       (sonst waere die Ausnahme ZU BREIT und verdeckte eine Alarm-Drift).
    """
    # (0) Die Ausnahme deckt GENAU 'thunder' — die drei Bedingungen unten
    #     begruenden nichts anderes. Jede weitere ID braucht ihre eigene Menge,
    #     ihre eigene Begruendung und ihren eigenen Waechter.
    assert _FE_BRIDGE_THUNDER_EXCEPTION == {"thunder"}, (
        "_FE_BRIDGE_THUNDER_EXCEPTION wurde erweitert auf "
        f"{sorted(_FE_BRIDGE_THUNDER_EXCEPTION)}. Die Bedingungen (1)-(3) "
        "dieses Waechters pruefen ausschliesslich Gewitter — eine zusaetzliche "
        "ID waere hier ungeprueft und ihre Drift bliebe lautlos. Deshalb sind "
        "drei Schritte Pflicht:\n"
        "  1. eigene Ausnahme-Menge anlegen statt diese hier zu erweitern,\n"
        "  2. den Grund als Kommentar darueber schreiben (warum die Bruecke "
        "fuer genau diese ID entfallen darf),\n"
        "  3. einen eigenen Rechtfertigungs-Waechter nach dem Muster dieses "
        "Tests schreiben, der rot wird, sobald der Grund entfaellt.\n"
        "Danach diese Zusicherung UNVERAENDERT lassen."
    )

    # (1) Wertebereiche-Seite: Gewitter ist aus der Bruecke ausgezogen.
    bridge = _frontend_bridge()
    assert "thunder" not in bridge, (
        "'thunder' steht wieder in ROUTE_CORRIDOR_CATALOG_IDS — dann ist die "
        "Ausnahme _FE_BRIDGE_THUNDER_EXCEPTION hinfaellig und muss ENTFERNT "
        "werden, sonst verdeckt sie echte Drift."
    )
    assert "thunder_level" not in _route_metric_def_ids(), (
        "ROUTE_METRIC_DEFS fuehrt wieder eine Gewitter-Zeile unter dem "
        "Prozent-Schluessel 'thunder_level' — die Begruendung der Ausnahme "
        "(Umzug auf den ordinalen Katalog-Eintrag) gilt dann nicht mehr."
    )

    # (2) Der Ersatz existiert und ist ordinal.
    from output.renderers.compare_metric_catalog import COMPARE_METRIC_CATALOG

    ersatz = [e for e in COMPARE_METRIC_CATALOG if e["key"] == "thunder_level_max"]
    assert ersatz, (
        "Der Katalog-Eintrag 'thunder_level_max' fehlt — die Wertebereiche-Zeile "
        "fuer Gewitter haette gar kein Ziel mehr."
    )
    assert ersatz[0].get("metric_id") == "thunder", (
        "'thunder_level_max' zeigt nicht mehr auf die Katalog-Groesse 'thunder' "
        "— die Zuordnung Wertebereich -> Spalte waere gebrochen."
    )
    assert ersatz[0].get("kind") == "ordinal", (
        "'thunder_level_max' ist nicht mehr ordinal — der ganze Grund fuer die "
        "Namensraum-Trennung (Prozent vs. Stufen) faellt damit weg."
    )

    # (3) Alarm-Seite unveraendert.
    assert catalog_id_to_alert_metrics()["thunder"] == {"thunder_level"}, (
        "Die Alarm-Seite fuehrt Gewitter nicht mehr unter 'thunder_level' — die "
        "Ausnahme ist damit zu breit und verdeckt eine echte Alarm-Drift."
    )
