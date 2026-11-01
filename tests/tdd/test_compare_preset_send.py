"""TDD RED — Issue #627: Compare-Preset Einzel-Sofortversand (Python-Core).

Spec: docs/specs/modules/issue_627_631_compare_send_rhythm.md (AC-4)

Echte Aufrufe — KEINE Mocks:
  - FastAPI TestClient ist ein echter ASGI-Call (kein Mock).
  - _send_compare_preset arbeitet gegen ein echtes temporäres compare_presets.json.

SOLL-Verhalten nach Fix:
  - api.routers.scheduler._send_compare_preset(user_id, preset_id, data_root=...)
    existiert und sendet das Vergleichs-Briefing sofort (ignoriert schedule).
  - Ohne Empfänger UND ohne mail_to-Fallback → Fehler (Exception oder
    Rückgabe mit Fehlerstatus), NICHT still "ok".
  - POST /api/scheduler/compare-presets/{id}/send?user_id=... existiert;
    unbekannte ID → HTTP 404.

RED-Erwartung (vor Fix):
  - ImportError: _send_compare_preset existiert nicht.
  - Endpoint fehlt → POST liefert kein 404 vom SOLL-Endpoint (Route fehlt).
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from tests.helpers.compare_briefings import write_compare_briefings


class TestComparePresetSend:
    """Issue #627 — Einzel-Sofortversand für ein Compare-Preset."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def _write_preset(self, data_root, user_id, preset):
        """Lege ein Test-Preset in einem temporären data_root an.

        Issue #1250 S7b Cutover: per-Datei briefings/<id>.json (kind="vergleich")
        — sonst laedt send_compare_preset das Preset nicht und der Test wuerde
        aus dem falschen Grund (KeyError 'nicht gefunden') gruen.
        """
        user_dir = data_root / "users" / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        write_compare_briefings(user_dir, [preset])

    # ── AC-4: Preset ohne Empfänger + ohne mail_to-Fallback → Fehler ──────────

    def test_send_without_recipients_signals_error(self, tmp_path):
        """Preset OHNE empfaenger und ohne mail_to-Fallback darf NICHT still 'ok'.

        RED: api.routers.scheduler._send_compare_preset existiert noch nicht
        → ImportError beim Import.
        """
        from services.scheduler_dispatch_service import send_compare_preset as _send_compare_preset

        user_id = "u1"
        preset = {
            "id": "cp-no-recipients",
            "name": "Ohne Empfänger",
            "user_id": user_id,
            "location_ids": ["loc-a"],
            "schedule": "manual",
            "profil": "SUMMER_TREKKING",
            "hour_from": 9,
            "hour_to": 16,
            "empfaenger": [],  # bewusst leer
            "created_at": "2026-01-01T00:00:00Z",
        }
        self._write_preset(tmp_path, user_id, preset)

        error_signalled = False
        try:
            result = _send_compare_preset(
                user_id, "cp-no-recipients", data_root=str(tmp_path)
            )
            status = (result or {}).get("status")
            error_signalled = status not in ("ok", None) or "error" in (result or {})
        except Exception:
            error_signalled = True

        assert error_signalled, (
            "Preset ohne Empfänger und ohne mail_to-Fallback muss einen Fehler "
            "signalisieren (Exception oder Fehlerstatus) — kein stiller 'ok'-Erfolg."
        )

    # ── Endpoint: unbekannte Preset-ID → HTTP 404 ─────────────────────────────

    def test_send_endpoint_unknown_id_returns_404(self, client, tmp_path):
        """POST /api/scheduler/compare-presets/{unbekannt}/send → fachliches 404.

        WICHTIG: FastAPI liefert für eine FEHLENDE Route ebenfalls ein generisches
        404 ({"detail":"Not Found"}). Damit dieser Test ein echtes RED ist und
        NICHT durch die abwesende Route grün scheint, muss er einen vorhandenen
        Endpoint mit einem FACHLICHEN Not-Found unterscheiden:
          - Der SOLL-Endpoint liefert bei unbekannter Preset-ID eine Detail-/Error-
            Meldung, die das Preset benennt (z.B. "preset"/"not found"/"nicht
            gefunden"), nicht das nackte Routing-"Not Found".

        RED (vor Fix): Route fehlt → FastAPI-Routing-404 mit detail=="Not Found"
        → die fachliche Assertion schlägt fehl.
        """
        # Existierenden, aber leeren User anlegen, damit der Endpoint einen echten
        # Lookup macht statt am Routing zu scheitern.
        user_dir = tmp_path / "users" / "u1"
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / "compare_presets.json").write_text("[]", encoding="utf-8")

        resp = client.post(
            "/api/scheduler/compare-presets/cp-does-not-exist/send",
            params={"user_id": "u1"},
        )
        assert resp.status_code == 404, (
            f"Erwartet 404 für unbekanntes Preset, bekam {resp.status_code} "
            f"(body={resp.text!r})."
        )
        detail = ""
        try:
            body = resp.json()
            detail = str(body.get("detail") or body.get("error") or "").lower()
        except Exception:
            detail = resp.text.lower()
        assert detail and detail != "not found", (
            f"Erwartet ein FACHLICHES Not-Found (Preset benannt), bekam generisches "
            f"Routing-404 {detail!r} — Endpoint /compare-presets/{{id}}/send fehlt (RED)."
        )


