# Kontext: fix-3361-ausblick-anlegen (Issue #3361)

## Request Summary
Beim Anlegen (Trip UND Orts-Vergleich) bedient der Nutzer die Karte „Was steht wo“ (z. B. ein Haken), fasst den
3-Tages-Ausblick nicht an und stellt danach im Reiter Zustellung „nur Morgen-Briefing“ ein. Der Anlege-POST trägt
`display_config.placements.outlook_reports: ["evening"]`, der Python-Kern nimmt den gespeicherten Wert wörtlich
(`resolve_outlook_reports`), der Ausblick steht in keinem Briefing. Soll (#3155 AC-7, #3122 AC-9, ADR-0124 Nr. 6):
wer den Ausblick nicht selbst gewählt hat, bekommt ihn in dem Briefing, das es gibt.

## Ursache (belegt)
- `src/services/placements_view_service.py:_tabelle_aufloesen` → ohne gespeicherte `rows` liefert die Vorschau
  `placements_aus_grundauswahl(...)` (`src/services/placements.py:273`), deren `outlook_reports` bereits nach der
  Vorbelegung aufgelöst ist (zum Zeitpunkt der Vorschau: beide Briefings an → `["evening"]`).
- `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte:82` `uebernehmen`: im Anlegen wird
  `lokal = klon(a.placements)` einmal übernommen und folgt der Vorschau danach nicht mehr.
- `melde()` gibt `placements: klon(lokal)` an die Anlegeseite; `mitKarte` in
  `frontend/src/lib/components/trip-new/tripNewLogic.ts:352` und
  `frontend/src/lib/components/compare/compareEditorSave.ts:644` setzen es unverändert in den POST.
- `src/services/placements.py:231` `resolve_outlook_reports`: gespeichert gewinnt; nur ohne Wert (`None`) gilt die
  Vorbelegung (nur Morgen an → Morgen, sonst Abend). Fehlt `outlook_reports` in gespeicherten `placements`, liest
  `read_placements` `None` → Vorbelegung wirkt bei jedem Lesen nach dem aktuellen Zustellungsstand.

## Related Files
- `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte` (einziger Code für Trip und Orte)
- `frontend/src/lib/components/shared/wetter-tab/wasStehtWoStand.ts` (reine Stand-Funktionen, `mitAusblick`)
- `frontend/src/lib/components/shared/wetter-tab/wasStehtWoSpeicherung.ts` (`KarteAnlegeStand`)
- `frontend/src/lib/components/trip-new/tripNewLogic.ts`, `compare/compareEditorSave.ts` (`mitKarte`, unverändert)
- Test (bereits vorhanden, `todo`): `frontend/src/lib/components/trip-new/__tests__/anlegen_ausblick_vorbelegung_folgt_zustellung.test.ts` (E137 aus #3020 R1)
- `frontend/src/lib/__tests__/rework_3020_rote_liste.ts` (Verweis auf #3361)

## Existing Patterns
- Schalter der Karte: Anlege-POST trägt nur die Differenz zum Start (`felderNutzlast(... felderStart)`). Dasselbe
  Prinzip „nur, was der Nutzer selbst gewählt hat“ gilt hier für den Ausblick.
- `placements` ohne `outlook_reports` ist eine gültige Speicherform (`placements_dict` lässt den Schlüssel bei
  `None` weg).

## Dependencies / Dependents
- Hub (Bearbeiten) nutzt dieselbe Karte; dort ist `createMode=false`, die Änderung greift nur im Anlegen.
- Anzeige der Ausblick-Schalter: `ausblickBerichte = lokal?.outlook_reports ?? antwort?.outlook_reports` → fällt
  ohne eigene Wahl auf die Vorschau zurück (unverändert richtig).
- Neu-Mount der Karte im Anlege-Wizard über `karteStart` (`start.placements`) — trägt dann ebenfalls keinen
  Ausblick ohne eigene Wahl.

## Existing Specs
- `docs/specs/modules/rework_3020_altbausteine_entfernen.md` (AC-6, E137 als `todo`)
- ADR-0124 Nr. 6 (Vorbelegung Ausblick)

## Risks
- Hub-Abos ohne gespeicherte `rows` (Vorschau-Stand) frieren den Ausblick beim ersten PUT ebenso ein. Nach dem
  Datenlauf #3351 tragen Bestandsabos `rows`; nicht Gegenstand dieses Issues (Bearbeiten ≠ Anlegen, Nutzer sieht dort
  den Ausblick-Schalter im Ist-Stand). Im Abschlusskommentar als Beobachtung vermerken, kein Code.
- Wahl des Nutzers muss erhalten bleiben: hat er den Ausblick selbst bedient, geht `outlook_reports` mit.

## Analysis

**Type:** Bugfix (Ursache belegt, siehe oben; strategische Prüfung durch Plan-Agent bestätigt).

**Affected Files (Change Type)**
- MODIFY `frontend/src/lib/components/organisms/wetter-tab/WasStehtWoKarte.svelte` — `uebernehmen`: im Anlegen `lokal = ohneAusblick(klon(a.placements))`
- MODIFY `frontend/src/lib/components/shared/wetter-tab/wasStehtWoStand.ts` — neue reine Funktion `ohneAusblick`
- MODIFY `frontend/src/lib/components/trip-new/__tests__/anlegen_ausblick_vorbelegung_folgt_zustellung.test.ts` — E137 aus `todo` nehmen
- MODIFY `frontend/src/lib/__tests__/rework_3020_rote_liste.ts` — Verweis #3361 bereinigen (falls er den `todo` führt)
- CREATE Test: Karte im Anlegen, Haken bedient → gemeldeter Stand ohne `outlook_reports`; Ausblick bedient → Wahl bleibt

**Scope/Risk:** ~10 LoC Code, ~40 LoC Test, Risiko niedrig (nur Anlege-Modus, Hub unberührt; Go füllt nichts nach:
`internal/handler/placements.go:118-166` lässt mitgeschickte `placements` unangetastet; Python liest fehlenden Schlüssel als `None`).

**Technical Approach:** Variante A (eine Stelle, ADR-0097 geteilt). Variante B (Flag in `KarteAnlegeStand`, Entfernen in
beiden `mitKarte`) verworfen: 4 Stellen, alle Fixtures bräuchten das Flag.

**Open Questions:** keine. Beobachtung (kein Code): Hub-Abos ohne gespeicherte `rows` frieren den Ausblick beim ersten PUT ein.
