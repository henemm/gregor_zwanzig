// Issue #2520 AC-9 — die Startseite `/` darf nie in die Positivliste des Service
// Workers fallen (sonst koennte ein nutzerbezogener Stand unter `/` abgelegt werden).
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test src/lib/pwa/ansicht.test.ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { ansichtVon } from './ansicht.ts';

test('AC-9: `/` und `/__data.json` gehoeren zu keiner Ansicht (Regel 3: nur Netz, nie ablegen)', () => {
	for (const p of ['/', '/__data.json', '/archiv', '/trips', '/trips/new', '/compare/new', '/landing/alarm.png']) {
		assert.equal(ansichtVon(p), null, p);
	}
});

test('AC-9: Gegenprobe, echte Ansichten bleiben in der Positivliste', () => {
	assert.equal(ansichtVon('/trips/abc'), '/trips/abc');
	assert.equal(ansichtVon('/compare/x/__data.json'), '/compare/x');
});

// doc-compliance-test
test('AC-9: der Service Worker nutzt genau diese Funktion', () => {
	const dir = dirname(fileURLToPath(import.meta.url));
	const sw = readFileSync(join(dir, '..', '..', 'service-worker.ts'), 'utf-8');
	assert.match(sw, /import \{[^}]*ansichtVon[^}]*\} from '\.\/lib\/pwa\/ansicht\.ts'/);
	assert.doesNotMatch(sw, /function ansichtVon/);
});
