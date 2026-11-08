# Context: feature-2837-s2b-fortschritt

## Request Summary
#2837 S2b (Nachzug zu S2, PR #2861): Der Fortschrittsbalken der Anlege-Seiten `/trips/new` und `/compare/new` ist noch vierfach gebaut (je Editor Computer und Handy). Auf dem Handy tönt der Vergleich den aktiven Schritt hell orange, der Trip nicht (Fresh-Eyes-Befund AC-21 S2). Ziel: **ein** Baustein im Anlege-Rahmen, eine Regel für alle Segmente.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/shared/anlege-rahmen/AnlegeRahmen.svelte` | Geteilter Rahmen (S2). Hat heute nur einen `fortschritt`-Snippet-Slot (Z. 36, 72), Handy-Teil ohne Fortschritt |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte:572-584` | Desktop-Balken Trip (Snippet `fortschritt`, Testids `trip-new-progress`, `trip-new-progress-segment`) |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte:963-971` | Handy-Balken Trip (keine Testid; `progressN/PROGRESS_STEPS.length`, aktiver Schritt **nicht** getönt) |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte:466-477` | Desktop-Balken Vergleich (Testids `compare-editor-progress`, `-segment`) |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte:600-607` | Handy-Balken Vergleich (`cm-mobile-progress`; aktiver Schritt `var(--g-accent-soft,#bcd)`) |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts:101-107` | `PROGRESS_STEPS` Trip = `anlegeKette('trip')` ohne optionale Schritte (5) |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte:174-181,233` | `TAB_DEFS`/`PROGRESS_STEPS` Vergleich = `anlegeKette('vergleich')` (5) |
| `frontend/src/lib/components/shared/anlegeLockEngine.ts:70` | `progressCount(done, steps)`, die gemeinsame Zählung |
| `frontend/src/lib/components/compare-new/__tests__/compare_new_lock_engine_wirkstelle.test.ts:108` | Liest den Zähler über die Testid `cm-mobile-progress` aus dem gerenderten HTML. Die Testid muss erhalten bleiben |
| `frontend/src/lib/components/shared/anlege-rahmen/__tests__/anlege_rahmen.test.ts` | Unit-Tests des Rahmens, hier kommen die neuen Zusicherungen hinzu |
| `frontend/e2e/anlege-rahmen-paritaet.spec.ts` (AR-1…AR-18) | Paritäts-E2E aus S2, wird um Fortschritts-Fälle erweitert |
| `docs/specs/modules/rework_2837_s2_anlege_rahmen.md` | S2-Spec. Z. 51 nahm fälschlich an, der Fortschritt sei „schon heute gleich“ |
| `docs/adr/` ADR-0110 | „Hub-Kopf und Anlege-Rahmen ein Baustein“ gilt auch für S2b, kein neues ADR, nur ein Nachtrag |

## Existing Patterns
- S1b (`shared/status-schild/StatusSchild.svelte`) und S2 (`AnlegeRahmen`): ein Baustein, `context` wählt nur Texte und Testid-Präfix, keine Verzweigung im Aufbau.
- Die Zählung ist bereits geteilt (`progressCount` aus `anlegeLockEngine`). Nur das Markup ist doppelt.

## Dependencies
- Upstream: `progressCount`, Design-Token `--g-accent`, `--g-rule`, `--g-accent-soft` (`app.css:209` = `#f3d9c8`), i18n-Schlüssel `trip.anlegen.nichts_eingerichtet` / `trip.anlegen.abschnitte`.
- Downstream: Unit-Test `compare_new_lock_engine_wirkstelle` (Testid `cm-mobile-progress`), E2E-Tests mit den Testids `trip-new-progress*` / `compare-editor-progress*`.

