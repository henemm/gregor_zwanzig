---
entity_id: fix_1544_1545_trip_alarm_zeilen_ableitung
type: module
created: 2026-08-07
updated: 2026-08-07
status: draft
version: "1.0"
tags: [alarme, trip-editor, alarm-zeilen, register]
---

# Trip-Alarme: Zeilen aus Auswahl × Register statt aus persistierten Schlüsseln

## Approval

- [ ] Approved

## Purpose

Der Reiter *Alarme* im Trip-Editor zeigt heute nur Zeilen für Größen, die bereits einen
Eintrag in `display_config.metric_alert_levels` haben. Das Backend schaltet aber jede im
Reiter *Wetter-Metriken* aktivierte, alarmfähige Größe scharf — auch ohne einen solchen
Eintrag. Diese Spec bringt beide Mengen zur Deckung: der Trip-Reiter leitet seine Zeilen
künftig aus **Auswahl × Alarmfähigkeit-aus-dem-zentralen-Register** ab, genau wie es der
Ortsvergleichs-Reiter seit #1435 E1a-2 bereits tut. Was der Nutzer sieht, ist danach, was
tatsächlich wirkt.

## Source

- **File:** `frontend/src/lib/components/trip-detail/AlarmeScheduleTab.svelte`
- **Identifier:** `activeMetrics` (Zeile 39, `Object.keys(metricLevels)`)

> **PFLICHT — Schicht-Hinweis:** betroffen ist ausschließlich die Frontend-Schicht
> (`frontend/src/lib/...`, SvelteKit). Kein Go-, kein Python-Code wird geändert — das
> Backend liefert die nötigen Register-Felder bereits (`api/routers/config.py:89,98-105`),
> nur der Frontend-Typ nimmt sie noch nicht auf (`frontend/src/lib/types.ts:159-194`).

## Estimated Scope

- **LoC:** ~60–90 (Limit 250)
- **Files:** ~4 (Typ-Erweiterung, neue Ableitungsfunktion + Test, Umverdrahtung
  `AlarmeScheduleTab.svelte`, Weiterreichen des Katalogs in `TripTabs.svelte`)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/shared/alarme-tab/activeAlertMetricsFromCatalog.ts` | Vorbild (kein Aufrufer) | Zeigt das Ableitungsmuster für den Vergleichs-Pfad — Kern wird NICHT wiederverwendet, siehe „Warum keine Vereinheitlichung mit Compare" |
| `frontend/src/lib/components/alerts-tab/alertMetricTable.ts` (`ALERTABLE_METRICS`) | Bestehende Konstante | Liefert die stabile Anzeige-Reihenfolge; unverändert weiterverwendet |
| `api/routers/config.py::get_metrics()` | Bestehender Endpoint | Liefert `aggregations[].alert_metric` und `change_alert_metric` bereits — keine Backend-Änderung nötig |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` (`metricsCatalog`) | Bestehender State | Bereits geladen (Zeile ~199), wird zusätzlich an `AlarmeScheduleTab` durchgereicht |

## Implementation Details

### 1. Register-Felder im Frontend-Typ sichtbar machen

`MetricEntry` in `frontend/src/lib/types.ts` additiv erweitern:

```
aggregations?: { id: string; label: string; alert_metric?: string | null }[];
change_alert_metric?: string | null;
```

Beide Felder liefert `GET /api/metrics` bereits (`api/routers/config.py:89` bzw.
`:98-105`); nur der Frontend-Typ nahm sie bisher nicht auf. Rein additiv, kein
Breaking Change für bestehende Aufrufer.

### 2. Geteilte Ableitungsfunktion (Trip-eigene Kennungen, kein Compare-Namensraum)

Neue Funktion unter `frontend/src/lib/components/shared/alarme-tab/` (Teilungs-Invariante:
Ableitungslogik gehört dorthin, nicht nach `trip-detail/**`), z. B.
`alertIdentitiesForMetricEntry(entry: MetricEntry): AlertMetric[]`:

- liest `aggregations[].alert_metric` **und** `change_alert_metric` vom übergebenen
  Katalog-Eintrag
- dedupliziert (eine Größe wie Temperatur trägt real drei Identitäten:
  `temperature_min`, `temperature_max`, `temperature_change` — belegt an echten
  Trip-Daten, siehe Kontext-Dokument)
