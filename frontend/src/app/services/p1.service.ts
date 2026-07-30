import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { API_BASE_URL } from '../config/api.config';
import { ResponseEnvelope } from './auth.service';

export interface UserNotification { id:string; type:string; title:string; message:string; action_url:string|null; payload_json:Record<string,unknown>; read_at:string|null; created_at:string; }
export interface NotificationList { items:UserNotification[]; unread_count:number; }
export interface JournalEntry { id:string; trip_id:string; user_id:string; activity_id:string|null; entry_date:string; note:string|null; photo_urls:string[]; actual_cost:number|null; rating:number|null; is_check_in:boolean; created_at:string; updated_at:string|null; }
export interface SavedCollection { id:string; name:string; description:string|null; item_count:number; created_at:string; }
export interface EmergencyOption { id:string; title:string; description:string; impact:string; requires_confirmation:boolean; }

@Injectable({ providedIn: 'root' })
export class P1Service {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = inject(API_BASE_URL);
  listNotifications(): Observable<ResponseEnvelope<NotificationList>> { return this.http.get<ResponseEnvelope<NotificationList>>(`${this.baseUrl}/notifications`); }
  readNotification(id:string) { return this.http.patch(`${this.baseUrl}/notifications/${id}/read`, {}); }
  readAllNotifications() { return this.http.patch(`${this.baseUrl}/notifications/read-all`, {}); }
  listJournal(tripId:string): Observable<ResponseEnvelope<JournalEntry[]>> { return this.http.get<ResponseEnvelope<JournalEntry[]>>(`${this.baseUrl}/trips/${tripId}/journal`); }
  createJournal(tripId:string, payload:Partial<JournalEntry>): Observable<ResponseEnvelope<JournalEntry>> { return this.http.post<ResponseEnvelope<JournalEntry>>(`${this.baseUrl}/trips/${tripId}/journal`, payload); }
  listCollections(): Observable<ResponseEnvelope<SavedCollection[]>> { return this.http.get<ResponseEnvelope<SavedCollection[]>>(`${this.baseUrl}/collections`); }
  createCollection(name:string, description?:string) { return this.http.post(`${this.baseUrl}/collections`, { name, description: description || null }); }
  addToCollection(collectionId:string, publicationId:string) { return this.http.post(`${this.baseUrl}/collections/${collectionId}/items/${publicationId}`, {}); }
  emergencyPreview(tripId:string, reason:string, activityId?:string) : Observable<ResponseEnvelope<EmergencyOption[]>> { return this.http.post<ResponseEnvelope<EmergencyOption[]>>(`${this.baseUrl}/trips/${tripId}/emergency/preview`, { reason, activity_id: activityId || null }); }
}
