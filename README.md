Scripts to migrate issues from jira to github
=============================================

To start, create a config file `config.yaml` based on `config.sample.yaml`.

1. `export-jira-issues.py`. Searches for issues in the jira project, and writes
a yaml file for each one containing the info we need.

2. `import-github-issues.py`. Starts off github import processes for each
per-issue yaml file, eventually writing out (or updating) a single yaml file
which records the mapping from jira issue to github issue. Uses a state
database to record its progress on each issue, so is safe to re-run on failure.

3. `update-github-links.py`. Linkifies jira issue keys in github comments; also
creates a github comment which records the cross-links from the original jira
issue. By default, runs on each issue for which `export-jira-issues.py`
generated a yaml file.

4. `add-jira-links.py`. Adds comments to the original jira issues pointing to the new
github issue.



