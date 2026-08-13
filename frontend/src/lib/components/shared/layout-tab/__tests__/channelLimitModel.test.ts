// TDD RED — Issue #1719 Scheibe S3, AC-3 + AC-4 (Unit-Anteil): die
// Platzgrenzen werden als EINHEIT modelliert (Spalten vs. Zeichen), nicht
// mehr als eine einzige, kanalübergreifend falsch interpretierte Zahl.
//
// Spec: docs/specs/modules/fix_1719_s3_aus_ist_ein_zustand.md
//   Abschnitt 5 ("Platzgrenzen ehrlich modellieren"), Abschnitt 6
//   ("Telegram 7 statt 8"), AC-3, AC-4.
// Kontext: docs/context/fix-1719-s3-aus-ist-ein-zustand.md
//   Abschnitt 3.1 ("Die echten Grenzen, je Kanal gemessen"),
//   Abschnitt 3.2 Punkt 1 ("Telegram ist um eins zu großzügig").
//
// Befund, den dieser Test rot macht:
//   - `CHANNEL_COL_BUDGET.telegram` (trip-detail/metricsEditor.ts:230) ist
//     heute 8, das Backend liefert aber nur 7 Metrik-Spalten
//     (src/output/renderers/channel_layout.py:110, `metric_slots = limit - 1`).
//   - Fuer SMS gibt es heute nur eine Spaltenzahl (`CHANNEL_COL_BUDGET.sms
//     === 0`, layout-tab/ltChannels.ts:39) — keine Modellierung der
//     tatsaechlichen Einheit (Zeichen, Trip-Pfad 160).
//
// Das hier importierte Modul `../ltChannels.ts` hat die unten verwendeten
// Exporte (`LtLimit`, `TELEGRAM_METRIC_COLUMNS`, `SMS_TRIP_CHAR_LIMIT`,
// `ltLimitForChannel`, `ltBadgeForLimit`, `ltOverflowForLimit`) noch NICHT
// -> der Import wirft einen Modul-Resolve-Fehler und ALLE Tests dieser Datei
// scheitern (RED). Muster: shared/__tests__/channelMetricLayouts.test.ts.
//
// Kontrakt fuer GREEN (reine Funktionen, kein Svelte-State, kein DOM):
//
//   type LtLimit =
//     | { kind: 'none' }
//     | { kind: 'columns'; value: number }
//     | { kind: 'chars'; value: number };
//
//   TELEGRAM_METRIC_COLUMNS: number  // 7 — Beleg: channel_layout.py:110
//   SMS_TRIP_CHAR_LIMIT: number      // 160 — Beleg: trip_report.py:446
//
//   ltLimitForChannel(channel: ChannelId, smsCharLimit: number): LtLimit
//     - email    -> { kind: 'none' }
//     - telegram -> { kind: 'columns', value: TELEGRAM_METRIC_COLUMNS }
//     - sms      -> { kind: 'chars', value: smsCharLimit }  (Wert vom
//       AUFRUFER, NICHT aus einer geteilten Konstante — Spec Abschnitt 5,
//       Praezedenz `hasLabelColumn` bei LTCapNote.svelte:23. Trip-Pfad ruft
//       mit SMS_TRIP_CHAR_LIMIT (160) auf, Vergleichs-Pfad mit 153 — dieser
//       Test prueft nur den Trip-Pfad.)
//
//   ltBadgeForLimit(limit: LtLimit): string
//     - none    -> '∞'
//     - columns -> String(value)
//     - chars   -> String(value)   (AC-4: Chip zeigt die Zeichenzahl, NICHT '—')
//
//   ltOverflowForLimit(limit: LtLimit, count: number): number | undefined
//     - none/chars -> undefined (AC-4: fuer 'chars' wird KEIN Ueberlauf
//       berechnet — Spec Abschnitt 5, "Ueberlauf fuer kind:'chars' wird
//       ausdruecklich NICHT berechnet")
//     - columns -> count - value, wenn count > value, sonst undefined
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/layout-tab/__tests__/channelLimitModel.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

