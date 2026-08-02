import * as L from 'leaflet';
import * as XLSX from '../../utils/xlsx-export-adapter';
import { Component, HostListener, inject, OnDestroy, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormsModule, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { AiStreamService } from '../../services/ai-stream.service';
import {
  TripService,
  TripResponse,
  DayPlanResponse,
  ActivityResponse,
  ChatHistoryItem,
  AiSuggestionResponse,
  ActivityType,
  CreateActivityRequest,
  UpdateActivityRequest,
  BudgetSummaryResponse,
  BudgetItemResponse,
  BudgetCategory,
  LocationResponse,
  LocationCategory,
  ItineraryGenerationSummary,
  GenerateDaysRequest,
  TripParticipant,
  TripInvite,
  TripShareRole,
  TripHistoryEvent,
  ItineraryQualityResponse,
} from '../../services/trip.service';

import { PlacePhotoService, BestRatedPlace } from '../../services/place-photo.service';
import {
  GENERIC_TRAVEL_FALLBACK_IMAGES,
  getInlineScenicFallback,
  resolveTravelCoverImage,
} from '../../services/travel-cover-images';
import { firstValueFrom, of } from 'rxjs';
import { catchError, timeout } from 'rxjs/operators';
import { OsrmService } from '../../services/osrm.service';
import { WeatherService, WeatherForecastResult, DailyWeather } from '../../services/weather.service';
import { PwaService } from '../../services/pwa.service';
import { CustomSelectComponent } from '../shared/custom-select/custom-select';
import { CustomDatePickerComponent } from '../shared/custom-date-picker/custom-date-picker';
import {
  AuthorVerdict,
  PublicActivityReview,
  PublicTripService,
  PublishTripRequest,
} from '../../services/public-trip.service';
import { EmergencyOption, JournalEntry, P1Service } from '../../services/p1.service';
import { MAX_BUDGET_VND } from '../../config/trip-policy';
import { apiErrorMessage, apiValidationIssues } from '../../utils/form-errors';

export interface RouteSegment {
  fromName: string;
  fromType: ActivityType | null;
  toName: string;
  toType: ActivityType | null;
  distanceKm: number;
  durationMin: number;
  coords: [number, number][];
}

@Component({
  selector: 'app-trip-detail',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    FormsModule,
    RouterModule,
    CustomSelectComponent,
    CustomDatePickerComponent
  ],
  templateUrl: './trip-detail.html',
  styleUrl: './trip-detail.css',
})
export class TripDetailComponent implements OnInit, OnDestroy {
  private readonly fb = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  private readonly tripService = inject(TripService);
  private readonly placePhotoService = inject(PlacePhotoService);
  private readonly aiStreamService = inject(AiStreamService);
  private readonly weatherService = inject(WeatherService);
  readonly pwaService = inject(PwaService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly osrmService = inject(OsrmService);
  private readonly publicTripService = inject(PublicTripService);
  private readonly p1Service = inject(P1Service);

  // Weather State Signals
  readonly weatherForecast = signal<WeatherForecastResult | null>(null);
  readonly isLoadingWeather = signal<boolean>(false);

  // Dynamic Destination Images Cache
  readonly destinationImagesMap = signal<Map<string, string[]>>(new Map());
  readonly defaultPlaceholderUrl = resolveTravelCoverImage('travel', 'place-placeholder');

  // A local database of coordinates for popular destinations
  readonly destinationCoordinates: { [key: string]: [number, number] } = {
    'quan lạn': [20.8752, 107.4925],
    'quan lan': [20.8752, 107.4925],
    'quảng ninh': [20.9500, 107.0833],
    'quang ninh': [20.9500, 107.0833],
    'vân đồn': [21.0815, 107.4619],
    'van don': [21.0815, 107.4619],
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
  };

  getCoordinatesForDestination(destination: string | undefined): [number, number] {
    if (!destination) return [20.8752, 107.4925];
    const cleanDest = destination.toLowerCase().replace(/[\(\)]/g, ' ').trim();
    if (this.destinationCoordinates[cleanDest]) {
      return this.destinationCoordinates[cleanDest];
    }
    for (const key in this.destinationCoordinates) {
      if (cleanDest.includes(key) || key.includes(cleanDest)) {
        return this.destinationCoordinates[key];
      }
    }
    const parts = cleanDest.split(/[,]/).map(p => p.trim()).filter(Boolean);
    for (const part of parts) {
      for (const key in this.destinationCoordinates) {
        if (part.includes(key) || key.includes(part)) {
          return this.destinationCoordinates[key];
        }
      }
    }
    return [20.8752, 107.4925];
  }

  // Leaflet Map instance & active markers
  private exploreMap: any = null;
  private mapMarkers: any[] = [];

  // Route mapping fields & signals
  private routeMap: any = null;
  private routeMarkers: any[] = [];
  private routePolylines: any[] = [];
  readonly routeDayIndex = signal<number>(0);
  readonly isLoadingRoute = signal<boolean>(false);
  readonly routeSegments = signal<RouteSegment[]>([]);
  readonly routeTotalDistance = signal<number>(0);
  readonly routeTotalDuration = signal<number>(0);

  // User Info signal link
  readonly currentUser = this.authService.currentUser;

  // Active Trip ID
  tripId = '';

  // State Signals
  readonly trip = signal<TripResponse | null>(null);
  readonly days = signal<DayPlanResponse[]>([]);
  readonly chatHistory = signal<ChatHistoryItem[]>([]);
  readonly activeSuggestions = signal<AiSuggestionResponse[]>([]);
  
  // Loading & Error States
  readonly isLoadingDetail = signal<boolean>(true);
  readonly isLoadingDays = signal<boolean>(true);
  readonly isGenerating = signal<boolean>(false);
  readonly isGenerateOptionsOpen = signal<boolean>(false);
  readonly generationProgressMessage = signal<string | null>(null);
  readonly generationSummary = signal<ItineraryGenerationSummary | null>(null);
  readonly generationOptionsError = signal<string | null>(null);
  readonly errorMsg = signal<string | null>(null);
  readonly itineraryQuality = signal<ItineraryQualityResponse | null>(null);
  readonly isCheckingQuality = signal<boolean>(false);
  readonly updatingLockId = signal<string | null>(null);
  readonly journalEntries = signal<JournalEntry[]>([]);
  readonly journalMessage = signal<string | null>(null);
  readonly emergencyOptions = signal<EmergencyOption[]>([]);
  readonly isLoadingEmergency = signal(false);

  // Chat Form/State
  readonly chatInput = signal<string>('');
  readonly isSendingMessage = signal<boolean>(false);
  readonly isChatOpen = signal<boolean>(typeof window !== 'undefined' ? window.innerWidth >= 1024 : false);
  readonly activeRightTab = signal<'chat' | 'history'>('chat');

  // Sub-tabs switcher state
  readonly activeSubTab = signal<'itinerary' | 'route' | 'budget' | 'explore' | 'settings'>('itinerary');

  // Custom Select Option Item Lists
  readonly paceSelectOptions = [
    { label: 'Thư giãn', value: 'relaxed' },
    { label: 'Cân bằng', value: 'balanced' },
    { label: 'Dày đặc', value: 'packed' }
  ];

  readonly budgetModeSelectOptions = [
    { label: 'Tiết kiệm nghiêm ngặt', value: 'strict' },
    { label: 'Linh hoạt 15%', value: 'flexible_15' },
    { label: 'Thoải mái', value: 'comfort' }
  ];

  readonly transportModeSelectOptions = [
    { label: 'Kết hợp linh hoạt', value: 'mixed' },
    { label: 'Taxi / Grab', value: 'taxi' },
    { label: 'Xe máy', value: 'motorbike' },
    { label: 'Ô tô', value: 'car' },
    { label: 'Đi bộ', value: 'walking' },
    { label: 'Công cộng', value: 'public_transport' }
  ];

  readonly userPlacePrioritySelectOptions = [
    { label: 'Cân bằng với tuyến đường', value: 'balanced' },
    { label: 'Ưu tiên cao', value: 'high' }
  ];

  readonly activityTypeSelectOptions = [
    { label: 'Tham quan / Giải trí', value: 'attraction' },
    { label: 'Ăn uống / Ẩm thực', value: 'meal' },
    { label: 'Khách sạn / Lưu trú', value: 'hotel' },
    { label: 'Di chuyển / Vé tàu xe', value: 'transport' },
    { label: 'Hạng mục khác', value: 'other' }
  ];

  readonly budgetCategorySelectOptions = [
    { label: 'Phòng lưu trú / Khách sạn', value: 'hotel' },
    { label: 'Ăn uống / Nhà hàng', value: 'food' },
    { label: 'Phương tiện di chuyển', value: 'transport' },
    { label: 'Vé vui chơi / Tham quan', value: 'activity' },
    { label: 'Chi phí khác', value: 'other' }
  ];

  readonly memberRoleSelectOptions = [
    { label: 'Xem', value: 'viewer' },
    { label: 'Sửa', value: 'editor' }
  ];

  readonly ratingSelectOptions = [
    { label: '5/5', value: 5 },
    { label: '4/5', value: 4 },
    { label: '3/5', value: 3 },
    { label: '2/5', value: 2 },
    { label: '1/5', value: 1 }
  ];

  readonly starRatingSelectOptions = [
    { label: '★ 5/5', value: 5 },
    { label: '★ 4/5', value: 4 },
    { label: '★ 3/5', value: 3 },
    { label: '★ 2/5', value: 2 },
    { label: '★ 1/5', value: 1 }
  ];

  // Settings State Signals
  readonly isSavingSettings = signal<boolean>(false);
  readonly isDeleteModalOpen = signal<boolean>(false);
  readonly isDeleting = signal<boolean>(false);
  readonly settingsSuccessMsg = signal<string | null>(null);
  readonly settingsErrorMsg = signal<string | null>(null);
  readonly settingsSaveState = signal<'idle' | 'pending' | 'saving' | 'saved' | 'error'>('idle');
  private settingsInitialized = false;
  private settingsAutosaveTimer: ReturnType<typeof setTimeout> | null = null;
  readonly shareParticipants = signal<TripParticipant[]>([]);
  readonly shareInvites = signal<TripInvite[]>([]);
  readonly shareSuccessMsg = signal<string | null>(null);
  readonly shareErrorMsg = signal<string | null>(null);
  readonly isLoadingShares = signal<boolean>(false);
  readonly isSubmittingShare = signal<boolean>(false);
  readonly latestInviteUrl = signal<string | null>(null);
  readonly isPublishWizardOpen = signal(false);
  readonly isPublishingPublicTrip = signal(false);
  readonly publishError = signal<string | null>(null);
  readonly publicationFieldErrors = signal<Record<string, string>>({});
  readonly publishedPublicSlug = signal<string | null>(null);
  readonly existingPublicSlug = signal<string | null>(null);
  publicationReviews: Record<string, PublicActivityReview> = {};
  publicationDraft = {
    title: '',
    summary: '',
    actual_total_cost: '',
    itinerary_rating: 5,
    cost_rating: 5,
    place_rating: 5,
    best_places: '',
    best_foods: '',
    general_tips: '',
    visibility: 'public' as 'public' | 'unlisted',
    show_author_name: true,
    show_cost: true,
    allow_clone: true,
    allow_partial_import: true,
    author_confirmed: false,
  };

  // Trip history drawer state
  readonly isHistoryOpen = signal<boolean>(false);
  readonly historyItems = signal<TripHistoryEvent[]>([]);
  readonly isLoadingHistory = signal<boolean>(false);
  readonly historyErrorMsg = signal<string | null>(null);
  readonly historyPage = signal<number>(1);
  readonly historyTotal = signal<number>(0);
  readonly historyLimit = 30;
  readonly highlightedActivityId = signal<string | null>(null);

  // Explore Tab State Signals
  readonly exploreLocations = signal<LocationResponse[]>([]);
  readonly exploreQuery = signal<string>('');
  readonly activeExploreCategory = signal<'attraction' | 'meal' | 'hotel' | 'cafe'>('attraction');
  readonly isLoadingExplore = signal<boolean>(false);
  readonly exploreError = signal<string | null>(null);
  readonly exploreTotal = signal<number>(0);
  readonly explorePage = signal<number>(1);
  readonly exploreHasMore = signal<boolean>(false);
  readonly exploreIsSearchResult = signal<boolean>(false);
  readonly bestRatedPlaces = signal<BestRatedPlace[]>([]);
  readonly isLoadingBestRated = signal<boolean>(false);

  // Day Selector from Explore State Signals
  readonly isAddActivityFromExploreOpen = signal<boolean>(false);
  readonly selectedExploreLocation = signal<LocationResponse | null>(null);
  readonly selectedExploreDayId = signal<string>('');
  readonly exploreStartTime = signal<string>('');
  readonly exploreEndTime = signal<string>('');
  readonly isSubmittingExploreActivity = signal<boolean>(false);

  // Budget Tracker State Signals
  readonly budgetSummary = signal<BudgetSummaryResponse | null>(null);
  readonly budgetItems = signal<BudgetItemResponse[]>([]);
  readonly isLoadingBudget = signal<boolean>(false);
  readonly isBudgetModalOpen = signal<boolean>(false);
  readonly selectedBudgetItem = signal<BudgetItemResponse | null>(null);
  readonly isSubmittingBudget = signal<boolean>(false);
  readonly budgetError = signal<string | null>(null);
  readonly groupSplitSummary = signal<any>(null);
  readonly tripMemberNames = computed(() => {
    const splitMembers = this.groupSplitSummary()?.members;
    if (splitMembers && Array.isArray(splitMembers) && splitMembers.length > 0) {
      return splitMembers as string[];
    }
    const names: string[] = [];
    const ownerName = this.currentUser()?.full_name || 'Chủ chuyến đi';
    names.push(ownerName);

    const participants = this.shareParticipants();
    if (participants && participants.length > 0) {
      for (const p of participants) {
        const pName = p.user?.full_name || (p.user?.email ? p.user.email.split('@')[0] : null) || p.user?.username;
        if (pName && !names.includes(pName)) {
          names.push(pName);
        }
      }
    }

    const numTravelers = this.trip()?.num_travelers || 1;
    let idx = 1;
    while (names.length < numTravelers) {
      idx++;
      const placeholder = `Thành viên ${idx}`;
      if (!names.includes(placeholder)) {
        names.push(placeholder);
      }
    }
    return names;
  });

  // Activity Modal State
  readonly isActivityModalOpen = signal<boolean>(false);
  readonly selectedDayId = signal<string | null>(null);
  readonly selectedActivityId = signal<string | null>(null);
  readonly selectedActivity = signal<ActivityResponse | null>(null);
  readonly isSubmittingActivity = signal<boolean>(false);
  readonly activityError = signal<string | null>(null);

  // Selected Active Day in Itinerary View (defaults to day 1 index)
  readonly activeDayIndex = signal<number>(0);

  // Form for Manual Activity Adding
  readonly activityForm = this.fb.nonNullable.group({
    title: ['', [Validators.required, Validators.maxLength(200)]],
    description: [''],
    type: ['other' as ActivityType, [Validators.required]],
    start_time: ['', [Validators.pattern(/^([01]\d|2[0-3]):[0-5]\d$/)]],
    end_time: ['', [Validators.pattern(/^([01]\d|2[0-3]):[0-5]\d$/)]],
    estimated_cost: [null as number | null, [Validators.min(0)]],
    notes: [''],
  });

  readonly generateOptionsForm = this.fb.nonNullable.group({
    pace: ['balanced' as 'relaxed' | 'balanced' | 'packed', [Validators.required]],
    budget_mode: ['flexible_15' as 'strict' | 'flexible_15' | 'comfort', [Validators.required]],
    prioritize_user_places: ['balanced' as 'balanced' | 'high', [Validators.required]],
    transport_mode: ['mixed' as 'walking' | 'motorbike' | 'car' | 'taxi' | 'public_transport' | 'mixed', [Validators.required]],
    departure_location: [''],
    departure_time: ['18:00', [Validators.pattern(/^([01]\d|2[0-3]):[0-5]\d$/)]],
    estimated_travel_hours: [6 as number | null, [Validators.min(0)]],
    arrival_transport: ['xe khách'],
    daily_start_time: ['08:30', [Validators.pattern(/^([01]\d|2[0-3]):[0-5]\d$/)]],
    daily_end_time: ['21:30', [Validators.pattern(/^([01]\d|2[0-3]):[0-5]\d$/)]],
    must_visit_text: [''],
    avoid_places_text: [''],
    interest_foodie: [true],
    interest_culture: [true],
    interest_nature: [false],
    interest_cafe: [false],
    interest_beaches: [false],
    interest_adventure: [false],
    dietary_notes: [''],
    mobility_notes: [''],
  });

  // Form for Budget Item Adding / Editing
  readonly budgetForm = this.fb.nonNullable.group({
    category: ['other' as BudgetCategory, [Validators.required]],
    label: ['', [Validators.required, Validators.maxLength(200)]],
    planned_amount: [0, [Validators.required, Validators.min(0)]],
    actual_amount: [0, [Validators.required, Validators.min(0)]],
    date: [''],
    paid_by: [''],
  });

  readonly copiedSettlement = signal<boolean>(false);

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

  // Form for Trip Settings
  readonly settingsForm = this.fb.nonNullable.group({
    title: ['', [Validators.required, Validators.maxLength(200)]],
    destination: ['', [Validators.required, Validators.maxLength(200)]],
    start_date: ['', [Validators.required]],
    end_date: ['', [Validators.required]],
    budget: ['' as any],
    num_travelers: [1, [Validators.required, Validators.min(1)]],
    status: ['draft' as 'draft' | 'active' | 'completed', [Validators.required]],
  });

  readonly shareForm = this.fb.nonNullable.group({
    recipient: [''],
    role: ['viewer' as TripShareRole, [Validators.required]],
    expires_in_days: [7, [Validators.required, Validators.min(1), Validators.max(30)]],
  });

  ngOnInit(): void {
    if (!this.authService.isAuthenticated()) {
      this.router.navigate(['/login']);
      return;
    }

    if (typeof window !== 'undefined' && window.innerWidth < 1024) {
      this.isChatOpen.set(false);
    }

    this.tripId = this.route.snapshot.paramMap.get('id') || '';
    if (!this.tripId) {
      this.router.navigate(['/dashboard']);
      return;
    }

    this.loadTripData();
    this.loadJournal();
    this.settingsForm.valueChanges.subscribe(() => {
      if (!this.settingsInitialized || !this.canManageShares()) return;
      this.settingsSaveState.set('pending');
      if (this.settingsAutosaveTimer) clearTimeout(this.settingsAutosaveTimer);
      this.settingsAutosaveTimer = setTimeout(() => this.onSaveSettings(true), 1200);
    });
  }

  loadJournal(): void {
    this.p1Service.listJournal(this.tripId).subscribe({ next: response => this.journalEntries.set(response.data || []) });
  }

  hasCheckedIn(activityId: string): boolean {
    return this.journalEntries().some(item => item.activity_id === activityId && item.is_check_in);
  }

  quickCheckIn(activity: ActivityResponse, event: Event): void {
    event.stopPropagation();
    if (!this.canEditTrip() || this.hasCheckedIn(activity.id)) return;
    const payload = { activity_id: activity.id, entry_date: new Date().toISOString().slice(0, 10), note: `Check-in tại ${activity.title}`, photo_urls: [], actual_cost: null, rating: null, is_check_in: true };
    if (!this.pwaService.isOnline()) {
      this.pwaService.enqueueOfflineAction('check_in', this.tripId, payload);
      this.journalMessage.set('Đã lưu check-in ngoại tuyến. Hệ thống sẽ đồng bộ khi có mạng.');
      return;
    }
    this.p1Service.createJournal(this.tripId, payload).subscribe({
      next: response => { this.journalEntries.update(items => [response.data, ...items]); this.journalMessage.set('Đã check-in hoạt động.'); },
      error: err => this.journalMessage.set(err?.error?.message || 'Không thể check-in.'),
    });
  }

  previewEmergency(reason: 'rain' | 'closed' | 'late' | 'skip'): void {
    this.isLoadingEmergency.set(true);
    this.p1Service.emergencyPreview(this.tripId, reason).subscribe({
      next: response => { this.isLoadingEmergency.set(false); this.emergencyOptions.set(response.data || []); },
      error: () => { this.isLoadingEmergency.set(false); this.journalMessage.set('Không thể tạo phương án khẩn cấp.'); },
    });
  }

  ngOnDestroy(): void {
    if (this.settingsAutosaveTimer) clearTimeout(this.settingsAutosaveTimer);
  }

  @HostListener('window:beforeunload', ['$event'])
  warnAboutUnsavedChanges(event: BeforeUnloadEvent): void {
    if (this.settingsSaveState() === 'pending' || this.settingsSaveState() === 'saving' || this.activityForm.dirty) {
      event.preventDefault();
      event.returnValue = '';
    }
  }

  @HostListener('window:online')
  async syncPendingOfflineActions(): Promise<void> {
    await this.pwaService.syncOfflineQueue(async action => {
      if ((action.type === 'journal' || action.type === 'check_in') && action.tripId === this.tripId) {
        await firstValueFrom(this.p1Service.createJournal(action.tripId, action.payload));
        return;
      }
      throw new Error('Unsupported offline action');
    });
    this.loadJournal();
    if (this.pwaService.pendingSyncCount() === 0) this.journalMessage.set('Đã đồng bộ dữ liệu ngoại tuyến.');
  }

  loadTripData(): void {
    this.isLoadingDetail.set(true);
    this.errorMsg.set(null);

    // Get Trip details
    this.tripService.getTripDetail(this.tripId).subscribe({
      next: (res) => {
        this.isLoadingDetail.set(false);
        if (res && res.data) {
          const t = res.data;
          this.trip.set(t);
          this.pwaService.cacheTripLocally(t);
          this.settingsForm.patchValue({
            title: t.title,
            destination: t.destination,
            start_date: this.formatIsoToDdMmYyyy(t.start_date),
            end_date: this.formatIsoToDdMmYyyy(t.end_date),
            budget: this.formatNumberWithDots(t.budget),
            num_travelers: t.num_travelers,
            status: t.status,
          });
          this.settingsForm.markAsPristine();
          this.settingsInitialized = true;

          // Fetch photo & weather for active trip destination
          if (t.destination) {
            this.fetchDestinationImage(t.destination);
            this.fetchWeatherForecast(t.destination);
          }
          if (this.canManageShares()) {
            this.fetchShares();
            this.loadPublicPublication();
          }
        }
      },
      error: (err) => {
        this.isLoadingDetail.set(false);
        // Try restoring from local offline cache
        const offlineTrip = this.pwaService.getLocalCachedTrip(this.tripId);
        if (offlineTrip) {
          this.trip.set(offlineTrip);
        } else {
          this.errorMsg.set('Không thể tải thông tin chuyến đi.');
        }
      },
    });

    this.fetchItinerary();
    this.fetchChatAndSuggestions();
  }

  fetchWeatherForecast(destination: string): void {
    const coords = this.getCoordinatesForDestination(destination);
    this.isLoadingWeather.set(true);
    this.weatherService.getWeatherForecast(coords[0], coords[1]).subscribe({
      next: (res) => {
        this.isLoadingWeather.set(false);
        this.weatherForecast.set(res);
      },
      error: () => {
        this.isLoadingWeather.set(false);
      },
    });
  }

  getWeatherForDate(dateStr: string): DailyWeather | undefined {
    const forecast = this.weatherForecast();
    if (!forecast || !forecast.daily) return undefined;
    return forecast.daily.find((d) => d.date === dateStr);
  }

  exportExcel(): void {
    const tripData = this.trip();
    const daysData = this.days();
    if (!tripData || !daysData || daysData.length === 0) {
      alert('Chưa có lịch trình để xuất file Excel.');
      return;
    }

    const formatActivityType = (type: string | null | undefined): string => {
      switch (type) {
        case 'transport':
          return 'Di chuyển';
        case 'meal':
          return 'Ăn uống';
        case 'attraction':
          return 'Tham quan';
        case 'hotel':
          return 'Lưu trú';
        default:
          return 'Khác';
      }
    };

    const wb = XLSX.utils.book_new();

    // Palette & Styles Definition
    const styles = {
      banner: {
        font: { name: 'Segoe UI', sz: 16, bold: true, color: { rgb: 'FFFFFF' } },
        fill: { fgColor: { rgb: '1E1B4B' } },
        alignment: { horizontal: 'center', vertical: 'center' }
      },
      sectionHeader: {
        font: { name: 'Segoe UI', sz: 12, bold: true, color: { rgb: '1E40AF' } },
        fill: { fgColor: { rgb: 'DBEAFE' } },
        alignment: { horizontal: 'left', vertical: 'center' }
      },
      dayBanner: {
        font: { name: 'Segoe UI', sz: 12, bold: true, color: { rgb: 'FFFFFF' } },
        fill: { fgColor: { rgb: '2563EB' } },
        alignment: { horizontal: 'left', vertical: 'center' }
      },
      tableHeader: {
        font: { name: 'Segoe UI', sz: 10, bold: true, color: { rgb: 'FFFFFF' } },
        fill: { fgColor: { rgb: '3B82F6' } },
        alignment: { horizontal: 'center', vertical: 'center' },
        border: {
          top: { style: 'thin', color: { rgb: '1D4ED8' } },
          bottom: { style: 'thin', color: { rgb: '1D4ED8' } },
          left: { style: 'thin', color: { rgb: '1D4ED8' } },
          right: { style: 'thin', color: { rgb: '1D4ED8' } }
        }
      },
      labelBold: {
        font: { name: 'Segoe UI', sz: 10, bold: true, color: { rgb: '334155' } },
        fill: { fgColor: { rgb: 'F8FAFC' } },
        alignment: { vertical: 'center' },
        border: {
          top: { style: 'thin', color: { rgb: 'E2E8F0' } },
          bottom: { style: 'thin', color: { rgb: 'E2E8F0' } },
          left: { style: 'thin', color: { rgb: 'E2E8F0' } },
          right: { style: 'thin', color: { rgb: 'E2E8F0' } }
        }
      },
      cellText: {
        font: { name: 'Segoe UI', sz: 10, color: { rgb: '0F172A' } },
        alignment: { vertical: 'center', wrapText: true },
        border: {
          top: { style: 'thin', color: { rgb: 'E2E8F0' } },
          bottom: { style: 'thin', color: { rgb: 'E2E8F0' } },
          left: { style: 'thin', color: { rgb: 'E2E8F0' } },
          right: { style: 'thin', color: { rgb: 'E2E8F0' } }
        }
      },
      cellCenter: {
        font: { name: 'Segoe UI', sz: 10, color: { rgb: '334155' } },
        alignment: { horizontal: 'center', vertical: 'center' },
        border: {
          top: { style: 'thin', color: { rgb: 'E2E8F0' } },
          bottom: { style: 'thin', color: { rgb: 'E2E8F0' } },
          left: { style: 'thin', color: { rgb: 'E2E8F0' } },
          right: { style: 'thin', color: { rgb: 'E2E8F0' } }
        }
      },
      cellBoldText: {
        font: { name: 'Segoe UI', sz: 10, bold: true, color: { rgb: '0F172A' } },
        alignment: { vertical: 'center' },
        border: {
          top: { style: 'thin', color: { rgb: 'E2E8F0' } },
          bottom: { style: 'thin', color: { rgb: 'E2E8F0' } },
          left: { style: 'thin', color: { rgb: 'E2E8F0' } },
          right: { style: 'thin', color: { rgb: 'E2E8F0' } }
        }
      },
      cellNumber: {
        font: { name: 'Segoe UI', sz: 10, color: { rgb: '0F172A' } },
        alignment: { horizontal: 'right', vertical: 'center' },
        numFmt: '#,##0',
        border: {
          top: { style: 'thin', color: { rgb: 'E2E8F0' } },
          bottom: { style: 'thin', color: { rgb: 'E2E8F0' } },
          left: { style: 'thin', color: { rgb: 'E2E8F0' } },
          right: { style: 'thin', color: { rgb: 'E2E8F0' } }
        }
      },
      totalRowLabel: {
        font: { name: 'Segoe UI', sz: 10, bold: true, color: { rgb: '78350F' } },
        fill: { fgColor: { rgb: 'FEF3C7' } },
        alignment: { vertical: 'center' },
        border: {
          top: { style: 'medium', color: { rgb: 'F59E0B' } },
          bottom: { style: 'medium', color: { rgb: 'F59E0B' } },
          left: { style: 'thin', color: { rgb: 'F59E0B' } },
          right: { style: 'thin', color: { rgb: 'F59E0B' } }
        }
      },
      totalRowNumber: {
        font: { name: 'Segoe UI', sz: 11, bold: true, color: { rgb: 'B45309' } },
        fill: { fgColor: { rgb: 'FEF3C7' } },
        alignment: { horizontal: 'right', vertical: 'center' },
        numFmt: '#,##0',
        border: {
          top: { style: 'medium', color: { rgb: 'F59E0B' } },
          bottom: { style: 'medium', color: { rgb: 'F59E0B' } },
          left: { style: 'thin', color: { rgb: 'F59E0B' } },
          right: { style: 'thin', color: { rgb: 'F59E0B' } }
        }
      }
    };

    const applyCellStyle = (ws: any, r: number, c: number, val: any, style: any, type: string = 's') => {
      const cellRef = XLSX.utils.encode_cell({ r, c });
      if (!ws[cellRef]) ws[cellRef] = { v: val };
      ws[cellRef].v = val;
      ws[cellRef].t = type;
      ws[cellRef].s = style;
      if (style.numFmt) ws[cellRef].z = style.numFmt;
    };

    // ==========================================
    // 1. SHEET TỔNG QUAN
    // ==========================================
    const wsSummary: any = {};
    wsSummary['!merges'] = [
      { s: { r: 0, c: 0 }, e: { r: 1, c: 4 } },
      { s: { r: 3, c: 0 }, e: { r: 3, c: 4 } },
      { s: { r: 12, c: 0 }, e: { r: 12, c: 4 } }
    ];

    // Banner
    for (let r = 0; r <= 1; r++) {
      for (let c = 0; c <= 4; c++) {
        applyCellStyle(wsSummary, r, c, '✈  SMART TRAVEL - KẾ HOẠCH DU LỊCH CHI TIẾT', styles.banner);
      }
    }

    // Section 1: Thông tin chuyến đi
    for (let c = 0; c <= 4; c++) {
      applyCellStyle(wsSummary, 3, c, '📋 THÔNG TIN TỔNG QUAN CHUYẾN ĐỊ', styles.sectionHeader);
    }

    const infoList = [
      ['Tên chuyến đi:', tripData.title || '', 's'],
      ['Điểm đến:', tripData.destination || '', 's'],
      ['Thời gian du lịch:', `${tripData.start_date || ''} đến ${tripData.end_date || ''}`, 's'],
      ['Tổng số ngày:', daysData.length, 'n'],
      ['Số người tham gia:', tripData.num_travelers || 1, 'n'],
      ['Ngân sách dự kiến:', Number(tripData.budget || 0), 'num'],
      ['Ghi chú / Sở thích:', tripData.preferences || 'Không có ghi chú', 's']
    ];

    infoList.forEach((info, idx) => {
      const r = 4 + idx;
      applyCellStyle(wsSummary, r, 0, info[0], styles.labelBold);
      const isNum = info[2] === 'num';
      applyCellStyle(wsSummary, r, 1, info[1], isNum ? styles.cellNumber : (info[2] === 'n' ? styles.cellCenter : styles.cellBoldText), isNum ? 'n' : (info[2] === 'n' ? 'n' : 's'));
      for (let c = 2; c <= 4; c++) {
        applyCellStyle(wsSummary, r, c, '', styles.cellText);
      }
    });

    // Section 2: Tổng hợp các ngày
    for (let c = 0; c <= 4; c++) {
      applyCellStyle(wsSummary, 12, c, '📊 TỔNG HỢP LỊCH TRÌNH NỔI BẬT THEO NGÀY', styles.sectionHeader);
    }

    const summaryHeaders = ['STT', 'Ngày Du Lịch', 'Số Hoạt Động', 'Tổng Chi Phí (VNĐ)', 'Ghi Chú Nổi Bật'];
    summaryHeaders.forEach((h, c) => applyCellStyle(wsSummary, 13, c, h, styles.tableHeader));

    let grandTotalCost = 0;

    daysData.forEach((day, idx) => {
      const r = 14 + idx;
      const actCount = (day.activities || []).length;
      const dayCost = (day.activities || []).reduce((sum, a) => sum + Number(a.estimated_cost || 0), 0);
      grandTotalCost += dayCost;

      applyCellStyle(wsSummary, r, 0, idx + 1, styles.cellCenter, 'n');
      applyCellStyle(wsSummary, r, 1, `Ngày ${day.day_number}${day.date ? ' (' + day.date + ')' : ''}`, styles.cellBoldText);
      applyCellStyle(wsSummary, r, 2, `${actCount} địa điểm/hoạt động`, styles.cellCenter);
      applyCellStyle(wsSummary, r, 3, dayCost, styles.cellNumber, 'n');
      applyCellStyle(wsSummary, r, 4, day.activities?.[0]?.title ? `Chính: ${day.activities[0].title}` : 'Lịch trình tự do', styles.cellText);
    });

    const summaryTotalR = 14 + daysData.length;
    applyCellStyle(wsSummary, summaryTotalR, 0, 'TỔNG CỘNG CHUYẾN ĐỊ', styles.totalRowLabel);
    applyCellStyle(wsSummary, summaryTotalR, 1, `${daysData.length} Ngày`, styles.totalRowLabel);
    applyCellStyle(wsSummary, summaryTotalR, 2, '', styles.totalRowLabel);
    applyCellStyle(wsSummary, summaryTotalR, 3, grandTotalCost, styles.totalRowNumber, 'n');
    applyCellStyle(wsSummary, summaryTotalR, 4, '', styles.totalRowLabel);

    wsSummary['!cols'] = [{ wch: 8 }, { wch: 24 }, { wch: 22 }, { wch: 22 }, { wch: 45 }];
    wsSummary['!rows'] = [{ hpt: 22 }, { hpt: 22 }, { hpt: 10 }, { hpt: 24 }];
    wsSummary['!ref'] = XLSX.utils.encode_range({ s: { r: 0, c: 0 }, e: { r: summaryTotalR + 1, c: 4 } });
    XLSX.utils.book_append_sheet(wb, wsSummary, 'Tổng quan');

    // ==========================================
    // 2. SHEET LỊCH TRÌNH CHI TIẾT (TẤT CẢ CÁC NGÀY GỘP TẠI NƠI NÀY)
    // ==========================================
    const wsMaster: any = {};
    const masterMerges: any[] = [{ s: { r: 0, c: 0 }, e: { r: 1, c: 4 } }];

    // Master Banner
    for (let r = 0; r <= 1; r++) {
      for (let c = 0; c <= 4; c++) {
        applyCellStyle(wsMaster, r, c, '🗺  LỊCH TRÌNH DỰ KIẾN CHI TIẾT TẤT CẢ CÁC NGÀY', styles.banner);
      }
    }

    let currentRow = 3;

    daysData.forEach((day) => {
      // Day Header Banner
      masterMerges.push({ s: { r: currentRow, c: 0 }, e: { r: currentRow, c: 4 } });
      for (let c = 0; c <= 4; c++) {
        applyCellStyle(wsMaster, currentRow, c, `📅 NGÀY ${day.day_number}${day.date ? ' - ' + day.date : ''}`, styles.dayBanner);
      }
      currentRow++;

      // Table Header
      const headers = ['Khung Giờ', 'Tên Hoạt Động / Địa Điểm', 'Phân Loại', 'Chi Phí (VNĐ)', 'Địa Chỉ & Ghi Chú Chi Tiết'];
      headers.forEach((h, c) => applyCellStyle(wsMaster, currentRow, c, h, styles.tableHeader));
      currentRow++;

      const activities = day.activities || [];
      let dayCost = 0;

      if (activities.length === 0) {
        applyCellStyle(wsMaster, currentRow, 0, '—', styles.cellCenter);
        applyCellStyle(wsMaster, currentRow, 1, 'Chưa có hoạt động nào được thêm vào ngày này', styles.cellText);
        applyCellStyle(wsMaster, currentRow, 2, '—', styles.cellCenter);
        applyCellStyle(wsMaster, currentRow, 3, 0, styles.cellNumber, 'n');
        applyCellStyle(wsMaster, currentRow, 4, 'Dành thời gian tự do khám phá', styles.cellText);
        currentRow++;
      } else {
        activities.forEach((act) => {
          const cost = Number(act.estimated_cost || 0);
          dayCost += cost;

          const timeStr = act.start_time
            ? act.end_time
              ? `${act.start_time} - ${act.end_time}`
              : act.start_time
            : 'Cả ngày';

          const note = [act.description || '', act.location?.address || act.notes || ''].filter(Boolean).join(' | ');

          applyCellStyle(wsMaster, currentRow, 0, timeStr, styles.cellCenter);
          applyCellStyle(wsMaster, currentRow, 1, act.title || 'Hoạt động', styles.cellBoldText);
          applyCellStyle(wsMaster, currentRow, 2, formatActivityType(act.type), styles.cellCenter);
          applyCellStyle(wsMaster, currentRow, 3, cost, styles.cellNumber, 'n');
          applyCellStyle(wsMaster, currentRow, 4, note, styles.cellText);
          currentRow++;
        });
      }

      // Day Subtotal
      applyCellStyle(wsMaster, currentRow, 0, `TỔNG CỘNG NGÀY ${day.day_number}`, styles.totalRowLabel);
      applyCellStyle(wsMaster, currentRow, 1, '', styles.totalRowLabel);
      applyCellStyle(wsMaster, currentRow, 2, '', styles.totalRowLabel);
      applyCellStyle(wsMaster, currentRow, 3, dayCost, styles.totalRowNumber, 'n');
      applyCellStyle(wsMaster, currentRow, 4, '', styles.totalRowLabel);
      currentRow += 2; // Spacing row
    });

    wsMaster['!merges'] = masterMerges;
    wsMaster['!cols'] = [{ wch: 16 }, { wch: 32 }, { wch: 16 }, { wch: 20 }, { wch: 50 }];
    wsMaster['!ref'] = XLSX.utils.encode_range({ s: { r: 0, c: 0 }, e: { r: currentRow, c: 4 } });
    XLSX.utils.book_append_sheet(wb, wsMaster, 'Lịch trình chi tiết');

    // ==========================================
    // 3. EACH INDIVIDUAL DAY SHEET
    // ==========================================
    daysData.forEach((day) => {
      const sheetName = `Ngày ${day.day_number}`;
      const wsDay: any = {};
      wsDay['!merges'] = [
        { s: { r: 0, c: 0 }, e: { r: 1, c: 4 } }
      ];

      // Banner
      for (let r = 0; r <= 1; r++) {
        for (let c = 0; c <= 4; c++) {
          applyCellStyle(wsDay, r, c, `📅 LỊCH TRÌNH NGÀY ${day.day_number}${day.date ? ' (' + day.date + ')' : ''}`, styles.dayBanner);
        }
      }

      const headers = ['Khung Giờ', 'Tên Hoạt Động / Địa Điểm', 'Phân Loại', 'Chi Phí (VNĐ)', 'Chi Tiết / Địa Chỉ & Ghi Chú'];
      headers.forEach((h, c) => applyCellStyle(wsDay, 3, c, h, styles.tableHeader));

      const activities = day.activities || [];
      let dayCost = 0;
      let r = 4;

      if (activities.length === 0) {
        applyCellStyle(wsDay, r, 0, '—', styles.cellCenter);
        applyCellStyle(wsDay, r, 1, 'Chưa có hoạt động', styles.cellText);
        applyCellStyle(wsDay, r, 2, '—', styles.cellCenter);
        applyCellStyle(wsDay, r, 3, 0, styles.cellNumber, 'n');
        applyCellStyle(wsDay, r, 4, 'Thời gian tự do', styles.cellText);
        r++;
      } else {
        activities.forEach((act) => {
          const cost = Number(act.estimated_cost || 0);
          dayCost += cost;

          const timeStr = act.start_time
            ? act.end_time
              ? `${act.start_time} - ${act.end_time}`
              : act.start_time
            : 'Cả ngày';

          const note = [act.description || '', act.location?.address || act.notes || ''].filter(Boolean).join(' | ');

          applyCellStyle(wsDay, r, 0, timeStr, styles.cellCenter);
          applyCellStyle(wsDay, r, 1, act.title || 'Hoạt động', styles.cellBoldText);
          applyCellStyle(wsDay, r, 2, formatActivityType(act.type), styles.cellCenter);
          applyCellStyle(wsDay, r, 3, cost, styles.cellNumber, 'n');
          applyCellStyle(wsDay, r, 4, note, styles.cellText);
          r++;
        });
      }

      // Total Row
      applyCellStyle(wsDay, r, 0, `TỔNG CỘNG NGÀY ${day.day_number}`, styles.totalRowLabel);
      applyCellStyle(wsDay, r, 1, '', styles.totalRowLabel);
      applyCellStyle(wsDay, r, 2, '', styles.totalRowLabel);
      applyCellStyle(wsDay, r, 3, dayCost, styles.totalRowNumber, 'n');
      applyCellStyle(wsDay, r, 4, '', styles.totalRowLabel);

      wsDay['!cols'] = [{ wch: 16 }, { wch: 30 }, { wch: 16 }, { wch: 20 }, { wch: 50 }];
      wsDay['!ref'] = XLSX.utils.encode_range({ s: { r: 0, c: 0 }, e: { r: r + 1, c: 4 } });
      XLSX.utils.book_append_sheet(wb, wsDay, sheetName);
    });

    const cleanDestination = (tripData.destination || 'Chuyen_di').replace(/[^a-zA-Z0-9_\u00C0-\u024F\u1EA0-\u1EFF]/g, '_');
    const cleanTitle = (tripData.title || 'detail').replace(/[^a-zA-Z0-9_\u00C0-\u024F\u1EA0-\u1EFF]/g, '_');
    const fileName = `Lich_trinh_${cleanDestination}_${cleanTitle}.xlsx`;

    XLSX.writeFile(wb, fileName);
  }

  fetchDestinationImage(destination: string): void {
    const dest = destination.trim();
    if (!dest) return;
    this.placePhotoService.getPhotos(dest, 3).subscribe({
      next: (photos) => {
        if (photos && photos.length > 0) {
          this.destinationImagesMap.update((map) => {
            const newMap = new Map(map);
            newMap.set(dest.toLowerCase().trim(), photos);
            return newMap;
          });
        }
      },
    });
  }

  private parseTimeToMinutes(timeStr?: string | null): number | null {
    if (!timeStr || typeof timeStr !== 'string') return null;
    const trimmed = timeStr.trim();
    if (!trimmed) return null;
    const parts = trimmed.split(':');
    if (parts.length < 2) return null;
    const hours = parseInt(parts[0], 10);
    const minutes = parseInt(parts[1], 10);
    if (isNaN(hours) || isNaN(minutes)) return null;
    return hours * 60 + minutes;
  }

  public sortActivitiesByStartTime(activities: ActivityResponse[]): ActivityResponse[] {
    if (!activities) return [];
    return [...activities].sort((a, b) => {
      const minA = this.parseTimeToMinutes(a.start_time);
      const minB = this.parseTimeToMinutes(b.start_time);

      if (minA !== null && minB !== null) {
        if (minA !== minB) return minA - minB;
        const endA = this.parseTimeToMinutes(a.end_time);
        const endB = this.parseTimeToMinutes(b.end_time);
        if (endA !== null && endB !== null && endA !== endB) {
          return endA - endB;
        }
        return (a.order_index ?? 0) - (b.order_index ?? 0);
      }

      if (minA !== null && minB === null) return -1;
      if (minA === null && minB !== null) return 1;

      return (a.order_index ?? 0) - (b.order_index ?? 0);
    });
  }

  fetchItinerary(): void {
    this.isLoadingDays.set(true);
    this.tripService.listDays(this.tripId).subscribe({
      next: (res) => {
        this.isLoadingDays.set(false);
        if (res && res.data) {
          // Sort days by day_number and sort activities of each day by start_time ascending
          const sortedDays = res.data
            .map((day) => ({
              ...day,
              activities: this.sortActivitiesByStartTime(day.activities || []),
            }))
            .sort((a, b) => a.day_number - b.day_number);
          this.days.set(sortedDays);
          this.refreshItineraryQuality();
          if (this.activeSubTab() === 'route') {
            if (this.routeDayIndex() >= sortedDays.length) {
              this.routeDayIndex.set(0);
            }
            setTimeout(() => this.renderRouteForDay(this.routeDayIndex()), 100);
          }
        }
      },
      error: () => {
        this.isLoadingDays.set(false);
      },
    });
  }

  refreshItineraryQuality(): void {
    this.isCheckingQuality.set(true);
    this.tripService.checkItineraryQuality(this.tripId).subscribe({
      next: (res) => {
        this.isCheckingQuality.set(false);
        this.itineraryQuality.set(res.data);
      },
      error: () => this.isCheckingQuality.set(false),
    });
  }

  toggleActivityLock(activity: ActivityResponse, event: Event): void {
    event.stopPropagation();
    if (!this.canEditTrip() || this.updatingLockId()) return;
    this.updatingLockId.set(activity.id);
    this.tripService.updateActivity(activity.id, { is_locked: !activity.is_locked }).subscribe({
      next: (res) => {
        this.updatingLockId.set(null);
        this.days.update((days) =>
          days.map((day) => ({
            ...day,
            activities: this.sortActivitiesByStartTime(
              day.activities.map((item) => (item.id === activity.id ? res.data : item))
            ),
          }))
        );
        this.refreshItineraryQuality();
      },
      error: (err) => {
        this.updatingLockId.set(null);
        this.activityError.set(err?.error?.message || 'Không thể thay đổi trạng thái khóa hoạt động.');
      },
    });
  }

  fetchChatAndSuggestions(): void {
    // Get chat history
    this.tripService.getChatHistory(this.tripId).subscribe({
      next: (res) => {
        if (res && res.data) {
          this.chatHistory.set(this.filterLegacyAutoSummaryThread(res.data));
          this.scrollToBottom();
        }
      },
    });

    // Get pending AI recommendations
    this.tripService.listSuggestions(this.tripId, 'pending').subscribe({
      next: (res) => {
        if (res && res.data) {
          this.activeSuggestions.set(res.data);
        }
      },
    });
  }

  // AI Auto Itinerary Generation
  onGenerateItinerary(): void {
    if (!this.canEditTrip()) return;
    this.openGenerateOptions();
  }

  openGenerateOptions(): void {
    if (!this.canEditTrip()) return;
    if (this.isGenerating()) return;
    this.generationOptionsError.set(null);
    this.isGenerateOptionsOpen.set(true);
  }

  closeGenerateOptions(): void {
    if (this.isGenerating()) return;
    this.isGenerateOptionsOpen.set(false);
    this.generationOptionsError.set(null);
  }

  onSubmitGenerateOptions(): void {
    if (this.generateOptionsForm.invalid) {
      this.generateOptionsForm.markAllAsTouched();
      this.generationOptionsError.set('Vui lòng kiểm tra lại định dạng giờ trước khi tạo lịch trình.');
      return;
    }

    this.isGenerateOptionsOpen.set(false);
    this.runGenerateItinerary(this.buildGeneratePayload());
  }

  private runGenerateItinerary(payload: GenerateDaysRequest): void {
    if (!this.canEditTrip()) return;
    this.isGenerating.set(true);
    this.generationSummary.set(null);
    this.generationProgressMessage.set('Dang tim dia diem phu hop...');
    setTimeout(() => {
      if (this.isGenerating()) this.generationProgressMessage.set('Dang toi uu tuyen duong va khung gio...');
    }, 1200);
    setTimeout(() => {
      if (this.isGenerating()) this.generationProgressMessage.set('Dang kiem tra ngan sach...');
    }, 2400);
    this.tripService.generateDays(this.tripId, payload).subscribe({
      next: (res) => {
        this.isGenerating.set(false);
        this.generationProgressMessage.set(null);
        this.generationSummary.set(res.data?.summary || null);
        this.routeDayIndex.set(0);
        this.clearRouteLayers();
        this.routeSegments.set([]);
        this.routeTotalDistance.set(0);
        this.routeTotalDuration.set(0);
        this.fetchItinerary();
      },
      error: (err) => {
        this.isGenerating.set(false);
        this.generationProgressMessage.set(null);
        alert(err?.error?.message || 'Có lỗi xảy ra khi tự động tạo lịch trình.');
      },
    });
  }

  canEditTrip(): boolean {
    const role = this.trip()?.role;
    return role === 'owner' || role === 'editor';
  }

  canManageShares(): boolean {
    return this.trip()?.role === 'owner';
  }

  canPublishCompletedTrip(): boolean {
    return this.canManageShares() && this.trip()?.status === 'completed' && this.days().length > 0;
  }

  openPublishWizard(): void {
    if (!this.canPublishCompletedTrip()) {
      this.publishError.set('Chỉ chủ sở hữu có thể chia sẻ chuyến đã hoàn thành và có lịch trình.');
      return;
    }
    const currentTrip = this.trip();
    this.publicationDraft.title = currentTrip?.title || '';
    this.publicationDraft.summary =
      `Lịch trình ${currentTrip?.destination || ''} ${this.days().length} ngày đã được tôi trải nghiệm và xác nhận.`;
    this.publicationDraft.actual_total_cost = this.budgetSummary()?.budget_actual?.toString() || '';
    this.publicationReviews = {};
    for (const day of this.days()) {
      for (const activity of day.activities || []) {
        if (!activity.location_id) continue;
        this.publicationReviews[activity.id] = {
          activity_id: activity.id,
          actual_status: 'visited',
          author_verdict: 'recommended',
          rating: 4,
          next_traveler_note: '',
          actual_cost: activity.estimated_cost,
        };
      }
    }
    this.publishError.set(null);
    this.publicationFieldErrors.set({});
    this.publishedPublicSlug.set(null);
    this.isPublishWizardOpen.set(true);
    if (this.existingPublicSlug()) {
      this.publicTripService.getOwnerPublication(this.tripId).subscribe({
        next: response => {
          const publication = response.data;
          this.publicationDraft.title = publication.title;
          this.publicationDraft.summary = publication.summary;
          this.publicationDraft.actual_total_cost = publication.actual_total_cost?.toString() || '';
          this.publicationDraft.itinerary_rating = publication.itinerary_rating || 5;
          this.publicationDraft.cost_rating = publication.cost_rating || 5;
          this.publicationDraft.place_rating = publication.place_rating || 5;
          this.publicationDraft.best_places = (publication.snapshot_json.review?.best_places || []).join(', ');
          this.publicationDraft.best_foods = (publication.snapshot_json.review?.best_foods || []).join(', ');
          this.publicationDraft.general_tips = publication.snapshot_json.review?.tips || '';
          this.publicationDraft.show_author_name = publication.privacy_options?.['show_author_name'] ?? true;
          this.publicationDraft.show_cost = publication.privacy_options?.['show_cost'] ?? true;
          this.publicationDraft.allow_clone = publication.allow_clone;
          this.publicationDraft.allow_partial_import = publication.allow_partial_import;
          for (const day of publication.snapshot_json.days || []) {
            for (const activity of day.activities || []) {
              const activityId = activity.source_activity_id;
              if (!activityId || !this.publicationReviews[activityId]) continue;
              this.publicationReviews[activityId] = {
                activity_id: activityId,
                actual_status: activity.actual_status,
                author_verdict: activity.author_verdict,
                rating: activity.rating,
                next_traveler_note: activity.next_traveler_note,
                best_time: activity.best_time,
                actual_wait_minutes: activity.actual_wait_minutes,
                booking_required: activity.booking_required,
                actual_cost: activity.actual_cost,
              };
            }
          }
        },
      });
    }
  }

  loadPublicPublication(): void {
    if (!this.canManageShares()) return;
    this.publicTripService.getOwnerPublication(this.tripId).subscribe({
      next: response => {
        if (response.data?.status === 'published') {
          this.existingPublicSlug.set(response.data.slug);
        }
      },
      error: () => this.existingPublicSlug.set(null),
    });
  }

  publicationReview(activityId: string): PublicActivityReview {
    if (!this.publicationReviews[activityId]) {
      this.publicationReviews[activityId] = {
        activity_id: activityId,
        actual_status: 'visited',
        author_verdict: 'recommended',
        rating: 4,
        next_traveler_note: '',
      };
    }
    return this.publicationReviews[activityId];
  }

  verdictOptions(): Array<{ value: AuthorVerdict; label: string }> {
    return [
      { value: 'must_go', label: 'Nhất định nên đi' },
      { value: 'recommended', label: 'Đáng đi' },
      { value: 'preference_based', label: 'Tùy sở thích' },
      { value: 'skip', label: 'Có thể bỏ qua' },
    ];
  }

  publishCompletedTrip(): void {
    if (!this.canPublishCompletedTrip() || this.isPublishingPublicTrip()) return;
    if (!this.validatePublicationDraft()) return;

    const splitList = (value: string) =>
      value.split(/[,;\n]+/).map(item => item.trim()).filter(Boolean);
    const rawCost = this.publicationDraft.actual_total_cost.replace(/\D/g, '');
    const payload: PublishTripRequest = {
      title: this.publicationDraft.title.trim(),
      summary: this.publicationDraft.summary.trim(),
      visibility: this.publicationDraft.visibility,
      actual_total_cost: rawCost ? Number(rawCost) : null,
      itinerary_rating: Number(this.publicationDraft.itinerary_rating),
      cost_rating: Number(this.publicationDraft.cost_rating),
      place_rating: Number(this.publicationDraft.place_rating),
      best_places: splitList(this.publicationDraft.best_places),
      best_foods: splitList(this.publicationDraft.best_foods),
      general_tips: this.publicationDraft.general_tips.trim() || null,
      tags: ['lịch trình thực tế'],
      show_travel_month: true,
      show_author_name: this.publicationDraft.show_author_name,
      show_cost: this.publicationDraft.show_cost,
      allow_clone: this.publicationDraft.allow_clone,
      allow_partial_import: this.publicationDraft.allow_partial_import,
      allow_comments: false,
      activity_reviews: Object.values(this.publicationReviews),
      author_confirmed: true,
    };
    this.isPublishingPublicTrip.set(true);
    this.publishError.set(null);
    this.publicTripService.publish(this.tripId, payload).subscribe({
      next: response => {
        this.isPublishingPublicTrip.set(false);
        this.publishedPublicSlug.set(response.data.slug);
        this.existingPublicSlug.set(response.data.slug);
      },
      error: error => {
        this.isPublishingPublicTrip.set(false);
        const fieldErrors: Record<string, string> = {};
        for (const issue of apiValidationIssues(error)) {
          if (issue.field) fieldErrors[issue.field] = issue.message;
        }
        this.publicationFieldErrors.set(fieldErrors);
        this.publishError.set(apiErrorMessage(error, 'Không thể xuất bản lịch trình.'));
      },
    });
  }

  publicationFieldError(field: string): string {
    return this.publicationFieldErrors()[field] || '';
  }

  clearPublicationFieldError(field: string): void {
    if (!this.publicationFieldErrors()[field] && !this.publishError()) return;
    this.publicationFieldErrors.update((current) => {
      const next = { ...current };
      delete next[field];
      return next;
    });
    this.publishError.set(null);
  }

  private validatePublicationDraft(): boolean {
    const errors: Record<string, string> = {};
    const title = this.publicationDraft.title.trim();
    const summary = this.publicationDraft.summary.trim();
    const rawCostInput = this.publicationDraft.actual_total_cost.trim();
    const rawCost = rawCostInput.replace(/\D/g, '');
    const bestPlaces = this.splitPublicationList(this.publicationDraft.best_places);
    const bestFoods = this.splitPublicationList(this.publicationDraft.best_foods);

    if (title.length < 3) errors['title'] = 'Tiêu đề phải có ít nhất 3 ký tự.';
    else if (title.length > 200) errors['title'] = 'Tiêu đề không được vượt quá 200 ký tự.';
    if (summary.length < 10) errors['summary'] = 'Tóm tắt phải có ít nhất 10 ký tự.';
    else if (summary.length > 2000) errors['summary'] = 'Tóm tắt không được vượt quá 2.000 ký tự.';

    if (rawCostInput && !/^[\d.,\s]+$/.test(rawCostInput)) {
      errors['actual_total_cost'] = 'Chi phí chỉ được chứa chữ số và dấu phân cách.';
    } else if (rawCost && (!Number.isSafeInteger(Number(rawCost)) || Number(rawCost) > MAX_BUDGET_VND)) {
      errors['actual_total_cost'] = 'Chi phí không được lớn hơn 2.000.000.000 VND.';
    }

    this.validatePublicationList(bestPlaces, 'best_places', 'Điểm đáng đi nhất', errors);
    this.validatePublicationList(bestFoods, 'best_foods', 'Đặc sản nên thử', errors);

    const reviews = Object.values(this.publicationReviews);
    if (reviews.length > 300) {
      errors['activity_reviews'] = 'Chỉ có thể công khai tối đa 300 đánh giá hoạt động.';
    }
    for (const review of reviews) {
      const note = (review.next_traveler_note || '').trim();
      if (note.length > 1000) {
        errors[`review:${review.activity_id}`] = 'Ghi chú không được vượt quá 1.000 ký tự.';
      }
      review.next_traveler_note = note || null;
    }

    if (!this.publicationDraft.author_confirmed) {
      errors['author_confirmed'] = 'Bạn cần xác nhận đây là lịch trình thực tế chính thức.';
    }

    this.publicationDraft.title = title;
    this.publicationDraft.summary = summary;
    this.publicationFieldErrors.set(errors);
    const firstError = Object.values(errors)[0] || null;
    this.publishError.set(firstError);
    return firstError === null;
  }

  private splitPublicationList(value: string): string[] {
    return value.split(/[,;\n]+/).map(item => item.trim()).filter(Boolean);
  }

  private validatePublicationList(
    items: string[],
    field: string,
    label: string,
    errors: Record<string, string>,
  ): void {
    if (items.length > 20) {
      errors[field] = `${label} chỉ được có tối đa 20 mục.`;
    } else if (items.some(item => item.length > 200)) {
      errors[field] = `Mỗi mục trong ${label.toLowerCase()} không được vượt quá 200 ký tự.`;
    }
  }

  viewPublishedTrip(): void {
    const slug = this.publishedPublicSlug() || this.existingPublicSlug();
    if (slug) this.router.navigate(['/community/trips', slug]);
  }

  fetchShares(): void {
    if (!this.canManageShares()) return;
    this.isLoadingShares.set(true);
    this.shareErrorMsg.set(null);
    this.tripService.listTripShares(this.tripId).subscribe({
      next: (res) => {
        this.isLoadingShares.set(false);
        this.shareParticipants.set(res.data?.participants || []);
        this.shareInvites.set(res.data?.invites || []);
      },
      error: (err) => {
        this.isLoadingShares.set(false);
        this.shareErrorMsg.set(err?.error?.message || 'Khong the tai danh sach chia se.');
      },
    });
  }

  openHistory(): void {
    if (this.isChatOpen() && this.activeRightTab() === 'history') {
      this.isChatOpen.set(false);
    } else {
      this.activeRightTab.set('history');
      this.isChatOpen.set(true);
      this.loadHistory(true);
    }
  }

  closeHistory(): void {
    this.isChatOpen.set(false);
  }

  loadHistory(reset = false): void {
    if (!this.tripId || this.isLoadingHistory()) return;
    const nextPage = reset ? 1 : this.historyPage() + 1;
    this.isLoadingHistory.set(true);
    this.historyErrorMsg.set(null);
    this.tripService.listTripHistory(this.tripId, nextPage, this.historyLimit).subscribe({
      next: (res) => {
        this.isLoadingHistory.set(false);
        const data = res.data;
        if (!data) return;
        this.historyPage.set(data.page);
        this.historyTotal.set(data.total);
        this.historyItems.set(reset ? data.items : [...this.historyItems(), ...data.items]);
      },
      error: (err) => {
        this.isLoadingHistory.set(false);
        this.historyErrorMsg.set(err?.error?.message || 'Khong the tai lich su chuyen di.');
      },
    });
  }

  loadMoreHistory(): void {
    if (!this.hasMoreHistory()) return;
    this.loadHistory(false);
  }

  hasMoreHistory(): boolean {
    return this.historyItems().length < this.historyTotal();
  }

  getHistoryEntityLabel(entityType: string): string {
    const labels: Record<string, string> = {
      trip: 'Chuyen di',
      itinerary: 'Lich trinh',
      activity: 'Hoat dong',
      budget_item: 'Chi tieu',
      share_invite: 'Chia se',
      participant: 'Thanh vien',
      ai_suggestion: 'AI',
    };
    return labels[entityType] || entityType;
  }

  formatHistoryValue(value: any): string {
    if (value === null || value === undefined || value === '') return 'Trong';
    if (typeof value === 'boolean') return value ? 'Co' : 'Khong';
    if (typeof value === 'object') return JSON.stringify(value);
    const text = String(value);
    return text.length > 90 ? `${text.slice(0, 90)}...` : text;
  }

  getHistoryActorName(item: TripHistoryEvent): string {
    return item.actor?.full_name || item.actor?.username || 'He thong';
  }

  getHistoryActorInitials(item: TripHistoryEvent): string {
    const name = this.getHistoryActorName(item).trim();
    return name ? name.substring(0, 2).toUpperCase() : 'HT';
  }

  navigateToHistoryTarget(item: TripHistoryEvent): void {
    if (!item) return;
    const meta = item.metadata || {};
    const entityType = (item.entity_type || '').toLowerCase();
    const entityId = item.entity_id;

    // 1. Budget items (check before activity to avoid truthy entityId condition)
    if (
      entityType === 'budget' ||
      entityType === 'budget_item' ||
      meta['budget_item_id'] ||
      meta['category']
    ) {
      this.activeSubTab.set('budget');
      return;
    }

    // 2. Activity events
    if (
      entityType === 'activity' ||
      meta['activity_id'] ||
      meta['day_id'] ||
      meta['day_number']
    ) {
      const activityId = meta['activity_id'] || (entityType === 'activity' ? entityId : null);
      const dayId = meta['day_id'];
      const dayNumber = meta['day_number'];

      // Switch to itinerary sub-tab
      this.activeSubTab.set('itinerary');

      // Find matching day in current trip days
      const daysList = this.days();
      let targetDayIdx = -1;

      if (dayId) {
        targetDayIdx = daysList.findIndex((d) => d.id === dayId);
      } else if (dayNumber) {
        targetDayIdx = daysList.findIndex((d) => d.day_number === Number(dayNumber));
      } else if (activityId) {
        targetDayIdx = daysList.findIndex((d) => (d.activities || []).some((a) => a.id === activityId));
      }

      if (targetDayIdx >= 0) {
        this.selectDayTab(targetDayIdx);
        this.routeDayIndex.set(targetDayIdx);
      }

      // Smooth scroll to target activity card and highlight it
      if (activityId) {
        setTimeout(() => {
          const el = document.getElementById(`activity-card-${activityId}`);
          if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            this.highlightedActivityId.set(activityId);
            setTimeout(() => {
              if (this.highlightedActivityId() === activityId) {
                this.highlightedActivityId.set(null);
              }
            }, 2500);
          }
        }, 150);
      }
      return;
    }

    // 3. Settings / Participants / Shares / Publications
    if (
      entityType === 'trip' ||
      entityType === 'participant' ||
      entityType === 'share' ||
      entityType === 'share_invite' ||
      entityType === 'publication'
    ) {
      this.activeSubTab.set('settings');
      return;
    }

    // Default fallback
    this.activeSubTab.set('itinerary');
  }

