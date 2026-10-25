---
entity_id: fix_2615_befehle_pausierte_vergleiche
type: module
created: 2026-10-25
updated: 2026-10-25
status: draft
version: "1.0"
tags: [ortsvergleich, inbound, trip-selection, premium-sms, telegram, bug, issue-2615]
---

# Wetterbefehle und pausierte Ortsvergleiche (Bug #2615)

## Approval

- [ ] Approved

## Purpose

Auf Produktion antworten `heute`/`morgen`/`report` mit „Mehrdeutig“, obwohl genau EIN
Ortsvergleich aktiv ist und alle anderen pausiert sind, weil die geteilte Zielauflösung
Pausierte als adressierbar mitzählt (bewusst, #2282 — nötig nur für `pause`/`weiter`).
Zusätzlich ist die auf 4 Zeichen gekürzte Premium-SMS-Rückfrage bei gleichem Namensanfang
(„Zill“/„Zill“) nicht unterscheidbar, und eine gekürzte Antwort („Muen pause“) wird vom
Antwort-Parser gar nicht gefunden (Vergleich nur exakt bzw. GSM-7-gefaltet exakt, kein
Präfix) — die Rückfrage ist dann auch bei eindeutigen Namen nicht beantwortbar.

## Source

- **File:** `src/services/trip_selection.py` — `resolve_active_target` (`:205`, Filter
  `vergleiche = [...]` `:223`), `resolve_command_target` (`:267`, Weiche `:291`),
  `_rueckfrage_text` (`:172`, Kürz-Schleife `:185-189`), `_rueckfrage_mit_laenge` (`:192`),
  `_vergleich_ist_aktiv` (`:123`, unverändert).
- **File:** `src/services/trip_command_processor.py` — `match_leading_name` (`:97`,
  gefalteter Zweig `:137-144`), `_find_compare_preset` (`:1325`, gefalteter Zweig
  `:1335-1340`), `_rest_ist_gueltiger_befehl` (`:78`, unverändert), Namensgleichheit
  Trip/Vergleich `:1354` (unverändert).
- **SSOT „pausiert“:** `src/services/compare_alert_guard.py::is_silenced` (`:48`) —
  wird genutzt, nicht neu erfunden.
- **Aufrufer (unverändert, Beleg):** `inbound_telegram_reader.py:281` (Text →
  `resolve_command_target`) und `:507` (Knopf `act_pause` → `resolve_active_target`
  direkt); `inbound_sms_reader.py:380` (`resolve_command_target`).
- **Schicht:** Python-Core (`src/services/`). Kein Frontend, keine Go-API, keine
  schema-relevante Datei (`models.py`, `trip.py`, `loader.py`, `internal/*`) — keine
  Migration, kein Pre-Snapshot.

**E-Mail-Pfad (belegt, nicht betroffen):** `inbound_email_reader.py` nutzt weder
`resolve_command_target` noch `resolve_active_target`; der Betreff-Name ist dort Pflicht
(`_find_trip_id` `:401`). Die Mehrdeutigkeits-Rückfrage ohne Namen gibt es für E-Mail
nicht. Von Befund 2 ist E-Mail nur über den gemeinsamen Processor berührt
(`_find_compare_preset`/`match_leading_name`): ein Betreff mit gekürztem Namen löst künftig
über denselben eindeutigen-Präfix-Fallback auf (kein Verhaltensverlust für exakte Namen).

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Kein neuer Baustein, kein Frontend; die Änderung liegt
>   in der bereits geteilten Auflösung (`trip_selection`) — kein Pendant nötig.
> - **Mandantentrennung:** Auflösung erhält `trips`/`presets` bereits je Nutzer geladen vom
>   Reader; keine neue Persistenz, kein `"default"`-Fallback. Test mit zwei Nutzern (AC-9).
> - **Kanäle:** Telegram, Premium-SMS (Text-Befehle) betroffen; Knopf `act_pause`
>   bewusst unverändert; E-Mail über den Processor-Präfix-Fallback; SMS (nicht Premium) hat
>   keine Rückfrage-Auflösung — nicht betroffen. Inhalt gleich, Form kanalgerecht.

## Estimated Scope

- **LoC:** ca. +70/−10 (Produktivcode) plus Tests
- **Files:** 2 Produktiv-Dateien, 1–2 Testdateien (nach Verhalten benannt, z. B. Ergänzung
  in `tests/tdd/test_eingangsauswahl_trip_und_vergleich.py` und/oder neue
  `tests/tdd/test_befehle_pausierte_vergleiche.py`)
- **Effort:** medium (Risiko mittel: zentrale Auflösung für mehrere Kanäle)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `compare_alert_guard.is_silenced` | Funktion | SSOT „pausiert/archiviert/abgelaufen“ |
| `fold_ascii` / `_gsm7_sicher` | Funktion | GSM-7-Faltung der Rückfrage-Namen |
| `_norm`, `_norm_gefaltet`, `_rest_ist_gueltiger_befehl` | Funktion | Namensvergleich im Antwort-Parser |
| `inbound_telegram_reader`, `inbound_sms_reader` | Aufrufer | unverändert |

## Implementation Details

**Teil 1 — Pausierte bei `heute`/`morgen`/`report` ausblenden**

```
resolve_active_target(trips, presets, now_utc, *, channel, englisch=False,
                      pausierte_ausblenden=False)        # Default = bisheriges Verhalten
  vergleiche = [p for p in presets if _vergleich_ist_aktiv(p, heute)]   # wie bisher
  if pausierte_ausblenden:
      aktive = [p for p in vergleiche if not is_silenced(p)]
      if aktive:            # nur wenn mindestens ein aktiver übrig bleibt
          vergleiche = aktive
      # sonst: Rückfall auf die ungefilterte Liste (bisheriges Verhalten)

resolve_command_target(key, ...):
  if key in _BEIDE_KINDS_ONLY_SCHLUESSEL:
      pausierte_ausblenden = key in {"report", "heute", "morgen"}   # NICHT pause/weiter
```

Der Filter wirkt vor der Entscheidungstabelle (Trip/Vergleich-Zählung), damit
„Trip + pausierte“ ⇒ Trip und „0 Trips + 1 aktiv + n pausiert“ ⇒ eindeutig der aktive.

**Teil 2 — Rückfrage-Namen paarweise eindeutig (Premium-SMS)**

`_rueckfrage_text` (nur `channel == "premium_sms"`): Namen zuerst GSM-7-falten, dann die
Kürzlänge wählen. Die Schleife `:185-189` geht heute von der längsten Länge abwärts bis
Boden 4 und nimmt die erste Länge, die in 160 Zeichen passt. Neu: eine Länge ist nur
zulässig, wenn die gekürzten, gefalteten Namen **paarweise verschieden** sind (verglichen
nach `_norm_gefaltet`); die Schleife wählt die kürzeste Länge ≥ 4, die sowohl ≤ 160 Zeichen
als auch eindeutig ist, andernfalls die längste eindeutige; ist auch voll ausgeschrieben
nichts eindeutig (identische Namen), bleibt die bisherige Kürzung (Randfall, siehe unten).
Telegram bleibt unverändert (volle Namen).

**Teil 3 — Antwort-Parser löst gekürzte Namen auf**

`match_leading_name` und `_find_compare_preset`: als LETZTER Fallback nach exakt und
gefaltet-exakt ein **eindeutiges Präfix** (gefalteter Eingabename mit ≥ 4 Zeichen ist
Präfix genau eines Kandidaten-Namens; in `match_leading_name` zusätzlich nur wenn
`_rest_ist_gueltiger_befehl(rest)`). Mehrfachtreffer ⇒ wie bisher mehrdeutig (`kind=None`
bzw. `None`), nie der erste. Ein exakter oder gefalteter Treffer gewinnt immer vor dem
Präfix.

## Expected Behavior

- **Input:** Befehl `heute`/`morgen`/`report`/`pause`/`weiter` ohne Namen (Telegram-Text,
  Premium-SMS); Antwort auf eine Rückfrage mit gekürztem Namen.
- **Output:** eindeutiges Ziel bzw. Rückfrage; gekürzte Rückfrage-Namen unterscheidbar und
  beantwortbar.
- **Side effects:** keine; reine Auflösungslogik.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer ohne Trip hat einen aktiven und fünf pausierte Ortsvergleiche
  / When er per Telegram oder Premium-SMS `heute`, `morgen` oder `report` ohne Namen
  sendet / Then wird der aktive Ortsvergleich eindeutig angesprochen und es erscheint keine
  „Mehrdeutig“-Rückfrage.
  - Test: Kern-Schicht, `resolve_command_target` je Schlüssel `heute`/`morgen`/`report`
    mit 0 Trips, 1 aktiv + 5 pausiert; erwartet `kind="vergleich"`, Ziel = der aktive
    (rot vor Fix).

- **AC-2:** Given derselbe Bestand (ein aktiver, fünf pausierte Ortsvergleiche, kein Trip)
  / When der Nutzer `pause` oder `weiter` ohne Namen sendet / Then bleibt es mehrdeutig
  und die Rückfrage nennt alle sechs Ortsvergleiche, damit auch pausierte Vergleiche
  fortgesetzt werden können.
  - Test: Kern-Schicht, `pause`/`weiter` → `text` enthält alle sechs Namen, `kind is None`.

- **AC-3:** Given ein Nutzer hat einen aktiven Trip und mehrere pausierte Ortsvergleiche
  (keinen aktiven) / When er `heute`, `morgen` oder `report` ohne Namen sendet / Then wird
  der Trip eindeutig angesprochen; sind dagegen Trip UND ein aktiver Ortsvergleich
  vorhanden, fragt das System wie bisher nach.
  - Test: Kern-Schicht, zwei Konstellationen (Trip + 3 pausiert ⇒ `kind="route"`;
    Trip + 1 aktiv ⇒ Rückfrage).

- **AC-4:** Given ein Nutzer hat nur pausierte Ortsvergleiche und keinen Trip / When er
  `heute` sendet / Then gilt das bisherige Verhalten: bei genau einem pausierten
  Ortsvergleich wird dieser eindeutig angesprochen, bei mehreren pausierten fragt das
  System nach.
  - Test: Kern-Schicht, 1 pausiert ⇒ eindeutig (bestehende Erwartung „AC-2 aus #2282“
    bleibt grün); 3 pausiert ⇒ Rückfrage mit allen drei Namen.

- **AC-5:** Given ein Ortsvergleich ist pausiert (`paused_at` gesetzt oder
  `schedule == "manual"`) / When die Auflösung entscheidet, ob er als pausiert gilt / Then
  folgt das der bestehenden Definition von `compare_alert_guard.is_silenced`
  (keine zweite Pausen-Definition); archivierte und abgelaufene Ortsvergleiche bleiben wie
  bisher gar nicht adressierbar.
  - Test: Kern-Schicht, beide Pausen-Varianten (`paused_at`, `schedule="manual"`) werden
    bei `heute` ausgeblendet; ein archivierter bleibt unsichtbar.

- **AC-6:** Given der Telegram-Knopf „Pause“ (`act_pause`) und die Namensgleichheit von
  Trip und Ortsvergleich (`trip_command_processor.py:1354`) / When sie die Auflösung
  nutzen / Then verhalten sie sich unverändert (Pausierte zählen mit, Rückfrage bei
  Namensgleichheit).
  - Test: Kern-Schicht, direkter Aufruf `resolve_active_target(...)` ohne den neuen
    Parameter liefert bei 1 aktiv + 5 pausiert weiterhin die Rückfrage.

- **AC-7:** Given eine Premium-SMS-Rückfrage mit mehreren Kandidaten, deren Namen gleich
  beginnen (z. B. „Zillertal Nord“, „Zillertal Süd“, „Zillergrund“) / When die Rückfrage
  erzeugt wird / Then sind die angezeigten, gekürzten Namen paarweise verschieden (auch
  nach GSM-7-Faltung, z. B. „Süd“ → „Sud“), jeder mindestens 4 Zeichen lang, und der Text
  ist höchstens 160 Zeichen lang, sofern das mit eindeutigen Namen möglich ist.
  - Test: Kern-Schicht, `_rueckfrage_text(..., channel="premium_sms")` mit Namen gleicher
    4-Zeichen-Anfänge und Umlauten; Namen im Text paarweise verschieden, `len <= 160`.

- **AC-8:** Given eine Premium-SMS-Rückfrage mit gekürzten Namen wurde gesendet / When der
  Nutzer mit dem gekürzten Namen und einem gültigen Befehl antwortet (z. B. „Muen pause“
  für „München Nord“) / Then wird der richtige Ortsvergleich angesprochen (Roundtrip
  Rückfrage → Antwort); trifft der gekürzte Name mehrere Kandidaten, bleibt es mehrdeutig
  und es wird NIE einer davon stillschweigend gewählt; ein exakter oder gefalteter Name
  schlägt immer ein Präfix; ein Präfix unter 4 Zeichen löst nichts auf.
  - Test: Kern-Schicht, `match_leading_name` und `_find_compare_preset`: eindeutiges
    Präfix ⇒ Treffer, zwei Treffer ⇒ `kind is None` bzw. `None`, 3-Zeichen-Präfix ⇒
    `None`, Roundtrip aus `_rueckfrage_text` → Antwort → richtiges Ziel.

- **AC-9:** Given zwei verschiedene Nutzer, A mit lauter pausierten Ortsvergleichen und B
  mit einem aktiven plus pausierten / When beide `heute` senden / Then bekommt jeder nur
  sein eigenes Ergebnis (A: Rückfall nach AC-4, B: eindeutig nach AC-1); die Pausen des
  einen beeinflussen den anderen nicht.
  - Test: Kern-Schicht mit zwei `user_id` und getrennten Preset-Listen.

## Randfälle

| Fall | Festlegung |
|---|---|
| Nur pausierte, genau 1 | eindeutig (bisher, AC-4) |
| Nur pausierte, mehrere | Rückfrage mit allen (AC-4) |
| Trip + nur pausierte | Trip (AC-3) |
| Trip + 1 aktiv (+ pausierte) | Rückfrage Trip/aktiver Vergleich; Pausierte erscheinen nicht in der Liste |
| Identische Namen (zwei Ortsvergleiche exakt gleich benannt) | auch voll ausgeschrieben nicht unterscheidbar; Rückfrage nennt sie weiter, die Antwort mit exaktem Namen verhält sich wie bisher (unverändert, nicht Teil dieses Fixes); Präfix-Fallback greift nie bei Mehrfachtreffer. Behebung durch Umbenennen im Frontend |
| Knopf `act_pause`, `:1354` | unverändert (AC-6) |
| E-Mail | Betreff-Name Pflicht, keine Rückfrage-Auflösung (Beleg oben); nur Präfix-Fallback über Processor |
| Trip-Name-Kollision durch Präfix | Präfix nur als letzter Fallback, nur eindeutig, nur mit gültigem Befehl-Rest |

## Testplan

- **Schicht:** Kern (deterministisch, ohne Netz/Live-Dienste), keine Mocks, die nur die
  eigene Annahme spiegeln; Presets als echte Dicts mit den Feldern `paused_at`, `schedule`,
  `archived_at`, `end_date`.
- **Zwei Nutzer:** AC-9.
- **Rot-vor-Fix:** AC-1 und AC-8 (Roundtrip) reproduzieren den Bug aus Nutzersicht.
- **Mutations-Gegenprobe (PFLICHT, per String-Ersetzung mit externer Sicherungskopie, nie
  `git checkout/stash/reset`):**
  1. Pausierten-Filter auch für `pause`/`weiter` aktivieren ⇒ AC-2 muss rot werden.
  2. Rückfall bei „0 aktive übrig“ entfernen ⇒ AC-4 muss rot werden.
  3. `is_silenced` durch nur `paused_at` ersetzen ⇒ AC-5 (Variante `schedule="manual"`)
     muss rot werden.
  4. Eindeutigkeitsprüfung beim Kürzen entfernen ⇒ AC-7 muss rot werden.
  5. Präfix-Fallback nimmt bei Mehrfachtreffer den ersten ⇒ AC-8 muss rot werden.
  6. Mindestlänge 4 des Präfix auf 1 senken ⇒ AC-8 muss rot werden.
  Wird eine Mutation von keinem Test gefangen, ist das ein Finding.
- **Bestehende Tests grün halten:** `tests/tdd/test_eingangsauswahl_trip_und_vergleich.py`,
  `tests/tdd/test_trip_auswahl_geteilt.py`, `test_befehle_*_e2e.py` (nur benannte Dateien
  ausführen).
- **Staging-Validierung (Live-Schicht):** Telegram-/Premium-SMS-Befehl `heute` über den
  echten Eingang mit Test-Nutzer, 1 aktiver + pausierte Vergleiche.

## Known Limitations

- Identische Namen bleiben unterscheidungslos (siehe Randfälle).
- Passen eindeutige Namen nicht in 160 Zeichen, hat Eindeutigkeit Vorrang vor der
  Kürzlänge; bei sehr vielen Kandidaten kann die Rückfrage länger als 160 Zeichen werden
  (dann mehrteilige SMS, nur Kostenfrage, keine Falschauflösung).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Verfeinerung der in #2282 getroffenen Auflösung (Pause zählt nur für
  `pause`/`weiter` als aktiv); keine Grundsatzentscheidung zu Kanälen, Provider,
  Datenmodell, Auth, Editor oder Deploy berührt.

## Changelog

- 2026-10-25: Initial spec created (Issue #2615)