const {
	TELEGRAM_METRIC_COLUMNS,
	SMS_TRIP_CHAR_LIMIT,
	ltLimitForChannel,
	ltBadgeForLimit,
	ltOverflowForLimit
} = await import('../ltChannels.ts');

describe('AC-3: Telegram liefert 7 Metrik-Spalten, nicht 8', () => {
	test('TELEGRAM_METRIC_COLUMNS === 7 (Beleg: channel_layout.py:110, metric_slots = limit - 1)', () => {
		assert.equal(
			TELEGRAM_METRIC_COLUMNS,
			7,
			'AC-3 FAIL: Telegram-Budget muss 7 Metrik-Spalten sein (die 8. Spalte ist die Uhrzeit) — ' +
				'metricsEditor.ts verspricht dem Nutzer heute eine Spalte mehr, als tatsaechlich ankommt'
		);
	});

	test("ltLimitForChannel('telegram', ...) traegt value 7", () => {
		const limit = ltLimitForChannel('telegram', SMS_TRIP_CHAR_LIMIT);
		assert.deepEqual(limit, { kind: 'columns', value: 7 });
	});

	test('9 aktive Metriken im Telegram-Reiter: Kapplinie nach der 7., Ueberlauf-Chip nennt 2', () => {
		const limit = ltLimitForChannel('telegram', SMS_TRIP_CHAR_LIMIT);
		const overflow = ltOverflowForLimit(limit, 9);
		assert.equal(
			overflow,
			2,
			'AC-3 FAIL: bei 9 aktiven Metriken im Telegram-Reiter muss der Ueberlauf-Chip 2 nennen (9 - 7)'
		);
	});
});

describe('AC-4: SMS traegt eine Zeichengrenze, keine Spaltengrenze', () => {
	test("ltLimitForChannel('sms', 160) === { kind: 'chars', value: 160 } im Trip-Pfad", () => {
		const limit = ltLimitForChannel('sms', SMS_TRIP_CHAR_LIMIT);
		assert.deepEqual(
			limit,
			{ kind: 'chars', value: 160 },
			"AC-4 FAIL: SMS muss im Trip-Kontext { kind: 'chars', value: 160 } liefern, " +
				"nicht { kind: 'columns', value: 0 } (der heutige Sentinel)"
		);
	});

	test('SMS_TRIP_CHAR_LIMIT === 160 (Beleg: trip_report.py:446, max_length=160, Literal)', () => {
		assert.equal(SMS_TRIP_CHAR_LIMIT, 160);
	});

	test('der Zeichenwert kommt vom Aufrufer, nicht aus einer festen Konstante (Vergleichs-Kontext waere 153)', () => {
		const limit = ltLimitForChannel('sms', 153);
		assert.deepEqual(
			limit,
			{ kind: 'chars', value: 153 },
			'AC-4 FAIL: ltLimitForChannel darf den SMS-Zeichenwert nicht fest verdrahten — ' +
				'Trip (160) und Vergleich (153) unterscheiden sich (channel_layout.py:45-54)'
		);
	});

	test("ltBadgeForLimit zeigt fuer 'chars' die Zeichenzahl, NICHT '—'", () => {
		const badge = ltBadgeForLimit({ kind: 'chars', value: 160 });
		assert.equal(
			badge,
			'160',
			"AC-4 FAIL: der SMS-Chip muss die Zeichengrenze (160) zeigen — " +
				"'—' waere die heutige (falsche) Anzeige fuer den Spalten-Sentinel 0"
		);
	});

	test("ltOverflowForLimit liefert fuer 'chars' KEINEN Eintrag (Spec Abschnitt 5: Ueberlauf nicht berechenbar)", () => {
		const overflow = ltOverflowForLimit({ kind: 'chars', value: 160 }, 25);
		assert.equal(
			overflow,
			undefined,
			'AC-4 FAIL: fuer SMS (kind: chars) darf kein Ueberlauf-Wert entstehen — der Editor kennt ' +
				'die fertig gebaute SMS-Zeile nicht, eine Schaetzzahl waere eine zweite falsche Behauptung'
		);
	});
});

