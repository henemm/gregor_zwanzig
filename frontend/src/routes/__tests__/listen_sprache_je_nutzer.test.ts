// Issue #2652 (i18n F3, Epic #2644) — AC-3, AC-4, AC-5: Cockpit und Listen
// sprechen die Nutzersprache. Echter SSR-Render (svelte/server, Pruefstand
// f3HomeListenSsr.ts) mit fester Zeit-Fixture:
//   * AC-4: Deutsch ist byte-gleich zur Ausgabe VOR der Umstellung
//     (tests/golden/f3_home_listen/*.de.html, aus dem Ist-Stand geschrieben),
//   * AC-3: Trip-Liste und Archiv auf Englisch, Plural ueber tn(),
//   * AC-5: zwei Nutzer (en/de) nacheinander durch die ECHTEN Loader
//     (+layout.server.ts fuer die Sprache, trips/archiv +page.server.ts fuer die Daten).
// Jeder en-Fall rendert zuerst de und schaltet dann OHNE Neuladen auf en: eine
// Mutation tr()/$t -> trFor('de', …) macht ihn rot.
// Spec: docs/specs/modules/i18n_f3_home_listen_2652.md
//
//   cd frontend && npm test -- src/routes/__tests__/listen_sprache_je_nutzer.test.ts

