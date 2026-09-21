import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './app/AppShell'
import { DashboardDataProvider } from './data/DashboardDataProvider'
import { IndonesiaStatisticsPage } from './pages/IndonesiaStatisticsPage'
import { MapExplorerPage } from './pages/MapExplorerPage'

export function App() {
  return (
    <DashboardDataProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Navigate to="/map" replace />} />
            <Route path="map" element={<MapExplorerPage />} />
            <Route path="indonesia" element={<IndonesiaStatisticsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </DashboardDataProvider>
  )
}
