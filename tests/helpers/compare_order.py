"""Soll-Menge und Reihenfolge-Auslese der Compare-Uebersicht — EINE Ableitung.

Epic #1703 Scheibe 7. SPEC: docs/specs/modules/fix_1703_s7_reihenfolge_matrix.md

Die Menge der reihenfolge-faehigen Uebersichts-Groessen wird NICHT getippt. Sie
ist genau die Menge der vom Compare-Katalog AUSGELIEFERTEN Eintraege
(``get_compare_metric_catalog()``), uebersetzt in Renderer-Metrik-IDs — der
Katalog filtert nicht waehlbare Groessen (``cape``, seit #1585) bereits selbst
heraus. Der Waechter erbt damit die Katalog-Entscheidung, statt sie ein zweites
Mal zu fuehren (Muster ``tests/helpers/outlook_columns.py`` aus Scheibe 2).

**Grenze, ausdruecklich** (Lehre Scheibe 1 F001 / Scheibe 2 F001): wer sein Soll
aus demselben Katalog liest wie der Prueflig, bewacht **Vollstaendigkeit**,
nicht **Zuordnung**. Jede Zuordnungsbehauptung braucht deshalb eine eigene
Assertion in der Achse selbst.

Die Auslese-Funktionen unten liefern die REIHENFOLGE der Metrik-Zeilen/-Zellen
je Kanal aus einer fertig gerenderten Ausgabe. Sie sind bewusst tolerant
gegenueber dem Zell-INHALT (der ist Gegenstand von Scheibe 5) und streng
gegenueber der Position — das ist die Achse dieser Scheibe.
"""
from __future__ import annotations

import re

from app.metric_catalog import aggregation_label_de, get_metric
from output.renderers.compare_metric_catalog import (
    COMPARE_METRIC_CATALOG, get_compare_metric_catalog,
)
from output.renderers.compare_metric_ids import FRONTEND_TO_RENDERER_METRIC_ID
from output.renderers.email.compare_html import CV2_METRICS
from tests.helpers.outlook_columns import nicht_waehlbare_compare_keys

# Vakuum-Schutz-Untergrenze (Muster outlook_columns.py:37-40): ein Waechter,
# der ueber eine leere oder stark geschrumpfte Menge iteriert, ist immer gruen
# und bewacht nichts. Gemessen 2026-08-13: 25 ausgelieferte Uebersichts-Groessen.
COMPARE_ORDER_SOLL_MINDESTGROESSE = 20

_CV2_BY_KEY: dict[str, dict] = {m["key"]: m for m in CV2_METRICS}

# Die Warn-Zeile ist keine sortierbare Groesse: sie steht unabhaengig von der
# Auswahl immer als erste HTML-Zeile (#1359 AC-6) und wird deshalb aus jeder
# Reihenfolge-Auslese entfernt.
WARN_LABEL = "Amtliche Warnungen"


def compare_order_soll_metriken(entries: list[dict] | None = None) -> list[str]:
    """Die reihenfolge-faehigen Uebersichts-Groessen als Renderer-Metrik-IDs,
    in Katalog-Reihenfolge — GERECHNET aus dem ausgelieferten Compare-Katalog.

    ``entries`` injiziert eine Testkopie der Katalogzeilen (Vorbild
    ``get_compare_metric_catalog(entries=...)``), damit der Vakuum-Schutz
    unten ohne Monkeypatch des echten Katalogs pruefbar ist.
    """
    return [
        FRONTEND_TO_RENDERER_METRIC_ID[eintrag["key"]]
        for eintrag in get_compare_metric_catalog(entries)
        if eintrag["key"] in FRONTEND_TO_RENDERER_METRIC_ID
    ]


