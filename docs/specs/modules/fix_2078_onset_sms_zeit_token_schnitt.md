---
entity_id: fix_2078_onset_sms_zeit_token_schnitt
type: bugfix
created: 2026-08-23
updated: 2026-08-23
status: draft
workflow: fix-2078-onset-sms-zeit-token-schnitt
---

# Onset-Kurznachricht: Kopf vor dem Zeit-Token kappen statt den fertigen Text hart zu schneiden (#2078)

## Approval

- [ ] Approved

## Purpose

`_render_sms_onset` und `_render_sms_onset_shift_only` bauen den Kopf (Ortsname) ohne
Längenbegrenzung und schneiden danach den fertigen Text stur bei `limit` (Default 140)
ab. Bei ausreichend langem Ortsnamen trifft dieser Endschnitt mitten ins Zeit-Token —
die Kurznachricht (SMS/Premium-SMS/Telegram-Kurzstil) trägt dann eine **inhaltlich
falsche** statt einer fehlenden Uhrzeit (`Sa0:40` → `Sa0:4`, liest sich wie eine andere
echte Uhrzeit). Fix: den Kopf VOR dem Zusammensetzen kappen (analog zum etablierten
Muster in `_render_sms_corridor_only`) — die Zeit-Aussage bleibt dadurch bei jeder
Kopflänge vollständig, nur der Ortsname wird im Extremfall kürzer.

## Source

- **File:** `src/output/renderers/alert/render.py`
- **Identifier:** `_render_sms_onset` (Zeilen 895-964), `_render_sms_onset_shift_only`
  (Zeilen 466-471)

Schicht: **Python-Core** (Renderer). Keine Go-Änderung, keine Frontend-Änderung.

## Estimated Scope

- **LoC:** ca. +6/-2 in `render.py` (zwei Kopf-Zeilen je einen `[:24]`-Zuschnitt);
  Test-LoC deutlich höher (neue Verhaltens-Testdatei mit ~7 ACs)
- **Files:** 1 Produktivdatei, 1 neue Testdatei
- **Effort:** low — lokal begrenzte Änderung an zwei strukturell identischen
  Zweigen, kein Datenmodell-, kein API-Vertrag berührt

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_ascii_alert_location` (`render.py:1611-1621`) | Funktion | erzeugt den Kopf-Rohtext (Piktogramm-Entfernung + ASCII/GSM-7-Faltung); MUSS weiterhin VOR der neuen Kappung laufen, sonst zählt die Kappung Unicode-Codepoints statt gefalteter Zeichen |
| `_render_sms_corridor_only` (`render.py:1420-1438`) | Funktion | Referenzmuster für die Kopf-Kappung (`trip[:16]`, `location_label[:24]`/`where[:24]`) — wird nicht verändert, nur als Vorbild übernommen |
| `_sms_onset_time` / `_sms_onset_ende` / `_sms_onset_menge` / `_sms_onset_sharpness_marker` (`render.py`) | Funktionen | bauen das Zeit-/Mengen-Token; bleiben unverändert — die Spec ändert ausschließlich den Kopf-Anteil `head` |
| `_sms_onset_shift_token` (`render.py:430-437`) | Funktion | baut das Verschiebungs-Token in `_render_sms_onset_shift_only`; bleibt unverändert |
| `notification_service.py:1598,1666,1680` | Aufrufer | konsumiert `sms_body` unverändert für SMS, Premium-SMS und Telegram-Kurzstil — kein Aufrufer-Code ändert sich |
| `docs/specs/modules/fix_1935_1779_alarm_nachricht_klarheit.md` | Spec | legt die `[:24]`-Kopf-Kappung als Konvention für den Nachbarzweig fest — diese Spec überträgt sie auf die beiden verbliebenen Ausreißer |
| `docs/specs/modules/fix_1948_s4_nowcast_sms_zielbild.md` | Spec | Ursprungs-Spec von `_render_sms_onset`; „Known Limitations" dort benannte das Risiko bereits als „geerbtes Risiko" — diese Spec schließt es |
| `docs/specs/modules/fix_2051_s1_ende_und_dauer.md` | Spec | führte das zweite Zeit-Token (Ende-Suffix) ein, wodurch der Kopf-Endschnitt-Konflikt real wurde |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/output/renderers/alert/render.py` | MODIFY | `_render_sms_onset`: `head` mit `[:24]` kappen, bevor `body = f"{head}: {token}"` gebaut wird. `_render_sms_onset_shift_only`: identische Kappung auf `_onset_shift_location(msg)` |
| `tests/tdd/test_alert_sms_onset_zeit_token_kappung.py` | CREATE | neue Verhaltens-Testdatei für diese Spec (Name nach Verhalten, nicht nach Issue-Nummer) |

