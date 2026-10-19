import { getHonesty, firstSentences, groupLimitations, splitNotFound } from '../api';
import { ErrorBox, Loading, Page } from '../components/ui';
import { useAsync } from '../state';
import type { HonestyResponse } from '../types';

const KIND_LABEL: Record<HonestyResponse['sources'][number]['kind'], string> = {
  'real-synthetic': 'synthetic, provided by the organisers',
  planted: 'planted by us',
  generic: 'generic public benchmark',
};

const LEAD =
  'The numbers come from simulated mule scenarios written by the same team. They show the method works as designed, not how it performs on real bank data.';

function H2({ children, id }: { children: string; id: string }) {
  return (
    <h2 id={id} className="text-[13px] font-semibold uppercase tracking-[0.08em] text-muted">
      {children}
    </h2>
  );
}

export default function HonestyScreen() {
  const h = useAsync(getHonesty, []);
  const d = h.data;
  return (
    <Page>
      <div className="max-w-[760px] space-y-16 pt-2">
      <header className="space-y-6">
        <h1 className="text-[28px] font-semibold leading-tight tracking-tight text-ink">Limits</h1>
        <p className="max-w-[34em] text-[22px] font-medium leading-[1.4] tracking-tight text-ink">{LEAD}</p>
      </header>

      {h.loading && !d ? (
        <Loading />
      ) : h.error ? (
        <ErrorBox error={h.error} onRetry={h.reload} />
      ) : d ? (
        <>
          <section aria-labelledby="lim-data" className="space-y-6">
            <H2 id="lim-data">What the data is</H2>
            <ul className="space-y-6">
              {d.sources.map((s) => (
                <li key={s.name} className="max-w-[62ch]">
                  <p className="text-[16px] font-semibold text-ink">{s.name}</p>
                  <p className="mt-1 text-[15px] leading-relaxed text-ink/85">{firstSentences(s.description, 1)}</p>
                  <p className="mt-1 text-[13px] text-faint">{KIND_LABEL[s.kind] ?? s.kind}</p>
                </li>
              ))}
            </ul>
          </section>

          <section aria-labelledby="lim-claims" className="space-y-8">
            <H2 id="lim-claims">What we cannot claim</H2>
            {groupLimitations(d.limitations.slice(0, 8)).map((g) => (
              <div key={g.group} className="grid gap-x-8 gap-y-2 sm:grid-cols-[120px_1fr]">
                <p className="pt-0.5 text-[14px] font-semibold capitalize text-ink">{g.group}</p>
                <ul className="max-w-[62ch] space-y-3">
                  {g.items.map((x, i) => (
                    <li key={i} className="text-[15px] leading-relaxed text-ink/85">
                      {firstSentences(x, 2)}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </section>

          <section aria-labelledby="lim-legal" className="space-y-6">
            <H2 id="lim-legal">Legal note</H2>
            <div className="card px-7 py-6 shadow-rest">
              <p className="max-w-[62ch] text-[15px] leading-relaxed text-ink">{d.legal_note}</p>
            </div>
          </section>

          {d.not_found_in_public_sources?.length > 0 && (
            <section aria-labelledby="lim-nf" className="space-y-4">
              <H2 id="lim-nf">What we did not find elsewhere (as of 19 Oct 2026)</H2>
              <ul className="max-w-[62ch] list-disc space-y-1.5 pl-5 text-[14px] leading-relaxed text-muted marker:text-faint">
                {d.not_found_in_public_sources.flatMap(splitNotFound).map((x, i) => (
                  <li key={i}>{x}</li>
                ))}
              </ul>
            </section>
          )}
        </>
      ) : null}
      </div>
    </Page>
  );
}
