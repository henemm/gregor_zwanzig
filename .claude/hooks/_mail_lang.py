#!/usr/bin/env python3
"""Sprache einer Mail fuer die Mail-Validatoren (Issue #2663, ADR-0104).

Gemeinsame Hilfe aller vier Validatoren: der Kopf ``X-GZ-Lang`` nennt die
Sprache des Inhalts, die Erwartungen (Ueberschriften, Hinweise, Warn-Woerter)
kommen aus dem Python-Katalog ``src/i18n`` in genau dieser Sprache -- nie aus
Literalen. Pfadregel #1409: ``src`` relativ zur eigenen Datei.

Uebergang (PV): fehlt der Kopf, gilt ``de`` plus Warnung. A2 (#2681) setzt
``HEADER_PFLICHT = True``; dann ist ein fehlender Kopf ein Fehler.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
from i18n import catalog as _catalog  # noqa: E402
from i18n import t as _t  # noqa: E402

HEADER_PFLICHT = False
SPRACHEN = ("de", "en")
FEHLER_PRAEFIX = "X-GZ-Lang unbekannt oder fehlt"
_PLATZHALTER_RE = re.compile(r"\{([a-z][a-z0-9_]*)\}")


def mail_lang(msg) -> tuple[str, list[str]]:
    """(lang, warnungen) aus dem Kopf ``X-GZ-Lang``; ValueError bei Fremdwert."""
    roh = msg.get("X-GZ-Lang")
    if roh is None:
        if HEADER_PFLICHT:
            raise ValueError(f"{FEHLER_PRAEFIX}: Kopf fehlt (Pflicht seit A2 #2681)")
        return "de", [
            "X-GZ-Lang fehlt -- Mail wird als 'de' geprueft (Uebergang #2663, "
            "ab A2 #2681 Pflicht)"
        ]
    wert = str(roh).strip()
    if wert not in SPRACHEN:
        raise ValueError(f"{FEHLER_PRAEFIX}: Wert {wert!r} (erlaubt: de, en)")
    return wert, []


def vorlage(key: str, lang: str) -> str:
    """Rohtext des Schluessels (Platzhalter unersetzt); fehlt er, KeyError."""
    text = _catalog.get_catalog().texte.get(lang, {}).get(key)
    if text is None:
        raise KeyError(f"Katalogschluessel fehlt ({lang}): {key}")
    return text


def erwartet(key: str, lang: str, **params) -> str:
    """Erwarteter Text = ``i18n.t(key, lang, **params)``."""
    vorlage(key, lang)
    return _t(key, lang, **params)


def marker(key: str, lang: str, trenner: str = " (") -> str:
    """Text eines Schluessels bis vor den ersten Trenner (z. B. 'Nacht am Ziel')."""
    text = vorlage(key, lang)
    return text.split(trenner, 1)[0] if trenner else text


def muster(key: str, lang: str, **gruppen: str) -> str:
    """Regex-Quelltext zur Vorlage; Platzhalter werden Gruppen (Standard ``.+?``)."""
    text = vorlage(key, lang)
    teile, pos = [], 0
    for m in _PLATZHALTER_RE.finditer(text):
        teile.append(_flexibel(text[pos:m.start()]))
        teile.append(f"({gruppen.get(m.group(1), '.+?')})")
        pos = m.end()
    teile.append(_flexibel(text[pos:]))
    return "".join(teile)


def _flexibel(literal: str) -> str:
    """Leerraum im Literal darf im Mailtext beliebig breit sein."""
    return r"\s+".join(re.escape(teil) for teil in literal.split(" "))


def _vorkommen(text: str, key: str, lang: str) -> bool:
    kern = _PLATZHALTER_RE.split(vorlage(key, lang))[0].strip() or vorlage(key, lang)
    return re.search(r"(?<!\w)" + re.escape(kern) + r"(?!\w)", text) is not None


def widerspruch(text: str, lang: str, keys: list[str]) -> str | None:
    """Meldung, wenn der Inhalt erkennbar die ANDERE Sprache spricht.

    Gezaehlt werden nur Schluessel, deren de- und en-Text verschieden sind:
    findet sich kein Text der Kopfsprache, aber mindestens einer der anderen
    Sprache, widersprechen sich Kopf und Inhalt."""
    andere = "en" if lang == "de" else "de"
    verschieden = [k for k in keys if vorlage(k, "de") != vorlage(k, "en")]
    eigene = [k for k in verschieden if _vorkommen(text, k, lang)]
    fremde = [k for k in verschieden if _vorkommen(text, k, andere)]
    if eigene or not fremde:
        return None
    belege = ", ".join(repr(marker(k, andere)) for k in fremde[:3])
    return (
        f"SPRACHE: Kopf X-GZ-Lang: {lang} widerspricht dem Inhalt -- gefunden "
        f"sind Texte der Sprache '{andere}' ({belege}), keiner der Sprache '{lang}'"
    )
