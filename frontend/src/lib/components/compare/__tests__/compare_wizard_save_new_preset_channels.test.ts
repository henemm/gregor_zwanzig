// Fix-Loop 1 fuer #1745 Scheibe A — Adversary-Finding F001 (HIGH): die Stelle, an der der
// Anlege-Zustand `sendPremiumSms` in den POST-Body gefuettert wird, hatte keine Testabdeckung.
// AC-11 (compare_new_preset_payload.test.ts) prueft nur die reine Funktion
// `buildNewComparePresetPayload()`, nicht ihren Aufrufer ("Pruefort != Wirkort"). Ungeschuetzt
// blieb der realistischere Fall: die Zeile steht da, speist aber den FALSCHEN Wert (hart `false`,
// oder versehentlich `sendSms`) — genau das faengt dieser Test.
//
// Issue #1703 Scheibe 8 — zweite Fundstelle: die Kanal-Overrides der Uebersichtstabelle
// (`channelActiveMetricKeys`) muessen im ECHTEN POST-Body ankommen; eine Mutation, die fest
// `{email:null,telegram:null,sms:null}` senden liess, lief frueher durch 38 Tests.
//
// Umgebaut fuer Issue #2727 (Epic #2345, DoD-1) — Spec
// docs/specs/modules/feat_2727_compare_wizardstate_abloesen.md, AC-22: die Zustandsklasse mit
// `saveNewPreset()` ist geloescht, gespeichert wird aus dem Anlege-Editor selbst. Die Zusicherung
// „Kanaele im Anlege-Payload" bleibt erhalten — jetzt am ECHTEN Editor: das Instanz-Skript von
// CompareNewEditor.svelte (compareNeuEditorPruefstand.ts, ohne Context). Die Werte setzt der Test
// so, wie der Nutzer sie setzt: ueber die Rueckrufe der Prop-Buendel, die der Editor selbst an den
// Versand-Abschnitt (`versand={versandPropsAus(…)}`) und den Wetter-Metriken-Reiter
// (`{...wetterMetrikenPropsAus(…)}`) haengt. Gemessen wird der gesendete Koerper an der
// Netzgrenze (fetch) — kein gespiegeltes Soll.
//
// Warum heute rot: der Editor holt seinen Zustand nur per getContext — ohne Context gibt es
// weder Name/Orte noch einen sendbaren Zustand.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/compare/__tests__/compare_wizard_save_new_preset_channels.test.ts

import { test, afterEach, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import type { CompareChannelActiveMetrics } from '../../shared/weather-metrics-tab/compareChannelMetricLayouts.ts';
import {
	VERTRAG_FEHLT_EDITOR,
	buendelAus,
	fetchMitschnitt,
	vergleichEditor
} from '../../shared/__tests__/compareNeuEditorPruefstand.ts';

let netz: ReturnType<typeof fetchMitschnitt>;
beforeEach(() => {
	netz = fetchMitschnitt('cmp-test');
});
afterEach(() => {
	netz.abbauen();
});

/** Legt ueber den echten Editor an; liefert den tatsaechlich gesendeten POST-Body. */
async function anlegen(
	sendPremiumSms: boolean,
	channelActiveMetricKeys?: CompareChannelActiveMetrics
): Promise<Record<string, unknown>> {
	// #2794 S3a: letzter Schritt „Zustellung" (Flags metrikenVisited/zustellungVisited).
	const e = await vergleichEditor({
		stateOverride: {
			activeTab: 'zustellung',
			isMobileViewport: false,
			metrikenVisited: true,
			zustellungVisited: true,
			name: 'Testvergleich',
			pickedIds: ['loc-1', 'loc-2']
		}
	});
	assert.equal(e.u.nameOk, true, VERTRAG_FEHLT_EDITOR);
	(buendelAus(e, 'WetterMetrikenVersandPanel', 'versand').onSendPremiumSmsChange as (an: boolean) => void)(sendPremiumSms);
	if (channelActiveMetricKeys) {
		(buendelAus(e, 'WetterMetrikenVersandPanel').onVergleichsMetrikenChange as (
			a: string[] | null,
			k: CompareChannelActiveMetrics
		) => void)(null, channelActiveMetricKeys);
	}
	await e.u.handleActivate();
	const posts = netz.presetPosts();
	assert.equal(posts.length, 1, `der Editor muss genau einen POST senden, gesehen: ${posts.length}`);
	return posts[0].koerper as Record<string, unknown>;
}

test('Anlegen: sendPremiumSms=true landet als send_premium_sms:true im tatsaechlich gesendeten POST-Body', async () => {
	const body = await anlegen(true);
	assert.strictEqual(
		body.send_premium_sms,
		true,
		`erwartet send_premium_sms:true im gesendeten Body, erhalten: ${JSON.stringify(body.send_premium_sms)}`
	);
	assert.strictEqual(body.send_sms, false, 'Premium-SMS darf nicht ueber das SMS-Feld reisen (Verwechslung)');
});

// Issue #3276 (Spec-AC-38, AC-1): `channel_active_metrics` ist Altschluessel. Vorher: die
// Kanal-Overrides landen im POST-Body (telegram im Speicherformat, sms als [], email fehlt).
// Jetzt: der tatsaechlich gesendete POST-Body traegt den Schluessel in keiner Form.
test('#3276 Anlegen: Kanal-Overrides landen NICHT als display_config.channel_active_metrics im gesendeten POST-Body', async () => {
	const body = await anlegen(false, {
		email: null,
		telegram: ['temp_max_c'],
		sms: []
	});
	const dc = (body.display_config as Record<string, unknown> | undefined) ?? {};
	assert.ok(
		!Object.prototype.hasOwnProperty.call(dc, 'channel_active_metrics'),
		`channel_active_metrics im POST-Body: ${JSON.stringify(dc)}`
	);
});

test('Anlegen: sendPremiumSms=false landet als send_premium_sms:false im tatsaechlich gesendeten POST-Body (Gegenprobe)', async () => {
	const body = await anlegen(false);
	assert.strictEqual(
		body.send_premium_sms,
		false,
		`erwartet send_premium_sms:false im gesendeten Body, erhalten: ${JSON.stringify(body.send_premium_sms)}`
	);
});

test('Anlegen: Alarm-Kanal-Geste im Alarme-Bereich (Schritt Zustellung) landet als alert_channels im POST-Body', async () => {
	const e = await vergleichEditor({
		stateOverride: {
			activeTab: 'zustellung',
			isMobileViewport: false,
			metrikenVisited: true,
			zustellungVisited: true,
			name: 'Testvergleich',
			pickedIds: ['loc-1', 'loc-2']
		}
	});
	assert.equal(e.u.nameOk, true, VERTRAG_FEHLT_EDITOR);
	const vorher = buendelAus(e, 'AlarmeTab').existingChannels as Record<string, boolean>;
	(buendelAus(e, 'AlarmeTab').onChannelToggle as (k: string) => void)('premium_sms');
	await e.u.handleActivate();
	const body = netz.presetPosts()[0]?.koerper as Record<string, unknown>;
	assert.deepEqual(body.alert_channels, { ...vorher, premium_sms: !vorher.premium_sms });
});
