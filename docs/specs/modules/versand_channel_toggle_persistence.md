---
entity_id: versand_channel_toggle_persistence
type: module
created: 2026-07-15
updated: 2026-07-15
status: draft
version: "1.0"
tags: [frontend, versand, briefing, bugfix, issue-1243]
---

# Versand-Tab: Kanal-Toggle-Persistenz (Single Source of Truth)

## Approval

- [ ] Approved

## Purpose

Der E-Mail/Telegram/SMS-Kanal-Toggle im Versand-Tab eines bestehenden Trips schreibt heute
redundant an zwei Stellen über zwei Speicher-Wege: `report_config.send_email` (die einzige
Quelle, die der Versand-Scheduler liest) **und** zusätzlich `display_config.channels` — ein
totes Feld, das kein Codepfad auswertet. Diese Spec **entfernt den redundanten toten
Schreibweg**: eine Quelle, ein Speicher-Weg.

> **Wichtige Korrektur gegenüber der Erst-Analyse (Changelog v1.1, s.u.):** Die ursprüngliche
> Sorge war ein Daten-Verlust (`report_config.send_email` geht durch ein Debounce-Rennen
> verloren → stiller Nicht-Versand). Die genaue Ablauf-Analyse zeigt: der maßgebliche
> `send_email`-Wert wird **sofort und navigations-sicher** (`doSave` mit `keepalive:true`)
> persistiert; nur der tote Zweitschreiber kann im Rennen verloren gehen — folgenlos. Es
> wurde **kein reproduzierbarer Nutzer-Fehler** gefunden. Der Wert dieser Änderung ist daher
> **Bereinigung/Härtung** (Konsolidierung auf eine Quelle, Entfernen von totem Ballast und
> eines fragilen geteilten Timer-Musters), nicht die Behebung eines akuten Versand-Fehlers.
> PO-Entscheidung 2026-07-15: „Ballast entfernen + Staging-Check".

## Source

- **File:** `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte`
- **Identifier:** `handleChannelChange`, `weatherChannels`, `onChannelChange`-Prop an `VersandTab`
- **Schicht:** Frontend / User-UI (SvelteKit, produktive Oberfläche gregor20.henemm.com)

Nebendateien:
- `frontend/e2e/issue-736-tabs-reorg.spec.ts` (AC-4-Assertion korrigieren — s. Known Limitations)

## Estimated Scope

- **LoC:** ~ -25 / +5
- **Files:** 2 (1 Fix, 1 E2E-Assertion-Korrektur)
- **Effort:** low
- **Kein neuer Kern-„Bug-Repro"-Test** — kein reproduzierbarer Fehler vorhanden (Changelog v1.1).
  Regressionsschutz über bestehende grüne Tests; Verhaltensnachweis über Staging-Check.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `VersandTab.svelte` | shared component | route-Zweig aktualisiert `send_email` lokal + `bind:reportConfig` → Auto-Save |
| `saveStatusStore.svelte.ts` (`SaveStatus`) | store | Auto-Save-Orchestrierung; bleibt unverändert |
| `trip_alert.py` (Scheduler) | backend consumer | liest `report_config.send_*` — die Versand-Wahrheit |

## Implementation Details

```
Faktenlage (durch Investigation belegt):
- Versand-Scheduler liest AUSSCHLIESSLICH report_config.send_email/send_telegram/send_sms.
- display_config.channels wird von KEINEM Codepfad ausgewertet (totes Legacy-Feld;
  loader.py:1519 markiert es explizit als nur-durchgereicht).
- Der sichtbare Toggle-Zustand hängt an report_config (VersandTab-eigener send_email-State),
  NICHT an display_config.channels.

Fix (toggle-lokal, kein Store-Eingriff):
1. handleChannelChange (den display_config.channels-Schreibpfad) aus BriefingScheduleTab
   entfernen.
2. onChannelChange={handleChannelChange}-Prop an der VersandTab-Einbindung entfernen.
   (VersandTab ruft onChannelChange?.() optional auf → wird zum No-op, send_email wird
   weiterhin lokal gesetzt und über bind:reportConfig auto-gespeichert.)
3. Totes weatherChannels-State + ungenutzten ChannelConfig-Import entfernen.

Danach persistiert der Kanal-Toggle nur noch über den EINEN report_config-Auto-Save-Weg
(VersandTab.$effect → bind:reportConfig → BriefingScheduleTab.$effect → doSave).
Kein konkurrierender schedule() → das Debounce-Rennen an dieser Stelle ist strukturell weg.

Bewusst NICHT im Scope: der latente SaveStatus.doSave()-Defekt (_timer=null ohne
clearTimeout). Berührt alle Editoren → höherer Blast Radius, kein anderswo bewiesenes
Nutzer-Symptom → Nebenbefund-Sammel-Eintrag #1199, kein eigenes Issue.
```

## Expected Behavior

