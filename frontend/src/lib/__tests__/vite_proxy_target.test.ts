// TDD RED — Issue #1284 (Spec docs/specs/modules/fix_1284_admin_prod_testdata.md,
// Test Plan Test 5 / AC-2, AC-4).
//
// Prüft das TATSÄCHLICH AUFGELÖSTE Proxy-Ziel der Vite-Konfiguration
// (`server.proxy['/api'].target`) gegen die geteilte Konstante aus
// `frontend/e2e/apiProxyTarget.ts` -- kein Dateiinhalt-Grep auf das Literal
// "8090" (Test-Politik, CLAUDE.md "Zwei Schichten").
//
// `frontend/vite.config.ts` exportiert `defineConfig({...})` als reines
// Objekt (keine Funktions-Form) -- ein direkter Import unter
// `--experimental-strip-types` funktioniert (verifiziert vor dem Schreiben
// dieses Tests: `node --import ./test-lib-loader.mjs
// --experimental-strip-types -e "import('./vite.config.ts')..."` liefert
// `typeof default === 'object'`). Die Rückfallebene aus der Spec
// (Source-Scan bei Funktions-Form) ist damit NICHT nötig.
//
// Dieser Test ist ABSICHTLICH ROT: `frontend/e2e/apiProxyTarget.ts`
// existiert noch nicht -> ERR_MODULE_NOT_FOUND beim Import.
//
// Ausführen (aus frontend/):
//   npm test -- "src/lib/__tests__/vite_proxy_target.test.ts"

import { test } from 'node:test';
import assert from 'node:assert/strict';

import viteConfig from '../../../vite.config.ts';
import { API_PROXY_TARGET } from '../../../e2e/apiProxyTarget.ts';

test('#1284 Test 5: aufgelöstes /api-Proxy-Ziel entspricht der geteilten Konstante und ist nicht Prod-Port 8090', () => {
	const config =
		typeof viteConfig === 'function'
			? viteConfig({ command: 'serve', mode: 'development' })
			: viteConfig;

	const resolvedTarget = config?.server?.proxy?.['/api']?.target;

	assert.equal(
		resolvedTarget,
		API_PROXY_TARGET,
		`Aufgelöstes Proxy-Ziel (${resolvedTarget}) weicht von der geteilten Konstante ` +
			`API_PROXY_TARGET (${API_PROXY_TARGET}) ab -- vite.config.ts und der Guard ` +
			`müssen dieselbe Quelle importieren, keine Kopie.`
	);
	assert.notEqual(
		resolvedTarget,
		'http://localhost:8090',
		'Aufgelöstes Proxy-Ziel zeigt auf den Prod-Go-Server (Port 8090) -- ' +
			'Standard-Playwright-Läufe müssen gegen Staging (8091) proxyen (#1284 AC-2).'
	);
});
