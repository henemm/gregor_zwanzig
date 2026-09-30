---
entity_id: bug_2454_kurzform_gefuehlte_temperatur
type: bugfix
created: 2026-09-28
updated: 2026-09-28
status: draft
version: "1.0"
workflow: "bug-2454-kurzform-gefuehlte-temperatur"
tags: [editor, kurzform, sms, premium-sms, telegram, wind-chill, migration, codes]
---

# Bug 2454 — Kurzform zeigt die gewählte gefühlte Temperatur nie an

## Approval

- [ ] Approved

## Purpose

Wählt ein Nutzer im Editor „Gefühlte Temperatur" (`wind_chill`) für einen Kurzform-Kanal
(SMS, Premium-SMS, Telegram-Kurzform) und speichert, bleibt die Kurzform-Antwort ohne
FD/FL/FN — die Wahl wirkt ins Leere. Ursache ist ein Einfrier-Mechanismus im geteilten
Trip/Ortsvergleich-Editor: fehlt beim Speichern ein expliziter Eintrag für die
abgeleiteten Untergrößen (`wind_chill_day_low/_day_high/_night`,
`temperature_day_low/_day_high/_night`), schreibt der Editor sie unbemerkt als
`enabled:false` fest und blockiert damit dauerhaft die eigentlich vorgesehene
Elter→Kind-Ableitung des Loaders (`_DERIVED_METRIC_RULES`). Diese Spec schließt die
Lücke im Editor (Laden UND Umschalten des Elters), bereinigt bereits eingefrorene
Bestandsdaten per Einmal-Migration und schärft als Nebenbefund die CODES/KUERZEL-Antwort
auf den richtigen Kontext (Trip vs. Ortsvergleich).

## Source

- **File:** `frontend/src/lib/components/shared/WeatherMetricsTab.svelte`
- **Identifier:** `initFromTrip()`, `onToggleMetric()`

## Estimated Scope

- **LoC:** ~380–480 (Editor-Produktionscode ~100–130, Migrationsskript ~140–170,
  CODES-Fix ~15–25, Rest Testcode) — liegt über dem 250-LoC-Workflow-Limit,
  `loc_limit_override` ist nötig.
- **Files:** 6 Produktionsdateien (4 Frontend inkl. Test-Nachbau-Kette, 1
  Python-Service, 1 neues Migrationsskript) + 1 Doku-Datei (zählt nicht gegen das
  LoC-Limit) + ~7–9 Testdateien (neu/erweitert).
