---
entity_id: feat_1717_s3_premium_sms_ui
type: module
created: 2026-08-11
updated: 2026-08-11
status: draft
version: "1.0"
tags: [sms, premium, garmin, seven-io, channel, frontend, go-api]
---

<!-- Issue #1717 (Scheibe S3) -- Premium-SMS in der Oberflaeche. Vorgaenger:
     S1 (feat_1676_s1_premium_sms_rueckkanal.md, live), S2a
     (feat_1676_s2a_premium_sms_versand.md, live). Nachfolger: S2b/#1701
     (Alarm-/Vergleichspfad), S2c/#1702 (Kostenstelle), #1533 (Generalprobe
     auf dem Geraet). Kontext-Grundlage: docs/context/feat-1717-s3-premium-sms-ui.md. -->

# Premium-SMS in der Oberfläche — S3

## Approval

- [x] Approved — PO-Freigabe 2026-08-11 ("freigabe"), 11 ACs inkl. AC-11
      (Frist-Drift-Wächter, vom Orchestrierer gegen den Entwurf nachgetragen)

## Purpose

Premium-SMS (Garmin inReach), seit S2a ein vollwertiger vierter Versandkanal, wird für den
Nutzer im Trip-Editor sichtbar und selbst schaltbar — inklusive der von S1 gelernten
Rückadresse und ihres Alters. Auf Tour soll nicht länger rätselhaft bleiben, ob der Kanal aus
ist, noch keine Rückadresse gelernt wurde oder sie verfallen ist — das Backend unterscheidet
diese drei Fälle bereits (S2a, `ChannelBlockedError.reason_code`), die Oberfläche zeigt sie
bislang nirgends.

## Abgrenzung (nicht in dieser Scheibe)

