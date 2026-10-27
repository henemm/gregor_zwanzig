"""TDD RED — Issue #2051 S1: Horizont-Waechter `event_ongoing_beyond_horizon`.

SPEC: docs/specs/modules/feat_2051_s1_dauer_und_ende.md — AC-5 (vollstaendig).

Fachlicher Kern (R4): "Ende" bei abgeschnittener Zeitreihe ist NICHT dasselbe
wie "Ende des Ereignisses". Wenn der letzte bekannte Frame noch nass ist —
weil die Frames ausgegangen sind oder der 180-Minuten-Horizont erreicht ist —
ist das echte Ende unbekannt. Der Waechter macht das sichtbar.

Spec-Fassung 1.1 (PO-Entscheid 2026-08-22) kehrt die urspruengliche Behandlung
UM: statt die Ende-Angabe wegzulassen, nennt jede der sieben Textstellen das
Ende als belegte UNTERGRENZE. `event_end_minutes` traegt in beiden
Waechter-Faellen bereits eine beobachtete, keine geratene Zahl — sie
wegzulassen verwarf eine wahre Aussage. Die Untergrenzen-Form nennt sie, ohne
ein unbekanntes echtes Ende zu behaupten:

  * Langform: `Regen mindestens bis HH:MM` (statt `letzter Regen gegen HH:MM`)
  * Kurzform: ` >@HH:MM` (statt `@HH:MM`), also `R@18:30 >@21:00`

Diese Datei deckt AC-5 vollstaendig ab:
  * das Flag selbst in `_derive_result` (beide Auspraegungen: Frames enden
    mitten im Fenster / Block reicht bis zum Horizont),
  * Langform E-Mail-Trip (`_render_email_onset` ueber `render_email`) — und
    zwar mit einem Ergebnis aus `_derive_result` ueber echte Frames, also
    ueber die gesamte Naht Ableitung -> `event_end_display` -> Renderer,
  * Kurzform SMS (`_render_sms_onset` ueber `render_sms`),
  * Briefing-Kurzfristhinweis (`format_starkregen_hint`).

Jeder Renderer-Fall traegt seine GEGENFASSUNG im selben Test: ohne gesetzten
Waechter MUSS die NORMALFORM erscheinen und die Untergrenzen-Form fehlen.
Ohne diese Kontrolle bestuende ein Renderer, der pauschal immer "mindestens"
schreibt, die Pruefung ebenfalls — die textliche Abgrenzung beider Formen ist
der ganze Grund fuer die Aenderung (AC-20).

RED heute: der Code ist auf Spec-Stand 1.0 und laesst die Ende-Angabe bei
gesetztem Waechter ERSATZLOS weg (`event_end_display` -> `(None, 0)`,
`format_starkregen_hint` -> Satz ohne Ende). Die Untergrenzen-Form gibt es
noch nirgends.

Mock-frei: echte `RadarFrame`/`NowcastResult`-Objekte durch die echten
Renderer. Die Uhr ist im Ableitungsteil ueber `now=` injiziert; im
Renderer-Teil ueber `freeze_time` festgestellt, weil der Buendel-Konstruktor
`onset_time` selbst aus `datetime.now()` bildet.
"""
from __future__ import annotations

import inspect
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from freezegun import freeze_time

from output.renderers.alert.project import to_multi_location_onset_alert_message
from output.renderers.alert.render import render_email, render_sms
from output.renderers.email.starkregen_hint import format_starkregen_hint
from providers.brightsky import RadarFrame
from services.radar_cache import RadarNowcastCacheService
from services.radar_service import (
    _NOWCAST_HORIZON_MIN, NowcastResult, RadarNowcastService,
)

_NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)

# Renderer-Teil: 18:00 Ortszeit Wien (= 16:00 UTC im Sommer). Beginn 18:30
# (+30 Min), bekanntes Ende 19:30 (+90 Min), Untergrenze am Horizont 21:00
# (+180 Min). Die beiden Ende-Zeitpunkte sind BEWUSST verschieden: so faellt
# auf, wenn eine Fassung die Zahl der anderen zeigt.
_TZ = ZoneInfo("Europe/Vienna")
_FROZEN_UTC = "2026-08-21 16:00:00+00:00"
# Dieselbe Sekunde als Objekt — Fensterbezug fuer die Frame-Zeitreihen des
# Langform-Tests, der den Waechter aus der ECHTEN Ableitung bezieht.
_FROZEN_NOW = datetime(2026, 8, 21, 16, 0, tzinfo=timezone.utc)
_ENDE_TEXT = "letzter Regen gegen 19:30"
_UNTERGRENZE_TEXT = "Regen mindestens bis 21:00"
# Kurzform-Untergrenze (Spec v1.1): Leerzeichen, `>`, dann das Zeit-Token.
_UNTERGRENZE_TOKEN = " >@21:00"
# Ende-Token OHNE vorangestelltes `>`: genau die Form, die im Waechterfall
# NICHT stehen darf, weil sie ein bekanntes Ende behauptet. Der Lookbehind
# trennt sie vom Untergrenzen-Token, das dieselbe Uhrzeit traegt.
_BLANKES_ENDE_RE = re.compile(r"(?<!>)@21:00")

