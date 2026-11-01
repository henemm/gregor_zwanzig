"""#2280: kind-neutraler Handversand ``POST /api/briefings/{id}/send``.

Spec: docs/specs/modules/feat_2280_handversand_endpoint.md
(AC-1, AC-2, AC-3, AC-9, AC-10, AC-13 — Python-Kern-Schicht)

Echte Kette: TestClient gegen ``api.main.app`` -> Router -> Trip- bzw.
Vergleichs-Versand -> NotificationService. Naehte nur zum Netz bzw. zur
Konfigurationslage (siehe ``tests/tdd/_handversand_fixtures.py``). Kein
Mock-Theater, kein Dateiinhalt-Check.

``services.send_outcomes`` wird nur in den Tests importiert, die das
Vokabular als Datenstruktur bzw. als Textquelle der Antworten pruefen.

Zwei-Nutzer-Pflicht (CLAUDE.md): AC-3 prueft Nutzer A und Nutzer B.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from services import send_lock
from tests.helpers.transport_mitschrift import Kanalmitschrift, aufzeichner_installieren
from tests.tdd import _handversand_fixtures as hv
from tests.tdd._compare_kette_fixtures import (
    engine_naht,
    fixture_dict,
    nutzer_anlegen,
    orte_anlegen,
    preset_ablegen,
    transport_einrichten,
)


# ---------------------------------------------------------------------------
# Aufbau
# ---------------------------------------------------------------------------


class _Lage:
    """Gemeinsame Naehte eines Testlaufs: Trip-Mails + Vergleichs-Kanaele."""

    def __init__(self, trip_mails: list, mit: Kanalmitschrift) -> None:
        self.trip_mails = trip_mails
        self.mit = mit

    @property
    def nichts_versendet(self) -> bool:
        return not self.trip_mails and not self.mit.kanaele

    def __repr__(self) -> str:
        return f"_Lage(trip_mails={self.trip_mails!r}, {self.mit!r})"


@pytest.fixture
def lage(monkeypatch) -> _Lage:
    transport_einrichten(monkeypatch)
    engine_naht(monkeypatch)
    trip_mails = hv.trip_naehte(monkeypatch)
    mit = aufzeichner_installieren(monkeypatch)
    return _Lage(trip_mails, mit)


@pytest.fixture
def c():
    return hv.client()


def _vergleich_anlegen(uid: str, preset_id: str, location_ids=None, *,
                       telegram: bool = False, sms: bool = False) -> str:
    roh = fixture_dict("basis")
    roh["id"] = preset_id
    roh["send_telegram"] = telegram
    roh["send_sms"] = sms
    if location_ids is not None:
        roh["location_ids"] = location_ids
    orte_anlegen(uid)
    preset_ablegen(uid, roh)
    return preset_id


def _nutzer_mit_trip_und_vergleich() -> tuple[str, str, str]:
    uid = nutzer_anlegen()
    hv.trip_anlegen(uid, "trip-hv")
    _vergleich_anlegen(uid, "vgl-hv")
    return uid, "trip-hv", "vgl-hv"


# ---------------------------------------------------------------------------
# AC-1 — neuer Endpoint stellt beide Arten zu
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac1_neuer_endpoint_stellt_beide_arten_zu(lage, c, kind):
    """Given Nutzer mit Trip und Ortsvergleich, je ein wirksamer Kanal /
    When POST /api/briefings/{id}/send?kind=... / Then 200 mit status ok,
    kind, id, sent:true und eine echte Zustellung."""
    uid, trip_id, vgl_id = _nutzer_mit_trip_und_vergleich()
    entity_id = trip_id if kind == "route" else vgl_id

    r = hv.neu_senden(c, entity_id, uid, kind)

    assert r.status_code == 200, f"Erwartet 200, bekommen {r.status_code}: {r.text}"
    b = hv.body(r)
    assert b.get("status") == "ok", b
    assert b.get("kind") == kind, b
    assert b.get("id") == entity_id, b
    assert b.get("sent") is True, b
    if kind == "route":
        assert len(lage.trip_mails) == 1, f"Trip-Briefing nicht zugestellt: {lage}"
    else:
        assert lage.mit.kanaele == ["email"], f"Vergleich nicht zugestellt: {lage}"


# ---------------------------------------------------------------------------
# AC-2 — kind ist Pflicht
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("falsches_kind", ["trip", "compare", "ROUTE"])
def test_ac2_ungueltiges_kind_liefert_400_kind_required(lage, c, falsches_kind):
    """Given ein gueltiger Trip / When kind ungueltig (z.B. das Frontend-Wort
    'trip') / Then 400 mit code 'kind_required', nichts versendet."""
    uid, trip_id, _ = _nutzer_mit_trip_und_vergleich()

    r = hv.neu_senden(c, trip_id, uid, falsches_kind)

    assert r.status_code == 400, f"Erwartet 400, bekommen {r.status_code}: {r.text}"
    assert hv.body(r).get("code") == "kind_required", hv.body(r)
    assert isinstance(hv.body(r).get("detail"), str) and len(hv.body(r)["detail"]) > 10, hv.body(r)
    assert lage.nichts_versendet, f"Bei kind_required darf nichts versendet sein: {lage}"


def test_ac2_fehlendes_kind_liefert_400_kind_required_ohne_versand(lage, c):
    """Given ein gueltiger Trip / When kind fehlt / Then 400 mit code
    'kind_required' und deutschem detail aus dem Vokabular (AC-2) — nicht
    FastAPIs 422-Validierungsfehler — und KEIN Versand."""
    uid, trip_id, _ = _nutzer_mit_trip_und_vergleich()

    r = hv.neu_senden(c, trip_id, uid, None)

    assert r.status_code == 400, f"Erwartet 400, bekommen {r.status_code}: {r.text}"
    b = hv.body(r)
    assert b.get("code") == "kind_required", b
    from services.send_outcomes import error_body  # noqa: PLC0415

    # #2671: SEND_OUTCOMES haelt Katalogschluessel; der Text kommt aus error_body.
    assert b.get("detail") == error_body("kind_required")[1]["detail"], b
    assert lage.nichts_versendet, f"Ohne kind darf nichts versendet sein: {lage}"


# ---------------------------------------------------------------------------
# AC-3 — Eigentuemerschaft, zwei echte Nutzer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac3_fremde_id_liefert_404_not_found_und_loest_bei_a_nichts_aus(lage, c, kind):
    """Given A besitzt Trip + Vergleich, B ist angemeldet / When B die ID von A
    aufruft / Then 404 mit code 'not_found', bei A nichts ausgeloest (kein
    Versand, kein gespeicherter Versand-Status). Kontroll-Bein: A selbst
    bekommt 200 — sonst waere das 404 vakuum."""
    a, trip_a, vgl_a = _nutzer_mit_trip_und_vergleich()
    b = nutzer_anlegen()  # eigener Nutzer OHNE Briefing unter A's Kennung
    entity_id = trip_a if kind == "route" else vgl_a
    vorbedingung = hv.alt_senden(c, kind, entity_id, b, report_type="morning")
    assert vorbedingung.status_code == 404, (
        f"Vorbedingung: der user-scoped Loader kennt A's ID fuer B nicht: {vorbedingung.text}"
    )

    r = hv.neu_senden(c, entity_id, b, kind)

    assert r.status_code == 404, f"Erwartet 404 fuer fremde ID, bekommen {r.status_code}: {r.text}"
    assert hv.body(r).get("code") == "not_found", (
        f"Fachliches not_found erwartet, nicht das Routing-404: {hv.body(r)}"
    )
    assert lage.nichts_versendet, f"Fremder Aufruf darf nichts versenden: {lage}"
    assert hv.letzter_versand(a, vgl_a) is None, "Bei A darf kein Versand-Status entstehen"

    kontrolle = hv.neu_senden(c, entity_id, a, kind)
    assert kontrolle.status_code == 200, (
        f"Kontroll-Bein: A muss das eigene Briefing senden koennen: {kontrolle.text}"
    )


@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac3_unbekannte_id_liefert_404_not_found(lage, c, kind):
    uid, _, _ = _nutzer_mit_trip_und_vergleich()

    r = hv.neu_senden(c, "gibt-es-nicht-2280", uid, kind)

    assert r.status_code == 404, r.text
    assert hv.body(r).get("code") == "not_found", hv.body(r)
    assert isinstance(hv.body(r).get("detail"), str) and hv.body(r)["detail"] != "Not Found", (
        f"Fachlicher deutscher Text erwartet, nicht das Routing-'Not Found': {hv.body(r)}"
    )
    assert lage.nichts_versendet, lage


@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac3_nutzerkontext_kommt_aus_dem_query_nicht_aus_dem_koerper(lage, c, kind):
    """Given A besitzt das Briefing / When der Aufruf als B (Query, vom
    Go-Proxy aus der Anmeldung gesetzt) kommt und im Koerper ein 'user_id' von A
    mitschickt / Then gilt der Query-Nutzer B -> 404, nichts versendet."""
    a, trip_a, vgl_a = _nutzer_mit_trip_und_vergleich()
    b = nutzer_anlegen()
    entity_id = trip_a if kind == "route" else vgl_a

    r = c.post(
        hv.NEU.format(id=entity_id),
        params={"user_id": b, "kind": kind},
        json={"user_id": a},
    )

    assert r.status_code == 404, f"Query-Nutzer B muss gelten, bekommen {r.status_code}: {r.text}"
    assert hv.body(r).get("code") == "not_found", hv.body(r)
    assert lage.nichts_versendet, lage


# ---------------------------------------------------------------------------
# AC-9 / AC-13 — Fehlerszenarien je Code (beide Arten)
# ---------------------------------------------------------------------------


def _szenario(name: str, monkeypatch) -> dict:
    """Baut die Ausgangslage fuer einen Fehlerfall. Liefert kind, id, uid,
    zusaetzliche Query-Parameter, optional einen zu haltenden Lock und den
    erwarteten Code."""
    uid = nutzer_anlegen()
    if name == "route_not_found":
        return dict(kind="route", id="trip-fehlt", uid=uid, extra={}, code="not_found")
    if name == "route_no_stage":
        hv.trip_anlegen(uid, "trip-leer", stages=False)
        return dict(kind="route", id="trip-leer", uid=uid,
                    extra={"report_type": "morning"}, code="no_stage")
    if name == "route_invalid_report_type":
        hv.trip_anlegen(uid, "trip-rt")
        return dict(kind="route", id="trip-rt", uid=uid,
                    extra={"report_type": "mittag"}, code="invalid_report_type")
    if name == "route_smtp_not_configured":
        hv.trip_anlegen(uid, "trip-smtp")
        monkeypatch.setenv("GZ_SMTP_HOST", "")
        from app.config import Settings

        assert not Settings().with_user_profile(uid).can_send_email(), "Vorbedingung: SMTP aus"
        return dict(kind="route", id="trip-smtp", uid=uid,
                    extra={"report_type": "morning"}, code="smtp_not_configured")
    if name == "route_no_channels":
        hv.trip_anlegen(uid, "trip-ohne", email=False)
        return dict(kind="route", id="trip-ohne", uid=uid,
                    extra={"report_type": "morning"}, code="no_channels")
    if name == "route_channels_unreachable":
        hv.trip_anlegen(uid, "trip-tg", email=False, telegram=True)
        hv.telegram_trip_unerreichbar(monkeypatch)
        return dict(kind="route", id="trip-tg", uid=uid,
                    extra={"report_type": "morning"}, code="channels_unreachable")
    if name == "route_already_in_progress":
        hv.trip_anlegen(uid, "trip-lock")
        return dict(kind="route", id="trip-lock", uid=uid, extra={"report_type": "morning"},
                    lock=(uid, "trip-lock", "morning"), code="already_in_progress")
    if name == "vergleich_not_found":
        return dict(kind="vergleich", id="vgl-fehlt", uid=uid, extra={}, code="not_found")
    if name == "vergleich_no_channels":
        # echte Lage: keine mail_to im Konto, kein Telegram-/SMS-Opt-in
        _vergleich_anlegen(uid, "vgl-ohne")
        hv.profil_ohne_mail_to(uid)
        return dict(kind="vergleich", id="vgl-ohne", uid=uid, extra={}, code="no_channels")
    if name == "vergleich_channels_unreachable":
        # echte Lage: nur Telegram wirksam (keine mail_to), Transport faellt aus
        _vergleich_anlegen(uid, "vgl-tg", telegram=True)
        hv.profil_ohne_mail_to(uid)
        hv.telegram_vergleich_scheitert(monkeypatch)
        return dict(kind="vergleich", id="vgl-tg", uid=uid, extra={},
                    code="channels_unreachable")
    if name == "vergleich_no_weather":
        _vergleich_anlegen(uid, "vgl-wetter")
        hv.wetter_faellt_ueberall_aus(monkeypatch)
        return dict(kind="vergleich", id="vgl-wetter", uid=uid, extra={}, code="no_weather")
    if name == "vergleich_already_in_progress":
        _vergleich_anlegen(uid, "vgl-lock")
        return dict(kind="vergleich", id="vgl-lock", uid=uid, extra={},
                    lock=("compare", uid, "vgl-lock"), code="already_in_progress")
    # F001: unerwartete Ausnahme INNERHALB des Versands (im gesperrten Bereich,
    # also auch Lock-Freigabe mitgeprueft) -> 500 send_failed aus dem Vokabular.
    # RuntimeError, weil ValueError/KeyError bereits fachlich abgebildet sind.
    if name == "route_send_failed":
        from services.trip_report_scheduler import TripReportSchedulerService

        hv.trip_anlegen(uid, "trip-boom")
        monkeypatch.setattr(TripReportSchedulerService, "_send_trip_report_outcome",
                            _wirft_unerwartet)
        return dict(kind="route", id="trip-boom", uid=uid,
                    extra={"report_type": "morning"}, code="send_failed")
    if name == "vergleich_send_failed":
        from services import scheduler_dispatch_service

        _vergleich_anlegen(uid, "vgl-boom")
        monkeypatch.setattr(scheduler_dispatch_service, "send_one_compare_preset",
                            _wirft_unerwartet)
        return dict(kind="vergleich", id="vgl-boom", uid=uid, extra={}, code="send_failed")
    raise AssertionError(name)


def _wirft_unerwartet(*_a, **_k):
    raise RuntimeError("unerwarteter Fehler im Versand (Testausloeser)")


SZENARIEN = [
    "route_not_found", "route_no_stage", "route_invalid_report_type",
    "route_smtp_not_configured", "route_no_channels", "route_channels_unreachable",
    "route_already_in_progress", "vergleich_not_found", "vergleich_no_channels",
    "vergleich_channels_unreachable", "vergleich_no_weather",
    "vergleich_already_in_progress", "route_send_failed", "vergleich_send_failed",
]


def _aufruf(c, sz: dict, *, alt: bool):
    lock = sz.get("lock")
    if lock:
        assert send_lock.try_acquire_send_lock(*lock), "Vorbedingung: Lock frei"
    try:
        if alt:
            return hv.alt_senden(c, sz["kind"], sz["id"], sz["uid"], **sz["extra"])
        return hv.neu_senden(c, sz["id"], sz["uid"], sz["kind"], **sz["extra"])
    finally:
        if lock:
            send_lock.release_send_lock(*lock)


@pytest.mark.parametrize("name", SZENARIEN)
def test_ac9_fehlerform_des_neuen_endpoints_je_code(lage, c, monkeypatch, name):
    """Given ein Fehlerfall / When der neue Endpoint antwortet / Then Status
    laut Vokabular, ``code`` auf oberster Ebene, ``detail`` ein deutscher Text
    (String, nicht der Code selbst), und kein 'sent:true'."""
    sz = _szenario(name, monkeypatch)

    r = _aufruf(c, sz, alt=False)

    b = hv.body(r)
    assert r.status_code == hv.ERWARTETE_CODES[sz["code"]], (
        f"{name}: Status {r.status_code}, erwartet {hv.ERWARTETE_CODES[sz['code']]}: {b}"
    )
    assert b.get("code") == sz["code"], f"{name}: code auf oberster Ebene fehlt/falsch: {b}"
    detail = b.get("detail")
    assert isinstance(detail, str) and len(detail) > 10 and detail != sz["code"], (
        f"{name}: detail muss ein anzeigbarer deutscher Text sein: {b}"
    )
    assert b.get("status") != "ok" and b.get("sent") is not True, b
    assert lage.nichts_versendet, f"{name}: im Fehlerfall darf nichts zugestellt sein: {lage}"
    # Der Text kommt aus DEM Vokabular (nicht aus einer zweiten Fassung):
    # jedes feste Stueck der Vorlage steht im detail.
    eintrag = _vokabular()[sz["code"]]
    vorlage = eintrag[1] if isinstance(eintrag, (tuple, list)) else (
        getattr(eintrag, "text", None) or getattr(eintrag, "detail", "")
    )
    # #2671: das Vokabular haelt Katalogschluessel; die deutsche Vorlage kommt
    # aus dem Katalog (Nutzer dieses Tests ohne Sprache = de).
    from i18n import t  # noqa: PLC0415

    vorlage = t(vorlage, "de")
    for stueck in re.split(r"\{[^}]*\}", vorlage):
        assert stueck.strip() in detail, (
            f"{name}: detail {detail!r} stammt nicht aus send_outcomes ({vorlage!r})"
        )


@pytest.mark.parametrize("name", SZENARIEN)
def test_ac13_alt_route_antwortet_wie_der_neue_endpoint(lage, c, monkeypatch, name):
    """Given derselbe Fehlerfall / When Alt-Route und neuer Endpoint aufgerufen
    werden / Then gleicher Status, gleiches ``detail``, gleicher ``code`` —
    die Fehler-Mappings gibt es nur einmal (Delegate, AC-9 Verhaltens-Waechter)."""
    sz = _szenario(name, monkeypatch)

    alt = _aufruf(c, sz, alt=True)
    neu = _aufruf(c, sz, alt=False)

    a, n = hv.body(alt), hv.body(neu)
    assert alt.status_code == neu.status_code, (
        f"{name}: Status alt {alt.status_code} != neu {neu.status_code} ({a} / {n})"
    )
    assert a.get("code") == n.get("code") == sz["code"], f"{name}: code alt {a} / neu {n}"
    assert a.get("detail") == n.get("detail"), f"{name}: detail alt {a!r} != neu {n!r}"


@pytest.mark.parametrize("name", SZENARIEN)
def test_ac9_alt_route_hat_keine_eigenen_fehlertexte(lage, c, monkeypatch, name):
    """AC-9 Waechter (Verhalten, kein Dateiinhalt-Check): ``scheduler.py``
    enthaelt fuer diese Faelle keine eigenen Fehlertexte. Herkunftsprobe:
    der Vokabular-Eintrag wird zur Laufzeit durch einen Marker ersetzt — die
    Alt-Route MUSS den Marker liefern. Eine eigene (auch wortgleiche) Kopie
    des Texts in ``scheduler.py`` liefert ihn nicht und faellt auf."""
    from services import send_outcomes  # noqa: PLC0415

    sz = _szenario(name, monkeypatch)
    status, _text = send_outcomes.SEND_OUTCOMES[sz["code"]]
    marker = f"HERKUNFTSPROBE {sz['code']} aus send_outcomes"
    monkeypatch.setitem(send_outcomes.SEND_OUTCOMES, sz["code"], (status, marker))

    alt = _aufruf(c, sz, alt=True)

    a = hv.body(alt)
    assert alt.status_code == status, f"{name}: Status {alt.status_code}, erwartet {status}: {a}"
    assert a.get("code") == sz["code"], f"{name}: {a}"
    assert a.get("detail") == marker, (
        f"{name}: Alt-Route liefert einen eigenen Text statt des Vokabulars: {a.get('detail')!r}"
    )


_PARITAET = (
    Path(__file__).resolve().parents[1] / "fixtures" / "send_detail_parity" / "faelle.json"
)


def test_ac2_kind_required_text_gleich_der_go_fassung(lage, c):
    """F004 Paritaet Python <-> Go ohne Quelltext-Read: die geteilte Fixture
    ``tests/fixtures/send_detail_parity/faelle.json`` haelt den Wortlaut, den
    die Go-API vor Python selbst meldet (``briefing_send_test.go`` prueft die
    Go-Seite gegen dieselbe Datei). Hier: der Python-Endpoint ohne ``kind``
    liefert exakt diesen Text."""
    soll = json.loads(_PARITAET.read_text(encoding="utf-8"))
    assert soll.get("kind_required"), f"Fixture leer/fehlt: {_PARITAET}"
    uid = nutzer_anlegen()

    r = hv.neu_senden(c, "x-2280", uid, None)

    assert r.status_code == 400, hv.body(r)
    assert hv.body(r).get("detail") == soll["kind_required"], hv.body(r)


def _vokabular() -> dict:
    """Die EINE Zuordnung Code -> (Status, Text) aus ``services.send_outcomes``.
    Bewusst lokal importiert (nur die Vokabular-Tests brauchen das Modul)."""
    from services import send_outcomes  # noqa: PLC0415

    kandidaten = [
        wert for wert in vars(send_outcomes).values()
        if isinstance(wert, dict) and set(hv.ERWARTETE_CODES) <= set(wert)
    ]
    assert kandidaten, (
        "send_outcomes muss eine Zuordnung Code -> (Status, Text) mit allen Codes "
        f"{sorted(hv.ERWARTETE_CODES)} enthalten"
    )
    return kandidaten[0]


def test_ac9_vokabular_steht_in_einer_datei_mit_status_und_text():
    """Given ``src/services/send_outcomes.py`` / When das Modul geladen wird /
    Then haelt EINE Zuordnung alle acht Codes mit HTTP-Status und deutschem
    Text."""
    vokabular = _vokabular()
    for code, status_soll in hv.ERWARTETE_CODES.items():
        eintrag = vokabular[code]
        if isinstance(eintrag, (tuple, list)):
            status, text = eintrag[0], eintrag[1]
        else:
            status = getattr(eintrag, "status", getattr(eintrag, "http_status", None))
            text = getattr(eintrag, "text", getattr(eintrag, "detail", None))
        assert status == status_soll, f"{code}: Status {status!r}, erwartet {status_soll}"
        assert isinstance(text, str) and len(text) > 10 and text != code, (
            f"{code}: deutscher Text erwartet, bekommen {text!r}"
        )


# ---------------------------------------------------------------------------
# AC-10 — einheitliche Erfolgsform, Erfolg heisst Zustellung
# ---------------------------------------------------------------------------


def test_ac10_erfolgsform_trip_traegt_report_type_und_keine_fehlenden_orte(lage, c):
    uid, trip_id, _ = _nutzer_mit_trip_und_vergleich()

    r = hv.neu_senden(c, trip_id, uid, "route")

    assert r.status_code == 200, r.text
    assert hv.body(r) == {
        "status": "ok", "kind": "route", "id": trip_id, "sent": True,
        "report_type": "morning",
    }, hv.body(r)


def test_ac10_erfolgsform_vergleich_traegt_fehlende_orte_und_keinen_report_type(lage, c):
    """Teilverlust (#2216): ein Ort geloescht -> Versand laeuft, fehlende_orte
    in der Antwort; winner/empfaenger_count entfallen (Spec, Abweichung 3)."""
    uid = nutzer_anlegen()
    _vergleich_anlegen(uid, "vgl-teil", location_ids=["loc-ibk", "loc-geloescht"])

    r = hv.neu_senden(c, "vgl-teil", uid, "vergleich")

    assert r.status_code == 200, r.text
    assert hv.body(r) == {
        "status": "ok", "kind": "vergleich", "id": "vgl-teil", "sent": True,
        "fehlende_orte": ["loc-geloescht"],
    }, hv.body(r)


def test_ac10_vergleich_ohne_fehlende_orte_hat_genau_die_grundform(lage, c):
    uid = nutzer_anlegen()
    _vergleich_anlegen(uid, "vgl-voll")

    r = hv.neu_senden(c, "vgl-voll", uid, "vergleich")

    assert r.status_code == 200, r.text
    assert hv.body(r) == {"status": "ok", "kind": "vergleich", "id": "vgl-voll", "sent": True}


@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac10_ohne_zustellung_nie_status_ok(lage, c, monkeypatch, kind):
    """Given kein wirksamer Kanal / When gesendet wird / Then nie 200 und nie
    status 'ok' — ein Fehlschlag ist 4xx, nie 200 mit sent:false."""
    uid = nutzer_anlegen()
    if kind == "route":
        hv.trip_anlegen(uid, "trip-nichts", email=False)
        entity_id = "trip-nichts"
    else:
        _vergleich_anlegen(uid, "vgl-nichts")
        hv.profil_ohne_mail_to(uid)  # echte Lage: kein Kanal wirksam
        entity_id = "vgl-nichts"

    r = hv.neu_senden(c, entity_id, uid, kind)

    assert 400 <= r.status_code < 500, f"Erwartet 4xx ohne Zustellung: {r.status_code} {r.text}"
    assert hv.body(r).get("status") != "ok", hv.body(r)
    assert hv.body(r).get("code") == "no_channels", hv.body(r)
    assert lage.nichts_versendet, lage


# ---------------------------------------------------------------------------
# AC-13 — Alt-Routen: Erfolgsgleichheit und report_type-Defaults
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["route", "vergleich"])
def test_ac13_alt_route_liefert_dieselbe_erfolgsantwort(lage, c, kind):
    uid, trip_id, vgl_id = _nutzer_mit_trip_und_vergleich()
    entity_id = trip_id if kind == "route" else vgl_id
    extra = {"report_type": "morning"} if kind == "route" else {}

    alt = hv.alt_senden(c, kind, entity_id, uid, **extra)
    neu = hv.neu_senden(c, entity_id, uid, kind, **extra)

    assert alt.status_code == neu.status_code == 200, (alt.text, neu.text)
    assert hv.body(alt) == hv.body(neu), f"alt {hv.body(alt)} != neu {hv.body(neu)}"


def test_ac13_report_type_default_alt_evening_neu_morning(lage, c):
    """Given ein Trip / When ohne report_type gesendet wird / Then nimmt die
    Alt-Route 'evening', der neue Endpoint 'morning'. Beobachtet am echten
    Send-Lock (Schluessel enthaelt report_type): der jeweils gehaltene Slot
    fuehrt zu 409 already_in_progress."""
    uid = nutzer_anlegen()
    hv.trip_anlegen(uid, "trip-default")

    assert send_lock.try_acquire_send_lock(uid, "trip-default", "evening")
    try:
        alt = hv.alt_senden(c, "route", "trip-default", uid)
    finally:
        send_lock.release_send_lock(uid, "trip-default", "evening")
    assert alt.status_code == 409, f"Alt-Route muss 'evening' als Default nehmen: {alt.text}"

    assert send_lock.try_acquire_send_lock(uid, "trip-default", "morning")
    try:
        neu = hv.neu_senden(c, "trip-default", uid, "route")
    finally:
        send_lock.release_send_lock(uid, "trip-default", "morning")
    assert neu.status_code == 409, f"Neuer Endpoint muss 'morning' als Default nehmen: {neu.text}"
    assert hv.body(neu).get("code") == "already_in_progress", hv.body(neu)
