// Epic #1301 Scheibe F2a / #2277 S4: Freischalt-Vertrag des Compare-Anlege-Flows.
//
// Vormals compareNewLogic.test.ts (Datei gelöscht, #2277 S4). Die Schwanz-Kette
// kommt jetzt aus dem geteilten Kern shared/anlegeLockEngine.ts; das Compare-
// Vorderteil (Name, ≥2 Orte) und der Zähler-Deckel wohnen in CompareNewEditor.svelte.
// Die Hilfsfunktionen unten bilden genau diese Komposition ab (Kern + Vorderteil);
// die Wirkstelle selbst (echte Reiterleiste) prüft compare_new_lock_engine_wirkstelle.test.ts.
// Issue #1743 (AC-17/AC-19): kein Schritt „Versand".
// Issue #2794 S3a (Spec feat_2794_s3a_teil2_leiste.md AC-6): Freischalt-Kette
// Name → Orte≥2 → wetter → zustellung, mit Besuchs-Kaskade (einmal besucht bleibt besucht);
// „Briefing aktivieren" ist frei, sobald Zustellung besucht ist; Zaehler-Deckel 4. Kein Mock.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare-new/__tests__/compare_anlege_freischaltung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import {
	tailUnlocked,
	tailDone,
	canFinish,
	progressCount as kernProgressCount,
	type TailIds,
} from '../../shared/anlegeLockEngine.ts';

type CompareNewTabId = 'vergleich' | 'orte' | 'wetter' | 'zustellung';
interface CompareNewProgress {
	name: string;
	pickedCount: number;
	metrikenVisited: boolean;
	zustellungVisited: boolean;
}
const TAIL: TailIds<CompareNewTabId> = { metriken: 'wetter', zustellung: 'zustellung' };
const STEPS: CompareNewTabId[] = ['vergleich', 'orte', 'wetter', 'zustellung'];

function tailP(p: CompareNewProgress) {
	return {
		metrikenFrei: !!p.name.trim() && p.pickedCount >= 2,
		metrikenVisited: p.metrikenVisited,
		zustellungVisited: p.zustellungVisited,
	};
}
function unlockedTabs(p: CompareNewProgress): Set<CompareNewTabId> {
	const s = tailUnlocked(TAIL, tailP(p));
	s.add('vergleich');
	if (p.name.trim()) s.add('orte');
	return s;
}
function doneTabs(p: CompareNewProgress): Set<CompareNewTabId> {
	const s = tailDone(TAIL, tailP(p));
	if (p.name.trim()) s.add('vergleich');
	if (p.pickedCount >= 2) s.add('orte');
	return s;
}
function progressCount(done: Set<CompareNewTabId>): number {
	return Math.min(kernProgressCount(done, STEPS), 4);
}
const canActivate = (done: Set<CompareNewTabId>) => canFinish(done);

// ── Progress-Builder: leerer Start, gezielt Felder überschreiben ──────────────

function progress(over: Partial<CompareNewProgress> = {}): CompareNewProgress {
	return {
		name: '',
		pickedCount: 0,
		metrikenVisited: false,
		zustellungVisited: false,
		...over,
	};
}

// ── AC-2: Leerzustand — nur "vergleich" offen ────────────────────────────────

