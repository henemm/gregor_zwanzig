# Context: fix-1738-versand-tab-migration

**Issue:** #1738 — Premium-SMS-Schalter verschwindet auf `/trips/new`, wenn die SMS-Wetter-Metrik ausgeblendet wird
**Track:** Full Process · **PO-Entscheid im Intake:** Weg 2 (`/trips/new` auf den geteilten `VersandTab` umstellen), nicht die kleine Entschachtelung.

## Request Summary

Auf der Trip-Anlage hängt der Premium-SMS-Schalter im Markup innerhalb von `{#if weatherVisible.sms}` — eine Anzeige-Einstellung für Wetter-Metriken versteckt damit den Zugang zum Satellitenkanal. Statt die Verschachtelung punktuell aufzulösen, soll `/trips/new` auf den geteilten `shared/VersandTab.svelte` umgestellt werden; damit fällt der Fall zusammen mit der Doppelpflege der Kanal-Logik weg (Teilungsregel, #1199).

## Kernbefunde der Recherche

### B1 — Der Bug ist breiter als das Issue beschreibt

Nicht nur Premium-SMS ist betroffen. Alle drei Kanal-Blöcke hängen an ihrer jeweiligen Metrik-Sichtbarkeit:

| Kanal | Gate | Datei:Zeile |
|---|---|---|
| E-Mail | `{#if weatherVisible.email}` | `edit/EditReportConfigSection.svelte:333` |
| Telegram | `{#if weatherVisible.telegram}` | `edit/EditReportConfigSection.svelte:355` |
| SMS | `{#if weatherVisible.sms}` | `edit/EditReportConfigSection.svelte:377` |
| **Premium-SMS** | zusätzlich **innerhalb** des SMS-Blocks | `edit/EditReportConfigSection.svelte:401-427` |

`weatherVisible = visibleChannels(weatherChannels)` (`:127`), Logik in `trip-detail/briefingChannelGating.ts:14-19`. Ohne `weatherChannels` sind alle sichtbar — deshalb tritt der Bug **nur** auf `/trips/new` auf (einziger Aufrufer, der `weatherChannels` mitgibt).

Premium-SMS ist der schwerwiegendste Fall: doppelt verschachtelt und laut ADR-0049 ein eigenständiger, gleichrangiger Kanal, der mit normalem SMS nichts zu tun hat.

### B2 — `VersandTab` funktioniert ohne persistiertes Trip (Intake-Unsicherheit entkräftet)

Der `trip`-Prop ist optional (`shared/VersandTab.svelte:31`) und wird im gesamten Skript-Körper **einmal** benutzt: `computeTripEnd(trip)` (`:221`), das bei `undefined` null-sicher `null` liefert (`:208-220`). Kein API-Call, keine Persistenz-Abhängigkeit in der Komponente.

**Präzedenzfall:** `compare-new/CompareNewEditor.svelte:420,502` fährt `VersandTab` bereits in einem Anlege-Flow ohne persistiertes Objekt — über einen reinen In-Memory-`$state` (`CompareWizardState`), ein einziger POST erst beim Aktivieren. Genau das Muster, das `/trips/new` braucht. Spec dazu: `docs/specs/modules/versand_tab_vergleich.md` (Doppel-Mount, **kein Self-Save**, zentrales `handleSave`).

### B3 — Was bei einer 1:1-Substitution verlorenginge

`VersandTab`/`VTBriefingChannels` haben Folgendes **nicht**:

1. **`weatherChannels`-Gating** — `visibleChannels`/`hasNoActiveChannel`/`activeChannelLabels` und der Leerzustand-Banner `briefings-channel-empty` (gegated auf `weatherChannels`).
2. **`syncSendFlags`-Write-Back** — `EditReportConfigSection` setzt beim Schreiben `send_email/telegram/sms := false`, wenn der jeweilige Wetter-Kanal aus ist (`briefingChannelGating.ts:49-61`, aufgerufen `:264-266`). `VersandTab`s `$effect` (`:127-148`) ist reiner Passthrough.
3. **Mail-Inhalt-Karte** — `email_format` full/compact + `show_outlook`/`show_stage_stats`/`show_yesterday_comparison` (`EditReportConfigSection.svelte:435-514`). `VersandTab` rendert sie gar nicht.

Zu 3 verifiziert: `shared/WeatherMetricsTab.svelte:1737` rendert die Mail-Inhalt-Karte hinter `{#if !createMode …}` — im Anlege-Flow also **nicht**. Auf `/trips/new` kommt sie heute ausschließlich aus dem `EditReportConfigSection` im Zeitplan-Tab. Ein reiner Komponententausch entfernt sie dort ersatzlos.

Kein Gap dagegen bei: `profile.sms_allowed`-Hinweis, `channelConnectionStatus`/`channelContactLabel`/`premiumSmsChannelState` (bereits geteilte Imports), Kanalzähler inkl. Premium-SMS (`VersandTab.svelte:157-159`), Zeitplan (`VTSchedulePlan` ist bereits geteilt, #1286).

### B4 — Doppel-Mount Desktop/Mobile

`EditReportConfigSection` wird **zweimal simultan** gemountet: `trip-new/TripNewEditor.svelte:800` (Desktop) und `:1036` (Mobile). Die Umschaltung ist **CSS-only** (`display:none` per Breakpoint, `:1088-1109`) — beide Instanzen leben parallel im DOM.

Gegenmuster in derselben Datei: `WeatherMetricsTab` (`:823`/`:1051`) hält per JS-Flag `isMobileViewport` bewusst nur **eine** Instanz — der Kommentar `:812-822` benennt genau diese Fehlerklasse (doppelte Kopie = doppelter unabhängiger Schreibpfad, Fix-Loop 4). Bei `EditReportConfigSection` fehlt das Gating; es fällt bisher nicht auf, weil `bind:reportConfig` two-way teilt statt über Callback-Rückkanal zu laufen. **Bei der Migration explizit gegenprüfen** — `versand_tab_vergleich.md` löst denselben Fall über „kein Self-Save".

### B5 — `stubTrip.stages` ist leer

`trip-new/TripNewEditor.svelte:86-93` hält einen `stubTrip` mit **fest verdrahtetem `stages: []`**, nie aus dem echten `stages`-State befüllt. `VersandTab`s `VTLaufzeitRoute` berechnet das Trip-Ende über `trip.stages` (`computeTripEnd`) — mit dem heutigen Stub bliebe die Laufzeit-Anzeige im Anlege-Flow leer.

### B6 — Der Dedupe-Wächter wird gegenstandslos

`shared/versand-tab/__tests__/channel_checkbox_dedupe_render.test.ts` SSR-rendert `EditReportConfigSection.svelte` **direkt per Pfad-Import** und vergleicht sie Feld für Feld mit `VTBriefingChannels`/`VersandTab` (Testids, Disabled-Zustände, Kanalzähler, Leerzustand). Zweck laut Dateikopf: zwei divergente Implementierungen synchron halten.

Nach der Migration gibt es nur noch **eine** Implementierung — der Test bewacht dann nichts mehr. Er darf nicht einfach gestrichen werden, ohne dass klar ist, was danach die Positivkontrolle stellt (vgl. Lehre „Übergangs-Ausnahme ist oft die einzige Positivkontrolle").

## Related Files

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | Migrationsziel; 2 Mounts (`:800`, `:1036`), `stubTrip` `:86-93`, `buildAndSave` `:335-364` |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` | Tab-Freischaltung `:14-44`, `canSave` `:69-70`, `buildCreateTripPayload` `:117-156` |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | Bug-Ort; bleibt bestehen (siehe „Lebende Aufrufer") |
| `frontend/src/lib/components/shared/VersandTab.svelte` | Zielkomponente, 342 Z. |
| `frontend/src/lib/components/shared/versand-tab/VTBriefingChannels.svelte` | Kanal-Block, Premium-SMS-Gating über Prop-Anwesenheit `:198` |
| `frontend/src/lib/components/trip-detail/briefingChannelGating.ts` | `visibleChannels` `:14-19`, `syncSendFlags` `:49-61` |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | `:1737` `createMode`-Gate der Mail-Inhalt-Karte; `:1758` zweiter lebender Aufrufer |
| `frontend/src/lib/components/compare-new/CompareNewEditor.svelte` | Präzedenz Anlege-Flow `:420`, `:502` |
| `frontend/src/lib/components/compare/compareWizardState.svelte.ts` | Muster In-Memory-State vor erstem Save |

### Lebende vs. tote Aufrufer von `EditReportConfigSection`

| Aufrufer | Status |
|---|---|
| `trip-new/TripNewEditor.svelte:800,1036` | **lebend** — Migrationsziel |
| `shared/WeatherMetricsTab.svelte:1758` | **lebend**, nur Mail-Inhalt (`showChannels={false} showSchedule={false}`) — Komponente kann daher **nicht gelöscht** werden |
| `edit/TripEditView.svelte:203` | tot — nirgends gemountet |
| `briefings-tab/BriefingsTab.svelte:40` | tot — importiert in `TripTabs.svelte:14`, im Template nie verwendet |

Aufräumen der beiden toten Pfade gehört **nicht** in #1738 (eigenes Ticket).

## Existing Specs & ADRs

- `docs/specs/modules/versand_tab_route.md` — AC-7 fixiert Testids: `channel-email`, `channel-telegram`, `channel-sms`, `briefings-channel-empty`, `report-morning-time`, `report-evening-time`, `morning-master-switch`, `evening-master-switch`, `report-mail-content`
- `docs/specs/modules/versand_tab_vergleich.md` — **das nächstliegende Vorbild**: Create-Fall, Doppel-Mount, kein Self-Save, Testid-Präfix parametrisierbar
- `docs/specs/modules/feat_1717_s3_premium_sms_ui.md` — schaltet Premium-SMS heute in **beiden** Komponenten parallel frei; benennt unter „Abgrenzung" (`:41-44`) genau die Migration, die #1738 jetzt einlöst. **AC-1 sichert: schaltbarer Premium-SMS-Block erscheint nie im `vergleich`-Zweig** (Gating über Prop-Anwesenheit, nicht `context`-String) — muss erhalten bleiben
- `docs/specs/modules/refactor_1286_shared_versandzeit.md` — hat den Zeitplan bereits geteilt (`VTSchedulePlan`)
- `docs/adr/0049-premium-sms-vierter-kanal.md` — Premium-SMS eigener 4. Kanal, gelernte Rückadresse, Tier-Gate `premium`
- Keine aktive `trip_new`-Spec; `issue_622_trip_new_progressive_editor.md` / `issue_661_trip_new_mobile.md` liegen im Archiv

## Tests & Gates

**Vitest**
- `shared/versand-tab/__tests__/channel_checkbox_dedupe_render.test.ts` — importiert `EditReportConfigSection.svelte` per Pfad; wird durch die Migration gegenstandslos (B6)
- `edit/__tests__/report_config_uses_shared_schedule.test.ts` — 4 von 6 Tests lesen `EditReportConfigSection.svelte` per `readFileSync`; überleben, solange die Datei existiert (tut sie, wegen `WeatherMetricsTab`)
- `edit/issue_619_report_config_write.test.ts`, `edit/issue_693_email_config_cleanup.test.ts` — testen nur `reportConfigWrite.ts`, unberührt
- `trip-new/__tests__/trip_new_editor_weather_metrics_wiring.test.ts` — Quelltext-Regex, erwartet **exakt 2** `WeatherMetricsTab`-Mounts; Mount-Struktur muss erhalten bleiben
- `trip-new/__tests__/tripNewLogic.test.ts` — reine Logik, unberührt

**Playwright**
| Spec | fährt `/trips/new` an | in `ci_e2e_specs.txt` | Versand-Testids |
|---|---|---|---|
| `issue-661-trip-new-mobile.spec.ts` | ja | **ja** | nein |
| `versandzeit-stundenwahl.spec.ts` (AC-4) | ja | nein | `report-morning-time` |
| `trip-new-loads-without-effect-loop.spec.ts` | ja | nein | nein |
| `trip-edit.spec.ts` | ja (nur Seeding) | nein | ⚠️ nutzt `wizard-next`/`wizard-save` — Verdacht auf Bestandsleiche, in der Spec-Phase gegenprüfen |
| `versand-tab.spec.ts` | nein (`/trips/{id}`) | **ja** | ja — Referenz für einen korrekten VersandTab-E2E-Test |

Der eigentliche Verhaltensnachweis für Kanäle auf `/trips/new` hängt damit **außerhalb** der CI-Ampel.

**Gates**
- Pendant-Sperre `.claude/hooks/pendant_gate.py` (`docs/specs/modules/feat_1481b_pendant_gate.md`, Prüfdatum 2026-11-03): blockiert **Neuanlagen** unter `trip-new/**` ohne `gz-eigenstaendig:`-Begründung. Ein Adapter für den unpersistierten State gehört daher nach `shared/**` — oder braucht eine Begründung.
- Kein Wächtertest erzwingt heute, dass `/trips/new` keine eigene Kanal-Komponente hat. Die Teilungsregel ist dort nur als Prosa-Kommentar und Backlog-Buchung dokumentiert.

## PO-Entscheidungen (2026-08-17, Phase 2)

**E1 — Die Kanal-Kopplung fällt.** Alle vier Versandkanäle sind auf `/trips/new` künftig immer wählbar, unabhängig von der Metrik-Darstellung. Damit verschwindet der Bug für **alle vier** Kanäle, nicht nur Premium-SMS, und Anlage verhält sich wie Trip-Detail. `weatherChannels`-Gating, Leerzustand-Banner-Gating und `syncSendFlags` entfallen auf diesem Pfad. Bewusst in Kauf genommen: ein Kanal kann versendet werden, ohne dass für ihn Wetter-Metriken konfiguriert sind — im Trip-Detail heute bereits möglich. Begründung: „Keine Bevormundung — der Nutzer entscheidet, was wichtig ist" (CLAUDE.md); ein Versandkanal ist keine Metrik-Darstellung.

**E2 — Die Mail-Inhalt-Karte bleibt im Zeitplan-Tab.** `EditReportConfigSection` bleibt dort gemountet, aber nur noch mit `showChannels={false} showSchedule={false}` — exakt das Muster, das `WeatherMetricsTab.svelte:1758` bereits benutzt. Der Bug verschwindet damit **strukturell**: der Kanal-Block kommt gar nicht mehr aus dieser Komponente. Kein Rückkanal-Umbau nötig, `bind:reportConfig` trägt weiter. `createMode` wird ausschließlich von `TripNewEditor` gesetzt (`WeatherMetricsTab.svelte:173` + Aufrufer `:825`, `:1053`) — Compare ist von dieser Entscheidung nicht berührt.

## Analyse-Ergebnisse (Phase 2, technische Entscheidungen)

### A1 — Doppel-Mount: XOR-Gate über `isMobileViewport`

`VersandTab`s `$effect` (`:126-148`) hängt **nur** von lokalem `$state` ab, nicht vom eingehenden `reportConfig`-Prop (der wird einmalig in `onMount` `:91-124` gelesen). Daraus folgt: **keine** Endlosschleife wie bei `WeatherMetricsTab`, aber ein **Last-Write-Wins-Race** — beide Instanzen initialisieren `originalReportConfig` aus ihrem eigenen Mount-Snapshot und schreiben unabhängig zurück. Ein auf Mobile gesetzter Wert kann bei einem späteren Resize/Re-Mount still von der Desktop-Instanz aus veraltetem Snapshot überschrieben werden — Datenverlust ohne Fehlermeldung.

`EditReportConfigSection` hat heute strukturell **denselben** Race (`:200-211` / `:224-267`, ebenfalls CSS-only doppelt gemountet). Er ist bisher nur nicht aufgefallen, nicht abwesend.

**Entscheidung: XOR-Gate.** Zwei Präzedenzfälle sprechen dafür, beide im unmittelbaren Umfeld:
- `TripNewEditor.svelte:823` / `:1051` macht es für `WeatherMetricsTab` bereits so — `isMobileViewport` ist in **derselben Datei** schon vorhanden (`:76-83`, `matchMedia('(max-width: 899px)')` + change-Listener). Anlass war Fix-Loop 4 / #1552 (`effect_update_depth_exceeded`).
- `CompareNewEditor.svelte:393,402,490,494` gatet `VersandTab` **selbst** bereits per XOR.

Der verbleibende Grenzfall (Resize mountet neu, lokaler State geht verloren) ist unkritisch, weil der Prop bei jedem Mount frisch aus dem aktuellen `reportConfig` initialisiert wird — Neu-Einlesen statt Überschreiben aus altem Snapshot.

### A2 — Ersatz für den Dedupe-Wächter

Nach der Migration existiert nur noch eine Kanal-Implementierung; `channel_checkbox_dedupe_render.test.ts` bewacht dann nichts mehr. Der Ersatz ist zugleich der zentrale RED-Test: `/trips/new` rendert die geteilte Komponente **und** alle vier Kanal-Zeilen — insbesondere Premium-SMS — bleiben sichtbar, wenn `display_config.channels` einen Kanal abwählt. Der alte Test darf erst fallen, wenn der neue rot war und dann grün wurde.

### A3 — Laufzeit-Anzeige: `stubTrip.stages` befüllen

`StageLocal` (`TripNewEditor.svelte:52-56`) hat **kein** `date`-Feld; `computeTripEnd` liest genau `s.date` (ISO). Mit dem heutigen `stages: []` zeigt `VTLaufzeitRoute` dauerhaft „endet —" (`VTLaufzeitRoute.svelte:25`, `tripEnd ?? '—'`) — kein Crash, sauber degradiert, aber unbefüllt.

**Entscheidung: befüllen** über die bereits existierende Ableitung `buildCreateTripPayload(state).stages` (`tripNewLogic.ts:117-124`, nutzt intern `addDaysISO` `:107-115`). **Falle:** `stageDate()` (`tripNewLogic.ts:48-57`) liefert `dd.mm.` ohne Jahr — für `s.date` unbrauchbar, `computeTripEnd` bräche daran still.

### A4 — `trip-edit.spec.ts` ist eine Bestandsleiche

Die Testids `wizard-next`/`wizard-save` existieren nirgends mehr in `frontend/src/` (mit #622 abgeschafft); `trip-name-input` lebt nur noch in `edit/EditRouteSection.svelte:151`, eingebunden ausschließlich von der seit #616 nicht mehr gerouteten `TripEditView.svelte`. Der Spec steht **nicht** in `.github/ci_e2e_specs.txt`, hat keinen Skip-Marker — er läuft in CI nicht und wäre manuell strukturell rot.

**Kein Blocker für #1738.** Nebenbefund → Sammel-Issue #1199 (kein nutzersichtbares Fehlverhalten, kein fälschlich blockierendes Gate).

## Risks & Considerations

- **Sicherheitskanal betroffen:** Premium-SMS ist auf der Hütte der einzige empfangbare Kanal. Eine Regression hier ist schwerer als der Bug selbst.
- **Geteilte Komponente:** `VersandTab` bedient auch Trip-Detail und beide Compare-Editoren. Jede Änderung *an* `VersandTab` wirkt dort mit; Änderungen sollten möglichst im Aufrufer bleiben.
- **AC-1 aus #1717** darf nicht reißen: Premium-SMS nie im `vergleich`-Zweig, Gating über Prop-Anwesenheit.
- **Schreibpfad-Duplikat** durch Doppel-Mount ist eine dokumentierte Fehlerklasse dieses Editors (Fix-Loop 4).
- Kein Datenverlust-Risiko am Versandpfad selbst: `report_config.send_premium_sms` wird weiter ausgewertet, es geht um Bedienbarkeit.
