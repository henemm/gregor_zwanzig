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
insbesondere `TestLearnMatchesCodeToCorrectAccountAmongTwoUsers` fuer die
Persistenz-Haelfte von AC-1, `TestLearnPrefersStoredMatchOverSoleCandidateRule`
fuer die Persistenz-Haelfte von AC-2 und `TestLearnOverwritesReplyAddressAcrossCalls`
fuer die Persistenz-Haelfte von AC-3). Der urspruengliche Entwurf hatte einen
Fake, der die Go-Persistenzlogik selbst nachbildete UND selbst schrieb --
die Tests pruefen dann tautologisch gegen ihre eigene Schreibung (Fund: eine
verfaelschte R3-Regel im Fake liess KEINEN Python-Test rot werden). Der
`_LearnCallRecorder` unten schreibt bewusst NICHTS mehr auf die Platte.

Issue #2323 (14.09.2026): das Content-Gate `GARMIN_MARKER not in text` (Zeile
212) wird durch `message.get("to") != SERVICE_NUMBER` ersetzt -- der
bestehende Go-Lern-Endpunkt (s.o.) entscheidet allein ueber Annahme/Ablehnung,
kein Python-seitiger Vorfilter mehr. Gleichzeitig wechselt `_LINK_CODE_PATTERN`
auf das neue Format `XX`-Praefix + 3 Buchstaben (ohne I/L/O) + 3 Ziffern (ohne
0/1) -- Go-Pendant: `internal/handler/premium_sms_link_code.go`. Derselbe
Zustaendigkeitsschnitt gilt weiter: AC-1/AC-2 dieser Spec pruefen hier nur die
Reader-Haelfte (Payload-Inhalt, weitergereichte `user_id`), nicht die
Aufloesung selbst -- die ist unveraendert und bereits durch die oben genannten
Go-Tests bewiesen.

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


def _private_message_with_text(msg_id: int, sender: str, text: str) -> dict:
    message = _private_message(msg_id, sender)
    message["text"] = text
    return message


def _message_to_other_number(msg_id: int, sender: str) -> dict:
    """Issue #2323 AC-4: eine an eine ANDERE Nummer als die Dienstnummer
    gerichtete Nachricht -- traegt bewusst das Garmin-Kennzeichen im Text,
    damit der Test wirklich das `to`-Gate misst und nicht zufaellig am
    (abzuloesenden) Marker-Gate haengen bleibt."""
    message = _garmin_message(msg_id, sender)
    message["to"] = "4915000000000"  # irgendeine Nummer, garantiert != SERVICE_NUMBER
    return message


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


def _trip_mit_aktiver_etappe(user_id: str, name: str = "SMS Test-Trip") -> None:
    """Legt einen minimalen, HEUTE aktiven Trip fuer ``user_id`` an (Issue
    #2282 AC-5): der Reader bricht seit #2282 VOR ``TripCommandProcessor``
    ab, wenn ``resolve_active_target`` weder Trip noch Ortsvergleich als
    Kandidat findet -- ohne einen echten, aktiven Trip wuerde jede Nachricht
    fuer den hiesigen synthetischen Nutzer den neuen "Kein aktiver Trip oder
    Ortsvergleich"-Text ausloesen statt den Kommandoverarbeiter zu
    erreichen. Der Trip-INHALT ist fuer die hier geprueften Zusicherungen
    (Link-Code-Trennung, Gross-/Kleinschreibung, Payload-Aufbau) irrelevant
    -- er muss nur als Auswahl-Kandidat zaehlen (Zustaendigkeitsschnitt s.
    Modul-Docstring, nur Reader-Haelfte).
    """
    from datetime import date, timedelta

    from app.loader import save_trip
    from app.trip import Stage, Trip, Waypoint

    heute = date.today()
    trip = Trip(
        id=f"trip-{user_id}",
        name=name,
        stages=[
            Stage(
                id="S1", name="Tag 1", date=heute - timedelta(days=1),
                waypoints=[Waypoint(id="W1", name="A", lat=47.0, lon=11.0, elevation_m=800)],
            ),
            Stage(
                id="S2", name="Tag 2", date=heute + timedelta(days=1),
                waypoints=[Waypoint(id="W2", name="B", lat=47.0, lon=11.0, elevation_m=800)],
            ),
        ],
    )
    save_trip(trip, user_id)


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
# Issue #2323 AC-3: Nachricht an die Dienstnummer, ohne Code, von unbekannter
# Nummer -- der ALTE Marker-Gate liess sie mangels "inreachlink.com" im Text
# unversucht (ex-AC-2, `test_message_without_marker_is_ignored`). Das neue
# `to`-Gate reicht JEDE Nachricht an die Dienstnummer weiter; die Aufloesung
# entscheidet ausschliesslich der bestehende Go-Endpunkt (hier simuliert durch
# den zaehlenden 409-Fake, den auch AC-4 unten verwendet).
# =============================================================================

