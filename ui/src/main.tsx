import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes, useParams } from 'react-router-dom';
import '@fontsource-variable/bricolage-grotesque';
import '@fontsource/jetbrains-mono/400.css';
import '@fontsource/jetbrains-mono/500.css';
import './index.css';
import Layout from './components/Layout';
import { AppProvider } from './state';
import QueueScreen from './screens/Queue';
import CaseScreen from './screens/Case';
import OpoScreen from './screens/Opo';
import RadarScreen from './screens/Radar';
import MetricsScreen from './screens/Metrics';
import HonestyScreen from './screens/Honesty';

/** Old /opo/:id links (used inside screens) go to the Report route. */
function OpoRedirect() {
  const { id } = useParams();
  return <Navigate to={id ? `/report/${id}` : '/report'} replace />;
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppProvider>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<QueueScreen />} />
            <Route path="case" element={<CaseScreen />} />
            <Route path="case/:id" element={<CaseScreen />} />
            <Route path="report" element={<OpoScreen />} />
            <Route path="report/:id" element={<OpoScreen />} />
            <Route path="opo" element={<OpoRedirect />} />
            <Route path="opo/:id" element={<OpoRedirect />} />
            <Route path="radar" element={<RadarScreen />} />
            <Route path="metrics" element={<MetricsScreen />} />
            <Route path="limits" element={<HonestyScreen />} />
            <Route path="honesty" element={<Navigate to="/limits" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AppProvider>
  </StrictMode>,
);
