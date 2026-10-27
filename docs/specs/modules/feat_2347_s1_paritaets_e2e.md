---
entity_id: feat_2347_s1_paritaets_e2e
type: feature
created: 2026-10-26
updated: 2026-10-26
status: draft
version: "1.0"
workflow: feat-2347-paritaets-e2e
tags: [epic-2345, etappe-p6, ratsche, e2e, playwright, trip-compare-teilung, mandantentrennung]
---

# Paritäts-E2E, Scheibe S1: Helfer, Versand-Autosave, Cross-User-Sperre, Wächter (#2347)

## Approval

- [ ] Approved

## Purpose

Die Playwright-Schicht spiegelt heute die Code-Doppelung: Was für den Ortsvergleich bewiesen ist (Autosave, Speicher-Chip, Schreibsperre zwischen Nutzern), ist für den Trip nicht bewiesen — und umgekehrt. Diese Spec legt für Epic #2345 (Etappe P6, Ticket #2347) das Fundament: dünne kind-Helfer, zwei erste Specs, die **eine** Zusicherung für **beide** Hubs per Schleife prüfen, und einen Wächter-Test, der verhindert, dass neue Compare-only-Specs ohne Begründung entstehen. Alles bleibt in #2347; S1 ist nur die erste von vier Scheiben, nichts wird abgespalten.

## Source

- **File:** `frontend/e2e/helpers.ts` (Helfer), `frontend/e2e/hub-versand-autosave-chip.spec.ts` (neu), `frontend/e2e/hub-cross-user-write-block.spec.ts` (neu, ersetzt `compare-cross-user-write-block.spec.ts`), `tests/unit/test_e2e_compare_paritaet_waechter.py` (neu)
- **Identifier:** `HubKind`, `HUB_KINDS`, `seedHub`, `openHub`, `hubApiPath` · Wächter `pruefe_compare_specs()`
- **Produktcode:** keiner. Reine Testschicht (`frontend/e2e/`, `tests/unit/`, CI-Ratsche, Gate-Doku).

**Schicht und Querschnitts-Prüfpunkte:**
- **Schicht:** ausschließlich Testschicht (Playwright gegen den CI-Stack bzw. Python-Unit-Wächter); kein Code in `frontend/src/`, `internal/`, `cmd/`, `api/`, `src/`.
- **Trip/Ortsvergleich-Teilung:** Kern dieser Spec — eine Spec je Verhalten, Schleife über beide kinds; der Wächter (AC-3) setzt die Teilung für E2E-Specs durch, die die Pendant-Sperre nicht erfasst.
- **Mandantentrennung:** AC-2 prüft mit zwei verschiedenen Nutzern (Eigentümer + registrierter Zweitnutzer) für beide kinds.
- **Kanäle:** nicht betroffen — kein Briefing- oder Alarm-Inhalt wird geändert; AC-1 prüft nur das Speichern der Versand-Uhrzeit.

## Gesamtschnitt #2347 (S1–S4, alles in diesem Ticket)

| Scheibe | Inhalt | Status |
|---|---|---|
| **S1 (diese Spec)** | Helfer; AC-1 Versand-Autosave + Chip je kind; AC-2 Cross-User-Sperre je kind (Umbenennung samt `MANDANTEN_SPECS`/Ratsche); Wächter im Ratschenmodus mit Altlastliste; Prüfdatum 2027-01-24; `E2E_MIN_SPECS`/`E2E_MIN_EXECUTED_HAUPT` | diese Spec |
| S2 | Hub-Kopf und Navigation: `compare-tab-bar` ↔ `mobile-tab-bar`; `compare-hub-name-region-profil` + `compare-hub-kopf-einmal` ↔ `trip-hub-kopf-region-aktivitaet`/`issue-724`; `bug-626-compare-menu-actions` ↔ `trips-list-aktionen` (12× `waitForTimeout` ersetzen); `compare-hub-save-chip` ↔ `issue-758-save-indicator`/`feat-880-autosave-overlay` | folgt |
| S3 (ggf. S3a/S3b) | `*-speichert-selbst`, `*-wertprops`, Versand-Trio (`compare-hub-versand-inline`, `compare-hub-briefing-times`, Rest von `compare-versand-speichert-selbst`), `compare-radar-toggle`, `compare-konfliktschutz-zwei-kontexte`, `compare-editor-autosave` (7× `waitForTimeout`), `issue-682-compare-editor-mobile` ↔ `issue-661-trip-new-mobile`, `compare-editor-slice3` AC-4..9 | folgt |
| S4 | Gruppe (c) (ohne Trip-Pendant) belegen und mit `gz-eigenstaendig:` versehen; `compare-editor-slice3`-Rest (Orte-Tab, AC-10); Altlastliste des Wächters auf leer; Ratsche final | folgt |

