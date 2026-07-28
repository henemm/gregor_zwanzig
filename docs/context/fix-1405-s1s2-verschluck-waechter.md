# Context: fix-1405-s1s2-verschluck-waechter

Issue: [#1405](https://github.com/henemm/gregor_zwanzig/issues/1405) — Wächter 2 von 5
Scheibe: **S1 (Bestandsaufnahme) + S2 (Wächter)**. S3 (Mengenerhalt-Nachweise) und S4
(Reparatur der Restliste) sind eigene Scheiben, PO-Entscheidung 2026-07-28.

## Request Summary

Die häufigste Fehlerart im Projekt (18 von 79 Fehlern in vier Wochen) ist das *stille
Verschlucken*: ein Wert verschwindet, ohne dass irgendetwas es meldet. Diese Scheibe
nimmt die betroffenen Stellen auf und baut einen maschinellen Wächter (AST-Scan, Vorbild
`tests/test_output_timezone_guard.py` aus #1402), der neue Fälle rot macht.

## Vorbild: der Zeitzonen-Wächter (#1402)

`tests/test_output_timezone_guard.py` (594 Zeilen) ist die Bauform, die dieses Ticket
ausdrücklich fortschreibt:

| Bestandteil | Umsetzung in #1402 |
|---|---|
| Scan-Fläche | `src/output/**` + namentlich gelistete nachrichtenerzeugende Services |
| Erkennung | `ast`-Besuche auf 3 Bugklassen (Direktaufruf, Parameter-Default, Rückfall im Rumpf mit 4 Ausdrucksformen) |
| Restliste | `KNOWN_VIOLATIONS` mit Begründung je Eintrag |
| Ratsche | Zwei-Wege-Abgleich: neuer Fund → rot, erledigter Eintrag noch gelistet → ebenfalls rot |
| Aufrufseite | `test_production_callsites_pass_tz_explicitly()` — fand allein 3 echte Produktionsbugs |
| Bewusst nicht | Signatur-Umbau bei großer Aufrufer-Fläche (>3 Dateien) — Aufrufseiten-Prüfung statt 250 Golden-Test-Änderungen |

## Related Files

### Auflösungspfade (Menge rein → kleinere Menge raus)

| Datei | Relevanz |
|---|---|
| `src/output/renderers/compare_metric_ids.py:125` `resolve_enabled_metrics` | **Vorbildlich**: verworfene Einträge werden in `unmapped` gesammelt und per `logger.warning` gemeldet (#1285/#1296). Referenzmuster für „so muss es aussehen". |
| `src/output/renderers/compare_hourly_metric_ids.py:34` `resolve_hourly_metrics` | Gleiches Muster, seit #1361 Befund 3 mit Warnung |
| `src/output/renderers/compare_outlook_metric_ids.py:50` `resolve_outlook_metrics` | Gleiches Muster (`dropped`-Liste + Warnung), zusätzlich `continue` bei Dedup — **ohne** Meldung, das ist hier korrekt (Duplikat ist kein Verlust) |
| `src/output/renderers/compare_metric_catalog.py` | Umkehr-Index `key_for()`, Drift-Wächter beim Modul-Import |
| `src/app/metric_catalog.py` | Zentrales Namensregister seit #1401 A1 (`_METRICS_BY_ID`, `selectable`) |
| `src/services/report_config_resolver.py:111/193/209` | Render-Optionen + Zeitfenster für Trip und Compare |
| `src/services/compare_slot_scheduler.py:36` `resolve_preset_slots` | Versandzeitpunkte je Preset |
| `src/output/renderers/day_window.py:70` `resolve_configured_window` | Tagesfenster |

### Erfolgsrückgaben (Status ohne Wirkungsbezug)

| Fundstelle | Erste Einschätzung |
|---|---|
| `api/routers/scheduler.py:217` `{"status": "ok", ..., "sent": True}` | **Der #1403-Fall selbst** — konstantes Literal, keine Ableitung aus dem Zustellergebnis |
| `api/routers/scheduler.py:54/64/74/84/94/111/126` | `{"status": "ok", "count": n}` — `count` ist abgeleitet, `status` konstant; zu bewerten |
| `src/services/scheduler_dispatch_service.py:443` | `{"status": "ok", "winner": ..., "empfaenger_count": ...}` |
| `src/services/channel_test_service.py:42` | `{"status": "ok"}` bzw. `{"error": ...}` — zweiwertig, vermutlich sauber |
| `src/services/forecast_budget.py:102`, `src/services/official_alerts/meteoalarm_budget.py:143` | Budget-Status, vermutlich abgeleitet |
| `api/routers/health.py:9`, `api/routers/webhook.py:72` | Reine Lebendmeldungen — sollen konstant sein, gehören auf die Ausnahmeliste |

### Versand-/Kanalpfade (Kandidaten für die Scanfläche)

`src/output/channels/{email,sms,telegram,console,base}.py`,
`src/services/{notification_service,scheduler_dispatch_service,radar_alert_service,
compare_alert,compare_radar_alert,compare_official_alert,trip_alert,
deviation_alert_engine,channel_test_service}.py`

### Empfänger-Auflösung

`src/app/config.py`, `src/app/loader.py`, `src/app/models.py`,
`src/services/notification_service.py`, `src/output/channels/email.py`

## Existing Patterns

1. **Sammeln-und-melden** (Referenzmuster, dreifach vorhanden): verworfene Einträge in
   eine lokale Liste (`unmapped`/`dropped`), am Ende `logger.warning` mit den
   Fundstücken und Issue-Bezug. Genau das soll der Wächter erzwingen.
2. **„Leer heißt leer"** (#1366): `None` = Feld fehlt = kein Filter; `[]` = bewusst leer.
   Ein Auflöser darf eine leere Auswahl nie in „alle" umdeuten.
3. **Ratschen-Tests mit schrumpfender Ausnahmeliste**: `test_egress_inventory_drift.py`,
   `test_compare_catalog_derives_from_central_catalog.py` (`AGGREGATION_CHECK_EXEMPTIONS`),
   `test_output_timezone_guard.py`.

## Dependencies

- **Upstream:** `ast`-Modul, Repo-Struktur `src/`/`api/`; zentrales Register
  `src/app/metric_catalog.py` (#1401 A1, gestern gelandet)
- **Downstream:** Kein Produktivcode hängt am Wächter — er ist ein Test. Reparaturen aus
  S4 werden dagegen Renderer-Dateien berühren und damit das Renderer-Commit-Gate #811
  auslösen (in dieser Scheibe voraussichtlich noch nicht).

## Existing Specs

- `docs/specs/modules/` — Compare-/Trip-Renderer-Specs
- Epic #1372 („Kein stilles Verwerfen") — die Invariante als Satz, bisher ohne Durchsetzung
- CLAUDE.md → Test-Politik, Nebenbefund-Triage, Regel-Budget

## Risks & Considerations

1. **Fehlalarm-Flut ist das Hauptrisiko.** Eine naive Signatur (`if x in MAP`, `.get(k)`)
   trifft in `src/output/renderers/` + `src/services/` grob **309 Stellen**; nur ein
   Bruchteil davon sind echte Auflösungsschleifen. Der Wächter braucht eine enge,
   strukturell begründete Signatur (Schleife über eine Eingabemenge, deren Ergebnis in
   eine kleinere Ausgabemenge fließt), sonst wird er entweder abgeschaltet oder die
   Restliste ist von Anfang an dreistellig und damit wertlos.
2. **„Erfolg heißt Wirkung" ist schwerer prüfbar als „still verschluckt".** Ein
   konstantes `True` ist strukturell erkennbar; ob es *zu Recht* konstant ist
   (Lebendmeldung `/health`) nicht. Ausnahmeliste mit Begründung ist Pflicht.
3. **Nur `logger.warning` reicht dem Zielbild nicht.** Zielbild-Satz 3 verlangt
   „protokolliert **und** an der Oberfläche erkennbar". Der Wächter kann nur das
   Protokoll erzwingen; die Sichtbarkeit gehört in die S3-Mengenerhalt-Nachweise. Diese
   Grenze muss die Spec ausdrücklich ziehen, sonst verspricht der Wächter mehr als er hält.
4. **Go-Seite bleibt ungeprüft.** Der Scheduler und die Persistenz liegen in `internal/`
   (Go); ein Python-AST-Scan erreicht sie nicht. Muss die Spec als bewusste Abgrenzung
   benennen (Vorbild: `test_egress_inventory_drift.py` prüft Python↔Go über ein Inventar,
   nicht über AST).
5. **Regel-Budget (CLAUDE.md).** Ein neuer Pflicht-Test braucht entweder eine ersetzte
   Regel oder ein Prüfdatum (+90 Tage → 2026-10-26). #1402 hat einen echten Fang
   nachgewiesen; dieser hier muss das ebenso belegen.
6. **Reihenfolge ist bindend** (Ticket, Lehre aus #1402): Wächter vor Reparatur. Die
   Restliste dieser Scheibe darf lang sein — sie ist das Ergebnis, nicht das Versäumnis.

---

# Analysis (Phase 2, 2026-07-28)

## Type

Bug (Vorrichtung gegen eine belegte Fehlerart) — Label `bug`, `priority:high`.

## S1 — Bestandsaufnahme: Ergebnis

**Leitbefund: Beide Normen existieren bereits im eigenen Code — sie sind nur nicht
überall angewandt.** Der Wächter muss keine neue Regel erfinden, sondern ein vorhandenes
Muster ausrollen. Das senkt das Risiko erheblich und macht jeden Fund unstrittig.

### Hälfte A — „Was hineingeht, kommt heraus" (Auflösungspfade)

Norm im Bestand: `resolve_enabled_metrics` / `resolve_hourly_metrics` /
`resolve_outlook_metrics` (Compare) sammeln Verworfenes und melden es per
`logger.warning`. **13 STILL-Fundstellen** ohne diese Absicherung:

| # | Fundstelle | Was verschwindet |
|---|---|---|
| A1 | `src/output/renderers/trip_report.py:401` `_aggregate_night_block` | Nacht-Block-Spalte einer aktivierten Metrik |
| A2 | `src/output/renderers/trip_report.py:482` `_dp_to_row` | Stunden-Zeile-Spalte |
| A3 | `src/output/renderers/email/html.py:715` `_allowed_col_keys_for_horizon` | Spalte aus Horizont-Filter |
| A4 | `src/output/renderers/email/html.py:782` `render_html` (`_col_order`) | Spaltenreihenfolge/-sichtbarkeit der ganzen Mail |
| A5 | `src/output/renderers/email/helpers.py:100` `dp_to_row` | Stunden-Zeile-Spalte |
| A6 | `src/output/renderers/email/helpers.py:152` `aggregate_night_block` | Nacht-Block-Spalte |
| A7 | `src/output/renderers/email/helpers.py:975` `build_friendly_keys` | Ampel/Friendly-Format |
| A8 | `src/output/renderers/email/helpers.py:992` `build_format_modes` | Format-Mode-Eintrag |
| A9 | `src/output/renderers/email/helpers.py:1017` `build_html_indicator_keys` | Ampel-Aktivierung |
| A10 | `src/services/alert_preset.py:198` `resolve_alert_rules` | Direction-Feld-Optout |
| A11 | `src/services/compare_official_alert.py:115` `_check_one_preset` | Ort aus der Alarm-Prüfung |
| A12 | `src/services/official_alerts/meteoalarm.py:334` `_parse_cap` | ganze CAP-Warnung (except ohne Log) |
| A13 | `src/services/official_alerts/meteoalarm.py:361` `_parse_cap` | ganze Warnung bei unbekanntem `awareness_type` |

Zwei Muster stechen heraus:
- **A1–A9 sind ein einziger Mechanismus:** `try: get_metric(id) except KeyError: continue`
  neunmal wiederholt. Die Compare-Seite ist gehärtet, die **Trip-Seite nicht** — genau die
  Asymmetrie, die #1262 ausgelöst hat (Legacy-`display_config` mit veralteter Metrik-ID).
- **A11 hat zwei Geschwister, die korrekt melden** (`compare_alert.py:154`,
  `compare_radar_alert.py:139`). Nur der amtliche-Warnungen-Pfad fehlt.

### Hälfte B — „Erfolg heißt Wirkung" (Statusrückgaben)

Norm im Bestand: `trigger_trip_reports` (`api/routers/scheduler.py:43`) und
`trigger_compare_presets_daily` (`:143`) melden seit #766/#1290 `"partial"`, sobald
`failed > 0`. **12 Fundstellen** ohne diese Ableitung:

| # | Fundstelle | Befund |
|---|---|---|
| B1 | `api/routers/scheduler.py:217` `send_test_trip_report` | `sent: True` fest; `outcome == "no_channels"` (kein Kanal konfiguriert → nichts zugestellt) meldet trotzdem Erfolg. **Das ist #1403 selbst.** |
| B2–B8 | `api/routers/scheduler.py:54,64,74,84,94,111,126` | `status: "ok"` fest; `count` ist echt, fließt aber nicht in den Status. Totalausfall sieht aus wie ein leerer Lauf. |
| B9–B12 | `trip_alert.py:275` `check_all_trips`, `trip_alert.py:606` `check_radar_alerts`, `compare_alert.py:80` `check_all_compare_presets` (2 Aufrufwege), `scheduler_dispatch_service.py:443` `send_compare_preset` | Teilerfolg-blind: try/except je Element, nur Erfolgszähler, kein Fehlerzähler nach außen. |

Ausnahmekandidaten (bewusst konstant): `api/routers/health.py:9` (Lebendmeldung),
`api/routers/webhook.py:62/72` (Telegram verlangt protokollbedingt immer 200, sonst
Wiederhol-Sturm).

### Offener Widerspruch im Bestand (PO-Entscheidung nötig)

`src/services/notification_service.py:1065/1081/1102` (`_dispatch_alert_message`, genutzt
von Änderungs-, Radar- und amtlichen Alarmen) sowie `:660ff` und `:863ff`:
`sent_channels.append("email")` steht **vor** dem `try` des eigentlichen Versands, mit dem
Kommentar „Kanal gilt als betreten, wenn er konfiguriert ist — auch wenn der Best-Effort-
Versand fehlschlägt (Issue #684 AC-3)". Damit heißt `NotificationResult.sent=True`
„konfiguriert", nicht „zugestellt" — und die Doppelalarm-Sperre greift auch dann, wenn
nichts ankam. **Das ist eine dokumentierte Vorentscheidung aus #684, die dem Zielbild-Satz
2 von #1405 direkt widerspricht.** Nicht stillschweigend mitfixen.

## S2 — Technischer Ansatz

Bauform übernommen von `tests/test_output_timezone_guard.py` (#1402), bestätigt als
Hausform über 42 vergleichbare Wächter:

1. Scanfläche als Datei-Liste/Glob, `ast.parse` je Datei
2. Verletzungssammlung → `dict["pfad:zeile"] = "Begründung"`
3. **Zwei gekoppelte Ratschen-Tests:** `test_no_unlisted_*` (neuer Fund → rot) +
   `test_known_violations_only_shrink` (erledigter Eintrag noch gelistet → rot)
4. Restliste `KNOWN_VIOLATIONS` mit Issue-Bezug je Eintrag
5. Synthetische Wirkungsnachweise (`tmp_path`) — beweisen, dass der Scanner das Muster
   wirklich erkennt, ohne von Zeilennummern abzuhängen
6. Namenskonvention: `tests/test_<thema>_guard.py`

Schlüssel `pfad:zeile` sind bewusst nicht zeilenstabil — der Scanner erkennt die Bugklasse
strukturell, ein Verschieben erzeugt schlicht einen neuen Schlüssel.

### Signatur A (stilles Verschlucken) — beide Bedingungen müssen zutreffen

- **Mengenbezug:** Schleife/Comprehension über eine Sammlung, deren Iterationsergebnis in
  eine Ausgabesammlung fließt (`append`/Comprehension-Ziel/`dict[k]=`/`set.add`) oder
  direkt in einen Renderer-/Versandaufruf. Schließt reine Aggregations- und
  Schwellenwertschleifen aus.
- **Stiller Abbruchpfad:** `continue`/Comprehension-Filter/`except: pass` ohne
  `logger.*`-Aufruf und ohne `raise`, wobei das Filterprädikat ein **Lookup-Fehltreffer**
  ist (`x not in MAP`, `MAP.get(x) is None`, `except KeyError`) — nicht ein Vergleich
  gegen einen Schwellenwert.

Damit fallen ~210 der ~230 Rohtreffer heraus. Bekannte Scannergrenze: Stellen, die statt
zu verschwinden einen **sichtbaren Platzhalter** liefern (`narrow.py:_col_key` → `"–"`),
sind strukturell nicht von echtem Verlust zu unterscheiden → Namensmuster-Ausnahme
(`_col_key`, `_cell`, `fmt_*`).

### Signatur B (Erfolg ohne Wirkung)

- **B-konstant:** Dict-Return mit Schlüssel aus `{status, sent, success, ok}` und
  Literalwert (`True`/`"ok"`/`"success"`) in einer Funktion, die weiter oben ein
  Ergebnis aus einem Unteraufruf empfangen und verzweigt hat, dieses aber nicht in den
  Rückgabeausdruck einfließen lässt. Trifft B1 exakt.
- **B-teilerfolg:** Schleife mit `try/except` je Element (= Fehlerisolierung), deren
  Funktion nur einen Erfolgszähler und kein Feld `failed`/`errors`/`skipped` nach außen
  gibt; Gegenprobe auf der Aufrufseite (Router setzt `status` ohne Bezug auf den Zähler).
- Lebendmeldungen (`health.py`, `webhook.py`) werden **per Liste** ausgenommen, nicht
  algorithmisch — die Unterscheidung ist inhaltlich, nicht syntaktisch.

## Scope Assessment

| Größe | Schätzung |
|---|---|
| Neue Dateien | 1–2 Wächter-Tests unter `tests/` |
| Geänderte Produktivdateien | **0** in dieser Scheibe (Wächter vor Reparatur) |
| LoC | Hälfte A ~350, Hälfte B ~350 (Vergleich: #1402 = 594 Zeilen für 3 Bugklassen) |
| Risiko | **Niedrig für den Betrieb** (reiner Test), **mittel für den Nutzen** (zu weite Signatur → Fehlalarme → wertlose Restliste) |
| LoC-Limit | 250/Workflow — wird in jedem Zuschnitt überschritten, Freigabe des PO nötig |

## PO-Entscheidungen (2026-07-28)

- [x] **Q1 — `#684`-Fall:** zählt als **Fund**, nicht als dauerhafte Ausnahme. Kommt mit
      Begründung auf die Restliste (der Hälfte B) und wird in der Reparatur-Scheibe S4
      behandelt, **nicht** jetzt — das Umstellen berührt die Doppelalarm-Sperre und ist
      eine echte Verhaltensänderung.
- [x] **Q2 — Zuschnitt:** die beiden Hälften laufen **nacheinander als zwei
      Arbeitseinheiten**, jede mit eigener Prüfung und eigener Restliste.

## Scope DIESER Arbeitseinheit

**Nur Hälfte A — „Was hineingeht, kommt heraus":** der Auflösungs-Wächter plus die
Restliste der 13 Fundstellen A1–A13. Keine Reparatur von Produktivcode.

Ausdrücklich **nicht** in dieser Einheit:
- Hälfte B („Erfolg heißt Wirkung", B1–B12 inkl. `#684`-Fall) → eigene Einheit als nächstes
- S3 (Mengenerhalt-Nachweise über die gerenderte Ausgabe) und S4 (Reparaturen) → eigene Scheiben
- Go-Code (`internal/`) — ein Python-AST-Scan erreicht ihn nicht; bewusste Lücke,
  in der Spec als Abgrenzung zu benennen

## Offener Punkt für die Spec-Phase

- Änderungsbudget: 250 Zeilen je Arbeitseinheit; der Wächter wird nach heutiger Schätzung
  ~350 Zeilen. Freigabe des PO einholen, sobald der Umfang aus der Spec belastbar ist.
