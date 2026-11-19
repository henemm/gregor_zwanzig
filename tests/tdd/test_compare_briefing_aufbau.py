"""TDD RED — Issue #2983: gemeinsamer Berichtsaufbau des Ortsvergleichs.

SPEC: docs/specs/modules/compare_briefing_aufbau.md (AC-1 bis AC-9)

Vorschau (``ComparePreviewService.render_all_channels``) und Versand
(``send_one_compare_preset``) setzen den Bericht heute an zwei Stellen
zusammen. Kuenftig baut ihn EIN Baustein ``services.compare_briefing_aufbau``.

Vertrag, den diese Tests an den Baustein stellen (aus der Spec):

* ``compare_wetter_laden(preset, locations, zieltag, user_id)``
* ``compare_email_rendern(kontext, *, lang, undelivered=None)`` -> (html, text)
* ``compare_kanaltexte_rendern(kontext, *, lang)`` -> SMS- und Telegram-Text
* ``compare_briefing_bauen(preset, locations, zieltag, user_id, *, lang,
  undelivered=None)`` -> dict/Objekt mit ``subject``, ``email_html``,
  ``email_text``, ``telegram``, ``sms``
* ``compare_zieltag_bestimmen(locations, jetzt_utc, *, context_label)`` -> date
* ``order_locations_by_ids``, ``build_compare_preset_subject`` (hierher verschoben,
  in den Alt-Modulen als Re-Export unter demselben Namen)

Versand und Vorschau loesen die Baustein-Funktionen ZUR LAUFZEIT ueber das
Modul auf (funktionslokaler Import wie heute ueblich, oder Modul-Attribut).
Nur so ist AC-5 ("eine Aenderung am Baustein ist in Vorschau UND Versand
sichtbar") am Wirkort beobachtbar.

Golden-Tests (AC-1): Die Soll-Werte unter ``tests/golden/compare_briefing_aufbau/``
wurden mit dem Code VOR dem Umbau erzeugt (``_golden_erzeugen`` unten, einmalig
in Phase 5). Sie sind vor UND nach dem Umbau gruen.

KEINE Mocks (kein Mock()/patch()/MagicMock). Naehte wie im Haus-Muster
``tests/tdd/test_compare_dispatch_channel_fanout.py``: ``ComparisonEngine.run``
(echte Subklasse, Live-Wetter ist in der Kern-Schicht verboten), der
Δ-Anker-Schreiber ``_write_compare_alert_snapshots`` (holt Nowcast-Wetter) und
die Transport-Sinks des NotificationService. Renderer bleiben echt.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.config import Settings
from app.models import ForecastDataPoint, ThunderLevel
from app.user import SavedLocation

TARGET_DATE = date(2026, 7, 8)
GOLDEN_DIR = Path(__file__).resolve().parents[1] / "golden" / "compare_briefing_aufbau"
REPO_ROOT = Path(__file__).resolve().parents[2]

# Nutzer A (Golden-Nutzer) und Nutzer B mit eigenen, unverwechselbaren Orten.
ORTE_A = [
    ("loc-ibk", "Innsbruck", 47.27, 11.39),
    ("loc-bz", "Bozen", 46.50, 11.35),
]
ORTE_B = [
    ("loc-chx", "Chamonix", 45.92, 6.87),
    ("loc-zrm", "Zermatt", 46.02, 7.75),
]
NUTZER_A = "aufbau-nutzer-a"
NUTZER_B = "aufbau-nutzer-b"


# ---------------------------------------------------------------------------
# Umgebung
# ---------------------------------------------------------------------------


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolierter Daten-Root ueber BEIDE Zugriffsformen (``_DATA_ROOT`` und
    relative ``data``-Pfade), zwei Premium-Nutzer mit je eigenen Orten und
    eigenem Preset, Engine- und Snapshot-Naht installiert."""
    from app import loader as app_loader

    data_root = tmp_path / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_loader, "_DATA_ROOT", str(data_root))
    try:
        from src.app import loader as src_loader

        monkeypatch.setattr(src_loader, "_DATA_ROOT", str(data_root))
    except ImportError:  # pragma: no cover
        pass

    for uid, orte in ((NUTZER_A, ORTE_A), (NUTZER_B, ORTE_B)):
        user_json = data_root / "users" / uid / "user.json"
        user_json.parent.mkdir(parents=True, exist_ok=True)
        user_json.write_text(json.dumps({"tier": "premium"}), encoding="utf-8")
        _orte_anlegen(uid, orte)

    calls = _EngineCalls()
    _engine_naht(monkeypatch, calls)
    return {"data_root": data_root, "calls": calls}


def _orte_anlegen(uid: str, orte) -> None:
    from app.loader import save_location

    for lid, name, lat, lon in orte:
        save_location(
            SavedLocation(id=lid, name=name, lat=lat, lon=lon, elevation_m=1000),
            user_id=uid,
        )


def _preset_ablegen(uid: str, preset_id: str, location_ids: list[str], *,
                    telegram_style: str | None = None, name: str = "Urlaubsorte",
                    extra: dict | None = None) -> dict:
    """Preset ueber den Test-Helfer ins Nutzerverzeichnis schreiben und ueber den
    ECHTEN Loader zurueckholen -- Vorschau und Versand sehen damit dasselbe Dict."""
    from app.loader import compare_preset_to_dict, get_data_dir, load_compare_presets
    from tests.helpers.compare_briefings import write_compare_briefings

    preset = {
        "id": preset_id,
        "name": name,
        "user_id": uid,
        "location_ids": location_ids,
        "schedule": "daily",
        "profil": "ALLGEMEIN",
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-07-01T00:00:00Z",
        "send_telegram": True,
        "send_sms": True,
    }
    if telegram_style:
        preset["display_config"] = {"telegram_style": telegram_style}
    preset.update(extra or {})
    write_compare_briefings(get_data_dir(uid), [preset])
    treffer = [p for p in load_compare_presets(uid) if p.id == preset_id]
    assert len(treffer) == 1, f"Vorbedingung: Preset {preset_id!r} fuer {uid!r} nicht ladbar"
    return compare_preset_to_dict(treffer[0])


