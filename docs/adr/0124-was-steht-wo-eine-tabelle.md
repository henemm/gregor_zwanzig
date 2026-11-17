# ADR-0124: Reiter Wetter — eine Tabelle „Was steht wo“ ersetzt „Inhalt je Kanal und Fläche“; die Grundauswahl gibt es genau einmal; der Bereich heißt „Orte“

- **Status:** Akzeptiert (PO 2026-11-17, Issue #3122)
- **Datum:** 2026-11-17
- **Bezug:** GitHub-Issue #3122 (Teil von Epic #2791 / #2795), Soll-Bild `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html`, Konzept `docs/context/einstellungen_neu.md` §2.5. Entscheidungsgrundlage (Varianten A/B mit Bildern für Computer und Handy): Commit `d5e57ca4b`, Ordner `docs/context/einstellungen_neu/vorlage-3122/` und `seiten/mockup-hub-fassung4-varianten.html` (danach entfernt). **Löst ab:** [ADR-0109](0109-reiterstruktur-wetter-zustellung.md) Nr. 3 und die Grundentscheidung `kanal_inhalt` („eigene Liste je Kanal“); [ADR-0059](0059-compare-ausblick-erbt-grundauswahl.md) und [ADR-0053](0053-compare-kanal-eigene-metrikauswahl-uebersicht.md) Punkt 1, soweit sie Ausblick und Stundenverlauf als eigene bzw. ungebundene Listen führen; [ADR-0107](0107-orte-ein-bis-n-orte.md) Nr. 2, soweit dort „Orts-Briefing“ als Name steht. **Präzisiert:** ADR-0109 Nr. 4 (eine Stelle für den 3-Tages-Ausblick), [ADR-0050](0050-metrik-kaskade-verfeinerung-nicht-ersetzung.md) (gilt durchgängig, auch für Ausblick und Stundenverlauf), [ADR-0121](0121-kanonische-kanal-liste.md) (das gespeicherte Format wird mit dem Bau zu #3122 neu geschnitten). **Bestätigt:** ADR-0055 Nr. 2 (eine Ausblick-Auswahl für E-Mail und Telegram), ADR-0095 (Kanal-Parität), ADR-0097 (ein Code für Trip und Orte), ADR-0049 (Premium-SMS), ADR-0104 (DE/EN).

## Kontext

Die Karte „Inhalt je Kanal und Fläche“ (ADR-0109 Nr. 3, Mockup Fassung 3) stellte Kanäle (E-Mail, Telegram, SMS, Premium-SMS) und Briefing-Teile (3-Tages-Ausblick, Stundenverlauf) in eine Leiste und gab jeder der bis zu sechs Listen eine eigene Auswahl, Reihenfolge und Darstellung. Der PO am 2026-11-17: „viel zu kompliziert, man muss immer wieder dieselben Dinge auswählen“. Die Leiste war nie begründet, sie war ein Mockup-Ergebnis (Analyse im Issue #3122, Abschnitt C3). Im Code steuern drei Schalter denselben Ausblick mit unterschiedlicher Wirkung je Ausgabe, Trip und Orte haben zwei Datenmodelle für dieselbe Liste, und es gibt drei verschiedene Rückfallregeln (Analyse Abschnitt B3).

Der PO hat anhand von Bildern entschieden (Varianten nebeneinander, echte Renderer-Werte, Trip, drei Orte, ein Ort, Computer und Handy). Eine zweite Tabelle für Ausblick und Stundenverlauf hat er verworfen: Zwei Tabellen hätten keinen erkennbaren Unterschied, beide beantworten „wo erscheint diese Metrik“.

## Entscheidung

1. **Die Grundauswahl gibt es genau einmal:** in den Metrik-Zeilen des Reiters Wetter („−“ nimmt eine Metrik aus dem Briefing, „+“ unter „Nicht im Briefing“ holt sie zurück). Keine andere Stelle kann eine Metrik hinzufügen. Jede weitere Auswahl schränkt nur ein (ADR-0050 gilt durchgängig, auch für Ausblick und Stundenverlauf).
2. **Eine Tabelle „Was steht wo“** (EN „What goes where“) ersetzt die Karte „Inhalt je Kanal und Fläche“, gleich für Trip und Orte. Zeile = Metrik der Grundauswahl. Spalte = Stelle, an der sie erscheinen kann. Ein Haken heißt: erscheint dort.

   | Spalte | Trip | Orte |
   |---|---|---|
   | E-Mail | Stundentabelle der Mail | Übersicht (Tageswerte je Ort) |
   | Telegram | Nachricht | Nachricht |
   | SMS | SMS und Premium-SMS | SMS und Premium-SMS |
   | Stundenverlauf | gibt es nicht (die Haupttabelle der Mail zeigt schon die Stunden) | Stunden-Tabelle je Ort, nur E-Mail |
   | 3-Tages-Ausblick | E-Mail und Telegram | E-Mail und Telegram |

3. **Eine Reihenfolge für alle Stellen.** Sie wird einmal gezogen. Die SMS kürzt bei Platzmangel von hinten (`docs/reference/sms_format.md` §6); die Tabelle zeigt in der SMS-Spalte, welche Metriken nicht mehr passen. Beim Trip zeigt die Telegram-Spalte ab der achten Metrik „nur Tageswert“.
4. **Stundenverlauf und 3-Tages-Ausblick folgen der E-Mail.** Sie haben keine eigene, unabhängige Liste. Ein Haken ist dort nur möglich, wenn die Metrik in der E-Mail steht. Vorbelegt ist alles wie in der E-Mail; je Metrik lässt sich der Haken wegnehmen. Der Ausblick bleibt **eine** Auswahl für E-Mail und Telegram (ADR-0055 Nr. 2). Metriken ohne Stundenwert (Sonnenstunden) sind im Stundenverlauf gesperrt („kein Stundenwert“).
5. **Roh/Einfach je Stelle:** in E-Mail, Telegram, Stundenverlauf und Ausblick einzeln, und nur bei Metriken, die laut Katalog zwei Formen haben (`format_modes` in `src/app/metric_catalog.py`; Stand 2026-11-17: Wind, Böen, Niederschlag, Gewitter, Bewölkung in allen Schichten, Sonnenstunden, Windrichtung). Alle anderen Metriken gibt es nur als Zahl, dort steht kein Umschalter. SMS und Premium-SMS haben keine Wahl, sie bleiben bei den Kürzeln.
6. **Ganze Blöcke schaltet man unter der Tabelle:** Stundenverlauf an/aus (Orte). 3-Tages-Ausblick „Morgen-Briefing“ und „Abend-Briefing“, für Trip **und** Orte, Vorbelegung nur abends; das ist die **eine** steuernde Stelle des Ausblicks und ersetzt `show_outlook`, `multi_day_trend_reports`, `outlook_enabled` und die Bedeutung „leere Liste = aus“. Beim Trip stehen hier außerdem Etappen-Kennzahlen, Vortag-Vergleich und Nacht-Stundentabelle (bisher „Weitere Einstellungen für E-Mail“).
7. **Einstellungen je Kanal stehen unter der Tabelle,** jede genau einmal: E-Mail-Format (Trip: Ausführlich oder Kompakt), Telegram-Kurzstil (gilt für Briefing und Alarme; die Telegram-Spalte ruht dann, es gilt die SMS-Spalte), Hinweis zur Premium-SMS.
8. **Die Premium-SMS folgt vorerst der SMS** und hat keine eigene Spalte. Ihre eigene Auswahl kommt mit S9 (#2801).
9. **Amtliche Warnungen** sind eine feste Zeile ohne Abwahl: in E-Mail und Telegram zuerst, in der SMS am Ende.
10. **Der Bereich heißt einheitlich „Orte“** (EN „Locations“), auch bei einem einzelnen Ort. „Vergleich“, „Orts-Vergleich“ und „Orts-Briefing“ entfallen als Name in Oberfläche, Mail, Telegram und SMS. Kein Text setzt mehrere Orte voraus: bei einem Ort steht nicht „alle Orte“ und nicht „1 Orte“. Die E-Mail-Tabelle der Orte heißt „Übersicht“.

## Verworfene Alternativen

- **Variante B, eine Liste je Kanal** (Stand ADR-0109 Nr. 3, ohne die Flächen-Reiter): dieselben Metriken dreimal pflegen, immer nur ein Kanal sichtbar, dazu ein zweiter Abschnitt für Ausblick und Stundenverlauf.
- **Eigener Abschnitt oder zweite Tabelle „Teile des Briefings“:** kein fachlicher Unterschied zur Kanal-Tabelle, beide beantworten dieselbe Frage.
- **Stundenverlauf und Ausblick nur als Schalter** (zeigen immer genau die E-Mail-Metriken): bei vielen E-Mail-Metriken wird der Ausblick so breit wie die Übersicht.
- **Roh/Einfach einmal je Metrik:** in der Stundentabelle liest sich ein Symbol schneller, in der Übersicht die Zahl; das System speichert die Form für Stundenverlauf und Ausblick heute schon getrennt (`hourly_metric_formats`, `outlook_metric_formats`).
- **Eigene Reihenfolge je Kanal:** ist der Preis der einen Tabelle. Der PO hat ihn angenommen.
- **Namen „Orts-Briefing“, „Ortswetter“, „Ortsbeobachtung“:** der PO will einen Namen, „Orte“.

## Konsequenzen

- **Positiv:** Jede Metrik steht im Reiter Wetter genau zweimal: einmal in der Grundauswahl, einmal als Zeile der Tabelle. Eine Zeile zeigt alles, was mit der Metrik geschieht. Trip und Orte haben dieselbe Oberfläche (ADR-0097). Der Ausblick hat eine steuernde Stelle (ADR-0109 Nr. 4).
- **Negativ / Preis:** Eine Reihenfolge für alle Stellen. Auf dem Handy stehen bei Orten fünf Haken-Spalten mit Umschaltern nebeneinander; das ist eng und in der Abnahme am Gerät zu prüfen. Das gespeicherte Format (ADR-0121: `channel_layouts` je Kanal, dazu `outlook_metrics`, `hourly_metrics` und ihre Format-Felder) wird neu geschnitten: je Metrik ein Satz Stellen-Flaggen, eine Darstellung je Stelle, eine Reihenfolge.
- **Folgepflichten:**
  - Migration nach Read-Modify-Write mit Merge (ADR-0101), Bestandsdaten bleiben erhalten. Welche der heutigen Reihenfolgen je Kanal führt, legt die Spec fest.
  - Ein Datenmodell, ein Speicherweg und ein Resolver für Trip und Orte. `WeatherMetricsTab` und der Übergangsblock im Reiter Zustellung entfallen.
  - Offen für die Spec: SMS-Anfang bei Orten (Vorschlag `Orte 18.11.: …`, bei einem Ort `Tecklenburg 18.11.: …`; berührt `sms_format.md`), Wirkung von „Einfach“ im Orte-Telegram, Kompakt-Mail und Ausblick-Schalter (Regel #722), Vorbelegung des Ausblicks, wenn nur das Morgen-Briefing aktiv ist.
  - Alle Texte in DE und EN (ADR-0104). Kürzel der Kurzform bleiben unübersetzt.
  - Bis zum Bau beschreiben die Ist-Referenzen (`api_contract.md`, `renderer_email_spec.md`, `telegram_format.md`, `sms_format.md`, `mail_validators.md`) weiter das heutige Verhalten. Sie werden mit dem Bau nachgezogen, nicht vorher.
  - Abnahme: Soll/Ist-Bild gegen Fassung 4 und „Einstellung = Ausgabe“ (Katalog #3047).
