import { expect, test } from 'vitest'
import { hourLabel } from './hours'

test('labels hours on a 12-hour clock', () => {
  expect([0, 7, 12, 19, 23].map(hourLabel)).toEqual(['12 am', '7 am', '12 pm', '7 pm', '11 pm'])
})
