import sys, graphviz, re, json, os
import urllib
from graphviz import Digraph

if sys.version_info[0] > 2:
    from urllib.error import HTTPError
    import urllib.request as urllib2
    raw_input = input
else:
    import urllib2
    from urllib2 import HTTPError

def urlopen(url):
    req = urllib2.Request(url, headers = {'User-agent': 'Interwiki Graph Generator'})
    uo = urllib2.urlopen(req)
    try:
        if sys.version_info[0] > 2:
            uo.charset = uo.headers.get_content_charset()
        else:
            uo.charset = uo.headers.getfirstmatchingheader('Content-Type')[0].strip().split('charset=')[1]
    except IndexError:
        uo.charset = 'latin-1'
    return uo

class Graph(object):
    def __init__(self, *args, **kwargs):
        self.dot = graphviz.Digraph(*args, **kwargs)
        self.dot.engine = 'circo'
        self.dot.format = 'png'
        
        self.nodes = {}
        self.edges = {}
    
    def node(self, wiki, **kwargs):
        if wiki.id in self.nodes: return
        self.nodes[wiki.id] = True
        
        args = {
            'URL': 'http://%s/' % wiki.url
        }
        args.update(kwargs)
        if wiki.invalid:
            self.dot.node(wiki.id, '%s\\n%s' % ('--', wiki.id), comment = 'invalid' , color='red', **args)
        else:
            self.dot.node(wiki.id, '%s\\n%s' % (wiki.lang, wiki.id), **args)
        
    def edge(self, w1, w2):
        w1, w2 = sorted([w1, w2], key=lambda x: x.id)
        if w1.id not in self.edges: self.edges[w1.id] = {}
        if w2.id in self.edges[w1.id]: return
        self.edges[w1.id][w2.id] = True
        w1, w2 = sorted([w1, w2], key=lambda x: x.level)
        
        print('\nEdge between %s and %s' % (w1, w2))
        
        if self.invalidEdge(w1, w2): return
        
        self.goodEdges(w1, w2)
        self.badEdges(w1, w2)
        
    
    def goodEdges(self, w1, w2):
        a = self._goodEdge(w1, w2)
        b = self._goodEdge(w2, w1)
        
        if a and b:
            #self.dot.edge(w1.id, w2.id, color='green', dir='both', weight='2')#, style='invis')
            print('Good both ways')
        elif a and not b:
            self.dot.edge(w1.id, w2.id)
            print('Only \'%s\' correctly points to %s' % (w1, w2))
        elif not a and b:
            self.dot.edge(w2.id, w1.id)
            print('Only \'%s\' correctly points to %s' % (w2, w1))
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
        badlinks = set()
        for lang, data in sorted(w1.langs.items()):
            wiki = Wiki(data['url'])
            try:
                url = Wiki.reURL.match(data['url']).group(1)
            except (AttributeError, KeyError):
                url = None
            if wiki != w2: continue
            if url and url != wiki.url and wiki.lang == lang:
                print('\'%s\' points to a redirect (http://%s/) to %s' % (lang, url, w2))
                self.dot.edge(w1.id, w2.id, color='darkorange')
            elif url and url != wiki.url:
                print('\'%s\' points to a redirect (http://%s/) to %s under wrong lang prefix' % (lang, url, w2))
                self.dot.edge(w1.id, w2.id, color='purple', fontcolor='purple', label=lang+':', headURL='http://%s/' % url)
            elif wiki.lang != lang:
                badlinks.add(lang)
                print('\'%s\' points to %s under wrong lang prefix' % (lang, w2))
        
        if len(badlinks) > 2:
            self.dot.edge(w1.id, w2.id, color='brown', fontcolor='brown', style='bold', label='%d links' % len(badlinks))
        else:
            for lang in badlinks:
                self.dot.edge(w1.id, w2.id, color='brown', fontcolor='brown', label=lang+':')
    
    def invalidEdge(self, w1, w2):
        return self._invalidEdge(w1, w2) or self._invalidEdge(w2, w1)
    def _invalidEdge(self, w1, w2):
        if w1.invalid:
            for lang, data in sorted(w2.langs.items()):
                if Wiki(data['url']) != w1: continue
                self.dot.edge(w2.id, w1.id, color='red', fontcolor='red', label=lang+':')
                print('Invalid \'%s\' link to %s' % (lang, w1))
            return True
        return False
    
    @property
    def source(self):
        return self.dot.source
    
class GraphGenerator(object):
    __instance = None
    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super(GraphGenerator,cls).__new__(cls)
            cls.__instance.__initialized = False
        return cls.__instance
        
    def __init__(self, url = None, depth = None):
        if(self.__initialized): return
        self.__initialized = True
        
        if url is None:
            url = raw_input("Please insert URL to wiki: ")
        self.url = url
        
        if depth is None:
            depth = raw_input("How many levels do you want to check (0 - only ones linked from main): ")
        self.depth = int(depth)
        
        self.root = root = Wiki(url, 0)
        self.all = set([root])
        
        self.dot = dot = Graph(comment='Interwiki map for http://%s/' % self.url)
    
    def nodes(self, wiki):
        print('Working on http://%s/  -- level: %d' % (wiki.url, wiki.level))
        self.dot.node(self.root, color='lightblue' if wiki.level == 0 else '')
        print('Has %d language links' % len(wiki.langs.keys()))
        
        langs = sorted(wiki.langs.items())
        
        for lang, data in langs:
            w = Wiki(data['url'])
            print('Found link to http://%s/' % w.url)
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
        all = sorted(list(self.all), key=lambda x: x.id)
        for i, w1 in enumerate(all[:-1]):
            for j, w2 in enumerate(all[i+1:]):
                self.dot.edge(w1, w2)
    
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
                          if u'language' in wiki}
        except (HTTPError, ValueError) as e:
            self.langs = {}
            self.invalid = True
    
    def __repr__(self):
        if hasattr(self, 'url'):
            return 'Wiki(%s, %s)' % (self.id, self.lang or '-')
        return 'new Wiki()'

if __name__ == "__main__":
    print("This script is lazy and most likely won't work for non-Wikia wikis\n")
    if len(sys.argv) != 3:
        print("Usage: %s <url> <depth>" % sys.argv[0])
        print("Example: %s https://community.wikia.com/ 1"
              % sys.argv[0])
        print("This will create the file families/mywiki_family.py")
        
    gen = GraphGenerator(*sys.argv[1:])
    gen.run()
    
    print('\n\n')
    #os.system('pause')
    print('\n\n')
    #print(gen.source())
    gen.dot.dot.save('round-table.gv')
    if raw_input('Render? ').lower() == 'y':
        gen.dot.dot.render('round-table.gv', view=True)