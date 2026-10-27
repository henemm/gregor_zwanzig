# Adversary-Dialog feature-2155-s4-admin-ui (Issue #2155 S4) -- Runde 3 (ersetzt Runde 2)

Testlauf: docs/artifacts/feature-2155-s4-admin-ui/adversary-test-output.txt
(`cd frontend && npm test -- --test-reporter=spec`, Exit 0): 3800 tests, 3795 pass, 0 fail, 5 skipped (Gesamt-Suite Frontend).
Mutationen: 29 eigene per String-Ersetzung, Sicherung je Mutation im Scratchpad, nach jeder Mutation Inhalt == Sicherung,
`git status --short` am Ende identisch zum Start (Produktivcode unberuehrt).
Zielsuite je Mutation: admin_hilfen, admin_seite_zugriff, admin_seite_render_und_dialogfluss, admin_nav_nur_fuer_admin,
admin_nav_konto_sheet_durchreichung, layout_istanlegeseite_bottomnav.

## Mutations-Tabelle

ROT, jeweils durch den gemeinten Test (kein Zufallsrot):
- m01 (+layout.svelte:282 KontoSheet `isAdmin={true}`): ROT durch admin_nav_konto_sheet_durchreichung "Nicht-Admin: kein Admin-Eintrag im Konto-Sheet", "isAdmin fehlt in data", "truthy Nicht-Boolean". F002 aus Runde 2, jetzt geschlossen.
- m02 (Durchreichung an KontoSheet entfernt): ROT durch "Admin: genau ein Admin-Eintrag im Konto-Sheet".
- m03 (`!!data.isAdmin` statt `=== true`): ROT durch "truthy Nicht-Boolean (strikt === true)".
- m04 (beide Stellen fest `true`): ROT durch admin_nav_nur_fuer_admin "Nicht-Admin: kein Admin-Link irgendwo im Layout".
- m05 (KontoSheet.svelte:71 `{#if true}`): ROT, 7 Tests.
- m06 (Sidebar.svelte:39 fest `true`): ROT, 6 Tests.
- m07 (+layout.server.ts:309 `!!profile?.role` statt `=== 'admin'`): ROT durch "Nutzer-Profil => isAdmin false".
- m08 (admin/+page.server.ts:276 Rollenpruefung entfernt): ROT durch "Nicht-Admin: load() wirft 403 und ruft die Nutzerliste NICHT ab".
- m09 (lib/admin.ts:212 `disableBlocked` ohne Selbst-ID-Pruefung): ROT durch "eigene Zeile: Sperren-Button ist deaktiviert".
- m10 (admin.ts:202 Sperr-Aktion an Pfad `tier`): ROT durch "Bestaetigen sendet genau {disabled:true} fuer die gewaehlte ID".
- m11 (admin.ts:207 Entsperren sendet `disabled:true`): ROT durch "Entsperren sendet {disabled:false} direkt, ohne Dialog".
- m29 (Hook-Drift mobile/Sheet.svelte): ROT, und zwar laut (Hook wirft "Muster nicht genau einmal"). Kein Vakuum-Gruen.

UEBERLEBEND (kein Test rot), alles Handler-/Dialog-Verdrahtung in admin/+page.svelte:
- m12 (:64 Sperren-Klick sendet sofort, kein Dialog)
- m13 (:74 Abbrechen sendet `disabled:true`)
- m14 (:58 Tier-Aenderung geht an `/disabled`)
- m15 (:58 Payload `level` statt `tier`)
- m16 (:78 Bestaetigen schliesst den Dialog nicht)
- m17 (:159 `onOpenChange` schliesst nicht)
- m18 (:59 Select springt nach Fehler nicht zurueck)
- m19 (:45 `busy` nie gesetzt)
- m20 (:156 `onConfirm` ruft Abbrechen, sperrt nie)
- m21 (:157 `onCancel` ist ein No-op)
- m22 (:148 Dialog nie offen)
- m23 (:125 Entsperren-Button oeffnet den Sperr-Dialog)
- m24 (:133 Sperren-Button entsperrt direkt)
- m25 (:46 Fehlertext der Zeile wird vor dem Senden nicht geloescht)
- m26 (:79 Bestaetigen sendet an `/tier`)
- m27 (:70 Entsperren sendet `disabled:true`)
- m28 (:116 Tier-Select bei `busy` nicht deaktiviert)

