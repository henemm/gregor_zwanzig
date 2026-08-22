"""TDD RED — Issue #2075: das Blockende in der Zone kurz VOR dem Horizont.

SPEC: docs/specs/modules/fix_2075_ende_am_radar_horizont.md — AC-1, AC-2,
AC-5, AC-8.

Fachlicher Kern: `_derive_wet_block_end` (#2051 S1) bildet je nassem Frame
eine Deckungsgrenze aus dessen eigener Deckung (`ts + _MAX_FRAME_COVERAGE`),
gedeckelt auf den Horizont — rechnet dabei aber, anders als seine beiden
Geschwister `_accumulate_precip_mm` und `_laufendes_frame`, den naechsten
Frame-Nachbarn NICHT ein. Endet der Regen innerhalb der letzten 15 Minuten
vor dem Horizont, greift deshalb der Horizont-Zweig, obwohl die Quelle den
Trockenuebergang laengst beobachtet hat: bis zu 14 Minuten Regen zu viel, und
eine BELEGTE Aussage erscheint als blosse Untergrenze.

#2051 S1 hatte je ein Kriterium an den beiden RAENDERN (Ende deutlich vor dem
Horizont / durchgehend nass bis zum Horizont) und liess die Flaeche dazwischen
ungeprueft — genau dort lag der Fehler. Diese Datei prueft die Zone deshalb
als FLAECHE, nicht als Einzelpunkt.

Bezugsrahmen aller Faelle (gemessen auf Staging bei der Verifikation von
#2051 S1): `now = 10:35`, `horizon = 13:35` (180 Min), Beginn 10:55.

Was hier steht:
  * AC-1 — die fehlerhafte Zone `T = 13:21 … 13:31` als parametrisierte
    Flaeche im 2-Minuten-Raster.
  * AC-2 — der Randfall `T = 13:33` mit einem trockenen Frame EXAKT auf dem
    Horizont. Bewusst ein eigener Test und nicht Teil der Parametrisierung:
    er ist der Fall, den der naive Einzeiler (Nachbar in die Deckung
    einrechnen) allein NICHT loest.
  * AC-5 — Nachbar JENSEITS des Horizonts. Positivkontrolle gegen ein
    Ueberschiessen des Fixes; heute schon gruen und nach dem Fix ebenso.
  * AC-8 — Durchschlag bis in den gerenderten Text (Langform + Kurzform),
    ueber die ECHTE Kette Ableitung -> `event_end_display` -> Renderer.

Bestandsfaelle (AC-3, AC-4, AC-6, AC-7, AC-9) werden hier NICHT dupliziert;
sie stehen in `test_nowcast_blockende_horizont_waechter.py`,
`_datenluecke.py`, `_ableitung.py` und
`test_alarm_szenario_laufendes_ereignis.py` und laufen als Regression mit.

Mock-frei: echte `RadarFrame`-Objekte durch die echte Ableitung und die
echten Renderer, die Uhr ist ueber `now=` FEST injiziert (keine Wanduhr).
Eigener Cache je Service, damit kein prozessweit geteilter Zustand wirkt.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from output.renderers.alert.model import OnsetEvent
from output.renderers.alert.project import event_end_display
from output.renderers.alert.render import _onset_end_suffix, _sms_onset_ende
from providers.brightsky import RadarFrame
from services.radar_cache import RadarNowcastCacheService
from services.radar_service import (
    _NOWCAST_HORIZON_MIN, RadarNowcastService, _derive_wet_block_end,
)

# Fester Bezugszeitpunkt aller Faelle — keine Wanduhr. 10:35 UTC, damit die
# Minutenversaetze unten unmittelbar den Uhrzeiten der Spec entsprechen:
# Beginn 10:55 (+20), Horizont 13:35 (+180).
_NOW = datetime(2026, 8, 21, 10, 35, tzinfo=timezone.utc)
_HORIZON = _NOW + timedelta(minutes=_NOWCAST_HORIZON_MIN)
_BEGINN_MIN = 20
_BEGINN_TS = _NOW + timedelta(minutes=_BEGINN_MIN)

# AC-8 rendert in Ortszeit: 2026-08-21 ist in Wien Sommerzeit (UTC+2), aus
# 13:25 UTC wird 15:25, aus dem Horizont 13:35 UTC wird 15:35. Die beiden
# Uhrzeiten sind BEWUSST verschieden — so faellt auf, wenn eine Fassung die
# Zahl der anderen zeigt.
_TZ = ZoneInfo("Europe/Vienna")

# Die gemessene Zone: letzter nasser Frame innerhalb der letzten
# `_MAX_FRAME_COVERAGE` (15 Min) vor dem Horizont, aber mit einem
# beobachteten Trockenuebergang danach.
_ZONE_MINUTEN = (166, 168, 170, 172, 174, 176)  # 13:21 … 13:31
_RANDFALL_MINUTE = 178                          # 13:33
_AC8_MINUTE = 170                               # 13:25


def _frames(raster: dict[int, float]) -> list[RadarFrame]:
    """`{Minutenversatz ab _NOW: Rate mm/h}` -> echte `RadarFrame`-Liste."""
    return [
        RadarFrame(timestamp=_NOW + timedelta(minutes=minute), precip_mm_h=rate)
        for minute, rate in sorted(raster.items())
    ]


def _zwei_minuten_raster(nass_bis: int) -> dict[int, float]:
    """Lueckenloses 2-Minuten-Raster von `_NOW` bis zum Horizont; nass
    (1.0 mm/h) vom Beginn (Minute 20) bis einschliesslich `nass_bis`, danach
    trocken."""
    return {
        m: (1.0 if _BEGINN_MIN <= m <= nass_bis else 0.0)
        for m in range(0, _NOWCAST_HORIZON_MIN + 1, 2)
    }


def _blockende(raster: dict[int, float]) -> tuple[datetime, bool]:
    """Echter Aufruf von `_derive_wet_block_end` mit derselben Bauform wie im
    Produktivpfad: `all_ts_sorted` stammt aus der VOLLSTAENDIGEN Frame-Liste
    (auch Frames jenseits des Horizonts), das Fenster begrenzt allein
    `horizon`."""
    frames = _frames(raster)
    all_ts_sorted = sorted({f.timestamp for f in frames})
    return _derive_wet_block_end(frames, all_ts_sorted, _BEGINN_TS, _HORIZON)


def _ergebnis(raster: dict[int, float]):
    """Echtes `_derive_result` mit fest injizierter Uhr — die volle Kette,
    nicht nur der Helfer."""
    svc = RadarNowcastService(cache=RadarNowcastCacheService())
    return svc._derive_result(_frames(raster), "radar", now=_NOW)


def _onset_event_aus_ableitung(raster: dict[int, float]) -> OnsetEvent:
    """Ein `OnsetEvent`, dessen Ende-Felder aus der ECHTEN Ableitung stammen.

    Der Weg ist derselbe, den beide Onset-Pfade nehmen (`project.py:555` bzw.
    der Trip-Radar-Pfad): `_derive_result` -> `event_end_display` ->
    `OnsetEvent`. Handgesetzte Felder wuerden hier nur den Renderer pruefen,
    nicht die Kette — und genau die Kette ist der Gegenstand von AC-8."""
    nc = _ergebnis(raster)
    end_time, end_offset, end_ongoing = event_end_display(_NOW, nc, _TZ)
    return OnsetEvent(
        onset_minutes=nc.onset_minutes or 0,
        onset_time="12:55",  # 10:55 UTC in Ortszeit; fuer das Ende belanglos
        km_from=8.0, km_to=8.0, is_convective=nc.is_convective,
        intensity_label=nc.intensity_label, source_label=nc.source,
        event_end_time=end_time,
        event_end_day_offset=end_offset,
        event_ongoing_beyond_horizon=end_ongoing,
    )


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): Nowcast-Dienst, Alarm-Projektion und
    Alarm-Renderer werden RELATIV ZU DIESER Testdatei aufgeloest — sonst
    pruefte ein Worktree-Lauf still die Dateien des Hauptrepos und lieferte
    falsches Gruen."""
    from output.renderers.alert import project as project_module
    from output.renderers.alert import render as render_module
    from services import radar_service as radar_module

    arbeitsbaum = Path(__file__).resolve().parents[2]
    for modul in (radar_module, project_module, render_module):
        modul_pfad = Path(inspect.getfile(modul)).resolve()
        assert modul_pfad.is_relative_to(arbeitsbaum), (
            f"Prueling stammt nicht aus diesem Arbeitsbaum: {modul_pfad}"
        )


