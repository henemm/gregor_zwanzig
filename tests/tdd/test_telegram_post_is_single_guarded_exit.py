"""Waechter (#1412 Scheibe S3b): `TelegramOutput._post` ist der EINE
geschuetzte Netzausgang -- die Test-Modus-Pruefungen haengen am Ausgang, nicht
an der einzelnen oeffentlichen Methode.

Spec: docs/specs/modules/fix_1412_s3b_telegram_sms_ausgang.md (AC-1, AC-2,
AC-4, AC-5, AC-6)

Nachweis ueber ECHTE Sendeaufrufe der oeffentlichen Methoden mit Sink am
Transport (`httpx.post`, Vorbild test_telegram_test_mode_guard.py) -- kein
isolierter Guard-Aufruf, kein Mock der Pruefungen selbst (ADR-0006).

Herkunft festgenagelt
---------------------
`_guard_code_origin` haengt am Ort, von dem der Code laeuft
(`running_origin`). Im Worktree ist das "test", in einem anderen Checkout
womoeglich nicht -- dann griffe je nach Ort mal die Herkunftssperre (#1476),
mal schriebe sie PROD still auf TEST um, und die Chat-Faelle maessen nichts.
Jeder Test hier setzt die Herkunft deshalb ausdruecklich auf "production"
(Vorbild test_telegram_test_isolation.py:226) und prueft im Fehlertext,
WELCHE Pruefung gegriffen hat (#1363 Token, #1288 Settings-Chat, #1363
Argument-Chat).

RED-Erwartung (ehrlich aufgeteilt)
----------------------------------
Bereits heute GRUEN (Regressionsschutz -- die Verlagerung darf sie nicht
kippen): `send`, Rueckfall, `delete_message`, `edit_message_text` in beiden
Fehlerfaellen; `set_my_commands` im Token-Fall; alle Gegenfaelle ohne
Test-Modus bzw. mit korrekter Test-Konfiguration.

Heute ROT: `answer_callback_query` und `get_my_commands` im Token-Fall
(AC-1/AC-4, bisher ohne jede Pruefung), die Unterklasse ohne eigene
Pruefungen (AC-2), "Pruefung vor der Slot-Reservierung" bzw. "genau einmal
bei 429" fuer bisher ungeschuetzte Wege (AC-5) und das Vorhandensein von
`SevenIoChannelBase._post` (AC-6).
"""
from __future__ import annotations

import httpx
import pytest

from app.config import Settings
from output.channels import telegram as telegram_mod
from output.channels.base import OutputConfigError
from output.channels.telegram import (
    TELEGRAM_API_BASE,
    TelegramOutput,
    reset_telegram_rate_limit_for_tests,
)

PROD_CHAT_ID = "777000111"
TEST_CHAT_ID = "424242"
PROD_TOKEN = "prod:token"
TEST_TOKEN = "test:token"

_TOKEN_TEXT = "Test-Bot-Token"


# ---------------------------------------------------------------------------
# Sink am Transport
# ---------------------------------------------------------------------------


class _Antwort:
    def __init__(self, status_code: int = 200, body: dict | None = None) -> None:
        self.status_code = status_code
        self._body = body if body is not None else {
            "ok": True, "result": {"message_id": 4242},
        }
        self.text = str(self._body)

    def json(self):
        return self._body


class _HttpxPostSink:
    """Zeichnet jeden `httpx.post`-Aufruf auf. `antworten` wird der Reihe
    nach ausgegeben, danach immer 200/ok."""

    def __init__(self, antworten: list[_Antwort] | None = None) -> None:
        self.calls: list[dict] = []
        self._antworten = list(antworten or [])

    def __call__(self, url, json=None, timeout=None, **kwargs):
        self.calls.append({"url": url, "payload": json})
        if self._antworten:
            return self._antworten.pop(0)
        return _Antwort()


@pytest.fixture(autouse=True)
def _herkunft_production_und_leere_drossel(monkeypatch):
    monkeypatch.setattr(
        telegram_mod, "running_origin", lambda module_file: "production"
    )
    reset_telegram_rate_limit_for_tests()
    yield
    reset_telegram_rate_limit_for_tests()


@pytest.fixture
def sink(monkeypatch) -> _HttpxPostSink:
    s = _HttpxPostSink()
    monkeypatch.setattr(httpx, "post", s)
    return s


