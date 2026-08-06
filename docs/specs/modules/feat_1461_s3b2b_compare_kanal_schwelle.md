---
entity_id: feat_1461_s3b2b_compare_kanal_schwelle
type: feature
created: 2026-08-06
updated: 2026-08-06
status: draft
version: "1.3"
tags: [alerts, channels, threshold, compare, epic-1458, issue-1461, s3b2b]
---

# Einstellbare Dringlichkeits-Schwelle je Alarm-Kanal — Ortsvergleiche (#1461 S3b-2b)

## Approval

- [x] Approved — PO „go", 2026-08-06 (v1.3, 18 ACs)

## Purpose

Die einstellbare Dringlichkeits-Schwelle je Alarm-Kanal (E-Mail · Telegram · SMS), die für Trips
seit S3b-2a wirkt, gilt künftig auch für Ortsvergleiche: der Nutzer stellt je Kanal eines
bestehenden Ortsvergleichs ein, ab welcher Dringlichkeit (gering · mittel · hoch) ihn eine
Alarm-Meldung dort erreicht. Eine Meldung, die auf einem Kanal unter der dort eingestellten
Schwelle liegt, geht auf diesem Kanal nicht raus, verschwindet aber nicht spurlos: sie steht im
Alarm-Protokoll und im nächsten Briefing als nicht zugestellt — dieselbe Sicherheitsleine wie beim
Trip. Die Stufe ist **beim Anlegen und im Vergleichs-Hub** einstellbar (PO-Entscheid 2026-08-06):
der Alarme-Schritt der Anlege-Maske zeigt ohnehin bereits die Telegram-/SMS-Schalter, die Stufe
gehört sichtbar dazu; ein dort gesetzter Wert überlebt das Anlegen. Ohne eigene Einstellung startet
jeder Kanal auf „gering". Zusätzlich behebt diese Scheibe zwei eingeschlossene Fehler, ohne die eine Wirkung
über die Oberfläche nicht nachweisbar wäre: den Regenradar-Alarm des Ortsvergleichs, der heute
ausschließlich per E-Mail geht, und einen bestätigten Speicher-Fehler, durch den die
Telegram-/SMS-Alarm-Schalter im Bearbeiten-Pfad des Vergleichs-Hubs beim Speichern verlorengehen.
Mit dieser Scheibe ist Issue #1461 vollständig abgeschlossen.

## Source