# ---------------------------------------------------------------------------
# AC-1 — die fehlerhafte Zone als FLAECHE
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nass_bis", _ZONE_MINUTEN)
def test_ac1_beobachtetes_ende_kurz_vor_dem_horizont_bleibt_belegtes_ende(nass_bis):
    """AC-1 GIVEN ein lueckenloses 2-Minuten-Raster (now 10:35, Beginn 10:55,
    Horizont 13:35), dessen letzter nasser Frame `T` in der Zone
    `13:21 … 13:31` liegt und auf den nur noch trockene Frames folgen
    WHEN `_derive_wet_block_end` fuer jeden dieser sechs Werte einzeln
    ausgewertet wird
    THEN ist das Ende in JEDEM Fall exakt `T` und der Horizont-Waechter
    `False` — die Quelle hat den Trockenuebergang beobachtet, das Ende ist
    bekannt und keine Untergrenze.

    Als FLAECHE geprueft und nicht als Einzelpunkt: #2051 S1 hatte je ein
    Kriterium an den beiden Raendern, und genau dazwischen lag der Fehler.

    RED heute: der Horizont-Zweig greift, sobald `ts + 15 Min` den Horizont
    erreicht, ohne den naechsten (trockenen) Frame-Nachbarn einzurechnen —
    Rueckgabe `(13:35, True)`, also bis zu 14 Minuten Regen zu viel."""
    erwartet_ende = _NOW + timedelta(minutes=nass_bis)

    end_ts, ongoing = _blockende(_zwei_minuten_raster(nass_bis))

    assert (end_ts, ongoing) == (erwartet_ende, False), (
        f"RED: letzter nasser Frame {erwartet_ende:%H:%M}, danach trocken im "
        f"2-Minuten-Raster bis zum Horizont {_HORIZON:%H:%M} — erwartet "
        f"({erwartet_ende:%H:%M}, False), bekam ({end_ts:%H:%M}, {ongoing!r})"
    )


