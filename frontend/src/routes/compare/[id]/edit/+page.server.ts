import { redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types.js';

// Epic #1273 Slice S3: Die separate Bearbeiten-Seite /compare/[id]/edit entfällt
// zugunsten des Hubs /compare/[id] (EINE Fläche). Diese Route ist nur noch ein
// reiner 307-Redirect (kein CompareEditor-Rendering, kein 404), exaktes Vorbild
// routes/trips/[id]/edit/+page.server.ts (#616). Kein tab-Query-Passthrough nötig:
// alle bekannten Aufrufer verlinken bereits direkt mit dem korrekten ?tab=-Ziel.
// Spec: docs/specs/modules/feat_1273_s3_redirect.md (AC-1).
export const load: PageServerLoad = async ({ params }) => {
	throw redirect(307, `/compare/${params.id}`);
};
