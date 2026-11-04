# Context: Einstellungen neu (Wetter · Ampel · Alarme · Zustellung) für Trip und Orte

- **Stand:** 2026-11-03, Konzeptphase abgeschlossen, Scheiben-Schnitt vom PO freigegeben (10 Scheiben, siehe unten).
- **Epic:** #2791 mit den Scheiben S1 #2792 · S2 #2793 · S3a #2794 · S3b #2795 · S4 #2796 · S5 #2797 · S6 #2798 · S7 #2799 · S8 #2800 · S9 #2801.
- **ADRs:** [ADR-0106](../adr/0106-profil-ampel-einzige-bewertung.md) *Akzeptiert* (2026-11-04, mit Präzisierungen P1 CAPE, P2 Gewitter „leicht“, P3 Altstufen) · [ADR-0107](../adr/0107-orte-ein-bis-n-orte.md) · [ADR-0108](../adr/0108-vorlage-und-tempo-getrennt.md) · [ADR-0109](../adr/0109-reiterstruktur-wetter-zustellung.md) (*Vorgeschlagen*).
- **Gemessen gegen:** `origin/main` @ `3c412c3ef` (2026-11-03). Alle Angaben `Datei:Zeile` beziehen sich darauf.
- **Sprache:** Jede neue oder geänderte Oberfläche und jeder neue Nachrichtentext ist **zweisprachig DE/EN** über die Kataloge (ADR-0104, `docs/reference/i18n_konventionen.md`, Glossar `docs/reference/i18n_glossar.md`). Das gilt für jede Scheibe (PO-Vorgabe bei der Freigabe des Schnitts, 2026-11-03).

## 0. Quellen: die vier Konzept-Seiten und ihre Sicherungskopie im Repo

Das Konzept ist auf vier claude.ai-Seiten entstanden. Ihre Speicher wurden am 2026-11-03 ausgelesen. Damit die Ergebnisse nicht an eine Sitzung oder ein Claude-Konto gebunden sind, liegen Seiten und Daten als Kopie in [`einstellungen_neu/`](einstellungen_neu/). **Maßgeblich ist dieses Dokument mit den Kopien.** Die Live-Seiten sind nur noch Verweis.

| Seite | Live-URL (Verweis) | Kopie im Repo | Gespeicherte Entscheidungen |
|---|---|---|---|
| Grundentscheidungen (12 Karten) | https://claude.ai/artifact/4j3tRPtmBxRkL67UU2JENB | `einstellungen_neu/seiten/grundentscheidungen.html` | `einstellungen_neu/daten/entscheidungen/*.json` |
| Ampel-Grenzen je Vorlage | https://claude.ai/artifact/1JjnLbshMDUCn1EZGGYBzu | `einstellungen_neu/seiten/ampel-grenzen.html` | `einstellungen_neu/daten/grenzwerte/*.json` |
| Hi-Fi-Mockup Hub (Fassung 3, Version 9) | https://claude.ai/artifact/Lfo1pdrjrgcA3XMLLJrrwQ | `einstellungen_neu/seiten/mockup-hub-fassung3.html` | Collection `rueckmeldung` leer, Mockup **angenommen** |
| Abgleich alt gegen neu (40 Punkte, 57 Inventar) | https://claude.ai/artifact/2HFmTFD5jnMVX8ShwMxZa8 | `einstellungen_neu/seiten/abgleich-alt-neu.html` | `einstellungen_neu/daten/abgleich/*.json` (nur Abweichungen) |
| Verbindlicher Stand (Text) | Speicher der ersten Seite, `stand/aktuell` | `einstellungen_neu/stand-2026-11-03.md` | – |

Die HTML-Kopien laufen lokal im Browser (Speicher-Anbindung fehlt dann, die Inhalte sind vollständig). Die Seiten speichern nur Abweichungen von ihrer Vorauswahl. Was nicht gespeichert ist, gilt als **angenommen** (PO-Regel 2026-11-03).

## 1. Ausgangslage

Laut PO ist die heutige GUI für Wetter-Metriken, Wertebereiche und Alarme „eine Katastrophe“. Ziele:

1. Trip und Ortsvergleich vereinheitlichen (ADR-0097 gilt weiter: ein Code, `context="route"|"vergleich"`).
2. So einfach wie möglich.
3. Beste Usability.

Diagnose:

- Die drei Reiter Wertebereiche, Layout und Alarme bilden drei technische Mechanismen ab: Renderer-Auswahl, Markierung und Δ-Wächter.
- Je Metrik gab es bis zu **vier Bewertungsstellen**: Wertebereich (`corridors`, `src/app/models.py:1282`, am Ortsvergleich `models.py:1361`), Markieren, SMS-Schwellwert (`MetricConfig.sms_threshold`, `models.py:689`, Stufen Sensibel/Standard/Robust) und Δ-Empfindlichkeit (`metric_alert_levels`, `models.py:848`, off/entspannt/standard/sensibel).
- Ein unabhängiger JTBD-Agent kommt zum Schluss, dass Nutzer in „gefährlich / unangenehm / ideal“ und „wann“ denken.

## 2. Entscheidungen des PO

### 2.1 Schritt 1 (per Rückfrage)

- **Alarm** bleibt ein Abweichungs-Wächter: Vergleich gegen das letzte Briefing bzw. den rollierenden Anker. ADR-0009 und ADR-0056 bleiben gültig. Je Metrik soll einstellbar sein, wie wichtig sie ist.
- **Stufen:** Die 4-stufige Ampel aus dem Trip-Briefing ist die Bewertung, und der Alarm hängt daran.
- **Kein Ranking im Ortsvergleich.** Ein Bericht für **einen einzigen Ort** muss möglich sein.
- **Keine Vorschau.** „Senden“ wird zu **„Test schicken ▾“** mit Auswahl des Kanals.

### 2.2 Schritt 2 (12 Karten, `daten/entscheidungen/`)

| Karte | Wahl | Bedeutung | Notiz des PO |
|---|---|---|---|
| `alarm_logik` | `beides` | Alarm bei **Stufenwechsel** gegenüber dem Briefing **oder** bei einem **sehr großen Sprung innerhalb einer Stufe** (z.B. Böen 65 → 95, beides rot). Die Sprunggröße legt das System fest, nicht der Nutzer. Sinkt die Stufe, kommt eine Entwarnung. | – |
| `wichtigkeit_woerter` | `ampel_direkt` | Regler heißt **„Alarm ab: Nie · Gelb · Orange · Rot“** (Gewitter: Nie · Orange · Rot) | – |
| `metrik_zeile` | `ampel_leiste` | **A · Ampel-Leiste**: vier Farben als Leiste, Grenzen als Zahlen darüber, rechts „Alarm ab“, Grenzen per Knopf eingebbar | – |
| `reiter` | `wetter_zustellung` | Reiter **Übersicht · Etappen/Orte · Wetter · Zustellung**. Kein Wertebereiche-, kein Alarme-, kein Versand-, kein Layout-Reiter. Alarmstufe steht an der Metrik, der Alarmweg unter Zustellung. | – |
| `test_schicken` | `menue` | **Menü am Knopf**: ein Klick öffnet die Kanalliste, ein zweiter schickt; nicht verknüpfte Kanäle ausgegraut mit Grund | – |
| `ein_ort` | `orte` | **„Orte“** mit 1..n Orten. Ein Ort ergibt ein Orts-Briefing, ab 2 Orten kommt die Vergleichstabelle dazu | Der Validator verlangt heute ≥3 Orte und muss angepasst werden |
| `aggregation` | `versteckt` | Aggregation **fest je Metrik**, nicht sichtbar, nicht wählbar (Böen = Spitze, Regen = Summe, Temperatur = Tief und Hoch). „Gefühlte Temperatur“ erscheint nicht mehr doppelt. | – |
| `kanal_inhalt` | `wie_heute` | **Eigene Liste je Kanal**, sichtbar (nicht automatisch nach Alarmstufe) | – |
| `ohne_ampel` | `ampel_nachruesten` | **Ampel überall, wo sinnvoll**, inklusive relativer und umgekehrter Skalen. Was übrig bleibt, ist reine Anzeige. Die Ampel ersetzt den Wertebereich vollständig. | „Es gibt aber auch Werte, die je nach Aktivität in den Extremen rot werden, z.B. Temperatur (Skilaufen: zu niedrig ist schlecht (−30 °C), aber zu hoch auch (+15 °C)). Das gleiche kann auch für Wind beim Segeln gelten.“ ⇒ **Ampel beidseitig je Vorlage** |
| `toleranz` | `nein` | **Kein** globaler Toleranz-Regler, die Vorlage reicht; Feinheiten je Metrik | – |
| `cooldown` | `anpassen` | Cooldown bleibt einstellbar **unter Zustellung → Anpassen** („Mindestabstand zwischen zwei Alarmen derselben Metrik“) | – |
| `aktivitaet` | `eine_auswahl` | **Eine Auswahl (Vorlage), Tempo getrennt** | „Aktivität hat grundsätzlich zwei Ursprünge: 1. sinnvolle Presets, der User kann sie anpassen und speichern. Das wäre für den Reiter ‚Wetter‘ relevant. 2. Fortbewegungsgeschwindigkeit. Ausschließlich für Trips relevant, hier aber sehr relevant.“ |
| Tempo (Rückfrage) | – | Tempo **im Reiter Etappen**: Fortbewegungsart, Tempo flach, Aufstieg; gilt für alle Etappen, je Etappe überschreibbar | – |

### 2.3 Mockup-Rückmeldungen (eingearbeitet in Fassung 3)

- Klick auf die Vorlage öffnet eine Liste mit den **7 Vorlagen** und den **eigenen** Vorlagen. Eigene Sets unter eigenem Namen gibt es heute schon (`frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte`). Bei einem Wechsel kommt eine Rückfrage mit der Zahl der Abweichungen.
- Statt Schalter: **„−“ entfernt** eine Metrik, sie wandert nach „Nicht im Briefing“, „+“ holt sie zurück.
- Unter jeder Ampel steht ein **Satz**, der den Alarm erklärt (Wortlaut in §4.3).
- **„Inhalt je Kanal und Fläche“**: E-Mail · Telegram · SMS · Premium-SMS · 3-Tages-Ausblick · (nur Orte) Stundenverlauf.
  - Jede Liste ist eine Teilmenge der Metrik-Zeilen (ADR-0050, ADR-0059): abwählen ja, hinzufügen nein.
  - Beim Trip *ist* die E-Mail-Liste die Stundentabelle, beim Ortsvergleich die Vergleichstabelle.
- Zeilenformat **„Temperatur (Temp | T)“**: englischer Mail-Spaltenkopf `col_label` | SMS-Kürzel (beides aus dem Katalog). Darüber eine Kopfzeile, die Metrik, Darstellung und Schalter erklärt.
- **Roh/Einfach** je Zeile in **jeder** Liste, also auch Vergleichstabelle, Stundenverlauf und Ausblick.
- **Briefing-Uhrzeiten** sind über ein Uhrzeitfeld änderbar. Die Schnellwahl 07:00/18:00 entfällt (V11).

### 2.4 Nachentscheidungen vom 2026-11-03 (nach Mockup Fassung 2)

