"""Issue #2096: geteilter Testhelfer fuer den TAGESBEZUG von Zeitangaben.

Warum es diesen Helfer gibt: die Alarm-Texte nennen eine Uhrzeit, die auf
einen anderen Kalendertag fallen kann. Der Renderer stellt dann korrekt einen
Tagesbezug voran -- Langform `morgen 00:12` (`_time_with_day()`,
`src/output/renderers/alert/render.py`), Kurzform als vorangestelltes
DE-Wochentagskuerzel `So1:35` (`_sms_onset_time()`/`_sms_day_prefix()`).
Testanker, die per nackter `HH:MM`-Regex greifen, treffen dann nicht mehr:
die CI-Ampel wurde abends rot, ohne dass ein Produktivdefekt vorlag.

Die naheliegende Behebung (Regex zu `(?:morgen )?` aufweichen) waere die
falsche -- sie macht gruen und laesst den Tagesbezug weiterhin UNGEPRUEFT.
Dieser Helfer zieht stattdessen ein PAAR aus Tagesbezug und Uhrzeit und
liefert dazu das aus den Zeitstempeln HERGELEITETE Gegenstueck; verglichen
wird das ganze Paar. Damit ist der Tagesuebergang erstmals bewacht statt
umgangen.

Die Wochentagskuerzel werden aus dem Produktivcode IMPORTIERT statt
abgetippt: eine zweite Liste liefe beim naechsten Umbau auseinander und der
Vergleich maesse dann die Kopie statt des Renderers.
"""
from __future__ import annotations

import re
from datetime import datetime, tzinfo

from output.renderers.alert.official_alerts import _DE_WEEKDAYS

# `HH:MM` -- die Stunde ein- ODER zweistellig, weil die Kurzform sie ohne
# fuehrende Null schreibt (`1:35`), die Langform mit (`01:35`).
_ZEIT = r"\d{1,2}:\d{2}"

# Die Tagesworte der Langform, in genau den Formen, die `_time_with_day()`
# erzeugt -- plus `heute`, das der Renderer NICHT erzeugt: der Helfer muss es
# erkennen koennen, sonst faellt ein falsches Tageswort als "kein Tageswort"
# durch und die Positivkontrolle (AC-4) pruefte nichts.
_TAGESWORT = r"(?:heute|morgen|gestern|in \d+ Tagen|vor \d+ Tagen)"

_KUERZEL = "|".join(_DE_WEEKDAYS)

# Ein vollstaendiges Kurzform-Zeit-Token samt (optionalem) Tagesbezug --
# fuer Aufrufer, die die STRUKTUR einer Token-Folge pruefen (z. B. "das
# Ende-Token haengt unmittelbar am Beginn-Token") und den WERT getrennt
# davon ueber `extract_day_and_time()` holen. Ohne dieses Fragment muesste
# jede solche Strukturpruefung die Kuerzel erneut auflisten.
KURZFORM_ZEIT_TOKEN = rf"(?:{_KUERZEL})?{_ZEIT}"


def extract_day_and_time(
    text: str, anker: str, style: str = "langform",
) -> tuple[str | None, str]:
    """Zieht am `anker` das Paar `(Tagesbezug, "HH:MM")` aus `text`.

    * `style="langform"`: der Anker ist die Floskel VOR der Zeitangabe
      (`"Radar reicht bis"`, `"letzter Regen gegen"`, `"Ortsangabe ab"`).
      Steht ein Tageswort dazwischen, ist es der erste Wert des Paares, sonst
      `None`. Der Anker trennt die Zeitangaben eines Textes voneinander --
      ein Aufruf liefert die Zeit DIESES Ankers, nicht die erstbeste des
      Textes.
    * `style="kurzform"`: der Anker ist `"@"`, getroffen wird das Zeit-Token,
      dem das Guete-Zeichen `?` folgt. Ein vorangestelltes
      DE-Wochentagskuerzel ist der Tagesbezug (`@So1:35?` ->
      `("So", "1:35")`), ohne Kuerzel `None`.

    Findet der Anker nichts, ist das Ergebnis `(None, "")` -- ein Paar, das
    gegen jede Erwartung ungleich ist und die Fundstelle im Assert-Text
    sichtbar macht.
    """
    if style == "kurzform":
        muster = (
            re.escape(anker)
            + rf"(?P<tag>{_KUERZEL})?(?P<zeit>{_ZEIT})\?"
        )
    elif style == "langform":
        muster = (
            re.escape(anker)
            + rf"\s+(?:(?P<tag>{_TAGESWORT})\s+)?(?P<zeit>{_ZEIT})"
        )
    else:
        raise ValueError(f"Unbekannter Stil: {style!r}")

    treffer = re.search(muster, text)
    if treffer is None:
        return None, ""
    return treffer.group("tag"), treffer.group("zeit")


def expected_day_and_time(
    target_utc: datetime, now_utc: datetime, tz: tzinfo,
    style: str = "langform",
) -> tuple[str | None, str]:
    """Bildet das ERWARTETE Paar aus dem Datumsvergleich.

    Beide Zeitpunkte werden auf `tz` projiziert -- der Versatz entsteht
    zwischen den lokalen KALENDERTAGEN, nicht zwischen den UTC-Tagen (genau
    daran scheiterte das Fixture-Datum in #2096, Mechanismus B). Der Wert
    wird hergeleitet, nie als Literal gesetzt.

    Langform spiegelt `_time_with_day()`: gleicher Tag -> `None`, `+1` ->
    `"morgen"`, `-1` -> `"gestern"`, darueber hinaus `"in N Tagen"` bzw.
    `"vor N Tagen"`. Kurzform spiegelt `_sms_onset_time()`/`_sms_day_prefix()`:
    statt des Wortes das DE-Wochentagskuerzel des ZIELtages, am Versandtag
    ersatzlos `None`, und die Stunde ohne fuehrende Null.
    """
    ziel = target_utc.astimezone(tz)
    versatz = (ziel.date() - now_utc.astimezone(tz).date()).days

    if style == "kurzform":
        kuerzel = _DE_WEEKDAYS[ziel.weekday()] if versatz else None
        return kuerzel, f"{ziel.hour}:{ziel.minute:02d}"
    if style != "langform":
        raise ValueError(f"Unbekannter Stil: {style!r}")
    return _tageswort(versatz), ziel.strftime("%H:%M")


def _tageswort(versatz: int) -> str | None:
    """Der Wortlaut zu einem Tagesversatz -- Gegenstueck zu `_time_with_day()`,
    das den Versatz EXAKT aufloest statt ueber seinen Wahrheitswert."""
    if versatz == 0:
        return None
    if versatz == 1:
        return "morgen"
    if versatz == -1:
        return "gestern"
    if versatz > 1:
        return f"in {versatz} Tagen"
    return f"vor {-versatz} Tagen"
