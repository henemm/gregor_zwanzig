"""Auswertungsschicht fuer den KHW-Vorhersage-Mitschnitt (#2181 Scheibe S2a).

Prueft T2 (CAPE-Sprossen) und T5 (HIGH-Haeufigkeit) — genauer: die
Auswertungsschicht darunter (Vorlauf-Auswahl, Tages-Aggregation,
Dreiwertigkeit, Teilmengen-Wahl). Die Gewitterrechnung selbst ist NICHT
Pruefling; ihre Ergebnisse (``cape_max_jkg``, ``thunder_level_max``) werden
aus dem Mitschnitt nur nachgelesen (ADR-0025).

Alle Fixtures sind UNVERAENDERTE Zeilen aus dem echten Mitschnitt
``/home/hem/gz-messdaten/khw-2026-08-mitschnitt/`` (2246 Zeilen,
24.08.-05.09.2026). Kein Mock, keine erfundenen Messwerte.
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from src.analysis.thunder_replay import (
    TEILMENGE_NUR_ALARM,
    TEILMENGE_PRIMAER,
    aggregiere_etappentag,
    cape_sprossen_treffer,
    etappentag,
    gruppiere_etappentage,
    hoch_haeufigkeit,
    tageswerte_je_teilmenge,
    vorlauf,
    waehle_vorlauf_aermste,
)
from src.app.model_registry import cape_ladder_thresholds_jkg
from src.app.models import ThunderLevel
from src.providers.thunder_routing import thunder_region_for

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "khw_2026_08"

# Der massgebliche Tourzeitraum 2026-08-24 bis 2026-09-05 (PO-Entscheid
# 2026-09-07). Er steht hier und NICHT im Auswertungsmodul: welche Kalendertage
# die Messgrundlage bilden, entscheidet der Aufrufer, nicht die Daten.
_TOURTAGE_KHW_2026 = frozenset(
    (date(2026, 8, 24) + timedelta(days=abstand)).isoformat() for abstand in range(13)
)


def _zeilen(name: str) -> list[dict]:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))["zeilen"]


def _schwellen() -> tuple[float, float, float]:
    """Die geeichte CAPE-Leiter — nachgeschlagen, nicht hartkodiert."""
    schwellen = cape_ladder_thresholds_jkg("icon_d2", "DE_ALPEN")
    assert schwellen is not None, "CAPE-Leiter fuer icon_d2/DE_ALPEN nicht kalibriert"
    return schwellen


def test_ac1_waehlt_die_vorlauf_aermste_zeile():
    """AC-1: Von mehreren Vorhersagen desselben Tages/Segments gewinnt die
    juengste — die mit dem kleinsten NICHT-negativen Vorlauf."""
    zeilen = _zeilen("vorlauf_gruppe_24_08_segment_3.json")
    gewaehlt = waehle_vorlauf_aermste(zeilen)

    assert gewaehlt is not None
    # Identifikation ueber den Wert, nicht ueber Dateiinhalt-Stringsuche.
    assert gewaehlt["fetched_at"] == "2026-08-24T13:45:35.941908+00:00"
    assert vorlauf(gewaehlt) == timedelta(minutes=26, seconds=24, microseconds=58092)
    # Keine andere Zeile mit gueltigem Vorlauf ist juenger.
    gueltige = [z for z in zeilen if vorlauf(z) >= timedelta(0)]
    assert len(gueltige) > 1, "Fixture muss mehrere Vorhersagen desselben Segments enthalten"
    assert vorlauf(gewaehlt) == min(vorlauf(z) for z in gueltige)


def test_ac2_negativer_vorlauf_wird_verworfen_auch_ohne_alternative():
    """AC-2: Eine Zeile, die NACH dem Fenster abgerufen wurde, ist eine
    Rueckschau — sie wird verworfen, selbst wenn nichts anderes da ist."""
    zeilen = _zeilen("negativer_vorlauf_einzelzeile.json")
    assert len(zeilen) == 1
    assert vorlauf(zeilen[0]) < timedelta(0)

    assert waehle_vorlauf_aermste(zeilen) is None


def test_ac3_tageswert_folgt_der_auswahl_je_segment_nicht_dem_gesamtmaximum():
    """AC-3: Der Tageswert verdichtet die je SEGMENT ausgewaehlten Zeilen.

    Gemessen wird ueber ``tageswerte_je_teilmenge`` — den Weg, den die
    Auswertung real nimmt. Das Fixture traegt zwei vollstaendige Segmente
    desselben Etappentags, und die Segment-Trennung bestimmt das Ergebnis:

    * je Segment gewinnt die vorlauf-aermste Zeile (Segment 2: 260 J/kg,
      Segment 'Ziel': 310 J/kg), der Tageswert ist deren Maximum 310;
    * behandelte man alle Tageszeilen als EIN Segment, gewaenne allein die
      tagesweit juengste Zeile (Segment 2, Vorlauf 1:21 min) und der Tag
      traege 260 — unter der low-Sprosse statt darueber;
    * eine Maximierung ueber alle Zeilen ergaebe 520 — auch das nicht 310.
    """
    zeilen = _zeilen("vorlauf_mehrsegment_24_08.json")
    assert list(gruppiere_etappentage(zeilen)) == ["2026-08-24"]
    assert {str(z["segment_id"]) for z in zeilen} == {"2", "Ziel"}, (
        "Fixture-Annahme: die Segment-Trennung ist ueberhaupt pruefbar"
    )

    tageswerte = tageswerte_je_teilmenge(zeilen)["alle_quellen"]
    assert list(tageswerte) == ["2026-08-24"]
    tageswert = tageswerte["2026-08-24"]

    assert tageswert["cape_max_jkg"] == 310.0
    assert tageswert["thunder_level_max"] == ThunderLevel.LOW

    # (a) nicht das Rohmaximum ueber alle Zeilen
    roh_maximum = max(
        z["werte"]["cape_max_jkg"] for z in zeilen
        if z["werte"]["cape_max_jkg"] is not None
    )
    assert roh_maximum == 520.0, "Fixture-Annahme: aeltere Zeilen tragen mehr"
    assert tageswert["cape_max_jkg"] != roh_maximum

    # (b) nicht der Wert der tagesweit juengsten Zeile — genau das Ergebnis,
    # das eine ausgehebelte Segment-Trennung liefern wuerde.
    tagesweit_juengste = waehle_vorlauf_aermste(zeilen)
    assert tagesweit_juengste["werte"]["cape_max_jkg"] == 260.0
    assert tagesweit_juengste["werte"]["thunder_level_max"] == "NONE"
    assert tageswert["cape_max_jkg"] != tagesweit_juengste["werte"]["cape_max_jkg"]

    # Die Segment-Trennung kippt die Sprossen-Kategorie, nicht nur die Zahl.
    low, _med, _high = _schwellen()
    assert tagesweit_juengste["werte"]["cape_max_jkg"] < low <= tageswert["cape_max_jkg"]
    sprossen = cape_sprossen_treffer(tageswerte_je_teilmenge(zeilen), _schwellen())
    assert sprossen["alle_quellen"]["low"]["ueber"] == 1
    assert sprossen["alle_quellen"]["low"]["unter"] == 0
    assert hoch_haeufigkeit(tageswerte_je_teilmenge(zeilen))["alle_quellen"] == {
        "hoch": 0, "andere_stufe": 1, "entwarnung": 0, "keine_aussage": 0,
    }


def test_ac2_halb_gueltiger_tag_bleibt_und_traegt_nur_die_gueltigen_segmente():
    """AC-2/AC-3: "kein Segment gueltig" und "manche Segmente gueltig" sind
    zwei verschiedene Faelle. Faellt nur EIN Segment als reine Rueckschau aus,
    bleibt der Tag Etappentag der Messung und traegt den aus den GUELTIGEN
    Segmenten aggregierten Wert.

    Am 26.08. traegt Segment 1 (Quelle ``alarm``) ausschliesslich eine
    Rueckschau-Zeile, die Segmente 2 und 'Ziel' tragen gueltige Vorhersagen.
    Wer verlangte, dass ALLE Segmente gueltig sind, verloere den Tag ganz.
    """
    zeilen = _zeilen("gemischte_segment_gueltigkeit_26_08.json")
    je_segment: dict[str, list[dict]] = {}
    for zeile in zeilen:
        je_segment.setdefault(str(zeile["segment_id"]), []).append(zeile)
    assert set(je_segment) == {"1", "2", "Ziel"}
    assert waehle_vorlauf_aermste(je_segment["1"]) is None, (
        "Fixture-Annahme: Segment 1 traegt nur Rueckschau, liefert also keine Auswahl"
    )
    for segment in ("2", "Ziel"):
        assert waehle_vorlauf_aermste(je_segment[segment]) is not None

    tageswerte = tageswerte_je_teilmenge(zeilen)

    assert "2026-08-26" in tageswerte["nur_alarm"], (
        "halb gueltiger Tag faelschlich ganz verworfen"
    )
    # Der Wert stammt aus den gueltigen Segmenten (0.0 / NONE und 380.0 / LOW).
    assert tageswerte["nur_alarm"]["2026-08-26"] == {
        "cape_max_jkg": 380.0, "thunder_level_max": ThunderLevel.LOW,
    }
    erwartet = aggregiere_etappentag(
        [waehle_vorlauf_aermste(je_segment[s]) for s in ("2", "Ziel")]
    )
    assert tageswerte["nur_alarm"]["2026-08-26"] == erwartet

    # Der Tag zaehlt in den Messfunktionen mit — nicht als "keine Aussage".
    assert cape_sprossen_treffer(tageswerte, _schwellen())["nur_alarm"]["low"] == {
        "ueber": 1, "unter": 0, "keine_aussage": 0,
    }
    assert hoch_haeufigkeit(tageswerte)["nur_alarm"]["andere_stufe"] == 1


def test_ac2_verworfene_rueckschau_hebt_den_tageswert_auch_dann_nicht_an():
    """AC-2: Eine verworfene Rueckschau-Zeile ist verworfen — sie darf den
    Tageswert auch dann nicht anheben, wenn sie den hoechsten Wert des Tages
    traegt. Der vorstehende Test misst die Nicht-Beteiligung nur ueber den
    Stellvertreter ``waehle_vorlauf_aermste(...) is None``; hier wird sie am
    ERGEBNIS gemessen.

    Die ueberhoehten Werte sind KONSTRUIERT, weil der Mitschnitt keinen
    solchen Fall enthaelt: in keiner Teilmenge traegt ein Nur-Rueckschau-Segment
    mehr als das Maximum der gueltigen Segmente desselben Tages (``nur_alarm``:
    26.08. 0 gegen 380, 27.08. 30 gegen 1160, 28.08. 20 gegen 1140, 29.08. 0
    gegen 820, 30.08. 50 gegen 360 J/kg; in 'primaer' und 'alle_quellen' kommt
    gemischte Segment-Gueltigkeit ueberhaupt nicht vor). An den echten Zahlen
    bliebe ein Rueckfall auf den eigenen Wert der Rueckschau-Zeile unsichtbar —
    er verschwaende im ``max()``. Geprueft wird die REGEL, nicht die Datenlage.

    Ueberschrieben werden ausschliesslich die beiden Wertfelder der echten
    Segment-1-Zeile; ihr negativer Vorlauf bleibt unveraendert.
    """
    zeilen = _zeilen("gemischte_segment_gueltigkeit_26_08.json")
    rueckschau = [z for z in zeilen if str(z["segment_id"]) == "1"]
    assert len(rueckschau) == 1, "Fixture-Annahme: Segment 1 traegt genau die Rueckschau-Zeile"
    assert vorlauf(rueckschau[0]) < timedelta(0)

    ueberhoeht = json.loads(json.dumps(rueckschau[0]))
    ueberhoeht["werte"] = dict(
        ueberhoeht["werte"], cape_max_jkg=1300.0, thunder_level_max="HIGH"
    )
    assert vorlauf(ueberhoeht) == vorlauf(rueckschau[0]), (
        "die Konstruktion darf nur die Werte anfassen, nicht die Gueltigkeit"
    )

    tageswerte = tageswerte_je_teilmenge(
        [ueberhoeht] + [z for z in zeilen if str(z["segment_id"]) != "1"]
    )

    # Der Tag traegt weiterhin die gueltigen Segmente — 1300.0/HIGH schlaegt
    # weder beim CAPE noch bei der Stufe durch.
    assert tageswerte["nur_alarm"]["2026-08-26"] == {
        "cape_max_jkg": 380.0, "thunder_level_max": ThunderLevel.LOW,
    }

    # Und es kippt auch keine Kategorie: der konstruierte Wert liegt ueber
    # ALLEN drei Sprossen, ein Durchschlagen waere an jeder einzeln sichtbar.
    low, med, high = _schwellen()
    assert low <= 380.0 < med and 1300.0 >= high, (
        "Konstruktion muss die Sprossen-Kategorie ueberhaupt kippen koennen"
    )
    sprossen = cape_sprossen_treffer(tageswerte, _schwellen())["nur_alarm"]
    assert sprossen["low"] == {"ueber": 1, "unter": 0, "keine_aussage": 0}
    assert sprossen["med"] == {"ueber": 0, "unter": 1, "keine_aussage": 0}
    assert sprossen["high"] == {"ueber": 0, "unter": 1, "keine_aussage": 0}
    assert hoch_haeufigkeit(tageswerte)["nur_alarm"] == {
        "hoch": 0, "andere_stufe": 1, "entwarnung": 0, "keine_aussage": 0,
    }


def test_ac2_tag_ohne_einzige_vorhersage_ist_kein_etappentag_der_messung():
    """AC-2: Bleibt nach dem Verwerfen der Rueckschau-Zeilen NICHTS uebrig,
    hat der Tag keine Vorhersage, ueber die man etwas aussagen koennte — er
    erscheint in KEINER Teilmenge und faelscht insbesondere die
    ``keine_aussage``-Zaehlung nicht.

    Am 21.08. (vor Trip-Start) tragen alle Zeilen negativen Vorlauf, auch die
    aus der Quelle ``alarm``; der Nachbartag 22.08. traegt echte Vorhersagen
    in allen drei Teilmengen und bleibt erhalten.
    """
    zeilen = _zeilen("pseudo_etappentag_nur_rueckschau.json")
    pseudo = [z for z in zeilen if etappentag(z) == "2026-08-21"]
    assert pseudo, "Fixture-Annahme: der Pseudo-Tag traegt ueberhaupt Zeilen"
    assert all(vorlauf(z) < timedelta(0) for z in pseudo)
    assert "alarm" in {z["source"] for z in pseudo}, (
        "Fixture-Annahme: der Pseudo-Tag wuerde sonst nur trivial aus 'nur_alarm' fallen"
    )

    tageswerte = tageswerte_je_teilmenge(zeilen)

    for teilmenge in ("primaer", "alle_quellen", "nur_alarm"):
        assert "2026-08-21" not in tageswerte[teilmenge], (
            f"{teilmenge}: Pseudo-Etappentag ohne einzige Vorhersage gezaehlt"
        )
        assert "2026-08-22" in tageswerte[teilmenge], f"{teilmenge}: Nachbartag fehlt"

    assert hoch_haeufigkeit(tageswerte)["alle_quellen"]["keine_aussage"] == 0
    for zaehler in cape_sprossen_treffer(tageswerte, _schwellen())["alle_quellen"].values():
        assert zaehler["keine_aussage"] == 0


def test_ac4_keine_aussage_ist_weder_entwarnung_noch_stufe():
    """AC-4: ``thunder_level_max: null`` zaehlt ausschliesslich als
    "keine Aussage" — nicht als geprueefte Entwarnung (NONE), nicht als Stufe."""
    zeilen = _zeilen("ohne_aussage_01_09_segmente_3_4.json")
    assert all(z["werte"]["thunder_level_max"] is None for z in zeilen)

    ergebnis = hoch_haeufigkeit(tageswerte_je_teilmenge(zeilen))

    assert ergebnis["alle_quellen"]["keine_aussage"] == 1
    for teilmenge in ("primaer", "alle_quellen", "nur_alarm"):
        assert ergebnis[teilmenge]["hoch"] == 0
        assert ergebnis[teilmenge]["entwarnung"] == 0
        assert ergebnis[teilmenge]["andere_stufe"] == 0


def test_ac5_cape_null_und_null_komma_null_zaehlen_verschieden():
    """AC-5: "kein Messwert" (null) und "gemessen, unter jeder Sprosse" (0.0)
    sind zwei Aussagen — fuer jede der drei Sprossen einzeln."""
    zeilen = _zeilen("cape_null_und_null_komma_null.json")
    ergebnis = cape_sprossen_treffer(tageswerte_je_teilmenge(zeilen), _schwellen())

    for sprosse in ("low", "med", "high"):
        zaehler = ergebnis["alle_quellen"][sprosse]
        assert zaehler["keine_aussage"] == 1, f"{sprosse}: der null-Tag fehlt"
        assert zaehler["unter"] == 1, f"{sprosse}: der 0.0-Tag fehlt"
        assert zaehler["ueber"] == 0


def test_ac6_beide_messfunktionen_liefern_drei_teilmengen():
    """AC-6: Die Wahl der Quellen-Teilmenge ist sichtbarer Bestandteil der
    Ausgabe. Am 03.09. liefert Primaer 330 J/kg (ueber der low-Sprosse),
    "alle Quellen" 150 und "nur alarm" 50 (beide darunter) — die Wahl kippt
    dort die Kategorie."""
    zeilen = _zeilen("quellen_mischung.json")
    assert len({z["source"] for z in zeilen}) >= 4

    tageswerte = tageswerte_je_teilmenge(zeilen)
    assert set(tageswerte) == {"primaer", "alle_quellen", "nur_alarm"}
    assert tageswerte["primaer"]["2026-09-03"]["cape_max_jkg"] == 330.0
    assert tageswerte["alle_quellen"]["2026-09-03"]["cape_max_jkg"] == 150.0
    assert tageswerte["nur_alarm"]["2026-09-03"]["cape_max_jkg"] == 50.0

    sprossen = cape_sprossen_treffer(tageswerte, _schwellen())
    assert set(sprossen) == {"primaer", "alle_quellen", "nur_alarm"}
    assert sprossen["primaer"]["low"]["ueber"] == 1
    assert sprossen["alle_quellen"]["low"]["ueber"] == 0
    assert sprossen["nur_alarm"]["low"]["ueber"] == 0

    hoch = hoch_haeufigkeit(tageswerte)
    assert set(hoch) == {"primaer", "alle_quellen", "nur_alarm"}
    assert hoch["primaer"]["andere_stufe"] == 1
    assert hoch["alle_quellen"]["entwarnung"] == 1


def test_ac6_teilmengen_definition_folgt_der_spec():
    """AC-6: Primaer sind die tatsaechlich versendeten Briefings; ``alarm``
    ist wegen Zirkularitaet separat ausgewiesen, nicht primaer."""
    assert set(TEILMENGE_PRIMAER) == {"briefing", "briefing_nacht"}
    assert set(TEILMENGE_NUR_ALARM) == {"alarm"}


def test_ac7_jede_sprosse_traegt_eine_eigene_zaehlung():
    """AC-7: drei getrennte Zahlen, keine kombinierte Kennzahl. Die vier
    Fixture-Tage erreichen 0, 1, 2 bzw. 3 Sprossen."""
    zeilen = _zeilen("cape_sprossen_spreizung.json")
    ergebnis = cape_sprossen_treffer(tageswerte_je_teilmenge(zeilen), _schwellen())["alle_quellen"]

    assert ergebnis["low"]["ueber"] == 3
    assert ergebnis["med"]["ueber"] == 2
    assert ergebnis["high"]["ueber"] == 1
    assert ergebnis["low"]["unter"] == 1
    assert ergebnis["med"]["unter"] == 2
    assert ergebnis["high"]["unter"] == 3
    for sprosse in ("low", "med", "high"):
        zaehler = ergebnis[sprosse]
        assert zaehler["ueber"] + zaehler["unter"] + zaehler["keine_aussage"] == 4


def test_ac8_gruppierung_folgt_dem_utc_kalendertag():
    """AC-8: Ein Etappentag ist das UTC-Kalenderdatum von ``fenster_start`` —
    unabhaengig von ``segment_id`` (auch der nicht-numerischen 'Ziel')."""
    zeilen = _zeilen("zwei_etappentage_24_25_08.json")
    gruppen = gruppiere_etappentage(zeilen)

    assert set(gruppen) == {"2026-08-24", "2026-08-25"}
    assert len(gruppen["2026-08-24"]) == 16
    assert len(gruppen["2026-08-25"]) == 14
    for tag, mitglieder in gruppen.items():
        assert all(etappentag(z) == tag for z in mitglieder)
    assert "Ziel" in {str(z["segment_id"]) for z in gruppen["2026-08-24"]}


def test_ac8_offset_zeile_faellt_auf_den_utc_kalendertag():
    """AC-8: Der Etappentag ist das UTC-Datum, nicht das Datum der lokalen
    Schreibweise. Bei ``2026-08-25T01:30:00+02:00`` gehen beide Lesarten
    auseinander — UTC ist der 24.08.

    Der Offset ``+02:00`` ist SYNTHETISCH: der Mitschnitt fuehrt
    ausschliesslich ``+00:00``, weshalb die Normalisierung ohne diesen Test
    unbewacht bliebe. Ueberschrieben wird nur das eine Feld einer echten
    Zeile.
    """
    basis = _zeilen("zwei_etappentage_24_25_08.json")[0]
    zeile = json.loads(json.dumps(basis))
    zeile["fenster_start"] = "2026-08-25T01:30:00+02:00"

    # Die naive Lesart (Datum der Schreibweise) waere der 25.08. — genau die
    # Verwechslung, die die Normalisierung verhindern soll.
    assert datetime.fromisoformat(zeile["fenster_start"]).date().isoformat() == "2026-08-25"

    assert etappentag(zeile) == "2026-08-24"
    assert list(gruppiere_etappentage([zeile])) == ["2026-08-24"]


def test_tages_maximum_folgt_der_kanonischen_stufenordnung():
    """Gegenprobe zur Aggregation: das Tages-Maximum mehrerer Segmente nutzt
    dieselbe Ordnung wie der Produktivpfad (NONE < LOW < MED < HIGH) — eine
    alphabetische Sortierung waehlte hier faelschlich 'NONE'."""
    basis = _zeilen("zwei_etappentage_24_25_08.json")[0]

    def mit(level, cape):
        zeile = json.loads(json.dumps(basis))
        zeile["werte"] = dict(zeile["werte"], thunder_level_max=level, cape_max_jkg=cape)
        return zeile

    tageswert = aggregiere_etappentag([mit("MED", 100.0), mit("NONE", 900.0), mit(None, None)])

    assert tageswert["thunder_level_max"] == ThunderLevel.MED
    assert tageswert["cape_max_jkg"] == 900.0


def test_sprossen_semantik_ist_inklusiv_wie_im_produktivpfad():
    """Gegenprobe zur Schwellen-Semantik: ``metric_format._thunder_level_from_ladder``
    zaehlt einen Wert, der die Sprosse ERREICHT, als Treffer (``>=``). Die
    Auswertung darf hier keine zweite Regel erfinden."""
    low, med, high = _schwellen()
    tageswerte = {
        "alle_quellen": {"2026-08-24": {"cape_max_jkg": low, "thunder_level_max": None}},
        "primaer": {},
        "nur_alarm": {},
    }
    ergebnis = cape_sprossen_treffer(tageswerte, (low, med, high))

    assert ergebnis["alle_quellen"]["low"]["ueber"] == 1
    assert ergebnis["alle_quellen"]["low"]["unter"] == 0


def test_gebiet_und_leiter_stammen_aus_der_registry():
    """Die CAPE-Leiter wird nachgeschlagen (Gebiet aus den Mitschnitt-
    Koordinaten), nicht im Auswertungsmodul hartkodiert."""
    zeile = _zeilen("vorlauf_gruppe_24_08_segment_3.json")[0]
    region = thunder_region_for(zeile["lat"], zeile["lon"])

    assert region == "DE_ALPEN"
    assert cape_ladder_thresholds_jkg(zeile["model"], region) == _schwellen()


def test_messgrundlage_ohne_etappentage_sind_alle_tage_mit_gueltiger_vorhersage():
    """Vorgabe-Betriebsart: ohne ``etappentage`` zaehlt jeder Tag, fuer den
    eine gueltige Vorhersage existiert. Die Menge der Etappentage ist damit
    eine Entscheidung des AUFRUFERS, keine Annahme des Moduls."""
    zeilen = _zeilen("zwei_etappentage_24_25_08.json")

    tageswerte = tageswerte_je_teilmenge(zeilen)

    assert set(tageswerte["alle_quellen"]) == {"2026-08-24", "2026-08-25"}
    assert tageswerte_je_teilmenge(zeilen, etappentage=None) == tageswerte


def test_messgrundlage_etappentage_grenzt_die_zaehlung_wirklich_ein():
    """Mit ``etappentage`` erscheinen ausschliesslich die uebergebenen Tage —
    ein Tag mit gueltigen Werten, der nicht dazugehoert, verschwindet aus der
    Ausgabe UND aus beiden Messfunktionen (gemeinsamer Nenner fuer T5)."""
    zeilen = _zeilen("zwei_etappentage_24_25_08.json")
    voll = tageswerte_je_teilmenge(zeilen)
    assert "2026-08-25" in voll["alle_quellen"], "Fixture-Annahme: der Tag traegt Werte"

    beschnitten = tageswerte_je_teilmenge(zeilen, etappentage={"2026-08-24"})

    for teilmenge in ("primaer", "alle_quellen", "nur_alarm"):
        assert "2026-08-25" not in beschnitten[teilmenge], (
            f"{teilmenge}: Tag ausserhalb der Messgrundlage gezaehlt"
        )
        assert set(beschnitten[teilmenge]) <= {"2026-08-24"}
    assert beschnitten["alle_quellen"]["2026-08-24"] == voll["alle_quellen"]["2026-08-24"]

    zaehler = hoch_haeufigkeit(beschnitten)["alle_quellen"]
    assert sum(zaehler.values()) == 1
    for sprosse in cape_sprossen_treffer(beschnitten, _schwellen())["alle_quellen"].values():
        assert sprosse["ueber"] + sprosse["unter"] + sprosse["keine_aussage"] == 1


def test_messgrundlage_schneidet_auch_gueltige_tage_vor_tourbeginn_weg():
    """Der Parameter greift gegen VOLLWERTIGE Tage, nicht nur gegen ohnehin
    leere. Der Mitschnitt setzt zwei Tage vor Tourbeginn an: der 22. und der
    23.08. tragen in allen drei Teilmengen gueltige Werte, gehoeren aber nicht
    zum massgeblichen Tourzeitraum (PO-Entscheid 2026-09-07). Mit
    ``etappentage`` verschwinden genau diese beiden Tage — samt Nenner.
    """
    assert len(_TOURTAGE_KHW_2026) == 13
    assert min(_TOURTAGE_KHW_2026) == "2026-08-24"
    assert max(_TOURTAGE_KHW_2026) == "2026-09-05"

    zeilen = (_zeilen("vor_tourbeginn_22_23_08.json")
              + _zeilen("vorlauf_mehrsegment_24_08.json"))
    voll = tageswerte_je_teilmenge(zeilen)

    # Fixture-Annahme: die beiden Vor-Tour-Tage sind KEINE Leerfaelle.
    assert set(voll["alle_quellen"]) == {"2026-08-22", "2026-08-23", "2026-08-24"}
    for teilmenge in ("primaer", "alle_quellen", "nur_alarm"):
        for tag in ("2026-08-22", "2026-08-23"):
            assert voll[teilmenge][tag]["cape_max_jkg"] is not None
            assert voll[teilmenge][tag]["thunder_level_max"] == ThunderLevel.NONE
    assert voll["alle_quellen"]["2026-08-22"]["cape_max_jkg"] == 50.0
    assert voll["alle_quellen"]["2026-08-23"]["cape_max_jkg"] == 90.0
    assert voll["primaer"]["2026-08-22"]["cape_max_jkg"] == 40.0
    assert voll["primaer"]["2026-08-23"]["cape_max_jkg"] == 100.0

    beschnitten = tageswerte_je_teilmenge(zeilen, etappentage=_TOURTAGE_KHW_2026)

    for teilmenge in ("primaer", "alle_quellen", "nur_alarm"):
        assert set(beschnitten[teilmenge]) == {"2026-08-24"}, (
            f"{teilmenge}: gueltiger Tag vor Tourbeginn weiterhin gezaehlt"
        )
    assert beschnitten["alle_quellen"]["2026-08-24"] == voll["alle_quellen"]["2026-08-24"]

    # Der Nenner wandert mit — genau darum geht es beim Maszstab "2:13".
    assert sum(hoch_haeufigkeit(voll)["alle_quellen"].values()) == 3
    assert sum(hoch_haeufigkeit(beschnitten)["alle_quellen"].values()) == 1


def test_messgrundlage_leere_menge_heisst_keine_tage_nicht_alle_tage():
    """Die leere Menge ist eine Angabe, keine Auslassung: der Aufrufer nennt
    KEINEN Etappentag, also erscheint keiner. Nur ``None`` heisst "alle Tage
    mit gueltiger Vorhersage" — ein Wahrheitswert-Test (``if etappentage:``)
    verwechselte beides und zaehlte die leere Menge als vollen Nenner."""
    zeilen = _zeilen("zwei_etappentage_24_25_08.json")
    assert tageswerte_je_teilmenge(zeilen)["alle_quellen"], (
        "Fixture-Annahme: ohne Eingrenzung gibt es ueberhaupt Tage zu verlieren"
    )

    for leer in (set(), [], frozenset(), ()):
        ergebnis = tageswerte_je_teilmenge(zeilen, etappentage=leer)
        for teilmenge in ("primaer", "alle_quellen", "nur_alarm"):
            assert ergebnis[teilmenge] == {}, (
                f"{teilmenge}: leere Messgrundlage als 'alle Tage' gelesen ({leer!r})"
            )
        assert sum(hoch_haeufigkeit(ergebnis)["alle_quellen"].values()) == 0
        for zaehler in cape_sprossen_treffer(ergebnis, _schwellen())["alle_quellen"].values():
            assert sum(zaehler.values()) == 0


def test_messgrundlage_erfindet_keinen_tag_ohne_daten():
    """``etappentage`` grenzt nur ein: ein Tag ohne gueltige Vorhersage
    erscheint auch dann nicht, wenn der Aufrufer ihn nennt."""
    zeilen = _zeilen("zwei_etappentage_24_25_08.json")

    ergebnis = tageswerte_je_teilmenge(
        zeilen, etappentage={"2026-08-24", "2026-09-30"}
    )

    assert set(ergebnis["alle_quellen"]) == {"2026-08-24"}


@pytest.mark.parametrize("name", [
    "vorlauf_gruppe_24_08_segment_3.json",
    "vorlauf_mehrsegment_24_08.json",
    "gemischte_segment_gueltigkeit_26_08.json",
    "vor_tourbeginn_22_23_08.json",
    "negativer_vorlauf_einzelzeile.json",
    "ohne_aussage_01_09_segmente_3_4.json",
    "cape_null_und_null_komma_null.json",
    "quellen_mischung.json",
    "cape_sprossen_spreizung.json",
    "zwei_etappentage_24_25_08.json",
    "pseudo_etappentag_nur_rueckschau.json",
])
def test_fixtures_tragen_das_mitschnitt_format(name):
    """Schutz gegen erfundene Testdaten: jede Fixture-Zeile traegt die Felder,
    die ``forecast_capture.py`` schreibt."""
    zeilen = _zeilen(name)
    assert zeilen
    for zeile in zeilen:
        assert isinstance(datetime.fromisoformat(zeile["fetched_at"]), datetime)
        assert isinstance(datetime.fromisoformat(zeile["fenster_start"]), datetime)
        assert zeile["model"] == "icon_d2"
        assert zeile["source"] in {
            "unbekannt", "alarm", "trend", "briefing", "briefing_nacht", "vorschau",
        }
        assert "cape_max_jkg" in zeile["werte"]
        assert "thunder_level_max" in zeile["werte"]
