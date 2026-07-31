declare const L: any;

import { Component, inject, OnInit, signal, DestroyRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, FormsModule, Validators } from '@angular/forms';
import { Router, RouterModule, ActivatedRoute } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { TripService, TripListItem, CreateTripRequest, TripScope } from '../../services/trip.service';
import { PublicTripService } from '../../services/public-trip.service';
import { PlacePhotoService } from '../../services/place-photo.service';
import {
  GENERIC_TRAVEL_FALLBACK_IMAGES,
  getInlineScenicFallback,
  resolveTravelFallbackImage,
  resolveTravelCoverImage,
} from '../../services/travel-cover-images';
import { forkJoin, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CustomSelectComponent } from '../shared/custom-select/custom-select';
import { CustomDatePickerComponent } from '../shared/custom-date-picker/custom-date-picker';
import { PwaService } from '../../services/pwa.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    FormsModule,
    RouterModule,
    CustomSelectComponent,
    CustomDatePickerComponent
  ],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class DashboardComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  private readonly tripService = inject(TripService);
  private readonly publicTripService = inject(PublicTripService);
  private readonly placePhotoService = inject(PlacePhotoService);
  readonly pwaService = inject(PwaService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  // PWA Signals
  readonly isOnline = this.pwaService.isOnline;

  // Dynamic Destination Images Cache
  readonly destinationImagesMap = signal<Map<string, string[]>>(new Map());

  // Leaflet Map properties
  private dashboardMap: any = null;
  private dashboardTileLayer: any = null;
  private mapMarkers: any[] = [];
  readonly mapStyle = signal<'streets' | 'satellite'>('streets');

  // User Info signal link
  readonly currentUser = this.authService.currentUser;

  // State signals
  readonly trips = signal<TripListItem[]>([]);
  readonly isLoading = signal<boolean>(false);
  readonly isSubmitting = signal<boolean>(false);
  readonly errorMessage = signal<string | null>(null);
  readonly filterStatus = signal<string>('all');
  readonly tripScopeFilter = signal<TripScope>('all');
  readonly isModalOpen = signal<boolean>(false);
  readonly modalErrorMessage = signal<string | null>(null);
  readonly submitProgressMessage = signal<string | null>(null);
  readonly submittingMode = signal<'manual' | 'ai' | null>(null);
  readonly overBudgetTrips = signal<TripListItem[]>([]);

  // Delete Modal state signals
  readonly tripToDelete = signal<TripListItem | null>(null);
  readonly isDeleteModalOpen = signal<boolean>(false);
  readonly isDeletingTrip = signal<boolean>(false);
  readonly tripToUnpublish = signal<TripListItem | null>(null);
  readonly isUnpublishModalOpen = signal<boolean>(false);
  readonly isUnpublishing = signal<boolean>(false);
  readonly publicationMessage = signal<string | null>(null);

  // Airbnb Hub State
  readonly activeTab = signal<string>('explore'); // 'my-trips', 'explore', or 'map'
  readonly selectedCategory = signal<string>('all');

  // A local database of coordinates for popular destinations
  readonly destinationCoordinates: { [key: string]: [number, number] } = {
    'phú quốc': [10.2181, 103.9607],
    'phu quoc': [10.2181, 103.9607],
    'đà nẵng': [16.0471, 108.2068],
    'da nang': [16.0471, 108.2068],
    sapa: [22.3364, 103.8438],
    'hà giang': [22.8233, 104.9836],
    'ha giang': [22.8233, 104.9836],
    'hà nội': [21.0285, 105.8542],
    hanoi: [21.0285, 105.8542],
    'hội an': [15.8801, 108.338],
    'hoi an': [15.8801, 108.338],
    'đà lạt': [11.9404, 108.4583],
    'da lat': [11.9404, 108.4583],
    tokyo: [35.6762, 139.6503],
    bali: [-8.4095, 115.1889],
    'hồ chí minh': [10.8231, 106.6297],
    'ho chi minh': [10.8231, 106.6297],
    'nha trang': [12.2388, 109.1967],
    huế: [16.4637, 107.5909],
    hue: [16.4637, 107.5909],
    'sài gòn': [10.8231, 106.6297],
    'sai gon': [10.8231, 106.6297],
    'bình thuận': [10.9333, 108.1],
    'vũng tàu': [10.346, 107.0843],
    'vung tau': [10.346, 107.0843],
    'hạ long': [20.9501, 107.0733],
    'ha long': [20.9501, 107.0733],
  };

  // Search inputs
  readonly searchDest = signal<string>('');
  readonly searchStart = signal<string>('');
  readonly searchEnd = signal<string>('');
  readonly searchGuests = signal<number>(1);

  readonly categories = [
    { id: 'all', name: 'Tất cả', icon: 'grid_view' },
    { id: 'beach', name: 'Biển đảo', icon: 'beach_access' },
    { id: 'mountain', name: 'Vùng núi', icon: 'terrain' },
    { id: 'culture', name: 'Văn hóa', icon: 'museum' },
    { id: 'city', name: 'Thành phố', icon: 'location_city' },
  ];

  getCategoryIcon(category: string): string {
    switch (category) {
      case 'beach': return 'beach_access';
      case 'mountain': return 'terrain';
      case 'culture': return 'museum';
      case 'city': return 'location_city';
      default: return 'explore';
    }
  }

  getCategoryLabel(category: string): string {
    switch (category) {
      case 'beach': return 'Biển đảo';
      case 'mountain': return 'Vùng núi';
      case 'culture': return 'Văn hóa';
      case 'city': return 'Thành phố';
      default: return 'Khám phá';
    }
  }

  readonly trendingDestinations = [
    {
      name: 'Phú Quốc',
      category: 'beach',
      description: 'Thiên đường nghỉ dưỡng với những bãi cát trắng mịn và hải sản tươi ngon.',
      image:
        'https://images.unsplash.com/photo-1589308454676-4259466e3437?q=80&w=600&auto=format&fit=crop',
      budget: 6000000,
      days: 4,
      preferences:
        'Nghỉ dưỡng resort ven biển, đi cáp treo Hòn Thơm, lặn ngắm san hô, thưởng thức hải sản và bún quậy.',
    },
    {
      name: 'Đà Nẵng',
      category: 'beach',
      description: 'Thành phố đáng sống nhất Việt Nam với sự kết hợp hoàn hảo giữa biển và núi.',
      image:
        'https://commons.wikimedia.org/wiki/Special:FilePath/Da%20Nang%20Dragon%20Bridge%202020%20IMG%204019.jpg?width=1200',
      budget: 4500000,
      days: 3,
      preferences:
        'Tắm biển Mỹ Khê, check-in Cầu Vàng Bà Nà Hills, ăn bánh tráng cuốn thịt heo, mì Quảng thơm ngon.',
    },
    {
      name: 'Sapa',
      category: 'mountain',
      description: 'Vẻ đẹp hùng vĩ của những ruộng bậc thang trong sương mù mờ ảo.',
      image:
        'https://images.unsplash.com/photo-1504457047772-27fad174996b?q=80&w=600&auto=format&fit=crop',
      budget: 3500000,
      days: 3,
      preferences:
        'Chinh phục đỉnh Fansipan bằng cáp treo, leo núi Hàm Rồng, ghé thăm bản Cát Cát thanh bình, ăn lẩu cá hồi.',
    },
    {
      name: 'Hà Giang',
      category: 'mountain',
      description: 'Cung đường hạnh phúc đầy thử thách với thiên nhiên hoang sơ.',
      image:
        'https://images.unsplash.com/photo-1627471203492-f04b2816911d?q=80&w=600&auto=format&fit=crop',
      budget: 4000000,
      days: 4,
      preferences:
        'Khám phá đèo Mã Pí Lèng, chèo thuyền ngắm cảnh sông Nho Quế, check-in hoa tam giác mạch.',
    },
    {
      name: 'Hà Nội',
      category: 'culture',
      description: 'Nét cổ kính ngàn năm văn hiến giữa nhịp sống thủ đô hiện đại.',
      image:
        'https://images.unsplash.com/photo-1509030450996-9352e043443f?q=80&w=600&auto=format&fit=crop',
      budget: 3000000,
      days: 3,
      preferences:
        'Dạo quanh Hồ Gươm, viếng lăng Bác, thưởng thức phở gánh cổ truyền, bún chả và cà phê trứng.',
    },
    {
      name: 'Hội An',
      category: 'culture',
      description: 'Thương cảng cổ yên bình với những ánh đèn lồng rực rỡ sắc màu.',
      image:
        'https://images.unsplash.com/photo-1594917409241-d64e9a4f4094?q=80&w=600&auto=format&fit=crop',
      budget: 3500000,
      days: 3,
      preferences:
        'Đi dạo phố cổ về đêm, đi thuyền thả hoa đăng trên sông Hoài, thưởng thức bánh mì Phượng và cơm gà.',
    },
    {
      name: 'Đà Lạt',
      category: 'mountain',
      description: 'Thành phố mộng mơ với không khí se lạnh và những ngọn đồi thông.',
      image:
        'https://images.unsplash.com/photo-1563293816-7f4f6556e89f?q=80&w=600&auto=format&fit=crop',
      budget: 3800000,
      days: 3,
      preferences:
        'Check-in hồ Xuân Hương, săn mây đồi chè Cầu Đất, ăn bánh tráng nướng, uống sữa đậu nành nóng.',
    },
    {
      name: 'Tokyo',
      category: 'city',
      description: 'Trải nghiệm sự giao thoa độc đáo giữa truyền thống và công nghệ tương lai.',
      image:
        'https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?q=80&w=600&auto=format&fit=crop',
      budget: 25000000,
      days: 5,
      preferences:
        'Tham quan ngã tư Shibuya đông đúc, đền Senso-ji cổ kính, tháp Tokyo, ăn sushi băng chuyền và ramen.',
    },
    {
      name: 'Bali',
      category: 'beach',
      description: 'Đảo rồng với những đền đài tâm linh và bãi biển tuyệt đẹp.',
      image:
        'https://images.unsplash.com/photo-1537996194471-e657df975ab4?q=80&w=600&auto=format&fit=crop',
      budget: 15000000,
      days: 5,
      preferences:
        'Tham quan đền Uluwatu bên bờ đá, ruộng bậc thang Tegallalang, chơi đu dây Bali Swing.',
    },
  ];

  readonly provinces = [
    'An Giang', 'Bà Rịa - Vũng Tàu', 'Bắc Giang', 'Bắc Kạn', 'Bạc Liêu', 'Bắc Ninh', 'Bến Tre',
    'Bình Định', 'Bình Dương', 'Bình Phước', 'Bình Thuận', 'Cà Mau', 'Cần Thơ', 'Cao Bằng',
    'Đà Nẵng', 'Đắk Lắk', 'Đắk Nông', 'Điện Biên', 'Đồng Nai', 'Đồng Tháp', 'Gia Lai',
    'Hà Giang', 'Hà Nam', 'Hà Nội', 'Hà Tĩnh', 'Hải Dương', 'Hải Phòng', 'Hậu Giang',
    'Hòa Bình', 'Hồ Chí Minh', 'Hưng Yên', 'Khánh Hòa', 'Kiên Giang', 'Kon Tum', 'Lai Châu',
    'Lâm Đồng', 'Lạng Sơn', 'Lào Cai', 'Long An', 'Nam Định', 'Nghệ An', 'Ninh Bình',
    'Ninh Thuận', 'Phú Thọ', 'Phú Yên', 'Quảng Bình', 'Quảng Nam', 'Quảng Ngãi', 'Quảng Ninh',
    'Quảng Trị', 'Sóc Trăng', 'Sơn La', 'Tây Ninh', 'Thái Bình', 'Thái Nguyên', 'Thanh Hóa',
    'Thừa Thiên Huế', 'Tiền Giang', 'Trà Vinh', 'Tuyên Quang', 'Vĩnh Long', 'Vĩnh Phúc', 'Yên Bái'
  ];

  // Create Trip Reactive Form
  readonly createForm = this.fb.nonNullable.group({
    title: ['', [Validators.required, Validators.maxLength(200)]],
    destination: ['', [Validators.required, Validators.maxLength(200)]],
    start_date: ['', [Validators.required]],
    end_date: ['', [Validators.required]],
    budget: ['' as any],
    num_travelers: [1, [Validators.required, Validators.min(1)]],
    preferences: [''],
  });

  private readonly destroyRef = inject(DestroyRef);

  ngOnInit(): void {
    // Redirect if not authenticated
    if (!this.authService.isAuthenticated()) {
      this.router.navigate(['/login']);
      return;
    }
    this.fetchTrips();

    // Auto-reload trips whenever trip list changes (e.g. invite accepted)
    this.tripService.tripListUpdated$.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
      this.fetchTrips();
    });

    // Prefetch trending destinations immediately
    const trendingNames = this.trendingDestinations.map((d) => d.name);
    this.prefetchDestinationImages(trendingNames);

    // Sync tab with query params
    this.route.queryParams.subscribe((params) => {
      const tab = params['tab'];
      if (tab === 'my-trips' || tab === 'explore' || tab === 'map') {
        if (this.activeTab() !== tab) {
          this.closeModal();
          this.closeDeleteModal();
          this.closeUnpublishModal();
        }
        this.setActiveTab(tab);
      }
    });
  }

  prefetchDestinationImages(destinations: string[]): void {
    const uniqueDests = Array.from(new Set(destinations.map((d) => d.trim()).filter(Boolean)));
    const requests = uniqueDests.map((dest) =>
      this.placePhotoService.getPhotos(dest, 3).pipe(
        map((photos) => ({ dest, photos })),
        catchError(() => of({ dest, photos: [] })),
      ),
    );

    forkJoin(requests).subscribe((results) => {
      this.destinationImagesMap.update((currentMap) => {
        const newMap = new Map(currentMap);
        results.forEach((res) => {
          if (res.photos && res.photos.length > 0) {
            newMap.set(res.dest.toLowerCase().trim(), res.photos);
          }
        });
        return newMap;
      });
    });
  }

  fetchTrips(): void {
    this.isLoading.set(true);
    this.errorMessage.set(null);

    this.tripService.listTrips(undefined, 1, 100, 'all').subscribe({
      next: (res) => {
        this.isLoading.set(false);
        if (res && res.data && res.data.items) {
          const items = res.data.items;
          this.trips.set(items);
          this.checkOverBudgetTrips();

          // Prefetch user trip images
          const tripDests = items.map((t) => t.destination);
          this.prefetchDestinationImages(tripDests);

          if (this.activeTab() === 'map') {
            this.initOrRefreshDashboardMap();
          }
        }
      },
      error: (err) => {
        this.isLoading.set(false);
        if (err.error && err.error.message) {
          this.errorMessage.set(err.error.message);
        } else {
          this.errorMessage.set('Không thể tải danh sách chuyến đi. Vui lòng thử lại sau.');
        }
      },
    });
  }

  checkOverBudgetTrips(): void {
    const activeTrips = this.trips().filter((t) => t.status === 'active');
    if (activeTrips.length === 0) {
      this.overBudgetTrips.set([]);
      return;
    }

    const requests = activeTrips.map((trip) =>
      this.tripService.getBudgetSummary(trip.id).pipe(catchError(() => of(null))),
    );

    forkJoin(requests).subscribe((summaries) => {
      const overspent: TripListItem[] = [];
      summaries.forEach((summary, index) => {
        if (summary && summary.data && summary.data.overspent) {
          overspent.push(activeTrips[index]);
        }
      });
      this.overBudgetTrips.set(overspent);
    });
  }

  getFilteredTrips(): TripListItem[] {
    const currentFilter = this.filterStatus();
    const scopeFilter = this.tripScopeFilter();
    let allTrips = this.trips();

    if (scopeFilter === 'owned') {
      allTrips = allTrips.filter((trip) => trip.access_type === 'owner');
    } else if (scopeFilter === 'shared') {
      allTrips = allTrips.filter((trip) => trip.access_type === 'shared');
    }

    if (currentFilter === 'published') {
      allTrips = allTrips.filter((trip) => trip.publication?.status === 'published');
    } else if (currentFilter !== 'all') {
      allTrips = allTrips.filter((trip) => trip.status === currentFilter);
    }

    const query = this.searchDest().toLowerCase().trim();
    if (query) {
      allTrips = allTrips.filter(
        (trip) =>
          trip.destination.toLowerCase().includes(query) ||
          trip.title.toLowerCase().includes(query),
      );
    }

    return allTrips;
  }

  getFilteredTrending() {
    const cat = this.selectedCategory();
    if (cat === 'all') {
      return this.trendingDestinations;
    }
    return this.trendingDestinations.filter((d) => d.category === cat);
  }

  selectCategory(catId: string): void {
    this.selectedCategory.set(catId);
  }

  getFutureDateString(daysOffset: number): string {
    const d = new Date();
    d.setDate(d.getDate() + daysOffset);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  planTrending(dest: any): void {
    const startDate = this.getFutureDateString(1);
    const endDate = this.getFutureDateString(1 + dest.days);

    const startDateStr = this.formatIsoToDdMmYyyy(startDate);
    const endDateStr = this.formatIsoToDdMmYyyy(endDate);
    this.createForm.reset({
      title: `Khám phá ${dest.name} cùng AI`,
      destination: dest.name,
      start_date: startDateStr,
      end_date: endDateStr,
      budget: this.formatNumberWithDots(dest.budget),
      num_travelers: 2,
      preferences: dest.preferences,
    });

    this.modalErrorMessage.set(null);
    this.isModalOpen.set(true);
  }

  onSearch(): void {
    const dest = this.searchDest().trim();
    if (dest) {
      const startDate = this.searchStart() || this.getFutureDateString(1);
      const endDate = this.searchEnd() || this.getFutureDateString(4);
      const guests = this.searchGuests() || 2;

      const match = this.trendingDestinations.find(
        (t) => t.name.toLowerCase() === dest.toLowerCase(),
      );

      const startDateStr = this.formatIsoToDdMmYyyy(startDate);
      const endDateStr = this.formatIsoToDdMmYyyy(endDate);
      this.createForm.reset({
        title: `Hành trình khám phá ${dest}`,
        destination: dest,
        start_date: startDateStr,
        end_date: endDateStr,
        budget: match ? this.formatNumberWithDots(match.budget) : '',
        num_travelers: guests,
        preferences: match ? match.preferences : '',
      });
      this.modalErrorMessage.set(null);
      this.isModalOpen.set(true);
    } else {
      this.openModal();
    }
  }

  onFilterChange(status: string): void {
    this.filterStatus.set(status);
  }

  onScopeFilterChange(scope: TripScope): void {
    this.tripScopeFilter.set(scope);
  }

  getOwnedTripsCount(): number {
    return this.trips().filter((trip) => trip.access_type === 'owner').length;
  }

  getSharedTripsCount(): number {
    return this.trips().filter((trip) => trip.access_type === 'shared').length;
  }

  getTripsCountByStatus(status: string): number {
    if (status === 'all') {
      return this.trips().length;
    }
    if (status === 'published') {
      return this.trips().filter((trip) => trip.publication?.status === 'published').length;
    }
    return this.trips().filter((trip) => trip.status === status).length;
  }

  getTripAccessLabel(trip: TripListItem): string {
    if (trip.role === 'owner') return 'Chủ chuyến đi';
    return trip.role === 'editor' ? 'Được chia sẻ: Sửa' : 'Được chia sẻ: Xem';
  }

  openModal(): void {
    this.createForm.reset({
      title: '',
      destination: '',
      start_date: '',
      end_date: '',
      budget: '',
      num_travelers: 1,
      preferences: '',
    });
    this.modalErrorMessage.set(null);
    this.isModalOpen.set(true);
  }

  closeModal(): void {
    this.isModalOpen.set(false);
  }

  onSubmitTrip(mode: 'manual' | 'ai' = 'ai'): void {
    if (this.createForm.invalid) {
      this.createForm.markAllAsTouched();
      return;
    }

    const formValue = this.createForm.getRawValue();
    const startIso = this.formatDdMmYyyyToIso(formValue.start_date);
    const endIso = this.formatDdMmYyyyToIso(formValue.end_date);
    const start = new Date(startIso);
    const end = new Date(endIso);
    if (isNaN(start.getTime()) || isNaN(end.getTime())) {
      this.modalErrorMessage.set('Ngày nhập vào không hợp lệ (định dạng dd/mm/yyyy).');
      return;
    }
    if (end < start) {
      this.modalErrorMessage.set('Ngày kết thúc phải lớn hơn hoặc bằng ngày bắt đầu.');
      return;
    }
    this.isSubmitting.set(true);
    this.submittingMode.set(mode);
    this.modalErrorMessage.set(null);
    this.submitProgressMessage.set('Đang tạo chuyến đi...');

    const rawBudget = formValue.budget ? Number(formValue.budget.toString().replace(/\./g, '')) : null;
    const payload: CreateTripRequest = {
      title: formValue.title,
      destination: formValue.destination,
      start_date: startIso,
      end_date: endIso,
      budget: isNaN(rawBudget as any) ? null : rawBudget,
      num_travelers: formValue.num_travelers,
      preferences: formValue.preferences || null,
    };

    this.tripService.createTrip(payload).subscribe({
      next: (res) => {
        const tripId = res?.data?.id;
        if (!tripId) {
          this.isSubmitting.set(false);
          this.submittingMode.set(null);
          this.submitProgressMessage.set(null);
          this.modalErrorMessage.set('Không thể tạo chuyến đi. Vui lòng thử lại.');
          return;
        }

        if (mode === 'ai') {
          // Step 2: Auto-generate grounded AI itinerary
          this.submitProgressMessage.set('Đang tìm địa điểm phù hợp...');
          setTimeout(() => {
            if (this.isSubmitting() && this.submittingMode() === 'ai') {
              this.submitProgressMessage.set('Đang tối ưu tuyến đường và khung giờ...');
            }
          }, 1200);
          setTimeout(() => {
            if (this.isSubmitting() && this.submittingMode() === 'ai') {
              this.submitProgressMessage.set('Đang kiểm tra ngân sách...');
            }
          }, 2400);

          this.tripService.generateDays(tripId, { overwrite: true, ai: true }).subscribe({
            next: () => {
              this.submitProgressMessage.set('Hoàn tất! Đang chuyển hướng...');
              this.isSubmitting.set(false);
              this.submittingMode.set(null);
              this.submitProgressMessage.set(null);
              this.closeModal();
              this.router.navigate(['/trip', tripId]);
            },
            error: (err) => {
              this.isSubmitting.set(false);
              this.submittingMode.set(null);
              this.submitProgressMessage.set(null);
              this.closeModal();
              this.router.navigate(['/trip', tripId]);
            },
          });
        } else {
          // Manual Flow - only initialize empty days
          this.submitProgressMessage.set('Đang tạo các ngày cho chuyến đi...');
          this.tripService.generateDays(tripId, { overwrite: true, ai: false }).subscribe({
            next: () => {
              this.submitProgressMessage.set('Hoàn tất! Đang chuyển hướng...');
              this.isSubmitting.set(false);
              this.submittingMode.set(null);
              this.submitProgressMessage.set(null);
              this.closeModal();
              this.router.navigate(['/trip', tripId]);
            },
            error: (err) => {
              this.isSubmitting.set(false);
              this.submittingMode.set(null);
              this.submitProgressMessage.set(null);
              this.closeModal();
              this.router.navigate(['/trip', tripId]);
            },
          });
        }
      },
      error: (err) => {
        this.isSubmitting.set(false);
        this.submittingMode.set(null);
        this.submitProgressMessage.set(null);
        if (err.error && err.error.message) {
          this.modalErrorMessage.set(err.error.message);
        } else {
          this.modalErrorMessage.set('Không thể tạo chuyến đi. Vui lòng thử lại sau.');
        }
      },
    });
  }

  onLogout(): void {
    this.authService.logout();
    this.router.navigate(['/login']);
  }

  isFieldInvalid(fieldName: string): boolean {
    const field = this.createForm.get(fieldName);
    return !!(field && field.invalid && (field.dirty || field.touched));
  }

  onBudgetInputChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    let value = input.value;
    let raw = value.replace(/\D/g, '');
    if (raw) {
      const num = Number(raw);
      const formatted = num.toLocaleString('en-US');
      input.value = formatted;
      this.createForm.get('budget')?.setValue(formatted, { emitEvent: false });
    } else {
      input.value = '';
      this.createForm.get('budget')?.setValue('', { emitEvent: false });
    }
  }

  formatNumberWithDots(val: number | string | null | undefined): string {
    if (val === null || val === undefined || val === '') return '';
    const clean = val.toString().replace(/\D/g, '');
    if (!clean) return '';
    return Number(clean).toLocaleString('en-US');
  }

  openDatePicker(input: HTMLInputElement): void {
    try {
      input.showPicker();
    } catch (e) {
      input.focus();
    }
  }

  getTripDurationDays(): number | null {
    const startVal = this.createForm.get('start_date')?.value;
    const endVal = this.createForm.get('end_date')?.value;
    if (startVal && endVal) {
      const startIso = this.formatDdMmYyyyToIso(startVal);
      const endIso = this.formatDdMmYyyyToIso(endVal);
      const start = new Date(startIso);
      const end = new Date(endIso);
      if (!isNaN(start.getTime()) && !isNaN(end.getTime()) && end >= start) {
        const diffTime = Math.abs(end.getTime() - start.getTime());
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;
        return diffDays;
      }
    }
    return null;
  }

  onDateInputChange(event: Event, controlName: string): void {
    const input = event.target as HTMLInputElement;
    let value = input.value.replace(/\D/g, '');
    if (value.length > 2) {
      value = value.slice(0, 2) + '/' + value.slice(2);
    }
    if (value.length > 4) {
      value = value.slice(0, 5) + '/' + value.slice(5);
    }
    value = value.slice(0, 10);
    input.value = value;
    this.createForm.get(controlName)?.setValue(value, { emitEvent: false });
  }

  onNativeDateChange(event: Event, controlName: string): void {
    const picker = event.target as HTMLInputElement;
    const value = picker.value;
    if (value) {
      const formatted = this.formatIsoToDdMmYyyy(value);
      this.createForm.get(controlName)?.setValue(formatted);
    }
  }

  formatIsoToDdMmYyyy(iso: string | null | undefined): string {
    if (!iso) return '';
    const parts = iso.split('-');
    if (parts.length === 3) {
      return `${parts[2]}/${parts[1]}/${parts[0]}`;
    }
    return iso;
  }

  formatDdMmYyyyToIso(dateStr: string | null | undefined): string {
    if (!dateStr) return '';
    const parts = dateStr.split('/');
    if (parts.length === 3) {
      return `${parts[2]}-${parts[1]}-${parts[0]}`;
    }
    return dateStr;
  }

  getTripImage(
    destination: string | undefined,
    tripId?: string,
    coverImageUrl?: string | null,
  ): string {
    const dest = destination?.toLowerCase().trim() || '';
    const list = dest ? this.destinationImagesMap().get(dest) || [] : [];
    return resolveTravelCoverImage(destination, tripId || destination, list, coverImageUrl);
  }

  get svgFallback(): string {
    const isLight = document.documentElement.classList.contains('light');
    return getInlineScenicFallback(isLight);
  }

  handleImgError(event: any): void {
    const img = event.target as HTMLImageElement;
    const attempts = Number(img.dataset['fallbackAttempts'] || '0');

    if (attempts < GENERIC_TRAVEL_FALLBACK_IMAGES.length) {
      img.dataset['fallbackAttempts'] = String(attempts + 1);
      img.src = resolveTravelFallbackImage(
        img.dataset['fallbackSeed'] || img.alt || img.src,
        attempts,
      );
      return;
    }

    img.onerror = null;
    img.src = this.svgFallback;
  }

  // Format currency for budgets helper
  formatCurrency(value: number | null): string {
    if (value === null || value === undefined) return 'N/A';
    return `${new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(value)} VND`;
  }

  goToTrip(tripId: string): void {
    this.router.navigate(['/trip', tripId]);
  }

  getTrendingCountry(name: string): string {
    const n = name.toLowerCase();
    if (n.includes('tokyo') || n.includes('japan') || n.includes('nhật')) return 'Nhật Bản';
    if (n.includes('bali') || n.includes('indonesia')) return 'Indonesia';
    return 'Việt Nam';
  }

  getUniqueDestinationsCount(): number {
    return new Set(this.trips().map((t) => t.destination.trim().toLowerCase())).size;
  }

  getUniqueDestinationsList(): string {
    const list = this.trips();
    if (list.length === 0) return 'Chưa có điểm đến';
    const dests = Array.from(new Set(list.map((t) => t.destination.trim())));
    if (dests.length <= 3) {
      return dests.join(', ');
    }
    return `${dests.slice(0, 3).join(', ')}, +${dests.length - 3}`;
  }

  getMapStats() {
    const list = this.getFilteredTrips();
    let totalBudget = 0;
    const destCounts: { [key: string]: number } = {};
    let isInternational = false;

    list.forEach((trip) => {
      if (trip.budget) {
        totalBudget += trip.budget;
      }
      const dest = trip.destination.trim();
      destCounts[dest] = (destCounts[dest] || 0) + 1;

      const destLower = dest.toLowerCase();
      if (
        destLower.includes('tokyo') ||
        destLower.includes('bali') ||
        destLower.includes('japan') ||
        destLower.includes('indonesia') ||
        destLower.includes('pháp') ||
        destLower.includes('paris') ||
        destLower.includes('london') ||
        destLower.includes('anh')
      ) {
        isInternational = true;
      }
    });

    // Favorite destination
    let favDest = 'Chưa có';
    let maxCount = 0;
    for (const d in destCounts) {
      if (destCounts[d] > maxCount) {
        maxCount = destCounts[d];
        favDest = d;
      }
    }

    // Active Region
    let region = 'Chưa có';
    if (list.length > 0) {
      region = isInternational ? 'Đông Nam Á & Quốc tế' : 'Việt Nam';
    }

    return {
      totalBudget: this.formatCurrency(totalBudget),
      favoriteDestination: favDest,
      activeRegion: region,
    };
  }

  // --- Map Integration Helpers ---

  getCoordinatesForDestination(destination: string): [number, number] {
    const dest = destination.toLowerCase().trim();
    if (this.destinationCoordinates[dest]) {
      return this.destinationCoordinates[dest];
    }
    for (const key in this.destinationCoordinates) {
      if (dest.includes(key) || key.includes(dest)) {
        return this.destinationCoordinates[key];
      }
    }
    // Fallback to center of Vietnam with a slight random offset
    const lat = 16.0471 + (Math.random() - 0.5) * 4.0;
    const lng = 108.2068 + (Math.random() - 0.5) * 4.0;
    return [lat, lng];
  }

  setActiveTab(tab: string): void {
    if (this.activeTab() !== tab) {
      this.closeModal();
      this.closeDeleteModal();
      this.closeUnpublishModal();
    }
    this.activeTab.set(tab);
    if (tab === 'map') {
      setTimeout(() => {
        this.initOrRefreshDashboardMap();
      }, 100);
    }
  }

  initOrRefreshDashboardMap(retryCount = 0): void {
    if (this.activeTab() !== 'map') return;

    const container = document.getElementById('dashboard-map');
    if (!container) {
      if (retryCount < 10) {
        setTimeout(() => this.initOrRefreshDashboardMap(retryCount + 1), 100);
      }
      return;
    }

    if (this.dashboardMap) {
      try {
        this.dashboardMap.remove();
      } catch (e) {
        console.warn('Error removing old map:', e);
      }
      this.dashboardMap = null;
    }

    const centerCoords: [number, number] = [16.0471, 108.2068]; // Center of Vietnam (Da Nang)
    this.dashboardMap = L.map('dashboard-map', { zoomControl: false }).setView(centerCoords, 6);

    // Google Maps tile layer
    this.dashboardTileLayer = L.tileLayer('https://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', {
      maxZoom: 20,
      subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
      attribution: '&copy; Google Maps',
    }).addTo(this.dashboardMap);

    // Add Zoom Control to Bottom Right
    L.control.zoom({ position: 'bottomright' }).addTo(this.dashboardMap);

    setTimeout(() => {
      if (this.dashboardMap) {
        this.dashboardMap.invalidateSize();
        this.renderDashboardMapMarkers();
      }
    }, 250);
  }

  toggleDashboardMapStyle(): void {
    if (!this.dashboardMap) return;
    if (this.dashboardTileLayer) {
      this.dashboardMap.removeLayer(this.dashboardTileLayer);
    }
    const nextStyle = this.mapStyle() === 'streets' ? 'satellite' : 'streets';
    this.mapStyle.set(nextStyle);
    const layerCode = nextStyle === 'satellite' ? 's' : 'm';
    this.dashboardTileLayer = L.tileLayer(
      `https://{s}.google.com/vt/lyrs=${layerCode}&x={x}&y={y}&z={z}`,
      { maxZoom: 20, subdomains: ['mt0', 'mt1', 'mt2', 'mt3'], attribution: '&copy; Google Maps' },
    ).addTo(this.dashboardMap);
  }

  renderDashboardMapMarkers(): void {
    if (!this.dashboardMap) return;

    // Clear old markers
    this.mapMarkers.forEach((m) => m.remove());
    this.mapMarkers = [];

    const trips = this.getFilteredTrips();
    const validCoords: any[] = [];

    trips.forEach((trip) => {
      const coords = this.getCoordinatesForDestination(trip.destination);
      validCoords.push(coords);

      const statusIcon = trip.status === 'draft' ? 'edit_note' : trip.status === 'active' ? 'flight_takeoff' : 'emoji_events';

      const customIcon = L.divIcon({
        className: 'custom-div-icon',
        html: `<div class="custom-emoji-marker w-10 h-10"><span class="material-symbols-outlined text-primary" style="font-size: 20px;">${statusIcon}</span></div>`,
        iconSize: [40, 40],
        iconAnchor: [20, 20],
        popupAnchor: [0, -20],
      });

      const marker = L.marker(coords, { icon: customIcon }).addTo(this.dashboardMap);
      this.mapMarkers.push(marker);

      const formattedBudget = this.formatCurrency(trip.budget);

      const popupContent = document.createElement('div');
      popupContent.className = 'flex flex-col';

      const popupBody = document.createElement('div');
      popupBody.className = 'p-3 space-y-2';
      const popupTitle = document.createElement('h4');
      popupTitle.className =
        'font-bold text-on-surface leading-tight text-sm text-ellipsis overflow-hidden white-space-nowrap m-0';
      popupTitle.textContent = trip.title;

      const popupMeta = document.createElement('div');
      popupMeta.className = 'space-y-1';
      const makeMetaRow = (icon: string, value: string): HTMLDivElement => {
        const row = document.createElement('div');
        row.className = 'flex items-center gap-1.5 text-xs text-on-surface-variant';
        const iconElement = document.createElement('span');
        iconElement.className = 'material-symbols-outlined text-[14px]';
        iconElement.textContent = icon;
        const valueElement = document.createElement('span');
        valueElement.textContent = value;
        row.append(iconElement, valueElement);
        return row;
      };
      popupMeta.append(
        makeMetaRow('location_on', trip.destination),
        makeMetaRow('calendar_today', new Date(trip.start_date).toLocaleDateString('vi-VN')),
      );

      const popupFooter = document.createElement('div');
      popupFooter.className = 'flex justify-between items-center pt-2 gap-2';
      const budgetLabel = document.createElement('span');
      budgetLabel.className =
        'bg-status-rose/10 text-status-rose px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider';
      budgetLabel.textContent = formattedBudget;
      const goBtn = document.createElement('button');
      goBtn.type = 'button';
      goBtn.className =
        'popup-btn-go text-primary text-xs font-semibold hover:underline bg-transparent border-none p-0 cursor-pointer';
      goBtn.textContent = 'Xem chi tiết';
      goBtn.addEventListener('click', () => this.goToTrip(trip.id));

      popupFooter.append(budgetLabel, goBtn);
      popupBody.append(popupTitle, popupMeta, popupFooter);
      popupContent.append(popupBody);

      marker.bindPopup(popupContent);
    });

    if (validCoords.length > 0) {
      this.dashboardMap.fitBounds(validCoords, { padding: [50, 50], maxZoom: 10 });
    }
  }

  confirmDeleteTrip(trip: TripListItem, event: Event): void {
    event.stopPropagation();
    this.tripToDelete.set(trip);
    this.isDeleteModalOpen.set(true);
  }

  closeDeleteModal(): void {
    this.isDeleteModalOpen.set(false);
    this.tripToDelete.set(null);
  }

  performDeleteTrip(): void {
    const trip = this.tripToDelete();
    if (!trip) return;

    this.isDeletingTrip.set(true);
    this.tripService.deleteTrip(trip.id).subscribe({
      next: () => {
        this.isDeletingTrip.set(false);
        this.closeDeleteModal();
        this.trips.update((list) => list.filter((t) => t.id !== trip.id));
        this.overBudgetTrips.update((list) => list.filter((t) => t.id !== trip.id));
      },
      error: (err) => {
        this.isDeletingTrip.set(false);
        alert('Không thể xóa chuyến đi: ' + (err?.error?.detail || err.message));
      },
    });
  }

  viewPublicTrip(trip: TripListItem, event: Event): void {
    event.stopPropagation();
    if (trip.publication?.slug) {
      this.router.navigate(['/community/trips', trip.publication.slug]);
    }
  }

  confirmUnpublishTrip(trip: TripListItem, event: Event): void {
    event.stopPropagation();
    this.publicationMessage.set(null);
    this.tripToUnpublish.set(trip);
    this.isUnpublishModalOpen.set(true);
  }

  closeUnpublishModal(): void {
    if (this.isUnpublishing()) return;
    this.isUnpublishModalOpen.set(false);
    this.tripToUnpublish.set(null);
  }

  performUnpublishTrip(): void {
    const trip = this.tripToUnpublish();
    if (!trip?.publication) return;
    this.isUnpublishing.set(true);
    this.publicTripService.archive(trip.id).subscribe({
      next: () => {
        this.isUnpublishing.set(false);
        this.isUnpublishModalOpen.set(false);
        this.tripToUnpublish.set(null);
        this.trips.update((items) => items.map((item) =>
          item.id === trip.id ? { ...item, publication: null } : item
        ));
        this.publicationMessage.set(`Đã gỡ “${trip.title}” khỏi Cộng đồng. Chuyến đi gốc vẫn được giữ nguyên.`);
      },
      error: (error) => {
        this.isUnpublishing.set(false);
        this.publicationMessage.set(error?.error?.message || 'Không thể gỡ lịch trình khỏi Cộng đồng.');
      },
    });
  }
}
