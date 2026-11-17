# Seiten zum Konzept „Einstellungen neu“

| Datei | Was | Stand |
|---|---|---|
| `mockup-hub-fassung4.html` | **Soll-Bild** des Hubs (Reiter Übersicht, Etappen/Orte, Wetter, Zustellung) für Trip, Orte mit drei Orten und Orte mit einem Ort. Quelle der Elementliste (`../elementliste.json`, Generator `scripts/elementliste_aus_mockup.ts`). | gültig seit 2026-11-17 (ADR-0124) |
| `grundentscheidungen.html` | Kopie der Entscheidungsseite mit den 12 Karten vom 2026-11-03 | historisch; Hinweisbalken nennt, was abgelöst ist |
| `abgleich-alt-neu.html` | Kopie des Abgleichs alt gegen neu vom 2026-11-03 | historisch; Hinweisbalken nennt, was abgelöst ist |
| `ampel-grenzen.html` | Kopie der Seite mit den Ampel-Grenzen je Vorlage | gültig |

## Fassung 3 gibt es nicht mehr als Datei

`mockup-hub-fassung3.html` wurde am 2026-11-17 durch `mockup-hub-fassung4.html` ersetzt (Issue #3122, ADR-0124). Fassung 4 ist
Fassung 3 mit genau drei Änderungen: Die Karte „Inhalt je Kanal und Fläche“ ist durch die Tabelle „Was steht wo“ ersetzt, der
Bereich heißt einheitlich „Orte“, und es gibt den Kontext „Orte · 1 Ort“. Alles andere ist zeichengleich.

Ältere Specs, Kontext-Notizen, ADRs und Code-Kommentare nennen noch den Pfad und Zeilennummern von Fassung 3. Sie beschreiben den
Stand ihrer Zeit und werden nicht umgeschrieben. Wer eine solche Stelle nachschlagen will: Der Inhalt steht unverändert in Fassung 4
(Zeilennummern verschoben), der letzte Stand der alten Datei liegt im Git-Verlauf (`git log -- docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html`).

Die Entscheidungsvorlage vom 2026-11-17 (Varianten-Mockup und Bildseite) liegt ebenfalls nur noch im Git-Verlauf, Commit `d5e57ca4b`.
Bilder der Karte in der gültigen Fassung: `../bilder-fassung4/`.
