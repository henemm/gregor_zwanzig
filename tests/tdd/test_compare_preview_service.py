"""TDD RED — Issue #1270 / Spec docs/specs/modules/compare_channel_preview_dispatch.md

Echte Vorschau fuer den Orts-Vergleich (`ComparePreviewService`), Test 2/4/8/9
des Test Plans (AC-1, AC-2, AC-7 + Ein-Ort-Edge-Case).

RED-Grund: `src/services/compare_preview_service.py` existiert nicht →
ModuleNotFoundError in jedem Test. Heute haengt der Vorschau-Tab am
Validator-Stub (`validator_render_service.py:147`), der einen hartcodierten
Ort "Vorschau-Ort"/`preview-1` rendert (KB-1).

KEINE Mocks (kein Mock()/patch()/MagicMock). Substituiert wird ausschliesslich
die teure Upstream-Abhaengigkeit `ComparisonEngine.run` (braucht Live-Wetter,
in der Kern-Schicht verboten) — per echter Subklasse + Attribut-Rebind auf dem
Modul, das der Pruefgegenstand ZUR LAUFZEIT aufloest; alles im finally
restauriert (Haus-Muster: tests/tdd/test_compare_dispatch_mail_marker.py).

Nicht-Zirkularitaet: die Recording-Engine baut ihr Ergebnis AUS den Orten, die
der Service ihr uebergibt. Taucht ein Stub-Ort in der Vorschau auf, hat der
Service ihn auch an die Engine gereicht — der Test wuerde ihn sehen.
Die Renderer selbst bleiben echt (reine Funktionen, kein Netz).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

import pytest

from app.loader import get_data_dir, save_location
from app.models import ForecastDataPoint, ThunderLevel
from app.user import SavedLocation

from tests.helpers.compare_briefings import write_compare_briefings

TARGET_DATE = date(2026, 7, 8)


# ---------------------------------------------------------------------------
# Umgebung: isolierter Daten-Root, ueber BEIDE Zugriffsformen erreichbar
# (get_data_dir()/_DATA_ROOT und das relative "data"-Default von
# load_compare_presets) — der Service darf beide Wege waehlen.
# ---------------------------------------------------------------------------


@pytest.fixture
def compare_env(tmp_path, monkeypatch):
    from app import loader as app_loader

    data_root = tmp_path / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_loader, "_DATA_ROOT", str(data_root))
    try:
        from src.app import loader as src_loader

        monkeypatch.setattr(src_loader, "_DATA_ROOT", str(data_root))
    except ImportError:  # pragma: no cover - Alias-Modul immer vorhanden
        pass
    return f"tdd-1270-{uuid.uuid4().hex[:8]}"


def _location(loc_id: str, name: str, lat: float, lon: float) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=1000)


def _preset(preset_id: str, user_id: str, location_ids: list[str], **extra) -> dict:
    preset = {
        "id": preset_id,
        "name": "Urlaubsorte",
        "user_id": user_id,
        "location_ids": location_ids,
        "schedule": "daily",
        "profil": "ALLGEMEIN",
        "hour_from": 9,
        "hour_to": 16,
        "forecast_hours": 48,
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-07-01T00:00:00Z",
    }
    preset.update(extra)
    return preset


def _dp(hour: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(TARGET_DATE.year, TARGET_DATE.month, TARGET_DATE.day, hour, 0),
        t2m_c=22.0,
        wind_chill_c=21.0,
        wind10m_kmh=11.0,
        gust_kmh=19.0,
        precip_1h_mm=0.0,
        cloud_total_pct=35,
        uv_index=5.0,
        thunder_level=ThunderLevel.NONE,
        pop_pct=10,
        visibility_m=9000,
    )


class _EngineCalls:
    """Aufruf-Protokoll der echten Engine-Naht (Zaehler + uebergebene Orte
    + die uebergebenen Keyword-Argumente; Issue #1268 prueft time_window/
    forecast_hours am echten Aufruf-Vertrag)."""

    def __init__(self) -> None:
        self.count = 0
        self.locations_seen: list[list[SavedLocation]] = []
        self.kwargs_seen: list[dict] = []


def _install_recording_engine(monkeypatch, calls: _EngineCalls) -> None:
    """Ersetzt ComparisonEngine durch eine echte Subklasse, die das Ergebnis
    AUS den uebergebenen Orten baut (kein Netz, keine vorgegebene Antwort).

    Rebind auf `services.comparison_engine` (Laufzeit-Aufloesung bei
    funktionslokalem Import) UND — falls vorhanden — auf dem Service-Modul
    selbst (Modul-Level-Import). monkeypatch restauriert beides.
    """
    import services.comparison_engine as ce_mod
    from app.user import ComparisonResult, LocationResult

    original = ce_mod.ComparisonEngine

    class RecordingEngine(original):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            locations = kwargs.get("locations")
            if locations is None and args:
                locations = args[0]
            locations = list(locations or [])
            calls.count += 1
            calls.locations_seen.append(locations)
            calls.kwargs_seen.append(dict(kwargs))
            return ComparisonResult(
                locations=[
                    LocationResult(
                        location=loc,
                        score=90 - 7 * i,
                        temp_max=22.0 + i,
                        temp_min=12.0 + i,
                        wind_max=11.0,
                        gust_max=19.0,
                        cloud_avg=35,
                        sunny_hours=6,
                        official_alerts=[],
                        hourly_data=[_dp(9), _dp(12), _dp(15)],
                    )
                    for i, loc in enumerate(locations)
                ],
                time_window=kwargs.get("time_window", (9, 16)),
                target_date=kwargs.get("target_date", TARGET_DATE),
                created_at=datetime(2026, 7, 8, 4, 0),
            )

    monkeypatch.setattr(ce_mod, "ComparisonEngine", RecordingEngine)
    try:
        import services.compare_preview_service as svc_mod
    except ImportError:
        return  # RED: der Service existiert noch nicht — der Test meldet das selbst
    if hasattr(svc_mod, "ComparisonEngine"):
        monkeypatch.setattr(svc_mod, "ComparisonEngine", RecordingEngine)


def _flatten_text(value) -> str:
    """Kanal-Payloads koennen str oder (subject, body, bubbles)-Tupel sein
    (PreviewService-Konvention) — beides zu einem Text zusammenziehen, damit
    der Inhaltsnachweis nicht an der Verpackung haengt."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return "\n".join(_flatten_text(v) for v in value)
    return str(value)


