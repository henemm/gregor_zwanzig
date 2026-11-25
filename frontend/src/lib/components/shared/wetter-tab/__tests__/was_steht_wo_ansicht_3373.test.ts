// Issue #3373 (Fix-Loop 2, F006): Kette Antwort -> Ansicht. Die gesperrte SMS-Zelle der Eltern-Zeile
// „Temperatur“ (state locked, reason kein_kuerzel) bringt ihren Beispielwert (Tagesbereich `D14/18`) aus der
// API-Antwort bis in die Zeile der Einstell-Tabelle; der Grund bleibt, eine Marke entsteht nicht.
// Spec: docs/specs/modules/feat_3373_sms_beispiel_karte.md AC-5.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/was_steht_wo_ansicht_3373.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { metrikenAus } from '../wasStehtWoAnsicht.ts';

const t = (k: string) => `«${k}»`;
const zelle = (extra: Record<string, unknown>) => ({ state: 'on', format: null, reason: null, example: null, ampel: null, mark: null, ...extra });

const ANTWORT = {
	rows: [
		{
			metric_id: 'temperature',
			name: 'Temperatur',
			position: 0,
			parent: null,
			cells: {
				email: zelle({ example: 'Temp 14.4' }),
				sms: zelle({ state: 'locked', reason: 'kein_kuerzel', example: 'D14/18', mark: 'passt_nicht_mehr' })
			}
		},
		{
			metric_id: 'temperature_night',
			name: 'Nachttiefst',
			position: 1,
			parent: 'temperature',
			cells: { sms: zelle({ example: 'N10' }) }
		},
		{
			metric_id: 'sunshine',
			name: 'Sonnenstunden',
			position: 2,
			parent: null,
			cells: { sms: zelle({ state: 'locked', reason: 'kein_kuerzel', example: null }) }
		}
	]
} as never;

test('gesperrte SMS-Zelle mit Beispiel: Wert kommt bis zur Zeile, Grund bleibt, keine Marke', () => {
	const zeilen = metrikenAus(ANTWORT, t as never);
	const sms = zeilen.find((m) => m.id === 'temperature')!.zellen.sms;
	assert.equal(sms.zustand, 'locked');
	assert.equal(sms.beispiel, 'D14/18');
	assert.equal(sms.grund, '«wetter.wsw.grund.kein_kuerzel»');
	assert.equal(sms.marke, undefined, 'Marken nur an angehakten Zellen');
	assert.equal(sms.format, null);
});

test('Kind-Zeile behält ihr eigenes Token, gesperrte Zelle ohne Beispiel bleibt ohne', () => {
	const zeilen = metrikenAus(ANTWORT, t as never);
	assert.equal(zeilen.find((m) => m.id === 'temperature_night')!.zellen.sms.beispiel, 'N10');
	assert.equal(zeilen.find((m) => m.id === 'sunshine')!.zellen.sms.beispiel, undefined);
});
