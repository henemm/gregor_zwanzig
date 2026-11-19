"""Orts-Vergleich: die Vorlage ersetzt das Profil (Issue #2796 S4a, ADR-0108 P3).

SPEC: docs/specs/modules/feat_2796_s4a_orte_vorlage_statt_profil.md (AC-4..AC-9)

Kern-Schicht, deterministisch: echter Versandweg ``send_one_compare_preset``
und echte Vorschau ``ComparePreviewService``; ersetzt sind nur die Raender
(Vergleichs-Engine als echte Subklasse, die das uebergebene Bewertungsprofil
mitschreibt; Delta-Anker ohne Netz; Zustellung ueber ``mail_sink``). Geprueft
wird dort, wo es WIRKT: das Profil, mit dem die Engine bewertet, und der
sichtbare Text der gerenderten Mail. Kein Mock()/patch().
"""
from __future__ import annotations

import html as _html
import json
import re
import uuid
from datetime import date, datetime

import pytest
from bs4 import BeautifulSoup

from app.config import Settings
from app.models import ForecastDataPoint, ThunderLevel
from app.profile import ActivityProfile
from app.user import ComparisonResult, LocationResult, SavedLocation
from i18n import t, tn
from tests.helpers.compare_briefings import write_compare_briefings

TAG = date(2026, 7, 8)
ORTE = (
    SavedLocation(id="loc-a", name="Innsbruck", lat=47.27, lon=11.39, elevation_m=574),
    SavedLocation(id="loc-b", name="Stubai", lat=47.10, lon=11.30, elevation_m=1000),
)


# --------------------------------------------------------------------- Raender


@pytest.fixture
def rig(tmp_path, monkeypatch):
    """Isolierter Daten-Root, Engine-Subklasse mit Profil-Mitschrift."""
    from app import loader as app_loader
    import services.comparison_engine as ce_mod
    import services.scheduler_dispatch_service as sds_mod

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_loader, "_DATA_ROOT", str(tmp_path / "data"))
    profile: list = []

    def _dp(h: int) -> ForecastDataPoint:
        return ForecastDataPoint(
            ts=datetime(2026, 7, 8, h, 0), t2m_c=20.0, wind_chill_c=19.0, wind10m_kmh=10.0,
            gust_kmh=18.0, precip_1h_mm=0.0, cloud_total_pct=30, uv_index=4.0,
            thunder_level=ThunderLevel.NONE, pop_pct=10, visibility_m=9000,
        )

    class MitschreibEngine(ce_mod.ComparisonEngine):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            profile.append(kwargs.get("profile"))
            orte = kwargs.get("locations") or (args[0] if args else [])
            return ComparisonResult(
                locations=[LocationResult(
                    location=loc, score=80, temp_max=20.0, temp_min=10.0, wind_max=10.0,
                    gust_max=18.0, cloud_avg=30, sunny_hours=6, official_alerts=[],
                    hourly_data=[_dp(9), _dp(12)]) for loc in orte],
                time_window=kwargs.get("time_window", (9, 16)),
                target_date=kwargs.get("target_date", TAG),
                created_at=datetime(2026, 7, 8, 4, 0),
            )

    monkeypatch.setattr(ce_mod, "ComparisonEngine", MitschreibEngine)
    monkeypatch.setattr(sds_mod, "_write_compare_alert_snapshots", lambda *a, **k: None)
    return {"profile": profile, "tmp": tmp_path}


def _neuer_nutzer(tmp_path) -> str:
    user_id = f"s4a-{uuid.uuid4().hex[:8]}"
    pfad = tmp_path / "data" / "users" / user_id / "user.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({"tier": "premium"}), encoding="utf-8")
    return user_id