_UNSET = object()  # Sentinel: neue Felder nur setzen, wenn ausdruecklich verlangt.


def _frames(raster: dict[int, float]) -> list[RadarFrame]:
    return [
        RadarFrame(timestamp=_NOW + timedelta(minutes=minute), precip_mm_h=rate)
        for minute, rate in sorted(raster.items())
    ]


def _result(raster: dict[int, float]):
    svc = RadarNowcastService(cache=RadarNowcastCacheService())
    return svc._derive_result(_frames(raster), "radar", now=_NOW)


def _abgeleitetes_ergebnis(raster: dict[int, float]) -> NowcastResult:
    """Wie `_result`, aber mit `_FROZEN_NOW` als Bezugspunkt — so passen die
    abgeleiteten Minutenwerte zu der Uhr, die die Renderer sehen."""
    svc = RadarNowcastService(cache=RadarNowcastCacheService())
    frames = [
        RadarFrame(timestamp=_FROZEN_NOW + timedelta(minutes=minute),
                   precip_mm_h=rate)
        for minute, rate in sorted(raster.items())
    ]
    return svc._derive_result(frames, "radar", now=_FROZEN_NOW)


def _nowcast(*, event_end_minutes: object = _UNSET,
             event_ongoing_beyond_horizon: object = _UNSET) -> NowcastResult:
    """Ein `NowcastResult` mit gesetztem Beginn; die neuen Felder werden NUR
    uebergeben, wenn ein Aufrufer sie ausdruecklich setzt (Muster
    `test_onset_kurzform_menge.py`) — so bleiben Vergleichsfassungen ohne die
    Felder unabhaengig vom Modell-Erweiterungsstand."""
    fields = dict(
        onset_minutes=30, intensity_label="Starker Regen", source="radar",
        is_convective=False,
    )
    if event_end_minutes is not _UNSET:
        fields["event_end_minutes"] = event_end_minutes
    if event_ongoing_beyond_horizon is not _UNSET:
        fields["event_ongoing_beyond_horizon"] = event_ongoing_beyond_horizon
    return NowcastResult(**fields)


