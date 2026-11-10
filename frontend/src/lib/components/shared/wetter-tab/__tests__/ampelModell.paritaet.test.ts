// TDD RED — Issue #2794 S3a, Teil-PR 3 (Reiter Wetter), Stufe 3.1. AC-28 (Frontend-Spiegel).
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md
//
// Der Frontend-Abweichungszaehler (`ampelModell.ts`) liefert fuer dieselben Faelle dieselbe Zahl
// wie die Python-Referenz `app.ampel.deviation_count`. Quelle der Faelle ist DIESELBE Datei, die
// der pytest liest: tests/fixtures/ampel_deviation_cases.json. Die Vorlagen-Ampeln kommen aus
// der echten `/api/templates`-Antwort (Python), nie aus einer Frontend-Kopie.
//
// Festgelegte API (ampelModell.ts):
//   vorlagenAusTemplates(liste: {id: string; ampel: Ampel}[]): VorlagenAmpeln   // GET /api/templates -> id -> Ampel
//   zaehleAbweichungen(abo: Ampel | null | undefined, vorlagen: VorlagenAmpeln): number
//       Spiegel von deviation_count: Vorlage = abo.template (unbekannt/fehlt -> „allgemein“),
//       je Metrik hoechstens 1 (Grenzen, enabled, alarm_ab, Metrik +/−), Gewitterfarbe 1,
//       Rueckkehr auf den Vorlagenwert zaehlt nicht, Metrik ohne Vorlagen-Zeile = aus/never.
//
// RED heute: ampelModell.ts existiert nicht.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/ampelModell.paritaet.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { ampelModell, fixture, live } from './wetterTabDaten.ts';

const FAELLE = fixture('ampel_deviation_cases.json').cases as Array<{ name: string; ampel: unknown; expected: number }>;

describe('AC-28: Frontend-Abweichungszaehler = Python deviation_count (gemeinsame Fixture)', () => {
	test('Messaufbau: Fixture hat Faelle fuer alle fuenf Aenderungsarten und Rueckkehr', () => {
		assert.ok(FAELLE.length >= 15, `zu wenige Faelle: ${FAELLE.length}`);
		const namen = FAELLE.map((f) => f.name).join(' ');
		for (const art of ['grenze', 'enabled', 'alarm_ab', 'hinzugefuegt', 'entfernt', 'gewitter', 'zurueck']) {
			assert.ok(namen.includes(art), `Fixture ohne Fall „${art}“`);
		}
	});

	for (const fall of FAELLE) {
		test(`ac28_${fall.name}: ${fall.expected} Abweichung(en)`, async () => {
			const m = await ampelModell();
			const vorlagen = m.vorlagenAusTemplates(live().templates);
			assert.equal(
				m.zaehleAbweichungen(structuredClone(fall.ampel), vorlagen),
				fall.expected,
				`AC-28: Frontend zaehlt fuer ${fall.name} anders als die Python-Referenz: ${JSON.stringify(fall.ampel)}`
			);
		});
	}

	test('ac28_zaehler_veraendert_die_eingabe_nicht', async () => {
		const m = await ampelModell();
		const vorlagen = m.vorlagenAusTemplates(live().templates);
		const kombi = FAELLE.find((f) => f.name === 'kombination');
		assert.ok(kombi, 'Messaufbau: Fall kombination fehlt');
		const vorher = JSON.stringify(kombi!.ampel);
		m.zaehleAbweichungen(kombi!.ampel, vorlagen);
		assert.equal(JSON.stringify(kombi!.ampel), vorher, 'zaehleAbweichungen mutiert die Abo-Ampel');
		assert.equal(JSON.stringify(vorlagen), JSON.stringify(m.vorlagenAusTemplates(live().templates)), 'zaehleAbweichungen mutiert die Vorlagen');
	});

	test('ac28_unbekannte_vorlage_faellt_auf_allgemein', async () => {
		const m = await ampelModell();
		const vorlagen = m.vorlagenAusTemplates(live().templates);
		// gust allgemein: upper 30/45/60 — gleich der Vorlage => 0; abweichend => 1
		assert.equal(m.zaehleAbweichungen({ template: 'gibt-es-nicht', metrics: { gust: { upper: { yellow: 30, orange: 45, red: 60 } } } }, vorlagen), 0);
		assert.equal(m.zaehleAbweichungen({ template: 'gibt-es-nicht', metrics: { gust: { upper: { yellow: 31, orange: 45, red: 60 } } } }, vorlagen), 1);
	});
});
