"""Empfaengervertrag Telegram -- Transport und Empfaenger-Objekt.

Spec: docs/specs/modules/fix_1412_s4a_empfaengervertrag_telegram.md
(AC-1, AC-2, AC-3, AC-5, AC-6, AC-9, AC-10, AC-12, AC-13)

Nachweisform (Spec-Abschnitt "Acceptance Criteria"):
* Sink am ``httpx``-Rand (``output.channels.telegram.httpx.post``), der eine
  ECHTE ``httpx.Response`` (mit ``request``) zurueckgibt -- KEIN ``_post``-Stub
  (Lehre #1288), kein Mock()/MagicMock/patch().
* Geprueft wird der Ziel-Chat in der Nutzlast (``payload["chat_id"]``) bzw.
  der Bot-Token in der URL, nicht nur die Aufrufzahl.
* ``is_test_mode=False`` (ausser AC-12 True-Fall).
* Herkunft auf "production" festgenagelt: ``_guard_code_origin`` haengt am
  Checkout-Ort (``running_origin``); im Worktree schriebe er jede Chat-ID auf
  den Test-Chat um und die Chat-Faelle maessen nichts (Vorbild
  ``test_telegram_post_is_single_guarded_exit.py``).
* ``.env``-Isolation: ``Settings.model_config["env_file"] = None`` (Vorbild
  ``_ohne_dotenv``, ``tests/test_public_host_links.py``), alle Settings mit
  ``_env_file=None`` und expliziten Werten.
* Datenwurzel: per-Test-Isolation aus ``tests/conftest.py`` (#1133); Profile
  ueber ``get_data_dir(uid)``. Nutzerkennungen ohne "test"/"tdd" (sonst
  erzwingt ``is_test_user_id`` den Testmodus).
* Chat-IDs sind numerisch (sonst blockte die neue Formpruefung AC-6 aus dem
  falschen Grund).

Die neue API (``output.channels.recipient``) wird INNERHALB der Testfunktionen
importiert, damit jeder Test einzeln aus seinem eigenen Grund rot wird.
"""
from __future__ import annotations

import json
import logging

import httpx
import pytest

from app.config import Settings
from app.loader import get_data_dir
from output.channels import telegram as telegram_mod
from output.channels.base import ChannelBlockedError, OutputConfigError, OutputError
from output.channels.telegram import (
    TelegramOutput,
    reset_telegram_rate_limit_for_tests,
)

PROD_TOKEN = "111111:prod-token"
TEST_TOKEN = "222222:test-token"
GLOBAL_CHAT = "900000001"  # globaler .env-Chat (Betreiber)
TEST_CHAT = "424242"
CHAT_A = "100000001"
CHAT_B = "200000002"


# ---------------------------------------------------------------------------
# Sink am httpx-Rand
# ---------------------------------------------------------------------------


def _bot_ok(request: httpx.Request, message_id: int = 4242) -> httpx.Response:
    return httpx.Response(
        200, json={"ok": True, "result": {"message_id": message_id}}, request=request,
    )


