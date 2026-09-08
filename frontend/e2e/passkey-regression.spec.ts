// TDD RED — Issue #2130 (Scheibe A zu Epic #2127).
// Spec: docs/specs/modules/passkey_rp_konfiguration.md — AC-2, AC-3
//
// Der einzige Nachweis, den keine Kern-Schicht erbringen kann: die WebAuthn-
// Zeremonie scheitert bei falscher RP-ID/Origin CLIENTSEITIG mit SecurityError,
// bevor irgendein HTTP-Request das Backend erreicht — genau der Mechanismus, der
// den Prod-Ausfall drei Monate verdeckt hat. Deshalb echter Chromium mit
// virtuellem CDP-Authentifikator gegen den echten lokalen Go-Server.
//
// Kein Mock: der virtuelle Authentifikator ist Chromiums eigene CTAP2-
// Implementierung, die Signaturen erzeugt, die der Go-Server kryptografisch
// prueft. Keine UI-Abhaengigkeit — die Passkey-UI ist in dieser Scheibe bewusst
// ausgeklammert (#2199); der Ablauf laeuft per page.evaluate() + fetch() gegen
// die echten Routen (/api/... geht ueber den SvelteKit-Proxy an GZ_API_BASE).
//
// Voraussetzung im lokalen Lauf: der Go-Server muss http://localhost:4173 als
// erlaubten Origin und "localhost" als RP-ID fuehren (start-preview.sh /
// ci-stack.sh, Spec-Abschnitt "Weitere betroffene Dateien"). Ohne das lehnt
// go-webauthn die Origin ab (protocol/client.go:219-229, Prueflung inkl. Port).
//
// Ausfuehrung:
//   cd frontend && npx playwright test e2e/passkey-regression.spec.ts

import { test, expect } from '@playwright/test';
import type { CDPSession } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard.ts';

const REGISTER_BEGIN = '/api/auth/passkey/register/begin';
const REGISTER_FINISH = '/api/auth/passkey/register/finish';
const DISCOVERABLE_BEGIN = '/api/auth/passkey/discoverable/begin';
const DISCOVERABLE_FINISH = '/api/auth/passkey/discoverable/finish';

/** Was im Browser passiert ist — Rueckgabe von page.evaluate(). */
type Zeremonie = {
	beginStatus: number;
	finishStatus: number;
	finishBody: string;
	credentialId: string;
	fehler: string | null;
};

/** CDP-Antwort von WebAuthn.addVirtualAuthenticator. */
type VirtuellerAuthenticator = { authenticatorId: string };

/** CDP-Antwort von WebAuthn.getCredentials. */
type GespeicherteCredentials = {
	credentials: { credentialId: string; isResidentCredential: boolean }[];
};

