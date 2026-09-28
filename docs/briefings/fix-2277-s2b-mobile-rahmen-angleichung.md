---
spec_file: docs/specs/modules/fix_2277_s2b_mobile_rahmen_angleichung.md
spec_sha256: 2a4981b114c358e4083197e655eb81b3416961f49c5739f066831dad0719a7ac
---

# PO-Briefing: fix-2277-s2b-mobile-rahmen-angleichung

- **Spec:** docs/specs/modules/fix_2277_s2b_mobile_rahmen_angleichung.md
- **Issue:** #2277 (Nachtrag vom 19.09., AC-6/AC-7)
- **Erstellt:** 2026-09-28

## Was gebaut wird

Die beiden Anlege-Seiten für Trip und Ortsvergleich bekommen auf dem Handy dieselbe Kopfleiste, Speichern-Leiste und denselben Scroll-Hinweis am Reiter-Streifen.

## Definition of Done

Fertig ist es, wenn beide Anlege-Seiten auf dem Handy dieselbe vorlesbare Kopfleiste, Speicher-Position und Tabbar-Sichtbarkeit zeigen und derselbe Scroll-Hinweis am Reiter-Streifen erscheint. Stand jetzt: umgesetzt, alle 10 Akzeptanzkriterien erfüllt.

## Wie geprüft wird

Automatisierte Bildschirm-Tests prüfen Struktur, Kopfleiste, Vorlese-Text und Speicherplatz; nur ein Klicktest prüft echtes Antippen auf dem Handy. Die volle Frontend-Testsuite ist grün (3501 bestanden), die unabhängige Gegenprüfung (Adversary) meldet VERIFIED.

## Kritische Anmerkungen

- Der Zurück-Tap am Schreibtisch-Bildschirm wird weiterhin nur bei der manuellen Staging-Prüfung angeschaut, nicht automatisiert abgesichert.
- Die Reihenfolge und Beschriftung der Reiter bleibt bewusst unangeglichen — das Ticket bleibt danach weiter offen.
- Automatisierte Tests prüfen Struktur und Text, nicht das tatsächliche Aussehen am echten Bildschirm.

## Was seit dem letzten Briefing behoben wurde

- Der Vorlese-Text am Zurück-Pfeil wird durch einen eigenen, benannten Test mit konkretem Wortlaut nachgewiesen, für Handy und Schreibtisch (auf deinen Wunsch ergänzt, Spec 1.0 auf 1.1).
- Neu in Spec 1.2: Die Gegenprüfung fand beim Umsetzen zwei Änderungen, die in der Spec noch fehlten (Befund G003, geringe Schwere). Die Spec ist nachgezogen; es gibt keine neuen Akzeptanzkriterien.
- Erstens: Unter der Speichern-Leiste bleibt kein leerer Streifen mehr, weil die untere App-Leiste auf den Anlege-Seiten ausgeblendet ist. Diese Änderung ist rein additiv (Stylesheet).
- Zweitens: Die Wegpunkte-Karte samt Quellenangabe endet jetzt oberhalb der Speichern-Leiste. Deren Höhe wird gemessen; alle anderen Stellen, die diese Karte nutzen, bleiben unverändert.
- Beide Änderungen sind durch die Browser-Tests „S2b AC-4 (mobil)" gedeckt.

## Was sich für dich sichtbar ändert

Auf dem Handy sehen `/trips/new` und `/compare/new` danach dieselbe Kopfleiste mit vorlesbarem Zurück-Pfeil, dieselbe Position der Speichern-Taste unten und denselben Ausblend-Effekt am rechten/linken Rand des Reiter-Streifens. Die untere App-Navigationsleiste verschwindet auf beiden Anlege-Seiten (bisher nur beim Trip), ohne dass unten ein leerer Streifen stehen bleibt. Beim Trip endet die Wegpunkte-Karte sauber über der Speichern-Leiste. Am Schreibtisch-Bildschirm ändert sich für den Ortsvergleich nichts sichtbar; beim Trip bekommt der Zurück-Pfeil dort ebenfalls den Vorlese-Text.

## Abweichungen vom Ticket

- **Ursprüngliche AC-3 des Gesamttickets** (Reihenfolge/Beschriftung der Reiter „ab dem zweiten Reiter") ist bewusst **nicht** Teil dieser Lieferung. Begründung: Trip hat drei eigene Reiter, Ortsvergleich nur zwei — „ab dem zweiten" ist deshalb wörtlich nicht anwendbar und bräuchte vorher eine Klärung, ab welchem Reiter „gleich" gilt. Das wird als eigene Folge-Lieferung zurückgestellt; das Ticket bleibt danach offen, es entsteht kein neues.
- **Die Speichern-Taste wandert für BEIDE Bildschirmgrößen** (nicht nur mobil, wie das Nachtrag-Anliegen wörtlich nahelegt) in dieselbe geteilte Speicher-Leiste. Begründung: Speichern-Logik und -Text sind für Desktop und Handy identisch — eine Aufteilung würde dieselbe Funktion doppelt pflegen. Kein Verhalten ändert sich dadurch für den Nutzer.
- **Ein zusätzlicher technischer Nachzieheffekt**: Wenn die untere App-Leiste verschwindet, darf am unteren Rand kein leerer, ungenutzter Streifen stehen bleiben. Das stand nicht wörtlich im Nachtrag, ist aber eine notwendige Folge davon, dass die Leiste jetzt verschwindet.
- **Zwei zusätzlich angefasste Dateien (neu in Spec 1.2):** das gemeinsame Stylesheet (kein Leerraum unter der Speichern-Leiste) und die Wegpunkte-Karte des Trip-Editors (endet über der Speichern-Leiste, Höhe wird gemessen). Beides war in der ersten Spec nicht genannt, wurde beim Umsetzen nötig und ist rein additiv; alle anderen Nutzer der Karte bleiben bitgleich.

## Wie abgesichert wird

- **Struktur- und Bildschirm-Tests (automatisiert, laufen bei jeder Auslieferung):** Kopfleiste, Vorlese-Text am Zurück-Pfeil (beide Bildschirmgrößen), Speichern-Taste, Ausblend-Effekt am Reiter-Streifen und die Sichtbarkeit der unteren App-Leiste werden für beide Anlege-Seiten geprüft.
- **Echte Klicktests im Browser (automatisiert):** der Zurück-Tap auf dem Handy beim Trip (kein ungewollter Zwischenspeicher-Versand) sowie die Fälle „S2b AC-4 (mobil)", die den freien unteren Rand und das Ende der Wegpunkte-Karte über der Speichern-Leiste abdecken.
- **Nicht automatisch geprüft:** der Zurück-Klick am Schreibtisch-Bildschirm (nur manueller Durchklick vor der Produktiv-Auslieferung), und ob die Kopfleiste am echten Bildschirm tatsächlich gleich aussieht — die Tests prüfen Text und Aufbau, kein Bildvergleich.

## Entscheidung, um die es geht

Mit „approved" gibst du die Spec in ihrer nachgezogenen Fassung 1.2 frei: beide Anlege-Seiten sind auf dem Handy angeglichen, inklusive Vorlese-Text und der zwei nachgetragenen Randänderungen — bei offen bleibender Reiter-Reihenfolge (eigene Folge-Lieferung) und nur manuell geprüftem Desktop-Zurück-Klick.

## Freigabe-Frage

Sollen Trip- und Ortsvergleich-Anlegeseite auf dem Handy angeglichen werden, während der Zurück-Klick am Schreibtisch nur manuell geprüft wird?
