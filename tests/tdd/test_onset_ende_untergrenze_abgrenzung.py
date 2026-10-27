"""TDD RED — Issue #2051 Scheibe S1: Untergrenze und bekanntes Ende bleiben
textlich UNTERSCHEIDBAR.

SPEC: docs/specs/modules/feat_2051_s1_dauer_und_ende.md (v1.1) — AC-20.

Fachlicher Kern: seit dem PO-Entscheid vom 2026-08-22 nennen alle sieben
Textstellen auch bei gesetztem R4-Waechter
(`event_ongoing_beyond_horizon=True`) einen Ende-Zeitpunkt — aber als belegte
UNTERGRENZE, nicht als bekanntes Ende. Die Zahl ist in beiden Faellen
dieselbe; nur die FORM sagt, was sie bedeutet:

  | Zustand | Langform | Kurzform |
  |---|---|---|
  | `False` (Ende bekannt) | `letzter Regen gegen HH:MM` | `@HH:MM` |
  | `True` (Zeitreihe/Horizont zu Ende) | `Regen mindestens bis HH:MM` | ` >@HH:MM` |

"Der Regen hoert um 19:30 auf" und "der Regen hoert mindestens bis 19:30
nicht auf" sind gegensaetzliche Aussagen. Rutschen die beiden Formen
ineinander — weil ein Renderer den Waechter nicht liest oder pauschal eine
der beiden Formen schreibt —, steht im Text das Gegenteil des Gemeinten. Der
Kanal, in dem das am teuersten ist, ist die Premium-SMS: auf der Huette am
Karnischen Hoehenweg kommt nur sie an, und dort entscheidet ` >` allein
ueber die Bedeutung.

Diese Datei prueft deshalb BEIDE Richtungen ueber alle sieben Textstellen:

  1. E-Mail-Betreff (`_render_subject_onset`)
  2. E-Mail Trip, Klartext (`_render_email_onset`)
  3. E-Mail Trip, HTML (dieselbe Stelle, Normalfassung)
  4. E-Mail Mehr-Orte (`_render_email_onset_multi`)
  5. Telegram rich (`_render_telegram_onset`)
  6. Kurzform SMS/Premium-SMS/Telegram-Kurzstil (`_render_sms_onset`)
  7. Briefing-Kurzfristhinweis (`format_starkregen_hint`)
  8. Kommando-Antwort (`RadarNowcastService.format_now_text`)

Beide Zustaende tragen ABSICHTLICH denselben `event_end_minutes`-Wert: so
kann kein Test versehentlich die Uhrzeit statt der Form pruefen, und ein
Renderer, der beide Zustaende gleich behandelt, faellt sicher durch.

Jede Negativ-Pruefung steht zusammen mit ihrer Positivkontrolle im selben
Test. Ohne sie waere "im Waechterfall steht nirgends `letzter Regen gegen`"
heute trivial wahr — der Code auf Spec-Stand 1.0 laesst die Ende-Angabe dort
naemlich ersatzlos weg.

RED heute: Spec-Stand 1.0 kennt die Untergrenzen-Form nicht. Die
Waechterfall-Tests scheitern an der fehlenden Untergrenze
(`event_end_display` -> `(None, 0)`, `starkregen_hint.py:41`,
`radar_service.py:548`). Die Normalfall-Tests sind ausdruecklich als
VERGLEICHSFASSUNG gebaut und bleiben gruen — sie nageln fest, dass die
Aenderung den unveraenderten Zweig nicht mitreisst.

Mock-frei: echte `NowcastResult`-Objekte durch den echten Projektions- und
Renderpfad (`to_multi_location_onset_alert_message`, ADR-0021: Trip und
Ortsvergleich teilen die Ausgabe). Die Uhr steht per `freeze_time`, weil
Projektion und Hinweis-Formatierer ihre Zeitpunkte selbst aus
`datetime.now()` bilden.
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path
from zoneinfo import ZoneInfo

from freezegun import freeze_time

from output.renderers.alert.project import to_multi_location_onset_alert_message
from output.renderers.alert.render import (
    render_email, render_sms, render_subject, render_telegram,
)
from output.renderers.email.starkregen_hint import format_starkregen_hint
from services.radar_cache import RadarNowcastCacheService
from services.radar_service import NowcastResult, RadarNowcastService

# 18:00 Ortszeit Wien (= 16:00 UTC im Sommer). Beginn 18:30 (+30 Min),
# Ende 19:30 (+90 Min) — in BEIDEN Zustaenden derselbe Wert.
_TZ = ZoneInfo("Europe/Vienna")
_FROZEN_UTC = "2026-08-21 16:00:00+00:00"
_ONSET_MIN = 30
_ENDE_MIN = 90
_BEGINN_HHMM = "18:30"
_ENDE_HHMM = "19:30"

_LANGFORM_NORMAL = f"letzter Regen gegen {_ENDE_HHMM}"
_LANGFORM_UNTERGRENZE = f"Regen mindestens bis {_ENDE_HHMM}"
# Kurzform-Untergrenze laut Spec v1.1: Leerzeichen, `>`, dann das Zeit-Token.
_KURZFORM_UNTERGRENZE = f" >@{_ENDE_HHMM}"
# Das Ende-Token OHNE vorangestelltes `>` — die Normalform. Der Lookbehind
# unterscheidet sie von der Untergrenzen-Form, die dieselbe Uhrzeit traegt;
# eine reine Substring-Suche nach `@19:30` faende beide und bewachte keine.
_BLANKES_ENDE_RE = re.compile(r"(?<!>)@" + re.escape(_ENDE_HHMM))

# Alle Fassungen ausser der Kurzform reden Langform.
_KURZFORM = "sms_kurzform"
# Fassungen MIT Auszeichnung: dort kommt `>` aus `<b>`/HTML-Tags und sagt
# nichts ueber die Ende-Angabe. Sie werden von der blanken `>`-Pruefung
# ausgenommen; ihre Untergrenzen-Pruefung laeuft ueber `>@` bzw. den
# Langform-Wortlaut, der von Auszeichnung unberuehrt bleibt.
_MIT_AUSZEICHNUNG = ("email_trip_html", "telegram_rich")

# Woran die Anwesenheit des BEGINNS je Fassung erkennbar ist. Fuenf der sechs
# Langform-Fassungen nennen ihn als Uhrzeit; der E-Mail-Betreff nennt ihn seit
# jeher als COUNTDOWN und nie als Uhrzeit (`render.py:355`:
# `f"[{trip_short}] {km} · {label} in {onset_minutes} Min"`) — vier
# Bestandstests nageln genau diese Form als Gleichheit fest
# (`test_alert_location_vocabulary.py:421`, `test_alert_sms_onset_zeitpunkt.py:451`,
# `test_alert_addendum_sms.py:543`, `test_multi_location_onset_alert.py:38`).
#
# Der Indikator wird deshalb je Fassung gewaehlt statt pauschal `18:30`
# vorauszusetzen. Die Zusicherung wird dadurch NICHT schwaecher: fuer jede der
# sechs Fassungen bleibt geprueft, dass die angehaengte Ende-Angabe die
# Beginn-Angabe ERGAENZT statt sie zu verdraengen — beim Betreff, dem
# kuerzesten und damit gefaehrdetsten Text, eben am Countdown.
#
# Eine Uhrzeit IN den Betreff zu ziehen waere ein Produktentscheid zum
# Zeitangaben-Wortlaut und gehoert der Parallelsitzung
# `fix-2020-zeitangaben-wortlaut` (#2020 S2), nicht dieser Scheibe.
_BEGINN_INDIKATOR = {"email_betreff": f"in {_ONSET_MIN} Min"}


def _nowcast(*, ongoing: bool) -> NowcastResult:
    """Ein Nowcast-Ergebnis mit Beginn UND Ende; nur der Waechter variiert."""
    return NowcastResult(
        onset_minutes=_ONSET_MIN, intensity_label="Starker Regen",
        source="radar", is_convective=False,
        event_end_minutes=_ENDE_MIN, event_ongoing_beyond_horizon=ongoing,
    )


def _texte(*, ongoing: bool) -> dict[str, str]:
    """Die sieben Textstellen (E-Mail Trip in beiden Haelften) fuer EINEN
    Waechter-Zustand.

    Der Einzel-Ort-Aufruf laesst `location_label is None` und faellt damit in
    denselben Einzel-Onset-Renderpfad, den auch der Trip-Radar-Alarm benutzt
    (ADR-0021); der Zwei-Orte-Aufruf erreicht zusaetzlich den
    Mehr-Orte-Zweig."""
    nc = _nowcast(ongoing=ongoing)
    einzel = to_multi_location_onset_alert_message(
        [("Sillian", nc)], tz=_TZ, stand_at="17:55",
    )
    buendel = to_multi_location_onset_alert_message(
        [("Sillian", nc), ("Obertilliach", _nowcast(ongoing=ongoing))],
        tz=_TZ, stand_at="17:55",
    )
    html_einzel, plain_einzel = render_email(einzel)
    _html_buendel, plain_buendel = render_email(buendel)
    svc = RadarNowcastService(cache=RadarNowcastCacheService())
    return {
        "email_betreff": render_subject(einzel),
        "email_trip_plain": plain_einzel,
        "email_trip_html": html_einzel,
        "email_mehr_orte": plain_buendel,
        "telegram_rich": render_telegram(einzel),
        _KURZFORM: render_sms(einzel),
        "briefing_hinweis": format_starkregen_hint(
            "Starker Regen", _ONSET_MIN, tz=_TZ,
            event_end_minutes=_ENDE_MIN,
            event_ongoing_beyond_horizon=ongoing,
        ),
        "kommando_antwort": svc.format_now_text(nc, tz=_TZ, include_source=False),
    }


def _langform_fassungen(texte: dict[str, str]) -> dict[str, str]:
    return {name: text for name, text in texte.items() if name != _KURZFORM}


def _befund(treffer: dict[str, str]) -> str:
    """Lesbare Fehlermeldung: Name der Fassung plus ein Ausschnitt. Der
    HTML-Teil der Mail ist mehrere Kilobyte gross — vollstaendig ausgegeben
    ersaeuft er die eigentliche Aussage."""
    return "; ".join(
        f"{name}={text[:160]!r}" for name, text in sorted(treffer.items())
    )


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): Projektion, Alarm-Renderer, Briefing-Hinweis
    und Nowcast-Dienst werden RELATIV ZU DIESER Testdatei aufgeloest — sonst
    pruefte ein Worktree-Lauf still die Dateien des Hauptrepos und lieferte
    falsches Gruen."""
    from output.renderers.alert import project as project_module
    from output.renderers.alert import render as render_module
    from output.renderers.email import starkregen_hint as hint_module
    from services import radar_service as radar_module

    arbeitsbaum = Path(__file__).resolve().parents[2]
    for modul in (project_module, render_module, hint_module, radar_module):
        modul_pfad = Path(inspect.getfile(modul)).resolve()
        assert modul_pfad.is_relative_to(arbeitsbaum), (
            f"Prueling stammt nicht aus diesem Arbeitsbaum: {modul_pfad}"
        )


