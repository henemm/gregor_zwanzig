// TDD RED — Issue #1726 (AC-11): die Ruhezeit-Karte benennt ihre Zeit-Basis,
// und zwar KONTEXTABHÄNGIG — beim Trip „Ortszeit der Tour", beim Ortsvergleich
// „Ortszeit des ersten Orts". Heute nennt sie gar keine Zone; ehrlich wäre
// derzeit „Wiener Zeit" (Kontext-Dokument, Risiko 10).
//
// Spec: docs/specs/modules/fix_1726_ruhezeit_und_zaehler_ortszone.md (AC-11, E)
//
// WARUM AlarmeTab UND NICHT NUR DIE KARTE: `AlertQuietHoursCard.svelte` ist der
// Ort, an dem der Text steht — aber NICHT der Ort, an dem über den Kontext
// entschieden wird. Das passiert an den beiden Mount-Punkten
// (`shared/AlarmeTab.svelte:429/431`). Ein Test, der nur die Karte mit einer
// von Hand gesetzten Prop rendert, wäre auch dann grün, wenn beide Mounts
// denselben Text übergeben — Prüfort ≠ Wirkort. Deshalb wird der geteilte
// Organism serverseitig gerendert (svelte/server, Hooks:
// frontend/test-svelte-ssr-hooks.mjs), einmal je Kontext. Vorbild:
// shared/__tests__/alarme_tab_premium_sms_channel_row_render.test.ts (#1745 A).
//
// 🔴 SSR FÜHRT `onMount` NIE AUS. Der Tarif-Fetch in AlarmeTab läuft dort also
// nicht — `profileOverride` wird deshalb explizit gesetzt (Testhaken aus
// #1745 A), damit der Rendervorgang nicht am fehlenden Profil hängt.
//
// RED HEUTE: `AlertQuietHoursCard` hat keine Prop für die Zonen-Bezeichnung und
// gibt in beiden Kontexten denselben Hinweistext aus — weder „Tour" noch
// „erste" taucht im Kartenbereich auf, und beide Kontexte liefern dieselbe
// Zeichenkette.
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei auflösen.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/alarme_tab_quiet_hours_zone_hinweis.test.ts

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
	id: 'trip-1726',
	name: 'Karnischer Höhenweg',
	stages: [],
	alert_rules: [],
	display_config: {},
	report_config: { send_email: true, send_telegram: true, send_sms: false },
	alert_quiet_from: '22:00',
	alert_quiet_to: '07:00'
};

/** Wizard-Stellvertreter mit den Feldern, die AlarmeTab im vergleich-Zweig
 *  liest (plain object — SSR braucht keine Runen). */
function wizStub(): Record<string, unknown> {
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
		alertQuietTo: '07:00'
	};
}

const PROFIL = { premium_sms_allowed: false };

function renderRoute(): string {
	return render(AlarmeTab, {
		props: {
			context: 'route',
			trip: TRIP,
			activeMetrics: [],
			metricLevels: {},
			existingChannels: { email: true, telegram: true, sms: false },
			profileOverride: PROFIL
		}
	}).body;
}

function renderVergleich(): string {
	return render(AlarmeTab, {
		props: {
			context: 'vergleich',
			wiz: wizStub(),
			catalog: [],
			profileOverride: PROFIL
		}
	}).body;
}

/** Schneidet GENAU den Bereich der Ruhezeit-Karte aus dem gerenderten HTML.
 *
 *  Die Begrenzung ist wichtig, nicht kosmetisch: ein zu grosszügiger Ausschnitt
 *  nimmt die nachfolgende Beispiel-Sektion mit, deren Inhalt sich zwischen den
 *  Kontexten ohnehin unterscheidet — der Vergleich „beide Kontexte liefern
 *  NICHT denselben Text" wäre dann strukturell immer grün und bewachte nichts.
 */
function quietCardHtml(body: string): string {
	const marker = 'data-testid="alert-quiet-hours-card"';
	const start = body.indexOf(marker);
	assert.notEqual(start, -1, 'Die Ruhezeit-Karte fehlt im gerenderten Alarme-Reiter.');
	const next = body.indexOf('class="alarme-section', start);
	return next === -1 ? body.slice(start) : body.slice(start, next);
}

describe('#1726 AC-11 — Ruhezeit-Karte nennt ihre Zonen-Basis', () => {
	test('Trip-Kontext nennt die Ortszeit der Tour', () => {
		const karte = quietCardHtml(renderRoute());

		assert.match(
			karte,
			/Ortszeit/,
			'Im Trip-Kontext muss die Karte sagen, auf welche Ortszeit sich die ' +
				'Ruhezeit bezieht — heute nennt sie gar keine Zone.'
		);
		assert.match(
			karte,
			/Tour/,
			'Beim Trip ist die Bezugsgrösse die Tour ("Ortszeit der Tour").'
		);
	});

	test('Vergleichs-Kontext nennt die Ortszeit des ersten Orts', () => {
		const karte = quietCardHtml(renderVergleich());

		assert.match(
			karte,
			/Ortszeit/,
			'Auch im Ortsvergleich muss die Zeit-Basis benannt sein.'
		);
		assert.match(
			karte,
			/ersten Orts/,
			'Beim Ortsvergleich gilt die Zone des erstgenannten Orts (#1378 AC-4) ' +
				'— genau das muss dort stehen.'
		);
	});

	test('beide Kontexte liefern NICHT denselben Text', () => {
		// Der eigentliche Wirkungsnachweis: ein hart auf einen Kontext
		// verdrahteter Text (die Verfälschung aus der Nachweis-Strategie)
		// fällt hier auf, auch wenn beide Einzelprüfungen oben zufällig
		// zuträfen.
		const route = quietCardHtml(renderRoute());
		const vergleich = quietCardHtml(renderVergleich());

		assert.notEqual(
			route,
			vergleich,
			'Trip und Ortsvergleich beziehen sich auf verschiedene Zonen — der ' +
				'Hinweistext darf nicht in beiden Mounts identisch sein.'
		);
	});
});
