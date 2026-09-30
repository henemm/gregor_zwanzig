# Adversary-Dialog feature-2155-s4-admin-ui (Issue #2155 S4) -- Runde 2 (ersetzt Runde 1)

Testlauf: docs/artifacts/feature-2155-s4-admin-ui/adversary-test-output.txt (spec-Reporter):
54 tests, 54 pass, 0 fail (Import-Guard #470, admin_hilfen, admin_seite_zugriff,
admin_seite_render_und_dialogfluss, admin_nav_nur_fuer_admin).
Mutationen: 62 per String-Ersetzung, Sicherung im Scratchpad (r2bak), nach jeder Mutation Diff = identisch,
Status-Abgleich des Arbeitsbaums vor/nachher identisch.

## Runde 1 -- Refactor-Verhaltensgleichheit (Code gelesen)
admin/+page.svelte vs. Spec Punkt 5/6: Sperren-Klick -> askDisable setzt nur confirmId (kein Senden);
Abbrechen oder Schliessen des Dialogs ruft cancelDisable (null, kein Senden). Bestaetigen ruft
confirmDisableAction und dann send mit disabled=true. Entsperren ruft enableAction direkt ohne Dialog.
disableBlocked(u.id, data.selfId, busy) deaktiviert das eigene Konto. Fehler: Ergebnis-Helfer laesst
users unveraendert, Klartext an der Zeile. Tier-Select springt per tierSelectValueAfter zurueck.
ConfirmDialog.svelte: Confirm-Button ruft NUR onConfirm (kein onOpenChange davor) -> confirmId ist beim
Bestaetigen noch gesetzt, kein Wettlauf. Imports: nur atoms + molecules/ConfirmDialog (Guard gruen).
Nur DTO-Felder gerendert. BottomNav unveraendert.
=> Verhalten gegenueber Spec durch den Refactor nicht veraendert. Kein Spec-Bruch gefunden.

## Mutations-Tabelle
ROT durch den gemeinten Test: m01-m06, m09 (admin_nav_nur_fuer_admin: Sidebar/Layout/Load),
m03 (KontoSheet isoliert), m04/m05 (layout.server), m10/m11/m12 (Rolle/Reihenfolge/Profil-null:
Test "Nicht-Admin: load() wirft 403 und ruft die Nutzerliste NICHT ab"), m13/m14 (Liste 401/403/500),
m15 (selfId), m16/m17 (Endpunkt/Cookie), m18-m20 (400/403/404-Texte), m22/m23/m25 (Pfad/Methode/Encoding),
m26 (alle Zeilen ersetzt), m27/m28 (TIER_LABELS), m29/m30, m31/m32/m33 (Dialog-Zustandsfunktionen),
m34-m39 (sendAdminUpdate und Ergebnis-Helfer), m43 (disableBlocked in der Seite: SSR-Test
"eigene Zeile: Sperren-Button ist deaktiviert"), m49 (Antrag-Hervorhebung), m59 (lokale TIER_LABELS),
m60 (Sperr-Badge).
Zufalls-Rot-Pruefung: bei m20/m26/m27 reissen Nachbartests mit, der gemeinte Test ist jeweils dabei.

UEBERLEBEND (kein Test rot):
- m07, m08: +layout.svelte reicht isAdmin an KontoSheet fest true bzw. gar nicht durch.
- m40, m41, m42, m44: Handler sendet Sperren ohne Dialog, Abbrechen sendet, Entsperren sendet
  disabled=true, Bestaetigen umgeht den Helfer.
- m45, m46, m47, m48, m58: Seite loescht Fehlerliste, Tier-Payload-Feld level statt tier, Select springt
  nicht zurueck, Tier-Handler sendet an /disabled, busy nie gesetzt.
- m53, m54, m55, m56: ConfirmDialog-Verdrahtung (onOpenChange, onCancel, onConfirm, open).
- m50, m51, m52, m57, m61, m62: Render-Felder: Fehlerzeilen-testid, tierLabel-Fallback, "kein Lauf" bei null,
  E-Mail-Anzeige, Select-value aus u.tier, Dialog-Hinweis "Sitzungen enden".
