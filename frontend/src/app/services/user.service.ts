import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ResponseEnvelope } from './auth.service';
import { API_BASE_URL } from '../config/api.config';

export interface UserPreferences {
  travel_style?: 'budget' | 'mid-range' | 'luxury' | null;
  interests?: string[];
  budget_range?: 'low' | 'medium' | 'high' | null;
  phone?: string | null;
  bio?: string | null;
}

export interface UserProfileResponse {
  id: string;
  username: string;
  email?: string | null;
  full_name: string;
  avatar_url: string | null;
  preferences_json: UserPreferences | null;
  is_public_profile: boolean;
  accepts_tour_bookings: boolean;
  public_bio?: string | null;
  public_phone?: string | null;
  public_zalo_url?: string | null;
  created_at: string;
}

export interface UpdateProfileRequest {
  full_name?: string | null;
  avatar_url?: string | null;
  preferences_json?: UserPreferences | null;
  is_public_profile?: boolean;
  accepts_tour_bookings?: boolean;
  public_bio?: string | null;
  public_phone?: string | null;
  public_zalo_url?: string | null;
}

export interface PublicUserSearchResult {
  id: string;
  username: string;
  full_name: string;
  avatar_url: string | null;
  public_bio: string | null;
  accepts_tour_bookings: boolean;
  public_trips_count: number;
}

export interface PublicUserProfile {
  id: string; username: string; full_name: string; avatar_url: string | null;
  public_bio: string | null; public_phone: string | null; public_zalo_url: string | null;
  accepts_tour_bookings: boolean; public_trips: any[];
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

  getPublicProfile(username: string): Observable<ResponseEnvelope<PublicUserProfile>> {
    return this.http.get<ResponseEnvelope<PublicUserProfile>>(`${this.baseUrl}/users/public/${encodeURIComponent(username)}`);
  }
  changePassword(payload: ChangePasswordRequest): Observable<ResponseEnvelope<null>> {
    return this.http.post<ResponseEnvelope<null>>(`${this.baseUrl}/users/me/password`, payload);
  }

  searchPublicUsers(query: string): Observable<ResponseEnvelope<PublicUserSearchResult[]>> {
    const params = new HttpParams().set('q', query.trim());
    return this.http.get<ResponseEnvelope<PublicUserSearchResult[]>>(`${this.baseUrl}/users/public-search`, { params });
  }
}
