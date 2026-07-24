---
entity_id: warnmail_official_alert_display
type: bugfix
created: 2026-07-23
updated: 2026-07-23
status: draft
version: "1.0"
tags: [official-alert, warnmail, mail-darstellung, bundle:G-mail-darstellung]
workflow: warnmail
---

# Warnmail — Darstellungsfehler amtliche Warn-/Alarm-Mail (Bündel)

## Approval

- [ ] Approved

## Purpose

Gebündelter Bug-Fix für sechs zusammenhängende Darstellungsfehler der amtlichen
Warn-/Alarm-Mails bei Trips (Bündel `bundle:G-mail-darstellung`, Issues #1326,
#1248, #1251, #1338). Betroffen sind: die Warn-Karte selbst (zeigt statt
betroffener Segmente die ganze Route mit durchgestrichenen Chips, doppelt
benannte Gefahren), der Betreff (nennt bei gemischtem Umfang nur das Segment
der führenden Warnung), die Quellen-Angabe (nennt bei gebündelten Warnungen
aus zwei Behörden nur eine Quelle) sowie der in den Abweichungs-Alarm
eingebettete Warn-Block (falsches Format, technischer Renderer-Pfad statt
echter Datenquelle in der Fußzeile). Ziel: die Mail zeigt in jedem Fall genau
das, was tatsächlich zutrifft — keine Verdichtung auf "gilt für alles", keine
verlorenen Quellen, keine internen Pfad-/Versions-Strings in einer
nutzerorientierten Fußzeile.

## Source

- **File:** `src/output/renderers/alert/official_alerts.py`
- **Identifier:** `build_official_alert_notices`, `_display_label`,
  `render_official_alert_subject`, `render_warn_block`
- **File:** `src/services/notification_service.py`
- **Identifier:** `_dispatch_alert_message`, `_official_source_label_for`
- **File:** `src/output/renderers/email/helpers.py`
- **Identifier:** `build_origin_footer`
- **File:** `src/output/renderers/alert/render.py`
- **Identifier:** `_with_origin`

> Schicht-Hinweis: alle betroffenen Dateien liegen im Python-Core
> (`src/output/renderers/`, `src/services/`) — kein Go-/Frontend-Code betroffen.

## Estimated Scope

- **LoC:** ~90-140 Produktiv (inkl. der zusätzlichen Call-Site-Anpassungen für
  Befund 4a, s. Betroffene Dateien) + ~50-70 Test
- **Files:** 4 Kern-Produktivdateien (Bestand aus `docs/context/warnmail.md`)
  + 4 zusätzliche Call-Site-Dateien (html.py/compact.py/plain.py/compare_html.py,
  s. Abweichung unten) + 2 Testdateien
- **Effort:** medium (mehrere unabhängige, aber im selben Rendering-Baustein
  verankerte Korrekturen; Risiko liegt in geteilten Funktionen, nicht in
  Komplexität der Einzel-Fixes)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `OfficialAlertNotice` (official_alerts.py) | dataclass | Trägt `free_chips`/`affected_chips`/`scope_kind`/`scope_ids` — Basis für Befund 1 + 3 |
