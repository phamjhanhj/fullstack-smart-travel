import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { API_BASE_URL } from '../config/api.config';
import { ResponseEnvelope } from './auth.service';

export type AuthorVerdict = 'must_go' | 'recommended' | 'preference_based' | 'skip';
export type ActualStatus = 'visited' | 'changed' | 'skipped' | 'planned_only';

export interface PublicActivityReview {
  activity_id: string;
  actual_status: ActualStatus;
  author_verdict: AuthorVerdict;
  rating?: number | null;
  next_traveler_note?: string | null;
  best_time?: string | null;
  actual_wait_minutes?: number | null;
  booking_required?: boolean | null;
  actual_cost?: number | null;
}

export interface PublishTripRequest {
  title: string;
  summary: string;
  visibility: 'public' | 'unlisted';
  traveler_type?: string | null;
  pace?: string | null;
  budget_style?: string | null;
  actual_total_cost?: number | null;
  itinerary_rating?: number | null;
  cost_rating?: number | null;
  place_rating?: number | null;
  best_places: string[];
  best_foods: string[];
  would_change?: string | null;
  general_tips?: string | null;
  tags: string[];
  show_travel_month: boolean;
  show_author_name: boolean;
  show_cost: boolean;
  allow_clone: boolean;
  allow_partial_import: boolean;
  allow_comments: boolean;
  activity_reviews: PublicActivityReview[];
  author_confirmed: boolean;
}

export interface PublicTripAuthor {
  id: string;
  profile_username?: string | null;
  full_name: string;
  avatar_url: string | null;
  accepts_tour_bookings?: boolean;
}

export interface PublicSnapshotActivity {
  source_activity_id: string;
  location_id: string | null;
  title: string;
  description?: string | null;
  type: string;
  start_time?: string | null;
  end_time?: string | null;
  actual_status: ActualStatus;
  actual_cost?: number | null;
  author_verdict: AuthorVerdict;
  rating?: number | null;
  next_traveler_note?: string | null;
  best_time?: string | null;
  actual_wait_minutes?: number | null;
  booking_required?: boolean | null;
  address?: string | null;
  lat?: number | null;
  lng?: number | null;
}

export interface PublicSnapshotDay {
  day_number: number;
  title: string;
  date?: string | null;
  actual_day_cost: number;
  activities: PublicSnapshotActivity[];
}

export interface PublicTrip {
  id: string;
  slug: string;
  title: string;
  summary: string;
  destination: string;
  cover_image_url: string | null;
  visibility: string;
  status: string;
  duration_days: number;
  travel_month: number | null;
  travel_year: number | null;
  traveler_type: string | null;
  actual_total_cost: number | null;
  actual_cost_per_person: number | null;
  cost_is_verified: boolean;
  itinerary_rating: number | null;
  cost_rating: number | null;
  place_rating: number | null;
  overall_rating: number | null;
  snapshot_version: number;
  snapshot_json: {
    official_itinerary: boolean;
    days: PublicSnapshotDay[];
    cost_summary: Record<string, any>;
    review: {
      best_places: string[];
      best_foods: string[];
      would_change?: string | null;
      tips?: string | null;
    };
  };
  tags: string[];
  privacy_options: Record<string, any>;
  allow_clone: boolean;
  allow_partial_import: boolean;
  view_count: number;
  save_count: number;
  clone_count: number;
  published_at: string | null;
  author: PublicTripAuthor;
  is_saved: boolean;
}

export interface PublicTripListItem {
  id: string;
  slug: string;
  title: string;
  summary: string;
  destination: string;
  cover_image_url: string | null;
  duration_days: number;
  actual_cost_per_person: number | null;
  overall_rating: number | null;
  save_count: number;
  clone_count: number;
  published_at: string | null;
  tags: string[];
  author: PublicTripAuthor;
  is_saved: boolean;
}

