---
entity_id: bundle_d_mail_ui_schalter
type: module
created: 2026-06-20
updated: 2026-06-20
status: draft
version: "1.0"
tags: [frontend, editor, email, report-config]
issues: [785, 709]
bundle: D-mail-ui-schalter
---

# Bundle D — E-Mail-Inhalt: Vortag-Toggle + UI-Bereinigung (Issues #785, #709)

Closes #785
Relates to #709

## Approval

- [ ] Approved

## Purpose

Issue #785 identifizierte, dass vier `report_config`-Felder im Backend schalten können, aber
kein entsprechendes UI-Element in `EditReportConfigSection.svelte` haben:
- `show_quick_take_tags` — Quick-Take-Chips
- `show_stability` — Großwetterlage-Label
- `show_highlights` — Highlights/Zusammenfassung
- `show_yesterday_comparison` — Vortag-Vergleich

Nach Analyse des aktuellen Zustands zeigt sich: Drei dieser vier Felder
(`show_quick_take_tags`, `show_highlights`, `show_stability`) sind durch Issue #723 und #790
bereits im Backend als deprecated / ohne Render-Effekt markiert. Sie werden in `html.py`
über `**_ignored` verschluckt — ein UI-Toggle dafür wäre sinnfrei.

**Einziger echter Gap: `show_yesterday_comparison`** ist aktiv im Render-Pfad
(`formatters/trip_report.py:135`, `html.py:592-598`) und hat einen funktionierenden
Backend-Schalter — aber kein Checkbox-Element in der UI. Der Nutzer kann die
Vortag-Vergleich-Sektion nie abschalten.

Issue #709 stellt fest, dass die bisherigen UI-Optionen für den User verwirrend sind
("Kompakte Zusammenfassung" klingt wie zum dritten Mal dasselbe). Die PO-Entscheidung
(Kommentar #709, 2026-06-10) hat bereits in Issues #721/#722/#723 umgesetzt — UI auf
3 Bausteine eingedampft. Offen geblieben: der fehlende `show_yesterday_comparison`-Toggle.

## Was wird umgesetzt

**Einzige Code-Änderung:** `show_yesterday_comparison`-Checkbox in der E-Mail-Inhalt-Card
von `EditReportConfigSection.svelte` hinzufügen — als 4. Baustein unter den bestehenden 3
(`show_metrics_summary`, `show_outlook`, `show_stage_stats`).

Die drei anderen in #785 genannten Felder (`show_quick_take_tags`, `show_stability`,
`show_highlights`) bleiben bewusst ohne UI-Element, da sie im Renderer inaktiv sind.

## Source

- **Datei (Änderung):** `frontend/src/lib/components/edit/EditReportConfigSection.svelte`
  — `$state`-Variable `show_yesterday_comparison` aus der stummen Bestandsdaten-Gruppe
  in die aktive E-Mail-Inhalt-Card verschieben
- **Datei (Änderung):** `frontend/src/lib/components/edit/reportConfigWrite.ts`
  — `MailElementUi`-Interface um `show_yesterday_comparison` erweitern +
  `CONTENT_MODULE_DESCRIPTIONS`-Eintrag ergänzen

## Aktueller Zustand

**In `EditReportConfigSection.svelte`:**
- `show_yesterday_comparison` ist NICHT deklariert (weder als `$state` noch im Write-Back)
- Das Feld wird beim Laden aus dem Backend NICHT gelesen (`onMount` kennt es nicht)
- Beim Schreiben wird es NICHT in den `merged`-Blob aufgenommen
- Folge: Jeder Speicher-Vorgang überschreibt `show_yesterday_comparison` mit dem Backend-Default `True`
  (da `originalReportConfig`-Spread den alten Wert bei erstem Edit verliert, sobald Go die
  opaque map zurückschreibt)

**Im Backend:**
- `models.py:735`: Feld `show_yesterday_comparison: bool = True` definiert
- `loader.py:402`: Lesen mit `rc_data.get("show_yesterday_comparison", True)`
- `loader.py:1125`: Serialisierung beim Schreiben
- `formatters/trip_report.py:135`: Render-Gate aktiv (False → `day_comparison = None`)
- `html.py:592-598`: `day_comparison_html` erscheint nur wenn `day_comparison` nicht None

## Estimated Scope

- **LoC:** ~25
- **Files:** 2 (beide Frontend)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `EditReportConfigSection.svelte` | modify | Checkbox hinzufügen, State-Variable aktivieren |
| `reportConfigWrite.ts` | modify | Interface + Beschreibung ergänzen |

