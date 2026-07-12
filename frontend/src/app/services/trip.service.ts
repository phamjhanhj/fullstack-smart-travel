import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ResponseEnvelope } from './auth.service';

export type TripRole = 'owner' | 'viewer' | 'editor';
export type TripShareRole = 'viewer' | 'editor';
export type TripAccessType = 'owner' | 'shared';
export type TripScope = 'owned' | 'shared' | 'all';

export interface TripOwnerInfo {
  id: string;
  email: string;
  full_name: string;
  avatar_url: string | null;
}

export interface TripListItem {
  id: string;
  title: string;
  destination: string;
  start_date: string; // ISO date string (YYYY-MM-DD)
  end_date: string;   // ISO date string (YYYY-MM-DD)
  budget: number | null;
  num_travelers: number;
  status: 'draft' | 'active' | 'completed';
  cover_image_url: string | null;
  created_at: string;
  owner: TripOwnerInfo;
  access_type: TripAccessType;
  role: TripRole;
}

export interface TripListResponse {
  items: TripListItem[];
  total: number;
  page: number;
  limit: number;
}

export interface CreateTripRequest {
  title: string;
  destination: string;
  start_date: string; // YYYY-MM-DD
  end_date: string;   // YYYY-MM-DD
  budget?: number | null;
  num_travelers: number;
  preferences?: string | null;
}

export interface UpdateTripRequest {
  title?: string;
  destination?: string;
  start_date?: string;
  end_date?: string;
  budget?: number | null;
  num_travelers?: number;
  preferences?: string | null;
  status?: 'draft' | 'active' | 'completed';
  cover_image_url?: string | null;
}

export interface TripResponse {
  id: string;
  title: string;
  destination: string;
  start_date: string;
  end_date: string;
  budget: number | null;
  num_travelers: number;
  status: 'draft' | 'active' | 'completed';
  preferences: string | null;
  cover_image_url: string | null;
  created_at: string;
  updated_at: string | null;
  owner: TripOwnerInfo;
  access_type: TripAccessType;
  role: TripRole;
}

export interface TripParticipant {
  id: string;
  trip_id: string;
  role: TripShareRole;
  user: TripOwnerInfo;
  invited_by: TripOwnerInfo;
  created_at: string;
  updated_at: string | null;
}

export interface TripInvite {
  id: string;
  trip_id: string;
  email: string | null;
  role: TripShareRole;
  status: 'pending' | 'accepted' | 'revoked' | 'rejected';
  invited_by: TripOwnerInfo;
  accepted_by: TripOwnerInfo | null;
  expires_at: string;
  created_at: string;
  updated_at: string | null;
  token: string | null;
  accept_url: string | null;
}

export interface TripInviteTripBrief {
  id: string;
  title: string;
  destination: string;
  start_date: string;
  end_date: string;
  cover_image_url: string | null;
}

export interface TripInviteNotification extends TripInvite {
  trip: TripInviteTripBrief;
}

export interface TripSharesResponse {
  participants: TripParticipant[];
  invites: TripInvite[];
}

export interface CreateTripInviteRequest {
  email?: string | null;
  role: TripShareRole;
  expires_in_days?: number;
}

export interface AcceptTripInviteResponse {
  trip_id: string;
  role: TripShareRole;
}

export interface TripHistoryChange {
  field: string;
  label: string;
  before: any;
  after: any;
}

export interface TripHistoryEvent {
  id: string;
  trip_id: string;
  actor: TripOwnerInfo | null;
  entity_type: string;
  entity_id: string | null;
  action: string;
  summary: string;
  changes: TripHistoryChange[];
  metadata: Record<string, any>;
  created_at: string;
}

export interface TripHistoryListResponse {
  items: TripHistoryEvent[];
  total: number;
  page: number;
  limit: number;
}

// Module 4: Day Plans & Activities Interfaces
export type ActivityType = 'meal' | 'attraction' | 'hotel' | 'transport' | 'other';

