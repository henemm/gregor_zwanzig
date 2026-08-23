"""TDD RED — Issue #2078: Kopf vor dem Zeit-Token kappen statt den fertigen
Text hart zu schneiden.

SPEC: docs/specs/modules/fix_2078_onset_sms_zeit_token_schnitt.md (AC-1..AC-9)

`_render_sms_onset` und `_render_sms_onset_shift_only` bauen den Kopf
(Ortsname) heute OHNE Laengenbegrenzung und schneiden danach den fertigen
Text stur bei `limit` ab. Bei einem ausreichend langen Ortsnamen trifft
dieser Endschnitt mitten ins Zeit-Token (`Sa0:40` -> `Sa0:4`) -- eine
inhaltlich FALSCHE statt einer fehlenden Uhrzeit. Der Fix kappt den Kopf VOR
dem Zusammensetzen auf 24 Zeichen (Muster `_render_sms_corridor_only`).

RED-Ursache: `head` traegt heute keinen `[:24]`-Zuschnitt. Bei den Faellen
mit langem Ortsnamen (AC-1/2/3/5/6/7/9) ist der Kopf im Ist-Zustand LAENGER
als 24 Zeichen -- die Laengen- und Gleichheits-Assertions schlagen rot.
AC-4 (kurzer Ortsname) und AC-8 (harter Endschnitt bei kleinem `limit`)
pruefen bestehendes, vom Fix UNBERUEHRTES Verhalten und sind bewusst als
Regressionsschutz bereits heute gruen (Muster `test_alert_sms_onset_
zeitpunkt.py::test_ac10_...`, "Nicht-Beruehrungs-Nachweis").

Mock-frei: echte `OnsetEvent`/`OnsetShiftEvent`/`AlertMessage`-Objekte durch
den echten Renderer. Alle Zeiten sind FEST gesetzt (keine Wanduhr).
"""
from __future__ import annotations

import re

from output.renderers.alert.model import AlertMessage, OnsetEvent, OnsetShiftEvent
from output.renderers.alert.render import render_sms

_ZEITPUNKT_TOKEN_RE = re.compile(r"\b(TH|R)@(\d{1,2}):(\d{2})\b")
_ZEITPUNKT_MIT_ENDE_RE = re.compile(
    r"\b(TH|R)@(\d{1,2}):(\d{2})@(\d{1,2}):(\d{2})\b"
)
_NOW_MIT_ENDE_RE = re.compile(r"\bnow@(\d{1,2}):(\d{2})\b")


def _onset_event(**kw) -> OnsetEvent:
    """Ein Trip-Radar-Onset-Ereignis mit festen Feldern (keine Wanduhr) --
    dieselben Default-Werte wie `test_alert_sms_onset_zeitpunkt.py::
    _onset_event`, damit der Goldstring 'km 8-8: TH@15:40' aus AC-4 der dort
    bereits bewiesene ist."""
    fields = dict(
        onset_minutes=8, onset_time="15:40", km_from=8.0, km_to=8.0,
        is_convective=True, intensity_label="Gewitter mit Hagel",
        source_label="Radar (ICON-D2)",
    )
    fields.update(kw)
    return OnsetEvent(**fields)


def _onset_msg(event: OnsetEvent, *, trip_short: str = "KHW 403",
               source: str = "radar") -> AlertMessage:
    """`source is not None` routet `render_sms` in den Onset-Zweig."""
    return AlertMessage(
        trip_short=trip_short, stand_at="10:00", events=(event,), source=source,
    )


def _kopf(sms: str) -> str:
    """Der Kopf-Anteil vor dem ': ' -- die Ortsangabe der Kurznachricht."""
    assert ": " in sms, f"Kurznachricht hat keinen '<Ort>: <Token>'-Aufbau: {sms!r}"
    return sms.split(": ", 1)[0]


def _langer_name(n: int = 30) -> str:
    """ASCII-Ortsname, garantiert laenger als die 24-Zeichen-Kappgrenze."""
    name = "Obertilliacher Bergwiesenalm".ljust(n, "x")
    assert len(name) == n and n > 24, "Vorbedingung: Name muss die Grenze ueberschreiten"
    return name


# ---------------------------------------------------------------------------
# AC-1 -- dritter Kopf-Zweig (km-Rueckfall ohne Segment/location_label)
# ---------------------------------------------------------------------------


