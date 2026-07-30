import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { map, tap } from 'rxjs/operators';
import { ResponseEnvelope } from './auth.service';
import { API_BASE_URL } from '../config/api.config';

export interface PhotoResponse {
  destination: string;
  photos: string[];
  photo_details?: PhotoDetail[];
  source: string;
}

export interface PhotoDetail {
  url: string;
  thumbnail_url: string;
  source: string;
  attribution: string;
  alt: string;
  width: number;
  height: number;
  quality_score: number;
}

export interface BestRatedPlace {
  name: string;
  rating: number | null;
  photo_url: string | null;
}

@Injectable({
  providedIn: 'root',
})
export class PlacePhotoService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = inject(API_BASE_URL);
  private readonly cache = new Map<string, string[]>();
  private readonly detailCache = new Map<string, PhotoDetail[]>();

  getPhotos(destination: string, count = 3): Observable<string[]> {
    const key = destination.toLowerCase().trim();
    if (this.cache.has(key)) {
      return of(this.cache.get(key)!);
    }
    return this.http
      .get<
        ResponseEnvelope<PhotoResponse>
      >(`${this.baseUrl}/places/photo?query=${encodeURIComponent(destination)}&count=${count}`)
      .pipe(
        map((res) => {
          const details = res.data.photo_details || [];
          if (details.length > 0) {
            this.detailCache.set(key, details);
          }
          return res.data.photos || details.map((photo) => photo.url);
        }),
        tap((photos) => {
          if (photos.length > 0) {
            this.cache.set(key, photos);
          }
        }),
      );
  }

  getPhotoDetails(destination: string, count = 3): Observable<PhotoDetail[]> {
    const key = destination.toLowerCase().trim();
    if (this.detailCache.has(key)) {
      return of(this.detailCache.get(key)!);
    }
    return this.http
      .get<
        ResponseEnvelope<PhotoResponse>
      >(`${this.baseUrl}/places/photo?query=${encodeURIComponent(destination)}&count=${count}`)
      .pipe(
        map((res) => {
          const details =
            res.data.photo_details ||
            (res.data.photos || []).map((url, idx) => ({
              url,
              thumbnail_url: url,
              source: res.data.source,
              attribution: res.data.source,
              alt: `${destination} travel photo ${idx + 1}`,
              width: 600,
              height: 400,
              quality_score: 1 - idx * 0.08,
            }));
          this.detailCache.set(key, details);
          this.cache.set(
            key,
            details.map((photo) => photo.url),
          );
          return details;
        }),
      );
  }

  getBestRatedPlaces(query: string, count = 5): Observable<BestRatedPlace[]> {
    return this.http
      .get<
        ResponseEnvelope<{ query: string; places: BestRatedPlace[] }>
      >(`${this.baseUrl}/places/best-rated?query=${encodeURIComponent(query)}&count=${count}`)
      .pipe(map((res) => res.data.places || []));
  }
}
