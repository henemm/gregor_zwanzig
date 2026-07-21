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

## Nachtrag (2026-07-06)

Dieser Fix hat `EditReportConfigSection` vollständig aus `WeatherMetricsTab.svelte` entfernt
und damit ungewollt auch die E-Mail-Inhalt-Karte (Ausblick/Etappen-Kennzahlen/
Vortagesvergleich/Format-Schalter) aus dem Inhalt-Reiter entfernt — entgegen AC-2 aus
`docs/specs/modules/issue_736_tabs_reorg.md`, wonach die Karte dort sichtbar bleiben sollte.
Durch Fix #1047 (`docs/specs/modules/fix_1047_mail_content_tab_restore.md`) wurde die Karte
über eine neue `showSchedule`-Prop gezielt wieder eingebunden, ohne die hier beschriebenen
Zeitplan-Karten zurückzubringen.
