// TDD RED — Issue #1738: "Premium-SMS-Schalter verschwindet auf /trips/new,
// wenn die SMS-Wetter-Metrik ausgeblendet wird."
// Spec: docs/specs/modules/fix_1738_trips_new_versand_tab.md — AC-1, AC-2, AC-3.
//
// NUTZERSICHT: Wer im Metriken-Tab einen Wetter-Kanal abwaehlt, verliert im
// Zeitplan-Tab den Zugang zum zugehoerigen VERSAND-Kanal — bei Premium-SMS
// doppelt verschachtelt (die frühere Report-Config-Section (#2277 S5 entfernt)). Premium-SMS
// ist auf der Huette der einzige empfangbare Kanal (ADR-0049).
//
// #3332 (D1 von #3307, Spec feat_3332_zustellung_anlegen_trip.md, AC-1): im Schritt Zustellung des
// Trip-Anlegens steht der Reiter Zustellung (wie im Hub) statt des Alt-Panels. Die Zusicherungen gelten
// fuer seine Kanal-Tabelle: vier Kanalzeilen, unabhaengig von den Wetter-Kanaelen (`display_config.channels`),
// und gesetzte Briefing-Kanaele bleiben angehakt.
//
// Gemessen wird am ECHTEN serverseitigen Render (svelte/server): der Anlege-Seite (Reiter, Briefing-Zeiten,
// Abschnitt Kanaele) und der echten KanalTabelle — Letztere erscheint im Reiter erst nach dem Profil-Abruf
// (onMount, im Server-Render nie) und wird deshalb mit dem Startstand gerendert, den der Reiter aus dem
// Eintrittstrip liest (standAusTrip — derselbe Trip-Rahmen wie im Editor: Wetter-Kanaele in display_config,
// Versand-Blob in report_config). Renderharness + Test-Seam: ./tripNewSsr.ts.
//
// Ausfuehrung:
//   cd frontend && npm test -- src/lib/components/trip-new/__tests__/trip_new_versandkanaele_unabhaengig_von_metriken.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { renderTripNew, assertTabOffen, countTestid, outerHtml, FRONTEND } from './tripNewSsr.ts';
import { buildCreateTripPayload } from '../tripNewLogic.ts';
import { kanalStatus, standAusTrip } from '../../shared/zustellung-tab/zustellungModell.ts';

type WetterKanaele = { email: boolean; telegram: boolean; sms: boolean };

const KANAELE = ['email', 'telegram', 'sms', 'premium_sms'] as const;
const KANAL_ZEILEN = KANAELE.map((k) => `zustellung-kanal-${k}`);

const { render } = await import('svelte/server');
const KanalTabelle = (await import(pathToFileURL(join(FRONTEND, 'src/lib/components/organisms/zustellung-tab/KanalTabelle.svelte')).href)).default;
/** Profil mit verbundenen Kanaelen (E-Mail, Telegram, bestaetigte SMS, Premium-Tarif). */
const PROFIL = { mail_to: 'a@example.com', email_verified: true, telegram_chat_id: 'c', sms_to: '+491700000000', sms_verified: true, sms_allowed: true, premium_sms_allowed: true };

/** /trips/new mit offenem Schritt Zustellung, breite Ansicht. */
function zeitplan(channels: WetterKanaele, reportConfig?: Record<string, unknown>): string {
	const html = renderTripNew({ activeTab: 'zustellung', isMobileViewport: false, channels, reportConfig, wtVisited: true, zuVisited: true, name: 'X', startDate: '2026-09-01', stageNames: ['E1'] });
	assertTabOffen(html, 'zustellung');
	return html;
}

/** Echte Kanal-Tabelle mit dem Startstand des Reiters fuer diesen Trip-Rahmen. */
function kanalTabelle(channels: WetterKanaele, reportConfig?: Record<string, unknown>): string {
	const stand = standAusTrip({ id: '__new__', name: 'x', stages: [], display_config: { channels, metrics: [] }, report_config: reportConfig } as never);
	return render(KanalTabelle, { props: { stand, status: kanalStatus(PROFIL as never), onaendern: () => {} } }).body;
}

const ALLE_AN: WetterKanaele = { email: true, telegram: true, sms: true };

// ─── AC-1 ────────────────────────────────────────────────────────────────────

describe('AC-1: Premium-SMS bleibt erreichbar, wenn der Wetter-Kanal SMS abgewaehlt ist', () => {
	test('premium_sms_zeile_ueberlebt_abgewaehlten_wetterkanal_sms', () => {
		const ohneSms = kanalTabelle({ email: true, telegram: true, sms: false });

		assert.equal(
			countTestid(ohneSms, 'zustellung-kanal-premium_sms'),
			1,
			'AC-1: Mit abgewaehltem Wetter-Kanal SMS fehlt die Premium-SMS-Zeile in der Kanal-Tabelle. ' +
				'Eine Anzeige-Einstellung fuer Wetter-Metriken versteckt damit den einzigen Kanal, ' +
				'der auf der Huette ankommt (ADR-0049).'
		);
	});

	test('premium_sms_schaltbarkeit_haengt_nicht_an_der_metrik_auswahl', () => {
		// Gegenprobe statt absoluter Behauptung: ob der Schalter bedienbar ist, entscheidet das
		// Tarif-/Rueckadress-Profil — NICHT die Metrik-Auswahl. Also muss er in beiden Faellen gleich sein.
		const mitSms = kanalTabelle(ALLE_AN);
		const ohneSms = kanalTabelle({ email: true, telegram: true, sms: false });
		assert.equal(
			outerHtml(ohneSms, 'zustellung-kanal-premium_sms-briefing'),
			outerHtml(mitSms, 'zustellung-kanal-premium_sms-briefing'),
			'AC-1: Die Bedienbarkeit des Premium-SMS-Schalters aendert sich mit der ' +
				'Wetter-Metrik-Auswahl — sie darf nur vom Profil abhaengen.'
		);
	});
});

