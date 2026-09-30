"""Kette Ortsvergleich-ALARME: Preset-JSON bis zum gesendeten Alarm je Kanal
(Issue #2422, Scheibe S5, Block D, AC-14..AC-22).

SPEC: docs/specs/modules/fix_2422_s5_ortsvergleich_kette.md.

Einstieg wie im Betrieb: das Preset liegt als ROHES JSON der Fixture-Datei
(``tests/fixtures/compare_kette/alarm_kanaele.json``) im Nutzerverzeichnis; die
DREI oeffentlichen Alarmdienste (``CompareAlertService`` = Abweichung,
``CompareRadarAlertService``, ``CompareOfficialAlertService``) lesen es ueber
ihren echten Loader. Messpunkt: die vier Kanal-Ausgaenge, ersetzt durch den
geteilten Aufzeichner (``tests/helpers/transport_mitschrift.py``); keine
``*_sink``-Parameter. Nur die Wetter-/Radar-/Warn-QUELLE ist ersetzt (echte
Klassen mit echten Signaturen, kein Netz).

Erwartungen (``compare_alarm_kanaele``) kommen aus dem rohen JSON, dem Tarif und
der Dringlichkeit -- NIE aus ``effective_alert_channels``/``split_by_threshold``.
Jeder Test ruft die Vorbedingung VOR seinen Zusicherungen; jeder datenbewegende
Test laeuft mit ZWEI Nutzern (eigene Kennung, eigene Empfaenger).

Presets tragen ausdruecklich Slot-Zeiten AUSSERHALB des Briefing-Vorlaufs
(``briefing_zeiten_iso``): sonst blockiert je nach Tageszeit die Vorlauf-Sperre
(#1594) und der Test misst sie statt seiner Zusicherung.

RED heute: AC-21 (abgelaufenes ``end_date`` ist fuer die Alarme NICHT stumm --
``fix_1594`` AC-7 sagte bisher das Gegenteil). Alles uebrige sichert den Ist-Stand.
"""
from __future__ import annotations

import copy
import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.loader import get_data_dir
from app.models import SegmentWeatherSummary
from services.compare_slot_scheduler import presets_due_for_hour
from services.radar_cache import reset_shared_radar_cache_for_tests
from tests.helpers.briefing_zeiten import briefing_zeiten_iso
from tests.helpers.einstellung_auslieferung_orakel import (
    COMPARE_KANAELE,
    compare_alarm_kanaele,
    compare_vorbedingung_pruefen,
)
from tests.helpers.transport_mitschrift import Kanalmitschrift, aufzeichner_installieren
from tests.tdd._compare_kette_fixtures import (
    ORTE,
    alle_orte,
    briefing_senden,
    engine_naht,
    fixture_dict,
    nutzer_anlegen,
    orte_anlegen,
    preset_ablegen,
    settings_fuer,
    transport_einrichten,
)

WIEN = ZoneInfo("Europe/Vienna")
IBK = (47.27, 11.39)
ARTEN = ("abweichung", "radar", "amtlich")
#: Niederschlags-Anker 2 mm; Live 14 mm -> MINOR/LOW, Live 30 mm -> MAJOR/HIGH
#: (Massstab wie ``test_compare_alert_channel_threshold.py``).
ANKER_MM = 2.0
LIVE_MM = {"LOW": 14.0, "HIGH": 30.0}  # nur diese beiden Stufen sind beim Abweichungsalarm kalibriert
#: amtliche Warnstufe -> Dringlichkeit (2 = LOW, 3 = MODERATE, 4 = HIGH)
AMTLICH_STUFE = {"LOW": 2, "MODERATE": 3, "HIGH": 4}


# ---------------------------------------------------------------------------
# Quellen (echte Klassen, kein Netz)
# ---------------------------------------------------------------------------


class _Wetterquelle:
    """``LocationWeatherSource`` mit vorab festgelegtem Niederschlag je Ort."""

    def __init__(self, mm: float) -> None:
        self._mm = mm
        self.aufrufe = 0

    def fetch(self, point_id, lat, lon, start_hour=None, end_hour=None,
              elevation_m=None, user_id=None, **_):
        from services.point_weather import PointWeatherData

        self.aufrufe += 1
        return PointWeatherData(
            id=point_id, name=point_id, lat=lat, lon=lon, timeseries=None,
            aggregated=SegmentWeatherSummary(precip_sum_mm=self._mm),
            fetched_at=datetime.now(timezone.utc), provider="test-scripted",
        )


