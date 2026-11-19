"""#3047 Runde 7, Paket p6 (Orte-Kanaele): Befunde B-L2, B-L3, B-L4.

SPEC: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md,
"Nachtrag Runde 7" (AC-22, AC-23, AC-24, Tech-Lead-Entscheidung "Grundauswahl
nie eingestellt: Orte = was die Mail zeigt"); ADR-0095 (Kanal-Paritaet),
ADR-0097 (ein Code Trip/Orte), Konzept docs/context/einstellungen_neu.md §5 P8.

Echter Weg: rohes Preset-JSON im Nutzerordner -> ``load_compare_presets`` ->
``send_one_compare_preset`` -> ``NotificationService`` -> Transport-Mitschrift.
Einzige Naehte: Wetter (``ComparisonEngine.run``, echte Subklasse) und
Transport. Jeder Fall mit zwei frischen Nutzern; Erwartungen von Hand.
"""
from __future__ import annotations

import copy
import dataclasses
import json
import re
from datetime import datetime

import pytest

from app.loader import get_data_dir
from tests.helpers.transport_mitschrift import aufzeichner_installieren
from tests.tdd._compare_kette_fixtures import (
    TARGET_DATE, _WERTE, _dp, briefing_senden, fixture_dict, nutzer_anlegen,
    orte_anlegen, preset_ablegen, settings_fuer, transport_einrichten,
)

#: Warndienst-Ausfall je Test (``official_alerts_unavailable`` am Ort).
STATE: dict = {"unavailable": False}

#: Boeen je Stunde (UTC): Spitze 25 km/h um 12 UTC = 14 Uhr Ortszeit (MESZ),
#: Tiefstwert 15 km/h um 9 UTC = 11 Uhr -- Spitzen- und Tiefststunde verschieden.
BOEEN_STUNDEN = ((9, 15.0), (12, 25.0), (15, 19.0))


def _stunden(w: dict) -> list:
    return [dataclasses.replace(_dp(h, w), gust_kmh=g) for h, g in BOEEN_STUNDEN]


def _ergebnis(locations, kwargs):
    from app.models import ThunderLevel
    from app.user import ComparisonResult, LocationResult

    res = []
    for i, loc in enumerate(list(locations)):
        w = _WERTE[loc.id]
        lr = LocationResult(
            location=loc, score=90 - 7 * i, temp_max=w["temp_max"], temp_min=w["temp_min"],
            wind_max=w["wind_max"], gust_max=w["gust_max"], cloud_avg=w["cloud_avg"],
            sunny_hours=w["sunny_hours"], snow_depth_cm=w["snow_depth_cm"],
            snow_new_cm=w["snow_new_cm"], wind_direction_avg=250 + 20 * i,
            precip_sum_mm=3.5 + i, pop_max_pct=40 + 10 * i, uv_index_max=6.0,
            thunder_level_max=ThunderLevel.MED, visibility_min_m=8000,
            official_alerts=[], hourly_data=_stunden(w),
        )
        if STATE["unavailable"]:
            lr.official_alerts_unavailable = True
        res.append(lr)
    return ComparisonResult(locations=res, time_window=kwargs.get("time_window", (9, 16)),
                            target_date=kwargs.get("target_date", TARGET_DATE),
                            created_at=datetime(2026, 7, 8, 4, 0))


@pytest.fixture
def mit(monkeypatch):
    import services.comparison_engine as ce_mod
    import services.scheduler_dispatch_service as sds_mod

    original = ce_mod.ComparisonEngine

    class Engine(original):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            locations = kwargs.get("locations") or (args[0] if args else [])
            return _ergebnis(locations, kwargs)

    transport_einrichten(monkeypatch)
    monkeypatch.setattr(ce_mod, "ComparisonEngine", Engine)
    monkeypatch.setattr(sds_mod, "_write_compare_alert_snapshots", lambda *a, **k: None)
    STATE["unavailable"] = False
    return aufzeichner_installieren(monkeypatch)


#: Grundauswahl, Folge bewusst != Katalogfolge.
GRUND = [("gust", "max"), ("temperature", "max"), ("wind", "max"),
         ("precipitation", "sum"), ("cloud_total", "avg")]


def preset(**top) -> dict:
    p = fixture_dict("basis")
    p["display_config"]["active_metrics"] = [{"metric_id": m, "aggregation": a} for m, a in GRUND]
    p["send_telegram"] = p["send_sms"] = p["send_premium_sms"] = True
    p["alert_channels"] = {"email": True, "telegram": False, "sms": False, "premium_sms": False}
    p.update(top)
    return p


