# ADR-0119: Der Ortsvergleich führt `channel_layouts` wieder — Reihenfolge, Aus und Roh/Einfach je Kanal (löst ADR-0053 Teil „Entfernung channel_layouts (#1351)“ ab)

- **Status:** Teilweise abgelöst durch [ADR-0124](0124-was-steht-wo-eine-tabelle.md) (Nr. 1, Teil „Reihenfolge = Listenindex je Kanal“: es gilt eine Reihenfolge für alle Stellen; Nr. 5, Teil „SMS: Einfach“: die SMS hat keine Wahl mehr; PO 2026-11-17, Issue #3122) — sonst Akzeptiert
- **Datum:** 2026-11-15
- **Bezug:** GitHub-Issue #3039 (Vorlauf zu #3031, Teil von #2795, Epic #2791), Spec `docs/specs/modules/feat_3039_vergleich_kanal_layouts.md` (AC-1 bis AC-14), Kontext `docs/context/feat-3039-vergleich-kanal-layouts.md`. **Löst teilweise ab:** [ADR-0053](0053-compare-kanal-eigene-metrikauswahl-uebersicht.md) (Kontext-Tabelle, Zeile „#1351 Teil 2“: Entfernung von `channel_layouts` aus dem Speicherweg samt Bestands-Migration). Schreibt fort: ADR-0050 (Teilmengen-Regel, „Aus ist ein Zustand“, Reihenfolge und Roh/Einfach je Kanal), ADR-0095 (Kanal-Parität), ADR-0049 (Premium-SMS sendet den SMS-Text), ADR-0077 (Go speichert `display_config` unvalidiert).
- **Ergänzt durch:** [ADR-0124](0124-was-steht-wo-eine-tabelle.md) (PO 2026-11-17, Issue #3122). Die Karte „Inhalt je Kanal“ (#3031), für die dieses ADR `channel_layouts` zurückbrachte, ist durch die Tabelle „Was steht wo“ ersetzt. Aus und Roh/Einfach bleiben je Stelle. Das gespeicherte Format je Kanal wird mit dem Bau zu #3122 neu geschnitten; bis dahin rendert der Bestand nach diesem ADR.

## Kontext

Mit #1351 Teil 2 (2026-07-24) wurde `display_config.channel_layouts` aus dem Speicherweg des Ortsvergleichs entfernt (`compareEditorSave.ts` löschte den Schlüssel bei jedem Speichern, `scripts/migrate_1351_drop_compare_channel_layouts.py` räumte den Bestand). Seit #1703 Scheibe 8 (ADR-0053) wählt der Vergleich je Kanal über `channel_active_metrics` aus, aber nur „an/aus und Reihenfolge“, ohne Roh/Einfach.

Die Karte „Inhalt je Kanal“ (#3031) gibt dem Vergleich dieselbe Bedienung wie dem Trip: je Kanal eine geordnete Liste mit „an/aus“ und „Roh/Einfach“. Dafür braucht der Vergleich wieder `channel_layouts`. Das kehrt die Entfernung aus #1351 um; CLAUDE.md verlangt dafür ein neues ADR.

## Entscheidung

1. **Datenform** am Vergleich: `display_config.channel_layouts = {email|telegram|sms: [{metric_id, enabled, use_friendly_format}]}`; Reihenfolge = Listenindex. Einträge tragen Katalog-Kennungen; die Renderer rechnen sie in Vergleichs-Zeilen um (z. B. Temperatur → Höchst- und Tiefstwert), das Format der Kennung gilt für alle abgeleiteten Zeilen.
2. **Kaskade je Kanal** (`resolve_compare_render_options`): `channel_layouts[kanal]` → sonst `channel_active_metrics[kanal]` → sonst Grundauswahl. `channel_active_metrics` bleibt lesbar (Bestand), Versand und Vorschau nutzen denselben Resolver.
3. **Bestand unverändert:** Ohne `channel_layouts` liefern die Rückfallstufen nur Auswahl und Reihenfolge, das Format ist der bisherige Festzustand. Bestandsvergleiche rendern Zeichen für Zeichen wie vorher.
4. **Standard ohne Angabe = Roh.** Fehlt `use_friendly_format`, gilt Roh (Präzedenz `outlook_metric_formats`). Bewusste Abweichung vom Trip (`loader._resolve_format_mode`, dort Katalog-Standard): sonst änderte sich jeder Vergleich, dessen Liste ohne Formatangabe gespeichert wurde. Einfach wirkt nur bei Metriken mit mehr als einem `format_mode`.
5. **Kanäle:** Mail Einfach = Ampelpunkt/Wort/Symbol wie im Trip, die Zelltönung bleibt; der Klartext-Teil zieht dieselbe Liste samt Format. Telegram nutzt dieselbe Formatstelle (ohne Einfachform bleibt die Zahl). SMS: Einfach nur für `SMS_FORMAT_MODE_METRIC_IDS` (Wolken als GSM-7-Stufe), höchstens 160 Zeichen. Premium-SMS und Telegram-„kurzform“ senden den SMS-Text.
6. **Teilmengen-Regel ADR-0050:** Kanal-Liste ∩ Grundauswahl; fehlt die Grundauswahl (`None`), wird nicht geschnitten; leer bleibt leer. Ein ausgeschalteter Eintrag ist ein ausdrücklicher Zustand. Werte der Grundauswahl ohne jeden Eintrag in der Kanal-Liste sind neu und erscheinen eingeschaltet am Ende. Folge: Eine leere Kanal-Liste (`channel_layouts[kanal] = []`) zeigt bei gesetzter Grundauswahl alle Werte eingeschaltet; „Kanal leer“ entsteht nur über ausdrücklich ausgeschaltete Einträge oder eine leere Grundauswahl (die Editor-Karte #3031 schreibt stets vollständige Listen).
7. **Altlast #1351 entfällt:** `compareEditorSave.ts` löscht `channel_layouts` nicht mehr; die Migration samt Test ist gelöscht und darf nie wieder laufen.

## Verworfene Alternativen

- **Katalog-Standard als Format ohne Angabe** (wie im Trip): verworfen, Bestandsvergleiche hätten ihr Aussehen geändert (Issue-AC „Bestand unverändert“ hat Vorrang).
- **Roh/Einfach als eigenes Feld neben `channel_active_metrics`:** verworfen, das wäre ein drittes Vergleichs-eigenes Vokabular statt der Trip-Form (Teilung Trip/Vergleich).

## Konsequenzen

- **Positiv:** Der Vergleich kann je Kanal Reihenfolge, Aus und Roh/Einfach zeigen wie der Trip; Bestand bleibt unverändert.
- **Negativ / Preis:** Zwei Felder für Kanal-Auswahl bestehen nebeneinander (`channel_layouts` hat Vorrang, `channel_active_metrics` ist Rückfall). Die Standardregel „ohne Angabe = Roh“ weicht vom Trip ab und muss beim Teilen von Code beachtet werden.
