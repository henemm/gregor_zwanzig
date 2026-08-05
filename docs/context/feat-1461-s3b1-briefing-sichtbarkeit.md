# Context: feat-1461-s3b1-briefing-sichtbarkeit

**Issue:** #1461 (Epic #1458, Scheibe S3) — Teilscheibe **S3b-1**
**Vorgänger:** S3a live (`cf7d8fc0`), #1503 live (`61165987`), #1459 (Protokoll) live
**Nachfolger:** S3b-2 — die einstellbare Dringlichkeits-Schwelle je Kanal

## Request Summary

Das Briefing soll zeigen, welche Alarme einen Kanal **nicht** erreicht haben. Das ist
Pflicht 2 aus #1461 („was ein Kanal nicht bekommen hat, wird protokolliert **und im nächsten
Briefing sichtbar**") und die Voraussetzung dafür, dass S3b-2 keine Meldungen still
verschwinden lässt (rote Linie #638).

## Der Befund, der die Scheibe begründet

Das Alarm-Protokoll aus #1459 hat **sechs Schreibstellen und null Leser** auf der
Python-Seite — gemessen:

| Schreibstelle | Datei:Zeile | Auslöser |
|---|---|---|
| Trip / Vorhersage-Änderung | `src/services/trip_alert.py:278` | `REASON_FORECAST_CHANGE` |
| Trip / Radar-Nowcast | `src/services/trip_alert.py:877` | `REASON_NOWCAST` |
| Trip / amtliche Warnung | `src/services/trip_alert.py:1150` | `REASON_OFFICIAL_ALERT` |
| Compare / Vorhersage-Änderung | `src/services/compare_alert.py:192` | `REASON_FORECAST_CHANGE` |
| Compare / Radar | `src/services/compare_radar_alert.py` | `REASON_NOWCAST` |
| Compare / amtliche Warnung | `src/services/compare_official_alert.py:150` | `REASON_OFFICIAL_ALERT` |

Gelesen wird es ausschließlich von **Go** (`internal/store/log.go`) für die Cockpit-Kachel
und die Archiv-Statistik — und zwar **nur** der Schlüssel `entries`, **nie** `not_delivered`
(Zusicherung D4 aus #1459). Kein Renderer, kein Scheduler, keine Mail liest das Protokoll.

## Datenlage: was im Protokoll steht

`src/services/alert_log.py` — Read-Modify-Write über die volle Datei
`data/users/<user_id>/alert_log.json`. Zwei Top-Level-Schlüssel:

* **`entries`** — mindestens ein Kanal war **erreichbar**. Enthält pro Eintrag
  `channels_sent` (Liste) und `channels_not_sent` (Liste aus `{channel, reason}`).
* **`not_delivered`** — **kein** Kanal erreichbar. Für Go unsichtbar (D4).

Pro Eintrag außerdem: `entity_id` + `entity_type` (`"trip"`|`"compare"`, seit #1467 S1
genau EINE Kennung), `sent_at` (UTC-ISO), `changes_count`, `severity`, `metrics`
(Register-Paare), `hazards`, `reason`.

Gründe einer Nicht-Zustellung (`alert_log.py:44-48`), bewusst freie Strings, damit
S3b-2 additiv „unter der Kanal-Schwelle" ergänzen kann:
`channel_disabled` · `delivery_failed` · `quiet_hours` · `daily_limit` · `cooldown`.
**Gemessen: nur die ersten beiden werden heute von einem Aufrufer gesetzt** —
`quiet_hours`/`daily_limit`/`cooldown` sind dokumentiert, aber tot (O3 aus #1459: zum
Gate-Zeitpunkt ist der Auslöser noch nicht bekannt).

⇒ **Zwei Quellen für „hat einen Kanal nicht erreicht":** `channels_not_sent` innerhalb von
`entries` (Teilausfall) **und** die ganzen Einträge in `not_delivered` (Totalausfall).

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/alert_log.py` | Schreibfunktion + Schema; hier gehört die neue **Lesefunktion** hin (kein neuer präfigierter Renderer → Pendant-Sperre #1481 B) |
| `src/services/alert_briefing_anchor.py` | **Die Naht „nächstes Briefing"** — schreibt den Δ-Anker und leert das Melde-Gedächtnis. Wird von Trip **und** Compare gerufen; `on_demand=True` ⇒ passiert nichts |
| `src/services/notification_service.py` | Baut das Trip-Briefing (`TripReportFormatter`, Z.263) und ruft alle Kanäle (`effective_channels`, Z.467ff) |
| `src/services/trip_report_scheduler.py` | Der Auslöser des geplanten Briefings; `_reset_alert_state_after_briefing` delegiert an den Anker-Baustein |
| `src/output/renderers/email/__init__.py:34` | `render_email()` — **reine Funktion**, „identical inputs → bit-identical output". Neue Daten müssen als kwarg hereingereicht werden, der Renderer darf nichts nachladen |
| `src/output/renderers/email/html.py`, `plain.py`, `compact.py` | Die drei Trip-Mail-Ausgaben (HTML full, Klartext, compact) |
| `src/output/renderers/narrow.py`, `sms_trip.py` | Telegram-Kurzform / SMS — 160 Zeichen, hier passt allenfalls eine Zahl |
| `src/output/renderers/email/compare_html.py` | Ortsvergleichs-Mail |
| `src/output/renderers/email/unavailable_hint.py` | **Das Vorbild**: kleiner Briefing-Hinweisblock, HTML + Klartext + Telegram, an vier Stellen eingebunden, bewusst NICHT unter `renderers/alert/` abgelegt, damit das Warn-Renderer-Gate unberührt bleibt |
| `src/output/renderers/email/outlook_state_hint.py` | Zweites Exemplar derselben Bauart (#1349) — DRY-Vorbild |
| `internal/store/log.go` | Go-Leser; `AlertCountByEntity()` zählt **Einträge**, nicht Kanäle (D1) |

## Existing Patterns

1. **Hinweisblock im Briefing** (`unavailable_hint.py`, `outlook_state_hint.py`): ein Modul mit
   (a) einer Prüffunktion auf den Daten, (b) `…_html()`, (c) `…_plain()`; eingebunden in
   `html.py`, `plain.py`, `compact.py`, `narrow.py` und `compare_html.py`. Genau der Zuschnitt,
   den S3b-1 braucht.
2. **Geteilter Baustein statt zwei Zweigen** (`alert_briefing_anchor.py`, `alert_log.py`,
   `alert_urgency.py` aus S3a): ein Modul in `src/services/`, von Trip- und Compare-Pfad
   gleichermaßen gerufen. PO-Vorgabe wörtlich: „Verwende zwingend den gleichen Code."
3. **Renderer bleibt rein**: Domänenwerte rechnet der Aufrufer (`TripReportFormatter`), der
   Renderer bekommt sie als expliziten kwarg (Spec §A1+§A5+§A6).
4. **Fail-soft beim Lesen**: `alert_log.append_entry()` fängt kaputte Dateien ab und macht
   weiter — eine unlesbare Protokolldatei darf ein Briefing nicht verhindern.

## Dependencies

* **Upstream** (was wir lesen): `alert_log.json` je Nutzer über `app.loader.get_data_dir()`;
  `app.metric_catalog` für sprechende Namen der Register-Paare; `output.metric_format` für
  ordinale Größen (nie roh — s. #1503/#1474).
* **Downstream** (was auf uns aufbaut): S3b-2 (die Schwelle) hängt an dieser Sichtbarkeit;
  der neue Grund „unter der Kanal-Schwelle" kommt dort additiv dazu.

## Existing Specs

| Spec | Inhalt |
|---|---|
| `docs/specs/modules/feat_1459_alert_protokoll.md` | Schema, D1/D4, O1–O3 |
| `docs/specs/modules/feat_1461_s3a_alarm_dringlichkeit.md` | Einstufung (v1.4, 16 ACs) |
| `docs/specs/modules/fix_1503_delta_dringlichkeit.md` | Δ-Einstufung, ordinale Sonderbehandlung |
| `docs/specs/modules/rework_1467_s1_alarm_kennung.md` | `entity_id`/`entity_type` |
| `docs/specs/modules/rework_1467_s2_aenderungsalarm.md` | AG5 = Briefing-Anker |
| `docs/specs/modules/output_channel_renderers.md` | §A1/§A5/§A6 — Renderer-Reinheit |

## Risks & Considerations

1. **🔴 Doppelzählung.** Treffen Vorhersage-Änderung, amtliche Warnung und ein kompletter
   Versandausfall zusammen, entstehen **zwei** `not_delivered`-Einträge für **eine**
   Nutzer-Meldung (drei getrennte `append_entry`-Aufrufe im selben Lauf). Wer zählt, zählt
   doppelt. Entweder je Meldung entdoppeln (`sent_at` + `entity_id` + `reason`) oder den
   Pfad mitbereinigen. Vom PO in #1461 (Kommentar 2026-08-02) ausdrücklich dieser Scheibe
   zugewiesen. Die im Kommentar genannten Zeilen `trip_alert.py:526-536` sind **veraltet** —
   der Code ist seither verschoben; die Fundstelle ist über die drei `append_entry`-Aufrufe
   zu bestimmen, nicht über die Zeilennummer.
2. **Zeitraum unbestimmt.** „Seit dem letzten Briefing" hat heute **keinen gespeicherten
   Anker**: es gibt `throttle_store.last_sent()` (Alarm-Drossel, nicht Briefing) und den
   Δ-Anker (Wetterwerte, kein Zeitstempel je Trip). Muss in der Analyse entschieden werden —
   Kandidaten: Zeitstempel beim Anker-Schreiben mitführen, oder fester Rückblick.
3. **Renderer-Commit-Gate (#811)** greift, sobald `email/*.py`, `trip_report.py`,
   `compact_summary.py`, `sms_trip.py` oder `channels/email.py` angefasst werden: verlangt
   `tests/tdd/test_issue_811_mode_matrix.py` grün **plus** frischen
   `briefing_mail_validator.py`-Lauf gegen eine echt zugestellte Staging-Mail.
4. **Pendant-Sperre (#1481 B):** keine neu angelegte Datei unter
   `frontend/src/lib/components/{compare,compare-new,trip-detail,trip-new}/**` und kein neuer
   Renderer mit `compare_`/`trip_`-Präfix. Der geteilte Baustein gehört nach `src/services/`
   bzw. — für den Darstellungsteil — neben `unavailable_hint.py`.
5. **D4 muss halten:** Cockpit-Kachel und Archiv-Statistik dürfen sich um **keine Zahl**
   ändern. Sie lesen `entries`; `not_delivered` bleibt für Go unsichtbar. Reines Lesen ist
   dafür unkritisch — sobald aber entdoppelt/umgeschrieben wird, ist es die Hauptgefahr.
6. **Mandantentrennung:** `alert_log.json` liegt je Nutzer; die Lesefunktion braucht die echte
   `user_id`, nie `"default"`. Mit **zwei** Nutzern zu testen.
7. **SMS/Telegram-Enge:** Die Kurznachricht nennt keinen Ort und hat 160 Zeichen — dort ist
   höchstens eine Zahl unterzubringen, nicht die Liste.
8. **Leerer Normalfall:** Der überwiegende Fall ist „alles zugestellt". Der Abschnitt darf dann
   **nicht** erscheinen — sonst steht in jedem Briefing eine Null-Zeile.
9. **Determinismus:** `render_email()` sichert bit-identische Ausgabe bei gleicher Eingabe zu.
   Zeitstempel und „jetzt" müssen von außen hereingereicht werden.

---

# Analysis

## Type

**Feature** (Epic-Scheibe, kein Fehlverhalten im Bestand).

## PO-Entscheidungen 2026-08-05

| Frage | Entscheidung |
|---|---|
| Detailtiefe | **Je Meldung eine Zeile** — Zeitpunkt · worum es ging · welcher Kanal · warum. Gedeckelt, darunter „und N weitere" |
| Umfang | **Beide Fälle** — Totalausfall *und* Teilausfall („E-Mail kam an, SMS nicht") |
| Kanäle | **Nur E-Mail.** Telegram-Kurzform und SMS bleiben **unberührt** |

Abgeleitete Routine-Entscheidungen (keine Rückfrage nötig, in der Spec festzuhalten):
* E-Mail heißt **beide** Mail-Formate (`full` **und** `compact`) — beides sind E-Mails.
* Trip **und** Ortsvergleich bekommen denselben Baustein (Teilungs-Gate, PO-Vorgabe
  „Verwende zwingend den gleichen Code").

## Technischer Ansatz

**Drei Bausteine, keiner davon neu erfunden.**

### 1. Lesen — `src/services/alert_log.py` (MODIFY)

Neue reine Lesefunktion neben `append_entry()`. Liefert für **eine** Kennung
(`entity_id` + `entity_type`) und einen Zeitraum die Meldungen, die mindestens einen Kanal
nicht erreicht haben. Speist sich aus **beiden** Quellen:

* `entries[*].channels_not_sent` — Teilausfall
* `not_delivered[*]` — Totalausfall (dort ist per Definition **jeder** Kanal betroffen)

Fail-soft wie die Schreibseite: unlesbare Datei ⇒ leeres Ergebnis + Warnung, nie eine
Ausnahme ins Briefing.

**Entdoppelung** (Risiko 1) an genau dieser Stelle: mehrere Einträge derselben Kennung mit
demselben Zeitstempel-Fenster und **verschiedenem** `reason` sind **ein** Vorfall für den
Nutzer, keine drei. Das Protokoll selbst bleibt unangetastet — es wird nur beim Lesen
zusammengefasst. Damit bleibt D4 zwingend gewahrt: an `entries` und `not_delivered` wird
nichts geschrieben, Cockpit-Zahl und Archiv-Statistik ändern sich um nichts.

### 2. Zeitraum — `src/services/alert_briefing_anchor.py` (MODIFY)

„Seit dem letzten Briefing" hat heute keinen Anker. Der **richtige Ort** ist der bestehende
geteilte Baustein: er wird in **beiden** Pfaden **nach** dem Versand gerufen
(`trip_report_scheduler.py:983`, `scheduler_dispatch_service.py:413`) und ist bereits die
Definition von „ein Briefing ist rausgegangen". Dort zusätzlich einen Zeitstempel je Kennung
fortschreiben; das Briefing liest **vorher** den alten Wert.

Die Reihenfolge ist damit von selbst richtig — gerendert wird vor dem Fortschreiben. Ein
`on_demand`-Abruf schreibt nichts fort (Bestandsverhalten, Issue #1007), zeigt den Hinweis
aber trotzdem an.

**🔴 Fallstrick, gemessen:** Der Anker-Baustein bekommt im Compare-Fall
`entity_ids = [f"{preset_id}:{loc.id}", …]` (je Ort), das **Protokoll** schreibt dagegen
`entity_id = preset_id` (`compare_alert.py:193`, `compare_official_alert.py:151`). Wer den
Briefing-Zeitstempel unter den Anker-Kennungen ablegt, findet beim Lesen **nie** einen
Treffer und zeigt dauerhaft einen leeren Hinweis. Die Kennung für den Zeitstempel muss die
**Protokoll-Kennung** sein.

Fehlt der Zeitstempel (erstes Briefing nach der Auslieferung, Bestandsnutzer): kein
Rückblick über unbestimmte Vergangenheit, sondern ab jetzt — sonst kippt beim ersten
Briefing die gesamte Historie in die Mail.

### 3. Anzeigen — `src/output/renderers/email/undelivered_hint.py` (CREATE)

Bauform 1:1 nach `unavailable_hint.py` (#1348) und `outlook_state_hint.py` (#1349): ein
Modul mit einer HTML- und einer Klartext-Fassung, eingebunden in `html.py`, `plain.py`,
`compact.py` und `compare_html.py`. Bewusst **nicht** unter `renderers/alert/` — es ist ein
Briefing-Baustein, kein Alarm-Renderer; so bleibt das Warn-Renderer-Gate unberührt (die
Begründung steht wörtlich im Kopf von `unavailable_hint.py`).

Der Dateiname trägt **kein** `trip_`/`compare_`-Präfix ⇒ Pendant-Sperre (#1481 B) greift nicht.

Hochkontrastig nach dem Design-Leitprinzip (Token `G_BOX_DANGER_BG`/`G_DANGER`, **kein**
`G_INK_FAINT`). Wettergrößen über `app.metric_catalog` in Klartext, ordinale Größen über
`output.metric_format.thunder_ordinal()` — nie roh (#1503/#1474).

**Leerer Normalfall ⇒ der Block erscheint gar nicht.** Kein „0 Meldungen".

### Durchreichung

`render_email()` sichert bit-identische Ausgabe bei gleicher Eingabe zu und darf nichts
nachladen. Die geladenen Daten wandern deshalb als **expliziter kwarg** durch
`notification_service` → `TripReportFormatter.format_email()` → `render_email()` (Muster
§A1/§A5/§A6). Ohne den kwarg (Vorschau, Golden-Tests, CLI) verhält sich alles wie bisher.

## Affected Files

| Datei | Änderung | Inhalt |
|---|---|---|
| `src/services/alert_log.py` | MODIFY | Lesefunktion + Entdoppelung |
| `src/services/alert_briefing_anchor.py` | MODIFY | Briefing-Zeitstempel je Protokoll-Kennung |
| `src/output/renderers/email/undelivered_hint.py` | CREATE | HTML- + Klartext-Baustein |
| `src/output/renderers/email/html.py` | MODIFY | Einbindung (Mail `full`) |
| `src/output/renderers/email/plain.py` | MODIFY | Einbindung (Klartext) |
| `src/output/renderers/email/compact.py` | MODIFY | Einbindung (Mail `compact`) |
| `src/output/renderers/email/compare_html.py` | MODIFY | Einbindung (Ortsvergleich) |
| `src/output/renderers/email/__init__.py` | MODIFY | kwarg durchreichen |
| `src/output/renderers/trip_report.py` | MODIFY | kwarg durchreichen |
| `src/services/notification_service.py` | MODIFY | Daten laden, echte `user_id` |
| `src/services/scheduler_dispatch_service.py` | MODIFY | dito für den Ortsvergleich |
| `tests/tdd/test_alert_undelivered_hint.py` | CREATE | Verhaltensnachweis |

**Unberührt:** `narrow.py`, `sms_trip.py`, `compact_summary.py` (PO: Kurznachricht bleibt
unberührt) · `internal/store/log.go` und die gesamte Go-Seite · das Frontend.

## Scope Assessment

* Dateien: **11 geändert, 2 neu**
* Geschätzt: **~280–320 Zeilen inkl. Tests**
* Risiko: **MEDIUM** — nur additive Anzeige, kein Eingriff in den Versand; die Gefahr liegt
  in der Entdoppelung (D4) und in der Kennungs-Verwechslung beim Compare-Zeitstempel

⚠️ **Die 250-Zeilen-Grenze je Arbeitsgang wird voraussichtlich gerissen.** Der Treiber ist
nicht der Ortsvergleich (dessen Einbindung sind ~20 Zeilen, weil der Baustein geteilt ist),
sondern die vier Einbindungsstellen plus die Testabdeckung. Ein Anheben der Grenze ist
PO-Entscheidung und wird erst erfragt, wenn sie tatsächlich erreicht ist.

## Open Questions

- [x] Detailtiefe — beantwortet: je Meldung eine Zeile
- [x] Umfang — beantwortet: beide Fälle
- [x] Kanäle — beantwortet: nur E-Mail
- [ ] Deckelung: bei wie vielen Zeilen abschneiden? (Vorschlag 5 — wird in der Spec
      vorgelegt, keine eigene Rückfrage)
