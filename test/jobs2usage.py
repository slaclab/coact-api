#!/usr/bin/env python
import os
import sys
import subprocess
import datetime
from dateutil import parser, tz
import pytz
import re
import traceback
import json

"""
Determine what to enter into the jobs collection based on SLURM sacct stats.
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
            return o.isoformat()
        return json.JSONEncoder.default(self, o)



def get_log(daystr):
   for line in stream(daystr):
	      sys.stdout.write(line)

def stream(daystr):
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
    host_name = "Disambiguated hostname " + nodelist
    if host_name == None:
        raise Exception("Unable to determine hostname for nodelist: %s" % nodelist)
    return {
        "job_id": parts_d["JobID"],
        "user_name": parts_d["User"],
        "uid": conv(parts_d["UID"], int, 0),
        "account_name": parts_d["Account"],
        "partition_name": parts_d["Partition"],
        "qos": parts_d["QOS"],
        "start_ts": parts_d["Start"],
        "end_ts": parts_d["End"],
        "ncpus": conv(parts_d["NCPUS"], int, 0),
        "alloc_nodes": kilos_to_int(parts_d["AllocNodes"]),
        "alloc_tres": parts_d["AllocTRES"],
        "nodelist": nodelist,
        "reservation": parts_d["Reservation"],
        "reservation_id": parts_d["ReservationId"],
        "submitter": None,
        "submit_ts": parts_d["Submit"],
        "host_name": host_name,
        "official_import": True
    }


def process_cache(daystr):
    first = True
    index = {}
    buffer = []
    job_count = 0
    total_secs = 0
    for line in stream(daystr):
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
                    ComputeUsage.save_jobs(buffer, None)
                    buffer = []
    if len(buffer) > 0:
        print("+++ Final upsert of %d jobs..." % len(buffer))
        ComputeUsage.save_jobs(buffer, None)

    return job_count, total_secs

def get_cpu_multiplier(compute, job_cpus, job_nodes):
    return 1
    # compute is self; look up cpus on node from db.
    # if job_nodes <= 1:
    #     # if there's only 1 node, use the number of cpu-s used / threads divided by the total cpu count for a node
    #     return (job_cpus / self.node_cpu_count_divisor) / self.node_cpu_count
    # else:
    #     # otherwise, there's no cpu multiplier
    #     return 1

def get_charge_factor(compute):
    return 1.0

def get_priority_factor(compute_name, qos, node_count, start_ts, project_premium_threshold_reached):
    """Return the queue charge factor as described in the "modifications to base charge" section of
    http://www.nersc.gov/users/accounts/user-accounts/how-usage-is-charged/#toc-anchor-1"""
    return 1.0
    # pf = _get_priority_factor(compute_name, qos, start_ts)
    # if not pf:
    #     # the default, just so job ingestion doesn't stop.
    #     _unknown_qos(compute_name, qos)
    #     return 1.0
    #
    # # Apply node-count discounts
    # if NODE_DISCOUNTS.get(compute_name):
    #     discount = NODE_DISCOUNTS[compute_name].get(pf.name)
    #     if discount and node_count >= discount.min_node_count:
    #         return next(e[1] for e in discount.charge_factor[::-1] if e[0] is None or start_ts.date() >= e[0])
    #
    # # Apply per-project priority factor for premium (or just return the regular charge factor)
    # return pf.high_charge_factor if project_premium_threshold_reached else pf.charge_factor



