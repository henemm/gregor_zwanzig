/**
 * Passkey/WebAuthn browser helper — Issue #450 V1 Add-on.
 *
 * Wraps the @github/webauthn-json browser-ponyfill so the rest of the app
 * never has to touch raw ArrayBuffer ↔ Base64URL conversion. The Go backend
 * speaks the canonical JSON encoding from the WebAuthn spec; this module is
 * the only place that has to know it.
 */

import {
	create,
	get,
	parseCreationOptionsFromJSON,
	parseRequestOptionsFromJSON
} from '@github/webauthn-json/browser-ponyfill';

export function isWebAuthnSupported(): boolean {
	return typeof window !== 'undefined' && !!window.PublicKeyCredential;
}

export interface RegisteredPasskey {
	id: string;
	label: string;
	created_at: string;
}

/**
 * Register a new Passkey for the currently-authenticated user. Requires a
 * valid session cookie. Throws on any failure (network, user-cancel, server
 * rejection).
 */
export async function registerPasskey(label: string): Promise<RegisteredPasskey> {
	const beginRes = await fetch('/api/auth/passkey/register/begin', {
		method: 'POST',
		credentials: 'include'
	});
	if (!beginRes.ok) {
		throw new Error('register_begin_failed');
	}
	const options = parseCreationOptionsFromJSON(await beginRes.json());

	// navigator.credentials.create() — opens the browser/OS UI prompt.
	const credential = await create(options);

	const finishRes = await fetch('/api/auth/passkey/register/finish', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		credentials: 'include',
		body: JSON.stringify({ ...credential.toJSON(), label })
	});
	if (!finishRes.ok) {
		throw new Error('register_finish_failed');
	}
	return (await finishRes.json()) as RegisteredPasskey;
}

/**
 * Authenticate the user via a previously-registered Passkey. On success the
 * server sets a `gz_session` cookie and we reload the page so SvelteKit picks
 * up the new auth state.
 */
export async function loginWithPasskey(username: string): Promise<void> {
	const beginRes = await fetch('/api/auth/passkey/login/begin', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ username })
	});
	if (!beginRes.ok) {
		throw new Error('invalid_credentials');
	}
	const options = parseRequestOptionsFromJSON(await beginRes.json());

	// navigator.credentials.get() — opens the browser/OS UI prompt.
	const credential = await get(options);

	const finishRes = await fetch('/api/auth/passkey/login/finish', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		credentials: 'include',
		body: JSON.stringify(credential.toJSON())
	});
	if (!finishRes.ok) {
		throw new Error('invalid_credentials');
	}
	// Cookie is now set; reload so the SvelteKit root layout sees it.
	window.location.assign('/');
}

/**
 * Authenticate the user via Discoverable Credentials + Conditional UI (Issue #467).
 * No username required — the browser surfaces all passkeys for this RP as an
 * autofill picker on focus of a `autocomplete="username webauthn"` input.
 *
 * The `signal` lets the caller abort the pending picker (e.g. when the user
 * clicks the explicit "Mit Passkey anmelden" button instead).
 */
export async function loginWithDiscoverablePasskey(signal?: AbortSignal): Promise<void> {
	const beginRes = await fetch('/api/auth/passkey/discoverable/begin', { method: 'POST' });
	if (!beginRes.ok) throw new Error('begin_failed');
	const options = await beginRes.json();

	// Direct navigator.credentials.get call so `mediation: 'conditional'` and
	// `signal` are guaranteed to reach the browser (the @github/webauthn-json
	// browser-ponyfill strips both).
	const credential = (await navigator.credentials.get({
		publicKey: options.publicKey,
		mediation: 'conditional' as CredentialMediationRequirement,
		signal
	} as CredentialRequestOptions)) as PublicKeyCredential | null;

	if (!credential) throw new Error('no_credential');

	const response = credential.response as AuthenticatorAssertionResponse;
	const b64url = (buf: ArrayBuffer): string =>
		btoa(Array.from(new Uint8Array(buf), (b) => String.fromCharCode(b)).join(''))
			.replace(/\+/g, '-')
			.replace(/\//g, '_')
			.replace(/=/g, '');

	const body = {
		id: credential.id,
		rawId: b64url(credential.rawId),
		type: credential.type,
		response: {
			clientDataJSON: b64url(response.clientDataJSON),
			authenticatorData: b64url(response.authenticatorData),
			signature: b64url(response.signature),
			userHandle: response.userHandle ? b64url(response.userHandle) : null
		}
	};

	const finishRes = await fetch('/api/auth/passkey/discoverable/finish', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		credentials: 'include',
		body: JSON.stringify(body)
	});
	if (!finishRes.ok) throw new Error('invalid_credentials');
	window.location.assign('/');
}

/**
 * Remove a previously-registered Passkey by its base64url-encoded credential
 * ID (as returned by `/api/auth/profile`). Returns nothing — the caller should
 * refresh the profile after a successful call.
 */
export async function deletePasskey(credentialId: string): Promise<void> {
	const res = await fetch(`/api/auth/passkey/credentials/${encodeURIComponent(credentialId)}`, {
		method: 'DELETE',
		credentials: 'include'
	});
	if (!res.ok) {
		throw new Error('delete_failed');
	}
}
