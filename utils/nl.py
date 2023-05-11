#!/usr/bin/env python
import re

FIXED_PART_NUMBER_PART_REGEX = r"^([^0-9]+)([0-9]+)$"

class NodeList(object):
    """
    From NERSC iris code
    Unpacks SLURM nodelists into a list of nodes.
    These are of the forms
    "nodelist": "psana1309",
    "nodelist": "psana[1514-1517]",
    "nodelist": "psana[1208-1210,1213-1219,1305-1306,1313,1315,1319,1402,1404-1405,1415]",
    For example, psana[1514-1517] becomes [ psana1514, psana15, psana16, psana17 ]
    """
    def __init__(self, str):
        self.nodes = set()
        m = re.match(r"^(.*?)\[(.*?)\]$", str)
        if m:
            self.prefix = self.fix_str(m.group(1))
            a = m.group(2)
            for s in a.split(","):
                s = s.strip()
                p = s.split("-")
                if len(p) == 1:
                    self.nodes.add(self.fix_str("%s%s" % (self.prefix, int(s))))
                else:
                    for i in range(int(p[0]), int(p[1]) + 1):
                        self.nodes.add(self.fix_str("%s%s" % (self.prefix, i)))
        else:
            m = re.match(r"^([^0-9]+)([0-9]+)$", str)
            if m:
                self.prefix = self.fix_str(m.group(1))
                self.nodes.add(self.fix_str(str))
            else:
                raise Exception()


    def fix_str(self, s):
        """
        Originally meant to remove leading 0's from the number part. Don't think we want to do this but maybe we do...
        If so, replace mm.group(2) with int(mm.group(2))
        """
        mm = re.match(FIXED_PART_NUMBER_PART_REGEX, s)
        return "%s%s" % (mm.group(1), mm.group(2)) if mm else s


    def sorted(self):
        def number_part(s):
            mm = re.match(FIXED_PART_NUMBER_PART_REGEX, s)
            return int(mm.group(2)) if mm else 0

        return sorted(self.nodes, key=number_part)

if __name__ == '__main__':
    print(",".join(NodeList("psana1309").sorted()))
    print(",".join(NodeList("psana[1514-1517]").sorted()))
    print(",".join(NodeList("psana[1208-1210,1213-1219,1305-1306,1313,1315,1319,1402,1404-1405,1415]").sorted()))