  private buildGeneratePayload(): GenerateDaysRequest {
    const val = this.generateOptionsForm.getRawValue();
    return {
      overwrite: true,
      must_visit: this.parsePlanningList(val.must_visit_text),
      avoid_places: this.parsePlanningList(val.avoid_places_text),
      interest_weights: this.buildInterestWeights(val),
      pace: val.pace,
      budget_mode: val.budget_mode,
      prioritize_user_places: val.prioritize_user_places,
      transport_mode: val.transport_mode,
      departure_location: val.departure_location || null,
      departure_time: val.departure_time || null,
      estimated_travel_hours: val.estimated_travel_hours ?? null,
      arrival_transport: val.arrival_transport || null,
      daily_start_time: val.daily_start_time || null,
      daily_end_time: val.daily_end_time || null,
      dietary_notes: val.dietary_notes || null,
      mobility_notes: val.mobility_notes || null,
      ai: true,
    };
  }

  private parsePlanningList(value: string): string[] {
    return value
      .split(/[\n,;]+/)
      .map((item) => item.trim())
      .filter((item, index, arr) => item.length > 0 && arr.indexOf(item) === index)
      .slice(0, 20);
  }

  private buildInterestWeights(value: ReturnType<typeof this.generateOptionsForm.getRawValue>): Record<string, number> {
    const weights: Record<string, number> = {};
    if (value.interest_foodie) weights['foodie'] = 8;
    if (value.interest_culture) weights['culture'] = 7;
    if (value.interest_nature) weights['nature'] = 7;
    if (value.interest_cafe) weights['cafe'] = 6;
    if (value.interest_beaches) weights['beaches'] = 7;
    if (value.interest_adventure) weights['adventure'] = 6;
    return weights;
  }

