"""Mail-Validatoren und der eine 3-Tages-Ausblick (Issue #3155, Scheibe B4).

SPEC: docs/specs/modules/feat_3155_ein_name_ausblick.md (AC-12, Entscheidungen
1, 5, 6).

Kern-Schicht, ohne Netz: die Mails entstehen aus der echten Kette (Helfer aus
``test_einstellung_gleich_mail_validatoren``: Trip ueber Loader und
``send_trip_report``, Orte ueber ``send_one_compare_preset``), die Validatoren
laufen als Prozess mit ``--eml`` und ``--konfig``. Negative Mails entstehen durch
gezielte Textaenderung der positiven bzw. durch eine Konfiguration, die den
Ausblick in einem anderen Briefing einstellt als dem der Mail. Kein Mock.
"""
from __future__ import annotations

import copy

import pytest

from tests.tdd.test_einstellung_gleich_mail_validatoren import (
    ORTE, TRIP, _TRIP_FOLGE, _aendere, _konfig, _lauf, _orte_eml, _orte_konfig, _orte_preset,
    _trip_daten, _trip_eml,
)

#: Fruehere Blocknamen je Sprache (Klartext-Titel, HTML-Eyebrow) vor B4.
_ALT_TRIP = {"de": ("Nächste Etappen", "Ausblick · nächste 3 Tage"),
             "en": ("Next stages", "Outlook · next 3 days")}
_ALT_ORTE = {"de": ("Ausblick", "AUSBLICK"), "en": ("Outlook", "OUTLOOK")}


def _name(lang: str) -> str:
    from i18n import t

    return t("mail.ausblick.name", lang)


def _mit_reports(daten: dict, reports: list[str]) -> dict:
    """Ausblick in den Briefings ``reports``. #3237: allein die Tabelle
    (``placements.outlook_reports``) steuert; ``multi_day_trend_reports``
    bleibt als Beschreibung stehen und wirkt nicht."""
    from tests.helpers.tabelle_aus_wunsch import tabelle

    neu = copy.deepcopy(daten)
    neu["report_config"]["multi_day_trend_reports"] = reports
    dc = neu["display_config"]
    dc["placements"] = tabelle(copy.deepcopy(dc), "trip", outlook_reports=reports)
    return neu