export interface LocationBrief {
  id: string;
  name: string;
  address?: string | null;
  lat?: number | null;
  lng?: number | null;
  category?: string | null;
  photo_url?: string | null;
  rating?: number | null;
}

export interface ActivityResponse {
  id: string;
  day_plan_id: string;
  title: string;
  description: string | null;
  type: ActivityType | null;
  start_time: string | null; // HH:MM
  end_time: string | null;   // HH:MM
  estimated_cost: number | null;
  order_index: number;
  booking_url: string | null;
  notes: string | null;
  location_id: string | null;
  location: LocationBrief | null;
  updated_at: string | null;
}

export interface DayPlanResponse {
  id: string;
  trip_id: string;
  day_number: number;
  date: string; // YYYY-MM-DD
  activities: ActivityResponse[];
}

export interface CreateActivityRequest {
  title: string;
  description?: string | null;
  type: ActivityType;
  location_id?: string | null;
  start_time?: string | null; // HH:MM
  end_time?: string | null;   // HH:MM
  estimated_cost?: number | null;
  order_index?: number;
  booking_url?: string | null;
  notes?: string | null;
}

export interface UpdateActivityRequest {
  title?: string | null;
  description?: string | null;
  type?: ActivityType | null;
  location_id?: string | null;
  start_time?: string | null; // HH:MM
  end_time?: string | null;   // HH:MM
  estimated_cost?: number | null;
  booking_url?: string | null;
  notes?: string | null;
}

export interface DayPlanBrief {
  id: string;
  day_number: number;
  date: string;
}

export interface GenerateDaysRequest {
  overwrite: boolean;
  must_visit?: string[];
  avoid_places?: string[];
  interest_weights?: Record<string, number>;
  pace?: 'relaxed' | 'balanced' | 'packed';
  budget_mode?: 'strict' | 'flexible_15' | 'comfort';
  prioritize_user_places?: 'balanced' | 'high';
  transport_mode?: 'walking' | 'motorbike' | 'car' | 'taxi' | 'public_transport' | 'mixed';
  departure_location?: string | null;
  departure_time?: string | null;
  estimated_travel_hours?: number | null;
  arrival_transport?: string | null;
  daily_start_time?: string | null;
  daily_end_time?: string | null;
  dietary_notes?: string | null;
  mobility_notes?: string | null;
  ai?: boolean;
}

export interface ItineraryGenerationSummary {
  total_estimated_cost: number;
  budget_limit: number | null;
  budget_used_percent: number | null;
  included_user_places: string[];
  missing_user_places: string[];
  candidate_places_count: number;
  warnings: string[];
}

export interface GenerateDaysResponse {
  days: DayPlanBrief[];
  summary: ItineraryGenerationSummary;
}

// Module 7: AI Chat & Suggestions Interfaces
export type ChatRole = 'user' | 'assistant';
export type SuggestionStatus = 'pending' | 'accepted' | 'rejected';

export interface ChatMessageResponse {
  message_id: string;
  role: string;
  message: string;
  suggestion_id: string | null;
  created_at: string;
}

export interface ChatHistoryItem {
  id: string;
  role: ChatRole;
  message: string;
  created_at: string;
}

export interface AiSuggestionResponse {
  id: string;
  trip_id: string;
  type: string;
  status: SuggestionStatus;
  content_json: any;
  created_at: string;
}

export interface UpdateSuggestionStatusResponse {
  suggestion_id: string;
  status: string;
  activities_created: number;
}

// Module 6: Budget Interfaces
export type BudgetCategory = 'food' | 'transport' | 'hotel' | 'activity' | 'other';

