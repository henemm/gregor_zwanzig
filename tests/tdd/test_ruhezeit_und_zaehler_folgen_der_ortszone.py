"""TDD RED — #1726: Ruhezeit, Alarm-Tageszähler und Ortsvergleichs-Fälligkeit
folgen der ORTSZONE statt der Wiener Uhr.

Spec: docs/specs/modules/fix_1726_ruhezeit_und_zaehler_ortszone.md (15 ACs)
Kontext: docs/context/fix-1726-ruhezeit-ortszone.md
ADR-0051 (Die Zone gehört an die Daten, nicht an den Server), ADR-0044.

Drei Entscheidungen laufen heute auf `Europe/Vienna`, obwohl sie den Nutzer an
SEINEM Ort betreffen:

* Ruhezeit-Fenster  — `deviation_alert_engine.py:31` (`VIENNA`), wirksam `:112`
* Tageszähler-Reset — `alert_daily_limit.py:23` (`VIENNA`), wirksam `:32`
* Slot-Fälligkeit   — `dispatch_orchestrator.py:128`
  (`NOCH_NICHT_ORTSZEIT_SIEHE_1726`), wirksam `:141`

═══════════════════════════════════════════════════════════════════════════
ZWEI FALLEN, DIE DIESE DATEI BEWUSST VERMEIDET
═══════════════════════════════════════════════════════════════════════════

**1. Die falsche Zone macht den Test blind.** `Europe/Paris` hat denselben
UTC-Versatz wie Wien — ein Test dort kann strukturell nicht unterscheiden, ob
die Zone aus den Daten kam oder still auf Wien zurückfiel (kostete in #1725
eine Adversary-Runde). Alle Ost/West-Nachweise benutzen deshalb
`Pacific/Auckland` (+12) und `America/Los_Angeles` (−7). Die beiden
Sommerzeit-Wechseltage (AC-10) sind EU-Umstellungstage — dort ist
`Europe/Lisbon` die Zone der Wahl: sie schaltet zum selben Zeitpunkt wie Wien
(EU-weit 01:00 UTC), hat aber einen ANDEREN Versatz (+0/+1 statt +1/+2). Ein
stiller Wien-Rückfall fällt damit trotzdem auf.

**2. Ein Test, der aus dem falschen Grund rot ist, beweist nichts.** Nach der
Umstellung bekommen `is_quiet_hours`, `check_nowcast_gate` und
`alert_daily_limit.*` einen Pflicht-Parameter `zone`. Ein Test, der heute nur
mit `TypeError: unexpected keyword argument 'zone'` scheitert, wäre ein
Signatur-Test — er würde auch grün, wenn der Parameter entgegengenommen und
IGNORIERT wird.

Deshalb gilt hier durchgehend:

* Wo möglich läuft der Nachweis über den **echten Dienstpfad** (Trip-Alarm,
  Vergleichs-Alarm, Nowcast-Schranke, Versand-Orchestrator). Deren Signaturen
  ändern sich NICHT — die Tests sind reine Verhaltenstests.
* Wo die neue Signatur unvermeidbar ist (die drei `alert_daily_limit`-
  Funktionen, der Engine-Kern), läuft der Aufruf über :func:`mit_zone`: die
  Zone wird übergeben, sobald der Prüfling sie annimmt, und sonst weggelassen.
  Dadurch ist der Test schon HEUTE mit einem Zählerstand/Unterdrückungs-
  Ergebnis rot, nicht mit einem `TypeError`. Zugleich ist jedes Szenario so
  gewählt, dass ein **entgegengenommener, aber ignorierter** `zone`-Parameter
  den Test WEITERHIN rot lässt. Jeder solche Test sagt das im Docstring.
* Jeder Test trägt im Docstring, WARUM er heute rot ist — „weil die Prüfung
  gegen Wien läuft" ist der gewünschte Grund, „weil das Argument unbekannt
  ist" nicht.

**Gekreuzte Probe.** Viele Dienstpfad-Tests fahren ZWEI Läufe: einmal mit
einem Ruhezeit-Fenster um „jetzt in der Ortszone" und einmal mit einem um
„jetzt in Wien". Nach dem Fix muss sich das Ergebnis GENAU UMKEHREN. Das ist
schärfer als ein einzelner Lauf und schützt gleichzeitig vor falschem Grün:
bricht der Pfad vorzeitig ab (z.B. kein aktives Segment), wären BEIDE Läufe
still — der Kreuz-Assert fällt darauf herein nicht.

Kern-Schicht, deterministisch: kein Netz, keine echten Postfächer, keine
`Mock()`/`patch()`/`MagicMock`. Netz-Nähte werden durch echte Unterklassen mit
echter Implementierung ersetzt (Muster `_OhneNetz` aus
`test_briefing_faelligkeit_ortszone.py`).

Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
"""
from __future__ import annotations

import json
import sys
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from tests.helpers.compare_briefings import write_compare_briefings  # noqa: E402
from tests.helpers.nowcast_gate_fixtures import (  # noqa: E402
    CountingFrameSource,
    clean_uid,
    location,
    make_trip,
    preset_root,
    read_daily_counter,
    reset_radar_cache,
    save_trip,
    seed_daily_counter,
    settings_email_only,
    trip_alert_service,
    trip_stage,
    write_user_tier,
)

# ═════════════════════════ Zonen und Koordinaten ══════════════════════════

VIENNA = ZoneInfo("Europe/Vienna")
AUCKLAND = ZoneInfo("Pacific/Auckland")          # +12/+13 — östlich
LOS_ANGELES = ZoneInfo("America/Los_Angeles")    # −8/−7  — westlich
LISBON = ZoneInfo("Europe/Lisbon")               # +0/+1  — EU-DST, ≠ Wien
UTC = timezone.utc

# Echte Orte, damit TimezoneFinder sie auflöst (offline, kein Netz).
KOORDINATEN = {
    "Pacific/Auckland": (-36.85, 174.76),
    "America/Los_Angeles": (34.05, -118.24),
    "Europe/Lisbon": (38.72, -9.14),
    "Europe/Vienna": (48.21, 16.37),
}

# Ruhezeit über Mitternacht (Wrap) — die Form, die der Nutzer real einstellt.
RUHE_VON, RUHE_BIS = "22:00", "07:00"

# ── Feste Zeitpunkte für die Pfade, die `now` als Parameter annehmen ───────
# 2026-08-12 14:00 UTC: Auckland 02:00 (13.8., IM Fenster) · Wien 16:00
# (ausserhalb) · Los Angeles 07:00 (ausserhalb — 07:00 ist die exklusive
# Obergrenze). GENAU EINE der drei Zonen ist ruhig.
JETZT_AUCKLAND_NACHT = datetime(2026, 8, 12, 14, 0, tzinfo=UTC)
# 2026-08-12 06:30 UTC: Los Angeles 23:30 (11.8., IM Fenster) · Wien 08:30
# (ausserhalb) · Auckland 18:30 (ausserhalb). Spiegelbild des obigen.
JETZT_LA_NACHT = datetime(2026, 8, 12, 6, 30, tzinfo=UTC)


def fenster_um_jetzt(zone: ZoneInfo, puffer_minuten: int = 45) -> tuple[str, str]:
    """Ruhezeit-Fenster, das den JETZIGEN Zeitpunkt in `zone` umschliesst.

    Für die Dienstpfade, die ihre Zeit selbst über `datetime.now(utc)` holen —
    dort lässt sich der Zeitpunkt nicht hereinreichen, wohl aber das Fenster
    um ihn herum legen.

    Warum ±45 Minuten sicher unterscheidbar ist: Auckland/Wien liegen 10–12 h
    auseinander, Los Angeles/Wien 8–10 h, Auckland/Los Angeles 19–21 h. Ein
    90-Minuten-Fenster um die Ortszeit der einen Zone kann die Ortszeit einer
    anderen nie mit enthalten. Mitternachts-Überläufe deckt die Wrap-Logik von
    `is_quiet_hours()` ab.
    """
    jetzt = datetime.now(UTC).astimezone(zone)
    return (
        (jetzt - timedelta(minutes=puffer_minuten)).strftime("%H:%M"),
        (jetzt + timedelta(minutes=puffer_minuten)).strftime("%H:%M"),
    )


def ortstag(zone: ZoneInfo) -> date_type:
    return datetime.now(UTC).astimezone(zone).date()


# ═══════════════════════ Ablage: Orte und Presets ═════════════════════════


def schreibe_ort(user_id: str, loc_id: str, zone_name: str):
    """Echter `SavedLocation` über den Produktiv-Schreiber `save_location()`."""
    from app.loader import save_location

    lat, lon = KOORDINATEN[zone_name]
    loc = location(loc_id, f"Ort {loc_id}", lat=lat, lon=lon)
    save_location(loc, user_id=user_id)
    return loc


# 🔴 KORREKTUR DER RED-PHASE (GREEN, #1726). Hier stand ein Helfer
# `schreibe_ort_ohne_koordinaten()`, der einen Ort auf 0/0 legte und behauptete,
# `tz_for_coords(0, 0)` liefere "UTC" und damit `resolve_location_tz() is None`.
# NACHGEMESSEN mit der installierten `timezonefinder`: sie liefert dort
# `Etc/GMT` — seit Version 6 sind die Ozean-Zonen (`Etc/GMT±X`) in den Daten,
# `timezone_at()` gibt für keinen Punkt der Erde mehr `None` zurück. Der Ort war
# also sehr wohl auflösbar, der Test hätte die Zusicherung nie gemessen (er wäre
# an der Protokoll-Erwartung hängengeblieben, ohne dass am Prüfling etwas fehlt).
#
# Der reale „kein Ort auflösbar"-Fall ist deshalb NICHT die Koordinate, sondern
# die ins Leere zeigende Kennung: ein gelöschter Ort bleibt in `location_ids`
# stehen (genau dafür filtert `compare_official_alert.py:128`). Zeigt die
# EINZIGE Kennung ins Leere, löst kein Ort auf — das ist der Fall, den AC-15
# meint, und er wird unten unverändert scharf geprüft.


def vergleichs_preset(
    preset_id: str,
    location_ids: list[str],
    *,
    quiet_from: str | None = None,
    quiet_to: str | None = None,
    morning_time: str = "07:00:00",
) -> dict:
    """Vergleichs-Preset im Bestandsschema (Feldauswahl analog
    `tests/test_compare_auto_pause_end_date.py::_make_preset`)."""
    preset: dict = {
        "id": preset_id,
        "name": f"Vergleich {preset_id}",
        "user_id": "default",
        "location_ids": location_ids,
        "schedule": "daily",
        "weekday": None,
        "profil": "ALLGEMEIN",
        "hour_from": 9,
        "hour_to": 16,
        "empfaenger": ["dummy@example.invalid"],
        "letzter_versand": None,
        "created_at": "2026-08-01T00:00:00Z",
        "archived_at": None,
        "morning_enabled": True,
        "morning_time": morning_time,
        "evening_enabled": False,
        "evening_time": "18:00:00",
    }
    if quiet_from is not None:
        preset["alert_quiet_from"] = quiet_from
    if quiet_to is not None:
        preset["alert_quiet_to"] = quiet_to
    return preset


def schreibe_presets(user_id: str, presets: list[dict]) -> None:
    write_compare_briefings(preset_root() / user_id, presets)


# ═════════════ Dienstpfade mit ersetzter Netz-Naht (keine Mocks) ══════════


