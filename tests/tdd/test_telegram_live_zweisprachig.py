"""Issue #2681 (A2): Telegram-Antwort in beiden Sprachen (AC-3).

Spec: docs/specs/modules/i18n_a2_e2e_zweisprachig_2681.md

Zwei Schichten:
* Kern (jeder Lauf, kein Netz): ``set_test_user_language``/``test_user_language``
  gegen ein echtes ``user.json`` in ``tmp_path`` -- Read-Modify-Write und das
  Ruecksetzen in ``finally`` auch bei einem Fehler im ``with``-Block.
* Live (Opt-in ``GZ_TELEGRAM_LIVE=1``, Marker ``live``): ``hilfe`` ueber den
  echten Webhook-Eintritt gegen den Test-Chat, erst Englisch, dann Deutsch.
"""
from __future__ import annotations

import json
import os

import pytest

from tests.tdd import _telegram_live_fixture as fx

# #2813: autouse-Fixture per Import registriert -- setzt nach jedem
# real_data_root-Test data/users/tg-live-e2e zurueck (Waechter #2226).
from tests.tdd._telegram_live_fixture import (  # noqa: E402,F401
    tg_live_datenwurzel_zuruecksetzen_autouse,
)

USER_JSON = ("users", fx.TEST_USER_ID, "user.json")


def _profil(data_dir) -> dict:
    # Liest das Nutzer-Profil (Daten, kein Produkt-Quelltext) -- bewusst per
    # json.load statt read_text(): Die Hygiene-Pruefung (#765) wertet ein
    # nicht aufloesbares read_text()-Ziel als Quelltext-Read und erntet dann
    # die Scope-Pfadlisten unten als vermeintliche Dateilisten.
    with data_dir.joinpath(*USER_JSON).open(encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture
def daten(tmp_path):
    pfad = tmp_path.joinpath(*USER_JSON)
    pfad.parent.mkdir(parents=True)
    pfad.write_text(json.dumps({"id": fx.TEST_USER_ID, "telegram_chat_id": "42",
                                "mail_to": ""}), encoding="utf-8")
    return tmp_path


def test_set_language_read_modify_write(daten):
    assert fx.set_test_user_language("en", data_dir=str(daten)) is None
    assert _profil(daten) == {"id": fx.TEST_USER_ID, "telegram_chat_id": "42",
                              "mail_to": "", "language": "en"}
    assert fx.set_test_user_language("de", data_dir=str(daten)) == "en"
    assert fx.set_test_user_language(None, data_dir=str(daten)) == "de"
    assert "language" not in _profil(daten)
    assert _profil(daten)["telegram_chat_id"] == "42"


@pytest.mark.parametrize("vorher", [None, "de", "en"])
def test_kontextmanager_setzt_auch_bei_fehler_zurueck(daten, vorher):
    fx.set_test_user_language(vorher, data_dir=str(daten))
    ziel = "en" if vorher != "en" else "de"
    with pytest.raises(RuntimeError):
        with fx.test_user_language(ziel, data_dir=str(daten)):
            assert _profil(daten)["language"] == ziel
            raise RuntimeError("absichtlich im with-Block")
    assert _profil(daten).get("language") == vorher


def test_katalogaenderung_zaehlt_als_telegram_scope():
    """Telegram-Texte kommen aus den Katalogen: eine Aenderung unter src/i18n/
    verlangt den Telegram-Live-Lauf (SKIPPED zaehlt nicht als gruen)."""
    import importlib.util
    from pathlib import Path

    hook = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "e2e_telegram_live.py"
    spec = importlib.util.spec_from_file_location("e2e_telegram_live_2681", hook)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod._scope_touches_telegram(["src/i18n/messages/en/inbound.json"]) is True
    assert mod._scope_touches_telegram(["src/i18n/lang.py"]) is True
    assert mod._scope_touches_telegram(["docs/reference/i18n_konventionen.md"]) is False
    assert mod.gate(mod._scope_touches_telegram(["src/i18n/catalog.py"]), {}) == 1


@pytest.mark.live
@pytest.mark.real_data_root
@pytest.mark.timeout(120)
@pytest.mark.skipif(not fx.live_telegram_enabled(),
                    reason="GZ_TELEGRAM_LIVE=1 nicht gesetzt — Live-Sends nur opt-in (#1014)")
def test_hilfe_englisch_dann_deutsch_live():
    from app.metric_catalog import get_all_metrics
    from services.trip_command_processor import _COMMAND_SPECS

    chat_id = os.environ["GZ_TELEGRAM_TEST_CHAT_ID"]
    fx.ensure_test_user_with_active_trip(chat_id=chat_id)
    from pathlib import Path

    vorher = _profil(Path("data")).get("language")
    with fx.test_user_language("en"):
        body_en = fx.run_command_through_pipeline(command="hilfe", chat_id=chat_id)
    body_de = fx.run_command_through_pipeline(command="hilfe", chat_id=chat_id)

    assert "Available commands" in body_en, body_en[:200]
    fehlend = [s.wort_en for s in _COMMAND_SPECS if s.wort_en.upper() not in body_en.upper()]
    assert not fehlend, f"englische Befehlswoerter fehlen: {fehlend}"
    assert "Verfügbare Befehle" in body_de, body_de[:200]
    kuerzel = [m.col_label for m in get_all_metrics()]
    assert [k for k in kuerzel if k in body_en] == [k for k in kuerzel if k in body_de]
    assert _profil(Path("data")).get("language") == vorher, "Sprache wieder wie vor dem Test"
