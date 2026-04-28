import { describe, expect, it } from 'vitest'
import { DashboardLayoutFileSchema } from '../src/foundation'
import {
  ComposeUpRequestSchema,
  DockerLogsRequestSchema,
  GitCloneRequestSchema,
  HostExecRequestSchema,
} from '../src/schemas'
import { isRegisteredWidgetType } from '../src/widgetRegistry'

describe('schemas', () => {
  it('rejects arbitrary host exec', () => {
    expect(() =>
      HostExecRequestSchema.parse({ command: 'rm_rf_root' as never })
    ).toThrow()
  })

  it('accepts docker logs with bounds', () => {
    expect(DockerLogsRequestSchema.parse({ id: 'abc', tail: 100 })).toEqual({
      id: 'abc',
      tail: 100,
    })
  })

  it('accepts compose profiles only', () => {
    expect(ComposeUpRequestSchema.parse({ profile: 'web-dev' })).toEqual({
      profile: 'web-dev',
    })
  })

  it('validates git clone url', () => {
    expect(() =>
      GitCloneRequestSchema.parse({
        url: 'not-a-url',
        targetDir: '/tmp/x',
      })
    ).toThrow()
  })

  it('parses dashboard layout file', () => {
    const v = DashboardLayoutFileSchema.parse({
      version: 1,
      placements: [{ instanceId: 'a', widgetTypeId: 'static.docker-permission-hint' }],
    })
    expect(v.placements).toHaveLength(1)
    expect(isRegisteredWidgetType('static.docker-permission-hint')).toBe(true)
    expect(isRegisteredWidgetType('unknown.widget')).toBe(false)
  })
})
