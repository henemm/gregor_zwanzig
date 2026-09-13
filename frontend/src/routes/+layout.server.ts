import type { LayoutServerLoad } from './$types.js';
import { apiBase as API } from '$lib/server/apiBase.js';


export const load: LayoutServerLoad = async ({ locals, cookies }) => {
	// Issue #642 — Anzeigename für die Seitenleiste durchreichen.
	let displayName: string | null = null;
	// Issue #2248 — beides aus DEMSELBEN Profil-Abruf, kein Zusatzabruf.
	let hasPasskey = false;
	let passkeyPromptDismissed = false;
	if (locals.userId) {
		const session = cookies.get('gz_session');
		const profile = await fetch(`${API()}/api/auth/profile`, {
			headers: { Cookie: `gz_session=${session}` }
		})
			.then((r) => (r.ok ? r.json() : null))
			.catch(() => null);
		displayName = profile?.display_name ?? null;
		hasPasskey = profile?.has_passkey === true;
		passkeyPromptDismissed = profile?.passkey_prompt_dismissed === true;
	}

	return {
		userId: locals.userId,
		displayName,
		hasPasskey,
		passkeyPromptDismissed
	};
};
