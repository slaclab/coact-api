#!/usr/bin/env python

"""
Generate and load test job data and run jobsAggregateForDate.
BE CAREFUL: This test deletes all the jobs before and after the test.
We want to generate job data for these conditions.
Unless specified otherwise, multi day jobs start and end exactly in the middle of the day.
....Id.....|..Day before Y....|...Yesterday......|......Today.......|     Yesterdays Aggregate should have          | Additional checks
 AggTest1  |                  |    S     E       |                  |     All of the resource hours for this job    | D_b_Y and Today have 0
 AggTest2  |        S         |        E         |                  |     50% of the resource hours                 | D_b_Y has 50% and Today has 0
 AggTest3  |                  |        S         |        E         |     50% of the resource hours                 | D_b_Y has 0 and Today has 50%
 AggTest4  |        S         |                  |        E         |     50% of the resource hours                 | D_b_Y and Today have 25% each
 AggTest5  |   S        E     |                  |                  |     0                                         | D_b_Y has 100% and Today has 0
 AggTest6  |                  |                  |    S       E     |     0                                         | D_b_Y has 0 and Today has 100%
           |                  |                  |                  |

Before running this test, make sure we have a fresh copy of the test database.
The repo compute allocation id's are not mapped to any repos
So, after the aggregates, check in Mongo using something like
db.getSiblingDB("iris").repo_daily_compute_usage.find({allocationId: "AggTest1"})
Also, make sure to delete the test database after running this test.
"""

import argparse
import logging
import pytz
import datetime

from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport

from pymongo import MongoClient
from bson import ObjectId

LOG = logging.getLogger(__name__)

jobsImport = gql(
    """
    mutation jobsImport($jobs: [Job!]!) {
        jobsImport(jobs: $jobs) {
                insertedCount
                upsertedCount
                modifiedCount
                deletedCount
        }
    }
    """
)

jobsAggregateForDate = gql(
    """
    mutation jobsAggregateForDate($thedate: CoactDatetime!) { 
        jobsAggregateForDate(thedate: $thedate) {
            status
        }
    }
    """
)

def getNextJobId():
    jobId = 0
    while True:
        yield jobId
        jobId = jobId + 1

nextjobid = getNextJobId()

pacificdaylight = pytz.timezone('America/Los_Angeles')
now = datetime.datetime.now(pytz.utc)

today = now.astimezone(pacificdaylight).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.utc)
yesterday = (now - datetime.timedelta(days=1)).astimezone(pacificdaylight).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.utc)
daybefore = (now - datetime.timedelta(days=2)).astimezone(pacificdaylight).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.utc)

today_midday = now.astimezone(pacificdaylight).replace(hour=12, minute=0, second=0, microsecond=0).astimezone(pytz.utc)
yesterday_midday = (now - datetime.timedelta(days=1)).astimezone(pacificdaylight).replace(hour=12, minute=0, second=0, microsecond=0).astimezone(pytz.utc)
daybefore_midday = (now - datetime.timedelta(days=2)).astimezone(pacificdaylight).replace(hour=12, minute=0, second=0, microsecond=0).astimezone(pytz.utc)

today_6AM = now.astimezone(pacificdaylight).replace(hour=6, minute=0, second=0, microsecond=0).astimezone(pytz.utc)
yesterday_6AM = (now - datetime.timedelta(days=1)).astimezone(pacificdaylight).replace(hour=6, minute=0, second=0, microsecond=0).astimezone(pytz.utc)
daybefore_6AM = (now - datetime.timedelta(days=2)).astimezone(pacificdaylight).replace(hour=6, minute=0, second=0, microsecond=0).astimezone(pytz.utc)

today_6PM = now.astimezone(pacificdaylight).replace(hour=18, minute=0, second=0, microsecond=0).astimezone(pytz.utc)
yesterday_6PM = (now - datetime.timedelta(days=1)).astimezone(pacificdaylight).replace(hour=18, minute=0, second=0, microsecond=0).astimezone(pytz.utc)
daybefore_6PM = (now - datetime.timedelta(days=2)).astimezone(pacificdaylight).replace(hour=18, minute=0, second=0, microsecond=0).astimezone(pytz.utc)

# Make up some allocationId's
testallocids = { f"AggTest{x}": f"646ea77586cdad815e0f5c3{x}" for x in range(1, 10)}


