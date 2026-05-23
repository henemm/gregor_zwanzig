# Context: Issue #336 — Doppelte Status-Anzeige im Tour-Kopf

## Request Summary
Im Tour-Kopf auf `/trips/[id]` erscheint der Status doppelt nebeneinander: als
Großbuchstaben-Text-Präfix ("AKTIV · läuft seit Tag 3") **und** als separate
farbige Pill ("Aktiv"). Eine der beiden Darstellungen soll entfernt/zusammengeführt
werden. Reines Frontend, `priority:low`, Label `design-compliance`.

## Wurzel der Redundanz
`frontend/src/lib/components/trip-detail/TripHeader.svelte`, Z. 81–86:

```svelte
<div class="status-line">
  <span class="status-text status-{status}">
    {statusLabelMap[status]} · {daysLabel}   <!-- "AKTIV" + "läuft seit Tag 3" -->
  </span>
  <TripStatusBadge {trip} {now} />            <!-- grüne Pill "Aktiv" -->
</div>
```

- `statusLabelMap[status]` (lokal in TripHeader, Z. 32–37) liefert die
  Großbuchstaben-Variante: `active→'AKTIV'`, `planned→'GEPLANT'`, `paused→'PAUSIERT'`,
  `archived→'ARCHIVIERT'`.
- `TripStatusBadge` rendert eine `Pill` mit deutscher Titelschreibweise
  (`active→'Aktiv'`, …) und Tone-Mapping (`active→success/grün`).
- Beide leiten denselben Status aus `deriveTripStatus(trip, now)` ab → identische Info.

## Related Files
| Datei | Relevanz |
|------|-----------|
| `frontend/src/lib/components/trip-detail/TripHeader.svelte` | **Kern-Änderung** — Status-Zeile Z. 81–86; lokale `statusLabelMap` Z. 32–37; `.status-text`-Styles Z. 174–182 |
| `frontend/src/lib/components/trip-detail/TripStatusBadge.svelte` | Die farbige Pill (Thin-Wrapper um `Pill`, deutsche Labels, Tone-Map). Bleibt vermutlich erhalten |
| `frontend/src/lib/utils/tripStatus.ts` | `deriveTripStatus()` — Single Source für Status. Unverändert |
| `frontend/src/lib/utils/tripHero.ts` | `getDaysLabel()` liefert den Zusatz ("läuft seit Tag N" / "in N Tagen" / …). Unverändert |
| `frontend/src/routes/trips/[id]/+page.svelte` | Einziger Renderer von `TripHeader` (Z. 110) |

