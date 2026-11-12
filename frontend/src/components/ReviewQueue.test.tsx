import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { api } from '../api/client'
import ReviewQueue from './ReviewQueue'

afterEach(() => vi.restoreAllMocks())

test('lists due and upcoming patterns', async () => {
  vi.spyOn(api, 'reviews').mockResolvedValue({
    due: [{ pattern: 'bfs', name: 'Breadth-first search', box: 1, due: '2026-11-12', last_outcome: 'missed' }],
    upcoming: [{ pattern: 'heap', name: 'Heap', box: 3, due: '2026-11-16', last_outcome: 'clean' }],
  })
  render(<ReviewQueue />)
  expect(await screen.findByText('Breadth-first search')).toBeInTheDocument()
  expect(screen.getByText(/missed · box 1/)).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Coming up' })).toBeInTheDocument()
  expect(screen.getByText(/solved first try · box 3/)).toBeInTheDocument()
})

test('hidden when nothing has been learned yet', async () => {
  const reviews = vi.spyOn(api, 'reviews').mockResolvedValue({ due: [], upcoming: [] })
  const { container } = render(<ReviewQueue />)
  await vi.waitFor(() => expect(reviews).toHaveBeenCalled())
  expect(container).toBeEmptyDOMElement()
})

test('reloads when the version changes', async () => {
  const reviews = vi.spyOn(api, 'reviews').mockResolvedValue({ due: [], upcoming: [] })
  const { rerender } = render(<ReviewQueue version={0} />)
  rerender(<ReviewQueue version={1} />)
  await vi.waitFor(() => expect(reviews).toHaveBeenCalledTimes(2))
})
