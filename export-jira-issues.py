#!/usr/bin/env python
#
# usage: export-jira-tickets.py <PROJ>
#
# create a yaml file for each jira ticket, with info about it

import argparse
import datetime
import logging
import multiprocessing
import os.path
import yaml

import common
from jira_to_markdown import to_markdown

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

parser = argparse.ArgumentParser()
parser.add_argument('proj', metavar='PROJ',
                    help='Jira project key')
parser.add_argument('--debug', '-d', action='store_true')
parser.add_argument(
    '--data-dir', default='data',
    help='destination directory for exported issues. (default: %(default)s)'
)
args = parser.parse_args()

if args.debug:
    logging.getLogger().setLevel(logging.DEBUG)

with open("config.yaml") as conf:
    config = yaml.load(conf)


def map_user(user, fallback_to_display_name=True):
    """Map a jira user object to a github @user

    Takes a jira user object with 'name' and 'displayname' properties

    Returns @githubuser, or just display name if fallback_to_display_name is
    True, else None.
    """
    jira_id = user['name']
    if jira_id in config['user_map']:
        return "@" + config['user_map'][jira_id]

    if fallback_to_display_name:
        return user['displayName']

    return None


def map_time(time):
    """ Map from jira's time format to iso format (which github accepts).

    Basically this just drops the millisecond component.
    """
    d = datetime.datetime.strptime(time, '%Y-%m-%dT%H:%M:%S.000%z')
    return d.isoformat()


def export_issue(issue):
    issue_key = issue['key']
    logger.info("Processing %s", issue_key)

    fields = issue['fields']

    # build the body of the github issue
    body = "{body}\n\n(Imported from {url})".format(
        body=to_markdown(fields['description']),
        url=config['jira_url'] + "/browse/"+issue['key']
    )
    creator = fields['reporter']
    if creator['name'] != 'neb':
        body += '\n\n(Reported by %s)' % map_user(creator)

    # build comments for the github issue
    comments = []
    for comment in fields['comment']['comments']:
        comments.append({
            'created_at': map_time(comment['created']),
            'body': "{body}\n\n-- {user}".format(
                body=to_markdown(comment['body']),
                user=map_user(comment['author'])
            )
        })

    # process attachments
    attachments = []
    for a in fields['attachment']:
        # 'content' is actually the url.
        attachments.append(a['content'])

    # process issue links
    links = []
    for l in fields['issuelinks']:
        if 'inwardIssue' in l:
            direction = 'inward'
            other = l['inwardIssue']
        elif 'outwardIssue' in l:
            direction = 'outward'
            other = l['outwardIssue']
        else:
            raise Exception('link neither inward nor outward: %r' % l)
        links.append({
            'direction': direction,
            'other': other['key'],
            'type': l['type'][direction]
        })

    # get external links
    resp = common.get_jira_session(config).get(
        config['jira_url'] + '/rest/api/2/issue/' + issue_key + '/remotelink'
    )
    resp.raise_for_status()
    r = resp.json()
    remotelinks = {}
    for l in r:
        o = l['object']
        remotelinks[o['title']] = o['url']

    # get watchers
    resp = common.get_jira_session(config).get(fields['watches']['self'])
    resp.raise_for_status()
    r = resp.json()
    watchers = []
    for w in r['watchers']:
        u = map_user(w, fallback_to_display_name=False)
        if u is not None:
            watchers.append(u)

    data = {
        'title': fields['summary'],
        'body': body,
        'created_at': map_time(fields['created']),
        'priority': fields['priority']['name'],
        'type': fields['issuetype']['name'],
        'comments': comments,
        'attachments': attachments,
        'remotelinks': remotelinks,
        'links': links,
        'watchers': watchers,
        'labels': fields['labels'],
    }

    output_file = os.path.join(args.data_dir, issue_key + '.yaml')
    with open(output_file, 'w') as f:
        yaml.dump(data, f, default_flow_style=False)


threadpool = multiprocessing.Pool(processes=10)

jql = """
project = {proj} AND resolution IS EMPTY ORDER BY id ASC
""".format(proj=args.proj)

issue_index = 0
total = None
asyncresults = []

while total is None or issue_index < total:
    result = common.get_jira_session(config).get(
        config['jira_url'] + '/rest/api/2/search',
        params={
            'jql': jql,
            'fields': '*all',
            'startAt': issue_index,
        }
    )
    result.raise_for_status()
    r = result.json()

    asyncresults.append(threadpool.map_async(export_issue, r['issues']))

    issue_index += len(r['issues'])
    total = r['total']

threadpool.close()

for r in asyncresults:
    r.get()

threadpool.join()