def zwei_nutzer(mit, p, *, lang: str = "de") -> list:
    laeufe = []
    for _ in range(2):
        uid = nutzer_anlegen("premium")
        pf = get_data_dir(uid) / "user.json"
        u = json.loads(pf.read_text())
        u["language"] = lang
        pf.write_text(json.dumps(u))
        orte_anlegen(uid)
        preset_ablegen(uid, copy.deepcopy(p))
        mit.leeren()
        briefing_senden(uid, p["id"], settings_fuer(uid))
        snap = copy.deepcopy(mit)
        mit.leeren()
        for k in ("telegram", "sms", "premium_sms", "email"):
            assert snap.sendungen(k), f"Vorbedingung: keine {k}-Sendung fuer {uid}"
        assert snap.empfaenger("telegram") == [f"chat-{uid}"]
        assert snap.empfaenger("email") == [f"{uid}@example.invalid"]
        laeufe.append((uid, snap))
    assert laeufe[0][0] != laeufe[1][0]
    return laeufe


def text(snap, kanal: str) -> str:
    return snap.sendungen(kanal)[-1]["body"]


def wertezeilen(tg: str, ort: str = "Innsbruck") -> list[list[str]]:
    """Werte-Zeilen (Zellen) eines Ortsblocks im Telegram."""
    zeilen = tg.splitlines()
    i = zeilen.index(ort)
    block = []
    for z in zeilen[i + 1:]:
        if not z.startswith("   "):
            break
        block.append(z.strip())
    return [z.split(" · ") for z in block if " · " in z]


def _sms_ort(sms: str, name: str) -> str:
    """#3172 (PO 2026-11-19): die Orte-SMS nennt keine Namen -- der Ort steht
    als ``O{n}`` an seiner Stelle in ``location_ids`` (``ORTSNAMEN``-Folge)."""
    from tests.helpers.orte_sms import orte_teil
    from tests.tdd._compare_kette_fixtures import ORTSNAMEN

    return orte_teil(sms, ORTSNAMEN.index(name) + 1)


# ---------------------------------------------------------------------------
# B-L4: "nie eingestellt" -> Telegram/SMS/Premium-SMS folgen der Mail-Tabelle
# ---------------------------------------------------------------------------

#: Folge der Vergleichstabelle der Mail bei "nie eingestellt" (alle Zeilen in
#: Register-Folge, CV2), von Hand: Telegram-Beschriftung je Sprache.
MAIL_FOLGE = {
    "de": ["Temp max", "Wind", "Regen", "Regenwahrscheinlichkeit", "Gewitter", "Sonne",
           "Wolken", "UV max", "Sicht min", "Schneehöhe", "Neuschnee", "Temp min", "Böen",
           "Nullgradgrenze", "Windrichtung"],
    "en": ["Temp max", "Wind", "Rain", "Rain probability", "Thunderstorm", "Sun",
           "Clouds", "UV max", "Visibility min", "Snow depth", "Fresh snow", "Temp min",
           "Gusts", "Freezing level", "Wind direction"],
}


def _beschriftung(zelle: str, lang: str) -> str:
    treffer = [b for b in sorted(MAIL_FOLGE[lang], key=len, reverse=True)
               if zelle.startswith(b + " ")]
    return treffer[0] if treffer else zelle


def _nie_eingestellt() -> dict:
    p = preset()
    p["display_config"].pop("active_metrics")
    return p


@pytest.mark.parametrize("lang", ["de", "en"])
def test_bl4_nie_eingestellt_telegram_folgt_mail(mit, lang):
    for uid, snap in zwei_nutzer(mit, _nie_eingestellt(), lang=lang):
        zeilen = wertezeilen(text(snap, "telegram"))
        assert len(zeilen) == 2, f"B-L4: erwartet zwei Wertezeilen (AC-24): {zeilen}"
        erste = [_beschriftung(z, lang) for z in zeilen[0]]
        alle = erste + [_beschriftung(z, lang) for z in zeilen[1]]
        # Zeile 1 = die ersten 7 Zeilen der Mail-Tabelle (alle haben Werte).
        assert erste == MAIL_FOLGE[lang][:7], f"B-L4 Telegram statt Mail-Folge: {erste}"
        # Sicherheitsrelevante Zeilen fehlen nicht mehr, Folge wie die Mail.
        bekannt = [b for b in alle if b in MAIL_FOLGE[lang]]
        assert bekannt == [b for b in MAIL_FOLGE[lang] if b in bekannt], alle
        for pflicht in (MAIL_FOLGE[lang][2], MAIL_FOLGE[lang][4], MAIL_FOLGE[lang][12]):
            assert pflicht in alle, f"B-L4: {pflicht} fehlt: {alle}"
        # Nichts gewaehlt -> kein "ohne Wert"-Zaehler (die Mail zeigt auch keinen).
        assert "ohne Wert" not in text(snap, "telegram"), text(snap, "telegram")
        assert "without data" not in text(snap, "telegram")
        plain = snap.sendungen("email")[-1]["plain_text_body"]
        mail_gewitter = "Gewitter" if lang == "de" else "Thunder"
        assert mail_gewitter in plain, "Vorbedingung: Mail zeigt die Gewitter-Zeile"


