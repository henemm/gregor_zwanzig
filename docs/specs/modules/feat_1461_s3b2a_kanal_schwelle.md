---
entity_id: feat_1461_s3b2a_kanal_schwelle
type: feature
created: 2026-08-05
updated: 2026-08-05
status: draft
version: "1.1"
tags: [alerts, channels, threshold, trip, epic-1458, issue-1461, s3b2a]
---

# Einstellbare Dringlichkeits-Schwelle je Alarm-Kanal — Trips (#1461 S3b-2a)

## Approval

- [x] Approved — PO-„go" 2026-08-05 (Beleg als Kommentar in Issue #1461)

## Purpose

Der Nutzer stellt je Alarm-Kanal eines Trips (E-Mail · Telegram · SMS) ein, **ab welcher
Dringlichkeit** (gering · mittel · hoch) ihn eine Alarm-Meldung dort erreicht — eine
Satelliten-SMS kostet Geld und Akku, eine E-Mail nichts. Eine Meldung, die auf einem Kanal
unter der dort eingestellten Schwelle liegt, geht auf diesem Kanal nicht raus, verschwindet
aber nicht spurlos: sie steht im Alarm-Protokoll und im nächsten Briefing als nicht zugestellt
(die Sicherheitsleine aus S3b-1). Diese Scheibe deckt ausschließlich **Trips** ab; der
Ortsvergleich folgt als eigener Arbeitsgang S3b-2b.

## Source

- **Datei (neu):** `src/services/alert_channel_threshold.py`
- **Dateien (geändert):** `src/services/alert_urgency.py` · `src/services/alert_log.py` ·
  `src/services/trip_alert.py` · `src/output/renderers/email/undelivered_hint.py` ·
  `src/output/renderers/alert/official_alerts.py` ·
  `src/output/renderers/sms_trip.py` · `src/output/renderers/narrow.py` ·
  `src/output/renderers/trip_report.py` (Durchreichung der Nutzer-Schwelle an
  `official_alerts_to_sms_entries()`) ·
  `internal/model/trip.go` · `internal/handler/trip.go` · `src/app/loader.py` ·
  `src/app/trip.py` · `frontend/src/lib/components/shared/AlertChannelPicker.svelte` ·
  `frontend/src/lib/components/shared/alarme-tab/alertChannelState.ts` ·
  `frontend/src/lib/components/shared/alarme-tab/alarmeDeliveryPayload.ts` ·
  `frontend/src/lib/components/shared/AlarmeTab.svelte` ·
  `frontend/src/lib/types.ts` (Feld `alert_channel_thresholds` am `Trip`-Typ) ·
  `frontend/src/lib/components/trip-detail/AlarmeScheduleTab.svelte` (reicht
  `existingChannelThresholds` als Prop an `AlarmeTab` durch) ·
  `frontend/src/lib/components/shared/__tests__/alarme_tab_catalog_prop_structure.test.ts`
  (bestehende Attribut-Liste der Trip-Einbettung um `existingChannelThresholds` erweitert) ·
  `docs/reference/api_contract.md` · `docs/adr/README.md` (Index-Zeile für ADR-0046)
- **Datei (neu, Dokumentation):** `docs/adr/0046-alarm-kanal-schwelle.md`
- **Schicht:** Python-Core (Naht + Protokoll + Bericht-Filter, `src/services/`,
  `src/output/`) · Go-API (Datenmodell + Persistenz, `internal/model/`, `internal/handler/`)
  · Frontend (Oberfläche + `route`-Speicherweg, `frontend/src/lib/components/shared/`).
  **Bewusst ausgeklammert:** jeder Code unter `src/services/compare_*`,
  `internal/model/compare_preset.go`, `internal/handler/compare_preset.go` und die drei
  Compare-Einbettungsflächen des Pickers — das ist S3b-2b.

## Estimated Scope

