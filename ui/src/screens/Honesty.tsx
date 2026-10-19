import { getHonesty } from '../api';
import { Card, Chip, ErrorBox, Loading, NA, PageHeader, SyntheticBadge } from '../components/ui';
import { useI18n, type I18nKey } from '../i18n';
import { useAsync } from '../state';

export default function HonestyScreen() {
  const { t } = useI18n();
  const h = useAsync(getHonesty, []);
  const d = h.data;
  return (
    <div className="space-y-5">
      <PageHeader title={t('h.title')}>
        <SyntheticBadge />
      </PageHeader>
      {h.loading && !d ? (
        <Loading />
      ) : h.error ? (
        <ErrorBox error={h.error} onRetry={h.reload} />
      ) : d ? (
        <>
          <section className="rounded-lg border-2 border-navy/30 bg-surface p-5" aria-labelledby="legal-h">
            <h2 id="legal-h" className="label mb-1.5 uppercase tracking-wide">
              {t('h.legal')}
            </h2>
            <p className="text-base leading-relaxed">{d.legal_note || <NA />}</p>
          </section>
          <div className="grid gap-5 lg:grid-cols-2">
            <Card title={t('h.sources')}>
              {d.sources?.length ? (
                <ul className="space-y-3">
                  {d.sources.map((s) => (
                    <li key={s.name}>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{s.name}</span>
                        <Chip tone={s.kind === 'planted' ? 'warn' : s.kind === 'generic' ? 'neutral' : 'teal'}>{t(`kind.${s.kind}` as I18nKey)}</Chip>
                      </div>
                      <p className="text-sm text-muted">{s.description}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <NA />
              )}
            </Card>
            <Card title={t('h.planted')}>
              <List items={d.planted} />
            </Card>
            <Card title={t('h.limitations')}>
              <List items={d.limitations} />
            </Card>
            <Card title={t('h.not_found')}>
              <List items={d.not_found_in_public_sources} />
            </Card>
          </div>
        </>
      ) : null}
    </div>
  );
}

function List({ items }: { items?: string[] }) {
  if (!items?.length) return <NA />;
  return (
    <ul className="list-disc space-y-1.5 pl-5 text-sm leading-relaxed">
      {items.map((x, i) => (
        <li key={i}>{x}</li>
      ))}
    </ul>
  );
}
