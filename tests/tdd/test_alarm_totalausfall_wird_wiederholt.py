"""TDD RED -- Alarm-Erfolg heisst Zustellung; ein Totalausfall wird begrenzt
wiederholt statt als Erfolg gebucht (Issue #1405 Scheibe 1, ADR-0086).

SPEC: docs/specs/modules/fix_1405_s1_alarm_zustellung.md (AC-1 bis AC-20)

Gemessen wird dort, wo die Zusicherung WIRKT: am Draht (Einlieferungsversuche
und Annahmen je Kanal), am Alarm-Protokoll, an den Zustandsdateien und am
Backoff-Eintrag (``throttle_state.json``, Scope ``<scope>:retry``) -- nicht an
einem Zwischenwert.

Transport: die vier ECHTEN Ausgabe-Klassen laufen gegen steuerbare Draehte aus
``tests/helpers/kanal_fake_transporte.py`` -- lokale HTTP-Server fuer Telegram
und seven.io (SMS + Premium-SMS), eine skriptbare SMTP-Gegenstelle fuer
``EmailOutput`` (Begruendung im Helfer: STARTTLS-Pflicht, kein ``aiosmtpd``).
Kein ``Mock()``/``patch()``/``MagicMock``; ``mail_sink`` wird NIRGENDS benutzt.

Neue Bezeichner (``delivery_outcome``, ``attempted_channels``) werden nur zur
Laufzeit innerhalb der Tests gelesen (``getattr`` mit sichtbarem Platzhalter),
nie auf Modulebene importiert -- jeder AC scheitert einzeln an seinem
Verhalten, nicht die ganze Datei an einem Collection-Fehler.

Zeit: alle Mehrfach-Laeufe stehen unter einer gestellten Uhr (``freeze_time``)
ab ``_T0``; Trip, Wetter und Schnappschuesse werden INNERHALB jedes Laufs neu
gebaut, damit sie zur gestellten Uhr passen.

Mandantentrennung: jede Kennung ist ein frischer Nutzer, ``user_id`` wird
immer explizit uebergeben, nie ``"default"``.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from freezegun import freeze_time

from app.loader import get_data_dir, save_location, save_trip
from app.models import ChangeSeverity, GPXPoint, SegmentWeatherSummary, TripReportConfig, WeatherChange
from app.user import SavedLocation

from tests.helpers.alert_log_fixtures import (
    LAT, LON, compare_data_root, gust_alert_trip, read_log, reason_for_channel, weather,
)
from tests.helpers.compare_briefings import write_compare_briefings
from tests.helpers.kanal_fake_transporte import (
    KANAELE, KanalRig, kanal_auswahl, premium_profil_schreiben, wiederholungs_eintraege,
)

#: Feste gestellte Uhr fuer alle Mehrfach-Laeufe (12:00 Ortszeit in Tirol und
#: auf Korsika, 10:00 in Reykjavik) -- weit weg von Mitternacht und von den
#: Briefing-Slots der Fixtures.
_T0 = datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc)
_FEHLT = "<Feld fehlt am NotificationResult>"

# AC-14 (Doku-Teil: Restrisiko 48 Versuche/Dubletten in Spec und ADR-0086)
# steht in ``test_alarm_wiederholung_restrisiko_dokumentiert.py``.


# ════════════════════════════════ Bausteine ═════════════════════════════════


@pytest.fixture
def rig(monkeypatch):
    r = KanalRig(monkeypatch)
    yield r
    r.stoppen()


def _uid(tag: str) -> str:
    return f"tdd-1405-{tag}-{uuid.uuid4().hex[:6]}"


def _ausgang(result) -> str:
    """``delivery_outcome`` -- nur zur Laufzeit gelesen (s. Moduldoku)."""
    return getattr(result, "delivery_outcome", _FEHLT)


def _betreten(result):
    """``attempted_channels`` -- nur zur Laufzeit gelesen."""
    wert = getattr(result, "attempted_channels", _FEHLT)
    return sorted(wert) if isinstance(wert, list) else wert


def _caches_leeren() -> None:
    """Jeder Lauf beginnt mit leeren Prozess-Caches (Muster Alarm-Pruefstrecke)."""
    from output.channels.telegram import reset_telegram_rate_limit_for_tests
    from providers.thunder_window_cache import reset_thunder_window_cache_for_tests
    from services.radar_cache import reset_shared_radar_cache_for_tests
    from services.weather_cache import reset_shared_weather_cache_for_tests

    reset_shared_radar_cache_for_tests()
    reset_shared_weather_cache_for_tests()
    reset_thunder_window_cache_for_tests()
    reset_telegram_rate_limit_for_tests()


def _protokoll_zahl(uid: str) -> int:
    """Cockpit-Zahl samt Nicht-Zugestellt-Liste: alle Protokolleintraege."""
    log = read_log(uid)
    return len(log["entries"]) + len(log["not_delivered"])


def _tageszaehler_summe(uid: str) -> int:
    """Summe aller Zaehlerstaende in ``alert_daily_count.json`` (0 ohne Datei)."""
    pfad = get_data_dir(uid) / "alert_daily_count.json"
    if not pfad.exists():
        return 0

    def _summe(x) -> int:
        if isinstance(x, bool):
            return 0
        if isinstance(x, int):
            return x
        if isinstance(x, dict):
            return sum(_summe(v) for v in x.values())
        if isinstance(x, list):
            return sum(_summe(v) for v in x)
        return 0

    return _summe(json.loads(pfad.read_text()))


def _gemeldete_aenderungen(uid: str, entity_id: str) -> list[str]:
    """Melde-Gedaechtnis des Aenderungsalarms (``<metrik>:<abschnitt>``)."""
    from services.alert_state import AlertStateService

    return sorted(
        k for k in AlertStateService(uid).load(entity_id)
        if k.startswith("gust") and ":" in k
    )


def _sms_limit_ausschoepfen(uid: str, at: datetime, *, sms: int | None = None,
                            premium_sms: int | None = None) -> None:
    """Echter Tagesstand: Tarif premium (SMS 10, Premium-SMS 15) bis zum Rand."""
    from services import sms_daily_limit

    sms_daily_limit.seed_daily_usage(uid, sms, premium_sms, at)


def _sms_verbraucht(uid: str, at: datetime) -> int:
    from services import sms_daily_limit

    return sms_daily_limit.get_daily_usage(uid, at)["sms"]["used"]


# ───────────────────── Versandpfade des NotificationService ─────────────────


def _warnung(hazard: str = "wind", jetzt: datetime | None = None):
    from services.official_alerts.models import OfficialAlert

    jetzt = jetzt or datetime.now(timezone.utc)
    return OfficialAlert(
        source="tdd-1405", hazard=hazard, level=3, label="Sturmwarnung",
        region_label="Testregion-1405",
        valid_from=jetzt - timedelta(hours=1), valid_to=jetzt + timedelta(hours=12),
    )


def _dienst(rig: KanalRig, uid: str):
    from services.notification_service import NotificationService

    jetzt = datetime.now(timezone.utc)
    premium_profil_schreiben(uid, reply_at=jetzt - timedelta(minutes=5))
    return NotificationService(rig.settings(premium_reply_at=jetzt - timedelta(minutes=5)), uid)


def _aenderung(segment_id: str = "1") -> WeatherChange:
    return WeatherChange(
        metric="temp_max_c", old_value=18.0, new_value=26.0, delta=8.0,
        threshold=5.0, severity=ChangeSeverity.MODERATE, direction="increase",
        segment_id=segment_id,
    )


def _versende(pfad: str, dienst, kanaele: set[str], *, orte: int = 1):
    """Ein Versand ueber einen der drei Versandpfade -- dieselbe Lage."""
    _caches_leeren()
    if pfad == "send_official_alert":
        return dienst.send_official_alert(
            gust_alert_trip("trip-1405"), [(_warnung(), ["1"])], set(kanaele),
        )
    if pfad == "_dispatch_alert_message":
        # Einstieg des Ortsvergleich-Aenderungsalarms; Telegram faechert je Ort auf.
        entities = [
            (f"Ort {i + 1}", [GPXPoint(lat=46.0 + i * 0.3, lon=7.0 + i * 0.3, elevation_m=500.0)],
             [_aenderung()])
            for i in range(orte)
        ]
        return dienst.send_multi_location_deviation_alert(entities, set(kanaele))
    if pfad == "send_multi_location_official_alert":
        ort = SavedLocation(id="loc-a", name="Vergleichsort", lat=LAT, lon=LON, elevation_m=1000)
        return dienst.send_multi_location_official_alert(
            "Vergleich 1405", [ort], [(_warnung(), ["loc-a"])], set(kanaele),
        )
    raise ValueError(pfad)


_VERSANDPFADE = ["send_official_alert", "_dispatch_alert_message", "send_multi_location_official_alert"]


# ══════════════════════════ Positivkontrolle (Rig) ══════════════════════════


@pytest.mark.parametrize("pfad", _VERSANDPFADE)
def test_kontrolle_alle_draehte_offen_jeder_kanal_stellt_genau_einmal_zu(rig, pfad):
    """Kontrolle zu AC-1 bis AC-6 (und AC-20): GIVEN alle vier Draehte nehmen an / WHEN ein Alarm
    ueber einen der drei Versandpfade an alle vier Kanaele geht / THEN ist
    ``sent`` wahr und jeder Draht hat genau eine Nachricht angenommen.

    Ohne diese Kontrolle bewiese kein roter Test etwas: ein Kanal, der schon an
    der Konfiguration scheitert, saehe aus wie ein Transportfehler."""
    uid = _uid("kontrolle")
    result = _versende(pfad, _dienst(rig, uid), set(KANAELE))
    assert result.sent is True, f"Kontrolle: Versand gescheitert: {result!r} / {rig!r}"
    for kanal in KANAELE:
        assert rig.anzahl_angenommen(kanal) == 1, (
            f"Kontrolle: Kanal {kanal} muss genau einmal angenommen sein: {rig!r}"
        )
    assert sorted(result.delivered_channels) == sorted(KANAELE), result


# ════════════════════════ A. Was "gesendet" bedeutet ════════════════════════


@pytest.mark.parametrize("kanal", KANAELE)
def test_ac1_einziger_kanal_scheitert_ergibt_nicht_gesendet(rig, kanal):
    """AC-1: GIVEN ein Alarm, dessen einziger konfigurierter Kanal (je Fall
    E-Mail, Telegram, SMS, Premium-SMS) am Transport scheitert / WHEN der Alarm
    versendet wird / THEN ist ``sent`` falsch, der Kanal steht nicht unter den
    zugestellten Kanaelen und das Ergebnis lautet ``transport_failed``."""
    uid = _uid(f"ac1-{kanal}")
    rig.modus[kanal] = "fehler"
    result = _versende("send_official_alert", _dienst(rig, uid), {kanal})

    assert rig.anzahl_versuche(kanal) == 1, (
        f"Voraussetzung: der {kanal}-Draht muss erreicht worden sein (sonst kein "
        f"Transportfehler, sondern Konfigurationsfehler): {rig!r}"
    )
    assert result.sent is False, (
        f"AC-1: sent ist True trotz Totalausfall des einzigen Kanals {kanal}: {result!r}"
    )
    assert kanal not in result.delivered_channels, result
    assert _ausgang(result) == "transport_failed", (
        f"AC-1: Ergebnis muss 'transport_failed' lauten, ist {_ausgang(result)!r}"
    )


def test_ac2_teilerfolg_gilt_als_zugestellt_fehlkanal_bleibt_sichtbar(rig):
    """AC-2: GIVEN E-Mail stellt zu, Telegram scheitert / WHEN der Alarm
    versendet wird / THEN ist ``sent`` wahr, das Ergebnis ``delivered`` und
    ``failed_channels == ["telegram"]``."""
    uid = _uid("ac2")
    rig.modus["telegram"] = "fehler"
    result = _versende("send_official_alert", _dienst(rig, uid), {"email", "telegram"})

    assert rig.anzahl_angenommen("email") == 1 and rig.anzahl_versuche("telegram") == 1, rig
    assert result.sent is True, f"AC-2: Teilerfolg muss als gesendet gelten: {result!r}"
    assert result.failed_channels == ["telegram"], result
    assert _ausgang(result) == "delivered", (
        f"AC-2: Teilerfolg muss 'delivered' lauten, ist {_ausgang(result)!r}"
    )


def test_ac3_reine_sperre_ergibt_blocked_only(rig):
    """AC-3: GIVEN der einzige Kanal SMS ist durch das ausgeschoepfte
    Tageslimit gesperrt (echter ``sms_daily_limit``-Stand) / WHEN der Alarm
    versendet wird / THEN lautet das Ergebnis ``blocked_only``."""
    uid = _uid("ac3")
    dienst = _dienst(rig, uid)
    _sms_limit_ausschoepfen(uid, datetime.now(timezone.utc), sms=10)
    result = _versende("send_official_alert", dienst, {"sms"})

    assert rig.anzahl_versuche("sms") == 0, f"Voraussetzung: gesperrt heisst kein Draht: {rig!r}"
    assert "sms" in result.blocked_reason_codes, f"Voraussetzung: Sperr-Code fehlt: {result!r}"
    assert result.sent is False, result
    assert _ausgang(result) == "blocked_only", (
        f"AC-3: reine Sperre muss 'blocked_only' lauten, ist {_ausgang(result)!r}"
    )


def test_ac4_mischfall_sperre_plus_transportfehler_ist_transport_failed(rig):
    """AC-4: GIVEN SMS ist gesperrt (Tageslimit) UND E-Mail scheitert am
    Transport / WHEN der Alarm versendet wird / THEN lautet das Ergebnis
    ``transport_failed`` (nicht ``blocked_only``)."""
    uid = _uid("ac4")
    dienst = _dienst(rig, uid)
    _sms_limit_ausschoepfen(uid, datetime.now(timezone.utc), sms=10)
    rig.modus["email"] = "fehler"
    result = _versende("send_official_alert", dienst, {"sms", "email"})

    assert rig.anzahl_versuche("email") == 1 and rig.anzahl_versuche("sms") == 0, rig
    assert result.sent is False, f"AC-4: sent ist True, obwohl nichts zugestellt wurde: {result!r}"
    assert _ausgang(result) == "transport_failed", (
        f"AC-4: Mischfall muss 'transport_failed' lauten, ist {_ausgang(result)!r}"
    )


@pytest.mark.parametrize("fall", ["transportfehler", "tageslimit"])
def test_ac5_premium_sms_transportfehler_ist_keine_sperre(rig, fall):
    """AC-5: GIVEN Premium-SMS ist der einzige Kanal / WHEN der Transport
    scheitert bzw. das Tageslimit sperrt / THEN ist der Transportfehler
    ``transport_failed`` (Kanal in ``failed_channels``), die echte Sperre mit
    Sperr-Code dagegen ``blocked_only`` (Kanal NICHT in ``failed_channels``)."""
    uid = _uid(f"ac5-{fall}")
    dienst = _dienst(rig, uid)
    if fall == "transportfehler":
        rig.modus["premium_sms"] = "fehler"
    else:
        _sms_limit_ausschoepfen(uid, datetime.now(timezone.utc), premium_sms=15)
    result = _versende("send_official_alert", dienst, {"premium_sms"})

    assert result.sent is False, f"AC-5 ({fall}): nichts zugestellt, sent ist True: {result!r}"
    if fall == "transportfehler":
        assert rig.anzahl_versuche("premium_sms") == 1, rig
        assert "premium_sms" not in result.blocked_reason_codes, (
            f"Voraussetzung: Transportfehler darf keinen Sperr-Code tragen: {result!r}"
        )
        assert "premium_sms" in result.failed_channels, result
        assert _ausgang(result) == "transport_failed", (
            f"AC-5: Premium-SMS-Transportfehler muss 'transport_failed' sein, "
            f"ist {_ausgang(result)!r}"
        )
    else:
        assert rig.anzahl_versuche("premium_sms") == 0, rig
        assert "premium_sms" in result.blocked_reason_codes, result
        assert "premium_sms" not in result.failed_channels, (
            f"AC-5: echte Sperre ist kein Transportfehler: {result!r}"
        )
        assert _ausgang(result) == "blocked_only", (
            f"AC-5: Premium-SMS-Tageslimit muss 'blocked_only' sein, ist {_ausgang(result)!r}"
        )


def test_ac6_eine_telegram_blase_zugestellt_kanal_gilt_als_zugestellt(rig):
    """AC-6 (Teilzustellung): GIVEN ein Telegram-Alarm in zwei Sprechblasen,
    Blase 2 scheitert / WHEN der Alarm versendet wird / THEN gilt der Kanal als
    zugestellt (``delivered``, ``sent`` wahr) und ``telegram_fully_sent`` ist
    falsch."""
    uid = _uid("ac6a")
    rig.telegram_fehler_bei = {2}
    result = _versende("_dispatch_alert_message", _dienst(rig, uid), {"telegram"}, orte=2)

    assert rig.anzahl_versuche("telegram") >= 2 and rig.anzahl_angenommen("telegram") >= 1, rig
    assert result.telegram_fully_sent is False, result
    assert result.sent is True, result
    assert _ausgang(result) == "delivered", (
        f"AC-6: eine zugestellte Blase reicht fuer 'delivered', ist {_ausgang(result)!r}"
    )


def test_ac6_alle_telegram_blasen_scheitern_ist_transportfehler(rig):
    """AC-6 (Totalausfall): GIVEN alle Sprechblasen scheitern / WHEN der Alarm
    versendet wird / THEN gilt Telegram als Transportfehler: ``sent`` falsch,
    ``transport_failed``."""
    uid = _uid("ac6b")
    rig.modus["telegram"] = "fehler"
    result = _versende("_dispatch_alert_message", _dienst(rig, uid), {"telegram"}, orte=2)

    assert rig.anzahl_versuche("telegram") >= 2 and rig.anzahl_angenommen("telegram") == 0, rig
    assert result.sent is False, (
        f"AC-6: sent ist True, obwohl keine einzige Telegram-Blase ankam: {result!r}"
    )
    assert _ausgang(result) == "transport_failed", _ausgang(result)


def test_ac7_kein_kanal_bucht_nichts_und_setzt_keinen_backoff(rig):
    """AC-7 (Verhalten, bleibt gruen): GIVEN ein Trip, dessen einziger
    wirksamer Kanal (E-Mail) nicht konfiguriert ist / WHEN die Alarmpruefung
    laeuft / THEN keine Buchung, keine Sperrzeit, kein Backoff, kein Draht."""
    from services.throttle_store import ThrottleStore
    from services.trip_alert import TripAlertService

    uid = _uid("ac7")
    premium_profil_schreiben(uid, reply_at=_T0 - timedelta(minutes=5))
    settings = rig.settings(premium_reply_at=_T0).model_copy(update={
        "smtp_host": None, "smtp_user": None, "smtp_pass": None,
    })
    assert settings.can_send_email() is False
    _caches_leeren()
    with freeze_time(_T0):
        trip = gust_alert_trip("trip-ac7", alert_channels=kanal_auswahl("email"))
        ergebnis = TripAlertService(settings=settings, throttle_hours=0, user_id=uid).check_and_send_alerts(
            trip, [weather(1, gust_max_kmh=20.0)], fresh_weather=[weather(1, gust_max_kmh=60.0)],
        )
    assert ergebnis is False
    assert rig.alle_versuche() == 0, rig
    assert ThrottleStore(uid).last_sent("trip", "trip-ac7") is None
    assert _gemeldete_aenderungen(uid, "trip-ac7") == []
    assert wiederholungs_eintraege(uid) == {}, "AC-7: kein Kanal => kein Backoff"


def test_ac7_kein_kanal_ergibt_no_channel(rig):
    """AC-7 (Ergebniswert): GIVEN kein wirksamer Kanal (E-Mail unkonfiguriert,
    nichts gesperrt) / WHEN der Alarm versendet wird / THEN lautet das
    Ergebnis ``no_channel`` und nichts wurde betreten."""
    from services.notification_service import NotificationService

    uid = _uid("ac7b")
    settings = rig.settings().model_copy(update={"smtp_host": None, "smtp_user": None, "smtp_pass": None})
    result = NotificationService(settings, uid).send_official_alert(
        gust_alert_trip("trip-ac7b"), [(_warnung(), ["1"])], {"email"},
    )
    assert result.sent is False and rig.alle_versuche() == 0
    assert _ausgang(result) == "no_channel", (
        f"AC-7: ohne wirksamen Kanal muss das Ergebnis 'no_channel' lauten, ist {_ausgang(result)!r}"
    )
    assert _betreten(result) == [], _betreten(result)


# ═════════════════════ Alarm-Aufrufer (sechs Pfade) ═════════════════════════


_PRESET = "cp-1405"
_LOC_B = (LAT + 0.5, LON + 0.5)


class _Pfad:
    """Ein Alarm-Aufrufer mit stellbarer Uhr. ``lauf(at, ereignis)`` baut alle
    zeitabhaengigen Daten unter der gestellten Uhr neu und ruft den ECHTEN
    Einstieg auf; Kontinuitaet kommt ausschliesslich vom Datentraeger."""

    name = ""

    def __init__(self, rig: KanalRig, uid: str, kanaele: tuple[str, ...], *,
                 smtp_host: str = "smtp.rig-1405.test", entity_id: str = "trip-1405") -> None:
        self.rig, self.uid, self.kanaele = rig, uid, kanaele
        self.entity_id = entity_id
        premium_profil_schreiben(uid, reply_at=_T0 - timedelta(minutes=5))
        self.settings = rig.settings(smtp_host=smtp_host, premium_reply_at=_T0 - timedelta(minutes=5))
        with freeze_time(_T0):
            self.aufbauen()

    def aufbauen(self) -> None:
        pass

    def lauf(self, at: datetime, ereignis: str = "A"):
        _caches_leeren()
        with freeze_time(at):
            return self._lauf(ereignis)

    def _lauf(self, ereignis: str):  # pragma: no cover - abstrakt
        raise NotImplementedError


class _TripAenderung(_Pfad):
    """``trip_alert.check_and_send_alerts`` -- Ereignis A: Boee auf Abschnitt 1;
    Ereignis B: zusaetzlich Boee auf Abschnitt 2 (anderer Abschnitt)."""

    name = "trip_aenderung"

    def _lauf(self, ereignis: str, *, normal: bool = False):
        from services.trip_alert import TripAlertService

        trip = gust_alert_trip(self.entity_id, alert_channels=kanal_auswahl(*self.kanaele))
        cached = [weather(1, gust_max_kmh=20.0), weather(2, gust_max_kmh=20.0)]
        fresh = [
            weather(1, gust_max_kmh=20.0 if normal else 60.0),
            weather(2, gust_max_kmh=60.0 if ereignis == "B" else 20.0),
        ]
        return TripAlertService(
            settings=self.settings, throttle_hours=0, user_id=self.uid,
        ).check_and_send_alerts(trip, cached, fresh_weather=fresh)

    def lauf_ohne_abweichung(self, at: datetime):
        _caches_leeren()
        with freeze_time(at):
            return self._lauf("A", normal=True)


class _TripRadar(_Pfad):
    """``trip_alert.check_radar_alerts`` -- Ereignis A: Regen in 12 Min;
    Ereignis B: anderes Zeitfenster (Regen in 50 Min). Der Nowcast kennt nur
    EINE Gefahrenklasse (``wet``, ``resolve_hazard_class``) -- das Ereignis
    unterscheidet sich deshalb am Zeitfenster."""

    name = "trip_radar"

    def _lauf(self, ereignis: str):
        from services.trip_alert import TripAlertService
        from tests.tdd.test_952_onset_alert_fidelity import (
            _GuaranteedWetRadar, _trip_with_active_segment,
        )

        config = TripReportConfig(trip_id=self.entity_id, alert_on_changes=True, send_email=True)
        trip = _trip_with_active_segment(self.entity_id, config)
        trip.alert_channels = kanal_auswahl(*self.kanaele)
        save_trip(trip, user_id=self.uid)
        radar = _GuaranteedWetRadar(onset_minutes=12 if ereignis == "A" else 50)
        return TripAlertService(
            settings=self.settings, throttle_hours=0, user_id=self.uid, radar_service=radar,
        ).check_radar_alerts()


class _TripAmtlich(_Pfad):
    """``trip_alert`` amtlich: ``check_official_alert_triggers`` +
    ``_send_official_alert_only`` (wie ``check_all_trips``). Ereignis A:
    Sturmwarnung; Ereignis B: Hitzewarnung (andere Meldung)."""

    name = "trip_amtlich"

    def aufbauen(self) -> None:
        from tests.helpers.briefing_imminent_fixtures import write_trip

        pfad = write_trip(self.uid, self.entity_id, morgen_stunde=3, abend_stunde=21)
        daten = json.loads(pfad.read_text())
        daten["alert_channels"] = kanal_auswahl(*self.kanaele)
        pfad.write_text(json.dumps(daten))

    def _lauf(self, ereignis: str):
        from services.trip_alert import TripAlertService
        from tests.helpers.official_alert_gate_fixtures import (
            StufenWarnquelle, load_trip_obj, nur_diese_warnquelle, schnappschuss_speichern,
        )

        schnappschuss_speichern(self.uid, self.entity_id)
        quelle = StufenWarnquelle(hazard="wind" if ereignis == "A" else "extreme_heat",
                                  region_label=f"Testregion-1405-{ereignis}")
        quelle.level = 3
        with nur_diese_warnquelle(quelle):
            dienst = TripAlertService(settings=self.settings, throttle_hours=2, user_id=self.uid)
            trip = load_trip_obj(self.uid, self.entity_id)
            meldungen = dienst.check_official_alert_triggers(trip)
            if not meldungen:
                return False
            return dienst._send_official_alert_only(trip, meldungen)


class _VergleichBasis(_Pfad):
    """Ortsvergleich mit zwei Orten. Ereignis A betrifft Ort A, Ereignis B
    zusaetzlich Ort B (anderer Ort)."""

    def aufbauen(self) -> None:
        from services.compare_weather_snapshot import CompareWeatherSnapshotService

        save_location(SavedLocation(id="loc-a", name="Ort A", lat=LAT, lon=LON, elevation_m=1000),
                      user_id=self.uid)
        save_location(SavedLocation(id="loc-b", name="Ort B", lat=_LOC_B[0], lon=_LOC_B[1],
                                    elevation_m=1000), user_id=self.uid)
        write_compare_briefings(compare_data_root() / self.uid, [{
            "id": self.entity_id, "name": "Vergleich 1405", "user_id": self.uid,
            "location_ids": ["loc-a", "loc-b"], "schedule": "daily", "weekday": 4,
            "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
            "empfaenger": [], "created_at": "2026-03-01T00:00:00Z",
            "radar_alert_enabled": True, "alert_cooldown_minutes": 60,
            "alert_channels": kanal_auswahl(*self.kanaele),
        }])
        snap = CompareWeatherSnapshotService(user_id=self.uid)
        snap.save(self.entity_id, "loc-a", _ortswetter("loc-a", gust_max_kmh=20.0))
        snap.save(self.entity_id, "loc-b", _ortswetter("loc-b", gust_max_kmh=20.0))


def _ortswetter(loc_id: str, **summary):
    from services.point_weather import PointWeatherData

    lat, lon = (LAT, LON) if loc_id == "loc-a" else _LOC_B
    return PointWeatherData(
        id=loc_id, name=loc_id, lat=lat, lon=lon, timeseries=None,
        aggregated=SegmentWeatherSummary(**summary),
        fetched_at=datetime.now(timezone.utc), provider="tdd-1405",
    )


class _OrtsQuelle:
    """Deterministische ``LocationWeatherSource`` je Ort (Konfigurations-Naht)."""

    def __init__(self, boeen: dict[str, float]) -> None:
        self._boeen = boeen

    def fetch(self, point_id, lat, lon, start_hour=None, end_hour=None,
              elevation_m=None, user_id=None):
        return _ortswetter(point_id, gust_max_kmh=self._boeen.get(point_id, 20.0))


class _VergleichAenderung(_VergleichBasis):
    name = "compare_alert"

    def _lauf(self, ereignis: str):
        from services.compare_alert import CompareAlertService

        boeen = {"loc-a": 60.0, "loc-b": 60.0 if ereignis == "B" else 20.0}
        return CompareAlertService(
            settings=self.settings, user_id=self.uid, weather_source=_OrtsQuelle(boeen),
        ).check_all_compare_presets()


class _VergleichRadar(_VergleichBasis):
    name = "compare_radar_alert"

    def _lauf(self, ereignis: str):
        from providers.brightsky import RadarFrame
        from services.compare_radar_alert import CompareRadarAlertService
        from services.radar_service import RadarNowcastService

        def _frames(lat, lon):
            jetzt = datetime.now(timezone.utc)
            nass = abs(lat - LAT) < 0.1 or (ereignis == "B" and abs(lat - _LOC_B[0]) < 0.1)
            rate = (5.0, 8.0) if nass else (0.0, 0.0)
            return [RadarFrame(timestamp=jetzt + timedelta(minutes=5), precip_mm_h=rate[0]),
                    RadarFrame(timestamp=jetzt + timedelta(minutes=15), precip_mm_h=rate[1])]

        return CompareRadarAlertService(
            settings=self.settings, user_id=self.uid,
            radar_service=RadarNowcastService(frame_source=_frames),
        ).check_all_compare_presets()


class _AlleOrteWarnquelle:
    def __init__(self, alerts) -> None:
        self._alerts = alerts

    @property
    def name(self) -> str:
        return "tdd-1405-quelle"

    def covers(self, lat, lon) -> bool:
        return True

    def fetch(self, lat, lon, **kwargs):
        return list(self._alerts)


class _VergleichAmtlich(_VergleichBasis):
    name = "compare_official_alert"

    def _lauf(self, ereignis: str):
        from services.compare_official_alert import CompareOfficialAlertService
        from tests.helpers.briefing_imminent_fixtures import nur_diese_warnquelle

        warnung = _warnung("wind" if ereignis == "A" else "extreme_heat",
                           jetzt=datetime.now(timezone.utc))
        with nur_diese_warnquelle(_AlleOrteWarnquelle([warnung])):
            return CompareOfficialAlertService(
                settings=self.settings, user_id=self.uid,
            ).check_all_compare_presets()


_AUFRUFER = {
    "trip_aenderung": _TripAenderung,
    "trip_radar": _TripRadar,
    "trip_amtlich": _TripAmtlich,
    "compare_alert": _VergleichAenderung,
    "compare_radar_alert": _VergleichRadar,
    "compare_official_alert": _VergleichAmtlich,
}

#: AC-19: sechs Aufrufer + Sammelpfad ``send_multi_location_official_alert``.
#: Der Sammelpfad bucht nichts selbst (sein einziger Aufrufer ist
#: ``compare_official_alert``); er wird ueber sein Ergebnis gemessen.
_SIEBEN_PFADE = list(_AUFRUFER) + ["send_multi_location_official_alert"]


@pytest.mark.parametrize("pfad", list(_AUFRUFER))
def test_kontrolle_jeder_aufrufer_stellt_bei_offenen_draehten_genau_einmal_zu(rig, pfad):
    """Kontrolle zu AC-8 und AC-19: GIVEN offene Draehte / WHEN jeder der sechs
    Aufrufer einmal laeuft / THEN genau eine angenommene E-Mail -- und ein
    zweiter Lauf mit gleicher Lage versendet nichts mehr (Buchung wirkt)."""
    p = _AUFRUFER[pfad](rig, _uid(f"k-{pfad}"), ("email",))
    p.lauf(_T0)
    assert rig.anzahl_angenommen("email") == 1, f"Kontrolle {pfad}: kein Versand: {rig!r}"
    p.lauf(_T0 + timedelta(minutes=31))
    assert rig.anzahl_versuche("email") == 1, f"Kontrolle {pfad}: Wiederholung trotz Buchung: {rig!r}"


@pytest.mark.parametrize("pfad", list(_AUFRUFER))
def test_kontrolle_ereignis_b_loest_bei_jedem_aufrufer_allein_aus(rig, pfad):
    """Kontrolle zu AC-12 und AC-19 (Ereignis-Wechsel): GIVEN offene Draehte und ein frischer Nutzer /
    WHEN nur Ereignis B auftritt / THEN geht genau ein Alarm raus -- sonst
    bewiese der Ereignis-Wechsel-Test (AC-12/AC-19) nach dem Fix nichts."""
    p = _AUFRUFER[pfad](rig, _uid(f"kb-{pfad}"), ("email",))
    p.lauf(_T0 + timedelta(minutes=5), ereignis="B")
    assert rig.anzahl_angenommen("email") == 1, f"Kontrolle {pfad}: Ereignis B loest nicht aus: {rig!r}"


# ═════════════════ B. Buchung nach dem Versand (Trip-Aenderung) ═════════════


def test_ac8_teilerfolg_wird_gebucht_und_nicht_wiederholt(rig):
    """AC-8: GIVEN E-Mail stellt zu, Telegram scheitert (Teilerfolg) / WHEN der
    Aufrufer nachbehandelt und ein zweiter Lauf mit gleicher Lage folgt / THEN
    ist gebucht (Sperrzeit, Tageskontingent) und es geht nichts erneut raus --
    auch nicht auf dem gescheiterten Kanal."""
    from services.throttle_store import ThrottleStore

    uid = _uid("ac8")
    rig.modus["telegram"] = "fehler"
    p = _TripAenderung(rig, uid, ("email", "telegram"))
    assert p.lauf(_T0) is True
    assert rig.anzahl_angenommen("email") == 1 and rig.anzahl_versuche("telegram") == 1, rig
    assert ThrottleStore(uid).last_sent("trip", p.entity_id) is not None
    assert _tageszaehler_summe(uid) == 1
    assert _gemeldete_aenderungen(uid, p.entity_id), "AC-8: Melde-Gedaechtnis nicht gebucht"
    rig.modus["telegram"] = "ok"
    p.lauf(_T0 + timedelta(minutes=31))
    assert rig.anzahl_versuche("email") == 1 and rig.anzahl_versuche("telegram") == 1, (
        f"AC-8: Teilerfolg darf nicht wiederholt werden: {rig!r}"
    )
    assert wiederholungs_eintraege(uid) == {}, "AC-8: Teilerfolg setzt keinen Backoff"


def test_ac9_reine_sperre_bucht_terminal_drei_laeufe_ein_zustand(rig):
    """AC-9: GIVEN der einzige Kanal SMS ist per Tageslimit gesperrt / WHEN drei
    Laeufe nacheinander folgen / THEN wird beim ersten terminal gebucht (Zustand,
    Sperrzeit), es entsteht EIN Protokolleintrag und kein weiterer Versuch."""
    from services.throttle_store import ThrottleStore

    uid = _uid("ac9")
    p = _TripAenderung(rig, uid, ("sms",))
    _sms_limit_ausschoepfen(uid, _T0, sms=10)
    for minuten in (0, 31, 62):
        p.lauf(_T0 + timedelta(minutes=minuten))
    assert rig.anzahl_versuche("sms") == 0, rig
    assert ThrottleStore(uid).last_sent("trip", p.entity_id) is not None, (
        "AC-9: reine Sperre muss terminal gebucht werden (Sperrzeit fehlt)"
    )
    assert _protokoll_zahl(uid) == 1, (
        f"AC-9: drei Laeufe gegen dieselbe Sperre duerfen nur EINEN Protokolleintrag "
        f"erzeugen, sind {_protokoll_zahl(uid)}"
    )
    assert wiederholungs_eintraege(uid) == {}, "AC-9: Sperre ist terminal, kein Backoff"


def test_ac10_totalausfall_bucht_nichts_setzt_backoff_und_versucht_erneut(rig):
    """AC-10: GIVEN ein Totalausfall (einziger Kanal E-Mail scheitert) / WHEN
    der Aufrufer nachbehandelt / THEN ist nichts gebucht (kein Zustand, keine
    Sperrzeit, kein Tageskontingent), der Backoff ist gesetzt, und der Lauf
    nach Ablauf (+31 Min) versucht den Alarm erneut."""
    from services.throttle_store import ThrottleStore

    uid = _uid("ac10")
    rig.modus["email"] = "fehler"
    p = _TripAenderung(rig, uid, ("email",))
    ergebnis = p.lauf(_T0)
    assert rig.anzahl_versuche("email") == 1, rig
    assert ergebnis is False, "AC-10: Aufrufer meldet Erfolg trotz Totalausfall"
    assert _gemeldete_aenderungen(uid, p.entity_id) == [], (
        f"AC-10: Alarm-Zustand wurde trotz Totalausfall gebucht: "
        f"{_gemeldete_aenderungen(uid, p.entity_id)!r}"
    )
    assert ThrottleStore(uid).last_sent("trip", p.entity_id) is None, "AC-10: Sperrzeit gebucht"
    assert _tageszaehler_summe(uid) == 0, "AC-10: Tageskontingent trotz Totalausfall verbraucht"
    assert wiederholungs_eintraege(uid), "AC-10: kein Backoff-Eintrag nach Totalausfall"
    p.lauf(_T0 + timedelta(minutes=31))
    assert rig.anzahl_versuche("email") == 2, (
        f"AC-10: nach Ablauf des Backoffs muss der Alarm erneut versucht werden: {rig!r}"
    )


# ═══════════════════════ C. Begrenzung der Wiederholung ═════════════════════


def test_ac11_dauerausfall_hoechstens_ein_versuch_je_30_minuten(rig):
    """AC-11 (30 Minuten): GIVEN Dauer-Transportausfall und anhaltende
    Abweichung / WHEN die Pruefung im 5-Minuten-Takt laeuft / THEN in den
    ersten 30 Minuten genau 1 Versuch und 1 Protokolleintrag, nach Ablauf
    (+35 Min) der naechste Versuch."""
    uid = _uid("ac11")
    rig.modus["email"] = "fehler"
    p = _TripAenderung(rig, uid, ("email",))
    for i in range(6):  # 0, 5, ..., 25 Minuten
        p.lauf(_T0 + timedelta(minutes=5 * i))
    assert rig.anzahl_versuche("email") == 1, f"AC-11: mehr als 1 Versuch in 30 Min: {rig!r}"
    assert _protokoll_zahl(uid) == 1, f"AC-11: {_protokoll_zahl(uid)} Protokolleintraege in 30 Min"
    p.lauf(_T0 + timedelta(minutes=35))
    assert rig.anzahl_versuche("email") == 2, (
        f"AC-11: nach 30 Minuten muss der naechste Versuch kommen: {rig!r}"
    )


@pytest.mark.timeout(300)
def test_ac11_dauerausfall_ueber_24_stunden_zwischen_2_und_48_versuchen(rig):
    """AC-11 (24 Stunden): GIVEN Dauer-Transportausfall und anhaltende
    Abweichung / WHEN die Pruefung 24 Stunden lang im 15-Minuten-Takt laeuft
    (96 Laeufe) / THEN mindestens 2 und hoechstens 48 Versuche und hoechstens
    48 Protokolleintraege -- weder Verlust noch Sturm."""
    uid2 = _uid("ac11-tag")
    rig.modus["email"] = "fehler"
    p2 = _TripAenderung(rig, uid2, ("email",))
    for i in range(96):  # 24 h im 15-Minuten-Takt
        p2.lauf(_T0 + timedelta(minutes=15 * i))
    versuche = rig.anzahl_versuche("email")
    assert 2 <= versuche <= 48, f"AC-11: 24-h-Dauerausfall ergab {versuche} Versuche (Soll 2..48)"
    assert _protokoll_zahl(uid2) <= 48, f"AC-11: {_protokoll_zahl(uid2)} Protokolleintraege in 24 h"


def test_ac12_neues_ereignis_wird_vom_backoff_eines_alten_nicht_blockiert(rig):
    """AC-12: GIVEN fuer Ereignis A (Abschnitt 1) laeuft ein Backoff / WHEN im
    naechsten Lauf ein neues Ereignis B (Abschnitt 2) hinzukommt und die
    Transporte wieder gehen / THEN wird sofort versendet und gebucht."""
    uid = _uid("ac12")
    rig.modus["email"] = "fehler"
    p = _TripAenderung(rig, uid, ("email",))
    p.lauf(_T0)
    assert wiederholungs_eintraege(uid), "AC-12 Voraussetzung: Backoff fuer Ereignis A fehlt"
    rig.modus["email"] = "ok"
    assert p.lauf(_T0 + timedelta(minutes=5), ereignis="B") is True, (
        f"AC-12: Ereignis B wurde vom Backoff von A blockiert: {rig!r}"
    )
    assert rig.anzahl_angenommen("email") == 1, rig


def test_ac13_nach_reparatur_zugestellt_gebucht_und_backoff_geloescht(rig):
    """AC-13: GIVEN der Draht faellt aus und wird repariert / WHEN der Lauf nach
    Ablauf (+31 Min) erneut versucht / THEN ``delivered``, normal gebucht,
    Backoff geloescht -- und ein Lauf +62 Min versendet nichts mehr."""
    from services.throttle_store import ThrottleStore

    uid = _uid("ac13")
    rig.modus["email"] = "fehler"
    p = _TripAenderung(rig, uid, ("email",))
    p.lauf(_T0)
    rig.modus["email"] = "ok"
    assert p.lauf(_T0 + timedelta(minutes=31)) is True, (
        f"AC-13: nach Reparatur kein erneuter Versand: {rig!r}"
    )
    assert rig.anzahl_angenommen("email") == 1
    assert ThrottleStore(uid).last_sent("trip", p.entity_id) is not None
    assert wiederholungs_eintraege(uid) == {}, (
        f"AC-13: Backoff nach Zustellung nicht geloescht: {wiederholungs_eintraege(uid)!r}"
    )
    p.lauf(_T0 + timedelta(minutes=62))
    assert rig.anzahl_versuche("email") == 2, f"AC-13: nach Zustellung erneut versendet: {rig!r}"


def test_ac14_entfallenes_ereignis_wird_nicht_weiter_versucht(rig):
    """AC-14 (Verhalten): GIVEN ein Ereignis ist am Transport gescheitert /
    WHEN es vor dem naechsten Versuch entfaellt (Abweichung verschwunden) /
    THEN gibt es keinen weiteren Versuch -- auch nicht als Entwarnung."""
    uid = _uid("ac14")
    rig.modus["email"] = "fehler"
    p = _TripAenderung(rig, uid, ("email",))
    p.lauf(_T0)
    assert rig.anzahl_versuche("email") == 1
    rig.modus["email"] = "ok"
    p.lauf_ohne_abweichung(_T0 + timedelta(minutes=31))
    p.lauf_ohne_abweichung(_T0 + timedelta(minutes=62))
    assert rig.anzahl_versuche("email") == 1, (
        f"AC-14: ein entfallenes Ereignis darf keinen weiteren Versand ausloesen: {rig!r}"
    )


def test_ac15_backoff_von_nutzer_a_bremst_nutzer_b_mit_gleicher_trip_id_nicht(rig):
    """AC-15: GIVEN zwei Nutzer mit identischer Trip-ID, bei A laeuft ein
    Backoff / WHEN fuer B derselbe Alarm ausgeloest wird / THEN wird B
    zugestellt und gebucht, und Backoff/Protokoll bleiben je Nutzer getrennt."""
    from services.throttle_store import ThrottleStore

    a, b = _uid("ac15-a"), _uid("ac15-b")
    rig.email_modus_je_host = {"smtp-a.rig-1405.test": "fehler", "smtp-b.rig-1405.test": "ok"}
    pa = _TripAenderung(rig, a, ("email",), smtp_host="smtp-a.rig-1405.test", entity_id="trip-gleich")
    pb = _TripAenderung(rig, b, ("email",), smtp_host="smtp-b.rig-1405.test", entity_id="trip-gleich")
    pa.lauf(_T0)
    assert wiederholungs_eintraege(a), "AC-15 Voraussetzung: Backoff bei Nutzer A fehlt"
    assert pb.lauf(_T0 + timedelta(minutes=5)) is True, f"AC-15: Nutzer B gebremst: {rig!r}"
    angenommen_hosts = [e["host"] for e in rig.angenommen["email"]]
    assert angenommen_hosts == ["smtp-b.rig-1405.test"], angenommen_hosts
    assert wiederholungs_eintraege(b) == {}, "AC-15: Nutzer B hat einen fremden Backoff"
    assert wiederholungs_eintraege(a), "AC-15: Backoff von A wurde durch B veraendert"
    assert ThrottleStore(a).last_sent("trip", "trip-gleich") is None
    assert ThrottleStore(b).last_sent("trip", "trip-gleich") is not None
    assert {e.get("entity_id") for e in read_log(b)["entries"]} == {"trip-gleich"}
    assert len(read_log(b)["entries"]) == 1 and len(read_log(a)["entries"]) == 1


def test_ac16_fehlversuche_verbrauchen_kein_sms_kontingent(rig):
    """AC-16: GIVEN der SMS-Versand scheitert dreimal (je nach Backoff-Ablauf)
    / WHEN danach ein Versand gelingt / THEN ist das Tageskontingent nach den
    Fehlversuchen unveraendert 0 und nach dem Erfolg genau 1."""
    uid = _uid("ac16")
    rig.modus["sms"] = "fehler"
    p = _TripAenderung(rig, uid, ("sms",))
    for minuten in (0, 31, 62):
        p.lauf(_T0 + timedelta(minutes=minuten))
    with freeze_time(_T0 + timedelta(minutes=63)):
        assert _sms_verbraucht(uid, datetime.now(timezone.utc)) == 0
    assert rig.anzahl_versuche("sms") == 3, (
        f"AC-16: drei Fehlversuche erwartet (Wiederholung nach Backoff), sind "
        f"{rig.anzahl_versuche('sms')}: {rig!r}"
    )
    rig.modus["sms"] = "ok"
    p.lauf(_T0 + timedelta(minutes=93))
    assert rig.anzahl_angenommen("sms") == 1, f"AC-16: Erfolg nach Fehlversuchen fehlt: {rig!r}"
    with freeze_time(_T0 + timedelta(minutes=94)):
        assert _sms_verbraucht(uid, datetime.now(timezone.utc)) == 1


# ═══════════════════════ D. Alarm-Protokoll und Cockpit ═════════════════════


@pytest.mark.parametrize("fall,kanaele,betreten", [
    ("teilerfolg", {"email", "telegram"}, ["email", "telegram"]),
    ("totalausfall", {"email"}, ["email"]),
    ("sperre", {"sms"}, []),
])
def test_ac17_attempted_channels_entspricht_dem_bisherigen_betreten(rig, fall, kanaele, betreten):
    """AC-17 (Ergebnisfeld): GIVEN Teilerfolg / Totalausfall / Sperre / WHEN der
    Alarm versendet wird / THEN enthaelt ``attempted_channels`` genau die
    Kanaele, die bisher in ``sent_channels`` (= betreten) standen."""
    uid = _uid(f"ac17-{fall}")
    dienst = _dienst(rig, uid)
    if fall == "teilerfolg":
        rig.modus["telegram"] = "fehler"
    elif fall == "totalausfall":
        rig.modus["email"] = "fehler"
    else:
        _sms_limit_ausschoepfen(uid, datetime.now(timezone.utc), sms=10)
    result = _versende("send_official_alert", dienst, kanaele)
    assert _betreten(result) == betreten, (
        f"AC-17 ({fall}): attempted_channels muss {betreten!r} sein, ist {_betreten(result)!r}"
    )


@pytest.mark.parametrize("fall,kanaele,liste", [
    ("teilerfolg", ("email", "telegram"), "entries"),
    ("totalausfall", ("email",), "entries"),
    ("sperre", ("sms",), "not_delivered"),
])
def test_ac17_cockpit_zahl_bleibt_wie_bisher(rig, fall, kanaele, liste):
    """AC-17 (Cockpit, Bestandsschutz): GIVEN Teilerfolg / Totalausfall /
    Sperre / WHEN das Protokoll geschrieben wird / THEN landet der Eintrag in
    derselben Liste wie bisher (#1459 AC-11)."""
    uid = _uid(f"ac17c-{fall}")
    p = _TripAenderung(rig, uid, kanaele)
    if fall == "teilerfolg":
        rig.modus["telegram"] = "fehler"
    elif fall == "totalausfall":
        rig.modus["email"] = "fehler"
    else:
        _sms_limit_ausschoepfen(uid, _T0, sms=10)
    p.lauf(_T0)
    log = read_log(uid)
    andere = "not_delivered" if liste == "entries" else "entries"
    assert len(log[liste]) == 1 and len(log[andere]) == 0, (
        f"AC-17 ({fall}): Eintrag gehoert nach {liste!r}: {log!r}"
    )


def test_ac18_totalausfall_steht_in_entries_mit_delivery_failed_ohne_zweiteintrag(rig):
    """AC-18: GIVEN ein konfigurierter Alarm stellt nichts zu / WHEN das
    Protokoll geschrieben wird / THEN steht der Eintrag in ``entries`` mit
    leerer Zugestellt-Liste und ``delivery_failed`` je Kanal; waehrend des
    Backoffs (+10 Min) entsteht kein weiterer Eintrag."""
    uid = _uid("ac18")
    rig.modus["email"] = "fehler"
    p = _TripAenderung(rig, uid, ("email",))
    p.lauf(_T0)
    log = read_log(uid)
    assert len(log["entries"]) == 1 and not log["not_delivered"], log
    eintrag = log["entries"][0]
    assert eintrag.get("channels_sent") == [], eintrag
    assert reason_for_channel(eintrag, "email") == "delivery_failed", eintrag
    p.lauf(_T0 + timedelta(minutes=10))
    assert _protokoll_zahl(uid) == 1, f"AC-18: Zweiteintrag waehrend des Backoffs: {read_log(uid)!r}"


# ═══════════════════ E. Paritaet Trip und Ortsvergleich ═════════════════════


def _sammelpfad(rig: KanalRig, uid: str, kanaele: set[str]):
    return _versende("send_multi_location_official_alert", _dienst(rig, uid), kanaele)


@pytest.mark.parametrize("pfad", _SIEBEN_PFADE)
def test_ac19_totalausfall_wird_je_pfad_nach_backoff_wiederholt(rig, pfad):
    """AC-19 (Totalausfall, AC-10/AC-13 je Pfad): GIVEN der einzige Kanal
    E-Mail scheitert / WHEN der Pfad laeuft, nach 10 Min erneut (Backoff) und
    nach 31 Min mit repariertem Draht / THEN keine Buchung, Backoff gesetzt,
    kein Versuch waehrend des Backoffs, Zustellung nach Ablauf, danach Ruhe."""
    uid = _uid(f"ac19t-{pfad}")
    rig.modus["email"] = "fehler"
    if pfad == "send_multi_location_official_alert":
        result = _sammelpfad(rig, uid, {"email"})
        assert rig.anzahl_versuche("email") == 1, rig
        assert result.sent is False, f"AC-19 ({pfad}): sent ist True trotz Totalausfall"
        assert _ausgang(result) == "transport_failed", _ausgang(result)
        return
    p = _AUFRUFER[pfad](rig, uid, ("email",))
    p.lauf(_T0)
    assert rig.anzahl_versuche("email") == 1, f"Voraussetzung {pfad}: kein Versuch: {rig!r}"
    assert wiederholungs_eintraege(uid), f"AC-19 ({pfad}): kein Backoff nach Totalausfall"
    rig.modus["email"] = "ok"
    p.lauf(_T0 + timedelta(minutes=10))
    assert rig.anzahl_versuche("email") == 1, f"AC-19 ({pfad}): Versuch waehrend Backoff: {rig!r}"
    p.lauf(_T0 + timedelta(minutes=31))
    assert rig.anzahl_angenommen("email") == 1, (
        f"AC-19 ({pfad}): Totalausfall wurde nach Backoff-Ablauf nicht wiederholt: {rig!r}"
    )
    assert wiederholungs_eintraege(uid) == {}, f"AC-19 ({pfad}): Backoff nach Zustellung"
    p.lauf(_T0 + timedelta(minutes=62))
    assert rig.anzahl_versuche("email") == 2, f"AC-19 ({pfad}): Wiederholung nach Zustellung: {rig!r}"


@pytest.mark.parametrize("pfad", _SIEBEN_PFADE)
def test_ac19_teilerfolg_wird_je_pfad_gebucht_und_nicht_wiederholt(rig, pfad):
    """AC-19 (Teilerfolg, AC-8 je Pfad): GIVEN E-Mail stellt zu, Telegram
    scheitert / WHEN der Pfad laeuft und 31 Min spaeter erneut / THEN gilt der
    Alarm als zugestellt, kein Backoff, kein zweiter Versand."""
    uid = _uid(f"ac19p-{pfad}")
    rig.modus["telegram"] = "fehler"
    if pfad == "send_multi_location_official_alert":
        result = _sammelpfad(rig, uid, {"email", "telegram"})
        assert result.sent is True and _ausgang(result) == "delivered", (result, _ausgang(result))
        return
    p = _AUFRUFER[pfad](rig, uid, ("email", "telegram"))
    p.lauf(_T0)
    assert rig.anzahl_angenommen("email") == 1, f"Voraussetzung {pfad}: {rig!r}"
    assert wiederholungs_eintraege(uid) == {}, f"AC-19 ({pfad}): Backoff trotz Teilerfolg"
    rig.modus["telegram"] = "ok"
    p.lauf(_T0 + timedelta(minutes=31))
    assert rig.anzahl_versuche("email") == 1, f"AC-19 ({pfad}): Teilerfolg wiederholt: {rig!r}"


@pytest.mark.parametrize("pfad", _SIEBEN_PFADE)
def test_ac19_reine_sperre_ist_je_pfad_terminal(rig, pfad):
    """AC-19 (Sperre, AC-9 je Pfad): GIVEN der einzige Kanal SMS ist per
    Tageslimit gesperrt / WHEN der Pfad dreimal laeuft / THEN ein einziger
    Protokolleintrag, kein Draht, kein Backoff -- und im Sammelpfad lautet das
    Ergebnis ``blocked_only`` statt "gesendet"."""
    uid = _uid(f"ac19s-{pfad}")
    if pfad == "send_multi_location_official_alert":
        dienst = _dienst(rig, uid)
        _sms_limit_ausschoepfen(uid, datetime.now(timezone.utc), sms=10)
        result = _versende(pfad, dienst, {"sms"})
        assert rig.anzahl_versuche("sms") == 0, rig
        assert result.sent is False, (
            f"AC-19: Tageslimit-Sperre im Sammelpfad ergibt 'gesendet': {result!r}"
        )
        assert _ausgang(result) == "blocked_only", _ausgang(result)
        return
    p = _AUFRUFER[pfad](rig, uid, ("sms",))
    _sms_limit_ausschoepfen(uid, _T0, sms=10)
    for minuten in (0, 31, 62):
        p.lauf(_T0 + timedelta(minutes=minuten))
    assert rig.anzahl_versuche("sms") == 0, rig
    assert _protokoll_zahl(uid) == 1, (
        f"AC-19 ({pfad}): reine Sperre muss terminal sein -- {_protokoll_zahl(uid)} "
        f"Protokolleintraege nach drei Laeufen"
    )
    assert wiederholungs_eintraege(uid) == {}, f"AC-19 ({pfad}): Backoff trotz reiner Sperre"


@pytest.mark.parametrize("pfad", list(_AUFRUFER))
def test_ac19_ereigniswechsel_wird_je_pfad_nicht_vom_alten_backoff_blockiert(rig, pfad):
    """AC-19 (Ereignis-Wechsel, AC-12 je Pfad): GIVEN Ereignis A ist am
    Transport gescheitert (Backoff) / WHEN 5 Min spaeter ein neues Ereignis B
    auftritt und der Draht wieder geht / THEN wird sofort zugestellt.

    Der Sammelpfad fehlt hier bewusst: er bucht nichts und kennt keinen
    Backoff; sein Ereignis-Wechsel ist der von ``compare_official_alert``."""
    uid = _uid(f"ac19e-{pfad}")
    rig.modus["email"] = "fehler"
    p = _AUFRUFER[pfad](rig, uid, ("email",))
    p.lauf(_T0)
    assert rig.anzahl_versuche("email") == 1, f"Voraussetzung {pfad}: {rig!r}"
    assert wiederholungs_eintraege(uid), f"AC-19 ({pfad}) Voraussetzung: Backoff fuer A fehlt"
    rig.modus["email"] = "ok"
    p.lauf(_T0 + timedelta(minutes=5), ereignis="B")
    assert rig.anzahl_angenommen("email") == 1, (
        f"AC-19 ({pfad}): neues Ereignis B wurde vom Backoff von A blockiert: {rig!r}"
    )


@pytest.mark.parametrize("fall", ["totalausfall", "teilerfolg", "sperre"])
def test_ac20_drei_versandpfade_liefern_denselben_ausgang(rig, fall):
    """AC-20: GIVEN derselbe Ausgang (Totalausfall, Teilerfolg, Sperre) / WHEN
    er in ``send_official_alert``, ``_dispatch_alert_message`` und
    ``send_multi_location_official_alert`` eintritt / THEN liefern alle drei
    dasselbe ``delivery_outcome``; bei Totalausfall und Teilerfolg auch
    dieselben ``attempted_channels``."""
    kanaele = {"totalausfall": {"email"}, "teilerfolg": {"email", "sms"}, "sperre": {"sms"}}[fall]
    erwartet = {"totalausfall": "transport_failed", "teilerfolg": "delivered",
                "sperre": "blocked_only"}[fall]
    ausgaenge, betreten = {}, {}
    for pfad in _VERSANDPFADE:
        uid = _uid(f"ac20-{fall}")
        dienst = _dienst(rig, uid)
        rig.modus = {k: "ok" for k in KANAELE}
        if fall == "totalausfall":
            rig.modus["email"] = "fehler"
        elif fall == "teilerfolg":
            rig.modus["sms"] = "fehler"
        else:
            _sms_limit_ausschoepfen(uid, datetime.now(timezone.utc), sms=10)
        result = _versende(pfad, dienst, kanaele)
        ausgaenge[pfad] = _ausgang(result)
        betreten[pfad] = _betreten(result)
    assert set(ausgaenge.values()) == {erwartet}, (
        f"AC-20 ({fall}): die drei Versandpfade liefern unterschiedliche Ausgaenge: {ausgaenge!r}"
    )
    if fall != "sperre":
        assert len({json.dumps(v) for v in betreten.values()}) == 1 and betreten["send_official_alert"] == sorted(kanaele), (
            f"AC-20 ({fall}): attempted_channels weichen ab: {betreten!r}"
        )
