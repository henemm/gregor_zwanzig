# Context: feat-1444-s2-warnen-schalter

Issue **#1444** Scheibe 2 · Vorgänger: Scheibe 1 (`4267c90d` + `debfc672`, auf `main`,
Staging VERIFIED, Prod-Deploy ausstehend).

## Request Summary

Der Reiter *Wertebereiche* bekommt den Schalter „Warnen" je Wettergröße zurück (PO-Entscheid
2026-08-01) und sagt wieder die Wahrheit über seine Wirkung. Seit Scheibe 1 löst ein gerissener
Wertebereich tatsächlich eine Sofort-Meldung aus — der Reiter behauptet aber weiterhin das
Gegenteil, und der Nutzer hat kein Bedienelement, um die Meldung je Größe an- oder abzuschalten.

## Ausgangslage — drei Ebenen, die auseinanderlaufen

| Ebene | Stand heute | Quelle |
|---|---|---|
| **Backend** | `corridor.notify` wirkt seit S1 — einzige Leser: `trip_alert.py:186,377,473` (+ Loader-Roundtrip `loader.py:1515`). **Nur Trip**, `compare_alert.py` liest `notify` nicht. | eigene Messung 2026-08-01 |
| **Speicherweg** | `buildCorridorSavePayload()` schreibt `notify` schon durch und lässt `metric_alert_levels` unangetastet (reiner Pass-Through, #1371-Fix). **Kein Umbau nötig.** | `corridorEditorState.ts:357-369` |
| **Oberfläche** | Kein „Warnen"-Schalter (seit #1371 S6 entfernt), Text sagt ausdrücklich „hier gibt es keine Sofort-Meldung", ein Test **verbietet** das Gegenteil. | `CorridorEditor.svelte:296-330`, `corridorEditorCopy.test.ts` |

Neu angelegte Trip-Zeilen stehen fest auf `notify: true` (`ROUTE_CTX_DEFAULTS`,
`corridorEditorState.ts:56`). Praktisch heißt das: **jeder Wertebereich im Trip meldet seit S1, und
niemand kann das abstellen, außer den Bereich zu löschen.** Genau diese Lücke schließt die Scheibe.

## Warum der Schalter überhaupt verschwand (und was daraus folgt)

`e5cec9ce` — *fix(#1371 S6): Das „Warnen"-Häkchen verstellt die Alarme nicht mehr heimlich*:

> Es saß neben einer Von/Bis-Grenze, warnte aber nicht beim Verlassen dieser Grenze — es schaltete
> den davon unabhängigen Abweichungs-Wächter für diese Wettergröße ein oder aus. […] Wer eine
> Grenze verstellte oder eine Zeile löschte, verstellte damit unbemerkt seine Alarme.

**Der Schalter war nicht als Bedienelement falsch, sondern weil er das Falsche steuerte.** Seit S1
hat `corridor.notify` eine eigene, echte Bedeutung. Die harte Invariante für diese Scheibe:

> Der Schalter schreibt **ausschließlich** `corridors[].notify`. `metric_alert_levels` (#1371) und
> `active_metrics` (#1311) bleiben reiner Pass-Through. Wer das aufweicht, baut #1371 nach.

Die bestehenden Tests dazu (`corridorEditorState.test.ts`, Zeilen ~300–340) müssen grün bleiben und
sind der Regressionsschutz.

## ⚠️ Befund: Gewitter löst gar keinen Schwellen-Alarm aus

`corridor_threshold.py:59` schlägt `corridor.metric` in `_ALERT_METRIC_TO_SUMMARY_FIELD`
(`weather_change_detection.py`) nach — Namensraum `AlertMetric`. Der Gewitter-Korridor heißt aber
seit der #1425-S2b-Migration `thunder_level_max` (Katalog-Namensraum). Gemessen:

```
'thunder_level'      -> 'thunder_level_max'   ✅
'thunder_level_max'  -> None                  ❌ übersprungen
'sunny_hours_h'      -> None                  ❌
'snow_new_sum_cm'    -> None                  ❌
```

Auswertbar sind heute **10** Größen (`wind_gust`, `precipitation_sum`, `temperature_min/max`,
`thunder_level`, `freezing_level`, `snow_line`, `fresh_snow`, `cape`, `visibility`) — der
Trip-Wertebereichs-Pool umfasst seit #1425 aber **23**.

**Folge:** AC-4 des Issues („nachgewiesen mindestens für Gewitter und Regen") ist nicht erfüllt.
Scheibe 1 wurde ausschließlich mit `temperature_max` verifiziert. Ein „Warnen"-Schalter auf der
Gewitter-Zeile wäre heute exakt das leere Versprechen, das #1425 S2c beseitigt hat.

## ⚠️ `alarmCapable` erreicht den Trip-Kontext nicht

> **Überholt durch die Analyse weiter unten.** Der Abschnitt bleibt als Fundprotokoll stehen. Die
> Analyse zeigt, dass `alarmCapable` die falsche Frage beantwortet und für den Schalter gar nicht
> gebraucht wird — die Durchreiche entfällt ersatzlos.

Das zentrale Register liefert `alarmCapable` je Katalog-Eintrag aus (#1435 E1a-1, `98d1a1f6`,
über `/api/compare/metrics`). `buildCompareMetricDefs()` übernimmt es
(`compareMetricCatalogLoader.ts:71`) — `buildRouteMetricDefsFromCatalog()` (ebd. :138-165)
**nicht**. Im Trip bleibt `alarmCapable` damit `undefined` und wird laut
`corridorEditorState.ts:80-81` als `true` behandelt: Der Schalter erschiene auf allen 23 Zeilen
bedienbar, auch auf den 13 wirkungslosen.

Das Muster für den Gegenfall existierte im alten Code bereits und ist wiederverwendbar:

```html
<button class="ce-effect notify disabled" disabled
        title="nur Markieren – für diese Metrik gibt es keinen Alarm-Abgleich">Warnen</button>
```

## Related Files

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte` | Desktop: Text (:296-308), Legende (:325-330), Effekt-Schalter (:413-421), Zähler (:438), CSS `.ce-effect.notify.on` (:489) **ist noch da** |
| `…/CorridorEditorMobile.svelte` | Handy: Text (:291-292), Legende (:304-306), Effekt-Schalter (:384-392), Zähler (:414), CSS `.cem-effect.notify.on` (:480) **ist noch da** |
| `…/corridorEditorState.ts` | `ROUTE_CTX_DEFAULTS` (:56), `CorridorRowState.alarmCapable` (:81), `buildCorridorSavePayload` (:357) — Schreibweg ist bereits richtig |
| `…/compareMetricCatalogLoader.ts` | `buildRouteMetricDefsFromCatalog` (:131) — hier fehlt die `alarmCapable`-Durchreiche |
| `…/__tests__/corridorEditorCopy.test.ts` | Wächter, der die Formulierungen heute **verbietet** — muss kontextabhängig umgedreht werden |
| `src/services/corridor_threshold.py` | Schwellen-Auswertung; `_ALERT_METRIC_TO_SUMMARY_FIELD.get()` (:59) ist die Stelle des Gewitter-Befunds |
| `src/services/trip_alert.py` | `:186,:377,:473` — die drei `notify`-Filter |
| `src/app/metric_catalog.py` | zentrales Register, `alert_metric_for()` — sanktionierte Quelle statt neuer Satellitenliste |

## Existing Specs

- `docs/specs/modules/feat_1444_s1_schwellen_alarm.md` — Scheibe 1
- `docs/specs/modules/fix_1371_warnen_haekchen_raus.md` — warum der Schalter ging (6 ACs)
- `docs/specs/fast/fix-1425-s2c-banner-text.md` — der heutige Text + sein Wächter
- `docs/adr/0040-schwellen-alarm-additiver-alarm-typ.md` — additiver zweiter Alarm-Typ
- `docs/adr/0013-*` — Auflage „kein erfundenes vorher" im Alarm-Render

## Existing Patterns

- **Kontext-Zweig statt zweitem Bauteil:** Der geteilte Editor verzweigt bereits auf
  `context === 'vergleich'` für Text/Überschrift. Ein zweiter Zweig für den Schalter ist das
  sanktionierte Muster (Trip/Compare-Teilungs-Invariante, CLAUDE.md) — **kein** neues Compare-Bauteil.
- **Deaktivierter Schalter statt fehlendem Schalter** bei fehlender Wirkung (siehe oben).
- **Doc-Compliance-Test** für reine Anzeigetexte (`// doc-compliance-test`), Markup ohne
  `<script>`/`<style>`/HTML-Kommentare.

## Dependencies

- **Upstream:** `/api/compare/metrics` (Register, liefert `alarmCapable`/`alertMetric`);
  `SegmentWeatherSummary` (32 Felder) als Wertequelle des Wächters
- **Downstream:** `trip_alert.py` → Alarm-Render → E-Mail/Telegram/SMS; Compare-Editor teilt
  dieselben Bauteile und darf sich **nicht** mitverändern

## Risks & Considerations

1. **#1371 nicht nachbauen** — der Schalter darf `metric_alert_levels` nicht anfassen. Höchstes
   Risiko der Scheibe.
2. **Compare darf nicht mitwandern** — `notify` hat dort keinen Leser; Text und Legende bleiben
   im Vergleichs-Kontext wörtlich unverändert (heutiger AC-4 des Copy-Wächters).
3. **Leeres Versprechen vermeiden** — Schalter nur bedienbar, wo der Wächter wirklich auswertet.
   Sonst ist der #1425-Fehler zurück, nur andersherum.
4. **Umfang/LoC:** Backend-Namensraum + Frontend-Schalter + Text + Wächter-Umkehr liegen zusammen
   nahe an der 250-Zeilen-Grenze. Zuschnitt in zwei Scheiben (erst Backend ehrlich, dann Oberfläche)
   ist in der Analyse zu prüfen.
5. **Fremder roter Test:** `tests/test_success_status_guard.py` ist seit `4267c90d` rot — reine
   Zeilennummern-Drift in `notification_service.py`/`trip_alert.py` (13 Einträge). Kern-Schicht muss
   grün sein; an denselben Dateien arbeitet parallel die #1448-S3-Sitzung. Nachziehen erst kurz vor
   dem Commit, sonst sofort wieder veraltet. Die Liste darf laut ihrem AC-3 **nur schrumpfen**.
6. **Parallele Sitzungen:** `fix-1448-s3-telegram-openmeteo`, `feat-1406b-stundenverlauf-katalog`,
   `feat-1445-s3-oesterreich-feed` laufen gleichzeitig. `trip_alert.py` ist geteilte Fläche.

---

# Analysis

## Type

Feature (mit einem in Scheibe 1 entstandenen Defekt als Voraussetzung).

## Der Kern: zwei Namensräume, ein Wächter

Eine Korridor-Metrik (`corridor.metric`) kommt in **zwei** Namensräumen vor:

| Herkunft | Beispielwerte | Namensraum |
|---|---|---|
| Die **5** fest verdrahteten `ROUTE_METRIC_DEFS` | `wind_gust`, `precipitation_sum`, `temperature_min/max`, `snow_line` | `AlertMetric` |
| Die **18** Katalog-Zusätze (`buildRouteMetricDefsFromCatalog`, seit #1425) | `thunder_level_max`, `sunny_hours_h`, `cape_max_jkg`, … | Katalog-`key` |

> Korrektur (unabhängige Zweitprüfung): Es sind **5**, nicht 6 fest verdrahtete Einträge —
> Gewitter wurde mit #1425 S2b aus `ROUTE_METRIC_DEFS` entfernt und kommt seither aus dem
> Katalog (`corridorEditorState.ts:45-50`). 5 + 18 = 23 Pool-Zeilen.

**Warum Namensraum 1 heute funktioniert:** `AlertMetric(str, Enum)` erbt `str.__hash__` — ein
reiner String trifft denselben Dict-Eintrag wie der Enum-Member. Namensraum 2 schlägt deshalb
**strukturell** fehl, nicht zufällig: diese Schlüssel sind nie AlertMetric-Werte.

`corridor_threshold.py:59` **und** `alert/project.py:128` schlagen beide ausschließlich im
`AlertMetric`-Namensraum nach. Alles aus dem zweiten Namensraum fällt durch — im Wächter still
(`continue`), in der Projektion mit gefangener Ausnahme und Log-Zeile. **Gemessen:**
`_ALERT_METRIC_TO_SUMMARY_FIELD.get('thunder_level_max')` → `None`.

## Das Register kann die Auflösung — es wird nur nicht gefragt

`src/app/metric_catalog.py` führt je Größe `summary_fields` als Paar-Tabelle
(Auswertung → Feld auf `SegmentWeatherSummary`), und `compare_metric_catalog.py` bindet jeden
Katalog-`key` an genau ein Paar (`metric_id`, `aggregation`). Damit ist

```
key → (metric_id, aggregation) → summary_fields[aggregation] → Feld auf SegmentWeatherSummary
```

**eindeutig und vollständig** — für alle 26 Katalog-Einträge gemessen. Der Weg über die
`AlertMetric`-Enum bleibt für die 6 alten Kennungen bestehen und wird nicht angefasst.

`alert/project.py:104-140` löst bereits über das **Summary-Feld** auf (F001-Fix aus S1) — die
Erweiterung passt dort ohne Umbau an: Sie liefert nur ein Feld mehr Fälle in dieselbe Funktion.

## ⚠️ Korrektur an der Ticket-Skizze: `alarm_capable` ist die falsche Frage

Das Ticket schlägt vor, die Alarmfähigkeit aus dem Register-Feld `alarm_capable` zu nehmen.
Gemessen am tatsächlichen Katalog beantwortet dieses Feld eine **andere** Frage:

- `alarm_capable` = „hat eine Alarm-Identität für den **Änderungs-Wächter**".
- Beispiel `wind_max_kmh`: `alarmCapable: true`, aber `alertMetric: wind_change` — eine
  **Änderungsrate**, kein absoluter Schwellwert. Als Schwellen-Alarm wäre das sinnlos.
- Umgekehrt `sunny_hours_h`, `snow_depth_cm`, `uv_index_max`, `pop_max_pct`: `alarmCapable: false`,
  obwohl ein Zahlenwert je Etappe vorliegt und „unter 3 Sonnenstunden" ein völlig sinnvoller
  Wertebereich ist.

**Die richtige Frage für einen Schwellen-Alarm lautet: „Gibt es für diese Größe einen Zahlenwert je
Etappe?"** — und die Antwort steht in `summary_fields`. Das deckt **25 von 26** Katalog-Einträgen;
einziger Ausfall ist `precip_type_dominant` (Aufzählung ohne Ordinalskala, in S1 bereits bewusst
ausgeschlossen).

Das passt zu ADR-0040: Der Schwellen-Alarm ist ein **additiver, eigener** Alarm-Typ und nicht an
die Identitäten des Delta-Wächters gebunden.

**Produktfolge:** Der Schalter „Warnen" ist auf **allen 23** Pool-Zeilen bedienbar. Es gibt keine
Grauzone „Schalter da, aber wirkungslos" — und damit auch keinen Bedarf für einen deaktivierten
Zustand mit Erklär-Tooltip. Einfachere Oberfläche als im ersten Entwurf angenommen.

**Daraus folgt ausdrücklich: kein neues Capability-Feld.** Weil jede Pool-Zeile schwellenfähig ist,
braucht Scheibe 2b weder ein zusätzliches Registerfeld noch eine Endpoint-Erweiterung noch eine
Durchreiche durch `buildRouteMetricDefsFromCatalog`. Das bestehende `alarmCapable` bleibt
unangetastet — es beantwortet die Änderungs-Wächter-Frage und ist per
`test_alert_metric_identity_delivery.py` auf 10 Schlüssel festgenagelt. Der naheliegende Fehler
wäre, den Schalter an `alarmCapable` zu hängen; dann bekäme z.B. die Wind-Zeile
(`wind_max_kmh` → `wind_change`) einen bedienbaren, aber wirkungslosen Schalter — exakt der
#1425-Fehlertyp, den diese Arbeit beseitigt.

### Die fertige Register-Funktion

`app.metric_catalog.summary_field_for(metric_id, aggregation)` (`src/app/metric_catalog.py:538-549`)
liefert genau den gesuchten Feldnamen und gibt für `selectable=False` bewusst `None` zurück
(`confidence` nach ADR-0005/#710, `temperature_cold`). Auflösung für Namensraum 2 damit:

```
key → COMPARE_METRIC_CATALOG-Eintrag (trägt metric_id + aggregation)
    → summary_field_for(metric_id, aggregation)
```

**`alert_metric_for()` ist hier verboten** — das ist die Funktion mit der Mehrdeutigkeit, die in
Scheibe 1 den CRITICAL verursacht hat. Sie betrifft nur die Rückwärtsrichtung
(Katalog-ID → AlertMetric); `summary_field_for` berührt die Stelle nicht.

Die beiden Namensräume sind **kollisionsfrei** (kein Katalog-Schlüssel ist zugleich ein
AlertMetric-Wert) — ein Rückfall-Nachschlag ist deshalb sicher. Ein Drift-Wächter im Test soll das
festhalten, damit ein künftiger Katalog-Eintrag es nicht still bricht.

## Affected Files

**Scheibe 2a — Backend (der Wächter erkennt, was es gibt)**

| Datei | Art | Beschreibung |
|---|---|---|
| `src/services/corridor_threshold.py` | MODIFY | Auflösung `corridor.metric` → Summary-Feld über das Register statt nur über `_ALERT_METRIC_TO_SUMMARY_FIELD` |
| `src/output/renderers/alert/project.py` | MODIFY | `_resolve_corridor_metric_id` nimmt denselben Weg (sonst wird der Treffer projiziert-verschluckt) |
| `tests/tdd/test_corridor_threshold_alert.py` | MODIFY | Nachweis Gewitter + Regen (AC-4 des Issues), plus Gegenprobe Delta-Wächter unverändert |

**Scheibe 2b — Oberfläche (Schalter + ehrlicher Text)**

| Datei | Art | Beschreibung |
|---|---|---|
| `frontend/…/CorridorEditor.svelte` | MODIFY | Schalter „Warnen" (nur `context === 'route'`), Text, Legende, Zähler |
| `frontend/…/CorridorEditorMobile.svelte` | MODIFY | dasselbe für die Handy-Ansicht |
| `frontend/…/__tests__/corridorEditorCopy.test.ts` | MODIFY | Wächter umdrehen: Tour **muss** die Wirkung nennen, Vergleich **darf nicht** |

CSS für beide Schalter (`.ce-effect.notify.on`, `.cem-effect.notify.on`) ist noch vorhanden und
wird wiederverwendet.

## Scope Assessment

| | Dateien | Produktivcode | Tests | Risiko |
|---|---|---|---|---|
| **S2a** | 3 | ~45 | ~130 | MITTEL |
| **S2b** | 3 | ~85 | ~110 | NIEDRIG |

Beide unter dem 250-Zeilen-Limit. Kein LoC-Override nötig.

## Risiken

1. **Delta-Wächter darf sich nicht ändern** (S2a, höchstes Risiko). `_ALERT_METRIC_TO_SUMMARY_FIELD`
   wird vom Änderungs-Wächter mitbenutzt. Die Auflösung wird deshalb **additiv als Rückfall**
   gebaut — bekannte `AlertMetric`-Kennungen laufen unverändert den alten Weg. Gegenprobe-Test
   Pflicht.
2. **#1371 nicht nachbauen** (S2b). Der Schalter schreibt ausschließlich `corridors[].notify`;
   `metric_alert_levels` und `active_metrics` bleiben Pass-Through. Bestehende Tests in
   `corridorEditorState.test.ts` sind der Schutz und müssen grün bleiben.
3. **Ortsvergleich darf nicht mitwandern** — `notify` hat dort keinen Leser; Text und Legende
   bleiben im Vergleichs-Kontext wörtlich unverändert.
4. **`snow_line`-Mehrdeutigkeit** — in S1 Ursache eines CRITICAL. Die Feld-basierte Auflösung ist
   genau der Fix dafür und darf nicht auf den Enum-Weg zurückfallen.
5. **Rauschen:** Auf 25 statt 10 Größen alarmfähig zu sein erhöht die Meldungsmenge. Entprellung
   liegt beim bestehenden Cooldown/Throttle (S1, Schlüsselraum `corridor:<metrik>:<etappe>`) —
   unverändert, aber in der Staging-Prüfung zu beobachten.

## Open Questions

- [ ] Keine blockierenden. Der Zuschnitt S2a → S2b und die Korrektur an `alarm_capable` gehen zur
      PO-Freigabe mit den Akzeptanzkriterien.
