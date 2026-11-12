"""Minimales Nutzerprofil fuer Versand-Tests (#2961).

Seit #2961 hat ein Nutzer ohne lesbares ``user.json`` keinen Mail-Empfaenger
mehr (kein Rueckfall auf das globale ``GZ_MAIL_TO``). Tests, die einen Versand
an ``mail_to`` pruefen, legen deshalb das Profil des Nutzers an.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.loader import get_data_dir

TEST_POSTFACH = "gregor-test@henemm.com"


def lege_profil_an(user_id: str, mail_to: str = TEST_POSTFACH, **felder) -> Path:
    """Schreibt ``data/users/<user_id>/user.json`` (unter der aktiven Datenwurzel).

    Ein vorhandenes Profil bleibt erhalten (Merge): nur fehlende Felder werden
    ergaenzt."""
    ordner = get_data_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    pfad = ordner / "user.json"
    bestehend = json.loads(pfad.read_text()) if pfad.exists() else {}
    pfad.write_text(json.dumps({"id": user_id, "mail_to": mail_to, **felder, **bestehend}))
    return pfad
