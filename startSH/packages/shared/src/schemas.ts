import { z } from 'zod'

export const DockerContainerActionSchema = z.enum(['start', 'stop', 'restart'])

export const DockerLogsRequestSchema = z.object({
  id: z.string().min(1).max(256),
  tail: z.number().int().min(1).max(5000).optional(),
})

export const HostExecRequestSchema = z.object({
  command: z.enum([
    'systemctl_is_active',
    'nvidia_smi_short',
    'flatpak_spawn_echo',
  ] as const),
  unit: z.string().max(128).optional(),
})

export const ComposeProfileSchema = z.enum([
  'web-dev',
  'data-science',
  'ai-ml',
  'mobile',
  'game-dev',
  'infra',
  'desktop-gui',
  'docs',
  'empty'
])

export const StoreSetRequestSchema = z.object({
  key: z.string().min(1).max(128),
  data: z.any(),
})

export const StoreGetRequestSchema = z.object({
  key: z.string().min(1).max(128),
})
export const ComposeUpRequestSchema = z.object({
  profile: ComposeProfileSchema,
})

export const GitCloneRequestSchema = z.object({
  url: z.string().url().max(2048),
  targetDir: z.string().min(1).max(4096),
})

export const GitStatusRequestSchema = z.object({
  repoPath: z.string().min(1).max(4096),
})

export const GitRecentAddSchema = z.object({
  path: z.string().min(1).max(4096),
})

export type DockerContainerAction = z.infer<typeof DockerContainerActionSchema>
export type ComposeProfile = z.infer<typeof ComposeProfileSchema>
