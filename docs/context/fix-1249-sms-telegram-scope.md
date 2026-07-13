# Context: fix-1249-sms-telegram-scope

## Request Summary

**#1249** — SMS und Telegram nennen bei mehreren amtlichen Warnungen mit **unterschiedlichem** Umfang den Ort/Abschnitt der **führenden** (schwersten) Warnung, als gälte er für alle. Der Empfänger liest „nur Toulon" und darunter vier Gefahren, von denen zwei Toulon gar nicht betreffen.

Dieselbe Fehlerklasse wurde in der **E-Mail** mit #1238/#1239 behoben (Betreff, Einleitungszeile, Quelle-Box). SMS/Telegram standen dort ausdrücklich außerhalb des Umfangs (Known Limitation der Spec) und sind unverändert.

**Gewicht:** SMS und Telegram sind laut Projektzweck die Kanäle für **unterwegs** — genau dort, wo der Empfänger die Mail nicht nachschlagen kann.

## Related Files

Alles in `src/output/renderers/alert/official_alerts.py`:

| Stelle | Was passiert |
|---|---|
| `render_official_alert_sms` (~`:1300`) | **uniform-Zweig:** `suffix = f", {leading.sms_scope}"` — EIN Ortszusatz am Ende, gilt für alle Tokens. **Bug.** **mixed-Zweig:** `... {n.sms_scope}` pro Token — **bereits korrekt**, dient als Vorbild. |
| `render_official_alert_telegram` (~`:1250`) | Kopfzeile `head = f"{prefix} · {leading.scope_label} · ..."` — Umfang der führenden Warnung. **Bug.** Die Warnungs-Zeilen darunter tragen **gar keinen** Umfang → der Empfänger kann nicht zuordnen. Zusätzlich `_hazard_display(n.alert)` (generisches Typ-Wort) statt `_display_label` → „Zugang gesperrt" statt „Zugang eingeschränkt — Monts Toulonnais", widerspricht der Mail. |
| `_sms_truncate` (`:1363-1375`) | Budget-Kürzung: behält ganze Tokens, hängt `+K`-Auslassungsmarker an, `suffix` immer. **Trägt die PO-Entscheidung bereits** — Tokens fallen als Ganzes weg, nie mitten im Wort. |

**Bereits vorhandene Bausteine (aus #1238/#1239, wiederzuverwenden — keine dritte Kopie):**

| Baustein | Zweck |
|---|---|
| `_uniform_scope(notices)` | Prüft **identitätsbasiert** (über `scope_ids`, nicht Anzeige-Namen), ob alle Warnungen denselben Umfang haben. Gleichnamige, aber verschiedene Orte kollabieren NICHT (F009). |
| `_display_label(alert)` | Reicher Quell-Label ersetzt das generische Typ-Wort; entfernt die numerische Quell-Stufe, wo ein Stufenwort danebensteht. Speist Betreff, Standalone-Titel, embedded Block, Aggregat-Banner. |
| `OfficialAlertNotice.sms_scope` / `.scope_label` / `.scope_ids` | Umfang je Warnung, bereits pro Notice gesetzt |

## Aufrufer

`src/services/notification_service.py` — Trip-Standalone (`:517` Telegram, `:548` SMS) und Compare-Standalone (`:652` Telegram, `:672` SMS).

## Existing Patterns

- **`_hazard_display(alert)[1]`** liefert das 2-Buchstaben-SMS-Kürzel — davon darf die SMS **nicht** abweichen (Zeichenbudget). `_display_label` gilt nur für ausgeschriebene Anzeigetexte (Telegram/Mail), nicht für das SMS-Kürzel.
- Der **mixed-level-Zweig der SMS** zeigt bereits, wie ein Umfang pro Token aussieht: `f"{kuerzel} {stufe} {zeit} {n.sms_scope}"`.

## PO-Entscheidung (locked)

**SMS bei unterschiedlichem Umfang:** Jede genannte Warnung trägt ihren **eigenen** Ort. Passt nicht alles ins Zeichenlimit, fallen die **schwächeren** Warnungen weg (`+N`-Marker) — lieber weniger Warnungen, die stimmen, als alle mit falscher Ortsangabe.

## Risks & Considerations

1. **SMS-Zeichenbudget (Default `limit=140`, GSM-7/ASCII).** Ein Ort pro Token frisst Zeichen. `_sms_truncate` löst das, aber die Nachricht darf nie in einem Token abgeschnitten werden und muss immer mindestens die schwerste Warnung samt Ort enthalten.
2. **Telegram-Zeilen tragen heute gar keinen Umfang** — die Ergänzung ist additiv, aber sie verändert das gewohnte Format. Bei einheitlichem Umfang soll die Kopfzeile ihn weiterhin nennen (dann ist die Aussage korrekt) und die Zeilen bleiben schlank.
3. **Non-Regression:** Bei **einheitlichem** Umfang müssen SMS und Telegram **bit-identisch** bleiben — die heutige Aussage ist dort korrekt.
4. **`_display_label` in Telegram** ändert den sichtbaren Text (z.B. „Extreme Hitze" statt „Hitze"). Das ist gewollt (Gleichlauf mit der Mail), bricht aber ggf. Bestandstests.
5. **Goldens:** `tests/golden/test_sms_golden.py` prüft SMS-Ausgaben.
