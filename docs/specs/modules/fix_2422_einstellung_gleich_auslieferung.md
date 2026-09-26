---
entity_id: fix_2422_einstellung_gleich_auslieferung
type: bugfix
created: 2026-09-26
updated: 2026-09-26
status: draft
version: "1.0"
tags: [testing, invariante, konfiguration, kanaele, orakel]
workflow: fix-2422-konfig-auslieferung-testluecken
---

# Fix #2422 (Scheibe S1): Invarianten-Test „Einstellung = Auslieferung"

## Approval

- [ ] Approved

## Purpose

Issue #2422 (PO): Eine im Trip-Editor eingestellte Kanal-Konfiguration kam nicht so an, wie
eingestellt (Fall „KHW 403") — und **kein Test hat es gemerkt**. Diese Scheibe (S1) liefert den
zugesagten Invarianten-Test „Einstellung = Auslieferung": EIN Test, der für die wählbaren Metriken
× alle sechs Ausgabe-Formen prüft, ob das, was im gespeicherten Trip-JSON steht, tatsächlich am
Transport ankommt — Einstieg über das Persistenzformat des Editors, echter Loader/Kaskade/
Formatter, Naht ausschließlich an den Transport-Klassen. Jede aktuell bestehende Abweichung wird
über ein begründetes Ausnahme-Register sichtbar gemacht statt stillschweigend grün durchgewunken
(Kernfrage des PO: „Warum sieht das kein Test?"). S1 ändert **kein** Produktverhalten.

## Deckungstabelle: Befund → Ort

Jeder Befund aus `docs/context/fix-2422-konfig-auslieferung-testluecken.md` bekommt hier einen
festen Platz. Nicht jeder Befund ist durch die S1-Golden-Fixtures überhaupt AUSLÖSBAR — ein
Register-Eintrag existiert nur für Befunde, die die Golden-Varianten tatsächlich als rote Zelle
erzeugen (sonst wäre der Eintrag beim ersten Lauf schon „veraltet", AC-7).

| # | Befund | Ort | Begründung |
|---|---|---|---|
| B1 | `wind_chill` ohne Kürzel fällt in Kurzform/SMS/Premium still weg | **Register-Eintrag in S1** (befristet, ausgelöst durch Golden A/B) | Bekannte Lücke (KHW 403); Variantenwahl V1 (Kürzel) vs. V2 (Editor-Hinweis) ist explizit NICHT Teil von S1 → siehe „Außerhalb des Umfangs" |
| B2 | Kurzform/SMS/Premium ignorieren Roh/Einfach (`format_mode` fehlt in `MetricSpec`) | **Register-Eintrag in S1** (befristet, kanalweit für sms/telegram_kurzform/premium_sms, ausgelöst durch Golden B) → Fix in Scheibe S6+ | Eigene Fix-Scheibe |
| B3 | Telegram rich erbt Roh/Einfach aus dem E-Mail-Layout statt dem eigenen | **Register-Eintrag in S1** (befristet, ausgelöst durch Golden B) **+ eigenes GitHub-Issue** | Nutzersichtbar und eigenständig — Nebenbefund-Triage-Kriterium (a) erfüllt (CLAUDE.md „Backlog & Nebenbefunde") |
| B4 | Telegram-Tab bei `telegram_style=kurzform` komplett wirkungslos, Editor sagt es nicht | **Kein S1-Register-Eintrag** — Quellzuordnung „Kurzstil/Premium ← `channel_layouts.sms`" steht direkt in der Orakel-Regel (wie B6, keine Zelle, keine Ausnahme); die fehlende Editor-Sichtbarkeit ist reines Frontend → Scheibe S6+ | Verhalten selbst bleibt (#1260) |
| B5 | `wind_direction` (Skalenmodus) + `wind` erzeugt Geisterspalte „WD" mit `–` in Telegram rich | **Register-Eintrag in S1** (befristet, ausgelöst durch Golden B) → Fix in Scheibe S6+ | Eigene Fix-Scheibe |
| B6 | Kanal-Layout kann nur abwählen — globales Maximum aus `display_config.metrics` (ADR-0050) | **Direkt in der Orakel-Regel**, kein Register-Eintrag → Editor-Anzeige-Konsistenz in Scheibe S2 | Gewollte Kernregel der Kaskade, nicht Ausnahme — siehe Orakel-Entscheidung unten |
| B7 | Editor ignoriert `bucket`/`morning_enabled`/`evening_enabled`/`channel_layouts_per_report` | **Kein S1-Register-Eintrag** — `report_type`/`bucket` ist keine der drei S1-Matrix-Dimensionen (Metrik × Kanal × erscheint/Reihenfolge/Roh-Einfach), Golden löst es nicht aus | Editor-Hinweis in Scheibe S6+, Ketten-Test in Scheibe S3 |
| B8 | `show_outlook` wirkt nur auf E-Mail | **Kein S1-Register-Eintrag** — `show_outlook` ist kein Kanal-Layout-Merkmal, keine Metrik der Matrix | Beschriftung-Prüfung in Scheibe S6+ |
| B9 | SMS-Nutzerposition wirkt nur bei Kaskadenquelle `per_channel`/`per_report` | **Kein S1-Register-Eintrag** — beide Goldens setzen immer `per_channel_layouts`, der `global`-Fallback wird nicht ausgelöst | Kaskadenquelle im Editor zeigen in Scheibe S2 |
| — | Zugesagte Invariante „Editor-Anzeige = gespeicherter Stand" | **Scheibe S2** (TS-Bein) | S1 prüft nur JSON → Transport, nicht JSON → Editor-Anzeige |
| L1 | Alarm-Familie: keine Kette gespeichertes JSON → Transport | Scheibe S4 | Außerhalb der S1-Matrix (Trip-Briefing-Kanäle, keine Alarme) |
| L2 | Kanal an/aus im regulären Slot-Briefing ungetestet | Scheibe S3 | Außerhalb der S1-Matrix |
| L3 | `email_format=compact`, `morning_enabled`/`evening_enabled`, `sms_threshold` ungetestet | Scheibe S3 | Außerhalb der S1-Matrix |
| L4 | Ortsvergleich `channel_active_metrics` + Kanalwahl ungetestet | Scheibe S5 | Ortsvergleich hat eigene Auswahl, kein Kurzstil/Premium, eigener Datenpfad |

## Außerhalb des Umfangs → Unter-Issue

Diese Zeilen sind bewusst **keine** Acceptance Criteria dieser Spec. Sie werden als Unter-Issues
unter dem Dach-Issue #2422 angelegt.

| Scheibe | Inhalt |
|---|---|
| S2 | TS-Bein (Editor-Serialisierung → Golden) + Go-Bein (PUT-Merge → Golden) + Invariante „Editor-Anzeige = gespeicherter Stand"; zusätzlich Editor-Anzeige-Konsistenz für B6/B9 |
| S3 | Kette Kanal an/aus, Versandzeiten, `email_format`, `sms_threshold`, `bucket`/`morning_enabled`/`evening_enabled`/`channel_layouts_per_report` (L2, L3, B7-Ketten-Anteil) |
| S4 | Kette Alarm-Familie (Schwellen, Radar/Regen, amtliche Warnungen) JSON → alle vier Kanäle (L1) |
| S5 | Kette Ortsvergleich `channel_active_metrics` + Kanalwahl (L4) |
| S6+ | **B1-Variantenwahl** (V1 eigenes Kürzel für gefühlte Temperatur vs. V2 Editor-Hinweis „erscheint in SMS/Kurzform nicht" — PO-Entscheidung nötig, gehört zur späteren Fix-Scheibe, nicht zu S1); B2 (`format_mode`-Fix); B3 (eigenes Issue, siehe Deckungstabelle); B4 (Editor-Hinweis Kurzstil wirkungslos); B5 (Geisterspalte-Fix); B7 (Editor-Hinweis bucket/morning/evening/`channel_layouts_per_report`); B8 (Beschriftung `show_outlook` prüfen) |

## Source

- **File:** `tests/tdd/test_einstellung_gleich_auslieferung.py` (neu)
- **Identifier:** Invarianten-Test-Funktion(en) über die Matrix Metrik × Kanal × Dimension
  (Testdatei nach Verhalten benannt, nicht nach Issue-Nummer — vgl. `test_naming_gate.py`)

> **Schicht-Hinweis:** Diese Spec ist Python-Core/Test-Infrastruktur (`tests/`, liest `src/app/`,
> `src/output/`, `src/services/`). Kein Frontend-, kein Go-Code betroffen — S2 übernimmt die
> anderen beiden Beine.

## Estimated Scope

- **LoC:** ~0–20 produktiv (allenfalls minimale Erweiterung des Aufzeichner-Helfers um
  `body`/`plain_text_body`/`parse_mode`, selbst Test-Infrastruktur) / ~550–650 Test-LoC
- **Files:** ~6 neu (Invarianten-Test, Orakel-Modul, Ausnahme-Register, zwei Golden-Trip-JSONs,
  synthetische Voll-Wetter-Fixture, Parser-Helfer für Telegram-rich-Tabellenkopf/
  E-Mail-Spaltenreihenfolge), 1 geändert (Aufzeichner-Helfer aus
  `test_kanaltreue_adhoc_antwort.py` als geteilter Baustein extrahiert), 1 dokumentiert
  (`docs/reference/gates_und_ratschen.md`, Regel-Budget-Zeile)
- **Effort:** medium (kein Produktverhalten geändert, aber die Orakel- und Golden-Konstruktion
  entscheidet, ob der Test überhaupt etwas bewacht — Risiko liegt in der Testkonstruktion, nicht im
  Code-Umfang)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0050 (Metrik-Kaskade) | ADR | Begründet die Orakel-Kernregeln „aktives Kanal-Layout ∩ globales Maximum" (B6) und „Kurzstil/Premium ← `channel_layouts.sms`" (B4) |
| `SMS_SYMBOL_BY_METRIC`, `SMS_MULTI_SYMBOLS_BY_METRIC`, `SMS_SYMBOL_GRAMMAR`, `COMPACT_LABEL_EXCEPTIONS` (`src/app/metric_catalog.py:772-843`) | Register (Daten) | Ausschließlich zum **Parsen** (Token → Metrik) im Kurzform-/SMS-/Premium-Text — niemals zur Erwartungsbildung |
| `src/app/loader.py` (`load_trip`, `_parse_display_config`) | Modul | Echter Einstieg: Golden-Trip-JSON → Trip-Objekt, ungemockt |
| `src/app/models.py` (`get_metrics_for_channel`, `_sorted_by_layout`, `_clip_to_global_maximum` o. ä.) | Modul | Läuft echt im Testpfad; die Orakel-Funktion importiert daraus NICHTS |
| `src/output/renderers/trip_report.py:136` (`get_metrics_for_channel("email", …)`), `:335` (`get_metrics_for_channel("sms", …)`) | Code-Beleg | Bestätigt: E-Mail hat eigene Kanal-Quelle, SMS-Text (geteilt von Kurzstil/Premium) hat eigene |
| `src/output/renderers/trip_report.py:142` (`build_friendly_keys(dc)` nach Email-Kollabierung) | Code-Beleg | Bestätigt B3: Telegram rich erbt diese `_friendly_keys`-Instanz von der E-Mail-Formatter-Instanz |
| `src/output/renderers/channel_layout.py:46-55` (`CHANNEL_LIMITS`, Schlüssel `email`/`telegram`/`sms`/`premium_sms`) | Code-Beleg | Bestätigt vier Kanal-Schlüssel, `premium_sms` mit identischem Limit wie `sms` |
| `src/services/notification_service.py:566,596,653,672` | Code-Beleg | Bestätigt: Kurzstil, SMS und Premium-SMS senden identisch `report.sms_text` |
| `src/services/notification_service.py` (`EmailOutput`/`SMSOutput`/`PremiumSmsOutput`/`TelegramOutput`) | Klassen | Einzige erlaubte Naht — per `monkeypatch` durch Aufzeichner ersetzt |
| `tests/tdd/test_kanaltreue_adhoc_antwort.py:88-225` | Testvorlage | Aufzeichner-Muster (`_TRANSPORT_ENV`, `_nutzer_anlegen`, `_trip_anlegen`); wird um `body`/`plain_text_body`/`parse_mode` erweitert |
| `tests/tdd/test_sms_wind_chill_position_inherits_from_anchor.py:54-84` | Testvorlage | Loader-Einstieg mit SMS-Text |
| `tests/tdd/test_sms_user_metric_order.py:121-160` | Testvorlage | Token-Parser-Muster (`_token_index`, `_present`) |
| `app/origin_guard.py:29-34` | Guard | Herkunftssperre: Nutzerkennung ohne „test"/„tdd", `sms_verified_number` Pflicht (#2406) |
| Issue #710 (Confidence nicht wählbar) | Produktentscheidung | `confidence_pct` ist von der Metriken-Matrix ausgeschlossen (`selectable=false`) |

## Implementation Details

### Zwei Golden-Trip-JSONs statt einer — sechs Kanäle sind aus einer einzigen Konfiguration nicht
### erreichbar

`telegram_style=kurzform` schließt Telegram rich aus, `send_sms=false` erreicht `SMSOutput` nie,
und Premium-SMS ist im Fall KHW 403 gar nicht erwähnt. Ein einziges Golden-JSON kann daher nicht
alle sechs Ausgabe-Formen zugleich prüfen. S1 nutzt deshalb **zwei** Golden-Trip-JSONs mit
**identischem** Metrik-Roster und identischen `channel_layouts`/`display_config.metrics` — nur die
Versand-Schalter unterscheiden sich:

- **Golden A („Basis", KHW-403-Nachbau):** `report_config.telegram_style="kurzform"`,
  `send_sms=false`, `send_premium_sms=false`. Deckt: E-Mail html, E-Mail plain, Telegram Kurzstil.
  Zweck: AC-1 (Laden treu), AC-2 (Bug-Nachweis `wind_chill × Telegram-Kurzstil × erscheint`).
- **Golden B („Kanal-Variante", gleiches Roster/Layout wie A):**
  `report_config.telegram_style="rich"`, `send_sms=true`, `send_premium_sms=true`. Deckt
  zusätzlich: Telegram rich, SMS, Premium-SMS. SMS und Premium-SMS senden laut Kontextdokument
  identisch `report.sms_text` wie Kurzstil (`notification_service.py:566,596,653,672`) — beide
  Zellen leiten sich aus **derselben** Quelle `channel_layouts.sms` ab wie Golden A's
  Telegram-Kurzstil-Zelle, keine eigene Orakel-Quelle nötig.

Zusammen deckt (A ∪ B) alle sechs Kanäle ab, ohne dass ein einzelnes Golden widersprüchliche
Versand-Schalter tragen müsste.

### Pflicht-Eigenschaften der Golden-Layouts (Implementierungs-Constraints für `/40`)

Beide Goldens zusammen müssen — über ein Metrik-Roster von ca. 8–12 wählbaren Metriken verteilt —
folgende Eigenschaften garantieren, sonst sind die Mutations-Pflichtfänge (AC-9) oder die
Zweiwertigkeit der Erscheint-Dimension (AC-2/AC-11) nicht prüfbar:

- **P1 (Reihenfolge):** Für jeden Kanal mit eigenem Layout (email, telegram_rich, sms) ist die
  gespeicherte Reihenfolge ≠ Katalog-Reihenfolge UND ≠ globale Reihenfolge (`display_config.metrics`)
  UND ≠ die Reihenfolge der anderen Kanäle. Fängt M1.
- **P2 (Clip-Nachweis, B6):** Mindestens eine im SMS-Kanal-Layout aktive Metrik ist NICHT im
  globalen Maximum enthalten → erwartet: in SMS/Kurzstil/Premium abwesend, obwohl im Kanal-Layout
  aktiv. Das ist eine korrekte, gewollte Anwendung der Clip-Regel (kein Register-Eintrag), UND der
  Fang für M2, falls die Mutation sie durchlässt.
- **P3 (globaler Überhang):** Das globale Maximum enthält mindestens eine Metrik, die in KEINEM
  Kanal-Layout aktiv ist. Erwartet: in allen Kanälen abwesend. Fängt M4, falls die Mutation die
  globale Liste statt des Kanal-Layouts liest (dann erschiene diese Metrik überall zusätzlich, in
  falscher Position).
- **P4 (Roh/Einfach-Divergenz, unabhängig von B3):** Mindestens eine Metrik mit
  `has_friendly_format=True`, deren `format_mode` im E-Mail-Layout „einfach" und im
  Telegram-rich-Layout „roh" ist (oder umgekehrt) — UND dieses Paar ist NICHT dieselbe Metrik wie
  die für den B3-Register-Eintrag verwendete. Erwartet: beide Kanäle zeigen ihren jeweils EIGENEN
  Modus. Fängt M3, wenn `build_friendly_keys` die falsche `dc` liest.
- **P5 (KHW-403-Nachbau, B1):** `wind_chill` aktiv in `channel_layouts.sms`, Position 0.
- **P6 (Roh/Einfach-Divergenz für B3):** Mindestens eine zweite Metrik mit
  `has_friendly_format=True`, deren `format_mode` im E-Mail-Layout und im Telegram-rich-Layout
  bewusst unterschiedlich gesetzt ist, um den bestehenden Produktionsfehler B3 zu reproduzieren
  (Telegram rich zeigt den E-Mail-Modus statt seines eigenen).
- **P7 (Geisterspalte, B5):** `wind_direction` im Skalenmodus + `wind` beide im
  `telegram`-Kanal-Layout, aber `wind_direction` nicht selbst aktiv gewählt (Golden B).
- **P8 (Zweiwertige Erscheint-Dimension):** mindestens eine Metrik, die NICHT im Telegram-Layout
  aktiv ist, aber über die geteilte SMS-Quelle im Kurzform-/SMS-/Premium-Text erscheint (z. B.
  `sunshine`, analog zum KHW-403-Befund) — Nachweis, dass „unerwartet zusätzlich" als eigener
  Rot-Grund erkannt wird, nicht nur „erwartet, aber fehlt".

Die konkrete Zuordnung Metrik-ID → Eigenschaft ist Implementierungsdetail von `/40`, keine
Spec-Vorgabe — diese Liste ist die Abnahme-Grundlage dafür, dass das Golden-Paar konstruiert genug
ist.

### Synthetische Voll-Wetter-Fixture

Neue Datei (Vorbild `tests/tdd/_min_temp_felt_fixtures.py`) mit **allen** Feldern, die die
bestehenden `openmeteo`-Fixtures nicht abdecken (humidity, dewpoint, pressure, wind_chill_c,
cloud_mid/high, precip_type, snow_new_24h) — Ziel: rote Zellen entstehen an Konfig-Logik, nicht an
fehlenden Rohdaten.

### Ausnahme-Register

Datenstruktur (keine Produktfunktion, kein Import aus `src/app/models.py`):

```python
@dataclass(frozen=True)
class AusnahmeEintrag:
    metrik: str          # metric_id, oder "*" fuer eine kanalweite Ausnahme (B2)
    kanal: str            # "email_html" | "email_plain" | "telegram_rich" | "telegram_kurzform" | "sms" | "premium_sms"
    dimension: str        # "erscheint" | "reihenfolge" | "roh_einfach"
    befund: str           # Pflichtfeld, z. B. "B1", "#2412" — keine leere Referenz
    grund: str            # Pflichtfeld — keine leere Begruendung
    befristet: bool       # True = Fix in eigener Scheibe geplant
```

Beim S1-Abschluss enthält das Register mindestens die Befunde B1, B2 (kanalweit), B3, B5 —
siehe Deckungstabelle — **plus** je einen Eintrag für jede strukturelle Ausnahme (160er-Budget/
`DROP_ORDER`, Telegram-7er-Tabellenlimit, `VISIBILITY_GATE_IDS`), die von den Goldens tatsächlich
ausgelöst wird, mit Referenz auf das begründende Issue/ADR. Maßgeblich ist nicht eine feste Zahl,
sondern die Mengengleichheit „Register-Zellen == rote Zellen ohne Register" (AC-6). Für B4/B6/
B7/B8/B9 gibt es bewusst KEINEN Eintrag (siehe Deckungstabelle-Begründungen).

### Orakel-Regel

> Erwartet wird für Kanal `email_html`/`email_plain`: die im `channel_layouts.email`-Layout aktive
> Teilmenge des globalen Maximums (`display_config.metrics`), in gespeicherter Reihenfolge, mit
> gespeichertem Roh/Einfach-Modus DIESES Layouts.
> Erwartet wird für Kanal `telegram_rich`: dieselbe Regel, Quelle `channel_layouts.telegram`.
> Erwartet wird für Kanal `sms`, `telegram_kurzform` UND `premium_sms`: dieselbe Regel, Quelle
> **immer** `channel_layouts.sms` (strukturelle Kaskadenregel „Kurzstil/Premium ← SMS", B4 — kein
> Register-Eintrag, weil sie für JEDE Metrik gleich gilt, nicht punktuell).
> Reihenfolge- und Roh/Einfach-Zellen werden NUR für Metriken gebildet, die auf BEIDEN Seiten
> (Erwartung und tatsächlicher Text) vorkommen — der Schnittmenge. Fehlt eine Metrik im Text, ist
> das ausschließlich eine Erscheint-Abweichung; ihre Reihenfolge- und Roh/Einfach-Zellen werden
> NICHT zusätzlich als rot gezählt (löst sonst den Widerspruch aus AC-2 aus: eine fehlende Metrik
> dürfte nicht drei Zellen gleichzeitig rot färben).
> Die Erscheint-Dimension ist zweiwertig: eine erwartete, aber im Text fehlende Metrik ist ebenso
> rot wie eine nicht erwartete, aber im Text zusätzlich auftauchende Metrik (P8/B4-Nachweis).

**Begründung für „globales Maximum (B6) und Kurzstil/Premium-Quelle (B4) direkt in der Regel, nicht
im Register":** Ein Register-Eintrag ist für eine **punktuelle** Abweichung mit eigenem Befund/
Grund gedacht — etwas, das *nicht* der Kaskade folgt. Das globale Maximum und die
Kurzstil/Premium-Quellzuordnung sind dagegen Teil der Definition von „aktiv" bzw. „Quelle" selbst
(ADR-0050, gilt identisch für jede Metrik/jeden Kanal, keine Ausnahme mit eigenem Fall). Würde man
sie ins Register aufnehmen, bräuchte jede einzelne Metrik-Kanal-Kombination ihre eigene Zeile — das
Register würde von den echten, punktuellen Abweichungen (B1/B2/B3/B5) überdeckt.

**Unabhängigkeit durch Konstruktion:** Die Orakel-Funktion nimmt ausschließlich das rohe
`json.load`-Dict des Golden-Trip-JSON entgegen — kein geladenes `Trip`/
`UnifiedWeatherDisplayConfig`-Objekt, kein Import von `get_metrics_for_channel`,
`resolve_metric_col_order` oder `_sorted_by_layout` aus `src/app/models.py`/`src/output/`.
**Verhaltensnachweis statt Static-Analysis-Test:** Würde die Orakel-Funktion heimlich
`_sorted_by_layout` (o. ä.) nutzen, bliebe Mutation M1 grün, weil beide Seiten (Erwartung UND
tatsächlicher Text) gleich falsch würden. AC-9 verlangt ausdrücklich Rot bei M1 — das ist der
Nachweis, nicht eine zusätzliche AST-/`inspect.getsource`-Prüfung (solche „Verhaltenstests" auf
Testcode selbst sind laut Kontextdokument genau das Muster, das in Sammel-Eintrag #1196 landet,
nicht in einem neuen Gate).

### Kürzel-Register — nur Parsen, nie Erwarten

`SMS_SYMBOL_BY_METRIC ∪ SMS_MULTI_SYMBOLS_BY_METRIC` wird ausschließlich verwendet, um im
**tatsächlich gesendeten** Kurzform-/SMS-/Premium-Text ein Token einer Metrik zuzuordnen (Parsen).
Die **Erwartung**, ob eine Metrik erscheinen soll, kommt einzig aus der Orakel-Regel oben. Fehlt
einer aktiven Metrik ein Kürzel (B1: `wind_chill`), bleibt die Erwartung „aktiv" — der Test wird an
dieser Zelle rot, bis der begründete Register-Eintrag sie befristet abdeckt.

### Parser-Helfer (neu, kein fertiger Baustein vorhanden)

- Telegram-rich-Tabellenkopf → Liste von Metriken in Spaltenreihenfolge
- E-Mail-Spaltenreihenfolge (html + plain) → Liste von Metriken in Spaltenreihenfolge
- Kurzform-/SMS-/Premium-Text → Token-Reihenfolge (Vorbild `test_sms_user_metric_order.py`)

### Aufzeichner-Ausbau

`tests/tdd/test_kanaltreue_adhoc_antwort.py:139-176` zeichnet nur `subject` auf. Für S1 wird der
Aufzeichner (als geteilter Helfer extrahiert, damit beide Testdateien ihn nutzen) um `body`,
`plain_text_body` und `parse_mode` erweitert — per `monkeypatch.setattr` auf
`EmailOutput`/`SMSOutput`/`PremiumSmsOutput`/`TelegramOutput`, kein `Mock()`/`patch()`/`MagicMock`.
Das ist die einzige Änderung an bestehendem Testcode.

## Expected Behavior

- **Input:** Zwei Golden-Trip-JSONs (Persistenzformat des Editors, siehe oben) + eine synthetische
  Voll-Wetter-Fixture + ein Ausnahme-Register.
- **Output:** Für jede Kombination aus wählbarer Metrik (`selectable=true`) × sechs Kanälen
  (E-Mail html, E-Mail plain, Telegram rich, Telegram Kurzstil, SMS, Premium-SMS) × drei
  Dimensionen (erscheint, Reihenfolge, Roh/Einfach) wird die aus dem jeweiligen Golden abgeleitete
  Erwartung gegen den tatsächlich an die Transport-Klasse übergebenen Text geprüft. Ohne
  Register-Deckung ist jede Abweichung ein roter Testfall.
- **Side effects:** Keine Produktänderung. Neue Testdateien, ein erweiterter Test-Helfer, ein neuer
  Regel-Budget-Eintrag in `docs/reference/gates_und_ratschen.md`.

## Acceptance Criteria

- **AC-1:** Given zwei Golden-Trip-JSONs mit identischem Metrik-Roster und identischen
  `channel_layouts`, die sich nur in den Versand-Schaltern unterscheiden (Golden A: KHW-403-Nachbau
  mit `telegram_style=kurzform`, `send_sms=false`, `send_premium_sms=false`; Golden B: gleiches
  Roster mit `telegram_style=rich`, `send_sms=true`, `send_premium_sms=true`) / When beide über den
  echten `load_trip`-Loader eingelesen werden / Then entstehen Kanal-Layouts und Kaskade exakt wie
  im jeweiligen JSON, ohne synthetische Nachbearbeitung im Testcode.
  - Test: `test_einstellung_gleich_auslieferung.py::test_golden_trips_laden_unveraendert` lädt beide
    Golden-JSONs über `load_trip` und vergleicht die geladenen `channel_layouts` 1:1 mit dem
    jeweiligen JSON-Inhalt (direkter Attributvergleich, keine Produktfunktion als Vergleichsmaßstab).

- **AC-2 (Bug-Nachweis aus Nutzersicht):** Given der Register-Eintrag für die Zelle
  `wind_chill × Telegram-Kurzstil × erscheint` wird entfernt / When der Invarianten-Test auf Golden
  A läuft / Then wird GENAU diese eine Zelle rot — nicht ihre Reihenfolge- oder Roh/Einfach-Zelle
  (die entfallen laut Orakel-Regel bei einer im Text fehlenden Metrik), kein anderer Test, keine
  andere Zelle im selben Testlauf.
  - Test: `test_ac2_fehlender_register_eintrag_wind_chill_telegram_kurzform_wird_rot` entfernt den
    einen Eintrag temporär (lokale Kopie des Registers im Testkörper, keine Dateiänderung), lässt
    die Matrix für Golden A laufen und prüft `rote_zellen == {("wind_chill", "telegram_kurzform", "erscheint")}`
    (Mengengleichheit, nicht nur „enthält").

- **AC-3 (Orakel-Unabhängigkeit):** Given die Orakel-Funktion nimmt ausschließlich das rohe
  `json.load`-Dict des Golden-Trip-JSON entgegen (kein geladenes `Trip`-Objekt, kein Import aus
  `src/app/models.py`) / When Mutation M1 (Sortkey in `_sorted_by_layout` invertiert) eingespielt
  wird / Then bleibt die von der Orakel-Funktion berechnete Erwartung unverändert, während sich der
  TATSÄCHLICHE, vom Produktcode erzeugte Text ändert — die betroffene Reihenfolge-Zelle wird rot.
  - Test: Nachweis über AC-9/M1 (derselbe Testlauf, nicht separat): würde das Orakel heimlich
    `_sorted_by_layout` nutzen, bliebe M1 grün, weil beide Seiten gleich falsch würden. Ergänzend
    Code-Review-Beleg: die Orakel-Funktion hat keinen `import`-Eintrag für `src.app.models`.

- **AC-4 (Kürzel-Register nur zum Parsen):** Given eine im Kanal-Layout aktive Metrik ohne Eintrag
  in `SMS_SYMBOL_BY_METRIC`/`SMS_MULTI_SYMBOLS_BY_METRIC` / When ihre Erwartung gebildet wird /
  Then bleibt die Erwartung „aktiv laut Kanal-Layout" bestehen — eine tatsächliche Abwesenheit im
  gesendeten Text wird nur über einen begründeten Register-Eintrag akzeptiert, niemals dadurch,
  dass der Parser kein Kürzel findet.
  - Test: `test_ac4_fehlendes_kuerzel_aendert_die_erwartung_nicht` prüft am Beispiel `wind_chill`
    (kein Kürzel seit #1887 E6), dass die Orakel-Erwartung unabhängig vom Kürzel-Register „aktiv"
    bleibt und die Abweichung ausschließlich über den Register-Eintrag B1 toleriert wird.

- **AC-5 (strukturelle Ausnahmen nur als Register-Eintrag oder Kernregel):** Given die
  strukturellen Ausnahmen 160er-Budget/`DROP_ORDER`, Telegram-7er-Limit, `VISIBILITY_GATE_IDS` /
  When eine Golden-Variante eine dieser Ausnahmen auslöst (Metrik fällt dem Budget zum Opfer,
  wandert aus der Telegram-Tabelle in die Kurzübersicht, hat keine Stundenspalte) / Then wird die
  betroffene Zelle rot und ist nur über einen Register-Eintrag mit Befund-Referenz (Issue/ADR) und
  Grund tolerierbar — die Orakel-Funktion kennt diese Ausnahmen NICHT und schränkt die Erwartung
  ihretwegen nicht ein. Einzige Kernregeln im Orakel bleiben B6 (globales Maximum) und B4
  (Kurzstil/Premium-Quelle).
  - Test: `test_ac5_strukturelle_ausnahme_verengt_die_erwartung_nicht` prüft für jede im Register
    geführte strukturelle Ausnahme, dass die Orakel-Erwartung die betroffene Metrik weiterhin als
    „erscheint" führt, und dass die zugehörige Zelle ohne den Eintrag rot wird.

- **AC-6 (Rückdreh-Gegenprobe):** Given das Ausnahme-Register wird auf eine leere Liste gesetzt /
  When der Invarianten-Test läuft / Then wird er an GENAU den Zellen rot, die die Register-Einträge
  normalerweise abdecken — nicht mehr (kein unregistrierter Fehler) und nicht weniger (keine
  vakuum-grüne Ratsche); die Menge ist nicht leer.
  - Test: `test_ac6_leeres_register_ist_rot_an_genau_den_registrierten_zellen` ersetzt das Register
    lokal durch `[]`, sammelt die roten Zellen über beide Goldens und vergleicht die Menge exakt
    (`==`, nicht „mindestens") mit der Zellmenge der Register-Einträge.

- **AC-7 (veralteter Eintrag):** Given ein Register-Eintrag, dessen Zelle im tatsächlich
  gesendeten Text mit der Orakel-Erwartung übereinstimmt (Zustand „bereits gefixt") / When der Test
  läuft / Then wird dieser Eintrag als „veralteter Eintrag ohne Wirkung" rot gemeldet, statt
  stillschweigend grün durchgewunken zu werden — die Ratsche zieht nur Richtung Schließung.
  - Test: `test_ac7_veralteter_eintrag_wird_rot` ergänzt lokal (Kopie des Registers im Testkörper)
    einen Eintrag für eine nachweislich grüne Zelle (z. B. eine korrekt erscheinende E-Mail-Metrik)
    und prüft, dass der Lauf genau diesen Eintrag als veraltet meldet. Die Prüfung stützt sich auf
    den echten gesendeten Text, nicht auf eine im Test veränderte Kürzel-Tabelle (die würde nur die
    Erwartungs-/Parserseite verschieben, nicht die Auslieferung).

- **AC-8 (Eintrag ohne Begründung):** Given ein Register-Eintrag ohne `befund`- oder ohne
  `grund`-Feld / When der Test das Register vor der Matrixprüfung validiert / Then schlägt der Test
  fehl, bevor die eigentliche Matrix überhaupt geprüft wird.
  - Test: `test_ac8_eintrag_ohne_begruendung_blockt_vor_der_matrix` fügt lokal einen Eintrag mit
    leerem `grund` hinzu und prüft, dass die Validierung mit einer spezifischen Fehlermeldung
    scheitert, bevor irgendeine Zelle geprüft wurde (Reihenfolge-Nachweis über einen Zähler/Spy, der
    erst nach erfolgreicher Validierung inkrementiert wird).

- **AC-9 (Mutations-Pflichtfänge M1–M4, echte Kern-Prüfung, nicht nur Adversary):** Given je eine
  der vier Mutationen — M1 (Sortkey in `_sorted_by_layout` invertiert), M2
  (`_clip_to_global_maximum`-Äquivalent lässt eine zusätzliche Metrik durch, die laut P2 geclippt
  werden müsste), M3 (`build_friendly_keys` liest die falsche `dc`), M4 (Formatter liest die
  globale `dc.metrics` statt das Kanal-Layout, sichtbar an P3) — einzeln per `monkeypatch` auf die
  echte Produktfunktion mit einer die Verfälschung exakt nachbildenden Ersatzfunktion eingespielt /
  When der Invarianten-Test aus dieser Spec (als aufrufbare Funktion, nicht nur als
  pytest-Sammlung) danach läuft / Then wird ER SELBST rot, an der von der jeweiligen
  Golden-Eigenschaft (P1/P2/P3/P4) betroffenen Zelle — nicht nur irgendein anderer Test in der
  Suite.
  - Test: `test_ac9_mutationen_m1_bis_m4_werden_von_diesem_test_rot_gefangen`, parametrisiert über
    M1–M4; jeder Fall patcht die benannte Produktfunktion für die Dauer des Testfalls und ruft die
    Invarianten-Matrix erneut auf. Die Adversary-Mutations-Gegenprobe in `/50` (PFLICHT laut
    CLAUDE.md) spielt zusätzlich echte String-Ersetzungen mit externer Sicherungskopie im
    Produktcode ein — dieser Kern-Test ist der wiederholbare, automatisierte Nachweis dafür.

- **AC-10 (Register-Startbefüllung):** Given die durch die zwei Golden-Varianten tatsächlich
  ausgelösten Befunde B1, B2, B3, B5 sowie etwaige ausgelöste strukturelle Ausnahmen (AC-5) / When
  Scheibe S1 abgeschlossen wird / Then hat jede daraus resultierende rote Zelle genau einen
  Register-Eintrag mit Befund-Referenz und Grund — und für B4/B6/B7/B8/B9 existiert laut
  Deckungstabelle bewusst KEIN Eintrag.
  - Test: `test_ac10_register_deckt_exakt_die_ausgeloesten_befunde_ab` prüft (a) für B1/B2/B3/B5 je
    mindestens einen Eintrag mit befülltem `befund`/`grund`, (b) dass kein Eintrag mit `befund`
    „B4"/„B6"/„B7"/„B8"/„B9" existiert, (c) dass der volle Testlauf über beide Goldens mit diesem
    Register grün ist.

- **AC-11 (Matrix-Abdeckung):** Given alle wählbaren Metriken (`selectable=true`, `confidence_pct`
  ausgeschlossen per Issue #710) und die sechs Kanäle E-Mail html, E-Mail plain, Telegram rich,
  Telegram Kurzstil, SMS, Premium-SMS / When der Invarianten-Test über BEIDE Goldens läuft / Then
  hat jede Kombination aus Metrik × Kanal × Dimension (erscheint, Reihenfolge, Roh/Einfach), die in
  mindestens einem der beiden Goldens erreichbar ist, ein Ergebnis (grün, rot oder
  Register-gedeckt) — keine erreichbare Kombination wird stillschweigend ausgelassen.
  - Test: `test_ac11_matrix_ist_vollstaendig` iteriert den Metrik-Katalog gefiltert auf
    `selectable=true`, kreuzt mit den sechs Kanälen und den drei Dimensionen, und prüft für jede in
    einem der beiden Goldens erreichbare Zelle ein vorhandenes Ergebnis.

- **AC-12 (synthetische Voll-Wetter-Fixture):** Given die bestehenden `openmeteo`-Fixtures haben
  Lücken (humidity, dewpoint, pressure, wind_chill_c, cloud_mid/high, precip_type, snow_new_24h) /
  When beide Goldens mit der neuen synthetischen Voll-Wetter-Fixture gerendert werden / Then
  entstehen keine roten Zellen wegen fehlender Rohdaten — jede verbleibende rote Zelle geht auf
  Konfig-Logik zurück, nicht auf eine Datenlücke.
  - Test: `test_ac12_keine_rote_zelle_durch_fehlende_rohdaten` rendert alle sechs Kanäle mit der
    neuen Fixture und prüft, dass kein Ausgabetext einen Platzhalter für fehlende Rohdaten enthält
    (z. B. `None`/leer an einer Stelle, an der eine aktive Metrik einen Wert erwarten lässt).

- **AC-13 (Naht nur am Transport):** Given `EmailOutput`/`SMSOutput`/`PremiumSmsOutput`/
  `TelegramOutput` werden per `monkeypatch.setattr` durch einen Aufzeichner ersetzt (Vorlage
  `test_kanaltreue_adhoc_antwort.py`, erweitert um `body`/`plain_text_body`/`parse_mode`) / When
  beide Goldens versendet werden / Then laufen Loader, Kaskade und Formatter unverändert echt — der
  Aufzeichner erfasst den vollständigen, durch echte Formatierung erzeugten Text je Kanal (kein
  `Mock()`/`patch()`/`MagicMock`, kein vom Test vorgegebener Platzhalter-Text).
  - Test: `test_ac13_naht_liegt_nur_am_transport` prüft, dass der aufgezeichnete Text für jeden
    Kanal die golden-spezifischen Werte (z. B. konkrete Wetterwerte aus der Voll-Wetter-Fixture,
    nicht nur Metrik-Labels) enthält — ein vom Test selbst vorgegebener Text käme ohne echten
    Formatter-Lauf nicht zustande.

- **AC-14 (Regel-Budget-Eintrag):** Given der neue Invarianten-Test führt ein neues Pflicht-Gate
  (das Ausnahme-Register) ein / When Scheibe S1 abgeschlossen wird / Then trägt
  `docs/reference/gates_und_ratschen.md` in der Tabelle „Regel-Budget: Prüfdaten im Überblick"
  eine neue Zeile mit Prüfdatum 2026-12-25 und einem Fang-Beleg-Platzhalter für diese Ratsche.
  - Test: `tests/test_regel_budget_pruefdatum_einstellung_auslieferung.py` (`# doc-compliance-test` — zulässige
    Ausnahme vom Dateiinhalt-Verbot, da hier die Dokumentationspflicht selbst der Prüfgegenstand
    ist, kein Verhaltensnachweis über Code) prüft, dass die Tabelle eine Zeile mit „2026-12-25" für
    diese Ratsche enthält.

## Known Limitations

- S1 ändert **kein** Produktverhalten. B1, B2, B3, B5 bleiben zunächst bestehen, nur sichtbar und
  befristet im Register dokumentiert — die Fixes sind eigene Scheiben (S6+, siehe „Außerhalb des
  Umfangs").
- B4, B6, B7, B8, B9 bekommen in S1 bewusst KEINEN Register-Eintrag: B6/B4 sind Kernregeln der
  Orakel-Funktion selbst (kein Ausnahmefall), B7/B8/B9 werden von den beiden S1-Goldens schlicht
  nicht ausgelöst (andere Matrix-Dimension bzw. andere Kaskadenquelle) — sie bleiben in der
  Deckungstabelle als offen vermerkt, ohne dass S1 dafür einen Platzhalter-Eintrag erzwingen muss.
- B3 bekommt zusätzlich zum befristeten Register-Eintrag ein eigenes GitHub-Issue (nutzersichtbar,
  eigenständig) — der Fix selbst ist nicht Teil von S1.
- B1-Variantenwahl (V1 Kürzel vs. V2 Editor-Hinweis) wird in dieser Spec **nicht** entschieden —
  das ist ausdrücklich Aufgabe der späteren Fix-Scheibe (S6+).
- L1–L4 (Alarm-Familie, Kanal an/aus, `email_format`/`sms_threshold`, Ortsvergleich) sind
  strukturell außerhalb der S1-Matrix (andere Kette, andere Einstiege) — eigene Scheiben S3–S5,
  keine Register-Einträge in S1 nötig.
- Kein Staging nötig: Loader/Kaskade/Formatter sind lokal reproduzierbar, Staging-Daten sind für
  `hem` ohnehin nicht lesbar (Memory: `reference_staging_hat_keinen_dateizugriff_fuer_hem`).
- KHW 403 (Trip `5f534011`) wird nirgends angefasst — Golden A ist eine strukturelle Nachbildung
  mit synthetischen Kennungen, kein Zugriff auf den Prod-Trip.
- Parallelsitzung #2417 ändert uncommittet `notification_service.py`/`trip_report_scheduler.py`
  (Stand 2026-09-26, noch nicht in `origin/main`). Die Naht per `monkeypatch` der
  Output-Klassen hält die Konfliktfläche klein; vor `/50` per `ListAgents`/`SendMessage`
  abstimmen.
- `test_channel_metric_matrix.py` wird durch S1 **nicht** ersetzt — es bewacht andere
  Zwischenschichten (`resolve_metric_col_order`, `get_metrics_for_channel`) und bleibt bestehen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0050 (keine Änderung, nur Anwendung als Prüf-Invariante)
- **Rationale:** ADR-0050 legt die Metrik-Kaskade als Verfeinerung fest, inklusive des globalen
  Maximums aus `display_config.metrics` als oberer Schranke jedes Kanal-Layouts (B6) und der
  Kurzstil/Premium-Quellzuordnung auf `channel_layouts.sms` (B4). Diese Spec trifft keine neue
  Architekturentscheidung — sie schreibt die bestehenden Kaskadenregeln als Orakel-Kernregeln eines
  Tests fest und macht ihre bislang unbewachten punktuellen Abweichungen (B1/B2/B3/B5) sichtbar.
  Kein neues ADR nötig, da weder Datenmodell noch Kaskadenlogik verändert werden.

## Changelog

- 2026-09-26: Initial spec created
- 2026-09-26: Nach Advisor-Review überarbeitet — zwei Golden-Varianten statt einer (sechs Kanäle
  aus einer Konfiguration nicht erreichbar), Golden-Pflichteigenschaften P1–P8 für die
  Mutations-Pflichtfänge ergänzt, B4/B6-Quellregeln in die Orakel-Regel statt ins Register verlegt,
  AC-2/AC-6/AC-7/AC-10 auf Konsistenz mit der tatsächlich auslösbaren Befundmenge (B1/B2/B3/B5)
  korrigiert, AST-/`inspect.getsource`-Testmuster aus AC-3/AC-5/AC-13 entfernt (Kontextdokument
  nennt dieses Muster selbst als Sammel-Eintrag #1196, kein neues Gate), AC-9 zu einem echten
  parametrisierten Kern-Test statt reinem Adversary-Schritt gemacht.
- 2026-09-26: Orchestrator-Gegenlesung — Widerspruch AC-5 ↔ AC-6/AC-10 aufgelöst (strukturelle
  Ausnahmen sind rote Zellen mit Register-Eintrag, keine feste Vierer-Zahl), AC-7 auf echten
  Sendetext statt veränderter Kürzel-Tabelle umgestellt, AC-14-Testdatei nach Verhalten benannt.