export interface BudgetItemResponse {
  id: string;
  trip_id: string;
  category: BudgetCategory;
  label: string;
  planned_amount: number;
  actual_amount: number;
  date: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface CreateBudgetItemRequest {
  category: BudgetCategory;
  label: string;
  planned_amount: number;
  actual_amount: number;
  date?: string | null;
}

export interface UpdateBudgetItemRequest {
  category?: BudgetCategory | null;
  label?: string | null;
  planned_amount?: number | null;
  actual_amount?: number | null;
  date?: string | null;
}

export interface CategoryBudgetSummary {
  category: string;
  label: string;
  planned: number;
  actual: number;
  itinerary_planned: number;
  items_count: number;
}

export interface BudgetSummaryResponse {
  trip_id: string;
  budget_total: number | null;
  budget_planned: number;
  budget_actual: number;
  budget_remaining: number;
  budget_itinerary_planned: number;
  overspent: boolean;
  categories: CategoryBudgetSummary[];
}


// Module 5: Locations Interfaces
export type LocationCategory = 'restaurant' | 'attraction' | 'hotel' | 'cafe' | 'other';

export interface LocationResponse {
  id: string;
  name: string;
  address: string | null;
  lat: number | null;
  lng: number | null;
  category: string | null;
  google_place_id: string | null;
  photo_url: string | null;
  rating: number | null;
}

export interface NearbyLocationResponse extends LocationResponse {
  distance_meters: number | null;
}

export interface UpsertLocationRequest {
  name: string;
  address?: string | null;
  lat?: number | null;
  lng?: number | null;
  category?: LocationCategory | null;
  google_place_id?: string | null;
  photo_url?: string | null;
  rating?: number | null;
}

export interface UpsertLocationResponse {
  id: string;
  name: string;
  google_place_id: string | null;
}

@Injectable({
  providedIn: 'root',
})
export class TripService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = 'http://localhost:8000/api';

  listTrips(status?: string, page = 1, limit = 20, scope: TripScope = 'owned'): Observable<ResponseEnvelope<TripListResponse>> {
    let url = `${this.baseUrl}/trips?page=${page}&limit=${limit}&scope=${scope}`;
    if (status) {
      url += `&status=${status}`;
    }
    return this.http.get<ResponseEnvelope<TripListResponse>>(url);
  }

  createTrip(trip: CreateTripRequest): Observable<ResponseEnvelope<TripResponse>> {
    return this.http.post<ResponseEnvelope<TripResponse>>(
      `${this.baseUrl}/trips`,
      trip
    );
  }

  getTripDetail(tripId: string): Observable<ResponseEnvelope<TripResponse>> {
    return this.http.get<ResponseEnvelope<TripResponse>>(
      `${this.baseUrl}/trips/${tripId}`
    );
  }

  updateTrip(tripId: string, payload: UpdateTripRequest): Observable<ResponseEnvelope<TripResponse>> {
    return this.http.put<ResponseEnvelope<TripResponse>>(
      `${this.baseUrl}/trips/${tripId}`,
      payload
    );
  }

  deleteTrip(tripId: string): Observable<ResponseEnvelope<any>> {
    return this.http.delete<ResponseEnvelope<any>>(
      `${this.baseUrl}/trips/${tripId}`
    );
  }

  listTripShares(tripId: string): Observable<ResponseEnvelope<TripSharesResponse>> {
    return this.http.get<ResponseEnvelope<TripSharesResponse>>(
      `${this.baseUrl}/trips/${tripId}/shares`
    );
  }

  createTripInvite(tripId: string, payload: CreateTripInviteRequest): Observable<ResponseEnvelope<TripInvite>> {
    return this.http.post<ResponseEnvelope<TripInvite>>(
      `${this.baseUrl}/trips/${tripId}/shares/invites`,
      payload
    );
  }

  updateTripParticipant(tripId: string, participantId: string, role: TripShareRole): Observable<ResponseEnvelope<TripParticipant>> {
    return this.http.patch<ResponseEnvelope<TripParticipant>>(
      `${this.baseUrl}/trips/${tripId}/shares/participants/${participantId}`,
      { role }
    );
  }

  revokeTripParticipant(tripId: string, participantId: string): Observable<ResponseEnvelope<any>> {
    return this.http.delete<ResponseEnvelope<any>>(
      `${this.baseUrl}/trips/${tripId}/shares/participants/${participantId}`
    );
  }

