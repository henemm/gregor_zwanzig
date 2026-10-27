// TDD RED — Issue #1969 (Nächstes Briefing), AC-18 / AC-19 (Lade-Naht).
// SPEC: docs/specs/modules/feat_1969_naechstes_briefing.md
//
// Prüfling: shared/versand-tab/nextBriefingLoad.ts —
//   ladeNaechstesBriefing(holen, context, id): Promise<NextBriefing | null>
// `holen` hat die Form von `api.get` (Pfad → Promise<JSON>). Der Versand-Reiter
// ruft diese EINE Funktion beim Öffnen und nach jedem erfolgreichen Speichern
// (AC-18). Dass der Reiter sie nach dem Speichern tatsächlich erneut aufruft,
// ist im SSR-Harness nicht ausführbar (kein DOM, keine Effects) und wird in der
// Live-Schicht geprüft (Staging: Uhrzeit ändern, speichern, Zeile aktualisiert).
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/shared/versand-tab/__tests__/naechstes_briefing_laden.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const { ladeNaechstesBriefing } = await import(pathToFileURL(path.join(HERE, '..', 'nextBriefingLoad.ts')).href);

const NB_T1 = {
	at: '2026-10-22T08:00:00+02:00',
	local_date: '2026-10-22',
	local_time: '08:00',
	tz: 'Europe/Paris',
	tz_abbr: 'CEST',
	slot: 'morning'
};
const NB_P1 = { at: null, reason: 'manual' };

/** Aufzeichnender Abrufer: merkt sich jeden Pfad und antwortet mit `antwort`. */
function abrufer(antwort: unknown | Error) {
	const pfade: string[] = [];
	const holen = async (p: string) => {
		pfade.push(p);
		if (antwort instanceof Error) throw antwort;
		return antwort;
	};
	return { holen, pfade };
}

describe('AC-18: Abruf je Kontext über /api/next-briefings mit Einschränkung', () => {
	test('route → ?trip_id=<id>, liefert den Eintrag aus trips', async () => {
		const { holen, pfade } = abrufer({ trips: { t1: NB_T1 }, compare: {} });
		const nb = await ladeNaechstesBriefing(holen, 'route', 't1');
		assert.deepEqual(pfade, ['/api/next-briefings?trip_id=t1']);
		assert.deepEqual(nb, NB_T1);
	});

	test('vergleich → ?preset_id=<id>, liefert den Eintrag aus compare', async () => {
		const { holen, pfade } = abrufer({ trips: {}, compare: { p1: NB_P1 } });
		const nb = await ladeNaechstesBriefing(holen, 'vergleich', 'p1');
		assert.deepEqual(pfade, ['/api/next-briefings?preset_id=p1']);
		assert.deepEqual(nb, NB_P1);
	});

	test('ID wird URL-kodiert', async () => {
		const { holen, pfade } = abrufer({ trips: {}, compare: {} });
		await ladeNaechstesBriefing(holen, 'route', 'a b&c');
		assert.equal(pfade.length, 1);
		const u = new URL(pfade[0], 'http://x');
		assert.equal(u.pathname, '/api/next-briefings');
		assert.equal(u.searchParams.get('trip_id'), 'a b&c');
		assert.deepEqual([...u.searchParams.keys()], ['trip_id']);
	});

	test('zweiter Aufruf (nach Speichern) fragt erneut und liefert den NEUEN Wert', async () => {
		let antwort: unknown = { trips: { t1: NB_T1 }, compare: {} };
		const pfade: string[] = [];
		const holen = async (p: string) => {
			pfade.push(p);
			return antwort;
		};
		assert.equal((await ladeNaechstesBriefing(holen, 'route', 't1'))?.local_time, '08:00');
		antwort = { trips: { t1: { ...NB_T1, at: '2026-10-22T09:00:00+02:00', local_time: '09:00' } }, compare: {} };
		assert.equal((await ladeNaechstesBriefing(holen, 'route', 't1'))?.local_time, '09:00');
		assert.equal(pfade.length, 2, 'kein Zwischenspeicher: jeder Aufruf fragt das Backend');
	});
});

describe('AC-19: Fehler/fehlender Eintrag → null, nie ein fremder oder erfundener Wert', () => {
	test('Abruf wirft → null (kein Absturz)', async () => {
		const { holen } = abrufer(new Error('502'));
		assert.equal(await ladeNaechstesBriefing(holen, 'route', 't1'), null);
	});

	test('Eintrag fehlt → null, auch wenn andere IDs geliefert werden', async () => {
		const { holen } = abrufer({ trips: { anderer: NB_T1 }, compare: { t1: NB_P1 } });
		assert.equal(await ladeNaechstesBriefing(holen, 'route', 't1'), null);
	});

	test('kaputte Antwort (kein Objekt) → null', async () => {
		const { holen } = abrufer('quatsch');
		assert.equal(await ladeNaechstesBriefing(holen, 'vergleich', 'p1'), null);
	});
});
