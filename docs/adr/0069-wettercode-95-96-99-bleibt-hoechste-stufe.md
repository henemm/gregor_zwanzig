# ADR-0069: WMO-Wettercode 95/96/99 bleibt auf `ThunderLevel.HIGH` — Hagel wird stattdessen im Text unterschieden

- **Status:** Akzeptiert
- **Datum:** 2026-09-15
- **Bezug:** GitHub-Issue #2205, Spec `docs/specs/modules/fix_2205_hagel_im_text_wettercode_bleibt.md`,
  Kontext `docs/context/fix-2205-wettercode-zwischenstufe.md`; betrifft
  `docs/features/gewitter-gesamtkonzept.md:345` (Zielverfahren Schritt 1); berührt ADR-0025,
  ADR-0043, ADR-0057, ADR-0064 (Abgrenzung s. unten)

## Kontext

WMO-Wettercode 95 ("Gewitter, schwach oder mäßig") sowie 96/99 ("Gewitter mit Hagel") heben in
`_parse_thunder_level`/`THUNDER_CODES` (`src/providers/openmeteo.py`) und im Go-Spiegel
(`internal/provider/openmeteo/models.go`) alle drei pauschal auf `ThunderLevel.HIGH`. Issue #2205
unterstellte, das sei fehlerhaft: Eine einzige Modellstunde auf Code 95 reiche aus, um die
Tagesstufe auf "hoch" zu heben (Beleg: KHW 24.08., eine Stunde Code 95).

Das Konzeptdokument `docs/features/gewitter-gesamtkonzept.md:345` sah für den Wettercode-Ast von
Anfang an eine feinere Zuordnung vor: `< 95 kein · 95 leicht · 96 mittel · 99 hoch`. Der
produktive Code ist diesem Konzept nie gefolgt.

Die Nachmessung (15.09., ICON-D2-Archiv `/home/hem/gz-messdaten/khw-2026-08-archiv/`, je
Etappenpunkt, UTC) widerlegt die Ticket-Prämisse:

| Tag | Wettercode-Stunden | Echtes Gewitter? |
|---|---|---|
| 24.08. | 19h:95 (eine Stunde, 1,2 mm) | nein — Mitschnitt zeigte für den Nutzer nur LOW |
| 28.08. | 17h:99, 18h:95; Nacht 01h:95, 02h:95 | ja |
| 29.08. | 13h:96, 14h:99 | ja, der einzige kräftige Tag |
| 31.08. | 20h:95 (eine Stunde, 5,3 mm) | ja — die Gewitternacht |
| übrige | keine | 02.09. wurde von CAPE getragen, nicht vom Code |

