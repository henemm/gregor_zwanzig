"""TDD RED — Wetter-Aenderungsalarme werden wieder abgestuft (Issue #1503).

SPEC: docs/specs/modules/fix_1503_delta_dringlichkeit.md (AC-1..AC-12)

Issue #2793 S2b (Spec feat_2793_s2_alarm_stufenwechsel.md §3, D3): die
Abstufung bleibt, ihre QUELLE wechselt -- statt Faktor Δ/Schwelle bestimmt die
Ampelfarbe (gelb gering, orange mittel, rot hoch; Entwarnung: verlassene
Farbe). Die Tests AC-1..AC-8 und AC-12 sind darauf umgestellt; je Test steht
der Grund im Docstring. AC-9..AC-11 behalten ihre Zusicherung (die Werte
ergeben unter der Ampel dieselbe Dringlichkeit).

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
Hauptrepo-Pfad. Die frueher hier genannte Ausnahme ``COMPARE_DATA_ROOT`` ist
mit #1595 entfallen: der Compare-Preset-Loader liest nicht mehr cwd-relativ,
sondern ueber ``get_data_root()``. An ihre Stelle tritt die Funktion
``compare_data_root()`` aus ``tests/helpers/alert_log_fixtures.py``.
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
    LAT,
    LON,
    clean_compare_user,
    compare_data_root,
    read_log,
    settings_email_only,
    weather,
)
from tests.helpers.briefing_zeiten import briefing_zeiten_fuer_trip
from tests.helpers.compare_briefings import write_compare_briefings

# Schwellen der Empfindlichkeitsstufe "standard" aus `alert_preset._PRESET_TABLE`.
# Seit #2793 S2b nur noch Sprung-Schwellen (D1); AC-9..AC-11 nennen sie weiter.
GUST_STANDARD = 20.0        # wind_gust        -> gust_max_kmh

# #2793 S2b: Vorlage „allgemein" -- Boeen gelb 30 / orange 45 / rot 60,
# Niederschlag gelb 1 / orange 5 / rot 10, Temperatur oben gelb 28 / orange 31 / rot 34.
GELB_AB = {"gust": "yellow", "precipitation": "yellow", "temperature": "yellow",
           "thunder": "orange"}


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


def _evaluate(alarm_ab: dict[str, str], alt: dict, neu: dict, template: str = "allgemein"):
    """Voller Engine-Lauf ueber die echte Kette (seit #2793 S2b: Abo-Ampel ->
    Farbe von Anker und Neuwert -> ``_highest_severity``). Kein Direktaufruf
    eines Bausteins -- geprueft wird dort, wo die Zusicherung WIRKT."""
    from app.ampel import resolve_ampel
    from services.deviation_alert_engine import DeviationAlertEngine
    from services.point_weather import AlertEvaluationConfig

    dc = UnifiedWeatherDisplayConfig(
        trip_id="t-1503", metrics=[],
        ampel={"template": template,
               "metrics": {m: {"alarm_ab": ab} for m, ab in alarm_ab.items()}},
    )
    config = AlertEvaluationConfig(
        cooldown_minutes=0, channels={"email"}, display_config=dc,
        ampel=resolve_ampel(dc),
    )
    return DeviationAlertEngine().evaluate(
        cached=[_point(**alt)], fresh=[_point(**neu)], config=config, alert_state={},
    )


# ───────────────────────── echte Pipeline: voller Trip-Lauf ─────────────────

def _trip(trip_id: str, levels: dict[str, str], catalog_ids: list[str],
          alert_rules: list | None = None, alarm_ab: dict | None = None) -> Trip:
    """Trip, deren Alarmquelle ausschliesslich ``metric_alert_levels`` ist
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
            # #2793 S2b: ohne Angabe Vorgabe der Vorlage „allgemein" (Orange).
            ampel={"template": "allgemein",
                   "metrics": {m: {"alarm_ab": ab} for m, ab in (alarm_ab or {}).items()}},
        ),
    )
    # Issue #1594: Briefing-Zeiten ausserhalb des Vorlauf-Fensters — sonst
    # schwiege der Alarm wegen der Sperre und die Abstufung waere ungemessen.
    morgen, abend = briefing_zeiten_fuer_trip(trip)
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, alert_on_changes=True,
        morning_time=morgen, evening_time=abend,
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
    """AC-1 (#2793 S2b, D3 umgestellt) GIVEN Boeen „Alarm ab Gelb"
    WHEN die Boeen von gruen (20) auf gelb (35) steigen
    THEN traegt das Ergebnis die Dringlichkeit ``"LOW"`` (gelb = gering).

    Vorher: Faktor Δ/Schwelle 1,25 -> LOW. Grund der Umstellung: Spec D3,
    die Dringlichkeit kommt aus der erreichten Farbe."""
    ergebnis = _evaluate(GELB_AB, {"gust_max_kmh": 20.0}, {"gust_max_kmh": 35.0})
    assert ergebnis.triggered, "Voraussetzung: gruen -> gelb bei Alarm ab Gelb muss ausloesen."
    assert ergebnis.severity == "LOW", f"gelb muss 'LOW' ergeben, erhalten: {ergebnis.severity!r}"


