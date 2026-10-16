"""Entwarnungs-Pruefungen E-1..E-4 des Official-Alert-Mail-Validators
(Issue #1441 Scheibe S2, Adversary F008).

SPEC: docs/specs/modules/feat_1441_s2_entwarnung.md -- AC-16, Abschnitt
      "E2E- und Staging-Strecke".

Mock-frei: die Mails werden mit den ECHTEN Renderern des Versandpfads
(`notification_service._official_subject` / `_official_mail_bodies`) erzeugt
und ueber die echte `build_mime_message()`-Pipeline gebaut -- genau das, was
`EmailOutput.send()` verschickt. Der Validator wird relativ zu dieser
Testdatei geladen (nie ueber den Hauptrepo-Pfad).
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

VALIDATOR_PATH = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "official_alert_mail_validator.py"
TZ = ZoneInfo("Europe/Vienna")


@pytest.fixture(scope="module")
def validator():
    spec = importlib.util.spec_from_file_location("_official_alert_mail_validator_e", VALIDATOR_PATH)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except ImportError as exc:  # Hook-Infrastruktur (Plugin) fehlt, z. B. CI-Runner
        pytest.skip(f"Validator nicht ladbar: {exc}")
    return mod


def _notices(region: str = "Innsbruck-Land"):
    from output.renderers.alert import official_alerts as oa

    return [
        oa.OfficialAllClearNotice("lowered", "thunderstorm", "Gewitter", region, "Segment 1",
                                  "Seg 1", 4, 2, 4, 2, "geosphere_warn"),
        oa.OfficialAllClearNotice("ended", "extreme_heat", "Hitze", region, "Segment 1",
                                  "Seg 1", 3, 0, 3, 0, "geosphere_warn"),
    ]


def _warnungen():
    from output.renderers.alert import official_alerts as oa
    from services.official_alerts.models import OfficialAlert

    now = datetime.now(timezone.utc)
    sturm = OfficialAlert(source="geosphere_warn", hazard="wind_gust", level=3, label="Sturmwarnung",
                          region_label="Innsbruck-Land", valid_from=now, valid_to=now + timedelta(hours=6))
    return oa.build_official_alert_notices(None, [(sturm, ["1"])])


def _mail(dto, ac, *, betreff=None, verfaelschen=None):
    from output.channels.email import build_mime_message
    from services import notification_service as ns

    label = ns._official_allclear_source_label(dto, ac)
    subject = betreff or ns._official_subject(dto, ac, prefix="Hoehenweg", tz=TZ)
    html, plain = ns._official_mail_bodies(dto, ac, source_label=label, source_url=None,
                                           stand_at="10:00", tz=TZ, context_label="Hoehenweg")
    if verfaelschen:
        html, plain = verfaelschen(html), verfaelschen(plain)
    return build_mime_message(subject, html, "a@henemm.com", "b@henemm.com", None, True, plain,
                              mail_type="official-alert")


def test_echte_entwarnungs_mails_bestehen(validator):
    """Reine und gemischte Entwarnungs-Mail aus dem echten Renderer: Exit-Urteil ok."""
    for name, msg in {"rein": _mail([], _notices()), "gemischt": _mail(_warnungen(), _notices())}.items():
        ok, errors = validator.validate_message(msg)
        assert ok, f"{name}: echte Entwarnungs-Mail abgelehnt: {errors}"


@pytest.mark.parametrize("dto", ["rein", "gemischt"])
def test_e3_uebergang_ohne_absenkung_wird_abgelehnt(validator, dto):
    """E-3: 'Stufe 2 → 4' ist keine Entwarnung (alt muss > neu sein)."""
    warnungen = [] if dto == "rein" else _warnungen()
    msg = _mail(warnungen, _notices(), verfaelschen=lambda t: t.replace("Stufe 4 → 2", "Stufe 2 → 4"))
    ok, errors = validator.validate_message(msg)
    assert not ok and any(e.startswith("E-3") for e in errors), errors


def test_e2_betreff_ohne_entwarnung_wird_abgelehnt(validator):
    msg = _mail([], _notices(), betreff="[Hoehenweg] Segment 1 · Hinweis")
    ok, errors = validator.validate_message(msg)
    assert not ok and any(e.startswith("E-2") for e in errors), errors


def test_e4_handlungsempfehlung_wird_abgelehnt(validator):
    for zusatz in (", du kannst los", ", jetzt wieder sicher"):
        msg = _mail([], _notices(),
                    verfaelschen=lambda t, z=zusatz: t.replace("Stufe 3 → beendet", f"Stufe 3 → beendet{z}"))
        ok, errors = validator.validate_message(msg)
        assert not ok and any(e.startswith("E-4") for e in errors), (zusatz, errors)


def test_e4_sicher_nur_als_ganzes_wort(validator):
    """E-4 darf Daten nicht falsch-positiv ablehnen: 'Sicherheitsbereich' bzw.
    'unsicher' sind keine Handlungsempfehlung -- nur das ganze Wort 'sicher'."""
    msg = _mail([], _notices(region="Sicherheitsbereich Ost"),
                verfaelschen=lambda t: t.replace("Stufe 3 → beendet", "Stufe 3 → beendet (Lage unsicher)"))
    ok, errors = validator.validate_message(msg)
    assert ok, f"Falsch-positiv: {errors}"