Begruendung: Die Kern-Tests rendern nur SSR und pruefen die reinen Helfer aus lib/admin.ts. Die Svelte-Handler lassen sich im Kern
nicht klicken. Eine Mutation im Handler wirkt nur im Browser und wird nur von der Staging-Playwright-Spec
frontend/e2e/admin-nutzerverwaltung.staging.spec.ts bewacht (AC-5 Z. 171, AC-4 Z. 144, AC-6 Z. 209). Diese Spec wurde nicht
ausgefuehrt; m28, m19 und m25 bewacht sie ohnehin nur indirekt.

## Findings

Finding:
  ID: F001
  Severity: MEDIUM
  Category: edge_case
  Code reference: frontend/src/routes/admin/+page.svelte:44
  Description: 17 von 17 Handler-/Dialog-Mutationen (m12-m28) ueberleben im Kern. Dazu gehoeren Sperren ohne Dialog, Abbrechen
    sendet, Tier-Aufruf an /disabled, Payload `level` statt `tier`, `onConfirm` sperrt nie (Handler Z. 44-80, ConfirmDialog-Verdrahtung
    Z. 147-161). Die Tests bewachen nur die Helfer in lib/admin.ts und das SSR-Render, nicht den Handler, der die Helfer aufruft.
  Spec requirement: AC-4 (nur Zeile ersetzt), AC-5 (Dialog vor Sperren, Abbrechen sendet nichts, Entsperren ohne Dialog), AC-6 (Fehler: Zeile unveraendert).
  Conflict: Zusicherung an der Stelle geprueft, an der der Code steht (Helfer), nicht dort, wo sie wirkt (Klick im Browser).
    Status: NOT_MEASURABLE_ON_STAGING (AC-5, AC-4-Handler, AC-6-Handler), nicht als PASS gewertet.
  Remediation: /e2e-verify mit gz-staging-admin muss AC-4, AC-5 und AC-6 bestehen. Optional: Handler-Logik in lib/admin.ts ziehen
    (fetch und Zustand explizit uebergeben), dann sind m12-m14, m22, m23, m26, m27 im Kern testbar.

Finding:
  ID: F002
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/routes/admin/+page.svelte:116
  Description: m19, m25 und m28 (busy nie gesetzt, Fehlertext bleibt, Select bleibt waehrend der Aktion aktiv, Z. 45/46/116) sind ohne
    Browser unbeobachtbar. Doppelklick waehrend laufender Aktion und veralteter Fehlertext sind ungeprueft.
  Spec requirement: AC-6 (Fehlertext je Zeile), AC-5 (Aktion waehrend Lauf blockiert).
  Conflict: Komfort-/Robustheitsverhalten, keine Datenkorruption; Backend ist idempotent (PUT).
  Remediation: Sammel-Eintrag #1199, sofern F001 nicht per Extraktion behoben wird.

Geschlossen seit Runde 2: F002 alt (Durchreichung Layout nach KontoSheet: m01-m05, m29 rot), F003 alt (Render-Felder im SSR-Test),
F004 alt (409 mit anderem Code: Test "409 mit anderem oder ohne Code => allgemeine Meldung"). Hinweis "Sitzungen enden" im Dialog
(Z. 150): im Kern nicht messbar (bits-ui-Portal), nicht als PASS gewertet, Teil von NOT_MEASURABLE_ON_STAGING fuer AC-5.

## Confirmations
AC-1 CONFIRMED (Kern). Code reference: frontend/src/routes/+layout.server.ts:297 (`isAdmin = profile?.role === 'admin'`, fail-closed);
  Code reference: frontend/src/routes/+layout.svelte:282 (Durchreichung); Code reference: frontend/src/lib/components/ui/sidebar/Sidebar.svelte:39 (Sidebar-Eintrag).
  Code reference: frontend/src/lib/components/ui/sidebar/KontoSheet.svelte:71 (Sheet-Eintrag). Evidenz: m01-m07 und m29 rot durch die gemeinten Tests,
  auch an der Durchreichung im Layout. Konto-Sheet-Hook robust (wirft bei Muster-Drift, Messaufbau-Assert `konto-sheet-export == 1`).
  Code reference: frontend/src/routes/__tests__/konto-sheet-offen.hooks.mjs:1
  Code reference: frontend/src/routes/__tests__/admin_nav_konto_sheet_durchreichung.test.ts:1
  Browser-Teil: NOT_MEASURABLE_ON_STAGING, nicht ausgefuehrt.
