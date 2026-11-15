"""Parser + Soll (Orakel) fuer den Pruefkatalog Trip von Issue #3047.

SPEC: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md (§1, §2)

**Parser** lesen NUR den tatsaechlich gesendeten Text:

* ``html_tabellen(html)`` -- Etappen- und Nacht-Stundentabellen
  (``<table data-table="resp">``; je Tabelle Desktop- und Mobilfassung).
* ``html_ausblick(html)`` -- 3-Tages-Ausblick (die eine ``<table>`` mit
  ``<thead>`` ausserhalb der Stundentabellen).
* ``klartext_tabellen(text)`` -- Stundentabellen im Klartext, Spalten ueber
  die Strichzeile fest abgegrenzt (Zellen mit Leerzeichen wie ``20 W``
  bleiben ganz).
* ``klartext_ausblick(text, tage)`` -- Ausblick im Klartext UND im
  Kompaktformat (``Label Wert``-Paare, durch zwei Leerzeichen getrennt).
* ``zellform(text, fragment)`` -- ``"zahl"`` | ``"einfach"`` | ``"ampel"``
  (Zahl mit HTML-Ampelpunkt) | ``None`` (Platzhalter, nicht ablesbar).

**Soll** wird aus dem ROHEN Trip-JSON und dem statischen Register gebildet
(``app.metric_catalog``: ``col_label``, ``has_friendly_format``,
``OUTLOOK_FRIENDLY_CAPABLE``) -- nie aus ``resolve_*``-Produktfunktionen
(Spiegel-Test-Verbot, CLAUDE.md). Die Kaskade der Stundentabellen liefert das
bestehende eigenstaendige Orakel ``erwartete_kaskade`` (#2422).
"""
from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass, field
from typing import Optional

from app.metric_catalog import OUTLOOK_FRIENDLY_CAPABLE, _METRICS
from tests.helpers.einstellung_auslieferung_orakel import erwartete_kaskade

# ---------------------------------------------------------------------------
# Register (statisch, nur Daten)
# ---------------------------------------------------------------------------

#: Spaltenbeschriftung -> Kennung (Protokoll-Token, nie uebersetzt).
LABEL_ZU_ID: dict[str, str] = {m.col_label: m.id for m in _METRICS}
_HAT_EINFACH: dict[str, bool] = {m.id: m.has_friendly_format for m in _METRICS}
_SELECTABLE: frozenset[str] = frozenset(m.id for m in _METRICS if m.selectable)

#: Strukturspalten ohne Metrik (Zeitspalte in beiden Sprachen, Risiko-Punkt,
#: Tag des Ausblicks, Verlaesslichkeits-Wort). Alles andere MUSS eine Metrik
#: sein, sonst scheitert der Parser laut.
STRUKTUR_LABELS = frozenset({"Time", "Zeit", "Zt", "Hr", "Risk", "Risiko", "Tag", "Day", "ACC"})

#: Issue #814: Groessen mit HTML-Ampelpunkt statt eigener Einfach-Form. Ihr
#: Klartext zeigt bei Einfach die Zahl -- gewollte Ausnahme (Fallliste
#: ``ausnahme``, Verweis #814). Register-Wissen, nicht aus dem Renderer gelesen.
AMPEL_GROESSEN = frozenset({"wind", "gust", "precipitation", "rain_probability"})

#: Groessen, die der 3-Tages-Ausblick als Spalte fuehren kann (Katalog-Stand
#: 2026-11, ``summary_fields`` belegt). Statisch, damit das Soll nicht aus
#: ``derived_aggregations`` (Produkt) entsteht.
AUSBLICK_FAEHIG = frozenset({
    "temperature", "wind_chill", "humidity", "dewpoint", "wind", "gust",
    "wind_direction", "precipitation", "rain_probability", "thunder",
    "snowfall_limit", "precip_type", "cloud_total", "cloud_low", "cloud_mid",
    "cloud_high", "visibility", "sunshine", "uv_index", "pressure",
    "freezing_level", "snow_depth", "fresh_snow",
})

#: Ausblick-Groessen ohne Einfach-Form (Spec §2 Punkt 3, #814 AC-5):
#: Temperatur/gefuehlte Temperatur sind eine Spanne, Gewitter zeigt roh schon
#: das Stufenwort, Sicht hat keine Einfach-Form.
AUSBLICK_OHNE_EINFACH = frozenset({"temperature", "wind_chill", "thunder", "visibility"})

_BUCKET_RANG = {"primary": 0, "secondary": 1}


# ---------------------------------------------------------------------------
# Zellform
# ---------------------------------------------------------------------------

