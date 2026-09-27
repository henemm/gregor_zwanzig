// TDD RED — Issue #2277 Scheibe S2b: BackLink/PageHeader bekommen ein optionales
// `onclick`, das die Href-Navigation durch einen Button-Callback ersetzt.
//
// Spec: docs/specs/modules/fix_2277_s2b_mobile_rahmen_angleichung.md (AC-1, AC-2)
//
// Echtes SSR-Rendering (svelte/server) der beiden Atome direkt. SSR serialisiert
// `onclick={fn}` nicht — der Test beweist die STRUKTUR: mit `onclick` gibt es
// keinen `href`-Navigationspfad mehr, ohne `onclick` bleibt `<a href>` bitgleich
// (Compare-Regressionsschutz). Ob der Callback beim Klick feuert, prüft die
// Live-E2E-Schicht (issue-661-trip-new-mobile.spec.ts, AC-5).
//
// RED HEUTE: BackLink kennt kein `onclick`, rendert immer `<a href>`; PageHeader
// reicht `back.onclick` nicht durch.
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei auflösen.
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/atoms/__tests__/back_link_page_header_onclick_button.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> atoms -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');

register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const BackLink = (await import(pathToFileURL(path.join(HERE, '..', 'BackLink.svelte')).href)).default;
const PageHeader = (await import(pathToFileURL(path.join(HERE, '..', 'PageHeader.svelte')).href))
	.default;

function html(component: unknown, props: Record<string, unknown>): string {
	return render(component as never, { props }).body.replace(/<!--[\s\S]*?-->/g, '');
}

/** Alle öffnenden Tags mit data-testid="back-link". */
function backLinkTags(markup: string): string[] {
	return [...markup.matchAll(/<([a-zA-Z]+)\b[^>]*data-testid="back-link"[^>]*>/g)].map((m) => m[0]);
}

function einzigerBackLinkTag(markup: string): string {
	const tags = backLinkTags(markup);
	assert.equal(tags.length, 1, `Erwartet genau EIN back-link-Element, gefunden: ${tags.length}`);
	return tags[0];
}

function assertButtonOhneHref(tag: string, kontext: string): void {
	assert.match(
		tag,
		/^<button\b/,
		`${kontext}: mit gesetztem onclick muss ein <button> gerendert werden, gefunden: ${tag}`
	);
	assert.match(tag, /\btype="button"/, `${kontext}: <button> ohne type="button": ${tag}`);
	assert.ok(
		!/\bhref=/.test(tag),
		`${kontext}: mit gesetztem onclick darf KEIN href-Navigationspfad existieren: ${tag}`
	);
}

function assertAnchorMitHref(tag: string, href: string, kontext: string): void {
	assert.match(tag, /^<a\b/, `${kontext}: ohne onclick muss weiterhin <a> gerendert werden: ${tag}`);
	assert.match(
		tag,
		new RegExp(`\\bhref="${href.replace(/\//g, '\\/')}"`),
		`${kontext}: <a> trägt nicht href="${href}": ${tag}`
	);
}

describe('AC-1: BackLink — onclick schaltet auf <button> ohne href', () => {
	test('mit onclick: <button type="button" data-testid="back-link"> ohne href', () => {
		const tag = einzigerBackLinkTag(
			html(BackLink, { href: '/trips', label: 'Trips', onclick: () => {} })
		);
		assertButtonOhneHref(tag, 'AC-1 BackLink');
	});

	test('mit onclick: identisches Innenleben (Label + Default-aria-label)', () => {
		const markup = html(BackLink, { href: '/trips', label: 'Trips', onclick: () => {} });
		const tag = einzigerBackLinkTag(markup);
		assert.match(tag, /aria-label="Zurück: Trips"/, `AC-1: Default-aria-label fehlt: ${tag}`);
		assert.ok(markup.includes('Trips'), 'AC-1: Label „Trips" fehlt im Button');
		assert.ok(markup.includes('<svg'), 'AC-1: Chevron-SVG fehlt im Button');
	});

	test('ohne onclick: unverändert <a href="/trips" data-testid="back-link">', () => {
		const tag = einzigerBackLinkTag(html(BackLink, { href: '/trips', label: 'Trips' }));
		assertAnchorMitHref(tag, '/trips', 'AC-1 BackLink (Regression)');
	});
});

describe('AC-2: PageHeader — back.onclick wird an BackLink durchgereicht', () => {
	test('back={{href:"/x",label:"X",onclick}} → <button> ohne href', () => {
		const tag = einzigerBackLinkTag(
			html(PageHeader, { back: { href: '/x', label: 'X', onclick: () => {} } })
		);
		assertButtonOhneHref(tag, 'AC-2 PageHeader');
	});

	test('Compare-Mount-Wortlaut back={{href:"/compare",label:"Vergleiche"}} → unverändert <a href="/compare">', () => {
		const tag = einzigerBackLinkTag(
			html(PageHeader, { back: { href: '/compare', label: 'Vergleiche' } })
		);
		assertAnchorMitHref(tag, '/compare', 'AC-2 PageHeader (Compare-Regression)');
	});
});