## Existing Patterns
- **Status-Pill ist das etablierte Design-System-Muster** für Status:
  `TripStatusBadge` → `ui/pill/Pill.svelte` mit Tone (success/info/warning/default).
  Auch in der Trips-Liste (#282/#295) wird Status über Pills/Status-Punkte gezeigt.
- Der Text-Präfix in Großbuchstaben stammt aus dem #302-Redesign (Spec §152, §313).
- Statusfarbe wird in der Text-Variante über `.status-{active|planned|…}`-Klassen
  gesetzt (Z. 179–182) — also dieselbe Farbsemantik wie die Pill.

## Dependencies
- **Upstream:** `deriveTripStatus`, `getDaysLabel`, `Pill`, `Btn`, `Eyebrow`.
- **Downstream:** `+page.svelte` (`/trips/[id]`). Keine weiteren Konsumenten.

## Existing Specs
- `docs/specs/modules/issue_302_trip_detail_page.md` — definiert die Status-Zeile.
  - §152 "Statuszeile" + §163: `statusLabel` aus `deriveTripStatus()` ('active'→'AKTIV' …).
  - §313 (Acceptance): *„zeigt die Statuszeile 'AKTIV · TAG N VON M' in Accent-Farbe"*.
  - **→ Wird die Text-Variante geändert, muss diese Spec mitgezogen werden (additive Korrektur-Notiz, #336).**
- Design-System (Autorität): `docs/design-system/` (COMPONENTS.md, COPY.md, ANTI-PATTERNS.md).
  Vor der Entscheidung prüfen, ob es eine Regel "Status nur einmal, als Pill" gibt.

## Tests (Auswirkung)
- `frontend/e2e/trip-detail-hero.spec.ts`
  - **AC-16** (Regressions-Guard) erwartet `trip-detail-status-badge` sichtbar →
    **die Pill muss erhalten bleiben.**
  - `trip-hero-*`-Tests (AC-3/AC-10/…) zielen auf die **alte** `TripHero.svelte`
    (nur noch via Barrel-Export `index.ts` referenziert, **nicht** in `+page.svelte`
    gerendert) — vorbestehend, außerhalb #336-Scope.
- `frontend/e2e/issue-302-trip-detail-redesign.spec.ts`, `trip-detail-actions.spec.ts`,
  `trip-header-btn-migration.spec.ts` — keine direkten Assertions auf den
  `status-text`-Präfix gefunden (grep), in Phase 2 final verifizieren.

## Risks & Considerations
- **Design-Entscheidung gehört dem PO** (Issue: „Entscheidung liegt beim Design/PO").
  Zwei Optionen: (A) Pill behalten, Text-Präfix auf reinen Zusatz reduzieren
  ("läuft seit Tag 3"); (B) Text behalten, Pill entfernen. Vorab-Neigung:
  Option A (Pill = Design-System-Standard, hält AC-16 grün). Endgültige Empfehlung
  + Begründung in Phase 2 / Entscheidung des PO.
- Bei Option A bleibt `getDaysLabel` als alleinige Textquelle — sicherstellen, dass
  der Zusatz auch für `planned/paused/archived` allein sinnvoll lesbar ist
  (z. B. planned: "in 5 Tagen" ohne Präfix — ggf. Pill liefert den Status-Kontext).
- Spec #302 §163/§313 muss bei Option A nachgezogen werden (sonst Spec-Drift).
- Sehr kleiner Diff erwartet (wenige Zeilen + ggf. tote `statusLabelMap`/`.status-*`
  entfernen). Keine Backend-/Daten-Schema-Berührung.

---

## Phase-2-Analyse (Ergebnis)

### Typ
UX-/Design-Compliance-Fix (kein Verhaltens-Bug). Reine Anzeige-Bereinigung.

### Befund — die Entscheidung ist nicht offen
Die im Issue genannte PO-Wahl „A (Pill behalten) vs. B (Text behalten)" kollabiert
nach Prüfung von Tests und Design-System auf **genau eine** korrekte Lösung:

1. **Tests:** `grep` über alle `*.spec.ts`/`*.test.ts` → **kein** Test prüft das
   Versalien-Präfix (`AKTIV`/`status-text`/`statusLabelMap`/`.status-active`).
   Dagegen prüfen **9 Assertions** in `trip-detail-actions.spec.ts` + AC-16 in
   `trip-detail-hero.spec.ts` die Pill `trip-detail-status-badge` (inkl.
   `toContainText('Pausiert')`). → **Die Pill muss bleiben.**
2. **Design-System:** `COPY.md §3 (Status & Zustände)` und `ANTI-PATTERNS AP-020`
   definieren Status ausschließlich über semantische Indikatoren (`<Pill tone>` /
   `<Dot tone>`). Ein Großbuchstaben-Text-Präfix ist **nicht** vorgesehen. → Der
   Text-Präfix ist das nicht-konforme, redundante Element.

→ **Variante B würde 9 Tests brechen UND gegen das Design-System verstoßen.**
Bleibt **Variante A**: Pill behalten, Versalien-Präfix entfernen.

### Empfohlene Umsetzung (Variante A)
In `frontend/src/lib/components/trip-detail/TripHeader.svelte`:
- Status-Zeile rendert nur noch den Zusatz: `{daysLabel}` statt
  `{statusLabelMap[status]} · {daysLabel}`.
- Tote `statusLabelMap`-Konstante (Z. 32–37) entfernen.
- Den Zusatz visuell als **gedämpften Sekundärtext** stylen (`--g-ink-muted`,
  analog `.meta-line`), da die Pill jetzt die Statusfarbe trägt — sonst stünde
  „läuft seit Tag 3" groß in Accent-Orange. Tote `.status-{active|planned|…}`-
  Farbklassen (Z. 179–182) + `status-{status}`-Binding entfernen.
- `<TripStatusBadge>` bleibt unverändert.

### Bewusst NICHT angefasst (Scope-Disziplin)
- `getDaysLabel()` (shared util, auch alte `TripHero`) — bleibt. Für `paused` liefert
  es „pausiert seit N Tagen" neben der Pill „Pausiert" (milder Wort-Wiederholer, aber
  keine echte Doppel-Darstellung; Änderung wäre Scope-Creep).
- `TripStatusBadge`-Darstellung (Pill vs. `Dot+Label` laut COPY.md §3 für „Aktiv")
  — projektweit bereits auf Pill standardisiert (#282/#295). Separate Frage, nicht #336.

### Spec-Nachzug (Pflicht, sonst Doku-Drift)
`docs/specs/modules/issue_302_trip_detail_page.md` §163 + §313 („Statuszeile
'AKTIV · TAG N VON M'") via additiver #336-Korrektur-Notiz anpassen.

### Scope
- **Dateien (Code):** 1 (`TripHeader.svelte`).
- **LoC:** ~ −20/+5 (weit unter 250).
- **Spec/Tests:** 1 Spec-Notiz (#302) + 1 neuer RED-Test (Präfix-Doppelung weg,
  Pill bleibt). Doku zählt nicht zum LoC-Limit.
- **Risiko:** minimal. Keine Daten/Backend. Bestehende Pill-Tests bleiben grün.

### Entscheidungs-Gate
Da Variante A alternativlos ist, kein A/B-Menü. PO-Freigabe erfolgt regulär über die
Spec-Approval (Phase 4).

---

## Status 2026-05-23: IMPLEMENTIERT & VERIFIZIERT — DEPLOY PENDING

- **Code fertig** in `frontend/src/lib/components/trip-detail/TripHeader.svelte` (Variante A
  exakt umgesetzt: Versalien-Präfix raus, `daysLabel` im `trip-detail-status-supplement`-Span,
  `--g-ink-muted`; toter Code + Import entfernt; Pill unverändert).
- **RED→GREEN** über Playwright-Spec `frontend/e2e/issue-336-status-dedup.spec.ts`
  (4 ACs, 5 passed inkl. Setup). Artefakte: `docs/artifacts/issue_336_status_dedup/`
  (red/green-Output + before/after-Screenshots; Verzeichnis ist gitignored = lokale Evidenz).
- **Neutrale Sichtprüfung** (fresh-eyes ohne Bug-Kontext) bestätigt: wörtliche Doppelung weg.
- **Push blockiert** — NICHT durch #336. `pre_commit_gate` fährt die volle Backend-pytest-Suite;
  die ist projektweit rot (veraltete `test_epic_191_*`; #346-Datenlimit bei geosphere/snowgrid;
  `GZ_TEST_PASS`-abhängige Integrationstests). Patt: auch Reparaturen ließen sich nicht committen.
  Gate NICHT umgangen (Harness blockt `pre_commit` in settings.local.json ohnehin).
- **PO-Entscheidung:** bereithalten → Auto-Deploy, sobald die Gesamtsuite grün ist
  (Kern: #346 erledigt + `test_epic_191_*`-Refresh à la #333). Siehe Memory
  `project_precommit_gate_full_suite_block`.

### Resume-Schritte (sobald Suite grün)
1. `uv run pytest --tb=line -q` → grün verifizieren.
2. Nur #336-Dateien stagen + committen: `fix(#336): Doppelte Status-Anzeige im Tour-Kopf entfernt`.
3. Push → ~5 Min Staging-Auto-Deploy → Staging-Smoke + visuelle Prüfung Tour-Kopf → `deploy-gregor-prod.sh`.
4. Issue #336 schließen.
