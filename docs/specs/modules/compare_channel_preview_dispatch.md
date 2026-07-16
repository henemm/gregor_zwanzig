---
entity_id: compare_channel_preview_dispatch
type: module
created: 2026-07-16
updated: 2026-07-16
status: draft
version: "1.0"
workflow: fix-1270-compare-channel-preview
tags: [backend, frontend, preview, compare, dispatch, issue-1270]
---

# Compare Channel Preview + Dispatch (Issue #1270)

## Approval

- [x] Approved — PO-Freigabe („go") am 2026-07-16, inkl. LoC-Override auf 1000
  und Scheiben S1-S5 in einem Workflow; Versand-Absicherung über den normalen
  Staging-Weg.

## Purpose

Der Vorschau-Tab im Orts-Vergleich-Hub zeigt heute entweder eine Fake-Vorschau
(hartcodierter Stub-Ort statt der echten Orte des Nutzers) oder direkt den
Hinweis „Vorschau-Daten nicht verfügbar." — für Telegram/SMS gibt es gar keine
echte Vorschau. Zusätzlich werden Telegram/SMS zwar als Versandkanal für das
Vergleichs-Briefing angeboten und gespeichert, beim tatsächlichen Versand aber
komplett ignoriert (E-Mail-only). Dieses Modul schließt beide Lücken: eine
echte, kanal-korrekte Vorschau (E-Mail/Telegram/SMS) auf Basis der echten
Orte des Nutzers, und einen tatsächlichen Telegram/SMS-Versand für das
Vergleichs-Briefing, der die gespeicherten Kanal-Einstellungen respektiert.

## Source

- **Python-Core (neu):** `src/services/compare_preview_service.py` — `class ComparePreviewService`
- **Python-Core (neu Methoden):** `src/output/renderers/comparison.py` — `render_compare_telegram`, `render_compare_sms`
- **Python-Core (erweitert):** `api/routers/preview.py` — **eine** neue Route `POST /api/preview/compare/{preset_id}`, die **alle** Kanäle fertig gerendert in einer Antwort liefert (ADR-0011-Muster, Vorbild `alert-preview`)
- **Python-Core (erweitert):** `src/services/notification_service.py` — `NotificationService.send_compare_report(...)`
- **Python-Core (erweitert):** `src/services/scheduler_dispatch_service.py` — `send_one_compare_preset` auf den neuen Fan-out umgehängt
- **Go-API (erweitert):** `internal/router/router.go` — Proxy-Routen für Compare-Preview (Muster `router.go:161-165`)
- **Frontend (erweitert):** `frontend/src/lib/components/compare/CompareTabs.svelte` (nur Vorschau-Bereich ~594-637, ~1169-1258), `frontend/src/lib/components/molecules/CompareBriefingPreview.svelte`, `CompareChatBubble.svelte`, `CompareSmsPreview.svelte`
- **Frontend (Bugfix):** `frontend/src/lib/components/compare/subscriptionHelpers.ts` — `presetChannels()`

## Estimated Scope

- **LoC:** ~700-800 Produktivcode (+ Tests) — **LoC-Override auf 1000 durch PO freigegeben** (siehe `docs/context/fix-1270-compare-channel-preview.md`, Open Questions)
- **Files:** ~10 Produktivdateien + zugehörige Testdateien
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src.services.preview_service.PreviewService` | bestehend | Vertrags-Vorbild (Methodennamen `render_email_preview`/`render_sms_preview`/`render_telegram_preview`, Fehler-Semantik) |
| `src.services.comparison_engine.ComparisonEngine.run()` | bestehend | Liefert `ComparisonResult` für ein Preset (Orte + Zeitfenster + Zieldatum) |
| `src.services.report_config_resolver.resolve_compare_render_options` | bestehend (#1209) | Einzige Quelle für aktivierte Metriken / Render-Optionen — keine eigene Metrik-Liste |
| `src.output.renderers.channel_layout.CHANNEL_LIMITS` | bestehend (#360) | Kanal-Budget (Zeichen-/Zeilen-Limits) für Telegram/SMS |
| `src.output.renderers.comparison.render_comparison_text` | bestehend (#1110) | Neutralitäts-Vertrag: kein Score/Rang — Vorbild für die neuen Kanal-Renderer |
| `src.services.notification_service.NotificationService` | bestehend | Ziel-Klasse für `send_compare_report`; Fan-out-Vorbild `send_trip_report:211-290` |
| `src.services.compare_official_alert._effective_channels` | bestehend | Kanal-Auflösungs-Muster (Opt-in UND `can_send_*()` UND `sms_allowed()`) |
| `internal/handler/preview_proxy.go::PreviewProxyHandler` | bestehend | Proxy-Vorbild für die neue Compare-Preview-Route |
| `docs/adr/0011-alert-render-single-backend-renderer.md` | bindend | Frontend rendert nicht nach — Backend liefert fertige Kanal-Payloads |
| `api/routers/validator.py::alert_preview` + `src/services/validator_render_service.py:134-144` | bestehend | **Struktur-Vorbild:** EIN Endpoint liefert `{subject, email_html, email_plain, telegram, sms}` in EINER Antwort |
| `frontend/src/lib/components/alerts-tab/AlertPreviewCard.svelte:34-44` | bestehend | **Frontend-Vorbild:** ein `api.post`, alle Kanäle im Ergebnis, Kanalwechsel rein clientseitig ohne Nachladen |

## Implementation Details

**Scheiben-Reihenfolge (S1-S5, ein Workflow, PO-Freigabe „alles zusammen"):**

- **S1 — `presetChannels()`-Bugfix (KB-6):** `subscriptionHelpers.ts:217` liest die
  Kanal-Liste aus `display_config.channel_layouts`-Keys (die immer alle Kanäle
  enthalten, auch leere) statt aus den Opt-in-Feldern `send_telegram`/`send_sms`
  (+ `send_email` implizit immer an). Fix: Ableitung aus den Opt-in-Feldern,
  analog der bestehenden `channelNamesLabel`-Quelle.

- **S2 — Echte E-Mail-Vorschau (KB-1/KB-2):** `ComparePreviewService` lädt das
  Preset + die echten Orte des Nutzers (nicht den Stub-Ort aus
  `validator_render_service.py:147`), ruft `ComparisonEngine.run()` **einmal**
  und rendert über den bestehenden `render_compare_email`/`compare_html`-Pfad.
  Neue Route `POST /api/preview/compare/{preset_id}` (s. „Endpoint-Form" unten).
  `CompareTabs.svelte` wird von `/api/_validator/compare-email-preview` auf diese
  neue Route umgehängt; der tote `CompareBriefingPreview`-Mount ohne
  `profile`/`data` (KB-2) wird entfernt bzw. korrekt mit den Vorschau-Daten
  befüllt. Der Validator-Stub-Endpoint bleibt **unverändert** bestehen (gehört
  dem externen Validator, #464).

- **S3 — Neue Kanal-Renderer (KB-4/KB-5):** `render_compare_telegram` und
  `render_compare_sms` in `src/output/renderers/comparison.py`, gebaut auf dem
  Neutralitäts-Vertrag von `render_comparison_text` (kein Score, kein Rang,
  keine Gewinner-Hervorhebung — Score bleibt ausschließlich interne
  Sortiergröße in `comparison_engine.py`). Budget über `CHANNEL_LIMITS`
  (`channel_layout.py`), Metrik-Filter ausschließlich über
  `resolve_compare_render_options` (keine eigene Metrik-Liste, insbesondere
  **kein** `confidence_pct`, #710/ADR-0005).

- **S4 — Telegram/SMS-Vorschau verdrahtet (ADR-0011):** `ComparePreviewService`
  bekommt `render_telegram_preview`/`render_sms_preview` (gleiche Signatur-Form
  wie `PreviewService`); beide werden von derselben S2-Route mitbedient (kein
  eigener Endpoint je Kanal — s. „Endpoint-Form"). `CompareChatBubble.svelte` und
  `CompareSmsPreview.svelte` verlieren ihre eigene Render-Logik
  (`CompareSmsPreview.svelte:43-55` baut heute den SMS-Text selbst,
  `CompareChatBubble.svelte:49-56` budgetiert Spalten selbst) und werden zu
  reinen Anzeige-Hüllen für die Backend-Payload (Vorbild
  `preview/SmsPhoneFrame.svelte:24,59,64`) — visuelle Chrome (Farben,
  Bubble-Optik) bleibt erhalten.

- **S5 — Telegram/SMS-Versand (KB-3):** Neue Methode
  `NotificationService.send_compare_report(...)` mit Kanal-Auflösung analog
  `compare_official_alert.py:198-206` (Opt-in **und** `can_send_telegram()`/
  `can_send_sms()` **und** `sms_allowed(user_id)`) und fail-soft try/except je
  Kanal analog `send_trip_report:250-290` (ein toter Kanal reißt die anderen
  nicht mit). `send_one_compare_preset`
  (`scheduler_dispatch_service.py:245-338`) wird auf diese Methode
  umgehängt statt direkt `EmailOutput` zu rufen. Änderungen bleiben strikt auf
  `notification_service.py` und `scheduler_dispatch_service.py` begrenzt —
  **`trip_report_scheduler.py` wird nicht angefasst**. Der neue Code-Block
  trägt den Marker-Kommentar `# TODO(#1207): wird durch den
  Versand-Orchestrator generalisiert`.

**Endpoint-Form: EIN Abruf, alle Kanäle (ADR-0011-Muster, KEIN Cache nötig).**

`POST /api/preview/compare/{preset_id}` liefert in **einer** Antwort alle Kanäle
fertig gerendert:

```json
{ "subject": "...", "email_html": "...", "telegram": "...", "sms": "...", "sms_char_count": 137 }
```

Begründung (Korrektur gegenüber dem ersten Entwurf, s. Changelog): Der Entwurf
sah drei Routen `/{channel}` vor und wollte den Mehrfach-Fetch über einen Cache
verhindern — das ist widersprüchlich, weil jeder Kanalwechsel ein **eigener
HTTP-Request** ist und ein request-lokaler Cache dort nicht greift; ein
Cross-Request-Cache mit TTL wäre Zustand ohne Not. Die Drei-Routen-Form kopierte
das **Trip**-Muster (`api/routers/preview.py`, #140/#189), das **älter ist als
ADR-0011** (2026-06-29). ADR-0011 formuliert dagegen wörtlich: „Die Live-Vorschau
im Frontend konsumiert die fertig gerenderten **Kanäle** (Plural) über **einen**
Backend-Endpunkt (Erweiterung des bestehenden `alert-preview`-Musters)".

Genau so arbeitet das Bestands-Vorbild bereits: `validator_render_service.py:134-144`
rendert `subject`/`email_html`/`email_plain`/`telegram`/`sms` in einem Rutsch, und
`AlertPreviewCard.svelte:34-44` holt sie mit **einem** `api.post` und schaltet die
Kanäle danach rein clientseitig um — ohne Nachladen.

Damit ist die Fetch-Sparsamkeit (AC-7) **strukturell** erfüllt statt durch
Cache-Mechanik: ein Request → ein `ComparisonEngine.run()` → drei Renderer auf
demselben `ComparisonResult`. Der Kanalwechsel im Vorschau-Tab löst **gar keinen**
Request mehr aus. Kein Cache, kein TTL, kein Invalidierungs-Problem.

## Expected Behavior

- **Input:** `preset_id` (aus dem Auth-Kontext des Nutzers aufgelöst),
  `channel` (`email`|`telegram`|`sms`), optional `target_date`.
- **Output:** Kanal-korrekte Vorschau-Payload — E-Mail: HTML-String; Telegram:
  `(subject, body, bubbles)`; SMS: `(subject, token_line)` bzw. äquivalente
  JSON-Struktur mit `char_count`. Beim Versand: tatsächlich zugestellte
  Telegram-/SMS-Nachricht, wenn der Nutzer die Kanäle im Preset aktiviert hat
  und global sendefähig ist.
- **Side effects:** Vorschau — keine (kein Versand, kein Logbuch-Eintrag, nur
  Wetter-Fetch über die bestehende `ComparisonEngine`-Pipeline). Versand
  (S5) — tatsächliche Telegram-/SMS-Zustellung über die bestehenden
  Output-Kanäle, analog Trip-Briefing.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer öffnet den Vorschau-Tab eines Orts-Vergleichs-Presets
  mit mindestens zwei konfigurierten Orten / When der E-Mail-Kanal aktiv ist /
  Then zeigt die Vorschau die tatsächlichen Ortsnamen und echten Wetterwerte
  des Presets — nicht mehr „Vorschau-Ort" mit lauter „—"-Werten.
  - Test: Kern-Test mit echter, aufgezeichneter Wetter-Fixture und einem
    Preset mit ≥2 realen Orten — Assert, dass die gerenderte E-Mail-Vorschau
    die konfigurierten Ortsnamen enthält und `stub_location`/„Vorschau-Ort"
    NICHT vorkommt.

- **AC-2:** Given ein Preset mit aktiviertem Telegram-Opt-in / When der Nutzer
  im Vorschau-Tab auf den Telegram-Kanal wechselt / Then zeigt die
  Render-Fläche eine echte, aus den Presets-Orten gerenderte Telegram-Vorschau
  (keine Platzhalter-Copy, kein „—") — analog für SMS.
  - Test: Kern-Test ruft `ComparePreviewService.render_telegram_preview` bzw.
    `render_sms_preview` mit einem echten Preset auf und prüft, dass die
    zurückgegebene Nachricht Orts- und Wetterinhalte des Presets enthält.

- **AC-3:** Given ein Preset-Vergleich mit mehreren Orten / When die
  Telegram- oder SMS-Vorschau bzw. der tatsächliche Telegram-/SMS-Versand
  gerendert wird / Then erscheint darin **kein** Rang und **keine** Punktzahl
  je Ort (weder als Zahl noch als „Gewinner"-Hervorhebung) — die Reihenfolge
  bleibt intern, ist aber nicht als Ranking sichtbar.
  - Test: Kern-Test prüft am gerenderten Telegram-/SMS-Text, dass keine
    Score-/Rang-Marker (z. B. Platzierungsziffern, Gewinner-Badge-Text)
    vorkommen — Fixture mit mindestens drei Orten unterschiedlicher
    Score-Reihenfolge, damit ein Regress sichtbar würde.

- **AC-4:** Given ein Nutzer hat für sein Vergleichs-Preset Telegram und/oder
  SMS als Versandkanal aktiviert (und ist dafür global freigeschaltet) / When
  der planmäßige oder manuelle Versand für dieses Preset ausgelöst wird / Then
  erhält er die Vergleichs-Nachricht tatsächlich über diese Kanäle — nicht nur
  per E-Mail wie bisher.
  - Test: Kern-Test ruft `send_one_compare_preset` mit einem Preset auf, das
    `send_telegram=True`/`send_sms=True` gesetzt hat, und nutzt die im Bestand
    etablierte **Sink-Naht** (`mail_sink`/`sms_sink`/`telegram_sink`, wie
    `send_multi_location_official_alert:596-607` sie bereits anbietet) als
    deterministischen Transport-Ersatz — kein Netz, kein Mock-Theater:
    Assert, dass in `sms_sink` und `telegram_sink` je eine Nachricht mit dem
    Vergleichs-Inhalt landet. `send_compare_report` MUSS dieselben
    Sink-Parameter anbieten.

- **AC-5:** Given ein Preset ohne Telegram-/SMS-Opt-in oder ein Nutzer ohne
  globale Telegram-/SMS-Sendefähigkeit / When der Versand ausgelöst wird /
  Then bleibt der Versand für diesen Kanal aus, während der E-Mail-Versand
  unverändert weiterläuft (ein nicht sendefähiger Kanal darf die anderen nicht
  verhindern).
  - Test: Kern-Test mit einem Preset, das `send_telegram=True` aber
    `can_send_telegram()==False` liefert — Assert: E-Mail wird gesendet,
    Telegram-Versandversuch bleibt aus, kein Fehler/Abbruch für die E-Mail.

- **AC-6:** Given ein Preset gehört Nutzer A / When Nutzer B (angemeldet mit
  eigener Session) die neue Compare-Preview-Route mit der Preset-ID von
  Nutzer A aufruft / Then bekommt Nutzer B keinen Zugriff auf die Vorschau
  von Nutzer A (404 oder gleichwertige Ablehnung) — Multi-User-Isolation ist
  gewahrt.
  - Test: Kern-Test mit zwei unterschiedlichen `user_id`-Kontexten
    (echte Auflösung über den Preset-Loader, kein `"default"`-Fallback) —
    Preset von User A ist unter User-B-`user_id` nicht auflösbar.

- **AC-7:** Given der Vorschau-Tab eines Presets ist geladen / When der Nutzer
  zwischen den Kanälen E-Mail → Telegram → SMS → E-Mail umschaltet / Then
  erscheint der jeweilige Kanal ohne erneute Ladezeit (die Wetter-Berechnung
  läuft für dasselbe Preset+Zieldatum genau einmal, nicht je Kanal erneut).
  - Test: Kern-Test instrumentiert `ComparisonEngine.run()` (Aufruf-Zähler,
    kein Verhaltens-Mock): EIN Aufruf der Preview-Route liefert alle drei
    Kanäle — Assert: genau ein `run()`-Aufruf, und die Antwort enthält
    `email_html`, `telegram` UND `sms` gleichzeitig gefüllt.
  - Test (Live-E2E): Kanalwechsel im Vorschau-Tab löst **keinen** weiteren
    Netzwerk-Request aus (Playwright-Request-Zähler auf die Preview-Route).

- **AC-8:** Given der Kanal-Umschalter im Vorschau-Tab wird für ein Preset mit
  konfiguriertem Telegram-Kanal angezeigt / When das Preset tatsächlich weder
  Telegram noch SMS aktiviert hat / Then zeigt der Umschalter nur die
  tatsächlich konfigurierten Kanäle als aktiv wählbar an — nicht länger alle
  Kanäle allein deshalb, weil `channel_layouts` für sie einen (leeren)
  Eintrag besitzt.
  - Test: Kern-Test (Source-/Verhaltens-Test) für `presetChannels()` mit einem
    Preset, das `send_telegram=false`/`send_sms=false` aber gefüllte
    `channel_layouts`-Keys für alle drei Kanäle hat — Assert: Rückgabe enthält
    nur `email`.

## Known Limitations

- **KL-1 (bewusst nicht behoben):** `send_email` wird auf Preset-Ebene gar
  nicht persistiert (`versand_tab_vergleich.md` KL-6) — vorbestehende Altlast,
  nicht Teil dieser Arbeit (Nebenbefund-Triage, #1199).
- **KL-2 (bewusst nicht behoben):** `compare_alert.py:229` und
  `compare_radar_alert.py:115` hardcodieren weiterhin `{"email"}` für den
  Alarm-Pfad (nicht den Briefing-Pfad, um den es hier geht) — eigenständiger
  Nebenbefund.
- **KL-3:** Jeder Aufruf der Vorschau-Route löst einen Wetter-Fetch über die
  bestehende `ComparisonEngine`-Pipeline aus (kein persistenter Cache über
  Requests hinweg) — analog `preview_service.md` Known Limitations. Innerhalb
  eines Aufrufs wird **einmal** gerechnet und für alle drei Kanäle
  wiederverwendet; ein erneutes Öffnen des Vorschau-Tabs rechnet neu. Bewusst
  akzeptiert: Cache-Invalidierung wäre Zustand ohne belegten Bedarf.
- **KL-4:** `empfaenger` bleibt eine reine E-Mail-Liste (Go-Validierung
  `compare_preset.go:132-133`); Telegram-Chat-ID/SMS-Nummer kommen weiterhin
  aus den globalen User-Settings, kein Preset-Feld-Umbau in diesem Workflow.
- **KL-5:** `internal/router/router.go:164` — die tote Signal-Preview-Route
  (Signal app-weit entfernt, #610) wird hier nicht aufgeräumt (Nebenbefund).

## Edge Cases

- Preset mit **null** Orten (`location_ids == []`): Vorschau liefert einen
  aussagekräftigen Hinweis/Fehler, keinen stillen Leerzustand. **Kein
  Mindest-Ort-Zwang darüber hinaus** — ein Vergleich mit genau EINEM Ort ist
  im Bestand ausdrücklich zulässig (`subscriptionHelpers.ts:130` formuliert
  „1 Ort" als gültigen Zustand; das Bestands-Gate ist überall
  `location_ids.length === 0`, z. B. `CompareTabs.svelte:612,1171`) und muss
  eine normale Vorschau bekommen.
- Wetter-Provider liefert keine Daten (Rate-Limit etc.): Vorschau wirft einen
  erwartbaren Fehler statt einer stillen leeren Vorschau (analog
  `preview_service.md` AC-4).
- Preset mit Telegram-Opt-in, aber Nutzer global nicht Telegram-fähig
  (`can_send_telegram()==False`): Vorschau-Kanal zeigt einen Hinweis
  „Kanal nicht konfiguriert"/nicht verfügbar statt eines leeren oder
  irreführenden Renders.
- Preset mit ungültiger/gelöschter Orts-Referenz (`location_ids`, die keinem
  geladenen Ort mehr entsprechen): Vorschau/Versand behandeln das wie den
  bestehenden Fehlerfall in `send_one_compare_preset` („Orte nicht
  aufloesbar"), kein Absturz.

## Out of Scope

- KL-6 aus `versand_tab_vergleich.md` (`send_email` unpersistiert) — bewusst
  nicht mitrepariert (Analyse-Entscheidung, Nebenbefund #1199).
- Konsolidierung von Trip- und Compare-Versand-Fan-out unter einem
  gemeinsamen Orchestrator (#1207) — dieser Workflow bleibt minimal-invasiv
  im Compare-Pfad; `trip_report_scheduler.py` wird nicht angefasst.
- Ein geteilter `PreviewService` für Trip UND Compare — dokumentierte
  Ausnahme von der Teilungs-Invariante (siehe Architektur-Entscheidung unten).
- Aufräumen der toten Signal-Preview-Route (`router.go:164`) und der
  hartcodierten `{"email"}`-Sets in `compare_alert.py`/`compare_radar_alert.py`
  (Nebenbefunde, #1199).
- Umbau des `empfaenger`-Feldmodells auf Telegram-Chat-ID/SMS-Nummer je
  Preset.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0011 (bindend), ADR-0003 (Multi-User-Isolation), ADR-0005
  (`confidence_pct` nicht wählbar) — keine neue ADR nötig.
- **Rationale:** ADR-0011 entscheidet bereits verbindlich, dass Kanal-Inhalte
  ausschließlich im Backend gerendert und im Frontend nur angezeigt werden
  („kein zweiter Renderer in TypeScript") — dieser Workflow wendet das
  Muster (bereits etabliert für Alerts) 1:1 auf den Compare-Briefing-Pfad an,
  statt es neu zu verhandeln. ADR-0003 (Mandantenfähigkeit) verlangt echte
  `user_id`-Auflösung ohne `"default"`-Fallback für den neuen Endpoint;
  ADR-0005 verbietet `confidence_pct` als wählbare Metrik — beide werden hier
  nur angewendet, nicht neu entschieden.
- **Dokumentierte Ausnahme von der Trip/Compare-Teilungs-Invariante
  (CLAUDE.md verlangt diese Begründung explizit):** `ComparePreviewService`
  ist eine neue Compare-Komponente mit einem Trip-Pendant (`PreviewService`)
  und damit auf den ersten Blick ein Verstoß gegen die Teilungs-Invariante.
  Begründung, warum hier keine gemeinsame Basisklasse gebaut wird: (1) Trip
  und Compare laden fundamental unterschiedliche Kern-Datentypen (Trip mit
  Etappen/Wegpunkten vs. Preset mit Orte-Liste + `ComparisonEngine.run()`)
  — ein `context`-Parameter würde nur `if context == 'vergleich'`-Verzweigung
  als Modul tarnen, keine echte Teilung; (2) es existiert heute **kein**
  geteilter Preview-Baustein, auf den aufgesetzt werden könnte — selbst die
  Trip-Preview-UI hat keinen Kanal-Umschalter; die Teilung wäre also
  Neubau, nicht Wiederverwendung; (3) echte strukturelle Konvergenz kommt
  über Epic #1230/#1250 (gemeinsame `BriefingSubscription`-Entität) — ein
  geteilter Preview-Service davor wäre verfrüht und würde bei der späteren
  Konvergenz wieder aufgebrochen. Die Teilungs-Invariante wird stattdessen
  über geteilte **Infrastruktur** eingelöst: `CHANNEL_LIMITS`
  (Kanal-Budget), `resolve_compare_render_options` (Metrik-Filter),
  `render_comparison_text`-Neutralitätsvertrag — sowie Konventions-Parität
  (identische Methodennamen `render_email_preview`/`render_sms_preview`/
  `render_telegram_preview`) statt Klassen-Parität.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1 (S1): GIVEN ein Preset mit `send_telegram=false`/`send_sms=false`
  aber gefüllten `channel_layouts`-Keys für alle drei Kanäle WHEN
  `presetChannels()` aufgerufen wird THEN enthält das Ergebnis nur `email`.
- [ ] Test 2 (S2): GIVEN ein Preset mit ≥2 echten Orten und einer
  aufgezeichneten Wetter-Fixture WHEN `render_email_preview` läuft THEN
  enthält das HTML die echten Ortsnamen und keinen Stub-Ort.
- [ ] Test 3 (S3): GIVEN ein `ComparisonResult` mit ≥3 Orten unterschiedlicher
  Score-Reihenfolge WHEN `render_compare_telegram`/`render_compare_sms`
  gerendert wird THEN enthält der Output keinerlei Rang-/Score-Marker.
- [ ] Test 4 (S4): GIVEN ein Preset mit aktivem Telegram-Opt-in WHEN
  `render_telegram_preview` aufgerufen wird THEN liefert es einen aus den
  echten Orten gerenderten Text (kein Platzhalter).
- [ ] Test 5 (S5): GIVEN ein Preset mit `send_telegram=True`,
  `send_sms=True` und globaler Sendefähigkeit WHEN `send_one_compare_preset`
  läuft THEN löst `NotificationService.send_compare_report` Versandaufrufe
  für E-Mail, Telegram UND SMS aus.
- [ ] Test 6 (S5): GIVEN ein Preset mit `send_telegram=True`, aber
  `can_send_telegram()==False` WHEN der Versand läuft THEN bleibt der
  E-Mail-Versand unbeeinflusst, Telegram wird nicht versucht.
- [ ] Test 7 (Multi-User, AC-6): GIVEN ein Preset gehört User A WHEN die
  Compare-Preview-Route mit User-B-Kontext aufgerufen wird THEN ist das
  Preset nicht auflösbar (404/Ablehnung statt fremder Daten).
- [ ] Test 8 (Fetch-Sparsamkeit, AC-7): GIVEN EIN Aufruf der Preview-Route für
  ein Preset WHEN `ComparisonEngine.run()` instrumentiert wird THEN wird es
  genau einmal aufgerufen UND die Antwort enthält `email_html`, `telegram` und
  `sms` gleichzeitig gefüllt (Kanalwechsel im UI braucht keinen neuen Request).
- [ ] Test 9 (Ein-Ort-Vergleich, Edge Case): GIVEN ein Preset mit genau EINEM
  Ort WHEN die Vorschau angefordert wird THEN liefert sie eine normale
  Vorschau (kein Fehler) — schützt gegen einen fälschlich eingebauten
  Mindest-Ort-Zwang.

### Live-E2E (nur `/e2e-verify` bzw. Deploy)

- [ ] Playwright gegen Staging: Kanalwechsel im Vorschau-Tab (E-Mail →
  Telegram → SMS) zeigt für jeden Kanal echte, unterscheidbare Inhalte statt
  Platzhalter-Copy.
- [ ] Test-Mail/Test-Versand über Staging-Postfach (`gregor-test@henemm.com`)
  bzw. Staging-Telegram-Bot: ein Preset mit aktiviertem Telegram-Opt-in
  erhält beim planmäßigen Versand tatsächlich eine Telegram-Nachricht.

### Hinweis zu Gates

Renderer-Mail-Gate #811 greift für `src/output/renderers/comparison.py`
**nicht** (verifiziert gegen `.claude/hooks/renderer_mail_gate.py:43-63`),
solange `renderers/email/compare_html.py` unangetastet bleibt — keine
zusätzliche Test-Mail-Runde für S3 nötig.

## Changelog

- 2026-07-16 (vor Freigabe, Tech-Lead-Review des Entwurfs): **Zwei Fakten-Fehler
  im Entwurf korrigiert.**
  1. **Endpoint-Form korrigiert (Widerspruch aufgelöst):** Der Entwurf sah drei
     Routen `/api/preview/compare/{preset_id}/{channel}` plus einen Cache gegen
     Mehrfach-Fetch vor — in sich widersprüchlich, da jeder Kanalwechsel ein
     eigener HTTP-Request ist und ein request-lokaler Cache dort nicht greift.
     Ursache: Der Entwurf kopierte das Trip-Muster (`preview.py`, #140/#189),
     das älter ist als ADR-0011. Jetzt: **eine** Route `POST
     /api/preview/compare/{preset_id}`, alle Kanäle in einer Antwort — wörtlich
     ADR-0011 („die fertig gerenderten Kanäle über einen Backend-Endpunkt,
     Erweiterung des `alert-preview`-Musters"), belegt durch das Bestands-Vorbild
     `validator_render_service.py:134-144` + `AlertPreviewCard.svelte:34-44`.
     AC-7 ist damit strukturell erfüllt; KL-3 entschärft (kein Cache/TTL).
  2. **Edge Case „weniger als zwei Orte" war falsch:** Ein Vergleich mit genau
     einem Ort ist im Bestand zulässig (`subscriptionHelpers.ts:130`; Gates
     prüfen überall auf `length === 0`, z. B. `CompareTabs.svelte:612,1171`).
     Korrigiert auf „null Orte"; Test 9 als Regressionsschutz gegen einen
     fälschlich eingebauten Mindest-Ort-Zwang ergänzt.
  - Zusätzlich präzisiert: Sink-Naht (`mail_sink`/`sms_sink`/`telegram_sink`,
    Vorbild `send_multi_location_official_alert:596-607`) als deterministischer
    Test-Ersatz für den Versandnachweis (AC-4/Test 5-6) — statt unscharfem
    „aufgezeichneter Transport-Stand".
- 2026-07-16: Initial spec created (Issue #1270, Analyse-Phase
  `fix-1270-compare-channel-preview` übernommen: KB-1..KB-6, Entscheidung 1+2,
  Scheiben-Plan S1-S5)
