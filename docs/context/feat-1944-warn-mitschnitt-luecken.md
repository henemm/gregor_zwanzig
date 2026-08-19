# Context: feat-1944-warn-mitschnitt-luecken

Issue: #1944 — „Amtliche Warnungen: Roh-Payload bei jedem Trigger-Lauf rollierend
mitschneiden (Beweisaufnahme, Scheibe 2 aus #1929)". Vorgänger-Lieferung: #1948 S1.

## Request Summary

Der Mitschnitt des rohen Eingangs-Datensatzes amtlicher Warnungen existiert seit #1948 S1,
hat aber zwei Lücken: (a) ein Abruf aus dem Zwischenspeicher hinterlässt keinen Datensatz,
(b) der `alert_log`-Eintrag einer amtlichen Warnung trägt keine Verknüpfung zum Datensatz,
der sie ausgelöst hat. Ohne (b) bleibt der Vorfall aus #1929 auch mit Mitschnitt
unentscheidbar — das ist der eigentliche Zweck des Tickets.

## Was #1948 S1 bereits liefert (Ist-Stand, `origin/main` e273c983)

| Fähigkeit | Stelle | Status |
|---|---|---|
| Roh-Payload amtlicher Warnungen wird zentral mitgeschnitten | `src/services/official_alerts/warn_egress.py:391-401` | ✅ erledigt |
| Abdeckung **aller** Warnquellen in einem Zug | alle 7 Quellen rufen `cached_fetch` (`geosphere_warn`, `meteoalarm`, `meteoalarm_feed`, `dpc`, `vigilance`, `massif_closure`, `meteo_forets`) | ✅ erledigt |
| Rollierende Aufbewahrung | `alert_input_capture._prune`, 50 Datensätze je Ablage | ✅ erledigt |
| Kein Auth-/Header-Leck | `capture_system` nimmt strukturell keine Header entgegen (AC-7) | ✅ erledigt |
| Korrelation Vorfall → Datensatz | — | ❌ **offen (Zweig b)** |
| Mitschnitt bei Zwischenspeicher-Treffer | — | ❌ **offen** |

Die #1948-Spec (`docs/specs/modules/alarm_eingangsprotokoll.md`, Sektion „Known
Limitations") führt beide Punkte ausdrücklich als zurückgestellt und benennt das
Folge-Ticket. Dieser Workflow ist dieses Folge-Ticket.

## Warum die Korrelation der Kern ist (Bezug #1929)

Der Vorfall (Trip `5f534011`, 2026-08-16): zwei amtliche Warnmeldungen mit byte-identischem
Kurztext. Die verbliebene, ex post nicht entscheidbare Hypothese lautet: *der tatsächlich
versendete Alert war ein anderer als der für den State geprüfte*. Diese Frage beantwortet
ein Mitschnitt nur, wenn feststeht, **welcher** Mitschnitt zu **welcher** versendeten
Meldung gehört. Ein Mitschnitt ohne Zuordnung beweist nichts.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/official_alerts/warn_egress.py:353-401` | Zwischenspeicher-Ausstieg (Z. 353-364) liegt **vor** dem Mitschnitt (Z. 391) — Ursache von Lücke (a). Eintrag je Schlüssel: `{"data", "fetched_at", "ttl"}` |
| `src/services/alert_input_capture.py:91-162` | `capture_system(branch, source_key, payload)`, `latest_capture_id(branch, source_key, max_age)` — vorhandenes Werkzeug, kein Neubau nötig |
| `src/services/trip_alert.py:1671-1780` | `_send_official_alert_only` — Versandpunkt Trip; `alert_log.append_entry(...)` bei Z. 1765 **ohne** `capture_id=` |
| `src/services/compare_official_alert.py:201-214` | Versandpunkt Ortsvergleich — ebenfalls **ohne** `capture_id=` |
| `src/services/trip_alert.py:1357-1373` | **Vorbild Nowcast**: `latest_capture_id("nowcast", _nowcast_source_key(lat, lon), max_age=300.0)` → `capture_id=` an `append_entry` |
| `src/services/alert_log.py:159/239, 268/335` | `capture_id` ist als optionales Feld bereits vorhanden und additiv — Protokoll-Seite braucht keine Änderung |
| `src/services/official_alerts/models.py:15-33` | `OfficialAlert` — frozen dataclass, alle Felder ab `valid_from` mit Default; ein additives Herkunftsfeld wäre bruchfrei |
| `src/services/official_alerts/base.py:24-36` | `OfficialAlertSource`-Protokoll; `fetch(lat, lon) -> list[OfficialAlert]` ist die gemeinsame Naht aller Quellen |

## Existing Patterns

- **Korrelation über Zeitfenster-Lookup** (Zweig c/Nowcast): Quell-Schlüssel trägt die
  Koordinate (`_nowcast_source_key(lat, lon)`), Fenster = Cache-Haltedauer des Zweigs.
- **Additive optionale Felder** statt Signaturbruch (`capture_id` in `alert_log`,
  `dedup_id` in `OfficialAlert`).
- **Fail-open bei Beobachtungs-Code**: jeder Mitschnitt fängt alle Ausnahmen, loggt eine
  Warnung, gibt `None` zurück — ein Beobachtungsfehler darf nie einen Alarm verhindern
  (#1948 AC-8).
- **Rollierende Datei-Retention** nach Vorbild `weather_snapshot._prune_dated_snapshots`.

## Dependencies

- **Upstream:** `alert_input_capture` (Schreiben/Lookup), `warn_egress.cached_fetch`
  (einziger Netzweg aller Warnquellen), TTL-Konstanten `WARN_SUCCESS_TTL=1800`,
  `WARN_FAILURE_TTL=60`, `WARN_NOT_COVERED_TTL=86400`.
- **Downstream:** `alert_log` (beide Schreibfunktionen), Versandpfade Trip **und**
  Ortsvergleich, sowie die Auswertung der Messlatte aus #1458 (K1 stützt sich auf das
  Protokoll).

## Existing Specs

- `docs/specs/modules/alarm_eingangsprotokoll.md` — #1948 S1, AC-1..AC-9 plus die
  „Known Limitations", die diesen Zuschnitt definieren.
- `docs/specs/modules/feat_1459_alert_protokoll.md` — Protokoll-Grundlage.
- `docs/specs/modules/fix_1422_warn_ausfall_alarm.md` — Verhalten von `cached_fetch` bei
  Ausfall/Kontingent, muss unberührt bleiben.

## Risks & Considerations

1. **Falsche Zuordnung ist schlimmer als keine.** Ein reiner Lookup über den
   Dienstnamen (Vorschlag im Issue-Body) trifft bei mehreren Orten/Trips derselben Quelle
   den jüngsten fremden Datensatz. Der Quell-Schlüssel muss so fein sein wie der
   Zwischenspeicher-Schlüssel — dieser ist provider-spezifisch gerundet
   (`_round_coord(lat, lon)`), und genau dieses Wissen liegt am Versandpunkt **nicht** vor.
   Das war der dokumentierte Grund für die Zurückstellung in #1948 und ist die zentrale
   Designfrage für `/20-analyse`.
2. **Zwischenspeicher-Treffer brauchen keinen neuen Schreibvorgang.** Trägt der
   Zwischenspeicher-Eintrag die Kennung seines Ursprungsabrufs mit, ist die Zuordnung bei
   einem Treffer exakt — ohne zusätzliche Schreiblast. Das entspricht der PO-Vorgabe
   „schlanker Verweis statt Vollmitschnitt" (Annahme aus dem Intake, siehe unten).
3. **`cached_fetch` ist heißer, geteilter Pfad.** Alle sieben Warnquellen und der
   Kontingent-/Ratenbremsen-Mechanismus (#1397, #1422) hängen daran. Bestehende Aufrufer
   müssen bit-identisch weiterlaufen; jede Erweiterung additiv mit Default.
4. **Aufkommen nicht messbar aus dieser Sitzung.** `/var/lib/gregor` ist nicht lesbar, die
   reale Datensatzrate lässt sich hier nicht prüfen. Die Aufbewahrungsgrenze (50) bleibt
   damit eine Schätzung; ob sie für eine Vorfallanalyse Tage später reicht, ist offen und
   gehört als Frage in die Spec.
5. **Kein sichtbares Verhalten ändern.** Reine Beweisaufnahme — Alarm-Auslösung, -Inhalt
   und -Format bleiben unverändert. `official_alerts.py:1896-2104` bleibt Sperrzone (#1929).
6. **Beide Flächen.** Trip **und** Ortsvergleich verwenden denselben Versandbaustein-Kreis;
   eine Lösung nur für den Trip wäre ein Paritätsverstoß (#1533).

## Annahme aus dem Intake (PO, 2026-08-18)

Auf die Frage „Vollmitschnitt bei Zwischenspeicher-Treffern oder schlanker Verweis?" kam
die Freigabe ohne abweichende Vorgabe. Es gilt die abgegebene Empfehlung: **schlanker
Verweis** — bei einem Treffer wird kein neuer Datensatz geschrieben, sondern die Kennung
des Ursprungsabrufs weitergereicht. Diese Annahme wird in der Spec sichtbar ausgewiesen.

## Bestehende Tests, die den Bestand bewachen

`tests/test_warn_egress_capture.py` (AC-2), `test_alert_log_capture_correlation.py` (AC-4),
`test_alert_input_capture_retention.py` (AC-5), `test_warn_egress_capture_no_secrets.py`
(AC-7), `test_alert_input_capture_failopen.py` (AC-8) — alle müssen grün bleiben; die
Erweiterung ist additiv.

---

## Analysis

### Type
Feature (Beweisaufnahme-Erweiterung, kein sichtbares Verhalten)

### Entscheidung: Herkunft mitführen statt nachträglich raten

Der im Issue-Body vorgeschlagene Weg — am Versandpunkt per Zeitfenster-Lookup über den
Dienstnamen (`latest_capture_id`, Vorbild Nowcast) — ist **nicht baubar**. Zwei
unabhängige, je für sich ausreichende Gründe:

1. **Namens-Bruch.** `OfficialAlert.source` ist nicht der Schlüssel, unter dem der
   Mitschnitt abgelegt wird. Vigilance meldet sich als `meteofrance_vigilance`
   (`vigilance.py:130`), schreibt aber unter `vigilance` (`vigilance.py:94`); der
   MeteoAlarm-Feed meldet `meteoalarm`, schreibt aber `meteoalarm_feed:AT` bzw. `:IT`
   (`meteoalarm_feed.py:212`). Der Lookup fände für diese Quellen **nie** einen Datensatz.
2. **Zu grobe Körnung — führt zu falscher Zuordnung.** Der Mitschnitt-Schlüssel ist der
   konstante Dienstname (`warn_egress.py:393`), der Zwischenspeicher-Schlüssel dagegen die
   provider-gerundete Koordinate (`geosphere_warn.py:90`). Liegen zwei Touren im selben
   Prüftakt bei derselben Quelle (Innsbruck/Salzburg über GeoSphere), entstehen zwei
   Datensätze unter identischem Schlüssel; der Lookup nimmt den jüngeren — je nach
   Verarbeitungsreihenfolge in rund der Hälfte der Fälle den **fremden**. Das verletzt die
   Randbedingung „falsche Zuordnung ist schlimmer als keine" nicht theoretisch, sondern im
   Regelbetrieb mit mehreren Touren.

Gewählt wird daher: **die Kennung des Mitschnitts wird von ihrer Entstehung bis zum
Protokolleintrag mitgeführt**, statt sie hinterher zu rekonstruieren.

- Rückkanal nach dem im selben Modul bereits etablierten Muster `_fetch_failure_sink`
  (`warn_egress.py:56-98`, `contextvars`) — kein neues Verfahren.
- Die Kennung wandert zusätzlich in den Zwischenspeicher-Eintrag. Damit liefert ein
  Treffer die Kennung des Ursprungsabrufs — **Lücke (a) ist ohne einen einzigen
  zusätzlichen Schreibvorgang geschlossen** (deckt sich mit der Intake-Annahme
  „schlanker Verweis").
- Anreicherung zentral an der einen Naht, durch die alle Quellen laufen
  (`base.py:148`, `dataclasses.replace`) — die sieben Quellen bleiben unangetastet.
- Der Rückgabewert von `cached_fetch` bleibt unverändert; alle Bestandsaufrufer laufen
  bit-identisch weiter.

### Affected Files (with changes)

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/official_alerts/warn_egress.py` | MODIFY | Rückkanal für die Kennung; Kennung in die Zwischenspeicher-Einträge (Lücke a) |
| `src/services/official_alerts/models.py` | MODIFY | additives Feld `capture_id: Optional[str] = None` an `OfficialAlert` |
| `src/services/official_alerts/base.py` | MODIFY | Anreicherung an der gemeinsamen Naht (Z. 148) |
| `src/services/official_alerts/massif_closure.py` | MODIFY | mehrfacher Abruf je Aufruf: Kennung an die gewinnende Meldung binden statt raten |
| `src/services/trip_alert.py` | MODIFY | `capture_id=` an den Protokolleintrag (~Z. 1765) |
| `src/services/compare_official_alert.py` | MODIFY | dito für den Ortsvergleich (Z. 201-214), Parität |
| `tests/…` | CREATE/MODIFY | siehe TDD-Phase |

### Scope Assessment
- Dateien: 6 (plus Tests)
- Geschätzte LoC: **+65 bis +100** — innerhalb des Limits von 250
- Risiko: **MEDIUM** — geteilter Abrufweg aller Warnquellen, aber rein additiv und fail-open

### Risiko-Schwerpunkte (aus der Bewertung)

1. **Mehrfach-Abrufe je Quellen-Aufruf.** `massif_closure.py:132-140` ruft den Abrufweg in
   einer Schleife und behält nur die stärkste Meldung. Ein naives „letzter gewinnt" würde
   die Kennung eines **nicht** gewählten Massivs anhängen. Regel: bei Mehrdeutigkeit
   **keine** Kennung statt einer falschen.
2. **Wiederholung nach Ratenbremse** (`warn_egress.py:410-430`): jeder Zwischenversuch
   erzeugt einen eigenen Mitschnitt. Der Zwischenspeicher-Eintrag muss die Kennung des
   **letzten tatsächlich verwerteten** Abrufs tragen, nicht die eines Zwischenversuchs.
3. **Die stillgelegte MeteoAlarm-Quelle** (`official_alerts/__init__.py:31-34`) ruft den
   Abrufweg bis zu dreimal je Meldung. Sie ist heute inaktiv, der Mechanismus muss aber so
   gebaut sein, dass eine Reaktivierung nicht still falsch zuordnet.

### Offene Frage → Entscheid in der Spec

Der Protokolleintrag hat **ein** Kennungs-Feld, die versendete Meldung kann aber aus
**mehreren** Mitschnitten stammen (mehrere Quellen im Trip-Pfad; mehrere Orte im
Ortsvergleich). Vorgeschlagener Entscheid, in der Spec sichtbar zu machen:

- Stammen alle Meldungen eines Versands aus **einem** Mitschnitt → dieses Feld wie bisher
  belegen (bestehende Auswertungen greifen unverändert).
- Stammen sie aus **mehreren** → zusätzlich alle beteiligten Kennungen entdoppelt
  festhalten, statt eine willkürlich auszuwählen. Genau dieser Fall ist der Vorfall aus
  #1929 (zwei Meldungen, gleicher Anzeigetext) — eine willkürliche Auswahl würde die
  Frage, die das Ticket beantworten soll, wieder verschließen.
