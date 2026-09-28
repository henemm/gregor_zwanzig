"""TDD RED — Issue #2134 (Epic #2133 S1): EINE Quelle fuer den Befehlssatz.

SPEC: docs/specs/modules/feat_2134_adhoc_abruf_metrik_katalog.md
      AC-9, AC-10, AC-11, AC-12.

RED-Ursache (acht divergierende Listen, keine zwei gleich):
* `_show_help` (trip_command_processor.py:1380-1401) — 12 fest eingetippte
  Zeilen, KEIN Metrikwort.
* Fehlertext A (:396-405) und B (:482-491) — beide nennen nur
  "ruhetag, report, startdatum, abbruch, status, hilfe"; `heute`, `morgen`,
  `jetzt`, `gewitter`, `strecke` werden verschwiegen.
* Klartext-Fussz. (`email/plain.py:364-375`) — ohne STRECKE.
* HTML-Fussz. (`email/html.py:471-519`) — ohne STRECKE und ohne RUHETAG.
* Telegram-Fehlertext (`inbound_telegram_reader.py:206-209`) — eigene achte
  Liste.

Mock-frei: echte Renderer-Aufrufe (`render_plain`,
`_render_kommandos_section`), echter `process()`-Aufruf, echter
`InboundTelegramReader._process_update`. Der Telegram-Versand haengt an einer
ECHTEN `NotificationService`-Unterklasse als Naht (kein `Mock()`/`patch()`) —
geprueft wird der TEXT, den der Reader erzeugt, nicht der Transport.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.config import Settings
from app.loader import get_data_dir
from services.notification_service import NotificationService

from tests.helpers.adhoc_metrik_fixtures import (
    frische_kennung,
    katalog_abrufwoerter,
    lege_trip_an,
    segmente,
    sende,
    specs_ohne,
    standard_felder,
    steuerbefehl_woerter,
    text_woerter,
)

TZ = ZoneInfo("UTC")

# Ein einziger Zeitpunkt fuer die Renderer-Fixtur (AC-11) — die Fussz. ist
# zeitunabhaengig, aber die Segmente brauchen einen Anker.
_JETZT = datetime.now(tz=timezone.utc)

# Die fuenf Woerter, die der heutige Fehlertext ausdruecklich verschweigt
# (AC-10) bzw. die in den Fussz. fehlen (AC-11).
_VERSCHWIEGEN = ("heute", "morgen", "jetzt", "gewitter", "strecke")


# ===========================================================================
# AC-9 — Hilfe ist kanalunabhaengig vollstaendig (PO-Vorgabe 2)
# ===========================================================================

def test_ac9_hilfe_per_email_traegt_dieselbe_wortmenge_wie_per_telegram():
    """AC-9 GIVEN der Metrik-Katalog fuehrt die waehlbaren Groessen WHEN der
    Nutzer `Hilfe` per E-Mail-Antwort sendet THEN erhaelt er dieselbe
    vollstaendige Liste wie per Telegram."""
    fix = lege_trip_an("ac9", mit_snapshot=False)

    per_telegram = sende(fix, "Hilfe", channel="telegram")
    per_email = sende(fix, "Hilfe", channel="email")

    woerter_tg = text_woerter(per_telegram.confirmation_body)
    woerter_mail = text_woerter(per_email.confirmation_body)

    assert woerter_mail == woerter_tg, (
        f"AC-9: die Hilfe unterscheidet sich je Kanal.\n"
        f"nur per Telegram: {sorted(woerter_tg - woerter_mail)!r}\n"
        f"nur per E-Mail:   {sorted(woerter_mail - woerter_tg)!r}"
    )

    erwartet = katalog_abrufwoerter()
    fehlend = {w: mid for w, mid in erwartet.items() if w not in woerter_mail}
    assert not fehlend, (
        f"AC-9: die E-Mail-Hilfe nennt {len(fehlend)} von {len(erwartet)} "
        f"Katalog-Groessen nicht: {fehlend!r}\n"
        f"Text war:\n{per_email.confirmation_body}"
    )


# ===========================================================================
# AC-10 — beide Fehlertexte nennen den vollstaendigen Befehlssatz
# ===========================================================================

def _fehlertext_unbekanntes_wort(fix) -> str:
    """Zweig `key is None` (trip_command_processor.py:396-405)."""
    return sende(fix, "quatschbefehl", channel="telegram").confirmation_body


def _fehlertext_ungueltiger_schluessel(fix) -> str:
    """Zweig `key not in _VALID_COMMANDS` (:482-491)."""
    return sende(fix, "### quatsch: 1", channel="telegram").confirmation_body


@pytest.mark.parametrize(
    "zweig", ["key_is_none", "nicht_in_valid_commands"],
)
def test_ac10_fehlertexte_nennen_den_vollstaendigen_befehlssatz(zweig):
    """AC-10 GIVEN ein Nutzer sendet ein unbekanntes Wort WHEN das System den
    Fehlertext erzeugt THEN nennt er den vollstaendigen Befehlssatz aus
    derselben Quelle wie die Erkennung — insbesondere die heute verschwiegenen
    `heute`, `morgen`, `jetzt`, `gewitter`, `strecke`."""
    fix = lege_trip_an(f"ac10-{zweig}", mit_snapshot=False)
    text = (
        _fehlertext_unbekanntes_wort(fix) if zweig == "key_is_none"
        else _fehlertext_ungueltiger_schluessel(fix)
    )
    gefunden = text_woerter(text)

    fehlend_hart = [w for w in _VERSCHWIEGEN if w not in gefunden]
    assert not fehlend_hart, (
        f"AC-10 ({zweig}): der Fehlertext verschweigt {fehlend_hart!r}.\n"
        f"Text war:\n{text}"
    )

    erwartet = steuerbefehl_woerter()
    fehlend = sorted(w for w in erwartet if w not in gefunden)
    assert not fehlend, (
        f"AC-10 ({zweig}): diese Befehlswoerter aus _COMMAND_SPECS fehlen im "
        f"Fehlertext: {fehlend!r}\nText war:\n{text}"
    )


def test_ac10_gegenprobe_fehlertext_ist_abgeleitet_nicht_danebengeschrieben(
    monkeypatch,
):
    """AC-10 (Mutations-Gegenprobe) GIVEN ein Eintrag wird aus `_COMMAND_SPECS`
    entfernt WHEN der Fehlertext erneut erzeugt wird THEN nennt er dieses Wort
    nicht mehr — der Text stammt aus der Quelle und ist nicht danebengetippt.

    Bleibt das Wort stehen, ist der Fehlertext eine neunte handgepflegte
    Liste und AC-10 waere nur zufaellig erfuellt.
    """
    from services import trip_command_processor as tcp

    fix = lege_trip_an("ac10m", mit_snapshot=False)
    reduziert = specs_ohne("strecke")

    monkeypatch.setattr(tcp, "_COMMAND_SPECS", reduziert)
    text = _fehlertext_unbekanntes_wort(fix)

    assert "strecke" not in text_woerter(text), (
        "AC-10-Gegenprobe: `strecke` wurde aus _COMMAND_SPECS entfernt, steht "
        f"aber weiter im Fehlertext — der Text ist danebengeschrieben:\n{text}"
    )


# ===========================================================================
# AC-11 — Klartext- und HTML-Fussz. tragen dieselbe Befehlsmenge
# ===========================================================================

def _plain_kommandoblock() -> str:
    """Der Block "Antwort-Kommandos" aus der ECHTEN Klartext-Ausgabe."""
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.plain import render_plain

    text = render_plain(
        segments=segmente(_JETZT, standard_felder),
        seg_tables=[[]],
        trip_name="Adhoc AC-11 Trip",
        report_type="evening",
        dc=build_default_display_config(),
        night_rows=[],
        thunder_forecast=None,
        changes=None,
        stage_name="Etappe 1",
        stage_stats=None,
        multi_day_trend=None,
        compact_summary="Test",
        tz=TZ,
        friendly_keys=set(),
    )
    zeilen = text.splitlines()
    start = next(
        (i for i, z in enumerate(zeilen) if "Antwort-Kommandos" in z), None,
    )
    assert start is not None, (
        f"Testaufbau: kein Block 'Antwort-Kommandos' in der Klartext-Mail:\n"
        f"{text}"
    )
    block: list[str] = []
    for zeile in zeilen[start + 1:]:
        if not zeile.strip():
            break
        block.append(zeile)
    assert block, "Testaufbau: der Kommando-Block der Klartext-Mail ist leer."
    return "\n".join(block)


def _html_kommandoblock() -> str:
    """Der Block "Antwort-Kommandos" aus der ECHTEN HTML-Ausgabe, entmarkupt."""
    from output.renderers.email.html import _render_kommandos_section

    return re.sub(r"<[^>]+>", " ", _render_kommandos_section())


def _befehlswoerter(text: str) -> set[str]:
    """Alle GROSSGESCHRIEBENEN Woerter (>=3 Zeichen) — so heben sich die
    Befehlsnamen in beiden Fussz. von ihren Beschreibungen ab, ohne dass der
    Test an einer Layout-/Style-Zeichenkette klebt."""
    return set(re.findall(r"\b[A-ZÄÖÜ]{3,}\b", text))


def test_ac11_klartext_und_html_fusszeile_tragen_dieselbe_befehlsmenge():
    """AC-11 GIVEN die Klartext- und die HTML-Fussz. "Antwort-Kommandos" WHEN
    beide gerendert werden THEN enthalten sie dieselbe Befehlsmenge (heute
    fehlt STRECKE in beiden und RUHETAG zusaetzlich im HTML)."""
    plain = _befehlswoerter(_plain_kommandoblock())
    html = _befehlswoerter(_html_kommandoblock())

    assert plain == html, (
        f"AC-11: die beiden Fussz. nennen verschiedene Befehle.\n"
        f"nur Klartext: {sorted(plain - html)!r}\n"
        f"nur HTML:     {sorted(html - plain)!r}"
    )
    assert "STRECKE" in plain, (
        f"AC-11: STRECKE fehlt in beiden Fussz. — gefunden: {sorted(plain)!r}"
    )


# ===========================================================================
# AC-12 — der Telegram-Fehlertext haengt an derselben Quelle
# ===========================================================================

class _MitschnittNotifier(NotificationService):
    """ECHTE Unterklasse als Naht: schneidet den erzeugten Text mit, statt ihn
    an die Telegram-Bot-API zu schicken. Kein Mock — geprueft wird der TEXT,
    den der Reader baut, nicht der Transport (der laege ohnehin hinter dem
    Egress-Waechter der Kernschicht)."""

    def __init__(self) -> None:
        super().__init__(user_id="default")
        self.gesendet: list[tuple[str, str]] = []

    def send_telegram_message(self, *, chat_id, subject, body, settings,
                              reply_markup=None):
        self.gesendet.append((subject, body))
        return len(self.gesendet)


def _telegram_fehlertext(chat_id: str, user_id: str) -> str:
    """Unbekannter Befehl durch den ECHTEN Reader-Eingang schicken."""
    from services.inbound_telegram_reader import InboundTelegramReader

    reader = InboundTelegramReader()
    mitschnitt = _MitschnittNotifier()
    reader._notification_service = mitschnitt

    verarbeitet = reader._process_update(
        {"message": {"text": "quatschbefehl", "chat": {"id": chat_id}}},
        Settings(is_test_mode=True),
    )
    assert verarbeitet, "Testaufbau: der Reader hat das Update nicht verarbeitet."
    assert mitschnitt.gesendet, (
        "Testaufbau: der Reader hat gar keine Antwort erzeugt."
    )
    betreff, text = mitschnitt.gesendet[-1]
    assert "Unbekannter Befehl" in betreff, (
        f"Testaufbau: erwartet die Unbekannt-Antwort, erhalten "
        f"{betreff!r} / {text!r} — der Zweig :206-209 wurde nicht erreicht "
        f"(Nutzer- oder Trip-Aufloesung des Readers ist nicht durchgelaufen)."
    )
    return text


def test_ac12_telegram_und_prozessor_fehlertext_tragen_dieselbe_befehlsmenge():
    """AC-12 GIVEN der Telegram-Fehlertext (inbound_telegram_reader.py:206)
    WHEN ein unbekanntes Kommando eingeht THEN stammt er aus derselben Quelle
    wie der Fehlertext des Prozessors — strukturell geprueft, nicht
    zeichenweise (die Formulierung darf kanalspezifisch bleiben)."""
    chat_id = "987654321"
    user_id = frische_kennung("ac12")
    fix = lege_trip_an("ac12", mit_snapshot=False, user_id=user_id)

    profil = get_data_dir(user_id) / "user.json"
    profil.parent.mkdir(parents=True, exist_ok=True)
    profil.write_text(json.dumps({
        "id": user_id,
        "created_at": "2026-09-06T00:00:00Z",
        "telegram_chat_id": chat_id,
    }), encoding="utf-8")

    text_telegram = _telegram_fehlertext(chat_id, user_id)
    text_prozessor = _fehlertext_unbekanntes_wort(fix)

    woerter_tg = text_woerter(text_telegram)
    woerter_pr = text_woerter(text_prozessor)

    fehlend = [w for w in _VERSCHWIEGEN if w not in woerter_tg]
    assert not fehlend, (
        f"AC-12: der Telegram-Fehlertext verschweigt {fehlend!r}.\n"
        f"Text war:\n{text_telegram}"
    )

    vokabular = steuerbefehl_woerter()
    assert (woerter_tg & vokabular) == (woerter_pr & vokabular), (
        f"AC-12: die beiden Fehlertexte nennen verschiedene Befehle.\n"
        f"nur Telegram:  {sorted((woerter_tg - woerter_pr) & vokabular)!r}\n"
        f"nur Prozessor: {sorted((woerter_pr - woerter_tg) & vokabular)!r}\n"
        f"Telegram:\n{text_telegram}\nProzessor:\n{text_prozessor}"
    )


# ===========================================================================
# #2417 Kurzform englisch, AC-1 — benannte Felder statt Tupel
# (SPEC: docs/specs/modules/feat_2417_kurzform_englisch.md)
# ===========================================================================

_AC1_FELDER = ("wort", "wort_en", "arg", "beschreibung_de", "wirkung_en", "kinds")


def test_ac1_command_specs_tragen_benannte_felder():
    """AC-1 GIVEN ``_COMMAND_SPECS`` WHEN ein Leser ein Feld braucht THEN
    greift er ueber den Feldnamen zu — jeder Eintrag ist eine benannte
    Struktur mit genau den Feldern ``wort``, ``wort_en``, ``arg``,
    ``beschreibung_de``, ``wirkung_en``, ``kinds`` (statt eines 4er-Tupels,
    das jede Spaltenerweiterung beim Entpacken bricht)."""
    from services import trip_command_processor as tcp

    for spec in tcp._COMMAND_SPECS:
        felder = getattr(spec, "_fields", None)
        assert felder is not None, (
            f"AC-1: _COMMAND_SPECS-Eintrag ist keine benannte Struktur "
            f"(kein _fields): {spec!r}"
        )
        fehlend = [f for f in _AC1_FELDER if f not in felder]
        assert not fehlend, f"AC-1: Eintrag {spec!r} fehlen die Felder {fehlend!r}"


def test_ac1_jeder_eintrag_traegt_englisches_wort_und_wirkung():
    """AC-1 GIVEN der Befehlssatz WHEN er um Englisch erweitert ist THEN traegt
    JEDER Eintrag ein nicht leeres ``wort_en`` und eine nicht leere
    ``wirkung_en`` — ein neuer Befehl ohne englische Wirkung faellt sofort
    auf, statt in der HELP-Kurzform ohne Wirkungstext zu erscheinen."""
    from services import trip_command_processor as tcp

    ohne = [
        spec for spec in tcp._COMMAND_SPECS
        if not (getattr(spec, "wort_en", None) or "").strip()
        or not (getattr(spec, "wirkung_en", None) or "").strip()
    ]
    assert not ohne, (
        f"AC-1: {len(ohne)} von {len(tcp._COMMAND_SPECS)} Eintraegen fehlt "
        f"wort_en oder wirkung_en: {ohne!r}"
    )
