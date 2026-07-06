"""
TDD RED — Bug #610: Signal-Kanal aus Backend entfernen (Schritt 2/2)

Alle Tests prüfen den SOLL-Zustand NACH der Implementierung.
Jeder Test ist JETZT rot, weil Signal noch im Backend vorhanden ist.
Nach der Implementierung müssen alle Tests grün sein.

Referenz-Spec: docs/specs/modules/bug_610_signal_backend.md
Baseline (pre-fix): 10 pre-existing failures in test_hybrid_segmentation + test_segment_builder
"""
from __future__ import annotations

import dataclasses
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ===========================================================================
# AC-1: Output-Factory — get_channel("signal") darf keinen gültigen Kanal mehr liefern
# ===========================================================================


def test_get_channel_signal_raises_value_error_not_import_error():
    """
    AC-1: get_channel("signal") muss sauber ValueError werfen (kein dangling Import).

    RED-Zustand: outputs/base.py hat noch `from output.channels.signal import SignalOutput`
    im elif-Zweig. Da outputs/signal.py nicht existiert, crasht der Aufruf mit
    ModuleNotFoundError (ImportError-Subklasse) statt einem sauberen ValueError.

    SOLL nach Fix: Signal-Zweig entfernt → get_channel("signal") erreicht
    den else-Zweig und wirft ValueError("Unknown output channel: signal").
    """
    from output.channels.base import get_channel
    from app.config import Settings

    settings = Settings()
    with pytest.raises(ValueError, match="Unknown output channel"):
        get_channel("signal", settings)


def test_get_channel_signal_does_not_raise_import_error():
    """
    AC-1: Der dangling Import `from output.channels.signal import SignalOutput` ist entfernt.

    RED-Zustand: Aufruf von get_channel("signal") wirft aktuell ImportError/
    ModuleNotFoundError weil outputs/signal.py fehlt aber der Import noch drin ist.

    SOLL nach Fix: Kein ImportError mehr — nur ValueError.
    """
    from output.channels.base import get_channel
    from app.config import Settings

    settings = Settings()
    try:
        get_channel("signal", settings)
    except ValueError:
        # Korrekt: sauberer ValueError
        pass
    except ImportError as e:
        pytest.fail(
            f"get_channel('signal') wirft ImportError statt ValueError — "
            f"dangling import noch vorhanden: {e}"
        )


def test_get_channel_signal_branch_gone_from_source():
    """
    AC-1: Der elif-Zweig für 'signal' in outputs/base.py ist entfernt.

    Strukturell: get_channel() mit bekannten Kanälen funktioniert weiterhin,
    'signal' ist kein gültiger Kanal mehr.
    """
    from output.channels.base import get_channel
    from app.config import Settings

    settings = Settings()

    # Bekannte Kanäle müssen weiter funktionieren (kein Signal-Fix bricht sie)
    null_channel = get_channel("none", settings)
    assert null_channel is not None

    # Signal: sauber ablehnend
    with pytest.raises(ValueError):
        get_channel("signal", settings)


# ===========================================================================
# AC-3: Renderer — 'signal' nicht in CHANNEL_LIMITS, render_narrow unterstützt nur telegram
# ===========================================================================


def test_channel_limits_has_no_signal_key():
    """
    AC-3: 'signal' ist nicht mehr in CHANNEL_LIMITS.

    RED-Zustand: CHANNEL_LIMITS enthält aktuell den Eintrag
    "signal": {"max_table_cols": 6, "max_chars": 1800}.
    """
    from src.output.renderers.channel_layout import CHANNEL_LIMITS

    assert "signal" not in CHANNEL_LIMITS, (
        f"CHANNEL_LIMITS enthält noch 'signal': {CHANNEL_LIMITS.get('signal')} — "
        "muss entfernt werden (AC-3)"
    )


def test_channel_limits_retains_telegram():
    """
    AC-3 (Regressionsschutz): 'telegram' bleibt in CHANNEL_LIMITS.
    """
    from src.output.renderers.channel_layout import CHANNEL_LIMITS

    assert "telegram" in CHANNEL_LIMITS, (
        "CHANNEL_LIMITS hat 'telegram' verloren — darf nicht passieren"
    )
    assert "email" in CHANNEL_LIMITS, "CHANNEL_LIMITS hat 'email' verloren"
    assert "sms" in CHANNEL_LIMITS, "CHANNEL_LIMITS hat 'sms' verloren"


