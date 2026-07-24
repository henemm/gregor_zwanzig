# Context: fix-1359-compare-reihenfolge

Issue: [#1359](https://github.com/henemm/gregor_zwanzig/issues/1359) · Label `bug`, `area:compare` · Triage `[triage:a]`
Track: Full Process · erstellt 2026-07-24

## Request Summary

Im Ortsvergleich kann der Nutzer weder die Reihenfolge der **Metriken** festlegen (es gibt nur An/Aus-Häkchen; die Mail-Reihenfolge entsteht als Nebenwirkung der Klick-Historie), noch wirkt sich die per Drag&Drop eingestellte Reihenfolge der **Orte** auf die Mail aus (die Mail sortiert hart alphabetisch, obwohl der Orte-Tab wörtlich zusagt: „Reihenfolge = Spalten im Briefing · ziehen zum Sortieren").

Zwei getrennte Befunde in einem Issue. Beide betreffen dieselbe Nutzererwartung: *was ich im Editor einstelle, steht so in der Mail.*

## PO-Vorgaben für diesen Workflow

| Vorgabe | Quelle | Konsequenz |
|---|---|---|
| **Nichts neu erfinden — Vorhandenes wiederverwenden. Ausdrücklich nicht nur für Bedienelemente, sondern durchgehend** (PO-Präzisierung) | PO 2026-07-24, diese Sitzung | Oberfläche: `WeatherV2Reihenfolge` / `SortableList` / `DragHandle` / `WeatherV2MailPreview` freischalten, nicht nachbauen. Backend: den **einen** bestehenden Sortier-Helfer umstellen statt neue Sortierpfade danebenzustellen; bestehende Persistenz (`active_metrics`, `location_ids` als geordnete Listen) nutzen statt neuer Felder; bestehenden RMW-Speicherpfad (`buildHubPutPayload`) nutzen |
| Trip/Compare teilen sich Code; Compare-Eigenbau bei existierendem Trip-Pendant = Verstoß | CLAUDE.md, Epic #1230 | Der `reihenfolge`-Abschnitt existiert bereits geteilt — nur `context`-Sperre lösen |
| Die Mail folgt der konfigurierten Orts-Reihenfolge | Issue-Text: „Erstes ist die PO-Erwartung" | Alphabetische Zwangssortierung fällt — dokumentierte Gegen-Entscheidung muss sauber abgelöst werden |

**Prüffrage für Adversary/Review (jede geänderte Stelle):** Gab es dafür schon einen Baustein, einen Helfer, ein Feld oder einen Speicherpfad? Wenn ja und er wurde nicht benutzt: Verstoß, Ausnahme nur mit Begründung in der Spec.

Konkret abgeleitet: `sort_locations_alphabetically` ist bereits der einzige Sortier-Helfer für alle vier Aufrufstellen (Docstring: „keine Doppel-Implementierung"). Er wird **umgestellt**, nicht ergänzt — die Ein-Helfer-Struktur bleibt erhalten.

## Teil A — Metrik-Reihenfolge (Ortsvergleich)

### Der Baustein existiert schon und ist geteilt

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte:22-30,43,49-101` | Der fertige Reihenfolge-Baustein: `SortableList` + `DragHandle` + Positionsnummern (`{i + 1}`), `data-testid="wm2-reihenfolge"` |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:853-884` | Bindet ihn ein, aber hart `<LayoutTab context="route">` und gespeist aus `buckets.primary` (Trip-Datenmodell) |
| `frontend/src/lib/components/shared/layout-tab/LayoutTab.svelte:20,51` | Kennt beide Kontexte bereits (`hasLabelColumn={context === 'vergleich'}`) |

### Drei Sperren hintereinander

1. **UI gesperrt** — `weather-metrics-tab/weatherMetricsTabSections.ts:19,23`: `ROUTE_ONLY_SECTIONS = ['reihenfolge', …]`, nur bei `context === 'route'`. Im Vergleich ist `sections.includes('reihenfolge')` immer `false`.
2. **Reihenfolge entsteht zufällig** — `WeatherMetricsTab.svelte:682-687` `toggleCompareMetric` baut über ein `Set` neu auf: abwählen + wieder anhaken schiebt die Metrik ans Ende.
3. **⚠️ Versteckter Blocker: reine Umsortierung wird gar nicht gespeichert** — `weatherMetricsCompareSave.ts:54-58`. Der Diff-Guard normalisiert vor dem Vergleich mit `[...s.activeMetricKeys].sort()`. Gleiche Menge in anderer Reihenfolge ⇒ `norm(current) === norm(baseline)` ⇒ `return null` ⇒ **kein PUT**. Auch mit freigeschalteter UI bliebe das Ziehen wirkungslos, solange das steht.

### Was bereits trägt (nicht anfassen)

Der Weg von der Persistenz bis in die Mail hält die Reihenfolge schon durch — #1335 Scheibe 1 hat diese Hälfte geliefert:

- `display_config.active_metrics` ist eine geordnete Liste; `compareEditorLoad.ts:24-33` `rehydrateActiveMetrics` gibt das Array 1:1 zurück
- `src/app/compare_metric_ids.py:110-127` `resolve_enabled_metrics` — ausdrücklich reihenfolge-erhaltend (`dict.fromkeys`)
- `src/output/renderers/email/compare_html.py:486-491` `_visible_metrics` — `ordered = [by_key[k] for k in enabled_metrics …]`, folgt der übergebenen Reihenfolge (im Issue empirisch bestätigt)
- Fix an Position 1: „Amtliche Warnungen" (`compare_html.py:217` in `CV2_METRICS`, angewandt `:486,491`)

### Latenter Widerspruch

`src/output/renderers/comparison.py:71` deklariert `enabled_metrics: set | None` — ein Mengen-Typ auf einem Wert, dessen Reihenfolge inzwischen Bedeutung trägt. Faktisch wird eine Liste durchgereicht. Sollte mitgezogen werden, sonst lädt die Signatur zum nächsten Reihenfolge-Verlust ein.

## Teil B — Orts-Reihenfolge (dreifacher Verlust)

Der Orte-Tab speichert korrekt — verloren geht es danach, an drei unabhängigen Stellen:

| # | Stelle | Was passiert |
|---|---|---|
| 0 | `CompareTabs.svelte:1190-1214,232-278` → `buildHubPutPayload` → `ComparePreset.LocationIDs` (`internal/model/compare_preset.go:18`) | ✅ Reihenfolge wird korrekt persistiert (PUT 200, im Issue belegt) |
| 1 | `src/app/services/scheduler_dispatch_service.py:340` | `[loc for loc in all_locations_cache if loc.id in location_ids]` — filtert über den Cache, übernimmt dessen Reihenfolge statt der von `location_ids` |
| 2 | `comparison_engine.py:278` | sortiert nach Score |
| 3 | `compare_html.py:1014-1019,1092` + `comparison.py:105,387,559` | `sort_locations_alphabetically` — case-insensitiv nach Ortsname |

Alle drei müssen fallen, sonst bleibt der Fix wirkungslos. Stufe 1 ist der unauffälligste: dort geht die Reihenfolge schon vor jeder Sortierung verloren.

`ComparisonResult.locations` (`src/app/models/user.py:168-179`) trägt den Kommentar „Sorted by score (descending)" — beschreibt einen Zustand, der seit #1110 nicht mehr gilt.

## Zu ändernde Festlegungen (Specs + Tests)

Die alphabetische Sortierung ist **keine Panne**, sondern eine PO-Entscheidung vom 2026-07-08 mit eigenen Akzeptanzkriterien. Sie wird abgelöst, nicht still überfahren:

| Ort | Wörtlich | Status |
|---|---|---|
| `docs/specs/modules/compare_location_summary.md:464-471` (AC-10) | „…Then sind die Orte alphabetisch geordnet, identisch zur Reihenfolge in der Matrix darüber" | muss umgeschrieben werden |
| `docs/specs/modules/compare_location_summary.md:381` | „ein Satz pro Ort mit Daten, alphabetisch geordnet" | dito |
| `docs/specs/_archive/modules/issue_1110_compare_mail_v2.md:223-227` (AC-1), `:54,70-73` | „präzisiert per PO-Entscheidung 2026-07-08: alphabetisch statt Preset-Reihenfolge" | Archiv — Ablösung vermerken |
| `docs/specs/modules/compare_weather_metrics_tab.md:128-134` | schreibt `ROUTE_ONLY_SECTIONS` inkl. `'reihenfolge'` fest | muss umgeschrieben werden |
| `frontend/src/lib/components/shared/__tests__/weatherMetricsTabSharing.test.ts:147` | friert das Fehlen des Reihenfolge-Abschnitts im Vergleich fest | Test dreht sich um |
| `tests/tdd/test_issue_1110_compare_mail_v2.py` — `test_ac1_…_orte_alphabetisch_sortiert`, `test_ac10_klartext_alphabetisch_sortiert` | prüfen alphabetische Reihenfolge in HTML und Klartext | Tests drehen sich um |

Kein ADR betroffen — die Sortierung war eine Ausführungs-Entscheidung in #1110, keine Architektur-Entscheidung. **Aber:** Ablösung einer dokumentierten Entscheidung ⇒ ADR-Pflicht prüfen (CLAUDE.md: „Abweichung ⇒ neues ADR").

## Vorbild Trip (Muster zum Nachziehen)

- `src/app/models.py:537` — `order: int = 0`, „Sortier-Reihenfolge innerhalb des Buckets"
- `src/output/renderers/channel_layout.py:59-65` — `sorted(…, key=lambda m: m.order)`; fehlender `order` = 0, Doppelwerte unkritisch (`sorted` ist stabil)

Für den Vergleich ist ein eigenes `order`-Feld voraussichtlich **nicht** nötig: `active_metrics` bzw. `location_ids` sind bereits geordnete Listen — die Listenposition *ist* die Reihenfolge. Das ist der einfachere und bereits tragende Weg (Entscheidung gehört in die Spec).

## Risiken

1. **Teilfix wirkt wie kein Fix.** Bei den Orten müssen alle drei Verluststellen fallen; bei den Metriken zusätzlich der Diff-Guard. Jede einzelne übersehene Stelle macht die ganze Änderung für den Nutzer unsichtbar — genau der Zustand, den das Issue meldet.
2. **Mail-Pfad ist gate-bewehrt.** Änderungen an `compare_html.py`/`comparison.py` lösen das Renderer-Commit-Gate #811 aus und verlangen einen erfolgreichen Compare-Mail-Validator-Lauf gegen eine echt zugestellte Staging-Mail (≥3 Orte).
3. **Bestandsdaten.** Vergleiche ohne je gespeicherte `active_metrics` gelten als „alle Metriken aktiv" (`hydrateWeatherMetricsFromPreset:22-26`). Die Standard-Reihenfolge für solche Altbestände muss definiert werden, sonst ändert sich deren Mail ungefragt.
4. **Nachweis nur über die echte Mail.** Ein Nutzer sieht die Reihenfolge in der Mail, nicht im DOM — die Abnahme muss an einer zugestellten Staging-Mail hängen, nicht an einem Unit-Test.
5. **Reihenfolge unsichtbar.** Das Issue fordert zusätzlich, dass der Nutzer *sieht*, in welcher Reihenfolge die Metriken landen. Der geteilte Baustein bringt Positionsnummern und die Mail-Vorschau (`WeatherV2MailPreview`) bereits mit — auch hier: verwenden, nicht neu bauen.

## Analysis

### Type
Bug (zwei unabhängige Befunde in einem Issue)

### PO-Entscheidungen 2026-07-24 (verbindlich)

| Frage | Entscheidung |
|---|---|
| **Priorität** | **Metrik-Reihenfolge zuerst.** Orts-Reihenfolge ist dem PO „relativ egal" → zweite Scheibe, bleibt aber im Scope (der Orte-Tab gibt ein wörtliches Versprechen ab, das sonst weiter falsch ist) |
| Reichweite der Metrik-Reihenfolge | **Überall gleich** — HTML-Mail, Klartext-Teil und Telegram folgen derselben Reihenfolge. Damit ist `comparison.py` in Scheibe 1 mit drin ⇒ Renderer-Gate #811 greift bereits für Scheibe 1 |
| „Amtliche Warnungen" | **Bleibt fest an Position 1** (Sicherheitsinformation vor Komfortdaten), aber im Editor **sichtbar** als fixierte, nicht ziehbare Zeile mit Hinweis — damit es nicht wie ein Sortier-Fehler wirkt |

### Schnittführung (angepasst an PO-Priorität)

**Scheibe 1 — Metrik-Reihenfolge (zuerst).** Für sich nutzbar: der Nutzer kann die Reihenfolge einstellen und sie steht so in Mail und Telegram.
**Scheibe 2 — Orts-Reihenfolge (danach).** Für sich nutzbar: das bestehende Ziehen im Orte-Tab wirkt endlich.

Ursprünglich war B-vor-A empfohlen (kleinerer, isolierterer Fix). Die PO-Priorität dreht das um. Vertretbar, weil beide Scheiben unabhängig sind und Scheibe 1 durch die „überall gleich"-Entscheidung ohnehin durchs Mail-Gate muss.

### Affected Files — Scheibe 1 (Metriken)

| Datei | Änderung | Beschreibung |
|---|---|---|
| `frontend/.../weather-metrics-tab/weatherMetricsTabSections.ts:19,23` | MODIFY | `'reihenfolge'` aus `ROUTE_ONLY_SECTIONS` lösen, für beide Kontexte sichtbar (Muster: `'official_alerts'`, Z. 24) |
| `frontend/.../shared/WeatherMetricsTab.svelte` | MODIFY | Vergleich-Zweig bindet **denselben** `LayoutTab`+`WeatherV2Reihenfolge`-Block ein; `context` dynamisch statt hart `"route"`; `primaryColumns={wiz.activeMetricKeys}`; kleine `metricById`-Ableitung aus dem bereits geladenen Compare-Katalog; `toggleCompareMetric` von `Set` auf Array-Filter/-Push (Trip-Muster Z. 471-500) |
| `frontend/.../weather-metrics-tab/weatherMetricsCompareSave.ts:54-58` | MODIFY | `.sort()` im Diff-Guard entfernen — reine Umsortierung muss als Änderung zählen. AC-4 („kein Schreiben ohne Nutzer-Geste") bleibt gewahrt, weil die Auslösung weiterhin an einer echten Geste hängt |
| `src/output/renderers/comparison.py` | MODIFY | Klartext + Telegram folgen der übergebenen Metrik-Reihenfolge statt fest verdrahteter Quellcode-Reihenfolge (`_metric_visible:126-127` prüft heute nur Mitgliedschaft); Typ `enabled_metrics: set` → `list[str]` |
| `frontend/.../__tests__/weatherMetricsTabSharing.test.ts:147` | MODIFY | Test dreht sich um (fror das Fehlen fest) |
| `docs/specs/modules/compare_weather_metrics_tab.md:128-134` | MODIFY | `ROUTE_ONLY_SECTIONS`-Festschreibung umschreiben |

**Nicht anfassen** (trägt bereits): `compare_metric_ids.py:110-127`, `compare_html.py:486-491` `_visible_metrics`, `compareEditorLoad.ts:24-33`, sowie der Trip-Zweig `WeatherMetricsTab.svelte:853-885` (nur additiv erweitern — geteilte Bausteine, beide Aufrufer müssen grün bleiben).

### Affected Files — Scheibe 2 (Orte)

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/scheduler_dispatch_service.py:340` | MODIFY | Muster von `compare_preview_service.py:210-227` übernehmen (dict-by-id, Iteration über `location_ids`) — **kein neuer Helfer**, das Muster existiert schon und ordnet korrekt |
| `src/services/comparison_engine.py:278` | MODIFY | Score-Sortierung entfernen |
| `src/output/renderers/email/compare_html.py:1014-1019` | MODIFY | Den **einen** bestehenden Sortier-Helfer auf Reihenfolge-Erhalt umstellen; die 4 Aufrufstellen bleiben unverändert (Ein-Helfer-Struktur bleibt) |
| `src/app/user.py:175` | MODIFY | Falscher Kommentar „Sorted by score (descending)" |
| `docs/specs/modules/compare_location_summary.md:381,464-471`, `_archive/.../issue_1110_compare_mail_v2.md` | MODIFY | AC-10/AC-1 ablösen, Ablösung im Archiv vermerken |
| `tests/tdd/test_issue_1110_compare_mail_v2.py` | MODIFY | Zwei Tests drehen sich um |

### Scope Assessment

| | Dateien | LoC | Risiko |
|---|---|---|---|
| Scheibe 1 | ~6 | ~120-160 | MEDIUM |
| Scheibe 2 | ~6 | ~50-70 | LOW-MEDIUM |

Beide je für sich unter dem 250er-Limit.

### Zusätzliche Funde der Analyse (über das Issue hinaus)

1. **Der Preview-Pfad ordnet bereits richtig.** `compare_preview_service.py:210-227` iteriert über `location_ids` — nur der Versandpfad tut es nicht. Erklärt, warum die Vorschau in der App stimmt und die zugestellte Mail nicht.
2. **Vierte Verluststelle ausgeschlossen.** Alle 26 `location_ids`-Fundstellen geprüft; ordnungserhaltend sind `compare_official_alert.py:115`, `compare_alert.py:154`, `compare_radar_alert.py:132`, `compare_preview_service.py:221`. Zusätzliche Gegenprobe über Sortier-Aufrufe gegen `LocationResult` ergab genau die zwei bekannten Stellen.
3. **`ComparisonResult.winner` ist im ganzen Repo ungenutzt** — das Entfernen der Score-Sortierung ist gefahrlos.
4. **Altbestands-Falle (existiert schon heute, unabhängig von #1359):** Der Legacy-Standard im Frontend (`COMPARE_METRIC_KEYS`) hat eine **andere** Reihenfolge als der Renderer-Standard (`CV2_METRICS`). Speichert ein Alt-Vergleich zum ersten Mal irgendetwas in diesem Tab, materialisiert sich die Frontend-Reihenfolge und die Mail springt ungefragt um. Mehr Speichervorgänge durch die neue Bedienung machen das wahrscheinlicher. **Tech-Lead-Entscheidung: Legacy-Standard auf die Renderer-Reihenfolge (`CV2_METRICS`) ziehen**, damit sich für Altbestände nichts ungefragt ändert. Gehört in Scheibe 1.
5. **Speichern nach Ziehen ist nicht gesichert.** Im Trip löst das Ziehen den Speichervorgang direkt aus; im Vergleich hängt er am Durchreichen von Klick-/Fokus-Ereignissen. Nach einer Ziehgeste unterdrücken Browser das Klick-Ereignis häufig — dann würde nichts gespeichert. Muss gegen Staging empirisch geprüft und im Zweifel wie im Trip direkt verdrahtet werden. **Das ist der wahrscheinlichste Weg, wie dieser Fix scheinbar funktioniert und trotzdem wirkungslos bleibt.**

### Offene Punkte für die Spec-Phase

1. Fixierte „Amtliche Warnungen"-Zeile im Editor: prüfen, ob der bestehende Reihenfolge-Baustein eine nicht-ziehbare Zeile bereits kann. Falls nicht, ist die minimale Lösung ein Hinweistext im vorhandenen Hinweis-Muster (`option-hint`) — **kein neues Bedienelement**.
2. Verhalten bei Leerauswahl bleibt unverändert (#1191-Semantik: leeres Array ist eine bewusste Wahl).