# --------------------------------------------------------------------------- #
# Trip (briefing_mail_validator)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("lang", ["de", "en"])
def test_trip_ausblick_name_alter_name_scheitert(monkeypatch, tmp_path, lang):
    """AC-12: der Block heisst "3-Tages-Ausblick"/"3-day outlook"; mit dem alten
    Namen (Klartext-Titel, HTML-Eyebrow) scheitert dieselbe Mail mit Namen."""
    daten = _mit_reports(_trip_daten(_TRIP_FOLGE), ["evening"])
    eml, konfig = _trip_eml(monkeypatch, daten, lang=lang), _konfig(tmp_path, "trip", daten)
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", konfig)
    assert code == 0, aus
    alt_plain, alt_html = _ALT_TRIP[lang]
    name = _name(lang)
    falsch = _aendere(eml, plain=lambda p: p.replace(name, alt_plain),
                      html=lambda h: h.replace(f">{name}<", f">{alt_html}<"))
    code, aus = _lauf(tmp_path, TRIP, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert f"SOLL: Ausblick-Block (Klartext) heisst '{alt_plain}' statt '{name}'" in aus, aus
    assert f"SOLL: Ausblick-Block (HTML) heisst '{alt_html}' statt '{name}'" in aus, aus


def test_trip_ausblick_im_falschen_briefing_scheitert(monkeypatch, tmp_path):
    """AC-12: Abend-Mail mit Ausblick gegen eine Konfiguration, die ihn nur im
    Morgen-Briefing einstellt -> scheitert und nennt beide Briefings."""
    daten = _mit_reports(_trip_daten(_TRIP_FOLGE), ["evening"])
    eml = _trip_eml(monkeypatch, daten)
    nur_morgen = _konfig(tmp_path, "morgen", _mit_reports(daten, ["morning"]))
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", nur_morgen)
    assert code == 1, aus
    assert ("SOLL: Ausblick (HTML) erscheint im Abend-Briefing, laut Konfiguration steht er "
            "nur im Morgen-Briefing") in aus, aus
    beide = _konfig(tmp_path, "beide", _mit_reports(daten, ["morning", "evening"]))
    assert _lauf(tmp_path, TRIP, eml, "--konfig", beide)[0] == 0


def test_trip_ausblick_fehlt_obwohl_eingestellt_scheitert(monkeypatch, tmp_path):
    """AC-12: Abend-Mail ohne Ausblick-Titel, obwohl er abends eingestellt ist."""
    daten = _mit_reports(_trip_daten(_TRIP_FOLGE), ["evening"])
    eml = _trip_eml(monkeypatch, daten)
    falsch = _aendere(eml, plain=lambda p: p.replace(_name("de"), "Irgendwas"))
    code, aus = _lauf(tmp_path, TRIP, falsch, "--konfig", _konfig(tmp_path, "t", daten))
    assert code == 1, aus
    assert ("SOLL: Ausblick-Block (Klartext) fehlt (kein Titel '3-Tages-Ausblick'), laut "
            "Konfiguration steht er im Abend-Briefing") in aus, aus


def test_trip_tabelle_outlook_reports_steuert(monkeypatch, tmp_path):
    """AC-12, Tabelle: ``placements.outlook_reports`` ist die eine Stelle --
    ``["morning"]`` laesst die Abend-Mail mit Ausblick scheitern, obwohl die
    Altfelder (``multi_day_trend_reports``) Abend sagen."""
    daten = _mit_reports(_trip_daten(_TRIP_FOLGE), ["evening"])
    eml = _trip_eml(monkeypatch, daten)
    tabelle = copy.deepcopy(daten)
    tabelle["display_config"]["placements"] = {"version": 1, "rows": [
        {"metric_id": m, "places": {"outlook": True}} for m in ("wind", "temperature", "precipitation")
    ], "outlook_reports": ["morning"]}
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", _konfig(tmp_path, "tab", tabelle))
    assert code == 1, aus
    assert "erscheint im Abend-Briefing, laut Konfiguration steht er nur im Morgen-Briefing" in aus, aus


@pytest.mark.parametrize("lang", ["de", "en"])
def test_trip_kompakt_name_ascii_alter_name_scheitert(monkeypatch, tmp_path, lang):
    """AC-12, Kompakt: Titel in ASCII-Schreibweise; alter Name scheitert."""
    daten = _mit_reports(_trip_daten(_TRIP_FOLGE, email_format="compact"), ["evening"])
    eml, konfig = _trip_eml(monkeypatch, daten, lang=lang), _konfig(tmp_path, "k", daten)
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig", konfig)
    assert code == 0, aus
    alt = {"de": "Naechste Etappen", "en": "Next stages"}[lang]
    falsch = _aendere(eml, plain=lambda p: p.replace(_name(lang), alt))
    code, aus = _lauf(tmp_path, TRIP, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert f"SOLL: Ausblick-Block (Kompakt) heisst '{alt}' statt '{_name(lang)}'" in aus, aus


def test_trip_kompakt_ausblick_im_falschen_briefing_scheitert(monkeypatch, tmp_path):
    daten = _mit_reports(_trip_daten(_TRIP_FOLGE, email_format="compact"), ["evening"])
    eml = _trip_eml(monkeypatch, daten)
    code, aus = _lauf(tmp_path, TRIP, eml, "--konfig",
                      _konfig(tmp_path, "km", _mit_reports(daten, ["morning"])))
    assert code == 1, aus
    assert ("SOLL: Ausblick (Kompakt) erscheint im Abend-Briefing, laut Konfiguration steht er "
            "nur im Morgen-Briefing") in aus, aus


# --------------------------------------------------------------------------- #
# Orte (email_spec_validator)
# --------------------------------------------------------------------------- #
def _mit_marke(preset: dict, reports: list[str], **slots) -> dict:
    neu = copy.deepcopy(preset)
    neu["display_config"]["placements"] = {"version": 1, "outlook_reports": reports}
    neu.update(slots)
    return neu


@pytest.mark.parametrize("lang", ["de", "en"])
def test_orte_ausblick_name_alter_name_scheitert(monkeypatch, tmp_path, lang):
    preset = _orte_preset()
    eml, konfig = _orte_eml(monkeypatch, preset, lang=lang), _orte_konfig(tmp_path, preset)
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", konfig)
    assert code == 0, aus
    alt_plain, alt_html = _ALT_ORTE[lang]
    name = _name(lang)
    falsch = _aendere(eml, plain=lambda p: p.replace(f"\n{name}\n", f"\n{alt_plain}\n"),
                      html=lambda h: h.replace(f">{name}<", f">{alt_html}<"))
    code, aus = _lauf(tmp_path, ORTE, falsch, "--konfig", konfig)
    assert code == 1, aus
    assert f"SOLL: Ausblick-Block (Klartext) heisst '{alt_plain}' statt '{name}'" in aus, aus
    assert f"SOLL: Ausblick-Block (HTML) heisst '{alt_html}' statt '{name}'" in aus, aus


def test_orte_ausblick_im_falschen_briefing_scheitert(monkeypatch, tmp_path):
    """AC-12: Morgen-Mail (nur Morgen-Slot) mit Ausblick gegen die Anlage-Marke
    ``outlook_reports: ["evening"]`` -> scheitert; mit ``["morning"]`` gruen."""
    preset = _orte_preset()
    eml = _orte_eml(monkeypatch, preset)
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig",
                      _orte_konfig(tmp_path, _mit_marke(preset, ["evening"]), "abend"))
    assert code == 1, aus
    assert ("SOLL: Ausblick (HTML) erscheint im Morgen-Briefing, laut Konfiguration steht er "
            "nur im Abend-Briefing") in aus, aus
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig",
                      _orte_konfig(tmp_path, _mit_marke(preset, ["morning"]), "morgen"))
    assert code == 0, aus


