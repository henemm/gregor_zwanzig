"""Eindeutigkeit des SMS-Kurz-Zeit-Tokens amtlicher Warnungen (#1929, Scheibe 1).

SPEC: docs/specs/modules/fix_1929_warnung_anzeigetext_eindeutig.md — AC-1..AC-7

TDD RED. Geprueft wird am FINALEN Rueckgabe-String von
`render_official_alert_sms`, nicht an `_tag_time` isoliert: die Kuerzungskette
(`_sms_pack_with_fallback`, vier Rueckfallstufen) greift danach und kann Tokens
ganz entfernen. Nur AC-3 und AC-7 rufen `_tag_time` direkt auf — dort IST die
isolierte Funktion die Zusicherung. Keine Mocks: echte `OfficialAlert`/
`OfficialAlertNotice`, echter Renderer-Aufruf, netzfrei.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from output.renderers.alert.official_alerts import (
    OfficialAlertNotice, _tag_time, render_official_alert_sms,
)
from services.official_alerts.models import OfficialAlert

UTC = timezone.utc
SMS_LIMIT = 140  # produktiver Default von `render_official_alert_sms`
# 2026-07-10 = Freitag, 2026-07-11 = Samstag, 2026-07-18 = Samstag (Folgewoche).
_FR, _SA, _SA2 = 10, 11, 18

# Erkennt Zeit-Tokens in BEIDEN Formaten: Bestand ('Sa', 'Sa15-21',
# 'Fr22-Sa03') UND kuenftig ('Sa11.07.', 'Sa15:20-21:40', 'Fr22:15-Sa03:10').
# Ein Parser, der nach der Implementierung nichts mehr findet, meldet trivial
# "keine Kollision" — deshalb ist "nicht gefunden" in `_time_tokens` ein
# Testfehler (Positivkontrolle), kein stilles Bestehen. Die Monatsgruppe
# `(?:\.\d{1,2})?` ist fuer F002 noetig: ohne sie endet der Match von
# 'Sa14.02.' schon nach 'Sa14.', und zwei Tokens verschiedener Monate saehen
# fuer den Parser weiterhin gleich aus — der Test wuerde dann die Kollision
# melden, die die Implementierung gerade behoben hat.
_WD = "(?:Mo|Di|Mi|Do|Fr|Sa|So)"
_TIME_TOKEN_RE = re.compile(
    rf"(?<![A-Za-z0-9]){_WD}(?:\d{{1,2}}(?::\d{{2}})?(?:\.\d{{1,2}})?\.?)?"
    rf"(?:-{_WD}?\d{{1,2}}(?::\d{{2}})?)?(?![A-Za-z])"
)


def _dt(day: int, hour: int, minute: int, second: int = 0, *,
        month: int = 7) -> datetime:
    return datetime(2026, month, day, hour, minute, second, tzinfo=UTC)


def _alert(vf, vt, *, hazard: str = "thunderstorm", label: str = "Gewitter") -> OfficialAlert:
    return OfficialAlert(source="vigilance", hazard=hazard, level=3, label=label,
                         valid_from=vf, valid_to=vt, region_label="Var")


def _notice(alert: OfficialAlert, scope: str, scope_id: str) -> OfficialAlertNotice:
    return OfficialAlertNotice(alert=alert, scope_label=scope, sms_scope=scope,
                               affected_chips=[scope], free_chips=[],
                               scope_ids=(scope_id,))


def _sms(notices: list[OfficialAlertNotice]) -> str:
    return render_official_alert_sms(notices, sms_prefix="GZ", limit=SMS_LIMIT, tz=UTC)


def _time_tokens(sms: str, *, expected: int) -> list[str]:
    """Zeit-Tokens des finalen SMS-Strings; Positivkontrolle inklusive."""
    found = _TIME_TOKEN_RE.findall(sms)
    assert len(found) == expected, (
        f"Positivkontrolle: {expected} Zeit-Tokens erwartet, {len(found)} "
        f"gefunden ({found!r}) in {sms!r}"
    )
    return found


def test_ac1_gleicher_tag_minuten_machen_tokens_unterscheidbar():
    """AC-1: Given zwei Warnungen am selben Kalendertag, deren Fenster sich nur
    in den Minuten unterscheiden und dieselbe Stundenpaarung ergeben
    (15:00-21:00 vs. 15:20-21:40) / When `render_official_alert_sms` beide
    gemeinsam rendert / Then sind die Zeit-Tokens im finalen SMS-String
    unterscheidbar.

    Abweichung vom Spec-Wortlaut, gemessen: das dort genannte Paar
    15:00-21:00 vs. 15:20-20:50 kollidiert im Bestand GAR NICHT ('Sa15-21' vs.
    'Sa15-20') und wuerde die Zusicherung nicht pruefen."""
    sms = _sms([
        _notice(_alert(_dt(_SA, 15, 0), _dt(_SA, 21, 0)), "Var interieur", "z1"),
        _notice(_alert(_dt(_SA, 15, 20), _dt(_SA, 21, 40)), "Var cotier", "z2"),
    ])
    first, second = _time_tokens(sms, expected=2)
    assert first != second, (
        f"Zwei verschiedene Zeitfenster tragen denselben Text {first!r}: {sms!r}"
    )


def test_ac1_gleicher_tag_nur_die_bis_grenze_variiert():
    """AC-1 (Einzelgrenze `vt`): Given zwei Warnungen am selben Kalendertag mit
    IDENTISCHER Von-Grenze (15:00), die sich allein in den Minuten der
    Bis-Grenze unterscheiden (21:00 vs. 21:40) / When gemeinsam gerendert wird
    / Then sind die Zeit-Tokens verschieden.

    Deckt die Luecke, die `test_ac1_gleicher_tag_...unterscheidbar` offenlaesst:
    dort variieren beide Grenzen, sodass allein die Von-Differenz die Tokens
    schon trennt und eine kaputte Bis-Grenze unbemerkt bleibt."""
    sms = _sms([
        _notice(_alert(_dt(_SA, 15, 0), _dt(_SA, 21, 0)), "Var interieur", "z1"),
        _notice(_alert(_dt(_SA, 15, 0), _dt(_SA, 21, 40)), "Var cotier", "z2"),
    ])
    first, second = _time_tokens(sms, expected=2)
    assert first != second, (
        f"Nur die Bis-Grenze unterscheidet sich, beide Tokens lauten {first!r}: "
        f"{sms!r}"
    )


def test_ac1_gleicher_tag_nur_die_von_grenze_variiert():
    """AC-1 (Einzelgrenze `vf`): Given zwei Warnungen am selben Kalendertag mit
    IDENTISCHER Bis-Grenze (21:00), die sich allein in den Minuten der
    Von-Grenze unterscheiden (15:00 vs. 15:20) / When gemeinsam gerendert wird
    / Then sind die Zeit-Tokens verschieden."""
    sms = _sms([
        _notice(_alert(_dt(_SA, 15, 0), _dt(_SA, 21, 0)), "Var interieur", "z1"),
        _notice(_alert(_dt(_SA, 15, 20), _dt(_SA, 21, 0)), "Var cotier", "z2"),
    ])
    first, second = _time_tokens(sms, expected=2)
    assert first != second, (
        f"Nur die Von-Grenze unterscheidet sich, beide Tokens lauten {first!r}: "
        f"{sms!r}"
    )


def test_ac2_tagesuebergang_minuten_machen_tokens_unterscheidbar():
    """AC-2: Given zwei Warnungen mit Tagesuebergangs-Fenstern
    (Fr22:15-Sa03:10 vs. Fr22:30-Sa03:45), die sich nur in den Minuten
    unterscheiden / When gerendert wird / Then sind beide Zeit-Tokens im
    finalen String verschieden."""
    sms = _sms([
        _notice(_alert(_dt(_FR, 22, 15), _dt(_SA, 3, 10)), "Var interieur", "z1"),
        _notice(_alert(_dt(_FR, 22, 30), _dt(_SA, 3, 45)), "Var cotier", "z2"),
    ])
    first, second = _time_tokens(sms, expected=2)
    assert first != second, (
        f"Zwei Tagesuebergangs-Fenster tragen denselben Text {first!r}: {sms!r}"
    )


def test_ac2_tagesuebergang_nur_die_bis_grenze_variiert():
    """AC-2 (Einzelgrenze `vt`): Given zwei Tagesuebergangs-Warnungen mit
    IDENTISCHER Von-Grenze (Fr22:00), die sich allein in den Minuten der
    Bis-Grenze unterscheiden (Sa03:10 vs. Sa03:45) / When gemeinsam gerendert
    wird / Then sind die Zeit-Tokens verschieden.

    Nur erfuellbar, wenn die Bis-Grenze des Tagesuebergangs-Zweigs die Minuten
    traegt; im Bestandstest variieren beide Grenzen zugleich und die
    Von-Differenz verdeckt eine kaputte Bis-Grenze vollstaendig."""
    sms = _sms([
        _notice(_alert(_dt(_FR, 22, 0), _dt(_SA, 3, 10)), "Var interieur", "z1"),
        _notice(_alert(_dt(_FR, 22, 0), _dt(_SA, 3, 45)), "Var cotier", "z2"),
    ])
    first, second = _time_tokens(sms, expected=2)
    assert first != second, (
        f"Nur die Bis-Grenze unterscheidet sich, beide Tokens lauten {first!r}: "
        f"{sms!r}"
    )


def test_ac2_tagesuebergang_nur_die_von_grenze_variiert():
    """AC-2 (Einzelgrenze `vf`): Given zwei Tagesuebergangs-Warnungen mit
    IDENTISCHER Bis-Grenze (Sa03:00), die sich allein in den Minuten der
    Von-Grenze unterscheiden (Fr22:15 vs. Fr22:30) / When gemeinsam gerendert
    wird / Then sind die Zeit-Tokens verschieden."""
    sms = _sms([
        _notice(_alert(_dt(_FR, 22, 15), _dt(_SA, 3, 0)), "Var interieur", "z1"),
        _notice(_alert(_dt(_FR, 22, 30), _dt(_SA, 3, 0)), "Var cotier", "z2"),
    ])
    first, second = _time_tokens(sms, expected=2)
    assert first != second, (
        f"Nur die Von-Grenze unterscheidet sich, beide Tokens lauten {first!r}: "
        f"{sms!r}"
    )


def test_ac3_volle_stunden_bleiben_ohne_minutenanhang():
    """AC-3 (Nicht-Regression, bewusst schon gruen): Given ein Fenster ohne
    Minutenanteil (15:00-21:00) / When `_tag_time` bzw.
    `render_official_alert_sms` rendert / Then bleibt der Kurz-Token
    bit-identisch 'Sa15-21' — ohne Minutenanhang, ohne Datum."""
    alert = _alert(_dt(_SA, 15, 0), _dt(_SA, 21, 0))
    assert _tag_time(alert, UTC) == "Sa15-21", (
        f"Voll-Stunden-Token veraendert: {_tag_time(alert, UTC)!r}"
    )
    sms = _sms([_notice(alert, "Var interieur", "z1")])
    assert _time_tokens(sms, expected=1) == ["Sa15-21"], f"in der SMS: {sms!r}"


def test_ac4_ganztags_tokens_verschiedener_wochen_sind_unterscheidbar():
    """AC-4: Given zwei Ganztags-Warnungen am selben Wochentag verschiedener
    Kalenderwochen (Sa 11.07. und Sa 18.07., beide im 15-Tage-Horizont) / When
    gemeinsam gerendert wird / Then tragen beide Tokens eine Tag-im-Monat-
    Angabe und sind textlich verschieden."""
    sms = _sms([
        _notice(_alert(_dt(_SA, 0, 0), _dt(_SA, 23, 59)), "Var interieur", "z1"),
        _notice(_alert(_dt(_SA2, 0, 0), _dt(_SA2, 23, 59)), "Var cotier", "z2"),
    ])
    first, second = _time_tokens(sms, expected=2)
    assert first != second, (
        f"Zwei Ganztags-Warnungen eine Woche auseinander tragen denselben Text "
        f"{first!r}: {sms!r}"
    )
    assert all(any(c.isdigit() for c in t) for t in (first, second)), (
        f"Ganztags-Tokens ohne Datumsangabe: {first!r}/{second!r} in {sms!r}"
    )


def test_f002_ganztags_tokens_verschiedener_monate_sind_unterscheidbar():
    """AC-4 (F002, Monat im Ganztags-Token): Given zwei Ganztags-Warnungen mit
    demselben Tag-im-Monat auf demselben Wochentag in VERSCHIEDENEN Monaten
    (Sa 14.02. und Sa 14.03.2026) / When gemeinsam gerendert wird / Then sind
    die Zeit-Tokens verschieden und tragen die Form 'Sa14.02.'/'Sa14.03.'.

    Gemessen vor der Aenderung: beide ergaben bit-identisch 'Sa14.' — die
    schaerfste Kollisionslage des Ganztags-Tokens. Der Bestandstest AC-4
    (11.07. vs. 18.07.) faengt sie nicht, weil dort beide Termine im SELBEN
    Monat liegen und schon der Tag-im-Monat trennt.

    Das Datumspaar ist bewusst gewaehlt und nicht frei austauschbar: gleicher
    Wochentag UND gleicher Tag-im-Monat erzwingen einen Abstand als Vielfaches
    von 7 Tagen, den nur Februar->Maerz (28 Tage) knapp liefert. Ein Paar wie
    10.07./10.08. waere Fr gegen Mo und damit schon ueber das Wochentags-
    kuerzel unterscheidbar — der Test wuerde die Zusicherung nicht pruefen.

    Der zweite Assert nagelt die Reihenfolge Tag-vor-Monat fest; ohne ihn
    bliebe eine Vertauschung ('Sa02.14.') unbemerkt, da auch vertauschte
    Tokens noch verschieden sind."""
    sms = _sms([
        _notice(_alert(_dt(14, 0, 0, month=2), _dt(14, 23, 59, month=2)),
                "Var interieur", "z1"),
        _notice(_alert(_dt(14, 0, 0, month=3), _dt(14, 23, 59, month=3)),
                "Var cotier", "z2"),
    ])
    first, second = _time_tokens(sms, expected=2)
    assert first != second, (
        f"Gleicher Wochentag, gleicher Tag-im-Monat, verschiedene Monate tragen "
        f"denselben Text {first!r}: {sms!r}"
    )
    assert (first, second) == ("Sa14.02.", "Sa14.03."), (
        f"Ganztags-Token nicht in der Form 'Tag.Monat.': {first!r}/{second!r} "
        f"in {sms!r}"
    )


def test_ac5_kein_kollidierender_rest_unter_budgetdruck():
    """AC-5: Given die Kollisionslage aus AC-1 plus eine dritte Warnung und
    lange Ortsnamen, die die Kuerzungskette zum Droppen zwingen (gemessen: das
    dritte Token faellt per '+1' weg, die beiden kollidierenden bleiben) / When
    gerendert wird / Then ist jedes verbliebene Zeit-Token eindeutig — ein
    kollidierender Rest ist die Verletzung."""
    scope = "Vallee du Verdon Haute Rive Est"
    sms = _sms([
        _notice(_alert(_dt(_SA, 15, 0), _dt(_SA, 21, 0)), scope, "z1"),
        _notice(_alert(_dt(_SA, 15, 20), _dt(_SA, 21, 40), hazard="wind_gust",
                       label="Sturm"), scope + " Sued", "z2"),
        _notice(_alert(_dt(_SA, 17, 0), _dt(_SA, 19, 0), hazard="snow",
                       label="Schneefall"), scope + " Nord", "z3"),
    ])
    assert " +" in sms, (
        f"Szenario greift nicht: kein Auslassungsmarker, kein Budgetdruck: {sms!r}"
    )
    visible = _time_tokens(sms, expected=2)
    assert len(set(visible)) == len(visible), (
        f"Kollidierender Rest nach der Kuerzung sichtbar: {visible!r} in {sms!r}"
    )


def test_ac6_alle_szenarien_bleiben_unter_140_zeichen():
    """AC-6: Given die Szenarien aus AC-1, AC-2, AC-4 und AC-5 / When mit dem
    produktiven Default-Limit gerendert wird / Then ueberschreitet der
    zurueckgegebene String nie 140 Zeichen."""
    lang = "Vallee du Verdon Haute Rive Est"
    szenarien = {
        "ac1": ("Var", [((_SA, 15, 0), (_SA, 21, 0)), ((_SA, 15, 20), (_SA, 21, 40))]),
        "ac2": ("Var", [((_FR, 22, 15), (_SA, 3, 10)), ((_FR, 22, 30), (_SA, 3, 45))]),
        "ac4": ("Var", [((_SA, 0, 0), (_SA, 23, 59)), ((_SA2, 0, 0), (_SA2, 23, 59))]),
        "ac5": (lang, [((_SA, 15, 0), (_SA, 21, 0)), ((_SA, 15, 20), (_SA, 21, 40)),
                       ((_SA, 17, 0), (_SA, 19, 0))]),
    }
    for name, (scope, fenster) in szenarien.items():
        sms = _sms([_notice(_alert(_dt(*vf), _dt(*vt)), f"{scope} {i}", f"z{i}")
                    for i, (vf, vt) in enumerate(fenster)])
        assert len(sms) <= SMS_LIMIT, (
            f"Szenario {name}: {len(sms)} Zeichen > {SMS_LIMIT}: {sms!r}"
        )


def test_ac7_none_fenster_und_sekunden_bleiben_unveraendert():
    """AC-7 (Bestandsverhalten, bewusst schon gruen): Given ein Fenster ohne
    `valid_from`/`valid_to` (DPC-Fall) sowie eines mit Sekundenanteil != 0 /
    When `_tag_time` aufgerufen wird / Then bleibt das Ergebnis wie
    vorbestehend: leerer String bzw. Sekunden weiterhin ignoriert."""
    assert _tag_time(_alert(None, None), UTC) == "", (
        "Fehlender Gueltigkeitszeitraum liefert nicht mehr '' (F003-Verhalten)"
    )
    mit = _tag_time(_alert(_dt(_SA, 9, 55, 57), _dt(_SA, 20, 0, 30)), UTC)
    ohne = _tag_time(_alert(_dt(_SA, 9, 55), _dt(_SA, 20, 0)), UTC)
    assert mit == ohne, f"Sekundenanteil wirkt neuerdings: {mit!r} vs. {ohne!r}"
