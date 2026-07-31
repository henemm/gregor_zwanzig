"""Zweiteiliger Waechter ueber die im Register deklarierte Alarm-Identitaet
(#1435 Etappe E1a-1, AC-5) plus Python-Nachweis der drei Neuzugaenge (AC-2).

Alarmfaehigkeit haengt am Paar (Groesse, Auswertung) und wird ab E1a im
zentralen Register deklariert (``MetricDefinition.alert_metrics`` je Auswertung,
``change_alert_metric`` fuer Aenderungsraten). Zwei Pruefungen:

1. **Auswertbarkeit** — jede deklarierte Identitaet muss von der
   Auswertungskette (``weather_change_detection._ALERT_METRIC_TO_CATALOG_ID``)
   erreichbar sein. Sonst waere sie ein Bedienelement ohne Wirkung
   (``is_alert_metric_active()`` liefert dann strukturell immer ``False``).
2. **Vollstaendigkeit/Eindeutigkeit** — die deklarierten Identitaeten sind
   exakt die 12 auswertbaren Ziel-Groessen, keine doppelt vergeben.

Beide mit Wirkungsnachweis auf KUENSTLICH veraenderten Registry-Kopien
(``dataclasses.replace``; die echte Registry wird nie mutiert) — Vorbild:
``test_compare_metric_catalog_consistency.py::
test_guard_actually_fails_when_a_catalog_metric_has_no_cv2_row``.
Kern-Schicht, deterministisch: kein Netz, kein Mock, kein ``patch()``.
SPEC: docs/specs/modules/feat_1435_e1a_alarmfaehigkeit_register.md
"""
from __future__ import annotations

from dataclasses import replace

from app.metric_catalog import _METRICS
from app.models import AlertMetric
from services.compare_alert import _SUMMARY_KEY_TO_CATALOG_ID
from services.weather_change_detection import _ALERT_METRIC_TO_CATALOG_ID

# Ziel-Vokabular, woertlich gespiegelt aus
# frontend/src/lib/components/alerts-tab/alertMetricTable.ts:202-216
# (kein automatisierter Cross-Language-Waechter, s. Spec Known Limitations).
ALERTABLE_METRICS: tuple[str, ...] = (
    "wind_gust", "precipitation_sum", "thunder_level", "temperature_min",
    "temperature_max", "temperature_change", "wind_change",
    "precipitation_change", "fresh_snow", "cape", "visibility", "humidity",
    "freezing_level",
)
EVALUABLE: set[str] = {m.value for m in _ALERT_METRIC_TO_CATALOG_ID}
TARGET: set[str] = {m for m in ALERTABLE_METRICS if m in EVALUABLE}


def _declared(metrics: list) -> list[tuple[str, str]]:
    """(Herkunft, Alarm-Identitaet) je Deklaration — die geprueften Rohdaten."""
    found: list[tuple[str, str]] = []
    for m in metrics:
        for aggregation, identity in sorted(m.alert_metrics.items()):
            found.append((f"{m.id}.alert_metrics[{aggregation!r}]", identity))
        if m.change_alert_metric:
            found.append((f"{m.id}.change_alert_metric", m.change_alert_metric))
    return found


def _registry_with(metric_id: str, **changes) -> list:
    """Registry-Kopie mit EINER veraenderten Groesse; Original bleibt unberuehrt."""
    return [replace(m, **changes) if m.id == metric_id else m for m in _METRICS]


