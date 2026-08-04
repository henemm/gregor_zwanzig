# Context: #1467 S2 AG6 — Pausierte und archivierte Ortsvergleiche schweigen

## Request Summary

PO-Vorgabe (in Spec `rework_1467_s2_aenderungsalarm.md` §AG6 wörtlich zitiert): *„Pausierte und
archivierte Ortsvergleiche dürfen grundsätzlich nichts senden. Sie sind ja pausiert beziehungsweise
archiviert. Sie sollen sich so verhalten, als würde es sie im System nicht geben."*
Letzter offener Arbeitsgang der Scheibe S2. Spec + ACs (AC-20 bis AC-23) sind seit 2026-08-03
PO-freigegeben.

## Ist-Stand (gemessen 2026-08-04, HEAD `3acc8515`)

### Der Riegel fehlt in zwei von drei Ortsvergleich-Alarmpfaden

| Pfad | Datei | archiviert schweigt? | pausiert schweigt? |
|---|---|---|---|
| Änderungsalarm (Δ Vorhersage) | `src/services/compare_alert.py` | **nein** | **nein** |
| Nowcast (Radar-Onset) | `src/services/compare_radar_alert.py` | **nein** | **nein** |
| Amtliche Warnung | `src/services/compare_official_alert.py:88-93` | ja (#1233) | ja (#1233) |
| Trip (Vergleichsmaßstab) | `trip_alert.py` | ja — implizit, `load_all_trips` filtert `archived_at` (`loader.py:1334`) | nein (außerhalb dieser Scheibe) |

Verifiziert: kein Treffer für `archived_at`/`schedule` in `compare_alert.py` und
`compare_radar_alert.py`.

### 🔴 Belegter Schadensfall in echten Produktivdaten

`data/users/henning/alert_log.json` enthält **genau einen** Ortsvergleich-Alarm:

```
entity_id   cp-eb6ba0b239d90e37
entity_type compare
sent_at     2026-08-04T04:00:26Z
reason      forecast_change   (Böen, MODERATE)
channels    ["email"]
```

Dasselbe Preset trägt `paused_at = 2026-07-31T20:08:12`. **Der Alarm ging vier Tage nach dem
Pausieren raus.** Das ist der einzige Vergleichs-Alarm der Historie — und er hätte nicht gesendet
werden dürfen. AG6 ist damit kein hypothetisches Aufräumen.

### 🔴 Bestandslage: ALLE fünf realen Vergleiche sind „pausiert"

Gemessen über `sudo -u claude-gregor` in `data/users/*/briefings/*.json` (`kind="vergleich"`):

| Nutzer | Preset | `schedule` | `paused_at` | `archived_at` |
|---|---|---|---|---|
| henning | heimat | `manual` | — | — |
| henning | zillertal- | `manual` | — | — |
| henning | zillertal | `manual` | — | — |
| henning | mallorca- | `manual` | — | — |
| henning | cp-eb6ba0b… | `manual` | 2026-07-31 | — |

Vier davon tragen `schedule="manual"` **ohne** `paused_at` — sie wurden nie über den Pause-Knopf
gestoppt, sondern haben schlicht keinen Zeitplan.

**Entscheidend:** Die Oberfläche wertet beides gleich. `deriveStatusFromPreset`
(`frontend/src/lib/components/compare/subscriptionHelpers.ts:83-88`):

```ts
if (!p.name || p.location_ids.length === 0) return 'draft';
if (p.paused_at) return 'paused';
if (p.schedule === 'manual') return 'paused';
return 'active';
```

⇒ Alle fünf Vergleiche stehen in der Liste als **„pausiert"**. Der Riegel ist damit deckungsgleich
mit dem, was der Nutzer sieht — aber die Folge ist: **nach dem Deploy sendet zunächst kein einziger
Ortsvergleich mehr einen Alarm**, bis ein Vergleich auf einen Zeitplan gestellt wird. Gewollte
Richtung (weniger Meldungen), aber sofort und vollständig sichtbar. Muss dem PO vor der Umsetzung
gesagt sein.

### 🔴 DRY: die Prüfung existiert bereits DREIMAL (Reuse-Befund vor der AC-Freigabe, #1481 Baustein B)

| Stelle | Prüft | Zweck |
|---|---|---|
| `compare_slot_scheduler.py:76-79` | `schedule=="manual"`, `archived_at` | Briefing-Fälligkeit |
| `scheduler_dispatch_service.py:66-68` | `archived_at`, `paused_at` **oder** `schedule=="manual"` | Auto-Pause-Schleife („schon stillgelegt?") |
| `compare_official_alert.py:88-93` | `schedule=="manual"`, `archived_at` | amtlicher Alarm |
| `subscriptionHelpers.ts:83-88` | `paused_at` **oder** `schedule=="manual"`, plus draft | Oberflächen-Status |

Drei Python-Fassungen, **keine zwei identisch**: nur die Auto-Pause-Schleife prüft `paused_at` mit.
Die Oberfläche ist die einzige vollständige Ableitung — und damit die verbindliche **Leser-Vorlage**
für den neuen Baustein.

Konsequenz für den Zuschnitt: Der geplante `is_silenced(preset)` darf nicht als **vierte** Fassung
entstehen. Er muss mindestens `compare_official_alert.py` ablösen (so in der Spec vorgesehen) und
die Frage stellen, ob `compare_slot_scheduler.py` mitzieht (dort wäre `paused_at` neu — Wirkung in
der Praxis gleich, weil `end_date` dort separat geprüft wird).

### AC-20-Präzisierung (materiell)

Spec AC-20 nennt nur `schedule: "manual"`. Die Oberflächen-Vorlage verknüpft **ODER**. Beide
Schreibpfade setzen heute zwar beides gleichzeitig
(Go `MaterializePausedAt`, belegt durch `internal/router/briefing_subscription_test.go:625`;
Python-Auto-Pause `scheduler_dispatch_service.py:251-255`), aber vier von fünf Bestandsdatensätzen
tragen nur `schedule` — der Altbestand ist bereits uneinheitlich. Der Baustein prüft daher
**`paused_at` ODER `schedule=="manual"` ODER `archived_at`**, deckungsgleich mit der Oberfläche.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/compare_alert_guard.py` | **NEU** — `is_silenced(preset: dict) -> bool` |
| `src/services/compare_alert.py:104` | Riegel im Preset-Schleifenkopf, nach der `preset_id`/`location_ids`-Prüfung, **vor** Sperrzeit/Tageslimit/Wetterabruf |
| `src/services/compare_radar_alert.py:82-86` | Riegel in `_check_one_preset`, vor `radar_alert_enabled`-Prüfung |
| `src/services/compare_official_alert.py:88-93` | Inline-Prüfung → Delegation, verhaltensgleich |
| `src/services/compare_slot_scheduler.py:76-79` | Kandidat für Mitziehen (Briefing-Fälligkeit) |
| `src/services/scheduler_dispatch_service.py:66-68` | Vierte Fassung, andere Semantik („schon pausiert?") — bewusst prüfen, nicht blind ersetzen |
| `frontend/…/subscriptionHelpers.ts:83-88` | Leser-Vorlage (Oberflächen-Status) |
| `src/app/models.py:959-963` | `archived_at` / `paused_at` auf `ComparePreset` |

## Bestandstests, die durch den Riegel rot werden

Vier Alarm-Tests bauen Fixtures mit `schedule: "manual"` und erwarten einen Alarm:

| Test | Zeile | Prüft eigentlich |
|---|---|---|
| `tests/tdd/test_compare_alert_quiet_hours_precedes_fetch.py` | 142 | Ruhezeit vor Abruf (AG2) |
| `tests/tdd/test_compare_alert_metric_gating.py` | 110 | Metrik-Gating (#1170) |
| `tests/tdd/test_compare_radar_alert.py` | 88 | Nowcast-Auslösung |
| `tests/tdd/test_compare_preset_send.py` | 63 | Versandpfad (vermutlich nicht betroffen — Handversand) |

Alle drei betroffenen prüfen eine **andere** Zusicherung, die weiterhin gilt ⇒ Fixture auf einen
aktiven Zeitplan korrigieren, **nicht** den Test löschen und **nicht** den Riegel weichspülen.
Das ist Pflichtarbeit dieser Scheibe, kein Nebenbefund.

## Existing Patterns

- **Riegel-Vorbild:** `compare_official_alert.py:84-93` (#1233) — früher Guard im Schleifenkopf,
  `return False`, kein Log-Rauschen.
- **Fail-soft je Preset:** ein kaputtes Preset darf den Lauf für die übrigen nicht abreißen
  (AG2/F001, `compare_alert.py:189-191`; `compare_slot_scheduler.py:86-94`). `is_silenced` ist eine
  reine Funktion über `.get()`-Zugriffe und kann strukturell nicht werfen — das ist die
  Absicherung, nicht ein zusätzliches try/except.
- **Geteilter Baustein statt Zweitfassung:** AG1 (`compare_alert_channels.py`), AG5
  (`alert_briefing_anchor.py`) — beide als eigenes Modul mit reiner Funktion, Alt-Stellen als dünne
  Delegation. Verlustfreiheit wurde dort über **Verdrahtungstests** belegt (Resolver-Symbol im
  verbrauchenden Modul patchen → baut eine Stelle wieder eigene Logik, wird der Test rot).

## Dependencies

- **Upstream:** `load_compare_presets` (`app/loader.py`), Preset-Felder `schedule`/`paused_at`/
  `archived_at` (Go-Store schreibt sie, `NormalizeComparePreset`).
- **Downstream:** drei Alarm-Dienste; Scheduler-Jobs `compare-alert-checks`,
  `compare-radar-alert-checks`, `compare-official-alert-checks` (15-Minuten-Takt).
- **Nicht betroffen:** Trip-Pfad, Handversand (`send_compare_preset`), Briefing-Renderer,
  Mail-Templates. **Keine** Renderer-Datei wird angefasst ⇒ Renderer-Mail-Gate #811 greift nicht.

## Existing Specs

- `docs/specs/modules/rework_1467_s2_aenderungsalarm.md` — **freigegeben** (v1.1, PO-„go"
  2026-08-03), §AG6 + AC-20…AC-23, Testplan nennt
  `tests/tdd/test_compare_alert_paused_archived_silent.py`.
- `docs/specs/modules/rework_1467_s1_alarm_kennung.md` — S1, `entity_id`/`entity_type`.
- ADR-0021 (Engine-Extraktion), ADR-0043 (Relevanzfilter) — keine neue ADR nötig.

## Risks & Considerations

| | Risiko | Gegenmaßnahme |
|---|---|---|
| **R1** | Riegel greift zu breit ⇒ ein **aktiver** Vergleich schweigt still. Der gefährlichste Fehler des Epics | AC-23 (aktives Preset desselben Nutzers meldet weiter) ist Pflicht-Gegenprobe, in derselben Fixture |
| **R2** | Vierte Fassung derselben Prüfung statt Ablösung (#1481, Anti-Muster #1170) | `is_silenced` löst `compare_official_alert.py` ab; Verdrahtungstest je Aufrufer |
| **R3** | AC-20 nur auf `schedule` gelesen ⇒ ein per Pause-Knopf gestopptes Preset ohne `schedule`-Umstellung sendet weiter | Baustein prüft ODER-verknüpft, deckungsgleich mit `subscriptionHelpers.ts` |
| **R4** | Vier Bestandstests werden rot; Versuchung, den Riegel abzuschwächen statt die Fixtures zu korrigieren | Fixtures sind Teil des Auftrags, in der Spec benannt |
| **R5** | Alle realen Vergleiche schweigen ab dem Deploy | PO vor der Umsetzung informieren (siehe oben); nicht technisch abfangen |

**Nebeneffekt, erwünscht:** Der Riegel sitzt vor dem Wetterabruf ⇒ pausierte Vergleiche verbrauchen
kein Open-Meteo-Kontingent mehr (#1329).

## Nicht-Ziele

- Trip-Pfad bekommt **keinen** `paused_at`-Riegel (eigene Frage, außerhalb S2).
- `draft`-Zustand (kein Name / keine Orte) braucht keine Behandlung — leere `location_ids` brechen
  in allen drei Pfaden bereits ab.
- Keine Datenmigration, keine Feldänderung, keine Go-/Frontend-Änderung.
