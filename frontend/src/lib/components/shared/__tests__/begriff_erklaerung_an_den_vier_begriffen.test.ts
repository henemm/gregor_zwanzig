// TDD RED — Issue #2521 S1 (Spec begriff_erklaerung_infobox.md): das ⓘ steht an
// den vier Fachbegriffen, in Trip UND Ortsvergleich, Desktop UND Mobil.
//
//   AC-8   Wertebereiche: ⓘ in CorridorEditor (Desktop) UND CorridorEditorMobile
//   AC-9   Alarme: sichtbares Label „Dringlichkeits-Schwelle“ + ⓘ im Kanal-Block
//   AC-10  Alarm-Tabelle: ⓘ NUR an der CAPE-Zeile; `title` der Schwellwert-Zelle unveraendert
//   AC-11  Cooldown: ⓘ an der Eyebrow; `.hint`-Text unveraendert
//
// 🔴 SSR rendert die Organismen in ihrem LADEZUSTAND (Katalog nicht geladen,
// `onMount` laeuft nie). Der Corridor-Editor hat fuenf Ueberschrift-Verzweigungen
// (Fehler, Laden vergleich, Laden route, Haupt vergleich, Haupt route) — im SSR ist
// nur „Laden" erreichbar. Das ⓘ muss deshalb auch dort stehen; die Hauptverzweigung
// misst frontend/e2e/begriff-erklaerung.spec.ts im Browser (AC-8, Desktop + Mobil).
//
// Mutations-Gegenprobe (Spec): ⓘ aus CorridorEditorMobile entfernen -> die Faelle
// „CorridorEditorMobile" unten werden rot, die Desktop-Faelle bleiben gruen.
//
// Pfadregel #1409: alles relativ zu DIESER Datei.
//
//   cd frontend && npm test -- src/lib/components/shared/__tests__/begriff_erklaerung_an_den_vier_begriffen.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { ALERTABLE_METRICS, thresholdTitle } from '../../alerts-tab/alertMetricTable.ts';
import {
	attribut,
	entschluesselt,
	innen,
	lade,
	neuerWiz,
	renderKomponente,
	sichtbarerText,
	tagsMitTestid
} from './infoboxSsr.ts';
import { corridorPropsAus } from '../../compare/corridorPropsAus.ts';
import { alarmePropsAus } from '../../compare/alarmePropsAus.ts';

const TRIP = {
	id: 'trip-ii',
	name: 'ⓘ-Trip',
	stages: [],
	alert_rules: [],
	display_config: {},
	report_config: { send_email: true }
};

function ii(html: string, begriff: string): string[] {
	return tagsMitTestid(html, `begriff-erklaerung-${begriff}`);
}

