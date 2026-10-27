"""Empfaengervertrag SMS und Premium-SMS -- Versand nur an belegte Nummern.

Spec: docs/specs/modules/fix_1412_s4b_empfaengervertrag_sms.md (AC-1 bis AC-14)

Nachweisform (Spec-Abschnitt "Acceptance Criteria"):
* Sink am ``httpx``-Rand (``httpx.post``, den ``SevenIoChannelBase._post``
  ruft), der eine ECHTE ``httpx.Response`` zurueckgibt -- ``_post`` selbst
  bleibt unangetastet, kein Mock()/MagicMock/patch(). Geprueft wird das
  ``to``-Feld der seven.io-Nutzlast (und ``X-Api-Key``), nicht nur die
  Aufrufzahl.
* ``is_test_mode=False`` (ausser in den AC-14-Testmodus-Faellen).
* Herkunft auf "production" festgenagelt (je Kanal-Modul, ``running_origin``):
  im Worktree schaltete ``_guard_code_origin`` sonst auf den Sandbox-Key um --
  harmlos, aber AC-14 misst genau diese Umschaltung gezielt.
* ``.env``-Isolation: ``Settings.model_config["env_file"] = None`` (Vorbild
  ``_ohne_dotenv``, ``tests/test_public_host_links.py``), Settings mit
  ``_env_file=None`` und expliziten Werten; ``GZ_SMS_TO`` nur in AC-3.
* Zwei Nutzer A/B; Nutzerkennungen ohne "test"/"tdd" (sonst erzwingt
  ``is_test_user_id`` den Testmodus). Datenwurzel: per-Test-Isolation aus
  ``tests/conftest.py`` (#1133).
* Rot aus dem richtigen Grund: die neuen Namen (``SmsRecipient``,
  ``PremiumSmsRecipient``, ``recipient=``, ``RecipientPurpose.verification``)
  werden nur INNERHALB der Testfunktionen benutzt (auch ueber
  ``tests/helpers/sms_empfaenger.py``) -- die Datei stirbt nicht beim Sammeln.
  Wo moeglich ist ein Test per Assertion gegen das heutige Verhalten rot
  (heute sendet der Transport an ``settings.sms_to`` /
  ``settings.premium_sms_reply_to``).
* Die AC-10-Tests (und der Positivfall AC-6 sowie AC-11) sind heute GRUEN und
  bewusst so: Nicht-Verstummen-Waechter fuer die Umstellung aller Aufrufer.
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.config import Settings  # noqa: E402
from app.loader import get_data_dir  # noqa: E402
from output.channels import premium_sms as premium_mod  # noqa: E402
from output.channels import sms as sms_mod  # noqa: E402
from output.channels.base import (  # noqa: E402
    ChannelBlockedError,
    OutputConfigError,
)
from output.channels.premium_sms import (  # noqa: E402
    BLOCK_REASON_NO_REPLY_ADDRESS,
    BLOCK_REASON_REPLY_ADDRESS_STALE,
    PREMIUM_SMS_SENDER,
    PremiumSmsOutput,
)
from output.channels.sms import SMSOutput  # noqa: E402

from tests.helpers.sms_empfaenger import (  # noqa: E402
    premium_ausgang,
    profil_rueckadresse,
    profil_sms,
    sms_ausgang,
    verifikations_ausgang,
)

GATEWAY = "https://gateway.seven.invalid/api/sms"
PROD_KEY = "seven-prod-key-s4b"
SANDBOX_KEY = "seven-sandbox-key-s4b"

NUMMER_A = "+41790000001"
NUMMER_B = "+41790000002"
BETREIBER = "+41790009999"   # globale GZ_SMS_TO-Nummer des Betreibers
FREMD = "+41790007777"       # wohlgeformt, aber niemandem zugeordnet

RUECK_A = "4917000000001"    # gelernte Garmin-Rueckadressen (seven.io-``from``)
RUECK_B = "4917000000002"
RUECK_SETTINGS = "4917000000099"  # Rueckadresse, die NUR in den Settings steht

KUNDE_A = "kunde-a"
KUNDE_B = "kunde-b"

CODE_SMS_NO_RECIPIENT = "sms_no_recipient"


# ---------------------------------------------------------------------------
# Sink am httpx-Rand
# ---------------------------------------------------------------------------


class _SevenSink:
    """Zeichnet jeden ``httpx.post`` an das seven.io-Gateway auf und antwortet
    wie seven.io im Erfolgsfall (HTTP 200, Text ``100``). POSTs an andere
    Adressen (Go-Lern-Endpunkt in AC-11) gehen an ``fremd``; ohne ``fremd``
    ist jeder fremde POST ein Testfehler."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.fremd = None

    def __call__(self, url, headers=None, data=None, json=None, timeout=None, **kwargs):
        if url != GATEWAY:
            if self.fremd is None:
                raise AssertionError(f"unerwarteter POST an {url!r}")
            return self.fremd(url, json=json)
        daten = dict(data or {})
        self.calls.append({
            "url": url,
            "api_key": (headers or {}).get("X-Api-Key"),
            "to": daten.get("to"),
            "from": daten.get("from"),
            "text": daten.get("text"),
        })
        return httpx.Response(200, text="100", request=httpx.Request("POST", url))

    def ziele(self) -> list:
        return [c["to"] for c in self.calls]


@pytest.fixture(autouse=True)
def _hermetisch(monkeypatch):
    monkeypatch.setattr(sms_mod, "running_origin", lambda module_file: "production")
    monkeypatch.setattr(premium_mod, "running_origin", lambda module_file: "production")
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for key in (
        "GZ_SMS_TO", "GZ_SMS_FROM", "GZ_IS_TEST_MODE", "GZ_ENV",
        "GZ_SMS_GATEWAY_URL", "GZ_SEVEN_API_KEY", "GZ_SEVEN_SANDBOX_KEY",
    ):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def sink(monkeypatch) -> _SevenSink:
    s = _SevenSink()
    monkeypatch.setattr(httpx, "post", s)
    return s


def _settings(**overrides) -> Settings:
    """Vollstaendig konfiguriertes seven.io, globale Betreibernummer in
    ``sms_to`` (das ist die Nummer, die heute faelschlich erreicht wird)."""
    werte = dict(
        _env_file=None,
        env="production",
        is_test_mode=False,
        sms_gateway_url=GATEWAY,
        seven_api_key=PROD_KEY,
        seven_sandbox_key=SANDBOX_KEY,
        sms_to=BETREIBER,
        sms_from=None,
    )
    werte.update(overrides)
    return Settings(**werte)


def _mit_rueck(settings: Settings, nummer: str, alter: timedelta = timedelta(minutes=5)) -> Settings:
    """Premium-Felder per ``model_copy`` (der before-Validator sperrt sie im
    Konstruktor)."""
    return settings.model_copy(update={
        "premium_sms_reply_to": nummer,
        "premium_sms_reply_at": datetime.now(timezone.utc) - alter,
    })


def _verbraucht(uid: str, kanal: str) -> int:
    from services import sms_daily_limit

    return sms_daily_limit.get_daily_usage(uid, datetime.now(timezone.utc))[kanal]["used"]


def _kein_daten_hinweis(settings: Settings, uid: str, kanal: str):
    from services.notification_service import NotificationService

    return NotificationService(settings=settings, user_id=uid).send_no_data_hint(
        SimpleNamespace(name=f"Trip-{uid}"), "morning",
        send_email=False, send_telegram=False,
        send_sms=(kanal == "sms"), send_premium_sms=(kanal == "premium_sms"),
    )


# ═══════════════════════════ AC-1 ════════════════════════════════════════════