describe('AC-2: unlockedTabs — progressive Freischaltung', () => {
	test('Leerzustand: nur "vergleich" offen, 3 Tabs gesperrt', () => {
		const u = unlockedTabs(progress());
		assert.deepEqual([...u].sort(), ['vergleich']);
	});

	test('AC-3: Name gesetzt → "orte" schaltet frei, "wetter" bleibt gesperrt', () => {
		const u = unlockedTabs(progress({ name: 'Sardinien-Woche' }));
		assert.ok(u.has('orte'), 'orte muss frei sein');
		assert.ok(!u.has('wetter'), 'wetter noch gesperrt (Orte fehlen)');
	});

	test('Nur Whitespace als Name schaltet "orte" NICHT frei', () => {
		const u = unlockedTabs(progress({ name: '   ' }));
		assert.ok(!u.has('orte'), 'Whitespace-Name darf nicht freischalten');
		assert.deepEqual([...u].sort(), ['vergleich']);
	});

	test('AC-4: genau 1 Ort schaltet "wetter" NICHT frei', () => {
		const u = unlockedTabs(progress({ name: 'X', pickedCount: 1 }));
		assert.ok(!u.has('wetter'), '1 Ort reicht nicht (Minimum 2)');
	});

	test('AC-4: 2 Orte schalten "wetter" frei, "zustellung" bleibt gesperrt', () => {
		const u = unlockedTabs(progress({ name: 'X', pickedCount: 2 }));
		assert.ok(u.has('wetter'), 'wetter frei ab 2 Orten');
		assert.ok(!u.has('zustellung'), 'zustellung noch gesperrt (Wetter nicht besucht)');
	});

	test('metrikenVisited → "zustellung" frei; kein entfallener Schritt wird frei', () => {
		const u1 = unlockedTabs(progress({ name: 'X', pickedCount: 2, metrikenVisited: true })) as Set<string>;
		assert.ok(u1.has('zustellung'), 'zustellung frei nach Wetter-Besuch');
		const u2 = unlockedTabs(progress({ name: 'X', pickedCount: 2, metrikenVisited: true, zustellungVisited: true })) as Set<string>;
		for (const alt of ['versand', 'wertebereiche', 'alarme', 'wetter-metriken']) {
			assert.ok(!u2.has(alt), `es gibt keinen Schritt ${alt} mehr: ${[...u2].sort().join(',')}`);
		}
	});

	test('Kaskade übersprungen: zustellungVisited ohne Vorstufen schaltet "zustellung" NICHT frei', () => {
		const u = unlockedTabs(progress({ zustellungVisited: true }));
		assert.ok(!u.has('zustellung'), 'ohne Name/Orte/Wetter kein zustellung-Zugang');
		assert.deepEqual([...u].sort(), ['vergleich']);
	});

	test('Vollständige Kette: alle 4 Tabs offen', () => {
		const u = unlockedTabs(progress({ name: 'X', pickedCount: 3, metrikenVisited: true, zustellungVisited: true }));
		const expected: CompareNewTabId[] = ['orte', 'vergleich', 'wetter', 'zustellung'];
		assert.deepEqual([...u].sort(), expected);
	});
});

// ── doneTabs ──────────────────────────────────────────────────────────────────

describe('doneTabs — Done-Zustand nach Spec-Tabelle', () => {
	test('Name → vergleich done; ≥2 Orte → orte done', () => {
		const d = doneTabs(progress({ name: 'X', pickedCount: 2 }));
		assert.ok(d.has('vergleich'));
		assert.ok(d.has('orte'));
		assert.ok(!d.has('wetter'), 'wetter erst nach Besuch done');
	});

	test('1 Ort → orte NICHT done', () => {
		const d = doneTabs(progress({ name: 'X', pickedCount: 1 }));
		assert.ok(d.has('vergleich'));
		assert.ok(!d.has('orte'), '1 Ort zählt nicht als erledigt');
	});

	test('visited-Flags markieren die jeweiligen Tabs als done', () => {
		const d = doneTabs(progress({ name: 'X', pickedCount: 2, metrikenVisited: true, zustellungVisited: true }));
		for (const id of ['wetter', 'zustellung'] as CompareNewTabId[]) {
			assert.ok(d.has(id), `${id} muss done sein`);
		}
	});
});

// ── progressCount (max 4 — #2794) ─────────────────────────────────────────────

describe('progressCount — Fortschrittszähler', () => {
	test('Leerzustand = 0', () => {
		assert.equal(progressCount(doneTabs(progress())), 0);
	});

	test('vollständige Kette = 4', () => {
		const d = doneTabs(progress({ name: 'X', pickedCount: 2, metrikenVisited: true, zustellungVisited: true }));
		assert.equal(progressCount(d), 4);
	});

	test('deckelt bei 4, auch wenn ein Fremd-Set größer wäre', () => {
		const bloated = new Set<CompareNewTabId>([
			'vergleich',
			'orte',
			'wetter',
			'zustellung',
			'versand' as CompareNewTabId,
			'nochwas' as CompareNewTabId,
		]);
		assert.equal(progressCount(bloated), 4);
	});
});

// ── canActivate (#2794: frei, sobald Zustellung besucht ist — nicht früher) ───

describe('canActivate — "Briefing aktivieren" nach Zustellungs-Besuch', () => {
	test('Zustellung nicht besucht → false (Aktivieren-Button deaktiviert)', () => {
		const d = doneTabs(progress({ name: 'X', pickedCount: 2, metrikenVisited: true, zustellungVisited: false }));
		assert.equal(canActivate(d), false);
	});

	test('Zustellung besucht → true (Aktivieren freigegeben)', () => {
		const d = doneTabs(progress({ name: 'X', pickedCount: 2, metrikenVisited: true, zustellungVisited: true }));
		assert.equal(canActivate(d), true);
	});

	test('Leerzustand → false', () => {
		assert.equal(canActivate(doneTabs(progress())), false);
	});
});

