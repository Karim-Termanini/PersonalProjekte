import type { ReactElement } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import { AppShell } from './layout/AppShell'
import { DashboardPage } from './pages/DashboardPage'
import { RegistryPage } from './pages/RegistryPage'
import { SystemPage } from './pages/SystemPage'
import { TerminalPage } from './pages/TerminalPage'
import { WorkstationPage } from './pages/WorkstationPage'

export default function App(): ReactElement {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/system" element={<SystemPage />} />
        <Route path="/workstation" element={<WorkstationPage />} />
        <Route path="/registry" element={<RegistryPage />} />
        <Route path="/terminal" element={<TerminalPage />} />
      </Routes>
    </AppShell>
  )
}
