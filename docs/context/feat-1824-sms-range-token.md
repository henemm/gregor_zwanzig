# Context: SMS-Format — Range-Token + Trennzeichen (#1824)

## Request Summary

Zwei Änderungswünsche des PO aus der Lektüre des echten KHW-SMS-Briefings:

- **(A) Range-Token:** Temperatur-Paare als ein Token statt zwei (`K13 D27` → `D13-27`,
  `FK13 FD27` → `FD13-27`). Nacht (`N`/`FN`) bleibt Einzelwert (PO-Vorgabe wörtlich).
- **(B) Trennzeichen:** Token, deren Wert mit einem Buchstaben beginnt, brauchen einen
  Trenner (`WDN` → `WD:N`). PO-Regel wörtlich: „der Trenner wird aber IMMER benötigt, wenn
  auf die Kürzel ein weiterer Buchstabe folgt."

Ein dritter Punkt (`SU14` = Sonnenstunden) hat sich als korrekt und dokumentiert erwiesen.

## 🔴 Vorbefund, der die Ausgangslage ändert: die Auswertungswahl existiert bereits

Der PO fragte ursprünglich: *„wo kann ich in der Konfiguration wählen, ob ich Höchst- bzw.
Tiefsttemperatur überhaupt sehen will? Mir reicht vielleicht die Höchst-Temperatur"* — und
bekam von mir die **falsche** Antwort „geht nicht, ein gemeinsamer Ein/Aus-Schalter".

**Das ist seit #1357 (UI) bzw. #1660 Scheibe A (SMS-Wirkung) falsch.** Beleg:

- `src/output/renderers/trip_report.py:420-430` — `_AGG_GATE_SYMBOLS` gated `K`/`D`/`FK`/`FD`
  **unabhängig voneinander** über `MetricConfig.aggregations` aus der globalen Metrikliste.
- UI: Touren-Editor → Wettergrößen → Abschnitt „Auswertungen"
  (`frontend/src/lib/components/shared/WeatherMetricsTab.svelte:1644 ff.`). Größen mit mehreren
  Auswertungen (Temperatur, gefühlte Temperatur) bekommen je Auswertung ein eigenes Kästchen.
- Wirkung: abgewählt ⇒ Kürzel entfällt **vollständig** (nicht mal Null-Form).

