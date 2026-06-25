import { Routes } from '@angular/router';
import { LoginComponent } from './components/auth/login/login';
import { RegisterComponent } from './components/auth/register/register';
import { DashboardComponent } from './components/dashboard/dashboard';
import { TripDetailComponent } from './components/trip-detail/trip-detail';
import { UserProfileComponent } from './components/profile/profile';

export const routes: Routes = [
  { path: 'login', component: LoginComponent },
  { path: 'register', component: RegisterComponent },
  { path: 'dashboard', component: DashboardComponent },
  { path: 'trip/:id', component: TripDetailComponent },
  { path: 'profile', component: UserProfileComponent },
  { path: '', redirectTo: 'login', pathMatch: 'full' }
];