def _alert_message(nc: NowcastResult):
    """Einzel-Ort-Buendel -> `location_label is None` -> derselbe
    Einzel-Onset-Renderpfad, den auch der Trip-Radar-Alarm benutzt
    (ADR-0021: Trip und Ortsvergleich teilen die Ausgabe)."""
    return to_multi_location_onset_alert_message(
        [("Sillian", nc)], tz=_TZ, stand_at="17:55",
    )


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): Nowcast-Dienst und Alarm-Renderer werden
    RELATIV ZU DIESER Testdatei aufgeloest — sonst pruefte ein Worktree-Lauf
    still die Dateien des Hauptrepos."""
    from output.renderers.alert import render as render_module
    from services import radar_service as radar_module

    arbeitsbaum = Path(__file__).resolve().parents[2]
    for modul in (radar_module, render_module):
        modul_pfad = Path(inspect.getfile(modul)).resolve()
        assert modul_pfad.is_relative_to(arbeitsbaum), (
            f"Prueling stammt nicht aus diesem Arbeitsbaum: {modul_pfad}"
        )


# ---------------------------------------------------------------------------
# AC-5 (a) — das Flag in `_derive_result`
# ---------------------------------------------------------------------------


def test_ac5_block_bis_zum_horizont_setzt_den_waechter():
    """AC-5 GIVEN eine Frame-Zeitreihe, die vom Beginn (Minute 20) bis zum
    180-Minuten-Horizont durchgehend nass ist (kein Trockenframe im gesamten
    Fenster)
    WHEN `_derive_result` das Ergebnis baut
    THEN ist `event_ongoing_beyond_horizon=True` — das echte Ende liegt
    jenseits der Reichweite der Quelle und ist nicht behauptbar.

    RED heute: `NowcastResult` kennt das Feld nicht."""
    raster = {m: (1.0 if m >= 20 else 0.0)
              for m in range(0, _NOWCAST_HORIZON_MIN + 1, 5)}

    result = _result(raster)

    assert result.onset_minutes == 20, (
        f"Vorbedingung: Beginn bei Minute 20, bekam {result.onset_minutes}"
    )
    assert result.event_ongoing_beyond_horizon is True, (
        "RED: ein bis zum Horizont nasser Block muss den Waechter setzen, "
        f"bekam {result.event_ongoing_beyond_horizon!r}"
    )


def test_ac5_ende_am_horizont_wird_nicht_ueber_den_horizont_hinaus_behauptet():
    """AC-5 (Wert) GIVEN denselben bis zum Horizont nassen Block
    WHEN das Ende abgeleitet wird
    THEN ist `event_end_minutes` der Horizont selbst (180 Minuten) und nicht
    groesser — die Quelle reicht nicht weiter, ein spaeterer Zeitpunkt waere
    erfunden.

    RED heute: `NowcastResult` kennt `event_end_minutes` nicht."""
    raster = {m: (1.0 if m >= 20 else 0.0)
              for m in range(0, _NOWCAST_HORIZON_MIN + 1, 5)}

    result = _result(raster)

    assert result.event_end_minutes == _NOWCAST_HORIZON_MIN, (
        f"RED: erwartet den Horizont ({_NOWCAST_HORIZON_MIN} Min) als Ende, "
        f"bekam {result.event_end_minutes!r}"
    )


def test_ac5_abgeschnittene_zeitreihe_setzt_den_waechter():
    """AC-5 (zweite Auspraegung) GIVEN eine Zeitreihe, deren LETZTER
    verfuegbarer Frame (Minute 90) noch nass ist und nach der keine
    Beobachtung mehr folgt (Quelle liefert nicht bis zum Horizont)
    WHEN `_derive_result` das Ergebnis baut
    THEN ist `event_ongoing_beyond_horizon=True` — auch hier ist das echte
    Ende unbekannt, obwohl der Horizont gar nicht erreicht wurde. Der
    Unterschied zur Deckungsgrenze aus AC-4: dort folgt NACH der Luecke
    wieder eine Beobachtung, hier folgt gar keine mehr.

    RED heute: `NowcastResult` kennt das Feld nicht."""
    raster = {m: (1.0 if m >= 20 else 0.0) for m in range(0, 91, 5)}

    result = _result(raster)

    assert result.onset_minutes == 20, (
        f"Vorbedingung: Beginn bei Minute 20, bekam {result.onset_minutes}"
    )
    assert result.event_ongoing_beyond_horizon is True, (
        "RED: eine abgeschnittene, bis zuletzt nasse Zeitreihe muss den "
        f"Waechter setzen, bekam {result.event_ongoing_beyond_horizon!r}"
    )


# ---------------------------------------------------------------------------
# AC-5 (b) — Langform E-Mail (Trip-Onset-Renderpfad)
# ---------------------------------------------------------------------------


@freeze_time(_FROZEN_UTC)
def test_ac5_email_langform_nennt_die_untergrenze_bei_gesetztem_waechter():
    """AC-5 (v1.1) GIVEN einen Onset-Alarm, dessen `NowcastResult` den Waechter
    gesetzt hat (`event_ongoing_beyond_horizon=True`, Ende-Wert der Horizont
    = 21:00 Ortszeit)
    WHEN die Langform-E-Mail (`render_email` -> `_render_email_onset`)
    gerendert wird
    THEN nennt sie das Ende als belegte Untergrenze
    (`Regen mindestens bis 21:00`) und NICHT als bekanntes Ende
    (`letzter Regen gegen`) — Gegenfassung im selben Test: ohne gesetzten
    Waechter steht dort die Normalform und kein `mindestens`.

    DIESER Test bewacht die NAHT: sein `NowcastResult` kommt nicht von Hand,
    sondern aus `_derive_result` ueber echte Frames — also durch denselben
    Ableitungsweg, den der Produktivpfad nimmt
    (`_derive_wet_block_end` -> `_derive_result` -> `event_end_display` in
    `project.py` -> Renderer). Klemmt man den Waechter an der QUELLE fest,
    wird er rot. Die beiden Geschwister-Tests (SMS, Briefing) setzen die
    Felder weiterhin direkt und pruefen nur den Renderer-Wortlaut
    (Adversary-Fund F001, 2026-08-22).

    RED heute: der Code laesst die Ende-Angabe bei gesetztem Waechter
    ersatzlos weg (`event_end_display` -> `(None, 0)`)."""
    # Durchgehend nass ab Minute 30 bis an den Horizont -> Waechter gesetzt,
    # Ende = Horizont (180 Min = 21:00 Ortszeit).
    mit_waechter = _abgeleitetes_ergebnis(
        {m: (5.0 if m >= 30 else 0.0)
         for m in range(0, _NOWCAST_HORIZON_MIN + 1, 5)}
    )
    # Nass von Minute 30 bis 90, danach trocken -> die Quelle sagt selbst, wo
    # es aufhoert: bekanntes Ende bei 90 Min (19:30 Ortszeit).
    ohne_waechter = _abgeleitetes_ergebnis(
        {m: (5.0 if 30 <= m <= 90 else 0.0)
         for m in range(0, _NOWCAST_HORIZON_MIN + 1, 5)}
    )

    # Vorbedingung deckt BEWUSST nur die Zeitpunkte ab, NICHT den Waechter:
    # der ist die zu pruefende Zusicherung. Stuende er hier, schluege eine
    # Klemme an der Quelle schon in der Vorbedingung fehl und der Nachweis,
    # dass sie bis in den TEXT durchschlaegt, bliebe ungefuehrt.
    assert (mit_waechter.onset_minutes, mit_waechter.event_end_minutes) == (
        30, _NOWCAST_HORIZON_MIN), (
        f"Vorbedingung: die Ableitung muss aus diesen Frames Beginn 30 und "
        f"Ende {_NOWCAST_HORIZON_MIN} ergeben, bekam "
        f"{mit_waechter.onset_minutes!r}/{mit_waechter.event_end_minutes!r}"
    )
    assert (ohne_waechter.onset_minutes, ohne_waechter.event_end_minutes) == (
        30, 90), (
        f"Vorbedingung: die Gegenfassung muss ein Ende bei 90 Min ergeben, "
        f"bekam {ohne_waechter.onset_minutes!r}/"
        f"{ohne_waechter.event_end_minutes!r}"
    )

    _, plain_waechter = render_email(_alert_message(mit_waechter))
    _, plain_bekannt = render_email(_alert_message(ohne_waechter))

    assert _ENDE_TEXT in plain_bekannt, (
        f"Gegenfassung: bei bekanntem Ende muss die Langform "
        f"{_ENDE_TEXT!r} nennen: {plain_bekannt!r}"
    )
    assert "mindestens" not in plain_bekannt, (
        f"Gegenfassung: bei bekanntem Ende darf keine Untergrenzen-Form "
        f"stehen: {plain_bekannt!r}"
    )
    assert _UNTERGRENZE_TEXT in plain_waechter, (
        f"RED: bei gesetztem Horizont-Waechter muss die Langform die "
        f"Untergrenze {_UNTERGRENZE_TEXT!r} nennen: {plain_waechter!r}"
    )
    assert "letzter Regen gegen" not in plain_waechter, (
        f"Bei gesetztem Horizont-Waechter darf kein bekanntes Ende behauptet "
        f"werden: {plain_waechter!r}"
    )


# ---------------------------------------------------------------------------
# AC-5 (c) — Kurzform SMS
# ---------------------------------------------------------------------------


@freeze_time(_FROZEN_UTC)
def test_ac5_sms_kurzform_traegt_die_untergrenze_bei_gesetztem_waechter():
    """AC-5 (v1.1) GIVEN denselben Aufbau
    WHEN die Kurznachricht (`render_sms` -> `_render_sms_onset`) gerendert
    wird
    THEN traegt sie bei gesetztem Waechter das Untergrenzen-Token ` >@21:00`
    — Leerzeichen, `>`, dann das minutengenaue Zeit-Token (Schreibweise vom PO
    vorgegeben, Spec v1.1) — und NICHT das blanke `@21:00` der Normalform.
    Gegenfassung im selben Test: ohne Waechter steht das blanke Ende-Token
    und kein `>`.

    Kurzweg mit Absicht: die Felder werden hier direkt gesetzt, geprueft wird
    allein der Renderer-Wortlaut. Die NAHT zwischen Ableitung und Renderer
    bewacht `test_ac5_email_langform_nennt_die_untergrenze_bei_gesetztem_waechter`,
    dessen Ergebnis aus echten Frames ueber `_derive_result` stammt.

    Die frueher hier stehende `@`-Zaehlung traegt nicht mehr: beide Formen
    tragen zwei `@`. Geprueft wird deshalb die FORM des Ende-Tokens
    ausdruecklich, per Regex mit Lookbehind — sonst waere `>@` und `@` an der
    Ende-Position ununterscheidbar.

    RED heute: der Code laesst das Ende-Token bei gesetztem Waechter
    ersatzlos weg (`event_end_display` -> `(None, 0)`)."""
    mit_waechter = _nowcast(event_end_minutes=_NOWCAST_HORIZON_MIN,
                            event_ongoing_beyond_horizon=True)
    ohne_waechter = _nowcast(event_end_minutes=90,
                             event_ongoing_beyond_horizon=False)

    sms_waechter = render_sms(_alert_message(mit_waechter))
    sms_bekannt = render_sms(_alert_message(ohne_waechter))

    assert "@19:30" in sms_bekannt and ">" not in sms_bekannt, (
        f"Gegenfassung: bei bekanntem Ende traegt die Kurznachricht das "
        f"blanke Ende-Token '@19:30' ohne '>': {sms_bekannt!r}"
    )
    assert _UNTERGRENZE_TOKEN in sms_waechter, (
        f"RED: bei gesetztem Horizont-Waechter muss die Kurznachricht das "
        f"Untergrenzen-Token {_UNTERGRENZE_TOKEN!r} tragen: {sms_waechter!r}"
    )
    assert _BLANKES_ENDE_RE.search(sms_waechter) is None, (
        f"Der Ende-Zeitpunkt steht ohne vorangestelltes '>' in der "
        f"Kurznachricht und behauptet damit ein bekanntes Ende: "
        f"{sms_waechter!r}"
    )
    assert "18:30" in sms_waechter, (
        f"Das Beginn-Token darf nicht verdraengt werden: {sms_waechter!r}"
    )


# ---------------------------------------------------------------------------
# AC-5 (d) — Briefing-Kurzfristhinweis
# ---------------------------------------------------------------------------


@freeze_time(_FROZEN_UTC)
def test_ac5_briefing_hinweis_nennt_die_untergrenze_bei_gesetztem_waechter():
    """AC-5 (v1.1) GIVEN den Briefing-Kurzfristhinweis mit gesetztem Waechter
    WHEN `format_starkregen_hint(...)` rendert
    THEN nennt der Hinweis das Ende als Untergrenze
    (`Regen mindestens bis 21:00`) statt es wegzulassen, und NICHT als
    bekanntes Ende — Gegenfassung im selben Test: mit
    `event_ongoing_beyond_horizon=False` steht `letzter Regen gegen 19:30` da
    und kein `mindestens`.

    Kurzweg mit Absicht (wie beim SMS-Fall): `format_starkregen_hint` bekommt
    die Werte direkt, geprueft wird der Wortlaut. Die Naht zur Ableitung
    bewacht der Langform-Test.

    RED heute: `format_starkregen_hint` unterdrueckt die Ende-Angabe bei
    gesetztem Waechter vollstaendig (`starkregen_hint.py:41`)."""
    text_waechter = format_starkregen_hint(
        "Starker Regen", 30, tz=_TZ,
        event_end_minutes=_NOWCAST_HORIZON_MIN,
        event_ongoing_beyond_horizon=True,
    )
    text_bekannt = format_starkregen_hint(
        "Starker Regen", 30, tz=_TZ,
        event_end_minutes=90, event_ongoing_beyond_horizon=False,
    )

    assert _ENDE_TEXT in text_bekannt, (
        f"Gegenfassung: bei bekanntem Ende muss der Briefing-Hinweis "
        f"{_ENDE_TEXT!r} nennen: {text_bekannt!r}"
    )
    assert "mindestens" not in text_bekannt, (
        f"Gegenfassung: bei bekanntem Ende darf keine Untergrenzen-Form "
        f"stehen: {text_bekannt!r}"
    )
    assert _UNTERGRENZE_TEXT in text_waechter, (
        f"RED: bei gesetztem Horizont-Waechter muss der Briefing-Hinweis die "
        f"Untergrenze {_UNTERGRENZE_TEXT!r} nennen: {text_waechter!r}"
    )
    assert "letzter Regen gegen" not in text_waechter, (
        f"Bei gesetztem Horizont-Waechter darf der Briefing-Hinweis kein "
        f"bekanntes Ende behaupten: {text_waechter!r}"
    )