# ---------------------------------------------------------------------------
# AC-20 (a) — Waechterfall: Untergrenze JA, bekanntes Ende NEIN
# ---------------------------------------------------------------------------


@freeze_time(_FROZEN_UTC)
def test_ac20_waechterfall_langform_nennt_die_untergrenze_statt_des_bekannten_endes():
    """AC-20 GIVEN `event_ongoing_beyond_horizon=True` bei gesetztem
    `event_end_minutes`
    WHEN die sechs Langform-Textstellen gerendert werden (Betreff, E-Mail Trip
    in Klartext und HTML, E-Mail Mehr-Orte, Telegram rich, Briefing-Hinweis,
    Kommando-Antwort)
    THEN nennt JEDE die Untergrenze `Regen mindestens bis 19:30` und KEINE die
    Normalfall-Formulierung `letzter Regen gegen` — die Untergrenze darf nicht
    als bekanntes Ende missverstanden werden.

    Die Positivkontrolle steht bewusst im selben Test: ohne sie waere die
    Negativ-Pruefung heute trivial wahr, weil der Code auf Spec-Stand 1.0 im
    Waechterfall gar keine Ende-Angabe rendert.

    RED heute: keine der Fassungen kennt die Untergrenzen-Form."""
    texte = _langform_fassungen(_texte(ongoing=True))

    ohne_untergrenze = {
        name: text for name, text in texte.items()
        if _LANGFORM_UNTERGRENZE not in text
    }
    assert not ohne_untergrenze, (
        f"RED: diese Langform-Stellen nennen die Untergrenze "
        f"{_LANGFORM_UNTERGRENZE!r} nicht: {_befund(ohne_untergrenze)}"
    )

    mit_bekanntem_ende = {
        name: text for name, text in texte.items()
        if "letzter Regen gegen" in text
    }
    assert not mit_bekanntem_ende, (
        "Diese Stellen behaupten ein BEKANNTES Ende, obwohl nur eine "
        f"Untergrenze belegt ist: {_befund(mit_bekanntem_ende)}"
    )

    ohne_beginn = {
        name: text for name, text in texte.items()
        if _BEGINN_INDIKATOR.get(name, _BEGINN_HHMM) not in text
    }
    assert not ohne_beginn, (
        f"Vorbedingung: die Beginn-Angabe darf nicht verdraengt werden: "
        f"{_befund(ohne_beginn)}"
    )


