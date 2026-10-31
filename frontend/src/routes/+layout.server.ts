import type { LayoutServerLoad } from './$types.js';
import { apiBase as API } from '$lib/server/apiBase.js';
import { onboardingAusProfil } from './_home/onboardingSichtbarkeit.js';


export const load: LayoutServerLoad = async ({ locals, cookies }) => {
	// Issue #642 — Anzeigename für die Seitenleiste durchreichen.
	let displayName: string | null = null;
	// Issue #2248 — beides aus DEMSELBEN Profil-Abruf, kein Zusatzabruf.
	let hasPasskey = false;
	let passkeyPromptDismissed = false;
	// Issue #2155 S4 — Sichtbarkeit des Admin-Eintrags; fail-closed, Go bleibt die Sperre.
	let isAdmin = false;
	// Issue #2521 S2 — Onboarding-Felder aus DEMSELBEN Profil-Abruf (fail-closed).
	let profileJson: Record<string, unknown> | null = null;
	// Issue #2647 — Sprache: Profil (de/en) > locals.lang (Cookie/Header aus hooks.server.ts).
	let lang: 'de' | 'en' = locals.lang ?? 'de';
	if (locals.userId) {
		const session = cookies.get('gz_session');
		const profile = await fetch(`${API()}/api/auth/profile`, {
			headers: { Cookie: `gz_session=${session}` }
		})
			.then((r) => (r.ok ? r.json() : null))
			.catch(() => null);
		profileJson = profile;
		displayName = profile?.display_name ?? null;
		hasPasskey = profile?.has_passkey === true;
		passkeyPromptDismissed = profile?.passkey_prompt_dismissed === true;
		isAdmin = profile?.role === 'admin';
		if (profile?.language === 'de' || profile?.language === 'en') lang = profile.language;
	}
	locals.lang = lang;

	return {
		userId: locals.userId,
		displayName,
		hasPasskey,
		passkeyPromptDismissed,
		isAdmin,
		onboarding: onboardingAusProfil(profileJson),
		lang
	};
};
