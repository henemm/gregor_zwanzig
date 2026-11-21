# ADR-0127: Ein Katalog, eine Verarbeitung — Metrik-Wissen steht nur im Katalog, Metrik-Werte werden nur in einem Modul zu Darstellung und Bewertung

- **Status:** Akzeptiert (PO-Vorgabe 2026-11-21, Pflicht-Nachtrag zu Issue #3260: „Es gibt nur einen Ort, wo die Informationen zu den Metriken hinterlegt werden und nur einen Ort, wo die Metriken prozessiert werden. Stelle das zu 100% sicher.")
- **Datum:** 2026-11-21
- **Bezug:** Issue #3260 (Auftrag, P1–P3), Befundliste #3256, Auslöser #3255, Bestandsaufnahme `docs/context/3260/`. Spec der ersten Scheibe `docs/specs/modules/feat_3260_s1a_ratsche_ein_katalog.md`. **Schreibt fort:** [ADR-0037](0037-datengetriebener-ausblick-aus-metrik-katalog.md) (Ausblick datengetrieben aus dem Katalog: gilt jetzt für jede Stelle), [ADR-0106](0106-profil-ampel-einzige-bewertung.md) (eine Bewertung je Metrik, aufgelöst in `resolve_ampel`; die Ampel-Grenzen bleiben Daten von Vorlage und Abo), [ADR-0121](0121-kanonische-kanal-liste.md) (ein Resolver für die Kanal-Liste), [ADR-0124](0124-was-steht-wo-eine-tabelle.md) Nr. 4 und 5 (Roh/Einfach und gesperrte Stellen als eine Quelle: jetzt mit der Form je Stelle und Ausgabeart, nicht nur „ob zwei Formen").

## Kontext

Die Bestandsaufnahme vom 2026-11-21 (`docs/context/3260/`) fand rund 590 Stellen, die außerhalb von `src/app/metric_catalog.py` und `src/output/metric_format.py` Metrik-Wissen halten oder Metrik-Werte verarbeiten: fünf Listen „alarmfähig", fünf Mengen „wird gefärbt", vier Handkopien „gesperrte Stellen", zwei Wind-Wortskalen mit verschiedenen Grenzen, ein zweiter Orte-Katalog, feste Trend-Schwellen ohne Abo-Ampel, Wortskalen und Schwellenstufen im Frontend, Handkopien in Go, und Mail-Validatoren, die ihr Soll aus Produktlisten importieren. Jede dieser Kopien wurde einzeln korrekt gebaut und driftete später, weil eine Änderung nicht alle Kopien erreichte (#3255: der Katalog bildete nur ab, OB eine Stelle zwei Formen hat; der Validator spiegelte das Produkt und konnte den Fehler nicht sehen).

## Entscheidung

1. **Ein Ort für Metrik-Wissen.** `src/app/metric_catalog.py` ist die einzige Quelle für alles, was über eine Metrik bekannt ist: Kennung, Namen DE/EN, Spaltenkopf, Kürzel, Einheit, Nachkommastellen, Stellen und Sperrgründe, Formen je Stelle und Ausgabeart (Zahl, Wort, Symbol, Ampelpunkt, Kompass), Wortskala mit Grenzen und Wörtern, Ampel-Fähigkeit, Alarm-Fähigkeit, Auswertungen. Die Ampel-Grenzen selbst sind Daten von Vorlage (`src/app/ampel_templates.py`) und Abo und werden allein in `resolve_ampel` aufgelöst (ADR-0106).
2. **Ein Ort für Metrik-Verarbeitung.** `src/output/metric_format.py` (bei Bedarf als Paket gleichen Namens) macht aus (Metrik, Wert, Stelle, Ausgabeart, gewählte Form, Ampel des Abos) die Darstellung: Zelltext, Form, Ampelfarbe, Kürzel. Jeder Verbraucher (Trip-Mail in allen Fassungen, Orte-Mail, Ausblick, Telegram, SMS, Premium-SMS, Alarme, Befehlsantworten, Vorschau, Etappen-Pille) ruft dieses Modul und macht selbst nur Layout. Kein Renderer vergleicht einen Messwert mit einer festen Zahl oder wählt selbst zwischen Wort und Ampelpunkt.
3. **Frontend und Go halten kein Metrik-Wissen.** Das Frontend bezieht es ausschließlich über die API aus dem Katalog; Go reicht durch und speichert.
4. **Ratsche.** Ein Kern-Test (`tests/unit/test_ein_katalog_eine_verarbeitung_ratsche.py`) durchsucht Python-Produktcode, Go, Frontend und die Mail-Validatoren maschinell und wird rot bei einer Sammlung von Metrik-Kennungen außerhalb des Katalogs, einer Verzweigung auf eine Metrik-Kennung, einem Vergleich eines Messwerts mit einer festen Zahl außerhalb des Verarbeitungsmoduls, einer Verarbeitungsfunktion außerhalb des Moduls samt ihren Aufrufen, einer Metrik-Liste in Go oder Frontend und einem Produktimport in einem Validator. Der Bestand steht in einer Ausnahmeliste (je Datei und Art eine Anzahl). Sie darf nie wachsen, muss mit jeder Scheibe von Issue #3260 schrumpfen und ist am Ende von Schritt 6 leer. Ein nicht leerer Rest wird dem PO gemeldet.
5. **Einzige Ausnahme: Erwartungen der Prüfwerkzeuge.** Tests und Mail-Validatoren führen ihr Soll von Hand aus der freigegebenen Tabelle abgeschrieben. Das Produkt liest es nie. Ein Validator importiert keine Produktliste (ADR-Nr. 4 prüft das).

## Verworfene Alternativen

- **Örtlich flicken, Stelle für Stelle.** So entstanden die 590 Kopien; jede Korrektur erzeugte eine weitere.
- **Validator-Soll aus dem Katalog ableiten.** Dann kann eine falsche Katalog-Angabe nie auffallen (#3255).
- **Ausnahmeliste als freie Zeilenliste.** Zeilennummern wandern bei jeder Änderung; die Anzahl je Datei und Art ist stabil und nennt im Fehlerfall trotzdem Datei und Zeile.

## Konsequenzen

- **Positiv:** Eine neue Metrik wird nur im Katalog eingetragen und erscheint überall richtig; eine Regeländerung wirkt an jeder Stelle gleichzeitig; Abweichungen zwischen Trip und Orte, Mail und Telegram können strukturell nicht mehr entstehen.
- **Negativ / Preis:** Großer Umbau über sechs Schritte; bis Schritt 6 trägt die Ausnahmeliste den Bestand. Die Ratsche arbeitet mit Mustern (Namensmuster für Messwerte, Klammer-Spannen in TS/Go) und kann Grenzfälle melden, die kein Metrik-Wissen sind; sie werden durch Umbau oder Umbenennung aufgelöst, nicht durch Ausnahmen.
- **Folgepflichten:** Jede Scheibe senkt die Ausnahmeliste. Wer eine Metrik-Regel braucht, erweitert Katalog oder Verarbeitungsmodul. Regel-Budget: die Ratsche ersetzt die Entdeckungsstufe der Metrik-Listen-Ratsche aus #1856 (deren Prüfdatum 2026-11-15 abgelaufen ist); Prüfdatum der neuen Ratsche 2027-02-19.
