#!/usr/bin/env python
#
# usage: add-jira-ids-to-github-issues.py
#
# retrospectively add the old Jira keys to the summaries of the github issues.
#
# Reads the mapping file written by import-github-issues.py.
#

import argparse
import logging
import os
import os.path
import re
import yaml

import requests

import common

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

parser = argparse.ArgumentParser()
parser.add_argument('--debug', '-d', action='store_true')
parser.add_argument(
    '--issue', action='append', help='Single jira issue to update'
)
parser.add_argument(
    '--data-dir', default='data',
    help='destination directory for exported issues. (default: %(default)s)'
)
args = parser.parse_args()

if args.debug:
    logging.getLogger().setLevel(logging.DEBUG)

with open('config.yaml') as conf:
    config = yaml.load(conf)

mapping_file = os.path.join(args.data_dir, 'issue_mapping.yaml')
with open(mapping_file) as f:
    issue_mapping = yaml.load(f)

github_session = requests.Session()
github_session.headers.update({
    'User-Agent': 'Jira issue import',
    'Authorization': 'token ' + config['github_token'],
})

issues = args.issue
if issues is None:
    issues = sorted(issue_mapping.keys(), key=common.sort_jira_key)

for issue_jira_key in issues:
    logger.info("Updating %s", issue_jira_key)
    fname = os.path.join(args.data_dir, issue_jira_key+'.yaml')

    j = yaml.load(open(fname))

    issue_url = 'https://api.github.com/repos/' + issue_mapping[issue_jira_key]

    updated_data = {
        'title': j['title'] + ' (' + issue_jira_key + ')'
    }

    resp = github_session.patch(
        issue_url,
        json=updated_data,
    )
    resp.raise_for_status()