⇒ Der ursprüngliche Anlass für (A) ist damit **bereits ohne jede Entwicklung lösbar**.
Das entwertet (A) nicht automatisch (kompaktere Darstellung bleibt ein eigener Nutzen), ändert
aber die Kosten/Nutzen-Rechnung grundlegend.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/tokens/builder.py:316-355` | Temperatur-Schleife: sechs Symbole (N/K/D/FN/FK/FD) in EINER Schleife, `(sym, val, evening_only, needs_spec)` |
| `src/output/tokens/builder.py:409-422` | WD/PT-Schleife — die einzigen zwei Token mit Buchstaben-Wert ohne Trenner |
| `src/output/tokens/dto.py:130-135` | `Token.render()`: `f"{symbol}{value}"`, reine Konkatenation, **keine** Trennlogik |
| `src/output/tokens/render.py:84-99` | Kürzungsreihenfolge: hartkodierte Literal-Tupel `("FN","FK","FD")` und `("K","D","N")` — NICHT das `PRIORITY`-Dict |
| `src/app/metric_catalog.py:700-706` | `SMS_MULTI_SYMBOLS_BY_METRIC`: `temperature:("K","D")`, `wind_chill:("FK","FD","WC")` |
| `api/routers/config.py:30-69` | `/api/sms-symbols` speist die Kürzel-Badges im Editor direkt aus obigem Dict — bewusst keine zweite Frontend-Liste |
| `src/output/renderers/trip_report.py:446` | `max_length=160` — die real geltende Grenze des Briefing-Pfads |
| `docs/reference/sms_format.md` | Bindende Formatdoku, v2.24, 607 Zeilen — §2/§3.2/§3.2a/§4/§6/§9/§12 betroffen |

## Existing Patterns

- **Trenner gehört ins SYMBOL, nicht in den Wert.** Präzedenzfälle im selben File:
  `FORECAST_TH = "TH:"` (`builder.py:17`), `VIGI_HR = "HR:"` (`:29`), `"Z:"`/`"M:"` (`:250,256`),
  amtliche Warnungen `f"{symbol}:"` (`:231`). Für (B) ist der Weg damit vorgezeichnet.
- **Keine zwei unabhängig nullbaren Werte in einem Token.** Kein Präzedenzfall im Code.
  Threshold+Peak kombiniert zwei Zahlen, aber aus derselben Stichprobe mit EINER Null-Form.
  Der einzige echte Paar-Fall (Vigilance `HR:`/`TH:`) bleibt bewusst **zwei getrennte Token**.
- Testhelfer parsen Token strukturell als whitespace-getrennte Einzelwerte per
  `fullmatch(r"{symbol}(-?\d+|-|\?)$")` — `tests/tdd/_min_temp_felt_fixtures.py:207,223`,
  `tests/tdd/_hiking_window_fixtures.py:484,506-515`.

## Dependencies

- **Upstream:** `MetricConfig.aggregations` (Auswertungswahl), `SMS_MULTI_SYMBOLS_BY_METRIC`,
  Positions-Kaskade #1677.
- **Downstream:** SMS **und** Premium-SMS (gemeinsamer `report.sms_text`, ADR-0049/D8) —
  auf dem KHW ist Premium-SMS auf der Hütte der einzige Empfangsweg. E-Mail/Telegram nicht betroffen.

## Existing Specs

- `docs/reference/sms_format.md` (v2.24) — bindend
- `docs/specs/modules/trip_min_temp_and_felt_shortforms.md` (#1410)
- `docs/specs/modules/fix_1660b_sms_token_wiring.md` — AC-6/AC-7 fordern **wörtlich** die Token
  `WDNW`/`PTS`; Änderung (B) macht diese ACs ungültig, Text muss mitgezogen werden
- `docs/specs/modules/fix_1677_sms_reihenfolge.md` — POSITIONAL-Sortierung, K/D/FK/FD/WD/PT als Einzelanker

## Risks & Considerations

### Zu (A) Range-Token — drei belegte Probleme

1. **Negative Temperaturen sind kein Randfall, sondern dokumentiertes Feature.**
   `sms_format.md:397-399` führt sie explizit (`N-12`, `D-5`, `WC-22`).
   Echte Winter-Fixture existiert (`tests/tdd/test_sms_snow_symbols.py:51`, `temp_min_c=-12.0`,
   `temp_max_c=-4.0`). Live gemessen: heute `K-12 D-4` → als Bindestrich-Range `D-12--4`.
   Der E-Mail-Renderer nutzt für Bereiche den En-Dash `–` (`email/helpers.py:945,1473`) — der ist
   **nicht GSM-7** und würde die SMS still auf UCS-2 zwingen (halbe Kapazität). Als SMS-Trenner
   unbrauchbar. GSM-7-sichere, noch freie Kandidaten: `/`, `_`.
2. **Vier reale Zustände, nur einer passt.** Durch die Auswertungswahl (s.o.) sind „nur Tiefst",
   „nur Höchst", „beide", „keines" alle real konfigurierbar. Ein Zwei-Werte-Token unterstellt
   „immer Spanne". Dazu 3×3 Null-/Lücken-Kombinationen (`-`, `?`, Wert) pro Hälfte.
3. **Der Gewinn ist ~1 Zeichen von 160.** Nachgerechnet an einer echten Briefing-Zeile:
   Range spart 3 Zeichen (`K`, `FK` fallen weg), die neuen Doppelpunkte kosten 2 → **netto −1**.

### Blast Radius, getrennt nach Änderung

| | (A) Range-Token | (B) Trennzeichen |
|---|---|---|
| Tests „bricht sicher" | **24 Dateien** inkl. 2 geteilte Helfer-Module | **3 Stellen** (`test_sms_extended_tokens_truncation.py:185`, `test_sms_extended_null_forms.py:195,215`, `test_sms_user_metric_order.py:461`) |
| Golden-/Byte-Identitäts-Tests | **5** `tests/golden/sms/*.txt` + 1 Textreport-Golden — alle enthalten K/D-Paare | 0 (kein Golden enthält WD/PT) |
| Doku-Stellen | §2, §3.2, §4, §6, §9, §12 + 2 Modul-Specs | §3.2a:179, §4:385, §12 + `fix_1660b`-ACs |
| Weitere Kopplung | `SMS_MULTI_SYMBOLS_BY_METRIC`, `/api/sms-symbols`, Editor-Badges, Kürzungsreihenfolge, Positions-Kaskade | keine |

### Offene Entscheidungen für den PO

1. **(A) überhaupt noch gewollt**, nachdem die Auswertungswahl den ursprünglichen Anlass löst?
2. Falls ja: **Trennzeichen bei negativen Werten** — anderes Zeichen (`/`) oder Rückfall auf
   Zwei-Token-Form bei Minusgraden?
3. Falls ja: **welches Kürzel trägt die Range** — `D` (PO-Vorschlag) oder `K` (bestehende
   Code-Konvention `_kurzform_kuerzel()` nimmt `mehrfach[0]`, also `K`)?
4. **(B) Null-Form:** wird `WD-` zu `WD:-`, oder bleibt die Null-Form ohne Trenner?
   (Entscheidet, ob `test_sms_extended_null_forms.py` mitbricht.)
5. **(B) Rand-Bestätigung:** `DBG[...]` beginnt mit `[`, `CL` (access_ban) hat gar keinen Wert —
   beide vermutlich außerhalb der Regel, kurz bestätigen.
