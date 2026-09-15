"""
TestRail → Confluence Manual Sync
===================================
Usage:
  py testrail_to_confluence.py <run_id>

Example:
  py testrail_to_confluence.py 9054

Setup:
  py -m pip install requests python-dotenv
"""

import sys
import re
import time
import os
import requests
from datetime import datetime
from base64 import b64encode
from dotenv import load_dotenv
from html import escape
# ─────────────────────────────────────────────
# LOAD CREDENTIALS FROM .env FILE
# ─────────────────────────────────────────────

load_dotenv()

TESTRAIL_URL              = os.getenv("TESTRAIL_URL")
TESTRAIL_USER             = os.getenv("TESTRAIL_USER")
TESTRAIL_API_KEY          = os.getenv("TESTRAIL_API_KEY")

CONFLUENCE_URL            = os.getenv("CONFLUENCE_URL")
CONFLUENCE_USER           = os.getenv("CONFLUENCE_USER")
CONFLUENCE_TOKEN          = os.getenv("CONFLUENCE_TOKEN")
CONFLUENCE_SPACE          = os.getenv("CONFLUENCE_SPACE")
CONFLUENCE_PARENT_PAGE_ID = os.getenv("CONFLUENCE_PARENT_PAGE_ID")

JIRA_URL                  = os.getenv("JIRA_URL")

# ─────────────────────────────────────────────
# STATUS MAP  (built dynamically from TestRail)
# ─────────────────────────────────────────────

# Fallback defaults in case the API call fails at import time
STATUS_MAP = {
    1: "Passed",
    2: "Blocked",
    3: "Untested",
    4: "Retest",
    5: "Failed",
}

def load_status_map():
    """Fetch all statuses (including custom) from TestRail and populate STATUS_MAP."""
    global STATUS_MAP
    try:
        creds = f"{TESTRAIL_USER}:{TESTRAIL_API_KEY}"
        headers = {
            "Authorization": f"Basic {b64encode(creds.encode()).decode()}",
            "Content-Type": "application/json",
        }
        url = f"{TESTRAIL_URL}/index.php?/api/v2/get_statuses"
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        statuses = resp.json()
        # TestRail returns a list of status objects; key is `id`, label is `label`
        if isinstance(statuses, list):
            STATUS_MAP = {s["id"]: s["label"] for s in statuses if "id" in s and "label" in s}
        elif isinstance(statuses, dict) and "statuses" in statuses:
            STATUS_MAP = {s["id"]: s["label"] for s in statuses["statuses"] if "id" in s and "label" in s}
        print(f"  ℹ️  Loaded {len(STATUS_MAP)} statuses from TestRail: {STATUS_MAP}")
    except Exception as e:
        print(f"  ⚠️  Could not load statuses from TestRail ({e}), using defaults.")

# ─────────────────────────────────────────────
# TESTRAIL API
# ─────────────────────────────────────────────

def tr_auth():
    creds = f"{TESTRAIL_USER}:{TESTRAIL_API_KEY}"
    return {"Authorization": f"Basic {b64encode(creds.encode()).decode()}"}

def tr_get(endpoint):
    url = f"{TESTRAIL_URL}/index.php?/api/v2/{endpoint}"
    resp = requests.get(url, headers={**tr_auth(), "Content-Type": "application/json"})
    resp.raise_for_status()
    return resp.json()

def get_run(run_id):
    return tr_get(f"get_run/{run_id}")

def get_tests_for_run(run_id):
    data = tr_get(f"get_tests/{run_id}")
    return data.get("tests", [])

def get_results_for_test(test_id):
    data = tr_get(f"get_results/{test_id}&limit=1")
    results = data.get("results", [])
    return results[0] if results else None

def get_testcases_url(run, tests):
    """Auto-build the TestRail testcases URL from run and tests data."""
    suite_id   = run.get("suite_id", "")
    # Get section_id from the actual case data
    case       = tr_get(f"get_case/{tests[0]['case_id']}") if tests else {}
    section_id = case.get("section_id", "")
    return (
        f"{TESTRAIL_URL}/index.php?/suites/view/{suite_id}"
        f"&group_by=cases:section_id&group_order=asc"
        f"&display=compact&display_deleted_cases=0"
        f"&group_id={section_id}"
    )
# ─────────────────────────────────────────────
# CONFLUENCE API
# ─────────────────────────────────────────────

def cf_headers():
    creds = f"{CONFLUENCE_USER}:{CONFLUENCE_TOKEN}"
    return {
        "Authorization": f"Basic {b64encode(creds.encode()).decode()}",
        "Content-Type": "application/json",
    }

def page_exists(title):
    url = f"{CONFLUENCE_URL}/wiki/rest/api/content"
    params = {"title": title, "spaceKey": CONFLUENCE_SPACE, "expand": "version"}
    resp = requests.get(url, headers=cf_headers(), params=params)
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return results[0] if results else None

def create_confluence_page(title, body_html):
    url = f"{CONFLUENCE_URL}/wiki/rest/api/content"
    payload = {
        "type": "page",
        "title": title,
        "space": {"key": CONFLUENCE_SPACE},
        "ancestors": [{"id": CONFLUENCE_PARENT_PAGE_ID}],
        "body": {"storage": {"value": body_html, "representation": "storage"}}
    }
    resp = requests.post(url, headers=cf_headers(), json=payload)
    resp.raise_for_status()
    page = resp.json()
    return f"{CONFLUENCE_URL}/wiki{page['_links']['webui']}"

