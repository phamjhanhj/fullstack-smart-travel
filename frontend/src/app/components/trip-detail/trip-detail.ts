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
  BudgetSummaryResponse,
  BudgetItemResponse,
  BudgetCategory,
  LocationResponse,
  LocationCategory,
} from '../../services/trip.service';

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
  private readonly aiStreamService = inject(AiStreamService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  // Leaflet Map instance & active markers
  private exploreMap: any = null;
  private mapMarkers: any[] = [];

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
  readonly errorMsg = signal<string | null>(null);

  // Chat Form/State
  readonly chatInput = signal<string>('');
  readonly isSendingMessage = signal<boolean>(false);

  // Sub-tabs switcher state
  readonly activeSubTab = signal<'itinerary' | 'budget' | 'explore' | 'settings'>('itinerary');

  // Settings State Signals
  readonly isSavingSettings = signal<boolean>(false);
  readonly isDeleteModalOpen = signal<boolean>(false);
  readonly isDeleting = signal<boolean>(false);
  readonly settingsSuccessMsg = signal<string | null>(null);
  readonly settingsErrorMsg = signal<string | null>(null);

  // Explore Tab State Signals
  readonly exploreLocations = signal<LocationResponse[]>([]);
  readonly exploreQuery = signal<string>('');
  readonly activeExploreCategory = signal<'attraction' | 'meal' | 'hotel' | 'cafe'>('attraction');
  readonly isLoadingExplore = signal<boolean>(false);
  readonly exploreError = signal<string | null>(null);

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
  readonly selectedActivityId = signal<string | null>(null); // For future editing support
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
    budget: [null as number | null, [Validators.min(0)]],
    num_travelers: [1, [Validators.required, Validators.min(1)]],
    status: ['draft' as 'draft' | 'active' | 'completed', [Validators.required]],
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
            start_date: t.start_date,
            end_date: t.end_date,
            budget: t.budget,
            num_travelers: t.num_travelers,
            status: t.status,
          });
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

  fetchItinerary(): void {
    this.isLoadingDays.set(true);
    this.tripService.listDays(this.tripId).subscribe({
      next: (res) => {
        this.isLoadingDays.set(false);
        if (res && res.data) {
          // Sort days by day_number
          const sortedDays = res.data.sort((a, b) => a.day_number - b.day_number);
          this.days.set(sortedDays);
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
          this.chatHistory.set(res.data);
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
    this.isGenerating.set(true);
    this.tripService.generateDays(this.tripId, true).subscribe({
      next: () => {
        this.isGenerating.set(false);
        this.fetchItinerary();
        // Ask AI assistant for a welcome advice as well
        this.sendMessageToAi("Hãy tóm tắt lịch trình bạn vừa thiết kế cho chuyến đi của tôi.");
      },
      error: (err) => {
        this.isGenerating.set(false);
        alert(err?.error?.message || 'Có lỗi xảy ra khi tự động tạo lịch trình.');
      },
    });
  }

  // Send Chat Message to AI
  onSendChatMessage(): void {
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
    this.tripService.updateSuggestionStatus(suggestionId, 'rejected').subscribe({
      next: () => {
        this.activeSuggestions.update((list) => list.filter((s) => s.id !== suggestionId));
      },
    });
  }

  onActivityDrop(event: CdkDragDrop<ActivityResponse[]>, dayPlanId: string): void {
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
    this.selectedDayId.set(dayId);
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

  closeActivityModal(): void {
    this.isActivityModalOpen.set(false);
    this.selectedDayId.set(null);
  }

  onSubmitActivity(): void {
    if (this.activityForm.invalid) {
      this.activityForm.markAllAsTouched();
      return;
    }

    const dayId = this.selectedDayId();
    if (!dayId) return;

    this.isSubmittingActivity.set(true);
    this.activityError.set(null);

    const val = this.activityForm.getRawValue();
    const payload: CreateActivityRequest = {
      title: val.title,
      description: val.description || null,
      type: val.type,
      start_time: val.start_time || null,
      end_time: val.end_time || null,
      estimated_cost: val.estimated_cost,
      notes: val.notes || null,
    };

    this.tripService.addActivity(this.tripId, dayId, payload).subscribe({
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

  getActivityIcon(type: ActivityType | null): string {
    switch (type) {
      case 'meal': return '🍽️';
      case 'attraction': return '🏛️';
      case 'hotel': return '🏨';
      case 'transport': return '🚗';
      default: return '📍';
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
  switchSubTab(tab: 'itinerary' | 'budget' | 'explore' | 'settings'): void {
    this.activeSubTab.set(tab);
    if (tab === 'budget') {
      this.loadBudgetData();
    } else if (tab === 'explore') {
      this.loadExploreData();
      setTimeout(() => this.initOrRefreshExploreMap(), 100);
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
      case 'food': return '🍽️';
      case 'transport': return '🚗';
      case 'hotel': return '🏨';
      case 'activity': return '🏛️';
      default: return '💵';
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
  }

  openAddActivityFromExplore(location: LocationResponse): void {
    this.selectedExploreLocation.set(location);
    this.isAddActivityFromExploreOpen.set(true);
  }

  closeAddActivityFromExplore(): void {
    this.isAddActivityFromExploreOpen.set(false);
    this.selectedExploreLocation.set(null);
  }

  confirmAddActivityFromExplore(dayId: string): void {
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
    if (this.settingsForm.invalid) return;

    const val = this.settingsForm.getRawValue();
    if (new Date(val.end_date) < new Date(val.start_date)) {
      this.settingsErrorMsg.set('Ngày kết thúc không được nhỏ hơn ngày bắt đầu.');
      return;
    }

    this.isSavingSettings.set(true);
    this.settingsSuccessMsg.set(null);
    this.settingsErrorMsg.set(null);

    const payload = {
      title: val.title,
      destination: val.destination,
      start_date: val.start_date,
      end_date: val.end_date,
      budget: val.budget,
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
        start_date: t.start_date,
        end_date: t.end_date,
        budget: t.budget,
        num_travelers: t.num_travelers,
        status: t.status,
      });
    }
    this.settingsErrorMsg.set(null);
    this.settingsSuccessMsg.set(null);
  }

  // Delete Trip actions
  onOpenDeleteModal(): void {
    this.isDeleteModalOpen.set(true);
  }

  onCloseDeleteModal(): void {
    this.isDeleteModalOpen.set(false);
  }

  onConfirmDeleteTrip(): void {
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
  initOrRefreshExploreMap(): void {
    const container = document.getElementById('explore-map');
    if (!container) return;

    if (!this.exploreMap) {
      // Find a center coordinate based on loaded explore list, otherwise default to city or Hanoi
      let centerCoords: [number, number] = [21.0285, 105.8542];
      const valid = this.exploreLocations().filter(loc => loc.lat !== null && loc.lng !== null);
      if (valid.length > 0) {
        centerCoords = [valid[0].lat as number, valid[0].lng as number];
      }

      this.exploreMap = L.map('explore-map').setView(centerCoords, 13);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap contributors'
      }).addTo(this.exploreMap);
    }

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
      const emoji = this.getExploreCategoryEmoji(loc.category);
      const html = `<div class="custom-map-pin" title="${loc.name}"><span class="pin-emoji">${emoji}</span></div>`;
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

  // Helper category mapping to emojis
  getExploreCategoryEmoji(category: string | null | undefined): string {
    if (!category) return '📍';
    const cat = category.toLowerCase().trim();
    if (cat.includes('meal') || cat.includes('restaurant') || cat.includes('food') || cat.includes('dining')) return '🍜';
    if (cat.includes('attraction') || cat.includes('sightseeing') || cat.includes('tourist')) return '🏛️';
    if (cat.includes('hotel') || cat.includes('accommodation') || cat.includes('lodging') || cat.includes('resort')) return '🏖️';
    if (cat.includes('cafe') || cat.includes('coffee') || cat.includes('tea')) return '☕';
    return '📍';
  }

  // Helper to return beautiful covers matching Airbnb photo-first rule
  getTripImage(destination: string | undefined): string {
    if (!destination) return 'https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?auto=format&fit=crop&w=600&q=80';
    const dest = destination.toLowerCase().trim();
    if (dest.includes('bali')) {
      return 'https://images.unsplash.com/photo-1537996194471-e657df975ab4?auto=format&fit=crop&w=600&q=80';
    }
    if (dest.includes('tokyo') || dest.includes('nhật')) {
      return 'https://images.unsplash.com/photo-1503899036084-c55cdd92da26?auto=format&fit=crop&w=600&q=80';
    }
    if (dest.includes('paris') || dest.includes('pháp')) {
      return 'https://images.unsplash.com/photo-1502602898657-3e91760cbb34?auto=format&fit=crop&w=600&q=80';
    }
    if (dest.includes('hà nội') || dest.includes('hanoi')) {
      return 'https://images.unsplash.com/photo-1509060464153-4466739f78d0?auto=format&fit=crop&w=600&q=80';
    }
    if (dest.includes('đà nẵng') || dest.includes('da nang')) {
      return 'https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=600&q=80';
    }
    if (dest.includes('phú quốc') || dest.includes('phu quoc')) {
      return 'https://images.unsplash.com/photo-1583212292454-1fe6229603b7?auto=format&fit=crop&w=600&q=80';
    }
    return 'https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?auto=format&fit=crop&w=600&q=80';
  }
}
