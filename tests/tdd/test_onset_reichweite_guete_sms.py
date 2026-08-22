"""TDD RED — Issue #2051 S3: die Kurzform (SMS/Premium-SMS/Telegram-Kurzstil)
traegt NUR die Guete als einzelnes `?`-Zeichen, nie die Reichweite.

SPEC: docs/specs/modules/feat_2051_s3_reichweite_und_guete.md — AC-11,
AC-12, AC-13.

Fachlicher Kern (E6): Grundauswahl ist das Maximum, der Kanal darf nur
abwaehlen. Die Kurzform hat ein hartes Budget (140 GSM-7-Zeichen) und
traegt deshalb NUR die Guete -- als EIN Zeichen `?` unmittelbar hinter dem
betroffenen Zeit-Token (`R2.5@15:00?`). Die Reichweite entfaellt hier
vollstaendig; im Untergrenzen-Fall (S1, `>@`) transportiert dieses Token die
Reichweite ohnehin schon.

`?` statt `~`: `~` gehoert zur GSM-7-Extension-Tabelle (2 Septets) und wird
vom Transport hart auf `-` gefaltet (`_ASCII_EXTENSION_REPLACEMENTS`,
render.py:1497) -- ein Bindestrich hinter einer Uhrzeit laese sich wie ein
abgeschnittener Zeitbereich. `?` steht im GSM-7-BASISzeichensatz und
ueberlebt die Faltung unveraendert.

Drei Zusicherungen:
  * AC-11 -- Guete-Fall: genau EIN `?` unmittelbar hinter dem Zeit-Token,
    Zeichenbudget haelt auch im Extremfall.
  * AC-12 -- Guete-Fall MIT gesetzter Reichweite: die Kurzform traegt KEIN
    drittes Zeit-Token fuer die Reichweite.
  * AC-13 -- ohne Guete-Fall: der Text bleibt BYTE-IDENTISCH zum Stand vor
    dieser Spec.

RED heute: `OnsetEvent` kennt `location_sharpness_limit_time`/
`source_reach_time` nicht -> `TypeError` bereits bei der Konstruktion.

Mock-frei: echte `OnsetEvent`/`AlertMessage`-Objekte durch den echten
`render_sms`."""
from __future__ import annotations

import inspect
import re
from pathlib import Path

from output.renderers.alert.model import AlertMessage, OnsetEvent
from output.renderers.alert.render import render_sms

_UNSET = object()


def _onset_event(
    *, event_end_time: object = _UNSET, event_ongoing_beyond_horizon: object = _UNSET,
    location_sharpness_limit_time: object = _UNSET, source_reach_time: object = _UNSET,
    onset_precip_mm: object = _UNSET, **kw,
) -> OnsetEvent:
    """Ein Trip-Radar-Onset-Ereignis mit festen Feldern. Die neuen S3-Felder
    werden NUR uebergeben, wenn ein Aufrufer sie ausdruecklich setzt (Muster
    `test_onset_ende_textstellen.py`)."""
    fields = dict(
        onset_minutes=30, onset_time="18:00", km_from=8.0, km_to=8.0,
        is_convective=False, intensity_label="Mäßiger Regen",
        source_label="Radar (DWD)", segment_id="Ziel",
    )
    fields.update(kw)
    if event_end_time is not _UNSET:
        fields["event_end_time"] = event_end_time
    if event_ongoing_beyond_horizon is not _UNSET:
        fields["event_ongoing_beyond_horizon"] = event_ongoing_beyond_horizon
    if location_sharpness_limit_time is not _UNSET:
        fields["location_sharpness_limit_time"] = location_sharpness_limit_time
    if source_reach_time is not _UNSET:
        fields["source_reach_time"] = source_reach_time
    if onset_precip_mm is not _UNSET:
        fields["onset_precip_mm"] = onset_precip_mm
    return OnsetEvent(**fields)


