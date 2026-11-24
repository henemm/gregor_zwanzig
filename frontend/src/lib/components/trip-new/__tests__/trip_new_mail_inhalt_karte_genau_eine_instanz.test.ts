// TDD RED — Issue #2277 Scheibe S5: Anlege-Wirkstelle der Mail-Inhalt-Karte.
// Spec: docs/specs/modules/feat_2277_s5_reportconfig_rueckbau.md — AC-3, AC-4, AC-5.
//
// Urspruenglich: die Karte "E-Mail-Inhalt" (report-mail-content) stand auf /trips/new in Desktop UND
// Mobil jeweils genau EINMAL (XOR per isMobileViewport — zwei gleichzeitig gemountete Instanzen hielten
// je einen Schnappschuss von report_config, Last-Write-Wins, Fix-Loop 4 aus #1738).
//
// #3332 (D1 von #3307, Spec feat_3332_zustellung_anlegen_trip.md, AC-10, „an die Hub-Paritaet angepasst"):
// Anlegen = Bearbeiten — der Hub hat keine Mail-Inhalt-Karte, also auch das Trip-Anlegen nicht mehr
// (Soll: 0 Instanzen, in jeder Ansicht und jedem Schritt; damit auch keine zwei Schreiber). E-Mail-Format,
// Etappen-Statistik, Vortagesvergleich und Nacht-Block bedient die Karte „Was steht wo“ im Reiter Wetter
// (Wirkung im POST: trip_anlegen_zustellung_verdrahtung_3332, AC-10). Die Standardfelder der Karte
// entstehen jetzt im Speicherweg (`ergaenzeStandardwerteReportConfig`): ein im Blob gesetzter Wert gewinnt
// dort — das sichern AC-3/AC-5 unten am Speicherweg (Wirkort ist der POST, nicht mehr die Karte).
//
// Ausfuehren:
//   cd frontend && npm test -- src/lib/components/trip-new/__tests__/trip_new_mail_inhalt_karte_genau_eine_instanz.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { parse } from 'svelte/compiler';
import { renderTripNew, countTestid } from './tripNewSsr.ts';
import { buildCreateTripPayload, ergaenzeStandardwerteReportConfig } from '../tripNewLogic.ts';
import { standAusTrip } from '../../shared/zustellung-tab/zustellungModell.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const EDITOR = path.join(HERE, '..', 'TripNewEditor.svelte');
const ALLE_AN = { email: true, telegram: true, sms: true };

// ─── AC-3 (Desktop) / AC-4 (Mobil): keine Mail-Inhalt-Karte mehr (Hub-Paritaet) ──

describe('AC-3/AC-4 (#3332 AC-10): keine Karte report-mail-content im Trip-Anlegen, in jeder Ansicht', () => {
	for (const [name, mobil] of [['Desktop', false], ['Mobil (390 px)', true]] as const) {
		for (const schritt of ['wetter', 'zustellung'] as const) {
			test(`keine_karte__${mobil ? 'mobil' : 'desktop'}__${schritt}`, () => {
				const html = renderTripNew({ activeTab: schritt, isMobileViewport: mobil, channels: ALLE_AN, wtVisited: true, zuVisited: true, name: 'X', startDate: '2026-09-01', stageNames: ['E1'] });
				assert.equal(countTestid(html, 'report-mail-content'), 0, `${name}/${schritt}: Mail-Inhalt-Karte noch im Trip-Anlegen (der Hub hat keine).`);
				assert.equal(countTestid(html, 'report-email-format-switcher'), 0, `${name}/${schritt}: zweite Bedienstelle des E-Mail-Formats.`);
				if (schritt === 'zustellung') assert.equal(countTestid(html, 'zustellung-tab'), 1, `${name}: Messaufbau — Reiter Zustellung fehlt.`);
			});
		}
	}
});

// ─── AC-3: Anlege-Payload traegt email_format ────────────────────────────────

