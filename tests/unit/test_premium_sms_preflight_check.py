"""Vorab-Check vor dem kostenpflichtigen Premium-SMS-Live-Nachweis (#1533 S4).

Prueft ``scripts/premium_sms_preflight_check.py``: die reine Prueflogik (AC-4)
und ihre Verdrahtung gegen ``PreviewService`` (AC-5). Der Vorab-Check
existiert, damit Zeichenbudget und Zeichensatz am ECHTEN Trip-Text geprueft
sind, BEVOR der PO den Kanal einschaltet -- der Versand kostet Geld, die
Vorschau nicht.

Kein Mock: ein echter ``PreviewService``-Abkoemmling zaehlt die Aufrufe mit
und delegiert an die echte Implementierung. Datenwurzel per
``_isolate_data_root`` (conftest, autouse) isoliert, Wetterdaten per
``demo=True`` aus Fixtures -- kein Netz, kein Versand.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from services.preview_service import PreviewService

_TRIP_ID = "gr221-mallorca"
_USER_ID = "default"


@pytest.fixture
def _geseedeter_trip(_isolate_data_root):
    """Kopiert das committete Trip-Fixture in die isolierte Datenwurzel.

    Ziel ist ``briefings/`` (seit #1250 S7a die einzige Lese-Wahrheit, ADR-0023).
    Quelle relativ zur EIGENEN Testdatei (#1409) -- ein fester Hauptrepo-Pfad
    wuerde aus einem Worktree die fremde Kopie lesen.
    """
    from app import loader

    repo_root = Path(__file__).resolve().parents[2]
    src = repo_root / "tests/fixtures/data_root/users" / _USER_ID / "trips" / f"{_TRIP_ID}.json"
    dst = Path(loader._DATA_ROOT) / "users" / _USER_ID / "briefings" / f"{_TRIP_ID}.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


class _ZaehlenderPreviewService(PreviewService):
    """Echter Preview-Service, der nur mitschreibt, wofuer er gerufen wurde."""

    def __init__(self) -> None:
        super().__init__()
        self.aufrufe: list[str] = []
        self.demo_flags: list[bool] = []
        self.texte: dict[str, str] = {}

    def render_sms_preview(self, trip_id: str, **kwargs) -> tuple[str, str]:
        report_type = kwargs.get("report_type", "morning")
        self.aufrufe.append(report_type)
        self.demo_flags.append(kwargs.get("demo"))
        subject, sms = super().render_sms_preview(trip_id, **kwargs)
        self.texte[report_type] = sms
        return subject, sms


# ---------------------------------------------------------------------------
# AC-4 -- reine Pruefkogik
# ---------------------------------------------------------------------------

def test_check_sms_text_flags_length_and_charset_violations():
    """Vier synthetische Texte, jeder so gebaut, dass NUR ein Verstoss-Typ
    ueberhaupt moeglich ist -- ein Treffer beweist damit den richtigen Fund,
    ohne die Wortwahl der Meldung festzuschreiben."""
    from scripts.premium_sms_preflight_check import _check_sms_text

    sauber = "E7: K8 D19 R3.4@14 W32 G58 TH:H@15"
    zu_lang = "A" * 161  # reines GSM-7, einzig moeglicher Verstoss: Laenge
    mit_grad = "E7: Hoechstwert 33°C"  # <=160 Zeichen, einzig moeglich: Zeichensatz
    mit_extension = "KHW[Test] AMT ROT3/3: TH Mi10-14, E1"

    assert _check_sms_text(sauber) == [], (
        f"Sauberer Text {sauber!r} darf keinen Verstoss melden, meldete: "
        f"{_check_sms_text(sauber)}"
    )
    assert _check_sms_text(zu_lang), (
        f"{len(zu_lang)} Zeichen ueberschreiten das 160er-Budget -- der "
        "Vorab-Check meldete trotzdem nichts."
    )
    for text, zeichen in ((mit_grad, "°"), (mit_extension, "[")):
        verstoesse = _check_sms_text(text)
        assert verstoesse, (
            f"{zeichen!r} in {text!r} ist GSM-7-fremd bzw. kostet zwei Septets "
            "-- der Vorab-Check meldete trotzdem nichts."
        )
        assert any(zeichen in v for v in verstoesse), (
            f"Der Befund nennt das beanstandete Zeichen {zeichen!r} nicht: "
            f"{verstoesse} -- unbrauchbar fuer den PO am Live-Nachweis-Tag."
        )


# ---------------------------------------------------------------------------
# AC-5 -- Verdrahtung gegen PreviewService, beide Report-Typen
# ---------------------------------------------------------------------------

def test_run_checks_both_morning_and_evening_via_preview_service(_geseedeter_trip):
    """``run()`` muss BEIDE Report-Typen pruefen -- ein Vorab-Check, der nur
    das Morgenbriefing ansieht, laesst genau die Haelfte des Tourbetriebs
    ungeprueft."""
    from scripts.premium_sms_preflight_check import run

    service = _ZaehlenderPreviewService()
    ergebnis = run(_TRIP_ID, _USER_ID, demo=True, service=service)

    assert sorted(service.aufrufe) == ["evening", "morning"], (
        f"render_sms_preview() wurde fuer {service.aufrufe} gerufen, erwartet "
        "waren genau 'morning' und 'evening'."
    )
    assert service.demo_flags == [True, True], (
        f"demo=True wurde nicht bis zum Preview-Service durchgereicht: "
        f"{service.demo_flags}. Daran haengt die Zusicherung 'kein Netz' -- "
        "ohne sie ruft der Vorab-Check die Live-API auf."
    )
    assert set(ergebnis) == {"morning", "evening"}, (
        f"Rueckgabe deckt nicht beide Report-Typen ab: {sorted(ergebnis)}"
    )
    for report_type, befund in ergebnis.items():
        assert befund["text"] == service.texte[report_type], (
            f"{report_type}: bewertet wurde nicht der Text, den der "
            f"Preview-Service geliefert hat ({befund['text']!r} vs. "
            f"{service.texte[report_type]!r})."
        )
        assert befund["length"] == len(befund["text"]), (
            f"{report_type}: gemeldete Laenge {befund['length']} passt nicht "
            f"zum bewerteten Text ({len(befund['text'])} Zeichen)."
        )
        assert isinstance(befund["violations"], list), (
            f"{report_type}: Zeichensatz-Bewertung fehlt oder ist keine Liste: "
            f"{befund!r}"
        )
