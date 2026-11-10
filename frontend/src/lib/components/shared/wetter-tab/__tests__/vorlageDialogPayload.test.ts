// TDD RED — Issue #2794 S3a, Teil-PR 3 (Reiter Wetter), Dialog „Als eigene Vorlage speichern“ (W5b). AC-42 (Kern).
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md — Implementation Details §5, AC-42
//
// Der POST /api/metric-presets-Body enthaelt die AUFGELOESTE Abo-Ampel (`ampel`) und die Art
// (`kind`: 'route' im Trip, 'vergleich' im Orts-Briefing); KEINE Zeithorizonte (`horizons`)
// und KEINE Zusammenfassung (`summary`). Name ist Pflicht (Fehlerschluessel, Text im Katalog).
// Die Duplikatpruefung bleibt serverseitig (409 name_exists, Teil-PR 1).
//
// Festgelegte API (ampelSchreiben.ts):
//   eigeneVorlagePayload({name, beschreibung, alsStandard, kind: 'route'|'vergleich', ampel: Ampel})
//       -> { name (getrimmt), description? (nur wenn nicht leer), is_default: boolean, kind, ampel,
//            metrics? (falls gesendet: nur {metric_id, enabled, ...} ohne horizons, aktive = Ampel-Auswahl) }
//   vorlagenNameFehler(name: string) -> string | null   // Katalogschluessel wetter.* oder null
//
// RED heute: ampelSchreiben.ts und de/wetter.json existieren nicht.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/vorlageDialogPayload.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { ampelModell, ampelSchreiben, live, wetterKatalog, type Json } from './wetterTabDaten.ts';

function enthaeltSchluessel(x: unknown, name: string): boolean {
	if (x === null || typeof x !== 'object') return false;
	if (Array.isArray(x)) return x.some((y) => enthaeltSchluessel(y, name));
	return Object.entries(x as Record<string, unknown>).some(([k, v]) => k === name || enthaeltSchluessel(v, name));
}

async function abo(): Promise<{ m: Json; s: Json; ampel: Json }> {
	const m = await ampelModell();
	const s = await ampelSchreiben();
	const vorlagen = m.vorlagenAusTemplates(live().templates);
	const ampel = m.verschmelzen(vorlagen.wandern, { template: 'wandern', metrics: { gust: { alarm_ab: 'red' }, dewpoint: { enabled: true } } });
	return { m, s, ampel };
}

describe('AC-42: Dialog-Payload POST /api/metric-presets', () => {
	for (const kind of ['route', 'vergleich'] as const) {
		test(`ac42_${kind}_payload_mit_ampel_und_kind_ohne_horizons_und_summary`, async () => {
			const { m, s, ampel } = await abo();
			const body = s.eigeneVorlagePayload({ name: '  Bergtag  ', beschreibung: 'Mein Tag', alsStandard: true, kind, ampel });
			assert.equal(body.kind, kind);
			assert.deepEqual(body.ampel, ampel, 'die aufgeloeste Abo-Ampel steht nicht im Body');
			assert.equal(body.name, 'Bergtag', 'Name nicht getrimmt');
			assert.equal(body.description, 'Mein Tag');
			assert.equal(body.is_default, true);
			assert.equal(enthaeltSchluessel(body, 'horizons'), false, 'Body enthaelt Zeithorizonte');
			assert.equal(enthaeltSchluessel(body, 'summary'), false, 'Body enthaelt eine Zusammenfassung');
			if (body.metrics !== undefined) {
				const an = (body.metrics as Json[]).filter((x) => x.enabled).map((x) => x.metric_id).sort();
				assert.deepEqual(an, [...m.aktiveMetriken(ampel)].sort(), 'metrics[] weicht von der Ampel-Auswahl ab');
			}
		});
	}

	test('ac42_ohne_beschreibung_kein_leeres_description_feld', async () => {
		const { s, ampel } = await abo();
		const body = s.eigeneVorlagePayload({ name: 'X', beschreibung: '   ', alsStandard: false, kind: 'route', ampel });
		assert.equal('description' in body && body.description !== undefined, false);
		assert.equal(body.is_default, false);
	});

	test('ac42_payload_mutiert_die_ampel_nicht', async () => {
		const { s, ampel } = await abo();
		const vorher = JSON.stringify(ampel);
		const body = s.eigeneVorlagePayload({ name: 'X', beschreibung: '', alsStandard: false, kind: 'vergleich', ampel });
		body.ampel.metrics.gust.alarm_ab = 'never';
		assert.equal(JSON.stringify(ampel), vorher, 'Body teilt das Ampel-Objekt mit dem Bearbeitungsstand');
	});

	test('ac42_name_pflicht_mit_katalogtext', async () => {
		const { s } = await abo();
		for (const leer of ['', '   ']) {
			const k = s.vorlagenNameFehler(leer);
			assert.equal(typeof k, 'string', `kein Fehler bei Name ${JSON.stringify(leer)}`);
			assert.equal(wetterKatalog('de')[k], 'Gib der Vorlage einen Namen.');
		}
		assert.equal(s.vorlagenNameFehler('Bergtag'), null);
	});
});