class _Radarquelle:
    """``frame_source`` von ``RadarNowcastService``: nasser Frame nur am Ort Innsbruck."""

    def __init__(self, *, konvektiv: bool) -> None:
        self._konvektiv = konvektiv
        self.aufrufe = 0

    def __call__(self, lat: float, lon: float) -> list:
        from providers.brightsky import RadarFrame

        self.aufrufe += 1
        if (round(lat, 4), round(lon, 4)) != IBK:
            return []
        ts = datetime.now(timezone.utc) + timedelta(minutes=8)
        return [RadarFrame(timestamp=ts, precip_mm_h=0.6, is_convective=self._konvektiv)]


class _Warnquelle:
    """Echte amtliche Quelle fuer den Punkt Innsbruck (Toleranz 0.05)."""

    name = "kette-quelle"

    def __init__(self, stufe: int) -> None:
        from services.official_alerts.models import OfficialAlert

        jetzt = datetime.now(timezone.utc)
        self._alerts = [OfficialAlert(
            source="kette-quelle", hazard="extreme_heat", level=stufe, label="Hitze",
            valid_from=jetzt - timedelta(hours=1), valid_to=jetzt + timedelta(hours=23),
            region_label="Innsbruck",
        )]
        self.fetch_calls = 0

    def covers(self, lat, lon) -> bool:
        return abs(lat - IBK[0]) < 0.05 and abs(lon - IBK[1]) < 0.05

    def fetch(self, lat, lon):
        self.fetch_calls += 1
        return list(self._alerts)


@contextmanager
def _amtliche_quelle(quelle: _Warnquelle):
    import services.official_alerts.base as b
    from services.official_alerts import register_official_alert_source

    sicherung = list(b._REGISTERED_SOURCES)
    b._REGISTERED_SOURCES.clear()
    register_official_alert_source(quelle)
    try:
        yield quelle
    finally:
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.extend(sicherung)


# ---------------------------------------------------------------------------
# Aufbau
# ---------------------------------------------------------------------------


@pytest.fixture
def mit(monkeypatch) -> Kanalmitschrift:
    transport_einrichten(monkeypatch)
    engine_naht(monkeypatch)
    return aufzeichner_installieren(monkeypatch)


@dataclass
class Nutzer:
    uid: str
    tier: str
    roh: dict   # Preset-JSON, wie es auf der Platte liegt


def _nutzer(vorlage: dict, tier: str = "premium", *, anker: bool = True, **aenderungen) -> Nutzer:
    """Nutzer + Orte + Preset-Datei (Slot-Zeiten ausserhalb des Vorlaufs) + Δ-Anker."""
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from services.point_weather import PointWeatherData

    uid = nutzer_anlegen(tier)
    orte_anlegen(uid)
    p = copy.deepcopy(vorlage)
    p["morning_time"], p["evening_time"] = briefing_zeiten_iso(WIEN)
    p["id"] = f"{p['id']}-{uid[-6:]}"
    for k, v in aenderungen.items():
        if v is _WEG:
            p.pop(k, None)
        else:
            p[k] = v
    pfad = preset_ablegen(uid, p)
    if anker:
        snaps = CompareWeatherSnapshotService(user_id=uid)
        for lid, (name, lat, lon) in ORTE.items():
            snaps.save(p["id"], lid, PointWeatherData(
                id=lid, name=name, lat=lat, lon=lon, timeseries=None,
                aggregated=SegmentWeatherSummary(precip_sum_mm=ANKER_MM),
                fetched_at=datetime.now(timezone.utc), provider="test-scripted",
            ))
    return Nutzer(uid, tier, json.loads(pfad.read_text(encoding="utf-8")))


_WEG = object()  # Sentinel: Schluessel aus dem JSON ENTFERNEN