  private filterLegacyAutoSummaryThread(messages: ChatHistoryItem[]): ChatHistoryItem[] {
    const filtered: ChatHistoryItem[] = [];
    for (let i = 0; i < messages.length; i++) {
      const message = messages[i];
      if (this.isLegacyAutoSummaryPrompt(message)) {
        if (messages[i + 1]?.role === 'assistant') {
          i += 1;
        }
        continue;
      }
      filtered.push(message);
    }
    return filtered;
  }

  private isLegacyAutoSummaryPrompt(message: ChatHistoryItem): boolean {
    if (message.role !== 'user') return false;
    const normalized = message.message
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase();
    return normalized.includes('hay tom tat lich trinh') && normalized.includes('vua thiet ke');
  }

  onCreateShareInvite(): void {
    if (!this.canManageShares() || this.shareForm.invalid) return;
    const value = this.shareForm.getRawValue();
    this.isSubmittingShare.set(true);
    this.shareErrorMsg.set(null);
    this.shareSuccessMsg.set(null);
    this.latestInviteUrl.set(null);

    this.tripService.createTripInvite(this.tripId, {
      recipient: value.recipient.trim() || null,
      role: value.role,
      expires_in_days: value.expires_in_days,
    }).subscribe({
      next: (res) => {
        this.isSubmittingShare.set(false);
        const invite = res.data;
        const hasRecipient = !!value.recipient.trim();
        this.shareSuccessMsg.set(
          hasRecipient
            ? invite.email_sent
              ? 'Đã tạo lời mời, gửi thông báo trong ứng dụng và gửi email cho người nhận.'
              : 'Đã tạo lời mời và thông báo trong ứng dụng, nhưng email chưa gửi được. Bạn có thể copy link bên dưới.'
            : 'Đã tạo link mời mở. Hãy copy link bên dưới để chia sẻ.',
        );
        if (invite?.accept_url) {
          this.latestInviteUrl.set(`${window.location.origin}${invite.accept_url}`);
        }
        this.shareForm.patchValue({ recipient: '' });
        this.fetchShares();
      },
      error: (err) => {
        this.isSubmittingShare.set(false);
        this.shareErrorMsg.set(err?.error?.message || 'Khong the tao loi moi chia se.');
      },
    });
  }

