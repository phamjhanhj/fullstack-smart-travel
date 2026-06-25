import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ResponseEnvelope } from './auth.service';

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

  private getHeaders() {
    const token = localStorage.getItem('access_token');
    return {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    };
  }

  listTrips(status?: string, page = 1, limit = 20): Observable<ResponseEnvelope<TripListResponse>> {
    let url = `${this.baseUrl}/trips?page=${page}&limit=${limit}`;
    if (status) {
      url += `&status=${status}`;
    }
    return this.http.get<ResponseEnvelope<TripListResponse>>(url, this.getHeaders());
  }

  createTrip(trip: CreateTripRequest): Observable<ResponseEnvelope<TripResponse>> {
    return this.http.post<ResponseEnvelope<TripResponse>>(
      `${this.baseUrl}/trips`,
      trip,
      this.getHeaders()
    );
  }

  getTripDetail(tripId: string): Observable<ResponseEnvelope<TripResponse>> {
    return this.http.get<ResponseEnvelope<TripResponse>>(
      `${this.baseUrl}/trips/${tripId}`,
      this.getHeaders()
    );
  }

  updateTrip(tripId: string, payload: UpdateTripRequest): Observable<ResponseEnvelope<TripResponse>> {
    return this.http.put<ResponseEnvelope<TripResponse>>(
      `${this.baseUrl}/trips/${tripId}`,
      payload,
      this.getHeaders()
    );
  }

  deleteTrip(tripId: string): Observable<ResponseEnvelope<any>> {
    return this.http.delete<ResponseEnvelope<any>>(
      `${this.baseUrl}/trips/${tripId}`,
      this.getHeaders()
    );
  }

  // Day plans & activities
  listDays(tripId: string): Observable<ResponseEnvelope<DayPlanResponse[]>> {
    return this.http.get<ResponseEnvelope<DayPlanResponse[]>>(
      `${this.baseUrl}/trips/${tripId}/days`,
      this.getHeaders()
    );
  }

  generateDays(tripId: string, overwrite = false): Observable<ResponseEnvelope<DayPlanBrief[]>> {
    return this.http.post<ResponseEnvelope<DayPlanBrief[]>>(
      `${this.baseUrl}/trips/${tripId}/days/generate`,
      { overwrite },
      this.getHeaders()
    );
  }

  addActivity(tripId: string, dayId: string, activity: CreateActivityRequest): Observable<ResponseEnvelope<ActivityResponse>> {
    return this.http.post<ResponseEnvelope<ActivityResponse>>(
      `${this.baseUrl}/trips/${tripId}/days/${dayId}/activities`,
      activity,
      this.getHeaders()
    );
  }

  updateActivity(activityId: string, activity: UpdateActivityRequest): Observable<ResponseEnvelope<ActivityResponse>> {
    return this.http.put<ResponseEnvelope<ActivityResponse>>(
      `${this.baseUrl}/activities/${activityId}`,
      activity,
      this.getHeaders()
    );
  }

  deleteActivity(activityId: string): Observable<ResponseEnvelope<any>> {
    return this.http.delete<ResponseEnvelope<any>>(
      `${this.baseUrl}/activities/${activityId}`,
      this.getHeaders()
    );
  }

  // AI Chat & suggestions
  getChatHistory(tripId: string): Observable<ResponseEnvelope<ChatHistoryItem[]>> {
    return this.http.get<ResponseEnvelope<ChatHistoryItem[]>>(
      `${this.baseUrl}/trips/${tripId}/chat/history`,
      this.getHeaders()
    );
  }

  sendMessage(tripId: string, message: string): Observable<ResponseEnvelope<ChatMessageResponse>> {
    return this.http.post<ResponseEnvelope<ChatMessageResponse>>(
      `${this.baseUrl}/trips/${tripId}/chat`,
      { message, stream: false },
      this.getHeaders()
    );
  }

  listSuggestions(tripId: string, status?: SuggestionStatus): Observable<ResponseEnvelope<AiSuggestionResponse[]>> {
    let url = `${this.baseUrl}/trips/${tripId}/suggestions`;
    if (status) {
      url += `?status=${status}`;
    }
    return this.http.get<ResponseEnvelope<AiSuggestionResponse[]>>(url, this.getHeaders());
  }

  updateSuggestionStatus(suggestionId: string, status: 'accepted' | 'rejected'): Observable<ResponseEnvelope<UpdateSuggestionStatusResponse>> {
    return this.http.patch<ResponseEnvelope<UpdateSuggestionStatusResponse>>(
      `${this.baseUrl}/suggestions/${suggestionId}/status`,
      { status },
      this.getHeaders()
    );
  }

  // Budget management
  getBudgetSummary(tripId: string): Observable<ResponseEnvelope<BudgetSummaryResponse>> {
    return this.http.get<ResponseEnvelope<BudgetSummaryResponse>>(
      `${this.baseUrl}/trips/${tripId}/budget`,
      this.getHeaders()
    );
  }

  listBudgetItems(tripId: string, category?: string): Observable<ResponseEnvelope<BudgetItemResponse[]>> {
    let url = `${this.baseUrl}/trips/${tripId}/budget/items`;
    if (category) {
      url += `?category=${category}`;
    }
    return this.http.get<ResponseEnvelope<BudgetItemResponse[]>>(url, this.getHeaders());
  }

  addBudgetItem(tripId: string, item: CreateBudgetItemRequest): Observable<ResponseEnvelope<BudgetItemResponse>> {
    return this.http.post<ResponseEnvelope<BudgetItemResponse>>(
      `${this.baseUrl}/trips/${tripId}/budget/items`,
      item,
      this.getHeaders()
    );
  }

  updateBudgetItem(itemId: string, item: UpdateBudgetItemRequest): Observable<ResponseEnvelope<BudgetItemResponse>> {
    return this.http.put<ResponseEnvelope<BudgetItemResponse>>(
      `${this.baseUrl}/budget/items/${itemId}`,
      item,
      this.getHeaders()
    );
  }

  deleteBudgetItem(itemId: string): Observable<ResponseEnvelope<any>> {
    return this.http.delete<ResponseEnvelope<any>>(
      `${this.baseUrl}/budget/items/${itemId}`,
      this.getHeaders()
    );
  }

  // Location discovery
  searchLocations(q: string, destination?: string, limit = 10): Observable<ResponseEnvelope<LocationResponse[]>> {
    let url = `${this.baseUrl}/locations/search?q=${q}&limit=${limit}`;
    if (destination) {
      url += `&destination=${destination}`;
    }
    return this.http.get<ResponseEnvelope<LocationResponse[]>>(url, this.getHeaders());
  }

  searchNearby(lat: number, lng: number, category?: string, radius = 1000): Observable<ResponseEnvelope<NearbyLocationResponse[]>> {
    let url = `${this.baseUrl}/locations/nearby?lat=${lat}&lng=${lng}&radius=${radius}`;
    if (category) {
      url += `&category=${category}`;
    }
    return this.http.get<ResponseEnvelope<NearbyLocationResponse[]>>(url, this.getHeaders());
  }

  upsertLocation(payload: UpsertLocationRequest): Observable<ResponseEnvelope<UpsertLocationResponse>> {
    return this.http.post<ResponseEnvelope<UpsertLocationResponse>>(
      `${this.baseUrl}/locations`,
      payload,
      this.getHeaders()
    );
  }
}

