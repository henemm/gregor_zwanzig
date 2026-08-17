---
entity_id: fix_1738_trips_new_versand_tab
type: module
created: 2026-08-17
updated: 2026-08-17
status: draft
version: "1.0"
tags: [trip-new, versand-tab, premium-sms, teilungsregel, issue-1738]
---

# Trip-Anlage nutzt den geteilten Versand-Baustein

## Approval

- [x] Approved (PO, 2026-08-17)

## Purpose

Auf `/trips/new` hängen die Versandkanäle im Markup innerhalb der Sichtbarkeits-Bedingung ihres jeweiligen Wetter-Metrik-Kanals — Premium-SMS zusätzlich noch innerhalb des SMS-Blocks. Wer die SMS-Wetter-Metrik abwählt, verliert damit den Schalter für den Satellitenkanal, ohne einen Hinweis zu sehen. Diese Spec stellt die Kanal- und Zeitplan-Fläche der Trip-Anlage auf den geteilten `VersandTab` um (Teilungsregel, #1199) und beseitigt die Kopplung damit strukturell für alle vier Kanäle.

## Source

- **Schicht:** Frontend / User-UI (SvelteKit)
- **File:** `frontend/src/lib/components/trip-new/TripNewEditor.svelte`
- **Identifier:** Zeitplan-Tab, Mounts bei `:800` (Desktop) und `:1036` (Mobile)

## Estimated Scope

- **LoC:** ~120–180 (Produktivcode), zzgl. Tests ~150–200
- **Files:** 3 Produktivdateien (`TripNewEditor.svelte`, `tripNewLogic.ts`, ggf. `VersandTab.svelte`), 2–3 Testdateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `shared/VersandTab.svelte` | Komponente | Zielkomponente, `context="route"` |
| `shared/versand-tab/VTBriefingChannels.svelte` | Komponente | Kanal-Block inkl. Premium-SMS |
| `shared/versand-tab/VTLaufzeitRoute.svelte` | Komponente | Laufzeit-Anzeige, braucht `tripEnd` |
| `trip-new/tripNewLogic.ts` | Modul | `buildCreateTripPayload` liefert datierte Etappen |
| `edit/EditReportConfigSection.svelte` | Komponente | bleibt für die Mail-Inhalt-Karte |
| `docs/specs/modules/versand_tab_route.md` | Spec | Testids AC-7 |
| `docs/specs/modules/feat_1717_s3_premium_sms_ui.md` | Spec | AC-1: Premium-SMS nie im `vergleich`-Zweig |
| `docs/adr/0049-premium-sms-vierter-kanal.md` | ADR | Premium-SMS als eigener vierter Kanal |

## Implementation Details

Im Zeitplan-Tab von `TripNewEditor` tritt `VersandTab` (`context="route"`) an die Stelle des Kanal- und Zeitplan-Teils von `EditReportConfigSection`. `EditReportConfigSection` bleibt dort gemountet, aber nur noch für die Mail-Inhalt-Karte:

```
<VersandTab context="route" trip={stubTrip} bind:reportConfig onJump={switchTab} />
<EditReportConfigSection bind:reportConfig mode="create"
                         showChannels={false} showSchedule={false} />
```

Damit kommt der Kanal-Block gar nicht mehr aus der Komponente, in der die Verschachtelung sitzt — der Bug verschwindet strukturell statt durch eine punktuelle Entschachtelung.

Beide Mounts (Desktop/Mobile) werden auf das bereits in derselben Datei vorhandene XOR-Gate `isMobileViewport` (`:76-83`) gelegt, wie es `WeatherMetricsTab` (`:823`/`:1051`) und `CompareNewEditor` für `VersandTab` selbst (`:393,402,490,494`) bereits tun.

`stubTrip.stages` wird aus der bestehenden Ableitung `buildCreateTripPayload(state).stages` befüllt, damit `computeTripEnd` ein Datum findet. `stageDate()` ist dafür unbrauchbar (Format `dd.mm.` ohne Jahr).

Das `weatherChannels`-Gating entfällt auf diesem Pfad ersatzlos (PO-Entscheid E1): kein `visibleChannels`, kein `syncSendFlags`, kein an `weatherChannels` gekoppelter Leerzustand.

## Expected Behavior

- **Input:** Nutzer legt unter `/trips/new` einen Trip an und wählt im Metriken-Tab Wetter-Kanäle ab bzw. im Zeitplan-Tab Versandkanäle an.
- **Output:** Der Zeitplan-Tab zeigt alle vier Versandkanäle unabhängig von der Metrik-Auswahl; gesetzte Kanäle landen beim Speichern in `report_config`.
- **Side effects:** `report_config.send_email/telegram/sms` wird nicht mehr still auf `false` zurückgesetzt, wenn der zugehörige Wetter-Kanal abgewählt ist.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer legt unter `/trips/new` einen Trip an und hat im Metriken-Tab den Wetter-Kanal SMS abgewählt / When er den Zeitplan-Tab öffnet / Then ist die Premium-SMS-Zeile mitsamt ihrem Schalter sichtbar und bedienbar.
  - Test: Render der Trip-Anlage mit `display_config.channels` ohne `sms`; die Premium-SMS-Checkbox ist im Zeitplan-Tab vorhanden und nicht deaktiviert.

- **AC-2:** Given derselbe Nutzer mit abgewähltem Wetter-Kanal SMS / When er den Zeitplan-Tab öffnet / Then sind auch die Zeilen für E-Mail, Telegram und SMS sichtbar — die Sichtbarkeit eines Versandkanals hängt an keiner Metrik-Auswahl mehr.
  - Test: Render mit je einem abgewählten Wetter-Kanal; alle vier Kanal-Zeilen bleiben in jeder Kombination vorhanden.

- **AC-3:** Given ein Nutzer hat auf `/trips/new` den Premium-SMS-Schalter gesetzt / When er den Trip speichert / Then enthält der angelegte Trip `report_config.send_premium_sms = true`, unabhängig davon, welche Wetter-Kanäle aktiv sind.
  - Test: Zustand setzen, Speicher-Payload prüfen; kein stilles Zurücksetzen durch ein Gating.

- **AC-4:** Given die Trip-Anlage ist geöffnet / When der Zeitplan-Tab gerendert wird / Then stammt der Kanal-Block aus dem geteilten Baustein — die Kanal-Testids `channel-email`, `channel-telegram`, `channel-sms`, `channel-premium-sms` erscheinen dort genau einmal, nicht doppelt aus zwei Implementierungen.
  - Test: Render des Zeitplan-Tabs; je Testid genau ein Treffer im Dokument.

- **AC-5:** Given die Trip-Anlage wird auf einer schmalen und auf einer breiten Ansicht geöffnet / When der Zeitplan-Tab gerendert wird / Then existiert zu jedem Zeitpunkt genau eine Versand-Instanz im Dokument, nie zwei gleichzeitig.
  - Test: Render unter beiden Viewport-Bedingungen; die Zahl der Versand-Instanzen ist jeweils exakt 1.

- **AC-6:** Given ein Nutzer stellt auf `/trips/new` das Mail-Format oder einen Inhaltsbaustein ein / When er den Trip speichert / Then sind diese Einstellungen im angelegten Trip enthalten — die Mail-Inhalt-Karte bleibt im Anlege-Flow erreichbar.
  - Test: Format `compact` und einen Inhaltsbaustein setzen, Speicher-Payload prüfen.

- **AC-7:** Given ein Trip mit gesetztem Startdatum und mehreren Etappen wird angelegt / When der Zeitplan-Tab gerendert wird / Then zeigt die Laufzeit-Angabe das aus Startdatum und Etappenzahl abgeleitete Enddatum statt eines Platzhalters.
  - Test: Startdatum + 3 Etappen setzen; die Laufzeit-Zeile nennt das erwartete Enddatum.

- **AC-8:** Given der Ortsvergleich-Editor / When sein Versand-Bereich gerendert wird / Then erscheint dort weiterhin kein schaltbarer Premium-SMS-Block, sondern der feste Platzhalter — die Zusicherung aus #1717 AC-1 bleibt unberührt.
  - Test: Render des Compare-Versandbereichs; keine bedienbare Premium-SMS-Checkbox.

## Known Limitations

- Ein Versandkanal kann künftig aktiv sein, ohne dass für ihn Wetter-Metriken konfiguriert sind. Das ist der bewusst gewählte PO-Entscheid E1 und entspricht dem Verhalten, das das Trip-Detail heute schon zeigt.
- `EditReportConfigSection.svelte` bleibt bestehen (zweiter lebender Aufrufer: `WeatherMetricsTab.svelte:1758` für die Mail-Inhalt-Karte). Die Kanal-Verschachtelung bleibt als toter Zweig in der Datei stehen, ist aber von keinem Aufrufer mehr erreichbar, da beide verbleibenden Aufrufer `showChannels={false}` setzen.
- `edit/TripEditView.svelte` und `briefings-tab/BriefingsTab.svelte` sind toter Bestand (nirgends gemountet). Ihr Rückbau gehört nicht in diese Scheibe.
- `frontend/e2e/trip-edit.spec.ts` ist eine Bestandsleiche (referenziert den mit #622 abgeschafften Wizard, steht nicht in `.github/ci_e2e_specs.txt`). Nebenbefund → #1199.
- Der bisherige Gleichhalte-Test `shared/versand-tab/__tests__/channel_checkbox_dedupe_render.test.ts` verliert seinen Gegenstand, sobald nur noch eine Implementierung existiert. Er darf erst entfallen, wenn die Tests zu AC-1/AC-2/AC-4 rot waren und dann grün wurden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue nötig
- **Rationale:** Die Entscheidung, Trip und Ortsvergleich möglichst viel Code teilen zu lassen, steht bereits in CLAUDE.md und Epic #1230; diese Scheibe löst nur eine bekannte, in #1199 gebuchte Abweichung ein. ADR-0049 (Premium-SMS als vierter Kanal) bleibt unverändert gültig und wird durch AC-8 geschützt.

## Changelog

- 2026-08-17: Initial spec created (Issue #1738, Track Full Process)
