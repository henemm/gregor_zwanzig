"""Datentyp fuer amtliche Wetterwarnungen (Issue #1034).

SPEC: docs/specs/modules/issue_1034_official_alerts_foundation.md
ADR-0016: eigener additiver Datentyp statt Wiederverwendung von
WeatherProvider- oder Delta-Alert-Modellen (absolute Behoerden-Einstufung).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# Issue #1441 (ADR-0089): Gefahrenart des amtlichen Lawinen-Lageberichts --
# eigene EAWS-Skala 1-5 neben der Awareness-Skala 1-4 (`avalanche`, MeteoAlarm).
AVALANCHE_BULLETIN = "avalanche_bulletin"


@dataclass(frozen=True)
class OfficialAlert:
    """Eine amtliche Warnung einer offiziellen Quelle (z.B. Météo-France Vigilance).

    Level 1=gruen, 2=gelb, 3=orange, 4=rot (analog zu Vigilance-Farbstufen).
    """
    source: str
    hazard: str
    level: int
    label: str
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    url: Optional[str] = None
    region_label: Optional[str] = None
    # Issue #1217/#1218 (F001): stabile, stufen-unabhängige Dedup-Identität.
    # Quellen, deren Label den Schweregrad codiert (z.B. Massiv-Sperren:
    # "Zugang eingeschränkt" vs. "gesperrt" fürs GLEICHE Massiv), setzen hier
    # eine über Stufen konstante Kennung, damit Eskalationen nicht als zwei
    # verschiedene Warnungen erscheinen. None -> Fallback auf region_label/label.
    dedup_id: Optional[str] = None
    # Issue #1944: Kennung des Eingangs-Mitschnitts (#1948 S1), aus dem diese
    # Warnung stammt -- mitgefuehrt vom Abruf bis zum `alert_log`-Eintrag,
    # damit fuer jede versendete Warnung der ausloesende Roh-Datensatz
    # nachweisbar ist (Vorfall #1929). None = Herkunft nicht eindeutig
    # feststellbar; eine falsche Zuordnung waere schlimmer als keine.
    capture_id: Optional[str] = None
    # Issue #1441 (ADR-0089): zweite Skala. Bestand = "awareness" (1-4, level).
    # Lagebericht = "eaws": `native_level` 1-5 ist die Originalstufe, `level`
    # nur die abgeleitete Farbe (5 -> 4). Alle Felder mit Default -> Bestand
    # bit-identisch.
    scale: str = "awareness"
    native_level: Optional[int] = None
    # Hoehenangabe woertlich: Zahl als String ("2200") oder "Waldgrenze";
    # Richtung "above"/"below". None = keine Hoehenbegrenzung.
    elevation_value: Optional[str] = None
    elevation_direction: Optional[str] = None
    # CAAML-`problemType`-Codes in Bulletin-Reihenfolge, dedupliziert.
    problems: tuple[str, ...] = ()
    # "earlier"/"later" nur, wenn Vor- und Nachmittag verschiedene Stufen haben.
    time_of_day: Optional[str] = None
    # Issue #1441 S3 (SLF): amtliche Feinstufe "-"/"+" (``subdivision``), nur fuer
    # die Langform (Mail, Telegram). Vergleiche nutzen weiter nur `native_level`.
    level_modifier: Optional[str] = None
    # Issue #2668 (ADR-0104): alle Sprachbloecke der Quelle als (Sprachcode,
    # Text), Sprachcode klein und zweistellig; `label_lang` = Sprache von
    # `label`. Die Wahl nach Nutzersprache faellt erst beim Darstellen (die
    # Warnungen liegen nutzeruebergreifend im Cache); `label` bleibt Kennung.
    label_by_lang: tuple[tuple[str, str], ...] = ()
    label_lang: str = ""


def comparable_level(alert: OfficialAlert) -> int:
    """Stufe fuer Vergleiche INNERHALB einer Gefahrenart (Dublettenwahl,
    Eskalation, Gedaechtnis): die Originalstufe, wenn gesetzt, sonst `level`.
    Nie ueber Gefahrenarten/Skalen hinweg verwenden (ADR-0089)."""
    return alert.native_level if alert.native_level is not None else alert.level
