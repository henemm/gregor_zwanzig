# Analyse #690 — Eigene Wetter-Metriken-Profile: speichern, kennzeichnen, eindeutig benennen

**Workflow:** `bug-690-custom-metrics-persist`
**Issue:** #690 „Trip - Wetter-Metriken"
**Typ:** Bug an halbfertigem Feature + kleine Erweiterung (eindeutiger Name)
**Scope:** Full-Stack (FE + kleiner BE-Anteil), ~40–50 LoC, **keine Schema-Migration**

## Symptom (PO)

Im Trip-Editor existiert ein „eigenes Profil speichern"-Feature (SavePresetDialog). Es erscheint, wirkt aber kaputt: nach dem Speichern passiert sichtbar nichts, eigene Profile sehen aus wie System-Vorlagen, und der Name muss eindeutig sein (neue Anforderung).

## Root Cause — vier Lücken (alle code-belegt)

1. **Kein Auto-Aktivieren.** `WeatherMetricsTab.svelte:360-362` `onPresetSaved` prependet das neue Profil nur in `userPresets`, ruft aber `applyPreset(preset.id)` **nicht** auf. → `selectedTemplate` bleibt leer, `display_config.preset_name` wird beim folgenden `handleSave` nicht gesetzt → das Profil ist nicht mit dem Trip verknüpft, wirkt „nicht gespeichert".
2. **Keine „Eigene"-Kennzeichnung.** `WeatherV2PresetBar.svelte:27-50` rendert `userPresets` und `templates` mit identischer `preset-pill`-Klasse, kein Badge. Nutzer kann eigene Profile nicht von System-Vorlagen unterscheiden.
3. **Trip-übergreifend** — Backend liefert eigene Profile mandantengetrennt auf jedem Trip (`GET /api/metric-presets`, `store.go` Pfad `data/users/<user_id>/metric_presets.json`, Handler `metric_preset.go:121` mit `s.WithUser(...)`). Diese Lücke löst sich automatisch mit Fix 1 (Profil wird am Trip vermerkt + voraktiviert).
4. **Name nicht eindeutig.** Dialog hat Pflicht-Namensfeld (`SavePresetDialog.svelte:155-167`, `canSubmit` = name nicht-leer), aber **keine** Eindeutigkeitsprüfung. Backend `CreateMetricPresetHandler` (`metric_preset.go:147-150`) lehnt nur leere Namen ab (`name_required`), erlaubt Duplikate.

## Betroffene Dateien

| Datei | Lücke | Änderung |
|---|---|---|
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | 1 | `onPresetSaved` ruft `applyPreset(preset.id)` |
| `frontend/src/lib/components/trip-detail/WeatherV2PresetBar.svelte` | 2 | „Eigene"-Pille/Badge für `userPresets` |
| `frontend/src/lib/components/trip-detail/SavePresetDialog.svelte` | 4 | Client-Validierung gegen vorhandene Namen (case-insensitive, trim) + Anzeige `name_exists` |
| `internal/handler/metric_preset.go` | 4 | Uniqueness-Check vor Append → `409 name_exists` (case-insensitive, trim) |
| `internal/handler/metric_preset_test.go` | 4 | Go-Test mock-frei: Dublette → 409, zwei Nutzer isoliert |

## Backend-Korrektheit (kein Fix nötig)

- Mandantentrennung ist sauber: `s.WithUser(middleware.UserIDFromContext(r.Context()))` in List/Create/Delete.
- Persistenz pro Nutzer unter `data/users/<user_id>/metric_presets.json`.

## Risiken

- Niedrig. `applyPreset()` ist der bestehende, getestete Pfad (`onSelectPreset`). Pille additiv. Uniqueness additiver Guard.
- Eindeutigkeit gilt **pro Nutzer** — zwei verschiedene Nutzer dürfen denselben Profilnamen haben (mandantengetrennt). Test mit zwei Nutzern Pflicht.
- Kein Schema-Rework an gespeicherten Daten → keine Migration, kein Datenverlust-Risiko.
