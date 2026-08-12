# Context: fix-1745-alarm-kanaele-premium-sms

**Issue:** [#1745](https://github.com/henemm/gregor_zwanzig/issues/1745) · Label `bug`, `priority:high`, `session:khw`
**Track:** Full Process (Intake-Summe 5) · **Phase 1 abgeschlossen 2026-08-11**
**Erhebung:** drei parallele Explore-Agenten (Frontend-Kette / Python-Alarmpfad / Go+Vertrag+Specs), Befunde
stichprobenartig vom Orchestrierer am Code gegengeprüft.

## Request Summary

Zwei zusammenhängende Befunde: (1) Der Alarme-Reiter kennt den vierten Kanal **Premium-SMS**
(Garmin inReach) nicht, obwohl das Backend ihn seit #1701 vollständig verarbeitet. (2) Der
Radar-/Regen-Alarm löst seine Kanäle ausschließlich aus den **Briefing**-Flags auf und ignoriert
die Alarm-Kanal-Auswahl komplett — für alle vier Kanäle, nicht nur den neuen.

## 🔴 PO-Entscheid 2026-08-11 (Grundlage der Spec)

**Radar-/Regen-Alarme folgen künftig dem scharfen Alarm-Kanal-Satz** (`trip.alert_channels`) wie
alle anderen Alarmtypen — EIN Auflösungsweg. Fallback auf die Briefing-Kanäle nur, wenn
`alert_channels` nie gesetzt wurde.

**Ausdrücklich nicht gewählt:** „Trennung bleibt, wird nur angezeigt" · „Ist-Zustand einfrieren"
(keine Migration, die `premium_sms` in `alert_channels` hineinschreibt). Folge für den KHW-Trip:
Regen-Alarme gehen künftig an E-Mail/Telegram/SMS; Premium-SMS erst, wenn der PO den Haken im
Alarme-Reiter selbst setzt. Bewusst in Kauf genommen, mit der roten Linie aus #1258 S3 AC-15
(kein *stiller* Kanal-Wechsel) besprochen.

## Ausgangslage: Das Backend ist fertig, die Oberfläche fehlt

Die naheliegende Annahme „der vierte Kanal muss überall nachgezogen werden" ist **falsch**.
Gemessener Ist-Stand:

| Schicht | `premium_sms` im Alarm-Kanal-Satz? | Beleg |
|---|---|---|
| Go-Modell | ✅ vorhanden | `internal/model/trip.go:198-217` — `AlertChannelsConfig.PremiumSms *bool` **und** `AlertChannelThresholdsConfig.PremiumSms *string` |
| Go-Handler (Merge) | ✅ vorhanden | `internal/handler/trip.go:371-407` — Feld-Level-Merge für alle vier Felder |
| Python, scharfer Zweig | ✅ vorhanden | `trip_alert.py:1518-1525`, Tier-Gate `:1544-1545` |
| Python, Vererbungszweig | ✅ vorhanden | `_briefing_channels`, `trip_alert.py:1548-1562` — **vier** Kanäle (selbst nachgemessen) |
| Python, Kanal-Schwellen | ✅ funktioniert generisch | `alert_channel_threshold.py:20-35` — unbekannter Kanal fällt auf `DEFAULT_CHANNEL_THRESHOLD = "LOW"`, wird also **nie** unterdrückt. Kein Absturz, kein Durchfallen |
| Python, Ortsvergleich | ✅ vorhanden | `compare_alert_channels.py:44-45` |
| Python, Radar-Pfad | ⚠️ Kanal vorhanden, **Quelle falsch** | `trip_alert.py:847-855` kennt `premium_sms`, liest aber `report_config` statt `alert_channels` |
| **Frontend, Alarm-Bereich** | ❌ **fehlt vollständig** | ~30 Stellen, s.u. |
| Datenvertrag | ✅ dokumentiert | `docs/reference/api_contract.md:775-833` |

Der Schwerpunkt der Arbeit liegt damit im **Frontend**; das Backend braucht genau **eine**
inhaltliche Änderung (Radar-Kanalquelle).

## Related Files

### Python — Radar-Kanalquelle (die eine Backend-Änderung)

| Datei:Zeile | Relevanz |
|---|---|
| `src/services/trip_alert.py:826-856` | `_radar_effective_channels()` — löst nur aus `report_config` auf. `grep alert_channels\|alert_rules` im Bereich: **keine Treffer** |
| `src/services/trip_alert.py:991` | Aufruf 1 — `effective_channels=` für `append_suppressed_entry` (Unterdrückungs-Protokoll, **vor** `get_nowcast`) |
| `src/services/trip_alert.py:1059` | Aufruf 2 — Leer-Check, bei leerem Set `continue` **ohne jeden Log-Eintrag** |
| `src/services/trip_alert.py:1107` | Aufruf 3 — Versand-Set; danach `split_by_threshold` (`:1130`), roh ins Protokoll (`:1148`) |
| `src/services/trip_alert.py:1491-1546` | `_effective_alert_channels()` — das Ziel-Muster (alert_rules → alert_channels → briefing → Tier-Gates) |
| `src/services/trip_alert.py:1548-1562` | `_briefing_channels()` — der Vererbungszweig, vier Kanäle |
| `src/services/alert_channel_threshold.py:20-35` | `split_by_threshold` — kanal-agnostisch, LOW-Default |

### Frontend — der Schwerpunkt (Auswahl; vollständige Liste im Agentenbericht)

| Datei:Zeile | Relevanz |
|---|---|
| `shared/alarme-tab/alertChannelState.ts:9-13,16,22,32-49,53-55,66-70,89-97` | Kern: `AlertChannelState`, `ALERT_CHANNEL_ORDER`, `NEW_ENTITY_DEFAULT`, `resolveAlertChannels`, `channelWarningNeeded`, `AlertChannelThresholdState`, `resolveAlertChannelThresholds` — **alle drei-kanalig** |
| `shared/alarme-tab/tripChannelReconstruction.ts:18-34` | AC-15-Rekonstruktion, beide Zweige drei-kanalig |
| `shared/alarme-tab/alarmeDeliveryPayload.ts:46-58,85-94,100-115` | Payload-Typen, **Laufzeit-Guard** (wirft bei nicht-boolean), `alert_channels`/`alert_channel_thresholds` im Body |
| `shared/AlertChannelPicker.svelte:44-53` | `CHANNEL_LABELS`, `CHANNEL_SUB` — Beschriftung. Rendering läuft über `{#each ALERT_CHANNEL_ORDER}` (`:102-125`) und zieht eine vierte Zeile **automatisch** nach |
| `shared/AlarmeTab.svelte:78,83,190-205,226-243` | Eigene, von `ChannelKind` **losgelöste** Union `'telegram'\|'sms'\|'email'`; `displayChannelState` im `vergleich`-Zweig setzt `email: true` fest; `handleChannelToggle`/`handleThresholdChange` mit `if/else if`-Ketten |
| `compare/compareWizardState.svelte.ts:49-50,124-125,188` | `sendTelegram`/`sendSms` als `$state`, kein `sendPremiumSms`; POST-Payload ohne das Feld |
| `compare/compareEditorSave.ts:61-62,189-190,245-246,310-311` | Edit- und Neuanlage-Payload für den Vergleich |
| `compare/compareHubWizardBridge.ts:444-471,505-507,529-550,598-600,628-644` | Hydration, Snapshot, Rollback-Feldliste |
| `compare/CompareTabs.svelte:575-596` | `currentAlarmSnapshot()` |
| `frontend/src/lib/types.ts:367,371,637-663` | `Trip.alert_channels` (Unterfelder **nicht** optional, kein `premium_sms`), `alert_channel_thresholds`, `ComparePreset` |

### Mount-Punkte (vier Flächen, drei davon Vergleich)

| Datei:Zeile | `context` |
|---|---|
| `trip-detail/AlarmeScheduleTab.svelte:60-69` | `route` — einziger Trip-Mount |
| `compare/CompareTabs.svelte:1429` | `vergleich` — Hub |
| `compare-new/CompareNewEditor.svelte:412` | `vergleich` — Neuanlage, Desktop-Zweig |
| `compare-new/CompareNewEditor.svelte:499` | `vergleich` — Neuanlage, **eigener** Mobile-DOM-Ast |

## Existing Patterns

**Vorlage ist der Versand-Reiter (#1717 S3, Commit `9a0dd398`)** — vier Bausteine:

1. **Ein geteilter, reiner Zustands-Helfer** (`shared/versand-tab/premiumSmsChannelState.ts:53-106`)
   leitet aus dem Profil das vollständige Anzeige-Objekt ab. Tarif-Gate zuerst, danach der
   **server-abgeleitete** `premium_sms_reply_state` (`fresh`/`stale`/`none`) — das Frontend rechnet
   keine Frist selbst nach.
2. **Gating über Prop-Anwesenheit**, nicht über einen `context`-String-Vergleich in der
   Presentation-Komponente (`VTBriefingChannels.svelte:54,202`).
3. **Lokaler `$state` + Read-Modify-Write-Merge im Container**, nicht in der Presentation-Komponente.
4. **Zählung als aktiver Kanal** (`VersandTab.svelte:157-159`), damit „nur Premium-SMS aktiv" nicht
   fälschlich als Leerzustand erscheint.

Beschriftung überall wörtlich **„Premium-SMS (Garmin inReach)"**, Anordnung als **vierte Zeile
direkt unter SMS**.

🔴 **Eine Stelle, an der die Alarm-Seite dem Vorbild NICHT folgen darf:** Im Versand-Pfad ist
Premium-SMS für `vergleich` **ausgeschlossen** (ADR-0049: reiner Trip-Briefing-Kanal; Test
`premium_sms_context_gating_render.test.ts:118`). Im **Alarm**-Pfad ist er laut #1701 AC-4
ausdrücklich **auch für den Vergleich** vorgesehen (`compare_alert_channels.py:44-45`,
`ComparePreset.SendPremiumSms`, `internal/model/compare_preset.go:97`). Ein kopiertes
`{#if context === 'route'}` wäre hier ein Fehler.

**Präzedenzfall für die Radar-Umstellung:** Im **Compare**-Zweig ist genau diese Umstellung bereits
vollzogen — #1461 S3b-2b hat den Compare-Radar-Onset-Pfad von hart `{"email"}` auf den regulären
`effective_compare_channels()`-Resolver umgestellt, mit eigenen ACs und als Nachtrag zu ADR-0021
(**ohne** neue ADR). Die Trip-Seite zieht mit #1745 nach.

## Dependencies

- **Upstream:** `report_config` (Briefing-Flags), `trip.alert_channels`, `trip.alert_rules`,
  `user_tier.premium_sms_allowed()`, `Settings.can_send_*()`, `alert_urgency`
- **Downstream:** `alert_log.append_entry`/`append_suppressed_entry` (Protokoll-Inhalt ändert sich
  mit dem Kanal-Set), `NotificationService.send_radar_alert`, Cockpit-/Protokoll-Anzeigen, die
  `channels_not_sent` lesen

## Existing Specs & ADRs

| Dokument | Vorgabe | Wirkung auf #1745 |
|---|---|---|
| `docs/specs/_archive/modules/issue_1258_alarme_tab_official_warnings.md:428` (**AC-15**) | Beim ersten Öffnen zeigt der Picker den aus dem Ist-Zustand **rekonstruierten** Status, nicht den Neuanlage-Default | Rekonstruktion muss um den vierten Kanal erweitert werden, ohne AC-15 zu brechen |
| dieselbe Datei, `:506-511` | **Known Limitation**: „Der Radar/Onset-Pfad baut sein Kanal-Set eigenständig aus `report_config` … Angleichung wäre ein eigenes Issue" | #1745 **ist** dieses angekündigte Issue. Abschnitt als eingelöst markieren |
| `docs/specs/modules/feat_1701_alarm_premium_sms.md:177-198` (D1) | Listet acht hart verdrahtete Kanal-Enumerationen, darunter die Radar-Stelle als „bewusst getrennt seit #1467 S3" | Fundstellen-Liste für die Umstellung |
| dieselbe Datei, `:380-388` | „Kein neues ADR — ADR-0049 legt den Kanalnamen fest, ADR-0046 verpflichtet zur Schwellenanwendung" | #1701 hielt für die Kanal**quelle** kein ADR für nötig; die Umstellung selbst hat noch keine ADR-Deckung |
| `docs/specs/modules/feat_1461_s3b2b_compare_kanal_schwelle.md` (AC-5/-6) | Compare-Radar bereits auf regulären Resolver umgestellt | Vorbild für Struktur und ACs |
| `docs/specs/modules/feat_1717_s3_premium_sms_ui.md:33-40` | „Premium-SMS bleibt ausschließlich ein Trip-Briefing-Kanal (ADR-0049)"; `AlertChannelPicker`/`AlarmeTab` ausdrücklich **nicht** Teil der Scheibe | Bestätigt die Lücke als bewusst offen gelassen, nicht als Regression |
| **ADR-0049** (Akzeptiert 2026-08-10) | `premium_sms` ist der verbindliche Kanalname; Konsequenzen-Abschnitt benennt die unvollständigen Kanallisten | Name steht fest — #1745 ändert nur Quelle und Oberfläche |
| **ADR-0046** (Akzeptiert 2026-08-05) | „Jede neue Stelle, die ein Kanal-Set auflöst — heute `_effective_alert_channels()` **plus die Radar-Inline-Kopie** — muss die Schwelle anwenden" | Der Radar-Pfad wendet sie bereits an (`trip_alert.py:1130`). Eine Zusammenführung erfüllt die Pflicht weiterhin |
| **ADR-0021** | Shared Deviation Alert Engine; Nachtrag S3b-2b dokumentiert die Compare-Radar-Umstellung als bloße Anwendung des Prinzips | Muster: Nachtrag statt neuer ADR |

**Es gibt keine ADR, die „Radar folgt Briefing" als Architekturprinzip festschreibt.** Die einzige
Begründung ist die Known-Limitation-Notiz oben. Nach dem Compare-Präzedenzfall genügt ein
**Spec-Nachtrag zu ADR-0021 oder ADR-0046**; eine eigenständige neue ADR ist nicht zwingend. Das
entscheidet die Analyse-Phase, nicht dieser Kontext.

## Risks & Considerations

🔴 **R1 — Die Umstellung ändert mehr als die Kanalquelle: die Bereitschaftsfrage.**
`_radar_effective_channels` prüft `can_send_email()`/`can_send_telegram()`/`can_send_sms()`
**inline** (`:838,840,843`) — technisch unerreichbare Kanäle fehlen bereits im Ergebnis.
`_effective_alert_channels` prüft **keine** davon (verifiziert per `grep can_send_`); dort filtert
erst `NotificationService` beim Versand. Ein naives Ersetzen der Funktion ändert damit still das
Verhalten der beiden Leer-Checks (`:1059`, `:1109`) und den Inhalt der Protokoll-Einträge
(`:991`, `:1148`): heute „kein Alarm, Warnung geloggt", danach „Alarm versucht, Dispatch filtert".
Das ist die riskanteste Stelle der ganzen Änderung und gehört ausdrücklich in die ACs.
*(Nebenbefund: Premium-SMS ist davon nicht betroffen — beide Pfade stellen für ihn bewusst keine
Bereitschaftsfrage, `trip_alert.py:851-854`.)*

🔴 **R2 — Test-Blindstelle.** `grep` über `tests/`: **kein einziger** Test exerciert
`check_radar_alerts()` mit gesetztem `trip.alert_channels` oder aktiven `trip.alert_rules`. Alle
Radar-Fixtures setzen die Kanäle ausschließlich über `report_config` mit vollständigen `send_*`-
Flags. Für diese Fixtures liefern beide Funktionen dasselbe Set — **kein bestehender Test würde
allein durch den Funktionswechsel rot**. Ein grüner Lauf beweist hier also nichts; die
Mutations-Gegenprobe muss genau darauf zielen.

**R3 — Verhaltensänderung für Bestandstrips.** Trips mit gesetztem `alert_channels` ändern ihr
Radar-Zustellverhalten (PO-entschieden, s.o.). Trips mit `alert_channels: None` (`Graveltour`,
`Lottis Abschiedfahrradtour`, `GR221 Mallorca`) merken nichts.

**R4 — Harte `deepEqual`-Tests im Frontend brechen sofort.**
`alarme_alert_channel_defaults.test.ts:27-29` prüft `ALERT_CHANNEL_ORDER` per `deepEqual` gegen ein
Drei-Element-Array; dazu `alarme_trip_channel_reconstruction.test.ts:27-51` und
`alertChannelThresholds.test.ts:45-48,71-82`. Das ist erwünscht (die Tests bewachen etwas) — sie
müssen bewusst mitgezogen werden.

**R5 — Laufzeit-Guard in `alarmeDeliveryPayload.ts:85-94`.** Wird `premium_sms` dort zum
Pflichtfeld, brechen mehrere Bestands-Aufrufer/Tests. Additiv-optional passt besser zum
Feld-Level-Merge des Backends (#1701 AC-7).

**R6 — Playwright deckt den vierten Kanal nicht ab.**
`frontend/e2e/feat-1461-s3b2b-compare-kanal-schwelle.spec.ts` iteriert hart über drei Kanäle und
würde **nicht** rot, bliebe aber strukturell unvollständig. Für den Trip-Alarm-Reiter existiert
überhaupt kein E2E-Spec.

**R7 — Zwei mutmaßlich parallele Compare-Speicherpfade.**
`compareWizardState.saveComparePreset()` (`:167-196`) übergibt heute **weder** `sendTelegram` noch
`sendSms` an `buildComparePresetSavePayload`, nur `channelThresholds`; der Hub speichert dagegen über
`CompareTabs.flushPendingAlarmSave` (`:598-600`). Welcher Pfad wirklich trägt, ist ungeklärt — vor
dem Bauen zu messen, sonst landet der vierte Kanal im toten Zweig.

**R8 — Namenskollision Trip vs. Compare.** `Trip.SendPremiumSms` ist ein **abgeleitetes
Briefing**-Flag (`internal/store/trip.go:57-95`), `ComparePreset.SendPremiumSms` ist das
**Alarm**-Opt-in (`compare_preset.go:93-97`). Eine Spec, die von „SendPremiumSms" spricht, ohne die
Seite zu nennen, ist mehrdeutig.

## Offene Fragen für Phase 2 / die Spec

1. **Neuanlage-Default für Premium-SMS** in `NEW_ENTITY_DEFAULT` (`alertChannelState.ts:22`, heute
   `{telegram: true, sms: true, email: false}`) — an oder aus? Kostenkanal, deshalb PO-Frage.
2. **Statusanzeige:** Der Alarm-Picker zeigt für **keinen** Kanal einen Verbindungsstatus (die
   `targets`-Prop wird an keiner der vier Mount-Stellen befüllt). Bekommt Premium-SMS dort den
   reichen Status des Versand-Reiters (Tarif-Sperre, Rückadresse frisch/veraltet) oder nur eine
   schlichte Zeile wie die drei Bestandskanäle?
3. **Scope-Grenze `AlertRulesEditor`** (Reiter „Alarmregeln", Pro-Regel-Kanal-Overrides, #687):
   `TripEditView.svelte:52-56` und `TripNewEditor.svelte:108` führen dieselbe harte Dreier-
   Aufzählung. Teil dieser Scheibe oder eigenes Issue?
4. **ADR-Frage:** Nachtrag zu ADR-0021/ADR-0046 (Compare-Präzedenz) oder eigenständige neue ADR?

---

# Analysis (Phase 2, abgeschlossen 2026-08-11)

## Type

**Bug** — zwei zusammenhängende Befunde, beide nutzersichtbar.

## Korrekturen an Phase 1 (nachgemessen, ersetzen die Einschätzungen oben)

🔴 **R1 war überzeichnet.** `_dispatch_alert_message` wiederholt `can_send_email/telegram/sms()` beim
Versand (`notification_service.py:1388,1404,1485`) — ein technisch unerreichbarer Kanal wird in
**beiden** Varianten nicht zugestellt. Premium-SMS hat dort bewusst **keine** Vorprüfung (`:1499`),
unverändert in beiden Varianten. Es ließ sich **keine** Konfiguration konstruieren, bei der die
Umstellung das Zustellergebnis ändert. Der einzige Effekt ist **Beobachtbarkeit**: wo heute `:1059`
mit `logger.warning("No channel configured")` und **ohne** Protokoll-Eintrag abbricht, entsteht
danach ein `alert_log`-Eintrag mit leerem `sent_channels`. Das ist eine Verbesserung — muss aber als
AC formuliert werden, damit niemand die neuen Einträge für einen Defekt hält.

🔴 **R7 ist erledigt.** `compareWizardState.saveComparePreset()` hat **keinen** Aufrufer mehr
(`CompareEditor.svelte` existiert nicht mehr). Lebender Speicherweg im Vergleich ist ausschließlich
`AlarmeTab.svelte:195-205` → `wiz.*` → `CompareTabs.currentAlarmSnapshot():575-596` →
`handleAlarmeCommit():653-680` → `flushPendingAlarmSave` → **`buildHubPutPayload`**
(`compareHubWizardBridge.ts:125-195`, kodiert die Feldliste ein **zweites** Mal) →
`buildComparePresetSavePayload` → PUT.

🔴 **Go braucht null Änderungen.** `internal/handler/trip.go:371-407` und
`internal/handler/compare_preset.go:407-416` mergen `PremiumSms` bereits feldweise (`*bool`,
`omitempty`) — ausgeliefert mit #1701.

**Der Vergleich hat kein `alert_channels`-Objekt** — flache Felder `send_telegram`/`send_sms`/
`send_premium_sms`; **E-Mail ist dort hart verdrahtet** (`compare_alert_channels.py:39`:
`channels = {"email"}`, es gibt kein `send_email`-Feld). `AlarmeTab.svelte:190-194` spiegelt das
korrekt mit `email: true`.

## Technical Approach

**Radar-Umstellung — Weg (b):** `_radar_effective_channels()` entfällt **ersatzlos**; die drei
Aufrufstellen (`trip_alert.py:991,1059,1107`) nutzen `_effective_alert_channels(trip)`. Ein
Wrapper, der die `can_send_*`-Vorfilterung behält, würde die Duplikat-Falle nur verschieben — genau
den Zustand, der diesen Bug erzeugt hat.

**Zwei Konsequenzen, die ausdrücklich in die ACs gehören:**
1. Radar erbt damit auch die **`alert_rules`-Union** (`:1515,1531-1540`) — ein Trip mit aktiven
   Regeln, deren `channels`-Override nicht leer ist, bestimmt damit auch den Radar-Kanalsatz mit.
   Jede Alternative wäre eine zweite, leicht abweichende Fassung — also derselbe Fehler noch einmal.
2. Der zweite Leer-Check (`:1109`) ist bereits heute unerreichbar (reine Funktion, `trip`
   unverändert) und entfällt. Das Kanal-Set wird **einmal** berechnet und an allen drei Stellen
   wiederverwendet. ADR-0046 bleibt erfüllt (Schwelle sitzt unverändert bei `:1121`).

**Tarif-Gate im Alarm-Picker — nicht die volle `premiumSmsChannelState()` wiederverwenden.** Die
verrechnet zusätzlich die Rückadress-Frische (`fresh`/`stale`/`none`) zu `disabled` — genau die
Bereitschaftsfrage, die der Alarmpfad bewusst **nicht** stellt (`trip_alert.py:851-854`,
`notification_service.py:1499`). Volle Wiederverwendung würde den Haken sperren, obwohl das Backend
den Versand trotzdem versucht. Stattdessen nur `ConnectionProfile.premium_sms_allowed`
(`channelConnectionStatus.ts:22-35`, Feld existiert), ein schlanker `onMount`-Profil-Fetch nach dem
Muster `VTBriefingChannels.svelte:81-109`. `AlertChannelPicker` wird nur von `AlarmeTab` eingebunden
— **ein** Fetch-Ort deckt alle vier Mount-Punkte.

## Scope Assessment — Empfehlung: zwei Scheiben

| Bereich | S1 Radar-Kanalquelle | S2 Premium-SMS in der Oberfläche |
|---|---|---|
| Python | ~40–70 (netto eher negativ, Funktion entfällt) | 0 |
| Go | 0 | 0 |
| Frontend-Kernlogik + `types.ts` | 0 | ~30–45 |
| Svelte-Komponenten | 0 | ~50–75 |
| Compare-Kette | 0 | ~40–65 |
| Tests | ~150–200 | ~250–350 |
| **Summe** | **~220–270** | **~370–535** |

**S1 zuerst.** Danach ist Befund (2) vollständig behoben: Radar-Alarme respektieren die
Alarm-Kanal-Auswahl für Telegram/SMS/E-Mail. Und S2 braucht danach **keinen Radar-Touch mehr** —
sobald die Oberfläche `alert_channels.premium_sms` schreibt, greift `_effective_alert_channels`
automatisch, weil sie den Kanal seit #1701 kennt. S2 braucht einen begründeten
`loc_limit_override`; eine weitere Unterteilung (Trip-Picker vs. Compare-Kette) würde einen
Zwischenstand mit sichtbarem, aber wirkungslosem Haken erzeugen — der gemeldete Bug, nur verschoben.

**Risk Level: MEDIUM.** Kein Zustellungsrisiko (R1 entschärft), aber eine gewollte
Verhaltensänderung für Bestandstrips und eine vollständige Test-Blindstelle (R2).

## Fünf Landminen (nach Wahrscheinlichkeit)

1. **`AlarmeTab.svelte:226-243`** — `handleThresholdChange` baut im `vergleich`-Zweig das
   Rückschreibe-Objekt **explizit dreifeldig** (`{telegram, sms, email}`) und verwirft ein
   berechnetes `premium_sms` still. Ergebnis: sichtbarer Schwellen-Regler, der beim Speichern
   verlorengeht — der gemeldete Bug in neuer Form.
2. **`hasAnyExplicitChannelValue()`** (`alertChannelState.ts:32-38`) prüft nur drei Kanäle. Ein
   Bestand mit **ausschließlich** `premium_sms` gilt als „kein Bestand" und wird vom
   Neuanlage-Default überschrieben — dieselbe Fehlerklasse, die Adversary Fix-Loop 1/F001 für die
   drei Bestandskanäle schon einmal gefixt hat.
3. **S2 wird ohne Override durchgedrückt** und dabei das Wiring unvollständig gelassen.
4. **Tarif-Gate 1:1 aus `premiumSmsChannelState()` übernommen** — sperrt einen Kanal, den das
   Backend bewusst ohne Vorprüfung versucht.
5. **Generische statt mutationsscharfe Radar-Tests** — R2: kein bestehender Test wird durch den
   Funktionswechsel rot, ein grüner Lauf beweist hier nichts.

## Was die Tests beweisen müssen (S1)

Prüfort ist durchgehend die **beobachtbare Nebenwirkung** (persistierter `alert_log`-Eintrag bzw.
die an `send_radar_alert` übergebenen `effective_channels`), nicht die interne Funktion.

| Mutation | Prüfort |
|---|---|
| M1 — Radar liest weiterhin `report_config` | `report_config.send_telegram=True` **aber** `alert_channels={telegram:False, sms:True}` → `telegram` darf **nicht** im Eintrag stehen |
| M2 — Fallback bei `alert_channels=None` bricht | `alert_channels=None`, `send_telegram=True` → `telegram` **muss** enthalten sein |
| M3 — Schwelle bindet an die falsche Variable | `alert_channel_thresholds={telegram:"HIGH"}`, Radar mit niedriger Dringlichkeit → `telegram` in `below_threshold_channels` |
| M4 — nur der Dispatch wird umgestellt, das Unterdrückungs-Protokoll (`:991`) nicht | Nowcast-Gate blockiert (Ruhezeit), divergierende Quellen → `append_suppressed_entry` zeigt dieselbe Quelle wie der Dispatch |
| M5 — Early-Exit `:1059` an globaler statt Trip-Erreichbarkeit | (a) global unerreichbar, trip-seitig an → Eintrag **entsteht**; (b) alles trip-seitig aus → **kein** Eintrag, **kein** Throttle-Record |

`make_trip()` (`tests/helpers/nowcast_gate_fixtures.py:360-402`) muss **nicht** erweitert werden —
`alert_channels` lässt sich am zurückgegebenen Objekt direkt setzen.

## Open Questions

- [ ] Liefer-Reihenfolge S1/S2 gegen den KHW-Tourtermin — PO-Frage, s. Bericht
- [ ] Tarif-Gate: nur `premium_sms_allowed` (Empfehlung) vs. voller Zustandshelfer — in der Spec zu fixieren

## 🔴 PO-Entscheid 2026-08-11 zur Liefer-Reihenfolge

**Scheibe A = Oberfläche zuerst** (dieser Workflow), **Scheibe B = Radar-Umstellung danach**
(eigenes Issue).

Begründung, die den Ausschlag gab: Solange Premium-SMS in der Alarm-Kanal-Auswahl fehlt, erreicht
**kein einziger Alarm** das Garmin — auch kein Gewitteralarm. Der KHW-Trip hat einen scharfen
Kanalsatz gesetzt (`alert_channels = {email, telegram, sms}`), und der ersetzt die
Briefing-Vererbung **vollständig** (`trip_alert.py:1518-1525`). Der Kanal ist im Backend seit #1701
fertig; es fehlt allein der Haken. Tourtermin Karnischer Höhenweg ab 2026-08-20, auf der Hütte ist
Satellit der einzige Empfangsweg.

Nach Scheibe A erreichen Gewitter-, Änderungs- und amtliche Alarme das Gerät (alle drei lesen
`_effective_alert_channels`). Regen-/Radar-Alarme folgen bis Scheibe B weiter den Briefing-Flags.

**Folge für den Schnitt:** Die in der Analyse empfohlene Reihenfolge S1→S2 ist damit **umgedreht**.
Scheibe A braucht deshalb `loc_limit_override` (Schätzung 370–535). Der Grund für die ursprüngliche
Empfehlung (S2 bräuchte nach S1 keinen Radar-Touch) entfällt nicht — er verschiebt sich nur:
Scheibe B braucht nach Scheibe A keinen Oberflächen-Touch, weil `_effective_alert_channels` den
Kanal bereits kennt.
