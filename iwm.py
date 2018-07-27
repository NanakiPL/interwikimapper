import sys, graphviz, re, json, os
import urllib.request, urllib.parse, urllib.error
from graphviz import Digraph

if sys.version_info[0] > 2:
    from urllib.error import HTTPError
    import urllib.request as urllib2
    raw_input = input
else:
    import urllib.request, urllib.error, urllib.parse
    from urllib.error import HTTPError

def urlopen(url):
    req = urllib.request.Request(url, headers = {'User-agent': 'Interwiki Graph Generator'})
    uo = urllib.request.urlopen(req)
    try:
        if sys.version_info[0] > 2:
            uo.charset = uo.headers.get_content_charset()
        else:
            uo.charset = uo.headers.getfirstmatchingheader('Content-Type')[0].strip().split('charset=')[1]
    except IndexError:
        uo.charset = 'latin-1'
    return uo

class Graph(object):
    showGood = 2
    showOneWay = 2
    showRedir = 2
    showBadRedir = 2
    showBad = 2
    showBroken = 2
    
    def __init__(self, *args, **kwargs):
        self.dot = graphviz.Digraph(*args, **kwargs)
        self.dot.engine = 'circo'
        self.dot.format = 'png'
        
        self.nodes = {}
        self.edges = {}
        self.name = None
        self.depth = None
        self.checkall = None
        
        self.dot.attr('node', shape='circle')
    
    def node(self, wiki, **kwargs):
        if wiki.id in self.nodes: return
        self.nodes[wiki.id] = True
        
        args = {
            'URL': 'http://%s/' % wiki.url
        }
        args.update(kwargs)
        if wiki.invalid:
            args['color'] = 'red'
            self.dot.node(wiki.id, '%s\\n%s' % ('--', wiki.id), comment = 'invalid', **args)
        else:
            self.dot.node(wiki.id, '%s\\n%s' % (wiki.lang, wiki.id), **args)
        
    def edge(self, w1, w2):
        w1, w2 = sorted([w1, w2], key=lambda x: x.id)
        if w1.id not in self.edges: self.edges[w1.id] = {}
        if w2.id in self.edges[w1.id]: return
        self.edges[w1.id][w2.id] = True
        w1, w2 = sorted([w1, w2], key=lambda x: x.level)
        
        print(('\nEdge between %s and %s' % (w1, w2)))
        
        if self.invalidEdge(w1, w2): return
        
        self.goodEdges(w1, w2)
        self.badEdges(w1, w2)
        
    
    def goodEdges(self, w1, w2):
        a = self._goodEdge(w1, w2)
        b = self._goodEdge(w2, w1)
        
        if a and b:
            if self.showGood > 0: self.dot.edge(w1.id, w2.id, color='green', dir='both', weight='2', style=[None,'invis','bold'][self.showGood], comment='good')
            print('Good both ways')
        elif a and not b:
            if self.showOneWay > 0: self.dot.edge(w1.id, w2.id, comment='good one-way', style=[None,'invis',''][self.showOneWay])
            print(('Only \'%s\' correctly points to %s' % (w1, w2)))
        elif not a and b:
            if self.showOneWay > 0: self.dot.edge(w2.id, w1.id, comment='good one-way', style=[None,'invis',''][self.showOneWay])
            print(('Only \'%s\' correctly points to %s' % (w2, w1)))
    def _goodEdge(self, w1, w2):
        try:
            return Wiki.reURL.match(w1.langs[w2.lang]['url']).group(1) == w2.url # w1 corretly points to w2
        except (AttributeError, KeyError):
            pass
        return False
    
    def badEdges(self, w1, w2):
        self._badEdge(w1, w2)
        self._badEdge(w2, w1)
    def _badEdge(self, w1, w2):
        print(('%s -> %s' % (w1, w2)))
        badlinks = set()
        for lang, data in sorted(w1.langs.items()):
            wiki = Wiki(data['url'])
            if wiki.id != w2.id: continue
            try:
                url = Wiki.reURL.match(data['url']).group(1)
            except (AttributeError, KeyError):
                url = ''
            
            if url != w2.url:
                if w2.lang == lang:
                    print(('\'%s\' points to a redirect (http://%s/) to %s' % (lang, url, w2)))
                    if self.showRedir > 0: self.dot.edge(w1.id, w2.id, color='darkorange', headURL='http://%s/' % url, comment='redirect', style=[None,'invis',''][self.showRedir])
                else:
                    print(('\'%s\' points to a redirect (http://%s/) to %s under wrong lang prefix' % (lang, url, w2)))
                    if self.showBadRedir > 0: self.dot.edge(w1.id, w2.id, color='purple', fontcolor='purple', label=lang+':', headURL='http://%s/' % url, comment='wrong redirect', style=[None,'invis',''][self.showBadRedir])
            elif w2.lang != lang:
                badlinks.add(lang)
                print(('\'%s\' points to %s under wrong lang prefix' % (lang, w2)))
        
        if len(badlinks) > 2:
            if self.showBad > 0: self.dot.edge(w1.id, w2.id, color='brown', fontcolor='brown', label='%d links' % len(badlinks), comment='wrong', style=[None,'invis','bold'][self.showBad])
            self.dumpLinks(w1, w2, badlinks)
        else:
            for lang in badlinks:
                if self.showBad > 0: self.dot.edge(w1.id, w2.id, color='brown', fontcolor='brown', label=lang+':', comment='wrong', style=[None,'invis',''][self.showBad])
    
    def invalidEdge(self, w1, w2):
        return self._invalidEdge(w1, w2) or self._invalidEdge(w2, w1)
    def _invalidEdge(self, w1, w2):
        if w1.invalid:
            for lang, data in sorted(w2.langs.items()):
                if Wiki(data['url']) != w1: continue
                if self.showBroken > 0: self.dot.edge(w2.id, w1.id, color='red', fontcolor='red', label=lang+':', style=[None,'invis',''][self.showBroken])
                print(('Invalid \'%s\' link to %s' % (lang, w1)))
            return True
        return False
    
    @property
    def source(self):
        return self.dot.source
    
    def dumpLinks(self, w1, w2, links):
        try:
            os.mkdir(self.name)
        except OSError:
            pass
        f = open('%s/badlinks %s-%s.txt' % (self.name, w1.id, w2.id), 'w')
        f.write(' '.join(sorted(links)))
        f.close()
    
    def filename(self):
        return '%s/%s L%d %s [%s,%s,%s,%s,%s,%s].gv' % (
            self.name,
            self.name,
            self.depth,
            ['R','A'][int(self.checkall)],
            ['I','H','S'][self.showGood],
            ['I','H','S'][self.showOneWay],
            ['I','H','S'][self.showRedir],
            ['I','H','S'][self.showBadRedir],
            ['I','H','S'][self.showBad],
            ['I','H','S'][self.showBroken],
        )
    
    def save(self, *args, **kwargs):
        f = self.filename()
        self.dot.save(f, *args, **kwargs)
        
    def render(self, *args, **kwargs):
        f = self.filename()
        self.dot.render(f, *args, **kwargs)
    
