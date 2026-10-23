// Issue #1969 Fix-Loop 1 (Adversary F002) — AC-18/AC-19 im ECHTEN Laufzeitverhalten.
// Spec: docs/specs/modules/feat_1969_naechstes_briefing.md
//
// Prüfling: shared/versand-tab/naechstesBriefingLader.svelte.ts — der EINE
// reaktive Lader hinter VTNextBriefing (Versand-Reiter Trip + Vergleich),
// CompareTabs (Hub-Stat) und HubOverview (Karte).
//
// Testart: das Runen-Modul wird mit dem echten Svelte-Compiler für die
// CLIENT-Laufzeit übersetzt (clientRunenHook.mjs) und unter `effect_root` +
// `flush` ausgeführt — echte Abhängigkeits-Verfolgung, kein DOM nötig. Der
// Abrufer ist ein aufzeichnender Stub am Netz-Ausgang (Pfad → Antwort).
//
// Dass die Komponenten den Lader mit der RICHTIGEN Quelle füttern (context,
// id, savedAt), prüft naechstes_briefing_verdrahtung.test.ts.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/shared/versand-tab/__tests__/naechstes_briefing_lader_laufzeit.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
register(pathToFileURL(path.join(HERE, 'clientRunenHook.mjs')).href, pathToFileURL(HERE + '/').href);

// Interne Client-Laufzeit (ohne Typdeklaration) — Spezifizierer als Wert, damit
// svelte-check keinen Typ verlangt.
const CLIENT_LAUFZEIT: string = 'svelte/internal/client';
const $ = (await import(CLIENT_LAUFZEIT)) as Record<string, any>;
const { erstelleNaechstesBriefingLader } = await import(
	pathToFileURL(path.join(HERE, '..', 'naechstesBriefingLader.svelte.ts')).href
);

const NB = (local_time: string) => ({
	at: `2026-10-22T${local_time}:00+02:00`,
	local_date: '2026-10-22',
	local_time,
	tz: 'Europe/Paris',
	tz_abbr: 'CEST',
	slot: 'morning'
});

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

/** Lader in einer echten Effekt-Wurzel; Quelle liest echte Signale. */
function starte(start: { context: string; id?: string; neuLaden?: unknown; extern?: unknown }, holen: (p: string) => Promise<unknown>) {
	const signale = {
		context: $.state(start.context),
		id: $.state(start.id),
		neuLaden: $.state(start.neuLaden),
		extern: $.state(start.extern),
		entwurf: $.state('07:00')
	};
	let lader: any;
	const stopp = $.effect_root(() => {
		lader = erstelleNaechstesBriefingLader(
			() => ({
				context: $.get(signale.context),
				id: $.get(signale.id),
				neuLaden: $.get(signale.neuLaden),
				extern: $.get(signale.extern)
			}),
			holen
		);
	});
	return { signale, get lader() { return lader; }, stopp };
}

describe('AC-18: Abruf je Kontext, Anzeige-Wert aus dem richtigen Bereich', () => {
	test('vergleich → ?preset_id=, Wert aus .compare[id]', async () => {
		const a = abrufer(() => ({ trips: { p1: NB('09:00') }, compare: { p1: NB('07:00') } }));
		const l = starte({ context: 'vergleich', id: 'p1' }, a.holen);
		await setzen();
		assert.deepEqual(a.pfade, ['/api/next-briefings?preset_id=p1']);
		assert.equal(l.lader.wert?.local_time, '07:00');
		l.stopp();
	});

	test('route → ?trip_id=, Wert aus .trips[id]', async () => {
		const a = abrufer(() => ({ trips: { t1: NB('08:00') }, compare: { t1: NB('07:00') } }));
		const l = starte({ context: 'route', id: 't1' }, a.holen);
		await setzen();
		assert.deepEqual(a.pfade, ['/api/next-briefings?trip_id=t1']);
		assert.equal(l.lader.wert?.local_time, '08:00');
		l.stopp();
	});
});