def _ausloesen(art: str, n: Nutzer, stufe: str, **kw) -> tuple[int, object]:
    """Genau ein Lauf des Alarmdienstes ``art`` mit der Lage ``stufe`` (LOW/MODERATE/HIGH).
    Gibt (Zahl gemeldeter Preset-Laeufe, Quelle) zurueck; die Quelle zaehlt ihre Abrufe."""
    settings = settings_fuer(n.uid)
    if art == "abweichung":
        from services.compare_alert import CompareAlertService

        quelle = _Wetterquelle(LIVE_MM[stufe])
        return CompareAlertService(settings=settings, user_id=n.uid, weather_source=quelle
                                   ).check_all_compare_presets(), quelle
    if art == "radar":
        from services.compare_radar_alert import CompareRadarAlertService
        from services.radar_service import RadarNowcastService

        # Der Radar-Cache ist prozessweit und nach Koordinaten geschluesselt: ohne
        # Leeren sieht der zweite Lauf die Lage des ersten.
        reset_shared_radar_cache_for_tests()
        quelle = _Radarquelle(konvektiv=(stufe == "HIGH"))
        return CompareRadarAlertService(
            settings=settings, user_id=n.uid, radar_service=RadarNowcastService(frame_source=quelle),
        ).check_all_compare_presets(), quelle
    from services.compare_official_alert import CompareOfficialAlertService

    quelle = _Warnquelle(AMTLICH_STUFE[stufe])
    with _amtliche_quelle(quelle):
        return CompareOfficialAlertService(settings=settings, user_id=n.uid).check_all_compare_presets(), quelle


def _lauf(mit: Kanalmitschrift, art: str, n: Nutzer, stufe: str) -> tuple[Kanalmitschrift, int, object]:
    mit.leeren()
    gemeldet, quelle = _ausloesen(art, n, stufe)
    snap = copy.deepcopy(mit)
    mit.leeren()
    return snap, gemeldet, quelle


def _pruefen(snap: Kanalmitschrift, n: Nutzer, art: str, stufe: str, *, metric_id=None) -> set[str]:
    """Vorbedingung, dann: bedient wird EXAKT die Kanalmenge des Orakels (vier Kanaele
    gleich streng), jeweils an die EIGENEN Empfaenger des Nutzers."""
    zugestellt, _ = compare_alarm_kanaele(n.roh, n.tier, stufe, metric_id=metric_id)
    assert zugestellt, "Vorbedingung: das Orakel erwartet mindestens einen Kanal"
    compare_vorbedingung_pruefen(snap, tuple(k for k in COMPARE_KANAELE if k in zugestellt))
    bedient = {k for k in COMPARE_KANAELE if snap.sendungen(k)}
    assert bedient == zugestellt, (
        f"{art}/{stufe}/Tarif {n.tier}: erwartet {sorted(zugestellt)}, bedient {sorted(bedient)} -- {snap!r}")
    if "email" in bedient:
        assert snap.empfaenger("email") == [f"{n.uid}@example.invalid"]
    if "telegram" in bedient:
        assert set(snap.empfaenger("telegram")) == {f"chat-{n.uid}"}
    return bedient


def _alle_kanaele(**extra) -> dict:
    ac = {"email": True, "telegram": True, "sms": True, "premium_sms": True}
    return {"alert_channels": ac, "alert_channel_thresholds": {}, **extra}


# ---------------------------------------------------------------------------
# AC-14 -- Briefing- und Alarm-Kanaele sind getrennt
# ---------------------------------------------------------------------------


def test_briefing_und_alarm_kanaele_sind_unabhaengig(mit):
    """AC-14: ``send_telegram`` an + ``alert_channels.telegram`` aus -> Telegram nur beim Briefing;
    umgekehrt nur beim Alarm; das Umlegen der Briefing-Schalter aendert die Alarm-Kanaele nicht."""
    a = _nutzer(fixture_dict("alarm_kanaele"), "premium",
                send_telegram=True, alert_channels={"email": True, "telegram": False, "sms": False, "premium_sms": False},
                alert_channel_thresholds={})
    b = _nutzer(fixture_dict("alarm_kanaele"), "premium",
                send_telegram=False, alert_channels={"email": True, "telegram": True, "sms": False, "premium_sms": False},
                alert_channel_thresholds={})
    a2 = _nutzer(fixture_dict("alarm_kanaele"), "premium",
                 send_telegram=False, send_sms=True, alert_channels=a.roh["alert_channels"],
                 alert_channel_thresholds={})
    assert a.roh["alert_channels"] == a2.roh["alert_channels"]

    for n, briefing_tg, alarm_tg in ((a, True, False), (b, False, True)):
        mit.leeren()
        briefing_senden(n.uid, n.roh["id"], settings_fuer(n.uid))
        compare_vorbedingung_pruefen(mit, ("email",))
        assert bool(mit.sendungen("telegram")) is briefing_tg, f"Briefing-Telegram bei {n.uid}"
        mit.leeren()
        snap, gemeldet, _ = _lauf(mit, "abweichung", n, "HIGH")
        assert gemeldet == 1
        _pruefen(snap, n, "abweichung", "HIGH")
        assert bool(snap.sendungen("telegram")) is alarm_tg, f"Alarm-Telegram bei {n.uid}"
    snap_a2, gemeldet, _ = _lauf(mit, "abweichung", a2, "HIGH")
    assert gemeldet == 1
    assert {k for k in COMPARE_KANAELE if snap_a2.sendungen(k)} == {"email"}, (
        "Briefing-Schalter (send_telegram/send_sms) duerfen die Alarm-Kanaele nicht veraendern")