def test_message_to_service_number_without_code_is_attempted_and_rejected(monkeypatch):
    """AC-3: Given eine Nachricht an die Dienstnummer OHNE Code von
    unbekannter Absenderadresse (kein Kennzeichen im Text) / When der Poll
    laeuft / Then setzt der Reader GENAU EINEN Lernaufruf ab, der Go-Endpunkt
    lehnt ihn ab (409) -- kein `learned`-Hit, keine Antwort-SMS (der
    409-Zweig ruft `_verarbeite_befehl` gar nicht erst auf)."""
    import services.inbound_sms_reader as reader_mod

    _fake_production_origin(monkeypatch, reader_mod)

    fake_get = _FakeJournalEndpoint([[_private_message(2001, PRIVATE_FROM)]])
    fake_post = _RejectingLearnRecorder()
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)

    reader = reader_mod.InboundSmsReader()
    result = reader.poll_and_process(_settings())

    assert result == 0
    assert len(fake_post.calls) == 1, (
        f"AC-3: eine Nachricht an die Dienstnummer muss IMMER einen "
        f"Lernaufruf-Versuch ausloesen (der Go-Endpunkt entscheidet ueber "
        f"Annahme/Ablehnung), gesehen: {fake_post.calls!r}"
    )
    assert reader.last_rejected_count == 1, (
        f"AC-3: die Ablehnung muss im eigenen Zaehler auftauchen, "
        f"gesehen: {reader.last_rejected_count!r}"
    )
    assert reader.last_failed_count == 0, (
        "AC-3: eine bewusste 409-Ablehnung ist KEIN voruebergehender Fehlschlag (Fix F001)"
    )


# =============================================================================
# Issue #2323 AC-4: eine Nachricht an eine ANDERE Nummer als die Dienstnummer
# bleibt vollstaendig folgenlos -- unabhaengig davon, ob der Text das
# Garmin-Kennzeichen traegt. Derselbe zaehlende Test-Double wie AC-3 oben,
# damit der einzige Unterschied zwischen "Aufruf erfolgt, wird abgelehnt"
# (AC-3) und "kein Aufruf" (AC-4) an derselben Beobachtungsstelle sichtbar ist.
# =============================================================================

def test_message_to_a_different_number_triggers_no_learn_attempt(monkeypatch):
    """AC-4: Given eine eingehende SMS mit `to` != Dienstnummer (Text traegt
    dennoch das Garmin-Kennzeichen) / When der Poll laeuft / Then setzt der
    Reader KEINEN Lernaufruf-Versuch ab."""
    import services.inbound_sms_reader as reader_mod

    _fake_production_origin(monkeypatch, reader_mod)

    fake_get = _FakeJournalEndpoint([[_message_to_other_number(2002, PRIVATE_FROM)]])
    fake_post = _RejectingLearnRecorder()
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)

    reader = reader_mod.InboundSmsReader()
    result = reader.poll_and_process(_settings())

    assert result == 0
    assert fake_post.calls == [], (
        f"AC-4: eine Nachricht an eine ANDERE Nummer als die Dienstnummer darf "
        f"KEINEN Lernaufruf-Versuch ausloesen -- selbst mit Garmin-Kennzeichen "
        f"im Text, gesehen: {fake_post.calls!r}"
    )
    assert reader.last_rejected_count == 0
    assert reader.last_failed_count == 0