// ── #1743 AC-19 / #2794 AC-6 an der Wirkstelle: ECHTES SSR-Rendering von CompareNewEditor ──
// Reiterleiste, Fortschrittszaehler und „Briefing aktivieren" (Desktop-Fuß cm-desktop-footer, #2837 S2, und
// mobiler Sticky-Footer im Schritt Zustellung) — Muster compare_new_lock_engine_wirkstelle.

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
register(pathToFileURL(path.join(HERE, '../../trip-new/__tests__/ssrRunesHook.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const Editor = (await import(pathToFileURL(path.join(HERE, '../CompareNewEditor.svelte')).href)).default;

function editorHtml(activeTab: string, isMobileViewport: boolean, flags: Record<string, boolean>): string {
	// Issue #2727 (AC-9): kein Context-Stub mehr — Name und Orte reisen ueber stateOverride.
	return render(Editor, {
		props: { stateOverride: { activeTab, isMobileViewport, name: 'X', pickedIds: ['a', 'b', 'c'], ...flags } }
	}).body;
}
function knopfGesperrt(html: string, testid: string): boolean {
	const m = html.match(new RegExp(`<button[^>]*data-testid="${testid}"[^>]*>`));
	assert.ok(m, `Knopf ${testid} nicht gerendert`);
	return /\sdisabled(=|\s|>)/.test(m![0]);
}
/** Äußeres HTML des Desktop-Fußes cm-desktop-footer (#2837 S2); fehlt er, scheitert der Test hier. */
function imDesktopFuss(html: string): string {
	const i = html.indexOf('data-testid="cm-desktop-footer"');
	assert.notEqual(i, -1, '#2837 S2 FAIL: Desktop-Fuß cm-desktop-footer fehlt — „Briefing aktivieren" steht nicht unten');
	const start = html.lastIndexOf('<', i);
	const re = /<div\b[^>]*>|<\/div>/g;
	re.lastIndex = start;
	let tiefe = 0;
	let m: RegExpExecArray | null;
	while ((m = re.exec(html))) {
		tiefe += m[0].startsWith('</') ? -1 : 1;
		if (tiefe === 0) return html.slice(start, m.index + m[0].length);
	}
	return html.slice(start);
}
const BIS_WETTER = { metrikenVisited: true };
const BIS_ZUSTELLUNG = { metrikenVisited: true, zustellungVisited: true };

describe('#1743 AC-19 / #2794 AC-6 Wirkstelle /compare/new: Aktivieren nach Zustellung', () => {
	test('Reiterleiste: vergleich · orte · wetter · zustellung', () => {
		const ids = [...editorHtml('vergleich', false, BIS_ZUSTELLUNG).matchAll(/data-testid="compare-editor-tab-([a-z-]+)"/g)].map((m) => m[1]);
		assert.deepEqual(ids, ['vergleich', 'orte', 'wetter', 'zustellung']);
	});

	test('Fortschritt: vier Segmente; nach Zustellung „4 / 4 Abschnitte eingerichtet"', () => {
		const html = editorHtml('zustellung', false, BIS_ZUSTELLUNG);
		assert.equal((html.match(/data-testid="compare-editor-progress-segment"/g) ?? []).length, 4, 'Segmentzahl ≠ 4');
		assert.match(html, /4 \/ 4 Abschnitte eingerichtet/);
	});

	// #2837 S2 (AC-8): „Briefing aktivieren" sitzt im Desktop-Fuß cm-desktop-footer des AnlegeRahmen.
	test('Desktop: „Briefing aktivieren" im Fuß cm-desktop-footer — gesperrt bis Wetter, frei nach Zustellung', () => {
		assert.equal(knopfGesperrt(imDesktopFuss(editorHtml('wetter', false, BIS_WETTER)), 'compare-editor-activate'), true);
		assert.equal(knopfGesperrt(imDesktopFuss(editorHtml('zustellung', false, BIS_ZUSTELLUNG)), 'compare-editor-activate'), false,
			'#2794 AC-6 FAIL: „Briefing aktivieren" ist nach dem Zustellungs-Besuch noch gesperrt.');
	});

	test('Mobil: im Schritt Zustellung steht der freie Aktivieren-Knopf im Sticky-Footer', () => {
		assert.equal(knopfGesperrt(editorHtml('zustellung', true, BIS_ZUSTELLUNG), 'cm-mobile-activate'), false,
			'#2794 AC-6 FAIL: mobil fehlt im Schritt Zustellung der freie Knopf „Briefing aktivieren".');
	});
});
