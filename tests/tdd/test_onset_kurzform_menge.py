"""TDD RED — Issue #2046: die Radar-Onset-Kurznachricht nennt die erwartete
Regenmenge.

SPEC: docs/specs/modules/fix_2046_onset_menge.md — AC-1, AC-2, AC-4, AC-5.

Fachlicher Kern: der Onset-Zweig (`_render_sms_onset`) ist heute der einzige
Alarmzweig, dessen Kurzform KEINEN Wert nennt (`Ziel: R@18:00`). Neu nennt sie
die ueber die Stunde AB DEM BEGINN erwartete Menge:

* Regen:   `Ziel: R2.5@18:00`   — Zahl klebt am Kuerzel, kein Trennzeichen.
* Gewitter: `Ziel: TH@18:00 R2.5` — die Zahl steht als EIGENES Token hinter
  der Zeit, weil die Position direkt hinter `TH` in der Briefing-Grammatik
  der Stufe (L/M/H) gehoert und ein `TH2.5` dort missverstaendlich waere.

RED-Ursache: `OnsetEvent` kennt das additive Feld `onset_precip_mm` noch
nicht -> `TypeError` beim Konstruktor-Aufruf. Die Regressionswaechter, die
das Feld NICHT setzen (AC-4a-Vergleichsfassung), bleiben davon unberuehrt.

Mock-frei: echte `OnsetEvent`/`AlertMessage`-Objekte durch die echten
Renderer. Alle Zeitangaben sind FEST gesetzt (keine Wanduhr) — ausser im
Ortsvergleich-Buendel (AC-4c), dessen Konstruktor `onset_time` selbst aus
`datetime.now()` ableitet; dort wird auf Struktur statt Goldstring geprueft.
"""
from __future__ import annotations

import inspect
import re
from datetime import timezone
from pathlib import Path

import pytest

from output.renderers.alert.model import AlertMessage, OnsetEvent
from output.renderers.alert.render import render_sms

# Eine Ziffer UNMITTELBAR hinter dem Kuerzel — die Mengen-Schreibweise des
# Regen-Falls. Wird von den ZAHLENLOSEN Faellen (AC-4a/AC-4c) benutzt: dort
# darf hinter KEINEM der beiden Kuerzel eine Ziffer stehen.
_ZIFFER_HINTER_KUERZEL_RE = re.compile(r"\b(TH|R)(\d)")
# KORRIGIERT (PO-Entscheid 2026-08-21): eigene, auf `TH` verengte Fassung fuer
# die Stufen-Zusicherung aus AC-2. Die urspruengliche Alternative `(TH|R)` an
# jener Stelle war in sich unerfuellbar — sie traf das von AC-2 SELBST
# geforderte Mengen-Token (`\bR2` in `Ziel: TH@18:00 R2.5`) und schloss damit
# den Goldstring aus, den derselbe Test zwei Zeilen darueber verlangt. Die
# Zusicherung selbst bleibt unveraendert: hinter `TH` steht NIE eine Ziffer,
# weil diese Position in der Briefing-Grammatik der Stufe (L/M/H) gehoert.
# Nur ihr fehlerhafter Ausdruck ist ersetzt; die allgemeine Fassung oben
# bleibt fuer AC-4a/AC-4c in Kraft und bewacht dort weiterhin BEIDE Kuerzel.
_ZIFFER_HINTER_TH_RE = re.compile(r"\bTH(\d)")
# Vollstaendiger Regen-Mengen-Token: `R<zahl mit einer Nachkommastelle>@HH:MM`.
_MENGEN_TOKEN_RE = re.compile(r"\bR(\d+)\.(\d)@(\d{1,2}):(\d{2})\b")

_UNSET = object()  # Sentinel: `onset_precip_mm` gar nicht erst uebergeben.


