// TDD RED — Issue #3443 (S5d aus #2797, Epic #2791): „Aktiviert“-Meldung nach dem Wechsel Entwurf → aktiv.
// Spec: docs/specs/modules/feat_3443_entwurf_aktivieren.md — AC-7, AC-8, AC-9 (Laufzeit der Wechsel-Erkennung).
//
// Prüfling: frontend/src/lib/components/shared/aktivierungsWechsel.svelte.ts (NEU) — Runen-Modul, das den
// Lebenszyklus der Seite beobachtet und beim Wechsel draft → active GENAU EINMAL „nächstes Briefing“ holt.
//
// VERTRAG für den Developer:
//   export interface AktivierungsQuelle {
//     context: 'route' | 'vergleich';
//     id: string | undefined;                 // fehlt ⇒ kein Abruf
//     lifecycle: SubscriptionLifecycle;       // 'draft' | 'active' | 'paused' | 'archived'
//   }
//   export function erstelleAktivierungsWechsel(
//     quelle: () => AktivierungsQuelle,       // liest echte Signale (Seite: lifecycle, trip.id / currentPreset.id)
//     holen: Holen,                           // (pfad) => Promise<unknown>, wie nextBriefingLoad.ts (Seite: api.get)
//     beiMeldung: (text: string) => void      // Seite: Meldungsweg hub-aktion-meldung
//   ): void;
//   Regeln: $effect im Modul; vorheriger Lebenszyklus wird gemerkt; nur warAktivierung(vorher, nachher)
//   (entwurfAktivieren.ts) löst den Abruf aus — nie beim ersten Lesen, nie bei anderen Wechseln.
//   Abruf über ladeNaechstesBriefing(holen, context, id); Meldung = aktiviertText(nb, context) in der
//   aktuellen Sprache. Laufnummer wie naechstesBriefingLader: eine spät eintreffende ältere Antwort meldet nie.
//
// Testart wie naechstes_briefing_lader_laufzeit.test.ts: das Runen-Modul wird mit dem echten Svelte-Compiler
// für die CLIENT-Laufzeit übersetzt (versand-tab/__tests__/clientRunenHook.mjs) und unter `effect_root` +
// `flush` ausgeführt — echte Abhängigkeits-Verfolgung, kein DOM. Der Abrufer ist ein aufzeichnender Stub am
// Netz-Ausgang (Pfad → Antwort), die Meldungen werden mitgeschrieben.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/shared/__tests__/aktivierungs_wechsel_laufzeit.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { locale } from '../../../i18n/index.ts';
import { formatNextBriefing } from '../versand-tab/nextBriefingText.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
register(pathToFileURL(path.join(HERE, '..', 'versand-tab', '__tests__', 'clientRunenHook.mjs')).href, pathToFileURL(HERE + '/').href);

// Interne Client-Laufzeit (ohne Typdeklaration) — Spezifizierer als Wert, damit svelte-check keinen Typ verlangt.
const CLIENT_LAUFZEIT: string = 'svelte/internal/client';
const $ = (await import(CLIENT_LAUFZEIT)) as Record<string, any>;

afterEach(() => locale.set('de'));

async function modul(): Promise<any> {
	try {
		return await import(pathToFileURL(path.join(HERE, '..', 'aktivierungsWechsel.svelte.ts')).href);
	} catch (e) {
		assert.fail(`TDD RED: shared/aktivierungsWechsel.svelte.ts fehlt oder lädt nicht (${(e as Error).message})`);
	}
}

const NB = (local_time: string) => ({
	at: `2026-10-22T${local_time}:00+02:00`,
	local_date: '2026-10-22',
	local_time,
	tz: 'Europe/Paris',
	tz_abbr: 'CEST',
	slot: 'morning'
});
const MIT_ZEIT = (local_time: string, ctx: 'route' | 'vergleich' = 'route') =>
	`Aktiviert. Das erste Briefing kommt ${formatNextBriefing(NB(local_time) as never, ctx)}.`;

/** Mikrotasks + Effekt-Warteschlange abarbeiten. */
async function setzen() {
	$.flush();
	for (let i = 0; i < 5; i++) await new Promise((r) => setTimeout(r, 0));
	$.flush();
}

