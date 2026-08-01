import { CommonModule } from '@angular/common';
import { Component, HostListener, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { PublicTripListItem, PublicTripService } from '../../services/public-trip.service';
import { UserService, PublicUserSearchResult } from '../../services/user.service';
import { Subject } from 'rxjs';
import { debounceTime, distinctUntilChanged, switchMap, catchError } from 'rxjs/operators';
import { of } from 'rxjs';
import { MAX_BUDGET_VND, MAX_TRIP_DURATION_DAYS } from '../../config/trip-policy';

@Component({
  selector: 'app-community-list',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './community-list.html',
  styleUrl: './community-list.css',
})
export class CommunityListComponent implements OnInit {
  private readonly publicTrips = inject(PublicTripService);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly userService = inject(UserService);

  readonly items = signal<PublicTripListItem[]>([]);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly view = signal<'explore' | 'saved' | 'recommended'>('explore');
  readonly recommendationReasons = signal<Record<string,string>>({});
  destination = '';
  sort = 'newest';

  // ── Advanced filters ──
  readonly isFilterOpen = signal(false);
  readonly filterError = signal<string | null>(null);
  filterSearch = '';
  filterMaxCost: number | null = null;
  filterMinDays: number | null = null;
  filterMaxDays: number | null = null;
  filterMinRating: number | null = null;
  filterTravelerType = '';
  filterPace = '';

  readonly travelerTypeOptions = [
    { value: '', label: 'Tất cả' },
    { value: 'solo', label: 'Du lịch một mình' },
    { value: 'couple', label: 'Cặp đôi' },
    { value: 'family', label: 'Gia đình' },
    { value: 'friends', label: 'Nhóm bạn bè' },
  ];
  readonly paceOptions = [
    { value: '', label: 'Tất cả' },
    { value: 'relaxed', label: 'Thư giãn' },
    { value: 'balanced', label: 'Cân bằng' },
    { value: 'packed', label: 'Dày đặc' },
  ];
  readonly ratingOptions = [
    { value: null as number | null, label: 'Tất cả' },
    { value: 3, label: '≥ 3 sao' },
    { value: 4, label: '≥ 4 sao' },
    { value: 5, label: '= 5 sao' },
  ];

  // ── User Search ──
  readonly userSearchQuery = signal('');
  readonly userSearchResults = signal<PublicUserSearchResult[]>([]);
  readonly isUserSearchFocused = signal(false);
  readonly isSearchingUsers = signal(false);
  private readonly userSearchSubject = new Subject<string>();

  readonly sortOptions = [
    { value: 'newest', label: 'Mới nhất' },
    { value: 'recommended', label: 'Đánh giá tốt' },
    { value: 'most_saved', label: 'Lưu nhiều nhất' },
    { value: 'lowest_cost', label: 'Chi phí thấp' },
  ];
  readonly isSortOpen = signal(false);

  @HostListener('document:click')
  closeSortDropdown(): void {
    this.isSortOpen.set(false);
    this.isUserSearchFocused.set(false);
  }

  toggleSortDropdown(event?: Event): void {
    if (event) event.stopPropagation();
    this.isSortOpen.update(v => !v);
  }

  selectSortOption(value: string): void {
    this.sort = value;
    this.isSortOpen.set(false);
    this.load();
  }

  getSortLabel(): string {
    const found = this.sortOptions.find(o => o.value === this.sort);
    return found ? found.label : 'Mới nhất';
  }

  ngOnInit(): void {
    if (this.route.snapshot.queryParamMap.get('view') === 'recommended') {
      if (!this.auth.isAuthenticated()) { this.router.navigate(['/login'], { queryParams: { returnUrl: '/community?view=recommended' } }); return; }
      this.view.set('recommended');
    }
    if (this.route.snapshot.queryParamMap.get('view') === 'saved') {
      if (!this.auth.isAuthenticated()) {
        this.router.navigate(['/login'], { queryParams: { returnUrl: '/community?view=saved' } });
        return;
      }
      this.view.set('saved');
    }
    this.load();

    // Setup user search debounce
    this.userSearchSubject.pipe(
      debounceTime(300),
      distinctUntilChanged(),
      switchMap(query => {
        if (query.trim().length < 1) {
          return of({ data: [] as PublicUserSearchResult[] });
        }
        this.isSearchingUsers.set(true);
        return this.userService.searchPublicUsers(query).pipe(
          catchError(() => of({ data: [] as PublicUserSearchResult[] }))
        );
      })
    ).subscribe(response => {
      this.userSearchResults.set(response.data || []);
      this.isSearchingUsers.set(false);
    });
  }

  setView(view: 'explore' | 'saved' | 'recommended'): void {
    if (view !== 'explore' && !this.auth.isAuthenticated()) {
      this.router.navigate(['/login'], { queryParams: { returnUrl: '/community?view=saved' } });
      return;
    }
    this.view.set(view);
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: view === 'saved' ? { view: 'saved' } : view === 'recommended' ? { view: 'recommended' } : { view: null },
      queryParamsHandling: 'merge',
      replaceUrl: true,
    });
    this.load();
  }

  load(): void {
    if (this.view() === 'explore' && !this.validateFilters()) return;
    this.loading.set(true);
    this.error.set(null);
    if (this.view() === 'recommended') {
      this.publicTrips.recommendations().subscribe({ next: response => { const rows=response.data||[]; this.items.set(rows.map(row=>row.publication)); this.recommendationReasons.set(Object.fromEntries(rows.map(row=>[row.publication.id,row.reason]))); this.loading.set(false); }, error:error=>{this.error.set(error?.error?.message||'Không thể tải gợi ý.');this.loading.set(false);} });
      return;
    }
    const request = this.view() === 'saved'
      ? this.publicTrips.listSaved(1, 50)
      : this.publicTrips.list({
          destination: this.destination.trim(),
          search: this.filterSearch.trim() || undefined,
          maxCost: this.filterMaxCost || undefined,
          minDays: this.filterMinDays || undefined,
          maxDays: this.filterMaxDays || undefined,
          minRating: this.filterMinRating || undefined,
          travelerType: this.filterTravelerType || undefined,
          pace: this.filterPace || undefined,
          sort: this.sort,
        });
    request.subscribe({
      next: (response) => {
        this.items.set(response.data?.items || []);
        this.loading.set(false);
      },
      error: (error) => {
        this.error.set(error?.error?.message || 'Không thể tải lịch trình cộng đồng.');
        this.loading.set(false);
      },
    });
  }

  hideRecommendation(publicationId:string,event:Event):void { event.preventDefault();event.stopPropagation();this.publicTrips.hideRecommendation(publicationId).subscribe({next:()=>this.items.update(items=>items.filter(item=>item.id!==publicationId))}); }

  money(value: number | null): string {
    return value == null ? 'Chưa công khai' : `${new Intl.NumberFormat('en-US').format(value)} VND/người`;
  }

  // ── Filter helpers ──
  toggleFilterPanel(event?: Event): void {
    if (event) event.stopPropagation();
    this.isFilterOpen.update(v => !v);
  }

  applyFilters(): void {
    if (!this.validateFilters()) return;
    this.isFilterOpen.set(false);
    this.load();
  }

  resetFilters(): void {
    this.filterSearch = '';
    this.filterMaxCost = null;
    this.filterMinDays = null;
    this.filterMaxDays = null;
    this.filterMinRating = null;
    this.filterTravelerType = '';
    this.filterPace = '';
    this.destination = '';
    this.filterError.set(null);
    this.load();
  }

  private validateFilters(): boolean {
    let message: string | null = null;
    if (this.destination.trim().length > 120) {
      message = 'Điểm đến không được vượt quá 120 ký tự.';
    } else if (this.filterSearch.trim().length > 200) {
      message = 'Từ khóa không được vượt quá 200 ký tự.';
    } else if (this.filterMaxCost !== null && (!Number.isFinite(this.filterMaxCost) || this.filterMaxCost < 0 || this.filterMaxCost > MAX_BUDGET_VND)) {
      message = 'Ngân sách lọc phải từ 0 đến 2.000.000.000 VND.';
    } else if (this.filterMinDays !== null && (!Number.isInteger(this.filterMinDays) || this.filterMinDays < 1 || this.filterMinDays > MAX_TRIP_DURATION_DAYS)) {
      message = `Số ngày tối thiểu phải từ 1 đến ${MAX_TRIP_DURATION_DAYS}.`;
    } else if (this.filterMaxDays !== null && (!Number.isInteger(this.filterMaxDays) || this.filterMaxDays < 1 || this.filterMaxDays > MAX_TRIP_DURATION_DAYS)) {
      message = `Số ngày tối đa phải từ 1 đến ${MAX_TRIP_DURATION_DAYS}.`;
    } else if (this.filterMinDays !== null && this.filterMaxDays !== null && this.filterMinDays > this.filterMaxDays) {
      message = 'Số ngày tối thiểu không được lớn hơn số ngày tối đa.';
    }
    this.filterError.set(message);
    return message === null;
  }

  get activeFilterCount(): number {
    let count = 0;
    if (this.filterSearch.trim()) count++;
    if (this.filterMaxCost) count++;
    if (this.filterMinDays) count++;
    if (this.filterMaxDays) count++;
    if (this.filterMinRating) count++;
    if (this.filterTravelerType) count++;
    if (this.filterPace) count++;
    if (this.destination.trim()) count++;
    return count;
  }

  // ── User Search helpers ──
  onUserSearchInput(query: string): void {
    const cappedQuery = query.slice(0, 50);
    this.userSearchQuery.set(cappedQuery);
    this.userSearchSubject.next(cappedQuery);
  }

  onUserSearchFocus(event: Event): void {
    event.stopPropagation();
    this.isUserSearchFocused.set(true);
    if (this.userSearchQuery().trim().length > 0) {
      this.userSearchSubject.next(this.userSearchQuery());
    }
  }

  goToUserProfile(username: string): void {
    this.isUserSearchFocused.set(false);
    this.userSearchQuery.set('');
    this.userSearchResults.set([]);
    this.router.navigate(['/community/users', username]);
  }
}
