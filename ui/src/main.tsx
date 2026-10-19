import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import './index.css';
import Layout from './components/Layout';
import { I18nProvider } from './i18n';
import { AppProvider } from './state';
import QueueScreen from './screens/Queue';
import CaseScreen from './screens/Case';
import OpoScreen from './screens/Opo';
import RadarScreen from './screens/Radar';
import MetricsScreen from './screens/Metrics';
import AuditScreen from './screens/Audit';
import HonestyScreen from './screens/Honesty';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <I18nProvider>
      <AppProvider>
        <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<QueueScreen />} />
              <Route path="case" element={<CaseScreen />} />
              <Route path="case/:id" element={<CaseScreen />} />
              <Route path="opo" element={<OpoScreen />} />
              <Route path="opo/:id" element={<OpoScreen />} />
              <Route path="radar" element={<RadarScreen />} />
              <Route path="metrics" element={<MetricsScreen />} />
              <Route path="audit" element={<AuditScreen />} />
              <Route path="honesty" element={<HonestyScreen />} />
              <Route path="*" element={<QueueScreen />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AppProvider>
    </I18nProvider>
  </StrictMode>,
);