### Estimated Changes

- Files: 2
- LoC: +6/-2 (Produktivcode), Testdatei separat

## Implementation Details

In `_render_sms_onset` (`render.py:957-963`) wird jeder der drei Kopf-Zweige VOR dem
Zusammensetzen mit `body = f"{head}: {token}"` auf 24 Zeichen gekappt — analog zu
`location_label[:24]` in `_render_sms_corridor_only`:

```
if getattr(e, "location_label", None):
    head = _ascii_alert_location(e.location_label)[:24]
elif msg.source == COMPARE_RADAR_SOURCE:
    head = _ascii_alert_location(msg.trip_short)[:24]
else:
    head = _ascii_alert_location(_location_of((e,), None))[:24]
body = f"{head}: {token}"
return body if len(body) <= limit else body[:limit]
```

Die Reihenfolge bleibt bewusst: `_ascii_alert_location` (Piktogramm-Entfernung +
ASCII/GSM-7-Faltung) läuft ZUERST, `[:24]` schneidet danach den bereits gefalteten
Text — sonst zählt die Kappung Unicode-Codepoints eines Piktogramms statt sichtbarer
ASCII-Zeichen, und die Grenze verschiebt sich unvorhersehbar.

In `_render_sms_onset_shift_only` (`render.py:466-471`) analog:

```
head = f"{_ascii_alert_location(_onset_shift_location(msg))[:24]}: "
body = head + " ".join(
    _sms_onset_shift_token(oe) for oe in msg.onset_shift_events
)
return body if len(body) <= limit else body[:limit]
```

Der harte Endschnitt (`body[:limit]`, Default 140) bleibt in beiden Funktionen
UNVERÄNDERT als Sicherheitsnetz bestehen — er greift im Normalfall nach der Kopf-Kappung
nicht mehr, ist aber weiterhin die letzte Instanz gegen ein Überlaufen des Limits (z. B.
bei mehreren Tokens in `onset_shift_events` oder einem sehr kleinen, vom Aufrufer
übergebenen `limit`).

## Expected Behavior

- **Input:** `AlertMessage`/`OnsetEvent`/`OnsetShiftEvent` mit einem Ortsnamen
  (`location_label`, `trip_short` oder aufgelöster Segmentname), der nach ASCII-Faltung
  länger als 24 Zeichen ist.
- **Output:** Der Kopf-Anteil der Kurznachricht (vor dem `": "`) ist auf maximal 24
  Zeichen gekappt; das/die nachfolgenden Zeit-Token(s) stehen vollständig und
  unverändert im Text — unabhängig davon, wie lang der ungekappte Ortsname gewesen wäre.
- **Side effects:** keine. Reines Text-Rendering, keine Persistenz-, keine API-Änderung.
  Wirkt automatisch auf alle drei Kanäle, die denselben `sms_body` konsumieren (SMS,
  Premium-SMS, Telegram-Kurzstil).

## Acceptance Criteria

- **AC-1:** Given ein Trip-Onset-Alarm über `_render_sms_onset`, dessen aufgelöster
  Ortsname (`_location_of`-Fallback, dritter Kopf-Zweig) nach ASCII-Faltung länger als
  24 Zeichen ist / When `render_sms` rendert / Then ist der Kopf-Anteil vor dem `": "`
  auf maximal 24 Zeichen gekappt UND das vollständige Zeit-Token (`TH@HH:MM` bzw.
  `R@HH:MM`) steht unverändert und ungekürzt im Text.
  - Test: `OnsetEvent` ohne `location_label`, dessen Segment-/km-Auflösung einen langen
    Text erzeugt (oder ein präpariertes langes `trip_short` im COMPARE_RADAR_SOURCE-Zweig,
    s. AC-2), `render_sms()` aufrufen, Kopf-Teil vor `": "` extrahieren und auf Länge
    ≤24 prüfen, Zeit-Token per Regex (`\b(TH|R)@\d{1,2}:\d{2}\b`) vollständig nachweisen.

