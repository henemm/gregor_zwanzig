---
entity_id: fix_1727_s5e_sperrcache_anzeige
type: bugfix
created: 2026-08-19
updated: 2026-08-19
status: draft
version: "1.0"
tags: [official-alerts, massif-closure, account-page, adr-0051]
---

# Fix #1727 S5e — Sperrcache tagesbewusst schlüsseln + Konto-Anzeige ehrlich beschriften

## Approval

- [ ] Approved

## Purpose

Zwei Reste aus dem Umgebungsuhr-Umbau (ADR-0051, Issue #1727): (A) der Zugangssperren-Cache für
französische Waldbrand-Massive schlüsselt nicht nach Kalendertag und kann deshalb bis zu 30 Minuten
lang eine über Nacht neu verhängte Sperre verschweigen; (B) die Konto-Seite beschriftet den
generischen stündlichen Scheduler-Tick als Versandtermin und formatiert ihn fest in Wiener Zeit statt
in der Zeitzone des Nutzers.

## Source

- **File A:** `src/services/official_alerts/massif_closure.py`
- **Identifier A:** `_get_cached_daily_json(src, ymd)` (`:98-112`)
- **File B:** `frontend/src/routes/account/+page.svelte`
- **Identifier B:** `formatNextRun(iso)` (`:264-281`)

## Estimated Scope

- **LoC:** ~45 Produktivcode (A: ~10, B: ~15 plus ~20 verschobene Zeilen) + ~140 Tests
- **Files:** 3 Produktivdateien (`massif_closure.py`, `account/+page.svelte`, neu
  `lib/utils/schedulerTime.ts`) + 4 Testdateien (Kern-Test A, Unit-Test B, **Playwright-Test B**,
  **Live-Ausgabe-Test A**)
- **Nachweis-Schichten:** Kern (deterministisch) für den Tageswechsel · Browser (Playwright gegen
  Staging, zwei Zeitzonen) für die Anzeige · Live-Ausgabe (echte Staging-Mail per IMAP + echte
  Telegram-Nachricht) für die Wirkung der Sperre auf das Briefing
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `warn_egress.cached_fetch` | function | TTL-Cache-Kern, unverändert — Schlüssel bleibt Aufrufer-Verantwortung |
| `utils.timezone.local_dt` / `tz_for_coords` | function | liefert bereits korrekt den Herausgebertag (S5d) — unverändert |
| `official_alerts/base.py:137-148` | Registry | ruft `covers`/`fetch` in `try/except Exception` — Signatur von `MassifClosureSource` darf nicht erweitert werden, sonst deaktiviert ein Fehler die Quelle still statt laut zu brechen |
| `/api/scheduler/status` → `jobs[].next_run` | API-Feld | Datenquelle für (B), unverändert — nur die Anzeige ändert sich |
| `trip_report_scheduler.py:180-189` | scheduling | tatsächliche Versandlogik, **nicht** Teil dieser Scheibe — Invariante: bleibt unberührt |

## Implementation Details

### (A) `src/services/official_alerts/massif_closure.py`

1. **Cache-Schlüssel trägt den Kalendertag.** Vorbild `meteoalarm.py:768`
   (`f"{country}:{slot}:p{page}"`), dort ist der Zeitanteil bereits Teil des Schlüssels. Neuer Schlüssel:
   `f"{src}:{ymd}"` statt bisher `src`.
2. **Aufräumen beim Ablegen.** `warn_egress.cached_fetch`/`_store_entry` kennen keine Invalidierung
   (Ablauf nur beim Zugriff, `warn_egress.py:431-434`) — ohne Aufräumen wüchse `_cache` in einem
   langlebigen Prozess pro Quelle und Kalendertag unbegrenzt. Vor dem Aufruf von
   `warn_egress.cached_fetch(...)` entfernt `_get_cached_daily_json` alle vorhandenen Einträge in
   `massif_closure._cache`, deren Schlüssel mit `f"{src}:"` beginnt und vom aktuellen `cache_key`
   abweicht (also Einträge derselben Quelle für einen anderen Tag).
3. **Keine Signaturänderung.** `_get_cached_daily_json(src, ymd)`, `MassifClosureSource.covers()` und
   `MassifClosureSource.fetch()` behalten ihre bestehenden Signaturen — die Änderung bleibt vollständig
   innerhalb der Schlüsselbildung. `warn_egress.py` (der geteilte Kern) und `base.py` (Registry) werden
   nicht angefasst.

### (B) `frontend/src/routes/account/+page.svelte`

1. **Label:** `Nächster:` (`:599`) wird zu `Nächste Prüfung:` — sagt, was der Wert ist (generischer
   Poll-Tick, kein Versandtermin).
2. **Zone:** alle vier `timeZone: 'Europe/Vienna'`-Literale (`:269, :270, :271, :279`) entfallen. Ohne
   `timeZone`-Option formatiert `Intl`/`Date` implizit in der Zeitzone des ausführenden Browsers — analog
   zu allen übrigen Zeitanzeigen im Frontend (`compare/subscriptionHelpers.ts:54-58`,
   `_home/TripKachel.svelte:11`, `+page.svelte:50/141/407`), die schon heute ohne `timeZone`-Angabe
   arbeiten.
3. **Zonenkürzel sichtbar:** die Uhrzeit-Formatierung (`:271`) erhält `timeZoneName: 'short'`, damit die
   Zahl trotz wegfallender fester Zone eindeutig bleibt. Erstmalige Einführung dieser Option im
   Frontend — Darstellung muss WCAG-AA-Kontrast einhalten (Design-Leitprinzipien, `CLAUDE.md`).
4. **Relativlogik unverändert:** `heute um …` / `morgen um …` bleibt erhalten, der Tagesvergleich
   (`:273-278`) rechnet nur noch ohne die feste Zonen-Option statt gegen `Europe/Vienna`.
5. 🔴 **Funktion auslagern, damit sie prüfbar wird.** `formatNextRun()` liegt heute als interne Funktion
   im `<script>`-Block von `+page.svelte` und ist damit **von außen nicht aufrufbar** — ein Unit-Test
   kann sie nicht importieren. Sie wandert unverändert in ein eigenes Modul
   `frontend/src/lib/utils/schedulerTime.ts` und wird dort exportiert; `+page.svelte` importiert sie.
   Das ist die Voraussetzung für AC-5 und zugleich der erste geteilte Zeit-Baustein im Frontend (bisher
   existiert keiner — jede Stelle formatiert eigenständig). Kein Verhalten ändert sich durch die
   Verschiebung selbst.

## Expected Behavior

- **Input A:** zwei `fetch()`-Aufrufe für dieselbe Präfektur-Quelle an zwei unterschiedlichen
  Kalendertagen, innerhalb der 1800s-Erfolgs-TTL, ohne Cache-Löschung dazwischen.
- **Output A:** der zweite Aufruf löst einen echten zweiten HTTP-Request gegen den Endpunkt des
  zweiten Tages aus und liefert dessen Daten; nach dem zweiten Aufruf enthält `_cache` genau einen
  Eintrag für diese Quelle (den des zweiten Tages).
- **Side effects A:** keine — Egress-Zähler/Journal-Verhalten von `cached_fetch` unverändert.
- **Input B:** `job.next_run` (ISO-Zeitstempel) aus `/api/scheduler/status`, gerendert im Browser eines
  Nutzers in beliebiger Zeitzone.
- **Output B:** Label „Nächste Prüfung", Uhrzeit in der Browser-Zeitzone mit sichtbarem Zonenkürzel.
- **Side effects B:** keine — reine Anzeigeänderung, kein Einfluss auf `next_run` selbst oder auf die
  tatsächliche Versandlogik.

## Acceptance Criteria

- **AC-1:** Given zwei aufeinanderfolgende Kalendertage innerhalb der 1800s-Erfolgs-TTL für dieselbe
  Massiv-Quelle, When `MassifClosureSource().fetch()` am zweiten Tag erneut aufgerufen wird, ohne dass
  der Cache zwischen den Aufrufen geleert wird, Then löst der zweite Aufruf einen echten zweiten
  HTTP-Request gegen den Endpunkt des zweiten Tages aus (nicht nur einen Cache-Treffer auf den ersten
  Tag).
  - Test: lokaler HTTP-Sentinel (Vorbild `_lokaler_massif_server()` in
    `test_import_und_fremdquellen_folgen_ortstag.py`) zeichnet angefragte Pfade auf; zwei `fetch()`-Aufrufe
    unter `freeze_time` auf zwei verschiedene Kalendertage, `massif_closure._cache` wird zwischen den
    Aufrufen **nicht** geleert (Gegenteil des bestehenden Testhelfer-Musters `:164-166`, das den Fall aktiv
    umgeht). Erwartung: `len(requested_paths) == 2`, zweiter Pfad trägt das `ymd` des zweiten Tages.

- **AC-2:** Given der Cache enthält nach dem ersten Aufruf einen Eintrag für Quelle+Tag-1, When der
  zweite Aufruf für Quelle+Tag-2 abgeschlossen ist, Then ist der Eintrag für Tag-1 aus
  `massif_closure._cache` entfernt und es existiert nur noch der Eintrag für Tag-2 (kein unbegrenztes
  Wachstum je Quelle über die Zeit).
  - Test: direkt im Anschluss an AC-1-Testlauf `massif_closure._cache.keys()` prüfen — genau ein
    Schlüssel, der mit dem zweiten `ymd` endet.

- **AC-3:** Given die Official-Alerts-Registry ruft `MassifClosureSource.covers()`/`.fetch()` in
  `try/except Exception` (`base.py:137-148`), When die Cache-Schlüsseländerung umgesetzt ist, Then
  bleiben beide Methodensignaturen unverändert und der bestehende Registry-Testpfad
  (`tests/tdd/test_issue_1037_massif_closure.py`) läuft unverändert und grün — kein Fehler wird durch
  eine neue Pflichtangabe still verschluckt.
  - Test: bestehende Testsuite `test_issue_1037_massif_closure.py` unverändert ausführen, alle 10
    Methoden weiterhin grün, keine Signaturänderung nötig.

- **AC-4:** Given die Konto-Seite zeigt den nächsten Prüf-Zeitpunkt eines Scheduler-Jobs, When die Seite
  gerendert wird, Then steht dort sichtbar „Nächste Prüfung" statt „Nächster" vor dem formatierten
  Zeitwert.
  - Test: **echter Browser-Test** (Playwright, `frontend/e2e/`) — Konto-Seite aufrufen, den sichtbaren
    Text der Scheduler-Zeile auslesen und auf „Nächste Prüfung" prüfen. Ein Dateiinhalt-Grep auf
    `+page.svelte` ist als Nachweis **ausdrücklich untersagt** (Test-Politik: Dateiinhalt-Checks belegen
    kein Verhalten); die Beschriftung ist statisches Markup und nur im gerenderten Zustand prüfbar.

- **AC-5:** Given ein Browser läuft in einer von Wien abweichenden Zeitzone (z. B. `America/New_York`),
  When `formatNextRun()` einen ISO-Zeitstempel rendert, Then erscheint die Uhrzeit in der Zeitzone des
  Browsers (nicht mehr fest `Europe/Vienna`) und trägt ein sichtbares Zonenkürzel
  (`timeZoneName: 'short'`), sodass sich der Anzeigewert nachweisbar ändert, wenn die simulierte
  Browser-Zone wechselt.
  - Test: Unit-Test gegen das neue Modul `frontend/src/lib/utils/schedulerTime.ts` (Auslagerung siehe
    Implementation Details B.5 — ohne sie ist die Funktion nicht importierbar). Derselbe ISO-Input wird
    unter zwei gesetzten Zonen (`Europe/Vienna` vs. `America/New_York`) formatiert; erwartet werden
    **unterschiedliche** Uhrzeit-Strings, beide mit Zonenkürzel.
  - 🔴 **Positivkontrolle Pflicht:** Der Test muss belegen, dass die Zonen-Umschaltung im Testaufbau
    überhaupt wirkt. Ein Testgerüst, in dem `TZ` folgenlos bleibt, liefert zwei identische Strings und
    wäre auch bei fest verdrahtetem Wien grün — der Nachweis wäre wertlos. Die beiden erwarteten
    Uhrzeiten sind deshalb als konkrete Werte zu prüfen, nicht nur auf Ungleichheit.
  - 🔴 **Der Unit-Test allein genügt nicht** — die Wirkung ist zusätzlich im echten Browser zu belegen,
    siehe AC-7.

- **AC-6:** Given die bestehende Versandkette (nackte Eingabe-Uhrzeit → naive Speicherung → Auswertung
  als Ortszeit des Trip-Startpunkts über `trip_report_scheduler.py:180-189`) ist ADR-0051-konform und
  korrekt, When diese Scheibe umgesetzt ist, Then ist an `trip_report_scheduler.py`, `models.py`,
  `internal/model/trip.go` oder anderen Versand-Dateien keine Zeile geändert, und die bestehende
  Scheduler-Testsuite bleibt unverändert grün.
  - Test: `git diff --stat` gegen `origin/main` (Drei-Punkt-Vergleich, damit fremde Parallelarbeit nicht
    als eigene zählt) zeigt ausschließlich `massif_closure.py`, `account/+page.svelte`,
    `lib/utils/schedulerTime.ts` plus die zugehörigen Testdateien; bestehende
    `trip_report_scheduler`-Tests laufen unmodifiziert durch.
- **AC-7:** Given die Konto-Seite läuft auf Staging und ein Browser wird einmal mit der Zeitzone
  `Europe/Vienna` und einmal mit `America/New_York` gestartet, When dieselbe Seite in beiden Fällen
  geöffnet wird, Then zeigt die Scheduler-Zeile beide Male den Text „Nächste Prüfung", **verschiedene**
  Uhrzeiten und jeweils das zur Browser-Zone passende Zonenkürzel.
  - Test: Playwright gegen `https://staging.gregor20.henemm.com`, zwei Browser-Kontexte mit
    `timezoneId: 'Europe/Vienna'` bzw. `timezoneId: 'America/New_York'`; der sichtbare Text der Zeile
    wird ausgelesen und verglichen. Das ist der Nachweis für AC-4 **und** AC-5 an der Stelle, an der die
    Änderung wirkt — im gerenderten Browser, nicht in einer Testumgebung.
  - 🔴 Die beiden Uhrzeiten **müssen** sich unterscheiden. Wären sie gleich, wäre entweder die feste
    Zone noch drin oder der Zonenwechsel des Testbrowsers folgenlos — beides ist ein Fehlschlag, kein
    Grenzfall.

- **AC-8:** Given eine amtliche Waldbrand-Zugangssperre liegt für ein Massiv des Test-Trips vor, When
  ein Briefing über Staging versendet wird, Then erscheint diese Sperre in der **zugestellten E-Mail**,
  in der **zugestellten Telegram-Nachricht im Vollformat** (`telegram_style: 'rich'`) und im
  **SMS-Kurzstil** (`telegram_style: 'kurzform'`).
  - Test: Live-Schicht. Versand über Staging, E-Mail per IMAP aus `gregor-test@henemm.com` abgeholt und
    im Text nachgewiesen; Telegram-Nachricht im Zielchat nachgewiesen. Damit ist belegt, dass der
    geänderte Cache-Pfad die Ausgabe tatsächlich erreicht — nicht nur, dass ein Dict den richtigen
    Schlüssel trägt.
  - 🔴 **SMS wird über den Telegram-Kurzstil geprüft, nicht durch echten SMS-Versand** (PO-Dauerregel).
    Der Schalter „Telegram im SMS-Kurzstil" (`TelegramKurzstilToggle.svelte`, Feld
    `report_config.telegram_style`, Werte `'rich'` | `'kurzform'`, Spec
    `docs/specs/modules/feat_1260_telegram_kurzstil.md`) lässt Telegram denselben kurzen Ein-Zeilen-Text
    ausliefern wie SMS. Damit ist das SMS-**Format** an einer echt zugestellten Nachricht belegt, ohne
    Kosten und ohne Versand ans Satellitengerät. Der Nachweis ist mit beiden Stellungen des Schalters zu
    führen, weil die Sperren-Darstellung im Kurzstil eine andere ist als im Vollformat.
  - Grenze: Der Kurzstil belegt den **Inhalt** des SMS-Formats, nicht den **Transportweg** (Provider,
    Zeichenzählung beim Versand, Zustellung am Gerät). Für diese Änderung genügt der Inhalt — der
    Transport ist von ihr nicht berührt.
  - 🔴 **Ehrliche Grenze:** Ein echter Kalendertagwechsel ist auf Staging nicht herstellbar. AC-8 ist
    deshalb die **Positivkontrolle des Ausgabewegs** (die Sperre kommt an), nicht der Nachweis des
    Tageswechsels — den führt AC-1 in der Kern-Schicht. Beide zusammen decken die Zusicherung ab;
    einzeln tut es keines von beiden. Liegt zum Testzeitpunkt für kein Massiv eine Sperre vor, ist das
    als SKIP mit Begründung zu dokumentieren, **niemals** als bestanden zu melden.

