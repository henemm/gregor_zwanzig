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
// Ausführen:
//   cd frontend && npm test -- src/lib/components/trip-new/__tests__/trip_new_mobile_rahmen_angleichung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { renderTripNew, countTestid, outerHtml } from './tripNewSsr.ts';

const DESKTOP = { activeTab: 'route', isMobileViewport: false };
const MOBIL = { activeTab: 'route', isMobileViewport: true };

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

describe('AC-3: Zurück in /trips/new über PageHeader/BackLink im Button-Modus', () => {
	test('Desktop: tn-desktop-breadcrumb enthält GENAU EINEN <button data-testid="back-link"> ohne href, kein <a>', () => {
		const wrapper = outerHtml(renderTripNew(DESKTOP), 'tn-desktop-breadcrumb');
		const buttons = treffer(wrapper, BUTTON_BACKLINK);
		assert.equal(
			buttons.length,
			1,
			`AC-3 FAIL: erwartet genau 1 <button data-testid="back-link"> im Desktop-Breadcrumb, gefunden ${buttons.length}.`
		);
		assert.ok(!/\bhref=/.test(buttons[0]), `AC-3 FAIL: Zurück-Button trägt href: ${buttons[0]}`);
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
	});
});

describe('AC-4: Speichern wandert in je einen EditorStickyFooter (context="route", navClearance={false})', () => {
	test('Zählungen: trip-new-save-btn = 1, tn-mobile-appbar = 1 (Desktop), tn-mobile-save = 1 (Mobil)', () => {
		const d = renderTripNew(DESKTOP);
		assert.equal(countTestid(d, 'trip-new-save-btn'), 1, 'AC-4 FAIL: trip-new-save-btn nicht genau 1×.');
		assert.equal(countTestid(d, 'tn-mobile-appbar'), 1, 'AC-4 FAIL: Wrapper tn-mobile-appbar nicht genau 1×.');
		const m = renderTripNew(MOBIL);
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
		const html = renderTripNew(MOBIL);
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

	test('zwei getrennte Footer-Mounts (einer je Viewport-Zweig)', () => {
		const html = renderTripNew(DESKTOP);
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
			const tag = tagMitTestid(renderTripNew(DESKTOP), testid);
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
	for (const [name, kombi] of [
		['Desktop', DESKTOP],
		['Mobil', MOBIL]
	] as const) {
		for (const testid of TESTIDS) {
			test(`${name}: ${testid} genau 1× (nie 0, nie 2)`, () => {
				assert.equal(
					countTestid(renderTripNew(kombi), testid),
					1,
					`AC-9 FAIL: ${testid} erscheint im ${name}-Render nicht genau einmal.`
				);
			});
		}
	}
});

describe('AC-10: Vorlesetext „Zurück: Trips" am Zurück-Pfeil in beiden Viewport-Zweigen', () => {
	test('Mobil: tn-mobile-appbar enthält aria-label="Zurück: Trips" genau einmal', () => {
		const wrapper = outerHtml(renderTripNew(MOBIL), 'tn-mobile-appbar');
		assert.equal(
			treffer(wrapper, /aria-label="Zurück: Trips"/g).length,
			1,
			'AC-10 FAIL: der Zurück-Pfeil der App-Leiste trägt nicht genau einmal aria-label="Zurück: Trips".'
		);
	});

	test('Desktop: tn-desktop-breadcrumb enthält aria-label="Zurück: Trips" genau einmal', () => {
		const wrapper = outerHtml(renderTripNew(DESKTOP), 'tn-desktop-breadcrumb');
		assert.equal(
			treffer(wrapper, /aria-label="Zurück: Trips"/g).length,
			1,
			'AC-10 FAIL: der Zurück-Link des Desktop-Breadcrumbs trägt nicht genau einmal aria-label="Zurück: Trips".'
		);
	});
});
