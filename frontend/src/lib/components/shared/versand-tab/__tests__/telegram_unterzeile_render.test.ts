// doc-compliance-test (nur der CSS-Kontrast-Test am Ende liest den Quelltext;
// alle anderen Tests sind echte SSR-Renders).
//
// Issue #2455 AC-3 (F001/F002): die Telegram-Unterzeile im Versand-Reiter folgt
// dem Telegram-Stil -- an der Stelle, an der sie WIRKT (gerendertes HTML der
// Komponenten), in BEIDEN Kontexten. Plus F003: Hinweistext des Schalters
// nutzt nie --g-ink-4 (Kontrast, CLAUDE.md Design-Leitprinzipien).
//
// Ausfuehrung: cd frontend && npm test -- src/lib/components/shared/versand-tab/__tests__/telegram_unterzeile_render.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../../..');
register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);
const { render } = await import('svelte/server');
const imp = async (rel: string) => (await import(pathToFileURL(path.join(FRONTEND, rel)).href)).default;
const VTBriefingChannels = await imp('src/lib/components/shared/versand-tab/VTBriefingChannels.svelte');
const VersandTab = await imp('src/lib/components/shared/VersandTab.svelte');

const KURZ = 'folgt der SMS-Auswahl';
const RICH = /Layout · \d+ Spalten/;

function channels(context: 'route' | 'vergleich', telegramStyle: 'rich' | 'kurzform'): string {
	return render(VTBriefingChannels, {
		props: {
			context,
			channels: { email: false, telegram: true, sms: false, premium_sms: false },
			onEmailChange: () => {}, onTelegramChange: () => {}, onSmsChange: () => {},
			telegramStyle, profileOverride: null
		}
	}).body;
}

describe('#2455 AC-3: VTBriefingChannels reicht den Stil in die Unterzeile', () => {
	for (const ctx of ['route', 'vergleich'] as const) {
		test(`${ctx}: kurzform -> "${KURZ}", rich -> Layout · N Spalten`, () => {
			const k = channels(ctx, 'kurzform');
			assert.ok(k.includes(KURZ));
			assert.doesNotMatch(k, RICH);
			const r = channels(ctx, 'rich');
			assert.match(r, RICH);
			assert.ok(!r.includes(KURZ));
		});
	}
});

describe('#2455 F002: VersandTab-Vergleich zeigt den Kurzform-Status (nur lesend)', () => {
	function vergleich(stil?: 'rich' | 'kurzform'): string {
		return render(VersandTab, {
			props: { context: 'vergleich', sendTelegram: true, vergleichTelegramStyle: stil }
		}).body;
	}
	test('kurzform -> Unterzeile verweist auf SMS-Auswahl, KEIN zweiter Schalter', () => {
		const html = vergleich('kurzform');
		assert.ok(html.includes(KURZ));
		assert.ok(!html.includes('Telegram im SMS-Kurzstil'), 'Schalter bleibt im Alarme-Reiter');
	});
	test('rich bzw. ohne Angabe -> Layout · N Spalten', () => {
		assert.match(vergleich('rich'), RICH);
		assert.match(vergleich(), RICH);
	});
});

describe('#2455 F003: Hinweisfarbe des Schalters', () => {
	test('.tks-sub nutzt --g-ink-3, nie --g-ink-4', () => {
		const src = readFileSync(path.join(FRONTEND, 'src/lib/components/shared/TelegramKurzstilToggle.svelte'), 'utf-8');
		const block = src.match(/\.tks-sub\s*\{([^}]*)\}/);
		assert.ok(block, '.tks-sub-Regel fehlt');
		assert.match(block![1], /color:\s*var\(--g-ink-3\)/);
		assert.ok(!block![1].includes('--g-ink-4'));
	});
});
