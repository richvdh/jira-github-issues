#!/usr/bin/env python
#
# usage: import-github-issues.py <user>/<project>
#
# imports all the issues to github, and writes a yaml file mapping from jira
# key to github issue.
#
# uses the github import API
# (https://gist.github.com/jonmagic/5282384165e0f86ef105), which allows us to
# add issues and comments in one pass, and also avoids sending notifications to
# everyone who gets mentioned.

import argparse
import logging
import os
import os.path
import re
import shelve
import yaml

import requests

import common

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

parser = argparse.ArgumentParser()
parser.add_argument(
    'proj', metavar='user/proj', help='Github project'
)
parser.add_argument('--debug', '-d', action='store_true')
parser.add_argument(
    '--limit', type=int,
    help=('Maximum number of new issues to import. '
          'Set to zero to just check the states of already-imported issues')
)
parser.add_argument(
    '--issue', action='append', help='Single jira issue to import'
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

github_session = requests.Session()
github_session.headers.update({
    'User-Agent': 'Jira issue import',
    'Accept': 'application/vnd.github.golden-comet-preview+json',
    'Authorization': 'token ' + config['github_token'],
})

# status: {
#   PROJ-N: {
#     status: pending | imported | failed,
#     url: gh import status url,
#     issue_url: github issue url (via the API)
#   }
# }
statusfile = os.path.join(args.data_dir, 'status.db')
status = shelve.open(statusfile)

issues = args.issue
if issues is None:
    issues = [
        fname.replace('.yaml', '')
        for fname in os.listdir(args.data_dir)
        if re.match('[A-Z]+-[0-9]+\.yaml', fname)
    ]

    issues.sort(key=common.sort_jira_key)

#
# STEP 1: kick off import processes for any issues which haven't yet been
# imported.
#
count = 0
for issueKey in issues:
    if args.limit is not None and count >= args.limit:
        break

    fname = os.path.join(args.data_dir, issueKey+'.yaml')

    issueStatus = status.get(issueKey, {})
    stat = issueStatus.setdefault('status', '')

    if stat == 'imported' or stat == 'pending':
        # already done / in progress
        continue

    logger.info('Processing %s (%s)', fname, issueKey)

    j = yaml.load(open(fname))

    body = j['body']

    # just dump attachment links in the body
    if j['attachments']:
        body += '\n\n#### Attachments:\n'
        for a in j['attachments']:
            body += '%s\n' % a

    comments = j['comments']

    # special comment which we will edit to contain the links
    if j['links'] or j['remotelinks']:
        comments.insert(0, {
            'body': "JIRA LINK PLACEHOLDER",
            'created_at': j['created_at'],
        })

    # special comment to subscribe the watchers
    if j['watchers']:
        comments.insert(0, {
            'body': "Jira watchers: " + ' '.join(j['watchers']),
            'created_at': j['created_at'],
        })

    labels = j['labels']

    if j['status'] != 'Pending Triage':
        priority_label = config['priority_to_label_map'].get(j['priority'])
        if priority_label is not None:
            labels.append(priority_label)

        type_label = config['type_to_label_map'].get(j['type'])
        if type_label is not None:
            labels.append(type_label)


    title = j['title'] + ' (' + issueKey + ')'

    data = {
        'issue': {
            'title': title,
            'body': body,
            'created_at': j['created_at'],
            'labels': labels,
        }, 'comments': comments,
    }

    resp = github_session.post(
        'https://api.github.com/repos/%s/import/issues' % (args.proj),
        json=data
    )
    if resp.status_code >= 400:
        logger.error(
            "Error from github: %i: %s", resp.status_code, resp.json()
        )
    resp.raise_for_status()
    issueStatus.update(resp.json())
    status[issueKey] = issueStatus

    count += 1

issues = args.issue
if issues is None:
    issues = status.keys()
has_pending = True
issue_mapping = {}

mapping_file = os.path.join(args.data_dir, 'issue_mapping.yaml')
if os.path.exists(mapping_file):
    with open(mapping_file) as f:
        issue_mapping = yaml.load(f)

#
# STEP 2: check the import progress for each issue in the database, and write a
# mapping file
#
while has_pending:
    has_pending = False
    for issue_jira_key in issues:
        logger.info('Checking %s', issue_jira_key)

        issueStatus = status[issue_jira_key]
        stat = issueStatus['status']

        if stat == 'pending':
            resp = github_session.get(issueStatus['url'])
            resp.raise_for_status()
            issueStatus.update(resp.json())
            status[issue_jira_key] = issueStatus
            logger.info('status now: %s', issueStatus['status'])

        stat = issueStatus['status']
        if stat == 'imported':
            url = issueStatus['issue_url']
            p = url.replace('https://api.github.com/repos/', '')
            link = 'https://github.com/' + p
            logger.info('imported: %s', link)
            issue_mapping[issue_jira_key] = p

        elif stat == 'pending':
            has_pending = True
        else:
            raise Exception("Unknown status " + stat)

with open(mapping_file, 'w') as f:
    yaml.dump(issue_mapping, f, default_flow_style=False)
