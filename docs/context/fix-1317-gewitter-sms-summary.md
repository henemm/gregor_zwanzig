# Context: fix-1317-gewitter-sms-summary

## Request Summary
Ein Gewitter am Ziel (in der Vorhersage-Detailtabelle klar sichtbar: 14:00 Uhr, ⚡⚡, Regen 16.7 mm,
Regenwahrscheinlichkeit 95 %) taucht **weder in der SMS** (`… G- TH:- TH+:-`) **noch in der
E-Mail-Kurzzusammenfassung** (grüne Pille „kein Gewitter", „Regen-W. max 10%") auf. Zusätzlich existiert
laut Nutzer eine amtliche Warnung, die ebenfalls nicht in SMS/Kurzzusammenfassung reflektiert wird.
**Kritischer, sicherheitsrelevanter Bug** (#1317, priority:critical).

## Beobachtung aus den Screenshots (Bug-Reproduktion aus Nutzersicht)
- **Detailtabelle „Nacht am Ziel (1504m)":** um **14:00** Thdr=⚡⚡, Rain=16.7 mm, Rain%=95; um 16:00 Rain%=85.
- **Kurzzusammenfassung / Metriken-Überblick:** grüne Pille „kein Gewitter", „Regen-W. max 10% (11:00)".
  Die Chip-Zeitstempel (gef. min 08:00, Wind max 11:00, 0°-Linie Max 10:00) deuten auf ein
  Aggregationsfenster **~08:00–11:00** (Etappe + Zielankunft) — das 14:00-Gewitter liegt **außerhalb**.
- **SMS `E9: N12 D17 R- PR- W- G- TH:- TH+:-`:** G-/TH:-/TH+:- = kein Gewitter heute/morgen.

## Arbeitshypothese (in Phase 2 zu verifizieren)
Das Gewitterfenster von SMS und Kurzzusammenfassung deckt die Nachmittags-/Nachtstunden am Ziel nicht ab.
Seit #1275 (ADR-0025) wird Gewitter bewusst aus **derselben gefensterten Stundenreihe** abgeleitet wie
die übrigen Metriken (Widerspruchsfreiheit „Gewitter aus EINER Quelle"). Nebenwirkung: ein Gewitter, das
erst nach dem Wander-/Ankunftsfenster am Ziel auftritt, fällt aus der Quelle heraus und wird strukturell
nie gemeldet — obwohl der „Nacht am Ziel"-Detailblock es zeigt.

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/sms_trip.py` (~L98–240) | Baut SMS-Gewitter-Token `TH:`/`TH+:` aus `thunder_samples`; Kommentar L125 verweist auf #1275/ADR-0025 „gefensterte Quelle" |
| `src/output/renderers/compact_summary.py` (L362–386) | `_format_thunder` iteriert über übergebenes `hourly`; keine Thunder-Stunde → „kein Gewitter" |
| `src/output/adapters/trip_result.py` | `time_window`-Zuordnung der Waypoints; Quelle der gefensterten Stundenreihen |
| `src/risk/*` | Risiko-/Gewitter-Aggregation (Peak-/Schwellenlogik), Zielzeitfenster |
| `src/output/renderers/email/html.py` / `compact.py` | „Wetter am Ziel" / „Nacht am Ziel"-Detailtabellen (zeigen das Gewitter korrekt) — Referenz für erwartetes Verhalten |
| `src/output/renderers/alert/official_alerts.py` | Amtliche Warnungen — zweiter Strang: warum nicht in SMS/Kurzzusammenfassung? |

## Existing Patterns / relevante Entscheidungen
- **#1275 / ADR-0025 „Gewitter aus EINER Quelle":** SMS/Telegram/E-Mail dürfen sich nicht widersprechen;
  Gewitter kommt aus einer gemeinsamen gefensterten Reihe. Ein Fix darf diese Widerspruchsfreiheit **nicht**
  zerstören (sonst Regress zu #1275).
- **#1313:** „Gewitter-Vorschau entfällt bei aktivem Ausblick, Nacht am Ziel auch morgens" — jüngste
  Änderung am selben Zeitfenster-/Nacht-am-Ziel-Verhalten.
- **#1316:** „Abgelaufene amtliche Warnungen zeitlich filtern — Fenster-Filter vor Dedup" — Fenster-Logik
  bei amtlichen Warnungen, relevant für den zweiten Strang.

## Dependencies
- **Upstream:** Normalizer/Risk-Engine liefert die gefensterten `hourly`/`thunder`-Reihen und die
  Zielzeitfenster (Etappe / Wetter am Ziel / Nacht am Ziel).
- **Downstream:** SMS-Kanal, E-Mail-Kurzzusammenfassung, Telegram — alle konsumieren die gemeinsame
  Gewitter-Ableitung.

## Existing Specs
- ADR-0025 (Gewitter-Quelle) — im Repo zu lokalisieren (Phase 2).
- `docs/specs/modules/` — Trip-Briefing / SMS-Token-Spec (Phase 2).

## Risks & Considerations
- **Regressionsgefahr #1275:** Fix muss Gewitter weiterhin widerspruchsfrei über alle Kanäle halten.
- **Zwei Stränge:** (1) Vorhersage-Gewitter außerhalb Wanderfenster, (2) amtliche Gewitterwarnung —
  evtl. unterschiedliche Ursachen; in Phase 2 trennen.
- **Fenster-Definition ist die Kernfrage:** Was ist das fachlich korrekte Gewitter-Warnfenster für einen
  Weitwanderer? Vermutlich „bis inkl. Nacht am Ziel", nicht nur die Wanderzeit — braucht PO-Entscheidung
  in der Spec (AC-Freigabe).
- **Kanal-Parität:** SMS, Kurzzusammenfassung UND Detailtabelle müssen nach dem Fix konsistent sein.

## Analysis (Phase 2 — bestätigt durch 2 parallele Root-Cause-Agenten)

### Type
Bug (strukturelle Lücke), mit Produktentscheidung. **Scope-Cut nach PO-Antwort: nur Strang 1.**

### Root Cause Strang 1 — Vorhersage-Gewitter am Ziel (DIESER Workflow)
SMS, E-Mail-Kurzzusammenfassung (`compact_summary`) und die Metriken-Pillen im E-Mail-Kopf
(`build_metrics_summary_pills`) leiten Gewitter **alle aus derselben Quelle** ab: der pro Etappe auf die
**Wanderzeit** gefensterten `segments`-Stundenreihe (`start_h..end_h`, endet an der Ankunftsstunde) —
so von ADR-0025 als „die eine Quelle" festgelegt. Der separate Datensatz `night_weather`
(Ankunft → 06:00 morgens), aus dem die Detailtabelle „Nacht am Ziel" korrekt gespeist wird, fließt in
**keinen** dieser Kanäle ein. Ein Gewitter um 14:00 (nach Ankunft) ist daher für SMS/Kurzzusammenfassung/
Pillen strukturell unsichtbar. **Kein Regress durch #1275/#1313** — strukturelle Lücke seit ADR-0025;
#1313 hat sie durch häufiger sichtbaren Nachtblock vergrößert.

Belege:
- `sms_trip.py:106-112` (Fenster `start_h<=h<=end_h`), `:224-233` (`format_sms(segments,…)` ohne `night_weather`)
- `compact_summary.py:140-165` (`_collect_hourly_data` filtert auf Segment-Fenster), `:362-386` (`_format_thunder`)
- `email/helpers.py:1417-1465` (`build_metrics_summary_pills`, gleiche Segment-Fensterung → „kein Gewitter"-Pille)
- `trip_report.py:126` (compact aus nur `segments`), `:107-114` (`night_weather` nur in Detailtabelle)
- `trip_report_scheduler.py:829-831` (`night_weather` separater Fetch)
- `narrow.py` (Telegram-Fußzeile) — laut ADR-0025 dieselbe Segment-Fensterung → muss mit erweitert werden
- ADR: `docs/adr/0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md`

### Root Cause Strang 2 — amtliche Warnung (→ FOLGE-ISSUE, nicht dieser Workflow)
SMS + Kurzzusammenfassung konsumieren amtliche Warnungen **grundsätzlich nie** (nie gebaut, keine Regression).
Amtliche Warnungen haben einen eigenen Block: HTML-WarnBlock ganz oben (`email/html.py:1430-1471`),
`== Warnungen ==` in Compact/Plain-Text. SMS hat keinen Warn-Block. **PO bestätigt:** Warn-Kasten war im
großen Briefing sichtbar → Abruf ok, reines „fehlt in Kurzformen"-Feature. **PO-Entscheid: eigener Folgeauftrag.**

### Fix-Leitplanken (ADR-0025 wahren)
1. `dp.thunder_level` bleibt einzige Rohquelle — kein Kanal fällt auf ein Aggregat zurück.
2. Fenster-Erweiterung um „Nacht am Ziel" muss **für alle Kanäle gleichzeitig** gelten (SMS, Kurzzusammenfassung,
   Pillen, Telegram-Fußzeile), sonst neue #1275-Divergenz.
3. Nur **zukunftsrelevante** Nacht am Ziel (nach Report-Zeitpunkt) — vergangene Nacht löst kein Token aus.
4. Beweis über echte Einstiegsfunktion (`format_sms()`, `render_email()`), nicht Glue überspringen (ADR-0025 E5).
5. Detailtabelle „Nacht am Ziel" ist Referenz für erwartetes Verhalten — darf nicht regressieren.

### Scope Assessment
- Betroffen: `sms_trip.py`, `compact_summary.py`, `email/helpers.py`, `narrow.py` (+ ggf. `trip_report.py` Glue).
- **LoC-Warnung:** 4 Kanäle → 250-LoC-Grenze könnte reißen (Override erst mit PO-Permission).
- Risk Level: **HIGH** (sicherheitskritischer Pfad, Kanal-Konsistenz-Invariante).

### Infrastruktur-Hinweis (WICHTIG für Implement-Phase)
Dieses Worktree liegt **27 Commits hinter `origin/main`** (HEAD `7bd7428d`, main `360ea01f`). Zieldateien laut
Agent 2 in diesen Commits unverändert, aber **vor der Implementierung muss das Worktree auf `origin/main`
aktualisiert werden** (Memory: „Worktree kann weit hinter main liegen").

### Open Questions (für Spec/TDD geklärt)
- [x] Fensterdefinition = Wanderzeit + Nacht am Ziel (bis 06:00), nur zukünftig → in Spec.
- [x] Amtliche Warnung = eigener Folgeauftrag (PO).
- [ ] SMS-Zeichenbudget: reicht bestehendes `TH:`-Token, oder braucht Nacht-Gewitter eigene Kennzeichnung? → in Spec entscheiden.
- [ ] Morgen- vs. Evening-Report: „nur zukünftige Nacht" sauber abgrenzen (Implementierungsdetail).
