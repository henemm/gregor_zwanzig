---
entity_id: feat_2794_s3a_reiter_wetter
type: module
created: 2026-11-08
updated: 2026-11-08
status: draft
version: "1.0"
tags: [hub, reiter, wetter, zustellung, ampel, vorlagen, alarm-ab, migration, i18n, epic-2791]
---

# Einstellungen neu S3a: Reiter „Wetter“ und Reiterleiste nach Soll (#2794)

## Approval

- [ ] Approved

## Purpose

Der Hub von Trip und Orts-Briefing bekommt nach ADR-0109 (Akzeptiert) vier Reiter: **Übersicht · Etappen (Trip) bzw. Orte · Wetter · Zustellung**. S3a baut den neuen Reiter **Wetter** und die Reiterleiste nach Atomic-Design-Soll. Im Reiter Wetter stellt der Nutzer an einer Stelle ein, was im Briefing steht, ab welchen Werten die Ampel gelb, orange oder rot färbt und ab welcher Farbe ein Alarm kommt. Er wählt dazu eine Vorlage (7 Systemvorlagen und eigene) und sieht jede Abweichung davon. Die Reiter Wertebereiche, Alarme und der heutige Reiter Wetter-Metriken (mit Layout und Versand) entfallen. Alte Adressen werden umgeleitet.