class GraphGenerator(object):
    __instance = None
    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super(GraphGenerator,cls).__new__(cls)
            cls.__instance.__initialized = False
        return cls.__instance
        
    def __init__(self, url = None, depth = None, checkall = None, showlinks = None):
        if(self.__initialized): return
        self.__initialized = True
        
        if url is None:
            url = input("\nPlease insert URL to wiki: ")
        self.url = url
        
        if depth is None:
            depth = input("\nHow many levels do you want to check (0 - only ones linked from root): ")
        self.depth = int(depth)
        
        if checkall is None:
            checkall = input("\nDo you want to check links between [a]ll found wikis or only for [r]oot: ").lower() == 'a'
        else:
            checkall = checkall == '1' or checkall.lower() == 'y'
        self.checkall = checkall
        
        if showlinks is None:
            print('How do you want to display link types?')
            print('[Show/Hide/Ignore]')
            showlinks = []
            a = input("Good both ways links? (green): ").lower()
            if a == 's': showlinks.append(2)
            elif a == 'h': showlinks.append(1)
            else: showlinks.append(0)
            a = input("Good one way links?  (black): ").lower()
            if a == 's': showlinks.append(2)
            elif a == 'h': showlinks.append(1)
            else: showlinks.append(0)
            a = input("Good redirects?      (orange): ").lower()
            if a == 's': showlinks.append(2)
            elif a == 'h': showlinks.append(1)
            else: showlinks.append(0)
            a = input("Bad redirects?       (purple): ").lower()
            if a == 's': showlinks.append(2)
            elif a == 'h': showlinks.append(1)
            else: showlinks.append(0)
            a = input("Bad links?           (brown): ").lower()
            if a == 's': showlinks.append(2)
            elif a == 'h': showlinks.append(1)
            else: showlinks.append(0)
            a = input("Broken links?        (red): ").lower()
            if a == 's': showlinks.append(2)
            elif a == 'h': showlinks.append(1)
            else: showlinks.append(0)
        else:
            showlinks = showlinks.lower().split(',')
            for i in range(6):
                try:
                    if showlinks[i] == 's': showlinks[i] = 2
                    elif showlinks[i] == 'h': showlinks[i] = 1
                    else: showlinks[i] = 0
                except IndexError:
                    showlinks.append(2)
        self.showlinks = showlinks
        
        self.root = root = Wiki(url, 0)
        self.all = set([root])
        
        self.dot = dot = Graph(comment='Interwiki map for http://%s/' % self.url)
        dot.name = root.id
        dot.depth = self.depth
        dot.checkall = self.checkall
        dot.showGood, dot.showOneWay, dot.showRedir, dot.showBadRedir, dot.showBad, dot.showBroken = self.showlinks 
        print('\n\n')
    
    def nodes(self, wiki):
        print(('Working on http://%s/  -- level: %d' % (wiki.url, wiki.level)))
        self.dot.node(self.root, color='lightblue' if wiki.level == 0 else '')
        print(('Has %d language links' % len(list(wiki.langs.keys()))))
        
        self.all.add(wiki)
        langs = sorted(wiki.langs.items())
        
        for lang, data in langs:
            w = Wiki(data['url'])
            print(('Found link to http://%s/' % w.url))
            self.dot.node(w)
            self.all.add(w)
        
        wiki.done = True
        if wiki.level+1 > self.depth: return
        for lang, data in langs:
            w = Wiki(data['url'])
            if not w.done:
                self.nodes(w)
    
    def run(self):
        self.nodes(self.root)
        self.edges()
        
    def edges(self):
        if self.checkall:
            all = sorted(list(self.all), key=lambda x: x.id)
            for i, w1 in enumerate(all):
                for j, w2 in enumerate(all[i+1:]):
                    self.dot.edge(w1, w2)
        else:
            all = sorted(list(self.all), key=lambda x: x.id)
            for i, w1 in enumerate(all):
                self.dot.edge(self.root, w1)
                self.dot.edge(w1, self.root)
    
    def source(self):
        return self.dot.source