// ─── AC-2 ────────────────────────────────────────────────────────────────────

describe('AC-2: alle vier Versandkanaele sind von jeder Metrik-Auswahl unabhaengig', () => {
	const KOMBINATIONEN: Array<[string, WetterKanaele]> = [
		['alle Wetter-Kanaele an', ALLE_AN],
		['E-Mail abgewaehlt', { email: false, telegram: true, sms: true }],
		['Telegram abgewaehlt', { email: true, telegram: false, sms: true }],
		['SMS abgewaehlt', { email: true, telegram: true, sms: false }],
		['alle abgewaehlt', { email: false, telegram: false, sms: false }]
	];

	for (const [name, channels] of KOMBINATIONEN) {
		test(`alle_vier_kanalzeilen_vorhanden__${name.replace(/\W+/g, '_')}`, () => {
			const html = zeitplan(channels);
			assert.equal(html.split('data-abschnitt="kanaele"').length - 1, 1, `AC-2 (${name}): Abschnitt Kanaele des Reiters Zustellung fehlt im Schritt Zustellung.`);
			const tabelle = kanalTabelle(channels);
			for (const testid of KANAL_ZEILEN) {
				assert.equal(
					countTestid(tabelle, testid),
					1,
					`AC-2 (${name}): Die Zeile "${testid}" fehlt in der Kanal-Tabelle (oder steht doppelt ` +
						'darin). Die Sichtbarkeit eines VERSAND-Kanals darf an keiner Metrik-Auswahl ' +
						'haengen.'
				);
			}
		});
	}

	test('zeitplan_bleibt_bedienbar_wenn_kein_wetterkanal_gewaehlt_ist', () => {
		// Positivkontrolle zur Kombination "alle abgewaehlt": die Briefing-Zeiten bleiben im Schritt Zustellung.
		const html = zeitplan({ email: false, telegram: false, sms: false });
		for (const id of ['zustellung-morgen-schalter', 'zustellung-abend-schalter']) {
			assert.equal(
				countTestid(html, id),
				1,
				'AC-2: Ohne aktive Wetter-Metrik-Kanaele verschwindet der Briefing-Zeitplan aus dem ' +
					'Schritt Zustellung — das Metrik-Gating darf den Versand-Bereich nicht abschalten.'
			);
		}
	});
});

// ─── AC-3 ────────────────────────────────────────────────────────────────────

describe('AC-3: gesetzte Versandkanaele bleiben gesetzt, egal welche Wetter-Kanaele aktiv sind', () => {
	test('angehakte_kanaele_werden_beim_rendern_nicht_still_zurueckgesetzt', () => {
		const html = kanalTabelle(
			{ email: false, telegram: false, sms: false },
			{ send_email: true, send_telegram: true, send_sms: true, send_premium_sms: true }
		);

		for (const k of KANAELE) {
			const schalter = outerHtml(html, `zustellung-kanal-${k}-briefing`);
			// Premium: nur ein verbundenes Geraet ist bedienbar — gesperrt heisst „aus", unabhaengig vom Blob.
			if (/aria-disabled="true"|disabled/.test(schalter)) continue;
			assert.match(
				schalter,
				/aria-checked="true"/,
				`AC-3: "${k}" ist in report_config eingeschaltet, wird aber nicht angehakt ` +
					'gerendert. Der Nutzer sieht einen Kanal als aus, den er eingeschaltet hat.'
			);
		}
		for (const k of ['email', 'telegram', 'sms'] as const)
			assert.match(outerHtml(html, `zustellung-kanal-${k}-briefing`), /aria-checked="true"/, `AC-3: Messaufbau — ${k} muss bedienbar und an sein`);
	});

	test('speicher_payload_traegt_send_premium_sms_unabhaengig_von_den_wetterkanaelen', () => {
		// Zweite Haelfte derselben Zusicherung, eine Ebene tiefer: der
		// Speicher-Payload. Diese Haelfte ist heute bereits gruen — der
		// Payload-Bauer hat nie auf Kanaele gefiltert. Sie steht hier als
		// Gegenprobe, damit ein kuenftiges Gating im Speicherpfad auffliegt.
		const payload = buildCreateTripPayload({
			name: 'Karnischer Hoehenweg',
			startDate: '2026-09-01',
			stages: [{ id: 1, name: 'Etappe 1' }],
			channels: { email: false, telegram: false, sms: false },
			reportConfig: { send_premium_sms: true }
		});

		assert.equal(
			payload.report_config?.send_premium_sms,
			true,
			'AC-3: send_premium_sms erreicht den angelegten Trip nicht, obwohl der Schalter gesetzt ist.'
		);
	});
});