# ===========================================================================
# #2280 (Epic #2345 P4) — Ortsvergleich meldet ehrlich: Erfolg heisst Zustellung
# Spec: docs/specs/modules/feat_2280_handversand_endpoint.md (AC-4 bis AC-8)
#
# Echte Kette: HTTP-Router -> send_compare_preset -> send_one_compare_preset
# -> NotificationService.send_compare_report. Naehte nur zu Wetter, Transport,
# Kanallage und Anker-Netzabruf (tests/tdd/_handversand_fixtures.py). Jeder
# Test benutzt frische Nutzer; AC-7 prueft Hand- UND Cron-Pfad.
# ===========================================================================

from tests.helpers.transport_mitschrift import Kanalmitschrift, aufzeichner_installieren  # noqa: E402
from tests.tdd import _handversand_fixtures as hv  # noqa: E402
from tests.tdd._compare_kette_fixtures import (  # noqa: E402
    TARGET_DATE,
    alle_orte,
    engine_naht,
    fixture_dict,
    nutzer_anlegen,
    orte_anlegen,
    preset_ablegen,
    preset_laden,
    settings_fuer,
    transport_einrichten,
)


@pytest.fixture
def mit(monkeypatch) -> Kanalmitschrift:
    transport_einrichten(monkeypatch)
    engine_naht(monkeypatch)
    return aufzeichner_installieren(monkeypatch)


@pytest.fixture
def anker(mit, monkeypatch) -> list:
    """Nach ``engine_naht`` (das den Anker-Schreiber still legt) neu belegt."""
    return hv.anker_zaehler(monkeypatch)


def _vergleich(uid: str, preset_id: str, *, telegram: bool = False, sms: bool = False) -> str:
    """Echtes Preset; die Kanallage entsteht ausschliesslich aus den
    Opt-ins hier und dem Konto-Profil (mit/ohne mail_to) -- kein Resolver-Patch."""
    roh = fixture_dict("basis")
    roh["id"] = preset_id
    roh["send_telegram"] = telegram
    roh["send_sms"] = sms
    orte_anlegen(uid)
    preset_ablegen(uid, roh)
    return preset_id


def _cron(uid: str, preset_id: str, settings=None) -> str | None:
    """Cron-Pfad wie im Betrieb: der fehler-isolierende Wrapper
    ``_dispatch_due_preset`` (Morgen-Slot, Versatz 0).

    Issue #1777 (Spec fix_1777, Ausgangs-Abbildung): der Wrapper liefert den
    AUSGANG als String (``"sent"``, ``"no_channels"``, ``"no_weather"``,
    ``"channels_unreachable"``) statt ``bool``. ``now_utc`` ist optional
    (Default = jetzt) und wird hier bewusst nicht uebergeben. Zusicherungen
    vergleichen den Ausgang EXPLIZIT, nie truthy."""
    from app.loader import get_data_root
    from services.scheduler_dispatch_service import _dispatch_due_preset

    return _dispatch_due_preset(
        preset_laden(uid, preset_id), TARGET_DATE,
        settings if settings is not None else settings_fuer(uid),
        uid, str(get_data_root()), alle_orte(uid), tage_ab_ortstag=0,
    )


