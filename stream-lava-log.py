#!/usr/bin/env python
#
# This file is part of lava-hacks.  lava-hacks is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Tyler Baker 2015

import argparse
import urlparse
import time
import xmlrpclib
import ConfigParser, os

class Config(object):
    def __init__(self, config_parser=None):
        if config_parser:
            self.username = config_parser.get_username()
            self.token = config_parser.get_token()
            self.server = config_parser.get_server()

    def construct_url(self):
        if not self.username or not self.token or not self.server:
            raise Exception("DIEE!!!!")

        print self.server

        self.url = urlparse.urlparse(self.server)
        print self.url
        if not self.url.path.endswith(('/RPC2', '/RPC2/')):
            print "LAVA Server URL must end with /RPC2 or /RPC2/"
            exit(1)
        return self.url.scheme + '://' + self.username + ':' + self.token + '@' + self.url.netloc + self.url.path

    def update(self, config):
        if config.get_username(): self.username = config.get_username()
        if config.get_token(): self.token = config.get_token()
        if config.get_server(): self.server = config.get_server()

    def get_username(self):
        return self.username

    def get_token(self):
        return self.token

    def get_server(self):
        return self.server


class FileConfigParser(object):
    def __init__(self, filename=None, section=None):
        self.section = section or "default"
        self.filename = filename or os.path.expanduser('~/.lavarc')

        self.config_parser = ConfigParser.ConfigParser()

        if os.path.isfile(self.filename):
            self.config_parser.readfp(open(self.filename))

        self.username = None
        self.token = None
        self.server = None

    def get_username(self):
        if self.username: return self.username

        if self.config_parser:
            self.username = self.config_parser.get(self.section, 'username')
        return self.username

    def get_token(self):
        if self.token: return self.token

        if self.config_parser:
            self.token = self.config_parser.get(self.section, 'token')
        return self.token

    def get_server(self):
        if self.server: return self.server

        if self.config_parser:
            self.server = self.config_parser.get(self.section, 'server')
        return self.server



class ArgumentParser(object):
    def __init__(self, args):
        self.username = args.get('username')
        self.token = args.get('token')
        self.server = args.get('server')

    def get_username(self):
        return self.username

    def get_token(self):
        return self.token

    def get_server(self):
        return self.server


def stream_string(s):
    separators = '\n'
    start = 0
    end = 0
    for end in range(len(s)):
        if s[end] in separators:
            yield s[start:end]
            start = end + 1
    if start < end:
        yield s[start:end+1]

def connect(url):
    try:
        print "Connecting to Server..."
        connection = xmlrpclib.ServerProxy(url)

        print "Connection Successful!"
        print "connect-to-server : pass"
        return connection
    except (xmlrpclib.ProtocolError, xmlrpclib.Fault, IOError) as e:
        print "CONNECTION ERROR!"
        print "Unable to connect to %s" % url
        print e
        print "connect-to-server : fail"
        exit(1)

def get_config(args):
    config = Config()
    config = Config(FileConfigParser(filename=args.get('config', None), section=args.get('section', None)))
    config.update(Config(ArgumentParser(args)))
    return config

def main(args):
    config = get_config(args)

    url = config.construct_url()

    connection = connect(url)
    run = True
    end_states = ['Complete', 'Incomplete', 'Canceled']
    current_job_file = None
    old_job_file = None
    latest = None

    while run:
        try:
            current_job_file = str(connection.scheduler.job_output(args.get('job')))
            if old_job_file is not None:
                latest = current_job_file[len(old_job_file):]
            else:
                latest = current_job_file
            for s in stream_string(latest):
                print s
            time.sleep(2)
            old_job_file = current_job_file
            status = connection.scheduler.job_status(args.get('job'))
            if status['job_status'] in end_states:
                print 'Job has finished'
                run = False
        except (xmlrpclib.ProtocolError, xmlrpclib.Fault, IOError):
            pass

    exit(0)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", help="configuration for the LAVA server")
    parser.add_argument("--section", help="section in the LAVA config file")
    parser.add_argument("--username", help="username for the LAVA server")
    parser.add_argument("--token", help="token for LAVA server api")
    parser.add_argument("--server", help="server url for LAVA server")
    parser.add_argument("--job", help="job to fetch console log from")
    args = vars(parser.parse_args())
    main(args)