class Wiki(object):
    cache = {}
    reURL = re.compile('(?:https?:\/\/)?(?:[^@\n]+@)?((?:www\.)?[^:\/\n]+)', re.I)
    def __new__(cls, *args, **kwargs):
        match = Wiki.reURL.match(args[0])
        url = match.group(1)
        
        if url in Wiki.cache:
            return Wiki.cache[url]
        obj = super(Wiki,cls).__new__(cls)
        obj.__initialized = False
        return obj
    
    def __init__(self, url, level = 1):
        if self.__initialized:
            self.level = min(level, self.level)
            return
        self.__initialized = True
        
        self.id = None
        self.lang = None
        self.setUrl(url)
        self.api = 'http://%s/api.php' % self.url
        self.level = level
        self.invalid = False
        self.done = False
        
        self.info()
        
    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.id == other.id
        return False
    def __hash__(self):
        return hash(self.id)
            
    def setUrl(self, url):
        match = Wiki.reURL.match(url)
        url = match.group(1)
        self.url = url
        self.id = url.replace('.wikia.com', '')
        Wiki.cache[url] = self
    
    def info(self):
        #print('Fetching info about http://%s/' % self.url)
        try:
            data = urlopen(self.api + "?action=query&meta=siteinfo&siprop=general|interwikimap&sifilteriw=local&format=json")
            res = json.loads(data.read().decode(data.charset))
            
            if 'error' in res:
                raise RuntimeError('%s - %s' % (res['error']['code'], res['error']['info']))
            
            self.setUrl(res['query']['general']['server'])
            self.lang = res['query']['general']['lang']
            
            self.langs = {wiki['prefix']: wiki for wiki in res['query']['interwikimap']
                          if 'language' in wiki}
        except (HTTPError, ValueError) as e:
            self.langs = {}
            self.invalid = True
    
    def __repr__(self):
        if hasattr(self, 'url'):
            return 'Wiki(%s, %s)' % (self.id, self.lang or '-')
        return 'new Wiki()'

if __name__ == "__main__":
    print("This script is lazy and most likely won't work for non-Wikia wikis\n")
    if len(sys.argv) != 5:
        print(("Usage: %s <url> <depth> <checkall> <showlinks>" % sys.argv[0]))
        print("url: url of the wiki")
        print("depth: how many levels to check <0|1|2|...>")
        print("checkall: check links between all wikis or only between root and target <1|0>")
        print("showlinks: what types of links should be shown, hidden or ignored")
        print("           comma separated list of <s|h|i>")
        print("           order: good both ways, good one-way, good redirs, bad redirs, bad, broken")
        print("           ommited entries will be 's'")
        
    gen = GraphGenerator(*sys.argv[1:])
    gen.run()
    
    print('\n\n')
    #os.system('pause')
    print('\n\n')
    #print(gen.source())
    gen.dot.save()
    if input('Render? ').lower() == 'y':
        gen.dot.render(view=True)