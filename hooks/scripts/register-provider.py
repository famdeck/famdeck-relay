#!/usr/bin/env python3
"""Register relay providers with Atlas (idempotent — runs at session start).

Registers two providers:
1. relay — issue tracker configuration per project (file-based)
2. relay-mail — pending mail count from mcp_agent_mail (mcp_query)
"""

from pathlib import Path

PROVIDERS_DIR = Path.home() / ".claude" / "atlas" / "providers"

PROVIDERS = {
    "relay.yaml": """\
name: relay
description: Issue tracker configuration per project
version: "0.1"
project_file: .claude/relay.yaml
field_name: issue_trackers
""",
    "relay-mail.yaml": """\
name: relay-mail
description: Pending mail count from mcp_agent_mail
version: "0.1"
type: mcp_query
endpoint: http://localhost:8765
resource: mail/api/unified-inbox
field_name: pending_mail
""",
}


def main():
    PROVIDERS_DIR.mkdir(parents=True, exist_ok=True)
    for filename, content in PROVIDERS.items():
        (PROVIDERS_DIR / filename).write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
