import { forkJoin, Observable } from 'rxjs';
import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
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

@Component({
  selector: 'app-public-trip-detail',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, CustomSelectComponent],
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

  readonly trip = signal<PublicTrip | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly isImportOpen = signal(false);
  readonly importError = signal<string | null>(null);
  readonly importPreview = signal<any | null>(null);
  readonly importing = signal(false);
  readonly saving = signal(false);
  readonly saveMessage = signal<string | null>(null);
  readonly targetTrips = signal<TripListItem[]>([]);
  readonly targetDays = signal<DayPlanResponse[]>([]);
  readonly feedback = signal<PublicFeedback | null>(null);
  readonly followingAuthor = signal(false);
  readonly feedbackMessage = signal<string | null>(null);
  commentText = '';
  selectedRating = 0;
  hoverRating = 0;
  readonly isSubmittingFeedback = signal(false);
  readonly collections = signal<SavedCollection[]>([]);
  readonly collectionMessage = signal<string | null>(null);
  selectedCollectionId = '';
  newCollectionName = '';

  importMode: 'full_trip' | 'day' | 'activity' = 'full_trip';
  selectedDay: PublicSnapshotDay | null = null;
  selectedActivity: PublicSnapshotActivity | null = null;
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
      }
    });
  }

  selectRatingDraft(star: number): void {
    this.selectedRating = star;
  }

  isDraftDirty(): boolean {
    const savedRating = this.feedback()?.my_rating || 0;
    const hasNewRating = this.selectedRating > 0 && this.selectedRating !== savedRating;
    const hasComment = this.commentText.trim().length > 0;
    return hasNewRating || hasComment;
  }

  canSubmitFeedback(): boolean {
    const savedRating = this.feedback()?.my_rating || 0;
    const hasRatingChange = this.selectedRating > 0 && this.selectedRating !== savedRating;
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
    const hasRatingToSave = this.selectedRating > 0 && this.selectedRating !== savedRating;
    const content = this.commentText.trim();

    if (!hasRatingToSave && !content) return;

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
        this.feedbackMessage.set(err?.error?.message || 'Không thể lưu đánh giá / bình luận.');
      }
    });
  }

  loadFollowStatus(authorId:string):void { this.publicTrips.followStatus(authorId).subscribe({next:response=>this.followingAuthor.set(response.data.following)}); }
  toggleFollow():void { const publication=this.trip(); if(!publication)return; if(!this.auth.isAuthenticated()){this.router.navigate(['/login'],{queryParams:{returnUrl:this.router.url}});return;} const request=this.followingAuthor()?this.publicTrips.unfollow(publication.author.id):this.publicTrips.follow(publication.author.id); request.subscribe({next:()=>this.followingAuthor.update(value=>!value)}); }

  requestTourBooking(): void {
    const publication = this.trip();
    if (!publication) return;
    if (!this.auth.isAuthenticated()) {
      this.router.navigate(['/login'], { queryParams: { returnUrl: this.router.url } });
      return;
    }
    const name = window.prompt('Tên người liên hệ:')?.trim();
    if (!name) return;
    const phone = window.prompt('Số điện thoại liên hệ:')?.trim();
    if (!phone) return;
    const travelers = Number(window.prompt('Số người tham gia:', '1') || '1');
    const message = window.prompt('Lời nhắn cho nhà tổ chức tour (không bắt buộc):')?.trim() || null;
    this.publicTrips.sendBookingInquiry(publication.id, { contact_name: name, contact_phone: phone, travelers, message }).subscribe({
      next: () => this.saveMessage.set('Đã gửi yêu cầu đặt tour. Thông tin chỉ được gửi cho tác giả.'),
      error: err => this.saveMessage.set(err?.error?.message || 'Không thể gửi yêu cầu đặt tour.'),
    });
  }

  reportTrip(): void {
    const publication = this.trip();
    if (!publication) return;
    if (!this.auth.isAuthenticated()) {
      this.router.navigate(['/login'], { queryParams: { returnUrl: this.router.url } });
      return;
    }
    const details = window.prompt('Mô tả vấn đề bạn muốn báo cáo:')?.trim();
    if (!details) return;
    this.publicTrips.reportTrip(publication.id, 'other', details).subscribe({
      next: () => this.saveMessage.set('Đã tiếp nhận báo cáo của bạn.'),
      error: err => this.saveMessage.set(err?.error?.message || 'Không thể gửi báo cáo.'),
    });
  }
  loadCollections(): void {
    this.p1Service.listCollections().subscribe({ next: response => this.collections.set(response.data || []) });
  }

  createCollection(): void {
    const publication = this.trip();
    const name = this.newCollectionName.trim();
    if (!name) return;
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
      error: error => this.collectionMessage.set(error?.error?.message || 'Không thể tạo bộ sưu tập.'),
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

  openImport(mode: 'full_trip' | 'day' | 'activity', day?: PublicSnapshotDay, activity?: PublicSnapshotActivity): void {
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
    this.importPreview.set(null);
  }

  onTargetTripChange(): void {
    this.targetDayId = '';
    this.targetDays.set([]);
    if (!this.targetTripId) return;
    this.tripsService.listDays(this.targetTripId).subscribe({
      next: response => this.targetDays.set(response.data || []),
    });
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
    this.importError.set(null);
    this.publicTrips.previewImport(publication.id, this.buildImportPayload()).subscribe({
      next: response => this.importPreview.set(response.data),
      error: error => this.importError.set(error?.error?.message || 'Không thể kiểm tra thao tác thêm.'),
    });
  }

  confirmImport(): void {
    const publication = this.trip();
    if (!publication) return;
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
        this.importError.set(error?.error?.message || 'Không thể thêm lịch trình.');
      },
    });
  }
}
