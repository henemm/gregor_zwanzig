# ADR-0052: Amtliche Warn-Mail übernimmt die Nowcast-Datenzeilen-Bauform und bekommt einen eigenen Klartext-Teil (schreibt ADR-0033 fort)

- **Status:** Akzeptiert
- **Datum:** 2026-08-13
- **Bezug:** Issue #1744 Scheibe A2, Spec
  `docs/specs/modules/fix_1744_alarm_format_angleichen.md` (AC-8 bis AC-14).
  **Schreibt ADR-0033 fort** (bleibt inhaltlich bindend — geändert wird nur
  der Träger der Zusicherung). Vorgänger: Scheibe A1 (Ortssprache, live über
  `0861a9a8`).

## Kontext

Scheibe A1 von #1744 vereinheitlichte die Ortssprache zwischen den beiden
Trip-Alarm-Mailtypen (Nowcast/Abweichung und amtliche Warnung). Der
Mail-Körper selbst blieb dabei in zwei unterschiedlichen Bauformen bestehen:

- Der Nowcast rendert jede Fakten-Angabe als eigene
  `<table role="presentation">` mit Label links, Wert rechtsbündig
  (`_datarow_html`, `src/output/renderers/alert/render.py`), bewusst so wegen
  Outlook-Kompatibilität.
- Die amtliche Warnung rendert stattdessen ein CSS-Grid `<div class="warn">`
  mit einem einzigen Facts-Block, in dem Label und Wert als
  `<span class="k">…</span> … <br>` inline stehen — plus eine eigene,
  getönte Quelle-Box (`_standalone_src_html`) unterhalb der Warn-Karte.

Zwei Mails zum selben Ereignis waren dadurch nicht nur in der Ortssprache
(A1), sondern auch im Aufbau kaum als verwandt erkennbar.

Zusätzlich hatte die amtliche Warn-Mail bislang **keinen bewusst gebauten
Klartext-Teil**: `send_official_alert` übergab `EmailOutput.send(...)` kein
`plain_text_body`, weshalb `src/output/channels/email.py` den Text per Regex
aus dem HTML strippte. Aus dem CSS-Grid entstand dabei Zeilensalat. Der
Nowcast dagegen baut HTML und Klartext in derselben Funktion aus denselben
Label-Wert-Tupeln und übergibt den Klartext ausdrücklich.

Der Warn-Mail-Wächter (`.claude/hooks/official_alert_mail_validator.py`)
verlangte zudem `class="src"` als einzigen erkannten Träger der
Quellenangabe (Regel S-1, `_REQUIRED_CLASSES`) — ein Umbau, der die Box
auflöst, hätte ihn ohne Anpassung eine sachlich korrekte Mail fälschlich
ablehnen lassen (dieselbe Falle wie in A1 bei `_SEGMENT_RE`, das `🏁 Ziel`
nicht kannte).

## Entscheidung