- m21 (409 ohne code-Pruefung), m24 (Content-Type-Header entfernt).

## Findings
Finding:
  ID: F001
  Severity: MEDIUM
  Category: edge_case
  Code reference: frontend/src/routes/admin/+page.svelte:66-96
  Description: Die Svelte-Handler (makeAskDisable, makeEnable, onCancelDisable, confirmDisable, makeTierHandler,
    send) und die ConfirmDialog-Verdrahtung (Z. 158-171) sind im Kern-Test nur ueber die reinen Helfer bewacht.
    15 Mutationen (m40-m42, m44-m48, m53-m56, m58) ueberleben, z. B. Sperren ohne Dialog (m40), Abbrechen
    sendet (m41), Tier-Payload level statt tier (m46), Tier-Aufruf an /disabled (m48).
  Spec requirement: AC-4/AC-5/AC-6 -- Dialog vor Sperren, Abbrechen sendet nichts, Entsperren ohne Dialog,
    Fehler => Zeile unveraendert; Tier-Payload mit Feld tier.
  Conflict: Zusicherung an der Helfer-Stelle geprueft, nicht dort, wo sie wirkt (Handler im Browser).
    Im Kern nicht messbar. Bewacht nur die Staging-Playwright-Spec frontend/e2e/admin-nutzerverwaltung.staging.spec.ts
    (AC-5 ab Z. 171 prueft Abbrechen => 0 Anfragen); in dieser Runde NICHT ausgefuehrt.
    Status: NOT_MEASURABLE_ON_STAGING (AC-5, AC-9) -- nicht als PASS werten.
  Remediation: /e2e-verify mit gz-staging-admin muss AC-5, Tier aendern und 409-Text bestehen.

Finding:
  ID: F002
  Severity: MEDIUM
  Category: edge_case
  Code reference: frontend/src/routes/+layout.svelte:282
  Description: isAdmin-Weitergabe an KontoSheet (mobil) ungetestet: m07 (fest true) und m08 (entfernt)
    ueberleben. Der Layout-Test prueft nur die Sidebar, KontoSheet wird nur isoliert gerendert.
    Folge: Nicht-Admin koennte mobil den Admin-Link sehen (Komfort-Leck, Go bleibt Sperre) bzw. Admin nie.
  Spec requirement: AC-1 -- Eintrag auch im Konto-Sheet, Nicht-Admin an keiner Stelle.
  Conflict: Durchreichung Layout nach KontoSheet nicht an der wirksamen Stelle geprueft.
    NOT_MEASURABLE_ON_STAGING (Browser-Spec Z. 83/89 prueft konto-sheet-admin, nicht ausgefuehrt).
  Remediation: Layout-Test mit geoeffnetem Konto-Sheet oder Live-Spec laufen lassen.

Finding:
  ID: F003
  Severity: MEDIUM
  Category: edge_case
  Code reference: frontend/src/routes/admin/+page.svelte:107-147
  Description: Zeilen-Render (AC-3) nur teilbewacht. Ueberlebend: m52 (kein Lauf wird leer, die einzige
    SSR-Fixtur hat last_trip_report_run=null, der Text wird nie geprueft), m57 (E-Mail entfernt),
    m61 (Select-value nicht aus u.tier), m51 (tierLabel-Fallback), m50 (testid Fehlerzeile),
    m62 (Sitzungen-enden-Hinweis im Dialog).
  Spec requirement: AC-3 -- je Zeile Kennung, E-Mail, Tier, Sperrstatus, letzter Lauf (null => kein Lauf);
    AC-5 Hinweis, dass Sitzungen enden.
  Conflict: SSR-Test prueft Hervorhebung, Badge, Buttons, nicht E-Mail oder Lauf-Text. Live-Spec Z. 129
    prueft nur eine sehr weite Regex (kein Lauf oder zwei Ziffern).
  Remediation: SSR-Assertions auf E-Mail, kein Lauf (null-Fixtur) und Zeit+Status (nicht-null-Fixtur).

