# Context: fix-1252-1253-kanal-text-v2

## Request Summary

Zwei nutzersichtbare Fehler auf den Kanälen, die im Gelände zählen:
- **#1252 (Telegram):** Amtliche Warnungen zeigen die Formatierungs-Auszeichnungen roh im Text (`<b>…</b>` steht wörtlich in der Nachricht).
- **#1253 (SMS + E-Mail-Klartext):** Ortsnamen mit Akzenten/Umlauten werden verstümmelt (`Hyères` → `Hyres`, `München` → `Mnchen`) — Zeichen werden **gelöscht** statt gefaltet.

## Existing Specs & ADRs (der entscheidende Fund)

| Dokument | Aussage — und was daraus folgt |
|---|---|
| **`docs/adr/0012-telegram-parse-mode-html.md`** (Status: **Akzeptiert**) | **Punkt 1:** `parse_mode="HTML"` ist der Standard für formatierte Telegram-Nachrichten; Renderer erzeugen `<b>`-Tags, **Nutzdaten laufen durch `_esc()`** (`&`, `<`, `>`) — „eine einzige Escaping-Stelle für beide Kanäle". **Punkt 2:** `TelegramOutput.send()` bleibt **rückwärtskompatibel** — `parse_mode=None` als Default reproduziert das Alt-Verhalten bit-identisch; „Bestands-Caller bleiben unberührt, **bis sie explizit umgestellt werden**". |
| `docs/specs/modules/telegram_output.md` | Vertrag des Kanals. **Veraltet** (nennt `src/outputs/telegram.py`, heute `src/output/channels/telegram.py`) → Doku-Drift, Sammel-Eintrag #1198. |
| `docs/reference/sms_format.md:27,66` | Verbindliche Faltungs-Konvention: `ä→ae, ö→oe, ü→ue, ß→ss`, und zwar **zuerst falten, dann kürzen**. |
| `docs/adr/0014-telegram-multi-bubble-format.md` | Bubble-Format, hier nicht berührt. |

**Konsequenz für den Lösungszuschnitt:** Der Default von `send()` darf **NICHT** auf HTML gekippt werden — das würde ADR-0012 Punkt 2 brechen. Stattdessen: die **zwei vergessenen Aufrufer explizit umstellen**. Damit bleibt auch `tests/tdd/test_952_onset_alert_fidelity.py:627` (assertet, dass der Altpfad kein `parse_mode` hat) **zu Recht grün** — dieser Test schützt eine bewusste Entscheidung, er ist kein Hindernis.

Der Defekt ist also **keine fehlende Entscheidung, sondern eine nicht nachgezogene**: ADR-0012 schreibt Escaping + HTML für die kanonischen Alert-Pfade bereits vor; für die Official-Alert-Pfade wurde es nie umgesetzt.

## Root Cause #1252 — Telegram

**Die Escaping-Lücke (Voraussetzung für alles Weitere):**
`src/output/renderers/alert/official_alerts.py:1361-1369` — nur die **Kopfzeile** ist escaped (`:1361`, `_html.escape(head)`). Nicht escaped sind:
- `:1362-1367` — `_display_label(n.alert)` (Behörden-Feed-Daten), `scope_label` (Ortsnamen), `_format_validity(...)`
- `:1368` — `source_label` (Behörden-Label)

Dass diese Felder untrusted sind, belegt der **E-Mail-Zweig derselben Datei**, der sie sehr wohl escaped: `:191`, `:194`, `:848`, `:1095`.

**Die fehlende Umstellung:**
`src/services/notification_service.py:538` (Standalone-Alert) und `:658` (Compare-Alert) senden ohne `parse_mode`. Die anderen Pfade setzen `"HTML"` längst: `:273` (Briefing-Bubbles), `:789` (Deviation + Radar-Onset).

**Die Gefahr:** `parse_mode` naiv setzen, ohne Escaping → ein `&` oder `<` im Ortsnamen → Bot-API 400 → `OutputError` (`src/output/channels/telegram.py:181-187`) → **kein Fallback, die Warnung ist verloren**. Ein stiller Totalausfall wäre schlimmer als der heutige kosmetische Defekt. Escaping MUSS zuerst kommen.