# ---------------------------------------------------------------------------
# AC-2 — der Randfall: Trockenframe exakt AUF dem Horizont
# ---------------------------------------------------------------------------


def test_ac2_trockenframe_exakt_auf_dem_horizont_beendet_den_block():
    """AC-2 GIVEN denselben Rahmen wie AC-1, aber mit letztem nassem Frame um
    13:33 und einem tatsaechlich vorhandenen, TROCKENEN Frame exakt auf dem
    Horizont (13:35)
    WHEN `_derive_wet_block_end` ausgewertet wird
    THEN ist das Ende 13:33 und der Horizont-Waechter `False`.

    Bewusst ein eigener Test statt eines siebten Parameters oben: dieser Fall
    wird davon, den Nachbarn in die Deckungsgrenze einzurechnen, allein NICHT
    repariert. Die Deckungsgrenze bleibt danach `== horizon` (der Nachbar IST
    der Horizont), und der Horizont-Zweig griffe weiterhin, bevor der
    trockene Frame ueberhaupt ausgewertet wird. Erst die zusaetzliche
    Bedingung "Horizont-Zweig nur, wenn wirklich KEIN Frame mehr innerhalb
    des Fensters folgt" schliesst ihn. Waere er in der Parametrisierung
    versteckt, verschwaende dieser Unterschied im Sammelbefund.

    RED heute: Rueckgabe `(13:35, True)` — zwei Minuten Regen zu viel, und
    ein beobachtetes Ende erscheint als Untergrenze."""
    erwartet_ende = _NOW + timedelta(minutes=_RANDFALL_MINUTE)
    raster = _zwei_minuten_raster(_RANDFALL_MINUTE)

    assert raster[_NOWCAST_HORIZON_MIN] == 0.0, (
        "Vorbedingung: auf dem Horizont-Zeitstempel MUSS ein trockener Frame "
        "liegen — ohne ihn pruefte dieser Fall etwas anderes."
    )

    end_ts, ongoing = _blockende(raster)

    assert (end_ts, ongoing) == (erwartet_ende, False), (
        f"RED: trockener Frame exakt auf dem Horizont {_HORIZON:%H:%M} — "
        f"erwartet ({erwartet_ende:%H:%M}, False), bekam "
        f"({end_ts:%H:%M}, {ongoing!r})"
    )