- **AC-2:** Given ein Ortsvergleich-Alarm mit genau einem Ort (`msg.source ==
  COMPARE_RADAR_SOURCE`, `location_label is None`, `msg.trip_short` länger als 24
  Zeichen) / When `render_sms` rendert / Then ist der Kopf auf 24 Zeichen gekappt und
  das Zeit-Token bleibt vollständig lesbar, unabhängig von der Kopflänge.
  - Test: `AlertMessage` mit `source=COMPARE_RADAR_SOURCE` und einem langen
    `trip_short` (z. B. einem konkatenierten, real langen Ortsnamen aus dem
    Testbestand) bauen, `render_sms()` aufrufen, Kopf-Länge und Token-Vollständigkeit
    wie AC-1 prüfen.

- **AC-3:** Given ein gebündelter Ortsvergleich-Alarm (`OnsetEvent.location_label`
  gesetzt, länger als 24 Zeichen) / When `render_sms` rendert / Then ist der Kopf
  gekappt und das Zeit-Token vollständig — derselbe Nachweis wie AC-1/AC-2, aber für den
  ersten der drei Kopf-Zweige (`location_label` gesetzt).
  - Test: `OnsetEvent(location_label=<langer Ortsname>)` bauen, `render_sms()` aufrufen,
    Kopf-Länge ≤24 und Zeit-Token vollständig per Regex prüfen.

- **AC-4:** Given einen kurzen, alltagstypischen Ortsnamen (≤24 Zeichen nach
  ASCII-Faltung, Normalfall) / When `render_sms` über `_render_sms_onset` rendert /
  Then ist die Ausgabe byte-identisch zum Verhalten vor diesem Fix — die Kappungsgrenze
  darf im Alltag nicht sichtbar werden (Regressionsschutz).
  - Test: bestehende Fixture aus `tests/tdd/test_alert_sms_onset_zeitpunkt.py`
    (`_onset_event()`, kurzer Ort) erneut durch `render_sms()` schicken und auf den
    bereits bekannten Goldstring (`"km 8-8: TH@15:40"`) prüfen — muss unverändert
    grün bleiben.

- **AC-5:** Given einen `_render_sms_onset_shift_only`-Alarm mit einem Ortsnamen länger
  als 24 Zeichen / When `render_sms` über den Onset-Shift-Zweig rendert / Then ist der
  Kopf auf 24 Zeichen gekappt UND das Verschiebungs-Token (`_sms_onset_shift_token`,
  Uhrzeit + Richtungswort) steht vollständig und unverändert im Text.
  - Test: `AlertMessage` mit `onset_shift_events` und langem, auflösbarem
    Ortsbezug bauen (Route ohne `events`/`corridor_events`, damit `_render_sms_body` in
    den Shift-Zweig verzweigt), `render_sms()` aufrufen, Kopf-Länge ≤24 und
    vollständiges Token (`to_time` + `shift_text`) per String-Suche nachweisen.

- **AC-6:** Given einen laufenden Nowcast-Alarm (`already_running=True`, Issue #2050
  S2b, `now`-Token statt Beginn-Zeit) mit einem Ortsnamen länger als 24 Zeichen / When
  `render_sms` rendert / Then ist der Kopf gekappt und das `now`-Token samt
  Ende-Grammatik (`now@HH:MM` bzw. `now >@HH:MM`) bleibt vollständig erhalten — der
  `already_running`-Zweig baut denselben `head` wie der Normalfall und ist von der
  Kappung ebenso betroffen.
  - Test: `OnsetEvent(already_running=True, ...)` mit langem Ortsnamen bauen,
    `render_sms()` aufrufen, Kopf-Länge ≤24 prüfen und `"now"` samt anschließendem
    Zeit-/Grenz-Token vollständig im Text nachweisen (kein abgeschnittenes `no`/`now@1`).

