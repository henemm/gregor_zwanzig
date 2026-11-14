<script lang="ts">
	// Issue #2795 S3b, Teilschritt 1b (AC-11 bis AC-21): Warnboxen und EINE Kanal-Tabelle fuer alle
	// vier Kanaele (Kanal · Briefing · Alarme · Alarm schon ab Dringlichkeit). Status, Sperren,
	// Konto-Link und Dringlichkeit kommen aus dem Modell (zustellungModell.ts), die Kanal-Zustaende
	// aus der EINEN Profil-Antwort des Reiters (AC-36). Speichert nicht selbst.
	import { Btn, Dot, Segmented, Switch } from '$lib/components/atoms';
	import { t, locale } from '$lib/i18n';
	import {
		KANAELE,
		KANAL_NAME_KEYS,
		dringlichkeitZelle,
		tabellenKopf,
		warnboxen,
		zaehler,
		type Dringlichkeit,
		type KanalId,
		type KanalStatus,
		type ZustellungStand
	} from '../../shared/zustellung-tab/zustellungModell.ts';

	interface Props {
		stand: ZustellungStand;
		/** null, solange das Profil laedt. */
		status: Record<KanalId, KanalStatus> | null;
		onaendern: (neu: ZustellungStand) => void;
	}
	let { stand, status, onaendern }: Props = $props();

	const TON = { ok: 'good', warn: 'warn', off: 'neutral' } as const;

	const z = $derived(status ? zaehler(stand, status) : null);
	const kopf = $derived.by(() => (void $locale, z ? tabellenKopf(z) : ''));
	const warn = $derived.by(() => (void $locale, z ? warnboxen(z) : { briefing: null, alarme: null }));
	const zellen = $derived.by(() => (void $locale, status ? Object.fromEntries(KANAELE.map((k) => [k, dringlichkeitZelle(k, stand, status)])) : {}));

	function setzeBriefing(k: KanalId, an: boolean): void {
		onaendern({ ...stand, briefing: { ...stand.briefing, [k]: an } });
	}
	function setzeAlarm(k: KanalId, an: boolean): void {
		onaendern({ ...stand, alarme: { ...stand.alarme, [k]: an } });
	}
	function setzeDringlichkeit(k: KanalId, wert: string): void {
		onaendern({ ...stand, dringlichkeit: { ...stand.dringlichkeit, [k]: wert as Dringlichkeit } });
	}
</script>