- **LoC:** ~260 Produktivcode (Tech-Lead-Schätzung aus der Analyse), deutlich mehr inkl. Tests
- **Files:** ~12 geändert, 2–3 neu (inkl. ADR)
- **Effort:** medium–high — erster absichtlicher Eingriff in den Alarm-**Versand**, nicht nur
  in seine Protokollierung

⚠️ **Die 250-Zeilen-Grenze wird voraussichtlich gerissen.** Die Vorgänger-Scheibe S3b-1 lag
mit Tests bei über 1600 Zeilen; diese Scheibe fasst zusätzlich Go-Modell, Go-Persistenz und
Frontend an. Ein `loc_limit_override` wird beim Erreichen erfragt, nicht hier vorab
festgelegt — gleiches Vorgehen wie bei S3b-1.

## Dependencies

| Entity | Typ | Zweck |
|---|---|---|
| `feat_1461_s3a_alarm_dringlichkeit` | liest | `severity` je Protokoll-Eintrag als Vergleichsbasis der Schwelle (Rangordnung `LOW`/`MODERATE`/`HIGH`) |
| `feat_1459_alert_protokoll` | erweitert | `alert_log.append_entry()` bekommt `below_threshold_channels`, additiver Grund `below_channel_threshold` — keine Schema-Migration |
| `feat_1461_s3b1_briefing_sichtbarkeit` | nutzt | `read_undelivered()` und `undelivered_hint.py` zeigen den neuen Grund automatisch, sobald er geschrieben wird — es braucht nur das neue Label |
| ADR-0043 | grenzt ab | Die Empfindlichkeitsstufe entscheidet **OB** eine Lage meldenswert ist; die Kanal-Schwelle entscheidet **AUF WELCHEM WEG** eine bereits ausgelöste Meldung ankommt — zwei Fragen, kein zweiter Regler für dieselbe |
| `output.tokens.hazard_symbols.LEVEL_LETTERS`/`MIN_SMS_LEVEL` | nutzt | bestehende Abbildung amtliche Stufe → gering/mittel/hoch; keine zweite Zahlenreihe für die Einstellung |
| `internal/model/trip.go` (Muster `OfficialWarningsConfig`) | folgt | Vorbild für Top-Level-`nil`-Erbe + Feld-Level-Merge des neuen Unterobjekts |

## Implementation Details

### Die Naht: zwei Auflösungsstellen bei Trips — nicht die Versandschicht

Der Versand (`notification_service._dispatch_alert_message()` und Konsorten) prüft nur noch
ein fertiges Kanal-Set — ein Filter dort verfehlt jeden Aufrufer, der sein Set anders baut.
Die Schwelle greift deshalb dort, wo das Kanal-Set für einen Trip **entsteht**. Das sind bei
Trips **zwei** Stellen, nicht eine:

1. `TripAlertService._effective_alert_channels()` — die reguläre Auflösung für
   Vorhersage-Änderung und amtliche Warnung.
2. Die **Inline-Kopie** im Radar-Zweig derselben Klasse — eine eigene, kleinere Ableitung aus
   den Trip-Kanal-Einstellungen, die (1) nicht aufruft.

Wird die zweite Stelle vergessen, bleiben Regenradar-Alarme dauerhaft ungefiltert, ohne dass
das für den Nutzer sichtbar wäre — er hat eine Schwelle eingestellt, die nur bei zwei von drei
Alarmarten wirkt. AC-3 nagelt genau das fest.

### Reihenfolge — das Herzstück: einstufen → protokollieren → versenden

