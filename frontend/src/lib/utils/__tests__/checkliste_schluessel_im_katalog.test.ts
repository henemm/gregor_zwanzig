// Fix-Loop 1 — Issue #2794 S3a Teil-PR 4b, Adversary F002: die Startklar-Checklisten
// (cockpitHelpers568.ts, Trip und Ortsvergleich) nutzen nur Katalogschlüssel, die es in
// DE UND EN gibt. Gemessen am Verhalten: jede Zeile, die setupStepTrip/setupStepCompare
// unter `de` bzw. `en` liefern, muss genau der Wert EINES Schlüssels `bausteine.checkliste.*`
// in beiden Katalogen sein (gleicher Schlüssel, gleiche Position). Ein nicht vorhandener
// Schlüssel liefert keinen Katalogwert und macht den Test rot.
//
//   cd frontend && npm test -- src/lib/utils/__tests__/checkliste_schluessel_im_katalog.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { setupStepTrip, setupStepCompare } from '../cockpitHelpers568.ts';
import { locale } from '../../i18n/index.ts';
import { de } from '../../i18n/messages/de/index.ts';
import { en } from '../../i18n/messages/en/index.ts';
import type { ComparePreset, Trip } from '../../types.ts';

afterEach(() => locale.set('de'));

const TRIP = { id: 't1', name: 'T', stages: [] } as unknown as Trip;
const PRESET = { id: 'c1', name: 'C', location_ids: [] } as unknown as ComparePreset;
const DE = de as Record<string, string>;
const EN = en as Record<string, string>;
const PRAEFIX = 'bausteine.checkliste.';

function labels(lang: 'de' | 'en', f: () => { label: string }[]): string[] {
	locale.set(lang);
	return f().map((s) => s.label);
}

/** Schlüssel, deren DE- und EN-Wert genau diese Zeile ergeben. */
function schluesselFuer(deText: string, enText: string): string[] {
	return Object.keys(DE).filter((k) => k.startsWith(PRAEFIX) && DE[k] === deText && EN[k] === enText);
}

describe('F002: Checklisten-Einträge stammen aus Schlüsseln, die DE und EN führen', () => {
	for (const [name, f] of [
		['Trip', () => setupStepTrip(TRIP)],
		['Ortsvergleich', () => setupStepCompare(PRESET)]
	] as const) {
		test(`${name}: jede Zeile = ein bausteine.checkliste.*-Schlüssel in DE und EN`, () => {
			const d = labels('de', f);
			const e = labels('en', f);
			assert.equal(d.length, e.length);
			assert.ok(d.length >= 5, 'Messaufbau: Checkliste leer');
			const ohne = d.map((t, i) => [t, e[i], schluesselFuer(t, e[i])] as const).filter(([, , k]) => k.length === 0);
			assert.deepEqual(ohne.map(([t, x]) => `${t} / ${x}`), [], 'Zeilen ohne Katalogschlüssel in DE und EN');
		});
	}
});
