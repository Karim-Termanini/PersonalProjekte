import type { ReactElement } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import { AppShell } from './layout/AppShell'
import { DashboardKernelsPage } from './pages/DashboardKernelsPage'
import { DashboardLayout } from './pages/DashboardLayout'
import { DashboardLogsPage } from './pages/DashboardLogsPage'
import { DashboardMainPage } from './pages/DashboardMainPage'
import { DashboardWidgetsPage } from './pages/DashboardWidgetsPage'
import { RegistryPage } from './pages/RegistryPage'
import { SystemPage } from './pages/SystemPage'
import { TerminalPage } from './pages/TerminalPage'
import { WorkstationPage } from './pages/WorkstationPage'

export default function App(): ReactElement {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardLayout />}>
          <Route index element={<DashboardMainPage />} />
          <Route path="widgets" element={<DashboardWidgetsPage />} />
          <Route path="kernels" element={<DashboardKernelsPage />} />
          <Route path="logs" element={<DashboardLogsPage />} />
        </Route>
        <Route path="/system" element={<SystemPage />} />
        <Route path="/workstation" element={<WorkstationPage />} />
        <Route path="/registry" element={<RegistryPage />} />
        <Route path="/terminal" element={<TerminalPage />} />
      </Routes>
    </AppShell>
  )
}