def _settings(**overrides) -> Settings:
    """Korrekte Test-Modus-Konfiguration; die Faelle verfaelschen gezielt
    EIN Feld."""
    werte = dict(
        telegram_bot_token=TEST_TOKEN,
        telegram_test_bot_token=TEST_TOKEN,
        telegram_chat_id=TEST_CHAT_ID,
        telegram_test_chat_id=TEST_CHAT_ID,
        is_test_mode=True,
    )
    werte.update(overrides)
    return Settings(**werte)


def _token_falsch() -> Settings:
    return _settings(telegram_bot_token=PROD_TOKEN)


def _chat_falsch() -> Settings:
    return _settings(telegram_chat_id=PROD_CHAT_ID)


# Die sieben oeffentlichen Sendewege -- je ein ECHTER Aufruf. Chat-gebundene
# Methoden bekommen die Prod-Chat-ID als Argument; ist die Konfiguration
# korrekt, waere das genau der Fall, den #1363 abfaengt.
_CHAT_METHODEN = {
    "send": lambda o: o.send("Betreff", "Text"),
    "fallback_ohne_parse_mode": lambda o: o._send_fallback_without_parse_mode(
        PROD_CHAT_ID, "<b>Text</b>", None, "Betreff"
    ),
    "delete_message": lambda o: o.delete_message(PROD_CHAT_ID, 1),
    "edit_message_text": lambda o: o.edit_message_text(PROD_CHAT_ID, 1, "Text"),
}
_CHATLOSE_METHODEN = {
    "answer_callback_query": lambda o: o.answer_callback_query("cb-1"),
    "set_my_commands": lambda o: o.set_my_commands(None),
    "get_my_commands": lambda o: o.get_my_commands(),
}
_ALLE_METHODEN = {**_CHAT_METHODEN, **_CHATLOSE_METHODEN}


def _mit_test_chat(name):
    """Fuer den Token-Fall bekommen Chat-Methoden die KORREKTE Test-Chat-ID,
    damit ausschliesslich der Token die Ablehnung ausloest."""
    return {
        "send": lambda o: o.send("Betreff", "Text"),
        "fallback_ohne_parse_mode": lambda o: o._send_fallback_without_parse_mode(
            TEST_CHAT_ID, "<b>Text</b>", None, "Betreff"
        ),
        "delete_message": lambda o: o.delete_message(TEST_CHAT_ID, 1),
        "edit_message_text": lambda o: o.edit_message_text(TEST_CHAT_ID, 1, "Text"),
        **_CHATLOSE_METHODEN,
    }[name]


# ---------------------------------------------------------------------------
# AC-1 / AC-4: jede der sieben Methoden blockt mit 0 Netzaufrufen
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(_ALLE_METHODEN))
def test_ac1_ac4_falscher_bot_token_blockt_jede_methode_ohne_netzaufruf(sink, name):
    """AC-1/AC-4: Given Test-Modus mit abweichendem Bot-Token / When eine der
    sieben oeffentlichen Methoden sendet / Then OutputConfigError (#1363
    Token) und 0 Aufrufe an httpx.post.

    RED heute: answer_callback_query und get_my_commands (keine Pruefung)."""
    output = TelegramOutput(_token_falsch())

    with pytest.raises(OutputConfigError) as exc:
        _mit_test_chat(name)(output)

    assert _TOKEN_TEXT in str(exc.value), (
        f"{name}: falsche Pruefung hat gegriffen: {exc.value}"
    )
    assert sink.calls == [], f"{name}: Netzaufruf trotz Blockade: {sink.calls!r}"


@pytest.mark.parametrize("name", sorted(_CHAT_METHODEN))
def test_ac1_fremder_chat_blockt_jede_chat_methode_ohne_netzaufruf(sink, name):
    """AC-1: Given Test-Modus, Ziel ist die Prod-Chat-ID / When eine
    chat-gebundene Methode sendet / Then OutputConfigError mit dem
    Prod-Chat im Text und 0 Netzaufrufe."""
    output = TelegramOutput(_chat_falsch())

    with pytest.raises(OutputConfigError) as exc:
        _CHAT_METHODEN[name](output)

    assert f"chat_id={PROD_CHAT_ID!r}" in str(exc.value), str(exc.value)
    assert sink.calls == [], f"{name}: Netzaufruf trotz Blockade: {sink.calls!r}"


def test_ac1_send_meldet_weiter_die_settings_chat_pruefung_1288(sink):
    """AC-1/AC-3 (Schalter `bound_chat`): `send` prueft den Settings-Chat mit
    dem #1288-Text -- NICHT nur die Argument-Pruefung #1363. Faellt der
    Schalter weg, meldet `send` den #1363-Text und dieser Test wird rot
    (AC-8-Gegenprobe)."""
    output = TelegramOutput(_chat_falsch())

    with pytest.raises(OutputConfigError) as exc:
        output.send("Betreff", "Text")

    assert "Issue #1288" in str(exc.value), str(exc.value)
    assert sink.calls == []