# ---------------------------------------------------------------------------
# AC-5 — Positivkontrolle: Nachbar JENSEITS des Horizonts
# ---------------------------------------------------------------------------


def test_ac5_nachbar_jenseits_des_horizonts_bleibt_untergrenze():
    """AC-5 GIVEN eine Frame-Zeitreihe im 5-Minuten-Raster, deren letzter
    nasser Frame um 13:30 liegt und deren naechster (trockener) Frame erst um
    13:40 folgt — also JENSEITS des Horizonts 13:35
    WHEN `_derive_wet_block_end` ausgewertet wird
    THEN bleibt das Ergebnis `(13:35, True)`.

    DIESER TEST IST HEUTE SCHON GRUEN — und muss es nach dem Fix bleiben. Er
    ist die Positivkontrolle gegen ein Ueberschiessen und bewacht beide
    Richtungen des moeglichen Fehlgriffs:

      * nicht auf 13:40 kippen — das waere eine Aussage ueber unbeobachtete
        Zeit; zwischen 13:35 und 13:40 belegt das Radar nichts, und der
        Horizont ist die Reichweitengrenze der Quelle;
      * nicht auf einen Wert VOR dem Horizont kippen — bis 13:35 ist der
        Regen durch die Deckung des 13:30-Frames belegt.

    Ohne diese Kontrolle koennte ein Fix die Zone aus AC-1 reparieren, indem
    er den Horizont-Zweig pauschal entschaerft — und die Tests blieben gruen,
    waehrend das Ergebnis unbeobachtete Zeit behauptet."""
    raster = {m: (1.0 if _BEGINN_MIN <= m <= 175 else 0.0) for m in range(0, 176, 5)}
    raster[185] = 0.0  # 13:40 — einziger Frame nach 13:30, jenseits des Horizonts

    assert _NOWCAST_HORIZON_MIN not in raster, (
        "Vorbedingung: auf dem Horizont selbst darf KEIN Frame liegen — sonst "
        "waere dies der Randfall aus AC-2 und nicht der Nachbar dahinter."
    )

    end_ts, ongoing = _blockende(raster)

    assert (end_ts, ongoing) == (_HORIZON, True), (
        f"Der Fix ueberschiesst: letzter nasser Frame 13:30, naechster Frame "
        f"erst 13:40 (jenseits des Horizonts {_HORIZON:%H:%M}) — erwartet "
        f"({_HORIZON:%H:%M}, True), bekam ({end_ts:%H:%M}, {ongoing!r})"
    )


# ---------------------------------------------------------------------------
# AC-8 — Durchschlag bis in den gerenderten Text
# ---------------------------------------------------------------------------


