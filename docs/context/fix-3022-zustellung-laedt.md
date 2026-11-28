# Kontext: fix-3022-zustellung-laedt (Issue #3022)

## Request Summary
Hängen im Orts-Vergleich die Katalog-Abrufe (`GET /api/metrics`, `GET /api/compare/metrics`), bleibt der
Reiter **Zustellung** leer (nur Kopf aus der Hydrations-Sperre), der Trip zeigt sofort alle Karten.
Derselbe Befund trifft den Reiter **Wetter** im Zustand `laedt`: statt Wetter-Kopf (Abschnitt
`abschnittskopf`) + „Lade Metriken …“ steht nur der Sperr-Kopf. Elementlisten-Besitzer: 59 Einträge
`orte.zustellung.laedt.*` + 3 Einträge `orte.wetter.laedt.*` tragen `#3022`.

## Ursache (belegt)
`frontend/src/lib/components/compare/CompareTabs.svelte`
- Z. ~777: `{#if wetterMetrikenLayoutHydrationBereit}` vor `<WetterTab>`, sonst Sperr-Kopf.
- Z. ~797: `{#if wetterMetrikenLayoutHydrationBereit && versandHydrated && alarmeHydrated}` vor
  `<ZustellungTab>`, sonst Sperr-Kopf.
- `wetterMetrikenHydrated` und `alarmeHydrated` warten auf `loadCompareSelectionEntries()` (Katalog) —
  hängt der Katalog, öffnet das Gate nie.

## Warum die Gates heute wirkungslos sind
Alle Hydrationen schreiben nur in `wizardState` (CompareTabs-intern). `wizardState` wird nach
Z. 561 nirgends mehr gelesen: kein Prop an WetterTab/ZustellungTab, kein `setContext`.
- `ZustellungTab` (shared/zustellung-tab/) liest seinen Stand direkt aus `preset`
  (`standAusPreset`), Speicherer-Basis = `startStand` aus dem Preset (#2795 S3b, #3036, #3154).
- `WetterTab` → `organisms/wetter-tab/WetterTabInhalt.svelte` lädt selbst und zeigt eigenen
  Ladezustand („Lade Metriken …“, Z. 266).
- Trip (`trip-detail/TripTabs.svelte` Z. 229/231) mountet beide Reiter ohne Gate.
Die Gate-Begründungen (F012 „Platzhalter-Baseline“, #1743 AC-9) stammen aus der Zeit, als die
Reiter `wizardState`-Felder bedienten (Übergangsblock, AlarmeTab, VersandTab) — alles entfernt.

## Related Files
- `frontend/src/lib/components/compare/CompareTabs.svelte` (Fix)
- `frontend/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte` (unverändert)
- `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte` (unverändert)
- `docs/context/einstellungen_neu/elementliste_besitzer.json` (62 `#3022`-Einträge entfernen)

## Betroffene Tests (müssen an den neuen Soll angepasst werden)
- `shared/__tests__/s3a2794_zustellung_vergleich_mount_hydration.test.ts` (F012: Gate-Pflicht → umkehren)
- `shared/__tests__/s3a2794_teil3_wettertab_mount.test.ts` Z. 140ff (Gate-Pflicht WetterTab)
- `compare/__tests__/compare_versand_hydration_unter_wetter_metriken.test.ts` Z. 182ff (Template-Gate)
- `molecules/__tests__/bereichskopf_3006.test.ts`, `listenzeile_3007.test.ts` (setzen Flags per
  String-Ersetzung auf true, um die Reiter zu rendern — bleiben ggf. gültig, prüfen)
- `shared/__tests__/s3a2794_flush_hydration_kette.test.ts`, `compare_wetter_reiter_hydration_nach_preset_sync_3298.test.ts`
  (prüfen Hydrations-Flags, nicht das Gate — bleiben gültig, solange die Effekte bleiben)

## Existing Patterns
Trip/Orte-Teilung (ADR-0097, CLAUDE.md): ein Reiter-Code mit `context`; Parität heißt hier: gleiche
Mount-Bedingung wie im Trip (nur Reiter aktiv).

## Risks
- Speicher-Baseline: ZustellungTab nimmt `startStand` untracked aus `preset` beim Mount — Preset ist
  beim Hub-Aufbau bereits da; Hydrationen ändern `currentPreset` nicht → kein Leerstand-PUT.
- Toter Code: Hydrations-Effekte + `wizardState` bleiben ohne Leser (Nebenbefund, eigenes Issue).
- Elementlisten-Abgleich `--abnahme`: nach Fix müssen die 62 Einträge aus der Besitzerliste,
  sonst „verwaister Besitzer“ bzw. weiterhin verdeckte Abweichung.

## Analysis

**Type:** Bugfix (Trip/Orte-Parität im Ladezustand)

**Affected Files:**
| Datei | Change | Grund |
|---|---|---|
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Mount-Gates vor `WetterTab` und `ZustellungTab` entfernen (nur `activeTab` bleibt), Sperr-Kopf-Zweige + `.hub-kopf-sperre*`-CSS entfernen (sonst ungenutzte Selektoren) |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | MODIFY | 62 Einträge mit `verweis: "#3022"` entfernen |
| `frontend/src/lib/components/shared/__tests__/s3a2794_zustellung_vergleich_mount_hydration.test.ts` | MODIFY | F012-Soll umkehren: ZustellungTab mountet bei jeder Flag-Kombination, sobald `activeTab==='zustellung'` |
| `frontend/src/lib/components/shared/__tests__/s3a2794_teil3_wettertab_mount.test.ts` | MODIFY | WetterTab-Gate-Test umkehren (mountet ohne Hydrations-Flag) |
| `frontend/src/lib/components/compare/__tests__/compare_versand_hydration_unter_wetter_metriken.test.ts` | MODIFY | Template-Test #1743 AC-9 (Gate-Pflicht) entfällt / wird umgekehrt |
| `bereichskopf_3006.test.ts`, `listenzeile_3007.test.ts` | prüfen | Flag-Ersetzungen werden wirkungslos, Tests sollten grün bleiben |

**Scope/Risk:** 1 Quelldatei, ~-40 LoC; Risiko niedrig: die Reiter lesen ihren Stand direkt aus dem
Preset bzw. laden selbst, `wizardState` hat keinen Leser mehr. Kein Speicherpfad ändert sich.

**Technical Approach:** Gleiche Mount-Bedingung wie im Trip (`TripTabs.svelte`): nur der aktive Reiter.
Hydrations-Effekte bleiben vorerst (harmlos, von Tests beobachtet) — Rückbau des toten
`wizardState`-Feldsatzes als eigenes Issue (Nebenbefund). Verhaltensnachweis: Render-Test der echten
`CompareTabs` mit hängendem Katalog (Promise, die nie auflöst) → Reiter Zustellung zeigt Briefing-Zeiten /
Kanal-Tabelle, Reiter Wetter zeigt Abschnittskopf + „Lade Metriken …“. Live-Nachweis: Elementlisten-Abgleich
Zustand `laedt` Orte (Zustellung + Wetter) ohne `#3022`-Besitzer grün.

**Dependencies:** ZustellungTab (preset, saveController, enqueueHubWrite), WetterTabInhalt (eigener Ladezustand).

**Open Questions:** keine (Soll ist im Issue und im Mockup festgelegt).
