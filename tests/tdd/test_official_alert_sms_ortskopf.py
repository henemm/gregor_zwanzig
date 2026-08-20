"""TDD RED — Issue #1948 Scheibe S5: die eigenstaendige amtliche Warn-SMS
spricht dieselbe Grammatik wie Trip-Briefing-SMS und (seit S4) der
Nowcast-Alarm — Ortskopf, Gefahren-Kuerzel mit Stufenbuchstabe, Zeitfenster.

SPEC: docs/specs/modules/fix_1948_s5_amtliche_sms_zielbild.md (AC-1 bis AC-17)

PO-Zielbild-Tabelle (woertlich, nicht verhandelbar):

    heute (Ist)              KHW403 AMT GELB1/3: TH Do12-22, ges.Route
    nach S5                  Seg 4: !TH:L 12-22
    zweite Warnung dazu      Seg 4: !TH:L 12-22 HT:L
    Ziel-Segment, orange     Ziel: !TH:M 15-21

Kein Mock, keine Dateiinhalt-Asserts: echte ``OfficialAlert``-Objekte durch
die echten Builder (``build_official_alert_notices`` /
``build_compare_official_alert_notices``) und den echten Renderer
(``render_official_alert_sms``); der Versandnachweis laeuft ueber die echten
Aufrufer in ``NotificationService`` mit ``sms_sink`` (kein Netz, kein
echter Versand).

WANDUHR (Spec "Known Limitations", Praezedenz S4): der "heute"-Fall (AC-8)
wird IMMER relativ zu ``datetime.now(TZ)`` konstruiert — ein eingefrorener
Goldstring waere rot, sobald ein Lauf ueber Mitternacht reicht.

SIGNATUR-TOLERANZ: ``_render`` reicht ``sms_prefix`` nur durch, solange die
Alt-Signatur den Parameter noch fuehrt. Dadurch scheitern AC-1..AC-8 an der
FORMAT-Zusicherung (dem eigentlichen Befund) statt an einem TypeError; dass
der Parameter verschwindet, prueft AC-9 eigens.
"""
from __future__ import annotations

import inspect
import json
import re
import shutil
import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.config import Settings
from app.trip import Stage, Trip, Waypoint
from output.renderers.alert.official_alerts import (
    OfficialAlertNotice,
    build_compare_official_alert_notices,
    build_official_alert_notices,
    render_official_alert_sms,
)
from services.official_alerts.models import OfficialAlert

TZ = ZoneInfo("Europe/Vienna")

# Wochentagskuerzel unmittelbar vor einer Stunde ("Do12", "Fr15:20") — genau
# das Praefix, das im "heute"-Fall (AC-8) ersatzlos entfaellt.
_WEEKDAY_BEFORE_HOUR = re.compile(r"(Mo|Di|Mi|Do|Fr|Sa|So)\d")

# Alt-Format-Spuren, die nach S5 nirgends mehr stehen duerfen.
_AMT_MARKER = re.compile(r"\bAMT\b")
_LEVEL_WORD_POSITION = re.compile(r"(GELB|ORANGE|ROT|GRÜN)\d/3")


# ---------------------------------------------------------------------------
# Bausteine
# ---------------------------------------------------------------------------

def _heute(hour: int, minute: int = 0) -> datetime:
    """Ein Zeitpunkt des HEUTIGEN Tages in ``TZ`` (Wanduhr-fest, kein
    Goldstring): der Kalendertag wird zur Laufzeit bestimmt."""
    return datetime.now(TZ).replace(
        hour=hour, minute=minute, second=0, microsecond=0,
    )


def _morgen(hour: int, minute: int = 0) -> datetime:
    return _heute(hour, minute) + timedelta(days=1)


def _alert(
    *, hazard: str = "thunderstorm", level: int = 2,
    von: datetime | None = None, bis: datetime | None = None,
    label: str = "Gewitter",
) -> OfficialAlert:
    return OfficialAlert(
        source="geosphere_warn", hazard=hazard, level=level, label=label,
        region_label="Kärnten", valid_from=von, valid_to=bis,
    )


def _notice(
    alert: OfficialAlert, *, sms_scope: str = "Seg 4",
    scope_label: str = "Segment 4", scope_ids: tuple[str, ...] = ("4",),
) -> OfficialAlertNotice:
    """Handgebaute Notice fuer die Faelle, die kein echter Mitschnitt hergibt
    (Spec "Known Limitations": Stufe 1/3/4, access_ban, unbekannter hazard)."""
    return OfficialAlertNotice(
        alert=alert, scope_label=scope_label, sms_scope=sms_scope,
        affected_chips=[scope_label], free_chips=[], scope_ids=scope_ids,
    )