# ---------------------------------------------------------------------------
# AC-15 -- Abweichungsalarm: Kanalmenge und Schwelle
# ---------------------------------------------------------------------------

_METRIK_UEBERSCHREIBUNG = {"precipitation": {"email": True, "telegram": True, "sms": True, "premium_sms": True}}


@pytest.mark.parametrize("stufe", ["LOW", "HIGH"])
def test_abweichungsalarm_kanalmenge_schwelle_und_tarif(mit, stufe):
    """AC-15: Kanalmenge aus Ueberschreibung (``alert_metric_channels``), Metrik-Union, Schwelle
    (SMS erst ab HIGH) und Tarif; zwei Nutzer mit verschiedenem Tarif bekommen je ihre Menge."""
    vorlage = fixture_dict("alarm_kanaele")
    vorlage["alert_metric_channels"] = _METRIK_UEBERSCHREIBUNG
    premium = _nutzer(vorlage, "premium")
    standard = _nutzer(vorlage, "standard")
    ergebnisse = {}
    for n in (premium, standard):
        snap, gemeldet, _ = _lauf(mit, "abweichung", n, stufe)
        assert gemeldet == 1
        ergebnisse[n.tier] = _pruefen(snap, n, "abweichung", stufe, metric_id="precipitation")
    if stufe == "LOW":
        assert ergebnisse["premium"] == {"email", "telegram", "premium_sms"}, "SMS liegt unter ihrer Schwelle HIGH"
        assert ergebnisse["standard"] == {"email", "telegram"}
    else:
        assert ergebnisse["premium"] == set(COMPARE_KANAELE)
        assert ergebnisse["standard"] == {"email", "telegram", "sms"}, "kein Premium-SMS im Tarif standard"


# ---------------------------------------------------------------------------
# AC-16 -- Radar: Standard AUS, dann Kanalmenge und Schwelle
# ---------------------------------------------------------------------------


def test_radar_alarm_standard_aus_und_kanalmenge_mit_schwelle(mit):
    """AC-16: ohne ``radar_alert_enabled`` kein Abruf, kein Versand; mit Schalter: unter der
    Schwelle (SMS erst ab HIGH) nur die Kanaele darunter, darueber alle aufgeloesten; ein
    pausiertes/archiviertes Preset schweigt (ohne Abruf)."""
    for tier in ("premium", "standard"):
        aus = _nutzer(fixture_dict("alarm_kanaele"), tier, radar_alert_enabled=_WEG)
        assert "radar_alert_enabled" not in aus.roh
        snap, gemeldet, quelle = _lauf(mit, "radar", aus, "HIGH")
        assert gemeldet == 0 and quelle.aufrufe == 0 and snap.kanaele == [], "Standard ist AUS: kein Abruf"

        an = _nutzer(fixture_dict("alarm_kanaele"), tier)
        snap, gemeldet, quelle = _lauf(mit, "radar", an, "LOW")
        assert quelle.aufrufe >= 1 and gemeldet == 1
        _pruefen(snap, an, "radar", "LOW")
        assert "sms" not in snap.kanaele, "SMS-Schwelle HIGH: knapp darunter nichts"

        hoch = _nutzer(fixture_dict("alarm_kanaele"), tier)
        snap, gemeldet, _ = _lauf(mit, "radar", hoch, "HIGH")
        assert gemeldet == 1
        bedient = _pruefen(snap, hoch, "radar", "HIGH")
        assert "sms" in bedient, "knapp ueber der SMS-Schwelle: SMS wird bedient"
    still = [
        _nutzer(fixture_dict("alarm_kanaele"), "premium", paused_at="2026-09-01T00:00:00Z"),
        _nutzer(fixture_dict("alarm_kanaele"), "premium", archived_at="2026-09-01T00:00:00Z"),
    ]
    for n in still:
        snap, gemeldet, quelle = _lauf(mit, "radar", n, "HIGH")
        assert gemeldet == 0 and quelle.aufrufe == 0 and snap.kanaele == []