class TestDailyAggregateComputation:
    def __init__(self, args):
        self.reqtransport = RequestsHTTPTransport(url=args.mutationurl, verify=True, retries=3)
        self.mutateclient = Client(transport=self.reqtransport, fetch_schema_from_transport=True)
        self.mongoclient = MongoClient(args.mongourl, tz_aware=True, connect=True)

    def loadJobs(self, jobs):
        self.mongoclient["iris"]["jobs"].delete_many({})
        self.mongoclient["iris"]["repo_daily_peruser_compute_usage"].delete_many({})
        self.mongoclient["iris"]["repo_daily_compute_usage"].delete_many({})
        try:
            result = self.mutateclient.execute(jobsImport, variable_values={"jobs": jobs})["jobsImport"]
            print(f"Imported jobs Inserted={result['insertedCount']}, Upserted={result['upsertedCount']} Deleted={result['deletedCount']}, Modified={result['modifiedCount']}")
        except Exception as e:
            LOG.exception(e)

    def runAggregates(self):
        for dt in [x.strftime('%Y-%m-%dT%H:%M:%S.%fZ') for x in [ daybefore, yesterday, today ]]:
            try:
                result = self.mutateclient.execute(jobsAggregateForDate, variable_values={"thedate": dt})["jobsAggregateForDate"]
                print(f"Computed aggregate for {dt} with result {result['status']}" )
            except Exception as e:
                LOG.exception(e)

    def verifyAggregates(self, allocationId, expectedaggs):
        computedaggs = { x["date"].astimezone(pytz.utc) : x["resourceHours"] for x in self.mongoclient["iris"]["repo_daily_compute_usage"].find({"allocationId": ObjectId(testallocids[allocationId])}) }
        LOG.debug("Expecting %s", expectedaggs)
        LOG.debug("Computed result %s", computedaggs)
        assert(expectedaggs == computedaggs)
        self.mongoclient["iris"]["jobs"].delete_many({})
        self.mongoclient["iris"]["repo_daily_peruser_compute_usage"].delete_many({})
        self.mongoclient["iris"]["repo_daily_compute_usage"].delete_many({})

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Test the daily aggregate computation using standard job start and end times")
    parser.add_argument("-m", "--mutationurl", help="The URL to the CoAct GraphQL API for mutations, for example, https://coact-dev.slac.stanford.edu/graphql", required=True)
    parser.add_argument("-g", "--mongourl", help="The mongo url used to connect to the database to validate the aggregates, for example, mongodb://admin:pwd@localhost:27017/?authSource=admin", required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG)

    pr = TestDailyAggregateComputation(args)

#....Id.....|..Day before Y....|...Yesterday......|......Today.......|     Yesterdays Aggregate should have          | Additional checks
# AggTest1  |                  |    S     E       |                  |     All of the resource hours for this job    | D_b_Y and Today have 0
    jobs = [
            {
                "jobId": next(nextjobid),
                "username": 'mshankar',
                "allocationId": testallocids["AggTest1"],
                "qos": 'normal',
                "startTs": yesterday_6AM.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                "endTs": yesterday_6PM.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                "resourceHours": 100
            }
    ]
    expectedaggs = { yesterday: 100.0 }

    pr.loadJobs(jobs)
    pr.runAggregates()
    pr.verifyAggregates("AggTest1", expectedaggs)

# ....Id.....|..Day before Y....|...Yesterday......|......Today.......|     Yesterdays Aggregate should have          | Additional checks
#  AggTest2  |        S         |        E         |                  |     50% of the resource hours                 | D_b_Y has 50% and Today has 0
    jobs = [
            {
                "jobId": next(nextjobid),
                "username": 'mshankar',
                "allocationId": testallocids["AggTest2"],
                "qos": 'normal',
                "startTs": daybefore_midday.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                "endTs": yesterday_midday.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                "resourceHours": 100
            }
    ]
    expectedaggs = { daybefore: 50.0, yesterday: 50.0 }

    pr.loadJobs(jobs)
    pr.runAggregates()
    pr.verifyAggregates("AggTest2", expectedaggs)





# ....Id.....|..Day before Y....|...Yesterday......|......Today.......|     Yesterdays Aggregate should have          | Additional checks
#  AggTest3  |                  |        S         |        E         |     50% of the resource hours                 | D_b_Y has 0 and Today has 50%
#  AggTest4  |        S         |                  |        E         |     50% of the resource hours                 | D_b_Y and Today have 25% each
#  AggTest5  |   S        E     |                  |                  |     0                                         | D_b_Y has 100% and Today has 0
#  AggTest6  |                  |                  |    S       E     |     0                                         | D_b_Y has 0 and Today has 100%
        #    |                  |                  |                  |