# --- AC-4: kein wirksamer Kanal -> 422 no_channels, Text wie beim Trip --------


def test_ac4_vergleich_ohne_wirksamen_kanal_liefert_422_no_channels_mit_trip_text(
    mit, monkeypatch,
):
    """Given ein Ortsvergleich ohne wirksamen Kanal / When per Hand versendet /
    Then 422, code 'no_channels', detail WORTGLEICH zum Trip-Fall ohne Kanal.
    Echte Lage: keine mail_to im Konto, kein Telegram-/SMS-Opt-in im Preset.
    RED: heute 422 'mail_to fehlt' ohne code."""
    from app.config import Settings

    hv.trip_naehte(monkeypatch)
    c = hv.client()
    uid = nutzer_anlegen()
    pid = _vergleich(uid, "vgl-ac4")
    hv.profil_ohne_mail_to(uid)
    assert not Settings().with_user_profile(uid).mail_to, "Vorbedingung: keine mail_to"
    trip_uid = nutzer_anlegen()
    hv.trip_anlegen(trip_uid, "trip-ac4", email=False)

    r = hv.alt_senden(c, "vergleich", pid, uid)
    trip = hv.alt_senden(c, "route", "trip-ac4", trip_uid, report_type="morning")

    assert r.status_code == 422, f"Erwartet 422 statt stillem Erfolg: {r.status_code} {r.text}"
    assert hv.body(r).get("code") == "no_channels", hv.body(r)
    assert trip.status_code == 422 and hv.body(trip).get("code") == "no_channels", hv.body(trip)
    assert hv.body(r)["detail"] == hv.body(trip)["detail"], (
        f"Ein Vokabular: Vergleich {hv.body(r)['detail']!r} != Trip {hv.body(trip)['detail']!r}"
    )
    assert not mit.kanaele, f"Ohne Kanal darf nichts hinausgehen: {mit}"
    assert hv.letzter_versand(uid, pid) is None, "Kein Erfolgs-Status ohne Zustellung"


# --- AC-5: alle Kanaele scheitern -> 422 channels_unreachable -----------------


def test_ac5_alle_kanaele_gescheitert_liefert_422_ohne_erfolgs_status(mit, anker, monkeypatch):
    """Given ein Ortsvergleich, dessen einziger wirksamer Kanal (Telegram) beim
    Senden scheitert / When per Hand versendet / Then 422 'channels_unreachable',
    kein gespeicherter Erfolgs-Status, kein Anker-Reset (Zustand vor/nach).
    Echte Lage: Preset send_telegram, Konto ohne mail_to (E-Mail unwirksam),
    Telegram-Transport faellt aus. RED: heute 422 'mail_to fehlt' ohne code.
    Hinweis: der Anker-Teil ist im Handversand strukturell schon heute erfuellt
    (on_demand=True); die wirksame Anker-Pruefung steht im Cron-Pfad (AC-8)."""
    c = hv.client()
    uid = nutzer_anlegen()
    pid = _vergleich(uid, "vgl-ac5", telegram=True)
    hv.profil_ohne_mail_to(uid)
    versuche = hv.telegram_vergleich_scheitert(monkeypatch)
    vorher = hv.letzter_versand(uid, pid)
    assert vorher is None, "Vorbedingung: noch kein Versand-Status"

    r = hv.alt_senden(c, "vergleich", pid, uid)

    assert r.status_code == 422, f"Erwartet 422 statt 'ok': {r.status_code} {r.text}"
    assert hv.body(r).get("code") == "channels_unreachable", hv.body(r)
    assert versuche, "Der Telegram-Ausgang muss betreten worden sein"
    assert hv.letzter_versand(uid, pid) == vorher, "Erfolgs-Status darf nicht gespeichert sein"
    assert anker == [], f"Kein Anker-Reset bei gescheitertem Versand: {anker}"


