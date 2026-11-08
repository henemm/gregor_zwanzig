// TDD RED — Issue #2277 Scheibe S2b: /trips/new übernimmt den Rahmen von
// /compare/new — Zurück über PageHeader/BackLink (Button-Pfad mit onCancel),
// Speichern in je einem EditorStickyFooter (context="route",
// navClearance={false}), Fade-Maske auf der mobilen Tab-Leiste.
//
// Spec: docs/specs/modules/fix_2277_s2b_mobile_rahmen_angleichung.md
//       (AC-3, AC-4, AC-8, AC-9, AC-10)
//
// Echtes SSR-Rendering über tripNewSsr.ts (Issue #1738). Beide Viewport-Bäume
// (.tn-desktop/.tn-mobile) rendern in JEDEM Aufruf (CSS-Umschaltung) — die
// Prüfungen laufen deshalb innerhalb der Wrapper-Testids, nicht über
// `bereichVon()` (das ordnet die App-Leiste oben im Dokument dem Desktop-Baum zu).
//
// RED HEUTE: kein back-link in /trips/new, Speichern-Tasten sitzen inline in
// Breadcrumb/App-Leiste, keine Fade-Maske auf tn-mobile-tabbar, kein
// aria-label am Zurück-Pfeil. AC-9 ist ein Strukturwächter und schon heute grün.
//
// #2837 S2 (docs/specs/modules/rework_2837_s2_anlege_rahmen.md, Tabelle „Divergenz-
// verankernde Tests"): UMGEDREHT, nicht gelöscht — Desktop-Zurück wird Breadcrumb des
// AnlegeRahmen (AC-1), Desktop-Fuß mit Abbrechen links / Btn primary rechts (AC-5/AC-8),
// mobiler Abschluss „Trip speichern" (AC-12), Aria-Wächter folgt dem Rahmen. Mobil-Zurück,
// Footer-Mounts, Sperre, Fade-Maske und Strukturwächter AC-9 bleiben wörtlich.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/trip-new/__tests__/trip_new_mobile_rahmen_angleichung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { renderTripNew, countTestid, outerHtml, visibleText } from './tripNewSsr.ts';

const DESKTOP = { activeTab: 'route', isMobileViewport: false };
const MOBIL = { activeTab: 'route', isMobileViewport: true };
// #2347 S4 (AN-9) löst „tn-mobile-save in jedem Schritt" ab: der mobile Abschluss
// steht wie cm-mobile-activate im Vergleich erst im letzten Schritt Alarme im
// Sticky-Footer. Die tn-mobile-save-Prüfungen rendern deshalb im Schritt Alarme.
// Die Vorbelegung von activeTab ruft switchTab NICHT auf ⇒ alVisited bleibt
// false, der Anfangszustand „nicht speicherbereit" bleibt erhalten.
const DESKTOP_ALARME = { activeTab: 'alarme', isMobileViewport: false };
const MOBIL_ALARME = { activeTab: 'alarme', isMobileViewport: true };

const BUTTON_BACKLINK = /<button\b[^>]*data-testid="back-link"[^>]*>/g;
const ANCHOR_BACKLINK = /<a\b[^>]*data-testid="back-link"[^>]*>/g;

function treffer(markup: string, re: RegExp): string[] {
	return [...markup.matchAll(re)].map((m) => m[0]);
}

/** [start, ende) des <div>, dessen öffnender Tag bei `start` beginnt. */
function divBereich(html: string, start: number): [number, number] {
	const re = /<div\b[^>]*>|<\/div>/g;
	re.lastIndex = start;
	let depth = 0;
	let m: RegExpExecArray | null;
	while ((m = re.exec(html))) {
		if (m[0].startsWith('</')) {
			depth--;
			if (depth === 0) return [start, m.index + m[0].length];
		} else if (!m[0].endsWith('/>')) {
			depth++;
		}
	}
	assert.fail(`<div> ab Index ${start} nicht geschlossen.`);
}

interface Footer {
	tag: string;
	bereich: [number, number];
}

