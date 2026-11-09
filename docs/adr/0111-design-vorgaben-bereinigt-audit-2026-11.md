# ADR-0111: Design-Vorgaben nach dem Audit vom 9.11.2026 bereinigt — Reiterleisten, Listen, Fortschritt, Soll-Bilder, Copy

- **Status:** Akzeptiert (PO 2026-11-09, Freigabe Spec `docs/specs/modules/rework_2881_design_system_bereinigung.md`)
- **Datum:** 2026-11-09
- **Bezug:** Issue #2881 (Teil 2), Design-Audit der Trip- und Vergleichsseiten (`origin/main` 08e0d9f1a); präzisiert ADR-0109 Punkt 7 und ADR-0110; löst AP-003 (`docs/design-system/ANTI-PATTERNS.md`) und Charter §3 für die Trip- und die Vergleichsliste ab; nimmt die Desktop-Werte aus Spec #2845 (`docs/specs/modules/rework_2845_hub_reiterleiste.md`) zurück; Folgen in #2879 (Kontrast) und #2880 (Parität).

## Kontext

Das Audit fand Vorgaben, die sich widersprechen oder überholt sind:

- **Reiterleiste:** ADR-0109 Punkt 7 (vom PO mit Mockup Fassung 3 angenommen) verlangt eine Grundlinie `--g-rule`, 13 px/500, aktiv 600. Spec #2845 (umgesetzt 2026-11-09) machte die damalige Trip-Optik zur Einheitsoptik: 14 px, Linie `--g-ink-faint`, aktiv 500. Am Computer bleibt zudem ein Kasten sichtbar, weil die globale Regel `[data-slot="segmented"]` aus `frontend/src/app.css` auf `MTabBar` durchschlägt.
- **Listen:** Charter §3 und AP-003 verlangen ein Kachel-Grid; Trip- und Vergleichsliste sind gleich gebaute Tabellen (`ListTable`). Das Trip-Soll zeigt selbst eine Tabelle, das Vergleichs-Soll Kacheln.
- **Reiterleisten am Handy:** Der Hub nutzt `MTabBar` (Pillen), das Anlegen vier handgebaute Unterstrich-Leisten. Eine gemeinsame Vorgabe fehlt.
- **Fortschritt beim Anlegen:** offene Segmente in `--g-rule` haben 1,4:1 gegen den Grund (WCAG 1.4.11 verlangt 3:1), obwohl Spec #2837 S2b sie so festlegt.
- **Soll-Bilder:** `claude-code-handoff/current/soll/*.png` stammen aus Epic #575 (Juni 2026), zeigen den entfernten Signal-Kanal, den alten Schritt-Wizard und „Meine Touren“. `design_fidelity_diff.py` misst Detailseiten nur über die Listen-URL; große Papierflächen lassen völlig andere Layouts bestehen.
- **Copy:** `COPY.md` und Charter §2 verlangen „Tour“ und vier Navigationspunkte; das Glossar (ADR-0104) verbietet „Tour“, Produktbegriff ist „Trip“. Im UI stehen „Drafts“, „Alert-Trigger“, „Alerts justieren“.
- **Hauptaktion:** Charter §5 nennt Accent als Farbe der Primäraktion; ADR-0110 legt „Hauptaktion = Ink“ fest.

## Entscheidung