# ---------------------------------------------------------------------------
# AC-17 -- Amtliche Warnung: Schalter-Vorrang und Kanalmenge
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fall,offiziell,legacy,soll", [
    ("a", {"enabled": True}, False, True),
    ("b", {"enabled": False}, True, False),
    ("c", {}, False, False),
    ("d", _WEG, _WEG, True),
])
def test_amtliche_warnung_schalter_vorrang_und_kanalmenge(mit, fall, offiziell, legacy, soll):
    """AC-17: aktueller Schalter (``official_warnings.enabled``) hat Vorrang vor dem Legacy-Feld,
    ein leerer Block zaehlt als nicht migriert; ausgeliefert wird an die aus ``alert_channels`` und
    Tarif aufgeloeste Kanalmenge auf allen vier Kanaelen."""
    for tier in ("premium", "standard"):
        n = _nutzer(fixture_dict("alarm_kanaele"), tier, official_warnings=offiziell,
                    official_alert_triggers_enabled=legacy, **_alle_kanaele())
        snap, gemeldet, quelle = _lauf(mit, "amtlich", n, "HIGH")
        if soll:
            assert gemeldet == 1, f"Fall {fall}: die Warnung muss ausgeliefert werden"
            _pruefen(snap, n, "amtlich", "HIGH")
        else:
            assert gemeldet == 0 and snap.kanaele == [], f"Fall {fall}: kein Versand erwartet"
            assert compare_alarm_kanaele(n.roh, tier, "HIGH")[0], "Vorbedingung: der Kanalsatz waere nicht leer"


# ---------------------------------------------------------------------------
# AC-18 -- Telegram-Kurzstil in allen drei Alarmpfaden
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("art", ARTEN)
def test_alarme_honorieren_telegram_kurzstil(mit, art):
    """AC-18: ``telegram_style = kurzform`` -> Telegram-Text identisch zum SMS-Text desselben
    Alarms; ``rich`` bzw. fehlender Schluessel -> ausfuehrlicher Text."""
    def _dc(stil):
        d = fixture_dict("alarm_kanaele")["display_config"]
        if stil is not _WEG:
            d["telegram_style"] = stil
        return d

    for stil, kurz in (("kurzform", True), ("rich", False), (_WEG, False)):
        for tier in ("premium", "standard"):
            n = _nutzer(fixture_dict("alarm_kanaele"), tier, display_config=_dc(stil), **_alle_kanaele())
            snap, gemeldet, _ = _lauf(mit, art, n, "HIGH")
            assert gemeldet == 1
            _pruefen(snap, n, art, "HIGH")
            tg = [s["body"] for s in snap.sendungen("telegram")]
            sms = [s["body"] for s in snap.sendungen("sms")]
            assert len(sms) == 1 and tg, f"{art}/{stil!r}: Telegram und SMS muessen ankommen"
            if kurz:
                assert tg == sms, f"{art}: Kurzstil -> Telegram-Text muss der SMS-Text sein"
            else:
                assert tg != sms and tg != [sms[0]], f"{art}/{stil!r}: ausfuehrlicher Telegram-Text erwartet"


# ---------------------------------------------------------------------------
# AC-19 -- Alarm-Mandantentrennung
# ---------------------------------------------------------------------------