def offizieller_vergleichsdienst(user_id: str):
    """`CompareOfficialAlertService`, bei dem AUSSCHLIESSLICH die Netz-Naht
    `_detect()` durch eine echte, zählende Implementierung ersetzt ist.

    `_detect()` ist die erste Stelle des Pfads, die amtliche Warnungen über das
    Netz holt — und sie liegt HINTER der Ruhezeit-Prüfung
    (`compare_official_alert.py:119`). Die Zählung ist damit der direkte
    Wirkungs-Nachweis: 0 Aufrufe = unterdrückt, ≥1 = durchgelassen.
    """
    from services.compare_official_alert import CompareOfficialAlertService

    class _Zaehlend(CompareOfficialAlertService):
        detect_aufrufe = 0

        def _detect(self, preset_id, locs, sources=None):
            type(self).detect_aufrufe += 1
            return ([], {})

    _Zaehlend.detect_aufrufe = 0
    return _Zaehlend(settings=settings_email_only(), user_id=user_id)


def vergleichs_alarmdienst(user_id: str):
    """`CompareAlertService` mit ersetzter Netz-Naht `_detect_triggered_locations()`
    (liegt hinter der Ruhezeit-Prüfung `compare_alert.py:176`)."""
    from services.compare_alert import CompareAlertService

    class _Zaehlend(CompareAlertService):
        detect_aufrufe = 0

        def _detect_triggered_locations(
            self, preset_id, location_ids, all_locations, config, day_window
        ):
            type(self).detect_aufrufe += 1
            return []

    _Zaehlend.detect_aufrufe = 0
    return _Zaehlend(settings=settings_email_only(), user_id=user_id)


def trip_abweichungsdienst(user_id: str):
    """`TripAlertService` mit ersetzter Netz-Naht `_fetch_fresh_weather()`
    (liegt hinter der Ruhezeit-Prüfung `trip_alert.py:229`)."""
    from services.trip_alert import TripAlertService

    class _Zaehlend(TripAlertService):
        fetch_aufrufe = 0

        def _fetch_fresh_weather(self, cached_weather):
            type(self).fetch_aufrufe += 1
            return []

    _Zaehlend.fetch_aufrufe = 0
    return _Zaehlend(
        settings=settings_email_only(), throttle_hours=2, user_id=user_id,
    )


def trip_mit_ruhezeit(user_id: str, trip_id: str, zone_name: str,
                      quiet: tuple[str, str]):
    """Aktiver Trip in `zone_name` mit gesetzter Ruhezeit, auf Platte."""
    lat, lon = KOORDINATEN[zone_name]
    trip = make_trip(
        trip_id,
        cooldown_minutes=0,
        quiet_from=quiet[0],
        quiet_to=quiet[1],
        stage_date=ortstag(ZoneInfo(zone_name)),
        lat=lat,
        lon=lon,
    )
    trip.report_config.alert_on_changes = True
    save_trip(trip, user_id)
    return trip


def mit_zone(funktion, *args, zone: ZoneInfo):
    """Ruft eine Prüfling-Funktion mit `zone=`, SOBALD sie den Parameter
    annimmt — und ohne ihn, solange sie das nicht tut.

    Ohne diese Fallunterscheidung wäre jeder Zähler-/Ruhezeit-Test HEUTE nur
    mit `TypeError: unexpected keyword argument 'zone'` rot. Das wäre ein
    Signatur-Befund, kein Verhaltensbefund — und er würde bereits grün, wenn
    der Parameter entgegengenommen und ignoriert wird. So misst der Test
    stattdessen schon heute das ERGEBNIS („welcher Zählerstand steht da?",
    „wird unterdrückt?") und bleibt nach der Umstellung wortgleich gültig. Ein
    entgegengenommener, aber ignorierter Parameter fällt weiterhin durch, weil
    jedes Szenario Wiener und Ortszeit auseinanderzieht.

    Die Signatur wird gelesen, nicht geraten — kein `try/except TypeError`, das
    einen echten Programmfehler nach der Umstellung verschlucken könnte.
    """
    import inspect

    if "zone" in inspect.signature(funktion).parameters:
        return funktion(*args, zone=zone)
    return funktion(*args)


def _uid(kennung: str) -> str:
    return f"tdd-1726-{kennung}"


@pytest.fixture
def sauberer_nutzer():
    """Vergibt Nutzer-Kennungen und räumt sie hinterher weg."""
    vergeben: list[str] = []

    def _neu(kennung: str, tier: str = "free") -> str:
        user_id = _uid(kennung)
        clean_uid(user_id)
        write_user_tier(user_id, tier)
        vergeben.append(user_id)
        return user_id

    yield _neu
    for user_id in vergeben:
        clean_uid(user_id)


# ═══════════════════════════════════════════════════════════════════════════
# AC-1 / AC-2 — Ruhezeit östlich und westlich von Wien
# ═══════════════════════════════════════════════════════════════════════════


def _trip_deviation_lauf(user_id: str, zone_name: str, quiet: tuple[str, str]) -> int:
    """Ein echter `check_and_send_alerts()`-Lauf; liefert die Zahl der
    Wetterabrufe (0 = durch die Ruhezeit unterdrückt)."""
    dienst = trip_abweichungsdienst(user_id)
    trip = trip_mit_ruhezeit(user_id, f"{user_id}-trip", zone_name, quiet)
    dienst.check_and_send_alerts(trip, cached_weather=[])
    return type(dienst).fetch_aufrufe


def test_ac1_ruhezeit_oestlich_folgt_der_ortszeit_nicht_wien(sauberer_nutzer):
    """AC-1: Trip mit Wegpunkt in `Pacific/Auckland`, Ruhezeit 22:00–07:00.

    Given ein Alarm-Zeitpunkt, der in Auckland IM Ruhezeit-Fenster liegt, in
    Wien aber tagsüber / Then wird der Alarm unterdrückt (kein Wetterabruf).
    Gekreuzt: ein Fenster um die WIENER Ortszeit darf denselben Trip NICHT
    mehr unterdrücken.

    ROT HEUTE, weil die Prüfung gegen Wien läuft (`deviation_alert_engine.py:112`):
    das Auckland-Fenster greift nicht (Abruf findet statt), das Wien-Fenster
    greift fälschlich (kein Abruf). Beide Erwartungen sind heute exakt
    invertiert — es ist ein Verhaltens-, kein Signaturbefund.
    """
    abrufe_auckland = _trip_deviation_lauf(
        sauberer_nutzer("ac1-ort"), "Pacific/Auckland", fenster_um_jetzt(AUCKLAND)
    )
    abrufe_wien = _trip_deviation_lauf(
        sauberer_nutzer("ac1-wien"), "Pacific/Auckland", fenster_um_jetzt(VIENNA)
    )

    assert abrufe_auckland == 0, (
        "Ruhezeit in Auckland-Ortszeit muss den Abweichungs-Alarm unterdrücken "
        "— vor jedem Wetterabruf."
    )
    assert abrufe_wien >= 1, (
        "Ein Fenster um die WIENER Uhrzeit darf einen Auckland-Trip nicht mehr "
        "stilllegen — sonst hängt die Ruhezeit weiter am Server."
    )


def test_ac2_ruhezeit_westlich_folgt_der_ortszeit_nicht_wien(sauberer_nutzer):
    """AC-2: Spiegelbild mit `America/Los_Angeles`.

    ROT HEUTE aus demselben Grund wie AC-1 — die Prüfung läuft gegen Wien.
    """
    abrufe_la = _trip_deviation_lauf(
        sauberer_nutzer("ac2-ort"), "America/Los_Angeles", fenster_um_jetzt(LOS_ANGELES)
    )
    abrufe_wien = _trip_deviation_lauf(
        sauberer_nutzer("ac2-wien"), "America/Los_Angeles", fenster_um_jetzt(VIENNA)
    )

    assert abrufe_la == 0, (
        "Ruhezeit in Los-Angeles-Ortszeit muss den Abweichungs-Alarm unterdrücken."
    )
    assert abrufe_wien >= 1, (
        "Ein Fenster um die WIENER Uhrzeit darf einen LA-Trip nicht mehr stilllegen."
    )


# ═══════════════════════════════════════════════════════════════════════════
# AC-3 — Alle SIEBEN Ruhezeit-Prüfstellen, je EINZELN nachgewiesen
#
# Geteilter Code bewies in #1697 dreimal in Folge nichts über den jeweiligen
# Aufrufer. Deshalb sieben Tests, keiner erschliesst die anderen mit.
# ═══════════════════════════════════════════════════════════════════════════


def _official_compare_lauf(user_id: str, quiet: tuple[str, str]) -> int:
    schreibe_ort(user_id, "loc-akl", "Pacific/Auckland")
    schreibe_presets(user_id, [
        vergleichs_preset("cp-1", ["loc-akl"], quiet_from=quiet[0], quiet_to=quiet[1])
    ])
    dienst = offizieller_vergleichsdienst(user_id)
    dienst.check_all_compare_presets()
    return type(dienst).detect_aufrufe


def test_ac3_stelle1_amtliche_warnung_vergleich(sauberer_nutzer):
    """AC-3 Stelle 1 — `compare_official_alert.py:119` (amtliche Warnung,
    Ortsvergleich). Zone-Quelle: erster Ort aus `location_ids`.

    ROT HEUTE: die Ruhezeit dieses Vergleichs wird gegen Wien ausgewertet, der
    Ort liegt in Auckland. Nachweis über den echten Dienst
    (`check_all_compare_presets`), gemessen an der Netz-Naht dahinter.
    """
    aufrufe_ort = _official_compare_lauf(
        sauberer_nutzer("ac3s1-ort"), fenster_um_jetzt(AUCKLAND)
    )
    aufrufe_wien = _official_compare_lauf(
        sauberer_nutzer("ac3s1-wien"), fenster_um_jetzt(VIENNA)
    )

    assert aufrufe_ort == 0, "Auckland-Ruhezeit muss die amtliche Vergleichs-Warnung stoppen."
    assert aufrufe_wien >= 1, "Wiener Ruhezeit darf einen Auckland-Vergleich nicht stoppen."


def test_ac3_stelle2_wetterabweichung_trip(sauberer_nutzer):
    """AC-3 Stelle 2 — `trip_alert.py:229` (Wetter-Abweichung, Trip).

    Eigenständiger Nachweis für DIESE Aufrufstelle, obwohl sie sich den
    Adapter mit Stelle 4 teilt (Spec, Entwurf A).

    ROT HEUTE: Prüfung gegen Wien, Trip in Los Angeles.
    """
    abrufe_ort = _trip_deviation_lauf(
        sauberer_nutzer("ac3s2-ort"), "America/Los_Angeles", fenster_um_jetzt(LOS_ANGELES)
    )
    abrufe_wien = _trip_deviation_lauf(
        sauberer_nutzer("ac3s2-wien"), "America/Los_Angeles", fenster_um_jetzt(VIENNA)
    )

    assert abrufe_ort == 0
    assert abrufe_wien >= 1


