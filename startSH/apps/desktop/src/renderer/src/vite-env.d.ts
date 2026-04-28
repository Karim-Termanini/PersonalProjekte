/// <reference types="vite/client" />

export {}

declare global {
  interface Window {
    dh: {
      dockerList: () => Promise<unknown>
      dockerAction: (payload: { id: string; action: string }) => Promise<unknown>
      dockerLogs: (payload: { id: string; tail?: number }) => Promise<unknown>
      metrics: () => Promise<unknown>
      hostExec: (payload: unknown) => Promise<unknown>
      composeUp: (payload: { profile: string }) => Promise<unknown>
      composeLogs: (payload: { profile: string }) => Promise<unknown>
      terminalCreate: (payload: { cols: number; rows: number }) => Promise<unknown>
      terminalWrite: (id: string, data: string) => void
      terminalResize: (id: string, cols: number, rows: number) => void
      openExternalTerminal: () => Promise<unknown>
      gitClone: (payload: { url: string; targetDir: string }) => Promise<unknown>
      gitStatus: (payload: { repoPath: string }) => Promise<unknown>
      gitRecentList: () => Promise<unknown>
      gitRecentAdd: (payload: { path: string }) => Promise<unknown>
      selectFolder: () => Promise<string | null>
      onTerminalData: (handler: (msg: { id: string; data: string }) => void) => () => void
      onTerminalExit: (handler: (msg: { id: string }) => void) => () => void
      openExternal: (url: string) => Promise<unknown>
      sessionInfo: () => Promise<unknown>
      layoutGet: () => Promise<unknown>
      layoutSet: (layout: unknown) => Promise<unknown>
      jobStart: (payload: { kind: string; durationMs?: number }) => Promise<unknown>
      jobsList: () => Promise<unknown>
      jobCancel: (payload: { id: string }) => Promise<unknown>
    }
  }
}