| `render_warn_block` (official_alerts.py) | function | Geteilter Warn-Block-Renderer (`variant="standalone"|"embedded"`) — Ziel-Baustein für Befund 4b |
| `build_origin_footer`/`OriginFooter` (helpers.py) | function/dataclass | SSoT der Herkunfts-Fußzeile (#1241) — Ziel-Baustein für Befund 4a |
| `AlertMessage`/`AlertEvent`/`OnsetEvent` (alert/model.py) | dataclass | Kanonisches Alert-Modell — NICHT Teil der Affected Files dieses Bundles (s. Known Limitations zu Befund 4a) |
| ADR-0011 (alert-render-single-backend-renderer) | ADR | Ein Backend-Renderer für alle Alert-Kanäle — Befund-4b-Fix bleibt innerhalb dieses Prinzips |
| ADR-0029 (openmeteo-standard-provider) | ADR | Begründet den Fallback-Quellstring für Pfade ohne plumbing-fähige Provider-Info (Befund 4a) |

## Implementation Details

Kein Implementierungscode in dieser Spec — nur Verhaltens-Verträge (Acceptance
Criteria) und Verortung. Root-Causes mit file:line stehen in
`docs/context/warnmail.md` (Abschnitt „Root Causes"); diese Spec zitiert die
relevanten Stellen nur zur Einordnung, nicht als Copy-Paste-Vorlage.

**Befund 1 (#1326a):** `_trip_total_segment_ids` + `build_official_alert_notices`
befüllen `free_ids`/`free_chips` heute mit ALLEN nicht-betroffenen Segmenten der
Gesamtroute. Der Compare-Builder (`build_compare_official_alert_notices`) setzt
`free_chips=[]` bereits fest — das ist das Vorbild für den Trip-Builder.

**Befund 2 (#1326b):** `_display_label`s else-Zweig (`display = f"{typ} — {label}"`)
konkateniert deutschen Typ + rohes Quell-Label, wenn keine der beiden
Ersetz-Heuristiken (`typ in label` bzw. `"—" in label`) greift. Für gemappte
Gefahren (Vigilance/MeteoAlarm mit englischem Roh-Label) soll NUR der deutsche
Typ erscheinen.

**Befund 3 (#1248):** `render_official_alert_subject` prüft `_uniform_scope`
nur für `scope_kind=="locations"` (Compare); der Route-Pfad (Trip, Default
`scope_kind="route"`) nimmt bedingungslos `_scope_display(leading)`. Die
Bedingung muss unabhängig vom `scope_kind` greifen.

**#1251:** `_official_source_label_for` (notification_service.py) wählt die
Quelle der höchststufigen (`leading`) Warnung und reicht genau EINEN
`source_label`-String an `render_warn_block`/`render_official_alert_html`
durch. Bei einem Bündel aus zwei Behörden geht die zweite Quelle verloren.

**Befund 4b (#1338 Format):** `_dispatch_alert_message` (notification_service.py:945-960)
hängt den amtlichen Zusatzblock heute über `render_official_alert_notice_plain`
+ HTML-Escaping in ein rohes `<p>` — der geteilte, bereits existierende
`render_warn_block(variant="embedded", ...)` (dieselbe Funktion, die
`send_official_alert` für die eigenständige Warn-Mail nutzt) MUSS stattdessen
verwendet werden.

**Befund 4a (#1338 Footer) — Quell-Semantik (Ergebnis der Code-Lektüre):**
`build_origin_footer` (helpers.py) erzeugt Zeile 2 heute IMMER als
`f"{renderer_name}{variant} · {_DEPLOYED_COMMIT}"` — ein technischer
Renderer-Pfad + Git-Commit, kein fachlicher Wert. JEDER Aufrufer übergibt
aktuell nur `renderer_name` (z.B. `"alert/render.py"`,
`"alert/official_alerts.py"`, `"email/html.py"`, `"email/compact.py"`,
`"email/compare_html.py"`). Für die geforderte „echte Datenquelle" gilt pro
Mail-Typ folgende, durch Code-Lektüre verifizierte Verfügbarkeit:

| Mail-Typ | Reale Quelle bereits verfügbar? | Fundstelle |
|---|---|---|
| trip-briefing (full/compact), plain | JA — `segments[0].provider` liegt in derselben Funktion, die `build_origin_footer` aufruft, bereits als lokale Variable vor (bestehende „Data: {provider}"-Zeile) | `html.py:414` (`provider_str`), `compact.py:218`/`plain.py:299` (`f"Data: {segments[0].provider} (...)"`) |
| official-alert (standalone) | JA — `source_label` ist am Aufrufort bereits berechnet (ggf. nach #1251-Fix mehrere Quellen, komma-separiert) | `official_alerts.py:1201` ff., `notification_service.py:575` |
| radar-alert (Onset) | JA — `OnsetEvent.source_label` trägt die reale Quelle bereits pro Event (z.B. „Radar (DWD)") | `alert/model.py:39`, `render.py` `msg.events[0]` |
| deviation-alert (Trip, `msg.source is None`) | NEIN ohne Modelländerung — `AlertMessage`/`AlertEvent` (alert/model.py) tragen keinerlei Provider-Feld; `to_alert_message()` (project.py) erhält zwar `segments` und könnte `segments[0].provider` ableiten, aber `model.py`/`project.py` sind NICHT Teil der für dieses Bündel freigegebenen Affected Files | `alert/model.py`, `alert/project.py:52-68` |
| deviation-alert (Compare, `to_point_alert_message`/`to_multi_point_alert_message`) | NEIN — diese Pfade erhalten gar keine `segments`, keine Provider-Information ist an dieser Stelle vorhanden | `alert/project.py:71-165` |
| compare (Ortsvergleich-Mail-Fuß) | NEIN — `_render_app_footer()` erhält aktuell keinerlei Datenquellen-Parameter, `ComparisonResult`/`LocationResult` (app/user.py) führen kein Provider-Feld | `compare_html.py:986-993` |

**OFFENER PUNKT (an PO zur Bestätigung, nicht geraten):** Für die drei
NEIN-Zeilen oben gäbe es zwei Wege — (a) Modelländerung (additives
`AlertMessage`-Feld analog `location_label`/`cooldown_display`, Provider von
`to_alert_message()`/Compare-Aufrufern durchreichen) — sprengt den deklarierten
Affected-Files-Rahmen dieses Bündels und ist Folgearbeit, ODER (b) fester
Fallback-String `"Open-Meteo"` (ADR-0029: einziger produktiv aktiver
Wetter-Standard-Provider im gesamten System) statt `"unknown"`. Diese Spec
setzt **(b)** als Scope für dieses Bündel an — siehe AC-5 — mit explizitem
Verweis auf Folgearbeit für (a), falls der PO künftig einen ECHTEN
per-Event-Provider im Footer wünscht (dann eigenes Issue, da model.py-Änderung).

## Expected Behavior

- **Input:** Trip mit amtlichen Warnungen (`OfficialAlert`-Objekten,
  Segment-Zuordnung), Abweichungs-Alarm-Events (`AlertMessage`) mit optional
  eingebetteten `official_notices`.
- **Output:** E-Mail (HTML + Plain), Betreff, Telegram- und SMS-Text, die
  jeweils NUR die tatsächlich zutreffenden Fakten zeigen (betroffene Segmente,
  deutsche Gefahrenbezeichnung, ehrlicher Umfang im Betreff, alle beteiligten
  Quellen, korrekt formatierter eingebetteter Warn-Block, echte Datenquelle im
  Fuß).
- **Side effects:** keine (reine Renderer-/Präsentationslogik, kein
  Datenmodell-Rework, keine Persistenzänderung).

## Acceptance Criteria

- **AC-1 (Befund 1, #1326a):** Given ein Trip mit vielen Segmenten (z.B. 63)
  und einer amtlichen Warnung, die nur 1 Segment betrifft / When die
  Warn-Karte (E-Mail-HTML, Standalone oder eingebettet) gerendert wird / Then
  erscheinen KEINE durchgestrichenen Chips der übrigen 62 Segmente — die Karte
  nennt ausschließlich den betroffenen Umfang (z.B. „Betrifft: Segment 5" bzw.
  „Betrifft: Segment 3–5, Ziel").
  - Test: `build_official_alert_notices()` mit 63-Segment-Trip + 1 betroffenem
    Segment aufrufen, gerendertes HTML auf Abwesenheit von `line-through`/
    `.seg.off` UND auf Abwesenheit der 62 unbetroffenen Segment-Bezeichner
    prüfen (kein Datei-Inhalts-Check, sondern tatsächliches Renderer-Ergebnis).

- **AC-2 (Befund 2, #1326b):** Given eine gemappte Gefahr mit deutschem
  Anzeigetext „Gewitter" und rohem, abweichendem Quell-Label „Orange
  Thunderstorm Warning" / When Betreff UND Body (HTML/Plain/Telegram/SMS)
  gerendert werden / Then erscheint NUR „Gewitter" — nirgends die Kombination
  „Gewitter — Orange Thunderstorm Warning" oder eine sonstige Verkettung aus
  beidem.
  - Test: `_display_label`/`render_official_alert_subject`/
    `render_official_alert_html` mit einem `OfficialAlert(hazard="thunderstorm",
    label="Orange Thunderstorm Warning")` aufrufen, Betreff+Body auf
    Abwesenheit des Roh-Labels UND Anwesenheit von „Gewitter" prüfen.

- **AC-3 (Befund 3, #1248):** Given mehrere Warnungen mit VERSCHIEDENEM Umfang
  (unterschiedliche `scope_ids`, egal ob `scope_kind="route"` oder
  `"locations"`) / When der Betreff gerendert wird / Then nennt der Betreff
  KEIN einzelnes Segment/keinen einzelnen Ort als gemeinsamen Umfang, sondern
  eine ehrliche Sammelangabe je `scope_kind` (Route: „mehrere Segmente"; Orte:
  „mehrere Orte", Bestandsverhalten). Nur wenn ALLE Warnungen denselben Umfang
  haben, wird dieser genannt.
  - Test: bestehender `test_ac3_mixed_levels_highest_leads_all_channels`
    (`tests/tdd/test_official_alert_template_render.py:130`) MUSS auf die neue
    Erwartung `"[KHW 403] mehrere Segmente · ORANGE Gewitter (Sa) + GELB Hitze
    (Fr)"` (statt `"Segment 3 · ..."`) umgestellt werden — reproduziert exakt
    den Bug (führendes Segment fälschlich als Gesamt-Umfang behauptet).

- **AC-4 (#1251):** Given eine gebündelte Warn-Karte aus zwei verschiedenen
  amtlichen Quellen (z.B. GeoSphere Austria + Météo-France) / When die
  Quelle-Box (Standalone-HTML) bzw. die Quellen-Angabe im eingebetteten
  Warn-Block gerendert wird / Then nennt die Mail BEIDE beteiligten Quellen
  (bzw. die Quelle pro Warnung), nicht nur die Quelle der führenden
  (höchststufigen) Warnung.
  - Test: zwei `OfficialAlertNotice`-Objekte mit unterschiedlichem
    `alert.source` bündeln, `render_official_alert_html`/`render_warn_block`
    aufrufen, geprüft wird dass BEIDE Quell-Anzeigenamen im Output stehen
    (nicht nur einer).

- **AC-5 (Befund 4a, #1338 Footer):** Given eine Mail eines beliebigen Typs
  wird gerendert / When die Herkunfts-Fußzeile (Zeile 2, `build_origin_footer`)
  gebaut wird / Then zeigt Zeile 2 je nach Mail-Typ die tatsächliche
  Datenquelle statt des internen Renderer-Pfads oder des Git-Fallbacks
  `"unknown"`: für trip-briefing/compact/plain den echten
  `segments[0].provider`-Wert; für official-alert den (nach AC-4 ggf.
  mehrfachen) `source_label`; für radar-alert das reale
  `OnsetEvent.source_label`; für deviation-alert (Trip+Compare) sowie für die
  Ortsvergleich-Mail (`compare`) den festen Fallback-String `"Open-Meteo"`
  (ADR-0029) — NIEMALS `"unknown"`, NIEMALS ein `.py`-Pfad, NIEMALS ein reiner
  Commit-Hash als alleiniger Inhalt von Zeile 2.
  - Test: für jeden der sechs Mail-Typen den jeweiligen Renderer mit einer
    echten, minimalen Fixture aufrufen und den Footer-Text auf Abwesenheit
    von `"alert/"`/`"email/"`-Pfad-Fragmenten UND von `"unknown"` prüfen,
    sowie Anwesenheit des in der Tabelle oben definierten Quell-Strings.
  - Bestandstest `tests/tdd/test_mail_origin_footer.py` (AC-1/2/3/9 dort)
    prüft heute explizit, dass der Commit-Hash im Footer steht — diese
    Assertions MÜSSEN auf die neue Erwartung (Quelle statt Commit) umgestellt
    werden; AC-9 dort (`_deployed_commit`-Verhalten selbst) bleibt als
    Hilfsfunktion ggf. bestehen, wird aber nicht mehr in Zeile 2 verbaut.

- **AC-6 (Befund 4b, #1338 Format):** Given ein Abweichungs-Alarm (Trip) mit
  eingebetteten amtlichen Warnungen (`official_notices` gesetzt) / When
  `_dispatch_alert_message` die Mail baut / Then wird der amtliche Zusatzblock
  über `render_warn_block(notices, variant="embedded", ...)` gerendert (wie
  `send_official_alert` es für die eigenständige Warn-Mail tut) — NICHT als
  roher, HTML-escaped Plaintext in ein `<p>`-Element. Der eingebettete
  Warn-Block trägt dieselbe visuelle Formatierung (Farb-Tokens, Chips,
  Quelle-Zeile) wie in der eigenständigen amtlichen Warn-Mail.
  - Test: `_dispatch_alert_message` mit `official_notices` aufrufen, den HTML-
    Output auf Anwesenheit der `.wb`-Bannerform-Marker (z.B. CSS-Klasse
    `wb-src`/`wb-count`, s. `_render_warn_block_embedded`) statt eines rohen
    `<p>{escaped text}</p>` prüfen — UND vergleichend gegen den Output von
    `send_official_alert` mit denselben Notices auf strukturelle Gleichheit
    des Warn-Block-Fragments prüfen.

## Known Limitations

- Befund 4a löst die per-Event-Provider-Frage für deviation-alert (Trip +
  Compare) NICHT vollständig — der feste Fallback `"Open-Meteo"` ist korrekt,
  solange ADR-0029 gilt (ein einziger Live-Standard-Provider), wird aber
  falsch, sobald ein zweiter Live-Provider aktiv würde. Echtes per-Event-Feld
  erfordert eine `AlertMessage`-Modelländerung — bewusst NICHT Teil dieses
  Bündels (Affected Files beschränkt sich auf Renderer/Service-Ebene ohne
  `alert/model.py`).
- `_display_label`-Fix (Befund 2) betrifft nur den `else`-Zweig (gemappte
  Hazards mit divergierendem Roh-Label). `access_ban`/„Extreme Hitze" laufen
  über die beiden Ersetz-Heuristiken davor und bleiben unberührt.
- Befund 1 greift nur im Trip-Builder (`build_official_alert_notices`); der
  Compare-Builder setzt `free_chips=[]` bereits. SMS/Telegram nutzen
  `scope_label`, nicht `free_chips` — unberührt.

## Abgelöste Entscheidungen (ADR)

Diese Spec kehrt zwei zuvor implementierte (aber nie als eigenes ADR
festgehaltene) Design-Entscheidungen bewusst um:

1. **Befund 1 löst die Durchstreich-Gitter-Absicht aus #1233/#1216 ab.** Die
   damalige Spec-Entscheidung (Warn-Karte zeigt die GESAMTE Route mit
   durchgestrichenen freien Segmenten, „übrige Strecke frei"-Hinweis) war nie
   als eigenständiges ADR dokumentiert — sie stand nur in den Specs zu
   #1216/#1233. Da diese Umkehr eine sichtbare, mehrfach durchdachte
   Produkt-Entscheidung revidiert, MUSS sie jetzt als ADR festgehalten werden
   (nächste freie Nummer: **ADR-0033**, Titel z.B. „Amtliche Warn-Karte zeigt
   nur betroffene Segmente, kein Vollrouten-Gitter"), Status Akzeptiert, mit
   Verweis „ersetzt die #1233/#1216-Spec-Festlegung (nie als ADR
   dokumentiert)".
2. **Befund 4a löst die Provenance-Zeile-2-Festlegung aus #1241 ab** (Zeile 2
   = erzeugender Renderer + Commit-Stand, für ALLE Mail-Typen). Auch #1241
   war nur als Spec/Code-Kommentar dokumentiert, nicht als ADR. Diese Spec
   verlangt ein neues ADR (**ADR-0034**, Titel z.B. „Herkunfts-Fußzeile zeigt
   die reale Datenquelle statt Renderer-Pfad + Commit-Hash"), Status
   Akzeptiert, mit explizitem Verweis auf die in AC-5 dokumentierte
   Fallback-Regel (ADR-0029-Bezug) und die in „Known Limitations" benannte
   offene Folgearbeit für echte per-Event-Provider-Angaben.

Beide neuen ADR-Dateien sind in `docs/adr/README.md` (Index-Tabelle)
einzutragen — der Index-Drift-Test (`tests/test_adr_index_drift.py`) erzwingt
das ohnehin bei jedem Commit, der eine neue ADR-Datei hinzufügt.

## Test-Plan

Kern-Schicht, deterministisch, KEINE Mocks — echte `OfficialAlert`/
`OfficialAlertNotice`/`AlertMessage`/`AlertEvent`/`OnsetEvent`-Objekte, echte
Renderer-Aufrufe. Jeder Test reproduziert den jeweiligen Befund aus
Nutzersicht (rot vor Fix, grün nach Fix):

1. **Befund 1:** Trip mit 63 Segmenten (`_trip_total_segment_ids`-Fixture),
   1 betroffenes Segment → HTML/Standalone UND embedded prüfen: kein
   `line-through`, keine 62 unbetroffenen Segment-Chips im Output.
2. **Befund 2:** `OfficialAlert(hazard="thunderstorm", label="Orange
   Thunderstorm Warning")` → Betreff + HTML + Telegram + SMS auf Abwesenheit
   des Roh-Labels, Anwesenheit von „Gewitter" prüfen.
3. **Befund 3 (mitzuziehen):** `tests/tdd/test_official_alert_template_render.py::
   test_ac3_mixed_levels_highest_leads_all_channels` (Zeile ~130) auf die neue
   Erwartung `"mehrere Segmente"` statt `"Segment 3"` umstellen.
4. **#1251:** zwei Notices mit unterschiedlichem `alert.source` bündeln →
   beide Quell-Anzeigenamen im gerenderten Output nachweisen.
5. **Befund 4a (mitzuziehen):** `tests/tdd/test_mail_origin_footer.py` — die
   Assertions, die den Commit-Hash in Zeile 2 erwarten (AC-1/2/3, ggf. weitere),
   auf die neue Quell-Erwartung je Mail-Typ umstellen (Tabelle in
   „Implementation Details"); zusätzlich ein neuer Test je Mail-Typ, der
   Abwesenheit von `"unknown"` und `.py`-Pfad-Fragmenten in Zeile 2 nachweist.
6. **Befund 4b:** `_dispatch_alert_message` mit `official_notices` aufrufen,
   HTML-Fragment strukturell mit dem Output von `send_official_alert`
   (`variant="embedded"` intern) vergleichen — kein rohes `<p>`-Escaping mehr.

Live-E2E (Staging, außerhalb dieser Kern-Suite): eine echte amtliche
Warn-Mail UND ein Abweichungs-Alarm mit eingebetteter Warnung an
`gregor-test@henemm.com` senden, IMAP-Verifikation der Darstellung —
Pflicht laut `X-GZ-Mail-Type: official-alert` bzw. `deviation-alert`-Dispatch
vor „E2E bestanden".

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0033 (neu, Befund 1), ADR-0034 (neu, Befund 4a) — siehe
  Abschnitt „Abgelöste Entscheidungen (ADR)" oben für Titel/Inhalt.
- **Rationale:** Beide Entscheidungen (Segment-Gitter-Abschaffung,
  Provenance-Zeile-2-Umkehr) revidieren sichtbar zuvor getroffene, mehrfach
  bekräftigte Produkt-Entscheidungen (#1233/#1216 bzw. #1241) — laut
  `docs/adr/README.md` Faustregel „eine bewusste Produkt-Grenze wird gezogen"
  MÜSSEN sie als ADR mit Status „Abgelöst durch"-Verweis auf die (nachträglich
  ebenfalls zu dokumentierenden) Vorgänger-Festlegungen geführt werden, damit
  diese Umkehr künftig nicht unbemerkt wieder rückgängig gemacht wird (Muster
  ADR-0002→ADR-0029).

## Betroffene Dateien

| File | Change Type | Description |
|------|-------------|--------------|
| `src/output/renderers/alert/official_alerts.py` | MODIFY | Befund 1 (Builder `free_chips=[]`), Befund 2 (`_display_label` else-Zweig), Befund 3 (`_uniform_scope`-Prüfung unabhängig von `scope_kind`), #1251 (Quelle pro Warnung in `_standalone_src_html`/embedded) |
| `src/services/notification_service.py` | MODIFY | Befund 4b (`_dispatch_alert_message`: geteilter `render_warn_block` statt roher Plain-Embed), #1251 (`_official_source_label_for` liefert alle Quellen statt nur der führenden) |
| `src/output/renderers/email/helpers.py` | MODIFY | Befund 4a (`build_origin_footer`-Signatur um echten Quell-String erweitern statt `renderer_name` als Zeile-2-Inhalt zu nutzen) |
| `src/output/renderers/alert/render.py` | MODIFY | Befund 4a (`_with_origin`: Quelle aus `OnsetEvent.source_label` bzw. Fallback `"Open-Meteo"` statt `renderer_name="alert/render.py"`) |
| `src/output/renderers/email/html.py` | MODIFY | Befund 4a — Call-Site-Anpassung: `provider_str` (bereits lokal vorhanden, `html.py:414`) an `build_origin_footer` durchreichen. **Abweichung von `docs/context/warnmail.md`:** dort nicht gelistet, aber durch die PO-Vorgabe „betrifft alle Mail-Typen" (Befund 4a) zwingend erforderlich. |
| `src/output/renderers/email/compact.py` | MODIFY | Befund 4a — analog html.py (`segments[0].provider`, `compact.py:218`). Abweichung wie oben. |
| `src/output/renderers/email/plain.py` | MODIFY | Befund 4a — analog html.py (`segments[0].provider`, `plain.py:299`). Abweichung wie oben. |
| `src/output/renderers/email/compare_html.py` | MODIFY | Befund 4a — `_render_app_footer()` braucht einen Quell-Parameter (Fallback `"Open-Meteo"`, s. Known Limitations). Abweichung wie oben. |
| `tests/tdd/test_official_alert_template_render.py` | MODIFY | AC-Assertions Befund 1 (Chips), 2 (Doppelname), 3 (`test_ac3_...:130` Erwartung `"mehrere Segmente"`) mitziehen |
| `tests/tdd/test_mail_origin_footer.py` | MODIFY | #1241-Tests (Commit-Hash-Erwartung in Zeile 2) auf neue Quell-Erwartung je Mail-Typ (Befund 4a) umstellen |

## Risiken

- **Geteilte Funktionen:** `render_warn_block`/`_display_label`/
  `build_origin_footer` werden von JEDEM Mail-Typ genutzt — ein Fehler in
  einer dieser Funktionen wirkt sofort auf alle Kanäle (Trip-Briefing,
  Ortsvergleich, Standalone-Alarm, eingebetteter Block). Golden-Email-Fixtures
  (falls vorhanden) MÜSSEN vor Merge geprüft werden, damit ein bestandenes
  neues AC keine stille Regression in einem anderen Mail-Typ verdeckt.
- **Scope-Erweiterung über die in `docs/context/warnmail.md` gelistete
  Affected-Files-Tabelle hinaus** (html.py/compact.py/plain.py/
  compare_html.py): notwendig, weil die PO-Entscheidung zu Befund 4a
  ausdrücklich „betrifft alle Mail-Typen" verlangt, aber die ursprüngliche
  Root-Cause-Analyse nur die vier Kern-Alert-Dateien gelistet hatte. Diese
  Spec macht die Erweiterung explizit, statt sie stillschweigend während der
  Implementierung nachzuziehen (Nachvollziehbarkeit, LoC-Budget-Kontrolle).
- **Fallback „Open-Meteo" (AC-5) ist eine bewusste Scope-Grenze, kein
  vollständiger Fix:** solange kein zweiter Live-Provider existiert (ADR-0029),
  ist der Fallback korrekt; er wird bei einer künftigen Multi-Provider-Welt
  erneut falsch und braucht dann echtes per-Event-Provider-Tracking
  (`AlertMessage`-Modelländerung, eigenes Issue).
- **`test_ac3_mixed_levels_highest_leads_all_channels`** ist ein Bestandstest
  mit einer HART kodierten, jetzt als Bug erkannten Erwartung
  (`"Segment 3 · ..."`) — die Änderung MUSS zusammen mit dem Produktivfix
  committet werden, sonst bricht die Kern-Testsuite (100%-grün-Pflicht).

## Changelog

- 2026-07-23: Initial spec created
