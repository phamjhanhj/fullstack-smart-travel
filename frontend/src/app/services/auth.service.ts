import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, firstValueFrom, tap, map } from 'rxjs';
import { API_BASE_URL } from '../config/api.config';
import { clearStoredSession } from './auth-storage';

export interface ResponseEnvelope<T> {
  status_code: number;
  message: string;
  data: T;
}

export interface UserInfo {
  id: string;
  username: string;
  email?: string | null;
  full_name: string;
  avatar_url?: string | null;
  is_admin?: boolean;
  created_at?: string;
}

export interface LoginData {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserInfo;
}

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = inject(API_BASE_URL);

  // Current logged in user details
  readonly currentUser = signal<UserInfo | null>(null);
  readonly isAuthenticated = signal<boolean>(false);
  readonly isAdmin = computed(() => this.currentUser()?.is_admin === true);
  private readonly initialization: Promise<void>;

  constructor() {
    // Defer the HTTP call until dependency construction has completed.
    this.initialization = Promise.resolve().then(() => this.checkInitialAuth());
  }

  whenReady(): Promise<void> {
    return this.initialization;
  }

  private async checkInitialAuth(): Promise<void> {
    const accessToken = sessionStorage.getItem('access_token');
    const userJson = sessionStorage.getItem('user_info');
    if (accessToken && userJson) {
      try {
        const user = JSON.parse(userJson);
        this.currentUser.set(user);
        this.isAuthenticated.set(true);
        try {
          const profile = await firstValueFrom(this.fetchProfile());
          sessionStorage.setItem('user_info', JSON.stringify(profile));
        } catch (error: any) {
          if (error?.status === 401) this.clearSession();
        }
        return;
      } catch {
        this.clearSession();
      }
    }

    try {
      const response = await firstValueFrom(
        this.http.post<ResponseEnvelope<{ access_token: string }>>(
          `${this.baseUrl}/auth/refresh`,
          {},
          { withCredentials: true },
        ),
      );
      sessionStorage.setItem('access_token', response.data.access_token);
      const profile = await firstValueFrom(this.fetchProfile());
      sessionStorage.setItem('user_info', JSON.stringify(profile));
      this.currentUser.set(profile);
      this.isAuthenticated.set(true);
    } catch {
      this.clearSession();
    }
  }

  register(
    username: string,
    email: string,
    password: string,
    fullName: string,
  ): Observable<ResponseEnvelope<UserInfo>> {
    return this.http.post<ResponseEnvelope<UserInfo>>(`${this.baseUrl}/auth/register`, {
      username: username.trim().toLowerCase(),
      email: email.trim().toLowerCase(),
      password,
      full_name: fullName.trim().replace(/\s+/g, ' '),
    });
  }

  login(login: string, password: string): Observable<ResponseEnvelope<LoginData>> {
    return this.http
      .post<ResponseEnvelope<LoginData>>(
        `${this.baseUrl}/auth/login`,
        { login: login.trim().toLowerCase(), password },
        { withCredentials: true },
      )
      .pipe(
        tap((response) => {
          if (response.data) {
            const loginData = response.data;
            sessionStorage.setItem('access_token', loginData.access_token);
            sessionStorage.setItem('user_info', JSON.stringify(loginData.user));
            this.currentUser.set(loginData.user);
            this.isAuthenticated.set(true);
          }
        }),
      );
  }

  verifyEmail(token: string): Observable<ResponseEnvelope<null>> {
    return this.http.post<ResponseEnvelope<null>>(`${this.baseUrl}/auth/verify-email`, { token });
  }

  resendVerification(login: string): Observable<ResponseEnvelope<null>> {
    return this.http.post<ResponseEnvelope<null>>(`${this.baseUrl}/auth/resend-verification`, {
      login: login.trim().toLowerCase(),
    });
  }

  fetchProfile(): Observable<UserInfo> {
    return this.http.get<ResponseEnvelope<UserInfo>>(`${this.baseUrl}/auth/me`).pipe(
      map((response) => response.data),
      tap((user) => this.currentUser.set(user)),
    );
  }

  clearSession(): void {
    clearStoredSession();
    this.currentUser.set(null);
    this.isAuthenticated.set(false);
  }

  logout(): void {
    this.http
      .post(`${this.baseUrl}/auth/logout`, {}, { withCredentials: true })
      .subscribe({ error: () => undefined });
    this.clearSession();
  }
}
