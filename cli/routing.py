"""Routing rule evaluation — determines which tracker gets an issue."""

from typing import Optional


def evaluate_rules(config: dict, issue: dict) -> dict:
    """Evaluate routing rules and return chosen tracker + merged labels/assignee.

    Args:
        config: Full relay.yaml config dict
        issue: Dict with keys: type, priority, source, labels

    Returns:
        Dict with: tracker (config entry), labels (merged list), assignee (str or None),
                   matched_rule (dict or None)
    """
    trackers = config.get("issue_trackers", [])
    issue_type = issue.get("type", "task")
    issue_priority = issue.get("priority", "medium")
    issue_source = issue.get("source", "human")
    issue_tags = set(issue.get("labels", []))

    merged_labels = list(issue.get("labels", []))
    assignee = issue.get("assignee")
    matched_rule = None
    chosen_tracker = None

    # Evaluate rules across all trackers in config order
    for tracker in trackers:
        for rule in tracker.get("routing_rules", []):
            match = rule.get("match", {})
            if _matches(match, issue_type, issue_priority, issue_source, issue_tags):
                action = rule.get("action", {})
                # Merge labels from rule
                rule_labels = action.get("labels", [])
                merged_labels = list(set(merged_labels + rule_labels))
                # Set assignee if not user-specified
                if not assignee and action.get("assignee"):
                    assignee = action["assignee"]
                matched_rule = rule

                if action.get("default"):
                    chosen_tracker = tracker
                    break
        if chosen_tracker:
            break

    # Fall back to default tracker
    if not chosen_tracker:
        for tracker in trackers:
            if tracker.get("default"):
                chosen_tracker = tracker
                break

    # Fall back to first tracker
    if not chosen_tracker and trackers:
        chosen_tracker = trackers[0]

    # Merge tracker-level default labels
    if chosen_tracker:
        tracker_labels = chosen_tracker.get("labels", [])
        merged_labels = list(set(tracker_labels + merged_labels))

    return {
        "tracker": chosen_tracker,
        "labels": merged_labels,
        "assignee": assignee,
        "matched_rule": matched_rule,
    }


def _matches(match: dict, issue_type: str, priority: str, source: str, tags: set) -> bool:
    """Check if all match conditions are satisfied."""
    if "type" in match and match["type"] != issue_type:
        return False

    if "priority" in match:
        allowed = match["priority"]
        if isinstance(allowed, list):
            if priority not in allowed:
                return False
        elif allowed != priority:
            return False

    if "source" in match and match["source"] != source:
        return False

    if "tags" in match:
        required = set(match["tags"])
        if not required.issubset(tags):
            return False

    return True


def priority_to_number(priority: str) -> int:
    """Convert relay priority string to beads numeric priority."""
    return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(priority, 2)


def priority_to_jira(priority: str) -> str:
    """Convert relay priority to Jira priority name."""
    return {"critical": "Highest", "high": "High", "medium": "Medium", "low": "Low"}.get(priority, "Medium")


def type_to_jira(issue_type: str) -> str:
    """Convert relay type to Jira issue type."""
    return {"bug": "Bug", "feature": "Story", "task": "Task", "chore": "Task"}.get(issue_type, "Task")
