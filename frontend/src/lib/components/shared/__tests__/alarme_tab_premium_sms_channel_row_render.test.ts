// TDD RED — Issue #1745 Scheibe A (AC-1): die vierte Kanalzeile erscheint in
// BEIDEN Flächen — Trip-Alarme-Reiter (context="route") UND Ortsvergleich
// (context="vergleich"). Keine ist gegenüber der anderen eingeschränkt.
// Spec: docs/specs/modules/fix_1745_a_alarm_kanal_premium_sms_ui.md (AC-1, D6, D3)
//
// WARUM SSR UND NICHT NUR DIE KONSTANTE: `ALERT_CHANNEL_ORDER` ist die Quelle
// der Zeilen, aber nicht ihr Wirkort. Ein `{#if context === 'route'}` um die
// `channels`-Sektion (der Fehler, den ADR-0049 im VERSAND-Reiter verlangt und
// der hier ein Fehler wäre, s. D6) bliebe an der Konstante unsichtbar. Deshalb
// wird die echte Komponente serverseitig gerendert (svelte/server, Hooks:
// frontend/test-svelte-ssr-hooks.mjs) — kein Mock, kein Datei-Grep.
//
// 🔴 SSR FÜHRT `onMount` NIE AUS. Der Tarif-Zustand entsteht aber genau dort
// (Profil-Fetch). Ein SSR-Test, der auf den gefetchten Zustand prüft, wäre
// strukturell immer grün und bewachte nichts (#1717, dort einmal passiert).
// Deshalb nutzen die Sperr-Prüfungen unten den Testhaken `profileOverride`
// (Muster VTBriefingChannels.svelte:60,74,82) — die Spec sieht ihn für
// AlarmeTab ausdrücklich vor.
//
// RED HEUTE: `alert-channel-row-premium_sms` existiert in keinem der beiden
// Kontexte (ALERT_CHANNEL_ORDER ist dreiwertig); `profileOverride` ist noch
// keine Prop von AlarmeTab.
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei auflösen.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/alarme_tab_premium_sms_channel_row_render.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> shared -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');

register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const AlarmeTab = (
	await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/shared/AlarmeTab.svelte')).href)
).default;

const TRIP = {
	id: 'trip-1745-a',
	name: 'KHW 403',
	stages: [],
	alert_rules: [],
	display_config: {},
	report_config: { send_email: true, send_telegram: true, send_sms: true }
};

/** Wizard-Stellvertreter mit exakt den Feldern, die AlarmeTab im
 *  vergleich-Zweig liest (CompareWizardState-Formen, plain object — SSR
 *  braucht keine Runen). */
function wizStub(overrides: Record<string, unknown> = {}): Record<string, unknown> {
	return {
		officialWarningsEnabled: true,
		radarAlertEnabled: false,
		activeMetricKeys: null,
		metricAlertLevels: {},
		sendTelegram: true,
		sendSms: false,
		sendPremiumSms: false,
		channelThresholds: {},
		telegramStyle: 'rich',
		alertCooldownMinutes: 30,
		alertQuietFrom: '22:00',
		alertQuietTo: '07:00',
		...overrides
	};
}

/** Profil mit Premium-Tarif — Premium-SMS ist damit schaltbar (AC-6/D2). */
const PREMIUM = { premium_sms_allowed: true };
/** Profil mit Tarif `standard` — Zeile sichtbar, aber gesperrt (AC-5/D3). */
const STANDARD = { premium_sms_allowed: false };

function renderRoute(profileOverride: unknown): string {
	return render(AlarmeTab, {
		props: {
			context: 'route',
			trip: TRIP,
			activeMetrics: [],
			metricLevels: {},
			existingChannels: { email: true, telegram: true, sms: true, premium_sms: false },
			profileOverride
		}
	}).body;
}

