import { useState } from 'react';
import { getAudit, verifyAudit } from '../api';
import { Chip, ErrorBox, Loading, PageHeader, short } from '../components/ui';
import { useI18n } from '../i18n';
import { useApp, useAsync } from '../state';
import type { AuditVerify } from '../types';

const PAGE = 25;

export default function AuditScreen() {
  const { t, num, lang } = useI18n();
  const { meta, refreshMeta } = useApp();
  const [offset, setOffset] = useState(0);
  const a = useAsync(() => getAudit(offset, PAGE), [offset]);
  const [v, setV] = useState<AuditVerify | null>(null);
  const [vBusy, setVBusy] = useState(false);
  const [vErr, setVErr] = useState<string | null>(null);

  const verify = async () => {
    setVBusy(true);
    setVErr(null);
    try {
      setV(await verifyAudit());
      refreshMeta();
    } catch (e) {
      setVErr(e instanceof Error ? e.message : String(e));
    } finally {
      setVBusy(false);
    }
  };

  const status = v ?? (meta ? { ok: meta.chain.ok, bad_index: null, length: meta.chain.length, head: meta.chain.head } : null);
  const total = a.data?.total ?? 0;
  const page = Math.floor(offset / PAGE) + 1;
  const pages = Math.max(1, Math.ceil(total / PAGE));

  return (
    <div className="space-y-4">
      <PageHeader title={t('a.title')}>
        {status && (
          <Chip tone={status.ok ? 'good' : 'bad'}>
            {status.ok ? `✓ ${t('a.ok')}` : `✕ ${t('a.bad')} ${status.bad_index ?? '?'}`}
          </Chip>
        )}
        <button className="btn-primary" onClick={verify} disabled={vBusy}>
          {vBusy ? t('a.verifying') : t('a.verify')}
        </button>
      </PageHeader>

      <div aria-live="polite">
        {vErr && <ErrorBox error={vErr} />}
        {v && (
          <div className={`rounded-md border px-4 py-3 text-sm ${v.ok ? 'border-good/30 bg-goodsoft text-good' : 'border-bad/30 bg-badsoft text-bad'}`} role="status">
            <span className="font-semibold">{v.ok ? t('a.ok') : `${t('a.bad')} ${v.bad_index}`}</span>
            <span className="ml-3 text-ink tnum">
              {num(v.length)} {t('a.total')} · {t('a.head')} <span className="mono">{short(v.head, 16)}</span>
            </span>
          </div>
        )}
      </div>

      <div className="card overflow-hidden">
        {a.loading && !a.data ? (
          <Loading />
        ) : a.error ? (
          <div className="p-4">
            <ErrorBox error={a.error} onRetry={a.reload} />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1100px] border-collapse">
              <caption className="sr-only">{t('a.title')}</caption>
              <thead className="border-b border-line bg-paper/60">
                <tr>
                  {(['a.seq', 'a.ts', 'a.actor', 'a.action', 'a.why', 'a.model', 'a.input', 'a.hash', 'a.prev'] as const).map((k) => (
                    <th key={k} className="th" scope="col">
                      {t(k)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {a.data?.entries.map((e) => {
                  const bad = v && !v.ok && v.bad_index === e.seq;
                  return (
                    <tr key={e.seq} className={`border-b border-line/70 last:border-0 ${bad ? 'bg-badsoft' : ''}`}>
                      <td className="td tnum text-muted">{e.seq}</td>
                      <td className="td mono whitespace-nowrap">{new Date(e.ts).toLocaleString(lang === 'cs' ? 'cs-CZ' : 'en-GB')}</td>
                      <td className="td text-sm">{e.actor}</td>
                      <td className="td">
                        <Chip tone={e.action === 'decision' ? 'navy' : 'neutral'} mono>
                          {e.action}
                        </Chip>
                      </td>
                      <td className="td max-w-[320px] text-sm">{e.why}</td>
                      <td className="td mono text-muted">{e.model_version ?? '–'}</td>
                      <td className="td mono" title={e.input_hash}>
                        {short(e.input_hash, 8)}
                      </td>
                      <td className="td mono" title={e.hash}>
                        {short(e.hash, 8)}
                      </td>
                      <td className="td mono text-muted" title={e.prev_hash}>
                        {short(e.prev_hash, 8)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <nav className="flex items-center justify-between gap-2 border-t border-line px-4 py-2 text-sm" aria-label="pagination">
          <span className="text-xs text-muted tnum">
            {num(total)} {t('a.total')}
          </span>
          <span className="flex items-center gap-2">
            <button className="btn-secondary py-1" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
              ← {t('common.prev')}
            </button>
            <span className="tnum text-xs">
              {t('common.page')} {page} {t('common.of')} {pages}
            </span>
            <button className="btn-secondary py-1" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}>
              {t('common.next')} →
            </button>
          </span>
        </nav>
      </div>
    </div>
  );
}
