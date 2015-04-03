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

import os
import sys
import argparse
import urlparse
import datetime
import time
import xmlrpclib
import ConfigParser
import curses

from text_output import TextBlock


class FileOutputHandler(object):
    def __init__(self, file_obj, outputter):
        self.file_obj = file_obj
        self.outputter = outputter

        self.full_output = ""
        self.printed_output = self.full_output


    def run(self, poll_interval):
        while True:
            self._update_output()

            if not self.outputter.is_running(): break

            time.sleep(poll_interval)

        print "Job has finished."


    def _update_output(self):
        self.full_output = str(self.outputter.get_output())
        if self.printed_output:
            new_output = self.full_output[len(self.printed_output):]
        else:
            new_output = self.full_output
        if new_output == 'None':
            self.file_obj.write("No job output...\n")
        elif new_output == '':
            pass
        else:
            self.file_obj.write(new_output)
        self.printed_output = self.full_output


class CursesOutput(object):
    def __init__(self, outputter, follow=True):
        self.outputter = outputter
        self.textblock = TextBlock()
        self.follow = follow

        self.win_height = 0
        self.win_width = 0
        self.cur_line = 0
        self.last_poll_time = None
        self.next_poll_time = datetime.datetime.now()
        self.finished = False


    def run(self, poll_interval):
        curses.wrapper(self._run, poll_interval)


    def _run(self, stdscr, poll_interval=2):
        self.stdscr = stdscr
        while True:
            self.win_height, self.win_width = self.stdscr.getmaxyx()

            if not self.finished and datetime.datetime.now() > self.next_poll_time:
                self._update_output(poll_interval)
                self._refresh()
                self.last_poll_time = self.next_poll_time
                self.next_poll_time = self.last_poll_time + datetime.timedelta(seconds=poll_interval)

            if not self.outputter.is_running():
                self.finished = True

            time.sleep(0.1)


    def _update_output(self, poll_interval):
        self.output = self.outputter.get_output()
        self.textblock.set_width(self.win_width, reflow=False)
        self.textblock.set_text(self.output)


    def _refresh(self):
        self.stdscr.clear()
        output_lines = None
        if self.follow:
            output_lines = self.textblock.get_block(-1, self.win_height)
        else:
            output_lines = self.textblock.get_block(self.cur_line, self.win_height)

        print output_lines
        self._print_lines(output_lines)


    def _print_lines(self, lines):
        for index, line in enumerate(lines):
            self.stdscr.addstr(index, 0, line)
        self.stdscr.refresh()


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


def handle_connection(func):
    def inner(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except xmlrpclib.ProtocolError as e:
            if e.errcode == 502:
                print "Protocol Error: 502 Bad Gateway, retrying..."
            elif e.errcode == 401:
                print "Server authentication error."
                print e
                exit(1)
            else:
                print "Unknown XMLRPC error."
                print e
                exit(1)
        except xmlrpclib.Fault as e:
            if e.faultCode == 404 and e.faultString == \
                    "Job output not found.":
                print "Waiting for job output..."
        except (IOError, Exception) as e:
            print "Function %s raised an exception, exiting..." % func.__name__
            print e
            exit(1)
    return inner


class LavaConnection(object):
    def __init__(self, configuration):
        self.configuration = configuration
        self.connection = None

    @handle_connection
    def connect(self):
        url = self.configuration.construct_url()
        print "Connecting to Server..."
        self.connection = xmlrpclib.ServerProxy(url)
        # Here we make a call to ensure the connection has been made.
        self.connection.system.listMethods()
        print "Connection Successful."

    @handle_connection
    def get_job_status(self, job_id):
        return self.connection.scheduler.job_status(job_id)

    @handle_connection
    def get_job_output(self, job_id):
        return self.connection.scheduler.job_output(job_id)

class LavaRunJob(object):
    def __init__(self, connection, job_id):
        self.END_STATES = ['Complete', 'Incomplete', 'Canceled']
        self.job_id = job_id
        self.connection = connection
        self.poll_interval = 2

    def _get_status(self):
        return self.connection.get_job_status(self.job_id)['job_status']

    def get_output(self):
        return self.connection.get_job_output(self.job_id) or ""

    def is_running(self):
        return self._get_status() not in self.END_STATES

    def connect(self):
        self.connection.connect()


def get_config(args):
    config = Config()
    config.add_config_override(FileConfigParser(filename=args.get('config', None), section=args.get('section', None)))
    config.add_config_override(ArgumentParser(args))
    return config

def main(args):
    config = get_config(args)
    lava_connection = LavaConnection(config)

    lava_job = LavaRunJob(lava_connection,
                          config.get_config_variable('job'))
    lava_job.connect()

    if args["curses"]:
        output_handler = CursesOutput(lava_job)
    else:
        output_handler = FileOutputHandler(sys.stdout, lava_job)

    output_handler.run(2)

    exit(0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", help="configuration for the LAVA server")
    parser.add_argument("--section", help="section in the LAVA config file")
    parser.add_argument("--username", help="username for the LAVA server")
    parser.add_argument("--token", help="token for LAVA server api")
    parser.add_argument("--server", help="server url for LAVA server")
    parser.add_argument("--job", help="job to fetch console log from")
    parser.add_argument("--curses", help="use curses for output", action="store_true")
    args = vars(parser.parse_args())
    main(args)

# vim: set sw=4 sts=4 et fileencoding=utf-8 :