def _unevaluable(declared: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [(src, i) for src, i in declared if i not in EVALUABLE]


def _duplicates(declared: list[tuple[str, str]]) -> list[str]:
    seen: set[str] = set()
    dupes: list[str] = []
    for _, identity in declared:
        if identity in seen and identity not in dupes:
            dupes.append(identity)
        seen.add(identity)
    return dupes


def test_every_declared_alert_identity_is_evaluable():
    """AC-5 Teil 1: keine deklarierte Identitaet ohne Auswertungspfad."""
    offenders = _unevaluable(_declared(_METRICS))
    assert not offenders, (
        "Im Register deklarierte Alarm-Identitaeten, die die Auswertungskette "
        "nicht kennt (Bedienelement ohne Wirkung — is_alert_metric_active() "
        f"liefert dort immer False): {offenders}"
    )


def test_guard_names_a_declared_but_unevaluable_identity():
    """AC-5 Wirkungsnachweis (a): Luftfeuchtigkeit kuenstlich deklariert →
    derselbe Vergleich wird rot und nennt die tote Identitaet."""
    tampered = _registry_with("humidity", alert_metrics={"avg": "humidity"})
    offenders = _unevaluable(_declared(tampered))
    assert offenders == [("humidity.alert_metrics['avg']", "humidity")], (
        f"Waechter erkennt die kuenstlich deklarierte, unauswertbare "
        f"Identitaet 'humidity' nicht: {offenders}"
    )
    assert not _unevaluable(_declared(_METRICS)), (
        "Gegenprobe fehlgeschlagen: die echte Registry ist selbst betroffen — "
        "der Wirkungsnachweis waere dann nicht aussagekraeftig."
    )


def test_declared_identities_are_exactly_the_evaluable_target_vocabulary():
    """AC-5 Teil 2: nichts fehlt, nichts doppelt, nichts unbekannt."""
    declared = _declared(_METRICS)
    identities = {i for _, i in declared}
    assert identities == TARGET, (
        f"fehlend: {sorted(TARGET - identities)}, "
        f"unbekannt (nicht im Ziel-Vokabular): {sorted(identities - TARGET)}"
    )
    assert not _duplicates(declared), (
        f"mehrfach vergebene Alarm-Identitaeten: {_duplicates(declared)}"
    )


def test_guard_names_a_missing_identity():
    """AC-5 Wirkungsnachweis (b1): reduzierte Kopie → Fehlstelle wird benannt."""
    tampered = _registry_with("cape", alert_metrics={})
    missing = TARGET - {i for _, i in _declared(tampered)}
    assert missing == {"cape"}, (
        f"Waechter erkennt die kuenstlich entfernte Identitaet 'cape' nicht: "
        f"{missing}"
    )


def test_guard_names_a_duplicate_identity():
    """AC-5 Wirkungsnachweis (b2): doppelte Vergabe → Kollision wird benannt."""
    tampered = _registry_with("wind", alert_metrics={"max": "wind_gust"})
    assert _duplicates(_declared(tampered)) == ["wind_gust"], (
        "Waechter erkennt die kuenstlich doppelt vergebene Identitaet "
        f"'wind_gust' nicht: {_duplicates(_declared(tampered))}"
    )


def test_the_three_newcomers_resolve_and_are_reachable_unlike_humidity():
    """AC-2 (Python-Teil): Temperatur-Minimum, CAPE und Nullgradgrenze loesen
    ueber das Register auf, sind auswertbar UND ueber die alarmausloesende
    Compare-Crosswalk erreichbar — Luftfeuchtigkeit ist beides nicht."""
    from app.metric_catalog import alert_metric_for

    cases = (
        ("temperature", "min", "temperature_min", "temp_min_c"),
        ("cape", "max", "cape", "cape_max_jkg"),
        ("freezing_level", "min", "freezing_level", "freezing_level_m"),
    )
    for metric_id, aggregation, identity, compare_key in cases:
        assert alert_metric_for(metric_id, aggregation) == identity
        assert identity in EVALUABLE, f"{identity} ist nicht auswertbar"
        catalog_id = _SUMMARY_KEY_TO_CATALOG_ID[compare_key]
        assert catalog_id in _ALERT_METRIC_TO_CATALOG_ID[AlertMetric(identity)], (
            f"{compare_key} → {catalog_id} ist von {identity} aus nicht erreichbar"
        )

    assert alert_metric_for("humidity", "avg") is None, (
        "Luftfeuchtigkeit darf keine Alarm-Identitaet tragen (nicht auswertbar)"
    )
    assert "humidity" not in EVALUABLE


def test_alert_metric_for_rejects_uncovered_or_unknown_aggregations():
    """Adversary-Fund F001 (#1435 E1a-1, LOW): der Change-Rueckfall auf
    ``change_alert_metric`` darf nur greifen, wenn die Groesse GAR KEINE
    auswertungsspezifischen Alarm-Identitaeten deklariert -- sonst erbt eine
    fuer die Groesse nicht vorgesehene (oder unbekannte) Auswertung
    stillschweigend die Aenderungsraten-Identitaet einer ANDEREN Auswertung.
    Heute folgenlos, weil der einzige Aufrufer (compare_metric_catalog.py:276)
    nur kuratierte, existierende Paare uebergibt -- ein kuenftiger zweiter
    Aufrufer oder eine kuenftige Katalogzeile waere betroffen."""
    from app.metric_catalog import alert_metric_for

    # Reproduzierter Fall: "avg" ist eine echte, berechnete Auswertung von
    # "temperature" (summary_fields kennt sie), aber NUR min/max haben eine
    # eigene Alarm-Identitaet deklariert -- avg darf NICHT stillschweigend
    # die Aenderungsraten-Identitaet der Groesse erben.
    assert alert_metric_for("temperature", "avg") is None, (
        "temperature/avg erbt faelschlich die Aenderungsraten-Identitaet "
        "'temperature_change', obwohl fuer diese Auswertung keine eigene "
        "Alarm-Identitaet vorgesehen ist"
    )

    # Gleichgelagerter zweiter Fall: "sum" ist fuer "wind" GAR KEINE
    # deklarierte Auswertung (wind kennt nur "max") -- der Rueckfall darf
    # erst recht nicht fuer eine unbekannte Auswertung greifen.
    assert alert_metric_for("wind", "sum") is None, (
        "wind/sum (keine deklarierte Auswertung dieser Groesse) erbt "
        "faelschlich die Aenderungsraten-Identitaet 'wind_change'"
    )

    # Entkreuzung bleibt erhalten: die einzige tatsaechlich deklarierte
    # Auswertung von wind ("max") faellt weiterhin auf die Aenderungsraten-
    # Identitaet zurueck, weil wind GAR KEINE eigenen Auswertungs-
    # Identitaeten kennt.
    assert alert_metric_for("wind", "max") == "wind_change"
