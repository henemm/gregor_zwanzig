// TDD RED — Issue #1743 (Reiter aufräumen), AC-16/AC-17/AC-18: EINE Quelle der Reiterfolge.
// Hub-Leiste (Trip, Vergleich) und Anlege-Kette (/trips/new, /compare/new) werden aus
// derselben Definition `REITER_DEFINITION` abgeleitet (`subscriptionTabs`, `anlegeKette`).
//
// Spec: docs/specs/modules/feat_1743_reiter_aufraeumen.md (Abschnitt 1, AC-16..AC-18)
// Schnittstelle: docs/artifacts/feat-1743-reiter-aufraeumen/red-schnittstellen.md
//
// Messweise: nur Funktionsausgaben. AC-18 injiziert eine KOPIE der Definition als Eingabe
// (Testdouble nur der Eingabe, nicht des Prüflings) — verschwindet ein Reiter in allen vier
// Ketten, existiert keine zweite Liste. Import per Namespace, damit fehlende Exporte als
// Assertion scheitern statt die ganze Datei beim Laden abzubrechen.
//
// Ausführen (aus frontend/):
//   node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/reiterfolge_eine_quelle.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import * as st from '../subscriptionTabs.ts';

type Kind = 'trip' | 'vergleich';
interface Reiter { id: string; label: string; lockHint?: string; optional?: boolean }
type Def = Record<string, unknown>;

const quelle = st as unknown as {
	REITER_DEFINITION?: Def;
	subscriptionTabs: (kind: Kind, def?: Def) => Reiter[];
	anlegeKette?: (kind: Kind, def?: Def) => Reiter[];
};

function def(): Def {
	assert.ok(quelle.REITER_DEFINITION, 'REITER_DEFINITION wird von shared/subscriptionTabs.ts nicht exportiert.');
	return quelle.REITER_DEFINITION!;
}

function anlege(kind: Kind, d?: Def): Reiter[] {
	assert.equal(typeof quelle.anlegeKette, 'function', 'anlegeKette wird von shared/subscriptionTabs.ts nicht exportiert.');
	return quelle.anlegeKette!(kind, d);
}

/** Die vier Ketten: Trip-Hub, Vergleichs-Hub, Trip-Anlegen, Vergleich-Anlegen. */
function vierKetten(d?: Def): Record<string, Reiter[]> {
	return {
		'Trip-Hub': quelle.subscriptionTabs('trip', d),
		'Vergleichs-Hub': quelle.subscriptionTabs('vergleich', d),
		'Trip-Anlegen': anlege('trip', d),
		'Vergleich-Anlegen': anlege('vergleich', d)
	};
}

/** Ab (einschliesslich) `wetter-metriken`, nur Kennung + Label. */
function schwanz(kette: Reiter[]): { id: string; label: string }[] {
	const i = kette.findIndex((r) => r.id === 'wetter-metriken');
	assert.notEqual(i, -1, `kein Reiter wetter-metriken in ${kette.map((r) => r.id).join(' · ')}`);
	return kette.slice(i).map((r) => ({ id: r.id, label: r.label }));
}

const SCHWANZ = [
	{ id: 'wetter-metriken', label: 'Wetter-Metriken' },
	{ id: 'wertebereiche', label: 'Wertebereiche' },
	{ id: 'alarme', label: 'Alarme' }
];

describe('AC-16: Reiter ab wetter-metriken sind in allen vier Ketten identisch', () => {
	test('Hub-Leiste je kind: fünf Reiter, ohne versand/vorschau', () => {
		assert.deepEqual(quelle.subscriptionTabs('trip').map((r) => r.id), ['uebersicht', 'etappen', 'wetter-metriken', 'wertebereiche', 'alarme']);
		assert.deepEqual(quelle.subscriptionTabs('vergleich').map((r) => r.id), ['uebersicht', 'orte', 'wetter-metriken', 'wertebereiche', 'alarme']);
	});

	test('Kennung, Label und Reihenfolge ab wetter-metriken gleich (Trip-Hub = Vergleichs-Hub = Trip-Anlegen = Vergleich-Anlegen)', () => {
		const ketten = vierKetten();
		for (const [name, kette] of Object.entries(ketten)) {
			assert.deepEqual(schwanz(kette), SCHWANZ, `${name}: Schwanz weicht ab`);
		}
	});
});