# =============================================================================
# Issue #2323 AC-2: eine bekannte, frische Rueckadresse OHNE Code wird als
# Befehl fuer GENAU DIESEN Nutzer verarbeitet -- Reader-Haelfte: die vom
# Go-Endpunkt gemeldete user_id muss unveraendert bei TripCommandProcessor
# ankommen. Text OHNE Kennzeichen (wie eine formlose Antwort ohne neuen
# Garmin-Link) -- das beweist zugleich, dass das neue `to`-Gate nicht am
# Marker haengt: der ALTE Marker-Gate haette diese Nachricht ignoriert.
# =============================================================================

def test_known_reply_address_without_code_is_processed_for_its_own_user(monkeypatch):
    """AC-2 (Reader-Haelfte): Given eine Nachricht an die Dienstnummer ohne
    Code und ohne Kennzeichen, von einer laut Go-Endpunkt bereits bekannten,
    eindeutigen, frischen Rueckadresse / When der Poll laeuft / Then wird der
    Text vollstaendig als Befehl an TripCommandProcessor uebergeben, mit der
    vom Go-Endpunkt gemeldeten user_id."""
    import services.inbound_sms_reader as reader_mod

    _fake_production_origin(monkeypatch, reader_mod)
    _trip_mit_aktiver_etappe("user-anna")

    fake_get = _FakeJournalEndpoint(
        [[_private_message_with_text(2003, GARMIN_FROM_A, "heute")]]
    )
    fake_post = _LearnCallRecorder(user_id="user-anna")
    recorder = _CommandProcessorRecorder()
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(reader_mod, "TripCommandProcessor", recorder)

    reader = reader_mod.InboundSmsReader()
    result = reader.poll_and_process(_settings())

    assert result == 1
    assert len(fake_post.calls) == 1
    assert "code" not in fake_post.calls[0]["json"], (
        f"AC-2: ohne Code im Text darf KEIN code-Schluessel mitgeschickt "
        f"werden, gesehen: {fake_post.calls[0]['json']!r}"
    )
    assert len(recorder.messages) == 1, (
        f"erwartet genau eine Befehlsverarbeitung, gesehen: {recorder.messages!r}"
    )
    assert recorder.messages[0].user_id == "user-anna", (
        f"AC-2: die vom Go-Endpunkt gemeldete user_id muss unveraendert bei "
        f"TripCommandProcessor ankommen, gesehen: {recorder.messages[0].user_id!r}"
    )
    assert recorder.messages[0].body == "heute", (
        f"AC-2: ohne Kennzeichen bleibt der gesamte Text der Befehl, "
        f"gesehen: {recorder.messages[0].body!r}"
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


def test_transient_failure_halts_the_rest_of_the_journal_window(monkeypatch):
    """Fix F001 (Mehr-Nachrichten-Fall, Adversary #2184 F001): Given ein
    Journal-Fenster mit ZWEI Garmin-Nachrichten, deren erste (niedrigere id)
    an einem Netzwerkfehler scheitert, waehrend die zweite zuzuordnen waere /
    When der Poll laeuft / Then wird die zweite NICHT gelernt und der
    Dedup-Zeiger bleibt VOR der ersten stehen -- der naechste Lauf versucht
    beide erneut, in derselben Reihenfolge (R2).

    Zwei Nachrichten sind Pflicht: bei nur EINER verhalten sich `break` und
    `continue` im Fehlerzweig identisch, deshalb faengt keiner der bisherigen
    Zwei-Lauf-Tests die Mutation `break` -> `continue`. Mit `continue`
    wanderte der Zeiger ueber BEIDE Nachrichten hinweg, weil die erfolgreiche
    zweite `max_seen` hochzieht -- die Rueckadresse der ersten waere dauerhaft
    verloren, ohne dass irgendwo ein Fehler sichtbar wird (genau der Schaden,
    den Fix F001 verhindert).
    """
    import services.inbound_sms_reader as reader_mod

    _fake_production_origin(monkeypatch, reader_mod)

    fenster = [_garmin_message(9001, GARMIN_FROM_A),
               _garmin_message(9002, GARMIN_FROM_B)]
    fake_get = _FakeJournalEndpoint([fenster, fenster])
    fake_post = _TransientlyFailingLearnRecorder(fail_times=1)
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)

    reader = reader_mod.InboundSmsReader()

    result_1 = reader.poll_and_process(_settings())
    assert result_1 == 0, (
        f"Lauf 1: nach dem Fehlschlag der ersten Nachricht darf KEINE weitere "
        f"Nachricht desselben Fensters gelernt werden, gemeldet wurden "
        f"{result_1!r}"
    )
    assert [c["json"]["from"] for c in fake_post.calls] == [GARMIN_FROM_A], (
        f"Lauf 1: der Poll muss NACH dem Fehlschlag abbrechen -- die zweite "
        f"Nachricht darf gar nicht erst gemeldet werden, gemeldet wurden "
        f"{[c['json']['from'] for c in fake_post.calls]!r}"
    )
    assert reader.last_failed_count == 1, (
        f"Lauf 1: genau ein voruebergehender Fehlschlag, gezaehlt wurden "
        f"{reader.last_failed_count!r}"
    )

    result_2 = reader.poll_and_process(_settings())
    assert [c["json"]["from"] for c in fake_post.calls[1:]] == [
        GARMIN_FROM_A, GARMIN_FROM_B,
    ], (
        f"Lauf 2: der Zeiger muss VOR der ersten Nachricht stehen geblieben "
        f"sein -- beide Nachrichten werden erneut versucht, in Reihenfolge "
        f"ihrer id, gemeldet wurden "
        f"{[c['json']['from'] for c in fake_post.calls[1:]]!r}"
    )
    assert result_2 == 2, (
        f"Lauf 2: beide Nachrichten muessen jetzt gelernt werden, gemeldet "
        f"wurden {result_2!r}"
    )
    assert reader.last_failed_count == 0


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


