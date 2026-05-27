# Context: Issue #402 — Trips-Seite Atomic-Migration

## Request Summary

`frontend/src/routes/trips/+page.svelte` wurde in #282/#295 visuell redesigned, aber nie auf
die Atomic-Bibliothek (`atoms/` + `molecules/`) umgestellt. Ziel: direkte `ui/`-Importe durch
Atom-/Molecule-Barrel-Importe ersetzen und den handgebauten Inline-Stats-Streifen durch das
`Stat`-Molecule ersetzen. **Keine Logik-, keine visuelle Änderung.** Teil von Epic #368 Phase 2.

## Related Files

| Datei | Relevanz |
|------|-----------|
| `frontend/src/routes/trips/+page.svelte` | **Einziges zu änderndes File.** 644 Z., 8 `ui/`-Importe (Z. 5–21), Inline-Stats-Streifen (Z. 261–276) |
| `frontend/src/lib/components/atoms/index.ts` | Barrel der Atom-Schicht (#371). Re-Export-Bridge auf `ui/`. Enthält **Btn, Input, Dot, Eyebrow** (relevant) |
| `frontend/src/lib/components/molecules/index.ts` | Barrel der Molecule-Schicht (#372). Enthält **`Stat`** |
| `frontend/src/lib/components/molecules/Stat.svelte` | Ziel-Komponente für den Stats-Streifen |
| `frontend/src/lib/utils/tripStatus.ts` | `deriveTripStatus()` — liefert die Status-Zähler, bleibt unverändert |

## Existing Patterns

- **Bridge-Atome (#371):** `atoms/Btn.svelte` etc. sind dünne Wrapper, die `ui/btn/Btn.svelte`
  1:1 durchreichen (`<Btn {...props} />`). Migration ist ein **reiner Import-Pfad-Tausch** ohne
  Verhaltensänderung — exakt das, was AC-1 verlangt.
- **Referenz-Migrationen (Epic #368 Phase 2):**
  - `issue_388_archiv_atomic.md` / `archiv/+page.svelte` — hat **nur** den Stats-Streifen auf
    `Stat` migriert, Btn/Eyebrow/Segmented aber in `ui/` belassen (Teil-Migration).
  - `issue_390_compare_atomic_migration.md`, `issue_389_trip_detail_atomic.md`,
    `issue_386_home_atomic_migration.md` — gleiche Phase-2-Vorgehensweise.
- **Stats-Streifen heute (Z. 261–276):** `{#each [...] as stat}` über 4 Status-Definitionen
  (Aktiv/Geplant/Pausiert/Archiviert, je `tone`), Count via
  `trips.filter(t => deriveTripStatus(t, now) === stat.status).length`, gerendert als
  `<div><Dot tone size="sm"/><span mono>{count}</span><div>{label}</div></div>`. Sichtbar nur
  auf Desktop (`hidden desktop:flex`), nur wenn `trips.length > 0`.

## Dependencies

- **Upstream (was diese Seite nutzt):** Atom-Barrel `$lib/components/atoms`, Molecule-Barrel
  `$lib/components/molecules`, weiterhin `ui/` für nicht-atomisierte Komponenten (s.u.).
- **Downstream (was diese Seite nutzt / wer sie nutzt):** SvelteKit-Route `/trips`, kein
  anderer Code importiert aus `+page.svelte`. Risiko isoliert.

## Existing Specs

- `docs/specs/modules/issue_371_atoms.md` — Atom-Schicht (Bridge-Ansatz, AC-1)
- `docs/specs/modules/issue_372_molecules.md` — Molecule-Schicht inkl. `Stat`
- `docs/specs/modules/issue_388_archiv_atomic.md` — direktes Vorbild (Stats→`Stat`)
- `docs/specs/modules/issue_390_compare_atomic_migration.md` — Phase-2-Migrations-Vorbild

## Risks & Considerations

1. **AC-1 wörtlich nicht erfüllbar — Scope-Abgrenzung nötig (KERNFRAGE für Phase 2/3):**
   Die Trips-Seite importiert 8 Komponenten aus `ui/`: **Btn, Input, Dot, Eyebrow** (haben
   Atom-Pendant) sowie **Table, Dialog, Select, EmptyState, Checkbox** (haben **kein**
   Atom-/Molecule-Pendant — existieren nur in `ui/`). „Keine direkten `ui/`-Importe mehr" ist
   also nur für die 4 atomisierten Komponenten + `Stat` erfüllbar. Table/Dialog/Select/
   EmptyState/Checkbox bleiben in `ui/`, bis die Atomic-Bibliothek sie abdeckt. Das deckt sich
   mit dem Issue-Aufwand (~15–20 LoC) und dem #388-Vorbild. → In Spec als bewusste
   Scope-Grenze festhalten (Tech-Lead-Entscheidung, keine PO-Frage).

2. **Stat-Molecule-Prop-Mapping:** Vor der Spec muss das Prop-Interface von `Stat.svelte`
   verifiziert werden (Label/Wert/Tone/`layout="inline"` wie in #388). Der heutige Streifen ist
   Desktop-only mit Mono-Zahl — das visuelle Ergebnis muss 1:1 bleiben (AC-2: „dieselben Zähler").

3. **Worktree-State-Routing:** Session läuft in Worktree `abundant-swimming-narwhal`. Specs/
   Test-Artefakte werden gegen das Hauptrepo aufgelöst — Artefakte ggf. dorthin spiegeln.

4. **Kein Backend, kein Mail, frontend-only:** E2E-Verifikation = visuelle Prüfung gegen Staging
   (kein Mail-Test). Post-Push-Workflow Schritt 3 = visueller Check via Playwright/Screenshot.

5. **Regressions-Schutz:** `contrast-audit.test.ts` (#377) und ggf. `atoms.test.ts`/
   `molecules.test.ts` bei jeder UI-Arbeit mitlaufen lassen.

## Analyse-Ergebnis (Phase 2)

### Befund: `Stat`-Molecule hat keinen Status-Punkt + festes Aussehen
`Stat.svelte` rendert Label + Wert (Inline: Wert ≥22px, Label uppercase mono caps), optional
`tone="accent"` (nur Textfarbe). **Kein** farbiger Status-`Dot`. Der heutige Trips-Streifen
(Z. 261–276) zeigt aber pro Status einen farbigen `Dot` (success/info/warning/danger) +
Mono-Count (~14px) + Normalcase-Label. → Konflikt zwischen Issue-Vorgaben „keine visuelle
Änderung" und „implementiert über Stat-Molecule".

### PO-Entscheidung (2026-05-27)
**Variante A — `Stat`-Baustein + farbige Punkte behalten.** Umsetzung: pro Status
`<Dot tone size="sm">` (aus `atoms`) + `<Stat layout="inline" label value>` (aus `molecules`)
komponieren. Typografie folgt dem `Stat`-Baustein (größere Zahl, Kapitälchen-Label — wie
Archiv-Seite #388); Status-Farben bleiben über die Punkte erhalten.

### Import-Mapping (AC-1, bewusste Scope-Grenze)
| Import heute (`ui/`) | Ziel | Begründung |
|---|---|---|
| Btn, Input, Dot, Eyebrow | `$lib/components/atoms` | Atom-Pendant existiert (Bridge-Wrapper) |
| Stats-Streifen (inline) | `$lib/components/molecules` → `Stat` (+ `Dot`) | Molecule existiert |
| Table, Dialog, Select, EmptyState, Checkbox | **bleiben `ui/`** | Kein Atom-/Molecule-Pendant in der Bibliothek |

### Scope
- **Files:** 1 (`frontend/src/routes/trips/+page.svelte`)
- **LoC:** ~15–25 (innerhalb 250-Limit)
- **Tests:** kein bestehender Test referenziert `trips/+page.svelte` → kein Test bricht durch
  den Import-Tausch. Neuer Sentinel-Test (Import-Quellen prüfen, analog `issue_388.test.ts`)
  ist sinnvoll für AC-1/AC-2.
- **Risiko:** gering, isoliert auf eine Route.
