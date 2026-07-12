declare const L: any;

import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
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
} from '../../services/trip.service';

import { PlacePhotoService, BestRatedPlace } from '../../services/place-photo.service';
import {
  GENERIC_TRAVEL_FALLBACK_IMAGES,
  getInlineScenicFallback,
  resolveTravelCoverImage,
} from '../../services/travel-cover-images';
import { of } from 'rxjs';
import { catchError, timeout } from 'rxjs/operators';
import { OsrmService } from '../../services/osrm.service';

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
  imports: [CommonModule, ReactiveFormsModule, RouterModule, DragDropModule],
  templateUrl: './trip-detail.html',
  styleUrl: './trip-detail.css',
})
export class TripDetailComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  private readonly tripService = inject(TripService);
  private readonly placePhotoService = inject(PlacePhotoService);
  private readonly aiStreamService = inject(AiStreamService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly osrmService = inject(OsrmService);

  // Dynamic Destination Images Cache
  readonly destinationImagesMap = signal<Map<string, string[]>>(new Map());
  readonly defaultPlaceholderUrl = resolveTravelCoverImage('travel', 'place-placeholder');

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
  };

  getCoordinatesForDestination(destination: string | undefined): [number, number] {
    if (!destination) return [16.0471, 108.2068];
    const dest = destination.toLowerCase().trim();
    if (this.destinationCoordinates[dest]) {
      return this.destinationCoordinates[dest];
    }
    for (const key in this.destinationCoordinates) {
      if (dest.includes(key) || key.includes(dest)) {
        return this.destinationCoordinates[key];
      }
    }
    return [16.0471, 108.2068];
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
  readonly shareParticipants = signal<TripParticipant[]>([]);
  readonly shareInvites = signal<TripInvite[]>([]);
  readonly shareSuccessMsg = signal<string | null>(null);
  readonly shareErrorMsg = signal<string | null>(null);
  readonly isLoadingShares = signal<boolean>(false);
  readonly isSubmittingShare = signal<boolean>(false);
  readonly latestInviteUrl = signal<string | null>(null);

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
  });

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
    email: [''],
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
          this.settingsForm.patchValue({
            title: t.title,
            destination: t.destination,
            start_date: this.formatIsoToDdMmYyyy(t.start_date),
            end_date: this.formatIsoToDdMmYyyy(t.end_date),
            budget: this.formatNumberWithDots(t.budget),
            num_travelers: t.num_travelers,
            status: t.status,
          });

          // Fetch photo for active trip destination
          if (t.destination) {
            this.fetchDestinationImage(t.destination);
          }
          if (this.canManageShares()) {
            this.fetchShares();
          }
        }
      },
      error: (err) => {
        this.isLoadingDetail.set(false);
        this.errorMsg.set('Không thể tải thông tin chuyến đi.');
      },
    });

    this.fetchItinerary();
    this.fetchChatAndSuggestions();
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
    return item.actor?.full_name || item.actor?.email || 'He thong';
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
      email: value.email.trim() || null,
      role: value.role,
      expires_in_days: value.expires_in_days,
    }).subscribe({
      next: (res) => {
        this.isSubmittingShare.set(false);
        const invite = res.data;
        this.shareSuccessMsg.set(
          value.email.trim()
            ? 'Da tao loi moi. Nguoi nhan can chap nhan o chuong thong bao de duoc chia se.'
            : 'Da tao link moi chia se.'
        );
        if (invite?.accept_url) {
          this.latestInviteUrl.set(`${window.location.origin}${invite.accept_url}`);
        }
        this.shareForm.patchValue({ email: '' });
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

  // Budget Tracker logic
  switchSubTab(tab: 'itinerary' | 'route' | 'budget' | 'explore' | 'settings'): void {
    this.activeSubTab.set(tab);
    if (tab === 'budget') {
      this.loadBudgetData();
    } else if (tab === 'explore') {
      this.loadExploreData();
      setTimeout(() => this.initOrRefreshExploreMap(), 100);
    } else if (tab === 'route') {
      if (this.routeDayIndex() >= this.days().length) {
        this.routeDayIndex.set(0);
      }
      setTimeout(() => this.initOrRefreshRouteMap(), 100);
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

    if (item) {
      this.budgetForm.reset({
        category: item.category,
        label: item.label,
        planned_amount: item.planned_amount,
        actual_amount: item.actual_amount,
        date: item.date || '',
      });
    } else {
      this.budgetForm.reset({
        category: 'other',
        label: '',
        planned_amount: 0,
        actual_amount: 0,
        date: '',
      });
    }

    this.isBudgetModalOpen.set(true);
  }

  closeBudgetModal(): void {
    this.isBudgetModalOpen.set(false);
    this.selectedBudgetItem.set(null);
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
  loadExploreData(): void {
    this.isLoadingExplore.set(true);
    this.exploreError.set(null);

    const cat = this.activeExploreCategory();
    let term = 'địa điểm du lịch';
    if (cat === 'meal') term = 'quán ăn ngon';
    else if (cat === 'hotel') term = 'khách sạn';
    else if (cat === 'cafe') term = 'quán cà phê';

    const dest = this.trip()?.destination || '';

    this.tripService.searchLocations(term, dest).subscribe({
      next: (res) => {
        this.isLoadingExplore.set(false);
        if (res && res.data) {
          this.exploreLocations.set(res.data);
          setTimeout(() => this.renderMapMarkers(), 50);
        }
      },
      error: (err) => {
        this.isLoadingExplore.set(false);
        this.exploreError.set('Không thể tải danh sách đề xuất.');
      },
    });

    this.loadBestRatedPlaces(term);
  }

  onExploreCategoryChange(category: 'attraction' | 'meal' | 'hotel' | 'cafe'): void {
    this.activeExploreCategory.set(category);
    this.exploreQuery.set('');
    this.loadExploreData();
  }

  onExploreSearch(): void {
    const q = this.exploreQuery().trim();
    if (!q) {
      this.loadExploreData();
      return;
    }

    this.isLoadingExplore.set(true);
    this.exploreError.set(null);

    const dest = this.trip()?.destination || '';
    this.tripService.searchLocations(q, dest).subscribe({
      next: (res) => {
        this.isLoadingExplore.set(false);
        if (res && res.data) {
          this.exploreLocations.set(res.data);
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

    const upsertPayload = {
      name: loc.name,
      address: loc.address,
      lat: loc.lat,
      lng: loc.lng,
      category: catVal,
      google_place_id: loc.google_place_id,
      photo_url: loc.photo_url,
      rating: loc.rating,
    };

    this.tripService.upsertLocation(upsertPayload).subscribe({
      next: (upsertRes) => {
        const locationId = upsertRes.data.id;
        
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
      },
      error: () => {
        this.isSubmittingExploreActivity.set(false);
        alert('Không thể lưu thông tin địa điểm.');
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
  onSaveSettings(): void {
    if (!this.canManageShares()) return;
    if (this.settingsForm.invalid) return;

    const val = this.settingsForm.getRawValue();
    if (new Date(val.end_date) < new Date(val.start_date)) {
      this.settingsErrorMsg.set('Ngày kết thúc không được nhỏ hơn ngày bắt đầu.');
      return;
    }

    this.isSavingSettings.set(true);
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
        if (res && res.data) {
          this.trip.set(res.data);
          this.settingsSuccessMsg.set('Đã lưu cài đặt chuyến đi thành công!');
          this.fetchItinerary(); // reload list of days in case dates were modified
          setTimeout(() => this.settingsSuccessMsg.set(null), 3000);
        }
      },
      error: (err) => {
        this.isSavingSettings.set(false);
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
      const html = `<div class="custom-map-pin" title="${loc.name}"><span class="material-symbols-outlined pin-emoji text-primary" style="font-size: 18px;">${iconName}</span></div>`;
      const customIcon = L.divIcon({
        html: html,
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
      popupContent.innerHTML = `
        <div class="popup-title" style="font-weight: 700; font-size: 14px; margin-bottom: 4px; color: #222222; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">${loc.name}</div>
        <div class="popup-address" style="font-size: 12px; color: #6a6a6a; margin-bottom: 8px; line-height: 1.3; text-overflow: ellipsis; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; max-height: 32px;">${loc.address || ''}</div>
        <button class="popup-btn-add" style="background-color: #ff385c; color: white; border: none; padding: 8px 12px; border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer; width: 100%; text-align: center; box-sizing: border-box; transition: background-color 0.2s;">Thêm vào lịch trình</button>
      `;

      // Popup Action bind
      const btn = popupContent.querySelector('.popup-btn-add');
      if (btn) {
        btn.addEventListener('click', () => {
          this.openAddActivityFromExplore(loc);
        });
      }

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
      let markerColor = '#ff385c';
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
      marker.bindPopup(`<div style="font-weight:bold; font-size:14px; color:#fff;">${act.title}</div><div style="font-size:12px; color:rgba(255,255,255,0.7);">${act.location!.name}</div>`);
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
            color: '#8083ff',
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
          
          let markerColor = '#8083ff'; // Default primary tint
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
              <div style="font-weight: 700; font-size: 14px; margin-bottom: 2px; color: #fff;">#${idx + 1} - ${act.title}</div>
              <div style="font-size: 12px; color: rgba(255,255,255,0.7);">${act.location?.name || ''}</div>
              ${act.start_time ? `<div style="font-size: 11px; margin-top: 4px; color: #8083ff;">🕒 ${act.start_time}</div>` : ''}
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
}
