// Issue #2278 (AC-10) — geteilter, fail-soft Profil-Loader fuer Seiten mit Sende-Dialog.
// Muster routes/compare/+page.server.ts: Session-Cookie durchreichen, die User-ID leitet der
// Go-Handler daraus ab; das Frontend baut NIE einen user_id-Parameter. Ohne Session oder bei
// jedem Fehler: null — nie ein Rueckfall auf einen Default-Nutzer.

import { apiBase as API } from '$lib/server/apiBase.js';

export async function loadProfile(
	cookies: { get(name: string): string | undefined }
): Promise<Record<string, unknown> | null> {
	const session = cookies.get('gz_session');
	if (!session) return null;
	try {
		const res = await fetch(`${API()}/api/auth/profile`, {
			headers: { 'Content-Type': 'application/json', Cookie: `gz_session=${session}` }
		});
		return res.ok ? ((await res.json()) as Record<string, unknown>) : null;
	} catch {
		return null;
	}
}
