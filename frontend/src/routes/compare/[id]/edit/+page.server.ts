import { env } from '$env/dynamic/private';
import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types.js';
import type { Location, Subscription } from '$lib/types.js';

// Issue #440 — Compare-Wizard Edit-Modus.
// Spec: docs/specs/modules/issue_440_compare_wizard_shell_step1_step2.md §9
//
// Laedt bestehende Subscription + Locations-Library; +page.svelte prefilled
// daraus den CompareWizardState im Mount.

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ cookies, params }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	const [subRes, locsRes] = await Promise.all([
		fetch(`${API()}/api/subscriptions/${params.id}`, { headers }).catch(() => null),
		fetch(`${API()}/api/locations`, { headers }).catch(() => null)
	]);

	if (!subRes?.ok) error(404, 'Vergleich nicht gefunden');

	const subscription: Subscription = await subRes.json();
	const locations: Location[] = locsRes?.ok ? await locsRes.json() : [];

	return {
		subscription,
		locations: Array.isArray(locations) ? locations : []
	};
};
