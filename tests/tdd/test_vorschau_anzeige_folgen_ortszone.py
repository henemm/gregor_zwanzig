"""TDD RED — #1727 S5c: Vorschau, Anzeige, Sofort-Vergleich folgen dem ORTSTAG.

SPEC: docs/specs/modules/fix_1727_s5c_vorschau_anzeige_ortstag.md (AC-1 bis AC-8)
KONTEXT: docs/context/fix-1727-s5c-vorschau-anzeige.md (sieben Fundstellen, gemessen)
ADR-0044 (Kalendertage folgen der Ortszeit), ADR-0051 Regel 2 (Zone gehoert an
die Daten) + Regel 3 (keine Umgebungsuhr).

Sieben Fundstellen in fuenf Dateien bestimmen "welcher Kalendertag ist
gemeint" ueber die Serveruhr (``date.today()``/``datetime.now()`` ohne Zone)
statt ueber den Ortstag der Tour bzw. des ersten aufloesbaren Preset-Orts.
Anders als S5b (Versandpfade) wirken sie primUER auf VORSCHAU-/ANZEIGE-Pfade,
mit einer Ausnahme (F7, versendete Mail):

    F1  preview_service._resolve_target_date + _build_report   (:84 / :120)
    F2  compare_preview_service._resolve_target_date            (:255)
    F3  api/routers/compare.py::run_comparison, Stunde          (:53)
    F4  api/routers/compare.py::run_comparison, Zieltag heute   (:55)
    F5  api/routers/compare.py::run_comparison, Zieltag morgen  (:58)
    F6  comparison_engine.dict_to_comparison_result (tot, 0 Aufrufer) (:394)
    F7  compare_html._compute_next_send / _render_abo_footer    (:1438/:1457)

ZWEI NACHWEISFORMEN, PFLICHT WO ANWENDBAR (AC-8)
===============================================================================
(a) Vorbedingungs-Anker ``_anker`` (tests/tdd/conftest.py) vor JEDER
    Hauptzusicherung, die einen vom Weltzeit-/Servertag abweichenden Ortstag
    behauptet — sonst waere sie strukturell nie falsifizierbar (#1726 F002).

(b) Parameter gegen Systemuhr (S5a-Befund F001) — PFLICHT genau dort, wo ein
    Pflichtparameter entsteht: F1 (``_resolve_target_date`` UND
    ``_build_report``) und F2 (``_resolve_target_date``). ``freeze_time(X)``
    setzen, ``now_utc=Y`` mit ANDEREM Ortstag uebergeben; die Assertion muss
    auf Y zeigen, nicht auf X. An F3-F5 und F7 bleibt "jetzt" bewusst
    funktionsintern (kein exponierter Parameter) — dort traegt der Anker
    allein (a).

MATHEMATISCHE ANMERKUNG ZU AC-3 (gemessen, nicht vermutet)
===============================================================================
``run_comparison`` bestimmt "heute/morgen" ueber EINE 14:00-Schwelle, die
sowohl die Stunde als auch den Tag traegt. Fuer die beiden hier gewaehlten
Szenarien ("voraus"/"hinterher") gilt: eine Konstruktion, die GLEICHZEITIG
(1) einen Tagesumbruch zwischen Welt- und Ortszeit zeigt (Anker-Pflicht),
UND (2) die lokale Uhrzeit nahe 14:00 UND (3) einen vom Servercode
tatsaechlich abweichenden target_date liefert, ist mit den real existierenden
Zeitzonen-Offsets (max. +14h Kiritimati, min. -11h Samoa, beide < 24h) fuer
den ">=14 Uhr lokal"-Zweig NICHT konstruierbar (nachgerechnet: ein
Tagesumbruch VORWAERTS haelt die neue lokale Stunde immer < Offset <= 14h,
ein Tagesumbruch RUECKWAERTS braucht fuer eine abweichende Antwort eine
Serverstunde >= 14 UND einen Offset < -14h, den es nicht gibt). Die beiden
ersten zwei Szenarien unten nutzen deshalb den TAGES-Anteil der Schwelle als
Diskriminator (Ortstag bereits uebergelaufen, Ortsstunde < 14:00 in beiden
Faellen) — das ist exakt die im Spec-Beispiel genannte Eigenschaft "Stunde
UND Tag aus DERSELBEN Ortszeit", nur mit rechnerisch tragfaehigen Werten
statt der illustrativen "13:xx/14:xx"-Uhrzeiten. Ein DRITTES Szenario
(Team-Lead-Review) deckt die andere Haelfte ab: Orts- und Servertag sind
DENSELBE Kalendertag, aber Orts- und Serverstunde liegen auf
VERSCHIEDENEN Seiten der 14-Uhr-Schwelle. Erst zusammen bewachen die drei
Tests BEIDE Haelften der Schwelle -- zwei den Tag, einer die Stunde. Ohne
das dritte Szenario besteht eine Implementierung, die nur den Tag auf
Ortszeit umstellt, die Stunde aber weiter von der Serveruhr nimmt, beide
Tag-Tests unbemerkt (dieselbe Fehlerklasse "Zusicherung behauptet, von
keinem Test bewacht", die dieses Epic bereits mehrfach getroffen hat).

RED-GRUENDE (gemessen, nicht vermutet)
===============================================================================
* F1: der Pflichtparameter ``now_utc`` existiert an ``_resolve_target_date``
  UND ``_build_report`` noch nicht -> ``TypeError``.
* F2: ``_resolve_target_date`` ist heute eine 1-Parameter-Funktion
  (``given``) -> ``TypeError`` bei 3 Argumenten.
* F3-F5: fachlich rot -- ``run_comparison`` liefert ein ``target_date``, das
  aus der zonenlosen Serveruhr stammt, nicht aus der Ortszeit.
* F6: fachlich rot -- ``dict_to_comparison_result`` existiert noch
  (``hasattr`` liefert heute ``True``).
* F7: fachlich rot -- der Footer "Naechster Versand" rechnet noch mit
  ``date.today()`` statt der bereits aufgeloesten Kopfzeilen-Zone.

TESTPOLITIK (CLAUDE.md "Test-Politik: Zwei Schichten"): Kern-Schicht, kein
Netz. Echte ``Trip``/``Stage``/``Waypoint``/``SavedLocation``/
``ComparisonResult``-Objekte. Kein ``Mock()``/``patch()``/``MagicMock`` --
die Netz-Naehte laufen ueber den bestehenden Demo-Modus (echter
``FixtureProvider``, Issue #483) bzw. ueber ``monkeypatch.setattr`` auf
echte, lokal konstruierte DTOs/Spione (Muster
``test_hail_flag_metrics_catalog_and_compare_api.py``), die AUFZEICHNEN, was
der Pruefling tatsaechlich entscheidet, statt eine Annahme zurueckzuspiegeln.

Pfadregel #1409: diese Datei liest nichts von der Platte des Hauptrepos.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from app.models import OutlookState, TrendResult
from app.trip import Trip
from app.user import ComparisonResult, LocationResult, SavedLocation
from services.compare_preview_service import _resolve_target_date as _cps_resolve_target_date
from services.preview_service import PreviewService
from services.trip_report_scheduler import TripReportSchedulerService
from tests.helpers.nowcast_gate_fixtures import settings_email_only, trip_stage
from tests.tdd.conftest import WP_NZ, _anker

# ═══════════════════════════ Zonen und Koordinaten ═══════════════════════════
# Mitteleuropaeische Fixturen (Versatz 2h) koennen den Fehler strukturell
# nicht zeigen -- durchgehend Zonen mit deutlichem Versatz.

WELLINGTON_ZONE = "Pacific/Auckland"   # im August UTC+12
PAGO_ZONE = "Pacific/Pago_Pago"        # UTC-11, kein DST
PAGO = (-14.28, -170.70)               # Pago Pago -- Muster aus S5a/S5b

D19, D20, D21, D22 = (date(2026, 8, d) for d in (19, 20, 21, 22))

# ── Einzel-Szenario (a): Ortstag != Servertag, EIN now_utc ──────────────────
# 14:00 UTC am 20.08. = 02:00 Ortszeit am 21.08. in Wellington.
MITTAGS_UTC = datetime(2026, 8, 20, 14, 0, tzinfo=timezone.utc)

# ── Parameter-gegen-Systemuhr (b): ZWEI now_utc, verschiedene Ortstage ──────
# 20:00 UTC am 19.08. = 08:00 Ortszeit am 20.08. in Wellington (Ortstag D20).
FROST_UTC = datetime(2026, 8, 19, 20, 0, tzinfo=timezone.utc)
# 20:00 UTC am 21.08. = 08:00 Ortszeit am 22.08. in Wellington (Ortstag D22).
PARAM_UTC = datetime(2026, 8, 21, 20, 0, tzinfo=timezone.utc)


def _preview_trip(trip_id: str, tage_und_koordinaten: list) -> Trip:
    """Tour mit je einer RENDERBAREN (2-Wegpunkt-)Etappe pro Tag.

    ``trip_two_zones`` (conftest) baut nur 1-Wegpunkt-Etappen -- unterhalb
    von ``PreviewService._MIN_WAYPOINTS_FOR_RENDER`` (2) und damit fuer
    ``_resolve_target_date``s Auto-Resolve nicht renderbar. Dieser Helfer
    nutzt stattdessen ``trip_stage`` (2 Wegpunkte je Etappe), analog dem
    ``_trip``-Helfer aus S5b.
    """
    return Trip(
        id=trip_id,
        name=trip_id,
        stages=[
            trip_stage(f"S{i}", tag, lat, lon, wp_prefix=f"W{i}-")
            for i, (tag, (lat, lon)) in enumerate(tage_und_koordinaten)
        ],
        official_alerts_enabled=False,  # strukturell kein Warnungs-Abruf
    )


def _ort(loc_id: str, coords) -> SavedLocation:
    """Gespeicherter Ort; ``coords=None`` = Ort OHNE aufloesbare Zone."""
    lat, lon = (None, None) if coords is None else coords
    return SavedLocation(id=loc_id, name=loc_id, lat=lat, lon=lon, elevation_m=500)


def _uhr_eingefroren(now_utc: datetime) -> None:
    """Belegt, dass ``freeze_time`` im PRUEFPROZESS wirklich greift -- ohne
    diese Pruefung waere ein gruener Lauf kein Beweis, sondern ein Zufall."""
    assert datetime.now(tz=timezone.utc) == now_utc, (
        "Testaufbau: freeze_time greift nicht, die Systemuhr steht auf "
        f"{datetime.now(tz=timezone.utc).isoformat()} statt auf "
        f"{now_utc.isoformat()}"
    )


# ═══════════════════════ AC-1: preview_service (F1) ═══════════════════════


def test_ac1_resolve_target_date_folgt_dem_parameter_nicht_der_systemuhr():
    """AC-1, erste Haelfte -- ``PreviewService._resolve_target_date`` (F1).

    GIVEN eine Neuseeland-Tour (UTC+12) mit Etappen am 19.08. und 21.08.,
    WHEN  ``_resolve_target_date(trip, given_date=None, now_utc=Y)`` unter
          eingefrorener Systemuhr X aufgerufen wird, wobei X und Y auf
          verschiedene Ortstage derselben Zone fallen,
    THEN  waehlt die Auto-Resolve-Logik die Etappe gemessen am Ortstag VON Y
          -- nicht von X. Bei X (Ortstag 20.08.) waere die 21.08.-Etappe die
          naechste kommende; bei Y (Ortstag 22.08.) liegen BEIDE Etappen
          bereits in der Vergangenheit, der Rueckfall greift auf die
          chronologisch ERSTE Etappe (19.08.) -- ein eindeutig
          unterscheidbares Ergebnis.

    RED heute: ``now_utc`` existiert an ``_resolve_target_date`` noch nicht
    -> ``TypeError``.
    """
    trip = _preview_trip("preview-param-nz", [(D19, WP_NZ), (D21, WP_NZ)])
    service = PreviewService(settings_email_only())

    with freeze_time(FROST_UTC):
        _anker(FROST_UTC, WELLINGTON_ZONE, D20)
        _uhr_eingefroren(FROST_UTC)
        ergebnis = service._resolve_target_date(trip, None, now_utc=PARAM_UTC)

    ortstag_param = PARAM_UTC.astimezone(ZoneInfo(WELLINGTON_ZONE)).date()
    assert ortstag_param == D22, (
        "Testaufbau nicht diskriminierend: PARAM_UTC muss auf Ortstag "
        f"{D22} fallen, liegt aber auf {ortstag_param}"
    )
    assert ergebnis == D19, (
        f"AC-1: _resolve_target_date lieferte {ergebnis}, erwartet {D19} "
        f"(chronologisch erste Etappe, weil am Ortstag von now_utc={PARAM_UTC.isoformat()} "
        f"({ortstag_param}) BEIDE Etappen bereits vergangen sind). "
        f"{D21} heisst: der Pruefling hat die eingefrorene Systemuhr "
        f"({FROST_UTC.isoformat()}, Ortstag {D20}) benutzt statt des "
        "uebergebenen Parameters now_utc (ADR-0051 Regel 3)."
    )


def test_ac1_build_report_folgt_dem_parameter_nicht_der_systemuhr(monkeypatch):
    """AC-1, zweite Haelfte -- ``PreviewService._build_report`` (F1).

    GIVEN dieselbe Situation wie oben, aber am ``_build_report``-Aufruf: ein
          echter Demo-Report (FixtureProvider, kein Netz) fuer eine Etappe am
          19.08. in Neuseeland,
    WHEN  ``_build_report(trip, target, "evening", now_utc=Y, demo=True)``
          aufgerufen wird,
    THEN  erhalten SOWOHL ``_build_stage_trend`` ALS AUCH
          ``_build_thunder_forecast_from_trend_or_fetch`` GENAU dieses Y --
          nicht die eingefrorene Systemuhr X UND nicht je eine eigene, im
          Rumpf neu aufgeloeste ``datetime.now(timezone.utc)``. Ein DI-Spion
          (echte Unterklassen-Methode, kein Mock) zeichnet auf, WELCHEN
          Zeitpunkt der Pruefling tatsaechlich durchreicht.

    Vor dem Fix hatte ``_build_report`` gar keinen ``now_utc``-Parameter --
    die zweite, bislang bei preview_service.py:223 liegende
    ``jetzt_utc = datetime.now(timezone.utc)``-Aufloesung ist genau die
    Stelle, die AC-1 abschafft.

    RED heute: ``now_utc`` existiert an ``_build_report`` noch nicht ->
    ``TypeError``.
    """
    gesehen_trend: list = []
    gesehen_thunder: list = []

    def _trend_spion(self, trip, target_date, now_utc, tz=None):
        gesehen_trend.append(now_utc)
        return TrendResult(rows=None, state=OutlookState.NO_STAGES)

    def _thunder_spion(self, trip, target_date, now_utc, tz,
                        multi_day_trend=None, night_weather=None):
        gesehen_thunder.append(now_utc)
        return None

    monkeypatch.setattr(TripReportSchedulerService, "_build_stage_trend", _trend_spion)
    monkeypatch.setattr(
        TripReportSchedulerService,
        "_build_thunder_forecast_from_trend_or_fetch",
        _thunder_spion,
    )

    ziel_tag = FROST_UTC.date()
    trip = _preview_trip("preview-build-report-param-nz", [(ziel_tag, WP_NZ)])
    service = PreviewService(settings_email_only())

    with freeze_time(FROST_UTC):
        _anker(FROST_UTC, WELLINGTON_ZONE, D20)
        _uhr_eingefroren(FROST_UTC)
        service._build_report(trip, ziel_tag, "evening", now_utc=PARAM_UTC, demo=True)

    assert gesehen_trend == [PARAM_UTC], (
        f"AC-1: _build_stage_trend erhielt now_utc={gesehen_trend!r}, erwartet "
        f"[{PARAM_UTC.isoformat()}]. {[FROST_UTC]} heisst: die Systemuhr statt "
        "des Parameters wurde durchgereicht."
    )
    assert gesehen_thunder == [PARAM_UTC], (
        f"AC-1: _build_thunder_forecast_from_trend_or_fetch erhielt "
        f"now_utc={gesehen_thunder!r}, erwartet [{PARAM_UTC.isoformat()}] -- "
        "dasselbe now_utc wie _build_stage_trend (EIN Zeitpunkt speist beide "
        "Entscheidungen, keine zweite Aufloesung)."
    )


# ═══════════════ AC-2: compare_preview_service._resolve_target_date (F2) ═══════════════


def test_ac2_resolve_target_date_folgt_dem_parameter_und_dem_ersten_aufloesbaren_ort():
    """AC-2 -- ``compare_preview_service._resolve_target_date`` (F2).

    GIVEN zwei Orte -- der ERSTE ohne aufloesbare Zone (keine Koordinaten),
          der ZWEITE in Neuseeland (UTC+12) -- und kein explizites Datum,
    WHEN  ``_resolve_target_date(None, locations, now_utc=Y)`` unter
          eingefrorener Systemuhr X aufgerufen wird (X != Y, verschiedene
          Ortstage),
    THEN  liefert die Funktion den ORTSTAG des ZWEITEN (ersten AUFLOESBAREN)
          Orts zum Zeitpunkt Y -- weder den unaufloesbaren ersten Ort noch
          die Systemuhr X.

    Ohne den unaufloesbaren ersten Ort waere "ueberspringen statt UTC" nicht
    falsifizierbar (#1378 AC-4/#1726 AC-15-Muster, wie in S5b AC-5 zweite
    Haelfte).

    RED heute: ``_resolve_target_date`` ist eine 1-Parameter-Funktion
    (``given``) -> ``TypeError`` bei 3 Argumenten.
    """
    orte = [_ort("ohne-zone", None), _ort("ort-nz", WP_NZ)]

    from utils.timezone import resolve_location_tz

    assert resolve_location_tz(orte[0]) is None, (
        "Testaufbau nicht diskriminierend: der erste Ort muss UNAUFLOESBAR "
        "sein, sonst belegt der Test nicht, dass uebersprungen statt auf UTC "
        "zurueckgefallen wird"
    )

    with freeze_time(FROST_UTC):
        _anker(FROST_UTC, WELLINGTON_ZONE, D20)
        _uhr_eingefroren(FROST_UTC)
        ergebnis = _cps_resolve_target_date(None, orte, PARAM_UTC)

    ortstag_param = PARAM_UTC.astimezone(ZoneInfo(WELLINGTON_ZONE)).date()
    assert ergebnis == ortstag_param, (
        f"AC-2: _resolve_target_date lieferte {ergebnis}, erwartet "
        f"{ortstag_param} (Ortstag des zweiten/ersten aufloesbaren Orts zum "
        f"Zeitpunkt now_utc={PARAM_UTC.isoformat()}). {D20} (Systemuhr-Ortstag) "
        f"oder {FROST_UTC.date()} (nackter UTC-Tag) heissen: der Parameter "
        "wurde ignoriert bzw. die Zone gar nicht aufgeloest."
    )


def test_ac2_gegebenes_datum_bleibt_unveraendert():
    """AC-2, Invariante -- der ``given is not None``-Zweig aendert sich NICHT.

    GIVEN ein explizit uebergebenes ISO-Datum (von der UI gesetzt),
    WHEN  ``_resolve_target_date(given, locations, now_utc)`` aufgerufen
          wird,
    THEN  kommt GENAU dieses Datum zurueck -- unabhaengig von Orten und
          now_utc. Die Zonen-/Parameter-Erweiterung aus AC-2 darf diesen
          Zweig nicht anfassen (Spec "Then": "der given is not None-Zweig
          ... bleibt dabei unveraendert").

    RED heute aus demselben Signaturgrund wie oben (3 statt 1 Argument) --
    NACH dem Fix bleibt dieser Test ein reiner Regressions-Riegel (analog
    S5b AC-7, zweiter Test).
    """
    orte = [_ort("ort-nz", WP_NZ)]
    erwartet = date(2026, 8, 1)

    ergebnis = _cps_resolve_target_date(erwartet.isoformat(), orte, PARAM_UTC)

    assert ergebnis == erwartet, (
        f"AC-2 (Invariante): explizit uebergebenes Datum {erwartet} kam als "
        f"{ergebnis} zurueck -- der given is not None-Zweig darf durch die "
        "Zonen-/now_utc-Erweiterung NICHT veraendert werden."
    )


# ═══════════════ AC-3: GET /api/compare (F3-F5, run_comparison) ═══════════════


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from api.main import app

    return TestClient(app)


def _leeres_vergleichsergebnis(target_date: date) -> ComparisonResult:
    """Minimaler, echter ``ComparisonResult`` OHNE Orte -- die Sonde
    interessiert sich nur fuer das ``target_date``, mit dem ``run_comparison``
    die Engine aufruft bzw. das direkt im JSON-Response landet
    (``api/routers/compare.py:120``)."""
    return ComparisonResult(locations=[], time_window=(9, 16), target_date=target_date)


def test_ac3_sofortvergleich_ortszeit_ist_dem_servertag_bereits_voraus(client, monkeypatch):
    """AC-3, Szenario "voraus" -- Fundstellen F3-F5 (``run_comparison``).

    GIVEN ein Ort in Neuseeland (UTC+12) und ein Zeitpunkt 13:00 UTC am
          20.08. -- ortszeitlich ist bereits 01:00 Uhr am 21.08., auf dem
          Server noch der 20.08. um 13:00 (< 14 Uhr),
    WHEN  ``GET /api/compare`` OHNE ``target_date`` aufgerufen wird,
    THEN  ist ``target_date`` im JSON-Response der 21.08. -- der Ortstag,
          nicht der Servertag.

    Vor dem Fix: die Serverstunde (13 Uhr, < 14) waehlte "heute" gemessen am
    zonenlosen Servertag (20.08.) -- ohne zu sehen, dass am Ort bereits der
    naechste Kalendertag laeuft.

    RED heute: fachlich rot (kein TypeError -- ``run_comparison`` nimmt
    keinen neuen Parameter, das Ergebnis ist schlicht falsch).
    """
    import app.loader as loader_mod
    from services.comparison_engine import ComparisonEngine

    ort = _ort("voraus-nz", WP_NZ)
    monkeypatch.setattr(loader_mod, "load_all_locations", lambda *a, **kw: [ort])
    monkeypatch.setattr(
        ComparisonEngine, "run",
        staticmethod(lambda **kwargs: _leeres_vergleichsergebnis(kwargs.get("target_date"))),
    )

    jetzt_utc = datetime(2026, 8, 20, 13, 0, tzinfo=timezone.utc)
    with freeze_time(jetzt_utc):
        _anker(jetzt_utc, WELLINGTON_ZONE, D21)
        _uhr_eingefroren(jetzt_utc)
        servertag = date.today()
        resp = client.get(f"/api/compare?location_ids={ort.id}")

    assert resp.status_code == 200, resp.text
    daten = resp.json()
    assert daten.get("target_date") == D21.isoformat(), (
        f"AC-3: target_date={daten.get('target_date')!r}, erwartet "
        f"{D21.isoformat()} (Ortstag in {WELLINGTON_ZONE} um "
        f"{jetzt_utc.isoformat()}, dort bereits 01:00 Uhr des Folgetags). "
        f"{servertag.isoformat()} heisst: die Serverstunde (< 14 Uhr UTC) hat "
        "'heute' anhand des zonenlosen Servertags gewaehlt."
    )


def test_ac3_sofortvergleich_ortszeit_hinkt_dem_servertag_hinterher(client, monkeypatch):
    """AC-3, Szenario "hinterher" -- Fundstellen F3-F5 (``run_comparison``).

    GIVEN ein Ort in Pago Pago (UTC-11) und ein Zeitpunkt 00:30 UTC am
          20.08. -- ortszeitlich ist erst 13:30 Uhr des VORTAGS (19.08.), auf
          dem Server bereits der 20.08.,
    WHEN  ``GET /api/compare`` OHNE ``target_date`` aufgerufen wird,
    THEN  ist ``target_date`` im JSON-Response der 19.08. -- der Ortstag,
          nicht der um einen Tag zu weit vorne liegende Servertag.

    Vor dem Fix: der Servertag (20.08.) wurde 1:1 uebernommen, ohne den
    negativen Zonenversatz zu beruecksichtigen.

    RED heute: fachlich rot (analog zum "voraus"-Szenario, umgekehrte
    Richtung).
    """
    import app.loader as loader_mod
    from services.comparison_engine import ComparisonEngine

    ort = _ort("hinterher-pago", PAGO)
    monkeypatch.setattr(loader_mod, "load_all_locations", lambda *a, **kw: [ort])
    monkeypatch.setattr(
        ComparisonEngine, "run",
        staticmethod(lambda **kwargs: _leeres_vergleichsergebnis(kwargs.get("target_date"))),
    )

    jetzt_utc = datetime(2026, 8, 20, 0, 30, tzinfo=timezone.utc)
    with freeze_time(jetzt_utc):
        _anker(jetzt_utc, PAGO_ZONE, D19)
        _uhr_eingefroren(jetzt_utc)
        servertag = date.today()
        resp = client.get(f"/api/compare?location_ids={ort.id}")

    assert resp.status_code == 200, resp.text
    daten = resp.json()
    assert daten.get("target_date") == D19.isoformat(), (
        f"AC-3: target_date={daten.get('target_date')!r}, erwartet "
        f"{D19.isoformat()} (Ortstag in {PAGO_ZONE} um {jetzt_utc.isoformat()}, "
        "dort erst 13:30 Uhr des VORTAGS). "
        f"{servertag.isoformat()} heisst: der Servertag wurde uebernommen, "
        "ohne den negativen Zonenversatz zu beruecksichtigen."
    )


def test_ac3_sofortvergleich_serverstunde_ueber_14_ortsstunde_darunter(client, monkeypatch):
    """AC-3, Szenario "Stundenschwelle" -- Fundstellen F3-F5 (``run_comparison``).

    GIVEN ein Ort in Pago Pago (UTC-11) und ein Zeitpunkt 14:30 UTC am
          20.08. -- die SERVERSTUNDE (14) liegt bereits >= 14 Uhr, die
          ORTSSTUNDE (03:30) liegt NOCH darunter, waehrend Ortstag UND
          Servertag auf DEMSELBEN Kalendertag liegen (20.08., KEIN
          Tagesumbruch),
    WHEN  ``GET /api/compare`` OHNE ``target_date`` aufgerufen wird,
    THEN  ist ``target_date`` im JSON-Response der 20.08. -- die ORTSSTUNDE
          entscheidet (< 14, kein Aufschlag), NICHT die Serverstunde.

    Grund fuer diesen dritten Test (Team-Lead-Review nach dem ersten
    Durchlauf): die beiden Tests oben ("voraus"/"hinterher") haben in BEIDEN
    Faellen Orts- UND Serverstunde unter 14 -- der Stundenzweig ist dort
    identisch. Eine Implementierung, die NUR den Tag auf ``first_resolvable_tz``
    umstellt, die Stunde aber weiterhin ueber die (zonenlose) Serveruhr
    entscheidet, besteht BEIDE Tests oben unbemerkt. Erst dieser dritte Test
    erzwingt, dass auch die STUNDE aus derselben Ortszeit kommt wie der Tag
    -- exakt die Klasse "Zusicherung behauptet, von keinem Test bewacht", die
    dieses Epic bereits mehrfach getroffen hat.

    Vorbedingungs-Anker: HIER faellt bewusst NICHT der Ortstag vom Servertag
    ab (beide 20.08.) -- der geteilte ``_anker`` (der GENAU diese Divergenz
    erzwingt, s. ``tests/tdd/conftest.py:88-109``) ist deshalb das FALSCHE
    Werkzeug fuer diesen Test und wird hier bewusst NICHT verwendet. Der
    diskriminierende Umstand ist ein anderer: Orts- und Serverstunde liegen
    auf VERSCHIEDENEN Seiten der 14-Uhr-Schwelle, bei GLEICHEM Kalendertag.
    Das wird als eigene Vorbedingung explizit gemessen (statt des Ankers),
    bevor die Hauptzusicherung geprueft wird -- Muster identisch zum Anker
    (erst messen, dann behaupten), nur mit der fuer diesen Fall richtigen
    Groesse.

    RED heute: fachlich rot -- die Serverstunde (>= 14) haengt den Tag an,
    obwohl am Ort noch derselbe Kalendertag laeuft.
    """
    import app.loader as loader_mod
    from services.comparison_engine import ComparisonEngine

    ort = _ort("stunde-pago", PAGO)
    monkeypatch.setattr(loader_mod, "load_all_locations", lambda *a, **kw: [ort])
    monkeypatch.setattr(
        ComparisonEngine, "run",
        staticmethod(lambda **kwargs: _leeres_vergleichsergebnis(kwargs.get("target_date"))),
    )

    jetzt_utc = datetime(2026, 8, 20, 14, 30, tzinfo=timezone.utc)
    erwarteter_tag = date(2026, 8, 20)
    with freeze_time(jetzt_utc):
        _uhr_eingefroren(jetzt_utc)
        ortszeit = jetzt_utc.astimezone(ZoneInfo(PAGO_ZONE))
        assert ortszeit.hour < 14 <= jetzt_utc.hour, (
            "Testaufbau nicht diskriminierend: die Ortsstunde muss < 14, die "
            f"Serverstunde muss >= 14 sein -- Ortsstunde {ortszeit.hour}, "
            f"Serverstunde {jetzt_utc.hour}"
        )
        assert ortszeit.date() == jetzt_utc.date() == erwarteter_tag, (
            "Testaufbau nicht diskriminierend: Ortstag und Servertag muessen "
            f"DENSELBEN Kalendertag tragen ({erwarteter_tag}) -- sonst "
            "wiederholte dieser Test den Tagesumbruch der beiden Szenarien "
            "oben, statt die Stundenschwelle ISOLIERT zu pruefen. Ortstag "
            f"{ortszeit.date()}, Servertag {jetzt_utc.date()}"
        )
        resp = client.get(f"/api/compare?location_ids={ort.id}")

    assert resp.status_code == 200, resp.text
    daten = resp.json()
    assert daten.get("target_date") == erwarteter_tag.isoformat(), (
        f"AC-3: target_date={daten.get('target_date')!r}, erwartet "
        f"{erwarteter_tag.isoformat()} (Ortsstunde {ortszeit.hour}:xx < 14, "
        "kein Aufschlag -- Ortstag und Servertag sind an diesem Tag GLEICH, "
        "nur die Stunde entscheidet). "
        f"{(erwarteter_tag + timedelta(days=1)).isoformat()} heisst: die "
        f"Serverstunde ({jetzt_utc.hour} Uhr UTC, >= 14) hat den Tag "
        "angehaengt, obwohl am Ort (Pago Pago) noch derselbe Kalendertag "
        "laeuft -- eine Implementierung, die nur den TAG auf Ortszeit "
        "umstellt, die STUNDE aber weiter von der Serveruhr nimmt, waere "
        "durch die beiden Tag-Tests oben NICHT gefangen worden."
    )


# ═══════════════ AC-4: tote Funktion dict_to_comparison_result (F6) ═══════════════


def test_ac4_dict_to_comparison_result_ist_ersatzlos_entfernt():
    """AC-4 -- ``services.comparison_engine.dict_to_comparison_result`` (F6).

    GIVEN die Funktion hat 0 Aufrufer in src/, api/, tests/, frontend/,
          internal/, cmd/ (Volltextsuche, Definitionsstelle ausgenommen --
          Kontext-Dokument, vom analysis-challenger bestaetigt),
    WHEN  sie ersatzlos entfernt wird,
    THEN  gelingt ``import services.comparison_engine`` weiterhin, aber
          ``hasattr(mod, "dict_to_comparison_result")`` liefert ``False``.

    RED heute: fachlich rot -- die Funktion existiert noch
    (``hasattr`` liefert heute ``True``).
    """
    import services.comparison_engine as mod

    assert hasattr(mod, "ComparisonEngine"), (
        "Testaufbau: das Modul muss weiterhin importierbar bleiben und "
        "ComparisonEngine exportieren"
    )
    assert not hasattr(mod, "dict_to_comparison_result"), (
        "AC-4: services.comparison_engine.dict_to_comparison_result existiert "
        "noch -- die Funktion hat 0 Aufrufer im gesamten Repo (Kontext-Dokument, "
        "Volltextsuche) und soll ersatzlos entfallen"
    )


# ═══════════════ AC-5: Footer "Naechster Versand" folgt header_tz (F7) ═══════════════


def _footer_ergebnis(target_date: date) -> ComparisonResult:
    ort = SavedLocation(id="footer-nz", name="Footer-NZ", lat=WP_NZ[0], lon=WP_NZ[1],
                        elevation_m=100)
    return ComparisonResult(
        locations=[LocationResult(location=ort)], time_window=(9, 16),
        target_date=target_date,
    )


def test_ac5_footer_naechster_versand_weekly_folgt_der_kopfzeilen_zone():
    """AC-5, ``weekly``-Schedule -- ``_compute_next_send``/``_render_abo_footer`` (F7).

    GIVEN eine versendete Vergleichs-Mail mit EINEM Ort in Neuseeland
          (UTC+12, damit ``header_tz`` = diese Zone traegt) und einem
          ``weekly``-Abo auf Wochentag Freitag (4), zu einem Zeitpunkt, an
          dem der ORTSTAG (21.08., ein Freitag) bereits einen Tag vor dem
          Servertag (20.08., Donnerstag) liegt,
    WHEN  ``render_compare_email`` den Footer "Naechster Versand" berechnet,
    THEN  zeigt der Footer den 28.08.2026 -- den naechsten Freitag AB dem
          ORTSTAG (21.08. IST bereits Freitag, also faellt der naive
          "0 Tage"-Fall auf den `or 7`-Zweig, naechster Freitag = 28.08.).

    Vor dem Fix rechnet ``_compute_next_send`` mit ``date.today()``
    (Servertag 20.08., ein Donnerstag): naechster Freitag = 21.08. -- ein
    ANDERES Datum als der korrekte 28.08., weil der Wochentag-Modulo-7-Wert
    fuer Donnerstag->Freitag (1 Tag) vom Freitag->Freitag-Fall (7 Tage,
    `or 7`-Zweig) abweicht. Genau dieser Weekday-Randfall macht die beiden
    Zeitbasen sichtbar unterscheidbar (bei den meisten anderen Wochentagen
    wuerde ein Ein-Tages-Versatz im Modulo-7 wieder herausfallen -- gemessen,
    nicht vermutet).

    RED heute: fachlich rot -- der Footer zeigt den Servertag-Wert.
    """
    from output.renderers.comparison import render_compare_email

    with freeze_time(MITTAGS_UTC):
        _anker(MITTAGS_UTC, WELLINGTON_ZONE, D21)
        _uhr_eingefroren(MITTAGS_UTC)
        servertag = date.today()
        assert D21.weekday() == 4 and servertag.weekday() == 3, (
            "Testaufbau nicht diskriminierend: Ortstag muss ein Freitag (4), "
            f"Servertag ein Donnerstag (3) sein -- Ortstag {D21} "
            f"({D21.weekday()}), Servertag {servertag} ({servertag.weekday()})"
        )
        ergebnis = _footer_ergebnis(D21)
        html_body, _text = render_compare_email(
            ergebnis, preset_name="Footer-Test-Weekly",
            preset_schedule="weekly", preset_weekday=4,
        )

    erwartet = "28.08.2026"
    falsch_server = "21.08.2026"
    assert erwartet in html_body, (
        f"AC-5 (weekly): Footer zeigt nicht {erwartet!r} (naechster Freitag ab "
        f"dem ORTSTAG {D21}, Wochentag 4). Enthaelt stattdessen "
        f"{falsch_server!r}: {falsch_server in html_body} -- das waere der "
        "Servertag-Wert (date.today() statt header_tz)."
    )


def test_ac5_footer_naechster_versand_daily_folgt_der_kopfzeilen_zone():
    """AC-5, ``daily``-Schedule -- ``_compute_next_send``/``_render_abo_footer`` (F7).

    GIVEN dieselbe Lage wie oben, aber ein ``daily``-Abo,
    WHEN  ``render_compare_email`` den Footer berechnet,
    THEN  zeigt der Footer den 22.08.2026 -- den Ortstag (21.08.) plus 1 Tag.

    Vor dem Fix: Servertag (20.08.) + 1 Tag = 21.08. -- ein anderes Datum.

    RED heute: fachlich rot.
    """
    from output.renderers.comparison import render_compare_email

    with freeze_time(MITTAGS_UTC):
        _anker(MITTAGS_UTC, WELLINGTON_ZONE, D21)
        _uhr_eingefroren(MITTAGS_UTC)
        servertag = date.today()
        ergebnis = _footer_ergebnis(D21)
        html_body, _text = render_compare_email(
            ergebnis, preset_name="Footer-Test-Daily",
            preset_schedule="daily", preset_weekday=None,
        )

    erwartet = "22.08.2026"
    falsch_server = "21.08.2026"
    assert erwartet in html_body, (
        f"AC-5 (daily): Footer zeigt nicht {erwartet!r} (Ortstag {D21} + 1 Tag). "
        f"Enthaelt stattdessen {falsch_server!r}: {falsch_server in html_body} -- "
        f"das waere der Servertag ({servertag}) + 1 Tag."
    )
