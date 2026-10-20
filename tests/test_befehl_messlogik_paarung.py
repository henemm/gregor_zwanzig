"""Kern: Paarung HEUTE->HELP und Erkennung kalter Laeufe (#2439, AC-13, AC-14 letzter Satz, AC-15).

Spec: docs/specs/modules/feat_2439_push_eingang_prod_scharf.md

Fixture ``staging_journal_2026-10-19.log`` ist ein echter Mitschnitt des Staging-Journals
(``journalctl -u gregor-python-staging -o short-iso-precise``, 19.10. 07:39-08:01 UTC, nur
``befehl=``- und ``*_fenster``-Zeilen). In genau diesem Lauf entstand der Fehlwert 813 s:
das HEUTE um 07:45:54,8 wurde mit dem naechsten E-Mail-HELP um 07:59:28,4 gepaart, obwohl
dazwischen neun andere Befehle lagen.

Vertrag an ``.claude/tools/befehl_messlogik.py`` (neu, kein Netz):
  lese_journal(zeilen)                       -> [(datetime UTC, text)]
  dauerzeilen(journal)                       -> [{"ts","befehl","kanal","trip","ms"}]
  paare_heute_help(laeufe, kanaele, max_abstand_s) -> [(heute, help)]
  kalt_laeufe(laeufe, fenster_zeilen, quellen=("dwd_fenster", "fr_direct_fenster")) -> [lauf]
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_FIXTURE = _REPO / "tests" / "fixtures" / "befehl_antwortzeit" / "staging_journal_2026-10-19.log"
EMAIL = {"email"}


def _messlogik():
    pfad = _REPO / ".claude" / "tools" / "befehl_messlogik.py"
    spec = importlib.util.spec_from_file_location("befehl_messlogik", pfad)
    assert spec and pfad.is_file(), f"{pfad} fehlt"
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _utc(text: str) -> datetime:
    return datetime.fromisoformat(f"2026-10-19T{text}+00:00").astimezone(timezone.utc)


def _journal(ml):
    return ml.lese_journal(_FIXTURE.read_text(encoding="utf-8").splitlines())


def _laeufe(ml):
    return sorted(ml.dauerzeilen(_journal(ml)), key=lambda l: l["ts"])


def _zeiten(paare):
    return [(h["ts"].strftime("%H:%M:%S.%f")[:12], p["ts"].strftime("%H:%M:%S.%f")[:12])
            for h, p in paare]


def test_dauerzeilen_werden_aus_dem_echten_journal_gelesen():
    ml = _messlogik()
    laeufe = _laeufe(ml)
    assert len(laeufe) == 77, f"{len(laeufe)} Dauer-Zeilen statt 77 im Mitschnitt"
    heute = laeufe[1]
    assert heute["befehl"] == "HEUTE" and heute["kanal"] == "email"
    assert heute["ms"] == 28378 and heute["ts"] == _utc("07:39:52.639774")
    assert heute["trip"] == "gzp-190739-bdf13e21-a"
    assert heute["ts"].tzinfo is not None
    # Phasen-Zeilen (`befehl_dauer: phase=... dauer_ms=`) sind keine Befehle
    assert all(l["befehl"].isupper() for l in laeufe)


def test_ac13_nur_gueltige_paare_aus_dem_echten_lauf():
    """Drei echte Paare (HELP direkt nach HEUTE, gleicher Eingang, kein Zwischenbefehl);
    HEUTE ohne Partner im Fenster und HEUTE mit Zwischenbefehl werden uebersprungen."""
    ml = _messlogik()
    paare = ml.paare_heute_help(_laeufe(ml), EMAIL, 180)
    assert _zeiten(paare) == [
        ("07:45:26.805", "07:45:27.442"),
        ("07:59:26.340", "07:59:28.405"),
        ("07:59:46.355", "07:59:46.885"),
    ]


def test_ac13_der_fehlwert_813_sekunden_entsteht_nicht_mehr():
    """Auch mit sehr grossem Fenster wird das HEUTE von 07:45:54 nicht mit dem HELP von
    07:59:28 gepaart -- dazwischen liegen andere Befehle desselben Eingangs."""
    ml = _messlogik()
    paare = ml.paare_heute_help(_laeufe(ml), EMAIL, 3600)
    for heute, help_ in paare:
        abstand = (help_["ts"] - heute["ts"]).total_seconds()
        assert abstand < 300, f"absurdes Paar {_zeiten([(heute, help_)])}: {abstand:.1f} s"
    assert not any(_utc("07:45:50") <= h["ts"] <= _utc("07:58:00") for h, _ in paare)


def test_ac13_paar_jenseits_der_pruefgrenze_bleibt_sichtbar():
    """Das Fenster ist NICHT an die 90-s-Pruefgrenze gebunden: ein HELP 211 s nach
    HEUTE-Start ohne Zwischenbefehl wird gepaart, damit der Live-Test den Verstoss sieht
    (sonst wuerde ein echter Verstoss still zu 'nicht messbar')."""
    ml = _messlogik()
    paare = ml.paare_heute_help(_laeufe(ml), EMAIL, 240)
    assert _zeiten(paare)[0] == ("07:39:52.639", "07:42:55.291")
    assert len(paare) == 4


def test_ac13_folge_ohne_gueltiges_paar_ist_nicht_messbar():
    ml = _messlogik()
    anfang = [l for l in _laeufe(ml) if l["ts"] <= _utc("07:43:07")]
    assert [l["befehl"] for l in anfang[:2]] == ["STATUS", "HEUTE"] and len(anfang) == 12
    assert ml.paare_heute_help(anfang, EMAIL, 180) == []


def test_ac13_anderer_eingang_wird_nicht_gepaart():
    ml = _messlogik()
    assert ml.paare_heute_help(_laeufe(ml), {"telegram"}, 3600) == []


# ---------------------------------------------------------------------------
# AC-15 / AC-14 (letzter Satz): kalte Laeufe ueber DWD- ODER fr_direct-Fensterzeile
# ---------------------------------------------------------------------------

# Die fr_direct-Zeile gibt es erst nach dieser Spec; sie steht hier im kuenftigen
# Format (Spec Abschnitt 5) -- alles andere ist echter Mitschnitt.
_FR_KALT = (_utc("07:59:58.100000"),
            "uv[1]: 2026-10-19 07:59:58,100 INFO providers.meteofrance: "
            "fr_direct_fenster fenster_s=6.41 downloads=24 cache_treffer=0")
_FR_WARM = (_utc("08:00:18.500000"),
            "uv[1]: 2026-10-19 08:00:18,500 INFO providers.meteofrance: "
            "fr_direct_fenster fenster_s=0.02 downloads=0 cache_treffer=24")


def _korsika(laeufe):
    return [l for l in laeufe if l["trip"].endswith("korsika")]


def test_ac15_korsika_heute_ohne_fr_direct_zeile_gilt_nicht_als_kalt():
    ml = _messlogik()
    laeufe = _laeufe(ml)
    assert ml.kalt_laeufe(_korsika(laeufe), _journal(ml)) == []


def test_ac15_nur_der_korsika_lauf_mit_downloads_gilt_als_kalt():
    ml = _messlogik()
    laeufe = _laeufe(ml)
    zeilen = sorted(_journal(ml) + [_FR_KALT, _FR_WARM])
    kalt = ml.kalt_laeufe(_korsika(laeufe), zeilen)
    assert [(l["befehl"], l["ms"]) for l in kalt] == [("HEUTE", 26343)]


def test_ac15_de_laeufe_werden_ueber_die_dwd_zeile_als_kalt_erkannt():
    ml = _messlogik()
    de = [l for l in _laeufe(ml) if "-deh" in l["trip"] or "-dem" in l["trip"]]
    assert len(de) == 10
    kalt = ml.kalt_laeufe(de, _journal(ml), quellen=("dwd_fenster",))
    assert len(kalt) == 10, [(l["trip"], l["ms"]) for l in de if l not in kalt]
    warm = [l for l in _laeufe(ml) if l["ts"] == _utc("07:45:26.805554")]
    assert ml.kalt_laeufe(warm, _journal(ml), quellen=("dwd_fenster",)) == []


def test_ac14_fr_direct_zeile_zaehlt_bei_reiner_dwd_auswertung_nicht():
    """Die heutige Live-Regel (`fenster_s=... downloads=...` ohne Praefix) wuerde die
    Korsika-Zeile als DWD-Download werten. Die DWD-Auswertung muss am Praefix haengen."""
    ml = _messlogik()
    korsika = _korsika(_laeufe(ml))
    zeilen = sorted(_journal(ml) + [_FR_KALT])
    assert ml.kalt_laeufe(korsika, zeilen, quellen=("dwd_fenster",)) == []
    assert len(ml.kalt_laeufe(korsika, zeilen, quellen=("fr_direct_fenster",))) == 1


def test_ac15_lauf_ausserhalb_des_fensters_wird_nicht_kalt():
    """Die Fensterzeile muss im Befehlsfenster [ts - dauer, ts] liegen, nicht irgendwo."""
    ml = _messlogik()
    korsika = _korsika(_laeufe(ml))
    spaet = (_FR_KALT[0] + timedelta(minutes=10), _FR_KALT[1])
    assert ml.kalt_laeufe(korsika, sorted(_journal(ml) + [spaet])) == []


# ---------------------------------------------------------------------------
# Fix-Loop 1 (Adversary F001/F005): Fensterbezug und Randwert der Paarung
# ---------------------------------------------------------------------------

def _dauer_journal(ml, *zeilen):
    """Dauer-Zeilen im echten Journalformat (wie im Mitschnitt, UTC)."""
    return ml.dauerzeilen(ml.lese_journal([
        f"2026-10-19T{ts}+00:00 Rennwienix uv[1]: x INFO befehl_dauer: befehl={b} "
        f"kanal=email trip=t dauer_ms={ms}" for ts, b, ms in zeilen]))


def test_f001_fenster_zaehlt_ab_heute_start_nicht_ab_heute_ende():
    """HEUTE dauerte 100 s und endete 09:00:00; das HELP kam 30 s nach dem HEUTE-ENDE, also
    130 s nach dem HEUTE-START. Mit Fenster 60 s ist das KEIN Paar; Ende-Bezug waere 30 s."""
    ml = _messlogik()
    laeufe = _dauer_journal(ml, ("09:00:00.000000", "HEUTE", 100_000),
                            ("09:00:30.000000", "HELP", 200))
    assert ml.paare_heute_help(laeufe, EMAIL, 60) == []
    assert len(ml.paare_heute_help(laeufe, EMAIL, 130)) == 1


def test_f005_randwert_des_fensters_gehoert_noch_dazu():
    """HELP genau `max_abstand_s` (60,000 s) nach dem HEUTE-Start: noch gepaart."""
    ml = _messlogik()
    laeufe = _dauer_journal(ml, ("09:00:10.000000", "HEUTE", 10_000),
                            ("09:01:00.000000", "HELP", 200))
    assert len(ml.paare_heute_help(laeufe, EMAIL, 60)) == 1
    assert ml.paare_heute_help(laeufe, EMAIL, 59.9) == []


@pytest.mark.parametrize("quellen", [("dwd_fenster", "fr_direct_fenster")])
def test_ac15_standardquellen_umfassen_beide_provider(quellen):
    ml = _messlogik()
    korsika = _korsika(_laeufe(ml))
    zeilen = sorted(_journal(ml) + [_FR_KALT])
    assert ml.kalt_laeufe(korsika, zeilen) == ml.kalt_laeufe(korsika, zeilen, quellen=quellen)