/** Alle EditorStickyFooter-Instanzen mit data-context="route". */
function routeFooter(html: string): Footer[] {
	const re = /<div\b[^>]*class="[^"]*\beditor-sticky-footer\b[^"]*"[^>]*>/g;
	return [...html.matchAll(re)]
		.filter((m) => /\bdata-context="route"/.test(m[0]))
		.map((m) => ({ tag: m[0], bereich: divBereich(html, m.index!) }));
}

function footerUm(html: string, testid: string): Footer {
	const idx = html.indexOf(`data-testid="${testid}"`);
	assert.notEqual(idx, -1, `Testid "${testid}" fehlt im gerenderten Dokument.`);
	const footer = routeFooter(html).find((f) => f.bereich[0] < idx && idx < f.bereich[1]);
	assert.ok(
		footer,
		`AC-4 FAIL: "${testid}" steht in keinem <EditorStickyFooter context="route"> ` +
			`(gefundene route-Footer: ${routeFooter(html).length}).`
	);
	return footer!;
}

function hatKlasse(tag: string, klasse: string): boolean {
	const cls = /\bclass="([^"]*)"/.exec(tag)?.[1] ?? '';
	return cls.split(/\s+/).includes(klasse);
}

// #2837 S2 (rework_2837_s2_anlege_rahmen.md, Entscheidung 1 / AC-1, AC-2) — UMGEDREHT: der
// Desktop-Kopf ist kein Zurück-Knopf mehr, sondern der Breadcrumb des geteilten AnlegeRahmen
// „Trips / Neuer Trip". Der Elternteil ist EIN Link mit href="/trips" (Adresse bleibt) und
// Katalogtext; sein Klick ruft onCancel (kein Autosave) — die Klickwirkung prüft die E2E
// anlege-rahmen-paritaet (AR-2), denn SSR führt keine Ereignisse aus. Weiterhin verboten:
// ein <a data-testid="back-link"> (Zurück per reinem href am intentionalCancel vorbei).
// Mobil bleibt der Zurück-Pfeil ein Button (Entscheidung 2).
describe('AC-3: Zurück in /trips/new — Desktop Breadcrumb (#2837 S2), mobil BackLink im Button-Modus', () => {
	test('Desktop: tn-desktop-breadcrumb = „Trips / Neuer Trip", Elternteil GENAU EIN <a href="/trips"> mit Katalogtext, Kind kein Link, kein Zurück-Knopf', () => {
		const wrapper = outerHtml(renderTripNew(DESKTOP), 'tn-desktop-breadcrumb');
		const links = treffer(wrapper, /<a\b[^>]*>[\s\S]*?<\/a>/g);
		assert.equal(links.length, 1, `#2837 S2 AC-1 FAIL: erwartet genau 1 Link im Desktop-Breadcrumb, gefunden ${links.length}.`);
		assert.match(links[0], /^<a\b[^>]*\shref="\/trips"/, `#2837 S2 AC-1 FAIL: Elternteil verlinkt nicht auf /trips: ${links[0]}`);
		assert.equal(visibleText(links[0]), 'Trips', '#2837 S2 AC-1 FAIL: Elternteil-Text ist nicht der Katalogtext „Trips".');
		assert.ok(visibleText(wrapper).includes('Neuer Trip'), `#2837 S2 AC-1 FAIL: Kind „Neuer Trip" fehlt: „${visibleText(wrapper)}"`);
		assert.ok(!visibleText(links[0]).includes('Neuer Trip'), '#2837 S2 AC-1 FAIL: das Kind ist Teil des Links.');
		assert.equal(treffer(wrapper, BUTTON_BACKLINK).length, 0, '#2837 S2 AC-1 FAIL: im Desktop-Breadcrumb steht noch der Zurück-Knopf.');
		assert.equal(
			treffer(wrapper, ANCHOR_BACKLINK).length,
			0,
			'AC-3 FAIL: Desktop-Breadcrumb enthält ein <a data-testid="back-link"> — Zurück navigiert per href ' +
				'und überspringt intentionalCancel (Autosave-Regression).'
		);
	});

	test('Mobil: tn-mobile-appbar enthält GENAU EINEN <button data-testid="back-link"> ohne href, kein <a>', () => {
		const wrapper = outerHtml(renderTripNew(MOBIL), 'tn-mobile-appbar');
		const buttons = treffer(wrapper, BUTTON_BACKLINK);
		assert.equal(
			buttons.length,
			1,
			`AC-3 FAIL: erwartet genau 1 <button data-testid="back-link"> in der App-Leiste, gefunden ${buttons.length}.`
		);
		assert.ok(!/\bhref=/.test(buttons[0]), `AC-3 FAIL: Zurück-Button trägt href: ${buttons[0]}`);
		assert.equal(
			treffer(wrapper, ANCHOR_BACKLINK).length,
			0,
			'AC-3 FAIL: App-Leiste enthält ein <a data-testid="back-link"> — Zurück navigiert per href.'
		);
		// #2837 S2 Entscheidung 2: Beschriftung = Elternteil aus dem Katalog.
		assert.equal(visibleText(outerHtml(wrapper, 'back-link')), 'Trips', '#2837 S2 AC-3 FAIL: Zurück-Pfeil trägt nicht den Katalogtext „Trips".');
	});
});