describe('AC-18: Neuladen nur nach gespeicherter Änderung (neuLaden = savedAt)', () => {
	test('neuLaden ändert sich → erneuter Abruf, neuer Wert wird angezeigt', async () => {
		const a = abrufer((_p, n) => ({ trips: { t1: NB(n === 1 ? '07:00' : '09:00') }, compare: {} }));
		const l = starte({ context: 'route', id: 't1', neuLaden: 'gespeichert-1' }, a.holen);
		await setzen();
		assert.equal(l.lader.wert?.local_time, '07:00');
		$.set(l.signale.neuLaden, 'gespeichert-2');
		await setzen();
		assert.equal(a.pfade.length, 2, 'Speichern muss einen erneuten Abruf auslösen');
		assert.equal(l.lader.wert?.local_time, '09:00');
		l.stopp();
	});

	test('ungespeicherte Eingabe (fremdes Signal) → KEIN Abruf', async () => {
		const a = abrufer(() => ({ trips: { t1: NB('07:00') }, compare: {} }));
		const l = starte({ context: 'route', id: 't1', neuLaden: 'gespeichert-1' }, a.holen);
		await setzen();
		$.set(l.signale.entwurf, '10:00');
		await setzen();
		assert.equal(a.pfade.length, 1);
		l.stopp();
	});
});

describe('Schutz gegen veraltete Antworten (Laufnummer)', () => {
	test('eine langsamere, ältere Antwort überschreibt die neuere nicht', async () => {
		let erstenAufloesen: (v: unknown) => void = () => {};
		const a = abrufer((_p, n) =>
			n === 1
				? new Promise((r) => (erstenAufloesen = r))
				: { trips: { t1: NB('09:00') }, compare: {} }
		);
		const l = starte({ context: 'route', id: 't1', neuLaden: 1 }, a.holen);
		await setzen();
		$.set(l.signale.neuLaden, 2);
		await setzen();
		assert.equal(l.lader.wert?.local_time, '09:00', 'Messaufbau: neuere Antwort ist da');
		erstenAufloesen({ trips: { t1: NB('07:00') }, compare: {} });
		await setzen();
		assert.equal(l.lader.wert?.local_time, '09:00', 'veraltete Antwort hat die neuere überschrieben');
		l.stopp();
	});
});

describe('Schutz gegen veraltete Antworten nach Wegfall der id (F011)', () => {
	test('id fällt weg, danach trifft die alte Antwort ein → wird NICHT übernommen', async () => {
		let aufloesen: (v: unknown) => void = () => {};
		const a = abrufer(() => new Promise((r) => (aufloesen = r)));
		const l = starte({ context: 'route', id: 't1' }, a.holen);
		await setzen();
		assert.equal(a.pfade.length, 1, 'Messaufbau: Abruf läuft');
		$.set(l.signale.id, undefined);
		await setzen();
		aufloesen({ trips: { t1: NB('07:00') }, compare: {} });
		await setzen();
		assert.equal(l.lader.wert, undefined, 'Antwort für eine weggefallene id wurde übernommen');
		l.stopp();
	});
});

describe('AC-19 / Anlege-Seite / Wert von aussen', () => {
	test('ohne id → kein Abruf, Wert bleibt „nicht geladen"', async () => {
		const a = abrufer(() => ({ trips: {}, compare: {} }));
		const l = starte({ context: 'route', id: undefined }, a.holen);
		await setzen();
		assert.equal(a.pfade.length, 0);
		assert.equal(l.lader.wert, undefined);
		l.stopp();
	});

	test('Abruf scheitert → null (Anzeige „—"), kein Absturz', async () => {
		const a = abrufer(() => Promise.reject(new Error('502')));
		const l = starte({ context: 'vergleich', id: 'p1' }, a.holen);
		await setzen();
		assert.equal(l.lader.wert, null);
		l.stopp();
	});

	test('Wert von aussen gesetzt → kein eigener Abruf, dieser Wert wird gezeigt', async () => {
		const a = abrufer(() => ({ trips: {}, compare: {} }));
		const l = starte({ context: 'route', id: 't1', extern: NB('08:00') }, a.holen);
		await setzen();
		assert.equal(a.pfade.length, 0);
		assert.equal(l.lader.wert?.local_time, '08:00');
		l.stopp();
	});
});
