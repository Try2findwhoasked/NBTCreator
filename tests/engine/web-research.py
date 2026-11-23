"""Verify fast, bounded online research and local provenance without network calls."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket
import sys
import tempfile
from threading import Event
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.agents/skills/minecraft-nbt-modeler/scripts'))
from nbt_knowledge.public_web import WebError, extract, public_address, public_url
from nbt_knowledge.retrieval import dispatch
from nbt_knowledge.web_research import location, persist, research


FIRST = 'https://first.example.org/rose'
SECOND = 'https://second.example.org/church'
THIRD = 'https://third.example.org/reference'


def evidence(url, text='The rose window tracery uses radial stone mullions.'):
    return dict(source_url=url,title='Architecture archive',publisher='City archive',section='Windows',
                accessed_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),text=text,content_kind='excerpt',
                page_sha256=hashlib.sha256(text.encode()).hexdigest(),verification='app_opened')


class WebResearch(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.workspace = Path(folder.name).resolve()

    def query(self, opener, finder=lambda *_:[], **request):
        return research(self.workspace,'prompt',{'workflow':'prompt',**request},finder=finder,opener=opener)

    def test_direct_url_races_slow_source_and_skips_search_after_first_evidence(self):
        unblock = Event()
        self.addCleanup(unblock.set)
        def open_page(url, *_):
            if url==FIRST:
                unblock.wait(4)
                raise WebError('TIMEOUT','slow')
            return evidence(url)
        result = self.query(open_page, lambda *_:self.fail('search was unnecessary'),
                            query='rose window',urls=[FIRST,SECOND,THIRD,FIRST])
        self.assertEqual(result['status'],'complete')
        self.assertEqual(result['metrics']['pages_started'],2)
        self.assertLess(result['metrics']['elapsed_ms'],1000)
        self.assertEqual(result['evidence'][0]['locator'],SECOND)

    def test_deadline_and_failure_leave_verified_partial_result(self):
        unblock = Event()
        self.addCleanup(unblock.set)
        def open_page(url, *_):
            if url==FIRST:
                unblock.wait(4)
            return evidence(url)
        result = self.query(open_page,urls=[FIRST,SECOND],limit=2,timeout_ms=500)
        self.assertEqual(result['status'],'partial')
        self.assertEqual([item['locator'] for item in result['evidence']],[SECOND])
        self.assertEqual(result['failures'][0]['code'],'TIMEOUT')
        self.assertLess(result['metrics']['first_evidence_ms'],result['metrics']['elapsed_ms'])

    def test_search_tries_alternative_only_when_needed_and_cache_is_read_only(self):
        searches,opens = [],[]
        def finder(query, *_):
            searches.append(query)
            return [FIRST,FIRST] if query=='palace windows' else [FIRST,SECOND]
        def open_page(url, *_):
            opens.append(url)
            if url==FIRST:
                raise WebError('NO_PASSAGE','no paragraph')
            return evidence(url)
        request = dict(query='palace windows',fallback_queries=['stone tracery','extra'])
        result = self.query(open_page,finder,**request)
        self.assertEqual(searches,['palace windows','stone tracery'])
        self.assertEqual(opens,[FIRST,SECOND])
        cached = self.query(lambda *_:self.fail('cache reopened original'),**request)
        self.assertTrue(cached['metrics']['cache_hit'])
        self.assertEqual(cached['evidence'],result['evidence'])
        fresh = self.query(open_page,finder,refresh=True,**request)
        self.assertFalse(fresh['metrics']['cache_hit'])
        self.assertEqual(len(searches),4)

    def test_rate_limited_index_isnt_retried_in_same_call(self):
        search_count = []
        def finder(query, *_):
            search_count.append(query)
            raise WebError('RATE_LIMIT','rate limited')
        found = self.query(lambda *_:self.fail('no candidates'),finder,query='rose window',fallback_queries=['tracery'])
        self.assertEqual(found['status'],'no_evidence')
        self.assertEqual(search_count,['rose window'])

    def test_public_transport_rejects_local_and_authenticated_sources(self):
        for address in ('http://first.example.org/rose','https://localhost/','https://127.0.0.1/',
                        'https://example.org:444/','https://user:password@example.org/','https://example.org/?token=x',
                        'https://[::1]/','https://example.org\\@other.org/'):
            with self.subTest(address=address),self.assertRaises(WebError):
                public_url(address)
        public = (socket.AF_INET,1,6,'',('8.8.8.8',443))
        for family,address in ((socket.AF_INET,'192.168.1.5'),(socket.AF_INET,'169.254.169.254'),(socket.AF_INET6,'64:ff9b::a00:1')):
            with patch('nbt_knowledge.public_web.socket.getaddrinfo',return_value=[public,(family,1,6,'',(address,443))]):
                with self.assertRaises(WebError):public_address('example.org')
        self.assertEqual(public_url('https://example.org/window#figure'), 'https://example.org/window')

    def test_markup_and_search_snippets_never_stand_in_for_page_body(self):
        markup = (b'<title>Rose and old walls</title><meta property="og:site_name" content="Archive">'
                  b'<nav><p>Rose window stained glass, printed only in the navigation.</p></nav>'
                  b'<script>rose window stained glass in JavaScript</script><h2>Opening</h2>'
                  b'<p>The rose of the Apocalypse lights the upper chapel.</p><h2>Construction</h2>'
                  b'<p>The current rose is dedicated to the Apocalypse and was rebuilt in 1485.</p>')
        title,publisher,section,excerpt = extract(markup,'text/html',None,'玫瑰窗 重建年代')
        self.assertEqual((title,publisher,section),('Rose and old walls','Archive','Construction'))
        self.assertIn('1485',excerpt)
        with self.assertRaises(WebError):extract(markup,'text/html',None,'space telescope')

    def test_only_explicit_research_can_network_and_disallows_private_payloads(self):
        with patch('nbt_knowledge.web_research.find_urls',side_effect=AssertionError('unexpected network')):
            result = dispatch(self.workspace,'search',dict(workflow='prompt',query='rose window'))
        self.assertEqual(result['knowledge'],[])
        for request in (dict(query=r'D:\work\note.md'),dict(query='api_key: pretend'),dict(query='wall [1,2,3]'),
                        dict(query='rose window',model_source='private')):
            with self.assertRaises(ValueError):self.query(lambda *_:self.fail('invalid query escaped'),**request)

    def test_host_and_app_provenance_stay_distinct_and_snapshots_are_hash_bound(self):
        observed = self.query(lambda *_:evidence(FIRST),urls=[FIRST])['evidence'][0]
        draft = evidence(SECOND)
        hosted = {key:draft[key] for key in ('source_url','title','publisher','section','accessed_at','text','content_kind')}
        imported = dispatch(self.workspace,'import-web',dict(workflow='prompt',evidence=[dict(hosted,reader='host web tool')]))['evidence'][0]
        self.assertEqual(imported['bibliography']['verification'],'host_reported')
        self.assertNotIn('page_sha256',imported['bibliography'])
        with self.assertRaises(ValueError):
            dispatch(self.workspace,'import-web',dict(workflow='prompt',evidence=[dict(hosted,reader='host',verification='app_opened')]))
        bundle = dispatch(self.workspace,'bundle',dict(workflow='prompt',selected=[observed['id'],imported['id']]))
        self.assertEqual(bundle['sources'][0]['bibliography']['verification'],'app_opened')
        self.assertEqual(bundle['sources'][1]['bibliography']['verification'],'host_reported')
        self.assertNotIn('text',bundle['sources'][0])
        receipt = {key:bundle[key] for key in ('id','sha256')}
        with patch('nbt_knowledge.web_research.get',side_effect=AssertionError('receipt triggered network')):
            found = dispatch(self.workspace,'read',dict(workflow='prompt',**receipt))
            self.assertEqual(found['knowledge'][0]['content'],observed['text'])
        with self.assertRaises(ValueError):
            dispatch(self.workspace,'bundle',dict(workflow='component',selected=[observed['id']]))
        file = location(self.workspace,'evidence',observed['sha256'])
        file.write_text(json.dumps(dict(forged=True)),encoding='utf8')
        with self.assertRaises(ValueError):dispatch(self.workspace,'read',dict(workflow='prompt',**receipt))

    def test_explicit_favorites_are_searchable_offline_and_removal_keeps_old_citations(self):
        original = self.query(lambda *_:evidence(FIRST),urls=[FIRST])['evidence'][0]
        request = dict(workflow='prompt',query='玫瑰窗 窗饰')
        favorite = dict(workflow='prompt',id=original['id'])
        with patch('nbt_knowledge.web_research.get',side_effect=AssertionError('favorites went online')):
            self.assertEqual(dispatch(self.workspace,'search',request)['knowledge'],[])
            self.assertTrue(dispatch(self.workspace,'saved-web',dict(favorite,action='add'))['saved'])
            self.assertTrue(dispatch(self.workspace,'saved-web',dict(favorite,action='add'))['saved'])
            listing = dispatch(self.workspace,'saved-web',dict(workflow='prompt',action='list'))
            self.assertEqual([item['id'] for item in listing['knowledge']],[original['id']])
            hit, = dispatch(self.workspace,'search',request)['knowledge']
            self.assertTrue(hit['saved'])
            self.assertEqual(hit['bibliography'],original['bibliography'])
            self.assertEqual(dispatch(self.workspace,'search',dict(request,workflow='component'))['knowledge'],[])
            self.assertEqual(dispatch(self.workspace,'search',dict(request,filters={'style':'gothic'}))['knowledge'],[])
            bundle = dispatch(self.workspace,'bundle',dict(request,selected=[hit['id']]))
            self.assertFalse(dispatch(self.workspace,'saved-web',dict(favorite,action='remove'))['saved'])
            self.assertEqual(dispatch(self.workspace,'search',request)['knowledge'],[])
            read = dispatch(self.workspace,'read',dict(workflow='prompt',id=bundle['id'],sha256=bundle['sha256']))
            self.assertEqual(read['sources'][0]['bibliography']['source_url'],FIRST)

    def test_saved_snapshot_refresh_dedupes_and_tampered_evidence_leaves_other_results(self):
        initial = evidence(FIRST,'The rose was rebuilt around 1485 under Charles VIII.')
        first = persist(self.workspace,'prompt',dict(initial,accessed_at='2026-01-01T00:00:00+00:00'))
        fresh = persist(self.workspace,'prompt',dict(initial,accessed_at='2026-01-02T00:00:00+00:00'))
        other = persist(self.workspace,'prompt',evidence(SECOND,'The chapel kept the other rose window of 1485.'))
        for item in (first,fresh,other):
            dispatch(self.workspace,'saved-web',dict(workflow='prompt',action='add',id=item['id']))
        result = dispatch(self.workspace,'search',dict(workflow='prompt',query='1485'))
        self.assertEqual({item['id'] for item in result['knowledge']},{fresh['id'],other['id']})
        location(self.workspace,'evidence',fresh['sha256']).write_text('{}',encoding='utf8')
        result = dispatch(self.workspace,'search',dict(workflow='prompt',query='1485'))
        self.assertEqual([item['id'] for item in result['knowledge']],[other['id']])
        self.assertTrue(result['saved_web_errors'])
        dispatch(self.workspace,'saved-web',dict(workflow='prompt',action='remove',id=fresh['id']))
        self.assertFalse(dispatch(self.workspace,'saved-web',dict(workflow='prompt',action='list'))['errors'])


if __name__=='__main__':
    unittest.main(verbosity=2)
