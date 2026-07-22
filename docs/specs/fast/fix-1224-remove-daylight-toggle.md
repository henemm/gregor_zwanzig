# Mini-Spec: #1224 — toten „Tageslicht anzeigen"-Toggle entfernen

- **Status:** Draft
- **created:** 2026-07-22
- **Workflow:** fix-1224-remove-daylight-toggle (Bug fast-track)
- **Issue:** #1224 · **Tech-Lead-Entscheidung:** Option 1 (entfernen), konsistent zu #790/#1208

## Problem

`report_config.show_daylight` ist seit #790 render-wirkungslos (Renderer absorbiert
`daylight` in `**_ignored`); #1208 hat das Feld als RENDER_NEUTRAL bestätigt. Der
Schalter bleibt aber in UI + Modell und der Scheduler berechnet bei
`show_daylight=true` weiterhin `compute_usable_daylight` (tote Berechnung). Klasse
„gespeichert, aber wirkungslos" (#1203).

## Was ändert sich (entfernen)

1. **Frontend:** Den „Tageslicht anzeigen"-Toggle aus den Report-Config-Editoren
   entfernen (`EditReportConfigSection.svelte`, `ReportConfigDialog.svelte`, ggf.
   `types.ts`) — Nutzer sehen keine wirkungslose Einstellung mehr.
2. **Scheduler:** die tote `compute_usable_daylight`-Berechnung (Schritt 7,
   `trip_report_scheduler.py:887-900` + `daylight_window`-Durchreichung) entfernen.
3. **Renderer:** die tote `daylight`-Parameter-Verdrahtung in
   `trip_report.py` (Import, Parameter, Weitergabe) entfernen; tote
   `_format_daylight_html/plain` (falls vorhanden) entfernen.
4. **Resolver:** `show_daylight` aus dem RENDER_NEUTRAL-Set von
   `report_config_resolver.py` entfernen.
5. **daylight_service.py:** nur entfernen, wenn nach 1–4 **kein** Nutzer mehr
   übrig ist (grep-verifiziert); sonst belassen (Blast-Radius begrenzen).

## Was darf sich NICHT ändern / kein Datenverlust

- **Gespeicherte Trips bleiben ladbar:** `show_daylight` im Modell/Loader darf als
  toleriertes Alt-Feld bestehen bleiben (Read-Modify-Write, kein Replace) ODER
  sauber entfernt werden — aber ein Trip-JSON mit `show_daylight` MUSS weiterhin
  ohne Fehler laden (unbekannte Keys tolerieren).
- Kein anderes Report-Config-Verhalten ändert sich (Vertragstest #1208 grün).
- Versand-Mail-Inhalt unverändert (Tageslicht war schon seit #790 nicht drin).

## Acceptance Criteria

- **AC-1:** Given ein Trip, When das Briefing gerendert/versendet wird, Then ist der
  Ablauf frei von der Tageslicht-Berechnung (kein `compute_usable_daylight`-Aufruf,
  kein `daylight`-Parameter-Pfad) und die Mail-Ausgabe ist unverändert.
- **AC-2:** Given der Report-Config-Editor im Frontend, When er geöffnet wird, Then
  erscheint KEIN „Tageslicht anzeigen"-Toggle mehr.
- **AC-3 (kein Datenverlust):** Given ein bestehendes Trip-JSON mit
  `report_config.show_daylight`, When es geladen wird, Then lädt es ohne Fehler
  (Alt-Feld toleriert), keine anderen Felder gehen verloren.
- **AC-4 (Test):** Given der Fix, Then belegt ein Test AC-1 (kein Tageslicht-Pfad,
  Mail unverändert) und der #1208-Resolver-Vertragstest bleibt grün; Frontend-Test
  belegt das Fehlen des Toggles.

## Manuelle Test-Schritte / Staging

- Staging: Report-Config-Editor eines Trips öffnen → kein Tageslicht-Toggle;
  Test-Mail rendern → `briefing_mail_validator.py` Exit 0, Inhalt unverändert.