# --- AC-6: keine Wetterdaten -> 422 no_weather statt 500 ----------------------


def test_ac6_keine_wetterdaten_liefert_422_no_weather_statt_500(mit, monkeypatch):
    """Given die Wetterabfrage scheitert fuer ALLE Orte / When per Hand
    versendet / Then 422 'no_weather' mit deutschem Text, kein 500, nichts
    versendet. RED: heute 500 Internal Server Error."""
    c = hv.client()
    uid = nutzer_anlegen()
    pid = _vergleich(uid, "vgl-ac6")
    hv.wetter_faellt_ueberall_aus(monkeypatch)

    r = hv.alt_senden(c, "vergleich", pid, uid)

    assert r.status_code == 422, f"Erwartet 422 statt Serverfehler: {r.status_code} {r.text}"
    b = hv.body(r)
    assert b.get("code") == "no_weather", b
    assert isinstance(b.get("detail"), str) and "Wetter" in b["detail"], (
        f"Verstaendlicher deutscher Text erwartet: {b}"
    )
    assert not mit.kanaele, mit
    assert hv.letzter_versand(uid, pid) is None


def test_ac6_alle_orte_ohne_daten_liefert_422_no_weather(mit, monkeypatch):
    """Realistische Form desselben Givens: die Engine faengt den Provider-
    Fehler je Ort selbst ab (``LocationResult(error=...)``, keine Ausnahme) —
    fuer ALLE Orte. Auch das ist "keine Wetterdaten zu bekommen" und darf
    weder als 200 'ok' noch als 500 enden."""
    c = hv.client()
    uid = nutzer_anlegen()
    pid = _vergleich(uid, "vgl-ac6-real")
    hv.wetter_fehlt_je_ort(monkeypatch)

    r = hv.alt_senden(c, "vergleich", pid, uid)

    assert r.status_code == 422, f"Erwartet 422 no_weather: {r.status_code} {r.text}"
    assert hv.body(r).get("code") == "no_weather", hv.body(r)
    assert not mit.kanaele, f"Ohne Wetterdaten darf nichts hinausgehen: {mit}"
    assert hv.letzter_versand(uid, pid) is None


# --- AC-7: nur Telegram/SMS, keine mail_to -> zustellbar (Hand + Cron) --------


@pytest.mark.parametrize("kanaele", [{"telegram"}, {"sms"}, {"telegram", "sms"}])
def test_ac7_handversand_nur_telegram_sms_ohne_mail_to_wird_zugestellt(
    mit, monkeypatch, kanaele,
):
    """Given Preset-Opt-in nur Telegram/SMS (echte Faehigkeit: Bot-Token +
    Profil-Chat, SMS-Gateway + verifizierte Nummer, Tarif premium) und KEINE
    mail_to im Profil / When per Hand versendet / Then 200 und Zustellung genau
    ueber diese Kanaele. RED: heute 422 'kein Empfaenger — mail_to fehlt'."""
    from app.config import Settings

    c = hv.client()
    uid = nutzer_anlegen()
    pid = _vergleich(uid, "vgl-ac7-hand",
                     telegram="telegram" in kanaele, sms="sms" in kanaele)
    # Vorbedingung: MIT mail_to erreichen die Opt-in-Kanaele die Ausgaenge
    # (beweist, dass die echte Kanallage SMS/Telegram zustellen kann).
    vorlauf = hv.alt_senden(c, "vergleich", pid, uid)
    assert vorlauf.status_code == 200 and set(mit.kanaele) == kanaele | {"email"}, (
        f"Vorbedingung verletzt: {vorlauf.status_code} {vorlauf.text} {mit}"
    )
    mit.leeren()
    hv.profil_ohne_mail_to(uid)
    assert not Settings().with_user_profile(uid).mail_to, "Vorbedingung: keine mail_to"

    r = hv.alt_senden(c, "vergleich", pid, uid)

    assert r.status_code == 200, f"Ohne E-Mail-Kanal ist mail_to keine Pflicht: {r.text}"
    assert hv.body(r).get("status") == "ok", hv.body(r)
    assert set(mit.kanaele) == kanaele, f"Zustellung ueber {kanaele} erwartet: {mit}"


