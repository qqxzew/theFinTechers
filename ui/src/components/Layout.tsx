import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { USING_MOCKS } from '../api';
import { useI18n, type I18nKey } from '../i18n';
import { ROLES, useApp } from '../state';
import { Chip } from './ui';

const ICONS: Record<string, string> = {
  queue: 'M4 6h16M4 12h16M4 18h10',
  case: 'M6 4h9l3 3v13H6z M9 11h6 M9 15h6',
  opo: 'M6 4h12v16H6z M9 8h6 M9 12h6 M9 16h3',
  radar: 'M12 12m-8 0a8 8 0 1 0 16 0a8 8 0 1 0 -16 0 M12 12m-4 0a4 4 0 1 0 8 0a4 4 0 1 0 -8 0 M12 12L18 6',
  metrics: 'M5 19V11 M10 19V6 M15 19V13 M20 19V9',
  audit: 'M7 7h4v4H7z M13 13h4v4h-4z M11 9h4v4',
  honesty: 'M12 4l7 3v5c0 4-3 7-7 8c-4-1-7-4-7-8V7z',
};

function Icon({ name }: { name: string }) {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={ICONS[name]} />
    </svg>
  );
}

export function rememberCase(id: string) {
  try {
    sessionStorage.setItem('staj.lastCase', id);
  } catch {
    /* ignore */
  }
}
function lastCase(): string | null {
  try {
    return sessionStorage.getItem('staj.lastCase');
  } catch {
    return null;
  }
}

