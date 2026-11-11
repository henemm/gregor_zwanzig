// TDD RED — Issue #2913, Scheibe (c): Wetter-Reiter „Nicht im Briefing“, Warnungen, Radar, Anpassen.
// Spec: docs/specs/modules/feat_2913_scheibe_c_wetter_rest.md — AC-2 (Rolle, ARIA, Tapfläche), AC-7 (Rückwärtskompatibilität).
//
// Vertrag (hier festgelegt, /50 baut danach):
//   atoms/Switch.svelte  Prop `testid?: string` → data-testid am role="switch"-Element; ohne Prop bleibt
//                        data-testid="switch" (alle bisherigen Nutzer unverändert, AC-7).
//                        Prop `tap?: boolean` → data-tap="true" am role="switch"-Element; sichtbare Größe bleibt
//                        (md = 36×20). Eine CSS-Regel (Switch.svelte <style> oder app.css), deren Selektor
//                        data-tap enthält, zieht die Trefferfläche auf var(--g-tap-min) (44 px, unsichtbar,
//                        z. B. per ::before). Ohne `tap` kein data-tap.
//                        Die Props werden nie als rohe Attribute `testid=`/`tap=` durchgereicht.
//
// Verhalten per Server-Render (svelte/server); CSS-Regel als doc-compliance-test.
//
//   cd frontend && npm test -- src/lib/components/atoms/__tests__/switch_testid_tap.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> atoms -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');
const ATOMS = path.resolve(HERE, '..');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');

const Switch = (await import(pathToFileURL(path.join(ATOMS, 'Switch.svelte')).href)).default;
const html = (props: Record<string, unknown>) => render(Switch, { props }).body.replace(/<!--[\s\S]*?-->/g, '');
const wurzel = (h: string) => h.match(/<span\b[^>]*\srole="switch"[^>]*>/)?.[0] ?? '';

describe('AC-7: Switch ohne neue Props wie bisher', () => {
	test('ohne testid → data-testid="switch"', () => {
		assert.match(wurzel(html({ checked: false })), /\sdata-testid="switch"/);
	});
	test('ohne tap → kein data-tap, sichtbar 36×20 (md)', () => {
		const w = wurzel(html({ checked: true }));
		assert.doesNotMatch(w, /data-tap/);
		assert.match(w, /width:\s*36px/);
		assert.match(w, /height:\s*20px/);
	});
});

describe('AC-2: Switch mit Testid und Tapfläche', () => {
	test('testid="wetter-warnungen-schalter" → genau diese Testid, kein rohes testid=-Attribut', () => {
		const w = wurzel(html({ checked: true, testid: 'wetter-warnungen-schalter' }));
		assert.match(w, /\sdata-testid="wetter-warnungen-schalter"/, 'TDD RED: Testid wird nicht durchgereicht');
		assert.doesNotMatch(w, /\sdata-testid="switch"/);
		assert.doesNotMatch(w, /\stestid=/);
	});
	test('Rolle switch, aria-checked folgt checked, aria-label durchgereicht', () => {
		const an = wurzel(html({ checked: true, testid: 't', 'aria-label': 'Amtliche Warnungen' }));
		const aus = wurzel(html({ checked: false, testid: 't', 'aria-label': 'Amtliche Warnungen' }));
		assert.match(an, /\saria-checked="true"/);
		assert.match(aus, /\saria-checked="false"/);
		assert.match(an, /\saria-label="Amtliche Warnungen"/);
	});
	test('tap → data-tap="true", sichtbare Größe bleibt 36×20, kein rohes tap=-Attribut', () => {
		const w = wurzel(html({ checked: false, tap: true }));
		assert.match(w, /\sdata-tap="true"/, 'TDD RED: kein data-tap');
		assert.doesNotMatch(w, /\stap=/);
		assert.match(w, /width:\s*36px/);
		assert.match(w, /height:\s*20px/);
	});
	// doc-compliance-test: die Trefferfläche ist eine CSS-Regel, im Server-Render nicht messbar.
	test('CSS: eine Regel mit data-tap im Selektor nutzt var(--g-tap-min)', () => {
		const quellen = [readFileSync(path.join(ATOMS, 'Switch.svelte'), 'utf8'), readFileSync(path.join(FRONTEND, 'src', 'app.css'), 'utf8')]
			.join('\n')
			.replace(/\/\*[\s\S]*?\*\//g, '');
		const treffer = [...quellen.matchAll(/([^{}]+)\{([^{}]*)\}/g)].filter((m) => /data-tap/.test(m[1]) && /var\(--g-tap-min\)/.test(m[2]));
		assert.ok(treffer.length > 0, 'TDD RED: keine CSS-Regel [data-tap] mit var(--g-tap-min)');
	});
});
