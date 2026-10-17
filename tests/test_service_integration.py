"""Domain/MCP integration regressions with pinned synthetic exception snapshots."""
import copy
from datetime import datetime, timezone
import tempfile
import unittest
from unittest.mock import patch

import published_full as pf
import server
import service_updates as su
from service_updates_source import PageResponse
import shuttle_now


def html(body):
    return '<html><body><h2>Shuttle Service Updates</h2><h3>Intercampus notice</h3><p>'+body+'</p></body></html>'


class ServiceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.now=datetime(2026,10,16,21,tzinfo=timezone.utc)
        self.state=su.refresh(root=self.temp.name,now=self.now,force=True,fetcher=lambda **k:PageResponse(200,
            html('No service at Central L on October 16, 2026 between 4:30 p.m. and 11:10 p.m.')))
        token=su.PINNED.set(self.state);self.addCleanup(su.PINNED.reset,token)

    def test_departures_preserve_original_fields_and_counts(self):
        a=datetime.fromisoformat('2026-10-16T16:20:00-05:00');b=a.replace(hour=17,minute=0)
        out=pf.lookup('Central L (EB)',a,b)
        self.assertEqual(out['total_matched'],1)
        self.assertEqual(out['arrivals'][0]['scheduled_departure_local'],'2026-10-16T16:32:00-05:00')
        self.assertIsNone(out['arrivals'][0]['reported_expected_arrival_local'])
        self.assertEqual(out['arrivals'][0]['service_impact'],'unavailable')
        self.assertFalse(out['normal_service_confirmed'])

    def test_journeys_excluded_but_original_options_and_totals_retained(self):
        out=server.plan_scheduled_shuttle_trip('Central L (EB)','Ward Building','2026-10-16T16:20')
        self.assertEqual(out['options'],[])
        self.assertGreater(out['total_excluded_options'],0)
        self.assertEqual(out['total_matching_scheduled_rides'],out['total_excluded_options'])
        self.assertEqual(out['scheduled_options'][0]['board_time_local'],'2026-10-16T16:32:00-05:00')
        self.assertEqual(out['excluded_options'][0]['recommendation_status'],'excluded')

    def test_uncertain_year_downgrades_does_not_remove(self):
        uncertain=copy.deepcopy(self.state)
        n=uncertain['notices'][0];n['windows']=[];n['warnings']=['Effective year is missing.']
        for e in n['effects']:e['certain']=False
        with patch.object(su,'snapshot',return_value=uncertain):
            token=su.PINNED.set(uncertain)
            try:out=pf.plan_trip('Central L (EB)','Ward Building','2026-10-16T16:20')
            finally:su.PINNED.reset(token)
        self.assertTrue(out['options']);self.assertFalse(out['excluded_options'])
        self.assertEqual(out['options'][0]['recommendation_status'],'provisional')

    def test_boarding_before_stop_closure_is_not_retroactively_excluded(self):
        option={'route':'Intercampus','direction':'Evanston to Chicago','board_stop':'Central L (EB)',
                'alight_stop':'Ward Building','board_time_local':'2026-10-16T16:29-05:00',
                'alight_time_local':'2026-10-16T17:30-05:00'}
        self.assertEqual(su.annotate_journey(option,self.state)['recommendation_status'],'schedule_only')

    def test_location_planner_filters_and_keeps_original_total(self):
        near={'stops':[{'stop_name':'Ward Building','stop_id':'demo-ward','straight_line_meters':100}]}
        with patch.object(pf,'served_stops_near',return_value=near):
            out=server.plan_scheduled_trip_to_location('Central L (EB)',42,-87,'2026-10-16T16:20')
        self.assertEqual(out['options'],[]);self.assertGreater(out['total_options'],0)
        self.assertEqual(out['total_options'],out['total_excluded_options'])
        self.assertIn('dropoff_straight_line_meters',out['excluded_options'][0])

    def test_current_fetch_preserves_eta_and_annotates_conflicting_notice(self):
        class Clock(datetime):
            @classmethod
            def now(cls,tz=None):return datetime.fromisoformat('2026-10-16T16:30:00-05:00')
        row={'stop_name':'Central L (EB)','stop_id':'demo','ride_id':'ride-demo',
             'direction':'Evanston to Chicago','route_name':'Intercampus',
             'reported_expected_arrival_local':'2026-10-16T16:34:00-05:00',
             'scheduled_departure_local':'2026-10-16T16:32:00-05:00'}
        report={'arrivals':[row],'fetched_at_local':'2026-10-16T16:30:00-05:00',
                'rides_examined':1,'matching_stops':[{'name':'Central L (EB)'}]}
        with patch.object(shuttle_now,'datetime',Clock),patch.object(shuttle_now,'load_once',return_value=report), \
             patch.object(shuttle_now,'resolve_query',return_value={'resolved':'Central L (EB)'}):
            out=shuttle_now.combine('Central L (EB)',{'Intercampus':'unused'})
        actual=out['arrivals'][0]
        self.assertEqual(actual['service_impact'],'unavailable')
        self.assertEqual(actual['reported_expected_arrival_local'],row['reported_expected_arrival_local'])

    def test_location_uses_one_snapshot_for_whole_response(self):
        su.PINNED.set(None)
        near={'stops':[{'stop_name':'Ward Building','stop_id':'ward','straight_line_meters':100},
                       {'stop_name':'Sheridan/Haven - Tech (SB)','stop_id':'tech','straight_line_meters':200}]}
        with patch.object(su,'snapshot',wraps=su.snapshot) as snapshot, \
             patch.object(su,'refresh',return_value=self.state) as refresh, \
             patch.dict('os.environ',{'TRIPSHOT_DISABLE_SERVICE_REFRESH':'0'}), \
             patch.object(pf,'served_stops_near',return_value=near):
            out=pf.plan_to_coordinates('Central L (EB)',42,-87,'2026-10-16T16:20')
        self.assertEqual(refresh.call_count,1);self.assertTrue(snapshot.called)
        self.assertEqual(out['service_updates_revision'],self.state['service_updates_revision'])

    def test_new_tools_validate_inputs_and_cached_queries(self):
        out=server.get_service_updates(route='Intercampus',when_local='2026-10-16T17:00',refresh=False)
        self.assertEqual(out['notice_count'],1);self.assertFalse(out['normal_service_confirmed'])
        self.assertEqual(server.get_service_updates(refresh='yes')['error'],'invalid_refresh')
        self.assertEqual(server.refresh_service_updates(force=1)['error'],'invalid_force')
        self.assertEqual(server.get_service_updates(when_local='invalid')['error'],'invalid_date_time')
        with patch.object(su,'refresh',return_value=self.state) as refresh:
            self.assertFalse(server.refresh_service_updates(force=True)['normal_service_confirmed'])
            refresh.assert_called_once_with(force=True)

    def test_transport_http_errors_size_and_charset(self):
        from email.message import Message
        from urllib.error import HTTPError
        from service_updates_source import fetch_page, MAX_BYTES, SOURCE_URL
        class Response:
            status=200
            def __init__(self,data,charset='utf-8'):
                self.data=data;self.headers=Message();self.headers['Content-Type']='text/html; charset='+charset
            def geturl(self):return SOURCE_URL
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,size):
                chunk=self.data[:size];self.data=self.data[size:];return chunk
        class Opener:
            def __init__(self,response):self.response=response;self.calls=0
            def open(self,req,timeout):self.calls+=1;return self.response
        response=Response(b'valid')
        self.assertEqual(fetch_page(opener=Opener(response)).html,'valid')
        for response in (Response(b'x'*(MAX_BYTES+1)),Response(b'\xff'),Response(b'data','bad-charset')):
            with self.assertRaises((ValueError,UnicodeError,LookupError)):fetch_page(opener=Opener(response))
        with patch('service_updates_source.build_opener') as client:
            client.return_value.open.side_effect=HTTPError(SOURCE_URL,403,'forbidden',{},None)
            with self.assertRaises(HTTPError):fetch_page()

    def test_unknown_stops_directions_negation_and_date_range(self):
        from service_updates_parser import parse_page
        for text in ('No service at Central L and Imaginary Stop on October 16, 2026.',
                     'Intercampus northbound service canceled October 16, 2026.',
                     'Intercampus service is not canceled October 16, 2026.',
                     'If weather requires, no service at Central L on October 16, 2026.',
                     'Updated October 17, 2026. Intercampus service canceled October 16, 2026.'):
            n=parse_page(html(text))['notices'][0]
            self.assertFalse(any(e['certain'] for e in n['effects']))
        n=parse_page(html('Intercampus service canceled from October 16, 2026 through October 18, 2026.'))['notices'][0]
        state={**self.state,'notices':[n]}
        self.assertEqual(su.evaluate(state,'Intercampus','Evanston to Chicago',['Ward Building'],
                         datetime.fromisoformat('2026-10-17T12:00-05:00'))['service_impact'],'unavailable')
        self.assertFalse(su._family_match('Central L','Central Lake'))

    def test_different_restoration_notice_downgrades_conflict(self):
        from service_updates_parser import parse_page
        n=parse_page(html('This closure has been withdrawn on October 16, 2026.').replace('Intercampus notice','Intercampus restoration'))['notices'][0]
        state={**self.state,'notices':self.state['notices']+[n]}
        out=su.evaluate(state,'Intercampus','Evanston to Chicago',['Central L (EB)'],
                        datetime.fromisoformat('2026-10-16T17:00-05:00'),journey=True)
        self.assertEqual(out['recommendation_status'],'provisional')
        self.assertTrue(out['service_alerts'][0]['conflicting_notice_ids'])

    def test_explicit_local_year_context_is_hash_bound_and_revalidated(self):
        import json
        from pathlib import Path
        from service_updates_parser import parse_page
        missing_year=html('No service at Central L on Friday, October 16 between 4:30 p.m. and 11:10 p.m.')
        notice=parse_page(missing_year)['notices'][0]
        root=Path(self.temp.name)
        context={notice['revision']:{'year':2026,'reviewer':'Test reviewer','reason':'Explicit test context',
                                    'reviewed_at':self.now.isoformat()}}
        (root/'reviewed_years.json').write_text(json.dumps(context),encoding='utf-8')
        state=su.refresh(root=root,now=self.now,force=True,fetcher=lambda **k:PageResponse(200,missing_year))
        self.assertEqual(state['notices'][0]['date_basis'],'reviewed_year_context')
        self.assertEqual(state['notices'][0]['review_context']['reviewer'],'Test reviewer')
        unreviewed=su.refresh(root=root,now=self.now,force=True,reviewed_years={},
                             fetcher=lambda **k:PageResponse(200,missing_year))
        self.assertEqual(unreviewed['refresh_status'],'updated')
        self.assertNotEqual(unreviewed['service_updates_revision'],state['service_updates_revision'])
        edited=missing_year.replace('11:10','11:40')
        state=su.refresh(root=root,now=self.now,force=True,fetcher=lambda **k:PageResponse(200,edited))
        self.assertFalse(next(n for n in state['notices'] if n['lifecycle']=='present')['windows'])
