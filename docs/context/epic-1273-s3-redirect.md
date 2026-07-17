# Context: epic-1273-s3-redirect

## Request Summary

Epic #1273 Slice S3: Die alte, separate Bearbeiten-Seite (`/compare/[id]/edit`) entfällt zugunsten des Hubs (`/compare/[id]`), der seit S1 (Save-Chip) und S2 (Name/Region/Profil editierbar) voll funktionsfähig als einzige Bearbeiten-Fläche ist. Alle produktiven Links werden umgebogen, die alte Route wird zum reinen Redirect (kein 404, kein CompareEditor-Rendering mehr). `CompareEditor.svelte` selbst wird NICHT gelöscht (das ist S5) — nur unerreichbar gemacht.

PO-Entscheid (AskUserQuestion, 2026-07-17): Der "Bearbeiten"-Knopf (Desktop) und das Stift-Icon, die bereits direkt auf dem Hub selbst sitzen, werden **entfernt** (nicht auf einen Tab umgeleitet) — sie sind auf der Seite, die man schon bearbeitet, sinnlos, analog zum Trip-Hub, der diesen Knopf ebenfalls nicht hat.

## Related Files

| File | Relevance | Änderung |
|------|-----------|----------|
| `frontend/src/routes/compare/[id]/edit/+page.svelte` + `+page.server.ts` | Alte Bearbeiten-Route | Wird zum reinen Redirect auf `/compare/[id]` (kein CompareEditor-Rendering mehr) |
| `frontend/src/routes/compare/[id]/+page.svelte:216-219` | `handleAction()` im Hub selbst | `id === 'edit' \|\| id === 'setup'`-Zweig entfernen (tote Branch, da `compareDetailActions()` künftig kein `edit` mehr liefert) |
| `frontend/src/routes/compare/[id]/+page.svelte:335-336` | Desktop "Bearbeiten"-Button | **Entfernen** (PO-Entscheid) |
| `frontend/src/routes/compare/[id]/+page.svelte:376-380` | Mobile Stift-Icon (TopBar) | **Entfernen** (PO-Entscheid) |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts:315-322` | `compareDetailActions()` — Hub-eigener Kebab | `editAction`-Zweig entfernen, Funktion liefert nur noch `compareLifecycleActions(status)` (deckt sich bereits mit dem Draft-Fall) |
| `frontend/src/routes/_home/CompareKachel.svelte:20` | Home-Kachel-Kebab (externer Einstieg) | `/edit` → `/compare/{id}` (Ziel bleibt erreichbar, Redirect entfällt für diesen Pfad direkt) |
| `frontend/src/routes/compare/+page.svelte:119-120` | Listen-Kebab, Actions `setup`+`edit` (externer Einstieg) | Beide → `/compare/{id}` |
| `frontend/src/routes/+page.svelte:97` | Home-Hero href-Helper (externer Einstieg) | `/edit` → entfällt aus dem Pfad |
| `frontend/src/routes/+page.svelte:560,566,572` | Home-Hero-Karte, 3 Links (externer Einstieg) | `/compare/{id}` · `/compare/{id}?tab=idealwerte` · `/compare/{id}?tab=versand` (Hash→Query-Fix, die alten `#idealwerte`/`#schedule`-Anker liefen schon vorher ins Leere, s. S1-Analyse) |

**Bewusst NICHT geändert:** `compareActions()` (Zeile 273-292, Listen-/Home-Kebab) behält `edit`/`setup` — das sind externe Einstiege, die weiterhin zum Hub führen sollen, nur eben nicht mehr zu `/edit`.

## Existing Patterns

- **#616 (Trip-IA):** exaktes Vorbild — `routes/trips/[id]/edit/+page.svelte` leitet auf die kanonische Trip-Oberfläche um (AC-2), keine tote Route.
- **CompareTabs.svelte unterstützt bereits `?tab=`** (`initialTab`-Prop, `resolve()`) — kein neuer Mechanismus nötig, nur die Linkziele ändern sich.

## Dependencies

- **Vorbedingung erledigt:** S1 (Save-Chip, live), S2 (Name/Region/Profil editierbar, live) — beide notwendig, damit der Hub tatsächlich feature-vollständig ist, bevor die alte Route stillgelegt wird.
- **Downstream:** S4a/S4b (Test-Migration der ~26 e2e-Specs + ~15 Unit-Tests, die noch `/edit` ansteuern) — S3 macht diese Tests strukturell rot (Route liefert jetzt einen Redirect statt der CompareEditor-Seite). Das ist erwartet und wird in S4 behoben, nicht Teil von S3.
- **S5 (CompareEditor-Löschung):** noch nicht Teil dieser Slice — `CompareEditor.svelte` bleibt als toter Code liegen, nur unerreichbar.

## Analysis

### Type
Feature (Standard Track)

### Technical Approach
1. Redirect-Route: `+page.server.ts` (oder `+page.svelte`-Load) unter `/compare/[id]/edit` wirft `redirect(307, `/compare/${params.id}`)` — kein Rendering von `CompareEditor.svelte` mehr für diesen Pfad.
2. 7 externe Link-Stellen auf `/compare/{id}` (bzw. `?tab=` für die 2 Hash-Anker) umbiegen.
3. 2 hub-interne, jetzt sinnlose Bearbeiten-Affordanzen (Desktop-Button, Mobile-Stift-Icon) entfernen, inkl. der zugehörigen toten `handleAction`-Branch und dem `editAction`-Zweig in `compareDetailActions()`.

### Scope Assessment
- Files: ~8 (Redirect-Route: 2 Dateien, Hub selbst: 1, subscriptionHelpers.ts: 1, CompareKachel: 1, Liste: 1, Home: 1) — plus zugehörige Unit-Tests, die diese Funktionen source-inspizieren, ggf. anzupassen (im Rahmen der Slice, nicht die große S4-Testmigration)
- Estimated LoC: ~100-150 (viele 1-5-Zeilen-Diffs + die Redirect-Route)
- Risk Level: LOW-MEDIUM — reine Umleitung + Entfernen redundanter UI, keine Datenmodell-Änderung

### Dependencies
Siehe oben.

### Open Questions
- [x] Was passiert mit dem Hub-eigenen "Bearbeiten"-Knopf/Stift-Icon? → PO-Entscheid: entfernen.
- [x] Betroffene Unit-Tests gefunden: `frontend/src/lib/components/compare/__tests__/compareDetailEditActions.test.ts` (aus #1261) prüft aktuell explizit, dass `compareDetailActions('active'|'paused')` einen `edit`-Eintrag ENTHÄLT — das ist per S3-Entscheid jetzt falsch und muss auf "enthält KEINEN edit-Eintrag mehr" gedreht werden (bewusste Verhaltensumkehr von #1261, durch S2s Inline-Editierbarkeit überholt). Die AC-4-Prüfung (Draft ohne edit) und die Regressionsprüfung (`compareLifecycleActions` nie mit edit, wegen MCompareActionSheet) bleiben unverändert gültig.

## Next Step

Weiter mit `/30-write-spec`.
