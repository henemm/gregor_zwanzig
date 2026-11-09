// TDD RED — #2277 S4, AC-1/AC-3/AC-6/AC-7: Zusicherung an der WIRKSTELLE.
// Rendert den echten CompareNewEditor (SSR) und liest `data-locked` der Reiterleiste bzw.
// `disabled` des Aktivieren-Knopfs. Ein Logik-Test allein reicht nicht (Mutations-Gegenprobe).
//
// TEST-SEAM (Muster TripNewEditor `stateOverride`): optionale Prop
//   stateOverride?: { activeTab?, isMobileViewport?, metrikenVisited?, zustellungVisited? }
// Ohne Übergabe bleibt das Verhalten unverändert. Name/Orte kommen aus dem Wizard-Kontext.
//
// Issue #2794 S3a (Spec feat_2794_s3a_teil2_leiste.md AC-6): die Kette lautet
// Vergleich · Orte · Wetter · Zustellung (4 Schritte); Aktivieren und voller Zähler hängen am
// Zustellungs-Besuch. Die Zusicherungen an der Wirkstelle bleiben, nur Kennungen und Deckel folgen.
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

type Seed = { name?: string; picked?: number; wetter?: boolean; zustellung?: boolean; altFlags?: boolean };

function html(s: Seed): string {
	// Issue #2727 (AC-9): kein Context-Stub mehr — Name und Orte reisen ueber stateOverride.
	return render(Editor, {
		props: {
			stateOverride: {
				activeTab: 'vergleich',
				isMobileViewport: false,
				name: s.name ?? '',
				pickedIds: Array.from({ length: s.picked ?? 0 }, (_, i) => `loc${i}`),
				metrikenVisited: !!s.wetter,
				zustellungVisited: !!s.zustellung,
				// Altbestand-Flags (vor #2794): duerfen nichts bewirken.
				...(s.altFlags ? { idealsVisited: true, alarmeVisited: true, versandVisited: true } : {}),
			},
		},
	}).body;
}

function locked(h: string, tab: string): boolean {
	const m = h.match(new RegExp(`data-testid="compare-editor-tab-${tab}"[^>]*?data-locked="(true|false)"`));
	assert.ok(m, `Reiter ${tab} nicht im Dokument — Wirkstelle nicht erreicht`);
	return m![1] === 'true';
}
// #2837 S2 (AC-8): Pfad folgt dem Rahmen — „Briefing aktivieren" wird im Desktop-Fuß
// cm-desktop-footer gesucht (vorher irgendwo im Dokument, faktisch in der Kopfleiste).
function activateDisabled(h: string): boolean {
	const fuss = h.indexOf('data-testid="cm-desktop-footer"');
	assert.notEqual(fuss, -1, '#2837 S2: Desktop-Fuß cm-desktop-footer fehlt — Wirkstelle nicht im Rahmen-Fuß');
	const m = h.slice(fuss).match(/<button[^>]*data-testid="compare-editor-activate"[^>]*>/);
	assert.ok(m, 'Aktivieren-Knopf nicht im Dokument — Wirkstelle nicht erreicht');
	return /\sdisabled(=|\s|>)/.test(m![0]);
}

describe('AC-6: Vorderteil an der Reiterleiste', () => {
	test('leerer Name: Orte gesperrt', () => assert.equal(locked(html({}), 'orte'), true));
	test('Name, 1 Ort: Orte frei, Wetter gesperrt', () => {
		const h = html({ name: 'X', picked: 1 });
		assert.equal(locked(h, 'orte'), false);
		assert.equal(locked(h, 'wetter'), true);
	});
	test('Name, 2 Orte: Wetter frei', () => assert.equal(locked(html({ name: 'X', picked: 2 }), 'wetter'), false));
});