def _preset(user_id: str, *, profil: str | None, vorlage: str | None) -> dict:
    p = {
        "id": f"cp-{user_id}", "name": "Tirol", "user_id": user_id, "kind": "vergleich",
        "location_ids": [o.id for o in ORTE], "schedule": "daily",
        "created_at": "2026-07-01T00:00:00Z", "hourly_enabled": False,
        "outlook_enabled": False,
    }
    if profil is not None:
        p["profil"] = profil
    if vorlage is not None:
        p["display_config"] = {"ampel": {"template": vorlage}}
    return p


def _settings() -> Settings:
    return Settings(smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
                    mail_to="dummy@example.invalid")


def _versand(rig, user_id: str, preset: dict, lang: str = "de") -> str:
    from services.scheduler_dispatch_service import send_one_compare_preset

    mails: list[str] = []
    send_one_compare_preset(
        preset, _settings(), user_id, str(rig["tmp"]), all_locations_cache=list(ORTE),
        target_date=TAG, tage_ab_ortstag=0, on_demand=True, lang=lang,
        mail_sink=lambda subject, body: mails.append(body),
    )
    assert len(mails) == 1, "eine Mail erwartet"
    return mails[0]


def _sichtbar(html: str) -> list[str]:
    s = re.sub(r"<head>.*?</head>", "", html, flags=re.S)
    s = re.sub(r"<[^>]+>", "\n", s)
    return [z.strip() for z in _html.unescape(s).split("\n") if z.strip()]


def _kopfzelle(html: str) -> tuple[str, str]:
    td = BeautifulSoup(html, "html.parser").select_one("table.header-stats-desktop td")
    assert td is not None, "Vorbedingung: Kennzahlen-Kopf"
    divs = td.find_all("div")
    return divs[0].get_text(strip=True), divs[1].get_text(strip=True)


def _mail_nennt_vorlage(html: str, lang: str, name: str, n: int = len(ORTE)) -> None:
    zeilen = _sichtbar(html)
    assert f"{t('vergleich.kopf.titel', lang)} · {name}" in zeilen, zeilen[:6]
    assert _kopfzelle(html) == (t("vergleich.kopf.profil", lang), name)
    assert tn("vergleich.fuss.abo_zeile", n, lang, vorlage=name) in zeilen


# ------------------------------------------------------- profile_for_template


@pytest.mark.parametrize("vorlage,profil", [
    ("wintersport", ActivityProfile.WINTERSPORT), ("skitouren", ActivityProfile.WINTERSPORT),
    ("wandern", ActivityProfile.WANDERN), ("alpen-trekking", ActivityProfile.SUMMER_TREKKING),
    # Nachtrag v1.1 (F1): allgemeine Vorlagen geben KEINE Vorgabe -- das eigene
    # Aktivitaetsprofil des Orts bleibt wirksam (comparison_engine).
    ("allgemein", None), ("radtour", None), ("wassersport", None), ("gibts-nicht", None),
    (None, None),
])
def test_profile_for_template_zuordnung(vorlage, profil):
    from app.ampel import profile_for_template
    assert profile_for_template(vorlage) is profil


def _wirksam(vorgabe, ort_profil):
    """Regel der Engine je Ort: Vorgabe, sonst Ortsprofil, sonst Allgemein
    (``comparison_engine``: ``profile or loc.activity_profile``; ``calculate_score``:
    ``profile or ALLGEMEIN``)."""
    return vorgabe or ort_profil or ActivityProfile.ALLGEMEIN


@pytest.mark.parametrize("alt", ["wintersport", "wandern", "summer_trekking", "allgemein"])
@pytest.mark.parametrize("ort_profil", [None, ActivityProfile.ALLGEMEIN])
def test_ac4_wirksames_profil_gleich_der_bisherigen_zuordnung(alt, ort_profil):
    """AC-4: fuer jedes alte Profil und einen Ort ohne eigenes Profil ist das
    WIRKSAME Bewertungsprofil gleich dem des bisherigen Versands
    (``ActivityProfile(profil)``, der entfernte ``_parse_activity_profile``)."""
    from app.ampel import profile_for_template, template_id_for
    neu = profile_for_template(template_id_for({"profil": alt}))
    assert _wirksam(neu, ort_profil) is _wirksam(ActivityProfile(alt), ort_profil)


