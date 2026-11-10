// TDD RED — Issue #2794 S3a, Teil-PR 3 (Reiter Wetter), Stufe 3.1. AC-37 (Frontend-Seite der Paritaet).
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md — Implementation Details §2 „Absicherung“
//
// Ueber alle 7 Systemvorlagen liefern die Frontend-Ableitung (`ampelModell.ts`) und Python
// `resolve_ampel` dieselbe Menge aktiver Metriken. Gemeinsame Fixture mit dem pytest
// tests/tdd/test_2794_teil3_auswahl_paritaet.py: tests/fixtures/ampel_auswahl_paritaet.json
//   vorlagen.<id>.ampel  = vollstaendige Vorlagen-Ampel, vorlagen.<id>.aktiv = enabled-IDs
//   faelle[].ampel       = Abo-Ampel (nur Abweichungen), faelle[].aktiv = aktive IDs nach Aufloesung
// Verglichen wird als Menge (Format-Beschreibung unter "_format" in der Fixture).
//
// Genutzte API: vorlagenAusTemplates, vorlageIdVon, verschmelzen, aktiveMetriken, zuruecksetzen,
// auswahlLesen (ampelModell.ts), abweichungsMenge (ampelSchreiben.ts) — Signaturen siehe ampelModell.test.ts.
//
// RED heute: ampelModell.ts / ampelSchreiben.ts existieren nicht.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/ampelModell.auswahl_paritaet.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { ampelModell, ampelSchreiben, fixture, live, ohneOffene, type Json } from './wetterTabDaten.ts';

const F = fixture('ampel_auswahl_paritaet.json');
const VORLAGEN_IDS = Object.keys(F.vorlagen as Record<string, Json>);
const FAELLE = F.faelle as Array<{ name: string; ampel: Json; aktiv: string[] }>;
const menge = (a: string[]) => [...new Set(a)].sort();

/** Vorlagen fuer den Spiegel: dieselbe Form wie GET /api/templates ({id, ampel}). */
const vorlagenListe = () => VORLAGEN_IDS.map((id) => ({ id, ampel: structuredClone(F.vorlagen[id].ampel) }));

describe('AC-37: Fixture ist aktuell (gleich /api/templates)', () => {
	test('ac37_fixture_vorlagen_gleich_live_templates', () => {
		const lebend = Object.fromEntries(live().templates.map((t: Json) => [t.id, t.ampel]));
		assert.deepEqual(VORLAGEN_IDS.sort(), Object.keys(lebend).sort(), 'Vorlagen-IDs der Fixture ≠ /api/templates');
		assert.equal(VORLAGEN_IDS.length, 7);
		for (const id of VORLAGEN_IDS) {
			assert.deepEqual(ohneOffene(F.vorlagen[id].ampel), ohneOffene(lebend[id]), `Fixture-Vorlage ${id} veraltet`);
		}
	});
});

describe('AC-37: Frontend-Ableitung = resolve_ampel ueber alle 7 Vorlagen', () => {
	for (const id of VORLAGEN_IDS) {
		test(`ac37_vorlage_${id}_aktive_metriken`, async () => {
			const m = await ampelModell();
			const vorlagen = m.vorlagenAusTemplates(vorlagenListe());
			assert.deepEqual(menge(m.aktiveMetriken(m.verschmelzen(vorlagen[id], null))), menge(F.vorlagen[id].aktiv));
			assert.deepEqual(menge(m.zuruecksetzen(id, vorlagen).auswahl), menge(F.vorlagen[id].aktiv), `${id}: Zuruecksetzen setzt eine andere Auswahl`);
		});
	}

	for (const fall of FAELLE) {
		test(`ac37_fall_${fall.name}_aktive_metriken`, async () => {
			const m = await ampelModell();
			const vorlagen = m.vorlagenAusTemplates(vorlagenListe());
			const vorlage = vorlagen[m.vorlageIdVon(fall.ampel, vorlagen)];
			const aufgeloest = m.verschmelzen(vorlage, structuredClone(fall.ampel));
			assert.deepEqual(menge(m.aktiveMetriken(aufgeloest)), menge(fall.aktiv), `${fall.name}: ${JSON.stringify(fall.ampel)}`);
			// AC-39: Orts-Briefing ohne active_metrics zeigt genau diese Auswahl
			assert.deepEqual(menge(m.auswahlLesen('vergleich', { ampel: fall.ampel }, aufgeloest)), menge(fall.aktiv));
		});

		test(`ac37_fall_${fall.name}_schreiben_und_wieder_aufloesen_erhaelt_auswahl`, async () => {
			const m = await ampelModell();
			const s = await ampelSchreiben();
			const vorlagen = m.vorlagenAusTemplates(vorlagenListe());
			const vorlage = vorlagen[m.vorlageIdVon(fall.ampel, vorlagen)];
			const aufgeloest = m.verschmelzen(vorlage, structuredClone(fall.ampel));
			const abw = s.abweichungsMenge(vorlage, aufgeloest, fall.aktiv);
			assert.deepEqual(menge(m.aktiveMetriken(m.verschmelzen(vorlage, abw))), menge(fall.aktiv));
			assert.equal(
				m.zaehleAbweichungen(abw, vorlagen),
				m.zaehleAbweichungen(fall.ampel?.template && fall.ampel.template in vorlagen ? fall.ampel : { ...fall.ampel, template: vorlage.template }, vorlagen),
				`${fall.name}: geschriebene Menge zaehlt anders als die Ausgangs-Abweichungen`
			);
		});
	}
});