## Known Limitations

- **Der Kalendertagwechsel ist auf Staging nicht herstellbar.** Er wird deshalb in der Kern-Schicht
  gegen einen lokalen Sentinel nachgewiesen (AC-1); Staging belegt den Ausgabeweg (AC-8). Wer nur eines
  von beiden vorzeigt, hat die Zusicherung nicht belegt.
- **Nachgewiesene Ausgabeformate sind E-Mail, Telegram-Vollformat und SMS-Kurzstil** (AC-8). Das
  SMS-Format wird über den Telegram-Kurzstil geprüft — echter SMS-Versand findet nicht statt und ist
  für einen Inhaltsnachweis auch nicht nötig (PO-Dauerregel 2026-08-19).
- **Premium-SMS wird nicht eigens geprüft.** Sie teilt den Kurzstil-Renderweg mit SMS; geprüft wird
  hier der Inhalt, und der ist identisch. Eine Abweichung im Transportweg wäre ein eigener Befund,
  kein Regress dieser Scheibe.
- Der eigentliche nächste Versandzeitpunkt je Trip in dessen Ortszeit wird weiterhin **nicht** angezeigt
  — das bleibt ausdrücklich #1969 (PO-entschieden ausgelagert, größerer Umbau).
- Ob externes Monitoring in `henemm-infra` den bisherigen Label-Text „Nächster" oder das ISO-Feld
  `next_run` maschinell parst, ist von hier aus nicht messbar (anderes Repo) — als Lücke benannt, nicht
  geschätzt.
