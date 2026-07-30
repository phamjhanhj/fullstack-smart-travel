import { Component, Input, forwardRef, ElementRef, ViewChild, OnInit, OnDestroy, inject, HostBinding } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

@Component({
  selector: 'app-custom-date-picker',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './custom-date-picker.html',
  styleUrl: './custom-date-picker.css',
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => CustomDatePickerComponent),
      multi: true,
    }
  ]
})
export class CustomDatePickerComponent implements ControlValueAccessor, OnInit, OnDestroy {
  @Input() placeholder: string = 'dd/mm/yyyy';
  @Input() disabled: boolean = false;
  @Input() isInvalid: boolean = false;
  @Input() minDate: string = '';

  @HostBinding('class.is-open') get hostIsOpen(): boolean {
    return this.isOpen;
  }

  @ViewChild('container') container!: ElementRef;

  private readonly elementRef = inject(ElementRef);

  selectedValue: string = '';
  isOpen: boolean = false;
  
  viewDate: Date = new Date();
  calendarDays: Date[] = [];
  weekdays: string[] = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'];

  onChange = (value: any) => {};
  onTouched = () => {};

  ngOnInit(): void {
    this.generateCalendar();
    document.addEventListener('click', this.onDocumentClick, true);
  }

  ngOnDestroy(): void {
    document.removeEventListener('click', this.onDocumentClick, true);
  }

  private readonly onDocumentClick = (event: MouseEvent): void => {
    if (this.isOpen && !this.elementRef.nativeElement.contains(event.target)) {
      this.isOpen = false;
      this.onTouched();
    }
  };

  writeValue(value: any): void {
    this.selectedValue = value || '';
    if (this.selectedValue) {
      const parsed = this.parseDateStr(this.selectedValue);
      if (parsed) {
        this.viewDate = parsed;
        this.generateCalendar();
      }
    }
  }

  registerOnChange(fn: any): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: any): void {
    this.onTouched = fn;
  }

  setDisabledState(isDisabled: boolean): void {
    this.disabled = isDisabled;
  }

  toggleDropdown(): void {
    if (this.disabled) return;
    this.isOpen = !this.isOpen;
    if (this.isOpen && this.selectedValue) {
      const parsed = this.parseDateStr(this.selectedValue);
      if (parsed) {
        this.viewDate = parsed;
        this.generateCalendar();
      }
    }
  }

  prevMonth(event: Event): void {
    event.stopPropagation();
    const current = new Date(this.viewDate.getTime());
    current.setMonth(current.getMonth() - 1);
    this.viewDate = current;
    this.generateCalendar();
  }

  nextMonth(event: Event): void {
    event.stopPropagation();
    const current = new Date(this.viewDate.getTime());
    current.setMonth(current.getMonth() + 1);
    this.viewDate = current;
    this.generateCalendar();
  }

  generateCalendar(): void {
    const year = this.viewDate.getFullYear();
    const month = this.viewDate.getMonth();

    const firstDay = new Date(year, month, 1);
    let firstDayOfWeek = firstDay.getDay(); // 0 = Sun, 1 = Mon...
    let startOffset = firstDayOfWeek === 0 ? 6 : firstDayOfWeek - 1;

    const startDate = new Date(year, month, 1 - startOffset);

    const grid: Date[] = [];
    for (let i = 0; i < 42; i++) {
      const day = new Date(startDate.getTime());
      day.setDate(startDate.getDate() + i);
      grid.push(day);
    }
    this.calendarDays = grid;
  }

  selectDay(day: Date, event: Event): void {
    event.stopPropagation();
    const formatted = this.formatDate(day);
    this.selectedValue = formatted;
    this.onChange(formatted);
    this.onTouched();
    this.isOpen = false;
  }

  isPastDate(day: Date): boolean {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    let minLimit = today;
    if (this.minDate) {
      const parsedMin = this.parseDateStr(this.minDate);
      if (parsedMin) {
        minLimit = parsedMin;
      }
    }

    const checkDate = new Date(day.getFullYear(), day.getMonth(), day.getDate());
    return checkDate.getTime() < minLimit.getTime();
  }

  isToday(day: Date): boolean {
    const today = new Date();
    return day.getDate() === today.getDate() &&
           day.getMonth() === today.getMonth() &&
           day.getFullYear() === today.getFullYear();
  }

  isSelected(day: Date): boolean {
    if (!this.selectedValue) return false;
    const parsed = this.parseDateStr(this.selectedValue);
    if (!parsed) return false;
    return day.getDate() === parsed.getDate() &&
           day.getMonth() === parsed.getMonth() &&
           day.getFullYear() === parsed.getFullYear();
  }

  private formatDate(date: Date): string {
    const dd = String(date.getDate()).padStart(2, '0');
    const mm = String(date.getMonth() + 1).padStart(2, '0');
    const yyyy = date.getFullYear();
    return `${dd}/${mm}/${yyyy}`;
  }

  private parseDateStr(str: string): Date | null {
    const parts = str.split('/');
    if (parts.length === 3) {
      const dd = Number(parts[0]);
      const mm = Number(parts[1]) - 1;
      const yyyy = Number(parts[2]);
      if (!isNaN(dd) && !isNaN(mm) && !isNaN(yyyy)) {
        return new Date(yyyy, mm, dd);
      }
    }
    return null;
  }
}