class _HttpxSink:
    """Zeichnet jeden ``httpx.post`` auf und gibt echte ``httpx.Response``
    zurueck. ``antworten``: Liste von Fabriken ``(request) -> Response``, der
    Reihe nach; danach immer 200/ok. ``bei_aufruf``: optionaler Haken, der VOR
    der Antwort mit der Aufrufnummer laeuft."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.antworten: list = []
        self.bei_aufruf = None

    def __call__(self, url, json=None, timeout=None, **kwargs):
        request = httpx.Request("POST", url, json=json)
        self.calls.append({"url": url, "payload": dict(json or {})})
        if self.bei_aufruf is not None:
            self.bei_aufruf(len(self.calls))
        if self.antworten:
            return self.antworten.pop(0)(request)
        return _bot_ok(request, message_id=4000 + len(self.calls))

    def chats(self) -> list[str]:
        return [str(c["payload"].get("chat_id")) for c in self.calls if "chat_id" in c["payload"]]


@pytest.fixture(autouse=True)
def _hermetisch(monkeypatch):
    monkeypatch.setattr(telegram_mod, "running_origin", lambda module_file: "production")
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for key in (
        "GZ_TELEGRAM_BOT_TOKEN", "GZ_TELEGRAM_CHAT_ID", "GZ_TELEGRAM_TEST_CHAT_ID",
        "GZ_TELEGRAM_TEST_BOT_TOKEN", "GZ_IS_TEST_MODE", "GZ_ENV",
    ):
        monkeypatch.delenv(key, raising=False)
    reset_telegram_rate_limit_for_tests()
    yield
    reset_telegram_rate_limit_for_tests()


@pytest.fixture
def sink(monkeypatch) -> _HttpxSink:
    s = _HttpxSink()
    monkeypatch.setattr(telegram_mod.httpx, "post", s)
    return s


def _settings(**overrides) -> Settings:
    werte = dict(
        _env_file=None,
        env="production",
        is_test_mode=False,
        telegram_bot_token=PROD_TOKEN,
        telegram_chat_id=GLOBAL_CHAT,
        telegram_test_chat_id=TEST_CHAT,
        telegram_test_bot_token=TEST_TOKEN,
    )
    werte.update(overrides)
    return Settings(**werte)


def _profil(user_id: str, **felder) -> None:
    ordner = get_data_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "user.json").write_text(json.dumps({"id": user_id, **felder}))


# ═══════════════════════════ AC-1 ════════════════════════════════════════════


def test_ac1_ohne_empfaenger_wird_send_geblockt_ohne_http_call(sink):
    """AC-1.

    GIVEN ein ``TelegramOutput``, gebaut OHNE Empfaenger-Objekt, mit
          Einstellungen, die einen (globalen) Chat tragen.
    WHEN  es eine Nachricht senden soll.
    THEN  ``ChannelBlockedError`` mit ``reason_code`` -- und kein einziger
          HTTP-Call.

    RED heute: ``send`` liest ``settings.telegram_chat_id`` und sendet an
    den globalen Chat.
    """
    out = TelegramOutput(_settings())
    with pytest.raises(ChannelBlockedError) as exc:
        out.send("Betreff", "Text")
    assert exc.value.reason_code, "AC-1: Block braucht einen reason_code"
    assert sink.calls == [], f"AC-1: kein HTTP-Call erlaubt, gesehen: {sink.calls!r}"


@pytest.mark.parametrize("methode", ["edit_message_text", "delete_message"])
def test_ac1_ohne_empfaenger_erreichen_chat_methoden_den_draht_nicht(sink, methode):
    """AC-1 (Kernregel 3/6).

    GIVEN ein ``TelegramOutput`` ohne Empfaenger.
    WHEN  eine chat-gebundene Methode (``edit_message_text``/``delete_message``)
          mit einer Chat-ID aufgerufen wird.
    THEN  geht kein HTTP-Call raus (Block; ob geworfen oder fail-soft
          geschluckt, legt die Spec nicht fest).

    RED heute: beide Methoden senden an die uebergebene Chat-ID.
    """
    out = TelegramOutput(_settings())
    try:
        if methode == "edit_message_text":
            out.edit_message_text(CHAT_A, 1, "Text")
        else:
            out.delete_message(CHAT_A, 1)
    except ChannelBlockedError:
        pass
    assert sink.calls == [], f"AC-1: {methode} ohne Empfaenger darf nicht senden: {sink.calls!r}"


# ═══════════════════════════ AC-2 ════════════════════════════════════════════


def test_ac2_for_user_b_sendet_an_b_auch_wenn_settings_den_chat_von_a_tragen(sink):
    """AC-2 (zwei echte Nutzer, CLAUDE.md-Pflicht).

    GIVEN Nutzer A (Chat A) und Nutzer B (Chat B), Einstellungen per
          ``model_copy`` mit dem Chat von A versehen, Empfaenger ``for_user(B)``.
    WHEN  gesendet wird.
    THEN  geht die Nachricht ausschliesslich an Chat B (frisch aus B's
          ``user.json``), nie an A; und spiegelbildlich fuer A.
    """
    from output.channels.recipient import TelegramRecipient

    _profil("nutzer-a", telegram_chat_id=CHAT_A)
    _profil("nutzer-b", telegram_chat_id=CHAT_B)

    settings_mit_a = _settings().model_copy(update={"telegram_chat_id": CHAT_A})
    TelegramOutput(
        settings_mit_a, recipient=TelegramRecipient.for_user("nutzer-b", settings_mit_a),
    ).send("Betreff", "fuer B")
    assert sink.chats() == [CHAT_B], f"AC-2: nur Chat B erwartet, gesehen {sink.chats()!r}"

    settings_mit_b = _settings().model_copy(update={"telegram_chat_id": CHAT_B})
    TelegramOutput(
        settings_mit_b, recipient=TelegramRecipient.for_user("nutzer-a", settings_mit_b),
    ).send("Betreff", "fuer A")
    assert sink.chats() == [CHAT_B, CHAT_A], (
        f"AC-2: zweite Nachricht nur an Chat A erwartet, gesehen {sink.chats()!r}"
    )


def test_ac2_for_user_ohne_eigenen_chat_blockt_trotz_fremdem_chat_in_settings(sink):
    """AC-2.

    GIVEN Nutzer A mit Chat, Nutzer B OHNE Chat im Profil, Einstellungen
          tragen per ``model_copy`` den Chat von A.
    WHEN  fuer B gesendet wird.
    THEN  Block (``ChannelBlockedError``), kein HTTP-Call, A erhaelt nichts.
    """
    from output.channels.recipient import TelegramRecipient

    _profil("nutzer-a", telegram_chat_id=CHAT_A)
    _profil("nutzer-b", mail_to="b@henemm.com")
    settings_mit_a = _settings().model_copy(update={"telegram_chat_id": CHAT_A})

    with pytest.raises(ChannelBlockedError):
        TelegramOutput(
            settings_mit_a,
            recipient=TelegramRecipient.for_user("nutzer-b", settings_mit_a),
        ).send("Betreff", "fuer B")
    assert sink.calls == [], f"AC-2: kein HTTP-Call erlaubt, gesehen {sink.calls!r}"


# ═══════════════════════════ AC-3 ════════════════════════════════════════════


@pytest.mark.parametrize("zustand", ["fehlt", "unlesbar", "ohne_chat", "leerer_chat"])
def test_ac3_profil_ohne_chat_blockt_mit_reason_code_trotz_env_chat(sink, caplog, zustand):
    """AC-3.

    GIVEN die ``user.json`` eines Nutzers fehlt / ist unlesbar / enthaelt
          keinen (oder einen leeren) Chat, und ein globaler ``.env``-Chat ist
          gesetzt (``settings.telegram_chat_id``).
    WHEN  fuer ihn gesendet werden soll.
    THEN  Block mit ``reason_code=telegram_no_chat_id``, kein HTTP-Call; das
          Log nennt die Nutzer-ID, nie die (globale) Chat-ID.

    Ob ``for_user`` selbst oder erst ``send`` blockt, legt die Spec nicht
    fest -- beide stehen im selben ``pytest.raises``.
    """
    from output.channels.recipient import TelegramRecipient

    uid = f"profil-{zustand.replace('_', '-')}"
    if zustand == "unlesbar":
        ordner = get_data_dir(uid)
        ordner.mkdir(parents=True, exist_ok=True)
        (ordner / "user.json").write_text("{kein json")
    elif zustand == "ohne_chat":
        _profil(uid, mail_to="x@henemm.com")
    elif zustand == "leerer_chat":
        _profil(uid, telegram_chat_id="")

    caplog.set_level(logging.DEBUG)
    settings = _settings()
    with pytest.raises(ChannelBlockedError) as exc:
        TelegramOutput(
            settings, recipient=TelegramRecipient.for_user(uid, settings),
        ).send("Betreff", "Text")

    assert exc.value.reason_code == "telegram_no_chat_id"
    assert sink.calls == [], f"AC-3: kein HTTP-Call erlaubt, gesehen {sink.calls!r}"
    texte = [r.getMessage() for r in caplog.records]
    assert any(uid in t for t in texte), f"AC-3: Log muss die Nutzer-ID {uid!r} nennen: {texte!r}"
    assert not any(GLOBAL_CHAT in t for t in texte), (
        f"AC-3: Log darf die Chat-ID {GLOBAL_CHAT!r} nicht nennen: {texte!r}"
    )


# ═══════════════════════════ AC-5 ════════════════════════════════════════════


@pytest.mark.parametrize("profilwert", [300000003, "300000003"])
def test_ac5_profil_chat_als_zahl_oder_text_wird_zugestellt(sink, profilwert):
    """AC-5 (Profilseite).

    GIVEN ein Profil-Chat als JSON-Zahl bzw. als Text.
    WHEN  fuer diesen Nutzer gesendet wird.
    THEN  wird nicht faelschlich geblockt; Ziel ist genau dieser Chat
          (normalisiert verglichen), nicht der globale.
    """
    from output.channels.recipient import TelegramRecipient

    _profil("nutzer-zahl", telegram_chat_id=profilwert)
    settings = _settings()
    TelegramOutput(
        settings, recipient=TelegramRecipient.for_user("nutzer-zahl", settings),
    ).send("Betreff", "Text")
    assert sink.chats() == ["300000003"], f"AC-5: gesehen {sink.chats()!r}"


@pytest.mark.parametrize(
    "absender, antwort_an, erlaubt",
    [
        (400000004, "400000004", True),   # int aus Update, str als Antwortziel
        ("400000004", 400000004, True),   # str im Beleg, int als Antwortziel
        (400000004, "400000005", False),  # fremder Chat
        ("400000004", 400000005, False),  # fremder Chat, Typen vertauscht
    ],
)
def test_ac5_inbound_reply_vergleicht_int_und_str_normalisiert(
    sink, absender, antwort_an, erlaubt,
):
    """AC-5 (Antwortseite).

    GIVEN der Herkunftsbeleg ``_current_inbound_sender`` (Absender des
          laufenden Updates) als Zahl bzw. Text, und ein Empfaenger
          ``inbound_reply(chat_id)`` mit dem jeweils anderen Typ.
    WHEN  gesendet wird.
    THEN  gleicher Chat -> zugestellt; fremder Chat -> Block ohne HTTP-Call.

    Der Beleg wird ueber die in der Spec benannte ContextVar gesetzt (sie IST
    der Vertrag zwischen Reader und Transport); der Reader-Weg selbst ist in
    ``test_telegram_inbound_reply_contract.py`` abgedeckt.
    """
    from output.channels.recipient import TelegramRecipient
    from services.inbound_telegram_reader import _current_inbound_sender

    token = _current_inbound_sender.set(absender)
    try:
        out = TelegramOutput(_settings(), recipient=TelegramRecipient.inbound_reply(antwort_an))
        if erlaubt:
            out.send("Betreff", "Antwort")
            assert sink.chats() == ["400000004"], f"AC-5: gesehen {sink.chats()!r}"
        else:
            with pytest.raises(ChannelBlockedError):
                out.send("Betreff", "Antwort")
            assert sink.calls == [], f"AC-5: fremder Chat darf nicht raus: {sink.calls!r}"
    finally:
        _current_inbound_sender.reset(token)


# ═══════════════════════════ AC-6 ════════════════════════════════════════════


@pytest.mark.parametrize(
    "chat", ["abc", "12; DROP", "", "1" * 21, "12a", "+491701234567", "-", "1 2",
             "\u0661\u0662\u0663"],  # F006: arabisch-indische Ziffern (nur ASCII zulaessig)
)
def test_ac6_nicht_numerische_chat_id_blockt_vor_jedem_http_call(sink, chat):
    """AC-6.

    GIVEN eine nicht-numerische (bzw. leere / ueberlange) Chat-ID im Profil,
          Produktion (``is_test_mode=False``).
    WHEN  gesendet werden soll.
    THEN  Block vor jedem HTTP-Call (0 Sink-Aufrufe).
    """
    from output.channels.recipient import TelegramRecipient

    _profil("nutzer-form", telegram_chat_id=chat)
    settings = _settings()
    with pytest.raises(ChannelBlockedError):
        TelegramOutput(
            settings, recipient=TelegramRecipient.for_user("nutzer-form", settings),
        ).send("Betreff", "Text")
    assert sink.calls == [], f"AC-6: {chat!r} darf nicht raus: {sink.calls!r}"


@pytest.mark.parametrize("chat", ["abc", "12; DROP", "1" * 21])
def test_ac6_formpruefung_gilt_auch_fuer_antwort_an_den_absender(sink, chat):
    """AC-6 (bedingungslos, auch ``inbound_reply``).

    GIVEN ein Herkunftsbeleg mit derselben ungueltigen Chat-ID wie das
          Antwortziel (Herkunft stimmt formal ueberein).
    WHEN  gesendet wird.
    THEN  greift trotzdem die Formpruefung: Block, 0 Sink-Aufrufe.
    """
    from output.channels.recipient import TelegramRecipient
    from services.inbound_telegram_reader import _current_inbound_sender

    token = _current_inbound_sender.set(chat)
    try:
        with pytest.raises(ChannelBlockedError):
            TelegramOutput(
                _settings(), recipient=TelegramRecipient.inbound_reply(chat),
            ).send("Betreff", "Antwort")
    finally:
        _current_inbound_sender.reset(token)
    assert sink.calls == [], f"AC-6: {chat!r} darf nicht raus: {sink.calls!r}"


def test_ac6_gruppen_chat_mit_minus_und_langer_id_bleibt_zustellbar(sink):
    """AC-6 (Gegenprobe gegen eine zu strenge Form).

    GIVEN eine legitime Gruppen-Chat-ID ``-1001234567890`` im Profil.
    WHEN  gesendet wird.
    THEN  wird zugestellt (``-?\\d{1,20}``).
    """
    from output.channels.recipient import TelegramRecipient

    _profil("nutzer-gruppe", telegram_chat_id="-1001234567890")
    settings = _settings()
    TelegramOutput(
        settings, recipient=TelegramRecipient.for_user("nutzer-gruppe", settings),
    ).send("Betreff", "Text")
    assert sink.chats() == ["-1001234567890"], f"AC-6: gesehen {sink.chats()!r}"


# ═══════════════════════════ AC-9 ════════════════════════════════════════════


def test_ac9_html_400_rueckfall_geht_an_denselben_empfaenger(sink):
    """AC-9 (HTML-400-Rueckfall, ADR-0012).

    GIVEN Empfaenger ``for_user(B)``; die Bot-API lehnt den HTML-Versand mit
          400 ab.
    WHEN  der Rueckfall ohne ``parse_mode`` gesendet wird.
    THEN  gehen beide Versuche an Chat B, der zweite ohne ``parse_mode``;
          der Bot-Token in der URL ist der Produktions-Token.
    """
    from output.channels.recipient import TelegramRecipient

    _profil("nutzer-b", telegram_chat_id=CHAT_B)
    sink.antworten = [
        lambda req: httpx.Response(
            400, json={"ok": False, "description": "can't parse entities"}, request=req,
        ),
    ]
    settings = _settings()
    TelegramOutput(
        settings, recipient=TelegramRecipient.for_user("nutzer-b", settings),
    ).send("Betreff", "<b>Text & mehr</b>", parse_mode="HTML")

    assert sink.chats() == [CHAT_B, CHAT_B], f"AC-9: gesehen {sink.chats()!r}"
    assert "parse_mode" not in sink.calls[1]["payload"]
    assert all(f"/bot{PROD_TOKEN}/" in c["url"] for c in sink.calls)


def test_ac9_bei_429_genau_eine_pruefung_und_wiederholung_an_denselben_chat(sink, caplog):
    """AC-9 (429, "genau einmal geprueft").

    GIVEN Empfaenger ``for_user(B)``; die Bot-API antwortet zuerst 429
          (``retry_after=0``), dann 200. Zwischen erstem Versuch und
          Wiederholung wird B's ``user.json`` entfernt.
    WHEN  der Versand einmal wiederholt wird.
    THEN  genau 2 POSTs, beide an Chat B; die Wiederholung wird NICHT neu
          geprueft (sonst blockte sie jetzt mangels Profil-Chat bzw. loggte
          doppelt); die 429-Warnung erscheint genau einmal, es gibt keinen
          Block-Logeintrag.

    Wahl des Zaehlers (dokumentiert, Auftrag): die Spec legt keinen Log-Text
    fuer "Pruefung gelaufen" fest. Gezaehlt wird deshalb ueber die Sink-
    Aufrufzahl + Ziel-Chat je Aufruf, die bestehende 429-Warnung
    ("drosselt", genau einmal) und das Fehlen jedes Block-Eintrags. Das
    Entfernen des Profils zwischen den Versuchen macht eine (verbotene)
    Neupruefung beim Retry beobachtbar.
    """
    from output.channels.recipient import TelegramRecipient

    _profil("nutzer-b", telegram_chat_id=CHAT_B)
    settings = _settings()
    out = TelegramOutput(settings, recipient=TelegramRecipient.for_user("nutzer-b", settings))

    sink.antworten = [
        lambda req: httpx.Response(
            429, json={"ok": False, "parameters": {"retry_after": 0}}, request=req,
        ),
    ]

    def _profil_weg(nr: int) -> None:
        if nr == 1:
            (get_data_dir("nutzer-b") / "user.json").unlink()

    sink.bei_aufruf = _profil_weg
    caplog.set_level(logging.DEBUG)
    mid = out.send("Betreff", "Text")

    assert mid is not None
    assert sink.chats() == [CHAT_B, CHAT_B], f"AC-9: gesehen {sink.chats()!r}"
    texte = [r.getMessage() for r in caplog.records]
    assert sum("drosselt" in t for t in texte) == 1, f"AC-9: 429-Warnung genau einmal: {texte!r}"
    assert not any("telegram_no_chat_id" in t or "blockiert" in t.lower() for t in texte), (
        f"AC-9: keine (zweite) Pruefung beim Retry erwartet: {texte!r}"
    )


def test_ac9_jede_bubble_als_frische_instanz_traegt_den_empfaenger(sink):
    """AC-9 (Bubbles, ADR-0014 frische Instanz je Bubble).

    GIVEN ein Empfaenger ``for_user(B)`` und eine Nachricht aus drei Bubbles,
          je Bubble eine frische ``TelegramOutput``-Instanz (wie der
          Briefing-Versand in ``notification_service``).
    WHEN  die Bubbles nacheinander gesendet werden.
    THEN  traegt jede Bubble den Empfaenger: drei POSTs, alle an Chat B.

    Bewusst auf Transportebene: der volle Briefing-Pfad wird in /50 ueber die
    Migration der bestehenden Briefing-Tests mitgezogen.
    """
    from output.channels.recipient import TelegramRecipient

    _profil("nutzer-b", telegram_chat_id=CHAT_B)
    settings = _settings()
    empfaenger = TelegramRecipient.for_user("nutzer-b", settings)
    for teil in ("eins", "zwei", "drei"):
        TelegramOutput(settings, recipient=empfaenger).send(
            "Betreff", teil, parse_mode="HTML", suppress_subject_line=True,
        )
    assert sink.chats() == [CHAT_B, CHAT_B, CHAT_B], f"AC-9: gesehen {sink.chats()!r}"


# ═══════════════════════════ AC-10 ═══════════════════════════════════════════


def test_ac10_answer_callback_query_ohne_empfaenger_unveraendert(sink):
    """AC-10 -- Erhaltung, bewusst gruen.

    GIVEN ein ``TelegramOutput`` ohne Empfaenger.
    WHEN  ``answer_callback_query`` aufgerufen wird.
    THEN  geht genau ein Aufruf an ``answerCallbackQuery`` mit dem
          Produktions-Token (kein Chat, keine Empfaengerpruefung).
    """
    TelegramOutput(_settings()).answer_callback_query("cq-1")
    assert len(sink.calls) == 1
    assert sink.calls[0]["url"].endswith(f"/bot{PROD_TOKEN}/answerCallbackQuery")
    assert sink.calls[0]["payload"] == {"callback_query_id": "cq-1"}


def test_ac10_set_my_commands_ohne_empfaenger_unveraendert(sink):
    """AC-10 -- Erhaltung, bewusst gruen.

    GIVEN ein ``TelegramOutput`` ohne Empfaenger.
    WHEN  ``set_my_commands`` aufgerufen wird.
    THEN  geht genau ein Aufruf an ``setMyCommands`` (kein Chat, kein Block).
    """
    TelegramOutput(_settings()).set_my_commands()
    assert len(sink.calls) == 1
    assert sink.calls[0]["url"].endswith(f"/bot{PROD_TOKEN}/setMyCommands")
    assert "chat_id" not in sink.calls[0]["payload"]


def test_ac10_bot_menue_bleibt_fail_soft(sink):
    """AC-10 -- Erhaltung, bewusst gruen.

    GIVEN die Bot-API lehnt ``setMyCommands`` mit 500 ab.
    WHEN  der Start-Haken ``api.main._init_telegram_bot_menu`` laeuft.
    THEN  wirft er nicht (fail-soft) und hat genau einen Aufruf versucht.
    """
    from api.main import _init_telegram_bot_menu

    sink.antworten = [lambda req: httpx.Response(500, json={"ok": False}, request=req)]
    _init_telegram_bot_menu(_settings())
    assert len(sink.calls) == 1


# ═══════════════════════════ AC-12 ═══════════════════════════════════════════


def test_ac12_testkontext_liefert_test_chat(sink):
    """AC-12 (True-Fall).

    GIVEN ``settings.is_test_mode=True`` (bestehendes Signal) und ein Nutzer
          mit eigenem Profil-Chat.
    WHEN  ``for_user`` den Empfaenger liefert und gesendet wird.
    THEN  ist der Ziel-Chat die ``telegram_test_chat_id``, nicht der
          Profil-Chat.
    """
    from output.channels.recipient import TelegramRecipient

    _profil("nutzer-b", telegram_chat_id=CHAT_B)
    settings = _settings(
        is_test_mode=True, telegram_bot_token=TEST_TOKEN, telegram_chat_id=TEST_CHAT,
    )
    TelegramOutput(
        settings, recipient=TelegramRecipient.for_user("nutzer-b", settings),
    ).send("Betreff", "Text")
    assert sink.chats() == [TEST_CHAT], f"AC-12: gesehen {sink.chats()!r}"


def test_ac12_ohne_testkontext_liefert_profil_chat(sink):
    """AC-12 (False-Fall).

    GIVEN ``settings.is_test_mode=False`` und ein Test-Chat ist konfiguriert.
    WHEN  ``for_user`` den Empfaenger liefert und gesendet wird.
    THEN  ist der Ziel-Chat der Profil-Chat.
    """
    from output.channels.recipient import TelegramRecipient

    _profil("nutzer-b", telegram_chat_id=CHAT_B)
    settings = _settings()
    TelegramOutput(
        settings, recipient=TelegramRecipient.for_user("nutzer-b", settings),
    ).send("Betreff", "Text")
    assert sink.chats() == [CHAT_B], f"AC-12: gesehen {sink.chats()!r}"


def test_recipient_purpose_kennt_die_zwei_zwecke():
    """Kernregel 7 (Grundlage AC-2/AC-4/AC-12).

    GIVEN die neue Aufzaehlung ``RecipientPurpose``.
    WHEN  sie gelesen wird.
    THEN  kennt sie ``user_profile`` und ``inbound_reply``, und die Fabriken
          tragen den jeweiligen Zweck.
    """
    from output.channels.recipient import RecipientPurpose, TelegramRecipient

    _profil("nutzer-b", telegram_chat_id=CHAT_B)
    assert TelegramRecipient.for_user("nutzer-b", _settings()).purpose == RecipientPurpose.user_profile
    assert TelegramRecipient.inbound_reply("500000005").purpose == RecipientPurpose.inbound_reply


# ═══════════════════════════ AC-13 ═══════════════════════════════════════════


def test_ac13_debug_cli_kanal_telegram_wird_mit_klarer_meldung_abgelehnt(sink):
    """AC-13.

    GIVEN die Debug-CLI ohne Nutzer (globale ``.env`` mit Chat und Token).
    WHEN  sie ueber ``get_channel("telegram", settings)`` den Telegram-Kanal
          anfordert und senden will.
    THEN  wird mit klarer Meldung (nennt Telegram) abgelehnt, 0 HTTP-Calls.

    Ob ``get_channel`` selbst oder erst ``send`` ablehnt, legt die Spec nicht
    fest -- beide stehen im selben ``pytest.raises``.

    RED heute: ``get_channel`` liefert ``TelegramOutput(settings)``, der an
    den globalen Chat sendet.
    """
    from output.channels.base import get_channel

    with pytest.raises((ChannelBlockedError, OutputConfigError, OutputError, ValueError)) as exc:
        get_channel("telegram", _settings()).send("GZ Report", "Text")
    assert "telegram" in str(exc.value).lower(), f"AC-13: Meldung unklar: {exc.value!r}"
    assert sink.calls == [], f"AC-13: kein HTTP-Call erlaubt, gesehen {sink.calls!r}"


# ═══════════════════════ Fix-Loop 1 (Adversary F001-F004, F007) ══════════════


def _sender(chat):
    from output.channels.recipient import _current_inbound_sender

    return _current_inbound_sender.set(chat)


@pytest.mark.parametrize("methode", ["send", "edit", "delete"])
def test_f001_befehlsantwort_wege_treffen_genau_die_uebergebene_chat_id(sink, methode):
    """F001 (R7, Wirkort statt Code-Ort).

    GIVEN ein laufendes Update von Absender 700000011; die Einstellungen
          tragen den globalen Betreiber-Chat.
    WHEN  ``NotificationService.send_telegram_message`` /
          ``edit_telegram_message_text`` / ``delete_telegram_message`` mit
          ``chat_id=700000011`` gegen das ECHTE ``TelegramOutput`` laeuft.
    THEN  geht genau EIN POST der passenden Bot-Methode an 700000011 und der
          Dienst meldet Erfolg.
    """
    from output.channels.recipient import _current_inbound_sender
    from services.notification_service import NotificationService

    settings = _settings()
    dienst = NotificationService(settings=settings, user_id=None)
    token = _sender("700000011")
    try:
        if methode == "send":
            ok = dienst.send_telegram_message(
                chat_id="700000011", subject="S", body="B", settings=settings,
            ) is not None
            bot_methode = "/sendMessage"
        elif methode == "edit":
            ok = dienst.edit_telegram_message_text(
                chat_id="700000011", message_id=5, text="T", settings=settings,
            )
            bot_methode = "/editMessageText"
        else:
            ok = dienst.delete_telegram_message(
                chat_id="700000011", message_id=5, settings=settings,
            )
            bot_methode = "/deleteMessage"
    finally:
        _current_inbound_sender.reset(token)

    assert ok, f"F001: {methode} meldet keinen Erfolg"
    assert len(sink.calls) == 1 and sink.calls[0]["url"].endswith(bot_methode), sink.calls
    assert sink.chats() == ["700000011"], f"F001: gesehen {sink.chats()!r}"


def test_f002_429_wiederholung_prueft_den_herkunftsbeleg_nicht_erneut(sink):
    """F002 (AC-9, "genau einmal geprueft" -- am Wirkort messbar).

    GIVEN Empfaenger ``inbound_reply(700000012)`` im laufenden Update; die
          Bot-API antwortet zuerst 429 (``retry_after=0``). Zwischen erstem
          POST und Wiederholung wird der Herkunftsbeleg geleert -- eine
          (verbotene) zweite Pruefung beim Retry wuerde jetzt blocken.
    WHEN  der Versand einmal wiederholt wird.
    THEN  genau 2 POSTs an 700000012, Zustellung erfolgreich.
    """
    from output.channels.recipient import TelegramRecipient, _current_inbound_sender

    token = _sender("700000012")
    sink.antworten = [
        lambda req: httpx.Response(
            429, json={"ok": False, "parameters": {"retry_after": 0}}, request=req,
        ),
    ]

    def _beleg_weg(nr: int) -> None:
        if nr == 1:
            _current_inbound_sender.set(None)

    sink.bei_aufruf = _beleg_weg
    try:
        mid = TelegramOutput(
            _settings(), recipient=TelegramRecipient.inbound_reply("700000012"),
        ).send("Betreff", "Text")
    finally:
        _current_inbound_sender.reset(token)
    assert mid is not None
    assert sink.chats() == ["700000012", "700000012"], f"F002: gesehen {sink.chats()!r}"


@pytest.mark.parametrize("methode", ["edit_message_text", "delete_message"])
def test_f003_profil_empfaenger_von_b_blockt_fremden_ziel_chat_von_a(sink, methode):
    """F003 (Mandantentrennung, zwei Nutzer).

    GIVEN Nutzer A (Chat A) und B (Chat B); Ausgang mit ``for_user(B)``.
    WHEN  eine chat-gebundene Methode mit dem Chat von A aufgerufen wird.
    THEN  ``ChannelBlockedError`` mit ``telegram_recipient_mismatch``, 0 POSTs.
    """
    from output.channels.recipient import TelegramRecipient

    _profil("nutzer-a", telegram_chat_id=CHAT_A)
    _profil("nutzer-b", telegram_chat_id=CHAT_B)
    settings = _settings()
    out = TelegramOutput(settings, recipient=TelegramRecipient.for_user("nutzer-b", settings))
    with pytest.raises(ChannelBlockedError) as exc:
        if methode == "edit_message_text":
            out.edit_message_text(CHAT_A, 1, "Text")
        else:
            out.delete_message(CHAT_A, 1)
    assert exc.value.reason_code == "telegram_recipient_mismatch"
    assert sink.calls == [], f"F003: {sink.calls!r}"


def test_f003_antwort_empfaenger_blockt_abweichendes_ziel_als_mismatch(sink):
    """F003 (inbound_reply): Empfaenger 700000013 im Update von 700000013,
    Ziel der Methode ist 700000014 -> ``telegram_recipient_mismatch``, 0 POSTs."""
    from output.channels.recipient import TelegramRecipient, _current_inbound_sender

    token = _sender("700000013")
    try:
        out = TelegramOutput(_settings(), recipient=TelegramRecipient.inbound_reply("700000013"))
        with pytest.raises(ChannelBlockedError) as exc:
            out.edit_message_text("700000014", 1, "Text")
    finally:
        _current_inbound_sender.reset(token)
    assert exc.value.reason_code == "telegram_recipient_mismatch"
    assert sink.calls == []


def test_f004_testmodus_prueft_das_original_ziel_nicht_den_settings_chat(sink):
    """F004 (#1288-Guard am Wirkort).

    GIVEN Testmodus mit korrektem Test-Token; ``settings.telegram_chat_id``
          IST der Test-Chat, das Original-Ziel (Absender des Updates) ist ein
          anderer Chat.
    WHEN  ``send`` laeuft.
    THEN  blockt der #1288-Guard (er prueft das Original-Ziel), 0 POSTs.
    """
    from output.channels.recipient import TelegramRecipient, _current_inbound_sender

    settings = _settings(
        is_test_mode=True, telegram_bot_token=TEST_TOKEN, telegram_chat_id=TEST_CHAT,
    )
    token = _sender("700000015")
    try:
        with pytest.raises(OutputConfigError) as exc:
            TelegramOutput(
                settings, recipient=TelegramRecipient.inbound_reply("700000015"),
            ).send("Betreff", "Text")
    finally:
        _current_inbound_sender.reset(token)
    assert "Issue #1288" in str(exc.value), str(exc.value)
    assert sink.calls == []


def test_f007_drossel_und_429_logs_nennen_die_chat_id_nicht(sink, caplog):
    """F007 (Spec: Logs nennen nie die Chat-ID).

    GIVEN Empfaenger ``for_user(B)``; Drossel auf 1 Nachricht je 0.05 s, die
          Bot-API antwortet beim ersten POST mit 429.
    WHEN  zwei Nachrichten nacheinander gesendet werden (Wartezeile der
          Drossel UND 429-Warnung entstehen).
    THEN  enthaelt keine Logzeile die rohe Chat-ID.
    """
    from output.channels.recipient import TelegramRecipient

    _profil("nutzer-b", telegram_chat_id=CHAT_B)
    settings = _settings(
        telegram_rate_limit_max_per_window=1, telegram_rate_limit_window_seconds=0.05,
    )
    sink.antworten = [
        lambda req: httpx.Response(
            429, json={"ok": False, "parameters": {"retry_after": 0}}, request=req,
        ),
    ]
    caplog.set_level(logging.DEBUG)
    empfaenger = TelegramRecipient.for_user("nutzer-b", settings)
    TelegramOutput(settings, recipient=empfaenger).send("Betreff", "eins")
    TelegramOutput(settings, recipient=empfaenger).send("Betreff", "zwei")

    texte = [r.getMessage() for r in caplog.records]
    assert any("drosselt" in t for t in texte), f"Vorbedingung 429-Log: {texte!r}"
    assert any("Telegram-Drossel: warte" in t for t in texte), f"Vorbedingung Drossel-Log: {texte!r}"
    assert not any(CHAT_B in t for t in texte), f"F007: Chat-ID im Log: {texte!r}"


# ═══════════════════════ Fix-Loop 2 (Adversary F-NEU-1..3) ═══════════════════


def test_fneu1_unvollstaendig_hinweis_geht_an_den_profil_chat(sink):
    """F-NEU-1 (fail-soft-Pfad ``_send_telegram_incomplete_hint``).

    GIVEN Nutzer B mit Profil-Chat B; die Einstellungen tragen den globalen
          Betreiber-Chat; echtes ``NotificationService`` + echtes
          ``TelegramOutput``.
    WHEN  der "Briefing unvollstaendig"-Hinweis fuer 2 fehlende Teile
          ausgeloest wird.
    THEN  geht genau EIN sendMessage-POST an Chat B (fail-soft darf eine
          Fehlverdrahtung nicht verschlucken).
    """
    from types import SimpleNamespace

    from services.notification_service import NotificationService

    _profil("nutzer-b", telegram_chat_id=CHAT_B)
    dienst = NotificationService(settings=_settings(), user_id="nutzer-b")
    dienst._send_telegram_incomplete_hint(SimpleNamespace(email_subject="Briefing"), 2)

    assert len(sink.calls) == 1 and sink.calls[0]["url"].endswith("/sendMessage"), sink.calls
    assert sink.chats() == [CHAT_B], f"F-NEU-1: gesehen {sink.chats()!r}"


def test_fneu2_keine_daten_hinweis_geht_per_telegram_an_den_profil_chat(sink):
    """F-NEU-2 (``send_no_data_hint``, Telegram-Zweig).

    GIVEN Nutzer B mit Profil-Chat B; globaler Betreiber-Chat in Settings.
    WHEN  der "Wetterdaten nicht verfuegbar"-Hinweis NUR per Telegram geht.
    THEN  genau EIN sendMessage-POST an Chat B, Telegram steht in
          ``sent_channels``.
    """
    from types import SimpleNamespace

    from services.notification_service import NotificationService

    _profil("nutzer-b", telegram_chat_id=CHAT_B)
    dienst = NotificationService(settings=_settings(), user_id="nutzer-b")
    ergebnis = dienst.send_no_data_hint(
        SimpleNamespace(name="Trip-B"), "evening", send_email=False, send_telegram=True,
    )

    assert "telegram" in ergebnis.sent_channels, ergebnis
    assert len(sink.calls) == 1 and sink.calls[0]["url"].endswith("/sendMessage"), sink.calls
    assert sink.chats() == [CHAT_B], f"F-NEU-2: gesehen {sink.chats()!r}"


def test_fneu3_drossel_abbruch_nennt_die_chat_id_weder_im_log_noch_im_fehler(
    sink, caplog, monkeypatch,
):
    """F-NEU-3 (Drossel-Abbruch, Spec: Logs nennen nie die Chat-ID).

    GIVEN Drossel auf 1 Nachricht je 60 s, Wartefrist auf 0.05 s verkuerzt.
    WHEN  die zweite Nachricht an Chat B den Drossel-Abbruch erzwingt.
    THEN  ``OutputError``; weder die Abbruch-Logzeile noch der Fehlertext
          enthaelt die rohe Chat-ID.
    """
    from output.channels.recipient import TelegramRecipient

    _profil("nutzer-b", telegram_chat_id=CHAT_B)
    monkeypatch.setattr(telegram_mod, "SEND_SLOT_MAX_WAIT_SECONDS", 0.05)
    settings = _settings(
        telegram_rate_limit_max_per_window=1, telegram_rate_limit_window_seconds=60,
    )
    empfaenger = TelegramRecipient.for_user("nutzer-b", settings)
    caplog.set_level(logging.DEBUG)
    TelegramOutput(settings, recipient=empfaenger).send("Betreff", "eins")
    with pytest.raises(OutputError) as exc:
        TelegramOutput(settings, recipient=empfaenger).send("Betreff", "zwei")

    texte = [r.getMessage() for r in caplog.records]
    assert any("Abbruch nach" in t for t in texte), f"Vorbedingung Abbruch-Log: {texte!r}"
    assert "timed out" in str(exc.value), str(exc.value)
    assert not any(CHAT_B in t for t in texte), f"F-NEU-3: Chat-ID im Log: {texte!r}"
    assert CHAT_B not in str(exc.value), f"F-NEU-3: Chat-ID im Fehlertext: {exc.value}"
    assert len(sink.calls) == 1