def test_bl4_nie_eingestellt_sms_folgt_mail(mit):
    for uid, snap in zwei_nutzer(mit, _nie_eingestellt()):
        sms = text(snap, "sms")
        assert len(sms) <= 160, len(sms)
        ort = _sms_ort(sms, "Innsbruck")
        # #3172 (ADR-0125): Kuerzel der Token-Zeile (``D12/22``, ``R1.5@11``).
        kuerzel = [re.match(r"[A-Z]+", t).group(0) for t in ort.split(" ")[1:]]
        # Mail-Folge: Temp max (D), Wind (W), Regen (R), Regenwahrsch. (PR) ...
        assert kuerzel[:3] == ["D", "W", "R"], f"B-L4 SMS-Festsatz statt Mail-Folge: {ort}"
        assert "SU" not in kuerzel[:3] and "SD" not in kuerzel[:3], ort
        # Kuerzung vom Listenende (AC-23) still wie im Trip: gezeigt wird ein
        # Anfang der Mail-Folge, die hinteren Zeilen fehlen, kein Zaehler +N/?N.
        mail_folge = ["D", "W", "R", "PR", "TH", "SU", "CT", "UV", "VS", "SD", "NS", "G",
                      "FZ", "WD", "FD", "CL", "CM", "CH", "HU", "DP", "HP", "PT", "SL"]
        assert kuerzel == mail_folge[:len(kuerzel)] and len(kuerzel) < len(mail_folge), ort
        assert not re.search(r" [+?]\d", ort), f"Zaehler in der SMS: {ort}"
        assert text(snap, "premium_sms") == sms


# ---------------------------------------------------------------------------
# B-L2: Warndienst nicht erreichbar -> Hinweis in Telegram/SMS/Premium-SMS
# ---------------------------------------------------------------------------

#: Wortlaut des Warndienst-Hinweises (nicht der Ausblick-Zustand "Vorhersage ...").
HINWEIS = {"de": "Amtliche Warnungen aktuell nicht abrufbar",
           "en": "Official warnings are currently unavailable"}


@pytest.mark.parametrize("lang", ["de", "en"])
def test_bl2_warnungen_nicht_abrufbar_telegram(mit, lang):
    STATE["unavailable"] = True
    for uid, snap in zwei_nutzer(mit, preset(), lang=lang):
        tg = text(snap, "telegram")
        assert HINWEIS[lang] in tg, f"B-L2 Telegram ohne Hinweis ({lang}): {tg}"
        assert tg.index(HINWEIS[lang]) < tg.index("Innsbruck"), "Hinweis gehoert vor die Orte"
        assert "nicht abrufbar" in snap.sendungen("email")[-1]["body"] or lang == "en", \
            "Vorbedingung: HTML-Mail zeigt den Hinweis"


def test_bl2_warnungen_nicht_abrufbar_sms(mit):
    STATE["unavailable"] = True
    for uid, snap in zwei_nutzer(mit, preset()):
        sms = text(snap, "sms")
        assert re.search(r"(^| )X\?( |$)", sms), f"B-L2 SMS ohne X?: {sms}"
        assert len(sms) <= 160, len(sms)
        assert text(snap, "premium_sms") == sms


def test_bl2_marker_faellt_nie_weg_und_haelt_budget(mit):
    """Volle SMS (nie eingestellt = alle Mail-Zeilen) und Warndienst-Ausfall:
    ``X?`` steht am Ende, die Zellen weichen ihm, das SMS-Budget haelt
    (#3172: 160 wie die Trip-SMS)."""
    from output.renderers.channel_layout import CHANNEL_LIMITS
    from output.renderers.comparison import ORTE_SMS_MAX_ZEICHEN

    STATE["unavailable"] = True
    for uid, snap in zwei_nutzer(mit, _nie_eingestellt()):
        sms = text(snap, "sms")
        assert sms.endswith(" X?"), sms
        assert len(sms) <= ORTE_SMS_MAX_ZEICHEN, (len(sms), sms)
        # #3172: die Premium-SMS kuerzt ueber 153 Zeichen neu -- der Marker bleibt.
        premium = text(snap, "premium_sms")
        assert premium.endswith(" X?") and len(premium) <= CHANNEL_LIMITS["premium_sms"]["max_chars"]


