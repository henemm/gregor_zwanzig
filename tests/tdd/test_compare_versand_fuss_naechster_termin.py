"""#1969 AC-26 im ECHTEN Versandpfad: der Abo-Fuss einer tatsaechlich
verschickten Compare-Mail nennt den naechsten Termin (Datum, HH:00, Kuerzel).

Spec: docs/specs/modules/feat_1969_naechstes_briefing.md (AC-26/AC-27)

Der Kern-Test ``test_compare_mail_fuss_naechster_versand.py`` steigt ueber die
Vorschau ein; das Durchreichen des Presets in
``scheduler_dispatch_service.send_one_compare_preset`` bewacht er nicht
(Adversary F001). Hier laeuft der echte ``send_one_compare_preset`` mit dem
ECHTEN Renderer; abgefangen wird erst der reale ``EmailOutput.send``-Aufruf
(Muster ``test_compare_dispatch_mail_marker.py``: echte Subklassen +
Attribut-Rebind, kein Mock-Framework). Ersetzt ist ausser dem Transport nur
die Wetter-Engine (kein Netz in der Kern-Schicht) -- nicht der Pruefgegenstand.

``Settings(..., _env_file=None)`` und ``delenv("GZ_MAIL_TO")``: eine lokale
``.env`` faerbt den Test nicht.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

VIENNA = ZoneInfo("Europe/Vienna")
# Fr 23.10.2026 07:00 Ortszeit Innsbruck (CEST) = die faellige Morgen-Stunde.
JETZT = datetime(2026, 10, 23, 7, tzinfo=VIENNA).astimezone(timezone.utc)


class _SendCaptured(Exception):
    def __init__(self, kwargs: dict):
        self.kwargs = kwargs
        super().__init__("send captured")


def _versende_und_fange_body(tmp_path) -> str:
    import output.channels.email as email_mod
    import services.comparison_engine as ce_mod
    from app.config import Settings
    from app.loader import SavedLocation
    from app.user import ComparisonResult, LocationResult
    from services.scheduler_dispatch_service import send_one_compare_preset

    user_id = f"nb-versand-{uuid.uuid4().hex[:8]}"
    settings = Settings(
        smtp_host="mail.henemm.com", smtp_port=587,
        smtp_user="dummy-user-1969", smtp_pass="dummy-pass-1969",
        mail_to="gregor-test@henemm.com", _env_file=None,
    ).with_user_profile(user_id)
    ort = SavedLocation(id="ort-ibk", name="Innsbruck", lat=47.27, lon=11.39, elevation_m=574)
    preset = {
        "id": "cp-1969-versand", "kind": "vergleich", "name": "Versand-Fuss",
        "location_ids": ["ort-ibk"], "schedule": "daily", "weekday": None,
        "morning_enabled": True, "morning_time": "07:00:00",
        "evening_enabled": True, "evening_time": "18:00:00",
        "empfaenger": ["gregor-test@henemm.com"], "created_at": "2026-01-01T00:00:00Z",
    }

    original_engine = ce_mod.ComparisonEngine
    original_email = email_mod.EmailOutput

    class OfflineEngine(original_engine):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            return ComparisonResult(
                locations=[LocationResult(location=ort)], time_window=(9, 16),
                target_date=date(2026, 10, 23),
            )

    class FangEmailOutput(original_email):  # echte Subklasse, kein Mock
        def send(self, subject, body, **kwargs):
            raise _SendCaptured({"subject": subject, "body": body, **kwargs})

    ce_mod.ComparisonEngine = OfflineEngine
    email_mod.EmailOutput = FangEmailOutput
    try:
        with freeze_time(JETZT):
            with pytest.raises(_SendCaptured) as exc:
                send_one_compare_preset(
                    preset, settings, user_id, str(tmp_path),
                    all_locations_cache=[ort],
                    target_date=date(2026, 10, 23), tage_ab_ortstag=0,
                )
    finally:
        ce_mod.ComparisonEngine = original_engine
        email_mod.EmailOutput = original_email
    return exc.value.kwargs["body"]


def test_versandpfad_fuss_nennt_folgetermin_mit_uhrzeit_und_kuerzel(tmp_path, monkeypatch):
    """AC-26 (Versandpfad): daily 07:00/18:00, versendet in der faelligen
    Stunde ⇒ der Fuss der ZUGESTELLTEN Mail nennt „23.10.2026 18:00 CEST" --
    nicht „—" (Preset nicht durchgereicht) und nicht den laufenden 07:00-Slot."""
    monkeypatch.delenv("GZ_MAIL_TO", raising=False)

    body = _versende_und_fange_body(tmp_path)

    start = body.find("Nächster Versand")
    assert start >= 0, "Fuss-Abschnitt 'Nächster Versand' fehlt in der versendeten Mail"
    fuss = body[start:body.find("</td>", start)]
    assert "23.10.2026 18:00 CEST" in fuss, (
        f"Versandpfad: Fuss nennt nicht den echten Folgetermin: {fuss!r}"
    )
    assert "—" not in fuss, f"Versandpfad: Fuss faellt auf '—' zurueck: {fuss!r}"
