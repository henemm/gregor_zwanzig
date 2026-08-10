"""TDD RED — Issue #1676 Scheibe S1: Premium-SMS Rueckkanal, Python-Seite.

`InboundSmsReader.poll_and_process(settings) -> int` existiert noch nicht --
jeder Test schlaegt heute mit ImportError fehl. Vorbild: `InboundEmailReader`/
`InboundTelegramReader` (`poll_and_process(settings)`-Muster).

Boundary-Sinks (kein Live-seven.io-Call, kein Live-Go-Call): `httpx.get` fuer
`journal/inbound`, `httpx.post` fuer den internen Go-Endpoint
`/api/internal/premium-sms-learn`.

**Zustaendigkeitsschnitt (Team-Lead-Korrektur #1676 S1, 2026-08-10):** Diese
Datei prueft ausschliesslich die READER-Verantwortung -- welcher Call, mit
welchem Payload, wie oft, in welcher Reihenfolge. Sie behauptet NICHTS ueber
die tatsaechliche Speicherwirkung (R3-Aufloesung, Read-Modify-Write,
Ueberschreiben in `user.json`) -- das ist Go-Verantwortung und wird gegen
einen ECHTEN Store bewiesen (`internal/handler/premium_sms_connect_test.go`,
insbesondere `TestLearnSetsReplyAddressForSoleUnambiguousPremiumUser` fuer
die Persistenz-Haelfte von AC-1 und `TestLearnOverwritesReplyAddressAcrossCalls`
fuer die Persistenz-Haelfte von AC-3). Der urspruengliche Entwurf hatte einen
Fake, der die Go-Persistenzlogik selbst nachbildete UND selbst schrieb --
die Tests pruefen dann tautologisch gegen ihre eigene Schreibung (Fund: eine
verfaelschte R3-Regel im Fake liess KEINEN Python-Test rot werden). Der
`_LearnCallRecorder` unten schreibt bewusst NICHTS mehr auf die Platte.

Alle Rufnummern sind erfunden (`491700000000x`), einzige echte Nummer ist die
im Issue oeffentliche Dienst-Nummer `4916092172595` als `to`-Feld.

Fix F004 (Produktionsfehler, gemessen 2026-08-10): die echte seven.io-API
liefert `id` als ZEICHENKETTE (`"5283665"`), nicht als Zahl. Die
Fixture-Helfer unten geben `id` deshalb als `str(msg_id)` weiter, exakt wie
die gemessene Antwort -- Zahlen-IDs in Fixtures haetten den Fehler nicht
gefangen (Team-Lead-Befund: kein Test bewachte den echten Datentyp).

SPEC: docs/specs/modules/feat_1676_s1_premium_sms_rueckkanal.md v1.5
"""
from __future__ import annotations

import httpx

SERVICE_NUMBER = "4916092172595"  # oeffentliche Dienst-Nummer aus Issue #1676
GARMIN_FROM_A = "4917000000001"
GARMIN_FROM_B = "4917000000002"
PRIVATE_FROM = "4917000000099"

LEARN_ENDPOINT_SUFFIX = "/api/internal/premium-sms-learn"


class AssertedNetworkTouch(Exception):
    """Beweist, dass der HTTP-Transport trotz Herkunftssperre erreicht wurde."""


def _garmin_message(msg_id: int, sender: str, text_suffix: str = "g-0Ab1Cd2Ef") -> dict:
    return {
        "id": str(msg_id),  # Fix F004: echte API liefert id als Zeichenkette
        "from": sender,
        "to": SERVICE_NUMBER,
        "text": f"Test ueber App inreachlink.com/{text_suffix}... (51.9956, 7.7136)",
        "timestamp": "2026-08-10 08:30:14",
        "reply_to_message_id": None,
        "price": 0.0,
    }


def _private_message(msg_id: int, sender: str) -> dict:
    return {
        "id": str(msg_id),  # Fix F004: echte API liefert id als Zeichenkette
        "from": sender,
        "to": SERVICE_NUMBER,
        "text": "Hallo, bist du morgen da?",
        "timestamp": "2026-08-10 09:19:00",
        "reply_to_message_id": None,
        "price": 0.0,
    }