def test_ac8_zone_erreicht_beide_textformen_als_bekanntes_ende():
    """AC-8 GIVEN den Aufbau aus AC-1 mit `T = 13:25` (= 15:25 Ortszeit Wien)
    WHEN das `OnsetEvent` ueber die ECHTE Kette gebaut wird
    (`_derive_result` -> `event_end_display` -> `OnsetEvent`) und daraus die
    Langform (`_onset_end_suffix`) sowie die Kurzform (`_sms_onset_ende`)
    gerendert werden
    THEN nennt die Langform `letzter Regen gegen 15:25` und die Kurzform
    `@15:25` — NICHT die Untergrenzen-Formen `Regen mindestens bis` bzw.
    ` >@`.

    Der Fehler wirkt bis in den Text durch: heute liest der Nutzer
    `Regen mindestens bis 15:35` und ` >@15:35`, obwohl das Radar das Ende um
    15:25 beobachtet hat — zehn Minuten Regen zu viel, und eine belegte
    Aussage als blosse Untergrenze. Am `>` der Kurzform haengt die ganze
    Bedeutung: auf der Huette am Karnischen Hoehenweg kommt nur die
    Premium-SMS an, dort stellt kein zweiter Kanal die Aussage richtig.

    POSITIVKONTROLLE im selben Test: derselbe Renderer, aber mit einem
    Ergebnis aus einer bis zum Horizont durchgehend nassen Zeitreihe, MUSS
    sehr wohl `Regen mindestens bis 15:35` und ` >@15:35` liefern. Ohne sie
    bestuende die Negativpruefung auch ein Renderer, der die
    Untergrenzen-Form ueberhaupt nie schreibt."""
    zone = _onset_event_aus_ableitung(_zwei_minuten_raster(_AC8_MINUTE))
    # Gegenfassung: durchgehend nass bis an den Horizont -> Waechter gesetzt.
    bis_horizont = _onset_event_aus_ableitung(
        _zwei_minuten_raster(_NOWCAST_HORIZON_MIN)
    )

    # Vorbedingung deckt BEWUSST nur den Beginn ab, NICHT die Ende-Werte: die
    # sind die zu pruefende Zusicherung. Stuenden sie hier, schluege der Test
    # schon in der Vorbedingung fehl und der Nachweis, dass der Fehler bis in
    # den TEXT durchschlaegt, bliebe ungefuehrt.
    assert zone.onset_minutes == _BEGINN_MIN, (
        f"Vorbedingung: Beginn bei Minute {_BEGINN_MIN}, bekam "
        f"{zone.onset_minutes!r}"
    )

    lang_zone = _onset_end_suffix(zone)
    sms_zone = _sms_onset_ende(zone)
    lang_horizont = _onset_end_suffix(bis_horizont)
    sms_horizont = _sms_onset_ende(bis_horizont)

    # Positivkontrolle zuerst: die Untergrenzen-Form gibt es ueberhaupt.
    assert "Regen mindestens bis 15:35" in lang_horizont, (
        f"Positivkontrolle: bei durchgehend nasser Zeitreihe MUSS die "
        f"Langform die Untergrenze nennen, bekam {lang_horizont!r}"
    )
    assert sms_horizont == " >@15:35", (
        f"Positivkontrolle: bei durchgehend nasser Zeitreihe MUSS die "
        f"Kurzform das Untergrenzen-Token tragen, bekam {sms_horizont!r}"
    )

    assert "letzter Regen gegen 15:25" in lang_zone, (
        f"RED: ein um 15:25 beobachtetes Ende muss die Langform als bekanntes "
        f"Ende nennen, bekam {lang_zone!r}"
    )
    assert "mindestens" not in lang_zone, (
        f"Ein beobachtetes Ende darf nicht als Untergrenze erscheinen: "
        f"{lang_zone!r}"
    )
    assert sms_zone == "@15:25", (
        f"RED: die Kurzform muss das blanke Ende-Token '@15:25' tragen — ohne "
        f"fuehrendes ' >', das eine Untergrenze behauptet — bekam "
        f"{sms_zone!r}"
    )
