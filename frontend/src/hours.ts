/** 0 -> "12 am", 13 -> "1 pm". */
export function hourLabel(h: number): string {
  const suffix = h < 12 ? 'am' : 'pm'
  return `${h % 12 === 0 ? 12 : h % 12} ${suffix}`
}