class _FakeJournalEndpoint:
    """Fake fuer `GET journal/inbound`. `responses` ist eine Liste von
    Journal-Listen -- ein Eintrag je aufeinanderfolgendem Aufruf (letzter
    Eintrag wird bei weiteren Aufrufen wiederholt)."""

    def __init__(self, responses: list[list[dict]]):
        self._responses = responses
        self.calls: list[dict] = []

    def __call__(self, url, headers=None, params=None, timeout=None, **kwargs):
        self.calls.append({"url": url, "headers": headers, "params": params})
        idx = min(len(self.calls) - 1, len(self._responses) - 1)
        return httpx.Response(200, json=self._responses[idx])


class _LearnCallRecorder:
    """Zeichnet Aufrufe von `POST /api/internal/premium-sms-learn` auf und
    antwortet mit einer kanonischen Erfolgs-/Dry-Run-Antwort -- OHNE die
    Vertragslogik des echten Go-Endpoints (R3-Aufloesung, Persistenz)
    nachzubilden und OHNE selbst irgendetwas auf die Platte zu schreiben.

    Das ist bewusst eng: dieser Fake beweist NICHTS ueber die tatsaechliche
    Speicherwirkung, nur darueber, WELCHEN Call der Reader absetzt. Die
    Speicherwirkung wird in `premium_sms_connect_test.go` gegen einen echten
    Store geprueft (Team-Lead-Korrektur #1676 S1 -- ein Fake, der user.json
    selbst schreibt und der Test danach dagegen prueft, waere tautologisch:
    eine verfaelschte R3-Regel im Fake liesse keinen Test hier rot werden)."""

    def __init__(self, user_id: str = "premium-user"):
        self._user_id = user_id
        self.calls: list[dict] = []

    def __call__(self, url, json=None, timeout=None, **kwargs):  # noqa: A002
        self.calls.append({"url": url, "json": json})
        assert url.endswith(LEARN_ENDPOINT_SUFFIX), f"unerwartete URL: {url!r}"

        dry_run = bool((json or {}).get("dry_run"))
        if dry_run:
            return httpx.Response(200, json={"status": "dry_run", "outcome": "would_learn"})
        return httpx.Response(200, json={"status": "ok", "user_id": self._user_id})


def _settings(**overrides):
    from app.config import Settings

    defaults = dict(seven_api_key="prod-configured-key")
    defaults.update(overrides)
    return Settings(**defaults, _env_file=None)


def _fake_production_origin(monkeypatch, reader_mod) -> None:
    monkeypatch.setattr(reader_mod, "classify_origin", lambda root: "production")


# =============================================================================
# Abruf-Vertrag: X-Api-Key-Header, limit-Param, KEIN date_from
# =============================================================================

def test_fetch_uses_x_api_key_header_and_limit_param(monkeypatch):
    """Given production-Herkunft und konfigurierter seven_api_key / When
    poll_and_process() laeuft / Then GET journal/inbound mit Header
    X-Api-Key und limit-Param, aber OHNE date_from."""
    import services.inbound_sms_reader as reader_mod

    _fake_production_origin(monkeypatch, reader_mod)
    fake_get = _FakeJournalEndpoint([[]])
    monkeypatch.setattr(httpx, "get", fake_get)

    reader = reader_mod.InboundSmsReader()
    result = reader.poll_and_process(_settings())

    assert result == 0
    assert len(fake_get.calls) == 1, f"erwartet genau 1 GET, gesehen: {fake_get.calls!r}"
    call = fake_get.calls[0]
    assert "journal/inbound" in call["url"], call["url"]
    assert call["headers"]["X-Api-Key"] == "prod-configured-key"
    assert call["params"] is not None and "limit" in call["params"], call["params"]
    assert "date_from" not in (call["params"] or {}), (
        f"date_from wurde NICHT spezifiziert (Spec-Implementation-Details) -- gesehen: {call['params']!r}"
    )


# =============================================================================
# AC-1 (Reader-Haelfte): eine als Garmin erkannte Nachricht loest GENAU EINEN
# Lernaufruf mit der Absendernummer aus, ohne dry_run-Flag. Die
# Persistenz-Haelfte (dass daraus tatsaechlich premium_sms_reply_to/_at am
# gespeicherten Nutzer wird) beweist
# handler.TestLearnSetsReplyAddressForSoleUnambiguousPremiumUser gegen einen
# echten Store.
# =============================================================================