def test_ac7_cron_nur_telegram_ohne_mail_to_wird_zugestellt(mit, anker, monkeypatch):
    """Cron-Pfad (``send_one_compare_preset`` ueber den Wrapper): gleiche
    Kanal-Paritaet. RED: heute ValueError -> Wrapper verbucht 'nicht gesendet'."""
    uid = nutzer_anlegen()
    pid = _vergleich(uid, "vgl-ac7-cron", telegram=True)
    hv.profil_ohne_mail_to(uid)
    settings = settings_fuer(uid)
    assert not settings.mail_to and settings.can_send_telegram(), "Vorbedingung"

    ergebnis = _cron(uid, pid, settings)

    assert ergebnis == "sent", f"Cron-Lauf nur mit Telegram muss als versendet gelten: {ergebnis!r}"
    assert mit.kanaele == ["telegram"], mit
    assert hv.letzter_versand(uid, pid), "Erfolgs-Status nach echter Zustellung erwartet"


def test_ac7_gegenprobe_ohne_mail_to_und_ohne_telegram_sms_bleibt_fehler(mit, monkeypatch):
    """Gegenprobe: keine mail_to UND kein Telegram-/SMS-Opt-in -> die Lockerung
    darf keinen stillen Erfolg erzeugen: 422 'no_channels', nichts zugestellt.
    RED: heute 422 'mail_to fehlt' ohne code (Fehler ja, Form noch nicht)."""
    c = hv.client()
    uid = nutzer_anlegen()
    pid = _vergleich(uid, "vgl-ac7-gegen")
    hv.profil_ohne_mail_to(uid)

    r = hv.alt_senden(c, "vergleich", pid, uid)

    assert r.status_code == 422, f"Ohne jeden wirksamen Kanal muss es scheitern: {r.text}"
    assert hv.body(r).get("status") != "ok", hv.body(r)
    assert not mit.kanaele, mit
    assert hv.letzter_versand(uid, pid) is None
    assert hv.body(r).get("code") == "no_channels", hv.body(r)


# --- AC-8: Cron bucht ehrlich ------------------------------------------------


def test_ac8_cron_ohne_wirksamen_kanal_bucht_nicht_als_versendet(mit, anker, monkeypatch):
    """Given Cron-Lauf ohne wirksamen Kanal / When der Lauf endet / Then kein
    Erfolgs-Status, kein Anker-Reset, Wrapper wirft nicht und meldet False.
    Echte Lage: keine mail_to, kein Telegram-/SMS-Opt-in.
    RED-Charakter: heute endet der Lauf ueber den ValueError 'mail_to fehlt'
    bereits mit False -- dieser Test ist HEUTE GRUEN und bewacht nach dem Fix
    (ValueError entfaellt) die Ableitung 'no_channels -> nicht verbucht'."""
    uid = nutzer_anlegen()
    pid = _vergleich(uid, "vgl-ac8-ohne")
    hv.profil_ohne_mail_to(uid)

    ergebnis = _cron(uid, pid)  # darf nicht werfen

    assert ergebnis == "no_channels", (
        f"Ohne Kanal darf der Cron-Lauf nicht als versendet gelten: {ergebnis!r}"
    )
    assert hv.letzter_versand(uid, pid) is None, "Kein Erfolgs-Status"
    assert anker == [], f"Kein Anker-Reset ohne Zustellung: {anker}"
    assert not mit.kanaele, mit


def test_ac8_cron_alle_kanaele_gescheitert_bucht_nicht_als_versendet(mit, anker, monkeypatch):
    """Echte Lage: send_telegram, keine mail_to, Telegram-Transport faellt aus.
    Heute endet der Lauf schon am ValueError 'mail_to fehlt' (False, ohne den
    Telegram-Ausgang zu betreten) -> rot an der Vorbedingung 'Ausgang betreten'."""
    uid = nutzer_anlegen()
    pid = _vergleich(uid, "vgl-ac8-tot", telegram=True)
    hv.profil_ohne_mail_to(uid)
    versuche = hv.telegram_vergleich_scheitert(monkeypatch)

    ergebnis = _cron(uid, pid)  # darf nicht werfen

    assert versuche, "Vorbedingung: Telegram-Ausgang betreten"
    assert ergebnis == "channels_unreachable", (
        f"Gescheiterter Cron-Lauf darf nicht als versendet gelten: {ergebnis!r}"
    )
    assert hv.letzter_versand(uid, pid) is None, "Kein Erfolgs-Status"
    assert anker == [], f"Kein Anker-Reset bei gescheitertem Versand: {anker}"


