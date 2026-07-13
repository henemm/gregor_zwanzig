"""Amtliche Warnungen: korrekter Ort JE WARNUNG in SMS und Telegram (#1249).

SPEC: docs/specs/modules/fix_1249_sms_telegram_scope.md (AC-1 .. AC-11)
KONTEXT: docs/context/fix-1249-sms-telegram-scope.md

RED-Phase — das fehlende Verhalten:
- AC-1/AC-4/AC-11: `render_official_alert_sms` haengt im uniform-LEVEL-Zweig
  EINEN gemeinsamen Ortszusatz (`suffix = f", {leading.sms_scope}"`) ans Ende,
  auch wenn die Warnungen unterschiedliche Umfaenge haben. Der Empfaenger liest
  ", nur Toulon" und darueber vier Gefahren, von denen zwei Toulon nicht
  betreffen. Der uniform-Schalter dieser Funktion prueft nur die STUFE
  (`alert.level`), nicht den UMFANG (`_uniform_scope`).
- AC-6/AC-8/AC-11: `render_official_alert_telegram` nennt in der Kopfzeile
  bedingungslos `leading.scope_label`; die Warnungszeilen tragen gar keinen
  Umfang.
- AC-10: die Telegram-Zeilen nutzen `_hazard_display` (generisches Typ-Wort,
  "Zugang gesperrt") statt `_display_label` ("Zugang eingeschraenkt — Monts
  Toulonnais") und widersprechen damit der Mail (#1238).

Non-Regression (JETZT SCHON GRUEN, muss gruen bleiben): AC-2, AC-3, AC-5,
AC-7, AC-9 — bei EINHEITLICHEM Umfang bleiben SMS und Telegram bit-identisch.
Die eingefrorenen Erwartungs-Strings wurden am echten Renderer im Ist-Stand
ermittelt (nicht geraten).

Mock-frei: echte `OfficialAlert`-DTOs durch die echten Builder
(`build_compare_official_alert_notices`, `build_official_alert_notices` --
nur sie setzen `scope_ids`, die `_uniform_scope` braucht) und die echten
Renderer (`render_official_alert_sms`, `render_official_alert_telegram`).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

from services.official_alerts.models import OfficialAlert

UTC = timezone.utc
FR_FROM = datetime(2026, 7, 10, 6, 0, tzinfo=UTC)
FR_TO = datetime(2026, 7, 10, 20, 0, tzinfo=UTC)
SA_FROM = datetime(2026, 7, 11, 15, 0, tzinfo=UTC)
SA_TO = datetime(2026, 7, 11, 21, 0, tzinfo=UTC)

# Preset "Le Var": vier verglichene Orte (der reale Staging-Fall).
LOC_IDS = ["toulon", "hyeres", "draguignan", "frejus"]
LOC_NAMES = {
    "toulon": "Toulon", "hyeres": "Hyeres",
    "draguignan": "Draguignan", "frejus": "Frejus",
}
LOC_DISPLAY = tuple(LOC_NAMES.values())

SMS_LIMIT = 140  # Default von `render_official_alert_sms` (GSM-7/ASCII)


def _alert(level, hazard, label, vf=None, vt=None, *, region=None,
           source="vigilance", dedup_id=None) -> OfficialAlert:
    return OfficialAlert(
        source=source, hazard=hazard, level=level, label=label,
        valid_from=vf, valid_to=vt, region_label=region, dedup_id=dedup_id,
    )


def _compare_notices(tagged, all_ids=None, names=None):
    from output.renderers.alert.official_alerts import build_compare_official_alert_notices
    return build_compare_official_alert_notices(
        all_ids or LOC_IDS, names or LOC_NAMES, tagged,
    )


def _sms(notices, prefix="GZ", limit=SMS_LIMIT) -> str:
    from output.renderers.alert.official_alerts import render_official_alert_sms
    return render_official_alert_sms(notices, sms_prefix=prefix, limit=limit, tz=UTC)


def _telegram(notices, prefix="Le Var") -> str:
    from output.renderers.alert.official_alerts import render_official_alert_telegram
    return render_official_alert_telegram(
        notices, prefix=prefix, source_label="Météo-France", tz=UTC,
    )


def _ordered(notices):
    from output.renderers.alert.official_alerts import _sort_notices
    return _sort_notices(notices)


def _tg_parts(notices):
    """(Kopfzeile, Warnungszeilen) der gerenderten Telegram-Nachricht."""
    lines = _telegram(notices).split("\n")
    return lines[0], lines[1:1 + len(notices)]


# ---------------------------------------------------------------------------
# Fixtures — der reale Staging-Fall (vier Warnungen, VIER verschiedene Umfaenge)
# ---------------------------------------------------------------------------

def _mixed_scope_notices():
    """Vier Warnungen gleicher Stufe (ORANGE) mit UNTERSCHIEDLICHEM Umfang.

    Gleiche Stufe -> `render_official_alert_sms` nimmt den uniform-Zweig, in dem
    heute EIN gemeinsamer Ortszusatz (", nur Toulon") fuer alle vier gilt.
    Umfaenge: nur Toulon / Toulon+Hyeres / nur Draguignan / alle Orte.
    """
    tagged = [
        (_alert(3, "access_ban", "Zugang eingeschränkt — Monts Toulonnais",
                source="massif_closure", dedup_id="monts_toulonnais"), ["toulon"]),
        (_alert(3, "wildfire_risk", "Waldbrand-Gefahr — Stufe 3", FR_FROM, FR_TO,
                region="Var cotier", source="meteo_forets"), ["toulon", "hyeres"]),
        (_alert(3, "thunderstorm", "Gewitter", SA_FROM, SA_TO,
                region="Var interieur"), ["draguignan"]),
        (_alert(3, "extreme_heat", "Extreme Hitze", SA_FROM, SA_TO,
                region="Var"), LOC_IDS),
    ]
    return _compare_notices(tagged)


def _uniform_scope_same_level_notices():
    """Zwei Warnungen, gleiche Stufe, GLEICHER Umfang (Toulon + Hyeres).

    Bewusst mit einer Gefahr mit REICHEM Quell-Label ("Extreme Hitze" statt des
    Typ-Worts "Hitze") — so prueft AC-9 den echten Konfliktfall mit AC-10 (S5,
    `_display_label`) statt ihm auszuweichen: die Umfangs-Behandlung bleibt
    bit-identisch, die Gefahren-Bezeichnung aendert sich gewollt."""
    tagged = [
        (_alert(3, "extreme_heat", "Extreme Hitze", FR_FROM, FR_TO, region="Var"),
         ["toulon", "hyeres"]),
        (_alert(3, "wind_gust", "Sturm", SA_FROM, SA_TO, region="Kueste"),
         ["toulon", "hyeres"]),
    ]
    return _compare_notices(tagged)


def _uniform_scope_mixed_level_notices():
    """Zwei Warnungen, GEMISCHTE Stufe, GLEICHER Umfang (alle Orte)."""
    tagged = [
        (_alert(3, "wildfire_risk", "Waldbrand-Gefahr — Stufe 3",
                region="Var cotier", source="meteo_forets"), LOC_IDS),
        (_alert(2, "extreme_heat", "Extreme Hitze", SA_FROM, SA_TO,
                region="Var"), LOC_IDS),
    ]
    return _compare_notices(tagged)


def _trip_mixed_scope_notices():
    """Trip-Pfad: zwei Warnungen gleicher Stufe ueber VERSCHIEDENE Segmente."""
    from app.trip import Stage, Trip, Waypoint
    from output.renderers.alert.official_alerts import build_official_alert_notices

    stage = Stage(
        id="s1", name="Tag 1", date=date(2026, 7, 10),
        waypoints=[
            Waypoint(id="w1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0),
            Waypoint(id="w2", name="Huette", lat=47.1, lon=11.1, elevation_m=1400.0),
            Waypoint(id="w3", name="Pass", lat=47.2, lon=11.2, elevation_m=1800.0),
            Waypoint(id="w4", name="Ziel", lat=47.3, lon=11.3, elevation_m=1200.0),
        ],
    )
    trip = Trip(id="tdd-1249-trip", name="KHW 403", stages=[stage])
    tagged = [
        (_alert(3, "access_ban", "Zugang eingeschränkt — Monts Toulonnais",
                source="massif_closure", dedup_id="monts_toulonnais"), ["1"]),
        (_alert(3, "thunderstorm", "Gewitter", SA_FROM, SA_TO, region="Var"),
         ["3", "Ziel"]),
    ]
    return build_official_alert_notices(trip, tagged)


def _access_ban_with_time_notices():
    """Eine Zugangssperre mit REICHEM Label (traegt selbst einen Gedankenstrich)
    UND bekannter Gueltigkeit -- der Fall, in dem F002 (Trennzeichen-Kollision)
    zuschlaegt, wenn F001 (fehlende Zeit) den Fall nicht schon eliminiert."""
    tagged = [
        (_alert(3, "access_ban", "Zugang eingeschränkt — Monts Toulonnais",
                FR_FROM, FR_TO, source="massif_closure",
                dedup_id="monts_toulonnais"), ["toulon"]),
    ]
    return _compare_notices(tagged)


def _huge_location_notices():
    """Eine Warnung, deren Ortsname (nutzereingegeben, im Modell nicht
    laengenbegrenzt) so lang ist, dass Kopf + Token + Ort das 140-Zeichen-
    SMS-Budget sprengt -- der Adversary-Fund F004 (CRITICAL, Runde 3): ohne
    Rueckfallebene wuerde `_sms_pack` hier `kept=[]` liefern (SMS ganz ohne
    Inhalt)."""
    huge = (
        "Saint-Julien-en-Vercors-les-Bains-sur-Mer-du-Grand-Massif-Central-"
        "Occitan-Provence-Alpes-Cote-Azur-Region-Administrative-Territoire"
    )
    ids = ["a", "b"]
    names = {"a": huge, "b": "Petitville"}
    tagged = [
        (_alert(3, "extreme_heat", "Extreme Hitze", SA_FROM, SA_TO, region="Var"), ["a"]),
    ]
    return _compare_notices(tagged, all_ids=ids, names=names)


def _location_longer_than_limit_notices():
    """Extremfall: EIN einziger Ortsname, laenger als das GESAMTE SMS-Limit
    (140 Zeichen) -- selbst ein Wortgrenzen-gekuerzter Ort wuerde keinen
    sinnvollen Rest-Platz fuer Kopf/Kuerzel lassen. Muss trotzdem eine
    gueltige, nicht-leere SMS ergeben (Stufe 2: Ort ganz weglassen)."""
    huge = "X" * 250
    ids = ["a", "b"]
    names = {"a": huge, "b": "Petitville"}
    tagged = [
        (_alert(3, "extreme_heat", "Extreme Hitze", SA_FROM, SA_TO, region="Var"), ["a"]),
    ]
    return _compare_notices(tagged, all_ids=ids, names=names)


def _overflow_notices():
    """Fuenf Warnungen gleicher Stufe, je EIN langer Ortsname -> mit Ort je
    Warnung passt nicht alles ins 140-Zeichen-Budget."""
    ids = ["a", "b", "c", "d", "e"]
    names = {
        "a": "Saint-Raphael-les-Bains", "b": "Villeneuve-Loubet-Plage",
        "c": "Chateauneuf-Grasse", "d": "Roquebrune-sur-Argens",
        "e": "La Croix-Valmer",
    }
    tagged = [
        (_alert(3, "access_ban", "Zugang eingeschränkt — Massif Central",
                source="massif_closure", dedup_id="massif_a"), ["a"]),
        (_alert(3, "wildfire_risk", "Waldbrand-Gefahr — Stufe 3", FR_FROM, FR_TO,
                region="R1", source="meteo_forets"), ["b"]),
        (_alert(3, "thunderstorm", "Gewitter", SA_FROM, SA_TO, region="R2"), ["c"]),
        (_alert(3, "wind_gust", "Sturm", SA_FROM, SA_TO, region="R3"), ["d"]),
        (_alert(3, "rain", "Starkregen", SA_FROM, SA_TO, region="R4"), ["e"]),
    ]
    return _compare_notices(tagged, all_ids=ids, names=names)


# ---------------------------------------------------------------------------
# AC-1 — SMS: jede Warnung nennt ihren EIGENEN Ort
# ---------------------------------------------------------------------------

def test_ac1_sms_carries_own_scope_per_warning():
    """AC-1: Given mehrere amtliche Warnungen mit unterschiedlichem betroffenem
    Umfang / When die SMS gerendert wird / Then nennt jede in der SMS enthaltene
    Warnung ihren eigenen Ort statt eines einzigen, gemeinsamen Ortszusatzes am
    Ende."""
    notices = _mixed_scope_notices()
    sms = _sms(notices)

    # Alle vier Tokens passen ins Budget -> jeder Umfang MUSS erscheinen.
    assert len(sms) <= SMS_LIMIT, f"SMS ueberschreitet das Limit: {len(sms)}"
    for n in notices:
        assert n.sms_scope in sms, (
            f"Umfang {n.sms_scope!r} der Warnung {n.alert.label!r} fehlt in der "
            f"SMS — nur der Ort der schwersten Warnung wird genannt: {sms!r}"
        )

    # Kein gemeinsamer Ortszusatz am Ende, der faelschlich fuer alle gilt.
    leading = _ordered(notices)[0]
    assert not sms.endswith(f", {leading.sms_scope}"), (
        f"SMS endet mit gemeinsamem Ortszusatz {leading.sms_scope!r}, der nur "
        f"fuer die schwerste Warnung gilt: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-2 — SMS Non-Regression: einheitlicher Umfang -> bit-identisch
# ---------------------------------------------------------------------------

def test_ac2_sms_uniform_scope_same_level_bit_identical():
    """AC-2 (Non-Regression, JETZT SCHON GRUEN): Given mehrere amtliche
    Warnungen, die alle denselben betroffenen Umfang haben (und dieselbe Stufe)
    / When die SMS gerendert wird / Then bleibt ihr Text bit-identisch zum Stand
    vor diesem Fix (gemeinsamer Ortszusatz am Ende)."""
    sms = _sms(_uniform_scope_same_level_notices())
    assert sms == "GZ AMT ORANGE2/3: HZ Fr06-20 + ST Sa15-21, Toulon+Hyeres", (
        f"SMS bei einheitlichem Umfang veraendert: {sms!r}"
    )


def test_ac2_sms_uniform_scope_mixed_level_bit_identical():
    """AC-2 (Non-Regression fuer die UMFANGS-Behandlung -- der Zeit-Platzhalter
    "?" ist durch F003 (Runde 2, s. Changelog) entfallen, unabhaengig von AC-2):
    Given Warnungen mit gleichem Umfang, aber gemischter Stufe / When die SMS
    gerendert wird / Then bleibt der Umfang je Token wie im Bestand (Stufe +
    Ort pro Warnung), ohne sinnfreies "?"-Zeit-Token bei fehlender Zeit."""
    sms = _sms(_uniform_scope_mixed_level_notices())
    assert sms == "GZ AMT: WB ORANGE alleOrte + HZ GELB Sa15-21 alleOrte", (
        f"SMS bei einheitlichem Umfang + gemischter Stufe veraendert: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-3 — SMS Zeichenlimit
# ---------------------------------------------------------------------------

def test_ac3_sms_never_exceeds_limit():
    """AC-3 (Non-Regression, JETZT SCHON GRUEN): Given eine SMS mit mehreren
    Warnungen und je eigenem Ortszusatz / When die SMS gerendert wird / Then
    ueberschreitet sie das konfigurierte Zeichenlimit (Default 140, GSM-7/ASCII)
    niemals."""
    for label, notices in (
        ("mixed scope", _mixed_scope_notices()),
        ("overflow", _overflow_notices()),
    ):
        sms = _sms(notices)
        assert len(sms) <= SMS_LIMIT, (
            f"SMS ({label}) ueberschreitet {SMS_LIMIT} Zeichen: {len(sms)} — {sms!r}"
        )
        assert sms.isascii(), f"SMS ({label}) ist nicht ASCII/GSM-7: {sms!r}"


# ---------------------------------------------------------------------------
# AC-4 — SMS Ueberlauf: schwaechere Warnungen fallen GANZ weg, +N stimmt
# ---------------------------------------------------------------------------

def test_ac4_sms_overflow_drops_weaker_warnings_whole():
    """AC-4: Given mehr Warnungen mit unterschiedlichem Umfang, als vollstaendig
    samt Ort ins Zeichenlimit passen / When die SMS gerendert wird / Then fallen
    die schwaecheren Warnungen als vollstaendige Eintraege weg (mit "+N"-Hinweis),
    waehrend die schwerste Warnung inklusive ihres Ortes vollstaendig erhalten
    bleibt."""
    notices = _overflow_notices()
    sms = _sms(notices)
    ordered = _ordered(notices)

    assert len(sms) <= SMS_LIMIT, f"SMS ueberschreitet das Limit: {len(sms)} — {sms!r}"

    # Schwerste Warnung: Kuerzel UND Ort vollstaendig erhalten.
    leading = ordered[0]
    assert leading.sms_scope in sms, (
        f"Ort {leading.sms_scope!r} der schwersten Warnung fehlt in der SMS: {sms!r}"
    )

    # "+N"-Marker am Ende -> nichts wurde mitten im Token abgeschnitten.
    m = re.search(r" \+(\d+)$", sms)
    assert m is not None, (
        f"'+N'-Auslassungsmarker fehlt am Ende — mit Ort je Warnung kann nicht "
        f"alles ins Limit passen: {sms!r}"
    )
    omitted = int(m.group(1))

    # Behaltene Warnungen = die, deren Ort vollstaendig in der SMS steht.
    kept = [n for n in ordered if n.sms_scope in sms]
    assert len(kept) >= 2, (
        f"Nur {len(kept)} Warnung(en) samt Ort behalten — das Budget traegt mehr: {sms!r}"
    )
    assert omitted == len(notices) - len(kept), (
        f"'+{omitted}' beziffert die weggelassenen Warnungen falsch: "
        f"{len(notices)} Warnungen, {len(kept)} behalten — {sms!r}"
    )

    # Kein Ort taucht nur als Fragment auf (Token ganz oder gar nicht). Geprueft
    # wird der UNTERSCHEIDENDE Ortsname: das gemeinsame Praefix "nur " traegt
    # keine Ortsinformation und steht legitim auch in den behaltenen Tokens.
    for n in ordered:
        if n.sms_scope in sms:
            continue
        name = n.sms_scope[4:] if n.sms_scope.startswith("nur ") else n.sms_scope
        for cut in range(4, len(name)):
            assert name[:cut] not in sms, (
                f"Ort {n.sms_scope!r} steht abgeschnitten ({name[:cut]!r}) "
                f"in der SMS: {sms!r}"
            )


# ---------------------------------------------------------------------------
# AC-5 — SMS Non-Regression: Gefahren-Kuerzel unveraendert
# ---------------------------------------------------------------------------

def test_ac5_sms_hazard_shortcodes_unchanged():
    """AC-5 (Non-Regression, JETZT SCHON GRUEN): Given amtliche Warnungen
    unterschiedlicher Gefahrentypen / When die SMS gerendert wird / Then bleiben
    die verwendeten Zwei-Buchstaben-Kuerzel je Gefahrentyp identisch zum Stand
    vor diesem Fix (Hitze HZ, Gewitter TH, Zugangssperre ZG, Waldbrand WB)."""
    sms = _sms(_mixed_scope_notices())
    for code, hazard in (("ZG", "Zugangssperre"), ("WB", "Waldbrand"),
                         ("TH", "Gewitter"), ("HZ", "Hitze")):
        assert re.search(rf"(?:^|[ :]){code} ", sms), (
            f"SMS-Kuerzel {code!r} ({hazard}) fehlt/veraendert: {sms!r}"
        )
    # Der ausgeschriebene Anzeigetext gehoert NICHT in die SMS (Zeichenbudget).
    assert "Waldbrand-Gefahr" not in sms, (
        f"SMS nutzt den ausgeschriebenen Anzeigetext statt des Kuerzels: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-6 — Telegram-Kopfzeile: kein Umfang, der faelschlich fuer alle gilt
# ---------------------------------------------------------------------------

def test_ac6_telegram_head_drops_scope_when_not_uniform():
    """AC-6: Given mehrere amtliche Warnungen mit unterschiedlichem betroffenem
    Umfang / When die Telegram-Kopfzeile gerendert wird / Then nennt die
    Kopfzeile keinen Umfang mehr, der faelschlich fuer alle Warnungen gaelte."""
    notices = _mixed_scope_notices()
    head, _lines = _tg_parts(notices)

    for name in LOC_DISPLAY:
        assert name not in head, (
            f"Telegram-Kopfzeile nennt den Ort {name!r}, der nicht fuer alle "
            f"Warnungen gilt: {head!r}"
        )
    assert "nur " not in head, (
        f"Telegram-Kopfzeile nennt einen einschraenkenden Umfang: {head!r}"
    )
    # Die Stufen-Aussage bleibt erhalten.
    assert "ORANGE" in head, f"Stufen-Angabe aus der Kopfzeile verloren: {head!r}"


# ---------------------------------------------------------------------------
# AC-7 — Telegram-Kopfzeile Non-Regression: einheitlicher Umfang bit-identisch
# ---------------------------------------------------------------------------

def test_ac7_telegram_head_uniform_scope_same_level_bit_identical():
    """AC-7 (Non-Regression, JETZT SCHON GRUEN): Given Warnungen mit demselben
    betroffenen Umfang (gleiche Stufe) / When die Telegram-Kopfzeile gerendert
    wird / Then bleibt sie bit-identisch zum Stand vor diesem Fix und nennt
    weiterhin den gemeinsamen Umfang."""
    head, _lines = _tg_parts(_uniform_scope_same_level_notices())
    assert head == "<b>Le Var · Toulon, Hyeres · Warnstufe ORANGE (2/3)</b>", (
        f"Telegram-Kopfzeile bei einheitlichem Umfang veraendert: {head!r}"
    )


def test_ac7_telegram_head_uniform_scope_mixed_level_bit_identical():
    """AC-7 (Non-Regression, JETZT SCHON GRUEN): Given Warnungen mit demselben
    betroffenen Umfang (gemischte Stufe) / When die Telegram-Kopfzeile gerendert
    wird / Then bleibt sie bit-identisch zum Stand vor diesem Fix."""
    head, _lines = _tg_parts(_uniform_scope_mixed_level_notices())
    assert head == "<b>Le Var · alle Orte · höchste Stufe ORANGE (2/3)</b>", (
        f"Telegram-Kopfzeile bei einheitlichem Umfang veraendert: {head!r}"
    )


# ---------------------------------------------------------------------------
# AC-8 — Telegram-Warnungszeilen: eigener Umfang je Zeile
# ---------------------------------------------------------------------------

def test_ac8_telegram_lines_carry_own_scope():
    """AC-8: Given mehrere amtliche Warnungen mit unterschiedlichem betroffenem
    Umfang / When die Telegram-Warnungszeilen gerendert werden / Then traegt jede
    Zeile den Umfang genau der Warnung, die sie beschreibt (und die Umfaenge
    unterscheiden sich zwischen den Zeilen)."""
    notices = _mixed_scope_notices()
    ordered = _ordered(notices)
    _head, lines = _tg_parts(notices)

    assert len(lines) == len(ordered), (
        f"Erwartet {len(ordered)} Warnungszeilen, erhalten {len(lines)}: {lines!r}"
    )
    for n, line in zip(ordered, lines):
        assert n.scope_label in line, (
            f"Telegram-Zeile zur Warnung {n.alert.label!r} nennt ihren Umfang "
            f"{n.scope_label!r} nicht: {line!r}"
        )
    assert len({n.scope_label for n in ordered}) == len(ordered), (
        "Fixture-Fehler: die Umfaenge sind nicht paarweise verschieden"
    )


# ---------------------------------------------------------------------------
# AC-9 — Telegram-Zeilen Non-Regression: einheitlicher Umfang -> schlank
# ---------------------------------------------------------------------------

def test_ac9_telegram_lines_uniform_scope_stay_lean():
    """AC-9 (Spec-Praezisierung 2026-07-13, s. Changelog Runde 1+2): Given
    Warnungen, die alle denselben betroffenen Umfang haben / When die
    Telegram-Warnungszeilen gerendert werden / Then bleibt ihre UMFANGS-
    Behandlung bit-identisch zum Stand vor diesem Fix: keine Zeile wiederholt
    den Umfang, er steht einmalig in der Kopfzeile.

    Die Fixture traegt bewusst eine Gefahr mit REICHEM Quell-Label ("Extreme
    Hitze" statt Typ-Wort "Hitze") — genau der Fall, in dem AC-10 (S5,
    `_display_label`) die Gefahren-Bezeichnung GEWOLLT aendert. AC-9 sichert die
    Umfangs-Behandlung, nicht die Bezeichnung; beide Zusagen sind hier zugleich
    pruefbar, statt einander auszuweichen.

    Trennzeichen Label/Zeit ist "·" statt "—" (F002, Runde 2, s. Changelog) —
    ein Gedankenstrich im Label selbst (z.B. bei access_ban) wuerde sonst mit
    dem Zeilen-Trenner kollidieren."""
    notices = _uniform_scope_same_level_notices()
    telegram = _telegram(notices)
    assert telegram == (
        "<b>Le Var · Toulon, Hyeres · Warnstufe ORANGE (2/3)</b>\n"
        "🟠 Extreme Hitze · Fr 10.07. · 06:00–20:00\n"
        "🟠 Sturm · Sa 11.07. · 15:00–21:00\n"
        "Météo-France"
    ), f"Telegram bei einheitlichem Umfang veraendert: {telegram!r}"

    _head, lines = _tg_parts(notices)
    for line in lines:
        for name in LOC_DISPLAY:
            assert name not in line, (
                f"Warnungszeile wiederholt den Umfang {name!r}, obwohl er "
                f"einheitlich ist und schon in der Kopfzeile steht: {line!r}"
            )
    # Die Zeilen bestehen ausschliesslich aus Stufen-Emoji + Mail-Bezeichnung +
    # Gueltigkeit — kein Umfangs-Anhang wie im uneinheitlichen Fall (AC-8).
    from output.renderers.alert.official_alerts import _display_label, _format_validity
    for n, line in zip(_ordered(notices), lines):
        expected = f"🟠 {_display_label(n.alert)} · {_format_validity(n.alert, UTC)}"
        assert line == expected, (
            f"Umfangs-Behandlung der Zeile veraendert (erwartet schlank ohne "
            f"Umfang): {line!r} != {expected!r}"
        )


# ---------------------------------------------------------------------------
# AC-10 — Telegram-Gefahrenbezeichnung = die der Mail (`_display_label`)
# ---------------------------------------------------------------------------

def test_ac10_telegram_line_uses_display_label_like_mail():
    """AC-10: Given eine amtliche Warnung mit einem reicheren Quell-Label (eine
    Zugangssperre mit Massiv-Namen) / When eine Telegram-Warnungszeile gerendert
    wird / Then zeigt sie dieselbe Gefahrenbezeichnung wie die entsprechende
    E-Mail-Warnung (`_display_label`), statt eines generischen Typ-Worts
    (`_hazard_display`)."""
    from output.renderers.alert.official_alerts import _display_label, _hazard_display

    notices = _mixed_scope_notices()
    ordered = _ordered(notices)
    _head, lines = _tg_parts(notices)

    ban = next(n for n in ordered if n.alert.hazard == "access_ban")
    ban_line = lines[ordered.index(ban)]
    expected = _display_label(ban.alert)  # "Zugang eingeschränkt — Monts Toulonnais"
    generic = _hazard_display(ban.alert)[0]  # "Zugang gesperrt"

    assert expected in ban_line, (
        f"Telegram-Zeile zeigt nicht die Mail-Bezeichnung {expected!r}: {ban_line!r}"
    )
    assert generic not in ban_line, (
        f"Telegram-Zeile zeigt weiterhin das generische Typ-Wort {generic!r}: {ban_line!r}"
    )

    heat = next(n for n in ordered if n.alert.hazard == "extreme_heat")
    heat_line = lines[ordered.index(heat)]
    assert _display_label(heat.alert) in heat_line, (
        f"Telegram-Zeile zeigt nicht 'Extreme Hitze' wie die Mail: {heat_line!r}"
    )


# ---------------------------------------------------------------------------
# AC-12 (F001) — Telegram-Zeile: kein "unbekannt" bei fehlender Gueltigkeit
# ---------------------------------------------------------------------------

def test_ac12_telegram_line_omits_time_when_unknown():
    """AC-12/F001 (Runde 2 -- dieselbe PO-Beanstandung aus #1238 lebte in
    Telegram fort): Given eine amtliche Warnung ohne bekannten Gueltigkeits-
    zeitraum / When eine Telegram-Warnungszeile gerendert wird / Then entfaellt
    die Zeitangabe (samt Trennzeichen) ERSATZLOS -- kein "unbekannt" mehr,
    Gleichlauf mit der Mail (#1238 AC-7)."""
    notices = _mixed_scope_notices()
    ordered = _ordered(notices)
    _head, lines = _tg_parts(notices)

    ban = next(n for n in ordered if n.alert.hazard == "access_ban")
    ban_line = lines[ordered.index(ban)]
    assert "unbekannt" not in ban_line, (
        f"Telegram-Zeile zeigt weiterhin den Platzhalter 'unbekannt': {ban_line!r}"
    )

    # Non-Regression: Warnung MIT bekannter Zeit zeigt sie unveraendert.
    from output.renderers.alert.official_alerts import _format_validity
    heat = next(n for n in ordered if n.alert.hazard == "extreme_heat")
    heat_line = lines[ordered.index(heat)]
    assert _format_validity(heat.alert, UTC) in heat_line, (
        f"Telegram-Zeile einer Warnung MIT Zeit verliert die Zeitangabe: {heat_line!r}"
    )


# ---------------------------------------------------------------------------
# AC-13 (F002) — Telegram-Zeile: Trennzeichen kollidiert nicht mit Label-Strich
# ---------------------------------------------------------------------------

def test_ac13_telegram_line_separator_does_not_collide_with_label_dash():
    """AC-13/F002 (Runde 2): Given eine Warnung mit einem reichen Quell-Label,
    das selbst einen Gedankenstrich traegt, UND bekannter Gueltigkeit / When
    eine Telegram-Warnungszeile gerendert wird / Then trennt die Zeile Label
    und Zeitangabe mit einem Zeichen, das nicht mit dem Gedankenstrich im Label
    kollidiert -- die Zeile enthaelt hoechstens den EINEN Gedankenstrich, der
    schon im Label selbst steht."""
    from output.renderers.alert.official_alerts import _display_label

    notices = _access_ban_with_time_notices()
    _head, lines = _tg_parts(notices)
    line = lines[0]
    label = _display_label(notices[0].alert)

    assert label in line, f"Telegram-Zeile zeigt nicht das reiche Label: {line!r}"
    assert line.count("—") == label.count("—"), (
        f"Zeilen-Trenner kollidiert mit dem Gedankenstrich im Label: {line!r}"
    )


# ---------------------------------------------------------------------------
# AC-14 (F003) — SMS-Token: kein "?"-Platzhalter bei fehlender Gueltigkeit
# ---------------------------------------------------------------------------

def test_ac14_sms_token_omits_placeholder_when_time_unknown():
    """AC-14/F003 (Runde 2): Given eine amtliche Warnung ohne bekannten
    Gueltigkeitszeitraum / When die SMS gerendert wird / Then enthaelt ihr
    Token kein Zeit-Platzhalterzeichen ("?") mehr, sondern laesst die
    Zeitangabe ersatzlos weg (spart zudem Zeichen im knappen Budget)."""
    sms = _sms(_mixed_scope_notices())
    assert "?" not in sms, f"SMS enthaelt weiterhin den Zeit-Platzhalter '?': {sms!r}"

    # Non-Regression: Warnungen MIT Zeit zeigen ihre Zeitangabe unveraendert.
    for code, tag in (("WB", "Fr06-20"), ("TH", "Sa15-21"), ("HZ", "Sa15-21")):
        assert tag in sms, f"Zeitangabe {tag!r} fuer {code!r} fehlt: {sms!r}"


# ---------------------------------------------------------------------------
# AC-15 (F004, CRITICAL) — SMS: schwerste Warnung uebersteht Ort-Ueberlauf
# ---------------------------------------------------------------------------

def test_ac15_sms_survives_when_leading_location_overflows_budget():
    """AC-15/F004 (Runde 3, Adversary CRITICAL): Given eine amtliche Warnung,
    deren Ortsname so lang ist, dass Kopf + Token + Ort das 140-Zeichen-Budget
    sprengt / When die SMS gerendert wird / Then enthaelt sie weiterhin die
    Gefahr und ihre Stufe, ist NICHT leer, haelt das Limit und bricht NICHT
    mitten im Wort ab -- statt einer inhaltsleeren SMS wie 'GZ AMT:  +1'."""
    notices = _huge_location_notices()
    sms = _sms(notices)

    assert 0 < len(sms) <= SMS_LIMIT, (
        f"SMS ist leer oder ueberschreitet das Limit: {len(sms)} — {sms!r}"
    )
    assert "HZ" in sms, f"SMS verliert die Gefahr (Kuerzel 'HZ'): {sms!r}"
    assert "Sa15-21" in sms, f"SMS verliert die Zeitangabe der schwersten Warnung: {sms!r}"
    # Kein Wort-Fragment des ueberlangen Ortsnamens am Ende.
    huge_prefix = "SaintJulien"  # ASCII-/Leerzeichen-bereinigtes Praefix des Ortsnamens
    assert huge_prefix not in sms.replace(" ", ""), (
        f"SMS enthaelt ein Fragment des zu langen Ortsnamens: {sms!r}"
    )


def test_ac16_sms_survives_single_location_longer_than_entire_limit():
    """AC-16/F004 (Runde 3, Extremfall): Given ein einziger Ortsname, der
    laenger ist als das GESAMTE SMS-Limit / When die SMS gerendert wird / Then
    bleibt sie gueltig (nicht leer, haelt das Limit, kein Wort-Fragment) und
    nennt weiterhin Gefahr und Stufe."""
    notices = _location_longer_than_limit_notices()
    sms = _sms(notices)

    assert 0 < len(sms) <= SMS_LIMIT, (
        f"SMS ist leer oder ueberschreitet das Limit: {len(sms)} — {sms!r}"
    )
    assert "HZ" in sms, f"SMS verliert die Gefahr (Kuerzel 'HZ'): {sms!r}"
    assert "X" * 10 not in sms, (
        f"SMS enthaelt ein Fragment des 250 Zeichen langen Ortsnamens: {sms!r}"
    )


def test_ac15_sms_normal_location_names_unaffected():
    """AC-15 Non-Regression: Given amtliche Warnungen mit NORMAL langen
    Ortsnamen (kein Overflow-Fall) / When die SMS gerendert wird / Then bleibt
    die Ausgabe unveraendert (Ort bleibt Teil der schwersten Warnung) -- die
    Rueckfallebene greift NICHT, wenn sie nicht gebraucht wird."""
    sms = _sms(_uniform_scope_same_level_notices())
    assert sms == "GZ AMT ORANGE2/3: HZ Fr06-20 + ST Sa15-21, Toulon+Hyeres", (
        f"Normalfall (kein Overflow) veraendert durch die Rueckfallebene: {sms!r}"
    )
    sms2 = _sms(_overflow_notices())
    assert "nur Saint-Raphael-les-Bains" in sms2, (
        f"Normale Ueberlauf-Kuerzung (AC-4) durch die neue Rueckfallebene veraendert: {sms2!r}"
    )


# ---------------------------------------------------------------------------
# AC-11 — beide Pfade: Trip (Segmente) UND Ortsvergleich (Orte)
# ---------------------------------------------------------------------------

def test_ac11_trip_path_sms_and_telegram_show_own_scope():
    """AC-11 (Trip-Pfad): Given eine Trip-Standalone-Alarmmeldung mit
    unterschiedlichem betroffenem Umfang ueber mehrere Streckenabschnitte / When
    SMS und Telegram gerendert werden / Then zeigt jede Warnung ihren eigenen
    Streckenabschnitt statt eines fuer alle geltenden."""
    notices = _trip_mixed_scope_notices()
    ordered = _ordered(notices)
    leading = ordered[0]

    sms = _sms(notices, prefix="KHW")
    for n in notices:
        assert n.sms_scope in sms, (
            f"Trip-SMS nennt den Abschnitt {n.sms_scope!r} der Warnung "
            f"{n.alert.label!r} nicht: {sms!r}"
        )
    assert not sms.endswith(f", {leading.sms_scope}"), (
        f"Trip-SMS endet mit gemeinsamem Abschnitts-Zusatz {leading.sms_scope!r}: {sms!r}"
    )

    head, lines = _tg_parts(notices)
    assert leading.scope_label not in head, (
        f"Trip-Telegram-Kopfzeile nennt {leading.scope_label!r} fuer alle "
        f"Warnungen: {head!r}"
    )
    for n, line in zip(ordered, lines):
        assert n.scope_label in line, (
            f"Trip-Telegram-Zeile zur Warnung {n.alert.label!r} nennt ihren "
            f"Abschnitt {n.scope_label!r} nicht: {line!r}"
        )


def test_ac11_compare_path_sms_and_telegram_show_own_scope():
    """AC-11 (Compare-Pfad): Given eine Ortsvergleich-Standalone-Alarmmeldung mit
    unterschiedlichem betroffenem Umfang ueber mehrere verglichene Orte / When SMS
    und Telegram gerendert werden / Then zeigt jede Warnung ihren eigenen Ort —
    derselbe korrigierte Renderer-Pfad wie im Trip-Fall."""
    notices = _mixed_scope_notices()
    ordered = _ordered(notices)
    leading = ordered[0]

    sms = _sms(notices)
    for n in notices:
        assert n.sms_scope in sms, (
            f"Compare-SMS nennt den Ort {n.sms_scope!r} der Warnung "
            f"{n.alert.label!r} nicht: {sms!r}"
        )
    assert not sms.endswith(f", {leading.sms_scope}"), (
        f"Compare-SMS endet mit gemeinsamem Ortszusatz {leading.sms_scope!r}: {sms!r}"
    )

    head, lines = _tg_parts(notices)
    assert leading.scope_label not in head, (
        f"Compare-Telegram-Kopfzeile nennt {leading.scope_label!r} fuer alle "
        f"Warnungen: {head!r}"
    )
    for n, line in zip(ordered, lines):
        assert n.scope_label in line, (
            f"Compare-Telegram-Zeile zur Warnung {n.alert.label!r} nennt ihren "
            f"Ort {n.scope_label!r} nicht: {line!r}"
        )


# ---------------------------------------------------------------------------
# Fixture-Ergaenzung (#1253, PO-go 2026-07-13): `LOC_NAMES` oben nutzt
# bewusst den bereits vorgefalteten Namen `"Hyeres"` (kein Test speist je den
# ROHEN Eingabewert `Hyères` ein -- genau die Luecke, die den Verstuemmelungs-
# Bug jahrelang durchgelassen hat, s. fix_1252_1253_kanal_text.md Test-Plan).
# Diese Ergaenzung ersetzt `LOC_NAMES` NICHT (das wuerde die AC-2/AC-7/AC-9-
# Golden-Strings dieser Datei zerstoeren, die bewusst bit-identisches
# Telegram-Verhalten pruefen), sondern fuegt einen eigenstaendigen Fall mit
# einem rohen Akzent-Namen hinzu, der den echten Falt-Pfad durchlaeuft.
# ---------------------------------------------------------------------------


def test_ac1_sms_folds_raw_accented_location_name():
    """Fixture-Ergaenzung zu AC-1: Given eine Warnung fuer den ROH eingegebenen
    Ortsnamen `Hyères` (nicht den vorgefalteten `Hyeres`) / When die SMS
    gerendert wird / Then enthaelt sie das gefaltete `Hyeres`, NICHT die
    verstuemmelte Form `Hyres` -- ohne diese Ergaenzung testet keine der
    Golden-Assertions in dieser Datei den echten Falt-Pfad, weil `LOC_NAMES`
    bereits vorgefaltete Namen nutzt."""
    tagged = [
        (_alert(3, "access_ban", "Zugang eingeschränkt — Monts Toulonnais",
                source="massif_closure", dedup_id="monts_toulonnais"), ["hyeres_raw"]),
    ]
    notices = _compare_notices(
        tagged,
        all_ids=["hyeres_raw", "toulon"],
        names={"hyeres_raw": "Hyères", "toulon": "Toulon"},
    )
    sms = _sms(notices)
    assert "Hyeres" in sms, f"Gefaltetes 'Hyeres' fehlt in der SMS: {sms!r}"
    assert "Hyres" not in sms, (
        f"SMS enthaelt weiterhin die verstuemmelte Form 'Hyres': {sms!r}"
    )
    assert sms.isascii() and len(sms) <= SMS_LIMIT
