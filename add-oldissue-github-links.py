#!/usr/bin/env python
#
# usage: add-oldissue-github-links.py
#
# for each exported issue, add a link from the old github issue to the new one

import argparse
import logging
import os.path

import requests
import yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

parser = argparse.ArgumentParser()
parser.add_argument('--debug', '-d', action='store_true')
parser.add_argument(
    '--issue', action='append', help='Single issue to update'
)
parser.add_argument(
    '--data-dir', default='data',
    help='destination directory for exported issues. (default: %(default)s)'
)
args = parser.parse_args()

if args.debug:
    logging.getLogger().setLevel(logging.DEBUG)

with open("config.yaml") as conf:
    config = yaml.load(conf)

mapping_file = os.path.join(args.data_dir, 'issue_mapping.yaml')
with open(mapping_file) as f:
    issue_mapping = yaml.load(f)

issues = args.issue
if issues is None:
    issues = sorted(issue_mapping.keys())

github_session = requests.Session()
github_session.headers.update({
    'User-Agent': 'Jira issue import',
    'Accept': 'application/vnd.github.v3+json',
    'Authorization': 'token ' + config['github_token'],
})

for old_issue_key in issues:
    logger.info("Updating %s", old_issue_key)
    url = 'https://github.com/' + issue_mapping[old_issue_key]

    comment_url = 'https://api.github.com/repos/%s/issues/%s/comments' % (
        "matrix-org/matrix-doc",  # FIXME
        old_issue_key,
    )

    body = 'Migrated to: %s' % url

    print("POST %s: %s" % (comment_url, body))
    resp = github_session.post(comment_url, json={"body": body})
    resp.raise_for_status()