def _orte(uid: str) -> list:
    from app.loader import load_all_locations

    return load_all_locations(user_id=uid)


def _settings() -> Settings:
    """Alle Kanaele sendefaehig; die Sinks ersetzen den Transport vollstaendig
    (Muster test_compare_dispatch_channel_fanout.py)."""
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.invalid",
        telegram_bot_token="dummy-token", telegram_chat_id="123456",
        sms_gateway_url="https://sms.invalid", seven_api_key="k",
        sms_to="+491700000000",
    )


# ---------------------------------------------------------------------------
# Naehte
# ---------------------------------------------------------------------------


def _dp(hour: int, temp: float) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(TARGET_DATE.year, TARGET_DATE.month, TARGET_DATE.day, hour, 0),
        t2m_c=temp, wind_chill_c=temp - 1, wind10m_kmh=11.0, gust_kmh=19.0,
        precip_1h_mm=0.0, cloud_total_pct=35, uv_index=5.0,
        thunder_level=ThunderLevel.NONE, pop_pct=10, visibility_m=9000,
    )


#: feste Tageswerte je Orts-Kennung (je Ort ein eigener Lauf, ein Index waere immer 0)
_WERTE = {
    "loc-ibk": (22.0, 12.0, 90), "loc-bz": (27.0, 15.0, 83),
    "loc-chx": (18.0, 8.0, 75), "loc-zrm": (16.0, 6.0, 70),
}


def _vertretungs_meta():
    """Herkunft mit Modell-Vertretung (Muster test_compare_vertretungshinweis_aufrufer)."""
    from app.models import ForecastMeta, Provider

    return ForecastMeta(
        provider=Provider.OPENMETEO, model="icon_d2", grid_res_km=2.2,
        run=datetime(2026, 7, 8, 0, 0, tzinfo=timezone.utc),
        fallback_model="icon_eu", fallback_metrics=["temperature_2m"],
        fallback_reason="metric_gap",
    )


class _EngineCalls:
    def __init__(self) -> None:
        self.kwargs_seen: list[dict] = []
        self.alle_fehler = False
        #: Orts-Kennungen, deren Lauf eine Modell-Vertretung meldet (#1563)
        self.vertretung_bei: set[str] = set()
        self.lock = threading.Lock()


def _engine_naht(monkeypatch, calls: _EngineCalls) -> None:
    import services.comparison_engine as ce_mod
    import services.scheduler_dispatch_service as sds_mod
    from app.user import ComparisonResult, LocationResult

    original = ce_mod.ComparisonEngine

    class RecordingEngine(original):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            locations = kwargs.get("locations")
            if locations is None and args:
                locations = args[0]
            with calls.lock:
                calls.kwargs_seen.append(dict(kwargs))
            ergebnisse = []
            for loc in list(locations or []):
                tmax, tmin, score = _WERTE[loc.id]
                if calls.alle_fehler:
                    ergebnisse.append(LocationResult(location=loc, error="provider down"))
                    continue
                ergebnisse.append(LocationResult(
                    location=loc, score=score, temp_max=tmax, temp_min=tmin,
                    wind_max=11.0, gust_max=19.0, cloud_avg=35, sunny_hours=6,
                    official_alerts=[],
                    hourly_data=[_dp(9, tmin), _dp(12, tmax), _dp(15, tmax - 1)],
                    forecast_meta=_vertretungs_meta() if loc.id in calls.vertretung_bei else None,
                ))
            return ComparisonResult(
                locations=ergebnisse,
                time_window=kwargs.get("time_window", (9, 16)),
                target_date=kwargs.get("target_date", TARGET_DATE),
                created_at=datetime(2026, 7, 8, 4, 0),
            )

    monkeypatch.setattr(ce_mod, "ComparisonEngine", RecordingEngine)
    monkeypatch.setattr(sds_mod, "_write_compare_alert_snapshots", lambda *a, **k: None)


