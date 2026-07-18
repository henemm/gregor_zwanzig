---
entity_id: d2_1301_official_alerts_single_control
type: module
created: 2026-07-18
updated: 2026-07-18
status: draft
version: "1.0"
tags: [compare, trip, alarme, ui, dataloss-fix]
---

# D2 — Amtliche Warnungen: eine Bedienstelle je Editor (#1292 P4, Scheibe D2 von #1301)

## Approval

- [x] Approved (PO-Freigabe 2026-07-18)

## Purpose

Das Feld `official_alerts_enabled` („amtliche Warnungen im Bericht anzeigen") wird pro Editor
an zwei Stellen geschaltet — in der Inhalt-Fläche UND im geteilten Alarm-Tab, mit identischem
Label. Die redundante Bedienstelle im Alarm-Tab entfällt. Die zwei fachlich verschiedenen
verbleibenden Schalter (Bericht-Inhalt vs. Alarm-Auslöser) bekommen unterscheidbare Labels.
Als Folge wird ein latenter Doppel-Writer beim Trip beseitigt (Datenverlust-Klasse).

## Source

- **File:** `frontend/src/lib/components/shared/AlarmeTab.svelte` (geteilt route+vergleich)
- **File:** `frontend/src/lib/components/shared/alarme-tab/alarmeDeliveryPayload.ts`
- **File:** `frontend/src/lib/components/compare/CompareInhaltSection.svelte`
- **File:** `frontend/src/lib/components/shared/WeatherMetricsTab.svelte`
- **Identifier:** `official-warnings`-Abschnitt in AlarmeTab; `buildAlarmeDeliveryPayload`

Schicht: **Frontend / User-UI** (SvelteKit). Kein Backend-Change — die Persistenz-Felder
(`official_alerts_enabled`, `official_warnings.enabled`) bleiben unverändert; nur der zweite
Schreibpfad (AlarmeTab-Payload) für `official_alerts_enabled` entfällt.

## Estimated Scope

- **LoC:** ~80 (davon Test-Anpassungen ~30)
- **Files:** 4 Produktiv-Dateien + 3 Test-Dateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `official_alerts_enabled` | Feld | Bericht-Inhalt-Flag (types.ts:299 Trip / :509 Compare) |
| `official_warnings.enabled` | Feld | Alarm-Auslöser (bleibt, nicht betroffen) |
| `issue_1258_alarme_tab_official_warnings.md` | Spec | AC-12/AC-26 (konsolidierte Payload) — wird durch D2 angepasst |

## Implementation Details

**Ausgangslage (dreifacher Schalter je Feld-Semantik):**

| Bedienstelle | Feld | Verbleib |
|---|---|---|
| Trip `WeatherMetricsTab.svelte:872-882` (Inhalt-Tab, Checkbox) | `official_alerts_enabled` | **bleibt** — Inhalt-Heimat Trip |
| Vergleich `CompareInhaltSection.svelte:84-89` (Inhalt-Sektion, Toggle) | `official_alerts_enabled` | **bleibt** — Inhalt-Heimat Vergleich |
| `AlarmeTab.svelte:246-251` (geteilt, Toggle „Amtliche Warnungen") | `official_alerts_enabled` | **ENTFÄLLT** (route + vergleich) |
| `AlarmeTab.svelte:252-257` (geteilt, Toggle „…lösen Alert aus") | `official_warnings.enabled` | **bleibt** — Alarm-Auslöser |

**Warum der Alarm-Tab-Toggle entfällt (und nicht die Inhalt-Heimat):**
Das Feld ist fachlich Bericht-**Inhalt**; seine Heimat ist der Inhalt-Bereich. Der Alarm-Tab
regelt Auslöser/Schwellen. Zudem ist der Alarm-Tab der **problematische** Doppel-Writer (s.u.).

**Änderungen `AlarmeTab.svelte`:**
1. Ersten `ChannelToggle` („Amtliche Warnungen", testid `alerts-tab-official-alerts-toggle`) aus
   dem `official-warnings`-Abschnitt entfernen. Der Auslöser-Toggle bleibt unverändert.
2. Toten Zustand entfernen: `officialAlertsEnabled`-State, `displayOfficialAlertsEnabled`-Derived,
   `handleOfficialAlertsToggle`-Handler.
3. `officialAlertsEnabled` aus dem route-`$effect`-JSON-Tracking und aus dem an
   `buildAlarmeDeliveryPayload` übergebenen State-Objekt entfernen.

**Änderungen `alarmeDeliveryPayload.ts`:**
4. `officialAlertsEnabled` aus `AlarmeDeliveryState` streichen, den zugehörigen boolean-Guard
   entfernen, und `official_alerts_enabled` nicht mehr in die PUT-Payload schreiben. Damit ist
   der Inhalt-Tab alleiniger Writer (Server-PUT ist partieller RMW-Merge — nicht gesendete Felder
   bleiben unberührt). Guards für `officialWarningsEnabled` und `channels` bleiben.

**Label-Schärfung (die zwei verbleibenden Schalter „müssen es auch heißen"):**
5. Inhalt-Content-Flag Label → **„Amtliche Warnungen im Bericht"** in beiden Inhalt-Heimaten
   (Trip `WeatherMetricsTab` Checkbox, Vergleich `CompareInhaltSection` Toggle). Alarm-Auslöser
   bleibt **„Amtliche Warnungen lösen Alert aus"**. (Eyebrow-/Struktur-Umbau im Alarm-Tab ist D3.)

**Test-Anpassungen (altes Ownership-Modell → neues):**
- `alarme_delivery_guard_symmetry.test.ts` — der `officialAlertsEnabled`-Guard-Test wird obsolet
  (Guard entfällt); Test streichen, Guard-Symmetrie für `officialWarningsEnabled`/`channels` bleibt.
- `alarme_delivery_consolidated_save.test.ts`, `alarme_save_single_writer.test.ts` — Assertions,
  die `official_alerts_enabled` in der Payload erwarten, an das neue Ownership anpassen.

## Expected Behavior

- **Input:** Nutzer schaltet „Amtliche Warnungen im Bericht" im Inhalt-Bereich; öffnet danach den
  Alarm-Tab und ändert dort ein Alarm-Feld (z. B. Cooldown).
- **Output:** Der Inhalt-Wert bleibt erhalten; der Alarm-Tab zeigt und persistiert
  `official_alerts_enabled` nicht mehr. Im Alarm-Tab steht nur noch der Auslöser-Schalter.
- **Side effects:** Beseitigt den Last-Writer-Wins-Konflikt beim Trip (AlarmeTab überschrieb bisher
  einen im Inhalt-Tab gesetzten Wert mit seinem Initialwert).

## Acceptance Criteria

- **AC-1:** Given der Alarm-Tab eines Vergleichs oder Trips ist geöffnet / When der Nutzer den
  `official-warnings`-Abschnitt betrachtet / Then erscheint dort nur noch **ein** Schalter
  „Amtliche Warnungen lösen Alert aus" — kein zweiter „Amtliche Warnungen"-Schalter mehr.
  - Test: Rendering von `AlarmeTab` (context `route` und `vergleich`) enthält Testid
    `alerts-tab-official-alert-triggers-toggle`, aber NICHT `alerts-tab-official-alerts-toggle`.

- **AC-2:** Given ein Trip mit `official_alerts_enabled=false`, im Inhalt-Tab gesetzt / When der
  Nutzer im Alarm-Tab ein beliebiges Alarm-Feld ändert und speichert / Then bleibt
  `official_alerts_enabled` false — der Alarm-Save schreibt das Feld nicht mehr.
  - Test: `buildAlarmeDeliveryPayload(state)` enthält keinen Key `official_alerts_enabled` mehr;
    Regressions-Test über die konsolidierte Payload beweist, dass das Feld nicht mitgesendet wird.

- **AC-3:** Given der Inhalt-Bereich (Trip `WeatherMetricsTab` bzw. Vergleich
  `CompareInhaltSection`) / When der Nutzer den Content-Schalter betrachtet / Then trägt er das
  Label „Amtliche Warnungen im Bericht" und schaltet weiterhin `official_alerts_enabled`.
  - Test: Rendering beider Inhalt-Komponenten zeigt das Label „Amtliche Warnungen im Bericht"; ein
    Klick schaltet den gebundenen Zustand (`officialAlertsEnabled`/`state.officialAlertsEnabled`).

- **AC-4:** Given der Vergleich / When der Nutzer „Amtliche Warnungen im Bericht" im Inhalt-Bereich
  umschaltet und den Vergleich speichert / Then wird `official_alerts_enabled` korrekt persistiert
  (unverändertes Round-Trip-Verhalten über die Hub-Bridge, kein Regress).
  - Test: Bestehende `compare_hub_alarme_bridge`-Round-Trip-Assertions für `officialAlertsEnabled`
    bleiben grün.

- **AC-5:** Given die konsolidierte Alarm-Payload / When sie ohne `officialAlertsEnabled` gebaut
  wird / Then wirft `buildAlarmeDeliveryPayload` nicht mehr wegen fehlendem `officialAlertsEnabled`,
  und die Guards für `officialWarningsEnabled` sowie `channels` bleiben wirksam.
  - Test: Payload-Aufbau ohne `officialAlertsEnabled` ist erfolgreich; Guard-Tests für die
    verbleibenden Pflichtfelder bleiben rot-bei-Nicht-boolean.

## Known Limitations

- Struktur/Beschriftung des `official-warnings`-Abschnitts im Alarm-Tab (Eyebrow „Wann Warnungen
  rausgehen", Blockaufteilung, Radar-Einordnung) ist **D3** und NICHT Teil von D2.
- Der Fix setzt voraus, dass der Server-PUT auf `/api/trips/{id}` ein partieller Merge ist (nicht
  gesendete Felder bleiben unberührt) — dieselbe Annahme, auf der die bestehende konsolidierte
  Payload bereits beruht.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein neues Architektur-Muster. D2 entfernt eine Duplizierung im bestehenden
  geteilten Baustein und stellt Single-Writer für ein bereits existierendes Feld her — im Rahmen
  der bestehenden konsolidierten-Payload-Architektur (#1258) und der Trip/Compare-Teilungs-Invariante.

## Changelog

- 2026-07-18: Initial spec created (Scheibe D2 von Epic #1301)