def _field(payload, name: str):
    """Feldzugriff auf dict ODER Objekt (dataclass) — die Spec legt die
    Antwort-Schluessel fest (`subject`/`email_html`/`telegram`/`sms`), nicht
    die Traeger-Form."""
    if isinstance(payload, dict):
        assert name in payload, f"Antwort-Feld '{name}' fehlt: {sorted(payload)}"
        return payload[name]
    assert hasattr(payload, name), f"Antwort-Feld '{name}' fehlt an {payload!r}"
    return getattr(payload, name)


def _seed(user_id: str, locations: list[SavedLocation], preset: dict) -> None:
    for loc in locations:
        save_location(loc, user_id=user_id)
    write_compare_briefings(get_data_dir(user_id), [preset])


# ---------------------------------------------------------------------------
# Test 2 (AC-1) — echte E-Mail-Vorschau statt Stub-Ort
# ---------------------------------------------------------------------------


def test_email_preview_shows_real_preset_locations_not_stub(compare_env, monkeypatch):
    """GIVEN ein Preset mit zwei echten Orten des Nutzers
    WHEN ComparePreviewService.render_email_preview laeuft
    THEN enthaelt das HTML die echten Ortsnamen und keinen Stub-Ort.

    RED: services.compare_preview_service existiert nicht (ModuleNotFoundError).
    Heute rendert der Vorschau-Pfad ueber den Validator-Stub genau EINEN Ort
    namens "Vorschau-Ort" (id "preview-1") mit lauter "—"-Werten (KB-1)."""
    user_id = compare_env
    locations = [
        _location("loc-ibk", "Innsbruck", 47.27, 11.39),
        _location("loc-bz", "Bozen", 46.50, 11.35),
    ]
    _seed(user_id, locations, _preset("cp-1270-a", user_id, ["loc-ibk", "loc-bz"]))

    calls = _EngineCalls()
    _install_recording_engine(monkeypatch, calls)
    from services.compare_preview_service import ComparePreviewService

    html = ComparePreviewService().render_email_preview(
        "cp-1270-a", user_id=user_id, target_date=TARGET_DATE.isoformat()
    )

    assert isinstance(html, str) and html.strip(), "Vorschau-HTML darf nicht leer sein"
    assert "Innsbruck" in html, "Der echte Preset-Ort 'Innsbruck' fehlt in der E-Mail-Vorschau"
    assert "Bozen" in html, "Der echte Preset-Ort 'Bozen' fehlt in der E-Mail-Vorschau"
    assert "Vorschau-Ort" not in html, (
        "AC-1: Die Vorschau zeigt weiterhin den hartcodierten Stub-Ort "
        "'Vorschau-Ort' (validator_render_service.py:147) statt der Orte des Nutzers."
    )
    assert "preview-1" not in html, "Stub-Orts-ID 'preview-1' darf in der Vorschau nicht vorkommen"
    assert calls.count == 1, f"Genau ein Engine-Lauf erwartet, waren {calls.count}"
    assert [loc.id for loc in calls.locations_seen[0]] == ["loc-ibk", "loc-bz"], (
        "Der Service muss die im Preset konfigurierten Orte an die "
        f"ComparisonEngine reichen, uebergeben wurden: {calls.locations_seen[0]!r}"
    )


