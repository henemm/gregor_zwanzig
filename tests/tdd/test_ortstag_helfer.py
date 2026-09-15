"""Selbsttest des Ortstag-Helfers (Issue #2314, AC-5).

`tests.helpers.ortstag.ortstag(lat, lon, *, now_utc=None) -> date` liefert den
Kalendertag AM ORT der uebergebenen Koordinaten -- nicht den Kalendertag der
fixierten Prozesszone `America/St_Johns` (#1402) und nicht den UTC-Kalendertag.
Diese Datei ist der Selbsttest des Helfers selbst -- die Sollwerte stehen
deshalb als LITERALE hier, nie aus `tz_for_coords()`/`zoneinfo` berechnet,
sonst pruefte der Test nur seine eigene Kopie (Tautologie-Verbot, Spec
Abschnitt "Explizit NICHT umgestellt").

Der Helfer existiert zum Zeitpunkt dieser RED-Phase noch nicht -- der Import
auf Modulebene macht die Datei deshalb absichtlich mit einem
`ModuleNotFoundError` rot.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from freezegun import freeze_time

from tests.helpers.ortstag import ortstag, utc_tag  # utc_tag: ERGAENZUNG #2314 D2

# Drei Zonen, die im Kontrollzeitraum (22:00-04:30 UTC, Spec-Nachtfenster)
# unterschiedlich vom UTC-Kalendertag und von der Prozesszone St. John's
# abweichen.
_TIROL = (47.0, 11.0)  # UTC+2 im September (CEST)
_REYKJAVIK = (64.13, -21.90)  # UTC+0, keine Sommerzeit
_KALIFORNIEN = (39.19, -120.24)  # UTC-7 im September (PDT)


@pytest.mark.parametrize(
    "lat_lon,now_utc,erwartet",
    [
        # 23:00 UTC: Tirol ist schon ueber Mitternacht, Reykjavik und
        # Kalifornien noch nicht.
        (_TIROL, datetime(2026, 9, 14, 23, 0, tzinfo=timezone.utc), date(2026, 9, 15)),
        (_REYKJAVIK, datetime(2026, 9, 14, 23, 0, tzinfo=timezone.utc), date(2026, 9, 14)),
        (_KALIFORNIEN, datetime(2026, 9, 14, 23, 0, tzinfo=timezone.utc), date(2026, 9, 14)),
        # 00:30 UTC (Folgetag): jetzt ist auch Reykjavik ueber Mitternacht.
        (_REYKJAVIK, datetime(2026, 9, 15, 0, 30, tzinfo=timezone.utc), date(2026, 9, 15)),
        # 04:00 UTC: Kalifornien liegt noch im Vortag, Tirol schon im Folgetag.
        (_KALIFORNIEN, datetime(2026, 9, 15, 4, 0, tzinfo=timezone.utc), date(2026, 9, 14)),
        (_TIROL, datetime(2026, 9, 15, 4, 0, tzinfo=timezone.utc), date(2026, 9, 15)),
    ],
)
def test_ortstag_liefert_den_kalendertag_am_ort(lat_lon, now_utc, erwartet):
    """GIVEN Koordinaten in einer von drei Zonen und ein fester UTC-Zeitpunkt
    WHEN `ortstag(lat, lon, now_utc=...)` aufgerufen wird
    THEN liefert er den Kalendertag DIESER Ortszone -- nicht den UTC-Tag und
    nicht den Kalendertag der Prozesszone St. John's.
    """
    lat, lon = lat_lon
    ergebnis = ortstag(lat, lon, now_utc=now_utc)

    assert ergebnis == erwartet, (
        f"ortstag({lat}, {lon}, now_utc={now_utc.isoformat()}) lieferte "
        f"{ergebnis} statt {erwartet}"
    )


def test_ortstag_liest_die_uhr_wenn_now_utc_fehlt():
    """GIVEN keine explizite `now_utc` UND eine auf 2026-09-14T23:00:00+00:00
    gestellte Uhr (freezegun)
    WHEN `ortstag(47.0, 11.0)` ohne `now_utc` aufgerufen wird
    THEN liefert er trotzdem den Ortstag in Tirol (2026-09-15) -- obwohl
    `date.today()` im selben Block noch den 2026-09-14 zeigt. Messgrenze:
    unter freezegun ist `date.today()` der UTC-Tag, nicht der Tag der
    fixierten Prozesszone St. John's (#1402). Belegt: der Helfer rechnet
    selbst die Ortszeit um, statt nur einen Kalendertag weiterzureichen.
    """
    with freeze_time("2026-09-14T23:00:00+00:00"):
        assert date.today() == date(2026, 9, 14), (
            "Vorbedingung: `date.today()` (unter freezegun der UTC-Tag) muss "
            "hier noch den 14.09. zeigen -- sonst prueft der Test die falsche "
            "Abweichung"
        )
        ergebnis = ortstag(47.0, 11.0)

    assert ergebnis == date(2026, 9, 15), (
        f"ortstag(47.0, 11.0) ohne now_utc lieferte {ergebnis} statt "
        f"date(2026, 9, 15) -- der Helfer muss selbst die aktuelle Uhrzeit "
        f"lesen und in die Ortszone umrechnen"
    )


def test_ortstag_ohne_argumente_ist_typeerror():
    """GIVEN der Helfer ohne jedes Argument
    WHEN `ortstag()` aufgerufen wird
    THEN scheitert der Aufruf mit `TypeError` -- `lat`/`lon` sind
    Pflichtparameter ohne Default. Ein stiller Rueckfall auf eine
    Standardkoordinate wuerde genau den Fehler reproduzieren, den diese
    Lieferung behebt.
    """
    with pytest.raises(TypeError):
        ortstag()  # type: ignore[call-arg]


def test_ortstag_nur_mit_breitengrad_ist_typeerror():
    """GIVEN der Helfer nur mit `lat`, ohne `lon`
    WHEN `ortstag(47.0)` aufgerufen wird
    THEN scheitert der Aufruf ebenfalls mit `TypeError` -- `lon` ist genauso
    Pflicht wie `lat`.
    """
    with pytest.raises(TypeError):
        ortstag(47.0)  # type: ignore[call-arg]


# ═══════════════ #2314 Durchgang 2: Selbsttest fuer utc_tag() ═══════════════
#
# utc_tag() ist der UTC-Tag-Zwilling von ortstag() -- reiner .date()-Zugriff
# auf einen UTC-Zeitpunkt, ohne Zonenarithmetik. Tautologie-Verbot (Spec):
# NUR `utc_tag() == now(utc).date()` in Standardzone zu pruefen waere
# trivial -- beide lesen dieselbe Uhr auf dieselbe Weise. Deshalb zwei
# NICHT-tautologische Nachweise: ein literal hingeschriebener Soll-Tag nahe
# einer Tagesgrenze, und ein Subprozess-Nachweis unter einer Gestern-Zone
# (GZ_TEST_PROCESS_TZ, AC-2), der utc_tag() gegen den PROZESSTAG abgrenzt.
#
# Heute (RED) importiert der Modulkopf `utc_tag` aus einer Funktion, die es
# in tests/helpers/ortstag.py noch nicht gibt -- ALLE Tests dieser Datei
# (auch die bestehenden ortstag-Tests oben) scheitern deshalb mit
# ImportError bei der Sammlung. Das ist beabsichtigt (Auftrag, Teil 1b:
# "Rot per ImportError") und wird erst mit /50 (utc_tag() in
# tests/helpers/ortstag.py implementiert) wieder gemeinsam gruen.

def test_utc_tag_liefert_das_literal_datum_nahe_der_tagesgrenze():
    """GIVEN ein UTC-Zeitpunkt 5 Minuten vor Mitternacht (literal
    hingeschrieben, nicht aus now(utc) berechnet)
    WHEN utc_tag(now_utc=...) aufgerufen wird
    THEN liefert er GENAU dieses Datum -- kein Ortsbezug, keine Umrechnung."""
    zeitpunkt = datetime(2026, 9, 14, 23, 55, tzinfo=timezone.utc)
    assert utc_tag(now_utc=zeitpunkt) == date(2026, 9, 14)


def test_utc_tag_ueberschreitet_die_tagesgrenze_eine_minute_spaeter():
    """Kehrseite: eine Minute spaeter (00:00 UTC) ist bereits der Folgetag --
    belegt, dass utc_tag() wirklich `.date()` auf `now_utc` anwendet, nicht
    ein vorab gebundenes Datum."""
    zeitpunkt = datetime(2026, 9, 15, 0, 0, tzinfo=timezone.utc)
    assert utc_tag(now_utc=zeitpunkt) == date(2026, 9, 15)


def _echte_utc_jetzt() -> datetime:
    """Real-Zeit-UTC-`jetzt`, UNBEEINFLUSST von einer evtl. gesetzten Wanduhr
    (``GZ_TEST_WALL_CLOCK_UTC``/``freeze_time``, Session-Fixture
    ``_gestellte_wanduhr``, #2096) -- gelesen per Subprozess (``date -u``),
    Vorbild ``test_prozesszonen_schalter.py::_echte_utc_jetzt`` (Adversary-
    Fund F001, Folgebefund): die ZONENWAHL fuer den Sonden-Subprozess muss
    die ECHTE Zeit sehen, weil der Sonden-Subprozess selbst NIE eingefroren
    ist."""
    proc = subprocess.run(
        ["date", "-u", "+%s"], capture_output=True, text=True,
        timeout=10, check=True,
    )
    return datetime.fromtimestamp(int(proc.stdout.strip()), tz=timezone.utc)


def _lauf_utc_tag_im_subprozess(env_overrides: dict[str, str]) -> dict:
    """Subprozess-Sonde analog zu
    ``tests/tdd/test_prozesszonen_schalter.py::_lauf_sonde`` -- ruft aber
    ``utc_tag()`` UND ``date.today()`` im SELBEN Kindprozess auf. Belegt
    AC-2 fuer den neuen Helfer (nicht nur fuer den rohen Prozesstag): unter
    einer tragenden Gestern-Zone muss ``utc_tag()`` genau 1 Tag NACH dem
    Prozesstag liegen, weil er am UTC-Tag verankert bleibt."""
    repo_root = Path(__file__).resolve().parents[2]
    sonde_dir = Path(tempfile.mkdtemp(dir=repo_root, prefix=".gz_tz_probe_utc_tag_"))
    try:
        ausgabe = sonde_dir / "ergebnis.json"
        sonde_datei = sonde_dir / "test_sonde.py"
        sonde_datei.write_text(
            "import json\n"
            "from datetime import date\n"
            "from tests.helpers.ortstag import utc_tag\n"
            "\n"
            "def test_sonde():\n"
            "    ergebnis = {\n"
            "        'prozess_heute': date.today().isoformat(),\n"
            "        'utc_tag': utc_tag().isoformat(),\n"
            "    }\n"
            f"    with open({str(ausgabe)!r}, 'w', encoding='utf-8') as f:\n"
            "        json.dump(ergebnis, f)\n",
            encoding="utf-8",
        )
        # Adversary-Fund F001 (test_prozesszonen_schalter.py): dieselbe Sonde
        # kann selbst unter GZ_TEST_PROCESS_TZ / GZ_TEST_WALL_CLOCK_UTC laufen
        # (z.B. Vollsuite-Nachweis unter Gestern-Zone) -- ohne Entfernen
        # wuerde die AEUSSERE Variable durchsickern statt dem, was der Test
        # ueber env_overrides bewusst setzt.
        env = {
            k: v for k, v in os.environ.items()
            if not k.startswith("PYTEST_")
            and k not in ("GZ_TEST_PROCESS_TZ", "GZ_TEST_WALL_CLOCK_UTC")
        }
        env.update(env_overrides)
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", str(sonde_datei), "-q", "--no-header"],
            cwd=str(repo_root), capture_output=True, text=True, timeout=60, env=env,
        )
        ergebnis: dict = {}
        if ausgabe.exists():
            ergebnis = json.loads(ausgabe.read_text(encoding="utf-8"))
        ergebnis["exit_code"] = proc.returncode
        ergebnis["stdout"] = proc.stdout
        ergebnis["stderr"] = proc.stderr
        return ergebnis
    finally:
        shutil.rmtree(sonde_dir, ignore_errors=True)


def test_utc_tag_unter_gestern_zone_weicht_vom_prozesstag_ab():
    """GIVEN ein Kindprozess mit gesetzter Gestern-Zone (GZ_TEST_PROCESS_TZ,
    Spec AC-2)
    WHEN sowohl ``date.today()`` (Prozesstag) als auch ``utc_tag()`` im
    selben Lauf ausgewertet werden
    THEN unterscheiden sie sich um genau 1 Tag -- ``utc_tag()`` bleibt am
    UTC-Tag verankert, waehrend ``date.today()`` der (dann tragenden)
    Prozesszone folgt. Heute (RED) scheitert schon der Modul-Import dieser
    Datei mit ImportError, bevor dieser Test ueberhaupt laeuft (s.
    Abschnitts-Kommentar oben).

    Zonenwahl per ``_echte_utc_jetzt()``, NICHT ``datetime.now(timezone.utc)``:
    unter session-weit gestellter Wanduhr waere dieser Prozess selbst
    eingefroren, waehrend der Sonden-Subprozess unten real laeuft."""
    zone = ("Pacific/Marquesas" if _echte_utc_jetzt().hour < 9
            else "<-2330>+23:30")
    ergebnis = _lauf_utc_tag_im_subprozess({"GZ_TEST_PROCESS_TZ": zone})
    assert ergebnis["exit_code"] == 0, (
        f"Sonde fehlgeschlagen:\n{ergebnis.get('stdout')}\n{ergebnis.get('stderr')}"
    )
    prozess_heute = datetime.fromisoformat(ergebnis["prozess_heute"]).date()
    utc_tag_wert = datetime.fromisoformat(ergebnis["utc_tag"]).date()
    assert utc_tag_wert == prozess_heute + timedelta(days=1), (
        f"utc_tag() ({utc_tag_wert}) muss unter Gestern-Zone {zone!r} genau "
        f"1 Tag NACH dem Prozesstag ({prozess_heute}) liegen -- gemessen "
        f"weicht es nicht ab (Knopf GZ_TEST_PROCESS_TZ existiert noch nicht, "
        f"/50)."
    )