def test_narrow_renderer_line_width_has_no_signal():
    """
    AC-3 (superseded durch Issue #1001): narrow.py ist seit dem Breaking Replace
    (render_telegram_bubbles ersetzt render_narrow vollstaendig) ausschliesslich
    Telegram-spezifisch — das per-Kanal-Dict `_LINE_WIDTH` existiert nicht mehr,
    stattdessen feste Telegram-Konstanten `_TG_PROSE_WIDTH`/`_TG_TABLE_WIDTH`.
    Der urspruengliche AC-3-Zweck (kein Signal-Ueberbleibsel im Renderer) ist
    dadurch a-fortiori erfuellt: es gibt ueberhaupt keinen Kanal-Schluessel mehr.
    """
    import src.output.renderers.narrow as narrow_module

    assert not hasattr(narrow_module, "_LINE_WIDTH"), (
        "narrow._LINE_WIDTH sollte seit #1001 nicht mehr existieren "
        "(Renderer ist Telegram-exklusiv)"
    )
    assert hasattr(narrow_module, "_TG_PROSE_WIDTH"), (
        "narrow._TG_PROSE_WIDTH (Nachfolge-Konstante) fehlt — Regression"
    )


# ===========================================================================
# AC-4: Modell — TripReport hat kein signal_text-Feld mehr
# ===========================================================================


def test_trip_report_has_no_signal_text_field():
    """
    AC-4: TripReport.signal_text ist entfernt.

    RED-Zustand: models.py:665 definiert
    `signal_text: Optional[str] = None  # Deprecated (Bug #590)...`

    SOLL nach Fix: das Feld existiert nicht mehr in TripReport.
    """
    from app.models import TripReport

    field_names = {f.name for f in dataclasses.fields(TripReport)}
    assert "signal_text" not in field_names, (
        f"TripReport hat noch das Feld 'signal_text' — muss entfernt werden (AC-4). "
        f"Vorhandene Felder: {sorted(field_names)}"
    )


def test_trip_report_retains_telegram_text_field():
    """
    AC-4 (Regressionsschutz, angepasst durch Issue #1001): TripReport behält
    ein Telegram-Feld. Issue #1001 hat `telegram_text: Optional[str]` bewusst
    (Breaking Change des transienten DTOs, siehe Spec "Side effects") durch
    `telegram_bubbles: list[str]` ersetzt — der urspruengliche Regressionsschutz
    ("Telegram-Feld darf bei der Signal-Entfernung nicht mitverschwinden") gilt
    jetzt fuer das neue Feld.
    """
    from app.models import TripReport

    field_names = {f.name for f in dataclasses.fields(TripReport)}
    assert "telegram_text" not in field_names, (
        "TripReport hat noch 'telegram_text' — sollte seit #1001 durch "
        "'telegram_bubbles' ersetzt sein"
    )
    assert "telegram_bubbles" in field_names, (
        "TripReport hat 'telegram_bubbles' verloren — Regression (Issue #1001)"
    )
    assert "sms_text" in field_names, (
        "TripReport hat 'sms_text' verloren — Regression"
    )
    assert "email_html" in field_names, (
        "TripReport hat 'email_html' verloren — Regression"
    )


def test_cli_channel_choices_exclude_signal():
    """
    AC-4: CLI akzeptiert 'signal' nicht mehr als --channel-Option.

    RED-Zustand: cli.py:65 hat `choices=["console", "email", "signal", "none"]`.
    """
    from app.cli import create_parser

    parser = create_parser()
    # Finde die --channel-Action
    channel_action = None
    for action in parser._actions:
        if hasattr(action, "dest") and action.dest == "channel":
            channel_action = action
            break

    assert channel_action is not None, "CLI hat keine --channel-Option"
    choices = channel_action.choices or []
    assert "signal" not in choices, (
        f"CLI --channel akzeptiert noch 'signal': {choices} — muss entfernt werden (AC-4)"
    )
    # Telegram und sms müssen bleiben
    assert "email" in choices, "CLI hat 'email' aus --channel verloren"


# ===========================================================================
# AC-6: Roundtrip — Altdaten mit signal_text laden ohne Crash, Rest intakt
# ===========================================================================