# ---------------------------------------------------------------------------
# Test 4 (AC-2) — echte Telegram-Vorschau aus den Preset-Orten
# ---------------------------------------------------------------------------


def test_telegram_preview_renders_real_preset_locations(compare_env, monkeypatch):
    """GIVEN ein Preset mit Telegram-Opt-in und zwei echten Orten
    WHEN ComparePreviewService.render_telegram_preview aufgerufen wird
    THEN enthaelt der Text die Ortsnamen des Presets (kein Platzhalter).

    RED: services.compare_preview_service existiert nicht; eine
    Telegram-Vorschau fuer den Ortsvergleich gibt es heute ueberhaupt nicht
    (Frontend zeigt einen Hinweis-Zweig, KB-4)."""
    user_id = compare_env
    locations = [
        _location("loc-ibk", "Innsbruck", 47.27, 11.39),
        _location("loc-bz", "Bozen", 46.50, 11.35),
    ]
    _seed(
        user_id,
        locations,
        _preset("cp-1270-b", user_id, ["loc-ibk", "loc-bz"], send_telegram=True),
    )

    calls = _EngineCalls()
    _install_recording_engine(monkeypatch, calls)
    from services.compare_preview_service import ComparePreviewService

    payload = ComparePreviewService().render_telegram_preview(
        "cp-1270-b", user_id=user_id, target_date=TARGET_DATE.isoformat()
    )
    text = _flatten_text(payload)

    assert text.strip(), "Telegram-Vorschau darf nicht leer sein"
    assert "Innsbruck" in text and "Bozen" in text, (
        "AC-2: Die Telegram-Vorschau muss aus den echten Preset-Orten gerendert "
        f"sein, war aber: {text[:300]!r}"
    )
    assert "Vorschau-Ort" not in text, "Stub-Ort darf in der Telegram-Vorschau nicht vorkommen"
    assert calls.count == 1, f"Genau ein Engine-Lauf erwartet, waren {calls.count}"


# ---------------------------------------------------------------------------
# Test 8 (AC-7) — EIN Aufruf, EIN Engine-Lauf, alle drei Kanaele gefuellt
# ---------------------------------------------------------------------------


