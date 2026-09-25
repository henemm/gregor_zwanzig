---
entity_id: rework_2276_s1_netz_und_fundament
type: refactor
created: 2026-09-18
updated: 2026-09-18
status: draft
version: "1.0"
tags: [compare, trips, etag, ci, testing]
---

# Netz und Fundament für die Compare-Speicherweg-Umstellung (Issue #2276, Scheibe S1, Epic #2345)

## Approval

- [ ] Approved

## Purpose

Der Umbau des Ortsvergleich-Hubs auf den Trip-Speicherweg (Issue #2276, Scheiben
S2–S6) beruht vollständig auf der Zusicherung „ein Teil-PUT, das nur ein
Feld schickt, lässt alle übrigen Felder unverändert". Diese Scheibe baut noch
nichts um — sie schließt zwei belegte Lücken im Fundament, bevor die
Folgescheiben darauf bauen: (1) für einen der beiden Compare-PUT-Wege fehlt
der Test, der genau diese Zusicherung mit einem echten Minimal-Body belegt,
(2) der bestehende Konflikt-Wiederholen-Mechanismus (`retryConflict`) ist fest
auf Trips verdrahtet und wäre für einen Ortsvergleich nach einem
Speicherkonflikt (412) wirkungslos. Zusätzlich nimmt diese Scheibe die
bereits vorhandenen, aber nicht geratschten Ortsvergleich-Hub-Persistenztests
in die CI-Ampel auf, damit die Folgescheiben nicht ohne Sicherheitsnetz
umbauen.

## Source

- **File (Go):** `internal/handler/compare_preset.go:292-354` (`applyComparePresetPatch`),
  `internal/handler/briefing_subscription.go:174-196` (`mergeBriefingPatch`)
- **File (Frontend):** `frontend/src/lib/api.ts:222-224` (`refreshTripEtag`,
  wird zu `refreshResourceEtag`),
  `frontend/src/lib/stores/saveStatusStore.svelte.ts:144-156` (`retryConflict`)
- **File (CI-Ratsche):** `.github/ci_e2e_specs.txt`, `.github/workflows/ci.yml`
- **Identifier:** `applyComparePresetPatch`, `refreshResourceEtag` (vormals
  `refreshTripEtag`), `SaveStatus.retryConflict`

Betroffene Schichten: **Go-API** (`internal/handler/`, Testdatei) und
**Frontend** (`frontend/src/lib/`, SvelteKit). Kein Python-Core-Code in dieser
Scheibe. `.github/ci_e2e_specs.txt`/`ci.yml` sind CI-Konfiguration, kein
Anwendungscode.

## Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `internal/handler/compare_preset_single_field_patch_test.go` | CREATE | Minimal-PUT-Test Weg 1, belegt AC-1 |
| `internal/handler/compare_preset_etag_ifmatch_test.go` | MODIFY | Kommentarkorrektur an `comparePresetPutBody` (Zeilen 38-39), kein Verhaltensfix |
| `internal/handler/compare_preset_alert_channel_thresholds_test.go` | MODIFY | Kommentarkorrektur am AC-9-Testbody (Zeilen 80-81), kein Verhaltensfix |
| `frontend/src/lib/api.ts` | MODIFY | `refreshTripEtag` → `refreshResourceEtag(id, kind)` — `kind: NachladeKennung['typ']` als zweiter Pflichtparameter, keine Ableitung mehr |
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` | MODIFY | `SaveStatus`/`createSaveStatus` nehmen eine `NachladeKennung` statt einer bloßen ID entgegen |
| `frontend/src/routes/trips/[id]/+page.svelte` | MODIFY | Z. 43: `createSaveStatus(trip.id)` → `createSaveStatus({ typ: 'trip', id: trip.id })` |
| `frontend/src/lib/__tests__/apiRefreshTripEtag.test.ts` | MODIFY | drei bestehende Aufrufe (Z. 30, 45, 63) bekommen `'trip'` als jetzt verpflichtendes zweites Argument |
| `frontend/src/lib/etagRegistry.ts` | MODIFY | **nur Kommentar** (Z. 42-44): die Zusicherung „Preset-Kennungen tragen immer das Präfix `cp-`" ist für Bestandsdaten falsch und hat den Fehlentwurf verursacht |
| `frontend/src/lib/stores/__tests__/saveStatusConflictRetry.test.ts` | MODIFY | Test-Factory + neue Describe-Blöcke für AC-2/AC-5 (Alt-Kennung **ohne** Präfix **und** `cp-`-Kennung), bestehende Fälle unverändert (AC-3) |
| `.github/ci_e2e_specs.txt` | MODIFY | Aufnahme der im Drei-Läufe-Test grünen Kandidaten aus (3) |
| `.github/workflows/ci.yml` | MODIFY | `E2E_MIN_SPECS` und `E2E_MIN_EXECUTED_HAUPT` auf die neuen exakten Werte angehoben |

## Estimated Scope

- **LoC:** Go ≈ +90/−4 (neuer Test + zwei Kommentarkorrekturen); Frontend
  ≈ +25/−6 Produktivcode (`api.ts`, `saveStatusStore.svelte.ts`,
  `trips/[id]/+page.svelte`, Kommentarkorrektur `etagRegistry.ts`) und +90
  bis +150 in neuen/erweiterten Testdateien (abhängig davon, wie viele
  Kandidaten Bestandteil (3) tatsächlich grün aufgenommen werden können,
  plus die drei Ein-Zeilen-Anpassungen in `apiRefreshTripEtag.test.ts`);
  CI-Konfiguration ≈ +10/−2 (`ci_e2e_specs.txt` + `ci.yml`-Schwellenwerte).
- **Files:** 3 Go (1 neu, 2 Kommentarkorrekturen), 6 Frontend (3
  Produktivdateien, 1 reine Kommentarkorrektur, 2 Testdateien),
  2 CI-Konfigurationsdateien.
- **Effort:** medium. Das Gesamtvolumen liegt voraussichtlich über dem
  250-LoC-Standardbudget (drei fachlich unabhängige Bestandteile in einer
  Scheibe) — `loc_limit_override` ist einzuplanen, kein Nachschneiden der
  Scheibe (CLAUDE.md-Regel, RED darf nicht eigenmächtig verengt werden).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `applyComparePresetPatch` / `mergeBriefingPatch` / `mergeConfigMap` | function | gemeinsamer Merge-Kernel beider Compare-PUT-Wege (#2285), Prüfling von (1) |
| `extractTripId` / `RESOURCE_PATH_RE` (`etagRegistry.ts:46-63`) | function | erkennt `/api/compare/presets/{id}` bereits korrekt — unverändert, nur als Fundament für (2) |
| `enqueueTripWrite`, `getKnownEtag`/`setKnownEtag` (`etagRegistry.ts`) | function | Schreib-Serialisierung und ETag-Registry — unverändert, gilt für Trips wie Ortsvergleiche bereits gemeinsam |
| `createFakeTripServer` (`frontend/src/lib/__tests__/fakeTripServer.ts`) | test-double | bildet den S2-Server-Vertrag nach; matcht bereits BEIDE Ressourcenarten (`TRIP_PATH_RE` dort), kein neuer Fake nötig |
| `NachladeKennung` (`frontend/src/lib/pwa/geraetespeicher.ts:104-105`) | type | bereits etablierter Diskriminierungstyp `{typ: 'trip'\|'vergleich'; id: string}` — wiederverwendet statt neu erfunden, s. Implementation Details (2) |
| `.github/ci_e2e_specs.txt` + `tests/unit/test_e2e_positivliste_ratschen_bindung.py` | ratchet | erzwingt exakte Übereinstimmung von `E2E_MIN_SPECS`/`ci.yml`-Env mit der Zeilenzahl der Liste — jede Aufnahme MUSS beide Werte mitziehen |

## Implementation Details

### (1) Beweislücke Weg 1 schließen (Go)

Neuer Test in `internal/handler/`, der einen PUT-Body mit **genau einem**
flachen Feld (`name`) sendet — ohne `schedule`, `profil`, `hour_from`,
`hour_to`, `location_ids`, `empfaenger` — gegen `PUT
/api/compare/presets/{id}` (Weg 1, `UpdateComparePresetHandler`). Vorbedingung:
ein gespeichertes Preset mit gesetztem `AlertChannelThresholds` auf **allen
vier** Kanälen (`Email`, `Telegram`, `Sms`, `PremiumSms` — der Typ hat keine
weiteren Felder, s. `internal/model/trip.go:218-223`) UND gesetztem
`OfficialWarnings.Sources` (mindestens zwei Einträge). Erwartung nach dem PUT:

- Antwort `200`, nicht `400` (die Merge-Ausgabe muss die Pflichtfeldprüfung
  `validateComparePreset` mit den aus `original` ererbten Werten bestehen —
  das ist der eigentliche Beweis: der Kernel muss die fehlenden Pflichtfelder
  aus dem gespeicherten Original ziehen, nicht nur akzeptieren, dass sie
  fehlen).
- `name` ist der neue Wert.
- `schedule`, `profil`, `hour_from`, `hour_to`, `location_ids`, `empfaenger`
  sind bytegleich zu `original`.
- `AlertChannelThresholds.Email`, `.Telegram`, `.Sms` UND `.PremiumSms` sind
  alle vier unverändert (Beleg: der generische Merge-Kernel schützt Weg 1
  genauso wie Weg 2, nicht nur die bereits belegten Ebene-1/Ebene-2-Fälle aus
  #1461 — dort waren nur zwei von vier Kanälen Teil der Fixture).
- `OfficialWarnings.Sources` ist unverändert (identische Länge und Reihenfolge).

Die zwei vorhandenen Weg-1-Tests, die dieselbe Zusicherung streifen
(`compare_preset_official_warnings_test.go`,
`compare_preset_alert_channel_thresholds_test.go`), senden beide weiterhin
alle Pflichtfelder im Body mit — sie belegen NICHT, dass ein PUT ohne
Pflichtfelder überhaupt angenommen wird. Der neue Test ist die erste
Belegstelle dafür.

**Kommentarkorrektur (kein Verhaltensfix, reine Doku-Richtigstellung):**

- `compare_preset_etag_ifmatch_test.go:38-39` — Kommentar über
  `comparePresetPutBody` beschreibt den Preset-PUT pauschal als
  „Voll-Ersetzen, kein Patch — Pflichtfelder muessen mit". Seit #2285 ist das
  falsch: der Helfer selbst sendet weiterhin einen vollständigen Body (das
  bleibt für seine eigenen Tests unverändert korrekt), aber die Aussage über
  den PUT-**Mechanismus** ist veraltet. Kommentar auf „vollständiger Body aus
  Testbequemlichkeit, der Merge-Kernel würde auch ein Teil-Update
  akzeptieren" umformulieren.
- `compare_preset_alert_channel_thresholds_test.go:80-81` — dieselbe
  veraltete Aussage im Kommentar über den Testbody von AC-9, analog
  korrigieren.

### (2) `refreshTripEtag` → `refreshResourceEtag`, entitätsneutral (Frontend)

`refreshTripEtag(tripId: string)` ruft heute fest `GET /api/trips/${tripId}`.

**Verworfener Entwurf — Pfadwahl über das ID-Präfix `cp-`.** Der Kommentar in
`etagRegistry.ts:42-44` sichert zu, Preset-Kennungen trügen „immer" das Präfix
`cp-` (`newComparePresetID()`, `compare_preset.go:83-88`). **Am Produktivbestand
gemessen (2026-09-18) ist das falsch:** `compare_presets.json` des Nutzers `henning`
enthält den Ortsvergleich mit der Kennung **`zillertal-t-glich`** —
ohne Präfix; `briefings/` enthält gemischt `cp-eb6ba0b239d90e37.json` (neu,
mit Präfix) und `zillertal-t-glich.json` (Bestand, ohne). Die Zusicherung gilt
nur für **neu erzeugte** Presets. Eine Pfadwahl über das Präfix wäre für genau
die real existierenden Alt-Ortsvergleiche wirkungslos — und ein Test mit einer
`cp-`-Kennung wäre dabei grün geblieben und hätte den Fehler verdeckt. Das ist
schlechter als der Ist-Zustand und deshalb ausgeschlossen.

**Verbindlicher Entwurf — die Ressourcenart wird übergeben, nie abgeleitet,
über den bereits im Projekt etablierten Diskriminierungstyp.** Das Frontend
hat dieses Problem bereits einmal gelöst: `NachladeKennung`
(`frontend/src/lib/pwa/geraetespeicher.ts:104-105`, `{ typ: 'trip' |
'vergleich'; id: string }`) unterscheidet Trip und Ortsvergleich exakt für
denselben Zweck (Entlade-/Nachlade-Mechanik, `sichereAusstehendeSpeicherung`,
`starteNachladenNachEntladen`) und wird an beiden bestehenden Aufrufstellen
bereits als Objektliteral direkt neben der `SaveStatus`-Erzeugung gebildet:
`trips/[id]/+page.svelte:50` schreibt schon heute `{ typ: 'trip', id:
trip.id }`, `compare/[id]/+page.svelte:66` schon heute `{ typ: 'vergleich',
id: currentPreset.id }`. `SaveStatus`/`createSaveStatus` bekommen denselben
Typ als (optionalen) Konstruktorparameter, statt eine zweite, neue
Unterscheidung zu erfinden:

```ts
import type { NachladeKennung } from '../pwa/geraetespeicher.ts';

