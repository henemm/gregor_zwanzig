"""Python-Textkatalog (Issue #2662, ADR-0104).

Dateien ``messages/{de,en}/<bereich>.json`` mit flachen Schluesseln
``bereich.gruppe.element``. Einziger Zustand: der geladene Katalog je Ordner
und die Menge der schon gemeldeten Schluessel (Log-Entdopplung, keine Sprache).
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger("i18n")

MESSAGES_DIR: Path = Path(__file__).resolve().parent / "messages"
SPRACHEN: tuple[str, ...] = ("de", "en")
BEREICHE: tuple[str, ...] = (
    "allgemein", "mail", "vergleich", "alarm", "warnung",
    "telegram", "sms", "versand", "inbound", "api",
)
PLATZHALTER_RE = re.compile(r"\{([a-z][a-z0-9_]*)\}")
SCHLUESSEL_RE = re.compile(r"[a-z0-9_]+(\.[a-z0-9_]+){1,3}")


class Catalog:
    """Geladene Texte eines Katalogordners plus Log-Entdopplung."""

    def __init__(self, root: Path) -> None:
        self.texte: dict[str, dict[str, str]] = {
            lang: _lade_sprache(Path(root) / lang) for lang in SPRACHEN
        }
        self._gemeldet: set[str] = set()

    def melde_einmal(self, art: str, key: str) -> None:
        zeile = f"i18n {art}: {key}"
        if zeile not in self._gemeldet:
            self._gemeldet.add(zeile)
            logger.warning(zeile)

    def nachschlagen(self, key: str, lang: str) -> str:
        if lang == "en":
            text = self.texte["en"].get(key)
            if text is not None:
                return text
        text = self.texte["de"].get(key)
        if text is None:
            self.melde_einmal("missing", key)
            return key
        if lang == "en":
            self.melde_einmal("fallback", key)
        return text


def _lade_sprache(ordner: Path) -> dict[str, str]:
    texte: dict[str, str] = {}
    for bereich in BEREICHE:
        pfad = ordner / f"{bereich}.json"
        try:
            daten = json.loads(pfad.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.warning("i18n catalog unreadable: %s", pfad)
            continue
        if isinstance(daten, dict):
            texte.update({k: v for k, v in daten.items() if isinstance(v, str)})
    return texte


_GELADEN: dict[Path, Catalog] = {}


def get_catalog() -> Catalog:
    """Katalog des aktuellen ``MESSAGES_DIR`` (einmal je Ordner geladen)."""
    root = Path(MESSAGES_DIR)
    if root not in _GELADEN:
        _GELADEN[root] = Catalog(root)
    return _GELADEN[root]


def _lese_bereich(pfad: Path, fehler: list[str]) -> dict | None:
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except OSError:
        fehler.append(f"{pfad}: Datei fehlt")
        return None
    except ValueError as exc:
        fehler.append(f"{pfad}: kein gueltiges JSON ({exc})")
        return None
    if not isinstance(daten, dict):
        fehler.append(f"{pfad}: kein JSON-Objekt")
        return None
    return daten


def _form_fehler(bereich: str, daten: dict, lang: str) -> list[str]:
    return [
        f"{lang}/{bereich}.json: Schluessel {key!r} verletzt Form oder Bereich"
        for key in daten
        if not SCHLUESSEL_RE.fullmatch(key) or key.split(".")[0] != bereich
    ]


def parity_errors(root: Path | str) -> list[str]:
    """Abweichungen zwischen ``de`` und ``en`` (Schluessel, Platzhalter, Form)."""
    fehler: list[str] = []
    for bereich in BEREICHE:
        de = _lese_bereich(Path(root) / "de" / f"{bereich}.json", fehler)
        en = _lese_bereich(Path(root) / "en" / f"{bereich}.json", fehler)
        if de is None or en is None:
            continue
        fehler += _form_fehler(bereich, de, "de") + _form_fehler(bereich, en, "en")
        fehler += [f"{bereich}: {k!r} fehlt in en" for k in sorted(set(de) - set(en))]
        fehler += [f"{bereich}: {k!r} fehlt in de" for k in sorted(set(en) - set(de))]
        for key in sorted(set(de) & set(en)):
            p_de = set(PLATZHALTER_RE.findall(str(de[key])))
            p_en = set(PLATZHALTER_RE.findall(str(en[key])))
            if p_de != p_en:
                fehler.append(f"{bereich}: {key!r} Platzhalter de {sorted(p_de)} != en {sorted(p_en)}")
    return fehler
