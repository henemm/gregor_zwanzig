<script lang="ts">
	// Issue #2795 S3b, Teilschritt 1b (AC-24, AC-26): Stille Stunden (von–bis + Schalter) und
	// darunter „Anpassen“ mit dem Mindestabstand zwischen zwei Alarmen derselben Metrik
	// (`alert_cooldown_minutes`, zeigt den gespeicherten Wert, Standard 120). Speichert nicht selbst.
	import { Input, Switch } from '$lib/components/atoms';
	import { Aufklapper, Einstellungszeile } from '$lib/components/molecules';
	import UhrzeitFeld from '$lib/components/molecules/UhrzeitFeld.svelte';
	import { t } from '$lib/i18n';
	import type { ZustellungStand } from '../../shared/zustellung-tab/zustellungModell.ts';

	interface Props {
		stand: ZustellungStand;
		onaendern: (neu: ZustellungStand) => void;
	}
	let { stand, onaendern }: Props = $props();

	// Minutenfeld: Wert erst beim Verlassen uebernehmen (ganze Zahl >= 0), Zwischenstaende nie.
	function cooldownUebernehmen(e: Event): void {
		const roh = (e.currentTarget as HTMLInputElement).value.trim();
		const n = Number(roh);
		if (roh === '' || !Number.isInteger(n) || n < 0) {
			(e.currentTarget as HTMLInputElement).value = String(stand.cooldown);
			return;
		}
		if (n !== stand.cooldown) onaendern({ ...stand, cooldown: n });
	}
</script>

<div class="zt-karte" data-abschnitt="stille-stunden">
	<div class="zt-zeile">
		<div class="zt-text">
			<b>{$t('zustellung.stille.titel')}</b>
			<small data-testid="zustellung-stille-unterzeile">{$t('zustellung.stille.unterzeile')}</small>
		</div>
		<div class="zt-bedienung">
			<UhrzeitFeld value={stand.stilleVon} testid="zustellung-stille-von" ariaLabel={$t('zustellung.stille.von')} onchange={(hhmm) => onaendern({ ...stand, stilleVon: hhmm })} />
			<span class="zt-strich" aria-hidden="true">–</span>
			<UhrzeitFeld value={stand.stilleBis} testid="zustellung-stille-bis" ariaLabel={$t('zustellung.stille.bis')} onchange={(hhmm) => onaendern({ ...stand, stilleBis: hhmm })} />
			<Switch
				checked={stand.stilleAn}
				tap
				aria-label={$t('zustellung.stille.titel')}
				testid="zustellung-stille-schalter"
				onchange={(an) => onaendern({ ...stand, stilleAn: an })}
			/>
		</div>
	</div>
	<Aufklapper titel={$t('zustellung.anpassen.titel')} testid="zustellung-anpassen">
		<Einstellungszeile titel={$t('zustellung.anpassen.cooldown')} hinweis={$t('zustellung.anpassen.cooldown_sub')}>
			<span class="zt-minuten">
				<Input
					type="number"
					min="0"
					step="1"
					inputmode="numeric"
					value={stand.cooldown}
					aria-label={$t('zustellung.anpassen.minuten')}
					data-testid="zustellung-cooldown"
					onchange={cooldownUebernehmen}
				/>
			</span>
			<span class="zt-einheit">{$t('zustellung.anpassen.minuten')}</span>
		</Einstellungszeile>
	</Aufklapper>
</div>

<style>
	.zt-karte {
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3);
		background: var(--g-card);
	}
	.zt-zeile {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--g-size-10px) var(--g-s-4);
		padding: var(--g-size-14px) var(--g-s-5);
	}
	.zt-text {
		display: flex;
		flex-direction: column;
		gap: var(--g-size-2px);
	}
	.zt-text small,
	.zt-einheit {
		font-size: var(--g-size-12-5px);
		color: var(--g-ink-2);
	}
	.zt-bedienung {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--g-s-2);
	}
	.zt-strich {
		color: var(--g-ink-2);
	}
	.zt-minuten {
		display: inline-block;
		width: var(--g-size-72px);
	}
</style>
