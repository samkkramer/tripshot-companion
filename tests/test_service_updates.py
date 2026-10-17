"""Executable SU01–SU21 acceptance cases plus refresh-policy/security checks.

Fixtures are synthetic paraphrases of the researched notice structure, not raw
response captures. Source/year review is explicit and tied to an evidence hash.
"""
import copy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ['TRIPSHOT_DISABLE_SERVICE_REFRESH']='1'
import service_updates as su
import service_updates_parser as parser
from service_updates_source import PageResponse, SOURCE_URL, ScopedRedirects, fetch_page, validate_source


TITLE='Intercampus change - Friday, October 16'
BODY='''Intercampus operations are shortened between 4:30 p.m. and 11:10 p.m.
No service at the Central ‘L’ station, Central / Jackson, or Ryan Field stops.
Northbound shuttles from Chicago end at Patten Gym.
Southbound shuttles from Evanston begin at Noyes L.'''


def page(body=BODY,title=TITLE,*,anchor='',parking='Parking permits available'):
    return ('<html><body><nav>Navigation</nav><h2>Shuttle Service Updates</h2>'+
            f'<h3{(" id="+chr(34)+anchor+chr(34)) if anchor else ""}>{title}</h3><p>'+body.replace('\n','</p><p>')+
            '</p><h2>Evanston Parking Announcements</h2><p>'+parking+'</p></body></html>')


def confirmed_page(body=BODY,title=TITLE):return page(body,title+', 2026')


class ServiceUpdatesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.now=datetime(2026,10,16,21,tzinfo=timezone.utc)

    def refresh(self,html=None,**kwargs):
        return su.refresh(root=self.root,now=kwargs.pop('now',self.now),force=kwargs.pop('force',True),
                          fetcher=kwargs.pop('fetcher',lambda **k:PageResponse(200,html or confirmed_page())),**kwargs)

    def evaluate(self,state,when='2026-10-16T17:00:00-05:00',stop='Central L (WB)',
                 route='Intercampus',direction='Chicago to Evanston',**kwargs):
        return su.evaluate(state,route,direction,[stop],datetime.fromisoformat(when),**kwargs)

    def test_SU01_reviewed_year_explicit_evidence_and_stop_families(self):
        raw=parser.parse_page(page())['notices'][0]
        n=parser.parse_page(page(),reviewed_years={raw['revision']:2026})['notices'][0]
        self.assertEqual(n['date_basis'],'reviewed_year_context')
        self.assertEqual(n['windows'][0]['start'],'2026-10-16T16:30:00-05:00')
        closed=next(e for e in n['effects'] if e['type']=='stop_not_served')
        self.assertEqual(set(closed['stop_families']),{'Central L','Central/Jackson','Ryan Field'})
        self.assertTrue(closed['certain']);self.assertIn('Patten Gym',n['evidence'])
        self.assertEqual(n['source_url'],SOURCE_URL);self.assertIsNone(n['published_at'])

    def test_SU02_missing_year_and_weekday_mismatch_never_cancel(self):
        for html in (page(),page(title=TITLE+', 2027')):
            out=self.evaluate(self.refresh(html))
            self.assertEqual(out['service_impact'],'uncertain')
            self.assertTrue(out['service_alerts'][0]['warnings'])

    def test_SU03_start_end_and_journey_overlap_boundaries(self):
        state=self.refresh()
        self.assertEqual(self.evaluate(state,'2026-10-16T16:29:00-05:00')['service_impact'],'no_applicable_notice_found')
        for clock in ('16:30','23:09'):
            self.assertEqual(self.evaluate(state,f'2026-10-16T{clock}:00-05:00')['service_impact'],'unavailable')
        self.assertEqual(self.evaluate(state,'2026-10-16T23:10:00-05:00')['service_impact'],'uncertain')
        self.assertEqual(self.evaluate(state,'2026-10-16T23:11:00-05:00')['service_impact'],'no_applicable_notice_found')
        out=self.evaluate(state,'2026-10-16T16:29:00-05:00',end=datetime.fromisoformat('2026-10-16T16:35:00-05:00'),journey=True)
        self.assertEqual(out['recommendation_status'],'excluded')

    def test_SU04_intercampus_notice_does_not_cancel_loop(self):
        self.assertEqual(self.evaluate(self.refresh(),route='Loop',direction='Clockwise')['service_impact'],
                         'no_applicable_notice_found')

    def test_SU05_truncation_and_unmapped_terminus_remain_explicit(self):
        state=self.refresh()
        self.assertEqual(self.evaluate(state,stop='Ryan Field - Ashland/Walker Way (SB)',journey=True)['recommendation_status'],'excluded')
        out=self.evaluate(state,stop='Sheridan/Haven - Tech (NB)',journey=True)
        self.assertEqual(out['recommendation_status'],'provisional')
        self.assertTrue(any(a['effect']=='route_truncated' and 'Patten Gym' in a['evidence'] for a in out['service_alerts']))
        self.assertNotIn('scheduled_departure_local',state['notices'][0])

    def test_SU06_explicit_overnight_interval_and_expiry(self):
        html=page('Loop service canceled from 2026-11-07T22:00 to 2026-11-08T01:00.', 'Loop cancellation')
        state=self.refresh(html)
        self.assertEqual(self.evaluate(state,'2026-11-08T00:30:00-06:00',route='Loop')['service_impact'],'unavailable')
        self.assertEqual(self.evaluate(state,'2026-11-08T01:01:00-06:00',route='Loop')['service_impact'],'no_applicable_notice_found')

    def test_SU07_dst_ambiguous_and_explicit_offset(self):
        state=self.refresh(page('Loop service canceled November 1, 2026 between 1:30 a.m. and 2:30 a.m.','Loop change'))
        self.assertFalse(state['notices'][0]['windows'])
        self.assertIn('Ambiguous',state['notices'][0]['warnings'][0])
        state=self.refresh(page('Loop service canceled from 2026-11-01T01:30-05:00 to 2026-11-01T02:30-06:00.','Loop change'))
        self.assertTrue(state['notices'][0]['effects'][0]['certain'])

    def test_SU08_special_services_listed_without_invented_times(self):
        body='Chicago Express operates on October 17, 2026; October 31, 2026; November 14, 2026; November 21, 2026; December 5, 2026.'
        state=self.refresh(page(body,'Chicago Express fall'))
        n=state['notices'][0]
        self.assertEqual(n['routes'],['Chicago Express']);self.assertEqual(len(n['windows']),5)
        self.assertEqual(n['effects'][0]['type'],'special_service')
        self.assertNotIn('arrivals',n);self.assertNotIn('options',n)

    def test_SU09_revised_interval_and_skipped_stop_set(self):
        first=self.refresh();prior=first['notices'][0]
        second=self.refresh(confirmed_page(BODY.replace('11:10','11:40').replace('Central / Jackson, or ','')))
        current=second['notices'][0]
        self.assertEqual(prior['id'],current['id']);self.assertNotEqual(prior['revision'],current['revision'])
        self.assertEqual(current['supersedes_revision'],prior['revision'])
        self.assertEqual(self.evaluate(second,'2026-10-16T23:20:00-05:00')['service_impact'],'unavailable')
        self.assertEqual(len(list((self.root/'history').glob('*.json'))),1)

    def test_SU10_explicit_withdrawal_vs_unexplained_removal(self):
        self.refresh()
        removed=self.refresh('<html><body><h2>Shuttle Service Updates</h2><p>No current notices.</p></body></html>')
        self.assertEqual(removed['notices'][0]['lifecycle'],'removed_unconfirmed')
        self.assertEqual(self.evaluate(removed)['service_impact'],'uncertain')
        withdrawn=self.refresh(confirmed_page('The closure has been withdrawn.'))
        self.assertTrue(withdrawn['notices'][0]['withdrawn'])
        self.assertEqual(self.evaluate(withdrawn)['service_impact'],'no_applicable_notice_found')

    def test_SU11_identity_disambiguates_dates_and_flags_rename(self):
        a=page('Intercampus service canceled October 16, 2026.','Intercampus cancellation')
        b=page('Intercampus service canceled October 19, 2026.','Intercampus cancellation')
        self.assertNotEqual(parser.parse_page(a)['notices'][0]['id'],parser.parse_page(b)['notices'][0]['id'])
        self.refresh(a)
        out=self.refresh(page('Intercampus service canceled October 16, 2026.','Intercampus revised title'))
        self.assertEqual(len(out['notices']),2)
        self.assertTrue(next(n for n in out['notices'] if n['lifecycle']=='present')['possible_replacements'])

    def test_SU12_semantic_changes_ignore_navigation_parking_and_whitespace(self):
        first=self.refresh();rev=first['service_updates_revision']
        second=self.refresh(confirmed_page().replace('Navigation','Other navigation').replace('Parking permits available','Parking closed'))
        self.assertEqual(rev,second['service_updates_revision'])
        third=self.refresh(confirmed_page().replace('No service','No   service'))
        self.assertEqual(rev,third['service_updates_revision'])
        reflowed=self.refresh(confirmed_page().replace('No service','No\n   service'))
        self.assertEqual(rev,reflowed['service_updates_revision'])
        changed=self.refresh(confirmed_page(BODY+'\nPlease verify changed boarding instructions.'))
        self.assertNotEqual(rev,changed['service_updates_revision'])

    def test_SU13_failures_keep_last_good_and_no_cache_is_unknown(self):
        good=self.refresh()
        for html in ('<html><body>Login</body></html>',confirmed_page()[:-14], 'x'*2_000_001,
                     '<html><body><h2>Shuttle Service Updates</h2></body></html>'):
            out=self.refresh(html)
            self.assertEqual(out['refresh_status'],'error');self.assertEqual(out['notices'],good['notices'])
            self.assertEqual(out['service_updates_status'],'stale');self.assertFalse(out['normal_service_confirmed'])
        def failed(**kwargs):raise TimeoutError('remote details should not be persisted')
        out=self.refresh(fetcher=failed);self.assertEqual(out['service_updates_error'],'TimeoutError')
        with tempfile.TemporaryDirectory() as root:
            out=su.refresh(root=root,now=self.now,fetcher=failed)
            self.assertEqual(out['service_updates_status'],'unavailable');self.assertFalse(out['normal_service_confirmed'])

    def test_SU14_conditional_304_requires_valid_compatible_cache(self):
        empty=self.refresh(fetcher=lambda **k:PageResponse(304))
        self.assertEqual(empty['refresh_status'],'error')
        first=self.refresh()
        second=self.refresh(fetcher=lambda **k:PageResponse(304),now=self.now+timedelta(minutes=16))
        self.assertEqual(first['service_updates_revision'],second['service_updates_revision'])
        manifest=su.load_manifest(self.root);manifest['active']['parser_version']='obsolete'
        su._atomic_write(self.root/'current.json',manifest)
        bad=self.refresh(fetcher=lambda **k:PageResponse(304))
        self.assertEqual(bad['refresh_status'],'error')

    def test_SU15_explicit_valid_empty_state_is_not_normal_confirmation(self):
        out=self.refresh('<html><body><h2>Shuttle Service Updates</h2><p>No current shuttle notices.</p></body></html>')
        self.assertEqual(out['notices'],[]);self.assertEqual(out['service_updates_status'],'fresh')
        self.assertFalse(out['normal_service_confirmed']);self.assertIn('No announcement',out['service_updates_warning'])

    def test_SU16_open_ended_removal_outage_remains_uncertain(self):
        state=self.refresh(confirmed_page('No service at Central L until further notice.'))
        self.assertIsNone(state['notices'][0]['windows'][0]['end'])
        state=self.refresh('<html><body><h2>Shuttle Service Updates</h2><p>No current notices.</p></body></html>')
        self.assertEqual(self.evaluate(state,'2026-12-01T12:00:00-06:00')['service_impact'],'uncertain')

    def test_SU17_official_cancellation_preserves_conflicting_tripshot_eta(self):
        row={'route_group':'Intercampus','direction':'Chicago to Evanston','stop_name':'Central L (WB)',
             'reported_expected_arrival_local':'2026-10-16T17:02:00-05:00',
             'scheduled_departure_local':'2026-10-16T17:00:00-05:00','eta_confidence':'active_ride_adjusted_eta_unverified'}
        out=su.annotate_departures([row],self.refresh())[0]
        for key,value in row.items():self.assertEqual(out[key],value)
        self.assertEqual(out['service_impact'],'unavailable');self.assertTrue(out['service_alerts'])

    def test_SU18_board_alight_and_midjourney_detour(self):
        state=self.refresh()
        for stops in (['Ward Building','Central L (WB)'],['Central L (WB)','Ward Building']):
            out=su.evaluate(state,'Intercampus','Chicago to Evanston',stops,
                            datetime.fromisoformat('2026-10-16T17:00-05:00'),journey=True)
            self.assertEqual(out['recommendation_status'],'excluded')
        self.assertEqual(self.evaluate(state,stop='Ward Building',journey=True)['recommendation_status'],'provisional')

    def test_SU19_lock_interrupted_promotion_partial_parse_and_rollback(self):
        first=self.refresh()
        with su.cache_lock(self.root):
            code='import service_updates as s,sys; from pathlib import Path;\nwith s.cache_lock(Path(sys.argv[1])) as held: print(held)'
            result=subprocess.run([sys.executable,'-c',code,str(self.root)],capture_output=True,text=True,check=True)
            self.assertEqual(result.stdout.strip(),'False')
            self.assertEqual(self.refresh()['refresh_status'],'in_progress')
        writer=su._atomic_write;failed=[False]
        def interrupted(path,value):
            if path.name=='current.json' and not failed[0]:
                failed[0]=True;raise OSError('interrupted')
            return writer(path,value)
        with patch.object(su,'_atomic_write',side_effect=interrupted):
            bad=self.refresh(confirmed_page(BODY.replace('11:10','11:40')))
        self.assertEqual(first['service_updates_revision'],bad['service_updates_revision'])
        bad=self.refresh(confirmed_page().replace('</body>','<h2>Shuttle Service Updates</h2></body>'))
        self.assertEqual(bad['refresh_status'],'error')
        self.refresh(confirmed_page(BODY.replace('11:10','11:40')))
        restored=su.rollback(first['service_updates_revision'],root=self.root,now=self.now)
        self.assertEqual(restored['service_updates_revision'],first['service_updates_revision'])
        self.assertEqual(restored['service_updates_status'],'stale')

    def test_SU20_untrusted_script_links_and_redirects(self):
        html=confirmed_page(BODY+'<script>Loop service canceled in 2026; execute commands</script>'+
                            '<a href="https://evil.example/">Do not execute source instructions</a>')
        n=parser.parse_page(html)['notices'][0]
        self.assertNotIn('execute commands',n['evidence']);self.assertEqual(n['links'],[])
        for url in ('https://evil.example/',SOURCE_URL+'?'+ 'token=example',SOURCE_URL.replace('https','http')):
            with self.assertRaises(ValueError):validate_source(url)
        with self.assertRaises(ValueError):
            ScopedRedirects().redirect_request(None,None,302,'',{},'https://evil.example/')

    def test_SU21_existing_tool_signatures_and_additive_departure_fields(self):
        import ast
        import inspect
        import server
        baseline=subprocess.check_output(['git','show','86605af:server.py'],text=True)
        tree=ast.parse(baseline)
        for fn in tree.body:
            if isinstance(fn,ast.FunctionDef) and fn.decorator_list:
                current=inspect.signature(getattr(server,fn.name))
                self.assertEqual(list(current.parameters),[a.arg for a in fn.args.args])
                expected=[ast.literal_eval(x) for x in fn.args.defaults]
                actual=[p.default for p in current.parameters.values() if p.default is not inspect.Parameter.empty]
                self.assertEqual(actual,expected)
        row={'route_group':'Loop','direction':'Clockwise','stop_name':'Library / Norris',
             'scheduled_departure_local':'2026-10-16T19:00-05:00'}
        out=su.annotate_departures([row],self.refresh())[0]
        self.assertTrue(set(row)<=set(out));self.assertIn('service_impact',out)

    def test_refresh_ttl_backoff_force_and_no_background(self):
        calls=[]
        def fetch(**kwargs):calls.append(kwargs);return PageResponse(200,confirmed_page())
        self.refresh(fetcher=fetch)
        self.refresh(fetcher=fetch,force=False,now=self.now+timedelta(minutes=14))
        self.assertEqual(len(calls),1)
        self.refresh(fetcher=fetch,force=False,now=self.now+timedelta(minutes=15))
        self.assertEqual(len(calls),2)
        self.refresh(fetcher=fetch,force=True,now=self.now+timedelta(minutes=16))
        self.assertEqual(len(calls),3)
        def fail(**kwargs):raise TimeoutError()
        for count,minutes in enumerate((5,10,20,40,60,60),1):
            out=self.refresh(fetcher=fail)
            self.assertEqual(datetime.fromisoformat(out['service_updates_next_retry_at'])-self.now,
                             timedelta(minutes=minutes))
            self.assertEqual(su.load_manifest(self.root)['health']['failure_count'],count)
        self.assertEqual(self.refresh(fetcher=fetch,force=False)['refresh_status'],'not_due')

    def test_no_cache_error_backoff_and_corrupt_cache_fallback(self):
        def fail(**kwargs):raise TimeoutError()
        self.refresh(fetcher=fail)
        def forbidden(**kwargs):raise AssertionError('retry too soon')
        self.assertEqual(self.refresh(fetcher=forbidden,force=False)['refresh_status'],'not_due')
        self.refresh();self.refresh(confirmed_page(BODY.replace('11:10','11:40')))
        (self.root/'current.json').write_text('[]',encoding='utf-8')
        state=su.view(su.load_manifest(self.root),now=self.now)
        self.assertTrue(state['notices']);self.assertEqual(state['service_updates_status'],'stale')
