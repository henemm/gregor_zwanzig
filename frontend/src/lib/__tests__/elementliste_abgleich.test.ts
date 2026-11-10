// doc-compliance-test
// TDD RED — Issue #2913 (Epic #2791): Staging-Abgleich der Elementliste.
// Spec: docs/specs/modules/einstellungen_neu_neustart_adr_waechter_elementliste.md — AC-13 bis AC-15.
//
// Der eigentliche Abgleich läuft nur gegen Staging (e2e/elementliste-abgleich.staging.spec.ts mit
// playwright.elementliste.staging.config.ts, nicht im PR-CI) — dessen Live-Lauf ist Teil von
// /60-validate bzw. /e2e-verify. Hier, ohne Browser und im CI-Job `frontend-test`, wird die
// Bewertungslogik (Bericht, Scope, Exit-Code) und die Absicherung gegen Produktion geprüft.
// Dateiinhalt-Checks nur für Konfigurationsmerkmale (Prod-Schutz, nicht im PR-CI).
//
// Vertrag des Logik-Moduls `e2e/elementliste_abgleich_logik.ts` (vom Developer umzusetzen):
//   type Status = 'gefunden' | 'abweichend' | 'nicht_pruefbar'
//   type Ergebnis = { status: Status; grund?: string; ist?: string }
//   filtereScope(elemente, scope: string | null): Element[]     — scope 'reiter' oder 'reiter/zustand'
//   baueBericht(elemente, ergebnisse: Map<string, Ergebnis>): Bericht
//        Bericht = { eintraege: Array<{ id; status; grund? ; ... }>; zaehler: Record<Status, number> }
//        Element ohne Ergebnis ⇒ 'nicht_pruefbar' mit Grund (nie still übersprungen)
//   exitCode(bericht, { strict: boolean }): number
//   berichtAlsMarkdown(bericht): string
//   leseOptionen(argv: string[], env: Record<string,string|undefined>): { strict: boolean; scope: string | null }
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/__tests__/elementliste_abgleich.test.ts
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
	filtereScope,
	baueBericht,
	exitCode,
	berichtAlsMarkdown,
	leseOptionen
} from '../../../e2e/elementliste_abgleich_logik.ts';
import { assertNotProdBaseURL } from '../../../e2e/prodUrlGuard.ts';

const FRONTEND = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..', '..');
const REPO = join(FRONTEND, '..');

const el = (id: string, reiter: string, zustand: string, text_de: string) => ({
	id,
	ctx: 'trip',
	reiter,
	zustand,
	segment: null,
	abschnitt: 'kopf',
	ordnung: Number(id.replace(/\D/g, '')) || 0,
	rolle: 'text',
	text_de,
	muster: null,
	i18n_key: null,
	text_en: null,
	luecke: true
});
const ELEMENTE = [
	el('e1', 'wetter', 'normal', 'Wetter'),
	el('e2', 'wetter', 'fehler', 'Die Metriken konnten nicht geladen werden.'),
	el('e3', 'zustellung', 'normal', 'Zustellung'),
	el('e4', 'zustellung', 'laedt', 'Lade Metriken …')
];

