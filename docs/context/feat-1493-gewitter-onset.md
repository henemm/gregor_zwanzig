# Context: feat-1493-gewitter-onset

> Phase 1+2 zu Issue #1493 — „Gewitter S7: Onset — 'Gewitter wahrscheinlich ab
> 14:00' in der Stundenvorhersage". Aus Epic #1419, Abschnitt 6 / S7.
> Erstellt 2026-08-17, Basis `c37a71f6` (= `origin/main` = Prod-Stand).
>
> **Hinweis:** Die erste Fassung ging verloren, als eine fremde Aufräum-Aktion
> den Worktree `slot-1599` per `git worktree remove --force` entfernte
> (2026-08-17). Rekonstruiert im Worktree `issue-1493-onset`.

## Request Summary

Die Trip-Briefing-E-Mail soll die **erste Stunde, ab der die Gewitterstufe eine
Schwelle erreicht**, als **ausgeschriebenen Satz** nennen, und Klartext- wie
Kompakt-Ausblick sollen die Onset-Stunde im Gewitterfeld führen.
**Telegram und SMS bleiben unverändert.** PO-Entscheid 2026-08-17.

## PO-Präzisierung (2026-08-17) — bestimmt den Satzbau

> „Ein Briefing bezieht sich immer auf eine Etappe (ein Wochentag wäre eine
> redundante Information). Ein Alert kann sich jedoch in Ausnahmefällen auch auf
> eine andere Etappe als das letzte Briefing beziehen (abends, nach Ankunft im
> Ziel, nachdem das Abendbriefing raus ist, Nowcast für Ziel)."

Daraus folgen **zwei getrennte Regeln**, die nicht vermischt werden dürfen:

| Ort | Bezug | Zeitangabe | Wochentag / Etappenname |
|---|---|---|---|
| **Satz-Block** (neu) | die Etappe **dieses** Briefings | `ab 14:00` ausgeschrieben | **nein** — steht im Mailkopf |
| **Ausblick-Zeilen** | kommende Etappen, eine je Zeile | `@14` am Gewitterfeld | ja — ist ohnehin Zeilen-Label |

Zugleich ist damit die Grenze zu #1948 sachlich begründet: Der **Alert** braucht
einen Ortskopf (`Ziel:`, `Segment N:`), weil sein Bezug wechseln kann. Das
**Briefing** braucht ihn nicht, weil sein Bezug feststeht. Gleicher Satzbau, der
Alert trägt zusätzlich einen Adressteil — kein Verstoß gegen „Format folgt dem
Phänomen".

## Wichtigster Befund: die Rechnung existiert bereits

`render_threshold_peak_value()` (`src/output/tokens/metrics.py:29-67`) ermittelt
die erste Stunde `>= threshold` **und** die Spitzenstunde und rendert
`{first}@{first.hour}({peak}@{peak.hour})`. Die Aggregation
(`services/weather_metrics.py:1227-1266`) kennt zwar wirklich keine
Zeitpunkt-Aggregation — die Ausgabe-Schicht hat sie aber längst.

| Ausgabe | Onset-Stunde | Spitzen-Stunde | Fundstelle |
|---|---|---|---|
| E-Mail HTML, Ausblick | ✅ `mittel @14` | ✅ | `email/outlook.py` |
| **E-Mail Klartext, Ausblick** | ❌ nur `⚡mittel` | ✅ | `email/outlook.py:370-378` |
| **E-Mail Kompakt, Ausblick** | ❌ Tagesteil ohne Stunde | ✅ | `email/compact.py:101-103` |
| Telegram Trendblock | ✅ `⚡mittel@14(hoch@18)` | ✅ | `renderers/narrow.py:600-629` |
| SMS Trip-Briefing | ✅ `TH:M@14(H@18)` | ✅ | `output/tokens/builder.py:392` |
| **Ausgeschriebener Satz** | ❌ **existiert nirgends** | — | — |

Folge: Das im Ticket vorgeschlagene SMS-Token `TH14+` wird **nicht** gebaut. Die
SMS führt den Onset bereits in `TH:` + Stufenbuchstabe (`LEVELS`) + `@Stunde` —
exakt der Grammatik, die das #1948-Konzept als Zielbild setzt.

## Analysis

