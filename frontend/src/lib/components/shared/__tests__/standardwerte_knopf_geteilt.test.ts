// TDD RED — Onboarding S3 (Issue #2521), AC-12 + AC-13 (+ AC-5 an der Oberflaeche):
// EIN geteilter Baustein `StandardwerteSpeichernKnopf` in beiden Anlege-Editoren,
// mit identischer Beschriftung und Sperrverhalten; erreichbar am Desktop und in
// der unteren Leiste mobil — im Ortsvergleich auf JEDEM Reiter, nicht nur Versand.
// Spec: docs/specs/modules/onboarding_standardwerte_hilfe.md
//
// Messwege (kein Quelltext-Grep):
//   - echte SSR-Renderings (svelte/server) des Bausteins und beider Editoren
//     (Pruefstand infoboxSsr.ts: echter CompareWizardState, Name + 2 Orte);
//   - AST der Editoren (`findeKomponenten`), um „derselbe Baustein, aus shared/"
//     festzuhalten (Pendant-Sperre).
//
// Vertraege (Test-Kennungen), die dieser Test festlegt:
//   Trip    Desktop  data-testid="trip-new-standardwerte-btn"  im Footer tn-desktop-footer
//   Trip    mobil    data-testid="tn-mobile-standardwerte"     im Footer tn-mobile-footer
//   Vergl.  Desktop  data-testid="compare-editor-standardwerte" (Kopfzeile)
//   Vergl.  mobil    data-testid="cm-mobile-standardwerte"     im Footer cm-mobile-cta
//   Baustein-Props: enabled, saving, onclick, testid (Spec); Beschriftung aus
//   de.json-Schluessel `standardwerte.knopf`.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/standardwerte_knopf_geteilt.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { parse } from 'svelte/compiler';
import { de } from '../../../i18n/messages/de/index.ts';
import {
	lade,
	renderKomponente,
	renderTrip,
	renderVergleichNeu,
	innen,
	sichtbarerText
} from './infoboxSsr.ts';
import { findeKomponenten } from './svelteInstanzPruefstand.ts';
import {
	TRIP_EDITOR,
	COMPARE_EDITOR,
	KNOPF_DATEI,
	KNOPF_NAME,
	importQuelle,
	importPfad
} from './standardwerteEditorPruefstand.ts';

const katalog = de as Record<string, string>;
const LABEL_KEY = 'standardwerte.knopf';

function knopfTag(html: string, testid: string): string | null {
	const m = new RegExp(`<button\\b[^>]*data-testid="${testid}"[^>]*>`).exec(html);
	return m ? m[0] : null;
}
const istDisabled = (tag: string) => /\sdisabled(=|\s|>)/.test(tag);

async function knopfBaustein(): Promise<unknown> {
	assert.ok(existsSync(KNOPF_DATEI), 'shared/StandardwerteSpeichernKnopf.svelte existiert nicht (Spec: EIN geteilter Knopf)');
	return lade('shared/StandardwerteSpeichernKnopf.svelte');
}

describe('AC-13: der Baustein StandardwerteSpeichernKnopf', () => {
	test('Beschriftung kommt aus dem Textkatalog (standardwerte.knopf) und ist nicht leer', async () => {
		assert.ok(katalog[LABEL_KEY]?.trim(), `de.json: Schluessel ${LABEL_KEY} fehlt`);
		const html = renderKomponente(await knopfBaustein(), { enabled: true, saving: false, onclick: () => {}, testid: 'x-std' });
		assert.ok(sichtbarerText(html).includes(katalog[LABEL_KEY]), `Beschriftung nicht aus dem Katalog: ${sichtbarerText(html)}`);
	});
	test('enabled=true: Knopf mit testid, nicht gesperrt', async () => {
		const html = renderKomponente(await knopfBaustein(), { enabled: true, saving: false, onclick: () => {}, testid: 'x-std' });
		const tag = knopfTag(html, 'x-std');
		assert.ok(tag, 'kein <button data-testid="x-std">');
		assert.equal(istDisabled(tag!), false);
	});
	test('enabled=false: gesperrt', async () => {
		const tag = knopfTag(renderKomponente(await knopfBaustein(), { enabled: false, saving: false, onclick: () => {}, testid: 'x-std' }), 'x-std');
		assert.ok(tag && istDisabled(tag));
	});
	test('saving=true: gesperrt (kein Doppelklick waehrend des Speicherns)', async () => {
		const tag = knopfTag(renderKomponente(await knopfBaustein(), { enabled: true, saving: true, onclick: () => {}, testid: 'x-std' }), 'x-std');
		assert.ok(tag && istDisabled(tag));
	});
});

describe('AC-13: beide Editoren binden DENSELBEN Baustein ein (keine compare-eigene Kopie)', () => {
	for (const [name, datei] of [['TripNewEditor', TRIP_EDITOR], ['CompareNewEditor', COMPARE_EDITOR]] as const) {
		test(`${name}: <${KNOPF_NAME}> mindestens zweimal (Desktop + mobil), importiert aus shared/`, () => {
			const ast = parse(readFileSync(datei, 'utf-8'), { modern: true });
			const n = findeKomponenten(ast, KNOPF_NAME).length;
			assert.ok(n >= 2, `${name}: ${n} Einbettung(en) von <${KNOPF_NAME}>`);
			const q = importQuelle(ast, KNOPF_NAME);
			assert.ok(q, `${name}: kein Import fuer ${KNOPF_NAME}`);
			assert.equal(importPfad(datei, q!), KNOPF_DATEI, `${name}: ${KNOPF_NAME} kommt nicht aus shared/`);
		});
	}
});