def test_ac3_stelle3_geteilter_ruhezeit_adapter(sauberer_nutzer):
    """AC-3 Stelle 3 — `trip_alert.py:688` (`_is_quiet_hours`-Adapter selbst).

    Der Adapter nimmt `(trip, now)` entgegen; seine Signatur ändert sich durch
    diese Scheibe NICHT — der Test reicht deshalb einen FESTEN Zeitpunkt herein
    und misst die Antwort. `JETZT_AUCKLAND_NACHT` liegt in Auckland um 02:00
    (im Fenster 22:00–07:00) und in Wien um 16:00 (ausserhalb).

    ROT HEUTE: der Adapter liefert `False`, weil er auf 16:00 Wiener Zeit prüft.
    """
    user_id = sauberer_nutzer("ac3s3")
    dienst = trip_abweichungsdienst(user_id)
    trip = trip_mit_ruhezeit(user_id, "t-adapter", "Pacific/Auckland",
                             (RUHE_VON, RUHE_BIS))

    assert dienst._is_quiet_hours(trip, JETZT_AUCKLAND_NACHT) is True, (
        "02:00 Ortszeit Auckland liegt im Fenster 22:00–07:00 — der geteilte "
        "Adapter muss die Zone des Trips auflösen (anchor_tz), nicht Wien."
    )
    # Gegenprobe in derselben Zone: 16:00 Ortszeit Auckland ist wach.
    wach = JETZT_AUCKLAND_NACHT - timedelta(hours=10)  # Auckland 16:00
    assert dienst._is_quiet_hours(trip, wach) is False, (
        "16:00 Ortszeit Auckland liegt ausserhalb — sonst wäre die Zusicherung "
        "durch ein pauschales True erfüllbar."
    )


def test_ac3_stelle4_amtliche_warnung_trip(sauberer_nutzer):
    """AC-3 Stelle 4 — `trip_alert.py:1443` (amtliche Warnung, Trip;
    `_send_official_alert_only`).

    Diese Methode IST die Aufrufstelle. Der öffentliche Einstieg darüber
    (`check_official_alert_triggers`) holt die Warnungen über das Netz — sie
    werden hier deshalb als echte `OfficialAlert`-Objekte hereingereicht,
    genau wie der Produktivpfad es tut.

    ROT HEUTE: Ruhezeit gegen Wien geprüft, Trip in Auckland → der Versand
    läuft an, der Mail-Sink füllt sich.
    """
    from services.official_alerts.models import OfficialAlert

    def lauf(quiet: tuple[str, str], kennung: str) -> int:
        user_id = sauberer_nutzer(kennung)
        gesendet: list = []
        from services.trip_alert import TripAlertService

        dienst = TripAlertService(
            settings=settings_email_only(), throttle_hours=2, user_id=user_id,
            mail_sink=lambda *a, **kw: gesendet.append((a, kw)),
        )
        trip = trip_mit_ruhezeit(user_id, "t-amtlich", "Pacific/Auckland", quiet)
        warnung = OfficialAlert(
            source="test-quelle", hazard="wind", level=3,
            label="Sturmwarnung", region_label="Testregion",
        )
        # Segment-Kennungen sind numerische Strings (`format_segment_reference`).
        dienst._send_official_alert_only(trip, [(warnung, ["1"])])
        return len(gesendet)

    versand_ort = lauf(fenster_um_jetzt(AUCKLAND), "ac3s4-ort")
    versand_wien = lauf(fenster_um_jetzt(VIENNA), "ac3s4-wien")

    assert versand_ort == 0, (
        "Auckland-Ruhezeit muss die amtliche Trip-Warnung unterdrücken."
    )
    assert versand_wien >= 1, (
        "Wiener Ruhezeit darf die amtliche Warnung eines Auckland-Trips nicht "
        "unterdrücken."
    )


def test_ac3_stelle5_nowcast_schranke(sauberer_nutzer):
    """AC-3 Stelle 5 — `alert_gate.py:93` (Nowcast-Schranke, geteilt
    Trip+Vergleich). Kein Objekt im Scope: die Zone muss von den beiden
    Aufrufern durchgereicht werden.

    Nachweis über den echten Trip-Radar-Pfad (`check_radar_alerts`), gemessen
    an der Radar-Naht `CountingFrameSource` — sie liegt HINTER der Schranke, ein
    gesperrter Lauf kostet keinen Abruf (Modul-Docstring `alert_gate.py`).

    Der Test ruft `check_nowcast_gate()` bewusst NICHT direkt auf: das wäre ein
    Signatur-Test, der auch bei entgegengenommenem, aber ignoriertem `zone`
    grün würde.

    ROT HEUTE: die Schranke wertet die Ruhezeit gegen Wien aus.
    """
    def lauf(quiet: tuple[str, str], kennung: str) -> int:
        user_id = sauberer_nutzer(kennung)
        reset_radar_cache()
        lat, lon = KOORDINATEN["Pacific/Auckland"]
        trip = make_trip(
            "t-radar", cooldown_minutes=0, quiet_from=quiet[0], quiet_to=quiet[1],
            stage_date=ortstag(AUCKLAND), lat=lat, lon=lon,
        )
        save_trip(trip, user_id)
        quelle = CountingFrameSource()
        dienst = trip_alert_service(
            user_id, settings_email_only(), quelle, mail_sink=lambda *a, **kw: None,
        )
        dienst.check_radar_alerts()
        return quelle.call_count

    abrufe_ort = lauf(fenster_um_jetzt(AUCKLAND), "ac3s5-ort")
    abrufe_wien = lauf(fenster_um_jetzt(VIENNA), "ac3s5-wien")

    assert abrufe_ort == 0, (
        "Die Nowcast-Schranke muss die Auckland-Ruhezeit sehen — vor dem Abruf."
    )
    assert abrufe_wien >= 1, (
        "Ohne diesen Gegen-Lauf wäre die erste Zusicherung auch dann erfüllt, "
        "wenn der Radar-Pfad aus einem ganz anderen Grund gar nicht erst "
        "losläuft (z.B. kein aktives Segment)."
    )


def _compare_deviation_lauf(user_id: str, quiet: tuple[str, str]) -> int:
    schreibe_ort(user_id, "loc-akl", "Pacific/Auckland")
    schreibe_presets(user_id, [
        vergleichs_preset("cp-dev", ["loc-akl"], quiet_from=quiet[0], quiet_to=quiet[1])
    ])
    dienst = vergleichs_alarmdienst(user_id)
    dienst.check_all_compare_presets()
    return type(dienst).detect_aufrufe


def test_ac3_stelle6_wetterabweichung_vergleich(sauberer_nutzer):
    """AC-3 Stelle 6 — `compare_alert.py:176` (Wetter-Abweichung, Vergleich).
    Zone-Quelle: `config.zone`, gesetzt in `_build_eval_config()` aus dem
    ersten Ort.

    ROT HEUTE: Prüfung gegen Wien, Ort in Auckland → der Wetterabruf läuft an.
    """
    aufrufe_ort = _compare_deviation_lauf(
        sauberer_nutzer("ac3s6-ort"), fenster_um_jetzt(AUCKLAND)
    )
    aufrufe_wien = _compare_deviation_lauf(
        sauberer_nutzer("ac3s6-wien"), fenster_um_jetzt(VIENNA)
    )

    assert aufrufe_ort == 0, "Auckland-Ruhezeit muss VOR dem Wetterabruf greifen."
    assert aufrufe_wien >= 1, "Wiener Ruhezeit darf einen Auckland-Vergleich nicht stoppen."


def _eval_config(dienst, preset: dict, all_locations: dict):
    """Baut die `AlertEvaluationConfig` über den PRODUKTIVEN Erbauer
    (`CompareAlertService._build_eval_config`) — nicht von Hand im Test.

    Nur so misst der Test, was der Produktivpfad tatsächlich in die Engine
    hineingibt. Ob der Erbauer die Ortsliste künftig als zusätzlichen
    Parameter braucht, entscheidet die GREEN-Phase; der Test liest das an der
    echten Signatur ab, statt es festzunageln.
    """
    import inspect

    signatur = inspect.signature(dienst._build_eval_config)
    extra = {}
    if "all_locations" in signatur.parameters:
        extra["all_locations"] = all_locations
    return dienst._build_eval_config(preset, 0, **extra)


def test_ac3_stelle7_engine_kern(sauberer_nutzer):
    """AC-3 Stelle 7 — `deviation_alert_engine.py:286` (`evaluate()`, der Kern).
    Zone-Quelle: `config.zone` (Rückfall UTC).

    Die Konfiguration entsteht über den PRODUKTIVEN Erbauer, der Zeitpunkt wird
    hereingereicht (`now=`, bestehender Parameter). Gemessen wird das
    Auswertungs-ERGEBNIS, nicht die Argumentliste.

    ROT HEUTE: `config` trägt keine Zone, die Engine rechnet in Wien (16:00,
    wach) statt in Auckland (02:00, Ruhezeit) — `suppressed_reason` ist
    `"no_significant_changes"` statt `"quiet_hours"`.

    Ein entgegengenommener, aber IGNORIERTER `zone`-Parameter liefert dasselbe
    falsche Ergebnis — dieser Test lässt sich damit nicht befriedigen.
    """
    from services.deviation_alert_engine import DeviationAlertEngine

    user_id = sauberer_nutzer("ac3s7")
    loc = schreibe_ort(user_id, "loc-akl", "Pacific/Auckland")
    preset = vergleichs_preset("cp-kern", ["loc-akl"],
                               quiet_from=RUHE_VON, quiet_to=RUHE_BIS)
    schreibe_presets(user_id, [preset])

    dienst = vergleichs_alarmdienst(user_id)
    config = _eval_config(dienst, preset, {"loc-akl": loc})

    ergebnis = DeviationAlertEngine().evaluate(
        cached=[], fresh=[], config=config, alert_state={},
        now=JETZT_AUCKLAND_NACHT,
    )

    assert ergebnis.triggered is False
    assert ergebnis.suppressed_reason == "quiet_hours", (
        "Der Engine-Kern muss die Zone aus der Konfiguration nehmen — 02:00 "
        "Ortszeit Auckland liegt im Fenster 22:00–07:00. Heute rechnet er in "
        f"Wien (16:00) und meldet {ergebnis.suppressed_reason!r}."
    )


# ═══════════════════════════════════════════════════════════════════════════
# AC-4 — Mehrzonen-Vergleich: Ruhezeit folgt dem ERSTEN Ort
# ═══════════════════════════════════════════════════════════════════════════


def test_ac4_ruhezeit_folgt_dem_ersten_ort_und_wandert_mit_der_reihenfolge(
    sauberer_nutzer,
):
    """AC-4: Zwei Orte, zwei Zonen — massgeblich ist der ERSTGENANNTE.

    Given ein Vergleich [Auckland, Los Angeles] mit einem Ruhezeit-Fenster um
    die Auckland-Ortszeit / Then ist er ruhig. When derselbe Vergleich als
    [Los Angeles, Auckland] konfiguriert wird / Then ist er NICHT mehr ruhig —
    das Ergebnis kippt mit der Reihenfolge.

    ROT HEUTE: beide Reihenfolgen werden gegen Wien geprüft, das Ergebnis ist
    in beiden Fällen dasselbe (nicht ruhig) — die Reihenfolge hat gar keine
    Wirkung. Der Kipp-Nachweis schlägt fehl.

    Eine feste oder alphabetische Ortsauswahl (statt `location_ids[0]`) fällt
    hier ebenfalls durch: „Auckland" käme alphabetisch immer zuerst und das
    Ergebnis kippte nicht.
    """
    fenster = fenster_um_jetzt(AUCKLAND)

    def lauf(reihenfolge: list[str], kennung: str) -> int:
        user_id = sauberer_nutzer(kennung)
        schreibe_ort(user_id, "loc-akl", "Pacific/Auckland")
        schreibe_ort(user_id, "loc-lax", "America/Los_Angeles")
        schreibe_presets(user_id, [
            vergleichs_preset("cp-multi", reihenfolge,
                              quiet_from=fenster[0], quiet_to=fenster[1])
        ])
        dienst = vergleichs_alarmdienst(user_id)
        dienst.check_all_compare_presets()
        return type(dienst).detect_aufrufe

    auckland_zuerst = lauf(["loc-akl", "loc-lax"], "ac4-akl-first")
    la_zuerst = lauf(["loc-lax", "loc-akl"], "ac4-lax-first")

    assert auckland_zuerst == 0, (
        "Erster Ort Auckland → die Auckland-Ruhezeit gilt für den Vergleich."
    )
    assert la_zuerst >= 1, (
        "Rückt Los Angeles an die erste Stelle, gilt dessen Ortszeit — dasselbe "
        "Fenster liegt dort nicht in der Nacht, der Vergleich läuft weiter."
    )