AC-2 CONFIRMED. Code reference: frontend/src/routes/admin/+page.server.ts:268 (Rolle vor Listenabruf, 401/403/502 fail-closed);
  Code reference: frontend/src/lib/types.ts:714 (AdminUser). Evidenz: m08 rot. Go-Sperre selbst liegt in S3.
AC-3 CONFIRMED (Datenform und SSR-Render). Code reference: frontend/src/routes/admin/+page.svelte:86 ; AdminUser ohne Geheimnisse.
  Evidenz: SSR-Tests auf E-Mail, "kein Lauf", Zeit plus Status, Select-Wert, Antrag-Hervorhebung, Sperr-Badge.
AC-4 PARTIAL. Code reference: frontend/src/lib/admin.ts:184. Helfer CONFIRMED (Pfad, Methode, Payload, nur Zeile ersetzt).
  Handler: F001, NOT_MEASURABLE_ON_STAGING.
AC-5 NOT_MEASURABLE_ON_STAGING. Code reference: frontend/src/lib/admin.ts:189 (Helfer, m10/m11 rot);
  Handler und Dialog in +page.svelte:62-80 und :147-161 (m12-m27 ueberleben).
AC-6 PARTIAL. Code reference: frontend/src/lib/admin.ts:173. Fehlertexte CONFIRMED, 409 nur mit Code `cannot_disable_self`.
  Anzeige und Zurueckspringen im Handler: F001/F002, NOT_MEASURABLE_ON_STAGING. Selbstschutz-Render CONFIRMED (m09 rot).
AC-7 CONFIRMED. Code reference: frontend/src/lib/admin.ts:166 (zentrale TIER_LABELS), Test admin_hilfen AC-7.
AC-8 CONFIRMED. Code reference: frontend/src/routes/admin/+page.svelte:5 (nur atoms und molecules/ConfirmDialog), Import-Guard #470 gruen.
AC-9 NOT_MEASURABLE_ON_STAGING. Live-Spec frontend/e2e/admin-nutzerverwaltung.staging.spec.ts existiert (AC-1 bis AC-6), nicht ausgefuehrt.

Zitierte Stellen je Datei (eine pro Zeile, fuer den Hash-Block):
Code reference: frontend/src/lib/admin.ts:166
Code reference: frontend/src/lib/types.ts:714
Code reference: frontend/src/routes/+layout.server.ts:297
Code reference: frontend/src/routes/+layout.svelte:282
Code reference: frontend/src/routes/admin/+page.server.ts:268
Code reference: frontend/src/routes/admin/+page.svelte:44
Code reference: frontend/src/lib/components/ui/sidebar/Sidebar.svelte:39
Code reference: frontend/src/lib/components/ui/sidebar/KontoSheet.svelte:71

### Checkliste (Stand dieser Runde; NOT_MEASURABLE_ON_STAGING ist benannt, nicht als PASS gewertet)
- [x] AC-1 Nav-Sichtbarkeit: Kern CONFIRMED (m01-m07, m29 rot); Browser-Teil NOT_MEASURABLE_ON_STAGING
- [x] AC-2 Nicht-Admin serverseitig abgewiesen: CONFIRMED (m08 rot)
- [x] AC-3 Zeilenfelder und Datenform: CONFIRMED (SSR-Tests auf E-Mail, kein Lauf, Zeit+Status, Select, Antrag, Badge)
- [x] AC-4 Tier aendern: Helfer CONFIRMED; Handler NOT_MEASURABLE_ON_STAGING (F001)
- [x] AC-5 Sperren mit Dialog: Helfer CONFIRMED; Handler und Dialog NOT_MEASURABLE_ON_STAGING (F001)
- [x] AC-6 Fehlertexte und Selbstschutz: Texte und Selbstschutz-Render CONFIRMED; Handler-Anzeige NOT_MEASURABLE_ON_STAGING (F001/F002)
- [x] AC-7 zentrale TIER_LABELS: CONFIRMED
- [x] AC-8 Import-Guard: CONFIRMED
- [x] AC-9 Staging-Playwright-Spec: vorhanden, in /e2e-verify als Hard Gate auszufuehren, NOT_MEASURABLE_ON_STAGING benannt