## Root Cause #1253 — SMS und E-Mail-Klartext

`src/output/renderers/alert/render.py:521-525` (`_ascii`): ersetzt nur typografische Symbole (`–`, `°`, `↑`), dann `.encode("ascii", "ignore")` → **keine Buchstaben-Faltung**, Rest wird ersatzlos gelöscht.

**Drei getrennte Implementierungen derselben Sache — deshalb wurde eine vergessen:**

| Ort | Umlaute | Akzente | Nutzung |
|---|---|---|---|
| `src/output/renderers/alert/render.py:521` (`_ascii`) | **NEIN** | **NEIN** | SMS (Alerts) — DER BUG |
| `src/output/renderers/email/compact.py:35-43` (`_ASCII_MAP`) | ja | **NEIN** | E-Mail-Klartext — `Hyères` → `Hyres` **auch hier** |
| `src/output/tokens/builder.py:20-23` (`_UMLAUT`) | ja | **NEIN** | Token-Bau (faltet korrekt VOR dem Kürzen — Vorbild) |

`src/output/renderers/sms_trip.py:38` (`_sms_stage_prefix`) faltet **gar nicht** (`[:10]` roh).

## Reihenfolge-Falle (Längen-Budget)

`sms_format.md:66` schreibt „zuerst falten" vor. Der `trip_short`-Pfad verletzt das:
`src/services/notification_service.py:703`, `src/services/radar_alert_service.py:71`, `src/services/validator_render_service.py:108` schneiden `trip.name[:16]` **roh** (ungefaltet) → danach faltet `render.py:257`/`:496` und kürzt **erneut** `[:16]`. Da `ü→ue` wächst, frisst die Doppelkürzung Buchstaben. Zweite Stelle: `render.py:498` (`[:24]` auf `location_label`).

**Bereits korrekt:** `official_alerts.py:1575-1577` faltet vor dem Packen (mit explizitem Kommentar) — dort degradiert eine längere Faltung sauber.

## Dependencies

- **Upstream:** Behörden-Feeds (Vigilance/MeteoAlarm) liefern `alert.label`, `scope_label`, `source_label` — **untrusted Text**, kann beliebige Sonderzeichen tragen.
- **Downstream:** Telegram Bot API (400 bei kaputtem HTML), seven.io (SMS, GSM-7/160 Zeichen), E-Mail-Klartext.

## Bestehende Tests

- **Kein einziger Test** prüft `parse_mode` oder Escaping für die Official-Alert-Telegram-Pfade (`:538`, `:658`) — genau deshalb der Bug.
- `tests/tdd/test_952_onset_alert_fidelity.py:616-627` — prüft `parse_mode == "HTML"` für den Onset-Pfad **und** dass der Altpfad kein `parse_mode` hat. **Bleibt zu Recht grün** (ADR-0012 Punkt 2), muss NICHT angefasst werden.
- SMS-Golden-Tests werden **nicht** rot: Fixtures nutzen bereits vorgefaltete Namen (`test_official_alert_channel_scope.py:46` — `"hyeres": "Hyeres"`). Kein Test füttert je `Hyères`/`München` ein — **das ist die Lücke, die den Bug durchgelassen hat**.
- Guard-Tests, die grün bleiben müssen: `tests/tdd/test_official_alert_template_render.py:204` (`sms.isascii()`), `tests/tdd/test_sms_preview_matches_sent.py:96` (Vorschau == Versand).

## Risks & Considerations

