---
entity_id: feat_3008_abgleich_waechter
type: feature
created: 2026-11-19
updated: 2026-11-19
status: draft
version: "1.0"
workflow: feat-3008-abgleich-waechter
tags: [elementliste, abgleich, waechter, epic-2913]
---

# Abgleich-Waechter: Besitzer-Kern-Test, Kopf-Reihenfolge-Test, engeres {metrik}-Muster

## Approval

- [ ] Approved

## Purpose

Haertet die Abnahme-Werkzeuge der Mockup-Abnahme (Epic #2913) gegen drei stille Luecken: verwaiste Eintraege in der Besitzerliste fallen heute erst im Staging-Lauf auf (#3008 F001), die Reihenfolge Kebab vor "Test schicken" im Seitenkopf ist nur per Byte-Golden bewacht (#3008 F002), und die Gegenrichtung des Abgleichs erklaert jeden Live-Text mit "+ " am Anfang als bekannt (#3011). Kein Produktcode und keine Nutzerdaten werden beruehrt.

## Source

- **File:** `frontend/e2e/elementliste_abgleich_logik.ts`
- **Identifier:** `gegenMuster`, `erwartungGegenrichtung`, `findeZusaetzliche`, `werteGegenrichtungAus`, `leseBesitzer`; neu: `metrikNamenAusRegister`, `metrikNamenAusListe`

> Schicht: ausschliesslich Frontend-Werkzeuge und -Tests (`frontend/e2e/`, `frontend/src/lib/`). Weder Go-API noch Python-Core betroffen.

> Querschnitts-Pruefpunkte: Trip/Ortsvergleich-Teilung nicht beruehrt (kein neuer Baustein, nur Pruefwerkzeug und Tests). Mandantentrennung nicht beruehrt (keine Nutzerdaten, kein Endpoint). Kanaele nicht beruehrt (kein Briefing- oder Alarm-Inhalt).

## Estimated Scope

- **LoC:** ca. +180 / -10 (davon ca. 120 Tests)
- **Files:** 5 (2 neu)
- **Effort:** low

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/e2e/elementliste_abgleich_logik.ts` | MODIFY | `{metrik}` in der Gegenrichtung nur auf bekannte Metriknamen; neuer Parameter `metrikNamen` in `findeZusaetzliche`/`werteGegenrichtungAus`; neue Funktionen `metrikNamenAusRegister`, `metrikNamenAusListe`; `leseBesitzer` prueft zusaetzlich Abschnitts-Besitzer |
| `frontend/e2e/elementliste-abgleich.staging.spec.ts` | MODIFY | Metriknamen einmal aus `/api/metrics` laden (Fehlschlag => leere Menge) und durchreichen |
| `frontend/src/lib/__tests__/elementliste_abgleich_metrik_gegenrichtung.test.ts` | CREATE | Kern-Test #3011 mit echter `elementliste.json` und Register-Fixture |
| `frontend/src/lib/__tests__/elementliste_besitzer_kern.test.ts` | CREATE | Kern-Test #3008 F001 mit echter Besitzer- und Elementliste |
| `frontend/src/lib/components/shared/hub-kopf/__tests__/hub_kopf_c2_mockup.test.ts` | MODIFY | Benannter SSR-Test der Leistenreihenfolge (#3008 F002) |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/einstellungen_neu/elementliste.json` | Daten | Quelle der Element-IDs, Abschnitte und `{metrik}`-Muster |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | Daten | Besitzerliste, die geprueft wird |
| `GET /api/metrics` (`src/app/metric_catalog.py`) | API | Registernamen `label_de`/`label_en` als Quelle der Metriknamen im Staging-Lauf |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/fixtures/f5_register_namen.json` | Fixture | Registernamen fuer netzfreie Kern-Tests |
| `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte` | Komponente | Gerenderte Leiste (`subscription-kebab`, `subscription-hub-send`), nur gelesen |
| `frontend/src/lib/components/shared/hub-kopf/__tests__/htmlBaum.ts` (Testhilfe im hub-kopf-Test) | Testhilfe | Dokument-Reihenfolge im SSR-Baum |
| Epic #2913, Abschluss-Sub-Issue #3009 (`--strict`) | Kontext | Abnahme-Lauf, der von den engeren Mustern profitiert |

## Implementation Details

1. **#3011:** In `gegenMuster` wird `{metrik}` nicht mehr zu `.+?`, sondern zu einer Alternation aus escapten Metriknamen (analog zu `ZAHL_TEXT` fuer `{zahl}`). Namen kommen aus dem Register (`metrikNamenAusRegister`: `label`/`label_de`/`label_en` aller Kategorien) plus den DE-Werten der Elementliste (`metrikNamenAusListe`). Ist die Menge leer oder der Abruf fehlgeschlagen, passt `{metrik}` auf nichts (fail-closed): unbekannte Texte erscheinen als `zusaetzlich`, nie still erklaert. Die Hinrichtung (`erwartung`, `bewerteKontoChips`) bleibt unveraendert.
2. **Verdrahtung:** Der Staging-Lauf laedt `/api/metrics` einmal und reicht die Namen an `werteGegenrichtungAus` weiter; Fehlschlag => leere Menge.
3. **#3008 F001:** Der Kern-Test ruft `leseBesitzer(text, liste)` mit den echten Dateien auf. `leseBesitzer` prueft kuenftig neben Element-IDs auch Abschnitts-Besitzer (`art: abschnitt`) gegen die vorhandenen Tripel (ctx, reiter, abschnitt). Die Pruefung wirkt damit auch im Staging-Lauf. `zusaetzlich`-Besitzer (Text/Muster ohne Listenbezug) bleiben bewusst ungeprueft.
4. **#3008 F002:** Benannter SSR-Test in `hub_kopf_c2_mockup.test.ts` auf dem gerenderten Baum: in `hub-kopf-leiste` steht `subscription-kebab` vor `subscription-hub-send`, je Art (Trip, Orte) und Sprache (DE, EN).

Testlauf: `cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test <datei>`. Kein Mock-Theater: echte Dateien, echte Funktionen, Verfaelschung nur an Kopien im Speicher.

## Expected Behavior

- **Input:** Besitzerliste und Elementliste; Live-Texte der Gegenrichtung; gerenderte Seitenkopf-Leiste; Metriknamen aus Register und Liste.
- **Output:** Fehler mit betroffener ID bzw. Abschnitt bei Drift; `zusaetzlich`-Befund fuer Fremdtexte mit "+ "-Praefix; roter Test bei vertauschter Leistenreihenfolge.
- **Side effects:** Keine. Kein Produktcode, keine Nutzerdaten beruehrt; ein zusaetzlicher lesender Abruf von `/api/metrics` im Staging-Lauf.

## Acceptance Criteria

- **AC-1:** Given die echte Besitzerliste und die echte Elementliste / When der Kern-Test `leseBesitzer` mit beiden Dateien aufruft / Then wirft die Funktion nicht und liefert alle Besitzer-Eintraege.
  - Test: `node --test` ueber `elementliste_besitzer_kern.test.ts` mit den unveraenderten Dateien aus `docs/context/einstellungen_neu/`; Nutzersicht ist die Abnahme, die bei sauberer Liste nicht abbricht.

- **AC-2:** Given eine verfaelschte Kopie der Besitzerliste mit einer unbekannten Element-ID / When `leseBesitzer` sie gegen die Elementliste prueft / Then wirft sie einen Fehler, der die unbekannte ID nennt.
  - Test: Kern-Test aendert im Speicher einen Eintrag auf eine erfundene ID und erwartet einen Fehler, dessen Text die ID enthaelt.

- **AC-3:** Given eine verfaelschte Kopie der Besitzerliste mit einem Abschnitts-Besitzer, dessen Tripel (ctx, reiter, abschnitt) in der Elementliste nicht vorkommt / When `leseBesitzer` sie prueft / Then wirft sie einen Fehler, der den betroffenen Abschnitt nennt; die Pruefung wirkt auch im Staging-Lauf, weil dieser `leseBesitzer` aufruft.
  - Test: Kern-Test mit erfundenem Tripel erwartet einen Fehler mit Abschnittsnamen; der echte Bestand (15 Abschnitte) bleibt fehlerfrei.

- **AC-4:** Given die gerenderte Seitenkopf-Leiste `hub-kopf-leiste` fuer Trip und Orte in DE und EN / When der benannte Test die Dokument-Reihenfolge prueft / Then steht `subscription-kebab` vor `subscription-hub-send`, und eine vertauschte Reihenfolge faerbt den Test rot.
  - Test: SSR-Test in `hub_kopf_c2_mockup.test.ts` ueber vier Kombinationen; Gegenprobe durch Vertauschen der beiden Elemente in einer Kopie des gerenderten Baums.

- **AC-5:** Given die Gegenrichtung des Abgleichs mit bekannter Metrikmenge / When ein Live-Text "+ " plus Nicht-Metrik (z. B. "+ Quatsch") vorkommt / Then wird er in DE und EN als `zusaetzlich` gemeldet, waehrend "+ " plus echter Metrikname weiter als erklaert gilt.
  - Test: Kern-Test mit echter `elementliste.json` und Register-Fixture prueft "+ Quatsch" (zusaetzlich) und "+ <echte Metrik aus Register und Liste>" (erklaert), je DE und EN.

- **AC-6:** Given die Muster "{metrik} aus dem Briefing nehmen" und "Remove {metrik} from the briefing" / When der Live-Text einen Fremdnamen statt einer Metrik enthaelt / Then wird er als `zusaetzlich` gemeldet; mit echtem Metriknamen bleibt er erklaert.
  - Test: Kern-Test mit "Quatsch aus dem Briefing nehmen" bzw. "Remove Quatsch from the briefing" gegen echte Metriknamen.

- **AC-7:** Given eine leere oder fehlgeschlagene Registermenge / When die Gegenrichtung "+ "-Texte auswertet / Then erklaert `{metrik}` ueber das Register nichts zusaetzlich (nie still erklaert); nur DE-Namen aus der Elementliste gelten.
  - Test: Kern-Test ruft `findeZusaetzliche` mit leerer Registermenge auf; Register-EN-Namen erscheinen als `zusaetzlich`, "+ Quatsch" bleibt ebenfalls `zusaetzlich`, nichts wird still erklaert.

- **AC-8:** Given der Staging-Abgleich und der Abnahme-Lauf / When die Gegenrichtung laeuft / Then werden die Metriknamen genau einmal geladen und durchgereicht, die Hinrichtung (`erwartung`, `bewerteKontoChips`) bleibt unveraendert, und es werden weder Produktcode noch Nutzerdaten veraendert.
  - Test: Bestehende Hinrichtungs-Kern-Tests (`elementliste_abgleich_*.test.ts`) bleiben ohne Aenderung gruen; Diff beruehrt nur die fuenf Dateien aus dem Scope.

## Test Plan

### Automated Tests (TDD RED)

Kern-Schicht, deterministisch, ohne Netz; kein Mock-Theater (echte `elementliste.json`/`elementliste_besitzer.json`, Register-Fixture im Antwortformat von `/api/metrics`). Lauf: `cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test <datei>`.

- [ ] Neu `frontend/src/lib/__tests__/elementliste_besitzer_kern.test.ts`: echter Bestand wirft nicht (AC-1); erfundene Element-ID ⇒ Fehler mit ID (AC-2); erfundenes Abschnitts-Tripel ⇒ Fehler mit Abschnitt, rot vor der Erweiterung von `leseBesitzer` (AC-3).
- [ ] Erweitert `frontend/src/lib/components/shared/hub-kopf/__tests__/hub_kopf_c2_mockup.test.ts`: benannter Reihenfolge-Test Kebab vor „Test schicken ▾“, Trip/Orte × DE/EN (AC-4).
- [ ] Neu `frontend/src/lib/__tests__/elementliste_abgleich_metrik_gegenrichtung.test.ts`: „+ Quatsch“/„Quatsch aus dem Briefing nehmen“/„Remove Quatsch from the briefing“ ⇒ `zusaetzlich`, echte Metriknamen erklärt, DE und EN (AC-5, AC-6); leere Registermenge fail-closed (AC-7). Rot vor der Änderung von `gegenMuster`.
- [ ] Unverändert grün (Regression, einzeln benannt): `elementliste_abgleich_ganzseite.test.ts`, `elementliste_abgleich_verdrahtung.test.ts`, `elementliste_abgleich_bedienplan.test.ts`, `elementliste_abgleich_fixloop2.test.ts`, `hub_kopf_c2_mockup.test.ts` (übrige Tests), `tests/test_2913_c2_besitzerliste.py`, `tests/test_3007_besitzerliste.py` (AC-8).
- [ ] Mutations-Gegenprobe durch den Adversary (Kopie extern, String-Ersetzung, nie `git checkout/stash/reset`): `{metrik}` wieder `.+?` in der Gegenrichtung; Abschnitts-Prüfung in `leseBesitzer` entfernt; Kebab hinter den Knopf in `HubKopf.svelte`; Staging-Lauf reicht keine Metriknamen durch. Jede Verfälschung muss einen Test rot machen.
- Live: `npm run elementliste:abgleich` gegen Staging (DE) läuft durch; keine neuen `zusaetzlich` mit echtem Metriknamen.

## Definition of Done

- AC-1 bis AC-8 durch benannte Tests grün, Regressionstests einzeln grün.
- Mutations-Gegenprobe durch den Adversary ohne unbewachte Verfälschung.
- Vor dem ersten Code gegen `origin/main` abgeglichen.
- Alle 6 CI-Checks grün; Staging-Abgleich ohne neue Fehlbefunde; Prod-Deploy und Selftest bestanden.
- #3008 und #3011 geschlossen, Kommentar im Epic #2913.

## Known Limitations

- `zusaetzlich`-Besitzer sind Text/Muster ohne Listenbezug und werden nicht auf Existenz geprueft.
- DE-Metriknamen der Mockup-Schreibweise (z. B. "Luftfeuchtigkeit") gelten ueber die Elementliste, bis #3012 sie dem Register angleicht.
- Ohne erreichbares Register gelten nur Listen-Namen; echte Register-Namen koennen dann als `zusaetzlich` erscheinen (gewollt sichtbar statt still).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Rein technische Haertung bestehender Pruefwerkzeuge; keine Entscheidungsflaeche (Kanaele, Provider, Datenmodell, Auth, Test-/Deploy-Strategie) wird veraendert.

## Changelog

- 2026-11-19: Initial spec created (Paket #3008 + #3011, Epic #2913)