describe('AC-1/AC-7 / #2794 AC-6: Schwanz-Kette an der Reiterleiste (Besuchs-Flags über stateOverride)', () => {
	const base = { name: 'X', picked: 2 };
	test('nichts besucht: Zustellung gesperrt', () => {
		assert.equal(locked(html(base), 'zustellung'), true);
	});
	test('Wetter besucht: Zustellung frei', () => {
		assert.equal(locked(html({ ...base, wetter: true }), 'zustellung'), false);
	});
	test('kein Reiter eines entfallenen Schritts im Dokument', () => {
		const h = html({ ...base, wetter: true, zustellung: true });
		for (const alt of ['versand', 'wetter-metriken', 'wertebereiche', 'alarme']) {
			assert.ok(!new RegExp(`data-testid="compare-editor-tab-${alt}"`).test(h), `Reiter ${alt} existiert noch`);
		}
	});
});

describe('AC-3: Aktivieren-Knopf', () => {
	const bisWetter = { name: 'X', picked: 2, wetter: true };
	test('vor Zustellungs-Besuch deaktiviert', () => assert.equal(activateDisabled(html(bisWetter)), true));
	test('nach Zustellungs-Besuch aktiv', () => assert.equal(activateDisabled(html({ ...bisWetter, zustellung: true })), false));
	test('Altbestand-Flags (Wertebereiche/Alarme/Versand) allein schalten nichts frei', () =>
		assert.equal(activateDisabled(html({ ...bisWetter, altFlags: true })), true));
});

// ── Zaehler-Anzeige (Hero "n / 4 Abschnitte eingerichtet" + Mobile "n/4") ──
function counter(h: string): { desktop: string; mobile: string } {
	const d = h.match(/data-testid="compare-editor-progress"[\s\S]*?<span class="mono"[^>]*>\s*([^<]*?)\s*<\/span>/);
	const m = h.match(/data-testid="cm-mobile-progress"[\s\S]*?<span class="mono"[^>]*>\s*([^<]*?)\s*<\/span>\s*<\/div>/);
	assert.ok(d && m, 'Zaehler-Anzeige nicht im Dokument — Wirkstelle nicht erreicht');
	return { desktop: d![1], mobile: m![1] };
}

describe('Zaehler am Editor (F002): Deckel und Schrittliste', () => {
	test('nichts eingerichtet: "Noch nichts eingerichtet", mobil 0/4', () => {
		const c = counter(html({}));
		assert.equal(c.desktop, 'Noch nichts eingerichtet');
		assert.equal(c.mobile, '0/4');
	});
	test('Name + 2 Orte: 2 / 4 (Vergleich + Orte)', () => {
		const c = counter(html({ name: 'X', picked: 2 }));
		assert.equal(c.desktop, '2 / 4 Abschnitte eingerichtet');
		assert.equal(c.mobile, '2/4');
	});
	test('alle Flags gesetzt: genau 4 / 4 (Deckel 4, Altbestand-Flags zaehlen nicht)', () => {
		const c = counter(html({ name: 'X', picked: 2, wetter: true, zustellung: true, altFlags: true }));
		assert.equal(c.desktop, '4 / 4 Abschnitte eingerichtet');
		assert.equal(c.mobile, '4/4');
	});
	test('bis Zustellung besucht: Zaehler voll (4 / 4) — voll genau dann, wenn Aktivieren frei', () => {
		const c = counter(html({ name: 'X', picked: 2, wetter: true, zustellung: true }));
		assert.equal(c.desktop, '4 / 4 Abschnitte eingerichtet');
	});
	test('Wetter-Besuch allein erhoeht den Zaehler (3 / 4 ohne Zustellung)', () => {
		const c = counter(html({ name: 'X', picked: 2, wetter: true }));
		assert.equal(c.desktop, '3 / 4 Abschnitte eingerichtet');
	});
});

describe('F003: konjunktive Kette bei uebersprungenem Flag (Compare-Semantik wie vor S4)', () => {
	const base = { name: 'X', picked: 2 };
	test('Zustellungs-Flag ohne Wetter-Flag: Zustellung bleibt gesperrt', () => {
		const h = html({ ...base, zustellung: true });
		assert.equal(locked(h, 'zustellung'), true);
	});
	test('Vorderteil offen (1 Ort): Wetter und Zustellung gesperrt trotz Besuchs-Flags', () => {
		const h = html({ name: 'X', picked: 1, wetter: true, zustellung: true });
		assert.equal(locked(h, 'wetter'), true);
		assert.equal(locked(h, 'zustellung'), true);
	});
});