- **Höchstes Risiko: stiller Totalausfall einer Warnung.** Escaping zuerst; zusätzlich braucht `send()` einen Fallback (bei 400 einmal ohne `parse_mode` + gestrippte Tags nachsenden). Eine Warnung darf nie an einem Sonderzeichen scheitern. Das ist eine **additive Härtung**, kein ADR-Konflikt (ADR-0012 nennt Härtungen selbst als offen).
- **`_ascii` ist NICHT identitäts-/schlüsselbildend** — Dedup läuft über `dedup_id` (`official_alerts.py:282-283`), der SMS-Shortcode über einen unabhängigen ASCII-Filter (`:452`). Keine Bestandsdaten-Gefahr durch die geänderte Faltung. Explizit geprüft.
- **Drei Faltungs-Implementierungen konsolidieren** (Projektregel: eine Quelle, Rest Thin-Wrapper) — sonst wird beim nächsten Mal wieder eine vergessen.
- Plaintext-Telegram-Caller (`notification_service.py:333`, `:840`, `:859`, `channel_test_service.py:40`) bleiben bei `parse_mode=None` — sie sind von der expliziten Umstellung nicht betroffen (ADR-0012 Punkt 2). Kein Handlungsbedarf, aber in der Spec zu benennen.
- `TelegramOutput.edit_message_text` (`telegram.py:235`) kennt keinen `parse_mode` → per Callback editierte Briefings können rohe Tags zeigen. Prüfen, ob im Scope oder Sammel-Eintrag.

---

## Analysis

### Type
**Bugfix** (zwei gebündelte Bugs, gemeinsame Klasse: Kanal-Textaufbereitung)

### Blinde Flecken aus der Nutzersicht-Analyse (bug-intake)

1. **Die Frontend-Vorschau zeigt denselben Fehler.** SMS-, Telegram- und Alert-Vorschau laufen durch dieselben Renderer (`api/routers/preview.py:54-122`, `api/routers/validator.py:224-245`, `src/services/validator_render_service.py:136-137`). Der Nutzer sieht `Hyres` und die rohen Auszeichnungen bereits im Editor. **Gute Nachricht:** `tests/tdd/test_sms_preview_matches_sent.py` garantiert Vorschau == Versand — der Renderer-Fix wandert automatisch in die Vorschau.
2. **Die Testdaten kodieren den Bug als Sollzustand.** `tests/tdd/test_official_alert_warn_section.py:59` nutzt `sms_scope="nurHyeres"` — der verstümmelte Name als **Konstante**. Wer den Fehler repariert, dem sieht es aus wie eine Regression. Genau so überlebt ein Bug jahrelang. Diese Fixtures müssen auf echte Eingaben (`Hyères`) umgestellt werden, sonst beweist der Test nichts.
3. **Betroffenheit ist nicht theoretisch:** Kernzielgebiete heißen `Hyères`, `Fréjus`, `Collobrières` (GR20/Korsika/Frankreich). Der Fehler trifft dort praktisch jede Warnung — seit #1249 trägt **jedes** SMS-Token einen Ortsnamen.
4. **Stiller Totalausfall bestätigt:** `telegram.py:181-187` wirft `OutputError`, `notification_service.py:542` fängt und loggt nur. Der Nutzer merkt **nichts** — die Warnung ist weg.

### Technical Approach (aus der strategischen Bewertung)

**Faltung — die Reihenfolge ist die Pointe, nicht die Deduplizierung:**
Neues Leaf-Modul `src/utils/ascii_fold.py` mit `fold_ascii(text)`. **Umlaut-Digraph-Map ZUERST** (`ä→ae`, `ü→ue`, `ß→ss`), **dann** NFKD-Normalisierung + Combining-Marks entfernen (`é→e`). Umgekehrt würde NFKD `ü` zu `u` zerlegen statt zu `ue` — das verletzt `sms_format.md:27`.
Die typografischen Symbole (`–`, `°`, `↑`, `·`, `⚡`) sind Präsentationsdetail je Kanal und bleiben als lokale Thin-Wrapper **vor** dem `fold_ascii()`-Aufruf.
Importrichtung geprüft: `src/utils/*` ist reiner Leaf (importiert nichts aus `src/output/*`), `from utils.geo import ...` ist bereits Konvention (`email/helpers.py:29`). **Kein Zirkelimport.**

