"""Der Lagebericht in Briefing-SMS, Alarm-SMS und Premium-SMS (AC-17, AC-18, AC-21).

SPEC: docs/specs/modules/avalanche_report_bulletin.md -- AC-17, AC-18, AC-21
VERTRAG: docs/artifacts/feat-1441-s1-lawinenlagebericht/red-contract.md Abschnitt 4/6

Echter `SMSTripFormatter().format_sms` (Briefing), echter `render_official_alert_sms` (Alarm; der
Premium-SMS-Pfad `notification_service.send_official_alert` ruft DIESELBE Funktion mit dem Limit
`channel_layout.CHANNEL_LIMITS["premium_sms"]["max_chars"]` auf). Alerts: echter Parser auf
aufgezeichneten Bulletins, Stufe 5 aus der abgeleiteten Datei (README der Fixtures).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from tests.helpers.avalanche_report_support import notice, parse_alert

UTC = timezone.utc
_TZ = ZoneInfo("UTC")


def _stufe(n: int):
    quelle = {
        1: ("2026-03-01_AT-02_de_CAAMLv6.json", "AT-02-05-02", "AT-02"),
        2: ("2026-03-01_AT-07_de_CAAMLv6.json", "AT-07-29-02", "AT-07"),
        3: ("2026-01-30_AT-07_de_CAAMLv6.json", "AT-07-28", "AT-07"),
        4: ("2026-02-20_AT-07_de_CAAMLv6.json", "AT-07-25", "AT-07"),
        5: ("derived/2026-02-20_AT-07_de_CAAMLv6_DERIVED_very_high.json", "AT-07-25", "AT-07"),
    }[n]
    return parse_alert(quelle[0], quelle[1], source=f"avalanche_report:{quelle[2]}")


def _av_token(text: str, ziffer: int) -> list[str]:
    return re.findall(rf"(?<![A-Za-z0-9])AV{ziffer}(?![0-9A-Za-z:@])", text)


def _briefing_sms(alerts, av_spec_enabled: bool | None, **kwargs) -> str:
    from output.renderers.sms_trip import SMSTripFormatter
    from output.tokens.dto import MetricSpec
    from tests.tdd.test_sms_official_alert_tokens import _DISABLE_NEW_14, _segment

    disabled = list(_DISABLE_NEW_14)
    if av_spec_enabled is not None:
        disabled.append(MetricSpec(symbol="AV", enabled=av_spec_enabled))
    return SMSTripFormatter().format_sms(
        [_segment(alerts)], stage_name="Etappe 5", tz=_TZ, disabled_specs=disabled, **kwargs,
    )


# ---------------------------------------------------------------- AC-17: Briefing-SMS, AV genau einmal
@pytest.mark.parametrize("metrik", [True, False, None], ids=["AV-sichtbar", "AV-ausgeschaltet", "AV-nicht-konfiguriert"])
def test_ac17_stufe_4_steht_genau_einmal_als_av4_im_warnblock(metrik):
    sms = _briefing_sms([_stufe(4)], metrik)

    assert len(_av_token(sms, 4)) == 1, f"AV4 muss genau einmal vorkommen: {sms!r}"
    assert "!" in sms and sms.index("!") < sms.index("AV4"), f"AV4 gehoert in den !-Block: {sms!r}"
    assert sms.count("AV") == 1, f"es darf kein zweites AV-Token geben: {sms!r}"


def test_ac17_token_hat_keinen_doppelpunkt_keinen_buchstaben_und_keine_stunde():
    sms = _briefing_sms([_stufe(4)], None)

    assert "AV:" not in sms
    assert not re.search(r"AV4[LMH]", sms)
    assert not re.search(r"AV4@", sms), "die Ausgabezeit des Bulletins (17:00) ist keine Warnstunde"


def test_ac17_sichtbare_und_ausgeschaltete_metrik_liefern_dieselbe_nachricht():
    """Die Stufe kommt unabhaengig von der Metrik-Einstellung an (Kanalparitaet)."""
    assert _briefing_sms([_stufe(4)], True) == _briefing_sms([_stufe(4)], False)


def test_ac17_stufe_5_steht_als_originalziffer_obwohl_das_farblevel_4_ist():
    sms = _briefing_sms([_stufe(5)], False)

    assert len(_av_token(sms, 5)) == 1, sms
    assert not _av_token(sms, 4), "5 darf nicht zu 4 umgedeutet werden"


def test_ac17_stufe_2_erscheint_bei_voreinstellung_stufe_1_nicht():
    """Stufenfilter wie bei allen amtlichen Warnungen: Voreinstellung ab Stufe 2."""
    assert len(_av_token(_briefing_sms([_stufe(2)], None), 2)) == 1
    sms1 = _briefing_sms([_stufe(1)], None)
    assert "AV" not in sms1 and "!" not in sms1


def test_ac17_stufenfilter_folgt_der_kanal_schwelle():
    """`sms_alert_min_level=4`: Stufe 3 faellt heraus, Stufe 4 und 5 bleiben."""
    assert "AV3" not in _briefing_sms([_stufe(3)], None, sms_alert_min_level=4)
    assert len(_av_token(_briefing_sms([_stufe(4)], None, sms_alert_min_level=4), 4)) == 1
    assert len(_av_token(_briefing_sms([_stufe(5)], None, sms_alert_min_level=4), 5)) == 1


def test_ac17_lagebericht_und_meteoalarm_lawine_haben_getrennte_kuerzel():
    """`AW` = MeteoAlarm-Warnung (Awareness), `AV` = Lagebericht (EAWS) -- beide koennen nebeneinander stehen."""
    from services.official_alerts.models import OfficialAlert

    aw = OfficialAlert(source="meteoalarm", hazard="avalanche", level=3, label="Lawine",
                       valid_from=datetime(2026, 7, 15, 6, 0, tzinfo=UTC), valid_to=datetime(2026, 7, 15, 20, 0, tzinfo=UTC),
                       region_label="Tirol")
    sms = _briefing_sms([aw, _stufe(4)], None)

    assert len(_av_token(sms, 4)) == 1
    assert re.search(r"(?<![A-Za-z])AW:M", sms), sms


# ---------------------------------------------------------------- AC-18: Alarm-SMS und Premium-SMS
def _alarm(alerts, *, limit=None, sms_scope="ges.Route"):
    from output.renderers.alert.official_alerts import render_official_alert_sms

    kwargs = {} if limit is None else {"limit": limit}
    return render_official_alert_sms([notice(a, sms_scope=sms_scope) for a in alerts], tz=_TZ, **kwargs)


def _premium_limit() -> int:
    from output.renderers.channel_layout import CHANNEL_LIMITS

    return CHANNEL_LIMITS["premium_sms"]["max_chars"]


def test_ac18_alarm_sms_traegt_av5_mit_originalziffer_ohne_buchstaben_im_budget():
    sms = _alarm([_stufe(5)])

    assert len(_av_token(sms, 5)) == 1, sms
    assert not re.search(r"AV5?:", sms), "kein Doppelpunkt/Stufenbuchstabe"
    assert not re.search(r"AV5[LMH]", sms)
    assert sms.startswith("!") or "!AV5" in sms
    assert len(sms) <= 140, f"Alarm-SMS ueber Budget: {len(sms)}"
    assert sms.isascii()


def test_ac18_premium_sms_traegt_av5_im_budget_des_premium_kanals():
    limit = _premium_limit()
    text = _alarm([_stufe(5)], limit=limit)

    assert limit == 153
    assert len(_av_token(text, 5)) == 1, text
    assert not re.search(r"AV5[:LMH]", text)
    assert len(text) <= limit, f"Premium-SMS ueber Budget: {len(text)}"


@pytest.mark.parametrize("ziffer", [1, 2, 3, 4, 5])
def test_ac18_jede_stufe_erscheint_mit_ihrer_ziffer_nie_als_l_m_h(ziffer):
    sms = _alarm([_stufe(ziffer)])

    assert len(_av_token(sms, ziffer)) == 1, f"Stufe {ziffer}: {sms!r}"
    assert not re.search(r"AV\d?[:LMH]", sms)


def test_ac18_langer_ortsname_laesst_das_token_nicht_aus_dem_budget_fallen():
    ort = "Sehr-langer-Etappen-und-Huettenname-in-den-Stubaier-Alpen-Nordseite"
    for limit in (140, _premium_limit()):
        text = _alarm([_stufe(5)], limit=limit, sms_scope=ort)

        assert len(text) <= limit
        assert len(_av_token(text, 5)) == 1, text


def test_ac18_gemischte_nachricht_nennt_lagebericht_und_gewitter():
    from services.official_alerts.models import OfficialAlert

    ts = OfficialAlert(source="meteoalarm", hazard="thunderstorm", level=4, label="Gewitter",
                       valid_from=datetime(2026, 2, 20, 12, 0, tzinfo=UTC), valid_to=datetime(2026, 2, 20, 18, 0, tzinfo=UTC),
                       region_label="Tirol")
    sms = _alarm([_stufe(5), ts])

    assert len(_av_token(sms, 5)) == 1 and "TS:H" in sms, sms
    assert len(sms) <= 140


# ---------------------------------------------------------------- AC-21: kein zweites AV aus _wintersport
def test_ac21_wintersport_baut_kein_av_token_mehr_auch_nicht_bei_sichtbarer_metrik():
    from output.tokens.builder import _wintersport
    from output.tokens.dto import DailyForecast, MetricSpec

    day = DailyForecast(avalanche_level=4, snow_depth_cm=80.0)
    tokens = _wintersport(day, {"AV": MetricSpec(symbol="AV", enabled=True),
                                "SD": MetricSpec(symbol="SD", enabled=True)}, "evening")

    symbole = [t.symbol for t in tokens]
    assert "SD" in symbole, "Gegenprobe: die uebrigen Wintersport-Token funktionieren weiter"
    assert "AV" not in symbole, f"_wintersport darf AV nicht mehr erzeugen: {symbole}"


def test_ac21_wintersport_ohne_av_spec_baut_ebenfalls_kein_av_token():
    from output.tokens.builder import _wintersport
    from output.tokens.dto import DailyForecast

    tokens = _wintersport(DailyForecast(avalanche_level=3, snow_depth_cm=10.0), {}, "morning")

    assert all(t.symbol != "AV" for t in tokens)


def test_ac21_trip_ohne_av_metrik_erhaelt_nie_ein_zweites_av_token_neben_dem_lagebericht():
    sms = _briefing_sms([_stufe(3)], None)

    assert sms.count("AV") == 1 and len(_av_token(sms, 3)) == 1, sms