# ---------------------------------------------------------------- Versandweg


@pytest.mark.parametrize("lang", ["de", "en"])
def test_ac4_versand_wintersport_nennt_vorlage_und_bewertet_gleich(rig, lang):
    user_id = _neuer_nutzer(rig["tmp"])
    html = _versand(rig, user_id, _preset(user_id, profil="wintersport", vorlage="wintersport"),
                    lang)
    assert rig["profile"] and set(rig["profile"]) == {ActivityProfile.WINTERSPORT}
    _mail_nennt_vorlage(html, lang, t("mail.vorlage.wintersport", lang))
    assert "PISTE" not in html


def test_ac4_texte_konkret_de_und_en(rig):
    user_id = _neuer_nutzer(rig["tmp"])
    preset = _preset(user_id, profil="wintersport", vorlage="wintersport")
    de = _sichtbar(_versand(rig, user_id, preset, "de"))
    en = _sichtbar(_versand(rig, user_id, preset, "en"))
    assert "ORTE · Wintersport" in de and "2 Orte · Vorlage Wintersport" in de  # #3122 B5
    assert "LOCATIONS · Winter sports" in en
    assert "2 locations · Template Winter sports" in en


def test_ac5_gewaehlte_vorlage_schlaegt_altes_profil_im_versand(rig):
    user_id = _neuer_nutzer(rig["tmp"])
    html = _versand(rig, user_id, _preset(user_id, profil="wandern", vorlage="wintersport"))
    assert set(rig["profile"]) == {ActivityProfile.WINTERSPORT}
    _mail_nennt_vorlage(html, "de", "Wintersport")
    assert "WANDERN" not in "\n".join(_sichtbar(html))


def test_ac5_gewaehlte_vorlage_schlaegt_altes_profil_in_der_vorschau(rig):
    from app.loader import get_data_dir, save_location
    from services.compare_preview_service import ComparePreviewService

    user_id = _neuer_nutzer(rig["tmp"])
    for ort in ORTE:
        save_location(ort, user_id=user_id)
    preset = _preset(user_id, profil="wandern", vorlage="wintersport")
    write_compare_briefings(get_data_dir(user_id), [preset])
    payload = ComparePreviewService().render_all_channels(
        preset["id"], user_id=user_id, target_date=TAG.isoformat())
    assert set(rig["profile"]) == {ActivityProfile.WINTERSPORT}
    _mail_nennt_vorlage(payload["email_html"], "de", "Wintersport")


@pytest.mark.parametrize("profil,vorlage,erwartet,name", [
    ("summer_trekking", None, ActivityProfile.SUMMER_TREKKING, "Alpen-Trekking"),
    (None, None, None, "Allgemein"),  # v1.1: keine Vorgabe, Ortsprofil bleibt wirksam
])
def test_ac6_ohne_vorlage_gilt_die_rueckfallkette(rig, profil, vorlage, erwartet, name):
    user_id = _neuer_nutzer(rig["tmp"])
    html = _versand(rig, user_id, _preset(user_id, profil=profil, vorlage=vorlage))
    assert set(rig["profile"]) == {erwartet}
    _mail_nennt_vorlage(html, "de", name)


def _html_teil(roh: str) -> str:
    import email as _email
    for teil in _email.message_from_string(roh).walk():
        if teil.get_content_type() == "text/html":
            return teil.get_payload(decode=True).decode(teil.get_content_charset() or "utf-8")
    raise AssertionError("Mail ohne HTML-Teil")


def _betrieb(kanal):
    """Rig-Settings wie im Produktivbetrieb (kein Staging-/Testpostfach-Umweg),
    damit die Empfaenger-Aufloesung je Nutzer greift."""
    return kanal.settings().model_copy(update={"env": "production"})


