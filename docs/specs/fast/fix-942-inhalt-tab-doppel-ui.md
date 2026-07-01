# Mini-Spec: fix-942 — Doppel-UI im Inhalt-Tab entfernen (Edit-Modus)

## Was ändert sich

`WeatherMetricsTab.svelte`: Der `{#if !createMode}`-Block um `EditReportConfigSection`
wird vollständig entfernt. EditReportConfigSection gehört ausschließlich in den
Versand-Tab — weder in createMode noch in edit mode in WeatherMetricsTab.

## Was darf sich nicht ändern

- Versand-Tab zeigt weiterhin alle Zeitplan-Einstellungen (Morgen/Abend-Report, Uhrzeiten, Kanäle)
- Inhalt-Tab zeigt weiterhin alle Wetter-Metriken und sonstigen Einstellungen
- createMode-Logik für alle anderen Elemente in WeatherMetricsTab bleibt unverändert

## Acceptance Criteria

**AC-1:** Given bestehender Trip im Bearbeiten-Modus / When Inhalt-Tab geöffnet und nach unten gescrollt / Then sind Morgen-Report und Abend-Report NICHT sichtbar im Inhalt-Tab

**AC-2:** Given bestehender Trip im Bearbeiten-Modus / When Versand-Tab geöffnet / Then sind Morgen-Report, Abend-Report, Uhrzeiten und Kanäle vollständig sichtbar (unverändert)

**AC-3:** Given /trips/new Wizard / When Wetter-Metriken-Tab besucht / Then zeigt er weiterhin KEINE Zeitplan-Elemente (Regression-Check für #934-Fix bleibt intakt)