# ═══════════════════════════════════════════════════════════════════════════
# AC-5 — #1479 bleibt gewahrt (grüner Regressions-Anker)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "kaputt",
    [("25:00", "07:00"), ("abc", "07:00"), ("22:00", "xx:yy")],
    ids=["stunde-25", "kein-zeitformat", "kaputtes-ende"],
)
def test_ac5_unbrauchbarer_ruhezeitwert_bleibt_keine_ruhezeit(sauberer_nutzer, kaputt):
    """AC-5 (grüner Regressions-Anker, KEIN RED-Fall): ein unbrauchbarer
    Ruhezeit-Wert gilt weiterhin als „keine Ruhezeit gesetzt" — auch mit dem
    zusätzlichen Zonen-Parameter.

    Dieser Test ist HEUTE grün und muss es bleiben. Er bewacht die Zusicherung
    aus #1479 gegen die naheliegende Regression, die Zonen-Auflösung ausserhalb
    (oder anstelle) des bestehenden `try/except` zu platzieren
    (`deviation_alert_engine.py:109-139`).
    """
    user_id = sauberer_nutzer(f"ac5-{kaputt[0]}-{kaputt[1]}".replace(":", ""))
    dienst = trip_abweichungsdienst(user_id)
    trip = trip_mit_ruhezeit(user_id, "t-kaputt", "Pacific/Auckland", kaputt)

    assert dienst._is_quiet_hours(trip, JETZT_AUCKLAND_NACHT) is False


def test_ac5_nicht_string_ruhezeitwert_bleibt_keine_ruhezeit(sauberer_nutzer):
    """AC-5, zweiter Teil (grüner Anker): ein Nicht-String (`int`) darf keine
    Ausnahme an den Aufrufer durchreichen — der gefährlichste Fehlerfall wäre
    ein Alarm-Totalausfall für ALLE Touren des Kontos (#1467)."""
    user_id = sauberer_nutzer("ac5-nichtstring")
    dienst = trip_abweichungsdienst(user_id)
    trip = trip_mit_ruhezeit(user_id, "t-int", "Pacific/Auckland", ("22:00", "07:00"))
    trip.alert_quiet_from = 2200  # kein String — kommt so aus einer Nutzerdatei

    assert dienst._is_quiet_hours(trip, JETZT_AUCKLAND_NACHT) is False


# ═══════════════════════════════════════════════════════════════════════════
# AC-6 — Tageszähler resettet zur ORTS-Mitternacht
#
# Die drei Modulfunktionen bekommen den Zonen-Parameter zwangsläufig. Die
# Szenarien sind deshalb so gewählt, dass ein entgegengenommener, aber
# IGNORIERTER `zone`-Parameter sie WEITERHIN rot lässt: gemessen wird immer
# ein Zählerstand, der sich zwischen Wiener und Ortstag unterscheidet.
# ═══════════════════════════════════════════════════════════════════════════

# Auckland-Mitternacht (NZST, +12) = 12:00 UTC. Wien bleibt über beide
# Zeitpunkte im selben Kalendertag (13:30 / 14:30 MESZ).
VOR_AUCKLAND_MITTERNACHT = datetime(2026, 8, 12, 11, 30, tzinfo=UTC)
NACH_AUCKLAND_MITTERNACHT = datetime(2026, 8, 12, 12, 30, tzinfo=UTC)
# Wiener Mitternacht (MESZ, +2) = 22:00 UTC des Vortags. Auckland bleibt über
# beide Zeitpunkte im selben Kalendertag (09:30 / 10:30 des 13.8.).
VOR_WIENER_MITTERNACHT = datetime(2026, 8, 12, 21, 30, tzinfo=UTC)
NACH_WIENER_MITTERNACHT = datetime(2026, 8, 12, 22, 30, tzinfo=UTC)
# Los-Angeles-Mitternacht (PDT, −7) = 07:00 UTC. Wien bleibt im selben Tag.
VOR_LA_MITTERNACHT = datetime(2026, 8, 12, 6, 30, tzinfo=UTC)
NACH_LA_MITTERNACHT = datetime(2026, 8, 12, 7, 30, tzinfo=UTC)


def test_ac6_zaehler_resettet_an_auckland_mitternacht(sauberer_nutzer):
    """AC-6 (östlich): Der Zähler springt an der AUCKLAND-Mitternacht auf 0.

    Given ein Alarm um 23:30 Auckland-Ortszeit (= 11:30 UTC) / When um 00:30
    Auckland-Ortszeit (= 12:30 UTC) gelesen wird / Then steht der Zähler auf 0.
    In Wien ist zwischen beiden Zeitpunkten NICHTS passiert (13:30 → 14:30,
    derselbe Tag).

    ROT HEUTE: der Reset hängt an `_vienna_date_str` — der Wiener Tag hat nicht
    gewechselt, also liefert `load()` weiterhin 1.
    """
    from services import alert_daily_limit

    user_id = sauberer_nutzer("ac6-akl-reset")
    mit_zone(
        alert_daily_limit.increment, user_id, VOR_AUCKLAND_MITTERNACHT, zone=AUCKLAND,
    )

    assert mit_zone(
        alert_daily_limit.load, user_id, VOR_AUCKLAND_MITTERNACHT, zone=AUCKLAND,
    ) == 1, "Vor der Orts-Mitternacht muss die Buchung sichtbar sein."
    assert mit_zone(
        alert_daily_limit.load, user_id, NACH_AUCKLAND_MITTERNACHT, zone=AUCKLAND,
    ) == 0, (
        "Nach der Auckland-Mitternacht beginnt der Ortstag neu — heute läuft "
        "der Reset noch auf der Wiener Uhr und der Zähler bleibt bei 1."
    )


def test_ac6_zaehler_resettet_nicht_an_wiener_mitternacht(sauberer_nutzer):
    """AC-6 (östlich, Gegenrichtung): Die WIENER Mitternacht darf einen
    Auckland-Zähler NICHT zurücksetzen.

    Given ein Alarm um 09:30 Auckland-Ortszeit (= 21:30 UTC) / When um 10:30
    Auckland-Ortszeit (= 22:30 UTC) gelesen wird — in Wien ist inzwischen
    Mitternacht vorbei / Then steht der Zähler unverändert auf 1.

    ROT HEUTE: der Wiener Tageswechsel setzt ihn auf 0 — ein Kontingent-Leck
    mitten am Ortstag.
    """
    from services import alert_daily_limit

    user_id = sauberer_nutzer("ac6-akl-kein-reset")
    mit_zone(
        alert_daily_limit.increment, user_id, VOR_WIENER_MITTERNACHT, zone=AUCKLAND,
    )

    assert mit_zone(
        alert_daily_limit.load, user_id, NACH_WIENER_MITTERNACHT, zone=AUCKLAND,
    ) == 1, (
        "Derselbe Auckland-Ortstag — der Zähler darf nicht mitten am Tag "
        "aufgefüllt werden, nur weil in Wien ein neuer Tag begonnen hat."
    )


def test_ac6_zaehler_resettet_an_los_angeles_mitternacht(sauberer_nutzer):
    """AC-6 (westlich): Spiegelbild zu Auckland.

    Alarm um 23:30 LA-Ortszeit (= 06:30 UTC), Lesung um 00:30 LA-Ortszeit
    (= 07:30 UTC). In Wien: 08:30 → 09:30, derselbe Tag.

    ROT HEUTE: kein Wiener Tageswechsel → `load()` liefert weiterhin 1.
    """
    from services import alert_daily_limit

    user_id = sauberer_nutzer("ac6-lax-reset")
    mit_zone(
        alert_daily_limit.increment, user_id, VOR_LA_MITTERNACHT, zone=LOS_ANGELES,
    )

    assert mit_zone(
        alert_daily_limit.load, user_id, VOR_LA_MITTERNACHT, zone=LOS_ANGELES,
    ) == 1
    assert mit_zone(
        alert_daily_limit.load, user_id, NACH_LA_MITTERNACHT, zone=LOS_ANGELES,
    ) == 0, (
        "Nach der Los-Angeles-Mitternacht beginnt der Ortstag neu."
    )


def test_ac6_zaehler_resettet_nicht_an_wiener_mitternacht_westlich(sauberer_nutzer):
    """AC-6 (westlich, Gegenrichtung): Die Wiener Mitternacht (22:00 UTC) fällt
    für Los Angeles mitten in den Nachmittag (15:00 Ortszeit) — der Zähler
    bleibt stehen.

    ROT HEUTE: der Wiener Tageswechsel setzt ihn auf 0.
    """
    from services import alert_daily_limit

    user_id = sauberer_nutzer("ac6-lax-kein-reset")
    mit_zone(
        alert_daily_limit.increment, user_id, VOR_WIENER_MITTERNACHT, zone=LOS_ANGELES,
    )

    assert mit_zone(
        alert_daily_limit.load, user_id, NACH_WIENER_MITTERNACHT, zone=LOS_ANGELES,
    ) == 1, (
        "In Los Angeles ist es 15:00 desselben Ortstags — der Zähler darf durch "
        "die Wiener Mitternacht nicht aufgefüllt werden."
    )


# ═══════════════════════════════════════════════════════════════════════════
# AC-7 — Getrennte Zähler pro Zone, BEIDE Richtungen
# ═══════════════════════════════════════════════════════════════════════════


def test_ac7_ausgeschoepfte_zone_blockiert_die_andere_nicht(sauberer_nutzer):
    """AC-7 (Richtung 1): Ein in Zone A ausgeschöpftes Kontingent blockiert
    Zone B nicht.

    Given ein Free-Nutzer (Limit 2), dessen Auckland-Kontingent voll ist / When
    ein Alarm für ein Objekt in Los Angeles anstünde / Then ist er erlaubt.

    ROT HEUTE: es gibt genau EINEN Zähler ohne Zonen-Unterscheidung — nach zwei
    Buchungen ist ALLES gesperrt. Ein ignorierter `zone`-Parameter ändert daran
    nichts, dieser Test bliebe rot.
    """
    from services import alert_daily_limit

    user_id = sauberer_nutzer("ac7-richtung1")
    jetzt = JETZT_AUCKLAND_NACHT
    mit_zone(
        alert_daily_limit.increment, user_id, jetzt, zone=AUCKLAND,
    )
    mit_zone(
        alert_daily_limit.increment, user_id, jetzt, zone=AUCKLAND,
    )

    assert mit_zone(
        alert_daily_limit.is_allowed, user_id, jetzt, zone=AUCKLAND,
    ) is False, (
        "Zwei Buchungen = Free-Limit erreicht (Vorbedingung des Tests)."
    )
    assert mit_zone(
        alert_daily_limit.is_allowed, user_id, jetzt, zone=LOS_ANGELES,
    ) is True, (
        "Das Kontingent wird je Zone geführt — der bewusste Preis dieser "
        "Lösung (wer Objekte in drei Zonen hat, bekommt es dreimal) ist Teil "
        "der Zusicherung, kein Nebenprodukt."
    )


