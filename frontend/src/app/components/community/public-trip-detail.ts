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

@Component({
  selector: 'app-public-trip-detail',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
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

  loadFeedback(publicationId:string): void {
    this.publicTrips.getFeedback(publicationId).subscribe({ next: response => { this.feedback.set(response.data); this.selectedRating = response.data.my_rating || 0; } });
  }

  submitComment(): void {
    const publication=this.trip(), content=this.commentText.trim(); if(!publication||!content) return;
    if(!this.auth.isAuthenticated()){ this.router.navigate(['/login'],{queryParams:{returnUrl:this.router.url}}); return; }
    this.publicTrips.addComment(publication.id,content).subscribe({ next:response=>{ this.commentText=''; this.feedback.update(value=>value?{...value,comments:[response.data,...value.comments]}:value); }, error:error=>this.feedbackMessage.set(error?.error?.message||'Không thể gửi bình luận.') });
  }

  submitRating(rating:number): void {
    const publication=this.trip(); if(!publication) return;
    if(!this.auth.isAuthenticated()){ this.router.navigate(['/login'],{queryParams:{returnUrl:this.router.url}}); return; }
    this.selectedRating=rating; this.publicTrips.rate(publication.id,rating).subscribe({ next:()=>{this.feedbackMessage.set('Đã lưu đánh giá của bạn.');this.loadFeedback(publication.id);}, error:error=>this.feedbackMessage.set(error?.error?.message||'Không thể đánh giá.') });
  }

  loadFollowStatus(authorId:string):void { this.publicTrips.followStatus(authorId).subscribe({next:response=>this.followingAuthor.set(response.data.following)}); }
  toggleFollow():void { const publication=this.trip(); if(!publication)return; if(!this.auth.isAuthenticated()){this.router.navigate(['/login'],{queryParams:{returnUrl:this.router.url}});return;} const request=this.followingAuthor()?this.publicTrips.unfollow(publication.author.id):this.publicTrips.follow(publication.author.id); request.subscribe({next:()=>this.followingAuthor.update(value=>!value)}); }

  loadCollections(): void {
    this.p1Service.listCollections().subscribe({ next: response => this.collections.set(response.data || []) });
  }

  createCollection(): void {
    const name = this.newCollectionName.trim();
    if (!name) return;
    this.p1Service.createCollection(name).subscribe({
      next: () => { this.newCollectionName = ''; this.collectionMessage.set('Đã tạo bộ sưu tập.'); this.loadCollections(); },
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
    return value == null ? 'Chưa công khai' : `${new Intl.NumberFormat('vi-VN').format(value)} ₫`;
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
        this.saveMessage.set(saved
          ? 'Đã lưu. Bạn có thể tìm lại tại Cộng đồng → Đã lưu của tôi.'
          : 'Đã bỏ lịch trình khỏi danh sách đã lưu.');
        this.saving.set(false);
      },
      error: (error) => {
        this.saveMessage.set(error?.error?.message || 'Không thể cập nhật trạng thái lưu.');
        this.saving.set(false);
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
    if (mode !== 'full_trip') {
      this.tripsService.listTrips(undefined, 1, 100, 'all').subscribe({
        next: response => this.targetTrips.set(
          (response.data?.items || []).filter(item => item.role === 'owner' || item.role === 'editor')
        ),
      });
    }
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
        num_travelers: 1,
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
        this.router.navigate(['/trip', response.data.trip_id]);
      },
      error: error => {
        this.importing.set(false);
        this.importError.set(error?.error?.message || 'Không thể thêm lịch trình.');
      },
    });
  }
}
