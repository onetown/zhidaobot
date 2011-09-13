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
    def get_current_user(self):
        return None

class HomeHandler(BaseHandler):
    def get(self):
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
        offset1 = resp.body.find("<div id=\"body\"")
        offset2 = resp.body.find("<div id=\"footer\"")
        body = "<html><body>" + resp.body[offset1:offset2] + "</body></html>"
        try:
            body = body.decode('gbk')
        except:
            pass
        try:
            question = self._parse(body)
            self.render("question.html",q=question)
        except:
            self.render("error.html")

    def _parse(self, body):
        q = {}
        doc = HTML.fromstring(body)
        qbox = doc.xpath("//*[@id=\"question-box\"]")[0]
        qtitle = qbox.xpath(".//h1[@id='question-title']//span")[1]
        qbody = qbox.xpath(".//pre[@id=\"question-content\"]")[0]
        q["title"] = qtitle.text_content()
        q["body"] = qbody.text_content()
        return q


class SearchHandler(BaseHandler):
    @tornado.web.asynchronous
    def get(self, keyword=None):
        if not keyword:
            #return
            self.redirect("/")
        else:
            self.keyword = keyword
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
        list = self._parse(body)
        self.render("search.html", list=list,keyword=self.keyword)

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
                title = cells[0].text_content()
                short = cells[2].text_content()
                tk = dict(title=title, link=link, description=short,qnumber=qnumber)
                list.append(tk)
            except Exception,e:
                logging.error("can not parse this record : %s",e)
        while list:
            alist.append(list.pop(random.randrange(len(list))))
        return alist




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

