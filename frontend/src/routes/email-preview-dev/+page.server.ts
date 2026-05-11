import { redirect } from '@sveltejs/kit';
import { dev } from '$app/environment';

export const load = () => {
	if (!dev) {
		// Issue #183: Dev-Vorschau-Seite — auf Production blocken (Phishing-Schutz).
		// Wird mit Issue #189 (Vorschau-Integration) komplett entfernt.
		throw redirect(307, '/');
	}
};
