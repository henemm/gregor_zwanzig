"""Vier reine Alert-Renderer (Issue #917, Formate aus #914).

render_subject · render_email · render_telegram · render_sms — generisch aus
der Metrik-Registry. Unicode-Pfeile NUR Email/Telegram; SMS rein ASCII/GSM-7.
"""
from __future__ import annotations

import unicodedata
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from app.metric_catalog import (
    format_metric_value, get_alert_label, get_decimals, get_label_for_field,
    get_metric, get_sms_code,
)
from app.thunder_scale import thunder_label
from i18n import Lang, fmt_weekday, t, tn
from output.metric_format import _THUNDER_JE_ORDINAL
from output.renderers.email.design_tokens import (
    FONT_DATA, FONT_UI, G_ACCENT, G_DANGER, G_INK, G_INK_MUTED, G_SUCCESS,
)
from output.tokens.metrics import LEVELS, _fmt_num
from utils.ascii_fold import fold_ascii

from .model import (
    AlertEvent, AlertMessage, OnsetEvent, OnsetShiftEvent,
    arrow, km_span, over_thr, severity, side_label,
)
from .hours import row_parts
from .project import COMPARE_RADAR_SOURCE
from .segments import _renderable_segment_ids, format_alert_location

if TYPE_CHECKING:  # pragma: no cover — nur fuer Typpruefung
    # Muster `model.py`: der Renderer haengt sich zur LAUFZEIT nicht an die
    # Service-Schicht, nur die Typpruefung kennt die Zonen-Datenklasse.
    from services.rain_extent import RainZone


def _sorted(msg: AlertMessage) -> list[AlertEvent]:
    # Über-Schwelle-Events zuerst (severity-absteigend), unter-Schwelle gedämpft zuletzt.
    # Issue #982: Innerhalb der unter-Schwelle-Gruppe nach BETRAG (abs(severity))
    # statt Vorzeichen — das am weitesten von der Schwelle entfernte Event zuerst.
    return sorted(
        msg.events,
        key=lambda e: (not over_thr(e), -severity(e) if over_thr(e) else -abs(severity(e))),
    )


_HANDLED_UNITS = {"m", "km", "hPa", "%", "km/h", "°C", "mm"}


def _thunder_word(value: float, lang: Lang = "de") -> str | None:
    """Uebersetzt einen thunder-Ordinalwert (POSITION auf der Gewitter-
    Leiter) in sein deutsches Wort (Issue #1948 S6). Rundung `round(v, 0)`
    (kaufmaennisch-gerade Bankersrundung), exakt wie bisher (AC-17). Werte
    ausserhalb 0-3 (nur ueber den Vorschau-Pfad erreichbar) liefern `None`
    -- der Aufrufer faellt dann auf die bisherige Zahlform zurueck, NIEMALS
    auf 'kein' (AC-13, `_THUNDER_JE_ORDINAL.get(4)` -> `None`)."""
    ordinal = int(round(value, 0))
    level = _THUNDER_JE_ORDINAL.get(ordinal)
    return thunder_label(level, lang=lang) if level is not None else None


def _stufe_unit(value: float, lang: Lang = "de") -> str:
    """Deutsches Einheitswort fuer einen Stufen-ABSTAND (threshold, |Δ| einer
    Stufenmetrik) -- Singular bei genau 1, sonst Plural (Issue #1948 S6,
    AC-6-Waechter: ein Abstand ist NIE ein Stufenwort)."""
    return tn("alarm.einheit.stufe", abs(round(value)), lang)


def _val_raw(e: AlertEvent, value: float, lang: Lang = "de") -> str:
    """Wert MIT Einheit via Katalog, OHNE Stufenwort-Weiche -- gemeinsamer
    Zahlen-Fallback fuer `_val()` (Positionen) und `_val_delta()` (Abstaende,
    Issue #1948 S6).

    format_metric_value() formatiert nur die o.g. Einheiten mit Suffix; fuer
    alle anderen (z.B. J/kg bei CAPE) baut dieser Renderer selbst einen
    ganzzahligen/dezimalen Fallback MIT Einheit — bewusst lokal gehalten,
    damit format_metric_value()'s geteilter else-Zweig fuer andere Aufrufer
    (z.B. format_change_line) unveraendert bleibt (Issue #952 Finding F001).
    """
    unit = get_metric(e.metric_id).unit
    rounded = round(value, get_decimals(e.metric_id))
    if unit in _HANDLED_UNITS:
        return format_metric_value(unit, rounded, lang=lang)
    formatted = str(int(rounded)) if float(rounded).is_integer() else str(rounded)
    return f"{formatted} {unit}".strip()


def _val(e: AlertEvent, value: float, lang: Lang = "de") -> str:
    """Wert MIT Einheit fuer eine POSITION (value_from/value_to) —
    Email/Telegram/Betreff. Bei Stufenmetriken (`is_level`)
    das deutsche Stufenwort statt der Ordinalzahl (Issue #1948 S6, Leit-
    unterscheidung Positionen vs. Abstaende); Werte ausserhalb 0-3 fallen auf
    die bisherige Zahlform zurueck (AC-13)."""
    if _is_level_metric(e.metric_id):
        word = _thunder_word(value, lang)
        if word is not None:
            return word
    return _val_raw(e, value, lang)


def _val_delta(e: AlertEvent, value: float, lang: Lang = "de") -> str:
    """Wert MIT Einheit fuer einen ABSTAND (threshold, |Δ|) -- bei
    Stufenmetriken NIE ein Wort, sondern Zahl + 'Stufe(n)' (Issue #1948 S6,
    AC-6-Waechter: 'Schwelle leicht' ist eine sachlich falsche Aussage)."""
    if _is_level_metric(e.metric_id):
        rounded = round(value, get_decimals(e.metric_id))
        formatted = str(int(rounded)) if float(rounded).is_integer() else str(rounded)
        return f"{formatted} {_stufe_unit(rounded, lang)}"
    return _val_raw(e, value, lang)


def _num_raw(value: float, decimals: int, lang: Lang = "de") -> str:
    """Zahl OHNE Einheit, OHNE Stufenwort-Weiche -- gemeinsamer Zahlen-
    Fallback fuer `_num()` (Positionen) und `_num_delta()` (Abstaende).

    Integer-Display bei glattem Rundungsergebnis (kein ',0'-Rauschen), sonst
    1 Nachkommastelle mit Komma -- Tausender-Punkt bleibt in beiden Zweigen
    erhalten (Issue #978 Finding F002). Baut die _format_de_thousand()-Logik
    aus metric_catalog lokal nach statt sie zu importieren, damit die
    geteilte Katalogfunktion fuer andere Aufrufer (format_change_line)
    unveraendert bleibt (Issue #952 Finding F001, analog zur Begruendung bei
    _val_raw() oben).
    """
    rounded = round(value, decimals)
    if lang == "en":  # Issue #2667: Dezimalpunkt, Tausender-Komma (ADR-0104 Nr. 6)
        if float(rounded).is_integer():
            return f"{int(rounded):,}"
        return f"{rounded:,.{decimals}f}"
    if float(rounded).is_integer():
        n = int(rounded)
        return f"{n:,}".replace(",", ".") if abs(n) >= 1000 else str(n)
    int_part, _, frac_part = f"{rounded:,.{decimals}f}".partition(".")
    return f"{int_part.replace(',', '.')},{frac_part}"


def _num(e: AlertEvent, value: float, lang: Lang = "de") -> str:
    """Zahl OHNE Einheit fuer eine POSITION in der Multi-Metrik-Zeile (Issue
    #978) -- bei Stufenmetriken das deutsche Stufenwort statt der Ordinal-
    zahl (Issue #1948 S6, AC-3/AC-4), sonst wie bisher."""
    if _is_level_metric(e.metric_id):
        word = _thunder_word(value, lang)
        if word is not None:
            return word
    return _num_raw(value, get_decimals(e.metric_id), lang)


def _num_delta(e: AlertEvent, value: float, lang: Lang = "de") -> str:
    """Zahl OHNE Einheit fuer einen ABSTAND (threshold, |Δ|) in der Multi-
    Metrik-Zeile -- NIE ein Wort, auch nicht bei Stufenmetriken (Issue #1948
    S6, AC-6-Waechter)."""
    return _num_raw(value, get_decimals(e.metric_id), lang)


def _unit_suffix(e: AlertEvent) -> str:
    """Einheiten-Suffix fuer Betreff/Telegram (Issue #1935/#1779 E5): immer
    angehaengt (nicht mehr nur bei '%') -- dieselbe Regel wie im E-Mail-Zweig
    (`_val()`). '%' klebt ohne Leerzeichen am Wert, alle anderen Einheiten mit
    einem Leerzeichen davor (Katalog-Konvention, z.B. '80 km/h')."""
    unit = _unit_display(e)
    if not unit:
        return ""
    return unit if unit == "%" else f" {unit}"


def _unit_display(e: AlertEvent) -> str:
    """Einheit fuer die Multi-Metrik-Zeile (Issue #978) -- immer aus dem Katalog.

    Frueher hing hier ein Sonderfall fuer 'thunder', der ein '%' anhaengte
    (Design-Vorlage zu #978, Vorschlaege.html:208/220-233/281). Er ist mit
    Issue #1703 Scheibe 1 ersatzlos entfallen: 'thunder' traegt
    alert_metrics={"max": "thunder_level"} (metric_catalog.py:340), der
    Alarmwert ist also eine STUFE (0-3), keine Prozentzahl. PO-Entscheidung
    #1585 (2026-08-07, genau zwei Gewitter-Metriken: 'thunder' = Staerke,
    'thunder_probability' = Wahrscheinlichkeit) hat die Vorlage abgeloest;
    die Abloesung wurde am 2026-08-11 vom PO bestaetigt. Der Einzel-Event-Pfad
    (:47, :365) las ohnehin schon die Katalog-Einheit ("").
    """
    return get_metric(e.metric_id).unit


def _code(e: AlertEvent) -> str:
    return get_sms_code(e.metric_id) or e.metric_id


def _is_level_metric(metric_id: str) -> bool:
    """Stufenleiter statt Messzahl (Issue #1948 S3). Unbekannte Kennungen
    bleiben numerisch -- derselbe Nachsichtigkeits-Vertrag wie in `_code()`."""
    try:
        return get_metric(metric_id).is_level
    except KeyError:
        return False


def _label(e: AlertEvent, lang: Lang = "de") -> str:
    """Kürzel für E-Mail/Telegram/Betreff (#914-Registry, Issue #952); Issue
    #2667: Alarm-Kurzform des Registers in ``lang`` (``alert_label_for``)."""
    return get_alert_label(e.metric_id, lang)


def _deviation_label(e: AlertEvent, lang: Lang = "de") -> str:
    """Kuerzel der Abweichungs-Alarmzeile -- STUFENABHAENGIG (Issue #2176).

    Bleiben VORHER- UND NACHHER-Wert auf "leicht" oder darunter, traegt die Zeile keine Ereignisbehauptung mehr
    -- "leicht" misst eine Luftmasse. Sobald einer der beiden MED/HIGH
    erreicht, bleibt es bei "Gewitter" (Spec AC-6) -- deshalb der Blick auf
    BEIDE Werte, nicht nur auf `value_to`.

    `_label()` selbst bleibt levelunabhaengig -- es ist weiterhin der Metrikname fuer MED/HIGH, fuer die
    Beginn-Verschiebungs-Ereignisse und fuer jede andere Groesse.
    """
    if _is_level_metric(e.metric_id):
        from app.models import ThunderLevel
        from output.metric_format import thunder_ordinal

        low = thunder_ordinal(ThunderLevel.LOW)
        if max(int(round(e.value_from, 0)), int(round(e.value_to, 0))) <= low:
            return t("alarm.abweichung.luftmasse", lang)
    return _label(e, lang)


def _location_of(events, location_label: str | None = None, *, lang: Lang = "de") -> str:
    """Ortsangabe einer Ereignismenge (Issue #1744 A1) — Betreff, Mailkoerper
    und Telegram-Langform holen sie ALLE hier, damit eine Mail nicht zwei
    Ortssprachen spricht (AC-6). Die Reihenfolge location_label -> Segment ->
    km steht in `segments.format_alert_location` und NUR dort (AC-3).

    Issue #1169: gesetztes `location_label` (Compare-Punkt-Alert) ersetzt die
    sinnlose km-Spanne eines Punktes ohne km-Kontext; der Trip-Pfad setzt das
    Feld nie."""
    a, b = km_span(events)
    # Issue #2036: die km-Spanne verdraengt die Segmentnummer nur, wenn sie
    # bei JEDEM beteiligten Ereignis aus echter Wegstrecke stammt -- eine
    # gemischte Menge waere eine Ortsangabe, die zur Haelfte geraten ist.
    measured = bool(events) and all(
        getattr(e, "km_measured", False) for e in events
    )
    return format_alert_location(
        location_label, [e.segment_id for e in events], a, b,
        km_measured=measured, lang=lang,
    )


def _km_str(msg: AlertMessage, lang: Lang = "de") -> str:
    return _location_of(msg.events, msg.location_label, lang=lang)


