// TDD RED — Issue #2913, Scheibe (c): Wetter-Reiter „Nicht im Briefing“, Warnungen, Radar, Anpassen.
// Spec: docs/specs/modules/feat_2913_scheibe_c_wetter_rest.md — AC-4 (Aufklapper), AC-5 (Stundenraster), AC-6.
//
// Vertrag (hier festgelegt, /50 baut danach):
//   molecules/Aufklapper.svelte (neu, Mockup `details.adv`, CSS Z.164–167)
//     Props: titel: string; offen?: boolean (Startzustand, Default false); testid?: string (am <details>);
//            summaryTestid?: string (am <summary>); children: Snippet (Inhalt).
//     Markup: <details data-slot="aufklapper" data-testid={testid} [open]> mit <summary data-testid={summaryTestid}
//            aria-expanded="true|false">titel + Zeichen „＋“ (zu) bzw. „－“ (auf, aria-hidden)</summary>; der Inhalt
//            steht immer im DOM (das native <details> blendet ihn aus), ein Klick klappt auf und zu und spiegelt
//            aria-expanded und das Zeichen. Kein rohes <button>/<input>/<select>; <style> nur aus Tokens (Regel b).
//     Export im Barrel molecules/index.ts.
//   molecules/UhrzeitFeld.svelte
//     Prop `stundenraster?: boolean` → data-stundenraster="true" an der Wurzel; nur die Stunde ist ein
//     Eingabesegment (role="spinbutton"), die Minute steht fest als „00“ und ist nicht editierbar (kein
//     spinbutton, nicht contenteditable); gemeldet wird `HH:00`. Ohne Prop unverändert (Stunde + Minute,
//     einziger bisheriger Nutzer edit/StageTimeField.svelte).
//
// Verhalten per Server-Render (svelte/server); Barrel und Token-Regel als doc-compliance-test.
//
//   cd frontend && npm test -- src/lib/components/molecules/__tests__/aufklapper_stundenraster.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { parse } from 'svelte/compiler';

import { zaehleTokenVerstoesse } from '../../../__tests__/bausteine_waechter_regeln.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> molecules -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');
const MOL = path.resolve(HERE, '..');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const { createRawSnippet } = await import('svelte');

async function lade(n: string): Promise<any> {
	const d = path.join(MOL, `${n}.svelte`);
	assert.ok(existsSync(d), `TDD RED: molecules/${n}.svelte fehlt`);
	return (await import(pathToFileURL(d).href)).default;
}
const html = (k: any, props: Record<string, unknown>) => render(k, { props }).body.replace(/<!--[\s\S]*?-->/g, '');
const text = (h: string) => h.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
const inhalt = createRawSnippet(() => ({ render: () => '<p data-testid="probe-inhalt">Inhalt</p>' }));

// ─── AC-4: Aufklapper ────────────────────────────────────────────────────────

