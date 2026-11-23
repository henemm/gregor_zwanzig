---
entity_id: fix_3273_trip_grundauswahl_ohne_metrics
type: bugfix
created: 2026-11-23
updated: 2026-11-23
status: draft
version: "1.0"
workflow: fix-3273-trip-grundauswahl-ohne-metrics
tags: [validator, soll, trip, grundauswahl, profil, "#3273", "#3122"]
---

# Validator-Soll (--konfig): Trip-Grundauswahl ohne gespeicherte metrics (Bug #3273)

## Approval

- [ ] Approved

## Purpose

Das Soll der Mail-Validatoren (`--konfig`) leitet für einen Trip ohne gespeicherte `display_config.metrics`, aber mit Tabelle (`placements`), eine andere Grundauswahl ab als das Produkt: Der Validator nimmt den Register-Standard (z. B. Gewitter, Nullgradgrenze, Sicht), das Produkt das Profil des Trips (z. B. Sonne, Regenwahrscheinlichkeit). Folge sind Fehlalarme der Mail-Prüfung bei korrekt gerenderter Mail. Das Soll folgt künftig der Produktregel des Loaders (#3122 B2b). Pendant zu #3242 AC-9 (Orte); Teil von Epic #3122. Nur das Prüfwerkzeug ist betroffen, keine Nutzer-Mail.

## Source

- **File:** `.claude/hooks/_soll_aus_konfiguration.py`
- **Identifier:** `_trip_display_config` (Fallunterscheidung), Aufrufer `trip_soll`, `_mit_grundauswahl_tabelle`

> Schicht: Prüfwerkzeug (`.claude/hooks/`), weder Frontend noch Go-API noch Produktcode. Nutzerdaten werden nur gelesen. Alle vier Kanäle unberührt (nur E-Mail-Prüfung).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.metric_catalog.WEATHER_TEMPLATES` | Datentabelle | Profil-Vorlagen (Rückfall `allgemein`) |
| `app.loader._OLD_METRIC_MAP` | Datentabelle | Altnamen der `weather_config` auf Katalog-IDs |
| `app.metric_catalog` Register (`get_all_metrics`, `trip_default_rank`) | Register | Register-Folge und Register-Standard |
| `src/app/loader.py` (611-631, `_nur_placements`, `trip_standard_bei_leer`) | Produktregel | Maßgebliche Regel, nur zum Gleichlauf-Test geladen |
| `briefing_mail_validator.py`, `email_spec_validator.py` | Verbraucher | Lesen das Soll (`--konfig`) |
| `docs/specs/modules/fix_3242_validator_soll_auswahl.md` | Spec | Vorbild, Spiegel-Verbot, AC-9 Orte |
| `docs/specs/modules/feat_3122_was_steht_wo.md` | Spec | Produktregel der Tabelle |

## Implementation Details

`_trip_display_config(trip)` unterscheidet nach der Loader-Regel anhand der rohen Trip-Hülle (Trip-JSON trägt `stages` oder `id`):

1. **`display_config`-Schlüssel vorhanden und nicht nur `{placements}`** (auch `null`): wie bisher. `metrics` fehlt oder `[]` ergibt den Register-Standard, sonst die gespeicherte Liste.
2. **`display_config` fehlt oder besteht nur aus `placements`:**
   - `weather_config` vorhanden: Altnamen über `_OLD_METRIC_MAP` auf Katalog-IDs; eingeschaltete Größen.
   - sonst Profil `aggregation.profile` (fehlend, `null` oder unbekannt ergibt `allgemein`) über `WEATHER_TEMPLATES` (Rückfall `allgemein`); eingeschaltete Größen.
   - Die Einträge entstehen in Register-Folge mit explizitem `order` (Register-Index, `bucket: primary`), **nicht** über `_altformat_folge` (dessen Register-Priorität weicht bei allen vier Profilen von der Produktfolge ab; in der Analyse gemessen). `placements` bleibt erhalten.
3. **Nackte `display_config` ohne Trip-Hülle:** bisheriges Verhalten (Profil nicht erkennbar).

**Spiegel-Verbot (wie #3242, ADR-0127 Nr. 5):** Profil-Vorlagen und Altnamen-Zuordnung stehen von Hand abgeschrieben im Validator (kein Import von `WEATHER_TEMPLATES`/`_OLD_METRIC_MAP`, Ratsche ADR-0127 Nr. 4); Drift fängt der Gleichlauf-Test AC-8 gegen den echten Loader. Kein Aufruf von `resolve_rows`, `resolve_channel_lists`, `placements_view`, `_cell`, `metrics_at`, `build_default_display_config_for_profile`, `tabellen_grundauswahl` oder `grundauswahl` im neuen Pfad; sonst fände der Validator Fehler der Produktregel nie.

## Expected Behavior

- **Input:** Trip-JSON ohne bzw. mit rein tabellarischer `display_config`, mit oder ohne `weather_config`, mit beliebigem Profil.
- **Output:** Soll-Grundauswahl gleich der Grundauswahl des über den echten Loader geladenen Trips.
- **Side effects:** keine.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/hooks/_soll_aus_konfiguration.py` | MODIFY | `_trip_display_config`: Fall 2 (Profil / `weather_config`) nach Loader-Regel |
| `tests/tdd/test_3273_trip_grundauswahl_ohne_metrics.py` | CREATE | Soll-Tests mit von Hand notierten Listen, Gleichlauf-Test mit echt geladenem Trip, doc-compliance-test |
| `docs/specs/modules/fix_3273_trip_grundauswahl_ohne_metrics.md` | CREATE | Diese Spec |

## Estimated Scope

- **LoC:** +40/-3 Code, Tests ca. +200
- **Files:** 3
- **Effort:** low

## Definition of Done

- AC-1 bis AC-10 durch Kern-Tests ohne Mock grün; Bestandstests der Soll-Module (`tests/tdd/test_einstellung_gleich_mail_*.py`, `tests/test_3047_*`) unverändert grün.
- Keine Änderung an Gate-Konfiguration; kein Schritt, der eine Sperre (override) braucht.

## Test Plan

### Automated Tests (TDD RED)

Datei `tests/tdd/test_3273_trip_grundauswahl_ohne_metrics.py`, ohne `Mock`/`patch`; Eingabe ist rohes Trip-JSON, die erwartete Liste steht von Hand im Test und wird nie aus `resolve_*` berechnet.

- [ ] GIVEN Profil allgemein, `display_config` nur `placements` (umgekehrte Folge, E-Mail der 2. Zeile aus) WHEN Soll THEN Produkt-Spalten (Temperatur, Nachttemperatur, Wind, Böen, Niederschlag, Regenwahrscheinlichkeit, Bewölkung, Sonne) in Register-Folge, Tabelle erhalten
- [ ] GIVEN `display_config` fehlt WHEN Soll THEN Profil-Grundauswahl
- [ ] GIVEN `weather_config` mit Altnamen, `display_config` fehlt/nur placements WHEN Soll THEN über `_OLD_METRIC_MAP` abgeleitete Größen
- [ ] GIVEN unbekanntes/fehlendes/`null` Profil WHEN Soll THEN Profil `allgemein`
- [ ] GIVEN `display_config: null` oder weitere Schlüssel ohne `metrics` WHEN Soll THEN Register-Standard
- [ ] GIVEN nackte `display_config` WHEN Soll THEN bisheriges Verhalten
- [ ] GIVEN alle Profile und Varianten WHEN Soll und echter Loader THEN gleiche Grundauswahl
- [ ] Quelltext-Kontrolle des neuen Pfads gegen `resolve_*` als `# doc-compliance-test`

## Acceptance Criteria

- **AC-1:** Given ein Trip mit Profil allgemein, `display_config` nur mit `placements` (umgekehrte Folge, E-Mail der zweiten Zeile aus) und ohne `metrics` / When das Soll abgeleitet wird / Then entspricht die Grundauswahl den Spalten des Produkts (Profil allgemein) und nicht dem Register-Standard.
  - Test: Rohes Trip-JSON des Befundfalls aus dem Issue; die von Hand notierte Spaltenliste enthält Sonne und Regenwahrscheinlichkeit, nicht Gewitter, Nullgradgrenze, Sicht.

- **AC-2:** Given ein Trip ganz ohne `display_config` und ohne `weather_config` mit Profil / When das Soll abgeleitet wird / Then ist die Grundauswahl die Vorlage dieses Profils in Register-Folge.
  - Test: Je Profil von Hand notierte Größenliste; das Soll stimmt in Auswahl und Folge überein.

- **AC-3:** Given ein Trip mit `weather_config` (Altnamen) und fehlender oder nur tabellarischer `display_config` / When das Soll abgeleitet wird / Then ergeben die eingeschalteten Altnamen über die Altnamen-Zuordnung die Grundauswahl in Register-Folge, nicht das Profil.
  - Test: `weather_config` mit gemischt ein- und ausgeschalteten Altnamen; erwartete Liste von Hand notiert.

- **AC-4:** Given ein Trip mit fehlendem, `null` oder unbekanntem Profil und ohne `weather_config` / When das Soll abgeleitet wird / Then gilt das Profil allgemein.
  - Test: Drei Eingaben liefern dieselbe Liste wie Profil allgemein.

- **AC-5:** Given ein Trip mit `display_config: null` oder mit weiteren Schlüsseln neben `placements` und ohne `metrics` / When das Soll abgeleitet wird / Then bleibt es beim Register-Standard wie bisher.
  - Test: Beide Eingaben ergeben die Register-Standard-Liste (Temperatur, Wind, Böen, Niederschlag, Gewitter, Nullgradgrenze, Sicht, Tag-Tiefst-/Höchsttemperatur).

- **AC-6:** Given eine nackte `display_config` ohne Trip-Hülle / When das Soll abgeleitet wird / Then ist das Verhalten unverändert zu vorher.
  - Test: Nackte `display_config` ohne `metrics` ergibt den Register-Standard, mit `metrics` die gespeicherte Liste.

- **AC-7:** Given Trips mit nur `placements` in `display_config` / When das Soll abgeleitet wird / Then bleibt die Tabelle `placements` im Soll unverändert erhalten und wirkt wie bisher auf Auswahl und Reihenfolge.
  - Test: Soll enthält dieselbe `placements`-Tabelle wie die Eingabe.

- **AC-8:** Given alle vier Profile und die Varianten (fehlend, nur placements, `null`, mit `weather_config`) / When der Trip einmal über den echten Loader geladen und einmal im Soll abgeleitet wird / Then ist die Grundauswahl im Soll gleich der Grundauswahl des geladenen Trips.
  - Test: Gleichlauf-Test mit echtem Loader, ohne Mock; Vergleich von Größen und Folge.

- **AC-9:** Given die bestehenden Soll-Tests (`test_einstellung_gleich_mail_*`, `test_3047_*`, #3218, #3242) / When sie nach der Änderung laufen / Then bleiben alle unverändert grün.
  - Test: Bestandstests ohne Anpassung ausführen.

- **AC-10:** Given der neue Pfad im Soll / When der Quelltext geprüft wird / Then enthält er keinen Aufruf von `resolve_rows`, `resolve_channel_lists`, `placements_view`, `_cell`, `metrics_at`, `build_default_display_config_for_profile`, `tabellen_grundauswahl` oder `grundauswahl`.
  - Test: Als `# doc-compliance-test` gekennzeichnet; ergänzend beweisen AC-1 bis AC-3, dass die Erwartung von Hand notiert ist.

## Known Limitations

- Eine nackte `display_config` ohne Trip-Hülle kennt das Profil nicht und behält das bisherige Verhalten.
- Altfelder und Altpfad bleiben bis #3237 bestehen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Fehlerbehebung im Prüfwerkzeug nach bestehender Produktregel (#3122 B2b, ADR-0124); keine neue Entscheidungsfläche. Gewählt: Datentabellen als Quelle statt Produktfunktion (Spiegel-Verbot wie #3242), damit Fehler der Produktregel auffallen.

## Changelog

- 2026-11-23: Initial spec created (Issue #3273)
- 2026-11-23: Tech-Lead-Präzisierung im Fix-Loop: Vorlagen und Altnamen von Hand abgeschrieben statt importiert (ADR-0127 Nr. 4/5, Ratsche), Verhalten und ACs unverändert.
