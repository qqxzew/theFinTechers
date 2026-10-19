import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { getOpo, opoExportUrl, putSectionV } from '../api';
import { rememberCase } from '../components/Layout';
import { Card, Chip, ErrorBox, PageHeader, ViolationList } from '../components/ui';
import { useI18n } from '../i18n';
import { useAsync } from '../state';
import type { OpoDraft, Sentence } from '../types';

const HUMAN_SECTIONS = new Set(['VI', 'IX']);
const isHuman = (no: string, text: string) => HUMAN_SECTIONS.has(no) || /DOPLNÍ ČLOVĚK/i.test(text);

/** The first GET drafts section V with an LLM (1-2 min): show elapsed time so the wait is legible. */
function OpoLoading() {
  const { t } = useI18n();
  const [s, setS] = useState(0);
  useEffect(() => {
    const start = Date.now();
    const h = window.setInterval(() => setS(Math.floor((Date.now() - start) / 1000)), 500);
    return () => window.clearInterval(h);
  }, []);
  return (
    <div role="status" aria-live="polite" className="card flex flex-wrap items-center gap-3 p-5 text-sm">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-line border-t-teal" aria-hidden="true" />
      <span>{t('o.loading')}</span>
      <span className="ml-auto tnum text-muted">
        {t('o.elapsed')} {Math.floor(s / 60)}:{String(s % 60).padStart(2, '0')}
      </span>
    </div>
  );
}

function CollapsibleViolations({ items, title }: { items: Record<string, unknown>[]; title: string }) {
  const { t } = useI18n();
  const [all, setAll] = useState(false);
  if (!items?.length) return null;
  const shown = all ? items : items.slice(0, 5);
  return (
    <div>
      <ViolationList items={shown} title={title} total={items.length} />
      {items.length > 5 && (
        <button type="button" className="btn-secondary mt-1.5 py-0.5 text-xs" onClick={() => setAll((a) => !a)}>
          {all ? t('o.show_less') : `${t('o.show_all')} (${items.length})`}
        </button>
      )}
    </div>
  );
}

export default function OpoScreen() {
  const { id } = useParams();
  const { t } = useI18n();
  const nav = useNavigate();
  const [typed, setTyped] = useState('');
  useEffect(() => {
    if (id) rememberCase(id);
  }, [id]);
  const o = useAsync(() => (id ? getOpo(id) : Promise.resolve(null)), [id]);

  if (!id)
    return (
      <div>
        <PageHeader title={t('o.title')} />
        <form
          className="card flex max-w-md flex-wrap items-end gap-2 p-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (typed.trim()) nav(`/opo/${typed.trim()}`);
          }}
        >
          <div className="flex flex-1 flex-col gap-1">
            <label className="label" htmlFor="opo-id">
              {t('q.col_case')}
            </label>
            <input id="opo-id" className="input mono" placeholder="B1-R00123" value={typed} onChange={(e) => setTyped(e.target.value)} />
          </div>
          <button className="btn-primary">OK</button>
        </form>
      </div>
    );

  return (
    <div className="space-y-4">
      <PageHeader title={t('o.title')}>
        <Link to={`/case/${id}`} className="btn-secondary">
          ← {id}
        </Link>
        {/* Only offer export once the draft exists: export.md would otherwise start a second LLM draft. */}
        {o.data ? (
          <a className="btn-primary" href={opoExportUrl(id)} download={`OPO_${id}.md`}>
            {t('o.export_md')}
          </a>
        ) : (
          <button className="btn-primary" disabled>
            {t('o.export_md')}
          </button>
        )}
      </PageHeader>
      <div role="note" className="rounded-md border border-warn/40 bg-warnsoft px-4 py-2.5 text-sm font-semibold text-warn">
        {t('o.banner')}
      </div>
      {o.loading && !o.data ? (
        <OpoLoading />
      ) : o.error ? (
        <ErrorBox error={o.error} message={t('o.not_found')} onRetry={o.reload} />
      ) : o.data ? (
        <OpoView id={id} data={o.data} setData={o.setData} />
      ) : null}
    </div>
  );
}

function OpoView({ id, data, setData }: { id: string; data: OpoDraft; setData: (d: OpoDraft) => void }) {
  const { t } = useI18n();
  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_320px]">
      <div className="space-y-4">
        <h2 className="text-base font-semibold">{data.title}</h2>
        {data.sections.map((s) =>
          s.no === 'V' ? (
            <SectionV key={s.no} id={id} title={s.title} text={s.text} data={data} setData={setData} />
          ) : (
            <Card
              key={s.no}
              title={
                <span>
                  <span className="mono mr-2 text-muted">{s.no}.</span>
                  {s.title}
                </span>
              }
              right={isHuman(s.no, s.text) ? <Chip tone="warn">{t('o.human')}</Chip> : undefined}
            >
              {isHuman(s.no, s.text) ? (
                <div className="rounded-md border border-dashed border-warn/50 bg-warnsoft/40 p-3 text-sm text-warn">
                  {t('o.human_note')}
                  {s.text && <p className="mt-2 text-ink">{s.text}</p>}
                </div>
              ) : (
                <p className="whitespace-pre-wrap text-sm leading-relaxed">{s.text || <span className="italic text-muted">{t('common.na')}</span>}</p>
              )}
            </Card>
          ),
        )}
      </div>
      <aside>
        <ContactBlock />
      </aside>
    </div>
  );
}

