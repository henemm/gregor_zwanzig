# Context: #1435 Etappe E3 — die drei „sichtbaren" Namensfehler

Workflow: `fix-1435-e3-namensfehler` · Stand: 2026-08-01 · Basis: `origin/main`

## Request Summary

#1435 E3 sollte laut Ticket drei heute sichtbare Namensfehler beheben: (A) die
Trip-Übersichtskarte zeigt englische Kennungen statt Namen, (B) die Chip-Vorschau
führt ein eigenes Vokabular, (C) dieselbe Wettergröße trägt zwei SMS-Kürzel.

**Die Recherche widerlegt die Prämisse von A und B und vergrößert C erheblich.**

## Befund A/B — die beiden Bauteile sind toter Code

Beide im Ticket genannten Komponenten sind **nirgends eingebunden**:

| Datei | Status | Beleg |
|---|---|---|
| `frontend/src/lib/components/trip-detail/WeatherMetricsPreviewCard.svelte` | nur re-exportiert, nie importiert | `trip-detail/index.ts:9`; kein weiterer Treffer im gesamten `frontend/src` |
| `frontend/src/lib/components/trip-detail/MetricsPreview.svelte` | nicht einmal exportiert | kein Treffer |
| `frontend/src/lib/components/trip-detail/TripOverview.svelte` | ebenfalls tot | `index.ts:4`; gerendert wird `HubOverview.svelte` (`TripTabs.svelte:188`) |
| `frontend/e2e/trip-detail-overview-right.spec.ts` | prüft `right-card-*`-Testids, die nur in der toten Karte existieren | `:44-47`, `:147-150` |

Der Übersichts-Reiter der Trip-Detailseite rendert `HubOverview.svelte` — Etappen,
Höhenprofil, Briefing-Zeilen, Kanal-Punkte. **Keine Metrik-Chips.** `TripOverview.svelte:2-7`
dokumentiert selbst, dass Issue #487 die rechten Vorschau-Karten aus #409 ersetzt hat.

Die einzigen produktiven Anzeigen von `display_config.metrics` sind
`WeatherMetricsTab.svelte`, `CorridorEditor(.Mobile).svelte` und `AlertsTab.svelte` —
alle lesen bereits das Register.

**Folge:** A und B sind keine Fehler, sondern Leichen. Die richtige Behandlung ist
Löschen, nicht Reparieren. Das dient dem Ziel von #1435 (weniger Listen) unmittelbar:
`rightColumn.ts:53-61` (`getDefaultMetricsForProfile`) und `:115-131`
(`METRIC_LABELS`/`prettyLabel`) sind das dritte und vierte Vokabular, `MetricsPreview.svelte:9`
das fünfte — alle drei ersatzlos entfernbar.

Geprüft: `getDefaultMetricsForProfile` und `getActiveMetrics` haben außerhalb von
`rightColumn.ts` und der toten Karte keine Aufrufer; kein Schreibpfad, keine Persistenz.
`getReportSchedule` aus derselben Datei ist **produktiv** (`TripOverview`… und
`HubOverview`-Kette) und bleibt.

## Befund C — echt, aber kein kleiner Handgriff

`SMS_SYMBOL_BY_METRIC` (`src/output/renderers/sms_trip.py:55-63`) ist **keine
Beschriftungstabelle**, sondern die Token-Grammatik der Touren-SMS. Die Kürzel stehen
wörtlich im zugestellten Text:

```
Arlberg: K-12 D-4 R- PR- W45@8(75@13) G70@8(110@13) TH:- TH+:- SN180 SN24+25 SFL1800 AV3 WC-22
```

| Kennung | SMS-Renderer | Register `sms_code` | Bewertung |
|---|---|---|---|
| `precipitation`,`rain_probability`,`wind`,`gust` | R, PR, W, G | identisch | kein Konflikt |
| `thunder` | `TH:` | `TH` | Doppelpunkt ist Teil der Grammatik (`builder.py:16`), `/api/sms-symbols` strippt ihn |
| `snow_depth` | **SN** | **SD** | echter Konflikt |
| `snowfall_limit` | **SFL** | **SL** | echter Konflikt |
| `wind_chill` | FN/FK/FD (+`WC` im Wintersport-Block) | `TF` | strukturell unauflösbar: eine Größe, vier Kürzel |

