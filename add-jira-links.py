#!/usr/bin/env python
#
# usage: add-jira-links.py
#
# for each exported issue, add a link from the jira issue to the new github
# issue

import argparse
import logging
import os.path
import yaml

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

with open("config.yaml") as conf:
    config = yaml.load(conf)

mapping_file = os.path.join(args.data_dir, 'issue_mapping.yaml')
with open(mapping_file) as f:
    issue_mapping = yaml.load(f)

issues = args.issue
if issues is None:
    issues = sorted(issue_mapping.keys(), key=common.sort_jira_key)

jira_session = common.get_jira_session(config)
for issue_jira_key in issues:
    logger.info("Updating %s", issue_jira_key)

    url = 'https://github.com/' + issue_mapping[issue_jira_key]
    body = 'Migrated to github: %s' % url

    comment_url = config['jira_url'] + '/rest/api/2/issue/%s/comment' % (
        issue_jira_key
    )
    resp = jira_session.post(comment_url, json={"body": body})
    if resp.status_code >= 400:
        logger.error("Error from jira: %i: %s", resp.status_code, resp.json())
    resp.raise_for_status()