function SectionV({ id, title, text, data, setData }: { id: string; title: string; text: string; data: OpoDraft; setData: (d: OpoDraft) => void }) {
  const { t } = useI18n();
  const [rows, setRows] = useState<Sentence[]>(data.section_v_sentences);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => setRows(data.section_v_sentences), [data.section_v_sentences]);

  const save = async () => {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const r = await putSectionV(id, rows.filter((s) => s.text.trim() !== ''));
      setData(r);
      setMsg(t('o.saved'));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const upd = (i: number, patch: Partial<Sentence>) => setRows((r) => r.map((s, j) => (j === i ? { ...s, ...patch } : s)));

  return (
    <Card
      title={
        <span>
          <span className="mono mr-2 text-muted">V.</span>
          {title}
        </span>
      }
      right={<Chip tone="teal">{t('o.editable')}</Chip>}
    >
      <div className="space-y-3">
        <CollapsibleViolations items={data.section_v_violations} title={t('o.violations')} />
        {rows.length === 0 && text && (
          <div className="rounded-md border border-dashed border-line bg-paper/60 p-3 text-sm">
            <p className="label mb-1">{t('o.v_fallback')}</p>
            <p className="whitespace-pre-wrap">{text}</p>
          </div>
        )}
        {rows.map((s, i) => (
          <div key={i} className="rounded-md border border-line p-2.5">
            <label className="label" htmlFor={`sv-${i}`}>
              {t('o.sentence')} {i + 1}
            </label>
            <textarea id={`sv-${i}`} rows={2} className="input mt-1 w-full" value={s.text} onChange={(e) => upd(i, { text: e.target.value })} />
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              <span className="text-[11px] text-muted">{t('o.refs')}:</span>
              {s.refs.length ? (
                s.refs.map((r, j) => (
                  <Chip key={`${r}-${j}`} tone="navy" mono>
                    {r}
                  </Chip>
                ))
              ) : (
                <Chip tone="bad">no refs</Chip>
              )}
              <label className="sr-only" htmlFor={`svr-${i}`}>
                {t('o.refs')}
              </label>
              <input
                id={`svr-${i}`}
                className="input mono ml-auto w-56 py-0.5 text-[11px]"
                value={s.refs.join(', ')}
                onChange={(e) =>
                  upd(i, {
                    refs: e.target.value
                      .split(',')
                      .map((x) => x.trim())
                      .filter(Boolean),
                  })
                }
                aria-label={`${t('o.refs')} ${i + 1}`}
              />
              <button type="button" className="btn-secondary py-0.5 text-xs" onClick={() => setRows((r) => r.filter((_, j) => j !== i))}>
                {t('o.remove')}
              </button>
            </div>
          </div>
        ))}
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" className="btn-secondary" onClick={() => setRows((r) => [...r, { text: '', refs: [] }])}>
            + {t('o.add_sentence')}
          </button>
          <button type="button" className="btn-primary" onClick={save} disabled={busy}>
            {busy ? t('o.saving') : t('o.save')}
          </button>
          {msg && (
            <span role="status" className="text-xs text-good">
              {msg}
            </span>
          )}
        </div>
        {err && <ErrorBox error={err} />}
      </div>
    </Card>
  );
}

function ContactBlock() {
  const { t } = useI18n();
  const [c, setC] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('staj.opo.contact') ?? '') as { name: string; phone: string; email: string };
    } catch {
      return { name: 'Oddělení AML compliance', phone: '+420 000 000 000', email: 'aml@banka.example' };
    }
  });
  const set = (k: 'name' | 'phone' | 'email', v: string) => {
    const n = { ...c, [k]: v };
    setC(n);
    try {
      localStorage.setItem('staj.opo.contact', JSON.stringify(n));
    } catch {
      /* ignore */
    }
  };
  return (
    <div className="xl:sticky xl:top-20">
      <Card title={t('o.contact')} sub={t('o.contact_sub')}>
        <div className="space-y-3">
          {(
            [
              ['name', t('o.contact_name')],
              ['phone', t('o.contact_phone')],
              ['email', t('o.contact_email')],
            ] as const
          ).map(([k, l]) => (
            <div key={k} className="flex flex-col gap-1">
              <label className="label" htmlFor={`ct-${k}`}>
                {l}
              </label>
              <input id={`ct-${k}`} className="input" value={c[k]} onChange={(e) => set(k, e.target.value)} />
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