def test_alarm_kette_trennt_zwei_nutzer(mit):
    """AC-19: zwei Nutzer mit verschiedenen ``alert_channels``, Schwellen und Tarifen -> jeden
    erreicht nur der eigene Alarm ueber die eigene Kanalmenge; Preset und Zaehler des einen
    wirken nicht auf den anderen."""
    a = _nutzer(fixture_dict("alarm_kanaele"), "standard",
                alert_channels={"email": True, "telegram": True, "sms": False, "premium_sms": False},
                alert_channel_thresholds={"telegram": "LOW"})
    b = _nutzer(fixture_dict("alarm_kanaele"), "premium",
                alert_channels={"email": False, "telegram": False, "sms": True, "premium_sms": True},
                alert_channel_thresholds={"sms": "HIGH", "premium_sms": "HIGH"})
    erwartet = {}
    for art in ARTEN:
        for n in (a, b):
            snap, gemeldet, _ = _lauf(mit, art, n, "HIGH")
            assert gemeldet == 1, f"{art}/{n.uid}"
            erwartet[(art, n.uid)] = _pruefen(snap, n, art, "HIGH")
        assert erwartet[(art, a.uid)] == {"email", "telegram"}
        assert erwartet[(art, b.uid)] == {"sms", "premium_sms"}
    for eigener, fremder in ((a, b), (b, a)):
        log = json.loads((get_data_dir(eigener.uid) / "alert_log.json").read_text())
        ids = {e.get("entity_id") for e in log["entries"]}
        assert ids == {eigener.roh["id"]}, f"Protokoll von {eigener.uid} enthaelt Fremdes: {ids}"
        for pfad in get_data_dir(eigener.uid).rglob("*"):
            if pfad.is_file():
                assert fremder.roh["id"] not in pfad.read_text(errors="ignore"), f"{pfad} traegt Daten des anderen Nutzers"


# ---------------------------------------------------------------------------
# AC-20 -- Ruhezeit und Sperrzeit
# ---------------------------------------------------------------------------


def _fenster_um_jetzt() -> tuple[str, str]:
    jetzt = datetime.now(timezone.utc).astimezone(WIEN)
    return ((jetzt - timedelta(hours=1)).strftime("%H:%M"), (jetzt + timedelta(hours=1)).strftime("%H:%M"))


def _protokolliert(uid: str, grund: str) -> bool:
    p = get_data_dir(uid) / "alert_log.json"
    return p.exists() and grund in p.read_text()


def test_ruhezeit_und_sperrzeit_unterdruecken_den_compare_alarm(mit):
    """AC-20: Alarm in der Ruhezeit bzw. in der Sperrzeit nach einem gesendeten Alarm bleibt aus und
    wird mit Grund protokolliert; ausserhalb beider Fenster liefert derselbe Ausloeser normal aus."""
    von, bis = _fenster_um_jetzt()
    ruhe = _nutzer(fixture_dict("alarm_kanaele"), "premium", alert_quiet_from=von, alert_quiet_to=bis, **_alle_kanaele())
    frei = _nutzer(fixture_dict("alarm_kanaele"), "premium", **_alle_kanaele())
    sperre = _nutzer(fixture_dict("alarm_kanaele"), "premium", **_alle_kanaele())

    snap, gemeldet, quelle = _lauf(mit, "abweichung", frei, "HIGH")
    assert gemeldet == 1
    _pruefen(snap, frei, "abweichung", "HIGH")

    snap, gemeldet, _ = _lauf(mit, "abweichung", ruhe, "HIGH")
    assert gemeldet == 0 and snap.kanaele == [], "Ruhezeit: keine Auslieferung"
    assert _protokolliert(ruhe.uid, "quiet_hours"), "Ruhezeit muss mit Grund im Protokoll stehen"

    erst, gemeldet, _ = _lauf(mit, "abweichung", sperre, "LOW")
    assert gemeldet == 1
    _pruefen(erst, sperre, "abweichung", "LOW")
    zweit, gemeldet, _ = _lauf(mit, "abweichung", sperre, "HIGH")  # groessere Aenderung, aber Sperrzeit
    assert gemeldet == 0 and zweit.kanaele == [], "Sperrzeit (60 min): keine zweite Auslieferung"
    assert _protokolliert(sperre.uid, "cooldown"), "Sperrzeit muss mit Grund im Protokoll stehen"


# ---------------------------------------------------------------------------
# AC-21 -- abgelaufener Ortsvergleich ist stumm (Briefing UND Alarme)
# ---------------------------------------------------------------------------


def _dateibestand(uid: str) -> dict[str, bytes]:
    wurzel = get_data_dir(uid)
    return {str(p.relative_to(wurzel)): p.read_bytes() for p in sorted(wurzel.rglob("*")) if p.is_file()}