def test_ac7_alarm_in_einer_zone_verbraucht_die_andere_nicht(sauberer_nutzer):
    """AC-7 (Richtung 2): Ein Alarm in Zone A verbraucht NICHTS von Zone B.

    ROT HEUTE: ein gemeinsamer Zähler ohne Zonen-Diskriminator — jede Buchung
    schlägt überall durch.
    """
    from services import alert_daily_limit

    user_id = sauberer_nutzer("ac7-richtung2")
    jetzt = JETZT_AUCKLAND_NACHT
    mit_zone(
        alert_daily_limit.increment, user_id, jetzt, zone=AUCKLAND,
    )

    assert mit_zone(
        alert_daily_limit.load, user_id, jetzt, zone=AUCKLAND,
    ) == 1
    assert mit_zone(
        alert_daily_limit.load, user_id, jetzt, zone=LOS_ANGELES,
    ) == 0, (
        "Der Zählerstand von Los Angeles darf durch eine Auckland-Buchung "
        "nicht steigen."
    )


# ═══════════════════════════════════════════════════════════════════════════
# AC-8 — Bestandsdaten überleben den Rollout
# ═══════════════════════════════════════════════════════════════════════════


def _schreibe_alt_schema(user_id: str, tag: date_type, count: int) -> Path:
    """Zähler-Datei im ALTEN Schema `{"date": ..., "count": N}` — genau so,
    wie sie heute auf der Produktions-Platte liegt."""
    from app.loader import get_data_dir

    ordner = get_data_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    pfad = ordner / "alert_daily_count.json"
    pfad.write_text(json.dumps({"date": tag.isoformat(), "count": count}))
    return pfad


def test_ac8_bestandszaehler_bleibt_beim_ersten_zugriff_erhalten(sauberer_nutzer):
    """AC-8: Ein Deploy mitten am Tag darf kein Kontingent-Leck erzeugen.

    Given ein Zähler im ALTEN Schema mit Stand 2 für den heutigen Wiener Tag /
    When der neue Code ihn zum ersten Mal für `Europe/Vienna` liest und erhöht /
    Then bleibt der Bestand erhalten (2 → 3), er wird nicht auf 0 gesetzt.

    GRÜN HEUTE — und das ist Absicht: dieser Teil von AC-8 sichert eine
    Eigenschaft, die der Altcode bereits hat, und die beim Schema-Wechsel
    verloren gehen würde (Migration per Replace statt Merge). Er ist der
    Regressions-Anker, nicht der RED-Fall. Von einem entgegengenommenen, aber
    ignorierten `zone`-Parameter wäre er ebenfalls erfüllt — den scharfen Teil
    trägt `test_ac8_migration_faellt_nur_der_wiener_zone_zu`.
    """
    from services import alert_daily_limit

    user_id = sauberer_nutzer("ac8-bestand")
    jetzt = JETZT_AUCKLAND_NACHT
    _schreibe_alt_schema(user_id, jetzt.astimezone(VIENNA).date(), 2)

    assert mit_zone(
        alert_daily_limit.load, user_id, jetzt, zone=VIENNA,
    ) == 2, (
        "Der Altbestand wurde nach Wiener Kalendertag geführt — für diese Zone "
        "ist er die korrekte Fortsetzung."
    )
    mit_zone(
        alert_daily_limit.increment, user_id, jetzt, zone=VIENNA,
    )
    assert mit_zone(
        alert_daily_limit.load, user_id, jetzt, zone=VIENNA,
    ) == 3


def test_ac8_migration_faellt_nur_der_wiener_zone_zu(sauberer_nutzer):
    """AC-8 (Schärfung): Der Altbestand gilt NUR für `Europe/Vienna`; jede
    andere Zone beginnt bei 0, und eine Buchung dort lässt den Wiener Stand
    unangetastet (Merge auf ZONEN-Ebene, nicht nur auf Datei-Ebene).

    ROT HEUTE — und auch mit einem ignorierten `zone`-Parameter: dort läge der
    Auckland-Stand bei 2 statt 0 und stiege gemeinsam mit dem Wiener.
    """
    from services import alert_daily_limit

    user_id = sauberer_nutzer("ac8-merge")
    jetzt = JETZT_AUCKLAND_NACHT
    _schreibe_alt_schema(user_id, jetzt.astimezone(VIENNA).date(), 2)

    assert mit_zone(
        alert_daily_limit.load, user_id, jetzt, zone=AUCKLAND,
    ) == 0, (
        "Für Auckland ist der Wiener Altbestand keine sinnvolle Fortsetzung."
    )
    mit_zone(
        alert_daily_limit.increment, user_id, jetzt, zone=AUCKLAND,
    )

    assert mit_zone(
        alert_daily_limit.load, user_id, jetzt, zone=AUCKLAND,
    ) == 1
    assert mit_zone(
        alert_daily_limit.load, user_id, jetzt, zone=VIENNA,
    ) == 2, (
        "Die Auckland-Buchung darf den migrierten Wiener Eintrag nicht "
        "überschreiben (Read-Modify-Write mit Merge, niemals Replace)."
    )


# ═══════════════════════════════════════════════════════════════════════════
# AC-9 — Ortsvergleichs-Slot-Fälligkeit folgt der Zone des ersten Orts
# ═══════════════════════════════════════════════════════════════════════════

# 2026-08-12 19:30 UTC → Auckland 07:30 (13.8.) · Wien 21:30 · LA 12:30
FAELLIG_IN_AUCKLAND = datetime(2026, 8, 12, 19, 30, tzinfo=UTC)
# 2026-08-12 14:30 UTC → Los Angeles 07:30 · Wien 16:30 · Auckland 02:30
FAELLIG_IN_LOS_ANGELES = datetime(2026, 8, 12, 14, 30, tzinfo=UTC)


def _faellige_presets(user_id: str, now_utc: datetime) -> set[str]:
    """Fällige Preset-Kennungen über den ECHTEN Versand-Orchestrator.

    `CompareDispatchStrategy.collect_due(now_utc)` nimmt schon heute einen
    ZEITPUNKT — die Signatur ändert sich durch diese Scheibe nicht. Der Test
    ist damit ein reiner Verhaltenstest.
    """
    from app.loader import get_data_root
    from services.dispatch_orchestrator import CompareDispatchStrategy

    strategie = CompareDispatchStrategy(
        settings_email_only(), user_id, data_root=str(get_data_root()),
    )
    return {eintrag[0].get("id") for eintrag in strategie.collect_due(now_utc)}


def _zwei_presets_in_zwei_zonen(user_id: str) -> None:
    schreibe_ort(user_id, "loc-akl", "Pacific/Auckland")
    schreibe_ort(user_id, "loc-lax", "America/Los_Angeles")
    schreibe_presets(user_id, [
        vergleichs_preset("cp-akl", ["loc-akl"], morning_time="07:00:00"),
        vergleichs_preset("cp-lax", ["loc-lax"], morning_time="07:00:00"),
    ])


def test_ac9_preset_ist_zur_eigenen_ortsstunde_faellig(sauberer_nutzer):
    """AC-9: Ein Preset mit Morgen-Slot 07:00 und Orten in Auckland ist fällig,
    wenn es DORT 07:00 ist — nicht, wenn es in Wien 07:00 ist.

    ROT HEUTE: `collect_due()` bildet EINEN `vor_ort`-Zeitpunkt aus der festen
    Konstante `NOCH_NICHT_ORTSZEIT_SIEHE_1726` und prüft alle Presets gegen
    dieselbe Stunde. Um 19:30 UTC ist es in Wien 21:30 — nichts ist fällig.
    """
    user_id = sauberer_nutzer("ac9-akl")
    _zwei_presets_in_zwei_zonen(user_id)

    assert _faellige_presets(user_id, FAELLIG_IN_AUCKLAND) == {"cp-akl"}, (
        "Um 07:30 Auckland-Ortszeit ist genau das Auckland-Preset fällig — das "
        "Los-Angeles-Preset (dort 12:30) nicht."
    )


def test_ac9_zwei_presets_sind_zu_verschiedenen_weltzeiten_faellig(sauberer_nutzer):
    """AC-9 (Gegenstück): Dasselbe Konto, dieselbe Slot-Uhrzeit, aber erste
    Orte in verschiedenen Zonen → verschiedene Weltzeit-Momente.

    ROT HEUTE: beide Läufe liefern die leere Menge, weil beide gegen die Wiener
    Stunde geprüft werden (21:30 bzw. 16:30).
    """
    user_id = sauberer_nutzer("ac9-lax")
    _zwei_presets_in_zwei_zonen(user_id)

    assert _faellige_presets(user_id, FAELLIG_IN_LOS_ANGELES) == {"cp-lax"}, (
        "Um 07:30 Los-Angeles-Ortszeit ist genau das LA-Preset fällig."
    )


def test_ac9_wiener_slotstunde_macht_fremde_presets_nicht_faellig(sauberer_nutzer):
    """AC-9 (Kontrolle): Wenn es in WIEN 07:00 ist, darf kein Preset fällig
    sein, dessen erster Ort anderswo liegt.

    ROT HEUTE genau umgekehrt: um 05:30 UTC ist es in Wien 07:30 und BEIDE
    Presets gelten als fällig, obwohl es in Auckland 17:30 und in Los Angeles
    22:30 ist.
    """
    user_id = sauberer_nutzer("ac9-wien")
    _zwei_presets_in_zwei_zonen(user_id)
    wien_0730 = datetime(2026, 8, 12, 5, 30, tzinfo=UTC)

    assert _faellige_presets(user_id, wien_0730) == set(), (
        "Die Wiener Uhr entscheidet über gar nichts mehr."
    )


# ═══════════════════════════════════════════════════════════════════════════
# AC-10 — Beide Sommerzeit-Wechseltage, Häufigkeit JEDER EINZELNEN Stunde
#
# Die beiden von der Spec vorgegebenen Daten sind EU-Umstellungstage. Wien ist
# als Prüfzone unbrauchbar (ein Rückfall wäre unsichtbar), Paris ebenso
# (gleicher Versatz). `Europe/Lisbon` schaltet zum selben Zeitpunkt, hat aber
# +0/+1 statt +1/+2 — ein Wien-Rückfall verschiebt jede Grenzstunde um eine
# Stunde und fällt auf.
# ═══════════════════════════════════════════════════════════════════════════

FRUEHJAHR = date_type(2026, 3, 29)   # 23 Ortsstunden, Stunde 01 fehlt (Lissabon)
HERBST = date_type(2026, 10, 25)     # 25 Ortsstunden, Stunde 01 zweimal (Lissabon)


def _stundenraster(tag: date_type, zone: ZoneInfo) -> list[datetime]:
    """Alle vollen Ortsstunden des Kalendertags `tag` in `zone`, als
    UTC-Zeitpunkte — gerechnet, nicht getippt.

    Es wird von 24 Stunden VOR bis 24 Stunden NACH dem Tag in UTC-Schritten
    gelaufen und behalten, was in der Ortszone auf diesem Kalendertag zur
    vollen Stunde liegt. Ein Tag mit 23 bzw. 25 Ortsstunden entsteht dadurch
    von selbst — die Zahl wird nirgends angenommen.
    """
    start = datetime.combine(tag, datetime.min.time(), tzinfo=UTC) - timedelta(days=1)
    raster: list[datetime] = []
    for i in range(24 * 3):
        moment = start + timedelta(hours=i)
        lokal = moment.astimezone(zone)
        if lokal.date() == tag and lokal.minute == 0:
            raster.append(moment)
    return raster


