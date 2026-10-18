// TDD RED — Issue #2278 (Epic #2345 P3), AC-3, AC-4 (+ Teil von AC-10, AC-14).
// Spec: docs/specs/modules/feat_2278_aktionsmodell.md — Implementation Details 5.
//
// SendConfirmDialog = EIN Sende-Dialog fuer Liste, Hub und Mobil beider Arten.
//
// WARUM Modell + AST statt SSR-Render: der Dialog sitzt auf bits-ui `Dialog` (Portal).
// Gemessen: `render(ConfirmDialog, {open:true})` liefert unter svelte/server KEINEN
// Dialog-Inhalt (weder Titel noch Beschreibung). Ein SSR-Test waere strukturell leer.
// Die Entscheidungslogik steht deshalb in einer REINEN Funktion `sendConfirmModel` in
// `molecules/sendConfirmModel.ts` (Vertrag hier festgelegt); die Komponente bindet sie ein,
// was per AST (echter Svelte-Compiler, kein String-Grep) bewacht wird. Das Durchklicken
// (echte Dialoge, gesendeter Request) bewacht Playwright `aktionsmodell-durchklick.spec.ts`.
//
// Vertrag `sendConfirmModel(kind, profile, subscription, auswahl?)`:
//   - kind: SubscriptionKind ('trip' | 'vergleich'); profile: Konto-Profil | null;
//     subscription: Objekt mit send_telegram/send_sms/send_premium_sms (Trip: flache Felder,
//     vom Go-Store aus report_config abgeleitet); auswahl: 'morning'|'evening' (nur Trip).
//   - Rueckgabe: { beschreibung: string,          // == sendTargetLabel(...).text
//                  gesperrt: boolean,             // == sendTargetLabel(...).gesperrt
//                  berichtsartWahl: null | [{value:'morning',label:'Morgen'},{value:'evening',label:'Abend'}],
//                  berichtsart: 'morning'|'evening'|undefined }  // Trip: Auswahl, Default 'morning'; Vergleich: undefined
//
// Vertrag Komponente `molecules/SendConfirmDialog.svelte`: Props `open, kind, profile,
// subscription, running?, onConfirm(berichtsart?), onCancel`. Sie sendet NICHT selbst
// (kein fetch / kein sendSubscription in der Komponente): der Request haengt allein am
// `onConfirm` des Aufrufers => vor Bestaetigung geht nachweislich nichts raus.
//
// RED heute: weder sendConfirmModel.ts noch SendConfirmDialog.svelte existieren.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/molecules/__tests__/send_confirm_dialog.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { pathToFileURL, fileURLToPath } from 'node:url';
import path from 'node:path';
import { parse } from 'svelte/compiler';
import { sendTargetLabel } from '../../shared/versand-tab/sendTargetLabel.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const MODEL = path.join(HERE, '..', 'sendConfirmModel.ts');
const DIALOG = path.join(HERE, '..', 'SendConfirmDialog.svelte');
const mod: any = await import(pathToFileURL(MODEL).href).catch(() => null);
function braucheModell(): any {
	assert.ok(mod, 'Modul molecules/sendConfirmModel.ts fehlt (RED) — AC-3/AC-4.');
	return mod.sendConfirmModel;
}

const MAIL = 'wanderer@example.org';
const PROFIL_A = { mail_to: 'anna@example.org', email_verified: true, telegram_chat_id: 'A-1' };
const PROFIL_B = { mail_to: 'bodo@example.org', email_verified: true, telegram_chat_id: 'B-9' };
const PREMIUM_PROFIL = {
	mail_to: MAIL,
	email_verified: true,
	premium_sms_allowed: true,
	premium_sms_reply_state: 'fresh' as const,
	premium_sms_reply_to: '+491700000000'
};
const KINDS = ['trip', 'vergleich'] as const;

describe('AC-3: Ziel kommt aus sendTargetLabel — fuer beide Arten', () => {
	for (const kind of KINDS) {
		test(`${kind}: Beschreibung == echtes Versandziel (E-Mail-Adresse)`, () => {
			const modell = braucheModell();
			const m = modell(kind, PROFIL_A, {});
			assert.equal(m.beschreibung, sendTargetLabel(PROFIL_A, {}).text);
			assert.match(m.beschreibung, /anna@example\.org/);
			assert.equal(m.gesperrt, false);
		});

		test(`${kind}: Premium-SMS wird als Ziel genannt, wenn eingeschaltet und zustellbar`, () => {
			const modell = braucheModell();
			const m = modell(kind, PREMIUM_PROFIL, { send_premium_sms: true });
			assert.equal(m.beschreibung, `Geht an E-Mail (${MAIL}) · Premium-SMS.`);
		});

		test(`${kind}: ohne Konto-Adresse gesperrt (kein Kanal kann liefern)`, () => {
			const modell = braucheModell();
			const m = modell(kind, { email_verified: false }, { send_telegram: true });
			assert.equal(m.gesperrt, true);
		});

		test(`${kind}: ohne Profil (null) ist der Versand gesperrt, kein Default-Ziel`, () => {
			const modell = braucheModell();
			const m = modell(kind, null, { send_telegram: true });
			assert.equal(m.gesperrt, true);
			assert.doesNotMatch(m.beschreibung, /@example\.org\)/);
		});
	}

	test('Fix-Loop 1 (F014/AC-10): ohne Profil/Session ist das Ziel „unbekannt" (gesperrt); mit Profil ohne Adresse bleibt es „keine E-Mail-Adresse"', () => {
		const modell = braucheModell();
		for (const ohne of [null, undefined]) {
			const m = modell('trip', ohne, { send_telegram: true });
			assert.equal(m.gesperrt, true);
			assert.match(m.beschreibung, /unbekannt/);
		}
		const leer = modell('trip', {}, {});
		assert.equal(leer.gesperrt, true);
		assert.match(leer.beschreibung, /keine E-Mail-Adresse/);
	});

	test('zwei Nutzer: Ziel B enthaelt nie die Adresse/den Chat von A (AC-10)', () => {
		const modell = braucheModell();
		const a = modell('trip', PROFIL_A, { send_telegram: true });
		const b = modell('trip', PROFIL_B, { send_telegram: true });
		assert.match(a.beschreibung, /anna@/);
		assert.match(b.beschreibung, /bodo@/);
		assert.doesNotMatch(b.beschreibung, /anna@/);
	});
});

