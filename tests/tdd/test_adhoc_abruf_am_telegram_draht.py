"""Issue #2134 — Fix-Loop 1: der Ad-hoc-Abruf am TELEGRAM-DRAHT.

Warum diese Datei existiert: AC-5 (Zitat-Praefix) und AC-6 (Slash-Praefix)
waren ausschliesslich gegen ``TripCommandProcessor._parse_command`` geprueft,
also gegen die interne Funktion. Telegram laeuft aber nie ueber diese
Funktion allein — ``InboundTelegramReader`` hat eine EIGENE
``_parse_command`` und weist ab, bevor der Prozessor ueberhaupt gefragt wird
(``inbound_telegram_reader.py``, Zweig "Unbekannter Befehl"). Auf genau dem
Kanal, auf dem #2120 gemeldet wurde, war ``/strecke 5`` damit unbehoben.

Alle Tests hier nehmen deshalb den Reader-Einstieg ``_command_body()`` —
dieselbe Kodierung, die ``_process_update`` produktiv an den Prozessor
uebergibt.

Mock-frei: echte ``InboundTelegramReader``/``TripCommandProcessor``-Objekte,
echter Trip und echter Stunden-Snapshot unter isolierter Datenwurzel.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from app.metric_catalog import get_metric
from services.inbound_telegram_reader import InboundTelegramReader
from services.trip_command_processor import (
    InboundMessage,
    TripCommandProcessor,
    _QUERY_KEYS,
)
from tests.helpers.adhoc_metrik_fixtures import (
    TRIP_TZ,
    ist_unbekannt,
    lege_trip_an,
    standard_felder,
)
from tests.helpers.verlauf_abdeckung import abgedeckte_stunden


# ---------------------------------------------------------------------------
# Draht-Bausteine
# ---------------------------------------------------------------------------

def _reader_body(text: str) -> tuple[str | None, str | None]:
    """Was der Reader aus einem getippten Telegram-Text macht.

    ``(None, None)`` heisst: der Reader hat abgewiesen, der Prozessor sieht
    die Nachricht nie — der Nutzer bekommt "Unbekannter Befehl".
    """
    return InboundTelegramReader()._command_body(text)


def _ueber_den_draht(fix, text: str, channel: str = "telegram"):
    """Getippter Text -> Reader -> Prozessor. ``None``, wenn der Reader abwies."""
    key, body = _reader_body(text)
    if key is None:
        return None
    return TripCommandProcessor().process(
        InboundMessage(
            trip_name=fix.trip_name,
            body=body,
            sender="4711",
            channel=channel,
            received_at=fix.now,
            user_id=fix.user_id,
        )
    )


def _felder_mit_katalog_groessen(i: int) -> dict:
    """Stundenpunkt mit den Feldern, die F001/F002 abfragen.

    ``standard_felder`` fuehrt nur Temperatur/Wind/Regen/Gewitter; Sicht,
    Feuchte und Nullgradgrenze muessen eigens belegt werden, sonst antwortet
    der Prozessor korrekt mit "nicht verfuegbar" und der Test bewiese nur die
    Luecken-Meldung statt der Zustellung von Werten.
    """
    punkt = standard_felder(i)
    punkt.update(
        visibility_m=float(8000 + i * 250),
        humidity_pct=float(55 + i),
        freezing_level_m=float(2400 + i * 25),
    )
    return punkt


@pytest.fixture
def fix():
    # Bewusst funktionsweit: die Datenwurzel ist je Test isoliert, ein
    # modulweit angelegter Trip waere ab dem zweiten Test unauffindbar.
    return lege_trip_an("draht", _felder_mit_katalog_groessen)


def _erwartete_stunden(fix) -> list[str]:
    """Die zwoelf Ortszeit-Stunden des Antwortfensters ("heute" = 12 h).

    Issue #2185: der Verlauf fasst gleiche Folgestunden zu Zeitbereichen
    zusammen — eine konstante Groesse kann kuenftig in EINER Zeile stehen.
    Die alte Schwelle ">= 3 Stundenzeilen" wuerde daran scheitern, ohne dass
    etwas fehlt. Ersatz ist die ABDECKUNGS-Zusicherung (Spec
    ``feat_2185_verlauf_wechselpunkte.md`` AC-7): geprueft wird, WELCHE
    Stunden die Antwort abdeckt — das ist staerker als jede Zeilenzahl, weil
    es auch einen verschluckten oder doppelt gezaehlten Zeitpunkt faengt.
    """
    return [
        (fix.now + timedelta(hours=i)).astimezone(TRIP_TZ).strftime("%H:%M")
        for i in range(12)
    ]


# ---------------------------------------------------------------------------
# AC-6 am Draht: fuehrender Slash (#2120)
# ---------------------------------------------------------------------------

def test_ac6_slash_strecke_mit_km_erreicht_den_prozessor(fix):
    """AC-6 GIVEN die Telegram-Nachricht '/strecke 5' WHEN sie durch den
    Reader-Einstieg laeuft THEN wird sie als Strecken-Befehl mit dem Argument
    '5' an den Prozessor uebergeben — NICHT als unbekannter Befehl abgewiesen.

    Das ist der gemeldete Fall aus #2120: der Slash zusammen mit einem
    Argument. ``/strecke`` allein traf die Shortcut-Tabelle, ``/strecke 5``
    nicht mehr.
    """
    key, body = _reader_body("/strecke 5")

    assert key is not None, (
        "AC-6: '/strecke 5' wird vom Telegram-Reader abgewiesen und erreicht "
        "den Prozessor nie — der Nutzer bekommt 'Unbekannter Befehl'."
    )
    assert key == "strecke", (
        f"AC-6: '/strecke 5' muss den Schluessel 'strecke' tragen, erhalten {key!r}"
    )
    # Wert statt Form: die 5 muss den Prozessor auch WIRKLICH erreichen, nicht
    # bloss irgendwo im Body stehen. Geprueft wird deshalb, was der Prozessor
    # aus dem Reader-Body als Argument herausloest.
    assert TripCommandProcessor()._parse_command(body) == ("strecke", "5"), (
        f"AC-6: der Reader-Body {body!r} muss beim Prozessor als "
        f"('strecke', '5') ankommen, erhalten "
        f"{TripCommandProcessor()._parse_command(body)!r}"
    )

    result = _ueber_den_draht(fix, "/strecke 5")
    assert result is not None and result.command == "strecke", (
        f"AC-6: '/strecke 5' muss den Strecken-Handler erreichen, erhalten "
        f"{None if result is None else result.command!r}"
    )
    assert not ist_unbekannt(result), (
        f"AC-6: '/strecke 5' darf nicht als unbekannter Befehl enden — "
        f"subject={result.confirmation_subject!r}"
    )


def test_ac6_slash_strecke_ohne_argument_bleibt_argumentlos(fix):
    """AC-6 (Gegenprobe): '/strecke' ohne Zahl darf sich kein Argument
    ausdenken — sonst waere die Argument-Weitergabe oben auch dann wahr, wenn
    der Reader pauschal den Rest der Zeile anhaengt."""
    assert _reader_body("/strecke") == ("strecke", "### strecke"), (
        f"AC-6: '/strecke' muss argumentlos bleiben, erhalten "
        f"{_reader_body('/strecke')!r}"
    )


@pytest.mark.parametrize(
    "text,erwartet",
    [("/heute", "heute"), ("/morgen", "morgen")],
)
def test_ac6_slash_heute_und_morgen_erreichen_den_prozessor(text, erwartet):
    """AC-6 GIVEN '/heute' bzw. '/morgen' — die der Produktivtext
    ``_BRIEFING_HINWEIS`` woertlich empfiehlt — WHEN sie durch den
    Reader-Einstieg laufen THEN kodiert der Reader sie als Abfrage-Schluessel,
    den der Prozessor als solchen wiedererkennt.

    Bewusst OHNE ``process()``: 'heute'/'morgen' loesen produktiv ein volles
    Briefing samt Versand aus (``_trigger_on_demand``). Geprueft wird deshalb
    die Weiche bis zum Dispatch, nicht der Versand.
    """
    key, body = _reader_body(text)

    assert key == erwartet, (
        f"AC-6: {text!r} muss den Schluessel {erwartet!r} tragen, erhalten {key!r}"
    )
    aufgeloest = TripCommandProcessor()._parse_command(body)
    assert aufgeloest == ("query", erwartet), (
        f"AC-6: der Reader-Body {body!r} muss beim Prozessor als "
        f"('query', {erwartet!r}) ankommen, erhalten {aufgeloest!r}"
    )
    assert erwartet in _QUERY_KEYS, (
        f"AC-6: {erwartet!r} muss ein Abfrage-Schluessel sein, sonst laeuft "
        f"{text!r} am Query-Dispatch vorbei"
    )


# ---------------------------------------------------------------------------
# AC-5 am Draht: Zitat-Praefix (#2137)
# ---------------------------------------------------------------------------

def test_ac5_zitiertes_heute_wird_am_draht_erkannt():
    """AC-5 GIVEN die Antwort auf ein Briefing, die der Client als '> Heute'
    zitiert WHEN sie durch den Reader-Einstieg laeuft THEN wird 'heute'
    erkannt und als Abfrage kodiert — nicht abgewiesen."""
    key, body = _reader_body("> Heute")

    assert key is not None, (
        "AC-5: '> Heute' wird vom Telegram-Reader abgewiesen — eine Antwort "
        "aus dem Client heraus erreicht den Prozessor nie."
    )
    assert (key, body) == ("heute", "### query: heute"), (
        f"AC-5: '> Heute' muss als ('heute', '### query: heute') kodiert "
        f"werden, erhalten {(key, body)!r}"
    )


def test_ac5_zitiertes_slash_strecke_traegt_das_argument():
    """AC-5 + AC-6 kombiniert GIVEN '> /strecke 5' — Zitat UND Slash, der
    realistische Fall beim Antworten auf ein Briefing mit Befehlsliste — WHEN
    es durch den Reader-Einstieg laeuft THEN kommt ('strecke', '5') an."""
    key, body = _reader_body("> /strecke 5")

    assert key == "strecke", (
        f"AC-5/AC-6: '> /strecke 5' muss 'strecke' liefern, erhalten {key!r}"
    )
    assert TripCommandProcessor()._parse_command(body) == ("strecke", "5"), (
        f"AC-5/AC-6: das Argument '5' muss das Zitat-Praefix ueberleben, "
        f"Body {body!r} loest zu "
        f"{TripCommandProcessor()._parse_command(body)!r} auf"
    )


def test_ac5_praefix_windet_keinen_unsinn_durch():
    """AC-5 Positivkontrolle: hinter Zitat und Slash wird NICHTS
    durchgewunken. Ohne diesen Test waere die Praefix-Toleranz auch dann
    'erfuellt', wenn der Reader pauschal alles akzeptierte."""
    assert _reader_body("> /quatsch") == (None, None), (
        f"AC-5: '> /quatsch' ist kein Befehl und muss abgewiesen werden, "
        f"erhalten {_reader_body('> /quatsch')!r}"
    )


# ---------------------------------------------------------------------------
# F001 (Adversary, HIGH): getipptes Katalog-Kuerzel am Draht
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "wort,metric_id",
    [("Visib", "visibility"), ("Humid", "humidity"), ("Thdr", "thunder")],
)
def test_f001_getipptes_katalogkuerzel_liefert_stundenwerte(fix, wort, metric_id):
    """F001 GIVEN ein getipptes Katalog-Kuerzel ('Visib', 'Humid', 'Thdr')
    als Telegram-Nachricht WHEN es durch den Reader-Einstieg laeuft THEN
    reicht der Reader es durch, der Prozessor loest es gegen den Katalog auf
    und antwortet mit stuendlichen Werten.

    Diese Strecke — Durchreich-Zweig im Reader UND Katalog-Aufloesung des
    ``### <wort>``-Bodys im Prozessor — hatte null Abdeckung: beide Zweige
    liessen sich entfernen, ohne dass ein Test rot wurde.
    """
    result = _ueber_den_draht(fix, wort)

    assert result is not None, (
        f"F001: {wort!r} wird vom Telegram-Reader abgewiesen und erreicht den "
        f"Prozessor nie."
    )
    assert not ist_unbekannt(result), (
        f"F001: {wort!r} darf nicht als unbekannter Befehl enden — "
        f"subject={result.confirmation_subject!r}, "
        f"body={result.confirmation_body!r}"
    )
    assert result.success, (
        f"F001: {wort!r} muss Werte liefern, erhalten "
        f"subject={result.confirmation_subject!r}, "
        f"body={result.confirmation_body!r}"
    )
    # Abdeckung statt Zeilenzahl (Issue #2185, s. `_erwartete_stunden`).
    assert abgedeckte_stunden(result.confirmation_body) == _erwartete_stunden(fix), (
        f"F001: {wort!r} muss den Verlauf des ganzen Antwortfensters liefern, "
        f"abgedeckt: {abgedeckte_stunden(result.confirmation_body)}\n"
        f"{result.confirmation_body}"
    )
    # Wert statt Form: die Antwort muss die ANGEFRAGTE Groesse tragen, nicht
    # irgendeine. Ohne diese Zusicherung waere jede beliebige Stundentabelle
    # (z.B. immer Temperatur) ausreichend.
    assert result.command == f"metrik_{metric_id}", (
        f"F001: {wort!r} muss die Groesse {metric_id!r} abrufen, erhalten "
        f"{result.command!r}"
    )
    label = get_metric(metric_id).label_de
    assert label.lower() in (
        f"{result.confirmation_subject} {result.confirmation_body}".lower()
    ), (
        f"F001: die Antwort auf {wort!r} muss {label!r} benennen — "
        f"subject={result.confirmation_subject!r}"
    )


# ---------------------------------------------------------------------------
# F002 (Adversary, MEDIUM): die sms_code-Zweitschreibweise
# ---------------------------------------------------------------------------

def test_f002_sms_code_zweitschreibweise_fz_liefert_nullgradgrenze(fix):
    """F002 GIVEN das getippte Kuerzel 'FZ' WHEN es durch den Reader-Einstieg
    laeuft THEN antwortet der Prozessor mit dem Stundenverlauf der
    Nullgradgrenze.

    Die Spec begruendet die Zweitschreibweise ausdruecklich damit, dass die
    Tabellenueberschrift '0°Line' auf einer Handy-Tastatur kaum tippbar ist.
    Ohne diesen Test laesst sich der gesamte ``sms_code``-Durchlauf aus
    ``metric_command_words()`` entfernen, ohne dass etwas rot wird.
    """
    result = _ueber_den_draht(fix, "FZ")

    assert result is not None, (
        "F002: 'FZ' wird vom Telegram-Reader abgewiesen und erreicht den "
        "Prozessor nie."
    )
    assert result.command == "metrik_freezing_level", (
        f"F002: 'FZ' muss die Nullgradgrenze abrufen, erhalten "
        f"{result.command!r} (subject={result.confirmation_subject!r})"
    )
    assert result.success, (
        f"F002: 'FZ' muss Werte liefern, erhalten "
        f"body={result.confirmation_body!r}"
    )
    # Abdeckung statt Zeilenzahl (Issue #2185, s. `_erwartete_stunden`).
    assert abgedeckte_stunden(result.confirmation_body) == _erwartete_stunden(fix), (
        f"F002: 'FZ' muss den Verlauf des ganzen Antwortfensters liefern, "
        f"abgedeckt: {abgedeckte_stunden(result.confirmation_body)}\n"
        f"{result.confirmation_body}"
    )


def test_f002_die_ueberschrift_bleibt_der_erste_weg(fix):
    """F002 Gegenprobe: die Zweitschreibweise tritt NEBEN die Ueberschrift,
    sie ersetzt sie nicht — '0Line' (die Ueberschrift ohne Gradzeichen) muss
    dieselbe Groesse treffen wie 'FZ'."""
    ueber_kuerzel = _ueber_den_draht(fix, "FZ")
    ueber_ueberschrift = _ueber_den_draht(fix, "0Line")

    assert ueber_ueberschrift is not None, (
        "F002: '0Line' wird vom Telegram-Reader abgewiesen."
    )
    assert ueber_ueberschrift.command == ueber_kuerzel.command, (
        f"F002: Ueberschrift und Kuerzel muessen dieselbe Groesse treffen, "
        f"erhalten {ueber_ueberschrift.command!r} vs. {ueber_kuerzel.command!r}"
    )


# ---------------------------------------------------------------------------
# Regressions-Waechter: die Shortcut-Tabelle des Readers
# ---------------------------------------------------------------------------

#: Die vollstaendige Invarianten-Tafel des Reader-Parsers. Sie ist die
#: Positivkontrolle dafuer, dass das Praefix-Streifen die Slash-Shortcuts
#: nicht auffrisst: '/status' ist der Glance-Alias, nacktes 'status' die
#: Etappenliste — wuerde der Slash vor der Shortcut-Aufloesung fallen, faenden
#: beide auf dieselbe Antwort zusammen und die Unterscheidung waere still weg.
_TAFEL: tuple[tuple[str, tuple[str | None, str | None]], ...] = (
    # Slash-Shortcuts behalten ihre Sonderbedeutung
    ("/th", ("timeline_heute", None)),
    ("/tm", ("timeline_morgen", None)),
    ("/s", ("glance", None)),
    ("/status", ("glance", None)),
    ("/h", ("heute", None)),
    ("/m", ("morgen", None)),
    ("/hg", ("heute_gewitter", None)),
    # ... und das nackte Wort behaelt seine andere Bedeutung
    ("status", ("status", None)),
    # Slash + Argument (#2120)
    ("/strecke 5", ("strecke", "5")),
    ("/strecke", ("strecke", None)),
    ("strecke 5", ("strecke", "5")),
    # Zitat-Praefix (#2137)
    ("> Heute", ("heute", None)),
    ("> /strecke 5", ("strecke", "5")),
    # Katalog-Kuerzel werden durchgereicht (#2134)
    ("TH", ("th", None)),
    ("th", ("th", None)),
    ("Visib", ("visib", None)),
    ("FZ", ("fz", None)),
    # ... und Unsinn bleibt Unsinn
    ("quatsch", (None, None)),
)


@pytest.mark.parametrize("text,erwartet", _TAFEL, ids=[t for t, _ in _TAFEL])
def test_reader_shortcut_tafel(text, erwartet):
    """Regressions-Waechter GIVEN jede Zeile der Invarianten-Tafel WHEN sie
    durch ``InboundTelegramReader._parse_command`` laeuft THEN kommt genau das
    erwartete Paar heraus."""
    erhalten = InboundTelegramReader()._parse_command(text)
    assert erhalten == erwartet, (
        f"Reader-Tafel: {text!r} muss {erwartet!r} liefern, erhalten "
        f"{erhalten!r}"
    )


# ---------------------------------------------------------------------------
# F004 (Adversary, HIGH): die Kreuzung Zitat-Praefix + Slash-Shortcut
# ---------------------------------------------------------------------------

#: Zitat UND Slash in EINER Zeile. Diese Kreuzung fiel zwischen die
#: bestehenden Waechter: AC-5 prueft das Zitat nur mit nacktem Schlagwort
#: ('> Heute'), AC-6 den Slash nur ohne Zitat ('/strecke 5'). Der einzige
#: Beruehrungspunkt war '> /strecke 5' — und 'strecke' ist ein regulaerer
#: Befehl, der den Slash-Streifen in Schritt 2 unbeschadet uebersteht. Die
#: SHORTCUTS dagegen (/s, /th, /hg ...) leben ausschliesslich von Schritt 1
#: und werden dort nur gefunden, wenn das Zitat VORHER gefallen ist.
#: Praxisfall: die Hilfe empfiehlt die Slash-Schreibweisen, und wer aus dem
#: Client heraus auf ein Briefing antwortet, bekommt vom Telegram-Client ein
#: '>' davorgestellt.
_KREUZUNG: tuple[tuple[str, tuple[str | None, str | None]], ...] = (
    # Zitat + Slash-Shortcut: die Sonderbedeutung muss das Zitat ueberleben.
    # '/status' ist der Glance-Alias — ohne vorheriges Zitat-Streifen wird
    # daraus die ETAPPENLISTE, eine andere Antwort auf dieselbe Frage.
    ("> /status", ("glance", None)),
    (">/status", ("glance", None)),  # Client setzt das '>' ohne Leerzeichen
    ("> /s", ("glance", None)),
    ("> /th", ("timeline_heute", None)),
    ("> /tm", ("timeline_morgen", None)),
    ("> /h", ("heute", None)),
    ("> /m", ("morgen", None)),
    ("> /hg", ("heute_gewitter", None)),
    # Zitat + Shortcut + Argument: beide Stufen greifen hintereinander.
    ("> /status 5", ("glance", "5")),
    # Mehrfach zitiert (Antwort auf eine Antwort), mit und ohne Zwischenraum.
    (">> heute", ("heute", None)),
    ("> > heute", ("heute", None)),
    # Slash mit Zwischenraum bzw. in Grossschreibung — beides tippt sich auf
    # einer Handy-Tastatur mit Autokorrektur von selbst.
    ("/ strecke 5", ("strecke", "5")),
    ("/STRECKE 5", ("strecke", "5")),
    # Katalog-Kuerzel mit Argument (#2134) bleibt Kuerzel mit Argument.
    ("Visib 5", ("visib", "5")),
)


@pytest.mark.parametrize("text,erwartet", _KREUZUNG, ids=[t for t, _ in _KREUZUNG])
def test_f004_zitat_und_slash_gekreuzt(text, erwartet):
    """F004 GIVEN eine Telegram-Zeile, die Zitat-Praefix UND Slash-Kuerzel
    zugleich traegt WHEN sie durch ``InboundTelegramReader._parse_command``
    laeuft THEN kommt genau dasselbe Paar heraus wie ohne Zitat.

    Die Kreuzung war unbewacht: das Zitat-Streifen liess sich vor der
    Shortcut-Aufloesung ersatzlos entfernen, ohne dass einer der 84 Tests rot
    wurde. Produktiv haette der Nutzer dann auf '> /status' die Etappenliste
    statt der Uebersicht bekommen — eine falsche Antwort, keine Fehlermeldung.
    """
    erhalten = InboundTelegramReader()._parse_command(text)
    assert erhalten == erwartet, (
        f"F004: {text!r} muss {erwartet!r} liefern, erhalten {erhalten!r} — "
        f"das Zitat-Praefix darf die Slash-Bedeutung nicht verschieben."
    )


def test_f004_zitat_verschiebt_die_bedeutung_nicht():
    """F004 Positivkontrolle: '/status' und nacktes 'status' bedeuten
    VERSCHIEDENES, und das Zitat aendert daran nichts.

    Ohne diesen Gegensatz waere die Tafel oben auch dann erfuellt, wenn beide
    Schreibweisen auf denselben Schluessel zusammenfielen — genau der stille
    Bedeutungsverlust, den das Zitat-Streifen vor Schritt 1 verhindert.
    """
    reader = InboundTelegramReader()
    zitiert_mit_slash = reader._parse_command("> /status")
    zitiert_ohne_slash = reader._parse_command("> status")

    assert zitiert_mit_slash != zitiert_ohne_slash, (
        f"F004: '> /status' und '> status' duerfen nicht dasselbe bedeuten, "
        f"beide liefern {zitiert_mit_slash!r} — die Unterscheidung "
        f"Uebersicht/Etappenliste ist still weg."
    )
    assert zitiert_ohne_slash == ("status", None), (
        f"F004: zitiertes nacktes 'status' bleibt die Etappenliste, erhalten "
        f"{zitiert_ohne_slash!r}"
    )
    assert zitiert_mit_slash == reader._parse_command("/status"), (
        f"F004: '> /status' muss dasselbe bedeuten wie '/status', erhalten "
        f"{zitiert_mit_slash!r} vs. {reader._parse_command('/status')!r}"
    )


def test_f004_zitiertes_shortcut_erreicht_den_prozessor():
    """F004 GIVEN das zitierte '> /th' WHEN es durch den Reader-EINSTIEG
    ``_command_body`` laeuft — den Weg, den auch ``_process_update`` nimmt —
    THEN wird es als Abfrage kodiert und nicht abgewiesen.

    Die Tafel oben prueft den Parser; dieser Test prueft, dass das Ergebnis
    auch tatsaechlich als Befehl weitergereicht wird statt in 'Unbekannter
    Befehl' zu enden.
    """
    key, body = _reader_body("> /th")

    assert key is not None, (
        "F004: '> /th' wird vom Telegram-Reader abgewiesen — eine zitierte "
        "Antwort mit Slash-Kuerzel erreicht den Prozessor nie."
    )
    assert (key, body) == ("timeline_heute", "### query: timeline_heute"), (
        f"F004: '> /th' muss als ('timeline_heute', "
        f"'### query: timeline_heute') kodiert werden, erhalten "
        f"{(key, body)!r}"
    )


@pytest.mark.parametrize(
    "text,erwartet_key",
    [
        # '/status' ist der Glance-Alias. Faellt die Erst-Token-Pruefung weg,
        # rutscht die Zeile in den Bare-Keyword-Pfad und wird zur ETAPPENLISTE
        # — dieselbe Verwechslung, die die Reihenfolge oben verhindert, nur
        # ausgeloest durch ein angehaengtes Wort statt durch den Slash.
        ("/status heute", "glance"),
        # '/th' und '/hg' haben ueberhaupt kein nacktes Pendant: ohne die
        # Erst-Token-Pruefung landen sie im Katalog ('th' -> Gewitter) bzw.
        # im Nichts.
        ("/th 5", "timeline_heute"),
        ("/hg 5", "heute_gewitter"),
    ],
)
def test_shortcut_behaelt_seine_bedeutung_auch_mit_argument(text, erwartet_key):
    """Regressions-Waechter GIVEN einen Slash-Shortcut MIT angehaengtem Wort
    WHEN er durch den Reader laeuft THEN behaelt er seine Bedeutung.

    Der Schluessel wird geprueft, nicht der Wert: ob ein Abfrage-Shortcut ein
    Argument mitschleppt, ist nirgends zugesichert — dass er nicht die
    Bedeutung wechselt, schon.
    """
    key, _value = InboundTelegramReader()._parse_command(text)
    assert key == erwartet_key, (
        f"Reader: {text!r} muss {erwartet_key!r} bleiben, erhalten {key!r}"
    )
