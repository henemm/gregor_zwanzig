# Context: feat-1461-s3b2-kanal-schwelle

**Issue:** #1461 (Epic #1458, Scheibe S3) — Teilscheibe **S3b-2**, die eigentliche Kanal-Schwelle
**Vorgänger, alle live:** #1459 (Protokoll) · S3a `cf7d8fc0` (Einstufung) · #1503 `61165987`
(Δ-Einstufung) · S3b-1 `c8fbb3e9` (Sichtbarkeit im Briefing)
**Basis:** `origin/main` = `2c0ee077`

## Request Summary

Der Nutzer soll je Kanal einstellen können, **ab welcher Dringlichkeit** ihn eine Alarm-Meldung
dort erreicht. Begründung des PO (2026-08-02): eine Satelliten-SMS kostet Geld und Akku, eine
E-Mail nichts — dieselbe Wetterlage rechtfertigt auf dem einen Kanal eine Nachricht und auf dem
anderen nicht. Beispiel des PO, ausdrücklich **kein** fester Vorgabewert: „auf Telegram alles,
auf Satelliten-SMS nur höchste Dringlichkeit".

Das ist Bedingung **(a)** des Relevanz-Filters aus #1458: *der Nutzer will darüber **auf diesem
Kanal** informiert werden.*

## Ausgangslage: was die Vorgänger-Scheiben geliefert haben

| Baustein | Stand | Bedeutung für S3b-2 |
|---|---|---|
| **Eine Dringlichkeitsskala** | `src/services/alert_urgency.py:20-21` — `LOW`/`MODERATE`/`HIGH`, Rangordnung in `_RANK` | Die Schwelle hat einen vergleichbaren Wert. **Alle sechs** Protokoll-Schreibstellen speisen sich daraus |
| **Einstufung stimmt** | S3a + #1503 | Vor S3a war leichter Nieselregen `HIGH` und eine rote Unwetterwarnung `MODERATE`; eine Schwelle darauf hätte das Falsche unterdrückt |
| **Sichtbarkeit** | `alert_log.read_undelivered()` `:270`, `alert_briefing_anchor.undelivered_since_last_briefing()` `:93`, `output/renderers/email/undelivered_hint.py` | Pflicht 2 des Issues ist erfüllt — unterdrückte Meldungen verschwinden nicht mehr spurlos |

**🔴 Die Dringlichkeit steuert bis heute nichts.** Gemessen: `severity` fließt ausschließlich in
`alert_log.append_entry(severity=…)`. Es gibt im Python-Code **keine** Stelle, an der eine
`alert_urgency`-Stufe eine Kanalentscheidung beeinflusst.

## Related Files

### Kanal-Auflösung — es sind VIER Stellen, nicht eine

| # | Pfad | Stelle | Bauart |
|---|---|---|---|
| 1 | Trip, Δ-Wetter + amtlich | `src/services/trip_alert.py:1171` `_effective_alert_channels(trip)` | Union über `alert_rules`; `trip.alert_channels` ersetzt den geerbten Briefing-Anteil (`:1198-1206`); SMS-Tier-Gate `:1219-1221`. Aufrufer: `:249`, `:992`, `:1140` |
| 2 | **Trip, Radar** | `src/services/trip_alert.py:852-860` | **Inline-Kopie**, ruft (1) **nicht** auf — eigene Ableitung aus `can_email/can_telegram/can_sms`; Abbruch bei leerem Set `:860-862` |
| 3 | Ortsvergleich (geteilt) | `src/services/compare_alert_channels.py:28` `effective_compare_channels()` | E-Mail **immer** an; Telegram/SMS nur bei Opt-in. Wrapper: `compare_official_alert.py:265`, `scheduler_dispatch_service.py:279`; Direktaufruf `compare_alert.py:334` |
| 4 | **Ortsvergleich, Radar** | `src/services/compare_radar_alert.py:131` und `:150` | **hart `{"email"}`** — kein Resolver |

### Versandpunkte — zwei Alarm-Wege laufen am geteilten Punkt vorbei

`notification_service._dispatch_alert_message()` (`:1065`) hat vier Aufrufer:
`send_deviation_alert:503` · `send_multi_location_deviation_alert:582` ·
`send_multi_location_radar_alert:653` · `send_radar_alert:1057`.

**Vorbei laufen:** `send_official_alert:661` (eigene Zweige E-Mail `:712`, Telegram `:725`,
SMS `:748`) und `send_multi_location_official_alert:857` (E-Mail `:923`, Telegram `:929`,
SMS `:936`). Wer die Schwelle nur an der geteilten Naht einbaut, lässt ausgerechnet die
amtlichen Warnungen ungefiltert.