def test_single_preview_call_runs_engine_once_and_fills_all_channels(compare_env, monkeypatch):
    """GIVEN ein Preset mit zwei Orten
    WHEN die Preview-Einstiegsfunktion EINMAL aufgerufen wird
    THEN wird ComparisonEngine.run genau einmal ausgefuehrt UND die Antwort
    traegt email_html, telegram und sms gleichzeitig gefuellt.

    Aufruf-Zaehler ueber eine echte Subklasse (kein Verhaltens-Mock).
    RED: services.compare_preview_service existiert nicht — es gibt heute
    keinen Einstieg, der alle Kanaele in einer Antwort liefert (ADR-0011)."""
    user_id = compare_env
    locations = [
        _location("loc-ibk", "Innsbruck", 47.27, 11.39),
        _location("loc-bz", "Bozen", 46.50, 11.35),
    ]
    _seed(user_id, locations, _preset("cp-1270-c", user_id, ["loc-ibk", "loc-bz"]))

    calls = _EngineCalls()
    _install_recording_engine(monkeypatch, calls)
    from services.compare_preview_service import ComparePreviewService

    payload = ComparePreviewService().render_all_channels(
        "cp-1270-c", user_id=user_id, target_date=TARGET_DATE.isoformat()
    )

    assert calls.count == 1, (
        "AC-7: Ein Vorschau-Aufruf darf die Wetter-Berechnung genau EINMAL "
        f"ausloesen (ein ComparisonEngine.run), gezaehlt wurden {calls.count}."
    )
    email_html = _flatten_text(_field(payload, "email_html"))
    telegram = _flatten_text(_field(payload, "telegram"))
    sms = _flatten_text(_field(payload, "sms"))
    assert email_html.strip(), "AC-7: email_html muss in derselben Antwort gefuellt sein"
    assert telegram.strip(), "AC-7: telegram muss in derselben Antwort gefuellt sein"
    assert sms.strip(), "AC-7: sms muss in derselben Antwort gefuellt sein"
    assert "Innsbruck" in email_html and "Innsbruck" in telegram, (
        "Alle Kanaele muessen auf demselben ComparisonResult der echten "
        "Preset-Orte beruhen"
    )


# ---------------------------------------------------------------------------
# Issue #1268 (AC-11) — die Vorschau rechnet mit dem Fenster des echten Versands
# ---------------------------------------------------------------------------


def test_preview_uses_fixed_full_day_window_ignoring_preset(compare_env, monkeypatch):
    """GIVEN ein Preset mit gespeichertem Zeitfenster 10-14 Uhr und Horizont 24h
    WHEN die Vorschau gerendert wird
    THEN erhaelt ComparisonEngine.run time_window=(0, 23) und forecast_hours=48
    — exakt das, was der echte Versand nutzt (scheduler_dispatch_service.py:319-326).

    Fachlich (Issue #1268): Zeitfenster/Horizont sind keine Editor-Felder mehr.
    Eine Vorschau, die die deprecateten Preset-Werte liest, zeigt etwas anderes
    als die tatsaechlich versendete Mail — genau der Widerspruch, den AC-11
    ausschliesst.

    RED vor Fix: der Service liest preset.get("hour_from", 9)/("hour_to", 16)
    und reicht (10, 14)/24 durch (compare_preview_service.py:143-145)."""
    user_id = compare_env
    locations = [_location("loc-ibk", "Innsbruck", 47.27, 11.39)]
    _seed(
        user_id,
        locations,
        _preset(
            "cp-1268-pv", user_id, ["loc-ibk"], hour_from=10, hour_to=14, forecast_hours=24
        ),
    )

    calls = _EngineCalls()
    _install_recording_engine(monkeypatch, calls)
    from services.compare_preview_service import ComparePreviewService

    ComparePreviewService().render_all_channels(
        "cp-1268-pv", user_id=user_id, target_date=TARGET_DATE.isoformat()
    )

    assert calls.kwargs_seen[0].get("time_window") == (0, 23), (
        "AC-11: Die Vorschau muss denselben Zeitraum rechnen wie der Versand "
        f"(0, 23), uebergeben wurde {calls.kwargs_seen[0].get('time_window')!r} "
        "— vermutlich aus den deprecateten Preset-Feldern hour_from/hour_to."
    )
    assert calls.kwargs_seen[0].get("forecast_hours") == 48, (
        "AC-11: Die Vorschau muss den festen 48h-Horizont des Versands nutzen, "
        f"uebergeben wurde {calls.kwargs_seen[0].get('forecast_hours')!r}."
    )