  copyLatestInviteUrl(): void {
    const url = this.latestInviteUrl();
    if (!url) return;
    this.copyToClipboard(url).then(() => {
      this.shareSuccessMsg.set('Đã copy link mời.');
    }).catch(err => {
      console.error('Copy invite error:', err);
    });
  }

  onUpdateParticipantRole(participant: TripParticipant, role: TripShareRole): void {
    if (!this.canManageShares() || participant.role === role) return;
    this.tripService.updateTripParticipant(this.tripId, participant.id, role).subscribe({
      next: () => this.fetchShares(),
      error: (err) => this.shareErrorMsg.set(err?.error?.message || 'Khong the cap nhat quyen.'),
    });
  }

  onRevokeParticipant(participantId: string): void {
    if (!this.canManageShares()) return;
    this.tripService.revokeTripParticipant(this.tripId, participantId).subscribe({
      next: () => this.fetchShares(),
      error: (err) => this.shareErrorMsg.set(err?.error?.message || 'Khong the thu hoi quyen.'),
    });
  }

  onRevokeInvite(inviteId: string): void {
    if (!this.canManageShares()) return;
    this.tripService.revokeTripInvite(inviteId).subscribe({
      next: () => this.fetchShares(),
      error: (err) => this.shareErrorMsg.set(err?.error?.message || 'Khong the huy loi moi.'),
    });
  }

