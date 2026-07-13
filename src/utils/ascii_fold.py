"""ASCII-Faltung — single source of truth (Issue #1253, #1252 v2).

SPEC: docs/specs/modules/fix_1252_1253_kanal_text.md
Bindend: docs/reference/sms_format.md:27 ("Umlaute werden ersetzt:
ae/oe/ue/ss"), :66 ("zuerst falten, dann kuerzen").

PO-Entscheidung (2026-07-13): eigene Transliterations-Tabellen (Griechisch,
Kyrillisch, Nordisch, ...) sind strukturell unvollstaendig -- drei
Adversary-Runden fanden je neue fehlende Schriften. Ersetzt durch die
Bibliothek `anyascii` (ISC, keine Folge-Abhaengigkeiten), die JEDE Schrift
abdeckt. Einzige eigene Ausnahme bleibt die deutsche Umlaut-Digraph-Map, weil
`anyascii("München") == "Munchen"` liefert, sms_format.md:27 aber "Muenchen"
verlangt -- die Digraph-Map muss deshalb VOR `anyascii()` laufen.

Adversary Runde 4 (2026-07-13): `anyascii` deckt NICHT "praktisch alle"
zugewiesenen Buchstaben ab -- ein Vollscan aller Unicode-Codepoints zeigt
30.779 Buchstaben (Kategorien Ll/Lu/Lt/Lo/Lm), darunter arabische, syrische,
Gurmukhi- und weitere Konsonantenschriften (z.B. `ا` ARABIC LETTER ALEF),
die `anyascii` zu leerem String faltet. Der vorherige `backslashreplace`-
Guard konnte das NICHT abfangen: er greift erst NACH `anyascii()`, das
Zeichen war zu diesem Zeitpunkt bereits geloescht (leerer String ist ASCII-
kodierbar, loest also nie eine `UnicodeEncodeError`-Ersetzung aus). Deshalb
jetzt ein echter, ZEICHENWEISER Guard (siehe `fold_ascii` unten).
"""
from __future__ import annotations

import unicodedata

from anyascii import anyascii

_UMLAUT_MAP = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
})

# Buchstaben-Kategorien nach Unicode-Standard (unicodedata.category()):
# Ll=Kleinbuchstabe, Lu=Grossbuchstabe, Lt=Titlecase, Lo=Buchstabe ohne
# Gross-/Kleinschreibung (z.B. arabisch, chinesisch, Gurmukhi), Lm=modifizierender
# Buchstabe. Lo ist die Kategorie, in der Adversary-Runde 4 den arabischen
# Alif-Fall fand -- sie darf im Guard NICHT fehlen.
_LETTER_CATEGORIES = frozenset({"Ll", "Lu", "Lt", "Lo", "Lm"})

# Sichtbarer Ersatz fuer Buchstaben, die `anyascii` restlos verschluckt statt
# zu falten. Bewusst EIN Zeichen (Laengen-Budget SMS <=160 unkritisch) und
# ASCII-sicher. Ein Ort, der teilweise als "?" erscheint, ist unschoen -- aber
# eine amtliche Warnung ganz ohne Ortsangabe (der Bug, den dieses Modul
# behebt) ist gefaehrlich. Sichtbarkeit schlaegt Kosmetik.
_UNFOLDABLE_LETTER_MARKER = "?"


def fold_ascii(text: str) -> str:
    """Falte Text auf reines ASCII, ohne dass Buchstaben spurlos verschwinden.

    1. `unicodedata.normalize("NFC", text)` ZUERST -- Eingaben koennen NFD-
       zerlegt hereinkommen (Basiszeichen + COMBINING-Zeichen getrennt, z.B.
       aus Upstream-Feeds oder macOS-Werkzeugen). Die Umlaut-Digraph-Map
       (Schritt 2) matcht nur den precomposed Codepoint ('ü' = U+00FC) --
       ohne vorherige NFC-Normalisierung wuerde 'u' + COMBINING DIAERESIS die
       Map verfehlen und `anyascii` wuerfe die Diaerese kommentarlos weg
       ('Munchen' statt 'Muenchen').
    2. Deutsche Umlaut-Digraphe (ae/oe/ue/ss) -- `anyascii` allein wuerde
       'ü' zu 'u' verkuerzen statt zur bindenden 'ue'-Digraph-Map
       (sms_format.md:27).
    3. `anyascii()` ZEICHENWEISE (nicht als ganzer String) fuer JEDE andere
       Schrift (Griechisch, Kyrillisch, Nordisch, Maltesisch, Polnisch,
       Tuerkisch, CJK, ...). Zeichenweise Verarbeitung ist Voraussetzung fuer
       Schritt 4 -- nur so laesst sich einem einzelnen Eingabezeichen genau
       eine Faltungs-Ausgabe zuordnen.
    4. Echter Guard: `anyascii` deckt NICHT jeden Unicode-Buchstaben ab --
       u.a. arabische, syrische und Gurmukhi-Konsonantenschriften (Kategorie
       `Lo`) falten zu leerem String. Jedes Eingabezeichen, das laut
       `unicodedata.category()` ein Buchstabe ist (Ll/Lu/Lt/Lo/Lm) und nach
       der Faltung NICHTS beigetragen hat, wird durch den sichtbaren
       Platzhalter `?` ersetzt statt still zu verschwinden. Der fruehere
       `encode("ascii", "backslashreplace")`-"Guard" war toter Code: er
       greift erst NACH der Faltung, ein zu leerem String gefaltetes Zeichen
       loest aber nie eine `UnicodeEncodeError` aus (leerer String ist immer
       gueltiges ASCII) -- die dokumentierte Sicherheit existierte nicht.
    """
    text = unicodedata.normalize("NFC", text)
    text = text.translate(_UMLAUT_MAP)

    folded_chars = []
    for ch in text:
        folded = anyascii(ch)
        if not folded and unicodedata.category(ch) in _LETTER_CATEGORIES:
            folded = _UNFOLDABLE_LETTER_MARKER
        folded_chars.append(folded)
    return "".join(folded_chars)
