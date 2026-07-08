# Context: Ortsvergleich C — Metriken im Stundenverlauf konfigurierbar (#1106)

## Request Summary
Die Stundentabelle der Compare-Mail zeigt aktuell 7 fest verdrahtete Wetter-Spalten
(Temp, Gef., Wind, Böen, Regen, Wolken, UV). Der User soll auswählen können, welche
dieser Spalten angezeigt werden — analog zum bereits existierenden Metrik-Filter der
Übersichtstabelle (#1104/#1105). Default bleibt unverändert (alle bisherigen Spalten
bzw. laut Issue-Text mindestens Temp/Wind/Wolken).

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/renderers/email/compare_html.py:79` | `_HOUR_COLUMNS` — hart codierte 8 Header (inkl. "Zeit") |
| `src/output/renderers/email/compare_html.py:284-311` | `_render_hour_row(dp)` — baut alle 7 Wert-Zellen hart aus `dp.*`-Attributen, kein Loop über Metrik-Liste |
| `src/output/renderers/email/compare_html.py:314-332` | `_render_hour_table(loc)` — Header-Loop über `_HOUR_COLUMNS`, Rows via `_render_hour_row` |
| `src/output/renderers/email/compare_html.py:335-358` | `_render_location_section(loc, index)` — ruft `_render_hour_table` ohne Config-Parameter |
| `src/output/renderers/email/compare_html.py:558-568` | `render_compare_html(...)` Signatur — `enabled_metrics` existiert bereits für Übersicht, **kein** analoges `hourly_metrics`-Arg |
| `src/output/renderers/email/compare_html.py:70-77` | `CV2_METRICS` — Vorbild-Liste (Übersicht) mit `key`/`label`/`unit`/`sev` |
| `src/output/renderers/email/compare_html.py:169-176` | `_visible_metrics(enabled_metrics)` — Vorbild-Resolver: `None`=alle, sonst Filter, `warn`-Zeile immer sichtbar |
| `src/output/renderers/comparison.py:112-149` | `render_compare_email()` — reicht `enabled_metrics` von Aufrufer an `render_compare_html` durch (Z.143) |
| `src/services/scheduler_dispatch_service.py:198-281` | `send_one_compare_preset` — realer Versandpfad; liest `display_config = preset.get("display_config") or {}` (Z.252), `resolve_enabled_metrics(display_config.get("active_metrics"))` (Z.270) |
| `src/output/renderers/compare_metric_ids.py:23-40` | `resolve_enabled_metrics()` — Vorbild-Resolver Frontend-ID → Renderer-ID, inkl. Defensiv-Handling (None/leer/nicht-Liste) |
| `src/services/compare_subscription.py:119-126` | zweiter Aufrufer, verdrahtet `enabled_metrics` bewusst **nicht** (Kommentar Z.102-106) |
| `src/app/models.py:87-138` | `ForecastDataPoint` — Quelle der Stunden-Attribute: `t2m_c` (93), `wind10m_kmh` (94), `gust_kmh` (96), `precip_1h_mm` (98), `cloud_total_pct` (99), `uv_index` (107), `wind_chill_c` (117) |
| `frontend/src/lib/components/compare/compareMetricDefs.ts:42-45` | `ALL_METRICS` — Frontend-Metrik-Katalog (Übersicht) |
| `frontend/src/lib/components/compare/steps/Step3Idealwerte.svelte:26-116` | Checkbox-UI für `activeMetricKeys` (Übersicht-Metriken) |
| `frontend/src/lib/components/compare/steps/Step5Versand.svelte:181-198` | "Stundenverlauf"-Section (Issue #1104, `top_n`) — naheliegender Ort für neue Metrik-Checkboxen |
| `frontend/src/lib/components/compare/compareEditorSave.ts:55-66` | Save-Payload-Mapping: `edits.activeMetricKeys` → `displayConfig.active_metrics`, `edits.topN` → `displayConfig.top_n` |
| `frontend/src/lib/types.ts:495` | Kommentar zu `display_config`-Struktur (dict, nicht typisiert) |
| `.claude/hooks/email_spec_validator.py:126-127,249-254` | `_HOUR_COLUMNS_V2` — **exakter Vertrag**, prüft `header_cols != _HOUR_COLUMNS_V2`. Muss bei Parametrisierung dynamisch werden |
| `internal/model/compare_preset.go:33` | `DisplayConfig map[string]interface{}` — Go-Persistenz, kein Struct-Feld nötig (bleibt dict-artig) |

## Existing Patterns

- **Resolver-Pattern (#1104):** Frontend liefert Liste kanonischer IDs (`display_config.active_metrics`) →
  `resolve_enabled_metrics()` mappt Frontend-Vokabular auf Renderer-Vokabular → `set[str] | None` →
  `_visible_metrics()` filtert die Renderer-seitige Metrik-Liste, `None` = Rückwärtskompatibilität (alle sichtbar).
  Dieses Pattern soll 1:1 für `hourly_metrics` wiederholt werden, mit einer neuen Renderer-seitigen
  Konstante analog `CV2_METRICS`, aber für die 7 Stundenspalten (ohne "Zeit", die ist Pflicht-Spalte).
- **`display_config` bleibt untypisiertes dict** — kein neues Pydantic/Dataclass-Modell nötig, nur ein
  weiterer Key (`hourly_metrics`) neben `active_metrics`/`top_n`.
- **Defensives Resolving:** `resolve_enabled_metrics()` wirft nie, fällt bei ungültigem/leerem/Nicht-Listen-Input
  auf `None` zurück — gleiches Verhalten für den neuen Resolver erwartet.
- **"Zeit" ist keine wählbare Metrik** — im Gegensatz zur Übersicht (wo "warn" immer sichtbar ist), muss die
  Zeitspalte immer erste Spalte bleiben, unabhängig von der Metrik-Auswahl.

## Dependencies

- **Upstream (was unser Code nutzt):** `ForecastDataPoint`-Attribute (`src/app/models.py`), bestehendes
  `resolve_enabled_metrics`-Pattern aus #1104 als Vorbild (kein Code-Reuse, da anderes Vokabular).
- **Downstream (was von unserem Code abhängt):**
  - `.claude/hooks/email_spec_validator.py` — MUSS den harten `_HOUR_COLUMNS_V2`-Vertrag lockern/parametrisieren,
    sonst schlägt jede Mail mit gefiltertem Stundenverlauf am Gate fehl (**Blocker**, nicht optional).
  - `renderer_mail_gate.py` — keine Treffer zu `_HOUR_COLUMNS`, vermutlich unberührt.
  - Frontend Compare-Editor Save/Load-Pfad (`compareEditorSave.ts`) — neues Feld muss dort mit-serialisiert werden.
  - `docs/specs/modules/issue_1108_email_spec_validator_v2.md` — Validator-v2-Vertrag-Doku, muss ergänzt werden.

## Existing Specs

- `docs/specs/modules/issue_1104_compare_config_foundation.md` — Fundament A: Wiring/Resolver/Frontend-Kette,
  direktes Vorbild-Pattern für dieses Slice.
- `docs/specs/modules/issue_1108_email_spec_validator_v2.md` + `docs/context/fix-1108-validator-v2.md` —
  Validator-v2-Vertrag (inkl. `_HOUR_COLUMNS_V2`).
- `docs/specs/modules/issue_1110_compare_mail_v2.md` + `docs/context/feat-1110-compare-mail-v2.md` — v2-Layout,
  Quelle des aktuellen Renderer-Docstrings.
- `docs/context/fix-1094-compare-config.md` — Ursprungsanalyse "vier inkompatible Metrik-Vokabulare"
  (Katalog / CE_PROFILES / Frontend-active_metrics / Step4Layout).
- Keine Dateien zu #1105/#1106/#1107 vorhanden — Geschwister-Issues noch nicht bearbeitet.

## Risks & Considerations

- **Validator-Vertrag ist der Hauptblocker:** `email_spec_validator.py:249-254` vergleicht Header 1:1 gegen
  eine feste Liste. Ohne Anpassung ist "E2E bestanden" strukturell unerreichbar, sobald eine Spalte fehlt.
  Analog zur Lehre aus #1108 ("Gate-Test-Scope") muss der Validator config-bewusst werden, nicht der Code
  am Gate vorbei.
- **Vokabular-Mapping nötig:** Frontend-Metrik-Namen (z.B. aus `compareMetricDefs.ts`) und Renderer-Spalten
  (`Temp`, `Gef.`, `Wind`, `Böen`, `Regen`, `Wolken`, `UV`) sind nicht deckungsgleich mit den Übersicht-IDs
  (`temp_max`, `wind_max`, `cloud_avg`, `uv_max` — Aggregate, nicht Rohwerte). Braucht eigene ID-Liste,
  kein Wiederverwenden von `FRONTEND_TO_RENDERER_METRIC_ID`.
- **"Zeit" immer Pflichtspalte**, sonst ergibt die Tabelle keinen Sinn (Zeitachse).
- **Default-Frage:** Issue-Text sagt "Default weiterhin Temp/Wind/Wolken" — das widerspricht dem Status quo
  (7 Spalten sichtbar). Zu klären in der Spec-Phase, ob Default wirklich nur 3 Spalten sein soll oder
  "alle bisherigen" gemeint ist (ambig formuliert, PO-Klärung in Spec-Freigabe nötig).
- **Zwei Aufrufer:** `scheduler_dispatch_service.py` verdrahtet `display_config`, `compare_subscription.py`
  bewusst nicht — muss geprüft werden, ob `hourly_metrics` in beiden Pfaden ankommen soll oder nur im
  Preset-Versandpfad (analog #1104-Scope).
- **Kein Mock-Test möglich** (Projektregel) — TDD-RED muss echte zugestellte Staging-Compare-Mail nutzen,
  Marker `X-GZ-Mail-Type: compare`, Validator `email_spec_validator.py`.

## Analysis

### Type
Feature (Konfigurierbarkeit-Erweiterung, Teil C von #1094)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/email/compare_html.py` | MODIFY | Neue `HOUR_METRICS`-Konstante (Rohwert-Vokabular) + `_visible_hour_metrics()`-Resolver; `_render_hour_row`/`_render_hour_table`/`_render_location_section`/`render_compare_html` auf Loop statt Hardcoding umbauen, neuer Parameter `hourly_metrics: set\|None`. "Zeit" bleibt fest verdrahtete erste Spalte |
| `src/output/renderers/compare_hourly_metric_ids.py` | CREATE | Neuer Resolver `resolve_hourly_metrics()` analog `compare_metric_ids.py`, eigenes `FRONTEND_TO_HOURLY_METRIC_ID`-Dict |
| `src/output/renderers/comparison.py` | MODIFY | `render_compare_email()` reicht `hourly_metrics` durch (analog `enabled_metrics`, Z.143) |
| `src/services/scheduler_dispatch_service.py` | MODIFY | `display_config.get("hourly_metrics")` lesen, resolven, durchreichen (neben Z.251-270) |
| `.claude/hooks/email_spec_validator.py` | MODIFY | `_HOUR_COLUMNS_V2`-Exaktvertrag → Teilmengen+Reihenfolge-Prüfung (Z.126-127, 249-254) |
| `docs/specs/modules/issue_1108_email_spec_validator_v2.md` | MODIFY | Validator-Vertrag-Doku ergänzen |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | MODIFY | Neues State-Feld `hourlyMetricKeys`, Load/Save analog `activeMetricKeys`/`topN` |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | MODIFY | Neues Edit-Feld `hourlyMetricKeys?: string[]` im Save-Payload-Mapping |
| `frontend/src/lib/components/compare/steps/Step5Versand.svelte` | MODIFY | Checkbox-UI unterhalb der bestehenden "Anzahl Orte"-Sektion (Z.181-198) |
| `frontend/src/lib/components/compare/compareHourlyMetricDefs.ts` | CREATE (ggf.) | Kleine Konstante mit 7 Metrik-Defs (Label = Spaltenname) für Step5-UI |
| Neue Test-Dateien (Python + ggf. Frontend) | CREATE | Resolver-Test, Renderer-Loop-Test, Save-Mapping-Test |