def test_bl2_gegenprobe_ohne_ausfall_kein_hinweis(mit):
    for uid, snap in zwei_nutzer(mit, preset()):
        assert "X?" not in text(snap, "sms")
        assert HINWEIS["de"] not in text(snap, "telegram")


# ---------------------------------------------------------------------------
# B-L3: Einfach bei Ampel-Groessen folgt den Ampel-Grenzen (Form wie Trip)
# ---------------------------------------------------------------------------

def _ampel_preset(gelb: int, orange: int, rot: int, *, ausblick: bool = True) -> dict:
    p = preset(outlook_enabled=ausblick)
    p["display_config"]["channel_layouts"] = {"telegram": [
        {"metric_id": "temperature", "enabled": True},
        {"metric_id": "gust", "enabled": True, "use_friendly_format": True},
    ]}
    p["display_config"]["ampel"] = {"template": "allgemein", "metrics": {
        "gust": {"upper": {"yellow": gelb, "orange": orange, "red": rot}}}}
    return p


def _boeen_zelle(tg: str) -> str:
    zellen = [z for zeile in wertezeilen(tg) for z in zeile]
    treffer = [z for z in zellen if z.startswith("Böen ")]
    assert treffer, f"Vorbedingung: Böen-Zelle fehlt: {zellen}"
    return treffer[0]


@pytest.mark.parametrize("ausblick", [True, False])
def test_bl3_einfach_folgt_ampel_grenzen(mit, ausblick):
    """Die Ampel wirkt unabhaengig vom Ausblick-Schalter."""
    niedrig = [_boeen_zelle(text(s, "telegram"))
               for _, s in zwei_nutzer(mit, _ampel_preset(5, 10, 15, ausblick=ausblick))]
    hoch = [_boeen_zelle(text(s, "telegram"))
            for _, s in zwei_nutzer(mit, _ampel_preset(100, 110, 120, ausblick=ausblick))]
    # Tageswert Boeen 19 km/h (Innsbruck): bei 5/10/15 rot -> Marke der
    # Spitzenstunde wie im Trip-Telegram (``@h``): 25 km/h um 12 UTC = 14 Uhr
    # Ortszeit; bei 100/110/120 gruen -> keine Marke.
    for zelle in niedrig:
        assert zelle.endswith("@14"), f"B-L3: Ampel-Grenzen ohne Wirkung: {zelle}"
    for zelle in hoch:
        assert "@" not in zelle, zelle
    assert niedrig[0] != hoch[0]


def test_bl2_marker_budget_bei_jeder_namenslaenge():
    """Reine Renderer-Pruefung (kein Netz): ueber viele Ortszahlen liegt die
    Nachricht ohne Marker irgendwann knapp am Budget -- ``X?`` darf es auch
    dann nicht sprengen (das Budget des Kerns ist um den Marker verkleinert).
    #3172: die Orte-SMS nennt keine Namen mehr, die Laenge waechst ueber die
    Zahl der Orte (``O1 D20 W? G? O2 ...``); Grenze 160 wie die Trip-SMS."""
    from app.user import ComparisonResult, LocationResult, SavedLocation
    from output.renderers.comparison import ORTE_SMS_MAX_ZEICHEN, render_compare_sms

    grenze = ORTE_SMS_MAX_ZEICHEN
    knapp = 0
    for n in range(1, 40):
        orte = [LocationResult(
            location=SavedLocation(id=f"o{i}", name=f"Ort{i}",
                                   lat=47.27, lon=11.39, elevation_m=1000),
            score=50, temp_max=20.0, wind_max=10.0, gust_max=30.0, cloud_avg=40,
        ) for i in range(n)]
        ergebnis = ComparisonResult(locations=orte, time_window=(9, 16), target_date=TARGET_DATE,
                                    created_at=datetime(2026, 7, 8, 4, 0))
        ohne = render_compare_sms(ergebnis, enabled_metrics=["temp_max", "wind_max", "gust_max"])
        for lr in orte:
            lr.official_alerts_unavailable = True
        mit_marker = render_compare_sms(ergebnis, enabled_metrics=["temp_max", "wind_max", "gust_max"])
        assert mit_marker.endswith(" X?"), mit_marker
        assert len(mit_marker) <= grenze, (n, len(mit_marker), mit_marker)
        knapp += len(ohne) > grenze - 3
    assert knapp > 0, "Vorbedingung: kein Fall lag ohne Marker knapp am Budget"
