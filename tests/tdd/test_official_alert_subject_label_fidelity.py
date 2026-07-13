"""Betreff-Label-Fidelity amtlicher Warnungen (Issue #1216 F004).

SPEC: docs/specs/modules/issue_1216_f004_label_fidelity.md (AC-1..AC-7)

Der Mail-Betreff amtlicher Warnungen zeigt aktuell nur ein sauberes Typ-Wort
(`_hazard_display()[0]`) statt des vollen Detail-Labels, das die Quelle liefert.
Bei Massiv-Sperren (`hazard=access_ban`) geht der Massiv-Name verloren, bei
Vigilance-Extremhitze wird "Extreme Hitze" zu "Hitze" verkuerzt.

RED-Phase: `_typ_tag()` bevorzugt heute noch nicht `alert.label`. Deshalb sind
die Detail-Tests (Test 1/2/3/5/7) ROT; die Invarianten (Test 4/6) sind bereits
GRUEN und muessen es NACH dem Fix bleiben (Standardfaelle + Body/SMS unangetastet).

Verhaltenstests — KEINE Mocks. Echte `OfficialAlert`/`OfficialAlertNotice`-
Objekte, reine Renderer-Funktionen (Muster wie
`tests/tdd/test_official_alert_template_render.py`).
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from services.official_alerts.models import OfficialAlert

UTC = timezone.utc
# Freitag 2026-07-10 (ganztaegig) und Samstag 2026-07-11 15–21 Uhr.
FR_ALLDAY_FROM = datetime(2026, 7, 10, 0, 0, tzinfo=UTC)
FR_ALLDAY_TO = datetime(2026, 7, 10, 23, 59, tzinfo=UTC)
SA_FROM = datetime(2026, 7, 11, 15, 0, tzinfo=UTC)
SA_TO = datetime(2026, 7, 11, 21, 0, tzinfo=UTC)


def _alert(level: int, hazard: str, label: str, vf, vt, region="Rotwand-Massiv",
           dedup_id=None) -> OfficialAlert:
    return OfficialAlert(
        source="geosphere", hazard=hazard, level=level, label=label,
        valid_from=vf, valid_to=vt, region_label=region, dedup_id=dedup_id,
    )


def _notice(alert, scope_label="gesamte Route", sms_scope="ges.Route",
            affected_chips=None, free_chips=None):
    from output.renderers.alert.official_alerts import OfficialAlertNotice
    return OfficialAlertNotice(
        alert=alert, scope_label=scope_label, sms_scope=sms_scope,
        affected_chips=affected_chips or ["Segment 1"], free_chips=free_chips or [],
    )


# ---------------------------------------------------------------------------
# Test 1 (AC-1) — access_ban Voll-Sperre: Massiv-Name im Betreff.
# ---------------------------------------------------------------------------
def test_ac1_access_ban_full_closure_shows_massif_in_subject():
    from output.renderers.alert.official_alerts import render_official_alert_subject
    notice = _notice(
        _alert(2, "access_ban", "Zugang gesperrt — Rotwand-Massiv", SA_FROM, SA_TO),
        scope_label="gesamte Route",
    )
    subject = render_official_alert_subject([notice], prefix="KHW 403")
    assert "Zugang gesperrt — Rotwand-Massiv" in subject, (
        f"Betreff verliert den Massiv-Namen (erwartet '…Rotwand-Massiv…'): {subject!r}"
    )


# ---------------------------------------------------------------------------
# Test 2 (AC-2) — beide weiteren Label-Varianten tragen den Massiv-Namen.
# ---------------------------------------------------------------------------
def test_ac2_access_ban_label_variants_keep_massif():
    from output.renderers.alert.official_alerts import render_official_alert_subject
    for label in (
        "Zugang eingeschränkt — Rotwand-Massiv",
        "Zugang gesperrt (total) — Rotwand-Massiv",
    ):
        notice = _notice(
            _alert(2, "access_ban", label, SA_FROM, SA_TO),
            scope_label="gesamte Route",
        )
        subject = render_official_alert_subject([notice], prefix="KHW 403")
        assert label in subject, (
            f"Variante verliert das volle Label (erwartet {label!r}): {subject!r}"
        )
        assert "Rotwand-Massiv" in subject


# ---------------------------------------------------------------------------
# Test 3 (AC-3) — Vigilance extreme_heat: "Extreme Hitze" statt nur "Hitze".
# ---------------------------------------------------------------------------
def test_ac3_vigilance_extreme_heat_full_label():
    from output.renderers.alert.official_alerts import render_official_alert_subject
    notice = _notice(
        _alert(3, "extreme_heat", "Extreme Hitze", FR_ALLDAY_FROM, FR_ALLDAY_TO,
               region="Haute-Corse"),
        scope_label="gesamte Route",
    )
    subject = render_official_alert_subject([notice], prefix="KHW 403")
    assert "Extreme Hitze" in subject, (
        f"Betreff verkuerzt 'Extreme Hitze' zu 'Hitze': {subject!r}"
    )


# ---------------------------------------------------------------------------
# Test 4 (AC-4, Invariante) — Standardfall label==Typ-Wort: Betreff bit-identisch.
# Erwartungswerte = HEUTIGER Output (fixiert), muss auch NACH dem Fix gruen sein.
# ---------------------------------------------------------------------------
def test_ac4_standard_case_subject_bit_identical_single():
    from output.renderers.alert.official_alerts import render_official_alert_subject
    notice = _notice(
        _alert(2, "thunderstorm", "Gewitter", SA_FROM, SA_TO, region="Hermagor"),
        scope_label="gesamte Route",
    )
    subject = render_official_alert_subject([notice], prefix="KHW 403")
    assert subject == "[KHW 403] gesamte Route · GELB Gewitter (Sa)", (
        f"Standardfall (Label==Typ-Wort) darf sich nicht aendern: {subject!r}"
    )


def test_ac4_standard_case_subject_bit_identical_bundle():
    from output.renderers.alert.official_alerts import render_official_alert_subject
    hitze = _notice(
        _alert(2, "extreme_heat", "Hitze", FR_ALLDAY_FROM, FR_ALLDAY_TO, region="Hermagor"),
        scope_label="gesamte Route",
    )
    gewitter = _notice(
        _alert(2, "thunderstorm", "Gewitter", SA_FROM, SA_TO, region="Hermagor"),
        scope_label="gesamte Route",
    )
    subject = render_official_alert_subject([hitze, gewitter], prefix="KHW 403")
    assert subject == "[KHW 403] gesamte Route · GELB Hitze (Fr) + Gewitter (Sa)", (
        f"Bündel-Standardfall darf sich nicht aendern: {subject!r}"
    )


# ---------------------------------------------------------------------------
# Test 5 (AC-5) — Bündel access_ban + Standard: nur access_ban traegt Detail,
# Reihenfolge/Trenner unveraendert.
# ---------------------------------------------------------------------------
def test_ac5_bundle_only_access_ban_carries_detail():
    from output.renderers.alert.official_alerts import render_official_alert_subject
    # Beide GELB: Sortierung nach valid_from aufsteigend -> Gewitter (Fr) zuerst,
    # dann access_ban (Sa). So bleibt die Standard-Warnung ganz vorne kompakt.
    gewitter = _notice(
        _alert(2, "thunderstorm", "Gewitter", FR_ALLDAY_FROM, FR_ALLDAY_TO, region="Hermagor"),
        scope_label="gesamte Route",
    )
    access_ban = _notice(
        _alert(2, "access_ban", "Zugang gesperrt — Rotwand-Massiv", SA_FROM, SA_TO),
        scope_label="gesamte Route",
    )
    subject = render_official_alert_subject([gewitter, access_ban], prefix="KHW 403")
    # access_ban-Tag traegt das Detail (RED heute).
    assert "Zugang gesperrt — Rotwand-Massiv (Sa)" in subject, (
        f"access_ban-Tag ohne Massiv-Detail: {subject!r}"
    )
    # Standard-Tag bleibt kompakt (unveraendert, kein aufgeblaehtes Label).
    assert "Gewitter (Fr)" in subject, subject
    # Trenner + Reihenfolge unveraendert: Standard vor access_ban.
    assert " + " in subject
    assert subject.index("Gewitter (Fr)") < subject.index("Zugang gesperrt")
    # Einheitliche Stufe -> genau EIN gemeinsames Stufen-Wort vorne.
    assert subject.startswith("[KHW 403] gesamte Route · GELB ")


# ---------------------------------------------------------------------------
# Test 6 (AC-6, Invariante) — HTML-Notice, Plain-Notice und SMS bleiben
# unveraendert (der Fix beruehrt nur `_typ_tag`, also nur den Betreff).
# Erwartungswerte = HEUTIGER Output (fixiert).
# ---------------------------------------------------------------------------
def _ab_and_vigilance_notices():
    ab = _alert(2, "access_ban", "Zugang gesperrt — Rotwand-Massiv", SA_FROM, SA_TO,
                region="Rotwand-Massiv")
    vig = _alert(3, "extreme_heat", "Extreme Hitze", FR_ALLDAY_FROM, FR_ALLDAY_TO,
                 region="Haute-Corse")
    return ab, vig, _notice(ab), _notice(vig)


def test_ac6_html_notice_unchanged():
    """AC-6-Invariante NACH #1233 Slice B: `render_official_alert_html` wurde
    auf das SOLL-Design gehoben (Issue #1233, Redesign explizit spec-
    mandatiert) -- das alte byte-exakte Markup ist daher bewusst NICHT mehr
    identisch (Klassen `.verdict`/`.warns`/`.warn.stacked`/`.facts`/`.src`
    statt der alten Struktur). Die eigentliche Invariante DIESES Tests -- die
    Detail-Fidelity aus `_typ_tag` (voller Label statt gekuerztem Typ-Wort)
    fliesst unveraendert in den `.type`-Text, Region-Dedup in `.src` bleibt --
    wird strukturell weitergeprueft (BeautifulSoup statt Byte-Vergleich).

    #1238 AC-4 (angepasst): der reichere Quell-Label ERSETZT das Typ-Wort, statt
    ihm nachgestellt zu werden. Die frueher hier eingefrorenen Titel ("Hitze —
    Extreme Hitze", "Zugang gesperrt — Zugang gesperrt — Rotwand-Massiv") waren
    genau der doppelte Warn-Titel aus Issue #1238 — die Detail-Fidelity (voller
    Label statt gekuerztem Typ-Wort) bleibt erhalten, die Dopplung faellt weg."""
    from bs4 import BeautifulSoup

    from output.renderers.alert.official_alerts import render_official_alert_html
    _ab, _vig, n_ab, n_vig = _ab_and_vigilance_notices()
    html = render_official_alert_html(
        [n_ab, n_vig], source_label="GeoSphere Austria", stand_at="09:30", tz=UTC,
    )
    soup = BeautifulSoup(html, "html.parser")
    types = [t.get_text(strip=True) for t in soup.select(".type")]
    assert types == [
        "Extreme Hitze",
        "Zugang gesperrt — Rotwand-Massiv",
    ], f"Detail-Fidelity aus _typ_tag hat sich veraendert: {types!r}"
    body_text = soup.get_text(" ", strip=True)
    assert "Fr 10.07. · ganztägig" in body_text
    assert "Sa 11.07. · 15:00–21:00" in body_text
    src = soup.select_one(".src")
    assert src is not None, ".src-Box fehlt"
    src_text = src.get_text()
    assert "Haute-Corse" in src_text and "Rotwand-Massiv" in src_text
    assert "GeoSphere Austria" in src_text


def test_ac6_plain_notice_unchanged():
    from output.renderers.alert.official_alerts import render_official_alert_notice_plain
    ab, vig, _n_ab, _n_vig = _ab_and_vigilance_notices()
    plain = render_official_alert_notice_plain([(ab, []), (vig, [])], tz=UTC)
    assert plain == [
        "GELB — Zugang gesperrt — Rotwand-Massiv",
        "Region: Rotwand-Massiv",
        "Gültig: Sat 11.07. 15:00 – Sat 11.07. 21:00",
        "",
        "ORANGE — Extreme Hitze",
        "Region: Haute-Corse",
        "Gültig: Fri 10.07. 00:00 – Fri 10.07. 23:59",
    ], f"Plain-Notice hat sich veraendert: {plain!r}"


def test_ac6_sms_unchanged():
    from output.renderers.alert.official_alerts import render_official_alert_sms
    _ab, _vig, n_ab, n_vig = _ab_and_vigilance_notices()
    sms = render_official_alert_sms([n_ab, n_vig], sms_prefix="KHW403")
    assert sms == "KHW403 AMT: HZ ORANGE Fr ges.Route + ZG GELB Sa15-21 ges.Route", (
        f"SMS hat sich veraendert: {sms!r}"
    )


# ---------------------------------------------------------------------------
# Test 7 (AC-7) — Trip- UND Compare-Pfad liefern denselben detailtreuen Typ-Tag.
# ---------------------------------------------------------------------------
def test_ac7_trip_and_compare_paths_same_detailed_tag():
    from app.trip import Stage, Trip, Waypoint
    from output.renderers.alert.official_alerts import (
        build_compare_official_alert_notices, build_official_alert_notices,
        render_official_alert_subject,
    )

    label = "Zugang gesperrt — Rotwand-Massiv"

    # Trip-Pfad: build_official_alert_notices -> render_official_alert_subject.
    stage = Stage(
        id="s1", name="Tag 1", date=date(2026, 7, 11),
        waypoints=[
            Waypoint(id="w1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0),
            Waypoint(id="w2", name="Ziel", lat=47.1, lon=11.1, elevation_m=1200.0),
        ],
    )
    trip = Trip(id="tdd-1216-f004-trip", name="KHW 403", stages=[stage])
    trip_tagged = [(_alert(2, "access_ban", label, SA_FROM, SA_TO, dedup_id="rotwand"), ["1"])]
    trip_notices = build_official_alert_notices(trip, trip_tagged)
    trip_subject = render_official_alert_subject(trip_notices, prefix="KHW 403")

    # Compare-Pfad: build_compare_official_alert_notices -> gleicher Renderer.
    compare_tagged = [(_alert(2, "access_ban", label, SA_FROM, SA_TO, dedup_id="rotwand"), ["loc1"])]
    compare_notices = build_compare_official_alert_notices(
        all_location_ids=["loc1", "loc2"],
        id_to_name={"loc1": "Rotwand", "loc2": "Tegernsee"},
        tagged_alerts=compare_tagged,
    )
    compare_subject = render_official_alert_subject(compare_notices, prefix="Vergleich")

    # Beide Pfade tragen denselben detailtreuen Typ-Tag (RED heute) — keine Divergenz.
    assert label in trip_subject, f"Trip-Pfad verliert das Detail: {trip_subject!r}"
    assert label in compare_subject, f"Compare-Pfad verliert das Detail: {compare_subject!r}"
    tag = "Zugang gesperrt — Rotwand-Massiv (Sa)"
    assert tag in trip_subject and tag in compare_subject, (
        f"Divergenz zwischen Trip {trip_subject!r} und Compare {compare_subject!r}"
    )


# ---------------------------------------------------------------------------
# Test 8 (F001, PO-go) — Vigilance wind_gust: volles Label "Sturmböen" statt
# nur des Typ-Worts "Sturm". Das Typ-Wort "Sturm" (aus _HAZARD_DISPLAY[
# "wind_gust"]) steckt im Label, also greift die detailtreue Bevorzugung —
# der Betreff zeigt "Sturmböen", nicht das isolierte kurze "Sturm".
# ---------------------------------------------------------------------------
def test_f001_vigilance_wind_gust_shows_stormboeen():
    from output.renderers.alert.official_alerts import render_official_alert_subject
    notice = _notice(
        _alert(3, "wind_gust", "Sturmböen", FR_ALLDAY_FROM, FR_ALLDAY_TO,
               region="Haute-Corse"),
        scope_label="gesamte Route",
    )
    subject = render_official_alert_subject([notice], prefix="KHW 403")
    assert "Sturmböen" in subject, (
        f"Betreff verkuerzt 'Sturmböen' zum Typ-Wort 'Sturm': {subject!r}"
    )
    # Das isolierte kurze Typ-Wort-Tag "Sturm (…" darf nicht statt des Details
    # erscheinen — nach "Sturm" folgt hier "böen", nie direkt " (".
    assert "Sturm (" not in subject, (
        f"Detail-Label wird nicht gezeigt, nur kurzes 'Sturm (…': {subject!r}"
    )
