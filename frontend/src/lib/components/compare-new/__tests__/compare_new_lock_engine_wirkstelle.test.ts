// TDD RED — #2277 S4, AC-1/AC-3/AC-6/AC-7: Zusicherung an der WIRKSTELLE.
// Rendert den echten CompareNewEditor (SSR) und liest `data-locked` der Reiterleiste bzw.
// `disabled` des Aktivieren-Knopfs. Ein Logik-Test allein reicht nicht (Mutations-Gegenprobe).
//
// TEST-SEAM (verlangt vom Developer, Muster TripNewEditor `stateOverride`): optionale Prop
//   stateOverride?: { activeTab?, isMobileViewport?, metrikenVisited?, idealsVisited?,
//                     alarmeVisited?, versandVisited? }
// Ohne Übergabe bleibt das Verhalten unverändert. Name/Orte kommen aus dem Wizard-Kontext.
// Pfadregel: alles relativ zu dieser Datei.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> compare-new -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');
register(pathToFileURL(path.join(HERE, '../../trip-new/__tests__/ssrRunesHook.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const { render } = await import('svelte/server');
const Editor = (
	await import(pathToFileURL(path.join(HERE, '../CompareNewEditor.svelte')).href)
).default;

type Seed = { name?: string; picked?: number; metriken?: boolean; ideals?: boolean; alarme?: boolean; versand?: boolean };

function html(s: Seed): string {
	const wiz = {
		name: s.name ?? '',
		region: '',
		profile: 'wandern',
		pickedIds: Array.from({ length: s.picked ?? 0 }, (_, i) => `loc${i}`),
	};
	return render(Editor, {
		props: {
			stateOverride: {
				activeTab: 'vergleich',
				isMobileViewport: false,
				metrikenVisited: !!s.metriken,
				idealsVisited: !!s.ideals,
				alarmeVisited: !!s.alarme,
				versandVisited: !!s.versand,
			},
		},
		context: new Map([['compare-wizard-state', wiz]]),
	}).body;
}

function locked(h: string, tab: string): boolean {
	const m = h.match(new RegExp(`data-testid="compare-editor-tab-${tab}"[^>]*?data-locked="(true|false)"`));
	assert.ok(m, `Reiter ${tab} nicht im Dokument — Wirkstelle nicht erreicht`);
	return m![1] === 'true';
}
function activateDisabled(h: string): boolean {
	const m = h.match(/<button[^>]*data-testid="compare-editor-activate"[^>]*>/);
	assert.ok(m, 'Aktivieren-Knopf nicht im Dokument — Wirkstelle nicht erreicht');
	return /\sdisabled(=|\s|>)/.test(m![0]);
}

describe('AC-6: Vorderteil an der Reiterleiste', () => {
	test('leerer Name: Orte gesperrt', () => assert.equal(locked(html({}), 'orte'), true));
	test('Name, 1 Ort: Orte frei, Metriken gesperrt', () => {
		const h = html({ name: 'X', picked: 1 });
		assert.equal(locked(h, 'orte'), false);
		assert.equal(locked(h, 'wetter-metriken'), true);
	});
	test('Name, 2 Orte: Metriken frei', () => assert.equal(locked(html({ name: 'X', picked: 2 }), 'wetter-metriken'), false));
});

// #1743: kein Reiter „Versand" mehr — die Kette endet bei Alarme; Aktivieren und
// voller Zaehler haengen am Alarme-Besuch (5 Schritte). Ein Versand-Flag im Seed
// (Altbestand) bleibt wirkungslos.
describe('AC-1/AC-7: Schwanz-Kette an der Reiterleiste (Besuchs-Flags über stateOverride)', () => {
	const base = { name: 'X', picked: 2 };
	test('nichts besucht: Wertebereiche, Alarme gesperrt', () => {
		const h = html(base);
		for (const t of ['wertebereiche', 'alarme']) assert.equal(locked(h, t), true, t);
	});
	test('Metriken besucht: nur Wertebereiche frei', () => {
		const h = html({ ...base, metriken: true });
		assert.equal(locked(h, 'wertebereiche'), false);
		assert.equal(locked(h, 'alarme'), true);
	});
	test('Wertebereiche besucht: Alarme frei', () => {
		const h = html({ ...base, metriken: true, ideals: true });
		assert.equal(locked(h, 'alarme'), false);
	});
	test('#1743: kein Reiter versand im Dokument', () => {
		const h = html({ ...base, metriken: true, ideals: true, alarme: true });
		assert.ok(!/data-testid="compare-editor-tab-versand"/.test(h), 'Reiter versand existiert noch');
	});
});

describe('AC-3: Aktivieren-Knopf', () => {
	const bisWertebereiche = { name: 'X', picked: 2, metriken: true, ideals: true };
	test('vor Alarme-Besuch deaktiviert', () => assert.equal(activateDisabled(html(bisWertebereiche)), true));
	test('nach Alarme-Besuch aktiv (#1743)', () => assert.equal(activateDisabled(html({ ...bisWertebereiche, alarme: true })), false));
	test('ein Versand-Flag allein schaltet nichts frei', () => assert.equal(activateDisabled(html({ ...bisWertebereiche, versand: true })), true));
});

// ── Zaehler-Anzeige (Hero "n / 5 Abschnitte eingerichtet" + Mobile "n/5", #1743) ──
function counter(h: string): { desktop: string; mobile: string } {
	const d = h.match(/data-testid="compare-editor-progress"[\s\S]*?<span class="mono"[^>]*>\s*([^<]*?)\s*<\/span>/);
	const m = h.match(/data-testid="cm-mobile-progress"[\s\S]*?<span class="mono"[^>]*>\s*([^<]*?)\s*<\/span>\s*<\/div>/);
	assert.ok(d && m, 'Zaehler-Anzeige nicht im Dokument — Wirkstelle nicht erreicht');
	return { desktop: d![1], mobile: m![1] };
}

describe('Zaehler am Editor (F002): Deckel und Schrittliste', () => {
	test('nichts eingerichtet: "Noch nichts eingerichtet", mobil 0/5', () => {
		const c = counter(html({}));
		assert.equal(c.desktop, 'Noch nichts eingerichtet');
		assert.equal(c.mobile, '0/5');
	});
	test('Name + 2 Orte: 2 / 5 (Vergleich + Orte)', () => {
		const c = counter(html({ name: 'X', picked: 2 }));
		assert.equal(c.desktop, '2 / 5 Abschnitte eingerichtet');
		assert.equal(c.mobile, '2/5');
	});
	test('alle Flags gesetzt: genau 5 / 5 (Deckel 5, Versand-Flag zaehlt nicht)', () => {
		const c = counter(html({ name: 'X', picked: 2, metriken: true, ideals: true, alarme: true, versand: true }));
		assert.equal(c.desktop, '5 / 5 Abschnitte eingerichtet');
		assert.equal(c.mobile, '5/5');
	});
	test('bis Alarme besucht: Zaehler voll (5 / 5) — voll genau dann, wenn Aktivieren frei', () => {
		const c = counter(html({ name: 'X', picked: 2, metriken: true, ideals: true, alarme: true }));
		assert.equal(c.desktop, '5 / 5 Abschnitte eingerichtet');
	});
	test('Wertebereiche-Besuch allein erhoeht den Zaehler (4 / 5 ohne Alarme)', () => {
		const c = counter(html({ name: 'X', picked: 2, metriken: true, ideals: true }));
		assert.equal(c.desktop, '4 / 5 Abschnitte eingerichtet');
	});
});

describe('F003: konjunktive Kette bei uebersprungenem Flag (Compare-Semantik wie vor S4)', () => {
	const base = { name: 'X', picked: 2 };
	test('Ideal-Flag ohne Metriken-Flag: Wertebereiche und Alarme bleiben gesperrt', () => {
		const h = html({ ...base, ideals: true });
		assert.equal(locked(h, 'wertebereiche'), true);
		assert.equal(locked(h, 'alarme'), true);
	});
	test('Alarme-Flag ohne Ideal-Flag: Alarme gesperrt', () => {
		const h = html({ ...base, metriken: true, alarme: true });
		assert.equal(locked(h, 'alarme'), true);
	});
});