# ---------------------------------------------------------------------------
# AC-4 Gegenfall: ohne Test-Modus aendert sich nichts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(_ALLE_METHODEN))
def test_ac4_ohne_test_modus_sendet_jede_methode_unveraendert(sink, name):
    """AC-4 (Gegenfall): Prod-Normalbetrieb (`is_test_mode=False`) mit
    beliebigem Token/Chat -- jede Methode sendet genau einen POST."""
    output = TelegramOutput(_settings(
        is_test_mode=False,
        telegram_bot_token=PROD_TOKEN,
        telegram_chat_id=PROD_CHAT_ID,
    ))

    _ALLE_METHODEN[name](output)

    assert len(sink.calls) == 1, f"{name}: {sink.calls!r}"


@pytest.mark.parametrize("name", sorted(_ALLE_METHODEN))
def test_korrekte_test_konfiguration_sendet_jede_methode(sink, name):
    """Regressionsschutz gegen Ueberblocken: korrekter Test-Token + Test-Chat
    sendet ueber jede Methode genau einen POST."""
    output = TelegramOutput(_settings())

    _mit_test_chat(name)(output)

    assert len(sink.calls) == 1, f"{name}: {sink.calls!r}"


# ---------------------------------------------------------------------------
# AC-2: eine neue Methode ohne eigene Pruefungen ist trotzdem geschuetzt
# ---------------------------------------------------------------------------


class _NeueMethodeOhnePruefung(TelegramOutput):
    """Simuliert die "achte Methode": ruft `_post` direkt, bringt KEINE
    eigenen Guards mit."""

    def pin_message(self, chat_id, message_id) -> httpx.Response:
        token = self._settings.telegram_bot_token
        url = f"{TELEGRAM_API_BASE}/bot{token}/pinChatMessage"
        return self._post(
            url, {"chat_id": chat_id, "message_id": message_id}, chat_id=chat_id,
        )

    def log_out(self) -> httpx.Response:
        token = self._settings.telegram_bot_token
        return self._post(f"{TELEGRAM_API_BASE}/bot{token}/logOut", {})

    def pin_payload(self, payload: dict) -> httpx.Response:
        """Reicht ein vom Aufrufer gebautes Dict unveraendert an `_post` --
        fuer den Nachweis, dass `_post` dieses Dict nicht veraendert."""
        token = self._settings.telegram_bot_token
        return self._post(
            f"{TELEGRAM_API_BASE}/bot{token}/pinChatMessage", payload,
            chat_id=payload["chat_id"],
        )


def test_ac2_neue_methode_mit_fremdem_chat_wird_am_ausgang_geblockt(sink):
    """AC-2: Given Test-Modus, neue Methode zielt auf den Prod-Chat / When sie
    `_post` ruft / Then OutputConfigError und 0 Netzaufrufe.

    RED heute: `_post` prueft nichts, der Sink faengt den POST."""
    output = _NeueMethodeOhnePruefung(_settings())

    with pytest.raises(OutputConfigError) as exc:
        output.pin_message(PROD_CHAT_ID, 7)

    assert f"chat_id={PROD_CHAT_ID!r}" in str(exc.value), str(exc.value)
    assert sink.calls == []


def test_ac2_neue_methode_mit_falschem_token_wird_am_ausgang_geblockt(sink):
    """AC-2: auch ein chatloser Endpunkt prueft am Ausgang den Token."""
    output = _NeueMethodeOhnePruefung(_token_falsch())

    with pytest.raises(OutputConfigError) as exc:
        output.log_out()

    assert _TOKEN_TEXT in str(exc.value), str(exc.value)
    assert sink.calls == []


def test_ac2_neue_methode_mit_korrekter_konfiguration_sendet(sink):
    """Gegenprobe: der Ausgang blockt nicht pauschal."""
    output = _NeueMethodeOhnePruefung(_settings())

    output.pin_message(TEST_CHAT_ID, 7)

    assert len(sink.calls) == 1
    assert str(sink.calls[0]["payload"]["chat_id"]) == TEST_CHAT_ID