Go: **keine Änderung nötig** — `DisplayConfig map[string]interface{}` bleibt generisch.

### Scope Assessment
- Files: ~9-10 (5 Python + 4 Frontend + 1 Doku, exkl. neuer Tests)
- Estimated LoC: ~+300/-0 bis +350/-30 (Python ~180-230, Frontend ~90-110)
- Risk Level: MEDIUM (Mail-Inhalt + Validator-Gate, aber etabliertes Pattern aus #1104 als Vorbild)

### Technical Approach
Resolver-Pattern aus #1104 wiederholen, aber mit **eigenem Rohwert-Vokabular** (kein Reuse von
`FRONTEND_TO_RENDERER_METRIC_ID`, da Übersicht-Aggregate ≠ Stunden-Rohwerte). "Zeit" bleibt außerhalb
der konfigurierbaren Liste, immer erste Spalte. Validator wird von Exakt-Vertrag auf
Teilmengen-mit-Reihenfolge-Prüfung umgestellt (`[c for c in _HOUR_COLUMNS_V2 if c in header_cols] == header_cols`),
um Erosion (Fremdspalten, Umsortierung) weiterhin zu verhindern.

**Implementierungsreihenfolge:**
1. Backend-Resolver + Renderer-Loop-Umbau (compare_html.py) — Kernstück
2. Validator parametrisieren — MUSS in derselben Spec/PR erfolgen, sonst blockt Gate jeden folgenden E2E-Test
3. `comparison.py` + `scheduler_dispatch_service.py` Durchreichen
4. Frontend State/Save/UI
5. `compare_subscription.py` — nur falls PO das explizit im Scope will (s. offene Fragen)

