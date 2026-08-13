# Context: #1703 Scheibe 8 — Compare-Kanal-Tabs im Frontend

**Workflow:** `feat-1703-s8-compare-kanal-tabs` · **Track:** Full Process (Intake-Score 5/6)
**Erstellt:** 2026-08-13

## Request Summary

Der Ortsvergleich soll kanalweise Metrik-Layouts bekommen wie der Trip-Editor — heute führt
Compare **eine globale Metrik-Liste** (`wiz.activeMetricKeys`), Trip führt **Layouts je Kanal**
(`display_config.channel_layouts.{email,telegram,sms}`). PO-Entscheidung (a) vom 2026-08-10 in
#1514: **JA**. Scheibe 8 ist Voraussetzung für Scheibe 7 (Reihenfolge-Wächter für die
Compare-Seite).

## 🔴 Befund mit Vorrang: Das ist eine Entscheidungs-Umkehr, keine Neuentwicklung

Compare **hatte** bereits einmal kanalweise Metrik-Auswahl (Step4Layout, #442, 2026-05-29). Sie
wurde in drei Schritten abgeschafft:

| Datum | Issue | Was |
|---|---|---|
| 2026-07-18 | #1287/#1291 | Kanal-Metrikauswahl aus der **Bedienung** entfernt — Begründung wörtlich: „Attrappen" (`docs/reference/api_contract.md:3723-3728`) |
| 2026-07-24 | #1351 Teil 2 | Feld `channel_layouts` aktiv aus dem Compare-**Speicherweg** entfernt (`compareEditorSave.ts:104-114`) + Bestands-Migration `scripts/migrate_1351_drop_compare_channel_layouts.py` |
| 2026-07-29 | #1359 | Ersatzweg gewählt: **eine** flache Liste, in Telegram/SMS nur **budgetbasiert gekürzt** (`docs/specs/modules/compare_kanal_metriken.md`) |

`docs/specs/modules/rework_1351_compare_catalog.md:215-217` sagt wörtlich:

> „sollte in Zukunft doch eine Kanal-spezifische Metrikauswahl für Compare gewünscht werden, ist
> das eine **neue Spec** (widerspricht aktuell #1287/#1291 und der Konvergenz-Richtung)"

**Warum das die wichtigste Randbedingung der Scheibe ist:** Die alten Compare-Kanal-Tabs wurden
nicht entfernt, weil sie unerwünscht waren, sondern weil sie **wirkungslos** waren — die
Oberfläche bot eine Kanal-Auswahl an, die Python-Seite las nie etwas anderes als die eine flache
Liste. Wer nur die Oberfläche zurückbaut, baut exakt die Attrappe wieder auf, die gelöscht wurde.
**Scheibe 8 muss die ganze Kette liefern** (Oberfläche → Speicherweg → Resolver → Renderer) oder
sie liefert nichts.

**Pflicht daraus (CLAUDE.md, Abschnitt ADRs):** „Eine dokumentierte Entscheidung wird nie still
rückgängig gemacht: Abweichung ⇒ neues ADR (Status ‚Abgelöst durch')". Die Scheibe braucht ein
ADR, das #1287/#1291/#1351 ablöst und sich auf den PO-Entscheid vom 2026-08-10 stützt.

## Der zweite Haken: `colCount` bedeutet in Compare etwas anderes

`WeatherMetricsTab.svelte:1201-1211` dokumentiert eine **bewusste** Abweichung: der geteilte
`LayoutTab`-Organism wird im Vergleich absichtlich nicht gemountet, weil seine Kappungs-Aussage
spaltenbasiert ist — **im Vergleich sind die Spalten die ORTE, die Metriken sind Zeilen**. Mit
Metriken als `colCount` stünde dort eine falsche Zahl.

Derselbe Kommentar nennt als echte Budgets „7 Metrik-Zellen je Ort im Telegram, **2 in der
SMS**". **Nachgemessen: die Telegram-Zahl stimmt, die SMS-Zahl ist veraltet.**

| Kanal | Gemessenes Budget | Beleg |
|---|---|---|
| E-Mail | unbegrenzt | `channel_layout.py:45-55`, `max_table_cols: None` |
| Telegram | **7 Metrik-Werte je Ort** (`max_table_cols: 8` inkl. impliziter Orts-Spalte) | `channel_layout.py:19`, `comparison.py:712-716` |
| SMS | **kein festes Zell-Limit** — `max_chars: 153`, Zellen werden von hinten nach Zeichenbudget gekürzt (`+N`-Marker) | `comparison.py:928-940` |

Die feste Zwei-Zellen-Grenze (`_SMS_METRICS_PER_LOCATION`) wurde am 2026-07-29 mit `9cdb492c`
abgeschafft („Die Vergleichs-SMS zeigt, was gewählt ist — nicht zwei Größen", #1362 S5b). Der
Kommentar in `WeatherMetricsTab.svelte:1207-1208` stammt aus `aea6ed88` (#1359, 2026-07-24) und
ist damit **fünf Tage älter als die Änderung, die er beschreibt**. ⚠️ Die Erstfassung dieses
Dokuments hat die veraltete Zahl ungeprüft übernommen.

Das ist der einzige inhaltliche Grund, warum die Einbettung bisher unterblieb; ein technisches
Verbot gibt es nicht. `ltChannels.ts:34-37` hält `SMS_COMPARE_CHAR_LIMIT = 153` bereits vor —
vorbereitet, aber ungenutzt. Das `LtLimit`-Modell (`none` | `columns` | `chars`) bildet genau
diese drei Formen bereits ab.

## Related Files

### Frontend — Compare (Ist-Zustand: eine globale Liste)
| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts:31` | `activeMetricKeys = $state<string[]\|null>(null)` — der globale Einzelzustand. `null` = nie eingestellt, `[]` = bewusst leer |
| `frontend/src/lib/components/compare/compareEditorSave.ts:104-130` | Payload-Bau; **droppt `channel_layouts` aktiv** (Z. 104-114); `active_metrics` als `{metric_id, aggregation}[]` |
| `frontend/src/lib/components/compare/compareHubWizardBridge.ts` | Hydrate/Flush/Rollback + `createPutQueue` (614 Zeilen) |
| `frontend/src/lib/components/compare/compareEditorLoad.ts` | Gegenstück beim Laden |
| `frontend/src/lib/components/compare/CompareTabs.svelte:1339-1392` | Wetter-Metriken-Reiter; zwei verschachtelte Commit-Wrapper (s. Risiken) |
| `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsCompareSave.ts` | Hub-Save-Zweig, `WeatherMetricsSnapshot` ohne Kanalbezug |

70 Nicht-Test-Fundstellen von `activeMetricKeys` in 12 Dateien.

### Frontend — Trip (Soll-Muster)
| Datei | Relevanz |
|---|---|
| `frontend/src/lib/types.ts:278-299` | `ChannelLayouts { email?, telegram?, sms?: WeatherConfigMetric[] }` in `DisplayConfig` |
| `frontend/src/lib/components/shared/weather-metrics-tab/channelMetricLayouts.ts` | **Das Zielmuster.** `startChannelOverride` (Copy-on-write), `channelOverrideFromMetrics` (Laden), `splitChannelMetricsForDisplay` (aktiv/„Aus"), `mergeAllChannelLayoutsForSave` (alle Kanäle serialisieren) |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:248-276` | `channelBuckets: Record<ChannelId, ChannelOverride\|null>`, `channelView()` = Kaskaden-Read |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:704-731` | `onToggleMetric` — globale Abwahl schreibt in **alle** Kanal-Overrides durch (ADR-0050 Regel 3) |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:1358-1381` | Der `<LayoutTab context="route">`-Mount, den Compare bekommen soll |

### Frontend — geteilte Bausteine (existieren bereits context-fähig)
| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/shared/layout-tab/LayoutTab.svelte` | 74 Zeilen, `context: 'route'\|'vergleich'`; einzige Verzweigung: `hasLabelColumn={context === 'vergleich'}` (Z. 59) |
| `frontend/src/lib/components/shared/layout-tab/LTChannelPicker.svelte` | Kanal-Umschalter, context-unabhängig, Testids `channel-tab-{id}` |
| `frontend/src/lib/components/shared/layout-tab/ltChannels.ts` | `LtLimit`-Einheitsmodell (none/columns/chars); `SMS_COMPARE_CHAR_LIMIT = 153` vorbereitet, ungenutzt (Z. 34-37) |
| `frontend/src/lib/components/shared/layout-tab/LTComparePreview.svelte` | **Totcode** (300 Zeilen, kein Importeur seit #1719 S3) |
| `frontend/src/lib/components/shared/layout-tab/LTCutLine.svelte` | Primitive, von keiner UI konsumiert |

### Backend
| Datei | Relevanz |
|---|---|
| `internal/model/compare_preset.go:48` | `DisplayConfig map[string]interface{}` — untypisiertes Blob, wie beim Trip. **Kein Go-Schema-Change nötig** |
| `internal/handler/compare_preset.go:331-341` | `mergeConfigMap(...)` — feldweiser Shallow-Merge |
| `internal/handler/config_merge.go:11-22` | Löscht Keys **nie**. Leere Auswahl muss explizit als `[]` reisen |
| `internal/store/compare_preset.go:84-116` | Ablage `data/users/<uid>/briefings/<id>.json`, Unterscheidung nur über `"kind": "vergleich"` |

### Python-Core
| Datei | Relevanz |
|---|---|
| `src/services/report_config_resolver.py:212-286` | **Der Engpass.** `enabled_metrics=resolve_enabled_metrics(display_config.get("active_metrics"))` — genau ein flaches Feld, kein Kanal-Dict |
| `src/output/renderers/compare_metric_ids.py:144-197` | `resolve_enabled_metrics()`; `None` = kein Filter, `[]` = bewusst leer |
| `src/output/renderers/comparison.py:678-701` | `_channel_layout_for_metrics()` — baut eine `MetricConfig`-Brücke, in der **alle** Metriken `bucket="primary"` sind; kürzt je Kanal nur nach Budget, **wählt nie anders aus** |
| `src/services/scheduler_dispatch_service.py:436,496-499` | Reicht **dieselbe** Liste an alle drei Renderer |
| `src/app/models.py:839-916` | Trip-Kaskade `get_metrics_for_channel()` + `_clip_to_global_maximum()` — das Soll-Verhalten |

## Existing Specs & ADRs

- `docs/adr/0050-metrik-kaskade-verfeinerung-nicht-ersetzung.md` — **verbindliche Regel:**
  Grundauswahl = Maximum, Kanal darf nur abwählen, globale Abwahl schreibt sofort durch
- `docs/specs/modules/rework_1351_compare_catalog.md` — die abzulösende Entscheidung
- `docs/specs/modules/compare_kanal_metriken.md` — der 2026-07-29 gewählte Ersatzweg (Budget-Kürzung)
- `docs/specs/modules/fix_1719_s3_aus_ist_ein_zustand.md` — Trip-Editor-Vorbild; **Block D/AC-13
  grenzt Compare ausdrücklich aus**
- `docs/specs/modules/feat_1481b_pendant_gate.md` — Neuanlagen unter `compare/**` lösen die
  Pendant-Sperre aus; Ausweg ist `shared/**` (= ohnehin der architektonisch richtige Ort)
- `docs/reference/metric_output_matrix.md` Abschnitt 6 — Scheiben-Zuschnitt, Abschnitt 7 PO-Entscheid

## Dependencies

**Upstream (was wir benutzen):** `channelMetricLayouts.ts`, `LayoutTab`/`LTChannelPicker`/
`ltChannels.ts`, `mergeConfigMap` (Go), `resolve_enabled_metrics` (Python), ADR-0050-Kaskade.

**Downstream (was von uns abhängt):** Scheibe 7 (Reihenfolge-Wächter Compare-Seite) ist
ausdrücklich blockiert, bis Compare eine kanalbezogene Soll-Reihenfolge hat.

**Zwei Wächter, die diese Scheibe umdrehen muss** (sie sperren heute genau das Zielverhalten):
- `frontend/src/lib/components/shared/__tests__/compare_outlook_metric_selection_structure.test.ts`
- `frontend/src/lib/components/shared/__tests__/compare_hourly_layout_controls_structure.test.ts`
- sowie `.../weather_metrics_tab_vergleich_reihenfolge_no_off_columns.test.ts`

Alle drei prüfen per AST, dass am Vergleichs-Aufruf **kein** `offColumns`/`onRestore` hängt
(#1719 S3, AC-13). Sie sind kein Hindernis, sondern der genaue Ort, an dem die Abgrenzung
dokumentiert steht — sie müssen in derselben Scheibe umgeschrieben werden, nicht umgangen.

## Risks & Considerations

1. **🔴 Attrappen-Risiko (Hauptrisiko).** Wird nur die Oberfläche gebaut, entsteht wieder genau
   das, was #1287/#1291 als „Attrappen" gelöscht hat. Der Nachweis muss am **zugestellten**
   Ergebnis hängen (Compare-Mail/Telegram/SMS zeigen je Kanal verschiedene Metriken), nicht am
   PUT-Body. Vgl. `reference_messe_die_zugestellte_ausgabe_nicht_die_zwischendatei`.

2. **Doppelter Commit-Pfad (#1423) — Warnung entschärft, aber nicht gegenstandslos.**
   ⚠️ *Die Erstfassung dieses Dokuments behauptete hier einen offenen Produktfehler mit 20–30 %
   Änderungsverlust. Das war falsch und stammte aus einem veralteten Gedächtniseintrag.*

   **Gemessener Stand:** #1423 ist **geschlossen** (2026-07-30, Fix `c7710e68`) und umbenannt in
   „Prüfscript-Fehler: `count()`-Kurzschluss gegen ladende Oberfläche…". Der Autor hat die
   Race-Diagnose selbst widerrufen: die verschachtelten Wrapper (`CompareTabs.svelte:1350-1361`)
   sind real und feuern 2–3 Commit-Aufrufe je Klick, **aber die Warteschlange dahinter fängt das
   ab** — jeder redundante Aufruf sieht den bereits gespeicherten Stand und tut nichts. Der
   Code-Kommentar `:1340-1349` behält recht. Die echte Ursache war der Testablauf
   (`count() === 0 → continue` gegen eine noch ladende Oberfläche; der Ausblick-Block ist während
   des Katalog-Ladens bewusst aus dem DOM entfernt, `WeatherMetricsTab.svelte:1026`).
   `test.fixme()` ist zurückgenommen, Abnahme 10/10 grün.

   **Was für diese Scheibe trotzdem offen ist:** Der Diff-Schutz wurde gegen **eine flache Liste**
   gemessen. Ob er auch trägt, wenn **drei Kanal-Layouts** durch dieselben zwei Wrapper committet
   werden, ist ungemessen. Das ist keine Altlast, sondern ein **neues Risiko dieser Scheibe** —
   gehört in die Testauflage, nicht in einen Vorab-Fix.

   Übertragbare Lehre für die Nachweisführung dieser Scheibe: ein `count() === 0 → weiter` gegen
   eine ladende Oberfläche macht aus „noch nicht da" ein stilles „gibt es nicht". Playwright-
   Nachweise müssen auf das Ladeende warten und `waitFor({state:'attached'})` benutzen.

3. **Server-Merge löscht nie.** Eine geleerte Kanal-Auswahl muss explizit als `[]` persistiert
   werden — Key weglassen wirkt nicht (`config_merge.go`). Hat bei #1299 schon einmal einen Bug
   erzeugt. Ein Client-Unit-Test auf den PUT-Body beweist das Serververhalten **nicht**.

4. **Shallow-Merge ersetzt `channel_layouts` als GANZES.** Deshalb serialisiert der Trip-Pfad
   über `mergeAllChannelLayoutsForSave` **alle** editierten Kanäle, nicht nur den aktiven
   (`channelMetricLayouts.ts:114`). Derselbe Fehler ist im Compare-Pfad neu zu vermeiden.

5. **`colCount`-Semantik** (s.o.) — die Kappungs-Aussage braucht für Compare eine eigene
   Ableitung (Metrik-Zellen je Ort), sonst zeigt die Oberfläche eine falsche Zahl.

6. **Kanal-Umfang: drei Reiter, nicht vier — bestätigt.** `notification_service.send_compare_report`
   (`:956-1044`) kennt genau `email` (`:997`), `telegram` (`:1016`), `sms` (`:1034`). Die
   Kanal-Tabs im Vergleich zeigen also **drei** Reiter.

   ⚠️ *Ein Agent meldete hier einen vermeintlichen Defekt: `effective_compare_channels()` nehme
   `premium_sms` in die Kanal-Menge auf, `send_compare_report` ignoriere es stillschweigend, der
   Nutzer bekomme also nichts. **Nachgemessen — das ist KEIN Defekt** und wurde vor der Meldung
   an den PO verworfen:*
   - Der Premium-SMS-Schalter wird nur gerendert, wenn `onPremiumSmsChange` übergeben wird
     (`VTBriefingChannels.svelte:198`) — und das geschieht **nur im route-Zweig** von
     `VersandTab.svelte:79-85` („Nur route: im vergleich-Zweig ist Premium-SMS kein Kanal,
     ADR-0049"). Im Ortsvergleich gibt es den Briefing-Schalter also gar nicht.
   - `send_premium_sms` reist am Compare-Preset trotzdem mit, weil Premium-SMS dort **Alarm**-Kanal
     ist (#1745) — und im Alarm-Pfad ist er korrekt verdrahtet
     (`send_multi_location_official_alert:1147-1149`).
   - `effective_compare_channels()` bedient **beide** Pfade; dass der Briefing-Pfad den Kanal
     nicht kennt, ist genau das dokumentierte Sollverhalten (ADR-0049, CLAUDE.md).

7. **Bestandsdaten.** Es liegen im Sandbox-Datenbestand **keine** Compare-Presets (`kind:
   vergleich`) — alle 9 `briefings/*.json` sind Trips. Die Migration ist damit risikoarm, aber
   der Altbestands-Pfad (`active_metrics` ohne `channel_layouts`) muss weiter funktionieren:
   fehlt das Feld, gilt die globale Liste für alle Kanäle (Trip-Vorbild: `loader.py:836-875`).

8. **LoC-Limit 250.** Der Umbau ist laut Matrix-Doku „groß — eigenes Vorhaben". Ein Override ist
   **nicht** ohne PO-Freigabe zulässig. Realistischer Weg: die Scheibe selbst noch einmal
   schneiden (z. B. Datenmodell+Persistenz+Resolver zuerst, Oberfläche danach). Vorschlag gehört
   in die Analyse-Phase.

9. **Totcode-Gelegenheit.** `LTComparePreview.svelte` (300 Zeilen) und `LTCutLine.svelte` haben
   keinen Importeur. Kein Scheiben-Ziel, aber beim Anfassen des Ordners zu vermerken.

## Der eigentliche Umbau-Kern: das Compare-Metrikformat ist zu arm

Compare speichert je Metrik **zwei** Felder, Trip **vierzehn**:

| | Felder |
|---|---|
| Compare `active_metrics` (`compareMetricSelection.ts:98`, `compare_metric_ids.py:116-122`) | `metric_id`, `aggregation` (Einzahl) |
| Trip `MetricConfig` (`models.py:609-641`, `types.ts:205-226`) | `metric_id`, `enabled`, `aggregations` (Liste), `morning_enabled`, `evening_enabled`, `use_friendly_format`, `format_mode`, `alert_enabled`, `alert_threshold`, `horizons`, `bucket`, `order`, `sms_threshold`, `derived` |

Für kanalweise Layouts werden mindestens `enabled` (der Zustand „Aus in diesem Kanal", ADR-0050
Regel 4) und `order` (Reihenfolge je Kanal, Voraussetzung für Scheibe 7) gebraucht. **Gute
Nachricht zur Reihenfolge:** sie ist heute schon die Listenposition und wird reihenfolge-erhaltend
bis in den Renderer durchgereicht (`compare_metric_ids.py:172,192-196`; `comparison.py:678-701`
setzt `order=i` aus der Position). Es braucht also keinen neuen Reihenfolge-Begriff, nur eine
Liste **je Kanal**.

## Muster-Warnung: dreimal in dieser Analyse waren Aussagen über den eigenen Code veraltet

1. Gedächtnis: #1423 als offener Produktfehler → tatsächlich Testfehler, widerrufen
2. Code-Kommentar `WeatherMetricsTab.svelte:1207-1208`: „2 Zellen in der SMS" → seit `9cdb492c` falsch
3. Test-Kommentar `issue_683_wizard_remove.test.ts`: verweist auf `LayoutTab context="vergleich"`,
   das es in der lebenden Einbettung nicht (mehr) gibt

**Konsequenz für diese Scheibe:** Jede Zahl und jede Zusicherung, die aus einem Kommentar oder
einer Spec stammt, wird vor Verwendung am Code nachgemessen. Vgl.
`reference_aussagen_ueber_eigenen_code_veralten_still`.

## Analysis

### Type
Feature (Entscheidungs-Umkehr mit ADR-Pflicht)

### Antworten auf die vier offenen Fragen

**F1 — Schnitt.** Der naheliegende Schnitt „erst Technik, dann Oberfläche" wird **verworfen**.
Er wäre zwar attrappenfrei (Wirkung ohne Oberfläche ist nicht dieselbe Sünde wie Oberfläche ohne
Wirkung), löst aber für sich genommen **keine Nutzer-Zusage** ein — niemand kann `channel_layouts`
ohne Editor befüllen. Das Verzeichnis liefert das mahnende Gegenbeispiel selbst:
`LTComparePreview.svelte` liegt seit #1719 S3 mit 300 Zeilen ohne Importeur herum.

**Stattdessen Schnitt entlang der Ausgabefläche, Kette jeweils vollständig:** Diese Scheibe
liefert kanal-eigene Metrik-Auswahl für die **Übersichtstabelle** des Ortsvergleichs
(`display_config.active_metrics`) — Oberfläche, Speicherweg, Resolver, Renderer, Nachweis an der
zugestellten Ausgabe. Stundenverlauf (`hourly_metrics`) und Ausblick (`outlook_metrics`) bleiben
global; sie sind eigene, getrennt gespeicherte Auswahllisten, keine willkürliche Abschneidung.
Das ist architektonisch sauber und für den Nutzer eine vollständige, ehrliche Zusage.

**F2 — #1423.** Nichts mitzufixen (s. Risiko 2). Der Schutz (serialisierte `createPutQueue` +
Snapshot-Diff, Snapshot wird **innerhalb** des Queue-Callbacks gebaut, liest also den frischen
`currentPreset`) ist payload-formunabhängig und hat bereits zwei Domänen-Erweiterungen
unbeschadet überstanden. **Auflage:** Kanal-Overrides werden in die bestehende
`WeatherMetricsSnapshot`-Domäne **erweitert**, niemals als dritter Wrapper/Handler angebaut. Dazu
ein eigener Test: Änderung an Kanal B bei sichtbarem Reiter A → genau ein PUT, Body trägt Kanal B.

**F3 — Kappungs-Aussage.** Kein Fork, kein neuer Text. Zahlen aus dem vorhandenen
`LtLimit`-Modell: E-Mail `none`, Telegram `columns: 7` (**identisch zum Trip** — gleiche
`CHANNEL_LIMITS`, gleiche `metric_slots = limit - 1`-Rechnung), SMS `chars: 153` über das bereits
vorgehaltene `SMS_COMPARE_CHAR_LIMIT`.

🔴 **Fund mit Fix-Pflicht in dieser Scheibe:** `LayoutTab.svelte:59` setzt
`hasLabelColumn={context === 'vergleich'}`. Dieser Default war für den Hub-Reiter „Layout"
gebaut (Orte als Spalten) — **den hat #1360 aufgelöst**, es gibt heute keinen lebenden
`context="vergleich"`-Konsumenten mehr (`ltChannels.ts:64-68` bestätigt das selbst). Für den
einzig verbleibenden Vergleichs-Anwendungsfall — Metriken als Zeilen — ist der Default **falsch**
und würde vom ersten Tag an eine falsche Kappungslinie zeigen. Konsequenz: `hasLabelColumn` wird
Pflicht-Prop statt kontextabgeleitetem Default, `smsCharLimit` wird durchreichbar. Beides ≤10
Zeilen am geteilten Organism. Damit fällt zugleich der historische Grund weg, aus dem
`WeatherMetricsTab.svelte:1201-1211` die Einbettung verweigert hat.

**F4 — ADR-0050.** Regeln 1–3 (Maximum, nur Abwahl, sofortige Durchschreibung) erbt Compare
**unverändert**; Regel 3 erfüllt sich automatisch, weil der Schnitt beim **Lesen** wirkt.
`_clip_to_global_maximum` ist das Vorbild, aber nicht kopierbar: Compare führt keine
`MetricConfig`-Objekte, sondern flache `{metric_id, aggregation}`-Einträge. Der Schnitt ist
deshalb eine reine ID-Mengen-Operation auf Strings, direkt hinter
`report_config_resolver.py:280`. Reihenfolge = Reihenfolge der Kanal-Liste (bereits
reihenfolge-erhaltend bis in den Renderer).

Regel 4 („Aus ist ein Zustand", wieder einschaltbare Zeile) ist laut ADR **Editor**-Umsetzung und
keine Pflicht — sie wird hier trotzdem übernommen, weil der PO Verhaltensgleichheit mit dem Trip
mehrfach und emphatisch verlangt hat. Eine einfachere „Abwahl entfernt die Zeile"-UX wäre genau
die Divergenz, die zu #1261 geführt hat.

### Affected Files
| File | Change | Beschreibung |
|---|---|---|
| `src/services/report_config_resolver.py` | MODIFY | kanalweise Auflösung + Schnitt gegen globales Maximum |
| `src/services/scheduler_dispatch_service.py` | MODIFY | pro Kanal statt einer gemeinsamen Liste durchreichen |
| `src/services/compare_preview_service.py` | MODIFY | Vorschau folgt demselben Weg |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | MODIFY | `channel_layouts`-Drop (Z. 104-114) zurücknehmen, neues Feld schreiben |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | MODIFY | Kanal-Overrides im State |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Snapshot-Domäne erweitern (kein dritter Wrapper) |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | Kanal-Umschalter im `vergleich`-Zweig |
| `frontend/src/lib/components/shared/layout-tab/LayoutTab.svelte` | MODIFY | `hasLabelColumn` Pflicht-Prop, `smsCharLimit` durchreichbar |
| `frontend/src/lib/components/shared/layout-tab/ltChannels.ts` | MODIFY | Compare-Kanalliste über `ltLimitForChannel(id, SMS_COMPARE_CHAR_LIMIT)` |
| `frontend/src/lib/components/shared/weather-metrics-tab/` | CREATE | Compare-Pendant zu `channelMetricLayouts.ts` für das `{metric_id, aggregation}`-Format (Ablage in `shared/**` — umgeht die Pendant-Sperre strukturell **und** ist der richtige Ort) |
| 3 AST-Wächter (`compare_*_structure.test.ts`, `..._no_off_columns.test.ts`) | MODIFY | Abgrenzung aus #1719 S3 AC-13 umdrehen |
| `docs/adr/0053-*.md` | CREATE | löst #1287/#1291/#1351 ab |

### Scope Assessment
- Dateien: ~12 + Tests
- Geschätzte LoC: **~330–380** (ohne `docs/`) → **über dem 250er-Limit**
- Risiko: **HOCH** (Datenmodell + Persistenz + Editor + Entscheidungs-Umkehr)
