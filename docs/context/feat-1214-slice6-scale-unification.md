# Context: #1214 Scheibe 6 — Wolken-Skala + Thunder-Ordinal (letzte Scheibe)

## Request Summary

Vereinheitlichung der Wolken-Emoji-Skala und des Thunder-Ordinals über alle Kanäle
(Issue #1214 Punkt 6, PO-Entscheidung zur Skala erforderlich). Beifang: Katalog-
`sunshine.decimals=1` + Migration der Scheibe-5-F001-Ausnahme.

## Ist-Stand (frisch erhoben + einzeln verifiziert, 3 parallele Analysen)

### Wolken-Emoji-Skalen — 3 lebende Varianten + 1 tote Kopie

| # | Stelle | Schwellen | Endnutzer-Artefakt | Testabdeckung |
|---|---|---|---|---|
| A | `email/helpers.py:558-571` (fmt_val cloud*-Zweig, friendly) | ≤10 ☀️ / ≤30 🌤️ / ≤70 ⛅ / ≤90 🌥️ / ☁️ | Wolken-Spalten der Mail-Stundentabellen (Trip-Briefing + Orts-Vergleich) | HART: `test_weather_metrics_ux.py::TestCloudEmojiFormatting` inkl. Boundary-Tests (10/11/70/91) |
| B | `compact_summary.py:150-162` (_format_clouds, friendly) | <20 ☀️ / <40 🌤️ / <60 ⛅ / <80 🌥️ / ☁️ | 1-2-zeilige Stagen-Kurzbeschreibung in der Mail (Kompakt-Zusammenfassung) | integration/test_compact_summary.py (Skala nicht boundary-genau verankert) |
| C | `weather_metrics.py:111-123` (_cloud_pct_emoji, Konstanten `_CLOUD_*` 20/40/70/…) | <20 / <40 / <70 / <… | Fallback der Sonnen-Emoji-Spalte (`get_weather_emoji`), wenn weder DNI noch WMO-Code vorliegen; plus `_night_emoji` (<40/<80, eigenes Nacht-Konzept) | über sunshine-Tests indirekt |
| tot | `narrow.py:158-170` (_cloud_emoji) | = A | **kein Aufrufer** (verifiziert) — Kopie von A, toter Code | — |

### Thunder-Ordinal — 6 lebende Kopien, KEINE echte Divergenz (Issue-Annahme überholt)

Alle lebenden Kopien nutzen identisch `{NONE:0, MED:1, HIGH:2}` ausschließlich als
Sortier-Schlüssel für `max(...)`; **nirgends wird der Zahlwert ausgegeben oder
persistiert** (Ergebnis ist immer das Enum):
`trip_report.py:359`, `narrow.py:174`, `helpers.py:164`, `weather_metrics.py:617`,
`weather_metrics.py:1036`, `day_comparison.py:19+345f` (als `_THUNDER_ORDINAL`, GENUTZT
— Analyse-C-Angabe „ungenutzt" war falsch, verifiziert).
`helpers.py:1091`: lokale `severity`-Definition ohne erkennbare Nutzung im
Funktionskörper — Verdacht toter Local, beim Implementieren verifizieren (ruff F841).

**`sms_trip.py:217` ist KEIN Abweichler desselben Konzepts:** `{NONE:0, MED:2, HIGH:3}`
ist die dokumentierte SMS-Builder-Level-KODIERUNG (Kommentar Bug #874: „Builder-System:
1=L, 2=M, 3=H") — der Zahlwert wird als Level in `HourlyValue` eingespeist und landet im
SMS-Token `TH+:M`/`TH+:H` (getestet: `test_bug_874_th_plus_sms.py`). Anderes Vokabular,
bleibt bestehen; die Issue-Annahme „undokumentiert abweichend" ist seit #874 überholt.

**WICHTIG (verifiziert):** `ThunderLevel` ist ein `str`-Enum OHNE Ordnung (models.py:33)
— nacktes `max(values)` wäre alphabetisch und damit FALSCH („NONE" > „MED" > „HIGH").
Die Analyse-C-Empfehlung „einfach max() ohne key" ist ein Fehlschluss. Konsolidierung
= EINE kanonische Ordnungsquelle (z.B. `metric_format.thunder_ordinal(level)` bzw.
`max_thunder(iterable)`), alle 6 Stellen darauf umstellen — reine Deduplizierung ohne
Verhaltensänderung, KEINE PO-Entscheidung nötig.

### Beifang: Katalog `sunshine.decimals`

`format_value("sunshine", …)` hat heute KEINEN Aufrufer; `calculate_sunny_hours()`
liefert verifiziert immer `round(x, 1)` (float, 1 Dezimale). Mit `decimals=1` im
Katalog wird die Scheibe-5-F001-Ausnahme auflösbar: `comparison.py:96ff` Sonne-Zeile
kann auf `format_value("sunshine", v, style="bare") + "h"` — Output beweisbar identisch
(`str(4.7)=="4.7"==f"{4.7:.1f}"`, `str(7.0)=="7.0"==f"{7.0:.1f}"`). Trip-Briefing
(`helpers.py:579` eigenes `.1f`) und compare_html (lokales decimals=1) bleiben unberührt.

## PO-Entscheidung (Kern dieser Scheibe)

Nur die **Wolken-Skala** braucht eine Produktentscheidung (Thunder hat sich als
divergenzfrei erwiesen). Optionen:

- **Option A (Empfehlung):** Mail-Skala (≤10/30/70/90) wird produktweite Wahrheit
  (Katalog-Quelle + kanonische Funktion). Sichtbare Änderung NUR in der Kompakt-
  Zusammenfassung (z.B. 15% Bewölkung: heute ☀️ → künftig 🌤️; 35%: 🌤️ → ⛅) und im
  seltenen Sonnen-Emoji-Fallback. Am wenigsten Änderung, bestehende Boundary-Tests
  bleiben die Wahrheit.
- **Option B:** Kompakt-Skala (20er-Stufen) wird Wahrheit — ändert die Mail-Tabellen
  (Haupt-Artefakt!) sichtbar + Boundary-Tests müssen neu.
- **Option C:** Keine Vereinheitlichung — nur tote Kopie löschen + Thunder-Konsolidierung
  + Kommentare (Minimal-Scheibe; die Skalen-Divergenz bleibt dokumentiert bestehen).

## PO-Entscheidung (2026-07-12, via AskUserQuestion)

- **Wolken-Skala: Option A** — Mail-Skala (≤10 ☀️ / ≤30 🌤️ / ≤70 ⛅ / ≤90 🌥️ / ☁️)
  wird produktweite Wahrheit. Sichtbare Änderung nur in der Kompakt-Zusammenfassung
  (15% → 🌤️ statt ☀️, 35% → ⛅ statt 🌤️ …) und im Sonnen-Emoji-Fallback.
- **Beifang JA:** Katalog `sunshine.decimals=1` + Migration der Sonne-Zeile
  (`comparison.py`) auf `format_value(..., style="bare")`.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/metric_format.py` | Ziel für kanonische `cloud_emoji(pct)` + `thunder_ordinal/max_thunder` |
| `src/app/metric_catalog.py` | ggf. Skalen-Schwellen als Katalog-Daten + `sunshine.decimals=1` |
| `email/helpers.py`, `compact_summary.py`, `weather_metrics.py` | Skalen-Konsumenten (je nach Option) |
| `narrow.py` | tote `_cloud_emoji` löschen; Thunder-Stelle :174 |
| `trip_report.py`, `day_comparison.py` | Thunder-Stellen |
| `comparison.py` | Beifang Sonne-Zeile (nach decimals=1) |
| `tests/unit/test_weather_metrics_ux.py` | Boundary-Tests = Skalen-Anker |
| `tests/tdd/test_bug_874_th_plus_sms.py` | SMS-Kodierungs-Anker (darf nicht brechen) |

## Risks & Considerations

- Renderer-Mail-Gate: helpers.py/compact_summary.py/sms_trip.py/trip_report.py sind
  Gate-Dateien → Matrix + briefing_mail_validator vor Commit.
- Kompakt-Zusammenfassungs-Änderung (Option A) ist nutzersichtbar in der compact-Mail
  → Vorher/Nachher-Beispiel in die Spec, compact-Format wird vom Validator geprüft.
- `_night_emoji` (<40/<80) ist ein eigenes Nacht-Konzept — NICHT Teil der Tages-Skala,
  nicht vereinheitlichen.
- DNI-basierte `_dni_emoji` (Sonnenstrahlung) ist ebenfalls eigenes Konzept — bleibt.
- ThunderLevel NICHT zu IntEnum umbauen (str-Werte sind persistiert — Schema-Risiko);
  Ordnung ausschließlich über kanonische Funktion.