export interface PublicTripListResponse {
  items: PublicTripListItem[];
  total: number;
  page: number;
  limit: number;
}
export interface PublicComment { id:string; content:string; is_verified_trip:boolean; rating?:number|null; created_at:string; user:{id:string;username:string;full_name:string;avatar_url:string|null}; }
export interface PublicFeedback { comments:PublicComment[]; rating_average:number|null; rating_count:number; my_rating:number|null; }
export interface CommunityReport {
  id: string;
  reporter_user_id: string;
  publication_id: string | null;
  reported_user_id: string | null;
  reason: string;
  details: string | null;
  status: 'open' | 'upheld' | 'dismissed';
  created_at: string;
}
export interface BookingInquiry {
  id: string;
  publication_id: string;
  trip_title: string;
  requester_user_id: string;
  author_user_id: string;
  contact_name: string;
  contact_phone: string;
  travelers: number;
  message: string | null;
  status: 'new' | 'contacted' | 'closed';
  created_at: string;
  updated_at: string | null;
}
export interface PersonalizedRecommendation { publication:PublicTripListItem; reason:string; score:number; }

export interface PublicTripImportRequest {
  import_mode: 'full_trip' | 'day' | 'activity';
  target_trip_id?: string | null;
  target_day_plan_id?: string | null;
  source_day_number?: number | null;
  source_activity_ids?: string[];
  start_date?: string | null;
  title?: string | null;
  budget?: number | null;
  num_travelers?: number;
  conflict_strategy?: 'append' | 'replace_optional' | 'smart_merge';
}