import { test, describe, before, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import {
	FAELLE,
	GOLDEN_DIR,
	locale,
	trFor,
	trnFor,
	ladeArchivGolden,
	schreibeGolden,
	seiteRendern,
	mitApi,
	cookiesFuer,
	archivLoad,
	tripsLoad,
	layoutLoad,
	tripAktiv,
	tripGeplant,
	vergleich
} from './f3HomeListenSsr.ts';
import { deutscheReste, sichtbarerText, attributText } from './f3Sprachpruefung.ts';
import { presetLocationsLabel, presetTileScheduleLabel } from '../../lib/components/compare/subscriptionHelpers.ts';

before(async () => {
	await ladeArchivGolden();
	// Die de-Golden sind der Ist-Stand VOR der Umstellung und werden nie neu geschrieben;
	// nur die en-Ansicht (Review-Hilfe, nicht verglichen) wird aktualisiert.
	if (process.env.GZ_GOLDEN_SCHREIBEN === 'en') schreibeGolden('en');
});
afterEach(() => locale.set('de'));

// Einzige Normalisierung: jede Leerraumfolge wird EIN Leerzeichen. Mehrzeilige
// Fliesstexte standen vorher mit Zeilenumbruch+Tabs im Markup (Svelte gibt sie
// unveraendert aus); der Katalogwert ist einzeilig. HTML stellt beides gleich
// dar (white-space: normal, kein <pre> auf diesen Seiten). Jedes Zeichen
// ausser Leerraum ist byte-gleich, auch ein fehlendes/zusaetzliches Leerzeichen.
const leerraum = (s: string) => s.replace(/\s+/g, ' ');

describe('AC-4: Deutsch byte-gleich zum Ist-Stand vor der Umstellung (Golden golden-de)', () => {
	for (const fall of Object.keys(FAELLE)) {
		test(`${fall}.de.html`, () => {
			const golden = readFileSync(path.join(GOLDEN_DIR, `${fall}.de.html`), 'utf-8');
			locale.set('en');
			FAELLE[fall]();
			locale.set('de');
			assert.equal(leerraum(FAELLE[fall]() + '\n'), leerraum(golden));
		});
	}
	test('Messaufbau: Golden enthaelt die deutschen Fliesstexte und Zaehler', () => {
		const alle = Object.keys(FAELLE).map((f) => readFileSync(path.join(GOLDEN_DIR, `${f}.de.html`), 'utf-8')).join('');
		for (const s of ['Nächster Versand', 'Live · Tag 2 von 3', '2 von 2 Trips', '1 Ort', '3 Etappen', 'Noch keine Vergleiche angelegt.'])
			assert.ok(alle.includes(s), s);
	});
});

/** de rendern, dann ohne Neuladen auf en schalten und erneut rendern. */
function enNachDe(f: () => string): string {
	locale.set('de');
	f();
	locale.set('en');
	return f();
}
const en = (k: string, p?: Record<string, string | number>) => trFor('en', k, p);
const hat = (text: string, teil: string) => assert.ok(text.includes(teil), `fehlt: "${teil}"\n${text}`);
const nichtDeutsch = (html: string) => {
	assert.deepEqual(deutscheReste(sichtbarerText(html)), []);
	assert.deepEqual(deutscheReste(attributText(html)), []);
};
const DREI_TRIPS = [tripAktiv(), tripGeplant(), tripGeplant('trip-drei', 'Dritter Trip')];

describe('AC-3: Listen auf Englisch', () => {
	test('Trip-Liste: Ueberschrift, Stats, Spaltenkoepfe, Zaehler, Plural der Etappen', () => {
		const html = enNachDe(() => seiteRendern('trips', { trips: DREI_TRIPS, profile: null }));
		const s = sichtbarerText(html);
		for (const k of ['listen.trips.intro', 'listen.stat.aktiv', 'listen.stat.geplant', 'listen.stat.abgeschlossen',
			'listen.spalte.etappen', 'listen.spalte.zeitraum', 'listen.tabelle.aktionen', 'listen.aktion.briefing_senden'])
			hat(s, en(k));
		hat(s, en('listen.zaehler.trips', { gefiltert: 3, gesamt: 3 }));
		hat(s, trnFor('en', 'listen.anzahl.etappen', 3));
		hat(s, trnFor('en', 'listen.anzahl.etappen', 1));
		hat(s, en('listen.status.aktiv'));
		nichtDeutsch(html);
	});
	test('Zaehler „0 of 3 trips" und Such-Hinweis mit unveraendertem Suchbegriff', () => {
		assert.equal(en('listen.zaehler.trips', { gefiltert: 0, gesamt: 3 }), '0 of 3 trips');
		const hinweis = en('listen.leer.trip_suche', { suche: 'Ötztal »x«' });
		assert.ok(hinweis.includes('Ötztal »x«'), hinweis);
		assert.notEqual(hinweis, trFor('de', 'listen.leer.trip_suche', { suche: 'Ötztal »x«' }));
	});
	test('Trip-Liste leer: Leerzustand englisch', () => {
		const html = enNachDe(() => seiteRendern('trips', { trips: [], profile: null }));
		hat(sichtbarerText(html), en('listen.leer.trip'));
		hat(sichtbarerText(html), en('listen.leer.trip_text'));
		nichtDeutsch(html);
	});
	test('Compare-Liste leer, Orte-Liste: englisch', () => {
		const c = enNachDe(() => seiteRendern('compare', { presets: [], profile: null }));
		hat(sichtbarerText(c), en('listen.leer.vergleich'));
		hat(sichtbarerText(c), en('listen.zaehler.vergleiche', { gefiltert: 0, gesamt: 0 }));
		nichtDeutsch(c);
		const o = enNachDe(() => FAELLE.orte_liste());
		hat(sichtbarerText(o), en('listen.spalte.koordinaten'));
		nichtDeutsch(o);
		const leer = enNachDe(() => seiteRendern('locations', { locations: [] }));
		hat(sichtbarerText(leer), en('listen.orte.leer_titel'));
		nichtDeutsch(leer);
	});
	test('Compare-Liste mit Vergleich: Spalten, Status, Zeitplan-Zeile', () => {
		const c = enNachDe(() => seiteRendern('compare', { presets: [vergleich()], profile: null }));
		const s = sichtbarerText(c);
		hat(s, en('listen.spalte.orte'));
		hat(s, en('listen.status.aktiv'));
		// Zelleninhalte aus subscriptionHelpers.ts gehoeren F10 (Known Limitations) — vor der Pruefung entfernt.
		const p = vergleich() as unknown as Parameters<typeof presetLocationsLabel>[0];
		const f10 = [presetLocationsLabel(p), presetTileScheduleLabel(p)];
		assert.deepEqual(deutscheReste(f10.reduce((t, w) => t.split(w).join(' '), s)), []);
		assert.deepEqual(deutscheReste(attributText(c)), []);
	});
});

// ── AC-5: zwei Nutzer, echte Loader, Sprache je Anfrage ──────────────────────

const archivZeit = '2026-10-20T08:00:00Z';
const etappen = (n: number) => tripAktiv().stages.slice(0, n);
const API = {
	A: {
		'/api/auth/profile': { id: 'nutzer-a', language: 'en', role: 'user' },
		'/api/trips': [
			{ ...tripAktiv('a-live', 'Alpha Live'), archived_at: null },
			{ ...tripAktiv('a-eins', 'Alpha Eins'), stages: etappen(1), archived_at: archivZeit },
			{ ...tripAktiv('a-zwei', 'Alpha Zwei'), stages: etappen(2), archived_at: archivZeit }
		],
		'/api/compare/presets': [{ ...vergleich('a-cmp'), name: 'Alpha Cmp', location_ids: ['x'], archived_at: archivZeit }]
	},
	B: {
		'/api/auth/profile': { id: 'nutzer-b', language: 'de', role: 'user' },
		'/api/trips': [
			{ ...tripAktiv('b-live', 'Beta Live'), archived_at: null },
			{ ...tripAktiv('b-drei', 'Beta Drei'), archived_at: archivZeit }
		],
		'/api/compare/presets': [{ ...vergleich('b-cmp'), name: 'Beta Vergleich', location_ids: ['x', 'y'], archived_at: archivZeit }]
	}
};

/** Eine Anfrage wie im Betrieb: Layout-Loader (Sprache) + Seiten-Loader + Render. */
async function anfrage(sitzung: 'A' | 'B', seite: 'trips' | 'archiv') {
	const userId = sitzung === 'A' ? 'nutzer-a' : 'nutzer-b';
	return mitApi(API, async () => {
		const locals: Record<string, unknown> = { userId, lang: 'de' };
		const ereignis = { cookies: cookiesFuer(sitzung), locals } as never;
		const layout = (await layoutLoad(ereignis)) as { lang: 'de' | 'en' };
		const data = (await (seite === 'trips' ? tripsLoad : archivLoad)(ereignis)) as Record<string, unknown>;
		locale.set(layout.lang); // wie +layout.svelte: locale.set(data.lang)
		return { lang: layout.lang, localsLang: locals.lang, data, html: seiteRendern(seite, data) };
	});
}

describe('AC-5: Sprache und Daten je Nutzer, keine Wanderung', () => {
	test('A (en) und B (de) laden nacheinander /trips und /archiv', async () => {
		const a1 = await anfrage('A', 'trips');
		const b1 = await anfrage('B', 'trips');
		const a2 = await anfrage('A', 'archiv');
		const b2 = await anfrage('B', 'archiv');
		assert.deepEqual([a1.lang, a1.localsLang, b1.lang, b1.localsLang], ['en', 'en', 'de', 'de']);

		const sa1 = sichtbarerText(a1.html);
		hat(sa1, 'Alpha Live');
		hat(sa1, en('listen.zaehler.trips', { gefiltert: 1, gesamt: 1 }));
		assert.ok(!sa1.includes('Beta'), sa1);
		nichtDeutsch(a1.html);

		const sb1 = sichtbarerText(b1.html);
		hat(sb1, 'Beta Live');
		hat(sb1, '1 von 1 Trips');
		assert.ok(!sb1.includes('Alpha'), sb1);
		assert.ok(!sb1.includes(en('listen.trips.intro')), sb1);

		const sa2 = sichtbarerText(a2.html);
		hat(sa2, en('listen.archiv.titel'));
		hat(sa2, '1 stage');
		hat(sa2, '2 stages');
		hat(sa2, trnFor('en', 'listen.anzahl.orte', 1));
		assert.ok(!sa2.includes('Beta'), sa2);
		nichtDeutsch(a2.html);

		const sb2 = sichtbarerText(b2.html);
		hat(sb2, '3 Etappen');
		hat(sb2, '2 Orte');
		hat(sb2, 'Wieder aktivieren');
		assert.ok(!sb2.includes('Alpha') && !sb2.includes('stage'), sb2);
	});
	test('Archiv-Loader liefert count je Eintrag, detail bleibt (Bestand)', async () => {
		const { data } = await anfrage('A', 'archiv');
		const entries = data.entries as { name: string; count: number; detail: string }[];
		const eins = entries.find((e) => e.name === 'Alpha Eins')!;
		assert.equal(eins.count, 1);
		assert.equal(eins.detail, '1 Etappe');
		assert.equal(entries.find((e) => e.name === 'Alpha Cmp')!.count, 1);
	});
});
