---
entity_id: feat_3039_vergleich_kanal_layouts
type: feature
created: 2026-11-15
updated: 2026-11-15
status: draft
version: "1.0"
workflow: feat-3039-vergleich-kanal-layouts
tags: [vergleich, kanaele, channel_layouts, renderer, adr-0050, adr-0095]
---

> **Hinweis (2026-11-17, [ADR-0124](../../adr/0124-was-steht-wo-eine-tabelle.md), Issue #3122):** Diese Spec ist gebaut (`channel_layouts` der Orte) und gilt bis zum Bau zu #3122. Die Frontend-Karte #3031 (PR #3042), für die sie der Vorlauf war, wird so nicht gebaut. ADR-0124 ersetzt „eigene Liste je Kanal“ durch **eine** Tabelle „Was steht wo“ mit einer Reihenfolge für alle Stellen; das gespeicherte Format wird dann neu geschnitten, Bestandsdaten bleiben per Read-Modify-Write mit Merge erhalten. ACs unverändert.

# Ortsvergleich: Aus und Roh/Einfach je Kanal (channel_layouts)

## Approval

- [ ] Approved

## Purpose

Der Ortsvergleich bekommt, wie der Trip, je Kanal (E-Mail, Telegram, SMS) eine eigene geordnete Liste seiner Werte mit den Einstellungen "ein/aus" und "Roh/Einfach". Damit kann der Nutzer z. B. Böen in Telegram als Zahl und in der Mail als Wort/Ampel zeigen. Vorlauf für die Frontend-Karte #3031 (Teil von #2795, Epic #2791); Premium-SMS folgt dem SMS-Text.

## Source

- **File:** `src/services/report_config_resolver.py`
- **Identifier:** `CompareRenderOptions`, `resolve_compare_render_options`

> **Schicht:** Python-Core (`src/services/`, `src/output/renderers/`) plus eine kleine Frontend-Korrektur (`compareEditorSave.ts`). **Keine Go-Änderung:** `display_config` ist dort ein opakes Objekt, der Merge ersetzt `channel_layouts` als Ganzes.
> **Trip/Vergleich-Teilung:** Das Trip-Pendant (`channel_layouts` am Trip, `_resolve_format_mode`, `fmt_val`) wird wiederverwendet, nicht neu gebaut; Vergleichs-eigen sind nur Zeilenschlüssel-Expansion und die Standardregel "ohne Angabe = Roh".
> **Mandantentrennung:** Es werden keine Nutzerdaten bewegt (Speichern ist Go, unverändert); Renderer-Tests laufen je Nutzer-Preset mit zwei Nutzern.
> **Kanäle:** E-Mail, Telegram, SMS, Premium-SMS (folgt dem SMS-Text über `notification_service`) sind benannt.

## Estimated Scope

- **LoC:** Quelle ca. +400/-60, Tests ca. +250
- **Files:** ca. 12 Quell-/Doku-Dateien plus Tests
- **Effort:** medium (Risiko MEDIUM: gemeinsamer Resolver für Versand und Vorschau)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/metric_catalog.py` (`format_modes`, `SMS_FORMAT_MODE_METRIC_IDS`) | module | Welche Metrik mehr als eine Darstellung hat; Wolken-Metriken für SMS-Einfach |
| `src/output/renderers/email/helpers.py` (`fmt_val`, `build_format_modes`) | module | Einfachform (Wort/Ampel/Symbol) wie beim Trip |
| `src/output/renderers/compare_metric_ids.py` (`key_for`, `resolve_channel_enabled_metrics`) | module | Kennung → Vergleichs-Zeilenschlüssel, Schnitt mit Grundauswahl |
| `src/output/renderers/compare_outlook_metric_ids.py` (`derived_aggregations`) | module | Muster für Expansion Kennung → mehrere Zeilen |
| `src/services/scheduler_dispatch_service.py`, `src/services/compare_preview_service.py` | module | Konsumenten: Versand und Vorschau reichen das neue Feld durch |
| `src/services/notification_service.py` | module | Premium-SMS sendet den SMS-Text (keine eigene Änderung) |
| Frontend-Karte #3031 (PR #3042) | feature | Schreibt `channel_layouts` + `channel_active_metrics`; bleibt bis zum Live-Gang dieser Spec gesperrt |
| ADR-0050, ADR-0053, ADR-0095, ADR-0049, ADR-0077 | adr | Teilmengen-Regel, Entfernung #1351, Kanal-Parität, Premium-SMS, Go-Speicherung |

## Implementation Details

Details und Entscheidungen: `docs/context/feat-3039-vergleich-kanal-layouts.md`. Verbindliche Regeln:

1. **Datenform** (am Vergleich, `display_config.channel_layouts`): `{email|telegram|sms: [{metric_id, enabled, use_friendly_format}]}`; Reihenfolge = Listenindex. Einträge tragen Katalog-Kennungen, die Renderer rechnen sie in Vergleichs-Zeilenschlüssel um (z. B. Temperatur → Höchst-/Tiefstwert); das Format der Kennung gilt für alle abgeleiteten Zeilen.
2. **Kaskade je Kanal (Resolver):** `channel_layouts[kanal]` → sonst `channel_active_metrics[kanal]` → sonst Grundauswahl. `enabled_metrics_by_channel` bleibt signaturgleich; neu ist ein additives Feld je Kanal mit geordneten Zeilen samt Format.
3. **Bestand unverändert:** Fehlt `channel_layouts`, liefern die Fallback-Stufen nur Auswahl und Reihenfolge; das Format ist der heutige Festzustand (Renderer-Argument `None`). Der Katalog-Standard greift bei Bestand nie. (Präzisiert Issue-Punkt 2: Der Bestands-AC hat Vorrang.)
4. **Format:** Eintrag ohne `use_friendly_format` = Roh (Präzedenz `outlook_metric_formats`; bewusste Abweichung von `loader._resolve_format_mode`, im ADR festgehalten). Einfach wirkt nur bei Metriken mit mehr als einem `format_mode` (gleiche Regel wie Karten-Spec #3031); sonst wird `true` ignoriert.
5. **Kanäle:** Mail Einfach = Ampelpunkt/Wort/Symbol wie Trip (`fmt_val`), die Zelltönung bleibt; der Klartext-Mailteil zieht dieselbe Zeilenliste samt Format. Telegram nutzt dieselbe Formatstelle, ohne eigene Einfachform bleibt die Zahl. SMS: Einfach nur für `SMS_FORMAT_MODE_METRIC_IDS` (GSM-7-sicher), sonst Roh, höchstens 160 Zeichen. Premium-SMS = SMS-Text. Telegram "kurzform" übernimmt den SMS-Text.
6. **Aus:** `enabled:false` blendet die Zeile nur in diesem Kanal aus. **Teilmengen-Regel ADR-0050:** Kanal-Auswahl ist eine Teilmenge der Grundauswahl; `global_metrics is None` = kein Schnitt; leere Grundauswahl bzw. alle Einträge aus ⇒ Kanal leer (kein Rückfall auf die volle Grundauswahl). In der Rückfallstufe `channel_active_metrics` gilt die heutige Semantik unverändert (leere Liste bleibt leer, `resolve_channel_enabled_metrics`).
7. **Neue Metriken** der Grundauswahl ohne Eintrag in `channel_layouts[kanal]` erscheinen eingeschaltet am Ende (wie #3031 AC-8; "aus" ist in `channel_layouts` immer ein expliziter Eintrag, ein fehlender Eintrag heißt also "neu"). Gilt nur für die Stufe `channel_layouts`, nicht für den Bestand über `channel_active_metrics` (AC-2).
8. **Eine Formatstelle** in `comparison.py` für Telegram, SMS und Klartext-Mail (Parameter `None` = Festzustand); Mail-HTML formatiert je Zeile in `compare_html.py`. Versand und Vorschau nutzen denselben Resolver.
9. **Altlast #1351 entfernen:** `compareEditorSave.ts` löscht `channel_layouts` nicht mehr; Migrationsskript `scripts/migrate_1351_drop_compare_channel_layouts.py` samt `tests/test_compare_channel_layouts_migration.py` entfällt (darf nie wieder laufen).
10. **Doku:** neues ADR-0119 (auf main frei, geprüft 2026-11-15) löst den ADR-0053-Teil "Entfernung channel_layouts (#1351)" ab; ADR-0053 und `docs/adr/README.md` bekommen "Abgelöst durch". `docs/reference/api_contract.md` §16 dokumentiert `channel_layouts` (Vergleich) und das bislang undokumentierte `channel_active_metrics`.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/report_config_resolver.py` | MODIFY | `CompareRenderOptions` um geordnete Zeilen je Kanal erweitern; Kaskade |
| `src/output/renderers/compare_metric_ids.py` | MODIFY | Kennung → Zeilenschlüssel-Expansion, Format je Zeile, Schnitt mit Grundauswahl |
| `src/output/renderers/comparison.py` | MODIFY | Eine Formatstelle für Telegram, SMS, Klartext-Mail |
| `src/output/renderers/email/compare_html.py` | MODIFY | Format je Zeile, Einfach über `fmt_val` |
| `src/services/scheduler_dispatch_service.py` | MODIFY | Neues Feld an Renderer durchreichen |
| `src/services/compare_preview_service.py` | MODIFY | Dito (Versand = Vorschau) |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | MODIFY | Löschen von `channel_layouts` entfällt |
| `scripts/migrate_1351_drop_compare_channel_layouts.py` | DELETE | Migration darf nie wieder laufen |
| `tests/test_compare_channel_layouts_migration.py` | DELETE | Test der entfernten Migration |
| `docs/adr/0119-vergleich-channel-layouts.md` | CREATE | Neues ADR |
| `docs/adr/0053-*.md`, `docs/adr/README.md` | MODIFY | "Abgelöst durch" |
| `docs/reference/api_contract.md` | MODIFY | §16 ergänzen |
| `tests/` (Resolver, Kaskade, Renderer je Kanal, Golden, GSM-7, Premium-SMS, Vorschau, Zwei-Nutzer) | CREATE/MODIFY | Ausgabe je Kanal prüfen |

### Estimated Changes
- Files: ca. 12 plus Tests
- LoC: +650/-60 inklusive Tests

## Test Plan

### Automated Tests (TDD RED)
- [ ] GIVEN Vergleich mit Böen Roh für Telegram und Einfach für E-Mail WHEN Telegram und Mail gerendert werden THEN Telegram zeigt die Zahl, Mail das Einfach-Zeichen
- [ ] GIVEN Bestandsvergleich nur mit `channel_active_metrics` WHEN gerendert wird THEN Ausgabe bit-identisch zu `tests/golden/vergleichs_mail/*` und zu den Telegram-/SMS-Referenzen
- [ ] GIVEN weder `channel_layouts` noch `channel_active_metrics` WHEN gerendert wird THEN Grundauswahl wie heute
- [ ] GIVEN `enabled:false` für eine Metrik in einem Kanal WHEN alle Kanäle gerendert werden THEN Zeile fehlt nur dort
- [ ] GIVEN unterschiedliche Reihenfolgen je Kanal WHEN gerendert wird THEN jeder Kanal folgt seiner Reihenfolge
- [ ] GIVEN Kanal-Eintrag außerhalb der Grundauswahl / leere Grundauswahl / alle Einträge eines Kanals aus WHEN gerendert wird THEN Eintrag erscheint nicht / Kanal bleibt leer
- [ ] GIVEN Eintrag ohne `use_friendly_format` WHEN gerendert wird THEN Roh
- [ ] GIVEN Einfach bei Metrik mit nur einem `format_mode` WHEN gerendert wird THEN Ausgabe wie Roh
- [ ] GIVEN SMS mit Einfach für Wolken- und Nicht-Wolkenmetrik WHEN SMS gerendert wird THEN nur Wolken einfach, GSM-7-sicher, höchstens 160 Zeichen
- [ ] GIVEN Premium-SMS-Versand WHEN gesendet wird THEN Text identisch zum SMS-Text
- [ ] GIVEN Speichern in anderem Editor-Reiter WHEN `compareEditorSave` läuft THEN `channel_layouts` bleibt erhalten
- [ ] GIVEN zwei Nutzer mit verschiedenen Presets WHEN beide gerendert werden THEN keine Vermischung
- [ ] GIVEN Vorschau und Versand desselben Presets WHEN beide gerendert werden THEN gleiche Zeilen und Formate je Kanal

## Definition of Done

- [ ] AC-1 bis AC-14 durch automatisierte Tests an der Ausgabe je Kanal (Mail HTML + Klartext, Telegram, SMS, Premium-SMS) grün, Kern-Schicht ohne Netz und ohne Mock-Theater
- [ ] Golden-Dateien `tests/golden/vergleichs_mail/*` unverändert (Bestand bit-identisch)
- [ ] ADR-0119 angelegt, ADR-0053 und `docs/adr/README.md` mit "Abgelöst durch", `api_contract.md` §16 nachgezogen
- [ ] Auf Staging: ein Vergleich mit `channel_layouts` (Böen Telegram Roh, Mail Einfach) liefert echt zugestellte Mail mit Einfach-Darstellung und Telegram-/SMS-Text mit Zahl; ein Bestandsvergleich ohne `channel_layouts` liefert unveränderte Ausgabe

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleich, in dem Böen für Telegram als "Roh" und für die E-Mail als "Einfach" eingestellt sind / When die Telegram-Nachricht und die E-Mail erzeugt werden / Then zeigt Telegram bei Böen die Zahl und die E-Mail das einfache Zeichen bzw. Wort, beide im selben Bericht.
  - Test: Mail und Telegram desselben Presets rendern und die Böen-Zelle je Kanal prüfen.

- **AC-2:** Given ein bestehender Vergleich, der nur `channel_active_metrics` und kein `channel_layouts` hat / When Mail, Telegram und SMS erzeugt werden / Then ist die Ausgabe Zeichen für Zeichen identisch zu vorher (Golden-Dateien unverändert).
  - Test: Golden-Vergleich der Mail und Referenzen für Telegram/SMS ohne Änderung der Golden-Dateien.

- **AC-3:** Given ein Vergleich ohne `channel_layouts` und ohne `channel_active_metrics` / When ein Bericht erzeugt wird / Then gilt in jedem Kanal die Grundauswahl wie heute.
  - Test: Rendern ohne beide Schlüssel, Zeilen entsprechen der Grundauswahl, Ausgabe wie vor der Änderung.

- **AC-4:** Given eine Metrik ist nur im Kanal Telegram auf "aus" gestellt / When Mail, Telegram und SMS erzeugt werden / Then fehlt die Zeile nur in Telegram und steht in Mail und SMS weiter.
  - Test: Alle Kanäle rendern, Vorkommen der Zeile je Kanal prüfen.

- **AC-5:** Given für Mail, Telegram und SMS sind verschiedene Reihenfolgen eingestellt / When die Berichte erzeugt werden / Then zeigt jeder Kanal die Werte in seiner eigenen Reihenfolge.
  - Test: Reihenfolge der Zeilen je Kanal in der Ausgabe lesen.

- **AC-6:** Given die Grundauswahl des Vergleichs enthält nur einen Teil der Werte / When ein Kanal einen Wert außerhalb dieser Auswahl listet, die Grundauswahl leer ist oder in einem Kanal alle Werte auf "aus" stehen / Then erscheint der fremde Wert nicht, und der betroffene Kanal zeigt keine Werte (kein Rückfall auf alle).
  - Test: Rendern mit Kanal-Eintrag außerhalb der Grundauswahl, mit leerer Grundauswahl und mit einem Kanal, in dem alle Einträge `enabled:false` tragen.

- **AC-7:** Given ein Kanal-Eintrag hat keine Angabe zu "Einfach" / When der Bericht erzeugt wird / Then wird der Wert als Roh (Zahl) gezeigt.
  - Test: Eintrag ohne `use_friendly_format` rendern, Zahl in der Ausgabe.

- **AC-8:** Given "Einfach" ist für einen Wert eingestellt, der nur eine einzige Darstellung kennt / When der Bericht erzeugt wird / Then bleibt die Darstellung unverändert wie bei Roh, ohne Fehler.
  - Test: Metrik mit nur einem `format_mode` mit Einfach rendern, Ausgabe gleich Roh.

- **AC-9:** Given in der SMS ist "Einfach" für eine Wolkenmetrik und für eine andere Metrik eingestellt / When die SMS erzeugt wird / Then ist nur die Wolkenmetrik einfach dargestellt, der Text besteht aus GSM-7-sicheren Zeichen und hat höchstens 160 Zeichen.
  - Test: SMS rendern, Zeichensatz und Länge prüfen.

- **AC-10:** Given ein Vergleich mit Premium-SMS als Kanal / When die Premium-SMS verschickt wird / Then entspricht ihr Text exakt dem SMS-Text desselben Vergleichs mit denselben Einstellungen.
  - Test: Premium-SMS-Versand und SMS-Rendering vergleichen.

- **AC-11:** Given ein Vergleich mit gespeicherten Kanal-Einstellungen / When der Nutzer in einem anderen Reiter des Vergleichs speichert / Then bleiben die Kanal-Einstellungen erhalten und werden nicht gelöscht.
  - Test: Speichern aus einem anderen Reiter simulieren, `channel_layouts` danach noch vorhanden.

- **AC-12:** Given zwei Nutzer mit verschiedenen Vergleichen und Kanal-Einstellungen / When beide Berichte erzeugt werden / Then enthält jeder Bericht nur die Einstellungen seines Nutzers.
  - Test: Zwei Presets verschiedener Nutzer rendern, Ausgaben unterscheiden sich wie konfiguriert.

- **AC-13:** Given ein Vergleich mit Kanal-Einstellungen / When die Vorschau und der echte Versand erzeugt werden / Then zeigen beide in jedem Kanal dieselben Zeilen im selben Format.
  - Test: Vorschau- und Versand-Ausgabe desselben Presets je Kanal vergleichen.

- **AC-14:** Given ein Vergleich mit Kanal-Einstellungen (`channel_layouts`), und eine neue Metrik wurde der Grundauswahl hinzugefügt, für die noch kein Kanaleintrag existiert / When der Bericht erzeugt wird / Then erscheint sie eingeschaltet am Ende der Liste jedes Kanals.
  - Test: Preset mit zusätzlicher Metrik rendern, Position am Ende prüfen.

## Known Limitations

- Telegram zeigt bei Metriken ohne eigene Einfach-Darstellung weiterhin die Zahl.
- Die Bedienoberfläche (Karte) liefert #3031; #3042 bleibt gesperrt, bis dieser Workflow live ist.
- Standard ohne Angabe ist im Vergleich Roh, nicht der Katalog-Standard (anders als beim Trip).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** neues ADR-0119 (`docs/adr/0119-vergleich-channel-layouts.md`); löst den Teil "Entfernung channel_layouts (#1351)" von ADR-0053 ab
- **Rationale:** Die Wiedereinführung von `channel_layouts` am Vergleich kehrt eine frühere Entscheidung um und darf nicht still erfolgen (CLAUDE.md). Das ADR hält auch die Abweichung "ohne Angabe = Roh" und die Lesekompatibilität über `channel_active_metrics` fest.

## Changelog

- 2026-11-15: Initial spec created
- 2026-11-15: Definition of Done ergänzt
- 2026-11-15: Leer-Regel (AC-6) und Neue-Metrik-Regel (AC-14) gegeneinander abgegrenzt