def test_ac10_fruehjahrs_umstellungstag_hat_23_ortsstunden():
    """AC-10 (Vorbedingung, grüner Anker): Der 29.03.2026 hat in
    `Europe/Lisbon` 23 Ortsstunden, Stunde 01 existiert nicht.

    Kein Prüfling-Test — er sichert nur ab, dass die folgenden Tests am
    richtigen Tag messen. Fiele er, wären die AC-10-Aussagen bedeutungslos.
    """
    stunden = [m.astimezone(LISBON).hour for m in _stundenraster(FRUEHJAHR, LISBON)]

    assert len(stunden) == 23
    assert stunden.count(1) == 0, "Die übersprungene Stunde ist 01 (WET→WEST)."
    assert all(stunden.count(h) == 1 for h in stunden)


def test_ac10_herbst_umstellungstag_hat_25_ortsstunden():
    """AC-10 (Vorbedingung, grüner Anker): Der 25.10.2026 hat in
    `Europe/Lisbon` 25 Ortsstunden, Stunde 01 existiert zweimal."""
    stunden = [m.astimezone(LISBON).hour for m in _stundenraster(HERBST, LISBON)]

    assert len(stunden) == 25
    assert stunden.count(1) == 2, "Die doppelte Stunde ist 01 (WEST→WET)."


@pytest.mark.parametrize("tag", [FRUEHJAHR, HERBST], ids=["fruehjahr", "herbst"])
def test_ac10_ruhezeit_stimmt_an_jeder_einzelnen_stunde_des_umstellungstags(tag):
    """AC-10: Ruhezeit-Wrap 22:00–07:00, Stunde für Stunde über den ganzen
    Umstellungstag geprüft — nicht die Zeilenzahl, sondern JEDE Stunde.

    ROT HEUTE: `is_quiet_hours` rechnet in Wien. Lissabon liegt eine Stunde
    dahinter, also weicht das Ergebnis an jeder Grenzstunde ab (z.B. 21:00
    Lissabon = 22:00 Wien: heute unterdrückt, richtig wäre wach).
    """
    from services.deviation_alert_engine import DeviationAlertEngine

    abweichungen: list[tuple[str, int, bool, bool]] = []
    for moment in _stundenraster(tag, LISBON):
        lokale_stunde = moment.astimezone(LISBON).hour
        erwartet = lokale_stunde >= 22 or lokale_stunde < 7
        gemessen = mit_zone(
            DeviationAlertEngine.is_quiet_hours,
            moment, RUHE_VON, RUHE_BIS, zone=LISBON,
        )
        if gemessen is not erwartet:
            abweichungen.append(
                (moment.isoformat(), lokale_stunde, erwartet, gemessen)
            )

    assert not abweichungen, (
        f"Ruhezeit weicht am {tag} an diesen Ortsstunden ab "
        f"(Zeitpunkt, Ortsstunde, erwartet, gemessen): {abweichungen}"
    )


@pytest.mark.parametrize("tag", [FRUEHJAHR, HERBST], ids=["fruehjahr", "herbst"])
def test_ac10_zaehler_haelt_ueber_den_ganzen_umstellungstag(sauberer_nutzer, tag):
    """AC-10: Der Tageszähler wird an einem Umstellungstag WEDER vorzeitig
    (Frühjahr) NOCH doppelt (Herbst) zurückgesetzt.

    Gebucht wird an der ERSTEN Ortsstunde des Tages; danach wird an JEDER
    weiteren Ortsstunde desselben Tages gelesen — überall muss 1 stehen. Erst
    die erste Stunde des Folgetags liefert 0.

    ROT HEUTE: gelesen wird gegen den WIENER Kalendertag. Der wechselt gegenüber
    dem Lissabonner um eine Stunde versetzt, also fällt der Zähler an der
    falschen Stelle auf 0.
    """
    from services import alert_daily_limit

    user_id = sauberer_nutzer(f"ac10-{tag.isoformat()}")
    raster = _stundenraster(tag, LISBON)
    mit_zone(
        alert_daily_limit.increment, user_id, raster[0], zone=LISBON,
    )

    zu_frueh = [
        moment.astimezone(LISBON).isoformat()
        for moment in raster
        if mit_zone(
        alert_daily_limit.load, user_id, moment, zone=LISBON,
    ) != 1
    ]
    assert not zu_frueh, (
        f"Der Zähler wurde am {tag} mitten am Ortstag zurückgesetzt: {zu_frueh}"
    )

    erste_stunde_folgetag = _stundenraster(tag + timedelta(days=1), LISBON)[0]
    assert mit_zone(
        alert_daily_limit.load, user_id, erste_stunde_folgetag, zone=LISBON,
    ) == 0, "An der Orts-Mitternacht des Folgetags muss der Zähler neu beginnen."


# ═══════════════════════════════════════════════════════════════════════════
# AC-12 / AC-13 / AC-14 — Dokumentation und Wächter-Restliste
# ═══════════════════════════════════════════════════════════════════════════


def test_ac12_adr_0044_nennt_die_beiden_module_nicht_mehr_als_ausnahme():
    """AC-12 — doc-compliance-test.

    ADR-0044 listet `alert_daily_limit` und `deviation_alert_engine` heute
    unter „Bewusst NICHT betroffen (feste Zone ist dort Absicht)". Nach dieser
    Scheibe stimmt das nicht mehr.

    Dateiinhalt-Prüfung ist hier ausdrücklich zulässig (Spec AC-12): der
    Gegenstand der Zusicherung IST die Dokumentation.

    ROT HEUTE: der Absatz steht unverändert da.
    """
    # doc-compliance-test
    adr = (ROOT / "docs/adr/0044-kalendertage-folgen-der-ortszeit.md").read_text(
        encoding="utf-8"
    )
    marker = "**Bewusst NICHT betroffen**"
    assert marker in adr, "Der Abschnitt selbst muss erhalten bleiben."

    start = adr.index(marker)
    ende = adr.find("\n\n", start)
    absatz = adr[start:ende if ende != -1 else len(adr)]

    for modul in ("alert_daily_limit", "deviation_alert_engine"):
        assert modul not in absatz, (
            f"ADR-0044 führt `{modul}` weiterhin als bewusste Ausnahme — nach "
            "#1726 folgt das Modul der Ortszone und gehört in den Abschnitt "
            "'Umgesetzt'."
        )


def test_ac13_waechter_restliste_verliert_genau_die_vier_eintraege():
    """AC-13: Die vier zu dieser Scheibe gehörenden Einträge sind aus
    `KNOWN_VIOLATIONS` entfernt.

    Geprüft wird die DATENSTRUKTUR des Wächters, nicht der Dateitext — nach dem
    Fix findet der Scanner diese Stellen nicht mehr, und
    `test_known_violations_only_shrink()` würde sie sonst als „stale" melden.

    ROT HEUTE: alle vier stehen noch drin.
    """
    from tests.test_output_timezone_guard import KNOWN_VIOLATIONS

    zu_entfernen = [
        "src/services/alert_daily_limit.py::<module>::0",
        "src/services/deviation_alert_engine.py::<module>::0",
        "src/services/alert_daily_limit.py::_vienna_date_str::0",
        "src/services/deviation_alert_engine.py::is_quiet_hours::0",
    ]
    verblieben = [k for k in zu_entfernen if k in KNOWN_VIOLATIONS]

    assert not verblieben, (
        "Diese Einträge gehören zu #1726 und müssen mit dem Fix verschwinden "
        f"(die Liste darf nur schrumpfen): {verblieben}"
    )


def test_ac14_blockkommentar_weist_die_muster_a_restliste_1727_zu():
    """AC-14 — doc-compliance-test.

    Der Blockkommentar bei `tests/test_output_timezone_guard.py:593` weist
    heute ALLE 53 Bestandseinträge pauschal #1726 zu — auch die ~25
    Muster-A-Funde, die tatsächlich #1727 (S5) tragen. Nach dem Schliessen von
    #1726 zeigte die Liste auf ein erledigtes Issue.

    ROT HEUTE: der Kommentar nennt #1727 nirgends.
    """
    # doc-compliance-test
    quelle = (ROOT / "tests/test_output_timezone_guard.py").read_text(encoding="utf-8")
    marker = "ENTSCHEIDUNGS-SCHICHT (Issue #1723"
    assert marker in quelle, "Der Blockkommentar selbst muss erhalten bleiben."

    start = quelle.index(marker)
    block = quelle[start:start + 1400]

    assert "#1727" in block, (
        "Der Blockkommentar muss die verbleibenden Muster-A-Funde auf #1727 "
        "verweisen, statt sie weiter #1726 zuzuschreiben."
    )
    assert "die Behebung traegt #1726 (S4)" not in block, (
        "Die pauschale Zuweisung der GESAMTEN Restliste an #1726 ist nach dem "
        "Schliessen dieses Issues falsch."
    )


# ═══════════════════════════════════════════════════════════════════════════
# AC-15 — Gelöschter/unauflösbarer erster Ort kippt nicht still auf Weltzeit
# ═══════════════════════════════════════════════════════════════════════════


def test_ac15_geloeschter_erster_ort_faellt_auf_den_naechsten_aufloesbaren(
    sauberer_nutzer,
):
    """AC-15: Steht in `location_ids` eine Kennung, zu der es keinen Ort mehr
    gibt (gelöschter Ort — der Filter in `compare_official_alert.py:128` gibt
    es zu), gilt die Zone des ersten Orts, der sich AUFLÖSEN LÄSST.

    Given ein Vergleich [gelöschte-ID, Auckland] mit einem Fenster um die
    Auckland-Ortszeit / Then ist er ruhig.

    ROT HEUTE: geprüft wird gegen Wien. Und ein naiver Fix
    (`all_locations.get(location_ids[0])` als reiner Indexzugriff) fällt hier
    ebenfalls durch: `location_tz(None)` liefert still UTC, und in UTC ist das
    Auckland-Fenster nicht erfüllt.
    """
    fenster = fenster_um_jetzt(AUCKLAND)
    user_id = sauberer_nutzer("ac15-geloescht")
    schreibe_ort(user_id, "loc-akl", "Pacific/Auckland")
    schreibe_presets(user_id, [
        vergleichs_preset("cp-luecke", ["loc-weg", "loc-akl"],
                          quiet_from=fenster[0], quiet_to=fenster[1])
    ])
    dienst = vergleichs_alarmdienst(user_id)
    dienst.check_all_compare_presets()

    assert type(dienst).detect_aufrufe == 0, (
        "Der erste AUFLÖSBARE Ort bestimmt die Zone — ein gelöschter Eintrag "
        "davor darf den Vergleich nicht still auf Weltzeit kippen."
    )


