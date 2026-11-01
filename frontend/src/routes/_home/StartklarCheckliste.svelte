<script lang="ts">
	// Issue #2521 S2 — Startklar-Checkliste. Zeigt den Stand (drei Pflichtpunkte,
	// zwei Info-Punkte); ob sie erscheint, entscheidet onboardingSichtbarkeit.ts.
	import { t, locale } from '$lib/i18n/index.js';
	import { fmtDateNumeric } from '$lib/i18n/format.js';
	import { Btn } from '$lib/components/atoms';
	import {
		checklistePunkte,
		tarifHinweise,
		type OnboardingProfil,
		type PunktId
	} from './onboardingSichtbarkeit.js';

	let {
		profil,
		tripCount,
		compareCount,
		testmailStatus = 'idle',
		testmailFehler = null,
		onTestmail,
		onAusblenden
	}: {
		profil: OnboardingProfil;
		tripCount: number;
		compareCount: number;
		testmailStatus?: 'idle' | 'loading' | 'error';
		testmailFehler?: string | null;
		onTestmail?: () => void;
		onAusblenden?: () => void;
	} = $props();

	const punkte = $derived(checklistePunkte(profil, { tripCount, compareCount }));
	const hinweise = $derived(tarifHinweise(profil));

	const LABEL: Record<PunktId, () => string> = {
		email: () => $t('onboarding.checkliste.email'),
		'trip-oder-vergleich': () => $t('onboarding.checkliste.trip_oder_vergleich'),
		'erstes-briefing': () => $t('onboarding.checkliste.erstes_briefing'),
		testmail: () => $t('onboarding.checkliste.testmail_gesendet'),
		telegram: () => $t('onboarding.checkliste.telegram')
	};

	// #2651 (F2): Datum in der Sprache der Anfrage (de 30.10.2026, en 30 Oct 2026).
	function datum(iso: string | null): string {
		if (!iso) return '';
		return fmtDateNumeric(new Date(iso), $locale);
	}
</script>

<section
	data-testid="startklar-checkliste"
	style="background: var(--g-card); color: var(--g-ink-2); border: 1px solid var(--g-rule); border-radius: 10px; padding: 18px 22px; margin-bottom: 28px;"
>
	<div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px;">
		<h2 style="font-size: 16px; font-weight: 600; margin: 0; color: var(--g-ink);">{$t('onboarding.checkliste.titel')}</h2>
		<Btn variant="quiet" size="sm" data-testid="startklar-ausblenden" onclick={() => onAusblenden?.()}>
			{$t('onboarding.checkliste.ausblenden')}
		</Btn>
	</div>
	<ul style="list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px;">
		{#each punkte as p (p.id)}
			<li
				data-testid="startklar-punkt-{p.id}"
				data-pflicht={p.pflicht ? 'true' : 'false'}
				data-erledigt={p.erledigt ? 'true' : 'false'}
				style="display: flex; align-items: center; gap: 10px; font-size: 14px; color: var(--g-ink-2);"
			>
				<span aria-hidden="true" style="font-weight: 700; color: {p.erledigt ? 'var(--g-success)' : 'var(--g-ink-2)'};">{p.erledigt ? '✓' : '○'}</span>
				{#if p.id !== 'testmail' || p.erledigt}
					<span>
						{LABEL[p.id]()}{#if p.id === 'testmail'} {datum(profil.testMailSentAt)}{/if}
					</span>
				{/if}
				{#if p.id === 'testmail' && !p.erledigt}
					<Btn
						variant="outline"
						size="sm"
						data-testid="startklar-testmail-senden"
						disabled={testmailStatus === 'loading'}
						onclick={() => onTestmail?.()}
					>{$t('onboarding.checkliste.testmail_senden')}</Btn>
				{/if}
			</li>
		{/each}
	</ul>
	{#if testmailStatus === 'loading'}
		<p style="margin: 8px 0 0; font-size: 13px; color: var(--g-ink-2);">{$t('onboarding.testmail.laeuft')}</p>
	{:else if testmailStatus === 'error'}
		<p role="alert" data-testid="startklar-testmail-fehler" style="margin: 8px 0 0; font-size: 13px; color: var(--g-ink-2);">{testmailFehler ?? $t('onboarding.testmail.fehler')}</p>
	{/if}
	{#each hinweise as h (h)}
		<p data-testid="startklar-hinweis-{h}" style="margin: 10px 0 0; font-size: 13px; color: var(--g-ink-2);">
			{h === 'sms' ? $t('onboarding.hinweis.sms') : $t('onboarding.hinweis.premium_sms')}
		</p>
	{/each}
	<p style="margin: 12px 0 0; font-size: 13px;">
		<a href="/hilfe" data-testid="startklar-hilfe" style="color: var(--g-ink); text-decoration: underline;">{$t('onboarding.checkliste.hilfe')}</a>
	</p>
</section>