⚠️ In allen Zweigen wird ein Kanal **vor** dem Transport als „betreten" verbucht
(z.B. `:1174-1175`, `:713`, `:927`) — Best-Effort-Semantik, für das Protokoll relevant.

### Protokoll

| Punkt | Fundstelle |
|---|---|
| `append_entry` Signatur | `src/services/alert_log.py:125-138` |
| 🔴 **früher Ausstieg bei leerem Kanal-Set** | `:173-175` — `if not effective: return`, **kein** Eintrag, weder in `entries` noch in `not_delivered` |
| `_channels_not_sent()` | `:110-122` — Grund `delivery_failed`, wenn der Kanal in `effective` war, sonst `channel_disabled` |
| Grund-Konstanten | `:45-49` — `channel_disabled`, `delivery_failed`, `quiet_hours`, `daily_limit`, `cooldown` (die letzten drei setzt **kein** Aufrufer) |
| `read_undelivered()` (S3b-1) | `:270-276`; `_missed_channels` `:246-267` filtert **genau** `channel_disabled` heraus, alle anderen Gründe zählen als Vorfall; Docstring `:254` nennt „unter der Kanal-Schwelle" bereits als künftigen Grund |
| Anzeige-Label je Grund | `src/output/renderers/email/undelivered_hint.py:36-39` |

⇒ Ein neuer Grund braucht **keine** Schema-Migration (freie Strings), aber **ein Label** in
`undelivered_hint.py`, sonst steht er unübersetzt in der Mail.

### Die bereits existierende, unsichtbare Kanal-Schwelle