def test_ac1_sms_ohne_empfaenger_wird_geblockt_ohne_http(sink):
    """AC-1: Given ein SMS-Ausgang, der ohne Empfaenger-Objekt gebaut wurde
    (Settings tragen die globale Betreibernummer) / When er eine Nachricht
    senden soll / Then ``ChannelBlockedError`` mit
    ``reason_code=sms_no_recipient`` und kein einziger HTTP-Versuch.

    RED heute: ``send`` liest ``settings.sms_to`` und sendet an den Betreiber.
    """
    out = SMSOutput(_settings())
    with pytest.raises(ChannelBlockedError) as exc:
        out.send("", "Text")
    assert exc.value.reason_code == CODE_SMS_NO_RECIPIENT, exc.value.reason_code
    assert sink.calls == [], f"AC-1: kein HTTP-Versuch erlaubt, gesehen {sink.calls!r}"


def test_ac1_premium_ohne_empfaenger_wird_geblockt_ohne_http(sink):
    """AC-1: Given ein Premium-SMS-Ausgang ohne Empfaenger-Objekt (Settings
    tragen eine frische Rueckadresse) / When er senden soll / Then Block mit
    dem bestehenden ``reason_code=premium_sms_no_reply_address`` (Alarm-
    Buchung greift unveraendert), kein HTTP-Versuch.

    RED heute: ``send`` liest ``settings.premium_sms_reply_to`` und sendet.
    """
    out = PremiumSmsOutput(_mit_rueck(_settings(), RUECK_SETTINGS))
    with pytest.raises(ChannelBlockedError) as exc:
        out.send("", "Text")
    assert exc.value.reason_code == BLOCK_REASON_NO_REPLY_ADDRESS, exc.value.reason_code
    assert sink.calls == [], f"AC-1: kein HTTP-Versuch erlaubt, gesehen {sink.calls!r}"


@pytest.mark.parametrize("kanal", ["sms", "premium_sms"])
def test_ac1_einziger_ausgang_post_blockt_ohne_empfaenger(sink, kanal):
    """AC-1 (Kernregel 6, Pruefort ist ``_post``): Given ein Ausgang ohne
    Empfaenger / When der einzige Netzausgang ``_post`` direkt mit einer
    wohlgeformten Nutzlast aufgerufen wird / Then Block mit dem Kanal-
    ``reason_code`` und kein HTTP-Versuch.

    RED heute: ``_post`` ist reiner Transport und sendet.
    """
    if kanal == "sms":
        out, ziel, code = SMSOutput(_settings()), BETREIBER, CODE_SMS_NO_RECIPIENT
    else:
        out = PremiumSmsOutput(_mit_rueck(_settings(), RUECK_SETTINGS))
        ziel, code = RUECK_SETTINGS, BLOCK_REASON_NO_REPLY_ADDRESS
    with pytest.raises(ChannelBlockedError) as exc:
        out._post(GATEWAY, PROD_KEY, {"to": ziel, "text": "x"})
    assert exc.value.reason_code == code, exc.value.reason_code
    assert sink.calls == [], f"AC-1: _post ohne Empfaenger sendete: {sink.calls!r}"


# ═══════════════════════════ AC-2 ════════════════════════════════════════════


@pytest.mark.parametrize("zustand", ["unbestaetigt", "abweichend", "leer", "kein_profil"])
def test_ac2_unbestaetigte_leere_oder_fehlende_nummer_blockt(sink, zustand):
    """AC-2: Given Nutzer B, dessen Nummer unbestaetigt
    (``sms_verified_number`` leer oder abweichend) oder leer ist oder der kein
    Profil hat; die Settings tragen die Betreibernummer / When fuer ihn per
    SMS gesendet werden soll / Then Block mit ``sms_no_recipient``, kein
    HTTP-Versuch (kein Rueckfall auf ``settings.sms_to``)."""
    if zustand == "unbestaetigt":
        profil_sms(KUNDE_B, NUMMER_B, bestaetigt=False)
    elif zustand == "abweichend":
        profil_sms(KUNDE_B, NUMMER_B, bestaetigt=False, sms_verified_number=NUMMER_A)
    elif zustand == "leer":
        profil_sms(KUNDE_B, "")
    settings = _settings()
    with pytest.raises(ChannelBlockedError) as exc:
        sms_ausgang(settings, KUNDE_B).send("", "Text")
    assert exc.value.reason_code == CODE_SMS_NO_RECIPIENT, exc.value.reason_code
    assert sink.calls == [], f"AC-2 ({zustand}): {sink.calls!r}"


def test_ac2_bestaetigte_nummer_wird_frisch_aus_dem_profil_gelesen(sink):
    """AC-2: Given Nutzer B mit bestaetigter Nummer B, Settings tragen die
    Betreibernummer / When fuer ihn per SMS gesendet wird / Then geht die SMS
    an genau Nummer B (aus ``user.json``), nie an die Settings-Nummer."""
    profil_sms(KUNDE_B, NUMMER_B)
    sms_ausgang(_settings(), KUNDE_B).send("", "Text")
    assert sink.ziele() == [NUMMER_B], f"AC-2: gesehen {sink.ziele()!r}"


# ═══════════════════════════ AC-3 ════════════════════════════════════════════


@pytest.mark.parametrize("profil", ["fehlt", "kaputt"])
def test_ac3_ohne_lesbares_profil_erhaelt_die_betreibernummer_nichts(sink, monkeypatch, profil):
    """AC-3: Given die ``user.json`` des Nutzers fehlt bzw. ist unlesbar und
    ``GZ_SMS_TO`` (Betreibernummer) ist gesetzt / When fuer diesen Nutzer per
    SMS gesendet werden soll (echter ``NotificationService``-Pfad auf
    ``with_user_profile``) / Then wird geblockt, die Betreibernummer erhaelt
    nichts, und ``with_user_profile`` liefert ``sms_to=None``.

    RED heute: ``with_user_profile`` gibt in beiden ``base``-Pfaden die
    Basis-Settings samt ``GZ_SMS_TO`` zurueck; die SMS geht an den Betreiber.
    """
    monkeypatch.setenv("GZ_SMS_TO", BETREIBER)
    base = Settings(
        _env_file=None, env="production", is_test_mode=False,
        sms_gateway_url=GATEWAY, seven_api_key=PROD_KEY, seven_sandbox_key=SANDBOX_KEY,
    )
    assert base.sms_to == BETREIBER, "Vorbedingung: GZ_SMS_TO muss in den Basis-Settings stehen"
    uid = f"kunde-ohne-profil-{profil}"
    if profil == "kaputt":
        ordner = get_data_dir(uid)
        ordner.mkdir(parents=True, exist_ok=True)
        (ordner / "user.json").write_text("{kaputt")

    nutzer_settings = base.with_user_profile(uid)
    assert nutzer_settings.sms_to is None, (
        f"AC-3 ({profil}): with_user_profile muss sms_to=None liefern, ist {nutzer_settings.sms_to!r}"
    )

    # Versand ueber die Profil-Fabrik mit genau diesen Settings. (Der Weg
    # durch den NotificationService taugt hier nicht als Beleg: ohne lesbares
    # Profil ist der Tarif unbekannt und das Tageslimit #2412 sperrt schon
    # vorher -- der Test waere aus dem falschen Grund gruen.)
    with pytest.raises(ChannelBlockedError) as exc:
        sms_ausgang(nutzer_settings, uid).send("", "Text")
    assert exc.value.reason_code == CODE_SMS_NO_RECIPIENT, exc.value.reason_code
    assert BETREIBER not in sink.ziele(), (
        f"AC-3 ({profil}): Cross-Tenant -- die Betreibernummer bekam die SMS: {sink.calls!r}"
    )
    assert sink.calls == [], f"AC-3 ({profil}): {sink.calls!r}"


# ═══════════════════════════ AC-4 ════════════════════════════════════════════


