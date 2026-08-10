# Context: fix-1662-versandfehler-nachliefern

- **Issue:** #1662 (`priority:critical`, `bug`, `area:reports`, `session:alarm`)
- **Track:** Full Process (Intake-Score 5/6)
- **Vorgänger:** #1629 (gemerged 2026-08-10, `c5bbadb0`) — Reihenfolge laut PO: #1629 → **#1662** → #1661
- **Zuschnitt (PO-Entscheidung 2026-08-10):** **Scheibe 1 = Nachlieferung.** Teilzustellung
  (`email.py`-Guard vereinzelt Empfänger) ist bewusst **nicht** Teil dieses Workflows.

## Request Summary

Scheitert der **Versand** eines Trip-Briefings, wird es nie nachgeliefert. Der bestehende
Nachhol-Mechanismus (#1012, `pending_briefings.json`) merkt ausschließlich **Wetterdaten**-Fehler
vor. Am 2026-08-08 fiel dadurch ein komplettes Morgen-Briefing aus; bemerkt wurde es erst am
Folgetag, zufällig.

Ziel dieser Scheibe: Ein gescheiterter Versand wird vorgemerkt, sodass der bereits vorhandene
stündliche Vorlauf ihn nachholt — **ohne** einen deterministisch aussichtslosen Fehler stündlich zu
wiederholen.

## Was #1629 bereits geliefert hat (Issue-Text ist an dieser Stelle überholt)

Der Issue-Text entstand **vor** dem Merge von #1629. Am Code nachgemessen:

| Aussage im Issue-Text | Ist-Stand 2026-08-10 |
|---|---|
| Anker geht bei Versandfehler verloren | ✅ behoben — `trip_report_scheduler.py:1033-1044` fängt, ankert, reicht weiter |
| Meldung ist edge-triggered, kein wachsendes Signal | ✅ **teilweise** — `briefing_dispatch_error_streak_since` / `_errors_recent_count` wachsen mit der Ausfalldauer (`internal/scheduler/briefing_health.go:203`, Streak-Schwelle 26 h). Es gibt weiterhin **keinen Push** — das Signal steht nur am Status-Endpunkt und braucht einen externen Leser (BetterStack-Leiter, Infra) |
| Diagnose fehlt | ✅ `users/<uid>/diagnostics/briefing_dispatch_failures.jsonl` (`alert_briefing_anchor.py:54`) |
| Kein Pending-Marker bei Versandfehler | 🔴 **unverändert** — Kern dieser Scheibe |
| Ein blockierter Empfänger kippt alles | 🔴 unverändert — **bewusst Scheibe 2** |
| Cockpit-Kachel #393 unterscheidet ausgefallen ≠ nie geplant nicht | 🔴 unverändert (`_append_briefing_log` nur im Erfolgs-Zweig, `trip_report_scheduler.py:1080`) |

## 🔴 Gemessen im Produktiv-Journal (`sudo journalctl -u gregor-python.service`, 2026-05-01 → 2026-08-10)

Ohne `sudo` ist die Journal-Sicht unvollständig und endet vor dem Vorfall — die folgenden Zahlen
stammen aus dem vollständigen Journal (1 618 227 Zeilen).

**Genau drei** gescheiterte Versandläufe in 101 Tagen:

| Zeitpunkt | Fehler | Art |
|---|---|---|
| 2026-07-02 16:00 | `Unknown provider: openmeteo. Available: geosphere` | Konfiguration/Registry |
| **2026-08-07 16:00** | Resend-Allowlist-Guard, 1 Empfänger | `OutputConfigError` |
| **2026-08-08 05:00** | Resend-Allowlist-Guard, 1 Empfänger | `OutputConfigError` |

Versandhistorie des betroffenen Trips (`KHW 403`) drumherum:

```
2026-08-07 05:01  morning  ✅ gesendet
2026-08-07 16:00  evening  ❌ Allowlist-Guard
2026-08-08 05:00  morning  ❌ Allowlist-Guard
2026-08-08 16:01  evening  ✅ gesendet      <- heilte von selbst
2026-08-09 …               ✅ durchgehend
```

### Zwei Folgerungen, die den Entwurf umstellen

1. **Es waren ZWEI verlorene Briefings, nicht eines.** Das Issue nennt nur das Morgen-Briefing vom
   08.08.; der Abend des 07.08. fiel bereits genauso aus. Der Nutzer war ~24 h ohne Briefing.
2. **🔴 Die Prämisse des Issue-Textes hält der Messung nicht stand.** Dort steht: „Der
   Allowlist-Fall ist **deterministisch** — stündlich zu wiederholen brächte nur stündliches
   Scheitern." Gemessen heilte genau dieser Fehler nach ~13 h von selbst, ohne Eingriff. Der
   Fehler**typ** (`OutputConfigError`) sagt „dauerhaft", die beobachtete **Wirkung** war
   vorübergehend — der Guard hängt an Nutzerprofil-Daten, nicht an einer statischen Konfiguration.
   Eine Klassifikation nach `isinstance(exc, OutputConfigError)` = „nie wiederholen" hätte **keinen
   einzigen** der drei realen Vorfälle gerettet. Auch der Provider-Fehler vom 02.07. wäre nach
   Behebung durch einen Wiederholungsversuch zustellbar gewesen.
   **Konsequenz für die Spec:** Die Frage ist nicht „welcher Typ ist dauerhaft?", sondern „wie oft
   und wie lange wiederholen, bevor aufgegeben wird?" — ein Deckel plus Verfall trägt weiter als
   eine Typ-Unterscheidung. Das ist dem PO in Phase 3 vorzulegen, weil es seiner im Issue notierten
   Erwartung widerspricht.

Nebenbefund: Der Allowlist-Guard feuerte im Zeitraum **702-mal**, aber nur 2-mal im
Briefing-Versandpfad — die übrigen Treffer stammen aus anderen Pfaden und sind Rauschen für dieses
Issue. Am 07.08. und 08.08. gab es jeweils **genau eine** Guard-Zeile, also kein Flächenproblem.

Der Scheduler-Endpunkt antwortete bei beiden Fehlschlägen mit **HTTP 200** (`status: "partial"`,
`api/routers/scheduler.py:40-42`) — von außen betrachtet lief der Aufruf „erfolgreich".

## Ursachenkette (jede Station am Code belegt)

1. `_send_trip_report_outcome` ruft den Versand in einem `try` (`trip_report_scheduler.py:1033`).
   Bei Ausnahme: Diagnose-Zeile + Anker + `raise` (`:1036-1044`) — **kein Marker**.
2. Der Marker entsteht ausschließlich weiter unten, **nach** erfolgreichem Versand, aus
   `errors = request.failed_segments` (`:1046`, geschrieben bei `:1086`) — das sind Segmente mit
   fehlgeschlagenem **Wetterabruf**, nie Versandfehler.
3. Zweite Schreibstelle: Totalausfall der Wetterdaten (`:865`), ebenfalls wetterbezogen.
4. Die Ausnahme fliegt hoch bis `dispatch_orchestrator.py:74-77`, wird als `failed` gezählt und
   protokolliert. Danach ist der Vorgang beendet — **kein zweiter Zustellversuch**.
5. Einen Retry im Versand selbst gibt es nicht; Wiederholungslogik existiert nur für den
   Wetterabruf (`trip_report_scheduler.py:1362-1413`, `FETCH_RETRY_ATTEMPTS`).

## Der Nachhol-Mechanismus, den es schon gibt (#1012)

`_process_pending_markers` (`trip_report_scheduler.py:361`) läuft **stündlich** als `pre_pass` vor
den regulären Slots (`dispatch_orchestrator.py:60-64`, getriggert über
`api/routers/scheduler.py:40`). Pro Marker:

| Bedingung | Folge | Beleg |
|---|---|---|
| Trip weg oder **jetzt regulär fällig** | Marker verfällt ersatzlos | `:385-388` |
| Keine Segmente | Marker verfällt | `:392-394` |
| Ein **zuvor** fehlendes Segment liefert weiter nicht | kein Re-Send, `attempts += 1` | `:400-406` |
| sonst | Marker entfernen, Re-Send mit Präfix | `:426-431` |

Marker-Schema (`_write_pending_marker`, `:435-465`):
`{trip_id, report_type, date, slot_hour, failed_segment_ids, attempts, created_at}`, **ein Marker je
Trip** (bestehender wird ersetzt, `:449`).

### 🔴 Drei gemessene Eigenheiten, die den Entwurf bestimmen

1. **`attempts` wird geschrieben, aber nirgends gelesen.** Kein Deckel, kein Verfall — geprüft mit
   `grep -n attempts trip_report_scheduler.py`, einzige Leser-Stelle ist das Inkrement selbst
   (`:485`). Der Lärmschutz kommt faktisch aus der Segment-Schnittmenge (`:400`), nicht aus
   `attempts`. **Antwort auf die Frage aus dem Issue-Text („reichen `attempts`/Verfall aus #1012?"):
   nein — das Feld ist heute tot.**
2. **Ein Marker mit leerem `failed_segment_ids` würde heute schon nachliefern — mit falschem Text.**
   `previously_failed` wäre die leere Menge, die Schnittmenge bei `:404` also leer → Re-Send.
   `was_complete_failure = len(previously_failed) >= len(segments)` ist `0 >= N` → falsch, also
   Präfix **„Aktualisiert — jetzt mit vollständigen Daten"** (`:421`). Für einen Versandfehler ist
   das sachlich falsch: die Daten waren nie das Problem, und der Nutzer hat kein „vorher", das
   aktualisiert würde. Ein eigener Präfix ist nötig.
3. **Ein Trip hat höchstens EINEN Marker.** Ein Versandfehler am Morgen und ein Wetter-Teilausfall
   am Abend überschreiben sich gegenseitig (`:449`). Welcher gewinnt, muss die Spec festlegen.

## Fehler-Taxonomie des Versandpfads (Grundlage der Klassifikation)

`send_trip_report` (`notification_service.py:275-430`) hat **kein** umschließendes `try`.
Kanal-Reihenfolge: **E-Mail (`:354`) → SMS (`:359`) → Telegram (`:371`)**.

| Kanal | Verhalten | Beleg |
|---|---|---|
| E-Mail | **propagiert** (kein try) | `notification_service.py:354-356` |
| SMS | fail-soft (`except Exception`) | `:361-368` |
| Telegram | fail-soft, aber nur `except OutputError` | `:378-390`, `:400-413` |

Damit ist der Scheduler-Kommentar bei `:1023` im Kern richtig, vereinfacht aber Telegram.

**Für die Nachlieferung entscheidend:** E-Mail läuft **zuerst** und ist der einzige propagierende
Kanal. Wirft sie, wurden SMS und Telegram **noch gar nicht** aufgerufen — eine vollständige
Nachlieferung erzeugt also **keine Doppelzustellung**. Randfall: eine unerwartete
Nicht-`OutputError`-Ausnahme aus der Telegram-Bubble-Schleife (`:398-413`) kann fliegen, **nachdem**
Mail und einzelne Bubbles schon draußen sind — dann würde eine Nachlieferung doppeln.

### Was zur Unterscheidung dauerhaft/vorübergehend zur Verfügung steht

| Merkmal | Aussagekraft | Beleg |
|---|---|---|
| `OutputConfigError` | **deterministisch dauerhaft** — fehlende Konfiguration, Empfänger-Guards (Allowlist/Lokal), Herkunftssperre. Einzige Subklasse von `OutputError` | `output/channels/base.py:60-63`; Guards `email.py:724-731`, `:763-770` |
| `OutputError` (Basis) | **undifferenziert** — SMTP-Auth (permanent), SMTP-5xx (permanent), erschöpfte Retries (vorübergehend), Ersatzweg gescheitert | `email.py:851, 857, 914, 962` |
| Freitext der Meldung | „SMTP permanent error 500" vs. „SMTP temporary error 421 after 4 attempts" | ebd. |
| `__cause__` | **meist nicht vorhanden** — die `raise OutputError(...)`-Stellen in `email.py` nutzen kein `from exc` | ebd. |

Die Unterscheidung existiert also **innerhalb** von `email.py` (`:853-861`, `:920-974`), geht beim
finalen `raise` aber verloren. `_is_transient_fetch_error` (`trip_report_scheduler.py:71-80`) und die
`_is_retryable_error`-Familie der Provider setzen an `status_code`/`httpx`-Typen an und sind nach dem
Wrapping **nicht** direkt wiederverwendbar.

**Präzedenzfall für die Bauform:** ADR-0018 Punkt 2 entscheidet dieselbe Frage für den
Wetter-Provider **strukturell** (5xx → ausweichen, 4xx → nicht, „läuft strukturell über
`ProviderRequestError.status_code`") und ausdrücklich nicht über Textmuster. Eine Klassifikation für
#1662 sollte demselben Prinzip folgen — also am **Typ**, nicht am Meldungstext.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/trip_report_scheduler.py` | Kern: Fehlerpfad `:1033`, Marker-Helfer `:435-490`, Vorlauf `:361`, zweite Schreibstelle `:865` |
| `src/services/alert_briefing_anchor.py` | Heimat der **geteilten** Bausteine (`write_anchor_and_reset_memory:160`, `record_briefing_dispatch_failure:54`) — beide von Trip **und** Compare aufgerufen |
| `src/services/dispatch_orchestrator.py` | `pre_pass`-Hook `:60`, Fehlerzählung `:74-77` |
| `src/services/scheduler_dispatch_service.py` | Compare-Fehlerpfad `:446-451` — strukturgleich zum Trip-Pfad, aber ohne jede Nachhol-Logik |
| `src/services/notification_service.py` | Kanal-Reihenfolge und Fail-soft-Grenzen `:275-430` |
| `src/output/channels/email.py` | Ursache vom 08.08. (`:724-731`) — in dieser Scheibe **nur lesend** |
| `internal/store/pending_briefings.go` | Go liest die Marker-Datei; unbekannte Felder werden ignoriert |
| `internal/scheduler/briefing_health.go:70-100` | `open_pending_briefings` / `degraded_segments_total` zählen aus derselben Datei |

## Existing Patterns

- **Strukturelle Fehlerklassifikation statt Textmuster** — ADR-0018 Punkt 2.
- **Read-Modify-Write auf Marker-Dateien**, ein Eintrag je Trip — `_write_pending_marker:448-465`.
- **Fail-soft bei Beobachtungs-Nebenwirkungen** — eine defekte Diagnose darf die eigentliche
  Ausnahme nie verdecken (`alert_briefing_anchor.py:86-90`).
- **Nachliefer-Präfix als Nutzertext** statt stiller Wiederholung — `:409-422`.
- **Marker zuerst entfernen, dann senden** (RMW-Reihenfolge), damit ein erneuter Fehlschlag vom
  regulären Pfad frisch vorgemerkt wird — `:425-428`.

## Dependencies

- **Upstream:** `get_data_dir` (Datenwurzel, #1633), `NotificationService.send_trip_report`,
  `OutputError`/`OutputConfigError`, `write_anchor_and_reset_memory`.
- **Downstream:** Go-Health (`open_pending_briefings`, `oldest_pending_created_at`),
  `/api/scheduler/status`, Cockpit-Kachel #393, der stündliche `pre_pass`.

## Existing Specs & ADRs

| Dokument | Bezug |
|---|---|
| `docs/adr/0018-provider-fallback-ohne-kaschieren.md` | Nicht-Kaschieren-Invariante; #1629 ist dort als erfüllt vermerkt. Punkt 2 = Vorbild der Klassifikation |
| `docs/specs/modules/fix_1629_briefing_anker_versandfehler.md:72-75` | Grenzt #1662 ausdrücklich ab |
| `docs/specs/modules/dispatch_orchestrator.md:95` | Divergenz `pre_pass`: Trip = Catch-up, Compare = Auto-Pause — **dokumentiert und akzeptiert** |
| `docs/specs/_archive/modules/issue_1115_openmeteo_model_fallback.md` | Herkunft von ADR-0018 |

## Trip/Compare-Teilung — Stand und Bewertung

Gemessen: **Der Ortsvergleich hat überhaupt keinen Nachhol-Mechanismus** — `CompareDispatchStrategy.pre_pass`
(`dispatch_orchestrator.py:122-127`) macht nur Auto-Pause, es gibt keine `pending_*`-Datei für
Presets. Der Compare-Fehlerpfad (`scheduler_dispatch_service.py:446-451`) ist ansonsten
**strukturgleich** zum Trip-Pfad: `record_briefing_dispatch_failure` → `_anchor_and_reset()` → `raise`.

Das ist keine neu geschaffene Asymmetrie: die `pre_pass`-Divergenz ist in
`docs/specs/modules/dispatch_orchestrator.md:95` dokumentiert und PO-getragen. Trotzdem gilt die
Teilungsregel — die Vormerk-Entscheidung (Klassifikation + Schreiben) gehört deshalb als
**geteilter Baustein neben `record_briefing_dispatch_failure`** in `alert_briefing_anchor.py`, wo
beide Seiten heute schon einhaken. Nur das **Abarbeiten** bleibt zunächst Trip-seitig.

## Risks & Considerations

- **Doppelzustellung** ist die teuerste Fehlwirkung. Für den Regelfall entschärft, weil Mail zuerst
  läuft und als einzige propagiert. Der Telegram-Randfall (`notification_service.py:398-413`) bleibt
  und muss in den ACs beantwortet werden.
- **Stündliche Wiederholung eines aussichtslosen Fehlers.** Der Auslöser vom 08.08. war ein
  Empfänger-Guard, also `OutputConfigError` — deterministisch. Ohne Klassifikation entstünden
  stündliche Fehlschläge, Journal-Rauschen und wachsende Diagnose-Zeilen.
- **`attempts` ist tot** — wer sich darauf verlässt, baut auf Sand. Entweder wird das Feld in dieser
  Scheibe scharf gemacht oder die Begrenzung kommt anders. Das gehört in die ACs.
- **Marker-Kollision** Morgen/Abend (ein Marker je Trip).
- **Bedeutungswandel eines bestehenden Signals:** `open_pending_briefings` heißt heute „Briefing mit
  unvollständigen Wetterdaten". Nach dieser Scheibe hieße es auch „Briefing nicht zugestellt".
  `degraded_segments_total` bliebe bei 0, weil `failed_segment_ids` leer ist. Go bricht nicht
  (unbekannte JSON-Felder werden ignoriert, `internal/store/pending_briefings.go:37-40`), aber die
  Semantik des Zählers verschiebt sich — das ist zu benennen, nicht stillschweigend hinzunehmen.
- **🔴 Testabdeckung ist trügerisch:** Die #1012-Tests
  (`tests/tdd/test_issue_1012_no_data_guard.py`, `test_issue_1113_partial_outage_guard.py`) tragen
  `pytestmark = pytest.mark.email` und laufen im Standard- **und CI**-Lauf **gar nicht**
  (`pyproject.toml:65` schließt `email`/`live`/`staging` aus). Die gesamte Nachhol-Mechanik ist im
  regulären Testlauf **unbewacht**. Die #1629-Tests
  (`test_briefing_anchor_survives_dispatch_failure.py`, 9 Tests) laufen offline — dort lässt sich
  sicher iterieren, und dort gehören die neuen Tests hin.
- **Kein Schema-Test bricht** bei einem neuen Feld (kein Test prüft Feldanzahl oder Gleichheit des
  ganzen Dicts). Der Format-Kontrakt steht nur als Docstring in
  `tests/tdd/test_issue_1012_no_data_guard.py:23-26` — bei Erweiterung mitziehen, sonst Doku-Drift.
- **Wiederverwendbare Helfer:** `_run_failing_briefing`
  (`tests/tdd/test_briefing_anchor_survives_dispatch_failure.py:220`) erzeugt einen **echten**
  `OutputConfigError` über unvollständige SMTP-Konfiguration — kein Mock. Genau der Fehlertyp vom
  08.08. Dazu `_pending_markers` (`test_issue_1012_no_data_guard.py:162`).
- **Signal ohne Leser** (Lehre aus #1629): Ein neues Merkmal braucht im selben Zug einen Leser.
- **Häufigkeit:** siehe „Gemessen im Produktiv-Journal" oben — 3 Fehlschläge in 101 Tagen. Ein
  Retry-Mechanismus muss vor allem *korrekt* sein, nicht durchsatzstark.
- **Ursache des Guard-Fehlschlags selbst ist ungeklärt.** Warum ein Empfänger an zwei Slots keinem
  echten Nutzerprofil zugeordnet werden konnte, steht nicht im Journal (kein Profil-Ladefehler im
  Umfeld, Adresse maskiert als `***@henemm.com`). Diese Scheibe behandelt die **Folge** (verlorenes
  Briefing), nicht die Ursache. Ob die Ursache ein eigenes Issue braucht: Phase 2.

## Offene Fragen für die Analyse (Phase 2)

1. ~~Welche Fehlerarten sind real aufgetreten?~~ **In Phase 1 beantwortet** (s.o.): 3 Fehlschläge,
   alle nominell „dauerhaft", zwei davon nachweislich selbstheilend.
2. Trägt eine Typ-Klassifikation überhaupt noch — oder ersetzt „Deckel + Verfall" sie vollständig?
   (Die Messung spricht für Letzteres; PO-Entscheidung, weil sie der Issue-Prämisse widerspricht.)
3. Wie oft und wie lange wird nachgeholt (Deckel über `attempts`, Verfall über `created_at`)?
   Konkret: Wäre ein Marker vom Abend des 07.08. am Morgen des 08.08. verfallen, weil der Trip dann
   regulär fällig ist (`:385`)? Dann wäre das Abend-Briefing trotz Nachhol-Mechanik verloren
   geblieben — diese Verfallsregel ist auf Wetterfehler zugeschnitten und muss geprüft werden.
4. Welcher Nutzertext steht auf einem nachgelieferten Briefing nach Versandfehler?
5. Kollisionsregel Morgen-/Abend-Marker.
6. Wird der Telegram-Teilzustellungs-Randfall abgedeckt oder ausdrücklich ausgeschlossen?
7. Braucht das erweiterte `open_pending_briefings` eine Aufschlüsselung nach Grund?

---

# Analysis (Phase 2)

## Type

**Bug.** Nutzersichtbarer Verlust einer zugesagten Leistung (zwei Briefings), belegt am gemessenen
Produktivvorfall.

## Gegenprüfung (analysis-challenger) — Ergebnis: NEEDS REVIEW

| Behauptung aus Phase 1 | Urteil | Konsequenz |
|---|---|---|
| Keine Doppelzustellung im Regelfall | **WACKELT** | Der Telegram-Randfall sitzt **exakt** am geplanten Einhängepunkt: `trip_report_scheduler.py:1035` fängt *jede* Ausnahme, `notification_service.py:398-413` fängt nur `OutputError`. Muss eine **AC** werden, keine Fußnote |
| `attempts` ist ein totes Feld | **HÄLT** | Kein Leser in Python, Go oder Frontend; `internal/store/pending_briefings.go:18` deklariert das Feld nur |
| Fehlertyp „dauerhaft", Wirkung vorübergehend | **HÄLT** | Zusätzlich am Code belegt, s.u. |
| Verfallsregel verlöre das Abend-Briefing | **HÄLT, präzisiert** | Der Vorlauf läuft **stündlich** (`internal/scheduler/scheduler.go:141`, `"0 * * * *"`) — es hätte elf Zwischenversuche gegeben. Dass bei Fälligkeit **kein letzter Versuch** stattfindet (`:386-388`), ist eine **unentschiedene Designfrage**, kein Naturgesetz |

Zusätzlich gefordert: Mandantentrennung als **explizite AC** (der Bestandscode macht es richtig —
`user_id=self._user_id` bei `:1037` — aber das beweist nichts über neuen Code), und ein Test, dass
der Ortsvergleich **nicht** versehentlich mitprofitiert.

Nicht prüfbar für den Challenger (kein Server-Zugriff) und deshalb hier nachgeholt: die
Journal-Zahlen und die Deploy-Frage.

## Der entscheidende Befund: warum eine Typ-Klassifikation falsch wäre

Die Selbstheilung zwischen 08-08 05:00 und 16:01 UTC hat eine am Code belegte Erklärung, die
**keinen** Deploy braucht — die Alternativen sind ausgeschlossen:

- **Der Guard-Code war unverändert.** Einzige Änderung an `email.py` im Zeitraum ist `ae0553b3`
  (2026-08-08 **19:31** UTC) — nach der Erholung; davor `a806647d` (08-03).
- **Kein Nutzerprofil wurde je von Git überschrieben.** `git log --diff-filter=AD -- 'data/users/**'`
  kennt nur `gpx/`, `trips/`, `briefings/`; die Bereinigung getrackter Datenreste (#1624, `0d02d601`)
  lief am 08-08 **20:28** UTC, ebenfalls danach.
- **Also kann nur die Datenlage den Unterschied gemacht haben** — und genau daran hängt der Guard:
  `_load_resend_allowlist()` (`email.py:239-292`) baut die Allowlist bei **jedem** Sendeversuch neu
  aus `<data_root>/users/<id>/user.json` und nimmt nur Profile mit gesetztem `email_verified_at`
  (`:284`). Nichts wird zwischengespeichert.

🔴 **Der Fail-soft-Zweig ist der wunde Punkt:** Lässt sich `<data_root>/users` nicht auflisten,
liefert die Funktion eine **leere** Allowlist (`:267-270`) — womit **jeder** Empfänger blockiert
wird. Ein Umgebungs- oder Datenwurzel-Problem erscheint damit als `OutputConfigError`, also als
„dauerhafter Konfigurationsfehler", obwohl es vorübergehend ist. Dass am selben Abend `ae0553b3`
(„hartkodierte Datenwurzeln auf `get_data_root` umgestellt", #1595) landete und zwei konkurrierende
`data`-Ordner bekannt sind (#1633), passt ins Bild.

**Schlussfolgerung:** `isinstance(exc, OutputConfigError)` als „nie wiederholen" wäre genau die
falsche Regel — sie würde die wahrscheinlichste reale Ursache aussperren. **Die Begrenzung muss über
Zeit laufen, nicht über den Fehlertyp.** Das widerspricht der im Issue-Text notierten Erwartung und
ist deshalb PO-Entscheidung (Phase 3).

## Affected Files (with changes)

| File | Change Type | Description |
|---|---|---|
| `src/services/alert_briefing_anchor.py` | MODIFY | Reine Entscheidungsfunktion `dispatch_failure_is_retryable(...)` neben `record_briefing_dispatch_failure` — geteilter Baustein, ohne I/O, ohne Mock testbar (~25 LoC) |
| `src/services/trip_report_scheduler.py` | MODIFY | Marker-Schreibaufruf im `except`-Zweig `:1035-1042` (mit `not on_demand` wie `:854`/`:1085`), `reason`-Parameter für `_write_pending_marker`, eigener Zweig in `_process_pending_markers` **vor** `:401`, eigener Nachliefer-Präfix (~45 LoC) |
| `tests/tdd/test_briefing_anchor_survives_dispatch_failure.py` | MODIFY | Neue ACs im **offline lauffähigen** Bestandsfile, Helfer `_run_failing_briefing:220` wiederverwenden (~60-90 LoC) |
| `docs/specs/modules/fix_1662_versandfehler_nachliefern.md` | CREATE | Spec (zählt nicht aufs LoC-Limit) |

**Kein Go-Code nötig** — unbekannte JSON-Felder werden ignoriert
(`internal/store/pending_briefings.go:37-40`). **Nicht** in
`tests/tdd/test_issue_1012_no_data_guard.py`: trägt `pytest.mark.email`, läuft weder lokal noch in
CI (`pyproject.toml:65`).

## Scope Assessment

- **Files:** 2 Produktiv + 1 Test + 1 Spec
- **LoC:** ~70 Produktivcode (Limit 250) — **kein Override nötig**
- **Risk Level:** MEDIUM — kritischer Pfad, aber kleine Fläche und offline bewachbar

## Technical Approach

1. **Marker-Unterscheidung über ein neues Feld `reason: "dispatch_error"`** (fehlend = Wetterfehler,
   Bestandsverhalten unverändert). Der neue Zweig hakt **vor** der Segment-Schnittmenge (`:401`)
   ein, statt sie zu verbiegen — bei einem Versandfehler ist `failed_segment_ids` leer, die
   Schnittmenge also immer leer, und die Bestandslogik zöge den falschen Schluss („jetzt vollständige
   Daten", `:421`).
2. **Begrenzung über Zeit, nicht über `attempts`** — der Grund ist strukturell, nicht ästhetisch:
   Der Nachhol-Pfad entfernt den Marker **vor** dem erneuten Senden (`:425-428`); scheitert der
   Versand wieder, schreibt der `except`-Zweig einen **frischen** Marker mit `attempts=0` (`:460`).
   Ein Zähler kann so nie hochlaufen, ohne durch drei Funktionen durchgereicht zu werden. Der
   **Tagesbezug** (`entry["date"]`) begrenzt ohne jede Durchreichung und passt fachlich: ein
   Morgen-Briefing um 23 Uhr ist wertlos. `attempts` bleibt Diagnosewert, wird nicht Abbruchkriterium.
3. **Rekursionsschutz ist damit strukturell**, nicht zählerabhängig: Ein Marker, dessen Zieltag
   vorbei ist, verfällt — unabhängig davon, ob irgendein Zähler korrekt mitlief.
4. **Beobachtbarkeit fällt kostenlos an** (s.u.).

## Wer merkt es? — der bestehende Melder greift bereits

Gemessen in `henemm-infra/scripts/check-gregor20.sh`:

- Zeile 199-210 alarmiert bei `open_pending_briefings > 0` **und** `oldest_pending_age_hours > 3`.
  Ein nicht nachgelieferter Versandfehler löst damit nach drei Stunden über den **bestehenden,
  verdrahteten** Weg einen externen Alarm aus. Kein neuer Melde-Mechanismus nötig.
- 🔴 **Die #1629-Felder haben dagegen keinen Leser.** `briefing_dispatch_error_streak_since` und
  `briefing_dispatch_errors_recent_count` kommen im gesamten Script **nicht vor**; ausgewertet wird
  nur `provider_error_streak_since` (Zeile 274 ff.). Das wachsende Signal aus #1629 ist gebaut und
  wird von niemandem gelesen — genau die „Signal ohne Leser"-Falle, vor der das
  #1629-Kontextdokument gewarnt hatte.

**Zwei Folgearbeiten im Infrastruktur-Repo** (MQ-Nachricht an `infra`, kein Python-Defekt):
(a) der Alarmtext deckt Versandfehler nicht ab („degradierte Briefing(s)", meldete „0 degradierte
Segmente"); (b) die beiden #1629-Felder auswerten.

## PO-Entscheidungen (2026-08-10) — Grundlage der ACs

- [x] **Begrenzung über den Zieltag**, nicht über den Fehlertyp und nicht über einen Zähler.
      Ausdrücklich abgelöst: die Annahme im Issue-Text, der Allowlist-Fall sei deterministisch und
      dürfe nicht wiederholt werden. `attempts` bleibt reiner Diagnosewert.
- [x] **Telegram wird voll fehlertolerant** (`except Exception` statt `except OutputError`,
      `notification_service.py:390`/`:411`) — analog zu SMS (`:367`). Damit ist E-Mail der einzige
      Kanal, der nach oben durchreicht, und da er zuerst läuft, gilt strukturell: **kommt eine
      Ausnahme am Vermerk an, ging nichts raus.** Das Doppel-Risiko wird beseitigt statt dokumentiert.
- [x] **Ein letzter Zustellversuch**, bevor ein Vermerk bei Fälligkeit verfällt (`:386-388`) — die
      bisherige, nie bewusst getroffene Regel wird damit abgelöst.
- [x] **Kanaltrennung kommt mit in diese Scheibe:** ein E-Mail-Fehler darf SMS und Telegram nicht
      mehr mitreißen. Begründung für die Abkehr von der alten Festlegung
      (`notification_service.py:813-819`, „damit ein SMTP-Ausfall sichtbar bleibt"): Sichtbarkeit
      liefern seit #1629 das Diagnose-Journal und das Health-Signal, zusätzlich künftig der Vermerk —
      dafür muss kein funktionierender Kanal mehr geopfert werden. Direkter Bezug: Garmin-Weg auf
      dem Karnischen Höhenweg ab 20.8. (#1533).

### Auswirkung auf den Zuschnitt

Die Kanaltrennung erhöht die Schätzung auf **~85 LoC** Produktivcode (Limit 250) und ergänzt
`src/services/notification_service.py` als dritte Produktivdatei. Sie berührt **nicht**
`src/output/channels/email.py` — der Empfänger-Guard und die Parity-Ratsche aus #1412 S2a bleiben
unangetastet; die eigentliche Teilzustellung (ein blockierter Empfänger reißt die übrigen nicht mit)
bleibt eine eigene Scheibe.

Nebenbefund aus der Gegenprüfung: Für Trip-Briefings ist `mail_to` einwertig
(`src/app/config.py:122`), die Empfängerliste hat also genau einen Eintrag — die
Mehr-Empfänger-Teilzustellung ist für diesen Pfad heute totes Gleis und betrifft vor allem den
Ortsvergleich.
