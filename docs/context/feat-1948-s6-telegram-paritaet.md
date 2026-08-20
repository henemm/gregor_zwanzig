# Context: #1948 S6 — Telegram-Parität (Alarm-Darstellung)

**Workflow:** `feat-1948-s6-telegram-paritaet` · Branch `feat-1948-s6-telegram-paritaet`
· Worktree `.claude/worktrees/intake-1948-s5` · Basis `origin/main` @ `b31acb40` (S5-Merge)
· Track **Full Process** (Intake-Summe 4)

## Request Summary

Der Änderungs-Alarm gibt in den ausführlichen Kanälen die **interne Rohzahl** der
Gewitterstufe aus (`2 ↑ 3`) und rechnet darauf eine **prozentuale Änderung**
(`+50 %`). Beides widerspricht dem Rest des Produkts: das Briefing nennt die
Gewitterstufe überall als deutsches Wort, und eine Prozentquote auf einer
Ordinalskala ist bedeutungslos. Zusätzlich fehlt dem Telegram-Alarm die
Stand-/Vergleichszeile, die die E-Mail führt.

## 🔴 Alles Folgende ist GEMESSEN, nicht aus dem Quelltext abgeleitet

Drei Messläufe am HEAD `b31acb40`, Renderer direkt aufgerufen (kein Versand).

### Ist-Zustand Änderungs-Alarm, Gewitter Stufe 2 → 3

```
Betreff:   [TESTTRIP] km 0–4 · ↑ Gewitter: 2→3
E-Mail:    Gewitter +50% seit dem Briefing
           ↑ +50 % · Änderung über deiner Alarm-Schwelle (1)
           Gewitter · : 2 ↑ 3 +50 %
           Änderung 1: über Alarm-Schwelle 1 ✗
           Wo & wann: km 0–4 · 15:00
           Stand: heute 09:30 · verglichen mit dem letzten Briefing
Telegram:  TESTTRIP · km 0–4 · ↑ Gewitter
           Gewitter · Schwelle 1 · 2 ↑ 3 · Änderung über
SMS:       km 0-4: TH:M->H@15
```

Mehr-Event-Fall (Gewitter 2→3 + Sicht 1400→280):
```
Telegram:  KHW 403 · 🏁 Ziel · 2 über Schwelle
           Gewitter 🏁 Ziel · 16:00 2→3 · Sicht 🏁 Ziel · 14:00 1.400→280 m
E-Mail:    Gewitter · 🏁 Ziel · 16:00 · Änderung 1 · Schwelle 1: 2 ↑ 3 über
```

### Ist-Vokabular der Gewitterstufe im übrigen Produkt

**SSoT:** `src/output/metric_format.py:283-288`
```python
THUNDER_LABEL_DE = {NONE: "kein", LOW: "leicht", MED: "mittel", HIGH: "hoch"}
```

| Ort | Datei:Zeile | Darstellung |
|---|---|---|
| SMS (Briefing + Alarm) | `src/output/tokens/metrics.py:14` | `-` / `L` / `M` / `H` |
| E-Mail Stundentabelle HTML | `email/helpers.py:773-776` | farbiger Ampelpunkt, **kein Text** |
| E-Mail Stundentabelle Text | `email/helpers.py:762-772` | `kein`/`leicht`/`mittel`/`hoch` |
| E-Mail Kurzzusammenfassung | `email/helpers.py:1784-1788` | `Gewitter mittel ab 16:00 · stärkste 18:00` |
| E-Mail Ausblick „Gew" | `email/outlook.py:176-247` | `{Wort} @{H}` |
| E-Mail Gewitter-Vorschau | `trip_report_scheduler.py:2607-2615` | `Starkes Gewitter erwartet ab 16:00` |
| E-Mail Kompakt | `email/compact.py:97-116` | `⚡{Wort}@{H}` |
| Telegram Briefing | `narrow.py:279-282`, `:538-543` | `⚡ {Wort}` |
| Frontend Schwellen-UI | `compare_metric_catalog.py:66-68` | `Leicht`/`Mittel`/`Hoch` |
| **Änderungs-Alarm** | `alert/render.py` | **Rohzahl 0–3** ← einziger Ausreißer |

`thunder` ist die **einzige** Metrik mit `is_level=True` (`metric_catalog.py:446`).

### Erreichbare Menge „berechnete Prozent-Änderung" (PO: entfällt grundsätzlich)

**Genau eine Rechenstelle, genau zwei f-Strings, ein einziger Konsument.**

