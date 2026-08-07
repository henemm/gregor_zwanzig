"""TDD — Fix #1544/#1545, AC-9 (Deckungsgleichheit).

Die eigentliche Zusicherung dieser Scheibe: die Menge der im Trip-Alarme-
Reiter angezeigten Alarm-Identitaeten ist exakt die Menge, die der
Live-Alarm-Detektor fuer denselben Trip tatsaechlich auswertet -- weder mehr
noch weniger.

Spec: docs/specs/modules/fix_1544_1545_trip_alarm_zeilen_ableitung.md
  Acceptance Criteria AC-9.

## Warum diese Datei ALLEIN heute schon gruen ist -- und das auch richtig so
   ist

Anzeige (TypeScript, neue Ableitung `deriveActiveAlertMetricsForTrip`) und
Auswertung (Python, `expand_per_metric_levels()`) liegen in verschiedenen
Sprachen. Ein Test, der die TS-Erwartung in Python nachbaut, wuerde nichts
pruefen -- er spiegelte nur die eigene Annahme zurueck (s. Auftrag zu
diesem Workflow).

Backend-seitig ist an DIESER Scheibe nichts geaendert (Spec, Abschnitt
"Schicht-Hinweis": ausschliesslich Frontend). `expand_per_metric_levels()`
funktioniert also bereits heute korrekt -- diese Datei belegt das nur, sie
kann durch diese Scheibe nicht rot werden.

Das eigentliche RED-Signal fuer AC-9 liegt deshalb NICHT hier, sondern im
TS-Test `frontend/src/lib/components/shared/alarme-tab/__tests__/
trip_active_alert_metrics_derivation.test.ts` (Describe-Block "AC-9"): der
importiert die noch nicht existierende `deriveActiveAlertMetricsForTrip`
und liest DIESELBE Fixture-Datei, die DIESER Test hier erzeugt/verifiziert.
Beide Seiten rechnen unabhaengig gegen ihre eigene Produktivrealitaet und
treffen sich an einem gemeinsamen, aus dem echten Backend gewonnenen
Fixpunkt -- kein Mock des Regel-Erzeugers, keine RPC zwischen den Sprachen.

Diese Datei ist der Anker dieses Fixpunkts: sie haelt das Backend-Ergebnis
fest UND bewacht es als Regression -- eine kuenftige Aenderung an
`expand_per_metric_levels()`/`is_alert_metric_active()`, die die erzeugte
Identitaeten-Menge fuer diesen Zustand veraendert, macht DIESEN Test rot
(Mutations-Gegenprobe: s. unten).

## Wahl des Trip-Zustands

AC-9 verlangt "fuer mindestens einen Trip-Zustand" Deckungsgleichheit --
nicht universell. Ein Zustand mit einem EXPLIZITEN `level: 'off'` wuerde in
der Anzeige (Auswahl x Register, unabhaengig vom Stufenwert) weiterhin eine
Zeile zeigen, waehrend der Regel-Erzeuger dafuer keine Regel baut -- die
Mengen wichen dann bewusst voneinander ab (das ist kein Fehler, sondern
Teil des Vertrags: eine "aus"-Zeile bleibt sichtbar, feuert aber nicht).
Der hier gewaehlte Zustand enthaelt daher KEIN 'off': Temperatur ist aktiv
und hat keinen expliziten Level-Eintrag (Backfill 'standard'), Boeen ist
aktiv mit explizitem 'sensibel', Luftfeuchtigkeit ist aktiv aber nicht
alarmfaehig (Register), CAPE ist im Wetter-Reiter deaktiviert. Fuer GENAU
diesen Zustand muessen beide Mengen identisch sein.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.models import MetricConfig, UnifiedWeatherDisplayConfig
from services.alert_preset import expand_per_metric_levels

# Pfadregel #1409: relativ zu DIESER Datei aufgeloest (services -> unit ->
# tests -> Repo-Wurzel), kein fester Hauptrepo-Pfad -- sonst prueft dieser
# Test aus einem Worktree die unveraenderte Hauptrepo-Kopie der Fixture.
_FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "src"
    / "lib"
    / "components"
    / "shared"
    / "alarme-tab"
    / "__tests__"
    / "fixtures"
    / "ac9_trip_state.json"
)


def _load_fixture() -> dict:
    assert _FIXTURE_PATH.exists(), (
        f"AC-9-Fixture fehlt: {_FIXTURE_PATH}. Sie wird von BEIDEN Seiten "
        "(dieser Python-Test UND der TS-Test trip_active_alert_metrics_"
        "derivation.test.ts, Describe-Block AC-9) gelesen."
    )
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def _display_config(fixture: dict) -> UnifiedWeatherDisplayConfig:
    metrics = [
        MetricConfig(metric_id=m["metric_id"], enabled=m["enabled"])
        for m in fixture["metrics"]
    ]
    return UnifiedWeatherDisplayConfig(
        trip_id="ac9-fixture",
        metrics=metrics,
        metric_alert_levels=dict(fixture["metric_alert_levels"]),
    )


def test_fixture_fields_are_self_consistent():
    """Rohdaten-Sanity: die Fixture ist kein erfundenes Format -- die
    Gegenprobe unten haengt vollstaendig an ihrer korrekten Struktur."""
    fixture = _load_fixture()
    assert set(fixture.keys()) >= {
        "metrics",
        "metric_alert_levels",
        "expected_alert_identities",
    }
    assert fixture["metric_alert_levels"], "Fixture sollte mindestens eine explizite Stufe enthalten (sonst prueft AC-4/Backfill nicht mit)."
    metric_ids = {m["metric_id"] for m in fixture["metrics"]}
    assert "cape" in metric_ids and any(
        m["metric_id"] == "cape" and m["enabled"] is False for m in fixture["metrics"]
    ), "Fixture braucht eine EXPLIZIT deaktivierte Groesse (CAPE), sonst prueft AC-3 im Backend-Pfad nicht mit."


def test_backend_produces_exactly_the_fixtures_expected_identities():
    """Der echte Regel-Erzeuger (kein Mock) erzeugt fuer den Fixture-Zustand
    genau die in `expected_alert_identities` festgehaltene Menge."""
    fixture = _load_fixture()
    display_config = _display_config(fixture)

    rules = expand_per_metric_levels(
        dict(fixture["metric_alert_levels"]), display_config
    )
    got = sorted({str(rule.metric) for rule in rules})

    assert got == sorted(fixture["expected_alert_identities"]), (
        f"expand_per_metric_levels() liefert {got}, die Fixture erwartet "
        f"{sorted(fixture['expected_alert_identities'])}. Beide Seiten "
        "(Python-Backend, TS-Frontend) muessen sich an DIESEM Wert treffen "
        "(AC-9) -- weicht der Backend-Wert ab, ist die Fixture veraltet "
        "oder das Backend hat sich veraendert."
    )


def test_backend_excludes_the_deactivated_metric_and_the_unalertable_one():
    """Gegenprobe zur Kernaussage: CAPE (deaktiviert) und Luftfeuchtigkeit
    (nicht alarmfaehig) duerfen in KEINEM erzeugten Regel-Namen auftauchen
    -- sonst waere die Fixture zufaellig richtig, statt die Trennschaerfe
    tatsaechlich zu belegen."""
    fixture = _load_fixture()
    display_config = _display_config(fixture)

    rules = expand_per_metric_levels(
        dict(fixture["metric_alert_levels"]), display_config
    )
    got = {str(rule.metric) for rule in rules}

    assert "cape" not in got, (
        "CAPE ist im Fixture-Zustand deaktiviert -- eine erzeugte Regel "
        "dafuer waere der Fehler aus Fehlerklasse 3 (vorgetaeuschte Kontrolle)."
    )
    assert "humidity" not in got, (
        "Luftfeuchtigkeit ist laut Register nicht alarmfaehig (ADR-0010) -- "
        "eine erzeugte Regel dafuer waere strukturell unmoeglich und ein "
        "Zeichen dafuer, dass die Fixture nicht mehr zum Register passt."
    )


def test_mutation_guard_missing_backfill_would_be_caught():
    """Mutations-Gegenprobe (CLAUDE.md, PFLICHT): simuliert den Ausfall des
    Backfills fuer aktive Groessen OHNE expliziten Level-Eintrag (Temperatur
    im Fixture-Zustand) durch Aufruf OHNE `display_config` -- das alte
    Verhalten (keine Filterung, kein Backfill). Belegt, dass der Test bei
    einer echten Regression tatsaechlich rot werden KANN, nicht nur
    zufaellig gruen ist."""
    fixture = _load_fixture()

    # Ohne display_config: kein Backfill, keine Aktivierungs-Pruefung
    # (Doku von expand_per_metric_levels(), Zeile "Ohne display_config
    # (Default None): altes Verhalten"). Temperatur (kein expliziter
    # Eintrag) faellt dann komplett weg -- exakt die Regression, die AC-9
    # verhindern soll.
    rules_ohne_backfill = expand_per_metric_levels(
        dict(fixture["metric_alert_levels"]), None
    )
    got_ohne_backfill = {str(rule.metric) for rule in rules_ohne_backfill}

    assert got_ohne_backfill != set(fixture["expected_alert_identities"]), (
        "Diese Gegenprobe muss selbst eine Abweichung zeigen -- sonst waere "
        "der Haupttest oben nicht in der Lage, einen fehlenden Backfill zu "
        "fangen (Mutations-Pflicht)."
    )
    assert "temperature_min" not in got_ohne_backfill
    assert "temperature_max" not in got_ohne_backfill
    assert "temperature_change" not in got_ohne_backfill
