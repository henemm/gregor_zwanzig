---
entity_id: feat_1563_compare_vertretungshinweis
type: module
created: 2026-11-04
updated: 2026-11-04
status: draft
version: "1.0"
tags: [gewitter, fallback, sichtbarkeit, ortsvergleich, email, telegram, mehrort]
workflow: feat-1563-compare-vertretungshinweis
---

# Vertretungshinweis in der Ortsvergleichs-Mail (Mehrort-Zuordnung)

## Approval

- [ ] Approved

## Purpose

Wird bei einem Ort des Ortsvergleichs die Gewitter-Direktquelle oder die
Grundvorhersage durch eine Ersatzquelle vertreten, erfährt der Nutzer davon
heute nichts: ADR-0018 und ADR-0047 verbieten diese stille Degradation, im
Trip-Pfad ist der Hinweis seit #1492 S2b sichtbar. Diese Scheibe (Issue #1563,
Folgescheibe aus #1492 S2b, Epic #2259) trägt die Herkunft je Ort bis zum
Renderer und zeigt sie im Ortsvergleich mit **Ortszuordnung** („welcher Ort?").

## Source

- **File:** `src/app/user.py` (`LocationResult`),
  `src/services/comparison_engine.py` (`fetch_forecast_for_location`, Bau von
  `LocationResult`), `src/output/renderers/fallback_notice.py`,
  `src/output/renderers/email/compare_html.py` (`render_compare_html`,
  `_render_app_footer`), `src/output/renderers/comparison.py`
  (`render_comparison_text`, `render_compare_telegram`),
  `src/i18n/messages/{de,en}/mail.json`
- **Identifier:** `LocationResult.forecast_meta` (neu),
  `fallback_notice.build_compare_fallback_lines` (neu)

> **Schicht-Hinweis:** Reine Python-Core-Schicht (`src/app/`, `src/services/`,
> `src/output/renderers/`). Keine Go-API, kein Frontend. Es werden nur
> bereits vorhandene `ForecastMeta`-Felder (`app/models.py:81`) gelesen, nichts
> Persistentes geschrieben.

## Bezug

- ADR-0018 / ADR-0047 (Fallback ohne Kaschieren; Sichtbarkeit), ADR-0095
  (Kanalparität), ADR-0104 (DE/EN, Katalog).
- `docs/specs/modules/feat_1492_s2b_fallback_sichtbarkeit.md` (Known
  Limitations Punkt 1, Regeln R1–R11 — die Formulierung wird **nicht**
  neu entschieden).
- Kontext: `docs/context/feat-1563-compare-vertretungshinweis.md`.

## Estimated Scope

- **LoC:** Quellcode ~70, i18n ~10, Tests ~150–200 (Summe über Standard-Limit
  möglich; Override-Entscheidung beim PO nach Diff, wie bei S2b — Testumfang
  skaliert mit Ausgabewegen x Fehlerlagen, hier 3 Ausgaben x 5 Zustände).
- **Files:** 7 Quell-, 2–3 Testdateien
- **Effort:** medium (Mail-Inhalts-Dateien: Renderer-Commit-Gate #811)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.models.ForecastMeta` | Datenmodell | wird je Ort gelesen (`fallback_model`, `fallback_metrics`, `fallback_reason`) |
| `fallback_notice.build_fallback_lines(meta, lang=)` | intern | **einzige** Formulierungsquelle (Trip/Compare-Teilung ist Gate) |
| `fallback_notice.select_fallback_meta` | intern | bleibt **ungenutzt** (liefert erstes Segment, verwirft die Ortszuordnung) |
| `comparison_engine._fetch_compare_series` | intern | liefert `timeseries` mit `.meta`; läuft über Cache/Single-Flight (#2234) |
| `i18n.t` / Katalog `mail.json` | intern | Nutzertexte nur über den Katalog (DE/EN) |
| `renderer_mail_gate.py` | Tooling | Commit-Gate für Mail-Inhalts-Dateien (Modus-Matrix-Test + Validator frisch grün) |
| `email_spec_validator.py` | Tooling | Validator für `X-GZ-Mail-Type: compare` |

## Implementation Details

**R1 — Datenweg.** `LocationResult` erhält das transiente, additive Feld
`forecast_meta: Optional[ForecastMeta] = None` (Muster wie
`official_alert_query`, `outlook_hourly_data`; kein Persistenzfeld).
`fetch_forecast_for_location` trägt `forecast.meta` in sein Ergebnis-Dict
(`result["forecast_meta"]`), und der `LocationResult`-Bau in
`comparison_engine.py` reicht es durch. Bestehende Aufrufer (Fehlerorte,
`comparison_parallel.py`, `validator_render_service.py`,
`dict_to_comparison_result`) bleiben durch den Default `None` unverändert
gültig. Ein Cache-Treffer von `_fetch_compare_series` muss dasselbe `meta`
liefern wie ein frischer Abruf; ist das nicht der Fall, ist das ein Befund,
der in Phase 4 per RED-Test festgestellt und im selben Zug behoben wird (nicht
still hingenommen).

**R2 — Formulierung nur über das geteilte Modul.** Neue dünne Mehrort-Hülle in
`src/output/renderers/fallback_notice.py`:

```
def build_compare_fallback_lines(location_results, *, lang: Lang = "de") -> list[str]:
    """Je betroffenem Ort die Zeilen aus build_fallback_lines(meta, lang=),
    mit dem Ortsnamen vorangestellt. [] wenn kein Ort betroffen."""
```

Sie ruft pro Ort ausschließlich `build_fallback_lines` (Wortlaut, Übersetzungs-
tabellen, Kollisions- und Rohwertregeln R1–R11 aus S2b bleiben unverändert).
Orte mit `error` und Orte ohne Markierung (`forecast_meta is None` oder
`build_fallback_lines` leer) liefern keine Zeile. Reihenfolge = Reihenfolge der
Vergleichstabelle. Das Modul bleibt neutral benannt (kein `compare_`-Präfix für
eine Neuanlage; `pendant_gate.py` unberührt, da es eine Funktion im
bestehenden Modul ist).

**R3 — Katalog.** Ein Muster `mail.fallback.compare_zeile`
(DE: `„{ort}: {text}"`, EN: `"{ort}: {text}"`) in `mail.json` beider Sprachen;
keine hartkodierten Nutzertexte. Ortsnamen sind Eigennamen und werden nicht
übersetzt. Falls eine Überschrift nötig wird, ebenfalls nur über den Katalog.

**R4 — Darstellung.** Ein Hinweisblock **unter der Vergleichstabelle**, je
betroffenem Ort eine Zeile (bzw. zwei bei Gewitter+Wetter-Kollision, wie in
S2b) mit Ortsname. Ohne betroffenen Ort gibt es **gar keinen Block**: weder
leeres `<div>` noch Leerzeile noch Überschrift; die Mail ist im Normalfall
**byte-identisch** zu vorher. Der feste Footer
(`build_origin_footer("compare", source="Open-Meteo", lang=lang)`) bleibt
unverändert.

**R5 — Verpackung je Kanal.**

- **E-Mail HTML** (`render_compare_html`): `<div>` je Zeile im Hinweisblock unter
  der Tabelle, Stil analog zum `fallback_row` aus dem Trip-Footer, kontrastreich
  (WCAG-AA, Design-Leitprinzip).
- **E-Mail Klartext** (`render_comparison_text`): je Zeile eine Textzeile unter
  der Tabelle.
- **Telegram Compare-Langform** (`render_compare_telegram`): dieselben Zeilen als
  eigene Zeilen unter dem Vergleichsinhalt; Umbruch nach dem bestehenden
  `_wrap`-Muster, falls nötig.
- Klartext und Telegram zeigen **nie** `Fallback`, `icon_eu`, `eu_direct` oder
  andere Rohkennungen (außer dem R7-Rohwert-Fall unbekannter Kennungen aus S2b).

**R6 — Umfang der Aufrufer.** Nur die **Briefing-Compare-Mail** (Versandpfade
von `notification_service.py` / `scheduler_dispatch_service.py` über
`render_comparison_text/_html`) trägt den Hinweis. Alarm- und Vorschau-Pfade
(`compare_official_alert.py`, `compare_alert_preview_service.py`) bekommen ihn
nicht; sie übergeben die Daten nicht an die Hinweis-Funktion oder aktivieren
den Block nicht (Parameter-/Aufrufweise legt die Implementierung fest, das
Verhalten ist in AC-8 festgeschrieben).

**R7 — Mandantentrennung.** Kein neuer Nutzerdaten-Endpoint; `user_id` kommt
unverändert aus dem bestehenden Pfad. Der Hinweis stammt ausschließlich aus
dem Abruf des jeweiligen Orts desselben Nutzers; Tests laufen dennoch mit zwei
verschiedenen Nutzern und zwei Orten (siehe Test-Plan).

## Kanäle

| Kanal | Verhalten in dieser Scheibe |
|-------|----------------------------|
| E-Mail (HTML + Klartext) | Hinweisblock mit Ortsnamen unter der Vergleichstabelle (AC-1, AC-2) |
| Telegram (Compare-Langform) | Dieselben Zeilen (AC-3) |
| SMS (<=160 Zeichen) | bewusst **kein** Hinweis (siehe Known Limitations) |
| Premium-SMS (inReach, <=160 Zeichen) | bewusst **kein** Hinweis (siehe Known Limitations) |

Gleicher Inhalt, kanalgerechte Form in den drei Ausgaben HTML / Klartext /
Telegram-Langform; SMS und Premium-SMS sind eine **benannte Paritätslücke**
(ADR-0095), keine stille.

## Expected Behavior

- **Input:** Ein Ortsvergleich mit n Orten; je Ort trägt `forecast_meta`
  (a) keine, (b) eine Gewitter-, (c) eine Grundvorhersage- oder (d) beide
  Vertretungen oder ist `None` (Fehlerort).
- **Output:** Kein betroffener Ort: Ausgabe unverändert (Byte-Identität).
  Sonst ein Hinweisblock mit je einer Zeile `<Ort>: <Klartext aus
  build_fallback_lines>` für genau die betroffenen Orte.
- **Side effects:** keine; kein zusätzlicher Abruf, keine Persistenz.

## Test Plan

Testdateien nach Verhalten benannt (nicht nach Issue-Nummer). Echte Objekte
(`LocationResult`, `ComparisonResult`, `ForecastMeta`, echte Renderer-Aufrufe),
**kein Mock-Theater**, kein Dateiinhalt-Check.

- [ ] Engine trägt `forecast_meta`: echter `fetch_forecast_for_location` mit
  einer Zeitreihe, deren `meta` eine Vertretung trägt, liefert ein
  `LocationResult` mit demselben `forecast_meta`; dasselbe über einen
  **Cache-Treffer** (zweiter Abruf desselben Orts).
- [ ] `build_compare_fallback_lines`: zwei Orte, nur einer betroffen -> genau
  die Zeile(n) dieses Orts mit seinem Namen; beide betroffen; Kollisionsfall
  (zwei Zeilen); Fehlerort mit gesetztem `forecast_meta` -> keine Zeile; alle
  `None` -> `[]`; EN-Sprache -> englischer Katalogtext.
- [ ] HTML / Klartext / Telegram mit Vertretung bei einem von zwei Orten:
  Ortsname und Klartext vorhanden, **kein** `Fallback` / `icon_eu` / `eu_direct`.
- [ ] **Byte-Identität im Normalfall:** dieselbe Eingabe ohne Vertretung vor und
  nach der Änderung, für HTML, Klartext und Telegram gerendert, ergibt
  identische Ausgabe (Golden aus dem Stand vor der Änderung bzw. vorhandene
  Compare-Goldens müssen unverändert grün bleiben).
- [ ] Kein leerer Rahmen: ohne Vertretung kein leeres Hinweis-`<div>`, keine
  Leerzeile, keine Überschrift.
- [ ] **Zwei Nutzer / zwei Orte:** zwei Vergleiche zweier Nutzer mit je
  unterschiedlichem betroffenem Ort; der Hinweis des einen erscheint nie in der
  Ausgabe des anderen.
- [ ] Alarm- und Vorschau-Compare-Ausgabe bleibt ohne Hinweis, auch bei
  gesetztem `forecast_meta`.
- [ ] SMS-/Premium-SMS-Compare-Ausgabe für dasselbe Ergebnis: kein Hinweistext,
  Länge <= 160 Zeichen (Verhaltensnachweis am erzeugten Text).
- [ ] Mutations-Gegenprobe (Adversary): Ortsname entfernen, Fehlerorte nicht
  mehr überspringen, Block im Normalfall erzeugen, `forecast_meta` im
  Cache-Pfad verwerfen -> jeweils muss ein Test rot werden.

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleich mit zwei Orten, bei dem nur der zweite Ort
  durch eine Ersatzquelle vertreten wurde, When die Vergleichs-Mail als HTML
  gerendert wird, Then steht unter der Vergleichstabelle genau eine
  Hinweiszeile mit dem Namen des zweiten Orts und dem Klartext aus
  `build_fallback_lines`, und der erste Ort wird nicht genannt.

- **AC-2:** Given derselbe Ortsvergleich, When die Klartext-Variante der
  Vergleichs-Mail gerendert wird, Then enthält sie dieselbe Hinweiszeile mit
  Ortsnamen unter der Tabelle, und weder `Fallback` noch `icon_eu` noch
  `eu_direct` kommen irgendwo im Text vor.

- **AC-3:** Given derselbe Ortsvergleich, When die Telegram-Compare-Langform
  gerendert wird, Then erscheint dieselbe Hinweiszeile mit Ortsnamen und dem
  gleichen Klartext-Kern wie in Mail-HTML und Klartext, ohne Rohkennungen.

- **AC-4:** Given ein Ortsvergleich ohne jede Vertretung (Normalfall), When
  HTML, Klartext und Telegram gerendert werden, Then ist jede Ausgabe
  byte-identisch zu der vor dieser Änderung und enthält keinen Hinweisblock,
  kein leeres Element und keine Überschrift.

- **AC-5:** Given ein Ortsvergleich, in dem ein Ort einen Abruffehler hat und
  die übrigen Orte keine Vertretung, When die Ausgaben gerendert werden, Then
  erscheint der Fehlerort nicht im Hinweisblock und es entsteht kein
  Hinweisblock.

- **AC-6:** Given ein Ort mit gleichzeitiger Gewitter- und
  Grundvorhersage-Vertretung (Kollisionsfall), When die Mail gerendert wird,
  Then stehen zwei Zeilen mit demselben Ortsnamen, und die Gewitterzeile nennt
  wie im Trip-Pfad keinen Quellennamen.

- **AC-7:** Given ein Nutzer mit Sprache Englisch, When der Hinweisblock
  gerendert wird, Then stammen Muster und Texte aus dem Englisch-Katalog, der
  Ortsname bleibt unübersetzt, und es gibt keinen hartkodierten deutschen Text.

- **AC-8:** Given ein Ortsvergleich mit Vertretung, When statt der Briefing-Mail
  eine Alarm- oder Vorschau-Compare-Ausgabe gerendert wird, Then enthält diese
  keinen Vertretungshinweis, während die Briefing-Mail ihn enthält.

- **AC-9:** Given ein Ort wurde über den Cache (zweiter Abruf desselben Orts)
  statt per frischem Abruf geladen, When das Vergleichsergebnis gebaut wird,
  Then trägt das `LocationResult` dasselbe `forecast_meta` wie beim frischen
  Abruf, sodass der Hinweis auch bei Cache-Treffern erscheint.

- **AC-10:** Given zwei verschiedene Nutzer mit je eigenem Ortsvergleich und
  jeweils einem anderen betroffenen Ort, When beide Mails gerendert werden,
  Then enthält jede Mail ausschließlich den Hinweis des eigenen betroffenen
  Orts und nie den des anderen Nutzers.

- **AC-11:** Given ein Ortsvergleich mit Vertretung, When die SMS- und die
  Premium-SMS-Ausgabe gerendert werden, Then enthalten sie keinen
  Vertretungshinweis und bleiben innerhalb von 160 Zeichen.

## Known Limitations

- **SMS und Premium-SMS ohne Hinweis (ADR-0095-Paritätslücke, bewusst).** Beide
  Kanäle sind auf 160 Zeichen begrenzt; ein Klartext-Hinweis je Ort würde das
  Budget für die Wetteraussage sprengen. Das entspricht der Linie von Trip S2b
  (AC-7 dort). Die Lücke ist benannt, nicht unsichtbar: Wer nur diese Kanäle
  nutzt, erfährt von einer Vertretung nicht. Ein SMS-tauglicher Kurzhinweis
  (z. B. Token) wäre eine eigene Produktentscheidung samt Protokoll-Token-Regel
  und kommt nur als eigene Scheibe.
- **Alarm- und Vorschau-Compare-Mails ohne Hinweis.** Nur die Briefing-Compare-Mail
  trägt ihn (Rauschen in Warnmails, wie bei Trip S2b).
- **Telegram-Kurzform des Ortsvergleichs** (sofern sie `sms_text` sendet) bleibt
  ohne Hinweis aus demselben Grund wie die SMS.
- **Keine Markierung in der Tabellenspalte selbst.** Die Zuordnung erfolgt
  namentlich im Hinweisblock, nicht per Symbol in der Spalte (Entscheidung:
  dort steckt die Information vollständig, ohne die Tabelle zu verändern).
- **Validierung auf Staging begrenzt.** Eine Vertretung lässt sich auf Staging
  in der Regel nicht erzwingen. Der Nachweis der Vertretungszeile erfolgt auf
  Datenweg- und Renderer-Ebene (echte Objekte, echte Renderer-Aufrufe); die
  echt zugestellte Staging-Mail belegt per Validator nur den Normalfall
  (Byte-Identität/keine Regression). Dass diese Grenze besteht, wird im
  Validierungsbericht ehrlich benannt und nicht als End-to-End-Beleg der
  Vertretungszeile ausgegeben.
- **Etappen-/Zeitraum-Granularität.** Der Hinweis sagt „bei diesem Ort wurde
  ausgewichen", nicht an welchem Tag oder in welcher Stunde (wie Trip S2b).
- **Übersetzungstabellen** (Quellen/Metriken) bleiben die aus S2b, mit denselben
  dort dokumentierten Grenzen (R7 Rohwert-Anzeige, keine mechanische Kopplung an
  den Metrik-Katalog).

## Validierung

**Renderer-Commit-Gate (un-überspringbar).** Die Scheibe berührt
Mail-Inhalts-Dateien (`email/compare_html.py`, `comparison.py`). Vor dem Commit:
Modus-Matrix-Test frisch grün und ein erfolgreicher Lauf von
`uv run python3 .claude/hooks/email_spec_validator.py` gegen eine **echt
zugestellte** Staging-Compare-Mail (Marker `X-GZ-Mail-Type: compare`, >=3 Orte;
**nicht** der Briefing-Validator). „E2E bestanden" nur bei Exit 0. Wegen der
Staging-Grenze (siehe Known Limitations) belegt der Validator den Normalfall;
die Vertretungszeile wird durch die Verhaltenstests des Test-Plans belegt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Anwendung bestehender Invarianten (ADR-0018, ADR-0047) auf die
  Compare-Ausgabe; die Mehrort-Darstellung ist eine Darstellungsentscheidung im
  Rahmen der Trip/Compare-Teilung (Formulierung geteilt, nur die Zuordnung zum
  Ort ist compare-eigen). Die SMS-Lücke folgt der bestehenden S2b-Linie.

## Changelog

- 2026-11-04: Initial spec created (Issue #1563, Kontext
  `docs/context/feat-1563-compare-vertretungshinweis.md`; Darstellung
  namentlich je Ort, Telegram-Langform im Umfang, SMS/Premium-SMS als benannte
  Paritätslücke).