### Type

**Feature** (Ausgabe-Erweiterung), mit einem Bug-Anteil: die Uneinheitlichkeit
zwischen HTML (mit Stunde) und Klartext/Kompakt (ohne) ist aus Nutzersicht nicht
erklärbar.

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/output/renderers/email/outlook.py:370-378` | MODIFY | Klartext-Ausblick: `_dm[1]` (Onset-Stunde) verbauen statt verwerfen |
| `src/output/renderers/email/compact.py:101-103` | MODIFY | Kompakt-Ausblick: dito für den Tagesteil |
| `src/output/renderers/email/helpers.py` | MODIFY | Neue `build_thunder_onset_hint()` nach Vorbild `build_confidence_hint()` (349-390) |
| `src/output/renderers/email/plain.py` | MODIFY | Satz-Block einhängen (Nachbarschaft von 241-246) |
| `src/output/renderers/email/html.py` | MODIFY | Satz-Block einhängen (Nachbarschaft von 1554-1564) |
| `src/output/renderers/email/compact.py` | MODIFY | Satz-Block einhängen (Nachbarschaft von 256-261) |
| `tests/tdd/test_*` | CREATE/MODIFY | siehe „Test-Auswirkungen" |
| `tests/golden/email/*` | MODIFY | Regeneration nach inhaltlicher Prüfung |

### Harte Randbedingung aus der Abhängigkeits-Analyse

**`format_trend_tokens()` (`helpers.py:994-1015`) ist geteilt** — Trip-Mail,
Ortsvergleich **und** der SMS-/Telegram-Pfad hängen daran. Da Telegram und SMS
unverändert bleiben sollen: **Der Token-Bau wird nicht angefasst.** Geändert
werden ausschließlich die beiden Verbraucher, die die vorhandene Stunde
wegwerfen. Das ist zugleich der Schutz des Ortsvergleichs.

**Der Alarm-Pfad ist strukturell isoliert:** `email/` und `alert/` importieren
einander nicht, sie berühren sich nur über das neutrale
`output/metric_format.py`. Änderungen hier können nicht in das Gebiet der
#1948-Sitzung durchschlagen.

### Mail-Aufbau (bestimmt die Platzierung)

`render_email()` (`email/__init__.py:34-214`) verzweigt nach `email_format`:

- **`full`** → `render_html()` + `render_plain()`. Klartext-Reihenfolge
  (`plain.py`): Kopf → `compact_summary` → Vortag-Vergleich → Metrik-Pillen →
  Stabilitäts-Text → **Confidence-Hinweis (241-246)** → Wetteränderungen /
  amtliche Warnungen / Starkregen → **heutige Etappe(n) mit Stundentabelle
  (274-305)** → **mehrtägiger Ausblick (339-354)** → Footer.
- **`compact`** → nur `render_compact()`; **keine Stundentabelle** (erzwungen
  durch `briefing_mail_validator.py:534-535`), nur Pillen + Ausblick.

`render_outlook_plain()` / `render_outlook_table()` sind der **mehrtägige
Ausblick**, *nicht* die heutige Etappe.

### Existing Patterns

- **Satz-Block:** `build_confidence_hint()` gibt `None` oder einen fertigen
  String zurück; drei Renderer hängen ihn nur an (`plain.py:241`,
  `compact.py:256`, `html.py:1554`). Einmal je Mail. Gleicher Bau bei
  Stabilitäts-Text, amtlichen Warnungen, Starkregen-Hinweis.
  → Der neue Satz folgt diesem Muster. **Kein neuer Mechanismus.**
- **Geteilte Zweigwahl:** `resolve_thunder_day_branch()` wird von `outlook.py`,
  `compact.py`, `narrow.py` gemeinsam benutzt; Formatierung bleibt lokal. Diese
  Trennung stammt aus #1653/#1671 und darf nicht aufweichen.
- **Zerlegung:** `_thunder_token_parts()` (`thunder_branch.py:30-51`) liefert
  `(Wort, Stunde-als-String, vorformatierter Peak-Zusatz " (hoch @18)")`.
  Klartext/Kompakt nehmen heute Element 0 und 2 und werfen Element 1 weg.
- **Stufen-Wörter:** Klartext nutzt `_TREND_THUNDER_LABELS`
  (`helpers.py:989`, 1/2/3 → leicht/mittel/hoch), bewusst getrennt von der
  SMS-Leiter `L`/`M`/`H` (`tokens/metrics.py:14`).

### Dependencies

- **Upstream:** `thunder_level_from_signals()` (#1474, `metric_format.py:476-489`)
  → Stufe je Stunde; `format_trend_tokens()` → `thunder_day_token`. Beide
  unverändert.
- **Downstream:** Golden-Fixtures `tests/golden/email/` (5 Profile je HTML/Plain
  + `outlook-thunder-day-night.txt`), Regeneration über
  `tests/golden/email/regenerate.py`.
- **Kein Frontend-/Go-Bezug:** weder `internal/` noch `frontend/` parsen den
  Gewitter-Text oder das Token-Format.
- `src/app/day_window.py` → `window_end_utc_exclusive()` ist der **gemeinsame**
  Fenster-Helfer (#1599). Falls eine Fenstergrenze gebraucht wird: diesen nehmen,
  nicht neu rechnen.

### Existing Specs

- `docs/specs/modules/feat_1680_s5a_gewitter_herkunft_ausblick.md:118-121` —
  **AC-2: „der Klartext führt wie bisher keine Tagesuhrzeit"**, dazu **AC-13**
  für die Kompakt-Mail. **Beide werden durch #1493 abgelöst**; die Alt-Spec
  braucht einen Rückverweis.
- `docs/specs/modules/fix_1671_kompaktmail_ausblick_tagesfenster.md` — Herkunft
  der geteilten Zweigwahl.

### Risks & Considerations

1. **Freigegebene ACs werden umgekehrt** (#1680 S5a AC-2/AC-13). Ausdrücklich in
   der neuen Spec benennen, Rückverweis in der Alt-Spec. Nicht still korrigieren.
2. **Renderer-Commit-Gate #811** (`.claude/hooks/renderer_mail_gate.py:42-48`):
   alle `email/*.py` sind erfasst; `helpers.py` fällt zusätzlich unter
   `_SHARED_HELPER_PATTERNS` und verlangt **auch den Compare-Nachweis**.
   Matrix-Test + `briefing_mail_validator.py` von Anfang an einplanen.
3. **Validator-Heuristik** (`briefing_mail_validator.py`): `_check_plausibility`
   reklamiert `HH:00`-Stunden außerhalb 06–22; `_has_hourly_table_plain`
   verbietet im Kompakt-Format ≥2 Zeilen, die mit `HH:00` **beginnen**. Der neue
   Satz darf also nicht mit einer Uhrzeit am Zeilenanfang beginnen.
4. **Golden-Fixtures brechen** — erwartet; Regeneration nur nach inhaltlicher
   Prüfung, nie blind.
5. **Datenverfügbarkeit (offen, Phase 3):** Der Satz braucht die Stundenreihe der
   **Etappe dieses Briefings**, nicht die des Ausblicks. Ob `hourly_thunder` an
   der Einhängestelle bereits vorliegt oder durchgereicht werden muss, entscheidet
   über den Umfang.
6. **Abstimmung #1948 (läuft):** Notation `TH…@…` ist dieselbe, die **Auflösung**
   unterscheidet sich (Briefing stundengenau aus `first.hour`, Nowcast
   minutengenau aus `OnsetEvent.onset_time`). Position dieser Spec: Auflösung
   folgt der Datenquelle — eine Stundenvorhersage kann keine Minute behaupten.

### Open Questions

- [x] Liegt die Stundenreihe der Briefing-Etappe an der Einhängestelle vor?
      **Ja** — `segments: list[SegmentWeatherData]`, `build_confidence_hint` liest
      darin `seg.timeseries`. Kein neuer Parameter nötig.
- [ ] Antwort der #1948-Sitzung zur Auflösung (`TH@14` vs. `TH@15:40`) — betrifft
      nur die Begründung in der Spec, nicht den Briefing-Code.

## ENTSCHEIDUNG (PO, 2026-08-17) — Zuschnitt geändert

### Der Auslöser: die Aussage existiert bereits

`_pill_for_metric("thunder", …)` (`email/helpers.py:1766-1775`) rendert für die
Etappe **dieses** Briefings schon heute:

```
Gewitter ab 14:00 · stärkste 18:00 · CAPE
```

in **allen drei** E-Mail-Renderern (`plain.py:205`, `html.py:1432`,
`compact.py:176`). Der im Ticket als „die einzige wirklich neue Mechanik"
beschriebene Satz ist inhaltlich vorhanden — nur nicht als Prosa.

Zwei echte Mängel bleiben:
- Die Pille erscheint nur, wenn der Nutzer **Gewitter als Metrik gewählt** hat
  (`resolve_trip_active_metrics`, `plain.py:193-195`).
- Sie nennt **die Stufe nicht** — „mittel"/„hoch" steckt allein in der
  Ampelfarbe (`_tone`), im Klartext nur als `tone_symbol()`-Zeichen.

### PO-Entscheid (allgemeingültig, siehe `docs/project/strategic-directions.md`)

> „Wenn der User will, wählt er Plaintext E-Mail. Die normale E-Mail (HTML)
> braucht keine Dopplung."

### Daraus folgt für #1493

| # | Was | Warum |
|---|---|---|
| 1 | **Kein neuer Prosa-Block.** Die geplante `build_thunder_onset_hint()` entfällt ersatzlos. | Die Pille trägt die Aussage bereits; ein zweiter Block wäre die Dopplung, die der PO ausschließt (Muster #1313 E1). |
| 2 | **Die Pille bekommt das Stufenwort in den Text** (`helpers.py:1774`). | Im Klartext existiert die Stufe sonst gar nicht — Farbe trägt dort nichts. Deckt sich mit „Akzent-Farben nie alleiniger Lesbarkeits-Träger". |
| 3 | **Klartext- und Kompakt-Ausblick bekommen die Onset-Stunde** (`outlook.py:372`, `compact.py:103`). | Die unbestrittene Lücke; löst #1680 S5a AC-2 und AC-13 ab. |
| 4 | **Telegram und SMS bleiben unverändert.** | Beide führen den Onset bereits. |

### Revidierte Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `email/helpers.py:1774` | MODIFY | Stufenwort in den Pillen-Text |
| `email/outlook.py:372` | MODIFY | `_dm[1]` verbauen statt verwerfen |
| `email/compact.py:103` | MODIFY | dito, Tagesteil |
| `tests/tdd/test_thunder_origin_outlook.py:329-334` | MODIFY | Zusicherung „ohne Tagesuhrzeit, wie bisher" ablösen |
| `tests/golden/email/outlook-thunder-day-night.txt:5-7` | MODIFY | Regeneration nach Prüfung |
| neue TDD-Datei | CREATE | Verhaltensnachweis Onset-Stunde + Stufenwort |
| `docs/specs/modules/feat_1680_s5a_…md` | MODIFY | Ablöse-Vermerk zu AC-2/AC-13 |
| `docs/specs/modules/fix_1671_…md` | MODIFY | dort steht „AC-13 bewusst NICHT abgelöst" — jetzt doch |

**`plain.py`, `html.py`, `compact.py` fallen als Änderungsziele weg** — kein
Einhängen eines neuen Blocks. Damit entfällt auch ein Teil der
Gate-#811-Fläche; `helpers.py` bleibt erfasst (inkl. Compare-Nachweis).

### Scope nach Entscheid

Deutlich kleiner als beim Intake: **3 Produktivzeilen-Bereiche** statt sechs
Dateien, geschätzt **+40/-10 LoC** produktiv plus Tests. Weit unter dem
LoC-Limit von 250.

## Abgrenzung zu Parallelsitzungen (Stand 2026-08-17)

- **#1948** (`gregor-zwanzig-b4`): Alarm-Format-Konzept, `renderers/alert/render.py`. Nicht angefasst.
- **#1945**: Radar-Nowcast-Onset, `_render_sms_onset`. Nicht angefasst.
- **#1929**: `official_alerts.py:1896-2104` + zwei `test_official_alert_*`-Dateien. Gesperrt, nicht angefasst.
- #1493 liegt vollständig in `src/output/renderers/email/`.

---

# WIEDEREINSTIEG NACH `/clear` (Stand 2026-08-18)

**Status: Spec FREIGEGEBEN. Nächster Schritt ist `/40-tdd-red`.**

| Was | Wert |
|---|---|
| Issue | **#1493** — Gewitter S7: Onset |
| Workflow | `feat-1493-gewitter-onset`, Phase `phase4_approved`, `approved=true` |
| Worktree | `/home/hem/gregor_zwanzig/.claude/worktrees/issue-1493-onset` |
| Branch | `feat-1493-gewitter-onset` auf `c37a71f6` (= `origin/main`), **noch kein eigener Commit** |
| Spec | `docs/specs/modules/feat_1493_gewitter_onset_sichtbar.md` — validiert VALID, 8 ACs, PO-Freigabe „go" am 2026-08-18 |
| Workflow-Werkzeug | `python3 /home/hem/.claude/plugins/cache/henemm-private/agent-os-openspec/3.11.4/core/hooks/workflow.py` |
| ENV-Variable | `OPENSPEC_ACTIVE_WORKFLOW` (**nicht** `GZ_ACTIVE_WORKFLOW` — CLAUDE.md ist an der Stelle veraltet) |

## Die drei Änderungen (PO-entschieden, nicht neu verhandeln)

1. `src/output/renderers/email/helpers.py:1774` — Stufenwort in den Pillen-Text.
   Heute: `Gewitter ab 14:00 · stärkste 18:00 · CAPE`. Die Stufe hängt allein an
   der Ampelfarbe `_tone` und fehlt im Klartext völlig. Wörter aus
   `THUNDER_LABEL_DE` / `_TREND_THUNDER_LABELS` — **keine neue Wortliste** (#1480).
2. `src/output/renderers/email/outlook.py:372` — `f"⚡{_dm[0]}{_dm[2]}"` →
   `f"⚡{_dm[0]}@{_dm[1]}{_dm[2]}"`.
3. `src/output/renderers/email/compact.py:103` — dieselbe Ergänzung im Tagesteil.

**KEIN neuer Prosa-Block.** **Telegram und SMS unverändert.**

## Fallen, die schon Zeit gekostet haben

- **`format_trend_tokens()` (`helpers.py:994-1015`) NICHT anfassen** — geteilt mit
  Ortsvergleich UND SMS/Telegram. Eine Änderung dort verändert SMS/Telegram mit
  und bricht AC-5.
- **Renderer-Commit-Gate #811** erfasst alle `email/*.py`; `helpers.py` verlangt
  zusätzlich den **Compare-Nachweis**. Validator-Lauf einplanen, nicht überrascht
  werden.
- **Bestandstest anpassen:** `tests/tdd/test_thunder_origin_outlook.py:329-334`
  assertiert „ohne Tagesuhrzeit, wie bisher" — wird durch die Ablösung falsch.
- **Golden-Fixture:** `tests/golden/email/outlook-thunder-day-night.txt:5-7`,
  Regeneration über `tests/golden/email/regenerate.py` — nur nach inhaltlicher
  Prüfung, nie blind.
- **Ablöse-Vermerke schreiben:** `feat_1680_s5a_gewitter_herkunft_ausblick.md`
  (AC-2, AC-13) und `fix_1671_kompaktmail_ausblick_tagesfenster.md` (dort steht
  „AC-13 bewusst NICHT abgeloest" — gilt nicht mehr).
- **Validator-Falle:** Tagesfenster ist 04–19, `briefing_mail_validator.py` prüft
  aber 06–22 → eine Onset-Stunde 04:00/05:00 kann Fehlalarm auslösen.
- **Worktree kann fremd gelöscht werden** (ist am 2026-08-17 passiert): Artefakte
  sofort ins Session-Scratchpad kopieren.

## Abgrenzung zu Parallelsitzungen

#1948 (Alarm-Format, `renderers/alert/`), #1945 (Radar-Nowcast, `_render_sms_onset`),
#1929 (`official_alerts.py:1896-2104`) — **alle drei nicht anfassen.** #1493 liegt
vollständig in `src/output/renderers/email/`.

## Allgemeingültige PO-Regel aus diesem Ticket

`docs/project/strategic-directions.md` (neu angelegt): „Die normale E-Mail (HTML)
braucht keine Dopplung" + „was in HTML durch Farbe getragen wird, muss im Klartext
als Wort dastehen".
