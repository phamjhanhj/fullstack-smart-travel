import writeXlsxFile, {
  type CellObject,
  type Sheet,
  type SheetData,
} from 'write-excel-file/browser';

interface CellAddress {
  r: number;
  c: number;
}

interface CellRange {
  s: CellAddress;
  e: CellAddress;
}

interface LegacyWorkbook {
  sheets: Array<{ name: string; worksheet: Record<string, any> }>;
}

export function escapeSpreadsheetText(value: unknown): string {
  const text = String(value ?? '');
  return /^[\t\r\n ]*[=+\-@]/.test(text) ? `'${text}` : text;
}

function columnName(index: number): string {
  let value = index + 1;
  let result = '';
  while (value > 0) {
    value -= 1;
    result = String.fromCharCode(65 + (value % 26)) + result;
    value = Math.floor(value / 26);
  }
  return result;
}

function decodeAddress(reference: string): CellAddress {
  const match = /^([A-Z]+)(\d+)$/.exec(reference);
  if (!match) throw new Error(`Invalid cell reference: ${reference}`);
  let column = 0;
  for (const character of match[1]) column = column * 26 + character.charCodeAt(0) - 64;
  return { r: Number(match[2]) - 1, c: column - 1 };
}

function color(value: string | undefined): string | undefined {
  if (!value) return undefined;
  return value.startsWith('#') ? value : `#${value.slice(-6)}`;
}

function convertCell(source: any, rowHeight?: number): CellObject {
  const style = source?.s ?? {};
  const border = style.border ?? {};
  const cell: CellObject = {
    value: source?.t === 'n' ? Number(source?.v ?? 0) : escapeSpreadsheetText(source?.v),
    type: source?.t === 'n' ? Number : String,
    format: source?.z ?? style.numFmt,
    fontFamily: style.font?.name,
    fontSize: style.font?.sz,
    fontWeight: style.font?.bold ? 'bold' : undefined,
    textColor: color(style.font?.color?.rgb),
    backgroundColor: color(style.fill?.fgColor?.rgb),
    align: style.alignment?.horizontal,
    alignVertical: style.alignment?.vertical,
    wrap: Boolean(style.alignment?.wrapText),
    height: rowHeight,
    topBorderStyle: border.top?.style,
    topBorderColor: color(border.top?.color?.rgb),
    bottomBorderStyle: border.bottom?.style,
    bottomBorderColor: color(border.bottom?.color?.rgb),
    leftBorderStyle: border.left?.style,
    leftBorderColor: color(border.left?.color?.rgb),
    rightBorderStyle: border.right?.style,
    rightBorderColor: color(border.right?.color?.rgb),
  };
  return Object.fromEntries(Object.entries(cell).filter(([, value]) => value !== undefined)) as CellObject;
}

function worksheetToSheet(name: string, worksheet: Record<string, any>): Sheet<Blob> {
  const range: CellRange = worksheet['!ref']
    ? (() => {
        const [start, end] = String(worksheet['!ref']).split(':');
        return { s: decodeAddress(start), e: decodeAddress(end ?? start) };
      })()
    : { s: { r: 0, c: 0 }, e: { r: 0, c: 0 } };
  const data: SheetData = [];

  for (let row = range.s.r; row <= range.e.r; row += 1) {
    const outputRow = [];
    const rowHeight = worksheet['!rows']?.[row]?.hpt;
    for (let column = range.s.c; column <= range.e.c; column += 1) {
      const source = worksheet[encodeCell({ r: row, c: column })];
      outputRow.push(source ? convertCell(source, rowHeight) : null);
    }
    data.push(outputRow);
  }

  for (const merge of (worksheet['!merges'] ?? []) as CellRange[]) {
    const row = merge.s.r - range.s.r;
    const column = merge.s.c - range.s.c;
    const first = data[row]?.[column] as CellObject | null | undefined;
    if (first && typeof first === 'object') {
      first.columnSpan = merge.e.c - merge.s.c + 1;
      first.rowSpan = merge.e.r - merge.s.r + 1;
    }
    for (let r = merge.s.r; r <= merge.e.r; r += 1) {
      for (let c = merge.s.c; c <= merge.e.c; c += 1) {
        if (r !== merge.s.r || c !== merge.s.c) data[r - range.s.r][c - range.s.c] = null;
      }
    }
  }

  return {
    sheet: name.slice(0, 31),
    data,
    columns: (worksheet['!cols'] ?? []).map((item: any) => ({ width: item.wch })),
  };
}

function encodeCell(address: CellAddress): string {
  return `${columnName(address.c)}${address.r + 1}`;
}

function encodeRange(range: CellRange): string {
  return `${encodeCell(range.s)}:${encodeCell(range.e)}`;
}

export const utils = {
  book_new(): LegacyWorkbook {
    return { sheets: [] };
  },
  encode_cell: encodeCell,
  encode_range: encodeRange,
  book_append_sheet(workbook: LegacyWorkbook, worksheet: Record<string, any>, name: string): void {
    workbook.sheets.push({ name, worksheet });
  },
};

export function writeFile(workbook: LegacyWorkbook, fileName: string): void {
  const sheets = workbook.sheets.map(({ name, worksheet }) => worksheetToSheet(name, worksheet));
  void writeXlsxFile(sheets, { fontFamily: 'Segoe UI', fontSize: 10 })
    .toFile(fileName)
    .catch(() => window.alert('Không thể xuất file Excel lúc này. Vui lòng thử lại.'));
}