- Rechnung: `alert/model.py:137-141` `delta_pct()` — `value_from == 0` → `None`
- H1: `alert/render.py:515-517` `f" {d:+d}%"` (ohne Leerzeichen!)
- Δ-Text: `alert/render.py:531-532` `f"{d:+d} %"` → Badge `:536-538`, Datenzeile `:558-563`
- Import-Kante: `alert/render.py:23`
- Einziger Konsument: `render_email()` `alert/render.py:646` → HTML `:766-776`, Plain `:742-746`

**Nur im Ein-Event-Zweig** (`render.py:658` `single = len(evs) == 1`).

**Entwarnungen (belegt, kein Prozent):** E-Mail-Betreff (`render_subject` `:466-509`
ruft `delta_pct` nie) · Telegram (`:781-827`) · SMS (`:829-983`) · Radar-Alarm
(`_render_email_onset`, `:647-651`) · amtlicher Alarm (`official_alerts.py`) ·
Trip-Briefing (`day_comparison.py:76` = absolute Differenz; `narrow.py:373` nie `%`) ·
Ortsvergleich (`comparison.py:72,84,112-114` = Einheit).

**Grenzfall, Tech-Lead-Entscheid:** `email/helpers.py:1086-1100` `format_change_line()`
erzeugt bei %-Einheiten Texte wie `+34 %` — das ist eine **vorzeichenbehaftete Differenz
in Prozentpunkten**, dieselbe Sorte Zahl wie `+3 °C`, keine Quote. **Bleibt unverändert.**

### Vergleichszeitpunkt (`reference_at`)