def test_garmin_marker_message_learns_reply_address(monkeypatch):
    """AC-1 (Reader-Haelfte): Given eine unbekannte Nummer schickt eine
    Garmin-SMS (Kennzeichen inreachlink.com) / When der Poll laeuft / Then
    setzt der Reader GENAU EINEN Lernaufruf ab, mit der Absendernummer als
    `from` und ohne `dry_run`-Flag. Ob daraus tatsaechlich ein persistierter
    `premium_sms_reply_to` wird, ist Go-Verantwortung (siehe Modul-Docstring)."""
    import services.inbound_sms_reader as reader_mod

    _fake_production_origin(monkeypatch, reader_mod)

    fake_get = _FakeJournalEndpoint([[_garmin_message(1001, GARMIN_FROM_A)]])
    fake_post = _LearnCallRecorder()
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)

    reader = reader_mod.InboundSmsReader()
    result = reader.poll_and_process(_settings())

    assert result == 1, f"erwartet 1 gelernte Rueckadresse, bekam {result!r}"
    assert len(fake_post.calls) == 1, f"erwartet genau 1 Lernaufruf, gesehen: {fake_post.calls!r}"

    call = fake_post.calls[0]
    assert call["url"].endswith(LEARN_ENDPOINT_SUFFIX), call["url"]
    assert call["json"]["from"] == GARMIN_FROM_A, (
        f"AC-1: der Lernaufruf muss die Absendernummer tragen, gesehen: {call['json']!r}"
    )
    assert not call["json"].get("dry_run"), (
        f"AC-1: in Produktion darf kein dry_run-Flag gesetzt sein, gesehen: {call['json']!r}"
    )


# =============================================================================
# AC-2: Nachricht ohne Kennzeichen bleibt folgenlos -- kein Lernaufruf
# =============================================================================

def test_message_without_marker_is_ignored(monkeypatch):
    """AC-2: Given eine eingehende SMS OHNE inreachlink.com / When der Poll
    laeuft / Then setzt der Reader KEINEN Lernaufruf ab."""
    import services.inbound_sms_reader as reader_mod

    _fake_production_origin(monkeypatch, reader_mod)

    fake_get = _FakeJournalEndpoint([[_private_message(2001, PRIVATE_FROM)]])
    fake_post = _LearnCallRecorder()
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)

    reader = reader_mod.InboundSmsReader()
    result = reader.poll_and_process(_settings())

    assert result == 0
    assert fake_post.calls == [], (
        f"AC-2: ohne Kennzeichen darf KEIN Lernaufruf erfolgen, gesehen: {fake_post.calls!r}"
    )


# =============================================================================
# AC-3 (Reader-Haelfte): eine zweite, neuere Garmin-Nachricht (andere
# Absendernummer) loest einen ZWEITEN Lernaufruf mit der NEUEN Nummer aus --
# ohne den ersten Aufruf zu wiederholen (id 1 ist bereits ueber die
# Dedup-Zeigerdatei verarbeitet). Dass der zweite reale Aufruf den zuvor
# gespeicherten Wert tatsaechlich VOLLSTAENDIG ueberschreibt, beweist
# handler.TestLearnOverwritesReplyAddressAcrossCalls gegen einen echten Store
# (Spec Implementation Details: "R2 braucht keine eigene Vergleichslogik im
# Python-Reader" -- die Ueberschreib-Semantik ist reine Go-Verantwortung).
# =============================================================================