# =============================================================================
# Issue #2154 Scheibe A — Verknuepfungscode (TDD RED)
# Spec: docs/specs/modules/fix_2154_premium_sms_verknuepfungscode.md v1.0
#
# Der Zustaendigkeitsschnitt des Modul-Docstrings gilt weiter: hier steht die
# READER-Haelfte (welcher Aufruf, welcher Payload, welcher Zaehler, welcher
# Befehlstext). Die Aufloesung selbst (Code gegen Hash, Ratebremse, TTL) ist
# Go-Verantwortung und wird in internal/handler/ gegen einen echten Store
# geprueft. Kein Fake hier bildet diese Entscheidung nach.
#
# Issue #2323 (PO-Entscheid 14.09.2026): Code-Format auf festen Praefix `XX`
# (case-insensitive) + 3 Buchstaben (ohne I/L/O) + 3 Ziffern (ohne 0/1)
# umgestellt (vorher: 7 Zeichen aus 31, ohne festen Praefix). LINK_CODE unten
# traegt deshalb das NEUE Format -- Go-Pendant:
# internal/handler/premium_sms_link_code.go::premiumSmsLinkCodeAlphabet.
# =============================================================================

LINK_CODE = "XXabc249"


def _garmin_message_with_text(msg_id: int, sender: str, text: str) -> dict:
    message = _garmin_message(msg_id, sender)
    message["text"] = text
    return message


class _AllPostsRecorder:
    """Zeichnet JEDEN ausgehenden POST auf, nicht nur den Lernaufruf.

    Der Premium-SMS-Versand laeuft ueber dasselbe modulweite ``httpx.post``
    (``src/output/channels/seven_io_base.py:171``). Ein Versand waere also
    zwangslaeufig ein WEITERER Eintrag in ``other_calls`` -- damit ist "es ging
    nichts hinaus" am echten Transport gemessen und nicht am Lernaufruf.

    Der Fake entscheidet nichts: er gibt den vorgegebenen Statuscode des
    Lern-Endpunkts zurueck (dessen Aufloesungslogik ist Go-Verantwortung) und
    antwortet auf jeden anderen POST mit der seven.io-Erfolgsantwort."""

    def __init__(self, learn_status: int, learn_body: dict):
        self._learn_status = learn_status
        self._learn_body = learn_body
        self.learn_calls: list[dict] = []
        self.other_calls: list[dict] = []

    def __call__(self, url, json=None, data=None, timeout=None, **kwargs):  # noqa: A002
        if str(url).endswith(LEARN_ENDPOINT_SUFFIX):
            self.learn_calls.append({"url": url, "json": json})
            return httpx.Response(self._learn_status, json=self._learn_body)
        self.other_calls.append({"url": url, "data": data})
        return httpx.Response(200, text="100")


