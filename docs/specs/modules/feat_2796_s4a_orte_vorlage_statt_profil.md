---
entity_id: feat_2796_s4a_orte_vorlage_statt_profil
type: module
created: 2026-11-17
updated: 2026-11-17
status: approved
version: "1.0"
tags: [hub, kopf, orte, vergleich, vorlage, profil, versand, mail, i18n, epic-2791]
---

# Einstellungen neu S4a: Orts-Vergleich — Profil-Kacheln im Kopf entfallen, die Vorlage ersetzt das Profil (#2796)

## Approval

- [x] Approved v1.0, Freigabe durch den PO am 2026-11-17 (AskUserQuestion: „Freigabe“)

## Purpose

Im Kopf des Orts-Vergleichs stehen unter Titel und Regionszeile noch die vier Profil-Kacheln „Allgemein · Wintersport · Wandern · Sommer-Trekking“ (am Handy als Knopf „Profil ▾“). Mockup Fassung 3 zeigt dort keine Auswahl; der PO hat das am 2026-11-17 bemängelt (Kommentar in #2796). ADR-0108 Punkt 3 legt fest: Die Profil-Chips im Kopf der Orte entfallen, der **Name der Vorlage** ersetzt das bisherige `profil` im Kopf, beim Versand und im Mail-Kopf (Abgleich-Punkt K3b, PO-Entscheidung „rein“).

Heute steuert `profil` beim Versand noch zwei Dinge, obwohl die Ampel schon aus der Vorlage kommt (S1, #2792): die Bewertung je Ort (`calculate_score`, entscheidet den „Top-Ort“) und die Kennzeile im Mail-Kopf und im Abo-Fuß („ORTS-VERGLEICH · WINTERSPORT · PISTE“, „3 Orte · Profil WINTERSPORT · PISTE“), dazu Farbakzent und Symbol der Mail. Nach dieser Scheibe liest alles davon die aufgelöste Vorlage. `profil` bleibt gespeichert, ist aber keine sichtbare Auswahl mehr.

Grundlagen: Issue #2796, ADR-0108 (Vorlage und Tempo getrennt), ADR-0106 (Vorlage trägt die Ampel), ADR-0097 (geteilter Code Trip/Orte), ADR-0095 (Kanal-Parität), ADR-0104 (zweisprachig), ADR-0101 (Read-Modify-Write), Spec `feat_2792_s1_profil_ampel.md` §3/§4 (Auflösung `profil` → Vorlage, Migration), Spec `feat_2913_c2_seitenkopf.md` AC-15 (Profil-Zeile bewusst bis #2796 stehen gelassen), Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html`.

## Zuschnitt (Tech-Lead-Entscheidung)

#2796 wird in zwei Scheiben geliefert:

| Scheibe | Inhalt | Abgleich-Punkte |
|---|---|---|
| **S4a (diese Spec)** | Orts-Vergleich: Profil-Kacheln und Profil-Knopf im Kopf entfallen; Vorlage ersetzt `profil` in Versand-Bewertung, Mail-Kopf, Abo-Fuß, Übersichts-Karte „Wetter“ und Listenkarte. | K4, K3b |
| **S4b (eigene Spec)** | Trip: Aktivitäts-Chips im Kopf entfallen; Karte „Fortbewegung und Tempo“ im Reiter Etappen mit Überschreibung je Etappe; Migration Trip-Aktivität → Fortbewegung + Tempo. | K3a, E1, Umfang 2/3/5 |

Gründe: (1) Die Orte-Kacheln sind nur noch ein Rest — die Vorlage existiert für Orte seit S3a und die Daten sind seit S1 schon übertragen. Die Scheibe ist klein und behebt genau den bemängelten Punkt. (2) Die Trip-Chips tragen heute das Tempo; sie dürfen erst entfallen, wenn die Tempo-Karte im Reiter Etappen steht. Das ist der größere, riskantere Teil (Gehzeiten, bewertete Stunden je Wegpunkt) und bekommt eine eigene Spec und eigene PO-Freigabe. (3) Beide Scheiben sind einzeln auslieferbar und einzeln rücknehmbar.

Im geteilten Kopf-Baustein (`SubscriptionHeader`) wird die Profil-Auswahl deshalb **optional**: Ohne Auswahlliste zeichnet er weder Kacheln noch Knopf. Der Trip übergibt sie in S4a weiter, der Orts-Vergleich nicht mehr. Damit entsteht keine Compare-eigene Kopf-Komponente (Pendant-Sperre).

## Source

| Datei | Änderung |
|---|---|
| `frontend/src/lib/components/shared/subscription-header/SubscriptionHeader.svelte` | Profil-Kacheln, Profil-Knopf und Profilname in der Regionszeile nur, wenn eine Auswahlliste übergeben wird |
| `frontend/src/routes/compare/[id]/+page.svelte` | keine Profil-Props mehr an den Kopf, kein Speicherweg `profil` aus dem Kopf |
| `frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts` | Karte „Wetter“: Titel = Name der aufgelösten Vorlage |
| `frontend/src/lib/components/organisms/SubscriptionCard.svelte` | Listenkarte Orte: „{n} Orte · {Vorlagenname}“ |
| `src/app/ampel.py` | neue reine Funktion `profile_for_template(template_id)` (Vorlage → Bewertungsprofil) |
| `src/services/scheduler_dispatch_service.py`, `src/services/compare_preview_service.py` | Bewertungsprofil aus der aufgelösten Vorlage statt aus `profil` |
| `src/output/renderers/email/compare_html.py` | Kennzeile im Kopf und Abo-Fuß: Vorlagenname statt Profil-Eyebrow |
| `src/i18n/messages/{de,en}/vergleich.json` | `vergleich.kopf.profil` → „Vorlage“/„Template“; `vergleich.fuss.abo_zeile` → „{n} Orte · Vorlage {vorlage}“ / „{n} locations · Template {vorlage}“ |
| Goldens/Tests der Compare-Mail, `.claude/hooks/email_spec_validator.py` (falls er Kopf/Fuß prüft) | nachziehen |

## Estimated Scope

Ca. 150–250 Zeilen Code ohne Tests und Goldens; Frontend + Python-Core; Go unverändert. Scope für den Deploy: full-stack.

## Dependencies

- S1 (#2792, geschlossen): `display_config.ampel.template` je Vergleich, Auflösung `ampel.template` → `preset_name` → `profil` → „allgemein“ (`app/ampel.py:_aufloesen`, Frontend `vorlageIdFuer`), Migration `scripts/migrate_2792_profil_ampel.py` hat für alle Bestands-Vergleiche die Vorlage aus `profil` geschrieben.
- S3a (#2794, geschlossen): Vorlagen-Auswahl im Reiter Wetter für Orte; Vorlagennamen zweisprachig (`vorlageAnzeigename`, Katalog `mail.vorlage.<id>`).

## Implementation Details

### 1. Kopf (Frontend)

- `SubscriptionHeader`: `profileOptions` wird optional (Default leer). Ist die Liste leer, entfallen Desktop-Kacheln (`*-profil-option-*`), Handy-Knopf und -Auswahl (`*-profil-knopf`, `*-profil-auswahl`) sowie der Zusatz „ · {Profil}“ in der Regionszeile. Der Trip-Kopf (`TripHeader`) bleibt in S4a byte-gleich.
- Seite Orts-Vergleich: übergibt `profile`, `profileOptions`, `profileLabel` nicht mehr; der Speicherweg `profil` aus dem Kopf entfällt (`KOPF_RUMPF.profile`, Konflikt-Schlüssel `kopf-profil`). Die Orte-Anzahl bleibt in der Meta-Zeile (Mockup: „3 Orte · Vergleichstabelle · Morgen-Briefing 07:00“).
- **Kein Vorlagenname im Kopf.** Das Issue nennt ihn als Möglichkeit („im Kopf“); das Zielbild Mockup Fassung 3 zeigt im Orte-Kopf aber keine Vorlage, die steht oben im Reiter Wetter. Das Mockup gewinnt (PO-Hinweis 2026-11-17: „entspricht nicht dem Zielbild“).

### 2. Bewertungsprofil aus der Vorlage (Python)

`profile_for_template(template_id) -> ActivityProfile` in `app/ampel.py`:

| Vorlage | Bewertungsprofil |
|---|---|
| `wintersport`, `skitouren` | WINTERSPORT |
| `wandern` | WANDERN |
| `alpen-trekking` | SUMMER_TREKKING |
| `allgemein`, `radtour`, `wassersport`, unbekannt | ALLGEMEIN |

Versand (`scheduler_dispatch_service`) und Vorschau (`compare_preview_service`) rufen `profile_for_template(template_id_for(preset))` statt `_parse_activity_profile(preset["profil"])`. Für jeden Vergleich, dessen Vorlage aus seinem `profil` stammt (Migration S1 oder Rückfallkette), ist das Ergebnis identisch zu heute: `wintersport`→`wintersport`→WINTERSPORT, `wandern`→`wandern`→WANDERN, `summer_trekking`→`alpen-trekking`→SUMMER_TREKKING, `allgemein`→`allgemein`→ALLGEMEIN. Anders wird es nur, wenn der Nutzer im Reiter Wetter bewusst eine andere Vorlage gewählt hat — dann folgt die Bewertung jetzt dieser Wahl (gewollt, ADR-0108). Der Pfad des Validator-Renderdienstes (`validator_render_service`, Testmail mit festem Profil) bleibt unverändert.

### 3. Mail-Kopf und Abo-Fuß (Python)

- Kennzeile über dem Titel: „ORTS-VERGLEICH · {Vorlagenname}“ statt „ORTS-VERGLEICH · {Profil-Eyebrow}“ (z. B. „ORTS-VERGLEICH · Wintersport“; EN „LOCATION COMPARISON · Winter sports“). Vorlagenname = `t(vorlage_label_schluessel(template_id), lang)`, dieselbe Quelle wie die Kopfzelle.
- Kopfzelle „Profil“ heißt „Vorlage“ (EN „Template“, Glossar), Wert unverändert der Vorlagenname.
- Abo-Fuß: „{n} Orte · Vorlage {Vorlagenname}“ (EN „{n} locations · Template {Vorlagenname}“).
- Farbakzent und Symbol der Mail kommen aus `profile_signature(profile_for_template(…))`.
- Vergleichs-SMS, -Telegram und Premium-SMS zeigen heute kein Profil und auch künftig keine Vorlage: Der Name ist ein Metadatum, keine Antwort auf eine Nutzerfrage; die Bewertung (Ampel) ist in allen vier Kanälen dieselbe (ADR-0095, wie S1 §3).
- Der Klartext-Teil der Vergleichsmail (`render_comparison_text`) zeigt heute kein Profil; unverändert.

### 4. Übersicht und Liste (Frontend)

- Hub-Übersicht, Karte „Wetter“ (Orte): Titel = Anzeigename der aufgelösten Vorlage (`vorlageIdFuer` + `vorlageAnzeigename`, Sprache des Nutzers) statt Profilname.
- Listenkarte eines Orts-Vergleichs (`SubscriptionCard`): „{n} Orte · {Vorlagenname}“ statt „{n} Orte · {Profilname}“.
- Sind die Vorlagen (noch) nicht geladen, wird die Vorlagen-ID ohne Bekanntheitsprüfung über die Rückfallkette bestimmt und ihr Katalogname gezeigt; nie ein leerer Titel, nie ein Katalogschlüssel.

### 5. Daten

Keine neue Migration und kein Schreibzugriff auf Bestandsdaten. Begründung: Die Migration aus S1 (`migrate_2792_profil_ampel.py`) hat für jeden Bestands-Vergleich `display_config.ampel.template` aus `profil` geschrieben; Vergleiche ohne Vorlage (z. B. später angelegt ohne Reiter Wetter) lösen über die bestehende Rückfallkette `profil` → Vorlage auf, in Python und im Frontend gleich. `profil` bleibt als Feld gespeichert (Go-Modell unverändert, ADR-0101: nichts wird gelöscht) und ist nur noch Rückfall-Quelle. Der Hub schreibt `profil` nicht mehr. Die Anlege-Kette (`CompareNewEditor`, Aktivitätsprofil als Vorbelegung der Vorlage) bleibt in S4a unverändert und wird mit S4b zusammen bereinigt (Folge-Issue).

### 6. Abgleich gegen das Mockup

Nach dem Staging-Deploy `npm run elementliste:abgleich -- --scope orte/zustellung` und `--scope orte/wetter` (DE und EN): Im Abschnitt `kopf` gibt es keine Profil-Elemente mehr als `zusaetzlich`. Prüf-Agent `mockup-bildpruefer` mit Mockup- und Staging-Bild des Orte-Kopfs (Desktop 1280 und Handy 390), höchstens zwei Runden.

## Expected Behavior

- **Input:** Orts-Vergleich mit `profil` und/oder `display_config.ampel.template`.
- **Output:** Kopf ohne Profil-Auswahl; Versand, Vorschau und Mail nutzen die aufgelöste Vorlage; Name der Vorlage in Mail-Kopf, Abo-Fuß, Übersicht und Listenkarte.
- **Side effects:** keine Datenänderung; `profil` wird vom Hub nicht mehr geschrieben.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer öffnet einen Orts-Vergleich im Hub am Computer (1280 px), egal welcher Reiter / When der Kopf unter Titel und Regionszeile betrachtet wird / Then gibt es dort keine Profil-Kacheln („Allgemein · Wintersport · Wandern · Sommer-Trekking“) und hinter der Region keinen Profilnamen mehr; Titel, Region, Status, Aktionen und die Meta-Zeile mit der Orte-Anzahl sind unverändert da.
  - Test: E2E (Playwright, 1280×900, DE und EN) — keine `compare-hub-profil-option-*`, Regionszeile ohne Profilnamen, Meta-Zeile mit „{n} Orte“; Unit am `SubscriptionHeader` ohne `profileOptions`.
- **AC-2:** Given derselbe Orts-Vergleich am Handy (390 px) / When der Kopf betrachtet wird / Then gibt es keinen Knopf „Profil ▾“ und keine Profil-Auswahl mehr.
  - Test: E2E 390×844 — kein `compare-hub-profil-knopf`, kein `compare-hub-profil-auswahl`.
- **AC-3:** Given ein Trip im Hub / When der Kopf betrachtet wird / Then sind die Aktivitäts-Chips (Computer) bzw. der Aktivitäts-Knopf (Handy) in dieser Scheibe unverändert da und speichern wie bisher (ihr Wegfall gehört zu S4b, weil sie das Tempo tragen).
  - Test: bestehende Unit-/E2E-Tests des Trip-Kopfs bleiben unverändert grün.
- **AC-4:** Given ein Orts-Vergleich mit `profil` „wintersport“ und Vorlage „wintersport“ (wie nach der Migration aus S1) / When das Briefing versendet wird / Then ist die Bewertung je Ort und damit der Top-Ort identisch zum Stand vor der Änderung, und Kennzeile, Kopfzelle und Abo-Fuß der Mail nennen den Vorlagennamen: DE „ORTS-VERGLEICH · Wintersport“, Zelle „Vorlage: Wintersport“, Fuß „{n} Orte · Vorlage Wintersport“; EN entsprechend mit „Template“ und dem englischen Vorlagennamen.
  - Test: Unit über den echten Versandweg (`scheduler_dispatch_service`, gerenderte Mail DE und EN); Gleichheit des Bewertungsprofils für alle vier alten Profile (`wintersport`, `wandern`, `summer_trekking`, `allgemein`) gegen die bisherige Zuordnung; E2E `email_spec_validator.py` gegen die echt zugestellte Staging-Mail.
- **AC-5:** Given ein Orts-Vergleich mit `profil` „wandern“, bei dem der Nutzer im Reiter Wetter die Vorlage „Wintersport“ gewählt hat / When das Briefing versendet wird oder die Vorschau gerendert wird / Then folgen Bewertung, Farbakzent und Name in der Mail der Vorlage „Wintersport“ und nicht dem alten Profil „Wandern“.
  - Test: Unit Versand und Vorschau mit abweichendem `profil` und `ampel.template` (wirkt dort, wo bewertet und gerendert wird).
- **AC-6:** Given ein Orts-Vergleich ohne gespeicherte Vorlage, nur mit `profil` „summer_trekking“ / When versendet wird / Then gilt die Vorlage „Alpen-Trekking“ (Name in der Mail, Bewertung wie bisher Sommer-Trekking); ohne `profil` und ohne Vorlage gilt „Allgemein“.
  - Test: Unit über `profile_for_template(template_id_for(…))` und gerenderte Mail.
- **AC-7:** Given der Nutzer öffnet die Übersicht eines Orts-Vergleichs bzw. die Liste seiner Orts-Vergleiche / When die Karte „Wetter“ bzw. die Listenkarte betrachtet wird / Then steht dort der Name der aktuellen Vorlage in seiner Sprache (z. B. „Wintersport“ / „Winter sports“) und nicht mehr der Profilname; nach einem Vorlagenwechsel im Reiter Wetter zeigt die Übersicht den neuen Namen.
  - Test: Unit `hubUebersichtModell` und `SubscriptionCard` (DE/EN, abweichendes `profil` vs. Vorlage); E2E Vorlage wechseln → Übersicht neu laden → neuer Name.
- **AC-8:** Given zwei verschiedene Nutzer mit je einem Orts-Vergleich (unterschiedliche Vorlagen) / When beide ihr Briefing auslösen / Then trägt jede Mail den Vorlagennamen ihres eigenen Vergleichs und geht nur an die Empfänger dieses Nutzers; gespeicherte Daten (`profil`, `display_config`) beider Nutzer sind danach unverändert.
  - Test: Unit/Integration mit zwei `user_id`, Vergleich der Preset-Dateien vor und nach dem Versand.
- **AC-9:** Given alle in dieser Scheibe neuen oder geänderten Texte / When die Kataloge geprüft werden / Then stehen sie in DE und EN, die Platzhalter sind in beiden Sprachen gleich, „Vorlage“ ist mit „template“ übersetzt (Glossar), und Vorlagen-IDs erscheinen nie übersetzt in Daten oder Protokoll.
  - Test: bestehende Katalog-Paritätstests; Unit auf die beiden geänderten Schlüssel.

## Known Limitations

- Eigene Vorlagen (vom Nutzer gespeichert) erscheinen in der Mail mit dem Namen ihrer Grund-Systemvorlage, weil das Abo nur die Vorlagen-ID speichert, nicht die Herkunft „eigene Vorlage X“. Unverändert gegenüber heute (Kopfzelle zeigt das schon so).
- Die Anlege-Kette des Orts-Vergleichs fragt weiterhin ein Aktivitätsprofil als Vorbelegung ab; Bereinigung mit S4b (Folge-Issue).
- Trip-Aktivitäts-Chips bleiben bis S4b.

## Architektur-Entscheidung (ADR)

Keine neue ADR: Umsetzung von ADR-0108 Punkt 3 (Orte-Teil). ADR-0108 bleibt „Vorgeschlagen“ bis S4b.

## Changelog

- 2026-11-17: Erstfassung v1.0 (Scheibe S4a, Orte), Anlass PO-Hinweis zu den Profil-Kacheln im Orte-Kopf.