def test_ac4_dienst_mit_model_copy_nummer_von_a_sendet_fuer_b_nur_an_b(sink):
    """AC-4: Given Nutzer A und B mit je bestaetigter Nummer; die Settings des
    Dienstes fuer B tragen per ``model_copy`` die Nummer von A / When fuer B
    eine SMS ausgeloest wird (echter ``NotificationService``) / Then geht sie
    ausschliesslich an Nummer B; spiegelbildlich fuer A.

    RED heute: der Ausgang sendet an ``settings.sms_to`` (= Nummer von A).
    """
    profil_sms(KUNDE_A, NUMMER_A)
    profil_sms(KUNDE_B, NUMMER_B)

    _kein_daten_hinweis(_settings().model_copy(update={"sms_to": NUMMER_A}), KUNDE_B, "sms")
    assert sink.ziele() == [NUMMER_B], f"AC-4: fuer B nur Nummer B erwartet, gesehen {sink.ziele()!r}"

    _kein_daten_hinweis(_settings().model_copy(update={"sms_to": NUMMER_B}), KUNDE_A, "sms")
    assert sink.ziele() == [NUMMER_B, NUMMER_A], f"AC-4: gesehen {sink.ziele()!r}"


def test_ac4_ausgang_fuer_b_ignoriert_settings_nummer_von_a(sink):
    """AC-4: Given Settings per ``model_copy`` mit der Nummer von A und ein
    Empfaenger ``SmsRecipient.for_user(B)`` / When gesendet wird / Then geht
    die SMS an Nummer B (frisch aus B's ``user.json``)."""
    profil_sms(KUNDE_A, NUMMER_A)
    profil_sms(KUNDE_B, NUMMER_B)
    settings_mit_a = _settings().model_copy(update={"sms_to": NUMMER_A})
    sms_ausgang(settings_mit_a, KUNDE_B).send("", "fuer B")
    assert sink.ziele() == [NUMMER_B], f"AC-4: gesehen {sink.ziele()!r}"


@pytest.mark.parametrize("kanal", ["sms", "premium_sms"])
def test_ac4_abweichendes_payload_ziel_blockt_im_einzigen_ausgang(sink, kanal):
    """AC-4 (Mismatch): Given ein Ausgang mit Empfaenger ``for_user(B)`` /
    When der einzige Ausgang ``_post`` mit einer Nutzlast an die Nummer von A
    aufgerufen wird / Then Mismatch-Block mit ``reason_code``, kein
    HTTP-Versuch."""
    settings = _settings()
    if kanal == "sms":
        profil_sms(KUNDE_A, NUMMER_A)
        out, fremdziel = sms_ausgang(settings, KUNDE_B, NUMMER_B), NUMMER_A
    else:
        profil_rueckadresse(KUNDE_A, RUECK_A)
        out, fremdziel = premium_ausgang(settings, KUNDE_B, RUECK_B), RUECK_A
    with pytest.raises(ChannelBlockedError) as exc:
        out._post(GATEWAY, PROD_KEY, {"to": fremdziel, "text": "x"})
    assert exc.value.reason_code, "AC-4: Mismatch-Block braucht einen reason_code"
    assert sink.calls == [], f"AC-4: Mismatch erreichte den Draht: {sink.calls!r}"


def test_ac4_block_im_dienst_verbraucht_keinen_drosselplatz(sink):
    """AC-4: Given Nutzer B ohne bestaetigte Nummer; die Settings des Dienstes
    tragen per ``model_copy`` die Nummer von A / When fuer B eine SMS
    ausgeloest wird / Then kein HTTP-Versuch, und B's SMS-Tageszaehler
    (``sms_daily_limit``) bleibt unveraendert.

    RED heute: die SMS geht an Nummer A und verbraucht einen Platz.
    """
    profil_sms(KUNDE_A, NUMMER_A)
    profil_sms(KUNDE_B, NUMMER_B, bestaetigt=False)
    vorher = _verbraucht(KUNDE_B, "sms")
    _kein_daten_hinweis(_settings().model_copy(update={"sms_to": NUMMER_A}), KUNDE_B, "sms")
    assert sink.calls == [], f"AC-4: Block erwartet, gesehen {sink.calls!r}"
    assert _verbraucht(KUNDE_B, "sms") == vorher, "AC-4: Block hat einen Drosselplatz verbraucht"


# ═══════════════════════════ AC-5 ════════════════════════════════════════════


@pytest.mark.parametrize(
    ("fall", "code"),
    [
        ("fehlend", BLOCK_REASON_NO_REPLY_ADDRESS),
        ("zukunft", BLOCK_REASON_REPLY_ADDRESS_STALE),
        ("31_tage", BLOCK_REASON_REPLY_ADDRESS_STALE),
    ],
)
def test_ac5_fehlende_kuenftige_oder_alte_rueckadresse_blockt_mit_bestehendem_code(sink, fall, code):
    """AC-5: Given Nutzer B ohne Rueckadresse bzw. mit Zeitstempel in der
    Zukunft bzw. 31 Tage alt; die Settings tragen eine frische fremde
    Rueckadresse / When ein Premium-SMS-Versand ausgeloest wird / Then Block
    mit ``premium_sms_no_reply_address`` bzw.
    ``premium_sms_reply_address_stale`` (Codes unveraendert), kein HTTP."""
    if fall == "fehlend":
        profil_rueckadresse(KUNDE_B, None, gelernt_vor=None)
    elif fall == "zukunft":
        profil_rueckadresse(KUNDE_B, RUECK_B, gelernt_am=datetime.now(timezone.utc) + timedelta(hours=1))
    else:
        profil_rueckadresse(KUNDE_B, RUECK_B, gelernt_vor=timedelta(days=31))
    settings = _mit_rueck(_settings(), RUECK_SETTINGS)
    with pytest.raises(ChannelBlockedError) as exc:
        premium_ausgang(settings, KUNDE_B).send("", "Text")
    assert exc.value.reason_code == code, exc.value.reason_code
    assert sink.calls == [], f"AC-5 ({fall}): {sink.calls!r}"


def test_ac5_frische_rueckadresse_aus_dem_profil_wird_bedient(sink):
    """AC-5: Given Nutzer B mit frisch gelernter Rueckadresse B; die Settings
    tragen eine andere Rueckadresse / When ein Premium-SMS-Versand ausgeloest
    wird / Then geht die Nachricht nur an Rueckadresse B, mit der festen
    Dienstnummer als Absender."""
    profil_rueckadresse(KUNDE_B, RUECK_B)
    premium_ausgang(_mit_rueck(_settings(), RUECK_SETTINGS), KUNDE_B).send("", "Text")
    assert sink.ziele() == [RUECK_B], f"AC-5: gesehen {sink.ziele()!r}"
    assert sink.calls[0]["from"] == PREMIUM_SMS_SENDER


