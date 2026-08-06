// Adversary-Fund F001 (fix-923b, docs/artifacts/fix-923b-wire-live-sms-preview/adversary-dialog.md):
// weather_v2_mail_preview_sms_fidelity.test.ts prueft NUR die Blattkomponente
// WeatherV2MailPreview.svelte isoliert mit explizit gesetztem context-Prop —
// das umgeht die Verdrahtungsstelle in WeatherMetricsTab.svelte (die beiden
// `{context}`-Weitergaben, Zeile ~1167 Desktop-Snippet / ~1426 Mobile-Sheet),
// die #923 urspruenglich kaputt gemacht hatte. Dieser Test rendert
// WeatherMetricsTab.svelte SELBST per SSR mit context='vergleich' und prueft
// auf Ebene der tatsaechlich live gerenderten Elternkomponente, dass die
// SMS-Vorschau nicht erscheint.
//
// Mutations-Gegenprobe (dokumentiert, s. u. im Kommentarblock "Ergebnis der
// Gegenprobe"): das Entfernen der `{context}`-Weitergabe an beiden Stellen in
// WeatherMetricsTab.svelte aendert die HTML-Ausgabe fuer context='vergleich'
// NICHT (byte-identisch) — WeatherV2MailPreview wird im vergleich-Zweig
// ueberhaupt nicht instanziiert (der komplette Block mit LayoutTab/
// WeatherV2MailPreview/Mobile-Sheet steht im `{:else}`-Zweig des aeusseren
// `{#if context === 'vergleich'} ... {:else if ...} ... {:else} ... {/if}`,
// WeatherMetricsTab.svelte:908-1458). Die von F001 beschriebene Verfaelschung
// ist damit STRUKTURELL unerreichbar -- kein Verhaltenstest kann sie fangen,
// weil sie keine beobachtbare Wirkung hat. Dieser Test bewacht stattdessen
// den TATSAECHLICH wirksamen Schutzmechanismus (den aeusseren Kontext-Gate)
// und faengt jede kuenftige Aenderung, die WeatherV2MailPreview im
// vergleich-Zweig ueberhaupt erreichbar macht.
//
// Echtes serverseitiges Rendern der echten Svelte-Komponente (svelte/server
// `render`). Keine Mocks, keine reine Datei-Inhalt-Pruefung.
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/weather_metrics_tab_vergleich_no_sms_preview.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> shared -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');

// $app/environment-Stub VOR den bestehenden SSR-Hooks einhaengen — der
// Komponentenbaum von WeatherMetricsTab.svelte importiert transitiv
// mobile/Sheet.svelte ($app/environment), das reine SvelteKit-Build-Alias
// ist und unter Node ohne Stub mit ERR_MODULE_NOT_FOUND scheitert.
register(
	pathToFileURL(path.join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);
register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const WeatherMetricsTab = (
	await import(
		pathToFileURL(path.join(FRONTEND, 'src/lib/components/shared/WeatherMetricsTab.svelte')).href
	)
).default;

describe('AC-3/F001: WeatherMetricsTab context="vergleich" rendert die SMS-Vorschau nicht', () => {
	test('weder data-testid="wm2-sms-line" noch die WeatherV2MailPreview-Huelle "wm2-mail-preview" erscheinen im DOM', () => {
		const html = render(WeatherMetricsTab, { props: { context: 'vergleich' } }).body;

		assert.ok(
			html.includes('data-testid="weather-metrics-tab-vergleich"'),
			`Vergleich-Zweig wurde nicht gerendert — Test-Setup fehlerhaft. HTML: "${html}"`
		);
		assert.ok(
			!html.includes('data-testid="wm2-sms-line"'),
			`F001: SMS-Vorschau-Kachel darf bei context='vergleich' NICHT erscheinen. HTML: "${html}"`
		);
		assert.ok(
			!html.includes('wm2-mail-preview'),
			`F001: WeatherV2MailPreview darf bei context='vergleich' ueberhaupt nicht instanziiert werden ` +
				`(kein Server-Aufruf, keine Attrappe). HTML: "${html}"`
		);
	});
});