  getTripRoleLabel(role: string | null | undefined): string {
    if (role === 'owner') return 'Chu chuyen di';
    return role === 'editor' ? 'Duoc chia se: Sua' : 'Duoc chia se: Xem';
  }

  // Send Chat Message to AI
  onSendChatMessage(): void {
    if (!this.canEditTrip()) return;
    const text = this.chatInput().trim();
    if (!text || this.isSendingMessage()) return;

    // Add user message locally
    const userMsg: ChatHistoryItem = {
      id: '',
      role: 'user',
      message: text,
      created_at: new Date().toISOString(),
    };
    this.chatHistory.update((hist) => [...hist, userMsg]);
    this.chatInput.set('');
    this.isSendingMessage.set(true);
    this.scrollToBottom();

    this.sendMessageToAi(text);
  }

  private sendMessageToAi(messageText: string): void {
    const tempAiId = 'temp-ai-' + Date.now();
    const initialAiMsg: ChatHistoryItem = {
      id: tempAiId,
      role: 'assistant',
      message: '',
      created_at: new Date().toISOString(),
    };
    this.chatHistory.update((hist) => [...hist, initialAiMsg]);
    this.scrollToBottom();

    this.aiStreamService.streamMessage(
      this.tripId,
      messageText,
      (delta) => {
        this.chatHistory.update((hist) =>
          hist.map((msg) =>
            msg.id === tempAiId
              ? { ...msg, message: msg.message + delta }
              : msg
          )
        );
        this.scrollToBottom();
      },
      (messageId, suggestionId) => {
        this.isSendingMessage.set(false);
        this.chatHistory.update((hist) =>
          hist.map((msg) =>
            msg.id === tempAiId ? { ...msg, id: messageId } : msg
          )
        );
        this.fetchChatAndSuggestions(); // Refresh suggestions queue
      },
      (err) => {
        this.isSendingMessage.set(false);
        this.chatHistory.update((hist) =>
          hist.map((msg) =>
            msg.id === tempAiId
              ? { ...msg, message: 'Đã có lỗi xảy ra trong quá trình kết nối với AI.' }
              : msg
          )
        );
      }
    );
  }

  // Accept / Reject AI Suggestion
  onAcceptSuggestion(suggestionId: string): void {
    if (!this.canEditTrip()) return;
    this.tripService.updateSuggestionStatus(suggestionId, 'accepted').subscribe({
      next: () => {
        // Remove suggestion from active list
        this.activeSuggestions.update((list) => list.filter((s) => s.id !== suggestionId));
        this.fetchItinerary(); // Reload itinerary to display new items
      },
      error: (err) => {
        alert(err?.error?.message || 'Có lỗi xảy ra.');
      },
    });
  }

  onRejectSuggestion(suggestionId: string): void {
    if (!this.canEditTrip()) return;
    this.tripService.updateSuggestionStatus(suggestionId, 'rejected').subscribe({
      next: () => {
        this.activeSuggestions.update((list) => list.filter((s) => s.id !== suggestionId));
      },
    });
  }

  // Manual Activities Add/Edit
  openActivityModal(dayId: string): void {
    if (!this.canEditTrip()) return;
    this.selectedDayId.set(dayId);
    this.selectedActivityId.set(null);
    this.selectedActivity.set(null);
    this.activityForm.reset({
      title: '',
      description: '',
      type: 'other',
      start_time: '',
      end_time: '',
      estimated_cost: null,
      notes: '',
    });
    this.activityError.set(null);
    this.isActivityModalOpen.set(true);
  }

  openEditActivityModal(dayId: string, activity: ActivityResponse): void {
    if (!this.canEditTrip()) return;
    this.selectedDayId.set(dayId);
    this.selectedActivityId.set(activity.id);
    this.selectedActivity.set(activity);
    this.activityForm.reset({
      title: activity.title || '',
      description: activity.description || '',
      type: (activity.type || 'other') as ActivityType,
      start_time: activity.start_time || '',
      end_time: activity.end_time || '',
      estimated_cost: activity.estimated_cost,
      notes: activity.notes || '',
    });
    this.activityError.set(null);
    this.isActivityModalOpen.set(true);
  }