describe('E-Mail bleibt unbegrenzt', () => {
	test("ltLimitForChannel('email', ...) === { kind: 'none' }", () => {
		assert.deepEqual(ltLimitForChannel('email', SMS_TRIP_CHAR_LIMIT), { kind: 'none' });
	});

	test("ltBadgeForLimit({kind:'none'}) === '∞'", () => {
		assert.equal(ltBadgeForLimit({ kind: 'none' }), '∞');
	});

	test("ltOverflowForLimit({kind:'none'}, ...) === undefined", () => {
		assert.equal(ltOverflowForLimit({ kind: 'none' }, 999), undefined);
	});
});

// ── TDD RED — Issue #1703 Scheibe 8, AC-S8-12 ──────────────────────────────
//
// Spec: docs/specs/modules/feat_1703_s8_compare_kanal_tabs.md Abschnitt 7
//   ("Fix B — SMS-Zeichengrenze am Kanal-Tab-Badge"), AC-S8-12, Gegenprobe M7.
//
// Gemessener Widerspruch: `LTChannelPicker.svelte:29,39` iteriert die
// Modul-Konstante `LT_CHANNELS` (ltChannels.ts:71-75), fest gebaut mit
// SMS_TRIP_CHAR_LIMIT (160). Im Ortsvergleich zeigt der SMS-Badge damit "160",
// waehrend der Hinweistext darunter (ltCapNoteText ueber smsCharLimit) korrekt
// "153" nennt — zwei sich widersprechende Kappungs-Aussagen auf einer Seite.
//
// `ltChannelsFor(smsCharLimit)` existiert noch NICHT -> die Zusicherung in
// `channelsFor()` schlaegt fehl (RED).
const { ltChannelsFor, LT_CHANNELS, SMS_COMPARE_CHAR_LIMIT } = await import('../ltChannels.ts');

const channelsFor = (smsCharLimit: number) => {
	assert.equal(
		typeof ltChannelsFor,
		'function',
		'RED: ltChannelsFor(smsCharLimit) fehlt in layout-tab/ltChannels.ts — ohne sie kann ' +
			'LTChannelPicker nur die fest verdrahtete Trip-Liste (160) anzeigen'
	);
	return ltChannelsFor(smsCharLimit);
};
const limitOf = (list: { id: string; limit: unknown }[], id: string) =>
	list.find((c) => c.id === id)?.limit;

describe('AC-S8-12: der SMS-Kanal-Tab des Ortsvergleichs nennt 153, der Trip-Pfad weiter 160', () => {
	test('ltChannelsFor(153) traegt fuer SMS chars:153 — LT_CHANNELS (Trip) unveraendert chars:160', () => {
		assert.equal(SMS_COMPARE_CHAR_LIMIT, 153, 'Beleg: channel_layout.py:45-54, floor((140-6)*8/7)');
		assert.deepEqual(
			limitOf(channelsFor(SMS_COMPARE_CHAR_LIMIT), 'sms'),
			{ kind: 'chars', value: 153 },
			'AC-S8-12 FAIL: der Kanal-Tab-Badge im Ortsvergleich muss 153 Zeichen nennen — ' +
				'M7 (weiterhin LT_CHANNELS direkt importieren) widerspraeche dem Hinweistext darunter'
		);
		assert.deepEqual(
			limitOf(LT_CHANNELS, 'sms'),
			{ kind: 'chars', value: 160 },
			'AC-S8-12 FAIL: die Trip-Kanalliste darf sich dabei NICHT auf 153 mitverschieben ' +
				'(trip_report.py:446, max_length=160)'
		);
	});

	test('Telegram bleibt in beiden Listen columns:7 — nur die SMS-Einheit haengt am Aufrufer', () => {
		assert.deepEqual(limitOf(channelsFor(SMS_COMPARE_CHAR_LIMIT), 'telegram'), {
			kind: 'columns',
			value: 7
		});
		assert.deepEqual(limitOf(LT_CHANNELS, 'telegram'), { kind: 'columns', value: 7 });
	});
});

