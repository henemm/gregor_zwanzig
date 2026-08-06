# Context: feat-1461-s3b2b-compare-kanal-schwelle

**Issue:** #1461 (Alerts S3), Scheibe **S3b-2b** — Epic #1458, Scheibe 3 von 5
**Vorgänger:** S3a (`cf7d8fc0`) · S3b-1 (`c8fbb3e9`) · **S3b-2a** (`2e89263c`, live seit 2026-08-05)
**Branch:** `feat/1461-s3b2b-compare-kanal-schwelle` auf `635fe754`

## Request Summary

Die einstellbare Dringlichkeits-Schwelle je Alarm-Kanal, die für **Trips** seit S3b-2a wirkt,
soll auch für **Ortsvergleiche** gelten. Damit ist Bedingung (a) des Relevanz-Filters aus #1458
— *der Nutzer will darüber auf diesem Kanal informiert werden* — für beide Entitäten erfüllt und
#1461 abgeschlossen.

**Zuschnitt-Entscheid des PO (2026-08-05, [#1461#issuecomment-5196900445]):** Diese Arbeit stand
doppelt gebucht — auch **#1463** (Alerts S5) führte „Kanal-Schwelle aus Scheibe 3 auch dort
wirksam" in seinem Umfang. Sie wird hier gebaut; #1463 ist auf Grenzwert-Melder + Zeitbezug
verkleinert ([#1463#issuecomment-5196903167]).

---

## Vorbemerkung: Diese Scheibe war bereits mitanalysiert

`docs/context/feat-1461-s3b2-kanal-schwelle.md` (441 Zeilen, in `main`) enthält ab `:240` eine
Analyse, die S3b-2a **und** S3b-2b abdeckt, inklusive Zuschnitt-Tabelle (`:350`). Vier
unabhängige Recherchen haben sie gegen den **heutigen** Code gegengeprüft. Dieses Dokument hält
fest, was sich als überholt erwiesen hat und was hinzugekommen ist.

**Aus S3b-2a fertig übernehmbar, nichts neu zu bauen:** `split_by_threshold()` ·
`meets_or_exceeds()` / `min_official_level_for_threshold()` · Protokollgrund
`below_channel_threshold` samt deutschem Label · die S3b-1-Sichtbarkeit inkl. Compare-HTML
**und** -Klartext · das Go-Struct `AlertChannelThresholdsConfig` · der Feld-Level-Merge als
Vorlage · der komplette Frontend-Zustand (`alertChannelState.ts`, `alarmeDeliveryPayload.ts`,
`AlertChannelPicker.svelte`) · alle vier PO-Entscheidungen.

---

## Related Files

### Python — die Naht

| Datei:Zeile | Rolle | Ruft den Resolver? |
|---|---|---|
| `src/services/compare_alert_channels.py:28-36` | `effective_compare_channels()` — die **eine** Compare-Kanalregel (#1467 S2 AG1 hat zwei Duplikate ersetzt) | — (ist der Resolver) |
| `src/services/compare_alert.py:334` | Änderungsalarm, Direktaufruf | ja |
| `src/services/compare_official_alert.py:271` | amtliche Warnung | ja (Wrapper) |
| 🔴 `src/services/compare_radar_alert.py:131` **und** `:150` | Radar/Nowcast — **hart `{"email"}`** | **nein** |
| ⛔ `src/services/scheduler_dispatch_service.py:409` | **Briefing**-Fanout — **KEINE Alarm-Naht** | ja (Wrapper) |

⛔ **`scheduler_dispatch_service.py:409` ist eine Falle, keine Naht.** Sie löst die Kanäle für den
**Briefing**-Versand auf. Dort darf `split_by_threshold` **nicht** greifen — die Einstellung wirkt
im Briefing über den Inhalt (`comparison.py:735`/`:900`), nicht über die Kanalauswahl. Ein Filter
an dieser Stelle würde den Ortsvergleichs-**Bericht** stummschalten, obwohl nur Alarme gemeint
sind. **Drei Alarm-Nahtstellen, nicht vier.**

🔴 **Und in `compare_alert.py` liegt eine Schleifen-Falle:** das Kanal-Set entsteht **einmal je
Preset** (`:334`), versendet wird aber **je Schleifendurchlauf** (`:177-187`). Ein
`split_by_threshold` außerhalb der Schleife filtert mit **fremder** Dringlichkeit — der Split muss
dorthin, wo die Dringlichkeit des jeweiligen Durchlaufs feststeht. **Pflicht-Ziel der
Mutations-Gegenprobe.**

**Die Zählung im alten Dokument („vier Auflösungsstellen") war zu niedrig.** Allein die
Trip-Seite hat drei (`trip_alert.py:878`, `:1022`, `:1181` — die dritte fand erst der Adversary).
Compare hat drei weitere. Die Lehre aus S3b-2a gilt unverändert: **Naht-Stellen zählen, nicht
schätzen.**

### Python — der geteilte Baustein (unverändert nutzbar)

`src/services/alert_channel_threshold.py:20-35` — `split_by_threshold(channels, urgency,
thresholds) -> (erlaubt, unterdrückt)`. **Bereits generisch:** nimmt rohe Mengen und Dicts, kennt
keine Trip-Objekte. Nichts daran zu ändern.
Rangvergleich: `src/services/alert_urgency.py:63-68` · Stufen-Abbildung `:74-80`.

### Python — `MIN_SMS_LEVEL` für Compare-Berichte

🔴 **Die Zeilenangaben im alten Dokument (`:704`/`:869`) stimmen nicht.** Gemessen:

| Stelle | Bauform | Was zu tun ist |
|---|---|---|
| `src/output/renderers/comparison.py:735` | **eigener Inline-Filter** (`a.level >= MIN_SMS_LEVEL`), ruft die Funktion gar nicht | Vergleichswert ersetzen — **kein** Parameter ergänzbar |
| `src/output/renderers/comparison.py:900` | `official_alerts_to_sms_entries(...)` **ohne** `min_level` | Parameter übergeben |

Der Parameter heißt `min_level` und existiert bereits: `src/output/renderers/alert/official_alerts.py:370`.
**Zwei Stellen, zwei verschiedene Bauformen** — nicht eine Änderung zweimal.
Trip-Vorlage: `src/output/renderers/sms_trip.py:161`. `narrow.py:386` ruft die Funktion **nicht**
auf, sondern filtert selbst (`:412-419`) — Telegram und SMS sind getrennt zu verdrahten.

### Go

| Datei:Zeile | Befund |
|---|---|
| `internal/model/trip.go:151`, Struct `:202-206` | `AlertChannelThresholds *AlertChannelThresholdsConfig` — die Vorlage |
| `internal/model/compare_preset.go:91-92` | nur `SendTelegram *bool` / `SendSms *bool`; **kein** `alert_channels`-Pendant, E-Mail implizit immer an |
| `internal/model/compare_preset.go:90` | `OfficialWarnings *OfficialWarningsConfig` — **derselbe Typ wie Trip**, der Präzedenzfall fürs Teilen |
| `internal/handler/compare_preset.go:280` | `UpdateComparePresetHandler` — Weg 1 |
| `internal/handler/compare_preset.go:396-406` | `OfficialWarnings`-Merge, zweistufig — **dorthin gehört der neue Block** |
| `internal/handler/briefing_subscription.go:164-187` | Weg 2, generischer JSON-Merge — trägt ein neues Feld **automatisch** |
| `internal/store/compare_preset.go:199-215` | schreibt `data/users/<uid>/briefings/<id>.json` (ADR-0023) |

🔴 **Der Typ ist bereits erreichbar.** `AlertChannelThresholdsConfig` steht in
`internal/model/trip.go:202`, `ComparePreset` in `internal/model/compare_preset.go:14` — **dasselbe
Package `model`**. Kein Import, kein Alias, kein Verschieben. Ein zweiter, compare-eigener
Schwellen-Typ wäre nach der Teilungs-Invariante ein Verstoß.

### Frontend

| Datei:Zeile | Befund |
|---|---|
| `shared/AlertChannelPicker.svelte:28-41` | Props inkl. der **neuen, optionalen** `thresholds?` (`:37`) und `onThresholdChange?` (`:38`) |
| `shared/AlertChannelPicker.svelte:101` | **Schalter 1:** `{#if thresholds}` — der Picker kennt `context` überhaupt nicht |
| `shared/AlarmeTab.svelte:333-334` | **Schalter 2:** `thresholds={context === 'route' ? … : undefined}` |
| `shared/AlarmeTab.svelte:216` | **Schalter 3:** `if (context === 'vergleich') return;` im Handler |
| `shared/alarme-tab/alertChannelState.ts:66-70`, `:105-111` | Schwellen-Zustand + `applyThresholdChange` — **bereits geteilt** |
| `shared/alarme-tab/alarmeDeliveryPayload.ts:110-116` | sendet `alert_channel_thresholds`, wenn gesetzt |

**Einbettung des Pickers: genau einmal** (`AlarmeTab.svelte:330`). Die vier Flächen sind
Mount-Punkte von `AlarmeTab`:

| # | Datei:Zeile | `context` | Oberfläche |
|---|---|---|---|
| 1 | `trip-detail/AlarmeScheduleTab.svelte:46` | `route` | Trip-Detail |
| 2 | `compare/CompareTabs.svelte:1422` | `vergleich` | **Compare-Hub** |
| 3 | `compare-new/CompareNewEditor.svelte:412` | `vergleich` | Compare-Anlegen, Desktop |
| 4 | `compare-new/CompareNewEditor.svelte:499` | `vergleich` | Compare-Anlegen, Mobil |

⚠️ **Wer nur Schalter 2 umlegt, bekommt sichtbare Knöpfe ohne Wirkung. Alle drei gehören zusammen.**

---

## Existing Patterns

1. **Geteilter reiner Baustein in `src/services/`** — `alert_log.py`, `alert_urgency.py`,
   `alert_channel_threshold.py`, `compare_alert_channels.py`: ein Modul, von Trip- und
   Compare-Pfad gleichermaßen gerufen. PO-Vorgabe wörtlich: „Verwende zwingend den gleichen Code."
2. **Geteilter Go-Typ über Package-Grenzen der Dateien hinweg** — `OfficialWarningsConfig` liegt
   in `trip.go` und wird von `compare_preset.go:90` verwendet.
3. **Zweistufiger Merge** — Objekt-Ebene **und** Feld-Ebene, Muster `OfficialWarnings.Sources`
   (`compare_preset.go:396-406`, Trip: `trip.go:375-385`).
4. **Bestehende Werte nie neu erfinden** — Stufen-Abbildung über `LEVEL_LETTERS`, keine zweite
   Zahlenreihe.
5. **Fail-soft** — eine kaputte Protokolldatei darf weder Alarm noch Briefing verhindern.

---

## Dependencies

* **Upstream:** `alert_urgency` (Stufe je Meldung) · `alert_channel_threshold.split_by_threshold`
  · `alert_log.append_entry` (Protokoll) · `effective_compare_channels` (Kanal-Opt-in) ·
  `sms_allowed()` (Tarif-Gate)
* **Downstream:** `undelivered_hint.py` (zeigt den Grund an, sobald er geschrieben wird — für
  Compare **ohne Codeänderung**, weil nur `channel_disabled` übersprungen wird) · Cockpit-Kachel
  und Archiv-Statistik über `internal/store/log.go` (dürfen sich **nicht** ändern, D4 aus #1459)

---

## Existing Specs & ADRs

| Dokument | Bindende Aussage für diese Scheibe |
|---|---|
| **ADR-0046** `docs/adr/0046-alarm-kanal-schwelle.md:106-108` | *„Scope dieser Scheibe: nur Trips. Der Ortsvergleich … folgt als S3b-2b."* ⇒ **kein neues ADR nötig**, S3b-2b füllt die dort geschriebene Lücke |
| ADR-0046 `:101-105` | **Folgepflicht:** *„Jede neue Stelle, die ein Kanal-Set für den Versand auflöst, muss die Schwelle ebenfalls anwenden."* |
| ADR-0046 `:60-73` | `MIN_SMS_LEVEL` geht in derselben Einstellung auf; *„Ortsvergleichs-Berichte bleiben bis S3b-2b bei der festen Stufe 3"* |
| **ADR-0021** `:85-94` | Schließt den Ortsvergleich **ausdrücklich ein** — seit #1169 der zweite Consumer derselben Engine. Keine zweite Auswertungslogik: die Schwelle muss `split_by_threshold()` nutzen, kein Compare-eigener Filter. ⚠️ **Aber** `:91-94` nimmt Tageslimit, Alert-Log und **Radar-Onset-Pfad** aus: sie *„bleiben vorerst Trip-spezifisch im Adapter"* — das ist die ADR-Wurzel dafür, warum der Compare-Radar-Pfad bis heute anders gebaut ist |
| **ADR-0043** | Die Empfindlichkeitsstufe bleibt der **einzige** Regler für „OB" — die Kanal-Schwelle regelt „AUF WELCHEM WEG" |
| ⚠️ **ADR-0013** | **Namenskollision:** „threshold" ist im Renderer-Kontext bereits als Δ-Sensitivität belegt. In der Spec sauber abgrenzen |
| `docs/specs/modules/feat_1461_s3b2a_kanal_schwelle.md` | 13 ACs — **nur AC-3 und AC-11 waren trip-spezifisch**, der Rest ist Formulierungsarbeit |
| `docs/specs/modules/compare_official_alert_channels.md` | 🔴 Die zentrale **abzulösende** Zusicherung: „ab Stufe orange, identisch für Trip und Compare" (`:66`) |

---

## Risks & Considerations

### 1. 🔴 Die Kanäle im Vergleichs-Alarme-Tab sind gar keine Alarm-Kanäle

`AlarmeTab.svelte:191` zeigt im Vergleichs-Zweig genau die Schalter an, die
`VersandTab.svelte:238-243` bedient — dieselben Runen `wiz.sendTelegram`/`wiz.sendSms`, also die
**Briefing**-Kanäle. Beim Trip sind Alarm-Kanäle (`alert_channels`) und Briefing-Versand
**getrennte** Felder.

Eine Schwelle „ab wann erreicht ein **Alarm** diesen Kanal" auf ein Feld zu legen, das
gleichzeitig steuert, ob das **Briefing** per Telegram geht, ist fachlich mehrdeutig. **Diese
Frage steht vor der Schwellen-Frage** und kann den Umfang der Scheibe erheblich verändern.

### 2. 🔴 Der Speicher-Bug ist BESTÄTIGT — und wirkt in beide Richtungen

Gemessen mit einem echten Lauf gegen die Bridge (nicht gelesen):

`AlarmSnapshot` (`compareHubWizardBridge.ts:507-518`) trägt acht Felder — `sendTelegram`/`sendSms`
sind an **allen vier** Stellen der Kette nicht dabei: Interface `:507-518`, Momentaufnahme
`CompareTabs.svelte:575-589`, Payload-Liste `:552-563`, Rollback-Feldliste `:590-601`.

| Messung | Ergebnis |
|---|---|
| Kanal-Umschaltung als Snapshot-Differenz darstellbar? | **nein** — `flushPendingAlarmSave` liefert `null` |
| PUT-Body bei anderer Alarm-Änderung | `send_telegram: false` — **die alten Server-Werte werden aktiv zurückgeschrieben** |
| `alert_channel_thresholds` im Compare-PUT | `undefined` — der Schlüssel existiert im Compare-Pfad nicht |

Die Oberfläche meldet danach „sauber" (`CompareTabs.svelte:674` `markPristine()`). Zweite,
sichtbare Folge: beim Wechsel in den Versand-Reiter hydriert dieser aus `currentPreset`
(`:483-501`) — **der Schalter springt zurück**.

**Der Bug ist auf den Bearbeiten-Pfad beschränkt:** `compareWizardState.svelte.ts:120-121` nimmt
die Kanäle in `saveNewPreset()` auf, das **Anlegen** speichert also korrekt.

⚠️ **Es genügt nicht, die Baseline zu erweitern** — das Feld fehlt in *beiden* Objekten des
`JSON.stringify`-Vergleichs (`:551`). Alle vier Stellen müssen ergänzt werden.

### 3. 🔴 Der Compare-Radar-Alarm ist einkanalig — die Begründung dafür ist verfallen

Belegt aus drei Quellen:

* **Herkunft:** `fd1628bb` (2026-07-10, #1041 Slice 1b) — keine Begründung in der Commit-Nachricht,
  kein Kommentar an `:131`/`:150`.
* **Spec, „Known Limitations":** `docs/specs/_archive/modules/issue_1041b_compare_radar_alert_service.md:343-345`
  — *„nur über den E-Mail-Kanal … **da Compare-Presets heute keine Telegram-/SMS-Empfänger-Zuordnung
  besitzen**"*, und `issue_1041_multi_location_onset_alert.md:180-183`: *„Falls künftig
  Compare-Telegram-/SMS-Empfänger existieren, wäre der Multi-Zweig dort nachzuziehen."*
* **Die Bedingung ist eingetreten:** seit #1467 S2 AG1 liest `compare_alert_channels.py:28-36`
  genau diese Zuordnung.

**Der Schwester-Pfad wurde bereits als Bug korrigiert:** `compare_alert.py:313-319` — *„die
Kanalliste war hier fest `{"email"}` verdrahtet — der Telegram-/SMS-Schalter im Alarme-Tab war
dadurch **wirkungslos**"*. Der Radar-Pfad blieb dabei **vertagt, nicht entschieden**
(`rework_1467_s2_aenderungsalarm.md:38`).

**Der Transport blockiert nichts:** `notification_service.py:593` delegiert an denselben
generischen Verteiler wie der Trip-Radar-Alarm (`:653-660` → `:1174` E-Mail, `:1190` Telegram,
`:1271` SMS). **Der Trip-Radar war nie eingeschränkt** (`trip_alert.py:858-864`, alle drei Kanäle).

⇒ Derselbe Alarmtyp ist beim Trip dreikanalig, beim Ortsvergleich einkanalig. Das ist eine
Abweichung von der Teilungs-Invariante und ein **eigener Befund**, nicht bloß eine Vorbedingung.
Die Umstellung ist technisch trivial (`_check_one_preset` hat das Preset zur Hand, `:84`,
nutzt es bereits `:118-119`/`:203`) — aber sie **ändert Versandverhalten** und braucht ein eigenes AC.

### 4. Go: ein neues Feld ist NICHT automatisch geschützt

Die Beschreibung im alten Kontextdokument („RMW mit Preserve je Einzelfeld") ist irreführend.
Gemessen — **umgekehrte Polarität zum Trip**:

| | Trip | ComparePreset |
|---|---|---|
| Decode-Ziel | Pointer-DTO `tripUpdateRequest` (`trip.go:197`) | **volles `model.ComparePreset`** (`compare_preset.go:320-324`) |
| Muster | `if req.X != nil { existing.X = req.X }` | `if updated.X == nil { updated.X = original.X }` |
| Startpunkt | der **Bestand** | der **Request** |
| Feld ohne Zeile | bleibt erhalten | **geht verloren** |

⇒ Der neue Block ist **Pflicht**, mit Objekt-Ebene *und* drei Kanal-Ebenen. Präzedenzfall im Repo:
`OutlookEnabled` (`compare_preset.go:67-71`) — *„ein Client, der es sendete, verlor es beim Decode
still"* (#1361/#1368).

⚠️ **Zwei Schreibwege**, beide müssen bedient sein: `PUT /api/compare/presets/{id}`
(Handarbeit) und `PUT /api/briefings/{id}?kind=vergleich` (`mergeBriefingPatch` trägt automatisch
— trotzdem mit einem Test belegen, nicht annehmen).

### 5. Keine Validierung der Stufenwerte — nirgends

Go nimmt jeden String an (`validateComparePreset:112-153` prüft keine Schwellen). Python
degradiert: ein unbekannter Wert bekommt Rang 0 (`alert_urgency.py:63-68`), der Kanal verhält
sich wie `LOW`. Richtige Ausfallrichtung für ein Alarmprodukt (kein verlorener Alarm) — aber ein
Tippfehler schaltet die Einstellung still ab. Die Trip-Seite kommt ohne Validierung aus;
Symmetrie spricht dafür, es hier genauso zu halten (Regel-Budget: eine neue Validierung bräuchte
ein Prüfdatum).

### 6. Python braucht KEINE Modelländerung

`compare_preset_to_dict()` (`src/app/loader.py:341-349`) liefert `preset.raw`, den unveränderten
Eingabe-Dict; `compare_preset_from_dict()` (`:238-243`) bewahrt `raw` ausdrücklich. Ein neuer
Go-Schlüssel kommt **ohne** Parser-Änderung an. Der Trip-Befund F002 (Lese-Hälfte) kann sich hier
so nicht wiederholen — **der Wirkungs-Nachweis bleibt trotzdem Pflicht** (Muster:
`tests/tdd/test_alert_channel_threshold.py:1058`, JSON so ablegen wie Go sie schreibt, über den
echten Loader lesen, dann einen **echten Alarm auslösen**).

### 7. ✅ Die Dringlichkeit ist da — aber sie entsteht zu spät

**Gemessen, nicht angenommen.** Ein `grep` über `urgency|severity|AlertSeverity|ChangeSeverity|
HIGH|MODERATE|LOW` in den drei Compare-Alarmdateien liefert **sechs Treffer**: drei Imports, drei
Ableitungen. **Keine hartkodierte Stufe ist übrig.**

| Weg | Ableitung | Aufgerufene Funktion |
|---|---|---|
| `compare_alert.py` (Δ-Änderung) | `:195` | `urgency_from_changes(alle_changes)` |
| `compare_official_alert.py` (amtlich) | `:153-156` | `highest_urgency(*[urgency_from_official_level(a.level) …])` |
| `compare_radar_alert.py` (Radar) | `:139-145` | `highest_urgency(*[urgency_from_radar(…) …])` |

**S3a hat den Compare-Pfad mitgezogen** — belegt am Diff von `cf7d8fc0`: die Commit-Nachricht
nennt „sechs Aufrufer" (drei Trip + drei Compare), und vorher standen dort exakt dieselben festen
Werte wie beim Trip (`severity="MODERATE"` amtlich, `severity="HIGH"` Radar). Es sind **dieselben**
Funktionen aus `alert_urgency.py`, kein Compare-eigener Weg. Dass `urgency_from_radar`
case-insensitiv ist (`alert_urgency.py:39-44`), war schon damals nötig, weil der Trip-Pfad das
Label kleinschreibt und der Compare-Pfad nicht.

🔴 **Der strukturelle Haken — der eigentliche Aufwand:** In allen drei Wegen wird die Dringlichkeit
**inline als Argument im `append_entry`-Aufruf** berechnet, und dieser Aufruf steht **nach** dem
Versand. `split_by_threshold()` braucht sie **davor**. Die Ableitung ist also in eine lokale
Variable hochzuziehen — genau das, was S3b-2a beim Trip tat (`trip_alert.py:874-880`, `:1015-1024`,
`:1177-1183`).

| Weg | Versand | Protokoll | Hochzuziehen |
|---|---|---|---|
| `compare_alert.py` | `:177-187` | `:192-201` | **zwei** Dinge: `alle_changes` (`:191`) **und** die Ableitung (`:195`) |
| `compare_official_alert.py` | `:142-148` | `:150-164` | nur die Ableitung; `tagged_alerts` liegt ab `:131` vor |
| `compare_radar_alert.py` | `:130-133` | `:136-153` | nur die Ableitung; `triggered` liegt ab `:111` vor |

Eine Abweichung, die keine ist: der Compare-Δ-Weg ruft nur `urgency_from_changes`, nicht wie der
Trip zusätzlich `urgency_from_official_level`. Das ist korrekt —
`send_multi_location_deviation_alert` (`compare_alert.py:177-187`) hat keinen
`official_notices`-Parameter, dort ist nichts zu kombinieren.

⇒ **Keine Einstufungs-Vorarbeit nötig, kein S3a-Nachzug. Je Weg drei Handgriffe:** Ableitung
hochziehen · `split_by_threshold` einsetzen · gefilterte Menge an den Versand, **rohe** Menge plus
`below_threshold_channels` an `append_entry`.

### 8. Das Protokoll: dieselbe Falle wie beim Trip, hier sogar enger

Im Compare-Pfad wandert heute **dieselbe Variable** in Versand und Protokoll
(`compare_alert.py:179`/`:198`, `compare_official_alert.py:144`/`:161`). Ein naiver Filter darauf
lässt eine vollständig unterdrückte Meldung **spurlos verschwinden** (früher Ausstieg
`alert_log.py:173-175`) — rote Linie #638. `append_entry` unterstützt
`below_threshold_channels` bereits (`alert_log.py:148`), es ist nur zu füttern.

### 9. Zwei Compare-Warnstufen-Tests werden sicher rot

`tests/tdd/test_compare_sms_official_alerts.py:84` (*„Ort mit nur gelber Warnung darf keinen
Marker tragen"*) und `test_compare_telegram_official_alerts.py:111` (*„Gelbe Warnung darf im
Compare-Telegram nicht mehr als Warn-Block erscheinen"*) prüfen das alte Soll. Umschreiben nach
dem Muster aus S3b-2a: `tests/tdd/test_telegram_official_alert_bubble.py:216` leitet die Schwelle
aus `min_official_level_for_threshold("LOW")` **ab**, statt eine Zahl zu wiederholen.

### 10. Kein Gate bewacht die Doku-Aussagen

`tests/test_api_contract_drift.py` prüft, ob jeder `json:"…"`-Tag in `api_contract.md` **vorkommt**
— der String `alert_channel_thresholds` steht dort seit S3b-2a. Der Test wäre also **trivial grün,
ohne dass die Compare-Semantik dokumentiert ist**. Kein Sicherheitsnetz. Die Doku-Zeilen sind
aktiv mitzuziehen: `sms_format.md:225`, `:235`, ⚠️`:476` (schon jetzt für Trips falsch),
`api_contract.md:11`, `:770`, ⚠️`:53`, und `compare_official_alert_channels.md` (elf Stellen).

### 11. Vorbestehend, kein Nutzer-Bug — Notiz nach #1199

Die handgepflegte Go-Preserve-Liste schützt `ArchivedAt`, `LocationIDs`, `Empfaenger`,
`HourFrom`/`HourTo`, `Weekday` **nicht**. Sie hält heute nur, weil das Frontend den Body als
vollen Spread des GET-Objekts baut (`compareEditorSave.ts:153`) — gemessen: alle fünf Felder sind
im PUT-Body enthalten. Ein künftiger Teil-PUT (anderer Client, `curl`, Skript) verlöre sie
lautlos. **Verdikt: theoretisch, kein Fehlalarm ins Backlog.**

### 12. Unverändert geltende Pflichten

* **D4 (#1459):** Cockpit-Kachel und Archiv-Statistik ändern sich um **keine Zahl**
* **Mandantentrennung:** echte `user_id` durchreichen, mit **zwei** Nutzern testen. Kein
  hartkodiertes `"default"` in den Compare-Handlern (gemessen) — aber `Store.WithUser("")` ist ein
  No-op (`store.go:16-19`), der Rückfall ist strukturell vorhanden
* **Kurznachricht-Zeichengleichheit:** SMS/Telegram sind 160-Zeichen-Formate
* **Renderer-Commit-Gate #811:** `comparison.py` steht **nicht** auf der Sperrliste,
  `email/compare_html.py` und `alert/official_alerts.py` **schon**
* **Pendant-Sperre (#1481 B):** neue Dateien unter `compare*/` sind gesperrt — der Picker ist
  bereits geteilt, es sollte **keine neue Datei** nötig sein

---

## Der Auftrag von S3b-2b (Stand der Recherche)

1. `AlertChannelThresholds` auf `ComparePreset` (Go-Modell + Handler-Merge, **beide** Schreibwege)
2. Schwellenanwendung an **drei** Compare-Nahtstellen: `compare_alert.py:334`,
   `compare_official_alert.py:271`, `compare_radar_alert.py:131`/`:150`
3. Entscheidung + ggf. Umbau der Radar-Hartverdrahtung auf den Resolver (**Verhaltensänderung**,
   eigenes AC)
4. `MIN_SMS_LEVEL`-Öffnung für Compare an **zwei** Stellen mit **zwei verschiedenen** Bauformen
   (`comparison.py:735` Inline-Filter, `:900` Funktionsparameter)
5. Compare-Speicherweg im Frontend: die Drei-Stellen-Sperre lösen **und** den bestätigten
   Speicher-Bug reparieren (vier Stellen in der Bridge-Kette)
6. Doku-Nachzug (neun Stellen) und Umschreibung der zwei Compare-Warnstufen-Tests

---

---

# Analysis

## Type

**Feature** (Epic-Scheibe, kein Fehlverhalten im Bestand) — **mit zwei eingeschlossenen Fehlern:**
dem bestätigten Speicher-Bug im Bearbeiten-Pfad des Vergleichs-Hubs und der verfallenen
E-Mail-Beschränkung des Compare-Radar-Alarms.

## 🔴 Die große Zuschnittsfrage hat sich beim Messen aufgelöst

Das Kontextdokument nannte als Risiko 1: *„Eine Schwelle auf ein Feld zu legen, das gleichzeitig
den Briefing-Versand steuert, ist fachlich mehrdeutig."* Die Messung entkräftet das:

**Beim Trip liegt die Schwelle in einem eigenen Feld NEBEN den Kanälen, nicht darin** —
`internal/model/trip.go:151`, Begründung `:194-201`. Genau dieselbe Anordnung ist beim
`ComparePreset` möglich, **ohne `SendTelegram`/`SendSms` anzufassen**.

Und der Trip ist strukturell näher am Ortsvergleich als gedacht:

| | Trip-Briefing | Trip-Alarm |
|---|---|---|
| Feld | `report_config.send_{email,sms,telegram}` (autoritativ, `loader.py:572-574`) | `trip.alert_channels` (`trip.go:145`) |
| Entscheidungsstelle | `trip_report_scheduler.py:836-838` / `:1079-1081` | `trip_alert.py:1212` |

**Aber `alert_channels` ERBT die Briefing-Kanäle, wenn es nicht gesetzt ist** —
`trip_alert.py:1236-1249`, wörtlich im Go-Kommentar `trip.go:141-144`: *„nil = Legacy-Verhalten
(Alert-Kanaele **erben** die Briefing-Kanaele aus ReportConfig)."*

⇒ **Der heutige Ortsvergleich ist exakt der Trip-Legacy-Zustand `alert_channels = nil`.** Er
verliert beim Zusammenlegen nichts, weil es dort keine Trennung gibt, die man aufgäbe. Der Trip
hat die Trennung **additiv** nachgerüstet (#1258 S3 D2), ohne den Erbfall abzuschaffen.

⇒ Die Mehrdeutigkeit besteht **heute schon, ohne Schwelle**, und die Schwelle macht sie nicht
schlimmer: sie regelt „ab welcher Dringlichkeit ein **Alarm** diesen Weg nimmt" und lässt den
Briefing-Versand unberührt — **der Briefing-Fanout ruft `split_by_threshold` gar nicht auf.**

**Folge:** „Soll ein Ortsvergleich Alarme auf anderen Wegen schicken als sein Briefing?" ist eine
eigene Produktentscheidung, vom Schwellen-Thema unabhängig. Sie gehört **nicht** in diese Scheibe.

### An den Produktivdaten gegengeprüft

Über alle 19 Entitäten unter `data/users/*/briefings/*.json`: **genau ein** Trip hat
`alert_channels` überhaupt gesetzt — und dessen Wert ist mit seinen eigenen Briefing-Kanälen
**identisch**. Alle übrigen stehen auf `nil` und erben (`trip_alert.py:1246-1249`).

⇒ **Trip und Ortsvergleich lösen ihre Alarm-Kanäle heute bereits gleich auf.** Die Struktur, um
die die Zuschnittsfrage kreiste, hat in der Praxis **keine einzige abweichende Wirkung**.

Sollte der PO die Felder später doch zusammenlegen wollen, ist die Richtung **A** — der Trip gibt
seinen ungenutzten Sonderweg auf. Nicht B: das gäbe der einfacheren Entität einen zweiten,
ungenutzten Regler und zwänge zur Gabelung des Compare-Resolvers, den #1467 S2 AG1 gerade erst
entdoppelt hat. Als eigene Scheibe mit eigenem PO-go, weil es Versandverhalten ändert.

## Affected Files

| Datei | Änderung | Inhalt |
|---|---|---|
| `internal/model/compare_preset.go` | MODIFY | `AlertChannelThresholds *AlertChannelThresholdsConfig` — **bestehender Typ**, selbes Package |
| `internal/handler/compare_preset.go` | MODIFY | Preserve-Block nach Muster `:396-406`, Objekt- **und** drei Kanal-Ebenen |
| `src/services/compare_alert.py` | MODIFY | Ableitung + `alle_changes` hochziehen (`:191`/`:195`), Split, roh an `append_entry` |
| `src/services/compare_official_alert.py` | MODIFY | Ableitung hochziehen (`:153-156`), Split |
| `src/services/compare_radar_alert.py` | MODIFY | Ableitung hochziehen (`:139-145`), Split, **Hartverdrahtung `:131`/`:150` → Resolver** |
| `src/output/renderers/comparison.py` | MODIFY | `:735` Vergleichswert ersetzen · `:900` `min_level` übergeben |
| `frontend/.../compareHubWizardBridge.ts` | MODIFY | Speicher-Bug (Stellen 1, 3, 4) + `HubEdit.alertChannelThresholds` + Durchreichung |
| `frontend/.../CompareTabs.svelte` | MODIFY | Speicher-Bug (Stelle 2) + `existingChannelThresholds` |
| `frontend/.../compareEditorSave.ts` | MODIFY | `CompareEditorEdits` + Body-Zeile (Muster `:184-185`) |
| `frontend/.../AlarmeTab.svelte` | MODIFY | Drei-Stellen-Sperre lösen (`:216`, `:333-334`) |
| `docs/reference/sms_format.md`, `api_contract.md`, `docs/specs/modules/compare_official_alert_channels.md`, `docs/adr/0046-…` | MODIFY | neun Doku-Stellen + ADR-Nachtrag |
| `tests/tdd/test_compare_sms_official_alerts.py`, `test_compare_telegram_official_alerts.py` | MODIFY | altes Soll → neues Soll |
| Tests | CREATE | Verhaltensnachweis inkl. Go→Python-Persistenzschleife |

**Nicht im Umfang:** `AlertChannelPicker.svelte` und `alertChannelState.ts` (bereits geteilt, kein
neues Bauteil) · `undelivered_hint.py` (entitätsblind, `:41`→`:84`) · Python-Modelle
(`preset.raw` reicht durch) · die beiden Compare-Anlege-Mounts (ein neuer Vergleich erbt den
Startwert, **genau wie ein neuer Trip** — `trip-new/` bettet gar keinen Alarm-Bereich ein)

## Gemessene Präzisierungen zum Kontextteil

| Punkt | Befund |
|---|---|
| Speicher-Bug | **Vier Stellen, nicht fünf.** `buildHubPutPayload:150-151` und `compareEditorSave.ts:184-185` reichen `send_telegram`/`send_sms` **bereits** durch. Korrektur: Stelle 4 ist `compareHubWizardBridge.ts:586-608` (`rollbackAlarmSnapshot`), nicht `CompareTabs.svelte`. Die Versand-Seite macht es fünf Bildschirmseiten höher richtig (`:294-305`) — **reine Symmetrie-Arbeit** |
| Schwellenfeld im Frontend | **zwei neue Zeilenpaare**: `HubEdit` + Durchreichung · `CompareEditorEdits` + Body-Zeile. Der Trip-Baustein `alarmeDeliveryPayload.ts` ist **nicht** wiederverwendbar (sein Aufrufer ist hart auf `PUT /api/trips/{id}` verdrahtet, `AlarmeTab.svelte:247`) — wiederverwendbar ist nur die *Form*. Kein Teilungs-Verstoß: die zwei Speicherwege sind Bestand, keine Neuanlage |
| Kurznachrichten-Bericht | **Kein toter Code.** Beide Renderer laufen im echten Versand (`scheduler_dispatch_service.py:404`/`:407`), erreichbar über Zeitplan (`:106`) **und** Handversand (`:469` → `api/routers/scheduler.py:245`). Die Vorschau (`compare_preview_service.py`) zeigt die Wirkung zusätzlich ohne Versand — nützlich für die Staging-Verifikation |
| ⚠️ Zwei Wirkungsorte | `comparison.py:735`/`:900` sind **Briefing**-Bausteine, nicht Alarm. Dort steuert die Einstellung die Sichtbarkeit amtlicher Marker im Kurzformat — das ist ADR-0046 `:60-73`, aber **ein anderer Wirkungsort** als die drei Alarm-Nahtstellen. In den ACs zu trennen |
| Compare-Hinweis im Briefing | Vier Compare-Tests fahren den **echten** Versandpfad (`test_alert_undelivered_hint.py:914`, `:961`, `:1043`, `:1098`). 🔴 **`below_channel_threshold` kommt darin null mal vor** — alle 26 Tests nutzen `delivery_failed`. Der End-zu-End-Nachweis ist der offensichtliche neue Test |

## Technischer Ansatz

**Die Naht sitzt dort, wo das Kanal-Set entsteht** (ADR-0046 `:101-105`), nie in der
Versandschicht. Je Compare-Alarmweg drei Handgriffe, Reihenfolge **zwingend**:

1. Dringlichkeit **hochziehen** (entsteht heute erst im `append_entry`-Argument, also nach dem Versand)
2. `allowed, suppressed = split_by_threshold(channels, urgency, thresholds)`
3. Versand mit `allowed` · `append_entry` mit dem **rohen** Set **plus** `below_threshold_channels=suppressed`

Schritt 3 ist die Sicherheitsleine: der frühe Ausstieg `alert_log.py:173-175` bleibt dadurch das,
was er ist („Nutzer hat alle Kanäle abgeschaltet"). Naiv als Filter auf die Protokollliste gebaut
⇒ vollständig unterdrückte Meldung verschwindet **spurlos** (rote Linie #638).

## Risiko-Bewertung

| Risiko | Bewertung |
|---|---|
| 🔴 Go-Feld geht beim Speichern verloren | **Sicher**, wenn der Preserve-Block fehlt — `UpdateComparePresetHandler` dekodiert in ein volles Struct, Startpunkt ist der **Request**. Präzedenzfall `OutlookEnabled` (#1361/#1368) |
| 🔴 Radar-Umstellung ändert Versandverhalten | Compare-Radar-Alarme gingen künftig auch per Telegram/SMS. Gewollt — aber eigenes AC und ADR-0021-Nachtrag |
| 🔴 Zwei Compare-Warnstufen-Tests | `test_compare_sms_official_alerts.py:84` und `test_compare_telegram_official_alerts.py:111` prüfen das alte Soll und werden **sicher rot**. Umschreiben nach Muster `test_telegram_official_alert_bubble.py:216` (Schwelle **ableiten**, keine Zahl wiederholen) |
| D4 (#1459) | Strukturell unberührt — die Schwelle ändert nur, welches Ziel getroffen wird, nie die Zähllogik. Trotzdem mit Test bewachen |
| 160-Zeichen-Formate | Nur `comparison.py:735`/`:900` betroffen, kein Umbau der Renderer. Zeichengenauer Nachweis nötig |
| Mandantentrennung | Kein neues Risiko (gleicher Dateiweg), Zwei-Nutzer-Test bleibt Pflicht |
| „Greift ohne Änderung" | 🔴 Struktur-Aussage, **kein** Wirkungsnachweis — die Falle aus #1457. Jedes AC muss dort prüfen, wo die Zusicherung **wirkt** |

## Scope Assessment

| | Produktivcode | Tests |
|---|---|---|
| Zeilen | ≈185 | ≈900–1100 |
| Dateien | ~13 | ~12 |

Risiko: **MEDIUM** — die Backend-Logik ist aus S3b-2a bewiesen, neu sind die Verdrahtung, ein
Go-Feld und der Frontend-Speicherweg. `loc_limit_override = 1600` voraussichtlich nötig
(S3b-2a zum Vergleich: 2200 bei ~455 Zeilen Produktivcode).

**Zuschnitt: eine Scheibe, sie trägt.** Der Speicher-Bug gehört hinein — die vier Bridge-Stellen
werden von der Schwelle ohnehin angefasst, und ohne den Fix ist ein Wirkungs-AC über den Hub
strukturell nicht erfüllbar. Eigenes AC und eigener Repro-Test.

## Open Questions (PO)

**Vorgabe des PO vom 2026-08-06:** *„Alles Sinnvolle soll zusammengelegt werden"* — samt der
ausdrücklichen Klarstellung, dass ADRs geändert werden dürfen, wenn eine Entscheidung dem im Weg
steht. Darunter bewertet:

| Frage | Stand |
|---|---|
| Gemeinsamer Kanalsatz für Briefing und Alarm im Ortsvergleich? | ✅ **Erledigt durch Messung** — die Schwelle liegt auch beim Trip in einem eigenen Feld **neben** den Kanälen. Kein Konflikt, keine Entscheidung nötig. Die Trip-Trennung `alert_channels` nachzuziehen ist eine eigene Produktentscheidung, unabhängig vom Schwellen-Thema |
| Bekommen alle drei Compare-Einbettungen denselben Umfang? | ✅ **Nein, und das ist symmetrisch zum Trip** — die beiden Anlege-Mounts bleiben draußen; ein neuer Vergleich erbt den Startwert, genau wie ein neuer Trip (`trip-new/` bettet gar keinen Alarm-Bereich ein) |
| 🔴 **Compare-Radar auf den Resolver umstellen?** | **Vorlagepflichtig** — es ist die einzige echte **Verhaltensänderung** der Scheibe: Radar-Alarme des Ortsvergleichs gingen künftig auch per Telegram/SMS statt nur per E-Mail. Unter „alles Sinnvolle zusammenlegen" ist die Antwort ja; sie wird trotzdem ausdrücklich bestätigt, weil sie über den Schwellen-Auftrag hinausgeht |
| LoC-Grenze | Voraussichtlich `loc_limit_override` nötig (S3b-2a: 2200 bei ~455 Zeilen Produktivcode / ~1300 Tests). Diese Scheibe ist kleiner — die Backend-Logik steht —, aber Go + Python + Frontend + Doku in einem Zug |

## Was bewusst NICHT in dieser Scheibe ist

* **Die Trip-Trennung `alert_channels` für den Ortsvergleich nachziehen** — eigene
  Produktentscheidung („soll ein Vergleich Alarme auf anderen Wegen schicken als sein Briefing?")
* **Ein neues ADR** — ADR-0046 `:106-108` hat die Lücke bereits ausgewiesen (*„Der Ortsvergleich …
  folgt als S3b-2b"*). Nachträge in ADR-0046 und ADR-0021 genügen
* **Eine Validierung der Stufenwerte** — die Trip-Seite kommt ohne aus; Symmetrie, und eine neue
  Regel bräuchte nach Regel-Budget ein Prüfdatum

## Was noch nicht gemessen ist

* **Keine Testläufe.** Alle „wird rot / bleibt grün"-Aussagen sind aus Assertions abgeleitet
* **Der Speicher-Bug ist am Code belegt und einmal an der Bridge gemessen**, nicht am laufenden
  System — der Staging-Nachweis muss ihn am echten Klick zeigen
* **Warum die Kanäle historisch in zwei Reitern landeten** — an keiner der beiden Stellen steht
  eine Begründung