@pytest.mark.parametrize(
    ("fall", "code"),
    [("fehlend", BLOCK_REASON_NO_REPLY_ADDRESS), ("31_tage", BLOCK_REASON_REPLY_ADDRESS_STALE)],
)
def test_ac5_alarm_buchung_registriert_den_unveraenderten_code(sink, fall, code):
    """AC-5 (Alarm-Buchung): Given Nutzer B ohne bzw. mit veralteter
    Rueckadresse, Settings des Dienstes mit frischer fremder Rueckadresse /
    When eine Amtswarnung nur per Premium-SMS geht (echter Dienst) und das
    Ergebnis ins Alarm-Protokoll gebucht wird (echtes ``append_entry``) /
    Then kein HTTP-Versuch, ``blocked_reason_codes`` und
    ``channels_not_sent`` tragen den unveraenderten Code.

    RED heute: die Premium-SMS geht an die Rueckadresse aus den Settings.
    """
    from services import alert_log
    from services.notification_service import NotificationService

    from tests.helpers.alert_log_fixtures import read_log, reason_for_channel

    if fall == "fehlend":
        profil_rueckadresse(KUNDE_B, None, gelernt_vor=None)
    else:
        profil_rueckadresse(KUNDE_B, RUECK_B, gelernt_vor=timedelta(days=31))
    dienst = NotificationService(_mit_rueck(_settings(), RUECK_SETTINGS), KUNDE_B)
    ergebnis = dienst.send_official_alert(
        trip=_amtswarnung_trip("trip-ac5"), notices=[(_warnung(), ["1"])],
        effective_channels={"premium_sms"},
    )
    assert sink.calls == [], f"AC-5 ({fall}): Block erwartet, gesehen {sink.calls!r}"
    assert ergebnis.blocked_reason_codes.get("premium_sms") == code, ergebnis

    alert_log.append_entry(
        KUNDE_B, entity_id="trip-ac5", entity_type="trip", changes_count=1,
        severity="MODERATE", reason=alert_log.REASON_OFFICIAL_ALERT,
        effective_channels={"premium_sms"}, sent_channels=ergebnis.sent_channels,
        reachable_channels=["premium_sms"],
        blocked_reason_codes=ergebnis.blocked_reason_codes,
    )
    log = read_log(KUNDE_B)
    eintraege = log["entries"] + log["not_delivered"]
    assert eintraege, f"AC-5: kein Protokolleintrag gebucht: {log!r}"
    assert reason_for_channel(eintraege[-1], "premium_sms") == code, eintraege[-1]


# ═══════════════════════════ AC-6 ════════════════════════════════════════════

_VERIF_PFAD = "/api/_internal/sms/verification-code"


class _Antwort:
    """Einheitliche Sicht auf die Rueckgabe des Endpunkts (``dict`` bei
    Erfolg, ``JSONResponse`` bei Fehler)."""

    def __init__(self, roh) -> None:
        if isinstance(roh, dict):
            self.status_code, self._json = 200, roh
        else:
            self.status_code = roh.status_code
            self._json = json.loads(bytes(roh.body).decode() or "null")
        self.text = repr(self._json)

    def json(self):
        return self._json


@pytest.fixture
def endpunkt(monkeypatch):
    """Der ECHTE Routen-Handler des internen Routers
    (``POST /api/_internal/sms/verification-code``), mit der echten
    Pydantic-Nutzlast aufgerufen. Bewusst ohne ``TestClient``: dessen
    Event-Loop braucht ein ``socketpair``, das ``--disable-socket`` sperrt.
    Der Handler baut sein ``Settings()`` selbst -- seven.io-Zugang daher ueber
    die Umgebung (``env_file`` ist per Autouse-Fixture abgeschaltet)."""
    from api.routers import internal

    monkeypatch.setenv("GZ_SMS_GATEWAY_URL", GATEWAY)
    monkeypatch.setenv("GZ_SEVEN_API_KEY", PROD_KEY)
    monkeypatch.setenv("GZ_SEVEN_SANDBOX_KEY", SANDBOX_KEY)
    monkeypatch.setenv("GZ_ENV", "production")
    routen = {getattr(r, "path", None): r for r in internal.router.routes}
    assert _VERIF_PFAD in routen, f"Vorbedingung: Route {_VERIF_PFAD} fehlt"
    return routen[_VERIF_PFAD].endpoint, internal.SmsVerificationCodeRequest


def _code_anfordern(endpunkt, uid: str, nummer: str) -> _Antwort:
    """Ruft den Handler; eine aus ihm entweichende Sperre (``OutputConfigError``
    inkl. ``ChannelBlockedError``) gilt als "nicht gesendet" -- die Spec legt
    nur "geblockt, ohne HTTP-Versuch" fest, nicht die Antwortform."""
    handler, nutzlast = endpunkt
    try:
        roh = handler(nutzlast(user_id=uid, to=nummer, code="428913"))
    except OutputConfigError as e:
        roh = {"error": "blocked", "reason_code": getattr(e, "reason_code", None)}
        antwort = _Antwort(roh)
        antwort.status_code = 403
        return antwort
    return _Antwort(roh)


def test_ac6_code_geht_nur_an_die_eigene_ausstehende_nummer(sink, endpunkt):
    """AC-6: Given Nutzer A mit ``pending_sms_to``=A und Nutzer B mit
    unbestaetigtem ``sms_to``=B (kein pending) / When Go fuer A die Nummer A,
    fuer B die Nummer B und fuer B die Nummer von A anfordert / Then gehen die
    Codes an A bzw. B; die Anforderung von B fuer die Nummer von A wird
    geblockt, ohne HTTP-Versuch.

    RED heute: der Endpunkt sendet an jedes uebergebene ``to``.
    """
    profil_sms(KUNDE_A, "", bestaetigt=False, pending_sms_to=NUMMER_A)
    profil_sms(KUNDE_B, NUMMER_B, bestaetigt=False)

    assert _code_anfordern(endpunkt, KUNDE_A, NUMMER_A).json() == {"status": "sent"}
    assert _code_anfordern(endpunkt, KUNDE_B, NUMMER_B).json() == {"status": "sent"}
    assert sink.ziele() == [NUMMER_A, NUMMER_B], f"AC-6: gesehen {sink.ziele()!r}"
    assert "428913" in sink.calls[0]["text"]

    antwort = _code_anfordern(endpunkt, KUNDE_B, NUMMER_A)
    assert antwort.json() != {"status": "sent"}, f"AC-6: fremde Nummer angenommen: {antwort.text}"
    assert sink.ziele() == [NUMMER_A, NUMMER_B], f"AC-6: Code an fremde Nummer: {sink.ziele()!r}"


@pytest.mark.parametrize("fall", ["fremd", "ohne_plus", "kein_profil"])
def test_ac6_fremde_unfoermige_oder_profillose_nummer_blockt(sink, endpunkt, fall):
    """AC-6: Given eine fremde wohlgeformte Nummer bzw. die ausstehende
    Nummer ohne ``+`` (nicht strikt E.164) bzw. ein Nutzer ohne Profil / When
    Go den Bestaetigungscode fuer diese Nummer anfordert / Then wird
    geblockt, kein HTTP-Versuch.

    RED heute: der Endpunkt setzt ``sms_to=req.to`` per ``model_copy`` und
    sendet.
    """
    if fall == "fremd":
        profil_sms(KUNDE_A, "", bestaetigt=False, pending_sms_to=NUMMER_A)
        uid, nummer = KUNDE_A, FREMD
    elif fall == "ohne_plus":
        profil_sms(KUNDE_A, "", bestaetigt=False, pending_sms_to=NUMMER_A.lstrip("+"))
        uid, nummer = KUNDE_A, NUMMER_A.lstrip("+")
    else:
        uid, nummer = "kunde-ohne-profil", NUMMER_A
    antwort = _code_anfordern(endpunkt, uid, nummer)
    assert antwort.json() != {"status": "sent"}, f"AC-6 ({fall}): {antwort.text}"
    assert sink.calls == [], f"AC-6 ({fall}): {sink.calls!r}"


# ═══════════════════════════ AC-7 ════════════════════════════════════════════


