"""Alarm-Eskalation, Folgeperiode und Absenkung/Entwarnung (AC-12, AC-13).

SPEC: docs/specs/modules/avalanche_report_bulletin.md -- AC-12, AC-13
VERTRAG: docs/artifacts/feat-1441-s1-lawinenlagebericht/red-contract.md Abschnitt 5

Echter Eskalationspfad: `official_alert_revision_verdict` (beide Pfade -- exakter Schluessel und
Ueberlappung) mit Gedaechtnis-Eintraegen aus `official_alert_state_entry`. Die Alerts kommen aus
dem echten Parser auf aufgezeichneten Tagesdateien; dieselbe Mikroregion AT-07-25 hat am
19./20./21.02.2026 jeweils Stufe 4, die Gueltigkeitsfenster beruehren sich (je 16:00Z).
Die Stufe 5 stammt aus der abgeleiteten Datei (README der Fixtures).
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone


from tests.helpers.avalanche_report_support import parse_alert

UTC = timezone.utc
JETZT = datetime(2026, 2, 20, 8, 0, tzinfo=UTC)
MELDUNG = "2026-02-20T07:00:00+00:00"


def _tag(datum: str, region: str = "AT-07-25"):
    return parse_alert(f"{datum}_AT-07_de_CAAMLv6.json", region)


def _fuenf():
    return parse_alert("derived/2026-02-20_AT-07_de_CAAMLv6_DERIVED_very_high.json", "AT-07-25")


def _gedaechtnis(alert) -> dict:
    from output.renderers.alert.official_alerts import official_alert_state_entry, official_alert_state_key

    return {official_alert_state_key(alert): official_alert_state_entry(alert, MELDUNG)}


def _urteil(alert, state):
    from output.renderers.alert.official_alerts import official_alert_revision_verdict

    return official_alert_revision_verdict(alert, state, now=JETZT)


# ---------------------------------------------------------------- AC-12
def test_ac12_gedaechtnis_traegt_die_originalstufe_nicht_das_farblevel():
    vier, fuenf = _tag("2026-02-20"), _fuenf()

    (eintrag4,) = _gedaechtnis(vier).values()
    (eintrag5,) = _gedaechtnis(fuenf).values()

    assert eintrag4["last_reported_value"] == 4.0
    assert eintrag5["last_reported_value"] == 5.0, "abgeleitetes level (4) darf die 5 nicht verdecken"


def test_ac12_stufe_4_auf_5_in_derselben_periode_eskaliert():
    """Exakter Schluessel (gleiche Region, gleiches Fenster): abgeleitetes `level` ist beidseitig 4.
    Mutation `native_level` -> `level` laesst diesen Test rot werden."""
    from output.renderers.alert.official_alerts import official_alert_state_key

    vier, fuenf = _tag("2026-02-20"), _fuenf()
    assert vier.level == fuenf.level == 4
    assert official_alert_state_key(vier) == official_alert_state_key(fuenf), "Voraussetzung: derselbe Schluessel"

    melden, stale, merged = _urteil(fuenf, _gedaechtnis(vier))

    assert melden is True and stale is None and merged is None


def test_ac12_stufe_4_auf_5_in_der_folgeperiode_eskaliert_ueber_den_ueberlappungspfad():
    """Gestern Stufe 4 (Fenster 19.02.-20.02. 16:00Z), heute Stufe 5 (Fenster beruehrt): anderer
    Schluessel, Eskalationspfad der Ueberlappung."""
    from output.renderers.alert.official_alerts import official_alert_state_key

    gestern, heute = _tag("2026-02-19"), _fuenf()
    assert official_alert_state_key(gestern) != official_alert_state_key(heute)

    melden, _stale, _merged = _urteil(heute, _gedaechtnis(gestern))

    assert melden is True


def test_ac12_gleiche_stufe_in_neuer_periode_am_folgetag_loest_keinen_alarm_aus():
    """Taeglich 17:00 erscheint ein neues Fenster. Stufe 4 -> Stufe 4 (20.02. -> 21.02.) ist
    dieselbe Lage und darf nicht erneut alarmieren; das Gedaechtnis wird still fortgeschrieben."""
    from output.renderers.alert.official_alerts import official_alert_state_key

    heute, morgen = _tag("2026-02-20"), _tag("2026-02-21")
    assert official_alert_state_key(heute) != official_alert_state_key(morgen), "Voraussetzung: neue Periode"
    assert heute.valid_to == morgen.valid_from, "Voraussetzung: die Fenster beruehren sich (17:00 Ortszeit)"

    melden, stale, merged = _urteil(morgen, _gedaechtnis(heute))

    assert melden is False
    assert stale == official_alert_state_key(heute)
    assert merged is not None and merged["last_reported_value"] == 4.0
    assert merged["valid_to"] == morgen.valid_to.isoformat()


def test_ac12_kette_ueber_drei_tage_bleibt_still():
    tage = [_tag("2026-02-19"), _tag("2026-02-20"), _tag("2026-02-21")]
    state = _gedaechtnis(tage[0])
    for vorher, nachher in zip(tage, tage[1:]):
        melden, stale, merged = _urteil(nachher, state)
        assert melden is False
        del state[stale]
        from output.renderers.alert.official_alerts import official_alert_state_key
        state[official_alert_state_key(nachher)] = merged

    assert len(state) == 1


def test_ac12_dieselbe_meldung_wird_nicht_wiederholt():
    vier = _tag("2026-02-20")

    melden, _stale, _merged = _urteil(vier, _gedaechtnis(vier))

    assert melden is False


def test_ac12_erstmeldung_ohne_gedaechtnis_wird_gemeldet():
    melden, _stale, _merged = _urteil(_tag("2026-02-20"), {})

    assert melden is True


def test_ac12_eskalation_4_auf_5_bleibt_nach_stiller_fortschreibung_erhalten():
    """Gedaechtnis nach 4 (gestern), 4 (heute, still), dann 5 (heute, hoeher) -> melden."""
    from output.renderers.alert.official_alerts import official_alert_state_key

    gestern, heute, fuenf = _tag("2026-02-19"), _tag("2026-02-20"), _fuenf()
    state = _gedaechtnis(gestern)
    melden, stale, merged = _urteil(heute, state)
    assert melden is False
    del state[stale]
    state[official_alert_state_key(heute)] = merged

    melden5, _s, _m = _urteil(fuenf, state)

    assert melden5 is True


# ---------------------------------------------------------------- AC-13
def _vier_und_zwei_am_grenzpunkt():
    vier = parse_alert("derived/2026-02-20_AT-07_de_CAAMLv6_DERIVED_border_4_4.json", "AT-07-04-02")
    zwei = parse_alert("derived/2026-02-20_AT-07_de_CAAMLv6_DERIVED_border_2_4.json", "AT-07-04-02")
    assert (vier.native_level, zwei.native_level) == (4, 2)
    return vier, zwei


def test_ac13_absenkung_von_4_auf_2_wird_nicht_als_neue_warnung_gemeldet():
    vier, zwei = _vier_und_zwei_am_grenzpunkt()

    melden, _stale, _merged = _urteil(zwei, _gedaechtnis(vier))

    assert melden is False


def test_ac13_absenkung_in_beruehrender_folgeperiode_behaelt_den_alten_hoechstwert_im_gedaechtnis():
    vier, zwei = _vier_und_zwei_am_grenzpunkt()
    zwei_morgen = replace(zwei, valid_from=vier.valid_to, valid_to=vier.valid_to + timedelta(days=1))

    melden, stale, merged = _urteil(zwei_morgen, _gedaechtnis(vier))

    assert melden is False and merged is not None
    assert merged["last_reported_value"] == 4.0, "die alte Dringlichkeit bleibt im Gedaechtnis"


def test_ac13_absenkung_traegt_die_dringlichkeit_des_alten_werts():
    from services import alert_urgency

    vier, zwei = _vier_und_zwei_am_grenzpunkt()

    assert alert_urgency.urgency_from_official_transition(vier, zwei) == "HIGH", \
        "Stufe 4 -> 2: Dringlichkeit des ALTEN Werts (HIGH), nicht die der neuen Stufe 2 (LOW)"


def test_ac13_entwarnung_traegt_die_dringlichkeit_des_alten_werts():
    from services import alert_urgency

    vier, _zwei = _vier_und_zwei_am_grenzpunkt()

    assert alert_urgency.urgency_from_official_transition(vier, None) == "HIGH"


def test_ac13_mittlere_stufe_bleibt_mittlere_dringlichkeit_bei_absenkung():
    """Stufe 3 (echt) -> Stufe 2 (abgeleitet): MODERATE, nicht LOW."""
    from services import alert_urgency

    drei = parse_alert("2026-02-20_AT-07_de_CAAMLv6.json", "AT-07-04-02")
    _vier, zwei = _vier_und_zwei_am_grenzpunkt()
    assert drei.native_level == 3

    assert alert_urgency.urgency_from_official_transition(drei, zwei) == "MODERATE"
    assert alert_urgency.urgency_from_official_transition(drei, None) == "MODERATE"


def test_ac13_stufe_5_entwarnung_ist_hoch():
    from services import alert_urgency

    assert alert_urgency.urgency_from_official_transition(_fuenf(), None) == "HIGH"


def test_ac13_anstieg_nutzt_den_hoeheren_der_beiden_werte():
    """Symmetrie wie `_ordinal_severity`: das Maximum aus alt und neu."""
    from services import alert_urgency

    vier, zwei = _vier_und_zwei_am_grenzpunkt()

    assert alert_urgency.urgency_from_official_transition(zwei, vier) == "HIGH"
