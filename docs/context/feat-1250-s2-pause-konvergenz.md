# Context: feat-1250-s2-pause-konvergenz

## Request Summary
Scheibe 2 von Epic #1250 (Phase 3, Briefing-Abo-Chassis): additives Feld `paused_at`
am ComparePreset (Go + Python + Frontend), Dual-Write mit der Alt-Semantik
`schedule=="manual"`, und `deriveStatusFromPreset` liest `paused_at` zuerst.
Verhaltensneutral, additiv — nichts wird ersetzt (Alt-Feld `schedule` bleibt bis
zur Migrations-Scheibe S5). ACs: AC-7–AC-9 der Programm-Spec
`docs/specs/modules/issue_1250_briefing_subscription.md`.

## Related Files
| File | Relevance |
|------|-----------|
| `internal/model/compare_preset.go:24` | `Schedule string json:"schedule"` — **kein `omitempty`**, wird immer emittiert; trägt laut Kommentar Z.19-23 „ausschließlich noch die Pause-Semantik" (`manual`=pausiert). Einbaustelle für `PausedAt *time.Time json:"paused_at,omitempty"` neben `ArchivedAt` (Z.38/39). |
| `internal/store/compare_preset.go:98` | `SaveComparePresets` = **Full-Replace der übergebenen Liste** (kein RMW). `NormalizeComparePreset` (Z.20) läuft bei jedem Save → **hier gehört die Dual-Write-Invariante hin** (schedule ⇄ paused_at). |
| `internal/handler/compare_preset.go:255-390` | PUT-Handler = eigentlicher RMW/Merge (`original := presets[idx]`, feldweises nil-preserve Z.275-283/362, `NormalizeComparePreset(&updated)` Z.378, `presets[idx]=updated` Z.385). **paused_at HIER nil-preserven** (`if updated.PausedAt==nil { =original.PausedAt }`, analog Corridors Z.362) für Zeitstempel-Stabilität — sicher, weil Normalize (Z.378, läuft danach) bei `schedule!="manual"` wieder löscht → Entpausen bleibt intakt. |
| `src/app/models.py:848` | `ComparePreset`-Dataclass (S1). Feld `archived_at` Z.878, `raw` Z.895. `paused_at: Optional[str]=None` neben `archived_at`. |
| `src/app/loader.py:211/234/292` | `compare_preset_from_dict` (parse + `raw=dict(data)`), `compare_preset_to_dict` gibt **`preset.raw`** zurück (nicht asdict → keine None-Emission). Parse für `paused_at` bei Z.234. |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts:65-70` | `deriveStatusFromPreset` — heute `schedule==='manual'` → `paused`. Umstellen: `paused_at` truthy zuerst, dann Fallback `schedule`. Draft-Vorrang (Z.66) bleibt oberste Regel. |
| `frontend/src/lib/types.ts:461-466` | TS-`ComparePreset` — kein `paused_at`; additiv `paused_at?: string` ergänzen (Trip hat es bereits, types.ts:292). |

## Vorbild-Muster (Ziel-Semantik)
- **Trip `paused_at` (Go):** `internal/model/trip.go:121` `PausedAt *time.Time json:"paused_at,omitempty"` (Pointer + omitempty).
- **Trip `paused_at` (Python):** `src/app/trip.py:201` `paused_at: Optional[str]`; konditionale Serialisierung `loader.py:1269-1270` (`if trip.paused_at:`).
- **Dual-Write-Vorbild #1231 (Korridore):** `scripts/migrate_1231_corridors.py:121` — neues Feld additiv aus alter Quelle füllen, alte Semantik parallel bestehen lassen. RMW-nil-preserve Corridors: `internal/handler/compare_preset.go:362`.

## Dependencies
- **Upstream:** braucht S1 (`ComparePreset`-Dataclass + `raw`-Mechanismus, ✅ live c263ad3c).
- **Downstream / Aufrufer von `deriveStatusFromPreset`:** `CompareGrid.svelte:145`, `CompareTile.svelte:61`, `CompareTabs.svelte:118` (mit `localSchedule`/`scheduleOverride`-Override!), `routes/compare/+page.svelte:15-17`, `routes/+page.svelte:38`, Wrapper `deriveStatusWithScheduleOverride` (subscriptionHelpers.ts:88). Test-Guards: `bug_591_pausieren_button.test.ts:40-50`, `hub_status_pill_override.test.ts:60`.

## Design-Entscheidung (Analyse, kombiniert mit Context — Standard-Track)
1. **KORRIGIERTES Design nach Adversary-Runde 1 (F001 CRITICAL / F002 MEDIUM):**
   `NormalizeComparePreset` läuft auch auf dem LESE-Pfad (`LoadComparePresets`, kein Write-Back).
   `time.Now()` dort → `paused_at` driftet bei jedem GET und wird nie persistiert. Deshalb:
   - **`time.Now()`-SET raus aus `NormalizeComparePreset`.** Normalize behält NUR die deterministische
     Löschung (`schedule!="manual"` → `paused_at=nil`) — driftfrei, läuft weiter überall.
   - **Neuer Store-Helfer `MaterializePausedAt(p *model.ComparePreset, now time.Time)`** (injizierte Zeit,
     testbar/deterministisch): `if p.Schedule=="manual" && p.PausedAt==nil { p.PausedAt=&now }`.
     Wird NUR vom Schreib-Pfad (Handler PUT/POST) mit `time.Now().UTC()` gerufen → paused_at wird bei
     der tatsächlichen Speicherung gesetzt und persistiert (echter Dual-Write, Slice-Def Z.129).
   - **Handler = server-verwaltetes Feld (F002):** `updated.PausedAt = original.PausedAt` UNBEDINGT
     (wie ID/UserID/CreatedAt Z.266-270), Client-Wert ignoriert. Dann `MaterializePausedAt(&updated, now)`,
     dann `NormalizeComparePreset(&updated)` (löscht bei Entpausen), dann Save. POST/Create analog
     (Client-`paused_at` ignorieren, aus `schedule` ableiten).
   - **Zeitstempel-Stabilität** ergibt sich: bestehendes `paused_at` (aus `original`) bleibt, weil
     `MaterializePausedAt` nur bei `==nil` setzt. **Kein Drift auf Lese-Pfad** (keine Zeit dort).
   - **AC-7-Interpretation:** „Dual-Write" = Schreibzeit. Der User-sichtbare Status bleibt korrekt (paused
     via `paused_at` ODER Fallback `schedule=="manual"`, AC-8). Alt-Presets ohne `paused_at` materialisieren
     beim nächsten Speichern; **keine Daten-Migration in S2** (gehört zu S5; Status ist via Fallback korrekt).
   - **AC-9-Observation:** Normalize löscht `paused_at` für non-manual weiterhin auf Load → S3 muss diesen
     Guard anfassen, wenn non-manual Auto-Pause `paused_at` setzt (dokumentiert, kein S2-Defekt).
2. **`schedule` bleibt in S2 die schreibende Quelle** (FE-Schreibpfad noch nicht umgestellt);
   `paused_at` wird daraus abgeleitet. `deriveStatusFromPreset` (Lesen) bevorzugt umgekehrt
   `paused_at` (AC-9 Zielrichtung Trip-Semantik). Kein Widerspruch: Schreiben normalisiert,
   Lesen ist robust gegen transiente Inkonsistenz.
3. **Bestehenden `paused_at`-Zeitstempel nicht bei jedem Save überschreiben** (`&& paused_at==nil`),
   sonst springt die Pausierungszeit.
4. **FE-`scheduleOverride`-Pfad** (CompareTabs optimistic pause) muss `paused_at` mitführen,
   sonst friert die Statuspille ein.

## Risks & Considerations
- **Daten-Schema-Rework (BUG-DATALOSS-GR221 #102):** additives Feld, RMW/Merge respektieren, kein Blind-Replace clientseitig. Pre-Snapshot-Hook `data_schema_backup.py` feuert bei Edits an `models.py`/`store.go`.
- **None-Emission Python:** Python-gesetztes `paused_at` MUSS in `preset.raw`, sonst weg beim to_dict-Roundtrip. Go: `omitempty` gegen `"paused_at":null`.
- **AC-Lücke Entpausen:** AC-7 (Setzen) + AC-9 (Vorrang) sind explizit; das **Löschen bei Entpausen** ist nur implizit — als Testfall aufnehmen (mit PO im Slice-Go bestätigen).
- **Draft-Vorrang** (subscriptionHelpers.ts:66) bleibt vor jedem paused_at-Check.
- **Breite Aufrufer** von `deriveStatusFromPreset` — Umstellung wirkt UI-weit; Test-Guards vorhanden.

## Existing Specs
- `docs/specs/modules/issue_1250_briefing_subscription.md` — Programm-Spec (PO-go 2026-07-13, 24 ACs, 8 Scheiben). S2 = AC-7–AC-9. **Wird wiederverwendet, nicht neu geschrieben.**
