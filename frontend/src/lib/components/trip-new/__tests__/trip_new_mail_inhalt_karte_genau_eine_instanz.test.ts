// TDD RED — Issue #2277 Scheibe S5: Anlege-Wirkstelle der Mail-Inhalt-Karte.
// Spec: docs/specs/modules/feat_2277_s5_reportconfig_rueckbau.md — AC-3, AC-4, AC-5.
//
// Die Karte "E-Mail-Inhalt" (report-mail-content) steht auf /trips/new im
// Versand-Reiter, in Desktop UND Mobil, jeweils genau EINMAL (XOR per
// isMobileViewport — zwei gleichzeitig gemountete Instanzen halten je einen
// Schnappschuss von report_config, Last-Write-Wins, Fix-Loop 4 aus #1738) und
// kommt ab S5 aus shared/MailInhaltCard.svelte statt aus der Section.
//
// Messung: SSR-Render der echten Anlege-Komponente (Harness ./tripNewSsr.ts),
// plus AST der Komponente fuer WELCHER Baustein in WELCHEM Gate steht
// (Mutation "isMobileViewport-Gate entfernen" / "Mobil-Mount weglassen" wird an
// der Wirkstelle rot, nicht nur im Baustein-Test).
//
// RED heute:
//   - Startzustand: die Section uebernimmt email_format erst in onMount; der
//     Server-Render zeigt bei email_format="compact" kein report-compact-hint.
//   - AST: TripNewEditor mountet EditReportConfigSection statt MailInhaltCard.
//
// Ausfuehren:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-new/__tests__/trip_new_mail_inhalt_karte_genau_eine_instanz.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { parse } from 'svelte/compiler';
import {
	renderTripNew,
	assertTabOffen,
	countTestid,
	bereichVon,
	checkboxInputTag,
	hatAttribut
} from './tripNewSsr.ts';
import { buildCreateTripPayload } from '../tripNewLogic.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const EDITOR = path.join(HERE, '..', 'TripNewEditor.svelte');
const ALLE_AN = { email: true, telegram: true, sms: true };

function versand(isMobileViewport: boolean, reportConfig?: Record<string, unknown>): string {
	const html = renderTripNew({ activeTab: 'versand', isMobileViewport, channels: ALLE_AN, reportConfig });
	assertTabOffen(html, 'versand');
	return html;
}

// ─── AC-3 (Desktop) / AC-4 (Mobil): genau eine Karte, im richtigen Baum ──────