def _onset_msg(*events: OnsetEvent) -> AlertMessage:
    return AlertMessage(
        trip_short="KHW 403", stand_at="17:30", events=tuple(events),
        source="Radar (DWD)",
    )


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): der gepruefte Renderer wird RELATIV ZU DIESER
    Testdatei aufgeloest."""
    from output.renderers.alert import render as render_module

    modul_pfad = Path(inspect.getfile(render_module)).resolve()
    arbeitsbaum = Path(__file__).resolve().parents[2]
    assert modul_pfad.is_relative_to(arbeitsbaum), (
        f"Prueling stammt nicht aus diesem Arbeitsbaum: {modul_pfad}"
    )


# ---------------------------------------------------------------------------
# AC-11 -- Guete-Fall: genau EIN '?' hinter dem Zeit-Token
# ---------------------------------------------------------------------------


def test_ac11_guete_zeichen_steht_unmittelbar_hinter_dem_zeit_token():
    """AC-11 GIVEN einen Onset-Alarm im Guete-Fall
    (`location_sharpness_limit_time="19:00"`), Beginn `18:00`, Menge `2.5`
    WHEN `render_sms(msg)` gerendert wird
    THEN traegt der Text genau EIN Zeichen `?` unmittelbar hinter dem
    Zeit-Token (`R2.5@18:00?`).

    RED heute: `OnsetEvent` kennt `location_sharpness_limit_time` nicht
    (`TypeError`)."""
    sms = render_sms(_onset_msg(_onset_event(
        onset_precip_mm=2.5, location_sharpness_limit_time="19:00",
    )))

    assert "R2.5@18:00?" in sms, (
        f"RED: das Guete-Zeichen steht nicht unmittelbar hinter dem "
        f"Zeit-Token: {sms!r}"
    )
    assert sms.count("?") == 1, (
        f"Es darf genau EIN Guete-Zeichen im Text stehen: {sms!r}"
    )


def test_ac11_zeichenbudget_haelt_auch_im_extremfall():
    """AC-11 (Zeichenbudget) GIVEN einen 30 Zeichen langen Ortsnamen,
    `onset_precip_mm=99.9`, ein kombiniertes Untergrenzen- UND Guete-Token
    WHEN `render_sms(msg, limit=140)` rendert
    THEN bleibt der Text unter 140 GSM-7-Zeichen, OHNE dass der harte
    Schnitt `body[:limit]` greift.

    RED heute: `OnsetEvent` kennt die neuen Felder nicht (`TypeError`)."""
    ortsname = "Obertilliacher Bergwiesenalm".ljust(30, "x")
    assert len(ortsname) == 30, "Voraussetzung: 30-Zeichen-Ortsname"

    event = OnsetEvent(
        onset_minutes=40, onset_time="18:00", km_from=0.0, km_to=0.0,
        is_convective=False, intensity_label="Starker Regen",
        source_label="Radar (DWD)", location_label=ortsname,
        onset_precip_mm=99.9, event_end_time="23:59",
        event_ongoing_beyond_horizon=True,
        location_sharpness_limit_time="19:00",
    )
    sms = render_sms(_onset_msg(event), limit=140)

    assert len(sms) <= 140, (
        f"RED: {len(sms)} Zeichen ueberschreiten das Render-Limit: {sms!r}"
    )
    assert sms.count("?") == 1, (
        f"Genau EIN Guete-Zeichen auch im Extremfall erwartet: {sms!r}"
    )
    assert sms.isascii(), f"Kurznachricht ist nicht ASCII-rein: {sms!r}"


# ---------------------------------------------------------------------------
# AC-12 -- Guete-Fall MIT Reichweite: kein drittes Zeit-Token
# ---------------------------------------------------------------------------


def test_ac12_kurzform_zeigt_kein_drittes_zeit_token_fuer_die_reichweite():
    """AC-12 GIVEN denselben Guete-Fall wie AC-11, ZUSAETZLICH mit gesetzter
    Reichweite (`source_reach_time="21:00"`)
    WHEN die Kurzform gerendert wird
    THEN enthaelt sie KEIN drittes Zeit-Token fuer die Reichweite -- die
    Anzahl der `@HH:MM`-Zeit-Token bleibt bei maximal zwei (Beginn, Ende),
    die Reichweite bleibt abgewaehlt (E6).

    RED heute: `OnsetEvent` kennt die neuen Felder nicht (`TypeError`)."""
    sms = render_sms(_onset_msg(_onset_event(
        onset_precip_mm=2.5, event_end_time="20:00",
        location_sharpness_limit_time="19:00", source_reach_time="21:00",
    )))

    zeit_token = re.findall(r"@\d{1,2}:\d{2}", sms)
    assert len(zeit_token) <= 2, (
        f"RED/E6: die Kurzform darf hoechstens zwei Zeit-Token tragen "
        f"(Beginn, Ende), kein drittes fuer die Reichweite: {sms!r} "
        f"({zeit_token!r})"
    )
    assert "21:00" not in sms, (
        f"Die Reichweiten-Uhrzeit darf in der Kurzform nicht auftauchen: "
        f"{sms!r}"
    )
    assert sms.count("?") == 1, (
        f"RED: das Guete-Zeichen muss trotz gesetzter Reichweite stehen: "
        f"{sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-13 -- ohne Guete-Fall: byte-identisch zum Stand vor dieser Spec
# ---------------------------------------------------------------------------


def test_ac13_ohne_guete_fall_bleibt_die_kurzform_byte_identisch():
    """AC-13 GIVEN einen Onset-Alarm ohne Guete-Fall UND ohne
    Reichweiten-relevante Besonderheit
    WHEN `render_sms(msg)` einmal MIT den neuen Feldern explizit auf `None`
    und einmal GANZ OHNE sie gerendert wird
    THEN sind beide Texte byte-identisch -- kein haengendes `?`, keine leere
    Anhaengsel-Stelle.

    RED heute: der Aufruf mit den neuen Feldern (auch mit `None`) scheitert
    an `TypeError`, weil `OnsetEvent` sie nicht kennt."""
    mit_none = render_sms(_onset_msg(_onset_event(
        onset_precip_mm=2.5,
        location_sharpness_limit_time=None, source_reach_time=None,
    )))
    ohne_felder = render_sms(_onset_msg(_onset_event(onset_precip_mm=2.5)))

    assert mit_none == ohne_felder, (
        "Ungesetzte neue Felder duerfen die Kurznachricht nicht anfassen.\n"
        f"  mit None   = {mit_none!r}\n  ohne Felder = {ohne_felder!r}"
    )
    assert "?" not in mit_none, (
        f"Ohne Guete-Fall darf kein Guete-Zeichen entstehen: {mit_none!r}"
    )
    assert not mit_none.rstrip().endswith("@"), (
        f"Leeres Zeit-Token am Textende: {mit_none!r}"
    )
