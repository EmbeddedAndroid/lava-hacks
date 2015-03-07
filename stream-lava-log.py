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
    def __init__(self, config_sources=None):
        self.config_sources = config_sources or list()

    def add_config_override(self, config_source):
        self.config_sources.insert(0, config_source)

    def has_enough_config(self):
        return (self.get_config_variable('username') and
                self.get_config_variable('token') and
                self.get_config_variable('server'))

    def construct_url(self):
        if not self.has_enough_config():
            raise Exception("Not enough configuration to construct the URL")

        url = urlparse.urlparse(self.get_config_variable('server'))

        if not url.path.endswith(('/RPC2', '/RPC2/')):
            print "LAVA Server URL must end with /RPC2 or /RPC2/"
            exit(1)

        return (url.scheme + '://' +
                self.get_config_variable('username') + ':' +
                self.get_config_variable('token') +
                '@' + url.netloc + url.path)

    def get_config_variable(self, variable_name):
        for config_source in self.config_sources:
            method_name = 'get_%s' % variable_name
            if hasattr(config_source, method_name):
                variable = getattr(config_source, method_name)()
                if variable:
                    return variable


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
        self.job = args.get('job')

    def get_username(self):
        return self.username

    def get_token(self):
        return self.token

    def get_server(self):
        return self.server

    def get_job(self):
        return self.job


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

class LavaRunJob(object):
    def __init__(self, configuration):
        self.configuration = configuration
        self.connection = connect(configuration.construct_url())
        self.END_STATES = ['Complete', 'Incomplete', 'Canceled']
        self.job_id = self.configuration.get_config_variable('job')
        self.printed_output = None

    def is_running(self):
        job_status = self.get_status()['job_status']
        return job_status not in self.END_STATES

    def get_status(self):
        return self.connection.scheduler.job_status(self.job_id)

    def get_output(self):
        return self.connection.scheduler.job_output(self.job_id)

    def print_output(self):
        full_output = str(self.get_output())
        if self.printed_output:
            new_output = full_output[len(self.printed_output):]
        else:
            new_output = full_output
        for s in stream_string(new_output):
            print s
        self.printed_output = full_output

    def run(self):
        is_running = True

        while is_running:
            try:
                self.print_output()
                time.sleep(2)
            except (xmlrpclib.ProtocolError, xmlrpclib.Fault, IOError):
                pass

            is_running = self.is_running()

        print 'Job has finished'


def get_config(args):
    config = Config()
    config.add_config_override(FileConfigParser(filename=args.get('config', None), section=args.get('section', None)))
    config.add_config_override(ArgumentParser(args))
    return config

def main(args):
    lava_job = LavaRunJob(get_config(args))

    lava_job.run()

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
