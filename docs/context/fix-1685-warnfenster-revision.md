# Kontext: #1685 — Alarm trotz Nennung im Morgenbriefing

**Issue:** https://github.com/henemm/gregor_zwanzig/issues/1685 (`priority:high`, `type:bug`, `area:alerts`, `session:alarm`)
**Workflow:** `fix-1685-warnfenster-revision` · Track: Full Process
**Erstellt:** 2026-08-10

---

## 1. Der Vorfall (aus Nutzersicht)

Am 10.08.2026 um **07:01 CEST** enthielt das Morgen-Briefing des Trips *KHW 403* (Etappe 3/13,
Sillianer Hütte → Obstansersee-Hütte) den Warnblock:

> AMTLICHE WARNUNG · 1 aktiv · Stufe GELB (1/3) · GeoSphere Austria
> **Gewitter** Mo 10.08. · 14:00–22:00 · Ziel · Kartitsch

Rund **3,5 Stunden später** (10:30 CEST) kam als eigenständige Nachricht:

> 1 AMTLICHE WARNUNG · **Gewitter gemeldet.** · WARNSTUFE GELB (niedrigste von drei)
> Gewitter · Gültig: Mo 10.08. · **18:00 — Di 11.08. 03:00** · Route: Ziel
> Quelle: GeoSphere Austria — Kartitsch.

Gleicher Ort, gleiche Gefahr, gleiche Warnstufe, gleiche Quelle. Einziger Unterschied: die Behörde
hat das Gültigkeitsfenster revidiert (Beginn 14:00 → 18:00, Ende 22:00 → 03:00).

**PO-Bewertung im Issue:** *„Ja, die Zeit ist etwas erweitert aber das ist für den Wandernden nicht
relevant. Schaffst du es, das in eine Regel zu kippen OHNE DASS ES ZU KOMPLEX wird?"*

---

## 2. Am Live-System nachgemessen (2026-08-10)

### 2.1 Melde-Gedächtnis der Produktion

`/var/lib/gregor/users/henning/alert_state/5f534011.json` (Trip KHW 403), gelesen als `claude-gregor`:

```
official_alert:region:Kartitsch:thunderstorm:2026-08-10T12:00:00+00:00:2026-08-10T20:00:00+00:00
    -> {"last_reported_value": 2.0, "reported_at": "2026-08-10T05:01:19Z"}   # = 07:01 CEST, Briefing
official_alert:region:Kartitsch:thunderstorm:2026-08-10T16:00:00+00:00:2026-08-11T01:00:00+00:00
    -> {"last_reported_value": 2.0, "reported_at": "2026-08-10T08:30:10Z"}   # = 10:30 CEST, Alarm
```

12:00–20:00 UTC = 14:00–22:00 CEST (Briefing) · 16:00–01:00 UTC = 18:00–03:00 CEST (Alarm).
**Beide Fenster überlappen** (16:00–20:00 UTC gemeinsam), Stufe in beiden Fällen `2.0` (GELB).

### 2.2 Der Versand ist protokolliert

`/var/lib/gregor/users/henning/alert_log.json`:

```
{"entity_id":"5f534011","sent_at":"2026-08-10T08:30:10Z","changes_count":1,"severity":"LOW",
 "hazards":["thunderstorm"],"reason":"official_alert",
 "channels_sent":["email","telegram"],
 "channels_not_sent":[{"channel":"sms","reason":"below_channel_threshold"}]}
```

### 2.3 Kein Einzelfall — zweiter Beleg, andere Quelle, anderer Tag

Im selben Melde-Gedächtnis, einen Tag früher, über **MeteoAlarm Italien**:

```
official_alert:region:Trentino Alto Adige:thunderstorm:2026-08-09T14:00:00+02:00:2026-08-10T01:59:00+02:00
    -> reported_at 2026-08-08T16:15:02Z
official_alert:region:Trentino Alto Adige:thunderstorm:2026-08-09T10:00:00+02:00:2026-08-10T01:59:00+02:00
    -> reported_at 2026-08-09T09:30:14Z
```

Gleiches Ende, Beginn **um 4 h vorverlegt** (14:00 → 10:00), gleiche Stufe. Auch dieser Doppel-Versand
steht im `alert_log` (`2026-08-09T09:30:14Z`). Der Defekt ist also **quellenübergreifend**, nicht
GeoSphere-spezifisch.

### 2.4 Gegenprobe: echte Folgeperioden werden korrekt getrennt

Im selben Melde-Gedächtnis stehen Hitzewarnungen aufeinanderfolgender Tage:

```
Dellach/Kirchbach extreme_heat  2026-08-03T22:00 – 2026-08-04T21:59
Kirchbach         extreme_heat  2026-08-04T22:00 – 2026-08-05T21:59
Friuli            extreme_heat  2026-08-04T10:00 – 2026-08-06T01:59  (+02:00)
Friuli            extreme_heat  2026-08-06T08:00 – 2026-08-06T19:59  (+02:00)
```