def test_ac7_verification_gibt_es_nur_am_sms_typ_und_nur_fuer_die_profilnummer(sink):
    """AC-7: Given die Empfaenger-Typen / When jemand am Premium-SMS-Typ den
    Zweck ``verification`` sucht bzw. am SMS-Typ ``verification`` mit einer
    nicht an das Profil gebundenen Nummer nutzt / Then gibt es am
    Premium-Typ keine ``verification``-Fabrik, der Zweck existiert in
    ``RecipientPurpose``, und die SMS-Fabrik blockt jede fremde Nummer (auch
    die eines anderen Nutzers) -- nur die eigene ausstehende geht raus."""
    from output.channels.recipient import PremiumSmsRecipient, RecipientPurpose, SmsRecipient

    assert not hasattr(PremiumSmsRecipient, "verification"), (
        "AC-7: Premium-SMS darf keinen Zweck verification anbieten"
    )
    assert RecipientPurpose("verification") is RecipientPurpose.verification
    assert SmsRecipient.verification is not None

    profil_sms(KUNDE_A, "", bestaetigt=False, pending_sms_to=NUMMER_A)
    profil_sms(KUNDE_B, "", bestaetigt=False, pending_sms_to=NUMMER_B)
    settings = _settings()
    for uid, nummer in ((KUNDE_A, FREMD), (KUNDE_B, NUMMER_A), (KUNDE_A, BETREIBER)):
        with pytest.raises(ChannelBlockedError) as exc:
            verifikations_ausgang(settings, uid, nummer).send("", "Code")
        assert exc.value.reason_code, f"AC-7: Block ohne reason_code ({uid}, {nummer})"
    assert sink.calls == [], f"AC-7: verification wurde zum Generalschluessel: {sink.calls!r}"

    verifikations_ausgang(settings, KUNDE_A, NUMMER_A).send("", "Code")
    assert sink.ziele() == [NUMMER_A], f"AC-7: gesehen {sink.ziele()!r}"
    assert SmsRecipient.verification(KUNDE_A, NUMMER_A).purpose == RecipientPurpose.verification


# ═══════════════════════════ AC-8 ════════════════════════════════════════════

_UNFOERMIG = {
    "sms_profil": ["abc", "12; DROP", "123456", "1234567890123456", "+49 151 12a4567"],
    "verification": ["491511234567", "+0151123456", "abc", "12; DROP", "+1234567",
                     "+1234567890123456"],
    "premium": ["abc", "12; DROP", "1234567", "1234567890123456", "+0170000000001"],
}


@pytest.mark.parametrize(
    ("zweck", "nummer"),
    [(z, n) for z, liste in _UNFOERMIG.items() for n in liste],
)
def test_ac8_unfoermige_nummer_blockt_vor_jedem_http_versuch(sink, zweck, nummer):
    """AC-8: Given eine Nummer, die der Form des Zwecks nicht genuegt
    (Produktion, kein Testmodus) und ansonsten belegt ist (bestaetigt bzw.
    ausstehend bzw. frisch gelernt) / When gesendet werden soll / Then Block
    vor jedem HTTP-Versuch: ``verification`` strikt ``^\\+[1-9]\\d{7,14}$``,
    SMS-Profil nur Ziffern/``+``/Leerzeichen/``-``/Klammern mit 7-15
    Ziffern, Premium ``^\\+?[1-9]\\d{7,14}$``."""
    settings = _settings()
    with pytest.raises(ChannelBlockedError) as exc:
        if zweck == "sms_profil":
            profil_sms(KUNDE_B, nummer)
            sms_ausgang(settings, KUNDE_B).send("", "Text")
        elif zweck == "verification":
            profil_sms(KUNDE_B, "", bestaetigt=False, pending_sms_to=nummer)
            verifikations_ausgang(settings, KUNDE_B, nummer).send("", "Code")
        else:
            profil_rueckadresse(KUNDE_B, nummer)
            premium_ausgang(settings, KUNDE_B).send("", "Text")
    assert exc.value.reason_code, f"AC-8 ({zweck}, {nummer!r}): Block ohne reason_code"
    assert sink.calls == [], f"AC-8 ({zweck}, {nummer!r}): {sink.calls!r}"


# ═══════════════════════════ AC-9 ════════════════════════════════════════════


@pytest.mark.parametrize(
    "nummer",
    ["+49 151 123-45 67", "(0151) 123 4567", "0041-79-000 00 01", "1234567", "+491511234567890"],
)
def test_ac9_tolerant_gespeicherte_bestandsnummer_geht_byteidentisch_raus(sink, nummer):
    """AC-9: Given ein Bestandskonto, dessen bestaetigte Nummer tolerant
    geschrieben ist (Leerzeichen, Bindestriche, Klammern; 7 bzw. 15 Ziffern)
    / When fuer diesen Nutzer gesendet wird / Then wird ausgeliefert, und der
    Anbieter sieht die gespeicherte Form byteidentisch (kein Ziffernumbau)."""
    profil_sms(KUNDE_B, nummer)
    sms_ausgang(_settings(), KUNDE_B).send("", "Text")
    assert sink.ziele() == [nummer], f"AC-9: gesehen {sink.ziele()!r}"


# ═══════════════════════════ AC-10 ═══════════════════════════════════════════
# Heute GRUEN (Nicht-Verstummen-Waechter): jeder produktive Aufrufer liefert an
# einen Nutzer mit bestaetigter Nummer bzw. frischer Rueckadresse weiter aus.


def _segment_weather():
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary, TripSegment,
    )

    tag = datetime(2026, 5, 1, tzinfo=timezone.utc)
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="icon_d2", run=tag, grid_res_km=2.0,
        interp="point_grid",
    )
    punkte = [
        ForecastDataPoint(ts=tag + timedelta(hours=9 + h), t2m_c=15.0 + h, wind10m_kmh=10.0 + h)
        for h in range(3)
    ]
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.2, lon=9.05, elevation_m=400.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=1200.0),
        start_time=tag + timedelta(hours=9), end_time=tag + timedelta(hours=13),
        duration_hours=4.0, distance_km=8.0, ascent_m=800.0, descent_m=0.0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=NormalizedTimeseries(meta=meta, data=punkte),
        aggregated=SegmentWeatherSummary(
            temp_min_c=15.0, temp_max_c=20.0, temp_avg_c=17.5, wind_max_kmh=16.0,
            precip_sum_mm=2.4,
        ),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _briefing_trip(trip_id: str):
    from app.models import TripReportConfig
    from app.trip import Stage, Trip, Waypoint

    stage = Stage(
        id="S1", name="Etappe 1", date=date(2026, 5, 1),
        waypoints=[
            Waypoint(id="W1", name="Start", lat=42.2, lon=9.05, elevation_m=400),
            Waypoint(id="W2", name="Ziel", lat=42.25, lon=9.09, elevation_m=1200),
        ],
    )
    return Trip(
        id=trip_id, name=f"Trip-{trip_id}", stages=[stage],
        report_config=TripReportConfig(trip_id=trip_id),
    )