**24.08. (Fehlfall) und 31.08. (echtes Nachtgewitter) sind nach Code (beide 95) und Dauer (beide
eine Stunde) identisch.** Keine Zuordnungs- oder Mindestdauerregel im verfügbaren Datenmaterial
trennt die beiden Fälle. Die Ticket-Prämisse "9 von 13 Tagen hoch" ist zudem ein Fehlzitat (9 =
mittel ODER hoch; hoch = 5 Tage, davon 4 echt) — der Wettercode-Ast trug 3 der 5 HIGH-Tage
(28./29./31.08.), alle drei real. Haupttreiber der Überprognose ist CAPE, nicht der Wettercode
(separat behandelt in #2178/#2206).

## Entscheidung

**Die Zuordnung `95/96/99 → ThunderLevel.HIGH` bleibt unverändert** — sowohl in
`_parse_thunder_level`/`THUNDER_CODES` (Python) als auch im Go-Spiegel
(`internal/provider/openmeteo/models.go`). `docs/features/gewitter-gesamtkonzept.md:345` (95
leicht/96 mittel/99 hoch) wird an dieser Stelle als **bewusst nicht umgesetzt** nachgetragen,
nicht gelöscht.

Statt die Stufe zu verändern, wird die vorhandene Hagel-Information (`hail_flag`, 96/99 → wahr)
im Text nachgezogen, an den Stellen, die heute 95 und 96/99 gleich behandeln (Spec
`fix_2205_hagel_im_text_wettercode_bleibt.md`):

- **Stufen-/Korridor-Änderungsalarm (alle vier Kanäle):** 96/99 tragen die bestehende
  Hagelaussage (`format_hail_note`, „Hagel: ja") im Mail-/Telegram-Text, SMS und Premium-SMS das
  bestehende Token-Suffix `+HL`; bei reinem 95 fehlt beides.
- **Nowcast/Radar-Label:** Code 95 → „Gewitter" (ohne Hagelbegriff), Code 96/99 → „Starker
  Hagel/Gewitter" (unverändertes Alt-Label, jetzt aber nicht mehr für 95 mitbehauptet).

Die Stufenzuordnung selbst, die Alarm-Auslöselogik (`alert_preset.py`,
`weather_change_detection.py`) und die bestehenden Presets bleiben unberührt.

Latente Codes 91–94/97 (0 Vorkommen in 230 000 gemessenen Stunden) bleiben auf
`ThunderLevel.NONE` — bewusst kein Fix, nur hier vermerkt.

## Verworfene Alternativen

- **95 → `LOW` (Konzeptwert aus `gewitter-gesamtkonzept.md:345`)** — verliert den 31.08.-Alarm
  (den einzigen Standard-Alarm-Auslöser für diesen Tag, ADR-0043: Standard/Entspannt alarmieren
  nur auf der höchsten Stufe) und kollidiert zusätzlich mit ADR-0064: `LOW` ist seit #2176 keine
  Gewitteransage mehr, sondern eine alarmlose Luftmassen-Größe außerhalb der vier-stufigen
  Leiter. Ein vom Modell tatsächlich gerechnetes Gewitter würde dadurch gar nicht mehr als
  Gewitter ausgesprochen.
- **95 → `MED`** — verliert ebenfalls den 31.08.-Alarm: Standard- und Entspannt-Preset
  alarmieren laut ADR-0043 nur beim Erreichen/Verlassen der höchsten Stufe, nicht bei `MED`.
- **Mindestdauer-/Persistenzregel (z. B. ≥ 2 h auf Code 95/96/99)** — verliert ebenfalls den
  31.08.-Alarm, da dort wie am 24.08. nur eine einzelne Stunde auf dem Code steht; keine im
  verfügbaren Datenmaterial beobachtete Mindestdauer trennt Fehlfall von echtem Ereignis.
- **Code 99 als eigene, höhere Sprosse behandeln** — Code 99 kommt außerhalb des ICON-D2-Gebiets
  praktisch nie vor (Messung 07.09.: icon_eu/AROME/ECMWF 0×99 in der Stichprobe). Korsika/GR20
  verlöre damit die Möglichkeit, "hoch" über den Wettercode-Ast zu erreichen — eine
  Gebiets-Asymmetrie zulasten der Kernstrecke des Produkts.

## Konsequenzen

- **Positiv:** Der reale Alarm-Nutzen (31.08.-Nachtgewitter, 28./29.08.) bleibt vollständig
  erhalten. Kein Deploy-Übergang mit Schein-Entwarnung (gespeichertes HIGH vs. neu berechnetes
  MED/LOW), kein verzerrter Mitschnitt-Vergleich. Die tatsächlich fehlende Information (Hagel ja/
  nein) wird dort ergänzt, wo sie fehlt, statt die Stufe zu verwässern.
- **Negativ / Preis:** Der 24.08.-Fehlfall (eine Stunde Code 95, 1,2 mm, kein echtes Gewitter)
  bleibt weiterhin ein möglicher Auslöser für HIGH — dieselbe Eingabe wie beim echten 31.08.-Fall
  lässt sich mit den verworfenen Optionen nicht trennen. Die Überprognose-Reduktion muss über den
  CAPE-Ast erfolgen (#2178/#2206), nicht über den Wettercode.
- **Folgepflichten:**
  - Jede künftige Änderung an `_parse_thunder_level`/`THUNDER_CODES` oder am Go-Spiegel
    `internal/provider/openmeteo/models.go`, die 95/96/99 von `HIGH` abweichen lässt, ist eine
    Abweichung von diesem ADR — sie verlangt ein neues ADR ("Abgelöst durch"), keine stille
    Änderung.
  - `docs/features/gewitter-gesamtkonzept.md:345` bleibt als dokumentierter, aber bewusst nicht
    umgesetzter Zielwert stehen — ein künftiger Umsetzungsversuch muss zuerst zeigen, welche neue
    Datenquelle oder Regel den 24.08./31.08.-Fall trennt, sonst gilt dieselbe Ablehnung.
  - Bestehende Tests, die "95/96/99 → HIGH" bereits als Invariante sichern
    (`tests/tdd/test_thunder_level_low_ordinal_and_render.py:77`,
    `internal/provider/openmeteo/provider_test.go:159-166`), bleiben die Zusicherung für diese
    Entscheidung — kein neuer, redundanter Test dafür.
  - Codes 91–94/97 bleiben ohne Fix (`ThunderLevel.NONE`), solange keine reale Messung einen
    Vorkommensfall zeigt.

## Abgrenzung

- **ADR-0025** ("eine Gewitter-Quelle für alle Briefing-Kanäle") ist unberührt: Die Stufe
  `dp.thunder_level` bleibt die alleinige Rohgröße für alle Kanäle; dieses ADR ändert nur, wie
  die Fusion aus dem Wettercode-Ast in diese Rohgröße einfließt — gar nicht.
- **ADR-0043** (Empfindlichkeitsstufe wirkt über das erreichte Niveau) ist die Referenz, gegen die
  die verworfenen Alternativen 95→LOW/MED und die Persistenzregel geprüft wurden — sie bleibt
  unverändert in Kraft.
- **ADR-0057** (additive Gewitter-Signalquellen je Gebiet) betrifft die Beschaffungsseite anderer
  Signale (GeoSphere cape/cin) und ist von diesem ADR nicht berührt.
- **ADR-0064** (`LOW` verlässt die vier-stufige Leiter) ist der Grund, warum "95 → LOW" verworfen
  wurde — dieses ADR bestätigt ADR-0064, statt es zu berühren.
- **`feat_1474_gewitter_befund_stufen.md`** (AC-4/AC-8) beschreibt dieselbe Zuordnung 95/96/99 →
  HIGH bereits als Ist-Zustand — kein Konflikt, keine Ablösung.