class _SuppressedCommandResult:
    """Antwort gilt als bereits verschickt -- unterdrueckt den zweiten
    Versandpfad in ``_verarbeite_befehl`` (AC-10 aus #2184)."""

    suppress_email_reply = True
    confirmation_subject = ""
    confirmation_body = ""


class _CommandProcessorRecorder:
    """Faengt die an ``TripCommandProcessor`` uebergebene ``InboundMessage`` ab.

    Bildet die Befehlsverarbeitung NICHT nach -- er merkt sich nur, was ihm
    uebergeben wurde. Die geprueften Werte entstehen vollstaendig im
    Produktivcode."""

    def __init__(self):
        self.messages: list = []

    def __call__(self):
        return self

    def process(self, message):
        self.messages.append(message)
        return _SuppressedCommandResult()


# =============================================================================
# AC-9 (ERHALTUNGS-WAECHTER, heute GRUEN): eine abgelehnte Verknuepfung loest
# keine ausgehende Premium-SMS aus. Keine RED-Evidenz -- der Test belegt, dass
# der Fix diese Eigenschaft nicht bricht, obwohl ab dem Fix deutlich mehr
# Nachrichten abgelehnt werden als bisher.
# =============================================================================

def test_unknown_sender_without_code_receives_no_outbound_reply(monkeypatch):
    """AC-9: Given eine unbekannte Nummer schickt eine Garmin-Nachricht ohne
    gueltigen Code / When der Lernaufruf sie mit 409 ablehnt / Then verlaesst
    KEINE Premium-SMS das System -- gemessen am ausgehenden Transport
    (jeder httpx.post), nicht am Lernaufruf."""
    import services.inbound_sms_reader as reader_mod

    _fake_production_origin(monkeypatch, reader_mod)

    fake_get = _FakeJournalEndpoint([[_garmin_message(11001, PRIVATE_FROM)]])
    fake_post = _AllPostsRecorder(409, {"status": "skipped", "reason": "no_valid_code"})
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)

    reader = reader_mod.InboundSmsReader()
    result = reader.poll_and_process(_settings())

    assert result == 0
    # Anti-Leerlauf: ohne diesen Nachweis waere "nichts ging hinaus" auch dann
    # erfuellt, wenn der Poll ueberhaupt nichts getan haette.
    assert len(fake_post.learn_calls) == 1, (
        f"der Lernaufruf muss stattgefunden haben, gesehen: {fake_post.learn_calls!r}"
    )
    assert fake_post.other_calls == [], (
        f"AC-9: nach einer Ablehnung darf KEIN weiterer ausgehender Aufruf "
        f"erfolgen (der Premium-SMS-Versand laeuft ueber dasselbe httpx.post), "
        f"gesehen: {fake_post.other_calls!r}"
    )


# =============================================================================
# AC-12 (heute ROT): der Code darf nicht als erstes Wort im ausgefuehrten
# Befehl landen. Heute schneidet inbound_sms_reader.py:254 nur am Kennzeichen
# ab -- der Code bleibt stehen und wird zum Befehlsanfang.
# =============================================================================

def test_link_code_is_stripped_before_command_processing(monkeypatch):
    """AC-12: Given eine Verknuepfungsnachricht traegt Code UND Befehl /
    When sie verarbeitet wird / Then enthaelt der an TripCommandProcessor
    uebergebene Befehlstext den Code NICHT."""
    import services.inbound_sms_reader as reader_mod

    _fake_production_origin(monkeypatch, reader_mod)
    _trip_mit_aktiver_etappe("premium-user")

    text = f"{LINK_CODE} heute inreachlink.com/g-0Ab1Cd2Ef... (51.9956, 7.7136)"
    fake_get = _FakeJournalEndpoint([[_garmin_message_with_text(11002, GARMIN_FROM_A, text)]])
    fake_post = _LearnCallRecorder()
    recorder = _CommandProcessorRecorder()
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(reader_mod, "TripCommandProcessor", recorder)

    reader = reader_mod.InboundSmsReader()
    reader.poll_and_process(_settings())

    assert len(recorder.messages) == 1, (
        f"erwartet genau eine Befehlsverarbeitung, gesehen: {recorder.messages!r}"
    )
    befehl = recorder.messages[0].body
    assert LINK_CODE not in befehl, (
        f"AC-12: der Verknuepfungs-Code darf nicht Teil des Befehls sein, "
        f"uebergeben wurde {befehl!r}"
    )
    assert befehl == "heute", (
        f"AC-12: erwartet den Befehl ohne Code ('heute'), uebergeben wurde {befehl!r}"
    )