- **Input:** Nutzer schaltet im Versand-Tab eines bestehenden Trips einen Kanal um.
- **Output:** `report_config.send_<kanal>` wird zuverlässig auf den neuen Wert persistiert.
- **Side effects:** Kein `display_config.channels`-Schreibvorgang mehr durch den Toggle.
  Compare-Zweig und Trip-Neuanlage-Wizard bleiben unverändert.

## Acceptance Criteria

> **Nachweis-Modell (nach Changelog v1.1):** Es gibt keinen reproduzierbaren Nutzer-Fehler,
> der sich „rot vor Fix" zeigen ließe (die `send_email`-Persistenz ist bereits korrekt). Der
> Nachweis ist daher: (a) **empirischer Staging-Check** — realer Toggle, danach persistierten
> Trip inspizieren; (b) **grüne Bestandstests** als Regressionsschutz; (c) Code-Review, dass
> der `display_config.channels`-Schreibweg entfernt ist. Kein neuer Kern-„Bug-Repro"-Test —
> das wäre bei fehlendem Fehler Theater.

- **AC-1:** Given ein gespeicherter Trip mit aktivem E-Mail-Kanal / When der Nutzer im
  Versand-Tab den E-Mail-Kanal ausschaltet / Then trägt der danach persistierte Trip
  `report_config.send_email = false` (der Wert, den der Versand-Scheduler liest)
  - Nachweis: Staging-Check — Toggle real auslösen, Trip via API/Store laden, `send_email`
    prüfen. Zusätzlich bleibt der bestehende Mapping-Guard
    `issue_617_briefing_channel_gating.test.ts` (`syncSendFlags`) grün.

- **AC-2:** Given der Nutzer schaltet im Versand-Tab einen Kanal um / When die Änderung
  gespeichert wird / Then wird kein `display_config.channels` mehr geschrieben — die
  Kanal-Entscheidung hat genau eine Quelle (`report_config.send_*`)
  - Nachweis: Code-Review (Schreibweg entfernt) + Staging-Check, dass ein Toggle den
    persistierten `display_config.channels`-Wert nicht mehr verändert.

- **AC-3:** Given der Orts-Vergleich-Editor (vergleich-Zweig des geteilten VersandTab) / When
  ein Nutzer dort einen Kanal umschaltet / Then persistiert das unverändert über den
  bestehenden `wiz.*`-Weg — das Verhalten des vergleich-Zweigs ändert sich nicht
  - Nachweis: bestehende Compare-Kanal-Tests bleiben grün; kein Edit am vergleich-Zweig.

- **AC-4:** Given der Trip-Neuanlage-Wizard (`TripNewEditor`, `createMode`) / When ein Nutzer
  dort Kanäle auswählt / Then werden `report_config.send_email/send_telegram/send_sms`
  korrekt gesetzt — der `syncSendFlags`-Pfad über `WeatherMetricsTab.channels` bleibt intakt
  - Nachweis: bestehende Neuanlage-Wizard-Kanaltests bleiben grün; `WeatherMetricsTab` wird
    nicht angefasst.

## Known Limitations

- **Kein reproduzierbarer Nutzer-Fehler.** Die `report_config.send_email`-Persistenz ist
  bereits heute korrekt (sofortiger, navigations-sicherer `doSave`). Entfernt wird nur toter,
  folgenloser Ballast. Deshalb kein „rot-vor-Fix"-Test.
- Der historische `display_config.channels`-Wert bestehender Trips bleibt als totes
  Legacy-Feld erhalten (nicht rückmigriert); da ihn kein Codepfad liest, ist das folgenlos.
- Der latente `SaveStatus.doSave()`-Defekt (`_timer=null` ohne `clearTimeout`) wird NICHT
  gefixt (Blast Radius über alle Editoren) → Sammel-Eintrag #1199.
- Der fixmed E2E-Test `issue-736-tabs-reorg.spec.ts` AC-4 wird in seiner **Assertion
  korrigiert**: Nach dem Fix schreibt der Toggle `display_config.channels` nicht mehr, d.h.
  die alte Erwartung `expect(display_config.channels.email).toBe(true)` wäre falsch — sie
  entfällt, geprüft wird nur noch `report_config.send_email`. Der `test.fixme`-Grund (Timeout
  F011) ist ein separater E2E-Infrastruktur-Befund und bleibt bestehen (Test läuft weiter
  nicht automatisch); die Korrektur verhindert lediglich eine falsche Assertion als Landmine
  für ein späteres Un-fixme.

## Changelog

- **v1.1 (2026-07-15):** Umgewidmet von „Bugfix Daten-Verlust" zu **Bereinigung/Härtung**.
  Ablauf-Analyse ergab, dass `report_config.send_email` zuverlässig persistiert wird (kein
  Rennen-bedingter Verlust); nur der tote `display_config.channels`-Zweitschreiber ist real.
  ACs auf Staging-Check + grüne Bestandstests umgestellt, neuer Kern-„Bug-Repro"-Test
  gestrichen, Scope 3→2 Dateien. PO-Entscheidung „Ballast entfernen + Staging-Check".
- **v1.0 (2026-07-15):** Erstfassung (Annahme: Debounce-Rennen verliert `send_email`).
