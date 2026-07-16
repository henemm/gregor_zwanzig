# Context: fix-1270-compare-channel-preview

**Issue:** #1270 — Hub-Vorschau-Tab leer (Vorschau-Daten nicht verfügbar) + Telegram/SMS-Vorschau nur Platzhalter
**Track:** Full Process (Intake-Score 5/6)
**Erstellt:** 2026-07-16

## Request Summary

Der Vorschau-Tab im Orts-Vergleich-Hub zeigt „Vorschau-Daten nicht verfügbar."; Telegram und
SMS liefern nur Platzhalter-Text. Das Ticket vermutete (a) einen datenbedingten Leerfall und
(b) reine UI-Arbeit, weil „Renderer existieren serverseitig". **Beide Annahmen sind falsch** —
die Recherche legt eine deutlich tiefere Lücke frei (s. Kernbefunde).

## Kernbefunde (widersprechen dem Ticket)

### KB-1 · Die E-Mail-Vorschau zeigt einen Fake-Ort, nicht den Vergleich des Nutzers

`CompareTabs.svelte:610-637` ruft `POST /api/_validator/compare-email-preview` auf und übergibt
**nur** `profile`, `time_window`, `target_date`, `winner_tags` — **nicht die Orte des Presets**.
Der Endpoint (`api/routers/validator.py:313`) delegiert an
`src/services/validator_render_service.py:147 render_compare_email_preview()`, das einen
**hartcodierten Stub-Ort** baut:

```python
stub_location = SavedLocation(id="preview-1", name="Vorschau-Ort", lat=47.0, lon=11.0, elevation_m=2000)
```

Lokal gerendert (deterministisch, kein Netz) ergibt das wörtlich: „Orte **1**", eine einzige
Spalte **„Vorschau-Ort"**, und **alle Metrik-Werte „—"**. Der Tab war also nie eine echte
Vorschau — er hängt an einem **Renderer-Testendpoint** (Issue #464, gebaut für den
externen Validator, Präfix `_validator` = Observability-Endpoint für Tests, `router.go:153`).
Das ist die eigentliche Ursache des „leeren" Eindrucks — **kein Datenproblem**.

### KB-2 · Zusätzlich: ein toter Baustein rendert die Missing-Box bedingungslos

`CompareTabs.svelte:1252-1257` mountet `CompareBriefingPreview` mit `profileId`/`channel`/
`subscriptionName`/`emailView` — aber **nie** `profile`/`data`. Die Komponente
(`molecules/CompareBriefingPreview.svelte:24`) prüft `{#if !profile || !data}` → rendert
**immer** `ComparePreviewMissing` = „Vorschau-Daten nicht verfügbar." — unabhängig vom Kanal
und zusätzlich zum (Stub-)iframe. `emailView` ist in den Props gar nicht deklariert (toter Prop).
Das ist der wörtlich im Ticket zitierte Text.

### KB-3 · Compare-Briefing-Versand ist E-Mail-only — Telegram/SMS werden gespeichert, aber ignoriert

`send_one_compare_preset` (`src/services/scheduler_dispatch_service.py:245-338`) ist der
**einzige** Report-Versandpfad (Daily-Loop `:27→:107`, Einzelversand `:341→:367`,
API `api/routers/scheduler.py:137`/`:205`). Er rendert nur `render_compare_email` und sendet
nur `EmailOutput(settings).send(...)` (`:322`). Die Preset-Felder `send_telegram`/`send_sms`
(`internal/model/compare_preset.go:86-87`, `src/app/models.py:899-900`) werden vom Frontend
als **„Briefing-Kanäle"** angeboten und persistiert (`compareEditorSave.ts:159-160`), im
Report-Pfad aber **nie gelesen**. → Ein Nutzer, der Telegram/SMS für sein Vergleichs-Briefing
aktiviert, bekommt darüber **nichts**. `compare_alert.py:229` dokumentiert das sogar im
Docstring: *„Kanal ist IMMER {"email"} — Compare-Versand ist heute E-Mail-only."*