// ─────────────────────────────────────────────────────────────────────────────
// AC-8
// ─────────────────────────────────────────────────────────────────────────────
describe('AC-8: Wertebereiche tragen das ⓘ in Desktop- UND Mobil-Editor, in beiden Kontexten', () => {
	const faelle: [string, string, 'route' | 'vergleich'][] = [
		['CorridorEditor (Desktop)', 'shared/corridor-editor/CorridorEditor.svelte', 'vergleich'],
		['CorridorEditorMobile', 'shared/corridor-editor/CorridorEditorMobile.svelte', 'vergleich'],
		['CorridorEditor (Desktop)', 'shared/corridor-editor/CorridorEditor.svelte', 'route'],
		['CorridorEditorMobile', 'shared/corridor-editor/CorridorEditorMobile.svelte', 'route']
	];
	for (const [name, datei, kontext] of faelle) {
		test(`${name}, context="${kontext}": genau ein ⓘ „wertebereiche“ mit Knopfname`, async () => {
			const Komp = await lade(datei);
			const props =
				kontext === 'vergleich'
					? { context: 'vergleich', ...corridorPropsAus(neuerWiz()) }
					: { context: 'route', trip: TRIP, createMode: true };
			const html = renderKomponente(
				Komp,
				props,
				kontext === 'vergleich' ? new Map([['compare-wizard-state', neuerWiz()]]) : undefined
			);
			const tags = ii(html, 'wertebereiche');
			assert.equal(tags.length, 1, `${name} (${kontext}): ⓘ fehlt oder doppelt — ${tags.length}`);
			assert.match(attribut(tags[0], 'aria-label') ?? '', /Wertebereich/);
			// Das ⓘ steht an der Ueberschrift (Eyebrow „Wertebereiche…“), vor dem Lade-/Inhaltstext.
			const text = sichtbarerText(html);
			assert.match(text, /Wertebereiche/);
			const ladePos = text.indexOf('Lade Metriken');
			assert.ok(ladePos === -1 || text.indexOf("ⓘ") < ladePos, 'ⓘ steht nicht an der Ueberschrift');
		});
	}
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-9
// ─────────────────────────────────────────────────────────────────────────────
describe('AC-9: Alarme — sichtbares Label „Dringlichkeits-Schwelle“ mit ⓘ im Kanal-Block (Trip UND Ortsvergleich)', () => {
	const mounts: [string, () => Record<string, unknown>][] = [
		[
			'route',
			() => ({
				context: 'route',
				trip: TRIP,
				activeMetrics: [],
				metricLevels: {},
				existingChannels: { email: true, telegram: true, sms: false, premium_sms: false },
				profileOverride: { premium_sms_allowed: false }
			})
		],
		[
			'vergleich',
			() => ({
				context: 'vergleich',
				...alarmePropsAus(neuerWiz()),
				catalog: [],
				profileOverride: { premium_sms_allowed: false }
			})
		]
	];
	for (const [kontext, props] of mounts) {
		test(`context="${kontext}": Label als SICHTBARER Text im Kanal-Block, ⓘ daneben, Stufen-Gruppe unveraendert benannt`, async () => {
			const AlarmeTab = await lade('shared/AlarmeTab.svelte');
			const html = renderKomponente(AlarmeTab, props());
			const picker = innen(html, 'alert-channel-picker');
			assert.match(
				sichtbarerText(picker),
				/Dringlichkeits-Schwelle/,
				'„Dringlichkeits-Schwelle“ ist kein sichtbares Label (heute nur aria-label)'
			);
			assert.equal(ii(picker, 'kanal_schwelle').length, 1, 'ⓘ „kanal_schwelle“ fehlt im Kanal-Block (oder doppelt)');
			// Waechter-Teil (heute gruen, im selben Fall): der aria-label der Stufen-Gruppe bleibt.
			assert.match(entschluesselt(picker), /aria-label="Dringlichkeits-Schwelle [^"]+"/);
		});
	}
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-10
// ─────────────────────────────────────────────────────────────────────────────
describe('AC-10: Alarm-Tabelle — ⓘ nur an der CAPE-Zeile, title der Schwellwert-Zelle unveraendert', () => {
	async function zeile(metric: string, label: string): Promise<string> {
		const Row = await lade('alerts-tab/AlertMetricLevelRow.svelte');
		return renderKomponente(Row, { metric, label, level: 'standard', onChange: () => {} });
	}
	function schwellenZelle(html: string, metric: string): string {
		const m = new RegExp(`<td[^>]*data-testid="alert-threshold-${metric}"[^>]*>`).exec(html);
		assert.ok(m, `Schwellwert-Zelle ${metric} fehlt`);
		return m![0];
	}

	test('CAPE-Zeile: ⓘ im Zeilen-Label UND title an der Schwellwert-Zelle = thresholdTitle("cape") (nicht leer)', async () => {
		const html = await zeile('cape', 'Gewitterenergie (CAPE)');
		const tags = ii(html, 'cape');
		assert.equal(tags.length, 1, 'ⓘ „cape“ fehlt an der CAPE-Zeile');
		const label = html.match(/<td class="metric-label[^"]*"[^>]*>([\s\S]*?)<\/td>/);
		assert.ok(label, 'Label-Zelle nicht gefunden');
		assert.ok(label![1].includes('begriff-erklaerung-cape'), 'ⓘ steht nicht IM Zeilen-Label');
		assert.match(sichtbarerText(label![1]), /Gewitterenergie \(CAPE\)/);
		const erwartet = thresholdTitle('cape' as never);
		assert.ok(erwartet && erwartet.length > 0, 'Messaufbau: thresholdTitle("cape") ist leer');
		assert.equal(attribut(schwellenZelle(html, 'cape'), 'title'), erwartet);
	});

	test('jede andere alarmierbare Metrik: KEIN ⓘ und KEIN title (Invariante: nur CAPE hat einen title)', async () => {
		const andere = ALERTABLE_METRICS.filter((m) => m !== 'cape');
		assert.ok(andere.length >= 3, 'Messaufbau: zu wenige Vergleichsmetriken');
		for (const metric of andere) {
			const html = await zeile(metric, `Label ${metric}`);
			assert.equal(tagsMitTestid(html, 'begriff-erklaerung-').length, 0, `${metric}: ⓘ an der falschen Zeile`);
			assert.equal(attribut(schwellenZelle(html, metric), 'title'), null, `${metric}: title an der Schwellwert-Zelle`);
		}
		// Gegenprobe zur Vakuum-Falle: die CAPE-Zeile dieser Rendermethode traegt tatsaechlich ein ⓘ
		// (sonst waere „kein ⓘ bei den anderen" auch bei kaputtem Messaufbau gruen).
		assert.equal(ii(await zeile('cape', 'Gewitterenergie (CAPE)'), 'cape').length, 1);
	});
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-11
// ─────────────────────────────────────────────────────────────────────────────
describe('AC-11: Cooldown — ⓘ an der Eyebrow, Hinweistext unveraendert', () => {
	test('AlertCooldownCard: ⓘ „cooldown“ VOR dem Eingabefeld; .hint-Text und Eingabefeld unveraendert', async () => {
		const Card = await lade('alerts-tab/AlertCooldownCard.svelte');
		const html = renderKomponente(Card, { cooldown_minutes: 30 });
		const tags = ii(html, 'cooldown');
		assert.equal(tags.length, 1, 'ⓘ „cooldown“ fehlt (oder doppelt)');
		assert.ok(
			html.indexOf('begriff-erklaerung-cooldown') < html.indexOf('data-testid="alert-cooldown-input"'),
			'ⓘ steht nicht an der Ueberschrift (vor dem Eingabefeld)'
		);
		// Waechter-Teil (heute gruen, im selben Fall): bestehender Hinweistext + Eingabefeld.
		const hint = html.match(/<p class="hint[^"]*">([\s\S]*?)<\/p>/);
		assert.ok(hint, '.hint-Absatz fehlt');
		assert.equal(
			sichtbarerText(hint![1]),
			'Mindestabstand zwischen zwei Alerts derselben Metrik — verhindert Spam bei zappelnden Werten.'
		);
		assert.match(html, /data-testid="alert-cooldown-input"/);
		assert.match(sichtbarerText(html), /Cooldown/);
	});
});
