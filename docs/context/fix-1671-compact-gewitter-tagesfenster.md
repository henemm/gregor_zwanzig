# Context: fix-1671-compact-gewitter-tagesfenster

Issue: [#1671](https://github.com/henemm/gregor_zwanzig/issues/1671) · Labels: `bug`, `priority:high`, `session:khw`
Gemessen am Stand `e2b5269b` (== `origin/main`) am 2026-08-14, nicht aus dem Ticket übernommen.

## Request Summary

Der Ausblick-Block „Naechste Etappen" der **Kurzformat-Mail** (`X-GZ-Format: compact`)
baut sein Gewitter-Tageswort weiterhin aus `tok['thunder_plain']` — dem auf die
Gehzeit geklemmten 24h-Aggregat. HTML-Tabelle, Klartext-Mail und Telegram wurden
mit #1653 auf `thunder_day_token`/`thunder_night_token` (Tagesfenster bzw.
Nachtfenster derselben Stundenreihe) umgestellt; die Kurzformat-Mail blieb als
vierter Ausgabeort zurück. Folge: falsch-negatives *oder* falsch-positives
Tagesgewitter, und dort fehlt jede Nachtangabe.

## Die Klasse ist ausgezählt (nicht von einem Fall verallgemeinert)

Vier Aufrufer von `format_trend_tokens()` bauen Ausblick-Zeilen:

| # | Ausgabeort | Code | Quelle heute | Stand |
|---|---|---|---|---|
| 1 | HTML-Ausblick-Tabelle | `email/outlook.py:208` (`render_outlook_table`) | `thunder_day_token` + `thunder_night_token` | ✅ #1653 |
| 2 | Klartext-Mail-Ausblick | `email/outlook.py:358` (`render_outlook_plain`) | day/night; `thunder_plain` nur noch als Rückfall **ohne** Stundenreihe | ✅ #1653 |
| 3 | Telegram-Trendblock | `narrow.py:575` (`_outlook_lines`) | dito | ✅ #1653 |
| 4 | **Kurzformat-Mail** | `email/compact.py:230-236` | **roh `tok['thunder_plain']`** | ❌ **dieses Issue** |

