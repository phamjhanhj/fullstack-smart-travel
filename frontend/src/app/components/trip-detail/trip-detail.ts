declare const L: any;

import { Component, HostListener, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormsModule, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { DragDropModule, CdkDragDrop, moveItemInArray } from '@angular/cdk/drag-drop';
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
    DragDropModule,
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
  readonly isChatOpen = signal<boolean>(true);
  readonly activeRightTab = signal<'chat' | 'history'>('chat');

  // Sub-tabs switcher state
  readonly activeSubTab = signal<'itinerary' | 'route' | 'budget' | 'explore' | 'settings'>('itinerary');

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
  readonly optimizingDayId = signal<string | null>(null);

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

    const escapeXml = (str: string | number | null | undefined): string => {
      if (str == null) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&apos;');
    };

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

    let xml = `<?xml version="1.0" encoding="UTF-8"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-microsoft-com:office:spreadsheet"
  xmlns:o="urn:schemas-microsoft-microsoft-com:office:office"
  xmlns:x="urn:schemas-microsoft-microsoft-com:office:excel"
  xmlns:ss="urn:schemas-microsoft-microsoft-com:office:spreadsheet">
  <Styles>
    <Style ss:ID="Header">
      <Font ss:Bold="1" ss:Color="#FFFFFF" ss:FontName="Arial" ss:Size="11"/>
      <Interior ss:Color="#2563EB" ss:Pattern="Solid"/>
      <Alignment ss:Horizontal="Center" ss:Vertical="Center"/>
      <Borders>
        <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#1D4ED8"/>
      </Borders>
    </Style>
    <Style ss:ID="Title">
      <Font ss:Bold="1" ss:Size="16" ss:Color="#1E293B" ss:FontName="Arial"/>
    </Style>
    <Style ss:ID="SubTitle">
      <Font ss:Bold="1" ss:Size="12" ss:Color="#2563EB" ss:FontName="Arial"/>
    </Style>
    <Style ss:ID="MetaLabel">
      <Font ss:Bold="1" ss:Color="#475569" ss:FontName="Arial" ss:Size="10"/>
    </Style>
    <Style ss:ID="Bold">
      <Font ss:Bold="1" ss:FontName="Arial" ss:Size="10"/>
    </Style>
    <Style ss:ID="Number">
      <NumberFormat ss:Format="#,##0"/>
      <Font ss:FontName="Arial" ss:Size="10"/>
      <Alignment ss:Horizontal="Right"/>
    </Style>
    <Style ss:ID="TotalNumber">
      <NumberFormat ss:Format="#,##0"/>
      <Font ss:Bold="1" ss:Color="#1E293B" ss:FontName="Arial" ss:Size="11"/>
      <Interior ss:Color="#FEF08A" ss:Pattern="Solid"/>
      <Alignment ss:Horizontal="Right"/>
    </Style>
    <Style ss:ID="TotalLabel">
      <Font ss:Bold="1" ss:Color="#1E293B" ss:FontName="Arial" ss:Size="11"/>
      <Interior ss:Color="#FEF08A" ss:Pattern="Solid"/>
    </Style>
    <Style ss:ID="Normal">
      <Font ss:FontName="Arial" ss:Size="10"/>
    </Style>
  </Styles>`;

    // --- TAB 1: TỔNG QUAN ---
    xml += `
  <Worksheet ss:Name="Tổng quan">
    <Table>
      <Column ss:Width="180"/>
      <Column ss:Width="350"/>
      <Row ss:Height="25">
        <Cell ss:StyleID="Title"><Data ss:Type="String">THÔNG TIN CHUYẾN ĐỊ</Data></Cell>
      </Row>
      <Row><Cell ss:StyleID="MetaLabel"><Data ss:Type="String">Tên chuyến đi:</Data></Cell><Cell ss:StyleID="Bold"><Data ss:Type="String">${escapeXml(tripData.title)}</Data></Cell></Row>
      <Row><Cell ss:StyleID="MetaLabel"><Data ss:Type="String">Điểm đến:</Data></Cell><Cell ss:StyleID="Normal"><Data ss:Type="String">${escapeXml(tripData.destination)}</Data></Cell></Row>
      <Row><Cell ss:StyleID="MetaLabel"><Data ss:Type="String">Thời gian:</Data></Cell><Cell ss:StyleID="Normal"><Data ss:Type="String">${escapeXml(tripData.start_date)} đến ${escapeXml(tripData.end_date)}</Data></Cell></Row>
      <Row><Cell ss:StyleID="MetaLabel"><Data ss:Type="String">Số ngày:</Data></Cell><Cell ss:StyleID="Normal"><Data ss:Type="Number">${daysData.length}</Data></Cell></Row>
      <Row><Cell ss:StyleID="MetaLabel"><Data ss:Type="String">Số người đồng hành:</Data></Cell><Cell ss:StyleID="Normal"><Data ss:Type="Number">${tripData.num_travelers || 1}</Data></Cell></Row>
      <Row><Cell ss:StyleID="MetaLabel"><Data ss:Type="String">Ngân sách dự kiến:</Data></Cell><Cell ss:StyleID="Number"><Data ss:Type="Number">${tripData.budget || 0}</Data></Cell></Row>
      <Row><Cell ss:StyleID="MetaLabel"><Data ss:Type="String">Ghi chú / Sở thích:</Data></Cell><Cell ss:StyleID="Normal"><Data ss:Type="String">${escapeXml(tripData.preferences || 'Không')}</Data></Cell></Row>
    </Table>
  </Worksheet>`;

    // --- TAB 2..N: TỪNG NGÀY ---
    let totalTripCost = 0;

    daysData.forEach((day) => {
      const sheetName = `Ngày ${day.day_number}`;
      const activities = day.activities || [];
      let dayTotalCost = 0;

      xml += `
  <Worksheet ss:Name="${escapeXml(sheetName)}">
    <Table>
      <Column ss:Width="100"/>
      <Column ss:Width="260"/>
      <Column ss:Width="120"/>
      <Column ss:Width="130"/>
      <Column ss:Width="380"/>
      
      <Row ss:Height="24">
        <Cell ss:StyleID="SubTitle"><Data ss:Type="String">LỊCH TRÌNH NGÀY ${day.day_number}${day.date ? ' (' + escapeXml(day.date) + ')' : ''}</Data></Cell>
      </Row>
      
      <Row ss:Height="22">
        <Cell ss:StyleID="Header"><Data ss:Type="String">Giờ</Data></Cell>
        <Cell ss:StyleID="Header"><Data ss:Type="String">Hoạt động / Địa điểm</Data></Cell>
        <Cell ss:StyleID="Header"><Data ss:Type="String">Loại</Data></Cell>
        <Cell ss:StyleID="Header"><Data ss:Type="String">Chi phí (VNĐ)</Data></Cell>
        <Cell ss:StyleID="Header"><Data ss:Type="String">Chi tiết / Địa chỉ &amp; Ghi chú</Data></Cell>
      </Row>`;

      activities.forEach((act) => {
        const cost = Number(act.estimated_cost || 0);
        dayTotalCost += cost;
        totalTripCost += cost;

        const timeStr = act.start_time
          ? act.end_time
            ? `${act.start_time} - ${act.end_time}`
            : act.start_time
          : '—';

        const detailNote = [act.description || '', act.location?.address || act.notes || '']
          .filter(Boolean)
          .join(' | ');

        xml += `
      <Row>
        <Cell ss:StyleID="Normal"><Data ss:Type="String">${escapeXml(timeStr)}</Data></Cell>
        <Cell ss:StyleID="Bold"><Data ss:Type="String">${escapeXml(act.title || 'Hoạt động')}</Data></Cell>
        <Cell ss:StyleID="Normal"><Data ss:Type="String">${escapeXml(formatActivityType(act.type))}</Data></Cell>
        <Cell ss:StyleID="Number"><Data ss:Type="Number">${cost}</Data></Cell>
        <Cell ss:StyleID="Normal"><Data ss:Type="String">${escapeXml(detailNote)}</Data></Cell>
      </Row>`;
      });

      // Total Row for Day
      xml += `
      <Row ss:Height="20">
        <Cell ss:StyleID="TotalLabel"><Data ss:Type="String">TỔNG CỘNG NGÀY ${day.day_number}</Data></Cell>
        <Cell ss:StyleID="TotalLabel"/>
        <Cell ss:StyleID="TotalLabel"/>
        <Cell ss:StyleID="TotalNumber"><Data ss:Type="Number">${dayTotalCost}</Data></Cell>
        <Cell ss:StyleID="TotalLabel"/>
      </Row>
    </Table>
  </Worksheet>`;
    });

    xml += `
</Workbook>`;

    const blob = new Blob([xml], { type: 'application/vnd.ms-excel;charset=utf-8' });
    const link = document.createElement('a');
    const cleanDestination = (tripData.destination || 'Chuyen_di').replace(/[^a-zA-Z0-9_\u00C0-\u024F\u1EA0-\u1EFF]/g, '_');
    const cleanTitle = (tripData.title || 'detail').replace(/[^a-zA-Z0-9_\u00C0-\u024F\u1EA0-\u1EFF]/g, '_');
    const fileName = `Lich_trinh_${cleanDestination}_${cleanTitle}.xls`;
    link.href = window.URL.createObjectURL(blob);
    link.setAttribute('download', fileName);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
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

  fetchItinerary(): void {
    this.isLoadingDays.set(true);
    this.tripService.listDays(this.tripId).subscribe({
      next: (res) => {
        this.isLoadingDays.set(false);
        if (res && res.data) {
          // Sort days by day_number
          const sortedDays = res.data.sort((a, b) => a.day_number - b.day_number);
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
        this.days.update(days => days.map(day => ({
          ...day,
          activities: day.activities.map(item => item.id === activity.id ? res.data : item),
        })));
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
    if (!this.publicationDraft.author_confirmed) {
      this.publishError.set('Bạn cần xác nhận đây là lịch trình thực tế chính thức.');
      return;
    }
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
      general_tips: this.publicationDraft.general_tips || null,
      tags: [this.trip()?.destination || '', 'lịch trình thực tế'].filter(Boolean),
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
        this.publishError.set(error?.error?.message || 'Không thể xuất bản lịch trình.');
      },
    });
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
    navigator.clipboard?.writeText(url).then(() => {
      this.shareSuccessMsg.set('Da copy link moi.');
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

  onActivityDrop(event: CdkDragDrop<ActivityResponse[]>, dayPlanId: string): void {
    if (!this.canEditTrip()) return;
    if (event.previousIndex === event.currentIndex) return;

    const day = this.days().find((d) => d.id === dayPlanId);
    if (!day) return;

    const activities = [...day.activities];
    moveItemInArray(activities, event.previousIndex, event.currentIndex);

    // Optimistic state update
    this.days.update((allDays) =>
      allDays.map((d) => (d.id === dayPlanId ? { ...d, activities } : d))
    );

    // Build items payload for reordering
    const payload = activities.map((act, idx) => ({
      id: act.id,
      order_index: idx,
    }));

    this.tripService.reorderActivities(dayPlanId, payload).subscribe({
      next: () => {
        // Success
      },
      error: (err) => {
        console.error('Reorder failed, fetching original itinerary:', err);
        this.fetchItinerary();
        alert(err?.error?.message || 'Có lỗi xảy ra khi cập nhật thứ tự hoạt động.');
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
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(value);
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

  optimizeDayRoute(dayId: string): void {
    if (!this.canEditTrip() || this.optimizingDayId()) return;
    this.optimizingDayId.set(dayId);
    this.tripService.optimizeDayRoute(this.tripId, dayId).subscribe({
      next: () => {
        this.optimizingDayId.set(null);
        this.fetchItinerary();
      },
      error: (err) => {
        this.optimizingDayId.set(null);
        alert(err?.error?.message || 'Có lỗi xảy ra khi tối ưu lộ trình.');
      },
    });
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

    navigator.clipboard.writeText(text).then(() => {
      this.copiedSettlement.set(true);
      setTimeout(() => this.copiedSettlement.set(false), 2500);
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
    this.isAddActivityFromExploreOpen.set(true);
  }

  closeAddActivityFromExplore(): void {
    this.isAddActivityFromExploreOpen.set(false);
    this.selectedExploreLocation.set(null);
  }

  confirmAddActivityFromExplore(dayId: string): void {
    if (!this.canEditTrip()) return;
    const loc = this.selectedExploreLocation();
    if (!loc) return;

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
        start_time: null,
        end_time: null,
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
      marker.bindPopup(`<div style="font-weight:bold; font-size:14px; color:#1e293b;">${act.title}</div><div style="font-size:12px; color:#4b5563;">${act.location!.name}</div>`);
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
              <div style="font-weight: 700; font-size: 14px; margin-bottom: 2px; color: #1e293b;">#${idx + 1} - ${act.title}</div>
              <div style="font-size: 12px; color: #4b5563;">${act.location?.name || ''}</div>
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
      const formatted = num.toLocaleString('vi-VN');
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
    return Number(clean).toLocaleString('vi-VN');
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