def test_newest_garmin_message_triggers_second_learn_call_with_new_sender(monkeypatch):
    """AC-3 (Reader-Haelfte): Given eine neue, als Garmin erkannte Nachricht
    von einer ANDEREN Nummer trifft in einem Folge-Poll ein / When der Poll
    laeuft / Then setzt der Reader einen ZWEITEN Lernaufruf mit der NEUEN
    Nummer ab (nicht der alten) -- die tatsaechliche Ueberschreib-Wirkung am
    gespeicherten Datensatz ist Go-Verantwortung (siehe Modul-Docstring)."""
    import services.inbound_sms_reader as reader_mod

    _fake_production_origin(monkeypatch, reader_mod)

    fake_post = _LearnCallRecorder()
    monkeypatch.setattr(httpx, "post", fake_post)

    # Lauf 1: Nachricht von GARMIN_FROM_A wird gelernt.
    fake_get_1 = _FakeJournalEndpoint([[_garmin_message(3001, GARMIN_FROM_A)]])
    monkeypatch.setattr(httpx, "get", fake_get_1)
    reader = reader_mod.InboundSmsReader()
    result_1 = reader.poll_and_process(_settings())
    assert result_1 == 1
    assert len(fake_post.calls) == 1
    assert fake_post.calls[0]["json"]["from"] == GARMIN_FROM_A

    # Lauf 2: neue Nachricht von GARMIN_FROM_B (id > last_seen_id) trifft ein.
    fake_get_2 = _FakeJournalEndpoint(
        [[_garmin_message(3001, GARMIN_FROM_A), _garmin_message(3002, GARMIN_FROM_B)]]
    )
    monkeypatch.setattr(httpx, "get", fake_get_2)
    result_2 = reader.poll_and_process(_settings())
    assert result_2 == 1, f"erwartet 1 NEU gelernte Rueckadresse in Lauf 2, bekam {result_2!r}"

    assert len(fake_post.calls) == 2, (
        f"AC-3: Lauf 2 darf id 3001 NICHT erneut lernen (Dedup, AC-8), nur die neue id 3002 -- "
        f"gesehen: {fake_post.calls!r}"
    )
    assert fake_post.calls[1]["json"]["from"] == GARMIN_FROM_B, (
        f"AC-3: der zweite Lernaufruf muss die NEUE (inhaltlich neueste) Nummer tragen, "
        f"gesehen: {fake_post.calls[1]!r}"
    )


# =============================================================================
# AC-8: Dedup-Zeiger verhindert Doppel-Verarbeitung derselben Nachricht
# =============================================================================

def test_dedup_pointer_prevents_reprocessing(monkeypatch):
    """AC-8: Given eine Garmin-Nachricht wurde bereits verarbeitet (id <=
    last_seen_id) / When sie im naechsten Poll erneut im Journal-Fenster
    auftaucht / Then loest sie KEINEN erneuten Lernaufruf aus und zaehlt
    nicht im Rueckgabewert des zweiten Laufs."""
    import services.inbound_sms_reader as reader_mod

    _fake_production_origin(monkeypatch, reader_mod)

    fake_post = _LearnCallRecorder()
    monkeypatch.setattr(httpx, "post", fake_post)

    same_journal = [_garmin_message(4001, GARMIN_FROM_A)]
    fake_get = _FakeJournalEndpoint([same_journal, same_journal])
    monkeypatch.setattr(httpx, "get", fake_get)

    reader = reader_mod.InboundSmsReader()
    result_1 = reader.poll_and_process(_settings())
    assert result_1 == 1
    assert len(fake_post.calls) == 1

    result_2 = reader.poll_and_process(_settings())
    assert result_2 == 0, f"AC-8: zweiter Lauf mit derselben id darf nichts zaehlen, bekam {result_2!r}"
    assert len(fake_post.calls) == 1, (
        f"AC-8: der Lernaufruf darf beim zweiten Lauf NICHT erneut erfolgen, gesehen: {fake_post.calls!r}"
    )


# =============================================================================
# AC-7: Herkunftssperre ausserhalb production ohne Dry-Run-Schalter
# =============================================================================

def test_non_production_origin_blocks_poll_without_dryrun_switch(monkeypatch):
    """AC-7: Given Nicht-Produktions-Herkunft UND
    GZ_PREMIUM_SMS_POLL_DRYRUN ist NICHT exakt '1' / When poll_and_process()
    aufgerufen wird / Then wird KEIN HTTP-Call ausgefuehrt und die Funktion
    liefert 0."""
    import services.inbound_sms_reader as reader_mod

    monkeypatch.setattr(reader_mod, "classify_origin", lambda root: "test")
    monkeypatch.delenv("GZ_PREMIUM_SMS_POLL_DRYRUN", raising=False)

    def _refusing_get(*args, **kwargs):
        raise AssertedNetworkTouch(
            "httpx.get wurde erreicht -- die Herkunftssperre hat NICHT vor "
            "dem Transport entschieden (AC-7)"
        )

    monkeypatch.setattr(httpx, "get", _refusing_get)

    reader = reader_mod.InboundSmsReader()
    result = reader.poll_and_process(_settings())

    assert result == 0


# =============================================================================
# AC-10 (Reader-Haelfte): Abruf laeuft tatsaechlich, und der Lernaufruf traegt
# das dry_run-Flag -- damit der Go-Endpoint (der die eigentliche Schreibsperre
# durchsetzt) ueberhaupt weiss, dass er nicht schreiben darf. Dass der
# echte Endpoint bei dry_run=true SaveUser NIE erreicht, beweist
# handler.TestLearnDryRunNeverCallsSaveUser gegen einen echten Store.
# =============================================================================

