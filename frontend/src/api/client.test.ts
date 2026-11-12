import { afterEach, expect, test, vi } from 'vitest'
import { ApiError, api, getToken, setToken } from './client'

function mockFetch(status: number, body: unknown) {
  const fn = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status }))
  vi.stubGlobal('fetch', fn)
  return fn
}

afterEach(() => vi.unstubAllGlobals())

test('sends JSON and the bearer token', async () => {
  setToken('tok')
  const fetch = mockFetch(200, { attempt: {} })
  await api.submit('my answer')
  const [url, init] = fetch.mock.calls[0]
  expect(url).toBe('/api/lessons/today/attempts')
  expect(init.method).toBe('POST')
  expect(init.headers).toEqual({ Authorization: 'Bearer tok', 'Content-Type': 'application/json' })
  expect(JSON.parse(init.body)).toEqual({ answer: 'my answer' })
})

test('no token, no auth header', async () => {
  const fetch = mockFetch(200, {})
  await api.today()
  expect(fetch.mock.calls[0][1].headers).toEqual({})
})

test('turns error bodies into ApiError messages', async () => {
  mockFetch(409, { detail: "Today's lesson is already finished." })
  await expect(api.submit('x')).rejects.toEqual(new ApiError(409, "Today's lesson is already finished."))
  mockFetch(422, { detail: [{ msg: 'String should have at least 8 characters' }] })
  await expect(api.register('a@b.c', 'short', 'UTC')).rejects.toThrow('at least 8 characters')
  mockFetch(500, null)
  await expect(api.me()).rejects.toThrow('Request failed (500)')
})

test('network failure is a friendly error', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('fetch failed')))
  await expect(api.me()).rejects.toMatchObject({ status: 0, message: expect.stringContaining("Can't reach") })
})

test('token storage', () => {
  setToken('abc')
  expect(getToken()).toBe('abc')
  setToken(null)
  expect(getToken()).toBeNull()
})