  revokeTripInvite(inviteId: string): Observable<ResponseEnvelope<any>> {
    return this.http.delete<ResponseEnvelope<any>>(
      `${this.baseUrl}/trip-invites/${inviteId}`
    );
  }

  acceptTripInvite(token: string): Observable<ResponseEnvelope<AcceptTripInviteResponse>> {
    return this.http.post<ResponseEnvelope<AcceptTripInviteResponse>>(
      `${this.baseUrl}/trip-invites/${token}/accept`,
      {}
    );
  }

  listPendingTripInvites(): Observable<ResponseEnvelope<TripInviteNotification[]>> {
    return this.http.get<ResponseEnvelope<TripInviteNotification[]>>(
      `${this.baseUrl}/trip-invites/pending`
    );
  }

  acceptEmailTripInvite(inviteId: string): Observable<ResponseEnvelope<AcceptTripInviteResponse>> {
    return this.http.post<ResponseEnvelope<AcceptTripInviteResponse>>(
      `${this.baseUrl}/trip-invites/${inviteId}/accept-email`,
      {}
    );
  }

  rejectTripInvite(inviteId: string): Observable<ResponseEnvelope<any>> {
    return this.http.post<ResponseEnvelope<any>>(
      `${this.baseUrl}/trip-invites/${inviteId}/reject`,
      {}
    );
  }

  listTripHistory(
    tripId: string,
    page = 1,
    limit = 30,
    filters?: { entity_type?: string; action?: string },
  ): Observable<ResponseEnvelope<TripHistoryListResponse>> {
    let url = `${this.baseUrl}/trips/${tripId}/history?page=${page}&limit=${limit}`;
    if (filters?.entity_type) {
      url += `&entity_type=${encodeURIComponent(filters.entity_type)}`;
    }
    if (filters?.action) {
      url += `&action=${encodeURIComponent(filters.action)}`;
    }
    return this.http.get<ResponseEnvelope<TripHistoryListResponse>>(url);
  }

  // Day plans & activities
  listDays(tripId: string): Observable<ResponseEnvelope<DayPlanResponse[]>> {
    return this.http.get<ResponseEnvelope<DayPlanResponse[]>>(
      `${this.baseUrl}/trips/${tripId}/days`
    );
  }

  generateDays(
    tripId: string,
    overwriteOrPayload: boolean | GenerateDaysRequest = false,
  ): Observable<ResponseEnvelope<GenerateDaysResponse>> {
    const payload: GenerateDaysRequest =
      typeof overwriteOrPayload === 'boolean'
        ? {
            overwrite: overwriteOrPayload,
            pace: 'balanced',
            budget_mode: 'flexible_15',
            prioritize_user_places: 'balanced',
          }
        : overwriteOrPayload;

    return this.http.post<ResponseEnvelope<GenerateDaysResponse>>(
      `${this.baseUrl}/trips/${tripId}/days/generate`,
      payload
    );
  }

  addActivity(tripId: string, dayId: string, activity: CreateActivityRequest): Observable<ResponseEnvelope<ActivityResponse>> {
    return this.http.post<ResponseEnvelope<ActivityResponse>>(
      `${this.baseUrl}/trips/${tripId}/days/${dayId}/activities`,
      activity
    );
  }

  updateActivity(activityId: string, activity: UpdateActivityRequest): Observable<ResponseEnvelope<ActivityResponse>> {
    return this.http.put<ResponseEnvelope<ActivityResponse>>(
      `${this.baseUrl}/activities/${activityId}`,
      activity
    );
  }

  deleteActivity(activityId: string): Observable<ResponseEnvelope<any>> {
    return this.http.delete<ResponseEnvelope<any>>(
      `${this.baseUrl}/activities/${activityId}`
    );
  }

  reorderActivities(
    dayPlanId: string,
    items: { id: string; order_index: number }[],
  ): Observable<ResponseEnvelope<any>> {
    return this.http.patch<ResponseEnvelope<any>>(
      `${this.baseUrl}/activities/reorder`,
      { day_plan_id: dayPlanId, items }
    );
  }

