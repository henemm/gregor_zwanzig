<script lang="ts">
	// Issue #2795 S3b, Teilschritt 1b (AC-1): Kopf des Reiters Zustellung (Mockup Fassung 3,
	// `viewZustellung()` `.sectionh`). Trip und Orts-Briefing gleich.
	import { t } from '$lib/i18n';
</script>

<div class="zt-kopf" data-abschnitt="abschnittskopf">
	<h2 data-testid="zustellung-titel">{$t('zustellung.kopf.titel')}</h2>
	<p data-testid="zustellung-erklaer">{$t('zustellung.kopf.erklaer')}</p>
</div>

<style>
	.zt-kopf h2 {
		margin: 0 0 var(--g-s-1);
		font-size: var(--g-size-22px);
		font-weight: 600;
		color: var(--g-ink);
	}
	.zt-kopf p {
		margin: 0;
		font-size: var(--g-size-13px);
		color: var(--g-ink-2);
		line-height: 1.5;
	}
</style>
