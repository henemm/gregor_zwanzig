// Issue #2139: Fail-Fast fuer das Session-Secret im Frontend-Server.
//
// Ohne diese Pruefung fiele hooks.server.ts still auf das oeffentlich im Repo
// stehende Default-Secret zurueck — damit koennte jede Person ein gueltiges
// gz_session-Cookie fuer eine beliebige user_id selbst signieren.

const DEFAULT_SESSION_SECRET = 'dev-secret-change-me';
const MIN_SESSION_SECRET_LEN = 32;

export function assertSessionSecretConfigured(secret: string | undefined): void {
	if (!secret) {
		throw new Error('GZ_SESSION_SECRET ist nicht gesetzt');
	}
	if (secret === DEFAULT_SESSION_SECRET) {
		throw new Error('GZ_SESSION_SECRET traegt noch das Default-Literal');
	}
	if (secret.length < MIN_SESSION_SECRET_LEN) {
		throw new Error('GZ_SESSION_SECRET ist kuerzer als 32 Zeichen');
	}
}
