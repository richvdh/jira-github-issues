#!/usr/bin/env python
#
# usage: export-github-isssues.py <user>/<project> <labels>
#
# create a yaml file for each github ticket, with info about it

import argparse
import logging
import os.path

import requests
import yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

parser = argparse.ArgumentParser()
parser = argparse.ArgumentParser()
parser.add_argument(
    'proj', metavar='user/proj', help='Github project'
)
parser.add_argument(
    'labels', help='Issue labels'
)
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


def export_issue(issue):
    issue_url = issue['url']
    logger.info("Processing %s", issue_url)

    comments = list(paginated_request(issue["comments_url"]))
    if len(comments) > 0:
        first_comment = comments[0]["body"]
        comments = comments[1:]
    else:
        first_comment = ""

    # build the body of the github issue
    body = u"{body}\n\n_(Imported from {url})_".format(
        body=first_comment,
        url=issue['html_url'],
    )

    creator = issue["user"]["login"]
    if creator != 'matrixbot':
        body += '\n\n_(Reported by @%s)_' % creator

    data = {
        'title': issue['title'],
        'body': body,
        'created_at': issue['created_at'],
        'priority': None,
        'type': 'issue',
        'status': 'Open',
        'comments': [],
        'attachments': [],
        'remotelinks': [],
        'links': [],
        'watchers': [],
        'labels': [label["name"] for label in issue["labels"]],
    }

    for comment in comments:
        data["comments"].append({
            'created_at': comment['created_at'],
            'body': u"_From @{user}:_\n\n{body}".format(
                body=comment['body'],
                user=comment['user']['login'],
            )
        })

    output_file = os.path.join(args.data_dir, str(issue['number']) + '.yaml')
    with open(output_file, 'w') as f:
        yaml.dump(data, f, default_flow_style=False)


def get_issues(proj, params):
    return paginated_request(
        'https://api.github.com/repos/%s/issues' % (proj),
        params=params,
    )


def paginated_request(url, method="get", **kwargs):
    resp = github_session.request(method, url, **kwargs)
    resp.raise_for_status()
    for item in resp.json():
        yield item
    while "next" in resp.links:
        logger.info("Requesting %s", url)
        resp = github_session.get(resp.links["next"]["url"])
        resp.raise_for_status()
        for item in resp.json():
            yield item


github_session = requests.Session()
github_session.headers.update({
    'User-Agent': 'Jira issue import',
    'Accept': 'application/vnd.github.v3+json',
    'Authorization': 'token ' + config['github_token'],
})

for issue in get_issues(args.proj, { "labels": args.labels }):
    export_issue(issue)