  closeActivityModal(): void {
    this.isActivityModalOpen.set(false);
    this.selectedDayId.set(null);
    this.selectedActivityId.set(null);
    this.selectedActivity.set(null);
  }

  onSubmitActivity(): void {
    if (!this.canEditTrip()) return;
    if (this.activityForm.invalid) {
      this.activityForm.markAllAsTouched();
      return;
    }

    const dayId = this.selectedDayId();
    if (!dayId) return;

    this.isSubmittingActivity.set(true);
    this.activityError.set(null);

    const val = this.activityForm.getRawValue();
    const payload = {
      title: val.title,
      description: val.description || null,
      type: val.type,
      start_time: val.start_time || null,
      end_time: val.end_time || null,
      estimated_cost: val.estimated_cost,
      notes: val.notes || null,
    };

    const activityId = this.selectedActivityId();
    if (activityId) {
      this.tripService.updateActivity(activityId, payload as UpdateActivityRequest).pipe(
        timeout(15000)
      ).subscribe({
        next: () => {
          this.isSubmittingActivity.set(false);
          this.closeActivityModal();
          this.fetchItinerary();
        },
        error: (err) => {
          this.isSubmittingActivity.set(false);
          this.activityError.set(err?.error?.message || 'KhÃ´ng thá»ƒ cáº­p nháº­t hoáº¡t Ä‘á»™ng.');
        },
      });
      return;
    }

    this.tripService.addActivity(this.tripId, dayId, payload as CreateActivityRequest).pipe(
      timeout(15000)
    ).subscribe({
      next: () => {
        this.isSubmittingActivity.set(false);
        this.closeActivityModal();
        this.fetchItinerary();
      },
      error: (err) => {
        this.isSubmittingActivity.set(false);
        this.activityError.set(err?.error?.message || 'Không thể thêm hoạt động.');
      },
    });
  }

  onDeleteActivity(activityId: string): void {
    if (!this.canEditTrip()) return;
    if (!confirm('Bạn có chắc chắn muốn xóa hoạt động này?')) return;

    this.tripService.deleteActivity(activityId).subscribe({
      next: () => {
        this.fetchItinerary();
      },
      error: (err) => {
        alert(err?.error?.message || 'Có lỗi xảy ra khi xóa.');
      },
    });
  }

  // UI Helpers
  selectDayTab(idx: number): void {
    this.activeDayIndex.set(idx);
  }

  isFieldInvalid(fieldName: string): boolean {
    const field = this.activityForm.get(fieldName);
    return !!(field && field.invalid && (field.dirty || field.touched));
  }

  isGenerateFieldInvalid(fieldName: string): boolean {
    const field = this.generateOptionsForm.get(fieldName);
    return !!(field && field.invalid && (field.dirty || field.touched));
  }

  getActivityIcon(type: ActivityType | null): string {
    switch (type) {
      case 'meal': return 'restaurant';
      case 'attraction': return 'local_activity';
      case 'hotel': return 'hotel';
      case 'transport': return 'directions_car';
      default: return 'location_on';
    }
  }

  getActivityTypeLabel(type: ActivityType | null): string {
    switch (type) {
      case 'meal': return 'Ẩn thực';
      case 'attraction': return 'Tham quan';
      case 'hotel': return 'Lưu trú';
      case 'transport': return 'Di chuyển';
      default: return 'Khác';
    }
  }

  formatCurrency(value: number | null | undefined): string {
    if (value === null || value === undefined) return 'N/A';
    return `${new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(value)} VND`;
  }

  openGoogleMaps(act: ActivityResponse, event?: Event): void {
    if (event) {
      event.stopPropagation();
    }
    if (act.location?.lat && act.location?.lng) {
      const url = `https://www.google.com/maps/dir/?api=1&destination=${act.location.lat},${act.location.lng}`;
      window.open(url, '_blank');
    } else {
      const q = encodeURIComponent(act.title + (act.location?.address ? ' ' + act.location.address : ''));
      const url = `https://www.google.com/maps/search/?api=1&query=${q}`;
      window.open(url, '_blank');
    }
  }


  getTravelEstimate(currentAct: ActivityResponse, nextAct: ActivityResponse): { distanceKm: number; durationMin: number } | null {
    if (!currentAct.location?.lat || !currentAct.location?.lng || !nextAct.location?.lat || !nextAct.location?.lng) {
      return null;
    }
    const R = 6371;
    const dLat = (nextAct.location.lat - currentAct.location.lat) * (Math.PI / 180);
    const dLng = (nextAct.location.lng - currentAct.location.lng) * (Math.PI / 180);
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(currentAct.location.lat * (Math.PI / 180)) *
        Math.cos(nextAct.location.lat * (Math.PI / 180)) *
        Math.sin(dLng / 2) * Math.sin(dLng / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    const distanceKm = Math.round(R * c * 10) / 10;
    const durationMin = Math.round(distanceKm * 2.5 + 5);
    return { distanceKm, durationMin };
  }

  loadGroupSplitSummary(): void {
    if (!this.tripId) return;
    this.tripService.getGroupSplitSummary(this.tripId).subscribe({
      next: (res) => {
        if (res && res.data) {
          this.groupSplitSummary.set(res.data);
        }
      },
      error: () => {},
    });
  }



  // Budget Tracker logic
  switchSubTab(tab: 'itinerary' | 'route' | 'budget' | 'explore' | 'settings'): void {
    this.activeSubTab.set(tab);
    if (tab === 'budget') {
      this.loadBudgetData();
      this.loadGroupSplitSummary();
    } else if (tab === 'explore') {
      this.loadExploreData();
      setTimeout(() => this.initOrRefreshExploreMap(), 100);
    } else if (tab === 'route') {
      if (this.routeDayIndex() >= this.days().length) {
        this.routeDayIndex.set(0);
      }
      setTimeout(() => this.initOrRefreshRouteMap(), 100);
    } else if (tab === 'settings') {
      if (this.canManageShares()) {
        this.fetchShares();
      }
    }
  }

  loadBudgetData(): void {
    this.isLoadingBudget.set(true);
    this.budgetError.set(null);

    this.tripService.getBudgetSummary(this.tripId).subscribe({
      next: (res) => {
        if (res && res.data) {
          this.budgetSummary.set(res.data);
        }
      },
    });

    this.loadGroupSplitSummary();

    this.tripService.listBudgetItems(this.tripId).subscribe({
      next: (res) => {
        this.isLoadingBudget.set(false);
        if (res && res.data) {
          this.budgetItems.set(res.data);
        }
      },
      error: (err) => {
        this.isLoadingBudget.set(false);
        this.budgetError.set('Không thể tải dữ liệu chi tiêu.');
      },
    });
  }


  openBudgetModal(item: BudgetItemResponse | null = null): void {
    if (!this.canEditTrip()) return;
    this.selectedBudgetItem.set(item);
    this.budgetError.set(null);
    this.loadGroupSplitSummary();

    const currentUserFullName = this.currentUser()?.full_name || 'Chủ chuyến đi';

    if (item) {
      this.budgetForm.reset({
        category: item.category,
        label: item.label,
        planned_amount: item.planned_amount,
        actual_amount: item.actual_amount,
        date: item.date || '',
        paid_by: item.paid_by || currentUserFullName,
      });
    } else {
      this.budgetForm.reset({
        category: 'other',
        label: '',
        planned_amount: 0,
        actual_amount: 0,
        date: '',
        paid_by: currentUserFullName,
      });
    }

    this.isBudgetModalOpen.set(true);
  }

  closeBudgetModal(): void {
    this.isBudgetModalOpen.set(false);
    this.selectedBudgetItem.set(null);
  }

  private copyToClipboard(text: string): Promise<void> {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    } else {
      const textArea = document.createElement('textarea');
      textArea.value = text;
      textArea.style.position = 'fixed';
      textArea.style.top = '0';
      textArea.style.left = '0';
      textArea.style.opacity = '0';
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      try {
        const successful = document.execCommand('copy');
        document.body.removeChild(textArea);
        return successful ? Promise.resolve() : Promise.reject(new Error('execCommand copy failed'));
      } catch (err) {
        document.body.removeChild(textArea);
        return Promise.reject(err);
      }
    }
  }

  copySettlementMessage(): void {
    const split = this.groupSplitSummary();
    const tripData = this.trip();
    if (!split || !split.settlements || split.settlements.length === 0) return;

    let text = `💸 KẾ HOẠCH BÙ TRỪ NỢ NHÓM - ${tripData?.title || 'Chuyến đi'}\n`;
    text += `(Tổng thực chi: ${this.formatCurrency(split.total_actual)} - Bình quân: ${this.formatCurrency(split.per_person_actual)}/người)\n\n`;
    text += `👉 CÁC BƯỚC CHUYỂN TIỀN TỐI ƯU (TỐI GIẢN GIAO DỊCH):\n`;

    split.settlements.forEach((s: any, idx: number) => {
      text += `${idx + 1}. ${s.from_name} ➔ chuyển ${this.formatCurrency(s.amount)} ➔ cho ${s.to_name}\n`;
    });

    text += `\nCảm ơn mọi người! ✨`;

    this.copyToClipboard(text).then(() => {
      this.copiedSettlement.set(true);
      setTimeout(() => this.copiedSettlement.set(false), 2500);
    }).catch(err => {
      console.error('Copy error:', err);
    });
  }

  onSubmitBudgetItem(): void {
    if (!this.canEditTrip()) return;
    if (this.budgetForm.invalid) {
      this.budgetForm.markAllAsTouched();
      return;
    }

    this.isSubmittingBudget.set(true);
    this.budgetError.set(null);

    const val = this.budgetForm.getRawValue();
    const payload = {
      category: val.category,
      label: val.label,
      planned_amount: val.planned_amount,
      actual_amount: val.actual_amount,
      date: val.date || null,
      paid_by: val.paid_by || null,
    };

    const selectedItem = this.selectedBudgetItem();
    if (selectedItem) {
      this.tripService.updateBudgetItem(selectedItem.id, payload).subscribe({
        next: () => {
          this.isSubmittingBudget.set(false);
          this.closeBudgetModal();
          this.loadBudgetData();
          this.refreshTripDetails();
        },
        error: (err) => {
          this.isSubmittingBudget.set(false);
          this.budgetError.set(err?.error?.message || 'Không thể cập nhật khoản chi.');
        },
      });
    } else {
      this.tripService.addBudgetItem(this.tripId, payload).subscribe({
        next: () => {
          this.isSubmittingBudget.set(false);
          this.closeBudgetModal();
          this.loadBudgetData();
          this.refreshTripDetails();
        },
        error: (err) => {
          this.isSubmittingBudget.set(false);
          this.budgetError.set(err?.error?.message || 'Không thể thêm khoản chi.');
        },
      });
    }
  }

  onDeleteBudgetItem(itemId: string): void {
    if (!this.canEditTrip()) return;
    if (!confirm('Bạn có chắc chắn muốn xóa khoản chi này?')) return;

    this.tripService.deleteBudgetItem(itemId).subscribe({
      next: () => {
        this.loadBudgetData();
        this.refreshTripDetails();
      },
      error: (err) => {
        alert(err?.error?.message || 'Có lỗi xảy ra khi xóa.');
      },
    });
  }

  refreshTripDetails(): void {
    this.tripService.getTripDetail(this.tripId).subscribe({
      next: (res) => {
        if (res && res.data) {
          this.trip.set(res.data);
        }
      },
    });
  }

  getBudgetCategoryIcon(cat: string): string {
    switch (cat) {
      case 'food': return 'restaurant';
      case 'transport': return 'directions_car';
      case 'hotel': return 'hotel';
      case 'activity': return 'local_activity';
      default: return 'payments';
    }
  }

  getBudgetCategoryLabel(cat: string): string {
    switch (cat) {
      case 'food': return 'Ẩm thực';
      case 'transport': return 'Di chuyển';
      case 'hotel': return 'Lưu trú';
      case 'activity': return 'Tham quan';
      default: return 'Khác';
    }
  }

  getBudgetUsedPercent(): number {
    const summary = this.budgetSummary();
    if (!summary || !summary.budget_total || summary.budget_total <= 0) return 0;
    return Math.round((summary.budget_actual / summary.budget_total) * 100);
  }

  getItineraryBudgetPercent(): number {
    const summary = this.budgetSummary();
    if (!summary || !summary.budget_total || summary.budget_total <= 0) return 0;
    return Math.round((summary.budget_itinerary_planned / summary.budget_total) * 100);
  }

  getCategoryUsedPercent(cat: any): number {
    const target = cat.itinerary_planned || cat.planned || 0;
    if (target <= 0) return 0;
    return Math.min(Math.round((cat.actual / target) * 100), 100);
  }

  // ── Budget Comparison Chart Helpers ──
  getBudgetComparisonMax(): number {
    const summary = this.budgetSummary();
    if (!summary?.categories) return 1;
    let max = 0;
    for (const cat of summary.categories) {
      max = Math.max(max, cat.planned, cat.actual, cat.itinerary_planned || 0);
    }
    return max || 1;
  }

  getCategoryBarHeight(value: number): number {
    const max = this.getBudgetComparisonMax();
    return Math.round((value / max) * 100);
  }

  getCategoryVariance(cat: any): number {
    const planned = cat.itinerary_planned || cat.planned || 0;
    if (planned <= 0) return 0;
    return Math.round(((cat.actual - planned) / planned) * 100);
  }

  getCategoryDistributionPercent(cat: any): number {
    const summary = this.budgetSummary();
    const total = summary?.budget_actual || 0;
    if (total <= 0) return 0;
    return Math.round((cat.actual / total) * 100);
  }


  goBack(): void {
    this.router.navigate(['/dashboard']);
  }

  // Explore sub-tab logic
  loadExploreData(page = 1, append = false): void {
    this.isLoadingExplore.set(true);
    this.exploreError.set(null);
    const dest = this.trip()?.destination || '';
    if (!dest) {
      this.isLoadingExplore.set(false);
      this.exploreError.set('Chuyến đi chưa có điểm đến.');
      return;
    }

    this.exploreIsSearchResult.set(false);
    this.bestRatedPlaces.set([]);
    this.tripService.exploreLocations(
      dest,
      this.activeExploreCategory(),
      page,
      36
    ).subscribe({
      next: (res) => {
        this.isLoadingExplore.set(false);
        if (res && res.data) {
          const nextItems = append
            ? [...this.exploreLocations(), ...res.data.items]
            : res.data.items;
          this.exploreLocations.set(nextItems);
          this.exploreTotal.set(res.data.total);
          this.explorePage.set(res.data.page);
          this.exploreHasMore.set(res.data.has_more);
          setTimeout(() => this.renderMapMarkers(), 50);
        }
      },
      error: () => {
        this.isLoadingExplore.set(false);
        this.exploreError.set('Không thể tải địa điểm từ bộ dữ liệu.');
      },
    });
  }