# =============================================================================
# Payload-Vertrag (heute ROT): der Code aus dem Text wird im Lernaufruf
# mitgeschickt -- und NUR dann, wenn im Text auch einer steht. Heute baut
# inbound_sms_reader.py:171 unbedingt {"from": sender}.
# =============================================================================

def test_link_code_from_text_is_sent_in_learn_payload(monkeypatch):
    """Given eine Garmin-Nachricht mit vorangestelltem Code und eine ohne /
    When der Poll laeuft / Then traegt der erste Lernaufruf `code`, der
    zweite hat KEINEN `code`-Schluessel (ein leerer Wert waere kein
    'fehlender Code' und kippte den Entscheidungsbaum im Go-Endpunkt)."""
    import services.inbound_sms_reader as reader_mod

    _fake_production_origin(monkeypatch, reader_mod)

    with_code = _garmin_message_with_text(
        11003, GARMIN_FROM_A,
        f"{LINK_CODE} inreachlink.com/g-0Ab1Cd2Ef... (51.9956, 7.7136)",
    )
    without_code = _garmin_message(11004, GARMIN_FROM_B)
    fake_get = _FakeJournalEndpoint([[with_code, without_code]])
    fake_post = _LearnCallRecorder()
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(reader_mod, "TripCommandProcessor", _CommandProcessorRecorder())

    reader = reader_mod.InboundSmsReader()
    reader.poll_and_process(_settings())

    assert len(fake_post.calls) == 2, f"erwartet 2 Lernaufrufe, gesehen: {fake_post.calls!r}"
    erster, zweiter = fake_post.calls[0]["json"], fake_post.calls[1]["json"]
    assert erster.get("code") == LINK_CODE.upper(), (
        f"der Code aus dem Text muss im Payload stehen (normalisiert "
        f"grossgeschrieben, Issue #2323 F001), gesehen: {erster!r}"
    )
    assert erster["from"] == GARMIN_FROM_A
    assert "code" not in zweiter, (
        f"ohne Code im Text darf KEIN code-Schluessel mitgeschickt werden, gesehen: {zweiter!r}"
    )


# =============================================================================
# Kollision Code-Gestalt vs. Steuerbefehl (Befund waehrend der Umsetzung):
# RUHETAG und STRECKE sind sieben Zeichen aus genau dem Code-Alphabet. Die
# Hilfe nennt alle Befehle in GROSSBUCHSTABEN -- ohne Ausnahme fuer bekannte
# Befehle frisst die Code-Abtrennung sie auf, und der Wanderer bekommt auf
# "RUHETAG" nichts. Gemessen an BEIDEN Wirkstellen: Payload und Befehlstext.
#
# Issue #2323: bleibt als Erhaltungswaechter GRUEN -- unter dem neuen
# XX-Praefix-Format treffen RUHETAG/STRECKE die Code-Gestalt ohnehin nicht
# mehr, die `bare_keywords()`-Sonderregel wird also nur noch ungenutzt (AC-6
# entscheidet unten unabhaengig vom internen Weg).
# =============================================================================

def test_uppercase_bare_keyword_is_not_mistaken_for_a_link_code(monkeypatch):
    """Given eine Garmin-Nachricht, deren Befehl ein siebenstelliger
    Grossbuchstaben-Befehl ist (RUHETAG/STRECKE) / When der Poll laeuft /
    Then wird KEIN `code` mitgeschickt und der Befehl erreicht den
    TripCommandProcessor vollstaendig."""
    import services.inbound_sms_reader as reader_mod

    _fake_production_origin(monkeypatch, reader_mod)
    _trip_mit_aktiver_etappe("premium-user")

    journal = [
        _garmin_message_with_text(
            11006, GARMIN_FROM_A, "RUHETAG inreachlink.com/g-0Ab1Cd2Ef... (51.9956, 7.7136)",
        ),
        _garmin_message_with_text(
            11007, GARMIN_FROM_B, "STRECKE 12 inreachlink.com/g-0Ab1Cd2Ef... (51.9956, 7.7136)",
        ),
    ]
    fake_get = _FakeJournalEndpoint([journal])
    fake_post = _LearnCallRecorder()
    recorder = _CommandProcessorRecorder()
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(reader_mod, "TripCommandProcessor", recorder)

    reader = reader_mod.InboundSmsReader()
    reader.poll_and_process(_settings())

    assert len(fake_post.calls) == 2, f"erwartet 2 Lernaufrufe, gesehen: {fake_post.calls!r}"
    for aufruf in fake_post.calls:
        assert "code" not in aufruf["json"], (
            f"ein bekannter Steuerbefehl ist KEIN Verknuepfungs-Code, gesehen: {aufruf['json']!r}"
        )

    befehle = [m.body for m in recorder.messages]
    assert befehle == ["RUHETAG", "STRECKE 12"], (
        f"der Befehl darf nicht als Code abgeschnitten werden, uebergeben wurde {befehle!r}"
    )