- Muster-3 des Zeitzonen-Wächters (`.hour`/`.date()` auf nicht zonenaufgelöstem Zeitstempel) und die
  Ausweitung der Wächter-Suchfläche auf `src/providers/`/`src/app/loader.py` sind eigener Umfang
  (#1199), nicht Teil dieser Scheibe.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — Umsetzung folgt ADR-0051 Regel 2/3 (Zeitbegriffe, Zone an den Daten),
  Status dort weiterhin „Vorgeschlagen" (in #1199 gebucht, unverändert durch diese Scheibe).
- **Rationale:** (A) ist eine reine Cache-Schlüssel-Korrektur ohne neues Architekturmuster — das Vorbild
  (`meteoalarm.py:768`) existiert bereits im selben Modulverbund. (B) ist eine reine Anzeigekorrektur,
  die das Frontend an das bestehende Muster „keine feste `timeZone`" angleicht, das an allen anderen
  Stellen schon gilt.

## Changelog

- 2026-08-19: Initial spec created

## Offene Punkte

- Die Testvorgabe in AC-1 verlangt, dass der bestehende lokale HTTP-Sentinel (`_lokaler_massif_server()`)
  wiederverwendet wird, aber **ohne** dessen Cache-Leerung zwischen den Aufrufen — der Handler liefert
  aktuell für jeden Pfad denselben statischen Body (`{"massifs": {"831": [1]}}`). Das genügt für AC-1
  (Nachweis über die **Pfade**, nicht über unterschiedliche Inhalte), sollte aber beim Schreiben des
  Tests explizit so kommentiert werden, damit niemand versehentlich einen Inhaltsvergleich erwartet, den
  der Sentinel gar nicht liefert.
