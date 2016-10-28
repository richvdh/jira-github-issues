import re
import threading

import requests

localdata = threading.local()


def sort_jira_key(key):
    """Turns AAAA-1 into AAAA-000001, to try to sort the issues by age"""
    def repl(match):
        return match.group(1) + '0' * (6-len(match.group(2))) + match.group(2)
    return re.sub('^([A-Z]+-)([0-9]+)$', repl, key)


def get_jira_session(config):
    jira_session = getattr(localdata, 'jira_session', None)
    if jira_session is None:
        jira_session = requests.Session()
        if 'jira_password' in config:
            jira_session.auth = (config['jira_user'], config['jira_password'])
        localdata.jira_session = jira_session
    return jira_session
