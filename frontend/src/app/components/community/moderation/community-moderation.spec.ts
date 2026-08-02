import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { CommunityReport, PublicTrip, PublicTripService } from '../../../services/public-trip.service';
import { CommunityModerationComponent } from './community-moderation';

describe('CommunityModerationComponent', () => {
  let fixture: ComponentFixture<CommunityModerationComponent>;
  let service: jasmine.SpyObj<PublicTripService>;

  const report: CommunityReport = {
    id: 'report-1',
    reporter_user_id: 'reporter-1',
    publication_id: 'publication-1',
    reported_user_id: null,
    reason: 'misleading',
    details: 'Thông tin lịch trình không đúng.',
    status: 'open',
    created_at: '2026-08-02T03:19:00Z',
    target: {
      type: 'trip',
      id: 'publication-1',
      title: 'Khám phá Đà Nẵng',
      destination: 'Đà Nẵng',
      author_name: 'Nguyễn An',
    },
  };

  const trip = {
    id: 'publication-1',
    slug: 'kham-pha-da-nang',
    title: 'Khám phá Đà Nẵng',
    summary: 'Lịch trình trải nghiệm Đà Nẵng.',
    destination: 'Đà Nẵng',
    cover_image_url: null,
    visibility: 'public',
    status: 'published',
    moderation_status: 'approved',
    duration_days: 1,
    actual_total_cost: 500000,
    actual_cost_per_person: 500000,
    overall_rating: 4.5,
    author: { id: 'author-1', full_name: 'Nguyễn An', avatar_url: null },
    snapshot_json: {
      days: [{
        day_number: 1,
        title: 'Trung tâm thành phố',
        actual_day_cost: 500000,
        activities: [{
          source_activity_id: 'activity-1',
          location_id: null,
          title: 'Cầu Rồng',
          type: 'sightseeing',
          actual_status: 'visited',
          author_verdict: 'recommended',
          start_time: '08:00',
          end_time: '09:00',
        }],
      }],
    },
  } as unknown as PublicTrip;

  beforeEach(async () => {
    service = jasmine.createSpyObj<PublicTripService>('PublicTripService', [
      'listCommunityReports',
      'getCommunityReportTrip',
      'reviewCommunityReport',
    ]);
    service.listCommunityReports.and.returnValue(of({ data: [report] } as any));
    service.getCommunityReportTrip.and.returnValue(of({ data: trip } as any));

    await TestBed.configureTestingModule({
      imports: [CommunityModerationComponent],
      providers: [{ provide: PublicTripService, useValue: service }],
    }).compileComponents();

    fixture = TestBed.createComponent(CommunityModerationComponent);
    fixture.detectChanges();
  });

  it('opens the reported trip preview from the report card', () => {
    const viewButton = Array.from(
      fixture.nativeElement.querySelectorAll('button') as NodeListOf<HTMLButtonElement>,
    ).find(button => button.textContent?.includes('Xem chuyến đi'));

    expect(viewButton).toBeTruthy();
    viewButton!.click();
    fixture.detectChanges();

    expect(service.getCommunityReportTrip).toHaveBeenCalledOnceWith(report.id);
    const dialog = fixture.nativeElement.querySelector('[role="dialog"]') as HTMLElement | null;
    expect(dialog).not.toBeNull();
    expect(dialog?.textContent).toContain('Khám phá Đà Nẵng');
    expect(dialog?.textContent).toContain('Cầu Rồng');
  });
});