Finding:
  ID: F004
  Severity: LOW
  Category: edge_case
  Code reference: frontend/src/lib/admin.ts:21
  Description: m21: 409 mit beliebigem Code liefert ebenfalls den Selbstsperr-Text, kein Test mit 409 und
    anderem Code. m24: Content-Type-Header unbewacht (Go dekodiert ohne Header-Pruefung,
    internal/handler/admin_users.go:113 und :144, daher aktuell wirkungslos).
  Spec requirement: AC-6 -- Text nur fuer 409 cannot_disable_self.
  Conflict: Falsch-positive Meldung bei kuenftigem anderen 409 ungeprueft.
  Remediation: Test "409 mit anderem Code => allgemeine Meldung" (Sammel-Eintrag #1199 genuegt).

## Confirmations
AC-2 CONFIRMED -- admin/+page.server.ts:13-14 (Rolle vor Listenabruf), m10-m14 und m17 rot durch
  admin_seite_zugriff. Go-403 selbst: S3.
AC-3 (Datenform) CONFIRMED, Render teilweise, siehe F003.
AC-4 (Helfer) CONFIRMED -- lib/admin.ts:32, m26/m34/m35/m38 rot. Browser-Teil siehe F001.
AC-6 CONFIRMED (Helfer) -- lib/admin.ts:10-19, m18-m20/m39 rot. Praezision siehe F004.
AC-7 CONFIRMED -- lib/admin.ts:5-9, account/+page.svelte:14, m27/m28/m59 rot.
AC-8 CONFIRMED -- Import-Guard gruen, Seite importiert nur atoms und molecules.
AC-1 PARTIAL -- Sidebar, layout.server, KontoSheet isoliert CONFIRMED (m01-m06, m09 rot). Durchreichung
  Layout nach KontoSheet siehe F002. Browser: NOT_MEASURABLE_ON_STAGING.
AC-5 NOT_MEASURABLE_ON_STAGING -- Helfer bewacht (m31-m33), Handler und Dialog siehe F001.
AC-9 NOT_MEASURABLE_ON_STAGING -- Live-Spec vorhanden, nicht ausgefuehrt.

## Runde 2 (Gegenpruefung)
Runde-1-Findings (Nav, Dialogfluss/Selbstschutz, Load-Zweige): Nav-Load, Sidebar, Selbstschutz-Render und
alle Load-Zweige sind jetzt rot geprueft (m01-m17, m29, m43). Die 6 vom Developer genannten Browser-Only-
Mutationen sind bestaetigt (a5 = m07/m08, g/h-svelte = m40-m42 und m44-m48). Neu, vom Developer nicht genannt:
m50-m52, m53-m58, m61, m62, m21, m24 (F001, F003, F004). Kein Rot war zufaellig der falsche Test.

═══════════════════════════════════════
VERDICT: AMBIGUOUS
═══════════════════════════════════════
Kern-Logik (Load, Helfer, Sidebar, Selbstschutz-Render) wirksam bewacht, Refactor verhaltensgleich zur Spec.
Offen: Handler/Dialog-Verdrahtung und Konto-Sheet-Durchreichung nur per Staging-Playwright messbar
(NOT_MEASURABLE_ON_STAGING, nicht ausgefuehrt), AC-3-Render-Felder teilbewacht (F003).
Tests: 54 passed, 0 failed
Recommendation: /e2e-verify mit Live-Spec als Pflichtnachweis fuer AC-1/5/9, F003 optional im Kern nachziehen.

## Geprüfte Dateien

- sha256:e2d924ddff684490662ab2a93fc7e653fe8011e05d7f125a7549729af88df206  frontend/src/lib/admin.ts
- sha256:bce9573afdccd7e592e56988fd2ff6f0251763827dbd292230aee370fea760cc  frontend/src/routes/+layout.svelte
- sha256:b88fd4e4e993f79f573d2d629d4c1718fb86fc0d3370470256810bd88cec0bdb  frontend/src/routes/admin/+page.svelte