def _stage_prefix(events) -> str:
    """Issue #2122: die EINE Stelle, an der das Etappen-Praefix der
    Alarm-Kurzform entsteht -- alle vier Kopf-Zweige stellen ihr Ergebnis
    voran (`_render_sms_onset_shift_only`, `_render_sms_onset`,
    `_render_sms_body`).

    Fehlt bei IRGENDEINEM Ereignis die Etappen-Nummer, entfaellt das Praefix
    GANZ -- eine Teilangabe waere unehrlich (dieselbe Logik wie
    `segments._renderable_segment_ids`, AC-8). Mehr als drei verschiedene
    Etappen entfallen ebenfalls (Known Limitation, AC-7): eine vierstellige
    Aufzaehlung kostet mehr Zeichenbudget, als sie an Zuordnung bringt.

    Schreibweise: eine Etappe -> "S5 "; benachbarte -> "S5-6 "; nicht
    benachbarte -> "S5,7 "."""
    numbers: list[int] = []
    for e in events:
        n = getattr(e, "stage_number", None)
        if n is None:
            return ""
        numbers.append(n)
    if not numbers:
        return ""
    distinct = sorted(set(numbers))
    if len(distinct) > 3:
        return ""
    if len(distinct) == 1:
        return f"S{distinct[0]} "
    if distinct[-1] - distinct[0] + 1 == len(distinct):
        return f"S{distinct[0]}-{distinct[-1]} "
    return f"S{','.join(str(n) for n in distinct)} "


def _time_with_day(
    hhmm: str, day_offset: int = 0, is_past: bool = False,
    *, past_key: str = "alarm.zeit.seit", lang: Lang = "de",
) -> str:
    """Issue #2020 Scheibe 2: DER gemeinsame Tageswort-Baustein — typunabhaengig,
    einer statt zweier.

    Loest den Versatz EXAKT auf, nicht ueber seinen Wahrheitswert: `-1` ist
    "gestern", nicht "morgen" (genau daran scheiterte `_onset_time_label()`,
    im Nowcast-Vorwaertsfenster unerreichbar, im Abweichungsalarm der
    Normalfall). Notation ist die Hausform aus `utils.timezone.
    format_reference_at`, die die Fusszeile schon heute spricht.

    Am Versandtag (`day_offset == 0`) entfaellt das Tageswort ersatzlos; ein
    bereits verstrichener Zeitpunkt bekommt stattdessen `past_word`. Das Wort
    ist Sache der Aufrufstelle, weil beide Ereignisarten es verschieden
    sprechen: ein Beginn laeuft "seit 15:00", eine Spitze "war 17:00".
    Issue #2667: das Wort ist ein Katalogschluessel (``past_key``).
    """
    if day_offset == -1:
        tag = t("alarm.zeit.gestern", lang, zeit=hhmm)
    elif day_offset < -1:
        tag = t("alarm.zeit.vor_tagen", lang, n=-day_offset, zeit=hhmm)
    elif day_offset == 1:
        tag = t("alarm.zeit.morgen", lang, zeit=hhmm)
    elif day_offset > 1:
        tag = t("alarm.zeit.in_tagen", lang, n=day_offset, zeit=hhmm)
    else:
        tag = hhmm
    return t(past_key, lang, zeit=tag) if is_past else tag


def _when_suffix(e: AlertEvent, lang: Lang = "de") -> str:
    """Issue #2020 Scheibe 2: der Bedeutungs-Zusatz einer Ereignis-Zeile.

    Eine nackte Uhrzeit sagt nicht, WELCHE Groesse sie meint. Fuer
    Niederschlags-Summen-Ereignisse (`remaining_mm` gesetzt) traegt die Zeile
    stattdessen die Blickrichtung — die Uhrzeiten stehen dort in den
    Restmengen-Zeilen, wo sie hingehoeren; fuer alle uebrigen Metriken bleibt
    es beim Zeitpunkt des staerksten Werts ("Restmenge" ergibt fuer Wind oder
    Temperatur keine Aussage).
    """
    if e.remaining_mm is not None:
        return " · " + t("alarm.abweichung.mehr_regen", lang)
    if not e.occurred_at:
        return ""
    return " · " + t("alarm.abweichung.staerkste_stunde", lang, zeit=_time_with_day(
        e.occurred_at, e.occurred_day_offset, e.occurred_is_past,
        past_key="alarm.zeit.war", lang=lang,
    ))


def _mm(value: float) -> str:
    """Millimeter als glatte Zahl -- die Restmenge ist eine Groessenordnung,
    keine Messung auf die Nachkommastelle (deshalb steht "~" davor)."""
    return f"{max(0.0, value):.0f}"


def _precip_rows(e: AlertEvent, lang: Lang = "de") -> list[tuple[str, str]]:
    """Issue #2020 Scheibe 2: die beiden Zeilen, die den Alarm nach vorn
    drehen — was bis jetzt gefallen ist, und was ab jetzt noch kommt.

    Das bereits Gefallene wird als `value_to - remaining_mm` abgeleitet und
    NICHT zweitgerechnet: zwei getrennt summierte Teilmengen driften
    auseinander, sobald eine von beiden eine Stunde anders zaehlt.

    Ohne Endzeit kommt nichts mehr. Diese Meldung wird ausdruecklich
    GESCHRIEBEN und nicht unterdrueckt (PO-Entscheid): mehr Regen als
    angekuendigt aendert die Lage auch rueckblickend (nasse Ausruestung,
    Wegzustand, Baeche) -- verschwiegen wuerde nur, wie weit die Aussage
    reicht, deshalb nennt sie ihr Fensterende.
    """
    # KEIN `or 0.0`: beide Aufrufstellen betreten diesen Block nur unter
    # `e.remaining_mm is not None`, und ein Rueckfall auf 0.0 wuerde genau
    # die Unterscheidung einebnen, die `_precip_remaining()` aufmacht
    # (unbestimmbar vs. nachweislich nichts mehr).
    gefallen = e.value_to - e.remaining_mm
    ab_jetzt = t("alarm.niederschlag.ab_jetzt", lang)
    rows = [(
        t("alarm.niederschlag.bis_jetzt", lang),
        t("alarm.niederschlag.gefallen", lang, mm=_mm(gefallen), angekuendigt=_mm(e.value_from)),
    )]
    if e.remaining_until_time:
        bis = _time_with_day(e.remaining_until_time, e.remaining_until_day_offset, lang=lang)
        rows.append((ab_jetzt, t("alarm.niederschlag.noch", lang, mm=_mm(e.remaining_mm), zeit=bis)))
    elif e.window_end_time:
        ende = _time_with_day(e.window_end_time, e.window_end_day_offset, lang=lang)
        rows.append((ab_jetzt, t("alarm.niederschlag.fensterende", lang, zeit=ende)))
    else:
        rows.append((ab_jetzt, t("alarm.niederschlag.kein_weiterer", lang)))
    return rows


def _where_when(e: AlertEvent, location_label: str | None = None, *, lang: Lang = "de") -> str:
    """Ort + Bedeutung/Uhrzeit EINES Ereignisses (Issue #1861).

    Issue #2020 Scheibe 2: `location_label` ist NEU und defaultet -- der
    Multi-Event-Zweig ruft weiterhin ohne ihn (er fuehrt den Ortsnamen bereits
    als `loc_prefix`), der Einzel-Datenblock reicht ihn durch, damit beide
    Zweige denselben Zeit-Baustein benutzen statt zweier Kopien.
    """
    return _location_of((e,), location_label, lang=lang) + _when_suffix(e, lang)


def _per_event_where_when(evs) -> bool:
    """Darf der Multi-Event-Zweig je Ereignis einen Ort-/Zeit-Zusatz tragen?

    Nur wenn JEDES Ereignis eine verwertbare Segment-Kennung hat (Issue #1744
    AC-7, "alles oder nichts"): traegt eines keine, nennt die Mail eine
    Teilliste und verschweigt eine tatsaechlich betroffene Etappe. Der
    Compare-Buendelpfad (`to_multi_point_alert_message`) setzt `segment_id`
    nie und faellt damit hier heraus (#1170-Invariante).
    """
    return bool(_renderable_segment_ids([e.segment_id for e in evs]))


def _km_str_onset(e: OnsetEvent, lang: Lang = "de") -> str:
    # Bewusst OHNE `location_label`: `_render_telegram_onset` liest auch im
    # gebuendelten Mehr-Orte-Fall nur `events[0]` (Nebenbefund im Kontext-
    # Dokument) — mit Ortsnamen stuende dort statt "km 0–0" der Name des
    # ERSTEN Ortes, und der Ortsvergleich soll unveraendert bleiben (AC-4).
    return _location_of((e,), lang=lang)


# --- Hagel-Zusaetze (Issue #2205) -------------------------------------------

def _hail_note_suffix(e, lang: Lang = "de") -> str:
    """Issue #2205: bestehende Hagelaussage (`format_hail_note`) als Zusatz
    ` · Hagel: ja` -- leer bei `None`/`False` (byte-identisch zum Bestand)."""
    from output.metric_format import format_hail_note

    note = format_hail_note(getattr(e, "hail_flag", None), lang=lang)
    return f" · {note}" if note else ""


def _sms_hail_suffix(e) -> str:
    """Issue #2205: bestehender SMS-Suffix `+HL` NUR bei bestaetigtem Hagel."""
    from output.tokens.builder import FORECAST_TH_HAIL_SUFFIX

    return FORECAST_TH_HAIL_SUFFIX if getattr(e, "hail_flag", None) is True else ""


# --- Beginn-Verschiebung (Issue #1468, ADR-0013: eigener Render-Vertrag --
# NIE durch _val()/_num(), sonst stuende "15 h" statt "15:00" im Text) -------

def _onset_shift_where(oe: OnsetShiftEvent, lang: Lang = "de") -> str:
    return format_alert_location(
        oe.location_label, [oe.segment_id], oe.km_from, oe.km_to,
        km_measured=getattr(oe, "km_measured", False),  # Issue #2036
        lang=lang,
    )


def _shift_text(oe: OnsetShiftEvent, lang: Lang = "de") -> str:
    """Issue #2667: Verschiebungswort der Langform in ``lang``. ``shift_text``
    bleibt der deutsche Text der Kurzform (SMS unveraendert, PO 2026-10-31)."""
    if lang == "de" or getattr(oe, "shift_seconds", None) is None:
        return oe.shift_text
    from .project import _onset_shift_text

    return _onset_shift_text(oe.shift_seconds, lang=lang)


def _onset_shift_to(oe: OnsetShiftEvent, lang: Lang = "de") -> str:
    """Issue #2020 Scheibe 2: die NEUE Beginn-Uhrzeit mit Tagesbezug und
    Vergangenheits-Ausweis. EINE Stelle fuer alle drei Ausgabewege (Klartext,
    HTML-Zeile, Telegram) -- sonst schriebe die Mail "seit 15:00" und die
    HTML-Tabelle daneben weiterhin ein bevorstehend klingendes "15:00"."""
    return _time_with_day(oe.to_time, oe.to_day_offset, oe.to_is_past, lang=lang)


def _onset_shift_label(oe: OnsetShiftEvent, lang: Lang = "de") -> str:
    return t("alarm.beginn.label", lang, label=_label(oe, lang))


def _onset_shift_line(oe: OnsetShiftEvent, lang: Lang = "de") -> str:
    """Eine Zeile Klartext: Groesse, alte und neue Uhrzeit, Richtungswort."""
    return (
        f"{_onset_shift_label(oe, lang)}: {oe.from_time} → {_onset_shift_to(oe, lang)} "
        f"({_shift_text(oe, lang)} · {_onset_shift_where(oe, lang)})"
    )


def _onset_shift_row(oe: OnsetShiftEvent, first: bool, lang: Lang = "de") -> str:
    """HTML-Zeile einer Beginn-Verschiebung (eine Bauform fuer beide Mails)."""
    return _datarow_html(
        f"{_onset_shift_label(oe, lang)} · {_onset_shift_where(oe, lang)}",
        f"{oe.from_time} → {_onset_shift_to(oe, lang)} ({_shift_text(oe, lang)})",
        G_DANGER, first,
    )


def _onset_shift_location(msg: AlertMessage) -> str:
    """Ortsangabe der Beginn-Ereignisse -- dieselbe Aufloesung wie ueberall
    sonst (`segments.format_alert_location`), damit eine Mail nicht zwei
    Ortssprachen spricht (Issue #1744 AC-6)."""
    evs = msg.onset_shift_events
    return format_alert_location(
        msg.location_label, [oe.segment_id for oe in evs],
        min(oe.km_from for oe in evs), max(oe.km_to for oe in evs),
        # Issue #2036: alles-oder-nichts wie in `_location_of`.
        km_measured=all(getattr(oe, "km_measured", False) for oe in evs),
    )


def _onset_shift_h1(msg: AlertMessage, lang: Lang = "de") -> str:
    n = len(msg.onset_shift_events)
    if n == 1:
        return t("alarm.beginn.verschiebt", lang, label=_label(msg.onset_shift_events[0], lang))
    return t("alarm.beginn.mehrere", lang, n=n)


def _sms_onset_shift_token(oe: OnsetShiftEvent) -> str:
    """Kurznachricht-Token: Kuerzel + neue Uhrzeit + Verschiebung im Klartext.

    Die Richtung MUSS als Wort mit -- ein Vorzeichen an einer Uhrzeit ist auf
    einer Kurznachricht nicht entzifferbar, und die Verschiebung ist genau die
    Aussage, um derentwillen die Meldung verschickt wird.
    """
    return f"{_code(oe)}{oe.to_time} {oe.shift_text}"