**Mitzieh-Pflicht (sonst stiller Bruch):** Die Symbole werden nicht nur ausgegeben,
sondern als Schlüssel für Schwellwert-Filter (#624, `trip_report.py:253-260`) und für
das Abschalten abgewählter Größen (#944, `:265-269`) benutzt. Der Token-Bauer emittiert
sie hartkodiert: `src/output/tokens/builder.py:186-188`, `:198` (inverse Schwellenlogik
für `SFL`), `render.py:10` (`DROP_ORDER`), `adapters/trip_result.py:206-208`. Wer nur die
Tabelle ändert, bekommt lautlos wirkungslose Filter.

**Das eigentliche Nutzer-Argument:** `SN` bedeutet in derselben SMS zweimal etwas
anderes — `HAZARD_SMS_SYMBOLS["snow"] = "SN"` (amtliche Schneewarnung, `hazard_symbols.py:14`)
gegen `SN180` = Schneehöhe 180 cm. Die Position im Format trennt sie
(`docs/reference/sms_format.md:45`), die Bedeutung nicht.

**Gegenposition, die vorliegt:** PO-Präzisierung vom 2026-06-30
(`docs/specs/_archive/modules/issue_917_alert_renderer.md:218`): ADR-0011 Ziel 3
(„doppelte Zuordnungen entfernen") gilt ausdrücklich **nicht** für die
Briefing-SMS-Token-Grammatik — „bleibt unangetastet". `docs/context/fix-1401-namensregister-a.md:221-224`
hat den Konflikt an Sammel-Issue #1199 verwiesen. Eine Umstellung hebt diese
Festlegung auf und braucht sie ausdrücklich.

**Betroffener Umfang bei Umstellung:** 4 Produktivdateien (Renderer, Token-Bauer,
Drop-Reihenfolge, Adapter) + `/api/sms-symbols` + sichtbare Kürzel-Anzeige im
Schwellwert-Editor (`WeatherMetricsTab.svelte:149-156`, `ThresholdMetricRow.svelte:20-37`)
+ ~12 Testdateien inkl. zwei goldener Vergleichsdateien + die kanonische Format-Doku
(`docs/reference/sms_format.md`, 8 Stellen) und 8 weitere Spec-/ADR-Dokumente.

**Gate:** `sms_trip.py` und `trip_report.py` stehen im Renderer-Commit-Gate
(`.claude/hooks/renderer_mail_gate.py:44`). Jeder Commit fordert drei frische Nachweise,
darunter einen bestandenen `briefing_mail_validator.py`-Lauf gegen eine **echt zugestellte
Staging-Mail**. Zusätzlich: Die SMS-Zeile steht nicht in der Mail — der Nachweis läuft
über Telegram-Kurzstil (`notification_service.py:325-337`, sendet exakt `report.sms_text`).

## Related Files

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/utils/rightColumn.ts` | zwei tote Vokabulare (`METRIC_LABELS`, Profil-Vorbelegungen); `getReportSchedule` bleibt |
| `frontend/src/lib/components/trip-detail/{MetricsPreview,WeatherMetricsPreviewCard,TripOverview}.svelte` | tot |
| `frontend/e2e/trip-detail-overview-right.spec.ts` | tot |
| `frontend/src/lib/utils/rightColumn.test.ts` | prüft die toten Funktionen |
| `src/output/renderers/sms_trip.py` | Token-Tabelle (C) |
| `src/output/renderers/trip_report.py` | einziger Leser der Tabelle |
| `src/output/tokens/{builder,render}.py`, `src/output/adapters/trip_result.py` | hartkodierte Symbole |
| `src/app/metric_catalog.py` | `sms_code`, `get_sms_code()` (`:829-835`, unbekannt → `""`) |
| `api/routers/config.py:43-51` | `/api/sms-symbols` |

## Existing Patterns

- **Fläche liest das Register:** `WeatherMetricsTab.svelte:386-415` lädt `/api/metrics`
  selbst mit Lade-/Fehlerzustand; der Alarme-Reiter bekommt den Katalog als **Prop**
  (`AlarmeTab.svelte:69`, gefüllt von `CompareTabs.svelte:602`). Einen zentralen Store
  für `/api/metrics` gibt es **nicht** — jeder Verbraucher fetcht selbst.
- **Ratsche gegen Rückfall:** `shared/__tests__/alarme_tab_shared_labels.test.ts:44-72`
  verbietet per Syntaxbaum-Prüfung eine lokale Beschriftungs-Konstante.
- **Register liefert schon heute:** Ortsvergleichs-SMS (`comparison.py:519`) und
  Alarm-SMS (`alert/render.py:90`) lesen `get_sms_code()` — dort gilt SD/SL bereits.

## PO-Entscheidungen 2026-08-01

Nach Vorlage der Befunde:

1. **E3 wird in zwei Scheiben geteilt, Oberfläche zuerst.**
2. **E3a (zuerst):** Der Reiter „Übersicht" einer Tour bekommt einen **fünften Block
   „Wetter-Metriken"** — die eingestellten Größen in Klartext plus Sprung in den Reiter.
   Namen ausschließlich aus dem zentralen Register. Der tote Code (zwei Karten,
   `TripOverview.svelte`, `METRIC_LABELS`/`prettyLabel`/`getDefaultMetricsForProfile`/
   `getActiveMetrics`, der tote Oberflächen-Test) fällt im selben Zug.
   *Begründung des PO-Zuschnitts:* die Übersicht zeigt heute Etappen · Briefings ·
   Alerts · Vorschau — die Wetter-Auswahl fehlt dort ersatzlos, obwohl sie die
   inhaltlich wichtigste Einstellung einer Tour ist.
3. **E3b (danach):** SMS-Kürzel **ganz vereinheitlicht auf `SD` und `SL`**. Damit ist
   die PO-Präzisierung vom 2026-06-30 (Schutz der Briefing-SMS-Token-Grammatik)
   **ausdrücklich aufgehoben** — gehört als ADR-Konsequenz festgehalten, damit keine
   spätere Sitzung sie stillschweigend zurückdreht.

### Offene Punkte für die Spezifikation E3a

- **Katalog-Bezug:** `HubOverview.svelte` hat heute keinen Zugang zu `/api/metrics`,
  und es gibt keinen zentralen Speicher dafür. Entweder selbst laden (Muster
  `WeatherMetricsTab.svelte:386-415`, mit Lade-/Fehlerzustand) oder von
  `+page.server.ts` mitliefern. Falle #1320: während des Ladens darf nicht „nichts
  eingestellt" erscheinen, wo etwas eingestellt ist.
- **Teilungs-Invariante:** Der Übersichts-Reiter des Ortsvergleichs
  (`CompareTabs.svelte:1081ff`) listet die gewählten Größen **ebenfalls nicht**. Es
  gibt also kein Gegenstück, das wir verletzen — die **Namensauflösung** gehört
  trotzdem als geteilter Baustein angelegt, nicht als Trip-Eigenheit.
- **Altbestand — der schärfste Punkt.** Was eine Tour tatsächlich versendet, entscheidet
  seit #1394 der kanonische Auflöser `resolve_trip_active_metrics()`
  (`src/output/renderers/trip_metric_ids.py`) mit **drei** Zuständen: Auswahl vorhanden ·
  Altbestand ohne Auswahl → `DEFAULT_TRIP_METRIC_IDS` (sieben Größen) · bewusste
  Leerauswahl → bleibt leer. Die alten Profil-Vorbelegungen in `rightColumn.ts:53-61`
  bilden das **nicht** ab.
  **Diese Logik im Frontend nachzubauen wäre exakt die Krankheit, gegen die #1435
  antritt** (eine zweite Antwort auf dieselbe Frage, diesmal in TypeScript). Die Spec
  muss zwischen zwei Wegen entscheiden: (a) der Server liefert die aufgelöste Menge
  aus, oder (b) ein geteilter Frontend-Baustein wird per Test gegen den Python-Auflöser
  gespiegelt. Weg (a) ist der einzige, der keine neue Liste erzeugt.

## Risks & Considerations

1. **A/B als „Reparatur" umzusetzen wäre Arbeit an totem Code** — und würde die
   Vokabulare zementieren, statt sie zu entfernen.
2. **C ändert das ausgelieferte SMS-Format.** Nutzer haben `SN`/`SFL` gelesen. Keine
   Migration möglich, die Umstellung ist zu einem Stichtag sichtbar.
3. **C widerspricht einer dokumentierten Festlegung** (PO 2026-06-30). Ohne
   ausdrückliche Aufhebung wäre die Umsetzung ein stiller Rückgängig-Macher — verboten
   nach ADR-Regel („Abweichung ⇒ neues ADR").
4. **`wind_chill` bleibt in jedem Fall Sonderfall** — vier Kürzel für eine Größe lassen
   sich nicht aus einem `sms_code`-Feld ableiten. Vollständige Register-Herrschaft über
   die SMS-Grammatik ist damit in dieser Etappe **nicht** erreichbar.
5. **Löschen von `rightColumn.test.ts`-Teilen** entfernt Tests — das ist zulässig, wenn
   sie veraltetes Verhalten prüfen (Test-Politik), muss aber benannt werden.