- **Alarm- und Vergleichspfad (#1701):** Premium-SMS bleibt ausschließlich ein
  Trip-Briefing-Kanal (ADR-0049). `VTBriefingChannels.svelte` wird zwar in **beiden** Kontexten
  gemountet (`context="route"` für `/trips/[id]`, `context="vergleich"` für `/compare/[id]` und
  `/compare/new`, verdrahtet über `shared/VersandTab.svelte:204-247`) — der neue, schaltbare
  Premium-SMS-Block darf **ausschließlich im `route`-Kontext** erscheinen. AC-1 sichert das
  strukturell ab.
- **`/trips/new` auf den geteilten `VersandTab` umstellen:** vorbestehender Bruch der
  Trip/Compare-Teilungsregel (der Anlege-Editor nutzt weiterhin `EditReportConfigSection`, nicht
  `VersandTab`), gebucht in #1199. Diese Scheibe aktiviert den Premium-SMS-Block **innerhalb**
  von `EditReportConfigSection`, ändert aber nichts an dieser strukturellen Abweichung.
- **Kostenstelle (#1702):** keine Zähler, keine Kontingent-Anzeige.
- **#1533 — Generalprobe auf dem Gerät:** ob eine über die neue Checkbox aktivierte Premium-SMS
  tatsächlich am Garmin-Gerät ankommt, bleibt dort. Siehe „Nachweisgrenzen" unten.

## Source

**Frontend (`frontend/src/lib/components/...`, SvelteKit):**

- **File:** `shared/versand-tab/VTBriefingChannels.svelte` (MODIFY, ≈+35 LoC) — der fest
  deaktivierte Platzhalter (`checked={false} disabled={true}`, Zeilen 187-192) wird durch einen
  echten, zustandsgetriebenen Block ersetzt, der **nur** rendert, wenn eine neue optionale Prop
  `onPremiumSmsChange` gesetzt ist — exakt das Gating-Muster des bestehenden
  `{#if onTelegramStyleChange}` (Zeile 155), das dort schon heute den Kurzstil-Schalter auf den
  `route`-Zweig beschränkt (`onTelegramStyleChange` wird im `vergleich`-Zweig von `VersandTab`
  nie übergeben, Zeilen 234-247).
- **File:** `edit/EditReportConfigSection.svelte` (MODIFY, ≈+35 LoC) — der Platzhalter (Zeilen
  376-382) wird analog aktiviert; `send_premium_sms` wird **aus der `reportConfig`-Prop
  initialisiert** (Vorbild im Bestand: `profile` per `untrack(…)`, Zeile 98) und im
  Write-Back-`$effect` mitgeführt (neben Zeilen 215-217).
  🔴 **Korrektur:** Die erste Fassung schrieb „Hydration in `onMount`" (neben Zeile 154). Das ist
  allein **nicht messbar** — `render()` aus `svelte/server` führt `onMount` nicht aus, und AC-10
  verlangt Sichtbarkeit beim Rendern. Eine Zusicherung, die per Bauart an ihrem eigenen Prüfort
  nicht ankommen kann, ist keine.
- **File:** `shared/VersandTab.svelte` (MODIFY, ≈+15 LoC) — **eigenständiger Fund, nicht im
  Kontextdokument benannt:** dies ist die tatsächliche State-/Persistenz-Schicht für
  `/trips/[id]` (gemountet von `trip-detail/BriefingScheduleTab.svelte:130-137` mit
  `bind:reportConfig`). Ohne Ergänzung von `send_premium_sms` hier (analog `send_sms` in
  Zeilen 68-70 State, 91-93 Hydration, 121-123 Write-Back, 143-151
  `makeChannelChangeHandler`) bliebe eine in `VTBriefingChannels` geklickte Premium-SMS-Checkbox
  für `/trips/[id]` folgenlos — der Wert würde nie in `report_config` geschrieben. Nur der
  `route`-Zweig (Zeilen 202-231) bekommt die neue Prop `onPremiumSmsChange`; der
  `vergleich`-Zweig (Zeilen 232-285, `CompareTabs.svelte:1452`,
  `CompareNewEditor.svelte:420,502`) bleibt unverändert — genau die in „Abgrenzung" beschriebene
  Trennung.
- **File:** `shared/versand-tab/channelConnectionStatus.ts` (MODIFY, +4 LoC) — `ConnectionProfile`
  (Zeilen 23-29) bekommt vier neue optionale Felder (`premium_sms_reply_to`,
  `premium_sms_reply_at`, `premium_sms_reply_state`, `premium_sms_allowed`) als **einzige**
  kanonische Profilform, statt die drei lokalen `interface Profile`-Kopien (VTBriefingChannels,
  EditReportConfigSection) unabhängig zu erweitern — `channelContactLabel.ts` importiert
  `ConnectionProfile` bereits (Zeile 15), der neue Helfer unten reiht sich ein.
- **File:** `shared/versand-tab/premiumSmsChannelState.ts` (NEU, ≈55 LoC) — geteilter Helfer,
  Design analog `channelConnectionStatus()` (ein Aufruf liefert Tone/Label/Hinweis/Meldedatum
  als ein Objekt) statt einer dritten Kopie der Zustandslogik. Liest ausschließlich die vier
  neuen Profilfelder, rechnet **keine** Frist selbst nach (s. Implementation Details).
- **File:** `shared/versand-tab/__tests__/channel_checkbox_dedupe_render.test.ts` (MODIFY,
  ≈+120 LoC) — bestehendes Muster (SSR beider Komponenten, identische Profile, s. AC-2/AC-3/AC-4
  im Bestand) um Premium-SMS-Fälle erweitert. Das wichtigste Regressionsnetz dieser Scheibe.
- **File:** `shared/versand-tab/__tests__/premium_sms_channel_state.test.ts` (NEU, ≈70 LoC) —
  reine Funktionsprüfung des neuen Helfers, u. a. der Server-Autoritäts-Fall (AC-5).
- **File:** `shared/versand-tab/__tests__/premium_sms_context_gating_render.test.ts` (NEU,
  ≈60 LoC) — SSR-Nachweis, dass `context="vergleich"` niemals eine schaltbare Premium-SMS-Box
  zeigt (AC-1).

**Go-API (`internal/...`, Production-API Port 8090):**

- **File:** `internal/model/premium_sms.go` (NEU, ≈45 LoC) — `PremiumSmsReplyTTL` (Go-Pendant zu
  `PREMIUM_SMS_REPLY_TTL`, `src/output/channels/premium_sms.py:39`, siehe Known Limitations),
  Zustands-Konstanten `PremiumSmsStateNone`/`PremiumSmsStateStale`/`PremiumSmsStateFresh` und
  `DerivePremiumSmsReplyState(replyTo string, replyAt *time.Time) string`.
- **File:** `internal/model/tier.go` (MODIFY, +≈10 LoC) — `PremiumSmsAllowed(tier string) bool`,
  Struktur analog `SmsAllowed` (Zeilen 3-10), aber ausschließlich `tier == "premium"` — **kein**
  Aufruf von `SmsAllowed` (das lässt `standard` durch, `:3-6`).
- **File:** `internal/model/trip.go` (MODIFY, +1 LoC) — `SendPremiumSms *bool
  \`json:"send_premium_sms,omitempty"\`` neben den bestehenden Flach-Feldern (Zeilen 161-163).
- **File:** `internal/store/trip.go` (MODIFY, +≈8 LoC) — `deriveFlatFields` (Zeilen 52-92): ein
  Reset auf `nil` bei den bestehenden Resets (`:63-70`, Fix-Loop F001 aus S2a-Vorbild:
  Trip-Konvergenz), eine bedingte Ableitung bei den bestehenden `rc[...]`-Zweigen (`:79-87`).
  **Kein** Merge-Zweig in `internal/handler/trip.go` nötig — der generische, feldweise
  `mergeConfigMap` (`internal/handler/config_merge.go:11-22`) transportiert
  `report_config.send_premium_sms` bereits verlustfrei.
- **File:** `internal/handler/auth.go` (MODIFY, +≈25 LoC) — `profileResponse` (Zeilen 446-465)
  bekommt vier neue Felder: `PremiumSmsReplyTo`/`PremiumSmsReplyAt` (Rohwerte, Muster
  `RequestedAt` `:461`/`:507` — Pointer, weil `omitempty` bei `time.Time`-Werten nicht greift),
  `PremiumSmsReplyState` (abgeleiteter String über `model.DerivePremiumSmsReplyState`, Muster
  `EmailVerified` `:457`/`:505` — abgeleiteter Zustand statt Rohwert), `PremiumSmsAllowed` (bool,
  Muster `SmsAllowed` `:454`/`:504`). **`UpdateProfileHandler`s Decode-Struct (Zeilen 541-547)
  bleibt unverändert** — keins der vier Felder wird dort aufgenommen (AC-7).
- **File:** `internal/handler/profile_test.go` (MODIFY, +≈90 LoC) — Feldmenge der vier neuen
  Felder je Drei-Zustands-Fall (Muster `TestGetProfileHandlerSmsAllowedField` `:465-515`), plus
  Negativ-Test, dass ein PUT mit den beiden Rohfeldern im Body wirkungslos bleibt (Muster der
  Negativ-Assertion in `TestGetProfileHandlerEmailVerifiedField_AC20` `:553-554`).
- **File:** `internal/model/premium_sms_test.go` (NEU, ≈90 LoC) — Grenzwerttest der Frist
  (± 1 Sekunde um 30 Tage, Muster S2a AC-4/AC-5) für `DerivePremiumSmsReplyState`.
- **File:** `internal/store/trip_flat_fields_test.go` (MODIFY, +≈50 LoC) — Premium-SMS-Fälle in
  die bestehenden Roundtrip-/Nil-Reset-Tests aufgenommen (Muster
  `TestLoadTrip_DerivesFlatSlotChannelFieldsFromReportConfig` `:20`,
  `TestLoadTrip_NoReportConfigLeavesFlatFieldsNil` `:101`).

**Vertrag:**

- **File:** `docs/reference/api_contract.md` (MODIFY) — drei Stellen nachziehen: `:579`
  (`send_premium_sms`-Zeile — der Hinweis „kein eigenes Go-Struct-Feld … folgt erst mit S3" ist
  jetzt eingelöst), `:741-743` (Trip-DTO-Flach-Feld-Block, viertes Feld ergänzen), `:2690-2736`
  (Profil-Response-Beispiel + Field-Definitions-Tabelle, vier neue Zeilen) und `:2832-2833`
  (`User`-Struct-Kommentar „kein Frontend, keine Auth-Profile-Ausgabe in dieser Scheibe" wird
  revidiert). Changelog-Eintrag.

## Estimated Scope

- **LoC (Produktivcode):** ≈ 231 (Frontend ≈140: VTBriefingChannels +35, EditReportConfigSection
  +35, VersandTab +15, channelConnectionStatus +4, premiumSmsChannelState.ts +55; Go ≈91:
  premium_sms.go +45, tier.go +10, trip.go(model) +1, store/trip.go +8, auth.go +25 minus
  Überschneidung — grob gerundet).
- **LoC (Tests):** ≈ 480 (Frontend ≈250: dedupe-Erweiterung 120, state-Test 70, gating-Test 60;
  Go ≈230: profile_test.go 90, premium_sms_test.go 90, trip_flat_fields_test.go 50).
- **Gesamt erwartet:** ≈ 700-750. Überschreitet das Default-Limit (250/Workflow) deutlich —
  LoC-Override bei Implementierungsbeginn erwartungsgemäß nötig (Begründung: zwei Schichten,
  vier Mount-Punkte, Kontext-Trennung als eigene Zusicherung). Doku zählt nicht mit.
- **Files:** 5 CREATE (3 Frontend-Tests + 1 Frontend-Modul + 2 Go-Dateien, davon 1 Test) +
  11 MODIFY.
- **Effort:** medium-high (zwei Schichten, keine neue Fachlogik — nur Sichtbarmachung
  bestehender Backend-Zustände).
- **Risiko:** MEDIUM. Größtes Einzelrisiko ist die Kontext-Trennung (AC-1) — sie ist leicht zu
  übersehen, weil `VTBriefingChannels.svelte` strukturell für beide Kontexte identisch aussieht
  und der bestehende Platzhalter in **beiden** heute gleich (fest deaktiviert) rendert. Zweites
  Risiko: die Cross-Language-TTL-Duplikation (Known Limitations).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/feat_1676_s1_premium_sms_rueckkanal.md` | Vorgänger-Spec | liefert `model.User.PremiumSmsReplyTo`/`PremiumSmsReplyAt` (`internal/model/user.go:37-38`) — alleinige Rohdatenquelle |
| `docs/specs/modules/feat_1676_s2a_premium_sms_versand.md` | Vorgänger-Spec, live | Sendepfad, Fail-Closed, `PREMIUM_SMS_REPLY_TTL` (`premium_sms.py:39`), `premium_sms_allowed()` (Python-Vorbild für das neue Go-Pendant) |
| `docs/adr/0049-premium-sms-vierter-kanal.md` | ADR | Kanalname, „nur Trip-Briefing", die vier fachlichen SMS-vs-Premium-SMS-Unterschiede |
| `shared/versand-tab/channelContactLabel.ts` | Vorbild | geteilter Helfer statt Doppel-Kopie — Muster für `premiumSmsChannelState.ts` |
| `shared/versand-tab/channelConnectionStatus.ts` | module, MODIFY | `ConnectionProfile` als einzige kanonische Profilform; `Dot`-Atom akzeptiert bereits `tone="warn"` (`ui/dot/Dot.svelte:10`) |
| `shared/versand-tab/__tests__/channel_checkbox_dedupe_render.test.ts` | Test-Vorbild, MODIFY | wichtigstes Regressionsnetz — hält beide Komponenten synchron |
| `internal/model/tier.go::SmsAllowed` | Vorbild, NICHT wiederverwendet | Struktur für `PremiumSmsAllowed` — `SmsAllowed` lässt `standard` durch, das darf Premium-SMS nicht |
| `internal/store/trip.go::deriveFlatFields` | module, MODIFY | Ableitungs-/Reset-Muster für `Trip.SendPremiumSms` |
| `internal/handler/config_merge.go::mergeConfigMap` | module | generischer Merge — kein neuer Handler-Zweig nötig |
| `internal/handler/auth.go::RequestedAt`/`EmailVerified` | Vorbild | Doppelmuster Rohwert (Zeitstempel) vs. abgeleiteter Zustand — beide Formen werden hier gebraucht |
| `docs/reference/api_contract.md` | Vertrag | drei Stellen erwarten diese Scheibe bereits explizit |

## Implementation Details

### Kontext-Trennung: dasselbe Gating-Muster wie der Telegram-Kurzstil (AC-1)

`VTBriefingChannels.svelte` wird von `VersandTab.svelte` in zwei Kontexten gemountet: `route`
(`/trips/[id]`, Zeilen 204-212, MIT `onTelegramStyleChange`) und `vergleich` (`/compare/[id]`,
`/compare/new`, Zeilen 234-247, OHNE `onTelegramStyleChange`). Die Komponente selbst rendert den
Kurzstil-Schalter schon heute nur `{#if onTelegramStyleChange}` (Zeile 155) — eine reine
Prop-Anwesenheitsprüfung, kein `context`-String-Vergleich. Premium-SMS folgt demselben Muster:
neue Prop `onPremiumSmsChange`, nur vom `route`-Zweig übergeben, Block nur `{#if
onPremiumSmsChange}` sichtbar. Ein `context === 'route'`-Vergleich direkt in der Komponente wäre
technisch gleichwertig, aber ein zweiter, redundanter Kontrollpunkt — das etablierte Muster
(Prop-Anwesenheit) reicht und bleibt konsistent zum Bestand.

### Geteilter Zustands-Helfer, keine dritte Kopie

`premiumSmsChannelState(profile: ConnectionProfile | null | undefined)` liefert ein Objekt mit
`disabled`, `tone` (`'good' | 'warn' | 'neutral'`), `statusLabel`, `hint` und `reportedAtLabel`.
Eingabe sind ausschließlich die vier neuen `ConnectionProfile`-Felder — keine
Datums-Arithmetik im Helfer (AC-5). `disabled = !profile.premium_sms_allowed ||
profile.premium_sms_reply_state !== 'fresh'`. Der Hinweistext für `stale` nennt das Meldedatum,
aber **keine Frist-Zahl** („Rückadresse verfallen — zuletzt gemeldet am …", nicht „vor mehr als
30 Tagen") — eine Zahl im Text wäre dieselbe Kopie in Prosaform.

### Server leitet den Zustand ab — zwei Schichten, eine Verantwortung

`GET /api/auth/profile` ist ein Go-Endpoint; die 30-Tage-Frist ist heute ausschließlich als
`PREMIUM_SMS_REPLY_TTL` im Python-Kern definiert (`premium_sms.py:39`), der den Sendepfad prüft.
Damit die Anzeige nicht doch eine eigene JS-Konstante braucht, bekommt `internal/model` eine
**eigene, bewusst benannte** Go-Konstante `PremiumSmsReplyTTL = 30 * 24 * time.Hour` mit einem
Code-Kommentar, der explizit auf `premium_sms.py:39` verweist. Das ist **kein** Widerspruch zur
Vorgabe „Frist nicht ins Frontend kopieren" — sie bleibt serverseitig, auf der einzigen Schicht,
die den HTTP-Endpoint für das Profil bedient. Die Duplikation zwischen Go- und Python-Backend
ist real, aber strukturell bedingt (zwei getrennte Prozesse ohne gemeinsame Konstante) und wird
unter „Known Limitations" ausgewiesen, nicht verschwiegen.

### Eigenes Tarif-Gate (analog D7 aus S2a)

`model.PremiumSmsAllowed(tier)` prüft ausschließlich `tier == "premium"`. Keine Delegation an
`SmsAllowed`, das `standard` **und** `premium` durchlässt (`tier.go:3-6`) — sonst könnte ein
`standard`-Nutzer den Kanal einschalten, obwohl das Backend ihn beim Versand ohnehin sperren
würde (S2a AC-8) — eine Checkbox, die etwas verspricht, das serverseitig nie passiert.

### `UpdateProfileHandler` bleibt unverändert (AC-7)

Die Decode-Struct (`auth.go:541-547`) nimmt die vier neuen Felder **nicht** auf. Diese Scheibe
ist rein lesend — würde die gelernte Rückadresse editierbar, fiele die S2a-Zusage „Empfänger
ausschließlich die gelernte Rückadresse, niemals aus der Konfiguration" strukturell in sich
zusammen: ein Nutzer könnte sich selbst eine beliebige `premium_sms_reply_to` eintragen und
Premium-SMS an eine fremde Nummer schicken lassen.

### Flach-Feld `Trip.SendPremiumSms` — Vertrags-Vollständigkeit, kein neuer Schreibpfad

Analog den drei bestehenden Feldern (`trip.go:161-163`) wird `SendPremiumSms` in
`deriveFlatFields` zuerst hart auf `nil` zurückgesetzt (neben den bestehenden Resets,
`store/trip.go:63-70` — sonst bliebe bei verschwindender Quelle ein stiller Altwert stehen,
Fix-Loop F001 aus S2a), dann bedingt aus `rc["send_premium_sms"]` gesetzt (`:79-87`). Der
Client schickt weiterhin `report_config.send_premium_sms`; `mergeConfigMap` transportiert das
generisch. Das Frontend liest ohnehin `report_config`, nicht die Flach-Felder — das Flach-Feld
ist Vertrags-Vollständigkeit, keine Voraussetzung für die UI (wie in S2a D8 für die anderen drei
Felder dokumentiert).

### Kontrast: Meldedatum ist ein Daten-Label, keine Fußnote

`.vt-channel-status-label` (`VTBriefingChannels.svelte:226-231`) nutzt bereits bewusst
`--g-ink-3` statt `--g-ink-4` „in beiden Zuständen" (Zeile 219-Kommentar, Kontrast-Leitprinzip).
Das Meldedatum-Label folgt derselben Klasse/Farbe — nicht `--g-ink-4` (2,85:1 auf Weiß, laut
CLAUDE.md strikt Platzhalter/Disabled vorbehalten).

## Expected Behavior

- **Input:** Nutzer öffnet `/trips/new` oder `/trips/[id]` → Versand-/Kanäle-Bereich; Klick auf
  die Premium-SMS-Checkbox (nur wenn nicht `disabled`).
- **Output:** `report_config.send_premium_sms` wird beim Speichern mitgeschrieben (Trip-Anlage:
  `EditReportConfigSection`-Write-Back; Trip-Detail: `VersandTab`-Write-Back → bestehender
  Speicherpfad, unverändert). `GET /api/auth/profile` liefert zusätzlich
  `premium_sms_reply_to`/`_at` (roh, `omitempty`), `premium_sms_reply_state`
  (`"none"|"stale"|"fresh"`, immer vorhanden) und `premium_sms_allowed` (bool, immer vorhanden).
- **Side effects:** keine. Kein neuer Schreibpfad für die gelernte Rückadresse, kein neuer
  Cron-Job, keine neue Persistenzdatei. `/compare/*` bleibt unverändert (weiterhin fester
  Platzhalter).

## Acceptance Criteria

- **AC-1:** Given derselbe geteilte Kanal-Baustein wird sowohl im Trip-Briefing (`/trips/[id]`,
  `/trips/new`) als auch im Orts-Vergleich (`/compare/[id]`, `/compare/new`) gerendert / When ein
  Nutzer mit vollständig gültigem Premium-Profil (Premium-Tier, frische Rückadresse) eine dieser
  Seiten öffnet / Then erscheint eine schaltbare Premium-SMS-Checkbox **ausschließlich** im
  Trip-Briefing — im Orts-Vergleich bleibt der Kanal weiterhin fest deaktiviert mit dem
  unveränderten „bald verfügbar"-Hinweis.
  - Prüfort: **ZWEI Nähte, nicht eine** (korrigiert in der RED-Phase, s.u.). (a) SSR von
    `VTBriefingChannels` mit identischem Profil in beiden Kontexten — nur `route` zeigt ein
    editierbares `<input>` für `channel-premium-sms`. (b) SSR von `VersandTab` in beiden Zweigen —
    dort unterscheidet ohne Profil nicht `disabled`, sondern **ob der schaltbare Block überhaupt
    entsteht** (`channel-status-premium-sms` vorhanden vs. „bald verfügbar").
  - 🔴 **Korrektur meines eigenen Prüforts:** Die erste Fassung nannte nur Naht (a). Da die
    Komponente über **Prop-Anwesenheit** gated und nicht über den `context`-String, wäre die von
    dieser Spec selbst vorgeschriebene Mutation („`VersandTab` übergibt `onPremiumSmsChange` auch
    im `vergleich`-Zweig") an Naht (a) **unsichtbar** geblieben — Prüfort ≠ Wirkort, genau der
    Fehler, den die Leitfrage abfangen soll. Naht (b) ist die wirksame.
  - Test: `shared/versand-tab/__tests__/premium_sms_context_gating_render.test.ts::premium_sms_switchable_only_in_route_context`
    und `::vergleich_behaelt_den_unveraenderten_platzhalter_hinweis`

- **AC-2:** Given ein und dasselbe Nutzerprofil / When sowohl die Trip-Anlage
  (`EditReportConfigSection`) als auch die Trip-Detail-Seite (`VTBriefingChannels`) den
  Kanalblock rendern / Then zeigen beide Komponenten für die Premium-SMS-Zeile identischen
  Beschriftungstext, identischen Verbindungsstatus (Dot + Label) und identischen
  Deaktiviert-Zustand — keine der beiden Komponenten weicht ab.
  - Prüfort: `channel_checkbox_dedupe_render.test.ts`, erweitert um Premium-SMS-Fälle nach dem
    bestehenden AC-3-Muster (Zeilen 158-183: Text-Vergleich zwischen beiden Renderings für
    identisches Profil).
  - Test: `channel_checkbox_dedupe_render.test.ts::beide_komponenten_zeigen_fuer_identisches_profil_denselben_premium_sms_zustand`

- **AC-3:** Given drei Profile — keine gelernte Rückadresse, eine laut Server veraltete
  Rückadresse, eine frische Rückadresse / When der Kanalblock die Premium-SMS-Zeile für jedes der
  drei Profile rendert / Then zeigt jeder der drei Fälle einen paarweise unterschiedlichen
  Hinweistext — kein Nutzer kann „keine Adresse" mit „veraltete Adresse" verwechseln, weil beide
  denselben Text zeigen.
  - Prüfort: SSR-Rendering aller drei Profile, Text-Extraktion des `channel-premium-sms-hint`-Blocks,
    paarweiser Ungleichheits-Vergleich.
  - Test: `premium_sms_channel_state.test.ts::state_labels_are_pairwise_distinct`,
    `channel_checkbox_dedupe_render.test.ts::premium_sms_drei_zustaende_zeigen_unterschiedlichen_hinweistext`

- **AC-4:** Given eine gelernte Rückadresse ist laut Server frisch (`premium_sms_reply_state ==
  "fresh"`) / When die Premium-SMS-Zeile gerendert wird / Then sind **sowohl** die Zielnummer
  (`premium_sms_reply_to`) **als auch** das Meldedatum (aus `premium_sms_reply_at`) im
  sichtbaren Text enthalten — nicht nur eines von beiden.
  - Prüfort: SSR-Text der Premium-SMS-Zeile enthält sowohl die Roh-Nummer aus dem Fixture-Profil
    als auch eine aus dem Fixture-Zeitstempel abgeleitete Datumsdarstellung.
  - Test: `channel_checkbox_dedupe_render.test.ts::premium_sms_fresh_zeigt_zielnummer_und_meldedatum`

- **AC-5:** Given der Server liefert `premium_sms_reply_state` als fertig abgeleiteten Wert, der
  einem rohen `premium_sms_reply_at` bewusst widerspricht (z. B. `reply_at` von vor einer Stunde,
  aber `state: "stale"`) / When die Oberfläche das Profil rendert / Then folgt die Anzeige
  ausnahmslos dem gelieferten `state`-Feld, nicht einer im Frontend nachgerechneten Frist — das
  belegt, dass im Frontend-Code keine 30-Tage-Konstante existiert.
  - Prüfort: Unit-Test des `premiumSmsChannelState`-Helfers mit einem absichtlich
    widersprüchlichen Fixture-Profil; zusätzlich zwei „stale"-Fixtures mit stark
    unterschiedlichem Alter (31 Tage vs. 400 Tage) müssen einen Hinweistext liefern, der sich nur
    im Meldedatum, nicht in einer Tage-Zahl unterscheidet.
  - Test: `premium_sms_channel_state.test.ts::state_feld_gewinnt_gegen_lokal_berechnetes_alter`,
    `premium_sms_channel_state.test.ts::hinweistext_nennt_keine_tage_zahl`
  - Mutation: im Helfer wird `Date.now() - replyAt > THIRTY_DAYS_MS` statt
    `profile.premium_sms_reply_state !== 'fresh'` geprüft.

- **AC-6:** Given ein Nutzer hat Tier `standard` (nicht `premium`) UND eine frische gelernte
  Rückadresse / When der Kanalblock gerendert wird / Then bleibt die Premium-SMS-Checkbox
  deaktiviert, obwohl derselbe Nutzer für den normalen SMS-Kanal (`sms_allowed`) als berechtigt
  gilt — das Tarif-Gate ist eigenständig, nicht von `sms_allowed` abgeleitet.
  - Prüfort: (a) Go-Funktionstest `model.PremiumSmsAllowed("standard") == false`, (b)
    SSR-Test mit Profil `{sms_allowed: true, premium_sms_allowed: false, premium_sms_reply_state:
    "fresh"}` — Checkbox bleibt `disabled`.
  - Test: `internal/model/premium_sms_test.go::TestPremiumSmsAllowedExcludesStandardTier`,
    `premium_sms_channel_state.test.ts::disabled_bei_tarif_sperre_trotz_frischer_adresse`

- **AC-7:** Given ein Nutzer sendet `PUT /api/auth/profile` mit `premium_sms_reply_to` und
  `premium_sms_reply_at` im Body (Versuch, die gelernte Rückadresse selbst zu setzen) / When der
  Request verarbeitet wird / Then bleiben die zuvor über den internen Lernpfad (S1) gespeicherten
  Werte in `user.json` unverändert — der Endpoint nimmt die Felder gar nicht erst entgegen.
  - Prüfort: Go-Handler-Test — `user.json` vor dem PUT mit einer bekannten S1-Rückadresse
    vorbelegen, PUT mit abweichenden Werten senden, anschließendes `GET` muss den
    Ursprungswert zeigen.
  - Test: `internal/handler/profile_test.go::TestUpdateProfileHandlerIgnoresPremiumSmsReplyFields`
  - Mutation: `PremiumSmsReplyTo`/`PremiumSmsReplyAt` werden zur Decode-Struct in
    `UpdateProfileHandler` hinzugefügt.

- **AC-8:** Given ein Trip hat `report_config.send_premium_sms = true` gespeichert, danach wird
  `report_config` komplett entfernt (z. B. Trip ohne Report-Konfiguration) / When der Trip erneut
  geladen wird / Then ist `Trip.SendPremiumSms` zuerst `true`, nach dem Entfernen der Quelle
  `nil` — kein stehen gebliebener Altwert.
  - Prüfort: Roundtrip-Test analog dem bestehenden Muster für `SendSms`
    (`trip_flat_fields_test.go:20`, `:101`).
  - Test: `internal/store/trip_flat_fields_test.go::TestLoadTrip_DerivesSendPremiumSmsFromReportConfig`,
    `::TestLoadTrip_SendPremiumSmsResetToNilWhenReportConfigMissing`
  - Mutation: der Reset auf `nil` (`store/trip.go:63-70`-Block) wird für `SendPremiumSms`
    weggelassen.

- **AC-9:** Given eine gelernte Rückadresse ist frisch oder veraltet und das Meldedatum wird
  angezeigt / When die Premium-SMS-Zeile gerendert wird / Then verwendet das Meldedatum-Label
  nicht die blasseste Textfarbe (`--g-ink-4`), sondern mindestens `--g-ink-3` — dieselbe Farbe,
  die der bestehende Verbindungsstatus-Text bereits aus Kontrastgründen verwendet.
  - Prüfort: die am gerenderten Element **wirkende** Farbe wird aufgelöst — Inline-`style` gewinnt,
    sonst die eigenen Klassen des Elements gegen das kompilierte Scoped-CSS. Verlangt wird eine
    **eigene explizite** Farbe am Label; Vererbung reicht nicht.
  - 🔴 **Korrektur meines eigenen Prüforts:** Die erste Fassung verlangte, den HTML-Ausschnitt auf
    die Zeichenkette `--g-ink-4`/`--g-ink-3` zu prüfen. Das hätte einen **Inline-Style erzwungen**
    und gerade die von dieser Spec empfohlene Lösung (dieselbe Klasse wie
    `.vt-channel-status-label`) rot gemacht, weil Komponenten-CSS im SSR-Body nicht auftaucht. Ein
    AC, das die eigene Empfehlung verbietet, ist ein Spec-Fehler, kein Testproblem.
  - Test: `channel_checkbox_dedupe_render.test.ts::meldedatum_label_nutzt_nicht_die_platzhalter_kontrastfarbe`

- **AC-10:** Given ein Trip hat `report_config.send_premium_sms = true` gespeichert und eine
  frische Rückadresse ist hinterlegt / When die Trip-Anlage ODER die Trip-Detail-Seite den
  Versand-Bereich rendert / Then ist die Premium-SMS-Checkbox als angehakt dargestellt — der
  gespeicherte Zustand wird korrekt aus `report_config` geladen, nicht nur aus dem Profil
  abgeleitet.
  - Prüfort: SSR-Test mit `reportConfig={send_premium_sms: true}` und frischem Profil, für beide
    Komponenten — `checked`-Attribut muss gesetzt sein.
  - Test: `channel_checkbox_dedupe_render.test.ts::premium_sms_checked_spiegelt_report_config_in_beiden_komponenten`

- **AC-11:** Given die Verfallsfrist der gelernten Rückadresse existiert zwangsläufig zweimal — im Python-Sendepfad und in der neuen Go-Ableitung / When jemand künftig nur eine der beiden Zahlen ändert / Then schlägt ein Wächter fehl und benennt beide Fundstellen — die Oberfläche kann nicht „frisch" anzeigen, während der Sendepfad denselben Wert bereits blockt.
  - Prüfort: die **beiden Quellen selbst**, gegeneinander gelesen — nicht die Oberfläche. Muster und Werkzeug-Klasse liegen vor: `tests/test_egress_inventory_drift.py` liest die Go-Quelle als **Daten** und die Python-Seite über den echten Import (`# doc-compliance-test`-Ausnahme, sonst wäre eine Dateiinhalt-Prüfung als Verhaltensnachweis verboten). Zweites Vorbild: `tests/test_adr_index_drift.py`.
  - Warum das ein AC ist und keine Fußnote: der Drift-Fall **ist** der Fehler, den diese Scheibe verhindern soll. Eine Anzeige, die der Wirklichkeit widerspricht, ist schlechter als keine — besonders dort, wo es keine zweite Quelle gibt.
  - Test: `tests/test_premium_sms_ttl_drift.py::go_und_python_frist_sind_deckungsgleich`

- **AC-12:** Given ein Trip hat **ausschließlich** Premium-SMS aktiviert, alle anderen Kanäle aus / When der Versand-Bereich gerendert wird / Then erscheint **kein** Leerzustand „Kein Kanal aktiv" — die Oberfläche behauptet nicht, es sei kein Kanal eingeschaltet, während das Briefing tatsächlich hinausgeht.
  - Prüfort: **beide** Wirkorte, und der Zähler sitzt nicht dort, wo die Checkbox sitzt — auf `/trips/[id]` hält ihn die Ebene darüber (`VersandTab`), auf `/trips/new` die Komponente selbst (`EditReportConfigSection`). Jeder Fall trägt seine Gegenprobe: alle vier Kanäle aus ⇒ der Leerzustand **muss** erscheinen. Ohne sie wäre der Test auch grün, wenn das geprüfte Element im gewählten Aufbau nie entsteht.
  - **Herkunft (Tech-Lead-Entscheid 2026-08-11, nach der PO-Freigabe):** Der Befund kam aus dem GREEN-Lauf, nicht aus der Analyse. Aufgenommen, weil er genau der Fehler dieser Scheibe an einer anderen Stelle ist — eine Oberfläche, die einen Zustand falsch darstellt. Nutzersichtbar und mit Gating-Wirkung, deshalb kein Sammel-Eintrag.
  - **Nebenwirkung, die dabei einen Bestandsfehler behoben hat:** Der Leerzustand war im serverseitigen Rendern **überhaupt nicht erreichbar**, weil `onMount` dort nie läuft und `send_email` beim Rendern immer `true` war. Die drei bestehenden Kanal-Flags werden jetzt wie `send_premium_sms` beim Erzeugen aus `report_config` gelesen. Folge über die Messbarkeit hinaus: ein Trip ohne E-Mail zeigt im ersten Rahmen nicht mehr fälschlich „E-Mail angehakt".
  - Test: `channel_checkbox_dedupe_render.test.ts`, Abschnitt „#1717 Kanalzaehler"

## Nachweisgrenzen — was diese Scheibe NICHT beweist

- **Keine Geräte-Zustellung.** Wie in S2a: dass eine über die neue Checkbox aktivierte
  Premium-SMS tatsächlich am Garmin-Gerät ankommt, ist mit den Mitteln dieser Scheibe nicht
  beweisbar — bleibt #1533.
- **Kein neuer Beweis für den Speicherpfad selbst.** Dass ein Klick auf die Checkbox letztlich zu
  einem `PUT`/`POST` führt, der `report_config` persistiert, ist Bestandsmechanik (identisch zu
  `send_sms`/`send_telegram`) und wird von dieser Scheibe nicht neu bewiesen — nur die
  **zusätzliche** Zeile `send_premium_sms` im selben, bereits bewiesenen Mechanismus.
  Playwright-Bestandssuiten (`versand-tab.spec.ts`, `issue-609-sms-profil.spec.ts`) müssen grün
  bleiben; keine dieser Suiten hängt heute an `channel-premium-sms` (gemessen: kein Treffer in
  `frontend/e2e/`), also kein Konflikt zu erwarten, aber auch kein neuer E2E-Nachweis für den
  Klick-Pfad in dieser Spec.
- **Kein Beweis, dass die Go-TTL-Konstante mit der Python-TTL-Konstante übereinstimmt.** Beide
  Werte sind zum Zeitpunkt dieser Spec identisch (30 Tage), aber es existiert kein automatischer
  Abgleich zwischen den beiden Prozessen. Siehe Known Limitations.
- **Fresh-Eyes + Browser-Gate sind Prozess, kein AC.** Frontend-Scope löst
  `staging_gate.py --write-verdict` aus (sechs Kernseiten in echtem Chromium,
  `console(type=error)`/`pageerror`-Sammlung); ohne bestandenen Lauf entsteht keine Attestation,
  kein Prod-Deploy. Zusätzlich ein `fresh-eyes-inspector`-Lauf auf Screenshots **ohne**
  Bug-Kontext (Confirmation-Bias-Schutz) — insbesondere für die drei Zustände der Premium-SMS-Zeile
  und die Kontrast-Zusage aus AC-9. Beides ist Verifikations-Ablauf, kein eigenes AC.

## Mutations-Gegenprobe

Pflicht laut Projektregel — je AC eine gezielte Verfälschung, die mindestens einen Test rot
machen MUSS:

| AC | Gezielte Verfälschung | Test, der dadurch rot werden MUSS |
|---|---|---|
| AC-1 | Gating-Prop-Prüfung entfernt / `VersandTab` übergibt `onPremiumSmsChange` auch im `vergleich`-Zweig | `premium_sms_switchable_only_in_route_context` |
| AC-2 | `EditReportConfigSection` bekommt eine eigene, leicht abweichende Kopie der Zustandslogik statt `premiumSmsChannelState()` zu importieren | `beide_komponenten_zeigen_fuer_identisches_profil_denselben_premium_sms_zustand` |
| AC-3 | Hinweistext für „stale" und „none" werden auf denselben generischen String vereinheitlicht | `premium_sms_drei_zustaende_zeigen_unterschiedlichen_hinweistext` |
| AC-4 | Meldedatum wird aus dem angezeigten Text entfernt (nur Zielnummer bleibt) | `premium_sms_fresh_zeigt_zielnummer_und_meldedatum` |
| AC-5 | Helfer berechnet `disabled` zusätzlich über `Date.now() - replyAt` statt ausschließlich über `premium_sms_reply_state` | `state_feld_gewinnt_gegen_lokal_berechnetes_alter` |
| AC-6 | `PremiumSmsAllowed(tier)` delegiert an `SmsAllowed(tier)` statt eigener Prüfung | `TestPremiumSmsAllowedExcludesStandardTier` |
| AC-7 | Die Felder werden zur Decode-Struct hinzugefügt **UND zugewiesen** (`user.PremiumSmsReplyTo = …`) | `TestUpdateProfileHandlerIgnoresPremiumSmsReplyFields` |
| | 🔴 **Korrektur (Adversary F001):** Die erste Fassung verlangte nur „zur Decode-Struct hinzufügen". Das ist in Go ein **No-Op** — ein dekodiertes Feld ohne Zuweisung ändert nichts, die Mutation blieb grün und bewies dadurch nichts. Gefährlich ist erst die **Zuweisung**, und die wird gefangen. Eine Mutation, die den Zustand nicht verändert, ist keine Gegenprobe. | |
| AC-8 | Reset-Zeile `trip.SendPremiumSms = nil` in `deriveFlatFields` weggelassen | `TestLoadTrip_SendPremiumSmsResetToNilWhenReportConfigMissing` |
| AC-9 | Meldedatum-Label bekommt versehentlich `--g-ink-4` statt `--g-ink-3` (Copy-Paste aus einem Platzhalter-Hinweis) | `meldedatum_label_nutzt_nicht_die_platzhalter_kontrastfarbe` |
| AC-10 | Initialisierung von `send_premium_sms` aus der `reportConfig`-Prop weggelassen (Feld bleibt beim Laden immer `false`) | `premium_sms_checked_spiegelt_report_config_in_beiden_komponenten` |
| AC-11 | Go-Frist auf 7 Tage geändert, Python-Frist bleibt bei 30 (die realistische Drift: eine Session ändert einen Wert und kennt den anderen nicht) | `go_und_python_frist_sind_deckungsgleich` |
| AC-12 | Kanalzähler wieder auf drei Kanäle zurückgedreht — **je Wirkort einzeln** (`VersandTab` und `EditReportConfigSection`), weil eine gemeinsame Quelle nicht existiert | Abschnitt „#1717 Kanalzaehler"; beide Mutationen wurden gefangen, jede mit der Meldung des betroffenen Wirkorts |

## Known Limitations

- **Cross-Language-TTL-Duplikation — bewacht, nicht hingenommen (AC-11).** Die Frist muss in Go
  ein zweites Mal als Konstante existieren, weil Go und Python getrennte Prozesse sind. Der
  Entwurf dieser Spec hat das als hingenommenes Risiko eingetragen („ein automatischer Abgleich
  wäre eigene Arbeit"). **Das ist zurückgewiesen:** genau dieser Drift-Fall ist der Fehler, den
  diese Scheibe verhindern soll — eine Oberfläche, die „frisch" zeigt, während der Sendepfad
  blockt. Ihn als Fußnote zu führen, hebt den Zweck der Scheibe auf.

  Das Projekt hat das Muster bereits: `tests/test_egress_inventory_drift.py` gleicht eine
  Python-Liste mit `internal/egress/inventory.go` ab (Go-Quelle als **Daten** gelesen,
  Python-Seite über den echten Import, `# doc-compliance-test`-Ausnahme). Begründung dort
  wörtlich: „zwei Listen driften auseinander … wer 14 Türen einzeln bewacht, vergisst irgendwann
  eine." Zweites Vorbild: `tests/test_adr_index_drift.py`. Der Abgleich ist damit kein Neubau,
  sondern eine vorhandene Werkzeug-Klasse — Aufwand: ein Test.

  Verbleibende Grenze: der Wächter erzwingt Gleichheit der **Zahl**, nicht der Semantik. Wer in
  einem der beiden Prozesse die Bedeutung der Frist ändert (z.B. Vergleich `>=` statt `>`), fällt
  ihm nicht auf.
- **Eine anfängliche, wortgleiche Kopie der Zustandslogik wird von keinem Test hier erkannt.**
  Der Dedupe-Test (AC-2) beweist Verhaltensgleichheit zum Zeitpunkt der Prüfung, keine
  Quelltext-Identität — käme in `EditReportConfigSection` eine zunächst identische, aber separat
  gepflegte Kopie statt eines Imports zustande, wäre das erst bei der nächsten Änderung sichtbar,
  die dann divergiert (wie es `channelContactLabel.ts` vor seiner Extraktion vorgemacht hat,
  Issue #1510).
- **Kein Playwright-Klickpfad-Test für Premium-SMS neu.** Die Bestandssuiten decken die
  bestehenden drei Kanäle ab; ein neuer End-to-End-Klicktest für Premium-SMS ist nicht Teil
  dieser Scheibe (s. Nachweisgrenzen).
- **`/trips/new` bleibt strukturell auf `EditReportConfigSection` statt `VersandTab`.**
  Vorbestehender, bewusst nicht behobener Bruch der Trip/Compare-Teilungsregel (#1199).
- **Kein Beweis für Geräte-Zustellung** — bleibt #1533.

## Test Coverage

- `shared/versand-tab/__tests__/channel_checkbox_dedupe_render.test.ts` (MODIFY) — AC-2, AC-3,
  AC-4, AC-9, AC-10 (SSR beider Komponenten, kein Mock).
- `shared/versand-tab/__tests__/premium_sms_channel_state.test.ts` (NEU) — AC-3, AC-5, AC-6
  (reine Funktionsprüfung, node:testbar).
- `shared/versand-tab/__tests__/premium_sms_context_gating_render.test.ts` (NEU) — AC-1.
- `internal/model/premium_sms_test.go` (NEU) — AC-6 (Funktionsteil), TTL-Grenzwert analog S2a
  AC-4/AC-5.
- `internal/handler/profile_test.go` (MODIFY) — AC-7, Feldmenge der vier neuen Profil-Felder.
- `internal/store/trip_flat_fields_test.go` (MODIFY) — AC-8.

Testdateien liegen unter `frontend/src/lib/components/shared/versand-tab/__tests__/` bzw.
`internal/model/`, `internal/handler/`, `internal/store/` — Namen nach Verhalten, nicht nach
Issue-Nummer.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue. Diese Scheibe exponiert ausschließlich die in ADR-0049 bereits
  getroffenen Entscheidungen (Kanalname, „nur Trip-Briefing", eigenes Tarif-Gate) in der
  Oberfläche — sie trifft keine neue Architekturentscheidung und weicht von keiner bestehenden
  ab.

## Changelog

- 2026-08-11: Initial spec erstellt — Issue #1717, Scheibe S3 (Premium-SMS in der Oberfläche)
