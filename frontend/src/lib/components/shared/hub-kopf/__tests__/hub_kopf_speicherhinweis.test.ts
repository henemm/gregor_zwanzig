// TDD RED — Issue #2954: Speicherhinweis wandert aus dem festen Overlay unten rechts in die
// Kopfleiste, links vor das Drei-Punkte-Menü und den Hauptknopf (Mockup Fassung 3, ADR-0120).
// Spec: docs/specs/modules/fix_2954_speicherhinweis_kopfleiste.md — AC-2, AC-4, AC-6, AC-8
// (Baustein-Anteil; Lage im Browser, 5-s-Timer und Verdeckung prüft die E2E
// frontend/e2e/fix-2954-speicherhinweis-kopfleiste.spec.ts).
//
// Echte Komponente HubKopf mit ECHTER SaveStatus-Instanz, serverseitig gerendert
// (svelte/server) — kein Mock. Lage-Zusicherungen über den Element-Baum (htmlBaum.ts).
//
// RED HEUTE: der Hinweis wird von SubscriptionHeader UNTER dem Titelblock gerendert
// (nicht in der Leiste), trägt kein aria-live und zeigt beim Öffnen ohne Speichern
// „Gespeichert".
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/shared/hub-kopf/__tests__/hub_kopf_speicherhinweis.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { baum, alle, einzig, mitTestid, text, liegtIn, klassen, type Knoten } from './htmlBaum.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../../..');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const { render } = await import('svelte/server');
const { locale, trFor } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);
const { createSaveStatus } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/stores/saveStatusStore.svelte.ts')).href);

const PRUEFLING = path.join(HERE, '..', 'HubKopf.svelte');
const HubKopf = (await import(pathToFileURL(PRUEFLING).href)).default;

afterEach(() => locale.set('de'));

type Ctx = 'route' | 'vergleich';
type Modus = 'senden' | 'setup';
type Zustand = { state: string; savedAt?: Date | null; error?: string | null };

function controller(z: Zustand): unknown {
	const c = createSaveStatus();
	c.state = z.state;
	c.savedAt = z.savedAt ?? null;
	c.error = z.error ?? null;
	return c;
}

function props(context: Ctx, sendMode: Modus, saveController: unknown): Record<string, unknown> {
	return {
		context,
		parent:
			context === 'route'
				? { label: trFor('de', 'listen.trips.titel'), href: '/trips' }
				: { label: trFor('de', 'listen.vergleiche.titel'), href: '/compare' },
		crumb: context === 'route' ? 'GR20' : 'Dolomiten Süd',
		sendLabel: sendMode === 'setup' ? 'Setup abschließen' : 'Test schicken',
		onSend: () => {},
		sendMode,
		onSetup: () => {},
		actions: [{ id: 'pause', label: 'Pausieren' }],
		onSelect: () => {},
		name: context === 'route' ? 'GR20 Nord' : 'Dolomiten Süd',
		region: 'Korsika',
		profile: 'trekking',
		profileOptions: [{ value: 'trekking', label: 'Trekking' }],
		profileLabel: 'Trekking',
		testidPrefix: 'kopf',
		onSaveField: async () => {},
		...(saveController ? { saveController } : {})
	};
}

function rendere(context: Ctx, sendMode: Modus, z: Zustand | null): Knoten {
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	const html = render(HubKopf as any, { props: props(context, sendMode, z ? controller(z) : undefined) }).body;
	return baum(html.replace(/<!--[\s\S]*?-->/g, ''));
}

/** Hauptknopf der Leiste: „Test schicken" (subscription-hub-send) bzw. „Setup abschließen". */
function hauptknopf(w: Knoten, sendMode: Modus): Knoten {
	const leiste = einzig(w, 'hub-kopf-leiste');
	if (sendMode === 'senden') return einzig(w, 'subscription-hub-send');
	const k = alle(leiste, (n) => (n.tag === 'button' || n.tag === 'a') && text(n).includes('Setup abschließen'));
	assert.equal(k.length, 1, `genau ein „Setup abschließen" in der Leiste erwartet, gefunden ${k.length}`);
	return k[0];
}

const FAELLE: Array<{ context: Ctx; sendMode: Modus; name: string }> = [
	{ context: 'route', sendMode: 'senden', name: 'Trip' },
	{ context: 'vergleich', sendMode: 'senden', name: 'Orte' },
	{ context: 'vergleich', sendMode: 'setup', name: 'Vergleich-Entwurf' }
];