## Analyse und Entscheidung (Summe 1: Kontext und Analyse in einem Durchgang)
- **Neuer Baustein** `shared/anlege-rahmen/AnlegeFortschritt.svelte` mit Props `steps`, `done`, `aktiv?`, `variante: 'desktop'|'mobil'`, `testidPrefix`. Ein Markup für Segmente und Zähler, die Varianten unterscheiden sich nur in Breite (24 px fest gegenüber flex) und Zählertext („n von 5 Abschnitten“ gegenüber „n/5“). Der Rahmen rendert ihn selbst (Desktop im Kopf, Handy als eigener Streifen), die Editoren reichen nur `steps`/`done`/`activeTab` durch. Der Snippet-Slot `fortschritt` entfällt.
- **Regel für den aktiven Schritt (Tech-Lead-Entscheid):** Erledigt = `--g-accent`, sonst `--g-rule`, **keine** Tönung des aktiven Schritts. Begründung: 3 von 4 heutigen Balken tönen nicht (Computer beide, Handy Trip). Den aktiven Schritt zeigt bereits die Reiterleiste direkt darunter (2 px Akzentlinie). Die Tönung `#f3d9c8` gegen `--g-rule` ist kontrastschwach, und das Leitprinzip „hoher Kontrast“ spricht gegen ein schwaches Doppelsignal. Der Rückfallwert `#bcd` (Blau) war ohnehin ein Fehler.
- **Testids:** bestehende bleiben erhalten (`trip-new-progress`, `compare-editor-progress`, `-segment`, `cm-mobile-progress`). Neu ist `tn-mobile-progress` für den Trip, Segmente tragen `data-done`.
- Die Handy-Reiterleiste ist ebenfalls doppelt gebaut, ist aber nicht Teil des Befunds (Fresh-Eyes: gleich). Sie bleibt außerhalb des Umfangs, eine Notiz kommt ins Issue.

## Risks & Considerations
- E2E und Unit-Tests lesen die Testids. Werden sie umbenannt, werden Tests rot, deshalb Testids exakt erhalten.
- Die Handy-Stelle liegt beim Trip außerhalb des `AnlegeRahmen`-Blocks (`tn-desktop` gegenüber `tn-mobile`). Der Rahmen muss deshalb einen Handy-Fortschritt anbieten oder den Baustein direkt einbinden. Entscheidung: Die Editoren binden `AnlegeFortschritt variante="mobil"` an ihrer Handy-Stelle ein, der Rahmen bindet ihn auf dem Computer ein. Es bleibt **ein** Baustein, zwei Einsatzorte je Gerät.
- Reines Frontend, kein Backend, kein Datenmodell.

## Analysis