`src/output/tokens/hazard_symbols.py:37` — `MIN_SMS_LEVEL = 3` („nur orange und rot erreichen
SMS/Telegram"). Drei Verwendungsstellen, alle **Render**-Filter auf **amtliche Warnungen**:

| Stelle | Was gefiltert wird |
|---|---|
| `src/output/renderers/alert/official_alerts.py:388` | die amtlichen Warnungen einer Meldung, bevor daraus SMS-Warnblöcke entstehen (geteilter Kern von Trip- und Compare-SMS) |
| `src/output/renderers/narrow.py:386` | die amtlichen Warnungen aller Segmente eines Trip-Telegram-**Briefings**; ohne Treffer entfällt die Bubble |
| `src/output/renderers/comparison.py:704` | die amtlichen Warnungen **eines Ortes** im Compare-Telegram |

**🟢 Der Anschluss ist exakt:** `alert_urgency.urgency_from_official_level()` (`:24`) bildet über
**dieselbe** Tabelle `hazard_symbols.LEVEL_LETTERS` ab — 2→`LOW`, 3→`MODERATE`, 4→`HIGH`.
`MIN_SMS_LEVEL = 3` **ist** damit begrifflich „Schwelle `MODERATE` für SMS und Telegram". Es
braucht keine zweite Zahlenreihe, um die feste Schwelle in der einstellbaren aufgehen zu lassen.

**⚠️ Aber es ist nicht dieselbe Ebene:** `MIN_SMS_LEVEL` filtert **Briefing-Inhalt**, die
S3b-2-Schwelle filtert **Alarm-Versand**. Ob die Einstellung auch den Briefing-Inhalt steuern
soll, ist eine PO-Frage, keine Ableitung.

### Datenmodell und Persistenz

| Ebene | Fundstelle | Stand |
|---|---|---|
| Go, Trip | `internal/model/trip.go:142` `AlertChannels *AlertChannelsConfig`; Struct `:178-182` | drei **Booleans** `Email`/`Telegram`/`Sms`, kein Platz für eine Stufe |
| 🔴 Go, Speicherweg Trip | `internal/handler/trip.go:361-363` | `if req.AlertChannels != nil { existing.AlertChannels = req.AlertChannels }` — **Replace des ganzen Pointers**, begründet mit „all-or-nothing" (`:357-360`) |
| Go, Ortsvergleich | `internal/model/compare_preset.go:91-92` | **kein** `alert_channels`. Stattdessen flach `SendTelegram *bool` / `SendSms *bool`; E-Mail hat gar kein Feld (implizit immer an) |
| Go, Speicherweg Compare | `internal/handler/compare_preset.go:407-411` | RMW mit **Preserve je Einzelfeld** (anderes Muster als Trip) |
| Weitergabe an Python | **über die Datei**, kein Proxy: Go schreibt `data/users/<uid>/briefings/<id>.json` (`internal/store/briefing_subscription.go:19-20`), Python liest denselben Pfad (`src/app/loader.py:423`, Durchreichung `:677-679`, Feld `src/app/trip.py:214`) |
| API-Vertrag | `docs/reference/api_contract.md:724-737` | beschreibt `alert_channels` ausschließlich als bool-Flags; **kein** dokumentierter Platz für eine Schwelle |

### Oberfläche

| Punkt | Fundstelle |
|---|---|
| Der Baustein | `frontend/src/lib/components/shared/AlertChannelPicker.svelte:25-31` — Props `channels`, `onToggle`, `targets?`, `dense?`; voll kontrolliert, kein eigener Zustand |
| Datentyp | `shared/alarme-tab/alertChannelState.ts:9-13` — `{telegram, sms, email}`, **flache Booleans** |
| Darstellung | `AlertChannelPicker.svelte:84-92` — je Zeile ein binärer `<Switch>`, keine Skala. `CHANNEL_SUB` (`:38-42`, `:80-83`) ist heute statischer Beschreibungstext — **der freie Platz je Zeile** |
| Einbettung des Pickers | **genau einmal**: `shared/AlarmeTab.svelte:295` |
| Flächen (über `AlarmeTab`) | Trip-Detail `trip-detail/AlarmeScheduleTab.svelte:46` · Compare-Hub `compare/CompareTabs.svelte:1422` · Compare-Anlegen Desktop `compare-new/CompareNewEditor.svelte:412` · Compare-Anlegen Mobil `:499` ⇒ **4 Flächen, davon 3 im Vergleichs-Zweig** |
| Speicherweg (nur `route`) | `AlarmeTab.svelte:207-223` + `$effect` `:233-245` → `PUT /api/trips/{id}`; Payload `shared/alarme-tab/alarmeDeliveryPayload.ts:81-91` |
| Compare-Zweig | `AlarmeTab.svelte:178-193` — E-Mail hart `true`, **ohne Toggle** (Begründung `:169-170`); geschrieben wird in den Wizard-Zustand, nicht per eigenem PUT |
| ⚠️ Trip-Anlegen | `trip-new/TripNewEditor.svelte` bettet **weder** `AlarmeTab` **noch** den Picker ein — ein neu angelegter Trip bekommt gar kein `alert_channels` |

## Existing Patterns

1. **Geteilter reiner Baustein in `src/services/`** — `alert_log.py` (#1459), `alert_urgency.py`
   (S3a), `alert_briefing_anchor.py` (#1467 AG5), `compare_alert_channels.py`: ein Modul, von
   Trip- und Compare-Pfad gleichermaßen gerufen. PO-Vorgabe wörtlich: „Verwende zwingend den
   gleichen Code."
2. **Bestehende Werte nie neu erfinden** — `LEVEL_LETTERS` als einzige Abbildung amtliche Stufe →
   drei Stufen (S3a hat das bereits so gelöst).
3. **Pointer-Feld mit Legacy-Erbe** — `alert_channels` und `official_warnings` folgen demselben
   Muster: `nil` = erben, gesetzt = ersetzen.
4. **Feld-Level-Merge, wenn eine Unterstruktur dazukommt** — `internal/handler/trip.go:345-356`
   bewahrt `OfficialWarnings.Sources` einzeln. Genau dieser Fix musste dort schon einmal
   nachgezogen werden (Fix-Loop F002).
5. **Fail-soft** — eine kaputte Protokolldatei darf weder Alarm noch Briefing verhindern.

## Dependencies

* **Upstream:** `alert_urgency` (Stufe je Meldung) · `alert_log.append_entry` (Protokoll) ·
  `alert_channels` / `send_telegram`+`send_sms` (Kanal-Opt-in) · `sms_allowed()` (Tarif-Gate)
* **Downstream:** `undelivered_hint.py` (zeigt den neuen Grund an, sobald er geschrieben wird) ·
  Cockpit-Kachel und Archiv-Statistik über `internal/store/log.go` (dürfen sich **nicht** ändern)

## Existing Specs

| Spec | Inhalt |
|---|---|
| `docs/specs/modules/feat_1459_alert_protokoll.md` | Protokoll-Schema, Zusicherungen D1/D4, offene Punkte O1–O3 |
| `docs/specs/modules/feat_1461_s3a_alarm_dringlichkeit.md` | Einstufung (v1.4, 16 ACs) |
| `docs/specs/modules/fix_1503_delta_dringlichkeit.md` | Δ-Einstufung, ordinale Sonderbehandlung |
| `docs/specs/modules/feat_1461_s3b1_briefing_sichtbarkeit.md` | Sichtbarkeit (v1.2, 17 ACs) — die Sicherheitsleine |
| `docs/specs/modules/rework_1467_s1_alarm_kennung.md` | `entity_id`/`entity_type` |
| `docs/specs/modules/compare_official_alert_channels.md` | Compare-Kanalregel |
| `docs/specs/_archive/modules/issue_1258_alarme_tab_official_warnings.md` | Herkunft von `alert_channels`, `AlertChannelPicker`, `AlarmeTab` |

**Zu S3b-2 selbst existiert noch keine Spec.**

## Relevante ADRs

| ADR | Bezug |
|---|---|
| **0043** — „Die Empfindlichkeitsstufe ist der **einzige** Alarm-Regler" | 🔴 Die wichtigste Entscheidungsfläche, siehe Risiko 1 |
| 0009 — Alarme sind Abweichungs-Wächter, keine absoluten Schwellen | bestätigt durch 0043 |
| 0016 — Amtliche Warnungen als additiver externer Typ | erklärt, warum sie einen eigenen Versandweg haben |
| 0004 — Signal entfernt | Kanäle sind genau E-Mail · Telegram · SMS |

## Risks & Considerations

1. **🔴 ADR-0043 sagt „ein Regler".** Die verworfene Alternative dort lautet wörtlich: *„Zwei
   Regler für dieselbe Frage sind für den Nutzer nicht erklärbar."* Die Schwelle je Kanal
   beantwortet eine **andere** Frage — die Empfindlichkeitsstufe entscheidet **ob** eine Lage
   meldenswert ist, die Schwelle **auf welchem Kanal** sie ankommt. Diese Abgrenzung muss die
   Spec ausdrücklich tragen, und die Entscheidung gehört in ein neues ADR (Entscheidungsfläche
   „Kanäle", CLAUDE.md). Sie darf nicht stillschweigend danebengestellt werden.

2. **🔴 Rote Linie #638.** Am 2026-06-09 wurde die Dringlichkeits-Auswahl aus der Oberfläche
   entfernt, weil eine Einstellung das Gegenteil ihres Versprechens tat: der Nutzer stellte einen
   Alarm ein und bekam nie einen. Der Unterschied jetzt: das Stummschalten ist **gewollt**. Damit
   es nicht wieder ungewollt und unsichtbar wird, gilt Pflicht 1 des Issues — eine Meldung, die
   auf allen Kanälen unter der Schwelle liegt, darf nicht spurlos verschwinden.

3. **🔴 Der frühe Ausstieg im Protokoll ist die konkrete Falle dazu.**
   `alert_log.append_entry():173-175` steigt bei leerem Kanal-Set aus, **bevor** irgendetwas
   geschrieben wird. Eine Schwelle, die schlicht als Filter auf die Kanalliste gebaut wird,
   erzeugt genau diesen Fall. Die Reihenfolge muss sein: einstufen → protokollieren (mit dem
   neuen Grund) → versenden.

4. **🔴 Datenverlust beim Speichern.** `internal/handler/trip.go:361-363` ersetzt den **ganzen**
   `AlertChannels`-Pointer, begründet mit „all-or-nothing, alle drei Felder werden immer
   gesendet". Sobald eine Schwelle dazukommt, stimmt diese Begründung nicht mehr: ein Client, der
   die Schwelle nicht kennt, löscht sie bei jedem Speichern still. Exakt die Fehlerklasse, die
   bei `OfficialWarnings.Sources` schon einmal nachgezogen werden musste
   (`internal/handler/trip.go:345-356`). CLAUDE.md-Pflicht: Read-Modify-Write mit **Merge**,
   niemals Replace.

5. **🔴 Vier Auflösungsstellen und zwei Versandpunkte, die vorbeilaufen.** Wer nur
   `_effective_alert_channels` und `_dispatch_alert_message` anfasst, lässt vier Wege
   ungefiltert: Trip-Radar (Inline-Kopie), Compare-Radar (hart E-Mail), Trip-amtlich und
   Compare-amtlich. Zusicherung muss an der Stelle geprüft werden, an der sie **wirkt**.

6. **Der Ortsvergleich hat kein Pendant zum Datenfeld.** Trip trägt `alert_channels` als Objekt,
   der Preset zwei flache Booleans ohne E-Mail-Feld. Eine geteilte Schwelle braucht dort entweder
   eine Angleichung oder eine bewusst dokumentierte Abweichung. Das Teilungs-Gate (CLAUDE.md,
   PO-Vorgabe mehrfach bekräftigt) gilt.

7. **Die Bedienfläche hat heute nur einen An/Aus-Schalter je Zeile.** `CHANNEL_SUB` ist der
   vorhandene freie Platz. Der Picker ist **einmal** eingebettet, schlägt aber auf **vier**
   Flächen durch — davon drei im Vergleichs-Zweig, der weder E-Mail-Toggle noch einen eigenen
   Speicherweg hat (`AlarmeTab.svelte:178-193`).

8. **Trip-Anlegen schreibt gar kein `alert_channels`.** Neue Trips landen im Legacy-Erbe. Eine
   Schwelle mit Vorgabewert muss auch für sie definiert sein.

9. **`MIN_SMS_LEVEL` aufgehen lassen ist eine Entscheidung, keine Ableitung.** Der Wert
   entspricht begrifflich „Schwelle MODERATE", filtert aber Briefing-**Inhalt**, nicht
   Alarm-**Versand**. Beides zusammenzulegen ändert das Verhalten des Briefings — das gehört
   vorgelegt, nicht nebenbei erledigt.

10. **Zusicherung D4 (#1459) gilt weiter:** Cockpit-Kachel und Archiv-Statistik lesen `entries`,
    nie `not_delivered`, und dürfen sich um keine Zahl ändern.

11. **Mandantentrennung:** echte `user_id` durchreichen, nie `"default"`; mit **zwei**
    verschiedenen Nutzern testen (CLAUDE.md, Pflicht bei jedem datenbewegenden Endpoint).

12. **Regressionsgefahr Kurznachricht:** SMS und Telegram sind 160-Zeichen-Formate; jede
    Änderung an ihren Renderpfaden ist zeichengenau nachzuweisen.

## Scope Assessment (vorläufig)

Python (Schwellen-Prüfung + vier Auflösungsstellen + zwei Vorbeiläufer + neuer Grund) ·
Go (Modell-Erweiterung + Merge statt Replace, Trip **und** Preset) ·
Frontend (Picker-Zeile + Zustand + Speicherweg, `route` **und** `vergleich`) · Tests.

⚠️ **Deutlich über der 250-Zeilen-Grenze je Arbeitsgang.** Ein weiterer Zuschnitt ist
wahrscheinlich — er wird in der Analyse-Phase mit einer Empfehlung vorgelegt, nicht hier
entschieden.

## Open Questions (für die Analyse-Phase)

- [ ] Abgrenzung zu ADR-0043 — neues ADR nötig? (Einschätzung: ja, Entscheidungsfläche „Kanäle")
- [ ] Vorgabewerte je Kanal — was gilt für Bestandsnutzer und für neue Trips?
- [ ] Geht `MIN_SMS_LEVEL` in der Einstellung auf, oder bleibt der Briefing-Filter unangetastet?
- [ ] Bekommt der Ortsvergleich dieselbe Struktur wie der Trip, oder eine dokumentierte Abweichung?
- [ ] Zuschnitt: Backend zuerst mit festen Vorgabewerten, Oberfläche danach?

---

# Analysis

## Type

**Feature** (Epic-Scheibe, kein Fehlverhalten im Bestand).

## Technischer Ansatz

### Die Naht: dort, wo die Kanalliste ENTSTEHT — nicht dort, wo versendet wird

`_dispatch_alert_message()` und die beiden Vorbeiläufer (`send_official_alert:661`,
`send_multi_location_official_alert:857`) sind reine **Konsumenten** eines fertigen
`set[str]` — sie prüfen nur noch `"email" in effective_channels`. Ein Filter dort verfehlt
zwei von sechs Wegen.

Die Schwelle greift deshalb an den **vier Auflösungsstellen**. Damit sind die beiden
Vorbeiläufer automatisch erfasst, weil ihr `effective_channels`-Argument von dort kommt.
Die Versand-Schicht bleibt unberührt.

### Neuer geteilter Baustein

`src/services/alert_channel_threshold.py` (Muster: `alert_urgency.py`, `alert_log.py`,
`compare_alert_channels.py`):

```python
def split_by_threshold(
    channels: set[str], urgency: str, thresholds: dict[str, str] | None,
) -> tuple[set[str], set[str]]:
    """(erlaubt, unterdrückt)."""
```

Der Rangvergleich wird **nicht** dupliziert, sondern als `meets_or_exceeds()` in
`alert_urgency.py` ergänzt — dort liegt `_RANK` bereits (`:21`).

### 🔴 Die Lösung für den frühen Ausstieg (`alert_log.py:173-175`)

**`effective_channels` bleibt roh.** Der Parameter behält seine heutige Bedeutung — das
unveränderte Opt-in des Nutzers. Der frühe Ausstieg feuert damit weiterhin **nur**, wenn der
Nutzer wirklich alle Kanäle abgeschaltet hat. Ablauf je Auflösungsstelle:

1. Rohes Opt-in `channels` wie heute berechnen (unverändert)
2. `allowed, suppressed = split_by_threshold(channels, urgency, thresholds)`
3. Versand mit `effective_channels=allowed` — **das** ist die Stummschaltung
4. `append_entry(effective_channels=channels, …, below_threshold_channels=suppressed, …)` —
   **unverändertes** `effective_channels`, neuer Parameter für den Grund

`_channels_not_sent()` (`:110-122`) bekommt eine dritte Fallunterscheidung:
`REASON_BELOW_THRESHOLD = "below_channel_threshold"`. Additiv, keine Schema-Migration.

Sind **alle** Kanäle unterdrückt, ist `reachable` leer ⇒ `target = "not_delivered"`
(`:202`) ⇒ für Go unsichtbar (D4 gewahrt) ⇒ von `read_undelivered()` als Vorfall gezählt,
weil der neue Grund **nicht** `channel_disabled` ist (`:246-267`). Genau das verhindert das
stille Verschwinden.

⚠️ **Detail:** `trip_alert.py:860-862` (`if not effective_channels: continue`) muss auf dem
**rohen** Set bleiben — auf `allowed` geprüft würde eine vollständig unterdrückte Meldung
wieder spurlos übersprungen statt protokolliert.

⚠️ **Pflicht:** Label für den neuen Grund in `undelivered_hint.py:36-39`, sonst steht er
unübersetzt in der Mail.

## Datenmodell: getrenntes Geschwisterfeld

Empfohlen und entschieden: ein **neues Feld neben** `alert_channels`, nicht darin.

```go
type AlertChannelThresholdsConfig struct {
    Email    *string `json:"email,omitempty"`    // "LOW"|"MODERATE"|"HIGH"
    Telegram *string `json:"telegram,omitempty"`
    Sms      *string `json:"sms,omitempty"`
}
```
Auf `Trip` **und** `ComparePreset` je ein `AlertChannelThresholds *AlertChannelThresholdsConfig`
— nach dem bereits geteilten Muster von `OfficialWarningsConfig` (`internal/model/trip.go:165`).

**Verworfen:**
* *Stufen-Felder in `AlertChannelsConfig`* — die Struktur wird heute **komplett ersetzt**
  (`internal/handler/trip.go:361-363`, „all-or-nothing"). Ein Client ohne Kenntnis der Stufen
  löscht sie bei jedem Speichern still.
* *Unterobjekt `{enabled, min_urgency}` je Kanal* — Python liest `trip.alert_channels.get(ch)`
  heute als **bool** (`trip_alert.py:1198-1206`); ein Dict wäre dort immer wahr, der An/Aus-
  Schalter würde stillschweigend wirkungslos.

**Zwei Ebenen Datenverlustschutz, beide bereits im Repo etabliert:**
1. Top-Level `nil`-Erbe (wie `internal/handler/trip.go:337-339`)
2. **Feld-Level-Merge innerhalb** des Unterobjekts — derselbe Fix wie bei
   `OfficialWarnings.Sources` (`:345-356`, Fix-Loop F002). **Pflicht, kein Kann.**

## 🔴 Gemessene Korrektur zu `MIN_SMS_LEVEL`

Die Formulierung im Issue-Kommentar vom 2026-08-05 („`MIN_SMS_LEVEL` ist bereits heute eine
feste Kanal-Schwelle … muss in der einstellbaren aufgehen") ist **ungenau**. Nachgemessen:

| Weg | Renderer | Stufen-Filter? |
|---|---|---|
| **Briefing** SMS (Trip) | `sms_trip.py:151` → `official_alerts_to_sms_entries` | **ja**, `MIN_SMS_LEVEL` (`official_alerts.py:388`) |
| **Briefing** SMS (Compare) | `comparison.py:869` → dieselbe Funktion | **ja** |
| **Briefing** Telegram (Trip) | `narrow.py:386` | **ja** |
| **Alarm** SMS (alle Wege) | `render_official_alert_sms` (`official_alerts.py:1694`), gerufen aus `notification_service.py:731/752/979/1014` | **nein** — kein Stufen-Filter |

⇒ `MIN_SMS_LEVEL` filtert **ausschließlich Briefing-Inhalt**, nie den Alarm-Versand. Es ist
also **keine** Kanal-Schwelle im Sinne dieser Scheibe, sondern eine Inhaltsregel auf einer
anderen Ebene. Die beiden zusammenzulegen ändert das Verhalten des normalen Briefings mit —
das ist eine eigene Entscheidung, keine Ableitung.

## Zuschnitt-Empfehlung

| Scheibe | Inhalt | Warum diese Reihenfolge |
|---|---|---|
| **S3b-2a** | Kanal-Schwelle für **Trips**, Ende-zu-Ende (Go-Modell + Merge · Python-Baustein + zwei Trip-Auflösungsstellen · Protokoll-Grund + Label · Picker-Zeile + `route`-Speicherweg) | Einziger vollständiger Speicherweg (`PUT /api/trips/{id}`), Picker für Trips an **einer** Stelle. Validiert Merge-Muster und Baustein am risikoärmeren Pfad |
| **S3b-2b** | **Ortsvergleich**-Parität (Preset-Feld + RMW · `compare_alert_channels.py` + Hartverdrahtung `compare_radar_alert.py` · Compare-Speicherweg) | Kein Pendant zum Datenfeld, kein eigener Speicherweg, **drei** Einbettungsflächen — höheres Oberflächen-Risiko, profitiert von bewiesener Backend-Logik. **Kein neuer UI-Baustein** (Picker ist bereits geteilt) |
| **S3b-2c** *(nur bei PO-„ja")* | `MIN_SMS_LEVEL` an die Einstellung angleichen | Andere Ebene (Briefing-**Inhalt**), eigenes Regressionsrisiko für die 160-Zeichen-Renderer — nicht mit 2a/2b vermischen |

## Risiko-Bewertung

| Risiko | Bewertung |
|---|---|
| **Rote Linie #638** | Durch Bauart gebannt, nicht durch Disziplin: der neue Grund landet im Protokoll und wird von der S3b-1-Sichtbarkeit angezeigt |
| **D4 (#1459)** | Strukturell unberührt — die Schwelle ändert nur, welches Ziel (`entries` vs. `not_delivered`) getroffen wird, nie die Zähllogik. Trotzdem mit Test bewachen |
| **Kurznachricht-Zeichengleichheit** | Nur gefährdet, wenn Render-Pfade angefasst werden. 2a/2b fassen sie **nicht** an |
| **🔴 Inline-Kopie `trip_alert.py:852-860`** | Höchstes praktisches Risiko: vergessen ⇒ Trip-Radar bleibt dauerhaft ungefiltert, für den Nutzer unsichtbar. Muss in **derselben** Änderung mitgehen |
| **🔴 `compare_radar_alert.py:131/150`** | Hart `{"email"}`, kennt kein Preset zum Nachschlagen ⇒ muss auf den Resolver umgestellt werden, sonst verspricht die Oberfläche etwas, das dort nie wirkt |
| **Mandantentrennung** | Kein neues Risiko (gleicher Dateiweg wie `alert_channels`), Zwei-Nutzer-Test bleibt Pflicht |

## Affected Files — Scheibe S3b-2a

| Datei | Änderung | Inhalt |
|---|---|---|
| `src/services/alert_channel_threshold.py` | CREATE | `split_by_threshold()` + Vorgabewerte |
| `src/services/alert_urgency.py` | MODIFY | `meets_or_exceeds()` |
| `src/services/alert_log.py` | MODIFY | `below_threshold_channels` + neuer Grund |
| `src/services/trip_alert.py` | MODIFY | zwei Auflösungsstellen (`:1171`, `:852-860`) |
| `src/output/renderers/email/undelivered_hint.py` | MODIFY | Label für den neuen Grund |
| `internal/model/trip.go` | MODIFY | `AlertChannelThresholdsConfig` + Feld |
| `internal/handler/trip.go` | MODIFY | RMW mit Feld-Level-Merge |
| `src/app/loader.py`, `src/app/trip.py` | MODIFY | Feld durchreichen |
| `frontend/.../AlertChannelPicker.svelte` | MODIFY | Stufen-Auswahl je Zeile (`CHANNEL_SUB`-Platz) |
| `frontend/.../alertChannelState.ts`, `alarmeDeliveryPayload.ts`, `AlarmeTab.svelte` | MODIFY | Zustand + Speicherweg (`route`) |
| `docs/reference/api_contract.md`, `docs/adr/00XX-…` | MODIFY/CREATE | Vertrag + Grundsatzentscheidung |
| Tests | CREATE | Verhaltensnachweis |

## Scope Assessment

* Dateien S3b-2a: **~12 geändert, 2 neu**
* Geschätzt: **~260 Zeilen Produktivcode**, inkl. Tests deutlich mehr
* Risiko: **MEDIUM–HIGH** — erster absichtlicher Eingriff in den Alarm-Versand
* ⚠️ Ein `loc_limit_override` wird voraussichtlich nötig (S3b-1 zum Vergleich: 280–320
  geschätzt, mit Tests weit darüber). **PO-Entscheidung, wird erst erfragt, wenn erreicht.**

## Open Questions (PO)

- [ ] Startwert je Kanal für Bestand und neue Trips
- [ ] `MIN_SMS_LEVEL`: aufgehen lassen oder unangetastet?
- [ ] Zuschnitt: Trips zuerst, Ortsvergleich danach?

Als Tech Lead selbst entschieden (nicht vorgelegt): Naht an den vier Auflösungsstellen ·
Baustein-Signatur · getrenntes Geschwisterfeld statt Erweiterung · Render-Pfade unberührt ·
neues ADR wird geschrieben (Entscheidungsfläche „Kanäle").

## PO-Entscheidungen 2026-08-05

| Frage | Entscheidung | Begründung |
|---|---|---|
| **Startwert je Kanal** | Alle drei Kanäle starten bei **`LOW`** („gering") | Es wird nirgends stiller, bis der Nutzer selbst eine Schwelle hochsetzt — rote Linie #638 |
| **`MIN_SMS_LEVEL`** | **Geht sofort in der Einstellung auf** (gegen die Tech-Lead-Empfehlung, PO-Entscheid) | Keine zweite unsichtbare Schwelle daneben |
| **Auflösung des Zielkonflikts** | Der **Alarm**-Versand bleibt unverändert; der **SMS-/Telegram-Bericht** bekommt künftig auch **gelbe** amtliche Warnungen | „Mehr Information ist nie ein Sicherheitsproblem, weniger schon." Kosten: Platz in den 160 Zeichen — bewusst in Kauf genommen |
| **Zuschnitt** | **Trips zuerst** (S3b-2a), Ortsvergleich danach (S3b-2b) | Nutzen früher; das Oberflächen-Risiko des Vergleichs-Zweigs profitiert von bewiesener Backend-Logik |

### 🔴 Der gemessene Zielkonflikt, der die dritte Entscheidung nötig machte

Zwei **gegenläufige** Bestandsverhalten — eine einzige Einstellung kann nicht beide erhalten:

| | gelbe amtliche Warnung (Stufe 2) heute |
|---|---|
| **Alarm**-SMS | **geht raus** — `trip_alert.py:1102` löst bei *steigender* Stufe aus, ohne Untergrenze; `render_official_alert_sms` hat keinen Stufen-Filter |
| **Briefing**-SMS/Telegram | **erscheint nie** — `MIN_SMS_LEVEL = 3` |

* Startwert `LOW` ⇒ Alarme unverändert, Bericht bekommt **mehr** ⇒ **gewählt**
* Startwert `MODERATE` für SMS/Telegram ⇒ Bericht unverändert, Alarme werden **stiller** ⇒ verworfen (#638-Muster)

### Folge für den Zuschnitt

`MIN_SMS_LEVEL` hat drei Verwendungsstellen, zwei davon berühren den Ortsvergleich. Damit
„Trips zuerst" trotzdem hält:

`official_alerts_to_sms_entries()` (`official_alerts.py:368`) bekommt einen **Schwellen-Parameter
mit Vorgabewert `MIN_SMS_LEVEL`**. In S3b-2a übergeben ihn die **Trip**-Pfade (`sms_trip.py:151`,
`narrow.py:386`) aus der Nutzereinstellung; die **Compare**-Pfade (`comparison.py:704/869`)
lassen ihn weg und verhalten sich unverändert, bis S3b-2b sie nachzieht. Keine Scheibe verändert
Verhalten, das sie nicht besitzt.

**Abbildung Einstellung → Warnstufe** (über die bestehende `LEVEL_LETTERS`, keine zweite
Zahlenreihe): `LOW` → ab Stufe 2 (gelb) · `MODERATE` → ab Stufe 3 (orange, heutiges Verhalten) ·
`HIGH` → nur Stufe 4 (rot).

### Damit erledigt

- [x] Startwert je Kanal
- [x] `MIN_SMS_LEVEL`: aufgehen lassen — ja, sofort
- [x] Zuschnitt: Trips zuerst

**Diese Scheibe ist S3b-2a.** S3b-2b (Ortsvergleich) folgt als eigener Arbeitsgang.