/** Abrufer mit steuerbarer Antwort je Aufruf. */
function abrufer(antwort: (pfad: string, n: number) => unknown | Promise<unknown>) {
	const pfade: string[] = [];
	return { pfade, holen: async (p: string) => (pfade.push(p), antwort(p, pfade.length)) };
}

/** Wechsel-Erkennung in einer echten Effekt-Wurzel; die Quelle liest echte Signale. */
async function starte(
	start: { context: 'route' | 'vergleich'; id?: string; lifecycle: string },
	holen: (p: string) => Promise<unknown>
) {
	const { erstelleAktivierungsWechsel } = await modul();
	const signale = {
		context: $.state(start.context),
		id: $.state(start.id),
		lifecycle: $.state(start.lifecycle),
		fremd: $.state(0)
	};
	const meldungen: string[] = [];
	const stopp = $.effect_root(() => {
		erstelleAktivierungsWechsel(
			() => ({ context: $.get(signale.context), id: $.get(signale.id), lifecycle: $.get(signale.lifecycle) }),
			holen,
			(text: string) => void meldungen.push(text)
		);
	});
	await setzen();
	const setze = async (lifecycle: string) => {
		$.set(signale.lifecycle, lifecycle);
		await setzen();
	};
	return { signale, meldungen, setze, stopp };
}

describe('AC-7: Wechsel draft → active ⇒ genau ein Abruf und genau eine Meldung mit dem Termin', () => {
	test('Trip: ?trip_id=, Meldung „Aktiviert. Das erste Briefing kommt Do 22.10. 07:00 (CEST).“', async () => {
		const a = abrufer(() => ({ trips: { t1: NB('07:00') }, compare: {} }));
		const w = await starte({ context: 'route', id: 't1', lifecycle: 'draft' }, a.holen);
		assert.deepEqual(a.pfade, [], 'beim ersten Lesen (Entwurf) darf nichts abgerufen werden');
		await w.setze('active');
		assert.deepEqual(a.pfade, ['/api/next-briefings?trip_id=t1']);
		assert.deepEqual(w.meldungen, ['Aktiviert. Das erste Briefing kommt Do 22.10. 07:00 (CEST).']);
		assert.deepEqual(w.meldungen, [MIT_ZEIT('07:00')]);
		w.stopp();
	});

	test('Orts-Vergleich: ?preset_id=, Wert aus .compare[id]', async () => {
		const a = abrufer(() => ({ trips: { p1: NB('09:00') }, compare: { p1: NB('07:00') } }));
		const w = await starte({ context: 'vergleich', id: 'p1', lifecycle: 'draft' }, a.holen);
		await w.setze('active');
		assert.deepEqual(a.pfade, ['/api/next-briefings?preset_id=p1']);
		assert.deepEqual(w.meldungen, [MIT_ZEIT('07:00', 'vergleich')]);
		w.stopp();
	});

	test('nach der Meldung: weitere Lesevorgänge/fremde Signale lösen keinen zweiten Abruf aus', async () => {
		const a = abrufer(() => ({ trips: { t1: NB('07:00') }, compare: {} }));
		const w = await starte({ context: 'route', id: 't1', lifecycle: 'draft' }, a.holen);
		await w.setze('active');
		$.set(w.signale.fremd, 1);
		await setzen();
		await w.setze('active');
		assert.equal(a.pfade.length, 1, `Abrufe: ${JSON.stringify(a.pfade)}`);
		assert.equal(w.meldungen.length, 1, `Meldungen: ${JSON.stringify(w.meldungen)}`);
		w.stopp();
	});

	test('Sprache EN: Meldung im Katalogtext der aktuellen Sprache', async () => {
		locale.set('en');
		const a = abrufer(() => ({ trips: { t1: NB('07:00') }, compare: {} }));
		const w = await starte({ context: 'route', id: 't1', lifecycle: 'draft' }, a.holen);
		await w.setze('active');
		assert.deepEqual(w.meldungen, [`Activated. The first briefing arrives ${formatNextBriefing(NB('07:00') as never, 'route')}.`]);
		w.stopp();
	});
});