def test_ac8_zwei_nutzer_je_eigene_vorlage_eigene_empfaenger_daten_unveraendert(rig, monkeypatch):
    """AC-8: zwei Nutzer, je eigener Vergleich mit anderer Vorlage. Jede Mail
    traegt den Vorlagennamen IHRES Vergleichs und geht NUR an die in
    ``user.json`` dieses Nutzers konfigurierte Adresse (echte Aufloesung
    ``Settings.with_user_profile``; Empfaengerliste des Versands, zugestellt
    ueber die SMTP-Gegenstelle der Rig);
    Preset-Dateien und ``user.json`` bleiben byte-gleich."""
    from app.loader import compare_preset_to_dict, get_data_dir, load_compare_presets
    from services.scheduler_dispatch_service import send_one_compare_preset
    from tests.helpers.kanal_fake_transporte import KanalRig

    kanal = KanalRig(monkeypatch)
    nutzer = {}
    for profil, vorlage, name in (("wandern", "skitouren", "Skitouren"),
                                  ("wintersport", "alpen-trekking", "Alpen-Trekking")):
        uid = _neuer_nutzer(rig["tmp"])
        adresse = f"{uid}@empfaenger.invalid"
        profil_datei = get_data_dir(uid) / "user.json"
        profil_datei.write_text(json.dumps({"tier": "premium", "mail_to": adresse}), encoding="utf-8")
        d = write_compare_briefings(get_data_dir(uid), [_preset(uid, profil=profil, vorlage=vorlage)])
        vorher = {p.name: p.read_bytes() for p in d.glob("*.json")}
        vorher["user.json"] = profil_datei.read_bytes()
        nutzer[uid] = {"adresse": adresse, "name": name, "vorher": vorher}
    for uid, n in nutzer.items():
        kanal.zaehler_leeren()
        geladen = load_compare_presets(user_id=uid, data_root=str(rig["tmp"] / "data"))
        _, empfaenger = send_one_compare_preset(
            compare_preset_to_dict(geladen[0]), _betrieb(kanal).with_user_profile(uid), uid,
            str(rig["tmp"]), all_locations_cache=list(ORTE), target_date=TAG,
            tage_ab_ortstag=0, on_demand=True, lang="de",
        )
        # Empfaengerliste, die der Versand an ``EmailOutput.send(to=...)`` gibt.
        # Die SMTP-Gegenstelle sieht im Testlauf immer das Testpostfach
        # (Herkunftssperre #1476) -- dort ist der Nutzer nicht unterscheidbar.
        assert empfaenger == [n["adresse"]], f"{uid}: Empfaenger {empfaenger}"
        mails = kanal.angenommen["email"]
        assert len(mails) == 1, f"{uid}: genau eine Mail erwartet, waren {len(mails)}"
        html = _html_teil(mails[0]["roh"])
        _mail_nennt_vorlage(html, "de", n["name"])
        andere = next(m["name"] for u, m in nutzer.items() if u != uid)
        assert andere not in "\n".join(_sichtbar(html))
    for uid, n in nutzer.items():
        d = get_data_dir(uid)
        jetzt = {p.name: p.read_bytes() for p in (d / "briefings").glob("*.json")}
        jetzt["user.json"] = (d / "user.json").read_bytes()
        assert jetzt == n["vorher"]


# ------------------------------------------------- v1.1: Ortsprofil bleibt wirksam


