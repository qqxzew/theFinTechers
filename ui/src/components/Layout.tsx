import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { USING_MOCKS } from '../api';
import { t, type I18nKey } from '../i18n';
import { ROLES, STAFF, useApp } from '../state';

const ROLE_LABEL: Record<string, string> = { analyst_l1: 'Analyst L1', analyst_l2: 'Analyst L2', aml_officer: 'AML officer', mlro: 'MLRO' };

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

/** App shell: text-only left rail, slim top bar with the demo identity, centred content. */
export default function Layout() {
  const loc = useLocation();
  const lc = lastCase();
  const items: { to: string; key: I18nKey; match: (p: string) => boolean; hint?: string }[] = [
    { to: '/', key: 'nav.queue', match: (p) => p === '/' },
    ...(lc ? [{ to: `/case/${lc}`, key: 'nav.case' as I18nKey, match: (p: string) => p.startsWith('/case'), hint: lc }] : []),
    { to: '/radar', key: 'nav.radar', match: (p) => p.startsWith('/radar') },
    { to: '/metrics', key: 'nav.metrics', match: (p) => p.startsWith('/metrics') },
    { to: lc ? `/report/${lc}` : '/report', key: 'nav.opo', match: (p) => p.startsWith('/report') || p.startsWith('/opo') },
    { to: '/limits', key: 'nav.honesty', match: (p) => p.startsWith('/limits') || p.startsWith('/honesty') },
  ];

  return (
    <div className="flex min-h-full">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2 focus:shadow-raise">
        Skip to content
      </a>

      <nav aria-label="Main" className="sticky top-0 hidden h-screen w-52 shrink-0 flex-col px-5 py-7 md:flex">
        <NavLink to="/" className="mb-10 px-3 text-[22px] font-semibold tracking-tight text-ink">
          Stáj
        </NavLink>
        <ul className="space-y-1">
          {items.map((it) => {
            const active = it.match(loc.pathname);
            return (
              <li key={it.key}>
                <NavLink
                  to={it.to}
                  aria-current={active ? 'page' : undefined}
                  className={`block rounded-lg px-3 py-2 text-[15px] transition-[box-shadow,background-color] ${
                    active ? 'bg-surface font-semibold text-ink shadow-rest' : 'text-muted hover:bg-surface/60 hover:text-ink'
                  }`}
                >
                  {t(it.key)}
                  {it.hint && <span className="mt-0.5 block truncate font-mono text-[11px] font-normal text-faint">{it.hint}</span>}
                </NavLink>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar items={items} pathname={loc.pathname} />
        {USING_MOCKS && (
          <p role="note" className="mx-6 mb-2 max-w-content rounded-lg bg-ambersoft px-4 py-2 text-[13px] text-amber md:mx-10 lg:mx-auto lg:w-[calc(100%-5rem)]">
            {t('mock.banner')}
          </p>
        )}
        <main id="main" className="min-w-0 flex-1 px-6 pb-10 pt-4 md:px-10">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function TopBar({ items, pathname }: { items: { to: string; key: I18nKey; match: (p: string) => boolean }[]; pathname: string }) {
  const { identity, setIdentity, meta } = useApp();
  const staff = meta?.staff?.length ? meta.staff : STAFF.map((s) => s.name);
  return (
    <header className="flex flex-wrap items-center gap-x-6 gap-y-2 px-6 pb-2 pt-5 md:px-10">
      {/* Compact nav for narrow screens (the rail is hidden below md). */}
      <nav aria-label="Main (compact)" className="flex flex-wrap gap-1 md:hidden">
        <span className="mr-2 text-[18px] font-semibold">Stáj</span>
        {items.map((it) => (
          <NavLink key={it.key} to={it.to} className={`rounded-md px-2 py-1 text-sm ${it.match(pathname) ? 'bg-surface font-semibold shadow-rest' : 'text-muted'}`}>
            {t(it.key)}
          </NavLink>
        ))}
      </nav>
      <div className="ml-auto flex items-center gap-2 text-[13px] text-muted" role="group" aria-label={t('top.identity')}>
        <span>{t('top.identity')}</span>
        <label className="sr-only" htmlFor="id-name">
          Name
        </label>
        <input
          id="id-name"
          list="top-staff"
          className="w-16 rounded-md bg-transparent px-2 py-1 text-[13px] font-medium text-ink hover:bg-surface hover:shadow-rest focus:bg-surface"
          value={identity.name}
          onChange={(e) => setIdentity({ ...identity, name: e.target.value })}
        />
        <datalist id="top-staff">
          {staff.map((s) => (
            <option key={s} value={s} />
          ))}
        </datalist>
        <label className="sr-only" htmlFor="id-role">
          Role
        </label>
        <select
          id="id-role"
          className="appearance-none rounded-md bg-transparent px-2 py-1 text-[13px] font-medium text-ink hover:bg-surface hover:shadow-rest focus:bg-surface"
          value={identity.role}
          onChange={(e) => setIdentity({ ...identity, role: e.target.value })}
        >
          {(meta?.roles ?? ROLES).map((r) => (
            <option key={r} value={r}>
              {ROLE_LABEL[r] ?? r}
            </option>
          ))}
        </select>
      </div>
    </header>
  );
}