def _render_email_onset_shift_only(msg: AlertMessage, lang: Lang = "de") -> tuple[str, str]:
    """Reine Beginn-Verschiebung ohne Wert-Aenderungs-Anteil -- Bauform 1:1
    wie die Wert-Aenderungs-Mail (Issue #1444 S1)."""
    h1 = _onset_shift_h1(msg, lang)
    footer = t("alarm.mail.stand", lang, stand=msg.stand_at)
    plain = "\n".join(
        [h1, "", *[_onset_shift_line(oe, lang) for oe in msg.onset_shift_events], "", footer]
    )
    rows = [
        _onset_shift_row(oe, i == 0, lang)
        for i, oe in enumerate(msg.onset_shift_events)
    ]
    html = (
        "<html><body style=\"font-family:" + FONT_UI + ";color:" + G_INK + ";\">"
        f"<h1 style=\"margin:0 0 12px;font-family:{FONT_UI};color:{G_INK};\">{_esc(h1)}</h1>"
        f"<div style=\"border-bottom:1px solid #d8d5c9;\">{''.join(rows)}</div>"
        f"<p style=\"color:{G_INK_MUTED};margin-top:16px;font-family:{FONT_UI};\">{_esc(footer)}</p>"
        "</body></html>"
    )
    return _with_origin(html, plain, "deviation-alert", "Open-Meteo", lang=lang)


def _render_sms_onset_shift_only(msg: AlertMessage, limit: int) -> str:
    prefix = _stage_prefix(msg.onset_shift_events)  # Issue #2122
    head = f"{prefix}{_ascii_alert_location(_onset_shift_location(msg))[:24]}: "
    body = head + " ".join(
        _sms_onset_shift_token(oe) for oe in msg.onset_shift_events
    )
    return body if len(body) <= limit else body[:limit]


def _onset_kind(e: OnsetEvent, lang: Lang = "de") -> str:
    """Ereigniswort der Langform: Gewitter oder Regen (Issue #2667)."""
    key = "alarm.radar.intensitaet.gewitter" if e.is_convective else "alarm.radar.intensitaet.regen"
    return t(key, lang)


def _intensity(e: OnsetEvent, lang: Lang = "de") -> str:
    """Angezeigte Intensitaet; ``intensity_label`` bleibt der deutsche
    Vergleichsschluessel (alert_urgency, rain_extent), Issue #2667."""
    from services import radar_service as radar_service_mod

    return radar_service_mod.intensity_text(e.intensity_label, lang)


def _onset_suffixes(e: OnsetEvent, lang: Lang = "de") -> str:
    """Die additiven Langform-Angaben hinter Beginn bzw. Zeitpunkt -- in
    Betreff, E-Mail und Telegram dieselbe Kette (#2051, #2050 S4b-2)."""
    return (
        f"{_onset_end_suffix(e, lang)}{_onset_reach_suffix(e, lang)}"
        f"{_onset_sharpness_suffix(e, lang)}{_onset_extent_suffix(e, lang)}"
        f"{_onset_gap_suffix(e, lang)}{_onset_convective_suffix(e, lang)}"
    )


def _render_subject_onset(msg: AlertMessage, lang: Lang = "de") -> str:
    # Issue #1041 Slice 1a: Sammel-Betreff nur bei MEHR ALS EINEM Event
    # (Bündel-Alarm); Ein-Ort-Fall bleibt byte-identisch (AC-2/AC-5).
    if len(msg.events) > 1:
        return f"[{msg.trip_short}] {t('alarm.regen.buendel', lang, n=len(msg.events))}"
    e = msg.events[0]
    label = _onset_kind(e, lang)
    km = _km_str_onset(e, lang)
    # Issue #2051 S1: das Ende additiv HINTER der Beginn-Angabe -- ohne
    # behauptbares Ende bleibt der Betreff byte-identisch (AC-19).
    # Issue #2051 S2b: die Ausdehnung als LETZTES Element derselben Kette --
    # ohne Zonen bzw. auf unvermessener Etappe bleibt der Betreff
    # byte-identisch (AC-1).
    # Issue #2050 S4b-2: die beiden Kennzeichnungen als LETZTE Glieder
    # derselben Kette -- ohne Ausfall bzw. ohne Messluecke bleibt der
    # Betreff byte-identisch (AC-5/AC-13).
    return f"[{msg.trip_short}] {km} · {label} {_onset_wann_kopf(e, lang)}{_onset_suffixes(e, lang)}"


def _distinct_source_labels(msg: AlertMessage) -> str:
    """Distinct `source_label`-Werte der Bündel-Events, dedupliziert in
    stabiler (erster-Vorkommen-)Reihenfolge, ", "-verbunden (Issue #1041
    Fix-Loop, Finding F003). Analog zum Single-Pfad-Zugriff `e.source_label`
    (render.py `_render_email_onset`)."""
    seen: list[str] = []
    for e in msg.events:
        if e.source_label not in seen:
            seen.append(e.source_label)
    return ", ".join(seen)


def _onset_time_label(e: OnsetEvent, lang: Lang = "de") -> str:
    """Issue #2009: eindeutiger Klartext-Tagesbezug fuer den Onset-Zeitpunkt.

    `onset_time` ist reines "HH:MM" ohne Datum -- bei einem Onset, der ueber
    Mitternacht rutscht, ist "00:23" sonst mehrdeutig (heute Nacht oder in
    ueber 23 Stunden?). Additiv: bei `onset_day_offset == 0` (Normalfall)
    byte-identisch zu `e.onset_time`.

    Issue #2020 Scheibe 2: loest den Versatz ueber den GEMEINSAMEN Baustein
    `_time_with_day()` auf statt ueber den Wahrheitswert -- vorher wurde jeder
    Versatz ungleich null zu "morgen", auch `-1`. `OnsetEvent` kennt kein
    Vergangenheits-Kennzeichen (Radar blickt nach vorn), daher `is_past=False`.
    """
    return _time_with_day(e.onset_time, e.onset_day_offset, lang=lang)


_WOCHE = [date(2026, 10, 26) + timedelta(days=i) for i in range(7)]  # Mo..So


def _weekday_short(kuerzel: str | None, lang: Lang = "de") -> str | None:
    """Das Modell traegt das deutsche Kuerzel (SMS unveraendert, PO-Korrektur
    2026-10-31); die Langform zeigt es in ``lang`` (Issue #2667)."""
    if lang == "de" or not kuerzel:
        return kuerzel
    return {fmt_weekday(d, "de"): fmt_weekday(d, lang) for d in _WOCHE}.get(kuerzel, kuerzel)


def _onset_wann_kopf(e: OnsetEvent, lang: Lang = "de") -> str:
    """Kopfzeilen-Form: "in 8 Min" -- oder "laeuft bereits" (Issue #2050 S2b).

    EINE Weiche fuer Betreff, E-Mail-H1/-Buendelzeile und Telegram-Kopf: die
    vier Stellen sagten denselben Satz in vier Kopien, und genau so entstand
    B-1 an vier Stellen gleichzeitig. Die Ende-Angabe haengt unveraendert
    ueber `_onset_end_suffix()` dahinter."""
    if getattr(e, "already_running", False):
        return t("alarm.regen.laeuft", lang)
    # Issue #2261 (A-1, B-2): jenseits der Guete-Grenze ist "in 170 Min"
    # nicht lesbar — dann die Uhrzeit mit Tagesbezug in der Form des
    # SMS-Bausteins (`_sms_onset_time`, kein neues Format). Grenze ueber die
    # Modulreferenz (Drift-Schutz, Muster `project.location_sharpness_display`).
    from services import radar_service as radar_service_mod

    onset = e.onset_minutes
    if onset is not None and onset > radar_service_mod.LOCATION_SHARPNESS_LIMIT_MIN:
        return t("alarm.zeit.ab", lang, zeit=_sms_onset_time(
            e.onset_time, getattr(e, "onset_day_offset", 0),
            _weekday_short(getattr(e, "onset_weekday", None), lang),
        ))
    return t("alarm.zeit.in_minuten", lang, min=onset)


def _onset_wann_zeile(e: OnsetEvent, *, ab: bool = False, lang: Lang = "de") -> str:
    """Detailzeilen-Form: der ZEITPUNKT -- oder "laeuft bereits" (#2050 S2b).

    Getrennt von `_onset_wann_kopf`, weil die Detailzeile den ZEITPUNKT nennt
    und die Kopfzeile die RESTZEIT; im Laufend-Fall fallen beide zusammen.

    `ab` gehoert der Aufrufstelle: die E-Mail schreibt "ab 15:40", die
    Telegram-Langform nennt die Uhrzeit nackt ("15:40"). Ein hier fest
    eingebautes "ab " hat genau diesen Unterschied eingeebnet und
    `test_alert_sms_onset_zeitpunkt::test_ac10` rot gemacht -- im
    Laufend-Fall entfaellt das Praefix mit der Uhrzeit zusammen."""
    if getattr(e, "already_running", False):
        return t("alarm.regen.laeuft", lang)
    zeit = _onset_time_label(e, lang)
    return t("alarm.zeit.ab", lang, zeit=zeit) if ab else zeit


def _onset_end_suffix(e: OnsetEvent, lang: Lang = "de") -> str:
    """Issue #2051 S1: Langform-Ende-Angabe als anhaengbares Stueck oder LEER,
    wenn es gar kein Ende gibt (`event_end_time is None` -- kein Beginn
    erkannt, keine Frames; dann faellt die Angabe ersatzlos weg).

    ZWEI Formen, entschieden allein am R4-Waechter
    `event_ongoing_beyond_horizon` (Spec v1.1, PO-Entscheid 2026-08-22):

      * Waechter NICHT gesetzt -> ` · letzter Regen gegen HH:MM`. Die Quelle
        hat den Trockenuebergang beobachtet, das Ende ist bekannt.
      * Waechter gesetzt -> ` · Regen mindestens bis HH:MM`. Die Zeitreihe
        bzw. der 180-Min-Horizont ist ausgegangen, waehrend es noch regnete:
        die Zahl ist eine BELEGTE Untergrenze, aber kein bekanntes Ende.

    Die beiden Saetze sagen Gegensaetzliches ("hoert um HH:MM auf" vs. "hoert
    bis HH:MM nicht auf"). Sie entstehen deshalb hier in EINEM Ausdruck mit
    genau einer Weiche -- zwei getrennte Zweige, die je einen ganzen Satz
    bauen, koennten unbemerkt beide dieselbe Form schreiben (AC-20).

    Der Tagesbezug wird eigenstaendig aus `event_end_day_offset` gebildet und
    NICHT vom Beginn kopiert: Beginn 23:50 (Versatz 0) und Ende 00:40
    (Versatz 1) liegen an verschiedenen Kalendertagen. Aufgeloest ueber
    DENSELBEN gemeinsamen Baustein `_time_with_day()`, den #2020 Scheibe 2
    eingefuehrt hat -- `_onset_time_label` (o.) selbst bleibt unangetastet
    (Zusage an `fix-2020-zeitangaben-wortlaut`).

    Die Fuge ` · ` gehoert bewusst zum Rueckgabewert: alle drei Langform-
    Stellen (Betreff, E-Mail, Telegram) reihen ihre Angaben mit diesem
    Trenner, und so bleibt der Bestandstext ohne Ende ohne haengendes
    Trennzeichen."""
    ende = getattr(e, "event_end_time", None)
    if not ende:
        return ""
    ende = _time_with_day(ende, getattr(e, "event_end_day_offset", 0), lang=lang)
    if getattr(e, "event_ongoing_beyond_horizon", False):
        return " · " + t("alarm.regen.mindestens_bis", lang, zeit=ende)
    return " · " + t("alarm.regen.letzter", lang, zeit=ende)


def _onset_reach_suffix(e: OnsetEvent, lang: Lang = "de") -> str:
    """Issue #2051 S3: Langform-Reichweiten-Angabe als anhaengbares Stueck
    oder LEER. `source_reach_time` ist bereits `None`, wenn keine
    Reichweite bekannt ist ODER `event_ongoing_beyond_horizon` gesetzt ist
    (E5 -- die S1-Untergrenzenform traegt die Reichweiten-Aussage bereits
    implizit) -- die Entscheidung faellt in `project.source_reach_display`,
    hier nur noch ein `None`-Check (Muster `_onset_end_suffix`)."""
    reach = getattr(e, "source_reach_time", None)
    if not reach:
        return ""
    reach = _time_with_day(reach, getattr(e, "source_reach_day_offset", 0), lang=lang)
    return " · " + t("alarm.regen.reichweite", lang, zeit=reach)


def _onset_sharpness_suffix(e: OnsetEvent, lang: Lang = "de") -> str:
    """Issue #2051 S3: Langform-Guete-Angabe als anhaengbares Stueck oder
    LEER. `location_sharpness_limit_time` ist bereits `None`, wenn weder
    Beginn noch Ende jenseits der Grenze liegen (E4) -- Entscheidung faellt
    in `project.location_sharpness_display`, hier nur noch ein
    `None`-Check (keine zweite Schwellpruefung, Muster AC-20)."""
    limit = getattr(e, "location_sharpness_limit_time", None)
    if not limit:
        return ""
    limit = _time_with_day(
        limit, getattr(e, "location_sharpness_limit_day_offset", 0), lang=lang,
    )
    return " · " + t("alarm.regen.unscharf", lang, zeit=limit)


def _onset_extent_suffix(e: OnsetEvent, lang: Lang = "de") -> str:
    """Issue #2051 S2a: Langform-Ausdehnungs-Angabe als anhaengbares Stueck
    oder LEER (Muster `_onset_end_suffix`).

    Leer in ZWEI Faellen:

    * keine Zonen (`rain_zones` leer) — die Mehrpunkt-Abfrage hat keine
      zusammenhaengend nasse Strecke gefunden, oder der Pfad setzt das Feld
      gar nicht (Ortsvergleich, AC-15);
    * unvermessene Etappe (`km_measured` aus, AC-8) — die km-Lage der Zonen
      stammt dann aus geschaetzter Kilometrierung und waere glaubwuerdig
      aussehender Unsinn (dieselbe Regel wie #2036 fuer die Ortsangabe). Die
      Beschriftung solcher Etappen ueber Wegpunktnamen ist S2b.

    Mehrere Zonen bleiben GETRENNT aufgezaehlt (`km 2-4, km 9-11`) — eine
    zusammengefasste Huelle wuerde die trockene Strecke dazwischen als nass
    ausweisen (AC-10, E2). Rundung und ASCII-Bindestrich wie die gemessene
    km-Spanne in `segments.format_alert_location`.
    """
    zonen = getattr(e, "rain_zones", ())
    if not zonen or not getattr(e, "km_measured", False):
        return ""
    spannen = ", ".join(
        f"km {int(round(z.km_from))}-{int(round(z.km_to))}" for z in zonen
    )
    return " · " + t("alarm.regen.nass", lang, spannen=spannen)