test.describe('Passkey-Regression (#2130)', () => {
	let cdp: CDPSession;
	let authenticatorId = '';
	let credentialId = '';

	test.beforeEach(async ({ page, context, baseURL }) => {
		// Issue #1265: niemals gegen Produktion.
		assertNotProdBaseURL(baseURL ?? '');

		cdp = await context.newCDPSession(page);
		await cdp.send('WebAuthn.enable');
		const antwort = (await cdp.send('WebAuthn.addVirtualAuthenticator', {
			options: {
				protocol: 'ctap2',
				transport: 'internal',
				hasResidentKey: true,
				hasUserVerification: true,
				isUserVerified: true,
				automaticPresenceSimulation: true
			}
		})) as unknown as VirtuellerAuthenticator;
		authenticatorId = antwort.authenticatorId;

		await page.goto('/');
	});

	test.afterEach(async ({ page, context }) => {
		// Aufraeumen: der angelegte Passkey haengt sonst dauerhaft am E2E-Nutzer.
		if (credentialId) {
			await page
				.evaluate(
					async (id) =>
						void (await fetch(`/api/auth/passkey/credentials/${id}`, { method: 'DELETE' })),
					credentialId
				)
				.catch(() => undefined);
			credentialId = '';
		}
		if (authenticatorId) {
			await cdp
				.send('WebAuthn.removeVirtualAuthenticator', { authenticatorId })
				.catch(() => undefined);
			authenticatorId = '';
		}
		await context.clearCookies().catch(() => undefined);
	});

	test('AC-2/AC-3: Registrierung und Anmeldung ohne Benutzernamen laufen durch, das Credential ist auffindbar', async ({
		page,
		context
	}) => {
		// -------------------------------------------------------------------
		// Schritt 1 (AC-2): Registrierung. Mit der alten RP-ID "localhost" auf
		// einer anderen Origin bricht navigator.credentials.create hier mit
		// SecurityError ab — dann steht der Grund in `fehler`.
		// -------------------------------------------------------------------
		const registrierung = await page.evaluate(
			async ([beginUrl, finishUrl]) => {
				const b64urlToBuf = (s: string): ArrayBuffer => {
					const b64 = s.replace(/-/g, '+').replace(/_/g, '/');
					const bin = atob(b64 + '==='.slice((b64.length + 3) % 4));
					const buf = new Uint8Array(bin.length);
					for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
					return buf.buffer;
				};
				const bufToB64url = (b: ArrayBuffer): string => {
					let s = '';
					for (const x of new Uint8Array(b)) s += String.fromCharCode(x);
					return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
				};

				const ergebnis = {
					beginStatus: 0,
					finishStatus: 0,
					finishBody: '',
					credentialId: '',
					fehler: null as string | null
				};
				try {
					const beginRes = await fetch(beginUrl, { method: 'POST' });
					ergebnis.beginStatus = beginRes.status;
					if (!beginRes.ok) return ergebnis;

					const pk = (await beginRes.json()).publicKey;
					const options: PublicKeyCredentialCreationOptions = {
						...pk,
						challenge: b64urlToBuf(pk.challenge),
						user: { ...pk.user, id: b64urlToBuf(pk.user.id) },
						excludeCredentials: (pk.excludeCredentials ?? []).map(
							(c: { id: string; type: string }) => ({ ...c, id: b64urlToBuf(c.id) })
						)
					};

					const cred = (await navigator.credentials.create({
						publicKey: options
					})) as PublicKeyCredential | null;
					if (!cred) {
						ergebnis.fehler = 'navigator.credentials.create lieferte null';
						return ergebnis;
					}
					const att = cred.response as AuthenticatorAttestationResponse;
					ergebnis.credentialId = bufToB64url(cred.rawId);

					const finishRes = await fetch(finishUrl, {
						method: 'POST',
						headers: { 'Content-Type': 'application/json' },
						body: JSON.stringify({
							id: cred.id,
							rawId: bufToB64url(cred.rawId),
							type: cred.type,
							label: 'E2E-GZ-Passkey-2130',
							response: {
								attestationObject: bufToB64url(att.attestationObject),
								clientDataJSON: bufToB64url(att.clientDataJSON)
							}
						})
					});
					ergebnis.finishStatus = finishRes.status;
					ergebnis.finishBody = (await finishRes.text()).slice(0, 400);
				} catch (e) {
					ergebnis.fehler = String(e);
				}
				return ergebnis;
			},
			[REGISTER_BEGIN, REGISTER_FINISH]
		);

		expect(
			registrierung.fehler,
			'die Registrierungs-Zeremonie brach im Browser ab — bei SecurityError passt die RP-ID nicht zur Origin (genau der Defekt aus #2130)'
		).toBeNull();
		expect(registrierung.beginStatus, `register/begin: ${registrierung.finishBody}`).toBe(200);
		expect(registrierung.finishStatus, `register/finish: ${registrierung.finishBody}`).toBe(200);
		expect(registrierung.credentialId).not.toBe('');
		credentialId = registrierung.credentialId;

		// -------------------------------------------------------------------
		// Schritt 2 (AC-3, Beleg 2): der Authentifikator hat ein AUFFINDBARES
		// Credential gespeichert — nur dann ist eine Anmeldung ohne
		// Benutzernamen ueberhaupt moeglich.
		// -------------------------------------------------------------------
		const gespeichert = (await cdp.send('WebAuthn.getCredentials', {
			authenticatorId
		})) as unknown as GespeicherteCredentials;

		expect(gespeichert.credentials.length, 'kein Credential im virtuellen Authentifikator').toBe(1);
		expect(
			gespeichert.credentials[0].isResidentCredential,
			'das Credential wurde nicht auffindbar (resident) gespeichert — dann taucht der Passkey im Autofill-Dialog womoeglich gar nicht auf'
		).toBe(true);

		// -------------------------------------------------------------------
		// Schritt 3 (AC-2/AC-3, Beleg 1): Anmeldung OHNE Benutzernamen. Die
		// bestehende Sitzung wird vorher verworfen, damit das Session-Cookie
		// nachweislich aus dieser Zeremonie stammt.
		// -------------------------------------------------------------------
		await context.clearCookies();
		const vorher = await context.cookies();
		expect(vorher.find((c) => c.name === 'gz_session')).toBeUndefined();

		const anmeldung = await page.evaluate(
			async ([beginUrl, finishUrl]) => {
				const b64urlToBuf = (s: string): ArrayBuffer => {
					const b64 = s.replace(/-/g, '+').replace(/_/g, '/');
					const bin = atob(b64 + '==='.slice((b64.length + 3) % 4));
					const buf = new Uint8Array(bin.length);
					for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
					return buf.buffer;
				};
				const bufToB64url = (b: ArrayBuffer): string => {
					let s = '';
					for (const x of new Uint8Array(b)) s += String.fromCharCode(x);
					return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
				};

				const ergebnis = {
					beginStatus: 0,
					finishStatus: 0,
					finishBody: '',
					credentialId: '',
					fehler: null as string | null
				};
				try {
					const beginRes = await fetch(beginUrl, { method: 'POST' });
					ergebnis.beginStatus = beginRes.status;
					if (!beginRes.ok) return ergebnis;

					const pk = (await beginRes.json()).publicKey;
					// KEINE allowCredentials, KEIN mediation:'conditional' (Spec AC-3):
					// der Browser muss den Passkey allein aus seinem Speicher finden.
					const options: PublicKeyCredentialRequestOptions = {
						...pk,
						challenge: b64urlToBuf(pk.challenge),
						allowCredentials: []
					};

					const assertion = (await navigator.credentials.get({
						publicKey: options
					})) as PublicKeyCredential | null;
					if (!assertion) {
						ergebnis.fehler = 'navigator.credentials.get lieferte null';
						return ergebnis;
					}
					const ass = assertion.response as AuthenticatorAssertionResponse;
					ergebnis.credentialId = bufToB64url(assertion.rawId);

					const finishRes = await fetch(finishUrl, {
						method: 'POST',
						headers: { 'Content-Type': 'application/json' },
						body: JSON.stringify({
							id: assertion.id,
							rawId: bufToB64url(assertion.rawId),
							type: assertion.type,
							response: {
								authenticatorData: bufToB64url(ass.authenticatorData),
								clientDataJSON: bufToB64url(ass.clientDataJSON),
								signature: bufToB64url(ass.signature),
								userHandle: ass.userHandle ? bufToB64url(ass.userHandle) : null
							}
						})
					});
					ergebnis.finishStatus = finishRes.status;
					ergebnis.finishBody = (await finishRes.text()).slice(0, 400);
				} catch (e) {
					ergebnis.fehler = String(e);
				}
				return ergebnis;
			},
			[DISCOVERABLE_BEGIN, DISCOVERABLE_FINISH]
		);

		expect(
			anmeldung.fehler,
			'die Anmelde-Zeremonie brach im Browser ab — bei SecurityError passt die RP-ID nicht zur Origin'
		).toBeNull();
		expect(anmeldung.beginStatus, `discoverable/begin: ${anmeldung.finishBody}`).toBe(200);
		expect(
			anmeldung.finishStatus,
			`discoverable/finish (Anmeldung ohne Benutzername): ${anmeldung.finishBody}`
		).toBe(200);
		expect(
			anmeldung.credentialId,
			'die Anmeldung benutzte ein anderes Credential als das eben registrierte'
		).toBe(registrierung.credentialId);

		// AC-2: gueltige Sitzung — das Cookie ist nach der Zeremonie gesetzt.
		const nachher = await context.cookies();
		const session = nachher.find((c) => c.name === 'gz_session');
		expect(
			session,
			'nach erfolgreicher Passkey-Anmeldung fehlt das gz_session-Cookie — keine gueltige Sitzung'
		).toBeTruthy();
		expect(session?.value ?? '').not.toBe('');
	});
});
