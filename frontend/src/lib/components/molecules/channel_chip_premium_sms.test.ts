// Issue #2422 S3 — ChannelChip zeigt Premium-SMS gleichrangig zu E-Mail,
// Telegram und SMS (eigenes Glyph statt Rueckfall '·'). Die Briefing-Zeilen der
// Startseite (BriefingTimelineRow) erhalten seit S3 `'premium-sms'` aus
// `reportChannels`.
//
// Kein Mock: echter Helfer `channelGlyph` (Modul-Export) und echter SSR-Render.
// Pfadregel #1409: Pfade relativ zu DIESER Datei.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/molecules/channel_chip_premium_sms.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// molecules -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../..');

register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

async function ladeChip() {
	return await import(pathToFileURL(path.join(HERE, 'ChannelChip.svelte')).href);
}

describe('ChannelChip — Premium-SMS als vierter Kanal', () => {
	test('channelGlyph: alle vier Kanaele haben ein eigenes, unterscheidbares Glyph', async () => {
		const { channelGlyph } = await ladeChip();
		const glyphen = ['email', 'telegram', 'sms', 'premium-sms'].map((k) => channelGlyph(k));
		assert.notEqual(channelGlyph('premium-sms'), '·', 'Premium-SMS faellt auf das Unbekannt-Glyph zurueck');
		assert.equal(new Set(glyphen).size, 4, `Glyphen nicht unterscheidbar: ${glyphen.join(' ')}`);
	});

	test('SSR: Chip fuer premium-sms zeigt Glyph und Beschriftung', async () => {
		const { render } = await import('svelte/server');
		const mod = await ladeChip();
		const html = render(mod.default, { props: { kind: 'premium-sms' } }).body;
		assert.ok(html.includes(mod.channelGlyph('premium-sms')), 'Glyph fehlt im Chip');
		assert.ok(!html.includes('<span>·</span>'), 'Chip zeigt das Unbekannt-Glyph');
		assert.ok(html.includes('premium-sms'), 'Beschriftung fehlt im Chip');
	});
});
