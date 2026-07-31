import { Component, Input, forwardRef, ElementRef, ViewChild, OnChanges, OnInit, OnDestroy, inject, HostBinding } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

export interface SelectOption {
  label: string;
  value: any;
}

@Component({
  selector: 'app-custom-select',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './custom-select.html',
  styleUrl: './custom-select.css',
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => CustomSelectComponent),
      multi: true,
    }
  ]
})
export class CustomSelectComponent implements ControlValueAccessor, OnChanges, OnInit, OnDestroy {
  @Input() items: (string | SelectOption)[] = [];
  @Input() placeholder: string = 'Chọn...';
  @Input() disabled: boolean = false;
  @Input() isInvalid: boolean = false;
  @Input() searchable: boolean = true;

  @HostBinding('class.is-open') get hostIsOpen(): boolean {
    return this.isOpen;
  }

  @HostBinding('class.drop-up') get hostIsDropUp(): boolean {
    return this.dropUp;
  }

  @ViewChild('searchInput') searchInput!: ElementRef<HTMLInputElement>;
  @ViewChild('container') container!: ElementRef;

  private readonly elementRef = inject(ElementRef);

  selectedValue: any = '';
  isOpen: boolean = false;
  dropUp: boolean = false;
  searchText: string = '';
  normalizedItems: SelectOption[] = [];
  filteredItems: SelectOption[] = [];

  onChange = (value: any) => {};
  onTouched = () => {};

  ngOnInit(): void {
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

  ngOnChanges(): void {
    this.normalizeItems();
    this.filterItems();
  }

  private normalizeItems(): void {
    this.normalizedItems = (this.items || []).map(item => {
      if (typeof item === 'object' && item !== null && 'label' in item && 'value' in item) {
        return item as SelectOption;
      }
      return { label: String(item), value: item };
    });
  }

  get selectedLabel(): string {
    const found = this.normalizedItems.find(opt => opt.value === this.selectedValue);
    if (found) return found.label;
    if (this.selectedValue !== null && this.selectedValue !== undefined && this.selectedValue !== '') {
      return String(this.selectedValue);
    }
    return '';
  }

  writeValue(value: any): void {
    this.selectedValue = value ?? '';
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
    if (this.isOpen) {
      this.checkDirection();
      this.searchText = '';
      this.filterItems();
      if (this.searchable && this.normalizedItems.length > 4) {
        setTimeout(() => {
          if (this.searchInput) {
            this.searchInput.nativeElement.focus();
          }
        }, 50);
      }
    }
  }

  private checkDirection(): void {
    const el = (this.container?.nativeElement || this.elementRef?.nativeElement) as HTMLElement;
    if (!el) return;
    const rect = el.getBoundingClientRect();

    // Check modal parent container space
    const modalCard = el.closest('.modal-card, .modal-dialog, [role="dialog"]') as HTMLElement | null;
    if (modalCard) {
      const modalRect = modalCard.getBoundingClientRect();
      const spaceInModalBelow = modalRect.bottom - rect.bottom;
      const spaceInModalAbove = rect.top - modalRect.top;

      if (spaceInModalBelow < 210 && spaceInModalAbove > spaceInModalBelow) {
        this.dropUp = true;
        return;
      }
    }

    const windowHeight = window.innerHeight || document.documentElement.clientHeight;
    const spaceBelow = windowHeight - rect.bottom;
    const spaceAbove = rect.top;

    this.dropUp = spaceBelow < 230 && spaceAbove > spaceBelow;
  }

  filterItems(): void {
    const search = this.searchText.toLowerCase().trim();
    if (!search) {
      this.filteredItems = [...this.normalizedItems];
    } else {
      this.filteredItems = this.normalizedItems.filter(item =>
        item.label.toLowerCase().includes(search)
      );
    }
  }

  selectItem(option: SelectOption): void {
    this.selectedValue = option.value;
    this.onChange(option.value);
    this.onTouched();
    this.isOpen = false;
  }

  clearSearch(event: Event): void {
    event.stopPropagation();
    this.searchText = '';
    this.filterItems();
    if (this.searchInput && this.searchable && this.normalizedItems.length > 4) {
      this.searchInput.nativeElement.focus();
    }
  }
}