def _onset_convective_suffix(e: OnsetEvent, lang: Lang = "de") -> str:
    """Issue #2050 S4b-2: Langform-Hinweis auf die AUSGEFALLENE
    Gewitterpruefung als anhaengbares Stueck oder LEER (Muster
    `_onset_sharpness_suffix`).

    Ohne ihn beschriftet der Text das Ereignis als "Regen", obwohl niemand
    geprueft hat, ob es ein Gewitter war -- "geprueft, kein Gewitter" und
    "nicht geprueft" waeren im Text ununterscheidbar. Der Zusatz nennt nur den
    Sachverhalt, er leitet keine Handlung ab.

    `getattr` mit Default `True`: eine Bestandslage ohne das Feld gilt als
    geprueft und bleibt stumm (AC-8)."""
    if getattr(e, "convective_checked", True):
        return ""
    return " · " + t("alarm.regen.ungeprueft", lang)


def _onset_gap_suffix(e: OnsetEvent, lang: Lang = "de") -> str:
    """Issue #2050 S4b-2: Langform-Hinweis auf die unvollstaendig gemessene
    Ausdehnung als anhaengbares Stueck oder LEER.

    DIESELBE Sichtbarkeitsregel wie `_onset_extent_suffix` (Zonen vorhanden UND
    vermessene Etappe) -- ohne gezeigte Ausdehnung haette der Hinweis keine
    Bezugsgroesse und haenge in der Luft (AC-15).

    Leere `gap_km` heisst NICHT "alles gemessen": das Feld entsteht auch leer,
    sobald die Mehrpunkt-Abfrage lief (`trip_alert._messluecken_felder`), und
    fehlt bei Altdaten ganz. Beide Faelle bleiben stumm (AC-13/AC-14)."""
    zonen = getattr(e, "rain_zones", ())
    if not zonen or not getattr(e, "km_measured", False):
        return ""
    if not getattr(e, "gap_km", ()):
        return ""
    return " · " + t("alarm.regen.luecke", lang)


def _cooldown_text(msg: AlertMessage, lang: Lang = "de") -> str:
    """Issue #2018 Teil C: der Cooldown haelt nur die jeweils EIGENE Quelle
    zurueck -- der Zusatz sagt das. Er steht in DERSELBEN Zeile wie der
    bestehende Satz (Leerzeichen als Fuge): die zeilen-/blockweisen
    Reihenfolge-Waechter des Mailkoerpers klassifizieren per Substring, eine
    eigene Zeile wuerde sie kippen. Leer ohne ``cooldown_display``. Issue
    #2667: EIN Baustein fuer Einzel- und Buendel-Mail."""
    if not msg.cooldown_display:
        return ""
    return t("alarm.regen.cooldown", lang, dauer=msg.cooldown_display,
             praefix=t("alarm.radar.cooldown_praefix", lang))


def _box_html(text: str) -> str:
    return (
        f"<div style=\"border-left:4px solid {G_ACCENT};padding:8px 12px;margin-top:12px;"
        f"font-family:{FONT_UI};color:{G_INK_MUTED};\">{_esc(text)}</div>"
    )


def _onset_mail(msg: AlertMessage, h1: str, data_rows, footer: str, lang: Lang) -> tuple[str, str]:
    """Gemeinsame Bauform beider Onset-Mails: Badge, H1, Datenblock,
    Cooldown- und Nachtrags-Box, Fusszeile (Design-Tokens, #952)."""
    badge_text = t("alarm.regen.badge", lang)
    cooldown = _cooldown_text(msg, lang)
    plain_parts = [h1, "", badge_text, ""] + [f"{k}: {v}" for k, v in data_rows] + ["", footer]
    if cooldown:
        plain_parts.append(cooldown)
    # Issue #2018 (AC-B2): additive Bezugszeile, nur wenn diese Meldung ein
    # Nachtrag zu einer bereits zugestellten amtlichen Warnung ist -- sonst
    # unveraendert, ohne Leerzeile.
    if msg.addendum_reference:
        plain_parts.append(msg.addendum_reference)
    rows = [
        _datarow_html(label_, value, G_INK, i == 0)
        for i, (label_, value) in enumerate(data_rows)
    ]
    html = (
        "<html><body style=\"font-family:" + FONT_UI + ";color:" + G_INK + ";\">"
        f"<div style=\"display:inline-block;padding:4px 12px;border-radius:12px;"
        f"background:{G_ACCENT}1f;color:{G_ACCENT};font-family:{FONT_UI};margin-bottom:12px;\">"
        f"{_esc(badge_text)}</div>"
        f"<h1 style=\"margin:0 0 12px;font-family:{FONT_UI};color:{G_INK};\">{_esc(h1)}</h1>"
        f"<div style=\"border-bottom:1px solid #d8d5c9;\">{''.join(rows)}</div>"
    )
    if cooldown:
        html += _box_html(cooldown)
    if msg.addendum_reference:  # Issue #2018 (AC-B2), additiv
        html += _box_html(msg.addendum_reference)
    html += (
        f"<p style=\"color:{G_INK_MUTED};margin-top:16px;font-family:{FONT_UI};\">{_esc(footer)}</p>"
        "</body></html>"
    )
    return html, "\n".join(plain_parts)


def _render_email_onset_multi(msg: AlertMessage, lang: Lang = "de") -> tuple[str, str]:
    """Bündel-Zweig (Issue #1041 Slice 1a): je Ort eine Zeile mit Onset-Zeit
    und Intensität (Muster `loc_prefix`, render_email:328-333).

    Pflicht-Fix (Staging-Befund): additive Cooldown-Zeile analog zum
    Einzel-Onset-Zweig (`_render_email_onset`), nur wenn `msg.cooldown_display`
    gesetzt ist — sonst unverändert (keine leere Zeile/Box)."""
    h1 = t("alarm.regen.buendel", lang, n=len(msg.events))
    data_rows = [
        (
            f"{e.location_label} · "
            f"{t('alarm.regen.gewitter_hagel', lang) if e.is_convective else _onset_kind(e, lang)} "
            f"{_onset_wann_kopf(e, lang)}",
            # Issue #2051 S1: das Ende JE ORT aus dessen eigenem Event -- ein
            # Buendel kann Orte mit verschiedenen Ende-Zeiten tragen. Ohne
            # behauptbares Ende bleibt die Zeile byte-identisch (AC-19).
            # Issue #2051 S2b: dokumentierter No-op -- dieser Zweig laeuft nur
            # ueber den Ortsvergleich-Buendelpfad, der `rain_zones` nie setzt
            # (S2a AC-15). Issue #2050 S4b-2: die Kennzeichnungen JE ORT aus
            # dessen eigenem Event (Known Limitation: kein Buendel-Marker).
            f"{_onset_wann_zeile(e, ab=True, lang=lang)}{_onset_suffixes(e, lang)} · "
            f"{_intensity(e, lang)}",
        )
        for e in msg.events
    ]
    # Finding F003: feste "Quelle: Radar (DWD)"-Fußzeile war falsch, sobald
    # gebündelte Orte unterschiedliche Quellen haben (z.B. AROME-FR, INCA) —
    # jetzt die tatsächlich beteiligten, distinct Quell-Labels der Events.
    footer = (
        f"{t('alarm.mail.stand', lang, stand=msg.stand_at)} · "
        f"{t('alarm.mail.quelle', lang, quelle=_distinct_source_labels(msg))}"
    )
    return _onset_mail(msg, h1, data_rows, footer, lang)


def _render_email_onset(msg: AlertMessage, lang: Lang = "de") -> tuple[str, str]:
    """Vorbild `render_email`s Deviation-Zweig (Z.185-244) — Badge/H1/Datenblock/
    Cooldown-Box/Fußzeile auf Design-Tokens (Issue #952 reopened)."""
    # Issue #1041 Slice 1a: Bündel-Zweig nur bei MEHR ALS EINEM Event; der
    # Ein-Ort-Fall unten bleibt unverändert byte-identisch (AC-2/AC-5).
    if len(msg.events) > 1:
        return _render_email_onset_multi(msg, lang)
    e = msg.events[0]
    h1 = f"{_onset_kind(e, lang)} {_onset_wann_kopf(e, lang)}"
    km = _km_str_onset(e, lang)
    data_rows = [
        # Issue #2051 S1: Beginn und Ende gehoeren in DIESELBE "Wo & wann"-
        # Zeile -- eine eigene Datenzeile nur fuer das Ende waere im
        # Ende-losen Normalfall eine leere Zeile (ADR-0052, Label-Wert-Form).
        # Issue #2051 S2a / #2050 S4b-2: Ausdehnung, Luecken- und
        # Pruefungs-Hinweis an DERSELBEN Stelle (`_onset_suffixes`).
        (t("alarm.mail.wo_wann", lang),
         f"{km} · {_onset_wann_zeile(e, ab=True, lang=lang)}{_onset_suffixes(e, lang)}"),
        (t("alarm.mail.intensitaet", lang), _intensity(e, lang)),
        (t("alarm.mail.quelle_label", lang), e.source_label),
    ]
    if e.briefing_context:
        data_rows.append((t("alarm.mail.briefing", lang), e.briefing_context))
    footer = t("alarm.mail.stand", lang, stand=msg.stand_at)
    return _onset_mail(msg, h1, data_rows, footer, lang)


def _render_telegram_onset(msg: AlertMessage, lang: Lang = "de") -> str:
    e = msg.events[0]
    label = _onset_kind(e, lang)
    km = _km_str_onset(e, lang)
    first = f"<b>{_esc(f'{msg.trip_short} · {km} · {label} {_onset_wann_kopf(e, lang)}')}</b>"
    # Issue #2051 S1: das Ende additiv HINTER der Beginn-Zeit, vor Intensitaet
    # und Quelle -- ohne behauptbares Ende byte-identisch wie bisher (AC-19).
    # Issue #2051 S2b: die Ausdehnung als LETZTES Suffix der Detailzeile, vor
    # Intensitaet und Quelle -- ohne Zonen byte-identisch wie bisher (AC-2).
    # Issue #2050 S4b-2: dieselben zwei Kennzeichnungen wie in E-Mail und
    # Betreff -- Telegram ist kein nachrangiger Kanal (auf dem Pass ist es
    # der gelesene).
    second = (
        f"{_onset_wann_zeile(e, lang=lang)}{_onset_suffixes(e, lang)} · "
        f"{_intensity(e, lang)} · {e.source_label}"
    )
    # Issue #2018 (AC-B3): die Bezugszeile steht als EIGENE Zeile zwischen Kopf
    # und Detailtext -- bei `None` bleibt der Text unveraendert.
    if msg.addendum_reference:
        return "\n".join([first, msg.addendum_reference, second])
    return "\n".join([first, second])


def _sms_onset_time(
    onset_time: str, day_offset: int = 0, weekday: str | None = None,
) -> str:
    """Zeitpunkt-Darstellung der Kurznachricht (Issue #1948 S4, AC-11): die
    Stunde OHNE fuehrende Null (`09:05` -> `9:05`, Zeichenbudget), die Minuten
    bleiben zweistellig. Gilt AUSSCHLIESSLICH hier -- E-Mail, Telegram und
    Betreff lesen `e.onset_time` unveraendert, und das Feld selbst wird nicht
    angefasst.

    Issue #2054: der Tagesbezug steht als vorangestelltes DE-Wochentagskuerzel
    (`Sa0:23`) und nicht mehr als Zahlensuffix (`0:23+1`) -- dieselbe
    Schreibweise, die derselbe Kanal fuer Abweichungsalarme (#2020 S2) und
    amtliche Warnungen (#1948 S5) schon fuehrt. Zweck ist Vereinheitlichung:
    danach kennt die Kurzform genau EINE Schreibweise fuer den Sachverhalt
    "diese Uhrzeit liegt an einem anderen Kalendertag".

    Ueber die Anzeige entscheidet der VERSATZ, nicht das Vorhandensein des
    Kuerzels: ein Gate auf `weekday` wuerde bei fehlendem Kuerzel still den
    Tagesbezug verschlucken (AC-10). Bei `day_offset == 0` (Normalfall)
    byte-identisch zum Bestandsverhalten."""
    hour, sep, rest = onset_time.partition(":")
    base = onset_time if not sep else f"{hour.lstrip('0') or '0'}:{rest}"
    return f"{weekday or ''}{base}" if day_offset else base


# Issue #2046: Untergrenze, ab der eine Mengenangabe in der Kurznachricht
# belastbar ist. Groessenordnung von `radar_service._DRY_THRESHOLD_MM_H`
# (0,1 mm/h ueber eine Stunde ~ 0,1 mm) -- dieselbe Schwelle, die den Beginn
# ueberhaupt erst als "nass" einstuft. BEWUSST hier als eigene Konstante und
# nicht aus `services.radar_service` importiert: ein Renderer haengt sich nicht
# an die Service-Schicht. Alles darunter (inklusive `0.0` und `None`) faellt
# auf die zahlenlose Alt-Form zurueck -- `R0.0@18:00` darf nie entstehen, die
# Anzeige unterscheidet nicht zwischen "nicht berechenbar" und "praktisch null".
_SMS_ONSET_MENGE_MIN_MM = 0.1


