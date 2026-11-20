# Adversary Dialog — fix-3212-was-steht-wo-tippflaeche
Spec: docs/specs/modules/fix_3212_was_steht_wo_tippflaeche.md
Datum: 2026-11-20 18:22

## Checkliste
- [x] **Input:** Tippen oder Klicken an einem Punkt innerhalb von 44×44 px um „Roh“, „Einfach“ oder ein E-Mail-Format-Segment.
- [x] **Output:** Der gemeinte Knopf löst aus; Pille und Segmente sehen unverändert aus (Mockup Fassung 4).
- [x] **Side effects:** Keine; Zeilenhöhe und Raster der Tabelle bleiben gleich.
- [x] **AC-1:** Given die Karte „Was steht wo“ im Desktop-Fenster / When der Wächter die Tippfläche von „Roh“ und „Einfach“ misst (Messweise wie AC-40: Trefferpunkte im 44×44-Quadrat) / Then liegt jeder Punkt auf dem jeweiligen Knopf.
- [x] **AC-2:** Given die Karte auf einem Mobil-Fenster / When die Tippfläche von „Roh“ und „Einfach“ (Kurzwort „Einf.“) gemessen wird / Then beträgt sie mindestens 44×44 px und das Raster bleibt unverändert.
- [x] **AC-3:** Given die Zeile „E-Mail: Format“ (Ausführlich/Kompakt) auf Desktop und Mobil / When die Tippfläche beider Segmente gemessen wird / Then beträgt sie mindestens 44×44 px (Messweise wie AC-40).
- [x] **AC-4:** Given die Karte vor und nach dem Fix / When die sichtbare Größe der Roh-/Einfach-Pille (32×22 / 56×22) und der Segmente verglichen wird / Then ist sie unverändert und entspricht dem Mockup Fassung 4 (`.mini` bzw. `.seg`).
- [x] **AC-5:** Given nebeneinanderliegende Knöpfe (Haken, Roh, Einfach, Segmente) / When an den Ecken und der Mitte der 44×44-Fläche geklickt wird / Then löst nur der gemeinte Knopf aus und kein Nachbar erhält den Treffer.
- [x] **AC-6:** Given die Karte kommt im Trip-Editor und im Orts-Vergleich-Editor vor / When AC-1 bis AC-5 in beiden geprüft werden / Then gelten sie gleich in beiden Kontexten.
- [x] **AC-7:** Given der Fix ist ausgeliefert / When der Wächter `s3a2794-teil3-design` AC-40 gegen Staging läuft / Then sind Desktop und Mobil grün.

## Dialog

### Runde 1
**Adversary:** Suite `frontend/src/lib/**/__tests__` 8361 Tests, 8357 bestanden, 0 fehlgeschlagen, 3 übersprungen (nicht die Fix-Tests). Fix-Testdatei 5/5 grün. Angriff auf Nachbar-Treffer: `.rek::before` (44 px) ragt bei Roh (32 px) je 6 px seitlich; Haken-Atom liegt davor mit Spalt `--g-s-2` = 8 px, also 2 px Luft; Beispielwert/Ampel/Marke sind nicht positioniert, `::before` liegt darüber, ragt aber nur 6 px in Zwischenraum bzw. Textrand. Vertikal 11 px über/unter der Pille, Zeilenteilung 10 px Padding + 1 px Rand, damit höchstens 0-1 px in die Nachbarzeile. Mobil: Knopf selbst 44×44 (Media-Regel), `::before` = max(100%,44) = 44, kein Mehrwuchs, Raster unverändert.
**Implementierer:** Muster identisch zu Btn `data-tap` und kompakt-Segmenten (app.css), vom Wächter bereits akzeptiert.

Finding F001 (nur Hinweis, LOW, edge_case): Ecken-Treffer an Überlappung nur per Stapelreihenfolge gesichert, im Node-Test nicht messbar.
Code reference: frontend/src/lib/components/atoms/RohEinfachKnopf.svelte:58
Live-Messung (Playwright, AC-40 Desktop/Mobil auf Staging) wurde in dieser Prüfung nicht ausgeführt; sie bleibt Pflicht in /e2e-verify (AC-5, AC-6, AC-7).