def test_dryrun_switch_polls_journal_and_sends_dryrun_flag(monkeypatch):
    """AC-10 (Reader-Haelfte): Given Nicht-Produktions-Herkunft UND
    GZ_PREMIUM_SMS_POLL_DRYRUN=1 (exakt) UND das Journal enthaelt eine als
    Garmin erkannte Nachricht / When poll_and_process() laeuft / Then wird
    der HTTP-Abruf gegen journal/inbound tatsaechlich ausgefuehrt UND der
    Lernaufruf traegt `dry_run: true` -- die Schreibsperre selbst ist
    Go-Verantwortung (siehe Modul-Docstring)."""
    import services.inbound_sms_reader as reader_mod

    monkeypatch.setattr(reader_mod, "classify_origin", lambda root: "test")
    monkeypatch.setenv("GZ_PREMIUM_SMS_POLL_DRYRUN", "1")

    fake_get = _FakeJournalEndpoint([[_garmin_message(5001, GARMIN_FROM_A)]])
    fake_post = _LearnCallRecorder()
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)

    reader = reader_mod.InboundSmsReader()
    result = reader.poll_and_process(_settings())

    assert len(fake_get.calls) == 1, (
        f"AC-10: der Journal-Abruf MUSS im Dry-Run tatsaechlich stattfinden, gesehen: {fake_get.calls!r}"
    )
    assert len(fake_post.calls) == 1, (
        f"AC-10: die erkannte Garmin-Nachricht muss trotzdem einen (dry_run-)Lernaufruf ausloesen, "
        f"gesehen: {fake_post.calls!r}"
    )
    assert fake_post.calls[0]["json"].get("dry_run") is True, (
        f"AC-10: der Lernaufruf MUSS dry_run=true tragen, sonst wuerde der echte Go-Endpoint "
        f"schreiben -- gesehen: {fake_post.calls[0]!r}"
    )
    assert result == 0, (
        "AC-10: der Dry-Run darf strukturell nie einen Zaehler-Hit ausloesen "
        f"(Schritt 9 der Spec), bekam {result!r}"
    )


def test_dryrun_switch_warns_loudly_on_stderr(monkeypatch, capsys):
    """Vorbild GZ_SKIP_FRONTEND_BROWSER_GATE (staging_gate.py): der
    Dry-Run-Schalter muss laut auf stderr warnen, nicht still durchlaufen."""
    import services.inbound_sms_reader as reader_mod

    monkeypatch.setattr(reader_mod, "classify_origin", lambda root: "test")
    monkeypatch.setenv("GZ_PREMIUM_SMS_POLL_DRYRUN", "1")

    fake_get = _FakeJournalEndpoint([[]])
    monkeypatch.setattr(httpx, "get", fake_get)

    reader = reader_mod.InboundSmsReader()
    reader.poll_and_process(_settings())

    captured = capsys.readouterr()
    assert "GZ_PREMIUM_SMS_POLL_DRYRUN" in captured.err, (
        f"erwartet lauten stderr-Hinweis mit dem Schalternamen, gesehen: {captured.err!r}"
    )


# =============================================================================
# Fix F001 (Adversary-Fund #1676 S1): ein vorruebergehender Lernfehler darf
# die Rueckadresse nicht dauerhaft verlieren -- der Dedup-Zeiger bleibt vor
# der betroffenen Nachricht stehen. Eine BEWUSSTE Ablehnung (HTTP 4xx) ist
# dagegen eine abschliessende Entscheidung und wandert weiter.
# =============================================================================

class _TransientlyFailingLearnRecorder:
    """POST premium-sms-learn: die ersten `fail_times` Aufrufe werfen einen
    Netzwerkfehler (Timeout) -- reproduziert Fix F001 (z.B. Go-API-Neustart
    waehrend des 5-Minuten-Polls). Danach antwortet sie normal erfolgreich."""

    def __init__(self, fail_times: int = 1, user_id: str = "premium-user"):
        self._fail_times = fail_times
        self._user_id = user_id
        self.calls: list[dict] = []

    def __call__(self, url, json=None, timeout=None, **kwargs):  # noqa: A002
        self.calls.append({"url": url, "json": json})
        if len(self.calls) <= self._fail_times:
            raise httpx.TimeoutException("simulierter Netzwerk-Timeout (Fix F001)")
        dry_run = bool((json or {}).get("dry_run"))
        if dry_run:
            return httpx.Response(200, json={"status": "dry_run", "outcome": "would_learn"})
        return httpx.Response(200, json={"status": "ok", "user_id": self._user_id})


def test_transient_learn_failure_keeps_pointer_and_retries_next_run(monkeypatch):
    """Fix F001: Given eine erkannte Garmin-Nachricht, deren Lernaufruf beim
    ersten Versuch an einem Netzwerkfehler scheitert (z.B. Go-API-Neustart
    waehrend des Polls) / When der Poll ein zweites Mal laeuft / Then bleibt
    der Dedup-Zeiger VOR dieser Nachricht stehen -- der naechste Lauf
    versucht dieselbe Nachricht erneut und lernt sie."""
    import services.inbound_sms_reader as reader_mod

    _fake_production_origin(monkeypatch, reader_mod)

    same_journal = [_garmin_message(6001, GARMIN_FROM_A)]
    fake_get = _FakeJournalEndpoint([same_journal, same_journal])
    fake_post = _TransientlyFailingLearnRecorder(fail_times=1)
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)

    reader = reader_mod.InboundSmsReader()

    result_1 = reader.poll_and_process(_settings())
    assert result_1 == 0, "Lauf 1: der Netzwerkfehler darf NICHT als gelernt zaehlen"
    assert reader.last_failed_count == 1, (
        "Lauf 1: der Fehlschlag muss sichtbar gezaehlt werden (Fix F001)"
    )
    assert len(fake_post.calls) == 1

    result_2 = reader.poll_and_process(_settings())
    assert result_2 == 1, (
        f"Lauf 2: dieselbe Nachricht muss erneut versucht und diesmal gelernt "
        f"werden, bekam {result_2!r}"
    )
    assert reader.last_failed_count == 0
    assert len(fake_post.calls) == 2, (
        f"Lauf 2: GENAU EIN weiterer (erfolgreicher) Versuch fuer dieselbe "
        f"Nachricht, gesehen: {fake_post.calls!r}"
    )
    assert fake_post.calls[1]["json"]["from"] == GARMIN_FROM_A


class _ServerErrorThenSuccessLearnRecorder:
    """POST premium-sms-learn: die ersten `fail_times` Aufrufe antworten mit
    einer ECHTEN HTTP-500-Response (kein Netzwerkfehler/Exception) --
    Fund F003 (Adversary): der Go-Endpunkt liefert bei einem Store-Fehler
    (voller Datentraeger, kaputte Datei, Stoerung waehrend SaveUser) genau
    diesen Antwortpfad, nicht den Ausnahme-Pfad. Danach antwortet sie normal
    erfolgreich."""

    def __init__(self, fail_times: int = 1, user_id: str = "premium-user"):
        self._fail_times = fail_times
        self._user_id = user_id
        self.calls: list[dict] = []

    def __call__(self, url, json=None, timeout=None, **kwargs):  # noqa: A002
        self.calls.append({"url": url, "json": json})
        if len(self.calls) <= self._fail_times:
            return httpx.Response(500, text="internal server error (simuliert, Fund F003)")
        dry_run = bool((json or {}).get("dry_run"))
        if dry_run:
            return httpx.Response(200, json={"status": "dry_run", "outcome": "would_learn"})
        return httpx.Response(200, json={"status": "ok", "user_id": self._user_id})


