# Fehlerarten-Auswertung Juli 2026 — und warum es keinen dritten Wächter braucht

**Stand:** 2026-07-28 · **Datenbasis:** 79 Fehler, Stichtag 2026-07-27

## Warum es dieses Dokument gibt

Die Tickets #1402 („Wächter 1 von 5") und #1405 („Wächter 2 von 5") berufen sich beide
auf eine „Fehlerarten-Auswertung vom 2026-07-27" — **dieses Dokument existierte nicht**.
Die Zahl „5" stand damit ohne Inhalt im Raum: Wächter 3 bis 5 waren weder benannt noch
begründet. Diese Auswertung holt die Grundlage nach.

**Ergebnis vorweg: Die beiden gebauten Wächter decken die einzigen beiden Fehlerarten ab,
die eine klassenweite Prüfung rechtfertigen. Ein dritter, vierter oder fünfter Wächter ist
nicht begründbar.** Für alle vier neu identifizierten Fehlerarten existiert bereits ein
billigeres Gegenmittel — meist eines, das schon läuft.

## Datengrundlage

Alle 138 `bug`-Issues des Repos, gefiltert auf `createdAt` oder `closedAt` im Fenster
2026-06-27 bis 2026-07-28 → 86 Treffer. Abzüglich #1402/#1405 selbst (das sind
Bauaufträge, keine klassifizierbaren Fehler) und fünf Tickets, die erst am 2026-07-28
und damit nach dem Stichtag angelegt wurden (#1403, #1404, #1407, #1408, #1409):
**86 − 2 − 5 = 79.** Deckt sich exakt mit der in beiden Tickets genannten Zahl.

**Korrektur zur Datenlage:** Zwischen 2026-05-28 und 2026-07-12 existiert kein einziges
`bug`-Issue. Der reale Zeitraum der 79 Fehler ist **2026-07-12 bis 2026-07-27 (15 Tage)**,
nicht die in den Tickets genannten „vier Wochen". Für die Klassifikation folgenlos, für
Aussagen über Fehler pro Woche nicht.

**Korrektur zur Zählung in #1405:** Dort stehen 18 Fälle für „stilles Verschlucken",
darunter #1403 — das aber einen Tag nach dem Stichtag angelegt wurde. Im 79er-Korpus sind
es sauber **17**. Zugleich gehören mindestens #1294, #1389 und #1390 mechanisch ebenfalls
dazu, stehen aber nicht in der Belegliste — die tatsächliche Häufigkeit dieser Fehlerart
wird also eher **unter**schätzt als über.

## Die sechs Fehlerarten

| Fehlerart | Fälle | Mechanik |
|---|---|---|
| **Zeitzone** | 7 | Uhrzeit/Datum in Weltzeit statt Ortszeit — naiver Zeitstempel wird direkt umgerechnet oder eine Signatur fällt still auf UTC zurück |
| **Stilles Verschlucken / Erfolg ohne Wirkung** | 17 | Eine Menge wird beim Auflösen kleiner, ein Lauf meldet Erfolg ohne Wirkungsprüfung, oder eine Eingabe wird verändert und die Änderung nicht zurückgemeldet |
| **Parallele Pfade ohne eine Quelle der Wahrheit** | 12 | Dieselbe fachliche Größe mehrfach implementiert (je Kanal, je Editor, je Sprache, Vorschau ≠ Versand) — eine Stelle wird bei Änderungen vergessen |
| **Vergleichs-Editor: unvollständig konvergierte Oberfläche** | 12 | Bedienelemente ohne Handler, Rückbau-Reste, durch Umbauten unerreichbar gewordene Einstellungen |
| **Überschreibende Schreibvorgänge** | 7 | Ein Schreib- oder Auslieferungsvorgang überschreibt Bestandsdaten, weil Änderungsstempel oder Merge-Prüfung fehlen |
| **Störungen im Test- und Gate-Werkzeug** | 10 | Die Prüfinfrastruktur selbst ist fehlerhaft — kein Produktfehler im engeren Sinn |
| *Rest ohne Muster (je Einzelfall)* | 14 | — |

Belegte Issue-Nummern je Art: siehe Abschnitt „Belege" unten.

## Bewertung: welche Art verdient einen Wächter?

Ein Wächter (struktureller Test, der eine Fehlerklasse unmöglich macht) lohnt nur, wenn
**alle vier** Kriterien tragen. Ein „nein" bei einem einzigen genügt zur Ablehnung.

| Fehlerart | Häufig? | Strukturell erkennbar? | Trennscharf? | Billigeres Mittel? | Wächter |
|---|---|---|---|---|---|
| Zeitzone | 7 ✓ | **Hoch** — reines Quelltextmuster | Hoch, ~20 Ausnahmen | teilweise gewählt (ein zentraler Auflöser) | **JA** (#1402, live) |
| Stilles Verschlucken | 17 ✓ | **Gemischt** — Unterarten A/B ja, C/D/E nein | A/B moderat–gut | Muster existiert im Haus, wird nur ausgerollt | **JA, nur A/B** (#1405, live) |
| Parallele Pfade | 12 ✓ | **Teilweise** — nur ein Unterfall | erwartbar niedrig; Divergenz ist im Vergleichs-Bereich teils **gewollt** | **ja**: Review-Pflicht in CLAUDE.md | **NEIN** (Ausnahme s. u.) |
| Vergleichs-Editor | 12 ✓ | **Niedrig** — Laufzeit-/DOM-Aussage, zudem Frontend | sehr niedrig | **ja**: Konvergenz-Programm #1230/#1372/#1374 läuft | **NEIN** |
| Überschreibende Schreibvorgänge | 7 ✓ | **Mittel** für einen Unterfall, sonst niedrig | ungemessen | **ja**: Merge-Pflicht + Snapshot-Hook; #1395 baut die Wurzel-Lösung | **NEIN** |
| Test-/Gate-Werkzeug | 10 ✓ | **Niedrig** — kein gemeinsames Muster | nicht anwendbar | **ja**: Gate-Bestandsaudit #1197 läuft | **NEIN** |

### Warum die vier „nein" keine Bequemlichkeit sind

- **Parallele Pfade:** Zwei Implementierungen derselben Sache sind hier teilweise
  *architektonisch gewollt* — CLAUDE.md erlaubt ausdrücklich vergleichs-eigene Bausteine
  (Orte-Tab, transponierte Übersicht, Vergleichs-Mail-Vorlage). Ein generischer Scanner
  träfe genau diese legitimen Fälle und würde abgeschaltet.
- **Vergleichs-Editor:** „Knopf ohne Funktion" ist keine Eigenschaft des Quelltexts,
  sondern des laufenden Programms. Ein Prüfwerkzeug, das nur liest, kann das nicht sehen.
  Die Wurzel wird ohnehin gerade behoben — ein Test würde nur Symptome eines bereits
  laufenden Umbaus fangen.
- **Überschreibende Schreibvorgänge:** Die Regel existiert seit BUG-DATALOSS-GR221 und
  wird durch einen automatischen Snapshot-Hook flankiert; #1395 baut gerade den
  Änderungsstempel, der das Problem an der Wurzel löst statt nachgelagert zu melden.
- **Test-/Gate-Werkzeug:** Ein Wächter für kaputte Wächter wäre selbstbezüglich und
  verstieße gegen das Regel-Budget (keine neue Pflicht ohne Ersatz einer alten).

## Empfehlung

**Kein dritter vollwertiger Wächter.** Falls dennoch einer gebaut werden soll, ist genau
ein Kandidat sauber genug:

> **Enger Aufrufseiten-Test: „jede Versandfunktion je Kanal muss die zentrale
> Empfänger-Prüfung aufrufen"** — Unterfall von „Parallele Pfade", 3 belegte Fälle
> (#1235, #1236, #1288). Technik wie beim Zeitzonen-Wächter (Aufrufseiten-Scan), geringer
> Bauaufwand, architektonisch unstrittige Signatur.

Er wird nicht empfohlen, weil er viele Fälle abdeckt, sondern weil er als einziger die
Kombination aus billigem Bau und scharfer Signatur hat. Ob drei belegte Fälle das
rechtfertigen, ist eine PO-Entscheidung.

## Was stattdessen mehr bringt

Die zwei größten verbliebenen Fehlerarten (Parallele Pfade, Vergleichs-Editor — zusammen
24 der 79 Fälle) werden beide **durch das laufende Konvergenz-Programm** adressiert
(#1230/#1372/#1374: ein gemeinsamer Editor-Rahmen für Trip und Vergleich). Das ist die
wirksamere Investition als ein weiterer Wächter: es beseitigt die Ursache, statt Symptome
zu melden.

## Belege

| Fehlerart | Issue-Nummern |
|---|---|
| Zeitzone | 1312, 1347, 1378, 1383, 1385, 1386, 1399 |
| Stilles Verschlucken | A: 1285, 1296, 1298, 1361, 1362, 1366, 1394 · B: 1290, 1346, 1348 · C: 1328, 1331, 1339 · D: 1376, 1379 · E: 1262, 1397 |
| Parallele Pfade | 1235, 1236, 1288, 1297, 1308, 1315, 1325, 1332, 1345, 1377, 1387, 1401 |
| Vergleichs-Editor | 1266, 1267, 1268, 1269, 1270, 1271, 1299, 1300, 1320, 1359, 1360, 1371 |
| Überschreibende Schreibvorgänge | 1234, 1257, 1259, 1264, 1395, 1396, 1398 |
| Test-/Gate-Werkzeug | 1263, 1265, 1279, 1284, 1289, 1295, 1307, 1358, 1381, 1382 |
| Rest ohne Muster | 1243, 1294, 1306, 1309, 1316, 1323, 1329, 1375, 1380, 1389, 1390, 1391, 1393, 1400 |

## Unsichere Zuordnungen

Offen gelegt statt stillschweigend einsortiert:

- **#1345** (Zeitstempel-Typkonflikt zwischen zwei Providern) passt zu Zeitzone *und* zu
  Parallele Pfade — hier zu Letzterem gezählt.
- **#1294, #1389, #1390** sind mechanisch stilles Verschlucken, fehlen aber in der
  Belegliste von #1405. Die Häufigkeit dieser Art ist damit eher unterschätzt.
- **#1397 und #1400** (geografische Zuständigkeit ohne echte Grenzprüfung) könnten eine
  eigene Fehlerart bilden — mit 2 Fällen unter der Schwelle von 4.
- **#1259** liegt zwischen Überschreibenden Schreibvorgängen und Vergleichs-Editor;
  CLAUDE.md nennt genau diesen Speicherweg als „Wurzel der Editor-Drift".
- **#1393** ist eine PO-Anforderungsänderung, kein Fehler mit technischer Ursache.

## Konsequenz für die Tickets

#1402 und #1405 sprechen von „Wächter 1 von 5" bzw. „2 von 5". Nach dieser Auswertung ist
**„von 2" die belegbare Zahl**. Die Formulierung „von 5" sollte in beiden Tickets
richtiggestellt werden, damit sie keine Arbeit ankündigt, für die es keine Begründung gibt.
