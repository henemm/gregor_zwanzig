---
entity_id: feat_1459_alert_protokoll
type: module
created: 2026-08-02
updated: 2026-08-18
status: draft
version: "1.7"
tags: [alerts, logging, trips, compare, epic-1458]
---

# Alert-Protokoll haelt fest, WORUM es ging (Issue #1459, Epic #1458 Scheibe 1)

## Approval

- [ ] Approved

## Purpose

`alert_log.json` haelt heute nur `trip_id`/`sent_at`/`changes_count`/`severity` fest —
nicht, **welche Wettergroesse** eine Meldung ausgeloest hat, **welcher der drei Gruende**
(Vorhersage-Aenderung / Nowcast / amtliche Warnung) greift, und **welche Kanaele sie
bekamen bzw. nicht bekamen**. Ohne diese Angabe ist weder die PO-Beobachtung „sechs
Wochen keine Gewitter-Warnung" belegbar, noch laesst sich der Erfolg der Folge-Scheiben
(#1460 ff.) von ruhigerem Wetter unterscheiden. Zusaetzlich protokolliert der
Ortsvergleich heute **gar nicht** (B1-Befund, `docs/context/feat-1459-alert-protokoll.md`).

**Harte Nebenbedingung (D4, PO-Entscheidung 2026-08-02):** Die Cockpit-Kachel „Alarme ·
letzte 24 h" und die Archiv-Statistik „Alarme je Tour" duerfen sich fuer Bestandstouren
durch diese Scheibe **um keine einzige Zahl** aendern. #1459 ist ein internes Protokoll,
kein Anzeige-Feature.

**Harte Nebenbedingung (O1, PO-Entscheidung 2026-08-02):** Die protokollierte
Wettergroesse ist die **Register-Kennung** aus `src/app/metric_catalog.py` (Issue #1435:
„keine Liste darf ein eigenes Vokabular erfinden"), nicht ein interner Datenfeldname —
und die Aufloesung ist **reihenfolge-unabhaengig**, nicht „erstes Treffer-Item gewinnt"
(Praezedenzfaelle #1257, #1444 S2a).

## Source

- **File:** `src/services/alert_log.py` (neu)
- **Identifier:** `append_entry()`

Betroffene Schicht — **ausschliesslich Python-Core**, kein Go, kein Frontend:

| Datei | Aenderung | Zweck |
|---|---|---|
| `src/services/alert_log.py` | CREATE | Geteilte Schreibfunktion (D1), Register-Kennung-Aufloesung (O1), Reason-Konstanten (O2), Zwei-Listen-Trennung (D4) |
| `src/app/metric_catalog.py` | MODIFY | EIN neuer Reverse-Lookup `metric_and_aggregation_for_field()` mit reihenfolge-unabhaengiger Vorrangregel — Geschwister von `get_label_for_field()`, keine neue Tabelle (O1) |
| `src/services/trip_alert.py` | MODIFY | 3 bestehende Schreibstellen (`:323`/`:978`/`:1210`) auf `alert_log.append_entry()` umgestellt; `_send_alert()` gibt die volle `NotificationResult` statt nur `bool` zurueck; `_append_alert_log()` entfaellt |
| `src/services/compare_alert.py` | MODIFY | Aufruf von `alert_log.append_entry()` ergaenzt — bisher **kein** Protokoll (B1) |
| `src/services/compare_radar_alert.py` | MODIFY | dito |
| `src/services/compare_official_alert.py` | MODIFY | dito |
| `internal/store/log.go` | **unveraendert** | `encoding/json` ignoriert unbekannte Felder UND unbekannte Top-Level-Keys (D2/D4); keine Go-Aenderung in dieser Scheibe |

## Estimated Scope

- **LoC:** ~485 (+485 / −25). **PO-Freigabe 2026-08-02: Umfang wird in EINEM Arbeitsgang
  gebaut** (alle sechs Aufrufstellen, kein weiteres Aufteilen), die 250-LoC-Workflow-Grenze
  wird dafuer auf **500** angehoben (`workflow.py set-field loc_limit_override 500`).
  Aufschluesselung: `alert_log.py` ~130 (inkl. Zwei-Listen-Trennung D4, Register-Paar-
  Aufloesung O1), `metric_catalog.py` ~25 (Reverse-Lookup + Vorrangregel + Logger-Import),
  `trip_alert.py` ~40 (netto, inkl. Wegfall von `_append_alert_log`), je Compare-Datei
  ~20-25 (bisher **kein** Schreibaufruf vorhanden), Tests (3 Dateien + 1 Ratchet-Test fuer
  die Registry, deterministisch, kein Netz) ~245-295.
- **Files:** 9 (1 neu, 5 geaendert, 3-4 Testdateien neu)
- **Effort:** medium-high

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `app.metric_catalog.metric_and_aggregation_for_field` (neu) | nutzt | Rueckwaerts-Aufloesung `SegmentWeatherSummary`-Feld → Register-Paar, reihenfolge-unabhaengig (O1) |
| `services.corridor_threshold.resolve_corridor_summary_field` | nutzt | Aufloesung des Korridor-Namensraums auf den Summary-Feldnamen (bereits S2a-Baustein, Vorstufe zu O1) |
| `services.weather_change_detection._ALERT_METRIC_TO_SUMMARY_FIELD`/`get_change_detection_map` | nutzt | Bestaetigt: `WeatherChange.metric` ist immer bereits ein Summary-Feldname (gemessen, s. O1) |
| `services.deviation_alert_engine.DeviationAlertEngine._highest_severity` | nutzt | Severity ueber mehrere Orte (Compare-Δ-Buendel) |
| `services.notification_service.NotificationResult` | nutzt | `sent_channels` — bereits vorhandene Kanal-Erfolgs-Liste |
| `app.loader.get_data_dir` | nutzt | Nutzer-gescopter Pfad (#1265, Test-Isolation) |
| `services.trip_alert.TripAlertService` | erweitert | 3 Schreibstellen umgestellt |
| `services.compare_alert.CompareAlertService` | erweitert | Schreibstelle NEU |
| `services.compare_radar_alert.CompareRadarAlertService` | erweitert | Schreibstelle NEU |
| `services.compare_official_alert.CompareOfficialAlertService` | erweitert | Schreibstelle NEU |
| `internal/store/log.go AlertCountByTrip()` / `CockpitStatusHandler` | **darf sich nicht aendern** | liest ausschliesslich den Top-Level-Key `entries` (D4) und zaehlt darin nach `trip_id` (D3) |

## Implementation Details

### D1 — ein Eintrag je Meldung (Tech-Lead-Vorgabe, uebernommen)

`internal/store/log.go:100 AlertCountByTrip()` zaehlt **Eintraege**, nicht Kanaele. Ein
Eintrag je Kanal wuerde die im Cockpit/Archiv gezeigte Alarm-Zahl unbemerkt
verdrei­fachen. Kanaele werden deshalb als **Listen innerhalb EINES Eintrags** gefuehrt.

### D2 — additiv, vier Altfelder unangetastet (Tech-Lead-Vorgabe, uebernommen)

> ⚠️ **Ueberholt seit Issue #1467 Scheibe S1** (2026-08-03). D2 und D3 galten fuer
> #1459; seither tragen neue Eintraege **eine** Kennung `entity_id` plus das Typfeld
> `entity_type` (`"trip"` | `"compare"`), und `trip_id`/`preset_id` werden nicht mehr
> geschrieben. Bestandsdateien bleiben unveraendert — Go leitet beim Lesen
> `entity_id := trip_id` und `entity_type := "trip"` ab. Massgeblich ist
> `docs/specs/modules/rework_1467_s1_alarm_kennung.md`. Der folgende Abschnitt
> beschreibt den Stand von #1459 und bleibt als Historie stehen.

`trip_id`, `sent_at`, `changes_count`, `severity` bleiben in Name/Typ/Bedeutung exakt
wie heute. `encoding/json` in Go ignoriert unbekannte Felder — keine Go-Aenderung
noetig oder gewuenscht in dieser Scheibe.

### D3 — Tour- und Vergleichs-Eintraege unterscheiden, ohne `AlertCountByTrip()` zu veraendern

**Entscheidung:** Vergleichs-Eintraege (die tatsaechlich versendet wurden, s. D4) lassen
`trip_id` **leer** (`""`) und tragen stattdessen ein neues Feld `preset_id`. Tour-Eintraege
spiegeln das: `preset_id` bleibt leer.

**Begruendung:** `AlertCountByTrip()` bucketet `counts[e.TripID]++` — ein leerer String
landet unter dem Schluessel `""`, den **keine echte Tour** jemals abfragt (Trip-IDs sind
nie leer). Fuer alle bestehenden Touren ist die Zaehlung dadurch **bit-identisch** zu
heute: nur neu hinzukommende Vergleichs-Eintraege erzeugen den neuen `""`-Bucket, kein
bestehender Bucket wird veraendert. Die Alternative — `trip_id` fuer Vergleichs-Eintraege
mit der Preset-ID zu befuellen — wuerde eine zweite, mit echten Trip-IDs kollisions­faehige
Kennung in dasselbe Feld zwingen (heute kollisionsfrei nur per Zufall der ID-Generierung)
und `AlertCountByTrip()` liesse Vergleiche unbemerkt als Tour-Alarme mitzaehlen, sobald
irgendwann doch gezaehlt wird. Ein eigenes Feld ist die einzige Variante, die **strukturell**
garantiert, dass sich an der bestehenden Zaehlung nichts aendert — nicht nur zufaellig,
solange keine ID kollidiert.

**Reichweite dieser Regel:** D3 schuetzt ausschliesslich `AlertCountByTrip()`
(Archiv-Statistik „Alarme je Tour"), NICHT die Cockpit-Kachel — die zaehlt unabhaengig von
`trip_id` ungefiltert **alle** Eintraege der letzten 24h (`internal/handler/cockpit.go:36-42`
`LoadAlertLog()` → 24h-Fenster → `len(alerts)`, kein Trip-Bezug). Ein Vergleichs-Eintrag mit
`trip_id=""` erhoeht die Cockpit-Zahl also weiterhin um 1 — das ist hier **gewollt**: Ein
tatsaechlich versendeter Ortsvergleichs-Alarm ist ein neues, echtes Ereignis, das vorher
(B1) komplett unsichtbar war. Fuer bestehende Touren aendert sich dadurch nichts, weil
Vergleichs-Presets nie zuvor Eintraege erzeugt haben — es gibt keinen „alten" Wert, der sich
verschieben koennte.

### D4 — Nutzer-Anzeigen bleiben unveraendert (Nachbesserung, PO-Entscheidung 2026-08-02)

**Befund, der D3 allein NICHT geloest hat:** Mein urspruenglicher O3-Entwurf schrieb einen
Eintrag mit `trip_id` gesetzt und `channels_sent: []`, sobald ein Versand komplett
fehlschlug ("kein Kanal erreichbar", obwohl der Nutzer welche aktiv hat). Zwei Effekte
waeren dadurch unbeabsichtigt entstanden:

1. `AlertCountByTrip()` haette diesen Fehlschlag als echten Alarm der Tour mitgezaehlt
   (`trip_id` war ja gesetzt) — die Archiv-Zahl „Alarme je Tour" haette sich fuer eine
   bestehende Tour erhoeht, obwohl der Nutzer NICHTS bekommen hat.
2. Die Cockpit-Kachel „Alarme · letzte 24h" zaehlt ungefiltert ALLE Eintraege im
   24h-Fenster (`cockpit.go:36-42`) — auch ein Eintrag mit `trip_id=""` haette diese Zahl
   erhoeht. D3s Trick (leeres `trip_id`) schuetzt **nur** die Pro-Tour-Statistik, nicht die
   Kachel.

Der Δ-Pfad schrieb bisher **ausdruecklich nur nach erfolgreichem Versand**
(`trip_alert.py:319-321`, Kommentar „Alert-Log fuer Cockpit-Kachel"); der Radar-Pfad
schreibt schon heute nach demselben Fail-soft-Muster wie mein Entwurf (`:801`,
Issue #827/F001) — die beiden Pfade sind also bereits heute uneinheitlich. **Diese
Uneinheitlichkeit ist NICHT Gegenstand dieser Scheibe** — der Radar-Pfad behaelt sein
heutiges Zaehlverhalten unveraendert bei (er schreibt weiterhin nur bei Erfolg in
`entries`, s.u.).

**Entscheidung:** `alert_log.json` bekommt einen **zweiten Top-Level-Schluessel**:

```json
{
  "entries": [ ... wie heute, plus neue Felder ... ],
  "not_delivered": [ ... neu, komplett fehlgeschlagene Zustellungen ... ]
}
```

`internal/store/log.go`s `alertLogFile`-Struct kennt ausschliesslich `entries`
(`json:"entries"`) — ein zweiter Top-Level-Key wird von `encoding/json.Unmarshal` exakt so
ignoriert wie ein unbekanntes Feld INNERHALB eines Objekts (dieselbe Garantie, die D2
bereits fuer neue Felder nutzt, nur eine Ebene hoeher). Go sieht `not_delivered` **nie** —
weder die Cockpit-Kachel noch `AlertCountByTrip()` koennen sich dadurch aendern, fuer
KEINE Tour, unabhaengig von `trip_id`.

**Aufteilungsregel in `append_entry()`:**

```
wenn effective_channels leer:
    nichts schreiben                          # Nutzer wollte gar keinen Kanal (unveraendert)
sonst wenn mindestens ein Kanal KONFIGURIERBAR war (NotificationResult.sent):
    Eintrag nach data["entries"]               # exakt das heutige Kriterium
sonst:
    Eintrag nach data["not_delivered"]         # NEU: heute verschwaende die Meldung spurlos
```

#### D4-Nachtrag (v1.4, 2026-08-02) — AC-10 und AC-11 schlossen sich gegenseitig aus

**Befund aus der Implementierung (Developer-Meldung, Tech-Lead-Entscheidung):** Die
v1.3-Fassung dieser Regel stellte auf den **Zustellerfolg** ab („channels_sent nicht
leer"). Das beruhte auf einer falschen Annahme ueber das Ist-Verhalten. Heute entsteht der
`entries`-Eintrag, sobald mindestens ein Kanal eine **funktionierende Konfiguration** hat
(`_send_alert()` → `NotificationResult.sent`); ein technischer Zustellfehler auf einem
konfigurierten Kanal unterdrueckt ihn ausdruecklich NICHT — der Docstring dort sagt es
woertlich: *„Send errors on a configured channel are logged but do NOT suppress recording
(best-effort, Anti-Pattern #656)"*.

Damit waren AC-10 (v1.3) und AC-11 **nicht gleichzeitig erfuellbar**: AC-10 haette einen
Fall aus `entries` herausgenommen, der heute darin landet — die Cockpit-Zahl waere fuer
Bestandstouren **gesunken**, genau der Effekt, den AC-11/D4 verhindern sollen. Belegt
wurde der Widerspruch durch den Bestandstest
`tests/tdd/test_914_slice4_alert_sms_dispatch.py::test_ac3_sms_http_error_logged_email_still_delivers`,
der das heutige Kriterium seit #914 festschreibt.

**Entscheidung: AC-11 gewinnt.** Die Unveraenderlichkeit der Nutzer-Anzeige ist die
PO-Kernforderung; AC-10 war ein Umsetzungsdetail auf falscher Annahme. Massgeblich fuer die
Ziel-Liste ist deshalb das heutige Kriterium „mindestens ein Kanal **konfigurierbar**",
nicht „zugestellt". `not_delivered` faengt danach ausschliesslich die Faelle, die heute
**spurlos** verschwinden (kein Kanal konfigurierbar, obwohl der Nutzer einen wollte).

Der urspruenglich von AC-10 gemeinte Fall geht dabei **nicht** verloren: „konfiguriert,
aber nichts zugestellt" steht als `channels_sent: []` + `channels_not_sent` mit
`delivery_failed` je Kanal **im regulaeren `entries`-Eintrag** (neues AC-15) — inhaltlich
vollstaendig, ohne die Zahl anzufassen.

**Umsetzung:** `append_entry()` bekommt dafuer den Parameter `reachable_channels`
(`NotificationResult.sent_channels` = die betretenen, also konfigurierbaren Kanaele); er
entscheidet die Ziel-Liste. `sent_channels` traegt weiterhin den tatsaechlichen
Zustellerfolg und fuellt `channels_sent`/`channels_not_sent`. Ohne `reachable_channels`
gilt `sent_channels` auch als Erreichbarkeits-Angabe (Direktaufrufer, AC-11/AC-14).

Ein Eintrag in `entries` (egal ob voller Erfolg oder Teil-Erfolg wie AC-9) verhaelt sich
**exakt wie heute** fuer Δ-Pfad und Radar-Pfad: nur bei mindestens einem erfolgreichen
Kanal wird ueberhaupt geschrieben — die Anzahl der `entries` fuer eine bestehende Tour
aendert sich durch diese Scheibe nicht. `not_delivered`-Eintraege duerfen den echten
`trip_id`/`preset_id` tragen (kein D3-Trick noetig — Go liest den Key ohnehin nie), das
gibt der spaeteren Auswertung (#1461) die volle Zuordenbarkeit.

**Ergebnis:** Die Sicherheitsleine aus O3 bleibt vollstaendig erhalten (die
Nicht-Zustellung IST protokolliert, mit Groesse/Grund/Kanal-Aufschluesselung), nur eben in
einer fuer Go unsichtbaren Ablage.

### O1 — Register-Kennung statt Datenfeldname (Nachbesserung, PO-Entscheidung 2026-08-02)

**Korrektur einer eigenen Fehlannahme:** Meine v1.1-Fassung loeste Wettergroessen in
`SegmentWeatherSummary`-**Feldnamen** auf (`gust_max_kmh`, `thunder_level_max`). Das sind
interne Datenfeldnamen der Aggregat-DTO, **nicht** die Register-Kennung aus
`src/app/metric_catalog.py`. Issue #1435 haelt die Kernregel fest: *keine Liste darf ein
eigenes Vokabular erfinden — alles haengt an der EINEN Registry.* Ein Protokoll, das einen
Feldnamen statt der Register-ID schreibt, fuehrt genau das achte Vokabular ein, das #1435
gerade abbaut.

**Zusaetzlicher Befund waehrend der Korrektur:** `WeatherChange.metric` ist entgegen meiner
v1.1-Annahme **niemals** ein `AlertMetric`-Enum-Wert — es ist **immer bereits** ein
`SegmentWeatherSummary`-Feldname. Belegt an allen drei erzeugenden Stellen in
`weather_change_detection.py`:
- Δ-Erkennung (`:576/:613`): `self._thresholds` = `get_change_detection_map()`, ein
  `{summary_field: threshold}`-Dict — die Schleife iteriert Feldnamen, `WeatherChange.metric
  = metric` (= Feldname).
- Absolute Regeln (`:652/:682`): `field_name = _ALERT_METRIC_TO_SUMMARY_FIELD.get(rule.metric)`
  — die `AlertMetric`→Feld-Aufloesung passiert VOR der `WeatherChange`-Konstruktion.
- Schwellwert-Ueberschreitung (`:723`): dieselbe `field_name`-Quelle.

Selbst eine Delta-Regel (`AlertRuleKind.DELTA`, `AlertMetric.WIND_CHANGE` etc.) wird
VOR der `WeatherChange`-Erzeugung ueber `_ALERT_DELTA_METRIC_TO_FIELDS` in einzelne
Feldnamen aufgefaechert (`:505-527`) — je Feld ein eigener `WeatherChange`. Die „3
Delta-`AlertMetric`-Werte ohne Summary-Feld", die ich in v1.1 als Sonderfall behandelt
habe, **kommen in `WeatherChange.metric` gar nicht vor**. Damit entfaellt dieser
Sonderfall vollstaendig — eine einzige Aufloesungsregel deckt jetzt alle Faelle.

**Neue Entscheidung:** Protokolliert wird **das Paar (Register-Kennung, Auswertung)** —
`MetricDefinition.id` + Aggregation (`"min"`/`"max"`/`"avg"`/`"sum"`) — nicht die Kennung
allein. Begruendung (#1435 E1a, wortgleich uebernommen): *„temperature" allein sagt nicht,
ob Hoechst- oder Tiefstwert gemeint ist* — dieselbe Datenmodell-Erkenntnis, die dort zu
`alert_metrics={"max": "wind_gust"}` (Dict, nicht flacher Wert) gefuehrt hat.

**JSON-Form:** `metrics: list[{"metric_id": str, "aggregation": str}]`, z.B.
`[{"metric_id": "gust", "aggregation": "max"}]`. Begruendung: selbstbeschreibend ohne
Parser-Konvention (kein `"gust:max"`-Trennzeichen, das in sechs Monaten neu gelernt werden
muss), und strukturell identisch zum bereits etablierten Muster `alert_metrics={"max":
"wind_gust"}` aus #1435 E1a — dieselbe Formsprache (Groesse + Auswertung als getrennte
Schluessel), nicht noch eine dritte Konvention.

**Fortschreibung #1954 (v1.6):** Je Dict kommen zwei OPTIONALE Felder dazu, `value: float`
und `previous_value: float` — s. „Erweiterung #1954" unten fuer Regeln und Beispiel. Die
zweigliedrige Grundform (`metric_id`+`aggregation`) bleibt fuer alle Bestandsfaelle
unveraendert bestehen.

**Rueckwaerts-Aufloesung — OHNE neue Tabelle moeglich:** `metric_catalog.py` bietet bereits
zwei Reverse-Lookups nach demselben Muster: `get_label_for_field(summary_field) ->
(label_de, aggregation, unit)` (`:813`) und `get_compact_label_for_field(summary_field) ->
(compact_label, unit_short)` (`:791`) — beide iterieren `_METRICS` und vergleichen gegen
`m.summary_fields.values()`. **Keine der beiden liefert `metric_id` selbst.** Diese Spec
ergaenzt einen dritten, strukturell aehnlichen Reverse-Lookup — mit EINEM wichtigen
Unterschied zu den beiden bestehenden Vorbildern (s.u.).

**Nachbesserung — Mehrdeutigkeit darf nicht von der Listenreihenfolge abhaengen:**
`get_label_for_field()`/`get_compact_label_for_field()` verwenden „erstes Treffer-Item in
`_METRICS` gewinnt" — genau dieses Muster hat in diesem Projekt bereits zweimal Alarme
gekostet (#1257, #1444 S2a: `SNOW_LINE` → zwei Katalog-IDs, positionsabhaengig aufgeloest).
Eine Umsortierung der Registry — jederzeit moeglich, sieht harmlos aus — wuerde
`metric_and_aggregation_for_field()` sonst still auf eine andere Kennung umstellen.

**Vollstaendig gemessen (alle 28 in `_METRICS` vorkommenden Summary-Felder gegen alle
Eintraege abgeglichen): genau EINE Mehrdeutigkeit.**

```
temp_min_c  ->  ("temperature", "min")  UND  ("temperature_cold", "min")
```

| | `selectable` | `alert_metrics` | `label_de` |
|---|---|---|---|
| `temperature` | **True** | `{"min": "temperature_min", "max": "temperature_max"}` | „Temperatur" |
| `temperature_cold` | **False** | `{}` (leer) | „Tiefsttemperatur-Alarm" |

`temperature_cold` ist die interne Pseudo-Groesse, die die Alarmwelt fuer die Kaelte-
Richtung fuehrt (Issue #1435: *„die Alarmwelt modelliert Richtungen als Pseudo-Groessen —
dieselbe Krankheit, die #1372 auf der Anzeigeseite geheilt hat"*). Sie ist nicht
nutzersichtbar (`selectable=False`) und traegt keine eigene Alarm-Identitaet.

**Vorrangregel — inhaltlich begruendet, nicht positionsbasiert:** Von mehreren Treffern
gewinnt der Eintrag mit `selectable=True` — er ist die nutzersichtbare, „echte" Groesse;
die nicht-sichtbare Pseudo-Groesse verliert. Bleibt danach immer noch mehr als ein
Kandidat (oder keiner) uebrig, ist das Feld **echt mehrdeutig** und wird **gemeldet statt
still gewaehlt**: die Funktion loggt eine Warnung und liefert `None` — dasselbe
Fail-soft-Verhalten wie bei einem komplett unbekannten Feld (das einzelne Register-Paar
wird im Protokoll-Eintrag ausgelassen, der Alarm-Lauf laeuft weiter). Eine Ausnahme waere
hier die falsche Wahl: Diese Funktion laeuft innerhalb eines Alarm-Laufs — ein
`raise` wuerde eine Sicherheitswarnung (Gewitter, amtliche Warnung) an einer voellig
unabhaengigen Katalog-Inkonsistenz scheitern lassen. Sichtbarkeit entsteht stattdessen
durch den Log-Eintrag (fuer den Betrieb) UND durch einen Ratchet-Test ueber die gesamte
Registry (fuer die Entwicklungszeit, s.u.) — der faengt eine NEUE Mehrdeutigkeit, bevor
sie je in einem Alarm-Lauf `None` produziert.

```python
def metric_and_aggregation_for_field(
    summary_field: str, *, _registry: Optional[list] = None,
) -> Optional[tuple[str, str]]:
    """Rueckwaerts-Aufloesung: SegmentWeatherSummary-Feldname -> (metric_id, aggregation).

    Anders als get_label_for_field()/get_compact_label_for_field() NICHT "erstes
    Treffer-Item gewinnt" -- bei mehreren Treffern entscheidet inhaltlich, welcher
    `selectable=True` ist (die nutzersichtbare Groesse; interne Pseudo-Groessen wie
    "temperature_cold" verlieren). Bleiben danach 0 oder >=2 Kandidaten, ist das Feld
    echt mehrdeutig -- geloggt, NICHT stillschweigend das erste Listen-Item gewaehlt
    (Praezedenzfaelle #1257, #1444 S2a). `_registry`-Parameter ist ein Test-Seam fuer den
    Reihenfolge-Unabhaengigkeits-Nachweis (AC-5) -- Default ist die echte `_METRICS`.
    """
    registry = _registry if _registry is not None else _METRICS
    matches = [
        (m, agg)
        for m in registry
        for agg, field in m.summary_fields.items()
        if field == summary_field
    ]
    if not matches:
        return None
    if len(matches) == 1:
        m, agg = matches[0]
        return (m.id, agg)
    selectable_matches = [(m, agg) for m, agg in matches if m.selectable]
    if len(selectable_matches) == 1:
        m, agg = selectable_matches[0]
        return (m.id, agg)
    logger.warning(
        "metric_and_aggregation_for_field: mehrdeutiges Summary-Feld %r (%d Treffer, "
        "%d davon selectable) -- Register-Paar im Alarm-Protokoll ausgelassen",
        summary_field, len(matches), len(selectable_matches),
    )
    return None
```

Das ist **kein** neues Vokabular — es liest ausschliesslich `_METRICS` (die eine
bestehende Registry) und mirrort im Grundmuster `get_label_for_field()`/
`get_compact_label_for_field()`, mit der einen inhaltlich begruendeten Erweiterung
(Vorrangregel statt Listenposition). `metric_catalog.py` braucht dafuer `import logging`
+ `logger = logging.getLogger(__name__)` (bisher nicht vorhanden — kleine additive
Ergaenzung).

Damit ist die Rueckwaerts-Richtung fuer **alle** Faelle abgedeckt, in denen `alert_log.py`
einen Summary-Feldnamen kennt:

| Ausloeser | Aufloesungspfad zum Register-Paar |
|---|---|
| `WeatherChange` (alle Faelle, s.o.) | `change.metric` ist bereits ein Summary-Feld → `metric_and_aggregation_for_field(change.metric)` |
| `CorridorHit` (Grenzwert, beide Corridor-Namensraeume) | `resolve_corridor_summary_field(hit.metric)` (bestehender S2a-Baustein) → Ergebnis in `metric_and_aggregation_for_field()` |
| Nowcast (Radar) | kein Feldname noetig — `is_convective` bildet direkt auf `("thunder","max")` bzw. `("precipitation","sum")` ab (beide Register-Paare bereits bekannt: `thunder.summary_fields={"max":"thunder_level_max"}`, `precipitation.summary_fields={"sum":"precip_sum_mm"}`) |

**Amtliche Warnungen bleiben bewusst ausserhalb dieses Vokabulars.** `OfficialAlert.hazard`
ist eine Gefahrenart aus einem eigenen, seit #1318 stabilen Katalog
(`output/tokens/hazard_symbols.py:15`, 10 Werte: `thunderstorm`, `flood`, `rain`,
`wind_gust`, `snow`, `black_ice`, `extreme_heat`, `extreme_cold`, `wildfire_risk`,
`access_ban`) — keine Wettergroesse des Registers, eine Uebersetzung waere verlustbehaftet
(`access_ban` z.B. hat keine Entsprechung in `_METRICS`). Damit diese Angabe nicht mit
Register-Kennungen vermischt wird, bekommt sie ein **eigenes JSON-Feld**, nicht denselben
Schluessel mit anderem Item-Typ:

```json
{"metrics": [], "hazards": ["thunderstorm"], "reason": "official_alert"}
```

vs.

```json
{"metrics": [{"metric_id": "gust", "aggregation": "max"}], "hazards": [], "reason": "forecast_change"}
```

Jeder Eintrag traegt **beide** Schluessel, genau einer ist nicht-leer — erkennbar allein an
der Feld-Struktur, ohne `reason` mitlesen zu muessen (auch wenn `reason` dieselbe Aussage
redundant bestaetigt).

**Reine Funktionen in `alert_log.py`** (deterministisch testbar, kein Mock noetig):
`register_pairs_from_changes(changes)`, `register_pairs_from_corridor_hits(hits)`,
`register_pairs_for_nowcast(is_convective)` — liefern `list[tuple[str, str]]`,
dedupliziert und sortiert; `hazards_from_official_alerts(alerts)` liefert `list[str]`,
dedupliziert und sortiert.

### O2 — Katalog der Nicht-Zustellungs-Gruende

**Gemessen, alle vier aus dem Auftrag bestaetigt, plus eine fuenfte:**

| Konstante | Bedeutung | Fundstelle(n) |
|---|---|---|
| `REASON_CHANNEL_DISABLED` | Kanal ist fuer diese Tour/dieses Preset nicht eingeschaltet | `trip_alert.py:1213 _effective_alert_channels()`, `compare_official_alert.py:198 _effective_channels()` |
| `REASON_DELIVERY_FAILED` | Kanal war aktiv, Best-Effort-Versand ist technisch nicht angekommen | `NotificationResult.sent_channels` vs. `effective_channels`-Differenz |
| `REASON_QUIET_HOURS` | Ruhezeiten aktiv | `trip_alert.py:581 _is_quiet_hours`, `deviation_alert_engine.py:243` |
| `REASON_DAILY_LIMIT` | Tages-Obergrenze erreicht | `alert_daily_limit.py:53 is_allowed` |
| `REASON_COOLDOWN` | Zeit-Cooldown/Throttle aktiv | `trip_alert.py:601 _is_throttled_with_cooldown`, `ThrottleStore.is_throttled` |

`reason` ist bewusst ein **freier String**, kein geschlossenes Enum im JSON — der
kuenftige Grund „unter der Kanal-Schwelle" (#1461, `below_channel_threshold`) kann so
additiv ergaenzt werden, ohne das Schema zu migrieren. Die fuenf Konstanten oben leben als
Python-Modulkonstanten in `alert_log.py` (keine Validierung gegen eine geschlossene Liste
beim Schreiben — vorsaetzlich, damit #1461 keine Aenderung an dieser Datei braucht).

**In dieser Scheibe tatsaechlich verwendet:** nur `REASON_CHANNEL_DISABLED` und
`REASON_DELIVERY_FAILED` (s. O3). Die drei uebrigen sind dokumentiert, aber noch von
keinem Aufrufer gesetzt — bewusste Entscheidung, s.u.

### O3 — Wo genau greift die Protokollierung? (zentrale Frage)

> ⚠️ **Fuer die beiden Nowcast-Pfade geschlossen seit Issue #1467 Scheibe S3**
> (2026-08-08). `src/services/alert_gate.py::check_nowcast_gate()` protokolliert
> Ruhezeit/Cooldown/Tageslimit-Unterdrueckungen jetzt fuer Tour-Radar UND
> Vergleichs-Nowcast ueber `alert_log.append_suppressed_entry()`
> (`REASON_QUIET_HOURS`/`REASON_COOLDOWN`/`REASON_DAILY_LIMIT`, Ziel-Liste
> `not_delivered`, D4 bleibt gewahrt). Fuer Vorhersage-Aenderungsalarm und
> amtliche Warnung (die vier uebrigen Zeilen der Tabelle unten) bleibt die
> Luecke **unveraendert offen** — dort ist weiterhin die Vorziehung der
> Auswertung aus Epic #1458 Scheibe 2 die Voraussetzung. Massgeblich:
> `docs/specs/modules/rework_1467_s3_nowcast.md`.

**Befund:** Ruhezeiten/Cooldown/Tageslimit laufen an **fast allen** Aufrufstellen VOR der
eigentlichen Auswertung (Δ-Erkennung/Korridor-Check/Nowcast-Abruf) — zum Zeitpunkt, an dem
das Gate greift, ist noch **gar nicht bekannt**, ob ueberhaupt eine Meldung faellig
gewesen waere:

| Pfad | Ruhezeit | Cooldown | Tageslimit | Auslöser zu dem Zeitpunkt bekannt? |
|---|---|---|---|---|
| Tour Δ+Grenzwert (`check_and_send_alerts`, `:202/:207/:212`) | vor Auswertung | vor Auswertung | vor Auswertung | **nein** |
| Tour Radar (`check_radar_alerts`, `:840/:849/:854`) | vor `get_nowcast()` | vor `get_nowcast()` | vor `get_nowcast()` | **nein** |
| Tour amtlich (`_send_official_alert_only`, `:1188/:1191/:1194`) | nach `check_official_alert_triggers()` (Aufrufer, `:510`) | dito | dito | **ja** |
| Vergleich Δ (`compare_alert.py:112/:118`) | — (kein Ruhezeit-Gate) | vor `_detect_triggered_locations()` | vor Detect | **nein** |
| Vergleich Radar (`compare_radar_alert.py:92/:103`) | nach `_detect_triggered_locations()` | vor Detect | — (kein Tageslimit-Gate) | gemischt |
| Vergleich amtlich (`compare_official_alert.py:107/:125`) | vor `_detect()` | — (kein Cooldown, s. Docstring) | nach `_detect()` | gemischt |

Zeile „Vergleich Radar" beschreibt den Stand vor #1467 S3: seit dieser Scheibe laufen
Ruhezeit/Sperrzeit/Tageslimit dort — wie bei „Tour Radar" — VOR `_detect_triggered_locations()`
ueber den geteilten `alert_gate.check_nowcast_gate()`, und ein Tageslimit-Gate existiert
jetzt ebenfalls. Die uebrigen vier Zeilen (Δ/amtlich, Tour wie Vergleich) sind unveraendert.

**Entscheidung:** In dieser Scheibe wird **nur** die Nicht-Zustellung „Auslöser war
bekannt, aber kein Kanal hat sie erreicht" protokolliert — das ist an **allen sechs**
Aufrufstellen bereits die letzte Zeile vor dem `return`/`continue` und braucht **keine
Umordnung**. Ruhezeit/Cooldown/Tageslimit-Unterdrueckung bleibt in dieser Scheibe
**unprotokolliert** — bewusst, nicht uebersehen:

1. Eine Protokollierung dieser drei Gruende wuerde an der Mehrheit der Pfade eine
   **Vorziehung der Auswertung vor die Gates** erfordern — das ist exakt der Umbau, den
   Scheibe 2 des Epic #1458 („Relevanz-Filter vereinheitlichen", Ziel: Gedaechtnis (c) fuer
   alle drei Ausloeser) ohnehin plant. Hier vorab eine inkonsistente Zwischenloesung zu
   bauen (protokollierbar nur an den drei/sechs Stellen, wo es zufaellig schon passt) hiesse,
   Code zu schreiben, der mit Scheibe 2 wieder umgebaut wird.
2. Die **gefaehrlichste** Wiederholung von #638 — eine Meldung, die auf **allen** Kanaelen
   verschwindet, obwohl der Nutzer sie erwartet — ist beim Gate „kein Kanal erreichbar"
   bereits abgedeckt: Wenn `effective_channels` nicht leer ist (der Nutzer hat also
   mindestens einen Kanal fuer Alarme aktiv) und trotzdem kein Kanal etwas bekommen hat,
   entsteht JETZT ein Eintrag in `data["not_delivered"]` (D4) mit `channels_sent: []`.
   Genau dieser Fall — „aktiv gewollt, aber nichts kam an" — ist der Kern der
   Sicherheitsleine, OHNE die Cockpit-Kachel oder die Pro-Tour-Statistik zu veraendern.
3. **Kein Eintrag**, wenn `effective_channels` leer ist (der Nutzer hat gar keinen Kanal
   fuer Alarme eingeschaltet) — das ist kein Verlust, sondern die bewusste Einstellung des
   Nutzers; ein Eintrag dafuer waere Log-Rauschen ohne Erkenntniswert.

**Konsequenz fuer `append_entry()`:** Die Funktion wird **immer** nach Kenntnis von
`sent_channels` aufgerufen (egal ob leer oder nicht) und entscheidet selbst, ob und in
welche der zwei Listen (D4) geschrieben wird:

```
wenn effective_channels leer:
    nichts schreiben  # niemand wollte es -- kein Rauschen
sonst:
    channels_sent      = zugestellte Kanaele ∩ effective_channels
    channels_not_sent  = fuer jeden Kanal in {email, telegram, sms} \ channels_sent:
                            REASON_DELIVERY_FAILED  wenn er in effective_channels war,
                            sonst REASON_CHANNEL_DISABLED
    wenn mindestens ein Kanal konfigurierbar war (reachable_channels nicht leer):
        Eintrag -> data["entries"]         # Ist-Verhalten, nur reicher (D4)
    sonst:
        Eintrag -> data["not_delivered"]   # NEU, fuer Go unsichtbar (D4)
```

(Ziel-Listen-Kriterium in v1.4 korrigiert — s. D4-Nachtrag. `channels_sent` bleibt
unveraendert der **Zustellerfolg**, nur die Wahl der Ziel-Liste haengt an der
Konfigurierbarkeit.)

Das ersetzt an allen sechs Aufrufstellen den bisherigen Unterschied „Erfolg loggen /
Misserfolg nicht loggen" durch EINEN einheitlichen Aufruf — Fehlerpfade brauchen keinen
Sonderfall mehr, UND die Cockpit-/Archiv-Zahlen bleiben fuer bestehende Touren unberuehrt.

### Funktionssignatur

```
alert_log.append_entry(
    user_id: str, *,
    trip_id: str = "", preset_id: str = "",
    changes_count: int, severity: str,
    metrics: list[tuple[str, str]] = (),      # [(metric_id, aggregation), ...] -- O1
    hazards: list[str] = (),                  # OfficialAlert.hazard-Werte -- O1
    reason: str,                              # forecast_change | nowcast | official_alert
    effective_channels: set[str], sent_channels: list[str],
    reachable_channels: list[str] | None = None,   # v1.4: entscheidet die Ziel-Liste
) -> None
```

**Fortschreibung #1954 (v1.6):** Die Signatur von `append_entry()` selbst bleibt
unveraendert — `metrics` traegt weiterhin `list[tuple[str, str]]`. Den Wert liefern
`register_pairs_from_changes()`/`register_pairs_from_corridor_hits()` NEBEN dem Tupel (s.
„Erweiterung #1954"); `append_entry()` liest ihn separat und serialisiert ihn optional ins
Ziel-Dict. Der Dedupe-/Aufruf-Vertrag der Funktion bleibt unberuehrt.

**Fortschreibung #1944 (v1.7):** `append_entry()` bekommt zwei weitere, additive
Keyword-Parameter ausserhalb des oben gedruckten Signatur-Blocks — `capture_id: str | None`
(bereits seit #1948 S1 vorhanden, hier erstmals dokumentiert) und neu `capture_ids:
Iterable[str] | None`. Beide identifizieren den/die Eingangs-Mitschnitt(e) amtlicher
Warnungen, aus denen der Eintrag entstand — kein Ersatz fuer `metrics`/`hazards`, sondern
ein zusaetzlicher Korrelations-Anker. Details, Mehrdeutigkeits-Regel und die
Ein-versus-Mehrfach-Unterscheidung: „Erweiterung #1944" unten sowie
`docs/specs/modules/feat_1944_warn_mitschnitt_herkunft.md`.

`sent_channels` = tatsaechlich zugestellt (fuellt `channels_sent`/`channels_not_sent`),
`reachable_channels` = konfigurierbar (`NotificationResult.sent_channels`, entscheidet
`entries` vs. `not_delivered`, s. D4-Nachtrag v1.4). Ohne `reachable_channels` gilt
`sent_channels` fuer beides — so rufen die Direktaufrufer in AC-11/AC-14 auf.

Genau eines von `metrics`/`hazards` ist je Aufruf nicht-leer (s. O1) — die Funktion prueft
das nicht selbst (Aufrufer-Vertrag, analog `reason`), serialisiert aber beide Schluessel
immer (leere Liste, wenn nicht zutreffend) fuer ein einheitliches Eintrags-Schema.

### Verdrahtung je Aufrufstelle (alle sechs bereits vorhandene `NotificationResult`/
`effective_channels`-Werte im Scope, kein Zusatz-Fetch noetig)

> ⚠️ **Überholt durch #1461 S3a (2026-08-04):** Die `severity`-Angaben in der rechten Spalte
> beschreiben den Stand von #1459. Seit S3a wird die Dringlichkeit **abgeleitet** statt
> konstant gesetzt — die hier genannten festen Werte `"HIGH"` (Radar) und `"MODERATE"`
> (amtlich) gelten nicht mehr. Maßgeblich ist
> `docs/specs/modules/feat_1461_s3a_alarm_dringlichkeit.md`. Alles Übrige in dieser Tabelle
> (`reason`, `metrics`/`hazards`, `changes_count`, Ziel-Liste) bleibt gültig, ebenso die
> Zusicherung D4.

| Aufrufstelle | `reason` | `metrics`/`hazards` | `changes_count`/`severity` |
|---|---|---|---|
| `trip_alert.py:323` | `forecast_change` | `metrics = register_pairs_from_changes(to_report) + register_pairs_from_corridor_hits(corridor_to_report)`, dedupliziert; `hazards = []` | unveraendert (`len(to_report)+len(corridor_to_report)`, `eval_result.severity`) |
| `trip_alert.py:978` | `nowcast` | `metrics = register_pairs_for_nowcast(result.is_convective)`; `hazards = []` | unveraendert (`1`, `"HIGH"`) |
| `trip_alert.py:1210` | `official_alert` | `metrics = []`; `hazards = hazards_from_official_alerts([a for a, _ in official_notices])` | unveraendert (`len(official_notices)`, `"MODERATE"`) |
| `compare_alert.py` (neu, nach `notif_result`) | `forecast_change` | `metrics = register_pairs_from_changes(alle .changes ueber triggered)`; `hazards = []` | `sum(len(t["changes"]) for t in triggered)`; Severity via `DeviationAlertEngine._highest_severity()` ueber alle Changes gebuendelt (Baustein existiert bereits, `deviation_alert_engine.py:256`) |
| `compare_radar_alert.py` (neu) | `nowcast` | `metrics = register_pairs_for_nowcast(...)` je getriggertem Ort, dedupliziert (kann `("thunder","max")` UND `("precipitation","sum")` gleichzeitig enthalten, wenn Orte gemischt konvektiv/nicht sind); `hazards = []` | `len(triggered)`, `"HIGH"` (Muster Tour-Radar) |
| `compare_official_alert.py` (neu) | `official_alert` | `metrics = []`; `hazards = hazards_from_official_alerts([a for a, _ in tagged_alerts])` | `len(tagged_alerts)`, `"MODERATE"` (Muster Tour-amtlich) |

`_evaluate_one_location()` (`compare_alert.py:170`) muss dafuer `result.severity`
zusaetzlich in das zurueckgegebene Dict aufnehmen (heute nur `changes`) — Ein-Zeilen-Zusatz.

Jede der sechs Aufrufstellen ruft `append_entry()` **einmal** nach dem jeweiligen
Versandversuch auf (egal ob `result.sent` `True` oder `False` ist) — die Funktion selbst
entscheidet ueber Ziel-Liste bzw. Auslassen (s.o.).

### Erweiterung #1954 — der Wert der gemeldeten Groesse

Das Register-Paar (`metric_id`+`aggregation`, O1) haelt fest, **welche** Groesse gemeldet
wurde, aber nicht **welchen Wert** sie hatte — Kennzahl K1 aus Epic #1458 („Anteil der
zugestellten Vorfaelle, die binnen 24h dieselbe fachliche Aussage wiederholen") blieb damit
nur naeherungsweise messbar. #1954 ergaenzt zwei **optionale** Felder je Register-Eintrag:

```json
{"metric_id": "gust", "aggregation": "max", "value": 60.0, "previous_value": 20.0}
```

**E1 — Wertumfang.** `value` ist der neue, ausschlaggebende Wert; `previous_value` der Wert
davor. Erst der alte Wert macht einen Stufenwechsel sichtbar: zweimal „Boeen 60" ist eine
Wiederholung, „20→60" gefolgt von „60→85" sind zwei echte Informationen. Die
Ausloese-Schwelle (`threshold`) kommt bewusst NICHT mit — sie steht in der
Trip-Konfiguration, nicht im Ereignis-Protokoll.

**E2 — beide Felder sind OPTIONAL, nicht immer beide gefuellt.** Ein Eintrag ohne
Wert-Feld bedeutet „kein Wert erhebbar", NIEMALS „Wert 0" — eine K1-Auswertung darf beide
Faelle nie gleichsetzen. Konkret pro Ausloeser:

| Ausloeser | `value` | `previous_value` |
|---|---|---|
| Vorhersage-Aenderung (`WeatherChange`) | `new_value` der schwerwiegendsten Aenderung | `old_value` derselben Aenderung |
| Korridor-Treffer (`CorridorHit`, toter Pfad, E4) | `value` | fehlt (ein `CorridorHit` hat keinen Vorwert) |
| Radar-Nowcast (`register_pairs_for_nowcast()`) | fehlt | fehlt |

Radar-Nowcast bleibt strukturell ohne Messwert: „Gewitter zieht auf" ist dieselbe Aussage,
unabhaengig von der Staerke — ein erfundener Wert waere schlechter als keiner (PO-Entscheid).
Kein Eingriff in `trip_alert.py`/`compare_radar_alert.py` fuer diesen Pfad.

**E3 — Mehrfachtreffer: EIN Eintrag je Groesse, der Extremwert gewinnt, der Wert bleibt
ausserhalb des Dedupe-Schluessels.** Loest dieselbe Groesse in einem Lauf mehrfach aus
(z.B. Boeen auf zwei Etappen), bleibt es bei EINEM Register-Eintrag (unveraendert AC-7).
Protokolliert wird der Wert der `WeatherChange` mit dem groessten `abs(delta)` — bei
gleicher Groesse gilt dieselbe Schwelle, groesstes `abs(delta)` ist damit deckungsgleich mit
der hoechsten `ChangeSeverity`. Bei Gleichstand entscheidet stabile Sortierung nach
`segment_id`, damit das Ergebnis reproduzierbar ist. **Der Wert wird NICHT Teil des
Dedupe-Schluessels** — `_norm_pairs()` dedupliziert weiterhin ausschliesslich ueber
`(metric_id, aggregation)`; sonst zerfiele die Buendelung an Fliesskomma-Rauschen und AC-7
waere gebrochen.

**E4 — der tote Korridor-Pfad wird mitgezogen.** `register_pairs_from_corridor_hits()` hat
heute keinen Produktiv-Aufrufer (nur `alert_log.py:84`, `tests/tdd/test_alert_log_metrics.py`
— Symmetrie zu ADR-0043/#1460 P1a), bekommt aber ebenfalls die Wert-Durchreichung:
`CorridorHit.value` → `value`; `CorridorHit.bound` bleibt draussen (das ist die Schwelle,
s. E1). Ein `CorridorHit` hat keinen Vorwert, `previous_value` entfaellt dort strukturell.

**Betroffene Funktionen:**

- `_norm_pairs()` — nimmt weiterhin `(metric_id, aggregation)`-Tupel fuer die Dedupe-Menge
  entgegen; der Wert wird DANEBEN, nicht IM Tupel gefuehrt (separate Zuordnung
  Register-Paar → Extremwert vor der Deduplizierung).
- `register_pairs_from_changes()` — ermittelt je Register-Paar zusaetzlich `value`/
  `previous_value` aus der `WeatherChange` mit dem groessten `abs(delta)` (E3), stabil
  sortiert nach `segment_id` bei Gleichstand.
- `register_pairs_from_corridor_hits()` — reicht `CorridorHit.value` als `value` durch,
  `previous_value` bleibt fuer diesen Pfad immer unbesetzt (E4).
- Schreibstelle in `append_entry()` (`:226-229`) — serialisiert `value`/`previous_value`
  je Metrik-Dict NUR, wenn vorhanden (kein `null`, kein `0` als Platzhalter).

**Ausdruecklich UNVERAENDERT bleibt:**

- Die Leseseite `read_undelivered()` (`:387ff`, Gruppierung `:444-460`)/`UndeliveredIncident.metrics` bleibt
  zweigliedrig `tuple[tuple[str, str], ...]` — die neuen Wert-Felder erreichen den
  Mail-Renderer NICHT. Damit bleibt die Zusicherung #1503/#1474 („ordinale Groessen nie als
  Zahl anzeigen") unberuehrt, obwohl die Gewitterstufe intern als Rang (`thunder_ordinal()`)
  protokolliert wird — ein spaeterer Umbau haertet sonst den falschen Pfad.
- `append_suppressed_entry()` schreibt weiterhin `"metrics": []` — zum Gate-Zeitpunkt ist
  nichts erkannt, ein erfundener Wert waere schlimmer als keiner.
- Radar-Nowcast (`register_pairs_for_nowcast()`) — bleibt bei `is_convective: bool`, kein
  Wert im Signaturpfad (s.o.).
- Amtliche Warnungen (`hazards_from_official_alerts()`) — tragen weiterhin `hazards`, kein
  `metrics`-Eintrag (O1-Grenze).
- Rein additiv, keine Migration: Alt-Eintraege ohne `value`/`previous_value` bleiben
  unveraendert lesbar (Roundtrip).
- Go liest `metrics` nicht (`internal/store/log.go`) — keine Go-Aenderung noetig.

**Nachzuziehende Fundstelle:** Die Docstring-Aussage in
`src/output/renderers/email/undelivered_hint.py:89-91` („das Protokoll haelt ohnehin nur
das Register-Paar fest, keinen Messwert, Spec v1.1 AC-15") wird durch #1954 falsch — beim
Implementieren zu korrigieren (das Protokoll haelt jetzt optional einen Wert, die
Leseseite gibt ihn nur weiterhin nicht an den Renderer weiter).

### Erweiterung #1944 — Herkunfts-Kennung des Mitschnitts

`metrics`/`hazards`/`value` halten fest, WORUM es ging und mit welchem Wert — nicht, aus
welchem rohen Eingangs-Mitschnitt (`capture_id`, seit #1948 S1,
`alert_input_capture.capture_system()`) die versendete amtliche Warnung stammt. Ohne diese
Angabe war eine Vorfallanalyse wie #1929 (zwei byte-identische Meldungen, keine Zuordnung
moeglich) auf nachtraegliche Zeitfenster-/Namens-Rekonstruktion angewiesen, die #1944 als
strukturell unzuverlaessig verwirft (`OfficialAlert.source` ≠ Mitschnitt-`service`-Schluessel,
s. „Verworfene Alternative" in der dedizierten Spec). Volle Herleitung, Rueckkanal-Mechanik
und AC-1 bis AC-9: `docs/specs/modules/feat_1944_warn_mitschnitt_herkunft.md`. Hier nur der
fuer dieses Schema-Dokument relevante Ausschnitt:

- **Ein Mitschnitt** → `capture_id: str` am Eintrag (additiv, gleiches Muster wie `value`).
- **Mehrere Mitschnitte** in einem Versand (mehrere Quellen im Trip- bzw. mehrere Orte im
  Ortsvergleich-Pfad) → `capture_ids: list[str]` (sortiert, entdoppelt); `capture_id` bleibt
  dann bewusst UNGESETZT statt eine der Kennungen willkuerlich zu waehlen.
- **Keine Kennung beobachtbar** (Mehrdeutigkeit an der `base.py`-Naht, fehlgeschlagener
  Rueckkanal) → weder `capture_id` noch `capture_ids` im Eintrag — Bestandsverhalten, kein
  `null`-Platzhalter.
- Betrifft ausschliesslich `reason="official_alert"`-Eintraege (Trip UND Ortsvergleich,
  Paritaet); `forecast_change`/`nowcast` bleiben unberuehrt. Rein additiv, keine Migration,
  Alt-Eintraege ohne diese Felder bleiben unveraendert lesbar. Kein sichtbares
  Alarm-Format aendert sich (SMS/E-Mail/Telegram bit-identisch).

## Expected Behavior

- **Input:** ein Alarm-Versandversuch (Tour oder Ortsvergleich) mit mindestens einem
  aktiven Kanal, inkl. der zugrundeliegenden Register-Paare/Hazards — unabhaengig davon,
  ob der Versand gelang.
- **Output:** genau ein zusaetzlicher Eintrag in `alert_log.json` des betroffenen Nutzers,
  additiv zu bestehenden Eintraegen, in `entries` (mindestens ein Kanal erfolgreich) oder
  `not_delivered` (kein Kanal erfolgreich, D4).
- **Side effects:** keine — reine Anhaengung (Read-Modify-Write ueber die volle Datei,
  wie im Bestand). Fuer bestehende Touren aendert sich weder die Cockpit-Kachel „Alarme ·
  letzte 24h" noch die Archiv-Statistik „Alarme je Tour" (D4).

## Acceptance Criteria

- **AC-1:** Given eine Tour-Vorhersage-Aenderung am Boeen-Feld (`change.metric =
  "gust_max_kmh"`, dem Register-Paar `("gust","max")` entsprechend) wird erfolgreich
  versendet / When der Eintrag geschrieben wird / Then enthaelt `metrics` genau
  `[{"metric_id": "gust", "aggregation": "max"}]`, `hazards` ist leer, `reason` ist
  `"forecast_change"`.
  - Test: `WeatherChange(metric="gust_max_kmh", ...)` durch `check_and_send_alerts()`
    schleusen, den neuesten Eintrag in `alert_log.json["entries"]` pruefen.

- **AC-2:** Given zwei Korridor-Treffer derselben Wettergroesse — einer mit
  `Corridor.metric` im `AlertMetric`-Namensraum, einer mit `Corridor.metric` im
  Compare-Katalog-`key`-Namensraum — / When beide protokolliert werden / Then tragen
  beide Eintraege **dasselbe** Register-Paar in `metrics` (Nachweis der
  Namensraum-Vereinheitlichung, O1).
  - Test: zwei `CorridorHit`-Objekte mit unterschiedlicher `metric`-Herkunft, aber
    gleicher Zielgroesse (z.B. Gewitter) durch `evaluate_corridor_thresholds()` erzeugen,
    `register_pairs_from_corridor_hits()` auf Gleichheit (`[("thunder","max")]` je Treffer)
    pruefen.

- **AC-3:** Given ein Radar-Alarm mit `is_convective=True` bzw. `is_convective=False` /
  When protokolliert wird / Then enthaelt `metrics` genau `[{"metric_id": "thunder",
  "aggregation": "max"}]` bzw. `[{"metric_id": "precipitation", "aggregation": "sum"}]`,
  `reason` ist `"nowcast"`.
  - Test: `check_radar_alerts()` mit gemocktem `RadarNowcastService` (DI-Seam, kein echtes
    Netz) fuer beide `is_convective`-Werte, je den Log-Eintrag pruefen.

- **AC-4:** Given eine amtliche Warnung mit `hazard="thunderstorm"` loest eine
  Standalone-Meldung aus / When protokolliert wird / Then steht `"thunderstorm"`
  unveraendert in `hazards` (NICHT in `metrics` — eigenes Vokabular, O1), `metrics` ist
  leer, `reason` ist `"official_alert"`.
  - Test: `_send_official_alert_only()` mit einer `OfficialAlert(hazard="thunderstorm", ...)`.

- **AC-5 (reihenfolge-unabhaengige Vorrangregel, O1-Nachbesserung):** Given die
  Registry-Reihenfolge von `temperature` und `temperature_cold` waere gegenueber der
  heutigen Reihenfolge in `_METRICS` vertauscht / When
  `metric_and_aggregation_for_field("temp_min_c")` aufgerufen wird / Then liefert die
  Funktion **unveraendert** `("temperature", "min")` — nicht `("temperature_cold",
  "min")`. Der Nachweis erfolgt ueber den `_registry`-Test-Seam mit einer tatsaechlich
  umsortierten Kopie, nicht durch Abfragen des heutigen Ergebnisses (sonst waere der Test
  ein Waechter, der nie anschlagen kann, vgl. #1435 E3a).
  - Test: `metric_and_aggregation_for_field("temp_min_c", _registry=<Kopie von _METRICS
    mit vertauschter Position von "temperature"/"temperature_cold">)` aufrufen, Ergebnis
    mit dem Aufruf ohne `_registry`-Override (heutige Reihenfolge) vergleichen — beide
    liefern `("temperature", "min")`.

- **AC-6 (Ratchet gegen neue Mehrdeutigkeit, O1-Nachbesserung):** Given die vollstaendige
  Registry `_METRICS` / When jedes Summary-Feld, das in mehr als einem Eintrag vorkommt,
  durch `metric_and_aggregation_for_field()` aufgeloest wird / Then liefert die Funktion
  fuer JEDES dieser Felder ein Ergebnis ungleich `None` (= genau ein `selectable=True`-
  Eigentuemer je Mehrfach-Feld) — ein neuer, unaufloesbarer Konflikt in der Registry faellt
  im Test auf, nicht erst als stille Luecke im Alarm-Protokoll.
  - Test: alle `(field, [owners])`-Gruppen aus `_METRICS` bilden, fuer jede Gruppe mit
    `len(owners) > 1` `metric_and_aggregation_for_field(field) is not None` behaupten.
    Deckt aktuell genau den `temp_min_c`-Fall ab; waechst automatisch mit der Registry.

- **AC-7:** Given ein Lauf, in dem sowohl eine Wetter-Aenderung als auch ein
  Korridor-Treffer gleichzeitig feuern (Muster #1088) / When die Meldung versendet wird /
  Then entsteht **genau ein** Log-Eintrag mit einer `metrics`-Liste, die BEIDE
  Register-Paare enthaelt — nicht zwei Eintraege (Nachweis D1).
  - Test: `check_and_send_alerts()` mit gleichzeitigem `WeatherChange` und `CorridorHit`;
    Eintraege in `alert_log.json["entries"]` vor/nach zaehlen (Delta = 1, nicht 2).

- **AC-8:** Given eine Tour hat nur E-Mail fuer Alarme aktiv (Telegram/SMS aus) und der
  Versand gelingt / When protokolliert wird / Then steht `"email"` in `channels_sent`,
  `"telegram"` und `"sms"` stehen je mit `reason="channel_disabled"` in
  `channels_not_sent`, der Eintrag liegt in `entries`.
  - Test: Trip mit `alert_channels={"email": true, "telegram": false, "sms": false}`,
    Mail-Sink erfolgreich, Log-Eintrag auf beide Listen und Ziel-Array pruefen.

- **AC-9:** Given eine Tour hat E-Mail UND Telegram fuer Alarme aktiv, der E-Mail-Versand
  gelingt, der Telegram-Versand schlaegt best-effort fehl (z.B. API-Fehler) / When
  protokolliert wird / Then steht `"email"` in `channels_sent`, `"telegram"` steht mit
  `reason="delivery_failed"` in `channels_not_sent`, und der Eintrag liegt (weil mindestens
  ein Kanal erfolgreich war) in `entries` — Ist-Verhalten der Eintragszahl bleibt
  unveraendert (D4), nur die Detailtiefe waechst.
  - Test: `NotificationService` mit fehlschlagendem Telegram-Sink, erfolgreichem
    Mail-Sink; Log-Eintrag UND Ziel-Array pruefen.

- **AC-10 (neu gefasst in v1.4, s. D4-Nachtrag):** Given ein Alarm-Versandversuch, bei dem
  **kein Kanal eine funktionierende Konfiguration** hat (`NotificationResult.sent` ist
  False), obwohl `effective_channels` nicht leer ist / When protokolliert wird / Then
  landet GENAU EIN Eintrag in `alert_log.json["not_delivered"]` (NICHT in `entries`) mit
  `channels_sent: []`. Heute entstuende in diesem Fall **gar kein** Eintrag — die Meldung
  verschwaende spurlos.
  - Test: Tour mit `alert_channels={"email": true, ...}`, aber `Settings` ohne
    funktionierende Mail-Konfiguration (`can_send_email() is False`); Telegram global
    konfiguriert, damit der Eingangs-Waechter von `check_and_send_alerts()` nicht schon
    vorher abbricht, auf Trip-Ebene aber abgeschaltet (kein Netz). `entries` unveraendert,
    `not_delivered` um einen Eintrag gewachsen.

- **AC-15 (neu in v1.4):** Given ein Alarm, bei dem mindestens ein Kanal konfiguriert ist,
  aber **kein einziger tatsaechlich zustellt** (beide Transporte scheitern) / When
  protokolliert wird / Then liegt der Eintrag in `entries` — Ist-Verhalten, die Zahl
  bleibt unveraendert — und traegt `channels_sent: []` sowie fuer jeden Kanal einen
  Eintrag in `channels_not_sent` mit `reason="delivery_failed"`. Das ist die
  Sicherheitsleine: „ausgeloest, aber niemand hat es bekommen" ist an der **leeren
  `channels_sent`-Liste** erkennbar, ohne die im Cockpit gezeigte Zahl anzufassen.
  - Test: `NotificationService` mit werfendem `mail_sink` und scheiterndem Telegram-
    Transport; `entries` um einen Eintrag gewachsen, `not_delivered` leer.

- **AC-11 (D4 — Anzeige-Unveraendertheit, PO-Kernforderung):** Given eine Tour hat vor
  dieser Aenderung N erfolgreiche Alarm-Eintraege in `entries` / When zusaetzlich ein
  komplett fehlgeschlagener Versand fuer dieselbe Tour protokolliert wird / Then bleibt
  die Anzahl der `entries`-Eintraege dieser Tour bei N — der fehlgeschlagene Versand
  erscheint ausschliesslich in `not_delivered`. Das entspricht bit-identisch dem, was
  `AlertCountByTrip()` (zaehlt nur `entries`) und die Cockpit-Kachel (zaehlt `entries` im
  24h-Fenster) fuer diese Tour heute und nach der Aenderung liefern.
  - Test: vorab N Eintraege in `entries` fuer `trip_id="X"` schreiben, einen
    `append_entry()`-Aufruf mit `channels_sent=[]`/`effective_channels={"email"}` fuer
    dieselbe `trip_id="X"` ausfuehren, `len(entries fuer trip_id="X")` vorher/nachher
    vergleichen (== N in beiden Faellen).

- **AC-12:** Given ein Ortsvergleich-Preset loest je einmal einen Δ-, einen Radar- und
  einen amtlichen Alarm aus (jeweils mit Erfolg) / When die drei Alarme versendet werden /
  Then entstehen (anders als heute, B1) drei Log-Eintraege in `entries` mit leerem
  `trip_id` und gesetztem `preset_id` — jeweils mit dem zum Ausloeser passenden `reason`.
  - Test: je einen Lauf von `CompareAlertService.check_all_compare_presets()`,
    `CompareRadarAlertService.check_all_compare_presets()`,
    `CompareOfficialAlertService.check_all_compare_presets()` mit einem triggernden Preset;
    `alert_log.json["entries"]` vorher leer, danach 3 Eintraege mit `trip_id=""`.

- **AC-13 (Mandantentrennung):** Given zwei verschiedene Nutzer (`user_id="alice"`,
  `user_id="bob"`) loesen je einen Alarm aus / When beide protokolliert werden / Then
  landet jeder Eintrag ausschliesslich in der `alert_log.json` seines eigenen Nutzers
  (`data/users/alice/alert_log.json` bzw. `.../bob/...`), niemals in der des jeweils
  anderen.
  - Test: `TripAlertService(user_id="alice")` und `TripAlertService(user_id="bob")`
    parallel einen Alarm ausloesen lassen, beide Dateien lesen, Kreuz-Kontamination
    ausschliessen.

- **AC-14 (Bestandsdaten):** Given eine bestehende `alert_log.json` mit einem
  Alt-Eintrag in `entries`, der ausschliesslich die vier heutigen Felder traegt (kein
  `metrics`, kein `hazards`, kein `reason`, keine Kanal-Listen, kein `not_delivered`-Key
  ueberhaupt vorhanden) / When ein neuer Eintrag angehaengt wird / Then bleibt der
  Alt-Eintrag byte-fuer-Feld unveraendert lesbar (Read-Modify-Write, kein Replace) und
  `entries` enthaelt danach genau zwei Eintraege.
  - Test: Datei mit `{"entries": [<Alt-Eintrag>]}` (kein `not_delivered`-Key) vorab
    schreiben, `append_entry()` aufrufen, `json.loads()` auf Alt-Eintrag-Feldgleichheit +
    Eintragszahl pruefen.

- **AC-16 (neu in v1.5, aus Adversary-Finding F001):** Given eine Tour hat **keinen**
  Kanal fuer Alarme eingeschaltet (`effective_channels` ist leer), es liegt aber ein
  ausloesender Befund vor / When der Protokoll-Aufruf erfolgt / Then entsteht **weder** in
  `entries` **noch** in `not_delivered` ein Eintrag — die Protokoll-Datei wird gar nicht
  erst angelegt. Das ist keine Nicht-Zustellungs-Luecke, sondern die ausdrueckliche
  Einstellung des Nutzers (s. Known Limitations); ein Eintrag dafuer waere Log-Rauschen
  ohne Erkenntniswert.
  - Hintergrund: Die Guard-Klausel in `append_entry()` war durch keinen Test abgesichert —
    entfernt man sie, blieben alle uebrigen Tests gruen (Adversary-Mutation F001, HIGH).
    Eine dokumentierte Regel ohne Waechter.
  - Test: echter `TripAlertService`-Lauf mit `alert_channels={"email": false,
    "telegram": false, "sms": false}`; `alert_log.json` darf danach nicht existieren. Der
    Test fuehrt ZUERST dieselbe Ausloese-Lage mit eingeschaltetem Kanal aus und
    behauptet dort einen Eintrag — ohne diese Kontrolle koennte er auch dann gruen
    bleiben, wenn die Lage die Schreibfunktion nie erreicht (Waechter-Falle #1435 E3a).
    Nachgewiesen rot bei entfernter Guard-Klausel, gruen mit ihr.

- **AC-17 (neu in v1.6, #1954 — Wert der Vorhersage-Aenderung):** Given eine
  Tour-Vorhersage-Aenderung am Boeen-Feld mit `old_value=20.0`, `new_value=60.0` / When der
  Eintrag geschrieben wird / Then enthaelt das zugehoerige `metrics`-Dict zusaetzlich
  `"value": 60.0` und `"previous_value": 20.0`.
  - Test: `WeatherChange(metric="gust_max_kmh", old_value=20.0, new_value=60.0, ...)` durch
    `check_and_send_alerts()` schleusen, den neuesten Eintrag pruefen.

- **AC-18 (neu in v1.6, #1954 — Extremwert bei Mehrfachtreffer):** Given zwei
  `WeatherChange`-Objekte fuer dieselbe Groesse in einem Lauf (`abs(delta)` unterschiedlich
  gross) / When protokolliert wird / Then entsteht **EIN** Register-Eintrag fuer diese
  Groesse, dessen `value`/`previous_value` von der `WeatherChange` mit dem groessten
  `abs(delta)` stammen — nicht von der zuerst oder zuletzt uebergebenen.
  - Test: zwei `WeatherChange` mit `metric="gust_max_kmh"`, unterschiedlichem `delta`, durch
    `register_pairs_from_changes()`/`check_and_send_alerts()` schleusen; Eintragszahl bleibt
    1 (AC-7 unveraendert), `value` entspricht dem groesseren `abs(delta)`.

- **AC-19 (neu in v1.6, #1954 — Wert nicht Teil des Dedupe-Schluessels):** Given zwei
  `WeatherChange`-Objekte derselben Groesse mit fast gleichem, aber nicht identischem Wert
  (z.B. `new_value=59.9` und `new_value=60.1`) / When protokolliert wird / Then bleibt es bei
  **EINEM** Register-Eintrag (kein Zerfall in zwei Eintraege durch Fliesskomma-Rauschen).
  Given umgekehrt zwei verschiedene Groessen mit unterschiedlichen Werten / When
  protokolliert wird / Then bleiben es **ZWEI** Eintraege — sie kollabieren nicht.
  - Test: `register_pairs_from_changes()` mit den beiden Szenarien aufrufen, Eintragszahl in
    `metrics` pruefen.

- **AC-20 (neu in v1.6, #1954 — Nowcast bleibt ohne Wert):** Given ein Radar-Alarm mit
  `is_convective=True` / When protokolliert wird / Then enthaelt das zugehoerige
  `metrics`-Dict WEDER den Schluessel `value` NOCH `previous_value` — die Felder fehlen
  vollstaendig, sie sind nicht auf `0`/`null` gesetzt.
  - Test: `check_radar_alerts()` ueber die vorhandene DI-Naht
    `RadarNowcastService(frame_source=...)` mit echten `RadarFrame`-Objekten (KEIN Mock —
    dieselbe Naht nutzt bereits `tests/tdd/test_alert_log_metrics.py`), den Log-Eintrag auf
    Abwesenheit beider Schluessel pruefen (`"value" not in metrics_dict`).

- **AC-21 (neu in v1.6, #1954 — Bestandsdaten ohne Wert bleiben lesbar):** Given eine
  bestehende `alert_log.json` mit einem Alt-Eintrag, dessen `metrics`-Dicts nur
  `metric_id`/`aggregation` tragen (kein `value`, kein `previous_value`, Spec-Stand v1.5)
  / When ein neuer Eintrag angehaengt wird / Then bleibt der Alt-Eintrag byte-fuer-Feld
  unveraendert lesbar (Read-Modify-Write, keine Migration).
  - Test: Datei mit Alt-Eintrag im v1.5-Schema vorab schreiben, `append_entry()` aufrufen,
    `json.loads()` auf Alt-Eintrag-Feldgleichheit pruefen.

- **AC-22 (neu in v1.6, #1954 — Leseseite bleibt zweigliedrig):** Given ein Alt- oder
  Neu-Eintrag mit gesetztem `value`/`previous_value` in `alert_log.json` / When
  `undelivered_incidents()` ihn liest / Then bleibt `UndeliveredIncident.metrics` weiterhin
  `tuple[tuple[str, str], ...]` — die Wert-Felder werden NICHT extrahiert und erreichen den
  Mail-Renderer nicht. Damit bleibt die Zusicherung #1503/#1474 unberuehrt.
  - Test: `read_undelivered()` mit einem Eintrag aufrufen, dessen `metrics`-Dicts `value`
    tragen; `UndeliveredIncident.metrics` bleibt ein reines `(metric_id, aggregation)`-Tupel
    ohne Wert-Anteil.

- **AC-23 (neu in v1.6, #1954 — Unterdrueckte Meldung bleibt ohne Wert):** Given
  `append_suppressed_entry()` wird fuer eine unterdrueckte Nowcast-Meldung aufgerufen / When
  der Eintrag geschrieben wird / Then bleibt `"metrics": []` — unveraendert gegenueber dem
  Bestand vor #1954.
  - Test: `append_suppressed_entry()` aufrufen, `metrics`-Feld des geschriebenen Eintrags auf
    leere Liste pruefen.

- **AC-24 (neu in v1.6, #1954 — toter Korridor-Pfad traegt Wert ohne Vorwert):** Given ein
  `CorridorHit` mit `value=45.0` / When `register_pairs_from_corridor_hits()` protokolliert
  / Then enthaelt das zugehoerige `metrics`-Dict `"value": 45.0`, aber **keinen**
  `previous_value`-Schluessel (ein `CorridorHit` hat keinen Vorwert) und keinen
  `bound`-Wert (das ist die Schwelle, kommt nicht mit).
  - Test: `register_pairs_from_corridor_hits([CorridorHit(..., value=45.0, bound=40.0)])`
    aufrufen, Ergebnis-Dict auf `value` pruefen, Abwesenheit von `previous_value` und
    `bound` pruefen.

## Known Limitations

- **Ruhezeit/Cooldown/Tageslimit bleiben unprotokolliert** (O3) — **fuer den
  Vorhersage-Aenderungsalarm und die amtliche Warnung weiterhin.** Diese beiden Gates
  laufen VOR der Auswertung — der Ausloeser ist zum Zeitpunkt der Unterdrueckung
  strukturell noch nicht bekannt. Eine vollstaendige Abdeckung braucht die Vorziehung der
  Auswertung, die Scheibe 2 des Epic #1458 ohnehin umsetzt. Bis dahin bleibt eine Luecke:
  eine durch Ruhezeit/Cooldown/Tageslimit unterdrueckte, aber tatsaechlich faellige Meldung
  erscheint dort nicht im Protokoll (auch nicht in `not_delivered`). **Fuer die beiden
  Nowcast-Pfade (Tour-Radar, Vergleichs-Nowcast) ist diese Luecke seit Issue #1467
  Scheibe S3 geschlossen** — `alert_gate.check_nowcast_gate()` kennt den Ausloeser bereits
  vor der Datenbeschaffung und protokolliert die Unterdrueckung ueber
  `alert_log.append_suppressed_entry()`, s. O3.
- **Die Warn-Ausgabe bei unaufloesbarer Mehrdeutigkeit ist im Betrieb nur schwach
  sichtbar.** `metric_and_aggregation_for_field()` meldet den Fall per `logger.warning` und
  liefert `None` (fail-soft, bewusst keine Exception — eine echte Gewitter- oder
  Amtswarnung darf nicht an einer Katalog-Inkonsistenz scheitern). Der Python-Kern hat
  jedoch **keine Log-Einstellung**: kein `basicConfig`/`dictConfig`/`FileHandler` im
  gesamten Repo, der Root-Logger bleibt auf `WARNING` ohne Handler. `logger.warning`
  erreicht das journald nur ueber `logging.lastResort` auf stderr — **ohne Zeitstempel,
  ohne Loggernamen, ohne Modul**, also praktisch nicht zuordenbar. Der belastbare Schutz
  ist deshalb die Ratsche AC-6 zur Entwicklungszeit, nicht die Betriebs-Warnung. Wer sich
  spaeter auf diese Warnung verlassen will, muss zuerst die Log-Einstellung des Kerns
  nachziehen.
- **Kein Eintrag bei komplett deaktivierten Alarmen.** Wenn `effective_channels` leer ist
  (Nutzer hat keinen Kanal fuer Alarme eingeschaltet), wird bewusst nichts geschrieben —
  das ist keine Nicht-Zustellungs-Luecke, sondern eine explizite Nutzer-Einstellung.
  Reason-Katalog erweiterbar (`below_channel_threshold` fuer #1461) — reines Reservat,
  keine Implementierung in dieser Scheibe.
- **Go-seitige `AlertCountByTrip()`/Cockpit-Unveraendertheit wird nicht per Go-Test
  nachgewiesen** (D2/D4): Der Nachweis ist strukturell (Go liest ausschliesslich den
  Top-Level-Key `entries`; `not_delivered` existiert fuer Go schlicht nicht), nicht durch
  einen Go-Test in dieser Scheibe — Go-Aenderungen sind explizit ausgeschlossen (D2). Die
  Python-seitige AC-11 belegt die Eintragszahl-Unveraendertheit auf der Ebene, die
  `AlertCountByTrip()`/`CockpitStatusHandler` tatsaechlich lesen (`entries`).
- **`_evaluate_one_location()` gibt bisher keine Severity zurueck** — kleiner additiver
  Zusatz im Rueckgabe-Dict (`compare_alert.py:170`), keine Verhaltensaenderung des
  Δ-Auswertungspfads selbst.
- **`metric_and_aggregation_for_field()` kann `None` liefern** — entweder weil das Feld
  komplett unbekannt ist, oder weil es nach Anwendung der Vorrangregel (`selectable=True`)
  immer noch mehrdeutig ist (0 oder ≥2 Kandidaten). Beide Faelle sind Fail-soft: das
  einzelne Register-Paar wird ausgelassen statt den Alarm-Lauf abzubrechen. Der
  Ratchet-Test (AC-6) haelt fest, dass unter dem heutigen Register **kein** Mehrfach-Feld
  in diesen zweiten Fall faellt — eine kuenftige Registry-Aenderung, die das aendert, macht
  den Ratchet-Test rot, bevor sie je in einem Alarm-Lauf `None` produziert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reines additives Logging-Schema (neue Felder + ein neuer, fuer Go
  unsichtbarer Top-Level-Key; unveraenderte Bedeutung der vier Altfelder und des
  bestehenden `entries`-Arrays) — keine der ADR-Trigger-Entscheidungsflaechen (Kanaele,
  Provider, **Wechsel** der Persistenz-Strategie, Auth, Editor-Paradigma,
  Test-/Deploy-Strategie) wird beruehrt. Die drei strukturellen Entscheidungen (D3: leeres
  `trip_id` + `preset_id`; D4: zweiter Top-Level-Key `not_delivered`; O1: Register-Paar
  statt Datenfeldname mit reihenfolge-unabhaengiger Vorrangregel, EIN neuer Reverse-Lookup
  in der bestehenden Registry) sind in diesem Dokument selbst begruendet und lokal auf
  `alert_log.json`/`metric_catalog.py` begrenzt; sie veraendern kein Verhalten fuer
  Bestandsdaten, Bestandsleser oder die Registry selbst.

## Changelog

- 2026-08-18: **v1.7** — Erweiterung #1944 (Scheibe 2 aus #1929, Folge-Ticket zu #1948 S1):
  `append_entry()` bekommt einen additiven `capture_ids`-Listenparameter fuer den
  Mehrfach-Mitschnitt-Fall (der bereits seit #1948 S1 vorhandene, bis hierhin undokumentierte
  `capture_id`-Parameter wird bei dieser Gelegenheit nachdokumentiert). Betrifft nur
  `reason="official_alert"`, Trip UND Ortsvergleich (Paritaet). Kein sichtbares Alarm-Format
  aendert sich. Eigene, dedizierte Spec fuer Rueckkanal-Mechanik und ACs:
  `docs/specs/modules/feat_1944_warn_mitschnitt_herkunft.md`.
- 2026-08-18: **v1.6** — Erweiterung #1954 (Folgebefund B3 aus #1459, Epic #1458): je
  Register-Eintrag zwei neue OPTIONALE Felder `value`/`previous_value` (PO-Entscheide
  E1-E4). Vorhersage-Aenderung protokolliert neuen+alten Wert; bei Mehrfachtreffer
  derselben Groesse gewinnt der Extremwert (groesstes `abs(delta)`), EIN Eintrag bleibt
  (AC-7 unveraendert), der Wert bleibt ausserhalb des Dedupe-Schluessels; Radar-Nowcast
  bleibt strukturell ohne Wert; der tote Korridor-Pfad wird mitgezogen (`CorridorHit.value`,
  ohne Vorwert). Rein additiv, keine Migration, Leseseite bleibt zweigliedrig
  (`UndeliveredIncident.metrics`), `append_suppressed_entry()` unveraendert. AC-17 bis
  AC-24 neu, jetzt **24 ACs**.
- 2026-08-08: O3-Hinweis praezisiert (Issue #1467 Scheibe S3, Doku-Nachzug) — die
  Nicht-Protokollierung von Ruhezeit/Cooldown/Tageslimit ist fuer die beiden
  Nowcast-Pfade (Tour-Radar, Vergleichs-Nowcast) geschlossen (`alert_gate.py`,
  `alert_log.append_suppressed_entry()`). Fuer Vorhersage-Aenderungsalarm und amtliche
  Warnung bleibt die Luecke unveraendert offen. Kein Code in dieser Spec geaendert,
  Vorbehalt (Epic #1458 Scheibe 2) bleibt bestehen.
- 2026-08-02: Initial spec created (Issue #1459, Epic #1458 Scheibe 1)
- 2026-08-02: D4 ergaenzt (Nachbesserung Team-Lead/PO) — zweiter Top-Level-Key
  `not_delivered` verhindert, dass komplette Nicht-Zustellungen die Cockpit-Kachel oder
  die Archiv-Statistik veraendern; AC-8/AC-9 neu, AC-Nummerierung ab AC-8 verschoben,
  Umfang/LoC-Grenze gemaess PO-Freigabe aktualisiert.
- 2026-08-02: O1 ersetzt (Nachbesserung Team-Lead/PO, Issue #1435) — Register-Kennung
  (`metric_id`+`aggregation`) statt `SegmentWeatherSummary`-Feldname; `hazards` als
  eigenes Feld getrennt von `metrics`; Korrektur einer Fehlannahme (`WeatherChange.metric`
  ist immer bereits ein Summary-Feldname, nie ein `AlertMetric`-Wert); ein neuer
  Reverse-Lookup in `metric_catalog.py` statt einer neuen Tabelle; AC-1 bis AC-4
  entsprechend angepasst.
- 2026-08-02: **v1.5** — AC-16 ergaenzt (aus Adversary-Finding F001, HIGH): die
  Guard-Klausel „kein Eintrag bei komplett abgeschalteten Alarm-Kanaelen" war durch
  keinen Test gedeckt; ihre Entfernung liess alle 24 Tests gruen. Jetzt **16 ACs**.
  Kein Code-Fix noetig — die Regel war korrekt umgesetzt, nur ungeschuetzt.
- 2026-08-02: **v1.4** — D4-Nachtrag (Befund Developer, Entscheidung Tech-Lead): AC-10
  (v1.3) und AC-11 schlossen sich gegenseitig aus, weil die Aufteilungsregel faelschlich
  auf den Zustellerfolg statt auf die Konfigurierbarkeit abstellte. AC-11 gewinnt
  (PO-Kernforderung „Anzeige bleibt unveraendert"); AC-10 neu gefasst auf „kein Kanal
  konfigurierbar", der bisherige AC-10-Fall lebt als neues **AC-15** in `entries` weiter
  (`channels_sent: []` + `delivery_failed` je Kanal). Jetzt **15 ACs**. `append_entry()`
  bekommt dafuer `reachable_channels`.
- 2026-08-02: O1 praezisiert (Nachbesserung Team-Lead/PO) — reihenfolge-unabhaengige
  Vorrangregel (`selectable=True` gewinnt) statt „erstes Treffer-Item"; gemessene
  Mehrdeutigkeit `temp_min_c` dokumentiert; AC-5 (Reihenfolge-Unabhaengigkeits-Nachweis
  ueber Test-Seam) und AC-6 (Ratchet ueber die volle Registry) neu, AC-Nummerierung ab
  AC-5 verschoben (jetzt 14 ACs); Umfang auf ~485 LoC aktualisiert.
