import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { PublicUserProfile, UserService } from '../../../services/user.service';

@Component({
  selector: 'app-public-user-profile', standalone: true,
  imports: [CommonModule, RouterLink], templateUrl: './public-user-profile.html',
  styleUrl: './public-user-profile.css',
})
export class PublicUserProfileComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly users = inject(UserService);
  readonly profile = signal<PublicUserProfile | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  ngOnInit(): void {
    const username = this.route.snapshot.paramMap.get('username') || '';
    this.users.getPublicProfile(username).subscribe({
      next: res => { this.profile.set(res.data); this.loading.set(false); },
      error: err => { this.error.set(err?.error?.message || 'Không tìm thấy trang cá nhân công khai.'); this.loading.set(false); },
    });
  }
}