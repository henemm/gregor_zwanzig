// Fix-Loop #2375 (Adversary F002): der undefined-Filter in
// `buildComparePresetPartialPayload` (compareEditorSave.ts) — `undefined`
// wird nie gesendet (JSON.stringify liesse den Schluessel zwar weg, der
// Objekt-Vertrag ist aber "kein Schluessel"), Lösch-Werte (`[]`, `{}`, `""`,
// `null`, `0`, `false`) dagegen schon; `display_config` erscheint nur, wenn
// mindestens ein Schluessel definiert ist.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/compare/__tests__/compare_partial_payload_filtert_undefined.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { buildComparePresetPartialPayload } from '../compareEditorSave.ts';

describe('#2375 F002: buildComparePresetPartialPayload filtert undefined', () => {
	test('Top-Level: kein Schluessel mit undefined, Loesch-Werte bleiben', () => {
		const { url, body } = buildComparePresetPartialPayload('p1', {
			name: undefined,
			location_ids: [],
			note: '',
			cfg: {},
			flag: false,
			zahl: 0,
			leer: null
		});
		assert.strictEqual(url, '/api/compare/presets/p1');
		assert.deepStrictEqual(body, {
			location_ids: [],
			note: '',
			cfg: {},
			flag: false,
			zahl: 0,
			leer: null
		});
		assert.ok(!('name' in body), 'undefined darf nicht als Schluessel im Body stehen.');
	});

	test('display_config: nur definierte Schluessel', () => {
		const { body } = buildComparePresetPartialPayload(
			'p1',
			{},
			{ hourly: undefined, outlook: [], ideal_ranges: {} }
		);
		assert.deepStrictEqual(body, { display_config: { outlook: [], ideal_ranges: {} } });
		assert.ok(!('hourly' in (body as Record<string, any>).display_config));
	});

	test('display_config: keine definierten Schluessel -> kein leeres display_config', () => {
		const { body } = buildComparePresetPartialPayload(
			'p1',
			{ name: 'x' },
			{ hourly: undefined, outlook: undefined }
		);
		assert.deepStrictEqual(body, { name: 'x' });
		assert.ok(!('display_config' in body), 'ein leeres display_config: {} wuerde Fremdwerte loeschen.');
	});

	test('display_config: Argument ganz fehlend -> kein display_config', () => {
		const { body } = buildComparePresetPartialPayload('p1', { name: 'x' });
		assert.deepStrictEqual(body, { name: 'x' });
	});
});
