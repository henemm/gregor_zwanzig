"""Kern: Kaltheit je Lauf, Trip-Filter und Zielgroessen-Pruefung des Prod-Lese-Werkzeugs
`befehl_antwortzeit.py` (#2439, Delta-Spec feat_2439_prod_antwortzeit_nachweis, AC-2..AC-6).

Fixture ``tests/fixtures/befehl_antwortzeit/prod_korsika_kalt_laeufe.log``: Journalzeilen im
echten Format ``journalctl -o short-iso-precise`` (Dauer-Zeilen ``befehl_dauer`` und
Fensterzeilen ``fr_direct_fenster``/``dwd_fenster``). Die Werte sind fuer die Grenzfaelle
gesetzt (Format wie im Prod-Journal, Inhalt konstruiert -- wie ``prod_dauerzeilen_2026-09.log``).
Trips in der Fixture:
  kors-gut   HEUTE 3 kalte (40/50/30 s), MORGEN 3 kalte (35/41/44 s) -> bestanden; dazu ein
             warmer 90-s-Lauf (downloads=0), ein Lauf mit Download VOR dem Befehlsfenster
             und ein HELP (80 s, kalt) -- keiner davon zaehlt.
  kors-lahm  HEUTE 40/61/30 s kalt -> verfehlt (61 000 ms >= 60 000 ms)
  kors-duenn HEUTE nur 2 kalte (+1 warmer) -> nicht belegt
  fremd-70   HEUTE 70 s kalt (Fremd-Trip, darf kors-gut nie rot machen)
  de-1       MORGEN 20 s mit ``dwd_fenster`` -> Quelle dwd (nie fr_direct)

Vertrag an ``.claude/tools/befehl_antwortzeit.py`` (SCHNITTSTELLE FUER /50-implement):
  Konstanten: GRENZE_MIT_WETTER_MS=60_000, GRENZE_MEDIAN_MS=45_000, MIN_LAEUFE_KORSIKA=3,
              MIN_LAEUFE_WETTER=5
  kaltheit_je_lauf(dauerzeilen, journal, trip=None) -> [lauf + {"quelle": "fr_direct"|"dwd"|"warm"}]
      journal = ml.lese_journal(...); trip filtert auf diese Trip-ID.
  pruefe_ziel(laeufe) -> [{"befehl", "quelle", "status": "bestanden"|"verfehlt"|"nicht belegt",
                           "anzahl", "werte_ms", "median_ms"}]
      nur HEUTE/MORGEN, nur kalte Laeufe (fr_direct, dwd), je (Befehl, Quelle);
      Mindestzahl fr_direct 3, dwd 5; strikte Grenzen (<60 000, Median <45 000);
      "verfehlt" hat Vorrang vor "nicht belegt".
  ziel_exitcode(ergebnisse) -> 0 (alle bestanden) | 1 (mind. eine verfehlt) | 2 (nicht belegt
      oder nichts geprueft)
  main(argv) -> int: ``--since``, ``--trip``, ``--ziel``, ``--journal-datei PFAD`` (Offline:
      liest dieses Journal statt journalctl und greift NICHT auf seven.io/Push zu).
      Ohne ``--ziel`` bleibt der Rueckgabewert 0. Ausgabe je Lauf: Zeit, Befehl, Kanal, Trip,
      Dauer, Quelle; mit ``--ziel`` zusaetzlich je Gruppe das Ergebnis und die Einzelwerte.

Kein Netz, kein Mock/patch (laeuft mit ``--disable-socket``).
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_FIX = _REPO / "tests" / "fixtures" / "befehl_antwortzeit"
_LOG = _FIX / "prod_korsika_kalt_laeufe.log"


def _lade(name: str):
    pfad = _REPO / ".claude" / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, pfad)
    assert spec and pfad.is_file(), f"{pfad} fehlt"
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


@pytest.fixture(scope="module")
def ml():
    return _lade("befehl_messlogik")


@pytest.fixture(scope="module")
def werkzeug():
    return _lade("befehl_antwortzeit")


@pytest.fixture(scope="module")
def journal(ml):
    return ml.lese_journal(_LOG.read_text("utf-8").splitlines())


@pytest.fixture(scope="module")
def dauer(ml, journal):
    return ml.dauerzeilen(journal)


def _quellen(werkzeug, dauer, journal, trip, befehl=None):
    laeufe = werkzeug.kaltheit_je_lauf(dauer, journal, trip=trip)
    return [(l["befehl"], l["ms"], l["quelle"]) for l in laeufe
            if befehl is None or l["befehl"] == befehl]


def _lauf(befehl, ms, quelle, trip="t"):
    """Lauf wie ihn kaltheit_je_lauf liefert (Eingabe fuer pruefe_ziel)."""
    return {"ts": datetime(2026, 10, 26, 9, 0, tzinfo=timezone.utc) + timedelta(minutes=ms // 1000),
            "befehl": befehl, "kanal": "email", "trip": trip, "ms": ms, "quelle": quelle}


def _gruppe(ergebnisse, befehl, quelle):
    treffer = [e for e in ergebnisse if e["befehl"] == befehl and e["quelle"] == quelle]
    assert len(treffer) == 1, f"Gruppe ({befehl}, {quelle}) nicht genau einmal: {ergebnisse}"
    return treffer[0]


# --- AC-2: Konstanten unveraendert ---------------------------------------------------------

def test_grenzen_im_werkzeug_sind_unveraendert(werkzeug):
    assert werkzeug.GRENZE_MIT_WETTER_MS == 60_000
    assert werkzeug.GRENZE_MEDIAN_MS == 45_000
    assert werkzeug.MIN_LAEUFE_KORSIKA == 3
    assert werkzeug.MIN_LAEUFE_WETTER == 5


# --- AC-3: Kaltheit/Quelle je Lauf ---------------------------------------------------------

def test_fr_direct_download_im_befehlsfenster_ist_quelle_fr_direct(werkzeug, dauer, journal):
    heute = _quellen(werkzeug, dauer, journal, "kors-gut", "HEUTE")
    assert heute[:3] == [("HEUTE", 40000, "fr_direct"), ("HEUTE", 50000, "fr_direct"),
                         ("HEUTE", 30000, "fr_direct")]


def test_dwd_fenster_zaehlt_nie_als_fr_direct(werkzeug, dauer, journal):
    assert _quellen(werkzeug, dauer, journal, "de-1") == [("MORGEN", 20000, "dwd")]


def test_downloads_null_und_fenster_ausserhalb_sind_warm(werkzeug, dauer, journal):
    heute = _quellen(werkzeug, dauer, journal, "kors-gut", "HEUTE")
    assert ("HEUTE", 90000, "warm") in heute  # fr_direct_fenster downloads=0
    assert ("HEUTE", 20000, "warm") in heute  # Download VOR dem Befehlsfenster
    assert len(heute) == 5


def test_lauf_ohne_fensterzeile_ist_warm(werkzeug, dauer, journal):
    assert ("HEUTE", 10000, "warm") in _quellen(werkzeug, dauer, journal, "kors-duenn")


# --- AC-4: Trip-Filter ---------------------------------------------------------------------

def test_trip_filter_laesst_nur_laeufe_dieses_trips_zu(werkzeug, dauer, journal):
    laeufe = werkzeug.kaltheit_je_lauf(dauer, journal, trip="kors-gut")
    assert laeufe and {l["trip"] for l in laeufe} == {"kors-gut"}


def test_fremd_trip_mit_70s_macht_test_trip_nicht_rot(werkzeug, dauer, journal):
    nur_test = werkzeug.pruefe_ziel(werkzeug.kaltheit_je_lauf(dauer, journal, trip="kors-gut"))
    assert werkzeug.ziel_exitcode(nur_test) == 0
    alle = werkzeug.pruefe_ziel(werkzeug.kaltheit_je_lauf(dauer, journal))
    assert _gruppe(alle, "HEUTE", "fr_direct")["status"] == "verfehlt"  # ohne Filter: Fremd 70 s


# --- AC-5: Zielgroessen-Pruefung (Grenzfaelle) ---------------------------------------------

def test_fixture_kors_gut_je_befehl_bestanden_und_nur_kalte_zaehlen(werkzeug, dauer, journal):
    erg = werkzeug.pruefe_ziel(werkzeug.kaltheit_je_lauf(dauer, journal, trip="kors-gut"))
    heute = _gruppe(erg, "HEUTE", "fr_direct")
    assert heute["status"] == "bestanden"
    assert heute["anzahl"] == 3 and sorted(heute["werte_ms"]) == [30000, 40000, 50000]
    assert _gruppe(erg, "MORGEN", "fr_direct")["status"] == "bestanden"
    assert not [e for e in erg if e["befehl"] not in ("HEUTE", "MORGEN")]  # HELP zaehlt nie


def test_einzellauf_grenze_ist_strikt(werkzeug):
    ok = werkzeug.pruefe_ziel([_lauf("HEUTE", ms, "fr_direct") for ms in (40000, 44000, 59999)])
    assert _gruppe(ok, "HEUTE", "fr_direct")["status"] == "bestanden"
    zu = werkzeug.pruefe_ziel([_lauf("HEUTE", ms, "fr_direct") for ms in (40000, 44000, 60000)])
    assert _gruppe(zu, "HEUTE", "fr_direct")["status"] == "verfehlt"


def test_median_grenze_ist_strikt(werkzeug):
    ok = werkzeug.pruefe_ziel([_lauf("MORGEN", 44999, "fr_direct") for _ in range(3)])
    assert _gruppe(ok, "MORGEN", "fr_direct")["status"] == "bestanden"
    zu = werkzeug.pruefe_ziel([_lauf("MORGEN", 45000, "fr_direct") for _ in range(3)])
    assert _gruppe(zu, "MORGEN", "fr_direct")["status"] == "verfehlt"


def test_zu_wenige_kalte_laeufe_sind_nicht_belegt_statt_bestanden(werkzeug):
    erg = werkzeug.pruefe_ziel([_lauf("HEUTE", 40000, "fr_direct"), _lauf("HEUTE", 41000, "fr_direct")])
    assert _gruppe(erg, "HEUTE", "fr_direct")["status"] == "nicht belegt"


def test_warme_laeufe_zaehlen_weder_fuer_die_mindestzahl_noch_gegen_die_grenze(werkzeug):
    kalt = [_lauf("HEUTE", ms, "fr_direct") for ms in (40000, 41000, 42000)]
    warm = [_lauf("HEUTE", 20000 + i, "warm") for i in range(5)]
    erg = werkzeug.pruefe_ziel(kalt + warm)
    assert _gruppe(erg, "HEUTE", "fr_direct")["anzahl"] == 3
    assert _gruppe(erg, "HEUTE", "fr_direct")["status"] == "bestanden"
    # nur 2 kalte + viele warme: weiterhin nicht belegt
    erg2 = werkzeug.pruefe_ziel(kalt[:2] + warm)
    assert _gruppe(erg2, "HEUTE", "fr_direct")["status"] == "nicht belegt"
    # ein warmer 90-s-Lauf macht nichts rot
    erg3 = werkzeug.pruefe_ziel(kalt + [_lauf("HEUTE", 90000, "warm")])
    assert _gruppe(erg3, "HEUTE", "fr_direct")["status"] == "bestanden"


def test_dwd_braucht_fuenf_kalte_laeufe(werkzeug):
    vier = werkzeug.pruefe_ziel([_lauf("HEUTE", 30000 + i, "dwd") for i in range(4)])
    assert _gruppe(vier, "HEUTE", "dwd")["status"] == "nicht belegt"
    fuenf = werkzeug.pruefe_ziel([_lauf("HEUTE", 30000 + i, "dwd") for i in range(5)])
    assert _gruppe(fuenf, "HEUTE", "dwd")["status"] == "bestanden"


def test_verfehlt_hat_vorrang_vor_nicht_belegt(werkzeug):
    erg = werkzeug.pruefe_ziel([_lauf("HEUTE", 61000, "fr_direct"), _lauf("HEUTE", 40000, "fr_direct")])
    assert _gruppe(erg, "HEUTE", "fr_direct")["status"] == "verfehlt"


# --- AC-6: Exit-Code und main() ------------------------------------------------------------

def test_exitcode_funktion_vier_ausgaenge(werkzeug):
    b = {"status": "bestanden"}
    v = {"status": "verfehlt"}
    n = {"status": "nicht belegt"}
    assert werkzeug.ziel_exitcode([b, b]) == 0
    assert werkzeug.ziel_exitcode([b, v]) == 1
    assert werkzeug.ziel_exitcode([b, n]) == 2
    assert werkzeug.ziel_exitcode([n, v]) == 1  # verfehlt schlaegt nicht belegt
    assert werkzeug.ziel_exitcode([]) == 2      # nichts geprueft ist nie "bestanden"


@pytest.mark.parametrize("trip, erwartet, wort", [
    ("kors-gut", 0, "bestanden"),
    ("kors-lahm", 1, "verfehlt"),
    ("kors-duenn", 2, "nicht belegt"),
])
def test_main_mit_ziel_liefert_exitcode_und_einzelwerte(werkzeug, capsys, trip, erwartet, wort):
    rc = werkzeug.main(["--since", "2026-10-26", "--trip", trip, "--ziel",
                        "--journal-datei", str(_LOG)])
    ausgabe = capsys.readouterr().out
    assert rc == erwartet
    assert wort in ausgabe
    assert "fr_direct" in ausgabe and f"trip={trip}" in ausgabe
    assert "40000" in ausgabe  # Einzelwert je Lauf steht in der Ausgabe


def test_main_ohne_ziel_bleibt_exit_0_auch_bei_verfehlung(werkzeug, capsys):
    rc = werkzeug.main(["--since", "2026-10-26", "--trip", "kors-lahm",
                        "--journal-datei", str(_LOG)])
    assert rc == 0
    assert "61000" in capsys.readouterr().out


def test_main_schreibt_nichts_und_gibt_keine_rufnummer_aus(werkzeug, capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    werkzeug.main(["--since", "2026-10-26", "--ziel", "--journal-datei", str(_LOG)])
    assert list(tmp_path.iterdir()) == []
    assert "+49" not in capsys.readouterr().out