def test_orte_briefing_argument_und_zieltag(monkeypatch, tmp_path):
    """``--briefing``: beide Slots an, Ausblick nur morgens. Die Morgen-Mail
    (Zieltag = Erstellungstag) besteht ohne Angabe; als Abend-Briefing
    ausgewiesen scheitert sie."""
    preset = _orte_preset()
    preset["evening_enabled"] = True
    # #3237: ohne Tabelle gilt die Vorbelegung (beide Slots an -> nur abends,
    # ADR-0124 Nr. 3); "Ausblick nur morgens" steht deshalb in der Tabelle --
    # dieselbe Einstellung fuer Versand und Soll.
    morgens = _mit_marke(preset, ["morning"])
    eml = _orte_eml(monkeypatch, morgens, versatz=0)
    konfig = _orte_konfig(tmp_path, morgens, "beide")
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", konfig)
    assert code == 0, aus
    code, aus = _lauf(tmp_path, ORTE, eml, "--konfig", konfig, "--briefing", "evening")
    assert code == 1, aus
    assert "erscheint im Abend-Briefing, laut Konfiguration steht er nur im Morgen-Briefing" in aus, aus


def test_orte_briefing_ohne_konfig_abgelehnt(monkeypatch, tmp_path):
    eml = _orte_eml(monkeypatch, _orte_preset())
    code, aus = _lauf(tmp_path, ORTE, eml, "--briefing", "morning")
    assert code == 2 and "--briefing nur zusammen mit --konfig" in aus, aus
