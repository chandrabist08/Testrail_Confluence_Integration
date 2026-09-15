# TestRail → Confluence Auto Sync

Automatically creates a Confluence page from a TestRail run — including test results, App IDs, and Bug IDs — with a single command.

---

## How It Works

```
You run the script with a TestRail Run ID
        ↓
Script fetches all test cases in that run
        ↓
For each test: pulls result, App ID (from custom_input if it contains a 7-digit number starting with 2 or 5), Bug ID (from result comment on Failed tests if it contains a Jira-style ticket e.g. EL-6014)
        ↓
Builds a formatted Confluence page matching your sprint QA template
        ↓
Creates the page under your chosen parent folder in Confluence
(or updates it if a page with the same name already exists)
```

---

## Folder Structure

```
my-automation/
├── testrail_to_confluence.py   ← main script
├── .env                        ← your credentials (never share this)
├── README.md                   ← this file
```

---

## Dependencies
| Package | Purpose |
|---|---|
| requests | Makes API calls to TestRail and Confluence |
| python-dotenv | Loads credentials from the .env file |

Install all at once:
```bash
py -m pip install requests python-dotenv
```

## One-Time Setup

### 1. Install Python
- Download from https://python.org/downloads
- During install, check **"Add Python to PATH"**
- Verify: open terminal and run `py --version`

### 2. Install VS Code *(optional but recommended)*
- Download from https://code.visualstudio.com
- Install the **Python extension** from the Extensions sidebar
- You can also use any other terminal or editor you prefer

### 3. Open project folder in VS Code
- File → Open Folder → select your `my-automation` folder
- Terminal → New Terminal (or use your system terminal)

### 4. Install dependencies
```bash
py -m pip install requests python-dotenv
```

### 5. Fill in your `.env` file
Open `.env` and replace all placeholder values:

| Variable | Where to find it |
|---|---|
| `TESTRAIL_URL` | Your TestRail domain e.g. `https://yourcompany.testrail.io` |
| `TESTRAIL_USER` | Your TestRail login email |
| `TESTRAIL_API_KEY` | TestRail → My Settings → API Keys → Add Key |
| `CONFLUENCE_URL` | Your Atlassian domain e.g. `https://yourcompany.atlassian.net` |
| `CONFLUENCE_USER` | Your Confluence login email |
| `CONFLUENCE_TOKEN` | https://id.atlassian.com/manage-profile/security/api-tokens → Create API token |
| `CONFLUENCE_SPACE` | Short space key visible in Confluence URL e.g. `LTR` |
| `CONFLUENCE_PARENT_PAGE_ID` | Open parent page in Confluence → copy ID from URL |
| `JIRA_URL` | Same as your Atlassian domain |


## Every Day Usage

### Step 1 — Get your TestRail Run ID
Open the test run in TestRail and check the URL:
```
https://yourcompany.testrail.io/index.php?/runs/view/1234
                                                       ^^^^
                                                   this is your Run ID

```

### Step 2 — Run the script
Open terminal in VS Code and run:
```bash
py testrail_to_confluence.py 1234
```
Replace `1234` with your actual Run ID.

### Step 3 — Open the link printed in terminal
The script prints the Confluence page URL when done. Open it and manually attach a screenshot of the TestRail run results under **Section 4**.

---

## What Gets Created in Confluence

| Section | Content |
|---|---|
| **1. Brief Description** | Placeholder — edit manually after creation |
| **2. Links** | Clickable Jira ticket link + TestRail Testcases link |
| **3. Test Scenarios** | Full table with Testcase, TestRail ID, App ID, Result (color-coded), Bug ID |
| **4. TestRail Run Results** | Link to the run + placeholder for screenshot |

### Table column details
- **App ID** — auto-filled from the `Input Data` field on each test case. Only populated if the field contains a **7-digit number starting with 2 or 5** (e.g. `2001234` or `5009876`). Multiple matches are comma-separated. Left blank otherwise.
- **Bug ID** — auto-filled from the result comment on **Failed tests only**. Only populated if the comment contains a **Jira-style ticket ID** (uppercase letters followed by a dash and digits, e.g. `EL-6014`). Left blank for Passed/Blocked/Retest/Untested or if no matching pattern is found.
- **Result** — color-coded: green = Passed, red = Failed, orange = Blocked, blue = Retest, grey = Untested

---

## Important Notes

- **`.env` file must never be shared or committed to Git.** Add it to `.gitignore`.
- If a Confluence page with the same name already exists, the script **updates** it instead of creating a duplicate.
- The Jira ticket ID is auto-detected from the TestRail run name (e.g. `Sprint_26.2.4_EL-5388:...` → extracts `EL-5388`).

---

## Troubleshooting

| Error | Fix |
|---|---|
| `pip not recognized` | Use `py -m pip install` instead of `pip install` |
| `404 space not found` | Check `CONFLUENCE_SPACE` — use short key (e.g. `LTR`) not full name |
| `400 Bad Request` | Usually HTML in page body — do not modify the `build_page_html` function |
| `401 Unauthorized` | API token is wrong or expired — regenerate at id.atlassian.com |
| `No tests found` | Run ID is wrong or the run has no test cases assigned |