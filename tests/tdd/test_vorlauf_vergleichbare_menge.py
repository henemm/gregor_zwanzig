"""TDD RED — Issue #2261 Teil A (A-1): vergleichbare Menge (AC-5) und
Briefing-Abgleich bei frueher Sicht (AC-6).

SPEC: docs/specs/modules/feat_2261_a1_radar_vorlauf.md (AC-5, AC-6;
Implementation Details §4)

Bei Schwelle = Quell-Horizont (180 Min) wird ein Ereignis erstmals bei Onset
~170 gemeldet. Das Mengenfenster (`window_precip_mm`, 60 Min ab jetzt) liegt
dann VOR dem Ereignis — die Menge ist ein Vorlauf-Artefakt (≈ 0). Wird sie
als Vergleichsbasis gespeichert, ueberholt spaeter jede Menge >= 2 mm die
Sperrzeit „als Verschaerfung", obwohl sich nichts verschaerft hat.

Aufbau: ECHTE Laeufe von `check_radar_alerts()` ueber die Alarm-Pruefstrecke
(#2050 S1). Die Vergleichsbasis entsteht durch einen echten ersten Lauf —
das Produkt schreibt sie selbst, keine Fixture setzt den Zustand. Gestellt
ist nur die Radar-Quelle: echter `RadarNowcastService` an seiner DI-Naht
`frame_source=` (statt `nass()`, das `window_precip_mm` auf 0.0 laesst —
AC-5/AC-6 brauchen echte, aus Frames akkumulierte Mengen). Die Frames
haengen an ABSOLUTEN Zeitpunkten; die Uhr laeuft im Cron-Raster
(7/22/37/52) weiter, der Onset schrumpft dadurch wie in Produktion.

Jeder Test laeuft fuer zwei verschiedene Nutzer mit DERSELBEN Trip-Kennung
(ein Zustandsleck ueber einen geteilten/„default"-Speicher fiele dann auf),
und jeder Test traegt eine Aufbau-Kontrolle mit Onset <= 55 (loest schon
heute aus): ohne sie waere ein RED am Erstsicht-Schritt nicht von einem
kaputten Aufbau zu unterscheiden.

Kein Mock()/patch()/MagicMock, keine Dateiinhalt-Checks.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from freezegun import freeze_time

from app.loader import save_trip
from app.models import (
    ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider,
    SegmentWeatherData, SegmentWeatherSummary, TripReportConfig,
)
from app.trip import Stage, Trip, Waypoint
from services import alert_log
from services.radar_service import RadarNowcastService
from services.weather_snapshot import WeatherSnapshotService
from utils.timezone import tz_for_coords

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
from tests.tdd.test_952_onset_alert_fidelity import _clean_user
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (
    _settings_all_channels, _write_tier,
)

# Cron-Raster 7/22/37/52: erster Lauf um :52. Ereignisbeginn 170 Min spaeter.
T0 = datetime(2026, 4, 5, 10, 52, tzinfo=timezone.utc)
ONSET_ERSTSICHT = 170
LAT, LON = 42.20, 9.10  # Korsika (UTC+2 im April) — Ortstag == UTC-Tag
# ~1 km Etappe: Reststrecke < Punktabstand (2 km) ⇒ Einzelpunkt-Fall, das
# Aufenthaltsfenster ist nach oben offen (Spec §3) — der Messort zur
# Ereigniszeit spielt in diesen Tests bewusst keine Rolle.
LAT_ZIEL = 42.209

SPERRZEIT_LANG_MIN = 240  # Nutzer-Sperrzeit > 120 Min (AC-5 Given)
BRIEFING_MM = 1.0  # Ankuendigung >= 0,5 mm (AC-6 Given)


def uid(tag: str) -> str:
    return f"tdd-2261-a1-{tag}-{uuid.uuid4().hex[:6]}"


def lauf_zeit(n: int) -> datetime:
    """n-ter Cron-Lauf nach T0 (15-Min-Raster)."""
    return T0 + timedelta(minutes=15 * n)


# ---------------------------------------------------------------------------
# Radar-Quelle: Frames an ABSOLUTEN Zeitpunkten
# ---------------------------------------------------------------------------

def regen_ab(beginn: datetime, rate_mm_h: float, *, frames: int = 10,
             gewitter: bool = False):
    """Frame-Quelle: trocken bis `beginn`, danach `frames` Frames im
    15-Min-Raster mit `rate_mm_h` (optional konvektiv). Koordinaten-
    unabhaengig — jeder Messpunkt sieht dieselbe Lage."""
    def _quelle(lat: float, lon: float) -> list:
        from providers.brightsky import RadarFrame
        return [
            RadarFrame(
                timestamp=beginn + timedelta(minutes=15 * k),
                precip_mm_h=rate_mm_h, is_convective=gewitter,
            )
            for k in range(frames)
        ]
    return _quelle


def radar(quelle) -> RadarNowcastService:
    return RadarNowcastService(frame_source=quelle)


def messe(quelle, at: datetime):
    """Das ECHTE Nowcast-Ergebnis dieser Quelle zur Uhrzeit `at` — die
    Testkonstruktion wird an der Quelle gemessen, nicht behauptet."""
    from services.radar_cache import reset_shared_radar_cache_for_tests
    with freeze_time(at):
        reset_shared_radar_cache_for_tests()
        ergebnis = radar(quelle).get_nowcast(LAT, LON)
        reset_shared_radar_cache_for_tests()
    return ergebnis


# ---------------------------------------------------------------------------
# Trip-Aufbau
# ---------------------------------------------------------------------------

def _hhmm(at: datetime) -> str:
    return at.astimezone(tz_for_coords(LAT, LON)).strftime("%H:%M")


def baue_trip(
    user_id: str, trip_id: str, ankuenfte_min: list[int], *,
    cooldown_min: int, lats: list[float] | None = None,
) -> Trip:
    """Eine Etappe mit Wegpunkten zu festen Ankunftszeiten (Minuten relativ
    zu T0, Ortszeit-`arrival_override`), gespeichert unter `user_id`. Alle
    Segmente < 2 km (Einzelpunkt-Fall)."""
    lats = lats or [LAT + 0.009 * i for i in range(len(ankuenfte_min))]
    tz = tz_for_coords(LAT, LON)
    with freeze_time(T0):
        wps = [
            Waypoint(
                id=f"W{i}", name=f"W{i}", lat=lat, lon=LON,
                elevation_m=1000.0,
                arrival_override=_hhmm(T0 + timedelta(minutes=off)),
            )
            for i, (lat, off) in enumerate(zip(lats, ankuenfte_min))
        ]
        start_local = (T0 + timedelta(minutes=ankuenfte_min[0])).astimezone(tz)
        stage = Stage(
            id="T1", name="Tag 1", date=T0.astimezone(tz).date(),
            start_time=start_local.time().replace(second=0, microsecond=0),
            waypoints=wps,
        )
        trip = Trip(id=trip_id, name="Vorlauf-Trip", stages=[stage])
        trip.report_config = TripReportConfig(
            trip_id=trip_id, alert_on_changes=True,
            send_email=True, send_telegram=True,
        )
        trip.alert_cooldown_minutes = cooldown_min
        save_trip(trip, user_id=user_id)
    return trip


def nutzer(tag: str) -> str:
    """Frischer Nutzer, Premium (kein Tageslimit) — Tier VOR der Pruefstrecke
    schreiben, die macht danach Read-Modify-Write auf `user.json`."""
    u = uid(tag)
    _clean_user(u)
    _write_tier(u, "premium")
    return u


def briefing_anker(user_id: str, trip: Trip, mm: float, at: datetime) -> None:
    """Datierter Briefing-Schnappschuss ueber den produktiven Schreibweg
    `save_dated()` — genau die Datei, die `check_radar_alerts()` per
    `load_dated()` liest. Segment/Datum aus demselben Aufloeser wie der
    Pruefling (Muster `test_alarm_szenario_briefing_ueberholung_zeitreihe`)."""
    from services.trip_day import trip_local_today
    from services.trip_segments import resolve_current_segment

    with freeze_time(at):
        jetzt = datetime.now(timezone.utc)
        aufgeloest = resolve_current_segment(trip, jetzt, trip_local_today(trip, jetzt))
        assert aufgeloest is not None, (
            "Aufbau: der Trip muss zur gestellten Uhr ein aktives Segment haben."
        )
        segment, segment_datum = aufgeloest
        tagesbeginn = jetzt.replace(hour=0, minute=0, second=0, microsecond=0)
        reihe = NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=[ForecastDataPoint(ts=tagesbeginn + timedelta(hours=h), precip_1h_mm=mm)
                  for h in range(48)],
        )
        WeatherSnapshotService(user_id).save_dated(trip.id, segment_datum, [
            SegmentWeatherData(
                segment=segment, timeseries=reihe, aggregated=SegmentWeatherSummary(),
                fetched_at=jetzt, provider="openmeteo",
            )])


def gruende_seit(user_id: str, trip: Trip, seit: datetime) -> set[str]:
    """Unterdrueckungsgruende des Radar-Zweigs seit `seit` — aus dem
    Protokoll, das der Pruefling selbst schreibt."""
    vorfaelle = alert_log.read_undelivered(
        user_id, entity_id=trip.id, entity_type="trip", since=seit,
    )
    return {
        str(g) for v in vorfaelle if v.trigger == alert_log.REASON_NOWCAST
        for g in v.reasons
    }


def gelesene_briefing_werte(user_id: str, trip: Trip, seit: datetime) -> list[float]:
    """Die Briefing-Mengen, die der Pruefling selbst gelesen hat
    (`briefing_announced:<mm>mm`)."""
    return [
        float(g[len("briefing_announced:"):-2])
        for g in gruende_seit(user_id, trip, seit)
        if g.startswith("briefing_announced:") and g.endswith("mm")
    ]


def aufbau_kontrolle(tag: str, trip_id: str, *, briefing_mm: float | None = None) -> None:
    """Positivkontrolle des Aufbaus: derselbe Trip-Bauer, Regen bei Onset 38
    (≤ 55, loest schon HEUTE aus), unangekuendigt bzw. mit grosser Menge.
    Scheitert sie, ist der Aufbau kaputt — nicht das Feature."""
    u = nutzer(f"{tag}-kontrolle")
    try:
        trip = baue_trip(u, trip_id, [-60, 300], cooldown_min=SPERRZEIT_LANG_MIN)
        if briefing_mm is not None:
            briefing_anker(u, trip, briefing_mm, T0)
        strecke = AlarmPruefstrecke(user_id=u, settings=_settings_all_channels())
        lauf = strecke.lauf(
            at=T0, zweig="radar", trip=trip,
            radar_service=radar(regen_ab(T0 + timedelta(minutes=38), 15.0)),
        )
        assert lauf.triggered_count == 1, (
            f"Aufbau defekt: Regen bei Onset 38 (15 mm/h) muss mit diesem "
            f"Trip-Aufbau schon heute alarmieren — sonst sagt ein RED am "
            f"Erstsicht-Schritt nichts ueber das Feature. "
            f"triggered_count={lauf.triggered_count}, "
            f"Gruende={gruende_seit(u, trip, T0)!r}"
        )
    finally:
        _clean_user(u)


# ===========================================================================
# AC-5 — vergleichbare Menge, Sperrzeit-Ueberholung
# ===========================================================================

def _erstsicht_170(strecke: AlarmPruefstrecke, trip: Trip, rate_mm_h: float = 2.0):
    """Lauf 0 um T0: Regen beginnt um T0+170 (Onset 170, Menge im
    Mengenfenster ≈ 0)."""
    return strecke.lauf(
        at=lauf_zeit(0), zweig="radar", trip=trip,
        radar_service=radar(regen_ab(T0 + timedelta(minutes=ONSET_ERSTSICHT), rate_mm_h)),
    )


def test_basis_aus_vorlauf_artefakt_ist_kein_durchbruch():
    """AC-5: Erstsicht bei Onset 170 (Menge ≈ 0) bucht eine Sperrzeit von
    240 Min. Zwei Laeufe spaeter liegt die Menge bei >= 2 mm (Onset 38) —
    das ist KEINE Verschaerfung gegen eine echte Basis, sondern nur das
    Vorlauf-Artefakt 0,0. Erwartet: kein Durchbruch, Grund Sperrzeit."""
    trip_id = "trip-2261-ac5-artefakt"
    aufbau_kontrolle("ac5a", trip_id)

    # Testkonstruktion an der Quelle gemessen.
    erst = messe(regen_ab(T0 + timedelta(minutes=ONSET_ERSTSICHT), 2.0), lauf_zeit(0))
    assert erst.onset_minutes == ONSET_ERSTSICHT and erst.window_precip_mm < 0.05, (
        f"Konstruktion: Erstsicht muss Onset 170 mit Menge ≈ 0 liefern, "
        f"gemessen onset={erst.onset_minutes} menge={erst.window_precip_mm}"
    )
    spaet_quelle = regen_ab(lauf_zeit(2) + timedelta(minutes=38), 10.0)
    spaet = messe(spaet_quelle, lauf_zeit(2))
    assert spaet.onset_minutes == 38 and spaet.window_precip_mm >= 2.0, (
        f"Konstruktion: Lauf 2 muss Onset 38 mit >= 2 mm liefern, gemessen "
        f"onset={spaet.onset_minutes} menge={spaet.window_precip_mm}"
    )

    for tag in ("a", "b"):
        u = nutzer(f"ac5a-{tag}")
        try:
            trip = baue_trip(u, trip_id, [-60, 300], cooldown_min=SPERRZEIT_LANG_MIN)
            strecke = AlarmPruefstrecke(user_id=u, settings=_settings_all_channels())

            lauf0 = _erstsicht_170(strecke, trip)
            assert lauf0.triggered_count == 1, (
                f"[{tag}] Erstsicht bei Onset 170 muss alarmieren (Schwelle = "
                f"Quell-Horizont, AC-1) — erst dieser Lauf schreibt die "
                f"Vorlauf-Basis, die AC-5 prueft. triggered_count="
                f"{lauf0.triggered_count}"
            )

            lauf1 = strecke.lauf(
                at=lauf_zeit(1), zweig="radar", trip=trip,
                radar_service=radar(regen_ab(T0 + timedelta(minutes=ONSET_ERSTSICHT), 2.0)),
            )
            assert lauf1.triggered_count == 0, (
                f"[{tag}] Lauf 1 (dasselbe Ereignis, Onset 155) muss an der "
                f"Sperrzeit haengen. triggered_count={lauf1.triggered_count}"
            )

            lauf2 = strecke.lauf(
                at=lauf_zeit(2), zweig="radar", trip=trip,
                radar_service=radar(spaet_quelle),
            )
            assert lauf2.triggered_count == 0, (
                f"[{tag}] AC-5: {spaet.window_precip_mm:.2f} mm bei Onset 38 "
                f"gegen eine Basis aus einem NICHT vergleichbaren Lauf (Onset "
                f"170, Menge ≈ 0) ist kein Durchbruch — die Basis gilt als "
                f"None. triggered_count={lauf2.triggered_count}, Kanaele: "
                f"mail={len(lauf2.mail)} telegram={len(lauf2.telegram)}"
            )
            gruende = gruende_seit(u, trip, lauf_zeit(2))
            assert alert_log.REASON_COOLDOWN in gruende, (
                f"[{tag}] AC-5: die Stille in Lauf 2 muss von der Sperrzeit "
                f"kommen (Grund {alert_log.REASON_COOLDOWN!r}). Gefunden: {gruende!r}"
            )
        finally:
            _clean_user(u)


def test_dringlichkeit_bricht_trotzdem_durch():
    """AC-5: Nach der Erstsicht bei Onset 170 (Sperrzeit 240 Min, Basis
    nicht vergleichbar) wird die Lage zum GEWITTER — bei kleiner Menge
    (< 2 mm, keine Mengen-Ueberholung moeglich). Die Dringlichkeit steigt
    (MODERATE -> HIGH): der Alarm bricht trotzdem durch."""
    trip_id = "trip-2261-ac5-dringlich"
    aufbau_kontrolle("ac5d", trip_id)

    gewitter_quelle = regen_ab(lauf_zeit(2) + timedelta(minutes=38), 1.0, gewitter=True)
    gemessen = messe(gewitter_quelle, lauf_zeit(2))
    assert gemessen.is_convective and gemessen.onset_minutes == 38, (
        f"Konstruktion: Lauf 2 muss ein Gewitter bei Onset 38 sein, gemessen "
        f"is_convective={gemessen.is_convective} onset={gemessen.onset_minutes}"
    )
    assert gemessen.window_precip_mm < 2.0, (
        f"Konstruktion: die Menge muss UNTER der Ueberholungs-Untergrenze "
        f"liegen ({gemessen.window_precip_mm} mm) — sonst traegt die Menge "
        f"den Durchbruch und die Dringlichkeit ist nicht geprueft."
    )

    for tag in ("a", "b"):
        u = nutzer(f"ac5d-{tag}")
        try:
            trip = baue_trip(u, trip_id, [-60, 300], cooldown_min=SPERRZEIT_LANG_MIN)
            strecke = AlarmPruefstrecke(user_id=u, settings=_settings_all_channels())

            lauf0 = _erstsicht_170(strecke, trip)
            assert lauf0.triggered_count == 1, (
                f"[{tag}] Erstsicht bei Onset 170 muss alarmieren (Schwelle = "
                f"Quell-Horizont, AC-1). triggered_count={lauf0.triggered_count}"
            )

            lauf2 = strecke.lauf(
                at=lauf_zeit(2), zweig="radar", trip=trip,
                radar_service=radar(gewitter_quelle),
            )
            assert lauf2.triggered_count == 1, (
                f"[{tag}] AC-5: Gewitter nach Erstsicht (Dringlichkeit steigt) "
                f"muss die laufende Sperrzeit durchbrechen, auch wenn die Basis "
                f"aus dem Vorlauf-Lauf nicht vergleichbar ist. "
                f"triggered_count={lauf2.triggered_count}, Gruende="
                f"{gruende_seit(u, trip, lauf_zeit(2))!r}"
            )
        finally:
            _clean_user(u)


def test_vergleichbare_menge_ueberholt_weiter_die_sperrzeit():
    """AC-5 Gegenprobe (Regressionswaechter): Erstmeldung bei Onset 53
    (< 60, VERGLEICHBAR, kleine Menge) bucht Sperrzeit und Basis. Einen Lauf
    spaeter liegt eine vergleichbare Menge >= Faktor 2 und >= 2 mm vor —
    die Sperrzeit wird wie heute ueberholt."""
    trip_id = "trip-2261-ac5-vergleichbar"
    basis_quelle = regen_ab(T0 + timedelta(minutes=53), 2.0)
    basis = messe(basis_quelle, lauf_zeit(0))
    stark_quelle = regen_ab(lauf_zeit(1) + timedelta(minutes=23), 15.0)
    stark = messe(stark_quelle, lauf_zeit(1))
    assert basis.onset_minutes == 53 and 0.0 < basis.window_precip_mm < 1.0, (
        f"Konstruktion: Basis-Lauf Onset 53 mit kleiner, echter Menge — gemessen "
        f"onset={basis.onset_minutes} menge={basis.window_precip_mm}"
    )
    assert (stark.window_precip_mm >= 2.0
            and stark.window_precip_mm >= 2 * basis.window_precip_mm), (
        f"Konstruktion: Lauf 1 muss die Basis ueberholen (>= 2 mm und >= "
        f"Faktor 2) — gemessen {stark.window_precip_mm} gegen "
        f"{basis.window_precip_mm}"
    )

    for tag in ("a", "b"):
        u = nutzer(f"ac5v-{tag}")
        try:
            trip = baue_trip(u, trip_id, [-60, 300], cooldown_min=SPERRZEIT_LANG_MIN)
            strecke = AlarmPruefstrecke(user_id=u, settings=_settings_all_channels())
            lauf0 = strecke.lauf(
                at=lauf_zeit(0), zweig="radar", trip=trip, radar_service=radar(basis_quelle),
            )
            assert lauf0.triggered_count == 1, (
                f"[{tag}] Vorbedingung: Erstmeldung bei Onset 53 muss alarmieren "
                f"und die Basis buchen. triggered_count={lauf0.triggered_count}"
            )
            lauf1 = strecke.lauf(
                at=lauf_zeit(1), zweig="radar", trip=trip, radar_service=radar(stark_quelle),
            )
            assert lauf1.triggered_count == 1, (
                f"[{tag}] AC-5: eine VERGLEICHBARE Menge ({stark.window_precip_mm:.2f} "
                f"mm gegen Basis {basis.window_precip_mm:.2f} mm, beide Onset < 60) "
                f"muss die Sperrzeit weiterhin ueberholen. triggered_count="
                f"{lauf1.triggered_count}, Gruende={gruende_seit(u, trip, lauf_zeit(1))!r}"
            )
        finally:
            _clean_user(u)


# ===========================================================================
# AC-6 — Briefing-Abgleich bei frueher Sicht (C-1)
# ===========================================================================

def test_angekuendigter_regen_frueh_wird_unterdrueckt():
    """AC-6: Briefing kuendigt 1,0 mm an; der Radar sieht denselben Regen
    bei Onset 170. Die (nicht vergleichbare) Menge ueberholt die Ankuendigung
    nicht — der Alarm wird unterdrueckt, Protokoll `briefing_announced`, und
    zwar mit dem tatsaechlich gelesenen Briefing-Wert (nicht still, weil der
    Regen gar nicht faellig war)."""
    trip_id = "trip-2261-ac6-angekuendigt"
    aufbau_kontrolle("ac6a", trip_id, briefing_mm=BRIEFING_MM)

    for tag in ("a", "b"):
        u = nutzer(f"ac6a-{tag}")
        try:
            trip = baue_trip(u, trip_id, [-60, 300], cooldown_min=SPERRZEIT_LANG_MIN)
            briefing_anker(u, trip, BRIEFING_MM, T0)
            strecke = AlarmPruefstrecke(user_id=u, settings=_settings_all_channels())
            lauf = strecke.lauf(
                at=T0, zweig="radar", trip=trip,
                radar_service=radar(regen_ab(T0 + timedelta(minutes=ONSET_ERSTSICHT), 11.0)),
            )
            assert lauf.triggered_count == 0, (
                f"[{tag}] AC-6: angekuendigter Regen bei Onset 170 darf nicht "
                f"alarmieren. triggered_count={lauf.triggered_count}"
            )
            assert gelesene_briefing_werte(u, trip, T0) == [BRIEFING_MM], (
                f"[{tag}] AC-6: die Unterdrueckung muss vom Briefing-Abgleich "
                f"kommen (Protokoll `briefing_announced:{BRIEFING_MM}mm`) — bei "
                f"Onset 170 muss der Regen also faellig sein und den Abgleich "
                f"erreichen. Protokolliert: {gruende_seit(u, trip, T0)!r}"
            )
        finally:
            _clean_user(u)


def test_unangekuendigter_regen_frueh_wird_gemeldet():
    """AC-6: Ohne Ankuendigung im Briefing (0,0 mm) wird derselbe Regen bei
    Onset 170 gemeldet — auf den konfigurierten Kanaelen."""
    trip_id = "trip-2261-ac6-unangekuendigt"
    aufbau_kontrolle("ac6u", trip_id, briefing_mm=0.0)

    for tag in ("a", "b"):
        u = nutzer(f"ac6u-{tag}")
        try:
            trip = baue_trip(u, trip_id, [-60, 300], cooldown_min=SPERRZEIT_LANG_MIN)
            briefing_anker(u, trip, 0.0, T0)
            strecke = AlarmPruefstrecke(user_id=u, settings=_settings_all_channels())
            lauf = strecke.lauf(
                at=T0, zweig="radar", trip=trip,
                radar_service=radar(regen_ab(T0 + timedelta(minutes=ONSET_ERSTSICHT), 11.0)),
            )
            assert lauf.triggered_count == 1, (
                f"[{tag}] AC-6: unangekuendigter Regen bei Onset 170 muss "
                f"gemeldet werden. triggered_count={lauf.triggered_count}, "
                f"Gruende={gruende_seit(u, trip, T0)!r}"
            )
            assert lauf.mail and lauf.telegram, (
                f"[{tag}] AC-6: der Alarm muss die konfigurierten Kanaele "
                f"erreichen: mail={lauf.mail!r} telegram={lauf.telegram!r}"
            )
        finally:
            _clean_user(u)


def test_spaeter_vergleichbar_ueberholt_wie_heute():
    """AC-6: Erstsicht des angekuendigten Regens bei Onset 170 ist
    unterdrueckt (`briefing_announced`). Zwei Laeufe spaeter ist das Ereignis
    vergleichbar (Onset < 60) und ueberholt die Ankuendigung nach dem heutigen
    Faktor (>= 2 x 1,0 mm und >= 2 mm) — jetzt wird gemeldet."""
    trip_id = "trip-2261-ac6-spaeter"
    aufbau_kontrolle("ac6s", trip_id, briefing_mm=BRIEFING_MM)

    spaet_quelle = regen_ab(lauf_zeit(8) + timedelta(minutes=38), 11.0)
    spaet = messe(spaet_quelle, lauf_zeit(8))
    assert spaet.onset_minutes == 38 and spaet.window_precip_mm >= 2 * BRIEFING_MM, (
        f"Konstruktion: Spaet-Lauf Onset 38 mit Menge >= Faktor x Ankuendigung, "
        f"gemessen onset={spaet.onset_minutes} menge={spaet.window_precip_mm}"
    )

    for tag in ("a", "b"):
        u = nutzer(f"ac6s-{tag}")
        try:
            trip = baue_trip(u, trip_id, [-60, 300], cooldown_min=SPERRZEIT_LANG_MIN)
            briefing_anker(u, trip, BRIEFING_MM, T0)
            strecke = AlarmPruefstrecke(user_id=u, settings=_settings_all_channels())
            # Ereignis beginnt fest um T0+170; Lauf 8 (T0+120) sieht es bei
            # Onset 50 — die Quelle fuer Lauf 8 ist jedoch eine schaerfere
            # Neu-Extrapolation (Onset 38, 11 mm/h).
            lauf0 = strecke.lauf(
                at=lauf_zeit(0), zweig="radar", trip=trip,
                radar_service=radar(regen_ab(T0 + timedelta(minutes=ONSET_ERSTSICHT), 11.0)),
            )
            assert lauf0.triggered_count == 0, (
                f"[{tag}] Erstsicht des angekuendigten Regens bei Onset 170 muss "
                f"unterdrueckt sein. triggered_count={lauf0.triggered_count}"
            )
            assert gelesene_briefing_werte(u, trip, lauf_zeit(0)) == [BRIEFING_MM], (
                f"[{tag}] AC-6: Erstsicht bei Onset 170 muss den Briefing-Abgleich "
                f"erreichen und dort unterdrueckt werden (`briefing_announced`). "
                f"Protokolliert: {gruende_seit(u, trip, lauf_zeit(0))!r}"
            )
            lauf8 = strecke.lauf(
                at=lauf_zeit(8), zweig="radar", trip=trip, radar_service=radar(spaet_quelle),
            )
            assert lauf8.triggered_count == 1, (
                f"[{tag}] AC-6: spaeter vergleichbar (Onset 38, "
                f"{spaet.window_precip_mm:.2f} mm gegen {BRIEFING_MM} mm "
                f"Ankuendigung) muss wie heute ueberholen und melden. "
                f"triggered_count={lauf8.triggered_count}, Gruende="
                f"{gruende_seit(u, trip, lauf_zeit(8))!r}"
            )
        finally:
            _clean_user(u)


def test_gewitter_durchbricht_ankuendigung():
    """AC-6 (#883): Ein Gewitter bei Onset 170 durchbricht die
    Briefing-Unterdrueckung wie bisher — auch bei frueher Sicht."""
    trip_id = "trip-2261-ac6-gewitter"
    aufbau_kontrolle("ac6g", trip_id, briefing_mm=BRIEFING_MM)

    quelle = regen_ab(T0 + timedelta(minutes=ONSET_ERSTSICHT), 11.0, gewitter=True)
    gemessen = messe(quelle, T0)
    assert gemessen.is_convective and gemessen.convective_checked, (
        f"Konstruktion: Gewitter mit durchgefuehrter Gewitterpruefung, gemessen "
        f"is_convective={gemessen.is_convective} "
        f"convective_checked={gemessen.convective_checked}"
    )

    for tag in ("a", "b"):
        u = nutzer(f"ac6g-{tag}")
        try:
            trip = baue_trip(u, trip_id, [-60, 300], cooldown_min=SPERRZEIT_LANG_MIN)
            briefing_anker(u, trip, BRIEFING_MM, T0)
            strecke = AlarmPruefstrecke(user_id=u, settings=_settings_all_channels())
            lauf = strecke.lauf(
                at=T0, zweig="radar", trip=trip, radar_service=radar(quelle),
            )
            assert lauf.triggered_count == 1, (
                f"[{tag}] AC-6: ein Gewitter bei Onset 170 durchbricht die "
                f"Briefing-Ankuendigung. triggered_count={lauf.triggered_count}, "
                f"Gruende={gruende_seit(u, trip, T0)!r}"
            )
        finally:
            _clean_user(u)
