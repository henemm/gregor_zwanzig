# Kontext: fix-3364-nur-morgens-abends (#3364)

## Request Summary

Bug aus #3020 R1 (Epic #3122, Spur B, go-live-pflicht). Größen mit Bericht-Flags je Metrik
(`morning_enabled` / `evening_enabled` in `display_config.metrics[]`):

- (a) `enabled: false, morning_enabled: true` → Reiter Wetter zeigt die Größe nicht als gewählt,
  die Morgen-Mail führt sie aber.
- (b) „−“ an einer Größe mit `morning_enabled: true` setzt nur `enabled: false`; sie bleibt in der
  Morgen-Mail (Override schlägt `enabled`).
- (c) Kennzeichnung „nur morgens / nur abends“ je Zeile hat seit #3357 keinen Ort mehr
  (Katalog #3047 N3, Fälle 35 bis 37). Im Issue als Produktfrage markiert; feat_3122 sagt nur
  „keine Bedienung in der Tabelle“ (Zeile 351), die Kennzeichnung ist dort nicht ausgeschlossen.
- Nachtrag 25.11.: Die Karte „Was steht wo“ hakt im 3-Tages-Ausblick `cloud_low` an, kein Briefing
  gibt die Größe dort aus (in `aenderungsfaelle_an_der_tabelle_3020.test.ts:88` ausgenommen).

Fertig, wenn die drei `todo`-Fälle in `was_steht_wo_karte.test.ts` (Describe „#3020 G44“,
`n3_semantik_wie_mail`, `n3_editor_kennzeichnet_je_zeile`, `n3_kennzeichnung_folgt_dem_editorstand`)
ohne `todo` und unabgeschwächt grün sind (Testtabelle `rework_3020_testtabelle.md` G44,
D-trip_tabellen-nur_ein_bericht_*).

## Related Files

| Datei | Rolle |
|---|---|
| `frontend/src/lib/components/shared/wetter-tab/ampelModell.ts` | `tripMetrikEintraege` (Z. 334), `auswahlAus…` (Z. 404–435): Auswahl liest nur `enabled === true` |
| `frontend/src/lib/components/shared/wetter-tab/ampelSchreiben.ts` | `tripMetriken` (Z. 67–95): schreibt nur `enabled`, Flags bleiben per `klon(e)` erhalten → Ursache (b) |
| `frontend/src/lib/components/shared/wetter-tab/wetterZustand.ts` | `standAusAbo`, `ohneMetrik` (vom Test benutzt) |
| `frontend/src/lib/components/shared/wetter-tab/wetterTabSpeicherung.ts` | `tripNutzlast` |
| `frontend/src/lib/components/molecules/EinstellTabelle.svelte` | Karte/Tabelle „Was steht wo“ (`data-metrik`), Ort der Kennzeichnung (c) |
| `frontend/src/lib/components/organisms/__tests__/was_steht_wo_karte.test.ts:684-745` | die drei todo-Fälle, Soll aus Python-Orakel |
| `frontend/src/lib/components/shared/wetter-tab/__tests__/aenderungsfaelle_an_der_tabelle_3020.test.ts:88` | Ausnahme `cloud_low` im Ausblick |
| `src/app/models.py:674-770` | `MetricConfig` (Flags, None = folgt `enabled`), `_filter_metrics_by_report_type` (Override-Semantik) |
| `src/services/channel_list_resolver.py:139` | `tabellen_grundauswahl`: Abend, dahinter nur-morgens (#3154) → Python liefert die Zeilen bereits |
| `src/services/placements_view_service.py` | Antwort der Karte (`_antwort`, `_trip_muster`, Ausblick `_trip_ausblick`) |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/feld_erhalt_ohne_ausnahme.test.ts` | Flags überleben Speichern ohne Änderung (muss grün bleiben) |
| `internal/store/trip_display_config_felderhalt_test.go` | Go-Felderhalt, zwei Nutzer |

## Existing Patterns

- Python-Semantik (Quelle der Wahrheit für die Mail): je Briefing-Typ gilt `morning_enabled`/
  `evening_enabled`, wenn gesetzt, sonst `enabled`.
- Frontend-Kennzeichen analog `nur Tageswert` / `daily value only` (Marken je Zelle,
  `was_steht_wo_karte.test.ts:672`), Texte über i18n-Katalog (ADR-0104).
- Read-Modify-Write mit Merge, nie Replace (Datenschema-Regel, #102).

## Dependencies / Dependents

- Trip-Kontext (`route`); Vergleich (`active_metrics`) kennt keine Bericht-Flags → prüfen, ob nur Trip betroffen.
- Kanal-Parität: E-Mail, Telegram, SMS, Premium-SMS lesen dieselbe Liste (`_filter_metrics_by_report_type` ist Choke-Point).
- Datenmenge Bestand: nicht gemessen, wie viele Trips Flags tragen (Prod-Messung per `sudo -n -u claude-gregor`).

## Existing Specs

- `docs/specs/modules/feat_3122_was_steht_wo.md` (Z. 351: Grundauswahl je Briefing-Typ ohne Bedienung)
- `docs/specs/modules/rework_3020_testtabelle.md` (G44, Z. 90, 320–328, 349)
- ADR-0124 (Tabelle „Was steht wo“), ADR-0050 Regel 3 (Bericht-Flags)

## Risks

- (b) Abwählen muss die Flags auf `false` setzen oder entfernen, ohne andere Felder zu verlieren (Felderhalt-Tests).
- (a) Wiederanwählen einer nur-morgens-Größe: soll sie danach in beiden Briefings stehen (Flags entfernen) oder Flags behalten? Semantik festlegen.
- (c) Produktfrage: Kennzeichnung in der Karte; Testvorgabe aus Katalog #3047 N3 sagt „ja, je Zeile, DE/EN“.
- `cloud_low`-Ausblick: eigener Befund in der Karten-Antwort (Python), evtl. getrennt.

## Analysis

**Type:** Bug (Frontend-Lese-/Schreibseite + fehlende Kennzeichnung in der Karte + Ausblick-Haken in Python).

### Ursachen (belegt, Bug-Intake + Plan)
- (a) `ampelModell.ts` `AUSWAHL_QUELLE.route` (~Z.418-435) und `mitAbgeleiteten` (Z.351) werten nur `enabled`.
- (b) `ampelSchreiben.ts` `tripMetriken` (Z.67-95) setzt nur `enabled`; `klon(e)` behält Flags, Python-Override hält die Größe in der Mail. `wiederAn` prüft nur `enabled !== false`.
- (c) Kennzeichnung entfernt mit #3297 (71c27e117) und #3383 (659fae240). Alte Semantik `weather-metrics-tab/nurEinBericht.ts` (eingeführt 2786662e5): Flag true/false, sonst `enabled` = Python-Semantik. Karte kommt aus Python `_antwort`; `mark` gibt es nur je Zelle (`wasStehtWoAnsicht.ts` Z.94), keine Zeilenmarke. i18n-Schlüssel gelöscht.
- (d) `placements.py` `_heute_ohne_einstellung` (Z.311ff) / `placements_aus_grundauswahl` (Z.273ff): Ausblick-Haken aus Vorgabemengen, `outlook_reports` fließt nicht ein → `cloud_low` (nur morgens, Golden C) angehakt, obwohl nur das Abend-Briefing den Ausblick führt.
- Zeilenmenge stimmt bereits (`tabellen_grundauswahl`). Vergleich nicht betroffen (keine Flags).

### Entscheidungen (Tech Lead)
1. **Variante C**: (a)+(b)+(c)+(d) in diesem Workflow (Issue-Nachtrag gehört zu #3364; kein „kommt später“).
2. **Abwahl („−“)**: `enabled:false` und die Schlüssel `morning_enabled`/`evening_enabled` des Eintrags **entfernen** (nicht `false` setzen, sonst wäre eine Wiederanwahl wirkungslos). Andere Felder bleiben.
3. **Wiederanwahl („+“)** einer zuvor abgewählten Größe: `enabled:true`, Flags entfernt → in beiden Briefings. Begründung: die Tabelle hat keine Bedienung je Briefing (feat_3122 Z.351); keine unsichtbare Einschränkung.
4. **Unveränderte Einträge** behalten ihre Flags (Felderhalt `feld_erhalt_ohne_ausnahme.test.ts`, Go-Felderhalt).
5. **Gewählt** (Lesen) = in mindestens einem Briefing geführt (Python-Semantik je Briefing: Flag wenn gesetzt, sonst `enabled`); Kinder (`mitAbgeleiteten`) entsprechend.
6. **Kennzeichnung (c)** kommt aus Python: neues Zeilenfeld (z. B. `briefing_only: "morning"|"evening"|null`) in `placements_view_service._antwort`, nur Trip (`route`); Regel = je Metrik nach Flags (morgens geführt XOR abends geführt), unabhängig davon, welche Briefings abonniert sind (wie alte `nurEinBericht`). Anzeige als Zeilenmarke in `EinstellTabelle.svelte`, Texte DE „nur morgens“/„nur abends“, EN „morning only“/„evening only“ über den Katalog; `api_contract.md` nachziehen.
7. **(d)**: Ausblick-Haken einer Zeile nur, wenn mindestens ein Briefing aus `outlook_reports` die Größe führt; Ausnahme in `aenderungsfaelle_an_der_tabelle_3020.test.ts` ~Z.86-90 entfernen. Gilt für Anzeige und Erstanlage gleichermaßen (Kanal-Parität, Go-Erstanlage `erstanlage_placements` prüfen).

### Affected Files
| Datei | Change |
|---|---|
| frontend/src/lib/components/shared/wetter-tab/ampelModell.ts | MODIFY (Lesen je Briefing) |
| frontend/src/lib/components/shared/wetter-tab/ampelSchreiben.ts | MODIFY (Flags entfernen bei Ab-/Wiederanwahl) |
| src/services/placements_view_service.py | MODIFY (Zeilenfeld Kennzeichnung) |
| src/services/placements.py (ggf. channel_list_resolver.py) | MODIFY (Ausblick-Haken) |
| frontend/src/lib/components/shared/wetter-tab/wasStehtWoAnsicht.ts / wasStehtWoStand.ts | MODIFY (Zeilenmarke durchreichen) |
| frontend/src/lib/components/molecules/EinstellTabelle.svelte | MODIFY (Zeilenmarke anzeigen) |
| frontend/src/lib/i18n/messages/{de,en}/*.json | MODIFY (2 Schlüssel) |
| docs/reference/api_contract.md | MODIFY (neues Antwortfeld) |
| was_steht_wo_karte.test.ts, aenderungsfaelle_an_der_tabelle_3020.test.ts | MODIFY (todo/Ausnahme weg) + neue Python-/Frontend-Tests |

**Scope/Risk:** ~150 LoC, 8–10 Dateien, Risiko mittel (Auswahl-Semantik, Schreibseite, Erstanlage-Tabelle). Mail-Pfad `_filter_metrics_by_report_type` bleibt unverändert.

### Open Questions
- Keine Produktfrage offen: Entscheidungen 2/3/6 gehen als ACs in die Spec zur PO-Freigabe.
- Bestandsmessung (wie viele Prod-Trips Flags tragen) in Phase 6/7 per `sudo -n -u claude-gregor` nachholen (nur lesend).