def test_ac2_boeen_mittlere_aenderung_bleibt_mittel():
    """AC-2 (#2793 S2b, D3 umgestellt) GIVEN derselbe Aufbau WHEN die Boeen
    auf orange (50) steigen THEN ist die Dringlichkeit ``"MODERATE"``."""
    ergebnis = _evaluate(GELB_AB, {"gust_max_kmh": 20.0}, {"gust_max_kmh": 50.0})
    assert ergebnis.triggered, "Voraussetzung: gruen -> orange muss ausloesen."
    assert ergebnis.severity == "MODERATE", f"orange muss 'MODERATE' ergeben, erhalten: {ergebnis.severity!r}"


def test_ac3_boeen_starke_aenderung_ist_hoch():
    """AC-3 (#2793 S2b, D3 umgestellt) GIVEN derselbe Aufbau WHEN die Boeen
    auf rot (65) steigen THEN ist die Dringlichkeit ``"HIGH"``."""
    ergebnis = _evaluate(GELB_AB, {"gust_max_kmh": 20.0}, {"gust_max_kmh": 65.0})
    assert ergebnis.triggered, "Voraussetzung: gruen -> rot muss ausloesen."
    assert ergebnis.severity == "HIGH", f"rot muss 'HIGH' ergeben, erhalten: {ergebnis.severity!r}"


def test_ac1_bis_ac3_liefern_heute_denselben_wert_fuer_alle_drei_staerken():
    """Klammer um AC-1/2/3: drei verschiedene erreichte Farben duerfen NICHT
    dieselbe Dringlichkeit tragen (#1503; seit #2793 S2b ueber die Farbe)."""
    stufen = [
        _evaluate(GELB_AB, {"gust_max_kmh": 20.0}, {"gust_max_kmh": neu}).severity
        for neu in (35.0, 50.0, 65.0)
    ]
    assert stufen == ["LOW", "MODERATE", "HIGH"], stufen


# ═════════════════ AC-4 — die staerkste Aenderung bestimmt ══════════════════

def test_ac4_staerkste_aenderung_bestimmt_den_protokolleintrag():
    """AC-4 (#2793 S2b, D3 umgestellt) GIVEN zwei Metriken aendern sich im
    selben Lauf, Boeen gruen -> gelb (gering) und Hoechsttemperatur gruen ->
    rot (hoch) WHEN der Lauf ausgewertet wird THEN traegt der
    Protokolleintrag ``"HIGH"`` (die hoechste Farbe)."""
    uid = _user("ac4")
    trip = _trip(
        "trip-ac4",
        {"wind_gust": "standard", "temperature_max": "standard"},
        ["gust", "temperature"], alarm_ab=GELB_AB,
    )

    sent, mails = _run_trip_alert(
        uid, trip,
        {"gust_max_kmh": 20.0, "temp_max_c": 20.0},
        {"gust_max_kmh": 35.0, "temp_max_c": 35.0},
    )

    assert sent is True and mails, "Voraussetzung: der Alarm muss versendet werden."
    entry = _latest_entry(uid)
    assert entry.get("changes_count") == 2, (
        "Voraussetzung: beide Metriken muessen ausloesen (Boeen gelb, "
        f"Temperatur rot), erhalten: {entry.get('changes_count')!r}"
    )
    assert entry.get("severity") == "HIGH", (
        f"Die hoechste Farbe (rot) muss den Eintrag bestimmen, erhalten: {entry.get('severity')!r}"
    )


# ═══════════ AC-5/AC-6 — Gefahrenstufen entscheiden ueber das Niveau ════════

def test_ac5_gewitterstufe_mittel_auf_hoch_ist_hoch():
    """AC-5 (#2793 S2b, D3 umgestellt) GIVEN Gewitter „Alarm ab Orange",
    Vorlage „allgemein" (mittel orange, hoch rot) WHEN die Stufe von „mittel"
    auf „hoch" steigt THEN ist die Dringlichkeit ``"HIGH"`` (erreichte Farbe
    rot). Vorher: hoeheres Niveau HIGH -- gleiches Ergebnis, neue Quelle."""
    ergebnis = _evaluate(
        GELB_AB, {"thunder_level_max": ThunderLevel.MED}, {"thunder_level_max": ThunderLevel.HIGH},
    )
    assert ergebnis.triggered, "Voraussetzung: orange -> rot muss ausloesen."
    assert ergebnis.severity == "HIGH", ergebnis.severity