describe('AC-4: Speichern wandert in je einen EditorStickyFooter (context="route", navClearance={false})', () => {
	test('Zählungen: trip-new-save-btn = 1, tn-mobile-appbar = 1 (Desktop), tn-mobile-save = 1 (Mobil)', () => {
		const d = renderTripNew(DESKTOP);
		assert.equal(countTestid(d, 'trip-new-save-btn'), 1, 'AC-4 FAIL: trip-new-save-btn nicht genau 1×.');
		assert.equal(countTestid(d, 'tn-mobile-appbar'), 1, 'AC-4 FAIL: Wrapper tn-mobile-appbar nicht genau 1×.');
		const m = renderTripNew(MOBIL_ALARME);
		assert.equal(countTestid(m, 'tn-mobile-save'), 1, 'AC-4 FAIL: tn-mobile-save nicht genau 1×.');
	});

	test('Desktop: trip-new-save-btn sitzt NICHT mehr im Breadcrumb, sondern in einem route-Footer ohne has-nav', () => {
		const html = renderTripNew(DESKTOP);
		assert.ok(
			!outerHtml(html, 'tn-desktop-breadcrumb').includes('data-testid="trip-new-save-btn"'),
			'AC-4 FAIL: trip-new-save-btn steht weiterhin inline im Desktop-Breadcrumb.'
		);
		const footer = footerUm(html, 'trip-new-save-btn');
		assert.ok(
			!hatKlasse(footer.tag, 'has-nav'),
			`AC-4 FAIL: Desktop-Footer reserviert Platz für die BottomNav (navClearance nicht false): ${footer.tag}`
		);
	});

	test('Mobil: tn-mobile-save sitzt NICHT mehr in der App-Leiste, sondern in einem route-Footer ohne has-nav', () => {
		const html = renderTripNew(MOBIL_ALARME);
		assert.ok(
			!outerHtml(html, 'tn-mobile-appbar').includes('data-testid="tn-mobile-save"'),
			'AC-4 FAIL: tn-mobile-save steht weiterhin inline in der App-Leiste.'
		);
		const footer = footerUm(html, 'tn-mobile-save');
		assert.ok(
			!hatKlasse(footer.tag, 'has-nav'),
			`AC-4 FAIL: Mobil-Footer reserviert Platz für die BottomNav (navClearance nicht false): ${footer.tag}`
		);
	});

	// #2837 S2 (Entscheidungen 4/5, AC-5/AC-8): der Desktop-Fuß ist der Fuß des AnlegeRahmen —
	// „Abbrechen" (Btn ghost) links, Hauptaktion trip-new-save-btn (Btn primary) rechts.
	test('#2837 S2: Desktop-Fuß tn-desktop-footer — Abbrechen (Btn ghost) VOR trip-new-save-btn (Btn primary)', () => {
		const footer = outerHtml(renderTripNew(DESKTOP), 'tn-desktop-footer');
		const save = /<button\b[^>]*data-testid="trip-new-save-btn"[^>]*>/.exec(footer);
		assert.ok(save, '#2837 S2 FAIL: trip-new-save-btn steht nicht im tn-desktop-footer.');
		assert.match(save[0], /\sdata-slot="btn"/, `#2837 S2 AC-8 FAIL: Trip speichern ist kein Btn: ${save[0]}`);
		assert.match(save[0], /\sdata-variant="primary"/, `#2837 S2 AC-8 FAIL: Trip speichern ist nicht Btn primary: ${save[0]}`);
		const ab = [...footer.matchAll(/<(button|a)\b[^>]*data-slot="btn"[^>]*>([\s\S]*?)<\/\1>/g)].filter((m) => visibleText(m[2]) === 'Abbrechen');
		assert.equal(ab.length, 1, `#2837 S2 AC-5 FAIL: erwartet genau 1 „Abbrechen" im Desktop-Fuß, gefunden ${ab.length}.`);
		assert.match(ab[0][0], /\sdata-variant="ghost"/, '#2837 S2 AC-5 FAIL: Abbrechen ist nicht Btn ghost.');
		assert.ok(ab[0].index! < save.index, '#2837 S2 AC-5 FAIL: Abbrechen steht nicht links von „Trip speichern".');
	});

	test('zwei getrennte Footer-Mounts (einer je Viewport-Zweig)', () => {
		const html = renderTripNew(DESKTOP_ALARME);
		const d = footerUm(html, 'trip-new-save-btn');
		const m = footerUm(html, 'tn-mobile-save');
		assert.notEqual(
			d.bereich[0],
			m.bereich[0],
			'AC-4 FAIL: Desktop- und Mobil-Speichern teilen sich EINEN Footer statt je einem Mount pro Zweig.'
		);
	});
});

