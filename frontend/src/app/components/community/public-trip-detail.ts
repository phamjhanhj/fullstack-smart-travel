import { forkJoin, Observable } from 'rxjs';
import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, FormsModule, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import {
  AuthorVerdict,
  PublicSnapshotActivity,
  PublicSnapshotDay,
  PublicTrip,
  PublicTripImportRequest,
  PublicTripService,
  PublicFeedback,
} from '../../services/public-trip.service';
import { DayPlanResponse, TripListItem, TripService } from '../../services/trip.service';
import { P1Service, SavedCollection } from '../../services/p1.service';
import { CustomSelectComponent } from '../shared/custom-select/custom-select';
import { MAX_BUDGET_VND, MAX_TRAVELERS } from '../../config/trip-policy';
import { apiErrorMessage, apiValidationIssues, applyApiErrors, controlErrorMessage, integerValidator, nonBlankValidator } from '../../utils/form-errors';

@Component({
  selector: 'app-public-trip-detail',
  standalone: true,
  imports: [CommonModule, FormsModule, ReactiveFormsModule, RouterLink, CustomSelectComponent],
  templateUrl: './public-trip-detail.html',
  styleUrl: './public-trip-detail.css',
})
export class PublicTripDetailComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  readonly auth = inject(AuthService);
  private readonly publicTrips = inject(PublicTripService);
  private readonly tripsService = inject(TripService);
  private readonly p1Service = inject(P1Service);
  private readonly fb = inject(FormBuilder);

  readonly trip = signal<PublicTrip | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly isImportOpen = signal(false);
  readonly importError = signal<string | null>(null);
  readonly importFieldErrors = signal<Record<string, string>>({});
  readonly importPreview = signal<any | null>(null);
  readonly importing = signal(false);
  readonly saving = signal(false);
  readonly saveMessage = signal<string | null>(null);
  readonly targetTrips = signal<TripListItem[]>([]);
  readonly targetDays = signal<DayPlanResponse[]>([]);
  readonly feedback = signal<PublicFeedback | null>(null);
  readonly followingAuthor = signal(false);
  readonly feedbackMessage = signal<string | null>(null);
  readonly commentError = signal<string | null>(null);
  commentText = '';
  selectedRating = 0;
  hoverRating = 0;
  readonly isSubmittingFeedback = signal(false);
  readonly collections = signal<SavedCollection[]>([]);
  readonly collectionMessage = signal<string | null>(null);
  selectedCollectionId = '';
  newCollectionName = '';
  readonly isBookingOpen = signal(false);
  readonly isSubmittingBooking = signal(false);
  readonly bookingError = signal<string | null>(null);
  readonly isReportOpen = signal(false);
  readonly isSubmittingReport = signal(false);
  readonly reportError = signal<string | null>(null);

  readonly bookingForm = this.fb.nonNullable.group({
    contact_name: ['', [Validators.required, nonBlankValidator(), Validators.minLength(2), Validators.maxLength(100)]],
    contact_phone: ['', [Validators.required, Validators.maxLength(30), Validators.pattern(/^(?=(?:\D*\d){7,})[+()\d\s.-]{7,30}$/)]],
    travelers: [1, [Validators.required, integerValidator(), Validators.min(1), Validators.max(100)]],
    message: ['', [Validators.maxLength(1500)]],
  });

  readonly reportForm = this.fb.nonNullable.group({
    reason: ['other' as 'spam' | 'misleading' | 'unsafe' | 'harassment' | 'copyright' | 'other', [Validators.required]],
    details: ['', [Validators.maxLength(1000)]],
  });

  readonly reportReasonOptions = [
    { label: 'Thông tin sai lệch', value: 'misleading' },
    { label: 'Nội dung không an toàn', value: 'unsafe' },
    { label: 'Spam', value: 'spam' },
    { label: 'Quấy rối', value: 'harassment' },
    { label: 'Vi phạm bản quyền', value: 'copyright' },
    { label: 'Lý do khác', value: 'other' },
  ];

  readonly collapsedDays = signal<Record<number, boolean>>({});

  importMode: 'full_trip' | 'day' | 'activity' = 'full_trip';
  selectedDay: PublicSnapshotDay | null = null;
  selectedActivity: PublicSnapshotActivity | null = null;

  toggleDayCollapse(dayNumber: number, event?: Event): void {
    if (event) event.stopPropagation();
    const currentState = this.isDayCollapsed(dayNumber);
    this.collapsedDays.update(map => ({
      ...map,
      [dayNumber]: !currentState
    }));
  }

  isDayCollapsed(dayNumber: number): boolean {
    const val = this.collapsedDays()[dayNumber];
    return val !== undefined ? val : true; // Default to collapsed on screen load
  }

  expandAllDays(): void {
    const pub = this.trip();
    if (!pub?.snapshot_json?.days) return;
    const newMap: Record<number, boolean> = {};
    for (const d of pub.snapshot_json.days) {
      newMap[d.day_number] = false;
    }
    this.collapsedDays.set(newMap);
  }

  collapseAllDays(): void {
    const pub = this.trip();
    if (!pub?.snapshot_json?.days) return;
    const newMap: Record<number, boolean> = {};
    for (const d of pub.snapshot_json.days) {
      newMap[d.day_number] = true;
    }
    this.collapsedDays.set(newMap);
  }

  areAllDaysCollapsed(): boolean {
    const pub = this.trip();
    if (!pub?.snapshot_json?.days?.length) return true;
    return pub.snapshot_json.days.every(d => this.isDayCollapsed(d.day_number));
  }

  toggleAllDays(): void {
    if (this.areAllDaysCollapsed()) {
      this.expandAllDays();
    } else {
      this.collapseAllDays();
    }
  }
  targetTripId = '';
  targetDayId = '';
  startDate = '';
  newTripTitle = '';
  estimatedBudget: number | null = null;
  formattedEstimatedBudget = '';
  numTravelers: number = 1;

  get collectionSelectOptions() {
    return this.collections().map(c => ({ label: `${c.name} (${c.item_count})`, value: c.id }));
  }

  get targetTripSelectOptions() {
    return this.targetTrips().map(t => ({ label: t.title, value: t.id }));
  }

  get targetDaySelectOptions() {
    return this.targetDays().map(d => ({ label: `Ngày ${d.day_number} (${d.date})`, value: d.id }));
  }

  onEstimatedBudgetInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    const raw = input.value.replace(/\D/g, '');
    if (raw) {
      const num = Number(raw);
      this.estimatedBudget = num;
      this.formattedEstimatedBudget = num.toLocaleString('en-US');
      input.value = this.formattedEstimatedBudget;
    } else {
      this.estimatedBudget = null;
      this.formattedEstimatedBudget = '';
      input.value = '';
    }
  }

  clearEstimatedBudget(): void {
    this.estimatedBudget = null;
    this.formattedEstimatedBudget = '';
  }

  ngOnInit(): void {
    if (this.auth.isAuthenticated()) this.loadCollections();
    const slug = this.route.snapshot.paramMap.get('slug') || '';
    this.publicTrips.getBySlug(slug).subscribe({
      next: (response) => {
        this.trip.set(response.data);
        this.loadFeedback(response.data.id);
        if (this.auth.isAuthenticated()) this.loadFollowStatus(response.data.author.id);
        this.newTripTitle = `${response.data.title} - bản của tôi`;
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        this.startDate = tomorrow.toISOString().slice(0, 10);
        this.loading.set(false);
      },
      error: (error) => {
        this.error.set(error?.error?.message || 'Không tìm thấy lịch trình công khai.');
        this.loading.set(false);
      },
    });
  }

  loadFeedback(publicationId: string): void {
    this.publicTrips.getFeedback(publicationId).subscribe({
      next: response => {
        this.feedback.set(response.data);
        this.selectedRating = response.data.my_rating || 0;
      },
      error: error => this.feedbackMessage.set(apiErrorMessage(error, 'Không thể tải đánh giá và bình luận.')),
    });
  }

  hasAlreadyRated(): boolean {
    return (this.feedback()?.my_rating || 0) > 0;
  }

  selectRatingDraft(star: number): void {
    if (this.hasAlreadyRated()) return;
    this.selectedRating = star;
  }

  isDraftDirty(): boolean {
    const savedRating = this.feedback()?.my_rating || 0;
    const hasNewRating = !this.hasAlreadyRated() && this.selectedRating > 0 && this.selectedRating !== savedRating;
    const hasComment = this.commentText.trim().length > 0;
    return hasNewRating || hasComment;
  }

  canSubmitFeedback(): boolean {
    const savedRating = this.feedback()?.my_rating || 0;
    const hasRatingChange = !this.hasAlreadyRated() && this.selectedRating > 0 && this.selectedRating !== savedRating;
    const hasComment = this.commentText.trim().length > 0;
    return hasRatingChange || hasComment;
  }

  saveFeedbackAndComment(): void {
    const publication = this.trip();
    if (!publication || this.isSubmittingFeedback()) return;

    if (!this.auth.isAuthenticated()) {
      this.router.navigate(['/login'], { queryParams: { returnUrl: this.router.url } });
      return;
    }

    const savedRating = this.feedback()?.my_rating || 0;
    const hasRatingToSave = !this.hasAlreadyRated() && this.selectedRating > 0 && this.selectedRating !== savedRating;
    const content = this.commentText.trim();

    if (!hasRatingToSave && !content) return;
    if (content && content.length < 2) {
      this.commentError.set('Bình luận phải có ít nhất 2 ký tự.');
      return;
    }
    if (content.length > 2000) {
      this.commentError.set('Bình luận không được vượt quá 2.000 ký tự.');
      return;
    }
    this.commentError.set(null);

    this.isSubmittingFeedback.set(true);
    this.feedbackMessage.set(null);

    const tasks: Observable<any>[] = [];

    if (hasRatingToSave) {
      tasks.push(this.publicTrips.rate(publication.id, this.selectedRating));
    }

    if (content) {
      tasks.push(this.publicTrips.addComment(publication.id, content));
    }

    forkJoin(tasks).subscribe({
      next: () => {
        this.isSubmittingFeedback.set(false);
        this.commentText = '';
        this.feedbackMessage.set('Đã lưu đánh giá và bình luận của bạn thành công!');
        this.loadFeedback(publication.id);
      },
      error: (err) => {
        this.isSubmittingFeedback.set(false);
        this.feedbackMessage.set(apiErrorMessage(err, 'Không thể lưu đánh giá / bình luận.'));
      }
    });
  }

  loadFollowStatus(authorId:string):void {
    this.publicTrips.followStatus(authorId).subscribe({
      next: response => this.followingAuthor.set(response.data.following),
      error: err => this.saveMessage.set(apiErrorMessage(err, 'Không thể tải trạng thái theo dõi.')),
    });
  }

  toggleFollow():void {
    const publication = this.trip();
    if (!publication) return;
    if (!this.auth.isAuthenticated()) {
      this.router.navigate(['/login'], { queryParams: { returnUrl: this.router.url } });
      return;
    }
    const request = this.followingAuthor()
      ? this.publicTrips.unfollow(publication.author.id)
      : this.publicTrips.follow(publication.author.id);
    request.subscribe({
      next: () => this.followingAuthor.update(value => !value),
      error: err => this.saveMessage.set(apiErrorMessage(err, 'Không thể cập nhật trạng thái theo dõi.')),
    });
  }

  requestTourBooking(): void {
    const publication = this.trip();
    if (!publication) return;
    if (!this.auth.isAuthenticated()) {
      this.router.navigate(['/login'], { queryParams: { returnUrl: this.router.url } });
      return;
    }
    this.bookingForm.reset({ contact_name: '', contact_phone: '', travelers: 1, message: '' });
    this.bookingError.set(null);
    this.isBookingOpen.set(true);
  }

  submitTourBooking(): void {
    const publication = this.trip();
    if (!publication || this.isSubmittingBooking()) return;
    if (this.bookingForm.invalid) {
      this.bookingForm.markAllAsTouched();
      this.bookingError.set('Vui lòng kiểm tra các trường được đánh dấu bên dưới.');
      return;
    }
    const value = this.bookingForm.getRawValue();
    this.isSubmittingBooking.set(true);
    this.bookingError.set(null);
    this.publicTrips.sendBookingInquiry(publication.id, {
      contact_name: value.contact_name.trim(),
      contact_phone: value.contact_phone.trim(),
      travelers: value.travelers,
      message: value.message.trim() || null,
    }).subscribe({
      next: () => {
        this.isSubmittingBooking.set(false);
        this.isBookingOpen.set(false);
        this.saveMessage.set('Đã gửi yêu cầu đặt tour. Thông tin chỉ được gửi cho tác giả.');
      },
      error: err => {
        this.isSubmittingBooking.set(false);
        this.bookingError.set(applyApiErrors(this.bookingForm, err, 'Không thể gửi yêu cầu đặt tour.'));
      },
    });
  }

  reportTrip(): void {
    const publication = this.trip();
    if (!publication) return;
    if (!this.auth.isAuthenticated()) {
      this.router.navigate(['/login'], { queryParams: { returnUrl: this.router.url } });
      return;
    }
    this.reportForm.reset({ reason: 'other', details: '' });
    this.reportError.set(null);
    this.isReportOpen.set(true);
  }

  submitReport(): void {
    const publication = this.trip();
    if (!publication || this.isSubmittingReport()) return;
    if (this.reportForm.invalid) {
      this.reportForm.markAllAsTouched();
      this.reportError.set('Vui lòng kiểm tra các trường được đánh dấu bên dưới.');
      return;
    }
    const value = this.reportForm.getRawValue();
    this.isSubmittingReport.set(true);
    this.reportError.set(null);
    this.publicTrips.reportTrip(publication.id, value.reason, value.details.trim() || undefined).subscribe({
      next: () => {
        this.isSubmittingReport.set(false);
        this.isReportOpen.set(false);
        this.saveMessage.set('Đã tiếp nhận báo cáo của bạn.');
      },
      error: err => {
        this.isSubmittingReport.set(false);
        this.reportError.set(applyApiErrors(this.reportForm, err, 'Không thể gửi báo cáo.'));
      },
    });
  }

  moderateTrip(decision: 'uphold' | 'dismiss'): void {
    const publication = this.trip();
    if (!publication || this.saving()) return;
    this.saving.set(true);
    this.saveMessage.set(null);
    this.publicTrips.moderatePublication(publication.id, decision).subscribe({
      next: response => {
        this.saving.set(false);
        const newStatus = response.data?.moderation_status || (decision === 'uphold' ? 'flagged' : 'approved');
        this.trip.update(curr => curr ? { ...curr, moderation_status: newStatus } : null);
        this.saveMessage.set(
          decision === 'uphold' ? 'Đã xác nhận vi phạm và ẩn bài viết khỏi cộng đồng.' : 'Đã bác bỏ báo cáo và mở hiển thị bài viết.'
        );
      },
      error: err => {
        this.saving.set(false);
        this.saveMessage.set(apiErrorMessage(err, 'Không thể thực hiện thao tác kiểm duyệt.'));
      },
    });
  }
  loadCollections(): void {
    this.p1Service.listCollections().subscribe({ next: response => this.collections.set(response.data || []) });
  }

  createCollection(): void {
    const publication = this.trip();
    const name = this.newCollectionName.trim();
    if (!name) {
      this.collectionMessage.set('Tên bộ sưu tập là bắt buộc.');
      return;
    }
    if (name.length > 100) {
      this.collectionMessage.set('Tên bộ sưu tập không được vượt quá 100 ký tự.');
      return;
    }
    this.p1Service.createCollection(name).subscribe({
      next: (response) => {
        const newCol = response.data;
        this.newCollectionName = '';
        this.loadCollections();
        if (newCol?.id && publication) {
          this.selectedCollectionId = newCol.id;
          this.addToCollection();
        } else {
          this.collectionMessage.set('Đã tạo bộ sưu tập.');
        }
      },
      error: error => this.collectionMessage.set(apiErrorMessage(error, 'Không thể tạo bộ sưu tập.')),
    });
  }

  addToCollection(): void {
    const publication = this.trip();
    if (!publication || !this.selectedCollectionId) return;
    this.p1Service.addToCollection(this.selectedCollectionId, publication.id).subscribe({
      next: () => this.collectionMessage.set('Đã thêm lịch trình vào bộ sưu tập.'),
      error: error => this.collectionMessage.set(error?.error?.message || 'Không thể thêm vào bộ sưu tập.'),
    });
  }

  verdictLabel(value: AuthorVerdict): string {
    return {
      must_go: 'Nhất định nên đi',
      recommended: 'Đáng đi',
      preference_based: 'Tùy sở thích',
      skip: 'Có thể bỏ qua',
    }[value];
  }

  verdictClass(value: AuthorVerdict): string {
    return `verdict ${value}`;
  }

  money(value: number | null | undefined): string {
    return value == null ? 'Chưa công khai' : `${new Intl.NumberFormat('en-US').format(value)} VND`;
  }

  save(): void {
    const publication = this.trip();
    if (!publication || this.saving()) return;
    if (!this.auth.isAuthenticated()) {
      this.router.navigate(['/login'], { queryParams: { returnUrl: this.router.url } });
      return;
    }

    this.saving.set(true);
    this.saveMessage.set(null);
    const request = publication.is_saved
      ? this.publicTrips.unsave(publication.id)
      : this.publicTrips.save(publication.id);

    request.subscribe({
      next: (response) => {
        const saved = response.data.saved;
        this.trip.update(item => item ? {
          ...item,
          is_saved: saved,
          save_count: Math.max(0, item.save_count + (saved ? 1 : -1)),
        } : item);
        this.saveMessage.set(saved ? 'Đã lưu lịch trình' : 'Đã bỏ lưu lịch trình');
        this.saving.set(false);
        setTimeout(() => this.saveMessage.set(null), 3000);
      },
      error: (error) => {
        this.saveMessage.set(error?.error?.message || 'Không thể cập nhật trạng thái lưu.');
        this.saving.set(false);
        setTimeout(() => this.saveMessage.set(null), 3000);
      },
    });
  }

  openImport(mode: 'full_trip' | 'day' | 'activity', day?: PublicSnapshotDay, activity?: PublicSnapshotActivity, event?: Event): void {
    if (event) event.stopPropagation();
    if (!this.auth.isAuthenticated()) {
      this.router.navigate(['/login'], { queryParams: { returnUrl: this.router.url } });
      return;
    }
    this.importMode = mode;
    this.selectedDay = day || null;
    this.selectedActivity = activity || null;
    this.targetTripId = '';
    this.targetDayId = '';
    this.targetDays.set([]);
    this.importError.set(null);
    this.importFieldErrors.set({});
    this.importPreview.set(null);
    this.isImportOpen.set(true);

    if (mode === 'full_trip') {
      const pub = this.trip();
      if (pub) {
        this.newTripTitle = `${pub.title} - bản của tôi`;
        this.startDate = new Date().toISOString().slice(0, 10);
        this.estimatedBudget = null;
        this.formattedEstimatedBudget = '';
        this.numTravelers = 1;
      }
    } else {
      this.tripsService.listTrips(undefined, 1, 100, 'all').subscribe({
        next: response => this.targetTrips.set(
          (response.data?.items || []).filter(item => item.role === 'owner' || item.role === 'editor')
        ),
        error: error => this.importError.set(apiErrorMessage(error, 'Không thể tải danh sách chuyến đi của bạn.')),
      });
    }
  }

  closeImport(): void {
    this.isImportOpen.set(false);
    this.newTripTitle = '';
    this.startDate = '';
    this.numTravelers = 1;
    this.estimatedBudget = null;
    this.formattedEstimatedBudget = '';
    this.targetTripId = '';
    this.targetDayId = '';
    this.targetDays.set([]);
    this.importError.set(null);
    this.importFieldErrors.set({});
    this.importPreview.set(null);
  }

  onTargetTripChange(): void {
    this.targetDayId = '';
    this.targetDays.set([]);
    if (!this.targetTripId) return;
    this.tripsService.listDays(this.targetTripId).subscribe({
      next: response => this.targetDays.set(response.data || []),
      error: error => this.importError.set(apiErrorMessage(error, 'Không thể tải danh sách ngày của chuyến đi.')),
    });
  }

  private validateImport(): boolean {
    const errors: Record<string, string> = {};
    if (this.importMode === 'full_trip') {
      if (!this.startDate) errors['start_date'] = 'Ngày bắt đầu là bắt buộc.';
      if (this.newTripTitle.trim().length > 200) errors['title'] = 'Tên chuyến không được vượt quá 200 ký tự.';
      if (this.estimatedBudget !== null && (this.estimatedBudget < 1 || this.estimatedBudget > MAX_BUDGET_VND)) {
        errors['budget'] = 'Ngân sách phải từ 1 đến 2.000.000.000 VND.';
      }
      if (!Number.isInteger(this.numTravelers) || this.numTravelers < 1 || this.numTravelers > MAX_TRAVELERS) {
        errors['num_travelers'] = `Số người đi phải từ 1 đến ${MAX_TRAVELERS}.`;
      }
    } else {
      if (!this.targetTripId) errors['target_trip_id'] = 'Chuyến đi đích là bắt buộc.';
      if (!this.targetDayId) errors['target_day_plan_id'] = 'Ngày muốn thêm là bắt buộc.';
    }
    this.importFieldErrors.set(errors);
    if (Object.keys(errors).length > 0) {
      this.importError.set('Vui lòng kiểm tra các trường được đánh dấu bên dưới.');
      return false;
    }
    return true;
  }

  private applyImportApiErrors(error: unknown, fallback: string): void {
    const errors: Record<string, string> = {};
    for (const issue of apiValidationIssues(error)) {
      if (issue.field) errors[issue.field] = issue.message;
    }
    this.importFieldErrors.set(errors);
    this.importError.set(apiErrorMessage(error, fallback));
  }

  buildImportPayload(): PublicTripImportRequest {
    if (this.importMode === 'full_trip') {
      return {
        import_mode: 'full_trip',
        start_date: this.startDate,
        title: this.newTripTitle,
        budget: this.estimatedBudget,
        num_travelers: this.numTravelers || 1,
        conflict_strategy: 'smart_merge',
      };
    }
    return {
      import_mode: this.importMode,
      target_trip_id: this.targetTripId,
      target_day_plan_id: this.targetDayId,
      source_day_number: this.selectedDay?.day_number,
      source_activity_ids: this.selectedActivity ? [this.selectedActivity.source_activity_id] : [],
      conflict_strategy: 'smart_merge',
    };
  }

  preview(): void {
    const publication = this.trip();
    if (!publication) return;
    if (!this.validateImport()) return;
    this.importError.set(null);
    this.publicTrips.previewImport(publication.id, this.buildImportPayload()).subscribe({
      next: response => this.importPreview.set(response.data),
      error: error => this.applyImportApiErrors(error, 'Không thể kiểm tra thao tác thêm.'),
    });
  }

  confirmImport(): void {
    const publication = this.trip();
    if (!publication) return;
    if (!this.validateImport()) return;
    this.importing.set(true);
    this.importError.set(null);
    this.publicTrips.import(publication.id, this.buildImportPayload()).subscribe({
      next: response => {
        this.importing.set(false);
        this.isImportOpen.set(false);
        const targetTripId = response.data?.trip_id || this.targetTripId;
        if (targetTripId) {
          this.router.navigate(['/trip', targetTripId]);
        } else {
          this.router.navigate(['/dashboard']);
        }
      },
      error: error => {
        this.importing.set(false);
        this.applyImportApiErrors(error, 'Không thể thêm lịch trình.');
      },
    });
  }

  isBookingFieldInvalid(fieldName: string): boolean {
    const field = this.bookingForm.get(fieldName);
    return !!(field && field.invalid && (field.dirty || field.touched));
  }

  bookingFieldError(fieldName: string, label: string): string {
    return controlErrorMessage(this.bookingForm.get(fieldName), label, {
      pattern: 'Số điện thoại không đúng định dạng.',
    });
  }

  isReportFieldInvalid(fieldName: string): boolean {
    const field = this.reportForm.get(fieldName);
    return !!(field && field.invalid && (field.dirty || field.touched));
  }

  reportFieldError(fieldName: string, label: string): string {
    return controlErrorMessage(this.reportForm.get(fieldName), label);
  }
}