def assert_compare_order_soll_ist_plausibel(
    entries: list[dict] | None = None,
) -> list[str]:
    """Vakuum-Schutz mit ausgesprochener Rechnung: Katalog gross genug, Abzug
    begruendet, jede Groesse in BEIDEN Uebersichts-Zwillingen (HTML-Zeilen-
    Register ``CV2_METRICS`` und Klartext-Tabelle ``_PLAIN_ROWS``) auffindbar.
    Gibt die Soll-Menge zurueck."""
    from output.renderers.comparison import _PLAIN_ROWS

    roh = COMPARE_METRIC_CATALOG if entries is None else entries
    zurueckgehalten = nicht_waehlbare_compare_keys(entries)
    geliefert = get_compare_metric_catalog(entries)
    soll = compare_order_soll_metriken(entries)

    assert soll, (
        "Soll-Menge leer — Vakuum. Jede Achse dieser Scheibe liefe ueber null "
        "Faelle und waere immer gruen."
    )
    assert len(soll) >= COMPARE_ORDER_SOLL_MINDESTGROESSE, (
        f"Vakuum-Schutz: nur {len(soll)} reihenfolge-faehige Uebersichts-"
        f"Groessen ({soll}) — erwartet mindestens "
        f"{COMPARE_ORDER_SOLL_MINDESTGROESSE}. Entweder ist der Compare-Katalog "
        "geschrumpft oder die Soll-Rechnung greift daneben."
    )
    assert len(soll) == len(set(soll)), (
        f"Soll-Menge enthaelt Doppelte: {sorted(soll)} — eine paarweise "
        "Reihenfolge-Pruefung waere damit mehrdeutig"
    )
    assert len(geliefert) == len(roh) - len(zurueckgehalten), (
        f"Rechnung geht nicht auf: {len(roh)} rohe Katalog-Zeilen "
        f"- {len(zurueckgehalten)} nicht waehlbare ({zurueckgehalten}) "
        f"!= {len(geliefert)} ausgelieferte"
    )
    assert zurueckgehalten, (
        "Der Compare-Katalog haelt keine einzige Zeile mehr wegen "
        "selectable=False zurueck (bis 2026-08-13: 'cape_max_jkg', #1585) — "
        "der Filterschritt waere unbewacht, die Rechnung oben trivial."
    )
    ohne_html_zeile = [m for m in soll if m not in _CV2_BY_KEY]
    assert not ohne_html_zeile, (
        f"Ohne HTML-Uebersichtszeile (CV2_METRICS): {ohne_html_zeile} — die "
        "Reihenfolge-Pruefung koennte sie nie sehen"
    )
    plain_ids = {row[0] for row in _PLAIN_ROWS}
    ohne_klartext_zeile = [m for m in soll if m not in plain_ids]
    assert not ohne_klartext_zeile, (
        f"Ohne Klartext-Uebersichtszeile (_PLAIN_ROWS): {ohne_klartext_zeile} "
        "— HTML und Klartext derselben Mail waeren nicht vergleichbar"
    )
    return soll


def partner_von(metric_id: str) -> str:
    """Fester Partner fuer die paarweise Reihenfolge-Pruefung, so gewaehlt,
    dass die beiden sichtbaren Zeilen NIE dieselbe Basis-Beschriftung
    bekommen: ``temp_max``/``temp_min`` teilen sich die Katalog-Groesse
    ``temperature``, alle uebrigen Uebersichts-Groessen sind gegenueber
    ``temperature`` eindeutig (gemessen ueber ``CV2_METRICS``)."""
    return "wind_max" if metric_id in ("temp_max", "temp_min") else "temp_max"


def uebersichts_label(metric_id: str, sichtbare: list[str]) -> str:
    """Die erwartete Zeilen-Beschriftung fuer ``metric_id`` bei genau der
    Auswahl ``sichtbare`` — UNABHAENGIG von ``derive_row_labels()`` aus dem
    Register gerechnet (Muster ``outlook_columns.compare_outlook_soll_
    spalten``: sonst waeren Massstab und Prueflig dieselbe Funktion).

    Regel (PO-Vorgabe #1401/#1453): ausgeschriebener deutscher Registername;
    kommt derselbe Name innerhalb der SICHTBAREN Auswahl mehrfach vor, haengt
    die deutsche Auswertung an."""
    eintrag = _CV2_BY_KEY[metric_id]
    basis = get_metric(eintrag["metric_id"]).label_de
    gleichnamig = [
        m for m in sichtbare
        if m in _CV2_BY_KEY
        and get_metric(_CV2_BY_KEY[m]["metric_id"]).label_de == basis
    ]
    if len(gleichnamig) > 1 and eintrag.get("aggregation"):
        zusatz = aggregation_label_de(eintrag["aggregation"]) or eintrag["aggregation"]
        return f"{basis} {zusatz}"
    return basis


# ---------------------------------------------------------------------------
# Auslese je Kanal — nur die REIHENFOLGE, nie der Zellinhalt
# ---------------------------------------------------------------------------

_HTML_LABEL_RE = re.compile(
    r'font-weight:500;font-size:12px;border-right:1px solid #f0ece1;">([^<]*)</td>'
)


