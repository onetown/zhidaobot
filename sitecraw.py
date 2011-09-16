#!/usr/bin/env python 
# -*- coding: UTF-8 -*-
import os
import re 
import logging
import random
import tornado.httpserver
import tornado.options
import tornado.ioloop
import tornado.web
import tornado.httpclient
import tornado.escape
from tornado.options import define, options
from lxml import html as HTML
from lxml.html.soupparser import fromstring
from lxml.etree import tostring
define("port", default=8000, help="run on the given port", type=int)
define("keysfile", default="keys.txt")

global static_keywords
static_keywords = []

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", HomeHandler),
            (r"/s/([^/]+)", SearchHandler),
            (r"/q/([^/]+)", QuestionHandler)
        ]
        settings = dict(
            debug = True,
            template_path=os.path.join(os.path.dirname(__file__),"templates"),
            static_path=os.path.join(os.path.dirname(__file__),"static"),
        )
        tornado.web.Application.__init__(self, handlers, **settings)

class BaseHandler(tornado.web.RequestHandler):
    def prepare(self):
        self.title = None

    def get_current_user(self):
        return None

class HomeHandler(BaseHandler):
    def get(self):
        kq = self.get_argument("keyword","")
        if kq and kq <> "":
            self.redirect("/s/" + kq)
            return
        global static_keywords
        rand_keys = []
        for i in range(60):
            r = random.randint(0, len(static_keywords))
            rand_keys.append(static_keywords[r])
            
        self.render("index.html", rkeys = rand_keys)

class QuestionHandler(BaseHandler):
    @tornado.web.asynchronous
    def get(self,qnumber=None):
        if not qnumber:
            self.redirect("/")
        else:
            baidu = "http://zhidao.baidu.com/question/"+ qnumber +".html"
            hc = tornado.httpclient.AsyncHTTPClient()
            hc.fetch(baidu, self._on_load)

    def _on_load(self,resp):
        global static_keywords
        rand_keys = []
        for i in range(20):
            r = random.randint(0,len(static_keywords))
            rand_keys.append(static_keywords[r])
        offset1 = resp.body.find("<div id=\"body\"")
        offset2 = resp.body.find("<div id=\"footer\"")
        body = "<html><body>" + resp.body[offset1:offset2] + "</body></html>"
        try:
            body = body.decode('gbk')
        except:
            pass
        try:
            question = self._parse(body)
            self.render("question.html",q=question, rkeys = rand_keys)
        except Exception,e:
            self.write(body)
            print e
            #self.render("error.html")
            self.finish()

    def _parse(self, body):
        q = {}
        doc = HTML.fromstring(body)
        qbox = doc.xpath("//*[@id=\"question-box\"]")[0]
        qtitle = qbox.xpath(".//h1[@id='question-title']//span")[1]
        qbody = qbox.xpath(".//*[@id=\"question-content\"]")[0]
        #get question
        q["title"] = qtitle.text_content()
        self.title = q["title"]
        q["body"] = qbody.text_content()

        anwsers = [None,None] #0 best anwser, 1 recommended anwser, 2-more other anwser
        '''get best anwser'''
        bae = doc.xpath("//*[@id='best-answer-panel']")
        if bae:
            ba = bae[0].xpath(".//*[@class='content']")[0]
            ba = HTML.tostring(ba,encoding="utf-8")
            anwsers[0] = ba

        '''get recommended anwser'''
        rae = doc.xpath("//*[@id='recommend-answer-panel']")
        if rae:
            ra = rae[0].xpath(".//*[@class='content']")[0]
            ra = HTML.tostring(ra,encoding="utf-8")
            anwsers[1] = ra

        '''get other anwsers'''
        oae = doc.xpath("//*[@id='reply-panel']")
        if oae:
            aes = oae[0].xpath(".//*[@class='content']")
            for aei in aes:
                anwsers.append(HTML.tostring(aei,encoding="utf-8"))
        q["anwsers"] = anwsers
        return q


class SearchHandler(BaseHandler):
    @tornado.web.asynchronous
    def get(self, keyword=None):
        if not keyword:
            #return
            self.redirect("/")
        else:
            self.keyword = keyword
            self.title = keyword
            baidu = "http://zhidao.baidu.com/q?word=" + tornado.escape.url_escape(keyword) + "&ct=17&pn=0&tn=ikaslist&rn=10&lm=0"
            hc = tornado.httpclient.AsyncHTTPClient()
            hc.fetch(baidu, self._on_load)

    def _on_load(self,resp):
        offset1 = resp.body.find("<table border=0 cellpadding=0 cellspacing=0><tr><td class=f>")
        offset2 = resp.body.find("<span id=\"mingren_icon\"")
        body = "<html><body>" + resp.body[offset1:offset2] + "</body></html>"
        try:
            body = body.decode('gbk')
        except:
            pass
        list,table = self._parse(body)
        global static_keywords
        rand_keys = []
        for i in range(20):
            r = random.randint(0,len(static_keywords))
            rand_keys.append(static_keywords[r])

        self.render("search.html", list=list,keyword=self.keyword, rkeys = rand_keys, rtable = table)

    def _parse(self,document):
        list = []
        alist = []
        doc = HTML.fromstring(document)
        result = doc.xpath("/html/body/table")
        for t in result:
            try:
                cells = t.xpath(".//td[@class='f']")[0].getchildren()
                link = cells[0].items()[0][1]
                qnumber = link.replace('/question/','').split('.')[0]
                title = cells[0]
                title.set("href","/q/" + qnumber)
                title = HTML.tostring(cells[0],encoding="utf-8")
                short = HTML.tostring(cells[2],encoding="utf-8")
                tk = dict(title=title, link=link, description=short,qnumber=qnumber)
                list.append(tk)
            except Exception,e:
                logging.error("can not parse this record : %s",e)
        while list:
            alist.append(list.pop(random.randrange(len(list))))

        '''parse relation questions'''
        result = doc.xpath("//td[@class='f14']")
        rtable = None
        global static_keywords
        if result:
            for rt in result:
                a = rt.getchildren()[0]
                a.set("href","/s/" + a.text_content())
                kindex = -1
                try:
                    kindex = static_keywords.index(a.text_content())
                except:
                    pass
                if kindex == -1:
                    static_keywords.append(a.text_content())
            try:
                rtable = HTML.tostring(result[0].getparent().getparent().getparent(),encoding="utf-8")
            except:
                pass
        return alist, rtable




def loadrandomkeys():
    global static_keywords
    f = open(options.keysfile,"r")
    static_keywords = f.read().split('\n')
    logging.info("%d keywords loaded", len(static_keywords))
    


if __name__ == '__main__':
    tornado.options.parse_command_line()
    loadrandomkeys()
    app = Application()
    http_server = tornado.httpserver.HTTPServer(app)
    http_server.listen(options.port)
    try:
        tornado.ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        tornado.ioloop.IOLoop.instance().stop()
# vim: ts=4 sts=4 sw=4 si et

