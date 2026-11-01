<script lang="ts">
	import { EmptyState } from '$lib/components/ui/empty-state/index.js';
	import { Btn } from '$lib/components/atoms';
	import { t } from '$lib/i18n/index.js';

	// Issue #2521 S2 — `willkommen`: Willkommens-Hinweis fuer neu angelegte Konten
	// (Sichtbarkeit entscheidet onboardingSichtbarkeit.ts in der Seite). Ohne
	// Flag bleibt der normale Leerzustand (Bestandskonten).
	let {
		willkommen = false,
		testmailStatus = 'idle',
		testmailFehler = null,
		onTestmail,
		onVerstanden
	}: {
		willkommen?: boolean;
		testmailStatus?: 'idle' | 'loading' | 'error';
		testmailFehler?: string | null;
		onTestmail?: () => void;
		onVerstanden?: () => void;
	} = $props();
</script>

{#if willkommen}
	<section
		data-testid="onboarding-willkommen"
		style="color: var(--g-ink-2); border: 1px solid var(--g-rule); border-radius: 10px; padding: 24px 26px; margin-bottom: 28px; text-align: center;"
	>
		<h2 style="font-size: 22px; font-weight: 600; margin: 0 0 8px; color: var(--g-ink);">{$t('onboarding.willkommen.titel')}</h2>
		<p style="font-size: 14px; line-height: 1.5; margin: 0 auto 16px; max-width: 560px; color: var(--g-ink-2);">{$t('onboarding.willkommen.text')}</p>
		<div style="display: flex; gap: 0.75rem; flex-wrap: wrap; justify-content: center;">
			<Btn variant="accent" href="/trips/new">{$t('onboarding.willkommen.neuer_trip')}</Btn>
			<Btn variant="outline" href="/compare/new">{$t('onboarding.willkommen.neuer_vergleich')}</Btn>
			<Btn
				variant="outline"
				data-testid="onboarding-testmail-senden"
				disabled={testmailStatus === 'loading'}
				onclick={() => onTestmail?.()}
			>{$t('onboarding.willkommen.testmail')}</Btn>
			<Btn variant="quiet" data-testid="onboarding-willkommen-verstanden" onclick={() => onVerstanden?.()}>
				{$t('onboarding.willkommen.verstanden')}
			</Btn>
		</div>
		{#if testmailStatus === 'loading'}
			<p style="margin: 10px 0 0; font-size: 13px; color: var(--g-ink-2);">{$t('onboarding.testmail.laeuft')}</p>
		{:else if testmailStatus === 'error'}
			<p role="alert" style="margin: 10px 0 0; font-size: 13px; color: var(--g-ink-2);">{testmailFehler ?? $t('onboarding.testmail.fehler')}</p>
		{/if}
	</section>
{:else}
	<EmptyState title={$t('onboarding.leer.titel')} description={$t('onboarding.leer.beschreibung')}>
		<div style="display: flex; gap: 0.75rem; flex-wrap: wrap; justify-content: center;">
			<Btn variant="accent" href="/trips/new">{$t('onboarding.willkommen.neuer_trip')}</Btn>
			<Btn variant="outline" href="/compare/new">{$t('onboarding.willkommen.neuer_vergleich')}</Btn>
		</div>
	</EmptyState>
{/if}
