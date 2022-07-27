#!/usr/bin/env python

import argparse
import logging

from gql import gql, Client
from gql.transport.websockets import WebsocketsTransport

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Load sample data from SLURM into the jobs collection. This is mainly for testing")
    parser.add_argument("-v", "--verbose", action='store_true', help="Turn on verbose logging")
    parser.add_argument("-u", "--url", help="The URL to the CoAct GraphQL API", default="wss://coact-dev.slac.stanford.edu/graphql")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    transport = WebsocketsTransport(url=args.url)

    client = Client(
        transport=transport,
        fetch_schema_from_transport=False,
    )

    # Provide a GraphQL query
    query = gql(
        """
        subscription {
          requests {
            theRequest {
        	reqtype
        	eppn
        	preferredUserName
            }
          }
        }
    """
    )

    for result in client.subscribe(query):
        print (result)