Steht **ausschließlich** in der E-Mail: `alert/render.py:670-674` (Ein-Event),
`:725-729` (Multi), `:1059` (Legacy-Shim #816). Telegram hat das Feld **nie** gelesen,
SMS seit S3 nicht mehr. Erzeugung `utils/timezone.py:146-162` `format_reference_at()`
(`"18:03"` / `"gestern 18:03 Uhr"` / `"vor N Tagen …"`), Durchreichung
`trip_alert.py:361-376`, `compare_alert.py:286-308`, DTO `alert/model.py:122-126`.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/alert/render.py` | **Kern.** `_h1`:511 · `_delta_text`:529 · `_verdict_single`:535 · `_datablock_single`:557 · `_email_line`:521 · `render_email`:646 · `render_telegram`:781 · `_num`:59 · `_val`:~40 · `_is_level_metric`:110 |
| `src/output/renderers/alert/model.py` | `delta_pct`:137 · `reference_at`:122 |
| `src/output/metric_format.py` | `THUNDER_LABEL_DE`:283 — Wort-SSoT, wird importiert statt kopiert |
| `src/output/tokens/metrics.py` | `LEVELS`:14 — SMS-Buchstaben, **tabu** |
| `src/app/metric_catalog.py` | `thunder`:428, `is_level=True`:446 |
| `src/services/notification_service.py` | `:1355-1361` zentraler Renderpunkt; Telegram-Weiche `:1444-1520` |
| `src/services/validator_render_service.py` | `:149-152` Alarm-Vorschau in der Oberfläche — dieselbe `AlertMessage` |

## Existing Patterns

- **Stufenleiter statt Messzahl** ist bereits gebaut: `_is_level_metric()` (`render.py:110`,
  liest `MetricDefinition.is_level`) + `LEVELS`-Map — heute **nur** im SMS-Zweig
  verdrahtet (`render.py:854-858`, Issue #1948 S3). Dasselbe Muster, andere Tabelle.
- **Kanalabhängige Darstellung derselben Größe** ist etabliert und gewollt:
  `Seg` (SMS) vs. `Segment` (Telegram/E-Mail) — S5 AC-13; führende Null nur in der SMS — S4 AC-11.
- **Konditionales Weglassen** ist im Prozent-Pfad schon vorhanden: `tail`/`d_suffix` sind
  bei `value_from == 0` bereits leer (`render.py:537-538`, `:558-559`) — der
  „ohne Prozent"-Zustand ist also heute schon erreichbar und messbar.

## Dependencies

- **Upstream:** `metric_format.THUNDER_LABEL_DE` · `metric_catalog.get_metric().is_level`/`.unit`
  · `alert/model.AlertEvent` · `utils/timezone.format_reference_at`
- **Downstream:** `notification_service` (4 Versandwege: Trip-Δ, Compare-Δ einzeln,
  Compare-Δ gebündelt, jeweils E-Mail + Telegram) · `validator_render_service` (Vorschau-API)

## Existing Specs

- `docs/specs/modules/fix_1948_s3_sms_sofortfix.md` — S3; `:207-210` merkt die S6-Frage vor
- `docs/specs/modules/fix_1948_s5_amtliche_sms_zielbild.md` — S5; AC-13 = TABU-Wächter
  für den ausführlichen Telegram-/E-Mail-Text des **amtlichen** Zweigs
- `docs/analysis/alarm-format-konzept-2026-08.md` §8 — Scheiben-Tabelle, S6-Zuschnitt
- `docs/reference/sms_format.md` §3.4c — `!`-Block, Stufenbuchstaben

## Risks & Considerations

1. **🔴 H1 verliert ohne Ersatz ihre Aussage.** Gemessen bei `value_from == 0`:
   `Gewitter seit dem Briefing` — grammatisch defekt, kein Informationsträger mehr.
   Prozent ist dort der **einzige** Träger (Von-/Bis-Werte stehen nicht in der H1).
   Badge und Datenzeile vertragen den Wegfall dagegen ersatzlos (gemessen).
2. **Byte-genaue Wächter werden rot** — bewusst nachzuziehen, nicht zu umgehen:
   `tests/tdd/test_957_alert_mail_literal_structure.py:44-59` (fordert `%` im Verdikt,
   importiert `delta_pct` in `:51`) · `tests/tdd/test_issue_1169_compare_alert_consumer.py:709,755-768`
   (byte-genaue Plain-Gleichheit mit drei Prozent-Vorkommen).
3. **🔴 Gegenprobe-Wächter muss GRÜN bleiben:** `tests/tdd/test_channel_metric_matrix.py:2202-2220`
   fordert, dass `%` als **Einheit** erhalten bleibt. Ein pauschaler „%-Entfall" macht ihn rot —
   er ist die Trennlinie zwischen (A) Einheit und (B) berechneter Änderung.
4. **A/B stehen in einer Zeile nebeneinander.** Gemessen für `rain_probability` 60→90:
   `Regen% · %: 60 % ↑ 90 % +50 %` — `60 %`/`90 %` Einheit, `+50 %` Quote, und in der
   Folgezeile `Änderung 30 %` = Prozentpunkte. Nur das mittlere fällt weg.
5. **Ortsvergleich zieht automatisch mit.** `render_email`/`render_telegram` bedienen Trip
   **und** Ortsvergleich (`notification_service.py:628`/`:673`/`:695`). Das ist gewollte
   Code-Teilung (CLAUDE.md), kein Ortsvergleich-Vorhaben — aber im Adversary zu prüfen.
6. **Alarm-Vorschau in der Oberfläche ändert sich mit** (`validator_render_service.py:149-152`).
7. **Nachbarsitzung #2009** (`gregor-zwanzig-26`, Branch `fix-2009-nowcast-vorlauf`) arbeitet
   in derselben Datei an `render.py:371`, `:418`, `:435-463` (Onset-Tagesbezug, SMS + Telegram).
   Abgestimmt: S6 fasst diese Zeilen **nicht** an und vereinheitlicht **keine** Zeitformatierung
   (`local_fmt`, `%H:%M`). Wer zuerst auf `main` ist, der andere rebased.
8. **Nebenbefund (nicht Teil des Zuschnitts, → #1199):** `Gewitter · :` — Trenner ins Leere,
   weil die Stufen-Metrik keine Einheit hat (`render.py:557`, `:740`).

## PO-Entscheide 2026-08-20 (Grundlage der Spec)

| # | Frage | Entscheid |
|---|---|---|
| 1 | Gewitterstufe im Alarm | **Wort** aus `THUNDER_LABEL_DE` — `mittel ↑ hoch` statt `2 ↑ 3`; **Schwelle zieht mit** (`Schwelle leicht` statt `Schwelle 1`) |
| 2 | Prozent-Änderung | **entfällt grundsätzlich** — Begründung wörtlich: „Das versteht niemand und stiftet keinen Nutzen" |
| 3 | Stand-/Vergleichszeile in Telegram | **Variante (b)** — volle Zeile wie in der E-Mail: `Stand: heute 10:00 · verglichen mit 18:03` |

Ersatz für die H1 (in Frage 2 mit vorgelegt): `Gewitter mittel → hoch seit dem Briefing`,
`Niedersch 2,0 mm → 18,0 mm seit dem Briefing`.