1. **Hub-Reiterleiste am Computer:** Maßgeblich ist ADR-0109 Punkt 7: kein Kasten, **eine** Grundlinie 1 px `--g-rule`, Reiter 13 px/500, inaktiv `--g-ink`, aktiv 600 mit 2-px-Unterstrich `--g-accent`, Zähler Mono 10 px neutral (`--g-paper-deep`/`--g-ink-3`), Radius 3 px. `MTabBar` setzt Rahmen und Radius der globalen Segmented-Regel ausdrücklich zurück. Die Desktop-Werte aus Spec #2845 (14 px, `--g-ink-faint`, aktiv 500) sind abgelöst; die Gleichheit von Trip und Vergleich aus #2845 bleibt. Am Handy bleibt die Pill-Leiste.
2. **Listen sind Tabellen:** Trip-Liste und Vergleichsliste nutzen `ListTable` (am Handy Karten-Zeilen). AP-003 und Charter §3 gelten für diese beiden Listen nicht mehr. Für neue Listen gilt: gleiche Art wie die Schwesterliste, keine dritte Form.
3. **Genau zwei Reiterleisten:** Im Hub `MTabBar` (Computer Unterstrich, Handy Pillen). Beim Anlegen `shared/anlege-rahmen/AnlegeReiter.svelte` (#2880), Unterstrich auf allen Breiten, weil die Schritte eine Reihenfolge mit den Zuständen erledigt und gesperrt haben. Eine weitere, handgebaute Reiterleiste ist nicht zulässig.
4. **Fortschritts-Segmente:** erledigt gefüllt in `--g-accent` (3,94:1), offen ohne Füllung mit 1-px-Kontur in `--g-ink-3` (5,13:1). Erledigt und offen unterscheiden sich damit nicht nur über die Farbe. Der Zähler „n von 5“ daneben nennt den Stand als Text in `--g-ink-3`.
5. **Soll-Bilder historisch:** `claude-code-handoff/current/soll/*.png` gelten als historisch. Maßstab sind `docs/reference/design_system.md`, das Mockup Fassung 3 (`docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html`) und die Playwright-Paritäts- und Kontrasttests (#2879, #2880). `design_fidelity_diff.py` und der Hook `pre_issue_close_design_gate.py` sind außer Dienst; der Hook-Eintrag in `.claude/settings.json` entfällt, die Skripte bleiben mit Vermerk liegen.
6. **Copy und Charter folgen den späteren Entscheidungen:** Produktbegriff **Trip** (Glossar, ADR-0104), Navigation wie die heutige Seitenleiste, Hauptaktion **Ink** (ADR-0110), Accent als Fläche unter Text nur als `--g-accent-deep` (#2879). Die Tabu-Liste in `COPY.md` nennt zusätzlich „Drafts“, „Alert-Trigger“ und „Alerts justieren“; im UI stehen „Entwürfe“, „Alarm-Auslöser“, „Alarme einstellen“.
7. **Zustands-Symbole:** Statt ✓ und ⊘ zeigt das UI den Baustein `Dot` mit Text (Charter §5). Gesperrt heißt `aria-disabled` und Punkt in `--g-ink-4`, erledigt Punkt in `--g-good`.

## Verworfene Alternativen

- **Spec #2845 als Maßstab behalten (14 px, `--g-ink-faint`):** jünger, aber nicht vom PO angenommen; ADR-0109 samt Mockup ist es. Die Kontrast-Verbesserung aus #2845 (inaktiv `--g-ink`) bleibt erhalten.
- **Listen auf Kacheln umbauen:** großer Umbau ohne Nutzerproblem; die Tabelle zeigt Status, Zeitraum und Versand vergleichbar, beide Listen sind heute gleich.
- **Soll-Bilder neu zeichnen:** hoher Aufwand; die Pixel-Differenz misst bei großen Papierflächen ohnehin wenig. Paritäts- und Kontrasttests messen genauer, was wirklich zählt.
- **Offene Fortschritts-Segmente als Fläche in `--g-ink-4`:** 2,71:1, weiter unter 3:1.

## Konsequenzen

- **Positiv:** Eine Quelle je Frage; der Code kann ohne Widerspruch an die Vorgaben angeglichen werden. Das Design-Gate, das wenig fing, wird durch genauere Tests ersetzt (Regel-Budget).
- **Negativ / Preis:** Die Hub-Reiter werden am Computer 1 px kleiner; Bestandstests mit 14 px werden umgestellt. Neue Soll-Bilder gibt es nicht; wer ein Bild als Vorlage braucht, nimmt das Mockup.
- **Folgepflichten:** #2794 baut den Reiter Wetter und übernimmt die hier ausgenommenen Reiter (Wertebereiche, Alarme, Layout, Wetter-Metriken); die Reiterleiste ist dann bereits nach Punkt 1. Neue Reiterleisten, Listen oder Status-Symbole richten sich nach den Punkten 2, 3 und 7.
