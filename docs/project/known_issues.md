# Known Issues & Bug Report Log (Archiv)

> **Offene Bugs sind auf GitHub Issues:**
> https://github.com/henemm/gregor_zwanzig/issues?q=label%3Abug
>
> Diese Datei bleibt als Detail-Referenz fuer Root-Cause-Analysen bestehen.

## BUG-1428-PREFLIGHT-SCOPE: staging_gate.py widersprach sich zwischen Preflight und Post-Reset-Check

**Status:** RESOLVED (2026-07-30) | **Severity:** High (Ursache eines Produktionsausfalls) | **GitHub Issue:** #1428 (henemm-infra#148)

### Symptom

`deploy-gregor-prod.sh` stufte denselben Ziel-Commit im Preflight (vor dem Sync) als `docs-only` (übersprungen) ein, im regulären Check nach dem Reset (identischer Commit, jetzt HEAD) aber als `backend`/gate-pflichtig — blockierte dort. Da das Script `gregor-python` bereits vor diesem zweiten Check gestoppt hatte, blieb der Dienst nach dem Abbruch offline (henemm-infra#148, Produktionsausfall 2026-07-29 ~19:38 UTC, separat infra-seitig durch einen trap-Handler gefixt).

### Root Cause

Zwei verschiedene Diff-Basen für dieselbe Scope-Frage: Der Preflight (`expected_commit` bekannt) diffte eng `HEAD..expected_commit`, schrieb dabei aber bewusst keinen Scope-Cache-Marker (Cache-Poisoning eines noch nicht ausgerollten Zustands wäre die Folge gewesen). Der reguläre Check nach dem Reset (`expected_commit=None`) fand deshalb keinen Cache-Treffer für den neuen HEAD und fiel auf den Marker des letzten ERFOLGREICHEN Gate-Laufs zurück — potenziell mehrere Commits alt, und damit ein deutlich breiterer, andere Frage beantwortender Diff-Bereich als der Preflight.

Ein erster Lösungsvorschlag (Scope-Wert unter der Ziel-SHA cachen) hätte NICHT funktioniert: `cached_scope_for_sha()` verwirft gecachte `docs-only`-Werte grundsätzlich (Schutzregel aus #1096/F001) — und `docs-only` war genau der im Vorfall betroffene Wert.

### Fix (Committed 2026-07-30, `e77a3c6e`)

Der Preflight hinterlegt jetzt seine Diff-**Basis** (den alten, noch live laufenden Commit) für den Ziel-Commit — nicht den Scope-Wert. `_scope_diff_base()` nutzt diesen Hint, sofern die hinterlegte SHA noch auflösbar ist und zum tatsächlichen Ziel-Commit passt, statt auf den möglicherweise veralteten Marker zurückzufallen. Der Scope wird weiterhin bei jedem Lauf frisch aus dem echten `git diff` berechnet — die #1096-Schutzregel bleibt unberührt, da nichts mehr als fertiger Scope-WERT gecacht wird.

Diagnose und Fix-Design stammen von der `henemm-infra`-Claude-Instanz (inkl. Selbstkorrektur ihres ersten, unzureichenden Vorschlags); die `gregor_zwanzig`-Instanz hat den fertigen Entwurf eingespielt, um einen Editier-Konflikt mit einer parallel laufenden Session zu vermeiden.

### Files Changed

- `.claude/hooks/_e2e_paths.py` (neu: `last_preflight_base_path`, `write_preflight_base`, `read_preflight_base`)
- `.claude/hooks/staging_gate.py` (`_scope_diff_base()` Hint-Vorrang, `gate_check()` schreibt die Basis im Preflight-Zweig)
- `tests/tdd/test_fix_1428_preflight_scope_base.py` (neu, End-to-End-Reproduktion des Vorfalls + zwei Unit-Tests)

### Lessons Learned

1. **Eine Diff-BASIS zu hinterlegen ist robuster als einen fertigen Scope-WERT zu cachen**, wenn eine bereits bestehende Schutzregel (hier #1096/F001) genau diesen Wert-Cache für einen bestimmten Ergebnistyp (`docs-only`) grundsätzlich verwirft — der erste, naheliegende Lösungsansatz hätte an der eigenen Schutzregel scheitern müssen.
2. **Cross-Repo-Root-Cause-Analyse funktioniert**, wenn die diagnostizierende Instanz keinen Schreibzugriff auf das betroffene Repo braucht, um trotzdem den vollständigen Fix (inkl. Code) zu liefern — die Umsetzung bleibt dann bei der zuständigen Instanz.

---

## BUG-1383-1385-1386-ALERT-TZ: Alarm-Uhrzeiten in drei Renderpfaden in UTC statt Ortszeit

**Status:** RESOLVED (2026-07-25) | **Severity:** High (falsche Sicherheitsaussage — Zeitangabe im Wetteralarm bis zu mehrere Stunden daneben) | **GitHub Issues:** #1383, #1385, #1386

### Symptom

Drei unabhängige, aber wurzelverwandte Fehler in Alarm-Mails:

- **#1383:** Der Radaralarm des Ortsvergleichs rendete alle Uhrzeiten in UTC statt in der Ortszeit — eine Prod-Mail meldete „Regen in 15 Min ab 20:00" für einen Ort in `Europe/Paris`, tatsächlich 2 Stunden daneben.
- **#1385:** Bei einem gebündelten Alarm für mehrere Orte trugen ALLE Orte die Zeitzone des ersten Ortes — Zermatt und Auckland in einem Bündel zeigten beide „ab 23:18", obwohl nur einer davon stimmen konnte.
- **#1386:** Die Ereigniszeit des Abweichungs-Alarms („Wo & wann: … · HH:MM") und das SMS-Kürzel `@HH` standen ebenfalls in UTC.

### Root Cause

Gemeinsamer Nenner aller drei: **Zeitstempel wurden zu früh in fertige Strings verwandelt**, an einer Stelle, die den Ort (und damit die Zeitzone) noch nicht kannte — danach war die Zeitzone nicht mehr korrigierbar.

- `compare_radar_alert.py` warf das Ortsobjekt vor dem Versand weg; `send_multi_location_radar_alert` fiel dadurch still auf `ZoneInfo("UTC")` zurück (#1383).
- `to_multi_location_onset_alert_message` formatierte `onset_time` für ALLE Gruppen mit der Zeitzone des ERSTEN Ortes, statt je Gruppe die Koordinaten der eigenen Gruppe zu nutzen (#1385).
- `_peak_occurred_at()` in `weather_change_detection.py` lieferte bereits ein fertiges `"HH:MM"` in Weltzeit zurück — die aufrufende Detektionsschicht kennt keine Ortskoordinaten, kann die Zeitzone also strukturell nicht korrigieren (#1386).

Ein vierter Befund, der die Analyse erst zusammenführte: `to_multi_point_alert_message()` nahm einen `tz`-Parameter entgegen, der **aussah, als regele er die Zeitzone**, tatsächlich aber nirgends benutzt wurde — ein Parameter, der Sicherheit vortäuschte, ohne sie zu liefern.

Zwei Fallen, die beim Fix zutage traten:

1. `ForecastDataPoint.__post_init__` strippt `tzinfo` grundsätzlich (Hausnorm #1345) — Zeitstempel aus Datenpunkten sind IMMER naiv. Ohne expliziten UTC-Guard deutet ein späteres `astimezone()` sie als System-Lokalzeit; auf dem UTC-Produktionsserver zufällig richtig, überall sonst falsch.
2. Bei tz-aware Etappenfenstern warf der Fenstervergleich (naiver Datenpunkt-Zeitstempel gegen aware Segment-Start/-Ende) vorher `TypeError`, `_peak_occurred_at()` fing das in einem breiten `except Exception` ab und lieferte still `None` — der Alarm nannte dann GAR KEINE Zeit, statt einer falschen.

### Fix (Committed 2026-07-25)

- **#1383:** Das Ortsobjekt wird bis zum Versandbaustein durchgereicht; `send_multi_location_radar_alert` leitet die Zeitzone aus den Ortskoordinaten ab (`tz_for_coords`), `ZoneInfo("UTC")` bleibt nur noch letzter Notnagel bei fehlenden Koordinaten.
- **#1385:** `to_multi_location_onset_alert_message` formatiert `onset_time` je Gruppe mit der Zeitzone IHRES Ortes (neuer Helfer `_tz_for_location(loc, fallback_tz)` in `src/output/renderers/alert/project.py`). `stand_at` bleibt bewusst EINE Nachrichtenzeit in der Zeitzone des ersten Ortes (Aussage über die Nachricht, nicht über einen Ort — kein Bug).
- **#1386:** `_peak_occurred_at()` liefert jetzt ein UTC-aware `datetime` statt eines fertigen `"HH:MM"`-Strings; die Formatierung in Ortszeit passiert erst in der Projektionsschicht (`to_alert_message()` über den Segment-Startpunkt, `to_multi_point_alert_message()` über den Ort). Neuer Guard `_as_utc()` deutet naive Zeitstempel explizit als UTC, bevor der Fenstervergleich läuft. `AlertEvent.occurred_at` bleibt `str | None`, die Renderer sind unverändert.

### Files Changed

`src/services/compare_radar_alert.py`, `src/services/notification_service.py`, `src/output/renderers/alert/project.py`, `src/services/weather_change_detection.py` — Details/ACs: `docs/reference/api_contract.md` (WeatherChange-Tabelle), `docs/specs/modules/alert_render_foundation.md`.

### Lessons Learned

1. **Zeitstempel bis zu der Schicht als `datetime` führen, die den Ort kennt.** Wird eine Uhrzeit gebildet, bevor Koordinaten verfügbar sind, ist sie strukturell nicht mehr korrigierbar — egal wie sorgfältig die Formatierung selbst ist. Formatierung in Ortszeit gehört ausschließlich in die Projektionsschicht.
2. **Kein stiller Zeitzonen-Default.** `ZoneInfo("UTC")` als Fallback ohne Log/Warnung sieht in jedem Einzeltest korrekt aus (Tests laufen meist ohnehin in UTC) und liefert erst in Produktion mit echten, nicht-UTC-Orten falsche Werte.
3. **Ein Zeitzonen-Parameter, der nicht benutzt wird, gehört entfernt oder aktiviert.** Der ungenutzte `tz`-Parameter in `to_multi_point_alert_message` täuschte Kontrolle vor, die nicht existierte — ein Reviewer, der die Signatur liest, hätte den Fehler nicht gefunden.
4. **Der Fehler war auf dem UTC-Produktionsserver teilweise unsichtbar**, weil naive Zeitstempel dort per Zufall dieselbe Zeitzone tragen wie das beabsichtigte UTC-Verhalten. Tests unter mehreren System-Zeitzonen (nicht nur UTC) sind der wirksame Nachweis für diese Fehlerklasse — ein grüner Test auf einer UTC-Maschine beweist hier nichts.

---

## BUG-1275-TH-MISMATCH: SMS/Telegram zeigten kein Gewitterrisiko, während E-Mail-Outlook-Tabelle "hoch" zeigte

**Status:** WIEDERERÖFFNET (2026-07-17) — der Fix vom 2026-07-16 behob nur einen von mehreren Defekten, s. „Zweiter Anlauf" unten | **Severity:** Critical (widersprüchliche Sicherheitsaussage zwischen Kanälen im selben Report) | **GitHub Issue:** #1275 | **Specs:** `docs/specs/_archive/bugfix/fix_1275_sms_th_mismatch.md` (1. Anlauf), `docs/specs/_archive/bugfix/fix_1275_sms_thunder_today.md` (2. Anlauf) | **ADR:** `docs/adr/0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md`

### Symptom

Im selben Abend-Trip-Report zeigte die E-Mail-Outlook-Tabelle für die morgige Etappe korrekt "hoch ab 4 Uhr" Gewitterrisiko, während SMS (`TH+:-`), Telegram und der kleine E-Mail-Vorschau-Textblock "kein Gewitter" meldeten — für dieselbe fachliche Aussage.

### Root Cause

Zwei unabhängige, konkurrierende Berechnungen derselben fachlichen Aussage in `trip_report_scheduler.py`: `_build_thunder_forecast()` wurde mit `segment_weather[-1]` aufgerufen — dem letzten Segment der HEUTIGEN Etappe, nicht der tatsächlichen morgigen Etappe — und durchsuchte dessen bereits geladene Zeitreihe ohne TZ-Konvertierung. `_build_stage_trend()` (Quelle der Outlook-Tabelle) machte es dagegen bereits richtig: frischer Fetch der tatsächlichen Folge-Etappe, Aggregation über alle deren Segmente, TZ-korrekt. Liegt das Gewitter-Ereignis an einem anderen Waypoint als dem letzten Segment von heute, wurde es vom SMS/Telegram-Pfad nicht erfasst.

### Fix (Committed 2026-07-16, Workflow `fix-1275-sms-th-mismatch`)

`_build_stage_trend()`s bereits korrekte Fetch-/Aggregations-Kette wird jetzt als primäre Quelle für `thunder_forecast["+1"]`/`["+2"]` wiederverwendet (Reihenfolge in der Aufrufstelle umgekehrt), statt eine zweite, fehlerhafte Berechnung parallel zu betreiben. Kein zusätzlicher API-Call im Evening-Default (Trend läuft ohnehin); nur bei deaktiviertem Trend (Morning) ein extrahierter Fallback-Helper mit eigenem Einzel-Etappen-Fetch. Downstream-Konsumenten (SMS, Telegram, E-Mail-Vorschau) blieben unverändert — sie konsumieren weiterhin denselben Dict-Vertrag.

### Zweiter Anlauf (2026-07-17, Workflow `fix-1275-sms-thunder-today`)

Der Fix vom 2026-07-16 reparierte `thunder_forecast` (die Quelle für `TH+:`) — und war für das gemeldete Symptom auch richtig. Er ließ aber vier weitere, unabhängige Defekte derselben Wurzel stehen. Der Adversary-Lauf des ersten Anlaufs fand sie nicht, weil er gegen die Spec prüfte und die Spec diese Pfade nicht kannte (bzw. im Fall Telegram **falsch** beschrieb).

| # | Defekt | Ort | Stand |
|---|--------|-----|-------|
| 1 | `TH:` (berichtete Etappe) hatte **gar keine Datenanbindung** — `_segments_to_normalized_forecast()` las `dp.thunder_level` nie, `thunder_hourly` blieb leer, `render_threshold_peak_value()` lieferte darum strukturell immer `-`. Unabhängig vom Wetter. | `sms_trip.py:113-165` | behoben |
| 2 | Die Stunde in `TH+:H@12` war **erfunden** — `HourlyValue(12, …)` ist eine Konstante. Die echte Stunde war im Scheduler bereits berechnet, wurde aber nur in einen `text`-String eingebettet, den niemand parst. | `sms_trip.py:227`, `trip_report_scheduler.py:1564,1701` | behoben (`hour` additiv im Dict) |
| 3 | Die **Telegram-Fußzeile** las `agg.thunder_level_max` — ein **ungefenstertes** Tages-Aggregat. Ein Nacht-Gewitter meldete Telegram als HIGH, während SMS/E-Mail zu Recht schwiegen. | `narrow.py:164-216` (`_tg_day_footer`) | behoben |
| 4 | Die **E-Mail-Kopfzeile** (Kompakt-Summary, per Default sichtbar) gated ebenfalls auf `agg.thunder_level_max` und meldete `⚡ möglich` für ein Gewitter, das ausschließlich außerhalb der Wanderzeit liegt. Zusätzlich fensterte sie **exklusiv** am Etappenende, während SMS/E-Mail-Tabelle **inklusiv** fenstern — ein Gewitter zur Ankunftsstunde erschien dadurch in der SMS mit Uhrzeit, in der Kopfzeile gar nicht. | `compact_summary.py:110-131,335-355` | behoben — Tor jetzt `bool(thunder_hours)` (Aggregat wird nirgends mehr gelesen), Fensterung per `is_last` nach dem Vorbild `email/helpers.py:1439-1452`: Grenzstunde zwischen Folge-Segmenten genau 1×, Ankunftsstunde erstmals enthalten. Vom Adversary des zweiten Anlaufs gefunden (F001/F003) und in Runde 3 gegengeprüft |

Nicht betroffen, entgegen der ursprünglichen Analyse: `_overview_line` (`narrow.py:284-326`) liest die bereits gefensterten `seg_tables`-Rows und war nie divergent (Faktenkorrektur im ADR-0025-Changelog).

### Lessons Learned

**1. Kanal-Divergenz-Bugs.** Wenn mehrere Ausgabekanäle dieselbe fachliche Aussage treffen sollen, aber jeweils eine eigene Berechnung dafür haben, divergieren sie garantiert irgendwann — die Abhilfe ist Wiederverwendung der bereits bewährten Quelle statt Parallel-Implementierung, nicht das Nachziehen der fehlerhaften zweiten Implementierung. **Diese Lehre stand am 2026-07-16 hier — und verhinderte denselben Fehler am selben Tag nicht.** Prosa in einem Known-Issues-Dokument bindet niemanden; deshalb ist die Regel jetzt ADR-0025.

**2. Ein Adversary prüft gegen die Spec, nicht gegen die Wirklichkeit.** Beide Anläufe liefen durch Adversary, echte Staging-Testmail und Prod-Selftest. Der erste fand die Defekte 1-4 trotzdem nicht: Die Spec kannte den `TH:`-Pfad nicht und beschrieb den Telegram-Pfad falsch — also konnte keine Prüfung sie widerlegen. Wer eine Kanal-Aussage spezifiziert, muss **am Aufrufbaum** prüfen, welcher Renderer den Wert tatsächlich bekommt.

**3. Grüne Tests über totem Code.** Kein Test schickte je eine echte Zeitreihe mit gesetztem `dp.thunder_level` durch `format_sms()`. Die Golden-Tests (`tests/golden/test_sms_golden.py:63-122`) bauen `DailyForecast(thunder_hourly=…)` **direkt** und überspringen genau die defekte Glue-Schicht. Der Snapshot zeigte seit jeher `TH:M@16(H@18)`, die Produktion lieferte `TH:-`. Ein Test, der eine Zwischenschicht direkt füttert, ist **kein** Nachweis für eine Kanal-Aussage (ADR-0025 Entscheidung 5).

**4. „Vollständig" heißt: alle Konsumenten gezählt.** Defekt 4 überlebte auch den zweiten Anlauf bis in die Adversary-Phase, weil Spec und ADR von *drei* Gewitter-Quellen ausgingen. Es waren *vier*. Vor dem Fix einer geteilten Aussage: `grep` nach **jedem** Konsumenten des Aggregats, nicht nach den erinnerten.

---

## BUG-1269-SAVESTATUS-LIE: Speicher-Status-Anzeige lügt (Trip + Ortsvergleich) + ungegateter Versand-PUT

**Status:** RESOLVED (2026-07-16) | **Severity:** Medium (Vertrauens-Bug + ungewollter Schreibzugriff) | **GitHub Issue:** #1269 | **Spec:** `docs/specs/_archive/modules/issue_1269_save_status_lie.md`

### Symptom

Der Speicher-Status-Chip lügt in zwei Richtungen: (a) bloßes Öffnen eines Tabs ohne jede Eingabe setzt „● Nicht gespeichert" (Trip-Inhalt-Tab; Ortsvergleich-Layout-Tab). (b) Der Chip springt anschließend auf „✓ Gespeichert HH:MM", obwohl kein Speichervorgang zum Server stattfand (nur Ortsvergleich-Editor). Beim Nachbohren zusätzlich (c): Das bloße Öffnen des Trip-Tabs „Versand" konnte einen echten, ungesteuerten `PUT /api/trips/{id}` auslösen — ohne jede Nutzergeste, bei Fehlschlag mit „Fehler beim Speichern"-Banner.

### Root Cause

Gemeinsame Wurzel: Mount-Normalisierung/Hydration (z.B. Zeitformat `"07:00"` → `"07:00:00"`, Materialisierung fehlender Default-Felder) erzeugt einen Diff gegen die Vergleichs-Baseline, der von einer echten Nutzeränderung nicht zu unterscheiden war. Drei Editor-Flächen verwalteten das uneinheitlich: `CompareEditor.svelte` rief bei dirty→clean unbedingt `setSaved()` auf — der einzige PUT-lose `setSaved()`-Aufruf im gesamten Frontend (b). `BriefingScheduleTab.svelte`s reportConfig-Watch-`$effect` rief `saveController.doSave()` ganz ohne Gesten-Gate (c) — genau der „latente Zwilling", den #1234 in seinen Known Limitations bereits benannt, aber bewusst ungefixt gelassen hatte, weil zu dem Zeitpunkt noch kein Autospeichern im Ortsvergleich lief.

### Fix (Committed 2026-07-16, Workflow `fix-1269-save-status-lie`)

Konsolidierung auf die bestehenden geteilten Bausteine, kein vierter Sonderweg:

1. **`SaveStatus.markPristine()`** (neu, `frontend/src/lib/stores/saveStatusStore.svelte.ts`): dirty→idle **ohne** `savedAt` neu zu stempeln. Ersetzt den unbedingten `setSaved()`-Aufruf in `CompareEditor.svelte` — `setSaved()` ist jetzt ausschließlich über `doSave()` nach echtem, erfolgreichem PUT erreichbar (fixt b).
2. **`reportConfigDirty.ts`** (neu, `frontend/src/lib/components/shared/`, Export `reportConfigChangedByUser()`): geteilte, normalisierungsbewusste Diff-Funktion (nutzt `toHHMMSS`) statt rohem Werte-/JSON-Vergleich — neu materialisierte Default-Felder zählen nicht als Änderung, ein aus der Baseline verschwundenes Feld konservativ schon (Robustheits-Invariante: im Zweifel „dirty"). Ersetzt den Diff in `WeatherMetricsTab.svelte` und `BriefingScheduleTab.svelte` (fixt a).
3. **Schreib-Gate auf die dritte Fläche ausgeweitet:** `BriefingScheduleTab.svelte` läuft jetzt durch dasselbe `weatherSaveGate` (`catalogLoaded && userTouched`) wie Trip-Inhalt und Ortsvergleich — das bloße Öffnen des Versand-Tabs kann keinen PUT mehr auslösen (fixt c).

Bewusst **verworfen**: `setDirty` an `userTouched` koppeln (Adversary-Challenge) — hätte bei einer von der Gesten-Erfassung übersehenen Interaktion (F003/F004-Klasse: Slider, Drag) die Anzeige fälschlich auf „gespeichert" gesetzt, während echte Änderungen ungespeichert geblieben wären → stiller Datenverlust. Stattdessen bleibt die Anzeige im Zweifel konservativ „nicht gespeichert" (nie fälschlich „gespeichert"), während das Schreiben im Zweifel unterbleibt (nie ungewollt) — dieselbe asymmetrisch-sichere Regel wie #1234.

### Löst vertagten Befund aus #1234 ein

#1234 (Known Limitations, 2026-07-14) benannte „zwei latente Zwillinge" (`BriefingScheduleTab.svelte`, `shared/VersandTab.svelte`) explizit, fixte sie aber bewusst nicht („kein Datenverlust, höchstens ein überflüssiger Speichervorgang ... sobald dort automatisches Speichern für den Ortsvergleich angeschaltet wird, kommt die Fehlerklasse mit"). #1261 (s.u.) schaltete genau das Autospeichern im Ortsvergleich an. #1269 schließt den Zwilling für den Trip-Versand-Pfad (`BriefingScheduleTab.svelte`).

### Files Changed

- `frontend/src/lib/stores/saveStatusStore.svelte.ts` (+ `markPristine()`)
- `frontend/src/lib/components/shared/reportConfigDirty.ts` (NEU, geteilt Trip + Ortsvergleich)
- `frontend/src/lib/components/compare/CompareEditor.svelte`
- `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte`
- `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte`

### Lessons Learned

1. Mount-/Hydration-Normalisierung (Zeitformat-Kanonisierung, Default-Feld-Materialisierung) ist eine wiederkehrende Fehlerklasse (#1234, #1269) — jede Fläche, die eine Konfiguration beim Laden zurückschreibt, braucht eine normalisierungsbewusste Diff-Funktion statt eines rohen Vergleichs.
2. Anzeige- und Schreib-Mechanik dürfen unterschiedlich konservativ sein: Die Anzeige darf im Zweifel „dirty" bleiben (harmlos), ein Schreibzugriff darf nie ohne Nutzergeste passieren (potenziell schädlich) — dieselbe Asymmetrie wie #1234.
3. Ein in einer Spec dokumentiertes „Known Limitation" mit explizit benanntem Folgerisiko (hier: „latente Zwillinge") ist kein abgeschlossenes Thema, sondern eine vorhergesagte Falle — sie schlägt zu, sobald die Bedingung eintritt (hier: Autospeichern im Ortsvergleich via #1261).

---

## BUG-1261-COMPARE-EDIT: Ortsvergleich nicht editierbar (Desktop) + kein Autospeichern

**Status:** RESOLVED (2026-07-16) | **Severity:** High (Kernfunktion unauffindbar + Datenverlustrisiko bei fehlendem Speichern) | **GitHub Issue:** #1261 | **Spec:** `docs/specs/_archive/modules/issue_1261_compare_edit_autosave.md`

### Symptom

Nutzer fanden auf der Compare-Detailseite (Desktop) keinen Weg mehr, einen bestehenden Ortsvergleich zu bearbeiten. Zusätzlich gingen Änderungen an Orten/Wertebereich/Versand/Layout/Alarmen verloren, wenn nicht explizit auf einen manuellen Speichern-Button geklickt wurde — der Trip-Editor speichert an derselben Stelle längst automatisch.

### Root Cause

1. **Editier-Einstieg vollständig entfernt statt nur umgebaut:** #528 entfernte „Bearbeiten" als Header-Primäraktion der Compare-Detailseite (Desktop), #1256 Scheibe 3 ersetzte den Desktop-⋮-Kebab durch reine Lebenszyklus-Aktionen (aktivieren/pausieren/löschen) ohne „Bearbeiten". Beide Änderungen waren für sich genommen begründet, in Summe verschwand der Desktop-Editier-Einstieg komplett — ohne dass ein Ersatzpfad geprüft wurde. Mobile-Sheet (`compareLifecycleActions`) blieb unberührt und war der einzige verbliebene Weg.
2. **Kein Autospeichern im Compare-Editor:** Der Compare-Editor kannte nur manuelles Speichern über einen Button; der Trip-Editor hatte Autospeichern (debounced, Gesten-Gate #1234) längst produktiv. Die beiden parallelen Editoren liefen damit strukturell auseinander (siehe Trip/Compare-Code-Teilungs-Vorgabe, `CLAUDE.md`).

### Fix (Committed 2026-07-16, Workflow `fix-1261-compare-edit-save`)

(a) Compare-Detailseiten-Header zeigt „Bearbeiten" neben „Test senden" (Trip-Parität); Desktop-⋮-Kebab nutzt neu `compareDetailActions(status)` = Lebenszyklus-Aktionen + „Bearbeiten" (aktiv/pausiert). Mobile-Sheet (`compareLifecycleActions`) und Draft/Setup-Pfad unverändert.
(b) Autospeichern im Compare-Editor: Änderungen an Orten/Wertebereich/Versand/Layout/Alarmen werden debounced (~700 ms) automatisch gespeichert, mit `beforeNavigate`-Flush und dem #1234-Gesten-Gate (kein Schreiben ohne echte Nutzergeste). Neue Bausteine: `compareAutosave.ts` (`computeCompareAutoSaveAction`), additive `SaveStatus.cancel()`. Geteilte Tab-Komponenten (CorridorEditor/VersandTab/AlarmeTab) blieben unverändert (AC-13).

### Strukturelle Lehre für Konvergenz-Epic #1230

Das zentrale Gesten-Gate im Compare-Editor (Ansatz A: eine gemeinsame Debounce-/Gate-Logik, die alle Tab-Interaktionen abdecken muss) erwies sich als fragil gegenüber nicht-standardkonformen Interaktionen. Der Adversary fand vier separate Datenverlust-Fallen, die jeweils eine eigene Selector-/Callback-Erweiterung brauchten: Folge-Edit während laufendem In-Flight-PUT, „Verwerfen" speicherte statt zu verwerfen, Slider-Drag löste das Gate nicht sauber aus, Layout-Drag-Reorder ebenso nicht. Jede Falle war ein eigener Fix-Loop-Zyklus. Robustere Zielarchitektur für #1230: **per-Tab-Save-Wiring (Ansatz B)** — jeder Tab meldet seine eigenen Save-Trigger explizit, statt dass ein zentrales Gate alle Interaktionsarten erraten muss.

## BUG-1257-ALERTVOCAB: Alarm-Regeln bei jedem Speichern gelöscht — zwei Vokabulare, kein Übersetzer

**Status:** RESOLVED (2026-07-15) | **Severity:** High (Datenverlust) | **GitHub Issue:** #1257 | **Spec:** `docs/specs/_archive/modules/bug_1257_alert_metric_mapping.md`

### Symptom

0 von 15 Prod-Trips hatten `alert_rules`. Eine konfigurierte Alarm-Regel wurde bereits beim Anlegen/Speichern vernichtet, war nach dem Neuladen weg.

### Root Cause

Zwei getrennte Namenslisten für dieselben Wettergrößen ohne Übersetzer im Go-Persistenzpfad: Metrik-Katalog (`gust`, `precipitation`, `temperature`, `snowfall_limit`, `thunder`, `freezing_level`) vs. `AlertMetric` (`wind_gust`, `precipitation_sum`, `temperature_min/max`, `snow_line`, `thunder_level`). `ActiveAlertableMetricIDs()` (`internal/model/trip.go`) schlug die Katalog-`metric_id` **roh** in `AlertableMetrics` (Alarm-Vokabular) nach — Schnittmenge leer → immer leere Liste → `SyncAlertRules()` lieferte `[]` und verwarf bestehende Regeln bei **jedem** Save/Load. Die eigentliche Lehre: die Übersetzung zwischen zwei Einheiten wurde nie geprüft — die Naht-Tests (`alert_sync_test.go`, `store_809/817_test.go`, `weather_config_701_test.go`) übergaben durchweg das **Alarm**-Vokabular als display_config und maskierten den Fehler genau an der Naht.

### Fix (Committed 2026-07-15, Workflow `fix-1257-alert-metric-mapping`)

Explizite Vorwärts-Abbildung Katalog-ID → AlertMetric(s) in `internal/model/trip.go` (`catalogIDToAlertMetrics`), definiert als exakte Inverse der bereits existierenden Python-Bridge `_ALERT_METRIC_TO_CATALOG_ID`, gefiltert auf `AlertableMetrics`; `temperature`→{min,max}, `snowfall_limit`+`freezing_level`→{snow_line} (dedup). Die zwei divergenten Go-Pfade wurden zusammengelegt (`extractActiveMetricIDs` entfernt, Handler nutzt `model.ActiveAlertableMetricIDs`). Drift-Schutz: `tests/tdd/test_alert_metric_mapping_parity.py`. Maskierende Naht-Tests auf echte Katalog-IDs korrigiert.

> **Korrektur 2026-07-26 (#1387):** Die frühere Formulierung „prüft Go↔Python-Konsistenz" war zu weit gefasst. Kein Test liest oder führt Go-Quelltext aus; geprüft wurde bis dahin nur Python gegen ein von Hand gespiegeltes Python-Literal (`_ALERTABLE_METRIC_VALUES`). Dass die Go-Kopie ungeprüft bleibt, ist als Sammel-Eintrag in #1199 vermerkt. Es gibt zudem eine **dritte** Kopie derselben Abbildung im Frontend (`ROUTE_CORRIDOR_CATALOG_IDS`, `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts`); dort fehlte `freezing_level`, weshalb „Nullgradgrenze" im Reiter Wertebereiche keinen Schneefallgrenzen-Bereich anbot. Seit #1387 prüft derselbe Test **Frontend↔Python** in beide Richtungen (er parst die TS-Konstante als Daten). Deckungsgrad also: Python↔Frontend testgeprüft, Go weiterhin handgespiegelt. Rückwirkende Materialisierung (PO-Entscheidung) via idempotentem `MigrateAllTripsAlertRules` (`internal/store/migrate_1257.go`, Deploy-Schritt pro Host mit Backup).

### Known Limitations

Der Fix stellt Regeln über Save/Load wieder her (Round-Trip-Integrität) und behebt fälschliches Gate-Ausschließen — er schaltet **keine** neuen Alarme ein. Das eigentliche Alarm-Feuern läuft über den `metric_alert_levels`-Pfad (#809/#817), der `alert_rules.metric` nicht liest und bewusst unangetastet bleibt.

## BUG-1133-TESTDATA: Python-Tests verschmutzten den echten `data/users/`-Baum

**Status:** RESOLVED (2026-07-09) | **Severity:** High | **GitHub Issue:** #1133 | **Spec:** `docs/specs/_archive/modules/issue_1133_testdata_cleanup.md`

### Symptom

Auf Prod lagen 124 von 139 `data/users/`-Verzeichnissen, auf Staging ~152 von 153, als Test-Residuen vor (`e2e-*`, `tdd-*`, `validator-*`, etc.) — kein bewusst angelegter Nutzer.

### Root Cause

`app.loader.get_data_dir()` konstruierte den Daten-Root hart auf `Path("data/users")`, ohne den bereits existierenden `_DATA_ROOT`-Modul-Override (Vorbild: `get_compare_subscriptions_file`) zu respektieren. Jeder pytest-Lauf, der `save_trip()`/`get_trips_dir()` ohne explizites `data_dir=` aufrief, schrieb daher in den echten Baum.

### Fix (Committed 2026-07-09, Workflow `fix-1133-testdata-cleanup`)

`get_data_dir()` respektiert jetzt `_DATA_ROOT` und (als zweite Quelle) `GZ_DATA_DIR`. Neue autouse-Fixture `tests/conftest.py::_isolate_data_root` lenkt `loader._DATA_ROOT` für jeden Test auf ein `tmp_path_factory`-Verzeichnis um (Opt-out via `@pytest.mark.real_data_root`/`@pytest.mark.live`). `scripts/cleanup_1133_testdata.py` räumt bestehende Residuen einmalig auf (Backup + Positivliste + Dry-Run-Default).

### Known Limitations

Mehrere Services konstruieren `Path("data/users/...")` weiterhin relativ statt über `get_data_dir()` (`src/services/trip_alert.py`, `trip_report_scheduler.py`, `user_tier.py`, `alert_daily_limit.py`, `gpx_processing.py`, `src/app/config.py`) — bewusst nicht migriert (LoC-Budget), bleiben strukturell anfällig für dieselbe Fallen-Klasse. Folge-Issue empfohlen, um diese Hardcodes ebenfalls auf `get_data_dir()` umzustellen.

### Adversary-Nachtrag (Fix-Loop, Committed 2026-07-09)

Die erste Implementierung brach 55 zuvor grüne TDD-Tests: Testdateien, die parallel zur `save_trip()`/`get_trips_dir()`-Isolation weiterhin über eine hartkodierte `DATA_ROOT`-Modul-Konstante oder `tmp_path`-relative Pfade lasen/schrieben, liefen an der isolierten Produktions-Auflösung vorbei (Diskrepanz zwischen Test-Schreibpfad und Service-Lesepfad). Root Cause: dieselbe Klasse Fehler wie oben, nur in den TESTS selbst statt in Produktionscode. Betroffene Testdateien wurden auf dynamische `get_trips_dir()`/`get_snapshots_dir()`/`get_data_dir()`-Auflösung zur Laufzeit migriert statt die Isolation aufzuweichen; Tests, die bewusst committete Fixture-Daten aus `data/users/default/` lesen, erhielten `@pytest.mark.real_data_root`.

## BUG-1066-STORE-WRITE: Trip-Speichern schlägt still fehl bei Group-ACL-Entzug

**Status:** RESOLVED (2026-07-08) | **Severity:** High | **GitHub Issue:** #1066 | **Spec:** `docs/specs/_archive/modules/fix_1066_store_write_logging.md`

### Symptom

Trip-Speichern (HTTP PATCH/POST auf `/api/trips/{id}`) antwortete mit HTTP 500 `{"error":"store_error"}` ohne weitere Details. Der Store-Layer loggte **nichts**, sodass der Root Cause mehrere Tage unentdeckt blieb.

### Root Cause

Ein Security-Audit-Skript (`henemm-security`, externe Instanz) restriktivierte ACLs auf `data/`: `group::r-x` (kein Write). Der API-Prozess (`gregor-api`, Systemuser `claude-gregor`) griff über die Gruppe auf Dateien zu. `os.WriteFile()` auf bereits existierende Dateien schlug mit Permission Denied fehl — dieser echte OS-Fehler verschwand stumm in generische `store_error`-Message.

### Sofort-Fix (Live 2026-07-07)

Berechtigungen wiederhergestellt:
```bash
setfacl -R -m g::rwX,m::rwx /home/hem/gregor_zwanzig/data/
setfacl -R -dm g::rwX,m::rwx /home/hem/gregor_zwanzig/data/
```

### Diagnostik-Fix (Workflow fix-1066-store-write-logging, Committed 2026-07-08)

Neuer Helper `internal/store/write.go::writeFileLogged()` loggt jeden Schreibfehler mit Pfad + Ursache via `log.Printf()`. Alle 8 `os.WriteFile()`-Aufrufe im Store laufen darüber. HTTP-Response bleibt `store_error` (keine Pfad-Exposition), aber Logs enthüllen echte Fehlerursachen (Permissions, Disk, i/o).

### Files Changed

- `internal/store/write.go` (NEU, +19 LoC, zentraler Write-Helper mit Logging)
- 8× `os.WriteFile` → `writeFileLogged` in 7 Store-Dateien: `trip.go`, `user.go` (2×), `group.go`, `subscription.go`, `compare_preset.go`, `location.go`, `metric_preset.go`
- Tests (NEU): `internal/store/store_write_logging_test.go` (AC-1..3), `internal/handler/trip_state_write_error_test.go` (AC-4)

### Lessons Learned

1. **Generic Error-Wrapping versteckt Diagnostik** — `store_error` ohne Context ist unbenutzbar für Betrieb
2. **OS-Fehler bei Datei-Ops brauchen strukturiertes Logging** — erst dann offenbaren sich ACL-/Permission-Probleme
3. **Externe Security-Audits können ACLs ändern** — Store-Schreib-Selftest (#1120, Follow-up) muss Überwachung übernehmen

---

## FOLLOWUP-1120: Aktiver Schreib-Selftest für data/ (Gegenmaßnahme zu #1066)

**Status:** RESOLVED (2026-07-08) | **Severity:** Medium | **GitHub Issue:** #1120 | **Spec:** `docs/specs/_archive/modules/fix_1120_write_selftest.md`

### Kontext

#1066 blieb tagelang unbemerkt, weil es keinen aktiven Schreib-Check für `data/` gab — nur
Lesezugriff (`/api/health`). Dieser Fix schließt die Monitoring-Lücke direkt an der Quelle: dem
Go-Scheduler-Prozess (`gregor-api`, User `claude-gregor`), der bei #1066 tatsächlich versagte.

### Fix

Neuer periodischer Job `data_write_selftest` (`*/15 * * * *`) in `internal/scheduler/scheduler.go`.
`probeDataWritable()` (neu, `internal/scheduler/selftest.go`) traversiert error-geprüft per
`os.ReadDir` (`users/` → `users/<id>/trips/` → `*.json`) die vorhandenen Trip-Dateien und öffnet
jede mit `os.OpenFile(path, os.O_WRONLY, 0)` gefolgt von sofortigem `Close()` — non-destruktiv
(kein `O_TRUNC`/`O_CREATE`), aber kernelseitig dieselbe Schreibberechtigung wie der reale
`os.WriteFile`-Pfad, reproduziert damit das #1066-EACCES identisch. **Bewusst kein
`filepath.Glob`** (F001, im Adversary-Review gefunden): Glob verschluckt Verzeichnis-Lesefehler
still → ein nicht mehr traversierbares `trips/`-Verzeichnis (Variante des `setfacl -R`-Sweeps)
ergäbe fälschlich `ok`. Die Traversierung wertet jeden Lesefehler ≠ `fs.ErrNotExist` als Fehler. Status landet automatisch unter `/api/scheduler/status` (`recordRun`-Muster). Edge-
getriggertes Alerting (kein `sync.Once`, damit ein späterer Re-Onset nicht verschluckt wird):
Übergang `ok→error` löst genau eine MQ-Nachricht an `infra` (Priorität `high`) aus, `error→ok`
optional eine Recovery-Notiz (Priorität `normal`). Kein neuer BetterStack-Heartbeat (Quota
erschöpft).

### Files Changed

- `internal/scheduler/selftest.go` (NEU) — `probeDataWritable(dataDir string) error`
- `internal/scheduler/scheduler.go` — neuer Job-Eintrag + `dataWriteSelftest()`
- Tests (NEU): `internal/scheduler/selftest_test.go`, `internal/scheduler/data_write_selftest_test.go`

### Lessons Learned

1. Reine Lesezugriffs-Health-Checks (`/api/health`) decken Schreib-Regressionen strukturell nicht ab
2. Non-destruktive `O_WRONLY`-Probes reichen aus, um dieselbe Kernel-Permission-Prüfung wie der
   reale Schreibpfad auszulösen, ohne Daten zu verändern
3. Edge-getriggertes Alerting (Statuswechsel statt `sync.Once`) verhindert sowohl Alert-Flapping
   als auch verschluckte Re-Onsets bei langlebigen Prozessen
4. `filepath.Glob` verschluckt Verzeichnis-Lesefehler still (Go-Doku: nur `ErrBadPattern`) — für
   Berechtigungs-Wächter ungeeignet; error-geprüfte `os.ReadDir`-Traversierung nötig (Adversary-
   Finding F001)

---

## BUG-774: Metriken-Überblick-Checkbox persistiert nicht

**Status:** RESOLVED (2026-06-12) | **Severity:** Medium | **GitHub Issue:** #774 | **Spec:** `docs/specs/_archive/bugfix/issue_774_metrics_summary_persist.md`

### Symptom

Im Metriken-Reiter eines Trips wurde die Checkbox „Metriken-Überblick" (`report_config.show_metrics_summary`) nicht gespeichert. Nach dem Speichern war die Checkbox beim Reload wieder deaktiviert, obwohl der Nutzer sie aktiviert hatte. Der Speichern-Button blieb auch bei reinen Checkbox-Änderungen deaktiviert.

### Root Cause

Zwei Probleme:

1. **Dirty-Tracking:** `isDirty` (Z.135) in `WeatherMetricsTab.svelte` und `snapshot()` (Z.139) berücksichtigten das `reportConfig`-Objekt nicht — eine Änderung an den Inhalts-Checkboxen markierte den Tab nicht als dirty, wodurch der Speichern-Button deaktiviert blieb.

2. **Persistenz:** `handleSave()` sendete nur `display_config` via `PUT /api/trips/{id}/weather-config`, niemals das in `reportConfig` gepflegte `report_config`-Objekt.

### Fix (Committed 2026-06-12)

**WeatherMetricsTab.svelte:**
- `isDirty` (Z.135) um Vergleich von `reportConfig` erweitert
- `snapshot()` (Z.139) speichert nun auch `reportConfig` als Teil des Snapshots
- `handleSave()` (Z.363) um zweiten PUT-Call ergänzt: `await api.put(/api/trips/{id}, { report_config: reportConfig })` (Merge via Go-Backend Issue #99)
- `handleDiscard()` restauriert nun auch `reportConfig` aus dem gespeicherten Snapshot

**EditReportConfigSection.svelte:**
- Einklapp-Toggle `report-content-modules-toggle` entfernt
- `contentModulesExpanded`-Block aufgelöst — die drei Inhalts-Checkboxen sind jetzt direkt sichtbar ohne Collapse
- `ChevronDown`-Import und ungenutzter State entfernt

### Files Changed

- `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` (+35 LoC)
- `frontend/src/lib/components/edit/EditReportConfigSection.svelte` (-12 LoC)

### Lessons Learned

1. **Dirty-Tracking:** Mehrerer State-Objekte (`displayConfig`, `reportConfig`) müssen alle in `isDirty` und `snapshot()` erfasst sein — ein fehlender Vergleich deaktiviert Speichern.
2. **Partial Persistence:** Der Trip-Editor spricht zwei verschiedene Endpoints an (`weather-config` für Display-Metriken, `/api/trips/{id}` für Report-Config). Beide müssen im Save-Handler aufgerufen werden.
3. **UI-Redundanz:** Einklapp-Elemente, die keine Raumersparnis bringen, erschweren das UX. Direktes Rendering der Inhalte ist klarer.

---

## BUG-730-INVALIDURL: prod_selftest.py crasht bei nicht-probearen URLs

**Status:** RESOLVED (2026-06-11) | **Severity:** Low | **GitHub Issue:** #730 | **Spec:** `docs/specs/_archive/modules/bug_730_prod_selftest_invalidurl.md`

### Symptom

`prod_selftest.py` (Post-Deploy-Selbsttest, Issue #564) crashte mit `http.client.InvalidURL`-Exception, wenn ein E2E-Attestation-Finding eine nicht-probebare URL trug (Freitext mit Leerzeichen/Steuerzeichen, z.B. Backend-AC-Beschreibung `/api/trips/{id} PUT/GET`). Das Crash-Exception-Traceback blockierte Issue-Close (Exit 1), obwohl der Deploy erfolgreich war.

### Root Cause

Staging-Validator (`staging_validator.py`) schreibt E2E-Attestation-Findings mit `url`-Feld. Für Backend-Only-ACs oder beschreibende Findings (keine echte probeable HTTP-Route) nutzt der Validator Freitext als URL-Marker.

`prod_selftest.py` in Funktion `_probe_ac` (Z. 114–141) versuchte, alle Findings per HTTP-GET zu proben:
```python
prod_url = _staging_to_prod_url(raw_url)
status, _ = _http_get(prod_url, ...)  # urllib.InvalidURL wenn prod_url Leerzeichen trägt
```

`urllib.request.Request()` wirft `http.client.InvalidURL` bei disallowed characters `[\x00-\x20\x7f]` (Space, Newline, etc.) — aber der `except (urllib.error.URLError, OSError)` in `_probe_ac` fing diesen Fehler **nicht** (es ist kein Subtyp von URLError oder OSError, sondern `HTTPException`). Exception propagierte → ThreadPoolExecutor re-raised → Script-Exit 1.

### Fix (Committed 2026-06-11)

**Zwei Schutzschichten:**

1. **Präventiv:** Neuer Helper `_is_probeable_url(url: str) → bool` (Z. 120–133) — prüft vor HTTP-Probe ob die URL gefahrlos probebar ist. Mirror von `http.client`-Disallowed-Chars-Regex. Gibt False bei Leerzeichen/Steuerzeichen ODER wenn parsed-URL kein gültiges `http(s)://host/path`-Format hat.

2. **Defense-in-Depth:** Exception-Handler in `_probe_ac` (Z. 176) erweitert um `http.client.InvalidURL` und `ValueError` (auch `urllib.parse.urlparse` wirft ValueError bei bestimmten Eingaben).

**Verdict-Semantik:** Nicht-probebare Findings bekommen `prod_status="SKIPPED_NO_URL"` — dies zählt **nicht** als FAIL oder PARTIAL, sondern wird transparent als übersprungenes Finding geführt (ähnlich wie `ATTESTED_SKIPPED`).

```python
if not _is_probeable_url(prod_url):
    return {
        **finding,
        "prod_url": prod_url,
        "prod_http": "—",
        "prod_status": "SKIPPED_NO_URL",
    }
```

### Files Changed

- `.claude/hooks/prod_selftest.py` (+25 LoC)

### Lessons Learned

1. **Staging-Attestation-URLs sind teils Freitext**, nicht immer echte HTTP-Pfade — Prod-Selftest muss idempotent damit umgehen
2. **Exception-Typen:** `http.client.InvalidURL` ist Subtyp von `HTTPException`, nicht `URLError` — Defense-in-Depth im except erforderlich
3. **SKIPPED_NO_URL** ergänzt die Verdict-Semantik ohne Regressions: nicht-probebare PASS-Findings führen nicht zu Verdikt-Verschlechterung (vgl. Issue #564 AC-2)

---

## BUG-1084-STALE-MARKER: prod_selftest.py übersprang sich still bei stale Gate-Marker

**Status:** RESOLVED (2026-07-07) | **Severity:** Medium | **GitHub Issue:** #1084 | **Spec:** `docs/specs/_archive/modules/issue_1084_gate_scope_cache.md`

### Symptom

Lief `prod_selftest.py` (Post-Deploy-Schritt 4b) unmittelbar nach einem erfolgreichen `staging_gate.py --check`-Lauf (Schritt 4) im selben Repo-Zustand, überprang sich die Post-Deploy-Verifikation still, obwohl echter Code deployt wurde (beobachtet bei der #1080-Deploy-Pipeline).

### Root Cause

Beide Skripte spiegeln ihre Scope-Erkennung über denselben Marker (`.claude/last_gate_scope.json`, eingeführt durch #916). `staging_gate.py` hatte den Marker gerade selbst auf HEAD gesetzt; `prod_selftest.py`s eigene `_detect_committed_scope()` diffte daraufhin `git diff HEAD..HEAD` (leer) gegen denselben, jetzt bereits aktuellen Marker und leitete fälschlich `docs-only` her.

### Fix (Committed 2026-07-07)

Scope-Cache im Marker selbst: `write_last_gate_scope()` speichert zusätzlich den bereits berechneten Scope-Wert (`gate_last_scope`); `prod_selftest.py::_detect_committed_scope()` nutzt diesen gecachten Wert bei exakter Commit-Übereinstimmung mit dem Marker, statt ihn selbstreferenziell neu herzuleiten. Ein naiver `HEAD~1`-Fallback wurde bewusst verworfen — er hätte den ursprünglichen Multi-Commit-Bug #916 wieder eingeschleppt.

### Files Changed

- `.claude/hooks/_e2e_paths.py`, `.claude/hooks/staging_gate.py`, `.claude/hooks/prod_selftest.py`, `tests/tdd/test_issue_1084_gate_scope_cache.py`

### Lessons Learned

1. **Gespiegelte Scope-Erkennung über zwei Prozesse ist selbstreferenz-anfällig**, wenn ein Prozess den Marker gerade erst auf den aktuellen Zustand geschrieben hat, den der zweite Prozess dann als "Diff-Basis" liest.
2. **Cache statt Neuberechnung** ist hier robuster als ein naiver Zeit-/Commit-Fallback, der bereits gefixte Bugs (#916) wieder einschleppen würde.

---

## BUG-1096-SELFPOISON: staging_gate.py vergiftete eigenen Scope-Marker bei Doppel-Lauf

**Status:** RESOLVED (2026-07-08) | **Severity:** High | **GitHub Issue:** #1096 | **Spec:** `docs/specs/_archive/modules/issue_1096_gate_scope_selfpoison.md`

### Symptom

Lief `staging_gate.py --check` ein zweites Mal auf demselben, bereits geprüften HEAD, stufte es echte Code-Deploys fälschlich auf `docs-only` herab — beobachtet bei den Deploys #1097 (Commit `3f5d3cfa`) und #1104 (Commit `b4620e97`). Der falsche Marker-Wert wurde dann von `prod_selftest.py`s eigenem Cache-Guard (#1084) als korrekt übernommen, wodurch der Post-Deploy-Selftest den echten Code-Deploy stillschweigend übersprang.

### Root Cause

#1084 hatte den Scope-Cache im Marker (`.claude/last_gate_scope.json`) nur auf der Leseseite (`prod_selftest.py`) eingeführt — die Schreibseite (`staging_gate.py::_detect_committed_scope()`) blieb ungeschützt. Ein zweiter `gate_check()`-Lauf auf demselben HEAD berechnete den Scope selbstreferenziell über `git diff HEAD..HEAD` (leer) neu, statt den beim ersten Lauf bereits korrekt ermittelten Wert zu nutzen — leitete daraus fälschlich `docs-only` her und überschrieb damit den vorher richtigen Marker-Eintrag. Asymmetrischer Cache-Guard aus #1084: nur die Leseseite war abgesichert, die Schreibseite nicht.

### Fix (Committed 2026-07-08)

Shared-Cache-Helper `_e2e_paths.cached_scope_for_sha(repo_dir, sha)` wird jetzt von **beiden** Gate-Skripten symmetrisch genutzt (`staging_gate.py` UND `prod_selftest.py`, vorher nur letzteres). Der docs-only-Skip-Zweig in `gate_check()` überschreibt keinen bestehenden Nicht-docs-only-Cache-Eintrag für dieselbe SHA mehr. Zusätzlich `TestGateCheckModeB` (`tests/tdd/test_staging_gate.py`) auf hermetische Temp-Git-Repos umgestellt — die Tests liefen vorher gegen das echte, bewegliche Hauptrepo und wurden instabil, sobald dessen Scope zufällig `docs-only` stand.

### Files Changed

- `.claude/hooks/_e2e_paths.py` (neu: `cached_scope_for_sha`)
- `.claude/hooks/staging_gate.py` (Cache-Guard in `_detect_committed_scope`, Härtung docs-only-Skip)
- `.claude/hooks/prod_selftest.py` (Duplikat-Logik durch Shared-Helper ersetzt, HEAD~1-Fallback)
- `tests/tdd/test_staging_gate.py` (`TestGateCheckModeB` hermetisiert)
- `tests/tdd/test_issue_1096_gate_scope_selfpoison.py` (neu)

### Lessons Learned

1. **Cache-Mechanismen brauchen symmetrische Guards auf Schreib- UND Leseseite** — ein Fix, der nur eine Seite absichert (#1084 nur `prod_selftest.py`), verlagert die Selbstreferenz-Anfälligkeit lediglich auf die andere Seite.
2. **Tests gegen das echte, bewegliche Hauptrepo sind nicht hermetisch** — `TestGateCheckModeB` lief ohne `--scope`-Override gegen den tatsächlichen Repo-Zustand und wurde flaky, sobald dessen Scope zufällig auf `docs-only` stand.
3. **Follow-ups:** Doppel-Lauf-Ursache (warum `gate_check()` beim #1097-Deploy überhaupt zweimal auf demselben Commit lief) → Issue #1119. Verbleibender Adversary-Finding F003 → Issue #1121.

---

## BUG-DATALOSS-GR221: 4 → 1 Stage Konsolidierung (GR221 Mallorca)

**Status:** RESOLVED — Recovery (2026-04-29) | **Severity:** High | **GitHub Issue:** #102

### Symptom

User wanderte den GR221 Ende Februar 2026 über **4 Etappen** (23.–26.02.) und erhielt während der Wanderung täglich Trip-Reports von Gregor Zwanzig. Bei einer späteren Sichtung des Trip-Files war nur noch **1 Stage** ("Tag 1: von Valldemossa nach Deià") vorhanden.

### Forensik

**Git-Spurenlage:**
- `data/users/default/trips/gr221-mallorca.json` taucht erstmalig in Git auf in Commit `51abdad` (2026-04-16) — bereits mit nur 1 Stage
- Vor diesem Commit lebte die Datei rein lokal außerhalb von Git (`data/` wurde erst durch `392ecc0` am 2026-02-11 versioniert, gr221-mallorca war zu dem Zeitpunkt nicht dabei)
- Stash `3f60e9c` (2026-04-29 pre-deploy) enthält ebenfalls nur 1 Stage — der Verlust passierte VOR dem Stash
- **Aber:** Im Stash liegen 4 GPX-Dateien (`Tag 1` bis `Tag 4`) untracked → die GPX-Daten überlebten, nur das aggregierte Trip-JSON war geschrumpft

**Vermutlicher Tatort:** `BUG-03/04` Pattern (gefixt am 2026-02-17 in `8de1a78`):

```python
updated_trip = Trip(
    id=trip_id,
    name=name_input.value,
    stages=stages,         # aus aktuellem UI-State neu gebaut
    avalanche_regions=regions,
)
save_trip(updated_trip)    # überschreibt persistierte Datei
```

Trip-Edit baute neues Trip-Objekt aus dem UI-Form-State, ohne Persistenz-Felder zu erhalten. Wenn das Frontend zu irgendeinem Zeitpunkt nach der Wanderung nur 1 Stage zeigte (z.B. beim Laden eines korrupten oder älteren Zustands) und der User editierte, wurden die anderen Stages überschrieben. `8de1a78` fixte zwar `display_config`/`weather_config`/`report_config`, aber die `stages` selbst wurden weiterhin aus `stages_data` (UI-State) ohne Backend-Merge neu gebaut.

**Limitation der Forensik:** Da die 4-Stage-Version nie comittet war, lässt sich der exakte Konsolidierungs-Commit nicht eindeutig identifizieren. Plausibles Zeitfenster: zwischen Wanderungs-Ende (2026-02-26) und erstem Commit (2026-04-16).

### Recovery

- 4 GPX-Dateien aus Stash `3f60e9c` extrahiert nach `data/users/default/gpx/`
- `gr221-mallorca.json` rekonstruiert: 4 Stages × 4 Waypoints (G1=Start, G2/G3=Zwischenpunkte, G4=Ziel), Datumssequenz 2026-02-23 bis 2026-02-26, Höhen aus GPX-Tracks
- `aggregation.profile=wintersport` und vollständige `report_config` aus Pre-Recovery-Zustand erhalten
- Frontend-Sichtbarkeit verifiziert (`/trips`, `/trips/gr221-mallorca/edit`)

### Lessons Learned

1. **Daten ohne Versionierung sind verloren, sobald sie modifiziert werden** — `data/` gehört von Anfang an in Git (oder zumindest in regelmäßige Backups mit History)
2. **Edit-Handler dürfen niemals Felder fallen lassen, die das UI nicht kennt** — Backend muss Merge statt Replace machen, oder der Client muss Read-Modify-Write korrekt umsetzen
3. **Schema-/Refactor-Reworks brauchen Pre/Post-Snapshot-Tests** — vor jeder Daten-Migration muss eine Roundtrip-Verifikation stattfinden

### Follow-up

- **Issue #99** (Backend Defense-in-Depth): `UpdateTripHandler` macht weiterhin `Replace` statt `Merge` — gleiches Bug-Pattern auf Go-Seite
- **Issue #102 Sub-Task 3** (Migrations-Hygiene): Pre-Rework-Backup-Hook in CLAUDE.md / settings.json
- **Issue #1159** (2026-07-15, RESOLVED): Blind-Replace-Klasse strukturell geschlossen — gemeinsamer `mergeConfigMap`-Helfer (`internal/handler/config_merge.go`) fuer alle Config-PUT-Endpoints (Trip, Location, ComparePreset) + table-driven Struktur-Test darueber. Keine verbliebene `.DisplayConfig = <body>`-Blind-Stelle mehr.

### Files Changed (Recovery)

`data/users/default/trips/gr221-mallorca.json`, `data/users/default/gpx/2026-01-17_*_Tag {1..4}_*.gpx`

---

## BUG-SNAP-01: Snapshot Coordinates Missing — Alert Calls Sent to (0.0, 0.0)

**Status:** RESOLVED (2026-04-12) | **Severity:** High | **Spec:** `docs/specs/bugfix/snapshot_missing_coordinates.md`

### Symptom

Alert checks called Open-Meteo with `lat=0.0, lon=0.0` (Gulf of Guinea) instead of actual trip coordinates. The trip report formatter also crashed with `TypeError: int() argument must be ... not 'NoneType'` when elevation_m was None.

### Root Cause

`weather_snapshot.py save()` only stored `segment_id`, `start_time`, `end_time` — no coordinates. On load, `_reconstruct_segment()` created `GPXPoint(lat=0.0, lon=0.0)` as placeholder. `trip_report.py` called `int(seg.start_point.elevation_m)` without a None guard.

### Fix

- `save()` now writes `start_lat`, `start_lon`, `start_elevation_m`, `end_lat`, `end_lon`, `end_elevation_m` per segment
- `_reconstruct_segment()` reads these fields with `.get(..., 0.0)` fallback (backwards compatible)
- `trip_report.py` replaced all 7 `int(elevation_m)` calls with `int(elevation_m or 0)`

### Files Changed

`src/services/weather_snapshot.py`, `src/formatters/trip_report.py`, `tests/tdd/test_snapshot_coordinates.py`

---

## BUG-IMAP-01: IMAP Reader Used SMTP Credentials

**Status:** RESOLVED (2026-04-12) | **Severity:** Medium

### Symptom

`InboundEmailReader` failed to authenticate against IMAP because it passed `smtp_user`/`smtp_pass` from config instead of the dedicated IMAP credentials.

### Root Cause

`src/services/inbound_email_reader.py` read `settings.smtp_user` and `settings.smtp_pass` for the IMAP login. SMTP and IMAP use separate accounts/credentials.

### Fix

`inbound_email_reader.py` now reads `settings.imap_user` / `settings.imap_pass`. `src/app/config.py` and `src/web/scheduler.py` updated accordingly.

### Files Changed

`src/app/config.py`, `src/services/inbound_email_reader.py`, `src/web/scheduler.py`

---

## BUG-TZ-01: Timezone Mismatch — All Trip Report Times in UTC

**GitHub Issue:** #21 (geschlossen) | **Status:** Erledigt (2026-07-26) — 5 Symptome behoben, 1 Symptom (Daylight-Banner) durch Feature-Entfall gegenstandslos, NICHT gefixt | **Severity:** High | **Date:** 2026-03-03

### Symptom

All timestamps in trip reports display in UTC instead of local time for the trip location:

- **Daylight Banner ("Ohne Stirnlampe"):** Shows 06:13 for Soller (Mallorca) instead of 07:13 (CET = UTC+1)
- **Hourly Weather Table:** All times 1h early (UTC instead of CET+1)
- **Thunder Highlights:** Times formatted as UTC
- **Wind Peak Labels:** Formatted as UTC
- **Compact Summary:** Peak times referenced in UTC
- **SMS Trip Formatter:** Start times in UTC

### Root Cause (Summary)

Multi-point failure across 5 files:
1. `src/services/daylight_service.py` — astral hardcoded to UTC
2. `src/providers/openmeteo.py` — API requests `"timezone": "UTC"`
3. `src/formatters/trip_report.py` — direct `.hour` on UTC datetimes
4. `src/formatters/compact_summary.py` — direct `.hour` on UTC
5. `src/formatters/sms_trip.py` — `.strftime()` on UTC

### Fix Strategy

Wird moeglicherweise durch Tech-Stack-Migration (M2, #23) direkt geloest.
Falls vorher gefixt: `timezonefinder` + `TimezoneService` + Formatter-Anpassungen.

### Nachtrag 2026-07-26 — Status-Prüfung (#1198)

GitHub-Issue #21 ist geschlossen — GitHub Issues ist laut CLAUDE.md die
Single Source of Truth für offene Arbeit, ein `Confirmed` hier daneben wäre
selbst der Doku-Widerspruch, den #1198 sammelt. Am Code belegt: 5 der 6
gemeldeten Symptome rechnen heute nachweislich in Ortszeit (s. u.). Das
sechste (Daylight-Banner) ist **nicht behoben, sondern entfallen** — das
Feature existiert seit #1224 nicht mehr (s. u.). PO-Entscheidung
(2026-07-26): Status auf **Erledigt** gesetzt, mit dieser Unterscheidung
Fix vs. Feature-Entfall ausdrücklich in der Statuszeile.

**Verifiziert als in Ortszeit rechnend** (echter, durchgängiger Aufrufpfad
von realen Ortskoordinaten bis zur Formatierung):
- **Hourly Weather Table:** `TripReportFormatter._tz` (`src/output/renderers/trip_report.py:120`)
  wird aus `tz=trip_tz` gesetzt; `trip_tz` kommt aus `tz_for_coords(...)`
  (`src/services/trip_report_scheduler.py:755`). Stundenwert je Zeile über
  `local_hour(dp.ts, self._tz)` (`trip_report.py:471`).
- **Thunder Highlights:** `local_fmt(dp.ts, self._tz)` (`trip_report.py:558`)
  sowie `local_hour(dp.ts, self._tz)` in `compact_summary.py:318,330,451` —
  gleicher `self._tz`-Kanal.
- **Wind Peak Labels:** `local_fmt(max_gust_ts, self._tz)` (`trip_report.py:579`),
  `local_fmt(max_wind_ts, self._tz)` (`trip_report.py:616`).
- **Compact Summary:** Peak-Stunde über `local_hour(dp.ts, self._tz)`
  (`compact_summary.py:431`), `self._tz` gesetzt aus demselben `tz`-Parameter
  (`compact_summary.py:129`), von `trip_report.py:774` mit `self._tz` (also
  `trip_tz`) aufgerufen.
- **SMS Trip Formatter:** `SMSTripFormatter().format_sms(..., tz=self._tz, ...)`
  (`trip_report.py:267`), Start-Uhrzeit über `local_fmt(seg_data.segment.start_time, tz, "%Hh")`
  (`sms_trip.py:434`) — derselbe `trip_tz`-Kanal.

**NICHT verifizierbar — Feature existiert nicht mehr:** Der **Daylight-Banner
("Ohne Stirnlampe")** wurde ersatzlos entfernt (`show_daylight` seit #790
render-wirkungslos, das Feld selbst seit #1224 ganz aus `TripReportConfig`
gestrichen — Beleg: `src/services/report_config_resolver.py:25-28,86-88`,
`src/app/models.py:765-766`). `src/services/daylight_service.py` (im
Original-Root-Cause referenziert) existiert nicht mehr, `astral` wird im
gesamten `src/`-Baum nicht mehr importiert. Ob der Banner „heute in Ortszeit
rechnet" lässt sich damit nicht belegen — er rechnet gar nicht mehr, weil es
ihn nicht mehr gibt. Das ist wahrscheinlich der Grund, warum #21 geschlossen
wurde, aber es ist keine Bestätigung des ursprünglich gemeldeten
Zeitzonen-Verhaltens.

**Root-Cause-Item 2 (`"timezone": "UTC"` in `openmeteo.py`) ist heute kein
Bug mehr, sondern die etablierte Architektur:** Der Provider liefert bewusst
naive UTC-Rohdaten (Hausnorm #1345), jede Umrechnung in Ortszeit passiert
downstream über `local_hour`/`local_fmt` mit echter, koordinatenbasierter
`tz` — s. oben.

**Bezug zu BUG-1383-1385-1386-ALERT-TZ:** Die fünf oben verifizierten
Trip-Report-Pfade sind nicht derselbe Code wie die drei 2026-07-25 gefixten
Alert-Mail-Pfade (Radaralarm, Mehr-Orte-Bündel, Abweichungs-Alarm) — beide
Fehlerfamilien teilen aber dasselbe Muster (zu früh gebildeter String / kein
Ortsbezug beim Erzeugen des Zeitstempels). #1383/#1385/#1386 sind eine
spätere Wiederkehr derselben Fehlerklasse in einem anderen Renderpfad, kein
Regress der hier verifizierten Trip-Report-Pfade.

---

## BUG-TEST-554: test_env_playwright_vorhanden mit Hard Assert (fehlende Credentials)

**Status:** RESOLVED (2026-06-02) | **Severity:** Low | **GitHub Issue:** #554

### Symptom

`test_env_playwright_vorhanden` schlägt dauerhaft fehl mit `AssertionError: .env.playwright fehlt` — die Datei liegt absichtlich nicht im Repo (enthält Credentials).

### Root Cause

Test nutzte `assert env.exists()` statt `pytest.skip()`. Die Datei wird in Staging injiziert, ist aber in lokalen Test-Läufen nicht vorhanden. Ein fehlgeschlagener Test blockt die Testsuite unnötig.

### Fix (Committed 2026-06-02)

```python
def test_env_playwright_vorhanden():
    """Voraussetzung: Staging-Credentials-Datei vorhanden."""
    env = REPO_ROOT / "frontend/.env.playwright"
    if not env.exists():
        pytest.skip(".env.playwright fehlt — E2E-Screenshot-Tests übersprungen")
    content = env.read_text()
    assert "E2E_USER" in content
    assert "E2E_PASS" in content
```

Test wird jetzt mit Status `SKIPPED` übersprungen, wenn `.env.playwright` fehlt.

### Files Changed

`tests/tdd/test_epic_404_phase2_ist_screenshots.py`

---

## BUG-TEST-556: Sidebar-Test-Drift (bereits behoben)

**Status:** RESOLVED (2026-06-02) | **Severity:** Low | **GitHub Issue:** #556

### Symptom

`test_sidebar_uses_trips_label` prüfte auf Literal-String statt Config-Array. War bereits durch Sidebar-Migration (#386) gelöst, aber Issue nicht geschlossen.

### Root Cause

Commit `a871fd6` (2026-06-02) hatte Sidebar-Config mit `'Meine Touren'`-Array aktualisiert; Test passte automatisch an. Issue #556 war damit erledig, aber nicht geschlossen.

### Resolution

GitHub Issue #556 manuell geschlossen — kein Code-Fix erforderlich.

---

## BUG-594-598: Test-Briefing-Feedback & Archivieren-Dialog

**Status:** RESOLVED (2026-06-04) | **Severity:** Low | **GitHub Issues:** #594, #598

### Symptom

**#594:** Der Button „Test-Briefing senden" auf der Trip-Detailseite zeigte eine Erfolgs- oder Fehlermeldung mit `color: var(--g-ink-muted)` — zu niedrig kontrastiert (WCAG-Verstoß), Nutzer erkannte nicht ob Versand funktioniert.

**#598:** Der Button „Archivieren" in der Trips-Liste führte die Aktion sofort aus. Keine Bestätigung wie beim Löschen — Nutzer konnte versehentlich archivieren.

### Root Cause

- **#594:** CSS-Styling der `.briefing-msg` nutzte durchgehend muted-Ink statt kontrastierter Farbe
- **#598:** `handlePrimaryAction()` für Archivieren hatte kein ConfirmDialog wie das Delete-Pattern

### Fix (Committed 2026-06-04)

**#594 — `TripHeader.svelte`:**
- `testBriefingKind: 'success' | 'error' | null` State hinzugefügt
- CSS: `kind='success'` → `--g-success` (grün, WCAG AA); `kind='error'` → `--g-danger` (rot, WCAG AA)

**#598 — `trips/+page.svelte`:**
- `archiveTarget: Trip | null` State hinzugefügt
- `handlePrimaryAction()` setzt `archiveTarget = trip` statt sofort zu patchen
- `handleArchive()` führt PATCH aus, lädt Liste neu, setzt `archiveTarget = null`
- ConfirmDialog mit Text „Archivierte Trips erhalten keine Briefings mehr."
- Dearchivieren bleibt sofort (reversibel, kein Dialog nötig)

### Files Changed

- `frontend/src/lib/components/trip-detail/TripHeader.svelte` (+11/-2)
- `frontend/src/routes/trips/+page.svelte` (+36/-1)

---

## BUG-720-STALE-SPREAD: display_config wird in TripEditView beim Speichern zurückgesetzt

**Status:** RESOLVED (2026-06-10) | **Severity:** Medium | **GitHub Issue:** #720 | **Spec:** `docs/specs/_archive/bugfix/bug720_tripeditview_spread_fix.md`

### Symptom

Wenn ein Nutzer auf dem Tab "Metriken-Auswahl" `display_config` speichert (über `WeatherMetricsTab`) und danach die Trip-Bearbeitung öffnet und speichert, wird die zuvor gespeicherte `display_config` stille zurückgesetzt auf den alten Stand vom Seiten-Load. Die Metrik-Auswahl ist nach dem Speichern in TripEditView wieder falsch.

### Root Cause

`TripEditView.svelte` sendete beim PUT-Request den kompletten `trip`-Spread:

```typescript
// FALSCH — sendet veraltete trip.display_config
const updated: Trip = { ...trip, name, stages, report_config, alert_rules };
await api.put(`/api/trips/${trip.id}`, updated);
```

`trip` ist der in-Memory-State beim initialen Seiten-Load. Wenn der Nutzer zwischenzeitlich auf einem anderen Tab (z.B. `WeatherMetricsTab`) `display_config` ändert und speichert, kennt `TripEditView` diese Änderungen nicht — `trip.display_config` bleibt veraltet. Der PUT-Request mit `{ ...trip, display_config: {...veraltet} }` überschreibt die aktuellen DB-Daten mit dem alten Stand.

Das Go-Backend (`internal/handler/trip.go`, `UpdateTripHandler`) merged Pointer-Felder mit Nil-Check: ein gefülltes `display_config`-Objekt wird als neue Wahrheit behandelt und überschreibt aktuelle Konfigurationsdaten. Ein Code-Kommentar in TripEditView (Zeilen 75–77) dokumentierte sogar explizit „display_config KEIN Überschreiben" — der `...trip`-Spread tat genau das Gegenteil.

Ein identisches Anti-Pattern wurde bereits in `TripHeader.svelte` (Issue #707) und `BriefingScheduleTab.svelte` (Issue #707) sowie `WaypointsPanel.svelte` (Issue #717) behoben — TripEditView war der vierte Fundort.

### Fix (Committed 2026-06-10)

```typescript
// KORREKT — sendet nur die tatsächlich bearbeiteten Felder
await api.put(`/api/trips/${trip.id}`, {
    name: tripName,
    stages: stages,
    report_config: reportConfig,
    alert_rules: alertRules,
});
goto('/trips');
```

Das `const updated: Trip`-Intermediate-Object wurde entfernt. Der minimale Body enthält nur die 4 tatsächlich von TripEditView bearbeiteten Felder. Das Go-Backend (korrekt implementiert) merged nur die gesendeten Felder; alle übrigen Felder (`display_config`, `activity`, `region`, `aggregation`, `weather_config`) bleiben unverändert.

**Dateien geändert:**
- `frontend/src/lib/components/edit/TripEditView.svelte` (makeSaveHandler, Zeile 71–81)

### Lessons Learned

1. **Partial Updates:** Nur das tatsächlich geänderte Feld im PUT-Body senden, nicht den kompletten Spread — verhindert stale-data-Überschreibung
2. **Multi-Tab-State:** In einer Komponente ist der lokale `trip`-State unreliable, wenn ein anderer Tab dieselben Felder ändern kann. Minimaler Request-Body verhindert Konflikte.
3. **Anti-Pattern-Recurring:** Dieses Bug-Muster trat 4× auf (#707, #717, #720, implizit). Ein Guard-Test gegen `{ ...trip,` in API-Calls wäre präventiv hilf­reich gewesen.

### Testing

- **AC-1:** Source-Code-Compliance: `{ ...trip,` nicht in `api.put()`-Aufrufen in TripEditView vorhanden (doc-compliance-test)
- **AC-2:** Source-Code-Compliance: minimaler Body mit exakt 4 Feldern vorhanden (doc-compliance-test)
- **AC-3:** Integrations-Nachweis: Trip mit `display_config` via HTTP PUT ohne `display_config` sendet → Backend antwortet mit unverändertem `display_config`

---

## BUG-707-STALE-SPREAD: Trip-Datum wird bei Name-/Config-Speichern überschrieben

**Status:** RESOLVED (2026-06-10) | **Severity:** Medium | **GitHub Issue:** #707 | **Spec:** `docs/specs/_archive/bugfix/bug707_trip_datum_overwrite.md`

### Symptom

Wenn ein Nutzer das Stage-Datum einer Etappe ändert und speichert, und danach den Trip-Namen ändert oder die Briefing-Konfiguration speichert, werden die angepassten Stage-Daten stille zurückgesetzt auf den alten Stand vom Seiten-Load. Das Datum der Etappe ist nach dem Speichern wieder falsch.

### Root Cause

Die Komponenten `TripHeader.svelte` (Name-Save) und `BriefingScheduleTab.svelte` (Briefing-Config-Save) sendeten beim PUT-Request den kompletten `trip`-Spread:

```typescript
// FALSCH — sendet veralteten trip.stages
await api.put(`/api/trips/${trip.id}`, { ...trip, name: editName });
```

`trip` ist der in-Memory-State beim initialen Seiten-Load. Wenn der Nutzer zwischenzeitlich auf einem anderen Tab (z.B. Etappen-Editor) Daten ändert und speichert, kennt `TripHeader` und `BriefingScheduleTab` diese Änderungen nicht — `trip.stages` bleibt veraltet. Der PUT-Request mit `{ ...trip, stages: [...veraltet] }` überschreibt die aktuellen DB-Daten mit dem alten Stand.

Das Go-Backend (`internal/handler/trip.go`, `UpdateTripHandler`) merged Pointer-Felder mit Nil-Check: ein gefülltes `stages`-Array wird als neue Wahrheit behandelt und überschreibt aktuelle Stage-Daten.

### Fix (Committed 2026-06-10)

```typescript
// KORREKT — sendet nur das geänderte Feld
await api.put(`/api/trips/${trip.id}`, { name: editName });
await api.put<Trip>(`/api/trips/${trip.id}`, { report_config: reportConfig });
```

**Dateien geändert:**
- `frontend/src/lib/components/trip-detail/TripHeader.svelte` (makeNameSaveHandler, Zeile 36)
- `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte` (makeSaveHandler, Zeile 31)

### Lessons Learned

1. **Partial Updates:** Nur das tatsächlich geänderte Feld im PUT-Body senden, nicht den kompletten Spread — verhindert stale-data-Überschreibung
2. **Multi-Tab-State:** In einer Komponente ist der lokale `trip`-State unreliable, wenn ein anderer Tab dieselben Felder ändern kann. Minimaler Request-Body verhindert Konflikte.
3. **Backend-Merge:** Das Go-Backend ist korrekt implementiert (Nil-Check auf Pointer-Felder). Der Bug war Frontend-seitig.

### Testing

- **AC-1:** Stage-Datum ändern + speichern → Trip umbenennen → Seite neu laden → Stage-Datum bleibt erhalten
- **AC-2:** Stage-Datum ändern + speichern → Briefing-Zeitplan speichern → Seite neu laden → Stage-Datum bleibt erhalten
- **AC-3:** Trip mit mehreren Etappen umbenennen → alle Etappen unverändert
- **AC-4:** Trip umbenennen + Briefing-Zeitplan speichern (hintereinander) → beide Änderungen gespeichert

---

## BUG-TOKEN-01: Alte Farb-Token-Aliasse nicht bereinigt (#541, #543, #544)

**Status:** RESOLVED (2026-06-02) | **Severity:** Low | **GitHub Issues:** #541, #543, #544

### Symptom

Drei rückwirkend durch Adversary-Audit (#510) gefundene Regressions:
1. Native HTML-Checkboxen in `Step3Weather.svelte` und `Step5Reports.svelte` statt Atomic-`Checkbox`-Komponente
2. Tailwind-Residual (`hover:bg-muted/50`) in `WeatherConfigDialog.svelte` nach Token-Migration (#285)
3. Alte Token-Aliasse (`--g-good`, `--g-warn`, `--g-bad`) in 35 Komponenten und `app.css` noch nicht durch kanonische Namen (`--g-success`, `--g-warning`, `--g-danger`) ersetzt, obwohl #519 die neuen Namen eingeführt hatte

### Root Cause

Atomic-Migration (#368) und Token-Konsolidierung (#519) waren teilweise unvollständig. Native Checkboxen wurden in zwei Wizard-Schritten übersehen. Alte Token-Aliasse wurden in der Übergangsphase als Brücke belassen, aber nicht aufgeräumt. Tailwind-Klasse war Residual aus einem früheren Refactor.

### Fix (Committed 2026-06-02)

**Commit:** [Details in Spec]

1. **#543 — Checkbox-Migration:** Native `<input type="checkbox">` in `Step3Weather.svelte` und `Step5Reports.svelte` durch `<Checkbox>`-Komponente aus `$lib/components/ui/checkbox` ersetzt
2. **#544 — Tailwind-Klasse:** `hover:bg-muted/50` in `WeatherConfigDialog.svelte` entfernt; Hover-Verhalten über scoped CSS mit `var(--g-surface-2)` implementiert
3. **#541 — Token-Rename:** Alle 35 Komponenten und `app.css`:
   - `var(--g-good)` → `var(--g-success)`
   - `var(--g-warn)` → `var(--g-warning)`
   - `var(--g-bad)` → `var(--g-danger)`
   - Bridge-Aliasse aus `app.css` entfernt
   - Pill/Dot-Farbregeln mit neuen Token-Namen aktualisiert

### Files Changed

- Frontend: 35 `.svelte` Komponenten (mechanisches Token-Rename)
- Styles: `frontend/src/app.css` (Token-Definitionen + Pill/Dot-Regeln)
- Tests: 3 TypeScript-Testdateien (Assertions aktualisiert)
- Spec: `docs/specs/_archive/modules/bug-541-543-544-token-checkbox-tailwind.md` v1.0

### Lessons Learned

1. Atomic-Migration und Token-Refactorings brauchen abschließende Audits gegen die gesamte Codebasis (Grep-Suche, nicht nur visuelles Review)
2. Temporäre Bridge-Aliasse sollten mit explizitem Verfallsdatum dokumentiert sein
3. Guard-Tests gegen veraltete Token-Namen helfen, Regressions zu fangen

---

## BUG-1389-CASCADE-RACE: Kaskade „Folgeetappen mitverschieben" blieb wirkungslos (#1389, #1390)

### Symptom
Der Nutzer änderte auf dem Handy das Datum der ersten Etappe, bestätigte die Rückfrage „Sollen die N Folgeetappen mitverschoben werden?" — und nur Etappe 1 bewegte sich. Die Oberfläche meldete dabei sogar „N Folge-Etappen verschoben · alle Daten angepasst".

Folgewirkung: Der 3-Tages-Ausblick verschwand aus den Briefing-Mails (#1388), weil nach der halben Verschiebung keine Etappe mehr in der Zukunft lag.

### Root Cause — zwei unabhängige Ursachen-Klassen

**(1) Konkurrierende Schreibvorgänge ohne Serverseite-Sperre.**
`handleDateChange()` plante beim Umdatieren sofort einen Debounce-Speichervorgang (700 ms) mit dem Stand „Etappe 1 neu, Folgeetappen ALT". Wer den Banner erst liest, klickt später — der veraltete Schreibvorgang war da schon unterwegs. `applyCascade()` rief `cancel()`, das aber nur einen **noch nicht ausgelösten** Timer stoppt, und sendete einen zweiten PUT. `UpdateTripHandler` (`internal/handler/trip.go`) ersetzt die Etappen vollständig, ohne Version/ETag/Mutex — **wer zuletzt ankommt, gewinnt**, nicht wer zuletzt sendet.

Auf schnellem Netz gewinnt zufällig der richtige. Der Fehler braucht **asymmetrische** Verzögerung: die früher gesendete Anfrage trifft später ein. Genau das ist bei eingeschränkter Konnektivität der Normalfall — und das ist die Zielgruppe dieses Produkts.

**(2) Position statt Identität.** Vier Riegel derselben Bauart in einer Datei: `activeStageIndex === 0` (Sichtbarkeit der Rückfrage), `i === 0` (Überspringen beim Anwenden), `idx === 0` (Neuberechnung beim zweiten Umdatieren), sowie ein positionsbasierter Ausschluss beim Festhalten der Grundlage. Alle waren **zufällig** richtig, solange die auslösende Etappe nicht umsortiert werden konnte — und fielen der Reihe nach um, sobald das ging.

### Fix (live 2026-07-26, Commits `920cc99c` … `d38740c2`)
- **Kein zweiter Schreibvorgang:** `SaveStatus.defer()` stellt zurück, statt zu takten, solange die Rückfrage offen ist. Genau ein PUT je Entscheidung.
- **Reihenfolge nicht dem Netz überlassen:** `SaveStatus.settle()` wartet auf einen dennoch laufenden Schreibvorgang, gedeckelt auf `SETTLE_TIMEOUT_MS`.
- **Idempotenz:** Die Zieldaten werden aus einer beim Aufstellen der Rückfrage festgehaltenen Grundlage (`baseFirstDate`/`baseDates`, nach `id` geschlüsselt) berechnet — nicht aus dem laufend veränderten Zustand. Wiederholung nach Fehlschlag verdoppelt dadurch nichts.
- **Reentrancy-Riegel** vor dem ersten `await`; Knöpfe während der Verarbeitung gesperrt.
- **`dismissCascade()` speichert unbedingt**, statt sich auf einen möglicherweise abgeräumten Speichervorgang zu verlassen; im Fehlerfall wird die geäußerte Absicht neu vorgemerkt, damit `beforeNavigate` sie retten kann.
- **Durchgängig identitätsbasiert:** Aufstellen, Grundlage, Anzeige, Anwenden, Zurücknehmen, Verwerfen.

### Lessons Learned

**Ein Test, der schneller klickt als ein Mensch, beweist den falschen Pfad.** `issue-498-stage-date-autosave.spec.ts` AC-2 prüfte diesen Ablauf seit jeher inklusive Neuladen — und war immer grün. Playwright klickt in Millisekunden, der Debounce-Timer war da noch nicht gefeuert, ein zweiter Schreibvorgang entstand nie. Der Test bewies genau den einen Fall, den ein Mensch nie auslöst. **Wo eine Bedienung eine menschliche Lesepause enthält, muss der Test sie enthalten** — und wo Nebenläufigkeit die Ursache ist, muss der Test sie erzwingen (`page.route()` mit gezielter Verzögerung), nicht auf sie hoffen.

**Sechs Staging-Runden, sechs neue Funde — keinen davon sah die Kern-Suite.** Doppeltipp, Wiederholung nach Fehlschlag, stilles Verwerfen bei „Nur diese Etappe", derselbe Verlust beim Reiterwechsel, ein unbegrenzter Hänger, den die Reparatur selbst eingebaut hätte. Alle wurden erst durch aktives Brechen am echten Klickpfad sichtbar.

**„Position" ist fast nie gemeint, wenn „Identität" gemeint ist.** Nach dem dritten Riegel derselben Bauart wurde die Datei systematisch nach Positions-Annahmen durchgesehen; das förderte zwei weitere latente Fehler zutage. Die Durchsicht war billiger als die drei Einzelrunden davor. Bemerkenswert: **eine** Stelle sieht aus wie derselbe Fehler und ist richtig — der Marker „· Tourstart" **soll** an der jetzt ersten Etappe hängen.

**Offen und bewusst nicht behoben:** Das Backend hat weiterhin keine optimistische Sperre. Die ganze Klasse „zwei parallele Speichervorgänge überschreiben sich" ist damit nur an dieser einen Stelle entschärft, nicht grundsätzlich. Ein Versionsstempel am Trip wäre die strukturelle Lösung — eigener Vorgang, mehrere PUT-Verbraucher betroffen.

### Testing
`frontend/e2e/issue-498-stage-date-autosave.spec.ts` — von 5 auf 21 Punkte gewachsen. Kern der Absicherung: AC-6 verzögert den veralteten Schreibvorgang gezielt und prüft den **persistierten** Stand. Dass er die Reparatur wirklich bewacht, wurde durch Rückrollen des Produktivcodes belegt — dann wird er rot mit exakt dem gemeldeten Symptom.