// ── Fix-Loop Adversary-Fund F002 (HIGH) — die VERDRAHTUNG, nicht nur die
//    reine Funktion ─────────────────────────────────────────────────────────
//
// Die Tests oben belegen ausschliesslich `ltChannelsFor()` als reine Funktion.
// Ob der Kanal-Umschalter sie ueberhaupt SIEHT, war unbewacht: die Mutation
// `{#each channels ...}` -> `{#each LT_CHANNELS ...}` in LTChannelPicker.svelte
// stellt exakt den Zustand VOR dem Fix wieder her (SMS-Badge zeigt im
// Ortsvergleich 160 statt 153, im Widerspruch zum Hinweistext darunter) und
// lief trotzdem durch alle Frontend-Tests gruen.
//
// Bewacht wird deshalb die ganze kurze Kette:
//   LayoutTab.smsCharLimit (Prop vom Aufrufer)
//     -> ltChannelsFor(smsCharLimit)
//     -> <LTChannelPicker channels={...}>
//     -> {#each channels}
// Reisst ein Glied, ist der Badge wieder eine feste Trip-Zahl.
//
// AST statt DOM aus demselben Grund wie in den Geschwister-Waechtern: dieses
// Repo hat kein vitest/jsdom (package.json "test": node --test), geparst wird
// mit dem ECHTEN Svelte-5-Compiler.

const here = dirname(fileURLToPath(import.meta.url));
const PICKER_FILE = join(here, '..', 'LTChannelPicker.svelte');
const LAYOUT_TAB_FILE = join(here, '..', 'LayoutTab.svelte');

function svelteAst(path: string): any {
	return parse(readFileSync(path, 'utf-8'), { modern: true });
}

function walk(root: unknown, pred: (n: any) => boolean): any[] {
	const found: any[] = [];
	(function visit(node: unknown): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visit);
			return;
		}
		const n = node as Record<string, any>;
		if (pred(n)) found.push(n);
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	})(root);
	return found;
}

/** Namen der aus `$props()` destrukturierten Eintraege einer Komponente. */
function propNames(ast: any): string[] {
	const decl = walk(ast.instance, (n) => n.type === 'VariableDeclarator').find(
		(d: any) => d.init?.type === 'CallExpression' && d.init.callee?.name === '$props'
	);
	if (!decl || decl.id?.type !== 'ObjectPattern') return [];
	return decl.id.properties.map((p: any) => p.key?.name).filter(Boolean);
}

/** `$derived(x)` / `$derived.by(...)` auspacken, sonst den Ausdruck selbst. */
function unwrapDerived(expr: any): any {
	if (expr?.type === 'CallExpression' && expr.callee?.name === '$derived') {
		return expr.arguments?.[0];
	}
	return expr;
}

