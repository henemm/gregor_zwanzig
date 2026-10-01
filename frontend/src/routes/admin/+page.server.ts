import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types.js';
import { apiBase as API } from '$lib/server/apiBase.js';
import type { AdminUser } from '$lib/types';

// Issue #2155 S4 — Zugriffsschutz als Komfort (keine leere Seite); die eigentliche
// Sperre bleibt requireAdmin in Go (ADR-0078).
export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('gz_session');
	const h = { headers: { Cookie: `gz_session=${session}` } };

	const profile = await fetch(`${API()}/api/auth/profile`, h)
		.then((r) => (r.ok ? r.json() : null))
		.catch(() => null);
	if (!profile) error(401, 'Nicht angemeldet');
	if (profile.role !== 'admin') error(403, 'Keine Berechtigung');

	const res = await fetch(`${API()}/api/admin/users`, h).catch(() => null);
	if (!res) error(502, 'Nutzerliste nicht erreichbar');
	if (res.status === 401 || res.status === 403) error(res.status, 'Keine Berechtigung');
	if (!res.ok) error(502, 'Nutzerliste nicht erreichbar');
	const body = await res.json().catch(() => null);

	const users: AdminUser[] = Array.isArray(body?.users) ? body.users : [];
	return { users, selfId: typeof profile.id === 'string' ? profile.id : '' };
};