# =============================================================================
# Issue #2323 AC-6: RUHETAG/STRECKE muessen unabhaengig davon korrekt
# ankommen, ob ihnen ein echter Verknuepfungs-Code vorangestellt ist. Der
# Fall OHNE Code ist bereits durch obigen Test abgedeckt (bleibt gruen); der
# Fall MIT vorangestelltem Code ist neu -- heute ROT, weil `_LINK_CODE_PATTERN`
# das neue Format (noch) nicht erkennt und der Code deshalb Teil des
# uebergebenen Befehlstexts bleibt.
# =============================================================================

def test_ruhetag_survives_with_and_without_leading_link_code(monkeypatch):
    """AC-6: Given eine Nachricht traegt ausschliesslich RUHETAG ODER einen
    gueltigen Verknuepfungs-Code gefolgt von RUHETAG / When der Poll laeuft /
    Then ist der an TripCommandProcessor uebergebene Befehlstext in BEIDEN
    Faellen exakt "RUHETAG"."""
    import services.inbound_sms_reader as reader_mod

    _fake_production_origin(monkeypatch, reader_mod)
    _trip_mit_aktiver_etappe("premium-user")

    journal = [
        _garmin_message_with_text(
            11008, GARMIN_FROM_A, "RUHETAG inreachlink.com/g-0Ab1Cd2Ef... (51.9956, 7.7136)",
        ),
        _garmin_message_with_text(
            11009, GARMIN_FROM_B,
            f"{LINK_CODE} RUHETAG inreachlink.com/g-0Ab1Cd2Ef... (51.9956, 7.7136)",
        ),
    ]
    fake_get = _FakeJournalEndpoint([journal])
    fake_post = _LearnCallRecorder()
    recorder = _CommandProcessorRecorder()
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(reader_mod, "TripCommandProcessor", recorder)

    reader = reader_mod.InboundSmsReader()
    reader.poll_and_process(_settings())

    befehle = [m.body for m in recorder.messages]
    assert befehle == ["RUHETAG", "RUHETAG"], (
        f"AC-6: RUHETAG muss in beiden Faellen (mit und ohne vorangestellten "
        f"Code) unverfaelscht ankommen, uebergeben wurde {befehle!r}"
    )
    assert fake_post.calls[1]["json"].get("code") == LINK_CODE.upper(), (
        f"AC-6: der vorangestellte Code muss trotzdem im Payload landen "
        f"(normalisiert grossgeschrieben, Issue #2323 F001), "
        f"gesehen: {fake_post.calls[1]['json']!r}"
    )


# =============================================================================
# Issue #2323 AC-5: `_LINK_CODE_PATTERN` muss ausschliesslich das neue Format
# akzeptieren (XX-Praefix + 3 Buchstaben ohne I/L/O + 3 Ziffern ohne 0/1),
# unabhaengig von Gross-/Kleinschreibung. Heute ROT: die alte Regel
# (7 Zeichen aus 31, kein Praefix, nur Grossbuchstaben) erkennt keinen der
# Akzeptanz-Faelle und lehnt die Ablehnungs-Faelle aus dem falschen Grund ab.
# =============================================================================

