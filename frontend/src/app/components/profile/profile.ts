import { forkJoin } from 'rxjs';
import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { AuthService, UserInfo } from '../../services/auth.service';
import { UserService, UserPreferences, UserProfileResponse } from '../../services/user.service';
import { P1Service, SavedCollection, SavedCollectionDetail } from '../../services/p1.service';
import { BookingInquiry, PublicTripListItem, PublicTripService } from '../../services/public-trip.service';
import { TripService } from '../../services/trip.service';

interface InterestItem {
  id: string;
  name: string;
}

interface DefaultAvatar {
  id: string;
  name: string;
  url: string;
}

@Component({
  selector: 'app-user-profile',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterModule],
  templateUrl: './profile.html',
  styleUrl: './profile.css',
})
export class UserProfileComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly authService = inject(AuthService);
  private readonly userService = inject(UserService);
  private readonly tripService = inject(TripService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  private readonly p1Service = inject(P1Service);
  private readonly publicTripService = inject(PublicTripService);

  readonly profile = signal<UserProfileResponse | null>(null);
  readonly userTripsCount = signal<number>(0);
  readonly userDestinationsCount = signal<number>(0);
  readonly isLoading = signal<boolean>(true);
  readonly isSaving = signal<boolean>(false);
  readonly successMessage = signal<string | null>(null);
  readonly errorMessage = signal<string | null>(null);
  readonly selectedAvatar = signal<string>('');
  readonly selectedInterests = signal<string[]>([]);

  readonly collections = signal<SavedCollection[]>([]);
  readonly savedTrips = signal<PublicTripListItem[]>([]);
  readonly receivedInquiries = signal<BookingInquiry[]>([]);
  readonly sentInquiries = signal<BookingInquiry[]>([]);
  readonly isBookingsLoading = signal(false);
  readonly selectedCollectionDetail = signal<SavedCollectionDetail | null>(null);
  readonly selectedCollectionId = signal<string | null>(null);
  readonly isSavedLoading = signal<boolean>(false);

  readonly fallbackAvatarUrl = '/default-avatars/avatar-01.svg';

  readonly availableInterests: InterestItem[] = [
    { id: 'history', name: 'Lich su' },
    { id: 'culture', name: 'Van hoa & Nghe thuat' },
    { id: 'nature', name: 'Thien nhien' },
    { id: 'adventure', name: 'Phieu luu' },
    { id: 'foodie', name: 'Am thuc' },
    { id: 'shopping', name: 'Mua sam' },
    { id: 'nightlife', name: 'Hoat dong ban dem' },
    { id: 'beaches', name: 'Nghi duong bien' },
    { id: 'cafe', name: 'Ca phe & Thu gian' },
  ];

  readonly defaultAvatars: DefaultAvatar[] = [
    { id: 'avatar1', name: 'Mac dinh 1', url: '/default-avatars/avatar-01.svg' },
    { id: 'avatar2', name: 'Mac dinh 2', url: '/default-avatars/avatar-02.svg' },
    { id: 'avatar3', name: 'Mac dinh 3', url: '/default-avatars/avatar-03.svg' },
    { id: 'avatar4', name: 'Mac dinh 4', url: '/default-avatars/avatar-04.svg' },
    { id: 'avatar5', name: 'Mac dinh 5', url: '/default-avatars/avatar-05.svg' },
    { id: 'avatar6', name: 'Mac dinh 6', url: '/default-avatars/avatar-06.svg' },
    { id: 'avatar7', name: 'Mac dinh 7', url: '/default-avatars/avatar-07.svg' },
    { id: 'avatar8', name: 'Mac dinh 8', url: '/default-avatars/avatar-08.svg' },
  ];

  readonly activeTab = signal<'personal' | 'ai' | 'saved' | 'bookings' | 'security'>('personal');
  readonly isPasswordChanging = signal<boolean>(false);
  readonly passwordSuccessMsg = signal<string | null>(null);
  readonly passwordErrorMsg = signal<string | null>(null);

  readonly profileForm = this.fb.nonNullable.group({
    full_name: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(100)]],
    avatar_url: [this.fallbackAvatarUrl],
    travel_style: ['mid-range' as 'budget' | 'mid-range' | 'luxury' | null],
    budget_range: ['medium' as 'low' | 'medium' | 'high' | null],
    email: [''],
    phone: [''],
    bio: [''],
    is_public_profile: [false],
    accepts_tour_bookings: [false],
    public_bio: [''],
    public_phone: [''],
    public_zalo_url: [''],
  });

  readonly passwordForm = this.fb.nonNullable.group({
    current_password: ['', [Validators.required]],
    new_password: ['', [Validators.required, Validators.minLength(6)]],
    confirm_password: ['', [Validators.required]],
  });

  ngOnInit(): void {
    if (!this.authService.isAuthenticated()) {
      this.router.navigate(['/login']);
      return;
    }
    const requestedTab = this.route.snapshot.queryParamMap.get('tab');
    if (requestedTab === 'bookings') this.activeTab.set('bookings');
    this.loadProfile();
    if (requestedTab === 'bookings') this.loadBookingInquiries();
  }

  loadProfile(): void {
    this.isLoading.set(true);
    this.errorMessage.set(null);

    this.userService.getUserProfile().subscribe({
      next: (res) => {
        this.isLoading.set(false);
        if (res?.data) {
          const u = res.data;
          const avatarUrl = this.isAllowedAvatarUrl(u.avatar_url) ? u.avatar_url! : this.fallbackAvatarUrl;

          this.profile.set(u);
          this.profileForm.patchValue({
            full_name: u.full_name,
            email: u.email || `${u.username}@smarttravel.com`,
            phone: (u as any).phone || (u as any).phone_number || '',
            avatar_url: avatarUrl,
            travel_style: u.preferences_json?.travel_style || 'mid-range',
            budget_range: u.preferences_json?.budget_range || 'medium',
            bio: (u.preferences_json as any)?.bio || '',
            is_public_profile: u.is_public_profile || false,
            accepts_tour_bookings: u.accepts_tour_bookings || false,
            public_bio: u.public_bio || '',
            public_phone: u.public_phone || '',
            public_zalo_url: u.public_zalo_url || '',
          });

          this.selectedAvatar.set(avatarUrl);
          this.selectedInterests.set(u.preferences_json?.interests || []);
        }
      },
      error: () => {
        this.isLoading.set(false);
        this.errorMessage.set('Khong the tai thong tin ho so cua ban.');
      },
    });

    this.tripService.listTrips(undefined, 1, 100, 'all').subscribe({
      next: (res) => {
        const items = res?.data?.items || [];
        this.userTripsCount.set(items.length);
        const uniqueDests = new Set(items.map((t) => t.destination).filter(Boolean));
        this.userDestinationsCount.set(uniqueDests.size);
      },
    });
  }

  switchTab(tab: 'personal' | 'ai' | 'saved' | 'bookings' | 'security'): void {
    this.activeTab.set(tab);
    if (tab === 'saved') this.loadSavedTabData();
    if (tab === 'bookings') this.loadBookingInquiries();
  }

  loadBookingInquiries(): void {
    this.isBookingsLoading.set(true);
    forkJoin({ received: this.publicTripService.receivedBookingInquiries(), sent: this.publicTripService.sentBookingInquiries() }).subscribe({
      next: result => {
        this.receivedInquiries.set(result.received.data || []);
        this.sentInquiries.set(result.sent.data || []);
        this.isBookingsLoading.set(false);
      },
      error: () => { this.isBookingsLoading.set(false); this.errorMessage.set('Không thể tải yêu cầu đặt tour.'); },
    });
  }

  updateInquiryStatus(item: BookingInquiry, status: 'new' | 'contacted' | 'closed'): void {
    this.publicTripService.updateBookingInquiryStatus(item.id, status).subscribe({
      next: () => { this.successMessage.set('Đã cập nhật trạng thái yêu cầu.'); this.loadBookingInquiries(); },
      error: error => this.errorMessage.set(error?.error?.message || 'Không thể cập nhật yêu cầu.'),
    });
  }

  bookingStatusLabel(status: string): string {
    return status === 'new' ? 'Mới' : status === 'contacted' ? 'Đã liên hệ' : 'Đã đóng';
  }
  loadSavedTabData(): void {
    this.isSavedLoading.set(true);
    forkJoin({
      collections: this.p1Service.listCollections(),
      saved: this.publicTripService.listSaved(1, 50)
    }).subscribe({
      next: (res) => {
        this.collections.set(res.collections?.data || []);
        this.savedTrips.set(res.saved?.data?.items || []);
        this.isSavedLoading.set(false);
      },
      error: () => this.isSavedLoading.set(false)
    });
  }

  viewCollection(collectionId: string): void {
    this.selectedCollectionId.set(collectionId);
    this.p1Service.getCollectionDetail(collectionId).subscribe({
      next: (res) => this.selectedCollectionDetail.set(res.data)
    });
  }

  backToCollections(): void {
    this.selectedCollectionId.set(null);
    this.selectedCollectionDetail.set(null);
  }

  deleteCollection(collectionId: string, event: Event): void {
    event.stopPropagation();
    if (!confirm('Bạn có chắc chắn muốn xóa bộ sưu tập này?')) return;
    this.p1Service.deleteCollection(collectionId).subscribe({
      next: () => {
        this.loadSavedTabData();
        if (this.selectedCollectionId() === collectionId) {
          this.backToCollections();
        }
      }
    });
  }

  onChangePassword(): void {
    if (this.passwordForm.invalid) return;
    const { new_password, confirm_password } = this.passwordForm.getRawValue();
    if (new_password !== confirm_password) {
      this.passwordErrorMsg.set('Mật khẩu mới và xác nhận mật khẩu không khớp.');
      return;
    }
    this.isPasswordChanging.set(true);
    this.passwordErrorMsg.set(null);
    this.passwordSuccessMsg.set(null);

    const currentPassword = this.passwordForm.getRawValue().current_password;
    this.userService.changePassword({
      current_password: currentPassword,
      new_password,
    }).subscribe({
      next: () => {
        this.isPasswordChanging.set(false);
        this.passwordSuccessMsg.set('Đã cập nhật mật khẩu thành công!');
        this.passwordForm.reset();
        setTimeout(() => this.passwordSuccessMsg.set(null), 3000);
      },
      error: (err) => {
        this.isPasswordChanging.set(false);
        const message = err?.error?.message;
        this.passwordErrorMsg.set(
          message === 'Mat khau hien tai khong dung'
            ? 'Mật khẩu hiện tại không đúng.'
            : message === 'Mat khau moi phai khac mat khau hien tai'
              ? 'Mật khẩu mới phải khác mật khẩu hiện tại.'
              : 'Không thể đổi mật khẩu. Vui lòng thử lại.',
        );
      },
    });
  }

  selectAvatar(url: string): void {
    this.selectedAvatar.set(url);
    this.profileForm.patchValue({ avatar_url: url });
  }

  isDefaultAvatar(url: string | null | undefined): boolean {
    return !!url && this.defaultAvatars.some((avatar) => avatar.url === url);
  }

  isAllowedAvatarUrl(url: string | null | undefined): boolean {
    return !!url && (this.isDefaultAvatar(url) || url.startsWith('https://') || url.startsWith('http://'));
  }

  toggleInterest(interestId: string): void {
    const current = this.selectedInterests();
    if (current.includes(interestId)) {
      this.selectedInterests.set(current.filter((i) => i !== interestId));
    } else {
      this.selectedInterests.set([...current, interestId]);
    }
  }

  isInterestSelected(interestId: string): boolean {
    return this.selectedInterests().includes(interestId);
  }

  getInterestName(interestId: string): string {
    return this.availableInterests.find((i) => i.id === interestId)?.name || interestId;
  }

  getTravelStyleName(style: string | null | undefined): string {
    switch (style) {
      case 'budget':
        return 'Tiet kiem';
      case 'luxury':
        return 'Sang trong';
      default:
        return 'Tu tuc';
    }
  }

  onSubmit(): void {
    if (this.profileForm.invalid) return;

    this.isSaving.set(true);
    this.successMessage.set(null);
    this.errorMessage.set(null);

    const formVal = this.profileForm.getRawValue();
    const avatarUrl = this.isAllowedAvatarUrl(formVal.avatar_url) ? formVal.avatar_url : this.fallbackAvatarUrl;

    const preferences_json: UserPreferences = {
      travel_style: formVal.travel_style,
      budget_range: formVal.budget_range,
      interests: this.selectedInterests(),
    };

    const payload = {
      full_name: formVal.full_name,
      avatar_url: avatarUrl,
      preferences_json,
      is_public_profile: formVal.is_public_profile,
      accepts_tour_bookings: formVal.is_public_profile && formVal.accepts_tour_bookings,
      public_bio: formVal.public_bio || null,
      public_phone: formVal.public_phone || null,
      public_zalo_url: formVal.public_zalo_url || null,
    };

    this.userService.updateUserProfile(payload).subscribe({
      next: (res) => {
        this.isSaving.set(false);
        if (res?.data) {
          const updated = res.data;
          this.profile.set(updated);
          this.selectedAvatar.set(updated.avatar_url || this.fallbackAvatarUrl);
          this.successMessage.set('Da cap nhat ho so thanh cong!');

          const cachedUser: UserInfo = {
            id: updated.id,
            username: updated.username,
            full_name: updated.full_name,
            avatar_url: updated.avatar_url || this.fallbackAvatarUrl,
          };
          this.authService.currentUser.set(cachedUser);
          localStorage.setItem('user_info', JSON.stringify(cachedUser));

          setTimeout(() => this.successMessage.set(null), 3000);
        }
      },
      error: (err) => {
        this.isSaving.set(false);
        this.errorMessage.set(err?.error?.message || 'Co loi xay ra khi cap nhat ho so.');
      },
    });
  }

  onReset(): void {
    this.loadProfile();
  }

  goBack(): void {
    this.router.navigate(['/dashboard']);
  }
}