def get_computed_values(start_ts, end_ts, submit_ts, alloc_nodes, ncpus, qos, compute, project_premium_threshold_reached):
    # calculate elapsed time as UTC so we don't get bitten by DST
    elapsed_secs = (end_ts.astimezone(pytz.utc) - start_ts.astimezone(pytz.utc)).total_seconds()
    wait_time = (start_ts.astimezone(pytz.utc) - submit_ts.astimezone(pytz.utc)).total_seconds() if submit_ts else None
    if alloc_nodes is None:
        if qos == "RESERVE":
            # for RESERVE jobs that don't have alloc_nodes or ncpus
            raw_secs = elapsed_secs
            machine_secs = raw_secs * compute.charge_factor
            queue_charge_factor = 1
        else:
            raise Exception("Only qos=RESERVE can have alloc_nodes==None")
    else:
        raw_secs = elapsed_secs * alloc_nodes * get_cpu_multiplier(compute, ncpus, alloc_nodes)
        machine_secs = raw_secs * get_charge_factor(compute)
        queue_charge_factor = get_priority_factor(
            compute,
            qos,
            alloc_nodes,
            start_ts,
            project_premium_threshold_reached
        )
    nersc_secs = machine_secs * queue_charge_factor
    return elapsed_secs, wait_time, queue_charge_factor, raw_secs, nersc_secs, machine_secs


class ComputeUsage():
    @classmethod
    def save_jobs(cls, jobs, project_thresholds):
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
                key = "%s,%s" % (inp["job_id"], inp["start_ts"])
                if key in seen:
                    continue
                seen.add(key)

                inp["compute_id"] = "compute_id_for_hostname_" + inp["host_name"]
                compute = inp["compute_id"]

                # convert to datetime
                inp["start_ts"] = parse_datetime(inp["start_ts"])
                inp["end_ts"] = parse_datetime(inp["end_ts"])
                inp["submit_ts"] = parse_datetime(inp.get("submit_ts"))

                # assume it's a realtime update
                if "official_import" not in inp:
                    inp["official_import"] = False

                if inp["official_import"]:
                    # if even one job is part of an official import, we will index the whole day
                    index_jobs_offline = True
                else:
                    # otherwise, keep track of what to index for the given days
                    realtime_job_ids.append(inp["job_id"])

                days.add(datetime.date(inp["start_ts"].year, inp["start_ts"].month, inp["start_ts"].day))

                # compute some values
                inp["elapsed_secs"], inp["wait_time"], inp["charge_factor"], inp["raw_secs"], inp["nersc_secs"], inp["machine_secs"] = \
                    get_computed_values(
                        inp["start_ts"],
                        inp["end_ts"],
                        inp["submit_ts"],
                        inp["alloc_nodes"],
                        inp["ncpus"],
                        inp["qos"],
                        compute,
                        False) #models.ComputeAllocation.ran_after_threshold(project_thresholds, inp["account_name"], inp["start_ts"])

                # inp["created_at"] = sa.func.now()
                # inp["updated_at"] = sa.func.now()

                inp["user_name"] = inp.get("user_name", "")

                values.append(inp)

                ids.append([inp["job_id"], inp["start_ts"], inp["compute_id"]])
            if not values:
                return ComputeUsage(status="ERROR", error="Error: no input")

            # Insert all in a single pass.
            # We do this via sqlalchemy core. Orm doesn't support this.
            # http://docs.sqlalchemy.org/en/latest/core/dml.html#sqlalchemy.sql.expression.Insert.values
            print(JSONEncoder(indent=4).encode(values))
            for val in values:
                todb[val["job_id"]] = val
            # insert_statement = postgresql.insert(models.Job).values(values)
            # updates = {k: insert_statement.excluded[k] for k in values[0].keys() if k not in ["job_id", "start_ts", "created_at", "compute_id"]}
            #
            # # On conflict, update existing row; this is a postgres feature called upsert
            # # http://docs.sqlalchemy.org/en/latest/dialects/postgresql.html?highlight=conflict#insert-on-conflict-upsert
            # do_update_statement = insert_statement.on_conflict_do_update(
            #     index_elements=[models.Job.job_id, models.Job.start_ts, models.Job.compute_id],
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
            notify.notify_error("Job import error", exc)
            return ComputeUsage(status="ERROR", error=str(exc))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python ./log.py <YYYYMMDD>")
        print("Eg.: python ./log.py 20180524")
    else:
        process_cache(sys.argv[1])
        # print("************************************************************************************************************************")
        # print(fromslurm["JobID"])
        # print(fromslurm["14353"])
        # print(JSONEncoder(indent=4).encode(todb["14353"]))
