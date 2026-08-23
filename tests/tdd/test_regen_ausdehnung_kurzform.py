"""TDD RED — Issue #2051 Scheibe S2b: die Kurzform (SMS, Premium-SMS,
Telegram-Kurzstil) traegt das Zonen-Kuerzel `km8-12`.

SPEC: docs/specs/modules/feat_2051_s2b_ausdehnung_kanaele.md — AC-4, AC-5,
AC-6, AC-7, AC-11.

Warum das zaehlt: auf der Huette am Karnischen Hoehenweg kommt NUR die
Premium-SMS an, und die traegt heute keinerlei Ausdehnungsangabe. Alle drei
Kurzkanaele senden denselben `sms_body` — ein Kuerzel hier wirkt auf alle
drei zugleich.

RED-Ursache: `_render_sms_onset` (`render.py:927-996`) kennt kein
Zonen-Token; der Helfer `_sms_onset_extent_suffix` existiert nicht.

Mock-frei: echte `OnsetEvent`/`RainZone`/`AlertMessage`-Objekte durch den
echten Renderer, feste Zeitangaben, keine Wanduhr.
"""
from __future__ import annotations

import inspect
from pathlib import Path

from output.renderers.alert.model import AlertMessage, OnsetEvent
from output.renderers.alert.render import render_sms
from services.rain_extent import RainZone

# Zeitgruppe `R2.5@15:00@16:30` (Spec AC-4): Beginn 15:00, bekanntes Ende
# 16:30 (kein Untergrenzen-Waechter), Menge 2.5 mm, kein Guete-Marker.
_MINIMAL_FIELDS = dict(
    onset_minutes=25, onset_time="15:00", km_from=0.0, km_to=6.0,
    is_convective=False, intensity_label="Mäßiger Regen",
    source_label="Radar (DWD)", location_label="Sillian",
    onset_precip_mm=2.5, event_end_time="16:30",
)

_ZEITGRUPPE = "R2.5@15:00@16:30"

_ZONE_A = RainZone(km_from=8.0, km_to=12.0, onset_minutes=20, event_end_minutes=40)
_ZONE_B = RainZone(km_from=19.0, km_to=21.0, onset_minutes=50, event_end_minutes=70)


def _onset_event(**overrides) -> OnsetEvent:
    fields = dict(_MINIMAL_FIELDS)
    fields.update(overrides)
    return OnsetEvent(**fields)


def _onset_msg(*events: OnsetEvent) -> AlertMessage:
    return AlertMessage(
        trip_short="KHW 403", stand_at="14:35", events=tuple(events),
        source="Radar (DWD)",
    )


