import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ResponseEnvelope } from './auth.service';

export interface UserPreferences {
  travel_style?: 'budget' | 'mid-range' | 'luxury' | null;
  interests?: string[];
  budget_range?: 'low' | 'medium' | 'high' | null;
}

export interface UserProfileResponse {
  id: string;
  email: string;
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

@Injectable({
  providedIn: 'root',
})
export class UserService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = 'http://localhost:8000/api';

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
}
