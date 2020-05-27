# coding=utf-8
"""
onionscope.py - Sopel Module to read horoscopes from The Onion
Copyright 2019, Natalie Fearnley

http://sopel.chat
"""
from __future__ import unicode_literals, absolute_import, print_function, division, with_statement

import os
import threading
import sys
import collections
import time

import requests
from bs4 import BeautifulSoup

from sopel.module import commands, example

class CachedDict(collections.MutableMapping):
    def __init__(self, *args, **kwargs):
        self.__filename = kwargs.pop("filename")    # filename to save/load dict to/from (required)
        self.goodfor = kwargs.pop("goodfor", 86400) # number of seconds before the dict is considered stale
        self.store = dict(*args, **kwargs)
        self.__lock = threading.Lock()
        self.lastfetched = 0                      # when the data was last fetched (epoch time)
        if not os.path.exists(self.__filename):
            with open(self.__filename, "w") as f:
                f.write("")
        self.load()

    def load(self):
        self.__lock.acquire()
        try:
            self.store.clear()
            self.lastfetched = 0
            with open(self.__filename) as f:
                try:
                    self.lastfetched = int(f.readline().strip())
                except ValueError:
                    self.lastfetched = 0
                for line in f:
                    line = line.strip()
                    if sys.version_info.major < 3:
                        line = line.decode("utf-8")
                    if line:
                        try:
                            key, value = line.split("\t", 1)
                        except ValueError:
                            continue
                        self.store[key] = value
        finally:
            self.__lock.release()

    def dump(self):
        self.__lock.acquire()
        try:
            with open(self.__filename, "w") as f:
                f.write(str(self.lastfetched) + "\n")
                for key, value in self.store.items():
                    line = "\t".join((key, value)) + "\n"
                    if sys.version_info.major < 3:
                        line = line.encode("utf-8")
                    try:
                        f.write(line)
                    except IOError:
                        break
        finally:
            self.__lock.release()
        return True

    # fetch the dict
    def fetch(self):
        raise NotImplementedError()

    @property
    def stale(self):
        return time.time() - self.lastfetched > self.goodfor

    def __getitem__(self, key):
        return self.store[key]

    def __setitem__(self, key, value):
        self.store[key] = value
        self.dump()

    def __delitem__(self, key):
        del self.store[key]
        self.dump()

    def __iter__(self):
        return iter(self.store)

    def __len__(self):
        return len(self.store)

class ScopesDict(CachedDict):
    def fetch(self):
        if not self.stale:
            return

        self.store.clear()
        self.lastfetched = int(time.time())

        article_id = BeautifulSoup(requests.get("https://www.theonion.com/c/horoscopes").content, "html.parser").find("article")["data-id"]
        sections = BeautifulSoup(requests.get("https://www.theonion.com/{}".format(article_id)).content, "html.parser").find_all("section", class_="quotable")

        for section in sections:
            sign = section.find(class_="quotable__header").text.split("|")[0].strip()
            text = section.find(class_="quotable__content").text
            self.store[sign] = text

        self.dump()

    def get_scopes(self, search_sign):
        self.fetch()
        return {sign.capitalize(): message for (sign, message) in self.store.items() if sign.lower().startswith(search_sign.lower())}

def setup(self):
    filename = self.nick + "-" + self.config.core.host + ".scopes.db"
    fullpath = os.path.join(self.config.core.homedir, filename)
    self.memory["scopes"] = ScopesDict(filename=fullpath)

def comma_join(items, sep=", ", finalsep="and"):
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return "{} {} {}".format(sep.join(items[0:-1]), finalsep, items[-1])

@commands("scope", "horoscope")
@example(".scope aquarius")
def scope(bot, trigger):
    sign = trigger.group(3)
    if not sign:
        bot.reply("I need to know which Zodiac Sign you want me to look up.")
        return
    scopes = bot.memory["scopes"]
    matching_scopes = scopes.get_scopes(sign)
    if not matching_scopes:
        bot.reply("I don't recognize that Zodiac Sign.")
    elif len(matching_scopes) > 1:
        bot.reply("Did you mean {}?".format(comma_join(matching_scopes.keys(), finalsep="or")))
    else:
        fullsign, message = matching_scopes.popitem()
        bot.reply("{}: {}".format(fullsign, message))
