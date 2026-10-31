"""Issue #2646 (i18n S1) -- der Loader uebernimmt die Nutzersprache.

Spec: docs/specs/modules/i18n_s1_sprachfeld_nutzer_2646.md (AC-7).

``load_user_from_dict`` leitet ``preferences.language`` aus dem Top-Level-Feld
``language`` (von Go geschrieben) ab, ersatzweise aus
``preferences.language``, sonst ``de``; unbekannte Werte werden ``de``.
"""
import pytest

from app.loader import load_user_from_dict


@pytest.mark.parametrize(
    ("daten", "erwartet"),
    [
        ({"id": "anna", "email": "anna@example.com", "language": "en"}, "en"),
        ({"id": "anna", "email": "anna@example.com", "language": "en", "preferences": {"language": "de"}}, "en"),
        ({"id": "bert", "email": "bert@example.com", "preferences": {"language": "en"}}, "en"),
        ({"id": "carl", "email": "carl@example.com"}, "de"),
        ({"id": "dora", "email": "dora@example.com", "language": "fr"}, "de"),
        ({"id": "emil", "email": "emil@example.com", "preferences": {"language": "fr"}}, "de"),
        ({"user": {"id": "fred", "email": "fred@example.com", "language": "en"}}, "en"),
    ],
)
def test_ac7_sprache_aus_top_level_dann_preferences_sonst_de(daten: dict, erwartet: str) -> None:
    assert load_user_from_dict(daten).preferences.language == erwartet
