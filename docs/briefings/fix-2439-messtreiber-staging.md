---
spec_file: docs/specs/modules/feat_2439_staging_messtreiber.md
spec_sha256: 17a59e00a41bab6f1b59d012a6cd2d929ad370e7ea4752ab3ac9288a6846e390
spec_frozen_sha256: 09c69e576cafc5d36bba254ea87b576c675237928ea10a7af59ddb1cf30af10e
---

# PO-Briefing: fix-2439-messtreiber-staging

- **Spec:** docs/specs/modules/feat_2439_staging_messtreiber.md
- **Issue:** #2439
- **Erstellt:** 2026-10-22

## Was gebaut wird

Der Messtreiber läuft auf echtem Staging durch den Probelauf, statt an Anmeldung, warmem Cache und gesperrtem Korsika-Abruf zu scheitern.

## Definition of Done

Ein echter Probelauf gegen Staging endet erfolgreich und räumt Testnutzer samt Trips auf.

## Wie geprüft wird

Schnelle Tests mit Attrappen prüfen die Logik; dass es auf echtem Staging klappt, belegt nur der Live-Probelauf.

## Kritische Anmerkungen

- Abweichung: Korsika unter 60 Sekunden mit Météo-France wird nicht mehr auf Staging, sondern erst auf Produktion geprüft; dort noch ungemessen.
- Die Produktionsmessung hat in dieser Spec keinen eigenen Test; Korsika-Zusicherung bleibt bis dahin unbelegt.
- Telegram wird nur bis zur Verarbeitung gemessen, nicht bis zur echten Zustellung; Verknüpfung ist ungetestet.

## Freigabe-Frage

Genehmigst du, dass die Korsika-Zusicherung von Staging auf Produktion verlegt wird?
