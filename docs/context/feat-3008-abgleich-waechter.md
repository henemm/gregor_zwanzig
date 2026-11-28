# Context: feat-3008-abgleich-waechter (#3008 + #3011, Epic #2913)

## Request Summary
Paket aus zwei kleinen Härtungen der Mockup-Abnahme (Epic #2913), beide aus offenen LOW-Befunden:
- **#3008** F001: Besitzer-Einträge in `elementliste_besitzer.json` werden gegen die Elementliste nur im Staging-Lauf geprüft (`ladeRegeln` → `leseBesitzer(text, liste)` wirft bei unbekannter Element-ID). Kein Kern-Test ⇒ verwaiste IDs fallen erst auf Staging auf. F002: Reihenfolge Kebab vor „Test schicken ▾“ im Seitenkopf nur per Byte-Golden (f9/f10) bewacht, kein benannter Test.
- **#3011**: Gegenrichtung des Abgleichs erklärt mit dem Muster `+ {metrik}` jeden Live-Text, der mit „+ “ beginnt (`gegenMuster` macht `{metrik}` zu `.+?`). Fremdtexte fallen nie als `zusaetzlich` auf, auch nicht im Abschluss-Lauf `--strict` (#3009).

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/e2e/elementliste_abgleich_logik.ts` | `gegenMuster` (Z. ~548), `erwartungGegenrichtung` (~559), `findeZusaetzliche` (~687), `werteGegenrichtungAus` (~717), `leseBesitzer`/`pruefeBesitzer`/`ladeRegeln` (~745–815), `kontoPfade`/`ladeKontoTexte` (~820) |
| `frontend/e2e/elementliste-abgleich.staging.spec.ts` | Staging-Lauf; ruft `ladeKontoTexte` (Z. 345) und `werteGegenrichtungAus` (Z. 429) — Verdrahtung neuer Metrik-Namen |
| `docs/context/einstellungen_neu/elementliste.json` | 78 Einträge mit `{metrik}`: 36× `+ {metrik}` (chip, `wetter.nicht_im_briefing.hinzufuegen`), 42× `{metrik} aus dem Briefing nehmen` (knopf, `wetter.zeile.entfernen`); EN `Remove {metrik} from the briefing` |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | `besitzer` (Verweise: #2968 446, #2795 314, #2967 247, #3111 156, #2913 82, #3022 62 (Stand 2026-11-28 durch #3022 auf 0 entfernt), #2796 38, #3122 10, #2797 8, #2913-e 2) + `ausnahmen` |
| `tests/test_2913_c2_besitzerliste.py`, `tests/test_3007_besitzerliste.py` | bestehende Python-Kern-Tests (doc-compliance) über die Besitzerliste — Muster für neuen Kern-Test |
| `frontend/src/lib/__tests__/elementliste_abgleich_*.test.ts` | bestehende `node --test`-Kern-Tests der Abgleich-Logik (ganzseite, verdrahtung, bedienplan, fixloop2) |
| `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte` Z. 100–110 | `.hub-actions`: `SubscriptionKebab` (testid `subscription-kebab`) vor `Btn` (testid `subscription-hub-send`) |
| `frontend/src/lib/components/shared/hub-kopf/__tests__/hub_kopf_c2_mockup.test.ts` Z. 212–250 | SSR-Tests der Leiste (Prüfstände f9/f10, `htmlBaum.ts`); prüft Kebab und Knopf je einzeln in der Leiste, NICHT die Reihenfolge |
| `src/app/metric_catalog.py` | Metrik-Register: `label_de`, `label_en` (Quelle der Metriknamen, ausgeliefert über `GET /api/metrics`) |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/fixtures/f5_register_namen.json` | vorhandene Fixture mit `label_en` je Metrik-ID |

## Existing Patterns
- Abgleich-Logik ist reine Funktionen-Datei; Kern-Tests importieren sie mit `node --import ./test-lib-loader.mjs --experimental-strip-types --test`.
- Konto-Texte (Namen aus API) werden im Staging-Lauf geladen und als Liste in die Gegenrichtung gereicht; fehlgeschlagener Abruf ⇒ keine Texte (nie geraten) — gleiches Fail-closed-Muster passt für Metriknamen.
- Gegenrichtung behandelt `{zahl}` bereits enger (`ZAHL_TEXT`), Fix-Loop 4 — `{metrik}` ist das Analogon.
- Besitzer-Prüfung gegen die Liste existiert schon als Funktion (`leseBesitzer(text, elemente)`) — der Kern-Test kann sie mit den echten Dateien aufrufen statt Logik zu duplizieren.

## Dependencies
- Upstream: `elementliste.json` (aus Mockup generiert, `scripts/elementliste_aus_mockup.ts`), Metrik-Register (`/api/metrics`).
- Downstream: `npm run elementliste:abgleich` (`--strict`, `--abnahme`), Abschluss-Sub-Issue #3009.

## Existing Specs
- `docs/specs/modules/feat_2913_abgleich_ganzseite.md` (Gegenrichtung), `docs/specs/modules/feat_2913_c2_seitenkopf.md` (Seitenkopf, AC-12/AC-13).

## Risks & Considerations
- Engeres `{metrik}` darf echte Metriknamen nicht als `zusaetzlich` melden — DE- und EN-Namen müssen vollständig vorliegen (sonst Flut neuer Befunde im Abnahme-Lauf). Abschwächung: Metriknamen aus der Elementliste selbst (DE-Werte aus `text_de`) plus Register (DE+EN).
- Abschnitts-Besitzer (`art: abschnitt`) und `zusaetzlich`-Besitzer werden heute auch im Staging-Lauf nicht auf Existenz geprüft; nur Element-IDs. Scope des Kern-Tests: mindestens alle Element-IDs (nicht nur #2913), Abschnitts-Tripel prüfen ist eine sinnvolle Erweiterung.
- Reihenfolge-Test muss auf der gerenderten Leiste (SSR) prüfen, wo die Reihenfolge wirkt, nicht auf Quelltext.
- Keine Berührung von Nutzer-Oberfläche oder Daten ⇒ kein Staging-Deploy-Risiko; Lieferung über CI.

## Analysis

### Type
Feature (Härtung der Abnahme-Werkzeuge, zwei LOW-Befunde; kein Nutzer-sichtbares Verhalten)

### Ist-Stand der Daten (gemessen 19.11.2026)
- Besitzerliste: 850 element, 15 abschnitt, 500 zusaetzlich. Verwaiste Element-IDs: 0, verwaiste Abschnitts-Tripel (ctx, reiter, abschnitt): 0. Der neue Kern-Test ist also heute grün und wird erst bei künftigem Drift rot (gewollt).
- `{metrik}`-Muster: 36× `+ {metrik}` (chip), 42× `{metrik} aus dem Briefing nehmen` (knopf). Live-Text entsteht aus `$t('wetter.nicht_im_briefing.hinzufuegen', { metrik: m.name })` (`NichtImBriefing.svelte:23`) bzw. `wetter.zeile.entfernen` (`MetrikZeile.svelte:64`); `name` = Registername aus `GET /api/metrics` (`label_de`/`label_en`).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/e2e/elementliste_abgleich_logik.ts` | MODIFY | (a) `gegenMuster`/`erwartungGegenrichtung`: `{metrik}` passt in der Gegenrichtung nur auf bekannte Metriknamen (Alternation aus escapten Namen; leere Menge ⇒ passt auf nichts, fail-closed). (b) `findeZusaetzliche`/`werteGegenrichtungAus`: neuer Parameter `metrikNamen`. (c) neue reine Funktionen `metrikNamenAusRegister(antwort)` (label/label_de/label_en aller Kategorien) und `metrikNamenAusListe(liste)` (DE-Werte aus `text_de` gegen `muster`). (d) `leseBesitzer(text, elemente)`: zusätzlich Abschnitts-Besitzer gegen vorhandene (ctx, reiter, abschnitt) prüfen. |
| `frontend/e2e/elementliste-abgleich.staging.spec.ts` | MODIFY | Metriknamen einmal laden (`api.get('/api/metrics')`, fehlgeschlagen ⇒ leere Menge, nie geraten) und an `werteGegenrichtungAus` reichen |
| `frontend/src/lib/__tests__/elementliste_abgleich_metrik_gegenrichtung.test.ts` | CREATE | #3011: echte `elementliste.json` + Register-Fixture; „+ Quatsch“ ⇒ zusaetzlich (DE und EN), „+ <echte Metrik>“ erklärt; ebenso „<Fremd> aus dem Briefing nehmen“ |
| `frontend/src/lib/__tests__/elementliste_besitzer_kern.test.ts` | CREATE | #3008 F001: echte Besitzer- und Elementliste durch `leseBesitzer(text, liste)` (wirft heute nicht); verfälschte Kopie mit unbekannter Element-ID bzw. unbekanntem Abschnitt ⇒ Fehler nennt die ID |
| `frontend/src/lib/components/shared/hub-kopf/__tests__/hub_kopf_c2_mockup.test.ts` | MODIFY | #3008 F002: benannter Test „Reihenfolge der Leiste: Kebab vor ‚Test schicken ▾‘“ je Art×Sprache, auf dem SSR-Baum (Dokument-Reihenfolge der beiden testids in `hub-kopf-leiste`) |

### Scope Assessment
- Files: 5 (2 neu)
- Estimated LoC: +~180 / -~10 (davon ~120 Tests)
- Risk Level: LOW — nur Prüfwerkzeug und Tests; kein Produktcode, keine Daten

### Technical Approach
1. **#3011 Quelle der Metriknamen:** Laufzeit-Register (`/api/metrics`), weil der Live-Text genau daraus entsteht; ergänzt um die DE-Namen aus der Elementliste (Mockup-Schreibweise, z. B. „Luftfeuchtigkeit“, bis #3012 angleicht). Kein statischer Snapshot im Code (würde bei neuen Metriken veralten). Fail-closed: ohne Register gelten nur Listen-Namen; unbekannte „+ …“-Texte erscheinen sichtbar als `zusaetzlich`, nie still erklärt.
2. Der Kern-Test von #3011 nutzt die vorhandene Fixture `f5_register_namen.json` (label_en je ID) bzw. eine kleine eigene Register-Fixture im Antwortformat von `/api/metrics`, damit er ohne Netz läuft.
3. **#3008 F001:** Prüfung gegen die Elementliste existiert schon in `leseBesitzer`; der Kern-Test ruft sie mit den echten Dateien auf (wirkt dort, wo der Staging-Lauf sie wirkt), statt die Logik in Python zu duplizieren. Erweiterung auf Abschnitts-Tripel schließt dieselbe Lücke für `art: abschnitt`. `zusaetzlich`-Besitzer sind Text/Muster ohne Listen-Bezug, nicht prüfbar (bewusst außen vor).
4. **#3008 F002:** Reihenfolge auf dem gerenderten Baum, nicht im Quelltext; Mutation „Kebab hinter Knopf“ muss den benannten Test rot färben.

### Dependencies
- Keine neuen Pakete. Testlauf: `cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test <datei>`.

### Open Questions
- keine (rein technische Härtung; Produktentscheidung nicht berührt)
