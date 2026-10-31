"""Sprache je Nutzer, kein globaler Zustand (Issue #2662 AC-7).

Zwei echte ``user.json`` unter der Test-Datenwurzel (``app.loader._DATA_ROOT``),
verschraenkte Aufrufe von ``resolve_user_lang`` und ``t``.
"""
from __future__ import annotations

import json

import pytest

import i18n.catalog as catalog
from app import loader
from i18n import resolve_user_lang, t


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    daten = tmp_path / "data"
    for uid, inhalt in (("nutzer-a", {"language": "en"}), ("nutzer-b", {"email": "b@x"})):
        ordner = daten / "users" / uid
        ordner.mkdir(parents=True)
        (ordner / "user.json").write_text(json.dumps(inhalt), encoding="utf-8")
    monkeypatch.setattr(loader, "_DATA_ROOT", str(daten))

    kat = tmp_path / "messages"
    for lang, text in (("de", "Guten Morgen, {name}"), ("en", "Good morning, {name}")):
        (kat / lang).mkdir(parents=True)
        (kat / lang / "allgemein.json").write_text(
            json.dumps({"allgemein.gruss.morgen": text}), encoding="utf-8")
    monkeypatch.setattr(catalog, "MESSAGES_DIR", kat)


def _text(uid: str) -> str:
    return t("allgemein.gruss.morgen", resolve_user_lang(uid), name=uid)


def test_verschraenkt_in_jeder_reihenfolge(umgebung):
    for reihenfolge in (("nutzer-a", "nutzer-b", "nutzer-a"), ("nutzer-b", "nutzer-a", "nutzer-b")):
        for uid in reihenfolge:
            soll = "Good morning, nutzer-a" if uid == "nutzer-a" else "Guten Morgen, nutzer-b"
            assert _text(uid) == soll


def test_sprachen_aufgeloest(umgebung):
    assert resolve_user_lang("nutzer-a") == "en"
    assert resolve_user_lang("nutzer-b") == "de"
    assert resolve_user_lang("nutzer-a") == "en"


def test_unbekannter_nutzer_ist_deutsch_ohne_ausnahme(umgebung):
    assert resolve_user_lang("niemand") == "de"
    assert resolve_user_lang("../nutzer-a") == "de"
    assert _text("niemand") == "Guten Morgen, niemand"
