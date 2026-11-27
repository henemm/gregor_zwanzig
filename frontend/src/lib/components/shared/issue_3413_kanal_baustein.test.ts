// Issue #3413 — restliche Kanal-Flag-Auswertungen auf den gemeinsamen Baustein.
// Spec: docs/specs/fast/feat-3413-kanal-baustein.md (AC-1, AC-2, AC-3; AC-4 per Mutations-Gegenprobe)
//
// Schuetzt das Verhalten von `tripBriefingKanaele` (Hub-Uebersicht) und `standAusPreset().briefing`
// (Reiter Zustellung) gegen FESTE Erwartungswerte: E-Mail an, solange send_email !== false;
// Telegram/SMS/Premium-SMS nur bei genau `true`; Reihenfolge email, telegram, sms, premium_sms.
// Kein Mock: echte reine Funktionen, echte Eingabeobjekte.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import type { ComparePreset, Trip } from '../../types.ts';
import { tripBriefingKanaele } from './hub-uebersicht/hubUebersichtModell.ts';
import { standAusPreset } from './zustellung-tab/zustellungModell.ts';

const FEHLT = Symbol('fehlt');
type Wert = typeof FEHLT | true | false | 'true';
const WERTE: readonly Wert[] = [FEHLT, true, false, 'true'];
const FLAGS = ['send_email', 'send_telegram', 'send_sms', 'send_premium_sms'] as const;

// Feste Erwartung je Wert: E-Mail (fehlend/true/"true" = an, nur false = aus), uebrige nur bei true.
const EMAIL_AN: ReadonlyMap<Wert, boolean> = new Map<Wert, boolean>([[FEHLT, true], [true, true], [false, false], ['true', true]]);
const UEBRIGE_AN: ReadonlyMap<Wert, boolean> = new Map<Wert, boolean>([[FEHLT, false], [true, true], [false, false], ['true', false]]);

function flagsObjekt(werte: readonly Wert[]): Record<string, unknown> {
	const o: Record<string, unknown> = {};
	werte.forEach((w, i) => {
		if (w !== FEHLT) o[FLAGS[i]] = w;
	});
	return o;
}

function* alleKombinationen(): Generator<Wert[]> {
	for (const a of WERTE) for (const b of WERTE) for (const c of WERTE) for (const d of WERTE) yield [a, b, c, d];
}

function erwartet(werte: readonly Wert[]) {
	return {
		email: EMAIL_AN.get(werte[0])!,
		telegram: UEBRIGE_AN.get(werte[1])!,
		sms: UEBRIGE_AN.get(werte[2])!,
		premium_sms: UEBRIGE_AN.get(werte[3])!
	};
}

const trip = (rc: Record<string, unknown> | undefined) => ({ id: 't1', name: 'T', stages: [], report_config: rc }) as unknown as Trip;
const preset = (felder: Record<string, unknown>) => ({ id: 'p1', name: 'P', ...felder }) as unknown as ComparePreset;

describe('#3413 tripBriefingKanaele (AC-1, AC-2)', () => {
	// Feste Stichproben mit ausgeschriebenem Ergebnis.
	const tabelle: Array<[Record<string, unknown>, string[]]> = [
		[{}, ['email']],
		[{ send_email: false }, []],
		[{ send_email: 'true' }, ['email']],
		[{ send_telegram: true, send_sms: true, send_premium_sms: true }, ['email', 'telegram', 'sms', 'premium_sms']],
		[{ send_email: false, send_premium_sms: true }, ['premium_sms']],
		[{ send_telegram: 'true', send_sms: 'true', send_premium_sms: 'true' }, ['email']],
		[{ send_email: false, send_telegram: true, send_sms: false, send_premium_sms: 'true' }, ['telegram']],
		[{ send_sms: true, send_telegram: false }, ['email', 'sms']]
	];
	for (const [rc, soll] of tabelle) {
		test(`Stichprobe ${JSON.stringify(rc)} -> ${JSON.stringify(soll)}`, () => {
			assert.deepEqual(tripBriefingKanaele(trip(rc)), soll);
		});
	}

	test('alle 256 Kombinationen (fehlend/true/false/"true") in fester Reihenfolge', () => {
		for (const werte of alleKombinationen()) {
			const e = erwartet(werte);
			const soll = (['email', 'telegram', 'sms', 'premium_sms'] as const).filter((k) => e[k]);
			assert.deepEqual(tripBriefingKanaele(trip(flagsObjekt(werte))), soll, JSON.stringify(flagsObjekt(werte)));
		}
	});

	test('Trip ohne report_config -> [email] (AC-2)', () => {
		assert.deepEqual(tripBriefingKanaele(trip(undefined)), ['email']);
	});
});

describe('#3413 standAusPreset().briefing (AC-3)', () => {
	test('Stichproben', () => {
		assert.deepEqual(standAusPreset(preset({})).briefing, { email: true, telegram: false, sms: false, premium_sms: false });
		assert.deepEqual(standAusPreset(preset({ send_email: false, send_premium_sms: true })).briefing, {
			email: false,
			telegram: false,
			sms: false,
			premium_sms: true
		});
		assert.deepEqual(
			standAusPreset(preset({ send_email: 'true', send_telegram: 'true', send_sms: true, send_premium_sms: 'true' })).briefing,
			{ email: true, telegram: false, sms: true, premium_sms: false }
		);
	});

	test('alle 256 Kombinationen', () => {
		for (const werte of alleKombinationen()) {
			assert.deepEqual(standAusPreset(preset(flagsObjekt(werte))).briefing, erwartet(werte), JSON.stringify(flagsObjekt(werte)));
		}
	});
});
