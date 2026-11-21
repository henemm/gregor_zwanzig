# Kontext und Analyse #3205: Reiter Wetter, Vorlagen gegen Mockup Fassung 4

## 1. Besitzer-Einträge (docs/context/einstellungen_neu/elementliste_besitzer.json)
- #3205, art=element, ctx Orte, DE: `orte.wetter.luecken.-.vorlage-auswahl.9a9818d548` und `orte.wetter.normal.-.vorlage-auswahl.827b20495b` (Zustände "luecken"/"normal"): eigene Vorlage "Mallorca Frühling" fehlt in der Orts-Vergleich-Auswahl (im Trip vorhanden). Gruppen luecken/normal.
- #3205, art=zusaetzlich, ctx trip, Reiter wetter, Muster `Auf "{vorlage}" zurücksetzen` (DE) und `Reset to "{vorlage}"` (EN): Zurücksetzen-Zeile live zusätzlich.
- #3009 (Art Trip, Auswahl): `trip.wetter.luecken.-.vorlage-auswahl.72bcb169cc` und `trip.wetter.normal.-.vorlage-auswahl.eda27b7726`. Grund: EN-Lücke, Name "Mallorca Frühling" hat keinen Katalogtext. Einstufung als Kontoname ist KORREKT: Der Name ist vom Nutzer vergebener Kontoinhalt (Seed #2967), kein Katalogtext; gehört NICHT zu #3205. (Der Rest-Grund "bleibt bis Abnahme DE+EN" ist zulässig; Alternative: im Abgleich Kontonamen EN wie DE gelten lassen.)

## 2. Code
- Filter je Art Frontend: `frontend/src/lib/components/shared/wetter-tab/wetterTabLaden.ts:35-37` (artVon, Bestand ohne kind = route), `:106-111` (eigeneVorlagen filtert `artVon(p) === kind`); frisch gespeicherte Vorlage nur im eigenen Kontext einsortiert: `organisms/wetter-tab/WetterTabInhalt.svelte:207`.
- Go: `internal/model/metric_preset.go:31-40` (PresetKindRoute/Vergleich, ValidPresetKind), `internal/store/metric_preset.go:70-72` (Lese-Default route), `internal/handler/metric_preset.go:57-65` (Duplikat je Art), `:79-86,:133-135` (Standard exklusiv je Art), `:252-256` (POST kind). Python: kein Filter, nur Aufloesung.
- Seit/warum: `kind` seit d3da25f15 (#2794 S3a Teil-PR 1) und 8909b8efb (10.11.2026, Teil 3). Spec `docs/specs/modules/feat_2794_s3a_reiter_wetter.md` P3 (Z.30) und AC-24 (Z.254); Z.339: "PO-Entscheidungen vom 2026-11-08 (kind)". Keine ADR zu "je Art"; ADR-0108 Pkt.1 sagt nur "eine Liste für Trip und Orte" (gemeint: eine UI/ein Code), Pkt.4 "Vorlagen gibt es künftig auch für Orte". #3193 (vorlageImKontext, `wetterZustand.ts:142-166`) ist NICHT der Filter, sondern die Abweichungs-Basis je Kontext (Orte: nur Metriken des Vergleichs-Katalogs, `BASIS_IM_KONTEXT.vergleich` Z.130-136).
- Zurücksetzen-Zeile: `organisms/wetter-tab/VorlageKarte.svelte:161-163`, Bedingung `abweichungen > 0`; Katalogschlüssel `wetter.vorlage.zuruecksetzen` (`frontend/src/lib/i18n/messages/de|en/wetter.json:33`), seit 10.11.2026 (8909b8efb).

## 3. Mockup
- `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html`: `VORLAGEN` (Z.358) und `EIGENE=[['Mallorca Frühling',...]]` (Z.359) sind EINE globale Liste, Picker Z.492-493 rendert sie für Trip und Orte identisch (keine Art-Trennung).
- Zurücksetzen gibt es im Mockup: Z.511, `${devs?<button data-reset>Auf „${c.vorlage}“ zurücksetzen</button>:''}`, also exakt dieselbe Bedingung wie live (nur bei Abweichungen; Picker zeigt dann "▾ N Abweichung(en)" statt "▾ unverändert", Z.510). Es ist KEIN Eintrag im Picker-Menü.
- Folge: Punkt (2) ist kein Code-Unterschied, sondern Zustandsunterschied: Das Prüfkonto-Trip steht live im Zustand mit Abweichung (Prüfdaten), der Mockup-Normalzustand hat devs=0. Elementliste hat für den Abweichungs-Zustand die Zeile nicht erfasst.

## 4. Frühere Entscheidungen
- gh-Suche (Vorlage je Art / eigene Vorlage / zurücksetzen) liefert nur #2799, #3151; relevant #2794 (Spec P3/AC-24, PO 8.11.) sowie #3205-Text selbst ("bleibt die Trennung gewollt, Ausnahme"). Code-Teilung (ADR-0097, CLAUDE.md): EIN Code mit context-Parameter; die Art-Trennung der DATEN ist damit vereinbar (Filter ist ein Parameter, keine zweite Komponente).
- Fachlich: Orte führen manche Metriken nicht (Vergleichs-Katalog, `vergleichsKatalogIds`); eine Trip-Vorlage mit z. B. Nullgradgrenze/Etappen-Metriken würde im Ort teils ins Leere laufen, #3193 neutralisiert das schon für Systemvorlagen (die ja in beiden Kontexten stehen). Die eigene Vorlage ist aber gerade die Momentaufnahme eines Trips, deshalb "Art" getrennt.

## 5. Optionen und Empfehlung
**Punkt 1 (Mallorca Frühling in Orte): ECHTE Produktentscheidung, durch #2794 P3 (PO 8.11.) bereits gegenteilig entschieden, aber das Mockup (später) zeigt anderes; PO hat im Issue-Text schon "Ausnahme" als Weg genannt.**
- A) Trennung behalten, Abweichung als Ausnahme festhalten (2 Einträge #3205 → Ausnahme, Mockup-Beispieldaten anpassen: Mockup-Orte ohne Mallorca Frühling). Kein Code, deckt PO-Entscheid 8.11. Empfohlen.
- B) Alle eigenen Vorlagen in beiden Kontexten zeigen: Filter weg (WetterTabInhalt/Laden), Duplikat/Standard je Art ändern, Kontext-Basis #3193 muss Trip-Vorlagen in Orte übersetzen; Risiko Metriken, die Orte nicht kennen; widerspricht P3/AC-24, Tests müssen kippen.
- C) Gemischt: Art-Trennung nur beim Speichern, Anzeige überall. Mehraufwand, Verwirrung.
Frage an Henning (Alltagssprache): "Eine selbst gespeicherte Vorlage aus einem Trip soll sie auch beim Orts-Vergleich zur Auswahl stehen, oder sollen Trip- und Orts-Vorlagen getrennt bleiben, wie du es am 8.11. festgelegt hast?" Empfehlung: getrennt lassen (A), Mockup per Ausnahme anpassen.

**Punkt 2 (Zurücksetzen): KEINE Produktentscheidung nötig.** Mockup hat die Zeile mit gleicher Bedingung. Empfehlung: Besitzer-Einträge #3205 auflösen, indem sie dem Abweichungs-Zustand zugeordnet werden (Elementliste um Zustand "Abweichung" erweitern, oder Prüfkonto-Trip auf "unverändert" bringen); kein Code. Zeile Katalogtext DE+EN existiert bereits.

**#3009 Mallorca-Einträge:** korrekt Kontoname; bei #3009 belassen (oder als Kontoname-Ausnahme schließen).
