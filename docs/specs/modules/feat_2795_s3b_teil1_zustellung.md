---
entity_id: feat_2795_s3b_teil1_zustellung
type: module
created: 2026-11-12
updated: 2026-11-13
status: draft
version: "1.0"
tags: [hub, reiter, zustellung, briefing-zeiten, kanal-tabelle, alarme, stille-stunden, i18n, epic-2791]
workflow: feature-2795-s3b-teil1-zustellung
issue: 2795
epic: 2791
---

# Einstellungen neu S3b, Teil 1: Reiter „Zustellung“ (#2795, Teil B)

## Approval

- [ ] Approved

## Purpose

Der Reiter **Zustellung** (Hub und Anlage-Kette, Trip und Orts-Briefing, ein Code mit `context="route"|"vergleich"`) wird nach Mockup Fassung 3 neu gebaut. Er beantwortet zwei Fragen an einer Stelle: **Wann** kommen die Briefings (Morgen-/Abend-Uhrzeit, Laufzeit) und **auf welchem Weg** erreichen Briefings und Alarme den Nutzer (eine Kanal-Tabelle für alle vier Kanäle, Dringlichkeit je Kanal, Stille Stunden, Mindestabstand). Die alten Versand- und Alarm-Bausteine im Reiter werden in derselben Scheibe abgelöst (Epic-Regel: senkrecht, sichtbar, alte Bausteine weg).

Zwei fachliche Entscheidungen des PO (2026-11-12) prägen den Zuschnitt:

1. **Viertelstunden-Raster für Briefing-Zeiten.** Das Uhrzeitfeld ist frei eintippbar (00/15/30/45). 06:45 wird gespeichert **und** um 06:45 versandt. Heute kappt das Backend jede Zeit still auf die volle Stunde; ein freies Feld ohne Backend-Umbau würde 06:45 zu 06:00 verfälschen. Deshalb gehört Backend-Arbeit (Teilschritt 1a) zu dieser Spec.
2. **„Kanäle je Wettergröße“ entfällt.** Alarme laufen ausschließlich über die Kanal-Tabelle; je Kanal steuert die Dringlichkeit (gering/mittel/hoch), welche Alarme dort ankommen. Bestehende Sonderregeln je Metrik werden beim Umstieg aufgelöst.

Grundlagen: Ticket #2795 (Teil B, Abgleich V1–V15, A7–A13, U2, K13, AC-Skizze AC-5), Analyse `docs/context/feature-2795-s3b-teil1-zustellung.md`, Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html` (`viewZustellung()`, Texte wörtlich), Elementliste `docs/context/einstellungen_neu/elementliste.json` (Scope `zustellung`), Vorgänger-Specs `feat_2794_s3a_reiter_wetter.md` und `feat_2794_s3a_teil3_wetter.md`. ADRs: 0046 (Alarm-Kanal-Schwelle), 0049 (Premium-SMS), 0095 (Kanal-Parität), 0097 (Trip/Orte ein Code), 0104 (zweisprachig), 0109 (Reiterstruktur), 0112 (Design-System, Atomic Design), 0101 (Read-Modify-Write).

## Source

- **Frontend:** `frontend/src/lib/components/organisms/zustellung-tab/` (neu), `frontend/src/lib/components/shared/zustellung-tab/` (`ZustellungTab.svelte`, `zustellungModell.ts`, `zustellungSpeicherung.ts`), `frontend/src/lib/i18n/messages/{de,en}/zustellung.json` (neu), `frontend/src/lib/types.ts`.
- **Go-API:** `internal/handler/compare_preset.go`, `internal/handler/trip.go`, `internal/store/slot_hour_normalization.go`, `internal/model/compare_preset.go`, `internal/scheduler/scheduler.go`.
- **Python-Core:** `src/services/briefing_slots.py`, `src/services/trip_report_scheduler.py`, `src/services/compare_slot_scheduler.py`, `src/services/scheduler_dispatch_service.py`, `src/services/compare_alert_channels.py`, `src/services/alert_channels.py`, `src/app/models.py`.

**Identifier (Hauptstellen):**

| File | Identifier |
|---|---|
| `internal/store/slot_hour_normalization.go` | `TruncateTimeStringToHour`, `TruncateTimePtrToHour`, `HealComparePresetSlotTimes`, `NormalizeReportConfigSlotTimes`, `healTripSlotTimes` (Kappen auf Stunde → Prüfung auf Viertelstunden-Raster) |
| `internal/scheduler/scheduler.go` | Cron-Eintrag `briefing_dispatch` / `s.briefingDispatch` (stündlich → alle 15 Minuten) |
| `internal/model/compare_preset.go` · `src/app/models.py` | `type ComparePreset` · `class ComparePreset` (neues Feld `send_email`) |
| `src/services/briefing_slots.py` | `fenster_offen`, `BriefingSlotStore.reserve` / `is_recorded_or_claimed` (Fälligkeit in Minuten, Dedupe je Slot und Tag) |
| `src/services/trip_report_scheduler.py` | `_slot_stunde`, `trip_briefing_due_at`, `_slot_faellig_vor_ort`, `trip_slot_due` |
| `src/services/compare_slot_scheduler.py` | `_due`, `resolve_preset_slots` |
| `src/services/compare_alert_channels.py` | `effective_compare_briefing_channels` (`send_email` mit Default true) |
| `src/services/alert_channels.py` | `effective_alert_channels`, `_metric_channel_sets` (Altschlüssel `alert_metric_channels` wird ignoriert) |
| `frontend/src/lib/components/shared/zustellung-tab/zustellungSpeicherung.ts` (neu) | Reiter-Speicherer mit den Nutzlast-Teilen der Owner `versand` und `alarme` |
| `frontend/src/lib/components/shared/zustellung-tab/zustellungModell.ts` (neu) | Ableitung von Kanalstatus, Zählern und Sperren für die Kanal-Tabelle |