describe('AC-17: Anlege-Kette je kind', () => {
	test('Trip: route · etappen · wegpunkte · wetter-metriken · wertebereiche · alarme', () => {
		assert.deepEqual(anlege('trip').map((r) => r.id), ['route', 'etappen', 'wegpunkte', 'wetter-metriken', 'wertebereiche', 'alarme']);
	});

	test('Vergleich: vergleich · orte · wetter-metriken · wertebereiche · alarme', () => {
		assert.deepEqual(anlege('vergleich').map((r) => r.id), ['vergleich', 'orte', 'wetter-metriken', 'wertebereiche', 'alarme']);
	});

	test('anlege-eigen sind nur Kopf-Schritte, lockHint und optional — keine weiteren Felder', () => {
		const erlaubt = new Set(['id', 'label', 'lockHint', 'optional']);
		for (const kind of ['trip', 'vergleich'] as const) {
			for (const s of anlege(kind)) {
				const fremd = Object.keys(s).filter((k) => !erlaubt.has(k));
				assert.deepEqual(fremd, [], `${kind}/${s.id}: unerwartete Felder ${fremd.join(',')}`);
				assert.equal(typeof s.label, 'string', `${kind}/${s.id}: Label fehlt`);
			}
		}
	});

	test('kein Schritt „versand" in beiden Anlege-Ketten', () => {
		for (const kind of ['trip', 'vergleich'] as const) {
			assert.ok(!anlege(kind).some((s) => s.id === 'versand'), `${kind}: Anlege-Kette führt noch versand`);
		}
	});
});

describe('AC-18: eine ersetzte Kopie der Definition wirkt auf alle vier Ketten', () => {
	test('Positivkontrolle: mit der Originaldefinition steht wertebereiche in allen vier Ketten', () => {
		for (const [name, kette] of Object.entries(vierKetten(def()))) {
			assert.ok(kette.some((r) => r.id === 'wertebereiche'), `${name}: wertebereiche fehlt schon im Original`);
		}
	});

	test('wertebereiche aus dem Schwanz der Kopie entfernt → fehlt in allen vier Ketten', () => {
		const kopie = structuredClone(def()) as { schwanz: Reiter[] };
		kopie.schwanz = kopie.schwanz.filter((r) => r.id !== 'wertebereiche');
		for (const [name, kette] of Object.entries(vierKetten(kopie as unknown as Def))) {
			assert.ok(!kette.some((r) => r.id === 'wertebereiche'), `${name}: wertebereiche noch vorhanden — zweite Liste?`);
			assert.ok(kette.some((r) => r.id === 'alarme'), `${name}: alarme fehlt — Ableitung kaputt`);
		}
	});

	test('Label in der Kopie umbenannt → kommt in allen vier Ketten an (Label nicht aus Zweitliste)', () => {
		const kopie = structuredClone(def()) as { schwanz: Reiter[] };
		kopie.schwanz = kopie.schwanz.map((r) => (r.id === 'alarme' ? { ...r, label: 'Alarme X' } : r));
		for (const [name, kette] of Object.entries(vierKetten(kopie as unknown as Def))) {
			assert.equal(kette.find((r) => r.id === 'alarme')?.label, 'Alarme X', `${name}: Label nicht aus der Definition`);
		}
	});

	test('die Originaldefinition bleibt nach den Ableitungen unverändert', () => {
		const vorher = structuredClone(def());
		vierKetten(structuredClone(def()));
		vierKetten();
		assert.deepEqual(def(), vorher);
		assert.ok(quelle.subscriptionTabs('trip').some((r) => r.id === 'wertebereiche'));
	});
});