def _amtswarnung_trip(trip_id: str):
    from app.trip import Stage, Trip, Waypoint

    stage = Stage(
        id="s1", name="Tag 1", date=datetime.now(timezone.utc).date(),
        waypoints=[Waypoint(id="w1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0)],
    )
    return Trip(id=trip_id, name=f"Amt-{trip_id}", stages=[stage])


def _warnung():
    from services.official_alerts.models import OfficialAlert

    jetzt = datetime.now(timezone.utc)
    return OfficialAlert(
        source="geosphere_warn", hazard="thunderstorm", level=2, label="Gewitter",
        valid_from=jetzt - timedelta(hours=1), valid_to=jetzt + timedelta(hours=6),
        region_label="Kaernten",
    )


def _boeen_aenderung():
    from app.models import ChangeSeverity, WeatherChange

    return WeatherChange(
        metric="gust_max_kmh", old_value=20.0, new_value=60.0, delta=40.0,
        threshold=20.0, severity=ChangeSeverity.MODERATE, direction="increase",
        segment_id="1",
    )


def _ort(uid: str):
    from app.user import SavedLocation

    return SavedLocation(id=f"loc-{uid}", name="Vergleichsort", lat=47.0, lon=11.0, elevation_m=1000)


def _aufrufer_ausloesen(aufrufer: str, dienst, uid: str, kanal: str):
    """Ein echter Versand ueber den genannten produktiven Aufrufer, nur an
    ``kanal``."""
    from app.models import GPXPoint
    from services.notification_service import RadarAlertRequest, TripReportRequest
    from services.radar_service import NowcastResult

    from tests.helpers.alert_log_fixtures import gust_alert_trip, weather

    kanaele = {kanal}
    if aufrufer == "briefing":
        trip = _briefing_trip(f"trip-{uid}")
        return dienst.send_trip_report(TripReportRequest(
            trip=trip, report_type="evening", segment_weather=[_segment_weather()],
            trip_tz=ZoneInfo("Europe/Paris"), report_config=trip.report_config,
            send_email=False, send_telegram=False,
            send_sms=(kanal == "sms"), send_premium_sms=(kanal == "premium_sms"),
        ))
    if aufrufer == "kein_daten_hinweis":
        return dienst.send_no_data_hint(
            _briefing_trip(f"trip-{uid}"), "morning", send_email=False, send_telegram=False,
            send_sms=(kanal == "sms"), send_premium_sms=(kanal == "premium_sms"),
        )
    if aufrufer == "amtswarnung":
        return dienst.send_official_alert(
            trip=_amtswarnung_trip(f"trip-{uid}"), notices=[(_warnung(), ["1"])],
            effective_channels=kanaele,
        )
    if aufrufer == "ortsvergleich":
        return dienst.send_compare_report(
            subject="Ortsvergleich", html_body="<p>H</p>", text_body="T",
            telegram_text="TG", sms_text="Ortsvergleich SMS", recipients=[],
            effective_channels=kanaele,
        )
    if aufrufer == "ortsvergleich_amtswarnung":
        ort = _ort(uid)
        return dienst.send_multi_location_official_alert(
            "Vergleich S4b", [ort], [(_warnung(), [ort.id])], kanaele,
        )
    if aufrufer == "alarm_trip":
        return dienst.send_deviation_alert(
            gust_alert_trip(f"trip-{uid}"), [weather(1, gust_max_kmh=60.0)],
            [_boeen_aenderung()], kanaele,
        )
    if aufrufer == "alarm_ortsvergleich":
        punkte = [GPXPoint(lat=46.0, lon=7.0, elevation_m=500.0)]
        return dienst.send_multi_location_deviation_alert(
            [("Ort 1", punkte, [_boeen_aenderung()])], kanaele,
        )
    if aufrufer == "regen_radar_trip":
        return dienst.send_radar_alert(
            trip=_amtswarnung_trip(f"trip-{uid}"),
            request=RadarAlertRequest(
                onset_minutes=15, onset_time="12:00", km_from=0.0, km_to=3.0,
                is_convective=False, intensity_label="Regen",
                source_label="Radar (DWD)", tz=ZoneInfo("UTC"), segment_id="1",
            ),
            source="Radar (DWD)", cooldown_display="1 Stunde", effective_channels=kanaele,
        )
    if aufrufer == "regen_radar_ortsvergleich":
        nowcast = NowcastResult(
            onset_minutes=10, intensity_label="leichter Regen", source="radar",
            is_convective=False,
        )
        return dienst.send_multi_location_radar_alert(
            [("Vergleichsort", _ort(uid), nowcast)], kanaele,
        )
    raise ValueError(aufrufer)


_AUFRUFER = [
    "briefing", "kein_daten_hinweis", "amtswarnung", "ortsvergleich",
    "ortsvergleich_amtswarnung", "alarm_trip", "alarm_ortsvergleich",
    "regen_radar_trip", "regen_radar_ortsvergleich",
]


@pytest.mark.parametrize("kanal", ["sms", "premium_sms"])
@pytest.mark.parametrize("aufrufer", _AUFRUFER)
def test_ac10_kein_produktiver_aufrufer_verstummt(sink, aufrufer, kanal):
    """AC-10 (heute gruen, Regressionswaechter): Given Nutzer B mit
    bestaetigter Nummer und frischer Rueckadresse, Settings aus seinem Profil
    (``with_user_profile``) / When der jeweilige produktive Aufrufer
    (Briefing, Kein-Daten-Hinweis, Amtswarnung, Ortsvergleich,
    Ortsvergleich-Amtswarnung, Alarme inkl. Regen/Radar in Trip UND
    Ortsvergleich) nur an SMS bzw. Premium-SMS ausloest / Then geht genau
    EINE Nachricht an Nummer B bzw. Rueckadresse B -- kein Weg verstummt."""
    from services.notification_service import NotificationService

    uid = f"kunde-ac10-{uuid.uuid4().hex[:6]}"
    profil_sms(uid, NUMMER_B)
    profil_rueckadresse(uid, RUECK_B)
    settings = _settings(sms_to=None).with_user_profile(uid)
    ergebnis = _aufrufer_ausloesen(aufrufer, NotificationService(settings, uid), uid, kanal)

    erwartet = NUMMER_B if kanal == "sms" else RUECK_B
    assert sink.ziele() == [erwartet], (
        f"AC-10 ({aufrufer}, {kanal}): genau eine Nachricht an {erwartet} erwartet, "
        f"gesehen {sink.calls!r}; Ergebnis {ergebnis!r}"
    )
    if kanal == "premium_sms":
        assert sink.calls[0]["from"] == PREMIUM_SMS_SENDER
    sent = getattr(ergebnis, "sent_channels", None)
    if sent is not None:
        assert kanal in sent, f"AC-10 ({aufrufer}, {kanal}): Kanal fehlt in sent_channels: {ergebnis!r}"


# ═══════════════════════════ AC-11 ═══════════════════════════════════════════


@pytest.mark.parametrize("lernen", ["erfolgreich", "kollision_409"])
def test_ac11_befehlsantwort_ueber_den_echten_reader(sink, monkeypatch, lernen):
    """AC-11 (heute gruen, Regressionswaechter): Given Nutzer A schickt
    "hilfe" per Premium-SMS ueber den echten Eingang (``_poll_journal`` ->
    ``_verarbeite_befehl``); Nutzer B hat eine eigene frische Rueckadresse /
    When Go die Rueckadresse lernt (200, schreibt ``user.json``) bzw. wegen
    Kollision #2328 ablehnt (409) / Then geht die Antwort ueber den
    Profil-Empfaenger an die gerade gelernte Rueckadresse (= Absender) -- bzw.
    bei 409 gar keine Antwort; B erhaelt nie etwas."""
    import services.inbound_sms_reader as reader_mod

    if lernen == "kollision_409":
        # A hat eine aeltere, noch zustellbare Rueckadresse (innerhalb der
        # 30-Tage-Frist) -- sonst blockte der Kanal eine faelschliche Antwort
        # ohnehin, und der Fall bewachte nichts.
        profil_rueckadresse(KUNDE_A, RUECK_A, gelernt_vor=timedelta(days=1))
    else:
        profil_rueckadresse(KUNDE_A, None, gelernt_vor=None)
    profil_rueckadresse(KUNDE_B, RUECK_B)
    monkeypatch.setenv("GZ_CORE_SHARED_SECRET", "s4b-geheimnis")
    monkeypatch.setenv("GZ_GO_API_URL", "http://go-api.invalid")

    journal = [{
        "id": "1", "from": RUECK_A, "to": reader_mod.SERVICE_NUMBER,
        "text": "hilfe inreachlink.com/g-0Ab1Cd2Ef (47.2692, 11.4041)",
        "timestamp": "2026-10-25 08:30:14",
    }]
    monkeypatch.setattr(
        httpx, "get",
        lambda url, headers=None, params=None, timeout=None, **kw: httpx.Response(
            200, json=journal, request=httpx.Request("GET", url)),
    )
    lernaufrufe: list = []

    def _lern_endpunkt(url, json=None):  # noqa: A002 -- Signatur wie httpx
        lernaufrufe.append(json)
        anfrage = httpx.Request("POST", url)
        if lernen == "kollision_409":
            return httpx.Response(409, json={"error": "premium_number_collision"}, request=anfrage)
        profil_rueckadresse(KUNDE_A, (json or {})["from"], gelernt_vor=timedelta(seconds=1))
        return httpx.Response(200, json={"status": "ok", "user_id": KUNDE_A}, request=anfrage)

    sink.fremd = _lern_endpunkt
    reader_mod.InboundSmsReader()._poll_journal(_settings(sms_to=None), dry_run=False)

    assert len(lernaufrufe) == 1, f"Vorbedingung: genau ein Lernaufruf, gesehen {lernaufrufe!r}"
    assert RUECK_B not in sink.ziele(), f"AC-11: fremder Nutzer B erreicht: {sink.calls!r}"
    if lernen == "erfolgreich":
        assert sink.ziele() == [RUECK_A], f"AC-11: Antwort an die gelernte Adresse erwartet: {sink.calls!r}"
        assert sink.calls[0]["from"] == PREMIUM_SMS_SENDER
    else:
        assert sink.calls == [], f"AC-11: bei 409 keine Antwort erlaubt: {sink.calls!r}"


# ═══════════════════════════ AC-12 ═══════════════════════════════════════════


@pytest.mark.parametrize("kanal", ["sms", "premium_sms"])
def test_ac12_get_channel_ohne_nutzer_lehnt_mit_klarer_meldung_ab(sink, kanal):
    """AC-12: Given die Debug-CLI ohne Nutzer (globale Settings mit
    Betreibernummer bzw. Rueckadresse) / When ``get_channel("sms")`` bzw.
    ``get_channel("premium_sms")`` angefordert und gesendet wird / Then klare
    Ablehnung (Meldung nennt den Kanal), 0 HTTP-Versuche.

    RED heute: ``get_channel`` liefert einen Ausgang, der still an
    ``settings.sms_to`` bzw. die Settings-Rueckadresse sendet.
    """
    from output.channels.base import get_channel

    settings = _mit_rueck(_settings(), RUECK_SETTINGS)
    # Fix-Loop 1 (F004): verengt -- die Ablehnung kommt schon beim ANFORDERN
    # als OutputConfigError des Kanals, nicht erst ein Block beim Senden.
    with pytest.raises(OutputConfigError) as exc:
        get_channel(kanal, settings)
    assert exc.value.channel == kanal, f"AC-12: falscher Kanal: {exc.value!r}"
    erwartet = "sms" if kanal == "sms" else "premium"
    assert erwartet in str(exc.value).lower(), f"AC-12: Meldung unklar: {exc.value!r}"
    assert sink.calls == [], f"AC-12: kein HTTP-Versuch erlaubt, gesehen {sink.calls!r}"


# ═══════════════════════════ AC-13 ═══════════════════════════════════════════


@pytest.mark.parametrize("kanal", ["sms", "premium_sms"])
def test_ac13_zwei_nutzer_abwechselnd_erreichen_nur_ihre_eigene_nummer(sink, kanal):
    """AC-13: Given Nutzer A und B mit je eigener bestaetigter Nummer bzw.
    Rueckadresse und EINEM gemeinsamen Settings-Objekt / When abwechselnd
    A, B, A, B gesendet wird / Then trifft jede Nachricht genau die Nummer
    ihres Nutzers (Mandantentrennung)."""
    settings = _mit_rueck(_settings(), RUECK_SETTINGS)
    if kanal == "sms":
        profil_sms(KUNDE_A, NUMMER_A)
        profil_sms(KUNDE_B, NUMMER_B)
        bauen, ziel = sms_ausgang, {KUNDE_A: NUMMER_A, KUNDE_B: NUMMER_B}
    else:
        profil_rueckadresse(KUNDE_A, RUECK_A)
        profil_rueckadresse(KUNDE_B, RUECK_B)
        bauen, ziel = premium_ausgang, {KUNDE_A: RUECK_A, KUNDE_B: RUECK_B}
    reihenfolge = [KUNDE_A, KUNDE_B, KUNDE_A, KUNDE_B]
    for uid in reihenfolge:
        bauen(settings, uid).send("", f"fuer {uid}")
    assert sink.ziele() == [ziel[u] for u in reihenfolge], f"AC-13: gesehen {sink.ziele()!r}"


# ═══════════════════════════ AC-14 ═══════════════════════════════════════════


def test_ac14_sandbox_guard_im_testmodus_bleibt_wirksam(sink):
    """AC-14: Given Testmodus und ein belegter Empfaenger / When der aktive
    Schluessel der Prod-Key ist bzw. der Sandbox-Key / Then blockt der
    Sandbox-Key-Guard den Prod-Key (``OutputConfigError``, kein HTTP), und mit
    dem Sandbox-Key geht der Versuch ausschliesslich mit dem Sandbox-Key an
    den Draht (sendet laut seven.io nie echt)."""
    profil_sms(KUNDE_B, NUMMER_B)
    prod = _settings(is_test_mode=True, seven_api_key=PROD_KEY)
    with pytest.raises(OutputConfigError) as exc:
        sms_ausgang(prod, KUNDE_B).send("", "Text")
    assert "Sandbox" in str(exc.value), f"AC-14: falscher Block: {exc.value!r}"
    assert sink.calls == [], f"AC-14: Prod-Key im Testmodus am Draht: {sink.calls!r}"

    sandbox = _settings(is_test_mode=True, seven_api_key=SANDBOX_KEY)
    sms_ausgang(sandbox, KUNDE_B).send("", "Text")
    assert [(c["to"], c["api_key"]) for c in sink.calls] == [(NUMMER_B, SANDBOX_KEY)], sink.calls


def test_ac14_herkunftssperre_schaltet_weiter_auf_den_sandbox_key(sink, monkeypatch):
    """AC-14: Given Testlauf-Herkunft (``_guard_code_origin``) und ein
    belegter Empfaenger / When mit dem Prod-Key gesendet wird / Then geht der
    Versuch mit dem Sandbox-Key an die Empfaengernummer -- der Herkunfts-Guard
    greift unveraendert."""
    monkeypatch.setattr(sms_mod, "running_origin", lambda module_file: "test")
    profil_sms(KUNDE_B, NUMMER_B)
    sms_ausgang(_settings(), KUNDE_B).send("", "Text")
    assert [(c["to"], c["api_key"]) for c in sink.calls] == [(NUMMER_B, SANDBOX_KEY)], sink.calls


@pytest.mark.parametrize("fall", ["ohne_empfaenger", "unfoermig"])
def test_ac14_empfaengerpruefung_laeuft_vor_herkunft_und_guards(sink, monkeypatch, fall):
    """AC-14 (Reihenfolge Form -> Herkunft -> Guards): Given Testlauf-Herkunft
    ohne Sandbox-Key und Testmodus mit Prod-Key (beide Guards wuerden
    blocken) / When ein Ausgang ohne Empfaenger bzw. mit unfoermiger Nummer
    senden soll / Then kommt der Block aus der Empfaengerpruefung
    (``ChannelBlockedError`` mit ``reason_code``), nicht aus einem Guard.

    RED heute (ohne_empfaenger): der Sandbox-Guard laeuft zuerst und wirft ein
    schlichtes ``OutputConfigError``.
    """
    monkeypatch.setattr(sms_mod, "running_origin", lambda module_file: "test")
    settings = _settings(is_test_mode=True, seven_sandbox_key=None)
    with pytest.raises(ChannelBlockedError) as exc:
        if fall == "ohne_empfaenger":
            SMSOutput(settings).send("", "Text")
        else:
            profil_sms(KUNDE_B, "12; DROP")
            sms_ausgang(settings, KUNDE_B).send("", "Text")
    assert exc.value.reason_code, f"AC-14 ({fall}): Block ohne reason_code"
    assert sink.calls == []


@pytest.mark.parametrize("kanal", ["sms", "premium_sms"])
def test_ac14_geblockter_versuch_verbraucht_keinen_drosselplatz(sink, kanal):
    """AC-14: Given Nutzer B ohne bestaetigte Nummer bzw. ohne Rueckadresse;
    die Settings des Dienstes tragen trotzdem eine Nummer bzw. frische
    Rueckadresse / When ein Versand durch den echten Dienst laeuft / Then
    kein HTTP-Versuch, und der Tageszaehler (``sms_daily_limit``) des Kanals
    bleibt unveraendert.

    RED heute: der Ausgang sendet an die Settings-Nummer und verbraucht einen
    Platz.
    """
    if kanal == "sms":
        profil_sms(KUNDE_B, NUMMER_B, bestaetigt=False)
        settings = _settings().model_copy(update={"sms_to": NUMMER_B})
    else:
        profil_rueckadresse(KUNDE_B, None, gelernt_vor=None)
        settings = _mit_rueck(_settings(), RUECK_SETTINGS)
    vorher = _verbraucht(KUNDE_B, kanal)
    _kein_daten_hinweis(settings, KUNDE_B, kanal)
    assert sink.calls == [], f"AC-14 ({kanal}): Block erwartet, gesehen {sink.calls!r}"
    assert _verbraucht(KUNDE_B, kanal) == vorher, f"AC-14 ({kanal}): Drosselplatz verbraucht"


# ═══════════════════ Fix-Loop 1 (Adversary F001-F004) ════════════════════════


@pytest.mark.parametrize(
    ("aufrufer", "kanal"),
    [(a, k) for a in _AUFRUFER for k in ("sms", "premium_sms")]
    + [("befehlsantwort", "premium_sms")],  # Befehlsantwort gibt es nur per Premium-SMS
)
def test_f001_block_an_jedem_aufrufer_gibt_die_reservierung_frei_und_bricht_nicht_ab(
    sink, aufrufer, kanal,
):
    """F001 (Kernregel/Aufrufer-Tabelle "im try nach _sms_gate_reserve"):
    Given Nutzer B mit Tarif, aber unbestaetigter Nummer und ohne
    Rueckadresse; die Settings tragen trotzdem eine Nummer bzw. frische
    Rueckadresse / When JEDER produktive Aufrufer (inkl. Befehlsantwort) nur
    an SMS bzw. Premium-SMS ausloest / Then kein HTTP-Versuch, der
    Tageszaehler bleibt unveraendert (Reservierung freigegeben) und der
    Aufruf laeuft ohne Ausnahme weiter."""
    from services.notification_service import NotificationService
    from services.trip_command_processor import CommandResult

    uid = f"kunde-f001-{uuid.uuid4().hex[:6]}"
    profil_sms(uid, NUMMER_B, bestaetigt=False)
    profil_rueckadresse(uid, None, gelernt_vor=None)
    settings = _mit_rueck(_settings(sms_to=NUMMER_B), RUECK_SETTINGS)
    vorher = _verbraucht(uid, kanal)
    dienst = NotificationService(settings, uid)

    if aufrufer == "befehlsantwort":
        dienst.send_command_reply_premium_sms(
            CommandResult(success=True, command="hilfe",
                          confirmation_subject="Hilfe", confirmation_body="Text"),
            settings,
        )
    else:
        _aufrufer_ausloesen(aufrufer, dienst, uid, kanal)

    assert sink.calls == [], f"F001 ({aufrufer}, {kanal}): Block erwartet, gesehen {sink.calls!r}"
    assert _verbraucht(uid, kanal) == vorher, (
        f"F001 ({aufrufer}, {kanal}): Block hat einen Tageslimit-Platz verbraucht"
    )


def _ziffern(text: str) -> str:
    return "".join(c for c in text if c.isdigit())


def test_f002_logs_nennen_die_nutzer_id_nie_die_nummer(sink, caplog):
    """F002 (Side effects der Spec): Given Versand an bestaetigte Nummer bzw.
    frische Rueckadresse sowie Block-Faelle (kein Empfaenger, unbestaetigt,
    abweichendes Ziel) / When protokolliert wird / Then steht weder die
    Nummer noch ihre Ziffernfolge in irgendeinem Logeintrag, und der
    Erfolgslog nennt die Nutzer-ID."""
    import logging

    caplog.set_level(logging.DEBUG)
    settings = _settings()
    sms_ausgang(settings, KUNDE_A, NUMMER_A).send("", "Text")
    premium_ausgang(settings, KUNDE_B, RUECK_B).send("", "Text")
    erfolg = [r.getMessage() for r in caplog.records if "gesendet" in r.getMessage()]
    assert any(KUNDE_A in m for m in erfolg) and any(KUNDE_B in m for m in erfolg), (
        f"F002: Erfolgslog muss die Nutzer-ID nennen: {erfolg!r}"
    )

    with pytest.raises(ChannelBlockedError):
        SMSOutput(settings).send("", "Text")
    profil_sms("kunde-f002", NUMMER_B, bestaetigt=False)
    with pytest.raises(ChannelBlockedError):
        sms_ausgang(settings, "kunde-f002").send("", "Text")
    with pytest.raises(ChannelBlockedError):
        sms_ausgang(settings, KUNDE_A)._post(GATEWAY, PROD_KEY, {"to": NUMMER_B, "text": "x"})

    assert len(sink.calls) == 2
    for record in caplog.records:
        nachricht = _ziffern(record.getMessage())
        for nummer in (NUMMER_A, NUMMER_B, RUECK_B):
            assert _ziffern(nummer) not in nachricht, (
                f"F002: Telefonnummer im Log: {record.getMessage()!r}"
            )


def test_f003_empfaenger_sind_nur_ueber_die_fabriken_erzeugbar():
    """F003: Given die Empfaenger-Typen / When jemand sie direkt (ohne
    Fabrik-Schluessel) konstruiert / Then wirft die Konstruktion."""
    from output.channels.recipient import PremiumSmsRecipient, RecipientPurpose, SmsRecipient

    for typ, zweck in (
        (SmsRecipient, RecipientPurpose.user_profile),
        (SmsRecipient, RecipientPurpose.verification),
        (PremiumSmsRecipient, RecipientPurpose.user_profile),
    ):
        with pytest.raises(TypeError):
            typ(NUMMER_A, zweck, KUNDE_A)
        with pytest.raises(TypeError):
            typ(NUMMER_A, zweck, KUNDE_A, object())


@pytest.mark.parametrize(
    ("alter", "blockt"),
    [(timedelta(days=29), False), (timedelta(days=30, hours=1), True)],
)
def test_f004_frist_der_rueckadresse_ist_genau_30_tage(sink, alter, blockt):
    """F004 (Kernregel 4, TTL 30 Tage): Given eine Rueckadresse, 29 Tage bzw.
    30 Tage + 1 Stunde alt / When gesendet wird / Then geht die 29-Tage-
    Adresse raus, die aeltere blockt mit ``premium_sms_reply_address_stale``."""
    profil_rueckadresse(KUNDE_B, RUECK_B, gelernt_vor=alter)
    if blockt:
        with pytest.raises(ChannelBlockedError) as exc:
            premium_ausgang(_settings(), KUNDE_B).send("", "Text")
        assert exc.value.reason_code == BLOCK_REASON_REPLY_ADDRESS_STALE
        assert sink.calls == []
    else:
        premium_ausgang(_settings(), KUNDE_B).send("", "Text")
        assert sink.ziele() == [RUECK_B]
