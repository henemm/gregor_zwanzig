"""TDD RED — Issue #2587: Ortsvergleich-Briefing nach Versandfehler nachholen.

SPEC: docs/specs/modules/feat_2587_compare_briefing_nachholen.md (AC-1..AC-13)
Trip-Vorbild: ``test_briefing_anchor_survives_dispatch_failure.py`` (#1662).

Test-Politik (CLAUDE.md, ``docs/reference/gates_und_ratschen.md``): kein
Mock-Theater. Alles laeuft ueber die echten Einstiegspunkte
(``run_briefing_dispatch("vergleich", ...)`` = stuendlicher Compare-Lauf mit
``collect_due``/``pre_pass``/``dispatch_one``, ``send_one_compare_preset``,
``_dispatch_due_preset``, ``TripDispatchStrategy.pre_pass``, Handversand-
Endpunkt). Beobachtet wird ausschliesslich echter Zustand:
``data/users/<uid>/pending_briefings.json`` (Ablage), ``briefing_log.json``
(Versand-Historie, #2281) und das, was am Kanal-Ausgang tatsaechlich hinausging.

Naehte (nur zum Netz bzw. zur teuren Upstream-Abhaengigkeit, nie zur
gepruefte Entscheidung):

* Wetter: ``engine_naht`` (echte ``ComparisonEngine``-Unterklasse) aus
  ``_compare_kette_fixtures``.
* Transport: der geteilte Aufzeichner ``tests/helpers/transport_mitschrift.py``;
  hier zusaetzlich je Kanal schaltbar gestoert (der Ausgang wirft beim Senden
  — ein SMTP-/Gateway-Ausfall, ohne je eine Verbindung aufzubauen).
* Zeit: ausschliesslich ueber das ``now_utc``-Argument der Einstiegspunkte;
  alle Tage werden aus der Ortszone des Presets abgeleitet, nie aus
  ``date.today()``.

Die Spec sieht ein neues Modul ``services.pending_briefings`` und neue
Parameter vor. Diese Tests koppeln sich bewusst NICHT daran (kein Import,
keine neuen Keyword-Argumente): sie muessen an fehlendem VERHALTEN rot sein,
nicht an ImportError/TypeError.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.loader import get_data_dir, get_data_root, save_location
from app.user import SavedLocation
from tests.helpers.transport_mitschrift import Kanalmitschrift, aufzeichner_installieren
from tests.tdd import _handversand_fixtures as hv
from tests.tdd._compare_kette_fixtures import (
    ORTE,
    TARGET_DATE,
    engine_naht,
    fixture_dict,
    nutzer_anlegen,
    preset_ablegen,
    preset_laden,
    settings_fuer,
    transport_einrichten,
)

# Pfadregel #1409: Pruefling relativ zur Testdatei aufloesen.
REPO_ROOT = Path(__file__).resolve().parents[2]

ZONE = "Europe/Vienna"
D = TARGET_DATE  # Zieltag "heute" in Preset-Ortszeit (fest, nie date.today())

#: Hinweis-Text laut Spec (Implementation Details 3.4 / AC-5): Wortlaut "07:00"
#: (zweistellig, Adversary F006 -- vorher tolerant "0?7:00").
_HINWEIS_RE = re.compile(
    r"Nachgeliefert (?:—|&mdash;|&#8212;) die Zustellung um 07:00 ist fehlgeschlagen"
)


# ---------------------------------------------------------------------------
# Umgebung: Wetter-Naht + schaltbar gestoerter Transport
# ---------------------------------------------------------------------------


class _Ausgang:
    """Was hinausging (``mit``), wie oft je Kanal versucht wurde, welche
    Kanaele gestoert sind und welche Zieltage die Wetter-Engine bekam."""

    def __init__(self, mit: Kanalmitschrift) -> None:
        self.mit = mit
        self.stoerung: set[str] = set()
        self.versuche = {"email": 0, "telegram": 0}
        self.beim_senden: list = []  # Rueckrufe (kanal) im Sendemoment
        self.ziel_tage: list[date] = []


@pytest.fixture
def aus(monkeypatch) -> _Ausgang:
    transport_einrichten(monkeypatch)
    engine_naht(monkeypatch)
    mit = aufzeichner_installieren(monkeypatch)
    a = _Ausgang(mit)

    from services import notification_service as ns
    import output.channels.email as email_mod
    import services.comparison_engine as ce_mod
    import services.dispatch_orchestrator as orch_mod

    # 2s zwischen Presets ist hier nicht Pruefgegenstand.
    monkeypatch.setattr(orch_mod.CompareDispatchStrategy, "inter_mail_delay", 0.0)

    email_aufzeichner = email_mod.EmailOutput
    telegram_aufzeichner = ns.TelegramOutput

    class _Email(email_aufzeichner):
        def send(self, *args, **kwargs):
            a.versuche["email"] += 1
            for rueckruf in list(a.beim_senden):
                rueckruf("email")
            if "email" in a.stoerung:
                raise RuntimeError("Mail-Gateway nicht erreichbar (simulierter Ausfall)")
            return super().send(*args, **kwargs)

    class _Telegram(telegram_aufzeichner):
        def send(self, *args, **kwargs):
            a.versuche["telegram"] += 1
            for rueckruf in list(a.beim_senden):
                rueckruf("telegram")
            if "telegram" in a.stoerung:
                raise RuntimeError("Telegram-Gateway nicht erreichbar (simulierter Ausfall)")
            return super().send(*args, **kwargs)

    monkeypatch.setattr(email_mod, "EmailOutput", _Email)
    monkeypatch.setattr(ns, "EmailOutput", _Email)
    monkeypatch.setattr(ns, "TelegramOutput", _Telegram)

    engine = ce_mod.ComparisonEngine

    class _ZieltagEngine(engine):  # echte Unterklasse, zeichnet nur den Zieltag auf
        @staticmethod
        def run(*args, **kwargs):
            if kwargs.get("target_date") is not None:
                a.ziel_tage.append(kwargs["target_date"])
            return engine.run(*args, **kwargs)

    monkeypatch.setattr(ce_mod, "ComparisonEngine", _ZieltagEngine)
    return a


# ---------------------------------------------------------------------------
# Aufbau: Orte, Presets, Ablage
# ---------------------------------------------------------------------------


def _orte(uid: str, lage: dict[str, tuple[str, float, float]] | None = None) -> None:
    """Die beiden Kettenorte (Kennungen ``loc-ibk``/``loc-bz``, an denen die
    Wetter-Naht haengt). Die Zone folgt den Koordinaten (``timezone`` wird vom
    Loader nicht persistiert); ``lage`` verlegt die Orte in andere Zonen."""
    for lid, (name, lat, lon) in (lage or ORTE).items():
        save_location(SavedLocation(
            id=lid, name=name, lat=lat, lon=lon, elevation_m=1000,
        ), user_id=uid)


def _vergleich(uid: str, pid: str, *, name: str | None = None, morgen: str | None = "07:00:00",
               abend: str | None = None, telegram: bool = False,
               orte: list[str] | None = None, **extra) -> str:
    roh = fixture_dict("basis")
    roh["id"] = pid
    roh["name"] = name or f"Vergleich {pid}"
    roh["morning_enabled"] = morgen is not None
    roh["morning_time"] = morgen or "07:00:00"
    roh["evening_enabled"] = abend is not None
    roh["evening_time"] = abend or "18:00:00"
    roh["send_telegram"] = telegram
    if orte is not None:
        roh["location_ids"] = list(orte)
    roh.update(extra)
    preset_ablegen(uid, roh)
    return pid


def _utc(tag: date, stunde: int, zone: str = ZONE) -> datetime:
    return datetime(tag.year, tag.month, tag.day, stunde, tzinfo=ZoneInfo(zone)).astimezone(
        timezone.utc,
    )


def _pfad(uid: str) -> Path:
    return get_data_dir(uid) / "pending_briefings.json"


def _ablage(uid: str) -> list:
    pfad = _pfad(uid)
    if not pfad.exists():
        return []
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    return daten.get("entries", []) if isinstance(daten, dict) else daten


def _vergleich_vermerke(uid: str) -> list:
    return [e for e in _ablage(uid) if e.get("kind") == "vergleich"]


def _schluessel(uid: str) -> set:
    return {(e.get("preset_id"), e.get("report_type"), e.get("date"), e.get("slot_hour"))
            for e in _vergleich_vermerke(uid)}


def _vermerk(pid: str, report_type: str, tag: date, slot_hour: int, *,
             created_at: str = "2026-07-01T00:00:00+00:00", attempts: int = 0) -> dict:
    """Ausgangslage im Datenmodell der Spec (Setup, keine Zusicherung)."""
    return {
        "kind": "vergleich", "preset_id": pid, "report_type": report_type,
        "date": tag.isoformat(), "slot_hour": slot_hour, "reason": "dispatch_error",
        "failed_segment_ids": [], "attempts": attempts, "created_at": created_at,
    }


def _trip_vermerk(trip_id: str, *, kind: str | None = None) -> dict:
    e = {
        "trip_id": trip_id, "report_type": "morning", "date": D.isoformat(),
        "slot_hour": 7, "failed_segment_ids": ["seg-1"], "attempts": 1,
        "created_at": "2026-07-08T05:00:00+00:00",
    }
    if kind is not None:
        e["kind"] = kind
    return e


def _ablage_schreiben(uid: str, entries: list) -> None:
    pfad = _pfad(uid)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({"entries": entries}, indent=2), encoding="utf-8")


def _kanon(e: dict) -> str:
    return json.dumps(e, sort_keys=True, ensure_ascii=False)


def _lauf(uid: str, now_utc: datetime):
    """Der echte stuendliche Compare-Lauf (Go-Cron -> compare-presets-daily)."""
    from services.dispatch_orchestrator import run_briefing_dispatch

    return run_briefing_dispatch("vergleich", uid, now_utc, data_root=str(get_data_root()))


def _mails(aus: _Ausgang, name: str | None = None) -> list[dict]:
    return [m for m in aus.mit.sendungen("email") if name is None or name in (m["subject"] or "")]


def _mail_to(uid: str) -> str:
    return json.loads((get_data_dir(uid) / "user.json").read_text())["mail_to"]


def _briefing_log(uid: str) -> list:
    pfad = get_data_dir(uid) / "briefing_log.json"
    if not pfad.exists():
        return []
    return json.loads(pfad.read_text()).get("entries", [])


def _nutzer() -> str:
    uid = nutzer_anlegen()
    _orte(uid)
    return uid


def _pid(stamm: str) -> str:
    return f"vgl-{stamm}-{uuid.uuid4().hex[:6]}"


# ═══════════════════════════════ AC-1 ════════════════════════════════════════


def test_ac1_gescheiterter_zeitplan_versand_hinterlaesst_genau_einen_vergleichs_vermerk(aus):
    """AC-1.

    GIVEN ein aktiver Ortsvergleich (Morgen-Slot 07:00 Ortszeit), dessen
          automatischer Versand auf allen Kanaelen scheitert (E-Mail wirft),
          und in der Ablage liegt bereits ein fremder Trip-Vermerk.
    WHEN  der Scheduler-Lauf der Slot-Stunde beendet ist.
    THEN  liegt in der Ablage dieses Nutzers genau ein Vermerk mit Art
          "vergleich", Preset-Kennung, Slot "morning", Zieltag D, Slot-Stunde 7,
          Grund "dispatch_error" — und der Trip-Vermerk ist unveraendert
          (Read-Modify-Write, kein Replace, #102).

    RED heute: Compare schreibt keinen Vermerk.
    """
    uid = _nutzer()
    pid = _vergleich(uid, _pid("ac1"))
    fremd = _trip_vermerk("trip-fremd-ac1")
    _ablage_schreiben(uid, [fremd])
    aus.stoerung.add("email")

    _lauf(uid, _utc(D, 7))

    assert aus.versuche["email"] == 1, "Vorbedingung: der Slot hat den E-Mail-Ausgang betreten"
    vermerke = _vergleich_vermerke(uid)
    assert len(vermerke) == 1, (
        "AC-1: ein vollstaendig gescheiterter Zeitplan-Versand muss genau einen "
        f"Ortsvergleich-Vermerk hinterlassen, Ablage: {_ablage(uid)!r}"
    )
    v = vermerke[0]
    assert v.get("preset_id") == pid, v
    assert not v.get("trip_id"), f"Compare-Vermerk traegt keine trip_id: {v!r}"
    assert v.get("report_type") == "morning", v
    assert v.get("date") == D.isoformat(), v
    assert v.get("slot_hour") == 7, v
    assert v.get("reason") == "dispatch_error", v
    trips = [e for e in _ablage(uid) if e.get("trip_id")]
    assert [_kanon(e) for e in trips] == [_kanon(fremd)], (
        f"Der fremde Trip-Vermerk muss unveraendert bleiben (RMW, #102): {trips!r}"
    )


# ═══════════════════════════════ AC-2 ════════════════════════════════════════


def test_ac2_kein_kanal_erreichbar_im_zeitplan_hinterlaesst_denselben_vermerk(aus):
    """AC-2 (positiv).

    GIVEN ein Ortsvergleich, dessen einziger wirksamer Kanal (Telegram; das
          Konto hat keine mail_to) beim Senden scheitert — Ausgang
          ``channels_unreachable``, keine Ausnahme.
    WHEN  der Scheduler-Lauf beendet ist.
    THEN  entsteht derselbe Vermerk wie bei AC-1.

    RED heute: kein Vermerk.
    """
    from app.config import Settings

    uid = _nutzer()
    pid = _vergleich(uid, _pid("ac2-unerreichbar"), telegram=True)
    hv.profil_ohne_mail_to(uid)
    assert not Settings().with_user_profile(uid).mail_to, "Vorbedingung: keine mail_to"
    aus.stoerung.add("telegram")

    _lauf(uid, _utc(D, 7))

    assert aus.versuche["telegram"] == 1, "Vorbedingung: Telegram-Ausgang betreten"
    assert aus.mit.kanaele == [], f"Vorbedingung: nichts zugestellt: {aus.mit!r}"
    assert _schluessel(uid) == {(pid, "morning", D.isoformat(), 7)}, (
        "AC-2: 'kein Kanal erreichbar' muss denselben Vermerk wie eine Ausnahme "
        f"hinterlassen, Ablage: {_ablage(uid)!r}"
    )
    assert _vergleich_vermerke(uid)[0].get("reason") == "dispatch_error"


def test_ac2_keine_kanaele_konfiguriert_hinterlaesst_keinen_vermerk(aus):
    """AC-2 (negativ, Bestandsabsicherung).

    GIVEN ein Ortsvergleich ohne wirksamen Kanal (keine mail_to, kein Opt-in).
    WHEN  der Scheduler-Lauf beendet ist.
    THEN  entsteht KEIN Vermerk (Konfigurationsfehler, Nachholen hilft nicht).
    """
    uid = _nutzer()
    _vergleich(uid, _pid("ac2-ohne-kanal"))
    hv.profil_ohne_mail_to(uid)

    _lauf(uid, _utc(D, 7))

    assert aus.mit.kanaele == [], aus.mit
    assert _vergleich_vermerke(uid) == [], (
        f"AC-2: no_channels darf keinen Vermerk erzeugen: {_ablage(uid)!r}"
    )


def test_ac2_keine_wetterdaten_im_cron_hinterlassen_slot_vermerk_und_nachhol_vermerk(aus, monkeypatch):
    """AC-2 (negativ) — abgeloest durch #1777 AC-12 (Spec fix_1777,
    „no_weather im Cron"; Trip-Paritaet).

    GIVEN ein Ortsvergleich, dessen Wetterabruf an jedem Ort scheitert
          (``LocationResult(error=...)`` -> ``no_weather``).
    WHEN  der Scheduler-Lauf beendet ist.
    THEN  nichts geht hinaus, der Slot ist mit ``no_weather`` vermerkt
          (``briefing_slots_compare.json``) UND es liegt genau ein Nachhol-
          Vermerk (morning, D, 07) vor — ein kurzer Wetterausfall laesst den
          Vergleich nicht mehr ersatzlos ausfallen. Frueher galt hier „no_weather
          erzeugt keinen Vermerk".
    """
    uid = _nutzer()
    pid = _vergleich(uid, _pid("ac2-ohne-wetter"))
    hv.wetter_fehlt_je_ort(monkeypatch)

    _lauf(uid, _utc(D, 7))

    assert aus.mit.kanaele == [], aus.mit
    assert _schluessel(uid) == {(pid, "morning", D.isoformat(), 7)}, (
        f"#1777 AC-12: no_weather im Cron muss einen Nachhol-Vermerk schreiben: {_ablage(uid)!r}"
    )
    slots = get_data_dir(uid) / "briefing_slots_compare.json"
    eintraege = json.loads(slots.read_text()).get("entries", []) if slots.exists() else []
    assert [(e.get("preset_id"), e.get("slot"), e.get("local_day"), e.get("outcome"))
            for e in eintraege] == [(pid, "morning", D.isoformat(), "no_weather")], (
        f"#1777 AC-11/AC-12: der Slot ist mit no_weather vermerkt: {eintraege!r}"
    )


def test_ac2_wetter_ausnahme_ueberall_hinterlaesst_keinen_vermerk(aus, monkeypatch):
    """AC-2 (negativ, Bestandsabsicherung).

    GIVEN ein Ortsvergleich, dessen Wetterabruf an jedem Ort mit einer
          durchschlagenden Ausnahme scheitert (im Cron KEIN ``no_weather``,
          sondern die Originalausnahme, #2286 F-ADV1).
    WHEN  der Scheduler-Lauf beendet ist.
    THEN  entsteht KEIN Nachhol-Vermerk (#1777: sonstige Ausnahme = release).
    """
    uid = _nutzer()
    _vergleich(uid, _pid("ac2-wetter-ausnahme"))
    hv.wetter_faellt_ueberall_aus(monkeypatch)

    _lauf(uid, _utc(D, 7))

    assert aus.mit.kanaele == [], aus.mit
    assert _vergleich_vermerke(uid) == [], (
        f"AC-2: eine Wetter-Ausnahme darf keinen Vermerk erzeugen: {_ablage(uid)!r}"
    )


# ═══════════════════════════════ AC-3 ════════════════════════════════════════


def test_ac3_handversand_und_befehl_hinterlassen_bei_keiner_fehlerform_einen_vermerk(aus):
    """AC-3 (Bestandsabsicherung; Gegenprobe: ``test_ac3_kontrolle_...``).

    GIVEN ein Ortsvergleich-Versand scheitert vollstaendig, ausgeloest als
          On-Demand (HEUTE/MORGEN-Befehl, ``on_demand=True``) bzw. ueber den
          Handversand-Endpunkt.
    WHEN  der Aufruf beendet ist.
    THEN  entsteht KEIN Vermerk — weder bei Ausnahme noch bei
          ``channels_unreachable``.
    """
    from services.scheduler_dispatch_service import send_one_compare_preset
    from services.send_outcomes import SendOutcomeError
    from tests.tdd._compare_kette_fixtures import alle_orte

    # (1) Ausnahme (E-Mail wirft), on_demand
    uid = _nutzer()
    pid = _vergleich(uid, _pid("ac3-ausnahme"))
    aus.stoerung = {"email"}
    with pytest.raises(RuntimeError):
        send_one_compare_preset(
            preset_laden(uid, pid), settings_fuer(uid), uid, str(get_data_root()),
            all_locations_cache=alle_orte(uid), target_date=D, tage_ab_ortstag=0,
            on_demand=True,
        )
    assert aus.versuche["email"] == 1, "Vorbedingung: E-Mail-Ausgang betreten"
    assert _ablage(uid) == [], f"AC-3: On-Demand-Ausnahme ohne Vermerk: {_ablage(uid)!r}"

    # (2) channels_unreachable, on_demand
    uid2 = _nutzer()
    pid2 = _vergleich(uid2, _pid("ac3-unerreichbar"), telegram=True)
    hv.profil_ohne_mail_to(uid2)
    aus.stoerung = {"telegram"}
    with pytest.raises(SendOutcomeError):
        send_one_compare_preset(
            preset_laden(uid2, pid2), settings_fuer(uid2), uid2, str(get_data_root()),
            all_locations_cache=alle_orte(uid2), target_date=D, tage_ab_ortstag=0,
            on_demand=True,
        )
    assert aus.versuche["telegram"] == 1, "Vorbedingung: Telegram-Ausgang betreten"
    assert _ablage(uid2) == [], f"AC-3: On-Demand ohne Zustellung ohne Vermerk: {_ablage(uid2)!r}"

    # (3) Handversand-Endpunkt (#2280)
    uid3 = _nutzer()
    pid3 = _vergleich(uid3, _pid("ac3-hand"), telegram=True)
    hv.profil_ohne_mail_to(uid3)
    r = hv.alt_senden(hv.client(), "vergleich", pid3, uid3)
    assert r.status_code == 422 and hv.body(r).get("code") == "channels_unreachable", r.text
    assert _ablage(uid3) == [], f"AC-3: Handversand ohne Vermerk: {_ablage(uid3)!r}"


def test_ac3_kontrolle_derselbe_fehler_ohne_on_demand_hinterlaesst_den_vermerk(aus):
    """AC-3 Gegenprobe (sonst waere AC-3 vakuum).

    GIVEN derselbe Ausnahme-Fehler wie oben, aber als regulaerer Versand
          (``on_demand=False``, Morgen-Slot: Versatz 0).
    WHEN  ``send_one_compare_preset`` beendet ist.
    THEN  liegt der Vermerk (Slot "morning", Zieltag D) vor.

    RED heute: kein Vermerk.
    """
    from services.scheduler_dispatch_service import send_one_compare_preset
    from tests.tdd._compare_kette_fixtures import alle_orte

    uid = _nutzer()
    pid = _vergleich(uid, _pid("ac3-kontrolle"))
    aus.stoerung.add("email")
    with pytest.raises(RuntimeError):
        send_one_compare_preset(
            preset_laden(uid, pid), settings_fuer(uid), uid, str(get_data_root()),
            all_locations_cache=alle_orte(uid), target_date=D, tage_ab_ortstag=0,
        )
    assert {(k[0], k[1], k[2]) for k in _schluessel(uid)} == {(pid, "morning", D.isoformat())}, (
        f"AC-3 Gegenprobe: regulaerer Fehlschlag muss vermerkt werden: {_ablage(uid)!r}"
    )


# ═══════════════════════════════ AC-4 ════════════════════════════════════════


def test_ac4_trip_nachholdurchlauf_laesst_den_vergleichs_vermerk_byte_gleich_stehen(aus):
    """AC-4.

    GIVEN in der Ablage liegen ein Ortsvergleich-Vermerk, ein Trip-Vermerk ohne
          Art-Feld (Bestandsformat) und ein Trip-Vermerk mit Art "route" — beide
          Trips existieren nicht (mehr).
    WHEN  der Trip-Nachholdurchlauf (``TripDispatchStrategy.pre_pass``, der
          Vorlauf von ``trip-reports``) laeuft.
    THEN  bleibt der Ortsvergleich-Vermerk unveraendert, und die Trip-Vermerke
          behandelt der Trip-Lauf wie bisher (zu nicht vorhandenem Trip:
          geloescht).

    RED heute: ``_remove_pending_marker(None)`` loescht den Compare-Eintrag.
    """
    from services.dispatch_orchestrator import TripDispatchStrategy

    uid = _nutzer()
    pid = _vergleich(uid, _pid("ac4"))
    vgl = _vermerk(pid, "evening", D + timedelta(days=1), 19, attempts=2)
    _ablage_schreiben(uid, [
        _trip_vermerk("trip-weg-alt"),
        vgl,
        _trip_vermerk("trip-weg-route", kind="route"),
    ])

    TripDispatchStrategy(settings=settings_fuer(uid), user_id=uid).pre_pass(
        now_utc=_utc(D, 10), due=[],
    )

    eintraege = _ablage(uid)
    trips = [e for e in eintraege if e.get("trip_id")]
    assert trips == [], (
        "Vorbedingung/Bestand: Vermerke zu nicht vorhandenen Trips raeumt der "
        f"Trip-Lauf weg (der Lauf hat also stattgefunden): {trips!r}"
    )
    assert [_kanon(e) for e in eintraege if e.get("kind") == "vergleich"] == [_kanon(vgl)], (
        "AC-4: der Trip-Nachholdurchlauf darf den Ortsvergleich-Vermerk weder "
        f"loeschen noch veraendern, Ablage danach: {eintraege!r}"
    )


def test_ac4_umgekehrt_der_vergleichs_vorlauf_laesst_trip_vermerke_unberuehrt(aus):
    """AC-4 Gegenrichtung (Implementation Details 5, Bestandsabsicherung).

    GIVEN eine Ablage nur mit Trip-Vermerken (Bestandsformat und "route").
    WHEN  der stuendliche Compare-Lauf (inkl. ``pre_pass``) laeuft.
    THEN  sind beide Trip-Vermerke byte-gleich erhalten.
    """
    uid = _nutzer()
    _vergleich(uid, _pid("ac4-gegen"))
    trips = [_trip_vermerk("trip-a"), _trip_vermerk("trip-b", kind="route")]
    _ablage_schreiben(uid, trips)

    _lauf(uid, _utc(D, 10))

    assert sorted(_kanon(e) for e in _ablage(uid)) == sorted(_kanon(e) for e in trips), (
        f"Der Compare-Lauf darf Trip-Vermerke nicht anfassen: {_ablage(uid)!r}"
    )


# ═══════════════════════════════ AC-5 ════════════════════════════════════════


def test_ac5_vermerk_wird_spaeter_am_zieltag_mit_hinweis_in_mail_und_telegram_nachgeholt(aus):
    """AC-5.

    GIVEN ein Vermerk fuer den Morgen-Slot 07:00 von D, es ist 10:00 Ortszeit
          an D, kein regulaerer Slot dieses Presets faellig; Kanaele E-Mail und
          Telegram funktionieren.
    WHEN  der stuendliche Compare-Vorlauf laeuft.
    THEN  wird das Briefing an die Empfaenger des Nutzers zugestellt, und der
          Text beginnt in E-Mail (Plain; HTML: vor dem Inhalt) und Telegram mit
          "Nachgeliefert — die Zustellung um 07:00 ist fehlgeschlagen"; der
          Vermerk ist danach weg.

    RED heute: es wird nichts nachgeholt.
    """
    uid = _nutzer()
    pid = _vergleich(uid, _pid("ac5"), telegram=True)
    _ablage_schreiben(uid, [_vermerk(pid, "morning", D, 7)])

    _lauf(uid, _utc(D, 10))

    mails = aus.mit.sendungen("email")
    assert len(mails) == 1, f"AC-5: genau eine nachgeholte Mail erwartet: {aus.mit!r}"
    assert mails[0]["empfaenger"] == _mail_to(uid), mails[0]["empfaenger"]
    assert D.strftime("%d.%m.%Y") in mails[0]["subject"], mails[0]["subject"]
    plain = mails[0]["plain_text_body"] or ""
    html = mails[0]["body"] or ""
    assert _HINWEIS_RE.match(plain), f"AC-5: Plain-Text beginnt nicht mit dem Hinweis: {plain[:200]!r}"
    treffer = _HINWEIS_RE.search(html)
    assert treffer, f"AC-5: HTML ohne Hinweis: {html[:400]!r}"
    ort_stellen = [i for i in (html.find(n) for n in ("Innsbruck", "Bozen")) if i >= 0]
    assert ort_stellen, f"Vorbedingung: die Mail nennt die Orte: {html[:400]!r}"
    erster_ort = min(ort_stellen)
    assert treffer.start() < erster_ort, "AC-5: der HTML-Hinweis steht nicht vor dem Inhalt"
    telegram = aus.mit.sendungen("telegram")
    assert len(telegram) == 1, f"AC-5: genau eine Telegram-Nachricht erwartet: {aus.mit!r}"
    assert _HINWEIS_RE.match(telegram[0]["body"] or ""), (
        f"AC-5: Telegram beginnt nicht mit dem Hinweis: {telegram[0]['body'][:200]!r}"
    )
    assert _vergleich_vermerke(uid) == [], f"Nach Zustellung kein Vermerk mehr: {_ablage(uid)!r}"


# ═══════════════════════════════ AC-6 ════════════════════════════════════════


def test_ac6_vermerk_ist_vor_dem_nachholen_entfernt_und_ein_erneuter_fehlschlag_vermerkt_frisch(aus):
    """AC-6.

    GIVEN ein Vermerk (alter ``created_at``, ``attempts=3``) wird nachgeholt.
    WHEN  der Nachhol-Versand beginnt und dabei erneut scheitert.
    THEN  ist der Vermerk im Sendemoment bereits aus der Ablage entfernt, und
          danach liegt genau ein NEUER Vermerk (frischer ``created_at``,
          ``attempts == 0``) fuer denselben Preset und Slot vor.

    RED heute: kein Nachholversuch.
    """
    uid = _nutzer()
    pid = _vergleich(uid, _pid("ac6"))
    alt = "2020-01-01T00:00:00+00:00"
    _ablage_schreiben(uid, [_vermerk(pid, "morning", D, 7, created_at=alt, attempts=3)])
    im_sendemoment: list = []
    aus.beim_senden.append(lambda kanal: im_sendemoment.append(_vergleich_vermerke(uid)))
    aus.stoerung.add("email")

    _lauf(uid, _utc(D, 10))

    assert im_sendemoment, "AC-6: es hat kein Nachhol-Versuch stattgefunden"
    assert im_sendemoment[0] == [], (
        "AC-6: der Vermerk muss VOR dem Senden entfernt sein (kein Doppelversand "
        f"bei Absturz), im Sendemoment lag: {im_sendemoment[0]!r}"
    )
    vermerke = _vergleich_vermerke(uid)
    assert len(vermerke) == 1, f"AC-6: genau ein neuer Vermerk erwartet: {_ablage(uid)!r}"
    v = vermerke[0]
    assert (v.get("preset_id"), v.get("report_type"), v.get("date")) == (pid, "morning", D.isoformat()), v
    assert v.get("attempts") == 0, v
    assert v.get("created_at") != alt and datetime.fromisoformat(v["created_at"]) > datetime.fromisoformat(alt), v


# ═══════════════════════════════ AC-7 ════════════════════════════════════════


def test_ac7_verfall_folgt_dem_ortstag_des_presets_nicht_dem_utc_tag(aus):
    """AC-7.

    GIVEN zwei Presets in verschiedenen Zonen (Auckland, Los Angeles) und ein
          fester UTC-Zeitpunkt, an dem in Auckland schon der Folgetag ist:
          (a) Auckland-Vermerk Morgen-Slot mit Zieltag = UTC-Tag (in Ortszeit
              gestern); (b) LA-Vermerk Abend-Slot mit Zieltag = morgen (Ortszeit).
    WHEN  der stuendliche Compare-Vorlauf laeuft.
    THEN  (a) wird nicht zugestellt und ist entfernt; (b) wird nicht verworfen,
          sondern nachgeholt (Zustellung fuer seinen Zieltag).

    RED heute: (a) bleibt liegen, (b) wird nie zugestellt.
    """
    from services.compare_slot_scheduler import preset_ortstag

    uid = nutzer_anlegen()
    _orte(uid, {"loc-ibk": ("Auckland", -36.85, 174.76),
                "loc-bz": ("Los Angeles", 34.05, -118.24)})
    pid_nz = _vergleich(uid, _pid("ac7-nz"), name="Vergleich Neuseeland", orte=["loc-ibk"])
    pid_la = _vergleich(uid, _pid("ac7-la"), name="Vergleich Kalifornien", orte=["loc-bz"],
                        abend="19:00:00")
    jetzt = datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)
    utc_tag = jetzt.date()
    nz_tag = jetzt.astimezone(ZoneInfo("Pacific/Auckland")).date()
    la_tag = jetzt.astimezone(ZoneInfo("America/Los_Angeles")).date()
    assert nz_tag == utc_tag + timedelta(days=1) and la_tag == utc_tag, "Vorbedingung Zonen"
    from app.loader import load_all_locations

    by_id = {o.id: o for o in load_all_locations(user_id=uid)}
    assert preset_ortstag(preset_laden(uid, pid_nz), by_id, jetzt) == nz_tag
    assert preset_ortstag(preset_laden(uid, pid_la), by_id, jetzt) == la_tag

    _ablage_schreiben(uid, [
        _vermerk(pid_nz, "morning", utc_tag, 7),
        _vermerk(pid_la, "evening", la_tag + timedelta(days=1), 19),
    ])

    _lauf(uid, jetzt)

    assert _mails(aus, "Neuseeland") == [], (
        f"AC-7: ein in Ortszeit abgelaufener Vermerk darf nichts zustellen: {aus.mit!r}"
    )
    assert pid_nz not in {e.get("preset_id") for e in _vergleich_vermerke(uid)}, (
        f"AC-7: der in Ortszeit abgelaufene Vermerk muss entfernt sein: {_ablage(uid)!r}"
    )
    la_mails = _mails(aus, "Kalifornien")
    assert len(la_mails) == 1, (
        "AC-7: ein Vermerk, dessen Zieltag in Ortszeit noch bevorsteht, darf nicht "
        f"verworfen werden (Nachholen erwartet): {aus.mit!r}, Ablage {_ablage(uid)!r}"
    )
    assert (la_tag + timedelta(days=1)).strftime("%d.%m.%Y") in la_mails[0]["subject"], la_mails[0]


# ═══════════════════════════════ AC-8 ════════════════════════════════════════


def test_ac8_abend_nachholer_nach_mitternacht_wird_als_abend_fuer_den_zieltag_verbucht(aus):
    """AC-8.

    GIVEN ein Abend-Vermerk (Slot 19:00, Zieltag D) und der Nachhol-Lauf findet
          um 01:00 Ortszeit an D statt (Zieltag ist nun "heute").
    WHEN  der Vorlauf den Vermerk nachholt.
    THEN  verbucht die Versand-Historie den Eintrag als "evening" (nicht
          "morning"), und Betreff/Wetterabruf beziehen sich auf D.

    RED heute: es wird nichts nachgeholt (kein Historien-Eintrag).
    """
    uid = _nutzer()
    pid = _vergleich(uid, _pid("ac8"), abend="19:00:00")
    _ablage_schreiben(uid, [_vermerk(pid, "evening", D, 19)])

    _lauf(uid, _utc(D, 1))

    eintraege = [e for e in _briefing_log(uid) if e.get("entity_id") == pid]
    assert len(eintraege) == 1, (
        f"AC-8: genau ein Historien-Eintrag fuer den Nachholer erwartet: {_briefing_log(uid)!r}"
    )
    assert eintraege[0].get("kind") == "evening", (
        f"AC-8: der Abend-Nachholer muss als 'evening' verbucht sein: {eintraege[0]!r}"
    )
    assert eintraege[0].get("on_demand") is False, eintraege[0]
    mails = aus.mit.sendungen("email")
    assert len(mails) == 1 and D.strftime("%d.%m.%Y") in mails[0]["subject"], mails
    assert aus.ziel_tage and set(aus.ziel_tage) == {D}, (
        f"AC-8: Tagesbezug muss der Zieltag sein: {aus.ziel_tage!r}"
    )


# ═══════════════════════════════ AC-9 ════════════════════════════════════════


def test_ac9a_regulaerer_slot_mit_gleichem_zieltag_ersetzt_das_nachholen(aus):
    """AC-9 (a).

    GIVEN ein Abend-Vermerk fuer D, und um 07:00 an D faellt der Morgen-Slot
          desselben Presets fuer D an (gleicher Zieltag), Versand ok.
    WHEN  der Compare-Lauf dieser Stunde beendet ist.
    THEN  genau EINE Zustellung (die regulaere), der Vermerk ist danach entfernt.

    RED heute: der Vermerk bleibt liegen.
    """
    uid = _nutzer()
    pid = _vergleich(uid, _pid("ac9a"), abend="19:00:00")
    _ablage_schreiben(uid, [_vermerk(pid, "evening", D, 19)])

    _lauf(uid, _utc(D, 7))

    assert len(aus.mit.sendungen("email")) == 1, (
        f"AC-9a: genau eine Zustellung (die regulaere), kein Doppel: {aus.mit!r}"
    )
    assert _vergleich_vermerke(uid) == [], (
        "AC-9a: nach gelungener regulaerer Zustellung fuer denselben Zieltag muss "
        f"der Vermerk weg sein: {_ablage(uid)!r}"
    )


def test_ac9b_scheitert_der_regulaere_slot_bleibt_der_vermerk_fuer_die_folgestunde(aus):
    """AC-9 (b), Bestandsabsicherung.

    GIVEN wie (a), aber die regulaere Zustellung scheitert.
    WHEN  der Compare-Lauf dieser Stunde beendet ist.
    THEN  bleibt der Abend-Vermerk fuer D bestehen, und es gab keinen
          zusaetzlichen Nachhol-Versuch neben dem regulaeren.
    """
    uid = _nutzer()
    pid = _vergleich(uid, _pid("ac9b"), abend="19:00:00")
    _ablage_schreiben(uid, [_vermerk(pid, "evening", D, 19)])
    aus.stoerung.add("email")

    _lauf(uid, _utc(D, 7))

    assert aus.versuche["email"] == 1, (
        f"AC-9b: nur der regulaere Versuch, kein zusaetzliches Nachholen: {aus.versuche!r}"
    )
    assert (pid, "evening", D.isoformat(), 19) in _schluessel(uid), (
        f"AC-9b: der Vermerk muss fuer die Folgestunde bestehen bleiben: {_ablage(uid)!r}"
    )


def test_ac9c_regulaerer_slot_mit_anderem_zieltag_wird_zusaetzlich_nachgeholt(aus):
    """AC-9 (c).

    GIVEN ein Morgen-Vermerk fuer D (07:00 gescheitert), und um 19:00 an D
          faellt nur der Abend-Slot (Zieltag D+1) an.
    WHEN  der Compare-Lauf dieser Stunde beendet ist.
    THEN  zwei Zustellungen: die regulaere fuer D+1 und die nachgeholte fuer D;
          danach kein Vermerk mehr.

    RED heute: nur die regulaere Zustellung.
    """
    uid = _nutzer()
    pid = _vergleich(uid, _pid("ac9c"), abend="19:00:00")
    _ablage_schreiben(uid, [_vermerk(pid, "morning", D, 7)])

    _lauf(uid, _utc(D, 19))

    betreffe = sorted(m["subject"] for m in aus.mit.sendungen("email"))
    assert len(betreffe) == 2, f"AC-9c: regulaer + nachgeholt erwartet: {betreffe!r}"
    assert any(D.strftime("%d.%m.%Y") in b for b in betreffe), betreffe
    assert any((D + timedelta(days=1)).strftime("%d.%m.%Y") in b for b in betreffe), betreffe
    assert _vergleich_vermerke(uid) == [], _ablage(uid)


def test_ac9_folgefall_mehrere_vermerke_gleicher_zieltag_ergeben_genau_eine_nachholung(aus):
    """AC-9-Grundsatz, Folgefall aus AC-9b (Orchestrator-Entscheidung, Spec §3).

    GIVEN zwei Vermerke desselben Presets mit demselben Zieltag D (Abend 19:00
          vom Vortag und Morgen 07:00 von D), um 10:00 an D ist kein Slot faellig.
    WHEN  der stuendliche Compare-Vorlauf laeuft.
    THEN  genau EINE Zustellung (Hinweis mit der fruehesten Slot-Stunde 07:00),
          beide Vermerke sind entfernt.
    """
    uid = _nutzer()
    pid = _vergleich(uid, _pid("ac9-dedup"), abend="19:00:00")
    _ablage_schreiben(uid, [_vermerk(pid, "evening", D, 19), _vermerk(pid, "morning", D, 7)])

    _lauf(uid, _utc(D, 10))

    mails = aus.mit.sendungen("email")
    assert len(mails) == 1, f"Je Preset und Zieltag hoechstens eine Nachholung: {aus.mit!r}"
    assert _HINWEIS_RE.match(mails[0]["plain_text_body"] or ""), mails[0]["plain_text_body"][:200]
    assert _vergleich_vermerke(uid) == [], _ablage(uid)


def test_ac9_folgefall_gescheiterte_einzelnachholung_vermerkt_den_fruehesten_slot(aus):
    """Wie oben, aber der Nachholversand scheitert: genau EIN frischer Vermerk
    mit den Werten des Vermerks mit der fruehesten Slot-Stunde."""
    uid = _nutzer()
    pid = _vergleich(uid, _pid("ac9-dedup-fehl"), abend="19:00:00")
    _ablage_schreiben(uid, [_vermerk(pid, "evening", D, 19), _vermerk(pid, "morning", D, 7)])
    aus.stoerung.add("email")

    _lauf(uid, _utc(D, 10))

    assert aus.versuche["email"] == 1, f"genau ein Nachholversuch: {aus.versuche!r}"
    assert _schluessel(uid) == {(pid, "morning", D.isoformat(), 7)}, _ablage(uid)


# ═══════════════════════════════ AC-10 ═══════════════════════════════════════


def test_ac10_stillgelegt_abgelaufen_oder_geloescht_verwirft_den_vermerk_ohne_versand(aus):
    """AC-10.

    GIVEN drei Vermerke zu drei Presets: pausiert (``paused_at``), abgelaufen
          (``end_date`` in der Vergangenheit), geloescht (keine Datei); dazu ein
          Trip-Vermerk.
    WHEN  der stuendliche Compare-Vorlauf laeuft (10:00, kein Slot faellig).
    THEN  wird nichts gesendet, alle drei Vermerke sind entfernt, der
          Trip-Vermerk bleibt byte-gleich.

    RED heute: Versandzaehler 0 (gruen), aber die Vermerke bleiben liegen.
    """
    uid = _nutzer()
    pid_pause = _vergleich(uid, _pid("ac10-pause"), paused_at="2026-07-01T00:00:00Z")
    pid_ende = _vergleich(uid, _pid("ac10-ende"), end_date="2026-01-01")
    pid_weg = _pid("ac10-weg")  # keine Preset-Datei
    trip = _trip_vermerk("trip-ac10")
    _ablage_schreiben(uid, [
        _vermerk(pid_pause, "morning", D, 7),
        _vermerk(pid_ende, "morning", D, 7),
        _vermerk(pid_weg, "morning", D, 7),
        trip,
    ])

    _lauf(uid, _utc(D, 10))

    assert aus.mit.kanaele == [], f"AC-10: nichts senden: {aus.mit!r}"
    assert _vergleich_vermerke(uid) == [], (
        f"AC-10: Vermerke stillgelegter/abgelaufener/geloeschter Presets verwerfen: {_ablage(uid)!r}"
    )
    assert [_kanon(e) for e in _ablage(uid) if e.get("trip_id")] == [_kanon(trip)], _ablage(uid)


# ═══════════════════════════════ AC-11 ═══════════════════════════════════════


def test_ac11_nur_der_regulaere_erfolg_desselben_presets_und_slots_raeumt_den_vermerk(aus):
    """AC-11.

    GIVEN Vermerke (A, Morgen, D), (A, Abend, D+1), (B, Morgen, D).
    WHEN  erst ein On-Demand-Versand von A erfolgreich zustellt, dann der
          regulaere Morgen-Versand von A (Cron-Wrapper ``_dispatch_due_preset``,
          Versatz 0) erfolgreich zustellt.
    THEN  aendert der On-Demand-Erfolg nichts; nach dem regulaeren Erfolg ist
          nur (A, Morgen, D) entfernt.

    RED heute: der regulaere Erfolg raeumt nichts.
    """
    from services.scheduler_dispatch_service import _dispatch_due_preset, send_one_compare_preset
    from tests.tdd._compare_kette_fixtures import alle_orte

    uid = _nutzer()
    pid_a = _vergleich(uid, _pid("ac11-a"), abend="19:00:00")
    pid_b = _vergleich(uid, _pid("ac11-b"), abend="19:00:00")
    _ablage_schreiben(uid, [
        _vermerk(pid_a, "morning", D, 7),
        _vermerk(pid_a, "evening", D + timedelta(days=1), 19),
        _vermerk(pid_b, "morning", D, 7),
    ])
    vorher = _schluessel(uid)

    send_one_compare_preset(
        preset_laden(uid, pid_a), settings_fuer(uid), uid, str(get_data_root()),
        all_locations_cache=alle_orte(uid), target_date=D, tage_ab_ortstag=0,
        on_demand=True,
    )
    assert len(aus.mit.sendungen("email")) == 1, "Vorbedingung: On-Demand hat zugestellt"
    assert _schluessel(uid) == vorher, (
        f"AC-11: ein On-Demand-Erfolg darf keinen Vermerk raeumen: {_ablage(uid)!r}"
    )

    assert _dispatch_due_preset(
        preset_laden(uid, pid_a), D, settings_fuer(uid), uid, str(get_data_root()),
        alle_orte(uid), tage_ab_ortstag=0,
    ) == "sent", "Vorbedingung: regulaerer Versand gelungen (#1777: Ausgang statt bool)"
    assert _schluessel(uid) == vorher - {(pid_a, "morning", D.isoformat(), 7)}, (
        "AC-11: nach regulaerem Erfolg darf genau (A, Morgen) fehlen, alles andere "
        f"bleibt: {_ablage(uid)!r}"
    )


# ═══════════════════════════════ AC-12 ═══════════════════════════════════════


def test_ac12_morgen_und_abend_vermerk_koexistieren_und_verfallen_unabhaengig(aus):
    """AC-12.

    GIVEN ein Preset mit Morgen- (07:00) und Abend-Slot (19:00), dessen Versand
          dauerhaft scheitert.
    WHEN  beide Slot-Laeufe an D beendet sind, und spaeter um 03:00 an D+1.
    THEN  liegen zwei getrennte Vermerke vor (morning/D/7, evening/D+1/19); nach
          dem Lauf an D+1 ist der Morgen-Vermerk verfallen, der Abend-Vermerk
          besteht weiter.

    RED heute: es entsteht kein Vermerk.
    """
    uid = _nutzer()
    pid = _vergleich(uid, _pid("ac12"), abend="19:00:00")
    aus.stoerung.add("email")

    _lauf(uid, _utc(D, 7))
    _lauf(uid, _utc(D, 19))

    morgen = (pid, "morning", D.isoformat(), 7)
    abend = (pid, "evening", (D + timedelta(days=1)).isoformat(), 19)
    assert _schluessel(uid) == {morgen, abend}, (
        f"AC-12: zwei getrennte Vermerke mit verschiedenen Zieltagen erwartet: {_ablage(uid)!r}"
    )

    _lauf(uid, _utc(D + timedelta(days=1), 3))

    assert morgen not in _schluessel(uid), f"AC-12: Morgen-Vermerk muss verfallen: {_ablage(uid)!r}"
    assert abend in _schluessel(uid), (
        f"AC-12: der Verfall des Morgen-Vermerks darf den Abend-Vermerk nicht treffen: {_ablage(uid)!r}"
    )


# ═══════════════════════════════ AC-13 ═══════════════════════════════════════


def test_ac13_vermerke_nachholen_und_verfall_bleiben_beim_eigenen_nutzer(aus):
    """AC-13 (Zwei-Nutzer-Pflicht).

    GIVEN zwei Nutzer mit verschiedenen Kennungen und Empfaengern, je ein
          Ortsvergleich, beide scheitern um 07:00 an D.
    WHEN  beide Vermerke geschrieben sind; dann laeuft fuer Nutzer 1 der
          Vorlauf an D+1 03:00 (Verfall) und fuer Nutzer 2 an D 10:00
          (Nachholen, Kanal wieder ok).
    THEN  liegt jeder Vermerk nur in der eigenen Ablage; Verfall und Nachholen
          aendern die Ablage des anderen Nutzers nicht; das Nachholen erreicht
          nur die Empfaenger von Nutzer 2.

    RED heute: es entstehen keine Vermerke.
    """
    u1, u2 = _nutzer(), _nutzer()
    assert u1 != u2 and _mail_to(u1) != _mail_to(u2), "Vorbedingung: zwei echte Nutzer"
    p1 = _vergleich(u1, _pid("ac13-eins"), name="Vergleich Eins")
    p2 = _vergleich(u2, _pid("ac13-zwei"), name="Vergleich Zwei")
    aus.stoerung.add("email")

    _lauf(u1, _utc(D, 7))
    _lauf(u2, _utc(D, 7))

    assert {e.get("preset_id") for e in _vergleich_vermerke(u1)} == {p1}, (
        f"AC-13: Nutzer 1 muss genau seinen eigenen Vermerk tragen: {_ablage(u1)!r}"
    )
    assert {e.get("preset_id") for e in _vergleich_vermerke(u2)} == {p2}, (
        f"AC-13: Nutzer 2 muss genau seinen eigenen Vermerk tragen: {_ablage(u2)!r}"
    )

    aus.stoerung.clear()
    aus.mit.leeren()
    u2_vorher = _pfad(u2).read_bytes()
    _lauf(u1, _utc(D + timedelta(days=1), 3))
    assert _pfad(u2).read_bytes() == u2_vorher, "AC-13: Verfall bei Nutzer 1 aendert Nutzer 2"
    assert _vergleich_vermerke(u1) == [], f"Nutzer 1: Vermerk verfallen: {_ablage(u1)!r}"
    assert aus.mit.kanaele == [], f"Verfall stellt nichts zu: {aus.mit!r}"

    u1_vorher = _pfad(u1).read_bytes()
    _lauf(u2, _utc(D, 10))
    assert _pfad(u1).read_bytes() == u1_vorher, "AC-13: Nachholen bei Nutzer 2 aendert Nutzer 1"
    assert aus.mit.empfaenger("email") == [_mail_to(u2)], (
        f"AC-13: das Nachholen erreicht nur die Empfaenger von Nutzer 2: {aus.mit!r}"
    )
    assert _vergleich_vermerke(u2) == [], f"Nutzer 2: nachgeholt, Vermerk weg: {_ablage(u2)!r}"


# ═════════════════════ Fix-Loop 1 (Adversary F001-F008) ══════════════════════


def test_f001_f002_nachholer_zaehlt_im_laufergebnis_sent_failed_no_channels_neutral(aus):
    """Spec §3 Punkt 6, beobachtet am Rueckgabewert des echten Laufs (sent, failed).

    GIVEN je ein Vermerk um 10:00 an D (kein Slot faellig): (a) Kanal ok,
          (b) E-Mail gestoert, (c) kein wirksamer Kanal (no_channels).
    THEN  (a) (1, 0), (b) (0, 1), (c) (0, 0) -- no_channels ist neutral.
    """
    uid = _nutzer()
    pid = _vergleich(uid, _pid("f001-ok"))
    _ablage_schreiben(uid, [_vermerk(pid, "morning", D, 7)])
    assert tuple(_lauf(uid, _utc(D, 10))) == (1, 0), "F001: erfolgreicher Nachholer = sent+1"

    uid = _nutzer()
    pid = _vergleich(uid, _pid("f001-fehl"))
    _ablage_schreiben(uid, [_vermerk(pid, "morning", D, 7)])
    aus.stoerung.add("email")
    assert tuple(_lauf(uid, _utc(D, 10))) == (0, 1), "F001: gescheiterter Nachholer = failed+1"
    aus.stoerung.clear()

    uid = _nutzer()
    pid = _vergleich(uid, _pid("f002-ohne-kanal"))
    hv.profil_ohne_mail_to(uid)
    _ablage_schreiben(uid, [_vermerk(pid, "morning", D, 7)])
    assert tuple(_lauf(uid, _utc(D, 10))) == (0, 0), "F002: no_channels zaehlt neutral"


def test_f003_abend_nachholer_am_selben_abend_traegt_versatz_eins_bis_zum_anker(aus, monkeypatch):
    """Spec §3 Punkt 5 (Vertrag #1661), beobachtet dort, wo der Versatz wirkt.

    GIVEN ein Abend-Vermerk (19:00, Zieltag D+1), Nachholen um 20:00 an D
          (vor Mitternacht Ortszeit, kein Slot faellig).
    THEN  der Alarm-Anker wird mit ``tage_ab_ortstag == 1`` geschrieben und das
          zugestellte Briefing gilt D+1.
    """
    import services.scheduler_dispatch_service as sds

    anker: list = []
    monkeypatch.setattr(sds, "_write_compare_alert_snapshots",
                        lambda pid, locs, uid, preset, tage_ab_ortstag: anker.append(tage_ab_ortstag))
    uid = _nutzer()
    pid = _vergleich(uid, _pid("f003"), abend="19:00:00")
    _ablage_schreiben(uid, [_vermerk(pid, "evening", D + timedelta(days=1), 19)])

    _lauf(uid, _utc(D, 20))

    mails = aus.mit.sendungen("email")
    assert len(mails) == 1 and (D + timedelta(days=1)).strftime("%d.%m.%Y") in mails[0]["subject"], mails
    assert anker == [1], f"F003: Abend-Nachholer am selben Abend = Versatz 1: {anker!r}"


def test_f004_regulaerer_erfolg_raeumt_gleichen_slot_mit_altem_zieltag_aber_keinen_anderen_grund(aus):
    """Spec §2: Raeumen nach Slot ODER Zieltag, nur ``reason == "dispatch_error"``.

    GIVEN (A, Morgen, D-1, dispatch_error) und (A, Morgen, D, anderer Grund).
    WHEN  der regulaere Morgen-Versand von A fuer D erfolgreich zustellt.
    THEN  der alte Versandfehler-Vermerk ist weg, der Vermerk mit anderem Grund bleibt.
    """
    from services.scheduler_dispatch_service import _dispatch_due_preset
    from tests.tdd._compare_kette_fixtures import alle_orte

    uid = _nutzer()
    pid = _vergleich(uid, _pid("f004"))
    anders = dict(_vermerk(pid, "morning", D, 7), reason="weather_outage")
    _ablage_schreiben(uid, [_vermerk(pid, "morning", D - timedelta(days=1), 7), anders])

    assert _dispatch_due_preset(
        preset_laden(uid, pid), D, settings_fuer(uid), uid, str(get_data_root()),
        alle_orte(uid), tage_ab_ortstag=0,
    ) == "sent"  # #1777: Ausgang statt bool
    assert [_kanon(e) for e in _vergleich_vermerke(uid)] == [_kanon(anders)], _ablage(uid)


def test_f005_rueckfall_konto_default_bekommt_nie_einen_vermerk(aus):
    """Spec §1 / CLAUDE.md: nie ``"default"`` als user_id. Gegenprobe mit echtem Nutzer."""
    from services.scheduler_dispatch_service import _mark_compare_undelivered

    _mark_compare_undelivered("default", "vgl-f005", "morning", D, 7)
    assert not _pfad("default").exists(), "F005: unter 'default' darf kein Vermerk entstehen"

    uid = _nutzer()
    _mark_compare_undelivered(uid, "vgl-f005", "morning", D, 7)
    assert _schluessel(uid) == {("vgl-f005", "morning", D.isoformat(), 7)}, "Gegenprobe"


def test_f007_nicht_schreibbare_ablage_verdeckt_den_versandfehler_nicht(aus):
    """Spec Datenmodell (fail-soft): ein Schreibfehler der Ablage darf den
    urspruenglichen Versandfehler nicht ersetzen."""
    from services.scheduler_dispatch_service import send_one_compare_preset
    from tests.tdd._compare_kette_fixtures import alle_orte

    uid = _nutzer()
    pid = _vergleich(uid, _pid("f007-ablage"))
    _pfad(uid).mkdir(parents=True)  # Ablage ist ein Ordner -> nicht schreibbar
    aus.stoerung.add("email")
    with pytest.raises(RuntimeError, match="Mail-Gateway"):
        send_one_compare_preset(
            preset_laden(uid, pid), settings_fuer(uid), uid, str(get_data_root()),
            all_locations_cache=alle_orte(uid), target_date=D, tage_ab_ortstag=0,
        )


def test_f007_trip_marker_funktion_trifft_keinen_vergleichs_vermerk(aus):
    """Blocker §5, Filter in ``_trip_marker`` einzeln: ``_remove_pending_marker(None)``
    (Trip-Eintrag ohne trip_id) darf den Ortsvergleich-Vermerk nicht loeschen."""
    from services.trip_report_scheduler import TripReportSchedulerService

    uid = _nutzer()
    vgl = _vermerk("vgl-f007", "morning", D, 7)
    _ablage_schreiben(uid, [vgl, _trip_vermerk("trip-x")])

    svc = TripReportSchedulerService(settings=settings_fuer(uid), user_id=uid)
    svc._remove_pending_marker(None)
    svc._bump_pending_marker_attempts(None)
    svc._clear_dispatch_error_marker(None)

    assert [_kanon(e) for e in _vergleich_vermerke(uid)] == [_kanon(vgl)], _ablage(uid)


def test_f008_nachholer_ohne_wetterdaten_bleibt_vermerkt_ohne_kanal_nicht(aus, monkeypatch):
    """Tech-Lead-Entscheidung F008 (Spec §3 Punkt 4).

    GIVEN ein Vermerk um 10:00 an D. (a) Der Nachholversand endet mit
          no_weather (voruebergehend). (b) Er endet mit no_channels.
    THEN  (a) der Vermerk bleibt mit den Original-Werten; er altert ehrlich
          (Fix-Loop 2, ADR-0018): ``created_at`` des Originals, ``attempts`` + 1;
          (b) kein Vermerk (Konfigurationsfehler).
    """
    uid = _nutzer()
    pid = _vergleich(uid, _pid("f008-wetter"))
    alt = "2026-07-01T00:00:00+00:00"
    _ablage_schreiben(uid, [_vermerk(pid, "morning", D, 7, attempts=2, created_at=alt)])
    hv.wetter_fehlt_je_ort(monkeypatch)
    _lauf(uid, _utc(D, 10))
    assert _schluessel(uid) == {(pid, "morning", D.isoformat(), 7)}, _ablage(uid)
    v = _vergleich_vermerke(uid)[0]
    assert (v["attempts"], v["created_at"]) == (3, alt), f"no_weather: altern statt frisch: {v!r}"

    uid = _nutzer()
    pid = _vergleich(uid, _pid("f008-kanal"))
    hv.profil_ohne_mail_to(uid)
    _ablage_schreiben(uid, [_vermerk(pid, "morning", D, 7)])
    _lauf(uid, _utc(D, 10))
    assert _vergleich_vermerke(uid) == [], _ablage(uid)


def test_parallele_schreiber_verlieren_keinen_vermerk(aus):
    """Nebenlaeufigkeit: trip-reports und compare-presets-daily schreiben dieselbe
    Ablage. Viele gleichzeitige Upserts verschiedener Schluessel => alle da."""
    import threading

    from services import pending_briefings as pb

    uid = _nutzer()
    pfad = pb.pending_path(uid)
    weg = [_vermerk(f"weg-{i}", "morning", D, 7) for i in range(150)]
    _ablage_schreiben(uid, [_vermerk("zaehler", "morning", D, 7), *weg])
    fehler: list = []

    def _schutz(arbeit) -> None:
        try:
            arbeit()
        except Exception as exc:  # noqa: BLE001 -- Fehler ist Pruefgegenstand
            fehler.append(exc)

    def _upserts(praefix: str) -> None:
        for i in range(150):
            pid = f"{praefix}-{i}"
            pb.upsert_entry(pfad, lambda e, p=pid: e.get("preset_id") == p,
                            _vermerk(pid, "morning", D, 7))

    def _removes() -> None:
        for e in weg:
            pb.remove_entries(pfad, lambda x, p=e["preset_id"]: x.get("preset_id") == p)

    def _bumps() -> None:
        for _ in range(150):
            pb.bump_attempts(pfad, lambda x: x.get("preset_id") == "zaehler")

    arbeiten = [lambda: _upserts("t0"), lambda: _upserts("t1"), _removes, _bumps]
    threads = [threading.Thread(target=_schutz, args=(a,)) for a in arbeiten]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert fehler == [], f"Schreibfehler unter Last: {fehler[:3]!r}"
    ids = [e["preset_id"] for e in _vergleich_vermerke(uid)]
    assert sum(i.startswith(("t0-", "t1-")) for i in ids) == 300, "Lost Update bei upsert"
    assert not any(i.startswith("weg-") for i in ids), "Lost Update bei remove"
    zaehler = [e for e in _vergleich_vermerke(uid) if e["preset_id"] == "zaehler"]
    assert [e["attempts"] for e in zaehler] == [150], "Lost Update bei bump"


def test_upsert_legt_fehlenden_nutzerordner_an(aus, tmp_path):
    """Sperre: der Ordner fuer Lock-Datei und Ablage entsteht beim ersten Schreiben."""
    from services import pending_briefings as pb

    pfad = tmp_path / "neu" / "pending_briefings.json"
    pb.upsert_entry(pfad, lambda e: False, _vermerk("vgl-neu", "morning", D, 7))
    assert json.loads(pfad.read_text())["entries"][0]["preset_id"] == "vgl-neu"


def test_f009_nachholer_mit_wetter_ausnahme_bleibt_vermerkt(aus, monkeypatch):
    """F009: die Wetterabfrage WIRFT beim Nachholen (nicht nur Fehler je Ort)
    -> no_weather, der Vermerk bleibt fuer die naechste Stunde."""
    uid = _nutzer()
    pid = _vergleich(uid, _pid("f009"))
    _ablage_schreiben(uid, [_vermerk(pid, "morning", D, 7)])
    hv.wetter_faellt_ueberall_aus(monkeypatch)

    _lauf(uid, _utc(D, 10))

    assert aus.mit.kanaele == [], aus.mit
    assert _schluessel(uid) == {(pid, "morning", D.isoformat(), 7)}, _ablage(uid)


def test_f010_abend_vermerk_ohne_wetterdaten_behaelt_slot_zieltag_und_stunde(aus, monkeypatch):
    """F010: no_weather mit einem Abend-Vermerk (Zieltag D+1, 19:00), Nachholen
    um 20:00 an D -> der Vermerk traegt weiter evening / D+1 / 19."""
    uid = _nutzer()
    pid = _vergleich(uid, _pid("f010"), abend="19:00:00")
    _ablage_schreiben(uid, [_vermerk(pid, "evening", D + timedelta(days=1), 19)])
    hv.wetter_fehlt_je_ort(monkeypatch)

    _lauf(uid, _utc(D, 20))

    assert _schluessel(uid) == {(pid, "evening", (D + timedelta(days=1)).isoformat(), 19)}, (
        _ablage(uid)
    )