_PLATZHALTER = {"", "-", "–", "?"}
_ZAHL_RE = re.compile(
    r"^-?\d+(?:[.,]\d+)?(?:/-?\d+(?:[.,]\d+)?)?\s*(?:°C|°|%|km/h|mm|cm|m|hPa)?"
    r"(?:\s+(?:N|NE|E|SE|S|SW|W|NW|NO|O|SO))?$"
)
_PUNKT_RE = re.compile(r"border-radius:\s*50%")
_TAG_RE = re.compile(r"<[^>]+>")


def _text(fragment: str) -> str:
    return _html.unescape(re.sub(r"\s+", " ", _TAG_RE.sub(" ", fragment))).strip()


def html_text(html: str) -> str:
    """Sichtbarer Text eines HTML-Teils (Tags entfernt, Leerraum vereinheitlicht)."""
    return _text(html)


def zellform(text: str, fragment: Optional[str] = None) -> Optional[str]:
    """``zahl`` (Roh), ``einfach`` (Symbol/Wort/Ampelpunkt allein), ``ampel``
    (Zahl plus HTML-Ampelpunkt, #814) oder ``None`` (Platzhalter)."""
    punkt = bool(fragment and _PUNKT_RE.search(fragment))
    t = text.strip()
    if t in _PLATZHALTER:
        return "einfach" if punkt else None
    if _ZAHL_RE.match(t):
        return "ampel" if punkt else "zahl"
    return "einfach"


# ---------------------------------------------------------------------------
# Tabellen-Modell
# ---------------------------------------------------------------------------


@dataclass
class Tabelle:
    """Eine gelesene Tabelle: Metrik-Spalten in Mail-Reihenfolge und je Zeile
    die Zellen dieser Spalten (``zellen[i][j]`` = Zeile i, Spalte j)."""
    art: str
    labels: list[str]
    spalten: list[str]
    zellen: list[list[str]] = field(default_factory=list)
    fragmente: list[list[Optional[str]]] = field(default_factory=list)

    def formen(self) -> dict[str, Optional[str]]:
        """Zellform je Metrik aus der ersten Zeile mit ablesbarer Form."""
        out: dict[str, Optional[str]] = {}
        for j, mid in enumerate(self.spalten):
            form = None
            for i, zeile in enumerate(self.zellen):
                frag = self.fragmente[i][j] if self.fragmente else None
                form = zellform(zeile[j], frag)
                if form is not None:
                    break
            out[mid] = form
        return out

    def spalte(self, mid: str) -> list[str]:
        j = self.spalten.index(mid)
        return [z[j] for z in self.zellen]


def _metrik_spalten(labels: list[str], art: str) -> list[tuple[int, str]]:
    """(Index, Kennung) der Metrik-Spalten; unbekannte Beschriftung = Fehler."""
    out = []
    for i, label in enumerate(labels):
        if label in STRUKTUR_LABELS:
            continue
        mid = LABEL_ZU_ID.get(label)
        assert mid is not None, f"{art}: unbekannte Spaltenbeschriftung {label!r} in {labels!r}"
        out.append((i, mid))
    return out


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

_TABLE_RE = re.compile(r"<table\b[^>]*>.*?</table>", re.DOTALL)
_TH_RE = re.compile(r"<th\b[^>]*>(.*?)</th>", re.DOTALL)
_TR_RE = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.DOTALL)
_TD_RE = re.compile(r"<td\b[^>]*>(.*?)</td>", re.DOTALL)


def _html_tabelle(block: str, art: str) -> Tabelle:
    kopf = re.search(r"<thead>(.*?)</thead>", block, re.DOTALL)
    assert kopf, f"{art}: kein <thead>"
    labels = [_text(t) for t in _TH_RE.findall(kopf.group(1))]
    idx = _metrik_spalten(labels, art)
    rumpf = block[kopf.end():]
    tab = Tabelle(art=art, labels=labels, spalten=[mid for _, mid in idx])
    for tr in _TR_RE.findall(rumpf):
        tds = _TD_RE.findall(tr)
        if len(tds) != len(labels):
            continue
        tab.zellen.append([_text(tds[i]) for i, _ in idx])
        tab.fragmente.append([tds[i] for i, _ in idx])
    return tab


def html_tabellen(html: str) -> dict[str, list[Tabelle]]:
    """``{"etappe": [...], "nacht": [...]}`` -- alle Stundentabellen des
    HTML-Teils (Desktop- und Mobilfassung je einmal). Nacht = vor der Tabelle
    steht seit der vorigen Stundentabelle der Mond (🌙, sprachneutral)."""
    out: dict[str, list[Tabelle]] = {"etappe": [], "nacht": []}
    letzte = 0
    for m in _TABLE_RE.finditer(html):
        if 'data-table="resp"' not in m.group(0)[:200]:
            continue
        art = "nacht" if "🌙" in html[letzte:m.start()] else "etappe"
        if "<thead>" in m.group(0):
            out[art].append(_html_tabelle(m.group(0), art))
        letzte = m.end()
    return out


