# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2017 Bitergia
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Authors:
#     Santiago Dueñas <sduenas@bitergia.com>
#

import json
import logging

import requests

from grimoirelab.toolkit.datetime import (datetime_utcnow,
                                          datetime_to_utc,
                                          str_to_datetime)
from grimoirelab.toolkit.uris import urijoin

from ...backend import (Backend,
                        BackendCommand,
                        BackendCommandArgumentParser,
                        metadata)
from ...utils import DEFAULT_DATETIME


logger = logging.getLogger(__name__)


class Functest(Backend):
    """Functest backend for Perceval.

    This class retrieves data from tests stored in a functest
    server. To initialize this class the URL must be provided.
    The `url` will be set as the origin of the data.

    :param url: Functest URL
    :param tag: label used to mark the data
    """
    version = '0.1.2'

    def __init__(self, url, tag=None):
        origin = url

        super().__init__(origin, tag=tag, cache=None)
        self.url = url
        self.client = FunctestClient(url)

    @metadata
    def fetch(self, from_date=DEFAULT_DATETIME, to_date=None):
        """Fetch tests data from the server.

        This method fetches tests data from a server that were
        updated since the given date.

        :param from_date: obtain data updated since this date
        :param to_date: obtain data updated before this date

        :returns: a generator of items
        """
        from_date = datetime_to_utc(from_date)
        to_date = datetime_to_utc(to_date) if to_date else datetime_utcnow()

        logger.info("Fetching tests data of '%s' group from %s to %s",
                    self.url, str(from_date),
                    str(to_date) if to_date else '--')

        pages = self.client.results(from_date=from_date,
                                    to_date=to_date)
        ndata = 0

        for raw_page in pages:
            parsed_data = self.parse_json(raw_page)

            for test_data in parsed_data:
                yield test_data
                ndata += 1

        logger.info("Fetch process completed: %s tests data fetched", ndata)

    @classmethod
    def has_caching(cls):
        """Returns whether it supports caching items on the fetch process.

        :returns: this backend does not support items cache
        """
        return False

    @classmethod
    def has_resuming(cls):
        """Returns whether it supports to resume the fetch process.

        :returns: this backend does not support items resuming
        """
        return False

    @staticmethod
    def metadata_id(item):
        """Extracts the identifier from a Functest item."""

        return str(item['_id'])

    @staticmethod
    def metadata_updated_on(item):
        """Extracts and coverts the update time from a Functest item.

        The timestamp is extracted from 'start_date' field as the item
        does not have any info about when it was updated for the last
        time. This time is converted to a UNIX timestamp.

        :param item: item generated by the backend

        :returns: a UNIX timestamp
        """
        ts = item['start_date']
        ts = str_to_datetime(ts)

        return ts.timestamp()

    @staticmethod
    def metadata_category(item):
        """Extracts the category from a Functest item.

        This backend only generates one type of item which is
        'functest'.
        """
        return 'functest'

    @staticmethod
    def parse_json(raw_json):
        """Parse a Functest JSON stream.

        The method parses a JSON stream and returns a
        dict with the parsed data.

        :param raw_json: JSON string to parse

        :returns: a dict with the parsed data
        """
        result = json.loads(raw_json)
        return result['results']


class FunctestClient:
    """Functest REST API client.

    This class implements a simple client to retrieve data
    from a Functest site using its REST API v1.

    :param base_url: URL of the Functest server
    """
    FUNCTEST_API_PATH = "/api/v1/"

    # API resources
    RRESULTS = 'results'

    # API parameters
    PFROM_DATE = 'from'
    PTO_DATE = 'to'
    PPAGE = 'page'

    def __init__(self, base_url):
        self.base_url = base_url

    def results(self, from_date, to_date=None):
        """Get test cases results."""

        fdt = from_date.strftime("%Y-%m-%d %H:%M:%S")
        params = {
            self.PFROM_DATE: fdt
        }

        if to_date:
            tdt = to_date.strftime("%Y-%m-%d %H:%M:%S")
            params[self.PTO_DATE] = tdt

        while True:
            response = self._fetch(self.RRESULTS, params)
            yield response

            j = json.loads(response)
            page = j['pagination']['current_page']
            total_pages = j['pagination']['total_pages']

            if page >= total_pages:
                break

            params[self.PPAGE] = page + 1

    def _fetch(self, resource, params):
        """Fetch a resource.

        :param resource: resource to fetch
        :param params: dict with the HTTP parameters needed to call
            the given method
        """
        url = urijoin(self.base_url, self.FUNCTEST_API_PATH, resource)

        logger.debug("Functest client requests: %s params: %s",
                     resource, str(params))

        r = requests.get(url, params=params)
        r.raise_for_status()

        return r.text


class FunctestCommand(BackendCommand):
    """Class to run Functest backend from the command line."""

    BACKEND = Functest

    @staticmethod
    def setup_cmd_parser():
        """Returns the Functest argument parser."""

        parser = BackendCommandArgumentParser(from_date=True,
                                              to_date=True)

        # Required arguments
        parser.parser.add_argument('url',
                                   help="URL of the Functest server")

        return parser