describe('AC-3/AC-4: genau eine Karte report-mail-content, in jeder Ansicht', () => {
	for (const [name, mobil, baum] of [
		['AC-3 Desktop', false, 'desktop'],
		['AC-4 Mobil (390 px)', true, 'mobil']
	] as const) {
		test(`genau_eine_karte__${baum}`, () => {
			const html = versand(mobil);
			assert.equal(
				countTestid(html, 'report-mail-content'), 1,
				`${name}: ${countTestid(html, 'report-mail-content')} Karten im Dokument (erwartet genau 1).`
			);
			assert.equal(countTestid(html, 'report-email-format-switcher'), 1, `${name}: Format-Umschalter nicht genau einmal.`);
			assert.equal(bereichVon(html, 'report-mail-content'), baum, `${name}: Karte steht im falschen Markup-Baum (CSS-Umschaltung macht sie sonst unsichtbar).`);
		});

		test(`startzustand_compact_aus_dem_blob__${baum}`, () => {
			const html = versand(mobil, { email_format: 'compact', show_outlook: false });
			assert.equal(countTestid(html, 'report-compact-hint'), 1,
				`${name}: Kompakt-Hinweis fehlt — der Startzustand der Karte kommt nicht beim Erzeugen aus dem Blob ` +
					'(onMount laeuft im Server-Render nie).');
			assert.ok(hatAttribut(checkboxInputTag(html, 'report-show-outlook'), 'disabled'),
				`${name}: Schalter "Ausblick" im Kompakt-Modus nicht deaktiviert.`);
			assert.ok(!hatAttribut(checkboxInputTag(html, 'report-show-outlook'), 'checked'),
				`${name}: show_outlook=false wird nicht uebernommen.`);
		});

		test(`ausfuehrlich_ohne_hinweis__${baum}`, () => {
			const html = versand(mobil, { email_format: 'full' });
			assert.equal(countTestid(html, 'report-compact-hint'), 0, `${name}: Hinweis im Modus "Ausfuehrlich".`);
		});
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
});

// ─── AC-5: Nachbar-Felder bleiben im Render stehen ───────────────────────────

describe('AC-5: Premium-SMS aus dem Blob bleibt neben der Karte erhalten', () => {
	test('premium_sms_haken_steht_trotz_mail_inhalt_karte', () => {
		const html = versand(false, { send_premium_sms: true, morning_time: '06:30:00', email_format: 'compact' });
		assert.equal(countTestid(html, 'channel-premium-sms'), 1);
		assert.ok(hatAttribut(checkboxInputTag(html, 'channel-premium-sms'), 'checked'),
			'AC-5: send_premium_sms=true aus dem Blob ist im Versand-Reiter nicht mehr angehakt.');
		assert.equal(countTestid(html, 'report-mail-content'), 1);
	});
});

// ─── Wirkstelle: welcher Baustein, unter welchem Gate ────────────────────────

type Knoten = Record<string, any>;
function laufe(n: unknown, ahnen: Knoten[], f: (k: Knoten, a: Knoten[]) => void): void {
	if (n === null || typeof n !== 'object') return;
	if (Array.isArray(n)) return n.forEach((x) => laufe(x, ahnen, f));
	const k = n as Knoten;
	if (typeof k.type === 'string') f(k, ahnen);
	const neu = typeof k.type === 'string' ? [...ahnen, k] : ahnen;
	for (const [feld, v] of Object.entries(k)) if (feld !== 'metadata') laufe(v, neu, f);
}

describe('AC-3/AC-4: TripNewEditor mountet MailInhaltCard genau zweimal, XOR per isMobileViewport', () => {
	const quelle = readFileSync(EDITOR, 'utf-8');
	const ast = parse(quelle, { modern: true }) as Knoten;
	const gate = (g: Knoten) => quelle.slice(g.test.start, g.test.end).trim();

	function mounts(name: string) {
		const out: { k: Knoten; ahnen: Knoten[] }[] = [];
		laufe(ast.fragment, [], (k, ahnen) => { if (k.type === 'Component' && k.name === name) out.push({ k, ahnen }); });
		return out;
	}

	test('keine_section_mehr_nur_der_baustein', () => {
		assert.equal(mounts('EditReportConfigSection').length, 0, 'EditReportConfigSection ist in TripNewEditor noch gemountet.');
		assert.equal(mounts('MailInhaltCard').length, 2, `Erwartet 2 MailInhaltCard-Mounts (Desktop + Mobil), gefunden ${mounts('MailInhaltCard').length}.`);
	});

	test('ein_mount_steht_unter_not_isMobileViewport_der_andere_unter_isMobileViewport', () => {
		const gates = mounts('MailInhaltCard').map((m) =>
			m.ahnen.filter((a) => a.type === 'IfBlock').map(gate)
		);
		const desktop = gates.filter((g) => g.some((t) => /^!\s*isMobileViewport$/.test(t)));
		const mobil = gates.filter((g) => g.some((t) => /^isMobileViewport$/.test(t)));
		assert.equal(desktop.length, 1, `AC-3: genau ein Mount muss unter {#if !isMobileViewport} stehen (Gates: ${JSON.stringify(gates)}).`);
		assert.equal(mobil.length, 1, `AC-4: genau ein Mount muss unter {#if isMobileViewport} stehen (Gates: ${JSON.stringify(gates)}).`);
	});

	test('beide_mounts_binden_reportConfig_ohne_kanal_oder_zeitplan_props', () => {
		assert.equal(mounts('MailInhaltCard').length, 2, 'Erwartet 2 MailInhaltCard-Mounts (sonst waere diese Pruefung leer).');
		for (const { k } of mounts('MailInhaltCard')) {
			assert.ok(k.attributes.some((a: Knoten) => a.type === 'BindDirective' && a.name === 'reportConfig'),
				'AC-4: Mount ohne bind:reportConfig — Desktop und Mobil schrieben nicht in denselben report_config.');
			const namen = k.attributes.map((a: Knoten) => a.name);
			for (const v of ['showChannels', 'showSchedule', 'mode', 'weatherChannels']) {
				assert.ok(!namen.includes(v), `Prop "${v}" gehoert nicht an den Baustein.`);
			}
		}
	});

	test('importiert_den_baustein_aus_shared', () => {
		const importe: string[] = [];
		laufe(ast.instance, [], (k) => { if (k.type === 'ImportDeclaration') importe.push(String(k.source.value)); });
		assert.ok(importe.some((p) => /shared\/MailInhaltCard\.svelte$/.test(p)), `Kein Import von shared/MailInhaltCard.svelte (Importe: ${importe.filter((p) => /Mail|Report/.test(p))}).`);
		assert.ok(!importe.some((p) => /EditReportConfigSection/.test(p)), 'EditReportConfigSection noch importiert.');
	});
});
