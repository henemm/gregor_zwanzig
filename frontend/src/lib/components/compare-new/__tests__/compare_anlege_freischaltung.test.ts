// Epic #1301 Scheibe F2a / #2277 S4: Freischalt-Vertrag des Compare-Anlege-Flows.
//
// Vormals compareNewLogic.test.ts (Datei gelöscht, #2277 S4). Die Schwanz-Kette
// kommt jetzt aus dem geteilten Kern shared/anlegeLockEngine.ts; das Compare-
// Vorderteil (Name, ≥2 Orte) und der Zähler-Deckel 6 wohnen in CompareNewEditor.svelte.
// Die Hilfsfunktionen unten bilden genau diese Komposition ab (Kern + Vorderteil);
// die Wirkstelle selbst (echte Reiterleiste) prüft compare_new_lock_engine_wirkstelle.test.ts.
// Freischalt-Kette: Name → Orte≥2 → metriken → wertebereiche(idealwerte) → alarme,
// mit Besuchs-Kaskade (einmal besucht bleibt besucht). Kein Mock.
// Issue #1743 (AC-17/AC-19): kein Schritt „Versand" mehr — die Kette endet bei Alarme,
// „Briefing aktivieren" ist frei, sobald Alarme besucht ist; Zaehler-Deckel 5.
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

type CompareNewTabId = 'vergleich' | 'orte' | 'wetter-metriken' | 'wertebereiche' | 'alarme';
interface CompareNewProgress {
	name: string;
	pickedCount: number;
	metrikenVisited: boolean;
	idealsVisited: boolean;
	alarmeVisited: boolean;
}
const TAIL: TailIds<CompareNewTabId> = { metriken: 'wetter-metriken', wertebereiche: 'wertebereiche', alarme: 'alarme' };
const STEPS: CompareNewTabId[] = ['vergleich', 'orte', 'wetter-metriken', 'wertebereiche', 'alarme'];

