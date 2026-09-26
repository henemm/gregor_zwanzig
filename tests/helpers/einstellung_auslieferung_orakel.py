"""Orakel + Ausnahme-Register + Parser + Matrix fuer Issue #2422 S1
("Einstellung = Auslieferung").

SPEC: docs/specs/modules/fix_2422_einstellung_gleich_auslieferung.md

**Orakel-Unabhaengigkeit (PFLICHT):** Dieses Modul importiert NICHTS aus
``src/app/models.py`` oder ``src/output/*`` fuer die ERWARTUNGSBILDUNG --
weder ``get_metrics_for_channel`` noch ``_sorted_by_layout`` noch
``_clip_to_global_maximum``. Die Kaskade (globales Maximum ∩ Kanal-Layout,
sortiert nach Bucket+Order) wird HIER eigenstaendig aus dem rohen
``json.load``-Dict nachgebaut (Orakel-Regel der Spec). Nur der statische
Metrik-KATALOG (``app.metric_catalog``) wird gelesen -- das ist Register-Wissen
(Daten), keine Kaskaden-Entscheidungsfunktion, und fuer AC-11 ausdruecklich
vorgeschrieben ("iteriert den Metrik-Katalog gefiltert auf selectable=true").

Kuerzel-Register (``SMS_SYMBOL_BY_METRIC``/``SMS_MULTI_SYMBOLS_BY_METRIC``)
wird AUSSCHLIESSLICH zum PARSEN des tatsaechlich gesendeten Textes verwendet,
niemals zur Erwartungsbildung (AC-4).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from app.metric_catalog import (
    SMS_MULTI_SYMBOLS_BY_METRIC, SMS_SYMBOL_BY_METRIC, _METRICS, get_metric,
)

# ---------------------------------------------------------------------------
# Ausnahme-Register
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AusnahmeEintrag:
    metrik: str        # metric_id, oder "*" fuer eine kanalweite Ausnahme (B2)
    kanal: str          # "email_html" | "email_plain" | "telegram_rich" | "telegram_kurzform" | "sms" | "premium_sms"
    dimension: str      # "erscheint" | "reihenfolge" | "roh_einfach"
    befund: str         # Pflichtfeld, z.B. "B1", "#2412" -- keine leere Referenz
    grund: str          # Pflichtfeld -- keine leere Begruendung
    befristet: bool     # True = Fix in eigener Scheibe geplant


class RegisterValidierungsFehler(Exception):
    """AC-8: ein Register-Eintrag ohne befund/grund blockt VOR der Matrix."""


#: F006/F007 (Adversary-Runde 4+5): ``metrik="*"`` ist laut Spec (Abschnitt
#: "Ausnahme-Register") ausschliesslich fuer den kanalweiten Befund B2
#: vorgesehen -- UND dort nur fuer den in der Spec benannten Scope
#: (sms/telegram_kurzform/premium_sms x roh_einfach). Ein metrikscharfer
#: Eintrag darf sich weder unbemerkt auf "*" verbreitern (F006) noch als
#: Wildcard in einen fremden (Kanal, Dimension)-Scope hinein deklariert
#: werden (F007) -- beides wuerde die Ausnahme fuer ALLE Metriken einer
#: Stelle oeffnen statt fuer die eine begruendete.
KANALWEITE_BEFUNDE: "dict[str, frozenset[tuple[str, str]]]" = {
    "B2": frozenset({
        ("sms", "roh_einfach"),
        ("telegram_kurzform", "roh_einfach"),
        ("premium_sms", "roh_einfach"),
    }),
}


def register_validieren(register: "list[AusnahmeEintrag]") -> None:
    for eintrag in register:
        if not eintrag.befund or not eintrag.befund.strip():
            raise RegisterValidierungsFehler(
                f"Register-Eintrag ohne 'befund': {eintrag!r}"
            )
        if not eintrag.grund or not eintrag.grund.strip():
            raise RegisterValidierungsFehler(
                f"Register-Eintrag ohne 'grund': {eintrag!r}"
            )
        if eintrag.metrik == "*":
            if eintrag.befund not in KANALWEITE_BEFUNDE:
                raise RegisterValidierungsFehler(
                    f"Register-Eintrag mit metrik='*' aber befund={eintrag.befund!r} "
                    f"ist nicht erlaubt -- 'metrik=\"*\"' ist laut Spec ausschliesslich "
                    f"fuer die kanalweiten Befunde {sorted(KANALWEITE_BEFUNDE)} "
                    f"vorgesehen: {eintrag!r}"
                )
            scope = KANALWEITE_BEFUNDE[eintrag.befund]
            if (eintrag.kanal, eintrag.dimension) not in scope:
                raise RegisterValidierungsFehler(
                    f"Register-Eintrag mit metrik='*' und befund={eintrag.befund!r} "
                    f"liegt ausserhalb des fuer diesen Befund erlaubten Scopes "
                    f"{sorted(scope)} -- (kanal, dimension)="
                    f"{(eintrag.kanal, eintrag.dimension)!r} ist nicht abgedeckt: "
                    f"{eintrag!r}"
                )


#: S1-Startbefuellung (TDD GREEN, /50). Deckt exakt die durch die zwei
#: Golden-Trip-Varianten tatsaechlich ausgeloesten Befunde B1/B2/B3/B5 sowie
#: die strukturelle Telegram-7er-Tabellenlimit-Ausnahme (``gust``) ab --
#: siehe ``docs/artifacts/fix-2422-konfig-auslieferung-testluecken/
#: red-handoff.md``.
AUSNAHMEN: "list[AusnahmeEintrag]" = [
    # B1: wind_chill ohne SMS-Kuerzel faellt in Kurzform/SMS/Premium-SMS
    # still weg (KHW 403). Variantenwahl (eigenes Kuerzel vs. Editor-Hinweis)
    # ist explizit NICHT Teil von S1 -- eigene Fix-Scheibe S6+.
    AusnahmeEintrag(
        metrik="wind_chill", kanal="telegram_kurzform", dimension="erscheint",
        befund="B1",
        grund=(
            "wind_chill hat kein Kuerzel in SMS_SYMBOL_BY_METRIC/"
            "SMS_MULTI_SYMBOLS_BY_METRIC (#1887 E6) und faellt deshalb im "
            "Kurzform-Text still weg, obwohl es im SMS-Kanal-Layout aktiv "
            "ist (KHW 403, #2422). Fix-Scheibe S6+ (Variantenwahl V1/V2 "
            "durch PO)."
        ),
        befristet=True,
    ),
    AusnahmeEintrag(
        metrik="wind_chill", kanal="sms", dimension="erscheint",
        befund="B1",
        grund=(
            "wind_chill hat kein Kuerzel in SMS_SYMBOL_BY_METRIC/"
            "SMS_MULTI_SYMBOLS_BY_METRIC (#1887 E6) und faellt deshalb im "
            "SMS-Text still weg, obwohl es im SMS-Kanal-Layout aktiv ist "
            "(KHW 403, #2422). Fix-Scheibe S6+ (Variantenwahl V1/V2 durch "
            "PO)."
        ),
        befristet=True,
    ),
    AusnahmeEintrag(
        metrik="wind_chill", kanal="premium_sms", dimension="erscheint",
        befund="B1",
        grund=(
            "wind_chill hat kein Kuerzel in SMS_SYMBOL_BY_METRIC/"
            "SMS_MULTI_SYMBOLS_BY_METRIC (#1887 E6) und faellt deshalb im "
            "Premium-SMS-Text still weg, obwohl es im SMS-Kanal-Layout aktiv "
            "ist (KHW 403, #2422). Fix-Scheibe S6+ (Variantenwahl V1/V2 "
            "durch PO)."
        ),
        befristet=True,
    ),
    # B2 (kanalweit, metrik="*"): Kurzform/SMS/Premium-SMS ignorieren
    # Roh/Einfach, weil MetricSpec kein format_mode kennt. Eigene
    # Fix-Scheibe S6+.
    AusnahmeEintrag(
        metrik="*", kanal="sms", dimension="roh_einfach",
        befund="B2",
        grund=(
            "SMS-Zellbau kennt kein format_mode auf MetricSpec-Ebene -- "
            "Roh/Einfach wird kanalweit ignoriert (z.B. cloud_total, "
            "sunshine, #2422). Fix in eigener Scheibe S6+."
        ),
        befristet=True,
    ),
    AusnahmeEintrag(
        metrik="*", kanal="telegram_kurzform", dimension="roh_einfach",
        befund="B2",
        grund=(
            "Telegram-Kurzform-Zellbau kennt kein format_mode auf "
            "MetricSpec-Ebene -- Roh/Einfach wird kanalweit ignoriert (z.B. "
            "cloud_total, sunshine, #2422). Fix in eigener Scheibe S6+."
        ),
        befristet=True,
    ),
    AusnahmeEintrag(
        metrik="*", kanal="premium_sms", dimension="roh_einfach",
        befund="B2",
        grund=(
            "Premium-SMS-Zellbau kennt kein format_mode auf MetricSpec-"
            "Ebene -- Roh/Einfach wird kanalweit ignoriert (z.B. "
            "cloud_total, sunshine, #2422). Fix in eigener Scheibe S6+."
        ),
        befristet=True,
    ),
    # B3: Telegram rich erbt Roh/Einfach aus dem E-Mail-Layout statt dem
    # eigenen (trip_report.py build_friendly_keys nach Email-Kollabierung).
    # Nutzersichtbar + eigenstaendig -> eigenes GitHub-Issue #2429.
    AusnahmeEintrag(
        metrik="cloud_total", kanal="telegram_rich", dimension="roh_einfach",
        befund="B3",
        grund=(
            "Telegram rich erbt seine Roh/Einfach-Entscheidung aus der "
            "geteilten _friendly_keys-Instanz des E-Mail-Formatters "
            "(trip_report.py:142 build_friendly_keys(dc) nach Email-"
            "Kollabierung) statt aus dem eigenen Telegram-Layout. Eigenes "
            "Issue #2429."
        ),
        befristet=True,
    ),
    # B5: wind_direction (Skalenmodus) + wind erzeugt eine Geisterspalte
    # "WD" mit Platzhalter in Telegram rich. Eigene Fix-Scheibe S6+.
    AusnahmeEintrag(
        metrik="wind_direction", kanal="telegram_rich", dimension="erscheint",
        befund="B5",
        grund=(
            "wind_direction im Skalenmodus zusammen mit wind erzeugt in "
            "Telegram rich eine eigene Geisterspalte 'WD', deren Zelle nur "
            "Platzhalter ('-') traegt (should_merge_wind_dir haengt den "
            "Wert stattdessen an die wind-Zelle, #2422). Fix in eigener "
            "Scheibe S6+."
        ),
        befristet=True,
    ),
    # Strukturell (kein Register-verfallendes Produktdefizit, sondern eine
    # bewusste Design-Grenze): Telegram-Tabellen sind auf 8 Gesamtspalten
    # begrenzt (Zeit + 7 Metriken, CHANNEL_LIMITS["telegram"]["max_table_cols"]
    # = 8, src/output/renderers/channel_layout.py:46-55, eingefuehrt mit
    # Issue #360 "kanal-bewusster Renderer fuer Signal/Telegram", Commit
    # 5f9b57f9). gust liegt in den Goldens hinter der 7er-Grenze und wird in
    # Telegram rich deshalb verdraengt (demoted), erscheint aber laut Orakel
    # weiterhin als "aktiv" (AC-5: die Orakel-Regel kennt das Limit nicht).
    AusnahmeEintrag(
        metrik="gust", kanal="telegram_rich", dimension="erscheint",
        befund="Issue #360 (Telegram-7er-Tabellenlimit)",
        grund=(
            "Telegram begrenzt Tabellen strukturell auf 8 Gesamtspalten "
            "(Zeit + 7 Metriken, channel_layout.py:46-55, CHANNEL_LIMITS"
            "['telegram']['max_table_cols']=8, eingefuehrt mit Issue #360, "
            "Commit 5f9b57f9). gust wird deshalb ab der 8. Kandidaten-"
            "Metrik verdraengt (demoted) -- bewusste Design-Grenze, kein "
            "Konfigurations-Fehler, daher nicht befristet."
        ),
        befristet=False,
    ),
]


# ---------------------------------------------------------------------------
# Kanaele / Dimensionen
# ---------------------------------------------------------------------------

KANAELE = (
    "email_html", "email_plain", "telegram_rich", "telegram_kurzform",
    "sms", "premium_sms",
)
DIMENSIONEN = ("erscheint", "reihenfolge", "roh_einfach")

#: Quell-Layoutschluessel je Kanal (Orakel-Regel: Kurzstil/Premium <- SMS).
_LAYOUT_KEY_JE_KANAL = {
    "email_html": "email", "email_plain": "email",
    "telegram_rich": "telegram",
    "telegram_kurzform": "sms", "sms": "sms", "premium_sms": "sms",
}

#: Welche Kanaele ein Golden je nach Versand-Schaltern tatsaechlich erreicht.
def erreichbare_kanaele(report_config: dict) -> tuple[str, ...]:
    kanaele = ["email_html", "email_plain"]
    if report_config.get("telegram_style") == "kurzform":
        kanaele.append("telegram_kurzform")
    else:
        kanaele.append("telegram_rich")
    if report_config.get("send_sms"):
        kanaele.append("sms")
    if report_config.get("send_premium_sms"):
        kanaele.append("premium_sms")
    return tuple(kanaele)


# ---------------------------------------------------------------------------
# Katalog-Register (nur Parsen/AC-11-Aufzaehlung, keine Kaskaden-Entscheidung)
# ---------------------------------------------------------------------------

_SELECTABLE_IDS: tuple[str, ...] = tuple(m.id for m in _METRICS if m.selectable)
_COL_LABEL_TO_ID: dict[str, str] = {m.col_label: m.id for m in _METRICS}
_COMPACT_LABEL_TO_ID: dict[str, str] = {m.compact_label: m.id for m in _METRICS}
_HAS_FRIENDLY: dict[str, bool] = {m.id: m.has_friendly_format for m in _METRICS}

#: Symbol -> metric_id (invers zu SMS_SYMBOL_BY_METRIC/SMS_MULTI_SYMBOLS_BY_METRIC).
_SMS_SYMBOL_TO_METRIC: dict[str, str] = {}
for _mid, _sym in SMS_SYMBOL_BY_METRIC.items():
    _SMS_SYMBOL_TO_METRIC[_sym] = _mid
for _mid, _syms in SMS_MULTI_SYMBOLS_BY_METRIC.items():
    for _sym in _syms:
        _SMS_SYMBOL_TO_METRIC[_sym] = _mid


def alle_waehlbaren_metrik_ids() -> tuple[str, ...]:
    """AC-11: alle Katalog-Metriken mit ``selectable=true`` (Issue #710:
    ``confidence_pct`` bereits per ``selectable=False`` ausgeschlossen)."""
    return _SELECTABLE_IDS


def hat_roh_einfach_dimension(metric_id: str) -> bool:
    return _HAS_FRIENDLY.get(metric_id, False)


# ---------------------------------------------------------------------------
# Orakel: eigenstaendige Kaskaden-Rekonstruktion aus dem rohen Golden-Dict
# ---------------------------------------------------------------------------

_BUCKET_RANK = {"primary": 0, "secondary": 1}


def _behalten_fuer_report_typ(mc: dict, report_type: str) -> bool:
    me, ee = mc.get("morning_enabled"), mc.get("evening_enabled")
    if report_type == "morning":
        if me is True:
            return True
        if me is False:
            return False
        return bool(mc.get("enabled", True))
    if report_type == "evening":
        if ee is True:
            return True
        if ee is False:
            return False
        return bool(mc.get("enabled", True))
    return bool(mc.get("enabled", True))


def _global_erlaubte_ids(golden: dict, report_type: str) -> Optional[set[str]]:
    """D4: leere globale Liste -> None ("kein Maximum definiert")."""
    metrics = golden["display_config"].get("metrics") or []
    if not metrics:
        return None
    erlaubt = set()
    for mc in metrics:
        mid = mc["metric_id"]
        if mid not in _SELECTABLE_IDS:
            continue
        if _behalten_fuer_report_typ(mc, report_type):
            erlaubt.add(mid)
    return erlaubt


def erwartete_kaskade(
    golden: dict, kanal: str, report_type: str = "evening",
) -> list[tuple[str, bool]]:
    """Erwartete (metric_id, friendly)-Liste in gespeicherter Reihenfolge fuer
    ``kanal`` -- EIGENSTAENDIGE Kaskaden-Rekonstruktion (kein Import von
    ``get_metrics_for_channel``/``_sorted_by_layout``).

    Kernregeln (nicht ausnahmefaehig, direkt in der Regel -- B6/B4):
    - Kanal-Layout ist Teilmenge des globalen Maximums (``display_config.
      metrics``), nie eine Ergaenzung.
    - sms/telegram_kurzform/premium_sms lesen IMMER ``channel_layouts.sms``.
    """
    layout_key = _LAYOUT_KEY_JE_KANAL[kanal]
    dc = golden["display_config"]
    global_erlaubt = _global_erlaubte_ids(golden, report_type)
    layouts = dc.get("channel_layouts") or {}

    if layout_key in layouts:
        kandidaten = layouts[layout_key]
        schneiden = True
    else:
        kandidaten = dc.get("metrics") or []
        schneiden = False  # globale Liste IST das Maximum, kein Schnitt gegen sich selbst

    gefiltert = []
    for mc in kandidaten:
        mid = mc["metric_id"]
        if mid not in _SELECTABLE_IDS:
            continue
        if not _behalten_fuer_report_typ(mc, report_type):
            continue
        if schneiden and global_erlaubt is not None and mid not in global_erlaubt:
            continue
        gefiltert.append(mc)

    gefiltert.sort(
        key=lambda mc: (_BUCKET_RANK.get(mc.get("bucket", "primary"), 2), mc.get("order", 0))
    )
    return [(mc["metric_id"], bool(mc.get("use_friendly_format", True))) for mc in gefiltert]


# ---------------------------------------------------------------------------
# Parser -- lesen NUR den tatsaechlich gesendeten Text
# ---------------------------------------------------------------------------

_HEADER_TRENNER_RE = re.compile(r"^\s*-{3,}(\s+-{3,})+\s*$")
_PLATZHALTER = {"-", "–", "?", ""}
#: Deutsche Himmelsrichtungs-Kuerzel -- narrow.py haengt sie an den Windwert
#: an ("20 W"), wenn wind_direction im Skalenmodus gemeinsam mit wind aktiv
#: ist (should_merge_wind_dir). Fuer die Tabellen-Tokenisierung wird ein
#: solches Kuerzel wieder an sein Zahlwort angehaengt.
_HIMMELSRICHTUNGEN = {"N", "NE", "E", "SE", "S", "SW", "W", "NW"}


def _ist_numerisch(wert: str) -> bool:
    return bool(re.fullmatch(r"-?\d+(\.\d+)?%?", wert))


def _zell_modus(wert: str) -> Optional[str]:
    """"raw" | "friendly" | None (Platzhalter/Null-Form -- kein Modus ablesbar)."""
    if wert in _PLATZHALTER:
        return None
    return "raw" if _ist_numerisch(wert) else "friendly"


def _tabellen_tokens_mit_richtungs_merge(zeile: str, spaltenzahl: int) -> list[str]:
    """``zeile.split()``, mit Ruecklauf fuer die Windrichtungs-Verschmelzung
    (narrow.py: Windwert + Himmelsrichtung landen als EINE Zelle mit
    innerem Leerzeichen, z.B. "20 W"). Nur wenn genau EIN Token zu viel da
    ist UND eines davon ein Himmelsrichtungs-Kuerzel ist, wird es an das
    VORANGEHENDE Token zurueckgehaengt."""
    tokens = zeile.split()
    if len(tokens) == spaltenzahl:
        return tokens
    if len(tokens) == spaltenzahl + 1:
        for i, tok in enumerate(tokens):
            if tok in _HIMMELSRICHTUNGEN and i > 0:
                merged = tokens[:i - 1] + [f"{tokens[i-1]} {tok}"] + tokens[i + 1:]
                if len(merged) == spaltenzahl:
                    return merged
    return tokens


def _email_tabellen_kopf_und_zeile(text: str) -> tuple[list[str], list[str]]:
    """Kopf (Labels ohne 'Time') + erste Datenzeile-Werte (ohne Zeit) der
    ERSTEN Stunden-Tabelle im Klartext. Windrichtungs-Merge-Ruecklauf wie bei
    Telegram (Mutations-Faelle wie M4 koennen wind_direction+wind auch in
    E-Mail aktiv werden lassen, obwohl das golden-eigene E-Mail-Layout es
    nicht vorsieht)."""
    zeilen = text.splitlines()
    for i, zeile in enumerate(zeilen):
        if _HEADER_TRENNER_RE.match(zeile):
            kopf = zeilen[i - 1].split()
            daten = _tabellen_tokens_mit_richtungs_merge(zeilen[i + 1], len(kopf))
            assert len(kopf) == len(daten), (
                f"Tabellenkopf/-zeile passen nicht zusammen: {kopf!r} vs {daten!r}"
            )
            return kopf[1:], daten[1:]
    raise AssertionError(f"Keine Tabellen-Trennzeile in Klartext gefunden:\n{text[:1500]}")


def parse_email_plain(text: str) -> tuple[list[str], dict[str, Optional[str]]]:
    """(metric_ids in Spaltenreihenfolge, {metric_id: Modus|None})."""
    labels, werte = _email_tabellen_kopf_und_zeile(text)
    ids, modi = [], {}
    for label, wert in zip(labels, werte):
        mid = _COL_LABEL_TO_ID.get(label)
        if mid is None:
            continue
        ids.append(mid)
        modi[mid] = _zell_modus(wert)
    return ids, modi


_TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


def _text_ohne_tags(html_fragment: str) -> str:
    return _TAG_RE.sub("", html_fragment).strip()


def _email_html_kopf_und_werte(html: str) -> tuple[list[str], list[str]]:
    """(Labels ohne 'Time', Werte ohne Zeit-Spalte) der ERSTEN Stunden-Tabelle
    im HTML -- gemeinsame Grundlage fuer ``parse_email_html`` (Modus) und
    ``roh_wert_der_metrik`` (Rohwert, AC-13)."""
    tabellen = [m.start() for m in re.finditer(r"<table", html)]
    assert len(tabellen) >= 2, "Keine zweite <table> (Stunden-Tabelle) im HTML gefunden"
    ausschnitt = html[tabellen[1]:tabellen[2] if len(tabellen) > 2 else tabellen[1] + 20000]
    kopf_match = re.search(r"<thead>(.*?)</thead>", ausschnitt, re.DOTALL)
    assert kopf_match, "Kein <thead> in der Stunden-Tabelle gefunden"
    labels = [_text_ohne_tags(t) for t in re.findall(r"<th[^>]*>(.*?)</th>", kopf_match.group(1), re.DOTALL)]
    rumpf = ausschnitt[kopf_match.end():]
    erste_zeile_match = re.search(r"<tr[^>]*>(.*?)</tr>", rumpf, re.DOTALL)
    assert erste_zeile_match, "Keine Datenzeile in der Stunden-Tabelle gefunden"
    werte = [_text_ohne_tags(t) for t in _TD_RE.findall(erste_zeile_match.group(1))]
    assert len(labels) == len(werte), f"Kopf/Zeile-Laenge weicht ab: {labels!r} vs {werte!r}"
    return labels[1:], werte[1:]  # erste Spalte = Zeit


def parse_email_html(html: str) -> tuple[list[str], dict[str, Optional[str]]]:
    """(metric_ids in Spaltenreihenfolge, {metric_id: Modus|None}) aus der
    ZWEITEN ``<table>`` (die erste ist der Mastkopf) -- deren ``<th>``-Zeile
    traegt die Spalten-Labels, die naechste ``<tr>`` die erste Datenzeile."""
    labels, werte = _email_html_kopf_und_werte(html)
    ids, modi = [], {}
    for label, wert in zip(labels, werte):
        mid = _COL_LABEL_TO_ID.get(label)
        if mid is None:
            continue
        ids.append(mid)
        modi[mid] = _zell_modus(wert)
    return ids, modi


def parse_telegram_rich(bodies: list[str]) -> tuple[list[str], dict[str, Optional[str]]]:
    """Sucht ueber ALLE Bubble-Texte den Tabellenkopf (Zeile beginnend mit
    "Zt ") des ERSTEN Segments -- ignoriert Kurzuebersicht/Fusszeile/Nacht/
    Ausblick.

    B5-Regel: eine Spalte, deren gesamte gesampelte Zelle ein Platzhalter ist
    (Geisterspalte), zaehlt NICHT als "erscheint" -- ihr Kuerzel wird aus der
    ID-Liste entfernt (sie bleibt dadurch automatisch ohne Reihenfolge-/
    Roh-Einfach-Zelle, s. Matrix-Regel "nur bei beidseitiger Praesenz").
    """
    for body in bodies:
        zeilen = body.splitlines()
        for i, zeile in enumerate(zeilen):
            if zeile.startswith("Zt "):
                kopf = zeile.split()
                daten = _tabellen_tokens_mit_richtungs_merge(zeilen[i + 1], len(kopf))
                assert len(kopf) == len(daten), (
                    f"Telegram-Tabellenkopf/-zeile passen nicht zusammen: "
                    f"{kopf!r} vs {daten!r}"
                )
                ids, modi = [], {}
                for label, wert in zip(kopf[1:], daten[1:]):
                    mid = _COMPACT_LABEL_TO_ID.get(label)
                    if mid is None:
                        continue
                    modus = _zell_modus(wert)
                    if modus is None:
                        continue  # Geisterspalte: zaehlt nicht als "erscheint"
                    ids.append(mid)
                    modi[mid] = modus
                return ids, modi
    raise AssertionError("Kein Telegram-Tabellenkopf ('Zt ...') in den Bubbles gefunden")


#: Wert-Grammatik der SMS-/Kurzform-Tokens (Vorbild test_sms_user_metric_order.py).
_RANGE_HALF = r"-?\d+|-|\?"
_VALUE_GRAMMAR = (
    rf"(?:(?:{_RANGE_HALF})/(?:{_RANGE_HALF})"
    r"|(?:\d+(?:\.\d+)?%?|[LMH])(?:@\d+(?:\((?:\d+(?:\.\d+)?%?|[LMH])@\d+\))?)?|-|\?)"
)


def _sms_treffer(text: str) -> list[tuple[int, str, str]]:
    """(index, metric_id, roher Wert) je erkanntem Kuerzel-Token in
    Token-Reihenfolge -- gemeinsame Grundlage fuer ``parse_sms_artig``
    (Modus) und ``roh_wert_der_metrik`` (Rohwert, AC-13)."""
    rumpf = text.split(": ", 1)[1] if ": " in text else text
    tokens = rumpf.split(" ")
    treffer: list[tuple[int, str, str]] = []  # (index, metric_id, wert)
    for i, tok in enumerate(tokens):
        for symbol, mid in _SMS_SYMBOL_TO_METRIC.items():
            m = re.fullmatch(rf"{re.escape(symbol)}({_VALUE_GRAMMAR})", tok)
            if m:
                treffer.append((i, mid, m.group(1)))
                break
    treffer.sort(key=lambda t: t[0])
    return treffer


def parse_sms_artig(text: str) -> tuple[list[str], dict[str, Optional[str]]]:
    """(metric_ids in Token-Reihenfolge, {metric_id: Modus|None}) aus einem
    SMS-/Kurzform-/Premium-SMS-Text -- Kuerzel-Register NUR zum Parsen
    (AC-4), niemals zur Erwartungsbildung."""
    treffer = _sms_treffer(text)
    ids: list[str] = []
    modi: dict[str, Optional[str]] = {}
    for _, mid, wert in treffer:
        if mid in ids:
            continue  # Mehrfachsymbole (TH:/TH+:) -> erste Fundstelle zaehlt
        ids.append(mid)
        if wert in ("-", "?"):
            modi[mid] = None
        elif re.fullmatch(r"[LMH]", wert):
            modi[mid] = "friendly"
        else:
            modi[mid] = "raw" if _ist_numerisch(wert.split("@")[0].split("/")[0]) else "friendly"
    return ids, modi


def _kanal_texte(mitschrift, kanal: str) -> tuple[list[str], Optional[str]]:
    """(telegram_bodies_liste, einzeltext) -- fuer telegram_rich die Liste
    aller Bubbles, sonst der EINE gesendete Text."""
    if kanal == "email_html":
        s = mitschrift.sendungen("email")
        return [], (s[0]["body"] if s else None)
    if kanal == "email_plain":
        s = mitschrift.sendungen("email")
        return [], (s[0]["plain_text_body"] if s else None)
    if kanal == "telegram_rich":
        bodies = [s["body"] for s in mitschrift.sendungen("telegram") if s["parse_mode"] == "HTML"]
        return bodies, None
    if kanal == "telegram_kurzform":
        s = [x for x in mitschrift.sendungen("telegram") if x["parse_mode"] is None]
        return [], (s[0]["body"] if s else None)
    if kanal == "sms":
        s = mitschrift.sendungen("sms")
        return [], (s[0]["body"] if s else None)
    if kanal == "premium_sms":
        s = mitschrift.sendungen("premium_sms")
        return [], (s[0]["body"] if s else None)
    raise ValueError(f"Unbekannter Kanal {kanal!r}")


def parse_kanal(mitschrift, kanal: str) -> tuple[list[str], dict[str, Optional[str]]]:
    bodies, text = _kanal_texte(mitschrift, kanal)
    if kanal == "telegram_rich":
        assert bodies, f"Kanal {kanal!r}: keine aufgezeichnete Sendung mit nicht-leerem Text"
        return parse_telegram_rich(bodies)
    assert text, f"Kanal {kanal!r}: keine aufgezeichnete Sendung mit nicht-leerem Text"
    if kanal == "email_html":
        return parse_email_html(text)
    if kanal == "email_plain":
        return parse_email_plain(text)
    return parse_sms_artig(text)


def _kurzuebersicht_wert(bodies: list[str], compact_label: str) -> Optional[str]:
    """Sucht in ALLEN Bubble-Texten eine Kurzuebersicht-Zeile "<Kuerzel>
    <Wert>" (z.B. "G 45") -- Format der Telegram-rich-Kurzuebersicht-Bubble,
    die zusaetzlich zur Stunden-Tabelle mitgesendet wird. Fuer eine wegen des
    Telegram-7er-Tabellenlimits (Issue #360) aus der Stunden-Tabelle
    verdraengte Metrik (z.B. ``gust``) ist dies die einzige Fundstelle."""
    muster = re.compile(rf"^{re.escape(compact_label)}\s+(\S.*)$")
    for body in bodies:
        for zeile in body.splitlines():
            m = muster.match(zeile.strip())
            if m:
                return m.group(1).strip()
    return None


def roh_wert_der_metrik(mitschrift, kanal: str, metric_id: str) -> Optional[str]:
    """Roher Zellwert (String) an der Stelle von ``metric_id`` im tatsaechlich
    gesendeten Text von ``kanal`` -- fuer punktuelle Wert-Zuordnungs-
    Pruefungen (AC-13), damit ein Substring-Treffer nicht zufaellig von einer
    anderen Stelle im Text stammt. ``None``, wenn die Metrik in diesem
    Kanaltext nicht auffindbar ist."""
    bodies, text = _kanal_texte(mitschrift, kanal)
    if kanal == "telegram_rich":
        assert bodies, f"Kanal {kanal!r}: keine aufgezeichnete Sendung"
        for body in bodies:
            zeilen = body.splitlines()
            for i, zeile in enumerate(zeilen):
                if zeile.startswith("Zt "):
                    kopf = zeile.split()
                    daten = _tabellen_tokens_mit_richtungs_merge(zeilen[i + 1], len(kopf))
                    for label, wert in zip(kopf[1:], daten[1:]):
                        if _COMPACT_LABEL_TO_ID.get(label) == metric_id:
                            return wert
        metric = get_metric(metric_id)
        return _kurzuebersicht_wert(bodies, metric.compact_label)
    assert text, f"Kanal {kanal!r}: keine aufgezeichnete Sendung"
    if kanal == "email_html":
        labels, werte = _email_html_kopf_und_werte(text)
    elif kanal == "email_plain":
        labels, werte = _email_tabellen_kopf_und_zeile(text)
    else:
        for _, mid, wert in _sms_treffer(text):
            if mid == metric_id:
                return wert
        return None
    for label, wert in zip(labels, werte):
        if _COL_LABEL_TO_ID.get(label) == metric_id:
            return wert
    return None


def vorbedingung_pruefen(mitschrift, kanaele: tuple[str, ...]) -> None:
    """Vor der Matrix: jeder erwartete Kanal hat GENAU eine (telegram_rich:
    mindestens eine) aufgezeichnete Sendung mit nicht-leerem Text."""
    for kanal in kanaele:
        bodies, text = _kanal_texte(mitschrift, kanal)
        if kanal == "telegram_rich":
            assert bodies, f"Vorbedingung verletzt: kein Telegram-rich-Text fuer {kanal!r}"
        else:
            assert text, f"Vorbedingung verletzt: kein Text fuer Kanal {kanal!r}"


# ---------------------------------------------------------------------------
# Matrix
# ---------------------------------------------------------------------------

Zelle = tuple[str, str, str]  # (metric_id, kanal, dimension)


def _register_deckt(
    zelle: Zelle, register: "list[AusnahmeEintrag]", genutzt: set,
) -> bool:
    mid, kanal, dim = zelle
    for eintrag in register:
        if eintrag.kanal == kanal and eintrag.dimension == dim and eintrag.metrik in (mid, "*"):
            genutzt.add(eintrag)
            return True
    return False


def abweichungen_fuer_golden(
    golden: dict, mitschrift, register: "list[AusnahmeEintrag]",
    *, report_type: str = "evening",
) -> tuple[set[Zelle], set[Zelle], set["AusnahmeEintrag"]]:
    """(rote Zellen, ALLE Abweichungen VOR Register-Filterung, genutzte
    Register-Eintraege) fuer EIN Golden (nur die von diesem Golden
    erreichbaren Kanaele). ``alle_abweichungen`` ist unabhaengig vom
    uebergebenen ``register`` -- sie ist die Grundlage fuer AC-6 (Vergleich
    "leeres Register" gegen "was das Register normalerweise deckt")."""
    register_validieren(register)
    kanaele = erreichbare_kanaele(golden["report_config"])
    vorbedingung_pruefen(mitschrift, kanaele)

    rot: set[Zelle] = set()
    alle_abweichungen: set[Zelle] = set()
    genutzt: set = set()

    def _pruefen(zelle: Zelle) -> None:
        alle_abweichungen.add(zelle)
        if not _register_deckt(zelle, register, genutzt):
            rot.add(zelle)

    for kanal in kanaele:
        erwartet = erwartete_kaskade(golden, kanal, report_type)
        erwartet_ids = [mid for mid, _ in erwartet]
        erwartet_friendly = dict(erwartet)
        ist_ids, ist_modi = parse_kanal(mitschrift, kanal)

        erwartet_set, ist_set = set(erwartet_ids), set(ist_ids)
        for mid in erwartet_set | ist_set:
            e_da, i_da = mid in erwartet_set, mid in ist_set
            if e_da != i_da:
                _pruefen((mid, kanal, "erscheint"))

        gemeinsame_erw = [m for m in erwartet_ids if m in ist_set]
        gemeinsame_ist = [m for m in ist_ids if m in erwartet_set]
        for mid in gemeinsame_erw:
            if gemeinsame_erw.index(mid) != gemeinsame_ist.index(mid):
                _pruefen((mid, kanal, "reihenfolge"))
            if not hat_roh_einfach_dimension(mid):
                continue
            ist_modus = ist_modi.get(mid)
            if ist_modus is None:
                continue
            erwartet_modus = "friendly" if erwartet_friendly[mid] else "raw"
            if erwartet_modus != ist_modus:
                _pruefen((mid, kanal, "roh_einfach"))

    return rot, alle_abweichungen, genutzt


def rote_zellen_fuer_golden(
    golden: dict, mitschrift, register: "list[AusnahmeEintrag]",
    *, report_type: str = "evening",
) -> tuple[set[Zelle], set["AusnahmeEintrag"]]:
    """Rote Zellmenge + tatsaechlich genutzte Register-Eintraege fuer EIN
    Golden (nur die von diesem Golden erreichbaren Kanaele)."""
    rot, _alle, genutzt = abweichungen_fuer_golden(
        golden, mitschrift, register, report_type=report_type,
    )
    return rot, genutzt


def rote_zellen_beide_goldens(
    golden_a: dict, mitschrift_a, golden_b: dict, mitschrift_b,
    register: "list[AusnahmeEintrag]", *, report_type: str = "evening",
) -> tuple[set[Zelle], set["AusnahmeEintrag"]]:
    rot_a, genutzt_a = rote_zellen_fuer_golden(golden_a, mitschrift_a, register, report_type=report_type)
    rot_b, genutzt_b = rote_zellen_fuer_golden(golden_b, mitschrift_b, register, report_type=report_type)
    return rot_a | rot_b, genutzt_a | genutzt_b


def veraltete_eintraege(
    register: "list[AusnahmeEintrag]", genutzt: set["AusnahmeEintrag"],
) -> set["AusnahmeEintrag"]:
    return set(register) - genutzt
