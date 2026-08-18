# Strategische Richtungsentscheidungen

> Ablage für PO-Entscheidungen, die über ein einzelnes Ticket hinaus gelten.
> In CLAUDE.md als Ziel für „strategische Entscheidungen" benannt; hier neu
> angelegt am 2026-08-17 (die Datei fehlte im Bestand).
>
> Eine Entscheidung wird hier nie still zurückgenommen — Abweichung heißt neuer
> Eintrag mit Datum und Begründung.

## 2026-08-17 — HTML ist die Normalfassung der Mail; Klartext ist die bewusste Wahl

**PO-Entscheid, allgemeingültig** (aus der Analyse zu #1493):

> „Wenn der User will, wählt er Plaintext E-Mail. Die normale E-Mail (HTML)
> braucht keine Dopplung."

### Was daraus folgt

1. **Die HTML-Mail ist die Normalfassung.** Wer Klartext bekommt, hat das selbst
   gewählt (Mail-Client oder Einstellung) — Klartext ist kein Notbehelf für
   Unfähige, sondern eine bewusste Entscheidung des Empfängers.

2. **Keine Dopplung in der HTML-Mail.** Steht eine Aussage bereits an einer
   Stelle der Mail, bekommt sie **keinen zweiten Block**, der dasselbe in anderen
   Worten wiederholt. Ein neuer Textblock ist nur berechtigt, wenn er eine
   Aussage trägt, die sonst **nirgends** in der Mail steht.
   Vorbild: #1313 E1 — die „Gewitter-Vorschau" entfällt, sobald der
   Mehrtages-Ausblick dieselbe Datenquelle zeigt.

3. **Die Prüffrage vor jedem neuen Mail-Block lautet:**
   *Steht diese Aussage schon irgendwo in derselben Mail?*
   Wenn ja, wird die bestehende Stelle **verbessert**, nicht eine zweite
   danebengestellt.

4. **Was in HTML durch Farbe oder Form getragen wird, muss im Klartext als Wort
   dastehen.** Der Klartext hat keine Ampelfarben, keine Pillen-Formen, keine
   Hintergründe — er hat nur Zeichen. Eine Information, die in der HTML-Fassung
   allein an einer Farbe hängt, ist in der Klartext-Fassung **nicht vorhanden**.
   Das ist kein Schönheitsfehler, sondern ein Informationsverlust auf genau dem
   Gerät, das im Gebirge gelesen wird.
   Deckt sich mit dem Design-Leitprinzip „Akzent-Farben nie alleiniger
   Lesbarkeits-Träger" (CLAUDE.md, PO-bestätigt 2026-05-25).

### Abgrenzung — was das NICHT heißt

- **Kein Freibrief für inhaltliche Unterschiede.** HTML und Klartext sagen
  dieselbe Sache; sie unterscheiden sich nur darin, **womit** sie sie sagen
  (Farbe/Form vs. Wort).
- **Keine Rechtfertigung, den Klartext zu vernachlässigen.** Er ist die Fassung,
  die auf schwacher Verbindung und altem Gerät ankommt.

### Erste Anwendung

Issue **#1493** (Gewitter-Onset): Der ursprünglich geplante Prosa-Satz
„Gewitter wahrscheinlich ab 14:00 …" entfällt ersatzlos, weil die Metrik-Pille
`Gewitter ab 14:00 · stärkste 18:00 · CAPE` (`email/helpers.py:1774`) dieselbe
Aussage bereits trägt. Stattdessen wird die bestehende Pille um das fehlende
**Stufenwort** ergänzt — das hing bis dahin allein an der Ampelfarbe und fehlte
im Klartext vollständig.
