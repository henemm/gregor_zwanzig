# Spec: Ortsvergleich B — Schneehöhe als konfigurierbare Metrik (#1105)

- **Status:** Draft (Freigabe ausstehend)
- **created:** 2026-07-08
- **Issue:** #1105 (Teil B von #1094)
- **Workflow:** fix-1105-compare-metrics-snow

## Problem

Seit dem v2-Layout (#1110) ist der Metrik-Katalog der Ortsvergleich-Mail auf sechs Zeilen
festgelegt (`CV2_METRICS`: Warnungen, Temp, Wind, Sonne, Wolken, UV). **Schneehöhe fehlt
komplett** — obwohl das Datenmodell (`LocationResult.snow_depth_cm/snow_new_cm`), der
Metrik-Resolver (#1104) und der Frontend-Editor sie tragen. Dadurch kann der Nutzer
Schneehöhe im Editor zwar auswählen, sie erscheint aber nie in der Mail und ist folglich
auch nicht abwählbar. Die Resolver-Kette (Editor → `compare_presets.json` →
`resolve_enabled_metrics` → `_visible_metrics`) ist bereits verdrahtet; es fehlt nur der
Katalog-Eintrag.

## Ziel

Schneehöhe (und Neuschnee) werden **reguläre Metriken ohne Sonderrolle** (PO-Entscheid
2026-07-08): im Default sichtbar wie jede andere Metrik, per Editor-Auswahl abwählbar,
gefiltert über denselben `enabled_metrics`-Mechanismus.

## Scope

- **IN:** Schnee-Einträge im v2-Renderer-Katalog (HTML + Plain-Text), sodass die
  bestehende Filter-/Resolver-Kette sie wie jede andere Metrik behandelt.
- **OUT:** Subscription-Versandpfad (`compare_subscription.py`) — separater Mechanismus,
  Folge-Issue. `top_n_details`/„Anzahl Orte"-Semantik (bleibt #1106/#1107).
  Winner/Score (in v2 entfernt).

## Acceptance Criteria

**AC-1:** Given ein Ortsvergleich mit ≥2 Orten und **ohne** konfigurierte Metrik-Teilmenge
(`enabled_metrics` = None / leer), When die Compare-Mail gerendert wird, Then enthält die
Übersichtstabelle sowohl eine „Schneehöhe"-Zeile als auch eine „Neuschnee"-Zeile —
sichtbar im Default wie alle anderen numerischen Metriken.

**AC-2:** Given ein Ortsvergleich, dessen Editor-Auswahl die Schneehöhe **nicht** enthält
(z. B. nur Temp + Wind aktiviert), When die echt zugestellte Staging-Compare-Mail
gerendert wird, Then erscheint **keine** Schnee-Zeile in der Übersichtstabelle, während
die gewählten Zeilen (Temp, Wind) und die immer sichtbare Warn-Zeile vorhanden sind.

**AC-3:** Given ein Ortsvergleich, dessen Editor-Auswahl die Schneehöhe **enthält**, When
die Mail gerendert wird, Then erscheint die „Schneehöhe"-Zeile mit je Ort einer Zelle, die
den Wert in Einheit „cm" zeigt bzw. „—" wenn für den Ort kein Schnee-Wert vorliegt.

**AC-4:** Given ein Ort mit befülltem `snow_depth_cm`, When die HTML- **und** die
Plain-Text-Variante der Mail gerendert werden, Then zeigen beide die Schnee-Zeile
konsistent (HTML-Zelle und Plain-Text-Zeile), ohne Risiko-/Schwellen-Färbung (reine
Datenzeile, keine `sev`-Logik).

## Non-Goals / Invarianten

- Warn-Zeile bleibt unabhängig von `enabled_metrics` **immer** sichtbar (unverändert).
- Reihenfolge und Rendering der bestehenden fünf numerischen Metriken bleiben unverändert.
- Keine Änderung an Resolver (`compare_metric_ids.py`) oder Filter (`_visible_metrics`) —
  sie greifen automatisch, sobald die Snow-Keys im Katalog stehen.
- Kein Winner/Score, kein Best-Value-Highlight (v2-Invariante aus #1110).

## Technischer Ansatz

1. `CV2_METRICS` (`compare_html.py`) um zwei Einträge erweitern:
   `{"key": "snow_depth_cm", "label": "Schneehöhe", "unit": "cm"}` und
   `{"key": "snow_new_cm", "label": "Neuschnee", "unit": "cm"}`. Keys = Resolver-Ziel-IDs.
2. `_metric_value` bleibt unverändert (`getattr` deckt beide Attribute ab).
3. Plain-Text-Übersicht (`comparison.py`) analog um die Schnee-Zeilen erweitern.

## Verifikation

- Rote Tests (`tests/tdd/test_issue_1105_compare_snow_metric.py`) für AC-1…AC-4 gegen den
  echten Renderer (kein Mock).
- #811-Mode-Matrix grün + Compare-Mail-Validator (`email_spec_validator.py`,
  `X-GZ-Mail-Type: compare`) gegen echt zugestellte Staging-Mail (Gate-Pflicht bei
  Mail-Renderer-Edit).
