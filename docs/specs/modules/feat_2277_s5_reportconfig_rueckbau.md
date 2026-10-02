---
entity_id: feat_2277_s5_reportconfig_rueckbau
type: feature
created: 2026-10-02
updated: 2026-10-02
status: draft
version: "1.0"
tags: [trip-new, trip-detail, mail-inhalt, shared, refactoring, rueckbau]
---

# Mail-Inhalt-Karte als geteilter Baustein, Rückbau von `EditReportConfigSection` (Issue #2277 Scheibe S5)

## Approval

- [ ] Approved

## Purpose

Letzte Scheibe von #2277. Ticket-AC-5 verlangt, dass es keinen produktiven Importeur von
`EditReportConfigSection`, `reportConfigWrite` und `BriefingsTab` mehr gibt.

**Befund (nachgemessen):** `edit/EditReportConfigSection.svelte` (574 Zeilen) ist **nicht tot**. Seit
S1–S4 und #1738 wird sie nur noch im **Mail-Inhalt-Modus** gemountet (`showChannels=false`,
`showSchedule=false`). Sie ist die **einzige** Implementierung der Karte „E-Mail-Inhalt"
(`data-testid="report-mail-content"`): Format-Umschalter Ausführlich/Kompakt plus drei Schalter
(Ausblick, Etappen-Kennzahlen, Vortag-Vergleich). Reines Löschen würde dieses Feature entfernen. Ihre
Kanal- und Zeitplan-Zweige sind in allen Produktivpfaden tot; `VersandTab` besitzt Kanäle und Zeitplan.

S5 ist daher ein **Umzug mit Rückbau**, kein Löschen:

- Die Karte zieht **verhaltensgleich** in einen neuen geteilten Baustein `shared/MailInhaltCard.svelte`.
- Die drei Mounts (Hub `WeatherMetricsTab`, `TripNewEditor` Desktop und Mobil) hängen auf den Baustein um.
- `EditReportConfigSection.svelte`, `reportConfigWrite.ts` und der **tote** `BriefingsTab` samt totem
  Import in `TripTabs.svelte` werden gelöscht.

Für den Nutzer ändert sich nichts Sichtbares. Die Karte sieht gleich aus, schreibt dieselben Felder in
`report_config` und löst im Hub dieselbe Speicher-Logik aus.

## Source

- **Frontend (Pfade relativ zu `frontend/src/lib/components/`):**
  `shared/MailInhaltCard.svelte` (CREATE),
  `shared/mailInhaltKonstanten.ts` (CREATE, nur `DEFAULT_DAILY_SUMMARY_METRICS` und
  `CONTENT_MODULE_DESCRIPTIONS`, aus `reportConfigWrite.ts` übernommen),
  `shared/WeatherMetricsTab.svelte` (MODIFY, Mount ca. Z. 1986 und Kommentare),
  `trip-new/TripNewEditor.svelte` (MODIFY, Import und 2 Mounts, Kommentare),
  `trip-detail/TripTabs.svelte` (MODIFY, toter Import entfällt),
  `edit/EditReportConfigSection.svelte` (DELETE), `edit/reportConfigWrite.ts` (DELETE),
  `briefings-tab/BriefingsTab.svelte` (DELETE)
- **Identifier:** `MailInhaltCard`, `report-mail-content`, `report-config-touch-scope`,
  `baueReportConfigPayload`, `ladeReportZustand`.

> **Schicht-Hinweis:** ausschließlich **Frontend**. Kein Go-API-, kein Python-Core-Code, kein
> Schema-Eingriff, kein Mail-Renderer. Der Datenvertrag von `report_config` bleibt unverändert; die
> Spec berührt nur, **wer** welche Felder schreibt.

## Entscheidungen

1. **Umzug statt Löschung (Tech-Lead-Entscheidung).** Die Mail-Inhalt-Karte ist ein Produktmerkmal ohne
   Pendant (`VersandTab` hat keinen Mail-Inhalt). Sie wird erhalten.