def _kurzform_soll(*zonen: RainZone) -> str:
    """Das Zonen-Kuerzel der KURZFORM, ABGELEITET aus den Zonenwerten der
    Fixture (` km8-12,19-21`) — nie als Literal getippt.

    EIN `km`-Praefix vor der ersten Spanne, danach nur noch `X-Y`-Paare,
    komma-getrennt ohne Leerzeichen; ganzzahlig gerundet wie die Langform."""
    return " km" + ",".join(
        f"{int(round(z.km_from))}-{int(round(z.km_to))}" for z in zonen
    )


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): der geprueften Renderer wird RELATIV ZU DIESER
    Testdatei aufgeloest — sonst pruefte ein Worktree-Lauf still die Datei des
    Hauptrepos und lieferte falsches Gruen."""
    from output.renderers.alert import render as render_module

    modul_pfad = Path(inspect.getfile(render_module)).resolve()
    arbeitsbaum = Path(__file__).resolve().parents[2]
    assert modul_pfad.is_relative_to(arbeitsbaum), (
        f"Prueling stammt nicht aus diesem Arbeitsbaum: {modul_pfad}"
    )


# --------------------------------------------------------------------------
# AC-4 — das Kuerzel haengt unmittelbar hinter der VOLLSTAENDIGEN Zeitgruppe,
#        mit genau EINEM Leerzeichen als Fuge.
# --------------------------------------------------------------------------

def test_ac4_zonen_kuerzel_haengt_hinter_der_zeitgruppe():
    """AC-4 GIVEN ein `OnsetEvent` mit `km_measured=True`, einer Zone km 8-12
    und Beginn/Ende, die die Zeitgruppe `R2.5@15:00@16:30` erzeugen
    WHEN `render_sms` mit dem Standardlimit 140 rendert
    THEN lautet der Token-Teil exakt `R2.5@15:00@16:30 km8-12`.

    Der Sollwert wird aus den Zonenwerten der Fixture abgeleitet
    (`_kurzform_soll`); die Vorbedingung darunter haelt fest, dass die
    Fixture wirklich das Beispiel der Spec erzeugt — sonst koennte die
    Ableitung mit dem Pruefling gemeinsam abdriften.

    RED heute: die Kurzform kennt kein Zonen-Token."""
    kuerzel = _kurzform_soll(_ZONE_A)
    assert kuerzel == " km8-12", (
        f"Testvoraussetzung: die Fixture muss das Spec-Beispiel ' km8-12' "
        f"erzeugen, abgeleitet wurde {kuerzel!r}"
    )

    sms = render_sms(
        _onset_msg(_onset_event(km_measured=True, rain_zones=(_ZONE_A,)))
    )

    assert f"{_ZEITGRUPPE}{kuerzel}" in sms, (
        f"AC-4: erwartet {_ZEITGRUPPE + kuerzel!r} als Token-Teil, "
        f"erhalten: {sms!r}"
    )
    assert sms == f"Sillian: {_ZEITGRUPPE}{kuerzel}", (
        f"AC-4: die Kurzform muss aus Kopf, Zeitgruppe und Kuerzel bestehen, "
        f"ohne weitere Zusaetze: {sms!r}"
    )


# --------------------------------------------------------------------------
# AC-5 — zwei Zonen: komma-getrennt, EIN `km`-Praefix, NIE zusammengefasst.
# --------------------------------------------------------------------------

def test_ac5_zwei_zonen_komma_getrennt_ohne_huelle():
    """AC-5 GIVEN denselben Aufbau wie AC-4, aber mit zwei Zonen km 8-12 und
    km 19-21
    WHEN die Kurzform gerendert wird
    THEN lautet das Kuerzel exakt `km8-12,19-21` — ohne Leerzeichen, ohne
    wiederholtes `km`-Praefix — und NIEMALS die zusammengefasste Spanne
    `km8-21`.

    Die Huelle waere eine Aussage ueber das Wetter, die niemand gemessen hat:
    die trockene Strecke zwischen den Zonen erschiene als nass (S2a E2).

    RED heute: die Kurzform kennt kein Zonen-Token."""
    kuerzel = _kurzform_soll(_ZONE_A, _ZONE_B)
    huelle = f"km{int(round(_ZONE_A.km_from))}-{int(round(_ZONE_B.km_to))}"
    assert kuerzel == " km8-12,19-21" and huelle == "km8-21", (
        f"Testvoraussetzung: Fixture muss ' km8-12,19-21' (Huelle 'km8-21') "
        f"erzeugen, abgeleitet wurde {kuerzel!r} / {huelle!r}"
    )

    sms = render_sms(
        _onset_msg(_onset_event(km_measured=True, rain_zones=(_ZONE_A, _ZONE_B)))
    )

    assert kuerzel in sms, (
        f"AC-5: erwartet {kuerzel!r} in der Kurzform: {sms!r}"
    )
    assert huelle not in sms, (
        f"AC-5: die zusammengefasste Huelle {huelle!r} ist verboten: {sms!r}"
    )
    wiederholtes_praefix = " " + ",".join(
        f"km{int(round(z.km_from))}-{int(round(z.km_to))}"
        for z in (_ZONE_A, _ZONE_B)
    )
    assert wiederholtes_praefix not in sms, (
        f"AC-5: das `km`-Praefix darf sich nicht je Spanne wiederholen "
        f"({wiederholtes_praefix!r}): {sms!r}"
    )


# --------------------------------------------------------------------------
# AC-6 — unvermessene Etappe: kein Kuerzel, Text byte-identisch. Mit
#        Positivkontrolle im selben Test (Muster S3-AC-6).
# --------------------------------------------------------------------------

def test_ac6_unvermessene_etappe_ohne_kuerzel_vermessene_mit():
    """AC-6 GIVEN zweimal denselben Aufbau wie AC-4, einmal mit
    `km_measured=False` (unvermessene Etappe) und einmal — bei sonst
    identischer Konstruktion — mit `km_measured=True`
    WHEN beide Texte gerendert werden
    THEN fehlt das Zonen-Kuerzel im ersten Fall vollstaendig (Text
    byte-identisch zum zonenlosen Stand) UND erscheint im zweiten.

    Ein verschobener Wert, gegensaetzliches Ergebnis: ohne den zweiten Fall
    waere die Abwesenheitspruefung trivial wahr (heute traegt die Kurzform
    ueberhaupt kein Kuerzel).

    RED heute: der zweite Fall (Positivkontrolle) faellt aus."""
    kuerzel = _kurzform_soll(_ZONE_A)

    ohne_zonen = render_sms(
        _onset_msg(_onset_event(km_measured=False, rain_zones=()))
    )
    unvermessen = render_sms(
        _onset_msg(_onset_event(km_measured=False, rain_zones=(_ZONE_A,)))
    )
    vermessen = render_sms(
        _onset_msg(_onset_event(km_measured=True, rain_zones=(_ZONE_A,)))
    )

    assert unvermessen == ohne_zonen, (
        "AC-6: auf unvermessener Etappe muss der Text byte-identisch zum "
        f"zonenlosen Stand bleiben.\n  mit Zonen: {unvermessen!r}\n"
        f"  ohne Zonen: {ohne_zonen!r}"
    )
    assert "km" not in unvermessen.removeprefix("Sillian: "), (
        f"AC-6: kein km-Kuerzel auf unvermessener Etappe: {unvermessen!r}"
    )
    assert kuerzel in vermessen, (
        f"AC-6 (Positivkontrolle): bei `km_measured=True` MUSS {kuerzel!r} "
        f"erscheinen — sonst prueft die Abwesenheit oben nichts: {vermessen!r}"
    )


# --------------------------------------------------------------------------
# AC-7 — Rundung, nicht Abschneiden.
# --------------------------------------------------------------------------

def test_ac7_fraktionale_zonengrenzen_werden_gerundet():
    """AC-7 GIVEN eine Zone mit `km_from=7.6`, `km_to=11.4`
    WHEN das Zonen-Kuerzel gebildet wird
    THEN lautet es exakt `km8-11` — ganzzahlig gerundet wie die Langform,
    NICHT abgeschnitten (`km7-11` waere falsch).

    Die Werte sind so gewaehlt, dass Runden und Abschneiden AUSEINANDER-
    LAUFEN — sonst pruefte der Test die Form statt des Werts. Beide Sollwerte
    stehen hier bewusst als Literal: geprueft wird die RUNDUNGSREGEL selbst,
    eine Ableitung ueber `int(round(...))` wuerde den Pruefling spiegeln.

    RED heute: die Kurzform kennt kein Zonen-Token."""
    zone = RainZone(km_from=7.6, km_to=11.4, onset_minutes=20, event_end_minutes=40)

    sms = render_sms(
        _onset_msg(_onset_event(km_measured=True, rain_zones=(zone,)))
    )

    assert "km8-11" in sms, (
        f"AC-7: 7.6/11.4 muessen gerundet als 'km8-11' erscheinen: {sms!r}"
    )
    assert "km7-11" not in sms, (
        f"AC-7: abgeschnitten statt gerundet ('km7-11') ist falsch: {sms!r}"
    )


# --------------------------------------------------------------------------
# AC-11 — Zeichenvorrat: der ASCII-Bindestrich ist GSM-7-Basiszeichensatz.
# --------------------------------------------------------------------------

def _extremfall_msg(*zonen: RainZone) -> AlertMessage:
    """Der kombinierte Extremfall aus AC-9: 30-Zeichen-Ortsname (auf 24
    gekappt), `onset_precip_mm=99.9`, Untergrenzen-Ende und Guete-Marker."""
    ortsname = "Obertilliacher Bergwiesenalm".ljust(30, "x")
    assert len(ortsname) == 30, "Voraussetzung: 30-Zeichen-Ortsname"
    event = OnsetEvent(
        onset_minutes=40, onset_time="18:00", km_from=0.0, km_to=0.0,
        is_convective=True, intensity_label="Starker Regen",
        source_label="Radar (DWD)", location_label=ortsname,
        onset_precip_mm=99.9, event_end_time="23:59",
        event_ongoing_beyond_horizon=True,
        location_sharpness_limit_time="20:00",
        km_measured=True, rain_zones=tuple(zonen),
    )
    return AlertMessage(
        trip_short="Alpen", stand_at="17:20", events=(event,),
        source="Radar (DWD)",
    )


def test_ac11_extremfall_mit_zonen_bleibt_ascii_rein():
    """AC-11 GIVEN den Extremfall aus AC-9 mit gesetztem Zonen-Kuerzel
    WHEN der resultierende Text auf seinen Zeichenvorrat geprueft wird
    THEN ist er vollstaendig ASCII-rein.

    Ein einziges Zeichen ausserhalb von GSM-7 stellte die Nachricht auf UCS-2
    um und halbierte die Kapazitaet von 160 auf 70 Zeichen — die
    Zeichenzahl allein bewiese das Budget dann nicht. Der Bindestrich des
    Zonen-Kuerzels ist GSM-7-BASISzeichen und aendert daran nichts, anders
    als `~` (S3 E6); genau das wird hier nachgewiesen statt angenommen.

    RED heute: das Kuerzel steht gar nicht im Text — die Vorbedingung faellt
    aus."""
    kuerzel = _kurzform_soll(_ZONE_A, _ZONE_B)
    sms = render_sms(_extremfall_msg(_ZONE_A, _ZONE_B), limit=140)

    assert kuerzel in sms, (
        f"Vorbedingung: das Zonen-Kuerzel {kuerzel!r} muss im Text stehen, "
        f"sonst prueft die ASCII-Zusicherung den falschen Text: {sms!r}"
    )
    assert sms.isascii(), f"AC-11: Kurznachricht ist nicht ASCII-rein: {sms!r}"
