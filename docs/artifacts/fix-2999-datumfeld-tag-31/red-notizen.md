# RED-Notizen #2999 (für /50-implement)

- Vertrag der Kernlogik steht im Kopf von `frontend/src/lib/components/molecules/__tests__/datum_tipp.test.ts`
  (`datumTipp.ts`: `Segment`, `pruefeTipp` → `{ok:true, iso}` | `{ok:false}`, `DatumTipp.taste/laeuft/zuruecksetzen`).
- Staging-Lauf: `cd frontend && npx playwright test --config playwright.2999-datumfeld.staging.config.ts`
  (GZ_VALIDATOR_* aus `.claude/validator.env`, GZ_AUTH_* aus `/home/hem/gregor_zwanzig_staging/.env`, Quotes strippen;
  im Worktree `frontend/node_modules` als Symlink auf den Hauptordner).
- Leere Segmente erkennt der Test an `aria-valuetext="Empty"` (bits-ui setzt kein `data-placeholder`).
- AC-10 ist heute schon rot: nach Kalenderklick 20.11.2026, zweimal Backspace im Tag und „25“ wird 2026-11-02
  gespeichert (der Zwischenstand „2“ geht nach außen). Nach Spec darf bis zum vollständigen Datum nichts gemeldet
  werden; beim Verlassen muss das sichtbare 25.11.2026 gespeichert werden.
- AC-12 (Uhrzeit) ist bewusst grün (Regressionswächter).