describe('AC-8: Quelle ohne Termin ⇒ nur „Aktiviert.“', () => {
	for (const [was, antwort] of [
		['Abruf scheitert', () => Promise.reject(new Error('502'))],
		['kein Eintrag für die id', () => ({ trips: {}, compare: {} })],
		['kein Termin (at null)', () => ({ trips: { t1: { at: null, reason: 'none' } }, compare: {} })],
		['kaputte Antwort', () => 'kaputt']
	] as const) {
		test(`${was} ⇒ genau eine Meldung „Aktiviert.“`, async () => {
			const a = abrufer(antwort as (p: string, n: number) => unknown);
			const w = await starte({ context: 'route', id: 't1', lifecycle: 'draft' }, a.holen);
			await w.setze('active');
			assert.equal(a.pfade.length, 1);
			assert.deepEqual(w.meldungen, ['Aktiviert.']);
			w.stopp();
		});
	}
});

describe('AC-9: kein Abruf und keine Meldung ohne echte Aktivierung', () => {
	for (const start of ['active', 'paused', 'archived'] as const) {
		test(`erstes Lesen „${start}“ ⇒ kein Abruf, keine Meldung`, async () => {
			const a = abrufer(() => ({ trips: { t1: NB('07:00') }, compare: {} }));
			const w = await starte({ context: 'route', id: 't1', lifecycle: start }, a.holen);
			assert.deepEqual(a.pfade, []);
			assert.deepEqual(w.meldungen, []);
			w.stopp();
		});
	}

	for (const [von, nach] of [
		['active', 'paused'],
		['paused', 'active'],
		['draft', 'archived'],
		['draft', 'paused'],
		['archived', 'active'],
		['active', 'archived']
	] as const) {
		test(`Wechsel ${von} → ${nach} ⇒ kein Abruf, keine Meldung`, async () => {
			const a = abrufer(() => ({ trips: { t1: NB('07:00') }, compare: {} }));
			const w = await starte({ context: 'route', id: 't1', lifecycle: von }, a.holen);
			await w.setze(nach);
			assert.deepEqual(a.pfade, []);
			assert.deepEqual(w.meldungen, []);
			w.stopp();
		});
	}

	test('draft → archived → active ist keine Aktivierung (vorher ist archiviert)', async () => {
		const a = abrufer(() => ({ trips: { t1: NB('07:00') }, compare: {} }));
		const w = await starte({ context: 'route', id: 't1', lifecycle: 'draft' }, a.holen);
		await w.setze('archived');
		await w.setze('active');
		assert.deepEqual(a.pfade, []);
		assert.deepEqual(w.meldungen, []);
		w.stopp();
	});

	test('fremdes Signal im Entwurf (ungespeicherte Eingabe) ⇒ kein Abruf', async () => {
		const a = abrufer(() => ({ trips: { t1: NB('07:00') }, compare: {} }));
		const w = await starte({ context: 'route', id: 't1', lifecycle: 'draft' }, a.holen);
		$.set(w.signale.fremd, 1);
		await setzen();
		assert.deepEqual(a.pfade, []);
		w.stopp();
	});
});

describe('Laufnummer: eine späte ältere Antwort überschreibt keine neuere', () => {
	test('zwei Aktivierungen nacheinander, die erste Antwort kommt zuletzt ⇒ nur die neuere wird gemeldet', async () => {
		let erstenAufloesen: (v: unknown) => void = () => {};
		const a = abrufer((_p, n) =>
			n === 1 ? new Promise((r) => (erstenAufloesen = r)) : { trips: { t1: NB('09:00') }, compare: {} }
		);
		const w = await starte({ context: 'route', id: 't1', lifecycle: 'draft' }, a.holen);
		await w.setze('active');
		assert.equal(a.pfade.length, 1, 'Messaufbau: erster Abruf läuft');
		await w.setze('draft');
		await w.setze('active');
		assert.equal(a.pfade.length, 2, 'Messaufbau: zweite Aktivierung ruft erneut ab');
		assert.deepEqual(w.meldungen, [MIT_ZEIT('09:00')], 'Messaufbau: neuere Antwort ist gemeldet');
		erstenAufloesen({ trips: { t1: NB('07:00') }, compare: {} });
		await setzen();
		assert.deepEqual(w.meldungen, [MIT_ZEIT('09:00')], 'veraltete Antwort hat eine Meldung ausgelöst');
		w.stopp();
	});
});