function tailP(p: CompareNewProgress) {
	return {
		metrikenFrei: !!p.name.trim() && p.pickedCount >= 2,
		metrikenVisited: p.metrikenVisited,
		wertebereicheVisited: p.idealsVisited,
		alarmeVisited: p.alarmeVisited,
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
	return Math.min(kernProgressCount(done, STEPS), 5);
}
const canActivate = (done: Set<CompareNewTabId>) => canFinish(done);

// ── Progress-Builder: leerer Start, gezielt Felder überschreiben ──────────────

function progress(over: Partial<CompareNewProgress> = {}): CompareNewProgress {
	return {
		name: '',
		pickedCount: 0,
		metrikenVisited: false,
		idealsVisited: false,
		alarmeVisited: false,
		...over,
	};
}

// ── AC-2: Leerzustand — nur "vergleich" offen ────────────────────────────────

describe('AC-2: unlockedTabs — progressive Freischaltung', () => {
	test('Leerzustand: nur "vergleich" offen, 4 Tabs gesperrt', () => {
		const u = unlockedTabs(progress());
		assert.deepEqual([...u].sort(), ['vergleich']);
	});

	test('AC-3: Name gesetzt → "orte" schaltet frei, "metriken" bleibt gesperrt', () => {
		const u = unlockedTabs(progress({ name: 'Sardinien-Woche' }));
		assert.ok(u.has('orte'), 'orte muss frei sein');
		assert.ok(!u.has('wetter-metriken'), 'metriken noch gesperrt (Orte fehlen)');
	});

	test('Nur Whitespace als Name schaltet "orte" NICHT frei', () => {
		const u = unlockedTabs(progress({ name: '   ' }));
		assert.ok(!u.has('orte'), 'Whitespace-Name darf nicht freischalten');
		assert.deepEqual([...u].sort(), ['vergleich']);
	});

	test('AC-4: genau 1 Ort schaltet "metriken" NICHT frei', () => {
		const u = unlockedTabs(progress({ name: 'X', pickedCount: 1 }));
		assert.ok(!u.has('wetter-metriken'), '1 Ort reicht nicht (Minimum 2)');
	});

	test('AC-4: 2 Orte schalten "metriken" frei, "idealwerte" bleibt gesperrt', () => {
		const u = unlockedTabs(progress({ name: 'X', pickedCount: 2 }));
		assert.ok(u.has('wetter-metriken'), 'metriken frei ab 2 Orten');
		assert.ok(!u.has('wertebereiche'), 'idealwerte noch gesperrt (Metriken nicht besucht)');
	});

	test('AC-5: metrikenVisited → "idealwerte" frei, "alarme" bleibt gesperrt', () => {
		const u1 = unlockedTabs(progress({ name: 'X', pickedCount: 2, metrikenVisited: true }));
		assert.ok(u1.has('wertebereiche'), 'idealwerte frei nach Metriken-Besuch');
		// Issue #1360: hier stand vormals der Layout-Reiter — er ist aufgeloest,
		// naechste Stufe ist direkt 'alarme'.
		assert.ok(!u1.has('alarme'), 'alarme noch gesperrt (Wertebereiche nicht besucht)');
	});

	test('AC-7: idealsVisited → "alarme" frei; #1743: alarmeVisited schaltet keinen "versand" frei', () => {
		const u1 = unlockedTabs(
			progress({
				name: 'X',
				pickedCount: 2,
				metrikenVisited: true,
				idealsVisited: true,
			})
		);
		assert.ok(u1.has('alarme'), 'alarme frei nach Wertebereiche-Besuch (#1360: Layout-Reiter aufgeloest)');
		const u2 = unlockedTabs(
			progress({
				name: 'X',
				pickedCount: 2,
				metrikenVisited: true,
				idealsVisited: true,
				alarmeVisited: true,
			})
		) as Set<string>;
		assert.ok(!u2.has('versand'), `#1743: es gibt keinen Schritt versand mehr: ${[...u2].sort().join(',')}`);
	});

	test('Kaskade übersprungen: idealsVisited ohne Vorstufen schaltet "alarme" NICHT frei', () => {
		// Nur idealsVisited=true, aber ohne Name/Orte/metriken — der Tab selbst
		// darf ohne die kompletten Vorbedingungen nicht erreichbar sein.
		// Issue #1360: vormals layoutVisited (Reiter aufgeloest).
		const u = unlockedTabs(progress({ idealsVisited: true }));
		assert.ok(!u.has('alarme'), 'ohne Name/Orte/metriken kein alarme-Zugang');
		assert.deepEqual([...u].sort(), ['vergleich']);
	});

	test('Vollständige Kette: alle 5 Tabs offen (#1360: ohne Layout-Reiter, #1743: ohne Versand)', () => {
		const u = unlockedTabs(
			progress({
				name: 'X',
				pickedCount: 3,
				metrikenVisited: true,
				idealsVisited: true,
				alarmeVisited: true,
			})
		);
		const expected: CompareNewTabId[] = [
			'alarme',
			'orte',
			'vergleich',
			'wertebereiche',
			'wetter-metriken',
		];
		assert.deepEqual([...u].sort(), expected);
	});
});

// ── doneTabs ──────────────────────────────────────────────────────────────────

describe('doneTabs — Done-Zustand nach Spec-Tabelle', () => {
	test('Name → vergleich done; ≥2 Orte → orte done', () => {
		const d = doneTabs(progress({ name: 'X', pickedCount: 2 }));
		assert.ok(d.has('vergleich'));
		assert.ok(d.has('orte'));
		assert.ok(!d.has('wetter-metriken'), 'metriken erst nach Besuch done');
	});

	test('1 Ort → orte NICHT done', () => {
		const d = doneTabs(progress({ name: 'X', pickedCount: 1 }));
		assert.ok(d.has('vergleich'));
		assert.ok(!d.has('orte'), '1 Ort zählt nicht als erledigt');
	});

	test('visited-Flags markieren die jeweiligen Tabs als done', () => {
		const d = doneTabs(
			progress({
				name: 'X',
				pickedCount: 2,
				metrikenVisited: true,
				idealsVisited: true,
				alarmeVisited: true,
			})
		);
		for (const id of ['wetter-metriken', 'wertebereiche', 'alarme'] as CompareNewTabId[]) {
			assert.ok(d.has(id), `${id} muss done sein`);
		}
	});
});

// ── progressCount (max 5 — Issue #1360, #1743 ohne Versand) ──────────────────

describe('progressCount — Fortschrittszähler', () => {
	test('Leerzustand = 0', () => {
		assert.equal(progressCount(doneTabs(progress())), 0);
	});

	test('vollständige Kette = 5 (ohne Versand-Schritt)', () => {
		const d = doneTabs(
			progress({
				name: 'X',
				pickedCount: 2,
				metrikenVisited: true,
				idealsVisited: true,
				alarmeVisited: true,
			})
		);
		assert.equal(progressCount(d), 5);
	});

	test('deckelt bei 5, auch wenn ein Fremd-Set größer wäre', () => {
		const bloated = new Set<CompareNewTabId>([
			'vergleich',
			'orte',
			'wetter-metriken',
			'wertebereiche',
			'alarme',
			'versand' as CompareNewTabId,
			'nochwas' as CompareNewTabId,
		]);
		assert.equal(progressCount(bloated), 5);
	});
});

// ── canActivate (#1743 AC-19: frei, sobald Alarme besucht ist — nicht früher) ─

describe('canActivate — "Briefing aktivieren" nach Alarme-Besuch', () => {
	test('Alarme nicht besucht → false (Aktivieren-Button deaktiviert)', () => {
		const d = doneTabs(
			progress({
				name: 'X',
				pickedCount: 2,
				metrikenVisited: true,
				idealsVisited: true,
				alarmeVisited: false,
			})
		);
		assert.equal(canActivate(d), false);
	});

	test('Alarme besucht (kein Versand-Schritt) → true (Aktivieren freigegeben)', () => {
		const d = doneTabs(
			progress({
				name: 'X',
				pickedCount: 2,
				metrikenVisited: true,
				idealsVisited: true,
				alarmeVisited: true,
			})
		);
		assert.equal(canActivate(d), true);
	});

	test('Leerzustand → false', () => {
		assert.equal(canActivate(doneTabs(progress())), false);
	});
});

// ── #1743 AC-19 an der Wirkstelle: ECHTES SSR-Rendering von CompareNewEditor ──
// Reiterleiste, Fortschrittszaehler und „Briefing aktivieren" (Desktop-Kopfzeile und
// mobiler Sticky-Footer im Schritt Alarme) — Muster compare_new_lock_engine_wirkstelle.

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
register(pathToFileURL(path.join(HERE, '../../trip-new/__tests__/ssrRunesHook.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const Editor = (await import(pathToFileURL(path.join(HERE, '../CompareNewEditor.svelte')).href)).default;

function editorHtml(activeTab: string, isMobileViewport: boolean, flags: Record<string, boolean>): string {
	const wiz = { name: 'X', region: '', profile: 'wandern', pickedIds: ['a', 'b', 'c'] };
	return render(Editor, {
		props: { stateOverride: { activeTab, isMobileViewport, ...flags } },
		context: new Map([['compare-wizard-state', wiz]])
	}).body;
}
function knopfGesperrt(html: string, testid: string): boolean {
	const m = html.match(new RegExp(`<button[^>]*data-testid="${testid}"[^>]*>`));
	assert.ok(m, `Knopf ${testid} nicht gerendert`);
	return /\sdisabled(=|\s|>)/.test(m![0]);
}
const BIS_WERTEBEREICHE = { metrikenVisited: true, idealsVisited: true };
const BIS_ALARME = { metrikenVisited: true, idealsVisited: true, alarmeVisited: true };

describe('#1743 AC-19 Wirkstelle /compare/new: kein Versand-Schritt, Aktivieren nach Alarme', () => {
	test('Reiterleiste: vergleich · orte · wetter-metriken · wertebereiche · alarme', () => {
		const ids = [...editorHtml('vergleich', false, BIS_ALARME).matchAll(/data-testid="compare-editor-tab-([a-z-]+)"/g)].map((m) => m[1]);
		assert.deepEqual(ids, ['vergleich', 'orte', 'wetter-metriken', 'wertebereiche', 'alarme']);
	});

	test('Fortschritt: fünf Segmente; nach Alarme „5 / 5 Abschnitte eingerichtet"', () => {
		const html = editorHtml('alarme', false, BIS_ALARME);
		assert.equal((html.match(/data-testid="compare-editor-progress-segment"/g) ?? []).length, 5, 'Segmentzahl ≠ 5');
		assert.match(html, /5 \/ 5 Abschnitte eingerichtet/);
	});

	test('Desktop: „Briefing aktivieren" gesperrt bis Wertebereiche, frei nach Alarme', () => {
		assert.equal(knopfGesperrt(editorHtml('wertebereiche', false, BIS_WERTEBEREICHE), 'compare-editor-activate'), true);
		assert.equal(knopfGesperrt(editorHtml('alarme', false, BIS_ALARME), 'compare-editor-activate'), false,
			'#1743 AC-19 FAIL: „Briefing aktivieren" ist nach dem Alarme-Besuch noch gesperrt.');
	});

	test('Mobil: im Schritt Alarme steht der freie Aktivieren-Knopf im Sticky-Footer', () => {
		assert.equal(knopfGesperrt(editorHtml('alarme', true, BIS_ALARME), 'cm-mobile-activate'), false,
			'#1743 AC-19 FAIL: mobil fehlt im Schritt Alarme der freie Knopf „Briefing aktivieren".');
	});
});
