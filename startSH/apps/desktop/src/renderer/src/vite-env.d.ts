/// <reference types="vite/client" />

import type { ComposeProfile } from '@linux-dev-home/shared'

export {}

declare global {
  interface Window {
    dh: {
      dockerList: () => Promise<unknown>
      dockerAction: (payload: { id: string; action: string }) => Promise<unknown>
      dockerLogs: (payload: { id: string; tail?: number }) => Promise<unknown>
      dockerImagesList: () => Promise<unknown>
      dockerImageAction: (payload: { id: string; action: 'remove'; force?: boolean }) => Promise<unknown>
      dockerVolumesList: () => Promise<unknown>
      dockerVolumeAction: (payload: { name: string; action: 'remove' }) => Promise<unknown>
      dockerNetworksList: () => Promise<unknown>
      dockerNetworkAction: (payload: { id: string; action: 'remove' }) => Promise<unknown>
      dockerPrune: () => Promise<unknown>
      metrics: () => Promise<unknown>
      hostExec: (payload: unknown) => Promise<unknown>
      composeUp: (payload: { profile: ComposeProfile }) => Promise<unknown>
      composeLogs: (payload: { profile: ComposeProfile }) => Promise<unknown>
      terminalCreate: (payload: { cols: number; rows: number }) => Promise<unknown>
      terminalWrite: (id: string, data: string) => void
      terminalResize: (id: string, cols: number, rows: number) => void
      openExternalTerminal: () => Promise<unknown>
      gitClone: (payload: { url: string; targetDir: string }) => Promise<unknown>
      gitStatus: (payload: { repoPath: string }) => Promise<unknown>
      gitRecentList: () => Promise<unknown>
      gitRecentAdd: (payload: { path: string }) => Promise<unknown>
      gitConfigSet: (payload: { name: string; email: string; target: 'sandbox'|'host' }) => Promise<unknown>
      sshGenerate: (payload: { target: 'sandbox'|'host' }) => Promise<unknown>
      sshGetPub: (payload: { target: 'sandbox'|'host' }) => Promise<unknown>
      selectFolder: () => Promise<string | null>
      onTerminalData: (handler: (msg: { id: string; data: string }) => void) => () => void
      onTerminalExit: (handler: (msg: { id: string }) => void) => () => void
      openExternal: (url: string) => Promise<unknown>
      sessionInfo: () => Promise<unknown>
      layoutGet: () => Promise<unknown>
      layoutSet: (layout: unknown) => Promise<unknown>
      storeGet: (payload: import('@linux-dev-home/shared').StoreGetRequest) => Promise<unknown>
      storeSet: (payload: import('@linux-dev-home/shared').StoreSetRequest) => Promise<unknown>
      jobStart: (payload: { kind: string; durationMs?: number }) => Promise<unknown>
      jobsList: () => Promise<unknown>
      jobCancel: (payload: { id: string }) => Promise<unknown>
    }
  }
}
