# Adversary-Dialog #2277 S2c (`/compare/new?from=`)

Kontext: Workflow `feature-2277-s2c-compare-from-vorlage`, Spec `docs/specs/modules/feat_2277_s2c_compare_from_vorlage.md`. Geprüft wurde der uncommittete Stand (Produktiv: `compareNewVorlage.ts`, `+page.server.ts`, `+page.svelte`; Tests: `compareNewVorlage.test.ts`, `ladeVorlage.test.ts`). Alle Mutationen per String-Ersetzung mit Sicherungskopie im Session-Scratchpad, danach `cmp`-Rückprüfung auf Byte-Gleichheit. Test-Artefakte: `adversary-test-output.txt` (Adversary-Lauf), `test-green-output.txt` (finaler Lauf, 48 bestanden).

### Runde 1 — Verdict BROKEN

Ausgangsstand 25/25 Tests grün, 4 Mutationsfamilien überlebten.

**AC-1 (Felder vorbelegt)** — Feld-Auslassungen für Region, Name, Orte, Zeitplan, Wochentag, Hub, Versand, Tagesfenster, Layout, Alarm, Korridore, Kurzform, `endDate` wurden vom jeweiligen Feld-Test gefangen.
Code reference: frontend/src/lib/components/compare-new/compareNewVorlage.ts:32-50
Status: teilweise CONFIRMED — Finding F001.

**AC-2 (Namenssuffix)** — Mutation „Suffix entfernen" rot.
Code reference: frontend/src/lib/components/compare-new/compareNewVorlage.ts:42
Status: CONFIRMED

**AC-3 (keine Identität, Anlege-Modus)** — `isEditMode` mitübertragen wurde gefangen; der Payload-Test war vakuös — Finding F004.
Code reference: frontend/src/lib/components/compare-new/compareNewVorlage.ts:33-34
Status: teilweise CONFIRMED

**AC-4 / AC-5 (gelöschte Orte, Sperre)** — Filter-Mutation rot in AC-4 und beiden AC-5-Tests.
Code reference: frontend/src/lib/components/compare-new/compareNewVorlage.ts:44
Status: CONFIRMED (Hinweis: Test misst den Reiter NACH Orte, Spec-Wortlaut „Orte-Reiter" — Wortlaut in `/60-validate` nachziehen)

**AC-6 (Server-Load, Nutzertrennung)** — Verhalten per Probe korrekt (Cookie durchgereicht, kein `"default"`-Fallback, nicht-OK ⇒ `vorlage: null`), aber ohne Kern-Test — Finding F003.
Code reference: frontend/src/routes/compare/new/+page.server.ts:11-22

**AC-9 (Sentinels)** — `null`→`[]` und `endDate || ''` rot; `outlookMetricFormats null→{}` überlebte — Teil von F001.

Findings Runde 1:
- **F001 (MEDIUM, spec_violation):** channelActiveMetricKeys, channels, channelThresholds, officialWarningsEnabled, officialAlertTriggersEnabled, activeMetricKeys, idealRanges, outlookMetricFormats ungeschützt. Code reference: frontend/src/lib/components/compare-new/compareNewVorlage.ts:32-50. Remediation: Fixture mit abweichenden Werten, je Feld ein Test.
- **F002 (LOW, edge_case):** Region-Rückfall `'ZZ'` überlebte. Code reference: frontend/src/lib/components/compare-new/compareNewVorlage.ts:41. Remediation: Test mit minimaler Vorlage.
- **F003 (MEDIUM, spec_violation):** Server-Load ohne Kern-Test; vier Mutationen (Ersatzvorlage, Cookie, leeres `from`, `catch`) unentdeckt. Code reference: frontend/src/routes/compare/new/+page.server.ts:11-22. Remediation: Kern-Test mit gestubbtem `fetch`.
- **F004 (MEDIUM, anti_pattern):** AC-3-Payload-Test aus Handauswahl gebaut, geht nicht durch `saveNewPreset`. Remediation: echten Speicherweg und positive Prüfung.
- **F005 (LOW, edge_case):** Client-Navigation `?from=A`→`?from=B` befüllt den Zustand nicht neu (Spec-Entscheidung 8). Hinweis für #2278.

### Runde 2 — Fix-Loop 1, erneute unabhängige Prüfung, Verdict AMBIGUOUS

Developer ergänzte nur Tests (Fixture-Erweiterung, Feld-Tests, F002-Test, AC-3-Test über echtes `saveNewPreset` mit gestubbtem `fetch`, neue Datei `ladeVorlage.test.ts`). Der Adversary fuhr 29 eigene Mutationen: F001/F003/F004 behoben und wirksam, alle Kern-Zusicherungen rot gefangen (auch Reihenfolge Alarm-vor-Hub über „aktive Metriken … fehlend bleibt null").

Ungefangen:
- äquivalente Mutation `officialAlertTriggersEnabled ?? true` — kein Finding.
- **F006 (LOW→im Ticket geschlossen):** `if (!res.ok) return null;` entfernen ließ keinen Test rot (Fehler-Body scheitert zufällig an der Formatprüfung). Code reference: frontend/src/routes/compare/new/+page.server.ts:15. Remediation: 403/404 mit gültigem Vorlagen-Body.

## Fix-Loop 2 — F006 geschlossen

Zwei neue Tests (403 und 404 mit gültigem Vorlagen-Body, erwartet `vorlage === null`). Mutation `if (!res.ok)` entfernt ⇒ genau diese beiden Tests rot; Original per `cmp` wiederhergestellt. Finaler Lauf: 48 von 48 bestanden.
Code reference: frontend/src/routes/compare/new/+page.server.ts:15

## Restpunkte (keine Blocker, laut Spec Staging-Schicht)

- AC-7, AC-10, AC-11 nur im Staging-E2E `frontend/e2e/compare-new-vorlage.spec.ts` messbar (Kern kann `+page.svelte`-Verdrahtung/`$effect` nicht beobachten). Code reference: frontend/src/routes/compare/new/+page.svelte:22
- F005 → Vermerk für #2278; AC-5-Wortlaut → Spec-Text in `/60-validate` angleichen.
- Multi-User: kein `"default"`-Fallback, Cookie des aufrufenden Nutzers wird durchgereicht (Test mit zwei Nutzern in `ladeVorlage.test.ts`); die Isolation selbst trägt die unveränderte Go-API (`WithUser`).

## Verdict

**VERIFIED**

Kern-Schicht: alle Findings F001–F004 und F006 behoben und durch Mutation belegt; F002 mitgenommen; F005 als Hinweis. Staging-E2E (AC-7/10/11) bleibt Deploy-Gate.

Tests: 48 passed, 0 failed.

## Geprüfte Dateien

- sha256:7f87aaf55ade9400ac7fdd055546ef1c1fcb9819f203d818bdc46de2a9ad3c1a  frontend/src/lib/components/compare-new/compareNewVorlage.ts
- sha256:2ea5190a6d95d6982429ed72b96df0e3eb2065b8b8d1eb9d6c8b97f538a08617  frontend/src/routes/compare/new/+page.server.ts