@freeze_time(_FROZEN_UTC)
def test_ac20_waechterfall_kurzform_traegt_das_untergrenzen_token_statt_des_blanken():
    """AC-20 (Kurzform) GIVEN denselben Aufbau
    WHEN die Kurznachricht gerendert wird (SMS, Premium-SMS und
    Telegram-Kurzstil teilen denselben `sms_body`)
    THEN traegt sie das Untergrenzen-Token ` >@19:30` und an der Ende-Position
    NIEMALS ein schmuckloses `@19:30` ohne vorangestelltes `>`.

    Das ist die schaerfste Stelle der ganzen Abgrenzung: zwischen "hoert um
    19:30 auf" und "hoert mindestens bis 19:30 nicht auf" steht hier ein
    einziges Zeichen. Auf der Huette am Karnischen Hoehenweg kommt nur die
    Premium-SMS an — faellt das `>` weg, liest der Nutzer dort das Gegenteil.

    RED heute: der Waechterfall rendert gar kein Ende-Token
    (`event_end_display` -> `(None, 0)`)."""
    sms = _texte(ongoing=True)[_KURZFORM]

    assert _KURZFORM_UNTERGRENZE in sms, (
        f"RED: die Kurznachricht traegt das Untergrenzen-Token "
        f"{_KURZFORM_UNTERGRENZE!r} nicht: {sms!r}"
    )
    assert _BLANKES_ENDE_RE.search(sms) is None, (
        f"Der Ende-Zeitpunkt steht ohne vorangestelltes '>' und behauptet "
        f"damit ein bekanntes Ende: {sms!r}"
    )
    assert f"@{_BEGINN_HHMM}" in sms, (
        f"Vorbedingung: das Beginn-Token darf nicht verdraengt werden: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-20 (b) — Normalfall: bekanntes Ende JA, Untergrenzen-Zeichen NEIN
# ---------------------------------------------------------------------------


@freeze_time(_FROZEN_UTC)
def test_ac20_normalfall_langform_nennt_das_bekannte_ende_und_nie_mindestens():
    """AC-20 (Gegenrichtung) GIVEN `event_ongoing_beyond_horizon=False` bei
    demselben `event_end_minutes`
    WHEN dieselben Langform-Textstellen gerendert werden
    THEN nennt JEDE das bekannte Ende `letzter Regen gegen 19:30` und KEINE
    traegt das Wort `mindestens` — ein Ende, das die Quelle beobachtet hat,
    darf nicht als blosse Untergrenze verkleinert werden.

    VERGLEICHSFASSUNG: dieser Zweig aendert sich in Spec v1.1 nicht und ist
    heute gruen. Er ist der Waechter dagegen, dass die Untergrenzen-Form
    pauschal ueberall eingebaut wird — genau die Verfaelschung, die die
    Negativ-Pruefung des Waechterfalls allein nicht faengt."""
    texte = _langform_fassungen(_texte(ongoing=False))

    ohne_ende = {
        name: text for name, text in texte.items()
        if _LANGFORM_NORMAL not in text
    }
    assert not ohne_ende, (
        f"Bei bekanntem Ende muss jede Langform-Stelle "
        f"{_LANGFORM_NORMAL!r} nennen; ohne: {_befund(ohne_ende)}"
    )

    mit_untergrenze = {
        name: text for name, text in texte.items() if "mindestens" in text
    }
    assert not mit_untergrenze, (
        "Diese Stellen nennen das bekannte Ende als blosse Untergrenze: "
        f"{_befund(mit_untergrenze)}"
    )


@freeze_time(_FROZEN_UTC)
def test_ac20_normalfall_kurzform_traegt_das_blanke_ende_token_ohne_groesser_zeichen():
    """AC-20 (Gegenrichtung, Kurzform) GIVEN denselben Aufbau mit
    `event_ongoing_beyond_horizon=False`
    WHEN die Kurznachricht gerendert wird
    THEN traegt sie das blanke Ende-Token `@19:30` und KEIN `>` — weder als
    Untergrenzen-Token noch sonstwo.

    VERGLEICHSFASSUNG (heute gruen): fiele diese Pruefung, hiesse das, die
    Kurzform schriebe die Untergrenzen-Form auch dann, wenn das Ende bekannt
    ist."""
    sms = _texte(ongoing=False)[_KURZFORM]

    assert _BLANKES_ENDE_RE.search(sms) is not None, (
        f"Bei bekanntem Ende muss das blanke Token '@{_ENDE_HHMM}' stehen: "
        f"{sms!r}"
    )
    assert ">" not in sms, (
        f"Bei bekanntem Ende darf die Kurznachricht kein '>' tragen: {sms!r}"
    )


@freeze_time(_FROZEN_UTC)
def test_ac20_normalfall_traegt_in_keiner_auszeichnungsfreien_fassung_ein_groesser_zeichen():
    """AC-20 (Gegenrichtung, wortwoertlich) GIVEN `event_ongoing_beyond_horizon
    =False`
    WHEN die auszeichnungsfreien Textstellen gerendert werden (Betreff,
    E-Mail-Klartext einzeln und gebuendelt, Kurzform, Briefing-Hinweis,
    Kommando-Antwort)
    THEN traegt KEINE von ihnen ein `>`.

    HTML-Mail und Telegram rich sind ausgenommen, weil dort `>` aus
    `<b>`/Tag-Syntax stammt und nichts ueber die Ende-Angabe aussagt; fuer
    diese beiden faengt die `mindestens`-Pruefung oben dieselbe Verfaelschung
    im Wortlaut ab, und `>@` waere dort ebenfalls sichtbar — deshalb wird es
    hier zusaetzlich fuer ALLE Fassungen geprueft.

    VERGLEICHSFASSUNG, heute gruen."""
    texte = _texte(ongoing=False)

    mit_token = {
        name: text for name, text in texte.items() if ">@" in text
    }
    assert not mit_token, (
        f"Untergrenzen-Token '>@' im Normalfall: {_befund(mit_token)}"
    )

    mit_zeichen = {
        name: text for name, text in texte.items()
        if name not in _MIT_AUSZEICHNUNG and ">" in text
    }
    assert not mit_zeichen, (
        f"'>' in einer auszeichnungsfreien Fassung des Normalfalls: "
        f"{_befund(mit_zeichen)}"
    )
