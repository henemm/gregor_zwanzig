"""TDD RED -- Issue #2220 C5-58: unbekannter Kanalname bleibt unbeobachtet.

``_resolve_channel_flags`` (``src/services/trip_report_scheduler.py:1747-
1753``) loest einen unbekannten ``restrict_to_channel``-Namen unbemerkt auf
``(False, False, False, False)`` auf -- exakt dasselbe Tupel, das auch ein
bekannter, aber tier-gesperrter Kanal liefert (feat_2126 AC-5). AC-8 prueft,
dass ein unbekannter Name protokolliert wird; AC-9 (die Falle) prueft, dass
der bekannte SMS-Name OHNE Tier-Berechtigung dabei KEINE Warnung ausloest --
der Guard prueft den Namen, nicht das Ergebnis-Tupel.

Spec: docs/specs/modules/fix_2220_telegram_kommando_befunde.md
Kontext: docs/context/fix-2220-telegram-kommando-befunde.md

Kern-Schicht, deterministisch: keine Mocks/patch()/MagicMock, kein Netz. Kein
Stub von ``sms_allowed`` (AC-9 verlangt das ausdruecklich) -- echtes
Nutzerprofil ohne SMS-Tier von der isolierten Datenwurzel (autouse-Fixtur aus
tests/conftest.py), Muster wie ``test_kanaltreue_adhoc_antwort.py`` AC-5.

Pfadregel #1409: der Pruefling wird relativ zur eigenen Testdatei aufgeloest.
"""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

import services.trip_report_scheduler as _trs
from app.loader import get_data_dir
from services.trip_report_scheduler import TripReportSchedulerService
from services.user_tier import sms_allowed

_BAUM = Path(__file__).resolve().parents[2]
_PRUEFLING = Path(_trs.__file__).resolve()
assert _PRUEFLING.is_relative_to(_BAUM), (
    f"Pfadregel #1409 verletzt: der Pruefling liegt unter {_PRUEFLING}, "
    f"diese Testdatei aber unter {_BAUM}."
)


def _kennung(praefix: str) -> str:
    return f"unbekannter-kanal-{praefix}-{uuid.uuid4().hex[:6]}"


def _nutzer_anlegen(user_id: str, *, tier: str = "free") -> None:
    """Echtes ``user.json`` -- Tier von der Platte, kein Stub."""
    ordner = get_data_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "user.json").write_text(json.dumps({"id": user_id, "tier": tier}))


# ═══════════════════════════ AC-8 ════════════════════════════════════════════


def test_ac8_unbekannter_kanalname_erzeugt_eine_warnung_mit_dem_namen(caplog):
    """AC-8.

    GIVEN ``restrict_to_channel`` traegt einen Namen ausserhalb der vier
          bekannten Kanaele (``"whatsapp"``),
    WHEN  die Kanal-Flags ueber ``_resolve_channel_flags`` aufgeloest werden,
    THEN  wird GENAU EINE Log-Warnung protokolliert, die "whatsapp" woertlich
          nennt; der Rueckgabewert bleibt ``(False, False, False, False)``.
    """
    uid = _kennung("ac8")
    _nutzer_anlegen(uid, tier="free")
    scheduler = TripReportSchedulerService(user_id=uid)

    with caplog.at_level(logging.WARNING):
        ergebnis = scheduler._resolve_channel_flags(
            None, uid, restrict_to_channel="whatsapp",
        )

    assert ergebnis == (False, False, False, False), (
        f"AC-8: der Rueckgabewert darf sich nicht aendern, erhalten {ergebnis!r}"
    )
    warnungen = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnungen) == 1, (
        f"AC-8: erwartet genau EINE Warnung, gefunden {len(warnungen)}: "
        f"{[r.getMessage() for r in warnungen]}"
    )
    assert "whatsapp" in warnungen[0].getMessage(), (
        f"AC-8: die Warnung nennt den unbekannten Namen nicht woertlich: "
        f"{warnungen[0].getMessage()!r}"
    )


# ═══════════════════════════ AC-9 (Falle) ════════════════════════════════════


def test_ac9_bekannter_sms_name_ohne_tier_erzeugt_keine_warnung(caplog):
    """AC-9 (Falle).

    GIVEN ``restrict_to_channel="sms"`` bei einem Nutzer OHNE SMS-Tier
          (``sms_allowed(user_id) == False``) -- ein legitimer,
          spezifizierter Zustand (feat_2126 AC-5),
    WHEN  die Kanal-Flags aufgeloest werden,
    THEN  wird KEINE Warnung protokolliert; das Ergebnis bleibt
          ``(False, False, False, False)`` -- der Guard prueft den NAMEN,
          nicht das Ergebnis-Tupel.
    """
    uid = _kennung("ac9")
    _nutzer_anlegen(uid, tier="free")
    assert sms_allowed(uid) is False, (
        "Testaufbau: das Profil darf keine SMS-Berechtigung tragen, sonst "
        "prueft AC-9 nicht die Falle"
    )
    scheduler = TripReportSchedulerService(user_id=uid)

    with caplog.at_level(logging.WARNING):
        ergebnis = scheduler._resolve_channel_flags(
            None, uid, restrict_to_channel="sms",
        )

    assert ergebnis == (False, False, False, False), (
        f"AC-9: das Ergebnis muss vier-mal False bleiben, erhalten {ergebnis!r}"
    )
    warnungen = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert not warnungen, (
        f"AC-9: 'sms' ist ein BEKANNTER Kanalname -- keine Warnung darf "
        f"feuern, obwohl das Ergebnis vier-mal False ist. Gefeuert: "
        f"{[r.getMessage() for r in warnungen]}"
    )
