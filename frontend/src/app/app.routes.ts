import { Routes } from '@angular/router';
import { authGuard } from './guards/auth.guard';
import { adminGuard } from './guards/admin.guard';
import { guestGuard } from './guards/guest.guard';

export const routes: Routes = [
  {
    path: 'login',
    canActivate: [guestGuard],
    loadComponent: () =>
      import('./components/auth/login/login').then((module) => module.LoginComponent),
  },
  {
    path: 'register',
    canActivate: [guestGuard],
    loadComponent: () =>
      import('./components/auth/register/register').then((module) => module.RegisterComponent),
  },
  {
    path: 'verify-email',
    loadComponent: () =>
      import('./components/auth/verify-email/verify-email').then((module) => module.VerifyEmailComponent),
  },
  {
    path: 'dashboard',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./components/dashboard/dashboard').then((module) => module.DashboardComponent),
  },
  {
    path: 'trip/:id',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./components/trip-detail/trip-detail').then((module) => module.TripDetailComponent),
  },
  {
    path: 'profile',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./components/profile/profile').then((module) => module.UserProfileComponent),
  },
  {
    path: 'community/moderation',
    canActivate: [adminGuard],
    loadComponent: () =>
      import('./components/community/moderation/community-moderation').then(
        (module) => module.CommunityModerationComponent,
      ),
  },  {
    path: 'community',
    loadComponent: () =>
      import('./components/community/community-list').then(
        (module) => module.CommunityListComponent,
      ),
  },
  {
    path: 'community/users/:username',
    loadComponent: () =>
      import('./components/community/public-user-profile/public-user-profile').then(
        (module) => module.PublicUserProfileComponent,
      ),
  },  {
    path: 'community/trips/:slug',
    loadComponent: () =>
      import('./components/community/public-trip-detail').then(
        (module) => module.PublicTripDetailComponent,
      ),
  },
  {
    path: 'trip-invites/:token',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./components/accept-invite/accept-invite').then(
        (module) => module.AcceptInviteComponent,
      ),
  },
  { path: '', redirectTo: 'login', pathMatch: 'full' },
  { path: '**', redirectTo: 'login' },
];
