import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { downloadOpoMarkdown, getCase, getOpo, putSectionV } from '../api';
import { rememberCase } from '../components/Layout';
import { buildSources } from '../components/report/evidence';
import { ReportLoading } from '../components/report/ReportLoading';
import { SectionVBody, SourcesList } from '../components/report/SectionV';
import { Toc, type SectionStatus } from '../components/report/Toc';
import { Button, ErrorBox, Page, PageTitle } from '../components/ui';
import { useAsync } from '../state';
import type { CaseDetail, OpoDraft, OpoSection, Sentence } from '../types';

const HUMAN = new Set(['VI', 'IX']);
const CONTACT = 'VIII';
const isHuman = (s: OpoSection) => HUMAN.has(s.no) || /DOPLNÍ ČLOVĚK/i.test(s.text);

const HUMAN_HINT: Record<string, string> = {
  VI: 'Say whether the transaction was carried out, refused or postponed, and when.',
  IX: 'Say how and on what date the report will be filed with the FIU.',
};

const store = {
  get(k: string) {
    try {
      return localStorage.getItem(k) ?? '';
    } catch {
      return '';
    }
  },
  set(k: string, v: string) {
    try {
      localStorage.setItem(k, v);
    } catch {
      /* ignore */
    }
  },
};

const same = (a: Sentence[], b: Sentence[]) => a.length === b.length && a.every((s, i) => s.text === b[i].text && s.refs.join() === b[i].refs.join());

export default function OpoScreen() {
  const { id } = useParams();
  const nav = useNavigate();
  const [typed, setTyped] = useState('');
  useEffect(() => {
    if (id) rememberCase(id);
  }, [id]);

  if (!id)
    return (
      <Page>
        <PageTitle title="Report draft" description="Open the FIU report draft for one case." />
        <form
          className="card flex max-w-md items-end gap-3 p-5"
          onSubmit={(e) => {
            e.preventDefault();
            if (typed.trim()) nav(`/report/${typed.trim()}`);
          }}
        >
          <label className="flex flex-1 flex-col gap-1">
            <span className="label">Case id</span>
            <input className="input mono" placeholder="B1-R03028" value={typed} onChange={(e) => setTyped(e.target.value)} />
          </label>
          <Button variant="primary">Open</Button>
        </form>
      </Page>
    );
  return <Report id={id} key={id} />;
}