> **Schicht-Hinweis:** Reiter, Organismen, Modell und Speicherer sind Frontend (SvelteKit). Zeitnormalisierung, Cron-Takt und Preset-Modell sind Go. Fälligkeit, Dedupe je Slot, `send_email` im Versand und die Auflösung von `alert_metric_channels` im Alarmversand sind Python. Es entstehen **keine neuen Endpunkte**.
>
> **Trip/Ortsvergleich-Teilung (PFLICHT, #1170, Epic #2345):** Alle Organismen liegen geteilt unter `organisms/zustellung-tab/` mit `context="route"|"vergleich"`; es entsteht keine Compare-Komponente mit Trip-Pendant. Kontextunterschiede sind nur Texte (Etappe des Tages / heute), die Laufzeit-Karte (Trip: Anzeige + „Etappen öffnen →“; Orte: Segment + Datum), der Speicherweg (Trip: PUT `/api/trips/{id}`; Orte: Diff-Gate-Queue gegen Preset-PUT) und das Feld `send_email` (nur Orte neu).
>
> **Mandantentrennung:** Trip-PUT und Preset-PUT sind datenbewegende Endpoints, deren Nutzlast sich ändert. Beide werden mit **zwei verschiedenen Nutzern** getestet; `user_id` kommt aus dem Auth-Kontext, nie `"default"`. Die Migration läuft je Nutzerverzeichnis unter `data/users/<user_id>/`.
>
> **Kanäle:** Die Kanal-Tabelle führt alle vier Kanäle (E-Mail · Telegram · SMS · Premium-SMS) gleichrangig (ADR-0095). Alarme erreichen alle vier über dieselbe Auflösung (Dringlichkeit je Kanal). Der Mail-Inhalt ändert sich nicht; berührt ist nur, **ob** die Orts-Mail versandt wird (`send_email`).

## Estimated Scope

- **LoC (grob, inkl. Tests):** 1a Backend ca. +350/-60; 1b Neubau ca. +1500/-250; 1c Aufräumen ca. -1500 (Löschung mit zugehörigen Tests, Gegenposten). LoC-Override begründet: ein Reiter mit zwei Speicherwegen, Backend-Zeitraster und Löschung der Altbausteine in einer Scheibe.
- **Files:** 1a ca. 12, 1b ca. 18 (davon ca. 12 neu), 1c ca. 25 (überwiegend Löschung).
- **Effort:** high. Risiko MEDIUM-HIGH: Versandzeitpunkt aller Briefings; zwei Speicherwege in einer Tabelle; Alarm-Sonderregeln-Migration.

**Lieferung:** ein Workflow, drei Teilschritte, jeder in sich lauffähig mit grüner Kern-Schicht (je eigener PR):

- **1a Backend** (kein UI): Viertelstunden-Raster, `send_email` für Orte, Auflösung `alert_metric_channels`.
- **1b Neubau des Reiters** nach Mockup, mit sichtbarem Übergangsblock.
- **1c Aufräumen:** nicht mehr importierte Alt-Bausteine samt Tests weg.

## Scope

### In Scope

- Reiter Zustellung komplett (Teil B des Tickets): Kopf, Morgen-/Abend-Briefing, Laufzeit, Warnboxen, Kanal-Tabelle, Stille Stunden, Anpassen (Cooldown).
- Backend 1a (Raster, `send_email`, Wegfall der Kanäle je Wettergröße inkl. Migration).
- Premium-SMS-Status V5 und Sperrgründe A10.
- Neue Kataloge `zustellung.*` (de/en) und Glossar-Einträge Zustellung, Stille Stunden, Dringlichkeit.
- Entfernen der Doppelungen im Reiter (amtliche Warnungen/Radar, „Alarm ab je Metrik“, Kanäle je Wettergröße).
- Regressionsschutz für U2 (Übersicht „Bearbeiten →“ nach Zustellung), K13 („Setup abschließen“ nach Zustellung), V13 („Nächstes Briefing“ bleibt in der Übersicht).

### Out of Scope

- **Teil 2 (eigener Workflow, Teil A des Tickets):** Inhalt je Kanal und Fläche im Reiter Wetter, 3-Tages-Ausblick-Vereinheitlichung, Umzug von Telegram-Kurzstil, Layout je Kanal, Mehrtages-Trend, Nachtblock, Report-Config. Diese Bedienelemente bleiben bis dahin **unverändert** im Reiter sichtbar (Übergangsblock, siehe Abschnitt „Übergangsblock“).
- **S5 (#2797):** „Test schicken“ im Kopf; das Beispiel-Alarm-Element bleibt bis dahin im Übergangsblock.
- Neue Endpunkte, neue Kanäle, neue Alarmarten.
- Anlegeseiten `TripNewEditor` / `CompareNewEditor`: bleiben auf `VersandTab`/`AlarmeTab`; kein von ihnen importierter Baustein wird in 1c entfernt.
- Abgleich-Werkzeuge der parallelen Sitzung #2913 (werden nicht angefasst; Marker im Reiter setzt diese Spec).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| S3a Reiter Wetter (live) | Vorarbeit | `WarnungenRadarKarte` (amtliche Warnungen/Radar) und „Alarm ab je Metrik“ wohnen im Reiter Wetter; `organisms/wetter-tab/` als Muster, `data-abschnitt`-Marker |
| `GET /api/auth/profile` (`internal/handler/auth.go`) | Daten | Kanalstatus, Tarif, Premium-SMS-Zustand; wird im Reiter **einmal** geladen (heute dreimal) |
| `channelConnectionStatus.ts`, `premiumSmsChannelState.ts`, `premiumSmsAlarmGate.ts`, `tripChannelReconstruction.ts`, `alarmeDeliveryPayload.ts` | Code | Bleiben als Helfer, Nutzlast-Bau wird als reine Funktionen herausgelöst |
| `versandVergleichSpeicherung.ts`, `alarmeVergleichSpeicherung.ts`, `BriefingScheduleTab.svelte`, `AlarmeScheduleTab.svelte` | Code | Bestehende Speicherwege (Owner `versand` / `alarme`) |
| `s3a2794_speicher_owner_waechter.test.ts` | Wächter | Muss grün bleiben: ein Reiter-Speicherer, Owner bleiben getrennt |
| `scripts/elementliste_abgleich.ts`, `elementliste.json`, `elementliste_freigaben.json` | Abnahme | `npm run elementliste:abgleich -- --scope zustellung` |
| ADR-0046 / `alert_channel_thresholds` | Datenmodell | Dringlichkeit je Kanal LOW/MODERATE/HIGH, fehlend = LOW |
| `.claude/agents/mockup-bildpruefer.md` | Abnahme | Soll/Ist-Bild an den PO |

## Implementation Details

### 1 Seitenaufbau (Reihenfolge wie Mockup)

Jeder Abschnitt trägt den DOM-Marker `data-abschnitt` mit den Elementlisten-Namen: `abschnittskopf`, `briefing-zeiten`, `laufzeit`, `kanaele`, `stille-stunden` (plus `uebergang` für den Übergangsblock, nicht Teil der Elementliste).

1. **Kopf:** „Zustellung“ / „Wann die Briefings kommen und auf welchem Weg Briefings und Alarme dich erreichen.“
2. **Zwei Karten nebeneinander** (Mobile untereinander): Morgen-Briefing (Vorgabe 07:00) und Abend-Briefing (Vorgabe 18:00), je Uhrzeitfeld + Schalter. Unterzeile Trip „für die Etappe des Tages“ / „für die Etappe von morgen“, Orte „für heute“ / „für morgen“. Keine Schnellwahl-Knöpfe (V11).
3. **Laufzeit:** Trip: „{Daten}. Die Briefings enden nach der letzten Etappe. Die Daten pflegst du in den Etappen.“ + Knopf „Etappen öffnen →“ (springt in den Reiter Etappen). Orte: Segment „Bis auf Weiteres · Bis Datum“ (`end_date`, nil = bis auf Weiteres) + Datumsfeld bei „Bis Datum“; Erklärsatz je Wahl („Das Briefing läuft, bis du es pausierst.“ / „Danach pausiert das Briefing von selbst. Im Kopf steht dann ‚Laufzeit überschritten‘.“).
4. **Warnboxen** (`role="alert"`, über der Tabelle, getrennt): „Kein Kanal für Briefings an. So kommt kein Briefing bei dir an. Schalte unten mindestens einen Kanal ein.“ nur bei 0 Briefing-Kanälen; „Kein Kanal für Alarme an. Alarme gehen nirgends hin.“ nur bei 0 Alarm-Kanälen.
5. **Kanal-Tabelle:** Kopf „Briefings über {n} {Kanal|Kanäle} · Alarme über {m} {Kanal|Kanäle}“ (Singular bei genau 1, sonst Plural, auch bei 0), Unterzeile „Ein Kanal ohne Verbindung ist gesperrt, bis du ihn im Konto einrichtest.“ Spalten **Kanal · Briefing · Alarme · Alarm schon ab Dringlichkeit**; Zeilen E-Mail, Telegram, SMS, Premium-SMS. Details in 2.
6. **Legende** unter der Tabelle: „Die SMS kostet wenig und bekommt deshalb schon Alarme ab ‚mittel‘. Die Premium-SMS geht über Satellit und meldet sich nur bei ‚hoch‘.“
7. **Stille Stunden:** von–bis (`alert_quiet_from`/`alert_quiet_to`, „HH:MM“) + Schalter, Unterzeile „keine Alarme, sie kommen mit dem nächsten Morgen-Briefing“. Darunter `<details>` „Anpassen“ mit „Mindestabstand zwischen zwei Alarmen“ / „derselben Metrik“ / Minutenfeld (`alert_cooldown_minutes`, Default 120; das Feld zeigt den **gespeicherten** Wert, die „10“ im Mockup ist Beispiel).
8. **Übergangsblock** (siehe Abschnitt 5), am Ende des Reiters.

### 2 Kanal-Tabelle: Status, Sperren, Dringlichkeit

- **Statuszeile je Kanal:** Punkt + Text „bestätigt / verbunden / unbestätigt / nicht verbunden“ + Ziel (E-Mail-Adresse, Chat, Nummer wie heute in `channelContactLabel`). Quelle: Profil + `channelConnectionStatus.ts`.
- **Ohne Verbindung:** Hinweiszeile in der Kanalzeile mit Grund und Konto-Link „Im Konto {verbinden|bestätigen|prüfen} →“ (Telegram-Chat fehlt, Nummer noch nicht bestätigt, E-Mail-Adresse fehlt, „SMS ab Level Standard“). Der **Briefing-Schalter ist gesperrt** (`disabled`, aus), die **Alarm-Zelle** zeigt „gesperrt: {Grund}“ statt Schalter; Dringlichkeit zeigt „–“.
- **Dringlichkeit:** Segment gering · mittel · hoch (Datenwerte LOW | MODERATE | HIGH in `alert_channel_thresholds`, fehlend = LOW) nur bei eingeschaltetem Alarm der Zeile, sonst „–“. Die Anzeige ist lokalisiert, der Datenwert bleibt unübersetzt (ADR-0104).
- **Premium-SMS (V5, sicherheitsrelevant):** Statuszeile „inReach · Rückadresse gelernt {Datum} · zuletzt gemeldet {Zeit}“; bei verfallener Rückadresse „Rückadresse verfallen“ + „Schick eine Nachricht vom Gerät, dann ist die Rückadresse wieder gültig.“ und **Alarm- und Briefing-Zelle gesperrt mit Grund** (die verfallene Adresse kann ein fremdes Gerät erreichen, daher kein Versand). Alarm-Sperrgründe aus `premiumSmsAlarmGate.ts` bleiben („Tarif wird geprüft …“, „ab Level Premium“).
- Zähler n/m zählen nur Kanäle, die **an und verbunden** sind.

### 3 Speichern (ein Reiter-Speicherer, zwei Nutzlast-Teile)

`zustellungSpeicherung.ts` ist der **einzige** Speicherer des Reiters. Er bildet aus dem Formularzustand zwei Nutzlast-Teile als reine Funktionen:

- **Teil `versand`** (Owner `versand`): `morning_time`/`evening_time` bzw. Flach-Slotfelder, Aktiv-Schalter Morgen/Abend, Briefing-Kanalschalter (`send_email`, `send_telegram`, `send_sms`, `send_premium_sms`), Laufzeit Orte (`end_date`).
- **Teil `alarme`** (Owner `alarme`): `alert_channels`, `alert_channel_thresholds`, `alert_quiet_from`/`alert_quiet_to` (+ Schalter), `alert_cooldown_minutes`.

Regeln: nur **geänderte** Felder werden gesendet (Diff gegen den zuletzt geladenen Stand, Read-Modify-Write mit Server-Merge, `If-Match`); Fremdfelder (z. B. `ampel`, `display_config`, `report_config`, Übergangsblock-Felder) werden nie überschrieben. Trip: `pickEigenfelder` mit den Owner-Schlüsseln über die bestehende PUT-Strecke. Orte: bestehendes Diff-Gate mit Queue und Rollback. Der Vergleich mountet den Reiter erst nach Hydration (bestehendes Gate in `CompareTabs.svelte`). Das Profil wird einmal je Reiter geladen und an alle Organismen gereicht.

### 4 Backend 1a

**4.1 Viertelstunden-Raster.**

- *Schreiben (Go):* `compare_preset.go` (Zeile 57–59) und `trip.go` (Zeile 403–405) kappen nicht mehr auf die volle Stunde. Zulässig sind Minuten 00/15/30/45; Format „HH:MM“ oder „HH:MM:SS“ (Sekunden werden zu :00). **Entscheidung Tech Lead:** Eine unzulässige Minute (z. B. 06:50) wird **nicht still gerundet**, sondern der Server antwortet **400** mit klarem Fehlertext; die Oberfläche verhindert das vorher (Inline-Fehler „Bitte eine Zeit im Viertelstunden-Raster eintragen (00, 15, 30, 45)“, kein Speichern). Begründung: stilles Runden ist genau der Fehler, den der PO nicht will (Ist ≠ Eingabe); ein harter Server-Fehler schützt zusätzlich vor Fremdclients; das Feld bleibt frei eintippbar, lässt aber keine Eingabe zu, die später verfälscht würde.
- *Lesen (Go):* `internal/store/slot_hour_normalization.go` normalisiert Bestandswerte nicht mehr auf die Stunde. Bestandswerte „07:00“/„18:00“ bleiben unverändert gültig; ein (theoretisch) nicht rasterkonformer Altwert wird beim Lesen auf die vorherige Viertelstunde abgerundet, aber nicht zurückgeschrieben.
- *Fälligkeit (Python):* `trip_report_scheduler.py` (Zeile 259–268) und `briefing_slots.py` (`fenster_offen`) vergleichen die volle Uhrzeit in Minuten statt nur `.hour`; `compare_slot_scheduler.py` (`MORGEN_SLOT_VERSATZ` prüfen) entsprechend. Fenster: ab Slot-Zeit bis Slot-Zeit + 3 h (Nachholfenster fachlich gleich).
- *Takt (Go):* Cron `briefing_dispatch` (`internal/scheduler/scheduler.go`, Zeile 341) läuft alle 15 Minuten statt stündlich (Python entscheidet weiter die Fälligkeit).
- *Genau ein Versand je Slot und Tag:* Der Dedupe-Schlüssel in `briefing_slots.json` ist (Abo, Slot-Name, Datum), nicht die Stunde; die Claim-TTL (900 s, `briefing_slots.py`) bleibt Schutz gegen Doppellauf, trägt die Dedupe aber nicht. Ein erfolgreich versandter Slot wird an diesem Tag nicht erneut ausgelöst, auch wenn bis zu 12 Ticks (3-h-Fenster, 15-Minuten-Takt) in das Fenster fallen. Der Fail-closed-Zustand bei unbekanntem Ausgang (`test_scheduler_unknown_outcome_locks_slot.py`) bleibt unverändert.

**4.2 `send_email` für Orte.** `internal/model/compare_preset.go` und das Preset-Modell in `src/app/models.py` bekommen `send_email` (Go `*bool` mit `omitempty`; Python `bool = True`). **Fehlendes Feld bedeutet true** (Alt-Presets verstummen nicht). Der Versand (`scheduler_dispatch_service.py`, Zeile 723–731) und die Alarm-Kanalauflösung (`compare_alert_channels.py`) lesen das Feld; ist es `false`, geht keine Orts-Mail raus (Telegram/SMS/Premium-SMS bleiben unabhängig). `types.ts` (`ComparePreset.send_email`) und der Reiter-Speicherer ziehen nach.

**4.3 Wegfall „Kanäle je Wettergröße“ (`alert_metric_channels`).** Der Alarmversand (`src/services/alert_channels.py`, `trip_alert.py`, `compare_alert.py`, `compare_alert_channels.py`) liest `alert_metric_channels` nicht mehr; Zielkanäle ergeben sich nur aus `alert_channels` und `alert_channel_thresholds` der Kanal-Tabelle, **für alle Metriken gleich**. Dazu kommt eine Migration `scripts/migrate_2795_alert_metric_channels.py`: je Nutzer und je Trip/Preset **Read-Modify-Write** (Objekt laden, nur den Schlüssel `alert_metric_channels` entfernen, alle anderen Felder unverändert zurückschreiben), mit Sicherung vor dem Lauf (Pre-Snapshot-Hook `data_schema_backup.py`), idempotent, mit Protokoll der betroffenen Abos (Nutzer, Trip/Ort, Metrik, bisherige Sonderregel). Zusätzlich ist der Alarmversand gegen Altbestand abgesichert: ein noch vorhandener Schlüssel wird ignoriert, nicht ausgewertet. Go behält das Feld lesetolerant im Modell (kein Datenverlust bei Zwischenständen), die Oberfläche schreibt es nicht mehr.

### 5 Übergangsblock (bis Teil 2 und S5)

Am Ende des Reiters, klar abgegrenzt (Überschrift über `zustellung.uebergang.*`, `data-abschnitt="uebergang"`): `WetterMetrikenVersandPanel` ohne den alten `<section id="versand">` mit den Abschnitten `layout_kanal`, `stundenverlauf`, `ausblick`, `report_config`, `nachtblock`, `sms_schwellen` (Telegram-Kurzstil, Layout je Kanal, Ausblick/Mehrtages-Trend, Nachtblock, E-Mail-Report-Config, SMS-Schwellen) und das **Beispiel-Alarm-Element** (bis S5). `sms_schwellen` und Empfindlichkeit entfallen laut Konzept mit der Ampel, sind im heutigen Stand aber noch im Reiter vorhanden (`weatherMetricsTabSections.ts`); sie werden deshalb **nicht still entfernt**, sondern bleiben hier bis Teil 2. Kein Bedienelement geht verloren. Der Anker `#versand` (Übersicht U2, „Setup abschließen“ K13, `subscriptionTabs.ts`) zeigt weiter auf den Reiter und scrollt zur Briefing-Zeiten-Karte.

### 6 Texte und Glossar

Alle neuen Nutzertexte nur über `frontend/src/lib/i18n/messages/{de,en}/zustellung.json` (Präfix `zustellung.*`, ADR-0104); Glossar `docs/reference/i18n_glossar.md` zuerst um Zustellung, Stille Stunden, Dringlichkeit ergänzen. Protokoll-Token (`sms_code`, Kürzel, Datenwerte LOW/MODERATE/HIGH) werden nie übersetzt. Alte `versand.*`/`alarme.*`-Schlüssel bleiben, solange die Anlegeseiten sie brauchen.

### 7 Elemente: Zuordnung alt nach neu

| Altes Element | Ziel |
|---|---|
| V1 Briefing-Kanalkästchen, V9 Uhrzeit-Select, V14/V15 Laufzeit | Zustellung (neu); Schnellwahl V11 entfällt |
| A7/A8 AlertChannelPicker, A12 Cooldown, A13 Stille Stunden | Zustellung (neu), Cooldown unter Anpassen |
| Amtliche Warnungen/Radar, „Alarm ab je Metrik“ | wohnen im Reiter Wetter, im Reiter Zustellung **entfernt** |
| AlertMetricChannelsBlock („Kanäle je Wettergröße“) | **entfällt** (PO), Auflösung per Migration |
| Nächstes Briefing V13 | bleibt in der Übersicht |
| Telegram-Kurzstil, Layout je Kanal, Ausblick, Nachtblock, Report-Config | Teil 2, bis dahin Übergangsblock |
| Beispiel-Alarm A14 | S5, bis dahin Übergangsblock |

## Definition of Done

- Alle AC-1 bis AC-41 sind durch Tests belegt; die Kern-Schicht (Go, Python, Frontend) ist vollständig grün, alle sechs CI-Prüfungen sind grün.
- Teilschritt 1a: 06:45 überlebt Schreiben und Lesen über Trip- und Preset-PUT, wird genau einmal um 06:45 Ortszeit versandt; Alt-Presets ohne `send_email` versenden weiter E-Mail; `alert_metric_channels` ist migriert (Read-Modify-Write, Migrationsprotokoll je Nutzer).
- Teilschritt 1b: Reiter Zustellung für Trip und Orte auf Staging; Elementliste Scope `zustellung` ohne Lücke (beide Kontexte, vier Zustände); Soll/Ist-Bild Mockup gegen Staging an den PO geschickt.
- Teilschritt 1c: nicht mehr importierte Alt-Bausteine samt Tests entfernt; Anlegeseiten funktionieren unverändert.
- Zwei-Nutzer-Test für Trip-PUT und Preset-PUT grün; DE- und EN-Katalog vollständig.
- Staging-Verifikation bestanden, Produktion ausgeliefert, Selbsttest mit Exit 0.

## Acceptance Criteria

### Kopf, Briefing-Zeiten, Laufzeit

- **AC-1:** Given ein Nutzer öffnet den Reiter Zustellung eines Trips oder eines Orts-Briefings, When der Reiter geladen ist, Then steht oben „Zustellung“ mit der Unterzeile „Wann die Briefings kommen und auf welchem Weg Briefings und Alarme dich erreichen.“, und der Abschnitt trägt den Marker `abschnittskopf`.

- **AC-2:** Given ein Trip, When der Reiter Zustellung geöffnet ist, Then zeigt er zwei Karten Morgen-Briefing (Uhrzeit-Vorgabe 07:00, „für die Etappe des Tages“) und Abend-Briefing (18:00, „für die Etappe von morgen“) mit je einem Schalter und einem Uhrzeitfeld, und es gibt keine Schnellwahl-Knöpfe.

- **AC-3:** Given ein Orts-Briefing, When der Reiter Zustellung geöffnet ist, Then lauten die Unterzeilen der Karten „für heute“ und „für morgen“, und die übrigen Elemente der Karten entsprechen dem Trip.

- **AC-4:** Given ein Trip mit Morgen-Briefing 07:00, When der Nutzer im Uhrzeitfeld 06:45 eintippt und speichert, Then steht nach dem Neuladen der Seite 06:45 im Feld (gespeichert ohne Kappen auf 06:00), und zwar für Trip und Orts-Briefing gleichermaßen.

- **AC-5:** Given ein Briefing mit gespeichertem Morgen-Slot 06:45 und aktivem Schalter, When der Scheduler an diesem Tag vor 06:45 läuft und danach im 15-Minuten-Takt weiterläuft, Then wird nichts vor 06:45 versandt und das Briefing beim ersten Takt ab 06:45 (spätestens im 3-Stunden-Nachholfenster).

- **AC-6:** Given ein Slot 06:45 mit mehreren Cron-Ticks im Fenster (alle 15 Minuten), When der Scheduler über alle Ticks läuft, Then wird je Slot und Tag **genau ein** Briefing versandt (schlug ein früherer Tick fehl, holt ein späterer nach; bei Erfolg nie zweimal).

- **AC-7:** Given Bestandswerte „07:00“ und „18:00“ in Trips und Orts-Briefings, When Go sie liest und Python sie auswertet, Then bleiben sie unverändert gültig, werden zur selben Zeit wie zuvor versandt und im Feld unverändert angezeigt.

- **AC-8:** Given der Nutzer tippt 06:50 ins Uhrzeitfeld, When er das Feld verlässt oder speichert, Then erscheint am Feld die Meldung „Bitte eine Zeit im Viertelstunden-Raster eintragen (00, 15, 30, 45)“, es wird nichts gespeichert, und ein direkter PUT mit 06:50 an den Server wird mit 400 abgelehnt (keine stille Verfälschung zu 06:45 oder 06:00).

- **AC-9:** Given ein Trip, When der Reiter geöffnet ist, Then zeigt die Laufzeit-Karte „{Daten}. Die Briefings enden nach der letzten Etappe. Die Daten pflegst du in den Etappen.“ mit dem Knopf „Etappen öffnen →“, der in den Reiter Etappen springt.

- **AC-10:** Given ein Orts-Briefing ohne Enddatum, When der Reiter geöffnet ist, Then ist „Bis auf Weiteres“ gewählt mit dem Satz „Das Briefing läuft, bis du es pausierst.“; wählt der Nutzer „Bis Datum“, erscheint ein Datumsfeld mit dem Satz „Danach pausiert das Briefing von selbst. Im Kopf steht dann ‚Laufzeit überschritten‘.“, und das gespeicherte `end_date` entspricht dem eingegebenen Datum.

### Warnboxen und Kanal-Tabelle

- **AC-11:** Given kein Briefing-Kanal ist an (Zähler 0), When der Reiter geöffnet ist, Then erscheint oberhalb der Tabelle eine Warnbox mit `role="alert"` „Kein Kanal für Briefings an. So kommt kein Briefing bei dir an. Schalte unten mindestens einen Kanal ein.“; ist mindestens ein Briefing-Kanal an, erscheint sie nicht.

- **AC-12:** Given kein Alarm-Kanal ist an (Zähler 0), When der Reiter geöffnet ist, Then erscheint eine eigene Warnbox mit `role="alert"` „Kein Kanal für Alarme an. Alarme gehen nirgends hin.“, unabhängig von der Briefing-Warnbox; ist mindestens ein Alarm-Kanal an, erscheint sie nicht.

- **AC-13:** Given genau ein Briefing-Kanal und zwei Alarm-Kanäle sind an, When die Tabelle angezeigt wird, Then lautet der Kopf „Briefings über 1 Kanal · Alarme über 2 Kanäle“ (Singular bei 1, sonst Plural, auch „0 Kanäle“), darunter steht „Ein Kanal ohne Verbindung ist gesperrt, bis du ihn im Konto einrichtest.“

- **AC-14:** Given die Tabelle, When sie angezeigt wird, Then hat sie die Spalten Kanal, Briefing, Alarme, „Alarm schon ab Dringlichkeit“ und je eine Zeile für E-Mail, Telegram, SMS und Premium-SMS, jede mit Statuspunkt, Statustext (bestätigt / verbunden / unbestätigt / nicht verbunden) und Ziel.

- **AC-15:** Given Telegram ist nicht verbunden, When die Tabelle angezeigt wird, Then ist der Briefing-Schalter der Telegram-Zeile gesperrt, die Alarm-Zelle zeigt „gesperrt: {Grund}“, die Zeile zeigt einen Hinweis mit dem Link „Im Konto verbinden →“, der in das Konto führt, und die Dringlichkeit zeigt „–“.

- **AC-16:** Given eine SMS-Nummer ist unbestätigt, When die Tabelle angezeigt wird, Then trägt der Konto-Link „Im Konto bestätigen →“ und der Hinweistext benennt den Grund („Nummer noch nicht bestätigt“); bei fehlender E-Mail-Adresse heißt der Hinweis „E-Mail-Adresse fehlt“, bei zu niedrigem Tarif „SMS ab Level Standard“.

- **AC-17:** Given ein Kanal ist verbunden und der Alarm der Zeile ist aus, When die Tabelle angezeigt wird, Then zeigt die Spalte Dringlichkeit „–“; schaltet der Nutzer den Alarm ein, erscheint das Segment gering · mittel · hoch, und die Wahl wird als LOW/MODERATE/HIGH in `alert_channel_thresholds` gespeichert (fehlender Wert gilt als gering).

- **AC-18:** Given die Tabelle, When sie angezeigt wird, Then steht unter ihr „Die SMS kostet wenig und bekommt deshalb schon Alarme ab ‚mittel‘. Die Premium-SMS geht über Satellit und meldet sich nur bei ‚hoch‘.“

- **AC-19:** Given Premium-SMS mit gültiger Rückadresse, When die Tabelle angezeigt wird, Then steht in der Premium-SMS-Zeile „inReach · Rückadresse gelernt {Datum} · zuletzt gemeldet {Zeit}“, und Briefing- und Alarm-Schalter sind bedienbar.

- **AC-20:** Given Premium-SMS mit verfallener Rückadresse, When die Tabelle angezeigt wird, Then steht in der Zeile „Rückadresse verfallen“ und „Schick eine Nachricht vom Gerät, dann ist die Rückadresse wieder gültig.“, **Alarm- und Briefing-Zelle sind gesperrt** mit Grund, und die Premium-SMS wird in diesem Zustand nicht als Alarm-Kanal mitgezählt. (Bestandsverhalten, keine neue Regel: Der heutige Versand-Reiter sperrt den Premium-SMS-Kanal bei verfallener Rückadresse bereits für Briefings, `premiumSmsChannelState.ts` Zweig `stale` → `disabled: true`. Grund ist die Sicherheit: eine verfallene Rückadresse kann ein fremdes Gerät erreichen; das gilt für Briefings genauso wie für Alarme.)

- **AC-21:** Given Premium-SMS-Tarif „wird geprüft“ oder ein Tarif unter Premium, When die Tabelle angezeigt wird, Then zeigt die Alarm-Zelle „gesperrt: {Grund}“ mit dem bisherigen Gate-Text („Tarif wird geprüft …“ bzw. „ab Level Premium“).

- **AC-22:** Given ein Orts-Briefing mit `send_email: false` im gespeicherten Preset, When ein Briefing fällig ist, Then wird keine Orts-Mail versandt und Telegram/SMS/Premium-SMS bleiben vom Schalter unberührt; Given `send_email: true` oder **fehlendes Feld** (Alt-Preset), Then wird die Orts-Mail wie bisher versandt.

- **AC-23:** Given ein Orts-Briefing, When der Nutzer in der E-Mail-Zeile den Briefing-Schalter ausschaltet und speichert, Then steht `send_email: false` im Preset, die Oberfläche zeigt den Schalter nach dem Neuladen aus, und beim Einschalten steht `true`; andere Preset-Felder bleiben unverändert.

### Stille Stunden, Anpassen, Cooldown

- **AC-24:** Given der Reiter, When er geöffnet ist, Then zeigt die Karte Stille Stunden ein von- und ein bis-Feld (Format HH:MM) mit Schalter und dem Text „keine Alarme, sie kommen mit dem nächsten Morgen-Briefing“; Eingaben werden als `alert_quiet_from`/`alert_quiet_to` gespeichert und nach Neuladen wieder angezeigt, in Trip und Orten.

- **AC-25:** Given Stille Stunden sind aus, When ein Alarm auslöst, Then wird er zugestellt; sind sie an und liegt der Zeitpunkt im Fenster, Then wird kein Alarm zugestellt, und der Inhalt kommt mit dem nächsten Morgen-Briefing (bestehendes Verhalten bleibt, Regressionsschutz).

- **AC-26:** Given der Nutzer klappt „Anpassen“ auf, When die Karte offen ist, Then steht dort „Mindestabstand zwischen zwei Alarmen“ / „derselben Metrik“ mit einem Minutenfeld, das den **tatsächlich gespeicherten** Wert (Standard 120, falls nichts gespeichert) zeigt; eine Änderung wird als `alert_cooldown_minutes` gespeichert und im Alarmversand als Mindestabstand je Metrik eingehalten.

### Wegfall Kanäle je Wettergröße und Migration

- **AC-27:** Given der Reiter Zustellung (Trip und Orte), When er vollständig angezeigt wird, Then erscheint kein Baustein „Kanäle je Wettergröße“ mehr, und der Reiter schreibt `alert_metric_channels` nicht mehr.

- **AC-28:** Given ein Bestands-Abo mit `alert_metric_channels` (Sonderregel je Metrik) und weiteren Feldern wie `ampel`, `report_config`, `alert_channels`, When die Migration läuft, Then ist nur der Schlüssel `alert_metric_channels` entfernt, alle anderen Felder sind im Wert unverändert erhalten, eine Sicherung besteht vorher, das Protokoll nennt jedes betroffene Abo mit der alten Regel, und ein zweiter Lauf ändert nichts.

- **AC-29:** Given ein Abo mit Kanal-Tabelle E-Mail=an (gering), Telegram=an (hoch) und (noch) einem Altschlüssel `alert_metric_channels`, der eine Metrik nur auf E-Mail begrenzt, When für diese Metrik ein Alarm der Dringlichkeit „hoch“ auslöst, Then geht er an beide Kanäle nach der Kanal-Tabelle; ein Alarm „gering“ geht nur an E-Mail; der Altschlüssel hat keine Wirkung (Verhalten im Alarmversand getestet, Trip und Orte).

### Übergangsblock und entfernte Doppelungen

- **AC-30:** Given der Reiter nach 1b, When er angezeigt wird, Then enthält er am Ende einen klar abgegrenzten Übergangsblock mit Telegram-Kurzstil, Layout je Kanal, Ausblick/Mehrtages-Trend, Nachtblock, Report-Config, SMS-Schwellen (soweit noch vorhanden) und dem Beispiel-Alarm; jedes dieser Elemente ist weiter bedienbar und speichert wie vor der Änderung (kein Bedienelement geht verloren).

- **AC-31:** Given der Reiter Zustellung, When er angezeigt wird, Then erscheinen dort weder „Amtliche Warnungen & Radar“ noch „Alarm ab“ je Metrik noch eine zweite Kanalauswahl für Alarme; diese stehen nur im Reiter Wetter bzw. in der Kanal-Tabelle (jede Funktion genau einmal im Hub).

### Speichern, Mandanten, i18n

- **AC-32:** Given der Nutzer ändert nur die Uhrzeit des Morgen-Briefings, When er speichert, Then enthält die gesendete Nutzlast ausschließlich die geänderten Felder, und die zuvor gespeicherten Felder `ampel`, `display_config`, `report_config`, `alert_channels` und alle Übergangsblock-Felder sind danach unverändert (Read-Modify-Write, keine Fremdfelder überschrieben); ändert er nur eine Dringlichkeit, wird nur der Alarm-Teil gesendet.

- **AC-33:** Given der Reiter Zustellung, When Briefing- und Alarm-Felder geändert werden, Then gibt es für den Reiter genau **einen** Speicherer mit zwei Nutzlast-Teilen (Owner `versand` und `alarme` bleiben getrennt), und der Wächter `s3a2794_speicher_owner_waechter` bleibt grün.

- **AC-34:** Given zwei verschiedene Nutzer A und B mit je einem Trip und einem Orts-Briefing, When A über Trip-PUT bzw. Preset-PUT Uhrzeit (inkl. 06:45), `send_email`, Dringlichkeit, Stille Stunden und Cooldown ändert, Then bleiben die Daten von B unverändert, ein PUT von B auf A's Objekt wird abgelehnt, und die `user_id` stammt aus dem Auth-Kontext (nie `"default"`).

- **AC-35:** Given die Sprache des Nutzers ist Englisch, When der Reiter angezeigt wird, Then erscheinen alle Texte des Reiters aus dem englischen Katalog `zustellung.*` (inklusive Warnboxen, Tabellenkopf mit Singular/Plural, Hinweise, Legende), Protokoll-Token und Datenwerte bleiben unübersetzt, und eine Lückenprüfung zeigt in `de` und `en` dieselben Schlüssel.

- **AC-36:** Given das Profil des Nutzers, When der Reiter geladen wird, Then wird `GET /api/auth/profile` genau einmal je Reiter-Aufruf angefragt (nicht mehr dreimal), und alle Kanal-Zustände stammen aus dieser einen Antwort.

### Abnahme und Regressionen

- **AC-37:** Given der Reiter nach 1b, When `npm run elementliste:abgleich -- --scope zustellung` gegen die Staging-Seite läuft, Then ist der Abgleich **lückenlos** (keine fehlenden und keine nicht freigegebenen Abweichungen) für beide Kontexte (Trip und Orte) und die vier Zustände normal, laedt, fehler, luecken.

- **AC-38:** Given Mockup und Staging-Seite desselben Zustands, When der Agent `mockup-bildpruefer` die Bilder anhand des Elementlisten-Auszugs vergleicht, Then liegt ein Soll/Ist-Bild mit dokumentiertem Ergebnis für den PO vor, und jede sichtbare Abweichung ist einer Zuordnung zugewiesen (Übergangsblock ausdrücklich benannt).

- **AC-39:** Given die Übersicht eines Trips oder Orts-Briefings (U2), When der Nutzer in der Versand-Karte „Bearbeiten →“ wählt, Then landet er im Reiter Zustellung an der Briefing-Zeiten-Karte (Anker `#versand`); „Nächstes Briefing“ (V13) steht weiter in der Übersicht und nicht im Reiter Zustellung.

- **AC-40:** Given ein Orts-Briefing im Hub nach dem Anlegen (K13), When der Nutzer „Setup abschließen“ wählt, Then öffnet sich `?tab=zustellung#versand`, und alte Links mit Kennungen `versand`/`alarme` führen ebenfalls auf den Reiter Zustellung.

- **AC-41:** Given 1c ist ausgeliefert, When der Code geprüft wird, Then sind nicht mehr importierte Alt-Bausteine samt ihrer Tests entfernt, `TripNewEditor` und `CompareNewEditor` funktionieren unverändert (Anlegen eines Trips und eines Orts-Briefings mit Kanalwahl gelingt), und kein von den Anlegeseiten importierter Baustein ist gelöscht.

## Test Plan

**Kern-Schicht (deterministisch, ohne Netz, ohne Mock-Theater):**

- *Go (`go test`):* Zeitnormalisierung (06:45 bleibt, 07:00 bleibt, 06:50 → 400, Sekunden → :00, Lesen rundet Altwert ab ohne Rückschreiben); `send_email` fehlt/true/false im Preset-Roundtrip; Preset-PUT und Trip-PUT mit **zwei Nutzern** (Fremdzugriff abgelehnt); Merge lässt Fremdfelder unberührt (`internal/handler/*_test.go`, `internal/store/slot_hour_normalization_test.go`, `compare_preset_slot_migration_test.go`).
- *Python (benannte Testdateien, nie ein Lauf ohne Dateinamen):* Fälligkeit in Minuten (`fenster_offen` für 06:45 vor/nach/im Fenster), Dedupe über 12 Ticks mit echter `briefing_slots.json` im tmp-Verzeichnis (nicht gemockt), Fail-closed bleibt (`test_briefing_slot_fail_closed.py`, `test_scheduler_unknown_outcome_locks_slot.py`), `send_email` fehlt/true/false im Versandpfad, Alarmauflösung mit Altschlüssel `alert_metric_channels` (ignoriert) und Dringlichkeit je Kanal, Migration (Idempotenz, Fremdfelder erhalten, Protokoll).
- *Frontend (`node --test`):* Modell und Speicherer als reine Funktionen (Diff nur geänderter Felder, Owner-Trennung, Premium-SMS-Sperren, Zähler Singular/Plural), Katalog-Parität de/en, Marker `data-abschnitt` je Abschnitt, AST-Wächter `s3a2794_speicher_owner_waechter`, Pendant-Sperre (#1170), Raster-Validierung des Uhrzeitfelds.
- *Umgesetzt in 1a (2026-11-13):* `internal/handler/zustellung_2795_test.go` (Trip-POST 06:50 → 400, Zwei-Nutzer-Preset-PUT) und `tests/test_2795_alert_metric_channels_ignoriert.py` (Zwei-Nutzer-Test Kanal-Auflösung, Altschlüssel ignoriert).
- Ein Verhaltens-Nachweis ist zuerst aus Nutzersicht rot (z. B. 06:45 wird zu 06:00 gespeichert), danach grün.

**Live-E2E auf Staging (`/e2e-verify`, nach dem Push):** Playwright für Trip und Orte: 06:45 eintippen, speichern, Neuladen, Wert steht; 06:50 → Meldung; Kanal ohne Verbindung gesperrt mit Konto-Link; Dringlichkeit nur bei Alarm an; Premium-SMS verfallen gesperrt; E-Mail-Schalter Orte aus/an; Stille Stunden und Cooldown speichern; Übergangsblock vorhanden; U2/K13-Sprünge; Elementlisten-Abgleich Scope `zustellung` (beide Kontexte, vier Zustände); Soll/Ist-Bild über `mockup-bildpruefer`.

**Mail-Validatoren:** Der Mail-**Inhalt** ändert sich nicht. Da `send_email` den Orts-Mailversand schaltet, läuft `email_spec_validator.py` (Orts-Briefing, Exit 0 = „E2E bestanden“) gegen eine echt zugestellte Staging-Mail als Regression mit Standardwert (Feld fehlt); `briefing_mail_validator.py` (Trip) dient als Gegenprobe. Das Renderer-Commit-Gate wird nicht ausgelöst, weil kein Renderer-Code geändert wird.

**Adversary/Mutationen (PFLICHT):** Verfälschungen u. a.: Kappen auf Stunde wieder einbauen, Dedupe-Schlüssel auf Stunde, Default `send_email` auf false, Alarmauflösung liest Altschlüssel wieder, Speicherer sendet Fremdfelder, Premium-SMS-Sperre entfernen; jede muss einen Test rot machen (Leitfrage: wird dort geprüft, wo die Zusicherung wirkt, also am Versandzeitpunkt bzw. am gespeicherten Objekt).

## Risks

1. **Versandzeitpunkt aller Briefings (hoch):** Ändert sich die Fälligkeitslogik falsch, kommt ein Briefing doppelt, zu früh oder gar nicht. Gegenmittel: Dedupe je (Abo, Slot, Tag), Tests über alle Ticks, Fail-closed-Tests unverändert, Staging-Lauf mit echtem 15-Minuten-Takt, Rollback über das Deploy-Playbook.
2. **Cron alle 15 Minuten:** Mehr Aufrufe an Python; Python entscheidet die Fälligkeit billig vor dem Provider-Aufruf. Heartbeat-Pflicht: der bestehende Heartbeat pingt nur nach fachlichem Erfolg, der Takt-Wechsel wird dort geprüft.
3. **Alarm-Sonderregeln fallen weg:** Wer eine Metrik bewusst auf einen Kanal begrenzt hatte, bekommt nach der Migration Alarme dieser Metrik über alle Kanäle nach Dringlichkeit. Gegenmittel: PO-Entscheidung, Protokoll der betroffenen Abos, Kanal-Tabelle als einzige Steuerung (Dringlichkeit je Kanal), Migration mit Sicherung und idempotent.
4. **Alt-Presets und `send_email`:** Fehlendes Feld muss true bleiben, sonst verstummen Orts-Briefings; durch Test fehlt/true/false abgesichert.
5. **Zwei Owner in einer Tabelle:** Eine Zeile mischt Briefing und Alarm. Gegenmittel: ein Speicherer, zwei Nutzlast-Teile, Wächter grün, Diff nur geänderter Felder, Hydration-Gate im Vergleich.
6. **Anlegeseiten:** `TripNewEditor`/`CompareNewEditor` nutzen weiter `VersandTab`/`AlarmeTab`; 1c löscht nichts, was sie importieren. Der Server-400 bei unzulässigen Minuten ist dort die Sicherung; die Stundenwahl dort liefert nur Rasterwerte.
7. **Viele Alt-Tests (ca. 48 node-Tests, ca. 15 Playwright-Specs) auf VersandTab/AlarmeTab:** werden in 1c gezielt angepasst oder gelöscht; Löschen nur, wenn der Baustein nicht mehr importiert wird.
8. **Parallele Sitzung #2913:** Abgleich-Werkzeuge werden nicht angefasst, Konflikte werden über `origin/main` gelöst.
9. **Premium-SMS-Sicherheit:** Ein falsch gelesener Zustand könnte an ein fremdes Gerät senden. Die Sperre bei verfallener Rückadresse wird im Frontend **und** im Alarmversand geprüft (bestehender Gate-Code bleibt).

## LoC-Schätzung je Teilschritt

| Teilschritt | Inhalt | LoC (inkl. Tests) |
|---|---|---|
| 1a Backend | Raster Go+Python, Cron-Takt, Dedupe, `send_email`, Auflösung + Migration | ca. +350 / -60 |
| 1b Neubau | Organismen, Modell, Speicherer, Kataloge, Glossar, Übergangsblock, Marker, E2E | ca. +1500 / -250 |
| 1c Aufräumen | Alt-Bausteine und Alt-Tests löschen | ca. -1500 |

## Known Limitations

- Die Anlegeseiten zeigen bis zu einer späteren Scheibe weiter die alte Versand-/Alarm-Oberfläche.
- Der Übergangsblock ist bewusst unfertig und wird mit Teil 2 (Inhalt je Kanal) und S5 (Test schicken) abgebaut.
- Das Raster ist Viertelstunde; feinere Zeiten sind kein Ziel.
- Das Migrationsprotokoll (betroffene Abos von `scripts/migrate_2795_alert_metric_channels.py`) erscheint nur auf der Konsole; beim `--execute`-Lauf ist die Ausgabe zu sichern.
- Bis Teilschritt 1b schreibt die alte Oberfläche weiter `alert_metric_channels`; das Feld hat keine Wirkung mehr.
- Entfallene Prüfungen (per Design nicht mehr möglich, kein Testverlust): F005/F101 (Teilausfall disjunkter Kanalgruppen je Ort) sowie ac16/ac17, da es keine metrikgenauen Kanalgruppen mehr gibt.
- 1a-Ist-Umfang: 21 Produktiv-Dateien, ca. +455/-162 Produktiv-LoC (Schätzung der Tabelle oben: ca. 12 Dateien, +350/-60).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; angewendet werden ADR-0046, ADR-0049, ADR-0095, ADR-0097, ADR-0101, ADR-0104, ADR-0109, ADR-0112.
- **Rationale:** Die Spec setzt bestehende Entscheidungen um (Reiterstruktur 0109, ein Code für Trip/Orte 0097, Kanal-Parität 0095, Kanal-Schwelle 0046, Premium-SMS 0049, Read-Modify-Write 0101, Zweisprachigkeit 0104, Design-System 0112). Das Viertelstunden-Raster und der Wegfall von „Kanäle je Wettergröße“ sind Produktentscheidungen des PO vom 2026-11-12 innerhalb dieser ADRs; ADR-0046 bleibt die Grundlage, weil die Dringlichkeit je Kanal nun allein steuert.

## Changelog

- 2026-11-12: Initiale Fassung (Entwurf).
- 2026-11-13: Teilschritt 1a (Backend) umgesetzt. Tatsächlicher Umfang: 21 Produktiv-Dateien, ca. +455/-162 Produktiv-LoC (Schätzung: ca. 12 Dateien). Inhalt: Briefing-Zeiten im Viertelstunden-Raster (00/15/30/45) statt Kappung auf die volle Stunde; unzulässige Minute → HTTP 400 (Trip-POST/PUT, Preset-PUT); Lesen normalisiert nicht mehr auf die Stunde (nicht rasterkonformer Altwert wird beim Lesen auf die vorige Viertelstunde abgerundet, nicht zurückgeschrieben). Cron `briefing_dispatch` alle 15 Minuten (vorher stündlich), Fälligkeit in Minuten, Nachholfenster 3 h, Dedupe je (Abo, Slot, Ortstag). Neues Feld `send_email` für Compare-Presets (Go `*bool` omitempty, Python `bool=True`, fehlend = true). Tech-Lead-Entscheidung: `send_email=false` nimmt nur die E-Mail aus dem Briefing und aus dem GEERBTEN Orts-Alarm-Satz; ein explizit gesetztes `alert_channels.email` bleibt wirksam (Briefing- und Alarm-Spalte der Kanal-Tabelle sind getrennt). `alert_metric_channels` („Kanäle je Wettergröße“) wirkt nicht mehr: Alarmziele ergeben sich nur aus `alert_channels` + `alert_channel_thresholds`, auch alte `alert_rules[].channels` wirken nicht mehr; Go hält das Feld lesetolerant. `trip_alert.py` musste nicht geändert werden (liest `alert_metric_channels` nicht mehr). Migration `scripts/migrate_2795_alert_metric_channels.py` (Read-Modify-Write, Sicherung vorher, idempotent). Nutzertext-Änderung: i18n `versand.json` `"{stunde}:00"` → `"{stunde}"` (Uhrzeit jetzt HH:MM; Golden-Texte zeigen „06:00“ statt „6:00“). Bis 1b schreibt die alte Oberfläche noch `alert_metric_channels`, ohne Wirkung. Neue Tests: Zwei-Nutzer-Test Kanal-Auflösung (`tests/test_2795_alert_metric_channels_ignoriert.py`, Ersatz für das gelöschte ac24), Go-Test Trip-POST 06:50 → 400 (`internal/handler/zustellung_2795_test.go`).