- **Effort:** medium-high — mehrere zusammenhängende, aber technisch getrennte
  Teilkorrekturen (Editor-Ableitung, Editor-Live-Mitnahme, Migration, CODES-Kontext).

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/trip-detail/metricsEditor.ts` | MODIFY | Neue Funktion `deriveMissingChildMetrics()` (Regeltabelle gespiegelt aus `src/app/loader.py::_DERIVED_METRIC_RULES`) für fehlende Kind-Einträge; neue Funktion `moveWithDerivedChildren()` für die Live-Mitnahme beim Elter-Umschalten (AC-2). |
| `frontend/src/lib/components/shared/weather-metrics-tab/channelMetricLayouts.ts` | MODIFY | `channelOverrideFromMetrics()` wendet `deriveMissingChildMetrics()` auf die gelesene `channel_layouts.<kanal>`-Liste an (Elter-Referenz aus DERSELBEN Kanal-Liste, nicht der globalen — mirrort `per_channel_layouts[ch] = _append_derived_metrics(ch_parsed)`), bevor die Buckets für den Kanal-Reiter gebaut werden. |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | `initFromTrip()` ruft `deriveMissingChildMetrics()` auf `savedMetrics` VOR dem Bucket-Aufbau (Zeile ~457 ff.); `onToggleMetric()` (global, Zeile ~807) und `onRestoreMetric()`/`onRemove()` (Kanal-Override, Zeile ~848 ff.) rufen für `temperature`/`wind_chill` `moveWithDerivedChildren()` statt `move()` auf; die bestehende Global-Abwahl-Durchschreibung in den Kanal-Overrides (Zeile ~821–833) nimmt bei `temperature`/`wind_chill` dieselben Kinder mit in `off`. |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/_editor_kette.ts` | MODIFY | Geteilter Test-Nachbau von `initFromTrip()`/Speicherpfad — `ladeInEditorState()` und die Verschiebungs-Helfer der Kette müssen dieselbe Ableitung/Mitnahme abbilden wie das echte Bauteil, sonst prüfen die darauf aufbauenden Tests eine veraltete Nachbildung statt der echten Verdrahtung. |
| `src/services/trip_command_processor.py` | MODIFY | `codes_text()` bekommt Parameter `vergleich: bool = False`; im Trip-Kontext wird `TF` sowohl aus der geordneten Wetter-Gruppe (`_CODES_WETTER`) als auch aus dem Nachtrags-Fallback (`bed`-Dict) entfernt. `_show_codes()` bekommt Parameter `kind: str = "route"`; Aufrufstelle Zeile ~1060 (Trip-Pfad) bleibt beim Default, Aufrufstelle Zeile ~1223 (`_dispatch_compare`) übergibt `"vergleich"`. |
| `scripts/migrate_2454_derived_children.py` | CREATE | Einmalige Bereinigung eingefrorener Kind-Einträge in bestehenden Trip-Dateien (`kind != "vergleich"`) — global (`display_config.metrics`), je `channel_layouts.<kanal>`, je `channel_layouts_per_report.<report>.<kanal>`. Vorbild `scripts/migrate_1373_compare_active_metrics_format.py` (Glob `*/briefings/*.json`, Dry-Run-Default, `--execute`, tar.gz-Backup, Read-Modify-Write). |
| `docs/reference/operations_playbook.md` | MODIFY (Doku, zählt nicht gegen LoC-Limit) | Neuer Abschnitt „Eingefrorene Kurzform-Kind-Metriken bereinigen (#2454)" nach dem Muster der Abschnitte zu #1244/#1373, inkl. Rollout-Reihenfolge (Editor-Deploy vor Migration). |
| `tests/tdd/test_kuerzel_eindeutig.py` | MODIFY | `KUERZEL_WORTLAUT_DE` (Zeile 81–98) und `test_codes_deutsch_auf_langform_kanaelen` verlieren „TF" im Trip-Kontext; ein neuer Testfall belegt, dass die Ortsvergleich-Antwort „TF" unverändert behält. `test_codes_tokenizer_selbsttest_am_spec_wortlaut`/`test_codes_vollstaendig_gegen_ausgabe_register`/`test_bedeutung_kommt_nur_aus_dem_katalog` sind GEPRÜFT UND bleiben unverändert grün (siehe Implementation Details Abschnitt 4 für die Begründung: `TF` steht nicht in der zur Laufzeit gerechneten Soll-Menge dieser Tests). |
| `tests/tdd/test_kurzform_befehle_englisch.py` | MODIFY | `CODES_WORTLAUT` (Zeile 97–111) verliert „TF feels like" im Trip-Kontext, analog. |
| Neue Fixture (Frontend) | CREATE | Golden-Trip-JSON mit dem eingefrorenen Muster für den `_editor_kette.ts`-Roundtrip-Test (AC-3), abgelegt neben bestehenden `fixtures/`-Dateien derselben Test-Kette. |
| Tests (neu, Frontend `node --test` + pytest, Kern-Schicht) | CREATE | Bug-Reproduktion Editor→Loader→Kurzform, Live-Mitnahme-Test, Migrations-Tests (Muster/Guard/Idempotenz/Zwei-Nutzer), CODES-Kontext-Tests. |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/loader.py::_DERIVED_METRIC_RULES`/`_append_derived_metrics` (Zeile 861–903, 997–1000, 1032–1035) | Referenzregel | Einzige Quelle der Elter→Kind-Zuordnung — Editor UND Migrationsskript spiegeln/importieren diese Regel, keine zweite Tabelle. Die Kanal-Ebene leitet dort explizit aus der EIGENEN Liste ab (`per_channel_layouts[ch] = _append_derived_metrics(ch_parsed)`), nicht aus der globalen — der Editor muss dasselbe tun. |
| `docs/specs/modules/feat_1728_s2_editor.md` DEC-6 (Zeile 165–184) | Bestehende Entscheidung | Kinder sind eigenständig abwählbare Zeilen — diese Spec darf das NICHT aufheben; AC-2/AC-4 sind bewusst als Default-Mitnahme, nicht als Zwangskopplung entworfen. |
| `docs/reference/gates_und_ratschen.md` (ADR-0050 Regel 1–4) | Bestehende Entscheidung | Eine Kanal-Ebene darf die globale Auswahl nur ABWÄHLEN, nie über sie hinaus einwählen — FD/FL erscheinen im Kanal deshalb nur, wenn Elter UND Kind auch GLOBAL aktiv sind. AC-3 prüft deshalb explizit den Fall „global UND Kanal aktiv", nicht „nur Kanal aktiv". |
| `tests/tdd/test_temp_tagesrichtung_aufloesung.py` (Zeile 156–166) | Bestehender Regressionsnachweis | Belegt bereits heute, dass Kurzform-Rendering ein Kind unabhängig vom Elter behandelt (`sms_token_value`) — bleibt durch diese Spec unverändert grün, da `builder.py`/`trip_report.py` nicht angefasst werden. |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/_editor_kette.ts` | Bestehender Test-Nachbau | `ladeInEditorState()` bildet `initFromTrip()` nach — ohne Anpassung würde ein darauf aufbauender Test die alte, noch fehlerhafte Nachbildung prüfen statt der echten Verdrahtung. |
| `scripts/migrate_1373_compare_active_metrics_format.py` | Vorbild | Glob `*/briefings/*.json` (seit ADR-0023/#1250-Cutover die einzige Speicherstruktur, `trips/*.json` und `compare_presets.json` werden nicht mehr geschrieben/gelesen), Dry-Run/`--execute`/Backup/Read-Modify-Write-Gerüst. |
| `docs/reference/operations_playbook.md` (Abschnitte #1244/#1373) | Betriebs-Rezept | Exakter Ausführungsweg (`uv run python3 scripts/... --root data/users`, User `claude-gregor`, Dry-Run vor `--execute`) — wird für #2454 fortgeschrieben, nicht neu erfunden. |
| `src/app/metric_catalog.py::_SMS_SYMBOL_METRIC_IDS`/`SMS_SYMBOL_BY_METRIC` (Zeile 802–843) | Register-Grundlage | Belegt, dass `wind_chill` NICHT in `_SMS_SYMBOL_METRIC_IDS` steht — `TF` ist damit NICHT Teil der zur Laufzeit gerechneten „Soll-Menge" der Tests `test_codes_vollstaendig_gegen_ausgabe_register`/`test_codes_tokenizer_selbsttest_am_spec_wortlaut`, diese Tests bleiben von Decision 4 unberührt. |

## Implementation Details

### 1. Editor: fehlende Kind-Einträge beim Laden ableiten (global + je Kanal)

```
// metricsEditor.ts — Regeltabelle 1:1 aus src/app/loader.py::_DERIVED_METRIC_RULES
const DERIVED_METRIC_RULES: ReadonlyArray<{ child: string; parent: string }> = [
  { child: 'temperature_night',    parent: 'temperature' },
  { child: 'wind_chill_night',     parent: 'wind_chill' },
  { child: 'temperature_day_low',  parent: 'temperature' },
  { child: 'temperature_day_high', parent: 'temperature' },
  { child: 'wind_chill_day_low',   parent: 'wind_chill' },
  { child: 'wind_chill_day_high',  parent: 'wind_chill' },
];

export function deriveMissingChildMetrics(
  metrics: ReadonlyArray<{ metric_id: string; enabled: boolean; bucket?: string; order?: number }>,
): typeof metrics {
  const byId = new Set(metrics.map((m) => m.metric_id));
  const parentById = new Map(metrics.map((m) => [m.metric_id, m]));
  const extra = [];
  for (const { child, parent } of DERIVED_METRIC_RULES) {
    if (byId.has(child)) continue;          // expliziter Eintrag (auch false) bleibt unangetastet
    const p = parentById.get(parent);
    if (!p) continue;                        // kein Elter -> keine Erfindung (Roundtrip-Invarianz)
    extra.push({ metric_id: child, enabled: p.enabled, bucket: p.bucket, order: p.order });
  }
  return [...metrics, ...extra];
}
```

`initFromTrip()` ruft `deriveMissingChildMetrics(trip!.display_config?.metrics ?? [])` auf,
BEVOR daraus `activeIds`/`buckets` berechnet werden (Zeile ~457 ff. — dieselbe Stelle, an
der heute `savedMetrics` roh gelesen wird). `channelOverrideFromMetrics()` bekommt dieselbe
Vorschaltung für `channel_layouts.<kanal>`: die Elter-Referenz ist dabei der Elter-Eintrag
in DERSELBEN Kanal-Liste (`layout`), NICHT die globale Liste — exakt wie der Loader es je
Kanal-Ebene tut (`per_channel_layouts[ch] = _append_derived_metrics(ch_parsed)`, eine
Liste, ein Elter-Lookup innerhalb dieser Liste). Zeigt der Kanal den Elter aus (z. B. `sms`
hat `wind_chill` selbst deaktiviert, obwohl global aktiv), leitet der Kanal seine Kinder
folgerichtig auch als „aus" ab — konsistent mit dem Backend, das sonst eine andere
Kind-Sichtbarkeit rendern würde als der Editor anzeigt. `channel_layouts_per_report` wird
vom Editor heute weder gelesen noch geschrieben (nur `cockpitHelpers568.ts` prüft es auf
Nicht-`null`) — dafür deckt ausschließlich die Migration (Abschnitt 5) Bestandsdateien ab,
kein Editor-Verhalten nötig.

### 2. Zusätzliche Ergänzung über die neun vorgegebenen Punkte hinaus (PFLICHT-Lesehinweis)

**Reine Lade-Ableitung (Abschnitt 1) reicht NICHT aus, um das PO-Szenario „wind_chill
wählen und speichern → FD/FL kommt an" zu erfüllen.** Die Ableitung greift nur für Kinder,
die beim LADEN bereits fehlen — der Elter-Status zu diesem Zeitpunkt ist der VOR dem
Toggle des Nutzers. Schaltet der Nutzer den Elter erst INNERHALB derselben Sitzung ein und
speichert, bleiben die Kinder im bis dahin geladenen (meist „aus"-)Bucket stehen;
`buildWeatherConfigMetrics` schreibt sie beim Speichern weiterhin explizit `enabled:false`
— exakt der ursprüngliche Fehler, nur einen Schritt später. Diese Spec ergänzt deshalb eine
zweite, kleine Regel:

**Live-Mitnahme beim Umschalten des Elters:** Bewegt der Nutzer `temperature` oder
`wind_chill` zwischen „aus" und einem aktiven Bucket (global über `onToggleMetric()`, je
Kanal über `onRestoreMetric()`/`onRemove()`), werden alle seine Kinder (laut
`DERIVED_METRIC_RULES`), die VOR der Verschiebung im SELBEN Bucket standen wie der Elter
(„mitgelaufen", nicht individuell abweichend), in denselben Bucket verschoben — direkt
hinter dem Elter einsortiert (verhindert eine Wiederholung von #1947: FD/FN/FL landen sonst
am Listenende statt an der vom Nutzer gewählten Stelle). Ein Kind, dessen aktueller Bucket
VOR der Verschiebung vom Elter abweicht (der Nutzer hat es bereits individuell
umgezogen), bleibt unangetastet — DEC-6 (eigenständig abwählbare Zeilen) bleibt dadurch
vollständig gewahrt: die Mitnahme ist ein Default beim Umschalten, keine dauerhafte
Zwangskopplung, und jedes Kind bleibt danach frei wieder verschiebbar.

```
// metricsEditor.ts
export function moveWithDerivedChildren(
  b: Buckets, id: string, from: keyof Buckets, to: keyof Buckets,
): Buckets {
  let next = move(b, id, from, to);
  const children = DERIVED_METRIC_RULES.filter((r) => r.parent === id).map((r) => r.child);
  for (const child of children) {
    if (b[from].includes(child)) next = move(next, child, from, to);
  }
  return next;
}
```

`WeatherMetricsTab.svelte::onToggleMetric()` (Zeile ~807) ersetzt den direkten
`move(buckets, id, from, to)`-Aufruf durch `moveWithDerivedChildren(...)`, wenn
`id in ('temperature', 'wind_chill')` — sonst unverändertes `move()`-Verhalten für alle
anderen Metriken. `onRestoreMetric()`/`onRemove()` (Kanal-Override, Zeile ~848 ff.) erhalten
dieselbe bedingte Ersetzung für `view.buckets`. Die bestehende Global-Abwahl-Durchschreibung
in dieselbe Funktion (Zeile ~821–833: eine globale Abwahl von `id` entfernt `id` bereits
heute aus jedem Kanal-Override, der es aktiv führt) muss dieselbe Kind-Mitnahme bekommen —
sonst bleiben Kind-Zeilen in einem Kanal-Override aktiv stehen, während der Elter global
gerade abgewählt wurde: die `for (const ch of ...)`-Schleife nutzt dort ebenfalls
`moveWithDerivedChildren(override.buckets, id, 'primary', 'off')` statt des rohen `move()`.

Diese Ergänzung ist die einzige Stelle in dieser Spec, die über die neun vom Kontext
vorgegebenen Entscheidungspunkte hinausgeht — sie ist bei der Spec-Freigabe durch den PO
ausdrücklich mitzuentscheiden, nicht nur die neun ursprünglichen Punkte.

### 3. Geteilter Editor bleibt für `context="vergleich"` unberührt

`initFromTrip()` ist laut bestehendem Kommentar (Zeile 454–456) ausschließlich über
`load()`/`handleDiscard()` erreichbar — beides route-only. `deriveMissingChildMetrics()`
und `moveWithDerivedChildren()` werden ausschließlich aus route-spezifischem Code
aufgerufen; der `context === 'vergleich'`-Zweig (eigener Katalog,
`compare_metric_catalog.py`) ruft keine dieser Funktionen auf und bleibt strukturell
unverändert.

### 4. CODES/KUERZEL: „TF" nur im Ortsvergleich-Kontext

`codes_text(en: bool, vergleich: bool = False)`: Im Trip-Kontext (`vergleich=False`,
Default) wird `("TF",)` aus der lokalen Kopie von `_CODES_WETTER` entfernt UND der
Schlüssel `"TF"` aus dem zur Laufzeit gebauten `bed`-Dict gelöscht — sonst hängt Zeile
391–392 (`wetter = _CODES_WETTER + tuple((c,) for c in bed if c not in geordnet)`) „TF"
unbeworben wieder ans Ende der Wetter-Gruppe an. `_show_codes(self, kind: str = "route")`
reicht `vergleich=(kind == "vergleich")` an `codes_text()` durch. Aufrufstelle Zeile ~1060
(`process()`, Trip-Pfad, nach `_resolve_vergleich()` bereits ausgeschlossen, dass es sich
um einen aufgelösten Ortsvergleich handelt) bleibt beim Default `kind="route"`; Aufrufstelle
Zeile ~1223 (`_dispatch_compare()`) übergibt `kind="vergleich"`.

**Geprüft, keine Kollision mit #2417:** `wind_chill` steht NICHT in
`_SMS_SYMBOL_METRIC_IDS` (`metric_catalog.py:802–815`) — `SMS_SYMBOL_BY_METRIC` enthält
deshalb keinen `"TF"`-Eintrag, und die zur Laufzeit gerechnete Soll-Menge
`_soll_codes_ac9()` (`test_kuerzel_eindeutig.py:172–177`, AC-9) verlangt „TF" folglich
NICHT von der CODES-Antwort. `test_bedeutung_kommt_nur_aus_dem_katalog` (AC-23) prüft nur,
dass die KATALOG-Bedeutung von „TF" nicht leer ist (bleibt unverändert bestehen), nicht
dass sie in der Trip-CODES-Antwort ERSCHEINT. Beide Tests bleiben unverändert grün. Einzig
`KUERZEL_WORTLAUT_DE`/`CODES_WORTLAUT` (fest verdrahtete goldene Texte, AC-10/AC-8) und der
zugehörige Testfall auf Deutsch/Englisch müssen angepasst werden (Abschnitt „Affected
Files"). `_CODES_WEITERE` und alle übrigen Kürzelgruppen bleiben unverändert — nur „TF" ist
betroffen, weil es das einzige Kürzel ist, das im Trip nie versendet wird (`wind_chill`
selbst hat seit #1887 E6 kein Kurzform-Kürzel mehr).

### 5. Migration eingefrorener Bestandsdaten

`scripts/migrate_2454_derived_children.py` importiert `_DERIVED_METRIC_RULES` aus
`src/app/loader.py` (kein zweites Regelwerk im Skript, analog zu
`migrate_1373_compare_active_metrics_format.py`, das `COMPARE_METRIC_CATALOG`
importiert). Gruppierung nach Elter (`temperature` → 3 Kinder, `wind_chill` → 3 Kinder).
Für jede der drei Fundstellen einer Liste (`display_config.metrics`,
`display_config.channel_layouts.<kanal>`, `display_config.channel_layouts_per_report.<report>.<kanal>`)
prüft das Skript pro Elter das VOLLSTÄNDIGE Muster: Elter-Eintrag mit `enabled:true`
vorhanden, UND ALLE DREI zugehörigen Kinder sind in DERSELBEN Liste explizit vorhanden mit
`enabled:false`, ohne `bucket`-Schlüssel (fehlt oder leer) und `order` fehlend/`0`. Nur bei
vollständigem Treffer werden genau diese Kind-Einträge aus der Liste entfernt — ist auch
nur eines der drei Kinder abweichend (fehlt, hat einen `bucket`, oder `order != 0`), bleibt
die GESAMTE Liste unverändert (kein Teil-Abbau, keine Interpretation einer echten
Einzelabwahl als Fehler). Glob `root.glob("*/briefings/*.json")` (seit ADR-0023/#1250 die
einzige aktive Speicherstruktur für Trips UND Ortsvergleiche; `compare_presets.json` wird
nicht mehr gelesen/geschrieben) — pro Datei wird zuerst `data.get("kind") != "vergleich"`
geprüft, Ortsvergleiche werden komplett übersprungen. Dry-Run als Default, `--execute`
schreibt nach vorherigem tar.gz-Backup (Muster `_make_backup` aus
`migrate_1373_compare_active_metrics_format.py`), Read-Modify-Write (nur die drei
Kind-Einträge je betroffener Liste werden entfernt, alle anderen Felder — auch dem Skript
unbekannte — bleiben erhalten), zweiphasig Plan→Apply, idempotent (zweiter Lauf über
bereits migrierte Daten liefert einen leeren Plan, Exit 0).

### 6. Rollout-Reihenfolge

Erst der Editor-Fix (Abschnitt 1–3) über `deploy-gregor-prod.sh` ausliefern, ERST DANACH
die Migration (Abschnitt 5) gegen den Prod-Datenbestand fahren — in der falschen
Reihenfolge würde ein Speichern im noch alten Editor die gerade bereinigten Kind-Einträge
sofort wieder einfrieren. Ausführung als User `claude-gregor` (Eigentümer von
`/var/lib/gregor`, `docs/reference/operations_playbook.md`-Konvention:
`uv run python3 scripts/migrate_2454_derived_children.py --root data/users`, danach
`--execute`), zuerst Dry-Run lesen. Tritt das eingefrorene Muster nach der Nachmessung
erneut auf (z. B. ein Browser-Tab mit altem, noch ungeladenem Editor-Code speichert
zwischen Deploy und Migrationslauf), ist ein erneuter Migrationslauf gefahrlos — das
Skript ist idempotent (Abschnitt 5) und behebt den Bestand ohne weitere Vorbereitung.
Staging-Datenbestand ist für `hem` nicht lesbar (bekannte Einschränkung) — die Migration
dort läuft ebenfalls als `claude-gregor`/über den Staging-Deploy-Pfad, oder wird explizit
als `NOT_MEASURABLE_ON_STAGING` markiert, wenn dieser Zugang nicht verfügbar ist; das
Kern-Schicht-Testset (AC-1/AC-2/AC-8/AC-9/AC-10) ist davon unabhängig und läuft unter allen
Umständen.

## Expected Behavior

- **Input:** Ein Nutzer aktiviert „Gefühlte Temperatur" (`wind_chill`) im Editor für einen
  Kurzform-Kanal (global oder je Kanal-Reiter, dabei global ebenfalls aktiv gemäß
  ADR-0050) und speichert; ODER eine Bestandsdatei mit dem eingefrorenen Muster (Elter an,
  alle drei Kinder explizit aus) wird migriert.
- **Output:** Die anschließend erzeugte Kurzform (SMS/Premium-SMS/Telegram-Kurzform, sofern
  #2455 dort separat behoben ist) enthält FD/FL (Tageswerte) bzw. FN (Nachtwert im
  Abendbriefing). Die CODES/KUERZEL-Antwort im Trip-Kontext bewirbt „TF" nicht mehr; im
  Ortsvergleich-Kontext bleibt sie unverändert.
- **Side effects:** `deriveMissingChildMetrics()`/`moveWithDerivedChildren()` wirken
  ausschließlich auf `context="route"`. Die Migration verändert ausschließlich die drei
  eingefrorenen Kind-Einträge je betroffener Liste — keine anderen Felder, keine anderen
  Nutzer, keine Ortsvergleiche.

## Acceptance Criteria

- **AC-1:** Given eine globale ODER Kanal-Layout-Liste mit einem Elter (`temperature` oder
  `wind_chill`) `enabled:true` und einem fehlenden Kind-Eintrag / When der Editor die Liste
  lädt / Then erscheint das Kind im selben Bucket wie der Elter DERSELBEN Liste
  (Bucket/Order vom Elter übernommen), UND ein bereits vorhandener expliziter Kind-Eintrag
  (auch `enabled:false`) bleibt dabei unverändert stehen.
  - Test: `metricsEditor.test.ts` (`node --test`), neuer Fall für
    `deriveMissingChildMetrics()` mit drei Teilfällen (fehlendes Kind wird ergänzt;
    vorhandenes `enabled:false`-Kind bleibt exakt erhalten; ein Kanal-Layout mit vom Elter
    abweichendem eigenem Elter-Status leitet aus dem KANAL-eigenen Elter ab, nicht aus dem
    globalen).

- **AC-2:** Given der Nutzer verschiebt `temperature`/`wind_chill` im Editor (global oder
  Kanal-Reiter) von „aus" in einen aktiven Bucket, seine Kinder standen zuvor im selben
  Bucket wie der Elter / When die Verschiebung ausgeführt wird / Then werden genau diese
  Kinder in den neuen Bucket des Elters mitgenommen (direkt hinter dem Elter
  einsortiert); ein Kind, das der Nutzer vorher schon individuell in einen abweichenden
  Bucket verschoben hatte, bleibt unangetastet. Dasselbe gilt spiegelbildlich für die
  bestehende Global-Abwahl-Durchschreibung in Kanal-Overrides.
  - Test: `metricsEditor.test.ts`, neuer Fall für `moveWithDerivedChildren()` mit den drei
    Teilfällen „läuft mit" (Einwahl), „bereits individuell abweichend" und „globale Abwahl
    nimmt mitgelaufene Kinder aus dem Kanal-Override mit".

- **AC-3:** Given ein Nutzer aktiviert „Gefühlte Temperatur" GLOBAL und zusätzlich im
  SMS-Kanal-Reiter (ADR-0050-Präzondition: nur global aktive Metriken dürfen in einem
  Kanal aktiv sein) und speichert / When anschließend der Kurzform-Trip-Report für SMS aus
  dem gespeicherten Ergebnis erzeugt wird / Then enthält er FD und FL (bzw. FN im
  Abendbriefing) — die Auswahl wirkt nicht mehr still ins Leere.
  - Test: zweigeteilt. (a) Node-Test über die vorhandene Kette
    `frontend/.../__tests__/_editor_kette.ts` (`ladeInEditorState()` → Toggle über
    `moveWithDerivedChildren()` → Speicherpfad), der aus einer NEUEN Golden-Fixture (leerer
    Bestand, dann Elter-Einwahl) eine Speicher-Payload erzeugt und gegen eine eingecheckte
    Erwartungsdatei prüft, in der die drei `wind_chill`-Kinder in `channel_layouts.sms` mit
    `enabled:true` stehen. (b) Pytest lädt DIESELBE Erwartungsdatei über
    `src/app/loader.py` und prüft über
    `src/output/tokens/builder.py::build_token_line`, dass FD/FL im Tokenstrom stehen.

- **AC-4:** Given ein Kind wurde durch AC-2 automatisch mitgenommen / When der Nutzer
  dieses eine Kind danach individuell wieder auf „aus" zieht und speichert, OHNE den Elter
  in derselben oder einer späteren Sitzung erneut aus- und wieder einzuschalten / Then
  bleibt es beim nächsten Laden explizit aus — DEC-6 bleibt gewahrt. Schaltet der Nutzer
  den Elter danach erneut komplett aus und wieder ein, greift die Mitnahme-Heuristik aus
  AC-2 erneut (bekannte, in „Known Limitations" dokumentierte Grenze der einfachen
  Zustandsheuristik).
  - Test: `metricsEditor.test.ts`, Zwei-Schritte-Fall (Mitnahme, dann individuelle
    Rück-Abwahl, dann erneutes Laden simuliert, OHNE zwischenzeitlichen Elter-Aus/Ein-
    Zyklus) — belegt, dass `deriveMissingChildMetrics()` den jetzt vorhandenen expliziten
    `false`-Eintrag respektiert.

- **AC-5:** Given der geteilte Editor läuft mit `context="vergleich"` und einer Auswahl,
  die `wind_chill` enthält / When der Vergleichs-Tab lädt oder eine Metrik verschoben wird
  / Then enthält weder die angezeigte Auswahl noch eine simulierte Speicher-Payload einen
  der sechs Kind-Bezeichner (`*_day_low`, `*_day_high`, `*_night`) — der Ortsvergleich
  erfindet keine Einträge und nutzt ausschließlich seinen eigenen Katalog.
  - Test: bestehende Compare-Editor-Tests (`context="vergleich"`-Fixtures) laufen
    unverändert grün; ergänzt um einen VERHALTENS-Test (kein Datei-/Quelltext-Grep), der
    den Compare-Ladepfad mit einer Fixture füttert, die `wind_chill` enthält, und die
    resultierende Auswahl/Payload auf Abwesenheit der sechs Kind-IDs prüft.

- **AC-6:** Given ein Nutzer sendet „kuerzel"/„codes" im Trip-Kontext (kein aufgelöster
  Ortsvergleich) auf einem beliebigen Kanal, deutsch oder englisch / When die
  CODES/KUERZEL-Antwort gebaut wird / Then enthält sie in keiner Sprache das Kürzel „TF" —
  weder in der geordneten Wetter-Gruppe noch im Nachtrag unbekannter Kürzel am Ende des
  Wetter-Blocks.
  - Test: `tests/tdd/test_kuerzel_eindeutig.py` (`KUERZEL_WORTLAUT_DE` ohne „TF",
    `test_codes_deutsch_auf_langform_kanaelen` angepasst) und
    `tests/tdd/test_kurzform_befehle_englisch.py` (`CODES_WORTLAUT` ohne „TF feels like"),
    beide gegen die tatsächlich zugestellte Antwort (Recorder, kein Mock).

- **AC-7:** Given ein Ortsvergleich-Nutzer sendet „kuerzel" im aufgelösten
  Vergleichs-Kontext / When die Antwort gebaut wird / Then bleibt „TF" unverändert
  enthalten wie vor diesem Fix.
  - Test: neuer Testfall in `tests/tdd/test_kuerzel_eindeutig.py`, der `_dispatch_compare()`
    über einen echten Compare-Preset anspricht und „TF" in der Antwort prüft.

- **AC-8:** Given eine Trip-Datei (`kind != "vergleich"`) hat global ODER in einem
  `channel_layouts.<kanal>` ODER in `channel_layouts_per_report.<report>.<kanal>` einen
  Elter mit `enabled:true` und ALLE seine Kinder (laut Regeltabelle) explizit
  `enabled:false` ohne `bucket`, `order` fehlend/`0`, in derselben Liste / When die
  Migration mit `--execute` läuft / Then werden genau diese Kind-Einträge aus der
  jeweiligen Liste entfernt, sonst bleibt die Datei unverändert.
  - Test: neuer Migrationstest mit drei Fixture-Varianten (global, `channel_layouts.sms`,
    `channel_layouts_per_report.morning.sms`), der den Plan UND das Ergebnis nach
    `--execute` prüft.

- **AC-9:** Given dieselbe Trip-Datei, aber nur eines der drei Kinder ist explizit `false`
  (Muster unvollständig, z. B. eine echte Einzelabwahl) / When die Migration läuft / Then
  bleibt diese Liste vollständig unverändert — kein Teil-Abbau.
  - Test: neuer Guard-Test, Fixture mit genau einem abweichenden Kind, Assertion auf
    unveränderte Liste vor/nach Dry-Run UND `--execute`.

- **AC-10:** Given ein Bestand mit migrationsbedürftigen und bereits sauberen Dateien /
  When das Skript zunächst ohne `--execute` läuft / Then wird nichts geschrieben; When es
  danach mit `--execute` läuft / Then entsteht vorher ein tar.gz-Backup, alle dem Skript
  unbekannten Felder bleiben erhalten (Read-Modify-Write), und ein zweiter `--execute`-Lauf
  über denselben Bestand liefert einen leeren Plan (Idempotenz, Exit 0).
  - Test: neuer Testlauf gegen ein temporäres Verzeichnis mit mehreren Fixture-Dateien,
    prüft Dry-Run-Kein-Schreiben, Backup-Existenz, Feld-Erhalt und zweiten leeren Lauf.

- **AC-11:** Given eine strukturgleiche Kopie der Prod-Datei von KHW 403
  (`/var/lib/gregor/users/henning/briefings/5f534011.json`) als eingecheckte Fixture / When
  die Migration darauf mit `--execute` läuft / Then unterscheidet sich der geparste
  JSON-Inhalt vorher/nachher ausschließlich um je drei entfernte `wind_chill`-Kind-Einträge
  pro betroffener Liste (global sowie jede betroffene `channel_layouts.<kanal>`-Liste) —
  jedes andere Feld ist strukturell identisch (verglichen als geparste JSON-Objekte, nicht
  als Byte-Diff). Der Nachweis GEGEN die echte Prod-Datei erfolgt separat als Teil der
  Rollout-Nachmessung (AC-14), nicht als automatisierter Testlauf.
  - Test: struktureller Vorher/Nachher-Vergleich gegen die Fixture.

- **AC-12:** Given Nutzer A trägt das eingefrorene Muster, Nutzer B hat eine echte
  Einzelabwahl (abweichendes Muster) im selben Testlauf / When die Migration mit
  `--execute` läuft / Then wird nur Nutzer A's Datei verändert, Nutzer B's Datei bleibt
  unverändert.
  - Test: Zwei-Nutzer-Fixture unter `<root>/nutzer_a/briefings/`,
    `<root>/nutzer_b/briefings/`, Assertion auf beide Dateien getrennt.

- **AC-13:** Given eine Trip-JSON mit dem eingefrorenen Muster in `channel_layouts.sms`
  (wie KHW 403) / When sie migriert UND anschließend über `src/app/loader.py` geladen UND
  über den Kurzform-Renderer für den SMS-Kanal verarbeitet wird / Then enthält der erzeugte
  Kurzform-Text FD und FL, wo er sie vor der Migration nicht enthielt — und genau dieser
  Text ist auch der Nachrichtentext der **Premium-SMS** (der Kanal, auf dem der PO den
  Fehler beobachtet hat; `src/output/channels/premium_sms.py` sendet `report.sms_text`
  unverändert).
  - Test: End-to-End-Kern-Test (pytest), Fixture → Migration → Loader → Renderer, ohne
    Mocks, Vergleich der Token-Ausgabe vor/nach. Zusätzlich wird aus demselben Report der
    Nachrichtentext über den Premium-SMS-Kanal gebaut (Transport durch einen lokalen
    Aufzeichnungs-Empfänger ersetzt, kein echter Versand) und muss FD und FL enthalten;
    ebenso der Telegram-Nachrichtentext für einen Trip mit `telegram_style=kurzform`.
    Live-Nachweis nach dem Rollout: Premium-SMS-Befehl `Tomorrow` auf KHW 403 über den
    echten Eingang, Eingang auf der zweiten seven.io-Nummer bzw. am PO-Handy.

- **AC-14:** Given Editor-Fix und Migration sind beide bereit / When der Rollout ausgeführt
  wird / Then wird zuerst der Editor-Fix per `deploy-gregor-prod.sh` ausgeliefert und erst
  danach die Migration (als `claude-gregor`, Dry-Run gefolgt von `--execute`) gegen den
  Prod-Datenbestand gefahren, mit anschließender Nachmessung (struktureller Diff der
  ECHTEN KHW-403-Datei + erzeugte Kurzform für KHW 403 enthält FD/FL) vor dem Issue-Close;
  tritt das eingefrorene Muster danach erneut auf, ist ein erneuter (idempotenter)
  Migrationslauf ausreichend.
  - Test: `# doc-compliance-test` auf den neuen Abschnitt in
    `docs/reference/operations_playbook.md` (Reihenfolge-Aussage vorhanden) + manueller
    Nachweis im Rollout-Schritt selbst (kein automatisierter Test möglich, da Prod-Deploy
    betroffen).

## Known Limitations

- **Telegram-Kurzform separat:** Telegram-Kurzform nutzt heute die `sms`-Metrik-Auswahl
  statt eines eigenen Telegram-Layouts (`trip_report.py:345`) — eigener Nebenbefund, wird
  in Issue #2455 behandelt, nicht Teil dieser Spec. **Der Fehler dieses Tickets ist für
  Telegram-Kurzform trotzdem mit behoben:** Weil sie denselben Kurzform-Text (`sms_text`)
  sendet, erscheinen FD/FL dort genauso wie in SMS und Premium-SMS (nachgewiesen in AC-13).
  Offen bleibt nur, dass eine *abweichende* Telegram-Spalten-Auswahl in der Kurzform nicht
  wirkt (#2455).
- **`channel_layouts_per_report` ohne Editor-UI:** Der Editor liest/schreibt dieses Feld
  nicht (nur `cockpitHelpers568.ts` prüft es auf Nicht-`null`) — nur die Migration deckt
  bestehende Dateien mit diesem Legacy-Feld (#434) ab; kein neues Editor-Verhalten dafür.
- **Zielloses „kuerzel" ohne Trip-Treffer:** Ein reiner Ortsvergleich-Nutzer, dessen
  Nachricht keinem Trip- oder Preset-Namen zugeordnet werden kann, bekommt weiterhin die
  Trip-Variante (ohne „TF") — bestehendes Verhalten (auch „hilfe" fällt heute schon so
  zurück), keine Regression durch diese Spec.
- **Verworfene Varianten:** B (Elter erzeugt selbst FD/FL/FN in der Kurzform) und C (Loader
  deutet ein explizites `false` als „ungesetzt" um) wurden verworfen — B erzeugt
  Doppel-Tokens und macht eine echte Kind-Abwahl unmöglich, C kann eine echte Abwahl nicht
  von einem eingefrorenen Default unterscheiden und hat den größeren Blast-Radius
  (globaler Loader statt Editor).
- **Einfache Zustandsheuristik bei AC-2/AC-4:** Die Mitnahme-Entscheidung vergleicht nur
  den Bucket VOR der aktuellen Verschiebung. Schaltet ein Nutzer den Elter nach einer
  individuellen Kind-Abwahl erneut komplett aus und wieder ein, wird das zuvor individuell
  abgewählte Kind bei diesem zweiten Umschalt-Zyklus erneut mitgenommen (die individuelle
  Abwahl „verjährt" nicht dauerhaft, sondern nur bis zum nächsten Elter-Aus/Ein-Zyklus).
  Bewegt ein Nutzer außerdem ein Kind manuell in exakt den Bucket, den es ohnehin durch den
  Elter hätte (zufällig identisch), erkennt der Vergleich diese individuelle Aktion nicht
  als „bereits abweichend". Beides sind Randfälle ohne Datenverlust — das Kind bleibt
  jederzeit erneut frei verschiebbar.
- **Kein automatischer Nachtrag für Trips zwischen Deploy und Migration:** Ein Trip, der
  nach dem Editor-Fix, aber vor dem Migrationslauf gespeichert wird, bleibt bis zum
  nächsten Editor-Save oder bis zur Migration im alten (ggf. eingefrorenen) Zustand.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Korrektur einer Implementierungslücke gegen eine bereits dokumentierte
  Entscheidung (`feat_1728_s2_editor.md` DEC-6/DEC-6b) — keine neue Entscheidungsfläche
  (Kanäle, Provider, Datenmodell, Auth). Die in Abschnitt „Implementation Details" Punkt 2
  ergänzte Live-Mitnahme-Regel ist eine UX-Default-Ergänzung innerhalb des bestehenden
  Editors, kein neuer Architektur-Entscheidungspunkt — sie erfordert dennoch die
  ausdrückliche PO-Freigabe bei der Spec-Approval, da sie über die ursprünglich
  vorgegebenen neun Punkte hinausgeht (siehe Hinweis dort).

## Changelog

- 2026-09-28: Initial spec created (Issue #2454)