describe('AC-4: Speichern ist gesperrt, solange der Trip nicht speicherbereit ist', () => {
	function tagMitTestid(html: string, testid: string): string {
		const m = new RegExp(`<[a-zA-Z]+\\b[^>]*data-testid="${testid}"[^>]*>`).exec(html);
		assert.ok(m, `Testid "${testid}" fehlt im gerenderten Dokument.`);
		return m![0];
	}

	for (const testid of ['trip-new-save-btn', 'tn-mobile-save']) {
		test(`${testid} trägt im Anfangszustand das Attribut disabled`, () => {
			const tag = tagMitTestid(renderTripNew(testid === 'tn-mobile-save' ? DESKTOP_ALARME : DESKTOP), testid);
			assert.match(tag, /^<button\b/, `${testid} ist kein <button>: ${tag}`);
			assert.match(
				tag,
				/\sdisabled(?:=""|\s|>|$)/,
				`${testid}: Speichern wirkt aktiv, obwohl der Zeitplan fehlt (disabled fehlt): ${tag}`
			);
		});
	}
});

describe('AC-8: Fade-Maske auf tn-mobile-tabbar (wörtlich wie cm-mobile-tabbar)', () => {
	const GRADIENT =
		'linear-gradient\\(to right, transparent, black 16px, black calc\\(100% - 16px\\), transparent\\)';

	function tabbarTag(): string {
		const outer = outerHtml(renderTripNew(MOBIL), 'tn-mobile-tabbar');
		return outer.slice(0, outer.indexOf('>') + 1);
	}

	test('Standard-Deklaration mask-image (nicht nur als Teil von -webkit-mask-image)', () => {
		const tag = tabbarTag();
		assert.match(
			tag,
			new RegExp(`(?<!-webkit-)mask-image:\\s*${GRADIENT}`),
			`AC-8 FAIL: tn-mobile-tabbar trägt keine Standard-mask-image-Deklaration: ${tag}`
		);
	});

	test('-webkit-mask-image-Variante', () => {
		const tag = tabbarTag();
		assert.match(
			tag,
			new RegExp(`-webkit-mask-image:\\s*${GRADIENT}`),
			`AC-8 FAIL: tn-mobile-tabbar trägt keine -webkit-mask-image-Deklaration: ${tag}`
		);
	});
});