def test_server_error_response_keeps_pointer_and_retries_next_run(monkeypatch):
    """Fund F003 (Adversary, #1676 S1): Given eine erkannte Garmin-Nachricht,
    deren Lernaufruf beim ersten Versuch mit einer ECHTEN HTTP-500-Antwort
    scheitert (kein Netzwerkfehler -- der Go-Endpunkt liefert das z.B. bei
    einem Store-Fehler waehrend SaveUser) / When der Poll ein zweites Mal
    laeuft / Then bleibt der Dedup-Zeiger VOR dieser Nachricht stehen --
    der naechste Lauf versucht dieselbe Nachricht erneut und lernt sie."""
    import services.inbound_sms_reader as reader_mod

    _fake_production_origin(monkeypatch, reader_mod)

    same_journal = [_garmin_message(8001, GARMIN_FROM_A)]
    fake_get = _FakeJournalEndpoint([same_journal, same_journal])
    fake_post = _ServerErrorThenSuccessLearnRecorder(fail_times=1)
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)

    reader = reader_mod.InboundSmsReader()

    result_1 = reader.poll_and_process(_settings())
    assert result_1 == 0, "Lauf 1: der HTTP-500-Fehlschlag darf NICHT als gelernt zaehlen"
    assert reader.last_failed_count == 1, (
        "Lauf 1: der Fehlschlag muss sichtbar gezaehlt werden (Fix F001/F003)"
    )
    assert len(fake_post.calls) == 1

    result_2 = reader.poll_and_process(_settings())
    assert result_2 == 1, (
        f"Lauf 2: dieselbe Nachricht muss erneut versucht und diesmal gelernt "
        f"werden, bekam {result_2!r}"
    )
    assert reader.last_failed_count == 0
    assert len(fake_post.calls) == 2, (
        f"Lauf 2: GENAU EIN weiterer (erfolgreicher) Versuch fuer dieselbe "
        f"Nachricht, gesehen: {fake_post.calls!r}"
    )
    assert fake_post.calls[1]["json"]["from"] == GARMIN_FROM_A


class _RejectingLearnRecorder:
    """POST premium-sms-learn antwortet immer mit HTTP 409 (bewusste
    Ablehnung, AC-5-Mehrdeutigkeit) -- keine Netzwerk-/Serverstoerung."""

    def __init__(self):
        self.calls: list[dict] = []

    def __call__(self, url, json=None, timeout=None, **kwargs):  # noqa: A002
        self.calls.append({"url": url, "json": json})
        return httpx.Response(
            409, json={"status": "skipped", "reason": "no_unique_premium_candidate"},
        )


def test_rejected_learn_advances_pointer_without_retry(monkeypatch):
    """Fix F001 (Gegenprobe): Given eine erkannte Garmin-Nachricht, deren
    Lernaufruf mit HTTP 409 (bewusste Mehrdeutigkeits-Ablehnung, AC-5)
    abgelehnt wird / When derselbe Poll ein zweites Mal laeuft / Then wandert
    der Dedup-Zeiger trotzdem weiter -- kein endloser Wiederholungsversuch
    fuer eine abschliessende Entscheidung."""
    import services.inbound_sms_reader as reader_mod

    _fake_production_origin(monkeypatch, reader_mod)

    same_journal = [_garmin_message(7001, GARMIN_FROM_A)]
    fake_get = _FakeJournalEndpoint([same_journal, same_journal])
    fake_post = _RejectingLearnRecorder()
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)

    reader = reader_mod.InboundSmsReader()

    result_1 = reader.poll_and_process(_settings())
    assert result_1 == 0
    assert reader.last_failed_count == 0, (
        "eine bewusste Ablehnung (409) ist KEIN Fehlschlag im Sinne von Fix F001"
    )
    assert len(fake_post.calls) == 1

    result_2 = reader.poll_and_process(_settings())
    assert result_2 == 0
    assert len(fake_post.calls) == 1, (
        f"Lauf 2 darf die abgelehnte Nachricht NICHT erneut versuchen (der "
        f"Zeiger ist bereits gewandert), gesehen: {fake_post.calls!r}"
    )


def test_router_reports_partial_when_learn_failures_occurred(monkeypatch):
    """Fix F001: Given poll_and_process() meldet mindestens einen
    Fehlschlag / When der Trigger-Endpunkt aufgerufen wird / Then meldet er
    NICHT bedingungslos status=ok, sondern leitet den Status aus dem
    Fehlschlag-Zaehler ab (Hausnorm run_briefing_dispatch(), analog
    scheduler.py:42-44/142-144). HTTP bleibt 200 -- Hausnorm der
    Nachbar-Endpunkte (Issue #766/#1290); die Sichtbarkeit fuer den
    Zeitplaner entsteht ueber den Antwortkoerper, ausgewertet in
    `internal/scheduler/scheduler.go::premiumSmsPoll()` (Fix F002,
    s. dortige Go-Tests)."""
    import api.routers.scheduler as scheduler_router
    import services.inbound_sms_reader as reader_mod

    class _FakeReaderWithFailure:
        def __init__(self):
            self.last_failed_count = 0

        def poll_and_process(self, settings):
            self.last_failed_count = 1
            return 0

    monkeypatch.setattr(reader_mod, "InboundSmsReader", _FakeReaderWithFailure)

    response = scheduler_router.trigger_inbound_sms()

    assert response["status"] != "ok", (
        f"ein Fehlschlag darf NICHT als 'ok' gemeldet werden, bekam {response!r}"
    )
    assert response["failed"] == 1


