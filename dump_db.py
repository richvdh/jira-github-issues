#!/usr/bin/env python
#
# dump the contents of the db used by import-github-issues.py

import shelve

statusfile = 'data/status.db'
status = shelve.open(statusfile)

for k, v in status.items():
    print("%s: %r" % (k, v))