  // AI Chat & suggestions
  getChatHistory(tripId: string): Observable<ResponseEnvelope<ChatHistoryItem[]>> {
    return this.http.get<ResponseEnvelope<ChatHistoryItem[]>>(
      `${this.baseUrl}/trips/${tripId}/chat/history`
    );
  }

  sendMessage(tripId: string, message: string): Observable<ResponseEnvelope<ChatMessageResponse>> {
    return this.http.post<ResponseEnvelope<ChatMessageResponse>>(
      `${this.baseUrl}/trips/${tripId}/chat`,
      { message, stream: false }
    );
  }

  listSuggestions(tripId: string, status?: SuggestionStatus): Observable<ResponseEnvelope<AiSuggestionResponse[]>> {
    let url = `${this.baseUrl}/trips/${tripId}/suggestions`;
    if (status) {
      url += `?status=${status}`;
    }
    return this.http.get<ResponseEnvelope<AiSuggestionResponse[]>>(url);
  }

  updateSuggestionStatus(suggestionId: string, status: 'accepted' | 'rejected'): Observable<ResponseEnvelope<UpdateSuggestionStatusResponse>> {
    return this.http.patch<ResponseEnvelope<UpdateSuggestionStatusResponse>>(
      `${this.baseUrl}/suggestions/${suggestionId}/status`,
      { status }
    );
  }

  // Budget management
  getBudgetSummary(tripId: string): Observable<ResponseEnvelope<BudgetSummaryResponse>> {
    return this.http.get<ResponseEnvelope<BudgetSummaryResponse>>(
      `${this.baseUrl}/trips/${tripId}/budget`
    );
  }

  listBudgetItems(tripId: string, category?: string): Observable<ResponseEnvelope<BudgetItemResponse[]>> {
    let url = `${this.baseUrl}/trips/${tripId}/budget/items`;
    if (category) {
      url += `?category=${category}`;
    }
    return this.http.get<ResponseEnvelope<BudgetItemResponse[]>>(url);
  }

  addBudgetItem(tripId: string, item: CreateBudgetItemRequest): Observable<ResponseEnvelope<BudgetItemResponse>> {
    return this.http.post<ResponseEnvelope<BudgetItemResponse>>(
      `${this.baseUrl}/trips/${tripId}/budget/items`,
      item
    );
  }

  updateBudgetItem(itemId: string, item: UpdateBudgetItemRequest): Observable<ResponseEnvelope<BudgetItemResponse>> {
    return this.http.put<ResponseEnvelope<BudgetItemResponse>>(
      `${this.baseUrl}/budget/items/${itemId}`,
      item
    );
  }

  deleteBudgetItem(itemId: string): Observable<ResponseEnvelope<any>> {
    return this.http.delete<ResponseEnvelope<any>>(
      `${this.baseUrl}/budget/items/${itemId}`
    );
  }

  // Location discovery
  searchLocations(q: string, destination?: string, limit = 15): Observable<ResponseEnvelope<LocationResponse[]>> {
    let url = `${this.baseUrl}/locations/search?q=${encodeURIComponent(q)}&limit=${limit}`;
    if (destination) {
      url += `&destination=${encodeURIComponent(destination)}`;
    }
    return this.http.get<ResponseEnvelope<LocationResponse[]>>(url);
  }

  searchNearby(lat: number, lng: number, category?: string, radius = 1000): Observable<ResponseEnvelope<NearbyLocationResponse[]>> {
    let url = `${this.baseUrl}/locations/nearby?lat=${lat}&lng=${lng}&radius=${radius}`;
    if (category) {
      url += `&category=${category}`;
    }
    return this.http.get<ResponseEnvelope<NearbyLocationResponse[]>>(url);
  }

  upsertLocation(payload: UpsertLocationRequest): Observable<ResponseEnvelope<UpsertLocationResponse>> {
    return this.http.post<ResponseEnvelope<UpsertLocationResponse>>(
      `${this.baseUrl}/locations`,
      payload
    );
  }
}