function Report({ id }: { id: string }) {
  const o = useAsync(() => getOpo(id), [id]);
  const c = useAsync(() => getCase(id), [id]);
  const [rows, setRows] = useState<Sentence[]>([]);
  const [base, setBase] = useState<Sentence[]>([]);
  const [everSaved, setEverSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [saveErr, setSaveErr] = useState<string | null>(null);
  const [dlErr, setDlErr] = useState<string | null>(null);
  const [human, setHuman] = useState<Record<string, string>>(() => ({
    VI: store.get(`staj.report.${id}.VI`),
    IX: store.get(`staj.report.${id}.IX`),
  }));

  useEffect(() => {
    if (o.data) {
      setRows(o.data.section_v_sentences);
      setBase(o.data.section_v_sentences);
    }
  }, [o.data]);

  const dirty = !same(rows, base);

  const save = async () => {
    setSaving(true);
    setSaveErr(null);
    setSaveMsg(null);
    try {
      const r = await putSectionV(
        id,
        rows.filter((s) => s.text.trim() !== ''),
      );
      o.setData(r);
      setEverSaved(true);
      setSaveMsg('Saved');
    } catch (e) {
      setSaveErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const download = async () => {
    setDlErr(null);
    try {
      await downloadOpoMarkdown(id);
    } catch (e) {
      setDlErr(e instanceof Error ? e.message : String(e));
    }
  };

  const actions = (
    <div className="flex flex-col items-end gap-2">
      <div className="flex items-center gap-2">
        {saveMsg && !dirty && (
          <span role="status" className="mr-2 text-[13px] text-muted">
            {saveMsg}
          </span>
        )}
        <Button onClick={save} disabled={!o.data || saving || !dirty} className="shadow-rest">
          {saving ? 'Saving…' : 'Save edits'}
        </Button>
        <Button onClick={download} disabled={!o.data} className="shadow-rest">
          Download Markdown
        </Button>
      </div>
      <p className="text-[12.5px] text-faint">Draft only — nothing is sent anywhere.</p>
    </div>
  );

  return (
    <Page className="!space-y-8">
      <header className="flex flex-wrap items-start justify-between gap-6">
        <div className="min-w-0 space-y-2">
          <CaseLine id={id} c={c.data} />
          <h1 className="text-[28px] font-semibold leading-tight tracking-tight text-ink">Report draft</h1>
        </div>
        {actions}
      </header>
      {saveErr && <ErrorBox error={saveErr} message="The edits were not saved." />}
      {dlErr && <ErrorBox error={dlErr} message="The download failed." />}

      {o.loading && !o.data ? (
        <ReportLoading />
      ) : o.error ? (
        <ErrorBox error={o.error} message="Could not draft the report for this case." onRetry={o.reload} />
      ) : o.data ? (
        <Document
          data={o.data}
          c={c.data}
          rows={rows}
          setRows={setRows}
          vStatus={dirty || everSaved ? 'edited' : 'auto-filled'}
          human={human}
          setHuman={(no, v) => {
            setHuman((h) => ({ ...h, [no]: v }));
            store.set(`staj.report.${id}.${no}`, v);
          }}
        />
      ) : null}
    </Page>
  );
}

function CaseLine({ id, c }: { id: string; c: CaseDetail | null }) {
  return (
    <p className="flex flex-wrap items-baseline gap-x-2 text-[14px] text-muted">
      <span>
        Case <span className="font-mono text-[13px] text-ink">{id}</span>
      </span>
      {c && (
        <>
          <span aria-hidden="true">·</span>
          <span>
            client <span className="font-mono text-[13px] text-ink">{c.client_ref}</span>
          </span>
          <span aria-hidden="true">·</span>
          <span>
            bank <span className="text-ink">{c.bank_id}</span>
          </span>
          <span aria-hidden="true">·</span>
          <span>
            priority <span className="tnum font-semibold text-ink">{c.priority}</span>
          </span>
        </>
      )}
      <span aria-hidden="true">·</span>
      <Link to={`/case/${id}`} className="text-accent hover:underline">
        Back to the case
      </Link>
    </p>
  );
}

function Document({
  data,
  c,
  rows,
  setRows,
  vStatus,
  human,
  setHuman,
}: {
  data: OpoDraft;
  c: CaseDetail | null;
  rows: Sentence[];
  setRows: (fn: (r: Sentence[]) => Sentence[]) => void;
  vStatus: SectionStatus;
  human: Record<string, string>;
  setHuman: (no: string, v: string) => void;
}) {
  const { sources, numOf } = useMemo(() => buildSources(rows, c), [rows, c]);
  const status = (s: OpoSection): SectionStatus => (s.no === 'V' ? vStatus : isHuman(s) ? (human[s.no]?.trim() ? 'edited' : 'needs your input') : 'auto-filled');

  return (
    <div className="grid items-start gap-10 lg:grid-cols-[240px_minmax(0,1fr)]">
      <aside className="hidden self-stretch lg:block">
        <Toc items={data.sections.map((s) => ({ no: s.no, title: s.title, status: status(s) }))} />
      </aside>

      <article className="card px-8 py-10 sm:px-14 sm:py-14">
        <div className="max-w-[68ch]">
          <h2 className="text-[20px] font-semibold leading-snug tracking-tight text-ink">{data.title}</h2>
          <p className="mt-2 text-[13px] text-faint">Click any statement in section V to edit it. Numbers point to the sources at the end.</p>

          <div className="mt-10 space-y-10">
            {data.sections.map((s) => (
              <DocSection key={s.no} s={s}>
                {s.no === 'V' ? (
                  <SectionVBody rows={rows} setRows={setRows} violations={data.section_v_violations} numOf={numOf} />
                ) : isHuman(s) ? (
                  <HumanBlock s={s} value={human[s.no] ?? ''} onChange={(v) => setHuman(s.no, v)} />
                ) : s.no === CONTACT ? (
                  <div className="rounded-lg bg-paper px-5 py-4">
                    <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-faint">From bank settings</p>
                    <p className="mt-1.5 text-[15px] leading-relaxed text-ink/85">{s.text}</p>
                  </div>
                ) : (
                  <p className="whitespace-pre-wrap text-[16px] leading-[1.7] text-ink/90">{s.text || <span className="text-faint">Empty in this draft.</span>}</p>
                )}
              </DocSection>
            ))}

            {sources.length > 0 && (
              <section id="sec-sources" className="scroll-mt-24">
                <h3 className="mb-4 text-[17px] font-semibold tracking-tight text-ink">Sources</h3>
                <SourcesList sources={sources} />
              </section>
            )}
          </div>
        </div>
      </article>
    </div>
  );
}

function DocSection({ s, children }: { s: OpoSection; children: ReactNode }) {
  return (
    <section id={`sec-${s.no}`} aria-labelledby={`sec-${s.no}-h`} className="scroll-mt-24">
      <h3 id={`sec-${s.no}-h`} className="mb-3 flex gap-4 text-[17px] font-semibold leading-snug tracking-tight text-ink">
        <span className="tnum w-8 shrink-0 text-muted">{s.no}</span>
        <span>{s.title}</span>
      </h3>
      <div className="pl-12">{children}</div>
    </section>
  );
}

function HumanBlock({ s, value, onChange }: { s: OpoSection; value: string; onChange: (v: string) => void }) {
  return (
    <div className="space-y-3">
      <p className="text-[12px] font-semibold uppercase tracking-[0.08em] text-amber">Left for the human</p>
      <p className="text-[15px] leading-relaxed text-ink">{HUMAN_HINT[s.no] ?? 'Fill this in yourself; the system does not decide it.'}</p>
      {s.text && <p className="text-[14px] leading-relaxed text-muted">{s.text}</p>}
      <label className="block">
        <span className="sr-only">{s.title}</span>
        <textarea
          rows={3}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Your text"
          className="block w-full resize-y rounded-lg bg-sunken px-4 py-3 text-[15px] leading-relaxed text-ink shadow-inset outline-none placeholder:text-faint focus:bg-surface focus:shadow-focus"
        />
      </label>
      <p className="text-[12.5px] text-faint">Kept in this browser only. It is not part of the Markdown download.</p>
    </div>
  );
}
