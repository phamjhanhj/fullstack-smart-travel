import {
  MAX_BUDGET_VND,
  estimateMinimumBudget,
  formatBudgetDigits,
  maximumEndDate,
  parseBudgetDigits,
  parseVietnameseDate,
  tripDurationDays,
} from './trip-policy';

describe('trip policy helpers', () => {
  it('validates real calendar dates', () => {
    expect(parseVietnameseDate('29/02/2028')).not.toBeNull();
    expect(parseVietnameseDate('29/02/2027')).toBeNull();
    expect(parseVietnameseDate('31/04/2027')).toBeNull();
  });

  it('calculates inclusive trip duration in UTC', () => {
    expect(tripDurationDays('31/12/2026', '01/01/2027')).toBe(2);
    expect(tripDurationDays('02/01/2027', '01/01/2027')).toBeNull();
  });

  it('caps the selectable end date at 90 inclusive days', () => {
    expect(maximumEndDate('01/01/2027')).toBe('31/03/2027');
  });

  it('formats budget text without floating point conversion', () => {
    expect(formatBudgetDigits('1000000000000')).toBe('1,000,000,000,000');
    expect(parseBudgetDigits('1,000,000,000,000')).toBeGreaterThan(MAX_BUDGET_VND);
  });

  it('estimates a minimum budget that rejects one thousand VND', () => {
    expect(estimateMinimumBudget(3, 2)).toBeGreaterThan(1_000);
  });
});
