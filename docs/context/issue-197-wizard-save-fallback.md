# Context: Issue #197 — Save-Pipeline: Fallback auf `/` wenn Trip-Detail-Route fehlt

## Request Summary

Nach erfolgreichem Trip-Save im Wizard (`POST /api/trips` 201) leitet `WizardState.save()` auf `/trips/${id}` weiter — die SvelteKit-Route existiert aber noch nicht (kommt erst mit Epic #135). User landet auf leerer 404-Seite. Master-Spec schreibt für genau diesen Fall einen Fallback vor; er ist nicht implementiert.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/trip-wizard/wizardState.svelte.ts` | **Bug-Ort.** Zeile 293: `await goto(/trips/${trip.id})` — der unbedingte Redirect ohne Fallback. |
| `frontend/src/routes/trips/[id]/edit/+page.svelte` | Existiert. Einzige `/trips/[id]/...`-Route, die heute funktioniert. |
| `frontend/src/routes/trips/[id]/+page.svelte` | **Existiert NICHT** (Verzeichnis `[id]` enthält nur `edit/`). Bestätigt die Wurzel des 404. |
| `frontend/src/routes/trips/+page.svelte` (Zeile 92) | Bestehendes Pattern: nach Trip-Klick → `goto(/trips/${trip.id}/edit)`. Alternativ-Ziel zum `/`-Fallback. |
| `frontend/src/lib/components/trip-wizard/__tests__/wizardState.test.ts` | Test-File. Testet `save()` aktuell NICHT direkt — nur Initial-State von `saveStatus`/`saveError`. |
| `docs/specs/modules/epic_136_trip_wizard.md` | Master-Spec §1.4: schreibt Fallback auf `/` explizit vor. |
| `docs/specs/modules/epic_136_step4_briefings.md` | Sub-Spec für Step 4 (Save-Pipeline-Trigger). |
| `docs/artifacts/issue-164-wizard-step4-channels/validator-report.md` | AC #25 (Zeile 80): Validator hat Redirect als PASS markiert — aber 404-Folge nicht überprüft. Lessons-learned-Eintrag fürs Spec/Validator-Pattern. |

## Existing Patterns

- **Lazy-Import von `goto`/`api`** (wizardState.svelte.ts Zeile 11-13, 289-292): bewusst, damit Plain-Node-Unit-Tests die Klasse instanziieren können, ohne SvelteKit-Aliase aufzulösen. Fix muss dieses Pattern erhalten.
- **Andere `goto`-Redirects nach Trip-Operation** (`+page.svelte` Zeile 92): nutzen `/trips/${id}/edit` — eine konkrete, existierende Detail-Route.
- **Master-Spec-Konditional-Patterns**: §1.4 enthält die "falls noch nicht vorhanden, Fallback auf /"-Klausel — Spec ist also bereits korrekt formuliert, nur die Implementierung weicht ab.

## Dependencies

- **Upstream:** `Step4Briefings.svelte` ruft `wizardState.save()` über Save-Button.
- **Downstream:** Validator-Tests, E2E `trips.spec.ts`, Master-Spec §1.4. Sobald Epic #135 die Detail-Page liefert, muss der Fallback wieder entfernt werden.

## Existing Specs

- `docs/specs/modules/epic_136_trip_wizard.md` §1.4 — Master-Spec mit Fallback-Klausel
- `docs/specs/modules/epic_136_step4_briefings.md` — Save-Pipeline-Spec

## Risks & Considerations

1. **Spec sagt `/`, aber `/trips` (Übersichtsliste) wäre semantisch näher** — der User hat gerade einen Trip erstellt, will diesen in der Liste sehen. Tech-Lead-Empfehlung: in Analyse-Phase mit dem User klären, ob wir vom Spec abweichen (`/trips` statt `/`).
2. **Alternative `/trips/${id}/edit`** existiert ebenfalls und zeigt sogar die Trip-Details — würde aber den User direkt in Bearbeitungs-Modus stecken. Wahrscheinlich nicht gewünscht.
3. **`fetch HEAD`-Probe** (Issue-Vorschlag): zu komplex für temporären Workaround — wir wissen statisch, dass Route fehlt.
4. **Test-Coverage:** `save()` ist aktuell nicht test-abgedeckt. RED-Phase muss einen Test einführen, der den Redirect-Pfad asserted.
5. **Spätere Bereinigung:** Sobald Epic #135 fertig, soll Fallback entfernt werden. Code-Kommentar mit Issue-Referenz pflichtbewusst setzen, damit Cleanup nicht vergessen wird.
6. **Validator-Lessons-learned:** AC #25 hat 404-Page nicht erkannt, weil URL-Wechsel ausreichte. Folge-Issue (oder Adversary-Verschärfung): Validator soll nach Redirect Page-Content laden, nicht nur URL prüfen. Nicht Scope dieses Issues.