Diese Paare **überlappen nicht** (21:59 endet, 22:00 beginnt; 01:59 endet, 08:00 beginnt). Eine
Überlappungs-Regel würde sie unverändert als getrennte, echte Warnungen behandeln. Das ist am
echten Datenbestand geprüft, nicht angenommen.

---

## 3. Ursache im Code

`official_alert_state_key()` — `src/output/renderers/alert/official_alerts.py:407-423`:

```python
if alert.dedup_id:       ident = f"id:{alert.dedup_id}"
elif alert.region_label: ident = f"region:{alert.region_label}"
else:                    ident = f"label:{alert.label}"
vf = alert.valid_from.isoformat() if alert.valid_from else "none"
vt = alert.valid_to.isoformat() if alert.valid_to else "none"
return f"official_alert:{ident}:{alert.hazard}:{vf}:{vt}"
```

Das Gültigkeitsfenster ist **Bestandteil der Identität**. Der Trigger vergleicht per exaktem
Schlüssel-Treffer (`src/services/trip_alert.py:1378-1384`):

```python
prev = state.get(key)
if prev is None or a.level > prev.get("last_reported_value", 0):
    new_or_escalated.append((a, segment_ids))
```

Ändert die Behörde das Fenster, entsteht ein **neuer Schlüssel** → `prev is None` → die Warnung gilt
als neu → eigenständiger Alarm. Identisch im Ortsvergleich (`src/services/compare_official_alert.py:226,230`).