@pytest.fixture
def echte_engine(tmp_path, monkeypatch):
    """ECHTE ComparisonEngine mit aufgezeichnetem Wetter (offline
    ``FixtureProvider``, ``GZ_TEST_FIXTURE_DIR``). Mitgeschrieben wird das
    Profil, mit dem ``calculate_score`` je Ort WIRKLICH bewertet -- die echte
    Funktion wird aufgerufen, ihr Ergebnis unveraendert zurueckgegeben."""
    from pathlib import Path

    from app import loader as app_loader
    import services.comparison_engine as ce_mod
    import services.scheduler_dispatch_service as sds_mod
    from services.weather_cache import reset_shared_weather_cache_for_tests

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_loader, "_DATA_ROOT", str(tmp_path / "data"))
    fixtures = Path(__file__).resolve().parents[2] / "fixtures" / "openmeteo"
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(fixtures))
    reset_shared_weather_cache_for_tests()
    monkeypatch.setattr(sds_mod, "_write_compare_alert_snapshots", lambda *a, **k: None)
    gesehen: list = []
    echt = ce_mod.calculate_score

    def mitschreiben(metrics, profile=None, window_hours=None):
        # Nur die Rang-Bewertung je Ort (``run``, mit Fensterlaenge) -- der
        # Einzelabruf ``fetch_forecast_for_location`` bewertet ohne Fenster.
        if window_hours is not None:
            gesehen.append(profile)
        return echt(metrics, profile=profile, window_hours=window_hours)

    monkeypatch.setattr(ce_mod, "calculate_score", mitschreiben)
    return {"tmp": tmp_path, "profile": gesehen}


@pytest.mark.parametrize("vorlage", [None, "allgemein"])
def test_v11_allgemeine_vorlage_laesst_das_ortsprofil_wirken(echte_engine, vorlage):
    """Nachtrag v1.1 (F1) / AC-6: ohne Vorlage (und ohne ``profil``) bzw. mit
    Vorlage „allgemein" gibt der Versand KEINE Vorgabe -- der Ort mit eigenem
    Profil WANDERN wird nach WANDERN bewertet, der Ort ohne eigenes Profil
    nach ALLGEMEIN. Die Mail nennt die Vorlage „Allgemein"."""
    from datetime import date as _date

    from freezegun import freeze_time

    from services.scheduler_dispatch_service import send_one_compare_preset

    user_id = _neuer_nutzer(echte_engine["tmp"])
    orte = [
        SavedLocation(id="loc-w", name="Innsbruck", lat=47.2692, lon=11.4041, elevation_m=574,
                      activity_profile=ActivityProfile.WANDERN),
        SavedLocation(id="loc-a", name="Stubai", lat=47.1015, lon=11.2958, elevation_m=1000),
    ]
    preset = _preset(user_id, profil=None, vorlage=vorlage)
    preset.update(location_ids=[o.id for o in orte], official_alerts_enabled=False)
    mails: list[str] = []
    with freeze_time("2026-10-29T04:00:00+00:00"):
        send_one_compare_preset(
            preset, _settings(), user_id, str(echte_engine["tmp"]), all_locations_cache=orte,
            target_date=_date(2026, 10, 29), tage_ab_ortstag=0, on_demand=True, lang="de",
            mail_sink=lambda subject, body: mails.append(body),
        )
    assert sorted(p.value for p in echte_engine["profile"]) == ["allgemein", "wandern"], (
        echte_engine["profile"])
    assert len(mails) == 1
    _mail_nennt_vorlage(mails[0], "de", "Allgemein")


# ------------------------------------------------------------------- Katalog


def test_ac9_katalog_vorlage_template_und_gleiche_platzhalter():
    assert t("vergleich.kopf.profil", "de") == "Vorlage"
    assert t("vergleich.kopf.profil", "en") == "Template"
    assert tn("vergleich.fuss.abo_zeile", 3, "de", vorlage="X") == "3 Orte · Vorlage X"
    assert tn("vergleich.fuss.abo_zeile", 3, "en", vorlage="X") == "3 locations · Template X"
    # #3122 B5 (AC-36): bei genau einem Ort die Einzahl.
    assert tn("vergleich.fuss.abo_zeile", 1, "de", vorlage="X") == "1 Ort · Vorlage X"
    assert tn("vergleich.fuss.abo_zeile", 1, "en", vorlage="X") == "1 location · Template X"
