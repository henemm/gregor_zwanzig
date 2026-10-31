<script lang="ts">
	// Issue #2521 S3 — Hilfeseite „So funktioniert Gregor" (statisch, nur fuer
	// Eingeloggte: /hilfe steht nicht in publicPaths). Abschnitte: Briefing-
	// Zeiten, Alarme, Kanaele (alle vier gleichrangig), nachrangig die
	// Antwort-Befehle. Alle Texte aus dem Katalog (t), die Befehlsliste ist die
	// statische Kopie hilfe.befehle.<wort>.* — Drift-Schutz gegen
	// command_rows(): tests/test_hilfe_befehle_drift.py.
	// Spec: docs/specs/modules/onboarding_standardwerte_hilfe.md
	import { t, type MessageKey } from '$lib/i18n';
	import { de } from '$lib/i18n/messages/de/index';

	const KANAELE: MessageKey[] = [
		'hilfe.kanaele.email',
		'hilfe.kanaele.telegram',
		'hilfe.kanaele.sms',
		'hilfe.kanaele.premium_sms'
	];

	// i18n-dynamic: hilfe.befehle.
	const befehle = $derived(
		Object.keys(de)
			.filter((k) => /^hilfe\.befehle\.[^.]+\.befehl$/.test(k))
			.map((k) => ({
				befehl: $t(k as MessageKey),
				text: $t(k.replace(/\.befehl$/, '.text') as MessageKey)
			}))
	);

	const h2 = 'font-size: 18px; font-weight: 600; margin: 0 0 10px; color: var(--g-ink);';
	const p = 'font-size: 14px; line-height: 1.55; margin: 0 0 8px; color: var(--g-ink-2);';
	const karte = 'background: var(--g-card); border: 1px solid var(--g-rule); border-radius: 10px; padding: 18px 22px; margin-bottom: 20px;';
</script>

<div style="max-width: 760px; padding: 28px 24px 60px;">
	<h1 style="font-size: 28px; font-weight: 600; margin: 0 0 24px; color: var(--g-ink);">{$t('hilfe.titel')}</h1>

	<section data-testid="hilfe-briefing" style={karte}>
		<h2 style={h2}>{$t('hilfe.briefing.titel')}</h2>
		<p style={p}>{$t('hilfe.briefing.morgens')}</p>
		<p style={p}>{$t('hilfe.briefing.abends')}</p>
	</section>

	<section data-testid="hilfe-alarme" style={karte}>
		<h2 style={h2}>{$t('hilfe.alarme.titel')}</h2>
		<p style={p}>{$t('hilfe.alarme.text')}</p>
	</section>

	<section data-testid="hilfe-kanaele" style={karte}>
		<h2 style={h2}>{$t('hilfe.kanaele.titel')}</h2>
		<ul style="list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px;">
			{#each KANAELE as key (key)}
				<li style="{p} margin: 0; padding: 10px 12px; border: 1px solid var(--g-rule); border-radius: 8px;">{$t(key)}</li>
			{/each}
		</ul>
	</section>

	<section data-testid="hilfe-befehle" style="padding: 4px 22px 0;">
		<h2 style="font-size: 15px; font-weight: 600; margin: 0 0 8px; color: var(--g-ink-2);">{$t('hilfe.befehle.titel')}</h2>
		<table style="border-collapse: collapse; font-size: 13px; color: var(--g-ink-2);">
			<tbody>
				{#each befehle as b (b.befehl)}
					<tr>
						<td class="mono" style="padding: 3px 16px 3px 0; white-space: nowrap; color: var(--g-ink);">{b.befehl}</td>
						<td style="padding: 3px 0;">{b.text}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</section>
</div>