def html_ausblick(html: str) -> Optional[Tabelle]:
    """Die Ausblick-Tabelle (``<thead>`` ohne ``data-table="resp"``) oder None."""
    treffer = [
        m.group(0) for m in _TABLE_RE.finditer(html)
        if "<thead>" in m.group(0) and 'data-table="resp"' not in m.group(0)[:200]
    ]
    assert len(treffer) <= 1, f"mehr als eine Ausblick-Tabelle: {len(treffer)}"
    return _html_tabelle(treffer[0], "ausblick") if treffer else None


# ---------------------------------------------------------------------------
# Klartext
# ---------------------------------------------------------------------------

_STRICH_RE = re.compile(r"^\s*-{3,}(?:\s+-{3,})+\s*$")


def _spannen(strichzeile: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in re.finditer(r"-+", strichzeile)]


def _schneiden(zeile: str, spannen: list[tuple[int, int]]) -> list[str]:
    out = []
    for k, (a, _e) in enumerate(spannen):
        ende = spannen[k + 1][0] if k + 1 < len(spannen) else len(zeile)
        out.append(zeile[a:ende].strip())
    return out


def klartext_tabellen(text: str) -> dict[str, list[Tabelle]]:
    """``{"etappe": [...], "nacht": [...]}`` aus dem Klartext. Etappe = die
    zuletzt davor stehende ``━━``-Ueberschrift beginnt mit ``━━ Segment``;
    jede andere Ueberschrift (Nacht am Ziel) zaehlt als Nacht."""
    zeilen = text.splitlines()
    out: dict[str, list[Tabelle]] = {"etappe": [], "nacht": []}
    ueberschrift = ""
    for i, zeile in enumerate(zeilen):
        if zeile.startswith("━━"):
            ueberschrift = zeile
        if not _STRICH_RE.match(zeile) or i == 0:
            continue
        art = "etappe" if ueberschrift.startswith("━━ Segment") else "nacht"
        spannen = _spannen(zeile)
        labels = _schneiden(zeilen[i - 1], spannen)
        idx = _metrik_spalten(labels, art)
        tab = Tabelle(art=art, labels=labels, spalten=[mid for _, mid in idx])
        for daten in zeilen[i + 1:]:
            if not daten.startswith("  ") or not daten.strip() or daten.strip().startswith("*"):
                break
            werte = _schneiden(daten, spannen)
            tab.zellen.append([werte[k] for k, _ in idx])
        out[art].append(tab)
    return out


def klartext_ausblick(text: str, tage: tuple[str, ...]) -> Optional[Tabelle]:
    """Ausblick-Zeilen (Klartext und Kompakt): Zeilen, die mit einem der
    ``tage`` beginnen; Felder durch zwei Leerzeichen getrennt, je Feld
    ``Label Wert``. Feld ohne Metrik-Label (Etappenname) wird uebersprungen,
    ``ACC`` ist Struktur. None, wenn keine Ausblick-Zeile vorkommt."""
    tab: Optional[Tabelle] = None
    for zeile in text.splitlines():
        felder = re.split(r"\s{2,}", zeile.strip())
        if not felder or felder[0] not in tage or len(felder) < 2:
            continue
        spalten, zellen = [], []
        for feld in felder[1:]:
            label, _, wert = feld.partition(" ")
            if label in STRUKTUR_LABELS:
                continue
            mid = LABEL_ZU_ID.get(label)
            if mid is None:
                continue  # Etappenname
            spalten.append(mid)
            zellen.append(wert.strip())
        if tab is None:
            tab = Tabelle(art="ausblick", labels=[], spalten=spalten)
        assert spalten == tab.spalten, f"Ausblick-Zeilen uneinheitlich: {spalten} vs {tab.spalten}"
        tab.zellen.append(zellen)
    return tab


# ---------------------------------------------------------------------------
# Soll aus dem rohen Trip-JSON
# ---------------------------------------------------------------------------


def _report_typ_an(mc: dict, report_type: str) -> bool:
    flag = mc.get(f"{report_type}_enabled")
    if flag is not None:
        return bool(flag)
    return bool(mc.get("enabled", True))