Kein fünfter Ort:
- **SMS / Premium-SMS** erreichen den Ausblick strukturell nicht — `SMSTripFormatter`
  sieht `multi_day_trend` nie, `thunder_sms` wird nirgends gelesen
  (belegt in `feat_1680_s5a`, „Am Code gemessen" Punkt 6).
- **Compare-Ausblick** nutzt denselben `outlook.py`-Baustein; ohne Stundenreihe
  bleibt dort das Aggregatwort korrekt (#1653 AC-6).

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/email/compact.py:230-236` | **Der Prüfling.** Ausblick-Zeile, spaltenformatiert, danach `_ascii()` |
| `src/output/renderers/email/compact.py:49-61` | `_ASCII_MAP` + `_ascii()`: `⚡`→`T`, `·`→`-`, danach `fold_ascii()` |
| `src/output/renderers/email/outlook.py:358-410` | Vorbild Klartext: Zweiglogik day-token → `hourly_thunder`-NONE → `thunder_plain` |
| `src/output/renderers/email/outlook.py:43-59` | `_thunder_token_parts()` — zerlegt `leicht@5(hoch@15)` in (Wort, Stunde, Peak-Zusatz) |
| `src/output/renderers/narrow.py:571-609` | Vorbild Telegram: dieselbe Zweiglogik, anderes Format (mit Uhrzeit) |
| `src/output/renderers/email/helpers.py:1005-1065` | `format_trend_tokens()` — SSoT, liefert `thunder_day_token`, `thunder_night_token`, `thunder_day_origin`, `thunder_plain` |
| `src/output/renderers/email/__init__.py:109` | Einziger Aufrufer von `render_compact()` |

## Existing Patterns

**Die Zweiglogik existiert bereits dreimal fast identisch** (`outlook.py:373-386`,
`narrow.py:588-601`):

1. Liegt ein `thunder_day_token != "-"` vor → Tageswort daraus.
2. Sonst, wenn `stage["hourly_thunder"]` gefüllt ist → ausdrücklich „kein Gewitter"
   (`_THUNDER_MAP["NONE"]["plain"]`) — Stundenreihe da, im Tagesfenster aber leer.
3. Sonst (Alt-Aufrufer, Compare: gar keine Stundenreihe) → `thunder_plain`.
4. Nacht: `thunder_night_token != "-"` → Zusatz `· nachts …`.

Das Format unterscheidet sich je Kanal (Klartext ohne Uhrzeit am Tagesteil,
Telegram mit) — die **Entscheidung** ist identisch, die **Darstellung** nicht.

## Dependencies

- **Upstream:** `format_trend_tokens()` (helpers.py) — liefert alle nötigen Token
  bereits; `multi_day_trend`-Stages kommen aus `trip_report_scheduler.py` und tragen
  `hourly_thunder` / `day_window_start_hour` / `day_window_end_hour`.
- **Downstream:** `render_compact()` → `render_email()` → Kurzformat-Mail-Body.
  Kein weiterer Verbraucher.

## Existing Specs

- `docs/specs/modules/fix_1653_ausblick_tag_nacht_trennung.md` — AC-1..AC-8, das Muster
- `docs/specs/modules/feat_1680_s5a_gewitter_herkunft_ausblick.md` — AC-13 (s. Risiko 1)
- `docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md` — AC-11 Byte-Paritätswächter

## Bestehende Wächter, die diese Änderung berühren

| Test | Wirkung |
|---|---|
| `tests/tdd/test_thunder_origin_outlook.py::test_ac13_kompaktmail_bleibt_zeichengleich` | **Sichert zu, dass die Kompakt-Mail unempfindlich gegen die Trägerinformation ist.** Bleibt grün, solange wir KEINE Herkunft aufnehmen; wird rot, sobald wir sie aufnehmen |
| `tests/tdd/test_trip_outlook_parity.py` | Byte-Parität der Trip-Mail gegen aufgezeichnete Golden-Dateien — bewacht `outlook.py`; arbeitet **für** uns, falls wir dort refaktorieren |
| `tests/tdd/test_outlook_day_night_thunder_split.py` | #1653-Nachweise für Kanäle 1–3 |
| `tests/tdd/test_issue_811_mode_matrix.py` + `briefing_mail_validator.py` | **Commit-Gate** (`renderer_mail_gate.py`): `compact.py` liegt in `src/output/renderers/email/*.py`, beide müssen frisch vorliegen |

## Risks & Considerations

**Risiko 1 — AC-13 aus #1680 S5a ist eine freigegebene Zusicherung (PO-go 2026-08-13).**
Sie lautet: der Kompakt-Ausblick bleibt zeichengleich, *„er liest `thunder_plain` und
wird von dieser Scheibe nicht berührt"*. Die **Begründung** der Zusicherung fällt mit
#1671 weg (er liest dann nicht mehr `thunder_plain`; und `·`→`-` ist eine saubere
Faltung, keine Zerstörung). Die Zusicherung selbst bleibt aber gültig, bis sie
abgelöst wird. ⇒ **PO-Entscheidung nötig**, ob die Herkunft (`thunder_day_origin`)
mitkommt. Ohne ausdrückliche Ablösung: Herkunft bleibt draußen, AC-13 bleibt grün.

**Risiko 2 — Format im ASCII-Spaltenlayout.** Die Zeile ist
`{weekday:<3} {name:<26} {temp:<8} {precip:<5} {wind:<5} {thunder}` und wird
anschließend gefaltet. `⚡mittel @16 · nachts hoch @2` wird zu
`Tmittel @16 - nachts hoch @2`. Die Gewitterspalte steht am Zeilenende, hat keine
feste Breite — ein Zusatz sprengt kein Raster, verlängert aber die Zeile.

**Risiko 3 — viertes Duplikat.** Wird die Zweiglogik ein viertes Mal kopiert,
entsteht genau das Muster, das #1671 überhaupt erst erzeugt hat: drei Stellen
umgestellt, eine vergessen. Ein geteilter *Entscheidungs*-Helper (Zweigwahl, nicht
Formatierung) in `helpers.py` schließt die Fehlerklasse ursächlich. Der
Byte-Paritätswächter aus #1361/#1368 ist dabei der Nachweis, dass ein Umbau an
`outlook.py` nichts an der Ausgabe ändert.

**Risiko 4 — Nachweisaufwand.** `renderer_mail_gate.py` verlangt vor dem Commit
zwingend einen frischen `test_issue_811_mode_matrix.py`-Lauf **und** einen
erfolgreichen `briefing_mail_validator.py`-Lauf gegen eine echt zugestellte
Staging-Mail im Kurzformat. Das ist der teurere Teil der Scheibe, nicht der Code.