Je Scheibe: `E2E_MIN_EXECUTED_HAUPT` neu messen, Filter A (kein `waitForTimeout`/`skip`) und Filter B (3× grün im Zielverbund).

## Befund-Korrekturen gegenüber Ticket und Analyse (am Code gemessen, 2026-10-26)

1. **Vorbild:** nicht `daywindow-shared-both-contexts.spec.ts` (keine Schleife, `waitForTimeout(1_500)`, nicht in der Ratsche), sondern `trip-hub-kopf-region-aktivitaet.spec.ts:917-935` (`for (const hub of ['Trip','Vergleich'])`, in der Ratsche).
2. **Versand ist kein Reiter mehr** (#1743): Abschnitt `#versand` im Reiter Wetter-Metriken, `?tab=wetter-metriken#versand`, testids `versand-abschnitt`, `report-morning-time`.
3. **Fremder Trip → 404, nicht 403/404:** `UpdateTripHandler` (`internal/handler/trip.go:358-369`) lädt über den nutzergebundenen Store, findet nichts und antwortet `404 not_found` **vor** der If-Match-Prüfung und vor dem Dekodieren des Rumpfes. Der Compare-Handler antwortet ebenso `404` (`internal/handler/compare_preset.go`, Treffer „not_found" nach `LoadComparePresets`). Die Spec behauptet daher exakt **404**.
4. **Chip ist schon geteilt:** `SaveIndicator.svelte` (`data-testid="save-indicator"`, `data-state`, `.save-time`) über `SubscriptionHeader`; nichts im Produktcode zu tun.
5. **Abweichung von der Analyse — `compare-versand-speichert-selbst` entfällt in S1 NICHT.** Die Datei enthält sechs Zusicherungen (AC-1, 4, 5, 6, 7, 11: Reiterwechsel verliert nichts, „Bis auf Weiteres", 412 → „Nochmal speichern", Pausieren flusht, Legacy-Restfelder bleiben). Nur ihr AC-1 wird durch den neuen Spec ersetzt; der Rest bleibt bis S3 stehen. Dabei verschwindet das einzige `waitForTimeout(1_200)` der Datei (Z. 154), das heute Filter A verletzt.
6. **Abweichung von der Analyse — Trip-AC-11 wird nur zur Hälfte ersetzt:** In `trip-hub-kopf-region-aktivitaet.spec.ts` prüft AC-11 zuerst den Chip-Verlauf nach einem Region-Speichern (bleibt, gehört zu S2) und hängt dann einen Versand-Teil an (Z. ~974-990). Nur dieser Versand-Anhang wird ersetzt und aus AC-11 entfernt.
7. **Abweichung von der Analyse — Wächter-Regel 2 enger gefasst:** 82 Specs berühren `/compare/` oder `compare-detail-tab`, die meisten nur beiläufig (Startseite, PWA, Mobil-Audits). Eine Regel auf `/compare/` ergäbe eine Altlastliste von rund 70 Zufallstreffern. Regel 2 greift deshalb nur bei Specs, die den **Compare-Hub-Reiter** (`compare-detail-tab`) ansteuern und **kein** Trip-Gegenstück (`trip-detail-tab`, `/trips/`) und keine kind-Schleife und keinen Kopf haben. Gemessen: genau 2 Treffer außerhalb der Compare-Dateinamen (`kanal-grenzen-ortsvergleich.staging.spec.ts`, `versand-tab-vergleich.spec.ts`).
8. **Keine testMatch-Konfigurationen betroffen:** `grep -rn compare-cross-user-write-block .github tests frontend` findet nur Ratsche (`.github/ci_e2e_specs.txt:66,320`), `MANDANTEN_SPECS` (`tests/unit/test_e2e_positivliste_ratschen_bindung.py:27`), den Dateikopf selbst und einen Kommentar in `frontend/e2e/passkey-angebot.spec.ts:39` (Verweis; wird mitgezogen). Staging-/RED-Configs nennen die Datei nicht.

## Abgrenzung zu #2243 (Löschscheibe)

Nicht in der Ratsche gelistete Leichen (`trip-edit`, `compare-editor-slice4`, `compare-editor-fidelity-s8d`, `compare-flow-navigation`, `issue-1093-compare-layout-crash`, `compare-layout-tab-dissolution`, `compare-alarm-config`, …) gehören zu #2243 und werden in #2347 **nicht angefasst**. Der Wächter führt sie in der Altlastliste (sie tragen keinen Kopf); fällt eine durch #2243 weg, muss ihr Altlast-Eintrag im selben PR entfallen — der Wächter verlangt das (AC-3). In der Ratsche gelistete Dateien fallen unter #2347 (in S1: `compare-cross-user-write-block`, Teil von `compare-versand-speichert-selbst`). `.github/ci_e2e_specs.txt` wird nicht parallel mit #2243 bearbeitet (Merge-Konflikt).

## Estimated Scope

- **LoC (Testcode, netto):** ca. +330 / -150 (Helfer ~70, AC-1-Spec ~110, AC-2-Spec ~100, Wächter ~150; abzüglich alter Cross-User-Spec, AC-1 aus Vergleichs-Versand, Versand-Anhang aus Trip-AC-11). Alles Testcode/Doku, zählt nicht als produktive Spec-Datei.
- **Files:** 12 (siehe Liste berührter Dateien)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/e2e/helpers.ts` (`registriereBestaetigtenZweitnutzer`, `E2E_TEST_PREFIX`, `createTestLocation`) | module | Zweitnutzer, Präfix für Aufräumen |
| `frontend/e2e/global.setup.ts` | module | Admin-`storageState`, Seed-Orte `e2e-loc-innsbruck`/`e2e-loc-stubai` |
| `frontend/src/lib/components/ui/SaveIndicator.svelte` / `frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte` | module | geteilter Chip (unverändert) |
| `UpdateTripHandler`, Compare-Preset-Update-Handler | endpoint | 404 für fremde Objekte (unverändert) |
| `.github/ci_e2e_specs.txt`, `ci.yml` Job `e2e`, `.github/scripts/e2e_gate.py` | CI | Positivliste, `E2E_MIN_SPECS`, `E2E_MIN_EXECUTED_HAUPT` |
| `.claude/hooks/pendant_gate.py` | hook | Vorbild für Marker `gz-eigenstaendig:` (15 Zeichen Mindestbegründung); erfasst `frontend/e2e/` selbst nicht |

## Implementation Details

### Helfer in `frontend/e2e/helpers.ts` (dünn, keine Assertions)

```ts
export type HubKind = 'route' | 'vergleich';          // = context-Parameter der geteilten Bausteine
export const HUB_KINDS: readonly HubKind[] = ['route', 'vergleich'];

export interface SeededHub { kind: HubKind; id: string; aufraeumen(): Promise<void> }

// legt Trip bzw. Vergleich über die REST-API an (Präfix E2E-GZ-, Vergleich mit den
// Seed-Orten aus global.setup.ts), wirft bei !ok; morning_time standardmäßig 06:00
export async function seedHub(request: APIRequestContext, kind: HubKind,
                              opts?: { extra?: Record<string, unknown> }): Promise<SeededHub>;

// page.goto auf /trips/<id> bzw. /compare/<id> (+ ?tab=…, #hash); wartet nur auf die
// Sichtbarkeit der Reiterleiste, prüft sonst nichts
export async function openHub(page: Page, kind: HubKind, id: string,
                              opts?: { tab?: string; hash?: string }): Promise<void>;

export const hubApiPath = (kind: HubKind, id: string): string =>
  kind === 'route' ? `/api/trips/${id}` : `/api/compare/presets/${id}`;
```

Selektor-Unterschiede (Kopf-testids, Feldpfad der Versand-Uhrzeit im gespeicherten Stand) stehen als `HUB_SEL[kind]` im jeweiligen Spec, nicht im Helfer. Compare-Zusätze nur in `if (kind === 'vergleich')`, wenn fachlich nötig. Wartebedingungen ausschließlich über `page.waitForResponse` und `expect.poll`.

### Spec `hub-versand-autosave-chip.spec.ts` (AC-1)

`for (const kind of HUB_KINDS) test(\`AC-1 (${kind}): …\`)`. Ablauf je kind: `seedHub` → PUT-Zähler auf `hubApiPath` registrieren → `openHub(page, kind, id, {tab:'wetter-metriken', hash:'versand'})` → `versand-abschnitt` sichtbar, Vorbedingung 0 PUTs → `report-morning-time` auf `08:00` setzen → `expect.poll` auf beantworteten PUT → Chip `idle`, Text „Gespeichert", `.save-time` passt auf `^\d{2}:\d{2}$` → GET auf `hubApiPath`: Uhrzeit beginnt mit `08:00` (Feldpfad: Trip `report_config.morning_time`, Vergleich `morning_time`) → `page.reload()` → Auswahl zeigt weiter `08:00`. Genau **ein** PUT je Geste (ersetzt die Zählung aus Vergleichs-AC-1, ohne `waitForTimeout`: ein verspäteter zweiter PUT wird über `expect.poll` mit stabiler Anzahl über zwei Abfragen im Abstand von `expect.poll`-Intervallen abgesichert, nicht über Schlaf). Aufräumen im `finally` über `SeededHub.aufraeumen()`.

### Spec `hub-cross-user-write-block.spec.ts` (AC-2)

`test.describe.configure({ mode: 'serial' })`. Im `beforeAll`: Eigentümerkontext `ctxA = browser.newContext()` (erbt Admin-`storageState`), je kind `seedHub(ctxA.request, kind)`; **genau eine** Registrierung: `ctxB = browser.newContext({ storageState: undefined })`, `registriereBestaetigtenZweitnutzer(ctxA.request, ctxB.request, user, pw)` — das Token holt die Sitzung des Eigentümers (Muster #2271). Pro kind ein Testfall: B sendet `PUT hubApiPath(kind, id)` mit vollständigem, gültigem Rumpf (aus dem GET des Eigentümers, Name auf `Hijack` geändert, damit ein Erfolg erkennbar wäre) → Status exakt **404**; danach GET des Eigentümers: Name unverändert und `updated_at`/ETag unverändert. `afterAll`: Objekte löschen, `ctxB.close()`. Verbrauch: 1 Registrierung (Kontingent 5/h je IP) und 1 Login — genauso viel wie die ersetzte Spec.

### Wächter `tests/unit/test_e2e_compare_paritaet_waechter.py`

Kopfzeile `# doc-compliance-test` (Konventions-/Ratschenwächter über **Testdateien**, kein Verhaltensnachweis). Einordnung: Die Regeln „Dateiinhalt-Checks verboten" und der #765-Wächter (`tests/tdd/test_765_backend_hygiene_compliance.py`) betreffen das Lesen von **Produkt-Quelltext** (`.py`/`.go` unter `src/`/`api/`/`internal/`/`cmd/`). Der Wächter liest ausschließlich `frontend/e2e/*.spec.ts` (Testdateien, wie `test_e2e_positivliste_ratschen_bindung.py` schon heute) — kein `src/`-Zugriff, kein Konflikt. Dem Muster `pendant_gate.py` folgend (Marker `gz-eigenstaendig:`, mind. 15 Zeichen Begründung, Kopf = erste 30 Zeilen).

Reine Funktion `pruefe_compare_specs(dateien: dict[str, str], altlast: frozenset[str]) -> list[str]` (Befunde, leer = ok) plus ein Test, der sie auf den echten Baum anwendet, und Selbsttests mit synthetischen Eingaben (keine Mocks).

- **Regel 1:** Jede `frontend/e2e/*compare*.spec.ts` hat entweder eine kind-Schleife (`HUB_KINDS` oder das Altmuster `for (const … of ['Trip','Vergleich'])`) oder einen `gz-eigenstaendig:`-Kopf. Erlaubte Themen laut Epic: Orte-Tab, transponierte Übersicht, Compare-Mail — der Kopf nennt das Thema; jeder andere Grund ist ebenfalls zulässig, muss aber begründet sein (Ticket-AC-3).
- **Regel 2 (gegen Umgehung per Dateiname):** Jede andere Spec, die `compare-detail-tab` ansteuert und weder `trip-detail-tab` noch `/trips/` noch eine kind-Schleife noch einen Kopf enthält, ist ein Verstoß.
- **Ratschenmodus:** Konstante `ALTLAST` (explizite Dateinamensliste, beim Anlegen am Baum gemessen: heute alle `*compare*.spec.ts` ohne Kopf, minus der umbenannten Cross-User-Spec, plus `kanal-grenzen-ortsvergleich.staging.spec.ts` und `versand-tab-vergleich.spec.ts`) und `ALTLAST_MAX` (= Länge beim Einführen). Rot, wenn (a) eine Datei gegen Regel 1/2 verstößt und **nicht** in `ALTLAST` steht; (b) ein `ALTLAST`-Eintrag nicht mehr existiert oder inzwischen konform ist („Eintrag entfernen" — die Liste darf nur schrumpfen); (c) `len(ALTLAST) > ALTLAST_MAX`.
- Prüfdatum `PRUEFDATUM = date(2027, 1, 24)` als Konstante im Test und Eintrag in `docs/reference/gates_und_ratschen.md` (Abschnitt CI-Ratschen plus Tabelle „Regel-Budget: Prüfdaten im Überblick"). Fang-Beleg bei Einführung: die zwei Dateien außerhalb der Compare-Namen, die Regel 2 sofort findet, und die fehlende Trip-Cross-User-Prüfung.

### CI-Kopplung

- `.github/ci_e2e_specs.txt`: `e2e/compare-cross-user-write-block.spec.ts` → `e2e/hub-cross-user-write-block.spec.ts`; neu `e2e/hub-versand-autosave-chip.spec.ts`; Kommentar Z. 66 (Aufnahme 2026-08-14) auf den neuen Namen ziehen. Alphabetische Reihenfolge der Datei beachten.
- `tests/unit/test_e2e_positivliste_ratschen_bindung.py:27` `MANDANTEN_SPECS`: Eintrag auf `e2e/hub-cross-user-write-block.spec.ts`.
- `ci.yml`: `E2E_MIN_SPECS` 63 → **64** (63 − 0 durch Umbenennung + 1 neue Datei), exakt gleich der Listenlänge (`grep -c '^e2e/'`; der Kern-Test erzwingt Gleichheit). `E2E_MIN_EXECUTED_HAUPT` wird **gemessen, nicht geschätzt**: `npx playwright test --list` über die Hauptlauf-Auswahl (Positivliste ohne `bug-703`) am Endstand; Erwartung als Plausibilitätsprobe: 367 + 2 (AC-1, zwei kinds) + 2 (AC-2, zwei kinds) − 1 (alter Cross-User-Fall) − 1 (Vergleichs-AC-1) = **369** (inkl. `global.setup`). Weicht die Messung ab, gilt die Messung; Herleitung wird im bestehenden Kommentar fortgeschrieben. Die Zahl **steigt** hier; sinkt sie in späteren Scheiben, wird die Senkung begründet (Präzedenz PR #2495).
- Kommentar in `frontend/e2e/passkey-angebot.spec.ts:39` auf den neuen Dateinamen.

## Expected Behavior

- **Input:** CI-Lauf `e2e` gegen den isolierten Stack; Unit-Lauf des Wächters.
- **Output:** Trip- und Vergleichs-Hub werden durch **dieselben** Specs mit denselben Zusicherungen geprüft; eine neue Compare-only-Spec ohne Begründung macht den Unit-Lauf rot.
- **Side effects:** Testdaten mit Präfix `E2E-GZ-` (werden im `finally`/`afterAll` und durch `global.teardown.ts` geräumt); ein Zweitnutzer pro Lauf.

## Acceptance Criteria

- **AC-1:** Given ein Trip und ein Ortsvergleich mit Versand-Uhrzeit 06:00 / When der Nutzer im Hub im Abschnitt `#versand` des Reiters Wetter-Metriken die Morgen-Uhrzeit auf 08:00 ändert / Then geht genau ein PUT an den jeweiligen Endpunkt, der geteilte Speicher-Chip `save-indicator` steht auf „Gespeichert" mit Uhrzeit HH:MM, der gespeicherte Stand trägt 08:00 und der Wert überlebt das Neuladen — in einer Spec, die per Schleife über beide kinds läuft.
  - Test: `hub-versand-autosave-chip.spec.ts` (zwei Fälle, je kind), Staging/CI-Stack.
  - Mutation (muss rot werden): (a) im Vergleichs-Hub das `onchange`-Speichern des Versand-Abschnitts abschalten bzw. (b) im Trip-Hub den Controller-Aufruf der Versand-Uhrzeit entfernen → je nur der Fall des betroffenen kind wird rot (beweist: kein Fall prüft nur „Code steht dort"); Chip-Text „Gespeichert" ändern → beide rot; zweiten PUT erzwingen (doppelter Handler) → beide rot.
- **AC-2:** Given zwei verschiedene Nutzer, A besitzt einen Trip und einen Ortsvergleich / When Nutzer B per API auf beide mit PUT schreibt / Then antwortet der Server in beiden Fällen mit Status 404 (nicht 403, nicht 200), und der Trip bzw. Vergleich von A ist per GET des Eigentümers unverändert (Name, `updated_at`/ETag) — mit genau einer Zweitnutzer-Registrierung für beide kinds.
  - Test: `hub-cross-user-write-block.spec.ts` (Eigentümer- und Gastkontext getrennt, `beforeAll`-Registrierung).
  - Mutation: in `UpdateTripHandler` die Nutzer-Auflösung (`s.WithUser(middleware.UserIDFromContext(...))`) durch die feste Eigentümer-ID ersetzen → nur der Trip-Fall rot (200 statt 404, Name `Hijack`); dieselbe Verfälschung im Compare-Update-Handler → nur der Vergleichs-Fall rot; Erwartung 404 auf 403 ändern → beide rot.
- **AC-3:** Given der Ordner `frontend/e2e/` / When der Wächter-Unit-Test läuft / Then ist jede `*compare*.spec.ts` und jede Compare-Hub-Spec ohne Trip-Gegenstück entweder durch eine kind-Schleife oder durch einen `gz-eigenstaendig:`-Kopf (mind. 15 Zeichen Begründung) gedeckt oder steht in der expliziten Altlastliste, und die Altlastliste ist exakt (kein toter, kein konformer, kein zusätzlicher Eintrag über `ALTLAST_MAX`).
  - Test: `tests/unit/test_e2e_compare_paritaet_waechter.py` (echter Baum plus synthetische Selbsttests).
  - Mutation: neue Datei `compare-neu.spec.ts` ohne Kopf anlegen → rot; Marker mit weniger als 15 Zeichen → rot; Spec mit `compare-detail-tab` unter dem Namen `x-hub.spec.ts` ohne Schleife/Kopf → rot (Umgehung per Dateiname); Altlast-Eintrag einer inzwischen konformen oder gelöschten Datei stehen lassen → rot; `ALTLAST_MAX` überschreiten → rot.
- **AC-4:** Given die CI-Ampel / When die Ratsche geprüft wird / Then enthält `.github/ci_e2e_specs.txt` `hub-cross-user-write-block.spec.ts` und `hub-versand-autosave-chip.spec.ts` und nicht mehr `compare-cross-user-write-block.spec.ts`, `E2E_MIN_SPECS` entspricht exakt der Listenlänge (64), `MANDANTEN_SPECS` nennt die umbenannte Datei, und `E2E_MIN_EXECUTED_HAUPT` ist der am Endstand per `--list` gemessene Wert (erwartet 369) mit fortgeschriebener Begründung.
  - Test: `tests/unit/test_e2e_positivliste_ratschen_bindung.py` (Existenz, Gleichheit, Mandanten-Specs) sowie der CI-Job `e2e` (exakte Ausführungszahl via `e2e_gate.py`).
  - Mutation: Eintrag in der Liste auf nicht existierenden Dateinamen ändern → Existenzprüfung rot; `E2E_MIN_SPECS` um 1 verfälschen → Kern-Test rot; `E2E_MIN_EXECUTED_HAUPT` um 1 verändern → `e2e_gate.py` rot; Spec aus Liste streichen → rot.
- **AC-5:** Given die neuen Specs und der geänderte Rest / When sie im Zielverbund (Hauptlauf der Positivliste) dreimal hintereinander laufen / Then sind alle drei Läufe grün, und die neuen sowie die in S1 angefassten Specs (`hub-*`, `compare-versand-speichert-selbst`, `trip-hub-kopf-region-aktivitaet`) enthalten kein `waitForTimeout` und kein `skip` (Wartebedingungen über `waitForResponse`/`expect.poll`); der Versand-Anhang ist aus Trip-AC-11 und AC-1 aus `compare-versand-speichert-selbst` entfernt, die übrigen Zusicherungen beider Dateien laufen unverändert grün.
  - Test: Filter B (3× CI-Hauptlauf bzw. lokal gegen den CI-Stack) und `grep -c waitForTimeout` über die genannten Dateien = 0.
  - Mutation: `waitForTimeout` in eine der Dateien einfügen → Filter-A-Prüfung rot; beim Entfernen von AC-1 aus `compare-versand-speichert-selbst` versehentlich einen weiteren Fall (z. B. Reiterwechsel) mitlöschen → Fallzahl-Prüfung rot: Fallzahl der Datei vorher 6, nachher genau 5.

## Zuordnung alt → neu (Regressionsnetz)

| Alt (Datei · Zusicherung) | Neu | Anmerkung |
|---|---|---|
| `compare-cross-user-write-block.spec.ts` · B-PUT auf A-Preset → 404, Name unverändert | `hub-cross-user-write-block.spec.ts` · Fall `vergleich` | Datei entfällt; Registrierung unverändert 1× |
| — (Lücke: kein Trip-Pendant) | `hub-cross-user-write-block.spec.ts` · Fall `route` | schließt die Ticket-Lücke; zusätzlich ETag/`updated_at` unverändert |
| `compare-versand-speichert-selbst.spec.ts` · AC-1 (genau ein PUT, „Gespeichert", Server-Stand 08:00) | `hub-versand-autosave-chip.spec.ts` · Fall `vergleich` | Fall wird aus der Altdatei entfernt; `waitForTimeout(1_200)` entfällt; zusätzlich „überlebt Neuladen" |
| `trip-hub-kopf-region-aktivitaet.spec.ts` · AC-11, Versand-Anhang (Uhrzeit 05:00 → PUT ok → Chip `idle`, genau 1 Chip) | `hub-versand-autosave-chip.spec.ts` · Fall `route` | nur der Anhang entfällt; Region-Teil von AC-11 und die Genau-ein-Chip-Prüfung (AC-10) bleiben bis S2; Titel von AC-11 wird angepasst |
| `compare-versand-speichert-selbst.spec.ts` · AC-4, 5, 6 (412), 7, 11 | bleiben in der Altdatei | wandern in S3 (kind-Schleife); Gesten-Gate/F001-Re-Arm/500-Rollback/412-Retry werden erst in S2/S3 berührt und dort je einmal per Mutation rot gezeigt |

Es entfällt in S1 keine Zusicherung ersatzlos.

## Berührte Dateien

| Datei | Änderung |
|---|---|
| `frontend/e2e/helpers.ts` | MODIFY — Helfer |
| `frontend/e2e/hub-versand-autosave-chip.spec.ts` | CREATE |
| `frontend/e2e/hub-cross-user-write-block.spec.ts` | CREATE (ersetzt Umbenennung) |
| `frontend/e2e/compare-cross-user-write-block.spec.ts` | DELETE |
| `frontend/e2e/compare-versand-speichert-selbst.spec.ts` | MODIFY — AC-1 entfernen, Kopfkommentar |
| `frontend/e2e/trip-hub-kopf-region-aktivitaet.spec.ts` | MODIFY — Versand-Anhang aus AC-11 |
| `frontend/e2e/passkey-angebot.spec.ts` | MODIFY — Kommentar-Verweis |
| `.github/ci_e2e_specs.txt` | MODIFY |
| `.github/workflows/ci.yml` | MODIFY — `E2E_MIN_SPECS`, `E2E_MIN_EXECUTED_HAUPT` |
| `tests/unit/test_e2e_positivliste_ratschen_bindung.py` | MODIFY — `MANDANTEN_SPECS` |
| `tests/unit/test_e2e_compare_paritaet_waechter.py` | CREATE |
| `docs/reference/gates_und_ratschen.md` | MODIFY — Wächter-Abschnitt, Prüfdatum 2027-01-24 |

## Testplan

1. RED: Wächter-Test mit leerer `ALTLAST` gegen den Baum (rot, listet alle Verstöße) → `ALTLAST` aus dieser Messung füllen → grün; Selbsttests der Mutationen aus AC-3.
2. RED: beide neuen Specs gegen den CI-Stack (`frontend/e2e/ci-stack.sh`) — Zielverbund; Mutationen aus AC-1/AC-2 per String-Ersetzung mit externer Sicherungskopie (nie `git checkout/stash/reset`), pro kind getrennt.
3. `npx playwright test --list` über die Hauptlauf-Auswahl → `E2E_MIN_EXECUTED_HAUPT`; `grep -c '^e2e/' .github/ci_e2e_specs.txt` → `E2E_MIN_SPECS`.
4. `uv run pytest tests/unit/test_e2e_positivliste_ratschen_bindung.py tests/unit/test_e2e_compare_paritaet_waechter.py` (benannte Dateien).
5. Filter B: 3× Hauptlauf im Zielverbund grün; Filter A: `grep -c "waitForTimeout\|\.skip(" ` der angefassten Dateien = 0.

## Risiken

- **Login-/Registrierungs-Kontingent:** Registrierung 5/h je IP, Login 30/h. AC-2 verbraucht nicht mehr als die ersetzte Spec; die neue AC-1-Spec nutzt nur die Admin-Sitzung. Kein weiterer Zweitnutzer in S1.
- **Reihenfolge der Dateien im Hauptlauf:** `bug-703` läuft im eigenen Nachlauf; `hub-*` sortiert alphabetisch vor `trip-*`. Die Anzahl der Logins bleibt gleich, daher kein neues 429-Risiko — im Zielverbund zu belegen (Filter B).
- **Feldpfad der Uhrzeit im Trip-Stand** (`report_config.morning_time` vs. Vergleich `morning_time`; Format `HH:MM:SS`): im RED gegen den echten GET prüfen; Vergleich mit `startsWith('08:00')` statt Gleichheit.
- **Wächter zu eng/zu weit:** Regel 2 ist bewusst auf `compare-detail-tab` ohne Trip-Gegenstück beschränkt (Befund 7); false negatives (Spec steuert den Hub nur über `/compare/<id>`-URL) sind in S4 über die Altlast-Räumung zu prüfen.
- **Merge-Konflikt mit #2243** an `ci_e2e_specs.txt`: nicht parallel bearbeiten.
- **Zusicherungsverlust:** durch Zuordnungstabelle und Fallzahl-Prüfung (6 → 5) abgesichert.

## Out of Scope (bleibt in #2347, folgt in S2–S4)

Alle Dateien der Gruppen (b) und (c) außer den oben genannten; `compare-editor-autosave` (7× `waitForTimeout`), `compare-hub-save-chip`, Alarme/Radar/Wertebereiche/Wetter-Metriken-Specs, Hub-Kopf/Navigation, Mobil-Specs, `compare-editor-slice3`; Befüllen der Köpfe `gz-eigenstaendig:` an Gruppe (a)/(c); Leeren der Altlastliste. Nicht Teil von #2347: nicht gelistete Leichen (#2243). Produktcode wird nicht geändert.

## Known Limitations

- Der Wächter erkennt „kind-Schleife" an Textmustern (`HUB_KINDS`, Altmuster mit `'Trip','Vergleich'`); er beweist nicht, dass die Schleife fachlich beide kinds prüft. Das bleibt Adversary-/Review-Punkt („hätte das ein geteilter Baustein sein müssen?").
- `gz-eigenstaendig:` in E2E wird von keinem Hook erzwungen (`pendant_gate` ignoriert `.spec.ts`); der Wächter schließt diese Lücke nur für `compare`-Specs.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Testschicht-Umbau und Ratsche, keine Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth, Editor-Paradigma) betroffen; setzt die bestehende Teilungs-Invariante (Trip/Ortsvergleich, CLAUDE.md) in der E2E-Schicht durch.

## Changelog

- 2026-10-26: Erstfassung S1 (Entwurf).