def _render(notices: list, *, limit: int = 140, tz: ZoneInfo | None = TZ) -> str:
    """Renderer-Aufruf, der die Alt- UND die Ziel-Signatur bedient.

    Solange ``sms_prefix`` noch Pflichtparameter ist, wird der Trip-Name
    "KHW403" durchgereicht — genau der Name, der nach AC-9 nirgends mehr in
    der Ausgabe stehen darf. Faellt der Parameter mit S5 weg, entfaellt die
    Durchreichung; die uebrigen Zusicherungen bleiben Wort fuer Wort
    dieselben."""
    kwargs: dict = {"limit": limit, "tz": tz}
    if "sms_prefix" in inspect.signature(render_official_alert_sms).parameters:
        kwargs["sms_prefix"] = "KHW403"
    return render_official_alert_sms(notices, **kwargs)


def _kopf(sms: str) -> str:
    assert ": " in sms, f"Kurznachricht hat keinen '<Ort>: <Token>'-Aufbau: {sms!r}"
    return sms.split(": ", 1)[0]


def _rumpf(sms: str) -> str:
    assert ": " in sms, f"Kurznachricht hat keinen '<Ort>: <Token>'-Aufbau: {sms!r}"
    return sms.split(": ", 1)[1]


def _trip(name: str = "KHW 403", waypoints: int = 7) -> Trip:
    """Trip mit ``waypoints-1`` Zwischensegmenten + Ziel — genug, damit
    Segment 4 existiert und NICHT als 'gesamte Route' gilt."""
    # HAERTUNG (Wanduhr-Ratsche `test_fixture_wallclock_ratchet.py`
    # AC-5/AC-10: haerten statt eintragen): FESTES Etappen-Datum, explizite
    # `start_time` UND explizite Ankunftszeit je Wegpunkt. Ohne all das faellt
    # die Segment-Ableitung auf die Prozessuhr zurueck -- die Fixture waere
    # dann davon abhaengig, WANN der Lauf stattfindet (Spec-Warnung
    # "Wanduhr-Abhaengigkeit", Known Limitations).
    #
    # Bewusste Arbeitsteilung mit dem "heute"-Fall: die Wanduhr steckt
    # ausschliesslich in `_heute()`/`_morgen()`, also in `valid_from`/
    # `valid_to` der WARNUNG -- genau dort verlangt AC-8 sie. Der TRIP
    # dagegen ist vollstaendig fest verdrahtet und traegt keine Wanduhr mehr.
    stage = Stage(
        id="S1", name="Etappe 1", date=date(2026, 7, 11),
        start_time=time(8, 0),
        waypoints=[
            Waypoint(
                id=f"W{i}", name=f"WP {i}",
                lat=46.60 + i / 100, lon=13.30 + i / 100, elevation_m=1400,
                arrival_calculated=f"{7 + i:02d}:00",
            )
            for i in range(1, waypoints + 1)
        ],
    )
    return Trip(id="trip-1948-s5", name=name, stages=[stage])


def _zwei_warnungen_segment_4(trip: Trip) -> list:
    """Zwei gelbe Warnungen auf demselben Segment 4 — der Fall der
    PO-Zielbild-Zeile ``Seg 4: !TH:L 12-22 HT:L``.

    Zwei statt einer Warnung, damit ``build_official_alert_notices`` den
    ``"nur "``-Zusatz NICHT setzt (er greift nur bei genau einer Warnung)."""
    gewitter = _alert(von=_heute(12), bis=_heute(22))
    hitze = _alert(
        hazard="extreme_heat", level=2, label="Hitze",
        von=_heute(13), bis=None,  # ohne Ende -> `_tag_time` liefert ""
    )
    return build_official_alert_notices(trip, [(gewitter, ["4"]), (hitze, ["4"])])


def _settings_mit_sms() -> Settings:
    """``can_send_sms()`` == True; der Versand selbst laeuft ueber ``sms_sink``
    und beruehrt kein Netz."""
    return Settings(
        sms_gateway_url="http://127.0.0.1:1/api/sms",
        seven_api_key="test-stub-key",
        sms_to="+49000000000",
        sms_from=None,
    )


# ---------------------------------------------------------------------------
# AC-1 — Ortskopf "Seg 4: " statt Kurzcode "S4"
# ---------------------------------------------------------------------------

