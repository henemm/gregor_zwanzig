// Fix-Loop 1 fuer #1745 Scheibe A — Adversary-Finding F001 (HIGH):
// compareWizardState.svelte.ts:129 (`sendPremiumSms: this.sendPremiumSms,`
// in saveNewPreset()) hatte KEINE Testabdeckung. AC-11
// (compare_new_preset_payload.test.ts) prueft nur die reine Funktion
// `buildNewComparePresetPayload()`, nicht ihren Aufrufer -- die Stelle, an
// der der Wizard-Zustand tatsaechlich in den POST-Body gefuettert wird
// ("Pruefort != Wirkort"). Ungeschuetzt blieb der realistischere Fall: die
// Zeile steht da, speist aber den FALSCHEN Wert (hart `false`, oder
// versehentlich `this.sendSms`) -- genau das faengt dieser Test.
//
// Technik (kein Mock-Theater): CompareWizardState.svelte.ts nutzt Svelte-5-
// Runen (`$state()`), die nur der Svelte-Compiler auflöst -- ausserhalb
// eines Kompilat-Kontexts wirft `new CompareWizardState()` sofort
// "$state is not defined" (siehe compare_hub_wizard_bridge.test.ts:26-30,
// dortige Praezedenz vermeidet Instanziierung deshalb ganz). Dieser Test
// schimmt `$state` VOR dem Import als reinen Passthrough (kein Reactivity-
// Ersatz noetig -- wir lesen den Feldwert nur direkt nach dem Setzen,
// unmittelbar vor dem Methodenaufruf). Zusaetzlich ist `$app/navigation`
// eine SvelteKit-virtuelle Ausgabe, die es ausserhalb von SvelteKit/vite gar
// nicht gibt -- ein lokaler node:module-Resolve-Hook (nur in diesem
// Testprozess, `node --test` isoliert jede Testdatei in einem eigenen
// Kindprozess) macht den Specifier ueberhaupt auflösbar, danach ersetzt
// `mock.module()` (`--experimental-test-module-mocks`, Praezedenz:
// alertPresetThresholdDisplay.test.ts) NUR die beiden Ausgabekanaele
// (HTTP-POST, Navigation) durch Spione. Gemessen wird der ECHTE, von
// `saveNewPreset()` gebaute POST-Body -- kein gespiegeltes Soll.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/compare/__tests__/compare_wizard_save_new_preset_channels.test.ts

import { test, mock } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';

// `$app/navigation` existiert ausserhalb von SvelteKit/vite nicht als
// resolvbarer Specifier -- `mock.module()` versucht dennoch, den Specifier
// ERST regulaer aufzuloesen (bevor es ihn ersetzt) und scheitert sonst mit
// ERR_MODULE_NOT_FOUND ("Cannot find package '$app'"). Dieser winzige, nur
// in diesem Testprozess registrierte Hook macht ihn ueberhaupt auflösbar;
// `mock.module()` unten ersetzt den Inhalt vollstaendig.
const appNavigationStubHook = `
export async function resolve(specifier, context, nextResolve) {
	if (specifier === '$app/navigation') {
		return { url: 'data:text/javascript,export function goto(){}', shortCircuit: true };
	}
	return nextResolve(specifier, context);
}
`;
register(`data:text/javascript,${encodeURIComponent(appNavigationStubHook)}`, import.meta.url);

// Muss VOR dem Import von compareWizardState.svelte.ts stehen -- die
// $state()-Aufrufe laufen als Klassenfeld-Initializer beim `new`, aber der
// Bezeichner `$state` wird bereits beim Modul-Laden im Scope gesucht.
(globalThis as unknown as { $state: <T>(v: T) => T }).$state = <T>(v: T): T => v;

const { CompareWizardState } = await import('../compareWizardState.svelte.ts');

/** Instanziiert CompareWizardState und fuehrt saveNewPreset() gegen
 *  gespionte $lib/api + $app/navigation aus. Liefert den tatsaechlich
 *  gesendeten POST-Body. */
async function runSaveNewPreset(sendPremiumSms: boolean): Promise<Record<string, unknown>> {
	let capturedBody: Record<string, unknown> | null = null;
	const apiMock = mock.module('$lib/api', {
		namedExports: {
			api: {
				post: async (_path: string, body: unknown) => {
					capturedBody = body as Record<string, unknown>;
					return { id: 'cmp-test' };
				}
			}
		}
	});
	const navMock = mock.module('$app/navigation', {
		namedExports: { goto: async (_url: string) => undefined }
	});

	try {
		const ws = new CompareWizardState();
		ws.name = 'Testvergleich';
		ws.pickedIds = ['loc-1', 'loc-2'];
		ws.sendPremiumSms = sendPremiumSms;
		await ws.saveNewPreset();
	} finally {
		apiMock.restore();
		navMock.restore();
	}

	assert.ok(capturedBody, 'saveNewPreset() muss api.post() mit einem Body aufrufen');
	return capturedBody as Record<string, unknown>;
}

test('saveNewPreset(): sendPremiumSms=true landet als send_premium_sms:true im tatsaechlich gesendeten POST-Body', async () => {
	const body = await runSaveNewPreset(true);
	assert.strictEqual(
		body.send_premium_sms,
		true,
		`erwartet send_premium_sms:true im gesendeten Body, erhalten: ${JSON.stringify(body.send_premium_sms)}`
	);
});

test('saveNewPreset(): sendPremiumSms=false landet als send_premium_sms:false im tatsaechlich gesendeten POST-Body (Gegenprobe)', async () => {
	const body = await runSaveNewPreset(false);
	assert.strictEqual(
		body.send_premium_sms,
		false,
		`erwartet send_premium_sms:false im gesendeten Body, erhalten: ${JSON.stringify(body.send_premium_sms)}`
	);
});