**1. Gemeinsamer Mail-Aufbau.** Alle Trip-Alarm-Mails folgen derselben
Bausteinfolge: Kennzeichen, Überschrift, Warnstufen-Skala (nur amtliche
Warnung), Datenzeilen, Sperrzeit-Hinweis (nur Nowcast), Stand-Zeile,
Herkunfts-Fußzeile. Die Fakten der amtlichen Warnung (Gefahrenart,
Gültigkeitsfenster, Ortsbezug, Quelle) stehen jetzt als Datenzeilen in der
Bauform des Nowcasts — technisch über `_standalone_datarow_html`/
`_standalone_facts_html` (`official_alerts.py`), die dasselbe
Label-links/Wert-rechts-Muster wie `render.py::_datarow_html` nachbilden.
Die Warnstufen-Skala (GELB · ORANGE · ROT mit „niedrigste von drei") bleibt
als eigenständige **Skala** erhalten — sie trägt eine Einordnung, die eine
bloße Textzeile verlieren würde. Die eigene Quelle-Box entfällt ersatzlos
(`_standalone_src_html` trägt keine `class="src"` mehr); die Quelle ist eine
Datenzeile wie die übrigen.

**2. Eigens gebauter Klartext-Teil.** Die amtliche Warn-Mail bekommt mit
`render_official_alert_mail_plain()` einen eigenen Klartext, gebaut aus
denselben Label-Wert-Tupeln und in derselben Reihenfolge wie das HTML —
analog dem Nowcast. Sowohl der Trip-Versand (`send_official_alert`,
`src/services/notification_service.py`) als auch der Compare-Versand
(`_dispatch_compare_official_email`) übergeben ihn als `plain_text_body`.
Der bisherige, aus dem HTML gestrippte Text entfällt für diesen Mailtyp.

`render_official_alert_notice_plain()` bleibt unverändert bestehen — sie
bedient den in eine ANDERE Mail eingebetteten Warnblock, nicht die
eigenständige Warn-Mail, und ist nicht Gegenstand dieser Entscheidung.

**3. ADR-0033 bleibt bindend.** Die Warn-Karte nennt weiterhin
ausschließlich den betroffenen Umfang; `free_chips` bleibt im Trip-Pfad
`[]`. Mit dieser Entscheidung ändert sich nur der **Träger** der Zusicherung
(Datenzeile statt Grid-Zelle), nicht die Zusicherung selbst.

**4. Additive Wächter-Erweiterung.** `official_alert_mail_validator.py`
prüfte die Quellenangabe bislang ausschließlich über die CSS-Klasse `src`
(Regel S-1, Pflichtklassen-Set). Diese Prüfung wird um eine zweite gültige
Form ergänzt (neue Regel S-1b): eine Quellenangabe gilt jetzt auch als
erbracht, wenn im Text eine Datenzeile `Quelle: …` steht. `src` bleibt eine
gültige Alternative — keine bestehende Form wird entfernt oder gelockert,
eine Mail ganz ohne Quellenangabe fällt weiterhin durch (S-1b UND
zusätzlich weiterhin P-4, das die Literale „Quelle:" und „abgerufen bei"
im Text verlangt).

## Verworfene Alternativen

- **Quelle-Box beibehalten, nur die übrigen Fakten umbauen.** Verworfen: die
  Zielreihenfolge kennt die Box als eigenen Baustein nicht — sie hätte als
  Fremdkörper unterhalb der Datenzeilen gestanden, während der Nowcast keine
  Entsprechung hat. Zwei Bauformen wären damit auf eine reduziert, aber
  nicht auf null.
- **Wächter-Regel S-1 lockern** (`src` ersatzlos aus den Pflichtklassen
  entfernen, ohne neue Alternative). Verworfen: eine Mail ganz ohne
  erkennbare Quellenangabe hätte den Wächter dann unbemerkt bestanden —
  genau die Lockerung, die die Projekt-Regel „additiv erweitern, nie
  lockern" (bereits in A1 an `_SEGMENT_RE` angewandt) ausschließt.
- **Klartext-Lücke unverändert lassen, erst in einer Folge-Scheibe
  schließen.** Verworfen (PO-Entscheid 2026-08-12): Die Label-Wert-Zeilen
  entstehen für das HTML ohnehin neu; der Klartext fällt aus denselben
  Tupeln praktisch kostenfrei ab. Ihn später nachzuziehen hieße, dieselbe
  Struktur ein zweites Mal aufzubrechen.

## Konsequenzen

- **Positiv:** Beide Trip-Alarm-Mailtypen sind jetzt strukturell als
  verwandt erkennbar — gleiche Bausteinfolge, gleiche Datenzeilen-Bauform.
  Die amtliche Warn-Mail hat erstmals einen belastbaren Klartext-Teil
  (vorher: aus dem HTML gestrippter Zeilensalat).
- **Negativ / Preis:** Vier Bestandstestdateien mussten auf die neue
  Bauform nachgezogen werden (`test_official_alert_warn_section.py`,
  `test_official_alert_subject_label_fidelity.py`,
  `test_official_alert_standalone_render.py`,
  `test_official_alert_mail_validator.py`) — ihre Selektoren prüften
  bislang `.src`/CSS-Grid-Struktur, jetzt Datenzeilen-Zellen.
- **Folgepflichten:** Neue Änderungen an der amtlichen Warn-Mail dürfen
  `free_chips` im Trip-Pfad weiterhin nicht befüllen (ADR-0033 unverändert
  bindend). Ein Wächter, der gültige Formen aufzählt (wie
  `official_alert_mail_validator.py` S-1/S-1b oder
  `radar_alert_mail_validator.py`), wird bei künftigen Umbauten **additiv
  erweitert**, nie durch Streichen bestehender Formen „gelockert" —
  Präzedenzfall bereits in A1 (`_SEGMENT_RE`).
