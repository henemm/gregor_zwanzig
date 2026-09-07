"""TDD RED — Antwort an den Fragenden statt an den Betreiber (Issue #2168).

SPEC: docs/specs/modules/fix_2168_antwort_an_den_fragenden.md (AC-1, AC-4)
Kontext: docs/context/fix-2168-antwort-an-den-fragenden.md

Defekt: ``InboundTelegramReader._process_update``, Zweig ``user_id ==
"default"`` (``inbound_telegram_reader.py:182-191``), ruft
``send_telegram_message(chat_id=chat_id, ..., settings=settings)`` mit den
BASIS-Settings auf. ``TelegramOutput.send()`` liest die Zieladresse
ausschliesslich aus ``settings.telegram_chat_id`` (``telegram.py:403``) — die
korrekt uebergebene ``chat_id`` wird nirgends verwendet. Der
Registrierungshinweis geht deshalb an den Betreiber statt an den Fragenden.

Nachweisform (zwingend, s. Spec-Abschnitt "Nachweisform"):
* NICHT am Draht (``httpx.post``-Payload) — ``_guard_code_origin``
  (``telegram.py:162-195``) haengt an der Code-HERKUNFT
  (``app/origin_guard.py:30-41``), nicht an ``is_test_mode``: aus jedem
  Worktree schaltet er die Ziel-Chat-ID auf ``telegram_test_chat_id`` um oder
  bricht hart ab. Ein Payload-Test saehe immer nur die Test-Chat-ID.
* NICHT das ``chat_id``-Argument am Notifier abgreifen (Muster
  ``_MitschnittNotifier``, ``test_kommandoliste_einzelquelle.py:234-247``) —
  dieses Argument wird bereits HEUTE korrekt uebergeben, es wird nur nicht
  benutzt. Ein Test darauf waere heute schon gruen und faengt den Bug nicht.
* Gemessen wird an der Konstruktor-Naht von ``TelegramOutput`` (Muster
  ``Kanalmitschrift``/``_aufzeichner_installieren``,
  ``test_kanaltreue_adhoc_antwort.py:115-192``) — dort liegt die Adresse fest,
  die ``send()`` tatsaechlich benutzen wird.
* Einstieg ist ``InboundTelegramReader._process_update(update, settings)``,
  NICHT ``TripCommandProcessor().process(...)`` — letzterer ueberspringt den
  Reader und erreicht den ``default``-Zweig nie.

Mock-frei: echte ``InboundTelegramReader``/``Settings``-Instanzen, echte
Aufzeichner-Klasse statt ``Mock()``/``patch()``. Isolierte Datenwurzel per
autouse-Fixture aus ``tests/conftest.py`` (#1133).
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.config import Settings  # noqa: E402
from app.loader import get_data_dir  # noqa: E402
from services.inbound_telegram_reader import InboundTelegramReader  # noqa: E402


def _kennung(praefix: str) -> str:
    """Mandantenkennung OHNE "tdd"/"test" — sonst erzwingt ``is_test_user_id``
    ``Settings.for_testing()`` und ``with_user_profile`` ueberschreibt die
    ``telegram_chat_id`` des Profils nicht mehr (``config.py:387-388``)."""
    return f"antwort-fragend-{praefix}-{uuid.uuid4().hex[:6]}"


def _aufzeichner_installieren(monkeypatch) -> list[str]:
    """Ersetzt ``notification_service.TelegramOutput`` durch eine echte
    Klasse, die die Zieladresse in ``__init__`` mitschneidet — genau die
    Groesse, die ``send()`` tatsaechlich verwenden wird (``telegram.py:403``).
    Kein ``Mock()``. Muster: ``Kanalmitschrift``/``_aufzeichner_installieren``
    (``test_kanaltreue_adhoc_antwort.py:115-192``)."""
    from services import notification_service as ns

    aufgezeichnete_chat_ids: list[str] = []

    class _TelegramAufzeichner:
        def __init__(self, settings) -> None:
            aufgezeichnete_chat_ids.append(settings.telegram_chat_id)

        def send(self, subject, body, reply_markup=None, *, parse_mode=None,
                 suppress_subject_line=False) -> int:
            return 1

    monkeypatch.setattr(ns, "TelegramOutput", _TelegramAufzeichner)
    return aufgezeichnete_chat_ids


# ═══════════════════════════ AC-1 ════════════════════════════════════════════


def test_ac1_antwort_an_unbekannten_chat_geht_an_den_absender_nicht_an_die_basis(
    monkeypatch,
):
    """AC-1.

    GIVEN eine Telegram-Nachricht von einer Chat-ID, zu der kein
          Nutzerprofil existiert, und Basis-Einstellungen mit einer
          ABWEICHENDEN ``telegram_chat_id`` (Betreiber-Chat).
    WHEN  ``_process_update`` die Nachricht verarbeitet (Registrierungs-
          Hinweis).
    THEN  ist die zum Versand VERWENDETE Adresse genau die Absender-Chat-ID
          — und die Basis-/Betreiber-Chat-ID kommt in KEINER Aufzeichnung vor.

    RED heute: der ``default``-Zweig uebergibt ``settings=settings`` (Basis)
    statt der Absender-Chat-ID — der Aufzeichner sieht die Betreiber-Chat-ID.
    """
    aufzeichnungen = _aufzeichner_installieren(monkeypatch)

    fragender_chat = "fragender-chat-" + uuid.uuid4().hex[:8]
    basis_chat = "betreiber-chat-" + uuid.uuid4().hex[:8]
    basis_settings = Settings(telegram_chat_id=basis_chat)

    reader = InboundTelegramReader()
    verarbeitet = reader._process_update(
        {"message": {"text": "hallo gregor", "chat": {"id": fragender_chat}}},
        basis_settings,
    )

    assert verarbeitet, "Vorbedingung: der Reader muss das Update verarbeitet haben"
    assert fragender_chat in aufzeichnungen, (
        f"AC-1: der Aufzeichner muss die Absender-Chat-ID {fragender_chat!r} "
        f"sehen, aufgezeichnet wurden {aufzeichnungen!r}"
    )
    assert basis_chat not in aufzeichnungen, (
        f"AC-1: die Basis-/Betreiber-Chat-ID {basis_chat!r} darf in KEINER "
        f"Aufzeichnung vorkommen — der Hinweis ginge sonst an den Betreiber "
        f"statt an den Fragenden. Aufgezeichnet wurden {aufzeichnungen!r}"
    )


# ═══════════════════════════ AC-4 ════════════════════════════════════════════


def test_ac4_registrierter_chat_bekommt_antwort_weiterhin_an_seine_profil_chat_id(
    monkeypatch,
):
    """AC-4 (Regressionswaechter, startet GRUEN).

    GIVEN ein Telegram-Absender, dessen Chat-ID einem Nutzerprofil
          zugeordnet ist, und eine ABWEICHENDE Basis-/Betreiber-Chat-ID.
    WHEN  er eine Nachricht schickt (hier: ohne aktiven Trip — einer der
          sechs bereits korrekten Aufrufer, ``:203-208``).
    THEN  ist die verwendete Adresse die Chat-ID AUS SEINEM PROFIL — nicht
          die Basis-Chat-ID.

    Sichert, dass der Fix fuer AC-1 die sechs bereits korrekten Aufrufer
    nicht verschiebt (Spec-Tabelle "Nur der `default`-Zweig weicht ab").
    """
    aufzeichnungen = _aufzeichner_installieren(monkeypatch)

    user_id = _kennung("ac4")
    profil_chat = "profil-chat-" + uuid.uuid4().hex[:8]
    basis_chat = "betreiber-chat-" + uuid.uuid4().hex[:8]

    ordner = get_data_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "user.json").write_text(json.dumps({
        "id": user_id,
        "telegram_chat_id": profil_chat,
    }))

    basis_settings = Settings(telegram_chat_id=basis_chat)
    reader = InboundTelegramReader()
    verarbeitet = reader._process_update(
        {"message": {"text": "irgendein text", "chat": {"id": profil_chat}}},
        basis_settings,
    )

    assert verarbeitet, "Vorbedingung: der Reader muss das Update verarbeitet haben"
    assert aufzeichnungen == [profil_chat], (
        f"AC-4: die Antwort an einen registrierten Nutzer muss an seine "
        f"Profil-Chat-ID {profil_chat!r} gehen, aufgezeichnet wurden "
        f"{aufzeichnungen!r}"
    )
    assert basis_chat not in aufzeichnungen, (
        f"AC-4: die Basis-/Betreiber-Chat-ID {basis_chat!r} darf hier nicht "
        f"auftauchen, aufgezeichnet wurden {aufzeichnungen!r}"
    )