- eine zweite Funktion (analog zu `deriveActiveAlertMetricsFromCatalog`) wendet das auf
  die **aktivierten** Katalog-Einträge eines Trips an und ordnet das Ergebnis über
  `ALERTABLE_METRICS` in stabile Anzeige-Reihenfolge — dieselbe Reihenfolge-Quelle wie
  der Vergleichs-Pfad, damit Zeilen nicht bei jedem Speichern springen

### 3. Falle 3 — Altbestands-Sonderfall (leere/fehlende Wetter-Metriken-Auswahl)

`is_alert_metric_active()` (`src/services/weather_change_detection.py:186-191`) behandelt
ein komplett leeres `display_config.metrics[]` als „jede alarmfähige Größe ist aktiv"
(konservativ, kein stiller Alarmverlust für Alt-Trips). Die neue Frontend-Ableitung MUSS
denselben Sonderfall abbilden: ist `trip.display_config.metrics` leer oder nicht gesetzt,
gelten **alle** alarmfähigen Register-Einträge als aktiv — nicht keine. Sonst zeigt die
Oberfläche für genau diese Trips wieder null Zeilen, während das Backend alles scharf hat
(Rückfall in Fehlerklasse 1).

### 4. Falle 4 — getrennte Quellen für Zeilen-Sichtbarkeit und Speicher-Payload

`AlarmeScheduleTab.svelte` übergibt an `AlarmeTab` (`context="route"`) zwei Props, die aus
**unterschiedlichen, unabhängig berechneten** Werten stammen dürfen:

- `activeMetrics` — die NEUE, gefilterte Ableitung aus Auswahl × Register (bestimmt, welche
  Zeilen sichtbar sind)
- `metricLevels` — bleibt der **ungefilterte** gespeicherte `metric_alert_levels`-Dict wie
  bisher (`trip.display_config?.metric_alert_levels ?? {}`, unverändert)

Grund: `buildAlarmeDeliveryPayload` (`alarmeDeliveryPayload.ts:117-121`) sendet
`metric_alert_levels` beim Speichern als **vollständigen Ersatz**, der Go-Merge ist flach
(`internal/handler/config_merge.go:11-22`). Würde `metricLevels` mitgefiltert, verlöre eine
deaktivierte Größe beim nächsten Speichern ihre zuvor gesetzte Stufe unwiderruflich (echter
Datenverlust, nicht nur Anzeige). Die gefilterte Ableitung darf daher **nur** in
`activeMetrics` einfließen, nie in `metricLevels`.

### 5. Umverdrahtung

- `AlarmeScheduleTab.svelte`: `activeMetrics` wird aus der neuen Ableitungsfunktion
  berechnet (Katalog + `trip.display_config`), statt aus `Object.keys(metricLevels)`.
  `metricLevels` bleibt unverändert (Punkt 4).
- `TripTabs.svelte`: das dort bereits geladene `metricsCatalog` (Zeile ~199/232) wird
  zusätzlich an `<AlarmeScheduleTab>` durchgereicht — **kein neuer Abruf**.