def test_ac15_kein_aufloesbarer_ort_ergibt_utc_und_einen_protokolleintrag(
    sauberer_nutzer, caplog,
):
    """AC-15 (zweiter Teil): Löst KEIN Ort eine Zone auf, gilt UTC — aber
    sichtbar, mit der Vergleichs-Kennung im Protokoll.

    Given ein Vergleich, dessen EINZIGE Ortskennung ins Leere zeigt (der Ort
    wurde gelöscht, die Kennung blieb im Preset stehen) / When die Ruhezeit
    bestimmt wird / Then gilt UTC (das Fenster um die UTC-Uhrzeit
    unterdrückt), UND es steht eine Warnung mit der Preset-Kennung im
    Protokoll.

    ROT HEUTE: geprüft wird gegen Wien (das UTC-Fenster greift dort nicht), und
    protokolliert wird gar nichts.

    Zur Wahl des Falls s. den Korrektur-Block oben bei den Ablage-Helfern:
    eine Koordinate ohne auflösbare Zone gibt es seit `timezonefinder` 6 nicht
    mehr, die ins Leere zeigende Kennung ist der reale Fall.
    """
    import logging

    fenster = fenster_um_jetzt(ZoneInfo("UTC"))
    user_id = sauberer_nutzer("ac15-nichts")
    schreibe_presets(user_id, [
        vergleichs_preset("cp-ohne-zone", ["loc-alle-weg"],
                          quiet_from=fenster[0], quiet_to=fenster[1])
    ])
    dienst = vergleichs_alarmdienst(user_id)

    with caplog.at_level(logging.WARNING):
        dienst.check_all_compare_presets()

    assert type(dienst).detect_aufrufe == 0, (
        "Ohne auflösbare Zone gilt UTC — das UTC-Fenster muss greifen."
    )
    assert any(
        "cp-ohne-zone" in eintrag.getMessage() for eintrag in caplog.records
    ), (
        "Der UTC-Rückfall darf nicht still geschehen: er gehört mit der "
        "Vergleichs-Kennung ins Protokoll."
    )


# ═══════════════════════════════════════════════════════════════════════════
# FIX-LOOP 1 — drei Stellen, die KEIN Test bewachte
#
# Der Adversary hat die Verdrahtung als korrekt gelesen und trotzdem BROKEN
# geurteilt — nicht behauptet, sondern gemessen: er hat den Produktivcode an
# drei Stellen verfälscht, und die Suite blieb grün. Ein grüner Testlauf
# beweist nur, dass die Tests durchlaufen, nicht dass sie etwas bewachen.
#
# Jeder Test dieses Abschnitts nennt im Docstring die Verfälschung, gegen die
# er rot wird, und WARUM die vorhandenen Tests sie durchgelassen haben.
# ═══════════════════════════════════════════════════════════════════════════


def _segment_wetter(precip_sum_mm: float, segment_id: int = 1):
    """Ein echtes `SegmentWeatherData` mit vorgegebener Niederschlagssumme.

    Aufbau übernommen aus `test_issue_1070_daily_alert_limit.py::_weather_data`
    — dieselbe Δ-Erkennung, dieselben Feldnamen. Ohne echte Wetterdaten auf
    BEIDEN Seiten (`cached` und `fresh`) wird `DeviationAlertEngine.evaluate()`
    gar nicht erst erreicht; genau daran scheiterte die Absicherung von F001.
    """
    from app.models import (
        ForecastMeta,
        GPXPoint,
        NormalizedTimeseries,
        Provider,
        SegmentWeatherData,
        SegmentWeatherSummary,
        TripSegment,
    )

    start = datetime(2026, 4, 5, 8, 0, tzinfo=UTC)
    return SegmentWeatherData(
        segment=TripSegment(
            segment_id=segment_id,
            start_point=GPXPoint(
                lat=47.0, lon=11.0, elevation_m=1000, distance_from_start_km=12.0,
            ),
            end_point=GPXPoint(
                lat=47.1, lon=11.1, elevation_m=1500, distance_from_start_km=18.0,
            ),
            start_time=start, end_time=start + timedelta(hours=4),
            duration_hours=4.0, distance_km=6.0, ascent_m=500, descent_m=0,
        ),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(precip_sum_mm=precip_sum_mm),
        fetched_at=datetime.now(UTC),
        provider="openmeteo",
    )


def _trip_mit_aenderungserkennung(user_id: str, trip_id: str, zone_name: str,
                                  quiet: tuple[str, str]):
    """Trip wie :func:`trip_mit_ruhezeit`, zusätzlich mit scharfer
    Δ-Erkennung für `precipitation_sum` — sonst filtert die Engine die
    Änderung als unbedeutend weg, bevor irgendetwas versendet wird."""
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig

    trip = trip_mit_ruhezeit(user_id, trip_id, zone_name, quiet)
    trip.display_config = UnifiedWeatherDisplayConfig(
        trip_id=trip_id,
        metrics=[MetricConfig(metric_id="precipitation", enabled=True)],
        metric_alert_levels={"precipitation_sum": "standard"},
    )
    return trip


def _deviation_versand(user_id: str, zone_name: str, quiet: tuple[str, str]):
    """Ein VOLLSTÄNDIGER `check_and_send_alerts()`-Lauf mit echten Wetterdaten
    auf beiden Seiten — bis in `DeviationAlertEngine.evaluate()` hinein und
    weiter bis zum Versand. Liefert `(ergebnis, anzahl_versendeter_mails)`."""
    from services.trip_alert import TripAlertService

    gesendet: list = []
    dienst = TripAlertService(
        settings=settings_email_only(), throttle_hours=0, user_id=user_id,
        mail_sink=lambda *a, **kw: gesendet.append((a, kw)),
    )
    trip = _trip_mit_aenderungserkennung(user_id, "t-kern-trip", zone_name, quiet)
    ergebnis = dienst.check_and_send_alerts(
        trip, [_segment_wetter(2.0)], fresh_weather=[_segment_wetter(18.0)],
    )
    return ergebnis, len(gesendet)


def test_f001_zweite_ruhezeit_pruefung_der_engine_nutzt_die_trip_zone(sauberer_nutzer):
    """F001 — `trip_alert.py:279`: die Zone in `AlertEvaluationConfig`.

    Diese Zone wirkt NICHT an der Stelle, an der sie steht, sondern in der
    ZWEITEN Ruhezeit-Prüfung, die innerhalb von `DeviationAlertEngine.
    evaluate()` läuft (`deviation_alert_engine.py:285-287`).

    Warum kein bestehender Test sie bewacht: alle Trip-Fixturen dieser Datei
    halten `_fetch_fresh_weather()` bei `[]` an. Der Ablauf bricht dann schon
    bei `trip_alert.py:252-254` ab — also VOR der Bildung der Konfiguration.
    `evaluate()` wird über den TRIP-Erbauer nie erreicht; AC-3 Stelle 7 misst
    ausschliesslich den COMPARE-Erbauer. Gemessen: eine fest verdrahtete
    Wiener Zone an `:279` liess alle 52 Tests grün.

    Wie dieser Test die INNERE Prüfung von der äusseren trennt: das
    Ruhezeit-Fenster liegt um die WIENER Ortszeit. Die äussere Prüfung
    (`:230`, Zone Auckland) lässt den Lauf damit durch — und die innere muss
    dasselbe tun. Rechnet sie in Wien, unterdrückt sie, und nichts kommt an.

    ROT bei der Verfälschung `zone=anchor_tz(trip, now_utc)` →
    `ZoneInfo("Europe/Vienna")` an `:279`.
    """
    ergebnis, versendet = _deviation_versand(
        sauberer_nutzer("f001-kern"), "Pacific/Auckland", fenster_um_jetzt(VIENNA),
    )

    assert ergebnis is True, (
        "Ein Fenster um die WIENER Uhrzeit darf den Auckland-Trip nirgends "
        "stilllegen — auch nicht in der zweiten Prüfung im Engine-Kern, die "
        "ihre Zone aus `AlertEvaluationConfig` bezieht."
    )
    assert versendet >= 1, "Der Alarm muss tatsächlich hinausgehen, nicht nur True melden."

    # Gegenprobe in derselben Bauart: liegt das Fenster um die AUCKLAND-Zeit,
    # muss derselbe Lauf still bleiben. Ohne sie wäre die Zusicherung oben
    # auch von einem Alarm erfüllt, der gar keine Ruhezeit mehr prüft.
    ergebnis_ruhig, versendet_ruhig = _deviation_versand(
        sauberer_nutzer("f001-kern-gegen"), "Pacific/Auckland",
        fenster_um_jetzt(AUCKLAND),
    )

    assert ergebnis_ruhig is False
    assert versendet_ruhig == 0, (
        "Die Auckland-Ruhezeit muss denselben Lauf unterdrücken — sonst misst "
        "die Zusicherung oben einen Pfad ohne jede Ruhezeit-Prüfung."
    )


# ── F002: `anchor_tz` gegen `trip_tz` — nur ein MEHRETAPPIGER Trip trennt sie ─
#
# `anchor_tz(trip, now)` liefert die Zone der Etappe des WELTZEIT-Tages,
# `trip_tz(trip)` die der ERSTEN Etappe mit Wegpunkten. Bei einem Trip mit
# genau einer Etappe ist das zwangsläufig dieselbe Zone — und jede Trip-Fixture
# dieser Datei baut genau eine. Gemessen: ersetzt man JEDEN `anchor_tz`-Aufruf
# in `trip_alert.py` durch `trip_tz(trip)`, bleibt die gesamte Suite grün.
#
# Das wiegt schwer, weil Abschnitt B der Spec ausdrücklich begründet, warum
# `anchor_tz` nötig ist: „ein mehrtägiger Trek, der die Zone wechselt, braucht
# die Zone SEINER AKTUELLEN Etappe, nicht die des Starttags". Diese Begründung
# hatte bis hierher keinen Wächter.


def trip_zwei_zonen(user_id: str, trip_id: str, *, erste_zone: str,
                    heutige_zone: str, quiet: tuple[str | None, str | None]):
    """Trip über ZWEI Etappen in verschiedenen Zonen.

    Etappe 1 (erste der Liste, mit Wegpunkten, GESTERN) liegt in `erste_zone`
    — das ist, was `trip_tz()` liefert. Etappe 2 trägt den heutigen
    Weltzeit-Tag und liegt in `heutige_zone` — das ist, was `anchor_tz()`
    liefert. Nur so lassen sich die beiden Auflösungen überhaupt
    unterscheiden.
    """
    heute = datetime.now(UTC).date()
    lat_erste, lon_erste = KOORDINATEN[erste_zone]
    lat_heute, lon_heute = KOORDINATEN[heutige_zone]
    trip = make_trip(
        trip_id,
        cooldown_minutes=0,
        quiet_from=quiet[0],
        quiet_to=quiet[1],
        stage_date=heute - timedelta(days=1),
        lat=lat_erste,
        lon=lon_erste,
        extra_stages=[
            trip_stage("S2", heute, lat_heute, lon_heute, wp_prefix="B"),
        ],
    )
    trip.report_config.alert_on_changes = True
    save_trip(trip, user_id)
    return trip


def test_f002_anchor_tz_und_trip_tz_liefern_bei_diesem_trip_verschiedene_zonen():
    """F002 (Vorbedingung, grüner Anker): Der Prüf-Trip der beiden folgenden
    Tests trennt die zwei Auflösungen tatsächlich.

    Kein Prüfling-Test — er sichert nur, dass die folgenden Zusicherungen
    überhaupt etwas unterscheiden können. Fiele er, wären sie so blind wie die
    einetappigen Fixturen, die den Fehler durchgelassen haben.
    """
    from services.trip_day import anchor_tz, trip_tz

    trip = trip_zwei_zonen(
        _uid("f002-vorbedingung"), "t-vorbedingung",
        erste_zone="America/Los_Angeles", heutige_zone="Pacific/Auckland",
        quiet=(None, None),
    )
    jetzt = datetime.now(UTC)

    assert str(trip_tz(trip)) == "America/Los_Angeles", (
        "Die erste Etappe mit Wegpunkten liegt in Los Angeles."
    )
    assert str(anchor_tz(trip, jetzt)) == "Pacific/Auckland", (
        "Die Etappe des heutigen Weltzeit-Tages liegt in Auckland — nur wenn "
        "beide Auflösungen hier auseinanderfallen, messen die folgenden Tests "
        "die Wahl zwischen ihnen."
    )
    clean_uid(_uid("f002-vorbedingung"))


