import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ResponseEnvelope } from './auth.service';
import { API_BASE_URL } from '../config/api.config';

export interface UserPreferences {
  travel_style?: 'budget' | 'mid-range' | 'luxury' | null;
  interests?: string[];
  budget_range?: 'low' | 'medium' | 'high' | null;
}

export interface UserProfileResponse {
  id: string;
  username: string;
  email?: string | null;
  full_name: string;
  avatar_url: string | null;
  preferences_json: UserPreferences | null;
  created_at: string;
}

export interface UpdateProfileRequest {
  full_name?: string | null;
  avatar_url?: string | null;
  preferences_json?: UserPreferences | null;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

@Injectable({
  providedIn: 'root',
})
export class UserService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = inject(API_BASE_URL);

  getUserProfile(): Observable<ResponseEnvelope<UserProfileResponse>> {
    return this.http.get<ResponseEnvelope<UserProfileResponse>>(
      `${this.baseUrl}/users/me`
    );
  }

  updateUserProfile(payload: UpdateProfileRequest): Observable<ResponseEnvelope<UserProfileResponse>> {
    return this.http.patch<ResponseEnvelope<UserProfileResponse>>(
      `${this.baseUrl}/users/me`,
      payload
    );
  }

  changePassword(payload: ChangePasswordRequest): Observable<ResponseEnvelope<null>> {
    return this.http.post<ResponseEnvelope<null>>(`${this.baseUrl}/users/me/password`, payload);
  }
}