### Type
Feature (Rework, Nachzug S2b zu #2837 S2). Kontext und Analyse wurden in einem Durchgang erarbeitet (siehe oben). In Phase 2 habe ich alle Stellen direkt im Code nachgeprüft (2026-11-08): Zeilen und Markup stimmen. Eine erneute Explore-Runde war nicht nötig.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/anlege-rahmen/AnlegeFortschritt.svelte` | CREATE | Ein Baustein für Segmente und Zähler, `variante: 'desktop'|'mobil'`, Testid-Props |
| `frontend/src/lib/components/shared/anlege-rahmen/AnlegeRahmen.svelte` | MODIFY | Snippet `fortschritt` entfällt, stattdessen Props `steps`/`done` und eigener Einbau der Desktop-Variante |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | MODIFY | Desktop-Snippet (Z. 571-584) und Handy-Balken (Z. 963-971) durch den Baustein ersetzen, neue Testid `tn-mobile-progress` |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | MODIFY | Desktop-Snippet (Z. 466-477) und Handy-Balken (Z. 600-607) ersetzen, Tönung des aktiven Schritts und Rückfallwert `#bcd` entfallen |
| `frontend/src/lib/components/shared/anlege-rahmen/__tests__/anlege_rahmen.test.ts` | MODIFY | Die Probe `fortschritt`-Snippet (Z. 96, 177) wird zur Zusicherung des eingebauten Bausteins |
| `frontend/src/lib/components/shared/anlege-rahmen/__tests__/anlege_fortschritt.test.ts` | CREATE | Unit-Tests des Bausteins: Segmentzahl, `data-done`, keine Tönung, Zählertexte beider Varianten |
| `frontend/e2e/anlege-rahmen-paritaet.spec.ts` | MODIFY | Paritäts-Fälle für den Fortschritt auf Computer und Handy (Trip = Vergleich) |
| `docs/specs/modules/rework_2837_s2_anlege_rahmen.md` | MODIFY | Z. 51 („Fortschritt schon heute gleich“) richtigstellen, Verweis auf die S2b-Spec |
| `docs/adr/0110-*` | MODIFY | Nachtrag: der Fortschritt gehört zum Anlege-Rahmen-Baustein |

### Scope Assessment
- Files: etwa 9 (4 Code, 3 Test, 2 Doku)
- Estimated LoC: +120/-50 (Code), dazu Tests
- Risk Level: LOW. Nur das Frontend ist betroffen, kein Backend und kein Datenmodell. Die Zählung (`progressCount`) bleibt unverändert, nur das Markup wird zusammengelegt.

### Technical Approach
Siehe „Analyse und Entscheidung“ oben, die Entscheidungen bleiben:
- Ein Baustein `AnlegeFortschritt` mit zwei Einsatzorten: Auf dem Computer bindet ihn der Rahmen ein, auf dem Handy der Editor an seiner Handy-Stelle. Die Handy-Teile liegen außerhalb des Rahmens.
- Farbregel: erledigt = `--g-accent`, sonst `--g-rule`. Der aktive Schritt wird nicht getönt, das zeigt schon die Reiterleiste.
- Die bestehenden Testids bleiben exakt erhalten, neu ist `tn-mobile-progress`, und Segmente tragen `data-done`.

### Testfallen, in Phase 2 gefunden (für Spec und TDD wichtig)
- `compare_new_lock_engine_wirkstelle.test.ts:107-108` liest den Zähler per Regex aus dem HTML: `data-testid="compare-editor-progress"` … `<span class="mono"…>TEXT</span>`, auf dem Handy zusätzlich `</span>\s*</div>` direkt danach. Der Baustein muss den Zähler deshalb als `<span class="mono">` als **letztes Kind** des Testid-Containers rendern. Sonst wird der Test rot, obwohl die Funktion stimmt. Alternative: den Test im Zuge von S2b auf Segment-/Testid-Abfrage umstellen. Ich empfehle, das Markup kompatibel zu halten.
- `compare_anlege_freischaltung.test.ts:319` zählt 5× `compare-editor-progress-segment`, also muss die Segment-Testid je Segment erhalten bleiben (Desktop). Der Handy-Balken hat heute keine Segment-Testids. Bekommt er welche, dürfen sie **nicht** `compare-editor-progress-segment` heißen, sonst zählt der Test 10.
- `standardwerte_knopf_geteilt.test.ts:130` prüft, dass `compare-editor-standardwerte` im HTML **nach** `compare-editor-progress` steht. Das bleibt so, weil der Fortschritt im Kopf steht und Standardwerte im Fuß.
- E2E `helpers.ts:888-929` nutzt `:visible`. Der Desktop-Testid darf auf dem Handy nicht sichtbar doppelt auftauchen (heute schon durch `tn-desktop`/`tn-mobile` getrennt).
- E2E `issue-682-compare-editor-mobile.spec.ts:78` erwartet `cm-mobile-progress` sichtbar.

### Dependencies
- Upstream: `progressCount` (`shared/anlegeLockEngine.ts:70`), Tokens `--g-accent`/`--g-rule`, i18n `trip.anlegen.nichts_eingerichtet`, `trip.anlegen.abschnitte`
- Downstream: die oben genannten Unit- und E2E-Tests über ihre Testids

### Open Questions
- keine. Die Farbregel ist eine Tech-Lead-Entscheidung, gestützt auf das Kontrast-Leitprinzip und 3 von 4 bestehenden Balken. Die Reiterleiste auf dem Handy bleibt außerhalb des Umfangs, eine Notiz kommt ins Issue.

## Phase 5 (RED) — Vertrag und Hinweise für /50-implement
- RED-Tests legen den Vertrag fest (Kopfkommentar `shared/anlege-rahmen/__tests__/anlege_fortschritt.test.ts`): `steps: readonly string[]`, `done: number` (Ergebnis von `progressCount`), `aktiv?` ohne Optik, `variante`, `testidPrefix`; Segment i erledigt ⇔ i < done; Farbe als Inline-Stil `background: var(--g-accent)` / `var(--g-rule)`; Breite `width: 24px` (desktop) bzw. `flex: 1` (mobil); Zähler `<span class="mono">` letztes Kind.
- Randfall: Mit `done` als Zahl färbt der Balken die ersten n Segmente, auch wenn ein späterer Schritt vor einem früheren erledigt ist. So zeichnen die heutigen Balken auch; bewusst beibehalten.
- Im Worktree fehlte `frontend/node_modules`; Symlink auf das Hauptrepo angelegt (git-ignoriert).

## Phase 6b — Adversary Runde 1: BROKEN (Fix-Loop 1, Auftrag für den Developer)
Protokoll: `docs/artifacts/feature-2837-s2b-fortschritt/adversary-dialog.md`. Kein Funktionsfehler in den ACs, aber:
1. **F003 (Korrektur des RED-Vertrags):** Der Altbestand färbte nach Schritt (`done.has(step)`, HEAD `TripNewEditor.svelte:576/967`, `CompareNewEditor.svelte:470/604`), nicht nach Position. Die Notiz oben „so zeichnen die heutigen Balken auch“ war falsch. Die Spec sagt „geteilt wird nur das Markup“ ⇒ Verhalten muss erhalten bleiben. Fix: `AnlegeFortschritt` bekommt optionale Prop `erledigt?: ReadonlySet<string>`; ist sie gesetzt, gilt Segment i erledigt ⇔ `erledigt.has(steps[i])`, sonst Rückfall `i < done` (bestehende Baustein-Tests bleiben gültig). Rahmen und beide Editoren (Computer und Handy) reichen ihr `done`-Set durch. Neuer Test auf Editor-Ebene: Trip mit Startdatum ohne Namen ⇒ 2. Segment erledigt, 1. nicht; dasselbe sinngemäß für den Vergleich.
2. **F001 (Testlücke):** `TripNewEditor.svelte` Handy `variante="mobil"` → `"desktop"` überlebt. Test in `fortschritt_in_beiden_editoren_gleich.test.ts`: Zählertext für beide Arten × beide Geräte × DE/EN × 0 und 1 erledigt.
3. **F004 (Testlücke):** `aktiv` am Trip-Handy weglassen überlebt. Test: `aria-current="step"` am aktiven Segment auf beiden Geräten beider Arten.
4. **F002 (AC-6):** Handy-Zähler `${done}/${steps.length}` ist hart gebaut; AC-6 verlangt Katalog. Katalogschlüssel (DE und EN) anlegen, z. B. `trip.anlegen.abschnitte_kurz` mit `{n}/{gesamt}`, und verwenden.
Umsetzung F003 (Developer, Fix-Loop 1): Prop `erledigt` umgesetzt; Testfälle: Trip ohne Namen mit besuchten Metriken ⇒ Segment 3, Vergleich ohne Namen mit Metriken ⇒ Segment 3, Vergleich ohne Namen mit 2 Orten ⇒ Segment 2. Korrektur zu Punkt 1: „Trip: Startdatum ohne Namen“ ist kein Beispiel, `route` gilt erst mit Name UND Startdatum als erledigt (`doneTabs`). AC-1 „die ersten erledigten“ ist so zu lesen: die erledigten Schritte in Akzentfarbe; bei der üblichen Reihenfolge sind das die ersten. Golden `f9_trip_flaechen/anlegen_weiter.de.html` hat damit wieder die Farbfolge von vor S2b.
Danach: Goldens `tests/golden/f10_vergleich_flaechen/*.de.html` ggf. neu erzeugen (nur Balken-Diff), GREEN-Output neu, neuer Adversary-Dialog (neues Gerüst per `adversary_dialog.py scaffold`).