Das Protokoll bricht heute früh ab, wenn das übergebene Kanal-Set leer ist — **bevor**
irgendetwas geschrieben wird. Eine Schwelle, die naiv als Filter auf genau dieses Set gebaut
wird, würde eine vollständig unterdrückte Meldung also spurlos verschwinden lassen (die rote
Linie #638). Deshalb bleibt der an das Protokoll übergebene Wert **roh** — das unveränderte
Opt-in des Nutzers, wie heute:

1. Rohes Opt-in wie bisher berechnen (unverändert).
2. Aus Dringlichkeit und den eingestellten Schwellen wird bestimmt, welche der
   eingeschalteten Kanäle diese eine Meldung erreichen dürfen und welche nicht.
3. Versendet wird nur an die erlaubten Kanäle — **das** ist die Stummschaltung.
4. Protokolliert wird mit dem **rohen**, unveränderten Opt-in plus einer zusätzlichen Angabe,
   welche Kanäle wegen der Schwelle ausgeschlossen wurden.

Der frühe Abbruch bei leerem Kanal-Set bleibt dadurch auf der rohen Größe — er feuert
weiterhin nur, wenn der Nutzer wirklich **alle** Kanäle abgeschaltet hat, nicht wenn eine
Schwelle sie stummschaltet. Sind durch die Schwelle **alle** Kanäle einer Meldung
ausgeschlossen, landet der Eintrag dort, wo heute schon jede komplett fehlgeschlagene
Zustellung landet (für Go unsichtbar, Zusicherung D4 aus #1459) — und wird von der
S3b-1-Sichtbarkeit als Vorfall gezählt, weil der neue Grund kein abgeschalteter Kanal ist.

### Neuer geteilter Baustein

Ein neues Modul im Muster der bestehenden geteilten Bausteine (`alert_urgency.py`,
`alert_log.py`, `compare_alert_channels.py`) trennt erlaubte von unterdrückten Kanälen:

```python
def split_by_threshold(
    channels: set[str], urgency: str, thresholds: dict[str, str] | None,
) -> tuple[set[str], set[str]]:
    """(erlaubt, unterdrückt). Kein gesetzter Wert je Kanal -> Startwert 'gering'."""
```

Der Rangvergleich selbst wird **nicht** dupliziert — er kommt als zusätzliche Funktion in das
bestehende Modul, das die Rangordnung bereits kennt (die drei Stufen `LOW`/`MODERATE`/`HIGH`
mit ihrer Reihenfolge existieren dort schon aus S3a).

### Protokoll — neuer Grund, ein neues Label

Die Aufschlüsselung „welcher eingeschaltete Kanal hat die Meldung nicht bekommen und warum"
bekommt eine dritte Fallunterscheidung neben den bestehenden zwei (technischer Fehlschlag /
vom Nutzer abgeschaltet): **unter der eingestellten Schwelle**. Additiv, freie Zeichenkette,
keine Schema-Migration.

Die Lesefunktion aus S3b-1, die entscheidet, was als Vorfall im Briefing erscheint, filtert
bereits nur genau einen Grund heraus (den abgeschalteten Kanal) und zählt jeden anderen Grund
als Vorfall — der neue Grund braucht dort **keine** Codeänderung, nur eine Übersetzung ins
Deutsche im Anzeige-Baustein, sonst stünde der interne Bezeichner unübersetzt in der Mail.

### Datenmodell — getrenntes Geschwisterfeld, zwei Ebenen Datenverlustschutz

Ein **neues Feld neben** dem bestehenden Kanal-Opt-in, nicht darin — das bestehende Feld wird
heute beim Speichern als Ganzes ersetzt („all-or-nothing", alle drei Kanal-Werte kommen immer
komplett vom Client); ein Client, der die Schwelle nicht kennt, würde sie sonst bei jedem
Speichern still löschen.

```go
type AlertChannelThresholdsConfig struct {
    Email    *string `json:"email,omitempty"`    // "LOW"|"MODERATE"|"HIGH"
    Telegram *string `json:"telegram,omitempty"`
    Sms      *string `json:"sms,omitempty"`
}
```

Je ein Pointer-Feld auf `Trip`, nach demselben Muster wie das bestehende
Warnungs-Unterobjekt. **Zwei** Ebenen Datenverlustschutz, beide bereits im Repo etabliert und
hier **Pflicht, kein Kann**:

1. **Top-Level-`nil`-Erbe** — ein PUT ohne das Feld im Body lässt den bestehenden Wert
   unangetastet (Muster: bestehendes Warnungs-Unterobjekt).
2. **Feld-Level-Merge innerhalb** des Unterobjekts — fehlt im Body nur der Wert für einen der
   drei Kanäle, bleibt dessen bestehender Wert erhalten, statt dass das ganze Unterobjekt
   ersetzt wird. Exakt der Fix, der beim Warnungs-Unterobjekt bereits einmal nachgezogen
   werden musste, weil er beim ersten Wurf fehlte.

### MIN_SMS_LEVEL geht auf — nur für Trip-Pfade

Die geteilte Funktion, die amtliche Warnungen für den SMS-/Telegram-**Bericht** filtert,
bekommt einen Schwellen-Parameter mit **Vorgabewert** gleich der heutigen festen Stufe — wer
ihn nicht übergibt, sieht keine Verhaltensänderung. Die **Trip**-Berichtspfade (SMS und
Telegram) übergeben künftig die jeweilige Nutzereinstellung für den entsprechenden Kanal; die
**Compare**-Berichtspfade lassen den Parameter weg und bleiben unverändert, bis S3b-2b sie
nachzieht.

**Abbildung Einstellung → Warnstufe**, über die bestehende Stufen-Abbildung, keine zweite
Zahlenreihe:

| Kanal-Schwelle | ab amtlicher Stufe |
|---|---|
| gering (Startwert) | 2 (gelb) |
| mittel | 3 (orange, heutiges Verhalten) |
| hoch | 4 (rot) |

Startwert „gering" ⇒ der Bericht zeigt künftig **mehr** (auch gelbe Warnungen), der
Alarm-**Versand** bleibt unverändert — das ist die bewusste Auflösung des gemessenen
Zielkonflikts (PO-Entscheidung 2026-08-05): eine gelbe amtliche Warnung löst schon heute einen
Alarm aus, ohne dass der Bericht sie je zeigte.

### Oberfläche — Picker-Zeile + Speicherweg (nur `route`)

Der geteilte Kanal-Picker bekommt je Zeile eine Stufen-Auswahl an der Stelle, an der heute nur
statischer Beschreibungstext steht. Der Picker ist **einmal** eingebettet, wird aber auf vier
Flächen wiederverwendet, davon drei im Vergleichs-Zweig. Diese Scheibe bedient **ausschließlich
den Trip-Speicherweg** (`PUT /api/trips/{id}` samt der dafür zuständigen Zustands- und
Payload-Bausteine); der Vergleichs-Zweig bettet dieselbe, jetzt erweiterte Komponente weiterhin
ein und darf dadurch **nicht kaputtgehen** — er bekommt aber noch keine eigene Wirkung
(AC-11).

### ⚠️ Betriebshinweis: das Renderer-Commit-Gate (#811) greift zwingend

Diese Scheibe fasst mit `src/output/renderers/email/undelivered_hint.py` und
`src/output/renderers/sms_trip.py` **zwei** Dateien aus der Sperrliste des Gates an. Jeder
Commit ist damit blockiert, bis im aktiven Workflow **beide** frisch vorliegen:
`tests/tdd/test_issue_811_mode_matrix.py` grün **und** ein erfolgreicher Lauf von
`.claude/hooks/briefing_mail_validator.py` gegen eine echt zugestellte Staging-Mail. Das ist
einzuplanen, nicht zu umgehen.

## Expected Behavior

- **Input:** eine ausgelöste Alarm-Meldung eines Trips (Vorhersage-Änderung, Regenradar oder
  amtliche Warnung) mit ihrer Dringlichkeit, das rohe Kanal-Opt-in des Nutzers, die je Kanal
  eingestellte Schwelle (Vorgabe „gering", wenn nichts eingestellt).
- **Output:** Versand nur an die Kanäle, die die Schwelle erreichen; ein Protokoll-Eintrag mit
  dem unveränderten rohen Opt-in plus der Information, welche Kanäle wegen der Schwelle
  ausgeschlossen wurden; im nächsten Briefing eine Zeile für jede vollständig unterdrückte
  Meldung.
- **Side effects:** Speichern der Kanal-Schwellen eines Trips über die Oberfläche schreibt ein
  neues Unterobjekt, ohne das bestehende Kanal-Opt-in oder andere Trip-Felder zu berühren. Am
  Versandverhalten des Ortsvergleichs ändert sich nichts.

## Acceptance Criteria

- **AC-1:** Given ein Trip hat für keinen Kanal eine Schwelle eingestellt / When ein Alarm mit
  geringer Dringlichkeit ausgelöst wird / Then erreicht die Meldung genau die Kanäle, die sie
  auch vor dieser Änderung erreicht hätte — kein Kanal wird stiller.
  - Test: Versandzähler je Kanal für denselben Alarm-Lauf mit unverändertem Trip (keine
    gesetzte Schwelle) vor und nach der Änderung vergleichen.

- **AC-2:** Given ein Nutzer hat für einen Kanal eine höhere als die geringste Dringlichkeit
  eingestellt / When eine Meldung mit geringerer Dringlichkeit ausgelöst wird / Then erreicht
  sie diesen einen Kanal nicht, während ein anderer, unveränderter Kanal sie weiterhin bekommt.
  - Test: Trip mit erhöhter Schwelle auf einem Kanal, Alarm mit geringer Dringlichkeit
    auslösen, Zustellung je Kanal einzeln prüfen.

- **AC-3:** Given ein Nutzer hat für einen Kanal eine höhere Schwelle eingestellt / When ein
  durch Regenradar ausgelöster Alarm mit geringerer Dringlichkeit auftritt / Then bleibt
  dieser Kanal ebenso stumm wie bei einer durch Vorhersage-Änderung ausgelösten Meldung.
  - Test: den Regenradar-Alarmpfad separat (nicht den Vorhersage-Änderungspfad) durchlaufen
    lassen, Zustellung je Kanal prüfen — deckt den Pfad ab, der bei Übernahme nur der
    Hauptstelle ungefiltert bliebe.

- **AC-4:** Given eine Meldung liegt auf jedem eingeschalteten Kanal unter der dort
  eingestellten Schwelle / When der Alarm ausgelöst wird / Then steht sie danach im
  Alarm-Protokoll und erscheint als nicht zugestellt im nächsten Briefing des Trips.
  - Test: Trip mit hoher Schwelle auf allen Kanälen, Alarm mit geringer Dringlichkeit
    auslösen; Protokolldatei auf einen Eintrag prüfen, danach das Briefing rendern und die
    Zeile im erzeugten Text nachweisen.

- **AC-5:** Given eine Meldung wurde wegen der Kanal-Schwelle unterdrückt / When das nächste
  Briefing erzeugt wird / Then nennt die dafür erzeugte Zeile einen für den Nutzer
  verständlichen, deutschen Grund — keinen internen Bezeichner.
  - Test: erzeugten Mail-Text prüfen: ein lesbares Wort steht dort, keine rohe Konstante wie
    ein englischer Code-Bezeichner.

- **AC-6:** Given ein Nutzer hat für einen Kanal eine erhöhte Schwelle gesetzt / When er
  anschließend über die Oberfläche eine andere Einstellung des Trips ändert und speichert,
  ohne dass dabei die Schwellen-Einstellung mitgeschickt wird / Then bleibt seine
  Schwellen-Einstellung unverändert erhalten.
  - Test: Trip mit gesetzter Schwelle anlegen, eine andere Einstellung ohne das Schwellenfeld
    im Speicher-Aufruf senden, Trip danach neu laden, Schwelle unverändert vorfinden.

- **AC-7:** Given ein Nutzer hat für zwei Kanäle je eine eigene Schwelle gesetzt / When er
  über die Oberfläche nur einen der beiden Kanäle ändert und speichert / Then bleibt die
  Schwelle des anderen, nicht angefassten Kanals unverändert.
  - Test: Speicher-Aufruf mit nur einem geänderten Kanal-Wert im Schwellen-Unterobjekt
    senden, den unveränderten Kanal danach prüfen.

- **AC-8:** Given zwei verschiedene Nutzer haben für ihre jeweils eigenen Trips
  unterschiedliche Kanal-Schwellen eingestellt / When bei beiden im selben Testlauf ein Alarm
  ausgelöst wird / Then wirkt bei jedem Nutzer ausschließlich seine eigene Einstellung — keine
  Vermischung.
  - Test: zwei getrennte Nutzer-Datenordner, je eigener Trip und Schwelle, beide Läufe
    wechselseitig prüfen.

- **AC-9:** Given ein Alarm-Lauf erzeugt sowohl zugestellte als auch wegen der Schwelle
  unterdrückte Meldungen / When die Cockpit-Kachel und die Archiv-Statistik danach abgefragt
  werden / Then zeigen sie dieselben Zahlen wie vor dieser Änderung.
  - Test: die für die Kachel und die Statistik maßgeblichen Protokoll-Einträge vor und nach
    dem Patch für denselben Ablauf zählen und vergleichen.

- **AC-10:** Given ein Nutzer öffnet die Alarm-Einstellungen eines Trips / When er dort
  nachsieht / Then erkennt er für jeden der drei Kanäle, ab welcher Dringlichkeit dieser ihn
  erreicht, und kann diese Einstellung ändern.
  - Test: die Oberfläche öffnen, für jeden Kanal eine Stufen-Auswahl mit dem aktuellen Wert
    vorfinden, einen Wert ändern und die dadurch ausgelöste Speicherung nachweisen.

- **AC-11:** Given ein Ortsvergleich ist von dieser Änderung nicht betroffen / When dort ein
  Alarm ausgelöst wird oder die Oberfläche des Vergleichs-Zweigs geöffnet wird / Then
  verhalten sich Versand, Protokoll und Bericht des Ortsvergleichs exakt wie vor dieser
  Änderung — unabhängig davon, welche Kanal-Schwellen bei Trips gesetzt sind.
  - Test: den Vergleichs-Alarmpfad mit unveränderten Zähl- und Protokollwerten vor/nach dem
    Patch durchlaufen lassen; zusätzlich die Oberfläche im Vergleichs-Zweig öffnen und
    speichern, ohne dass ein Fehler auftritt.

- **AC-12:** Given ein Nutzer hat für einen Kanal die Startschwelle (gering) unverändert
  gelassen / When sein reguläres Briefing eine amtliche Warnung der niedrigsten wirksamen
  Stufe enthält / Then erscheint diese Warnung jetzt im Kurznachrichten-Bericht dieses Trips,
  wo sie vorher fehlte.
  - Test: die Briefing-Kurznachricht des Trips mit einer amtlichen Warnung dieser Stufe
    erzeugen, den entsprechenden Eintrag im Ergebnis nachweisen — vorher war er dort leer.

- **AC-13:** Given ein Nutzer hat für einen Kanal keine Schwelle über gering gesetzt / When
  eine amtliche Warnung der niedrigsten wirksamen Stufe einen Alarm auslöst / Then wird die
  Alarm-Meldung genauso verschickt wie vor dieser Änderung.
  - Test: Versandzähler und Protokolleintrag für diesen Alarm vor und nach dem Patch
    vergleichen.

## Known Limitations

- **Ortsvergleich (S3b-2b) hat noch keine Wirkung.** Die Oberfläche ist zwar an drei weiteren
  Flächen des Vergleichs-Zweigs eingebettet, ihre dort gesetzten Werte werden weder
  gespeichert noch bei einem Vergleichs-Alarm ausgewertet.
- **MIN_SMS_LEVEL-Aufgehen gilt nur für Trip-Pfade.** Ortsvergleichs-Briefings filtern
  amtliche Warnungen im Bericht weiterhin mit der festen mittleren Stufe, unangetastet bis
  S3b-2b.
- **Ein neu angelegter Trip erhält weiterhin gar kein Kanal-Opt-in-Objekt** (Bestandslücke aus
  einer früheren Scheibe, unabhängig von dieser hier) — die Kanal-Schwelle erbt in diesem Fall
  den Code-Vorgabewert „gering", ohne dass er je gespeichert wurde. Nachrüstbar erst, wenn die
  Trip-Anlage-Oberfläche den Alarm-Tab überhaupt einbettet.
- Die noch ungenutzten Protokoll-Gründe (Ruhezeit, Tageslimit, Sperrzeit) bleiben unverändert
  unbenutzt — diese Scheibe ergänzt nur den vierten, jetzt tatsächlich gesetzten Grund „unter
  der Schwelle".
- **Kein neuer Alarm-Auslöser, keine neue Empfindlichkeitsstufe.** Die Kanal-Schwelle
  entscheidet nicht, OB eine Lage meldenswert ist (das bleibt allein die Empfindlichkeitsstufe
  aus ADR-0043) — nur, AUF WELCHEM Weg eine bereits ausgelöste Meldung ankommt.
- **Zielkonflikt bewusst zulasten der 160-Zeichen-Reserve gelöst.** Mehr amtliche Warnungen im
  Bericht kosten dort Platz — PO-Entscheidung 2026-08-05, bewusst in Kauf genommen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** [ADR-0046](../../adr/0046-alarm-kanal-schwelle.md) —
  `docs/adr/0046-alarm-kanal-schwelle.md`, Status Akzeptiert (Entscheidungsfläche
  „Kanäle", CLAUDE.md).
- **Rationale:** ADR-0043 legt fest, dass die Empfindlichkeitsstufe der **einzige** Regler
  dafür ist, OB eine Wetterlage überhaupt eine Meldung wert ist — „zwei Regler für dieselbe
  Frage sind für den Nutzer nicht erklärbar". Die Kanal-Schwelle beantwortet eine **andere**
  Frage: AUF WELCHEM Weg eine bereits ausgelöste Meldung den Nutzer erreicht. Sie ersetzt
  keinen Teil der Empfindlichkeitsstufe und steht ihr nicht für denselben Zweck zur Seite —
  deshalb kein Widerspruch zu ADR-0043, aber eine eigene, dokumentationswürdige
  Entscheidungsfläche (Kanäle als Datenmodell- und Versandfrage).

## Changelog

- 2026-08-05: Initial spec (v1.0) — auf Basis von
  `docs/context/feat-1461-s3b2-kanal-schwelle.md`, Zuschnitt S3b-2a (Trips zuerst),
  PO-Entscheidungen 2026-08-05 (Startwert „gering" je Kanal, MIN_SMS_LEVEL geht sofort auf,
  Alarm-Versand bleibt unverändert während der Bericht mehr zeigt, Ortsvergleich folgt als
  S3b-2b).
- 2026-08-05: Implementiert (v1.1) — Adversary-Runden 1–3, Befunde F001–F004 behoben,
  Verdict VERIFIED. `## Source` um die tatsächlich mitgeänderten Dateien ergänzt
  (`trip_report.py`, `frontend/src/lib/types.ts`, `AlarmeScheduleTab.svelte`,
  `docs/adr/README.md`, den bestehenden Attribut-Struktur-Test). ADR-Referenz auf die
  tatsächlich vergebene Nummer 0045 aktualisiert.
