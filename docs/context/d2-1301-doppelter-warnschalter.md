# Context: D2 — Doppelter „Amtliche Warnungen"-Schalter (#1292 P4, Scheibe D2 von #1301)

## Request Summary
Das Inhalt-Feld `official_alerts_enabled` (amtliche Warnungen im Bericht) wird pro Editor an
zwei Stellen geschaltet — in der Inhalt-Fläche UND im geteilten Alarm-Tab. Eine Bedienstelle
entfällt; die zwei fachlich verschiedenen verbleibenden Schalter (Bericht-Inhalt vs.
Alarm-Auslöser) müssen unterscheidbar heißen.

## Kernbefund: die Duplizierung ist symmetrisch (Trip + Vergleich)
`AlarmeTab.svelte` ist der **geteilte** Baustein (`context="route"|"vergleich"`). Weil er in
beiden Editoren dieselbe „Amtliche Warnungen"-Bedienstelle rendert, existiert die Doppelung
identisch beim Trip und beim Vergleich:

| Feld | Semantik | Inhalt-Heimat | Zweite (redundante) Stelle |
|------|----------|---------------|----------------------------|
| `official_alerts_enabled` | amtliche Warnungen **im Bericht anzeigen** | Trip: `WeatherMetricsTab.svelte:872-882` · Vergleich: `CompareInhaltSection.svelte:84-89` | `AlarmeTab.svelte:246-251` (route **und** vergleich) |
| `official_warnings.enabled` | amtliche Warnungen **lösen Alert aus** (Auslöser) | `AlarmeTab.svelte:252-257` (bleibt) | — (kein Duplikat) |

Der Auslöser-Schalter ist fachlich verschieden und bleibt unangetastet.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | Enthält die redundante Inhalt-Bedienstelle (Z. 246-251) + Auslöser (Z. 252-257). State/Handler Z. 82-107, Payload `buildAlarmeSaveFn` Z. 170+ |
| `frontend/src/lib/components/shared/alarme-tab/alarmeTabSections.ts` | Abschnitt `official-warnings` (Eyebrow „Wann Warnungen rausgehen") — D3-relevant, hier nur Kenntnisnahme |
| `frontend/src/lib/components/shared/alarme-tab/alarmeDeliveryPayload.ts` | `buildAlarmeDeliveryPayload` — führt `officialAlertsEnabled` in die konsolidierte route-Payload |
| `frontend/src/lib/components/compare/CompareInhaltSection.svelte` | Vergleich-Inhalt-Heimat des Feldes (Z. 84-89). Bleibt bestehen; ggf. Label schärfen |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | Trip-Inhalt-Heimat (Checkbox Z. 872-882, eigener PUT Z. 496/524). Bleibt; ggf. Label |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Verdrahtet Trip-AlarmeTab (route); Flush-Guard Z. 139-144 |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | Verdrahtet Vergleich-AlarmeTab (vergleich) |

## Latenter Datenintegritäts-Befund (Trip)
Beim **Trip** schreiben ZWEI Bedienstellen dasselbe persistierte Feld:
- `WeatherMetricsTab` in seinem zweiten PUT (`official_alerts_enabled: officialAlertsEnabled`, Z. 496/524)
- `AlarmeTab`s konsolidierte Payload (`buildAlarmeDeliveryPayload → officialAlertsEnabled`)

→ Last-Writer-Wins: ein im Inhalt-Tab gesetzter Wert kann durch Speichern im Alarm-Tab mit
dessen (evtl. veraltetem) Initialwert überschrieben werden. Beim **Vergleich** harmlos, weil
`CompareInhaltSection` und `AlarmeTab` (vergleich) beide dieselbe reaktive `wiz.officialAlertsEnabled`
schreiben — kein zweiter Persistenz-Pfad.

**Konsequenz für D2:** Es reicht nicht, nur das UI zu entfernen. Wenn der AlarmeTab die
Inhalt-Bedienstelle verliert, muss er `official_alerts_enabled` auch aus seiner Persistenz-Payload
nehmen — sonst re-assertiert er ein Feld, das dort niemand mehr steuern kann (Doppel-Writer-Race
bleibt). Danach ist der Inhalt-Tab alleiniger Writer.

## Existing Patterns
- **Geteilter Baustein `context="route"|"vergleich"`** — eine Codebasis, Kontext-Parameter. Änderung
  gilt automatisch für beide Editoren (Trip/Compare-Teilungs-Invariante, CLAUDE.md).
- **Single-Writer-Disziplin im AlarmeTab** — EIN `$effect`, EINE konsolidierte Payload
  (`buildAlarmeSaveFn`); Tests: `alarme_save_single_writer.test.ts`, `alarme_delivery_consolidated_save.test.ts`.
- **Round-Trip-Merge für persistierte Felder** — Client-unbekannte Felder nie verlieren (Read-Modify-Write).

## Dependencies
- Upstream: `official_alerts_enabled` (types.ts:299 Trip / :509 Compare), `official_warnings.enabled`.
- Downstream: Backend-Render-/Alarm-Pfade lesen die Felder unverändert — kein Backend-Change nötig.

## Existing Specs
- `docs/specs/modules/issue_1258_alarme_tab_official_warnings.md` — AlarmeTab-Grundspec (AC-9/AC-10, Abschnitte a-h)

## Risks & Considerations
- **Shared-Component-Blast-Radius:** Entfernen im AlarmeTab betrifft Trip UND Vergleich. Bewusst
  gewollt (behebt die Doppelung symmetrisch), muss aber in ACs für beide Editoren nachgewiesen werden.
- **Persistenz-Race nicht nur kaschieren:** AlarmeTab muss `official_alerts_enabled` aus der Payload
  nehmen, nicht nur den Toggle ausblenden.
- **Kein context-spezifischer Sonderweg im Shared-Baustein** — nicht „nur bei vergleich entfernen"
  (das wäre der Anti-Pattern-Verstoß gegen die Teilungs-Invariante).
- **D3 folgt** (Struktur/Beschriftung im selben Abschnitt) — D2 nicht mit D3-Umbau vermischen.