def test_link_code_pattern_matches_new_format_table(monkeypatch):
    """AC-5: Given eine Tabelle literaler Werte / When sie gegen
    `_LINK_CODE_PATTERN` geprueft werden / Then akzeptiert das Muster
    ausschliesslich gueltige XX+3+3-Codes in beiden Schreibweisen und lehnt
    Formatverstoesse ab."""
    import services.inbound_sms_reader as reader_mod

    faelle = [
        ("XXabc249", True, "gueltig, wie im Beispiel der Spec"),
        ("xxABC249", True, "gueltig, gemischte Schreibweise (case-insensitive)"),
        ("XXabc0249", False, "zu lang (9 statt 8 Zeichen)"),
        ("XXab249", False, "zu kurz (7 statt 8 Zeichen)"),
        ("XXilo249", False, "verbotene Buchstaben I/L/O"),
        ("XXabc019", False, "verbotene Ziffern 0/1"),
    ]
    for code, erwartet_gueltig, grund in faelle:
        treffer = reader_mod._LINK_CODE_PATTERN.match(code) is not None
        assert treffer == erwartet_gueltig, (
            f"AC-5: {code!r} ({grund}) -- erwartet gueltig={erwartet_gueltig}, "
            f"Muster lieferte gueltig={treffer}"
        )


# =============================================================================
# AC-11 (heute ROT): abgelehnte Lernversuche brauchen einen eigenen, von
# Netz-/5xx-Fehlern unterscheidbaren Zaehler. Heute zaehlt der 4xx-Zweig
# (inbound_sms_reader.py:210-218) gar nichts und meldet still "ok" -- ein
# dauerhaft ausgesperrter Nutzer bleibt unsichtbar.
# =============================================================================

def test_rejected_learn_is_counted_separately_from_failures(monkeypatch):
    """AC-11 (Reader-Haelfte): Given ein Lernaufruf wird mit 409 abgelehnt /
    When der Poll durchlaeuft / Then zaehlt der Reader die Ablehnung in einem
    EIGENEN Zaehler, nicht in `last_failed_count`."""
    import services.inbound_sms_reader as reader_mod

    _fake_production_origin(monkeypatch, reader_mod)

    fake_get = _FakeJournalEndpoint([[_garmin_message(11005, GARMIN_FROM_A)]])
    fake_post = _RejectingLearnRecorder()
    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)

    reader = reader_mod.InboundSmsReader()
    reader.poll_and_process(_settings())

    assert reader.last_failed_count == 0, (
        "eine bewusste Ablehnung ist KEIN voruebergehender Fehlschlag (Fix F001)"
    )
    assert getattr(reader, "last_rejected_count", None) == 1, (
        "AC-11: die Ablehnung braucht einen eigenen Zaehler `last_rejected_count`, "
        f"gesehen: {getattr(reader, 'last_rejected_count', '<Attribut fehlt>')!r}"
    )


def test_router_reports_partial_when_learn_was_rejected(monkeypatch):
    """AC-11 (Antwortkoerper-Haelfte): Given der Reader meldet eine Ablehnung
    ohne jeden Netzfehler / When der Trigger-Endpunkt aufgerufen wird / Then
    meldet er `status: "partial"` (genau diesen Wert macht
    internal/scheduler/scheduler.go::triggerPremiumSmsPollEndpoint zu einem
    sichtbaren partialRunError) und weist die Ablehnung getrennt von `failed`
    aus."""
    import api.routers.scheduler as scheduler_router
    import services.inbound_sms_reader as reader_mod

    class _FakeReaderWithRejection:
        def __init__(self):
            self.last_failed_count = 0
            self.last_rejected_count = 0

        def poll_and_process(self, settings):
            self.last_rejected_count = 1
            return 0

    monkeypatch.setattr(reader_mod, "InboundSmsReader", _FakeReaderWithRejection)

    response = scheduler_router.trigger_inbound_sms()

    assert response["status"] == "partial", (
        f"AC-11: eine Ablehnung darf nicht als 'ok' durchgehen und muss den vom "
        f"Go-Zeitplaner ausgewerteten Wert 'partial' tragen, bekam {response!r}"
    )
    assert response.get("rejected") == 1, (
        f"AC-11: die Ablehnung muss eigenstaendig sichtbar sein, bekam {response!r}"
    )
    assert response.get("failed") == 0, (
        f"AC-11: eine Ablehnung ist KEIN Netz-/5xx-Fehler und darf `failed` nicht "
        f"erhoehen, bekam {response!r}"
    )
