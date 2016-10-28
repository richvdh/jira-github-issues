import re

def sort_jira_key(key):
    """Turns AAAA-1 into AAAA-000001, to try to sort the issues by age"""
    return re.sub(
        '^([A-Z]+-)([0-9]+)$',
        lambda match: match.group(1) + '0' * (6-len(match.group(2))) + match.group(2),
        key
    )