def _sms_onset_menge(value: float | None) -> str | None:
    """Zahlanteil der Onset-Mengenangabe (Issue #2046) oder `None`.

    Zahlform kommt aus `output.tokens.metrics._fmt_num` — DERSELBE Formatierer
    wie im Briefing (`R{value:.1f}`), damit Kurznachricht und Briefing keine
    zwei Zahlen-Dialekte sprechen. Keine Einheit im Text (Zeichenbudget)."""
    if value is None or value < _SMS_ONSET_MENGE_MIN_MM:
        return None
    return _fmt_num("R", value)


def _sms_onset_ende(e: OnsetEvent) -> str:
    """Issue #2051 S1: das Ende-Token der Kurznachricht oder leer.

    Dieselbe Zeitform wie das Beginn-Token (`_sms_onset_time`: Stunde ohne
    fuehrende Null, Tages-Suffix `+1` beim Mitternachts-Ueberlauf) -- zwei
    benachbarte Zeit-Token in unterschiedlicher Granularitaet waeren eine
    eigene Fehlerquelle. Ohne Ende (`event_end_time is None`) bleibt das
    Token leer und die Kurzform ist byte-identisch zu #2046 -- kein
    haengendes `@`.

    ZWEI Formen, entschieden allein am R4-Waechter (Spec v1.1, Schreibweise
    vom PO vorgegeben 2026-08-22):

      * nicht gesetzt -> `@HH:MM` direkt am Beginn-Token (`R2.5@18:00@20:00`)
      * gesetzt       -> ` >@HH:MM`, also Leerzeichen, `>`, Zeit-Token
        (`R2.5@18:00 >@20:00`) -- die Untergrenzen-Form.

    Hier haengt an EINEM Zeichen die Bedeutung: `>` fehlt, und aus "regnet
    mindestens bis" wird "hoert auf um". Auf der Huette am Karnischen
    Hoehenweg kommt nur die Premium-SMS an, die denselben `sms_body` traegt --
    es gibt dort keinen zweiten Kanal, der die Aussage richtigstellt. Das
    Praefix wird deshalb an dieser einen Stelle gebildet und dem gemeinsamen
    Zeit-Token nur vorangestellt (AC-20)."""
    ende = getattr(e, "event_end_time", None)
    if not ende:
        return ""
    praefix = " >" if getattr(e, "event_ongoing_beyond_horizon", False) else ""
    return (
        f"{praefix}@" + _sms_onset_time(
            ende,
            getattr(e, "event_end_day_offset", 0),
            # Issue #2054: das Kuerzel des ENDE-Zeitpunkts, nicht das des
            # Beginns -- beide Zeitpunkte werden unabhaengig bewertet.
            getattr(e, "event_end_weekday", None),
        )
    )


def _sms_onset_sharpness_marker(e: OnsetEvent) -> str:
    """Issue #2051 S3 (E8, Spec v1.1 -- Nachtrag aus der Abstimmung mit
    #2054): das Guete-Zeichen der Kurzform -- `"?"` oder leer.

    Bindet an die GANZE Zeitgruppe, nicht an einen einzelnen Zeitpunkt: der
    Aufrufer haengt das Ergebnis IMMER ans Ende des bereits VOLLSTAENDIG
    gebildeten Zeit-Tokens an (Beginn+Ende bzw. `now`+Ende) -- diese
    Funktion selbst kennt die innere Form dieses Tokens nicht und darf sie
    auch nicht kennen (Laufzeit-unabhaengig vom #2054-Wochentagskuerzel,
    das INNERHALB von `_sms_onset_time()` entsteht). Waere der Beginn
    diesseits der Guete-Grenze und nur das Ende jenseits (AC-5), stuende
    eine Marke am Beginn-Token an der einen Zeit, die scharf ist -- am
    LETZTEN Token der Gruppe ist sie das nicht.

    `?` statt `~`: `~` gehoert zur GSM-7-Extension-Tabelle (2 Septets) und
    wird vom Transport hart auf `-` gefaltet (`_ASCII_EXTENSION_
    REPLACEMENTS`, unten). `?` steht im GSM-7-BASISzeichensatz."""
    return "?" if getattr(e, "location_sharpness_limit_time", None) else ""


def _sms_onset_convective_marker(e: OnsetEvent) -> str:
    """Issue #2050 S4b-2: das Zeichen der AUSGEFALLENEN Gewitterpruefung --
    `"#"` oder leer.

    Bindet an das KUERZEL (`R#2.5@18:00`), nicht an die Zeitgruppe wie der
    Guete-Marker: qualifiziert wird der Sachverhalt selbst (Gewitter oder
    Regen), nicht der Zeitpunkt.

    `#` statt `?` (durch die Einsetzschaerfe #2051 S3 belegt) und statt `*`
    (vor einer Zahl als Multiplikation lesbar). GSM-7-BASISzeichen, kein
    Extension-Faltungsrisiko."""
    return "" if getattr(e, "convective_checked", True) else "#"


def _sms_onset_gap_marker(e: OnsetEvent) -> str:
    """Issue #2050 S4b-2: das Zeichen der unvollstaendig gemessenen Ausdehnung
    -- `">"` oder leer.

    Der Aufrufer haengt es an die bereits gebildete Zonen-Liste (`km2-4,9-11>`)
    und NUR dann, wenn eine Liste entstanden ist: freistehend hinter dem
    Zeit-Token truege `>` die andere, bestehende Bedeutung der Ende-Grammatik
    ("Regen mindestens bis", #2051 S1) und waere damit eine FALSCHE Angabe
    statt einer fehlenden. Auf die Strecke angewandt sagt dasselbe Zeichen
    dasselbe: "reicht mindestens so weit"."""
    return ">" if getattr(e, "gap_km", ()) else ""


def _sms_onset_extent_suffix(zonen: tuple[RainZone, ...], budget: int) -> str:
    """Issue #2051 S2b: Zonen-Kuerzel der Kurzform (` km8-12,19-21`) oder leer.

    `budget` ist die Anzahl noch verfuegbarer Zeichen NACH dem Rest des Textes
    (`limit - len(bisheriger_body)`) -- das Kuerzel haengt sich nur an, wenn es
    VOLLSTAENDIG hineinpasst; passt nicht einmal die erste Zone, entfaellt die
    Angabe komplett. Bei mehreren Zonen werden von vorn so viele genommen, wie
    vollstaendig passen -- nie eine angeschnittene Spanne, nie ein haengendes
    Komma.

    Der Grund ist fachlich, nicht kosmetisch: `km8-1` waere im Satellitenkanal
    eine FALSCHE Angabe, keine fehlende -- und auf der Huette am Karnischen
    Hoehenweg kommt nur die Premium-SMS an, es gibt dort keinen zweiten Kanal,
    der sie richtigstellt.

    EIN `km`-Praefix vor der ersten Spanne, danach nur noch `X-Y`-Paare
    (Zeichenbudget). Ganzzahlig gerundet und mit ASCII-Bindestrich wie die
    Langform (`_onset_extent_suffix`) -- unterschiedliche Wortform, identischer
    Zahleninhalt (AC-10). Die Sichtbarkeitsregel (`km_measured`, leere Zonen)
    kennt diese Funktion bewusst NICHT, sie kennt nur das Budget; entschieden
    wird sie an der Aufrufstelle, wie in der Langform."""
    if not zonen:
        return ""
    genommen: list[str] = []
    for z in zonen:
        kandidat = genommen + [f"{int(round(z.km_from))}-{int(round(z.km_to))}"]
        if len(" km" + ",".join(kandidat)) > budget:
            break
        genommen = kandidat
    if not genommen:
        return ""
    return " km" + ",".join(genommen)


def _render_sms_onset(msg: AlertMessage, limit: int = 140) -> str:
    """Issue #1948 S4: die Nowcast-/Onset-Kurznachricht nennt einen ZEITPUNKT
    (`TH@15:40`) statt eines Countdowns (`TH!8`) und spricht im Kopf dieselbe
    Ortssprache wie Betreff und E-Mail (`format_alert_location`: Ortsname ->
    Segment -> km-Rueckfall) statt der selbstgebauten `km8-8`-Notation.

    Drei Kopf-Faelle:
      * `location_label` gesetzt -> gebuendelter Ortsvergleich (>1 Ort), Kopf
        ist der Ortsname des fuehrenden Events (Issue #1935/#1779 E4-Weiche).
      * `msg.source == COMPARE_RADAR_SOURCE` -> Ortsvergleich mit GENAU einem
        Ort; dort bleibt `location_label` laut Konstruktor-Invariante `None`,
        der Ortsname steht allein in `msg.trip_short` (AC-6).
      * sonst -> Trip-Radar, dieselbe Ortsaufloesung wie die anderen Kanaele.

    `_ascii_alert_location` (nicht `_ascii`) entfernt Piktogramme VOR der
    ASCII-Faltung -- sonst stuende `:checkered_flag:` in der SMS (AC-8).
    `_km_str_onset` bleibt bewusst unangetastet: Telegram und Betreff lesen
    ihn mit (AC-10)."""
    e = msg.events[0]
    kuerzel = "TH" if e.is_convective else "R"
    # Issue #2050 S4b-2: das Zeichen der ausgefallenen Gewitterpruefung haengt
    # unmittelbar am Kuerzel -- in JEDER Token-Form unten, auch dort, wo das
    # `R` mit der Mengenangabe verschmilzt (`R#2.5@18:00`). Es steht genau
    # EINMAL im Text: das zweite `R` des Gewitter-Zweigs (die Menge) traegt es
    # nicht, es beschriftet keine Ereignisart. Der Weichen-Vergleich unten
    # bleibt auf `kuerzel` und nicht auf dieser Form -- sonst kippte er still,
    # sobald die Marke gesetzt ist.
    kopf = kuerzel + _sms_onset_convective_marker(e)
    # Issue #2051 S1: das Ende-Token haengt unmittelbar am Beginn-Token
    # (`R2.5@18:00@20:00`). Bewusst hier zusammengefasst statt in jedem der
    # drei Token-Zweige unten: so traegt AUCH der Gewitter-Zweig das Ende an
    # der Zeit (`TH@18:00@20:00 R2.5`) und nicht hinter der Menge -- sonst
    # bliebe dort eine stille Luecke.
    # Issue #2051 S3 (E8): einmalig berechnet, dem jeweils LETZTEN Zeit-Token
    # der Gruppe angehaengt -- unabhaengig davon, welchen Zweig (Normalform
    # unten oder Laufend-Form) der Text nimmt. Unabhaengig vom #2054-
    # Wochentagskuerzel, das INNERHALB von `_sms_onset_time()` entsteht
    # (Token-Anfang) -- unsere Marke sitzt am Token-ENDE (E8).
    guete_marker = _sms_onset_sharpness_marker(e)
    zeit = (
        _sms_onset_time(
            e.onset_time, e.onset_day_offset,
            getattr(e, "onset_weekday", None),  # Issue #2054
        ) + _sms_onset_ende(e)
        + guete_marker
    )
    menge = _sms_onset_menge(getattr(e, "onset_precip_mm", None))
    if getattr(e, "already_running", False):
        # Issue #2050 S2b (PO-Entscheid 2026-08-22): `now` steht dort, wo
        # sonst das Beginn-Zeittoken stuende -- ENGLISCH wie die ganze
        # Kurzform (`R` = Rain, `TH` = Thunder). Die Ende-Grammatik aus #2051
        # haengt unveraendert dahinter (`now@20:00` bekanntes Ende,
        # `now >@20:00` Untergrenze), damit es nur EINE Ende-Form gibt.
        ende = _sms_onset_ende(e) + guete_marker
        if menge is None:
            token = f"{kopf} now{ende}"
        elif kuerzel == "TH":
            token = f"{kopf} now{ende} R{menge}"
        else:
            token = f"{kopf}{menge} now{ende}"
    elif menge is None:
        token = f"{kopf}@{zeit}"
    elif kuerzel == "TH":
        # Issue #2046: im Gewitter-Fall steht die Menge als EIGENES Token NACH
        # der Zeit. Die Position unmittelbar hinter `TH` gehoert in der
        # Briefing-Grammatik der Stufe (LEVELS: L/M/H) -- ein `TH2.5` dort
        # waere als Stufe lesbar und damit missverstaendlich.
        token = f"{kopf}@{zeit} R{menge}"
    else:
        token = f"{kopf}{menge}@{zeit}"
    prefix = _stage_prefix(msg.events)  # Issue #2122
    if getattr(e, "location_label", None):
        loc = _ascii_alert_location(e.location_label)[:24]
    elif msg.source == COMPARE_RADAR_SOURCE:
        loc = _ascii_alert_location(msg.trip_short)[:24]
    else:
        loc = _ascii_alert_location(_location_of((e,), None))[:24]
    head = f"{prefix}{loc}"
    body = f"{head}: {token}"
    # Issue #2051 S2b: das Zonen-Kuerzel ist das ZULETZT angefuegte Element --
    # dieselbe Sichtbarkeitsregel wie `_onset_extent_suffix` in der Langform
    # (nur vermessene Etappe, nur nicht-leere Zonen), und nur so viel, wie
    # vollstaendig ins Budget passt (AC-4/AC-6/AC-8).
    if getattr(e, "km_measured", False) and getattr(e, "rain_zones", ()):
        # Issue #2050 S4b-2: der Platz fuer den Luecken-Marker wird VOR der
        # Zonenauswahl reserviert. Haengte man ihn danach unbedingt an, fraesse
        # ihn im Randfall der harte Sicherungsschnitt unten still weg -- der
        # Text saehe dann vollstaendig gemessen aus, obwohl er es nicht ist,
        # und keine Pruefung koennte den Unterschied sehen (das Ergebnis waere
        # byte-identisch zur korrekten Fassung). Im Randfall entfaellt deshalb
        # die LETZTE ZONE zugunsten des Markers: der Hinweis "unvollstaendig
        # gemessen" wiegt schwerer als die letzte von vielen Streckenangaben.
        luecken_marker = _sms_onset_gap_marker(e)
        zonen = _sms_onset_extent_suffix(
            e.rain_zones, limit - len(body) - len(luecken_marker),
        )
        # Ohne Zonen-Liste entfaellt der Marker mit ihr: freistehend hinter dem
        # Zeit-Token truege `>` die Ende-Bedeutung ("mindestens bis") und waere
        # eine falsche Aussage statt einer fehlenden.
        body += (zonen + luecken_marker) if zonen else ""
    return body if len(body) <= limit else body[:limit]