- **Grenzen bearbeiten:** deutlicher Knopf „Grenzen ändern“ in jeder Metrik-Zeile. Er öffnet die Felder der Seiten, die die Metrik erlaubt (beidseitig, nur oben oder nur unten wie auf der Grenzwert-Seite), mit dem Text „grün: X bis Y“. Gewitter: Farbe für „mittel“ (gelb/orange/rot) und „hoch“ (orange/rot) wählbar. Geänderte Grenzen zählen als Abweichung von der Vorlage.
- **Roh/Einfach** sitzt **nur** in den Listen unter „Inhalt je Kanal und Fläche“, je Zeile und Liste, mit Beispiel (z.B. „27 °C · ● gelb“). In den Metrik-Zeilen steht es nicht.
- **Aufbau „Inhalt je Kanal und Fläche“:** Die Metrik-Liste steht in jedem Kanal-Reiter an derselben Stelle direkt unter den Kanal-Reitern. Kanalweite Einstellungen (Mail-Format, Zusatzblöcke, Telegram-Kurzstil, Ausblick morgens/abends, Stundenverlauf an/aus) und Erklärsätze kommen **unter** die Liste in ein festes, eingeklapptes Feld **„Weitere Einstellungen für <Kanal>“**. Die Reiter bleiben, Zustellung wird nicht umbenannt. Der Telegram-Kurzstil (A11) zieht deshalb aus Zustellung dorthin.
- **V12, „Mehrtages-Trend“ geht im 3-Tages-Ausblick auf:** Im Code ist `multi_day_trend` die Datenquelle des Ausblicks (`src/output/renderers/email/html.py:1176-1221`, Schalter `outlook_active` in Zeile 1182). Heute steuern drei Stellen denselben Block: `show_outlook` (`models.py:1170`), `multi_day_trend_reports` (`models.py:1157`, Default `["evening"]`; Label „Mehrtages-Trend · Sonntags · 3–7-Tage-Ausblick“ ist irreführend) und `outlook_metrics=[]` (`models.py:860`). Neu gibt es **eine** Stelle: die Liste „3-Tages-Ausblick“ unter „Inhalt je Kanal und Fläche“, mit Spalten und „erscheint im Morgen-/Abend-Briefing“. Vorbelegung **nur abends**. Der Begriff „Mehrtages-Trend“ entfällt. **Ein Name überall:** „3-Tages-Ausblick“ (EN „3-day outlook“) in Oberfläche und beiden Mails. Heute gibt es vier Namen:
  - „Mehrtages-Trend · Sonntags · 3–7-Tage-Ausblick“ (`frontend/src/lib/components/shared/versand-tab/VTSchedulePlan.svelte:188`, Schlüssel `versand.zeitplan.trend`/`trend_sub`; noch sichtbar, die Unterzeile ist falsch),
  - „3-Tages-Ausblick“ (Layout, Orte-Mail),
  - „Ausblick“ (Trip-Mail, `mail.ausblick.titel`),
  - „3-Tages-Vorschau“ (nur in Specs/Code).