def _wien(tag: date, stunde: int) -> datetime:
    return datetime(tag.year, tag.month, tag.day, stunde, 0, tzinfo=WIEN).astimezone(timezone.utc)


def test_abgelaufener_ortsvergleich_ist_fuer_briefing_und_alle_alarme_stumm(mit):
    """AC-21: ``end_date`` in der Vergangenheit -> weder die drei Alarmdienste noch der Briefing-Lauf
    liefern ueber irgendeinen Kanal aus, und es wird kein State verbraucht (Melde-Gedaechtnis, Sperrzeit,
    Tageszaehler); ``end_date`` heute bzw. fehlend alarmiert unveraendert. Zwei Nutzer: der abgelaufene
    beruehrt den aktiven nicht."""
    heute = datetime.now(timezone.utc).astimezone(WIEN).date()
    abgelaufen = _nutzer(fixture_dict("alarm_kanaele"), "premium",
                         end_date=(heute - timedelta(days=1)).isoformat(), **_alle_kanaele())
    aktiv_heute = _nutzer(fixture_dict("alarm_kanaele"), "premium",
                          end_date=heute.isoformat(), **_alle_kanaele())
    aktiv_offen = _nutzer(fixture_dict("alarm_kanaele"), "premium", end_date=_WEG, **_alle_kanaele())
    assert "end_date" not in aktiv_offen.roh

    vorher = _dateibestand(abgelaufen.uid)
    for art in ARTEN:
        snap, gemeldet, quelle = _lauf(mit, art, abgelaufen, "HIGH")
        assert gemeldet == 0 and snap.kanaele == [], (
            f"{art}: ein abgelaufener Ortsvergleich muss stumm sein, bedient wurde {snap.kanaele}")
    assert _dateibestand(abgelaufen.uid) == vorher, "ein stummer Ortsvergleich darf keinen State verbrauchen"
    stunde = int(abgelaufen.roh["morning_time"][:2])
    orte = {o.id: o for o in alle_orte(abgelaufen.uid)}
    from app.loader import compare_preset_to_dict, load_compare_presets

    def faellig(n: Nutzer) -> bool:
        preset = [compare_preset_to_dict(p) for p in load_compare_presets(n.uid) if p.id == n.roh["id"]]
        assert len(preset) == 1
        return bool(presets_due_for_hour(preset, {o.id: o for o in alle_orte(n.uid)}, _wien(heute, stunde)))

    assert not faellig(abgelaufen), "Briefing-Lauf: abgelaufen -> nicht faellig"
    assert faellig(aktiv_heute) and faellig(aktiv_offen), "Gegenprobe: Grenztag/unbegrenzt bleiben faellig"
    assert orte

    for kontrolle in (aktiv_heute, aktiv_offen):
        for art in ARTEN:
            snap, gemeldet, _ = _lauf(mit, art, kontrolle, "HIGH")
            assert gemeldet == 1, f"{art}: aktiver Ortsvergleich ({kontrolle.roh.get('end_date')!r}) muss alarmieren"
            _pruefen(snap, kontrolle, art, "HIGH")


# ---------------------------------------------------------------------------
# AC-22 -- Premium-SMS in jeder Alarmart, nur im Premium-Tarif
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("art", ARTEN)
def test_premium_sms_ist_alarmkanal_in_allen_drei_arten_nur_im_premium_tarif(mit, art):
    """AC-22: Premium-Tarif + ``alert_channels.premium_sms`` -> Premium-SMS in allen drei Alarmarten;
    im Tarif ``standard`` in keiner."""
    prem = _nutzer(fixture_dict("alarm_kanaele"), "premium", **_alle_kanaele())
    std = _nutzer(fixture_dict("alarm_kanaele"), "standard", **_alle_kanaele())
    snap_p, gemeldet, _ = _lauf(mit, art, prem, "HIGH")
    assert gemeldet == 1
    assert "premium_sms" in _pruefen(snap_p, prem, art, "HIGH")
    assert snap_p.empfaenger("premium_sms") == ["+490000000008"]
    snap_s, gemeldet, _ = _lauf(mit, art, std, "HIGH")
    assert gemeldet == 1
    assert "premium_sms" not in _pruefen(snap_s, std, art, "HIGH")
    assert snap_s.sendungen("premium_sms") == []
