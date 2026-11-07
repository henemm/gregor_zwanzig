// TDD RED — Issue #2837 Scheibe S1 (Epic #2345), Entscheidung 6 / AC-7: der mobile
// Weitere-Aktionen-Knopf (bisher je Seite selbst gebaut: Trip `EllipsisVertical`,
// Vergleich `MoreHorizontal`) wird in `SubscriptionKebab` gehoben. Mobil öffnet er das
// Aktionsblatt der Seite (`onSheetOpen`), Desktop bleibt das Dropdown — Symbol in
// beiden Fällen VERTIKAL, Tippfläche mobil 44×44.
// Spec: docs/specs/modules/rework_2837_s1_hub_kopf.md
//
// Vertrag (von RED festgelegt, Spec nennt nur „Kebab-Daten"): neue Props
// `mobil?: boolean` und `onSheetOpen?: () => void`; ohne `mobil` unverändert.
//
// Echte Komponente, serverseitig gerendert (svelte/server; der bits-ui-Trigger rendert
// unter SSR, der Menüinhalt nicht). Lage im echten Browser: E2E
// hub-kopf-paritaet-compare-trip.spec.ts (390 px, beide Arten).
//
// RED HEUTE: `mobil` wird ignoriert — es rendert immer der 28-px-Dropdown-Trigger.
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/molecules/__tests__/subscription_kebab_mobil_vertikal.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { baum, alle, mitTestid } from '../../shared/hub-kopf/__tests__/htmlBaum.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> molecules -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const { render } = await import('svelte/server');
const { locale, trFor } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);
const Kebab = (await import(pathToFileURL(path.join(HERE, '..', 'SubscriptionKebab.svelte')).href)).default;

afterEach(() => locale.set('de'));

function html(props: Record<string, unknown>): string {
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	return render(Kebab as any, {
		props: { actions: [{ id: 'pause', label: 'Pausieren' }], onSelect: () => {}, 'data-testid': 'subscription-kebab', ...props }
	}).body;
}

const knopf = (h: string) => {
	const t = mitTestid(baum(h), 'subscription-kebab');
	assert.equal(t.length, 1, `subscription-kebab ${t.length}× gerendert (erwartet genau 1)`);
	return t[0];
};
const symbole = (h: string) => alle(knopf(h), (n) => n.tag === 'svg').map((n) => n.attrs.class ?? '');

describe('#2837 S1 Entscheidung 6 — SubscriptionKebab mobil: eigener 44-px-Knopf, vertikal, öffnet das Blatt', () => {
	test('mobil: genau ein Knopf mit vertikalem Symbol, KEIN Dropdown-Trigger', () => {
		const h = html({ mobil: true, onSheetOpen: () => {} });
		const k = knopf(h);
		assert.equal(k.tag, 'button');
		assert.ok(!('data-dropdown-menu-trigger' in k.attrs), 'mobil rendert noch den Dropdown-Trigger (statt das Blatt zu öffnen)');
		assert.ok(symbole(h).some((c) => /\blucide-ellipsis-vertical\b/.test(c)), `Symbol: ${symbole(h).join(' | ')}`);
		assert.ok(!/lucide-ellipsis(?!-vertical)|lucide-more-horizontal/.test(h), 'horizontales Symbol im mobilen Kebab');
	});

	test('mobil: Tippfläche 44×44 (Inline-Maß oder min-Klassen)', () => {
		const k = knopf(html({ mobil: true, onSheetOpen: () => {} }));
		const stil = (k.attrs.style ?? '').replace(/\s+/g, '');
		const klasse = k.attrs.class ?? '';
		const breit = /(^|;)(min-)?width:44px/.test(stil) || /\bmin-w-\[44px\]/.test(klasse);
		const hoch = /(^|;)(min-)?height:44px/.test(stil) || /\bmin-h-\[44px\]/.test(klasse);
		assert.ok(breit && hoch, `mobiler Kebab ohne 44×44-Tippfläche: style="${k.attrs.style}" class="${klasse}"`);
	});

	test('Desktop (ohne mobil): Dropdown-Trigger mit vertikalem Symbol bleibt', () => {
		const h = html({});
		assert.ok('data-dropdown-menu-trigger' in knopf(h).attrs, 'Desktop rendert keinen Dropdown-Trigger');
		assert.ok(symbole(h).some((c) => /\blucide-ellipsis-vertical\b/.test(c)));
	});

	test('AC-13: Aria-Text aus dem Katalog in beiden Breiten und Sprachen', () => {
		for (const lang of ['de', 'en'] as const) {
			locale.set(lang);
			for (const mobil of [false, true])
				assert.equal(knopf(html({ mobil, onSheetOpen: () => {} })).attrs['aria-label'], trFor(lang, 'aktionen.weitere'), `${lang}, mobil=${mobil}`);
		}
	});
});
