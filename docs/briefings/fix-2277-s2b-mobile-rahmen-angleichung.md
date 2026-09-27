---
spec_file: docs/specs/modules/fix_2277_s2b_mobile_rahmen_angleichung.md
spec_sha256: abf839aee21954ff0306d52825916531e25acdc40c2323e9a0fde55001d2fe9f
---

# PO-Briefing: fix-2277-s2b-mobile-rahmen-angleichung

- **Spec:** docs/specs/modules/fix_2277_s2b_mobile_rahmen_angleichung.md
- **Issue:** #2277 (Nachtrag vom 19.09., AC-6/AC-7)
- **Erstellt:** 2026-09-27

## Was gebaut wird

Die beiden Anlege-Seiten für Trip und Ortsvergleich bekommen auf dem Handy dieselbe Kopfleiste, Speichern-Leiste und denselben Scroll-Hinweis am Reiter-Streifen.

## Definition of Done

Fertig ist es, wenn beide Anlege-Seiten auf dem Handy dieselbe vorlesbare Kopfleiste, Speicher-Position und Tabbar-Sichtbarkeit zeigen und derselbe Scroll-Hinweis am Reiter-Streifen erscheint.

## Wie geprüft wird

Automatisierte Bildschirm-Tests prüfen Struktur, Kopfleiste, Vorlese-Text und Speicherplatz; nur ein Klicktest prüft echtes Antippen auf dem Handy.

## Kritische Anmerkungen

- Der Zurück-Tap am Schreibtisch-Bildschirm wird weiterhin nur bei der manuellen Staging-Prüfung angeschaut, nicht automatisiert abgesichert.
- Die Reihenfolge und Beschriftung der Reiter bleibt bewusst unangeglichen — das Ticket bleibt danach weiter offen.
- Automatisierte Tests prüfen Struktur und Text, nicht das tatsächliche Aussehen am echten Bildschirm.

## Was seit dem letzten Briefing behoben wurde

Der zuvor bemängelte Punkt ist jetzt geschlossen: Der Vorlese-Text am Zurück-Pfeil (`aria-label`) wird jetzt durch einen eigenen, benannten Test mit dem konkreten Wortlaut nachgewiesen — für beide Bildschirmgrößen (Handy und Schreibtisch). Das war auf deinen ausdrücklichen Wunsch hin ergänzt worden (Spec-Version 1.0 → 1.1).

## Was sich für dich sichtbar ändert

Auf dem Handy sehen `/trips/new` und `/compare/new` danach dieselbe Kopfleiste mit vorlesbarem Zurück-Pfeil, dieselbe Position der Speichern-Taste unten und denselben Ausblend-Effekt am rechten/linken Rand des Reiter-Streifens. Die untere App-Navigationsleiste verschwindet auf beiden Anlege-Seiten (bisher nur beim Trip). Am Schreibtisch-Bildschirm ändert sich für den Ortsvergleich nichts sichtbar — dessen bisherige Kopfzeile bleibt dort unangetastet; beim Trip bekommt der Zurück-Pfeil dort ebenfalls den Vorlese-Text.

## Abweichungen vom Ticket

- **Ursprüngliche AC-3 des Gesamttickets** (Reihenfolge/Beschriftung der Reiter „ab dem zweiten Reiter") ist bewusst **nicht** Teil dieser Lieferung. Begründung: Trip hat drei eigene Reiter, Ortsvergleich nur zwei — „ab dem zweiten" ist deshalb wörtlich nicht anwendbar und bräuchte vorher eine Klärung, ab welchem Reiter „gleich" gilt. Das wird als eigene Folge-Lieferung zurückgestellt; das Ticket bleibt danach offen, es entsteht kein neues.
- **Die Speichern-Taste wandert für BEIDE Bildschirmgrößen** (nicht nur mobil, wie das Nachtrag-Anliegen wörtlich nahelegt) in dieselbe geteilte Speicher-Leiste. Begründung: Speichern-Logik und -Text sind für Desktop und Handy identisch — eine Aufteilung würde dieselbe Funktion doppelt pflegen. Kein Verhalten ändert sich dadurch für den Nutzer.
- **Ein zusätzlicher technischer Nachzieheffekt**: Wenn die untere App-Leiste beim Ortsvergleich verschwindet, darf am unteren Rand kein leerer, ungenutzter Streifen stehen bleiben. Das stand nicht wörtlich im Nachtrag, ist aber eine notwendige Folge davon, dass die Leiste jetzt verschwindet.

## Wie abgesichert wird

- **Struktur- und Bildschirm-Tests (automatisiert, laufen bei jeder Auslieferung):** Kopfleiste, Vorlese-Text am Zurück-Pfeil (beide Bildschirmgrößen), Speichern-Taste, Ausblend-Effekt am Reiter-Streifen und die Sichtbarkeit der unteren App-Leiste werden für beide Anlege-Seiten geprüft.
- **Ein echter Klicktest (automatisiert):** nur für den Zurück-Tap auf dem Handy beim Trip — stellt sicher, dass dabei kein ungewollter Zwischenspeicher-Versand ausgelöst wird.
- **Nicht automatisch geprüft:** der Zurück-Klick am Schreibtisch-Bildschirm (nur manueller Durchklick vor der Produktiv-Auslieferung), und ob die Kopfleiste am echten Bildschirm tatsächlich gleich aussieht — die Tests prüfen Text und Aufbau, kein Bildvergleich.

## Entscheidung, um die es geht

Mit „approved" gibst du frei, dass beide Anlege-Seiten auf dem Handy optisch und im Aufbau angeglichen werden, inklusive des jetzt nachgewiesenen Vorlese-Texts — bei offen bleibender Reiter-Reihenfolge (eigene Folge-Lieferung) und nur manuell geprüftem Desktop-Zurück-Klick.

## Freigabe-Frage

Sollen Trip- und Ortsvergleich-Anlegeseite auf dem Handy angeglichen werden, während der Zurück-Klick am Schreibtisch nur manuell geprüft wird?