# ---------------------------------------------------------------------------
# AC-5: Pruefung VOR der Drossel und genau EINMAL pro `_post`
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "aufruf",
    [
        pytest.param(lambda: TelegramOutput(_token_falsch()).answer_callback_query("cb"),
                     id="answer_callback_query"),
        pytest.param(lambda: TelegramOutput(_token_falsch()).get_my_commands(),
                     id="get_my_commands"),
        pytest.param(lambda: _NeueMethodeOhnePruefung(_settings()).pin_message(PROD_CHAT_ID, 7),
                     id="neue_methode"),
    ],
)
def test_ac5_geblockter_aufruf_belegt_keinen_drossel_platz(sink, aufruf):
    """AC-5: Given eine Blockade / When `_post` laeuft / Then wird KEIN
    Drossel-Platz reserviert -- die Pruefung laeuft vor `_reserve_send_slot`.
    Gemessen an der echten prozessweiten Buchfuehrung."""
    with pytest.raises(OutputConfigError):
        aufruf()

    assert TelegramOutput._rate_limit_stamps == {}, (
        "Drossel-Platz trotz Blockade belegt: "
        f"{TelegramOutput._rate_limit_stamps!r}"
    )
    assert sink.calls == []


class _ZaehltPruefungen(TelegramOutput):
    """Zaehlt, wie oft die ECHTEN Pruefungen laufen (Weiterreichung, kein
    Ersatz)."""

    def __init__(self, settings):
        super().__init__(settings)
        self.token_pruefungen = 0
        self.ziel_pruefungen = 0

    def _guard_test_mode_bot_token(self) -> None:
        self.token_pruefungen += 1
        super()._guard_test_mode_bot_token()

    def _guard_test_mode_target_chat(self, chat_id) -> None:
        self.ziel_pruefungen += 1
        super()._guard_test_mode_target_chat(chat_id)


def _sink_429_dann_200(monkeypatch) -> _HttpxPostSink:
    s = _HttpxPostSink([
        _Antwort(429, {"ok": False, "parameters": {"retry_after": 0}}),
        _Antwort(200),
    ])
    monkeypatch.setattr(httpx, "post", s)
    return s


@pytest.mark.parametrize(
    "name, aufruf, erwartet_ziel",
    [
        ("answer_callback_query", lambda o: o.answer_callback_query("cb"), 0),
        ("get_my_commands", lambda o: o.get_my_commands(), 0),
        ("delete_message", lambda o: o.delete_message(TEST_CHAT_ID, 1), 1),
    ],
)
def test_ac5_pruefung_laeuft_genau_einmal_auch_bei_429(
    monkeypatch, name, aufruf, erwartet_ziel
):
    """AC-5: Given HTTP 429 beim ersten Versuch / When `_post` einmal
    wiederholt / Then laufen die Pruefungen genau EINMAL (nicht erneut beim
    Wiederholungsversuch), der Sink sieht zwei POSTs.

    RED heute: answer_callback_query/get_my_commands pruefen den Token nie
    (0 statt 1)."""
    s = _sink_429_dann_200(monkeypatch)
    output = _ZaehltPruefungen(_settings())

    aufruf(output)

    assert len(s.calls) == 2, f"{name}: erwartet 429 + Wiederholung: {s.calls!r}"
    assert output.token_pruefungen == 1, (
        f"{name}: Token-Pruefung lief {output.token_pruefungen}x statt genau 1x"
    )
    assert output.ziel_pruefungen == erwartet_ziel, (
        f"{name}: Ziel-Chat-Pruefung lief {output.ziel_pruefungen}x "
        f"statt {erwartet_ziel}x"
    )


# ---------------------------------------------------------------------------
# AC-6: SMS / Premium-SMS -- ein Transport, Guards bleiben in `send`
# ---------------------------------------------------------------------------


def test_ac6_seven_io_basis_hat_einen_transport_post():
    """AC-6: `SevenIoChannelBase._post` ist der eine Transportweg.

    RED heute: die Methode fehlt, `httpx.post` steht direkt in `send`."""
    from output.channels.seven_io_base import SevenIoChannelBase

    assert callable(getattr(SevenIoChannelBase, "_post", None)), (
        "SevenIoChannelBase._post fehlt -- httpx.post steht noch in send()"
    )


def test_ac6_keine_unterklasse_ueberschreibt_send():
    """AC-6 (Begruendung fuer "Guards bleiben in send"): `send` ist der
    gemeinsame Pfad fuer SMS und Premium-SMS -- keine Unterklasse darf ihn
    ueberschreiben, sonst liefe sie an den Pruefungen vorbei."""
    from output.channels.premium_sms import PremiumSmsOutput
    from output.channels.seven_io_base import SevenIoChannelBase
    from output.channels.sms import SMSOutput

    for klasse in (SMSOutput, PremiumSmsOutput):
        assert "send" not in vars(klasse), f"{klasse.__name__} ueberschreibt send()"
        assert klasse.send is SevenIoChannelBase.send


