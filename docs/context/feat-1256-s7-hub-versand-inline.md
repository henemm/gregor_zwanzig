# Context: 1256-s7-hub-versand-inline (Scheibe 7 von #1256)

## Request Summary

Der Versand-Tab im Compare-Detail-Hub (`CompareTabs.svelte`) ist heute ein
Read-only-Bespoke-Nachbau (disabled Kanal-Switches, „Bearbeiten →"-Redirect
`goToEditVersand()` nach `/compare/{id}/edit?tab=versand`). Scheibe 7 ersetzt
ihn durch die Einbettung des geteilten `<VersandTab context="vergleich">` —
Inline-Edit-Parität nach dem in S6 etablierten Muster (CorridorEditor +
`compareHubWizardBridge`).

Programm-Spec: `docs/specs/modules/issue_1256_compare_ui_rewire.md`
§ Scheibe 7 (Z.462–486), ACs: AC-17, AC-18, AC-19, AC-20, AC-35, AC-36, AC-37.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/compare/CompareTabs.svelte` (1130 Z.) | MODIFY: Bespoke-Versand-Panel (ab Z.608) durch `VersandTab`-Einbettung ersetzen; `goToEditVersand()` (Z.401–406) entfällt; `handleToggleActive` (Übersicht-Tab) für AC-37 wiederverwenden |
| `frontend/src/lib/components/shared/VersandTab.svelte` (410 Z.) | Geteilter Organism, wird EINGEBETTET, 0 Zeilen Diff angestrebt (C0). `context="vergleich"`-Zweig bindet an `wiz.*`, KEIN Self-Save |
| `frontend/src/lib/components/compare/compareHubWizardBridge.ts` | MODIFY: Hydration + PUT-Payload um Versand-Felder erweitern (S6-Muster: `HubWizardFields`, `HubEdit`, `flushPending*`) |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | Konsumiert: `CompareEditorEdits` unterstützt bereits `sendTelegram/sendSms/morningEnabled/morningTime/eveningEnabled/eveningTime/endDate/alertCooldownMinutes/alertQuietFrom/alertQuietTo` (Z.51–57, 137–156) — Payload-Seite ist fertig |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | Trägt alle nötigen Runen (`sendEmail/sendTelegram/sendSms`, `morningEnabled/…`, `endDate`, `alertCooldown*`) |
| `frontend/src/routes/compare/[id]/edit/+page.svelte` (Z.35–61) | Vorbild für die Versand-Feld-Hydration aus dem Preset (Defaults identisch übernehmen) |
| `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte` | Trip-Pendant: bettet `VersandTab context="route"` bereits inline in den Trip-Hub ein — S7 stellt exakt diese Parität her (Teilungs-Invariante) |
| `frontend/src/lib/components/compare/__tests__/compare_hub_wizard_bridge.test.ts` | Bestehende Bridge-Tests, werden erweitert |

## Existing Patterns

- **S6-Einbettungsmuster (live, adversary-gehärtet):** Lazy-Hydration beim
  ersten Tab-Besuch aus `currentPreset` (nie aus der eingefrorenen
  `preset`-Prop — F005), Event-diskretisierte PUTs OHNE Auto-Save-Timer
  (#1234), Diff-Wächter gegen No-Op-PUTs, Rollback-Snapshot bei PUT-Fehler
  (Edge Case Z.1020), Baseline-Auffrischung aus dem PUT-Response-Body,
  fenster-weiter Flush-Guard (F002) für Pointer-Releases außerhalb des
  Wrapper-Subtrees.
- **VersandTab-Doppelrolle:** `context="route"` = Self-Save via
  `saveController` (Trip-Hub); `context="vergleich"` = reine `wiz.*`-Mutation,
  Persistenz zentral beim Aufrufer (Compare-Editor: Save-Button). Im Hub gibt
  es keinen Save-Button → der Hub muss den Commit-Trigger liefern (S6-Muster).
- **`activation`-Snippet-Prop:** VersandTab rendert am Ende des
  vergleich-Zweigs ein optionales `activation`-Snippet — dafür vorgesehen
  für die Aktivierungs-Karte (AC-17/AC-37).
- **`handleToggleActive` existiert bereits im Hub** (Übersicht-Tab, F007-fix
  mit `buildToggleActivePutPayload` aus `currentPreset`) — AC-37
  wiederverwendet ihn, kein neuer PUT-Pfad.

## Dependencies

- Upstream: `buildComparePresetSavePayload` (Round-Trip-Spread, #679),
  `api.put` auf `/api/compare/presets/{id}`, `CompareWizardState`.
- Downstream: Playwright-Specs des Hubs (17 Compare-Specs, `/edit` bleibt
  parallel bestehen — Staffelungs-Stufe 2 der Spec); Vorschau-Tab (AC-19
  Regression); `versandSummaryText` im Übersicht-Tab (liest Preset-Zeiten —
  Stale-bis-Reload ist bekannter Nebenbefund in #1199).

## Handoff-5 Punkt 5 (Konflikt Spec ↔ neueres PO-Dokument)

Die Programm-Spec (älter) beschreibt die S7-Einbettung „inklusive der
kompletten notify-Zustellung (Cooldown/Stille Stunden)". Das verbindliche
Handoff-5-Dokument (`claude-code-handoff/issue-bodies/body-1256-compare-ui-fragen.md`,
PO-entschieden 2026-07-14, P5) revidiert: Versand-Tab trägt künftig NUR das
geplante Briefing; Cooldown/Stille Stunden/Beispiel-Warnung/amtliche Warnungen
wandern mit **#1258** in einen eigenen Alarme-Tab (Trip UND Vergleich).

Tech-Lead-Position (Entscheidung beim PO in der Spec-Freigabe):
Organism 1:1 einbetten wie er heute ist (inkl. der noch enthaltenen
Alert-Sektion) — #1258 zieht die Sektion danach für Editor UND Hub
gleichzeitig um. Keine Hub-Sondervariante (Teilungs-Invariante), kein
Vorgriff auf #1258. S7 baut nichts Neues an notify.

## Risks & Considerations

- **Kein `send_email`-Feld im ComparePreset** (weder Go-Model noch TS-Typ):
  Der E-Mail-Switch ist auch im Editor togglebar, wird aber nie persistiert —
  vorbestehende Lücke, NICHT S7-Scope. AC-35-PUT-Assertion muss auf
  Telegram/SMS testen; Verhalten des E-Mail-Switch = Editor-Parität.
  → Known Limitation in der Freigabe nennen.
- **Datenverlust-Historie:** S6 fand 3 echte Lost-Update-Bugs (F002/F005/F007)
  bei exakt diesem Muster. S7-Committrigger sind einfacher (change/focusout
  statt Slider-Drag), aber: gleiche `currentPreset`-Baseline für ALLE
  PUT-Pfade zwingend; der Versand-Flush darf den Idealwerte-Flush nicht
  überschreiben (zwei Tabs, ein `wizardState`, eine Baseline).
- **`endDate`-Sentinel:** `CompareEditorEdits.endDate` — `undefined` =
  unangetastet, `null` = „bis auf Weiteres" (sendet `""`), String =
  Datum. Bei der Hub-Hydration/Diff-Bildung nicht verwechseln.
- **AC-20 (CompareMatrix/HourlyMatrix Totcode-Grep)** ist reiner
  statischer Test, kein Code-Eingriff.
- **LoC:** ~200 netto laut Spec, Override-Kandidat — Ankündigung beim
  Scheiben-Start ist hiermit erfolgt; Override nur nach PO-Erlaubnis.