def test_ac1_dritter_kopf_zweig_km_rueckfall_wird_auf_24_zeichen_gekappt():
    """AC-1: Given ein Trip-Onset-Alarm, dessen aufgeloester Ortsname (dritter
    Kopf-Zweig, `_location_of`-km-Rueckfall) nach ASCII-Faltung laenger als
    24 Zeichen ist / When `render_sms` rendert / Then ist der Kopf auf 24
    Zeichen gekappt UND das Zeit-Token `TH@15:40` steht vollstaendig."""
    km_from, km_to = 11234567890.0, 98765432109.0
    voller_kopf = f"km {int(round(km_from))}-{int(round(km_to))}"
    assert len(voller_kopf) > 24, "Vorbedingung: ungekappter Kopf muss die Grenze beruehren"

    event = _onset_event(km_from=km_from, km_to=km_to, segment_id=None)
    sms = render_sms(_onset_msg(event))
    kopf = _kopf(sms)

    assert len(kopf) <= 24, f"Kopf ist laenger als 24 Zeichen: {kopf!r}"
    assert kopf == voller_kopf[:24], (
        f"Kopf muss der auf 24 Zeichen gekappte km-Rueckfall sein, "
        f"erwartet {voller_kopf[:24]!r}, bekam {kopf!r}"
    )
    treffer = _ZEITPUNKT_TOKEN_RE.search(sms)
    assert treffer and treffer.group(0) == "TH@15:40", (
        f"Vollstaendiges Zeit-Token 'TH@15:40' fehlt oder ist beschaedigt: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-2 -- Ortsvergleich mit genau einem Ort (Kopf aus trip_short)
# ---------------------------------------------------------------------------


def test_ac2_compare_radar_kopf_aus_trip_short_wird_auf_24_zeichen_gekappt():
    """AC-2: Given einen Ortsvergleich-Alarm mit genau einem Ort
    (`source=COMPARE_RADAR_SOURCE`, `location_label is None`, langer
    `trip_short`) / When `render_sms` rendert / Then ist der Kopf auf 24
    Zeichen gekappt und das Zeit-Token bleibt vollstaendig."""
    from output.renderers.alert.project import COMPARE_RADAR_SOURCE

    langer_name = _langer_name()
    msg = AlertMessage(
        trip_short=langer_name, stand_at="10:00", events=(_onset_event(),),
        source=COMPARE_RADAR_SOURCE,
    )
    sms = render_sms(msg)
    kopf = _kopf(sms)

    assert len(kopf) <= 24, f"Kopf ist laenger als 24 Zeichen: {kopf!r}"
    assert kopf == langer_name[:24], (
        f"Kopf muss der auf 24 Zeichen gekappte trip_short sein, "
        f"erwartet {langer_name[:24]!r}, bekam {kopf!r}"
    )
    treffer = _ZEITPUNKT_TOKEN_RE.search(sms)
    assert treffer and treffer.group(0) == "TH@15:40", (
        f"Vollstaendiges Zeit-Token 'TH@15:40' fehlt oder ist beschaedigt: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-3 -- gebuendelter Ortsvergleich (location_label gesetzt)
# ---------------------------------------------------------------------------


def test_ac3_location_label_kopf_wird_auf_24_zeichen_gekappt():
    """AC-3: Given einen gebuendelten Ortsvergleich-Alarm
    (`OnsetEvent.location_label` gesetzt, laenger als 24 Zeichen) / When
    `render_sms` rendert / Then ist der Kopf gekappt und das Zeit-Token
    vollstaendig."""
    langer_name = _langer_name()
    sms = render_sms(_onset_msg(_onset_event(location_label=langer_name)))
    kopf = _kopf(sms)

    assert len(kopf) <= 24, f"Kopf ist laenger als 24 Zeichen: {kopf!r}"
    assert kopf == langer_name[:24], (
        f"Kopf muss der auf 24 Zeichen gekappte location_label sein, "
        f"erwartet {langer_name[:24]!r}, bekam {kopf!r}"
    )
    treffer = _ZEITPUNKT_TOKEN_RE.search(sms)
    assert treffer and treffer.group(0) == "TH@15:40", (
        f"Vollstaendiges Zeit-Token 'TH@15:40' fehlt oder ist beschaedigt: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-4 -- Regressionsschutz: kurzer Ortsname bleibt byte-identisch
# ---------------------------------------------------------------------------


def test_ac4_kurzer_ortsname_bleibt_byte_identisch_zum_bisherigen_verhalten():
    """AC-4 (Regressionsschutz): Given einen kurzen, alltagstypischen
    Ortsnamen (<=24 Zeichen) / When `render_sms` rendert / Then bleibt die
    Ausgabe byte-identisch zum bekannten Goldstring aus `test_alert_sms_
    onset_zeitpunkt.py::test_ac1_...` -- die neue Kappgrenze darf im Alltag
    nicht sichtbar werden. Bewusst bereits heute gruen (Nicht-Beruehrungs-
    Nachweis, unbetroffen vom Fix)."""
    sms = render_sms(_onset_msg(_onset_event()))

    assert sms == "km 8-8: TH@15:40", (
        f"Erwartet unveraendert 'km 8-8: TH@15:40', bekam {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-5 -- Onset-Shift-Zweig
# ---------------------------------------------------------------------------


def test_ac5_onset_shift_kopf_wird_auf_24_zeichen_gekappt():
    """AC-5: Given einen `_render_sms_onset_shift_only`-Alarm mit einem
    Ortsnamen laenger als 24 Zeichen / When `render_sms` ueber den
    Onset-Shift-Zweig rendert / Then ist der Kopf gekappt UND das
    Verschiebungs-Token (`to_time` + `shift_text`) steht vollstaendig."""
    langer_name = _langer_name()
    shift = OnsetShiftEvent(
        metric_id="precipitation", from_time="17:00", to_time="15:00",
        shift_text="2 h früher", km_from=8.0, km_to=8.0,
    )
    msg = AlertMessage(
        trip_short="KHW 403", stand_at="10:00", events=(),
        location_label=langer_name, onset_shift_events=(shift,),
    )
    sms = render_sms(msg)
    kopf = _kopf(sms)

    assert len(kopf) <= 24, f"Kopf ist laenger als 24 Zeichen: {kopf!r}"
    assert kopf == langer_name[:24], (
        f"Kopf muss der auf 24 Zeichen gekappte location_label sein, "
        f"erwartet {langer_name[:24]!r}, bekam {kopf!r}"
    )
    assert f"{shift.to_time} {shift.shift_text}" in sms, (
        f"Verschiebungs-Token (to_time + shift_text) muss vollstaendig "
        f"erhalten bleiben: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-6 -- laufender Nowcast-Alarm (already_running)
# ---------------------------------------------------------------------------


def test_ac6_already_running_kopf_wird_auf_24_zeichen_gekappt_now_token_bleibt_ganz():
    """AC-6: Given einen laufenden Nowcast-Alarm (`already_running=True`) mit
    einem Ortsnamen laenger als 24 Zeichen / When `render_sms` rendert / Then
    ist der Kopf gekappt und das `now`-Token samt Ende-Grammatik bleibt
    vollstaendig erhalten."""
    langer_name = _langer_name()
    event = _onset_event(
        location_label=langer_name, already_running=True, event_end_time="20:00",
    )
    sms = render_sms(_onset_msg(event))
    kopf = _kopf(sms)

    assert len(kopf) <= 24, f"Kopf ist laenger als 24 Zeichen: {kopf!r}"
    assert kopf == langer_name[:24], (
        f"Kopf muss der auf 24 Zeichen gekappte location_label sein, "
        f"erwartet {langer_name[:24]!r}, bekam {kopf!r}"
    )
    treffer = _NOW_MIT_ENDE_RE.search(sms)
    assert treffer and treffer.group(0) == "now@20:00", (
        f"'now'-Token samt Ende-Grammatik muss vollstaendig erhalten bleiben "
        f"(kein abgeschnittenes 'no'/'now@2'): {sms!r}"
    )
    assert sms.endswith("TH now@20:00"), (
        f"Erwartet Endung 'TH now@20:00', bekam {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-7 -- zwei Zeit-Token (Beginn UND Ende-Suffix)
# ---------------------------------------------------------------------------


def test_ac7_beide_zeit_token_bleiben_vollstaendig_bei_langem_kopf():
    """AC-7: Given ein Onset-Ereignis mit ZWEI Zeit-Token (Beginn UND
    Ende-Suffix, `event_end_time` gesetzt) und einem Ortsnamen laenger als 24
    Zeichen / When `render_sms` rendert / Then bleiben BEIDE Zeit-Token
    vollstaendig erhalten -- genau der Fall, der den Bug laut Issue #2078
    erst real gemacht hat."""
    langer_name = _langer_name()
    event = _onset_event(location_label=langer_name, event_end_time="20:00")
    sms = render_sms(_onset_msg(event))
    kopf = _kopf(sms)

    assert len(kopf) <= 24, f"Kopf ist laenger als 24 Zeichen: {kopf!r}"
    assert kopf == langer_name[:24], (
        f"Kopf muss der auf 24 Zeichen gekappte location_label sein, "
        f"erwartet {langer_name[:24]!r}, bekam {kopf!r}"
    )
    treffer = _ZEITPUNKT_MIT_ENDE_RE.search(sms)
    assert treffer and treffer.group(0) == "TH@15:40@20:00", (
        f"Beide Zeit-Token (Beginn UND Ende-Suffix) muessen vollstaendig "
        f"erhalten bleiben, kein abgeschnittenes Suffix am Textende: {sms!r}"
    )
    assert sms.endswith("TH@15:40@20:00"), (
        f"Erwartet Endung 'TH@15:40@20:00', bekam {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-8 -- Regressionsschutz: harter Endschnitt bleibt Sicherheitsnetz
# ---------------------------------------------------------------------------


def test_ac8_harter_endschnitt_bleibt_sicherheitsnetz_fuer_render_sms_onset():
    """AC-8 (Regressionsschutz): Given einen absurd kleinen `limit`-Wert /
    When `_render_sms_onset` direkt rendert / Then greift weiterhin der
    harte Endschnitt `body[:limit]` -- die Ausgabe ist nie laenger als
    `limit`. Bewusst bereits heute gruen: der harte Endschnitt selbst ist
    vom Fix unveraendert."""
    from output.renderers.alert.render import _render_sms_onset

    msg = _onset_msg(_onset_event(location_label=_langer_name()))
    ergebnis = _render_sms_onset(msg, limit=10)

    assert len(ergebnis) <= 10, (
        f"Harter Endschnitt (Sicherheitsnetz) muss weiterhin greifen, "
        f"bekam {len(ergebnis)} Zeichen: {ergebnis!r}"
    )


def test_ac8_harter_endschnitt_bleibt_sicherheitsnetz_fuer_render_sms_onset_shift_only():
    """AC-8 (Regressionsschutz), zweite Aufrufstelle: dasselbe fuer
    `_render_sms_onset_shift_only`."""
    from output.renderers.alert.render import _render_sms_onset_shift_only

    shift = OnsetShiftEvent(
        metric_id="precipitation", from_time="17:00", to_time="15:00",
        shift_text="2 h früher", km_from=8.0, km_to=8.0,
    )
    msg = AlertMessage(
        trip_short="KHW 403", stand_at="10:00", events=(),
        location_label=_langer_name(), onset_shift_events=(shift,),
    )
    ergebnis = _render_sms_onset_shift_only(msg, limit=10)

    assert len(ergebnis) <= 10, (
        f"Harter Endschnitt (Sicherheitsnetz) muss weiterhin greifen, "
        f"bekam {len(ergebnis)} Zeichen: {ergebnis!r}"
    )


# ---------------------------------------------------------------------------
# AC-9 -- Reihenfolge: Piktogramm/GSM-7-Faltung VOR der 24-Zeichen-Kappung
# ---------------------------------------------------------------------------


def test_ac9_piktogramm_entfernung_und_ascii_faltung_laufen_vor_der_kappung():
    """AC-9: Given einen Ortsnamen mit Piktogramm gefolgt von ausreichend
    vielen Zeichen, sodass ein Zaehlen VOR der Faltung eine andere
    Kapp-Stelle traefe als ein Zaehlen NACH der Faltung / When `render_sms`
    rendert / Then zaehlt die Kappung die sichtbaren ASCII-Zeichen des
    bereits gefalteten Texts -- kein Piktogramm-Rest im Kopf."""
    roh = "\U0001F3C1 " + "A" * 30  # Piktogramm + Leerzeichen + 30x 'A'
    gefaltet = "A" * 30
    assert len(gefaltet) > 24, "Vorbedingung: gefalteter Text muss die Grenze beruehren"

    sms = render_sms(_onset_msg(_onset_event(location_label=roh)))
    kopf = _kopf(sms)

    assert kopf == gefaltet[:24], (
        f"Kappung muss NACH Piktogramm-Entfernung/ASCII-Faltung zaehlen, "
        f"erwartet {gefaltet[:24]!r} (24x 'A'), bekam {kopf!r}"
    )
    assert "\U0001F3C1" not in sms, f"Piktogramm-Rest in der Kurznachricht: {sms!r}"
    assert sms.isascii(), f"Kurznachricht ist nicht ASCII-rein: {sms!r}"
