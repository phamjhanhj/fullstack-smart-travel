import { Component, Input, forwardRef, ElementRef, ViewChild, OnChanges, OnInit, OnDestroy, inject, HostBinding } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

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
  @Input() items: string[] = [];
  @Input() placeholder: string = 'Chọn...';
  @Input() disabled: boolean = false;
  @Input() isInvalid: boolean = false;

  @HostBinding('class.is-open') get hostIsOpen(): boolean {
    return this.isOpen;
  }

  @ViewChild('searchInput') searchInput!: ElementRef<HTMLInputElement>;
  @ViewChild('container') container!: ElementRef;

  private readonly elementRef = inject(ElementRef);

  selectedValue: string = '';
  isOpen: boolean = false;
  searchText: string = '';
  filteredItems: string[] = [];

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
    this.filteredItems = [...this.items];
  }

  writeValue(value: any): void {
    this.selectedValue = value || '';
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
      this.searchText = '';
      this.filteredItems = [...this.items];
      setTimeout(() => {
        if (this.searchInput) {
          this.searchInput.nativeElement.focus();
        }
      }, 50);
    }
  }

  filterItems(): void {
    const search = this.searchText.toLowerCase().trim();
    if (!search) {
      this.filteredItems = [...this.items];
    } else {
      this.filteredItems = this.items.filter(item =>
        item.toLowerCase().includes(search)
      );
    }
  }

  selectItem(item: string): void {
    this.selectedValue = item;
    this.onChange(item);
    this.onTouched();
    this.isOpen = false;
  }

  clearSearch(event: Event): void {
    event.stopPropagation();
    this.searchText = '';
    this.filteredItems = [...this.items];
    if (this.searchInput) {
      this.searchInput.nativeElement.focus();
    }
  }
}
