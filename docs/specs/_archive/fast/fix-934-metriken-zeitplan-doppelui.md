# Mini-Spec: fix-934 — Doppel-UI Wetter-Metriken / Briefing-Zeitplan

## Was ändert sich

- `WeatherMetricsTab.svelte`: `EditReportConfigSection` wird im createMode
  (`{#if !createMode}`) ausgeblendet — die Zeitplan-Maske (Morgen-Report,
  Abend-Report, E-Mail-Inhalt) gehört im Anlegen-Wizard nur in den Zeitplan-Tab
- Damit gibt es nur noch eine einzige `EditReportConfigSection`-Instanz im
  Anlegen-Fluss → keine getrennten Zustände mehr, kein Datenverlust beim
  Tab-Wechsel

## Was darf sich nicht ändern

- Im normalen Trip-Bearbeiten-Modus (`createMode=false`) bleibt
  `EditReportConfigSection` in `WeatherMetricsTab` vollständig sichtbar
- Kanal-Propagation via `onChannelsChange` bleibt unberührt
- Save-Bar-Logik (`!createMode`-Checks aus bea3f9de) bleibt erhalten —
  war bereits korrekt

## Manuelle Test-Schritte

1. `/trips/new` öffnen → Wetter-Metriken-Tab: **keine** Morgen/Abend-Report-Karten sichtbar
2. Zeitplan-Tab: Morgen-Report, Abend-Report, Kanäle, E-Mail-Inhalt vorhanden
3. Zeitplan-Tab: Morgen-Report deaktivieren → Metriken-Tab öffnen → zurück zum
   Zeitplan-Tab → Einstellung noch gespeichert (kein Reset)
4. Bestehenden Trip bearbeiten → Wetter-Metriken-Tab: `EditReportConfigSection`
   weiterhin sichtbar (createMode=false)

## Acceptance Criteria

**AC-1:** Given `/trips/new` ist offen / When Wetter-Metriken-Tab angeklickt / Then sind Morgen-Report- und Abend-Report-Karten NICHT sichtbar (createMode-Guard wirkt)

**AC-2:** Given `/trips/new` ist offen / When Zeitplan-Tab angeklickt / Then sind Morgen-Report, Abend-Report, Kanäle und E-Mail-Inhalt sichtbar

**AC-3:** Given Zeitplan-Tab mit Morgen-Report deaktiviert / When Wetter-Metriken-Tab und zurück zum Zeitplan-Tab / Then ist die Deaktivierung noch gespeichert (kein State-Reset)

**AC-4:** Given bestehender Trip im Bearbeiten-Modus / When Wetter-Metriken-Tab geöffnet / Then Morgen-Report und Abend-Report weiterhin sichtbar (createMode=false unverändert)

## Inline-Test

- [x] Playwright: Im Anlegen-Wizard zeigt Wetter-Metriken-Tab keine `EditReportConfigSection`