describe('AC-12/AC-5: Platzierung Trip (/trips/new)', () => {
	const basis = { name: 'Trip X', startDate: '2026-07-01' };
	test('Desktop: Knopf im Footer neben „Trip speichern", solange der Bestandsknopf gesperrt ist', async () => {
		const html = await renderTrip({ ...basis, isMobileViewport: false });
		const footer = innen(html, 'tn-desktop-footer');
		assert.ok(knopfTag(footer, 'trip-new-standardwerte-btn'), 'trip-new-standardwerte-btn fehlt im Desktop-Footer');
		assert.ok(footer.includes('data-testid="trip-new-save-btn"'), 'Bestandsknopf fehlt (Messaufbau)');
	});
	test('mobil (375 px): Knopf in der unteren Leiste', async () => {
		const html = await renderTrip({ ...basis, isMobileViewport: true });
		assert.ok(innen(html, 'tn-mobile-footer').includes('data-testid="tn-mobile-standardwerte"'), 'tn-mobile-standardwerte fehlt im mobilen Footer');
	});
	test('AC-5: alle Reiter besucht (Bestandsknopf frei) => Standardwerte-Knopf nicht mehr da', async () => {
		const alle = { wtVisited: true, wbVisited: true, alVisited: true, vsVisited: true };
		const d = await renderTrip({ ...basis, ...alle, isMobileViewport: false });
		const m = await renderTrip({ ...basis, ...alle, isMobileViewport: true });
		assert.ok(!d.includes('trip-new-standardwerte-btn') && !m.includes('tn-mobile-standardwerte'));
	});
});

describe('AC-12/AC-5: Platzierung Ortsvergleich (/compare/new)', () => {
	test('Desktop: Knopf in der Kopfzeile', async () => {
		const html = await renderVergleichNeu({ activeTab: 'vergleich', isMobileViewport: false });
		assert.ok(knopfTag(html, 'compare-editor-standardwerte'), 'compare-editor-standardwerte fehlt');
	});
	const reiterVorVersand: Array<[string, Record<string, boolean>]> = [
		['vergleich', {}],
		['orte', {}],
		['wetter-metriken', { metrikenVisited: true }],
		['wertebereiche', { metrikenVisited: true, idealsVisited: true }]
		// #1743: „Alarme" ist der letzte Schritt — mit seinem Besuch wird Aktivieren frei
		// und der Standardwerte-Knopf entfaellt (AC-5 unten, nie beide gleichzeitig).
	];
	for (const [reiter, flags] of reiterVorVersand) {
		test(`mobil, Reiter „${reiter}": Knopf in der unteren Leiste (nicht nur auf dem letzten Reiter)`, async () => {
			const html = await renderVergleichNeu({ activeTab: reiter, isMobileViewport: true, ...flags });
			assert.ok(innen(html, 'cm-mobile-cta').includes('data-testid="cm-mobile-standardwerte"'), `cm-mobile-standardwerte fehlt auf Reiter ${reiter}`);
		});
	}
	// #1743: der Reiter „versand" entfaellt — „Alarme" ist der letzte Schritt.
	test('AC-5: alle Reiter besucht (Aktivieren frei) => Standardwerte-Knopf nicht mehr da', async () => {
		const alle = { metrikenVisited: true, idealsVisited: true, alarmeVisited: true };
		const d = await renderVergleichNeu({ activeTab: 'alarme', isMobileViewport: false, ...alle });
		const m = await renderVergleichNeu({ activeTab: 'alarme', isMobileViewport: true, ...alle });
		assert.ok(!d.includes('compare-editor-standardwerte') && !m.includes('cm-mobile-standardwerte'));
	});
});

describe('AC-13: identische Beschriftung und Sperre in beiden Editoren (SSR: Katalog nie geladen)', () => {
	test('Trip und Ortsvergleich zeigen denselben Katalog-Text; beide gesperrt, solange Standardwerte nicht bereit', async () => {
		const trip = await renderTrip({ name: 'Trip X', startDate: '2026-07-01', isMobileViewport: false });
		const vergl = await renderVergleichNeu({ activeTab: 'vergleich', isMobileViewport: false });
		const t = knopfTag(trip, 'trip-new-standardwerte-btn');
		const v = knopfTag(vergl, 'compare-editor-standardwerte');
		assert.ok(t && v, 'Knopf fehlt in mindestens einem Editor');
		assert.ok(istDisabled(t!) && istDisabled(v!), 'ohne geladenen Katalog darf kein Standardwerte-Knopf aktiv sein');
		const text = (html: string, id: string) => sichtbarerText(innen(html, id));
		assert.equal(text(trip, 'trip-new-standardwerte-btn'), katalog[LABEL_KEY]);
		assert.equal(text(vergl, 'compare-editor-standardwerte'), katalog[LABEL_KEY]);
	});
});
