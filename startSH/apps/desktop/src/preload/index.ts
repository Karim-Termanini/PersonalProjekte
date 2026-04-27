import { contextBridge, ipcRenderer } from 'electron'

import { IPC } from '@linux-dev-home/shared'

export type DhApi = {
  dockerList: () => unknown
  dockerAction: (payload: { id: string; action: string }) => unknown
  dockerLogs: (payload: { id: string; tail?: number }) => unknown
  metrics: () => unknown
  hostExec: (payload: unknown) => unknown
  composeUp: (payload: { profile: string }) => unknown
  composeLogs: (payload: { profile: string }) => unknown
  terminalCreate: (payload: { cols: number; rows: number }) => unknown
  terminalWrite: (id: string, data: string) => void
  terminalResize: (id: string, cols: number, rows: number) => void
  openExternalTerminal: () => unknown
  gitClone: (payload: { url: string; targetDir: string }) => unknown
  gitStatus: (payload: { repoPath: string }) => unknown
  gitRecentList: () => unknown
  gitRecentAdd: (payload: { path: string }) => unknown
  selectFolder: () => Promise<string | null>
  onTerminalData: (handler: (msg: { id: string; data: string }) => void) => () => void
  onTerminalExit: (handler: (msg: { id: string }) => void) => () => void
  openExternal: (url: string) => Promise<unknown>
}

const api: DhApi = {
  dockerList: () => ipcRenderer.invoke(IPC.dockerList),
  dockerAction: (payload) => ipcRenderer.invoke(IPC.dockerAction, payload),
  dockerLogs: (payload) => ipcRenderer.invoke(IPC.dockerLogs, payload),
  metrics: () => ipcRenderer.invoke(IPC.metrics),
  hostExec: (payload) => ipcRenderer.invoke(IPC.hostExec, payload),
  composeUp: (payload) => ipcRenderer.invoke(IPC.composeUp, payload),
  composeLogs: (payload) => ipcRenderer.invoke(IPC.composeLogs, payload),
  terminalCreate: (payload) => ipcRenderer.invoke(IPC.terminalCreate, payload),
  terminalWrite: (id, data) => ipcRenderer.send(IPC.terminalWrite, { id, data }),
  terminalResize: (id, cols, rows) => ipcRenderer.send(IPC.terminalResize, { id, cols, rows }),
  openExternalTerminal: () => ipcRenderer.invoke(IPC.openExternalTerminal),
  gitClone: (payload) => ipcRenderer.invoke(IPC.gitClone, payload),
  gitStatus: (payload) => ipcRenderer.invoke(IPC.gitStatus, payload),
  gitRecentList: () => ipcRenderer.invoke(IPC.gitRecentList),
  gitRecentAdd: (payload) => ipcRenderer.invoke(IPC.gitRecentAdd, payload),
  selectFolder: () => ipcRenderer.invoke(IPC.selectFolder),
  onTerminalData: (handler) => {
    const listener = (
      _event: Electron.IpcRendererEvent,
      msg: { id: string; data: string }
    ): void => {
      handler(msg)
    }
    ipcRenderer.on(IPC.terminalData, listener)
    return () => ipcRenderer.removeListener(IPC.terminalData, listener)
  },
  onTerminalExit: (handler) => {
    const listener = (_event: Electron.IpcRendererEvent, msg: { id: string }): void => {
      handler(msg)
    }
    ipcRenderer.on(IPC.terminalExit, listener)
    return () => ipcRenderer.removeListener(IPC.terminalExit, listener)
  },
  openExternal: (url) => ipcRenderer.invoke('dh:openExternal', url),
}

contextBridge.exposeInMainWorld('dh', api)