<div class="zt-kanaele" data-abschnitt="kanaele">
	{#if warn.briefing}
		<div class="zt-warnbox" role="alert" data-testid="zustellung-warnung-briefing">
			<b>{warn.briefing.titel}</b> <span>{warn.briefing.text}</span>
		</div>
	{/if}
	{#if warn.alarme}
		<div class="zt-warnbox" role="alert" data-testid="zustellung-warnung-alarme">
			<b>{warn.alarme.titel}</b> <span>{warn.alarme.text}</span>
		</div>
	{/if}

	<div class="zt-karte">
		{#if !status}
			<p class="zt-laedt" role="status">{$t('zustellung.kanaele.laedt')}</p>
		{:else}
			<div class="zt-kopf">
				<b data-testid="zustellung-kanaele-kopf">{kopf}</b>
				<small data-testid="zustellung-kanaele-unterzeile">{$t('zustellung.kanaele.unterzeile')}</small>
			</div>
			<div class="zt-tabelle-huelle">
				<table class="zt-tabelle" data-testid="zustellung-kanal-tabelle">
					<thead>
						<tr>
							<th>{$t('zustellung.spalte.kanal')}</th>
							<th>{$t('zustellung.spalte.briefing')}</th>
							<th>{$t('zustellung.spalte.alarme')}</th>
							<th>{$t('zustellung.spalte.dringlichkeit')}</th>
						</tr>
					</thead>
					<tbody>
						{#each KANAELE as k (k)}
							{@const st = status[k]}
							{@const name = $t(KANAL_NAME_KEYS[k])}
							{@const zelle = zellen[k]}
							<tr data-testid="zustellung-kanal-{k}">
								<td>
									<b>{name}</b>
									<div class="zt-status" data-testid="zustellung-kanal-{k}-status">
										<Dot tone={TON[st.ton]} size={7} />
										<span>{st.statusText}{st.ziel ? ` · ${st.ziel}` : ''}</span>
									</div>
									{#if st.grund}
										<div class="zt-hinweis" data-testid="zustellung-kanal-{k}-hinweis">
											<span>{st.grund}</span>
											{#if st.kontoLink}
												<Btn href="/account" variant="link" size="xs" data-testid="zustellung-kanal-{k}-konto">{st.kontoLink.text}</Btn>
											{/if}
										</div>
									{/if}
								</td>
								<td>
									<Switch
										checked={stand.briefing[k] && !st.briefingGesperrt}
										disabled={st.briefingGesperrt}
										tap
										aria-label={$t('zustellung.kanal.briefing_aria', { kanal: name })}
										testid="zustellung-kanal-{k}-briefing"
										onchange={(an) => setzeBriefing(k, an)}
									/>
								</td>
								<td>
									{#if st.alarmGesperrt}
										<span class="zt-gesperrt" data-testid="zustellung-kanal-{k}-alarm-gesperrt">{st.alarmSperre}</span>
									{:else}
										<Switch
											checked={stand.alarme[k]}
											tap
											aria-label={$t('zustellung.kanal.alarm_aria', { kanal: name })}
											testid="zustellung-kanal-{k}-alarm"
											onchange={(an) => setzeAlarm(k, an)}
										/>
									{/if}
								</td>
								<td data-testid="zustellung-kanal-{k}-dringlichkeit">
									{#if zelle && zelle.art === 'segment'}
										<Segmented
											rolle="radio"
											size="sm"
											ariaLabel={$t('zustellung.kanal.dringlichkeit_aria', { kanal: name })}
											items={zelle.optionen.map((o) => ({ id: o.wert, label: o.text, testid: `zustellung-kanal-${k}-dringlichkeit-${o.wert}` }))}
											value={zelle.wert}
											onChange={(w: string) => setzeDringlichkeit(k, w)}
										/>
									{:else}
										<span class="zt-strich">–</span>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			<p class="zt-legende" data-testid="zustellung-legende">{$t('zustellung.legende')}</p>
		{/if}
	</div>
</div>

<style>
	.zt-kanaele {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-3);
	}
	.zt-warnbox {
		display: flex;
		flex-wrap: wrap;
		gap: var(--g-s-1);
		padding: var(--g-s-3) var(--g-s-4);
		border: 1px solid var(--g-danger);
		border-radius: var(--g-r-3);
		background: var(--g-danger-bg);
		color: var(--g-danger-fg);
		font-size: var(--g-size-13px);
	}
	.zt-karte {
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3);
		background: var(--g-card);
	}
	.zt-kopf {
		display: flex;
		flex-direction: column;
		gap: var(--g-size-2px);
		padding: var(--g-size-14px) var(--g-s-5);
	}
	.zt-kopf small,
	.zt-laedt {
		font-size: var(--g-size-12-5px);
		color: var(--g-ink-2);
	}
	.zt-laedt {
		margin: 0;
		padding: var(--g-size-14px) var(--g-s-5);
	}
	.zt-tabelle-huelle {
		overflow-x: auto;
	}
	.zt-tabelle {
		width: 100%;
		border-collapse: collapse;
		font-size: var(--g-size-13px);
	}
	.zt-tabelle th {
		text-align: left;
		font-weight: 500;
		font-size: var(--g-size-12-5px);
		color: var(--g-ink-2);
		padding: var(--g-s-2) var(--g-s-5);
		border-top: 1px solid var(--g-rule-soft);
	}
	.zt-tabelle td {
		vertical-align: top;
		padding: var(--g-s-3) var(--g-s-5);
		border-top: 1px solid var(--g-rule-soft);
	}
	.zt-status,
	.zt-hinweis {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--g-s-1);
		margin-top: var(--g-size-2px);
		font-size: var(--g-size-12-5px);
		color: var(--g-ink-2);
	}
	.zt-hinweis {
		color: var(--g-danger-fg);
	}
	.zt-gesperrt,
	.zt-strich {
		font-size: var(--g-size-12-5px);
		color: var(--g-ink-2);
	}
	.zt-legende {
		margin: 0;
		padding: var(--g-s-3) var(--g-s-5) var(--g-size-14px);
		border-top: 1px solid var(--g-rule-soft);
		font-size: var(--g-size-12-5px);
		color: var(--g-ink-2);
	}
</style>
