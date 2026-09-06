"""TDD RED — Issue #2134 (Epic #2133 S1): eine fehlende Einzelgroesse wird
BENANNT, nicht durch stillen Komplettabbruch bzw. ein stummes `?` verdeckt.

SPEC: docs/specs/modules/feat_2134_adhoc_abruf_metrik_katalog.md
      AC-4 (Temperatur-Abbruch entschaerfen), AC-17 (geführt != gefuellt).

RED-Ursache:
* `_handle_hours_drilldown` (trip_command_processor.py:799-809) bricht den
  GESAMTEN Stundenabruf ab, sobald `r_temp.available` falsch ist — obwohl
  Wind/Regen/Gewitter separat abgerufen und per Zeitstempel gemappt werden
  (:811-813) und unabhaengig vorhanden sein koennen.
* Faellt nur das FELD aus (Punkte vorhanden, `t2m_c` durchgaengig `None`),
  greift der Abbruch gar nicht — die Tabelle zeigt dann stumme `?°C`
  (:822). Dieselbe Anforderung wie die Messluecken-Kennzeichnung aus
  #2050 S4b: eine Luecke gehoert benannt, nicht als Zeichen ausgeliefert.
* `Visib` ist heute ueberhaupt kein Abrufwort — eine im Gebiet unbefuellte
  Katalog-Groesse kann deshalb gar keine Luecke melden.

Mock-frei: echter Snapshot-Roundtrip; die Ausfall-Injektion fuer AC-4 laeuft
ueber eine ECHTE `WeatherExtractor`-Unterklasse (Vorbild `_FailingProcessor`,
tests/tdd/test_issue_1009_1019_inbound_robustness.py), die alle uebrigen
Groessen an `super()` durchreicht.
"""
from __future__ import annotations

import re

from services.weather_extractor import DrilldownResult, WeatherExtractor

from tests.helpers.adhoc_metrik_fixtures import (
    ist_unbekannt,
    lege_trip_an,
    sende,
    standard_felder,
    stundenzeilen,
)

# Woerter, mit denen eine benannte Luecke erkennbar ist. Bewusst eine Auswahl
# von Formulierungen statt EINER Zeichenkette — der AC verlangt, DASS die
# Luecke in Worten steht, nicht ihren genauen Wortlaut.
_LUECKENWORTE = (
    "nicht verfügbar", "nicht verfuegbar", "keine daten", "fehlt", "fehlen",
    "lücke", "luecke", "unbekannt", "nicht gemessen", "liegen nicht vor",
)


def _benennt_luecke(body: str, sache: str) -> bool:
    text = (body or "").lower()
    return sache.lower() in text and any(w in text for w in _LUECKENWORTE)


class _OhneTemperatur(WeatherExtractor):
    """ECHTE Unterklasse: `t2m_c` faellt aus, alles andere kommt echt.

    Kein Mock — jede andere Groesse laeuft unveraendert durch den realen
    Snapshot-Abruf von `WeatherExtractor.drilldown`.
    """

    def drilldown(self, trip_id, metric, from_time=None, hours=12):
        if metric == "t2m_c":
            return DrilldownResult(
                trip_id=trip_id, metric=metric, points=[], available=False,
                message="Temperatur im Testaufbau nicht verfuegbar.",
            )
        return super().drilldown(
            trip_id, metric, from_time=from_time, hours=hours,
        )


# ===========================================================================
# AC-4 (a) — Extraktor liefert available=False fuer die Temperatur
# ===========================================================================

def test_ac4_fehlende_temperatur_bricht_den_stundenabruf_nicht_ab(monkeypatch):
    """AC-4 GIVEN die Temperatur-Teilgroesse ist nicht verfuegbar, Wind/Regen/
    Gewitter aber schon WHEN der Nutzer die Stundenuebersicht abruft THEN
    erscheinen Wind, Regen und Gewitter und die fehlende Temperaturspalte wird
    als Luecke BENANNT, statt dass die gesamte Antwort leer bleibt.

    Eingehaengt wird auf `services.weather_extractor.WeatherExtractor` (nicht
    auf `services.trip_command_processor.WeatherExtractor`): der Prozessor
    importiert die Klasse zur AUFRUFZEIT innerhalb der Methode
    (`trip_command_processor.py:785`, Issue #1818) — ein Modul-Attribut am
    Prozessor gibt es gar nicht, ein Patch dort waere wirkungslos.
    """
    fix = lege_trip_an("ac4a")
    monkeypatch.setattr(
        "services.weather_extractor.WeatherExtractor", _OhneTemperatur,
    )

    result = sende(fix, "### dd_hours_today", channel="telegram")

    assert result.success is True, (
        f"AC-4: eine fehlende Einzelgroesse darf den Stundenabruf nicht "
        f"abbrechen, erhalten success={result.success} / "
        f"subject={result.confirmation_subject!r} / "
        f"body={result.confirmation_body!r}"
    )
    body = result.confirmation_body
    assert len(stundenzeilen(body)) >= 6, (
        f"AC-4: erwartet die vorhandenen Stundenzeilen (Wind/Regen/Gewitter), "
        f"gefunden {len(stundenzeilen(body))} in:\n{body}"
    )
    assert len(re.findall(r"\d+\s*km/h", body)) >= 3, (
        f"AC-4: die verfuegbaren Windwerte fehlen in der Antwort:\n{body}"
    )
    assert _benennt_luecke(body, "temperatur"), (
        f"AC-4: die fehlende Temperatur muss als Luecke BENANNT werden "
        f"(erwartet das Wort 'Temperatur' zusammen mit einem der Hinweise "
        f"{_LUECKENWORTE!r}), Antwort war:\n{body}"
    )