for (const f of FAELLE) {
	describe(`#2954 AC-2 (${f.name}): Hinweis in der Kopfleiste vor Kebab und Hauptknopf`, () => {
		test(`${f.name}: genau ein save-indicator im ganzen Kopf`, () => {
			const w = rendere(f.context, f.sendMode, { state: 'idle', savedAt: new Date() });
			assert.equal(mitTestid(w, 'save-indicator').length, 1);
		});

		test(`${f.name}: Hinweis liegt IN der Leiste, in der Aktionsgruppe, nicht im Titelblock`, () => {
			const w = rendere(f.context, f.sendMode, { state: 'idle', savedAt: new Date() });
			const hinweis = einzig(w, 'save-indicator');
			const leiste = einzig(w, 'hub-kopf-leiste');
			assert.ok(liegtIn(hinweis, leiste), 'der Speicherhinweis steht nicht in der Kopfleiste');
			const aktionen = alle(leiste, (n) => klassen(n).includes('hub-actions'));
			assert.equal(aktionen.length, 1, 'genau eine Aktionsgruppe .hub-actions erwartet');
			assert.ok(liegtIn(hinweis, aktionen[0]), 'der Speicherhinweis steht nicht in der Aktionsgruppe');
			const titel = alle(w, (n) => klassen(n).includes('hub-kopf-titel'));
			assert.ok(titel.length === 1 && !liegtIn(hinweis, titel[0]), 'der Speicherhinweis steht im Titelblock');
		});

		test(`${f.name}: Reihenfolge Hinweis → Drei-Punkte-Menü → Hauptknopf`, () => {
			const w = rendere(f.context, f.sendMode, { state: 'idle', savedAt: new Date() });
			const hinweis = einzig(w, 'save-indicator');
			const kebab = einzig(w, 'subscription-kebab');
			const knopf = hauptknopf(w, f.sendMode);
			assert.ok(hinweis.nr < kebab.nr, 'der Hinweis muss VOR dem Drei-Punkte-Menü stehen');
			assert.ok(kebab.nr < knopf.nr, 'Drei-Punkte-Menü muss vor dem Hauptknopf stehen (Mockup-Reihenfolge)');
		});

		test(`${f.name}: ohne saveController kein Hinweis`, () => {
			const w = rendere(f.context, f.sendMode, null);
			assert.equal(mitTestid(w, 'save-indicator').length, 0);
		});
	});
}

describe('#2954 AC-8: stabile, höflich angesagte Region mit Zustand', () => {
	for (const state of ['idle', 'dirty', 'saving', 'conflict', 'error']) {
		test(`${state}: aria-live="polite", data-state="${state}", Region im DOM`, () => {
			const w = rendere('route', 'senden', { state });
			const hinweis = einzig(w, 'save-indicator');
			assert.equal(hinweis.attrs['aria-live'], 'polite', 'aria-live="polite" fehlt am Speicherhinweis');
			assert.equal(hinweis.attrs['data-state'], state);
		});
	}
});

describe('#2954 AC-4: beim Öffnen ohne Speichern steht kein Text', () => {
	for (const f of FAELLE) {
		test(`${f.name}: idle ohne savedAt ⇒ Region leer, aber im DOM`, () => {
			const w = rendere(f.context, f.sendMode, { state: 'idle', savedAt: null });
			const hinweis = einzig(w, 'save-indicator');
			assert.equal(text(hinweis).trim(), '', `beim Öffnen steht „${text(hinweis).trim()}" im Hinweis (erwartet leer)`);
		});
	}

	test('idle MIT savedAt (gerade gespeichert) ⇒ „Gespeichert" (Gegenprobe)', () => {
		const w = rendere('route', 'senden', { state: 'idle', savedAt: new Date() });
		assert.ok(text(einzig(w, 'save-indicator')).includes('Gespeichert'));
	});
});

describe('#2954 AC-5/AC-6: Zwischenzustände und Fehler im Hinweis', () => {
	test('dirty ⇒ „nicht gespeichert", saving ⇒ „Speichere …"', () => {
		assert.match(text(einzig(rendere('route', 'senden', { state: 'dirty' }), 'save-indicator')), /nicht gespeichert/i);
		assert.match(text(einzig(rendere('route', 'senden', { state: 'saving' }), 'save-indicator')), /Speichere/);
	});

	test('error ⇒ Fehlertext; conflict ⇒ Text und Knopf „Nochmal speichern"', () => {
		const fehler = einzig(rendere('vergleich', 'senden', { state: 'error' }), 'save-indicator');
		assert.ok(text(fehler).trim().length > 0, 'Fehlerzustand ohne Text');
		const konflikt = einzig(rendere('vergleich', 'senden', { state: 'conflict' }), 'save-indicator');
		const knoepfe = alle(konflikt, (n) => n.tag === 'button');
		assert.equal(knoepfe.length, 1, 'Konflikt ohne Knopf „Nochmal speichern"');
		assert.equal(text(knoepfe[0]).trim(), trFor('de', 'nav.nochmal_speichern'));
	});
});