def test_preview_of_new_preset_without_hours_is_not_empty_window(compare_env, monkeypatch):
    """GIVEN ein NEU angelegtes Preset — der Wizard schickt hour_from/hour_to
    seit #1268 nicht mehr, das Go-Model persistiert daher den Zero-Value 0
    WHEN die Vorschau gerendert wird
    THEN rechnet sie NICHT mit dem leeren Fenster (0, 0), sondern mit (0, 23).

    Genau der in AC-11 benannte Schaden: "ein aus hour_from/hour_to gebautes
    Fenster, das bei neuen Vergleichen 0-0 Uhr waere und die Vorschau leer
    liefe". Staerker als der Assert oben: schliesst aus, dass (0, 23) zufaellig
    aus einem Default entsteht.

    RED vor Fix: preset.get("hour_from", 9) findet die persistierte 0 (der
    Default 9 greift NICHT, der Schluessel existiert) -> (0, 0)."""
    user_id = compare_env
    locations = [_location("loc-ibk", "Innsbruck", 47.27, 11.39)]
    _seed(
        user_id,
        locations,
        _preset(
            "cp-1268-new", user_id, ["loc-ibk"], hour_from=0, hour_to=0, forecast_hours=0
        ),
    )

    calls = _EngineCalls()
    _install_recording_engine(monkeypatch, calls)
    from services.compare_preview_service import ComparePreviewService

    ComparePreviewService().render_all_channels(
        "cp-1268-new", user_id=user_id, target_date=TARGET_DATE.isoformat()
    )

    assert calls.kwargs_seen[0].get("time_window") == (0, 23), (
        "AC-11: Ein neu angelegtes Preset traegt hour_from/hour_to = 0 (Go "
        "Zero-Value, der Wizard schickt die Felder nicht mehr). Die Vorschau "
        f"rechnet damit mit {calls.kwargs_seen[0].get('time_window')!r} und "
        "liefe leer — erwartet (0, 23)."
    )


# ---------------------------------------------------------------------------
# Test 9 (Edge Case) — genau EIN Ort ist ein gueltiger Vergleich
# ---------------------------------------------------------------------------


def test_single_location_preset_previews_without_error(compare_env, monkeypatch):
    """GIVEN ein Preset mit genau EINEM Ort
    WHEN die Vorschau angefordert wird
    THEN liefert sie eine normale Vorschau (kein Fehler, kein Mindest-Ort-Zwang).

    Bestandsvertrag: `subscriptionHelpers.ts:130` kennt "1 Ort" als gueltigen
    Zustand; alle Gates pruefen auf `location_ids.length === 0`.
    RED: services.compare_preview_service existiert nicht."""
    user_id = compare_env
    locations = [_location("loc-ibk", "Innsbruck", 47.27, 11.39)]
    _seed(user_id, locations, _preset("cp-1270-d", user_id, ["loc-ibk"]))

    calls = _EngineCalls()
    _install_recording_engine(monkeypatch, calls)
    from services.compare_preview_service import ComparePreviewService

    html = ComparePreviewService().render_email_preview(
        "cp-1270-d", user_id=user_id, target_date=TARGET_DATE.isoformat()
    )

    assert isinstance(html, str) and html.strip(), (
        "Ein Ein-Ort-Vergleich muss eine normale Vorschau liefern — ein "
        "Mindest-Ort-Zwang waere ein Regress gegen den Bestandsvertrag."
    )
    assert "Innsbruck" in html, "Der einzige Preset-Ort muss in der Vorschau erscheinen"