def soll_grundauswahl(trip: dict, report_type: str = "evening") -> list[str]:
    """Die Grundauswahl (globale ``metrics``) in EINGESTELLTER Folge
    (Bucket-Rang, dann ``order``) -- nie in Array-/Katalogfolge."""
    eintraege = [
        mc for mc in trip["display_config"].get("metrics") or []
        if mc["metric_id"] in _SELECTABLE and _report_typ_an(mc, report_type)
    ]
    eintraege.sort(key=lambda mc: (_BUCKET_RANG.get(mc.get("bucket", "primary"), 2),
                                   mc.get("order", 0)))
    return [mc["metric_id"] for mc in eintraege]


def _windrichtung_verschmolzen(kaskade: list[tuple[str, bool]]) -> bool:
    """Gewollte Ausnahme #435: Windrichtung auf Einfach (Skala) verschmilzt in
    die Wind-Zelle (``20 W``), wenn Wind in derselben Liste steht."""
    ids = dict(kaskade)
    return "wind" in ids and ids.get("wind_direction") is True


def soll_stundenspalten(trip: dict, report_type: str = "evening") -> list[str]:
    """Spalten der Etappen- und Nachttabelle (E-Mail-Liste) in Mail-Folge."""
    kaskade = erwartete_kaskade(trip, "email_html", report_type)
    ids = [mid for mid, _ in kaskade]
    if _windrichtung_verschmolzen(kaskade):
        ids.remove("wind_direction")
    return ids


def soll_stundenformen(trip: dict, teil: str, report_type: str = "evening") -> dict[str, str]:
    """Erwartete Zellform je Spalte der Stundentabellen. ``teil``:
    ``"html"`` | ``"klartext"``.

    * Einfach + Katalog-Einfachform -> ``einfach``.
    * Einfach + Ampel-Groesse (#814) -> HTML ``einfach`` (Ampelpunkt allein),
      Klartext ``zahl`` (gewollte Ausnahme, Spec §2 Punkt 3).
    * Einfach ohne Einfachform (z. B. UV) -> ``zahl`` (AC-8).
    * Roh -> ``zahl``.
    """
    kaskade = erwartete_kaskade(trip, "email_html", report_type)
    out = {}
    for mid, einfach in kaskade:
        if mid not in soll_stundenspalten(trip, report_type):
            continue
        if einfach and _HAT_EINFACH.get(mid):
            out[mid] = "einfach"
        elif einfach and mid in AMPEL_GROESSEN:
            out[mid] = "einfach" if teil == "html" else "zahl"
        else:
            out[mid] = "zahl"
    # #435: eine verschmolzene Wind-Zelle ("20 W") liest ``zellform`` als Zahl
    # mit Richtungs-Suffix -- Wind bleibt "zahl".
    return out


_FEHLT = object()


def soll_ausblick(trip: dict, report_type: str = "evening") -> Optional[list[str]]:
    """Ausblick-Spalten laut rohem JSON; ``None`` = Block entfaellt.

    * ``outlook_metrics == []`` -> entfaellt (bewusst leer).
    * fehlt/``None`` -> die ganze Grundauswahl in EINGESTELLTER Folge (AC-4).
    * gefuellt -> gespeicherte Folge, geschnitten mit der Grundauswahl
      (ADR-0050); bleibt nichts uebrig -> volle Grundauswahl (AC-10).
    """
    dc = trip["display_config"]
    gespeichert = dc.get("outlook_metrics", _FEHLT)
    grund = [m for m in soll_grundauswahl(trip, report_type) if m in AUSBLICK_FAEHIG]
    if gespeichert == []:
        return None
    if gespeichert is _FEHLT or gespeichert is None:
        return grund
    ids = [g if isinstance(g, str) else g["metric_id"] for g in gespeichert]
    aktiv = []
    for mid in ids:
        if mid in grund and mid not in aktiv:
            aktiv.append(mid)
    return aktiv or grund


def soll_ausblickformen(trip: dict, spalten: list[str]) -> dict[str, Optional[str]]:
    """Erwartete Zellform je Ausblick-Spalte: Einfach nur, wenn in
    ``outlook_metric_formats`` gesetzt UND die Groesse eine Ausblick-
    Einfachform hat (``OUTLOOK_FRIENDLY_CAPABLE``). Groessen ohne Einfachform
    (Spec §2 Punkt 3) liefern ``None`` = keine Formaussage (eigene
    Ausnahme-Faelle)."""
    fmts = trip["display_config"].get("outlook_metric_formats") or {}
    out: dict[str, Optional[str]] = {}
    for mid in spalten:
        if mid in AUSBLICK_OHNE_EINFACH:
            out[mid] = None
        elif fmts.get(mid) and mid in OUTLOOK_FRIENDLY_CAPABLE:
            out[mid] = "einfach"
        else:
            out[mid] = "zahl"
    return out