2. **Nur Mail-Felder.** Der neue Baustein kennt weder Kanäle, Zeitplan, Profil noch Kanal-Gating
   (`weatherChannels`, `onChannelChange`, `profileOverride`, `mode`). Damit entfallen der
   `/api/auth/profile`-Fetch und die Doppelung zu `VersandTab` (C4-22 in #1986).
3. **Schreibpfad unverändert.** Der Baustein schreibt per Read-Modify-Write über
   `baueReportConfigPayload` mit dem **lebenden** Blob als Basis (`untrack`, kein Selbst-Trigger), mit
   `showSchedule=false` und `showChannels=false`. Er schreibt dieselben Mail-Felder wie bisher
   (`email_format`, `show_outlook`, `show_stage_stats`, `show_yesterday_comparison` sowie die
   nicht angezeigten Bestandsfelder `show_compact_summary`, `wind_exposition_min_elevation_m`,
   `show_quick_take_tags`, `show_stability`, `show_highlights`, `daily_summary_metrics`,
   `show_metrics_summary`). Keine Verhaltensänderung des Blobs, auch nicht zum Nachteil
   unbekannter Felder (`change_threshold_*`, `custom_unknown_*`).
4. **Fremdfeld-Schutz bleibt Pflicht.** Zeitplan-Felder (`morning_*`, `evening_*`, `enabled`,
   `multi_day_trend_*`), Kanal-Felder (`send_email`, `send_telegram`, `send_sms`, `send_premium_sms`) und
   `telegram_style` gehören `VersandTab`. Der Baustein schreibt sie nie (Fehlerklasse Fix-Loop 4, #1738).
5. **Mount-Disziplin bleibt.** Die XOR-Mounts per `isMobileViewport` in `TripNewEditor` (genau eine
   Instanz im DOM) und der Container `report-config-touch-scope` im Hub bleiben unverändert. Ein
   Wechsel dieser Disziplin wäre eine eigene Datenverlust-Gefahr (Last-Write-Wins).
6. **Hub-Dirty-Verhalten bleibt.** Die Mount-Normalisierung (#1269) darf den Trip im Hub nicht als
   „geändert" markieren; eine echte Nutzergeste muss weiter speichern (#774, #1234). Der Baustein selbst
   enthält keine Geste-Erkennung; die liegt wie bisher im umschließenden Container.
7. **Ortsvergleich: Karte bleibt route-eigen (Begründung für die Teilungsregel).** Der Ortsvergleich
   mountet die Karte nie; er hat ein eigenes Mail-Template und eigene Steuerung der Vorschau. Ein
   `context="vergleich"` wäre ein Parameter ohne Aufrufer. Dass der Baustein in `shared/` liegt, ist das
   Gegenteil eines Pendants; die Ablage ist so gewählt, weil Hub und Anlegen ihn gemeinsam nutzen.
8. **Konstanten.** `DEFAULT_DAILY_SUMMARY_METRICS` und `CONTENT_MODULE_DESCRIPTIONS` ziehen in
   `shared/mailInhaltKonstanten.ts`. Die übrigen Exporte von `reportConfigWrite.ts`
   (`toggleDailySummaryMetric`, `buildMailElementWrite`, `dailySummaryMetric*`,
   `countActiveContentModules`, `MailElementUi`) haben keinen produktiven Aufrufer und fallen mit,
   ebenso der Katalog `DAILY_SUMMARY_METRICS` (nur von `toggleDailySummaryMetric` genutzt; die Karte
   zeigt keine Kennzahlen-Auswahl). Bestehende Playwright-Specs unter `frontend/e2e/`, die
   `report-mail-content` ansprechen (z. B. `weather-metrics-tab-autosave`, `issue-619-mail-elements-ui`,
   `issue-723-email-tab-eindampfen`), brauchen keine Änderung, weil alle `data-testid` gleich bleiben; sie
   laufen unverändert gegen Staging.
9. **`trip-detail/briefingChannelGating.ts`:** Importiert nur die Section. Nach der Löschung hat sie
   keinen produktiven Aufrufer mehr und wird **mit** ihrem Test `issue_617_briefing_channel_gating.test.ts`
   gelöscht, sofern der Import-Scan das bestätigt. Bleibt ein Importeur, bleibt die Datei.

## Nicht im Umfang

- `VersandTab`, `VTBriefingChannels`, `VTSchedulePlan`, `mergeReportConfig.ts`, `reportConfigPayload.ts`
  (nur Kommentar-Verweise werden nachgezogen).
- Mail-Renderer, Mail-Template, Mail-Validatoren, Go-API, Python-Core.
- Inhalt und Optik der Karte (Texte, Reihenfolge, Farben), Reiter-Struktur.
- Eine inhaltliche Überarbeitung der Karte (z. B. weitere Schalter) und die Frage, ob die nicht
  angezeigten Bestandsfelder künftig nicht mehr geschrieben werden sollen. Das wäre eine eigene
  Produktentscheidung.
- **Nach S5 ist #2277 vollständig** (Ticket-AC-1 bis AC-7 geliefert); Schließen erst nach Prod-Selftest
  Exit 0.

## Affected Files

Pfade relativ zu `frontend/src/lib/components/`.

| File | Change Type | Description |
|------|-------------|-------------|
| `shared/MailInhaltCard.svelte` | CREATE | Karte „E-Mail-Inhalt", `$bindable reportConfig`, nur Mail-Felder, Read-Modify-Write mit lebendem Blob; `data-testid`-Werte unverändert. |
| `shared/mailInhaltKonstanten.ts` | CREATE | `DEFAULT_DAILY_SUMMARY_METRICS`, `CONTENT_MODULE_DESCRIPTIONS`. |
| `shared/WeatherMetricsTab.svelte` | MODIFY | Import und Mount auf `MailInhaltCard`; Kommentare (#1234, #1269) nachziehen; Container `report-config-touch-scope` unverändert. |
| `trip-new/TripNewEditor.svelte` | MODIFY | Import und beide Mounts (Desktop, Mobil) auf `MailInhaltCard`; XOR-Gate unverändert. |
| `trip-detail/TripTabs.svelte` | MODIFY | Toter Import von `BriefingsTab` entfällt. |
| `edit/EditReportConfigSection.svelte` | DELETE | Ersetzt durch Baustein. |
| `edit/reportConfigWrite.ts` | DELETE | Einziger Aufrufer war die Section. |
| `briefings-tab/BriefingsTab.svelte` | DELETE | Toter Mount (nirgends gerendert). |
| `trip-detail/briefingChannelGating.ts` | DELETE (bedingt) | Siehe Entscheidung 9. |
| Kommentar-Verweise in `shared/VersandTab.svelte`, `shared/versand-tab/{VTBriefingChannels.svelte,mergeReportConfig.ts,channelContactLabel.ts,reportConfigPayload.ts,premiumSmsChannelState.ts}`, `shared/reportConfigDirty.ts`, `trip-detail/weatherSaveGate.ts`, `trip-detail/BriefingScheduleTab.svelte` | MODIFY | Nur Texte; Verweise auf die gelöschte Section nachziehen. |
| Tests | MODIFY/DELETE | Siehe Abschnitt Tests. |

## Estimated Scope

- **LoC (produktiv):** Zugang ca. +190 (Baustein, Konstanten), Abgang ca. −830 (Section 574, Write 156,
  BriefingsTab 98, Gating 61). Netto stark negativ; brutto über dem 250-LoC-Limit durch Tests.
  Erwartet `workflow.py set-field loc_limit_override 500`.
- **Files:** 5 produktiv geändert oder neu, 3–4 gelöscht, ca. 12 Testdateien betroffen.
- **Effort:** medium. **Risk Level: MITTEL** — Verhalten muss gleich bleiben; die Kopplung an die
  Hub-Speicherlogik (`weatherSaveGate`, `reportConfigDirty`, Touch-Scope) ist die Gefahrenstelle.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `shared/versand-tab/reportConfigPayload.ts` | module | `baueReportConfigPayload`, `ladeReportZustand` (Read-Modify-Write). |
| `shared/versand-tab/mergeReportConfig.ts` | module | Merge-Regel mit Gating `showSchedule`/`showChannels`. |
| `shared/WeatherMetricsTab.svelte` | component | Hub-Mount, Touch-Scope, Dirty-Wächter. |
| `trip-detail/weatherSaveGate.ts`, `shared/reportConfigDirty.ts` | module | Hub-Speicherentscheidung; dürfen nicht neu „dirty" werden. |
| `trip-new/TripNewEditor.svelte` | component | Anlegen; XOR-Mount per `isMobileViewport`. |
| `feat_1481b_pendant_gate.md` | spec | Pendant-Sperre; neue Datei liegt in `shared/`. |
| `email_toggles_621.md`, `briefing_mail_inhalt.md` | spec | Bestehende Mail-Inhalt-Schalter (Verhalten bleibt). |

## Implementation Details

1. **Reihenfolge:** (a) RED-Tests an der Wirkstelle (Hub und Anlegen rendern die Karte über den neuen
   Baustein), (b) Baustein und Konstanten anlegen, (c) Mounts umhängen, (d) Altbestand und Alt-Tests
   löschen, (e) Kommentare nachziehen.
2. **Baustein:** aus dem Mail-Zweig der Section ableiten. Startzustand der Mail-Felder aus dem Blob,
   Standardwerte wie bisher (`email_format='full'`; `show_outlook`, `show_stage_stats`,
   `show_yesterday_comparison` an, `show_metrics_summary` aus). `onMount` übernimmt Werte wie bisher
   typgeprüft (`typeof … === 'boolean'`).
3. **Write-Back:** `$effect` ruft `baueReportConfigPayload` mit `showSchedule=false`,
   `showChannels=false`. Der Zustand `zustand` bleibt rein formal (die Gruppen werden nicht
   geschrieben). `telegram_style` bleibt außen vor.
4. **Compact-Modus:** Hinweis `report-compact-hint` und Deaktivierung der drei Schalter unverändert.
5. **Mounts:** Hub `edit`-Pfad (nicht `createMode`) im `report-config-touch-scope`; Trip-Anlegen im
   Versand-Reiter hinter dem `isMobileViewport`-Gate und im Mobil-Pfad.
6. **Nach der Löschung:** `grep -rn "EditReportConfigSection\|reportConfigWrite\|BriefingsTab"
   frontend/src frontend/e2e tests` darf keinen Import mehr finden; erlaubt sind nur erklärende
   Kommentare mit neuem Verweis.

## Expected Behavior

- **Input:** Nutzer öffnet den Wetter-Tab im Trip-Hub oder den Versand-Reiter von `/trips/new`.
- **Output:** Karte „E-Mail-Inhalt" wie bisher. Format und Schalter lassen sich ändern, der Hub speichert
  sie, das Anlegen übernimmt sie in den neuen Trip.
- **Side effects:** Keine. Kein zusätzlicher Netzwerkzugriff (der Profil-Fetch der Section entfällt, ohne
  dass der Mail-Inhalt davon abhing).

## Acceptance Criteria

- **AC-1:** Given ein bestehender Trip im Hub mit gespeichertem `email_format: "compact"` und
  `show_outlook: false` / When der Nutzer den Wetter-Tab öffnet / Then zeigt die Karte „E-Mail-Inhalt"
  (`report-mail-content`) „Kompakt" gewählt, den Hinweis `report-compact-hint` und den Schalter „Ausblick"
  ausgeschaltet; alle drei Schalter sind deaktiviert.
  - Test: Kern — SSR-Test auf der echten Hub-Komponente (`WeatherMetricsTab`), die Karte entsteht durch
    den Baustein, nicht durch die gelöschte Section.
  - Mutations-Gegenprobe: im Hub-Mount den Baustein durch `null` ersetzen oder `email_format` nicht aus
    dem Blob lesen ⇒ der Hub-Test wird rot.

- **AC-2:** Given ein bestehender Trip im Hub / When der Nutzer im Format „Ausführlich" wählt und
  „Vortag-Vergleich" ausschaltet und speichert / Then enthält das gespeicherte `report_config`
  `email_format: "full"` und `show_yesterday_comparison: false`, und alle übrigen Felder (auch unbekannte
  wie `change_threshold_*`) sind byte-gleich zum Vorzustand.
  - Test: Kern — Payload-Test (`baueReportConfigPayload` mit den Eigenfeldern des Bausteins gegen einen
    Blob mit Fremdfeldern) plus Hub-Test an der Speicherstelle (`weatherSaveGate`/Speichern-Payload).
  - Mutations-Gegenprobe: den lebenden Blob durch den Mount-Schnappschuss ersetzen oder unbekannte
    Felder beim Merge verwerfen ⇒ ein Test wird rot.

- **AC-3:** Given `/trips/new` im Versand-Reiter, Desktop-Breite / When der Nutzer „Kompakt" wählt /
  Then steht genau **eine** Karte `report-mail-content` im DOM, und der Anlege-Payload enthält
  `email_format: "compact"`.
  - Test: Kern — SSR-Harness-Test auf `TripNewEditor` (Versand-Reiter) zählt die Karten und liest den
    Anlege-Payload (Muster `trip_new_zeitplan_tab_nutzt_geteilten_versand_baustein`).
  - Mutations-Gegenprobe: das `isMobileViewport`-Gate entfernen (zwei Instanzen) ⇒ der Zähl-Test wird rot.

- **AC-4:** Given `/trips/new` in Mobil-Breite (390 px) / When der Nutzer den Versand-Reiter öffnet /
  Then steht ebenfalls genau eine Karte `report-mail-content` im DOM, und sie schreibt in denselben
  `report_config` wie die Desktop-Fassung.
  - Test: Kern — SSR-Harness mit gesetztem `isMobileViewport`; Staging-Playwright auf 390×844.
  - Mutations-Gegenprobe: den Mobil-Mount weglassen ⇒ der Mobil-Test wird rot.

- **AC-5:** Given `/trips/new`, Nutzer hat im Versand-Reiter Premium-SMS eingeschaltet und das
  Zeitplan-Fenster Morgen auf 06:30 gesetzt / When er danach in der Karte „E-Mail-Inhalt" einen Schalter
  umlegt / Then bleiben `send_premium_sms: true` und `morning_time` unverändert; die Karte schreibt
  nie Kanal-, Zeitplan- oder `telegram_style`-Felder.
  - Test: Kern — Baustein-Test: nach einem Klick in der Karte sind Kanal- und Zeitplan-Felder des Blobs
    gleich dem Vorzustand (zwei Blob-Zustände, auch mit abweichendem Nachbarwert).
  - Mutations-Gegenprobe: im Baustein `showChannels` auf `true` oder `showSchedule` auf `true` setzen ⇒
    der Test wird rot (Fremdfeld-Schutz).

- **AC-6:** Given ein Trip im Hub, den der Nutzer nur öffnet / When der Wetter-Tab mountet und die Karte
  den Blob beim Laden normalisiert, ohne dass der Nutzer etwas anfasst / Then bleibt der Trip „ungeändert":
  kein Speichern-Hinweis, kein geänderter Zustand. Wenn der Nutzer danach den ersten Schalter umlegt,
  wird gespeichert.
  - Test: Kern — Test auf `weatherSaveGate`/`reportConfigDirty` mit dem Baustein als Kind: Mount-Schreiben
    ohne Geste ⇒ nicht dirty; Geste in `report-config-touch-scope` ⇒ dirty.
  - Mutations-Gegenprobe: den Container `report-config-touch-scope` weglassen oder die Geste vor dem
    Mount-Schreiben zählen ⇒ der Test wird rot (Zusicherung an der Stelle, an der sie wirkt: im Hub,
    nicht im Baustein).

- **AC-7:** Given der Quellbaum nach dem Umbau / When man nach `EditReportConfigSection`,
  `reportConfigWrite` und `BriefingsTab` sucht / Then existieren `edit/EditReportConfigSection.svelte`,
  `edit/reportConfigWrite.ts` und `briefings-tab/BriefingsTab.svelte` nicht mehr, kein Quell-, Test- oder
  E2E-Code importiert sie, und `TripTabs.svelte` importiert `BriefingsTab` nicht.
  - Test: Kern — Wächtertest (Existenz, Import-Scan über `src/`, `e2e/`, `tests/`), nach Verhalten
    benannt.
  - Mutations-Gegenprobe: eine der drei Dateien zurücklegen oder den Import in `TripTabs` wiederherstellen
    ⇒ der Wächtertest wird rot.

- **AC-8:** Given die neue geteilte Datei und die Pendant-Sperre / When der Commit-Wächter
  (`pendant_gate.py`) den Änderungssatz prüft / Then bleibt er grün: `MailInhaltCard.svelte` liegt in
  `shared/`, es entsteht keine neue Datei in `trip-new/` oder `compare-new/`, und der Ortsvergleich
  (`CompareNewEditor`, Compare-Hub) rendert keine Karte `report-mail-content`.
  - Test: Kern — Lauf der Pendant-Sperre; Test, dass der Ortsvergleich die Karte nicht mountet
    (route-eigen, Begründung in Entscheidung 7).
  - Mutations-Gegenprobe: den Baustein probehalber nach `compare-new/` legen ⇒ die Pendant-Sperre
    schlägt an (Nachweis der Wirkung, nicht Produktbestandteil).

- **AC-9:** Given die Tests, die die gelöschten Dateien kannten (`issue_619_report_config_write`,
  `issue_693_email_config_cleanup`, `issue_723_email_tab_eindampfen`, `report_config_uses_shared_schedule`,
  `sms_unbestaetigt_trip_editor`, `reportConfigDirty`, `weatherSaveGate`, `report_slot_aktiv` und die
  Dateien unter `shared/versand-tab/__tests__/`) / When sie nach dem Umbau laufen / Then prüfen sie
  dieselben Zusicherungen am neuen Baustein, ohne dass eine Zusicherung ersatzlos verschwindet.
  - Test: Kern — Zuordnungstabelle alter Test ⇒ neuer Test im Adversary-Bericht; alle betroffenen
    Dateien grün (`node --test`). Reine Section-/Write-Tests ohne Entsprechung im Baustein werden
    gelöscht und in der Tabelle als „Zusicherung entfällt, weil Code entfällt" geführt.
  - Mutations-Gegenprobe: je eine Verfälschung pro früher bewachter Zusicherung (Format-Umschalter,
    Compact-Deaktivierung, Fremdfeld-Schutz, Read-Modify-Write) ⇒ jeweils mindestens ein Test wird rot.

- **AC-10:** Given ein Wegwerf-Nutzer auf Staging mit einem Trip, dessen Karte auf „Kompakt" steht /
  When ein Briefing an dessen Postfach versendet wird / Then trägt die zugestellte Mail den Header
  `X-GZ-Format: compact` und besteht `briefing_mail_validator.py` mit Exit 0; mit „Ausführlich" trägt sie
  `X-GZ-Format: full`.
  - Test: Live-E2E — Staging-Mail aus dem Test-Postfach (Wegwerf-Nutzer `gregor-test+…`), Validator
    `briefing_mail_validator.py`.
  - Mutations-Gegenprobe: im Baustein `email_format` nie schreiben ⇒ die Staging-Mail trägt weiter
    `full`, der Live-Test wird rot.

## Tests

**Neu oder umgehängt:**
- **Baustein-Test** `shared/__tests__/mail_inhalt_card.test.ts`: Startzustand aus dem Blob, Compact-Modus,
  Fremdfeld-Schutz mit zwei Blob-Zuständen, Read-Modify-Write mit unbekannten Feldern (AC-2, AC-5).
- **Hub-Wirkstellen-Test** (SSR auf `WeatherMetricsTab`): Karte aus dem Baustein, Touch-Scope und Dirty
  (AC-1, AC-6).
- **Anlege-Wirkstellen-Test** (SSR-Harness `tripNewSsr.ts`/`ssrRunesHook.mjs` auf `TripNewEditor`):
  genau eine Karte Desktop und Mobil, Anlege-Payload (AC-3, AC-4).
- **Wächtertest** Rückbau (AC-7) und Ortsvergleich-ohne-Karte (AC-8).
- **Umgehängte Alt-Tests:** `edit/issue_619_report_config_write.test.ts`, `issue_693_email_config_cleanup`,
  `issue_723_email_tab_eindampfen`, `edit/__tests__/report_config_uses_shared_schedule.test.ts`,
  `edit/__tests__/sms_unbestaetigt_trip_editor.test.ts` auf `MailInhaltCard` bzw. gelöscht mit
  Zuordnung (AC-9). Dateien nach Verhalten benennen. Prüflinge relativ zur eigenen Testdatei auflösen.

**Unverändert grün zu halten:** `reportConfigDirty.test.ts`, `weatherSaveGate.test.ts`,
`shared/versand-tab/__tests__/*`, `report_slot_aktiv.test.ts`,
`trip_new_versandkanaele_unabhaengig_von_metriken`, `trip_new_zeitplan_tab_nutzt_geteilten_versand_baustein`,
`anlege_reiterleiste_trip_vergleich_paritaet` (nur Kommentar-/Importpfad-Anpassungen).

**Mutations-Gegenprobe (Pflicht, Adversary):** Mutationen nur per String-Ersetzung mit externer
Sicherungskopie (nie `git checkout/stash/reset`). Zu verfälschen: (1) Hub-Mount entfernen, (2) `showChannels`
oder `showSchedule` im Baustein auf `true`, (3) lebenden Blob durch Schnappschuss ersetzen,
(4) `isMobileViewport`-Gate entfernen, (5) Touch-Scope-Container weglassen, (6) `email_format` nicht
schreiben. Gemeldet wird, **welcher** Test jeweils rot wird. Mutationen (1), (4) und (5) müssen an der
**Wirkstelle** (Hub bzw. `TripNewEditor`) rot werden, nicht nur im Baustein-Test; sonst Finding.

**Playwright (Staging, 390×844 und Desktop):** Versand-Reiter von `/trips/new` zeigt die Karte genau
einmal; Hub-Wetter-Tab zeigt sie; Umlegen eines Schalters im Hub speichert.

## Staging-Verifikation

Nach Merge und Staging-Auto-Deploy (`https://staging.gregor20.henemm.com`), mit Wegwerf-Nutzer
`gregor-test+…` (kein Sammel-Versand, kein Hauptkonto):

1. HTTP-Smoke: `/` → 200/302, `/api/health` → 200.
2. `/trips/new`, Versand-Reiter, Desktop und 390 px: eine Karte „E-Mail-Inhalt"; „Kompakt" wählen,
   Karte zeigt Hinweis und deaktivierte Schalter.
3. Trip im Hub: Wetter-Tab öffnen (kein Speichern-Hinweis ohne Geste), Schalter umlegen, speichern,
   neu laden, Wert steht.
4. Briefing-Mail an den Wegwerf-Nutzer, Validator `briefing_mail_validator.py` Exit 0
   (`X-GZ-Format` stimmt zur Karte; Staging-Zugang nach `/home/hem/gregor_zwanzig_staging/.env`).
5. Ist ein Teil nicht messbar, wird er als `NOT_MEASURABLE_ON_STAGING` geführt, nicht als PASS.

## Known Limitations

- Die nicht angezeigten Bestandsfelder (`show_quick_take_tags`, `show_stability`, `show_highlights`,
  `daily_summary_metrics`, `show_metrics_summary`, `show_compact_summary`,
  `wind_exposition_min_elevation_m`) werden weiter mitgeschrieben, wie heute. Ob sie entfallen können,
  ist eine eigene Entscheidung.
- Die Karte bleibt route-eigen; der Ortsvergleich hat keine Entsprechung (eigenes Mail-Template).
- Die Mount-Disziplin (XOR-Mount, Touch-Scope) bleibt eine Verabredung zwischen Hub/Anlegen und
  Baustein, kein Baustein-Merkmal.

## Risiken

- **Dirty-Drift im Hub:** Eine Änderung beim Mount-Zeitpunkt oder bei der Normalisierung markiert den
  Trip fälschlich als geändert oder verschluckt eine echte Geste. Gegenmittel: AC-6 an der Hub-Stelle,
  Mutation (5).
- **Fremdfeld-Überschreiben:** Der Baustein schreibt versehentlich Kanal-/Zeitplan-Felder oder arbeitet
  mit veraltetem Schnappschuss (Last-Write-Wins). Gegenmittel: AC-5, Mutationen (2), (3).
- **Zwei Instanzen im DOM:** Verlust des `isMobileViewport`-Gates. Gegenmittel: AC-3/AC-4, Mutation (4).
- **Test-Löschung nimmt Zusicherung mit:** Gegenmittel: Zuordnungstabelle (AC-9).
- **Falsches Grün durch Pfad-Auflösung:** Tests lösen ihren Prüfling relativ zur eigenen Testdatei auf.
- **Commit im Worktree:** drei Wächter mit Formvorgaben (Message-Datei); `e2e_scope` nach jedem Commit
  gegenlesen; Worktree-HEAD vor Deploy per `git merge --ff-only origin/main` angleichen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue (umgesetzt wird ADR-0032, progressive Tab-Editoren, und die PO-Vorgabe
  Trip/Ortsvergleich-Code-Teilung)
- **Rationale:** Verlagerung eines vorhandenen Bausteins in `shared/` und Rückbau des Altbestands; keine
  Entscheidungsfläche wird neu entschieden oder umgekehrt.

## Changelog

- 2026-10-02: Initial spec created (#2277 S5: Mail-Inhalt-Karte als `MailInhaltCard`, Rückbau
  `EditReportConfigSection`/`reportConfigWrite`/`BriefingsTab`)
