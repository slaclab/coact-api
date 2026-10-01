#!/usr/bin/env python3

"""
Populate facility_compute_purchases.burst_nodes from each facility's current
purchase on each cluster (partition).

This is a manually-run script that writes directly to Mongo. The daemon picks up
the new burst values on its next pass.
"""

import argparse
import datetime
import logging
import os
import sys
from math import sqrt

from pymongo import MongoClient

logger = logging.getLogger(__name__)

MONGODB_URL = os.environ.get("MONGODB_URL", "mongodb://127.0.0.1:27017/")
DB_NAME = os.environ.get("DB_NAME", "iris")


# Equation defining the number of burst nodes based on purchased nodes
def compute_burst_nodes(purchased: float) -> int:
    return int(4 * (1 + sqrt(purchased)))


def current_purchases(db, facilities=None):
    """
    Current purchases grouped by facility:cluster, matching Facility.computepurchases
    in models.py: servers are summed and burst_nodes is the max across the current docs.
    Limited to the named facilities when given.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    match = {"start": {"$lte": now}, "end": {"$gt": now}}
    if facilities:
        match["facility"] = {"$in": list(facilities)}
    return list(db["facility_compute_purchases"].aggregate([
        {"$match": match},
        {"$group": {
            "_id": {"facility": "$facility", "clustername": "$clustername"},
            "servers": {"$sum": "$servers"},
            "burst_nodes": {"$max": "$burst_nodes"},
            "ids": {"$push": "$_id"},
        }},
        {"$sort": {"_id.facility": 1, "_id.clustername": 1}},
    ]))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Compute and store burst_nodes for current facility compute purchases.")
    parser.add_argument("-v", "--verbose", action='store_true', help="Turn on verbose logging")
    parser.add_argument("--dry-run", action='store_true', help="Only report what would change; do not write to Mongo")
    parser.add_argument("--facility", action='append', help="Only act on this facility; repeat for more than one (default: all facilities)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    mongo = MongoClient(
        host=MONGODB_URL, tz_aware=True, connect=True,
        username=os.environ.get("MONGODB_USER", None),
        password=os.environ.get("MONGODB_PASSWORD", None))
    db = mongo[DB_NAME]

    # facility names are matched exactly, so a typo or wrong case would otherwise silently match nothing
    if args.facility:
        known = set(db["facilities"].distinct("name"))
        unknown = [f for f in args.facility if f not in known]
        if unknown:
            for name in unknown:
                similar = [k for k in known if k.lower() == name.lower()]
                hint = f"; did you mean {', '.join(similar)}?" if similar else ""
                logger.error(f"Unknown facility {name}{hint}")
            sys.exit(1)

    changes = []
    print(f"{'facility':<16} {'cluster':<12} {'purchased':>10} {'current':>8} {'new':>8}")
    for grp in current_purchases(db, args.facility):
        facility, clustername = grp["_id"]["facility"], grp["_id"]["clustername"]
        purchased = grp["servers"] or 0
        current = grp["burst_nodes"] or 0
        new = compute_burst_nodes(purchased)
        if new is None or new < 0:
            logger.error(f"Invalid burst node count {new} for {facility}:{clustername}")
            sys.exit(1)
        changed = new != current
        print(f"{facility:<16} {clustername:<12} {purchased:>10g} {current:>8g} {new:>8g}{'  *' if changed else ''}")
        if changed:
            changes.append((facility, clustername, grp["ids"], new))

    if not changes:
        logger.info("No changes")
        sys.exit(0)
    if args.dry_run:
        logger.info(f"{len(changes)} facility:cluster pairs would change; rerun without --dry-run to write")
        sys.exit(0)

    for facility, clustername, ids, new in changes:
        res = db["facility_compute_purchases"].update_many({"_id": {"$in": ids}}, {"$set": {"burst_nodes": new}})
        logger.info(f"{facility}:{clustername} burst_nodes={new} matched={res.matched_count} modified={res.modified_count}")