def render_subject(msg: AlertMessage, *, lang: Lang = "de") -> str:
    if msg.source is not None:
        return _render_subject_onset(msg, lang)
    if not msg.events and msg.onset_shift_events:
        # Issue #1468: reine Beginn-Verschiebung ohne Wert-Aenderungs-Anteil.
        oe = msg.onset_shift_events[0]
        mehr = (f" +{len(msg.onset_shift_events) - 1}"
                if len(msg.onset_shift_events) > 1 else "")
        return (
            f"[{msg.trip_short}] {_onset_shift_where(oe, lang)} · {_onset_shift_label(oe, lang)} "
            f"{oe.to_time} ({_shift_text(oe, lang)}){mehr}"
        )
    evs = _sorted(msg)
    km = _km_str(msg, lang)
    if len(evs) == 1:
        e = evs[0]
        return (
            f"[{msg.trip_short}] {km} · {arrow(e)} {_deviation_label(e, lang)}: "
            f"{_val(e, e.value_from, lang)}→{_val(e, e.value_to, lang)}"
        )
    # Issue #981: Zähler UND Top-3-Auswahl nur aus über-Schwelle-Events; ohne
    # solche wechselt die Formulierung auf "N Änderungen seit dem Briefing".
    over_evs = [e for e in evs if over_thr(e)]
    if not over_evs:
        return f"[{msg.trip_short}] {km} · {t('alarm.abweichung.aenderungen', lang, n=len(evs))}"
    n = len(over_evs)
    # Issue #978 (PO-Nachtrag): Top-3-Auswahl UND Anzeige-Reihenfolge sind
    # severity-absteigend (kritischster zuerst), kanal-konsistent mit
    # render_email() und render_telegram().
    # Issue #1935/#1779 (E5): Einheit immer anhaengen (nicht mehr nur bei
    # '%') -- dieselbe Regel wie im E-Mail-Zweig (AC-11).
    top3 = ", ".join(
        f"{_deviation_label(e, lang)} {_num(e, e.value_to, lang)}{_unit_suffix(e)}"
        for e in over_evs[:3]
    )
    ueber = t("alarm.abweichung.ueber_schwelle", lang, n=n)
    return f"[{msg.trip_short}] {km} · {arrow(over_evs[0])} {ueber}: {top3}"


def _h1(msg: AlertMessage, lang: Lang = "de") -> str:
    """Issue #1948 S6 (AC-9): nennt Von-/Bis-Wert statt der entfallenen
    berechneten Prozent-Änderung -- die inhaltsleere Form 'Gewitter seit dem
    Briefing' (frueherer value_from==0-Sonderfall) entsteht dadurch nicht
    mehr, `_val()` liefert fuer Stufenmetriken ohnehin ein Wort statt '0'."""
    evs = _sorted(msg)
    if len(evs) == 1:
        e = evs[0]
        return t("alarm.abweichung.h1", lang, label=_deviation_label(e, lang),
                 von=_val(e, e.value_from, lang), bis=_val(e, e.value_to, lang))
    return t("alarm.abweichung.h1_mehrere", lang, n=len(evs))


def _email_line(e: AlertEvent, lang: Lang = "de") -> str:
    schwelle = t("alarm.abweichung.schwelle", lang, wert=_val_delta(e, e.threshold, lang))
    return (
        f"{_deviation_label(e, lang)} · {schwelle} · "
        f"{_val(e, e.value_from, lang)} {arrow(e)} {_val(e, e.value_to, lang)}"
        f"{_hail_note_suffix(e, lang)} · "
        f"{t('alarm.abweichung.aenderung', lang, wert=side_label(e, lang))}"
    )


def _verdict_single(e: AlertEvent, lang: Lang = "de") -> str:
    """Issue #1948 S6 (AC-8): keine berechnete Prozent-Änderung mehr im
    Badge -- nur noch Richtung, Über/Unter-Schwelle-Aussage und der
    tatsaechliche Schwellenwert (Abstand, daher `_val_delta`)."""
    return t("alarm.abweichung.urteil", lang, pfeil=arrow(e), seite=side_label(e, lang),
             schwelle=_val_delta(e, e.threshold, lang))


def _datablock_single(
    e: AlertEvent, location_label: str | None = None, *, lang: Lang = "de",
) -> list[tuple[str, str]]:
    """3 (label, value)-Zeilen: Wert-Vergleich / Schwellwert-Status / Wo & wann.

    Issue #1169: gesetztes `location_label` (Compare-Punkt-Alert) ersetzt die
    km-Spanne; Trip-Pfad übergibt es nie (bit-identisch, AC-7).

    Issue #1935/#1779 (E1): Zeile 2 nannte bisher `Alarm-Schwelle {wert}` als
    Label und `jetzt {über|unter} {mark}` als Wert -- beides zeigte auf den
    MESSWERT, obwohl `threshold` per ADR-0013 (#958) immer die Δ-Schwelle
    ist. Neu: Label nennt den tatsaechlichen Aenderungsbetrag, Wert stellt ihn
    der Schwelle gegenueber -- deckungsgleich mit `_verdict_single` eine Zeile
    hoeher (AC-3). `over_thr()`/`side_label()` bleiben unveraendert.
    """
    unit = get_metric(e.metric_id).unit
    row1 = (
        f"{_deviation_label(e, lang)} · {unit}",
        f"{_val(e, e.value_from, lang)} {arrow(e)} {_val(e, e.value_to, lang)}"
        f"{_hail_note_suffix(e, lang)}",  # Issue #2205
    )
    mark ="✓" if not over_thr(e) else "✗"
    row2 = (
        t("alarm.abweichung.aenderung", lang, wert=_val_delta(e, abs(e.value_to - e.value_from), lang)),
        t("alarm.abweichung.seite_schwelle", lang, seite=side_label(e, lang),
          schwelle=_val_delta(e, e.threshold, lang), mark=mark),
    )
    # Issue #1744 A1 (AC-6): DIESELBE Aufloesung wie im Betreff — vorher stand
    # hier ein dritter, eigener km-Bauer (`_km_str_events`), weshalb der
    # Mailkoerper km sprach, waehrend der Betreff schon Segmente sprach.
    # Issue #2020 Scheibe 2: derselbe Zeit-/Bedeutungs-Baustein wie im
    # Mehr-Ereignis-Zweig (`_where_when`) -- keine zweite Kopie.
    row3 = (t("alarm.mail.wo_wann", lang), _where_when(e, location_label, lang=lang))
    # Issue #2020 Scheibe 2: Niederschlags-Summen-Ereignisse bekommen die
    # Blickrichtung als eigene Zeilen; alle uebrigen Metriken behalten den
    # Block unveraendert dreizeilig.
    if e.remaining_mm is None:
        return [row1, row2, row3]
    return [row1, row2, row3, *_precip_rows(e, lang)]


def _datarow_html(
    label: str, value: str, value_color: str, first: bool, *,
    value_html: str | None = None,
) -> str:
    """Issue #986: Outlook-kompatible 2-Spalten-Tabellen-Row (Label links,
    Wert rechtsbündig in FONT_DATA). Outlook ignoriert Flexbox — daher eine
    `<table role="presentation">`-Row statt zweier <span>s im selben <div>.

    Issue #1744 A2: `value_html` setzt FERTIGES Markup in die Wert-Zelle
    (Route-Chips der amtlichen Warnung), statt `value` zu escapen — dieselbe
    Bauform trägt damit beide Alarm-Mailtypen (AC-8). Ohne den Parameter
    bleibt die Ausgabe byte-identisch.
    """
    border = "" if first else "border-top:1px solid #d8d5c9;"
    return (
        f"<table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" "
        f"style=\"{border}\"><tr>"
        f"<td align=\"left\" style=\"padding:8px 0;font-family:{FONT_UI};color:{G_INK_MUTED};\">"
        f"{_esc(label)}</td>"
        f"<td align=\"right\" style=\"padding:8px 0;font-family:{FONT_DATA};color:{value_color};\">"
        f"{_esc(value) if value_html is None else value_html}</td>"
        f"</tr></table>"
    )


def _with_origin(
    html: str, plain: str, mail_type: str, source: str, *, lang: Lang = "de",
) -> tuple[str, str]:
    """Issue #1241/warnmail-Spec AC-5 (Befund 4a): hängt die geteilte
    Herkunfts-Fußzeile an (HTML vor </body>, Plain am Ende) -- Zeile 2 zeigt
    die echte Datenquelle (`source`), nicht mehr den internen Renderer-Pfad."""
    from output.renderers.email.helpers import (
        build_origin_footer, render_origin_footer_html, render_origin_footer_text,
    )
    footer = build_origin_footer(mail_type, source=source, lang=lang)
    html = html.replace(
        "</body></html>", render_origin_footer_html(footer) + "</body></html>",
    )
    plain = plain + "\n\n" + render_origin_footer_text(footer)
    return html, plain


def _hours_note(e: AlertEvent, lang: Lang = "de") -> str:
    return t("alarm.abweichung.betroffen", lang, von=e.hours_range[0], bis=e.hours_range[1])


def _hour_lines(e: AlertEvent, modes: dict | None, lang: Lang = "de") -> list[str]:
    """Issue #1737: Stundenzeilen `HH:MM | alt → neu` (Klartext/Telegram) plus
    Hinweiszeile bei Kappung. Leer ohne Stundenreihe (Ausgabe unveraendert)."""
    lines = [
        f"{r.time} | " + " → ".join(row_parts(e, r, modes, html=False)) for r in e.hours
    ]
    if lines and e.hours_capped and e.hours_range:
        lines.append(_hours_note(e, lang))
    return lines


def _hours_html(
    e: AlertEvent, modes: dict | None, indicators: frozenset = frozenset(),
    lang: Lang = "de",
) -> str:
    """Issue #1737: EIN eigener Zeilenblock je Ereignis (keine gemeinsame
    Tabelle). EINFACH = CSS-Punkte aus `fmt_val`, nie Emoji (#2220)."""
    if not e.hours:
        return ""
    td = f"padding:2px 12px 2px 0;font-family:{FONT_DATA};color:{G_INK};"
    trs = []
    for r in e.hours:
        cell = " → ".join(
            p if p.startswith("<span") else _esc(p)
            for p in row_parts(e, r, modes, html=True, indicators=indicators)
        )
        trs.append(f"<tr><td style=\"{td}\">{_esc(r.time)}</td><td style=\"{td}\">{cell}</td></tr>")
    if e.hours_capped and e.hours_range:
        note = _esc(_hours_note(e, lang))
        trs.append(
            f"<tr><td colspan=\"2\" style=\"padding:2px 0;font-family:{FONT_UI};"
            f"color:{G_INK_MUTED};\">{note}</td></tr>"
        )
    return (
        "<table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" "
        f"style=\"margin:4px 0 8px;\">{''.join(trs)}</table>"
    )


def _stand_footer(msg: AlertMessage, lang: Lang = "de") -> str:
    """'Stand: heute HH:MM · verglichen mit …' -- E-Mail und Telegram (#1948 S6)."""
    referenz = msg.reference_at or t("alarm.mail.letztes_briefing", lang)
    return (f"{t('alarm.mail.stand', lang, stand=msg.stand_at)} · "
            f"{t('alarm.mail.verglichen', lang, referenz=referenz)}")


def _verdict_multi(msg: AlertMessage, evs, over_count: int, lang: Lang = "de") -> str:
    if over_count:
        return t("alarm.abweichung.ueber_schwelle", lang, n=over_count)
    return t("alarm.abweichung.aenderungen", lang, n=len(evs))


