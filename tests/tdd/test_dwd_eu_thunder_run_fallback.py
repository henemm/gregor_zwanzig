"""TDD RED — #1457 S2c AC-7: Rueckfall auf aeltere ICON-EU-Laeufe.

Spec: docs/specs/modules/feat_1457_s2c_icon_eu_luekenfueller.md (AC-7)

Vermessung und Testart: siehe Modul-Docstring von
`tests/tdd/_dwd_eu_fixtures.py` (Punkt 7: ICON-EU veroeffentlicht einen Lauf
erst 3,6-4,5 h nach seinem Zeitpunkt — deutlich spaeter als ICON-D2 mit ~1,4 h;
gemessen am 2026-08-04 07:32 UTC war der 03Z-Lauf da, der 06Z-Lauf nicht).

RED-GRUND: `providers.dwd_eu` existiert nicht -> ModuleNotFoundError.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from tests.tdd._dwd_eu_fixtures import ABRUZZEN, dwd_eu, eu_server  # noqa: E402

# Gemessene Veroeffentlichungs-Verzoegerung (Punkt 7). Der gewaehlte Lauf muss
# mindestens so alt sein, sonst laeuft im Regelbetrieb JEDER Abruf in 404 —
# exakt der S2a-Fehler, den 24 gruene Tests nicht gefangen haben.
_GEMESSENE_VERZOEGERUNG_H = 4.5


def _fenster(stunden: int = 3):
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return start, start + timedelta(hours=stunden)


def test_ac7_404_auf_dem_gewaehlten_lauf_faellt_auf_einen_aelteren_zurueck(monkeypatch):
    """AC-7: Given der vom Code gewaehlte ICON-EU-Lauf antwortet mit 404 (noch
    nicht veroeffentlicht), When die Signale geholt werden, Then wird ein
    aelterer Lauf angefragt und liefert Werte.
    """
    kandidaten = dwd_eu()._thunder_run_candidates(datetime.now(timezone.utc))
    assert len(kandidaten) >= 2, (
        f"Erwartet: gewaehlter Lauf plus mindestens eine Rueckfallstufe, "
        f"bekommen {kandidaten}"
    )
    primaer = kandidaten[0].strftime("%Y%m%d%H")
    rueckfall = kandidaten[1].strftime("%Y%m%d%H")

    start, ende = _fenster()
    with eu_server(monkeypatch, status_je_lauf={primaer: 404}) as srv:
        ergebnis = dwd_eu().DwdEuDirectProvider().fetch_thunder_signals_named(
            ABRUZZEN, start, ende
        )
        versucht = {lauf for lauf, _ttt in srv.abrufe}

    assert primaer in versucht, "Der gewaehlte Lauf wurde gar nicht erst versucht"
    assert rueckfall in versucht, (
        f"Der naechstaeltere Lauf ({rueckfall}) wurde nie angefragt — kein "
        f"Rueckfall. Angefragt: {sorted(versucht)}"
    )
    werte = [w for reihe in ergebnis.values() for w in reihe.values() if w is not None]
    assert werte, "Kein Wert angekommen — der Rueckfall greift nicht"


def test_ac7_nullpunkt_bleibt_am_zeitfenster_nicht_am_rueckfall_lauf(monkeypatch):
    """AC-7, zweite Haelfte: Given den Rueckfall auf einen aelteren Lauf, When
    die Signale fuer ein Zeitfenster geholt werden, Then bezeichnen die
    zurueckgegebenen Stunden-Offsets weiterhin `start + Offset` — die
    angefragten Zeitschritte des aelteren Laufs sind entsprechend groesser.

    Ohne diese Zusage verschoeben sich beim Rueckfall alle Werte um die
    Lauf-Differenz; das Gewitter stuende Stunden zu frueh in der Vorhersage,
    und genau diese Verschiebung sieht man einer Vorhersage nicht an.
    """
    kandidaten = dwd_eu()._thunder_run_candidates(datetime.now(timezone.utc))
    primaer, rueckfall_lauf = kandidaten[0], kandidaten[1]
    start, ende = _fenster()

    with eu_server(
        monkeypatch, status_je_lauf={primaer.strftime("%Y%m%d%H"): 404}
    ) as srv:
        ergebnis = dwd_eu().DwdEuDirectProvider().fetch_thunder_signals_named(
            ABRUZZEN, start, ende
        )
        rueckfall_str = rueckfall_lauf.strftime("%Y%m%d%H")
        zeitschritte = sorted({ttt for lauf, ttt in srv.abrufe if lauf == rueckfall_str})

    assert zeitschritte, "Der Rueckfall-Lauf wurde nie angefragt"
    geholte_zeiten = {
        rueckfall_lauf.replace(tzinfo=timezone.utc) + timedelta(hours=t)
        for t in zeitschritte
    }
    reihe = next(iter(ergebnis.values()))
    erwartete_zeiten = {start + timedelta(hours=o) for o in sorted(reihe)}
    assert erwartete_zeiten <= geholte_zeiten, (
        f"Die zurueckgegebenen Offsets zeigen auf {sorted(erwartete_zeiten)}, "
        f"geholt wurden aber {sorted(geholte_zeiten)} — beim Rueckfall wurde "
        "der Nullpunkt mitverschoben, die Werte stehen an der falschen Stunde"
    )


def test_ac7_der_sicherheitsabstand_deckt_die_gemessene_verzoegerung_ab():
    """AC-7, Voraussetzung: Given die gemessene ICON-EU-Veroeffentlichungs-
    Verzoegerung von 3,6-4,5 h, When der Code zu einer beliebigen Tageszeit
    seinen Lauf waehlt, Then liegt dieser mindestens 4,5 h zurueck.

    Der Sicherheitsabstand von ICON-D2 (3 h) reicht hier NICHT: er trifft im
    unguenstigsten Fall einen Lauf, den der DWD noch gar nicht veroeffentlicht
    hat. Der Rueckfall federt das zwar ab, wuerde aber im Regelbetrieb bei
    JEDEM Abruf zusaetzliche 404-Runden kosten. Geprueft wird ueber den ganzen
    Tag, weil der Abstand mit der Stunde schwankt (Laeufe alle 3 h).
    """
    schlechteste = None
    for stunde in range(24):
        for minute in (5, 59):
            jetzt = datetime.now(timezone.utc).replace(
                hour=stunde, minute=minute, second=0, microsecond=0
            )
            gewaehlt = dwd_eu()._thunder_run_candidates(jetzt)[0]
            alter_h = (jetzt - gewaehlt).total_seconds() / 3600.0
            if schlechteste is None or alter_h < schlechteste[0]:
                schlechteste = (alter_h, jetzt, gewaehlt)

    alter_h, jetzt, gewaehlt = schlechteste
    assert alter_h >= _GEMESSENE_VERZOEGERUNG_H, (
        f"Um {jetzt:%H:%M} UTC waehlt der Code den Lauf {gewaehlt:%Y-%m-%d %H}Z "
        f"— nur {alter_h:.1f} h alt. Gemessen braucht ICON-EU bis zu "
        f"{_GEMESSENE_VERZOEGERUNG_H} h bis zur Veroeffentlichung; dieser Lauf "
        "existiert dann noch nicht und jeder Abruf laeuft in 404"
    )