class _Sink:
    """Echte Aufzeichnungs-Naht (kein Mock)."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, *args, **kwargs) -> None:
        self.calls.append({"args": args, "kwargs": kwargs})


def _versand(uid: str, preset: dict, *, target_date: date | None = TARGET_DATE) -> dict:
    """Echter Versand ueber ``send_one_compare_preset`` mit Sinks; liefert die
    zugestellten Inhalte je Kanal."""
    from services.scheduler_dispatch_service import send_one_compare_preset

    mail, sms, telegram = _Sink(), _Sink(), _Sink()
    extra = {"target_date": target_date, "tage_ab_ortstag": 0} if target_date else {}
    send_one_compare_preset(
        preset, _settings(), uid, "data",
        all_locations_cache=_orte(uid),
        mail_sink=mail, sms_sink=sms, telegram_sink=telegram,
        on_demand=True,
        **extra,
    )
    assert len(mail.calls) == 1, f"genau eine Mail erwartet, waren {len(mail.calls)}"
    assert len(sms.calls) == 1, f"genau eine SMS erwartet, waren {len(sms.calls)}"
    assert len(telegram.calls) == 1, f"genau ein Telegram erwartet, waren {len(telegram.calls)}"
    m = mail.calls[0]["kwargs"]
    return {
        "subject": m["subject"],
        "email_html": m["body"],
        "email_text": m.get("plain_body"),
        "sms": sms.calls[0]["args"][0],
        "telegram": telegram.calls[0]["args"][0],
    }


def _vorschau(uid: str, preset_id: str, target_date=TARGET_DATE) -> dict:
    from services.compare_preview_service import ComparePreviewService

    return ComparePreviewService().render_all_channels(
        preset_id, user_id=uid,
        target_date=target_date.isoformat() if target_date else None,
    )


def _feld(payload, name: str):
    if isinstance(payload, dict):
        assert name in payload, f"Feld {name!r} fehlt: {sorted(payload)}"
        return payload[name]
    assert hasattr(payload, name), f"Feld {name!r} fehlt an {payload!r}"
    return getattr(payload, name)


# ---------------------------------------------------------------------------
# Golden-Werte (einmalig mit dem Code VOR dem Umbau erzeugt)
# ---------------------------------------------------------------------------

_KANAELE = ("subject", "email_html", "email_text", "sms", "telegram")


def _golden_pfad(stil: str, kanal: str) -> Path:
    endung = {"email_html": "html"}.get(kanal, "txt")
    return GOLDEN_DIR / f"versand_{stil}.{kanal}.{endung}"


#: Laufzeit-Zeitpunkte ("Erstellt: <jetzt>", Fuss "Naechster Versand") haengen an der
#: Uhr, nicht am Aufbau -- sie werden auf beiden Seiten durch eine Marke ersetzt.
#: Die Zonen-Abkuerzung (CET/CEST) gehoert dazu (Sommerzeit). Der Zieltag
#: (08.07.2026, ohne Uhrzeit) bleibt unberuehrt.
_ZEITPUNKT = re.compile(r"\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}(?: \(?[A-Z]{2,5}\)?)?|\d{2}:\d{2} \([A-Z]{2,5}\)")


def _ohne_uhr(text: str) -> str:
    return _ZEITPUNKT.sub("<ZEITPUNKT>", text)


def _golden_erzeugen(stil: str, ist: dict) -> None:  # pragma: no cover - nur Phase 5
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for kanal in _KANAELE:
        _golden_pfad(stil, kanal).write_text(_ohne_uhr(ist[kanal]), encoding="utf-8")


@pytest.mark.parametrize("stil", ["langform", "kurzform"])
def test_ac1_versand_bleibt_byte_gleich(env, stil):
    """AC-1: Given ein Ortsvergleich mit festen Orten und gleichen Wetterdaten /
    When der Versand laeuft / Then sind Betreff, E-Mail (HTML und Text), SMS und
    Telegram byte-gleich zu den vor dem Umbau erfassten Werten (beide
    Telegram-Stile).

    Characterization: VOR dem Umbau gruen, nach dem Umbau unveraendert gruen."""
    preset = _preset_ablegen(
        NUTZER_A, "cp-aufbau-golden", ["loc-ibk", "loc-bz"],
        telegram_style="kurzform" if stil == "kurzform" else None,
    )
    ist = _versand(NUTZER_A, preset)
    if os.environ.get("GZ_GOLDEN_ERZEUGEN") == "2983":  # pragma: no cover
        _golden_erzeugen(stil, ist)
    for kanal in _KANAELE:
        soll = _golden_pfad(stil, kanal).read_text(encoding="utf-8")
        assert _ohne_uhr(ist[kanal]).encode("utf-8") == soll.encode("utf-8"), (
            f"AC-1: Versand-{kanal} ({stil}) weicht vom Stand vor dem Umbau ab"
        )


# ---------------------------------------------------------------------------
# AC-2 / AC-3: Vorschau = Versand
# ---------------------------------------------------------------------------


def test_ac2_vorschau_telegram_kurzform_ist_der_sms_text(env):
    """AC-2: Given ein Ortsvergleich mit Telegram-Stil Kurzform / When die
    Vorschau erzeugt wird / Then zeigt die Telegram-Vorschau denselben Kurztext
    wie die SMS und wie die zugestellte Telegram-Nachricht.

    RED: die Vorschau rendert Telegram heute immer in Langform
    (compare_preview_service.render_all_channels)."""
    preset = _preset_ablegen(NUTZER_A, "cp-aufbau-kurz", ["loc-ibk", "loc-bz"],
                             telegram_style="kurzform")
    vorschau = _vorschau(NUTZER_A, "cp-aufbau-kurz")
    versand = _versand(NUTZER_A, preset)

    assert versand["telegram"] == versand["sms"], "Vorbedingung: Versand-Kurzform = SMS"
    assert vorschau["telegram"] == vorschau["sms"], (
        "AC-2: Telegram-Vorschau im Kurzform-Stil muss der SMS-Text sein, war: "
        f"{vorschau['telegram'][:200]!r}"
    )
    assert vorschau["telegram"] == versand["telegram"], (
        "AC-2: Telegram-Vorschau muss der zugestellten Telegram-Nachricht gleichen"
    )


def test_ac3_vorschau_gleich_versand_langform(env):
    """AC-3: Given Telegram-Stil Langform / When Vorschau und Versand laufen /
    Then sind Telegram (inkl. Ausblick, Vertretungshinweis), SMS, Betreff und
    Mail-HTML identisch (frischer Nutzer: kein ``undelivered``-Block).
    Regressionswaechter, vor und nach dem Umbau gruen."""
    preset = _preset_ablegen(NUTZER_A, "cp-aufbau-lang", ["loc-ibk", "loc-bz"])
    vorschau = _vorschau(NUTZER_A, "cp-aufbau-lang")
    versand = _versand(NUTZER_A, preset)

    for kanal in ("telegram", "sms", "subject", "email_html"):
        assert vorschau[kanal] == versand[kanal], f"AC-3: Vorschau-{kanal} != Versand-{kanal}"


# ---------------------------------------------------------------------------
# AC-4: Mandantentrennung
# ---------------------------------------------------------------------------


def test_ac4_vorschau_und_versand_nur_mit_daten_des_nutzers(env):
    """AC-4 (Huellen): Given zwei Nutzer mit je eigenem Ortsvergleich / When
    Vorschau und Versand fuer Nutzer A laufen / Then erscheinen nur A-Orte, der
    Wetterabruf laeuft mit A als Nutzer (nie "default"), und B's Preset ist fuer
    A nicht erreichbar (LookupError)."""
    preset_a = _preset_ablegen(NUTZER_A, "cp-aufbau-a", ["loc-ibk", "loc-bz"])
    _preset_ablegen(NUTZER_B, "cp-aufbau-b", ["loc-chx", "loc-zrm"], name="Westalpen")

    vorschau = _vorschau(NUTZER_A, "cp-aufbau-a")
    versand = _versand(NUTZER_A, preset_a)
    for quelle, payload in (("Vorschau", vorschau), ("Versand", versand)):
        alles = "\n".join(str(payload[k]) for k in ("subject", "email_html", "sms", "telegram"))
        assert "Innsbruck" in alles, f"{quelle}: Ort von A fehlt"
        for fremd in ("Chamonix", "Zermatt", "Westalpen"):
            assert fremd not in alles, f"AC-4: {quelle} fuer A zeigt {fremd!r} von Nutzer B"
    nutzer = {kw.get("user_id") for kw in env["calls"].kwargs_seen}
    assert nutzer == {NUTZER_A}, f"AC-4: Wetterabruf lief mit {nutzer!r}, erwartet nur A"

    from services.compare_preview_service import ComparePreviewService

    with pytest.raises(LookupError):
        ComparePreviewService().render_all_channels("cp-aufbau-b", user_id=NUTZER_A,
                                                    target_date=TARGET_DATE.isoformat())


def test_ac4_baustein_nutzt_die_echte_user_id(env):
    """AC-4 (Baustein): Given zwei Nutzer / When der Baustein fuer B laeuft /
    Then rechnet der Wetterabruf auf B's Konto (Abrufbudget #2234) und das
    Ergebnis traegt nur B's Orte.

    RED: services.compare_briefing_aufbau existiert noch nicht."""
    from services.compare_briefing_aufbau import compare_briefing_bauen, order_locations_by_ids

    preset_b = _preset_ablegen(NUTZER_B, "cp-aufbau-b2", ["loc-chx", "loc-zrm"], name="Westalpen")
    orte = order_locations_by_ids(_orte(NUTZER_B), preset_b["location_ids"])
    ergebnis = compare_briefing_bauen(preset_b, orte, TARGET_DATE, NUTZER_B, lang="de")

    nutzer = {kw.get("user_id") for kw in env["calls"].kwargs_seen}
    assert nutzer == {NUTZER_B}, f"AC-4: Baustein rief das Wetter mit {nutzer!r} ab"
    html = _feld(ergebnis, "email_html")
    assert "Chamonix" in html and "Innsbruck" not in html, "AC-4: falsche Orte im Baustein-Ergebnis"


# ---------------------------------------------------------------------------
# AC-5: genau eine Aufbau-Stelle, beide Seiten nutzen sie
# ---------------------------------------------------------------------------

_MARKE = "‹baustein-2983›"


def _markiert(wert):
    if isinstance(wert, str):
        return wert + _MARKE
    if isinstance(wert, tuple):
        return tuple(_markiert(v) for v in wert)
    if isinstance(wert, list):
        return [_markiert(v) for v in wert]
    if isinstance(wert, dict):
        return {k: _markiert(v) for k, v in wert.items()}
    return wert


def test_ac5_aenderung_am_baustein_wirkt_in_vorschau_und_versand(env, monkeypatch):
    """AC-5: Given eine Test-Ersatzfassung der Render-Schritte des Bausteins
    (sie haengt eine Marke an jeden Text) / When Vorschau und Versand laufen /
    Then traegt JEDER Kanal beider Seiten die Marke -- es gibt keine zweite,
    eigene Kopie des Aufbaus.

    RED: services.compare_briefing_aufbau existiert noch nicht."""
    import services.compare_briefing_aufbau as aufbau

    for name in ("compare_email_rendern", "compare_kanaltexte_rendern"):
        original = getattr(aufbau, name)
        monkeypatch.setattr(
            aufbau, name,
            lambda *a, _o=original, **k: _markiert(_o(*a, **k)),
        )

    preset = _preset_ablegen(NUTZER_A, "cp-aufbau-marke", ["loc-ibk", "loc-bz"])
    vorschau = _vorschau(NUTZER_A, "cp-aufbau-marke")
    versand = _versand(NUTZER_A, preset)

    for quelle, payload in (("Vorschau", vorschau), ("Versand", versand)):
        for kanal in ("email_html", "sms", "telegram"):
            assert _MARKE in payload[kanal], (
                f"AC-5: {quelle}-{kanal} laeuft nicht durch den Baustein "
                "(eigene Kopie des Aufbaus)"
            )


# ---------------------------------------------------------------------------
# AC-6: kein Zirkelimport, Alt-Namen bleiben
# ---------------------------------------------------------------------------


def test_ac6_baustein_laedt_weder_versand_noch_vorschau():
    """AC-6: Given der Baustein / When er in einem frischen Prozess importiert
    wird / Then sind weder ``scheduler_dispatch_service`` noch
    ``compare_preview_service`` geladen.

    RED: Modul existiert nicht (Import scheitert im Subprozess)."""
    code = (
        "import sys, services.compare_briefing_aufbau as m\n"
        "print(sorted(n for n in sys.modules if n.endswith(('scheduler_dispatch_service',"
        " 'compare_preview_service'))))\n"
    )
    env = dict(os.environ, PYTHONPATH=f"{REPO_ROOT / 'src'}{os.pathsep}{REPO_ROOT}")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       cwd=REPO_ROOT, env=env, timeout=120)
    assert r.returncode == 0, f"AC-6: Baustein nicht importierbar:\n{r.stderr[-1500:]}"
    assert r.stdout.strip() == "[]", f"AC-6: Baustein zieht Dienste nach: {r.stdout.strip()}"


def test_ac6_alte_namen_bleiben_importierbar_und_sind_dieselben():
    """AC-6: Given der Umzug / Then sind ``order_locations_by_ids`` und
    ``build_compare_preset_subject`` aus den alten Modulen importierbar und
    identisch mit dem Baustein (Re-Export, keine zweite Fassung).

    RED: Modul existiert nicht."""
    import services.compare_briefing_aufbau as aufbau
    from services.compare_preview_service import order_locations_by_ids
    from services.scheduler_dispatch_service import build_compare_preset_subject

    assert order_locations_by_ids is aufbau.order_locations_by_ids
    assert build_compare_preset_subject is aufbau.build_compare_preset_subject


# ---------------------------------------------------------------------------
# AC-7: Baustein ohne Nebenwirkung
# ---------------------------------------------------------------------------


def _verzeichnis_abbild(root: Path) -> dict:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*")) if p.is_file()
    }


def test_ac7_baustein_und_vorschau_ohne_nebenwirkung(env, monkeypatch):
    """AC-7: Given der Baustein / When er (direkt und ueber die Vorschau)
    ausgefuehrt wird / Then wird nichts versendet, kein Anker/Melde-Gedaechtnis
    geschrieben, kein Vorfall gebucht und keine Datei im Datenverzeichnis
    geaendert.

    RED: services.compare_briefing_aufbau existiert noch nicht."""
    import services.alert_briefing_anchor as anker
    import services.notification_service as ns
    from services.compare_briefing_aufbau import compare_briefing_bauen, order_locations_by_ids

    preset = _preset_ablegen(NUTZER_A, "cp-aufbau-rein", ["loc-ibk", "loc-bz"])

    def _verboten(name):
        def _wirf(*a, **k):
            raise AssertionError(f"AC-7: Baustein/Vorschau loest {name} aus")
        return _wirf

    monkeypatch.setattr(ns.NotificationService, "send_compare_report", _verboten("Versand"))
    for name in ("write_anchor_and_reset_memory", "record_briefing_dispatch_failure"):
        monkeypatch.setattr(anker, name, _verboten(name))

    vorher = _verzeichnis_abbild(env["data_root"])
    orte = order_locations_by_ids(_orte(NUTZER_A), preset["location_ids"])
    ergebnis = compare_briefing_bauen(preset, orte, TARGET_DATE, NUTZER_A, lang="de")
    _vorschau(NUTZER_A, "cp-aufbau-rein")
    nachher = _verzeichnis_abbild(env["data_root"])

    for kanal in ("subject", "email_html", "email_text", "telegram", "sms"):
        assert _feld(ergebnis, kanal), f"Baustein liefert leeres {kanal}"
    assert sorted(nachher) == sorted(vorher), (
        f"AC-7: Dateien angelegt/geloescht: {sorted(set(nachher) ^ set(vorher))}"
    )
    geaendert = [k for k in vorher if vorher[k] != nachher[k]]
    assert not geaendert, f"AC-7: Dateien geaendert: {geaendert}"


# ---------------------------------------------------------------------------
# AC-8: Reihenfolge des Versands
# ---------------------------------------------------------------------------


def test_ac8_ohne_wetter_kein_mailaufbau_und_kein_versand(env, monkeypatch):
    """AC-8: Given alle Orte ohne Wetterdaten / When der Versand laeuft / Then
    endet er mit ``no_weather``, BEVOR der Baustein eine Mail rendert, und es
    wird nichts zugestellt.

    RED: services.compare_briefing_aufbau existiert noch nicht."""
    import services.compare_briefing_aufbau as aufbau
    from services.send_outcomes import SendOutcomeError
    from services.scheduler_dispatch_service import send_one_compare_preset

    gerendert: list[str] = []
    for name in ("compare_email_rendern", "compare_kanaltexte_rendern"):
        original = getattr(aufbau, name)
        monkeypatch.setattr(
            aufbau, name,
            lambda *a, _o=original, _n=name, **k: (gerendert.append(_n), _o(*a, **k))[1],
        )

    env["calls"].alle_fehler = True
    preset = _preset_ablegen(NUTZER_A, "cp-aufbau-leer", ["loc-ibk", "loc-bz"])
    mail, sms, telegram = _Sink(), _Sink(), _Sink()
    with pytest.raises(SendOutcomeError) as exc:
        send_one_compare_preset(
            preset, _settings(), NUTZER_A, "data", all_locations_cache=_orte(NUTZER_A),
            target_date=TARGET_DATE, tage_ab_ortstag=0, on_demand=True,
            mail_sink=mail, sms_sink=sms, telegram_sink=telegram,
        )
    assert "no_weather" in str(exc.value.args), f"AC-8: falscher Ausgang {exc.value.args!r}"
    assert env["calls"].kwargs_seen, "Vorbedingung: der Wetterlauf hat stattgefunden"
    assert gerendert == [], f"AC-8: trotz no_weather gerendert: {gerendert}"
    assert not (mail.calls or sms.calls or telegram.calls), "AC-8: trotz no_weather zugestellt"


# ---------------------------------------------------------------------------
# AC-9: gemeinsame Zieltag-Ermittlung
# ---------------------------------------------------------------------------


def test_ac9_zieltag_ist_ortstag_des_ersten_aufloesbaren_orts(env):
    """AC-9: Given Orte in unterschiedlichen Zeitzonen und eine feste Uhr / When
    der Tag ohne Vorgabe bestimmt wird / Then gilt der Ortstag des ERSTEN
    aufloesbaren Orts, und die Vorschau kommt ueber dieselbe Ermittlung zum
    selben Tag.

    RED: compare_zieltag_bestimmen existiert noch nicht."""
    from services.compare_briefing_aufbau import compare_zieltag_bestimmen
    from services.compare_preview_service import _resolve_target_date

    denver = SavedLocation(id="loc-den", name="Denver", lat=39.74, lon=-104.99, elevation_m=1600)
    ibk = SavedLocation(id="loc-ibk", name="Innsbruck", lat=47.27, lon=11.39, elevation_m=600)
    jetzt = datetime(2026, 7, 9, 3, 0, tzinfo=timezone.utc)  # Denver 8.7. abends, Innsbruck 9.7.

    assert compare_zieltag_bestimmen([denver, ibk], jetzt, context_label="t") == date(2026, 7, 8)
    assert compare_zieltag_bestimmen([ibk, denver], jetzt, context_label="t") == date(2026, 7, 9)
    assert _resolve_target_date(None, [denver, ibk], jetzt) == date(2026, 7, 8)
    # Vorgabe der Vorschau bleibt wirksam (ISO-String und date).
    assert _resolve_target_date("2026-07-01", [denver, ibk], jetzt) == date(2026, 7, 1)


def test_ac9_versand_ohne_tag_nutzt_dieselbe_ermittlung(env, monkeypatch):
    """AC-9: Given Vorschau und Versand ohne uebergebenen Zieltag / When der Tag
    bestimmt wird / Then rufen BEIDE die gemeinsame Ermittlung des Bausteins und
    kommen zum selben Tag (sichtbar im Betreff).

    RED: compare_zieltag_bestimmen existiert noch nicht."""
    import services.compare_briefing_aufbau as aufbau

    aufrufe: list[date] = []
    original = aufbau.compare_zieltag_bestimmen

    def _protokoll(*a, **k):
        tag = original(*a, **k)
        aufrufe.append(tag)
        return tag

    monkeypatch.setattr(aufbau, "compare_zieltag_bestimmen", _protokoll)
    preset = _preset_ablegen(NUTZER_A, "cp-aufbau-tag", ["loc-ibk", "loc-bz"])
    vorschau = _vorschau(NUTZER_A, "cp-aufbau-tag", target_date=None)
    versand = _versand(NUTZER_A, preset, target_date=None)

    assert len(aufrufe) == 2, f"AC-9: gemeinsame Ermittlung {len(aufrufe)}x statt 2x gerufen"
    assert aufrufe[0] == aufrufe[1], f"AC-9: Vorschau {aufrufe[0]} != Versand {aufrufe[1]}"
    assert vorschau["subject"] == versand["subject"], "AC-9: Betreff (Tag) weicht ab"


# ---------------------------------------------------------------------------
# Adversary-Gegenprobe (F001/F002): Zusicherungen des Bausteins am Wirkort
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("schalter", [False, True])
def test_f001_amtliche_warnungen_schalter_erreicht_den_wetterlauf(env, schalter):
    """F001 (M10): Given ein Ortsvergleich mit dem Schalter "Amtliche
    Warnungen" aus bzw. an / When Vorschau und Versand laufen / Then empfaengt
    der Wetterlauf je Ort genau diesen Wert (``official_alerts_enabled``) --
    dort entscheidet die Engine, ob Warnungen ueberhaupt geholt werden
    (#1040, #3047 E4). Ein fest verdrahtetes ``True`` holte trotz "aus"."""
    preset = _preset_ablegen(
        NUTZER_A, "cp-aufbau-warn", ["loc-ibk", "loc-bz"],
        extra={"official_alerts_enabled": schalter,
               "official_warnings": {"enabled": schalter}},
    )
    from services.amtliche_warnungen_schalter import amtliche_warnungen_an_preset

    assert amtliche_warnungen_an_preset(preset) is schalter, (
        "Vorbedingung: der gespeicherte Schalter kommt durch den Loader"
    )
    _vorschau(NUTZER_A, "cp-aufbau-warn")
    _versand(NUTZER_A, preset)

    gesehen = [kw.get("official_alerts_enabled") for kw in env["calls"].kwargs_seen]
    assert len(gesehen) == 4, f"Vorbedingung: je Ort ein Lauf in Vorschau und Versand, {gesehen}"
    assert gesehen == [schalter] * 4, (
        f"F001/M10: Wetterlauf bekam official_alerts_enabled={gesehen}, "
        f"Schalter im Ortsvergleich ist {schalter}"
    )


def _fragezaehler(teil: str) -> int:
    treffer = re.findall(r"(?:^|\s)\?(\d+)(?=\s|$)", teil)
    return sum(int(n) for n in treffer)


def test_f001_sms_zeigt_unmappbare_auswahl_in_vorschau_und_versand(env):
    """F001 (M12): Given ein Ortsvergleich, dessen SMS-Auswahl eine Groesse
    ohne Renderer-Zuordnung traegt (``unresolved_by_channel["sms"] == 1``,
    #1405 S3) / When Vorschau und Versand laufen / Then ist die SMS in der
    Vorschau, im Versand und in der Telegram-Kurzform (= SMS-Text) identisch.

    #3172 (ADR-0125): der Zaehler ``?N`` ist abgeloest -- die unmappbare
    Auswahl erzeugt in der SMS kein Zeichen mehr (die Mail weist sie aus);
    jeder Ortsteil ist die Token-Zeile ``{Name}: D22``."""
    from services.report_config_resolver import resolve_compare_render_options

    preset = _preset_ablegen(
        NUTZER_A, "cp-aufbau-luecke", ["loc-ibk", "loc-bz"], telegram_style="kurzform",
        extra={"display_config": {
            "telegram_style": "kurzform",
            "active_metrics": ["temp_max_c", "wind_max_kmh"],
            "channel_active_metrics": {"sms": ["temp_max_c", "gibt_es_nicht_2983"]},
        }},
    )
    opts = resolve_compare_render_options(preset)
    assert opts.unresolved_by_channel.get("sms") == 1, (
        f"Vorbedingung: SMS-Luecke kommt durch den Loader, {opts.unresolved_by_channel}"
    )
    vorschau = _vorschau(NUTZER_A, "cp-aufbau-luecke")
    versand = _versand(NUTZER_A, preset)

    for quelle, payload in (("Vorschau", vorschau), ("Versand", versand)):
        for kanal in ("sms", "telegram"):
            text = payload[kanal]
            # Wire-Form "Orte TT.MM.: <Ort>: <Token>; <Ort>: <Token>" (sms_format.md §5b)
            teile = [t.strip() for t in text.split(": ", 1)[-1].split(";") if t.strip()]
            assert [t.split(": ", 1)[0] for t in teile] == ["Innsbruck", "Bozen"], text
            for teil in teile:
                assert _fragezaehler(teil) == 0, (
                    f"#3172: {quelle}-{kanal} mit abgeloestem Zaehler ?N in {teil!r}: {text!r}"
                )
                assert re.fullmatch(r"\w+: D\d+", teil), (quelle, kanal, teil)
    assert vorschau["sms"] == versand["sms"], "F001/M12: Vorschau-SMS != Versand-SMS"
    assert vorschau["telegram"] == versand["telegram"], "F001/M12: Kurzform weicht ab"


def test_f003_mail_und_telegram_langform_zeigen_unmappbare_auswahl(env):
    """F003 (M16/M17): Given ein Ortsvergleich (Telegram-Langform), dessen
    E-Mail- und Telegram-Auswahl je eine Groesse ohne Renderer-Zuordnung
    traegt (``unresolved_by_channel`` je 1, #1405 S3) / When Vorschau und
    Versand laufen / Then traegt die Mail (HTML und Klartext) genau einmal den
    tabellenweiten Hinweis "+1 ... ohne Wert in diesem Vergleich" und das
    Telegram je Ort den Hinweis "+1 ... ohne Wert an diesem Ort" -- in
    Vorschau und Versand gleich. Ohne die Luecke fehlt der Hinweis (Gegenprobe
    am Kontroll-Preset)."""
    import html as _html

    from output.renderers.channel_layout import selection_gap_notice
    from services.report_config_resolver import resolve_compare_render_options

    luecke_mail = selection_gap_notice(1, scope="vergleich")
    luecke_ort = selection_gap_notice(1, scope="ort")
    assert luecke_mail and luecke_ort, "Vorbedingung: Hinweis-Wortlaut nicht leer"

    def _ablegen(preset_id: str, mit_luecke: bool) -> dict:
        extra_id = ["gibt_es_nicht_2983"] if mit_luecke else []
        return _preset_ablegen(
            NUTZER_A, preset_id, ["loc-ibk", "loc-bz"],
            extra={"display_config": {
                "active_metrics": ["temp_max_c", "wind_max_kmh"],
                "channel_active_metrics": {
                    "email": ["temp_max_c", "wind_max_kmh", *extra_id],
                    "telegram": ["temp_max_c", "wind_max_kmh", *extra_id],
                },
            }},
        )

    preset = _ablegen("cp-aufbau-luecke-lang", True)
    kontrolle = _ablegen("cp-aufbau-ohne-luecke-lang", False)
    opts = resolve_compare_render_options(preset)
    assert opts.unresolved_by_channel.get("email") == 1, opts.unresolved_by_channel
    assert opts.unresolved_by_channel.get("telegram") == 1, opts.unresolved_by_channel
    assert not any(resolve_compare_render_options(kontrolle).unresolved_by_channel.values())

    for quelle, payload, gegen in (
        ("Vorschau", _vorschau(NUTZER_A, "cp-aufbau-luecke-lang"),
         _vorschau(NUTZER_A, "cp-aufbau-ohne-luecke-lang")),
        ("Versand", _versand(NUTZER_A, preset), _versand(NUTZER_A, kontrolle)),
    ):
        html_text = _html.unescape(payload["email_html"])
        assert html_text.count(luecke_mail) == 1, (
            f"F003/M17: {quelle}-Mail (HTML) ohne Luecken-Hinweis {luecke_mail!r}"
        )
        if "email_text" in payload:  # Klartext traegt nur der Versand
            assert (payload["email_text"] or "").count(luecke_mail) == 1, (
                f"F003/M17: {quelle}-Mail (Klartext) ohne Luecken-Hinweis {luecke_mail!r}"
            )
            assert luecke_mail not in (gegen["email_text"] or ""), quelle
        telegram = payload["telegram"]
        assert telegram != payload["sms"], f"Vorbedingung: {quelle}-Telegram ist Langform"
        assert telegram.count(luecke_ort) == 2, (
            f"F003/M16: {quelle}-Telegram ohne Luecken-Hinweis je Ort: {telegram!r}"
        )
        # Gegenprobe: ohne unmappbare Auswahl kein Hinweis.
        assert luecke_mail not in _html.unescape(gegen["email_html"]), quelle
        assert luecke_ort not in gegen["telegram"], quelle


def test_f002_versand_zeigt_nicht_zugestellte_meldungen_in_der_mail(env):
    """F002 (M7): Given ein Ortsvergleich mit einer Meldung, die seit dem
    letzten Briefing einen Kanal nicht erreicht hat (Protokoll unter der
    Protokoll-Kennung ``preset_id``, #1461) / When der Versand laeuft / Then
    traegt die zugestellte Mail den Hinweisblock; die Vorschau (liest keine
    Vorfaelle) nicht."""
    from datetime import timedelta

    from app.loader import get_data_dir
    from output.renderers.email.undelivered_hint import HEADING_FAILED
    from services.alert_briefing_anchor import record_briefing_sent

    preset_id = "cp-aufbau-undeliv"
    preset = _preset_ablegen(NUTZER_A, preset_id, ["loc-ibk", "loc-bz"])
    jetzt = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    eintrag = {
        "entity_id": preset_id, "entity_type": "compare",
        "sent_at": (jetzt - timedelta(hours=2)).isoformat(),
        "changes_count": 1, "severity": "MODERATE",
        "metrics": [{"metric_id": "thunder", "aggregation": "max"}],
        "hazards": [], "reason": "forecast_change", "channels_sent": [],
        "channels_not_sent": [{"channel": "sms", "reason": "delivery_failed"}],
    }
    log = get_data_dir(NUTZER_A) / "alert_log.json"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(json.dumps({"entries": [], "not_delivered": [eintrag]}), encoding="utf-8")
    record_briefing_sent(user_id=NUTZER_A, entity_id=preset_id, entity_type="compare",
                         at=jetzt - timedelta(hours=6))

    vorschau = _vorschau(NUTZER_A, preset_id)
    versand = _versand(NUTZER_A, preset)

    assert HEADING_FAILED not in vorschau["email_html"], "Vorschau liest keine Vorfaelle"
    assert HEADING_FAILED in versand["email_html"], (
        "F002/M7: der Versand reicht die nicht zugestellte Meldung nicht an die Mail weiter"
    )


def test_f002_vorschau_spricht_die_sprache_des_nutzers(env):
    """F002 (M8): Given ein Nutzer mit ``language = "en"`` / When Vorschau und
    Versand laufen / Then ist der Betreff beider Seiten englisch und gleich
    (#2672) -- keine fest deutsche Vorschau."""
    from services.compare_briefing_aufbau import build_compare_preset_subject

    user_json = env["data_root"] / "users" / NUTZER_A / "user.json"
    user_json.write_text(json.dumps({"tier": "premium", "language": "en"}), encoding="utf-8")
    preset = _preset_ablegen(NUTZER_A, "cp-aufbau-en", ["loc-ibk", "loc-bz"])

    vorschau = _vorschau(NUTZER_A, "cp-aufbau-en")
    versand = _versand(NUTZER_A, preset)

    soll_en = build_compare_preset_subject("Urlaubsorte", TARGET_DATE, lang="en")
    assert soll_en != build_compare_preset_subject("Urlaubsorte", TARGET_DATE, lang="de"), (
        "Vorbedingung: Betreff unterscheidet sich je Sprache"
    )
    assert versand["subject"] == soll_en, "Vorbedingung: Versand spricht Englisch"
    assert vorschau["subject"] == soll_en, (
        f"F002/M8: Vorschau-Betreff nicht englisch: {vorschau['subject']!r}"
    )
    assert vorschau["email_html"] == versand["email_html"], (
        "F002/M8: Vorschau-Mail weicht von der englischen Versand-Mail ab"
    )


def test_f002_mail_zeigt_den_vertretungshinweis(env):
    """F002 (M14): Given ein Ort, dessen Wetterlauf eine Modell-Vertretung
    meldet (#1563) / When Vorschau und Versand laufen / Then tragen Mail-HTML
    und Mail-Text beider Seiten die Vertretungszeile dieses Orts."""
    from output.renderers.fallback_notice import build_compare_fallback_lines

    env["calls"].vertretung_bei = {"loc-bz"}
    preset = _preset_ablegen(NUTZER_A, "cp-aufbau-vertretung", ["loc-ibk", "loc-bz"])
    vorschau = _vorschau(NUTZER_A, "cp-aufbau-vertretung")
    versand = _versand(NUTZER_A, preset)

    from app.user import LocationResult

    bz = next(o for o in _orte(NUTZER_A) if o.id == "loc-bz")
    zeilen = build_compare_fallback_lines(
        [LocationResult(location=bz, forecast_meta=_vertretungs_meta())], lang="de",
    )
    assert zeilen and zeilen[0].startswith("Bozen"), f"Vorbedingung: Vertretungszeile {zeilen}"
    import html as _html

    for quelle, payload in (("Vorschau", vorschau), ("Versand", versand)):
        assert zeilen[0] in _html.unescape(payload["email_html"]), (
            f"F002/M14: {quelle}-Mail (HTML) ohne Vertretungshinweis"
        )
    assert zeilen[0] in versand["email_text"], "F002/M14: Versand-Mail (Text) ohne Vertretungshinweis"