### Dependencies
- Upstream: `ForecastDataPoint`-Attribute, etabliertes Resolver-Pattern aus #1104
- Downstream: Validator-Gate (Blocker ohne Anpassung), Frontend Save/Load-Kette, Doku `issue_1108`

### Open Questions — GEKLÄRT (PO-Entscheidungen 2026-07-08)

- [x] **Default-Set:** Bestandsnutzer werden NICHT geschont (keine aktiven Produktiv-User, s. Memory
      `project-no-active-production-users`). Standard = **alle** wählbaren Spalten (kein Zeitdruck-Kontext:
      Ortsvergleich wird am Frühstückstisch in Ruhe gelesen, nicht unter Zeitdruck).
- [x] **`compare_subscription.py`:** Bleibt außen vor (Scope-Konsistenz mit #1104). Nutzer möchte den
      gesamten Alt-Pfad (CLI-only, kein aktiver App-Pfad) entfernen — **eigenes Follow-up-Issue**, NICHT
      Teil von #1106.
- [x] **Validator-Mindestspalten:** Ja, mindestens 1 Wert-Spalte neben "Zeit" ist Pflicht — verhindert eine
      sinnentleerte Tabelle.
- [x] **Metrik-Inventar erweitert (PO-Entscheidung, über ursprünglichen Issue-Scope hinaus):**
      - **Wolken (`cloud_total_pct`) wird ENTFERNT** — eher Aussicht- als sicherheitsrelevant.
      - **NEU: Gewitter-Risiko (`thunder_level`)** — sicherheitskritisch für exponierte Kammwege,
        aktuell im Stundenverlauf gar nicht sichtbar. Format-Vorbild: `_THUNDER_LEVEL_LABEL`/`_THUNDER_LEVEL_BG`
        in `src/output/renderers/email/html.py:1160-1161` (Werte "mittel"/"hoch", NONE nicht angezeigt).
      - **NEU: Regenwahrscheinlichkeit (`pop_pct`)** — ergänzt bestehende Regenmenge (mm) um Eintreffwahr-
        scheinlichkeit (%). Vorbild: `src/output/renderers/email/helpers.py:1192-1193`.
      - **NEU: Sicht (`visibility_m`)** — navigationsrelevant bei Nebel im Gebirge. Vorbild:
        `src/services/aggregation.py:194`, `src/output/renderers/email/helpers.py:1234-1235`.
      - **Finales wählbares Spalten-Set (9 + Pflichtspalte Zeit):** Temp, Gef., Wind, Böen, Regen, UV,
        Gewitter, Regen-Chance, Sicht. Default = alle 9.

### Scope-Erweiterung ggü. ursprünglichem Issue-Text
Der Issue-Text sprach nur von den 7 *bereits gerenderten* Spalten. PO hat den Scope in der Analyse-Phase
bewusst erweitert: 3 neue Datenpunkte (`thunder_level`, `pop_pct`, `visibility_m`) kommen hinzu, `cloud_total_pct`
entfällt. Das bedeutet zusätzliche Formatierungs-/Severity-Logik für 3 neue Spaltentypen (kategorial/Prozent/Meter)
statt reinem Refactoring bestehender Zellen. Scope-Schätzung (Plan-Agent, s.o.) muss um diesen Mehraufwand
korrigiert werden — wird in der Spec-Phase neu beziffert.

### Follow-up-Issue
`compare_subscription.py` (Alt-Pfad, CLI-only) wird NICHT in #1106 entfernt — dafür angelegt:
**#1131** "Alt-Pfad compare_subscription.py entfernen".
