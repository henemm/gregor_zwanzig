# ADR-0022: ASCII-Faltung via `anyascii` statt handgepflegter Transliterations-Tabellen

- **Status:** Akzeptiert
- **Datum:** 2026-07-13
- **Bezug:** GitHub-Issue #1253 (gebündelt mit #1252), Spec
  `docs/specs/modules/fix_1252_1253_kanal_text.md`, `docs/reference/sms_format.md:27,66`,
  Implementierung `src/utils/ascii_fold.py`

## Kontext

Ortsnamen mit Akzenten/Umlauten wurden auf SMS und im E-Mail-Klartext verstümmelt
(`Hyères` → `Hyres`, `München` → `Mnchen`) — drei getrennte, handgepflegte
Implementierungen (`render.py::_ascii`, `email/compact.py::_ASCII_MAP`,
`tokens/builder.py::_UMLAUT`) deckten jeweils nur Umlaute bzw. eine feste
NFKD-Zerlegung ab und löschten alles andere ersatzlos. `sms_trip.py::_sms_stage_prefix`
faltete überhaupt nicht.

Der erste Lösungsversuch (v1) ersetzte die Löschung durch eigene, handgepflegte
Transliterations-Tabellen (Griechisch, Kyrillisch, Nordisch, …). Drei aufeinander
folgende Adversary-Runden fanden dabei **jeweils neue** Lücken:

- Runde 2: griechische und kyrillische Ortsnamen fehlten komplett (`Θεσσαλονίκη`,
  `София`) — eine amtliche Warnung erschien ohne jede Ortsangabe.
- Runde 3: serbische und mazedonisch-kyrillische Buchstaben (`Ђердап` → `erdap`,
  führendes `Ђ` verschwand) sowie Maltesisch (`Ħamrun`) fehlten in den Tabellen.
- Runde 4: `anyascii` (bereits als Kandidat evaluiert) faltet arabische, syrische
  und Gurmukhi-Konsonantenschriften (Unicode-Kategorie `Lo`, z.B. `ا` ARABIC LETTER
  ALEF) zu **leerem String** — ein rein zeichenweiser Guard war zu diesem Zeitpunkt
  noch nicht vorhanden.

Diese Serie zeigt ein strukturelles Muster, kein Restrisiko einzelner vergessener
Einträge: **Eine Positivliste von Schriften ist prinzipiell unvollständig.** Jedes
fehlende Zeichen wird ohne Faltungsfunktion still gelöscht; im Extremfall steht in
einer amtlichen Warnung danach gar kein Ort mehr.

## Entscheidung

1. **`anyascii`** (PyPI, ISC-Lizenz, keine Folge-Abhängigkeiten) ist die einzige
   Quelle für die Transliteration nicht-lateinischer/nicht-ASCII-Buchstaben. Die
   Bibliothek deckt praktisch jede zugewiesene Unicode-Schrift ab, statt jede neu
   auftauchende Schrift als Folge-Issue nachzupflegen.
2. **Deutsche Umlaut-Digraph-Map läuft VOR `anyascii()`**, als einzige eigene
   Ausnahme: `anyascii("München") == "Munchen"`, `sms_format.md:27` verlangt aber
   `Muenchen`. Die Digraph-Map (`ä→ae`, `ö→oe`, `ü→ue`, `ß→ss`) faltet den
   precomposed Codepoint zuerst, danach übernimmt `anyascii` den Rest. Voraussetzung
   dafür ist eine `unicodedata.normalize("NFC", …)`-Stufe ganz am Anfang, sonst
   umgehen NFD-zerlegte Eingaben (Basiszeichen + COMBINING-Zeichen, plausibel bei
   Upstream-Feeds) die Map.
3. **Zeichenweiser Guard nach der Faltung:** Da `anyascii` nicht jeden zugewiesenen
   Buchstaben faltet (insbesondere Kategorie `Lo`, z.B. arabische Konsonantenschriften),
   läuft `anyascii()` in `fold_ascii` zeichenweise statt auf dem Gesamtstring. Jedes
   Eingabezeichen, das laut `unicodedata.category()` ein Buchstabe ist
   (`Ll`/`Lu`/`Lt`/`Lo`/`Lm`) und nach der Faltung nichts beiträgt, wird durch den
   sichtbaren Platzhalter `?` ersetzt statt still zu verschwinden. Sichtbarkeit
   schlägt Kosmetik: ein Ort, der teilweise als `?` erscheint, ist unschön, aber eine
   amtliche Warnung ganz ohne Ortsangabe ist gefährlich.
4. Einzige verbindliche Implementierung: `src/utils/ascii_fold.py::fold_ascii`. Die
   drei bisherigen Implementierungen delegieren jetzt dorthin (Details:
   `docs/reference/sms_format.md`).

## Verworfene Alternativen

- **Eigene Transliterations-Tabellen weiterpflegen** — verworfen: strukturell
  unvollständig, siehe Kontext. Jede neue Schrift wäre ein neuer Adversary-Fund statt
  einer einmaligen Entscheidung.
- **`unidecode`** — verworfen wegen GPL-Lizenz; unvereinbar mit dem Lizenzprofil des
  Projekts für Runtime-Dependencies.
- **Scope auf Westeuropa begrenzen** (nur lateinische Schriften mit diakritischen
  Zeichen) — verworfen: Zielgebiete von MeteoAlarm/Vigilance schließen explizit
  Griechenland, Bulgarien, Balkan-Staaten und weitere nicht-lateinische Schriftregionen
  ein; eine Ortsangabe darf dort nicht ersatzlos verschwinden.

## Konsequenzen

- **Positiv:** Neue, bisher unbekannte Schriften benötigen keine Code-Änderung mehr —
  `anyascii` deckt sie bereits ab, der Guard fängt den verbleibenden Rest sichtbar auf.
  Ein Vollscan über alle 1.112.064 Unicode-Codepoints (Python `sys.maxunicode`) zeigt:
  0 Buchstaben falten zu leerem String, 0 Nicht-ASCII-Zeichen bleiben in der Ausgabe.
- **Negativ / Preis:** Neue Runtime-Dependency `anyascii`. Transliterationen sind
  keine amtlichen Umschriften (z.B. `Київ` → `Kiyiv` statt der amtlichen Form `Kyiv`) —
  Ziel ist Wiedererkennbarkeit, nicht linguistische Korrektheit. Einzelne, von
  `anyascii` nicht abgedeckte Buchstaben erscheinen als `?` statt als Buchstabe.
- **Folgepflichten:** Die deutsche Umlaut-Digraph-Map muss **immer vor** `anyascii()`
  laufen — wird diese Reihenfolge vertauscht, bricht `sms_format.md:27` lautlos
  (`Munchen` statt `Muenchen`). Der zeichenweise Guard darf nicht auf Gesamtstring-Länge
  reduziert werden (verdeckt Einzelbuchstaben-Verlust in mehrsilbigen Namen).