- **A11, Telegram-Kurzstil, geklärt:** `telegram_style` (`rich`/`kurzform`, `models.py:1172`) wirkt auf **Briefing und Alarme**, beim Trip (`src/services/notification_service.py:903`, `src/services/trip_alert.py:485`) und bei Orten (`src/services/scheduler_dispatch_service.py:1048`, `src/services/compare_alert_channels.py:65`). Es wird ein Schalter „Kurzstil“ in der Telegram-Liste unter „Weitere Einstellungen für Telegram“ mit dem Satz „gilt für Briefing und Alarme“. **Nebenbefund, geklärt:** Das ältere Feld `telegram_kurzform` (#614, `models.py:843`) ist seit #1001 AC-10 **wirkungslos** (`src/output/renderers/trip_report.py:487`, `src/output/renderers/narrow.py:698`). Es bleibt nur aus Altdaten-Kompatibilität bestehen, wird aber noch in `loader.py:1095/1620/1837` gelesen und geschrieben und in `frontend/src/lib/components/shared/versand-tab/vtBriefingChannelsText.ts:43` angezeigt. Es bekommt keine Oberfläche mehr.
- **W5b, Zeithorizonte, weglassen:** Der Renderer filtert zwar nach `horizons` (`models.py:683`, `html.py:759` `_allowed_col_keys_for_horizon`), aber kein Bedienelement setzt sie mehr: `frontend/src/lib/components/molecules/HorizonChips.svelte` und `frontend/src/lib/components/trip-detail/MetricCheckbox.svelte` sind nirgends importiert. Die Zusammenfassung im Dialog „Vorlage speichern“ entfällt. Gespeicherte Altwerte werden per Migration (Read-Modify-Write, ADR-0101) auf „alle Tage“ gesetzt, damit keine Spalte unbemerkt fehlt.

## 3. Abgleich alt gegen neu (`daten/abgleich/`)

Ein Agent hat jedes Bedienelement der heutigen Hubs inventarisiert, für Trip und Ortsvergleich, Desktop und Mobil: **97 Elemente** (40 Prüfpunkte + 57 Inventarzeilen). 38 Punkte waren nicht abgedeckt, dazu kamen 2 neue Fragen (N1, N2). **Alle Empfehlungen sind angenommen**, mit den in der letzten Spalte markierten Ausnahmen.

### 3.1 Vier Annahmen, die nicht stimmten

- **Vorlagen gibt es heute nur im Trip.** Für „Orte“ ist die Vorlage neu (WV4).
- **Radar-Alarm gibt es heute nur im Ortsvergleich** (`radar_alert_enabled`, `models.py:1336`; `src/services/compare_radar_alert.py:226`). Siehe N1.
- **„Inhalt je Kanal“ hat heute 3 Kanäle** (E-Mail, Telegram, SMS). Premium-SMS hat keine eigene Liste. Siehe N2.
- **Totes Alarm-Bündel:** `frontend/src/lib/components/alerts-tab/AlertsTab.svelte`, `AlertPresetSelector.svelte`, `AlertCard.svelte` werden nirgends importiert (geprüft 2026-11-03, 0 Importeure). Sie fallen beim Umbau weg (A15).

### 3.2 Die 40 Prüfpunkte mit Entscheidung

| ID | Bereich | Kontext | Punkt | Heute | Empfehlung | **Entscheidung PO** |
|---|---|---|---|---|---|---|
| N1 | Neu zu entscheiden | Trip | Radar-Regen-Alarm auch für Trips | Gibt es heute nur im Ortsvergleich (radar_alert_enabled). | Rein. Gerade unterwegs ist „Regen in der nächsten Stunde“ wertvoll. Parität zu Orte (ADR-0095). | **rein („unbedingt“)** |
| N2 | Neu zu entscheiden | beide | Premium-SMS: eigene Inhaltsliste oder folgt der SMS | Heute hat sie keine eigene Liste und folgt technisch der SMS. | Folgt der SMS. In der Liste steht dann der Hinweis „wie SMS“, damit keine zweite Liste gepflegt werden muss. | **rein, eigene Liste** (abweichend von der Empfehlung) — Alarm-Unterschied über Dringlichkeits-Schwelle: SMS ab gering/mittel, Premium-SMS ab hoch |
| K3b | Kopf & Aktionen | Orte | Profil des Ortsvergleichs (Mail-Kopf, Vergleichsprofil beim Versand) | Die Chips im Kopf setzen „profil“. Das steuert den Versand (scheduler_dispatch_service.py:918) und den Kopf der Mail. | Rein, aber über die Vorlage. Der Name der Vorlage ersetzt das Profil, die Mail zeigt ihn im Kopf. | **rein** (Empfehlung angenommen) |
| K10 | Kopf & Aktionen | beide | Ziel und Sperre beim Test-Versand | Der Senden-Dialog zeigt „Geht an E-Mail (x) · Telegram …“ und sperrt, wenn eine Adresse fehlt oder unbestätigt ist. | Rein ins Kanal-Menü: jede Zeile nennt ihr Ziel, gesperrte Kanäle nennen den Grund und verlinken aufs Konto. | **rein** (Empfehlung angenommen) |
| K11 | Kopf & Aktionen | Trip | Berichtsart Morgen oder Abend beim Test | Der Dialog fragt beim Trip, welches Briefing geschickt wird. | Rein: im Menü oben „Morgen-Briefing · Abend-Briefing“, darunter die Kanäle. | **rein** (Empfehlung angenommen) |
| K12 | Kopf & Aktionen | beide | Rückmeldung nach dem Senden | „Briefing gesendet!“ und Fehlertexte, im Ortsvergleich mobil heute schon fehlend. | Rein, in beiden Kontexten gleich und auch mobil. | **rein** (Empfehlung angenommen) |
| A14 | Kopf & Aktionen | beide | Beispiel-Warnung (Alarm-Vorschau) | „Vorschau laden“ zeigt Betreff, Mail, Telegram und SMS eines Beispiel-Alarms mit Zeichenzähler. | Ersetzen: „Test schicken ▾“ bekommt den Eintrag „Test-Alarm“. Das passt zu deinem Entscheid, keine Vorschau, sondern echte Tests. | **rein** (Empfehlung angenommen) |
| K14 | Kopf & Aktionen | beide | Kebab: Pausieren, Archivieren, Löschen | Pausieren/Fortsetzen, Archivieren/Reaktivieren, Löschen, jeweils mit Rückfrage. | Rein, das Kebab neben „Test schicken“ bleibt unverändert. | **rein** (Empfehlung angenommen) |
| K15 | Kopf & Aktionen | beide | Bestätigungsdialoge und Fehlermeldung beim Statuswechsel | Archivieren (Trip), Löschen, Fehler beim Statuswechsel. | Rein, gehört zu K14. | **rein** (Empfehlung angenommen) |
| V16 | Kopf & Aktionen | Orte | Entwurf aktivieren | Die Aktivierungskarte im Versand ist der einzige Weg, einen Entwurf zu aktivieren. | Rein: Status-Pill im Kopf mit Aktion „Aktivieren“, dazu der Eintrag im Kebab. | **rein** (Empfehlung angenommen) |
| K17 | Kopf & Aktionen | beide | Alte Links und Lesezeichen | ?tab=wertebereiche, ?tab=alarme und der Listen-Eintrag „Alarme“ führen auf entfallene Reiter. | Rein: alte Adressen leiten auf Wetter bzw. Zustellung um, der Listen-Eintrag wird angepasst. | **rein** (Empfehlung angenommen) |
| W1 | Reiter Wetter | beide | Ladefehler und Ladezustand | „Lade Metriken …“ und „Wiederholen“ bei einem Fehler. | Rein. Ohne das sieht man einen stillen, leeren Editor. | **rein** (Empfehlung angenommen) |
| W4 | Reiter Wetter | beide | Rückfrage beim Wechsel der Vorlage | „Preset anwenden … überschreibt die aktuelle Auswahl“. | Rein, steht schon im Mockup (Übernehmen/Abbrechen mit Zahl der Abweichungen). | **rein** (Empfehlung angenommen) |
| W5b | Reiter Wetter | beide | Dialog „Vorlage speichern“: Beschreibung, Standard für neue, Zeithorizonte | Heute gibt es Beschreibung, Zusammenfassung, Zeithorizonte und „Als Standard für neue Trips“. Wie die Zeithorizonte wirken, ist unklar. | Rein: Name, Beschreibung und „Als Standard für Neue“. Die Zeithorizonte prüfe ich vor dem Umbau und lasse sie weg, wenn sie nichts bewirken. | **rein ohne Zeithorizonte** — Name, Beschreibung, „Als Standard für Neue“; Altwerte `horizons` per Migration auf „alle Tage“ |
| W11 | Reiter Wetter | beide | Darstellung Roh oder Einfach je Metrik, in jeder Liste | Heute je Kanal beim Trip. Ändert, was in Mail, SMS und Telegram steht (Zahl gegen Ampelpunkt oder Symbol). | Rein als Umschalter je Zeile in jeder Liste: E-Mail, Telegram, SMS, Premium-SMS, Vergleichstabelle, Stundenverlauf und 3-Tages-Ausblick. Gilt für Trip und Orte gleich (dein Hinweis). | **rein** (Empfehlung angenommen) |
| W19 | Reiter Wetter | beide | 3-Tages-Ausblick: Metriken, Reihenfolge, Roh/Einfach | Eigene Auswahl aus der Grundauswahl, mit Reihenfolge und Darstellungsform. | Rein, steht seit der zweiten Fassung im Mockup als eigene Liste neben den Kanälen. | **rein** (Empfehlung angenommen) |
| WV9 | Reiter Wetter | Orte | Stundenverlauf: Metriken, Reihenfolge, gesperrte Größen mit Grund | Z.B. Sonnenstunden sind dort gesperrt, mit Begründung. | Rein als eigene Liste, die gesperrten Größen werden mit Grund angezeigt. | **rein** (Empfehlung angenommen) |
| W15 | Reiter Wetter | Trip | E-Mail-Format: Ausführlich (HTML) oder Kompakt (Nur-Text) | report_config.email_format, betrifft die ganze Mail. | Rein unter „Inhalt je Kanal → E-Mail“ als erste Einstellung. Gilt künftig auch für Orte, wenn der Renderer es kann. | **rein** (Empfehlung angenommen) |
| W17 | Reiter Wetter | Trip | Etappen-Kennzahlen in der Mail | show_stage_stats | Rein unter „E-Mail → Zusatzblöcke“. | **rein** (Empfehlung angenommen) |
| W18 | Reiter Wetter | Trip | Vortag-Vergleich | show_yesterday_comparison | Rein unter „E-Mail → Zusatzblöcke“. | **rein** (Empfehlung angenommen) |
| W22 | Reiter Wetter | Trip | Nacht-Stundentabelle in der Mail | show_night_block | Rein unter „E-Mail → Zusatzblöcke“. | **rein** (Empfehlung angenommen) |
| V12 | Reiter Wetter | Trip | Mehrtages-Trend (sonntags, 3–7 Tage) | multi_day_trend_morning/evening, ein anderer Block als der 3-Tages-Ausblick. | Rein unter „E-Mail → Zusatzblöcke“ mit Wahl Morgen/Abend. | **rein, zusammengelegt** mit dem 3-Tages-Ausblick (ein Name, eine Stelle) |
| W21 | Reiter Wetter | beide | Legende der amtlichen Warnungen in Kurzform | Präfix „!“, Gefahren-Kürzel, Stufen L/M/H. | Rein in die Kürzel-Legende von Telegram, SMS und Premium-SMS. | **rein** (Empfehlung angenommen) |
| WV6 | Reiter Wetter | Orte | Hinweis „Amtliche Warnungen stehen immer an erster Stelle“ | Kleiner Hinweis in der Reihenfolge. | Rein als feste, nicht verschiebbare erste Zeile jeder Kanalliste. Das erklärt sich von selbst. | **rein** (Empfehlung angenommen) |
| A3 | Reiter Wetter | beide | Kennzeichnung nicht alarmfähiger Größen | „Keine der gewählten Größen kann einen Alarm auslösen …“ | Rein: In der Zeile steht statt „Alarm ab“ der Text „kein Alarm (Vorbote)“. Der Sammelhinweis erscheint, wenn gar keine Größe alarmfähig ist. | **rein** (Empfehlung angenommen) |
| A5 | Reiter Wetter | beide | „Alle Metriken auf …“ und Zähler | Sammel-Setzen der Empfindlichkeit, „x von y aktiv“. | Rein als „Alarm ab für alle: Nie · Gelb · Orange · Rot“ über den Metrik-Zeilen. | **rein** (Empfehlung angenommen) |
| A6 | Reiter Wetter | beide | ⓘ-Erklärung bei CAPE | CAPE steht heute als eigene Alarmzeile mit Erklärung. | Darf weg, wenn CAPE in der Gewitter-Zeile aufgeht. Sonst bleibt die Erklärung. | **weg** — CAPE geht in der Gewitter-Zeile auf |
| B8 | Reiter Wetter | beide | Bestandsschutz für gespeicherte Wertebereiche | „n weitere Einträge bleiben erhalten“, also ideal_ranges, corridors, alert_rules. | Rein als eigene Migrations-Scheibe (Read-Modify-Write): alte Wertebereiche und Alarmstufen werden in Ampel-Grenzen überführt, nichts geht verloren. | **rein** (Empfehlung angenommen) |
| V3 | Reiter Zustellung | beide | Verbindungsstatus je Kanal und Sperre | Punkt plus „bestätigt / verbunden / unbestätigt / nicht verbunden“. Ohne Verbindung ist der Schalter gesperrt. | Rein in die Kanal-Tabelle als Unterzeile. | **rein** (Empfehlung angenommen) |
| V4 | Reiter Zustellung | beide | Hinweise mit Konto-Link | „E-Mail-Adresse fehlt“, „Telegram-Chat-ID fehlt“, „Nummer noch nicht bestätigt“, „SMS ab Level Standard“. | Rein, direkt in der betroffenen Kanalzeile. | **rein** (Empfehlung angenommen) |
| V5 | Reiter Zustellung | beide | Premium-SMS-Status (gelernt, verfallen, zuletzt gemeldet) | Sicherheitsrelevant: eine verfallene Rückadresse kann ein fremdes Gerät erreichen. | Rein, unverändert, in der Premium-SMS-Zeile. | **rein** (Empfehlung angenommen) |
| A10 | Reiter Zustellung | beide | Premium-SMS-Alarm gesperrt mit Grund | „Tarif wird geprüft …“, „ab Level Premium“. | Rein in der Spalte „Alarme“ der Premium-SMS-Zeile. | **rein** (Empfehlung angenommen) |
| V7 | Reiter Zustellung | beide | „Kein Kanal aktiv“ | Warnung, wenn kein Briefing-Kanal an ist. | Rein über der Kanal-Tabelle. | **rein** (Empfehlung angenommen) |
| A9 | Reiter Zustellung | beide | „Kein Alarm-Kanal“ und Zähler | „Alerts gehen nirgends hin“, „n aktiv“, Einleitungstext. | Rein über der Kanal-Tabelle, getrennt für Briefing und Alarm. | **rein** (Empfehlung angenommen) |
| V2 | Reiter Zustellung | beide | Erklärsätze zum Kanal-Layout | „Telegram die ersten 7“, „SMS 160 Zeichen“, „folgt der SMS-Auswahl“. | Rein, aber in „Inhalt je Kanal“, wo die Schnittlinie sichtbar ist. | **rein** (Empfehlung angenommen) |
| V8 | Reiter Zustellung | Orte | „Morgen = heute, Abend = morgen“ | Hinweis im Versand des Ortsvergleichs. | Rein, steht im Mockup schon als Unterzeile der Briefings. | **rein** (Empfehlung angenommen) |
| V11 | Reiter Zustellung | beide | Schnellwahl „Morgens 07:00 / Abends 18:00“ | Knöpfe zum schnellen Setzen der Uhrzeit. | Darf weg. Das Uhrzeitfeld mit Vorgabe 07:00 bzw. 18:00 reicht. | **weg** — Uhrzeitfeld bleibt (Vorgabe 07:00/18:00) |
| V14 | Reiter Zustellung | Trip | Laufzeit des Trips und „Etappen öffnen →“ | „endet …, wird in den Etappen gepflegt“. | Rein als eine Zeile unter den Briefings. | **rein** (Empfehlung angenommen) |
| V15 | Reiter Zustellung | Orte | Laufzeit „Bis auf Weiteres / Bis Datum“ | end_date. Davon hängen die automatische Pause und „Laufzeit überschritten“ ab. | Rein unter den Briefings. | **rein** (Empfehlung angenommen) |
| A11 | Reiter Zustellung | beide | „Telegram im SMS-Kurzstil“: für Briefing, Alarm oder beides? | Heute steht der Schalter beim Trip im Versand und beim Ortsvergleich unter Alarme, die Wirkung ist unklar. | Klären und dann als ein Schalter in der Telegram-Zeile. Der veraltete Hinweis auf den „Layout-Reiter“ fällt weg. | **geklärt** — `telegram_style` wirkt auf Briefing UND Alarme; ein Schalter „Kurzstil“ unter Wetter → Inhalt je Kanal → Telegram → Weitere Einstellungen |

### 3.3 Inventar: abgedeckt, geändert, bewusst entfallen (57 Zeilen)

| ID | Bereich | Kontext | Element | Klasse | Wohin im neuen Modell |
|---|---|---|---|---|---|
| K1 | Kopf | beide | Name umbenennen | abgedeckt | Kopf |
| K2 | Kopf | beide | Region | abgedeckt | Kopf |
| K3a | Kopf | Trip | Aktivitäts-Chips | bewusst entfallen | Fortbewegung + Tempo in Etappen |
| K4 | Kopf | Orte | Profil-Label, Orte-Anzahl | abgedeckt | Kopf |
| K5 | Kopf | Trip | Datum, Tage, Status, km/↑m | abgedeckt | Kopf |
| K6 | Kopf mobil | Trip | Kacheln Etappe/Briefing/Start | abgedeckt | Kopf |
| K7 | Kopf | Orte | Status-Pill, Laufzeit überschritten | abgedeckt | Kopf (hängt an V15) |
| K8 | Kopf | beide | Speicher-Chip, Feldfehler | abgedeckt | Kopf |
| K9 | Kopf | beide | „Senden“ | geändert | „Test schicken ▾“ |
| K13 | Kopf | Orte | „Setup abschließen“ | geändert | Sprung auf Zustellung |
| K16 | Reiterleiste | beide | 5 Reiter, Badges | geändert | 4 Reiter, Handoff-Badges |
| W2 | Wetter | Trip | Vorlagen + eigene | abgedeckt | Vorlage |
| W3 | Wetter | Trip | „als eigenes Profil speichern“ | abgedeckt | Vorlage |
| W5a | Wetter | Trip | Vorlagen-Name, Fehler „existiert“ | abgedeckt | Vorlage |
| W6 | Wetter | Trip | Grundauswahl | abgedeckt | Metrik-Zeilen |
| W7 | Inhalt | beide | Kanalwahl mit Limits | geändert | 4 Kanäle + Flächen |
| W8 | Inhalt | beide | Reihenfolge, Aus/Ein je Kanal | abgedeckt | Inhalt je Kanal |
| W9 | Inhalt | beide | Schnittlinie Telegram-/SMS-Limit | abgedeckt | Inhalt je Kanal |
| W10 | Inhalt | beide | Kürzel und Legende | abgedeckt | Inhalt je Kanal |
| W12 | Wetter | beide | Tagesfenster | abgedeckt | Anpassen |
| W13 | Wetter | Trip | SMS-Schwellwerte Sensibel/Standard/Robust | bewusst entfallen | Ampel |
| W14 | Wetter | Trip | Kürzel der Temperaturgrößen | geändert | in W10 |
| W16 | Wetter | Trip | „Ausblick“ an/aus | abgedeckt | 3-Tages-Ausblick |
| W20 | Wetter | beide | Amtliche Warnungen im Bericht | geändert | ein Schalter mit A1 |
| WV2 | Wetter | Orte | Metrikliste mit Auswertung | abgedeckt | Metrik-Zeilen |
| WV3 | Wetter | Orte | Mehrfach-Auswertung (Min+Max) | bewusst entfallen | fest je Metrik, Bestand prüfen |
| WV4 | Wetter | Orte | keine Vorlagen | geändert | Vorlagen neu |
| WV5 | Inhalt | Orte | Reihenfolge je Kanal | abgedeckt | Inhalt je Kanal |
| WV8 | Wetter | Orte | Stundenverlauf an/aus | abgedeckt | eigene Liste |
| WV10 | Wetter | Orte | Ausblick an/aus | abgedeckt | eigene Liste |
| V1 | Versand | beide | Kanal-Kästchen Briefing | abgedeckt | Zustellung |
| V6 | Versand | Trip | Telegram im SMS-Kurzstil | abgedeckt | Zustellung (s. A11) |
| V9 | Versand | beide | Morgen/Abend aktiv + Uhrzeit | abgedeckt | Zustellung |
| V13 | Versand | beide | „Nächstes Briefing“ | geändert | Übersicht |
| B1 | Wertebereiche | beide | Titel, Einleitung | bewusst entfallen | Ampel |
| B2 | Wertebereiche | beide | Band, Von/Bis, Gewitter-Stufen | bewusst entfallen | Ampel |
| B3 | Wertebereiche | beide | Markieren | bewusst entfallen | Ampel färbt immer |
| B4 | Wertebereiche | beide | „im Bereich = markiert“ | geändert | Ampel-Farbe im Briefing |
| B5 | Wertebereiche | beide | Metrik hinzufügen/entfernen | bewusst entfallen | Metrik-Zeilen |
| B6 | Wertebereiche | beide | Pflichtfehler | bewusst entfallen | Ampel-Prüfung |
| B7 | Wertebereiche | Orte | „kein Score · kein Rang“ | bewusst entfallen | kein Ranking |
| A1 | Alarme | beide | Amtliche Warnungen lösen Alarm aus | geändert | ein Schalter |
| A2 | Alarme | Orte | Radar-Alarm | geändert | auch Trip (N1) |
| A4 | Alarme | beide | Empfindlichkeit, Δ-Spalte | bewusst entfallen | „Alarm ab Farbe“ |
| A7 | Alarme | beide | Alarm-Kanäle | abgedeckt | Zustellung |
| A8 | Alarme | beide | Dringlichkeits-Schwelle | abgedeckt | Zustellung |
| A12 | Alarme | beide | Cooldown | abgedeckt | Zustellung → Anpassen |
| A13 | Alarme | beide | Stille Stunden (Ortszeit) | abgedeckt | Zustellung |
| A15 | Alarme | – | AlertsTab, AlertPresetSelector, AlertCard | bewusst entfallen | toter Code |
| U1 | Übersicht | beide | Kennzahlen | abgedeckt | unverändert |
| U2 | Übersicht | beide | Versand-Karte „Bearbeiten →“ | geändert | Ziel Zustellung |
| U3 | Übersicht | Orte | Wertebereiche-Karte | geändert | Ziel Wetter |
| U4 | Übersicht | Trip | „Alarm bei Δ“ | geändert | Text anpassen |
| U5 | Übersicht | beide | Versand-Historie | abgedeckt | unverändert |
| E1 | Etappen | Trip | Startzeit, Pausentag, Ankunftszeiten | abgedeckt | + Tempo/Aufstieg |
| E2 | Orte | Orte | Reihenfolge, hinzufügen/entfernen | abgedeckt | unverändert |
| X1 | Texte | beide | Verweise auf alte Reiter | geändert | Texte nachziehen |

## 4. Ampel (Fachkern)

### 4.1 Ist

- Heute gilt eine **globale** 4-Stufen-Ampel nur für **10 Metriken**, über `display_thresholds` in `src/app/metric_catalog.py` (Feld `metric_catalog.py:57`, 10 Belegungen, z.B. Temperatur `metric_catalog.py:159-162` mit `yellow/orange/red` und `yellow_lt/orange_lt/red_lt`). Sie ist Ticket für Ticket gewachsen, angefangen mit #759 (Wind, Böen, Regen, Regenwahrscheinlichkeit), danach CAPE, Temperatur, Sicht, UV und Neuschnee. Für die Nullgradgrenze wurde sie ausdrücklich gestrichen, weil eine feste Zahl nichts aussagt.
- Heutige globale Werte (= künftige Vorlage „Allgemein“): Böen 30/45/60 km/h · Wind 30/50/70 km/h · Niederschlag 1/5/10 mm · Gewitter mittel = orange, hoch = rot · CAPE 300/800/1500 J/kg · Temperatur oben 28/31/34 °C, unten 0/−5/−15 °C · Gefühlte Temperatur wie Temperatur · Sichtweite < 2000/1000/500 m · Neuschnee 10/20/30 cm · UV 3/6/8 · Regenwahrscheinlichkeit 30/60/80 %.
- Vorlagen heute: `WEATHER_TEMPLATES` (`metric_catalog.py:1296`): `alpen-trekking`, `wandern`, `skitouren`, `wintersport`, `radtour`, `wassersport`, `allgemein`. Sie wählen heute nur Metriken vor und tragen keine Grenzen.
- SMS-Kürzel kommen immer aus dem Katalog und `docs/reference/sms_format.md`. Die Metrik „Temperatur“ trägt seit #2417 AC-12 `sms_code="T"` (`metric_catalog.py:163-165`), `D` ist der Gehzeit-Höchstwert `temperature_day_high` (`sms_format.md:95`). Die Kürzel im Mockup (z.B. „Temperatur (Temp | D)“) sind nur Beispiele.

### 4.2 Soll

- Die Ampel ist **beidseitig**: unten rot < orange < gelb, oben gelb < orange < rot. Grün liegt zwischen „gelb unten“ und „gelb oben“. Ein leeres Feld heißt: auf dieser Seite keine Grenze. Prüfregeln (aus der Grenzwert-Seite): unten muss rot < orange < gelb gelten, oben gelb < orange < rot, und die unteren Grenzen dürfen nicht über den oberen liegen.
- Sie kommt aus der **Vorlage** und ist **je Trip/Ort änderbar**. Eine eigene Vorlage speichert Auswahl, Ampel und Alarmstufen zusammen (nicht Zustellung, Etappen, Orte).
- **Nullgradgrenze und Schneefallgrenze sind relativ**: Meter über der höchsten Stelle der Etappe bzw. über der Höhe des Orts, negativ heißt darunter.
- **Sonnenstunden** sind umgekehrt (weniger ist schlechter). Für den **Taupunkt** gilt eine Schwüle-Skala. **Luftfeuchte** bekommt keine eigene Ampel (über den Taupunkt bewertet).
- Die **Schneehöhe** hängt von der Vorlage ab (Skitour: wenig ist schlecht).
- **Keine Ampel** bekommen: Luftdruck, Windrichtung, Niederschlagsart, mittlere und hohe Wolken. Sie bleiben reine Anzeige.
- **CAPE** bekommt keine eigene Zeile mehr, es geht in der Gewitter-Zeile auf (A6). Es geht **wie heute** über die geeichte Leiter je Modell und Gebiet in die Gewitterstufe ein; eigene CAPE-Farbe und CAPE-Alarm entfallen (ADR-0106 P1, PO 2026-11-04). Gewitter „leicht“ ist immer gelb und alarmiert nie (ADR-0106 P2).
- **Vorboten** (ADR-0010: `humidity`, `dewpoint`, `rain_probability`, `cloud_total`, `pressure`, `wind_chill`) werden gefärbt, lösen aber **keinen Alarm** aus. Ihre Zeile zeigt „kein Alarm (Vorbote)“.

### 4.3 Erklärsätze der Metrik-Zeile (Wortlaut aus dem Mockup)

- Normal: „Alarm, wenn der Wert seit dem letzten Briefing über {X} {Einheit} steigt [oder unter {Y} {Einheit} fällt] ({Stufe}), dazu bei sehr großen Sprüngen. Entwarnung, wenn er zurückgeht.“ Dahinter: „· grün: {a} bis {b} {Einheit}“ (bzw. „grün: ab {a}“, „grün: bis {b}“, „immer grün (keine Grenze gesetzt)“).
- Gewitter: „Alarm, wenn die Gewitter-Stufe seit dem letzten Briefing auf {mittel oder hoch} steigt ({Stufe}). Entwarnung, wenn sie wieder fällt.“ Erreicht keine Farbe die Stufe: „Mit diesen Farben erreicht Gewitter nie {Stufe}, daher kein Alarm.“
- „Alarm ab: Nie“: „Kein Alarm. Die Farbe erscheint nur im Briefing.“
- Vorbote: „Nur im Briefing gefärbt. Vorboten lösen keinen Alarm aus.“
- Nur Anzeige: „Nur Anzeige: keine Ampel und kein Alarm. Roh oder Einfach stellst du unten je Liste ein.“
- Keine Grenze für die gewählte Stufe: „Für {Stufe} ist keine Grenze gesetzt, daher kein Alarm.“

Alle Sätze kommen in den Katalog, mit EN-Fassung.

### 4.4 Metriken der Ampel (Stammdaten aus der Grenzwert-Seite)

| ID | Metrik | Einheit | Seiten | Skala | alarmfähig | Vorbote | Gruppe | Bewertet wird |
|---|---|---|---|---|---|---|---|---|
| `temperature` | Temperatur | °C | beidseitig | -35 … 40 | ja | nein | Temperatur | Tageshöchst / Tagestief |
| `temperature_night` | Tiefsttemperatur Nacht | °C | beidseitig | -30 … 25 | ja | nein | Temperatur | Nacht vor der Etappe |
| `wind_chill` | Gefühlte Temperatur | °C | beidseitig | -40 … 40 | nein | ja | Temperatur | – |
| `dewpoint` | Taupunkt | °C | nur oben (zu viel) | -10 … 28 | nein | ja | Temperatur | Schwüle |
| `humidity` | Luftfeuchte | % | keine Ampel | 0 … 100 | nein | ja | Temperatur | nur Anzeige (über Taupunkt bewertet) |
| `wind` | Wind | km/h | beidseitig | 0 … 90 | ja | nein | Wind | Mittelwind |
| `gust` | Böen | km/h | nur oben (zu viel) | 0 … 110 | ja | nein | Wind | Spitze |
| `wind_direction` | Windrichtung | – | keine Ampel | 0 … 1 | nein | nein | Wind | nur Anzeige |
| `precipitation` | Niederschlag | mm | nur oben (zu viel) | 0 … 30 | ja | nein | Niederschlag | Summe |
| `rain_probability` | Regenwahrscheinlichkeit | % | nur oben (zu viel) | 0 … 100 | nein | ja | Niederschlag | – |
| `thunder` | Gewitter | – | Stufe keins·mittel·hoch | 0 … 2 | ja | nein | Niederschlag | Stufe keins · mittel · hoch |
| `visibility` | Sichtweite | m | nur unten (zu wenig) | 0 … 10000 | ja | nein | Himmel & Sicht | Minimum |
| `cloud_total` | Bewölkung | % | nur oben (zu viel) | 0 … 100 | nein | ja | Himmel & Sicht | – |
| `cloud_low` | Tiefe Wolken | % | nur oben (zu viel) | 0 … 100 | nein | nein | Himmel & Sicht | Gipfel in Wolken |
| `sunshine` | Sonnenstunden | h | nur unten (zu wenig) | 0 … 14 | nein | nein | Himmel & Sicht | Summe |
| `uv_index` | UV-Index | – | nur oben (zu viel) | 0 … 12 | ja | nein | Himmel & Sicht | Maximum |
| `freezing_level` | Nullgradgrenze | m rel. | beidseitig | -1500 … 2500 | ja | nein | Schnee & Höhe | über höchster Stelle |
| `snowfall_limit` | Schneefallgrenze | m rel. | beidseitig | -1500 … 2500 | ja | nein | Schnee & Höhe | über höchster Stelle |
| `fresh_snow` | Neuschnee | cm | nur oben (zu viel) | 0 … 60 | ja | nein | Schnee & Höhe | Summe |
| `snow_depth` | Schneehöhe | cm | beidseitig | 0 … 300 | ja | nein | Schnee & Höhe | – |

##### Alpen-Trekking (`alpen-trekking`) — Vorschlag, vom PO unverändert angenommen

| Metrik | im Briefing | unten rot < / orange < / gelb < | oben gelb > / orange > / rot > | Alarm ab |
|---|---|---|---|---|
| Temperatur (`temperature`) | **an** | -10 / -3 / 2 | 27 / 30 / 33 | Orange |
| Tiefsttemperatur Nacht (`temperature_night`) | **an** | -8 / -3 / 0 | – / – / – | Orange |
| Gefühlte Temperatur (`wind_chill`) | **an** | -15 / -8 / -2 | – / – / – | kein Alarm (Vorbote) |
| Taupunkt (`dewpoint`) | aus | – | 16 / 18 / 21 | kein Alarm (Vorbote) |
| Luftfeuchte (`humidity`) | aus | – | – | kein Alarm (Vorbote) |
| Wind (`wind`) | **an** | – / – / – | 30 / 45 / 60 | Orange |
| Böen (`gust`) | **an** | – | 35 / 50 / 70 | Orange |
| Windrichtung (`wind_direction`) | aus | – | – | kein Alarm |
| Niederschlag (`precipitation`) | **an** | – | 1 / 5 / 15 | Orange |
| Regenwahrscheinlichkeit (`rain_probability`) | **an** | – | 30 / 60 / 80 | kein Alarm (Vorbote) |
| Gewitter (`thunder`) | **an** | mittel = orange | hoch = rot | Orange |
| Sichtweite (`visibility`) | **an** | 100 / 300 / 1000 | – | Orange |
| Bewölkung (`cloud_total`) | **an** | – | 70 / 90 / – | kein Alarm (Vorbote) |
| Tiefe Wolken (`cloud_low`) | **an** | – | 50 / 80 / – | kein Alarm |
| Sonnenstunden (`sunshine`) | aus | – / 1 / 3 | – | kein Alarm |
| UV-Index (`uv_index`) | **an** | – | 6 / 8 / 10 | Nie |
| Nullgradgrenze (`freezing_level`) | **an** | -300 / 0 / 300 | – / – / – | Orange |
| Schneefallgrenze (`snowfall_limit`) | **an** | -500 / 0 / 300 | – / – / – | Orange |
| Neuschnee (`fresh_snow`) | aus | – | 5 / 10 / 20 | Orange |
| Schneehöhe (`snow_depth`) | aus | – / – / – | – / – / – | Nie |

##### Wandern (`wandern`) — Vorschlag, vom PO unverändert angenommen

| Metrik | im Briefing | unten rot < / orange < / gelb < | oben gelb > / orange > / rot > | Alarm ab |
|---|---|---|---|---|
| Temperatur (`temperature`) | **an** | -10 / -5 / 0 | 26 / 30 / 33 | Orange |
| Tiefsttemperatur Nacht (`temperature_night`) | **an** | -8 / -3 / 0 | – / – / – | Orange |
| Gefühlte Temperatur (`wind_chill`) | aus | -15 / -5 / 0 | 28 / 31 / 34 | kein Alarm (Vorbote) |
| Taupunkt (`dewpoint`) | aus | – | 16 / 18 / 21 | kein Alarm (Vorbote) |
| Luftfeuchte (`humidity`) | **an** | – | – | kein Alarm (Vorbote) |
| Wind (`wind`) | **an** | – / – / – | 30 / 50 / 70 | Orange |
| Böen (`gust`) | **an** | – | 40 / 60 / 75 | Orange |
| Windrichtung (`wind_direction`) | aus | – | – | kein Alarm |
| Niederschlag (`precipitation`) | **an** | – | 1 / 5 / 10 | Orange |
| Regenwahrscheinlichkeit (`rain_probability`) | **an** | – | 30 / 60 / 80 | kein Alarm (Vorbote) |
| Gewitter (`thunder`) | **an** | mittel = orange | hoch = rot | Orange |
| Sichtweite (`visibility`) | aus | 500 / 1000 / 2000 | – | Orange |
| Bewölkung (`cloud_total`) | **an** | – | 70 / 90 / – | kein Alarm (Vorbote) |
| Tiefe Wolken (`cloud_low`) | aus | – | 50 / 80 / – | kein Alarm |
| Sonnenstunden (`sunshine`) | **an** | – / 1 / 3 | – | kein Alarm |
| UV-Index (`uv_index`) | **an** | – | 5 / 7 / 9 | Nie |
| Nullgradgrenze (`freezing_level`) | aus | -300 / 0 / 300 | – / – / – | Orange |
| Schneefallgrenze (`snowfall_limit`) | aus | -300 / 0 / 300 | – / – / – | Orange |
| Neuschnee (`fresh_snow`) | aus | – | 10 / 20 / 30 | Orange |
| Schneehöhe (`snow_depth`) | aus | – / – / – | – / – / – | Nie |

##### Skitouren (`skitouren`) — Vorschlag, vom PO unverändert angenommen

| Metrik | im Briefing | unten rot < / orange < / gelb < | oben gelb > / orange > / rot > | Alarm ab |
|---|---|---|---|---|
| Temperatur (`temperature`) | **an** | -30 / -20 / -15 | 3 / 8 / 15 | Orange |
| Tiefsttemperatur Nacht (`temperature_night`) | **an** | -25 / -18 / -12 | 0 / 2 / 5 | Orange |
| Gefühlte Temperatur (`wind_chill`) | **an** | -35 / -25 / -15 | – / – / – | kein Alarm (Vorbote) |
| Taupunkt (`dewpoint`) | aus | – | 16 / 18 / 21 | kein Alarm (Vorbote) |
| Luftfeuchte (`humidity`) | aus | – | – | kein Alarm (Vorbote) |
| Wind (`wind`) | **an** | – / – / – | 30 / 45 / 60 | Orange |
| Böen (`gust`) | **an** | – | 40 / 55 / 70 | Orange |
| Windrichtung (`wind_direction`) | aus | – | – | kein Alarm |
| Niederschlag (`precipitation`) | **an** | – | 2 / 10 / 20 | Orange |
| Regenwahrscheinlichkeit (`rain_probability`) | aus | – | 30 / 60 / 80 | kein Alarm (Vorbote) |
| Gewitter (`thunder`) | aus | mittel = orange | hoch = rot | Orange |
| Sichtweite (`visibility`) | **an** | 200 / 500 / 1000 | – | Orange |
| Bewölkung (`cloud_total`) | **an** | – | 70 / 90 / – | kein Alarm (Vorbote) |
| Tiefe Wolken (`cloud_low`) | **an** | – | 40 / 70 / 90 | kein Alarm |
| Sonnenstunden (`sunshine`) | aus | – / 1 / 3 | – | kein Alarm |
| UV-Index (`uv_index`) | aus | – | 3 / 6 / 8 | Nie |
| Nullgradgrenze (`freezing_level`) | **an** | – / – / – | 300 / 800 / 1500 | Orange |
| Schneefallgrenze (`snowfall_limit`) | **an** | – / – / – | 0 / 300 / 800 | Orange |
| Neuschnee (`fresh_snow`) | **an** | – | 20 / 30 / 50 | Orange |
| Schneehöhe (`snow_depth`) | **an** | 15 / 30 / 50 | – / – / – | Orange |

##### Wintersport (`wintersport`) — Vorschlag, vom PO unverändert angenommen

| Metrik | im Briefing | unten rot < / orange < / gelb < | oben gelb > / orange > / rot > | Alarm ab |
|---|---|---|---|---|
| Temperatur (`temperature`) | **an** | -25 / -20 / -15 | 5 / 10 / 15 | Orange |
| Tiefsttemperatur Nacht (`temperature_night`) | **an** | -25 / -18 / -12 | 0 / 2 / 5 | Nie |
| Gefühlte Temperatur (`wind_chill`) | **an** | -30 / -22 / -15 | – / – / – | kein Alarm (Vorbote) |
| Taupunkt (`dewpoint`) | aus | – | 16 / 18 / 21 | kein Alarm (Vorbote) |
| Luftfeuchte (`humidity`) | aus | – | – | kein Alarm (Vorbote) |
| Wind (`wind`) | **an** | – / – / – | 30 / 50 / 70 | Orange |
| Böen (`gust`) | **an** | – | 40 / 60 / 80 | Orange |
| Windrichtung (`wind_direction`) | aus | – | – | kein Alarm |
| Niederschlag (`precipitation`) | **an** | – | 2 / 10 / 20 | Orange |
| Regenwahrscheinlichkeit (`rain_probability`) | aus | – | 30 / 60 / 80 | kein Alarm (Vorbote) |
| Gewitter (`thunder`) | aus | mittel = orange | hoch = rot | Orange |
| Sichtweite (`visibility`) | **an** | 200 / 500 / 1000 | – | Orange |
| Bewölkung (`cloud_total`) | **an** | – | 70 / 90 / – | kein Alarm (Vorbote) |
| Tiefe Wolken (`cloud_low`) | aus | – | 50 / 80 / – | kein Alarm |
| Sonnenstunden (`sunshine`) | **an** | – / 1 / 3 | – | kein Alarm |
| UV-Index (`uv_index`) | aus | – | 3 / 6 / 8 | Nie |
| Nullgradgrenze (`freezing_level`) | aus | -300 / 0 / 300 | – / – / – | Orange |
| Schneefallgrenze (`snowfall_limit`) | aus | -300 / 0 / 300 | – / – / – | Orange |
| Neuschnee (`fresh_snow`) | **an** | – | – / – / – | Nie |
| Schneehöhe (`snow_depth`) | **an** | 10 / 20 / 40 | – / – / – | Orange |

##### Radtour (`radtour`) — vom PO geprüft („passt“)

| Metrik | im Briefing | unten rot < / orange < / gelb < | oben gelb > / orange > / rot > | Alarm ab |
|---|---|---|---|---|
| Temperatur (`temperature`) | **an** | -5 / 0 / 5 | 28 / 32 / 35 | Orange |
| Tiefsttemperatur Nacht (`temperature_night`) | **an** | -5 / 0 / 5 | – / – / – | Nie |
| Gefühlte Temperatur (`wind_chill`) | **an** | -15 / -5 / 0 | 28 / 31 / 34 | kein Alarm (Vorbote) |
| Taupunkt (`dewpoint`) | aus | – | 16 / 18 / 21 | kein Alarm (Vorbote) |
| Luftfeuchte (`humidity`) | aus | – | – | kein Alarm (Vorbote) |
| Wind (`wind`) | **an** | – / – / – | 20 / 30 / 45 | Orange |
| Böen (`gust`) | **an** | – | 35 / 50 / 65 | Orange |
| Windrichtung (`wind_direction`) | **an** | – | – | kein Alarm |
| Niederschlag (`precipitation`) | **an** | – | 0,5 / 2 / 5 | Orange |
| Regenwahrscheinlichkeit (`rain_probability`) | **an** | – | 30 / 50 / 70 | kein Alarm (Vorbote) |
| Gewitter (`thunder`) | **an** | mittel = orange | hoch = rot | Orange |
| Sichtweite (`visibility`) | aus | 500 / 1000 / 2000 | – | Orange |
| Bewölkung (`cloud_total`) | **an** | – | 80 / 95 / – | kein Alarm (Vorbote) |
| Tiefe Wolken (`cloud_low`) | aus | – | 50 / 80 / – | kein Alarm |
| Sonnenstunden (`sunshine`) | **an** | – / 1 / 3 | – | kein Alarm |
| UV-Index (`uv_index`) | **an** | – | 6 / 8 / 10 | Nie |
| Nullgradgrenze (`freezing_level`) | aus | -300 / 0 / 300 | – / – / – | Orange |
| Schneefallgrenze (`snowfall_limit`) | aus | -300 / 0 / 300 | – / – / – | Orange |
| Neuschnee (`fresh_snow`) | aus | – | 10 / 20 / 30 | Orange |
| Schneehöhe (`snow_depth`) | aus | – / – / – | – / – / – | Nie |

##### Wassersport (`wassersport`) — Vorschlag, vom PO unverändert angenommen

| Metrik | im Briefing | unten rot < / orange < / gelb < | oben gelb > / orange > / rot > | Alarm ab |
|---|---|---|---|---|
| Temperatur (`temperature`) | **an** | 0 / 5 / 10 | 30 / 33 / 36 | Orange |
| Tiefsttemperatur Nacht (`temperature_night`) | **an** | 0 / 5 / 8 | – / – / – | Nie |
| Gefühlte Temperatur (`wind_chill`) | aus | -15 / -5 / 0 | 28 / 31 / 34 | kein Alarm (Vorbote) |
| Taupunkt (`dewpoint`) | aus | – | 16 / 18 / 21 | kein Alarm (Vorbote) |
| Luftfeuchte (`humidity`) | aus | – | – | kein Alarm (Vorbote) |
| Wind (`wind`) | **an** | – / 4 / 8 | 30 / 40 / 50 | Orange |
| Böen (`gust`) | **an** | – | 40 / 50 / 62 | Orange |
| Windrichtung (`wind_direction`) | **an** | – | – | kein Alarm |
| Niederschlag (`precipitation`) | **an** | – | 2 / 5 / 10 | Orange |
| Regenwahrscheinlichkeit (`rain_probability`) | **an** | – | 30 / 60 / 80 | kein Alarm (Vorbote) |
| Gewitter (`thunder`) | **an** | mittel = rot | hoch = rot | Orange |
| Sichtweite (`visibility`) | **an** | 500 / 1000 / 2000 | – | Orange |
| Bewölkung (`cloud_total`) | **an** | – | 80 / 95 / – | kein Alarm (Vorbote) |
| Tiefe Wolken (`cloud_low`) | aus | – | 50 / 80 / – | kein Alarm |
| Sonnenstunden (`sunshine`) | aus | – / 1 / 3 | – | kein Alarm |
| UV-Index (`uv_index`) | aus | – | 6 / 8 / 10 | Nie |
| Nullgradgrenze (`freezing_level`) | aus | -300 / 0 / 300 | – / – / – | Orange |
| Schneefallgrenze (`snowfall_limit`) | aus | -300 / 0 / 300 | – / – / – | Orange |
| Neuschnee (`fresh_snow`) | aus | – | 10 / 20 / 30 | Orange |
| Schneehöhe (`snow_depth`) | aus | – / – / – | – / – / – | Nie |

##### Allgemein (`allgemein`) — vom PO geprüft („passt“)

| Metrik | im Briefing | unten rot < / orange < / gelb < | oben gelb > / orange > / rot > | Alarm ab |
|---|---|---|---|---|
| Temperatur (`temperature`) | **an** | -15 / -5 / 0 | 28 / 31 / 34 | Orange |
| Tiefsttemperatur Nacht (`temperature_night`) | aus | -10 / -5 / 0 | – / – / – | Orange |
| Gefühlte Temperatur (`wind_chill`) | aus | -15 / -5 / 0 | 28 / 31 / 34 | kein Alarm (Vorbote) |
| Taupunkt (`dewpoint`) | aus | – | 16 / 18 / 21 | kein Alarm (Vorbote) |
| Luftfeuchte (`humidity`) | aus | – | – | kein Alarm (Vorbote) |
| Wind (`wind`) | **an** | – / – / – | 30 / 50 / 70 | Orange |
| Böen (`gust`) | **an** | – | 30 / 45 / 60 | Orange |
| Windrichtung (`wind_direction`) | aus | – | – | kein Alarm |
| Niederschlag (`precipitation`) | **an** | – | 1 / 5 / 10 | Orange |
| Regenwahrscheinlichkeit (`rain_probability`) | **an** | – | 30 / 60 / 80 | kein Alarm (Vorbote) |
| Gewitter (`thunder`) | **an** | mittel = orange | hoch = rot | Orange |
| Sichtweite (`visibility`) | aus | 500 / 1000 / 2000 | – | Orange |
| Bewölkung (`cloud_total`) | **an** | – | 60 / 85 / – | kein Alarm (Vorbote) |
| Tiefe Wolken (`cloud_low`) | aus | – | 50 / 80 / – | kein Alarm |
| Sonnenstunden (`sunshine`) | **an** | – / 1 / 3 | – | kein Alarm |
| UV-Index (`uv_index`) | aus | – | 3 / 6 / 8 | Nie |
| Nullgradgrenze (`freezing_level`) | aus | -300 / 0 / 300 | – / – / – | Orange |
| Schneefallgrenze (`snowfall_limit`) | aus | -300 / 0 / 300 | – / – / – | Orange |
| Neuschnee (`fresh_snow`) | aus | – | 10 / 20 / 30 | Orange |
| Schneehöhe (`snow_depth`) | aus | – / – / – | – / – / – | Nie |

**Lesehilfe:** „–“ in einer Grenze heißt offen. Metriken, die eine Vorlage nicht nennt, sind dort „aus“, behalten aber die Grenzen der Vorlage „Allgemein“, damit sie beim Hinzufügen („+“) sinnvoll gefärbt sind. Die einzige PO-Änderung gegenüber dem Vorschlag: **Radtour hat „Gefühlte Temperatur“ an** (Grenzen wie Allgemein). Notiz des PO zu Radtour: „Ich meine hier gibt es auch schon die Funktion ‚eigene‘. Also eigene Sets neben ‚Skifahren‘, ‚Wandern‘ etc. zu speichern unter eigenem Namen.“ ⇒ eigene Vorlagen bleiben (`SavePresetDialog`).

## 5. Mockup Fassung 3: was wo sitzt

Das Mockup (`einstellungen_neu/seiten/mockup-hub-fassung3.html`) hat oben eine Rahmenleiste (nicht Teil der App): Kontext **Trip/Orte**, Zustand **normal / lädt / Ladefehler / Konto mit Lücken**, Marken für die Abgleich-Punkte an/aus.

**Kopf (beide Kontexte):** Brotkrumen, Eyebrow, h1 30–38px mit Status-Pill (fertig, aktiv, Entwurf, pausiert, archiviert), Meta-Zeile. Rechts **⋮ (Kebab)** und **„Test schicken ▾“**.

- Test-Menü: beim Trip oben Segment „Morgen-Briefing · Abend-Briefing“ (K11), darunter je Kanal eine Zeile mit Ziel (E-Mail „an 2 Empfänger“, Telegram „@name“, SMS „+49 171 …“, Premium-SMS „inReach · über Satellit“). Gesperrte Kanäle zeigen „gesperrt: {Grund} · Im Konto {verbinden/bestätigen/prüfen} →“ (K10). Danach „Alle eingerichteten Kanäle“ und „Test-Alarm: Beispiel-Alarm mit echten Werten an alle Alarm-Kanäle“ (A14).
- Rückmeldung als Hinweis im Kopf (K12): „{Morgen-Briefing} an {Kanal} geschickt · {Ziel} · 20:41“, bei „alle“ „… geschickt: E-Mail ✓ · Telegram übersprungen (nicht verbunden) …“. Test-Alarm ohne Alarm-Kanal: „Kein Alarm-Kanal eingerichtet, der Test-Alarm ging nirgends hin.“
- Kebab (K14/K15): Aktivieren (nur Entwurf, V16) · Pausieren/Fortsetzen · Archivieren …/Reaktivieren · Löschen …, mit Bestätigung im Menü: „Löschen? ‚{Name}‘ wird endgültig gelöscht. Briefings und Alarme hören sofort auf. Das lässt sich nicht rückgängig machen.“ bzw. „Archivieren? ‚{Name}‘ verschwindet aus der Liste. Es kommen keine Briefings und Alarme mehr. Du kannst es im Archiv reaktivieren.“ Fehlerfall: „{Löschen} hat nicht geklappt: keine Verbindung zum Server. Versuch es gleich noch einmal.“
- Entwurf: neben der Pill ein Knopf „Aktivieren“ (V16). Danach: „Aktiviert. Das erste Briefing kommt morgen um 07:00.“

**Reiterleiste:** Trip „Übersicht · Etappen [4] · Wetter · Zustellung“, Orte „Übersicht · Orte [3] · Wetter · Zustellung“. Nur Unterstrich, keine Box (Atomic-Design-Soll, §7).

**Reiter Wetter** (Kopf „Wetter: Was im Briefing steht, was für dich zu viel oder zu wenig ist und ab wann du einen Alarm bekommst.“):

1. Zustände: „Lade Metriken …“ mit Platzhalterbalken; Ladefehler „Die Metriken konnten nicht geladen werden. Die Verbindung zum Server ist abgebrochen. Deine Einstellungen sind gespeichert und gehen nicht verloren. [Erneut laden]“ (W1).
2. **Vorlage**-Karte: Picker „{Vorlage} ▾ {n Abweichungen | unverändert}“, Liste „Vorlagen“ (7, je mit Kurzbeschreibung, z.B. „Alpen-Trekking: 14 Metriken · Gewitter, Böen, Nullgradgrenze“) und „Eigene“. Wechsel: „‚{neu}‘ übernehmen? Ersetzt Metrik-Auswahl, Ampel-Grenzen und Alarmstufen dieses {Trips|Orts-Briefings}. Deine {n} Abweichungen von ‚{alt}‘ gehen verloren. Zustellung, Etappen und Orte bleiben unverändert. [Übernehmen] [Abbrechen]“ (W4). Knöpfe „Als eigene Vorlage speichern“ und, bei Abweichungen, „Auf ‚{Vorlage}‘ zurücksetzen“.
3. Dialog „Als eigene Vorlage speichern“ (W5b): Name (Pflicht, „Gib der Vorlage einen Namen.“, Duplikat: „Eine Vorlage ‚{n}‘ gibt es schon. Wähle einen anderen Namen.“), Beschreibung (optional), „Als Standard für neue {Trips|Orte}“, Hinweis „Gespeichert werden Metrik-Auswahl, Ampel-Grenzen und Alarmstufen. Zustellung, Etappen und Orte gehören nicht dazu.“ Keine Zeithorizonte.
4. Kopfzeile **„Alarm ab für alle: Nie · Gelb · Orange · Rot“** mit Zähler „{x} von {y} Metriken lösen einen Alarm aus. {z} können keinen auslösen (Vorboten und reine Anzeige).“ (A5). Ist keine Metrik alarmfähig: „Keine der gewählten Metriken kann einen Alarm auslösen. Nimm z.B. Wind, Böen oder Gewitter dazu.“ (A3). Bei Gewitter setzt „Gelb“ auf „Orange“.
5. **Metrik-Zeilen**, gruppiert (Temperatur · Wind · Niederschlag & Gewitter · Himmel & Sicht · Schnee & Höhe): Knopf „−“ (aus dem Briefing nehmen), Name + Einheit + Hinweis (z.B. „km/h · Spitze“), Ampel-Leiste mit Grenzzahlen, Erklärsatz (§4.3), rechts „Alarm ab“ (oder „kein Alarm (Vorbote)“ / „kein Alarm“) und „Grenzen ändern“/„Fertig“. Aufgeklappt: Felder „unten / zu wenig: rot < · orange < · gelb <“ und „oben / zu viel: gelb > · orange > · rot >“ je nach erlaubten Seiten, Hinweis „Grün ist alles zwischen ‚gelb unten‘ und ‚gelb oben‘. Ein leeres Feld heißt: auf dieser Seite keine Grenze. Abweichend von der Vorlage ‚{Vorlage}‘.“ Gewitter: „mittel: gelb · orange · rot“, „hoch: orange · rot“, „‚keins‘ ist immer grün.“ Windrichtung: „keine Ampel, nur Anzeige“, kein „Grenzen ändern“.
6. Unter den Zeilen: **„Nicht im Briefing: + {Metrik} …“**. Hinzufügen meldet: „{Metrik} ist jetzt im Briefing und steht in allen Listen unter ‚Inhalt je Kanal und Fläche‘. Dort stellst du Roh oder Einfach ein.“ Jede Änderung (−, +, Grenze, Alarm ab, Gewitterfarbe) zählt als Abweichung.
7. Karte **Amtliche Warnungen** („im Briefing und als Alarm, sobald sie dein Gebiet betreffen“, ein Schalter; W20 + A1 zusammengelegt) und **Radar-Regen** („Alarm, wenn in der nächsten Stunde Regen auf {deine Etappe|deine Orte} zukommt“; beim Trip neu, N1).
8. Karte **„Inhalt je Kanal und Fläche“**: Untertitel „Reihenfolge und Auswahl je Kanal, dazu Ausblick [und Stundenverlauf]. Jede Liste nimmt nur aus den Metriken oben, sie kann abwählen, aber nichts hinzufügen. Je Zeile und Liste: Roh (Zahl) oder Einfach (Ampelpunkt, Symbol, Wort).“ Segment E-Mail · Telegram · SMS · Premium-SMS · 3-Tages-Ausblick · (Orte) Stundenverlauf. Kopfzeile „Metrik (Spaltenkopf in der Mail | Kürzel in SMS/Telegram) · Darstellung (Roh = Zahl · Einfach = Symbol/Ampel) · In {Kanal} (an = erscheint)“. Zeilen: Griff ⋮⋮ (ziehen zum Umsortieren), „Temperatur (Temp | T)“, Segment Roh/Einfach, Beispiel „27 °C · ● gelb“, Hinweis rechts, Schalter.
   - **Amtliche Warnungen** als feste Zeile: bei E-Mail/Telegram „steht immer zuerst, nicht verschiebbar“, bei SMS/Premium-SMS „steht immer am Ende (Warn-Block mit !) und fällt beim Kürzen als letztes weg“ (WV6).
   - **Schnittlinie:** Telegram ab Zeile 8 „nur in der Tabelle“ (Kurzübersicht = erste 7). SMS/Premium-SMS: was nicht in 160 Zeichen passt, „passt nicht mehr in 160 Zeichen“, mit Budgetzeile (Mockup-Beispiele: SMS „GR221 E2 D27 N8 W30@11 G45@14 R2@15 TH:M@15 · 43 von 160 Zeichen“, Premium „GR221 E2 D27 N8 W30@11 G45@14 · 27 von 160 Zeichen“; in der Umsetzung erzeugt der echte Renderer die Zeile).
   - **Kürzel-Legende** bei Telegram/SMS/Premium-SMS: Kürzel der gewählten Metriken, „@14 ab 14 Uhr gelb oder schlechter“, „!TS:H@14 amtliche Warnung: Gewitter, Stufe hoch, ab 14 Uhr“, „Stufen L gelb · M orange · H rot“, „WG Wind · RA Starkregen · AV4 Lawinenstufe“, „X? Warnquelle nicht erreichbar“, „Die Legende steht auch am Ende jedes Briefings.“ (W21)
   - Stundenverlauf: Sonnenstunden „gesperrt: Tagessumme, je Stunde gibt es keinen Wert“ (WV9).
   - Eingeklappt **„Weitere Einstellungen für {Kanal}“**: Erklärsatz (V2), z.B. E-Mail Trip: „Diese Liste sind die Spalten der Stundentabelle in der Mail. Beim Trip ist die Haupttabelle selbst die Stundentabelle, deshalb gibt es keine eigene Liste ‚Stundenverlauf‘.“; Orte: „Diese Liste sind die Zeilen der Vergleichstabelle. Der Stundenverlauf darunter hat eine eigene Liste.“; Telegram: „Die Kurzübersicht oben in der Nachricht zeigt die ersten 7 Zeilen, alle weiteren nur in der Tabelle darunter. Ist der Kurzstil an, bekommt Telegram den SMS-Text, dann gilt die SMS-Liste.“; SMS: „Eine SMS hat 160 Zeichen. Was nicht mehr passt, fällt weg; die Liste zeigt, ab welcher Zeile.“; Premium-SMS: „Geht über Satellit an dein inReach. 160 Zeichen, jede Nachricht kostet. Eigene, kürzere Liste als die SMS.“; Ausblick: „Kompakte Tageswerte der nächsten drei {Etappen|Tage}. Wählst du alle Zeilen ab, entfällt der Ausblick.“; Stundenverlauf: „Stunden-Tabelle unter der Vergleichstabelle. Größen ohne Stundenwert sind gesperrt.“ Dazu:
     - E-Mail: **Format** „Ausführlich (HTML) · Kompakt (Nur-Text)“ (W15, `email_format`, `models.py:1171`; Orte: „Kompakt gilt für Orte, sobald die Orts-Mail Nur-Text kann.“). Nur Trip: **Zusatzblöcke** Etappen-Kennzahlen (W17, `show_stage_stats`, `models.py:1162`), Vortag-Vergleich (W18, `show_yesterday_comparison`, `models.py:1173`), Nacht-Stundentabelle (W22, `show_night_block`, `models.py:829`).
     - Telegram: **Kurzstil** „Telegram bekommt denselben kurzen Text wie die SMS, ohne Knöpfe. Gilt für Briefing und Alarme. Die Liste oben ruht dann, es gilt die SMS-Liste.“ (A11; gesperrt, wenn Telegram nicht verbunden ist).
     - 3-Tages-Ausblick: „Erscheint im: Morgen-Briefing · Abend-Briefing“, „Ersetzt den bisherigen ‚Mehrtages-Trend‘. Vorbelegung: nur abends.“ (V12)
     - Stundenverlauf (Orte): „Stundenverlauf im Briefing“ an/aus (WV8).
9. Karte **Anpassen** (eingeklappt): **Tagesfenster** von–bis (W12, ADR-0035).

**Reiter Zustellung** („Wann die Briefings kommen und auf welchem Weg Briefings und Alarme dich erreichen.“):

1. **Morgen-Briefing** (Uhrzeitfeld 07:00 + Schalter; Trip „für die Etappe des Tages“, Orte „für heute“) und **Abend-Briefing** (18:00; Trip „für die Etappe von morgen“, Orte „für morgen“) (V8, V9, V11).
2. **Laufzeit**: Trip „{Daten}. Die Briefings enden nach der letzten Etappe. Die Daten pflegst du in den Etappen. [Etappen öffnen →]“ (V14). Orte „Bis auf Weiteres · Bis Datum“ + Datumsfeld, „Danach pausiert das Briefing von selbst. Im Kopf steht dann ‚Laufzeit überschritten‘.“ bzw. „Das Briefing läuft, bis du es pausierst.“ (V15, `end_date`).
3. Warnungen: „Kein Kanal für Briefings an. So kommt kein Briefing bei dir an. Schalte unten mindestens einen Kanal ein.“ (V7) und „Kein Kanal für Alarme an. Alarme gehen nirgends hin.“ (A9).
4. **Kanal-Tabelle**, Kopf „Briefings über {n} Kanäle · Alarme über {m} Kanäle“, „Ein Kanal ohne Verbindung ist gesperrt, bis du ihn im Konto einrichtest.“ Spalten **Kanal · Briefing · Alarme · Alarm schon ab Dringlichkeit (gering · mittel · hoch)**. Je Kanal Statuszeile mit Punkt (bestätigt/verbunden/unbestätigt/nicht verbunden, V3), Hinweis mit Konto-Link (V4: „Telegram-Chat fehlt.“, „Nummer noch nicht bestätigt.“), Premium-SMS-Status „inReach · Rückadresse gelernt {Datum} · zuletzt gemeldet {Zeit}“ bzw. „Rückadresse verfallen“ mit „Schick eine Nachricht vom Gerät, dann ist die Rückadresse wieder gültig.“ (V5, sicherheitsrelevant), Alarm gesperrt mit Grund (A10). Fußzeile: „Die SMS kostet wenig und bekommt deshalb schon Alarme ab ‚mittel‘. Die Premium-SMS geht über Satellit und meldet sich nur bei ‚hoch‘.“ (N2). Vorbelegung im Mockup: E-Mail und Telegram „gering“, SMS „mittel“, Premium-SMS „hoch“.
5. **Stille Stunden** von–bis + Schalter, „keine Alarme, sie kommen mit dem nächsten Morgen-Briefing“ (A13).
6. **Anpassen** (eingeklappt): „Mindestabstand zwischen zwei Alarmen derselben Metrik“, Minuten (A12, Karte `cooldown`; `alert_cooldown_minutes`, `models.py:1338`).

**Reiter Etappen (Trip):** Karte „Fortbewegung: zu Fuß · Rad · MTB · Ski“, „Tempo flach“ (4,0 km/h), „Aufstieg“ (300 Hm/h), „Gilt für alle Etappen, je Etappe überschreibbar (z.B. Ruhetag, Bergetappe).“ Je Etappe „Gehzeit {h:mm}“ und „Tempo ändern“. Kopf: „Das Tempo bestimmt die Gehzeiten und damit, welche Stunden je Wegpunkt bewertet werden.“ Heute: `EtappenConfig` (`models.py:413-417`) mit `speed_flat_kmh`, `speed_ascent_mh`, `speed_descent_mh` (Abstieg ist im Mockup nicht gezeigt, bleibt erhalten).

**Reiter Orte:** „Ein Ort ergibt ein Orts-Briefing. Ab zwei Orten kommt die Vergleichstabelle dazu, ohne Rangfolge.“, „+ Ort hinzufügen“, je Ort „entfernen“.

**Ohne Oberfläche (im Konzept):** K17 Umleitung alter Links (`?tab=wertebereiche` → Wetter, `?tab=alarme` → Zustellung, Listen-Eintrag „Alarme“ anpassen) · K3b Name der Vorlage ersetzt das Profil des Ortsvergleichs und steht im Mail-Kopf · B8 Migration · W5b Zeithorizonte → „alle Tage“ · V12 · A6 · V11 · A15 · Radtour mit Gefühlter Temperatur.

## 6. Aktivität heute (dreimal, verschieden benannt)

| Wo | Auswahl | Wirkt auf | Neu |
|---|---|---|---|
| Trip, Kopf (`frontend/src/lib/components/trip-detail/TripHeader.svelte`) | Trekking · Skitour · Hochtour · Klettersteig · MTB · Fahrrad 15/20/25 km/h | Gehzeit bzw. Tempo, dazu die Vorbelegung der Metrik-Vorlage | entfällt; Fortbewegung + Tempo im Reiter Etappen; „Fahrrad 15/20/25“ wird „Rad“ + Tempo |
| Wetter-Metriken, „01 Profil“ | die 7 `WEATHER_TEMPLATES` | Metrik-Vorauswahl | wird **die** Vorlage (Metriken + Ampel + Alarm ab) |
| Ortsvergleich, Kopf | Allgemein · Wintersport · Wandern · Sommer-Trekking (`profil`, `models.py:1320`; Auswertung `scheduler_dispatch_service.py:919` `_parse_activity_profile`, `src/app/loader.py:2136`) | Profil-Label, Versand, Mail-Kopf | entfällt; Name der Vorlage ersetzt das Profil (K3b) |

## 7. Atomic Design (Soll für das UI)

- **Soll:** `claude-code-handoff/current/jsx/` (`atoms.jsx`, `molecules.jsx`, `screen-trip-detail.jsx:213-231`, `screen-compare-detail.jsx:94-111`) und `current/soll/*.png`. Tokens in `docs/design-system/TOKENS.md`.
- **Reiterleiste laut Soll:** nur eine Grundlinie `--g-rule`, Reiter 13px/500, aktiv 600 mit 2px-Unterstrich `--g-accent`. Badges mono 10px, radius 3px, neutral `--g-paper-deep`/`--g-ink-3`.
- **Ist-Abweichungen:** `frontend/src/lib/components/mobile/MTabBar.svelte:82` setzt `data-slot="segmented"` und erbt dadurch die globalen Segmented-Stile (`frontend/src/app.css:502-528`): Box und Trennlinien (aus dem CSS abgeleitet, nicht im Browser geprüft). Badges sind orange Kreise. Der Seitenkopf hat h1 20px statt 30–38px. Das Segmented-Atom selbst weicht ab. `CorridorEditor` (`frontend/src/lib/components/shared/corridor-editor/`) und `AlarmeTab` (`frontend/src/lib/components/shared/AlarmeTab.svelte`) haben eigene Knöpfe statt der Atome.
- **Mobil:** Die Pill-Leiste ist eine spätere, vom PO freigegebene Entscheidung (`docs/specs/modules/mobile_tab_leisten_mtabbar.md`). Sie bleibt.
- Für die Reiterstruktur gibt es bisher kein Design-ADR (`docs/specs/modules/feat_1743_reiter_aufraeumen.md:486`: „ADR-Nr.: keine“). Das schließt ADR-0109.

## 8. Zweisprachigkeit (PO-Vorgabe 2026-11-03)

Alles, was die Scheiben an Oberfläche, Mail, Telegram, SMS-Freitext oder Hinweisen neu schreiben oder umbenennen, kommt über die Kataloge in **DE und EN** (ADR-0104). Protokoll-Token (`sms_code`, `compact_label`, Kürzel, `col_label`) werden nie übersetzt (ADR-0042). Glossar-Vorschläge für neue Begriffe (vor der ersten UI-Scheibe ins Glossar `docs/reference/i18n_glossar.md`):

| Deutsch | Englisch (Vorschlag) | Ersetzt |
|---|---|---|
| Wetter (Reiter) | Weather | Wertebereiche *(target ranges)*, Layout, Alarme |
| Zustellung (Reiter) | Delivery | Versand *(delivery)* |
| Vorlage / eigene Vorlage | template / my templates | Profil, Preset |
| Ampel | rating scale (Farben: green · yellow · orange · red) | Wertebereich, Markieren |
| Grenzen ändern | Edit limits | – |
| Alarm ab: Nie · Gelb · Orange · Rot | Alert from: Never · Yellow · Orange · Red | Empfindlichkeit entspannt/standard/sensibel |
| Nicht im Briefing | Not in briefing | – |
| Inhalt je Kanal und Fläche | Content per channel and section | Layout |
| Roh / Einfach | Raw / Simple | – |
| Weitere Einstellungen für {Kanal} | More settings for {channel} | – |
| 3-Tages-Ausblick | 3-day outlook | Mehrtages-Trend, Ausblick, 3-Tages-Vorschau |
| Test schicken | Send test | Senden, Vorschau |
| Test-Alarm | Test alert | Alarm-Vorschau |
| Orte / Orts-Briefing | Locations / location briefing | Ortsvergleich *(location comparison)* |
| Fortbewegung · Tempo flach · Aufstieg | Mode of travel · Pace on flat · Ascent rate | Aktivitäts-Chips |
| Stille Stunden | Quiet hours | – |
| Mindestabstand zwischen zwei Alarmen | Minimum gap between two alerts | Cooldown |
| Kurzstil | compact style | (Glossar hat es schon) |

## 9. Was neue ADRs braucht (Entwürfe angelegt)

1. **ADR-0106 Profil-Ampel als einzige Bewertung.** Ersetzt Wertebereiche/corridors, SMS-Schwellwerte und die Δ-Empfindlichkeitsstufen. Alarm bei Stufenwechsel oder großem Sprung gegen das letzte Briefing bzw. den Anker (ADR-0009 und ADR-0056 bestätigt). Bei Annahme: ADR-0043 abgelöst, ADR-0013 teilweise abgelöst, ADR-0040 bleibt abgelöst, ADR-0046 und ADR-0010 bestätigt.
2. **ADR-0107 „Orte“ mit 1..n Orten** statt Ortsvergleich mit ≥3. Berührt `.claude/hooks/email_spec_validator.py` (`min_locations: int = 3`, Zeilen 1096 und 1129; Prüfung Zeile 980) und das Compare-Mail-Template. ADR-0097 bleibt.
3. **ADR-0108 Vorlage und Tempo getrennt.** Die Aktivitäts-Chips im Kopf entfallen.
4. **ADR-0109 Reiterstruktur Übersicht · Etappen/Orte · Wetter · Zustellung**, inklusive „Inhalt je Kanal und Fläche“ und Reiterleiste nach Atomic-Design-Soll. Präzisiert ADR-0097 Punkt 1 (Tab-Organismen).

## 10. Freigegebener Scheiben-Schnitt (PO 2026-11-03)

Freigegeben: der Vorschlag aus dem Stand, **Scheibe 3 geteilt** in 3a und 3b, also 10 Scheiben. Alles DE/EN.

| # (Issue) | Scheibe | Inhalt (Kurz) | Abhängig von | Abgleich-Punkte |
|---|---|---|---|---|
| S1 #2792 | Beidseitige Profil-Ampel im Datenmodell | Ampel je Trip/Ort aus der Vorlage, Vorlagen mit Grenzen (§4.4), alle Renderer aller vier Kanäle lesen sie, Migration der Bestandsdaten (B8, W5b-Altwerte), eigene Vorlagen speichern Ampel + Alarmstufen | ADR-0106 angenommen | B8, W5b (Migration), A6 (CAPE), K3b (Datenteil) |
| S2 #2793 | Alarm nach Stufenwechsel plus Sprung | „Alarm ab“ je Metrik, Entwarnung, Sprung durch System, Abbildung der alten Stufen, Vorboten ohne Alarm, alle Kanäle | S1 | A3 (Logik), A4 |
| S3a #2794 | Reiter Wetter nach Atomic-Design-Soll | Reiterleiste, Vorlage-Picker + Speichern, Metrik-Zeilen mit Ampel-Leiste, Grenzen ändern, −/+, Alarm ab für alle, amtliche Warnungen/Radar-Karte, Anpassen/Tagesfenster, Wertebereiche/Alarme/Layout-Reiter weg, Umleitungen, toter Code weg | S1, S2 | W1, W4, W5b (UI), A3, A5, K16, K17, U3, U4, X1, A15, W20/A1 |
| S3b #2795 | Inhalt je Kanal und Fläche + Reiter Zustellung | Kanal-Listen mit Roh/Einfach, Schnittlinie, Legende, Weitere Einstellungen, 3-Tages-Ausblick vereinheitlicht, Kurzstil, Zustellung mit Uhrzeiten, Laufzeit, Kanal-Tabelle, Stille Stunden, Cooldown | S3a | W7–W11, W15, W17–W19, W21, W22, WV5, WV6, WV8–WV10, V1–V4, V7–V9, V11–V15, A7–A13, U2, K13, V13 |
| S4 #2796 | Vorlage und Tempo trennen | Kopf-Chips weg (Trip und Orte), Fortbewegung + Tempo im Reiter Etappen, je Etappe überschreibbar, Profil des Ortsvergleichs über die Vorlage | S3a | K3a, K3b, K4, E1, WV4 |
| S5 #2797 | „Test schicken ▾“ | Kanal-Menü mit Ziel und Sperre, Morgen/Abend, Alle, Test-Alarm, Rückmeldung, Kebab, Aktivieren | – (nach S3a empfohlen) | K9–K12, K14, K15, A14, V16, K7 |
| S6 #2798 | „Orte“ mit 1..n Orten | Umbenennung, Ein-Ort-Briefing (alle Kanäle), Vergleich ab 2, kein Ranking, Validator-Anpassung | S3b | B7, E2 |
| S7 #2799 | Ampel für weitere Metriken | Sonnenstunden (umgekehrt), Bewölkung, tiefe Wolken, Taupunkt (Schwüle), Schneehöhe (je Vorlage), Nullgrad-/Schneefallgrenze relativ zur höchsten Stelle bzw. Ortshöhe | S1 (S3a für die Zeilen) | – |
| S8 #2800 | Radar-Alarm für Trips | Regen in der nächsten Stunde auf der Etappe, alle Kanäle, Schalter im Reiter Wetter | S2 | N1, A2 |
| S9 #2801 | Premium-SMS mit eigener Inhaltsliste | eigene Liste im Reiter Premium-SMS, Renderer nutzt sie, Dringlichkeits-Vorbelegung SMS mittel / Premium-SMS hoch | S3b | N2 |

Jede Scheibe folgt dem OpenSpec-Workflow (`/10-context` … `/70-deploy`): eigene Spec mit deutschen ACs (Freigabe durch den PO), TDD, Adversary mit Mutations-Gegenprobe, E2E auf Staging. Datenändernde Scheiben (S1, S2, S3b, S4, S6, S9) sind Daten-Schema-Reworks (Read-Modify-Write mit Merge, ADR-0101; Pre-Snapshot-Hook). Jeder datenbewegende Endpoint wird mit zwei Nutzern getestet. Wer eine Mail anfasst, nimmt den Validator des Pfads mit.