def _zwei_zonen_lauf(user_id: str, quiet: tuple[str | None, str | None]) -> int:
    """`check_and_send_alerts()` für den zweietappigen Trip; liefert die Zahl
    der Wetterabrufe (0 = vorher unterdrückt)."""
    dienst = trip_abweichungsdienst(user_id)
    trip = trip_zwei_zonen(
        user_id, "t-zwei-zonen",
        erste_zone="America/Los_Angeles", heutige_zone="Pacific/Auckland",
        quiet=quiet,
    )
    dienst.check_and_send_alerts(trip, cached_weather=[])
    return type(dienst).fetch_aufrufe


def test_f002_ruhezeit_folgt_der_heutigen_etappe_nicht_der_ersten(sauberer_nutzer):
    """F002 (Ruhezeit) — `trip_alert.py:700` (`_is_quiet_hours`-Adapter).

    Given ein Trek, dessen erste Etappe in Los Angeles liegt und dessen Etappe
    des heutigen Tages in Auckland / When die Ruhezeit geprüft wird / Then
    gilt die Zone der HEUTIGEN Etappe.

    ROT bei der Verfälschung `anchor_tz(trip, now)` → `trip_tz(trip)`: dann
    kippen BEIDE Zusicherungen gleichzeitig — der Auckland-Lauf liefe weiter,
    der Los-Angeles-Lauf würde stillgelegt.
    """
    abrufe_heutige_etappe = _zwei_zonen_lauf(
        sauberer_nutzer("f002-ruhe-heute"), fenster_um_jetzt(AUCKLAND),
    )
    abrufe_erste_etappe = _zwei_zonen_lauf(
        sauberer_nutzer("f002-ruhe-erste"), fenster_um_jetzt(LOS_ANGELES),
    )

    assert abrufe_heutige_etappe == 0, (
        "Die Ruhezeit muss der Zone der heutigen Etappe (Auckland) folgen."
    )
    assert abrufe_erste_etappe >= 1, (
        "Die Zone der ERSTEN Etappe (Los Angeles) darf einen Trek, der längst "
        "woanders ist, nicht mehr stilllegen — genau dafür gibt es `anchor_tz`."
    )


def test_f002_tageszaehler_folgt_der_heutigen_etappe_nicht_der_ersten(sauberer_nutzer):
    """F002 (Tageszähler) — `trip_alert.py:243` (`is_allowed`).

    Given derselbe Trek (erste Etappe Los Angeles, heutige Etappe Auckland)
    und ein Free-Kontingent, das in EINER der beiden Zonen erschöpft ist /
    When ein Abweichungs-Alarm ansteht / Then entscheidet der Auckland-Zähler.

    Free-Limit 2, davon reserviert `reason="forecast_change"` einen Platz für
    NowCast (#1555) — ein Stand von 1 sperrt also bereits.

    ROT bei derselben Verfälschung wie oben (`anchor_tz` → `trip_tz`): dann
    entscheidet der Los-Angeles-Zähler und beide Zusicherungen kippen.
    """
    def lauf(zone: ZoneInfo, kennung: str) -> int:
        user_id = sauberer_nutzer(kennung)
        seed_daily_counter(user_id, 1, zone=zone)
        return _zwei_zonen_lauf(user_id, (None, None))

    abrufe_bei_vollem_auckland = lauf(AUCKLAND, "f002-zaehler-heute")
    abrufe_bei_vollem_la = lauf(LOS_ANGELES, "f002-zaehler-erste")

    assert abrufe_bei_vollem_auckland == 0, (
        "Erschöpftes Kontingent in der Zone der HEUTIGEN Etappe muss den "
        "Alarm sperren — vor jedem Wetterabruf."
    )
    assert abrufe_bei_vollem_la >= 1, (
        "Ein erschöpftes Kontingent in der Zone der ERSTEN Etappe geht diesen "
        "Trek nichts mehr an; das Auckland-Kontingent steht auf 0."
    )


# ── F003: Prüfung und Buchung des Kontingents dürfen nicht auseinanderlaufen ──
#
# Beide Vergleichspfade lösen die Zone EINMAL auf und benutzen sie für die
# Prüfung (`is_allowed`) UND die Buchung (`increment`). Dass beide dieselbe
# Zone sehen, hängt allein an einer gemeinsamen lokalen Variable. Gemessen:
# stellt man NUR `increment()` auf eine feste Wiener Zone um, bleibt alles
# grün — AC-6/AC-7 prüfen `alert_daily_limit.*` ausschliesslich direkt über
# den Testhelfer, nie über die tatsächlichen Aufrufstellen. `alert_gate.py`
# benennt die Gefahr im eigenen Docstring: „wer hier eine andere zone
# uebergibt als check_nowcast_gate(), fuellt einen anderen Zaehler als den
# geprueften".
#
# Beide Tests unten laufen deshalb über den ECHTEN Preset-Lauf und messen die
# Wirkung, die eine Divergenz hätte: der Riegel greift nicht mehr.


def _amtlicher_vergleichsdienst_mit_warnung(user_id: str, gesendet: list):
    """`CompareOfficialAlertService`, dessen Netz-Naht `_detect()` bei JEDEM
    Lauf eine echte amtliche Warnung liefert — der Riegel, der den zweiten
    bzw. dritten Lauf stoppen muss, ist dann allein das Tageskontingent."""
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts.models import OfficialAlert

    class _MitWarnung(CompareOfficialAlertService):
        def _detect(self, preset_id, locs, sources=None):
            warnung = OfficialAlert(
                source="test-quelle", hazard="wind", level=3,
                label="Sturmwarnung", region_label="Testregion",
            )
            return ([(warnung, [loc.id for loc in locs])], {})

    return _MitWarnung(
        settings=settings_email_only(), user_id=user_id,
        mail_sink=lambda *a, **kw: gesendet.append((a, kw)),
    )


def test_f003_amtlicher_vergleich_bucht_in_der_zone_die_er_auch_prueft(
    sauberer_nutzer,
):
    """F003 (amtliche Warnung) — `compare_official_alert.py:146` (`is_allowed`)
    gegen `:190` (`increment`).

    Given ein Free-Nutzer (Kontingent 2) mit einem Vergleich in Auckland /
    When drei amtliche Warnungen nacheinander anstehen / Then gehen die ersten
    beiden hinaus und die dritte wird gesperrt.

    Das fängt eine Divergenz zwischen Prüf- und Buchungszone in BEIDE
    Richtungen: bucht `increment()` woanders als `is_allowed()` prüft, steht
    der geprüfte Zähler dauerhaft auf 0 und der Riegel greift nie.

    ROT bei der Verfälschung `alert_daily_limit.increment(self._user_id, now,
    zone)` → feste Wiener Zone an `:190` (dritter Lauf geht dann ebenfalls
    hinaus).
    """
    user_id = sauberer_nutzer("f003-amtlich")
    schreibe_ort(user_id, "loc-akl", "Pacific/Auckland")
    schreibe_presets(user_id, [vergleichs_preset("cp-kontingent", ["loc-akl"])])

    gesendet: list = []
    dienst = _amtlicher_vergleichsdienst_mit_warnung(user_id, gesendet)
    laeufe = [dienst.check_all_compare_presets() for _ in range(3)]

    assert laeufe == [1, 1, 0], (
        f"Free-Kontingent 2: zwei Warnungen gehen hinaus, die dritte ist "
        f"gesperrt. Gemessen: {laeufe}"
    )
    assert read_daily_counter(user_id, zone=AUCKLAND) == 2, (
        "Gebucht werden muss in DERSELBEN Zone, gegen die geprüft wird."
    )
    assert read_daily_counter(user_id, zone=VIENNA) == 0, (
        "Eine Buchung auf der Wiener Uhr wäre ein Zähler, den niemand liest."
    )


class _OrtsWetterQuelle:
    """Echte `LocationWeatherSource`-Naht (kein Mock): liefert für jeden Ort
    ein festes `PointWeatherData` mit vorgegebener Niederschlagssumme, ohne
    Netzzugriff. Vorbild: `test_issue_1070_daily_alert_limit.py::
    _ScriptedComparePointSource`."""

    def __init__(self, precip_sum_mm: float) -> None:
        self._precip = precip_sum_mm

    def fetch(self, point_id: str, lat: float, lon: float,
              start_hour: int | None = None, end_hour: int | None = None):
        from app.models import SegmentWeatherSummary
        from services.point_weather import PointWeatherData

        return PointWeatherData(
            id=point_id, name=point_id, lat=lat, lon=lon, timeseries=None,
            aggregated=SegmentWeatherSummary(precip_sum_mm=self._precip),
            fetched_at=datetime.now(UTC), provider="test-fix-loop",
        )


def test_f003_vergleichs_aenderungsalarm_bucht_in_der_zone_die_er_auch_prueft(
    sauberer_nutzer,
):
    """F003 (Änderungsalarm) — `compare_alert.py:158` (`is_allowed`) gegen
    `:301` (`increment`). Strukturell identisch angreifbar wie der amtliche
    Pfad, deshalb hier eigenständig nachgewiesen.

    Given ein Free-Nutzer mit ZWEI Vergleichen am selben Auckland-Ort, beide
    mit einer deutlichen Wetter-Abweichung gegen ihren Δ-Anker / When der
    Alarmlauf beide abarbeitet / Then geht genau EINER hinaus: der erste
    verbraucht das um die NowCast-Reserve verringerte Kontingent (Free 2 − 1),
    der zweite sieht es als erschöpft.

    ROT bei der Verfälschung `alert_daily_limit.increment(self._user_id, now,
    config.zone)` → feste Wiener Zone: dann bleibt der Auckland-Zähler auf 0
    und BEIDE Vergleiche senden.
    """
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    user_id = sauberer_nutzer("f003-aenderung")
    ort = schreibe_ort(user_id, "loc-akl", "Pacific/Auckland")
    preset_ids = ["cp-erst", "cp-zweit"]
    schreibe_presets(
        user_id, [vergleichs_preset(pid, ["loc-akl"]) for pid in preset_ids],
    )
    anker = _OrtsWetterQuelle(2.0)
    for preset_id in preset_ids:
        CompareWeatherSnapshotService(user_id=user_id).save(
            preset_id, ort.id, anker.fetch(ort.id, ort.lat, ort.lon),
        )

    gesendet: list = []
    dienst = CompareAlertService(
        settings=settings_email_only(), user_id=user_id,
        weather_source=_OrtsWetterQuelle(30.0),
        mail_sink=lambda *a, **kw: gesendet.append((a, kw)),
    )
    versandt = dienst.check_all_compare_presets()

    assert versandt == 1, (
        f"Der zweite Vergleich muss am Kontingent scheitern, das der erste "
        f"verbraucht hat. Gemessen: {versandt} Versände."
    )
    assert read_daily_counter(user_id, zone=AUCKLAND) == 1, (
        "Gebucht werden muss in DERSELBEN Zone, gegen die geprüft wird."
    )
    assert read_daily_counter(user_id, zone=VIENNA) == 0, (
        "Eine Buchung auf der Wiener Uhr wäre ein Zähler, den niemand liest."
    )
