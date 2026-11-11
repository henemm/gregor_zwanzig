// Issue #2390: Entscheidung, ob der gespeicherte Anmeldezustand
// (playwright/.auth/admin.json) wiederverwendet werden darf oder ob sich das
// E2E-Setup neu anmelden muss. Die Ablaufzeit allein reicht nicht: nach einem
// Stack-Neustart (neues Session-Secret) lehnt der Server die Cookies mit 401
// ab. Deshalb zusaetzlich eine echte Probe gegen GET /api/auth/profile
// (authentifiziert; /api/health ist oeffentlich und taugt nicht).
// Fail-closed: nur Status 200 heisst "wiederverwenden".

import * as fs from 'node:fs';
import type { BrowserContext } from '@playwright/test';

export const AUTH_PROBE_PATH = '/api/auth/profile';

/** Schmale Sicht auf Playwrights APIRequestContext (page.request). */
export interface AuthProbeRequest {
	get(url: string): Promise<{ status(): number }>;
}

export interface AuthStateDecision {
	reuse: boolean;
	reason: string;
}

/** Bisherige Zeitpruefung: Datei vorhanden, gz_session-Cookie noch >60 s gueltig. */
function checkExpiry(authFile: string): string | null {
	if (!fs.existsSync(authFile)) return 'Anmeldezustand fehlt';
	try {
		const state = JSON.parse(fs.readFileSync(authFile, 'utf-8'));
		const cookies = state.cookies ?? [];
		const sessionCookie = cookies.find(
			(c: { name: string; expires: number }) => c.name === 'gz_session'
		);
		if (!sessionCookie) return 'Anmeldezustand ohne Sitzungs-Cookie';
		if (sessionCookie.expires * 1000 > Date.now() + 60_000) return null;
		return 'Anmeldezustand abgelaufen';
	} catch {
		return 'Anmeldezustand nicht lesbar';
	}
}

export async function decideAuthState(opts: {
	authFile: string;
	request: AuthProbeRequest;
}): Promise<AuthStateDecision> {
	const expiryProblem = checkExpiry(opts.authFile);
	if (expiryProblem) return { reuse: false, reason: expiryProblem };

	try {
		const res = await opts.request.get(AUTH_PROBE_PATH);
		const status = res.status();
		if (status === 200) return { reuse: true, reason: 'Anmeldezustand vom Server akzeptiert' };
		return { reuse: false, reason: `Anmeldezustand vom Server abgelehnt (${status})` };
	} catch (err) {
		const msg = err instanceof Error ? err.message : String(err);
		return { reuse: false, reason: `Probe des Anmeldezustands fehlgeschlagen (${msg})` };
	}
}

/** Schmale Sicht auf Playwrights BrowserContext (page.context()). */
export interface AuthProbeContext {
	addCookies(cookies: Parameters<BrowserContext['addCookies']>[0]): Promise<void>;
	clearCookies(): Promise<void>;
}

/**
 * Kompletter Ablauf vor dem Login-Zweig: gespeicherte Cookies (falls die
 * Datei lesbar ist) in den Kontext setzen, Entscheidung treffen und bei
 * "neu anmelden" Grund protokollieren und den Kontext leeren.
 */
export async function prepareAuthState(opts: {
	authFile: string;
	context: AuthProbeContext;
	request: AuthProbeRequest;
	log: (message: string) => void;
}): Promise<AuthStateDecision> {
	if (fs.existsSync(opts.authFile)) {
		try {
			const cookies = JSON.parse(fs.readFileSync(opts.authFile, 'utf-8')).cookies ?? [];
			await opts.context.addCookies(cookies);
		} catch {
			// unlesbar/ungueltig: decideAuthState liefert den Grund, Login folgt
		}
	}
	const decision = await decideAuthState({ authFile: opts.authFile, request: opts.request });
	if (!decision.reuse) {
		opts.log(`[e2e-setup] ${decision.reason} – melde neu an`);
		await opts.context.clearCookies();
	}
	return decision;
}
