<script lang="ts">
	// Issue #3319 (AC-12) — Aufruf zur Registrierung am Ende der Funktionsseiten.
	import { Btn } from '$lib/components/atoms';
	import { t } from '$lib/i18n';
</script>

<section class="cta" data-testid="registrierung" aria-labelledby="cta-titel">
	<h2 id="cta-titel">{$t('funktionen.cta.titel')}</h2>
	<p>{$t('funktionen.cta.text')}</p>
	<div class="knoepfe">
		<Btn variant="primary" size="lg" href="/register">{$t('start.cta.register')}</Btn>
		<Btn variant="outline" size="lg" href="/login">{$t('start.cta.login')}</Btn>
	</div>
</section>

<style>
	.cta {
		background: var(--g-card);
		border: var(--g-size-2px) solid var(--g-ink);
		border-radius: var(--g-r-4);
		padding: var(--g-s-5);
	}
	h2 {
		margin: 0 0 var(--g-size-6px);
		font-size: var(--g-text-xl);
		line-height: 1.3;
		font-weight: 600;
		color: var(--g-ink);
	}
	p {
		margin: 0;
		color: var(--g-ink-2);
		line-height: 1.55;
	}
	.knoepfe {
		display: flex;
		flex-wrap: wrap;
		gap: var(--g-s-3);
		margin-top: var(--g-s-4);
	}
</style>
