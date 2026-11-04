# Context: Scheibe S3b2 — Hinweise „Kanal ohne Empfänger" und „Kanal-Schwelle über Metrik-Stufe" (#1895)

> Workflow `feat-1895-s3b2-kanal-hinweise` · Issue #1895 · Epic #2345
> Erhoben 2026-11-04, Stand `origin/main` = `db933f288` (S3b1 live, PR #2804, Prod `eca9d56fa`).
> **Grundlagen, weiter gültig:** `docs/context/feat-1895-s3b-kanal-spalte.md` (Entscheidungen F1–F9, Übergabe-Vertrag),
> `docs/context/feat-1895-s3-kanal-spalte.md` (E1–E10). Spec: `docs/specs/modules/alert_metric_channels.md`
> (AC ab AC-41; S3b2 laut Scheibenschnitt `:1078` „offen, eigener Workflow unter #1895, kein neues Issue").

## Request Summary

Der Block „Kanäle je Wettergröße" (S3b1) lässt den Nutzer pro Wettergröße eigene Kanäle wählen. Zwei Fälle,
in denen eine solche Wahl einen Alarm trotzdem nicht zustellt, sind für den Nutzer unsichtbar:
(1) gewählter Kanal hat **keinen Empfänger** (z. B. Telegram ohne verknüpften Chat, SMS ohne bestätigte Nummer);
(2) die **Kanal-Schwelle** des gewählten Kanals (ADR-0046) liegt über der Dringlichkeit der Metrik-Stufe.
S3b2 ergänzt genau diese zwei Hinweise im Block — reine Frontend-Scheibe (Spec: „kein neuer Backend-Code", ca. +60–80 LoC).
Wirkung bleibt wie heute: der Hinweis **informiert**, er sperrt nichts (kein Gate, kein Schreibverbot).

## Ist-Stand Block (aus S3b1, gemessen)

| Baustein | Stand |
|---|---|
| `alerts-tab/AlertMetricChannelsBlock.svelte` (137 Z.) | Props `aktiveMetriken`, `eintraege`, `aboKanaele`, `premiumSmsGate`, `schluesselOverride?`, `onChange`. Je Zeile: Umschalter erbt/eigene Wahl, 4× `ChannelToggle`, Hinweise `kanal-hinweis-nicht-im-abo-<k>`, `kanal-hinweis-wind-<k>`, global `kanal-hinweis-metrikfrei` |
| `shared/alarme-tab/alertMetricChannels.ts` (67 Z.) | `hinweise(eintrag, aboSatz)` liefert nur „gewählt, aber im Abo aus" — hier andocken, ähnliche reine Funktionen daneben |
| `shared/AlarmeTab.svelte` | kennt `displayChannelThresholds` (`:334-343`, Zustand je Kanal `LOW/MODERATE/HIGH`, Typ `AlertChannelThresholdState` in `alarme-tab/alertChannelState.ts:95-106`) und `alarmProfile` (`:195-209`) — letzteres liest **nur** `premium_sms_allowed` |
| Mounts | Block wird in `AlarmeTab` mounted (Trip-Hub, `/trips/new`, Ortsvergleich-Editor, `/compare/new`); Änderungen am Block gelten automatisch für alle vier Flächen (Parität ADR-0095, kein Compare-Sonderweg) |

## Befund 1 — „Kanal ohne Empfänger": Was der Python-Transport wirklich verlangt

Quelle der Wahrheit: `src/output/channels/recipient.py` (Empfängervertrag #1412). Ein Kanal gilt als „ohne Empfänger", wenn die Fabrik blockt:

| Kanal | Blockbedingung im Transport | Profilfeld (Frontend sieht via `GET /api/auth/profile`, `internal/handler/auth.go:911-975`) |
|---|---|---|
| E-Mail | immer Empfänger (`mail_to`, ersatzweise `email`; Konto hat Pflicht-E-Mail) | nie „ohne Empfänger" ⇒ **kein Hinweis nötig** |
| Telegram | `telegram_chat_id` leer ⇒ `ChannelBlockedError telegram_no_chat_id` (`:77-84`) | `telegram_chat_id` (omitempty) |
| SMS | `sms_to` leer **oder** `sms_verified_number != sms_to` ⇒ `sms_no_recipient` (`:136-142`) | `sms_to` + `sms_verified` (immer vorhanden, abgeleitet) |
| Premium-SMS | gelernte Rückadresse `premium_sms_reply_to` fehlend/zu alt ⇒ blockt (`PremiumSmsRecipient.for_user`, `:208-220`) — **aber** `premiumSmsAlarmGate.ts:7-14` hält fest: der **Alarmpfad** fragt die Frische bewusst nicht (`trip_alert.py:847-855`, `notification_service.py:1499`) | `premium_sms_reply_to`, `premium_sms_reply_state` (`none/stale/fresh`), `premium_sms_allowed` |

Folgen für den Entwurf:
- **Kein Falschversprechen riskieren:** Der Hinweis darf nur dort stehen, wo der Transport tatsächlich blockt. Telegram und SMS sind eindeutig ableitbar. **Premium-SMS ist der Streitfall**: Gate-Datei sagt, der Alarmpfad prüft die Rückadresse nicht — bevor ein Premium-Hinweis entsteht, muss in `/20-analyse` am Alarm-Sendepfad (`trip_alert.py`, `notification_service.py` Alarm-Methoden, `compare_alert.py`) gemessen werden, ob `PremiumSmsRecipient.for_user` dort überhaupt greift. Sonst Premium-SMS ausdrücklich ausnehmen (Known Limitation) statt raten.
- Die Hinweislogik braucht **dieselbe Definition von „Empfänger vorhanden"** wie der Versand-Reiter (der zeigt bereits Zustände je Kanal). Vor neuer Logik prüfen, ob dort ein wiederverwendbarer Helper existiert (Wiederholungs-Klasse #1481; Pendant-Sperre).
- Das Profil-Objekt wird im AlarmeTab schon geladen (`alarmProfile`, Typ nur `{premium_sms_allowed?}`) — Erweiterung des Typs und ggf. der `profileOverride`-Testhaken (`AlarmeTab.svelte:153`) nötig; Quelle bleibt `/api/auth/profile`, **keine zweite Abfrage**.
- Mandantentrennung: Profil kommt aus dem Auth-Kontext des Nutzers; Zwei-Nutzer-Test (A hat Telegram-Chat, B nicht) gehört in die ACs.

## Befund 2 — „Kanal-Schwelle über Metrik-Stufe": Semantik

- `split_by_threshold(channels, urgency, thresholds)` (`src/services/alert_channel_threshold.py:20-37`): Kanal erlaubt, wenn `meets_or_exceeds(urgency, schwelle)`; Startwert je Kanal `LOW` (wirkt nur, wenn der Nutzer sie hochsetzt, rote Linie #638). Läuft **nach** der Kanal-Auflösung (Abo-Satz oder Metrik-Arm) und bleibt unverändert (ADR-0046, ADR-0077).
- Wirkung: Metrik-Arm `{sms}` + SMS-Schwelle `HIGH` ⇒ eine Alarmstufe mit Dringlichkeit `MODERATE` erreicht **niemanden** über diesen Arm. Gleiches gilt bereits für den Abo-Satz; S3b2 macht die Lage nur sichtbar.
- **Was das Frontend kennt:** Schwellen je Kanal (`displayChannelThresholds`) ✔. **Was es nicht ohne Weiteres kennt:** die *Dringlichkeit der gewählten Metrik-Stufe* (Mapping Empfindlichkeitsstufe → `LOW/MODERATE/HIGH`, `services.alert_urgency`, ADR-0043/0046). `/20-analyse` muss klären: gibt es eine Frontend-Entsprechung (`alertMetricLevels`/Stufenkatalog) oder reicht ein **stufenunabhängiger** Hinweistext („Kanal X hat Schwelle ≠ niedrig — schwächere Warnungen kommen darüber nicht an")? Letzteres vermeidet eine zweite Rangtabelle im Frontend (Wächter #1480/#1481) und ist ehrlich, solange er nur bei Schwelle > `LOW` erscheint.
- Premium-SMS hat seit #1701 S2b ebenfalls eine Schwelle (ADR-0095 löst die Kanalliste von ADR-0046 teilweise ab) — alle vier Kanäle abdecken.
- `AlertChannelThresholdState` hat vier Schlüssel; Quelle der Anzeige existiert bereits im selben Tab (Abschnitt Kanal-Schwellen) ⇒ Hinweis kann darauf verweisen.

## Related Files (S3b2)

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/alerts-tab/AlertMetricChannelsBlock.svelte` | zwei neue Hinweiszeilen je Wettergröße (Testids analog `kanal-hinweis-…`) |
| `frontend/src/lib/components/shared/alarme-tab/alertMetricChannels.ts` | neue reine Funktionen (Empfänger-Lücken, Schwellen-Hinweis) neben `hinweise()` |
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | Profil-Typ erweitern, Schwellenzustand + Empfängerstand an den Block geben (Ratsche `context_herkunft_zweige_eingefroren.test.ts` pinnt Zeilen in AlarmeTab — nach Edit neu messen; keine neue `context===`-Weiche) |
| `frontend/src/lib/components/shared/alarme-tab/alertChannelState.ts` | Typ/Konstanten der Kanal-Schwellen |
| `frontend/src/lib/components/shared/alarme-tab/premiumSmsAlarmGate.ts` | Vorbild + Prüfstein für Premium-SMS-Frage |
| `frontend/src/lib/components/shared/versand-tab/` (Kanalzustände, `premiumSmsChannelState.ts`) | vorhandene Empfänger-Zustandslogik — Wiederverwendung prüfen |
| `frontend/src/lib/i18n/messages/{de,en}/alarme.json` | neue Texte (`alarme.kanaele.*`), Katalog-Ratsche verlangt Verwender im Block |
| `frontend/src/lib/components/alerts-tab/__tests__/kanal_block_zeilen_und_hinweise_render.test.ts`, `shared/alarme-tab/__tests__/kanal_wahl_je_wettergroesse_regeln.test.ts` | Vorbild/Erweiterung der Tests aus S3b1 |
| `frontend/e2e/kanal-je-wettergroesse-block.staging.spec.ts` | Staging-Spec aus S3b1, erweiterbar (`.tn-mobile` + `.tn-desktop`) |
| `src/output/channels/recipient.py`, `src/services/alert_channel_threshold.py`, `src/services/trip_alert.py`, `compare_alert.py`, `notification_service.py` | nur **lesen** (Quelle der Wahrheit für die Hinweisbedingungen); keine Backend-Änderung |
| `docs/specs/modules/alert_metric_channels.md` | S3b2-ACs ab AC-63 (letzter vergebener: AC-62); Scheibenschnitt `:1078` und Known Limitations nachziehen |

## Existing Patterns

- Hinweise im Block: reine Funktion im Helper (`hinweise()`), Anzeige per `{#if}` mit `data-testid`, Text über Katalog (`$t`), Farbe `--g-ink-muted` (WCAG-AA, Design-Leitprinzip).
- Gate-Muster: `premiumSmsAlarmGate` — pure Funktion mit **einem** Eingang, Hinweis folgt `tr`/`$locale`.
- Doppelverdrahtung Trip/Vergleich: hier **nicht** nötig, der Block ist EIN geteilter Baustein in `AlarmeTab`.
- Frontend-Tests über `node --test` (kein Vitest); Svelte-Komponenten über den Prüfstand `ohneTypen()` (bekannter Fehler: schneidet bei `(x) as T` die schließende Klammer ab — Nebenbefund #1199; in neuem Block-Code `as T` in Ausdrücken meiden).
- Mutations-Gegenprobe Pflicht: Leitfrage „ist die Zusicherung dort geprüft, wo sie WIRKT?" — Hinweis muss an der Bedingung (Profilfeld/Schwelle) hängen, nicht nur am Text.

## Dependencies

- Upstream: S3b1-Block (live), `/api/auth/profile` (Felder s. o.), Kanal-Schwellen-Zustand im AlarmeTab, Python-Transportregeln (nur als Referenz).
- Downstream: S4 (Rückbau `alert_rules`) setzt S3b1 voraus, **nicht** S3b2 (Spec `:1079`). Issue #1895 schließt erst nach S4.

## Risks & Considerations

- **R1 Falschversprechen durch Hinweis (größtes Risiko):** Hinweis ohne Entsprechung im Transport (Premium-SMS-Rückadresse im Alarmpfad!) wäre eine neue Falschaussage — ADR-0043-Geist. Bedingungen aus `recipient.py` ableiten und je Kanal belegen; ungeklärte Kanäle bewusst ausnehmen und in Known Limitations benennen.
- **R2 Profil nicht ladbar:** `alarmProfile === null` ⇒ **keine** Hinweise raten (wie `premiumSmsAlarmGate` „wird geprüft"), nie fälschlich „kein Empfänger" behaupten.
- **R3 Zweite Rangtabelle:** Dringlichkeit der Stufe nicht im Frontend nachbauen, wenn es keine einzige Quelle gibt (Wächter #1480/#1481).
- **R4 Datenverlust:** Hinweise sind reine Anzeige; nichts darf in `alert_metric_channels`/Speicherweg ändern (Read-Modify-Write aus S3b1 bleibt unberührt, AC-42/47).
- **R5 Parität & Mandantentrennung:** vier Flächen, zwei Nutzer mit verschiedenem Empfängerstand testen; Staging kennt nur Login `default` (Spec `:1127`) ⇒ Kern-Test mit zwei Nutzern, E2E ergänzend.
- **R6 EN-Abläufe nicht messbar:** Testhelfer `anlegenPflicht` kennt nur deutsche Labels (#2810) ⇒ EN-Anlegen-Abläufe im E2E nicht beweisbar, Katalog-Test (DE/EN) deckt Texte ab.
- **R7 Renderer-Gate:** keine Mail-Inhalts-Dateien betroffen (reines Frontend) ⇒ kein Mail-Validator-Zwang; Frontend-only-Deploy-Scope.
- **R8 Ratsche AlarmeTab:** Pins neu messen; i18n-Hardcode-Allowlist muss `[]` bleiben.
- **R9 Lage Worktree:** Branch `feat/1895-s3b2-kanal-hinweise` basiert auf `db933f288`; Staging-Mailweg ist laut Memo (#2774) kaputt — für diese Scheibe irrelevant (keine Mail).

## Offene Punkte für /20-analyse

1. **Premium-SMS im Alarmpfad:** blockt der Alarm-Sendepfad bei fehlender/veralteter Rückadresse wirklich (`PremiumSmsRecipient.for_user`) oder nicht? Entscheidet, ob Premium-SMS einen Empfänger-Hinweis bekommt (messen, nicht annehmen).
2. **Schwellen-Hinweis: stufenabhängig oder -unabhängig?** Gibt es eine einzige Frontend-Quelle für die Dringlichkeit der Metrik-Stufe? Falls nein ⇒ stufenunabhängiger Text bei Schwelle > `LOW` (Empfehlung, da ehrlich und ohne zweite Rangtabelle).
3. **Wiederverwendung statt Neubau:** existiert im Versand-Reiter bereits eine Ableitung „Kanal hat Empfänger" (Telegram/SMS)? Dann importieren statt duplizieren.
4. **Wann gilt der Hinweis?** Nur für Zeilen mit **eigener Wahl** oder auch für „wie Abo-Kanäle"? (Abo-Satz hat dasselbe Problem; S3b2-Zuschnitt = Hinweis nur dort, wo der Block selbst den Kanal wählt — in der Analyse bestätigen, Scope-Creep vermeiden.)
5. **Link/Verweis:** Soll der Empfänger-Hinweis auf die Stelle verweisen, an der der Nutzer den Empfänger einträgt (Profil/Einstellungen)? Ziel-Route in Analyse klären, **kein** Link auf nicht vorhandene Seite.
6. **Keine PO-Fragen erwartet** — rein technische Entscheidungen (CLAUDE.md: keine technischen Fragen an den PO). Ausnahme nur, falls die Textformulierung ein Produktversprechen ändert.

## Analysis

### Type
Feature (reine Frontend-Scheibe, Frontend-only-Deploy).

### Messergebnisse zu den offenen Punkten (2026-11-04)
1. **Premium-SMS im Alarmpfad blockt sehr wohl bei fehlender/veralteter Rückadresse.** Jede Alarm-Sendestelle ruft `self._premium_sms_output()` (`notification_service.py:1482, 1623, 886, 1063, 1878, 2257`), das `PremiumSmsRecipient.for_user` → `check_reply_address` (`premium_sms.py:70-95`) ausführt; Block ⇒ `blocked_channels`/`blocked_reason_codes`. „Bewusst OHNE Bereitschaftsfrage" (`:1474`) meint nur `can_send_*()`, NICHT die Empfängerprüfung. Der Kommentar in `premiumSmsAlarmGate.ts:7-14` (Verweis `trip_alert.py:847-855`) ist insoweit überholt/ungenau — beim Spec-Schreiben nicht übernehmen, ggf. Kommentar berichtigen. ⇒ **Premium-SMS bekommt den Empfänger-Hinweis** bei `premium_sms_reply_state` ∈ {`none`,`stale`} (Profilfeld, serverseitig abgeleitet; Frische-Schwelle gehört dem Server, keine zweite Zeitrechnung im Frontend).
2. **Schwellen-Hinweis: stufenunabhängig.** Im Frontend gibt es keine Entsprechung Stufe → LOW/MODERATE/HIGH (nur Schwellenzustand `AlertChannelThresholdState`). Keine zweite Rangtabelle (#1480/#1481). Text: erscheint je gewähltem Kanal, dessen Schwelle > `LOW` ist („… Schwelle <mittel/hoch>: schwächere Warnungen kommen über diesen Kanal nicht an").
3. **Wiederverwendung:** `channelConnectionStatus(profile)` (`versand-tab/channelConnectionStatus.ts`) liefert Telegram/SMS-Zustand (SMS fail-closed bei `!sms_verified`), Typ `ConnectionProfile` enthält alle Felder inkl. Premium. Empfänger-Lücke Telegram = `!telegram_chat_id`, SMS = `!sms_to || sms_allowed===false || !sms_verified`. Neue reine Funktion `kanalOhneEmpfaenger(profile)` in `alertMetricChannels.ts` baut darauf auf bzw. nutzt dieselben Bedingungen (eine Definition, Pendant-Sperre). E-Mail: nie Hinweis. Premium: zusätzlich `premium_sms_reply_state`.
4. **Geltungsbereich:** nur Zeilen mit **eigener Wahl** (der Block wählt dort selbst); „wie Alert-Kanäle" bleibt unberührt (Scope-Creep vermeiden, Abo-Satz hat dasselbe Problem, ist aber ein anderer Reiter-Abschnitt).
5. **Verweis:** reiner Text, **kein Link** (Hinweis nennt, wo: „im Reiter Versand/Profil"); keine Route nötig → kein Risiko eines toten Links.
6. **Profil null/unbekannt ⇒ keine Empfänger-Hinweise** (R2). Schwellen-Hinweis hängt nicht am Profil.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/alarme-tab/alertMetricChannels.ts` | MODIFY | reine Funktionen `kanaeleOhneEmpfaenger(eintrag, profil)` und `kanaeleMitSchwelle(eintrag, schwellen)` |
| `frontend/src/lib/components/alerts-tab/AlertMetricChannelsBlock.svelte` | MODIFY | zwei Hinweiszeilen je eigener Wahl-Zeile (Testids `kanal-hinweis-kein-empfaenger-<k>`, `kanal-hinweis-schwelle-<k>`), neue Props `profil`, `schwellen` |
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | MODIFY | Profil-Typ auf `ConnectionProfile` erweitern, Props an Block reichen; Ratsche `context_herkunft_zweige_eingefroren` neu messen, keine neue `context===`-Weiche |
| `frontend/src/lib/i18n/messages/{de,en}/alarme.json` | MODIFY | je 2 neue Schlüssel `alarme.kanaele.kein_empfaenger`, `alarme.kanaele.schwelle_hinweis` |
| `frontend/src/lib/components/shared/alarme-tab/premiumSmsAlarmGate.ts` | MODIFY (nur Kommentar) | überholte Aussage zum Alarmpfad berichtigen |
| `frontend/src/lib/components/shared/alarme-tab/__tests__/…`, `alerts-tab/__tests__/kanal_block_zeilen_und_hinweise_render.test.ts` | MODIFY/CREATE | Regeltests (zwei Nutzer, Profil null, je Kanal), Render-Test, i18n DE/EN |
| `frontend/e2e/kanal-je-wettergroesse-block.staging.spec.ts` | MODIFY | Hinweis sichtbar auf `.tn-mobile` + `.tn-desktop` |
| `docs/specs/modules/alert_metric_channels.md` | MODIFY | S3b2-ACs ab AC-63, Scheibenschnitt/Known Limitations |

### Scope Assessment
- Files: ~8 (davon 4 Tests/Spec) · Estimated LoC: +90/−5 · Risk Level: LOW (reine Anzeige, Speicherweg unberührt, kein Backend)

### Technical Approach
Zwei reine Funktionen neben `hinweise()`, Anzeige per `{#if}` mit `$t`, Profil aus der bereits vorhandenen Abfrage in `AlarmeTab`. Hinweise informieren nur, sperren nichts. Premium-SMS ist abgedeckt (Messung 1), Schwelle stufenunabhängig (Messung 2).

### Dependencies
S3b1-Block (live), `/api/auth/profile`, `channelConnectionStatus.ts`, `AlertChannelThresholdState`. Downstream: S4.

### Open Questions
- [x] alle sechs Punkte oben beantwortet; keine PO-Frage nötig (rein technisch, Textversprechen entspricht dem Transportverhalten).