# ===========================================================================
# AC-4 (b) — der Fall, der produktiv tatsaechlich auftritt
# ===========================================================================

def test_ac4_leeres_temperaturfeld_wird_in_worten_benannt_nicht_als_fragezeichen():
    """AC-4 (produktiv erreichbarer Fall) GIVEN Stundenpunkte SIND vorhanden,
    aber `t2m_c` ist durchgaengig `None` WHEN der Nutzer die Stundenuebersicht
    abruft THEN wird die Temperatur-Luecke in WORTEN benannt.

    Warum das der eigentlich auftretende Fall ist (gemessen):
    `WeatherExtractor.drilldown` (weather_extractor.py:175-206) setzt
    `available=False` NUR, wenn gar kein Punkt im Fenster liegt. Ein
    fehlendes FELD ergibt `getattr(p, "t2m_c", None) -> None` bei
    `available=True` — der Abbruch aus :799 greift dann gar nicht, und die
    Tabelle liefert stumme `?°C` (:822). Der Nutzer kann nicht unterscheiden,
    ob es kalt ist oder ob nichts gemessen wurde.
    """
    def ohne_temperatur(i: int) -> dict:
        felder = standard_felder(i)
        felder.pop("t2m_c")
        return felder

    fix = lege_trip_an("ac4b", ohne_temperatur)

    result = sende(fix, "### dd_hours_today", channel="telegram")
    body = result.confirmation_body

    assert result.success is True, (
        f"Testaufbau: mit vorhandenen Punkten muss der Abruf durchlaufen, "
        f"erhalten success={result.success} / body={body!r}"
    )
    assert len(re.findall(r"\d+\s*km/h", body)) >= 3, (
        f"Testaufbau: die Windwerte muessen vorhanden sein:\n{body}"
    )
    assert _benennt_luecke(body, "temperatur"), (
        f"AC-4: die leere Temperaturspalte wird als stummes Zeichen "
        f"ausgeliefert statt in Worten benannt (erwartet 'Temperatur' plus "
        f"einen der Hinweise {_LUECKENWORTE!r}):\n{body}"
    )


# ===========================================================================
# AC-17 — gefuehrte, aber im Gebiet unbefuellte Groesse
# ===========================================================================

def test_ac17_unbefuellte_katalog_groesse_meldet_eine_benannte_luecke():
    """AC-17 GIVEN eine im Katalog gefuehrte Groesse ist im abgefragten Gebiet
    nicht befuellt (kein Stundenfeld) WHEN sie per Ad-hoc-Abruf abgefragt wird
    THEN benennt die Antwort die Luecke ausdruecklich, statt zu schweigen oder
    eine leere Tabelle aus Platzhaltern zu senden."""
    fix = lege_trip_an("ac17")  # standard_felder: KEIN visibility_m

    result = sende(fix, "Visib", channel="telegram")
    body = result.confirmation_body or ""

    assert not ist_unbekannt(result), (
        f"AC-17: `Visib` ist ein gefuehrtes Katalog-Kuerzel und muss erkannt "
        f"werden — auch wenn keine Werte vorliegen. Erhalten "
        f"command={result.command!r} / body={body!r}"
    )
    assert body.strip(), "AC-17: die Antwort ist leer — die Luecke schweigt."
    assert any(w in body.lower() for w in _LUECKENWORTE), (
        f"AC-17: erwartet einen ausdruecklichen Lueckenhinweis (eines von "
        f"{_LUECKENWORTE!r}), Antwort war:\n{body}"
    )
    platzhalter = re.findall(r"[–?]", body)
    assert len(platzhalter) < 6, (
        f"AC-17: die Antwort besteht aus einer Tabelle von Platzhaltern "
        f"({len(platzhalter)} Stueck) statt aus einem benannten Hinweis:\n"
        f"{body}"
    )
