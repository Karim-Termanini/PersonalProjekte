import { contextBridge, ipcRenderer } from 'electron'

import { IPC, type ComposeProfile, type CustomProfileEntry } from '@linux-dev-home/shared'

export type DhApi = {
  dockerList: () => unknown
  dockerAction: (payload: { id: string; action: string }) => unknown
  dockerLogs: (payload: { id: string; tail?: number }) => unknown
  dockerImagesList: () => unknown
  dockerImageAction: (payload: { id: string; action: 'remove'; force?: boolean }) => unknown
  dockerVolumesList: () => unknown
  dockerVolumeAction: (payload: { name: string; action: 'remove' }) => unknown
  dockerNetworksList: () => unknown
  dockerNetworkAction: (payload: { id: string; action: 'remove' }) => unknown
  dockerPrune: () => unknown
  metrics: () => unknown
  hostExec: (payload: unknown) => unknown
  composeUp: (payload: { profile: ComposeProfile }) => unknown
  composeLogs: (payload: { profile: ComposeProfile }) => unknown
  terminalCreate: (payload: { cols: number; rows: number }) => unknown
  terminalWrite: (id: string, data: string) => void
  terminalResize: (id: string, cols: number, rows: number) => void
  openExternalTerminal: () => unknown
  gitClone: (payload: { url: string; targetDir: string }) => unknown
  gitStatus: (payload: { repoPath: string }) => unknown
  gitRecentList: () => unknown
  gitRecentAdd: (payload: { path: string }) => unknown
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
  storeGet: (payload: { key: 'custom_profiles' }) => Promise<CustomProfileEntry[] | null>
  storeSet: (payload: { key: 'custom_profiles'; data: CustomProfileEntry[] }) => Promise<unknown>
  jobStart: (payload: { kind: string; durationMs?: number }) => Promise<unknown>
  jobsList: () => Promise<unknown>
  jobCancel: (payload: { id: string }) => Promise<unknown>
}

const api: DhApi = {
  dockerList: () => ipcRenderer.invoke(IPC.dockerList),
  dockerAction: (payload) => ipcRenderer.invoke(IPC.dockerAction, payload),
  dockerLogs: (payload) => ipcRenderer.invoke(IPC.dockerLogs, payload),
  dockerImagesList: () => ipcRenderer.invoke(IPC.dockerImagesList),
  dockerImageAction: (payload) => ipcRenderer.invoke(IPC.dockerImageAction, payload),
  dockerVolumesList: () => ipcRenderer.invoke(IPC.dockerVolumesList),
  dockerVolumeAction: (payload) => ipcRenderer.invoke(IPC.dockerVolumeAction, payload),
  dockerNetworksList: () => ipcRenderer.invoke(IPC.dockerNetworksList),
  dockerNetworkAction: (payload) => ipcRenderer.invoke(IPC.dockerNetworkAction, payload),
  dockerPrune: () => ipcRenderer.invoke(IPC.dockerPrune),
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
  gitConfigSet: (payload) => ipcRenderer.invoke(IPC.gitConfigSet, payload),
  sshGenerate: (payload) => ipcRenderer.invoke(IPC.sshGenerate, payload),
  sshGetPub: (payload) => ipcRenderer.invoke(IPC.sshGetPub, payload),
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
  sessionInfo: () => ipcRenderer.invoke(IPC.sessionInfo),
  layoutGet: () => ipcRenderer.invoke(IPC.layoutGet),
  layoutSet: (layout) => ipcRenderer.invoke(IPC.layoutSet, layout),
  storeGet: (payload) => ipcRenderer.invoke(IPC.storeGet, payload),
  storeSet: (payload) => ipcRenderer.invoke(IPC.storeSet, payload),
  jobStart: (payload) => ipcRenderer.invoke(IPC.jobStart, payload),
  jobsList: () => ipcRenderer.invoke(IPC.jobsList),
  jobCancel: (payload) => ipcRenderer.invoke(IPC.jobCancel, payload),
}

contextBridge.exposeInMainWorld('dh', api)