function renderVergleich(profileOverride: unknown, wizOverrides: Record<string, unknown> = {}): string {
	return render(AlarmeTab, {
		props: {
			context: 'vergleich',
			wiz: wizStub(wizOverrides),
			catalog: [],
			profileOverride
		}
	}).body;
}

const ROW = (kind: string) => `data-testid="alert-channel-row-${kind}"`;

/** Fragment vom Zeilen-Marker bis zum nächsten Zeilen-Marker (bzw. Ende). */
function rowFragment(html: string, kind: string): string {
	const start = html.indexOf(ROW(kind));
	assert.notEqual(
		start,
		-1,
		`Die Kanalzeile "${kind}" fehlt im gerenderten HTML — gefundene Zeilen: ` +
			JSON.stringify([...html.matchAll(/data-testid="alert-channel-row-([a-z_]+)"/g)].map((m) => m[1]))
	);
	const next = html.indexOf('data-testid="alert-channel-row-', start + 1);
	return html.slice(start, next === -1 ? html.length : next);
}

// ─────────────────────────────────────────────────────────────────────────────
// AC-1 — beide Kontexte, dieselbe Zeile, nach SMS.
// Mutation (Spec): ALERT_CHANNEL_ORDER bleibt dreiwertig ODER die
// `channels`-Sektion wird für `vergleich` hinter ein {#if} gestellt.
// ─────────────────────────────────────────────────────────────────────────────
describe('#1745 AC-1: beide_kontexte_zeigen_premium_sms_zeile', () => {
	test('beide_kontexte_zeigen_premium_sms_zeile', () => {
		for (const [label, html] of [
			['route (Trip-Alarme-Reiter)', renderRoute(PREMIUM)],
			['vergleich (Ortsvergleich)', renderVergleich(PREMIUM)]
		] as const) {
			assert.ok(
				html.includes(ROW('premium_sms')),
				`${label}: Die Kanalzeile "premium_sms" fehlt. Ohne sie erreicht KEIN Alarm das ` +
					'Garmin-Gerät, obwohl das Backend seit #1701 sendebereit ist.'
			);
			assert.ok(
				html.indexOf(ROW('premium_sms')) > html.indexOf(ROW('sms')),
				`${label}: Die Premium-SMS-Zeile muss NACH der SMS-Zeile stehen (D5).`
			);
		}
	});

	test('beide_kontexte_zeigen_premium_sms_zeile — der Vergleich ist NICHT eingeschränkt (D6)', () => {
		// Der Versand-Reiter schliesst Premium-SMS für `vergleich` bewusst aus
		// (ADR-0049). Im Alarm-Pfad ist der Kanal ausdrücklich auch für den
		// Vergleich vorgesehen (#1701 AC-4, compare_alert_channels.py:44-45) —
		// ein kopiertes `{#if context === 'route'}` wäre hier ein Fehler, kein
		// Schutz. Gemessen als Gleichheit der Zeilenmengen beider Kontexte.
		const zeilen = (html: string) =>
			[...html.matchAll(/data-testid="alert-channel-row-([a-z_]+)"/g)].map((m) => m[1]);
		// Sollwert (Spec D5, wie in alarme_alert_channel_defaults.test.ts korrigiert):
		// premium_sms steht DIREKT unter sms, VOR email.
		const erwartet = ['telegram', 'sms', 'premium_sms', 'email'];

		// Gegen den Ist-Zustand geprüft, nicht gegeneinander: ein Vergleich der
		// beiden Kontexte allein wäre heute (drei Zeilen hier wie dort) grün und
		// bewachte nichts.
		assert.deepEqual(
			zeilen(renderRoute(PREMIUM)),
			erwartet,
			'Trip-Alarme-Reiter: Kanalzeilen unvollständig oder in falscher Reihenfolge.'
		);
		assert.deepEqual(
			zeilen(renderVergleich(PREMIUM)),
			erwartet,
			'Ortsvergleich: Kanalzeilen unvollständig — ein kopiertes `{#if context === "route"}` ' +
				'wäre hier ein Fehler, kein Schutz (D6, #1701 AC-4).'
		);
	});

	test('beide_kontexte_zeigen_premium_sms_zeile — der Haken spiegelt den Ist-Zustand je Fläche', () => {
		// Trip: aus `existingChannels`; Vergleich: aus `wiz.sendPremiumSms`.
		// Ohne diese Verdrahtung zeigte die Zeile im Vergleich dauerhaft „aus",
		// egal was gespeichert ist (der gemeldete Bug in neuer Form).
		const anHtml = rowFragment(renderVergleich(PREMIUM, { sendPremiumSms: true }), 'premium_sms');
		const ausHtml = rowFragment(renderVergleich(PREMIUM, { sendPremiumSms: false }), 'premium_sms');

		assert.match(
			anHtml,
			/aria-checked="true"/,
			'Ein im Vergleich gespeichertes `send_premium_sms: true` muss als gesetzter Haken erscheinen.'
		);
		assert.match(ausHtml, /aria-checked="false"/);
	});
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-5/AC-13 am WIRKORT: die Sperre entscheidet sich in der gerenderten Zeile,
// nicht nur in der reinen Funktion (die prüft premiumSmsAlarmGate.test.ts).
// D3: gesperrt heisst SICHTBAR und gesperrt, nicht versteckt.
// ─────────────────────────────────────────────────────────────────────────────
describe('#1745 AC-5/AC-13: die Premium-SMS-Zeile ist sichtbar und je nach Tarif gesperrt', () => {
	test('Tarif standard: Zeile sichtbar, Schalter gesperrt (nicht versteckt)', () => {
		for (const [label, html] of [
			['route', renderRoute(STANDARD)],
			['vergleich', renderVergleich(STANDARD)]
		] as const) {
			const fragment = rowFragment(html, 'premium_sms');
			assert.match(
				fragment,
				/aria-disabled="true"/,
				`${label}: Ohne Premium-Tarif muss der Schalter gesperrt sein (das Tarif-Gate sitzt ` +
					'serverseitig, user_tier.py:33) — ein klickbarer Haken wäre vorgespiegelte Kontrolle.'
			);
		}
	});

	test('Tarif premium: derselbe Schalter ist bedienbar (Gegenprobe)', () => {
		for (const [label, html] of [
			['route', renderRoute(PREMIUM)],
			['vergleich', renderVergleich(PREMIUM)]
		] as const) {
			const fragment = rowFragment(html, 'premium_sms');
			assert.ok(
				!/aria-disabled="true"/.test(fragment),
				`${label}: Mit Premium-Tarif darf der Schalter NICHT gesperrt sein — sonst wäre die ` +
					'Sperre eine Konstante und keine Tarif-Entscheidung.'
			);
		}
	});

	test('AC-13: ohne Tarif-Auskunft (profileOverride=null, der SSR-/Erstframe-Zustand) gesperrt', () => {
		const fragment = rowFragment(renderRoute(null), 'premium_sms');
		assert.match(
			fragment,
			/aria-disabled="true"/,
			'Solange die Tarif-Auskunft aussteht, muss die Zeile fail-closed gesperrt sein — sonst ' +
				'liesse sich ein Haken setzen und speichern, der serverseitig nie wirkt.'
		);
	});

	test('AC-5: die drei Bestandskanäle bleiben von der Tarif-Sperre unberührt', () => {
		// Kollateralschaden-Gegenprobe: eine pauschal auf alle Zeilen gelegte
		// Sperre würde den Tarif-Test oben ebenfalls bestehen.
		const html = renderRoute(STANDARD);
		for (const kind of ['telegram', 'sms', 'email']) {
			assert.ok(
				!/aria-disabled="true"/.test(rowFragment(html, kind)),
				`Der Kanal "${kind}" darf durch das Premium-SMS-Tarif-Gate nicht mitgesperrt werden.`
			);
		}
	});
});