### Runde 1 (Gegenpruefung der Developer-Angabe)
Der Developer meldet 12 rot-geschaltete Mutationen. Unabhaengig bestaetigt: Layout-Durchreichung (m01-m05, m29), Sidebar und
layout.server (m04-m07), Load-Rolle (m08), Helfer (m09-m11) rot durch die gemeinten Tests, kein Zufallsrot. Der Konto-Sheet-Hook
kann den Test nicht vakuum-gruen machen. Nicht bestaetigt: dass damit die Handler-Verdrahtung bewacht waere (17 Ueberlebende).

### Runde 2 (Gegenfrage)
Kann die Helfer-Testabdeckung (m10, m11) die Handler-Verdrahtung ersetzen? Nein, m12-m28 belegen es. Kann der SSR-Test mit dem
Sheet-Hook ein Falsch-Positiv liefern? Nein, m29 und die Messaufbau-Asserts belegen es. Bleibt die Staging-Spec als einzige Wache:
nicht ausgefuehrt, daher AC-4, AC-5, AC-6, AC-9 NOT_MEASURABLE_ON_STAGING und nicht PASS.

═══════════════════════════════════════
VERDICT: AMBIGUOUS
═══════════════════════════════════════
Wirksam bewacht: Nav-Sichtbarkeit inklusive Layout-Durchreichung an das Konto-Sheet, Zugriffsschutz im Load, Helfer,
Selbstschutz-Render, Render-Felder. Offen: F001 (17 ueberlebende Handler-/Dialog-Mutationen), nur per Staging-Playwright messbar.
Empfehlung: /e2e-verify mit gz-staging-admin als Pflichtnachweis fuer AC-4, AC-5, AC-6, AC-9.
Tests: 3795 passed, 0 failed (5 skipped)

## Geprüfte Dateien

- sha256:e2d924ddff684490662ab2a93fc7e653fe8011e05d7f125a7549729af88df206  frontend/src/lib/admin.ts
- sha256:fe4bf06b7feb4a8f0b1b7c9c97103687e90372ef53d2e2e7810850ec2e129e59  frontend/src/lib/components/ui/sidebar/KontoSheet.svelte
- sha256:b0c8332763cf9ef3e0adeacd7f94de4c0c792f58ea65c3cc1b1024ab407a10e1  frontend/src/lib/components/ui/sidebar/Sidebar.svelte
- sha256:e8fbf7f94c9ab46425a99ccc9a30c78b2e9f1e2d19a356fb277ddf442796351b  frontend/src/lib/types.ts
- sha256:77fb0f35cc984bbc9aec3de8a79c46dd73d38df59c0322a07ed8b815d66a8738  frontend/src/routes/+layout.server.ts
- sha256:bce9573afdccd7e592e56988fd2ff6f0251763827dbd292230aee370fea760cc  frontend/src/routes/+layout.svelte
- sha256:f7f45cd8087df582783d4842920a055cf7989d6b5f4943cb85f3239490d84fe1  frontend/src/routes/__tests__/admin_nav_konto_sheet_durchreichung.test.ts
- sha256:9f3d9c62a0294ac243ee6a8d01cef74bd38ca732b8619f4d1839b981fe55f2e6  frontend/src/routes/__tests__/konto-sheet-offen.hooks.mjs
- sha256:247d00461fc3dadc61c28e350b0609bbbc1ac2d7e5408bbc054903ce3f227988  frontend/src/routes/admin/+page.server.ts
- sha256:b88fd4e4e993f79f573d2d629d4c1718fb86fc0d3370470256810bd88cec0bdb  frontend/src/routes/admin/+page.svelte
