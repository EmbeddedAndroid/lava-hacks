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

def validate_input(username, token, server):
    url = urlparse.urlparse(server)
    if url.path.find('RPC2') == -1:
        print "LAVA Server URL must end with /RPC2"
        exit(1)
    return url.scheme + '://' + username + ':' + token + '@' + url.netloc + url.path


def main(args):
    url = validate_input(args.username, args.token, args.server)
    connection = connect(url)
    run = True
    end_states = ['Complete', 'Incomplete', 'Canceled']
    current_job_file = None
    old_job_file = None
    latest = None

    while run:
        try:
            current_job_file = str(connection.scheduler.job_output(args.job))
            if old_job_file is not None:
                latest = current_job_file[len(old_job_file):]
            else:
                latest = current_job_file
            for s in stream_string(latest):
                print s
            time.sleep(2)
            old_job_file = current_job_file
            status = connection.scheduler.job_status(args.job)
            if status['job_status'] in end_states:
                print 'Job has finished'
                run = False
        except (xmlrpclib.ProtocolError, xmlrpclib.Fault, IOError):
            pass

    exit(0)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", help="username for the LAVA server")
    parser.add_argument("--token", help="token for LAVA server api")
    parser.add_argument("--server", help="server url for LAVA server")
    parser.add_argument("--job", help="job to fetch console log from")
    args = parser.parse_args()
    main(args)