Damit kein Bedienelement verschwindet, bevor S3b (#2795) die Zustellung neu baut, wird **Zustellung in S3a ein Übergangsreiter** (Variante (a) der Analyse), der die heutigen Alarm- und Versand-Bausteine unverändert aufnimmt.

Entscheidungsgrundlage: ADR-0109 (Reiterstruktur, Akzeptiert 2026-11-08), ADR-0106 (Ampel als Auslöser), ADR-0101 (Ampel-Speicherung, Read-Modify-Write), ADR-0097 (Trip und Orte teilen den Code), ADR-0035 (Tagesfenster), ADR-0104 (zweisprachig), ADR-0095 (Kanal-Parität). Ursprungsanfrage: Issue #2794 (Umfang 1 bis 12, Abgleich-Punkte W1, W4, W5b, A3, A5, A6, K17). Analyse und Befunde: `docs/context/feature-2794-s3a-reiter-wetter.md`. Konzept: `docs/context/einstellungen_neu.md` §4 bis §8, Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html`.

**PO-Entscheidungen 2026-11-08 (AskUserQuestion):**
- **P1:** ADR-0109 angenommen; Zustellung ist bis S3b ein Übergangsreiter mit den heutigen Bausteinen.
- **P2:** Amtliche Warnungen: ein Schalter. Lese-Regel „an, wenn Bericht ODER Alarm an war“, Speichern setzt beide Felder gleich.
- **P3:** Eigene Vorlagen getrennt je Art (`kind` = `route` oder `vergleich`); Bestand ohne `kind` gehört zu Trip; „Als Standard für neue“ exklusiv je Art; Duplikat-Prüfung je Art plus gegen die 7 Systemvorlagen.
- Aus dem Abgleich des Issues: **W1** rein (Lade- und Fehlerzustand), **W4** rein (Rückfrage beim Vorlagenwechsel), **W5b** rein ohne Zeithorizonte (Altwerte per Migration auf „alle Tage“), **A3** rein, **A5** rein, **A6** weg (CAPE geht in der Gewitter-Zeile auf), **K17** rein.

## Source

- **Frontend (produktive Oberfläche):** `frontend/src/lib/components/shared/subscriptionTabs.ts` (einzige Reiter-Definition `REITER_DEFINITION`, `LEGACY`, `resolveTab`, `bereinigteTabAdresse`), `frontend/src/lib/components/trip-detail/TripTabs.svelte`, `frontend/src/lib/components/compare/CompareTabs.svelte`, `frontend/src/lib/components/mobile/MTabBar.svelte`, `frontend/src/app.css`, `frontend/src/lib/components/shared/WeatherMetricsTab.svelte`, `shared/weather-metrics-tab/SavePresetDialog.svelte`, `shared/AlarmeTab.svelte`, `shared/hub-uebersicht/*`, `trip-detail/HubOverview.svelte`, `shared/subscriptionActions.ts`, `frontend/src/lib/i18n/messages/{de,en}/*.json`; neu: `shared/wetter-tab/*`, `shared/zustellung-tab/*`.
- **Go-API:** `internal/handler/metric_preset.go`, `internal/model/metric_preset.go`, `internal/store/metric_preset.go`, `internal/handler/ampel.go`, Anlege-Handler für Trip und Orts-Vergleich (`internal/handler/trip.go`, `briefing_subscription.go`), `internal/router/router.go`.
- **Python-Core:** `api/routers/config.py` (`/api/metrics`, `/api/templates`), `src/app/metric_catalog.py`, `src/app/ampel.py` (`deviation_count`), `src/services/trip_alert.py`, `src/services/compare_alert.py`, `scripts/migrate_2794_preset_horizons.py` (neu).

> **Schicht-Hinweis:** Reiter, Karten, Dialog und Übergangsreiter sind Frontend. Vorlagen-Endpunkte und Eigene-Vorlagen-Store sind Go (`data/users/<id>/metric_presets.json`). Katalog, Abweichungszähler (Referenz) und Alarmquellen-Gate sind Python.
>
> **Trip/Ortsvergleich-Teilung (PFLICHT, #1170, Epic #2345):** Alle neuen Bausteine (Reiter Wetter, Übergangsreiter Zustellung, Vorlage-Karte, Metrik-Zeile, Ampel-Leiste, Grenzen-Editor, Karte Amtliche Warnungen & Radar, Karte Anpassen) liegen unter `shared/` und bekommen `context="route"|"vergleich"`. Es entsteht keine Compare-Komponente mit Trip-Pendant. Compare-eigen bleiben nur Orte-Tab, transponierte Übersicht und Compare-Mail-Template.
>
> **Mandantentrennung:** Jeder datenbewegende Endpunkt (Vorlagen anlegen, ändern, löschen, Standard setzen, Abo-Speichern, Migration) wird mit zwei verschiedenen Nutzern getestet; `user_id` kommt aus dem Auth-Kontext, nie `"default"`.
>
> **Kanäle:** Der Reiter Wetter bestimmt Metrik-Auswahl, Ampel und „Alarm ab“ und wirkt damit in allen vier Kanälen (E-Mail, Telegram, SMS, Premium-SMS) gleich. Inhalt je Kanal und Fläche ist S3b.

## Estimated Scope

- **LoC:** ca. +3000 bis 4500 / −2500 (inkl. Tests)
- **Files:** ca. 60 bis 90 Produktiv-Dateien plus ca. 150 Test-Dateien mit alten Reiter-Kennungen (Umzug)
- **Effort:** high (Risiko hoch: zentrale Reiterdefinition für Hub und Anlegen, Alarm-Gate, Daten-Migration)

## Scope

**In Scope:**
- Reiterleiste nach Soll, vier Reiter, neue Kennungen `wetter` und `zustellung`, Umleitung alter Kennungen, Anlege-Ketten.
- Übergangsreiter Zustellung aus den heutigen Alarm- und Versand-Bausteinen (keine neue Speichermechanik).
- Reiter Wetter vollständig (Umfang 2 bis 9 des Issues), Dialog „Als eigene Vorlage speichern“.
- Backend: Katalog-Felder, Abweichungszähler, Vorlagen (Duplikat, `ampel`, `kind`, Standard), `horizons`-Migration, Alarmquellen-Gate.
- Entfernen von `corridor-editor/`, `AlarmeTab`, `HorizonChips`, `MetricCheckbox`; Übersicht U3/U4, Listen-Sprünge K17, Hilfe-Texte X1, Glossar.

**Out of Scope:**
- **S3b (#2795):** Inhalt je Kanal und Fläche (Roh/Einfach je Liste, Layout je Kanal), Kanal-Tabelle, Dringlichkeit je Kanal neu, „Test schicken“ als neue Funktion. Der Übergangsreiter Zustellung wird dort umgebaut.
- **S8 (#2800):** Radar-Regen-Schalter für Trips. Im Trip erscheint die Radar-Zeile in S3a nicht.
- Ampel für Nullgradgrenze, Schneefallgrenze, Schneehöhe, Nacht (S7 #2799), Kanal-Vorbelegungen (S9 #2801).
- Neue Grenzwerte oder neue Vorlagen: die 7 Systemvorlagen bleiben inhaltlich unverändert (`src/app/ampel_templates.py`).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| S1 #2792 (geschlossen) | Vorarbeit | Ampel-Modell `display_config.ampel`, `resolve_ampel`, `ampel_templates`, Validierung Python und Go |
| S2 #2793 / **S2b PR #2862** | Vorarbeit | Alarm-Auslösung nach Ampel (`alarm_ab`), Migration der Altstufen. **PR #2862 muss vor Teil-PR 3 gemergt sein**, sonst schreibt die Oberfläche `alarm_ab` ohne Wirkung. Nach dem Rebase auf S2b ist zu prüfen, ob `trip_alert.py`/`compare_alert.py` das Gate weiter unverändert lassen (PR #2862 ändert es nach Befund der Analyse nicht) |
| `REITER_DEFINITION`, `LEGACY`, `bereinigteTabAdresse` | Code | eine Quelle für Hub-Leiste und Anlege-Kette |
| `DayWindowCard`, `dayWindowClamp.ts` | Code | Tagesfenster, wiederverwendet (ADR-0035) |
| `alerts-tab/` (`AlertPreviewCard`, `AlertMetricLevelTable`, `AlertMetricChannelsBlock`, `AlertCooldownCard`, `AlertQuietHoursCard`) | Code | leben im Übergangsreiter Zustellung weiter; der Ordner bleibt (anders als im Issue-Punkt 10 angenommen) |
| `mobile_tab_leisten_mtabbar` (Spec) | Spec | mobile Pill-Leiste bleibt |
| `docs/reference/i18n_glossar.md` | Doku | Glossar zuerst ergänzen |
| S3b #2795, S4 #2796, S7 #2799, S8 #2800 | Folgearbeit | bauen auf Reiter und Kennungen auf |

## Implementation Details

### 1. Reiter-Definition und Umleitung

- Eine Definition (`REITER_DEFINITION`) trägt Hub und Anlege-Kette. Neue Kennungen: **`wetter`** und **`zustellung`**.
- **Trip:** `uebersicht`, `etappen`, `wetter`, `zustellung`. **Orte:** `uebersicht`, `orte`, `wetter`, `zustellung`.
- **LEGACY-Umleitung** (`resolveTab`, `bereinigteTabAdresse`): `wetter-metriken`, `wertebereiche`, `layout` → `wetter`; `alarme`, `versand` → `zustellung`. Die Adresse wird bereinigt (kein Rest der alten Kennung in der URL). Der Anker `#versand` landet im Reiter Zustellung.
- **Anlege-Ketten:** `/trips/new` = route, etappen, wegpunkte, wetter, zustellung. `/compare/new` = vergleich, orte, wetter, zustellung. `ANLEGE_SCHWANZ_HINWEIS` und Zähler der Schritte werden angepasst.
- Badges: Etappen bzw. Orte zeigen ihre Anzahl; der bisherige Badge „Wertebereiche = aktive alert_rules“ entfällt.

### 2. Reiterleiste nach Soll

Eine Grundlinie `--g-rule`, Reiter 13px/500, aktiv 600 mit 2px-Unterstrich `--g-accent`, Badges Mono 10px, Radius 3px, neutral `--g-paper-deep` / `--g-ink-3`. `data-slot="segmented"` und `segmented-badge` in `MTabBar.svelte` entfallen, damit die Segmented-Box (`app.css:502-528`) nicht mehr vererbt wird. **Mobil bleibt die Pill-Leiste** (Spec `mobile_tab_leisten_mtabbar`). Soll-Quellen: `claude-code-handoff/current/jsx/{atoms,molecules,screen-trip-detail,screen-compare-detail}.jsx`, `current/soll/*.png`.

### 3. Übergangsreiter Zustellung (Variante (a))

Shared-Komponente mit `context`. Er nimmt die heutigen Bausteine mit ihren heutigen Speicherwegen und Ownern auf. **Inventar, das erhalten bleiben muss** (kein Element verschwindet; Ziel ist der Reiter Zustellung):

1. Alarm-Kanäle und Dringlichkeit je Kanal (AlertChannelPicker)
2. Kanal je Wettergröße (`alert_metric_channels`, `AlertMetricChannelsBlock`)
3. Telegram-Kurzstil
4. Cooldown (`AlertCooldownCard`)
5. Stille Stunden (`AlertQuietHoursCard`)
6. Briefing-Kanäle
7. Morgen/Abend mit Uhrzeit
8. Mehrtages-Trend
9. Laufzeit
10. Aktivieren
11. Mail-Inhalt
12. Layout je Kanal (`channel_layouts`)
13. 3-Tages-Ausblick
14. Nacht-Block
15. Stundenverlauf
16. Beispiel-Warnung (`alerts-tab/AlertPreviewCard`; das neue „Test schicken“ ist S3b, die vorhandene Beispiel-Warnung bleibt bis dahin)

Was aus Alarme nach **Wetter** wandert: Alarmstufe je Metrik (jetzt „Alarm ab“), Amtliche Warnungen, Radar (nur Orte). Die alte Tabelle „Alarm-Empfindlichkeit“ (nach S2b nur lesbar) entfällt mit `AlarmeTab`.

### 4. Reiter Wetter

Aufbau von oben nach unten (Mockup Fassung 3):

1. **Kopf:** „Wetter — Was im Briefing steht, was für dich zu viel oder zu wenig ist und ab wann du einen Alarm bekommst.“ Ladezustand „Lade Metriken …“ mit Platzhaltern. Ladefehler: „Die Metriken konnten nicht geladen werden. Die Verbindung zum Server ist abgebrochen. Deine Einstellungen sind gespeichert und gehen nicht verloren.“ mit Knopf „Erneut laden“ (W1).
2. **Vorlage-Karte:** Picker „{Vorlage} ▾ {n Abweichungen | unverändert}“, darin die Liste „Vorlagen“ (7, je mit Kurzbeschreibung; Metrikzahl und Stichworte aus den Daten abgeleitet, nicht fest im Frontend) und „Eigene“ (nur eigene Vorlagen der passenden Art). Wechsel mit Rückfrage (W4): „‚{neu}‘ übernehmen? Ersetzt Metrik-Auswahl, Ampel-Grenzen und Alarmstufen dieses {Trips|Orts-Briefings}. Deine {n} Abweichungen von ‚{alt}‘ gehen verloren. Zustellung, Etappen und Orte bleiben unverändert.“ [Übernehmen] [Abbrechen]. Ohne Abweichungen entfällt der Verlust-Satz. Knöpfe „Als eigene Vorlage speichern“ und bei Abweichungen „Auf ‚{Vorlage}‘ zurücksetzen“. Vorlagen gibt es auch für Orte (WV4).
3. **„Alarm ab für alle: Nie · Gelb · Orange · Rot“** mit Zähler „{x} von {y} Metriken lösen einen Alarm aus. {z} können keinen auslösen (Vorboten und reine Anzeige).“ Ohne alarmfähige Metrik: „Keine der gewählten Metriken kann einen Alarm auslösen. Nimm z.B. Wind, Böen oder Gewitter dazu.“ (A3, A5). Das Setzen wirkt nur auf alarmfähige Metriken und zählt je geänderter Metrik als Abweichung.
4. **Metrik-Zeilen**, gruppiert nach Temperatur · Wind · Niederschlag & Gewitter · Himmel & Sicht · Schnee & Höhe (Gruppen aus dem Backend-Katalog). Je Zeile: Knopf „−“ („{Metrik} aus dem Briefing nehmen“), Name, Einheit und Hinweis (z. B. „km/h · Spitze“, „Vorbote, kein Alarm“), **Ampel-Leiste** mit Grenzzahlen, Erklärsatz und „grün: …“-Zeile („grün: a bis b {Einheit}“, „grün: ab …“, „grün: bis …“, „immer grün (keine Grenze gesetzt)“), rechts „Alarm ab“ (Segment Nie/Gelb/Orange/Rot mit Farbpunkten) bzw. „kein Alarm (Vorbote)“ / „kein Alarm“, dazu der Knopf **„Grenzen ändern“** / „Fertig“.
   - Aufgeklappt erscheinen nur die erlaubten Seiten (beidseitig, nur oben, nur unten): „unten / zu wenig: rot < · orange < · gelb <“ und „oben / zu viel: gelb > · orange > · rot >“. Hinweis „Grün ist alles zwischen ‚gelb unten‘ und ‚gelb oben‘. Ein leeres Feld heißt: auf dieser Seite keine Grenze. Abweichend von der Vorlage ‚{Vorlage}‘.“ (letzter Satz nur bei Abweichung).
   - Ungültige Reihenfolge wird mit Fehlertext abgelehnt und nicht gespeichert: unten rot < orange < gelb, oben gelb < orange < rot, unten nicht über oben.
   - **Gewitter:** „mittel: gelb · orange · rot“, „hoch: orange · rot“, „‚keins‘ ist immer grün.“ Gewitter kennt kein „Alarm ab Gelb“ (S2 / Go-Prüfung). **Windrichtung:** „keine Ampel, nur Anzeige“, kein Knopf.
   - **Erklärsätze** (alle über den Katalog, DE+EN): Normal „Alarm, wenn der Wert seit dem letzten Briefing über {X} {Einheit} steigt [oder unter {Y} {Einheit} fällt] ({Stufe}), dazu bei sehr großen Sprüngen. Entwarnung, wenn er zurückgeht.“; Gewitter „Alarm, wenn die Gewitter-Stufe seit dem letzten Briefing auf {mittel oder hoch} steigt ({Stufe}). Entwarnung, wenn sie wieder fällt.“ bzw. „Mit diesen Farben erreicht Gewitter nie {Stufe}, daher kein Alarm.“; Nie „Kein Alarm. Die Farbe erscheint nur im Briefing.“; Vorbote „Nur im Briefing gefärbt. Vorboten lösen keinen Alarm aus.“; Anzeige „Nur Anzeige: keine Ampel und kein Alarm. Roh oder Einfach stellst du unten je Liste ein.“; ohne Grenze „Für {Stufe} ist keine Grenze gesetzt, daher kein Alarm.“ Wortlaut wird beim Rebase mit dem S2b-Katalog `alarm.ampel.*` abgeglichen (keine zwei Fassungen derselben Aussage).
   - **Keine CAPE-Zeile** (A6), **keine Aggregationswahl** (fest je Metrik, „Gefühlte Temperatur“ nicht doppelt), **kein Roh/Einfach** in den Zeilen (S3b).
5. **„Nicht im Briefing: + {Metrik} …“** unter den Zeilen. Hinzufügen meldet „{Metrik} ist jetzt im Briefing und steht in allen Listen unter ‚Inhalt je Kanal und Fläche‘. Dort stellst du Roh oder Einfach ein.“ Hinzufügen und Entfernen (−) zählen als Abweichung.
6. **Karte Amtliche Warnungen & Radar:** ein Schalter „Amtliche Warnungen — im Briefing und als Alarm, sobald sie dein Gebiet betreffen“. Lesen: wirksamer Wert = an, wenn Bericht ODER Alarm an war (`official_alerts_enabled` nil oder true bzw. `official_warnings.enabled` true bzw. bei fehlendem Schlüssel Fallback `official_alert_triggers_enabled`, Default an). Speichern setzt `official_alerts_enabled` und `official_warnings.enabled` auf denselben Wert; Renderer und Alarm-Engine bleiben unverändert. Bei Orten zusätzlich „Radar-Regen — Alarm, wenn in der nächsten Stunde Regen auf {deine Orte} zukommt“ (`radar_alert_enabled`); beim Trip erscheint die Radar-Zeile nicht (S8).
7. **Karte „Anpassen“** (eingeklappt): Tagesfenster von–bis (W12, ADR-0035; Trip `report_config.day_window_*_hour`, Orte top-level), bestehende `DayWindowCard`.

**Speichern:** `display_config.ampel` wird per Read-Modify-Write mit Merge geschrieben (ADR-0101): nur Abweichungen von der Vorlage stehen im Abo (`ampel.metrics.<id>` mit `enabled`, `alarm_ab`, Grenzen, `ampel.thunder`, `ampel.template`), nie ein Replace. Bestehende Wege bleiben (Trip: PUT `/api/trips/{id}/weather-config`, dann PUT `/api/trips/{id}`; Orte: bestehender Vergleichs-Speicherweg). Der Frontend-Typ `DisplayConfig` bekommt ein typisiertes `ampel`-Feld. Die Speicher-Schutz-Logik der Hubs (ungespeicherte Änderungen beim Reiterwechsel) gilt für den Reiter Wetter wie für die bisherigen Reiter.

### 5. Dialog „Als eigene Vorlage speichern“ (W5b)

Aufbau auf `SavePresetDialog.svelte`: Name (Pflicht: „Gib der Vorlage einen Namen.“), Beschreibung (optional), Schalter „Als Standard für neue {Trips|Orte}“, Hinweis „Gespeichert werden Metrik-Auswahl, Ampel-Grenzen und Alarmstufen. Zustellung, Etappen und Orte gehören nicht dazu.“ **Keine Zeithorizonte, keine Zusammenfassung.** Gespeichert wird zusätzlich die **`ampel`** (heute schickt der Dialog keine). Duplikat: „Eine Vorlage ‚{n}‘ gibt es schon. Wähle einen anderen Namen.“ Erfolg: „Vorlage ‚{n}‘ gespeichert. Du findest sie unter ‚Eigene‘.“

### 6. Backend

- **Katalog `/api/metrics`** (`api/routers/config.py`, Quelle `metric_catalog.py`, SSOT): neue Felder `group` (`temperature|wind|precip_thunder|sky_visibility|snow_height`, 5 UI-Gruppen), `alertable`, `is_precursor`, `allowed_sides` (`both|upper|lower|level`; `null` in der Vorlage heißt „offen“, nicht „Seite verboten“), `display_only` (z. B. Windrichtung). Kurzbeschreibung und Metrikzahl der Vorlagen kommen aus den Vorlagen-Daten (`/api/templates`). Keine Frontend-Kopie dieser Eigenschaften.
- **Abweichungszähler:** Python-Referenz `deviation_count` in `src/app/ampel.py` zählt zusätzlich `enabled`, `alarm_ab`, Metrik +/− gegenüber der Vorlage und die Gewitterfarbe (heute nur Grenzen und Gewitter; kein Produktiv-Aufrufer). Das Frontend spiegelt die Zählung für sofortige Anzeige beim Bearbeiten. **Parität** über gemeinsame JSON-Fixtures, die von pytest und `node --test` gelesen werden.
- **Alarmquellen-Gate** (`trip_alert.py:685-706`, `:1187-1219` und `compare_alert.py` nach Stand von `origin/main` @ b48afb378; nach Rebase auf S2b neu verorten): Ein Abo mit mindestens einer **aktiven** Metrik mit `alarm_ab` ≠ `never` in der aufgelösten Ampel gilt als alarmfähig (Trip und Vergleich). Bestehende Gate-Fälle bleiben.
- **Eigene Vorlagen (Go):** Duplikat ohne Beachtung der Groß-/Kleinschreibung je Art und gegen die 7 Systemvorlagen, bei POST **und PATCH** (heute nur eigene und PATCH ungeprüft); neues Feld `kind` (`route|vergleich`, Bestand ohne `kind` wird als `route` gelesen, Lese-Default und Migration); `ampel` wird gespeichert und mit der bestehenden Go-Ampel-Prüfung validiert; `is_default` exklusiv je Art (Setzen entfernt das Flag bei den anderen Vorlagen derselben Art) und **bei Neuanlage von Trip bzw. Orts-Vergleich tatsächlich angewendet** (heute nirgends). `summary` und `horizons` entfallen im Dialog.
- **Migration** `scripts/migrate_2794_preset_horizons.py`: Altwerte `horizons` je Metrik in `data/users/<id>/metric_presets.json` auf „alle Tage“. Wie `migrate_2792/2793`: `--root` Pflicht, `--backup-dir`, ohne `--execute` Probelauf, tar.gz je Nutzer vor dem Schreiben (Pre-Snapshot, Hook `data_schema_backup.py`), Read-Modify-Write mit Merge unter Sperre, idempotent (zweiter Lauf „Nichts zu tun“), Bericht je Datei.

### 7. Entfernen und Nachziehen

- **Entfernen:** `frontend/src/lib/components/shared/corridor-editor/`, `shared/AlarmeTab.svelte` samt `alarme-tab/*` und `trip-detail/AlarmeScheduleTab.svelte` (lebende Bausteine ziehen nach `zustellung-tab/` bzw. bleiben in `alerts-tab/`), `molecules/HorizonChips.svelte` (inkl. Barrel-Export), `trip-detail/MetricCheckbox.svelte`. **`alerts-tab/` bleibt.**
- **Übersicht:** Karte „Wertebereiche“ zielt auf Wetter (U3); „Alarm bei Δ“ wird ein Text über „Alarm ab“ (U4) (`hubUebersichtModell.ts`, `HubUebersicht.svelte`, `HubOverview.svelte`).
- **Listen und Hilfe:** Listen-Eintrag „Alarme“ in `subscriptionActions.ts`, `routes/trips/+page.svelte`, `routes/compare/+page.svelte`, `routes/+page.svelte` springt auf den neuen Reiter (K17); Verweise auf alte Reiter in `routes/hilfe`, `infoboxKeys.ts`, Onboarding und Katalogen (X1).
- **Texte:** Neue und geänderte Texte nur über den Katalog (`de` und `en`, neue Dateien für Wetter und Zustellung, bestehende Verweise in `layout.json`, `hilfe.json`, `alarme.json`, `bausteine.json`, `vergleich.json`, `trip.json`, `aktionen.json` nachziehen). **Glossar zuerst** (`docs/reference/i18n_glossar.md`): Wetter, Vorlage, Ampel, Grenzen ändern, Alarm ab, Nicht im Briefing; der Eintrag „Wertebereiche = target ranges“ entfällt. Protokoll-Token werden nicht übersetzt (ADR-0104).

## Lieferung in 4 Teil-PRs (Reihenfolge verbindlich, Zuordnung der ACs)

| Teil-PR | Inhalt | ACs |
|---|---|---|
| **1 Backend** | Katalog-Felder, Abweichungszähler (Referenz und Fixtures), Vorlagen (Duplikat, `ampel`, `kind`, Standard), `horizons`-Migration, Zwei-Nutzer-Tests; Alarmquellen-Gate erst nach Rebase auf S2b | AC-22 bis AC-27, AC-29 |
| **2 Leiste und Umleitung** | Reiterleiste nach Soll, Kennungen und Umleitungen, Anlege-Ketten, Übergangsreiter Zustellung, Testumzug der Kennungen, Seitenüberschrift nach Soll | AC-1 bis AC-8, AC-36 |
| **3 Reiter Wetter** (erst nach Merge **PR #2862**) | Reiter Wetter, Dialog, Alarmquellen-Gate falls in 1 noch offen | AC-9 bis AC-21, AC-28, AC-30 |
| **4 Entfernen und Nachziehen** | Entfernen der Altkomponenten, Übersicht, Listen-Sprünge, Hilfe-Texte, Glossar, Fresh-Eyes gegen Mockup | AC-31 bis AC-35 (AC-33 und AC-34 teilweise schon in 2 und 3, Texte je Teil-PR über den Katalog) |

Zwischen den Teil-PRs bleibt jeder Stand lauffähig: PR 2 liefert Wetter vorläufig über die bestehende Metrik-Oberfläche in der neuen Kennung `wetter`, bis PR 3 sie ersetzt; PR 3 löscht diese Altoberfläche erst, wenn der neue Reiter sie vollständig abdeckt. Jeder Teil-PR hat eigene CI (6 Checks), eigenes Staging und `/e2e-verify`.

## Expected Behavior

- **Input:** Aufruf von Hub oder Anlege-Kette, auch über alte Adressen; Bedienung des Reiters Wetter; Anlegen, Ändern und Löschen eigener Vorlagen.
- **Output:** vier Reiter nach Soll; Reiter Wetter mit Vorlage, Ampel-Grenzen, „Alarm ab“, Warnungen, Tagesfenster; gespeicherte `display_config.ampel` nur mit Abweichungen; Alarme, die zur Oberfläche passen.
- **Side effects:** Migration der `horizons` in Vorlagen-Dateien (Sicherung je Nutzer); `kind` und `is_default` in Vorlagen; beide Felder der Amtlichen Warnungen gleich gesetzt.

## Acceptance Criteria

### Teil-PR 2: Reiterleiste, Umleitung, Übergangsreiter

- **AC-1:** Given ein Trip / When der Nutzer den Hub öffnet / Then stehen genau die Reiter Übersicht · Etappen · Wetter · Zustellung in der Leiste (kein Reiter Wertebereiche, Alarme oder Wetter-Metriken), auf Deutsch und auf Englisch
  - Test: Playwright auf Staging, Reiter-Liste je Sprache; `node --test` auf `REITER_DEFINITION` (Trip) ohne Mocks.

- **AC-2:** Given ein Orts-Briefing / When der Nutzer den Hub öffnet / Then stehen genau die Reiter Übersicht · Orte · Wetter · Zustellung in der Leiste, der Badge am Reiter Orte zeigt die Zahl der Orte
  - Test: Playwright auf Staging mit einem Orts-Vergleich mit drei Orten; `node --test` auf die Definition (Vergleich).

- **AC-3:** Given der Hub eines Trips oder Orts-Briefings am Desktop / When der Nutzer die Leiste ansieht / Then hat sie genau eine Grundlinie, der aktive Reiter ist 600 stark mit 2px-Unterstrich in der Akzentfarbe, und Badges sind kleine neutrale Mono-Marken (keine orangen Kreise, keine Segmented-Box)
  - Test: Playwright mit gemessenen Stilen (Unterstrich-Höhe, Badge-Hintergrund, kein `data-slot="segmented"` an der Leiste) plus Fresh-Eyes-Abgleich gegen `current/soll/*.png`.

- **AC-36:** Given der Hub eines Trips und eines Orts-Briefings am Desktop (Breite ≥ 1024 px) / When der Nutzer den Seitenkopf ansieht / Then hat die Seitenüberschrift (h1) eine berechnete Schriftgröße zwischen 30 und 38 px (Soll Atomic Design, heute 20 px), in beiden Kontexten aus demselben Kopf-Baustein; mobil bleibt die Überschrift im Soll der mobilen Kopfzeile
  - Test: Playwright auf Staging misst `getComputedStyle(h1).fontSize` je Kontext am Desktop und im Mobil-Viewport; Fresh-Eyes-Abgleich gegen `current/soll/*.png`.

- **AC-4:** Given ein Mobilgerät (schmale Breite) / When der Nutzer einen Hub öffnet / Then zeigt die Leiste weiter die Pill-Form mit denselben vier Reitern und alle vier sind erreichbar
  - Test: Playwright im Mobil-Viewport, vier Reiter antippbar; Pill-Stil unverändert (bestehender MTabBar-Test bleibt grün).

- **AC-5:** Given Lesezeichen mit den alten Adressen / When `?tab=wetter-metriken`, `?tab=wertebereiche` oder `?tab=layout` geöffnet wird / Then landet der Nutzer im Reiter Wetter, und bei `?tab=alarme` oder `?tab=versand` (auch `#versand`) im Reiter Zustellung, jeweils für Trip und Orts-Briefing, und die Adresszeile zeigt danach die neue Kennung
  - Test: Playwright-Tabelle aller fünf alten Kennungen je Trip und Vergleich; `node --test` auf `resolveTab`/`bereinigteTabAdresse`.

- **AC-6:** Given der Nutzer legt einen Trip über `/trips/new` bzw. ein Orts-Briefing über `/compare/new` an / When er durch die Schritte geht / Then lauten die Schritte beim Trip Route · Etappen · Wegpunkte · Wetter · Zustellung und bei Orten Vergleich · Orte · Wetter · Zustellung, kein Schritt führt auf einen entfallenen Reiter, und der angelegte Trip bzw. Vergleich ist danach vollständig gespeichert
  - Test: Playwright auf Staging, beide Anlege-Ketten bis zum Speichern; Datei-/API-Zustand des neuen Abos.

- **AC-7:** Given ein Trip mit gesetzten Alarm- und Versand-Einstellungen vor dem Umbau / When der Nutzer den Reiter Zustellung öffnet / Then ist jedes der 16 Bedienelemente aus dem Inventar (Alarm-Kanäle und Dringlichkeit je Kanal, Kanal je Wettergröße, Telegram-Kurzstil, Cooldown, Stille Stunden, Briefing-Kanäle, Morgen/Abend mit Uhrzeit, Mehrtages-Trend, Laufzeit, Aktivieren, Mail-Inhalt, Layout je Kanal, 3-Tages-Ausblick, Nacht-Block, Stundenverlauf, Beispiel-Warnung) vorhanden, zeigt seinen gespeicherten Wert, und das Gleiche gilt im Orts-Briefing für die dort vorhandenen Elemente
  - Test: Playwright auf Staging, Bedienelement-Liste je Kontext gegen das Inventar (festgeschrieben als Testdaten, abgeleitet aus dem Stand vor dem Umbau).

- **AC-8:** Given der Reiter Zustellung / When der Nutzer einen Wert ändert (z. B. Cooldown, Stille Stunden, Briefing-Uhrzeit, Alarm-Kanal) und speichert / Then bleibt der Wert nach Neuladen erhalten, wirkt über denselben Speicherweg wie vor dem Umbau, und alle anderen gespeicherten Felder des Abos (Ampel, Etappen, Orte) bleiben unverändert
  - Test: Playwright auf Staging mit Datei-/API-Vergleich vorher/nachher je Feld, Trip und Vergleich.

### Teil-PR 3: Reiter Wetter

- **AC-9:** Given der Nutzer öffnet den Reiter Wetter / When die Metriken laden / Then steht oben die Überschrift mit Erklärsatz, währenddessen „Lade Metriken …“ mit Platzhaltern; bricht der Katalog-Abruf ab, erscheint die Fehlermeldung „Die Metriken konnten nicht geladen werden …“ mit „Erneut laden“, die gespeicherten Einstellungen bleiben unverändert, und ein Klick lädt neu
  - Test: Playwright auf Staging mit blockierter Katalog-Anfrage (Netzwerk-Abbruch im Browser, keine Mock-Logik im Code), danach Freigabe und Neu-Laden; Abo-Datei vorher/nachher gleich.

- **AC-10:** Given ein Trip mit Vorlage „Alpen-Trekking“ / When der Nutzer den Vorlagen-Picker öffnet / Then sieht er die 7 Systemvorlagen mit Kurzbeschreibung (Metrikzahl und Stichworte aus den Vorlagen-Daten, z. B. „14 Metriken“ bei Alpen-Trekking) und darunter „Eigene“, und der Picker zeigt „unverändert“ oder „{n} Abweichungen“
  - Test: Playwright auf Staging; Zahlen werden gegen `/api/templates` geprüft statt gegen feste Werte.

- **AC-11:** Given ein Trip mit 3 Abweichungen von „Alpen-Trekking“ / When der Nutzer „Wandern“ wählt / Then fragt ein Dialog „‚Wandern‘ übernehmen? … Deine 3 Abweichungen von ‚Alpen-Trekking‘ gehen verloren. Zustellung, Etappen und Orte bleiben unverändert.“; „Abbrechen“ ändert nichts, „Übernehmen“ ersetzt Metrik-Auswahl, Ampel-Grenzen und Alarmstufen, und Zustellung, Etappen und Orte sind danach unverändert
  - Test: Playwright auf Staging, Abo-Datei vorher/nachher (Ampel, Auswahl ersetzt; `report_config`, Etappen, Zustellung gleich); beide Wege (Abbrechen, Übernehmen).

- **AC-12:** Given ein Trip mit Abweichungen von seiner Vorlage / When der Nutzer „Auf ‚{Vorlage}‘ zurücksetzen“ wählt / Then stehen Auswahl, Grenzen und Alarm-ab-Stufen wieder wie in der Vorlage, der Picker zeigt „unverändert“, und der Zurücksetzen-Knopf ist verschwunden
  - Test: Playwright auf Staging mit Abo-Zustand vorher/nachher.

- **AC-13:** Given ein Orts-Briefing (bisher ohne Vorlagen) / When der Nutzer den Reiter Wetter öffnet / Then hat es dieselbe Vorlage-Karte mit den 7 Systemvorlagen und den eigenen Vorlagen der Art „Orte“, und ein Vorlagenwechsel verhält sich wie beim Trip (AC-11)
  - Test: Playwright auf Staging im Kontext `vergleich`; derselbe Test-Code läuft für beide Kontexte.

- **AC-14:** Given ein Trip, bei dem Böen und Gewitter alarmfähig sind / When der Nutzer in der Kopfzeile „Alarm ab für alle“ auf Orange stellt / Then steht bei jeder alarmfähigen Metrik „Alarm ab Orange“, Vorboten und reine Anzeige bleiben „kein Alarm“, der Zähler lautet „{x} von {y} Metriken lösen einen Alarm aus. {z} können keinen auslösen (Vorboten und reine Anzeige).“, und ist keine alarmfähige Metrik gewählt, erscheint „Keine der gewählten Metriken kann einen Alarm auslösen. Nimm z.B. Wind, Böen oder Gewitter dazu.“
  - Test: Playwright auf Staging mit Zählung der Segmente; zweiter Lauf mit einer Auswahl aus lauter Vorboten (z. B. Luftfeuchte, Regenwahrscheinlichkeit).

- **AC-15:** Given ein Trip mit mehreren Metriken / When der Nutzer den Reiter Wetter öffnet / Then stehen die Metrik-Zeilen in den fünf Gruppen Temperatur · Wind · Niederschlag & Gewitter · Himmel & Sicht · Schnee & Höhe (nur belegte Gruppen), jede Zeile zeigt Ampel-Leiste mit Grenzzahlen, Erklärsatz, „grün: …“-Zeile, „Alarm ab“ bzw. „kein Alarm (Vorbote)“ / „kein Alarm“ und „Grenzen ändern“, und es gibt keine CAPE-Zeile, keine Aggregationswahl und keine Roh/Einfach-Wahl
  - Test: Playwright auf Staging; Gruppenzugehörigkeit je Metrik aus `/api/metrics`, kein Test gegen eine Frontend-Kopie.

- **AC-16:** Given Böen mit „Alarm ab Orange“ in einer Vorlage mit Böen-Grenzen / When der Nutzer „Grenzen ändern“ öffnet und oben orange auf 50 setzt / Then zeigt der Erklärsatz „über 50 km/h“, der Picker „1 Abweichung“, nur die erlaubten Seiten sind als Felder sichtbar, und nach Speichern und Neuladen ist der Wert gespeichert und die Zeile zeigt „Fertig“ nicht mehr
  - Test: Playwright auf Staging, Neuladen, Abo-Datei prüft `ampel.metrics.gust` (nur die Abweichung steht dort).

- **AC-17:** Given ein Nutzer gibt in „Grenzen ändern“ eine ungültige Reihenfolge ein (oben gelb 50 und orange 40, oder unten gelb unter 0 und orange unter 5) / When er speichern will / Then zeigt die Zeile einen Fehlertext, nichts wird gespeichert, und die zuvor gespeicherten Grenzen bleiben
  - Test: Playwright auf Staging, Abo-Datei unverändert; `node --test` für die Reihenfolge-Regeln (oben, unten, unten nicht über oben).

- **AC-18:** Given ein Trip mit Gewitter und Windrichtung / When der Nutzer die beiden Zeilen ansieht / Then zeigt Gewitter „mittel: gelb · orange · rot“ und „hoch: orange · rot“ mit dem Hinweis „‚keins‘ ist immer grün.“, bietet kein „Alarm ab Gelb“ an, und Windrichtung zeigt „keine Ampel, nur Anzeige“ ohne „Grenzen ändern“; bei Vorlage „Wassersport“ erscheint für Gewitter mit Alarm ab Rot der Satz „Alarm, wenn …“, bei Farben, die die Stufe nie erreichen, „Mit diesen Farben erreicht Gewitter nie {Stufe}, daher kein Alarm.“
  - Test: Playwright auf Staging, zwei Vorlagen.

- **AC-19:** Given ein Trip mit der Metrik Wind im Briefing / When der Nutzer „−“ an Wind klickt und danach unter „Nicht im Briefing“ „+ Wind“ wählt / Then verschwindet Wind aus den Zeilen (Picker zeigt 1 Abweichung), taucht nach „+“ wieder auf mit der Meldung „Wind ist jetzt im Briefing und steht in allen Listen unter ‚Inhalt je Kanal und Fläche‘. Dort stellst du Roh oder Einfach ein.“, und der Picker zeigt dann wieder „unverändert“
  - Test: Playwright auf Staging; der Abweichungszähler wird dabei als Nutzer sichtbarer Wert geprüft.

- **AC-20:** Given ein Orts-Briefing, dessen Altfelder auseinanderlaufen (Bericht an, Alarm aus) / When der Nutzer den Reiter Wetter öffnet / Then steht der Schalter „Amtliche Warnungen“ auf an (ODER-Regel); nach dem Umlegen auf aus und Speichern sind `official_alerts_enabled` und `official_warnings.enabled` beide false, bei an beide true, und im Trip gilt dasselbe; ein Abo ohne den Schlüssel `official_warnings` fällt auf `official_alert_triggers_enabled` (Default an) zurück
  - Test: Go- und Python-Tests der Lese-Regel mit allen Kombinationen; Playwright auf Staging mit Datei-Zustand; Renderer und Alarm-Engine werden nicht verändert (bestehende Tests grün).

- **AC-21:** Given ein Orts-Briefing und ein Trip / When der Nutzer die Karten „Radar“ und „Anpassen“ ansieht / Then zeigt nur das Orts-Briefing den Schalter „Radar-Regen“ (Speichern setzt `radar_alert_enabled`), der Trip zeigt ihn nicht, und die eingeklappte Karte „Anpassen“ lässt das Tagesfenster von–bis einstellen, das wie bisher begrenzt (ADR-0035) und gespeichert wird
  - Test: Playwright auf Staging je Kontext; Tagesfenster-Grenzen über den bestehenden Clamp-Test.

### Teil-PR 1: Backend (Vorlagen, Katalog, Zähler, Migration)

- **AC-22:** Given ein Nutzer speichert eine eigene Vorlage / When der Dialog sich öffnet / Then enthält er Name, Beschreibung, „Als Standard für neue {Trips|Orte}“ und den Hinweis „Gespeichert werden Metrik-Auswahl, Ampel-Grenzen und Alarmstufen …“, aber weder Zeithorizonte noch Zusammenfassung; nach dem Speichern erscheint „Vorlage ‚{n}‘ gespeichert. Du findest sie unter ‚Eigene‘.“, und die gespeicherte Vorlage enthält die `ampel` des Abos
  - Test: Playwright auf Staging; Go-Handler-Test auf die gespeicherte Datei (`ampel` vorhanden, Feld `summary` und Zeithorizonte nicht gesetzt).

- **AC-23:** Given es gibt eine eigene Vorlage „Bergtag“ und die Systemvorlage „Allgemein“ / When ein Nutzer eine Vorlage „allgemein“, „ALLGEMEIN“ oder „bergtag“ derselben Art anlegt oder eine bestehende per PATCH so umbenennt / Then lehnt die API mit dem Fehler `name_exists` ab (Meldung in der Anfragesprache DE/EN: „Eine Vorlage ‚{n}‘ gibt es schon. Wähle einen anderen Namen.“), und der Dialog zeigt dieselbe Meldung; ein leerer Name zeigt „Gib der Vorlage einen Namen.“
  - Test: Go-Handler-Tests für POST und PATCH mit allen Schreibweisen und zwei Nutzern (derselbe Name bei Nutzer B ist erlaubt); Playwright auf Staging für die Dialog-Meldung.

- **AC-24:** Given Bestandsvorlagen ohne Feld `kind` und neue Vorlagen mit `kind` `route` bzw. `vergleich` / When der Nutzer im Trip bzw. im Orts-Briefing „Eigene“ öffnet / Then sieht er nur Vorlagen seiner Art, Bestandsvorlagen erscheinen beim Trip, und ein Name darf je Art einmal vorkommen, aber nicht doppelt innerhalb einer Art; ein ungültiger Wert für `kind` wird mit HTTP 400 abgelehnt
  - Test: Go-Handler- und Store-Tests mit zwei Nutzern und beiden Arten; Playwright auf Staging je Kontext.

- **AC-25:** Given ein Nutzer hat zwei Trip-Vorlagen und setzt bei der zweiten „Als Standard für neue Trips“ / When er danach einen neuen Trip anlegt / Then ist die zweite Vorlage vorausgewählt und angewendet (Metrik-Auswahl, Ampel, Alarmstufen), die erste ist nicht mehr Standard, eine Orts-Vorlage als Standard bleibt davon unberührt, und für einen zweiten Nutzer gilt sein eigener Standard
  - Test: Go-Handler-Test auf Anlegen mit zwei Nutzern und beiden Arten; Playwright auf Staging mit Anlegen über `/trips/new` und `/compare/new`.

- **AC-26:** Given Vorlagen-Dateien zweier Nutzer, in denen `horizons` je Metrik gesetzt sind / When `scripts/migrate_2794_preset_horizons.py` mit `--execute` läuft / Then stehen die Zeithorizonte danach auf „alle Tage“, alle übrigen Felder sind unverändert, je Nutzer liegt vor dem Schreiben eine tar.gz-Sicherung nur mit den Dateien dieses Nutzers vor, der Probelauf ohne `--execute` schreibt nichts, und ein zweiter Lauf meldet „Nichts zu tun“
  - Test: Migrationstest auf Fixture-Verzeichnis mit zwei Nutzern, Vergleich vorher/nachher je Feld, zwei Läufe, Probelauf.

- **AC-27:** Given die Metrik-Liste `/api/metrics` / When sie abgefragt wird / Then trägt jede Metrik `group` (eine der fünf UI-Gruppen), `alertable`, `is_precursor`, `allowed_sides` und `display_only`, Windrichtung ist `display_only` ohne Ampel, Luftfeuchte und Regenwahrscheinlichkeit sind Vorboten und nicht alarmfähig, Böen sind alarmfähig mit Seite „oben“, Temperatur „beidseitig“, und bestehende Felder (`unit`, `category`, `aggregations`) bleiben unverändert
  - Test: pytest gegen den Endpunkt (echte Katalog-Daten) mit festen Erwartungen für diese Metriken; Konsistenz `alertable` ↔ `is_precursor` ↔ `display_only` für alle Metriken.

- **AC-28:** Given dieselben Fixtures (Vorlage, Abo-Ampel mit Änderungen an Grenze, `enabled`, `alarm_ab`, Metrik hinzugefügt/entfernt, Gewitterfarbe) / When die Abweichungen gezählt werden / Then liefern die Python-Referenz und der Frontend-Spiegel dieselbe Zahl, jede der fünf Änderungsarten zählt einmal je betroffener Metrik, eine Änderung zurück auf den Vorlagenwert zählt nicht mehr, und der Picker zeigt die Zahl nach jeder Eingabe sofort
  - Test: pytest und `node --test` lesen dieselbe JSON-Fixture-Datei; Playwright prüft die Anzeige im Picker nach einer Änderung.

- **AC-29:** Given ein Trip und ein Orts-Briefing, die keine Altstufen, keinen Alarm-Preset, keine Regeln und keine Wetteränderungs-Alarme haben, aber eine aktive Metrik mit `alarm_ab` ≠ `never` in der aufgelösten Ampel / When Werte von grün auf Alarmfarbe springen / Then gilt das Abo als alarmfähig und der Alarm kommt (Trip und Vergleich), und ohne aktive Metrik mit `alarm_ab` ≠ `never` bleibt es wie bisher stumm
  - Test: pytest-Läufe über den Trip- und den Vergleichs-Einstieg mit und ohne `alarm_ab`, beobachtet wird Versand bzw. kein Versand.

### Querschnitt (Teil-PR 3, Mandanten- und Schreibsicherheit)

- **AC-30:** Given zwei Nutzer A und B mit je einem Trip und einem Orts-Briefing, bei A mit gesetzten Grenzen und Alarm-ab-Stufen / When Nutzer B in seinem Reiter Wetter Grenzen ändert und speichert und A parallel eine unabhängige Einstellung speichert / Then bleiben die Daten von A unverändert, B bekommt keine Werte von A, und das Speichern erhält alle Felder von `display_config`, die der Reiter nicht anfasst (`metric_alert_levels`, `alarm_ab_migration`, Zustellungs-Felder), unverändert (Read-Modify-Write, kein Replace)
  - Test: Go-Handler-Test mit zwei Nutzern und Feld-Vergleich; Playwright auf Staging mit zwei Konten.

### Teil-PR 4: Entfernen und Nachziehen

- **AC-31:** Given der Stand nach diesem PR / When Hub, Anlege-Ketten und Hilfe durchlaufen werden / Then gibt es keine Oberfläche mehr für Wertebereiche (Corridor-Editor), den Reiter Alarme, Zeithorizont-Chips und die Metrik-Checkbox, aber `alerts-tab/` mit den Bausteinen des Reiters Zustellung existiert weiter, und alle Aufrufer übersetzen und bauen ohne tote Importe
  - Test: Frontend-Build und `svelte-check` grün; Playwright-Durchlauf Hub und Anlege-Kette; Prüfstand-Tests der entfernten Komponenten sind mit entfernt (kein Test hält Altcode am Leben).

- **AC-32:** Given die Übersicht eines Orts-Briefings und eines Trips / When der Nutzer sie öffnet / Then führt die Karte „Wertebereiche“ im Orts-Briefing in den Reiter Wetter (U3) und die Zeile „Alarm bei Δ“ im Trip ist ein Text über „Alarm ab“ (U4); Kennzahlen und Versand-Historie (U1, U5) bleiben unverändert
  - Test: Playwright auf Staging je Kontext, Klickziel und Text; Übersichts-Modell per `node --test`.

- **AC-33:** Given der Listen-Eintrag „Alarme“ in Trip-Liste, Orts-Liste und Startseite sowie die Hilfe- und Onboarding-Texte / When der Nutzer darauf klickt oder sie liest / Then landet er im Reiter Zustellung bzw. Wetter (je nach Ziel), und kein Text nennt noch die Reiter Wertebereiche, Alarme, Layout oder Wetter-Metriken
  - Test: Playwright-Klicks auf jeden Sprung; `node --test` über die Kataloge `de` und `en` auf alte Reiternamen in Nutzertexten.

- **AC-34:** Given alle neuen und geänderten Texte dieser Scheibe / When die Oberfläche auf Deutsch und auf Englisch läuft / Then erscheinen alle über den Katalog in beiden Sprachen mit gleichen Platzhaltern, es gibt keinen hartkodierten Nutzertext, Protokoll-Token (z. B. `sms_code`, `compact_label`) bleiben unübersetzt, und die Begriffe Wetter, Vorlage, Ampel, Grenzen ändern, Alarm ab, Nicht im Briefing stehen vorab im Glossar
  - Test: bestehender Wächter `keine_hartkodierten_nutzertexte.test.ts`, Katalog-Paritäts-Test (Platzhaltermengen DE = EN), Playwright mit `language=en`.

- **AC-35:** Given dieselbe Funktion in Trip und Orts-Briefing (Reiter Wetter, Zustellung, Vorlage-Karte, Metrik-Zeile, Grenzen-Editor, Karte Amtliche Warnungen & Radar, Karte Anpassen) / When der Code betrachtet wird / Then gibt es je Funktion genau eine Komponente unter `shared/` mit `context="route"|"vergleich"` und keine Compare-Komponente mit Trip-Pendant, und die Oberfläche beider Kontexte entspricht dem Mockup Fassung 3 (Fresh-Eyes-Abgleich Desktop und Mobil)
  - Test: Pendant-Sperre des Gates (`docs/reference/gates_und_ratschen.md`) grün; Playwright-Screenshots beider Kontexte für den Fresh-Eyes-Inspektor.

## Test Plan

Je AC steht die konkrete Prüfung in der `Test:`-Zeile oben. Die Schichten:

### Automated Tests (TDD RED)

- [ ] **Kern-Schicht Python (pytest, ohne Netz, ohne Mocks):** Katalog-Felder an `/api/metrics` (AC-27), Abweichungszähler gegen die gemeinsame JSON-Fixture (AC-28), Alarmquellen-Gate Trip und Vergleich mit und ohne `alarm_ab` (AC-29), Lese-Regel Amtliche Warnungen (AC-20), `horizons`-Migration auf Fixture-Verzeichnis mit zwei Nutzern, zwei Läufen und Probelauf (AC-26).
- [ ] **Kern-Schicht Go (`go test`):** Vorlagen-Handler und Store für Duplikat (POST und PATCH, alle Schreibweisen, gegen die 7 Systemvorlagen), `ampel` im Dialog-Payload, `kind` mit Lese-Default `route`, „Als Standard für neue“ exklusiv je Art und wirksam bei Neuanlage, jeweils mit zwei Nutzern (AC-22 bis AC-25, AC-30); Lese-Regel Amtliche Warnungen (AC-20).
- [ ] **Kern-Schicht Frontend (`node --test`):** `REITER_DEFINITION`, `resolveTab`, `bereinigteTabAdresse` für alle alten Kennungen (AC-1, AC-2, AC-5), Abweichungszähler-Spiegel gegen dieselbe Fixture wie pytest (AC-28), Grenzen-Reihenfolge-Regeln (AC-17), Übersichts-Modell (AC-32), Katalog-Parität DE/EN und Wächter gegen hartkodierte Texte (AC-33, AC-34).
- [ ] **RED zuerst aus Nutzersicht:** Je Teil-PR werden die zugehörigen ACs (Zuordnung siehe Lieferplan) vor der Umsetzung rot nachgewiesen, Artefakte im Workflow registriert.
- [ ] **Mutations-Gegenprobe (Adversary):** mindestens Gate ohne `alarm_ab`-Erkennung, Duplikat-Prüfung ohne Systemvorlagen, Zähler ohne `alarm_ab`, Umleitung `alarme` → `wetter` statt `zustellung`, Speichern ohne Read-Modify-Write; jede Verfälschung muss einen Test rot machen.

### Live-E2E (nur `/e2e-verify` gegen Staging)

- [ ] Playwright je Kontext (Trip und Orte), Desktop und Mobil, für AC-1 bis AC-21, AC-31 bis AC-35 und AC-36, mit Datei- bzw. API-Zustand vorher/nachher statt reiner Oberflächen-Prüfung.
- [ ] Zwei-Konten-Lauf für alle datenbewegenden Wege (Vorlagen, Abo-Speichern).
- [ ] Fresh-Eyes-Abgleich der Screenshots beider Kontexte gegen Mockup Fassung 3 (AC-3, AC-35, AC-36).

## Definition of Done

- [ ] Alle 36 ACs grün in ihrer Schicht; Kern-Schicht zu 100 % grün, alle 6 CI-Checks je Teil-PR grün.
- [ ] Vier Teil-PRs in der festgelegten Reihenfolge gemergt; Teil-PR 3 erst nach Merge von PR #2862, Gate-Zeilen nach Rebase neu abgeglichen.
- [ ] `horizons`-Migration auf Staging und Produktion gelaufen, Pre-Snapshot je Nutzer vorhanden, Bestandsdaten unverändert bis auf die migrierten Felder.
- [ ] Kein Bedienelement aus Alarme/Versand verschwunden (Inventar-Test AC-7 grün).
- [ ] Adversary-Verdict VERIFIED inklusive Mutations-Gegenprobe; `/e2e-verify` auf Staging grün; Prod-Deploy mit Selftest Exit 0.
- [ ] Glossar, Hilfe-Texte, betroffene Specs (Status-Hinweis „abgelöst durch #2794“ bei entfallenen Reitern) und Changelog nachgezogen; Issue #2794 erst danach geschlossen.

## Known Limitations

- **Zustellung ist ein Übergangsreiter:** er zeigt bis S3b die heutigen Bausteine in der heutigen Reihenfolge, noch nicht die Kanal-Tabelle. Layout, 3-Tages-Ausblick, Stundenverlauf und Roh/Einfach je Liste wandern erst mit S3b in „Inhalt je Kanal und Fläche“. Die Hinweise auf diese Karte in den Texten von „Nicht im Briefing“ verweisen auf einen Ort, der bis S3b nur als Abschnitt im Übergangsreiter existiert.
- **Radar-Alarm beim Trip** fehlt bis S8 (#2800).
- **Gate-Reihenfolge:** Die „Alarm ab“-Bedienung (Teil-PR 3) wird erst nach Merge von PR #2862 ausgeliefert. Wird PR #2862 vorher geändert, sind Gate-Zeilen und Katalogschlüssel `alarm.ampel.*` neu abzugleichen.
- **Testumzug:** ca. 150 Test-Dateien nennen alte Kennungen; sie werden auf die neuen Kennungen und Reiter umgestellt (Teil-PR 2 und 4). Tests, die ausschließlich entfallene Oberflächen prüfen, werden gelöscht statt umgebogen.
- **Vorlagen-Migration `kind`:** Bestandsvorlagen bekommen `kind` per Lese-Default `route`; ein Schreiben der Datei setzt das Feld dauerhaft.
- **Kein Mail-Validator-Lauf nötig:** der Mail-Inhalt ändert sich in S3a nicht (nur Auswahl und Auslöser); Renderer-Gate wird nicht berührt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue. ADR-0109 (Reiterstruktur Wetter/Zustellung, Akzeptiert 2026-11-08) und ADR-0106 tragen die Entscheidung; ADR-0097 Punkt 1 wird durch ADR-0109 präzisiert.
- **Rationale:** Die Reiterstruktur ist entschieden. Offene Parameter dieser Scheibe (Übergangsreiter, ODER-Regel, `kind`) sind PO-Entscheidungen vom 2026-11-08 und stehen in dieser Spec und im Issue #2794.

## Changelog

- 2026-11-08: v1.0 Entwurf (Phase 3), Grundlage Analyse `docs/context/feature-2794-s3a-reiter-wetter.md` und PO-Entscheidungen P1 bis P3