  onExploreCategoryChange(category: 'attraction' | 'meal' | 'hotel' | 'cafe'): void {
    this.activeExploreCategory.set(category);
    this.exploreQuery.set('');
    this.loadExploreData(1, false);
  }

  onExploreSearch(): void {
    const q = this.exploreQuery().trim();
    if (!q) {
      this.loadExploreData();
      return;
    }

    this.isLoadingExplore.set(true);
    this.exploreError.set(null);
    this.exploreIsSearchResult.set(true);
    this.exploreHasMore.set(false);

    const dest = this.trip()?.destination || '';
    this.tripService.searchLocations(
      q,
      dest,
      40,
      this.activeExploreCategory(),
      true
    ).subscribe({
      next: (res) => {
        this.isLoadingExplore.set(false);
        if (res && res.data) {
          this.exploreLocations.set(res.data);
          this.exploreTotal.set(res.data.length);
          setTimeout(() => this.renderMapMarkers(), 50);
        }
      },
      error: () => {
        this.isLoadingExplore.set(false);
        this.exploreError.set('Tìm kiếm thất bại. Vui lòng thử lại.');
      },
    });

    this.loadBestRatedPlaces(q);
  }

  loadMoreExplore(): void {
    if (this.isLoadingExplore() || !this.exploreHasMore() || this.exploreIsSearchResult()) {
      return;
    }
    this.loadExploreData(this.explorePage() + 1, true);
  }

  loadBestRatedPlaces(term: string): void {
    const dest = this.trip()?.destination || '';
    if (!dest) return;
    const query = `${term} ${dest}`.trim();
    this.isLoadingBestRated.set(true);
    this.placePhotoService.getBestRatedPlaces(query, 5).subscribe({
      next: (places) => {
        this.isLoadingBestRated.set(false);
        this.bestRatedPlaces.set(places);
      },
      error: () => {
        this.isLoadingBestRated.set(false);
        this.bestRatedPlaces.set([]);
      }
    });
  }

  searchForBestRatedPlace(name: string): void {
    this.exploreQuery.set(name);
    this.onExploreSearch();
  }

  focusOnMap(lat: number | null | undefined, lng: number | null | undefined, name: string): void {
    if (!lat || !lng || !this.exploreMap) return;

    // Pan and zoom to coordinates
    this.exploreMap.setView([lat, lng], 17, { animate: true });

    // Find and open popup for matching marker
    const marker = this.mapMarkers.find(m => {
      const pos = m.getLatLng();
      return Math.abs(pos.lat - lat) < 0.0001 && Math.abs(pos.lng - lng) < 0.0001;
    });

    if (marker) {
      setTimeout(() => marker.openPopup(), 300);
    }

    // Scroll smoothly to map container
    const container = document.getElementById('explore-map');
    if (container) {
      container.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  openAddActivityFromExplore(location: LocationResponse): void {
    if (!this.canEditTrip()) return;
    this.selectedExploreLocation.set(location);
    const daysList = this.days();
    const activeDay = daysList[this.activeDayIndex()] || daysList[0];
    this.selectedExploreDayId.set(activeDay ? activeDay.id : '');
    this.exploreStartTime.set('');
    this.exploreEndTime.set('');
    this.isAddActivityFromExploreOpen.set(true);
  }

  closeAddActivityFromExplore(): void {
    this.isAddActivityFromExploreOpen.set(false);
    this.selectedExploreLocation.set(null);
    this.selectedExploreDayId.set('');
    this.exploreStartTime.set('');
    this.exploreEndTime.set('');
  }

  isValidTime24h(val: string | null | undefined): boolean {
    if (!val) return true;
    return /^([01]\d|2[0-3]):[0-5]\d$/.test(val);
  }

  formatTime24h(raw: string): string {
    if (!raw) return '';
    const digits = raw.replace(/\D/g, '');
    if (digits.length === 0) return '';

    let h1 = digits[0];
    let h2 = '';
    let mStartIdx = 2;

    if (parseInt(h1, 10) > 2) {
      h2 = h1;
      h1 = '0';
      mStartIdx = 1;
    } else if (digits.length >= 2) {
      h2 = digits[1];
      if (h1 === '2' && parseInt(h2, 10) > 3) {
        h2 = '3';
      }
    }

    const hours = h1 + h2;
    if (hours.length < 2) {
      return hours;
    }

    const mDigits = digits.slice(mStartIdx);
    if (mDigits.length === 0) {
      return `${hours}:`;
    }

    let m1 = mDigits[0];
    if (parseInt(m1, 10) > 5) {
      m1 = '5';
    }

    const m2 = mDigits.length > 1 ? mDigits[1] : '';

    return `${hours}:${m1}${m2}`.slice(0, 5);
  }

  onExploreTimeInput(event: Event, type: 'start' | 'end'): void {
    const input = event.target as HTMLInputElement;
    const inputEvent = event as InputEvent;
    let raw = input.value;

    if (inputEvent.inputType === 'deleteContentBackward' && raw.endsWith(':')) {
      raw = raw.slice(0, -1);
    }

    const masked = this.formatTime24h(raw);
    input.value = masked;
    if (type === 'start') {
      this.exploreStartTime.set(masked);
    } else {
      this.exploreEndTime.set(masked);
    }
  }

  onExploreTimeBlur(event: Event, type: 'start' | 'end'): void {
    const input = event.target as HTMLInputElement;
    let val = input.value?.trim();
    if (!val) return;

    if (val.endsWith(':')) val += '00';
    else if (/^\d{2}:\d{1}$/.test(val)) val += '0';

    if (this.isValidTime24h(val)) {
      input.value = val;
      if (type === 'start') {
        this.exploreStartTime.set(val);
      } else {
        this.exploreEndTime.set(val);
      }
    }
  }

  onTimeInputControl(event: Event, formGroup: 'activityForm' | 'generateOptionsForm', fieldName: string): void {
    const input = event.target as HTMLInputElement;
    const inputEvent = event as InputEvent;
    let raw = input.value;

    if (inputEvent.inputType === 'deleteContentBackward' && raw.endsWith(':')) {
      raw = raw.slice(0, -1);
    }

    const masked = this.formatTime24h(raw);
    input.value = masked;

    if (formGroup === 'activityForm') {
      this.activityForm.get(fieldName)?.setValue(masked, { emitEvent: true });
    } else if (formGroup === 'generateOptionsForm') {
      this.generateOptionsForm.get(fieldName)?.setValue(masked, { emitEvent: true });
    }
  }

  normalizeTimeOnBlur(event: Event, formGroup: 'activityForm' | 'generateOptionsForm', fieldName: string): void {
    const input = event.target as HTMLInputElement;
    let val = input.value?.trim();
    if (!val) return;

    if (val.endsWith(':')) val += '00';
    else if (/^\d{2}:\d{1}$/.test(val)) val += '0';

    if (this.isValidTime24h(val)) {
      input.value = val;
      if (formGroup === 'activityForm') {
        this.activityForm.get(fieldName)?.setValue(val);
      } else if (formGroup === 'generateOptionsForm') {
        this.generateOptionsForm.get(fieldName)?.setValue(val);
      }
    }
  }

  confirmAddActivityFromExplore(targetDayId?: string): void {
    if (!this.canEditTrip()) return;
    const dayId = targetDayId || this.selectedExploreDayId();
    if (!dayId) return;

    const loc = this.selectedExploreLocation();
    if (!loc) return;

    let startTime = this.exploreStartTime();
    let endTime = this.exploreEndTime();

    if (startTime) {
      if (startTime.endsWith(':')) startTime += '00';
      else if (/^\d{2}:\d{1}$/.test(startTime)) startTime += '0';
      if (!this.isValidTime24h(startTime)) {
        alert('Giờ bắt đầu không hợp lệ (định dạng 24h từ 00:00 đến 23:59).');
        return;
      }
    }

    if (endTime) {
      if (endTime.endsWith(':')) endTime += '00';
      else if (/^\d{2}:\d{1}$/.test(endTime)) endTime += '0';
      if (!this.isValidTime24h(endTime)) {
        alert('Giờ kết thúc không hợp lệ (định dạng 24h từ 00:00 đến 23:59).');
        return;
      }
    }

    this.isSubmittingExploreActivity.set(true);

    let catVal: LocationCategory = 'other';
    const cat = loc.category?.toLowerCase() || '';
    if (cat.includes('restaurant') || cat.includes('food')) catVal = 'restaurant';
    else if (cat.includes('hotel') || cat.includes('motel') || cat.includes('guest')) catVal = 'hotel';
    else if (cat.includes('cafe') || cat.includes('bar')) catVal = 'cafe';
    else if (cat.includes('attraction') || cat.includes('tourism') || cat.includes('museum')) catVal = 'attraction';

    const executeAddActivity = (locationId: string) => {
      let actType: ActivityType = 'other';
      if (catVal === 'restaurant' || catVal === 'cafe') actType = 'meal';
      else if (catVal === 'hotel') actType = 'hotel';
      else if (catVal === 'attraction') actType = 'attraction';

      const createActivityPayload = {
        title: loc.name,
        description: loc.address || '',
        type: actType,
        location_id: locationId,
        start_time: startTime || null,
        end_time: endTime || null,
        estimated_cost: null,
        notes: 'Thêm từ tab Khám phá',
      };

      this.tripService.addActivity(this.tripId, dayId, createActivityPayload).subscribe({
        next: () => {
          this.isSubmittingExploreActivity.set(false);
          this.closeAddActivityFromExplore();
          this.fetchItinerary();
          alert(`Đã thêm "${loc.name}" vào lịch trình của bạn!`);
        },
        error: (err) => {
          this.isSubmittingExploreActivity.set(false);
          alert(err?.error?.message || 'Không thể thêm hoạt động vào lịch trình.');
        }
      });
    };

    if (loc.id) {
      executeAddActivity(loc.id);
      return;
    }

    const validPhotoUrl = (loc.photo_url && (loc.photo_url.startsWith('http://') || loc.photo_url.startsWith('https://')))
      ? loc.photo_url
      : null;

    const upsertPayload = {
      name: loc.name,
      address: loc.address,
      lat: loc.lat,
      lng: loc.lng,
      category: catVal,
      google_place_id: loc.google_place_id,
      photo_url: validPhotoUrl,
      rating: loc.rating,
    };

    this.tripService.upsertLocation(upsertPayload).subscribe({
      next: (upsertRes) => {
        executeAddActivity(upsertRes.data.id);
      },
      error: (err) => {
        if (loc.id) {
          executeAddActivity(loc.id);
        } else {
          this.isSubmittingExploreActivity.set(false);
          alert(err?.error?.message || 'Không thể lưu thông tin địa điểm.');
        }
      }
    });
  }

  private scrollToBottom(): void {
    setTimeout(() => {
      const container = document.getElementById('chat-body');
      if (container) {
        container.scrollTop = container.scrollHeight;
      }
    }, 100);
  }

  // Save modified Trip Settings
  onSaveSettings(isAutosave = false): void {
    if (!this.canManageShares()) return;
    if (this.settingsForm.invalid || this.isSavingSettings()) return;

    const val = this.settingsForm.getRawValue();
    if (new Date(val.end_date) < new Date(val.start_date)) {
      this.settingsErrorMsg.set('Ngày kết thúc không được nhỏ hơn ngày bắt đầu.');
      return;
    }

    this.isSavingSettings.set(true);
    this.settingsSaveState.set('saving');
    this.settingsSuccessMsg.set(null);
    this.settingsErrorMsg.set(null);

    const rawBudget = val.budget ? Number(val.budget.toString().replace(/\./g, '')) : null;
    const startIso = this.formatDdMmYyyyToIso(val.start_date);
    const endIso = this.formatDdMmYyyyToIso(val.end_date);
    const payload = {
      title: val.title,
      destination: val.destination,
      start_date: startIso,
      end_date: endIso,
      budget: isNaN(rawBudget as any) ? null : rawBudget,
      num_travelers: val.num_travelers,
      status: val.status,
    };

    this.tripService.updateTrip(this.tripId, payload).subscribe({
      next: (res) => {
        this.isSavingSettings.set(false);
        this.settingsSaveState.set('saved');
        if (res && res.data) {
          this.trip.set(res.data);
          this.settingsForm.markAsPristine();
          this.settingsSuccessMsg.set('Đã lưu cài đặt chuyến đi thành công!');
          this.fetchItinerary(); // reload list of days in case dates were modified
          setTimeout(() => this.settingsSuccessMsg.set(null), 3000);
          if (isAutosave) this.settingsSuccessMsg.set(null);
        }
      },
      error: (err) => {
        this.isSavingSettings.set(false);
        this.settingsSaveState.set('error');
        this.settingsErrorMsg.set(err?.error?.message || 'Có lỗi xảy ra khi cập nhật cài đặt.');
      },
    });
  }

  // Restore Settings Form values to current trip state
  onResetSettings(): void {
    const t = this.trip();
    if (t) {
      this.settingsForm.patchValue({
        title: t.title,
        destination: t.destination,
        start_date: this.formatIsoToDdMmYyyy(t.start_date),
        end_date: this.formatIsoToDdMmYyyy(t.end_date),
        budget: this.formatNumberWithDots(t.budget),
        num_travelers: t.num_travelers,
        status: t.status,
      });
    }
    this.settingsErrorMsg.set(null);
    this.settingsSuccessMsg.set(null);
    this.settingsForm.markAsPristine();
    this.settingsSaveState.set('idle');
  }

  // Delete Trip actions
  onOpenDeleteModal(): void {
    if (!this.canManageShares()) return;
    this.isDeleteModalOpen.set(true);
  }

  onCloseDeleteModal(): void {
    this.isDeleteModalOpen.set(false);
  }

  onConfirmDeleteTrip(): void {
    if (!this.canManageShares()) return;
    this.isDeleting.set(true);
    this.tripService.deleteTrip(this.tripId).subscribe({
      next: () => {
        this.isDeleting.set(false);
        this.isDeleteModalOpen.set(false);
        this.router.navigate(['/dashboard']);
      },
      error: (err) => {
        this.isDeleting.set(false);
        alert(err?.error?.message || 'Có lỗi xảy ra khi xóa chuyến đi.');
      },
    });
  }

  // Initialize or redraw Leaflet Map
  initOrRefreshExploreMap(retryCount = 0): void {
    if (this.activeSubTab() !== 'explore') return;

    const container = document.getElementById('explore-map');
    if (!container) {
      if (retryCount < 10) {
        setTimeout(() => this.initOrRefreshExploreMap(retryCount + 1), 100);
      }
      return;
    }

    if (this.exploreMap) {
      try {
        this.exploreMap.remove();
      } catch (e) {
        console.warn('Error removing old explore map:', e);
      }
      this.exploreMap = null;
    }

    // Find a center coordinate based on loaded explore list, otherwise default to trip destination coordinates
    let centerCoords = this.getCoordinatesForDestination(this.trip()?.destination);
    const valid = this.exploreLocations().filter(loc => loc.lat !== null && loc.lng !== null);
    if (valid.length > 0) {
      centerCoords = [valid[0].lat as number, valid[0].lng as number];
    }

    this.exploreMap = L.map('explore-map').setView(centerCoords, 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap contributors'
    }).addTo(this.exploreMap);

    // Always delay size validation slightly to ensure CSS flexbox layout calculations are complete
    setTimeout(() => {
      if (this.exploreMap) {
        this.exploreMap.invalidateSize();
        this.renderMapMarkers();
      }
    }, 250);
  }

  // Render locations array as custom Leaflet markers
  renderMapMarkers(): void {
    if (!this.exploreMap) {
      this.initOrRefreshExploreMap();
      return;
    }

    // Clear active markers
    this.mapMarkers.forEach(m => m.remove());
    this.mapMarkers = [];

    const locations = this.exploreLocations();
    const validCoords: any[] = [];

    locations.forEach(loc => {
      if (loc.lat === null || loc.lng === null) return;

      const lat = loc.lat;
      const lng = loc.lng;
      validCoords.push([lat, lng]);

      // Styled custom marker DivIcon
      const iconName = this.getExploreCategoryIcon(loc.category);
      const markerElement = document.createElement('div');
      markerElement.className = 'custom-map-pin';
      markerElement.title = loc.name;
      const markerIcon = document.createElement('span');
      markerIcon.className = 'material-symbols-outlined pin-emoji text-primary';
      markerIcon.style.fontSize = '18px';
      markerIcon.textContent = iconName;
      markerElement.appendChild(markerIcon);
      const customIcon = L.divIcon({
        html: markerElement,
        className: 'custom-leaflet-pin',
        iconSize: [36, 36],
        iconAnchor: [18, 36],
        popupAnchor: [0, -32]
      });

      // Marker instantiation
      const marker = L.marker([lat, lng], { icon: customIcon }).addTo(this.exploreMap);
      this.mapMarkers.push(marker);

      // Popup structure
      const popupContent = document.createElement('div');
      popupContent.className = 'custom-map-popup';
      popupContent.style.width = '200px';
      const popupTitle = document.createElement('div');
      popupTitle.className = 'popup-title';
      popupTitle.style.cssText =
        'font-weight:700;font-size:14px;margin-bottom:4px;color:#222;text-overflow:ellipsis;overflow:hidden;white-space:nowrap';
      popupTitle.textContent = loc.name;

      const popupAddress = document.createElement('div');
      popupAddress.className = 'popup-address';
      popupAddress.style.cssText =
        'font-size:12px;color:#6a6a6a;margin-bottom:8px;line-height:1.3;text-overflow:ellipsis;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;max-height:32px';
      popupAddress.textContent = loc.address || '';

      const popupButton = document.createElement('button');
      popupButton.type = 'button';
      popupButton.className = 'popup-btn-add';
      popupButton.style.cssText =
        'background-color:#3b82f6;color:white;border:none;padding:8px 12px;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;width:100%;text-align:center;box-sizing:border-box;transition:background-color .2s';
      popupButton.textContent = 'Thêm vào lịch trình';
      popupContent.append(popupTitle, popupAddress, popupButton);

      // Popup Action bind
      popupButton.addEventListener('click', () => {
        this.openAddActivityFromExplore(loc);
      });

      marker.bindPopup(popupContent);
    });

    // Auto fit map bounds
    if (validCoords.length > 0) {
      this.exploreMap.fitBounds(validCoords, { padding: [40, 40] });
    }
  }

  // Initialize or redraw Route Leaflet Map
  initOrRefreshRouteMap(retryCount = 0): void {
    if (this.activeSubTab() !== 'route') return;

    const container = document.getElementById('route-map');
    if (!container) {
      if (retryCount < 10) {
        setTimeout(() => this.initOrRefreshRouteMap(retryCount + 1), 100);
      }
      return;
    }

    if (this.routeMap) {
      try {
        this.routeMap.remove();
      } catch (e) {
        console.warn('Error removing old route map:', e);
      }
      this.routeMap = null;
    }

    // Default to trip destination coordinates
    let centerCoords = this.getCoordinatesForDestination(this.trip()?.destination);
    
    this.routeMap = L.map('route-map').setView(centerCoords, 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap contributors'
    }).addTo(this.routeMap);

    setTimeout(() => {
      if (this.routeMap) {
        this.routeMap.invalidateSize();
        this.renderRouteForDay(this.routeDayIndex());
      }
    }, 250);
  }