## Implementation Details

### EditReportConfigSection.svelte

1. In der State-Sektion (nach `show_outlook`) hinzufügen:
   ```
   let show_yesterday_comparison = $state(true);
   ```

2. In `onMount` → E-Mail-Elemente-Block hinzufügen:
   ```
   if (typeof c.show_yesterday_comparison === 'boolean')
     show_yesterday_comparison = c.show_yesterday_comparison;
   ```

3. Im `$effect` → `merged`-Objekt hinzufügen:
   ```
   show_yesterday_comparison,
   ```

4. In der E-Mail-Inhalt-Card (nach dem `show_stage_stats`-Block) hinzufügen:
   ```svelte
   <div class="text-sm">
     <span data-testid="report-show-yesterday-comparison" class="inline-flex items-center gap-2">
       <Checkbox
         checked={show_yesterday_comparison}
         disabled={email_format === 'compact'}
         onchange={(e) => { show_yesterday_comparison = (e.target as HTMLInputElement).checked; }}
       >{CONTENT_MODULE_DESCRIPTIONS.show_yesterday_comparison.label}</Checkbox>
     </span>
     <p class="pl-6 text-xs text-muted-foreground mt-0.5">
       {CONTENT_MODULE_DESCRIPTIONS.show_yesterday_comparison.description}
     </p>
   </div>
   ```

### reportConfigWrite.ts

1. `MailElementUi`-Interface um Feld ergänzen:
   ```ts
   show_yesterday_comparison?: boolean;
   ```

2. `CONTENT_MODULE_DESCRIPTIONS`-Eintrag ergänzen:
   ```ts
   show_yesterday_comparison: {
     label: 'Vortag-Vergleich',
     description: 'Vergleich des heutigen Wetters mit dem Vortag als Kurzzeile im Briefing.',
   },
   ```

3. `countActiveContentModules` um das neue Feld erweitern:
   ```ts
   ui.show_yesterday_comparison ?? true,
   ```

## Acceptance Criteria

**AC-1:** Given ein Trip mit `show_yesterday_comparison = false` in der Datenbank /
When der Nutzer den E-Mail-Inhalt-Tab öffnet /
Then ist die Checkbox "Vortag-Vergleich" im UI nicht angehakt (unchecked).

**AC-2:** Given die Checkbox "Vortag-Vergleich" ist im UI sichtbar und angehakt /
When der Nutzer die Checkbox abwählt und den Trip speichert /
Then liefert ein anschließender GET `/api/trips/<id>` ein `report_config.show_yesterday_comparison = false`.

**AC-3:** Given `show_yesterday_comparison = false` ist in report_config gespeichert /
When der Scheduler ein Briefing-Mail generiert /
Then enthält die zugestellte Mail keine Vortag-Vergleich-Zeile ("Im Vergleich zu gestern …" oder ähnlich).

**AC-4:** Given ein Trip dessen `report_config` ursprünglich kein `show_yesterday_comparison`-Feld
kennt (Altdaten / Default) /
When der Nutzer den E-Mail-Inhalt-Tab öffnet /
Then ist die Checkbox "Vortag-Vergleich" angehakt (Default = true, Backward-Compatibility).

**AC-5:** Given die E-Mail ist im Format "Kompakt (Nur-Text)" /
When der Nutzer den E-Mail-Inhalt-Tab öffnet /
Then ist die Checkbox "Vortag-Vergleich" deaktiviert (disabled, opacity 0.45 — analog zu den
anderen 3 Bausteinen im Kompakt-Modus).

## Test-Strategie

**Kein Mock.** Verhalten wird gegen die laufende Staging-Umgebung über Playwright bewiesen:

- AC-1/AC-2: Playwright-E2E — Trip anlegen, `show_yesterday_comparison = false` via API-PUT
  setzen, UI öffnen, Checkbox-Status prüfen, abwählen, speichern, API-GET prüfen
- AC-3: Test-Briefing auf Staging triggern (Test-Trip mit `show_yesterday_comparison = false`),
  Mail via IMAP abrufen, Vortag-Zeile darf nicht enthalten sein
- AC-4/AC-5: Playwright — Altdaten-Trip ohne Feld öffnen (Checkbox angehakt), Kompakt-Modus
  wählen (Checkbox disabled)

**Test-Datei:** `tests/tdd/test_bundle_d_785_yesterday_toggle.py`
