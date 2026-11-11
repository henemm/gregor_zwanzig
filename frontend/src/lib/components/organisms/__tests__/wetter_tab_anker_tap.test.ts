// Issue #2913 Teil 2, Fix-Loop 1 (Adversary F001–F003).
// Spec: docs/specs/modules/feat_2913_s3_bausteine.md — K-5 (Touch-Ziele, Btn-Größe `tap`),
// K-6 (Ladeanzeige aus dem Atom Skelett, „Erneut laden“ als Btn), K-7 (Testids bleiben).
//
// Geprüft wird dort, wo die Zusicherung WIRKT: im Server-Render (svelte/server) der Organismen.
//   - F003: Lade-Phase von WetterTabInhalt (SSR-Startzustand) — Testid wetter-tab-laden mit dem
//     Skelett (role="status", aria-busy, aria-label aus dem Katalog).
//   - F001: Fehler-Phase von WetterTabInhalt — Testid wetter-tab-erneut-laden am Btn der Größe tap.
//     Die Fehler-Phase entsteht erst nach einem gescheiterten Laden (onMount, läuft im SSR nicht);
//     startzustandHook.mjs rendert die ECHTE Datei mit Startwert 'fehler' statt 'laedt'.
//   - F002: jeder gerenderte Btn (data-slot="btn") in MetrikZeile, VorlageKarte (zu und offen),
//     NichtImBriefing/ChipLeiste und WetterTabInhalt trägt data-size="tap" (Touch-Ziel ≥ 44px).
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/wetter_tab_anker_tap.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> organisms -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');
const WT = path.resolve(HERE, '..', 'wetter-tab');
const I18N = path.join(FRONTEND, 'src', 'lib', 'i18n', 'messages', 'de');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(pathToFileURL(path.join(HERE, 'startzustandHook.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');

const WETTER: Record<string, string> = JSON.parse(readFileSync(path.join(I18N, 'wetter.json'), 'utf8'));
const url = (n: string) => pathToFileURL(path.join(WT, `${n}.svelte`)).href;

async function lade(n: string, start: [string, string][] = []): Promise<any> {
	const abfrage = start.length ? `?start=${encodeURIComponent(JSON.stringify(start))}` : '';
	return (await import(url(n) + abfrage)).default;
}
const html = (k: any, props: Record<string, unknown>) => render(k, { props }).body.replace(/<!--[\s\S]*?-->/g, '');
const text = (h: string) =>
	h
		.replace(/<[^>]*>/g, ' ')
		.replace(/&nbsp;/g, ' ')
		.replace(/\s+/g, ' ')
		.trim();
const noop = () => {};

/** Öffnender Tag des Elements mit dieser Testid. */
function tagMitTestid(h: string, testid: string): string | null {
	return h.match(new RegExp(`<[a-z]+\\b[^>]*data-testid="${testid}"[^>]*>`))?.[0] ?? null;
}
/** Element mit dieser Testid samt Inhalt (bis zum passenden Schluss-Tag gleichen Namens). */
function elementMitTestid(h: string, testid: string): string | null {
	const m = h.match(new RegExp(`<([a-z]+)\\b[^>]*data-testid="${testid}"[^>]*>`));
	if (!m || m.index === undefined) return null;
	const name = m[1];
	const re = new RegExp(`<${name}\\b|</${name}>`, 'g');
	re.lastIndex = m.index + m[0].length;
	let tiefe = 1;
	for (let x = re.exec(h); x; x = re.exec(h)) {
		tiefe += x[0].startsWith('</') ? -1 : 1;
		if (tiefe === 0) return h.slice(m.index, x.index + x[0].length);
	}
	return null;
}
/** Alle öffnenden Tags gerenderter Btn (data-slot="btn"). */
function btnTags(h: string): string[] {
	return [...h.matchAll(/<(?:button|a)\b[^>]*\sdata-slot="btn"[^>]*>/g)].map((m) => m[0]);
}
function alleTap(h: string, wo: string, mindestens: number): void {
	const tags = btnTags(h);
	assert.ok(tags.length >= mindestens, `${wo}: erwartet mindestens ${mindestens} Btn, gefunden ${tags.length}`);
	const falsch = tags.filter((t) => !/\sdata-size="tap"/.test(t));
	assert.deepEqual(falsch, [], `${wo}: Btn ohne data-size="tap" (K-5 Touch-Ziel ≥ 44px)`);
}

// ─── WetterTabInhalt: Lade- und Fehler-Phase ─────────────────────────────────

const PHASE_START = "$state<'laedt' | 'fehler' | 'bereit'>('laedt')";
const inhaltProps = { context: 'route', trip: { id: 't1', name: 'Trip', stages: [] } };

describe('F003/K-6/K-7: WetterTabInhalt Lade-Phase', () => {
	test('SSR-Startzustand: Testid wetter-tab-laden mit dem Skelett (role=status, aria-busy, Katalogtext)', async () => {
		const W = await lade('WetterTabInhalt');
		const h = html(W, inhaltProps);
		const laden = elementMitTestid(h, 'wetter-tab-laden');
		assert.ok(laden, 'Testid wetter-tab-laden fehlt in der Lade-Phase');
		assert.match(tagMitTestid(laden!, 'wetter-tab-laden')!, /\saria-busy="true"/);
		const skelett = laden!.match(/<div\b[^>]*\sdata-slot="skelett"[^>]*>/)?.[0];
		assert.ok(skelett, 'Lade-Phase ohne das Atom Skelett');
		assert.match(skelett!, /\srole="status"/);
		assert.match(skelett!, /\saria-busy="true"/);
		assert.match(skelett!, new RegExp(`\\saria-label="${WETTER['wetter.kopf.laden']}"`));
		assert.doesNotMatch(h, /data-testid="wetter-tab-fehler"/, 'Lade-Phase zeigt keinen Fehler');
	});
});

describe('F001/K-5/K-7: WetterTabInhalt Fehler-Phase', () => {
	test('Fehler-Phase: role=alert, Testid wetter-tab-erneut-laden am Btn der Größe tap mit Katalogtext', async () => {
		const W = await lade('WetterTabInhalt', [[PHASE_START, PHASE_START.replace("('laedt')", "('fehler')")]]);
		const h = html(W, inhaltProps);
		const fehler = elementMitTestid(h, 'wetter-tab-fehler');
		assert.ok(fehler, 'Fehler-Phase nicht gerendert');
		assert.match(tagMitTestid(h, 'wetter-tab-fehler')!, /\srole="alert"/);
		assert.doesNotMatch(h, /data-testid="wetter-tab-laden"/, 'Fehler-Phase zeigt keine Ladeanzeige');
		const knopf = elementMitTestid(fehler!, 'wetter-tab-erneut-laden');
		assert.ok(knopf, 'Testid wetter-tab-erneut-laden fehlt in der Fehler-Phase');
		const tag = tagMitTestid(knopf!, 'wetter-tab-erneut-laden')!;
		assert.match(tag, /^<button\b/);
		assert.match(tag, /\sdata-slot="btn"/);
		assert.match(tag, /\sdata-size="tap"/);
		assert.equal(text(knopf!), WETTER['wetter.kopf.erneut_laden']);
		alleTap(h, 'WetterTabInhalt (Fehler-Phase)', 1);
	});
});

// ─── F002/K-5: jeder Btn der Organismen in Größe tap ─────────────────────────

const EIG = { id: 'wind', group: 'wind', alertable: true, is_precursor: false, allowed_sides: 'upper', display_only: false, unit: 'km/h' };
const zeileProps = (offen: boolean) => ({
	id: 'wind',
	name: 'Wind',
	eig: EIG,
	eintrag: { alarm_ab: 'orange', upper: { yellow: 30, orange: 50, red: 70 } },
	thunder: undefined,
	offen,
	abweichend: false,
	vorlageLabel: 'Standard',
	fehler: [],
	onEntfernen: noop,
	onAlarmAb: noop,
	onGrenzen: noop,
	onWert: noop,
	onGewitter: noop
});

describe('F002/K-5: Btn im Wetter-Reiter tragen data-size="tap"', () => {
	for (const offen of [false, true]) {
		test(`MetrikZeile (Grenzen ${offen ? 'offen' : 'zu'}): Entfernen und Grenzen ändern sind Btn tap`, async () => {
			const Z = await lade('MetrikZeile');
			const h = html(Z, zeileProps(offen));
			for (const id of ['wetter-zeile-entfernen-wind', 'wetter-grenzen-aendern-wind']) {
				const tag = tagMitTestid(h, id);
				assert.ok(tag, `Testid ${id} fehlt`);
				assert.match(tag!, /\sdata-slot="btn"/, `${id} ist kein Btn`);
				assert.match(tag!, /\sdata-size="tap"/, `${id} ohne data-size="tap"`);
			}
			alleTap(h, 'MetrikZeile', 2);
		});
	}

	const LISTE = [
		{ id: 'standard', label: 'Standard', anzahl: 3, stichworte: ['wind'] },
		{ id: 'alpin', label: 'Alpin', anzahl: 2, stichworte: [] }
	];
	const vorlageProps = {
		context: 'route',
		vorlageId: 'standard',
		liste: LISTE,
		eigene: [{ id: 'e1', name: 'Meine', ampel: {} }],
		abweichungen: 1,
		metrikName: (id: string) => id,
		aboAmpel: {},
		onUebernehmen: noop,
		onEigene: noop,
		onZuruecksetzen: noop,
		onGespeichert: noop
	};
	test('VorlageKarte (Menü zu): Picker, Als eigene, Zurücksetzen sind Btn tap', async () => {
		const V = await lade('VorlageKarte');
		const h = html(V, vorlageProps);
		for (const id of ['wetter-vorlage-picker', 'wetter-vorlage-als-eigene', 'wetter-vorlage-zuruecksetzen']) {
			assert.match(tagMitTestid(h, id) ?? '', /\sdata-size="tap"/, `${id} fehlt oder ohne data-size="tap"`);
		}
		alleTap(h, 'VorlageKarte (zu)', 3);
	});
	test('VorlageKarte (Menü offen mit Rückfrage): Optionen, Eigene, Übernehmen, Abbrechen sind Btn tap', async () => {
		const V = await lade('VorlageKarte', [
			['let pickerOffen = $state(false);', 'let pickerOffen = $state(true);'],
			[
				'let wahl = $state<{ id: string; name: string; eigen: boolean } | null>(null);',
				"let wahl = $state<{ id: string; name: string; eigen: boolean } | null>({ id: 'alpin', name: 'Alpin', eigen: false });"
			]
		]);
		const h = html(V, vorlageProps);
		for (const id of [
			'wetter-vorlage-wechsel-uebernehmen',
			'wetter-vorlage-wechsel-abbrechen',
			'wetter-vorlage-option-standard',
			'wetter-vorlage-option-alpin',
			'wetter-vorlage-eigene-e1'
		]) {
			assert.match(tagMitTestid(h, id) ?? '', /\sdata-size="tap"/, `${id} fehlt oder ohne data-size="tap"`);
		}
		alleTap(h, 'VorlageKarte (offen)', 8);
	});
	test('NichtImBriefing (ChipLeiste): jeder Chip ist Btn tap', async () => {
		const N = await lade('NichtImBriefing');
		const h = html(N, {
			metriken: [
				{ id: 'wind', name: 'Wind' },
				{ id: 'gust', name: 'Böen' }
			],
			hinzugefuegt: null,
			onHinzufuegen: noop
		});
		for (const id of ['wind', 'gust']) {
			assert.match(tagMitTestid(h, `wetter-nicht-im-briefing-plus-${id}`) ?? '', /\sdata-size="tap"/);
		}
		alleTap(h, 'NichtImBriefing', 2);
	});
});
