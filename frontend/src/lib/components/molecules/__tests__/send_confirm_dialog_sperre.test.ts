// Issue #2278 Fix-Loop (Adversary F001/F002), AC-3: der Bestaetigen-Knopf des Sende-Dialogs
// ist GESPERRT, wenn kein Kanal liefern kann, und waehrend ein Versand laeuft.
//
// Warum nicht `svelte/server` render: der Dialog sitzt auf bits-ui `Dialog` (Portal) — unter
// SSR liefert er KEINEN Inhalt (gemessen, siehe send_confirm_dialog.test.ts). Stattdessen wird
// das ECHTE Instanz-Skript von SendConfirmDialog.svelte mit gesaeten Props ausgewertet
// (Pruefstand `umgebungFuer`, echte Importe inkl. sendConfirmModel) und der Ausdruck, den die
// Komponente WIRKLICH an `<ConfirmDialog disabled=...>` uebergibt, gegen diese Umgebung
// berechnet. Damit faengt der Test jede Verfaelschung der Sperr-Herleitung (z. B.
// `$derived(false)` oder das Weglassen von `|| running`) — nicht nur den Bezeichner-Namen.
// Dass ConfirmDialog `disabled` an den Knopf `send-confirm-yes` weiterreicht, bewacht der
// Durchklick `e2e/aktionsmodell-durchklick.spec.ts` (Test „Sende-Dialog gesperrt").
//
// Pfadregel #1409: relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/molecules/__tests__/send_confirm_dialog_sperre.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
	umgebungFuer,
	findeKomponenten,
	attributAusdruck,
	werte,
	type Knoten
} from '../../shared/__tests__/svelteInstanzPruefstand.ts';

const HIER = path.dirname(fileURLToPath(import.meta.url));
const DIALOG = path.join(HIER, '..', 'SendConfirmDialog.svelte');

const GUELTIG = { mail_to: 'anna@example.org', email_verified: true, telegram_chat_id: 'A-1' };
const OHNE_ADRESSE = { email_verified: true };
const UNBESTAETIGT = { mail_to: 'anna@example.org', email_verified: false };

/** Was die Komponente bei diesen Props an `<ConfirmDialog disabled>` uebergibt. */
async function knopfGesperrt(props: Knoten): Promise<unknown> {
	const { ast, quelle, u } = await umgebungFuer(
		DIALOG,
		{ open: true, onConfirm: () => {}, onCancel: () => {}, ...props },
		{ jsAlsTs: true }
	);
	assert.equal(typeof u.sendConfirmModel, 'function', 'sendConfirmModel wurde nicht gebunden — Messung waere leer');
	const dialoge = findeKomponenten(ast, 'ConfirmDialog');
	assert.equal(dialoge.length, 1, 'genau ein <ConfirmDialog> erwartet');
	const ausdruck = attributAusdruck(dialoge[0], quelle, 'disabled');
	assert.ok(ausdruck, '<ConfirmDialog> hat kein `disabled`-Attribut (Sperre fehlt)');
	return werte(ausdruck, u);
}

describe('AC-3 (F001): Bestaetigen ist gesperrt, wenn kein Kanal liefern kann', () => {
	for (const kind of ['trip', 'vergleich'] as const) {
		test(`${kind}: gueltiges Ziel -> Knopf frei`, async () => {
			assert.equal(await knopfGesperrt({ kind, profile: GUELTIG, subscription: {} }), false);
		});
		test(`${kind}: Profil ohne Adresse -> Knopf gesperrt`, async () => {
			assert.equal(
				await knopfGesperrt({ kind, profile: OHNE_ADRESSE, subscription: { send_telegram: true } }),
				true
			);
		});
		test(`${kind}: Adresse unbestaetigt -> Knopf gesperrt`, async () => {
			assert.equal(await knopfGesperrt({ kind, profile: UNBESTAETIGT, subscription: {} }), true);
		});
		test(`${kind}: kein Profil (null) -> Knopf gesperrt`, async () => {
			assert.equal(await knopfGesperrt({ kind, profile: null, subscription: {} }), true);
		});
	}
});

describe('AC-3 (F002): waehrend ein Versand laeuft, ist Bestaetigen gesperrt', () => {
	for (const kind of ['trip', 'vergleich'] as const) {
		test(`${kind}: gueltiges Ziel + running=true -> gesperrt (kein Doppel-Versand)`, async () => {
			assert.equal(
				await knopfGesperrt({ kind, profile: GUELTIG, subscription: {}, running: true }),
				true
			);
		});
		test(`${kind}: running nicht gesetzt -> Default false, Knopf frei`, async () => {
			assert.equal(await knopfGesperrt({ kind, profile: GUELTIG, subscription: {} }), false);
		});
	}
});