def update_confluence_page(page_id, version, title, body_html):
    url = f"{CONFLUENCE_URL}/wiki/rest/api/content/{page_id}"
    payload = {
        "type": "page",
        "title": title,
        "version": {"number": version + 1},
        "body": {"storage": {"value": body_html, "representation": "storage"}}
    }
    resp = requests.put(url, headers=cf_headers(), json=payload)
    resp.raise_for_status()
    return f"{CONFLUENCE_URL}/wiki/spaces/{CONFLUENCE_SPACE}/pages/{page_id}"

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def extract_app_id(custom_input):
    """Extract 7-digit numbers starting with 2 or 5 from input data field."""
    if not custom_input:
        return ""
    matches = re.findall(r'\b[25]\d{6}\b', str(custom_input))
    return ", ".join(matches) if matches else ""

def extract_bug_id(comment):
    """Extract Jira ticket from comment like 'Bug created EL-6014'."""
    if not comment:
        return ""
    match = re.search(r'[A-Z]+-\d+', str(comment))
    return match.group(0) if match else ""

# ─────────────────────────────────────────────
# PAGE BUILDER
# ─────────────────────────────────────────────

def build_table_rows(tests):
    rows_html = ""
    for test in tests:
        # Use the status_id directly from the test object (already set by TestRail)
        status_id = test.get("status_id") or 3
        status    = STATUS_MAP.get(status_id, "Unknown")

        # App ID from custom_input field
        app_id = extract_app_id(test.get("custom_input", ""))

        # Bug ID from comment on failed tests only — fetch result only when needed
        bug_id = ""
        if status == "Failed":
            result = get_results_for_test(test["id"])
            if result:
                bug_id = extract_bug_id(result.get("comment", ""))

        color = {
            "Passed":   "#00875A",
            "Failed":   "#DE350B",
            "Blocked":  "#FF991F",
            "Retest":   "#0052CC",
            "Untested": "#6B778C",
        }.get(status, "#6B778C")

        rows_html += f"""
        <tr>
            <td></td>
            <td>{test.get("title", "")}</td>
            <td>C{test.get("case_id", "")}</td>
            <td>{app_id}</td>
            <td><span style="color:{color};font-weight:bold;">{status}</span></td>
            <td>{bug_id}</td>
            <td></td>
        </tr>"""
    return rows_html


def build_page_html(run, tests, testcases_url):
    run_name   = run.get("name", f"Run {run['id']}")
    run_url    = f"{TESTRAIL_URL}/index.php?/runs/view/{run['id']}"
    created_on = datetime.fromtimestamp(run.get("created_on", time.time())).strftime("%Y-%m-%d")

    safe_run_url       = escape(run_url, quote=True)
    safe_testcases_url = escape(testcases_url, quote=True)

    match     = re.search(r'[A-Z]+-\d+', run_name)
    jira_id = run.get("refs") or (re.search(r'[A-Z]+-\d+', run_name) or [None])[0]
    jira_link = (
        f'<a href="{JIRA_URL}/browse/{jira_id}">{jira_id}</a>'
        if jira_id else "N/A"
    )

    table_rows = build_table_rows(tests)

    return f"""
<h2>1. Brief Description</h2>
<p><em>Add your feature description here.</em></p>

<h2>2. Links</h2>
<ul>
  <li><strong>Jira:</strong> {jira_link}</li>
  <li><strong>TestRail Testcases:</strong> <a href="{safe_testcases_url}">{safe_testcases_url}</a></li>
</ul>

<h2>3. Test Scenarios</h2>
<table>
  <colgroup>
    <col style="width:10%"/>
    <col style="width:40%"/>
    <col style="width:10%"/>
    <col style="width:10%"/>
    <col style="width:10%"/>
    <col style="width:10%"/>
    <col style="width:10%"/>
  </colgroup>
  <tbody>
    <tr>
      <th>Scenarios</th>
      <th>Testcase</th>
      <th>TestRail ID</th>
      <th>App ID</th>
      <th>Result</th>
      <th>BugID</th>
      <th>Notes</th>
    </tr>
    {table_rows}
  </tbody>
</table>

<h2>4. TestRail Run Results</h2>
<p>
  <strong>Run:</strong> <a href="{safe_run_url}">{run_name}</a>
</p>
<p>
  <ac:structured-macro ac:name="info">
    <ac:rich-text-body>
      <p>Please attach a screenshot of the TestRail run result here.</p>
    </ac:rich-text-body>
  </ac:structured-macro>
</p>
"""

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def sync_run(run_id):
    print(f"\n── Run {run_id} ──────────────────────────")
    load_status_map()
    try:
        run   = get_run(run_id)
        title = run.get("name", f"Run {run_id}")
        print(f"  📋 Name   : {title}")

        tests = get_tests_for_run(run_id)
        print(f"  🧪 Tests  : {len(tests)} found")

        # Auto-generate testcases URL from run and tests data
        testcases_url = get_testcases_url(run, tests)
        print(f"  🔗 Testcases URL: {testcases_url}")

        html     = build_page_html(run, tests, testcases_url)
        existing = page_exists(title)

        if existing:
            print(f"  ℹ️  Page already exists — updating...")
            url = update_confluence_page(
                existing["id"],
                existing["version"]["number"],
                title,
                html
            )
            print(f"  ✅ Updated : {url}")
        else:
            url = create_confluence_page(title, html)
            print(f"  ✅ Created : {url}")

    except requests.HTTPError as e:
        print(f"  ❌ HTTP error: {e.response.status_code} — {e.response.text}")
    except Exception as e:
        print(f"  ❌ Error: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: py testrail_to_confluence.py <run_id>")
        print("Example: py testrail_to_confluence.py 9054")
        sys.exit(1)

    run_id = int(sys.argv[1])

    print(f"🚀 Syncing Run {run_id}")
    sync_run(run_id)
    print("\n✔ All done.")