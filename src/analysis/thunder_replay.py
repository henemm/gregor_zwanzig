"""Auswertung des KHW-Vorhersage-Mitschnitts (#2181 Scheibe S2a).

Vorlauf-Auswahl, Tages-Aggregation, Dreiwertigkeit und Teilmengen-Wahl fuer
T2 (CAPE-Sprossen) und T5 (HIGH-Haeufigkeit). Reine Funktionen: kein Netz,
kein Dateizugriff, keine ``GZ_*``-Umgebung.

ADR-0025: Es entsteht KEINE zweite Gewitter-Fusion. ``cape_max_jkg`` und
``thunder_level_max`` werden aus dem Mitschnitt nur nachgelesen, die
Stufenordnung kommt aus ``app.thunder_scale.thunder_ordinal``, die
Schwellenleiter aus ``app.model_registry.cape_ladder_thresholds_jkg`` (vom
Aufrufer uebergeben) — hier steht kein eigener Zahlenwert.
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.models import ThunderLevel
from app.thunder_scale import thunder_ordinal

# Quellen-Teilmengen (Spec, Abschnitt "Teilmengen-Festlegung")
TEILMENGE_PRIMAER: frozenset = frozenset({"briefing", "briefing_nacht"})
TEILMENGE_NUR_ALARM: frozenset = frozenset({"alarm"})

# Namen und Reihenfolge der Sprossen — ABGELEITET aus der kanonischen
# Stufenskala (jede Nicht-NONE-Stufe ist genau eine Sprosse der Leiter), nicht
# als lokale Kopie aufgezaehlt. Eine kuenftige fuenfte Stufe wandert damit von
# selbst mit; ``cape_ladder_thresholds_jkg`` liefert die Schwellen in derselben
# Ordnung (Waechter tests/tdd/test_thunder_scale_local_copy_guard.py).
_SPROSSEN = tuple(
    stufe.name.lower()
    for stufe in sorted(ThunderLevel, key=thunder_ordinal)
    if thunder_ordinal(stufe) > thunder_ordinal(ThunderLevel.NONE)
)


def vorlauf(zeile: dict) -> timedelta:
    """Abstand zwischen Abruf (``fetched_at``) und Fensterbeginn."""
    return (datetime.fromisoformat(zeile["fenster_start"])
            - datetime.fromisoformat(zeile["fetched_at"]))


def waehle_vorlauf_aermste(zeilen: list[dict]) -> Optional[dict]:
    """Die juengste Vorhersage — kleinster NICHT-negativer Vorlauf.

    Zeilen mit negativem Vorlauf sind Rueckschau und werden verworfen, auch
    wenn dadurch nichts uebrig bleibt (AC-2)."""
    gueltige = [z for z in zeilen if vorlauf(z) >= timedelta(0)]
    if not gueltige:
        return None
    return min(gueltige, key=vorlauf)


def etappentag(zeile: dict) -> str:
    """UTC-Kalenderdatum von ``fenster_start`` als ISO-Datum."""
    beginn = datetime.fromisoformat(zeile["fenster_start"])
    if beginn.tzinfo is not None:
        beginn = beginn.astimezone(timezone.utc)
    return beginn.date().isoformat()


def gruppiere_etappentage(zeilen: list[dict]) -> dict[str, list[dict]]:
    """Zeilen nach Etappentag gruppiert, unabhaengig von ``segment_id``."""
    gruppen: dict[str, list[dict]] = {}
    for zeile in zeilen:
        gruppen.setdefault(etappentag(zeile), []).append(zeile)
    return gruppen


def aggregiere_etappentag(segmentzeilen: list[dict]) -> dict:
    """Ein Tageswert aus den je Segment ausgewaehlten Zeilen.

    ``None`` (keine Aussage) bleibt ``None`` und kollabiert nicht auf 0.0
    bzw. ``ThunderLevel.NONE`` (AC-4/AC-5)."""
    cape_werte = [z["werte"]["cape_max_jkg"] for z in segmentzeilen
                  if z["werte"].get("cape_max_jkg") is not None]
    level_werte = [ThunderLevel(z["werte"]["thunder_level_max"]) for z in segmentzeilen
                   if z["werte"].get("thunder_level_max") is not None]
    return {
        "cape_max_jkg": max(cape_werte) if cape_werte else None,
        "thunder_level_max": max(level_werte, key=thunder_ordinal) if level_werte else None,
    }


def _tageswerte(
    zeilen: list[dict],
    etappentage: Optional[Collection[str]] = None,
) -> dict[str, dict]:
    """Je Etappentag ein Tageswert: pro ``segment_id`` gewinnt die
    vorlauf-aermste Zeile, daraus wird der Tag verdichtet (AC-1/AC-3).

    Bleibt fuer einen Tag KEINE Zeile uebrig, ist er kein Etappentag der
    Messung und faellt aus dem Ergebnis. Das folgt aus AC-2: eine verworfene
    Rueckschau-Zeile ist verworfen, und ein Tag ohne verbleibende Zeile hat
    keine Vorhersage, ueber die man etwas aussagen koennte. ``keine_aussage``
    bleibt damit dem anderen, echten Fall vorbehalten — eine Vorhersage
    EXISTIERTE, lieferte aber keinen Wert (AC-4/AC-5).

    Faellt nur EIN Segment als reine Rueckschau aus, bleibt der Tag erhalten
    und traegt den aus den verbleibenden, gueltigen Segmenten aggregierten
    Wert — halbe Gueltigkeit ist keine Ungueltigkeit.

    ``etappentage`` grenzt die Messgrundlage ein (siehe
    ``tageswerte_je_teilmenge``)."""
    tageswerte: dict[str, dict] = {}
    for tag, tagzeilen in gruppiere_etappentage(zeilen).items():
        if etappentage is not None and tag not in etappentage:
            continue
        je_segment: dict[str, list[dict]] = {}
        for zeile in tagzeilen:
            je_segment.setdefault(str(zeile["segment_id"]), []).append(zeile)
        ausgewaehlt = [waehle_vorlauf_aermste(g) for g in je_segment.values()]
        ausgewaehlt = [z for z in ausgewaehlt if z is not None]
        if not ausgewaehlt:
            continue
        tageswerte[tag] = aggregiere_etappentag(ausgewaehlt)
    return tageswerte


def tageswerte_je_teilmenge(
    zeilen: list[dict],
    etappentage: Optional[Collection[str]] = None,
) -> dict[str, dict[str, dict]]:
    """Tageswerte fuer 'primaer', 'alle_quellen' und 'nur_alarm'.

    Die Empfindlichkeit gegenueber der Quellenwahl ist Bestandteil der
    Ausgabe, kein nachgereichter Kommentar (AC-6).

    ``etappentage`` (ISO-Datumsstrings) macht die Messgrundlage explizit und
    ist eine Entscheidung des AUFRUFERS, keine Annahme dieses Moduls:

    * ``None`` (Vorgabe): jeder Tag zaehlt, fuer den eine gueltige Vorhersage
      existiert;
    * eine Menge: ausschliesslich diese Tage erscheinen — ein Tag ausserhalb
      faellt heraus, auch wenn er gueltige Werte traegt. Umgekehrt wird kein
      genannter Tag erfunden, fuer den keine Vorhersage vorliegt."""
    return {
        "primaer": _tageswerte(
            [z for z in zeilen if z.get("source") in TEILMENGE_PRIMAER], etappentage),
        "alle_quellen": _tageswerte(list(zeilen), etappentage),
        "nur_alarm": _tageswerte(
            [z for z in zeilen if z.get("source") in TEILMENGE_NUR_ALARM], etappentage),
    }


def cape_sprossen_treffer(
    tageswerte_je_teilmenge: dict[str, dict[str, dict]],
    schwellen: tuple[float, float, float],
) -> dict:
    """Je Teilmenge und Sprosse: ueber / unter / keine Aussage.

    "Ueber der Sprosse" ist inklusiv (``>=``) — dieselbe Semantik wie
    ``metric_format._thunder_level_from_ladder``, keine zweite Regel."""
    ergebnis: dict = {}
    for teilmenge, tageswerte in tageswerte_je_teilmenge.items():
        je_sprosse: dict = {}
        for sprosse, schwelle in zip(_SPROSSEN, schwellen):
            zaehler = {"ueber": 0, "unter": 0, "keine_aussage": 0}
            for tageswert in tageswerte.values():
                cape = tageswert.get("cape_max_jkg")
                if cape is None:
                    zaehler["keine_aussage"] += 1
                elif cape >= schwelle:
                    zaehler["ueber"] += 1
                else:
                    zaehler["unter"] += 1
            je_sprosse[sprosse] = zaehler
        ergebnis[teilmenge] = je_sprosse
    return ergebnis


def hoch_haeufigkeit(tageswerte_je_teilmenge: dict[str, dict[str, dict]]) -> dict:
    """Je Teilmenge: hoch / andere Stufe / Entwarnung / keine Aussage.

    Dreiwertigkeit: ``None`` (keine Aussage), ``ThunderLevel.NONE``
    (geprueefte Entwarnung) und LOW/MED (andere Stufe) bleiben getrennt."""
    ergebnis: dict = {}
    for teilmenge, tageswerte in tageswerte_je_teilmenge.items():
        zaehler = {"hoch": 0, "andere_stufe": 0, "entwarnung": 0, "keine_aussage": 0}
        for tageswert in tageswerte.values():
            level = tageswert.get("thunder_level_max")
            if level is None:
                zaehler["keine_aussage"] += 1
            elif level == ThunderLevel.HIGH:
                zaehler["hoch"] += 1
            elif level == ThunderLevel.NONE:
                zaehler["entwarnung"] += 1
            else:
                zaehler["andere_stufe"] += 1
        ergebnis[teilmenge] = zaehler
    return ergebnis