# =============================================================================
# Fix F004 (Produktionsfehler, gemessen 2026-08-10): die echte seven.io-API
# liefert `id` als Zeichenkette -- der Vergleich `id > last_seen_id` brach
# deshalb mit TypeError ab und legte den Cron-Job alle 5 Minuten lahm.
# =============================================================================

def test_string_ids_are_processed_and_deduplicated_across_runs(monkeypatch):
    """Fix F004: Given das Journal liefert `id` als Zeichenkette (exakt wie
    die echte seven.io-API) / When der Poll zweimal laeuft (zweiter Lauf mit
    derselben plus einer neuen, hoeheren id) / Then wird die Nachricht im
    ersten Lauf korrekt verarbeitet, der Dedup-Zeiger wandert ueber
    Laeufe hinweg weiter, und der zweite Lauf verarbeitet NUR die neue id --
    ohne diesen Fix bricht bereits der erste Lauf mit TypeError ab."""
    import services.inbound_sms_reader as reader_mod

    _fake_production_origin(monkeypatch, reader_mod)

    fake_post = _LearnCallRecorder()
    monkeypatch.setattr(httpx, "post", fake_post)

    # Lauf 1: einzige Nachricht mit String-id "9001" (wie die echte API).
    fake_get_1 = _FakeJournalEndpoint([[_garmin_message(9001, GARMIN_FROM_A)]])
    monkeypatch.setattr(httpx, "get", fake_get_1)
    reader = reader_mod.InboundSmsReader()
    result_1 = reader.poll_and_process(_settings())
    assert result_1 == 1, f"erwartet 1 gelernte Rueckadresse, bekam {result_1!r}"
    assert len(fake_post.calls) == 1
    assert fake_post.calls[0]["json"]["from"] == GARMIN_FROM_A

    # Lauf 2: dieselbe Nachricht (id "9001") plus eine neue (id "9002").
    fake_get_2 = _FakeJournalEndpoint(
        [[_garmin_message(9001, GARMIN_FROM_A), _garmin_message(9002, GARMIN_FROM_B)]]
    )
    monkeypatch.setattr(httpx, "get", fake_get_2)
    result_2 = reader.poll_and_process(_settings())
    assert result_2 == 1, (
        f"Lauf 2 darf NUR die neue id \"9002\" lernen, bekam {result_2!r}"
    )
    assert len(fake_post.calls) == 2, (
        f"Fix F004: id \"9001\" darf im Lauf 2 NICHT erneut gelernt werden "
        f"(Dedup ueber Zeichenketten-IDs hinweg), gesehen: {fake_post.calls!r}"
    )
    assert fake_post.calls[1]["json"]["from"] == GARMIN_FROM_B


def test_unparseable_id_is_skipped_without_aborting_the_run(monkeypatch):
    """Fix F004: Given das Journal-Fenster enthaelt einen Eintrag mit
    NICHT umwandelbarer `id` (`"abc"`) zwischen zwei gueltigen Garmin-
    Nachrichten / When der Poll laeuft / Then werden die beiden gueltigen
    Nachrichten trotzdem verarbeitet -- der kaputte Eintrag wird
    uebersprungen, der Lauf bricht NICHT ab."""
    import services.inbound_sms_reader as reader_mod

    _fake_production_origin(monkeypatch, reader_mod)

    broken_entry = _garmin_message(0, GARMIN_FROM_A)
    broken_entry["id"] = "abc"
    journal = [
        _garmin_message(9101, GARMIN_FROM_A),
        broken_entry,
        _garmin_message(9102, GARMIN_FROM_B),
    ]
    fake_get = _FakeJournalEndpoint([journal])
    fake_post = _LearnCallRecorder()
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)

    reader = reader_mod.InboundSmsReader()
    result = reader.poll_and_process(_settings())

    assert result == 2, (
        f"beide gueltigen Nachrichten muessen trotz kaputter id verarbeitet "
        f"werden, bekam {result!r}"
    )
    assert len(fake_post.calls) == 2, (
        f"der kaputte Eintrag darf den Lauf NICHT abbrechen, gesehen: {fake_post.calls!r}"
    )
    assert {c["json"]["from"] for c in fake_post.calls} == {GARMIN_FROM_A, GARMIN_FROM_B}