def render_email(msg: AlertMessage, *, lang: Lang = "de") -> tuple[str, str]:
    if msg.source is not None:
        html, plain = _render_email_onset(msg, lang)
        # AC-5 (Befund 4a): reale Quelle des ersten (fuehrenden) Onset-Events.
        onset_source = getattr(msg.events[0], "source_label", None) or "Open-Meteo"
        return _with_origin(html, plain, "radar-alert", onset_source, lang=lang)
    if not msg.events and msg.onset_shift_events:
        return _render_email_onset_shift_only(msg, lang)
    evs = _sorted(msg)
    h1 = _h1(msg, lang)
    single = len(evs) == 1

    if single:
        e = evs[0]
        verdict_text = _verdict_single(e, lang)
        # Issue #1170: per-Event `location_label` (gebündelter Mehr-Orte-Alarm)
        # geht dem kollektiven `msg.location_label` vor; für Trip/Einzel-Ort
        # sind beide identisch bzw. beide None (bit-identisch, AC-7).
        data_rows = _datablock_single(e, e.location_label or msg.location_label, lang=lang)
        # Issue #1916 (AC-1/AC-2): gesetztes `reference_at` ersetzt den
        # generischen Text durch den Referenz-Zeitpunkt der tatsaechlich
        # verglichenen Vergleichsbasis. `None` -> Regressions-Invariante AC-5.
        footer = _stand_footer(msg, lang)
        any_over = over_thr(e)
        plain_data = [f"{k}: {v}" for k, v in data_rows]
        plain_data += _hour_lines(e, msg.format_modes.get("email"), lang)  # Issue #1737
    else:
        # Issue #981: Zähler zählt nur über-Schwelle-Events; sind es null,
        # wechselt die Formulierung auf "N Änderungen seit dem Briefing".
        over_count = len([e for e in evs if over_thr(e)])
        verdict_text = _verdict_multi(msg, evs, over_count, lang)
        if over_count:
            verdict_text = f"{arrow(evs[0])} {verdict_text}"
        # Issue #978: Einheit genau einmal (am letzten Wert), Schwelle ohne
        # Einheit -- ausser bei "%", wo sie zur Unterscheidung mitgefuehrt
        # wird (exaktes Vorbild Design-Vorlage Zeilen 220-233).
        data_rows = []
        # Issue #1861: mehrere Ereignisse DERSELBEN Metrik waren als Zeilen
        # ununterscheidbar — Segment-/Zeit-Bezug je Zeile behebt das.
        with_where_when = _per_event_where_when(evs)
        for e in evs:
            unit = _unit_display(e)
            unit_suffix = f" {unit}" if unit else ""
            # Issue #1170: bei gebündelten Mehr-Orte-Alarmen trägt jedes Event
            # sein eigenes `location_label` — Label bekommt den Ortsnamen
            # vorangestellt, damit jeder Datenblock den richtigen Ort zeigt.
            # Trip-Fall (location_label immer None) bleibt unverändert (leerer
            # Prefix, AC-7-Invariante).
            loc_prefix = f"{e.location_label} · " if e.location_label else ""
            where_when = f" · {_where_when(e, lang=lang)}" if with_where_when else ""
            if over_thr(e):
                # Issue #1935/#1779 (E2): dieselbe Ambiguitaet wie E1, nur im
                # gebuendelten Fall -- Label nennt zusaetzlich zur Schwelle
                # den tatsaechlichen Aenderungsbetrag (zwei unterscheidbare
                # Zahlen in derselben Zeile, AC-4).
                delta = abs(e.value_to - e.value_from)
                if _is_level_metric(e.metric_id):
                    # Issue #1948 S6 (AC-4/AC-6): Abstaende einer Stufen-
                    # metrik sind Zahl + 'Stufe(n)', NIE ein Stufenwort.
                    delta_suffix = f" {_stufe_unit(delta, lang)}"
                    schwelle_suffix = f" {_stufe_unit(e.threshold, lang)}"
                else:
                    delta_suffix = schwelle_suffix = " %" if unit == "%" else ""
                aenderung = f"{_num_delta(e, delta, lang)}{delta_suffix}"
                schwelle = f"{_num_delta(e, e.threshold, lang)}{schwelle_suffix}"
                data_rows.append((
                    f"{loc_prefix}{_deviation_label(e, lang)}{where_when} · "
                    f"{t('alarm.abweichung.aenderung', lang, wert=aenderung)} · "
                    f"{t('alarm.abweichung.schwelle', lang, wert=schwelle)}",
                    f"{_num(e, e.value_from, lang)} {arrow(e)} {_num(e, e.value_to, lang)}"
                    f"{unit_suffix}{_hail_note_suffix(e, lang)} {side_label(e, lang)}",
                ))
            else:
                # Issue #980: gedämpfte Unter-Schwelle-Zeile — Label OHNE
                # Schwellen-Zahl, Wert mit neutralem Pfeil, kein über/unter-Suffix
                # (Design-Vorlage Zeilen 231-234).
                data_rows.append((
                    f"{loc_prefix}{_deviation_label(e, lang)}{where_when} · "
                    f"{t('alarm.abweichung.unter_schwelle', lang)}",
                    f"{_num(e, e.value_from, lang)} → {_num(e, e.value_to, lang)}{unit_suffix}"
                    f"{_hail_note_suffix(e, lang)}",
                ))
        footer = f"{_stand_footer(msg, lang)} · {_km_str(msg, lang)}"
        any_over = over_count > 0
        plain_data = []
        for e, (k, v) in zip(evs, data_rows):
            plain_data.append(f"{k}: {v}")
            plain_data += _hour_lines(e, msg.format_modes.get("email"), lang)  # Issue #1737

    verdict_bg = G_DANGER if any_over else G_SUCCESS
    # Issue #1468 (PO-Entscheid): Beginn- UND Stufenaenderung werden beide
    # gemeldet, aber im Text DERSELBEN Nachricht zusammengefasst.
    onset_lines = [_onset_shift_line(oe, lang) for oe in msg.onset_shift_events]
    plain_parts = [h1, "", verdict_text, ""] + plain_data
    if onset_lines:
        plain_parts += ["", *onset_lines]
    plain_parts += ["", footer]
    plain = "\n".join(plain_parts)

    rows = []
    if single:
        threshold_status_color = G_DANGER if over_thr(e) else G_SUCCESS
        for idx, (label, value) in enumerate(data_rows):
            value_color = G_INK if idx != 1 else threshold_status_color
            rows.append(_datarow_html(label, value, value_color, not rows))
        rows.append(_hours_html(e, msg.format_modes.get("email"), msg.indicator_keys.get("email", frozenset()), lang))  # Issue #1737
    else:
        for e, (label, value) in zip(evs, data_rows):
            value_color = G_DANGER if over_thr(e) else G_INK_MUTED
            rows.append(_datarow_html(label, value, value_color, not rows))
            rows.append(_hours_html(e, msg.format_modes.get("email"), msg.indicator_keys.get("email", frozenset()), lang))  # Issue #1737
    for oe in msg.onset_shift_events:
        rows.append(_onset_shift_row(oe, not rows, lang))

    html = (
        "<html><body style=\"font-family:" + FONT_UI + ";color:" + G_INK + ";\">"
        f"<h1 style=\"margin:0 0 12px;font-family:{FONT_UI};color:{G_INK};\">{_esc(h1)}</h1>"
        f"<div style=\"display:inline-block;padding:4px 12px;border-radius:12px;"
        f"background:{verdict_bg};color:#ffffff;font-family:{FONT_UI};margin-bottom:12px;\">"
        f"{_esc(verdict_text)}</div>"
        f"<div style=\"border-bottom:1px solid #d8d5c9;\">{''.join(rows)}</div>"
        f"<p style=\"color:{G_INK_MUTED};margin-top:16px;font-family:{FONT_UI};\">{_esc(footer)}</p>"
        "</body></html>"
    )
    # AC-5 (Befund 4a, Known Limitation): kein per-Event-Provider im Modell --
    # fester Fallback "Open-Meteo" (ADR-0029).
    return _with_origin(html, plain, "deviation-alert", "Open-Meteo", lang=lang)


def render_telegram(msg: AlertMessage, *, lang: Lang = "de") -> str:
    if msg.source is not None:
        return _render_telegram_onset(msg, lang)
    if not msg.events and msg.onset_shift_events:
        # Issue #1468: reine Beginn-Verschiebung.
        lines = [f"<b>{_esc(f'{msg.trip_short} · {_onset_shift_h1(msg, lang)}')}</b>"]
        lines += [_onset_shift_line(oe, lang) for oe in msg.onset_shift_events]
        return "\n".join(lines)
    evs = _sorted(msg)
    km = _km_str(msg, lang)
    if len(evs) == 1:
        e = evs[0]
        verdict = f"{msg.trip_short} · {km} · {arrow(e)} {_deviation_label(e, lang)}"
        # Issue #2020 Scheibe 2: Telegram traegt DIESELBEN Saetze wie die
        # E-Mail (Kanal-Paritaet) -- vorher fehlte hier jede Zeitangabe, der
        # Kanal konnte den Tagesbezug also gar nicht nennen.
        lines = [f"<b>{_esc(verdict)}</b>", _email_line(e, lang), _where_when(e, lang=lang)]
        if e.remaining_mm is not None:
            lines += [f"{k}: {v}" for k, v in _precip_rows(e, lang)]
        lines += [_esc(ln) for ln in _hour_lines(e, msg.format_modes.get("telegram"), lang)]  # Issue #1737
    else:
        # Issue #981: Kopfzeilen-Zähler nur über-Schwelle; null → Änderungs-Text.
        over_count = len([e for e in evs if over_thr(e)])
        verdict = f"{msg.trip_short} · {km} · {_verdict_multi(msg, evs, over_count, lang)}"
        # Issue #978 (PO-Nachtrag): kein "Schwelle"-Text pro Zeile (steht
        # bereits in der fetten Kopfzeile), keine Einheiten ausser "%";
        # severity-absteigende Reihenfolge, kanal-konsistent mit Betreff/
        # E-Mail-Datenblock.
        # Issue #1861: derselbe Ort-/Zeit-Zusatz wie im E-Mail-Datenblock
        # (Kanalkonsistenz, Issue #978-Praezedenz).
        with_where_when = _per_event_where_when(evs)
        # Issue #1935/#1779 (E5): Einheit immer anhaengen (AC-11).
        metric_line = " · ".join(
            f"{_deviation_label(e, lang)}{f' {_where_when(e, lang=lang)}' if with_where_when else ''} "
            f"{_num(e, e.value_from, lang)}→{_num(e, e.value_to, lang)}"
            f"{_unit_suffix(e)}{_hail_note_suffix(e, lang)}"
            for e in evs
        )
        lines = [f"<b>{_esc(verdict)}</b>", metric_line]
        # Issue #1737: je Ereignis ein eigener Stundenblock unter seiner Kopfzeile.
        for e in evs:
            block = _hour_lines(e, msg.format_modes.get("telegram"), lang)
            if block:
                lines += [_esc(_deviation_label(e, lang)), *[_esc(ln) for ln in block]]
    # Issue #1468: Beginn-Verschiebungen desselben Laufs anhaengen -- eine
    # Nachricht, nicht zwei.
    lines += [_onset_shift_line(oe, lang) for oe in msg.onset_shift_events]
    # Issue #1948 S6 (AC-11): dieselbe Stand-/Vergleichszeile wie die E-Mail
    # -- AUSSCHLIESSLICH hier, niemals in render_sms (AC-12, der Telegram-
    # Kurzstil sendet render_sms()s Text unveraendert weiter).
    lines.append(_stand_footer(msg, lang))
    return "\n".join(lines)


def _sms_token(
    e: AlertEvent, location_positions: dict[str, int] | None = None,
) -> str:
    """Issue #1467 S2 AG3b: `location_positions` (Ortsname → 1-basierte Position
    in `preset["location_ids"]`) ist ein NEUER, defaultierter Parameter. Ist er
    gesetzt UND traegt das Ereignis ein `location_label` — das setzt
    `to_multi_point_alert_message()` nur im gebuendelten Mehr-Orte-Fall
    (`project.py:215`) —, wird die Ortsposition als ZAHL vorangestellt (PO E2:
    Orte werden als Zahl gefuehrt, nicht ausgeschrieben). Ohne den Parameter
    bleibt das Token byte-identisch zum bisherigen Verhalten fuer Trip-Radar
    und Compare-Radar — AC-26-Zusicherung fuer SMS.

    Issue #1935/#1779 (E3): traegt das Ereignis KEINE Ortsposition (also der
    Trip-Δ-Pfad, `location_positions is None`), fuehrt das Token zusaetzlich
    den Von-Wert statt nur den Bis-Wert -- der Ausschlag wird lesbar, ohne
    dass der Empfaenger den letzten Mailstand kennen muss (AC-6). Der
    Ortsvergleich-Aenderungspfad (`location_positions` gesetzt) behaelt sein
    Token byte-identisch (AC-9, #1467 S2 AG3b).

    Issue #1948 S3: der Trip-Δ-Pfad schreibt `{code}{von}->{bis}` OHNE
    Vorzeichen-Praefix (`>` las sich als "groesser als"); Stufen-Metriken
    (`is_level`, z.B. Gewitter) sprechen dabei dieselbe Buchstabenleiter wie
    das Briefing (`TH:M->H`). Der Compare-Pfad bleibt bei `{sign}{code}{bis}`.
    """
    if location_positions is None:
        if _is_level_metric(e.metric_id):
            tok = (
                f"{_code(e)}:{LEVELS.get(int(round(e.value_from)), '-')}"
                f"->{LEVELS.get(int(round(e.value_to)), '-')}"
            )
        else:
            tok = f"{_code(e)}{int(round(e.value_from))}->{int(round(e.value_to))}"
    else:
        sign = "+" if e.value_to >= e.value_from else "-"
        tok = f"{sign}{_code(e)}{int(round(e.value_to))}"
    tok += _sms_hail_suffix(e)  # Issue #2205: vor `@HH`, Muster tokens.builder
    span = ""
    if e.hours_range:
        first, last = e.hours_range[0][:2], e.hours_range[1][:2]
        span = first + (f"-{last}" if last != first else "")
    if span and not e.occurred_day_offset:
        # Issue #1737: betroffene Stunden als Zeitspanne `@HH-HH` (ASCII, GSM-7
        # #1796) statt der Einzelstunde.
        tok = tok + f"@{span}"
    elif e.occurred_at:
        # Issue #2020 Scheibe 2: liegt der Zeitpunkt an einem anderen Tag,
        # klebt das Wochentagskuerzel vor die Stunde (`@Do15`) -- dieselbe
        # Bestandsnotation wie die amtliche Warnung. Ein Zahlensuffix ist
        # verworfen: "-" ist in der Kurzform bereits dreifach belegt.
        tag = _sms_day_prefix(e.occurred_day_offset, e.occurred_weekday)
        tok = tok + f"@{tag}{e.occurred_at[:2]}"
        # Issue #1737: an einem anderen Tag steht die Spanne NACH dem Tagesbezug-
        # Token -- `@Do13-17` waere formgleich zur Fensterform der amtlichen
        # Warnung (`Do12-22`, #2020 AC-14).
        if span:
            tok += f" {span}"
    pos = (location_positions or {}).get(e.location_label or "")
    return f"{pos}:{tok}" if pos else tok


