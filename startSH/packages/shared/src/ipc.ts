import type { ComposeProfile, DockerContainerAction } from './schemas.js'

export type ContainerRow = {
  id: string
  name: string
  image: string
  state: string
  status: string
  ports: string
}

export type HostMetrics = {
  cpuUsagePercent: number
  cpuModel: string
  loadAvg: number[]
  totalMemMb: number
  freeMemMb: number
  uptimeSec: number
  diskTotalGb: number
  diskFreeGb: number
  netRxMbps: number
  netTxMbps: number
}

export type SystemdRow = {
  name: string
  state: Readonly<'active' | 'inactive' | 'failed' | 'unknown'>
}

export type GitRepoEntry = {
  path: string
  lastOpened: number
}

/** Renderer ↔ main IPC channel names */
export type HostMetricsResponse = {
  metrics: HostMetrics
  systemd: SystemdRow[]
}

export const IPC = {
  dockerList: 'dh:docker:list',
  dockerAction: 'dh:docker:action',
  dockerLogs: 'dh:docker:logs',
  /** Returns HostMetricsResponse (metrics + read-only systemd rows). */
  metrics: 'dh:metrics',
  hostExec: 'dh:host:exec',
  composeUp: 'dh:compose:up',
  composeLogs: 'dh:compose:logs',
  terminalCreate: 'dh:terminal:create',
  terminalWrite: 'dh:terminal:write',
  terminalResize: 'dh:terminal:resize',
  terminalData: 'dh:terminal:data',
  terminalExit: 'dh:terminal:exit',
  openExternalTerminal: 'dh:terminal:openExternal',
  gitClone: 'dh:git:clone',
  gitStatus: 'dh:git:status',
  gitRecentList: 'dh:git:recent:list',
  gitRecentAdd: 'dh:git:recent:add',
  gitConfigSet: 'dh:git:config:set',
  sshGenerate: 'dh:ssh:generate',
  sshGetPub: 'dh:ssh:get:pub',
  selectFolder: 'dh:dialog:folder',
  sessionInfo: 'dh:session:info',
  layoutGet: 'dh:layout:get',
  layoutSet: 'dh:layout:set',
  storeGet: 'dh:store:get',
  storeSet: 'dh:store:set',
  jobStart: 'dh:job:start',
  jobsList: 'dh:job:list',
  jobCancel: 'dh:job:cancel',
} as const

export type DockerActionPayload = { id: string; action: DockerContainerAction }

export type ComposeUpPayload = { profile: ComposeProfile }