describe('AC-4: Molekül Aufklapper (details/summary, ＋/－, aria-expanded)', () => {
	const props = (offen: boolean) => ({ titel: 'Anpassen', offen, testid: 'probe-karte', summaryTestid: 'probe-auf', children: inhalt });

	test('zu: <details> ohne open, <summary> mit aria-expanded="false" und „＋“, Testids', async () => {
		const A = await lade('Aufklapper');
		const h = html(A, props(false));
		const det = h.match(/<details\b[^>]*>/)?.[0] ?? '';
		assert.ok(det, 'kein <details>');
		assert.match(det, /data-slot="aufklapper"/);
		assert.match(det, /data-testid="probe-karte"/);
		assert.doesNotMatch(det, /\sopen\b/);
		const sum = h.match(/<summary\b[^>]*>([\s\S]*?)<\/summary>/);
		assert.ok(sum, 'kein <summary>');
		assert.match(sum![0], /data-testid="probe-auf"/);
		assert.match(sum![0], /aria-expanded="false"/);
		assert.match(text(sum![1]), /Anpassen/);
		assert.match(sum![1], /＋/);
		assert.doesNotMatch(sum![1], /－/);
	});
	test('auf: <details open>, aria-expanded="true" und „－“', async () => {
		const A = await lade('Aufklapper');
		const h = html(A, props(true));
		assert.match(h.match(/<details\b[^>]*>/)?.[0] ?? '', /\sopen\b/);
		const sum = h.match(/<summary\b[^>]*>([\s\S]*?)<\/summary>/);
		assert.match(sum![0], /aria-expanded="true"/);
		assert.match(sum![1], /－/);
		assert.doesNotMatch(sum![1], /＋/);
	});
	test('Inhalt steht im <details> nach dem <summary> (auch zugeklappt im DOM)', async () => {
		const A = await lade('Aufklapper');
		const h = html(A, props(false));
		assert.match(h, /<\/summary>[\s\S]*data-testid="probe-inhalt"[\s\S]*<\/details>/);
	});
	// doc-compliance-test: Regeln des Bausteine-Wächters (ADR-0112) für das neue Molekül.
	test('Quelle: kein rohes <button>/<input>/<select>, Tokens regelkonform, kein audit:exempt', () => {
		const d = path.join(MOL, 'Aufklapper.svelte');
		assert.ok(existsSync(d), 'TDD RED: molecules/Aufklapper.svelte fehlt');
		const q = readFileSync(d, 'utf8');
		const roh: string[] = [];
		const lauf = (x: any) => {
			if (Array.isArray(x)) return x.forEach(lauf);
			if (!x || typeof x !== 'object') return;
			if (x.type === 'RegularElement' && ['button', 'input', 'select', 'textarea'].includes(x.name)) roh.push(x.name);
			for (const [k, v] of Object.entries(x)) if (k !== 'parent') lauf(v);
		};
		lauf((parse(q, { modern: true }) as any).fragment);
		assert.deepEqual(roh, []);
		assert.deepEqual(zaehleTokenVerstoesse('src/lib/components/molecules/Aufklapper.svelte', q), [], 'Aufklapper verletzt Regel b (rohe Werte statt Tokens)');
		assert.doesNotMatch(q, /audit:exempt/);
	});
	// doc-compliance-test
	test('Barrel molecules/index.ts exportiert Aufklapper', () => {
		const idx = readFileSync(path.join(MOL, 'index.ts'), 'utf8');
		assert.match(idx, /export\s*\{\s*default as Aufklapper\s*\}\s*from\s*'\.\/Aufklapper\.svelte'/, 'TDD RED: Aufklapper nicht im Barrel');
	});
});

// ─── AC-5: UhrzeitFeld im Stundenraster ──────────────────────────────────────

const spinbuttons = (h: string) => [...h.matchAll(/<[a-z]+\b[^>]*\srole="spinbutton"[^>]*>/g)].map((m) => m[0]);

describe('AC-5: UhrzeitFeld Stundenraster-Modus', () => {
	test('stundenraster: Wurzel data-stundenraster="true", Anzeige „06:00“', async () => {
		const U = await lade('UhrzeitFeld');
		const h = html(U, { value: '06:00', testid: 'day-window-start-hour', ariaLabel: 'von', stundenraster: true });
		assert.match(h.match(/<div\b[^>]*data-slot="uhrzeit-feld"[^>]*>/)?.[0] ?? '', /data-stundenraster="true"/, 'TDD RED: kein Stundenraster-Modus');
		assert.match(text(h).replace(/\s/g, ''), /06:00/);
	});
	test('stundenraster: nur die Stunde ist editierbar, die Minute steht fest (kein spinbutton, nicht contenteditable)', async () => {
		const U = await lade('UhrzeitFeld');
		const h = html(U, { value: '06:00', ariaLabel: 'von', stundenraster: true });
		const sb = spinbuttons(h);
		assert.equal(sb.length, 1, `TDD RED: erwartet 1 Eingabesegment (Stunde), gefunden ${sb.length}`);
		assert.match(sb[0], /data-segment="hour"/);
		assert.doesNotMatch(h, /<[a-z]+\b[^>]*data-segment="minute"[^>]*contenteditable="true"/, 'Minute ist editierbar');
	});
	test('ohne stundenraster unverändert: Stunde und Minute editierbar, kein data-stundenraster (StageTimeField)', async () => {
		const U = await lade('UhrzeitFeld');
		const h = html(U, { value: '08:30', ariaLabel: 'Start' });
		const sb = spinbuttons(h);
		assert.equal(sb.length, 2);
		assert.match(sb[0], /data-segment="hour"/);
		assert.match(sb[1], /data-segment="minute"/);
		assert.doesNotMatch(h, /data-stundenraster/);
	});
});