@Injectable({ providedIn: 'root' })
export class PublicTripService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = inject(API_BASE_URL);

  eligibility(tripId: string): Observable<ResponseEnvelope<any>> {
    return this.http.get<ResponseEnvelope<any>>(`${this.baseUrl}/trips/${tripId}/publication/eligibility`);
  }

  publish(tripId: string, payload: PublishTripRequest): Observable<ResponseEnvelope<PublicTrip>> {
    return this.http.post<ResponseEnvelope<PublicTrip>>(
      `${this.baseUrl}/trips/${tripId}/publication/publish`,
      payload,
    );
  }

  getOwnerPublication(tripId: string): Observable<ResponseEnvelope<PublicTrip>> {
    return this.http.get<ResponseEnvelope<PublicTrip>>(`${this.baseUrl}/trips/${tripId}/publication`);
  }

  archive(tripId: string): Observable<ResponseEnvelope<null>> {
    return this.http.post<ResponseEnvelope<null>>(`${this.baseUrl}/trips/${tripId}/publication/archive`, {});
  }

  list(filters: {
    destination?: string;
    search?: string;
    maxCost?: number;
    minDays?: number;
    maxDays?: number;
    minRating?: number;
    travelerType?: string;
    pace?: string;
    sort?: string;
    page?: number;
    limit?: number;
  } = {}): Observable<ResponseEnvelope<PublicTripListResponse>> {
    let params = new HttpParams()
      .set('page', String(filters.page || 1))
      .set('limit', String(filters.limit || 12))
      .set('sort', filters.sort || 'newest');
    if (filters.destination) params = params.set('destination', filters.destination);
    if (filters.search) params = params.set('search', filters.search);
    if (filters.maxCost) params = params.set('max_cost_per_person', String(filters.maxCost));
    if (filters.minDays) params = params.set('min_days', String(filters.minDays));
    if (filters.maxDays) params = params.set('max_days', String(filters.maxDays));
    if (filters.minRating) params = params.set('min_rating', String(filters.minRating));
    if (filters.travelerType) params = params.set('traveler_type', filters.travelerType);
    if (filters.pace) params = params.set('pace', filters.pace);
    return this.http.get<ResponseEnvelope<PublicTripListResponse>>(`${this.baseUrl}/public-trips`, { params });
  }

  getBySlug(slug: string): Observable<ResponseEnvelope<PublicTrip>> {
    return this.http.get<ResponseEnvelope<PublicTrip>>(`${this.baseUrl}/public-trips/${encodeURIComponent(slug)}`);
  }

  getFeedback(publicationId:string): Observable<ResponseEnvelope<PublicFeedback>> { return this.http.get<ResponseEnvelope<PublicFeedback>>(`${this.baseUrl}/public-trips/${publicationId}/feedback`); }
  addComment(publicationId:string, content:string): Observable<ResponseEnvelope<PublicComment>> { return this.http.post<ResponseEnvelope<PublicComment>>(`${this.baseUrl}/public-trips/${publicationId}/comments`, { content }); }
  rate(publicationId:string, rating:number) { return this.http.put(`${this.baseUrl}/public-trips/${publicationId}/rating`, { rating }); }
  followStatus(authorId:string): Observable<ResponseEnvelope<{following:boolean}>> { return this.http.get<ResponseEnvelope<{following:boolean}>>(`${this.baseUrl}/authors/${authorId}/follow-status`); }
  follow(authorId:string) { return this.http.post(`${this.baseUrl}/authors/${authorId}/follow`, {}); }
  unfollow(authorId:string) { return this.http.delete(`${this.baseUrl}/authors/${authorId}/follow`); }
  listCommunityReports(status: 'open' | 'upheld' | 'dismissed' = 'open'): Observable<ResponseEnvelope<CommunityReport[]>> {
    return this.http.get<ResponseEnvelope<CommunityReport[]>>(`${this.baseUrl}/community-reports`, { params: { status } });
  }
  reviewCommunityReport(reportId: string, decision: 'uphold' | 'dismiss') {
    return this.http.patch<ResponseEnvelope<{ id: string; status: string }>>(`${this.baseUrl}/community-reports/${reportId}`, { decision });
  }
  reportTrip(publicationId: string, reason: string, details?: string) {
    return this.http.post(`${this.baseUrl}/public-trips/${publicationId}/report`, { reason, details: details || null });
  }
  sendBookingInquiry(publicationId: string, payload: { contact_name: string; contact_phone: string; travelers: number; message?: string | null }) {
    return this.http.post(`${this.baseUrl}/public-trips/${publicationId}/booking-inquiries`, payload);
  }
  sentBookingInquiries(): Observable<ResponseEnvelope<BookingInquiry[]>> { return this.http.get<ResponseEnvelope<BookingInquiry[]>>(`${this.baseUrl}/booking-inquiries/sent`); }
  receivedBookingInquiries(): Observable<ResponseEnvelope<BookingInquiry[]>> { return this.http.get<ResponseEnvelope<BookingInquiry[]>>(`${this.baseUrl}/booking-inquiries/received`); }
  updateBookingInquiryStatus(inquiryId: string, status: 'new' | 'contacted' | 'closed') {
    return this.http.patch<ResponseEnvelope<BookingInquiry>>(`${this.baseUrl}/booking-inquiries/${inquiryId}/status`, { status });
  }
  recommendations(): Observable<ResponseEnvelope<PersonalizedRecommendation[]>> { return this.http.get<ResponseEnvelope<PersonalizedRecommendation[]>>(`${this.baseUrl}/recommendations/me`); }
  hideRecommendation(publicationId:string) { return this.http.post(`${this.baseUrl}/recommendations/${publicationId}/hide`, {}); }

  listSaved(page = 1, limit = 12): Observable<ResponseEnvelope<PublicTripListResponse>> {
    return this.http.get<ResponseEnvelope<PublicTripListResponse>>(
      `${this.baseUrl}/public-trips/saved/me?page=${page}&limit=${limit}`,
    );
  }

  save(publicationId: string): Observable<ResponseEnvelope<{ saved: boolean }>> {
    return this.http.post<ResponseEnvelope<{ saved: boolean }>>(
      `${this.baseUrl}/public-trips/${publicationId}/save`,
      {},
    );
  }

  unsave(publicationId: string): Observable<ResponseEnvelope<{ saved: boolean }>> {
    return this.http.delete<ResponseEnvelope<{ saved: boolean }>>(
      `${this.baseUrl}/public-trips/${publicationId}/save`,
    );
  }

  previewImport(publicationId: string, payload: PublicTripImportRequest): Observable<ResponseEnvelope<any>> {
    return this.http.post<ResponseEnvelope<any>>(
      `${this.baseUrl}/public-trips/${publicationId}/import-preview`,
      payload,
    );
  }

  import(publicationId: string, payload: PublicTripImportRequest): Observable<ResponseEnvelope<any>> {
    return this.http.post<ResponseEnvelope<any>>(
      `${this.baseUrl}/public-trips/${publicationId}/import`,
      payload,
    );
  }
}