def test_ac8_kontrolle_cron_mit_zustellung_bucht_und_setzt_anker(mit, anker, monkeypatch):
    """Kontroll-Bein (sonst waeren die beiden AC-8-Tests vakuum): ein Cron-Lauf
    MIT Zustellung verbucht den Versand und setzt den Anker. Heute gruen."""
    uid = nutzer_anlegen()
    pid = _vergleich(uid, "vgl-ac8-ok")  # echte Lage: mail_to da, nur E-Mail

    ergebnis = _cron(uid, pid)

    assert ergebnis == "sent", ergebnis
    assert mit.kanaele == ["email"], mit
    assert hv.letzter_versand(uid, pid), "Erfolgs-Status nach Zustellung erwartet"
    assert len(anker) >= 1, f"Anker muss nach echter Zustellung gesetzt werden: {anker}"


# --- Fix-Loop 1 F-ADV1: Cron OHNE Opt-in behaelt das Bestandsverhalten -------
# Vor #2280 (git show HEAD): ein Engine-Ausfall an allen Orten schlug als die
# urspruengliche Ausnahme durch (kein SendOutcomeError), und ein Lauf, in dem
# jeder Ort nur ``LocationResult(error=...)`` liefert, wurde gerendert,
# zugestellt und verbucht. ``weather_failure_as_outcome`` gilt nur fuer den
# Handversand; ein Default ``True`` wuerde den Cron still umstellen.


def test_cron_ohne_opt_in_engine_ausfall_ueberall_wirft_originalfehler(mit, monkeypatch):
    """Given ein Engine-Ausfall an JEDEM Ort / When ``send_one_compare_preset``
    ohne Opt-in (Cron-Form) laeuft / Then die urspruengliche Ausnahme schlaegt
    durch -- KEIN ``SendOutcomeError('no_weather')`` -- und nichts geht hinaus."""
    from app.loader import get_data_root
    from services.scheduler_dispatch_service import send_one_compare_preset
    from services.send_outcomes import SendOutcomeError

    uid = nutzer_anlegen()
    pid = _vergleich(uid, "vgl-adv1-wirft")
    hv.wetter_faellt_ueberall_aus(monkeypatch)

    with pytest.raises(Exception) as info:
        send_one_compare_preset(
            preset_laden(uid, pid), settings_fuer(uid), uid, str(get_data_root()),
            all_locations_cache=alle_orte(uid),
        )

    assert not isinstance(info.value, SendOutcomeError), (
        f"Cron ohne Opt-in darf den Wetterausfall nicht in no_weather umdeuten: {info.value!r}"
    )
    assert "simulierter Ausfall" in str(info.value), info.value
    assert not mit.kanaele, mit


def test_cron_ohne_opt_in_alle_orte_mit_fehler_wird_nicht_zugestellt(mit, anker, monkeypatch):
    """Given jeder Ort liefert ``LocationResult(error=...)`` / When der Cron-
    Wrapper laeuft / Then seit Fix #2286 (AC-4, ADR-0018) wie beim Handversand:
    keine Mail aus lauter Fehlerzellen, der Lauf gilt als NICHT versendet,
    kein Erfolgs-Status (vormals Bestandsverhalten "zugestellt")."""
    uid = nutzer_anlegen()
    pid = _vergleich(uid, "vgl-adv1-fehlerorte")
    hv.wetter_fehlt_je_ort(monkeypatch)

    ergebnis = _cron(uid, pid)

    assert ergebnis == "no_weather", (
        f"Cron: Provider-Totalausfall darf nicht als zugestellt gelten (#2286): {ergebnis!r}"
    )
    assert mit.kanaele == [], mit
    assert not hv.letzter_versand(uid, pid), "kein Erfolgs-Status bei no_weather (#2286)"