export default function Layout() {
  const { t, lang, setLang } = useI18n();
  const { identity, setIdentity, meta, metaError, dark, setDark } = useApp();
  const loc = useLocation();
  const [navOpen, setNavOpen] = useState(false);
  useEffect(() => setNavOpen(false), [loc.pathname]);
  const lc = lastCase();

  const items: { to: string; key: I18nKey; icon: string; end?: boolean; hint?: string }[] = [
    { to: '/', key: 'nav.queue', icon: 'queue', end: true },
    { to: lc ? `/case/${lc}` : '/case', key: 'nav.case', icon: 'case', hint: lc ?? t('nav.case_hint') },
    { to: lc ? `/opo/${lc}` : '/opo', key: 'nav.opo', icon: 'opo', hint: lc ?? undefined },
    { to: '/radar', key: 'nav.radar', icon: 'radar' },
    { to: '/metrics', key: 'nav.metrics', icon: 'metrics' },
    { to: '/audit', key: 'nav.audit', icon: 'audit' },
    { to: '/honesty', key: 'nav.honesty', icon: 'honesty' },
  ];

  const chain = meta?.chain;

  return (
    <div className="flex min-h-full flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2">
        Skip to content
      </a>
      {USING_MOCKS && (
        <div role="note" className="border-b border-warn/40 bg-warnsoft px-4 py-1.5 text-center text-xs font-medium text-warn">
          {t('mock.banner')}
        </div>
      )}
      <header className="z-30 lg:sticky lg:top-0 border-b border-line bg-surface/95 backdrop-blur-sm">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2">
          <button
            className="btn-secondary px-2 lg:hidden"
            aria-label="Menu"
            aria-expanded={navOpen}
            aria-controls="side-nav"
            onClick={() => setNavOpen((o) => !o)}
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
              <path d="M4 7h16M4 12h16M4 17h16" />
            </svg>
          </button>
          <div className="flex items-baseline gap-2">
            <span className="text-lg font-semibold tracking-tight text-navy">{t('app.name')}</span>
            <span className="hidden text-xs text-muted md:inline">{t('app.tagline')}</span>
          </div>

          <div className="flex flex-wrap items-center gap-1.5" aria-label="data labels">
            {meta && (
              <Chip tone="warn" title={meta.data_label} className="max-w-[18rem] overflow-hidden text-ellipsis">
                {/^SYNTHETIC( DATA)?$/i.test(meta.data_label) ? t('chip.synthetic') : meta.data_label}
              </Chip>
            )}
            {meta?.fx_placeholder && <Chip tone="warn">{t('chip.fx')}</Chip>}
            {meta?.matrix_placeholder && <Chip tone="warn">{t('chip.matrix')}</Chip>}
            {meta && (
              <Chip tone="neutral" mono title={`primary ${meta.models.agent_primary} · fallback ${meta.models.fallback} · bulk ${meta.models.bulk}`}>
                {t('chip.model')}: {meta.models.active.agent_primary}
              </Chip>
            )}
            {chain ? (
              <NavLink to="/audit" className="rounded">
                <Chip tone={chain.ok ? 'good' : 'bad'} title={`length ${chain.length} · head ${chain.head}`}>
                  {chain.ok ? '✓' : '✕'} {chain.ok ? t('chip.chain_ok') : t('chip.chain_bad')} · <span className="tnum">{chain.length}</span>
                </Chip>
              </NavLink>
            ) : (
              <Chip tone="neutral" title={metaError ?? ''}>
                {t('chip.chain_unknown')}
              </Chip>
            )}
          </div>

          <div className="ml-auto flex flex-wrap items-center gap-2">
            <fieldset className="flex items-center gap-1.5" aria-label={t('top.identity')}>
              <label className="sr-only" htmlFor="id-name">
                {t('top.name')}
              </label>
              <input
                id="id-name"
                className="input w-36 py-1 text-xs"
                placeholder={t('top.name_ph')}
                value={identity.name}
                onChange={(e) => setIdentity({ ...identity, name: e.target.value })}
                list="top-staff"
              />
              <datalist id="top-staff">
                {(meta?.staff ?? []).map((s) => (
                  <option key={s} value={s} />
                ))}
              </datalist>
              <label className="sr-only" htmlFor="id-role">
                {t('top.role')}
              </label>
              <select id="id-role" className="input py-1 text-xs" value={identity.role} onChange={(e) => setIdentity({ ...identity, role: e.target.value })}>
                {(meta?.roles ?? ROLES).map((r) => (
                  <option key={r} value={r}>
                    {t(`role.${r}` as I18nKey) ?? r}
                  </option>
                ))}
              </select>
            </fieldset>
            <div className="flex overflow-hidden rounded-md border border-line" role="group" aria-label={t('top.lang')}>
              {(['cs', 'en'] as const).map((l) => (
                <button
                  key={l}
                  className={`px-2 py-1 text-xs font-medium uppercase ${lang === l ? 'bg-navy text-white dark:text-paper' : 'bg-surface text-muted hover:text-ink'}`}
                  aria-pressed={lang === l}
                  onClick={() => setLang(l)}
                >
                  {l}
                </button>
              ))}
            </div>
            <button className="btn-secondary px-2 py-1 text-xs" aria-pressed={dark} onClick={() => setDark(!dark)} title={t('top.theme')}>
              <span aria-hidden="true">{dark ? '☀' : '☾'}</span>
              <span className="sr-only">{t('top.theme')}</span>
            </button>
          </div>
        </div>
      </header>

      <div className="flex flex-1 flex-col lg:flex-row">
        <nav
          id="side-nav"
          aria-label={t('nav.main')}
          className={`${navOpen ? 'block' : 'hidden'} w-full border-b border-line bg-surface p-3 lg:block lg:w-56 lg:shrink-0 lg:border-b-0 lg:border-r lg:bg-transparent`}
        >
          <ul className="space-y-0.5 lg:sticky lg:top-16">
            {items.map((it) => (
              <li key={it.key}>
                <NavLink
                  to={it.to}
                  end={it.end}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm ${isActive || (it.icon === 'case' && loc.pathname.startsWith('/case')) || (it.icon === 'opo' && loc.pathname.startsWith('/opo')) ? 'bg-navy/10 font-semibold text-navy' : 'text-ink hover:bg-surface'}`
                  }
                >
                  <Icon name={it.icon} />
                  <span className="min-w-0">
                    <span className="block">{t(it.key)}</span>
                    {it.hint && <span className="block truncate font-mono text-[10px] font-normal text-muted">{it.hint}</span>}
                  </span>
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <main id="main" className="min-w-0 flex-1 px-4 py-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