- **AC-7:** Given ein Onset-Ereignis mit ZWEI Zeit-Token (Beginn UND Ende-Suffix,
  Issue #2051 S1, `event_end_time` gesetzt) und einem Ortsnamen länger als 24 Zeichen /
  When `render_sms` rendert / Then bleiben BEIDE Zeit-Token (Beginn-Zeitpunkt und
  Ende-Suffix `@HH:MM` bzw. `>@HH:MM`) vollständig erhalten — genau der Fall, der den
  Bug laut Issue #2078 erst real gemacht hat, weil zwei Token statt einem am
  Zeilenende stehen.
  - Test: `OnsetEvent` mit gesetztem `event_end_time` (bzw. dem für den
    Ende-Suffix nötigen Feld-Kombination aus `fix_2051_s1_ende_und_dauer.md`) und
    langem Ortsnamen bauen, `render_sms()` aufrufen, beide Zeit-Token per Regex
    vollständig nachweisen (kein abgeschnittenes Suffix am Textende).

- **AC-8:** Given einen absurd langen Kopf-Rohtext, der auch nach der 24-Zeichen-Kappung
  plus Token-Anteil das Gesamtlimit (`limit`-Parameter) überschreiten würde (z. B.
  `limit` bewusst klein gewählt, etwa `limit=10`) / When `render_sms`/`_render_sms_onset`
  mit diesem `limit` rendert / Then greift weiterhin der harte Endschnitt
  `body[:limit]` — die Ausgabe ist nie länger als `limit` Zeichen, kein Crash, kein
  Overflow (Regressionsschutz für das bestehende Sicherheitsnetz).
  - Test: `_render_sms_onset`/`_render_sms_onset_shift_only` direkt mit kleinem
    `limit`-Wert aufrufen (bestehendes Muster aus den Signatur-Tests dieser Funktionen),
    `len(ergebnis) <= limit` prüfen.

- **AC-9:** Given einen Ortsnamen, der ein Piktogramm ODER GSM-7-Extension-Zeichen
  enthält (z. B. `~`, das auf `-` gefaltet wird) UND lang genug ist, um die
  24-Zeichen-Grenze zu berühren / When `render_sms` rendert / Then laufen
  Piktogramm-Entfernung und ASCII/GSM-7-Faltung (`_ascii_alert_location`) VOR der
  neuen 24-Zeichen-Kappung — die Kappung zählt sichtbare ASCII-Zeichen des bereits
  gefalteten Texts, nicht Unicode-Codepoints des Rohtexts.
  - Test: `OnsetEvent`/`AlertMessage` mit einem Ortsnamen bauen, der ein Piktogramm
    (z. B. 🏁) und danach ausreichend viele Zeichen enthält, sodass ein Zählen VOR der
    Faltung eine andere Kapp-Stelle träfe als ein Zählen NACH der Faltung;
    `render_sms()` aufrufen und den Kopf-Text gegen den erwarteten, bereits gefalteten
    und auf 24 Zeichen gekappten Text vergleichen (kein Piktogramm-Rest, keine
    GSM-7-Extension-Zeichen im Kopf).

## Out of Scope

- **`_render_sms_body`-Fallback-Kopf** (`render.py:1530`, Trip-Δ-Pfad ohne
  `location_positions`/`multi_location`/`location_label`, nutzt `_km_str(msg)`): trägt
  denselben ungekappten Kopf + harten Endschnitt, ist aber laut Kontext-Analyse
  strukturell geringeres Risiko — `_km_str` liefert typischerweise kurze km-Spannen/
  Segmentnamen, kein frei langer, nutzergesteuerter Ortsname. Kein konkreter
  Fehlerfall belegt. Bei Bedarf als Eintrag in Sammel-Issue #1199 nachtragen, nicht
  Teil dieser Scheibe.
- **Zentrale `limit`-Konstante** (aktuell dreifach als Default `140` dupliziert): rein
  kosmetisch, nicht Teil dieser Scheibe.

## Known Limitations

- Die 24-Zeichen-Grenze ist aus dem bestehenden Nachbarzweig (`_render_sms_corridor_only`)
  übernommen, nicht neu hergeleitet — sie ist die im Projekt bereits etablierte Konvention
  für SMS-Kopf-Ortstexte und wird hier bewusst NICHT neu bemessen.
- Der harte Endschnitt `body[:limit]` kann in seltenen Extremfällen (sehr viele
  Tokens/`onset_shift_events`, sehr kleines `limit`) weiterhin mitten in ein Token
  schneiden — dieses Restrisiko ist mit AC-8 als bestehendes, bewusst beibehaltenes
  Sicherheitsnetz dokumentiert, nicht Ziel dieser Spec, das restlos auszuschließen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** lokale Rendering-Korrektur innerhalb eines bestehenden, bereits per
  ADR-0011 (ein Backend-Renderer für alle vier Kanäle) etablierten Musters — keine neue
  Entscheidungsfläche (kein Kanal, kein Provider, kein Datenmodell, kein Auth-Aspekt
  betroffen).

## Changelog

- 2026-08-23: Initial spec created