describe('AC-3: der Anlege-Payload enthaelt das gewaehlte Format', () => {
	test('payload_traegt_email_format_compact_und_fremdfelder_unveraendert', () => {
		const rc = { email_format: 'compact', send_premium_sms: true, morning_time: '06:30:00', change_threshold_temp_c: 3 };
		const payload = buildCreateTripPayload({
			name: 'T', startDate: '2026-09-01', stages: [{ id: 1, name: 'E1' }], channels: ALLE_AN, reportConfig: rc as any
		});
		assert.equal((payload.report_config as any)?.email_format, 'compact');
		assert.deepEqual(payload.report_config, rc, 'AC-3/AC-5: report_config im Anlege-Payload weicht vom Blob ab.');
	});

	// Ersetzt „startzustand_compact_aus_dem_blob": die Standardfelder der entfallenen Karte ergaenzt jetzt der
	// Speicherweg — ein gesetzter Wert (Kompakt, Grosswetterlage aus) darf dort nicht vom Standard ueberschrieben werden.
	test('speicherweg_ergaenzt_standardfelder_ohne_gesetzte_werte_zu_ueberschreiben', () => {
		const rc = ergaenzeStandardwerteReportConfig({ email_format: 'compact', show_stability: false, show_outlook: true } as any) as any;
		assert.equal(rc.email_format, 'compact', 'Kompakt aus dem Blob vom Standard ueberschrieben.');
		assert.equal(rc.show_stability, false, '#3237 F002: show_stability=false aus dem Blob vom Standard ueberschrieben.');
		assert.equal(rc.show_stage_stats, true, 'Standardfeld der Karte fehlt im Speicherweg.');
		const voll = ergaenzeStandardwerteReportConfig({ email_format: 'full' } as any) as any;
		assert.equal(voll.email_format, 'full');
		assert.equal(voll.show_stability, true, 'Standard der Grosswetterlage fehlt im Speicherweg.');
	});
});

// ─── AC-5: Nachbar-Felder bleiben erhalten ───────────────────────────────────

describe('AC-5: Premium-SMS aus dem Blob bleibt neben den Mail-Feldern erhalten', () => {
	// Ersetzt den Haken im Alt-Panel: der Reiter Zustellung liest den Briefing-Kanal aus demselben Blob,
	// und der Speicherweg laesst ihn neben den ergaenzten Mail-Feldern stehen.
	test('premium_sms_bleibt_im_speicherweg_und_im_startstand_des_reiters', () => {
		const blob = { send_premium_sms: true, morning_time: '06:30:00', email_format: 'compact' };
		const rc = ergaenzeStandardwerteReportConfig(blob as any) as any;
		assert.equal(rc.send_premium_sms, true, 'AC-5: send_premium_sms=true geht im Speicherweg verloren.');
		assert.equal(rc.morning_time, '06:30:00');
		assert.equal(rc.email_format, 'compact');
		const stand = standAusTrip({ id: '__new__', name: 'x', stages: [], report_config: blob } as any);
		assert.equal(stand.briefing.premium_sms, true, 'AC-5: Reiter Zustellung zeigt Premium-SMS aus dem Blob nicht an.');
	});
});

// ─── Wirkstelle: kein Mail-Inhalt-Baustein mehr im Editor ────────────────────

type Knoten = Record<string, any>;
function laufe(n: unknown, ahnen: Knoten[], f: (k: Knoten, a: Knoten[]) => void): void {
	if (n === null || typeof n !== 'object') return;
	if (Array.isArray(n)) return n.forEach((x) => laufe(x, ahnen, f));
	const k = n as Knoten;
	if (typeof k.type === 'string') f(k, ahnen);
	const neu = typeof k.type === 'string' ? [...ahnen, k] : ahnen;
	for (const [feld, v] of Object.entries(k)) if (feld !== 'metadata') laufe(v, neu, f);
}

describe('#3332 AC-10: TripNewEditor mountet und importiert keinen Mail-Inhalt-Baustein (Hub-Paritaet)', () => {
	const quelle = readFileSync(EDITOR, 'utf-8');
	const ast = parse(quelle, { modern: true }) as Knoten;
	function mounts(name: string) {
		const out: Knoten[] = [];
		laufe(ast.fragment, [], (k) => { if (k.type === 'Component' && k.name === name) out.push(k); });
		return out;
	}

	test('keine_section_und_keine_mail_inhalt_karte', () => {
		assert.equal(mounts('EditReportConfigSection').length, 0, 'EditReportConfigSection ist in TripNewEditor noch gemountet.');
		assert.equal(mounts('MailInhaltCard').length, 0, `MailInhaltCard noch ${mounts('MailInhaltCard').length}-mal gemountet (Hub hat keine).`);
	});

	test('importiert_den_baustein_nicht_mehr', () => {
		const importe: string[] = [];
		laufe(ast.instance, [], (k) => { if (k.type === 'ImportDeclaration') importe.push(String(k.source.value)); });
		assert.ok(!importe.some((p) => /MailInhaltCard/.test(p)), 'MailInhaltCard noch importiert.');
		assert.ok(!importe.some((p) => /EditReportConfigSection/.test(p)), 'EditReportConfigSection noch importiert.');
	});
});
