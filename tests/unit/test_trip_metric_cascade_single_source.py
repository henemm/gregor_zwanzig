"""TDD RED — #1848 Scheibe A: EINE Quelle fuer die Trip-Kaskade.

SPEC: docs/specs/modules/feat_1848_a_kaskade_eine_quelle.md
KONTEXT: docs/context/feat-1848-ausblick-vokabular.md

Hier: AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-8, AC-9.
AC-7 ist der BESTANDSTEST ``tests/tdd/test_trip_outlook_metric_selection.py``
(unveraendert erneut ausgefuehrt) und wird hier bewusst NICHT nachgebaut.

Die Kaskadenregel aus ADR-0050 (D1-D4) ist heute zweimal implementiert:
``models.py::_clip_to_global_maximum()`` fuer das Kanal-Layout und
``compare_outlook_metric_ids.py::resolve_trip_outlook_metrics()`` fuer den
Ausblick (dessen Docstring sich selbst als "Nachbildung" bezeichnet). Diese
Datei ist der Waechter darueber, dass beide Flaechen fuer denselben Fall
dieselbe Kennungsmenge erlauben -- und dass die gemeinsame Quelle
``UnifiedWeatherDisplayConfig.allowed_metric_ids_for_report_type()``
existiert und D4 als ``None`` (nicht als leere Menge) traegt.

RED-Erwartung: jeder Test dieser Datei ruft die neue Methode auf; sie fehlt
noch, also scheitert jeder Test an der Zusicherung in ``_erlaubte_kennungen``.
Kein Test darf hier gruen anlaufen -- ein gruener Test in der RED-Phase wuerde
nur Bestandsverhalten zementieren.

🔴 Grenze dieser Datei (fuer den Adversary): der Waechter faengt DIVERGENZ
zwischen den beiden Flaechen, nicht DOPPLUNG. Eine zweite Umsetzung, die sich
in allen hier geprueften Faellen gleich verhaelt, bliebe unsichtbar (Spec,
"Known Limitations").

Kern-Schicht, deterministisch. Kein Mock-Framework, kein patch(), kein Netz.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Pfadregel #1409: Pruefling relativ zur eigenen Testdatei aufloesen -- sonst
# pruefte ein Worktree-Lauf die unveraenderte Hauptrepo-Kopie.
REPO_ROOT = Path(__file__).resolve().parents[2]
for _pfad in (REPO_ROOT, REPO_ROOT / "src"):
    if str(_pfad) not in sys.path:
        sys.path.insert(0, str(_pfad))

from app.models import MetricConfig, UnifiedWeatherDisplayConfig  # noqa: E402
from output.renderers.compare_metric_ids import (  # noqa: E402
    resolve_channel_enabled_metrics, resolve_enabled_metrics,
)
from output.renderers.compare_outlook_metric_ids import (  # noqa: E402
    resolve_trip_outlook_metrics,
)

# Alle hier verwendeten Kennungen sind im Compare-Katalog aufloesbar AUSSER
# ``confidence`` (selectable=False, dort gar nicht gefuehrt) -- s. Hinweis im
# AC-3-Test.
#
# #1848 A2: die Ausblick-Auswahl speichert reine KENNUNGEN; die frueher hier
# gefuehrte Auswertung je Kennung ist kein Speicherinhalt mehr, sondern wird
# vom Katalog abgeleitet. Fuer die Zusicherung dieses Tests -- der
# Kaskaden-Schnitt trifft in beiden Flaechen DIESELBE Kennungsmenge -- ist das
# folgenlos: geschnitten wurde schon immer auf ``metric_id``.

KANAL = "email"


def _ausblick_auswahl(kennungen):
    """Ausblick-Auswahl im Speicherformat: reine Kennungen (#1848 A2)."""
    return list(kennungen)


def _dc(*, grundauswahl, kanal_layout=None, ausblick=None):
    """Echte ``UnifiedWeatherDisplayConfig`` -- kein Mock, kein Stub.

    ``grundauswahl``: Liste von ``(kennung, felder)``; ``felder`` setzt
    ``enabled``/``morning_enabled``/``evening_enabled`` der GLOBALEN Ebene.
    ``kanal_layout``/``ausblick``: Kennungslisten. Die Kanal-Ebene traegt
    bewusst KEINE eigenen Overrides (``enabled=True``, kein morning/evening) --
    so entscheidet in beiden Flaechen ausschliesslich der Schnitt gegen die
    Grundauswahl, und die Flaechen sind vergleichbar (AC-9).
    """
    metrics = [
        MetricConfig(metric_id=kennung, order=i, **felder)
        for i, (kennung, felder) in enumerate(grundauswahl)
    ]
    dc = UnifiedWeatherDisplayConfig(trip_id="tour-1848", metrics=metrics)
    if kanal_layout is not None:
        dc.per_channel_layouts = {
            KANAL: [
                MetricConfig(metric_id=k, enabled=True, order=i)
                for i, k in enumerate(kanal_layout)
            ]
        }
    dc.outlook_metrics = _ausblick_auswahl(ausblick) if ausblick is not None else None
    return dc


def _erlaubte_kennungen(dc, report_type):
    """Die neue gemeinsame Quelle -- mit sprechendem RED-Fehler."""
    methode = getattr(dc, "allowed_metric_ids_for_report_type", None)
    assert methode is not None, (
        "RED: UnifiedWeatherDisplayConfig.allowed_metric_ids_for_report_type() "
        "fehlt (Spec Source: src/app/models.py:833-921). Ohne sie tragen "
        "_clip_to_global_maximum() und resolve_trip_outlook_metrics() je eine "
        "eigene Kopie der ADR-0050-Regeln D1-D4 -- genau die Doppelpflege, "
        "die #1848 Scheibe A aufloest."
    )
    return methode(report_type)


def _kanal_kennungen(dc, report_type):
    """Kennungsmenge der Flaeche KANAL-LAYOUT (ueber _clip_to_global_maximum)."""
    return {mc.metric_id for mc in dc.get_metrics_for_channel(KANAL, report_type)}


def _ausblick_kennungen(dc, report_type):
    """Kennungsmenge der Flaeche AUSBLICK (ueber resolve_trip_outlook_metrics)."""
    aufgeloest = resolve_trip_outlook_metrics(dc, report_type)
    assert aufgeloest is not None, (
        "Die Ausblick-Auswahl wurde gar nicht aufgeloest (None) -- dann "
        "vergleicht dieser Test zwei Flaechen, von denen eine leer ist."
    )
    return set(aufgeloest)


# ═════════════════════════ AC-1 — abgewaehlte Groesse ═════════════════════════

def test_ac1_abgewaehlte_groesse_faellt_in_kanal_layout_und_ausblick_gleich_raus():
    """AC-1: GIVEN eine Grundauswahl, in der "Schneehoehe" bewusst abgewaehlt
    ist, obwohl sie in Kanal-Layout UND Ausblick-Auswahl steht / WHEN beide
    Flaechen fuer denselben report_type geprueft werden / THEN schneidet jede
    Flaeche dieselbe Groesse heraus -- keine zeigt sie, keine behaelt sie.

    Erwartungswerte fest im Test hinterlegt, NICHT aus dem Pruefling
    abgeleitet: sonst bliebe jede Verfaelschung der Schnittregel gruen.
    """
    alle = ["precipitation", "temperature", "gust", "snow_depth"]
    dc = _dc(
        grundauswahl=[
            ("precipitation", {"enabled": True}),
            ("temperature", {"enabled": True}),
            ("gust", {"enabled": True}),
            ("snow_depth", {"enabled": False}),   # bewusst abgewaehlt
        ],
        kanal_layout=alle,
        ausblick=alle,
    )
    erwartet = {"precipitation", "temperature", "gust"}

    assert _erlaubte_kennungen(dc, "morning") == erwartet, (
        "Die gemeinsame Quelle erlaubt nicht genau die drei aktiven Groessen "
        "-- eine global abgewaehlte Groesse ist kein Teil des Maximums (D1/D2)."
    )
    assert _kanal_kennungen(dc, "morning") == erwartet, (
        "Kanal-Layout: 'snow_depth' ist global abgewaehlt, erscheint aber im "
        "Kanal. Eine Ebene darf nur abwaehlen, nie zurueckholen (ADR-0050)."
    )
    assert _ausblick_kennungen(dc, "morning") == erwartet, (
        "Ausblick: 'snow_depth' ist global abgewaehlt, erscheint aber in der "
        "3-Tages-Vorschau -- die Vorschau haelt die Kaskade nicht ein (AC-14 "
        "aus #1720 S1, hier ueber die gemeinsame Quelle)."
    )


# ═══════════════ AC-2 — leere Grundauswahl: None, kein Schnitt ═══════════════

def test_ac2_leere_grundauswahl_liefert_none_und_schneidet_in_keiner_flaeche():
    """AC-2 (Regel D4): GIVEN ein Altbestands-Trip ohne gespeicherte
    Grundauswahl (``metrics == []``) / WHEN die gemeinsame Quelle gefragt wird
    / THEN liefert sie ``None`` -- nicht ``set()``, nicht ``[]`` -- und beide
    Flaechen geben ihre Eingabe UNVERAENDERT zurueck.

    Die zentrale Falle dieser Scheibe: wer ``None`` und ``set()`` verwechselt
    (``allowed = ... or set()``), verwandelt "kein Maximum definiert" in
    "nichts erlaubt" und leert jeden Altbestands-Trip.
    """
    eingabe = ["precipitation", "gust", "snow_depth"]
    dc = _dc(grundauswahl=[], kanal_layout=eingabe, ausblick=eingabe)

    erlaubt = _erlaubte_kennungen(dc, "morning")
    assert erlaubt is None, (
        f"D4 verletzt: bei leerer Grundauswahl muss die gemeinsame Quelle "
        f"None liefern ('kein Maximum definiert'), nicht {erlaubt!r}. "
        "set() bedeutet 'nichts erlaubt' und leert jeden Bestandstrip."
    )

    kanal = [mc.metric_id for mc in dc.get_metrics_for_channel(KANAL, "morning")]
    assert kanal == eingabe, (
        f"Kanal-Layout: bei leerer Grundauswahl wurde geschnitten. Erwartet "
        f"die unveraenderte Eingabe {eingabe!r}, erhalten {kanal!r} (D4, "
        "models.py::_clip_to_global_maximum)."
    )

    ausblick = resolve_trip_outlook_metrics(dc, "morning")
    assert list(ausblick or []) == eingabe, (
        f"Ausblick: bei leerer Grundauswahl wurde geschnitten. Erwartet die "
        f"unveraenderte Auswahl {eingabe!r}, erhalten {ausblick!r} (D4, "
        "AC-16 aus #1720 S1)."
    )


# ═════════════════ AC-3 — selectable=False wirkt in beiden ═══════════════════

def test_ac3_nicht_waehlbare_groesse_erscheint_in_keiner_der_beiden_flaechen():
    """AC-3 (#1585): GIVEN ein Bestandstrip, der die zentral als
    ``selectable=False`` markierte Groesse "confidence" noch mit
    ``enabled=True`` gespeichert hat / WHEN beide Flaechen geprueft werden /
    THEN erscheint sie in keiner -- das selectable-Gate wirkt ueber die
    gemeinsame Quelle in beiden Aufrufern.

    🔴 Nachweiskraft ehrlich benannt: im Ausblick faellt "confidence" schon
    bei der Katalog-Aufloesung heraus (kein Compare-Katalog-Eintrag), dort
    beweist der Fall den Schnitt NICHT. Traegend sind darum die Zusicherung
    auf die gemeinsame Quelle selbst und die Kanal-Flaeche; die
    Ausblick-Zusicherung haelt nur die beobachtbare Abwesenheit fest.
    """
    alle = ["precipitation", "confidence"]
    dc = _dc(
        grundauswahl=[
            ("precipitation", {"enabled": True}),
            ("confidence", {"enabled": True}),   # Bestand: noch aktiv gespeichert
        ],
        kanal_layout=alle,
        ausblick=alle,
    )

    assert _erlaubte_kennungen(dc, "evening") == {"precipitation"}, (
        "Die gemeinsame Quelle laesst 'confidence' zu, obwohl der zentrale "
        "Katalog sie als selectable=False fuehrt (#1585). Wer die Menge aus "
        "self.metrics statt aus get_metrics_for_report_type() baut, verliert "
        "das Gate fuer BEIDE Flaechen auf einen Schlag."
    )
    assert "confidence" not in _kanal_kennungen(dc, "evening"), (
        "Kanal-Layout zeigt eine zentral nicht waehlbare Groesse (#1585)."
    )
    assert "confidence" not in _ausblick_kennungen(dc, "evening"), (
        "Ausblick zeigt eine zentral nicht waehlbare Groesse (#1585)."
    )


# ═══════════ AC-4 — Morgen-/Abend-Override wirkt in beiden Flaechen ══════════

def test_ac4_morgen_override_schliesst_in_beiden_flaechen_identisch_aus():
    """AC-4 (ADR-0050 Regel 3): GIVEN "Boeen" ist global aktiv, aber per
    ``morning_enabled=False`` fuer den Morgenbericht abgewaehlt / WHEN beide
    Flaechen fuer ``report_type="morning"`` geprueft werden / THEN schliessen
    beide sie aus -- und fuer ``"evening"`` zeigen beide sie weiterhin.

    Wer gegen rohe ``enabled``-Flags statt gegen
    ``get_metrics_for_report_type()`` schneidet, wird hier rot.
    """
    alle = ["precipitation", "gust"]
    dc = _dc(
        grundauswahl=[
            ("precipitation", {"enabled": True}),
            ("gust", {"enabled": True, "morning_enabled": False}),
        ],
        kanal_layout=alle,
        ausblick=alle,
    )

    assert _erlaubte_kennungen(dc, "morning") == {"precipitation"}, (
        "Die gemeinsame Quelle ignoriert den morning_enabled=False-Override."
    )
    assert _kanal_kennungen(dc, "morning") == {"precipitation"}, (
        "Kanal-Layout: eine fuer den Morgenbericht abgewaehlte Groesse "
        "erscheint in der Morgen-Ausgabe (ADR-0050 Regel 3)."
    )
    assert _ausblick_kennungen(dc, "morning") == {"precipitation"}, (
        "Ausblick: eine fuer den Morgenbericht abgewaehlte Groesse erscheint "
        "in der Morgen-Vorschau -- der Override wirkt nur in einer Flaeche."
    )

    # Gegenprobe: derselbe Trip am Abend -- der Override darf NICHT dauerhaft
    # ausschliessen, sonst waere der Test auch mit einem Totalschnitt gruen.
    assert _erlaubte_kennungen(dc, "evening") == {"precipitation", "gust"}, (
        "Der Morgen-Override wirkt faelschlich auch am Abend."
    )
    assert _kanal_kennungen(dc, "evening") == {"precipitation", "gust"}
    assert _ausblick_kennungen(dc, "evening") == {"precipitation", "gust"}


# ═══════════ AC-5/AC-6 — Drei-Werte-Semantik des Ausblicks bleibt ════════════

def test_ac5_fehlende_ausblick_auswahl_bleibt_none():
    """AC-5: GIVEN ein Trip MIT Grundauswahl, dessen Feld ``outlook_metrics``
    nicht gesetzt ist (``None``, Altbestand) / WHEN
    ``resolve_trip_outlook_metrics()`` aufgerufen wird / THEN kommt die
    GANZE Grundauswahl zurueck -- niemals ``[]``.

    ⚠️ NACHGEZOGEN durch #1848 A3 (AC-3, PO-Freigabe 2026-08-21): bis dahin
    lieferte dieser Fall ``None`` ("Feld fehlt" -> die sieben festen
    Spalten). Seither heisst "nie eingestellt" = "nichts abgewaehlt", und der
    Ausblick zeigt exakt die Groessen des Trips.

    Der Kern der Zusicherung ist unveraendert und bleibt der wichtige Teil:
    das Ergebnis darf NICHT ``[]`` sein -- diese Verwechslung wuerde den
    Ausblick-Block fuer 100 % der heutigen Trips still abschalten (ADR-0037
    Drei-Werte-Semantik).
    """
    dc = _dc(
        grundauswahl=[("precipitation", {"enabled": True}),
                      ("gust", {"enabled": True})],
        ausblick=None,
    )
    # Vorbedingung ueber die gemeinsame Quelle: ein Maximum IST definiert.
    assert _erlaubte_kennungen(dc, "morning") == {"precipitation", "gust"}

    ergebnis = resolve_trip_outlook_metrics(dc, "morning")
    assert ergebnis != [], (
        "Erwartet die Grundauswahl, erhalten []. [] heisst 'bewusst geleert' "
        "und wuerde den Ausblick-Block ganz abschalten (ADR-0037 "
        "Drei-Werte-Semantik)."
    )
    assert ergebnis is not None and set(ergebnis) == {"precipitation", "gust"}, (
        f"Erwartet die GANZE Grundauswahl ['precipitation', 'gust'], erhalten "
        f"{ergebnis!r}. ``None`` hiesse Rueckfall auf die sieben festen "
        "Spalten -- genau das loest #1848 A3 ab (AC-3)."
    )


def test_ac6_bewusst_geleerte_ausblick_auswahl_bleibt_leere_liste():
    """AC-6: GIVEN ein Trip MIT Grundauswahl und einer bewusst geleerten
    Ausblick-Auswahl (``outlook_metrics == []``) / WHEN
    ``resolve_trip_outlook_metrics()`` aufgerufen wird / THEN bleibt der
    Rueckgabewert ``[]`` -- der neue Schnitt macht daraus weder ``None`` noch
    eine gefuellte Liste.

    Explizit auf ``== []`` geprueft und getrennt vom None-Fall aus AC-5: die
    beiden "leer"-Faelle haben gegensaetzliches Sollverhalten.
    """
    dc = _dc(
        grundauswahl=[("precipitation", {"enabled": True}),
                      ("gust", {"enabled": True})],
        ausblick=[],
    )
    assert _erlaubte_kennungen(dc, "morning") == {"precipitation", "gust"}

    ergebnis = resolve_trip_outlook_metrics(dc, "morning")
    assert ergebnis == [], (
        f"Erwartet [] ('bewusst geleert' -> der Ausblick-Block entfaellt), "
        f"erhalten {ergebnis!r}. None wuerde stattdessen die sieben festen "
        "Bestandsspalten zurueckholen (ADR-0037)."
    )
    assert ergebnis is not None, (
        "Der leere Wert darf nicht None sein -- 'leer heisst leer'."
    )


# ═══════ AC-8 — Ortsvergleich behaelt seine gegensaetzliche []-Semantik ══════

def test_ac8_leere_grundauswahl_schneidet_im_ortsvergleich_leer_beim_trip_nicht():
    """AC-8 (#1366 vs. D4): GIVEN dieselbe leere Grundauswahl / WHEN sie
    einmal an die Ortsvergleich-Auswahl
    (``resolve_channel_enabled_metrics()``) und einmal an den Trip gegeben
    wird / THEN schneidet der Ortsvergleich auf ``[]``, waehrend der Trip
    NICHT schneidet.

    Bewusster Kontrast zu AC-2: der Ortsvergleich wird von dieser Scheibe
    NICHT eingemeindet. Zoege der Umbau ihn versehentlich auf die neue
    Methode, folgte er der Trip-Semantik und dieser Test wuerde rot.
    """
    ortsvergleich = resolve_channel_enabled_metrics(
        [], {"sms": ["temp_max_c", "wind_max_kmh"]}, "sms",
    )
    assert ortsvergleich == [], (
        f"Ortsvergleich: eine bewusst geleerte Grundauswahl ([]) IST ein "
        f"Maximum -- die leere Menge (#1366). Erhalten {ortsvergleich!r}. "
        "Wurde resolve_channel_enabled_metrics() auf "
        "allowed_metric_ids_for_report_type() umgezogen? Das ist Out of Scope "
        "dieser Scheibe."
    )
    # Gegenprobe, dass der Ortsvergleich ueberhaupt schneiden KANN und nicht
    # generell [] liefert -- sonst waere die Zusicherung oben trivial wahr.
    global_metrics = resolve_enabled_metrics(["temp_max_c", "wind_max_kmh"])
    assert resolve_channel_enabled_metrics(
        global_metrics, {"sms": ["temp_max_c"]}, "sms",
    ) == ["temp_max"]

    # Derselbe "leer"-Fall beim Trip: kein Maximum, also KEIN Schnitt (D4).
    eingabe = ["precipitation", "gust"]
    dc = _dc(grundauswahl=[], kanal_layout=eingabe, ausblick=eingabe)
    assert _erlaubte_kennungen(dc, "morning") is None, (
        "Trip: leere Grundauswahl muss None ergeben (D4) -- die Divergenz zur "
        "Ortsvergleich-Semantik ist gewollt und bleibt nach dieser Scheibe "
        "bestehen."
    )
    assert _kanal_kennungen(dc, "morning") == set(eingabe)
    assert _ausblick_kennungen(dc, "morning") == set(eingabe)


# ═════════════ AC-9 — Flaechenvergleich: Divergenz wird sichtbar ═════════════

def test_ac9_beide_flaechen_liefern_fuer_denselben_fall_dieselbe_kennungsmenge():
    """AC-9: GIVEN ein Kaskaden-Fall mit allen drei Ausschlussgruenden
    (global abgewaehlt, Morgen-Override, Abend-Override) / WHEN Kanal-Layout
    und Ausblick mit IDENTISCHEN Eingabedaten fuer Morgen UND Abend gefragt
    werden / THEN liefern beide Flaechen dieselbe Kennungsmenge.

    Der Vergleich laeuft DIREKT zwischen den beiden Ergebnismengen -- nicht
    nur je Flaeche gegen einen Festwert. Fuehrt jemand kuenftig eine zweite,
    unabhaengige ID-Filterung fuer nur eine Flaeche ein, wird dieser Test rot,
    sobald sich die Flaechen an einem Randfall unterscheiden.

    Zwei report_types im selben Test: eine "gemeinsame Quelle", die den
    report_type nur in einer Flaeche durchreicht, faellt hier auf.
    """
    alle = ["precipitation", "temperature", "gust", "wind", "snow_depth"]
    dc = _dc(
        grundauswahl=[
            ("precipitation", {"enabled": True}),
            ("temperature", {"enabled": True}),
            ("gust", {"enabled": True, "morning_enabled": False}),
            ("wind", {"enabled": False, "evening_enabled": True}),
            ("snow_depth", {"enabled": False}),
        ],
        kanal_layout=alle,
        ausblick=alle,
    )
    erwartet = {
        "morning": {"precipitation", "temperature"},
        "evening": {"precipitation", "temperature", "gust", "wind"},
    }

    for report_type, soll in erwartet.items():
        kanal = _kanal_kennungen(dc, report_type)
        ausblick = _ausblick_kennungen(dc, report_type)

        assert kanal == ausblick, (
            f"DIVERGENZ bei report_type={report_type!r}: Kanal-Layout liefert "
            f"{sorted(kanal)}, Ausblick liefert {sorted(ausblick)}. Beide "
            "Flaechen muessen dieselbe Kaskadenregel benutzen -- laufen sie "
            "auseinander, gibt es wieder zwei Umsetzungen von ADR-0050 "
            "(#1848 Scheibe A)."
        )
        assert kanal == soll, (
            f"Beide Flaechen sind sich einig, aber gemeinsam falsch bei "
            f"report_type={report_type!r}: erwartet {sorted(soll)}, erhalten "
            f"{sorted(kanal)}."
        )
        assert _erlaubte_kennungen(dc, report_type) == soll, (
            f"Die gemeinsame Quelle liefert fuer report_type={report_type!r} "
            f"nicht {sorted(soll)} -- sie ist der Massstab, an dem beide "
            "Flaechen haengen."
        )
