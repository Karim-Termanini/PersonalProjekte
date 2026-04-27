import { describe, expect, it } from 'vitest'
import {
  ComposeUpRequestSchema,
  DockerLogsRequestSchema,
  GitCloneRequestSchema,
  HostExecRequestSchema,
} from '../src/schemas'

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
})
