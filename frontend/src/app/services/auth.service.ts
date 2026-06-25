import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap, map } from 'rxjs';

export interface ResponseEnvelope<T> {
  status_code: number;
  message: string;
  data: T;
}

export interface UserInfo {
  id: string;
  email: string;
  full_name: string;
  avatar_url?: string | null;
  created_at?: string;
}

export interface LoginData {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: UserInfo;
}

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = 'http://localhost:8000/api';

  // Current logged in user details
  readonly currentUser = signal<UserInfo | null>(null);
  readonly isAuthenticated = signal<boolean>(false);

  constructor() {
    this.checkInitialAuth();
  }

  private checkInitialAuth(): void {
    const accessToken = localStorage.getItem('access_token');
    const userJson = localStorage.getItem('user_info');
    if (accessToken && userJson) {
      try {
        const user = JSON.parse(userJson);
        this.currentUser.set(user);
        this.isAuthenticated.set(true);
        // Refresh user info in the background
        this.fetchProfile().subscribe({
          next: (profile) => {
            this.currentUser.set(profile);
            localStorage.setItem('user_info', JSON.stringify(profile));
          },
          error: () => this.logout(),
        });
      } catch (e) {
        this.logout();
      }
    }
  }

  register(
    email: string,
    password: string,
    fullName: string,
  ): Observable<ResponseEnvelope<UserInfo>> {
    return this.http.post<ResponseEnvelope<UserInfo>>(`${this.baseUrl}/auth/register`, {
      email,
      password,
      full_name: fullName,
    });
  }

  login(email: string, password: string): Observable<ResponseEnvelope<LoginData>> {
    return this.http
      .post<ResponseEnvelope<LoginData>>(`${this.baseUrl}/auth/login`, {
        email,
        password,
      })
      .pipe(
        tap((response) => {
          if (response.data) {
            const loginData = response.data;
            localStorage.setItem('access_token', loginData.access_token);
            localStorage.setItem('refresh_token', loginData.refresh_token);
            localStorage.setItem('user_info', JSON.stringify(loginData.user));
            this.currentUser.set(loginData.user);
            this.isAuthenticated.set(true);
          }
        }),
      );
  }

  fetchProfile(): Observable<UserInfo> {
    const accessToken = localStorage.getItem('access_token');
    return this.http
      .get<ResponseEnvelope<UserInfo>>(`${this.baseUrl}/auth/me`, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      })
      .pipe(
        map((response) => response.data),
        tap((user) => this.currentUser.set(user)),
      );
  }

  logout(): void {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_info');
    this.currentUser.set(null);
    this.isAuthenticated.set(false);
  }
}
