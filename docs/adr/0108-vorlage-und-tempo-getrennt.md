# ADR-0108: Wetter-Vorlage und Fortbewegungstempo sind zwei getrennte Einstellungen — die Aktivitäts-Chips im Kopf entfallen

- **Status:** Akzeptiert
- **Datum:** 2026-11-03 (angepasst und akzeptiert 2026-11-20, Issue #3196)
- **Bezug:** Epic #2791, Scheibe S4 #2796, Kontext `docs/context/einstellungen_neu.md` §2.2 (Karte `aktivitaet` + Rückfrage Tempo), §6; berührt `frontend/src/lib/components/trip-detail/TripHeader.svelte` (Aktivitäts-Chips), `ComparePreset.profil` (`src/app/models.py:1320`, ausgewertet in `src/services/scheduler_dispatch_service.py:919` über `_parse_activity_profile`, `src/app/loader.py:2136`), `EtappenConfig` (`models.py:413-417`); hängt an ADR-0106 (Vorlage trägt die Ampel)

## Kontext

„Aktivität“ gibt es heute dreimal, mit eigenen Listen, die im Hintergrund aufeinander abgebildet werden:

| Wo | Auswahl | Wirkt auf |
|---|---|---|
| Trip, Kopf | Trekking · Skitour · Hochtour · Klettersteig · MTB · Fahrrad 15/20/25 km/h | Gehzeit bzw. Tempo, dazu die Vorbelegung der Metrik-Vorlage |
| Reiter Wetter-Metriken, „01 Profil“ | Alpen-Trekking · Wandern · Skitouren · Wintersport · Radtour · Wassersport · Allgemein | Metrik-Vorauswahl |
| Ortsvergleich, Kopf | Allgemein · Wintersport · Wandern · Sommer-Trekking | Profil-Label, Versand, Mail-Kopf |

Der PO (Notiz 2026-11-03): „Aktivität hat grundsätzlich zwei Ursprünge: 1. sinnvolle Presets, der User kann sie anpassen und speichern. Das wäre für den Reiter ‚Wetter‘ relevant. 2. Fortbewegungsgeschwindigkeit. Ausschließlich für Trips relevant, hier aber sehr relevant.“

## Entscheidung

1. **Vorlage** (Wetter): eine Liste für Trip und Orte, oben im Reiter Wetter. Sie setzt Metrik-Auswahl, Ampel-Grenzen und „Alarm ab“ (ADR-0106). Sie ist anpassbar und als **eigene Vorlage** unter eigenem Namen speicherbar (Name, Beschreibung, „Als Standard für neue Trips/Orte“; ohne Zeithorizonte). Ein Wechsel fragt nach und nennt die Zahl der Abweichungen, die verloren gehen.
2. **Tempo** (nur Trip): im Reiter **Etappen**, mit Fortbewegung (zu Fuß · Rad · MTB · Ski) und **Grundtempo** (km/h). Die Gehzeit folgt dem Modell des DAV (DIN 33466): `t = max(t_h, t_v) + min(t_h, t_v) / 2` mit `t_h = km / Grundtempo` und `t_v = Hm auf / R auf + Hm ab / R ab`. Die Auf-/Abstiegsrate folgt dem Grundtempo im festen Verhältnis je Fortbewegung (`R = R_ref · v / v_ref`; Referenz zu Fuß 4 km/h · 300/500 Hm/h, Rad 20 · 600/1000, MTB 12 · 500/1000, Ski 3 · 300/1500) und ist nicht sichtbar. Ein Wechsel der Fortbewegung setzt das Grundtempo auf den Vorschlagswert. Das Tempo gilt für alle Etappen und ist je Etappe überschreibbar (nur Grundtempo, #3197). „Fahrrad 15/20/25 km/h“ wird zu „Rad“ plus Grundtempo.
   > **Anpassung 2026-11-20 (Issue #3196, PO-Entscheidung):** ersetzt die ursprüngliche Fassung „Tempo flach und Aufstieg (Abstieg bleibt im Modell)“. Der PO hat bewusst akzeptiert, dass sich die Gehzeiten aller Bestandstrips damit einmalig ändern.
3. Die **Aktivitäts-Chips im Trip-Kopf** und die **Profil-Chips im Kopf der Orte** entfallen. Beim Ortsvergleich ersetzt der **Name der Vorlage** das bisherige `profil`, auch im Mail-Kopf und beim Versand (K3b).
4. Vorlagen gibt es künftig auch für Orte (heute nur Trip).
5. Bestehende Trips behalten ihr Tempo: Die Migration überträgt die alte Aktivität per Read-Modify-Write mit Merge (ADR-0101) in Fortbewegung und Tempo. Das alte `profil` wird auf eine Vorlage abgebildet.
   > **Ergänzung 2026-11-20 (Issue #3196):** Die Migration erhält Fortbewegung und Grundtempo, nicht die Gehzeiten (`fahrrad_15/20/25` → Rad 15/20/25 km/h, alles andere → zu Fuß 4 km/h, nie MTB oder Ski). Das Altfeld `activity` bleibt auf der Platte stehen; fehlt `tempo`, wird es beim Lesen daraus abgeleitet.

## Verworfene Alternativen

- **Nur im Reiter Wetter, kein Tempo-Feld:** Das Tempo würde wieder aus der Vorlage abgeleitet, und „Radtour“ kann 15 oder 25 km/h bedeuten.
- **Getrennt lassen, nur Namen vereinheitlichen:** Die Doppelung im Kopf und die versteckte Abbildung blieben.

## Konsequenzen

- **Positiv:** Jede Auswahl hat einen Ort und eine Wirkung. Das Tempo kann je Etappe stimmen (Ruhetag, Bergetappe).
- **Negativ / Preis:** Bestandsdaten (Trip-Aktivität, Compare-`profil`) müssen migriert werden. Der Versandpfad des Ortsvergleichs liest das Profil künftig aus der Vorlage.
- **Folgepflichten:** Texte in DE und EN (ADR-0104). Gehzeit-Berechnung und Bewertungsstunden je Wegpunkt hängen weiter am Tempo, das ist zu testen.
