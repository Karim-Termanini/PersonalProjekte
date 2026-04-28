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
  'empty',
])

/** Preserved compose template id for a user-named dashboard profile. */
export const CustomProfileEntrySchema = z.object({
  name: z.string().trim().min(1).max(128),
  baseTemplate: ComposeProfileSchema,
})

export const CustomProfilesStoreSchema = z.array(CustomProfileEntrySchema).max(50)

/** Keys with typed payloads persisted under userData (`store_<key>.json`). */
export const StoreKeySchema = z.enum(['custom_profiles'])

export const StoreGetRequestSchema = z.object({
  key: StoreKeySchema,
})

export const StoreSetRequestSchema = z.discriminatedUnion('key', [
  z.object({
    key: z.literal('custom_profiles'),
    data: CustomProfilesStoreSchema,
  }),
])
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
export type CustomProfileEntry = z.infer<typeof CustomProfileEntrySchema>
export type StoreKey = z.infer<typeof StoreKeySchema>
export type StoreSetRequest = z.infer<typeof StoreSetRequestSchema>