describe('AC-S8-12 (Verdrahtung): der Kanal-Umschalter iteriert die PROP, nicht die Modul-Konstante', () => {
	test('LTChannelPicker.svelte: das {#each} laeuft ueber `channels`, und `channels` ist eine $props()-Prop', () => {
		const ast = svelteAst(PICKER_FILE);

		const eachBlocks = walk(ast.fragment, (n) => n.type === 'EachBlock');
		assert.equal(
			eachBlocks.length,
			1,
			`Erwartet genau EIN {#each} in LTChannelPicker.svelte, gefunden ${eachBlocks.length} — ` +
				'Test ist blind geworden oder die Struktur hat sich geaendert.'
		);

		const expr = eachBlocks[0].expression;
		assert.equal(
			expr?.type === 'Identifier' ? expr.name : `Ausdruck(${expr?.type})`,
			'channels',
			'AC-S8-12 FAIL: der Kanal-Umschalter iteriert nicht mehr die `channels`-Prop. Iteriert er ' +
				'wieder die Modul-Konstante LT_CHANNELS (ltChannels.ts:84, fest mit ' +
				'SMS_TRIP_CHAR_LIMIT gebaut), zeigt der SMS-Badge im Ortsvergleich 160 — der ' +
				'Kappungs-Hinweis darunter nennt aber 153 (LTCapNote ueber smsCharLimit). Zwei ' +
				'sich widersprechende Kappungs-Aussagen auf einer Seite, genau der Zustand vor #1703 S8.'
		);

		assert.ok(
			propNames(ast).includes('channels'),
			'AC-S8-12 FAIL: `channels` ist kein $props()-Eintrag von LTChannelPicker mehr — eine ' +
				'gleichnamige lokale Konstante wuerde das {#each} oben unveraendert bestehen lassen ' +
				'und den Aufrufer trotzdem entmachten.'
		);
	});

	test('LayoutTab.svelte: LTChannelPicker bekommt `channels` aus ltChannelsFor(smsCharLimit)', () => {
		const ast = svelteAst(LAYOUT_TAB_FILE);

		const pickers = walk(
			ast.fragment,
			(n) => n.type === 'Component' && n.name === 'LTChannelPicker'
		);
		assert.equal(
			pickers.length,
			1,
			`Erwartet genau EINEN LTChannelPicker-Aufruf in LayoutTab.svelte, gefunden ${pickers.length} — ` +
				'Test ist blind geworden oder die Struktur hat sich geaendert.'
		);

		const attr = (pickers[0].attributes ?? []).find(
			(a: any) => a.type === 'Attribute' && a.name === 'channels'
		);
		assert.notEqual(
			attr,
			undefined,
			'AC-S8-12 FAIL: LayoutTab reicht `channels` nicht mehr an LTChannelPicker durch — die ' +
				'Prop faellt dann auf ihren Vorgabewert LT_CHANNELS (Trip, 160 Zeichen) zurueck und ' +
				'der Ortsvergleich zeigt wieder die falsche Zahl.'
		);

		// `{channels}` (Kurzform) -> Identifier; der Wert darf auch direkt als
		// Aufruf stehen. Beide Formen werden bis zum Aufruf zurueckverfolgt.
		let call = attr.value?.type === 'ExpressionTag' ? attr.value.expression : undefined;
		if (call?.type === 'Identifier') {
			const decl = walk(ast.instance, (n) => n.type === 'VariableDeclarator').find(
				(d: any) => d.id?.type === 'Identifier' && d.id.name === call.name
			);
			assert.notEqual(
				decl,
				undefined,
				`AC-S8-12 FAIL: \`channels={${call.name}}\` — aber \`${call.name}\` ist in LayoutTab.svelte ` +
					'nicht deklariert (Import einer fertigen Liste?). Dann haengt der Badge nicht mehr am ' +
					'smsCharLimit des Aufrufers.'
			);
			call = unwrapDerived(decl.init);
		}

		assert.equal(
			call?.type === 'CallExpression' ? call.callee?.name : `Ausdruck(${call?.type})`,
			'ltChannelsFor',
			'AC-S8-12 FAIL: die Kanalliste stammt nicht aus `ltChannelsFor(...)`. Jede andere Quelle ' +
				'(LT_CHANNELS, eigene Literalliste) traegt eine fest verdrahtete SMS-Zeichenzahl.'
		);

		const arg = call.arguments?.[0];
		assert.equal(
			arg?.type === 'Identifier' ? arg.name : `Ausdruck(${arg?.type})`,
			'smsCharLimit',
			'AC-S8-12 FAIL: `ltChannelsFor(...)` bekommt nicht die `smsCharLimit`-Prop, sondern eine ' +
				'andere Quelle. Steht dort wieder eine Konstante (SMS_TRIP_CHAR_LIMIT), nennt der ' +
				'Badge im Ortsvergleich 160 statt 153 — die Prop waere zwar benutzt, aber falsch gespeist.'
		);

		assert.ok(
			propNames(ast).includes('smsCharLimit'),
			'AC-S8-12 FAIL: `smsCharLimit` ist kein $props()-Eintrag von LayoutTab mehr — der Wert ' +
				'kaeme dann nicht mehr vom Aufrufer (Trip 160 / Vergleich 153), sondern aus dem Organism.'
		);
	});
});