def html_uebersicht_labels(html: str) -> list[str]:
    """Zeilen-Beschriftungen der HTML-Uebersichtstabelle in Render-Reihenfolge,
    ohne die immer erste Warn-Zeile (Muster ``_html_labels()`` aus
    ``tests/unit/test_compare_metric_order.py``)."""
    return [lbl for lbl in _HTML_LABEL_RE.findall(html) if lbl != WARN_LABEL]


def klartext_uebersicht_labels(text: str) -> list[str]:
    """Zeilen-Beschriftungen des ERSTEN Ortsblocks im Klartext-Teil derselben
    Mail, in Render-Reihenfolge (Muster ``_text_labels()`` ebenda)."""
    labels: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped == "STUNDENVERLAUF":
            break
        if not raw.startswith("   ") or stripped.startswith("⚠️") or ":" not in stripped:
            continue
        label = stripped.split(":", 1)[0]
        if label in labels:  # zweiter Ortsblock -> fertig
            break
        labels.append(label)
    return labels


def telegram_zellen(nachricht: str) -> list[str]:
    """Die Metrik-Zellen des ERSTEN Ortsblocks einer Compare-Telegram-
    Nachricht, in Render-Reihenfolge (ganze Zelle, nicht nur das Label —
    mehrwortige Labels wie "Temp max" wuerden sonst abgeschnitten)."""
    for raw in nachricht.splitlines():
        if " · " not in raw and "keine Werte" not in raw:
            continue
        return [
            zelle for zelle in raw.strip().split(" · ")
            if zelle and zelle != "keine Werte"
        ]
    return []


def sms_tokens(nachricht: str) -> list[str]:
    """Die Leerzeichen-getrennten Tokens des ERSTEN Ortsteils einer
    Compare-SMS (Kuerzel UND Wert), in Render-Reihenfolge."""
    _kopf, trenner, rumpf = nachricht.partition(": ")
    if not trenner:
        return []
    return rumpf.split("; ")[0].split(" ")


def sms_index(nachricht: str, kuerzel: str) -> int | None:
    """Position des Kuerzel-Tokens in der Compare-SMS — ueber EXAKTE
    Token-Gleichheit, nicht ueber Teilstring-Suche.

    Begruendung (Muster ``_first_index_starting_with()`` in
    ``test_channel_metric_matrix.py``): die Compare-Kuerzel sind teilweise
    Praefixe voneinander ("N" ist Wortanfang von "NL"/"NS", "C" von "CT"/
    "CL"/"CH"/"CM"). Eine ``in``-Suche schluege am falschen Token an und die
    Reihenfolge-Aussage waere Zufall. ``None`` = Kuerzel nicht in der
    Nachricht (z.B. vom Zeichen-Budget verdraengt)."""
    treffer = [i for i, tok in enumerate(sms_tokens(nachricht)) if tok == kuerzel]
    assert len(treffer) <= 1, (
        f"Kuerzel {kuerzel!r} kommt {len(treffer)}-mal im ersten Ortsteil vor "
        f"— die Positionsaussage waere mehrdeutig.\n{nachricht!r}"
    )
    return treffer[0] if treffer else None


def sms_kuerzel(loc_result, metric_id: str) -> str:
    """Das SMS-Kuerzel-Token, unter dem ``metric_id`` in der Compare-SMS
    erscheint (inkl. Auswertungszeichen ``+``/``-``, #1362 S5b).

    Bewusst aus dem Produktiv-Baustein ``_sms_metric_cell()`` gelesen: er ist
    hier reiner ORTSFINDER fuer eine Reihenfolge-Aussage und selbst
    reihenfolge-blind (er kennt genau eine Groesse). Die Zusicherung dieser
    Achse — dass die Zell-FOLGE der Nutzerliste folgt — entsteht dadurch
    nicht; sie entsteht aus dem paarweisen Vergleich zweier Renderlaeufe.
    Ein zweites, hier getipptes Kuerzel-Vokabular waere die vierte Handkopie
    (s. comparison.py:640-660) und liefe der Katalog-Aenderung hinterher."""
    from output.renderers.comparison import _sms_metric_cell

    zelle = _sms_metric_cell(loc_result, metric_id)
    assert zelle is not None, (
        f"{metric_id!r} hat an diesem Ort keinen SMS-Wert — die Fixture muss "
        "jede geprueften Groesse befuellen, sonst misst der Test das Fehlen "
        "statt der Reihenfolge"
    )
    return zelle.split(" ", 1)[0]
