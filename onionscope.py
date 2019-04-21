# coding=utf-8
"""
onionscope.py - Sopel Onion Horoscope Module
Copyright 2018, Natalie Fearnley

http://sopel.chat
"""
from __future__ import unicode_literals, absolute_import, print_function, division

import os
import threading
import sys

import requests
from bs4 import BeautifulSoup

from sopel.module import commands, example

class AmbigiousKeyError(KeyError):
    def __init__(self, key):
        super(AmbigiousKeyError, self).__init__("AmbigiousKeyError: {}".format(key))
        
class LooseDict(dict):        
    def __getitem__(self, partial_key):
        matching_keys = list(filter(lambda s: s.lower().startswith(partial_key.lower()), super(LooseDict, self).keys()))
        if len(matching_keys) < 1:
            raise KeyError(partial_key)
        if len(matching_keys) > 1:
            raise AmbigiousKeyError(partial_key)
        key = matching_keys[0]
        return key, super(LooseDict, self).__getitem__(key)

def loadData(fn, lock):
    lock.acquire()
    try:
        data = {}
        f = open(fn)
        for line in f:
            line = line.strip()
            if sys.version_info.major < 3:
                line = line.decode('utf-8')
            if line:
                try:
                    key, value = line.split('\t', 1)
                except ValueError:
                    continue
                data[key] = value;
        f.close()
    finally:
        lock.release()
    return data

def dumpData(fn, data, lock):
    lock.acquire()
    try:
        f = open(fn, 'w')
        for key, value in data.items():
            line = '\t'.join((key, value)) + '\n'
            try:
                if sys.version_info.major < 3:
                    line = line.encode('utf-8')
                f.write(line)
            except IOError:
                break
        try:
            f.close()
        except IOError:
            pass
    finally:
        lock.release()
    return True

def setup(self):
    fn = self.nick + '-' + self.config.core.host + '.scopes.db'
    self.scopes_filename = os.path.join(self.config.core.homedir, fn)
    if not os.path.exists(self.scopes_filename):
        with open(self.scopes_filename, 'w') as f:
            f.write('')
    self.memory['scopes_lock'] = threading.Lock()
    self.memory['scopes'] = loadData(self.scopes_filename, self.memory['scopes_lock'])
        
def fetchScopes():
    article_id = BeautifulSoup(requests.get("https://www.theonion.com/c/horoscopes").content, 'html.parser').find("article")['data-id']
    sections = BeautifulSoup(requests.get("https://www.theonion.com/{}".format(article_id)).content, 'html.parser').find_all("section", class_="quotable")

    scopes = LooseDict()

    for section in sections:
        sign = section.find(class_="quotable__header").text.split("|")[0].strip()
        text = section.find(class_="quotable__content").text
        scopes[sign] = text

    return scopes

@commands('scope', 'horoscope')
@example('.scope aquarius')
def scope(bot, trigger):
    sign = trigger.group(3)
    if not sign:
        bot.reply("I need to know which Zodiac Sign you want me to look up.")
    scopes = fetchScopes()
    fullsign = None
    try:
        fullsign, message = scopes[sign]
    except AmbigiousKeyError:
        bot.reply("I'm not sure which Zodiac Sign you mean.")
    except KeyError:
        bot.reply("I don't recognize that Zodiac Sign.")
    if fullsign:
        bot.reply("{}: {}".format(fullsign.capitalize(), message))        
    