def _onset_event(*, onset_precip_mm: object = _UNSET, **kw) -> OnsetEvent:
    """Ein Trip-Radar-Onset-Ereignis mit festen Feldern (keine Wanduhr).

    `onset_precip_mm` wird NUR uebergeben, wenn ein Aufrufer es ausdruecklich
    setzt (Muster `test_alert_addendum_sms.py`): so bleibt die Vergleichs-
    fassung ohne Menge unabhaengig vom Modell-Erweiterungsstand gruen,
    waehrend die Mengen-Faelle heute am `TypeError` scheitern.
    """
    fields = dict(
        onset_minutes=30, onset_time="18:00", km_from=8.0, km_to=8.0,
        is_convective=False, intensity_label="Mäßiger Regen",
        source_label="Radar (DWD)", segment_id="Ziel",
    )
    fields.update(kw)
    if onset_precip_mm is not _UNSET:
        fields["onset_precip_mm"] = onset_precip_mm
    return OnsetEvent(**fields)


def _onset_msg(event: OnsetEvent) -> AlertMessage:
    """`source is not None` routet `render_sms` in den Onset-Zweig."""
    return AlertMessage(
        trip_short="KHW 403", stand_at="17:30", events=(event,),
        source="Radar (DWD)",
    )


def _sms(*, onset_precip_mm: object = _UNSET, **kw) -> str:
    return render_sms(_onset_msg(_onset_event(onset_precip_mm=onset_precip_mm, **kw)))


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): der gepruefte Renderer wird RELATIV ZU DIESER
    Testdatei aufgeloest — sonst pruefte ein Worktree-Lauf still die Datei des
    Hauptrepos und lieferte falsches Gruen."""
    from output.renderers.alert import render as render_module

    modul_pfad = Path(inspect.getfile(render_module)).resolve()
    arbeitsbaum = Path(__file__).resolve().parents[2]
    assert modul_pfad.is_relative_to(arbeitsbaum), (
        f"Prueling stammt nicht aus diesem Arbeitsbaum: {modul_pfad}"
    )


# ---------------------------------------------------------------------------
# AC-1 — Regen: Zahl klebt am Kuerzel, davor das Kuerzel, dahinter die Zeit
# ---------------------------------------------------------------------------


def test_ac1_regen_onset_traegt_die_menge_direkt_hinter_dem_kuerzel():
    """AC-1 GIVEN ein Trip-Onset-Alarm mit nicht-konvektivem Ereignis
    (`is_convective=False`, `onset_time="18:00"`, `onset_precip_mm=2.5`)
    WHEN `render_sms(msg)` ueber den Onset-Zweig rendert
    THEN enthaelt der Text exakt das Token `R2.5@18:00` — Kuerzel, Zahl mit
    EINER Nachkommastelle und Uhrzeit ohne Trennzeichen dazwischen.

    RED heute: `OnsetEvent` kennt `onset_precip_mm` nicht (`TypeError`)."""
    sms = _sms(onset_precip_mm=2.5)

    assert "R2.5@18:00" in sms, (
        f"RED: Mengen-Token 'R2.5@18:00' fehlt in der Kurznachricht: {sms!r}"
    )
    assert sms == "Ziel: R2.5@18:00", (
        f"Erwartet 'Ziel: R2.5@18:00' (Kopf unveraendert, Menge im Token), "
        f"bekam {sms!r}"
    )
    assert " R2.5" not in sms.split(": ", 1)[1], (
        f"Im Regen-Fall darf die Zahl NICHT als eigenes Token stehen: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-2 — Gewitter: Zahl als eigenes Token NACH der Zeit, nie hinter `TH`
# ---------------------------------------------------------------------------


def test_ac2_gewitter_onset_traegt_die_menge_als_eigenes_token_nach_der_zeit():
    """AC-2 GIVEN denselben Aufbau wie AC-1, aber konvektiv
    (`is_convective=True`, `onset_time="18:00"`, `onset_precip_mm=2.5`)
    WHEN `render_sms(msg)` ueber denselben Onset-Zweig rendert
    THEN enthaelt der Text exakt `TH@18:00 R2.5` — die Zahl steht als eigenes
    Token NACH dem Zeit-Token, durch ein Leerzeichen getrennt — und hinter
    `TH` selbst steht NIEMALS eine Ziffer (die Position gehoert der Stufe
    L/M/H der Briefing-Grammatik).

    RED heute: `OnsetEvent` kennt `onset_precip_mm` nicht (`TypeError`)."""
    sms = _sms(onset_precip_mm=2.5, is_convective=True,
               intensity_label="Starker Hagel/Gewitter")

    assert "TH@18:00 R2.5" in sms, (
        f"RED: Gewitter-Mengen-Token 'TH@18:00 R2.5' fehlt: {sms!r}"
    )
    assert sms == "Ziel: TH@18:00 R2.5", (
        f"Erwartet 'Ziel: TH@18:00 R2.5', bekam {sms!r}"
    )
    assert "TH2" not in sms and "TH2.5" not in sms, (
        f"Die Stufen-Position hinter 'TH' ist mit einer Menge belegt: {sms!r}"
    )
    treffer = _ZIFFER_HINTER_TH_RE.search(sms)
    assert treffer is None, (
        f"Ziffer unmittelbar hinter 'TH' im Gewitter-Fall — diese Position "
        f"gehoert der Stufe (L/M/H), nicht der Menge: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-4 — ohne belastbare Zahl bleibt die heutige Form (nie `R0.0@`)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("is_convective, kuerzel", [(False, "R"), (True, "TH")])
def test_ac4a_ohne_menge_bleibt_die_heutige_zahlenlose_form(is_convective, kuerzel):
    """AC-4 (a) GIVEN ein `OnsetEvent` mit `onset_precip_mm=None` (keine
    Frames im Fenster ab dem Beginn)
    WHEN `render_sms(msg)` rendert
    THEN bleibt die heutige Form ohne Zahl (`R@18:00` bzw. `TH@18:00`) —
    byte-identisch zur Fassung, die das Feld gar nicht erst uebergibt.

    RED heute: `OnsetEvent` kennt `onset_precip_mm` nicht (`TypeError`)."""
    label = "Starker Hagel/Gewitter" if is_convective else "Mäßiger Regen"
    mit_none = _sms(onset_precip_mm=None, is_convective=is_convective,
                    intensity_label=label)
    ohne_feld = _sms(is_convective=is_convective, intensity_label=label)

    assert mit_none == f"Ziel: {kuerzel}@18:00", (
        f"Ohne Zahl muss die heutige Form stehenbleiben: {mit_none!r}"
    )
    assert mit_none == ohne_feld, (
        "Ein ungesetztes Mengenfeld darf die Kurznachricht nicht anfassen.\n"
        f"  mit None   = {mit_none!r}\n  ohne Feld  = {ohne_feld!r}"
    )
    assert _ZIFFER_HINTER_KUERZEL_RE.search(mit_none) is None, (
        f"Ziffer unmittelbar hinter dem Kuerzel ohne belastbare Zahl: "
        f"{mit_none!r}"
    )


@pytest.mark.parametrize("is_convective, kuerzel", [(False, "R"), (True, "TH")])
def test_ac4b_null_menge_erzeugt_niemals_r0_0(is_convective, kuerzel):
    """AC-4 (b) GIVEN ein `OnsetEvent` mit `onset_precip_mm=0.0` (Menge
    unterhalb der Trockenschwelle)
    WHEN `render_sms(msg)` rendert
    THEN entsteht NIEMALS `R0.0@18:00` — die Anzeige unterscheidet nicht
    zwischen "nicht berechenbar" und "berechnet, aber null".

    RED heute: `OnsetEvent` kennt `onset_precip_mm` nicht (`TypeError`)."""
    label = "Starker Hagel/Gewitter" if is_convective else "Mäßiger Regen"
    sms = _sms(onset_precip_mm=0.0, is_convective=is_convective,
               intensity_label=label)

    assert sms == f"Ziel: {kuerzel}@18:00", (
        f"Eine Null-Menge muss die zahlenlose Form ergeben: {sms!r}"
    )
    assert "0.0" not in sms, f"Null-Menge steht als Zahl in der SMS: {sms!r}"
    assert "R0" not in sms, f"Null-Menge steht als Zahl in der SMS: {sms!r}"


@pytest.mark.parametrize("flag", ["data_unavailable", "throttled"])
def test_ac4c_nowcast_ohne_belastbare_daten_rendert_ohne_zahl(flag):
    """AC-4 (c) GIVEN ein `NowcastResult`, das als `data_unavailable=True`
    bzw. `throttled=True` gekennzeichnet ist und deshalb KEINE belastbare
    Menge traegt (`onset_precip_mm=None`)
    WHEN daraus ueber den Ortsvergleich-Bündelpfad eine Kurznachricht
    entsteht
    THEN steht dort die zahlenlose Form (`R@HH:MM`) — kein `R0.0`, keine
    erfundene Zahl.

    Wanduhrfest: der Buendel-Konstruktor leitet `onset_time` aus
    `datetime.now()` ab, deshalb Struktur- statt Goldstring-Pruefung.

    RED heute: `NowcastResult` kennt `onset_precip_mm` nicht (`TypeError`)."""
    from output.renderers.alert.project import to_multi_location_onset_alert_message
    from services.radar_service import NowcastResult

    nc = NowcastResult(
        onset_minutes=30, intensity_label="Mäßiger Regen", source="radar",
        is_convective=False, onset_precip_mm=None, **{flag: True},
    )
    msg = to_multi_location_onset_alert_message(
        [("Zermatt", nc)], tz=timezone.utc, stand_at="10:00",
    )
    sms = render_sms(msg)

    assert re.search(r"\bR@\d{1,2}:\d{2}", sms), (
        f"Erwartet die zahlenlose Form 'R@HH:MM': {sms!r}"
    )
    assert _ZIFFER_HINTER_KUERZEL_RE.search(sms) is None, (
        f"Ohne belastbare Daten darf keine Zahl am Kuerzel kleben: {sms!r}"
    )
    assert "0.0" not in sms, f"Erfundene Null-Menge in der SMS: {sms!r}"


# ---------------------------------------------------------------------------
# AC-5 — Zahlform: genau eine Nachkommastelle, Punkt, keine Einheit
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("menge, erwartet", [(2.0, "R2.0@18:00"), (12.34, "R12.3@18:00")])
def test_ac5_zahlformat_eine_nachkommastelle_punkt_und_keine_einheit(menge, erwartet):
    """AC-5 GIVEN `onset_precip_mm=2.0` (glatte Zahl) bzw. `12.34` (zwei
    Nachkommastellen)
    WHEN beide ueber `render_sms(msg)` gerendert werden
    THEN erscheint die Zahl in BEIDEN Faellen mit genau EINER Nachkommastelle
    und Punkt als Trennzeichen (`R2.0@…`, `R12.3@…`) und NIEMALS mit Einheit
    ("mm") im Text — identisch zur Briefing-Zahlform aus
    `output.tokens.metrics._fmt_num`.

    RED heute: `OnsetEvent` kennt `onset_precip_mm` nicht (`TypeError`)."""
    sms = _sms(onset_precip_mm=menge)

    assert erwartet in sms, f"RED: erwartete Zahlform {erwartet!r} fehlt: {sms!r}"
    treffer = _MENGEN_TOKEN_RE.search(sms)
    assert treffer is not None, (
        f"Kein 'R<zahl>.<zahl>@HH:MM'-Token in der Kurznachricht: {sms!r}"
    )
    assert len(treffer.group(2)) == 1, (
        f"Die Zahl muss GENAU eine Nachkommastelle tragen: {sms!r}"
    )
    assert "mm" not in sms, f"Einheit 'mm' steht im Kurznachrichten-Text: {sms!r}"
    assert "," not in sms, f"Dezimal-Komma statt Punkt: {sms!r}"


def test_ac5_zahlform_ist_dieselbe_wie_im_briefing():
    """AC-5 (Kopplung) GIVEN denselben Wert `12.34`
    WHEN die Kurznachricht ihn rendert
    THEN traegt sie GENAU die Zeichenfolge, die der Briefing-Zahlformatierer
    `_fmt_num("R", 12.34)` liefert — die beiden Formate duerfen nicht
    auseinanderlaufen (eine eigene Rundungsregel im Alarm-Renderer waere ein
    stiller zweiter Zahlen-Dialekt).

    RED heute: `OnsetEvent` kennt `onset_precip_mm` nicht (`TypeError`)."""
    from output.tokens.metrics import _fmt_num

    sms = _sms(onset_precip_mm=12.34)

    assert f"R{_fmt_num('R', 12.34)}@" in sms, (
        f"Die Kurznachricht weicht von der Briefing-Zahlform "
        f"{_fmt_num('R', 12.34)!r} ab: {sms!r}"
    )