export class SaveStatus {
	private _tripId?: string;
	private _resourceKind?: NachladeKennung['typ'];

	constructor(kennung?: NachladeKennung) {
		this._tripId = kennung?.id;
		this._resourceKind = kennung?.typ;
	}
	// …
	async retryConflict(): Promise<void> {
		if (this.state !== 'conflict' || !this._lastFailed || !this._tripId || !this._resourceKind) return;
		// …
		await refreshResourceEtag(this._tripId, this._resourceKind);
		// …
	}
}

export function createSaveStatus(kennung?: NachladeKennung): SaveStatus {
	return new SaveStatus(kennung);
}
```

Das erfüllt die drei Zusicherungen strukturell, nicht nur per Konvention:

1. **Keine Ableitung aus der Kennung.** Die Pfadwahl liest ausschließlich
   `kennung.typ`, nie die ID selbst — weder Präfix, noch Länge, noch
   Zeichenklasse spielen eine Rolle.
2. **Das Vergessen der Angabe fällt beim Typcheck auf, nicht erst zur
   Laufzeit.** `NachladeKennung` bündelt `typ` und `id` in einem Objekt — eine
   bloße ID-Zeichenkette ist kein gültiges Argument mehr.
   `createSaveStatus(trip.id)` (die heutige Aufrufform) lässt sich nach
   diesem Umbau nicht mehr kompilieren; `svelte-check`/`tsc` weist es ab. Ein
   Vorgabewert „Trip" (z. B. `typ: 'trip'` als Default) wird bewusst NICHT
   eingebaut — das reproduzierte exakt den Fehler, den diese Scheibe behebt.
   Bleibt die Kennung ganz weg (`createSaveStatus()`, heutiger Zustand des
   Compare-Hubs vor S2), degradiert der Konfliktschutz wie bisher zu einem
   generischen Fehlerzustand — das ist unverändert zulässig, weil dann gar
   keine Pfadwahl stattfindet.
3. **`/api/briefings/{id}` bleibt außen vor** (s. u.).

`_tripId`/`_resourceKind` bleiben als getrennte private Felder bestehen
(statt eines einzelnen `_kennung`-Felds), weil mehrere bestehende
Testdateien (`apiKeepaliveSkipsIfMatch.test.ts`, `serviceWorkerUpdate.test.ts`,
`trip_speicherung_reicht_keepalive_durch.test.ts`) `SaveStatus`-Instanzen per
`Object.create(SaveStatus.prototype)` ohne Konstruktor bauen und dabei direkt
`fields._tripId = tripId` setzen (Muster erzwungen durch Svelte-5-Runen
außerhalb des Compiler-Kontexts, s. Kommentar in `saveStatus.test.ts`). Diese
Tests rufen `retryConflict()` nie auf (geprüft: kein Treffer für
`retryConflict` in den drei Dateien) — sie verlassen sich nur auf die
UNVERÄNDERTE `doSave()`-Zusicherung „ein 412 mit gesetztem `_tripId` wird zum
Konflikt", die weiterhin ausschließlich `_tripId` prüft. Ein einzelnes
`_kennung`-Feld hätte sie unbemerkt gebrochen (dann bräuchten drei fachfremde
Dateien Änderungen); die getrennten Felder halten den Blast-Radius auf genau
die Dateien, die tatsächlich `retryConflict()` treiben.

**Achtung bei `saveStatusConflictRetry.test.ts` (anders als die drei Dateien
oben):** dessen eigene `createTestInstance(tripId?: string)`-Factory (Z. 50-64)
RUFT `retryConflict()` in praktisch jedem Testfall auf. Diese Factory muss
einen zweiten Parameter für `_resourceKind` bekommen, UND alle **zehn**
bestehenden Aufrufe der Factory in dieser Datei (`grep -c
"createTestInstance(" saveStatusConflictRetry.test.ts` → 10, nachgemessen
2026-09-18) müssen auf `createTestInstance('gr20', 'trip')` erweitert
werden — sonst würde die neue, striktere `retryConflict()`-Wächterbedingung
(`!this._resourceKind`) genau die bestehenden AC-3-Regressionsfälle
stillschweigend zu Kein-Op machen und AC-3 liefe fälschlich grün, ohne noch
etwas zu prüfen. Das ist der einzige Ort, an dem „bestehende Fälle
unverändert" (Affected Files) sich auf die Assertions bezieht, nicht auf den
Wortlaut jedes Aufrufs der Factory.

**`doSave()`s 412-Erkennung bleibt bewusst NUR an `_tripId` geknüpft, nicht
zusätzlich an `_resourceKind`.** Naheliegend wäre, beide Bedingungen
symmetrisch zu machen (`this._tripId && this._resourceKind`) — das würde
aber `apiKeepaliveSkipsIfMatch.test.ts`,
`trip_speicherung_reicht_keepalive_durch.test.ts:166` und
`serviceWorkerUpdate.test.ts:793/926` brechen: alle drei fabrizieren ihre
`SaveStatus`-Instanz per `Object.create` und setzen NUR `fields._tripId`,
nie `_resourceKind`, und prüfen `state === 'conflict'` nach einem 412 direkt
über `doSave()`. Sie überleben diese Scheibe nur, weil `doSave()`s Guard
unverändert bleibt; erst `retryConflict()` (dort nicht aufgerufen) bekommt
die zusätzliche `_resourceKind`-Bedingung. Wer diese beiden Guards
vereinheitlicht, bricht drei fachfremde Dateien ohne Testnutzen.

`refreshTripEtag` wird zu **`refreshResourceEtag`** umbenannt und bekommt die
Art als **zweiten Pflichtparameter** (kein Vorgabewert):
`refreshResourceEtag(id: string, kind: NachladeKennung['typ']):
Promise<void>`. Die Umbenennung kostet keine zusätzlichen Änderungen
gegenüber einem Namenserhalt — jeder Aufrufer (Produktivcode UND die drei
Testfälle in `apiRefreshTripEtag.test.ts`, Zeilen 30, 45, 63) wird ohnehin
angefasst, weil die Signatur sich ändert. Der alte Name wäre ab dieser
Scheibe irreführend (er suggeriert „nur Trips"), und genau ein irreführender
Name in `etagRegistry.ts:42-44` hat den verworfenen Entwurf oben erst
verursacht — derselbe Fehler soll hier nicht neu entstehen. Die Testdatei
behält ihren Namen `apiRefreshTripEtag.test.ts` (Testdateien werden nach
Verhalten benannt, nicht nach dem exportierten Symbol; ihr geprüftes
Verhalten — „ETag nach Konflikt aktualisieren" — ändert sich nicht).

**Kommentarkorrektur `etagRegistry.ts:42-44` (Pflichtbestandteil):** Die
Zusicherung „eine Verwechslung mit einer Trip-Kennung ist damit ausgeschlossen"
ist am Bestand widerlegt und hat den verworfenen Entwurf verursacht. Sie wird
auf den tatsächlichen Stand korrigiert (Präfix gilt nur für neu erzeugte
Presets; Alt-Kennungen sind Slugs). Ohne diese Korrektur führt derselbe
Kommentar die nächste Sitzung in denselben Fehler.

Kein Eingriff in `extractTripId`/`RESOURCE_PATH_RE` (`etagRegistry.ts`) — die
erkennen `/api/compare/presets/{id}` für If-Match/ETag-Übernahme/Serialisierung
bereits korrekt (Risk 1 im Kontextdokument, gemessen 2026-09-18). Kein
Eingriff in `/api/briefings/{id}` — der bleibt bewusst außerhalb der
ETag-Registry (Kontextdokument, Risk 1: „der Hub bleibt auf
`/api/compare/presets/{id}`").

### (3) Ortsvergleich-Hub-Persistenztests in die CI-Ampel aufnehmen

Kandidatenliste (heute vorhanden, aber NICHT in `.github/ci_e2e_specs.txt`):
`compare-hub-save-chip`, `compare-hub-name-region-profil`,
`compare-hub-versand-inline` (enthält den Lost-Update-Nachweis F004,
`:311-369`), `compare-hub-inline-edit`, `compare-hub-briefing-times`,
`compare-metric-order`, `compare-hourly-metric-order`, `compare-alarm-config`,
`compare-layout-tab-dissolution`.

**Verfahren (bindend, identisch zur bisherigen Aufnahme-Praxis der Liste,
s. Kopfkommentar `ci_e2e_specs.txt:6-25`):**

1. Jeden Kandidaten gegen Filter A prüfen (kein `waitForTimeout`,
   `test.skip`, `test.fixme`, `describe.skip`, kein Schreiben von
   `page.screenshot({path: ...})` in einen versionierten Ordner ohne
   `../`-Präfix). Vier der neun Kandidaten enthalten nachweislich
   `page.waitForTimeout(...)` (`compare-hub-save-chip.spec.ts:173`,
   `compare-hub-name-region-profil.spec.ts:240`,
   `compare-hourly-metric-order.spec.ts:411`,
   `compare-alarm-config.spec.ts:53`) und sind damit **ohne vorherige
   Änderung an der Spec-Datei selbst** keine Filter-A-Kandidaten — diese
   Änderung ist NICHT Teil dieser Scheibe (Umfang wäre sonst unkalkulierbar).
2. Jeden verbleibenden Filter-A-Kandidaten dreimal hintereinander gegen den
   isolierten lokalen Stack laufen lassen (Muster: Kopfkommentar
   `ci_e2e_specs.txt:27-34`, NICHT gegen Staging).
3. Nur die drei-mal grünen Dateien werden `.github/ci_e2e_specs.txt`
   hinzugefügt, alphabetisch einsortiert.
4. `E2E_MIN_SPECS` in `ci.yml` auf die neue exakte Zeilenzahl der Liste
   angehoben (bindend geprüft von
   `tests/unit/test_e2e_positivliste_ratschen_bindung.py::pruefe_schwellen_bindung`
   — Abweichung ist ein Kern-Testfehlschlag, kein Warnhinweis).
   `E2E_MIN_EXECUTED_HAUPT` um die tatsächliche, per `--list` ermittelte
   Fallzahl der neu aufgenommenen Dateien erhöhen (nicht geschätzt).
5. Jeder Kandidat, der Filter A nicht besteht oder im Drei-Läufe-Test nicht
   durchgehend grün ist, wird NICHT aufgenommen. Stattdessen: Name, Datei,
   Zeile und Befund (welcher Filter/welcher Testfall) als Zeile im
   Sammel-Issue **#1196** dokumentiert.

Diese Scheibe ändert an den E2E-Spec-Dateien selbst nichts (kein
`waitForTimeout`-Ersatz, keine Testreparatur) — sie zieht ausschließlich die
bereits grün laufenden Dateien in die Ampel. Reparatur der vier
Filter-A-durchfallenden Dateien ist ein eigener, im Sammel-Issue zu
buchender Nebenbefund.

**Realistische Ausbeute voraussichtlich kleiner als neun (Risikohinweis, kein
Vorgriff auf den Drei-Läufe-Test):** Fünf der neun Kandidaten
(`compare-hub-save-chip`, `compare-hub-name-region-profil`,
`compare-metric-order`, `compare-hourly-metric-order`,
`compare-layout-tab-dissolution`) haben eine eigene
`playwright.<name>.staging.config.ts` und/oder `<name>.staging.setup.ts` —
ein eigenes Login-/Seed-Setup für den Staging-Lauf. Das ist genau das Muster,
das der Kopfkommentar von `ci_e2e_specs.txt` bei `issue-579-home-fidelity`
als Ausschlussgrund dokumentiert („Vorbedingung im GETEILTEN Seed nicht
herstellbar" — der CI-`e2e`-Hauptlauf nutzt ausschließlich das geteilte
`e2e/global.setup.ts`, keine dateispezifischen Setups). Ob die jeweilige
`.spec.ts`-Datei trotzdem gegen den geteilten Seed läuft, ist NICHT
angenommen, sondern im Drei-Läufe-Test je Kandidat zu prüfen. Die verbleibenden drei Kandidaten ohne Filter-A-Fund
(`compare-hub-versand-inline`, `compare-hub-inline-edit`,
`compare-hub-briefing-times`) haben weder ein eigenes Staging-Setup noch
einen `page.screenshot({path: …})`-Treffer (Filter C, geprüft) — sie sind die
wahrscheinlichsten Kandidaten für eine tatsächliche Aufnahme in dieser
Scheibe. Insbesondere `compare-hub-versand-inline` ist der wichtigste
Einzelfall: er trägt den Lost-Update-Nachweis F004. `compare-alarm-config`
scheidet in dieser Scheibe bereits an Filter A aus (s. o.) und ist damit
kein Kandidat, unabhängig vom Staging-Setup-Befund.

## Expected Behavior

- **Input (1):** ein PUT-Body mit einem einzelnen flachen Feld gegen
  `PUT /api/compare/presets/{id}`.
- **Output (1):** `200`, alle nicht gesendeten Felder (flach UND
  verschachtelt: `alert_channel_thresholds`, `official_warnings.sources`)
  bleiben unverändert erhalten.
- **Input (2):** ein `retryConflict()`-Aufruf auf einer `SaveStatus`-Instanz,
  die mit einer `NachladeKennung` vom `typ: 'vergleich'` erzeugt wurde — die
  ID selbst kann beliebig geformt sein (`cp-…` oder ein Alt-Slug wie
  `zillertal-t-glich`), nach einem 412.
- **Output (2):** der Refresh-GET geht an `/api/compare/presets/{id}`, nicht
  an `/api/trips/{id}` — unabhängig von der Form der ID, weil die Pfadwahl
  ausschließlich `typ` liest; der anschließende Retry-PUT trägt den frisch
  aufgefrischten ETag und gelingt unter denselben Bedingungen wie beim
  bestehenden Trips-Fall.
- **Side effects:** keine neuen. Der Merge-Kernel (1) bleibt eine reine
  Funktion; (2) fügt keinen neuen Zustand hinzu, nur eine explizit
  übergebene Fallunterscheidung.

## Acceptance Criteria

- **AC-1 (Minimal-PUT Weg 1 verlustfrei):** Given ein gespeicherter
  Ortsvergleich mit gesetzten Alarm-Kanal-Schwellen auf allen vier Kanälen
  und gesetzten amtlichen Warnquellen / When ein PUT auf
  `/api/compare/presets/{id}` nur ein einzelnes Feld ohne die Pflichtfelder
  enthält / Then wird der PUT angenommen und alle nicht gesendeten Felder
  bleiben unverändert, ausdrücklich einschließlich aller vier
  Alarm-Kanal-Schwellen und der amtlichen Warnquellen-Liste.
  - Test: neuer Go-Test gegen den echten Handler mit echtem Datei-Store
    (`t.TempDir()`), Minimal-Body, Assertion auf jedes einzelne erhaltene
    Feld nach dem Laden vom Store.

- **AC-2 (Konflikt-Wiederholen trifft die richtige Adresse):** Given ein
  Ortsvergleich, dessen Speichern mit einem Konflikt (412) fehlschlägt /
  When der Nutzer „Wiederholen" auslöst / Then holt der Refresh den frischen
  Stand von `/api/compare/presets/{id}`, nicht von `/api/trips/{id}`, und der
  wiederholte Speichervorgang gelingt mit dem frisch aufgefrischten Stand.
  - Test: Erweiterung der bestehenden Konflikt-Wiederholen-Testsuite um
    **zwei** Fälle gegen den vorhandenen Ersatz-Server (`fakeTripServer.ts`,
    der beide Ressourcenarten bereits bedient), jeweils mit Assertion auf den
    tatsächlich aufgerufenen Pfad des Refresh-GET und auf Erfolg des
    Retry-PUT:
    1. **Alt-Kennung ohne Präfix** (Form von `zillertal-t-glich`) — das ist
       der heute kaputte Fall und der eigentliche Prüfling.
    2. Kennung **mit** `cp-`-Präfix — damit beide Bestandsformen belegt sind.
  - **Bindend:** Ein Test, der die Zusicherung nur an einer `cp-`-Kennung
    prüft, erfüllt AC-2 **nicht** — er wäre auch mit der verworfenen
    Präfix-Ableitung grün und beweist daher nichts.
  - **Hinweis (bewusste Lücke, kein Mangel dieser Scheibe, Korrektur einer
    ungenauen Vorfassung):** Der Hub hat bereits heute einen echten
    `SaveStatus`-Controller (`compare/[id]/+page.svelte:59`,
    `hubSaveCtl = createSaveStatus()`) — er ist verdrahtet
    (`beforeNavigate`-Wächter `:66`, `speicherAnmeldestelle.anmelden` `:82`,
    als `saveController` an `CompareTabs` durchgereicht `:494`,
    `SaveIndicator` liest ihn dort `CompareTabs.svelte:1081`). Tot ist nicht
    der Controller, sondern sein Konfliktzustand: **jeder** Commit-Handler im
    Hub meldet einen fehlgeschlagenen PUT über `saveController?.setError(...)`
    direkt (`CompareTabs.svelte:284, 549, 674, 784, 875, 1029`), nie über
    `doSave()` — und nur `doSave()` setzt `state='conflict'`. Ein 412 im Hub
    landet deshalb heute IMMER im generischen Fehlerzustand, unabhängig vom
    Ergebnis dieser Scheibe. Diese Scheibe macht den Mechanismus korrekt und
    entitätsneutral bereit; S2 schließt die Lücke, indem es die
    Commit-Handler auf `doSave()` umstellt (Kontextdokument, Entscheidung
    E2). Der Nachweis in AC-2 läuft deshalb bewusst auf Store-/API-Ebene,
    nicht über eine Klick-Strecke — eine UI-Strecke gäbe es zwar (der
    Controller existiert), sie würde aber den Konfliktzweig heute gar nicht
    erreichen.

- **AC-3 (Trip-Verhalten unverändert):** Given dieselbe
  Konflikt-Wiederholen-Situation bei einer Trip / When Refresh und Retry
  laufen / Then bleibt das Verhalten exakt wie vor dieser Scheibe (Refresh
  gegen `/api/trips/{id}`, Retry gelingt).
  - Test: die bestehende Suite `saveStatusConflictRetry.test.ts` läuft
    unverändert und bleibt vollständig grün — kein Testfall wird angepasst,
    nur ergänzt.

- **AC-4 (Netz in der Ampel):** Given die neun benannten
  Ortsvergleich-Hub-Persistenztest-Kandidaten / When jeder Kandidat gegen
  Filter A geprüft und die verbleibenden dreimal hintereinander lokal
  ausgeführt werden / Then stehen genau die dabei durchgehend grünen
  Kandidaten in `.github/ci_e2e_specs.txt` und laufen dort in der
  CI-Ampel grün; die übrigen sind namentlich mit Befund im Sammel-Issue
  #1196 dokumentiert, nicht Teil der Liste.
  - Test: Nachweis über einen tatsächlichen CI-Lauf des `e2e`-Jobs nach dem
    Merge (Live-E2E) plus lokales Drei-Läufe-Protokoll als Aufnahmebeleg,
    analog zum bestehenden Vorgehen im Kopfkommentar der Datei.

- **AC-5 (Mutations-Gegenprobe, zwei Verfälschungen):** Given die übergebene
  Ressourcenart aus AC-2 ist umgesetzt / When sie versuchsweise verfälscht
  wird / Then wird jeweils mindestens ein Test rot:
  1. **Rückfall auf festen Trip-Pfad** (Refresh ruft wieder bedingungslos
     `/api/trips/${id}`) ⇒ **beide** Ortsvergleichs-Fälle aus AC-2 werden rot.
  2. **Rückfall auf die verworfene Präfix-Ableitung** (Pfadwahl über
     `id.startsWith('cp-')`) ⇒ der Fall mit der **Alt-Kennung ohne Präfix**
     wird rot, der `cp-`-Fall bleibt grün. Genau diese Verfälschung ist der
     Beleg, dass der Test die Zusicherung an der Stelle prüft, an der sie
     wirkt — und nicht bloß am bequemen Fall.
  - Test: identisch zu den Tests aus AC-2 — deren Assertion auf den
    tatsächlich aufgerufenen Pfad ist die Gegenprobe selbst, keine separate
    Testdatei nötig.

## Mutations-Gegenprobe

- **(a)** In `applyComparePresetPatch` den Merge-Aufruf umgehen und den Patch
  stattdessen direkt in ein frisches `model.ComparePreset{}` unmarshalen
  (Rückfall auf Vollersetzen-Semantik, wie vor #2285) ⇒ AC-1 wird rot: der
  Minimal-Body ohne Pflichtfelder liefert dann `400 validation_error` statt
  `200`, weil `schedule`/`profil`/`hour_from`/`hour_to`/`location_ids`/
  `empfaenger` im frischen Struct leer sind.
- **(b1)** Den Refresh fest auf `/api/trips/${id}` zurücksetzen (übergebene
  Ressourcenart ignorieren) ⇒ beide Ortsvergleichs-Fälle aus AC-2 werden rot,
  AC-3 bleibt fälschlich grün (der Beleg, dass AC-3 allein die Regression
  NICHT gefangen hätte — AC-2 ist die tragende Zusicherung).
- **(b2)** Die Pfadwahl auf das verworfene `id.startsWith('cp-')` umstellen
  ⇒ **nur** der Alt-Kennungs-Fall wird rot. Bleibt er grün, prüft die Suite
  den heute kaputten Fall nicht und AC-2 gilt als nicht erfüllt.
- **(b3)** Die Ressourcenart-Angabe bei einem bestehenden Trip-Aufrufer
  entfernen ⇒ muss beim Typcheck/`svelte-check` auffallen, nicht still zum
  Trip-Pfad werden (Zusicherung 2 aus Abschnitt (2)).
- **(c)** In `mergeBriefingPatch` den verschachtelten Zweig entfernen (kein
  `mergeConfigMap`-Aufruf mehr, jedes Overlay-Feld wird unbedingt per
  `base[k] = v` ersetzt) ⇒ der neue AC-1-Test aus dieser Scheibe fängt das
  NICHT (sein Patch enthält weder `alert_channel_thresholds` noch
  `official_warnings` als Key — die Prüfung dieser Objekte in AC-1 belegt nur
  „bleibt erhalten, wenn der Patch das Objekt gar nicht erwähnt", nicht den
  Ebene-2-Feld-Merge). Rot wird stattdessen der bereits bestehende
  `TestUpdateComparePreset_AlertChannelThresholdsFieldLevelMergePreservesUntouchedChannel`
  (#1461 AC-10, `compare_preset_alert_channel_thresholds_test.go`), dessen
  Patch genau ein Unterfeld mitschickt. **Konsequenz für den Scope:** diese
  Mutation zeigt, dass AC-1 und #1461-AC-10 zwei disjunkte Fälle prüfen
  („Objekt fehlt im Patch" vs. „Objekt ist im Patch, aber nur teilweise") —
  #1461 bleibt deshalb unverändert bestehen, es ist kein Ersatz durch AC-1.

## Test-Plan

| AC | Datei | Schicht |
|---|---|---|
| AC-1 | neuer Test in `internal/handler/compare_preset_single_field_patch_test.go` | Kern (Go, `t.TempDir()`-Store, kein Netz) |
| AC-2, AC-5 | Erweiterung `frontend/src/lib/stores/__tests__/saveStatusConflictRetry.test.ts` | Kern (Frontend, `fakeTripServer.ts`, kein echtes Netz) |
| AC-3 | bestehende Fälle in `saveStatusConflictRetry.test.ts` unverändert | Kern |
| AC-4 | `.github/ci_e2e_specs.txt` + realer `e2e`-CI-Lauf | Live-E2E (Staging-naher isolierter Stack in CI) |

Kern-Schicht: deterministisch, ohne Netz/Live-Dienste, Tests lösen den
Prüfling relativ zur eigenen Testdatei auf. Live-E2E-Schicht (AC-4): Nachweis
ausschließlich über den tatsächlichen CI-Lauf nach dem Merge — kein
lokaler Ersatz dafür, dass die Ampel grün bleibt.

## Known Limitations

- **Kein Ersatz für die vier Filter-A-durchfallenden Kandidaten in dieser
  Scheibe.** `compare-hub-save-chip`, `compare-hub-name-region-profil`,
  `compare-hourly-metric-order`, `compare-alarm-config` bleiben außerhalb der
  Ampel, bis ihr jeweiliger `waitForTimeout`-Aufruf durch eine deterministische
  Wartebedingung ersetzt ist — das ist ein eigener Nebenbefund (#1196), keine
  Aufgabe dieser Scheibe.
- **Keine Migration von `/api/briefings/{id}`.** Dieser Pfad bleibt bewusst
  außerhalb der ETag-Registry und außerhalb von `refreshResourceEtag` — der
  Hub bleibt in dieser und den Folgescheiben auf `/api/compare/presets/{id}`.
- **Kein Umbau der Compare-Klebeschicht.** `compareHubWizardBridge`,
  `compareEditorSave`, `compareWizardState`, `hubPutQueue` bleiben
  unverändert — sie werden erst in S2–S6 abgelöst (Kontextdokument, E4/E2).
- **AC-4 ist kein reiner Kern-Nachweis.** Der endgültige Beleg entsteht erst
  im echten `e2e`-CI-Lauf nach dem Merge, nicht im lokalen Drei-Läufe-Protokoll
  allein — Konsequenz aus der Natur der Ratsche (sie bewacht den CI-Stand,
  nicht den lokalen).
- **Gemeinsamer Namens- und Schlüsselraum von Trips und Ortsvergleichen —
  nicht Teil dieser Scheibe.** Beide Arten liegen in derselben Ablage
  (`briefings/<id>.json`, laut Befund der Team-Lead-Sitzung —
  `/var/lib/gregor/` ist aus diesem Worktree nicht lesbar, s. o.:
  `gr221-mallorca.json`, `heimat.json`, `zillertal.json` neben
  `zillertal-t-glich.json` und `cp-eb6ba0b239d90e37.json`) und teilen sich in
  `etagRegistry.ts` **einen**
  Schlüsselraum. Die Begründung im dortigen Kommentar („Verwechslung
  ausgeschlossen, weil `cp-`-Präfix") trägt am Bestand nicht. Trügen eine Trip
  und ein Ortsvergleich dieselbe Kennung, überschrieben sich ihre ETags
  gegenseitig — mögliche Folge: ein gemeldeter Konflikt ohne Anlass oder ein
  Schreibvorgang mit fremdem Stempel. Diese Scheibe korrigiert **nur den
  irreführenden Kommentar**; der Sachverhalt selbst wird als eigener Befund
  gemeldet (nutzersichtbares Fehlverhalten möglich ⇒ eigenes Issue nach der
  Nebenbefund-Triage, nicht Sammel-Issue).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Diese Scheibe führt keine neue Entscheidungsfläche ein. Sie
  belegt eine bereits getroffene Entscheidung (#2285: ein gemeinsamer
  Merge-Kernel für beide Compare-PUT-Wege) mit dem bisher fehlenden Test und
  verallgemeinert `refreshResourceEtag` (vormals `refreshTripEtag`)/`SaveStatus`
  auf den bereits im Frontend
  etablierten Diskriminierungstyp `NachladeKennung` (`{typ: 'trip'|
  'vergleich'; id}`, `geraetespeicher.ts`) — keine neue Unterscheidung, nur
  Wiederverwendung einer bestehenden. Die Aufnahme bestehender Testdateien in
  die CI-Ratsche ändert keine Architektur, nur den Prüfumfang der
  bestehenden Ratsche (analog zu jeder früheren Aufnahme in
  `ci_e2e_specs.txt`).

## Changelog

- 2026-09-18: Initial spec created
- 2026-09-18: Abschnitt (2) und AC-2/AC-5 überarbeitet — die Pfadwahl über das
  ID-Präfix `cp-` ist am Produktivbestand widerlegt (`zillertal-t-glich` ohne
  Präfix) und durch eine verpflichtend übergebene Ressourcenart ersetzt; AC-2
  prüft nun bindend eine Alt-Kennung ohne Präfix; Mutations-Gegenprobe um zwei
  Verfälschungen erweitert; Kommentarkorrektur `etagRegistry.ts` aufgenommen;
  Nebenbefund „gemeinsamer Schlüsselraum" dokumentiert.
- 2026-09-18: Konkrete Form der Ressourcenart festgelegt (war zuvor als
  Umsetzungsentscheidung offengelassen): Wiederverwendung des bereits
  bestehenden Diskriminierungstyps `NachladeKennung`
  (`frontend/src/lib/pwa/geraetespeicher.ts:104-105`,
  `{typ: 'trip'|'vergleich'; id}`) statt einer neu erfundenen Unterscheidung.
  `SaveStatus`/`createSaveStatus` nehmen eine `NachladeKennung` entgegen,
  `refreshTripEtag` bekommt `kind` als zweiten Pflichtparameter ohne
  Vorgabewert. Affected Files, Dependencies, Estimated Scope und die
  ADR-Rationale entsprechend nachgezogen.
- 2026-09-18: Nach Advisor-Gegenlesen drei Korrekturen: (1) AC-2-Hinweis
  berichtigt — der Hub-Controller existiert bereits und ist verdrahtet, tot
  ist nur der Konfliktzweig, weil die Commit-Handler `setError()` statt
  `doSave()` rufen; (2) exakte Fundstellenzahl in `saveStatusConflictRetry.test.ts`
  nachgemessen (10, nicht geschätzt) plus explizite Begründung, warum
  `doSave()`s 412-Guard bewusst NICHT symmetrisch zu `retryConflict()`s Guard
  wird; (3) `refreshTripEtag` wird zu `refreshResourceEtag` umbenannt, weil
  ohnehin jeder Aufrufer angefasst wird und der alte Name ab dieser Scheibe
  irreführend wäre.
- 2026-09-18: Herkunft des Produktivbestands-Befunds geklärt und bestätigt.
  `zillertal-t-glich` wurde in der führenden Sitzung direkt am Bestand
  gemessen (`/var/lib/gregor/users/henning/compare_presets.json` sowie das
  Verzeichnis `briefings/`, Lesezugriff über erhöhte Rechte); aus dem
  Arbeits-Worktree ist dieser Pfad nicht lesbar, der Befund dort also nicht
  nachvollziehbar, aber belegt. Abschnitt (2) („Verworfener Entwurf") wurde
  von zwei Bearbeitern nacheinander geschrieben; die zusammengeführte Fassung
  ist geprüft (Formprüfung VALID, keine Doppelungen, keine abgeschnittenen
  Stellen, kein Rückfall auf den verworfenen Entwurf).
