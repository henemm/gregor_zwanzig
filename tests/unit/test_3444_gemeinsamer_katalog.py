"""Gemeinsamer Textkatalog Go/Python, Bereich ``geteilt`` (#3444, ADR-0130).

Spec: docs/specs/modules/feat_3444_gemeinsamer_katalog.md (AC-2, AC-4, AC-5, AC-7)
Echte Katalogordner (Kopie des echten Baums mit geaendertem Text), kein Mock.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import i18n.catalog as catalog
from services.send_outcomes import error_body

ROOT = Path(__file__).resolve().parents[2]
MESSAGES = ROOT / "src" / "i18n" / "messages"
SCHLUESSEL = "geteilt.fehler.kind_required"
FIXTURE = ROOT / "tests" / "fixtures" / "send_detail_parity" / "faelle.json"


def _json(pfad: Path) -> dict:
    return json.loads(pfad.read_text(encoding="utf-8"))


def test_ac4_python_katalog_hat_nur_den_neuen_schluessel():
    texte = catalog.get_catalog().texte
    for lang in ("de", "en"):
        assert SCHLUESSEL in texte[lang]
        assert "versand.ergebnis.kind_required" not in texte[lang]
    assert texte["de"][SCHLUESSEL] == _json(FIXTURE)["kind_required"]


def test_ac4_error_body_liefert_fixture_wortlaut_de():
    status, body = error_body("kind_required", lang="de")
    assert status == 400 and body["code"] == "kind_required"
    assert body["detail"] == _json(FIXTURE)["kind_required"]


def test_ac5_bereich_geteilt_in_python_und_paritaet():
    assert "geteilt" in catalog.BEREICHE
    de, en = _json(MESSAGES / "de" / "geteilt.json"), _json(MESSAGES / "en" / "geteilt.json")
    assert set(de) == set(en) and SCHLUESSEL in de
    assert all(k.startswith("geteilt.") for k in de)
    assert catalog.parity_errors(MESSAGES) == []


@pytest.mark.parametrize("lang", ["de", "en"])
def test_ac2_geaenderter_text_in_geteilt_json_kommt_im_fehlerkoerper(tmp_path, monkeypatch, lang):
    kopie = tmp_path / "messages"
    shutil.copytree(MESSAGES, kopie)
    datei = kopie / lang / "geteilt.json"
    daten = _json(datei)
    daten[SCHLUESSEL] = f"GEAENDERT-{lang}"
    datei.write_text(json.dumps(daten), encoding="utf-8")
    monkeypatch.setattr(catalog, "MESSAGES_DIR", kopie)  # Konfiguration, kein Mock
    _, body = error_body("kind_required", lang=lang)
    assert body["detail"] == f"GEAENDERT-{lang}"


def test_ac7_adr_0130_und_doku():  # doc-compliance-test
    assert len(list((ROOT / "docs" / "adr").glob("0130-*.md"))) == 1
    adr104 = next((ROOT / "docs" / "adr").glob("0104-*.md")).read_text(encoding="utf-8")
    assert "ADR-0130" in adr104
    konv = (ROOT / "docs" / "reference" / "i18n_konventionen.md").read_text(encoding="utf-8")
    assert "geteilt" in konv and "src/i18n/messages" in konv