  selectRouteDay(idx: number): void {
    this.routeDayIndex.set(idx);
    this.renderRouteForDay(idx);
  }

  clearRouteLayers(): void {
    this.routeMarkers.forEach(m => m.remove());
    this.routeMarkers = [];
    this.routePolylines.forEach(p => p.remove());
    this.routePolylines = [];
  }

  renderRouteForDay(dayIndex: number): void {
    if (!this.routeMap) return;
    this.clearRouteLayers();

    const day = this.days()[dayIndex];
    if (!day) return;

    // Filter activities with valid coords
    const validActivities = day.activities.filter(act => act.location && act.location.lat !== null && act.location.lng !== null);
    
    if (validActivities.length === 0) {
      this.routeSegments.set([]);
      this.routeTotalDistance.set(0);
      this.routeTotalDuration.set(0);
      return;
    }

    const coords = validActivities.map(act => [act.location!.lat, act.location!.lng] as [number, number]);

    if (validActivities.length === 1) {
      this.routeSegments.set([]);
      this.routeTotalDistance.set(0);
      this.routeTotalDuration.set(0);
      
      const act = validActivities[0];
      const lat = act.location!.lat!;
      const lng = act.location!.lng!;
      
      // Draw single marker
      let markerColor = '#3b82f6';
      if (act.type === 'meal') markerColor = '#f59e0b';
      else if (act.type === 'attraction') markerColor = '#3b82f6';
      else if (act.type === 'hotel') markerColor = '#a855f7';
      else if (act.type === 'transport') markerColor = '#14b8a6';

      const markerHtml = `<div class="custom-map-pin-route text-white font-bold" style="background-color: ${markerColor}; display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 50%; border: 2px solid white; box-shadow: 0 2px 5px rgba(0,0,0,0.5);">1</div>`;
      const customIcon = L.divIcon({
        html: markerHtml,
        className: 'custom-leaflet-route-pin',
        iconSize: [32, 32],
        iconAnchor: [16, 16],
        popupAnchor: [0, -16]
      });

      const marker = L.marker([lat, lng], { icon: customIcon }).addTo(this.routeMap);
      marker.bindPopup(`<div style="font-weight:bold; font-size:14px; color:#1e293b;">${this.escapeLeafletText(act.title)}</div><div style="font-size:12px; color:#4b5563;">${this.escapeLeafletText(act.location!.name)}</div>`);
      this.routeMarkers.push(marker);

      this.routeMap.setView([lat, lng], 14);
      return;
    }

    this.isLoadingRoute.set(true);
    this.osrmService.getRoute(coords).subscribe({
      next: (res) => {
        this.isLoadingRoute.set(false);
        if (!res) return;

        this.routeTotalDistance.set(res.totalDistanceMeters / 1000);
        this.routeTotalDuration.set(res.totalDurationSeconds / 60);

        const segments: RouteSegment[] = [];
        const fitCoords: [number, number][] = [];

        res.segments.forEach((seg, i) => {
          const fromAct = validActivities[i];
          const toAct = validActivities[i + 1];

          segments.push({
            fromName: fromAct.title,
            fromType: fromAct.type,
            toName: toAct.title,
            toType: toAct.type,
            distanceKm: seg.distanceMeters / 1000,
            durationMin: seg.durationSeconds / 60,
            coords: seg.geometryCoords
          });

          // Draw segment polyline
          const polyline = L.polyline(seg.geometryCoords, {
            color: '#3b82f6',
            weight: 4,
            opacity: 0.85,
            dashArray: '10 6',
            lineCap: 'round',
            lineJoin: 'round',
            className: 'route-polyline-animated'
          }).addTo(this.routeMap);

          // Tooltip on segment polyline
          polyline.bindTooltip(
            `Đoạn ${i + 1}: ${(seg.distanceMeters / 1000).toFixed(1)} km (~${Math.round(seg.durationSeconds / 60)} phút)`,
            { sticky: true, className: 'custom-polyline-tooltip' }
          );

          this.routePolylines.push(polyline);
          seg.geometryCoords.forEach(c => fitCoords.push(c));
        });

        this.routeSegments.set(segments);

        // Draw numbered markers for all valid activities
        validActivities.forEach((act, idx) => {
          const lat = act.location!.lat!;
          const lng = act.location!.lng!;
          
          let markerColor = '#3b82f6'; // Default primary blue
          if (act.type === 'meal') markerColor = '#f59e0b';
          else if (act.type === 'attraction') markerColor = '#3b82f6';
          else if (act.type === 'hotel') markerColor = '#a855f7';
          else if (act.type === 'transport') markerColor = '#14b8a6';

          const markerHtml = `<div class="custom-map-pin-route text-white font-bold" style="background-color: ${markerColor}; display: flex; align-items: center; justify-content: center; width: 30px; height: 30px; border-radius: 50%; border: 2px solid white; box-shadow: 0 2px 5px rgba(0,0,0,0.5);">${idx + 1}</div>`;
          const customIcon = L.divIcon({
            html: markerHtml,
            className: 'custom-leaflet-route-pin',
            iconSize: [30, 30],
            iconAnchor: [15, 15],
            popupAnchor: [0, -15]
          });

          const marker = L.marker([lat, lng], { icon: customIcon }).addTo(this.routeMap);
          
          const popupContent = `
            <div style="padding: 4px;">
              <div style="font-weight: 700; font-size: 14px; margin-bottom: 2px; color: var(--color-on-surface, #e2e8f1);">#${idx + 1} - ${this.escapeLeafletText(act.title)}</div>
              <div style="font-size: 12px; color: var(--color-on-surface-variant, #94a3b8);">${this.escapeLeafletText(act.location?.name || '')}</div>
              ${act.start_time ? `<div style="font-size: 11px; margin-top: 4px; color: #4f46e5;">🕒 ${act.start_time}</div>` : ''}
            </div>
          `;
          marker.bindPopup(popupContent);
          this.routeMarkers.push(marker);
        });

        // Fit map bounds
        if (fitCoords.length > 0) {
          this.routeMap.fitBounds(fitCoords, { padding: [50, 50] });
        }
      },
      error: () => {
        this.isLoadingRoute.set(false);
      }
    });
  }

  private escapeLeafletText(value: string): string {
    const replacements: Record<string, string> = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    };
    return value.replace(/[&<>"']/g, (character) => replacements[character]);
  }

  zoomToSegment(coords: [number, number][]): void {
    if (!this.routeMap || !coords || coords.length === 0) return;
    this.routeMap.fitBounds(coords, { padding: [40, 40], maxZoom: 16 });
  }

  // Helper category mapping to icons
  getExploreCategoryIcon(category: string | null | undefined): string {
    if (!category) return 'location_on';
    const cat = category.toLowerCase().trim();
    if (cat.includes('meal') || cat.includes('restaurant') || cat.includes('food') || cat.includes('dining')) return 'restaurant';
    if (cat.includes('attraction') || cat.includes('sightseeing') || cat.includes('tourist')) return 'local_activity';
    if (cat.includes('hotel') || cat.includes('accommodation') || cat.includes('lodging') || cat.includes('resort')) return 'hotel';
    if (cat.includes('cafe') || cat.includes('coffee') || cat.includes('tea')) return 'local_cafe';
    return 'location_on';
  }

  onBudgetInputChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    let value = input.value;
    let raw = value.replace(/\D/g, '');
    if (raw) {
      const num = Number(raw);
      const formatted = num.toLocaleString('en-US');
      input.value = formatted;
      this.settingsForm.get('budget')?.setValue(formatted, { emitEvent: false });
    } else {
      input.value = '';
      this.settingsForm.get('budget')?.setValue('', { emitEvent: false });
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
    this.settingsForm.get(controlName)?.setValue(value, { emitEvent: false });
  }

  onNativeDateChange(event: Event, controlName: string): void {
    const picker = event.target as HTMLInputElement;
    const value = picker.value;
    if (value) {
      const formatted = this.formatIsoToDdMmYyyy(value);
      this.settingsForm.get(controlName)?.setValue(formatted);
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

  // Helper to return beautiful covers matching Airbnb photo-first rule
  getTripImage(destination: string | undefined): string {
    const dest = destination?.toLowerCase().trim() || '';
    const list = dest ? this.destinationImagesMap().get(dest) || [] : [];
    return resolveTravelCoverImage(destination, this.tripId || destination, list);
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
      img.src = GENERIC_TRAVEL_FALLBACK_IMAGES[attempts];
      return;
    }

    img.onerror = null;
    img.src = this.svgFallback;
  }

  readonly activeTravelStyleTags = signal<string[]>(['Nghỉ dưỡng']);

  toggleTravelStyleTag(tag: string): void {
    const current = this.activeTravelStyleTags();
    if (current.includes(tag)) {
      if (current.length > 1) {
        this.activeTravelStyleTags.set(current.filter((t) => t !== tag));
      }
    } else {
      this.activeTravelStyleTags.set([...current, tag]);
    }
  }

  isTravelStyleActive(tag: string): boolean {
    return this.activeTravelStyleTags().includes(tag);
  }

  incrementTravelers(): void {
    const current = Number(this.settingsForm.get('num_travelers')?.value || 1);
    this.settingsForm.get('num_travelers')?.setValue(current + 1);
  }

  decrementTravelers(): void {
    const current = Number(this.settingsForm.get('num_travelers')?.value || 1);
    if (current > 1) {
      this.settingsForm.get('num_travelers')?.setValue(current - 1);
    }
  }

  onUnpublishFromCommunity(): void {
    if (!this.tripId) return;
    this.publicTripService.archive(this.tripId).subscribe({
      next: () => {
        this.publishedPublicSlug.set(null);
        this.settingsSuccessMsg.set('Đã gỡ lịch trình khỏi Cộng đồng.');
        setTimeout(() => this.settingsSuccessMsg.set(null), 3000);
      },
      error: (err: any) => {
        this.settingsErrorMsg.set(err?.error?.message || 'Không thể gỡ lịch trình khỏi Cộng đồng.');
      },
    });
  }
}
