import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { map, catchError } from 'rxjs/operators';

export interface OsrmRouteSegment {
  distanceMeters: number;
  durationSeconds: number;
  geometryCoords: [number, number][]; // [lat, lng] for Leaflet polyline
}

export interface OsrmRouteResponse {
  totalDistanceMeters: number;
  totalDurationSeconds: number;
  segments: OsrmRouteSegment[];
}

@Injectable({
  providedIn: 'root',
})
export class OsrmService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = 'https://router.project-osrm.org';

  /**
   * Get routing from OSRM demo server for list of waypoints.
   * @param waypoints array of [lat, lng]
   */
  getRoute(waypoints: [number, number][]): Observable<OsrmRouteResponse | null> {
    if (!waypoints || waypoints.length < 2) {
      return of(null);
    }

    // OSRM coordinates are in lng,lat format
    const coordString = waypoints.map(wp => `${wp[1]},${wp[0]}`).join(';');
    const url = `${this.baseUrl}/route/v1/driving/${coordString}?overview=full&geometries=geojson&steps=false`;

    return this.http.get<any>(url).pipe(
      map(res => {
        if (!res || !res.routes || res.routes.length === 0) {
          return this.getHaversineFallback(waypoints);
        }

        const route = res.routes[0];
        const legs = route.legs || [];
        const segments: OsrmRouteSegment[] = [];

        // If OSRM returned legs, use their distance/duration.
        // Otherwise, split the overall geometry.
        for (let i = 0; i < waypoints.length - 1; i++) {
          const leg = legs[i];
          const fromWp = waypoints[i];
          const toWp = waypoints[i + 1];

          let distance = leg ? leg.distance : this.haversineDistance(fromWp, toWp) * 1000;
          let duration = leg ? leg.duration : (distance / 11.1); // ~40km/h average speed fallback

          segments.push({
            distanceMeters: distance,
            durationSeconds: duration,
            geometryCoords: [fromWp, toWp]
          });
        }

        // Parse route coordinates: OSRM returns [lng, lat], convert to [lat, lng] for Leaflet
        let allRouteCoords: [number, number][] = [];
        if (route.geometry && route.geometry.coordinates) {
          allRouteCoords = route.geometry.coordinates.map((c: any) => [c[1], c[0]] as [number, number]);
        }

        // Distribute coordinates to segments based on nearest waypoint projection
        if (allRouteCoords.length > 0) {
          let currentCoordIdx = 0;
          for (let i = 0; i < segments.length; i++) {
            const nextWaypoint = waypoints[i + 1];
            const segCoords: [number, number][] = [waypoints[i]];

            // Collect coordinates until we are closest to nextWaypoint
            while (currentCoordIdx < allRouteCoords.length) {
              const coord = allRouteCoords[currentCoordIdx];
              // check if this coord is extremely close to the next waypoint
              const distToNext = this.haversineDistance(coord, nextWaypoint);
              
              segCoords.push(coord);
              currentCoordIdx++;

              if (distToNext < 0.05) { // within 50 meters
                break;
              }
            }
            segCoords.push(nextWaypoint);
            segments[i].geometryCoords = segCoords;
          }
        }

        return {
          totalDistanceMeters: route.distance,
          totalDurationSeconds: route.duration,
          segments
        };
      }),
      catchError(() => {
        // Fallback to straight line Haversine routing
        return of(this.getHaversineFallback(waypoints));
      })
    );
  }

  /**
   * Fallback using straight lines and Haversine formula.
   */
  private getHaversineFallback(waypoints: [number, number][]): OsrmRouteResponse {
    const segments: OsrmRouteSegment[] = [];
    let totalDist = 0;
    let totalDur = 0;

    for (let i = 0; i < waypoints.length - 1; i++) {
      const from = waypoints[i];
      const to = waypoints[i + 1];
      const distanceKm = this.haversineDistance(from, to);
      const distanceMeters = distanceKm * 1000;
      // Assume average speed 30km/h (8.33 m/s) in city traffic
      const durationSeconds = distanceMeters / 8.33;

      totalDist += distanceMeters;
      totalDur += durationSeconds;

      segments.push({
        distanceMeters,
        durationSeconds,
        geometryCoords: [from, to]
      });
    }

    return {
      totalDistanceMeters: totalDist,
      totalDurationSeconds: totalDur,
      segments
    };
  }

  /**
   * Distance in kilometers using Haversine formula.
   */
  haversineDistance(coords1: [number, number], coords2: [number, number]): number {
    const lon1 = coords1[1];
    const lat1 = coords1[0];
    const lon2 = coords2[1];
    const lat2 = coords2[0];

    const R = 6371; // km
    const dLat = this.toRad(lat2 - lat1);
    const dLon = this.toRad(lon2 - lon1);
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(this.toRad(lat1)) * Math.cos(this.toRad(lat2)) *
      Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  }

  private toRad(value: number): number {
    return (value * Math.PI) / 180;
  }
}
