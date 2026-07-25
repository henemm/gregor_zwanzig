---
entity_id: compare_shared_day_window
type: module
created: 2026-07-25
updated: 2026-07-25
status: draft
version: "1.0"
tags: [compare, trip, day-window, shared, editor]
---

# Gemeinsames Tagesfenster für Trip und Ortsvergleich

## Approval

- [ ] Approved

## Purpose

Der Ortsvergleich speichert ein Zeitfenster (`hour_from`/`hour_to`), das **nirgends
wirkt**: beide Aufrufer ersetzen es hart durch den ganzen Tag (#1361 Befund 1).
Gleichzeitig existiert für den Trip bereits ein **gemeinsam gebauter** Tagesfenster-
Baustein mit eigener Auflösungsquelle — er ist für den Vergleich ausdrücklich
vertagt worden („Compare hat sein eigenes"), und dieses „eigene" ist der tote Pfad.

Diese Scheibe (**S1b** von Epic #1372, Dach #1374) führt beide auf **einen** Weg
zusammen: ein Feld, ein Auflöser, eine Bedienfläche für beide Kontexte — und
akzeptiert dabei erstmals Fenster über Mitternacht (#1361 Befund 1).

## Source

- **File:** `src/output/renderers/day_window.py`
- **Identifier:** `resolve_configured_window()` — „eine Quelle für die effektiven
  Fenster-Grenzen" (Epic #1319 Scheibe B)

## PO-Entscheidungen (2026-07-25, bindend)

1. Das Fenster wirkt auf **beides**: welche Zeilen die Stundentabelle zeigt **und**
   aus welchen Stunden die Vergleichswerte berechnet werden.
2. Bedienfläche zieht in den Reiter **Wetter-Metriken** — für **beide** Kontexte.
   Beim Trip bedeutet das einen Umzug aus dem Versand-Reiter. Begründung: Welche
   Stunden bewertet werden, ist eine Inhalts- und keine Versandfrage
   (Zuständigkeits-Vertrag, `docs/context/fix-1360-compare-tab-konzept.md`).
3. Voreinstellung **4 bis 19 Uhr für beide Seiten** — ein Standard, überall gleich.
   Für bestehende Vergleiche ändern sich dadurch einmalig die Werte (heute: ganzer
   Tag). Das ist gewollt und wird im Ticket dokumentiert.
4. `hour_from`/`hour_to` entfallen ersatzlos aus Bedienung und Auflösung. Kein
   Übernehmen der Altwerte — das Fenster kommt aus der gemeinsamen Quelle.

## Estimated Scope

- **LoC:** ~+180 / −140 (Zusammenführung, kein Neubau)
- **Files:** ~12
- **Effort:** medium — **LoC-Override erforderlich** (Testcode + Rückbau)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/day_window.py` | REUSE | `resolve_configured_window()` bleibt die einzige Quelle — **nicht** nachbauen |
| `src/output/renderers/email/helpers.py` | REUSE | `extract_hourly_rows()` (`:121-135`) ist das erprobte Filtermuster **inkl. Mitternachts-Übergang** (Bug #399) |
| `src/services/comparison_engine.py` | MODIFY | `time_window` kommt aus der gemeinsamen Auflösung statt aus dem Aufrufer; Mitternachts-Übergang ergänzen (`:105-112` kennt ihn nicht) |
| `src/services/scheduler_dispatch_service.py` | MODIFY | hartes `time_window=(0,23)` (`:354`) entfällt |
| `src/services/compare_preview_service.py` | MODIFY | hartes `time_window=(0,23)` (`:154`) entfällt |
| `src/services/report_config_resolver.py` | MODIFY | Compare-Zweig löst das Fenster über dieselbe Quelle auf wie der Trip-Zweig |
| `src/output/renderers/email/compare_html.py` | MODIFY | Stundentabelle zeigt nur Stunden im Fenster |
| `shared/WeatherMetricsTab.svelte` (+ `weatherMetricsTabSections.ts`) | MODIFY | neue Heimat der Bedienfläche, Abschnitt für **beide** Kontexte |
| `shared/VersandTab.svelte` / `versand-tab/VTSchedulePlan.svelte` | MODIFY | Tagesfenster-Bedienung zieht aus (Route-Zweig) |
| `internal/model/compare_preset.go`, `src/app/models.py` | MODIFY | Feld für das Tagesfenster am Vergleich; `hour_from`/`hour_to` bleiben in der Persistenz, verlassen die Bedienung |
| `scripts/migrate_1361_*.py` | CREATE | Bereinigung der toten `hour_from`/`hour_to` — Probelauf als Default, Sicherung, wiederholbar (Vorbild: `migrate_1360_drop_compare_top_n.py`) |

## Expected Behavior

- **Input:** Nutzer öffnet Trip oder Ortsvergleich, Reiter Wetter-Metriken.
- **Output:** Ein Tagesfenster (Von/Bis) an derselben Stelle, in beiden Fällen
  gleich bedienbar. Voreinstellung 4–19 Uhr.
- **Side effects:** Die Vergleichswerte und die Stundentabelle beziehen sich auf
  dieses Fenster. Ein über Mitternacht gehendes Fenster (z. B. 22–2 Uhr) wird
  korrekt behandelt.

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleich mit einem eingestellten Tagesfenster / When das
  Briefing erzeugt wird / Then zeigt die Stundentabelle je Ort ausschließlich
  Stunden innerhalb dieses Fensters.
  - Test: echte Staging-Mail, Stundenzeilen je Ort gegen das eingestellte Fenster
    prüfen.

- **AC-2:** Given derselbe Vergleich / When das Briefing erzeugt wird / Then sind
  die Werte der Vergleichstabelle (Höchst-/Tiefstwerte, Summen, Mittel)
  ausschließlich aus Stunden dieses Fensters berechnet.
  - Test: Fenster auf einen Ausschnitt setzen, in dem ein bekannter Extremwert
    außerhalb liegt; die Mail darf diesen Wert nicht mehr zeigen.

- **AC-3:** Given ein Fenster, das über Mitternacht reicht (z. B. 22 bis 2 Uhr) /
  When der Nutzer es über die Bedienfläche einstellt und das Briefing erzeugt wird /
  Then enthält die Stundentabelle die Stunden beider Kalendertagsseiten und keine
  Stunde dazwischen — und die Bedienfläche macht erkennbar, dass das Fenster über
  Mitternacht geht.
  - Test: Fenster über die Oberfläche setzen (nicht nur im Datensatz), echte Mail
    prüfen. PO-Entscheidung 2026-07-25: gilt für **beide** Kontexte; die gemeinsame
    Auflösung akzeptiert solche Fenster künftig, statt sie auf den Standard
    zurückzusetzen. Normale Fenster (Start vor Ende) dürfen sich dabei **nicht**
    ändern — die bestehenden Trip-Tests bleiben unverändert grün.

- **AC-4:** Given ein Trip und ein Ortsvergleich / When der Nutzer beide öffnet /
  Then findet er die Bedienfläche für das Tagesfenster an derselben Stelle im
  Reiter Wetter-Metriken, und sie verhält sich gleich.
  - Test: Playwright gegen Staging, beide Editoren, Position und Bedienbarkeit.

- **AC-5:** Given ein Trip, dessen Tagesfenster bisher im Versand-Reiter stand /
  When der Nutzer speichert / Then bleibt der zuvor eingestellte Wert erhalten und
  wirkt unverändert auf das Trip-Briefing.
  - Test: Trip mit gesetztem Fenster lesen, über die neue Fläche speichern, Wert
    und erzeugte Mail vergleichen.

- **AC-8:** Given bestehende Vergleiche mit den toten Feldern `hour_from`/`hour_to`
  / When die einmalige Bereinigung gelaufen ist / Then sind diese Felder aus den
  gespeicherten Vergleichen entfernt und alle übrigen Felder unverändert; ein
  zweiter Lauf ändert nichts.
  - Test: Preset vor/nach der Bereinigung feldweise vergleichen, zweiter Lauf ohne
    Wirkung.

## Known Limitations

- **AC-6/AC-7 entfallen aus dieser Scheibe (PO-Entscheidung 2026-07-25).** Die
  stille Fallback-Falle der Stundengrößen-Auswahl (#1361 Befund 3) kollidiert mit
  der Mindestspalten-Regel des Mail-Validators. Was „leere Auswahl" bedeutet, wird
  in **S3** einmal für alle Ausgaben entschieden — zusammen mit #1366 und der
  Validator-Regel. In dieser Scheibe wird daran nichts angefasst.
- Der 3-Tages-Ausblick bleibt unkonfigurierbar (#1361 Befund 2) — das ist **S3**.
- Die Voreinstellung 4–19 Uhr ändert bei bestehenden Vergleichen einmalig die
  Werte. Bewusste PO-Entscheidung, im Ticket zu dokumentieren.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** neu anzulegen
- **Rationale:** Nimmt die Festlegung aus #1268 („Bewertung = ganzer Tag, kein
  Editor-Feld") für den Ortsvergleich zurück und legt stattdessen fest: **ein**
  Tagesfenster für Trip und Vergleich, wirksam auf Anzeige **und** Bewertung,
  bedient im Reiter Wetter-Metriken. Eine dokumentierte Entscheidung wird nicht
  still rückgängig gemacht — daher eigener Eintrag.

## Changelog

- 2026-07-25: Initial spec created (S1b von Epic #1372)
- 2026-07-25: AC-6/AC-7 nach S3 verschoben (Konflikt mit Mindestspalten-Regel des
  Mail-Validators); AC-3 auf End-zu-End erweitert — Mitternachts-Fenster wird in
  der gemeinsamen Auflösung freigeschaltet (PO-Entscheidungen 2026-07-25).