def test_ac6_entwarnung_von_hoechster_gewitterstufe_ist_ebenfalls_hoch():
    """AC-6 (#2793 S2b, D3) GIVEN derselbe Aufbau WHEN die Gewitterstufe von
    „hoch" (rot) auf „keins" (gruen) faellt THEN Entwarnung mit der
    Dringlichkeit der VERLASSENEN Farbe: ``"HIGH"``."""
    ergebnis = _evaluate(
        GELB_AB, {"thunder_level_max": ThunderLevel.HIGH}, {"thunder_level_max": ThunderLevel.NONE},
    )
    assert ergebnis.triggered, "Voraussetzung: rot -> gruen ist eine Entwarnung."
    assert ergebnis.severity == "HIGH", ergebnis.severity


def test_ac6_entwarnung_traegt_die_verlassene_farbe_nicht_immer_hoch():
    """AC-6 umgekehrt (#2793 S2b, Spec §3 D3): die fruehere Regel „Entwarnung
    so dringlich wie das gefaehrlichere Niveau" bzw. „Entwarnung immer hoch"
    gilt nicht mehr -- eine Entwarnung von ORANGE (Boeen 50 -> 35 bei „Alarm
    ab Orange") traegt ``"MODERATE"``, nicht ``"HIGH"``."""
    ergebnis = _evaluate({"gust": "orange"}, {"gust_max_kmh": 50.0}, {"gust_max_kmh": 35.0})
    assert ergebnis.triggered, "Voraussetzung: orange -> gelb unter Alarm ab Orange entwarnt."
    assert [c.art for c in ergebnis.changes] == ["entwarnung"]
    assert ergebnis.severity == "MODERATE", ergebnis.severity


def test_ac5_ac6_mittlere_gewitterstufe_als_hoechstes_niveau_ist_mittel():
    """AC-5/AC-6 (Luecken-Absicherung, #1503 F001; #2793 S2b ueber die Farbe)
    GIVEN Gewitter „Alarm ab Orange" WHEN die Stufe von „keins" auf „mittel"
    (orange) steigt THEN ist die Dringlichkeit ``"MODERATE"`` -- weder LOW
    noch HIGH."""
    ergebnis = _evaluate(
        GELB_AB, {"thunder_level_max": ThunderLevel.NONE}, {"thunder_level_max": ThunderLevel.MED},
    )
    assert ergebnis.triggered, "Voraussetzung: gruen -> orange muss ausloesen."
    assert ergebnis.severity == "MODERATE", ergebnis.severity


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
    # #2793 S2b: „geringe" Dringlichkeit heisst jetzt gelb (Boeen 20 -> 35).
    trip = _trip("trip-ac7", {"wind_gust": "standard"}, ["gust"], alarm_ab=GELB_AB)

    sent, mails = _run_trip_alert(
        uid, trip, {"gust_max_kmh": 20.0}, {"gust_max_kmh": 35.0},
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

    # #2793 S2b (D3): Staerke = erreichte Farbe -- Boeen gelb (gering),
    # Niederschlag orange (mittel), Temperatur rot (hoch). Die Engine liefert
    # die Ereignisse in der Reihenfolge Temperatur, Boeen, Niederschlag --
    # also NICHT schon nach Staerke sortiert.
    ergebnis = _evaluate(
        GELB_AB,
        {"gust_max_kmh": 20.0, "precip_sum_mm": 0.0, "temp_max_c": 20.0},
        {"gust_max_kmh": 44.0, "precip_sum_mm": 6.0, "temp_max_c": 35.0},
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
    mittel = _teil("precip_sum_mm", 6.0)
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
        elevation_m: int | None = None, user_id: str | None = None,
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
    write_compare_briefings(compare_data_root() / uid, [{
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

    geladen = load_trip(get_briefings_dir(uid) / "trip-ac11.json", user_id="default")
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
    # #2793 S2b (D3): leise = gruen -> gelb (35, LOW), laut = gruen -> rot (80, HIGH).
    leise, laut = _user("leise"), _user("laut")
    erwartet = {leise: ("trip-leise", 35.0, "LOW"), laut: ("trip-laut", 80.0, "HIGH")}

    for uid, (trip_id, neuer_wert, _) in erwartet.items():
        sent, mails = _run_trip_alert(
            uid, _trip(trip_id, {"wind_gust": "standard"}, ["gust"], alarm_ab=GELB_AB),
            {"gust_max_kmh": 20.0}, {"gust_max_kmh": neuer_wert},
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
