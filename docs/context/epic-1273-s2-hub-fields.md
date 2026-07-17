# Context: epic-1273-s2-hub-fields

## Request Summary

Epic #1273 Slice S2: Name, Region und Aktivitätsprofil des Ortsvergleichs sollen direkt im Hub (`/compare/[id]`) editierbar werden — aktuell existieren diese Felder nur im alten, separaten Editor (`CompareEditor.svelte`, Route `/compare/[id]/edit`), der in einer späteren Slice (S3) entfällt. Ohne diese Slice wäre ein Redirect von `/edit` auf den Hub eine echte Funktionsregression (Nutzer könnten den Vergleich nicht mehr umbenennen).

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/routes/compare/[id]/+page.svelte:152-246` | Hub-Kopfbereich (Desktop Z.152-199, Mobile Z.201-246) — Name (Z.165,215), Region (Z.174,244), Aktivitätsprofil (`profileLabel`, Z.174,244) werden hier aktuell NUR lesend angezeigt. Genau hier sollen die Felder editierbar werden — analog zur Trip-Kopfzeile, nicht in einem Tab. |
| `frontend/src/lib/components/trip-detail/TripHeader.svelte:33-54,127-163,274-314` | Exaktes Vorbild: Stift-Icon-Toggle (`isEditingName`), lokaler State (`editName`/`nameSaving`/`nameSaveError`), direkter `api.put()`-Aufruf OHNE `saveController` — der Chip wird nur mitgerendert, nicht für den Save selbst benutzt. 1:1 auf Name übertragbar; Region/Aktivitätsprofil brauchen dasselbe Muster, aber eigene Eingabe-UI (Region = Text, Aktivitätsprofil = Auswahl). |
| `frontend/src/lib/components/compare/CompareEditor.svelte:1177-1247` | Referenz für die editierbaren Felder im alten Editor: Name (Z.1177-1189, `data-testid="compare-editor-name"`), Region (Z.1191-1200, `data-testid="compare-editor-region"`), Aktivitätsprofil-Kacheln (Z.1202-1247, `data-testid="compare-editor-profile-*"`) — zeigt die Werte-Optionen für Aktivitätsprofil (Auswahl-Kacheln, kein Freitext). |
| `internal/handler/compare_preset.go:288-295` | Go-PUT-Handler macht bereits Read-Modify-Write / Object-Level-Preserve für `display_config` — ein Teil-PUT mit nur `{name: ...}` bzw. `{display_config: {region: ...}}` bzw. `{profil: ...}` sollte sicher mergen, ohne andere Felder zu löschen. Vor Implementierung stichprobenartig verifizieren (nicht nur annehmen). |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | Bestehender Round-Trip-Payload-Bauer für den alten Editor — NICHT direkt wiederverwendbar (arbeitet auf `CompareWizardState`, die auf dieser Seite nicht existiert), aber als Referenz für die erwarteten Feldnamen (`name`, `display_config.region`, `activity_profile`/`profil`). |

## Existing Patterns

- **Isolierte Inline-Edits neben dem geteilten `saveController`:** TripHeader zeigt, dass nicht JEDE Änderung durch `saveController.schedule()`/`hubPutQueue` muss — punktuelle, seltene Edits (Name ändern ist kein Live-Tipp-Feld) dürfen einen eigenen, einfachen `api.put()` + lokalen Saving-State haben. Der `hubSaveCtl` aus S1 bleibt für die 5 bestehenden Commit-Handler zuständig, wird hier nicht angefasst.
- **Trip/Compare-Teilungs-Invariante:** Die drei neuen Edit-UIs sollten so nah wie möglich am TripHeader-Muster gebaut werden (gleiche CSS-Klassen-Namensgebung, gleiches Stift-Icon-Verhalten), auch wenn TripHeader.svelte selbst kein `context`-Prop hat und daher nicht direkt wiederverwendet werden kann (andere Datenstruktur: `Trip` vs. `ComparePreset`, andere Seite). Geteilter Code wäre nur über eine neue Abstraktion möglich — dafür ist der Umfang dieser Slice zu klein; stattdessen Musterkopie mit Kommentar-Verweis (wie an vielen Stellen im Projekt bereits üblich, z. B. `CorridorEditorMobile`-Verweis auf `TripTabs.svelte:198-202`).

## Dependencies

- **Upstream:** `api.put()` (`$lib/api.js`), Go-Handler `internal/handler/compare_preset.go` (Read-Modify-Write bereits vorhanden).
- **Downstream:** Keine — reine additive UI-Ergänzung, nichts Bestehendes wird entfernt oder umgebaut.
- **Vorbedingung erledigt:** Slice S1 (Save-Chip-Infra) — live, unabhängig von dieser Slice nutzbar.
- **Blockiert NICHT S3** (Link-Umbiegung/Redirect), ist aber dessen Voraussetzung (Feature-Paritäts-Lücke muss vor jedem Redirect geschlossen sein).

## Risks & Considerations

1. **Aktivitätsprofil ist eine Auswahl, kein Freitext** — die UI braucht Kacheln/Buttons wie im alten Editor (Z.1202-1247), nicht nur ein Input-Feld wie bei Name/Region.
2. **Mobile + Desktop getrennt implementiert** in `+page.svelte` (zwei Markup-Blöcke, Z.152-199 und Z.201-246) — beide müssen die neue Edit-Fähigkeit bekommen, sonst Parität-Lücke zwischen den Viewports.
3. **PUT-Payload-Minimalität verifizieren:** vor dem Schreiben der Spec kurz gegen den echten Go-Handler bestätigen, dass ein Teil-PUT (nur ein Feld) tatsächlich sicher mergt und nicht versehentlich andere `display_config`-Unterfelder (z. B. `active_metrics`, `channel_layouts`) löscht.
4. **Scope-Grenze:** NUR Name/Region/Aktivitätsprofil. Keine weiteren Felder, kein Redirect (S3), keine Testmigration (S4).

## Analysis

### Type
Feature (Standard Track)

### Technical Approach
Drei isolierte Inline-Edit-Blöcke im Hub-Kopfbereich (`routes/compare/[id]/+page.svelte`), je Feld eigener Stift-Icon-Toggle + lokaler State nach TripHeader-UI-Vorbild — ABER mit Round-Trip-Spread-Payload statt Minimal-Body (s. Korrektur unten, Datenverlust-Risiko sonst real). Dupliziert für Desktop- und Mobile-Block. Aktivitätsprofil als Auswahl-Kacheln analog `CompareEditor.svelte:1202-1247`. Nach erfolgreichem PUT: `data.preset` lokal aktualisieren, damit die Anzeige ohne Reload aktuell ist.

### Scope Assessment
- Files: 1 Produktivdatei (`routes/compare/[id]/+page.svelte`), ggf. 1 kleine gemeinsame Hilfsfunktion falls Desktop/Mobile stark duplizieren würden (Entscheidung: erst duplizieren, nur bei echtem Bedarf extrahieren — YAGNI)
- Estimated LoC: ~150-220 (inkl. Tests)
- Risk Level: LOW-MEDIUM

### Dependencies
Siehe oben — keine neuen Bausteine, alles bestehende Muster.

### Open Questions
- [x] Exaktes PUT-Payload-Format geklärt: `name` und `profil` sind Top-Level-Strings (`internal/model/compare_preset.go:26`), Region liegt in `display_config.region`.

### KRITISCHE KORREKTUR nach Verifikation gegen den echten Go-Handler

**Das TripHeader-Muster (minimaler PUT-Body wie `{name: editName}`) ist für Compare-Presets NICHT sicher und darf NICHT kopiert werden.**

`UpdateComparePresetHandler` (`internal/handler/compare_preset.go:259-297`) dekodiert den Body in ein FRISCHES `model.ComparePreset{}` (Zero-Value-Start), nicht in eine Kopie von `original`. Nur explizit mit `if updated.X == zero { updated.X = original.X }`-Guards versehene Felder werden vor dem Verlust geschützt (`DisplayConfig`, `PreviousSchedule`, `OfficialAlertsEnabled`, `RadarAlertEnabled`, `HourlyEnabled`, `AlertCooldownMinutes`/`QuietFrom`/`QuietTo`, `OfficialAlertTriggersEnabled`, `OfficialWarnings`, `SendTelegram`, `SendSms`, `ForecastHours`, die 5 Slot-Felder, `Corridors`, `EndDate`). **`Name`, `Profil`, `LocationIds`, `Empfaenger`, `Schedule`, `HourFrom`/`HourTo` haben KEINEN solchen Schutz** — ein PUT-Body, der nur `{"name": "..."}` enthält, würde `location_ids`/`empfaenger`/`schedule`/`profil` etc. auf Zero-Value (leerer String/leeres Array) zurücksetzen. Exakt das BUG-DATALOSS-Muster aus CLAUDE.md.

**Korrigierter Ansatz:** Wie `compareEditorSave.ts` bereits vormacht — Round-Trip-Spread. Vor dem PUT den *aktuell geladenen* `data.preset` vollständig spreaden und NUR das geänderte Feld überschreiben: `{ ...data.preset, name: editName }` (bzw. `{ ...data.preset, display_config: { ...data.preset.display_config, region: editRegion } }` für Region, `{ ...data.preset, profil: editProfil }` für Aktivitätsprofil). Das ist KEIN Sonderweg, sondern dasselbe Prinzip, das der alte Editor schon nutzt — muss in der Spec als Pflicht-Implementierungsdetail stehen, nicht als Option.