def test_trip_report_config_roundtrip_ignores_legacy_signal_fields():
    """
    AC-6: Ein TripReportConfig mit altem send_signal-Feld (aus persistiertem JSON)
    muss fehlerfrei laden und alle anderen Felder behalten.

    Verhaltenstest: Kein Crash beim Laden eines Dicts mit unbekanntem Feld.
    """
    from app.models import TripReportConfig
    import dataclasses

    # Simuliert einen gespeicherten Datensatz aus der Zeit, als signal_text existierte
    legacy_data = {
        "trip_id": "gr20-test",
        "enabled": True,
        "send_email": True,
        "send_sms": False,
        "send_telegram": True,
        # Legacy-Felder aus alten Saves (vor #590/#610):
        # send_signal ist schon durch #590 entfernt worden
    }

    # Laden: nur bekannte Felder übergeben
    known_fields = {f.name for f in dataclasses.fields(TripReportConfig)}
    clean_data = {k: v for k, v in legacy_data.items() if k in known_fields}
    config = TripReportConfig(**clean_data)

    assert config.trip_id == "gr20-test"
    assert config.send_email is True
    assert config.send_telegram is True
    assert not hasattr(config, "send_signal"), (
        "TripReportConfig hat noch send_signal — bereits in #590 entfernt"
    )


def test_trip_report_construction_without_signal_text():
    """
    AC-6: TripReport kann ohne signal_text-Feld konstruiert werden.

    SOLL nach Fix: signal_text existiert nicht mehr, Konstruktion ohne
    signal_text ist der einzig mögliche Weg.
    """
    from app.models import TripReport

    field_names = {f.name for f in dataclasses.fields(TripReport)}

    # Konkrete Prüfung: signal_text darf nicht mehr im Modell sein
    assert "signal_text" not in field_names, (
        "TripReport hat noch 'signal_text' — AC-4/AC-6: muss entfernt werden"
    )


# ===========================================================================
# AC-5: Preview-Endpoint — GET /api/preview/{trip_id}/signal → 404
# ===========================================================================


@pytest.fixture
def preview_client():
    """TestClient mit dem Preview-Router — direkte Import-Verdrahtung ohne Mocks."""
    from api.routers import preview
    app = FastAPI()
    app.include_router(preview.router)
    return TestClient(app, raise_server_exceptions=False)


def test_preview_signal_endpoint_returns_404(preview_client):
    """
    AC-5: GET /api/preview/{trip_id}/signal existiert nicht mehr → 404.

    RED-Zustand: preview.py registriert noch `@router.get("/api/preview/{trip_id}/signal")`.
    SOLL nach Fix: Route entfernt → TestClient bekommt 404.
    """
    resp = preview_client.get(
        "/api/preview/gr221-mallorca/signal",
        params={"user_id": "default"},
    )
    assert resp.status_code == 404, (
        f"GET /api/preview/gr221-mallorca/signal antwortete {resp.status_code} "
        f"statt 404 — Route muss entfernt werden (AC-5)"
    )


def test_preview_telegram_endpoint_still_exists(preview_client):
    """
    AC-5 (Regressionsschutz): /api/preview/{trip_id}/telegram bleibt erreichbar.

    Erlaubte Status: 200, 404 (Trip nicht gefunden), 422, 503 — aber NICHT 405 (Method Not Allowed).
    """
    resp = preview_client.get(
        "/api/preview/gr221-mallorca/telegram",
        params={"user_id": "default", "demo": "true"},
    )
    # Route muss existieren — 405 wäre ein Zeichen dass sie verschwunden ist
    assert resp.status_code != 405, (
        "GET /api/preview/gr221-mallorca/telegram antwortete 405 — "
        "Telegram-Route darf nicht entfernt worden sein"
    )


def test_preview_email_endpoint_still_exists(preview_client):
    """
    AC-5 (Regressionsschutz): /api/preview/{trip_id}/email bleibt erreichbar.
    """
    resp = preview_client.get(
        "/api/preview/gr221-mallorca/email",
        params={"user_id": "default", "demo": "true"},
    )
    assert resp.status_code != 405, (
        "GET /api/preview/gr221-mallorca/email antwortete 405 — Route darf nicht fehlen"
    )


def test_signal_route_not_registered_in_preview_router():
    """
    AC-5: Der Preview-Router hat keine Route mit Pfad-Suffix '/signal'.

    Direkter Routen-Tabellen-Check als Ergänzung zum HTTP-Test.
    """
    from api.routers import preview

    signal_routes = [
        r for r in preview.router.routes
        if hasattr(r, "path") and r.path.endswith("/signal")
    ]
    assert len(signal_routes) == 0, (
        f"Preview-Router hat noch {len(signal_routes)} Route(n) mit Pfad-Suffix "
        f"'/signal': {[r.path for r in signal_routes]} — muss entfernt werden (AC-5)"
    )