# --- Fix-Loop 1 F-ADV6 (a): Cron-Vergleich ohne Zustellung hinterlaesst Spur --


def _versandfehler_eintraege(uid: str) -> list:
    import json

    from app.loader import get_data_dir

    pfad = get_data_dir(uid) / "diagnostics" / "briefing_dispatch_failures.jsonl"
    if not pfad.exists():
        return []
    return [json.loads(z) for z in pfad.read_text().splitlines() if z.strip()]


def test_cron_alle_kanaele_gescheitert_schreibt_versandfehler_spur(mit, anker, monkeypatch):
    """Given Cron-Lauf, einziger wirksamer Kanal (Telegram) scheitert / Then ein
    Eintrag in briefing_dispatch_failures.jsonl (kind vergleich, Preset-ID) —
    sichtbar in briefing_health — und kein Anker-Reset."""
    uid = nutzer_anlegen()
    pid = _vergleich(uid, "vgl-adv6-cron", telegram=True)
    hv.profil_ohne_mail_to(uid)
    versuche = hv.telegram_vergleich_scheitert(monkeypatch)

    assert _cron(uid, pid) == "channels_unreachable"
    assert versuche, "Vorbedingung: Telegram-Ausgang betreten"
    eintraege = _versandfehler_eintraege(uid)
    assert [(e["kind"], e["entity_id"]) for e in eintraege] == [("vergleich", pid)], eintraege
    assert "channels_unreachable" in eintraege[0]["error"], eintraege
    assert anker == [], f"Kein Anker-Reset: {anker}"


def test_handversand_alle_kanaele_gescheitert_schreibt_keine_versandfehler_spur(
    mit, anker, monkeypatch,
):
    """Gegenstueck Handversand: 422 channels_unreachable, aber KEIN Eintrag."""
    c = hv.client()
    uid = nutzer_anlegen()
    pid = _vergleich(uid, "vgl-adv6-hand", telegram=True)
    hv.profil_ohne_mail_to(uid)
    versuche = hv.telegram_vergleich_scheitert(monkeypatch)

    r = hv.alt_senden(c, "vergleich", pid, uid)

    assert r.status_code == 422 and hv.body(r).get("code") == "channels_unreachable", r.text
    assert versuche, "Vorbedingung: Telegram-Ausgang betreten"
    assert _versandfehler_eintraege(uid) == []


# --- Fix-Loop 1 F-ADV3: send_compare_report meldet 'kein Kanal' ---------------


def _compare_report(uid: str, kanaele: set, ausgaenge: list):
    from app.config import Settings
    from services.notification_service import NotificationService

    return NotificationService(settings=Settings(), user_id=uid).send_compare_report(
        subject="Vergleich", html_body="<p>x</p>", text_body="x",
        telegram_text="x", sms_text="x", recipients=["a@example.invalid"],
        effective_channels=kanaele,
        mail_sink=lambda **kw: ausgaenge.append(("email", kw)),
        sms_sink=lambda t: ausgaenge.append(("sms", t)),
        telegram_sink=lambda t: ausgaenge.append(("telegram", t)),
        premium_sms_sink=lambda t: ausgaenge.append(("premium_sms", t)),
    )


def test_send_compare_report_ohne_wirksamen_kanal_setzt_no_channel_configured():
    """Given keine wirksamen Kanaele / When ``send_compare_report`` laeuft /
    Then ``no_channel_configured is True``, nichts gesendet (Trip-Paritaet).
    Kontroll-Bein: mit E-Mail ist das Feld False."""
    uid = nutzer_anlegen()
    ausgaenge: list = []

    leer = _compare_report(uid, set(), ausgaenge)

    assert leer.no_channel_configured is True, leer
    assert leer.sent is False and ausgaenge == [], (leer, ausgaenge)

    mit_mail = _compare_report(uid, {"email"}, ausgaenge)
    assert mit_mail.no_channel_configured is False and mit_mail.sent is True, mit_mail
    assert [k for k, _ in ausgaenge] == ["email"], ausgaenge
