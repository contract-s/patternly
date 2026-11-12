import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { ApiError, api } from '../api/client'
import ReminderSettings from './ReminderSettings'

afterEach(() => vi.restoreAllMocks())

test('shows the current setting in the learner time zone', () => {
  render(<ReminderSettings initial={{ enabled: true, hour: 19 }} timezone="America/Detroit" />)
  expect(screen.getByRole('checkbox')).toBeChecked()
  expect(screen.getByRole('combobox')).toHaveDisplayValue('7 pm')
  expect(screen.getByText('(America/Detroit)')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
})

test('saves a new hour', async () => {
  const save = vi.spyOn(api, 'setReminders').mockResolvedValue({ enabled: true, hour: 7 })
  render(<ReminderSettings initial={{ enabled: true, hour: 19 }} timezone="UTC" />)
  await userEvent.selectOptions(screen.getByRole('combobox'), '7 am')
  await userEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(save).toHaveBeenCalledWith({ enabled: true, hour: 7 })
  expect(await screen.findByText('Saved')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
})

test('turning reminders off disables the hour', async () => {
  const save = vi.spyOn(api, 'setReminders').mockResolvedValue({ enabled: false, hour: 19 })
  render(<ReminderSettings initial={{ enabled: true, hour: 19 }} timezone="UTC" />)
  await userEvent.click(screen.getByRole('checkbox'))
  expect(screen.getByRole('combobox')).toBeDisabled()
  await userEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(save).toHaveBeenCalledWith({ enabled: false, hour: 19 })
})

test('shows the error when saving fails', async () => {
  vi.spyOn(api, 'setReminders').mockRejectedValue(new ApiError(500, 'Server error'))
  render(<ReminderSettings initial={{ enabled: true, hour: 19 }} timezone="UTC" />)
  await userEvent.selectOptions(screen.getByRole('combobox'), '9 pm')
  await userEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByText('Server error')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled()
})