- `AlarmeTab.svelte` selbst wird **nicht** angefasst: der `route`-Zweig liest weiterhin nur
  `activeMetrics`/`metricLevels` als Props, unverändert zum bisherigen Vertrag (hält den
  AC-7-Struktur-Test grün, siehe „Known Limitations").

### Warum keine Vereinheitlichung mit dem Compare-Pfad (Falle 2)

`deriveActiveAlertMetricsFromCatalog()` arbeitet auf **Compare-Auswahlschlüsseln**
(`CompareSelectionEntry`), der Trip-Pfad auf **nackten Metrik-Kennungen** aus
`display_config.metrics[]`. Eine erzwungene gemeinsame Signatur würde denselben Fehler
reproduzieren, der schon den Compare-Katalog ungeeignet macht: `GET /api/compare/metrics`
führt Temperatur nur als `max`/`min` — `temperature_change` und `precipitation_change`
sind über keinen Compare-Auswahlschlüssel erreichbar (belegt an allen 26
Compare-Einträgen), Trips können aber beides. Die Ableitung läuft deshalb bewusst auf
Ebene der **Metrik-Kennung** gegen `MetricEntry` (Trip-Katalog), mit einem gemeinsamen
Kern (`alertIdentitiesForMetricEntry`), aber zwei getrennten Aufrufern für die
unterschiedlichen Auswahl-Räume.

## Expected Behavior

- **Input:** ein Trip mit `display_config.metrics[]` (aktivierte Wetter-Metriken) und
  optional `display_config.metric_alert_levels` (gesetzte Empfindlichkeitsstufen); der
  vollständige Metrik-Katalog aus `GET /api/metrics`.
- **Output:** der Reiter *Alarme* zeigt genau eine Zeile je alarmfähiger Alarm-Identität,
  die zu einer aktivierten Wetter-Metrik gehört — in stabiler, aus `ALERTABLE_METRICS`
  abgeleiteter Reihenfolge. Jede Zeile zeigt die zuletzt gespeicherte Stufe (Default
  `standard`, wenn nie gesetzt).
- **Side effects:** keine neuen Netzwerk-Abrufe (Katalog ist bereits geladen); Speichern
  schreibt weiterhin den vollständigen, ungefilterten `metric_alert_levels`-Dict.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit aktivierter alarmfähiger Wetter-Metrik ohne jeden
  Eintrag in `metric_alert_levels` (Fehlerklasse 1 — unsichtbare Scharfschaltung) /
  When der Nutzer den Reiter *Alarme* öffnet / Then zeigt der Reiter eine Zeile für
  diese Größe mit der Stufe „standard", nicht leer.
  - Test: an einem Trip mit realistisch nachgebildeter Datenlage (aktivierte Größe,
    kein Alert-Level-Eintrag) prüfen, dass die Zeile im gerenderten/berechneten
    Zeilensatz erscheint — kein Dateiinhalt-Check.

- **AC-2:** Given ein Trip, dessen `display_config.metric_alert_levels` einen
  `humidity`-Eintrag trägt (Fehlerklasse 2 — Geisterzeile) / When der Nutzer den Reiter
  *Alarme* öffnet / Then erscheint keine Zeile „Luftfeuchtigkeit".
  - Test: Trip mit `metric_alert_levels: {humidity: 'standard', ...}` gegen den echten
    Metrik-Katalog auswerten; die berechnete Zeilenliste darf `humidity` nicht enthalten.

- **AC-3:** Given ein Trip mit einer Größe, die im Reiter *Alarme* auf eine echte Stufe
  gesetzt ist, deren zugehörige Wetter-Metrik aber im Reiter *Wetter-Metriken* NICHT
  aktiviert ist (Fehlerklasse 3 — vorgetäuschte Kontrolle) / When der Nutzer den Reiter
  *Alarme* öffnet / Then erscheint für diese Größe keine Zeile.
  - Test: Trip mit gesetzter Stufe für eine deaktivierte Größe; die berechnete
    Zeilenliste darf diese Größe nicht enthalten.

- **AC-4 (Normalfall zu AC-3):** Given dieselbe Größe wird anschließend im Reiter
  *Wetter-Metriken* aktiviert und gespeichert / When der Nutzer danach den Reiter
  *Alarme* öffnet / Then erscheint die Zeile wieder — mit der zuvor gesetzten Stufe,
  nicht mit „standard" oder „aus".
  - Test: nach simuliertem Aktivieren prüfen, dass sowohl die Zeile erscheint als auch
    die vorher gespeicherte (nicht zurückgesetzte) Stufe angezeigt wird.

- **AC-5 (Altbestands-Sonderfall, Falle 3 aus dem Kontext-Dokument):** Given ein Trip,
  dessen `display_config.metrics` leer oder nicht gesetzt ist (Wetter-Metriken-Reiter
  nie angefasst) / When der Nutzer den Reiter *Alarme* öffnet / Then zeigt der Reiter
  Zeilen für **alle** alarmfähigen Größen aus dem Register, nicht null.
  - Test: Trip mit `display_config.metrics: []` bzw. `metrics: undefined` gegen den
    vollständigen Katalog auswerten; die Zeilenanzahl muss der Anzahl alarmfähiger
    Register-Einträge entsprechen, nicht 0.

- **AC-6 (Kein Datenverlust, Falle 4 aus dem Kontext-Dokument):** Given eine Größe mit
  gesetzter Empfindlichkeitsstufe wird im Reiter *Wetter-Metriken* deaktiviert und der
  Trip gespeichert / When die Größe später wieder aktiviert wird / Then zeigt ihre
  Zeile wieder die vor der Deaktivierung gesetzte Stufe — nicht „standard" und nicht
  „aus".
  - Test: Speicher-Payload nach dem Deaktivieren prüfen — der zur deaktivierten Größe
    gehörende Schlüssel bleibt im gesendeten `metric_alert_levels`-Dict erhalten, wird
    nicht entfernt, obwohl seine Zeile nicht mehr angezeigt wird.

- **AC-7 (Mehrfach-Identität):** Given ein Trip mit aktivierter Temperatur-Metrik /
  When der Nutzer den Reiter *Alarme* öffnet / Then erscheinen alle drei zugehörigen
  Alarmzeilen (Minimum, Maximum, Änderungsrate) gleichzeitig, nicht nur eine.
  - Test: an einer Metrik mit bekannt mehreren Alarm-Identitäten (Temperatur:
    `temperature_min`, `temperature_max`, `temperature_change`) prüfen, dass alle drei
    in der berechneten Zeilenliste stehen.

- **AC-8 (Stabile Reihenfolge):** Given ein Trip mit mehreren aktivierten alarmfähigen
  Größen / When der Reiter *Alarme* mehrfach hintereinander geöffnet wird — auch nach
  einem Speichervorgang, der die Auswahl nicht ändert / Then steht die Zeilenreihenfolge
  jedes Mal identisch.
  - Test: Zeilenliste zweimal aus identischem Trip-Zustand berechnen und auf exakt
    gleiche Reihenfolge (nicht nur gleiche Menge) prüfen.

- **AC-9 (Deckungsgleichheit — die eigentliche Zusicherung dieser Scheibe):** Given ein
  beliebiger Trip mit einer Wetter-Metriken-Auswahl / When der Reiter *Alarme* seine
  Zeilen berechnet / Then ist die Menge der angezeigten Alarm-Identitäten exakt
  identisch mit der Menge der Identitäten, die der Live-Alarm-Detektor für denselben
  Trip tatsächlich auswertet (weder mehr noch weniger).
  - Test: für mindestens einen Trip-Zustand die per Ableitung berechnete Zeilenmenge und
    die vom echten Backend-Regel-Erzeuger (`expand_per_metric_levels()` /
    `deviation_alert_engine`) tatsächlich erzeugten Regel-Metriken gegenüberstellen und
    auf Mengengleichheit prüfen — kein indirekter Näherungsvergleich.

- **AC-10 (Bestandsschutz):** Given ein Trip mit bereits sinnvoll gesetzten
  Empfindlichkeitsstufen für seine aktivierten Größen / When die neue Ableitung
  ausgeliefert wird, ohne dass der Nutzer etwas ändert / Then bleiben alle zuvor
  gesetzten Stufen unverändert erhalten — nichts wird automatisch umgeschrieben oder
  auf einen anderen Wert zurückgesetzt.
  - Test: Trip-Zustand vor und nach Anwenden der neuen Ableitung vergleichen — die
    gespeicherten Stufenwerte je Größe sind identisch, nur die Zeilen-**Sichtbarkeit**
    ändert sich.

## Nicht in dieser Scheibe

- **Keine Kennzeichnung „gilt derzeit, nicht von dir gesetzt" an den Zeilen.** Für keine
  der drei Fehlerklassen nötig — sie blähte den Umfang, ohne eine der drei Zusicherungen
  zusätzlich zu erfüllen.
- **Keine Migration der `humidity`-Schlüssel.** Betrifft 2 von 14 Trips, der Schlüssel
  wirkt schon heute nicht (ADR-0010) und wird nach dieser Scheibe nicht mehr angezeigt.
  Ein Aufräumen der Persistenz wäre kosmetisch und brächte Datenrisiko ohne Nutzen.
- **Keine Änderung am Backend-Backfill** (`src/services/alert_preset.py:309-348`). Er
  bleibt exakt wie er ist — diese Scheibe macht seine Wirkung sichtbar, ändert sie
  nicht.
- **Kein neuer Onboarding-Schritt oder Wizard.** ADR-0032 (progressive Tab-Editoren,
  kein Wizard) bleibt bindend; die Lösung bleibt vollständig im bestehenden Reiter.
- **Keine zweite persistierte Steuergröße neben der Empfindlichkeitsstufe.** ADR-0043
  legt die Empfindlichkeitsstufe als einzigen Alarm-Regler fest; diese Scheibe führt
  keinen zusätzlichen Schalter (z. B. ein separates „aktiv"-Flag) ein.

## Bindende Entscheidungen

| Quelle | Bindender Inhalt | Wie diese Spec ihn einhält |
|---|---|---|
| **ADR-0010** (Vorboten-Metriken kein Alert-Auslöser) | Luftfeuchtigkeit ist Vorboten-Größe, kein Alarm-Auslöser; Enum bleibt für Altdaten. | Die neue Ableitung liest die Alarmfähigkeit aus dem Register — `humidity` deklariert dort keine Alarm-Identität, erscheint also strukturell nicht mehr (AC-2). Keine Löschung der Altdaten. |
| **ADR-0032** (Wizard-Abschaffung) | Progressive Tab-Editoren, kein Wizard. | Die Lösung bleibt im bestehenden Reiter *Alarme*; kein neuer Schritt, kein Wizard (siehe „Nicht in dieser Scheibe"). |
| **ADR-0043** (Empfindlichkeitsstufe als einziger Alarm-Regler) | Keine zweite Steuergröße neben der Stufe einführen. | Die Ableitung steuert nur, **welche** Zeile sichtbar ist — nicht **wie** sie gesteuert wird. Die Empfindlichkeitsstufe bleibt der einzige Regler je Zeile. |
| **#946 AC-4** | „…einen Onboarding-Zustand … und keinen stillen Standard-Preset." | Der stille Standard existiert weiterhin im Backend-Backfill (unverändert, s. o.); diese Scheibe macht ihn sichtbar und stellt einen Bedienweg her — sie schafft ihn nicht neu. |
| **#1258 S3 D4** | Hatte die Ableitung aus persistierten Schlüsseln für den Trip-Pfad festgeschrieben. | Wird hier bewusst abgelöst — genau diese Festlegung ist die Fehlerursache, die diese Scheibe behebt. |
| **#1435 E1a-2 AC-3** | Stellte nur den Vergleichs-Zweig um, AC-3 ausdrücklich „Trip-Zweig bleibt unangetastet". | War die dort bewusst gesetzte Grenze für E1a-2 — diese Scheibe ist die angekündigte Folge-Arbeit, die den Trip-Zweig jetzt nachzieht. |
| **Teilungs-Invariante (Trip/Compare-Code-Teilung)** | Ableitungslogik gehört nach `shared/alarme-tab/`. | Die neue Ableitungsfunktion liegt unter `frontend/src/lib/components/shared/alarme-tab/`; `AlarmeScheduleTab.svelte` (bestehende Datei unter `trip-detail/**`) wird nur umverdrahtet, keine neue Datei dort angelegt — löst die Pendant-Sperre nicht aus. |

## Test-Plan

Kern-Schicht (deterministisch, kein Netz, echte aufgezeichnete Katalog-/Trip-Daten als
Fixtures), Namensregel: nach Verhalten benennen, nicht nach Issue-Nummer.

| Testdatei (Vorschlag) | Deckt ab | Was geprüft wird |
|---|---|---|
| `frontend/src/lib/components/shared/alarme-tab/__tests__/alert_identities_from_metric_entry.test.ts` | AC-1, AC-2, AC-7 | reine Funktionstests der neuen Ableitung gegen nachgebildete `MetricEntry`-Katalogeinträge (inkl. Temperatur mit drei Identitäten, Luftfeuchtigkeit ohne Identität) |
| `frontend/src/lib/components/shared/alarme-tab/__tests__/trip_active_alert_metrics_derivation.test.ts` | AC-3, AC-4, AC-5, AC-8 | Ableitung Auswahl × Register gegen nachgebildete `display_config`-Zustände: aktiviert/deaktiviert, leeres `metrics[]` (Altbestands-Sonderfall), zweifacher Aufruf auf identischem Zustand (Reihenfolge) |
| `frontend/src/lib/components/shared/alarme-tab/__tests__/alarme_delivery_payload_preserves_inactive_levels.test.ts` | AC-6 | `buildAlarmeDeliveryPayload`/vergleichbare Payload-Erzeugung: deaktivierte Größe bleibt im gesendeten `metric_alert_levels`-Dict erhalten |
| `tests/unit/services/test_deviation_alert_engine_matches_frontend_derivation.py` (Python, Kern-Schicht) | AC-9 | Nachbildung eines Trip-Zustands, Regeln über den echten Produktivpfad (`load_trip_from_dict()` → `deviation_alert_engine` → `expand_per_metric_levels()`) erzeugen, die erzeugten Metrik-Identitäten gegen dieselbe Ableitungslogik (als portierte/gespiegelte Erwartung) auf Mengengleichheit prüfen — **kein** Mock des Regel-Erzeugers |
| `frontend/src/lib/components/shared/__tests__/alarme_tab_catalog_prop_structure.test.ts` (bestehend) | Regressionsschutz | läuft unverändert mit — bewacht, dass `AlarmeTab.svelte` im `route`-Zweig weiterhin nur `activeMetrics`/`metricLevels` liest (kein `catalog`-Prop im Trip-Pfad) |
| Bestandsschutz zu AC-10 | AC-10 | Snapshot-Vergleich gesetzter Stufen vor/nach Anwenden der neuen Ableitung an einem Fixture-Trip mit bereits konfigurierten Alarmen |

**Mutations-Gegenprobe (Pflicht im Adversary):** u. a. den Altbestands-Sonderfall
(Falle 3) gezielt entfernen (leeres `metrics[]` liefert dann `[]` statt „alle") und
prüfen, ob AC-5 das fängt; die Trennung `activeMetrics`/`metricLevels` gezielt
aufheben (beide aus derselben gefilterten Quelle) und prüfen, ob AC-6 das fängt.

## Known Limitations

- Die `humidity`-Altdaten in `metric_alert_levels` (2 von 14 Trips) bleiben in der
  Persistenz liegen — unsichtbar, aber nicht entfernt. Siehe „Nicht in dieser Scheibe".
- `alarme_tab_catalog_prop_structure.test.ts` (AC-7 aus #1258) bleibt unverändert
  bestehen und wurde geprüft: er bewacht die Grenze zwischen `AlarmeTab.svelte` und
  seinen Einbettungen, nicht die Datenquelle innerhalb von `AlarmeScheduleTab.svelte` —
  kein Testumbau nötig, aber im Adversary trotzdem aktiv mitlaufen lassen statt
  anzunehmen.
- Der Nutzer sieht nach dieser Scheibe erstmals Alarmzeilen, die er nie selbst gesetzt
  hat (die 6–9 Regeln je Trip aus Fehlerklasse 1 laufen bereits scharf). Das ist
  beabsichtigt (Sichtbarmachung, keine Neuerung), bedeutet aber: der Nutzer kann diese
  Regeln jetzt erstmals auf „aus" stellen, was den tatsächlichen Alarmversand
  gegenüber heute verringern kann.
- Kein Backend-Change: `GET /api/metrics` liefert die benötigten Felder bereits;
  Fehlläufe der Ableitung sind ausschließlich im Frontend zu suchen.
- **Bewusste Grenze der Namenslisten-Sperre** (Adversary Runde 3, ausdrücklich *nicht* als
  Finding gemeldet): Die Tests schließen die Bypass-Klasse „Kennungen aufzählen statt
  Register lesen" auf zwei Ebenen — im generischen Kern (`alertIdentitiesForMetricEntry`)
  und beim Aufrufer (`deriveActiveAlertMetricsForTrip`). Beide Wächter verlangen für
  **dieselbe** Katalog-Kennung gegensätzliche Ergebnisse (einmal mit, einmal ohne
  Alarm-Identitäten); das kann keine ID-Tabelle auflösen, unabhängig von ihrer Länge.
  Eine Ebene darüber — der Container ruft die Ableitung noch auf, überschreibt ihr
  Ergebnis aber nachträglich per Handtabelle — bleibt ungefangen. Das ist die
  prinzipielle Grenze des Musters: jede Aufrufebene ließe sich erneut umgehen, eine
  vollständige Absicherung wäre eine unendliche Kette. **Nicht als Lücke nachtragen.**
  Der direkte Fork ohne Aufruf ist dagegen abgedeckt (Ebene-2-AST-Wächter aus F001).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — ADR-0010, ADR-0032, ADR-0043 bleiben unverändert bindend
  (siehe „Bindende Entscheidungen"); diese Spec führt keine neue Architektur-Entscheidung
  ein, sondern setzt bestehende konsequent um.
- **Rationale:** Die Ableitung Auswahl × Register ist bereits für den Vergleichs-Pfad
  ADR-Level-Praxis (#1435 E1a-2); diese Spec überträgt sie auf den Trip-Pfad, ohne neue
  Grundsatzentscheidung.

## Bezug zu #1435

Diese Scheibe ist die in der Spec zu #1435 Etappe E4 (`AC-3`: „Trip-Zweig bleibt
unangetastet") ausdrücklich angekündigte Folge-Arbeit. E4 hat den Zahlenwert der
Geisterzeile Luftfeuchtigkeit bereits entschärft (zeigt „—" statt einer irreführenden
festen Zahl); diese Spec entfernt die Zeile selbst und behebt zusätzlich die beiden
weiteren, in #1435 nicht behandelten Fehlerklassen (unsichtbare Scharfschaltung,
vorgetäuschte Kontrolle) in einem Zug (PO-Entscheid Zuschnitt A, 2026-08-07).

## Changelog

- 2026-08-07: Initial spec created (Issues #1544, #1545, Zuschnitt A)
