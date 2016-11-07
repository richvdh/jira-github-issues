#!/usr/bin/env python
#
# usage: update-github-links.py
#
# works through the yaml files, and updates the placeholder comment in the
# github issue to include the links which were exported from jira. Also updates
# any PROJ-NN words in the comments to be links.
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

# compile a big regexp which matches any jira key
jira_key_regex = re.compile(
    r'(?<![\w\[])(' +  # don't match after a word character or [
    '|'.join((re.escape(x) for x in config['jira_project_keys'])) +
    r')-\d+(?!\w)'
)


def map_jira_key(key):
    """convert a jira key into either a github link, or a link back to jira"""
    if key in issue_mapping:
        return 'https://github.com/' + issue_mapping[key]
    else:
        return '[%s](https://matrix.org/jira/browse/%s)' % (key, key)


def replace_jira_keys(text):
    """look for jira keys in text and replace with links

    returns (new: string, updated: boolean) where updated is True if a change
    was made
    """

    idx = 0
    updated = False
    while True:
        match = jira_key_regex.search(text, idx)
        if not match:
            return (text, updated)
        s = match.start()

        # logger.debug("got match %r after %s", match, text[s-7:s])

        # don't replace if the previous text is 'browse/', because that means
        # it's already linkified.
        if s > 7 and text[s-7:s] == 'browse/':
            idx = match.end()
            continue

        # looks like a real match. make a substitution
        old = match.group()
        new = map_jira_key(old)
        logger.debug("%s -> %s", old, new)
        text = text[:s] + new + text[match.end():]
        updated = True
        idx += len(new)


def build_link_body(issue_data):
    """ returns a comment body containing the inter-issue links """
    comment = 'Links exported from Jira:\n\n'
    for link in issue_data['links']:
        other = map_jira_key(link['other'])
        comment += '%s %s\n' % (link['type'], other)
    for (k, v) in issue_data['remotelinks'].items():
        comment += '[%s](%s)\n' % (k, v)
    return comment


issues = args.issue
if issues is None:
    issues = (
        fname.replace('.yaml', '')
        for fname in os.listdir(args.data_dir)
        if re.match('[A-Z]+-[0-9]+\.yaml', fname)
    )

for issue_jira_key in issues:
    logger.info("considering %s", issue_jira_key)
    fname = os.path.join(args.data_dir, issue_jira_key+'.yaml')

    issue_data = yaml.load(open(fname))

    if issue_jira_key not in issue_mapping:
        raise Exception('Issue %s not in issue mapping' % issue_jira_key)
    issue_url = 'https://api.github.com/repos/' + issue_mapping[issue_jira_key]

    # get the body of the issue to decide if we need to update it
    resp = github_session.get(issue_url)
    resp.raise_for_status()
    r = resp.json()
    updated_data = {}

    # *don't* do this to title: links don't work in the title anyway, and we
    # deliberately want the jira id there.
    for field in ('body', ):
        (new, updated) = replace_jira_keys(r[field])
        if updated:
            updated_data[field] = new
    if updated_data:
        logger.info("Updating %s", issue_jira_key)
        resp = github_session.patch(
            issue_url,
            json=updated_data,
        )
        resp.raise_for_status()

    # get the comments on this issue
    resp = github_session.get(
        issue_url+"/comments",
    )
    resp.raise_for_status()
    placeholder_issue_url = None
    for comment in resp.json():
        if comment['body'] == 'JIRA LINK PLACEHOLDER':
            newbody = build_link_body(issue_data)
            updated = True
        else:
            (newbody, updated) = replace_jira_keys(comment['body'])

        # update the comment
        if updated:
            resp = github_session.patch(
                comment['url'],
                json={'body': newbody}
            )
            resp.raise_for_status()