describe('AC-4: Morgen/Abend nur beim Trip, Default Morgen', () => {
	test('Trip: Wahl Morgen/Abend vorhanden, Vorauswahl Morgen', () => {
		const modell = braucheModell();
		const m = modell('trip', PROFIL_A, {});
		assert.deepEqual(m.berichtsartWahl, [
			{ value: 'morning', label: 'Morgen' },
			{ value: 'evening', label: 'Abend' }
		]);
		assert.equal(m.berichtsart, 'morning');
	});
	test('Trip: gewaehlte Option "Abend" bestimmt die Berichtsart', () => {
		const modell = braucheModell();
		assert.equal(modell('trip', PROFIL_A, {}, 'evening').berichtsart, 'evening');
		assert.equal(modell('trip', PROFIL_A, {}, 'morning').berichtsart, 'morning');
	});
	test('Ortsvergleich: keine Wahl, keine Berichtsart — auch wenn eine Auswahl uebergeben wird', () => {
		const modell = braucheModell();
		const m = modell('vergleich', PROFIL_A, {}, 'evening');
		assert.equal(m.berichtsartWahl, null);
		assert.equal(m.berichtsart, undefined);
	});
});

// --- Komponente per AST (echter Svelte-Compiler) -----------------------------------------

function collect(subtree: unknown, pred: (n: any) => boolean): any[] {
	const found: any[] = [];
	(function visit(node: unknown): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) return void node.forEach(visit);
		const n = node as Record<string, any>;
		if (pred(n)) found.push(n);
		for (const key of Object.keys(n)) if (key !== 'parent') visit(n[key]);
	})(subtree);
	return found;
}
const ids = (t: unknown) =>
	new Set(collect(t, (n) => n.type === 'Identifier' && typeof n.name === 'string').map((n) => n.name as string));

describe('AC-3: SendConfirmDialog sendet nicht selbst und sperrt ueber das Modell', () => {
	test('Komponente existiert', () => {
		assert.ok(existsSync(DIALOG), 'molecules/SendConfirmDialog.svelte fehlt (RED)');
	});

	test('baut auf ConfirmDialog auf und bindet `disabled` an `gesperrt` des Modells', () => {
		assert.ok(existsSync(DIALOG), 'molecules/SendConfirmDialog.svelte fehlt (RED)');
		const ast: any = parse(readFileSync(DIALOG, 'utf-8'), { modern: true });
		const dialogs = collect(ast.fragment, (n) => n.type === 'Component' && n.name === 'ConfirmDialog');
		assert.equal(dialogs.length, 1, 'genau ein <ConfirmDialog> erwartet');
		const disabled = dialogs[0].attributes.find((a: any) => a.name === 'disabled');
		assert.ok(disabled, '<ConfirmDialog> hat kein `disabled`-Attribut (Sperre fehlt)');
		assert.ok(ids(disabled.value).has('gesperrt'), '`disabled` haengt nicht an `gesperrt` des Modells');
		const importe = collect(ast.instance, (n) => n.type === 'ImportDeclaration').map((n) => String(n.source.value));
		assert.ok(importe.some((s) => /sendConfirmModel/.test(s)), 'Komponente importiert sendConfirmModel nicht');
	});

	test('die Komponente selbst loest KEINEN Request aus (kein fetch, kein sendSubscription)', () => {
		assert.ok(existsSync(DIALOG), 'molecules/SendConfirmDialog.svelte fehlt (RED)');
		const ast: any = parse(readFileSync(DIALOG, 'utf-8'), { modern: true });
		const alle = ids(ast.instance);
		for (const verboten of ['fetch', 'sendSubscription', 'sendTripBriefing', 'sendComparePreset', 'XMLHttpRequest'])
			assert.ok(!alle.has(verboten), `Komponente benutzt ${verboten} — Versand muss am onConfirm des Aufrufers haengen`);
	});

	test('Props enthalten onConfirm und onCancel; onConfirm wird nur im Bestaetigen-Zweig aufgerufen', () => {
		assert.ok(existsSync(DIALOG), 'molecules/SendConfirmDialog.svelte fehlt (RED)');
		const ast: any = parse(readFileSync(DIALOG, 'utf-8'), { modern: true });
		const dialogs = collect(ast.fragment, (n) => n.type === 'Component' && n.name === 'ConfirmDialog');
		const onConfirm = dialogs[0]?.attributes.find((a: any) => a.name === 'onConfirm');
		assert.ok(onConfirm, '<ConfirmDialog onConfirm=…> fehlt');
		const onCancel = dialogs[0]?.attributes.find((a: any) => a.name === 'onCancel');
		assert.ok(onCancel, '<ConfirmDialog onCancel=…> fehlt');
		assert.ok(!ids(onCancel.value).has('onConfirm'), 'Abbrechen darf onConfirm nicht aufrufen');
	});
});