// ---------------------------------------------------------------- AC-13
describe('AC-13: Bericht enthält jedes Element mit Status; nichts wird still übersprungen', () => {
	test('jedes Listenelement erscheint genau einmal im Bericht', () => {
		const erg = new Map([
			['e1', { status: 'gefunden' as const }],
			['e2', { status: 'abweichend' as const, ist: 'Fehler' }],
			['e3', { status: 'nicht_pruefbar' as const, grund: 'Zustand per Route-Abfangen nicht herstellbar' }]
		]);
		const b = baueBericht(ELEMENTE, erg);
		assert.deepEqual(
			b.eintraege.map((e: { id: string }) => e.id).sort(),
			['e1', 'e2', 'e3', 'e4']
		);
		const e4 = b.eintraege.find((e: { id: string }) => e.id === 'e4');
		assert.equal(e4!.status, 'nicht_pruefbar', 'Element ohne Ergebnis darf nicht fehlen oder als gefunden gelten');
		assert.ok(e4!.grund && e4!.grund.length > 0, 'nicht_pruefbar braucht einen Grund');
		assert.deepEqual(b.zaehler, { gefunden: 1, abweichend: 1, nicht_pruefbar: 2 });
	});

	test('nicht_pruefbar ohne Grund wird abgelehnt', () => {
		assert.throws(() => baueBericht(ELEMENTE, new Map([['e1', { status: 'nicht_pruefbar' as const }]])));
	});

	test('Markdown-Bericht nennt jedes Element und die Zähler', () => {
		const md = berichtAlsMarkdown(baueBericht(ELEMENTE, new Map([['e1', { status: 'gefunden' as const }]])));
		for (const id of ['e1', 'e2', 'e3', 'e4']) assert.ok(md.includes(id), `${id} fehlt im Markdown`);
		assert.match(md, /gefunden/);
		assert.match(md, /nicht_pruefbar/);
	});

	test('Staging-Spec stellt nicht herstellbare Zustände per Route-Abfangen her', () => {
		const spec = readFileSync(join(FRONTEND, 'e2e/elementliste-abgleich.staging.spec.ts'), 'utf8');
		assert.match(spec, /page\.route\(/, 'Ladefehler/Lädt müssen per page.route hergestellt werden');
		assert.match(spec, /elementliste\.json/);
	});
});

// ---------------------------------------------------------------- AC-14
describe('AC-14: --strict und --scope', () => {
	const sauber = baueBericht.bind(null);
	test('ohne --strict immer Exit 0, auch bei Abweichungen', () => {
		const b = sauber(ELEMENTE, new Map([['e1', { status: 'abweichend' as const, ist: 'x' }]]));
		assert.equal(exitCode(b, { strict: false }), 0);
	});
	test('--strict: Abweichung oder nicht_pruefbar ⇒ Exit ≠ 0', () => {
		const ab = sauber(ELEMENTE.slice(0, 1), new Map([['e1', { status: 'abweichend' as const, ist: 'x' }]]));
		assert.notEqual(exitCode(ab, { strict: true }), 0);
		const np = sauber(ELEMENTE.slice(0, 1), new Map([['e1', { status: 'nicht_pruefbar' as const, grund: 'g' }]]));
		assert.notEqual(exitCode(np, { strict: true }), 0);
	});
	test('--strict: alles gefunden ⇒ Exit 0', () => {
		const ok = sauber(ELEMENTE.slice(0, 1), new Map([['e1', { status: 'gefunden' as const }]]));
		assert.equal(exitCode(ok, { strict: true }), 0);
	});
	test('--scope reiter bzw. reiter/zustand filtert die Elemente', () => {
		assert.deepEqual(filtereScope(ELEMENTE, 'wetter').map((e: { id: string }) => e.id), ['e1', 'e2']);
		assert.deepEqual(filtereScope(ELEMENTE, 'zustellung/laedt').map((e: { id: string }) => e.id), ['e4']);
		assert.equal(filtereScope(ELEMENTE, null).length, 4);
	});
	test('unbekannter Scope ist ein Fehler, kein leerer grüner Lauf', () => {
		assert.throws(() => filtereScope(ELEMENTE, 'gibtsnicht'));
	});
	test('Optionen aus Argumenten oder Umgebung', () => {
		assert.deepEqual(leseOptionen(['--strict', '--scope', 'wetter/normal'], {}), { strict: true, scope: 'wetter/normal' });
		assert.deepEqual(leseOptionen([], { ELEMENTLISTE_STRICT: '1', ELEMENTLISTE_SCOPE: 'zustellung' }), {
			strict: true,
			scope: 'zustellung'
		});
		assert.deepEqual(leseOptionen([], {}), { strict: false, scope: null });
	});
});

// ---------------------------------------------------------------- AC-15
describe('AC-15: Schutz vor Produktion, nicht im PR-CI', () => {
	test('assertNotProdBaseURL wirft bei Prod, läuft bei Staging', () => {
		assert.throws(() => assertNotProdBaseURL('https://gregor20.henemm.com'));
		assert.doesNotThrow(() => assertNotProdBaseURL('https://staging.gregor20.henemm.com'));
	});
	test('Config zielt standardmäßig auf Staging; Spec ruft den Prod-Schutz vor dem ersten Seitenaufruf', () => {
		const cfg = readFileSync(join(FRONTEND, 'playwright.elementliste.staging.config.ts'), 'utf8');
		assert.match(cfg, /https:\/\/staging\.gregor20\.henemm\.com/);
		assert.match(cfg, /elementliste-abgleich\\?\.staging\\?\.spec/);
		const spec = readFileSync(join(FRONTEND, 'e2e/elementliste-abgleich.staging.spec.ts'), 'utf8');
		const schutz = spec.indexOf('assertNotProdBaseURL(');
		const goto = spec.indexOf('.goto(');
		assert.ok(schutz >= 0, 'assertNotProdBaseURL fehlt');
		assert.ok(goto < 0 || schutz < goto, 'Prod-Schutz muss vor dem ersten goto stehen');
	});
	test('kein CI-Workflow ruft die Abgleich-Config oder -Spec auf', () => {
		const wf = join(REPO, '.github/workflows');
		for (const f of readdirSync(wf)) {
			const t = readFileSync(join(wf, f), 'utf8');
			assert.ok(!t.includes('playwright.elementliste.staging'), `${f} ruft den Staging-Abgleich auf`);
			assert.ok(!t.includes('elementliste-abgleich'), `${f} nennt die Abgleich-Spec`);
		}
	});
});
