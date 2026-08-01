export const MAX_TRIP_DURATION_DAYS = 90;
export const MAX_SYNC_AI_DAYS = 7;
export const MAX_BUDGET_VND = 2_000_000_000;
export const MAX_TRAVELERS = 50;

export function parseBudgetDigits(value: unknown): number | null {
  const digits = String(value ?? '').replace(/\D/g, '');
  if (!digits) return null;
  const amount = Number(digits);
  return Number.isSafeInteger(amount) ? amount : Number.POSITIVE_INFINITY;
}

export function formatBudgetDigits(value: unknown): string {
  const digits = String(value ?? '').replace(/\D/g, '').replace(/^0+(?=\d)/, '');
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

export function parseVietnameseDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(value);
  if (!match) return null;
  const day = Number(match[1]);
  const month = Number(match[2]);
  const year = Number(match[3]);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  if (
    parsed.getUTCFullYear() !== year ||
    parsed.getUTCMonth() !== month - 1 ||
    parsed.getUTCDate() !== day
  ) {
    return null;
  }
  return parsed;
}

export function tripDurationDays(start: string, end: string): number | null {
  const startDate = parseVietnameseDate(start);
  const endDate = parseVietnameseDate(end);
  if (!startDate || !endDate || endDate < startDate) return null;
  return Math.floor((endDate.getTime() - startDate.getTime()) / 86_400_000) + 1;
}

export function maximumEndDate(start: string | null | undefined): string {
  const startDate = parseVietnameseDate(start);
  if (!startDate) return '';
  const maxDate = new Date(startDate.getTime());
  maxDate.setUTCDate(maxDate.getUTCDate() + MAX_TRIP_DURATION_DAYS - 1);
  return [
    String(maxDate.getUTCDate()).padStart(2, '0'),
    String(maxDate.getUTCMonth() + 1).padStart(2, '0'),
    maxDate.getUTCFullYear(),
  ].join('/');
}

export function estimateMinimumBudget(days: number, travelers: number): number {
  const safeTravelers = Math.max(1, Math.min(MAX_TRAVELERS, Math.trunc(travelers || 1)));
  const rooms = Math.max(1, Math.ceil(safeTravelers / 2));
  const totalCost =
    500_000 * safeTravelers +
    250_000 * rooms * Math.max(days - 1, 0) +
    320_000 * safeTravelers * days;
  return Math.ceil(totalCost / 1.15);
}
