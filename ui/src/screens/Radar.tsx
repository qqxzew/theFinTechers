import { useEffect, useMemo, useState } from 'react';
import { getRadar } from '../api';
import Graph from '../components/Graph';
import { Card, Chip, ErrorBox, Loading, PageHeader, SyntheticBadge } from '../components/ui';
import { useI18n, type I18nKey } from '../i18n';
import { useAsync } from '../state';
import type { RadarResponse, WireMsg } from '../types';

export default function RadarScreen() {
  const { t } = useI18n();
  const r = useAsync(getRadar, []);
  return (
    <div className="space-y-5">
      <PageHeader title={t('r.title')}>
        <SyntheticBadge />
      </PageHeader>
      {r.loading && !r.data ? <Loading /> : r.error ? <ErrorBox error={r.error} onRetry={r.reload} /> : r.data ? <RadarView d={r.data} /> : null}
    </div>
  );
}

function RadarView({ d }: { d: RadarResponse }) {
  const { t, num } = useI18n();
  return (
    <>
      <section aria-labelledby="alone-h">
        <h2 id="alone-h" className="mb-2 text-base font-semibold">
          {t('r.alone')}
        </h2>
        <div className="grid gap-4 md:grid-cols-3">
          {d.banks.map((b) => (
            <Card key={b.bank_id} title={<span className="mono">{b.bank_id}</span>}>
              <div className="mb-3 flex flex-wrap gap-4">
                <Stat n={num(b.n_cases)} l={t('r.cases')} />
                <Stat n={num(b.n_review)} l={t('r.review')} />
                <Stat n={num(b.n_candidates_exported)} l={t('r.exported')} />
              </div>
              <Graph graph={b.local_graph} height={230} layout="concentric" ariaLabel={`${b.bank_id} local graph`} />
            </Card>
          ))}
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-5">
        <Card title={t('r.together')} className="xl:col-span-3" sub={`${t('r.rule')}: ${d.disclosure_rule}`}>
          <Graph graph={d.cluster_graph} height={380} layout="cose" ariaLabel={t('r.together')} />
          <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-4 rounded-sm bg-navy" aria-hidden="true" />
              bank
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full border-2 border-navy" aria-hidden="true" />
              {t('r.candidates')}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rotate-45 bg-warn" aria-hidden="true" />
              {t('r.tokens')} (blinded)
            </span>
          </div>
        </Card>
        <Card title={t('r.clusters')} className="xl:col-span-2">
          <ul className="space-y-3">
            {d.clusters.map((c) => (
              <li key={c.cluster_id} className={`rounded-md border p-3 ${c.disclosed ? 'border-warn/40 bg-warnsoft/40' : 'border-line'}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <Chip tone={c.disclosed ? 'warn' : 'neutral'} mono>
                    ◆ {c.cluster_id}
                  </Chip>
                  <Chip tone={c.disclosed ? 'warn' : 'outline'}>{c.disclosed ? t('r.disclosed') : t('r.withheld')}</Chip>
                  {c.same_hand_global && <Chip tone="navy">{t('r.same_hand')}</Chip>}
                  <span className="ml-auto text-xs text-muted">
                    score <span className="tnum font-semibold text-ink">{num(c.score, 2)}</span>
                  </span>
                </div>
                <p className="mt-1.5 text-xs text-muted tnum">
                  {c.banks.join(', ')} · {c.banks.length} {t('r.banks')} · {c.n_candidates} {t('r.candidates')} · {c.tokens} {t('r.tokens')}
                  {c.lag_ret_concentration !== null && ` · lag/ret ${num(c.lag_ret_concentration, 2)}`}
                </p>
                {d.refused[c.cluster_id] && (
                  <p className="mt-1 text-xs">
                    <span className="text-muted">{t('r.refused_reason')}:</span> {d.refused[c.cluster_id]}
                  </p>
                )}
              </li>
            ))}
          </ul>
          <p className="mt-3 rounded-md bg-paper p-2.5 text-xs text-muted">
            <span className="font-semibold text-ink">{t('r.rule')}:</span> {d.disclosure_rule}
          </p>
        </Card>
      </div>

      <WirePanel wire={d.wire} />

      <ExposureTable d={d} />

      <p role="note" className="rounded-md border border-line bg-surface px-4 py-3 text-sm text-muted">
        {t('r.psi_note')}
      </p>
    </>
  );
}

function Stat({ n, l }: { n: string; l: string }) {
  return (
    <div className="min-w-0">
      <div className="tnum text-lg font-semibold">{n}</div>
      <div className="text-[11px] leading-tight text-muted">{l}</div>
    </div>
  );
}

function WirePanel({ wire }: { wire: WireMsg[] }) {
  const { t, tx, num } = useI18n();
  // Bank-to-bank PSI messages carry hex ciphertext; the coordinator session carries match rows (objects).
  const isPair = (w: WireMsg) => /^[^:x×-]+[:x×-][^:x×-]+$/.test(w.session) && w.sample.every((s) => typeof s === 'string');
  const pairWire = useMemo(() => wire.filter(isPair), [wire]);
  const coordWire = useMemo(() => wire.filter((w) => !isPair(w)), [wire]);
  const sessions = useMemo(() => [...new Set(pairWire.map((w) => w.session))], [pairWire]);
  const [session, setSession] = useState(sessions[0] ?? '');
  const msgs = pairWire.filter((w) => w.session === session);
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  useEffect(() => setStep(0), [session]);
  useEffect(() => {
    if (!playing) return;
    const h = window.setInterval(() => setStep((s) => (s + 1) % Math.max(1, msgs.length)), 2000);
    return () => window.clearInterval(h);
  }, [playing, msgs.length]);

  if (!wire.length) return null;
  const m = msgs[step];
  const [a, b] = session.split(/[:x×-]/);
  const fromA = m ? m.from === a : true;

  return (
    <Card
      title={t('r.wire')}
      sub={t('r.wire_sub')}
      right={
        <>
          <label className="sr-only" htmlFor="sess">
            {t('r.session')}
          </label>
          <select id="sess" className="input py-1 text-xs" value={session} onChange={(e) => setSession(e.target.value)}>
            {sessions.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
          <button className="btn-secondary py-1 text-xs" onClick={() => setPlaying((p) => !p)} aria-pressed={playing}>
            {playing ? t('r.pause') : t('r.play')}
          </button>
        </>
      }
    >
      <ol className="mb-4 flex flex-wrap gap-2" aria-label={t('r.step')}>
        {msgs.map((w, i) => (
          <li key={i}>
            <button
              className={`rounded-md border px-2.5 py-1.5 text-left text-xs ${i === step ? 'border-navy bg-navy/10 text-navy' : 'border-line text-muted hover:text-ink'}`}
              aria-current={i === step ? 'step' : undefined}
              onClick={() => {
                setPlaying(false);
                setStep(i);
              }}
            >
              <span className="tnum font-semibold">{i + 1}.</span> {tx(`msg.${w.msg}`, w.msg)}
            </button>
          </li>
        ))}
      </ol>
      {m && (
        <div className="grid items-center gap-4 md:grid-cols-[110px_1fr_110px]">
          <BankBox id={a} active={fromA} />
          <div className="min-w-0">
            <div className="mb-2 flex items-center gap-2 text-xs text-muted" aria-live="polite">
              <span className="mono">{m.from}</span>
              <span aria-hidden="true">{fromA ? '→' : '←'}</span>
              <span className="mono">{fromA ? b : a}</span>
              <span>·</span>
              <span className="mono">{m.msg}</span>
              <span>·</span>
              <span className="tnum">
                {num(m.n)} {t('r.elements')}
              </span>
            </div>
            <div className="relative h-1 overflow-hidden rounded-full bg-line" aria-hidden="true">
              <span key={`${session}-${step}`} className={`absolute inset-y-0 w-1/4 rounded-full bg-warn motion-safe:animate-[wire_1.8s_ease-in-out_infinite] ${fromA ? '' : '[animation-direction:reverse]'}`} />
            </div>
            <ul className="mt-3 space-y-1 rounded-md bg-ink/[0.04] p-2.5" aria-label="ciphertext samples">
              {m.sample.map((h, i) => {
                const hex = String(h);
                return (
                  <li key={i} className="mono break-all text-[11px] leading-snug text-ink/80" title={hex}>
                    {hex.length > 96 ? `${hex.slice(0, 96)}…` : hex}
                    {hex.length > 96 && <span className="text-muted"> ({num(hex.length / 2)} B, {t('r.truncated')})</span>}
                  </li>
                );
              })}
              <li className="mono text-[11px] text-muted">… +{num(Math.max(0, m.n - m.sample.length))}</li>
            </ul>
          </div>
          <BankBox id={b} active={!fromA} />
        </div>
      )}
      {coordWire.map((w, i) => (
        <CoordinatorRows key={i} w={w} />
      ))}
    </Card>
  );
}

function BankBox({ id, active }: { id: string; active: boolean }) {
  return (
    <div className={`flex h-16 items-center justify-center rounded-md border-2 text-sm font-semibold mono ${active ? 'border-navy bg-navy text-white dark:text-paper' : 'border-line text-muted'}`}>{id}</div>
  );
}

function fmtBytes(n: number, num: (n: number, d?: number) => string) {
  if (n >= 1_000_000) return `${num(n / 1_000_000, 1)} MB`;
  if (n >= 1000) return `${num(n / 1000, 1)} kB`;
  return `${num(n)} B`;
}

function ExposureTable({ d }: { d: RadarResponse }) {
  const { t, num } = useI18n();
  const e = d.exposure;
  const rows: { k: 'isolated' | 'staj_psi' | 'naive_raw_sharing'; raw?: number; bytes?: number; blinded?: number; match?: number }[] = [
    { k: 'isolated', raw: e?.isolated?.raw_records_exposed, bytes: e?.isolated?.bytes_exchanged },
    { k: 'staj_psi', raw: e?.staj_psi?.raw_records_exposed, bytes: e?.staj_psi?.bytes_exchanged, blinded: e?.staj_psi?.blinded_elements, match: e?.staj_psi?.match_rows_to_coordinator },
    { k: 'naive_raw_sharing', raw: e?.naive_raw_sharing?.raw_records_exposed, bytes: e?.naive_raw_sharing?.bytes_exchanged },
  ];
  const cell = (v: number | undefined, f: (n: number) => string = (n) => num(n)) => (v === undefined ? <span className="italic text-muted">{t('common.na')}</span> : f(v));
  return (
    <Card title={t('r.exposure')}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] border-collapse">
          <thead className="border-b border-line">
            <tr>
              <th className="th" scope="col">
                {t('r.mode')}
              </th>
              <th className="th text-right" scope="col">
                {t('r.raw_records')}
              </th>
              <th className="th text-right" scope="col">
                {t('r.bytes')}
              </th>
              <th className="th text-right" scope="col">
                {t('r.blinded')}
              </th>
              <th className="th text-right" scope="col">
                {t('r.match_rows')}
              </th>
            </tr>
          </thead>
          <tbody className="tnum">
            {rows.map((r) => (
              <tr key={r.k} className={`border-b border-line/70 last:border-0 ${r.k === 'staj_psi' ? 'bg-tealsoft/40' : ''}`}>
                <th scope="row" className="td text-left font-medium">
                  {t(`mode.${r.k}` as I18nKey)}
                </th>
                <td className={`td text-right ${r.k === 'naive_raw_sharing' && (r.raw ?? 0) > 0 ? 'font-semibold text-bad' : ''}`}>{cell(r.raw)}</td>
                <td className="td text-right" title={r.bytes !== undefined ? `${num(r.bytes)} B` : undefined}>
                  {cell(r.bytes, (n) => fmtBytes(n, num))}
                </td>
                <td className="td text-right">{r.k === 'staj_psi' ? cell(r.blinded) : '–'}</td>
                <td className="td text-right">{r.k === 'staj_psi' ? cell(r.match) : '–'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function CoordinatorRows({ w }: { w: WireMsg }) {
  const { t, num } = useI18n();
  const rows = w.sample.filter((s): s is Record<string, unknown> => typeof s === 'object' && s !== null);
  const cols = [...new Set(rows.flatMap((r) => Object.keys(r)))];
  return (
    <div className="mt-6 border-t border-line pt-4">
      <h3 className="text-sm font-semibold">
        {t('r.coordinator')} <span className="tnum font-normal text-muted">· {num(w.n)} · {w.from} → {w.session}</span>
      </h3>
      <p className="text-xs text-muted">{t('r.coordinator_sub')}</p>
      {rows.length ? (
        <div className="mt-2 overflow-x-auto">
          <table className="w-full border-collapse text-xs">
            <thead className="border-b border-line">
              <tr>
                {cols.map((c) => (
                  <th key={c} className="th mono">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-b border-line/70 last:border-0">
                  {cols.map((c) => (
                    <td key={c} className="px-3 py-1.5 mono tnum">
                      {typeof r[c] === 'object' ? JSON.stringify(r[c]) : String(r[c] ?? '–')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-1 text-[11px] text-muted tnum">… +{num(Math.max(0, w.n - rows.length))}</p>
        </div>
      ) : (
        <p className="mt-2 text-xs text-muted">{w.sample.map(String).join(', ')}</p>
      )}
    </div>
  );
}
