# ADR-0124: Reiter Wetter — eine Tabelle „Was steht wo“ ersetzt „Inhalt je Kanal und Fläche“; die Grundauswahl gibt es genau einmal; der Bereich heißt „Orte“

- **Status:** Akzeptiert (PO 2026-11-17, Issue #3122) — teilweise abgelöst durch ADR-0125 (SMS-Kopf entfällt; Orte-SMS nennt Orte als `O1`, `O2` …) und durch [ADR-0131](0131-alarm-schwelle-vorbelegung-je-kanal.md) (Nr. 8: die Premium-SMS bekommt endgültig den SMS-Inhalt, keine eigene Auswahl)
- **Datum:** 2026-11-17
- **Bezug:** GitHub-Issue #3122 (Teil von Epic #2791 / #2795), Soll-Bild `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html`, Konzept `docs/context/einstellungen_neu.md` §2.5. Entscheidungsgrundlage (Varianten A/B mit Bildern für Computer und Handy): Commit `d5e57ca4b`, Ordner `docs/context/einstellungen_neu/vorlage-3122/` und `seiten/mockup-hub-fassung4-varianten.html` (danach entfernt). **Löst ab:** [ADR-0109](0109-reiterstruktur-wetter-zustellung.md) Nr. 3 und die Grundentscheidung `kanal_inhalt` („eigene Liste je Kanal“); [ADR-0059](0059-compare-ausblick-erbt-grundauswahl.md) und [ADR-0053](0053-compare-kanal-eigene-metrikauswahl-uebersicht.md) Punkt 1, soweit sie Ausblick und Stundenverlauf als eigene bzw. ungebundene Listen führen; [ADR-0107](0107-orte-ein-bis-n-orte.md) Nr. 2, soweit dort „Orts-Briefing“ als Name steht; [ADR-0050](0050-metrik-kaskade-verfeinerung-nicht-ersetzung.md) Regel 5 und [ADR-0119](0119-vergleich-channel-layouts.md) Nr. 1, soweit sie eine Reihenfolge je Kanal führen (Nr. 3); ADR-0119 Nr. 5, soweit die SMS eine wählbare Einfach-Form hat (Nr. 5); [ADR-0055](0055-trip-ausblick-waehlbare-spalten.md) Punkt 3 und 4, soweit der Ausblick unmittelbar an die Grundauswahl und ausdrücklich nicht an die E-Mail-Auswahl gebunden ist (Nr. 4), und Punkt 1, soweit eine leere Liste den Block abschaltet (Nr. 6); [ADR-0037](0037-datengetriebener-ausblick-aus-metrik-katalog.md) Punkt 3, soweit eine leere Liste den Block abschaltet, und Punkt 6 (`outlook_enabled` als Schalter) (Nr. 6). **Präzisiert:** ADR-0109 Nr. 4 (eine Stelle für den 3-Tages-Ausblick), ADR-0050 Regeln 1 bis 3 (gelten durchgängig, auch für Ausblick und Stundenverlauf), [ADR-0121](0121-kanonische-kanal-liste.md) (das gespeicherte Format wird mit dem Bau zu #3122 neu geschnitten). **Bestätigt:** ADR-0055 Nr. 2 (eine Ausblick-Auswahl für E-Mail und Telegram), ADR-0095 (Kanal-Parität), ADR-0097 (ein Code für Trip und Orte), ADR-0049 (Premium-SMS), ADR-0104 (DE/EN).

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
5. **Roh/Einfach je Stelle:** in E-Mail, Telegram, Stundenverlauf und Ausblick einzeln, und nur dort, wo die Metrik an dieser Stelle zwei Formen hat. Wo es nur die Zahl gibt, steht kein Umschalter. SMS und Premium-SMS haben keine Wahl, sie bleiben bei den Kürzeln. Welche Metrik an welcher Stelle zwei Formen hat, führt der Code heute an mehreren Stellen und nicht deckungsgleich:
   - der Katalog (`format_modes` in `src/app/metric_catalog.py`; Stand 2026-11-17: Wind, Böen, Niederschlag, Gewitter, Bewölkung in allen Schichten, Sonnenstunden, Windrichtung),
   - eine eigene Liste für den Ausblick (`OUTLOOK_FRIENDLY_CAPABLE` im selben Modul: mit Regenwahrscheinlichkeit, ohne Gewitter),
   - der Orte-Stundenverlauf, dessen Umschalter dieser Ausblick-Liste folgt (`frontend/src/lib/components/compare/hourlyFriendlyMap.ts`, `_friendly_hour_text` in `src/output/renderers/compare_outlook_metric_ids.py`; Gewitter ohne Umschalter),
   - das Orte-Telegram: „Einfach“ nutzt die Wortformen des Ausblicks und hängt bei Ampel-Größen zusätzlich die Marke `@h` an, auch wo die Zahl bleibt (`_friendly_overview_text` und `_ampel_stunde` in `src/output/renderers/comparison.py`).

   Die Spec legt die Liste je Stelle fest, mit dem Ziel einer einzigen Quelle im Katalog. Das Soll-Bild zeigt den Umschalter nach dem Katalog.
6. **Ganze Blöcke schaltet man unter der Tabelle:** Stundenverlauf an/aus (Orte). 3-Tages-Ausblick „Morgen-Briefing“ und „Abend-Briefing“, für Trip **und** Orte, Vorbelegung nur abends; das ist die **eine** steuernde Stelle des Ausblicks und ersetzt `show_outlook`, `multi_day_trend_reports`, `outlook_enabled` und die Bedeutung „leere Liste = aus“. Beim Trip stehen hier außerdem Etappen-Kennzahlen, Vortag-Vergleich und Nacht-Stundentabelle (bisher „Weitere Einstellungen für E-Mail“).
7. **Einstellungen je Kanal stehen unter der Tabelle,** jede genau einmal: E-Mail-Format (Trip: Ausführlich oder Kompakt), Telegram-Kurzstil (gilt für Briefing und Alarme; die Telegram-Spalte ruht dann, es gilt die SMS-Spalte), Hinweis zur Premium-SMS.
8. **Die Premium-SMS folgt vorerst der SMS** und hat keine eigene Spalte. Ihre eigene Auswahl kommt mit S9 (#2801). *(Abgelöst durch ADR-0131: „vorerst“ ist endgültig, eine eigene Auswahl gibt es nicht.)*
9. **Amtliche Warnungen** sind eine feste Zeile ohne Abwahl: in E-Mail und Telegram zuerst, in der SMS am Ende.
10. **Der Bereich heißt einheitlich „Orte“** (EN „Locations“), auch bei einem einzelnen Ort. „Vergleich“, „Orts-Vergleich“ und „Orts-Briefing“ entfallen als Name in Oberfläche, Mail, Telegram und SMS. Kein Text setzt mehrere Orte voraus: bei einem Ort steht nicht „alle Orte“ und nicht „1 Orte“. Die E-Mail-Tabelle der Orte heißt „Übersicht“.
11. **Die Tabelle steuert nur die Briefings, nicht die Alarme.** Welche Metrik einen Alarm auslöst, bestimmt allein „Alarm ab“ in ihrer Metrik-Zeile (ADR-0106). Eine in der E-Mail-Spalte abgewählte Metrik erscheint deshalb weiter in der Alarm-Mail, wenn sie auslöst (PO 2026-11-17, Issue #3107). Roh/Einfach der Alarm-Mail folgt wie bisher der Stelle E-Mail bzw. Telegram.

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
  - Leitlinie für den Bau: Die Naht ist das View-Model des Lese-Resolvers (`src/services/channel_list_resolver.py`). Ausgaben, die ausschließlich daraus lesen, sind vom Neuschnitt unberührt; deshalb zuerst alle Ausgaben auf das View-Model stellen (#3099, #3100), danach den Eingang des Resolvers tauschen. Die schreibende Migration aus #3102 geht im Bau zu #3122 auf. (Erledigt: #3157, #3351.)
  - Offen für die Spec: SMS-Anfang bei Orten (Vorschlag `Orte 18.11.: …`, bei einem Ort `Tecklenburg 18.11.: …`; berührt `sms_format.md`), Wirkung von „Einfach“ im Orte-Telegram, Kompakt-Mail und Ausblick-Schalter (Regel #722), Vorbelegung des Ausblicks, wenn nur das Morgen-Briefing aktiv ist. Dazu:
    - Regel bei leerer Grundauswahl. Heute ist sie je Fläche und Stelle verschieden (ADR-0050, Nachtrag 2026-11-17).
    - Kürzel-Legende (Konzept W21, W10). Fassung 4 zeigt keine.
    - Stellen ohne eigene Ausgabe: Haken dort sperren oder die Zeile kennzeichnen. Beispiel Trip, Tiefsttemperatur Nacht: nie eine Spalte der Stundentabelle (`NO_HOURLY_COLUMN_METRIC_IDS` in `src/output/renderers/email/helpers.py`), in Telegram nur abends eine eigene Zeile und nur, wenn „Temperatur“ nicht gewählt ist (`src/output/renderers/narrow.py`).
    - Zeilen-Kennung der Orte: Katalog-ID mit Aufweitung auf Höchst- und Tiefstwert oder `metric_id` plus Aggregation (#3101).
    - Ergänzung der Design-Charter: `docs/design-system/CHARTER.md` erlaubt ein Tabellen-Layout bisher nur für stündliche Wetterdaten, die Hourly-Matrix der Orte und System-Status-Tabellen im Konto.
  - Alle Texte in DE und EN (ADR-0104). Kürzel der Kurzform bleiben unübersetzt.
  - Bis zum Bau beschreiben die Ist-Referenzen (`api_contract.md`, `renderer_email_spec.md`, `telegram_format.md`, `sms_format.md`, `mail_validators.md`) weiter das heutige Verhalten. Sie werden mit dem Bau nachgezogen, nicht vorher.
  - Abnahme: Soll/Ist-Bild gegen Fassung 4 und „Einstellung = Ausgabe“ (Katalog #3047).

## Nachtrag 2026-11-17: Festlegungen der Spec

Die Punkte, die oben unter „Folgepflichten“ und in Nr. 5 als offen für die Spec stehen, sind in `docs/specs/modules/feat_3122_was_steht_wo.md` entschieden (vom PO freigegeben am 2026-11-17). Die Spec ist für die Einzelheiten maßgeblich; hier steht die Kurzform.

**Vom PO entschieden (2026-11-17, per Abfrage):**

1. **SMS-Anfang bei Orten:** mehrere Orte `Orte 18.11.: Münster D 13C …`, genau ein Ort `Tecklenburg 18.11.: D 11C …`. „Vergleich“ entfällt.
2. **Kürzel-Legende:** aufklappbar in der Karte unter dem SMS-Beispiel („Kürzel erklärt“). In den Briefings steht keine Legende; der Satz „Die Legende steht auch am Ende jedes Briefings.“ entfällt.
3. **Vorbelegung des Ausblicks:** nur im Abend-Briefing. Ist beim Abo nur das Morgen-Briefing eingeschaltet, im Morgen-Briefing. Bestehende Trips und Orte behalten, was sie heute bekommen.
4. **Führende Reihenfolge bei der Migration:** die heute wirksame Reihenfolge der SMS, weil nur dort die Reihenfolge entscheidet, was bei Platzmangel wegfällt. Was in der SMS fehlt, folgt in der Reihenfolge von Telegram, dann E-Mail, dann Grundauswahl.

**In der Spec festgelegt (Tech Lead):**

5. **Gespeichertes Format:** `display_config.placements` mit `rows` (Katalog-ID, Haken je Stelle, Darstellung je Stelle; Listenposition = Reihenfolge) und `outlook_reports`. Ein fehlender Haken heißt „angehakt“, `false` heißt „bewusst abgewählt“ (löst #3082).
6. **Zeilen-Kennung der Orte:** die Katalog-ID, aufgeweitet auf die Auswertungen der Grundauswahl (#3101).
7. **Roh/Einfach:** eine Liste im Katalog, je Metrik die Stellen mit zwei Formen (Tabelle in der Spec, Teil A Nr. 4). Gewitter hat zwei Formen nur in der HTML-Mail, die Regenwahrscheinlichkeit kommt dazu. Die SMS behält je Fläche die Form, die heute ohne Einstellung erscheint.
8. **Orte-Telegram:** „Einfach“ zeigt Wort oder Symbol nach dieser Liste, bei Wind, Böen, Niederschlag und Regenwahrscheinlichkeit mit der Stunden-Marke `@h`. „Zahl mit Marke“ gibt es nicht mehr.
9. **Kompakt-Mail:** Den Ausblick steuert auch dort nur die eine Stelle. Die übrigen Block-Schalter ignoriert sie weiter (#722).
10. **Leere Auswahl:** Leer bleibt leer, an jeder Stelle und bei bewusst leerer Grundauswahl, ohne Rückfall. Nur eine nie eingestellte Grundauswahl bekommt den Standardsatz der Vorlage.
11. **Stellen ohne eigene Ausgabe:** gesperrt mit Grund (Strich statt Haken), aus einer Liste im Katalog.
12. **Neue Metrik:** steht hinten und ist an allen ihren Stellen angehakt.
13. **Genau ein Ort:** Die Tabelle „Übersicht“ steht auch dann in der Mail (Soll-Bild „Orte · 1 Ort“). Das ersetzt die Formulierung „E-Mail ohne Vergleichstabelle“ aus #2798.
14. **SMS-Schwellen** bekommen keine Oberfläche (Konzept W13: entfallen mit der Profil-Ampel).
15. **Design-Charter:** §3 bekommt die Ausnahme „Einstell-Tabelle ‚Was steht wo‘“.

**Weiter offen, nicht Teil des Baus zu #3122:** die Schalter der Trip-Mail ohne Platz im Soll-Bild (Kurz-Zusammenfassung, Quick-Take-Chips, Metriken-Überblick, Großwetterlage, Zusammenfassung, Tages-Summe). Sie bleiben bis #3036 im Übergangsblock bedienbar; die Frage gehört zu #3036.

Nachtrag 2026-11-24 (#3036): entschieden, dass Kurz-Zusammenfassung und Großwetterlage eigene Schalter unter der Tabelle bekommen (nur ausführliche Mail, bei Kompakt gesperrt); die übrigen vier (Quick-Take-Chips, Metriken-Überblick, Zusammenfassung, Tages-Summe) bleiben wirkungslos und ohne Oberfläche. Diese Entscheidung ändert den Wortlaut oben nicht.

## Nachtrag 2026-11-24: E-Mail-Format „Kompakt“ auch für Orte (#3059)

Überholt die Einschränkung „(Trip: …)“ in Nr. 7 und ergänzt Nr. 6 und Nr. 9 der Spec-Festlegungen; nichts wird still zurückgenommen. Spec: `docs/specs/modules/feat_3059_orte_kompakt_mail.md`.

- **Nr. 7:** Der Schalter „E-Mail: Format“ (Ausführlich oder Kompakt) steht in der Karte für Trip **und** Orte, aus demselben Baustein (Kontext-Flag, kein eigener Orte-Baustein, #1170). Orte speichern ihn in `display_config.email_format` (wie `telegram_style`, Teilfeld per Read-Modify-Write); fehlend oder unbekannt = Ausführlich. Bestehende Orte-Abos bleiben ausführlich.
- **Nr. 6 / Nr. 9:** Die Orte-Kompakt-Mail ist ein einzelner ASCII-Textteil unter 2 KB: je Ort eine Zeile (Name, Warnmarker, Kürzel und Wert der für die E-Mail gewählten Metriken), je Ort eine Zeile „3-Tages-Ausblick“ nur, wenn der Ausblick für das Briefing eingeschaltet ist. Den Stundenverlauf zeigt sie nie; in der Karte ist sein Schalter bei Kompakt gesperrt (gespeicherter Wert bleibt), der Ausblick-Schalter bleibt bedienbar (#722, PO #3160). Bei mehr Orten als in 2 KB passen, wird vom Listenende gekürzt („+N Orte nicht gezeigt“).
- **Kanäle:** Das Format wirkt allein auf die E-Mail; Telegram, SMS und Premium-SMS bleiben unverändert, `email_format` und `telegram_style` sind unabhängig.
- **Nicht Teil:** Vortag-Vergleich für Orte (#3342); Etappen-Kennzahlen und Nacht-Stundentabelle für Orte sind nicht vorgesehen (PO 2026-11-24).