- **Dateien (geändert):** `src/services/compare_alert.py` · `src/services/compare_official_alert.py` ·
  `src/services/compare_radar_alert.py` · `src/output/renderers/comparison.py` ·
  `internal/model/compare_preset.go` · `internal/handler/compare_preset.go` ·
  `frontend/src/lib/components/compare/CompareTabs.svelte` (Prop `existingChannelThresholds`
  durchreichen) · `frontend/src/lib/components/compare/compareHubWizardBridge.ts` (Speicher-Bug +
  Schwellenfeld in `AlarmSnapshot`, `hydrateAlarmFieldsFromPreset`, `flushPendingAlarmSave`,
  `rollbackAlarmSnapshot`) · `frontend/src/lib/components/compare/compareWizardState.svelte.ts`
  (neues Feld `channelThresholds`, analog `metricAlertLevels`) ·
  `frontend/src/lib/components/compare/compareEditorSave.ts` (`NewComparePresetFields` +
  `buildNewComparePresetPayload()` + optionales Feld in `buildComparePresetSavePayload()`, Muster
  `metricAlertLevels`/`sendTelegram` an den bereits gemessenen Stellen) ·
  `frontend/src/lib/components/shared/AlarmeTab.svelte` (die Sichtbarkeits-Weiche für die
  Stufen-Auswahl entfällt ersatzlos — s. „Implementation Details") · `docs/reference/sms_format.md` ·
  `docs/reference/api_contract.md` · `docs/specs/modules/compare_official_alert_channels.md` ·
  `docs/adr/0046-alarm-kanal-schwelle.md` (Nachtrag) ·
  `docs/adr/0021-shared-deviation-alert-engine.md` (Nachtrag)
- **Dateien (Bestandsänderung, altes Soll → neues Soll):** `tests/tdd/test_compare_sms_official_alerts.py` ·
  `tests/tdd/test_compare_telegram_official_alerts.py`
- **Bereits geteilt, keine Änderung nötig:** `src/services/alert_channel_threshold.py`
  (`split_by_threshold`) · `src/services/alert_urgency.py` (`meets_or_exceeds`) ·
  `src/services/alert_log.py` (`append_entry` kennt `below_threshold_channels` bereits) ·
  `internal/model/trip.go` (liefert den Typ `AlertChannelThresholdsConfig`, selbes Go-Package) ·
  `frontend/src/lib/components/shared/AlertChannelPicker.svelte` und
  `alarme-tab/alertChannelState.ts` (Picker kennt `context` gar nicht, Zustand bereits geteilt) ·
  `frontend/src/lib/components/trip-detail/AlarmeScheduleTab.svelte` (reicht
  `existingChannelThresholds` bereits durch, unverändert) ·
  `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` (bindet `wiz` bereits an
  `AlarmeTab` — kein eigener Code nötig, die Wirkung entsteht über `CompareWizardState` und
  `AlarmeTab.svelte`, s. „Implementation Details")
- **Identifier:** `effective_compare_channels()` (`src/services/compare_alert_channels.py:28`),
  `AlertChannelThresholdsConfig` (`internal/model/trip.go:202`)
- **Schicht:** Python-Core (Naht an drei Compare-Alarmwegen + zwei Bericht-Filterstellen) ·
  Go-API (Datenmodell + Persistenz für `ComparePreset`, zwei Schreibwege) · Frontend (Oberfläche
  für den Vergleichs-Zweig, beide Speicherwege — Bearbeiten UND Anlegen — plus Speicher-Bugfix).
  **Bewusst ausgeklammert:** Trip-Code, `AlertChannelPicker.svelte`/`alertChannelState.ts` selbst
  (bereits geteilt).

## Estimated Scope

- **LoC:** ~205 Produktivcode (Tech-Lead-Schätzung aus der Analyse, inkl. der beiden
  Anlege-Speicherwege), ~950–1150 inkl. Tests
- **Files:** ~14 geändert
- **Effort:** medium — die Backend-Logik (`split_by_threshold`, Rangvergleich, Protokoll-Grund)
  steht bereits aus S3b-2a; neu sind Verdrahtung an drei Compare-Nahtstellen, ein Go-Feld mit zwei
  Schreibwegen und der Frontend-Speicherweg samt Bugfix und Anlege-Pfad

⚠️ Voraussichtlich `loc_limit_override = 1600` nötig (S3b-2a zum Vergleich: 2200 bei ~455 Zeilen
Produktivcode). Wird beim Erreichen erfragt, nicht hier vorab festgelegt.

## Dependencies

| Entity | Typ | Zweck |
|---|---|---|
| `feat_1461_s3b2a_kanal_schwelle` | wiederverwendet | `split_by_threshold()`, `meets_or_exceeds()`, Protokollgrund `below_channel_threshold`, das Go-Struct `AlertChannelThresholdsConfig`, der komplette Frontend-Zustand des Pickers — nichts davon wird neu gebaut |
| `feat_1461_s3a_alarm_dringlichkeit` | liest | `urgency_from_changes`/`urgency_from_official_level`/`urgency_from_radar` — bereits am Compare-Pfad verdrahtet (S3a hat ihn mitgezogen), liefert die Dringlichkeit je Compare-Alarm |
| `feat_1459_alert_protokoll` | erweitert (bereits generisch) | `alert_log.append_entry()` nimmt `below_threshold_channels` bereits entgegen, unabhängig von Trip oder Compare |
| `feat_1461_s3b1_briefing_sichtbarkeit` | nutzt | `undelivered_hint.py` zeigt den Grund automatisch für den Ortsvergleich, ohne Codeänderung |
| ADR-0046 `:101-108` | erfüllt Folgepflicht | *„Scope S3b-2a: nur Trips … der Ortsvergleich folgt als S3b-2b"* — diese Scheibe füllt die dort offengehaltene Lücke |
| ADR-0021 `:85-94` | grenzt ab, wird nachgetragen | Compare als zweiter Consumer derselben Engine, nimmt aber Tageslimit/Alert-Log/Radar-Onset-Pfad bisher aus — der Radar-Ausnahmefall wird mit dieser Scheibe geschlossen |
| `internal/model/compare_preset.go` (Muster `OfficialWarningsConfig`) | folgt | bereits geteilter Go-Typ über Dateigrenzen, derselbe Präzedenzfall wie beim Trip |
| `AlertChannelPicker.svelte:101` (`{#if thresholds}`) | grenzt ab | zeigt, wie die Sichtbarkeit heute schon richtig entschieden wird: an der Prop selbst, nicht an ihrem Inhalt — Vorbild für die Auflage in „Implementation Details" |
| `CompareWizardState.metricAlertLevels`/`officialWarningsEnabled` (`compareWizardState.svelte.ts:70`/`:68`) | folgt | Vorbild für ein weiteres `wiz`-Feld, das über beide Compare-Speicherwege (POST Anlegen, PUT Bearbeiten) läuft |

## Implementation Details

### Die Naht: drei Auflösungsstellen bei Ortsvergleichen, eine davon mit Verhaltensänderung

Genau wie beim Trip greift die Schwelle dort, wo das Kanal-Set für einen Ortsvergleichs-Alarm
**entsteht**, nie in der Versandschicht (ADR-0046 `:101-105`). Beim Ortsvergleich sind das drei
Stellen:

1. `compare_alert.py:334` — Vorhersage-Änderungsalarm.
2. `compare_official_alert.py:271` — amtliche Warnung.
3. `compare_radar_alert.py:131`/`:150` — Regenradar. **Heute hart auf `{"email"}` verdrahtet**,
   unabhängig vom Kanal-Opt-in des Nutzers. Diese Hartverdrahtung wird auf denselben Resolver
   (`effective_compare_channels()`) umgestellt wie die anderen beiden Wege — der Schwesterpfad
   `compare_alert.py` wurde bereits als vergleichbarer Bug korrigiert (#1467 S2 AG1), der
   Radar-Pfad blieb dabei vertagt. Das ist die einzige echte **Verhaltensänderung** dieser
   Scheibe: Regenradar-Alarme eines Ortsvergleichs erreichen künftig auch Telegram und SMS, nicht
   mehr nur E-Mail.

Alle drei Wege leiten ihre Dringlichkeit bereits korrekt ab (S3a hat sie mitgezogen), aber jeweils
**inline im `append_entry`-Argument**, also **nach** dem Versand. Die Ableitung wird deshalb je
Weg in eine lokale Variable vorgezogen — derselbe Handgriff, den S3b-2a beim Trip dreimal gemacht
hat.

🔴 **Schleifen-Falle in `compare_alert.py`:** das Kanal-Set entsteht einmal je Preset (`:334`),
der Versand läuft aber je Schleifendurchlauf über die Orte des Vergleichs (`:177-187`). Der Split
muss **innerhalb** der Schleife stehen und jeweils mit der Dringlichkeit **dieses** Durchlaufs
rechnen — sonst wird die Meldung eines Ortes an der Dringlichkeit eines anderen Ortes gemessen.
Bei einem Ortsvergleich, dem Normalfall dieser Entität, kann das genau dann passieren, wenn ein
Ort eine dringende und ein anderer eine geringfügige Meldung auslöst. Ein eigenes AC (AC-3)
macht diese Zusicherung aus Nutzersicht prüfbar — die Mutations-Gegenprobe allein zeigt nur, ob
ein Test die Mutation fängt, sie ersetzt den Test nicht.

⛔ **`scheduler_dispatch_service.py:409` ist keine vierte Naht.** Sie löst Kanäle für den
**Briefing**-Fanout auf, nicht für Alarme — dort darf `split_by_threshold` nicht greifen.

### Reihenfolge — unverändert das Herzstück: einstufen → protokollieren → versenden

Wie bei S3b-2a bleibt der an `append_entry` übergebene Wert das **rohe**, unveränderte
Kanal-Opt-in — nur der tatsächliche Versand wird gefiltert, plus eine zusätzliche Angabe, welche
Kanäle wegen der Schwelle ausgeschlossen wurden (`below_threshold_channels`). Der frühe Ausstieg
bei leerem Kanal-Set (`alert_log.py:173-175`) bleibt dadurch auf der rohen Größe — er feuert
weiter nur, wenn der Nutzer wirklich alle Kanäle abgeschaltet hat (rote Linie #638).

### Zwei Wirkungsorte, sauber getrennt

Die drei Alarm-Nahtstellen oben entscheiden **ob eine Alarm-Meldung** einen Kanal erreicht. Davon
getrennt: `MIN_SMS_LEVEL` entscheidet, welche amtlichen Warnungen im regulären
Kurznachrichten-**Bericht** eines Ortsvergleichs erscheinen — das ist kein Alarm-Versand. Zwei
Stellen, zwei verschiedene Bauformen:

- `src/output/renderers/comparison.py:735` — heute ein eigener Inline-Filtervergleich
  (`a.level >= MIN_SMS_LEVEL`), ruft die geteilte Funktion gar nicht auf; der feste
  Vergleichswert wird durch die Nutzereinstellung ersetzt.
- `src/output/renderers/comparison.py:900` — ruft bereits `official_alerts_to_sms_entries(...)`,
  aber **ohne** den seit S3b-2a existierenden Parameter `min_level`
  (`alert/official_alerts.py:370`); der Aufruf bekommt ihn.

Startwert `LOW` ⇒ der Bericht zeigt künftig auch gelbe (Stufe 2) amtliche Warnungen eines
Ortsvergleichs, die er vorher nie zeigte — der Alarm-**Versand** bleibt davon unberührt (dieselbe
Auflösung des Zielkonflikts wie beim Trip, PO-Entscheidung 2026-08-05).

### Datenmodell — bestehender Go-Typ, aber umgekehrte Verlustpolarität

`AlertChannelThresholdsConfig` liegt bereits in `internal/model/trip.go:202`, `ComparePreset` in
`internal/model/compare_preset.go:14` — dasselbe Go-Package, kein neuer Typ, kein Import. Neu ist
ein Pointer-Feld auf `ComparePreset`, nach demselben Muster wie das bestehende
Warnungs-Unterobjekt (`OfficialWarnings`, `compare_preset.go:90`).

🔴 **`UpdateComparePresetHandler` dekodiert anders als der Trip-Handler — der
Datenverlustschutz ist deshalb Pflicht, nicht automatisch:**

| | Trip | ComparePreset |
|---|---|---|
| Decode-Ziel | Pointer-DTO | volles `model.ComparePreset` (`compare_preset.go:320-324`) |
| Muster | `if req.X != nil { existing.X = req.X }` | `if updated.X == nil { updated.X = original.X }` |
| Feld ohne Preserve-Zeile | bleibt erhalten | **geht verloren** |

Der neue Preserve-Block braucht **Objekt-Ebene und drei Kanal-Ebenen** (Muster
`OfficialWarnings.Sources`, `compare_preset.go:396-406`) — Präzedenzfall für den Verlustfall ohne
diesen Block: `OutlookEnabled` (#1361/#1368). **Zwei Schreibwege** existieren:
`PUT /api/compare/presets/{id}` (Handarbeit, dieser Block) und
`PUT /api/briefings/{id}?kind=vergleich` (`mergeBriefingPatch` trägt neue Felder generisch —
trotzdem mit Test zu belegen, nicht anzunehmen). Python braucht keine Modelländerung:
`preset.raw` reicht den neuen Schlüssel unverändert durch (`loader.py:238-243`/`:341-349`).

### Oberfläche — Drei-Stellen-Sperre lösen, für alle vier Flächen

Der geteilte Kanal-Picker ist **einmal** eingebettet (`AlarmeTab.svelte:330`) und schlägt auf vier
Flächen durch: den Trip-Alarm-Reiter (`AlarmeScheduleTab.svelte:46`, `context="route"`), den
Vergleichs-Hub (`CompareTabs.svelte:1422`) und beide Anlege-Masken
(`CompareNewEditor.svelte:412`/`:499`, Desktop und Mobil). Die Stufen-Zeile erscheint schlicht dann,
wenn die Prop `thresholds` gesetzt ist (`AlertChannelPicker.svelte:101`, `{#if thresholds}` — der
Picker kennt `context` gar nicht); die heutige Weiche in `AlarmeTab.svelte:333-334` fragt dagegen
`context === 'route'`, und der Änderungs-Handler bricht bei `context === 'vergleich'` sofort ab
(`:216`).

**PO-Entscheid 2026-08-06: alle vier Flächen zeigen die Stufen-Auswahl**, und ein in der
Anlege-Maske gesetzter Wert überlebt das Anlegen. Der Alarme-Schritt der Anlage zeigt bereits die
Telegram-/SMS-Schalter — eine Kanal-Zeile ohne die zugehörige Stufe wäre dort die auffälligere
Inkonsistenz. Der Trip ist dabei **kein** Gegenargument: `trip-new/` bettet überhaupt keinen
Alarm-Bereich ein, es gibt dort also keine Fläche, zu der man symmetrisch sein könnte.

Begründung für die Umsetzbarkeit: `CompareWizardState` (`compareWizardState.svelte.ts`) trägt
bereits mehrere Alarm-Felder exakt in der Form, die eine Kanal-Schwelle bräuchte —
`metricAlertLevels` (`:70`, ein `Record<string, string>`) und `officialWarningsEnabled` (`:68`) —
und beide werden in `saveNewPreset()` (`:107-154`) unverändert in den POST-Body übernommen sowie
im Hub über `flushPendingAlarmSave`/`AlarmSnapshot` (`compareHubWizardBridge.ts:507-564`) in den
PUT-Body. Ein neues Feld `channelThresholds` folgt demselben, bereits etablierten Muster — keine
neue Architektur. `CompareNewEditor.svelte` selbst braucht **keine** Codeänderung: es bindet
`wiz` bereits ein, die Wirkung entsteht ausschließlich über `CompareWizardState` und die
`AlarmeTab`-Weiche.

Damit fällt die heutige `context`-Weiche ersatzlos, statt durch eine feinere ersetzt zu werden.

🔴 **Auflage an die Umsetzung: die Sichtbarkeit darf nicht vom Wert einer Prop abhängen.** Ein
bestehender Trip oder Ortsvergleich **ohne** gesetzte Schwellen liefert `existingChannelThresholds`
als `null`/`undefined`. Eine wertbasierte Bedingung ließe die Auswahl dort fälschlich verschwinden —
ein Regress auf AC-10 aus S3b-2a. Zugesichert ist: **Trip-Alarm-Reiter, Vergleichs-Hub und beide
Anlege-Masken zeigen die Auswahl**, unabhängig davon, ob bereits ein Wert gesetzt ist.

Die konkrete Bauform legt diese Spec **nicht** fest — das ist Sache der Umsetzung; festgelegt ist
ausschließlich die Zusicherung aus dem vorigen Absatz.

🔴 **Der bestätigte, unabhängige Speicher-Fehler auf dem Hub-Pfad bleibt bestehen und wird mit
demselben Umbau behoben:** `AlarmSnapshot` (`compareHubWizardBridge.ts:507-518`) führt
`sendTelegram`/`sendSms` nicht in seinen Feldern. Eine Kanal-Umschaltung im Bearbeiten-Pfad des
Vergleichs-Hubs ist deshalb weder als Speicher-Differenz erkennbar noch im PUT-Body enthalten —
stattdessen werden die alten Server-Werte aktiv zurückgeschrieben, und beim Wechsel in den
Versand-Reiter springt der Schalter sichtbar zurück. Der **Anlegen**-Pfad ist von diesem
speziellen Fehler nicht betroffen (`compareWizardState.svelte.ts:120-121` nimmt die dortigen
Versand-Kanäle korrekt auf — das betrifft `sendTelegram`/`sendSms` für den Bericht, nicht die
hier neue Alarm-Schwelle). Ohne den Bugfix ist ein Wirkungs-Nachweis der neuen
Schwellen-Oberfläche über den Hub-Bearbeiten-Pfad strukturell nicht erbringbar — deshalb gehört
der Fix in diese Scheibe, mit eigenem AC und eigenem Repro-Test (rot vor, grün nach dem Fix).

### ⚠️ Betriebshinweis: Renderer-Commit-Gate (#811) und Pendant-Sperre (#1481 B)

`comparison.py` steht **nicht** auf der Sperrliste des Renderer-Gates; `alert/official_alerts.py`
(bereits durch S3b-2a berührt) und `email/compare_html.py` **schon** — bei Berührung greift
dasselbe Zwei-Nachweis-Gate wie bei S3b-2a. Die Pendant-Sperre (#1481 B) betrifft diese Scheibe
nicht: der Picker ist bereits geteilt, es ist keine neue Datei unter `compare*/` nötig.

## Expected Behavior

- **Input:** eine ausgelöste Alarm-Meldung eines Ortsvergleichs (Δ-Änderung, Regenradar oder
  amtliche Warnung) mit ihrer Dringlichkeit, das rohe Kanal-Opt-in des Ortsvergleichs, die je
  Kanal eingestellte Schwelle (Vorgabe „gering", wenn nichts eingestellt).
- **Output:** Versand nur an die Kanäle, die die Schwelle erreichen; ein Protokoll-Eintrag mit
  dem unveränderten rohen Opt-in plus der Information, welche Kanäle wegen der Schwelle
  ausgeschlossen wurden; im nächsten Briefing eine Zeile für jede vollständig unterdrückte
  Meldung; im Kurznachrichten-Bericht des Ortsvergleichs erscheinen amtliche Warnungen ab der
  eingestellten Stufe.
- **Side effects:** Speichern der Kanal-Schwellen eines **bestehenden** Ortsvergleichs im
  Vergleichs-Hub schreibt ein neues Unterobjekt am `ComparePreset`, ohne bestehende Felder zu
  berühren; der zuvor bestätigte Speicher-Fehler bei den Telegram-/SMS-Alarm-Schaltern im
  Bearbeiten-Pfad ist behoben. Die Anlege-Maske eines neuen Ortsvergleichs zeigt die
  Stufen-Auswahl ebenfalls; ein dort gesetzter Wert wird beim Aktivieren mitgespeichert, ohne
  eigene Einstellung startet jeder Kanal auf „gering". Am Versandverhalten eines Trips ändert
  sich nichts.

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleich hat für keinen Kanal eine Schwelle eingestellt / When ein
  Alarm (gleich welcher Art) mit geringer Dringlichkeit ausgelöst wird / Then erreicht die
  Meldung genau die Kanäle, die sie auch vor dieser Änderung erreicht hätte — kein Kanal wird
  stiller.
  - Test: Versandzähler je Kanal für denselben Alarm-Lauf mit unverändertem Ortsvergleich (keine
    gesetzte Schwelle) vor und nach der Änderung vergleichen.

- **AC-2:** Given ein Nutzer hat für einen Kanal eines Ortsvergleichs eine höhere als die
  geringste Dringlichkeit eingestellt / When eine durch eine Wetteränderung ausgelöste
  Alarm-Meldung geringerer Dringlichkeit eintritt / Then erreicht sie diesen einen Kanal nicht,
  während ein anderer, unveränderter Kanal sie weiterhin bekommt.
  - Test: Ortsvergleich mit erhöhter Schwelle auf einem Kanal, Änderungsalarm mit geringer
    Dringlichkeit auslösen, Zustellung je Kanal einzeln prüfen.

- **AC-3:** Given ein Ortsvergleich mit mehreren Orten hat für einen Kanal eine erhöhte Schwelle
  eingestellt / When bei einem Alarm-Lauf ein Ort eine Meldung hoher Dringlichkeit auslöst und
  ein anderer Ort eine Meldung geringer Dringlichkeit / Then erreicht dieser Kanal die dringende
  Meldung, aber nicht die geringe — jede Meldung wird an ihrer eigenen Dringlichkeit gemessen,
  nicht an der eines anderen Ortes desselben Vergleichs.
  - Test: einen Ortsvergleich mit mindestens zwei Orten so präparieren, dass ein Alarm-Lauf für
    einen Ort eine hohe und für einen anderen Ort eine geringe Dringlichkeit erzeugt; bei
    erhöhter Kanal-Schwelle die Zustellung je Meldung getrennt prüfen — nicht nur den letzten
    Durchlauf der Schleife.

- **AC-4:** Given ein Nutzer hat für einen Kanal eines Ortsvergleichs eine höhere Schwelle
  eingestellt / When eine amtliche Warnung geringerer Dringlichkeit einen Alarm auslöst / Then
  bleibt dieser Kanal ebenso stumm wie bei einer durch Wetteränderung ausgelösten Meldung.
  - Test: den amtliche-Warnung-Alarmpfad des Ortsvergleichs separat durchlaufen lassen,
    Zustellung je Kanal prüfen.

- **AC-5:** Given ein Ortsvergleich hat Telegram oder SMS als Alarm-Kanal eingeschaltet / When
  ein durch Regenradar ausgelöster Alarm eintritt / Then erreicht die Meldung diese Kanäle jetzt
  ebenso wie E-Mail — vor dieser Änderung ging ein Regenradar-Alarm eines Ortsvergleichs
  ausschließlich per E-Mail raus.
  - Test: Regenradar-Alarmpfad eines Ortsvergleichs mit Telegram und SMS eingeschaltet auslösen,
    Zustellung auf allen drei Kanälen nachweisen — vor dem Fix nur auf E-Mail.

- **AC-6:** Given ein Nutzer hat für einen Kanal eines Ortsvergleichs eine höhere Schwelle
  eingestellt / When ein durch Regenradar ausgelöster Alarm geringerer Dringlichkeit auftritt /
  Then bleibt dieser Kanal ebenso stumm wie bei den beiden anderen Alarmarten des Ortsvergleichs.
  - Test: den Regenradar-Alarmpfad separat durchlaufen lassen, Zustellung je Kanal gegen dieselbe
    Schwelle prüfen wie in AC-2/AC-4.

- **AC-7:** Given eine Meldung eines Ortsvergleichs liegt auf jedem eingeschalteten Kanal unter
  der dort eingestellten Schwelle / When der Alarm ausgelöst wird / Then steht sie danach im
  Alarm-Protokoll und erscheint als nicht zugestellt im nächsten Briefing dieses Ortsvergleichs.
  - Test: Ortsvergleich mit hoher Schwelle auf allen Kanälen, Alarm mit geringer Dringlichkeit
    auslösen; Protokolldatei auf einen Eintrag prüfen, danach das Vergleichs-Briefing rendern und
    die Zeile im erzeugten Text nachweisen.

- **AC-8:** Given eine Meldung eines Ortsvergleichs wurde wegen der Kanal-Schwelle unterdrückt /
  When das nächste Briefing erzeugt wird / Then nennt die dafür erzeugte Zeile denselben
  verständlichen, deutschen Grund wie beim Trip — keinen internen Bezeichner.
  - Test: erzeugten Vergleichs-Mail-Text prüfen: ein lesbares Wort steht dort, keine rohe
    Konstante wie ein englischer Code-Bezeichner.

- **AC-9:** Given ein Nutzer hat für einen Kanal eines Ortsvergleichs eine erhöhte Schwelle
  gesetzt / When er anschließend über die Oberfläche eine andere Einstellung des Vergleichs
  ändert und speichert, ohne dass dabei die Schwellen-Einstellung mitgeschickt wird / Then bleibt
  seine Schwellen-Einstellung unverändert erhalten.
  - Test: über beide Schreibwege (`PUT /api/compare/presets/{id}` und
    `PUT /api/briefings/{id}?kind=vergleich`) je einmal: Ortsvergleich mit gesetzter Schwelle
    anlegen, eine andere Einstellung ohne das Schwellenfeld senden, Ortsvergleich danach neu
    laden, Schwelle unverändert vorfinden.

- **AC-10:** Given ein Nutzer hat für zwei Kanäle eines Ortsvergleichs je eine eigene Schwelle
  gesetzt / When er über die Oberfläche nur einen der beiden Kanäle ändert und speichert / Then
  bleibt die Schwelle des anderen, nicht angefassten Kanals unverändert.
  - Test: Speicher-Aufruf mit nur einem geänderten Kanal-Wert im Schwellen-Unterobjekt senden,
    den unveränderten Kanal danach prüfen.

- **AC-11:** Given zwei verschiedene Nutzer haben für ihre jeweils eigenen Ortsvergleiche
  unterschiedliche Kanal-Schwellen eingestellt / When bei beiden im selben Testlauf ein Alarm
  ausgelöst wird / Then wirkt bei jedem Nutzer ausschließlich seine eigene Einstellung — keine
  Vermischung, in beiden Richtungen geprüft.
  - Test: zwei getrennte Nutzer-Datenordner, je eigener Ortsvergleich und Schwelle, beide Läufe
    wechselseitig prüfen (Nutzer A bekommt nicht Nutzer Bs Schwelle und umgekehrt).

- **AC-12:** Given ein Alarm-Lauf eines Ortsvergleichs erzeugt sowohl zugestellte als auch wegen
  der Schwelle unterdrückte Meldungen / When die Cockpit-Kachel und die Archiv-Statistik danach
  abgefragt werden / Then zeigen sie dieselben Zahlen wie vor dieser Änderung.
  - Test: die für Kachel und Statistik maßgeblichen Protokoll-Einträge vor und nach dem Patch für
    denselben Ablauf zählen und vergleichen.

- **AC-13:** Given ein Nutzer öffnet die Alarm-Einstellungen eines bestehenden Ortsvergleichs im
  Vergleichs-Hub / When er dort für jeden der drei Kanäle eine Stufe ändert, speichert und die
  Seite danach neu lädt / Then steht für jeden Kanal genau der zuletzt eingestellte Wert da —
  nicht nur, dass eine Auswahl angezeigt wird.
  - Test: die Hub-Oberfläche öffnen, für jeden Kanal einen Wert ändern, speichern auslösen, Seite
    neu laden (bzw. Zustand frisch vom Server abrufen), geänderten Wert je Kanal nachweisen.

- **AC-14:** Given ein Nutzer legt einen neuen Ortsvergleich an und setzt dort im Alarme-Schritt
  für einen Kanal eine höhere Stufe als „gering" / When er den Vergleich aktiviert und danach
  öffnet / Then steht für diesen Kanal genau die beim Anlegen gesetzte Stufe — nicht der
  Startwert.
  - Test: die Anlege-Maske durchlaufen, im Alarme-Schritt für einen Kanal eine höhere Stufe
    setzen, den Vergleich aktivieren, den entstandenen Ortsvergleich neu laden und den
    gespeicherten Wert je Kanal nachweisen (der ungeänderte Kanal steht weiterhin auf „gering").

- **AC-15:** Given ein Nutzer ändert im Alarme-Reiter eines bestehenden Ortsvergleichs den
  Telegram- oder SMS-Schalter / When er speichert und danach den Reiter erneut öffnet oder die
  Seite neu lädt / Then steht die geänderte Schalterstellung weiterhin so, wie er sie eingestellt
  hat — sie springt nicht auf den vorherigen Wert zurück.
  - Test: Repro-Test aus Nutzersicht, der den bestätigten Speicher-Fehler vor dem Fix rot zeigt
    (Schalter fällt auf den alten Wert zurück bzw. der Speicher-Aufruf enthält den geänderten
    Wert nicht) und nach dem Fix grün ist.

- **AC-16:** Given ein Trip ist von dieser Änderung nicht betroffen / When dort ein Alarm
  ausgelöst wird oder die Trip-Oberfläche geöffnet und gespeichert wird / Then verhalten sich
  Versand, Protokoll und Bericht des Trips exakt wie vor dieser Änderung — unabhängig davon,
  welche Kanal-Schwellen bei Ortsvergleichen gesetzt sind.
  - Test: den Trip-Alarmpfad mit unveränderten Zähl- und Protokollwerten vor/nach dem Patch
    durchlaufen lassen; zusätzlich die Trip-Oberfläche öffnen und speichern, ohne dass ein Fehler
    auftritt oder sich ihr Verhalten ändert.

- **AC-17:** Given ein Nutzer hat für einen Kanal eines Ortsvergleichs die Startschwelle (gering)
  unverändert gelassen / When der reguläre Kurznachrichten-Bericht (SMS und Telegram) dieses
  Vergleichs eine gelbe amtliche Warnung (Stufe 2) enthält / Then erscheint diese Warnung jetzt in
  beiden Berichtsformaten dieses Ortsvergleichs, wo sie vorher fehlte.
  - Test: die SMS- und die Telegram-Kurznachricht des Ortsvergleichs mit einer gelben amtlichen
    Warnung je einzeln erzeugen, den entsprechenden Eintrag in beiden Ergebnissen nachweisen —
    vorher waren beide leer.

- **AC-18:** Given ein Ortsvergleich hat für einen Kanal keine Schwelle über gering gesetzt / When
  eine gelbe amtliche Warnung (Stufe 2) einen Alarm auslöst / Then wird die Alarm-Meldung
  genauso verschickt wie vor dieser Änderung — das Aufgehen der Berichtsschwelle (AC-17)
  verändert den Alarm-Versand nicht.
  - Test: Versandzähler und Protokolleintrag für diesen Alarm vor und nach dem Patch vergleichen,
    unabhängig vom Ergebnis von AC-17.

## Known Limitations

- **Der Trip-Anlegepfad bleibt unverändert.** `trip-new/` bettet weiterhin überhaupt keinen
  Alarm-Bereich ein; ein neu angelegter Trip startet auf „gering" je Kanal. Das anzugleichen wäre
  eigene Arbeit am Trip und gehört nicht in diese Scheibe.
- **Die Trip-Trennung `alert_channels` wird für den Ortsvergleich nicht nachgezogen.** Der
  Ortsvergleich löst seine Alarm-Kanäle weiterhin über dieselben Schalter auf, die auch den
  Briefing-Versand steuern (Legacy-Verhalten, das der Trip mit `alert_channels = nil` ebenfalls
  kennt). Eine eigene Trennung wäre eine eigene Produktentscheidung, unabhängig vom
  Schwellen-Thema.
- **Kein neues ADR.** ADR-0046 `:106-108` hat die Lücke bereits als „folgt in S3b-2b" ausgewiesen;
  diese Scheibe trägt einen Nachtrag in ADR-0046 (Scope-Zeile) und ADR-0021
  (Radar-Onset-Ausnahme entfällt) nach.
- **Keine Validierung der Stufenwerte.** Weiterhin nirgends — Go nimmt jeden String an, Python
  degradiert unbekannte Werte auf Rang „gering". Symmetrie zur Trip-Seite; eine neue Validierung
  bräuchte nach Regel-Budget ein eigenes Prüfdatum.
- **Die noch ungenutzten Protokoll-Gründe** (Ruhezeit, Tageslimit, Sperrzeit) bleiben unverändert
  unbenutzt.
- **Kein neuer Alarm-Auslöser, keine neue Empfindlichkeitsstufe** — wie bei S3b-2a entscheidet die
  Kanal-Schwelle nicht, OB eine Lage meldenswert ist, nur AUF WELCHEM Weg eine bereits ausgelöste
  Meldung ankommt.
- **Teil-Unterdrückung innerhalb eines Laufs erscheint nicht im Briefing.** Erreicht eine Meldung
  einen Kanal für mindestens einen Ort, gilt der Kanal für diesen Lauf als zugestellt — die
  Unterdrückung für einen anderen Ort desselben Laufs erzeugt keine Hinweiszeile. Ursache ist das
  Protokollmodell aus #1459: ein Eintrag je Preset-Lauf auf Kanal-Ebene, während die Schwelle je
  Ort wirkt (`alert_log.py:113-132` überspringt zugestellte Kanäle vor der Grund-Prüfung). Gemessen
  am AC-3-Fall (Graz hoch, Wien gering, Telegram-Schwelle hoch): der Protokoll-Eintrag trägt
  `"channels_sent": ["email", "telegram"]`, `"channels_not_sent": [{"channel": "sms", "reason":
  "channel_disabled"}]` — Telegram fehlt in `channels_not_sent` vollständig, obwohl die Meldung für
  Wien unterdrückt wurde. Das nächste Briefing zeigt dafür keine Zeile. **Keine Falschmeldung,
  sondern eine fehlende** — der vollständige Ausfall, um den es die Sicherheitsleine des Issues
  geht, ist abgedeckt (AC-7 und die beiden Pendants für den amtlichen und den Radar-Pfad, alle drei
  per Mutations-Gegenprobe belegt). Eine Behebung verlangt das Protokoll auf Ort-Ebene statt
  Kanal-Ebene — ein Schema-Umbau an #1459 mit Folgen für Cockpit-Kachel, Archiv-Statistik und die
  Briefing-Darstellung — und ist eigene Arbeit, kein Nachtrag dieser Scheibe.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0046 (Nachtrag, kein neues ADR) — `docs/adr/0046-alarm-kanal-schwelle.md:106-108`
  (Scope-Zeile „S3b-2a: nur Trips" wird um den jetzt erledigten Ortsvergleich-Teil ergänzt);
  zusätzlich Nachtrag zu ADR-0021 `docs/adr/0021-shared-deviation-alert-engine.md:91-94`
  (der Radar-Onset-Pfad ist mit dieser Scheibe kein Trip-Sonderweg mehr).
- **Rationale:** Die Entscheidung selbst — Kanal-Schwelle als von der Empfindlichkeitsstufe
  unabhängiger Regler, rohes Kanal-Set ans Protokoll, gefiltertes an den Versand — ist mit
  ADR-0046 bereits getroffen und gilt unverändert für beide Entitäten (ADR-0021 `:85-94` schließt
  den Ortsvergleich als zweiten Consumer derselben Engine ausdrücklich ein). Diese Scheibe füllt
  nur die dort offen gelassene Scope-Lücke; ein neues ADR wäre eine unnötige zweite Quelle für
  dieselbe Entscheidung.

## Changelog

- 2026-08-06: Initial spec (v1.0) — auf Basis von
  `docs/context/feat-1461-s3b2b-compare-kanal-schwelle.md`, Vorlage
  `feat_1461_s3b2a_kanal_schwelle.md` (11 von 13 ACs 1:1 übertragbar, AC-3/AC-11 dort waren
  trip-spezifisch).
- 2026-08-06: Review-Nachbesserung (v1.1) — drei Team-Lead-Befunde adressiert: Anlege-Masken
  zunächst auf „mitnehmen" (Option a) entschieden, AC-3 für die Schleifen-Falle ergänzt,
  AC-15/AC-16 (heute AC-17/AC-18) und AC-13 (heute AC-15) konkretisiert.
- 2026-08-06: Korrektur (v1.2) — Entscheidung zu Punkt 1 nach erneuter Messung durch den
  Team-Lead umgedreht: **Option b statt a.** Die Anlege-Masken bekommen **keinen** Speicherweg
  für die Schwelle — Symmetrie zum Trip (`trip-new/` bettet ebenfalls keinen Alarm-Bereich ein),
  statt eine neue Asymmetrie zu schaffen. `compareWizardState.svelte.ts`/`compareEditorSave.ts`
  sind damit wieder aus dem Scope, `CompareNewEditor.svelte` bleibt unverändert. Neue Auflage in
  „Implementation Details": die Weiche in `AlarmeTab.svelte` muss eine Fähigkeit des jeweiligen
  Mounts abfragen — weder `context` noch den Wert von `existingChannelThresholds` (Regress auf
  AC-10 aus S3b-2a) —, die konkrete Bauform bleibt bewusst offen. AC-14 umformuliert: beobachtbare
  Abwesenheit der Auswahl beim Anlegen plus Startwert „gering" nach dem Anlegen, statt eines beim
  Anlegen gesetzten Werts. Estimated Scope entsprechend zurückgenommen (~185 LoC / ~13 Dateien).
  Punkte 2 (AC-3) und 3 (Wortwahl) aus v1.1 unverändert übernommen.
- 2026-08-06: **PO-Entscheid (v1.3)** — die Stufen-Auswahl erscheint auf **allen vier** Flächen,
  auch in den beiden Compare-Anlege-Masken, und ein dort gesetzter Wert überlebt das Anlegen.
  Damit ist die in v1.2 getroffene Gegenentscheidung abgelöst. Vorgelegt wurden beide Varianten
  mit Skizze; der Ausschlag gab, dass der Alarme-Schritt der Anlage die Kanal-Schalter ohnehin
  zeigt. Das in v1.2 tragende Argument „Symmetrie zum Trip" war unzutreffend — `trip-new/` hat
  dort gar keine Fläche, zu der man symmetrisch sein könnte. Folge: die `context`-Weiche in
  `AlarmeTab.svelte:333-334` fällt ersatzlos statt ersetzt zu werden;
  `compareWizardState.svelte.ts`/`compareEditorSave.ts` sind wieder im Umfang; AC-14 prüft wieder
  den beim Anlegen gesetzten Wert; Source-Liste und Estimated Scope entsprechend auf den v1.1-Stand
  zurückgeführt (kein Fähigkeits-Signal, ~205 LoC / ~14 Dateien). **Unverändert aus v1.2
  übernommen:** die Auflage, dass die Sichtbarkeit nicht vom Wert einer Prop abhängen darf (sonst
  Regress auf AC-10 aus S3b-2a). PO-„go" liegt vor (Approval-Checkbox oben).