# ---------------------------------------------------------------------------
# Herkunftssperre (#1476) am Ausgang: Umschreibung wirkt auf den POST
# (Adversary-Findings F001/F002/F003)
# ---------------------------------------------------------------------------
#
# Hier wird die Herkunft bewusst auf "test" gestellt (die autouse-Fixture
# oben pinnt "production"). Konfiguration: Test-Chat gesetzt, Token korrekt.
# Im Test-Modus prueft danach die Ziel-Chat-Pruefung den UMGESCHRIEBENEN Chat
# und laesst ihn durch; ohne Test-Modus wirkt allein die Herkunftssperre.

_HERKUNFT_TEST_METHODEN = {
    "fallback_ohne_parse_mode": lambda o: o._send_fallback_without_parse_mode(
        PROD_CHAT_ID, "<b>Text</b>", None, "Betreff"
    ),
    "delete_message": lambda o: o.delete_message(PROD_CHAT_ID, 1),
    "edit_message_text": lambda o: o.edit_message_text(PROD_CHAT_ID, 1, "Text"),
    "neue_methode": lambda o: o.pin_message(PROD_CHAT_ID, 7),
}


@pytest.fixture
def herkunft_test(monkeypatch):
    monkeypatch.setattr(telegram_mod, "running_origin", lambda module_file: "test")


@pytest.mark.parametrize("test_modus", [True, False], ids=["test_modus", "ohne_test_modus"])
@pytest.mark.parametrize("name", sorted(_HERKUNFT_TEST_METHODEN))
def test_herkunft_test_schreibt_den_gesendeten_chat_auf_den_test_chat_um(
    sink, herkunft_test, name, test_modus
):
    """F001/F002: Given Herkunft "test" und konfigurierter Test-Chat / When
    eine Methode mit Prod-Chat-Argument sendet / Then traegt der POST den
    Test-Chat (nie den Prod-Chat), und der Drossel-Platz wird fuer den
    Test-Chat gebucht."""
    output = _NeueMethodeOhnePruefung(_settings(is_test_mode=test_modus))

    _HERKUNFT_TEST_METHODEN[name](output)

    assert len(sink.calls) == 1, f"{name}: {sink.calls!r}"
    gesendet = str(sink.calls[0]["payload"]["chat_id"])
    assert gesendet == TEST_CHAT_ID, (
        f"{name}: POST ging an chat_id={gesendet!r} statt an den Test-Chat"
    )
    assert set(TelegramOutput._rate_limit_stamps) == {TEST_CHAT_ID}, (
        f"{name}: Drossel-Platz fuer {set(TelegramOutput._rate_limit_stamps)!r} "
        "gebucht statt fuer den umgeschriebenen Test-Chat"
    )


@pytest.mark.parametrize("name", sorted(_HERKUNFT_TEST_METHODEN))
def test_herkunft_test_ohne_test_chat_bricht_ohne_netzaufruf_ab(
    sink, herkunft_test, name
):
    """F001 Gegenfall: Given Herkunft "test" OHNE Test-Chat / When gesendet
    wird / Then OutputConfigError der Herkunftssperre und 0 POSTs."""
    output = _NeueMethodeOhnePruefung(_settings(
        is_test_mode=False, telegram_test_chat_id="",
    ))

    with pytest.raises(OutputConfigError) as exc:
        _HERKUNFT_TEST_METHODEN[name](output)

    assert "Herkunftssperre" in str(exc.value), str(exc.value)
    assert sink.calls == [], f"{name}: Netzaufruf trotz Blockade: {sink.calls!r}"


def test_post_veraendert_das_dict_des_aufrufers_nicht(sink, herkunft_test):
    """F003: Given Herkunft "test" (Ziel-Chat wird umgeschrieben) / When eine
    Methode ihr eigenes Payload-Dict an `_post` gibt / Then bleibt dieses
    Dict unveraendert -- umgeschrieben wird nur die gesendete Kopie."""
    output = _NeueMethodeOhnePruefung(_settings())
    payload = {"chat_id": PROD_CHAT_ID, "message_id": 7}
    vorher = dict(payload)

    output.pin_payload(payload)

    assert payload == vorher, f"Aufrufer-Dict veraendert: {payload!r}"
    assert str(sink.calls[0]["payload"]["chat_id"]) == TEST_CHAT_ID
