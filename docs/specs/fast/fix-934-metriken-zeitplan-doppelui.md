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

## Inline-Test

- [ ] Playwright: Im Anlegen-Wizard zeigt Wetter-Metriken-Tab keine `EditReportConfigSection`
