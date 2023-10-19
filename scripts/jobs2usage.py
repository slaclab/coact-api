#!/usr/bin/env python3
import os
import sys
import subprocess
import datetime
from dateutil import parser, tz
import pytz
import re
import traceback
import json
import argparse
import logging

"""
Use SLURM sacct stats to generate a JSON file with job information.
This is then consumed by load_sample_job_data to load the jobs into the database.
Combines various methods from the original iris code
"""

fromslurm = {}
todb = {}


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, float) and not math.isfinite(o):
            return str(o)
        elif isinstance(o, datetime.datetime):
            # Use var d = new Date(str) in JS to deserialize
            # d.toJSON() in JS to convert to a string readable by datetime.strptime(str, '%Y-%m-%dT%H:%M:%S.%fZ')
            return o.astimezone(pytz.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        return json.JSONEncoder.default(self, o)

def fetch_data_from_SLURM(daystr):
    day = datetime.datetime(int(daystr[0:4]), int(daystr[4:6]), int(daystr[6:8]))
    start = day.strftime("%Y-%m-%d")
    commandstr = f"""SLURM_TIME_FORMAT=%s sacct --allusers --duplicates --allclusters --allocations --starttime="{start}T00:00:00" --endtime="{start}T23:59:59" --truncate --parsable2 --format=JobID,User,UID,Account,Partition,QOS,Submit,Start,End,Elapsed,NCPUS,AllocNodes,AllocTRES,CPUTimeRAW,NodeList,Reservation,ReservationId,State"""
    print(commandstr)
    process = subprocess.Popen(commandstr, shell=True, stdout=subprocess.PIPE)
    index = 0
    c = 0
    s = 0
    for line in iter(process.stdout.readline, b''):
        fields = line.decode("utf-8").split("|")
        if index == 0 or ( len(fields) >= 10 and line.find(b"PENDING") == -1 and int(fields[7]) < int(fields[8]) and fields[9] != "00:00:00" ):
            yield line.decode("utf-8")
            if index > 0:
                c += 1
                s += int(fields[8]) - int(fields[7])
            index += 1
    yield "--- %d %d" % (c, s)

def conv(s, fx, default=None):
    try:
        return fx(s)
    except:
        return default

def kilos_to_int(s):
    m = re.match(r"(^[0-9.]+)([KMG])?", s.upper())
    if m:
        mul = 1
        g = m.group(2)
        if g:
            p = "KMG".find(g)
            if p >= 0:
                mul = math.pow(2, (p + 1) * 10)
            else:
                raise Exception("Can't handle multiplier=%s for value=%s" % (g, s))
        return int(float(m.group(1)) * mul)
    else:
        raise Exception("Can't parse %s" % s)


def parse_datetime(value, make_date=False):
    if not value:
        return None
    if re.match(r"^[0-9]+$", value):
        # assume the epoch time sent is in UTC
        dt = datetime.datetime.fromtimestamp(int(value), tz.gettz("UTC"))
    else:
        if value.find("T") > -1:
            dt = parser.isoparse(value)
        else:
            dt = parser.parse(value)

        # if "aware" timestamp (ie. has timezone), convert to PST
        if dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None:
            dt = dt.astimezone(tz.gettz(database.TZ))
    return datetime.datetime.combine(datetime.date(dt.year, dt.month, dt.day), datetime.time()) if make_date else dt


def _to_job(index, parts):
    parts_d = { field: parts[idx] for field, idx in index.items() }
    nodelist = parts_d["NodeList"]
    return {
        "jobId": parts_d["JobID"],
        "username": parts_d["User"],
        "uid": conv(parts_d["UID"], int, 0),
        "accountName": parts_d["Account"],
        "partitionName": parts_d["Partition"],
        "qos": parts_d["QOS"],
        "startTs": parts_d["Start"],
        "endTs": parts_d["End"],
        "ncpus": conv(parts_d["NCPUS"], int, 0),
        "allocNodes": kilos_to_int(parts_d["AllocNodes"]),
        "allocTres": parts_d["AllocTRES"],
        "nodelist": nodelist,
        "reservation": parts_d["Reservation"],
        "reservationId": parts_d["ReservationId"],
        "submitter": None,
        "submitTs": parts_d["Submit"],
        "officialImport": True
    }


def process_cache(daystr, compusage):
    first = True
    index = {}
    buffer = []
    job_count = 0
    total_secs = 0
    for line in fetch_data_from_SLURM(daystr):
        if line:
            parts = line.split("|")
            print(parts)
            fromslurm[parts[0]] = parts
            if first:
                index = { s: idx for idx, s in enumerate(parts) }
                first = False
            else:
                if line.startswith("--- "):
                    # verification info follows: line_count and total time
                    s = line.split(" ")
                    job_count = int(s[1].strip())
                    total_secs = int(s[2].strip())
                    break
                buffer.append(_to_job(index, parts))
                if len(buffer) >= 1000:
                    print("+++ Upserting %d jobs..." % len(buffer))
                    compusage.save_jobs(buffer)
                    buffer = []
    if len(buffer) > 0:
        print("+++ Final upsert of %d jobs..." % len(buffer))
        compusage.save_jobs(buffer)

    return job_count, total_secs

def get_computed_values(startTs, endTs, submitTs, alloc_nodes, ncpus, qos):
    # calculate elapsed time as UTC so we don't get bitten by DST
    elapsed_secs = (endTs.astimezone(pytz.utc) - startTs.astimezone(pytz.utc)).total_seconds()
    wait_time = (startTs.astimezone(pytz.utc) - submitTs.astimezone(pytz.utc)).total_seconds() if submitTs else None
    return elapsed_secs, wait_time




class ComputeUsage():
    def __init__(self):
        self.todb = {}

    def save_jobs(self, jobs):
        try:
            # gather the values
            values = []
            days = set()
            seen = set()
            ids = []
            index_jobs_offline = False
            realtime_job_ids = []
            for inp in jobs:
                # skip dupes (they cause a sql exception)
                key = "%s,%s" % (inp["jobId"], inp["startTs"])
                if key in seen:
                    continue
                seen.add(key)

                # convert to datetime
                inp["startTs"] = parse_datetime(inp["startTs"])
                inp["endTs"] = parse_datetime(inp["endTs"])
                inp["submitTs"] = parse_datetime(inp.get("submitTs"))

                # assume it's a realtime update
                if "officialImport" not in inp:
                    inp["officialImport"] = False

                if inp["officialImport"]:
                    # if even one job is part of an official import, we will index the whole day
                    index_jobs_offline = True
                else:
                    # otherwise, keep track of what to index for the given days
                    realtime_job_ids.append(inp["jobId"])

                days.add(datetime.date(inp["startTs"].year, inp["startTs"].month, inp["startTs"].day))

                # compute some values
                inp["elapsedSecs"], inp["waitSecs"] = \
                    get_computed_values(
                        inp["startTs"],
                        inp["endTs"],
                        inp["submitTs"],
                        inp["allocNodes"],
                        inp["ncpus"],
                        inp["qos"])

                inp["username"] = inp.get("username", "")

                values.append(inp)

                ids.append([inp["jobId"], inp["startTs"]])
            if not values:
                raise Exception("Error: no input")

            # Insert all in a single pass.
            # We do this via sqlalchemy core. Orm doesn't support this.
            # http://docs.sqlalchemy.org/en/latest/core/dml.html#sqlalchemy.sql.expression.Insert.values
            print(JSONEncoder(indent=4).encode(values))
            for val in values:
                self.todb[val["jobId"]] = val
            # insert_statement = postgresql.insert(models.Job).values(values)
            # updates = {k: insert_statement.excluded[k] for k in values[0].keys() if k not in ["jobId", "startTs", "created_at", "compute_id"]}
            #
            # # On conflict, update existing row; this is a postgres feature called upsert
            # # http://docs.sqlalchemy.org/en/latest/dialects/postgresql.html?highlight=conflict#insert-on-conflict-upsert
            # do_update_statement = insert_statement.on_conflict_do_update(
            #     index_elements=[models.Job.job_id, models.Job.startTs, models.Job.compute_id],
            #     set_=updates
            # )
            #
            # # the timezone sometimes changes (not sure why) so reset it here
            # session.execute("set timezone to '%s'" % database.TZ)
            #
            # # run it
            # print("Upserting %d rows" % len(values))
            # session.execute(do_update_statement)
            #
            # # replay transfers
            # models.Transfer.replay(session, ids)

            if index_jobs_offline:
                print("Will index jobs off-line.")
                # update the day flags for days changed (this will cause the whole day to be indexed)
                # util.mark_days_updated(session, days, is_job=True)

            print("Committing %d rows" % len(values))
            # session.commit()
            print("Done")

            # the timezone sometimes changes (not sure why) so reset it here
            # session.execute("set timezone to '%s'" % database.TZ)

            # print("index_jobs_offline=", index_jobs_offline, " realtime_job_ids=", len(realtime_job_ids))
            # if not index_jobs_offline and len(realtime_job_ids) > 0:
            #     # just index the given days/job_ids
            #     # todo: maybe do this via rabbitmq? (if it takes too long)
            #     print("REALTIME JOB INDEXER will process %d jobs." % len(realtime_job_ids))
            #     InProcessJobIndexer(days, session, realtime_job_ids).process_all(session)

            return
        except Exception as exc:
            print("Error saving usage: ")
            traceback.print_exc()
            raise exc


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Import data from SLURM using sacct and generate a JSON file that can be consumed by CoAct")
    parser.add_argument("-v", "--verbose", action='store_true', help="Turn on verbose logging")
    parser.add_argument("-d", "--date", help="Load job information for this date. Specify as a YYYYMMDD; for example, 20180524. Defaults to yesterday", default=(datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y%m%d"))
    parser.add_argument("datafolder", help="Save jobs data into this folder as a file named <Date>.json")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    compusage = ComputeUsage()
    process_cache(args.date, compusage)
    with open(os.path.join(args.datafolder, args.date + ".json"), "w") as f:
        json.dump(list(compusage.todb.values()), f, indent=4, cls=JSONEncoder)
    print("Done")
