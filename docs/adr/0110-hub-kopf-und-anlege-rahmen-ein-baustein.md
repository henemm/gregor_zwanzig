# ADR-0110: Hub-Kopf und Anlege-Rahmen sind bei Trip und Ortsvergleich ein Baustein; Hauptaktion in Ink, Accent für Weiter und Aktiv-Zustand

- **Status:** Teilweise abgelöst durch ADR-0118 (Punkt 2 für „Test schicken ▾“: Akzent-Fläche `--g-accent-deep` statt Ink; Punkt 3: kein Zurück-Pfeil, voller Name statt Kürzel; Punkt 6: Mobil-Kennzahl-Kacheln entfallen; Issue #2980) — sonst Akzeptiert
- **Datum:** 2026-11-06
- **Bezug:** Issue #2837 (Scheibe S1 Hub-Kopf, Scheibe S2 Anlege-Rahmen), Epic #2345 (DoD-2 Oberfläche); Spec `docs/specs/modules/rework_2837_s1_hub_kopf.md`; schreibt ADR-0097 (Trip und Ortsvergleich teilen ihren Code) fort; Leitprinzip „Hoher Kontrast = Lesbarkeit“ (`docs/reference/design_system.md`).
- **Ergänzt durch:** ADR-0111 (Design-Vorgaben bereinigt, Issue #2881)

## Kontext

Der Kopf der Detailseite war bei Trip (`/trips/[id]`) und Ortsvergleich (`/compare/[id]`) zweimal verschieden gebaut: eigene Leiste mit orangem „Senden“, Status in eigener Zeile und orangen Reiter-Zählern beim Trip; „ORTS-VERGLEICHE / Hub“, schwarzes „Senden“ neben dem Titel, Status als Badge, waagerechtes Kebab mobil und graue Zähler beim Vergleich. Das widerspricht ADR-0097. Zwei frühere Spec-Entscheidungen aus #2284 hielten diese Teilung ausdrücklich fest; sie werden hier abgelöst, nicht still übergangen.

Kontrast, gemessen: Weiß auf `--g-accent #c45a2a` erreicht 4,34:1 und verfehlt damit WCAG-AA (4,5:1 für kleinen Text). Ink `--g-ink #1a1a18` auf Papier erreicht etwa 15:1. Ein neutraler Zähler (`--g-ink-3` auf `--g-paper-deep`) erreicht etwa 4,7:1.

## Entscheidung

1. **Ein Baustein `shared/hub-kopf/HubKopf.svelte` mit `context="route"|"vergleich"`.** Er trägt die Leiste (Breadcrumb bzw. mobiler Zurück-Pfeil, „Senden“, Kebab, Meldungen) und bindet den geteilten `SubscriptionHeader` ein. `context` wählt nur Text und Datenmarke, das Markup verzweigt nicht nach Art.
2. **Hauptaktion = Ink (`Btn primary`)**, bei beiden Arten in der Leiste ganz oben rechts. `--g-accent` bleibt für „Weiter“, Aktiv-Zustände (Unterstrich des aktiven Reiters), KI-Vorschlag und Logo-Blitz.
3. **Breadcrumb** „Trips / Kürzel oder Name“ bzw. „Orts-Vergleiche / Name“, Elternteil als Link aus dem Katalog; der Krümel „Hub“ entfällt. Mobil bei beiden der Zurück-Pfeil.
4. **Status als Badge in der Titelzeile** bei beiden Arten; „Tag x von y“ bzw. die Laufzeit stehen daneben.
5. **Kebab mobil senkrecht** (der mobile Knopf liegt in `SubscriptionKebab`), **Reiter-Zähler neutral** als Standard in `MTabBar` (nicht über `size`).
6. **Fachlich verschieden bleibt nur:** Datum, Kürzel, km/Hm, „Tag x von y“ bzw. Laufzeit, Mobil-Kennzahl-Kacheln (Trip), Orte-Anzahl (Vergleich) und die Entwurfs-Regel (Vergleich „Setup abschließen“ auf dem Platz von „Senden“, Trip-„Senden“ gesperrt).
7. **Anlege-Rahmen (Scheibe S2):** Dieselben Grundsätze gelten für `/trips/new` und `/compare/new` (Hauptaktion Ink, Weiter in Accent mit sichtbarem Gesperrt-Zustand, Speicherleiste unten für beide). S2 braucht dafür kein weiteres ADR.

**Löst ab:**

- `docs/specs/modules/feat_2284_s1_subscription_header.md` **Entscheidung 6** („Seiten-Chrome bleibt in der Seite“): Breadcrumb, Zurück-Pfeil, „Senden“, Kebab und mobiler Weitere-Aktionen-Knopf gehören jetzt in den geteilten `HubKopf`. Das Aktionsmodell (#2278: „Senden“ öffnet nur den Dialog, Aktionen kommen als Props) gilt weiter.
- `docs/specs/modules/feat_2284_s2_trip_kopf.md` **Entscheidungen 7 und 8** („`TripHeader` bleibt Hülle“, „Status und Meta außerhalb des Bausteins“): `TripHeader` bleibt Hülle für Datum, Kürzel, km/Hm und Mobil-Kacheln; aufgehoben ist die eigene Statuszeile, der Status kommt als Badge in die Titelzeile.

## Verworfene Alternativen

- **Senden orange für beide:** Weiß auf Orange liegt unter der AA-Schwelle 4,5:1; im Produkt sind Hauptaktionen schon heute überwiegend Ink (`Btn primary` 33×, `accent` 13×).
- **Zwei Köpfe mit gleichem Aussehen:** gleiche Optik ohne gemeinsamen Code driftet wieder auseinander (Anti-Pattern #1170).

## Konsequenzen

- **Positiv:** Trip und Ortsvergleich teilen den Kopf (ADR-0097); Lesbarkeit nach WCAG-AA; eine Zeile weniger beim Trip.
- **Negativ:** Viele Tests und E2E verankerten die Divergenz und wurden umgedreht (nicht gelöscht). Wer später wieder Orange für die Hauptaktion will, braucht ein neues ADR.

## Nachtrag 2026-11-08: S2 umgesetzt

Scheibe S2 (Spec `docs/specs/modules/rework_2837_s2_anlege_rahmen.md`) ist umgesetzt: `shared/anlege-rahmen/AnlegeRahmen.svelte` mit `context="route"|"vergleich"` trägt bei `/trips/new` und `/compare/new` den Desktop-Rahmen (Pfad „Trips / Neuer Trip“ bzw. „Orts-Vergleiche / Neuer Vergleich“ mit Elternteil als Link, Eyebrow, Titel, Fortschritt, Fuß mit „Abbrechen“ links und Hauptaktion `Btn primary` rechts). „Weiter“ ist bei beiden `Btn accent`, gesperrt nur über `disabled`. Erlaubte Abweichungen stehen allein in der Whitelist der Spec (Schritt-Inhalte, Abschluss-Text mit Hinweis, Autosave-Semantik beim Verlassen, Lock-Engines, Texte/Datenmarke/Testid-Präfix). `HubKopf` wurde dafür nicht erweitert; ein neues ADR war nicht nötig.

## Nachtrag 2026-11-08: S2b Fortschritt gehört zum Anlege-Rahmen

Scheibe S2b (Spec `docs/specs/modules/rework_2837_s2b_anlege_fortschritt.md`) macht den Fortschrittsbalken zum Teil des Anlege-Rahmens: ein Baustein `shared/anlege-rahmen/AnlegeFortschritt.svelte` zeichnet Segmente und Zähler für `/trips/new` und `/compare/new`, auf dem Computer (`variante="desktop"`, vom `AnlegeRahmen` selbst eingebunden, der Snippet-Slot `fortschritt` entfällt) und auf dem Handy (`variante="mobil"`, an der Handy-Stelle der Editoren). Farbregel für beide: erledigt `--g-accent`, sonst `--g-rule`; der aktive Schritt wird nicht getönt (er zeigt sich in der Reiterleiste). Die Annahme der S2-Spec, der Fortschritt sei schon gleich gewesen, war falsch: er war vierfach gebaut, und auf dem Handy tönte nur der Ortsvergleich den aktiven Schritt (Rückfallwert `#bcd`). Ein neues ADR war nicht nötig.

## Nachtrag 2026-11-09 (#2879): Accent unter Text ist `--g-accent-deep`

Der im Kontext festgehaltene AA-Verstoß (Weiß auf `--g-accent` = 4,34:1) ist behoben, ohne die Rollen zu ändern: „Weiter“ bleibt die Accent-Variante (`Btn accent`, `MBtn accent`), deren Fläche ist jetzt `--g-accent-deep` (#8c3e1a; Weiß darauf 7,45:1, Papier 6,77:1), im Hover 85 % `--g-accent-deep` mit Schwarz gemischt. Dasselbe gilt für den aktiven Handy-Reiter und alle handgeschriebenen Accent-Flächen mit Text auf den Trip- und Vergleichsseiten. Accent als Textfarbe (Kürzel im Trip-Titel, Rangnummern im Orte-Reiter, Kennzahl „Aktiv“ der Listen) ist ebenfalls `--g-accent-deep`. `--g-accent` bleibt, wo es keinen Text trägt (Unterstrich des aktiven Reiters, Fortschritts-Segmente, Rahmen, Punkte; Nicht-Text-Schwelle 3:1, Accent auf Papier 3,94:1). Der Zähler im aktiven Handy-Reiter ist jetzt neutral wie alle Zähler (`--g-paper-deep`/`--g-ink-3`, vorher transluzent mit 2,79:1). Spec `docs/specs/modules/fix_2879_kontrast_wcag_aa.md`, Prüftest `frontend/e2e/kontrast-trip-vergleich.spec.ts`. Ein neues ADR war nicht nötig.