def test_ac1_segment_kopf_lautet_seg_4_statt_kurzcode_s4():
    """AC-1: Given eine amtliche Warnung mit Umfang genau Segment 4
    (``sms_scope`` heute "S4") / When ueber den einheitlichen Umfang gerendert
    wird / Then lautet der Ortskopf exakt "Seg 4: " und der Kurzcode "S4"
    steht nirgends mehr."""
    notices = _zwei_warnungen_segment_4(_trip())
    sms = _render(notices)

    assert sms.startswith("Seg 4: "), (
        f"AC-1: Ortskopf muss exakt 'Seg 4: ' lauten (PO-Zielbild), "
        f"bekam {sms!r}"
    )
    assert not re.search(r"\bS4\b", sms), (
        f"AC-1: der alte Kurzcode 'S4' darf nicht mehr auftauchen: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-2 — Zielsegment
# ---------------------------------------------------------------------------

def test_ac2_zielsegment_kopf_lautet_ziel():
    """AC-2: Given eine Warnung, deren Umfang ausschliesslich das Zielsegment
    ist / When gerendert wird / Then beginnt die Nachricht mit "Ziel: " —
    dieselbe Ortssprache wie Trip-Briefing und Nowcast-Alarm."""
    trip = _trip()
    gewitter = _alert(von=_heute(15), bis=_heute(21), level=3)
    hitze = _alert(
        hazard="extreme_heat", level=3, label="Hitze", von=_heute(16), bis=None,
    )
    notices = build_official_alert_notices(
        trip, [(gewitter, ["Ziel"]), (hitze, ["Ziel"])],
    )
    sms = _render(notices)

    assert sms.startswith("Ziel: "), (
        f"AC-2: Zielsegment-Kopf muss exakt 'Ziel: ' lauten, bekam {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-3 — genau EIN "!", Tokens durch genau ein Leerzeichen getrennt
# ---------------------------------------------------------------------------

def test_ac3_zwei_warnungen_tragen_genau_ein_ausrufezeichen():
    """AC-3: Given zwei Warnungen mit demselben Segment-Umfang / When beide zu
    einer Kurznachricht zusammengefasst werden / Then traegt die Ausgabe genau
    EIN "!" unmittelbar vor dem ersten Token, und beide Tokens sind durch genau
    ein Leerzeichen getrennt (kein " + "-Joiner mehr)."""
    sms = _render(_zwei_warnungen_segment_4(_trip()))

    assert sms.count("!") == 1, (
        f"AC-3: genau EIN '!' erwartet (nur vor dem ersten Token), "
        f"bekam {sms.count('!')} in {sms!r}"
    )
    assert re.search(r": !TH:", sms), (
        f"AC-3: das '!' muss unmittelbar vor dem ERSTEN Kuerzel-Token stehen "
        f"('<Ort>: !TH:...'), bekam {sms!r}"
    )
    assert " + " not in sms, (
        f"AC-3: Tokens werden mit einem Leerzeichen verbunden, nicht mit "
        f"' + ' (PO-Zielbild 'Seg 4: !TH:L 12-22 HT:L'): {sms!r}"
    )
    assert re.search(r"\bHT:L\b", sms), (
        f"AC-3: die zweite Warnung muss als eigener Token 'HT:L' erscheinen: "
        f"{sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-4 — Stufenbuchstabe L / M / H
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(("level", "buchstabe"), [(2, "L"), (3, "M"), (4, "H")])
def test_ac4_warnstufe_erscheint_als_buchstabe_hinter_dem_doppelpunkt(
    level: int, buchstabe: str,
):
    """AC-4: Given je eine Warnung der Stufen gelb (2), orange (3) und rot (4)
    derselben Gefahrenart / When einzeln gerendert wird / Then traegt der Token
    exakt L, M bzw. H direkt hinter dem Doppelpunkt."""
    sms = _render([_notice(_alert(level=level, von=_heute(15), bis=_heute(21)))])

    assert f"TH:{buchstabe}" in sms, (
        f"AC-4: Stufe {level} muss als 'TH:{buchstabe}' erscheinen, "
        f"bekam {sms!r}"
    )
    assert not _LEVEL_WORD_POSITION.search(sms), (
        f"AC-4: das alte Stufenwort mit Positionsangabe ('GELB1/3') ist "
        f"abgeloest: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-5 (Waechter) — GRÜN als "-", ohne LEVEL_LETTERS anzufassen
# ---------------------------------------------------------------------------

def test_ac5_gruene_stufe_zeigt_minus_und_urgency_bleibt_absturzfrei():
    """AC-5 (Mutations-Waechter): Given eine Warnung der Stufe GRÜN (1) UND ein
    direkter Aufruf von ``urgency_from_official_level(1)`` im selben Testkoerper
    / When beide Pfade nacheinander laufen / Then zeigt die SMS-Darstellung "-"
    fuer GRÜN, UND die Dringlichkeitsableitung liefert weiterhin ihren
    unveraenderten Wert OHNE ``KeyError``.

    Der Wert ist "HIGH", nicht "LOW": ``urgency_from_official_level`` faellt
    fuer eine Stufe ausserhalb von ``LEVEL_LETTERS`` konservativ auf "H"
    zurueck (``alert_urgency.py:28``, dokumentiert als AC-3 von #1461).
    Die Spec-Formulierung "liefert weiterhin LOW" trifft auf den Code nicht
    zu — gemessen, nicht angenommen; die Zusicherung dieses ACs (kein
    Absturz, unveraenderter Wert) bleibt davon unberuehrt.

    MUTATION: ergaenzt jemand ``1: "-"`` in ``hazard_symbols.LEVEL_LETTERS``,
    schlaegt der zweite Teil mit ``KeyError: '-'`` fehl, weil
    ``_LETTER_TO_URGENCY`` nur L/M/H kennt."""
    import output.tokens.hazard_symbols as hazard_symbols
    from services.alert_urgency import urgency_from_official_level

    sms = _render([_notice(_alert(level=1, von=_heute(12), bis=_heute(22)))])
    assert "TH:-" in sms, (
        f"AC-5: Stufe GRÜN (1) muss als 'TH:-' erscheinen, bekam {sms!r}"
    )

    assert 1 not in hazard_symbols.LEVEL_LETTERS, (
        "AC-5 (TABU): `LEVEL_LETTERS` darf um KEINE Stufe 1 ergaenzt werden — "
        "die vierstufige SMS-Darstellungsleiter lebt als eigene Tabelle im "
        f"Renderer. Gefunden: {hazard_symbols.LEVEL_LETTERS!r}"
    )
    assert urgency_from_official_level(1) == "HIGH", (
        "AC-5: `urgency_from_official_level(1)` muss unveraendert und "
        "absturzfrei antworten (konservativer 'H'-Rueckfall)."
    )
    assert urgency_from_official_level(2) == "LOW"
    assert urgency_from_official_level(3) == "MODERATE"
    assert urgency_from_official_level(4) == "HIGH"


# ---------------------------------------------------------------------------
# AC-6 — access_ban blank, ohne Stufe, ohne Zeit
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level", [2, 3, 4])
def test_ac6_access_ban_bleibt_blankes_kuerzel_ohne_stufe_und_zeit(level: int):
    """AC-6: Given eine Warnung mit ``hazard="access_ban"`` / When sie gerendert
    wird / Then erscheint "CL" blank — ohne Doppelpunkt, ohne Stufenbuchstaben
    und ohne Zeitangabe, unabhaengig von der Stufe."""
    sms = _render([
        _notice(_alert(
            hazard="access_ban", level=level, label="Zugang gesperrt",
            von=_heute(12), bis=_heute(22),
        )),
    ])

    assert re.search(r"\bCL\b", sms), f"AC-6: Kuerzel 'CL' fehlt: {sms!r}"
    assert "CL:" not in sms, (
        f"AC-6: 'CL' ist stufenlos (LEVELLESS_HAZARDS) und darf keinen "
        f"Doppelpunkt tragen: {sms!r}"
    )
    assert "12-22" not in sms, (
        f"AC-6: eine Zugangssperre traegt keine Stunde/kein Fenster: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-7 — anderer Kalendertag: Fenster MIT Wochentag
# ---------------------------------------------------------------------------

def test_ac7_anderer_tag_zeigt_fenster_mit_wochentagspraefix():
    """AC-7: Given eine Gewitterwarnung 12:00-22:00 an einem ANDEREN
    Kalendertag als dem Testlauf-Tag / When der Zeit-Token gerendert wird /
    Then zeigt er das vollstaendige Fenster inklusive Wochentag-Praefix —
    nicht nur die Beginnstunde und nicht das '@'-Beginn-Format der
    Trip-Briefing-Vorhersage-Tokens."""
    from output.renderers.alert.official_alerts import _de_weekday_short, _tag_time

    alert = _alert(von=_morgen(12), bis=_morgen(22))
    tag = _de_weekday_short(_morgen(12))

    assert _tag_time(alert, TZ) == f"{tag}12-22", (
        f"AC-7: `_tag_time` muss das ganze Fenster mit Wochentag liefern, "
        f"bekam {_tag_time(alert, TZ)!r}"
    )

    sms = _render([_notice(alert)])
    assert f"TH:L {tag}12-22" in sms, (
        f"AC-7: der Token muss '{f'TH:L {tag}12-22'}' lauten (Kuerzel, Stufe, "
        f"volles Fenster mit Wochentag), bekam {sms!r}"
    )
    assert "@" not in sms, (
        f"AC-7: das '@'-Beginn-Format gehoert der Vorhersage, nicht der "
        f"amtlichen Warnung: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-8 — heute: Wochentag entfaellt ersatzlos
# ---------------------------------------------------------------------------

def test_ac8_heutiger_tag_laesst_das_wochentagspraefix_weg():
    """AC-8: Given dieselbe Warnung wie die Ist-Basislinie (Fall 1), deren
    Gueltigkeit am HEUTIGEN Tag beginnt / When der Zeit-Token gerendert wird /
    Then entfaellt das Wochentag-Praefix ersatzlos ("12-22" statt "Do12-22").

    Wanduhr-fest: ``valid_from``/``valid_to`` entstehen aus
    ``datetime.now(TZ)``, kein eingefrorenes Wochentagskuerzel."""
    sms = _render([_notice(_alert(von=_heute(12), bis=_heute(22)))])

    assert "TH:L 12-22" in sms, (
        f"AC-8: am heutigen Tag lautet der Token 'TH:L 12-22' ohne "
        f"Wochentag, bekam {sms!r}"
    )
    assert not _WEEKDAY_BEFORE_HOUR.search(sms), (
        f"AC-8: vor der Stunde darf kein Wochentagskuerzel stehen: {sms!r}"
    )


def test_ac8_minuten_bleiben_zweistellig_wenn_sie_nicht_voll_sind():
    """AC-8 (zweiter Halbsatz): Minuten bleiben zweistellig, sobald sie
    ungleich ":00" sind — auch ohne Wochentag-Praefix."""
    sms = _render([_notice(_alert(von=_heute(15, 20), bis=_heute(21, 40)))])

    assert "TH:L 15:20-21:40" in sms, (
        f"AC-8: ungerade Minuten bleiben erhalten ('15:20-21:40'), "
        f"bekam {sms!r}"
    )
    assert not _WEEKDAY_BEFORE_HOUR.search(sms), (
        f"AC-8: auch mit Minuten steht am heutigen Tag kein Wochentag "
        f"davor: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-9 — Trip-/Preset-Name ersatzlos entfallen
# ---------------------------------------------------------------------------

def test_ac9_trip_name_erscheint_nicht_mehr_und_parameter_ist_weg():
    """AC-9: Given einen Trip "KHW 403" und mindestens eine amtliche Warnung /
    When ``render_official_alert_sms`` OHNE ``sms_prefix`` aufgerufen wird (die
    Signatur fuehrt den Parameter nicht mehr) / Then enthaelt die Ausgabe den
    Trip-Namen an keiner Stelle."""
    parameter = inspect.signature(render_official_alert_sms).parameters
    assert "sms_prefix" not in parameter, (
        "AC-9: `render_official_alert_sms` darf den Parameter `sms_prefix` "
        f"nicht mehr fuehren; Signatur heute: {list(parameter)!r}"
    )

    notices = _zwei_warnungen_segment_4(_trip(name="KHW 403"))
    sms = render_official_alert_sms(notices, tz=TZ)

    assert "KHW403" not in sms, f"AC-9: Trip-Name steht noch im Text: {sms!r}"
    assert "KHW 403" not in sms, f"AC-9: Trip-Name steht noch im Text: {sms!r}"
    assert not _AMT_MARKER.search(sms), (
        f"AC-9: der Quellen-Marker 'AMT' ist ersatzlos entfallen — das Format "
        f"folgt dem Phaenomen, nicht der Quelle: {sms!r}"
    )


# ---------------------------------------------------------------------------
# AC-10 — echter Trip-Dispatch (SMS-Kanal)
# ---------------------------------------------------------------------------

def test_ac10_trip_dispatch_versendet_die_neue_grammatik():
    """AC-10: Given einen aktiven Trip-Alarm mit genau einer Segment-Warnung /
    When ``NotificationService.send_official_alert`` den SMS-Kanal ueber den
    echten Dispatch-Pfad bedient / Then traegt der versendete Text die
    Ortskopf-Kuerzel-Stufe-Zeit-Grammatik statt des AMT-Formats.

    Der ``sms_sink`` faengt den finalen Text ab — kein Netz, kein echter
    Versand (Muster der Bestandstests)."""
    from services.notification_service import NotificationService

    gefangen: list[str] = []
    trip = _trip(name="KHW 403")
    svc = NotificationService(
        settings=_settings_mit_sms(), user_id="tdd-1948-s5-trip",
    )
    svc.send_official_alert(
        trip=trip,
        notices=[(_alert(level=3, von=_heute(15), bis=_heute(21)), ["4"])],
        effective_channels={"sms"},
        sms_sink=gefangen.append,
    )

    assert len(gefangen) == 1, f"Setup: genau ein SMS-Text erwartet: {gefangen!r}"
    sms = gefangen[0]
    assert not _AMT_MARKER.search(sms), (
        f"AC-10: der Versandpfad sendet noch das alte AMT-Format: {sms!r}"
    )
    assert "KHW403" not in sms, f"AC-10: Trip-Name im Versandtext: {sms!r}"
    assert "Seg 4" in _kopf(sms), (
        f"AC-10: der Ortskopf muss das Segment in der Kurzform 'Seg 4' "
        f"nennen, bekam Kopf {_kopf(sms)!r} aus {sms!r}"
    )
    assert _rumpf(sms).startswith("!TH:M "), (
        f"AC-10: der Rumpf muss mit '!TH:M ' beginnen (Marker, Kuerzel, "
        f"Stufe orange), bekam {_rumpf(sms)!r}"
    )


# ---------------------------------------------------------------------------
# AC-11 — Ortsvergleich-Dispatch, identische Token-Grammatik
# ---------------------------------------------------------------------------

def test_ac11_compare_dispatch_nutzt_dieselbe_token_grammatik_wie_der_trip():
    """AC-11: Given einen Ortsvergleich-Alarm mit derselben Warnungsstruktur
    wie AC-10 / When ``_dispatch_compare_official_sms`` den SMS-Kanal bedient /
    Then ist der Token-Teil byte-identisch zum Trip-Fall — beide Flaechen rufen
    dieselbe ``render_official_alert_sms``, es entsteht keine zweite
    Renderer-Kopie (Teilungs-Invariante)."""
    from services.notification_service import NotificationService

    gewitter = _alert(level=3, von=_heute(15), bis=_heute(21))
    hitze = _alert(
        hazard="extreme_heat", level=3, label="Hitze", von=_heute(16), bis=None,
    )

    trip = _trip()
    alle_segmente = [str(i) for i in range(1, 7)] + ["Ziel"]
    trip_notices = build_official_alert_notices(
        trip, [(gewitter, alle_segmente), (hitze, alle_segmente)],
    )
    compare_notices = build_compare_official_alert_notices(
        ["loc-a", "loc-b"], {"loc-a": "Hermagor", "loc-b": "St. Stefan"},
        [(gewitter, ["loc-a", "loc-b"]), (hitze, ["loc-a", "loc-b"])],
    )

    gefangen: list[str] = []
    svc = NotificationService(
        settings=_settings_mit_sms(), user_id="tdd-1948-s5-compare",
    )
    ok = svc._dispatch_compare_official_sms(
        "Kärnten Orte", compare_notices, TZ, gefangen.append,
    )
    assert ok and len(gefangen) == 1, (
        f"Setup: Compare-Dispatch muss genau einen Text liefern: {gefangen!r}"
    )
    compare_sms = gefangen[0]
    trip_sms = _render(trip_notices)

    assert not _AMT_MARKER.search(compare_sms), (
        f"AC-11: Compare-Versandtext traegt noch 'AMT': {compare_sms!r}"
    )
    # Der Preset-Name laeuft heute durch `_ascii` ("Kärnten Orte" ->
    # "KaerntenOrte") — beide Schreibweisen muessen verschwinden.
    assert "KaerntenOrte" not in compare_sms and "Kärnten" not in compare_sms, (
        f"AC-11: der Preset-Name ist ersatzlos entfallen: {compare_sms!r}"
    )
    assert _rumpf(compare_sms) == _rumpf(trip_sms), (
        "AC-11: Trip und Ortsvergleich muessen bei struktur-gleicher Eingabe "
        "denselben Token-Teil liefern (nur der Ortskopf unterscheidet sich).\n"
        f"  Trip   ={trip_sms!r}\n  Compare={compare_sms!r}"
    )
    assert _rumpf(compare_sms).startswith("!TH:M "), (
        f"AC-11: Token-Grammatik '!TH:M <Fenster>' erwartet, bekam "
        f"{_rumpf(compare_sms)!r}"
    )


# ---------------------------------------------------------------------------
# AC-13 (Waechter, gruen vorher UND nachher) — die vier anderen Kanaele
# ---------------------------------------------------------------------------

def test_ac13_betreff_mail_und_telegram_behalten_ihr_vokabular():
    """AC-13 (TABU-Waechter): Betreff, E-Mail-HTML, Klartext-Mail und die
    ausfuehrliche Telegram-Vorlage bleiben unangetastet — sie sprechen
    weiterhin Stufenwort + Position und schreiben "Segment" AUS.

    Dieser Test ist HEUTE GRUEN und muss es bleiben; er ist der Gegenpol zu
    den SMS-Zusicherungen oben. Die byte-genaue Fassung desselben Wächters
    steht in ``tests/unit/test_official_alert_output_unchanged.py``
    (Schnappschuss ueber den GANZEN String je Kanal)."""
    from output.renderers.alert.official_alerts import (
        render_official_alert_mail_plain, render_official_alert_subject,
        render_official_alert_telegram, render_warn_block,
    )

    notices = _zwei_warnungen_segment_4(_trip())

    betreff = render_official_alert_subject(notices, prefix="KHW 403", tz=TZ)
    html = render_warn_block(
        notices, variant="standalone", source_label="GeoSphere Austria",
        source_url=None, stand_at="09:30", tz=TZ, context_label="KHW 403",
    )
    plain = render_official_alert_mail_plain(
        notices, source_label="GeoSphere Austria", stand_at="09:30", tz=TZ,
        context_label="KHW 403",
    )
    telegram = render_official_alert_telegram(
        notices, prefix="KHW 403", source_label="GeoSphere Austria", tz=TZ,
    )

    assert "GELB" in betreff and "Segment 4" in betreff, (
        f"AC-13: der Betreff behaelt Stufenwort und ausgeschriebenes Segment: "
        f"{betreff!r}"
    )
    assert "AMT" not in betreff, (
        f"AC-13: der Betreff trug nie einen 'AMT'-Marker — das bleibt so: "
        f"{betreff!r}"
    )
    assert "Segment 4" in html, (
        "AC-13: die E-Mail schreibt 'Segment' weiterhin AUS (die 'Seg'-"
        "Kurzform gilt nur fuer SMS-Koepfe)."
    )
    assert "Segment 4" in plain, (
        "AC-13: die Klartext-Mail schreibt 'Segment' weiterhin AUS."
    )
    assert "GELB" in telegram and "Segment 4" in telegram, (
        f"AC-13: die reiche Telegram-Vorlage bleibt unveraendert: "
        f"{telegram[:200]!r}"
    )


# ---------------------------------------------------------------------------
# AC-14 — "Seg" ist die GETEILTE SMS-Ortssprache aller Alarmarten
# ---------------------------------------------------------------------------

def test_ac14_amtliche_und_nowcast_sms_teilen_die_seg_kurzform():
    """AC-14: Given eine amtliche Warnung mit Segment-Umfang UND einen
    Nowcast-Onset-Alarm mit derselben Segment-Kennung / When beide ueber ihre
    jeweilige SMS-Renderfunktion gerendert werden / Then nennen BEIDE Koepfe
    "Seg 4" — waehrend E-Mail und Betreff desselben Onset-Alarms "Segment 4"
    ausgeschrieben zeigen."""
    from output.renderers.alert.model import AlertMessage, OnsetEvent
    from output.renderers.alert.render import (
        render_email, render_sms, render_subject,
    )

    amtlich = _render(_zwei_warnungen_segment_4(_trip()))

    onset = OnsetEvent(
        onset_minutes=8, onset_time="15:40", km_from=8.0, km_to=8.0,
        is_convective=True, intensity_label="Gewitter mit Hagel",
        source_label="Radar (ICON-D2)", segment_id="4",
    )
    msg = AlertMessage(
        trip_short="KHW 403", stand_at="10:00", events=(onset,), source="radar",
    )
    nowcast_sms = render_sms(msg)

    assert _kopf(amtlich) == "Seg 4", (
        f"AC-14: amtlicher SMS-Kopf muss 'Seg 4' lauten, bekam "
        f"{_kopf(amtlich)!r}"
    )
    assert _kopf(nowcast_sms) == "Seg 4", (
        f"AC-14: Nowcast-SMS-Kopf muss dieselbe Kurzform 'Seg 4' nutzen "
        f"(EINE geteilte Ortssprache), bekam {_kopf(nowcast_sms)!r}"
    )
    assert _kopf(amtlich) == _kopf(nowcast_sms), (
        "AC-14: beide Alarmarten muessen im SMS-Kopf identisch sprechen."
    )

    html, plain = render_email(msg)
    assert "Segment 4" in html and "Segment 4" in plain, (
        "AC-14 (Gegenprobe): die E-Mail desselben Onset-Alarms schreibt "
        "'Segment' weiterhin AUS."
    )
    assert "Segment 4" in render_subject(msg), (
        "AC-14 (Gegenprobe): der Betreff schreibt 'Segment' weiterhin AUS."
    )


# ---------------------------------------------------------------------------
# AC-15 (Vorbedingung aus S4) — Segment-Feld an OnsetPayload/NowcastFramesPayload
# ---------------------------------------------------------------------------

class TestAC15SegmentFeldAmPreviewEndpunkt:
    """AC-15: ``OfficialAlertPayload`` traegt ``segment_ids`` schon heute,
    ``OnsetPayload``/``NowcastFramesPayload`` fehlt das Feld — die Luecke aus
    S4 (issuecomment-5351380856). Nachweis ueber den ECHTEN Endpunkt, nicht
    ueber die DTO-Definition."""

    pytestmark = pytest.mark.real_data_root

    @pytest.fixture
    def client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from api.routers import validator
        app = FastAPI()
        app.include_router(validator.router)
        return TestClient(app)

    @pytest.fixture
    def stub_trip(self):
        user_id = f"test_1948s5ac15_{uuid.uuid4().hex[:8]}"
        trip_id = "trip-ac15"
        trip_dir = Path("data/users") / user_id / "briefings"
        trip_dir.mkdir(parents=True, exist_ok=True)
        (trip_dir / f"{trip_id}.json").write_text(json.dumps({
            "id": trip_id, "name": "AC-15 Trip", "stages": [],
        }))
        yield user_id, trip_id
        shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)

    def test_onset_payload_mit_segment_id_nennt_das_segment_im_kopf(
        self, client, stub_trip,
    ):
        """Given einen ``onset``-Payload, der ein Segment benennt / When der
        Payload in ein ``OnsetEvent`` uebersetzt wird / Then nennt der
        gerenderte Ortskopf dieses Segment statt des km-Rueckfalls."""
        user_id, trip_id = stub_trip
        resp = client.post(
            f"/api/trips/{trip_id}/alert-preview",
            params={"user_id": user_id},
            json={"onset": {
                "onset_minutes": 8, "onset_time": "15:40",
                "km_from": 8.0, "km_to": 8.0, "is_convective": True,
                "intensity_label": "Gewitter mit Hagel",
                "source_label": "Radar (ICON-D2)",
                "segment_id": "4",
            }},
        )
        assert resp.status_code == 200, f"Body: {resp.text[:300]}"
        sms = resp.json()["sms"]

        assert sms.startswith("Seg 4: "), (
            f"AC-15: der Preview muss das uebergebene Segment im Kopf nennen "
            f"('Seg 4: '), nicht auf den km-Rueckfall fallen: {sms!r}"
        )
        assert "km " not in sms, (
            f"AC-15: km-Rueckfall trotz uebergebener Segment-Kennung: {sms!r}"
        )

    def test_nowcast_frames_payload_mit_segment_id_nennt_das_segment_im_kopf(
        self, client, stub_trip,
    ):
        """Dieselbe Luecke im Frame-Replay-Zweig
        (``validator_render_service._render_nowcast_replay``)."""
        user_id, trip_id = stub_trip
        jetzt = datetime.now(timezone.utc)
        resp = client.post(
            f"/api/trips/{trip_id}/alert-preview",
            params={"user_id": user_id},
            json={"nowcast_frames": {
                "source": "radar",
                "frames": [
                    {"timestamp": (jetzt + timedelta(minutes=5)).isoformat(),
                     "precip_mm_h": 0.0, "is_convective": False},
                    {"timestamp": (jetzt + timedelta(minutes=20)).isoformat(),
                     "precip_mm_h": 2.5, "is_convective": False},
                    {"timestamp": (jetzt + timedelta(minutes=40)).isoformat(),
                     "precip_mm_h": 3.0, "is_convective": False},
                ],
                "km_from": 2.0, "km_to": 6.0,
                "segment_id": "4",
            }},
        )
        assert resp.status_code == 200, f"Body: {resp.text[:300]}"
        data = resp.json()
        assert data.get("onset_detected") is True, f"Setup: {data!r}"

        assert data["sms"].startswith("Seg 4: "), (
            f"AC-15: der Frame-Replay muss das uebergebene Segment im Kopf "
            f"nennen, nicht 'km 2-6': {data['sms']!r}"
        )


# ---------------------------------------------------------------------------
# AC-16 — Schnappschuss: nur trip_sms/compare_sms wechseln das Format
# ---------------------------------------------------------------------------

def test_ac16_schnappschuss_sms_felder_tragen_die_neue_grammatik():
    """AC-16: Given den Schnappschuss
    ``tests/fixtures/official_alert_render_snapshot_1944.json`` / When
    ``render_all()`` erneut laeuft / Then tragen ``trip_sms``/``compare_sms``
    die neue Grammatik (kein "AMT", kein Trip-/Preset-Name "GZ", genau ein
    "!"), waehrend Betreff/E-Mail/Telegram-rich unveraendert bleiben.

    Der Schnappschuss selbst wird in Phase 6 bewusst NEU ERZEUGT (kein
    Goldstring-Editieren) — dieser Test bewacht, WAS dabei herauskommen
    muss. Pfadregel #1409: die Fixture wird relativ zu DIESER Datei
    aufgeloest, nie ueber einen festen Hauptrepo-Pfad."""
    import sys

    unit_dir = Path(__file__).resolve().parents[1] / "unit"
    sys.path.insert(0, str(unit_dir))
    try:
        from test_official_alert_output_unchanged import SNAPSHOT, render_all
    finally:
        sys.path.remove(str(unit_dir))

    ist = render_all()

    for feld in ("trip_sms", "compare_sms"):
        text = ist[feld]
        assert not _AMT_MARKER.search(text), (
            f"AC-16: '{feld}' traegt noch den Quellen-Marker 'AMT': {text!r}"
        )
        assert not _LEVEL_WORD_POSITION.search(text), (
            f"AC-16: '{feld}' traegt noch die '{{WORT}}{{Pos}}/3'-Notation: "
            f"{text!r}"
        )
        assert "GZ" not in text, (
            f"AC-16: '{feld}' traegt noch den Trip-/Preset-Namen 'GZ': {text!r}"
        )
        assert text.count("!") == 1, (
            f"AC-16: '{feld}' muss genau EIN '!' tragen: {text!r}"
        )

    erwartet = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    unveraendert = [
        "trip_subject", "trip_html", "trip_mail_plain", "trip_telegram",
        "compare_subject", "compare_html", "compare_telegram",
    ]
    abweichungen = [k for k in unveraendert if ist[k] != erwartet[k]]
    assert not abweichungen, (
        "AC-16: die drei unveraenderten Kanaele beider Flaechen muessen "
        f"byte-genau bleiben; abweichend: {abweichungen!r}"
    )


# ---------------------------------------------------------------------------
# AC-17 — unbekannte Gefahrenart, bekannte Stufe
# ---------------------------------------------------------------------------

def test_ac17_unbekannte_gefahrenart_behaelt_den_stufenbuchstaben():
    """AC-17: Given eine Warnung mit einem ``hazard`` ausserhalb des
    zehnteiligen Katalogs, aber bekannter Stufe orange (3) / When sie gerendert
    wird / Then traegt das Fallback-Kuerzel trotzdem ":M" — nur der
    Gefahrentyp ist unbekannt, die Schwere bleibt bekannt."""
    from output.tokens.hazard_symbols import HAZARD_SMS_SYMBOLS, sms_symbol_for

    hazard = "thunder_squall"  # Kollisions-Kandidat laut sms_format.md Sz.4c
    assert hazard not in HAZARD_SMS_SYMBOLS, "Setup: hazard muss unbekannt sein."
    kuerzel = sms_symbol_for(hazard)

    sms = _render([
        _notice(_alert(
            hazard=hazard, level=3, label="Sturmböe",
            von=_heute(15), bis=_heute(21),
        )),
    ])

    assert f"{kuerzel}:M" in sms, (
        f"AC-17: das Fallback-Kuerzel '{kuerzel}' muss den Stufenbuchstaben "
        f"'M' tragen, bekam {sms!r}"
    )
    assert "TH:" not in sms, (
        f"AC-17: das Fallback darf nicht mit 'TH' (thunderstorm) kollidieren: "
        f"{sms!r}"
    )
