#!/usr/bin/python
#coding=utf-8

# version Alpha 3

import os, sys
import urllib.request
import json
import ssl
from datetime import datetime
import time
import random
import subprocess
import ctypes

class ttpLangLiveRecorder:
    def __init__(self, current_path=''):
        # self.name = name
        if current_path=='':
            self.current_path = os.path.dirname(os.path.abspath(__file__))
        else:
            self.current_path = current_path

    def getLiveInfo(self, langlive_id):
        # ignore ssl
        ctx = ssl.create_default_context()
        # ctx._create_default_https_context = ssl._create_unverified_context
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        live_url = False
        live_id = ""
        nickname = ""
        avatar_url = ""
        liveimg_url = ""

        try:
            url = "https://api.lang.live/langweb/v1/room/liveinfo?room_id=%s" % langlive_id
            response = urllib.request.urlopen(url, context=ctx, timeout=10)
            oLiveInfo = json.loads(response.read())
            # print(oLiveInfo)
        except:
            return live_url, live_id, nickname, avatar_url, liveimg_url

        # get live video url (if any)
        if 'data' not in oLiveInfo:
            return live_url, live_id, nickname, avatar_url, liveimg_url

        if 'live_info' not in oLiveInfo['data']:
            return live_url, live_id, nickname, avatar_url, liveimg_url
        
        if 'liveurl_hls' in oLiveInfo['data']['live_info']:
            live_url = oLiveInfo['data']['live_info']['liveurl_hls']

        if 'live_id' in oLiveInfo['data']['live_info']:
            live_id = oLiveInfo['data']['live_info']['live_id']
        
        if 'nickname' in oLiveInfo['data']['live_info']:
            nickname = oLiveInfo['data']['live_info']['nickname']

        if 'headimg' in oLiveInfo['data']['live_info']:
            avatar_url = oLiveInfo['data']['live_info']['headimg']

        if 'liveimg' in oLiveInfo['data']['live_info']:
            liveimg_url = oLiveInfo['data']['live_info']['liveimg']

        # print(live_url, live_id, nickname)

        return live_url, live_id, nickname, avatar_url, liveimg_url


    def getOutputFile(self, langlive_id):
        #get current date time
        now = datetime.today()
        # format output video filename (i.e. langliveid_date-time.js)
        filename = "%sY_%s.ts" % (langlive_id,  now.strftime("%y%m%d_%H_%M_%S"))
        filespec = os.path.join(self.current_path, filename)
        return filespec

    def getLockFile(self, langlive_id, session_id):
        #get current date time
        now = datetime.today()
        # format output video filename (i.e. langliveid_date-time.js)
        filename = "%s_%s.lock" % (langlive_id, session_id)
        filespec = os.path.join(self.current_path, filename)
        return filespec

    def quickedit(self, enabled=1):
        # This is a patch to the system that sometimes hangs
        '''
        Enable or disable quick edit mode to prevent system hangs, sometimes when using remote desktop
        Param (Enabled)
        enabled = 1(default), enable quick edit mode in python console
        enabled = 0, disable quick edit mode in python console
        '''
        # -10 is input handle => STD_INPUT_HANDLE (DWORD) -10 | https://docs.microsoft.com/en-us/windows/console/getstdhandle
        # default = (0x4|0x80|0x20|0x2|0x10|0x1|0x40|0x200)
        # 0x40 is quick edit, #0x20 is insert mode
        # 0x8 is disabled by default
        # https://docs.microsoft.com/en-us/windows/console/setconsolemode
        kernel32 = ctypes.windll.kernel32
        if enabled:
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-10), (0x4|0x80|0x20|0x2|0x10|0x1|0x40|0x100))
            # print("Console Quick Edit Enabled")
        else:
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-10), (0x4|0x80|0x20|0x2|0x10|0x1|0x00|0x100))
            # print("Console Quick Edit Disabled")