def _sms_day_prefix(day_offset: int, weekday: str | None) -> str:
    """Wochentagskuerzel vor der Stunde -- nur bei Versatz != 0 (am Versandtag
    entfaellt es ersatzlos, dieselbe Regel wie #1948 S5)."""
    return (weekday or "") if day_offset else ""


def _sms_rest_token(e: AlertEvent) -> str | None:
    """Issue #2020 Scheibe 2: `Rest{mm}@{HH}` -- die Restmenge ab jetzt und
    ihr Ende als Kompakt-Token. `None` fuer Metriken ohne Restmenge.

    Ohne Endzeit steht `Rest0` OHNE Zeit-Suffix: die Kurzform verschweigt den
    Sachverhalt nicht, sie kuerzt ihn nur.
    """
    if e.remaining_mm is None:
        return None
    tok = f"Rest{int(round(e.remaining_mm))}"
    if e.remaining_until_time:
        tag = _sms_day_prefix(
            e.remaining_until_day_offset, e.remaining_until_weekday,
        )
        tok += f"@{tag}{e.remaining_until_time[:2]}"
    return tok


# Issue #2018 (AC-B4/AC-B11): Kompakt-Token der Nachtragsmeldung fuer SMS,
# Kurzstil-Telegram und Premium-SMS -- die drei Kanaele, die denselben
# SMS-Text senden. Bewusst OHNE "-": die SMS-Grammatik ueberlaedt den
# Bindestrich bereits zweifach (Stufen-Rueckfall `LEVELS.get(..., "-")` UND
# der "->"-Pfeil bei Stufenaenderungen); eine dritte Bedeutung waere im
# Fliesstext nicht mehr auseinanderzuhalten.
_ADDENDUM_SMS_PREFIX = "Erg "


def render_sms(
    msg: AlertMessage,
    limit: int = 140,
    location_positions: dict[str, int] | None = None,
    addendum: bool = False,
) -> str:
    """Kurznachricht ueber alle SMS-artigen Kanaele.

    Issue #2018: traegt die Meldung eine Nachtrags-Bezugszeile
    (`msg.addendum_reference`) -- oder verlangt ein Aufrufer `addendum=True`
    ausdruecklich --, wird der Kern-Text mit einem um die Praefixlaenge
    VERKLEINERTEN Limit gerendert und das Praefix danach vorangestellt. Die
    Laengen-Zusicherung entsteht damit aus der bestehenden Kuerzungslogik,
    nicht aus einer zweiten Laengenpruefung."""
    if addendum or msg.addendum_reference is not None:
        kern = _render_sms_body(
            msg, limit - len(_ADDENDUM_SMS_PREFIX), location_positions,
        )
        return _ADDENDUM_SMS_PREFIX + kern
    return _render_sms_body(msg, limit, location_positions)


def _render_sms_body(
    msg: AlertMessage,
    limit: int = 140,
    location_positions: dict[str, int] | None = None,
) -> str:
    """Längenbasierte Kürzung: Kopf immer; Tokens nach severity, solange das
    Ergebnis inkl. evtl. ' +k'-Suffix ≤limit bleibt; Rest → ' +k'.

    Issue #1467 S2 AG3b: `location_positions` ist NEU und defaultiert — ohne
    ihn bleibt die Ausgabe byte-identisch (AC-26-Zusicherung fuer SMS). Gesetzt
    wird er ausschliesslich vom Ortsvergleich-Änderungspfad; dort fuehrt er
    die Ortsposition als Zahl an jedem Ereignis-Token (`_sms_token`).

    Korrektur-Runde 2026-08-04 (K-1/K-2, PO-Entscheidung): ist der Parameter
    gesetzt, entfaellt der Kopf VOLLSTAENDIG — kein Ortsname, keine
    Ortsliste, kein Vergleichsname. DIE ZAHL IST DIE ORTSANGABE; ein Kopf,
    der die Orte noch einmal ausschreibt, frisst genau das Laengenbudget, das
    die Zahlenkodierung freischaufeln soll. Das gilt fuer BEIDE Kopf-Zweige:
    im Mehr-Orte-Fall stand die Ortsliste doppelt (`trip_short` UND
    `location_label` tragen denselben `collective_label`,
    `project.py:217-220`), im Ein-Ort-Fall der Name zweimal hintereinander
    (`'Graz Graz: '`). Aufrufer OHNE `location_positions` UND OHNE
    `location_label`/`multi_location` (Trip-Radar, Compare-Radar, amtliche
    Warnungen) behalten ihren Kopf byte-identisch.

    Issue #1935/#1779 (E3/E4): der Trip-Δ-Kopf (kein `location_positions`,
    kein `multi_location`, kein `msg.location_label`) spricht seither
    dieselbe Ortssprache wie Betreff/E-Mail/Telegram (`_km_str`/
    `format_alert_location`) statt einer km-Spanne, und fuehrt keinen
    Trip-Namen mehr -- PO-Entscheid 2026-08-17, hebt AC-5 von
    `fix_1744_alarm_format_angleichen.md` fuer diesen Pfad auf.
    """
    if msg.source is not None:
        return _render_sms_onset(msg, limit)
    if not msg.events and msg.onset_shift_events:
        return _render_sms_onset_shift_only(msg, limit)
    evs = _sorted(msg)
    trip = _ascii(msg.trip_short)[:16].rstrip(" (-_")
    # Nur der gebuendelte Mehr-Orte-Fall traegt per-Event-`location_label`
    # (`project.py:215`) — er und der Ein-Ort-Fall sind zwei VERSCHIEDENE
    # Kopf-Zweige; der Wegfall des Kopfes muss beide treffen (K-2).
    multi_location = any(e.location_label for e in evs)
    if location_positions is not None:
        # Ortsvergleich-Aenderungspfad: gar kein Kopf. Bewusst `is not None`
        # statt Wahrheitswert — auch eine leere Zuordnung (kein Ort mehr
        # aufloesbar) kommt von genau diesem Pfad und darf den Kopf nicht
        # zurueckbringen.
        head = ""
    elif multi_location:
        head = f"{_ascii(msg.location_label or msg.trip_short)[:24]}: "
    elif msg.location_label:
        head = f"{trip} {_ascii(msg.location_label)[:24]}: "
    else:
        # Issue #1935/#1779 (E3/E4): Trip-Δ-Pfad -- dieselbe Ortsaufloesung
        # wie Betreff/E-Mail/Telegram (`_km_str`), Emoji ENTFERNT statt
        # transliteriert (AC-7), kein Trip-Name mehr (AC-5).
        # Issue #2122: das Etappen-Praefix ueber ALLE Bausteine dieser
        # Nachricht (Δ-Ereignisse + Beginn-Verschiebungen)
        # -- fehlt es bei irgendeinem, entfaellt es GANZ (AC-8). Der Compare-
        # Pfad setzt `stage_number` nie -> Praefix bleibt leer (AC-9).
        prefix = _stage_prefix(list(evs) + list(msg.onset_shift_events))
        head = f"{prefix}{_ascii_alert_location(_km_str(msg))}: "
    # Issue #2020 Scheibe 2: das Restmengen-Token steht DIREKT neben dem
    # Delta-Token desselben Ereignisses -- sonst stuenden bei mehreren
    # Ereignissen Menge und Rest an unzusammenhaengenden Stellen.
    tokens: list[str] = []
    for e in evs:
        tokens.append(_sms_token(e, location_positions))
        rest = _sms_rest_token(e)
        if rest:
            tokens.append(rest)
    tokens += [_sms_onset_shift_token(oe) for oe in msg.onset_shift_events]

    kept: list[str] = []
    for tok in tokens:
        omitted = len(tokens) - len(kept) - 1  # weggelassen, wenn wir hier stoppen
        marker = f" +{omitted}" if omitted > 0 else ""
        candidate = head + " ".join(kept + [tok]) + marker
        if len(candidate) <= limit:
            kept.append(tok)
        else:
            break
    omitted = len(tokens) - len(kept)
    body = head + " ".join(kept)
    if omitted > 0:
        body += f" +{omitted}"
    # Garantie len<=limit auch im Degenerationsfall (Kopf+Suffix allein zu lang).
    return body if len(body) <= limit else body[:limit]


# GSM-7-Extension-Tabelle (Form-Feed, ^ { } \ [ ~ ] | €) ist zwar
# GSM-7-kodierbar, kostet aber ZWEI Septets je Zeichen (ESC-Fluchtsequenz,
# GSM 03.38) -- eine stille Budget-Verletzung. Zeichenliste dupliziert aus
# tests/tdd/_gsm7_charset.py::GSM7_EXTENDED_TWO_SEPTET_CHARS (Quelle der
# Wahrheit fuer die Test-Verifikation), Issue #1796.
_ASCII_EXTENSION_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("[", "("),
    ("]", ")"),
    ("{", "("),
    ("}", ")"),
    ("\\", "/"),
    ("|", "-"),
    ("~", "-"),
    ("^", ""),
    ("€", "EUR"),
    ("\x0c", ""),
)


def _ascii(text: str) -> str:
    text = (
        text.replace("–", "-").replace("−", "-").replace("°", "")
        .replace("↑", "+").replace("↓", "-")
    )
    for bad, good in _ASCII_EXTENSION_REPLACEMENTS:
        text = text.replace(bad, good)
    return fold_ascii(text)


def _strip_pictographs(text: str) -> str:
    """Entfernt Piktogramm-Zeichen (Unicode-Kategorie 'So', z.B. 🏁) samt
    einem direkt folgenden Leerzeichen (Issue #1935/#1779 AC-7): das Emoji
    wird ENTFERNT statt transliteriert -- `fold_ascii()`/`anyascii` wuerde
    sonst z.B. ':checkered_flag:' bauen, was auf einer SMS unlesbar waere."""
    out: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if unicodedata.category(ch) == "So":
            i += 1
            if i < len(text) and text[i] == " ":
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _ascii_alert_location(text: str) -> str:
    """SMS-Kopf-Ortstext (Issue #1935/#1779 AC-5/AC-7/AC-8): Piktogramme
    ZUERST entfernen, danach dieselbe ASCII/GSM-7-Faltung wie jeder andere
    SMS-Text -- sonst faellt die Reihenfolge in `fold_ascii()`.

    Issue #1948 S5 (AC-14): "Segment N" wird im SMS-Kopf zu "Seg N" gekuerzt.
    Diese Funktion ist SMS-only-Konsument (Onset-, Onset-Shift-, Trip-Delta-
    SMS) -- die Kurzform an EINER Stelle trifft alle Alarm-SMS-Zweige, waehrend
    E-Mail/Telegram/Betreff (`_km_str`/`_km_str_onset`) "Segment" weiter
    ausschreiben."""
    return _ascii(_strip_pictographs(text)).replace("Segment ", "Seg ")


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# Kompat-Shim: alter knapper #816-Abweichungs-Alert (render_deviation_alert),
# weiter genutzt von 3 Bestandstests; Verhalten unverändert.
def _legacy_line(change, segments, *, tz, stage_label=None, lang: Lang = "de") -> str:
    from output.renderers.email.helpers import build_segment_label
    info = get_label_for_field(change.metric)
    name = info[0] if info else change.metric
    unit = info[2] if info else ""
    old_fmt = format_metric_value(unit, change.old_value, lang=lang) if info else f"{change.old_value:.1f}"
    new_fmt = format_metric_value(unit, change.new_value, lang=lang) if info else f"{change.new_value:.1f}"
    seg = build_segment_label(change, segments, tz=tz, stage_label=stage_label)
    return f"{name}  {old_fmt} → {new_fmt}  ({seg})"


def render_deviation_alert(
    changes, segments, trip_name, *,
    tz, stage_label=None, sent_at=None, lang: Lang = "de",
) -> tuple[str, str]:
    """Kompat: knapper #816-Abweichungs-Alert (html, plain), severity-sortiert.

    Issue #1402: `tz` ist PFLICHTPARAMETER — alle drei Bestandstests
    uebergeben bereits immer eine echte Zone.
    """
    from utils.timezone import local_fmt
    ordered = sorted(changes, key=lambda c: abs(c.delta) / (abs(c.threshold) or 1.0), reverse=True)
    stamp = local_fmt(sent_at or datetime.now(timezone.utc), tz)
    footer = (f"{t('alarm.mail.stand', lang, stand=stamp)} · "
              f"{t('alarm.mail.verglichen', lang, referenz=t('alarm.mail.letztes_briefing', lang))}")
    header = t("alarm.abweichung.legacy_kopf", lang)
    lines = [_legacy_line(c, segments, tz=tz, stage_label=stage_label, lang=lang) for c in ordered]
    plain = "\n".join([header, "", *lines, "", footer])
    rows = "".join(f"<tr><td style=\"padding:4px 0;\">{_esc(line)}</td></tr>" for line in lines)
    html = (
        "<html><body style=\"font-family:sans-serif;\">"
        f"<h2 style=\"margin:0 0 12px;\">{_esc(header)}</h2>"
        f"<table style=\"border-collapse:collapse;\">{rows}</table>"
        f"<p style=\"color:#555;margin-top:16px;\">{_esc(footer)}</p>"
        "</body></html>"
    )
    return html, plain