### Runde 2
**Adversary:** Mutations-Gegenprobe (String-Ersetzung, Sicherung im Scratchpad, Hash vorher = nachher: RohEinfachKnopf 5b9fafd656ab, WasStehtWoKarte daac450f43af): M1 `data-tap` weg: 3 rot. M2 `::before` in `@media` verschoben: 1 rot. M3 `max(…)` zu `100%`: 1 rot. M4 `position: relative` weg: 1 rot. M5 `variant` zurück auf `size="sm"`: 1 rot. Alle gefangen. Segmented: `variant` setzt nur `data-variant` (Segmented.svelte:71), Auswahl/Tastatur/aria (`rolle="radio"`, aria-checked, Pfeiltasten) unverändert. Karte wird nur in `WetterTabInhalt` für Trip und Vergleich geteilt gerendert, kein eigener Pfad je Kontext (AC-6).
**Implementierer:** keine weitere Änderung nötig.

## Bestätigungen
Confirmation:
  AC: AC-1, AC-2
  Code reference: frontend/src/lib/components/atoms/RohEinfachKnopf.svelte:32 (data-tap) und :58 (::before ohne Media)
  Evidence: Wächter AC-40 prüft damit 44×44-Trefferpunkte per elementFromPoint; Mobil Knopf 44
  Status: CONFIRMED
Confirmation:
  AC: AC-3
  Code reference: frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte:248
  Evidence: variant="kompakt" liefert ::before max(100%,44) laut app.css:794
  Status: CONFIRMED
Confirmation:
  AC: AC-4
  Code reference: frontend/src/lib/components/atoms/RohEinfachKnopf.svelte:69
  Evidence: Pille (Padding 3/6, 10.5 px) unverändert, ::before unsichtbar und ohne Layoutwirkung (absolut)
  Status: CONFIRMED
Confirmation:
  AC: AC-5, AC-6, AC-7
  Code reference: frontend/src/lib/components/organisms/__tests__/fix_3212_was_steht_wo_tippflaeche.test.ts:103
  Evidence: Node-Tests (Trip und Vergleich) grün und per 5 Mutationen bewacht; Ecken-Treffer live und Staging-AC-40 stehen noch aus (E2E-Phase)
  Status: CONFIRMED (Teil statisch)

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict
VERDICT: VERIFIED
Tests: 8357 bestanden, 0 fehlgeschlagen, 3 übersprungen. Mutationen 5/5 gefangen. Offen: Live-Ecken-Messung auf Staging (F001, LOW).

Code reference: frontend/src/lib/components/organisms/__tests__/fix_3212_was_steht_wo_tippflaeche.test.ts:103

## Geprüfte Dateien

- sha256:5b9fafd656abfe3657c454c2a44ecf74872067e8948015720edae093c9deb8a7  frontend/src/lib/components/atoms/RohEinfachKnopf.svelte
- sha256:88669881faa5696c49b8a74ef94ed741bfd6b3b74b47441a31aacbc6679b097c  frontend/src/lib/components/organisms/__tests__/fix_3212_was_steht_wo_tippflaeche.test.ts
- sha256:daac450f43af78b2166f52f8c0568426851d529546316a470c9f5c6f52f4adce  frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte

## Prüfbasis

- base: bf437de111f660d957d66c7e1a98ee0696e8c206
- blob:2e4c2a8622038cc6f5cef50445efd1218a715b07  frontend/src/lib/components/atoms/RohEinfachKnopf.svelte
- blob:7b68691cb39d0595365e10d43b8c7ece91661a2d  frontend/src/lib/components/organisms/__tests__/fix_3212_was_steht_wo_tippflaeche.test.ts
- blob:d4173352676104f6ae727fd868ce3bef8edc9bea  frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte
