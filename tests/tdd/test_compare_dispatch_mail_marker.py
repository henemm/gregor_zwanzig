"""Verhaltensnachweis #1124 Teil A: Der Compare-Versandpfad setzt X-GZ-Mail-Type: compare.

Kein Mock-Framework (Mock()/patch()/MagicMock): echte Recording-Subklassen +
Attribut-Rebind, Muster wie test_issue_764_compare_forecast_hours_consume.py.
Die Substitution betrifft NUR die teuren Upstream-Abhaengigkeiten (Wetter-Engine
und Renderer), die in der Kern-Schicht kein Netz haben duerfen — NICHT den
Pruefgegenstand.

Pruefgegenstand (der echte Produktivpfad):
  - reicht `send_one_compare_preset()` `mail_type="compare"` an den echten
    Aufruf `EmailOutput(settings).send(...)` durch (Seam: das reale mail_type-
    Argument am realen Produktiv-Aufruf abgefangen, nicht simuliert), und
  - materialisiert der echte `build_mime_message()` aus diesem Wert den Header
    `X-GZ-Mail-Type: compare`.

Der Voll-Transport-Seam (echte SMTP-Message end-to-end) ist im Kern nicht
deterministisch aufsetzbar: `ComparisonEngine.run` + `render_compare_email`
brauchen Live-Wetterdaten, und die Empfaenger-Guards in EmailOutput.send
blockieren Test-Zustellungen. Daher der vom Spec vorgesehene Fallback-Seam,
plus separater Nachweis, dass der abgefangene Wert ueber den echten Builder
den Header erzeugt.

RED vor Fix: send_one_compare_preset ruft send() OHNE mail_type auf →
kwargs.get("mail_type") is None → beide Tests rot.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest


class _SendCaptured(Exception):
    """Sentinel: bricht send_one_compare_preset gezielt IM send()-Aufruf ab,
    nachdem die Argumente abgefangen wurden — bevor Guards/SMTP oder der
    Snapshot-Netz-Fetch beruehrt werden. Traegt die realen send()-kwargs."""

    def __init__(self, kwargs: dict):
        self.kwargs = kwargs
        super().__init__("send captured")


def _location(loc_id: str):
    """Eine echte SavedLocation (in-memory), durchgereicht ueber
    all_locations_cache — kein data/-Seiteneffekt, kein Netz-Resolve."""
    from app.loader import SavedLocation

    return SavedLocation(id=loc_id, name="Innsbruck", lat=47.27, lon=11.39, elevation_m=574)


def _preset(preset_id: str, loc_id: str) -> dict:
    return {
        "id": preset_id,
        "name": f"Vergleich {preset_id}",
        "location_ids": [loc_id],
        "schedule": "daily",
        "profil": "SUMMER_TREKKING",
        "hour_from": 9,
        "hour_to": 16,
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-01-01T00:00:00Z",
    }


def _capture_send_kwargs(tmp_path) -> dict:
    """Treibt den echten `send_one_compare_preset` und faengt die realen
    Argumente ab, die er an `EmailOutput.send` uebergibt.

    Mock-frei: echte Subklassen + Attribut-Rebind auf den Modulen, die
    send_one_compare_preset ZUR LAUFZEIT (`from ... import ...`) aufloest;
    alles in finally restauriert.
    """
    import output.channels.email as email_mod
    import output.renderers.comparison as render_mod
    import services.comparison_engine as ce_mod
    from app.config import Settings
    from app.user import ComparisonResult, LocationResult
    from services.scheduler_dispatch_service import send_one_compare_preset

    user_id = f"test1124-{uuid.uuid4().hex[:8]}"
    settings = Settings().with_user_profile(user_id)
    loc = _location("loc-1124-a")
    preset = _preset("cp-1124", "loc-1124-a")

    original_engine = ce_mod.ComparisonEngine
    original_render = render_mod.render_compare_email
    original_email = email_mod.EmailOutput

    class RecordingEngine(original_engine):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            return ComparisonResult(
                locations=[LocationResult(location=loc)],
                time_window=(9, 16),
                target_date=date.today(),
            )

    def _fake_render(*args, **kwargs):
        # Teure Renderer-Abhaengigkeit (braucht Live-Metriken) ersetzt — nicht
        # der Pruefgegenstand. Liefert nur plausible Bodies.
        return ("<html>Vergleich</html>", "Vergleich text")

    class RecordingEmailOutput(original_email):  # echte Subklasse, kein Mock
        def send(self, subject, body, **kwargs):
            raise _SendCaptured({"subject": subject, "body": body, **kwargs})

    ce_mod.ComparisonEngine = RecordingEngine
    render_mod.render_compare_email = _fake_render
    email_mod.EmailOutput = RecordingEmailOutput
    try:
        with pytest.raises(_SendCaptured) as exc:
            send_one_compare_preset(
                preset,
                settings,
                user_id,
                str(tmp_path),
                all_locations_cache=[loc],
            )
        return exc.value.kwargs
    finally:
        ce_mod.ComparisonEngine = original_engine
        render_mod.render_compare_email = original_render
        email_mod.EmailOutput = original_email


def test_dispatch_passes_mail_type_compare_to_real_send(tmp_path):
    """GIVEN ein faelliges Compare-Preset
    WHEN send_one_compare_preset laeuft und real EmailOutput.send aufruft
    THEN traegt der reale Aufruf mail_type="compare".

    RED vor Fix: der Aufruf setzt kein mail_type → None != "compare"."""
    kwargs = _capture_send_kwargs(tmp_path)
    assert kwargs.get("mail_type") == "compare", (
        f"Compare-Versandpfad reichte mail_type={kwargs.get('mail_type')!r} an "
        "EmailOutput.send durch, erwartet 'compare' — der Header X-GZ-Mail-Type "
        "fehlt sonst in der zugestellten Mail (#1124)."
    )


def test_captured_mail_type_yields_header_via_real_builder(tmp_path):
    """GIVEN das reale mail_type-Argument aus dem Produktivpfad
    WHEN es durch den echten build_mime_message laeuft
    THEN traegt die MIME-Message den Header X-GZ-Mail-Type: compare.

    Beweist end-to-end die Header-Materialisierung aus dem realen Builder
    (kein selbst gesetzter Header)."""
    from output.channels.email import build_mime_message

    kwargs = _capture_send_kwargs(tmp_path)
    msg = build_mime_message(
        subject=kwargs["subject"],
        body=kwargs["body"],
        from_addr="gregor_zwanzig@henemm.com",
        to_header="gregor-test@henemm.com",
        reply_to=None,
        html=True,
        plain_text_body=kwargs.get("plain_text_body"),
        mail_type=kwargs.get("mail_type"),
        compare_hourly_enabled=kwargs.get("compare_hourly_enabled"),
    )
    assert msg["X-GZ-Mail-Type"] == "compare", (
        f"build_mime_message erzeugte X-GZ-Mail-Type={msg['X-GZ-Mail-Type']!r} "
        "aus dem vom Produktivpfad durchgereichten mail_type — erwartet 'compare'."
    )
