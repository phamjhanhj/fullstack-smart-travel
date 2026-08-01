import { escapeSpreadsheetText } from './xlsx-export-adapter';

describe('escapeSpreadsheetText', () => {
  it('neutralizes values that spreadsheet software could treat as formulas', () => {
    expect(escapeSpreadsheetText('=HYPERLINK("https://example.com")')).toBe(
      '\'=HYPERLINK("https://example.com")',
    );
    expect(escapeSpreadsheetText('  @SUM(1,2)')).toBe("'  @SUM(1,2)");
  });

  it('keeps regular itinerary text unchanged', () => {
    expect(escapeSpreadsheetText('Tham quan Hồ Gươm')).toBe('Tham quan Hồ Gươm');
  });
});