describe('AC-9: Strukturwächter — vertragliche Testids je Render genau einmal', () => {
	const TESTIDS = ['tn-mobile-appbar', 'tn-mobile-save', 'tn-desktop-breadcrumb', 'tn-mobile-tabbar'];
	for (const [name, kombi, kombiAlarme] of [
		['Desktop', DESKTOP, DESKTOP_ALARME],
		['Mobil', MOBIL, MOBIL_ALARME]
	] as const) {
		for (const testid of TESTIDS) {
			// tn-mobile-save nur im Schritt Alarme (AN-9), die übrigen im Schritt Route.
			test(`${name}: ${testid} genau 1× (nie 0, nie 2)`, () => {
				assert.equal(
					countTestid(renderTripNew(testid === 'tn-mobile-save' ? kombiAlarme : kombi), testid),
					1,
					`AC-9 FAIL: ${testid} erscheint im ${name}-Render nicht genau einmal.`
				);
			});
		}
		test(`${name}: tn-mobile-save fehlt vor dem Schritt Alarme (AN-9)`, () => {
			assert.equal(
				countTestid(renderTripNew(kombi), 'tn-mobile-save'),
				0,
				'AN-9 FAIL: der mobile Abschluss steht schon im Schritt Route.'
			);
		});
	}
});

// #2837 S2 AC-12: der mobile Abschluss heißt wie der Desktop-Abschluss „Trip speichern"
// (Katalog trip.anlegen.speichern), nicht mehr „Speichern" (aktionen.speichern).
describe('#2837 S2 AC-12: mobiler Abschluss „Trip speichern"', () => {
	test('tn-mobile-save (Schritt Alarme) trägt den Text „Trip speichern"', () => {
		assert.equal(visibleText(outerHtml(renderTripNew(MOBIL_ALARME), 'tn-mobile-save')), 'Trip speichern');
	});
});

// #2837 S2 — Aria-Wächter folgt dem Rahmen: mobil bleibt der Zurück-Pfeil mit „Zurück: Trips";
// Desktop ist ein Breadcrumb-Link, dessen zugänglicher Name der sichtbare Katalogtext „Trips" ist
// (kein Zurück-Knopf mehr, also auch kein „Zurück: Trips" dort).
describe('AC-10: Vorlesetext am Zurück-Pfeil (mobil) bzw. Breadcrumb-Link (Desktop)', () => {
	test('Mobil: tn-mobile-appbar enthält aria-label="Zurück: Trips" genau einmal', () => {
		const wrapper = outerHtml(renderTripNew(MOBIL), 'tn-mobile-appbar');
		assert.equal(
			treffer(wrapper, /aria-label="Zurück: Trips"/g).length,
			1,
			'AC-10 FAIL: der Zurück-Pfeil der App-Leiste trägt nicht genau einmal aria-label="Zurück: Trips".'
		);
	});

	test('Desktop: Breadcrumb-Link heißt „Trips" (aria-label, falls gesetzt, nennt ebenfalls „Trips"), kein „Zurück: Trips"-Knopf', () => {
		const wrapper = outerHtml(renderTripNew(DESKTOP), 'tn-desktop-breadcrumb');
		const link = /<a\b[^>]*\shref="\/trips"[^>]*>([\s\S]*?)<\/a>/.exec(wrapper);
		assert.ok(link, '#2837 S2 AC-10 FAIL: kein Breadcrumb-Link auf /trips.');
		assert.equal(visibleText(link[1]), 'Trips', '#2837 S2 AC-10 FAIL: zugänglicher Name des Links ist nicht „Trips".');
		const aria = /\saria-label="([^"]*)"/.exec(link[0].slice(0, link[0].indexOf('>') + 1));
		if (aria) assert.ok(aria[1].includes('Trips'), `#2837 S2 AC-10 FAIL: aria-label „${aria[1]}" verdeckt den Katalogtext.`);
		assert.equal(treffer(wrapper, /<button\b[^>]*aria-label="Zurück: Trips"/g).length, 0, '#2837 S2 AC-10 FAIL: Desktop trägt noch den Zurück-Knopf.');
	});
});
