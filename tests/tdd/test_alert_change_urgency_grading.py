"""TDD RED — Wetter-Aenderungsalarme werden wieder abgestuft (Issue #1503).

SPEC: docs/specs/modules/fix_1503_delta_dringlichkeit.md (AC-1..AC-12)

Kernaussage: Der Δ-Detektor berechnet in ``_classify_severity()`` bereits eine
abgestufte Dringlichkeit aus dem Ueberschreitungsfaktor, erreicht diese
Berechnung aber nie -- ``from_alert_rules()`` schreibt fuer JEDE Δ-Regel einen
Vorrang-Eintrag (``severity_overrides[field] = rule.severity``), und
``alert_preset.expand_per_metric_levels()`` setzt dort hart
``AlertSeverity.WARNING``. Ergebnis heute: jede Vorhersage-Aenderung traegt
``ChangeSeverity.MODERATE`` -> Protokoll immer ``"MODERATE"``.

RED-Grund je Test steht im jeweiligen Docstring. Zwei Tests sind bewusst
KEINE RED-Tests und als solche gekennzeichnet:

* ``test_ac2_...`` -- Invariante. Faktor 1,75 liegt heute (Konstante) UND
  kuenftig (Rechnung) bei ``MODERATE``. Der Test faellt zufaellig mit dem
  Ist-Zustand zusammen; sein Wert liegt darin, dass die Mitte nach dem Fix
  nicht wegrutscht. Er belegt fuer sich genommen NICHTS ueber den Bug.
* ``test_ac7_...`` -- Invariante #638: die Einstufung ist Etikett, nie
  Filterkriterium. Gilt heute und muss nach dem Fix weiter gelten.

Mock-frei (CLAUDE.md „Test-Politik"): echte ``DeviationAlertEngine``-,
``TripAlertService``- und ``CompareAlertService``-Laeufe, echte Modelle, echte
Persistenz ueber die pytest-isolierte ``app.loader.get_data_dir()``-Basis
(#1133), Transport ausschliesslich ueber die vorhandene ``mail_sink``-/
``weather_source``-DI-Naht. Kein ``Mock``/``patch``/``MagicMock``, kein Netz
(laeuft unter ``--disable-socket``).

Pfadregel #1409: alle Pruefling-Pfade laufen ueber ``get_data_dir()`` bzw.
werden relativ zu DIESER Testdatei aufgeloest -- nie ueber einen festen
Hauptrepo-Pfad. Einzige bewusste Ausnahme ist ``COMPARE_DATA_ROOT`` aus
``tests/helpers/alert_log_fixtures.py``: der Compare-Preset-Loader liest
cwd-relativ (``load_compare_presets(data_root="data")``) -- die in CLAUDE.md
ausgenommene „geteilte Ablage".
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone

from app.loader import get_briefings_dir, get_data_dir, load_trip, save_location, save_trip
from app.models import (
    AlertMetric,
    AlertRule,
    AlertRuleKind,
    AlertSeverity,
    ChangeSeverity,
    MetricConfig,
    SegmentWeatherSummary,
    ThunderLevel,
    TripReportConfig,
    UnifiedWeatherDisplayConfig,
)
from app.trip import Stage, Trip, Waypoint
from app.user import SavedLocation

from tests.helpers.alert_log_fixtures import (
    COMPARE_DATA_ROOT,
    LAT,
    LON,
    clean_compare_user,
    read_log,
    settings_email_only,
    weather,
)
from tests.helpers.compare_briefings import write_compare_briefings

# Schwellen der Empfindlichkeitsstufe "standard" aus `alert_preset._PRESET_TABLE`.
# Bewusst als benannte Konstanten, damit die Faktoren in den Tests ablesbar sind.
GUST_STANDARD = 20.0        # wind_gust        -> gust_max_kmh
PRECIP_STANDARD = 10.0      # precipitation_sum-> precip_sum_mm
TEMP_MAX_STANDARD = 6.0     # temperature_max  -> temp_max_c


def _user(prefix: str) -> str:
    return f"tdd-1503-{prefix}-{uuid.uuid4().hex[:6]}"


# ───────────────────────── echte Pipeline: Engine-Lauf ──────────────────────

def _point(**summary):
    """Ein Ort mit ausschliesslich den uebergebenen Summary-Werten."""
    from services.point_weather import PointWeatherData

    return PointWeatherData(
        id="p1", name="Pruefort", lat=LAT, lon=LON, timeseries=None,
        aggregated=SegmentWeatherSummary(**summary),
        fetched_at=datetime.now(timezone.utc), provider="tdd-1503",
    )


def _evaluate(levels: dict[str, str], alt: dict, neu: dict):
    """Voller Engine-Lauf ueber die echte Kette
    ``metric_alert_levels`` -> ``expand_per_metric_levels`` ->
    ``from_alert_rules`` -> ``detect_changes`` -> ``_highest_severity``.
    Kein Direktaufruf von ``_classify_severity()`` -- geprueft wird dort, wo
    die Zusicherung WIRKT."""
    from services.deviation_alert_engine import DeviationAlertEngine
    from services.point_weather import AlertEvaluationConfig

    config = AlertEvaluationConfig(
        cooldown_minutes=0, metric_alert_levels=levels, channels={"email"},
    )
    return DeviationAlertEngine().evaluate(
        cached=[_point(**alt)], fresh=[_point(**neu)], config=config, alert_state={},
    )


# ───────────────────────── echte Pipeline: voller Trip-Lauf ─────────────────

def _trip(trip_id: str, levels: dict[str, str], catalog_ids: list[str],
          alert_rules: list | None = None) -> Trip:
    """Tour, deren Alarmquelle ausschliesslich ``metric_alert_levels`` ist
    (der Zustand seit #946). ``catalog_ids`` sind die auf dem Wetter-Tab
    aktiven Katalog-Metriken -- ohne sie greift der #961-Deaktivieren-Filter
    und es entsteht gar keine Regel."""
    stage = Stage(
        id="T1", name="Tag 1", date=date.today(),
        waypoints=[Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0)],
    )
    trip = Trip(
        id=trip_id, name="Abstufungs-Trip", stages=[stage],
        official_warnings=None, corridors=[],
        alert_rules=alert_rules or [],
        display_config=UnifiedWeatherDisplayConfig(
            trip_id=trip_id,
            metrics=[MetricConfig(metric_id=cid, enabled=True) for cid in catalog_ids],
            metric_alert_levels=levels,
        ),
    )
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, alert_on_changes=True,
    )
    trip.alert_cooldown_minutes = 0
    trip.official_alert_triggers_enabled = False
    return trip


def _run_trip_alert(user_id: str, trip: Trip, alt: dict, neu: dict) -> tuple[bool, list]:
    from services.trip_alert import TripAlertService

    mails: list = []
    sent = TripAlertService(
        settings=settings_email_only(), user_id=user_id, throttle_hours=0,
        mail_sink=lambda subject, body: mails.append((subject, body)),
    ).check_and_send_alerts(
        trip, [weather(1, **alt)], fresh_weather=[weather(1, **neu)],
    )
    return sent, mails


def _latest_entry(user_id: str) -> dict:
    entries = read_log(user_id)["entries"]
    assert entries, "Es wurde ueberhaupt kein Protokoll-Eintrag geschrieben."
    return entries[-1]


# ═════════════════════ AC-1..AC-3 — die Abstufung selbst ════════════════════

def test_ac1_boeen_knapp_ueber_schwelle_ist_gering():
    """AC-1 GIVEN Empfindlichkeit "standard" fuer Windboeen (Schwelle 20 km/h)
    WHEN sich die Boeen-Vorhersage zwischen zwei Staenden um 25 km/h aendert
    (Faktor 1,25)
    THEN traegt das Ergebnis von ``DeviationAlertEngine.evaluate()`` die
    Dringlichkeit ``"LOW"``.

    RED heute: der Vorrang-Eintrag aus ``from_alert_rules()`` liefert
    ``ChangeSeverity.MODERATE`` -> ``"MODERATE"``."""
    ergebnis = _evaluate(
        {"wind_gust": "standard"},
        {"gust_max_kmh": 30.0}, {"gust_max_kmh": 55.0},
    )
    assert ergebnis.triggered, "Voraussetzung: 25 km/h > Schwelle 20 muss ausloesen."
    assert ergebnis.severity == "LOW", (
        f"Faktor {25.0 / GUST_STANDARD:.2f} muss 'LOW' ergeben, "
        f"erhalten: {ergebnis.severity!r}"
    )


def test_ac2_boeen_mittlere_aenderung_bleibt_mittel():
    """AC-2 (INVARIANTE, heute schon GRUEN — kein RED-Beleg) GIVEN derselbe
    Aufbau WHEN die Aenderung 35 km/h betraegt (Faktor 1,75) THEN ist die
    Dringlichkeit ``"MODERATE"``.

    Dieser Test faellt zufaellig mit dem heutigen Konstantwert zusammen: der
    Vorrang liefert ``MODERATE``, und die Rechnung liefert fuer Faktor 1,75
    ebenfalls ``MODERATE``. Er beweist fuer sich genommen NICHTS ueber den
    Bug -- sein Zweck ist, dass die Mitte nach dem Fix nicht wegrutscht (die
    Abstufung entsteht sonst nur an den Raendern)."""
    ergebnis = _evaluate(
        {"wind_gust": "standard"},
        {"gust_max_kmh": 30.0}, {"gust_max_kmh": 65.0},
    )
    assert ergebnis.triggered, "Voraussetzung: 35 km/h > Schwelle 20 muss ausloesen."
    assert ergebnis.severity == "MODERATE", (
        f"Faktor {35.0 / GUST_STANDARD:.2f} muss 'MODERATE' ergeben, "
        f"erhalten: {ergebnis.severity!r}"
    )


def test_ac3_boeen_starke_aenderung_ist_hoch():
    """AC-3 GIVEN derselbe Aufbau WHEN die Aenderung 45 km/h betraegt
    (Faktor 2,25) THEN ist die Dringlichkeit ``"HIGH"``.

    RED heute: der Vorrang liefert ``"MODERATE"``. Zusammen mit AC-1 belegt
    dieser Test, dass heute ein 25-km/h-Sprung und ein 45-km/h-Sprung im
    Protokoll nicht unterscheidbar sind."""
    ergebnis = _evaluate(
        {"wind_gust": "standard"},
        {"gust_max_kmh": 30.0}, {"gust_max_kmh": 75.0},
    )
    assert ergebnis.triggered, "Voraussetzung: 45 km/h > Schwelle 20 muss ausloesen."
    assert ergebnis.severity == "HIGH", (
        f"Faktor {45.0 / GUST_STANDARD:.2f} muss 'HIGH' ergeben, "
        f"erhalten: {ergebnis.severity!r}"
    )


def test_ac1_bis_ac3_liefern_heute_denselben_wert_fuer_alle_drei_staerken():
    """Bug-Reproduktion aus Nutzersicht (Klammer um AC-1/2/3): drei
    unterschiedlich starke Boeen-Aenderungen (Faktor 1,25 / 1,75 / 2,25)
    duerfen NICHT dieselbe Dringlichkeit tragen -- sonst ist im Protokoll ein
    2-Grad-Sprung von einem 20-Grad-Sprung nicht zu unterscheiden (#1503).

    RED heute: alle drei liefern ``"MODERATE"``."""
    stufen = [
        _evaluate({"wind_gust": "standard"},
                  {"gust_max_kmh": 30.0}, {"gust_max_kmh": neu}).severity
        for neu in (55.0, 65.0, 75.0)
    ]
    assert len(set(stufen)) == 3, (
        "Drei verschieden starke Aenderungen muessen drei verschiedene "
        f"Dringlichkeiten ergeben, erhalten: {stufen!r}"
    )


# ═════════════════ AC-4 — die staerkste Aenderung bestimmt ══════════════════

def test_ac4_staerkste_aenderung_bestimmt_den_protokolleintrag():
    """AC-4 GIVEN zwei Metriken aendern sich im selben Lauf, eine knapp ueber
    Schwelle (Boeen, Faktor 1,2) und eine deutlich darueber
    (Hoechsttemperatur, Faktor 2,5) WHEN der Lauf ausgewertet wird THEN
    traegt der Protokolleintrag ``"HIGH"``.

    RED heute: beide Aenderungen tragen ``MODERATE`` -> Eintrag ``"MODERATE"``."""
    uid = _user("ac4")
    trip = _trip(
        "trip-ac4",
        {"wind_gust": "standard", "temperature_max": "standard"},
        ["gust", "temperature"],
    )

    sent, mails = _run_trip_alert(
        uid, trip,
        {"gust_max_kmh": 30.0, "temp_max_c": 10.0},
        {"gust_max_kmh": 54.0, "temp_max_c": 25.0},
    )

    assert sent is True and mails, "Voraussetzung: der Alarm muss versendet werden."
    entry = _latest_entry(uid)
    assert entry.get("changes_count") == 2, (
        "Voraussetzung: beide Metriken muessen ausloesen (Boeen Faktor 1,2 und "
        f"Temperatur Faktor 2,5), erhalten: {entry.get('changes_count')!r}"
    )
    assert entry.get("severity") == "HIGH", (
        f"Die staerkste Aenderung (Faktor {15.0 / TEMP_MAX_STANDARD:.1f}) muss den "
        f"Eintrag bestimmen, erhalten: {entry.get('severity')!r}"
    )


# ═══════════ AC-5/AC-6 — Gefahrenstufen entscheiden ueber das Niveau ════════

def test_ac5_gewitterstufe_mittel_auf_hoch_ist_hoch():
    """AC-5 GIVEN Empfindlichkeit "sensibel" fuer Gewitter WHEN die
    Gewitterstufe von "mittel" (MED) auf "hoch" (HIGH) steigt -- ein Sprung um
    genau eine Stufe -- THEN ist die Dringlichkeit ``"HIGH"``.

    RED heute: der Vorrang liefert ``"MODERATE"``. Faellt der Vorrang ersatzlos
    weg, wird es sogar ``"LOW"``: ``abs(delta)/threshold`` = 1/1 = 1,0 ->
    ``MINOR``. Genau diesen Zweitfehler verhindert diese AC — das Erreichen der
    hoechsten Gewitterstufe darf nie "gering" heissen."""
    ergebnis = _evaluate(
        {"thunder_level": "sensibel"},
        {"thunder_level_max": ThunderLevel.MED},
        {"thunder_level_max": ThunderLevel.HIGH},
    )
    assert ergebnis.triggered, (
        "Voraussetzung: 'sensibel' meldet laut #1460 jeden Stufenwechsel."
    )
    assert ergebnis.severity == "HIGH", (
        "Das Erreichen der hoechsten Gewitterstufe muss 'HIGH' sein, "
        f"erhalten: {ergebnis.severity!r}"
    )


def test_ac6_entwarnung_von_hoechster_gewitterstufe_ist_ebenfalls_hoch():
    """AC-6 GIVEN derselbe Aufbau WHEN die Gewitterstufe von "hoch" (HIGH) auf
    "kein Gewitter" (NONE) faellt THEN ist die Dringlichkeit ebenfalls
    ``"HIGH"``.

    RED heute: der Vorrang liefert ``"MODERATE"``. Belegt die Symmetrie -- die
    Entwarnung von der Hoechststufe wird nicht dadurch abgewertet, dass der
    neue Wert harmlos ist (#1460 loest bereits symmetrisch aus)."""
    ergebnis = _evaluate(
        {"thunder_level": "sensibel"},
        {"thunder_level_max": ThunderLevel.HIGH},
        {"thunder_level_max": ThunderLevel.NONE},
    )
    assert ergebnis.triggered, (
        "Voraussetzung: 'sensibel' meldet laut #1460 auch die Entwarnung."
    )
    assert ergebnis.severity == "HIGH", (
        "Die Entwarnung von der hoechsten Gewitterstufe muss 'HIGH' sein, "
        f"erhalten: {ergebnis.severity!r}"
    )


def test_ac5_ac6_mittlere_gewitterstufe_als_hoechstes_niveau_ist_mittel():
    """AC-5/AC-6 (Luecken-Absicherung) GIVEN Empfindlichkeit "sensibel" fuer
    Gewitter WHEN die Gewitterstufe von "kein Gewitter" (NONE) auf "mittel"
    (MED) steigt -- das gefaehrlichere der beiden beteiligten Niveaus ist damit
    MED -- THEN ist die Dringlichkeit ``"MODERATE"``, also ausdruecklich weder
    ``"LOW"`` noch ``"HIGH"``.

    Herkunft: Adversary-Finding F001 zu #1503 (MEDIUM). Die Mutations-
    Gegenprobe „MED → MODERATE aus ``_ordinal_severity()`` entfernt" (MED fiel
    damit auf ``MINOR`` = ``"LOW"`` zurueck) blieb UNGEFANGEN -- 31 von 31 Tests
    der beiden #1503-Dateien plus 76 Tests des verwandten Alarm-Korpus blieben
    gruen. Grund: AC-5 prueft MED→HIGH und AC-6 prueft HIGH→NONE, bei beiden ist
    ``max(alt, neu)`` gleich HIGH -- der MED-Zweig wurde nie beruehrt. Die
    #1460-Tests pruefen nur, OB ausgeloest wird, nie mit welcher Dringlichkeit.

    Damit ist die mittlere Gewitterstufe erstmals an der Wirkstelle bewacht:
    ueber den echten ``DeviationAlertEngine.evaluate()``-Lauf wie AC-5/AC-6,
    nicht per Direktaufruf von ``_ordinal_severity()``."""
    ergebnis = _evaluate(
        {"thunder_level": "sensibel"},
        {"thunder_level_max": ThunderLevel.NONE},
        {"thunder_level_max": ThunderLevel.MED},
    )
    assert ergebnis.triggered, (
        "Voraussetzung: 'sensibel' meldet laut #1460 jeden Stufenwechsel ab "
        "'mittel' — NONE -> MED muss ausloesen."
    )
    assert ergebnis.severity == "MODERATE", (
        "Die mittlere Gewitterstufe als hoechstes beteiligtes Niveau muss "
        f"'MODERATE' ergeben (weder 'LOW' noch 'HIGH'), erhalten: "
        f"{ergebnis.severity!r}"
    )


# ═════════ AC-7 — Invariante #638: Einstufung filtert nichts weg ════════════

def test_ac7_geringer_alarm_wird_trotzdem_gesendet_und_protokolliert():
    """AC-7 (INVARIANTE, heute schon GRUEN — kein RED-Test) GIVEN eine
    Aenderung, die nur knapp ueber der Schwelle liegt (Faktor 1,2) und damit
    kuenftig ``"LOW"`` traegt WHEN der vollstaendige Alarmlauf durchlaeuft
    THEN wird der Alarm gesendet UND protokolliert.

    Dies ist die Severity-Falle aus #638: der frueher vorhandene
    MODERATE/MAJOR-Filter hat Alarme still verschluckt.
    ``_filter_significant_changes()`` gibt seither ALLE Aenderungen zurueck --
    die Einstufung ist Etikett, nie Filterkriterium. Der Test gilt heute und
    MUSS nach dem Fix weiter gelten; er ist kein fehlgeschlagener RED-Test."""
    uid = _user("ac7")
    trip = _trip("trip-ac7", {"wind_gust": "standard"}, ["gust"])

    sent, mails = _run_trip_alert(
        uid, trip, {"gust_max_kmh": 30.0}, {"gust_max_kmh": 54.0},
    )

    assert sent is True, (
        "Eine geringe Aenderung darf den Versand nicht unterdruecken (#638)."
    )
    assert mails, "Mindestens ein Kanal muss beliefert worden sein."
    entry = _latest_entry(uid)
    assert entry.get("changes_count") == 1, (
        f"Die Aenderung muss protokolliert sein, erhalten: {entry!r}"
    )


# ═══════════════ AC-8 — SMS: staerkste Aenderung steht vorn ═════════════════

def test_ac8_alarm_sms_nennt_die_staerkste_aenderung_zuerst():
    """AC-8 GIVEN drei Aenderungen unterschiedlicher Staerke im selben Alarm
    (Boeen Faktor 1,2 / Niederschlag Faktor 1,8 / Hoechsttemperatur Faktor 2,5)
    WHEN die Alarm-SMS gerendert wird THEN steht das Kuerzel der staerksten
    Aenderung vorn.

    Die ``WeatherChange``-Objekte kommen aus dem echten Detektor-Lauf, sind
    also NICHT handgebaut. RED heute: alle drei tragen denselben Rang
    (``MODERATE``); ``format_alert_sms()`` sortiert stabil und laesst damit die
    Detektor-Reihenfolge stehen -- vorn steht die SCHWAECHSTE Aenderung."""
    from app.metric_catalog import get_compact_label_for_field
    from output.renderers.sms_trip import SMSTripFormatter

    # Reihenfolge der Schluessel bestimmt die Detektor-Reihenfolge: die
    # schwaechste Aenderung steht bewusst zuerst.
    ergebnis = _evaluate(
        {"wind_gust": "standard", "precipitation_sum": "standard",
         "temperature_max": "standard"},
        {"gust_max_kmh": 30.0, "precip_sum_mm": 5.0, "temp_max_c": 10.0},
        {"gust_max_kmh": 54.0, "precip_sum_mm": 23.0, "temp_max_c": 25.0},
    )
    assert ergebnis.triggered and len(ergebnis.changes) == 3, (
        "Voraussetzung: alle drei Metriken muessen ausloesen, erhalten: "
        f"{[(c.metric, c.severity) for c in ergebnis.changes]!r}"
    )

    sms = SMSTripFormatter().format_alert_sms(ergebnis.changes, "Trip")

    def _teil(feld: str, delta: float) -> str:
        label, einheit = get_compact_label_for_field(feld)
        return f"{label}{delta:+.0f}{einheit}"

    schwach = _teil("gust_max_kmh", 24.0)
    mittel = _teil("precip_sum_mm", 18.0)
    stark = _teil("temp_max_c", 15.0)
    assert len({schwach, mittel, stark}) == 3, (
        f"Voraussetzung: die drei Kuerzel muessen unterscheidbar sein: "
        f"{schwach!r}/{mittel!r}/{stark!r}"
    )
    for teil in (schwach, mittel, stark):
        assert teil in sms, f"Teil {teil!r} fehlt in der SMS: {sms!r}"

    assert sms.index(stark) < sms.index(mittel) < sms.index(schwach), (
        "Die staerkste Aenderung muss vorn stehen (erwartete Reihenfolge "
        f"{stark!r} < {mittel!r} < {schwach!r}), erhalten: {sms!r}"
    )


# ═════════════ AC-9 — derselbe Detektor traegt den Ortsvergleich ════════════

_COMPARE_PRESET_ID = "cp-1503"


class _ScriptedSource:
    """Deterministische ``LocationWeatherSource`` (DI-Naht, kein Mock)."""

    def __init__(self, **summary) -> None:
        self._summary = summary

    def fetch(
        self, point_id: str, lat: float, lon: float,
        start_hour: int | None = None, end_hour: int | None = None,
    ):
        from services.point_weather import PointWeatherData

        return PointWeatherData(
            id=point_id, name="Vergleichsort", lat=lat, lon=lon, timeseries=None,
            aggregated=SegmentWeatherSummary(**self._summary),
            fetched_at=datetime.now(timezone.utc), provider="tdd-1503",
        )


def _setup_compare_user(uid: str, anker: dict) -> None:
    """Ort, Preset und Δ-Anker-Schnappschuss. Das Preset traegt bewusst KEIN
    eigenes ``display_config`` -> ``compare_alert`` faellt auf die
    Standard-Empfindlichkeit aller Metriken zurueck (Schwelle Boeen 20)."""
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    save_location(
        SavedLocation(id="loc-a", name="Vergleichsort", lat=LAT, lon=LON, elevation_m=1000),
        user_id=uid,
    )
    write_compare_briefings(COMPARE_DATA_ROOT / uid, [{
        "id": _COMPARE_PRESET_ID, "name": "Vergleich 1503", "user_id": uid,
        "location_ids": ["loc-a"], "schedule": "daily", "weekday": 4,
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "empfaenger": ["dummy@example.com"], "created_at": "2026-08-01T00:00:00Z",
        "alert_cooldown_minutes": 0,
    }])
    user_dir = get_data_dir(uid)
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "user.json").write_text(json.dumps({"tier": "premium"}))
    CompareWeatherSnapshotService(user_id=uid).save(
        _COMPARE_PRESET_ID, "loc-a",
        _ScriptedSource(**anker).fetch("loc-a", LAT, LON),
    )


def test_ac9_ortsvergleich_protokolliert_dieselbe_abstufung():
    """AC-9 GIVEN ein Orts-Vergleich mit Empfindlichkeit "standard" WHEN sich
    an einem Ort eine Metrik um den Faktor 2,5 aendert (Boeen 20 -> 70 km/h)
    THEN traegt der Protokolleintrag des Vergleichs ``"HIGH"``.

    Belegt, dass der GETEILTE Detektor beide Seiten traegt -- es gibt keinen
    zweiten Codepfad, der eigens nachgezogen werden muesste (Trip/Compare-
    Teilung, CLAUDE.md). RED heute: ``"MODERATE"``."""
    from services.compare_alert import CompareAlertService

    uid = _user("ac9")
    clean_compare_user(uid)
    try:
        _setup_compare_user(uid, {"gust_max_kmh": 20.0})
        mails: list = []
        gesendet = CompareAlertService(
            settings=settings_email_only(), user_id=uid,
            weather_source=_ScriptedSource(gust_max_kmh=70.0),
            mail_sink=lambda subject, body: mails.append((subject, body)),
        ).check_all_compare_presets()

        assert gesendet == 1, (
            f"Voraussetzung: der Vergleichs-Alarm muss rausgehen, erhalten {gesendet}."
        )
        entry = _latest_entry(uid)
        assert entry.get("entity_type") == "compare", (
            f"Voraussetzung: Vergleichs-Eintrag erwartet, erhalten {entry!r}"
        )
        assert entry.get("severity") == "HIGH", (
            f"Faktor {50.0 / GUST_STANDARD:.1f} muss auch im Ortsvergleich 'HIGH' "
            f"ergeben, erhalten: {entry.get('severity')!r}"
        )
    finally:
        clean_compare_user(uid)


# ═══════════════════ AC-10 — Schwelle 0 stuerzt nicht ab ════════════════════

def test_ac10_schwelle_null_stuerzt_nicht_ab_und_ist_hoch():
    """AC-10 GIVEN eine Δ-Regel mit Schwelle 0 WHEN eine Aenderung erkannt
    wird THEN stuerzt die Einstufung nicht ab und liefert ``MAJOR``.

    Einziger AC ohne Pipeline: ueber ``metric_alert_levels`` ist die Schwelle 0
    nicht erzeugbar (alle Werte in ``_PRESET_TABLE`` sind > 0). Der Vorrang hat
    diese Stelle bisher zusaetzlich abgeschirmt; faellt er weg, rechnet
    ``_classify_severity()`` ``abs(delta) / 0``.

    RED heute: ``ZeroDivisionError`` -- der Detektor wird hier direkt und ohne
    Vorrang gebaut, also genau so, wie der Alarmpfad ihn nach dem Fix sieht.
    Konservative Richtung: eine Regel ohne sinnvollen Nenner feuert bei jeder
    Aenderung, ihr Ergebnis darf nicht stiller sein als der Normalfall."""
    from services.weather_change_detection import WeatherChangeDetectionService

    detektor = WeatherChangeDetectionService(thresholds={"gust_max_kmh": 0.0})
    changes = detektor.detect_changes(
        weather(1, gust_max_kmh=30.0), weather(1, gust_max_kmh=34.0),
        include_absolute=False,
    )

    assert len(changes) == 1, (
        f"Voraussetzung: die Aenderung muss erkannt werden, erhalten: {changes!r}"
    )
    assert changes[0].severity == ChangeSeverity.MAJOR, (
        "Eine Regel ohne sinnvollen Nenner muss konservativ 'MAJOR' liefern, "
        f"erhalten: {changes[0].severity!r}"
    )


# ═══════ AC-11 — persistierte Regel-Dringlichkeit wirkt nicht mehr ══════════

def test_ac11_persistierte_regel_dringlichkeit_bestimmt_nichts_mehr():
    """AC-11 GIVEN ein gespeicherter Trip, dessen ``alert_rules`` eine Regel
    mit ``severity="info"`` enthaelt WHEN ein Alarmlauf mit einer
    Faktor-2,5-Aenderung stattfindet THEN ist die Dringlichkeit ``"HIGH"`` und
    nicht ``"LOW"``.

    Geprueft an der Wirkstelle: eine reine Pruefung "Feld existiert nicht mehr"
    wuerde nicht zeigen, dass der Vorrang wirklich fort ist. Der Trip wird
    echt gespeichert und wieder geladen, damit die persistierte Dringlichkeit
    denselben Weg nimmt wie im Betrieb.

    RED heute: ``"MODERATE"`` (der Vorrang traegt die hart gesetzte
    ``WARNING`` aus ``expand_per_metric_levels``, nicht einmal die
    persistierte ``INFO``)."""
    uid = _user("ac11")
    info_regel = AlertRule(
        id=str(uuid.uuid4()), kind=AlertRuleKind.DELTA, metric=AlertMetric.WIND_GUST,
        threshold=GUST_STANDARD, severity=AlertSeverity.INFO, enabled=True,
    )
    save_trip(_trip("trip-ac11", {"wind_gust": "standard"}, ["gust"], [info_regel]), user_id=uid)

    geladen = load_trip(get_briefings_dir(uid) / "trip-ac11.json")
    assert geladen is not None, "Voraussetzung: der Trip muss ladbar sein."
    assert [str(getattr(r.severity, "value", r.severity)) for r in (geladen.alert_rules or [])] == ["info"], (
        "Voraussetzung: die persistierte Regel muss die Dringlichkeit 'info' "
        f"tragen, erhalten: {geladen.alert_rules!r}"
    )
    geladen.alert_cooldown_minutes = 0
    geladen.official_alert_triggers_enabled = False

    sent, mails = _run_trip_alert(
        uid, geladen, {"gust_max_kmh": 30.0}, {"gust_max_kmh": 80.0},
    )

    assert sent is True and mails, "Voraussetzung: der Alarm muss versendet werden."
    entry = _latest_entry(uid)
    assert entry.get("severity") == "HIGH", (
        f"Faktor {50.0 / GUST_STANDARD:.1f} muss 'HIGH' ergeben — die persistierte "
        f"Regel-Dringlichkeit 'info' darf nichts mehr bestimmen. Erhalten: "
        f"{entry.get('severity')!r}"
    )


# ═══════════════ AC-12 — zwei Nutzer, zwei eigene Einstufungen ══════════════

def test_ac12_zwei_nutzer_tragen_je_ihre_eigene_dringlichkeit():
    """AC-12 GIVEN zwei Nutzer mit je eigenem Datenordner, deren Trips im
    selben Lauf unterschiedlich starke Aenderungen erfahren (Faktor 1,2 bzw.
    2,5) WHEN beide Laeufe durchlaufen THEN traegt die Protokolldatei jedes
    Nutzers ausschliesslich die eigene Dringlichkeit (``"LOW"`` bzw.
    ``"HIGH"``) -- kein Rueckfall auf ``"default"``, keine Kreuz-Kontamination.

    RED heute: beide tragen ``"MODERATE"``."""
    leise, laut = _user("leise"), _user("laut")
    erwartet = {leise: ("trip-leise", 54.0, "LOW"), laut: ("trip-laut", 80.0, "HIGH")}

    for uid, (trip_id, neuer_wert, _) in erwartet.items():
        sent, mails = _run_trip_alert(
            uid, _trip(trip_id, {"wind_gust": "standard"}, ["gust"]),
            {"gust_max_kmh": 30.0}, {"gust_max_kmh": neuer_wert},
        )
        assert sent is True and mails, f"Voraussetzung: Alarm fuer {uid} muss rausgehen."

    for uid, (trip_id, _, soll) in erwartet.items():
        log = read_log(uid)
        alle = log["entries"] + log["not_delivered"]
        assert [e.get("entity_id") for e in alle] == [trip_id], (
            f"Der Ordner von {uid} darf ausschliesslich den eigenen Trip halten, "
            f"erhalten: {[e.get('entity_id') for e in alle]!r}"
        )
        assert alle[0].get("severity") == soll, (
            f"{uid} muss die eigene Dringlichkeit {soll!r} tragen, erhalten: "
            f"{alle[0].get('severity')!r}"
        )

    # Beide Nutzer haben verschiedene Datenordner — sonst ist die Trennung oben
    # trivial erfuellt.
    assert get_data_dir(leise) != get_data_dir(laut), (
        "Voraussetzung: die beiden Nutzer muessen getrennte Datenordner haben."
    )