**`trip_short`:** Nachweislich **nicht** identitätsbildend — nur Anzeigetext (`render.py:115,119,249,257,271,278,287,462,468,469,496`), kein Dedup-/Vergleichs-/Persistenzschlüssel. Die rohe `[:16]`-Vorkürzung an drei Konstruktionsstellen kann ersatzlos entfallen; `AlertMessage.trip_short` (`model.py:51`) trägt keinen Längenvertrag. Nebenwirkung: Titelzeilen zeigen künftig den vollen statt eines willkürlich mitten im Wort gekappten Namens — Verbesserung, keine Regression.

**400-Fallback:** Additive Härtung, **kein ADR-Konflikt** — greift ausschließlich bei `parse_mode is not None AND status == 400`, der Altpfad (`parse_mode=None`) wird nicht berührt. `test_952_onset_alert_fidelity.py:616-627` bleibt grün (setzt nie `parse_mode`, erreicht den Zweig nie). Beim Nachsenden Tags strippen **und** `html.unescape()` — sonst zeigt der Fallback `&amp;` statt `&`, also ein kosmetischer Fehler gegen einen anderen getauscht.

### Reihenfolge-Zwang (damit nie ein Zustand ohne Netz entsteht)

Zwei unabhängige Spuren; innerhalb der Telegram-Spur ist die Reihenfolge **bindend**:
1. **Escaping** (`official_alerts.py:1361-1369`) — Voraussetzung
2. **400-Fallback** (`telegram.py::send()`) — muss live sein, **bevor** die Formatierung scharf geschaltet wird. Sonst existiert ein Zeitfenster, in dem ein übersehenes Sonderzeichen eine Warnung verschluckt.
3. **`parse_mode="HTML"`** (`notification_service.py:538`, `:658`) — zuletzt

### Affected Files

| File | Change | Beschreibung |
|------|--------|--------------|
| `src/utils/ascii_fold.py` | CREATE | `fold_ascii()` — die eine Quelle (~25 LoC) |
| `src/output/renderers/alert/render.py` | MODIFY | `_ascii` → Symbol-Wrapper + `fold_ascii` |
| `src/output/renderers/email/compact.py` | MODIFY | `_ASCII_MAP` Umlaut-Einträge raus, an `fold_ascii` delegieren |
| `src/output/tokens/builder.py` | MODIFY | `_UMLAUT` raus → `fold_ascii` |
| `src/output/renderers/sms_trip.py` | MODIFY | `_sms_stage_prefix`: erst falten, dann `[:10]` |
| `src/output/renderers/alert/official_alerts.py` | MODIFY | Escaping :1361-1369 (`_display_label`, `scope_label`, `_format_validity`, `source_label`) |
| `src/output/channels/telegram.py` | MODIFY | 400-Fallback in `send()` (additiv) |
| `src/services/notification_service.py` | MODIFY | `parse_mode="HTML"` :538, :658; Roh-Kürzung :703 raus |
| `src/services/radar_alert_service.py` | MODIFY | Roh-Kürzung :71 raus |
| `src/services/validator_render_service.py` | MODIFY | Roh-Kürzung :108 raus |

### Scope Assessment
- Files: 10 (1 neu, 9 geändert) + Testdateien
- Estimated LoC: **+85/-25** Produktionscode — klar im 250er-Budget
- Risk Level: **MEDIUM** (Blast Radius hoch, aber Reihenfolge entschärft ihn)

### Baseline-Testlage (verifiziert, vor der Änderung)
`uv run pytest -k "sms or telegram or ascii or fold or official_alert"` → ~28 Tests **heute schon rot**, alle nachweislich unabhängig (fehlende Svelte-Datei, Textmuster-Drift aus #722, Live-Telegram-Netzwerktests). **Kein einziger SMS-/Official-Alert-Golden-Test ist rot, und keiner kippt durch die Faltungsänderung** — die Fixtures nutzen bereits vorgefaltete Namen. Genau das ist die Lücke.

### Open Questions
Keine. Alle Entscheidungen sind durch ADR-0012 (bindend) und `sms_format.md:27,66` bereits getroffen.
Beobachtung ohne Entscheidungsbedarf: `TelegramOutput.edit_message_text` (`telegram.py:235`) kennt weiterhin kein `parse_mode` → bleibt außerhalb des Scopes, Sammel-Eintrag #1199.