**Konsequenz für den Scope:** Eine Telegram/SMS-Vorschau ohne Versand-Fix wäre eine
**lügende UI** — sie zeigt eine Nachricht, die nie ankommt (vgl. #1269 „Speicher-Anzeige lügt").

### KB-4 · Es gibt keinen Compare-Telegram/SMS-Renderer — der muss neu gebaut werden

`src/output/renderers/comparison.py` hat nur `render_comparison_text:30` (= Plaintext-Teil der
Mail, nicht kanal-budgetiert) und `render_compare_email:145`. **Kein** `render_compare_telegram`,
**kein** `render_compare_sms`. Die Telegram/SMS-Pfade in `notification_service.py:684`/`:722`
gehören zu **amtlichen Warnungen** (`render_official_alert_telegram/sms`), nicht zum Briefing —
nicht 1:1 wiederverwendbar. Die Ticket-Annahme „Renderer existieren serverseitig" trifft nur auf
den Alarm-Pfad zu.

### KB-5 · Die vorhandenen Vorschau-Molecules sind auf einem abgeschafften Datenmodell gebaut

`molecules/CompareChatBubble.svelte` und `molecules/CompareSmsPreview.svelte` (aus #578,
1:1 vom Design-JSX) rendern **Rang (`r.rank`) und Punktzahl (`r.score`)** samt grüner
Gewinner-Hervorhebung. Score/Winner sind aber **PO-seitig abgeschafft**
(`issue_1110_compare_mail_v2.md:67`: „`render_compare_html()` liest `result.winner` **nicht
mehr**. Kein Score-Badge"). Sie einfach zu verdrahten würde #1110 (Neutralität) regressieren.
Score existiert nur noch **intern** zur Sortierung (`comparison_engine.py:185,229`).

### KB-6 · `presetChannels()` liest die falsche Quelle (eigenständiger Anzeige-Bug)

`subscriptionHelpers.ts:217` leitet die Kanal-Liste aus `display_config.channel_layouts`-Keys
ab statt aus `send_telegram`/`send_sms`. `channel_layouts` enthält nur **Metrik-Layouts pro
Kanal**, und `CompareEditor.svelte:605-606` legt `telegram`/`sms`-Keys **immer** an (auch leer)
→ der Kanal-Umschalter im Vorschau-Tab (`CompareTabs.svelte:601`) zeigt Telegram/SMS
vermutlich unabhängig vom echten Opt-in an. Erklärt, warum der Widerspruch überhaupt auffiel.

## Trip als Vorbild (Teilungs-Invariante)

| Aspekt | Trip | Orts-Vergleich |
|---|---|---|
| Preview-Service | `src/services/preview_service.py` — `render_email_preview`, `render_sms_preview`, `render_telegram_preview:282` (echter Trip, echtes Wetter, kein Versand) | **fehlt** — nur Validator-Stub |
| Preview-Endpoints | `/api/preview/{trip_id}/{email,sms,telegram}` (`api/routers/preview.py:28,54,99`; Go-Proxy `router.go:161-165`) | **fehlt** |
| Versand-Kanal-Fan-out | `NotificationService.send_trip_report` (`notification_service.py:211`) → Email `:211`, SMS `:256`, Telegram `:267`, je eigenes try/except (fail-soft) | **fehlt** — direkt `EmailOutput` |
| Kanal-Gate-Muster | Opt-in **UND** `can_send_*()` **UND** `sms_allowed(user_id)` (`trip_report_scheduler.py:698-701,918-921`) | nur im Alarm-Pfad (`compare_official_alert.py:198-206`) |

**Wichtige Einschränkung der Invariante:** Es gibt **keinen geteilten Vorschau-Baustein**.
`context: 'route'|'vergleich'` ist zwar etabliert (`shared/VersandTab.svelte:30,49`, `AlarmeTab`,
`layout-tab/LayoutTab`, `LTChannelPicker`, `corridor-editor/*`), aber **keiner davon ist
preview-bezogen**. Trip nutzt `preview/EmailIframe.svelte` + `preview/SmsPhoneFrame.svelte`
(nebeneinander, **kein** Kanal-Umschalter, **kein** Telegram im UI trotz vorhandenem Endpoint);
Compare nutzt `molecules/CompareChannelSwitch` + `CompareBriefingPreview`. Das ist genau die
Doppelung, die die PO-Vorgabe adressiert — hier ist die Teilung **noch zu bauen**, nicht nur
zu benutzen.

**Falle:** `trip-detail/ChannelPreviewBlock.svelte:34-92` hat zwar einen Email/Telegram/SMS-
Umschalter, ist aber ein **statischer Mock** im Metriken-Editor („Beispielwerte · kein
Live-Wetter", `:74`) — **nicht** die Briefing-Vorschau. Gleiches gilt für `ChannelFidelity*`.
Nicht verwechseln.

## Related Files

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/compare/CompareTabs.svelte:594-637, 1169-1258` | Vorschau-Tab: Stub-Fetch, Kanal-Umschalter, Platzhalter-Zweige, toter Mount |
| `frontend/src/lib/components/molecules/CompareBriefingPreview.svelte` | Rendert bedingungslos Missing-Box (KB-2) |
| `frontend/src/lib/components/molecules/ComparePreviewMissing.svelte:22` | Quelle der Copy „Vorschau-Daten nicht verfügbar." |
| `frontend/src/lib/components/molecules/CompareChatBubble.svelte`, `CompareSmsPreview.svelte` | Design-Molecules auf Score/Rang-Modell (KB-5) |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts:217` | `presetChannels()` — falsche Ableitungsquelle (KB-6) |
| `api/routers/validator.py:313-324` | Validator-Stub-Endpoint (KB-1) |
| `src/services/validator_render_service.py:147-173` | Stub-Ort „Vorschau-Ort" (KB-1) |
| `src/services/preview_service.py` (+ `api/routers/preview.py`) | **Vorbild** für einen echten Compare-Preview-Service |
| `src/services/scheduler_dispatch_service.py:245-338` | E-Mail-only Versandpfad (KB-3) |
| `src/output/renderers/comparison.py:30,145` | Vorhandene Compare-Renderer (kein Telegram/SMS, KB-4) |
| `src/services/notification_service.py:211-290` | Trip-Fan-out — Vorbild für Compare |
| `src/services/compare_official_alert.py:198-206` | Korrektes Kanal-Auflösungs-Muster im Compare-Kontext |
| `src/services/comparison_engine.py:185,229` | Score nur noch intern (Sortierung) |
| `internal/model/compare_preset.go:79-87` | `SendTelegram`/`SendSms` — Kanal-Opt-in |
| `claude-code-handoff/current/jsx/screen-compare-detail.jsx:330-391` | Design-Soll `CHub_PreviewTab` |

## Existing Patterns

- **Kanal-Gate doppelt:** Opt-in am Objekt **UND** globale Fähigkeit (`can_send_telegram()`),
  bei SMS zusätzlich Tier-Gate `sms_allowed(user_id)`.
- **Fan-out fail-soft:** je Kanal eigenes try/except — ein toter Kanal darf die anderen nicht reißen.
- **Preview = Render ohne Versand,** kein SMTP, Wetter über bestehende Pipeline (`preview_service.md`).
- **`context`-Prop** (`'route'|'vergleich'`) für geteilte Organismen.
- **Kanal-Spalten-Budget** aus **einer** Quelle: `CHANNEL_COL_BUDGET` (`metricsEditor.ts`).

## Dependencies

- **Upstream:** `ComparisonEngine.run()` (Wetterdaten), `Settings.can_send_*()`,
  `resolve_compare_render_options` (#1209), `sms_allowed()` (Tier-Gate).
- **Downstream:** Vorschau-Tab (Hub), Compare-Versand (Daily-Loop + Einzelversand),
  `email_spec_validator.py` (Marker `X-GZ-Mail-Type: compare`).

## Existing Specs

- `docs/specs/modules/fix_1256_s8b_preview_channel_switch.md` — direkter Vorgänger; hat den
  Umschalter repariert und Telegram/SMS **bewusst** auf Hinweis-Zweige gelegt („plus Hinweis
  solange keine dedizierte Telegram-Vorschau existiert", AC-2). #1270 ist die Einlösung.
- `docs/specs/modules/preview_service.md` — Trip-PreviewService (Vorbild-Vertrag inkl. Fehler-ACs).
- `docs/specs/modules/issue_464_compare_email_preview_validator.md` — Herkunft des Stub-Endpoints.
- `docs/specs/modules/issue_1110_compare_mail_v2.md:67` — Score/Winner abgeschafft (Neutralität).
- `docs/specs/modules/versand_tab_vergleich.md:377-384` — KL-4 (Alert-Kanalwahl E-Mail-only),
  **KL-6** (`send_email` gar nicht persistiert — vorbestehende Lücke!).
- `docs/specs/modules/issue_1229_monitor_hub.md`, `issue_514_compare_vorschau_tab.md` — Tab-Historie.

## Risks & Considerations

- **R1 · Scope-Explosion:** Ehrlich gelöst umfasst #1270 drei Schichten (Renderer → Preview-Service
  + Endpoints → Versand-Fan-out) plus Frontend. Weit über 250 LoC → **LoC-Override nötig,
  PO-Freigabe erforderlich** (kein Selbstbedienungs-Override). Scheiben-Schnitt in der Spec klären.
- **R2 · Renderer-Commit-Gate #811 — ENTWARNUNG (verifiziert in der Analyse):** Die Gate-Muster
  (`.claude/hooks/renderer_mail_gate.py:43-63`) sind `renderers/email/*.py`,
  `renderers/(trip_report|sms_trip|compact_summary).py`, `renderers/alert/*.py`,
  `channels/email.py`. **`src/output/renderers/comparison.py` matcht keins davon** → neue
  `render_compare_telegram`/`render_compare_sms` dort triggern das Gate **nicht**, solange
  `renderers/email/compare_html.py` unangetastet bleibt. Keine Test-Mail-Runde für S3 einplanen.
- **R3 · Kollision mit #1207** (Ein Versand-Orchestrator Trip+Compare) und **#1273** (Epic: EINE
  Fläche). Der Versand-Fan-out hier ist genau #1207-Terrain — Doppelarbeit/Konflikt-Risiko.
  In der Analyse entscheiden: minimal-invasiv im Compare-Pfad **oder** #1207 vorziehen.
- **R4 · Neutralitäts-Regress:** Telegram/SMS-Render darf **keinen** Score/Rang zeigen (KB-5, #1110).
- **R5 · `confidence_pct` ist keine wählbare Metrik** (PO final, #710) — im Narrow-Render nicht als
  Spalte einführen.
- **R6 · Wetter-Fetch pro Vorschau:** Ein echter Compare-Preview ruft `ComparisonEngine.run()`
  über alle Orte → teuer/langsam (Trip-Preview hat dasselbe Problem, `preview_service.md`
  Known Limitations). Ladezustand + Caching bedenken.
- **R7 · Multi-User-Isolation:** Ein neuer Preview-Endpoint ist nutzerbezogen → echte `user_id`
  aus dem Auth-Kontext, **nie** `"default"`; Pflicht-Test mit **zwei** Nutzern.
- **R8 · `empfaenger` ist reine E-Mail-Liste** (Go-Validierung `compare_preset.go:132-133`,
  400 ohne `@`). Telegram-Chat-ID/SMS-Nummer kommen aus globalen User-Settings — kein
  Preset-Feld. Kein Empfänger-Modell-Umbau nötig, aber Erwartung klären.
- **R9 · Ticket-Screenshot fehlt:** `docs/artifacts/audit-1256-prod/02-detail-vorschau-desktop.png`
  wurde **nie committet** (lebte nur im Worktree intake-1194) — nicht als Beleg verfügbar.
  Diagnose stützt sich auf Code + lokalen Render.

## Nebenbefunde (Triage → #1199, nicht Teil dieser Arbeit)

- `internal/router/router.go:164` — **Signal-Preview-Route lebt noch**, obwohl Signal app-weit
  entfernt ist (#610).
- `compare_alert.py:229` + `compare_radar_alert.py:115` hardkodieren `{"email"}`, während
  `compare_official_alert.py:198` direkt daneben korrekt auflöst — dieselbe Lücke, andere Services.
- `versand_tab_vergleich.md` KL-6: `send_email` wird gar nicht persistiert (Checkbox ohne Wirkung).
- Trip-Telegram-Preview-Endpoint existiert, wird vom Frontend aber nie aufgerufen (toter Endpoint).

---

# Analysis (Phase 2)

## Type

**Bug** (Label `bug`) mit erheblichem Feature-Anteil: Die im Ticket gemeldeten Symptome sind
echte Fehler, aber ihre Behebung erfordert drei fehlende Schichten (Renderer → Preview-Service
→ Versand-Fan-out). Ticket-Annahmen widerlegt (KB-1..KB-6).

## Architektur-Anker (entscheidet die offenen Fragen)

**ADR-0011** (`docs/adr/0011-alert-render-single-backend-renderer.md:26-36`) ist bindend:
> „Die Live-Vorschau im Frontend konsumiert die fertig gerenderten Kanäle über einen
> Backend-Endpunkt. Es wird **kein** zweiter Renderer in TypeScript gebaut."
> Folgepflicht: „Frontend rendert Alert-/Kanal-Inhalte nicht eigenständig nach, sondern
> zeigt Backend-Ergebnisse an."

Damit ist entschieden: `CompareChatBubble`/`CompareSmsPreview` dürfen **nicht** verdrahtet
werden wie sie sind — sie rendern clientseitig (`CompareSmsPreview.svelte:43-55` baut den
SMS-Text selbst; `CompareChatBubble.svelte:49-56` budgetiert Spalten selbst). Sie werden zu
**reinen Anzeige-Hüllen** (visuelle Chrome), die Backend-Payload darstellen — exakt wie
`preview/SmsPhoneFrame.svelte:24,59,64` es beim Trip tut (fetch → `token_line`/`char_count`
anzeigen, null Render-Logik).

## Entscheidung 1 — Schnitt gegen #1207: **minimal-invasiv, über den bereits geteilten NotificationService**

`NotificationService` ist **kein reiner Trip-Baustein**: neben `send_trip_report:211` existiert
bereits `send_multi_location_official_alert:596` — eine content-type-spezifische Methode auf
derselben geteilten Klasse, gebaut für den **Compare**-Kontext. Genau dieses Muster wird
fortgesetzt: neue Methode `NotificationService.send_compare_report(...)` mit
Kanal-Auflösung analog `compare_official_alert.py:198-206` und fail-soft try/except je Kanal
analog `send_trip_report:250-290`. **Kein** Ad-hoc-Fan-out in `scheduler_dispatch_service`.

**Verworfen — #1207 vorziehen:** #1207 konsolidiert ~1.800 LoC (`trip_report_scheduler.py` 1452
+ `scheduler_dispatch_service.py` 359) und empfiehlt im eigenen Body **2 Workflows**. Es an
einen Nutzer-Bugfix zu koppeln sprengt jedes Budget und erzwingt eine Strategy-Pattern-
Grundsatzentscheidung, die der PO für #1270 nicht angefragt hat. Epic #1204 sieht die
Backend-Konsolidierung zudem **nach** den Frontend-Scheiben vor. (#1203 ist zwar CLOSED,
#1207 also entblockt — aber Reihenfolge ≠ Dringlichkeit.)

**Verworfen — Versand raushalten:** Widerspricht PO-Entscheid „alles zusammen" und KB-3
(Vorschau ohne Versand = lügende UI, #1269-Muster).

**Konfliktminderung:** Änderungen strikt auf `notification_service.py` +
`scheduler_dispatch_service.py` begrenzen, **`trip_report_scheduler.py` niemals anfassen**;
Block markieren mit `# TODO(#1207): wird durch den Versand-Orchestrator generalisiert`.

## Entscheidung 2 — Vorschau: eigener `ComparePreviewService`, **eine** Router-Datei

Trip lädt einen `Trip` (Etappen/Waypoints); Compare lädt Preset + Orte-Liste +
`ComparisonEngine.run()`. Ein `context`-Parameter an `PreviewService` erzwingt durchgängig
`if context == 'vergleich': ... else: ...` — Verzweigung als Modul getarnt, keine echte Teilung.

**Gewählt:** `src/services/compare_preview_service.py` mit **denselben Methodennamen** wie
`PreviewService` (`render_email_preview`/`render_sms_preview`/`render_telegram_preview`) —
Konventions-Parität statt Klassen-Parität. Routen in **derselben** Datei `api/routers/preview.py`
(`/api/preview/compare/{preset_id}/{channel}`) — das ist die sinnvolle Teilungs-Ebene.

**Teilungs-Invariante — dokumentierte Ausnahme (CLAUDE.md verlangt sie explizit):**
`ComparePreviewService` ist eine neue Compare-Komponente mit Trip-Pendant (`PreviewService`).
Begründung: (1) unterschiedliche Kern-Datentypen, (2) es existiert heute **kein** geteilter
Preview-Baustein (Trip-Preview-UI hat nicht mal einen Kanal-Umschalter) — die Teilung wäre
Neubau, nicht Wiederverwendung, (3) echte Konvergenz kommt strukturell über Epic #1230/#1250
(gemeinsame `BriefingSubscription`-Entität); ein geteilter Preview-Service davor ist verfrüht.
**Eingelöst wird die Invariante stattdessen über geteilte Infrastruktur:**
`renderers/channel_layout.py::CHANNEL_LIMITS` (Kanal-Budget, #360), `resolve_compare_render_options`
(#1209, Metrik-Filter), `render_comparison_text`-Vertrag (Neutralität, #1110).

Der Validator-Stub-Endpoint (`/api/_validator/compare-email-preview`, #464) **bleibt
unverändert** — er gehört dem externen Validator. `CompareTabs.svelte` wird umgehängt.

## Scheiben-Plan (interne Reihenfolge in EINEM Workflow)

| # | Ziel | Dateien | LoC | Abh. | Allein nutzersichtbar? |
|---|---|---|---|---|---|
| **S1** | `presetChannels()` liest `send_telegram`/`send_sms` statt `channel_layouts`-Keys (KB-6) | `subscriptionHelpers.ts` | ~15 | — | Ja — Umschalter zeigt nur echte Opt-ins |
| **S2** | **Echte** E-Mail-Vorschau (KB-1/KB-2): `ComparePreviewService.render_email_preview`, Route, `CompareTabs` umgehängt, toter `CompareBriefingPreview`-Mount weg | `compare_preview_service.py` (CREATE), `preview.py`, `CompareTabs.svelte`, `CompareBriefingPreview.svelte` | ~180 | S1 (weich) | **Ja — löst die Kern-Beschwerde** |
| **S3** | `render_compare_telegram`/`render_compare_sms` — kein Score/Rang (KB-4/KB-5), Budget via `CHANNEL_LIMITS` | `renderers/comparison.py` + Tests | ~150-200 | — | Nein |
| **S4** | Telegram/SMS-Vorschau verdrahtet; Molecules → reine Anzeige-Hüllen (ADR-0011) | `compare_preview_service.py`, `preview.py`, `CompareTabs.svelte`, `CompareChatBubble.svelte`, `CompareSmsPreview.svelte` | ~180 | S3 | Ja |
| **S5** | Telegram/SMS-**Versand** (KB-3): `NotificationService.send_compare_report`, `send_one_compare_preset` umgehängt | `notification_service.py`, `scheduler_dispatch_service.py` + Tests | ~180-220 | S3 | Ja — Opt-in wirkt endlich |

**Summe: ~700-800 LoC Produktivcode** (+ Tests) → **LoC-Override zwingend, PO-Freigabe nötig.**

**Reihenfolge-Begründung:** S1 zuerst (trivial, entkoppelt Anzeige-Bug, den S2+S4 sonst
zweimal anfassen). S2 vor allem anderen — löst die wörtliche Ticket-Beschwerde bei geringstem
Risiko (kein neuer Renderer, kein Gate, kein Versand). S3 vor S4/S5 (reine Funktionen, früh
gegen Neutralität testbar). **S5 zuletzt** — höchstes Konfliktrisiko (#1207) und einziger
echter Versand-Seiteneffekt. Bricht der Workflow vorzeitig ab, sind S1-S4 ein in sich
konsistenter Stand (Vorschau korrekt für alle 3 Kanäle); nur der Versand-Fix wäre dann
bewusst zu vertagen (PO-Entscheidung, nicht stillschweigend).

## Scope Assessment

- **MODIFY:** `subscriptionHelpers.ts`, `CompareTabs.svelte` (nur Vorschau-Bereich ~594-637,
  ~1169-1258), `CompareBriefingPreview.svelte`, `CompareChatBubble.svelte`,
  `CompareSmsPreview.svelte`, `api/routers/preview.py`, `src/output/renderers/comparison.py`,
  `src/services/notification_service.py`, `src/services/scheduler_dispatch_service.py`
- **CREATE:** `src/services/compare_preview_service.py` + Tests (verhaltensbenannt, **keine**
  Issue-Nummern im Dateinamen — `test_naming_gate.py`)
- **Files:** ~10 + Tests · **LoC:** ~700-800 Source · **Risk: MEDIUM-HIGH**

## Zusätzliche Risiken (aus der Analyse)

- **Kanal-Wechsel darf nicht 3× Wetter fetchen (R6 konkretisiert):** `ComparisonEngine.run()`
  ist teuer. `ComparePreviewService` muss das Ergebnis je `preset_id`+`target_date` einmal
  halten und die drei Renderer daraufsetzen — sonst wird jeder Kanalwechsel spürbar langsam.
- **#1273-Rebase-Reibung:** `CompareTabs.svelte` wird auch vom Hub-Epic angefasst → Änderungen
  hier strikt auf den Vorschau-Bereich begrenzen.
- **KL-6 (`send_email` unpersistiert) NICHT mitreparieren** — wird in `send_one_compare_preset`
  sichtbar, ist aber eigenständige Altlast → Nebenbefund, kein Scope-Kriechen.
- **Neutralitäts-Test explizit:** Assert „kein `rank`/`score` im Telegram/SMS-Output" analog
  bestehender #1110-Tests.

## Open Questions (PO)

- [ ] **LoC-Override ~800-1000** freigeben? (Pflicht — kein Selbstbedienungs-Override.)
- [ ] S5 (Versand) im selben Workflow bestätigen, oder als bewusst getrennte Auslieferung
      nach S1-S4? (PO-Entscheid war „alles zusammen" — Analyse bestätigt Machbarkeit,
      benennt aber S5 als Konflikt-Terrain zu #1207.)
