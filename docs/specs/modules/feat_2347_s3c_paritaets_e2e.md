---
entity_id: feat_2347_s3c_paritaets_e2e
type: feature
created: 2026-10-28
updated: 2026-10-28
status: draft
version: "1.0"
workflow: feat-2347-s3c-paritaets-e2e
tags: [epic-2345, etappe-p6, ratsche, e2e, playwright, trip-compare-teilung, konfliktschutz, zwei-kontexte]
---

# Paritäts-E2E, Scheibe S3c: Konfliktschutz über zwei Kontexte (#2347)

## Approval

- [ ] Approved

## Purpose

S1, S2, S3a und S3b sind live (ALTLAST 48 → 30). S3c räumt die Altlast `compare-konfliktschutz-zwei-kontexte.spec.ts` (394 Zeilen, nur Ortsvergleich, aus #2375/#2381). Sie ist das Regressionsnetz gegen den stillen Datenverlust „zwei Fenster desselben Nutzers überschreiben sich" (Lehre #2381: gültiges If-Match plus veralteter Körper ergibt 200 OK und segnet den Verlust ab). Das Trip-Pendant ist Produkt seit #1433 (Teilfeld-Nutzlasten, Konflikt-Sperre, `meldeKonflikt`), aber bisher nur durch einen einzelnen Staging-Fall (`feat-1395-s4-conflict-retry.staging.spec.ts`) und Kerntests gemessen, nie im CI-Stack über zwei Browser-Kontexte.

Die kind-neutralen Fälle (Reiter-Teilfelder, #2381 im selben Tab, Pausieren im Hub, Pausieren auf der Listenseite) werden zu **einer geteilten Spec** `hub-konfliktschutz-zwei-kontexte.spec.ts` mit `for (const kind of HUB_KINDS)`. Der Fall „Orte" ist eine der drei erlaubten Compare-Eigenheiten und bleibt in einer eigenen Datei mit `gz-eigenstaendig:`-Kopf. **Keine Zusicherung darf verloren gehen oder abgeschwächt werden**; rote Trip-Fälle sind eine Produktlücke und werden im selben Ticket behoben (AC-10).

## Source

- **File:** neue Specs `frontend/e2e/hub-konfliktschutz-zwei-kontexte.spec.ts` (KS) und `frontend/e2e/compare-orte-konfliktschutz-zwei-kontexte.spec.ts` (KO, `gz-eigenstaendig:`); gelöscht `frontend/e2e/compare-konfliktschutz-zwei-kontexte.spec.ts`; Wächter `tests/unit/test_e2e_compare_paritaet_waechter.py`; Ratsche `.github/ci_e2e_specs.txt`, `.github/workflows/ci.yml`; optional `frontend/e2e/helpers.ts` (Hilfsfunktion `hubZweiterKontext`, ohne Assertions)
- **Identifier:** `HUB_KINDS`, `HUB_SEL`, `seedHub`, `openHub`, `hubApiPath` (`helpers.ts:597-724`) · `ALTLAST`, `ALTLAST_MAX` · `E2E_MIN_SPECS`, `E2E_MIN_EXECUTED_HAUPT`
- **Produktcode:** keiner geplant (Regel für Trip-Rotfälle: AC-10).

**Schicht und Querschnitts-Prüfpunkte:**
- **Schicht:** ausschließlich Testschicht. Kein Code in `frontend/src/`, `internal/`, `cmd/`, `api/`, `src/` — außer AC-10.
- **Trip/Ortsvergleich-Teilung:** Kern der Spec. Compare-eigene Zweige nur dort, wo das Produkt für den Trip keine Entsprechung hat (Tabelle „Kind-Kontraste"); wo der Trip dasselbe in anderer Form hat (Pausieren), prüft jeder Zweig **seine eigene** Zusicherung, keiner wird übersprungen (Muster WW-4 aus S3a).
- **Mandantentrennung:** keine neuen Endpunkte. Der Zweit-Kontext ist ein neuer Browser-Kontext mit **demselben** `storageState` (derselbe Nutzer, zweites Fenster; kein zweiter Login, keine Registrierung, Bremse 5/h/IP unberührt). Es werden keine Nutzerdaten über Nutzergrenzen bewegt; die Zwei-Nutzer-Abdeckung bleibt in `hub-cross-user-write-block` und `hub-editor-autosave-user-isolation` unverändert.
- **Kanäle:** nicht betroffen, es wird nichts versendet.

## Gesamtschnitt #2347 (Stand)

| Scheibe | Inhalt | Status |
|---|---|---|
| S1–S3a | Helfer, Reiterleiste, Kopf, Listen-Menü, Alarme, Wertebereiche, Wetter-Metriken (48 → 34) | live |
| S3b | Versand-Gruppe (34 → 30) | live (c3c7fcc) |
| **S3c (diese Spec)** | **Konflikt-412 über zwei Kontexte** (`compare-konfliktschutz-zwei-kontexte`); ALTLAST 30 → 29 | diese Spec |
| S3d | compare-eigener Rest (Radar, Stundenverlauf, Hourly-Order, 682-Mobile, `compare-hub-inline-edit`, `compare-editor-autosave`, **alle `.staging`-Specs inkl. `feat-1395-s4-conflict-retry.staging.spec.ts`**) | folgt |
| S4 | Gruppe ohne Trip-Pendant, #2243-Leichen, ALTLAST leer | folgt |

`feat-1395-s4-conflict-retry.staging.spec.ts` (+ `.setup.ts`) ist `.staging`, steht nicht in der Positivliste und gehört zu S3d; sie wird in S3c weder gelöscht noch verändert. Ihre Zusicherung (Trip-412-Retry) wird hier **zusätzlich** im CI-Stack gemessen (KS-1), nicht ersetzt. Ticket und Epic bleiben offen bis S4; Scheiben werden strikt nacheinander gemergt.

## Entscheidungen zu den offenen Fragen aus der Analyse

Alle am Code beantwortet; keine Rückfrage an den PO.

1. **Orte-Fall (Alt Test 9 Orte):** bleibt compare-eigen, eigene Datei `compare-orte-konfliktschutz-zwei-kontexte.spec.ts` mit `gz-eigenstaendig:`-Kopf (erste 30 Zeilen, ≥ 15 Zeichen Begründung: Orte-Tab ist eine der drei erlaubten Compare-Eigenheiten; sein Trip-Gegenstück „Etappen" hat andere Gesten und Felder, kein `location_ids`-Teilfeld). Der Dateiname enthält „compare", die Datei braucht also Kopf oder Schleife (Regel 1) — sie hat den Kopf.
2. **Wächter-Zahl:** `ALTLAST` verliert `compare-konfliktschutz-zwei-kontexte.spec.ts`; weder die neue geteilte Datei (trägt `HUB_KINDS`) noch die Orte-Datei (trägt Kopf) gehört in `ALTLAST` — der Wächter meldet einen konformen Eintrag als „inzwischen konform" (`test_konformer_altlast_eintrag_ist_rot`). Damit **30 → 29**, `ALTLAST_MAX` Literal 29 im selben Zug. Gegenprobe am Ist-Stand in /50: `len(ALTLAST) == ALTLAST_MAX`.
3. **Ratsche:** Die Altspec steht auf der Positivliste (`ci_e2e_specs.txt:420`, Aufnahme-Kommentar `:293-300`). Sie wird durch **zwei** Zeilen ersetzt (hub-Spec und Orte-Datei, die Orte-Zusicherung darf nicht aus der CI-Ampel fallen): `E2E_MIN_SPECS` 71 → **72** (= `grep -c '^e2e/'`). `E2E_MIN_EXECUTED_HAUPT` wird am Endstand per `npx playwright test --list` über die Hauptlauf-Auswahl **gemessen**; die Rechnung 528 − 8 + 14 + 1 = 535 ist nur Erwartung, verbindlich ist die Messung (im /50 zu messen).
4. **Trip-Pausieren (Alt 11a):** Der Trip pausiert per `PATCH /api/trips/{id}/state` `{paused}` **ohne If-Match** (`setPaused('trip', …)`, `subscriptionExec.ts:61-68`; die Trip-Seite flusht zuvor `tripSaveCtl`, `trips/[id]/+page.svelte:181-187`) — dort kann kein 412 entstehen, das ist Entwurf (Trip-Spec #1433, S2 AC-15). Der Ortsvergleich-Hub pausiert per PUT `{schedule, previous_schedule}` **mit** If-Match ⇒ 412. KS-3 prüft deshalb je kind die **eigene** Zusicherung (siehe Tabelle); die gemeinsame Kernaussage „Name von A bleibt, Status ist gesetzt, der Status-Körper trägt nur den Status" gilt für beide.
5. **Listenseite (Alt 11b):** Die Alt-Spec nennt den Pfad „roher fetch ohne If-Match". Am Code: `/compare` ruft `setPaused('vergleich', …)` (`compare/+page.svelte:134`): frischer GET, dann PUT `{schedule, previous_schedule}` ohne If-Match; `/trips` ruft `setPaused('trip', …)` (`trips/+page.svelte:118`): PATCH `/state` `{paused}`. Beide Listen schreiben also bewusst unbedingt, aber mit Status-Teilkörper; die Zusicherung „Name von A bleibt" ist je kind belegbar. Es gibt ein echtes Trip-Pendant, kein Compare-Eigenfall.

## Kind-Kontraste (compare-eigen vs. gemeinsam)

Selektoren aus `HUB_SEL`, `hub-alarme-/-wertebereiche-/-wetter-metriken-/-versand-speichert-selbst` (dort je kind belegt), in /50 im RED gegen den gerenderten Hub gemessen.

| Fall | route (Trip) | vergleich | Begründung |
|---|---|---|---|
| Reiter-Schreibweg | PUT `/api/trips/{id}` mit Teilfeld (Alarme `official_warnings`, Wertebereiche `corridors`, Versand `report_config`); Wetter-Metriken zusätzlich PUT `…/weather-config` (`display_config.metrics`) | PUT `/api/compare/presets/{id}` mit Teilfeldern (`radar_alert_enabled`, `corridors`+`display_config`, `morning_time`, `official_alerts_enabled`) | `zaehlePuts` zählt je kind den passenden Pfad; Zusicherung gleich (If-Match im ersten PUT, 412, Retry, Name von A bleibt) |
| Auslöser Alarme | `alerts-tab-official-alert-triggers-toggle` (Seed `official_warnings.enabled=true` ⇒ Klick ⇒ `false`) | `alarme-radar-toggle` (Seed `false` ⇒ `true`) | der Trip hat keinen Radar-Alarm; derselbe `AlarmeTab` |
| Auslöser Wertebereiche | `corridor-editor-route`, Seed `wind_gust` [30,70], Pool-Eintrag `precipitation_sum` ⇒ 2 Korridore | `corridor-editor-vergleich`, Seed `snow_depth_cm`, erster Pool-Eintrag ⇒ 2 Korridore | gleicher geteilter Editor, andere Metrik-Namen |
| Auslöser Versand | `versand-abschnitt` · `report-morning-time` 06:00 ⇒ 08:00; Stand `report_config.morning_time` beginnt mit `08:00` | gleiche Auswahl; Stand `morning_time === '08:00:00'` | Trip führt die Uhrzeit in `report_config`, trägt ein abgeleitetes Flachfeld |
| Auslöser Wetter-Metriken | `weather-metrics-tab`, Knopf „Schneehöhe" in `wm2-grundauswahl` (Zielwert aus `MS_SEL.route` in S3a); Stand `display_config.metrics[snow_depth].enabled` | `weather-metrics-tab-vergleich`, `report-show-official-alerts` ⇒ `official_alerts_enabled === false` | Wetter-Metriken-Reiter hat je kind eigene Schalter (S3a MS) |
| Pausieren im Hub | PATCH `/state` `{paused}`, **kein** If-Match, **kein** 412, Chip bleibt nicht `conflict`; Stand `paused_at` gesetzt | PUT `{schedule, previous_schedule}` mit If-Match ⇒ 412 ⇒ „Nochmal speichern" ⇒ Retry 200; Stand `schedule === 'manual'` | Übertragungsweg unterscheidet sich (Entscheidung 4) |
| Pausieren Liste | `trips`-Seite: `trip-row-<id>` · `trip-row-menu-btn`, PATCH `{paused:true}` | `compare`-Seite: `compare-tile-<id>` · `compare-row-kebab`, PUT `{schedule:'manual', previous_schedule:'daily'}` | Listenseiten rufen `setPaused(kind, …)`, Körper je kind (Entscheidung 5) |
| Kopf-Umbenennen in A | `trip-name-edit-toggle`/`-name-edit`/`-name-save`, PUT-Körper `{name}` | `compare-hub-name-edit-toggle`/`-name-edit`/`-name-save`, PUT-Körper `{name}` | `HUB_SEL[kind].kopf`; KB-4 (`hub-kopf-bearbeiten`) sichert `{name}` bereits je kind |
| Orte entfernen | – (Trip-Pendant „Etappen" hat andere Gesten, kein `location_ids`) | `hub-orte-row`/`hub-orte-remove`, PUT-Körper `{location_ids}` | **echtes Compare-Eigen**: Orte-Tab (`gz-eigenstaendig:`), Datei KO |

## Befunde (am Code gemessen, 2026-10-28)

1. Die Alt-Spec hat **8 Fälle**: Test 9 je Reiter ×4 (Alarme, Wertebereiche, Versand, Wetter-Metriken) + Test 9 Orte + Test 10 + Test 11a + Test 11b. Sie legt Vergleiche mit eigener `legeVergleichAn` an (viele Seed-Felder), Neu: `seedHub(request, kind, { extra })` mit denselben Feldern (`extra` überlagert flach, `display_config` wird ersetzt).
2. **Zwei Seed-Anforderungen je kind:** Test 9 braucht einen ersten PUT von B mit `If-Match` aus dem Seitenaufbau; B muss den Hub **vor** As Umbenennung laden und seinen Reiter bereit haben. Der Trip hat denselben Seitenaufbau-ETag (`adoptEtagFromPageLoad`, #1433), das ist die zu messende Zusicherung.
3. `hubApiPath('route')` = `/api/trips/{id}`; der Trip-Fremdschreiber in S3b VS-2 (`PUT … ohne If-Match`) funktioniert im CI-Stack und ist das Vorbild für den Trip-Zweig.
4. Verweis-Hygiene: Der alte Dateiname steht in `test_e2e_compare_paritaet_waechter.py`, `ci.yml:285`, `ci_e2e_specs.txt:293-300, 420`, `docs/specs/bugfix/compare_konfliktschutz_teilfelder.md` und in älteren `docs/specs`/`docs/context` (Historie). Code-/CI-Verweise werden umgehängt (Zeiger umhängen, Kommentar fortschreiben, nicht löschen); Historie in `docs/` bleibt.
5. Quota: ein Vergleich je Fall (max. 2 aktive pro Nutzer, 409); jeder Fall räumt im `finally` per `seedHub().aufraeumen()`; zusätzlich schließt `afterEach` alle Zweit-Kontexte.

## Estimated Scope

- **LoC (Testcode, netto):** ca. +430 (KS ≈ 370, KO ≈ 60) / −394 (Altdatei). Ob Testdateien ins LoC-Limit 250 zählen, liefert `workflow.py status`; zählen sie, `loc_limit_override` auf 500.
- **Files:** 7 (2 neu, 1 gelöscht, Wächter, Ratsche, `ci.yml`, ggf. `helpers.ts`), plus Doku-Zeiger (`compare_konfliktschutz_teilfelder.md`, `gates_und_ratschen.md`).
- **Effort:** high (Trip-Fälle erstmals gemessen, Zwei-Kontexte-Aufbau, Mutations-Gegenprobe je kind). **Risiko:** MEDIUM — (1) Trip-Fälle können rot sein (AC-10), (2) Verfälschungen wirken nur im Zwei-Kontexte-Aufbau, (3) `ci_e2e_specs.txt` ist Konfliktpunkt: vor Commit `git merge --ff-only origin/main` bzw. Rebase prüfen.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `frontend/e2e/helpers.ts` (`HUB_KINDS`, `HUB_SEL`, `seedHub`, `openHub`, `hubApiPath`) | module | Basis |
| `hub-versand-speichert-selbst.spec.ts` (VS-2), `hub-alarme-speichert-selbst.spec.ts` (AS), `hub-wertebereiche-speichert-selbst.spec.ts` (WS), `hub-wetter-metriken-speichert-selbst.spec.ts` (MS), `hub-kopf-bearbeiten.spec.ts` (KB), `hub-list-menu.spec.ts` (LM) | module | Vorbilder und Selektor-/Feldpfad-Quellen je kind |
| `saveStatusStore.svelte.ts` (`retryConflict`), `etagRegistry.ts` (`markiereKonflikt`), `api.ts` (If-Match, 412), `pickEigenfelder.ts`, `tripSpeicherung.ts`, `CompareTabs.svelte`, `TripTabs.svelte`, `subscriptionExec.ts` | module | geprüfte Bausteine (unverändert, außer AC-10) |
| `docs/specs/bugfix/compare_konfliktschutz_teilfelder.md`, `docs/specs/bugfix/trip_mehrreiter_konfliktschutz.md` | Spec | Ursprungs-ACs |
| `.github/ci_e2e_specs.txt`, `ci.yml` (Job `e2e`), `e2e_gate.py`, `tests/unit/test_e2e_positivliste_ratschen_bindung.py` | CI | Positivliste, `E2E_MIN_SPECS`, `E2E_MIN_EXECUTED_HAUPT` |
| `tests/unit/test_e2e_compare_paritaet_waechter.py` | test | `ALTLAST`, `ALTLAST_MAX` |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/e2e/hub-konfliktschutz-zwei-kontexte.spec.ts` | CREATE | KS-1 (Reiter-Teilfelder ×4 je kind), KS-2 (#2381), KS-3 (Pausieren Hub), KS-4 (Pausieren Liste) |
| `frontend/e2e/compare-orte-konfliktschutz-zwei-kontexte.spec.ts` | CREATE | KO-1 (Orte), `gz-eigenstaendig:`-Kopf |
| `frontend/e2e/compare-konfliktschutz-zwei-kontexte.spec.ts` | DELETE | erst nach grünem Lauf und 1:1-Abgleich |
| `frontend/e2e/helpers.ts` | MODIFY (optional) | `hubZweiterKontext(browser, baseURL, storageState)`: Kontext mit gleichem `storageState`, `serviceWorkers: 'block'`, Viewport 1280×900; keine Assertions |
| `.github/ci_e2e_specs.txt` | MODIFY | Altzeile raus, zwei Zeilen rein (alphabetisch); Aufnahme-Kommentar `:293-300` umhängen (Filter-A/B/C-Ergebnis) |
| `.github/workflows/ci.yml` | MODIFY | `E2E_MIN_SPECS` 72, `E2E_MIN_EXECUTED_HAUPT` gemessen, Begründung fortgeschrieben |
| `tests/unit/test_e2e_compare_paritaet_waechter.py` | MODIFY | Eintrag raus, `ALTLAST_MAX` 30 → 29, Docstring-Messzeile |
| `docs/reference/gates_und_ratschen.md`, `docs/specs/bugfix/compare_konfliktschutz_teilfelder.md` | MODIFY | Zahl „S3c: 29", Verweis auf neue Dateien |

## Implementation Details

Jeder Fall läuft als `for (const kind of HUB_KINDS) test(\`KS-n (${kind}): …\`)`. Setup `seedHub(request, kind, { extra })`; Kontext B per `hubZweiterKontext`, B lädt **zuerst** (`openHub(b, kind, id, { tab })`, Reiter „bereit"), danach öffnet A den Hub und benennt um (Kopf-PUT `{name}`, `expect.poll` auf Status 200); dann ändert B. Warten nur `expect.poll`, `toHaveAttribute`, `toHaveCount`, `toBeVisible` — kein `waitForTimeout`, kein `skip`, kein UI-`login()`, kein fester `storageState`-Pfad. Erwartungswerte (Name von A, Seed-Werte, Zielwerte) stehen im Test fest, nie aus dem gerenderten Produkt gelesen. `finally`: `hub.aufraeumen()`; `afterEach`: Zweit-Kontexte schließen.

### Fälle

**`hub-konfliktschutz-zwei-kontexte.spec.ts` (KS)**
- **KS-1 (je kind × Reiter Alarme, Wertebereiche, Versand, Wetter-Metriken = 8 Fälle)** (Alt Test 9): B lädt den Reiter, A benennt um, B ändert ⇒ Chip `conflict`; Vorbedingung genau ein PUT von B auf den kind-Pfad (Wetter-Metriken Trip: Pfad `…/weather-config` zusätzlich gezählt); erster PUT trägt `If-Match` (nicht leer) und wird mit **412** beantwortet; „Nochmal speichern" ⇒ Chip `idle`, Wiederholungs-PUT 200, Schlüsselmenge des Wiederholungs-Körpers enthält **nicht** `name`; Server-Stand: `name === nameA` **und** Reiter-Änderung von B (je Reiter und kind laut Kontrast-Tabelle, Fehlertext „… von B fehlt auf dem Server").
- **KS-2 (je kind)** (Alt Test 10, #2381): im selben Tab Alarme-Wert ändern ⇒ Chip `idle`, Stand trägt den Wert (`expect.poll`); danach Kopf-Umbenennen ⇒ Kopf-PUT-Körper `toEqual({ name })`; Stand trägt Name **und** den Alarme-Wert (Fehlertext „Kopf-Edit hat den Alarm-Wert zurückgeschrieben (#2381)").
- **KS-3 (je kind)** (Alt Test 11a): B lädt den Hub, A benennt um, B pausiert über „Weitere Aktionen" → „Pausieren". *vergleich:* erster PUT mit If-Match ⇒ 412, Chip `conflict`, „Nochmal speichern" ⇒ `idle`, Wiederholungs-PUT 200 mit **genau** den Schlüsseln `['previous_schedule','schedule']`, Stand `schedule === 'manual'`, `name === nameA`. *route:* der Status-Abruf ist `PATCH …/state` mit Körper **genau** `{paused:true}`, Antwort 200, **kein** If-Match, Chip bleibt nicht `conflict`, es geht **kein** PUT auf `/api/trips/{id}` von B aus; Stand `paused_at` gesetzt, `name === nameA`, `stages.length === 1` (kein Datenverlust). Beide Zweige sind eigene Zusicherungen, kein Zweig überspringt etwas.
- **KS-4 (je kind)** (Alt Test 11b): B öffnet die Listenseite (`HUB_SEL[kind].liste.url`), A benennt um, B pausiert im Zeilenmenü ⇒ der Status-Abruf trägt nur den Status (*vergleich:* PUT `toEqual({schedule:'manual', previous_schedule:'daily'})`; *route:* PATCH `toEqual({paused:true})`), Antwort 200; Stand pausiert, `name === nameA`.

**`compare-orte-konfliktschutz-zwei-kontexte.spec.ts` (KO)**
- **KO-1 (vergleich)** (Alt Test 9 Orte): B öffnet `?tab=orte` (2 `hub-orte-row`), A benennt um, B entfernt `e2e-loc-stubai` ⇒ erster PUT mit If-Match, 412, Chip `conflict`, Ortsliste von B bleibt stehen (1 Zeile, kein Rollback); „Nochmal speichern" ⇒ `idle`, Wiederholungs-PUT 200, Körper `toEqual({ location_ids: ['e2e-loc-innsbruck'] })`; Stand `name === nameA`, `location_ids === ['e2e-loc-innsbruck']`.

### Wächter, Ratsche, CI

- **Wächter:** Eintrag `compare-konfliktschutz-zwei-kontexte.spec.ts` streichen, `ALTLAST_MAX` = **29**, Docstring-Messzeile um S3c ergänzen, Prüfdatum 2027-01-24 unverändert.
- **Ratsche:** `e2e/compare-konfliktschutz-zwei-kontexte.spec.ts` raus; `e2e/compare-orte-konfliktschutz-zwei-kontexte.spec.ts` und `e2e/hub-konfliktschutz-zwei-kontexte.spec.ts` rein; `E2E_MIN_SPECS` 72; `E2E_MIN_EXECUTED_HAUPT` per `--list` am Endstand messen (im /50 zu messen); Aufnahme-Kommentar „Aufnahme 2026-09-29 (#2375)" auf die neuen Namen umhängen und #2347 S3c vermerken.
- **Verweis-Hygiene:** `grep -rn "compare-konfliktschutz-zwei-kontexte"` über `frontend`, `.github`, `tests`, `docs/specs/bugfix`: kein Treffer außer Historie.

### Reihenfolge in /50
1. Neue Specs schreiben; Trip-Fälle im CI-Stack messen (rot ⇒ Produktlücke, AC-10).
2. Dreimal grün (Filter B), Fallzahl `--list`: KS 14 + KO 1 ≥ 8 Altfälle (je kind abgedeckt).
3. Mutations-Gegenprobe je kind (Sicherungskopie extern, nur String-Ersetzung, nie `git checkout/stash/reset`).
4. Erst bei Grün Altdatei löschen; Wächter, Ratsche, `ci.yml`, Doku-Zeiger.

## Zuordnung alt → neu (Regressionsnetz)

| Alt (`compare-konfliktschutz-zwei-kontexte`) | Neu | Anmerkung |
|---|---|---|
| Test 9 Alarme | KS-1 Alarme (vergleich) + KS-1 Alarme (route) | Trip: Amtliche-Warnungen-Auslöser |
| Test 9 Wertebereiche | KS-1 Wertebereiche je kind | |
| Test 9 Versand | KS-1 Versand je kind | seit #1743 Abschnitt im Reiter Wetter-Metriken (`versand-abschnitt`) |
| Test 9 Wetter-Metriken | KS-1 Wetter-Metriken je kind | Trip nutzt zusätzlich `weather-config`-Pfad |
| Test 9 Orte | KO-1 | compare-eigen, `gz-eigenstaendig:` |
| Test 10 (#2381) | KS-2 je kind | Kopf-PUT `{name}` |
| Test 11a Pausieren im Hub | KS-3 vergleich (412-Retry, Status-Schlüssel) + KS-3 route (PATCH ohne If-Match) | je kind eigene Zusicherung |
| Test 11b Pausieren Liste | KS-4 je kind | |
| Alt-Zusicherung „Wiederholungs-PUT trägt `name` nicht" | KS-1/KS-3 (vergleich) und KS-1 (route) | nichts abgeschwächt |

## Expected Behavior

- **Input:** CI-Lauf `e2e` gegen den isolierten Stack; Unit-Lauf des Wächters.
- **Output:** Der Konfliktschutz („fremde Änderung überlebt, Änderung von B fehlt nicht") wird für Trip und Ortsvergleich durch dieselbe Spec geprüft; die CI bewacht ihn.
- **Side effects:** Wegwerf-Daten `E2E-GZ-…` (Aufräumen im `finally`, Sicherheitsnetz `global.teardown.ts`); keine Registrierung, kein Versand.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN zwei Kontexte desselben Nutzers auf Trip bzw. Ortsvergleich WHEN A umbenennt und B danach je Reiter ändert THEN 412 mit If-Match, nach „Nochmal speichern" stehen Name von A und Änderung von B auf dem Server (KS-1).
- [ ] Test 2: GIVEN ein Hub WHEN im selben Tab erst ein Reiter-Wert, dann der Name gespeichert wird THEN stehen beide auf dem Server, Kopf-PUT = `{name}` (KS-2).
- [ ] Test 3: GIVEN veralteter Stand in B WHEN B pausiert (Hub bzw. Liste) THEN gilt je kind seine eigene Zusicherung, Name von A bleibt (KS-3, KS-4).
- [ ] Test 4: GIVEN der Wächter WHEN er läuft THEN `ALTLAST` hat 29 Einträge, `ALTLAST_MAX` ist 29.
- [ ] Test 5: GIVEN die Positivliste WHEN der Bindungstest läuft THEN entspricht `E2E_MIN_SPECS` (72) der Listenlänge.

## Acceptance Criteria

- **AC-1:** Given ein Wegwerf-Trip und ein Wegwerf-Ortsvergleich, je im Hub in zwei Browser-Kontexten desselben Nutzers geöffnet, und B hat den Reiter vor As Umbenennung geladen / When A den Namen ändert und B danach im Reiter Alarme, Wertebereiche, Versand (Abschnitt in Wetter-Metriken) oder Wetter-Metriken speichert / Then sendet B einen ersten Speicher-Aufruf mit If-Match aus dem Seitenaufbau, der Server antwortet 412, der Chip zeigt „Nochmal speichern", der Wiederholungs-Aufruf (200) trägt kein `name`, und nach dem Neuladen stehen der Name von A **und** die Änderung von B im Server-Stand — für Trip UND Ortsvergleich, je Reiter mit dem kind-eigenen Schreibweg und Feld (Tabelle „Kind-Kontraste").
  - Test: `hub-konfliktschutz-zwei-kontexte.spec.ts` (KS-1, 8 Fälle).
  - Mutation (je kind getrennt): Reiter-Nutzlast als Vollobjekt mit stalem `name` senden → KS-1 des kind rot (Wiederholungs-Körper trägt `name`, Name von A verloren); If-Match im Reiter-Schreibweg weglassen → KS-1 des kind rot (kein 412); 412 im Reiter auf generischen Fehler umstellen (`meldeKonflikt` nicht aufrufen) → KS-1 des kind rot (Chip `conflict` fehlt); „Nochmal speichern" holt keinen frischen Stempel → Wiederholung bleibt 412 → rot.
- **AC-2:** Given ein Hub (Trip bzw. Ortsvergleich) in einem einzigen Tab / When der Nutzer zuerst einen Reiter-Wert (Alarme) speichert und danach im Kopf den Namen ändert / Then enthält der Kopf-Aufruf genau `{ name }`, und der Server-Stand trägt den neuen Namen **und** den zuvor gespeicherten Reiter-Wert (kein Zurückschreiben, #2381) — für Trip UND Ortsvergleich.
  - Test: `hub-konfliktschutz-zwei-kontexte.spec.ts` (KS-2, 2 Fälle).
  - Mutation: Kopf-Edit sendet Vollobjekt aus alter Baseline → KS-2 des kind rot (Körper ≠ `{name}`, Wert zurückgeschrieben).
- **AC-3:** Given zwei Kontexte, B mit veraltetem Stand / When A umbenennt und B im Hub „Pausieren" wählt / Then gilt für den **Ortsvergleich**: erster Aufruf mit If-Match ⇒ 412 ⇒ „Nochmal speichern" ⇒ Wiederholung 200 mit genau den Schlüsseln `previous_schedule` und `schedule`, Stand `manual`, Name von A bleibt; für den **Trip**: der Status-Abruf ist ein PATCH `…/state` mit genau `{paused:true}` ohne If-Match (kein 412, kein PUT auf den Trip aus B), Stand pausiert, Name von A bleibt, Etappen unverändert. Jeder Zweig prüft seine eigene Zusicherung (Übertragungsweg je kind, Entscheidung 4); der Zweig wird nicht übersprungen.
  - Test: `hub-konfliktschutz-zwei-kontexte.spec.ts` (KS-3, 2 Fälle).
  - Mutation: Ortsvergleich-Status-Körper als Spread der stalen Baseline → nur KS-3 (vergleich) rot; If-Match im Status-Pfad weglassen → nur KS-3 (vergleich) rot (kein 412); Trip-`setPaused` als PUT des stalen Trips senden → nur KS-3 (route) rot (Name von A überschrieben, PUT von B).
- **AC-4:** Given zwei Kontexte, B steht auf der Listenseite (`/trips` bzw. `/compare`) / When A umbenennt und B im Zeilenmenü „Pausieren" wählt / Then trägt der Status-Aufruf nur den Status (Ortsvergleich PUT `{schedule:'manual', previous_schedule:'daily'}`, Trip PATCH `{paused:true}`), der Server antwortet 200, der Stand ist pausiert und der Name von A bleibt — für Trip UND Ortsvergleich.
  - Test: `hub-konfliktschutz-zwei-kontexte.spec.ts` (KS-4, 2 Fälle).
  - Mutation: Listen-Pausieren sendet Vollobjekt (Name stale) → KS-4 des kind rot; `previous_schedule` aus dem Körper entfernen → KS-4 (vergleich) rot.
- **AC-5:** Given der Ortsvergleich-Hub mit zwei Orten in zwei Kontexten / When A umbenennt und B im Reiter Orte einen Ort entfernt / Then antwortet der Server 412 auf den ersten Aufruf mit If-Match, die Ortsliste von B bleibt stehen, nach „Nochmal speichern" trägt der Wiederholungs-Aufruf genau `{ location_ids: ['e2e-loc-innsbruck'] }`, und der Server-Stand trägt Name von A und die verkürzte Ortsliste. Die Datei hat den `gz-eigenstaendig:`-Kopf (Begründung: Orte-Tab ist eine der drei erlaubten Compare-Eigenheiten, das Trip-Pendant „Etappen" hat andere Gesten).
  - Test: `compare-orte-konfliktschutz-zwei-kontexte.spec.ts` (KO-1), Wächter-Test (Datei konform).
  - Mutation: Orte-PUT trägt Vollobjekt → KO-1 rot; Kopf entfernen → Wächter rot (Regel 1).
- **AC-6:** Given die zwei neuen Specs / When ein kind-Zweig (`if (kind === 'route'|'vergleich')`) in ihnen vorkommt / Then trägt er einen Begründungskommentar und steht in „Kind-Kontraste"; zulässig sind Reiter-Schreibweg/Auslöser, Pausier-Übertragungsweg und Orte-Datei; ein Zweig, der einen Fall nur für eine Art prüft, obwohl das Produkt ihn für beide kann, ist unzulässig.
  - Test: Adversary-Prüfpunkt, `grep -n "kind === " frontend/e2e/hub-konfliktschutz-zwei-kontexte.spec.ts` gegen die Tabelle.
  - Mutation: keine (Prozess); Finding bei Zweig ohne Kommentar oder Gegenstück.
- **AC-7:** Given der Paritäts-Wächter / When der Unit-Test läuft / Then enthält `ALTLAST` **29** Einträge (`compare-konfliktschutz-zwei-kontexte.spec.ts` entfernt; weder die hub-Datei noch die Orte-Datei stehen drin), `ALTLAST_MAX` ist das Literal **29**, und die Selbsttests bleiben grün.
  - Test: `tests/unit/test_e2e_compare_paritaet_waechter.py` (benannte Datei).
  - Mutation: Altnamen in `ALTLAST` stehen lassen → „zeigt auf keine Datei mehr" rot; `ALTLAST_MAX` auf 30 lassen → rot; Orte-Datei in `ALTLAST` aufnehmen → „inzwischen konform" rot.
- **AC-8:** Given die CI-Ampel / When die Ratsche geprüft wird / Then enthält `.github/ci_e2e_specs.txt` die zwei neuen Namen und nicht mehr `compare-konfliktschutz-zwei-kontexte`, `E2E_MIN_SPECS` entspricht exakt der Listenlänge (erwartet **72**), `E2E_MIN_EXECUTED_HAUPT` ist der am Endstand per `npx playwright test --list` gemessene Wert (im /50 zu messen) mit fortgeschriebener Begründung, jede Listenzeile verweist auf eine vorhandene Datei, und `grep -rn` auf den alten Namen findet nur Historie in `docs/`.
  - Test: `tests/unit/test_e2e_positivliste_ratschen_bindung.py`, CI-Job `e2e` (`e2e_gate.py`).
  - Mutation: Zeile auf nicht existierende Datei → Existenzprüfung rot; `E2E_MIN_SPECS` um 1 verfälschen → Kern-Test rot; `E2E_MIN_EXECUTED_HAUPT` um 1 verändern → `e2e_gate.py` rot.
- **AC-9:** Given die neuen Specs / When sie im Zielverbund (Hauptlauf ohne `bug-703`) dreimal hintereinander laufen / Then sind alle drei Läufe grün, die Specs enthalten kein `waitForTimeout`, kein `skip`/`test.fixme`, kein `page.screenshot({path})`, keinen Hauptrepo-Pfad, kein `__dirname`, keinen festen `storageState`-Pfad und kein UI-`login()`; der Zweit-Kontext nutzt denselben `storageState` (keine Registrierung); jeder Fall räumt Objekt und Zweit-Kontexte auf, kein Fall braucht mehr als einen aktiven Vergleich (kein 409), und `global.teardown.ts` meldet keinen Restbestand `E2E-GZ-`.
  - Test: Filter B (3 Zyklen) + `grep -c "waitForTimeout\|\.skip(\|test\.fixme\|__dirname" frontend/e2e/hub-konfliktschutz-zwei-kontexte.spec.ts frontend/e2e/compare-orte-konfliktschutz-zwei-kontexte.spec.ts` = 0.
  - Mutation: `waitForTimeout` einfügen → Filter-A-Prüfung rot; `finally`-Aufräumen entfernen → Folgefall scheitert mit 409.
- **AC-10:** Given ein Fall der neuen Specs wird für den Trip rot, obwohl er für den Ortsvergleich grün ist / When die Ursache untersucht wird / Then wird die Produktlücke im **selben Ticket** (#2347) behoben und der Test bleibt streng; Abschwächen, `test.skip`, ein kind-Zweig, der nur eine Art prüft, oder ein „bekannte Abweichung"-Vermerk sind unzulässig. Berührte Produktdateien werden in diese Spec nachgetragen und das LoC-Limit bei Bedarf per `loc_limit_override` angehoben. Erwartete Messpunkte für den Trip: Seitenaufbau-If-Match und 412 je Reiter (KS-1, insbesondere `…/weather-config`), Konflikt-Anzeige im Trip-Chip, Kopf-PUT `{name}` nach Reiter-Speichern (KS-2). Kein Messpunkt ist ein Trip-412 beim Pausieren (Entwurf, Entscheidung 4).
  - Test: Prozess-AC; Beleg im Adversary-Protokoll („rot beim Zusammenführen: ja/nein, wenn ja: Fix-Commit").
  - Mutation: keine (Regel).
- **AC-11:** Given jedes zusammengeführte Verhalten aus AC-1 bis AC-5 / When die Implementierung gezielt verfälscht wird (Sicherungskopie extern, nur String-Ersetzung, nie `git checkout/stash/reset`) / Then wird für **jedes** Verhalten und **beide** kinds der jeweils betroffene Fall rot, und protokolliert wird, **welcher** Test rot wurde; eine Verfälschung, die kein Test fängt, ist ein Finding; eine kind-spezifische Verfälschung macht nur den Fall dieser Art rot. Zusätzlich die Ausfallprobe der Zuordnung: ein weggelassener Fall wird von der Fallzahl-Prüfung (`--list`: KS 14 + KO 1 gegen 8 Altfälle, je kind) gemeldet, und die Altdatei wird erst nach grünem Lauf gelöscht.
  - Test: Adversary-Dialog in `/50` (Familien: Teilfeld-Nutzlast, If-Match, 412-Pfad, Status-Übertragungsweg, Kopf-Körper, Zähler, Selektor je kind).
  - Mutation: siehe die Mutationszeilen in AC-1 bis AC-5.

## Definition of Done

- [ ] AC-1 bis AC-11 per Test und Mutations-Gegenprobe belegt (je Mutation protokolliert, welcher Test rot wurde)
- [ ] Neue Specs laufen für beide kinds dreimal grün gegen den CI-Stack; Altdatei erst danach gelöscht
- [ ] Zuordnung gegen `--list` der Altdatei (8 Fälle) vollständig
- [ ] `E2E_MIN_EXECUTED_HAUPT` gemessen, `E2E_MIN_SPECS` (72) und Positivliste konsistent
- [ ] Wächter `ALTLAST`/`ALTLAST_MAX` auf 29, Wächter-Test grün
- [ ] CI-Ampel (6 Checks) grün, kein Produktcode geändert (oder Produktlücke nach AC-10 dokumentiert)

## Known Limitations

- Trip-Verhalten bei If-Match/412 je Reiter, besonders im Wetter-Metriken-Reiter (zweiter Schreibpfad `…/weather-config`), ist erst im RED messbar; die Spec legt die Zusicherung fest, nicht das Messergebnis.
- Der Trip hat beim Pausieren absichtlich keinen 412-Weg (PATCH `/state` ohne If-Match); der Schutz ist dort strukturell (Teilkörper `{paused}`). Würde das geändert, wäre KS-3 (route) anzupassen und das neu zu spezifizieren.
- Konfliktschutz für Trip-Etappen-Änderungen (Etappen-Editor) ist nicht Gegenstand dieser Scheibe (kein Alt-Fall, kein Compare-Pendant ohne Orte-Eigenheit).
- `E2E_MIN_EXECUTED_HAUPT` ist erst am Endstand messbar; die Rechnung 535 ist nur Erwartung.
- `feat-1395-s4-conflict-retry.staging.spec.ts` bleibt bis S3d unverändert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Testschicht-Konsolidierung nach bestehender Vorgabe (Trip/Ortsvergleich-Code-Teilung, Epic #2345 P6); keine neue Entscheidungsfläche.

## Changelog

- 2026-10-28: Initial spec created (S3c, Konflikt-412 über zwei Kontexte). Entscheidungen am Code: Orte-Fall bleibt compare-eigen in eigener Datei (`gz-eigenstaendig:`), Wächter 30 → 29 (beide Neu-Dateien konform, nicht in ALTLAST), `E2E_MIN_SPECS` 71 → 72; Trip pausiert per PATCH ohne If-Match (kein 412, eigene Zusicherung in KS-3); Listenseiten rufen beide `setPaused(kind, …)` (KS-4 je kind); `feat-1395-s4` bleibt bei S3d.