**Das war Absicht** (#1245, PO-Entscheidung 2026-07-15): zwei *echte* Warnperioden derselben Region
und Gefahr sollen getrennt bleiben. Die Absicht ist richtig — sie unterscheidet nur nicht zwischen
„zweite Periode" und „dieselbe Periode, korrigiertes Fenster".

---

## 4. Warum keine stabile Kennung der Behörde hilft

Naheliegender „sauberer" Weg wäre, die von der Quelle gelieferte Warn-ID als `dedup_id` zu
übernehmen. **Am Live-Endpunkt nachgemessen** (`GET warnungen.zamg.at/wsapp/api/getWarningsForCoords`
für Kartitsch, 2026-08-10):

| Warnung | `warnid` | `chgid` | `verlaufid` | Fenster |
|---|---|---|---|---|
| Gewitter (redaktionell) | 4838 | 1 | 3 | 10.08. 18:00 – 11.08. 03:00 |
| Gewitter (Kurzwarnung) | **5** | 0 | 0 | 09.08. 23:00 – 00:00 |
| Gewitter (Kurzwarnung) | **5** | 0 | 0 | 10.08. 00:00 – 01:00 |
| Gewitter (Kurzwarnung) | **5** | 0 | 0 | 10.08. 20:00 – 21:00 |
| Hitze | 10 | 202608100 | 21 / 31 / 41 / 51 | 11.–14.08., je ein Tag |

`warnid` ist **nicht eindeutig**: bei automatischen Kurzwarnungen ist es ein Typ-Code (`5`), der über
viele verschiedene Warnungen hinweg gleich bleibt. Als `dedup_id` verwendet, würden diese echten,
verschiedenen Warnungen zu einer kollabieren. Zudem setzen **fünf von sechs Quellen** überhaupt kein
`dedup_id` (einziger Produzent: `massif_closure.py:67-70`).

⇒ Eine quellenübergreifende Regel auf Basis von **Identität + Gefahr + Zeitüberlappung** ist der
tragfähige Weg; sie funktioniert für GeoSphere und MeteoAlarm gleichermaßen (beide Belege oben).

---

## 5. Bestehende Zusicherungen, die nicht brechen dürfen

| Quelle | Zusicherung | Berührt? |
|---|---|---|
| #1245 AC-1 | Zwei Perioden gleicher Region+Gefahr bleiben in `dedupe_official_alerts` **zwei Einträge** | **Nein** — Fix betrifft nur die Melde-Entprellung, nicht die Anzeige |
| #1245 Known Limitation | „Kein Interval-Merging (PO 2026-07-15): überlappende Perioden werden NICHT zu einem Gesamtzeitraum verschmolzen" | **Nein** — es wird nichts verschmolzen, nur nicht erneut *gemeldet* |
| #1245 AC-4 | Neue Periode T2 ≠ T1 erzeugt eigenen Zustands-Key ohne A zu überschreiben | **Ja, präzisierungsbedürftig** → „T2 **überlappt T1 nicht**". Der bewachende Test (`test_official_alert_dedup_timespan.py:271`) nutzt aneinandergrenzende, **nicht überlappende** Perioden (Mo 04:00–22:00 / Mo 22:00–Di 22:00) und bleibt damit grün |
| #1245 AC-2/AC-3 | Eskalation am selben Zeitraum bzw. bei Massiv-Sperren kollabiert auf Maximum | **Nein** |
| #1460 AC-20/AC-22 | `official_alert:`-Einträge überleben den Briefing-Reset | **Nein** |
| #1614 AC-1/AC-2 | Im Briefing gemeldete Warnung feuert nicht erneut; Eskalation feuert weiterhin | **Nein** — wird erweitert, nicht ersetzt |
| #1086 / F001 | Cross-Source-Kollaps minütlich abweichender Zeiträume | **Nein** — Anzeige-Ebene |
| ADR-0040 | „gemeldet wird eine gerissene Grenze **einmal**; erneut erst bei Verschärfung" | Bestätigt die Richtung |

Kein ADR regelt die Identität amtlicher Warnungen; #1245 notiert selbst, dass eines langfristig
naheliegt.

---

## 6. PO-Entscheidung (2026-08-10, im Dialog eingeholt)

Gewählt: **stumm bei Überlappung, AUSSER die Warnung beginnt ≥ 2 h früher.**

| Zuvor gemeldet | Neu geliefert | Verhalten |
|---|---|---|
| Gewitter Kartitsch 14:00–22:00 GELB | 18:00–03:00 GELB | **still** (später, überlappt) |
| " | 14:00–02:00 GELB | **still** (nur verlängert) |
| " | 12:00–20:00 GELB | **melden** (2 h früher) |
| " | 10:00–18:00 GELB | **melden** (4 h früher) |
| " | 18:00–03:00 ORANGE | **melden** (Stufe gestiegen) |
| " | morgen 14:00–22:00 GELB | **melden** (kein Zeit-Überlapp) |

Begründung für die Asymmetrie: Ein Ereignis, das **früher** eintritt, zwingt zum Umplanen — der
Wanderer ist dann eventuell schon im Gelände. Das ist derselbe Gedanke, den der PO in #1468 wörtlich
als *„höchstrelevant"* bezeichnet hat (dort für die Vorhersage, hier für amtliche Warnungen).
Der am 09.08. gemessene Trentino-Fall (Vorverlegung um 4 h) bleibt damit bewusst ein Alarm.

---

## 7. Betroffene Stellen

**Lesepfad (Entscheidung „melden ja/nein"):**
- `src/services/trip_alert.py:1378-1384`
- `src/services/compare_official_alert.py:224-234`

**Schreibpfad (Melde-Gedächtnis):**
- `src/services/alert_briefing_anchor.py:305-333` (`record_official_alerts_reported`) — geteilte Fassung
- `src/services/trip_alert.py:1387-1402` (Wrapper) · Aufrufer `:1279`, `:1456`
- `src/services/trip_report_scheduler.py:1218-1226` (Trip-Briefing vermerkt, was es gezeigt hat)
- `src/services/compare_official_alert.py:264-273` (**eigene Inline-Kopie** `_record_state`)

**Schlüsselbildung:** `src/output/renderers/alert/official_alerts.py:407-423`
**Präfix-Konstante / Reset:** `src/services/alert_state.py:36`, `:73-101`
**Taktung:** beide Prüfer laufen `*/15` (`internal/scheduler/scheduler.go:145`, `:156`)

---

## 8. Nebenbefund — eigener Defekt, NICHT Teil dieser Scheibe

**Das Ortsvergleich-Briefing vermerkt gezeigte amtliche Warnungen überhaupt nicht.**
`scheduler_dispatch_service.py:453-464` schreibt nur Anker + Reset; ein Gegenstück zu
`trip_report_scheduler.py:1218-1226` fehlt. Der Compare-Prüfer (`*/15`) kennt die im
Vergleichs-Briefing gezeigten Warnungen daher nicht als „gemeldet" und schickt sie erneut als
eigenständigen Alarm. #1614 hat diese Lücke nur auf der Trip-Seite geschlossen.

Nutzersichtbares Fehlverhalten ⇒ eigenes Issue (Triage-Kriterium a), nicht Sammel-Eintrag.

Weitere, geringere Befunde für #1199:
- `trip_alert.py:434` liest im Vorfilter nur das Legacy-Feld `official_alert_triggers_enabled`,
  nicht `official_warnings.enabled` (der eigentliche Prüfer `:1307` liest beide).
- Trip-Prüfer wertet `official_warnings.sources` nicht aus; der Compare-Prüfer (`:130`, `:213-215`) schon.
- Briefing und Prüfer holen mit **verschiedenen Fenstern**; `get_official_alerts_with_status`
  (`official_alerts/base.py:163-186`) kann dadurch je Lauf eine andere „beste Quelle" wählen und
  damit einen anderen Schlüssel erzeugen.
