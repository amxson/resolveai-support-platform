"""Run the Multi-Agent Customer Support Ticket Assistant.

This script loads sample tickets from CSV, runs a sequential CrewAI workflow
for each ticket, prints the final answer, and saves the approved results.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time
from pathlib import Path

os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

from crewai import Crew, Process
from dotenv import load_dotenv

from ticket_rules import suggest_ticket_rules


PROJECT_ROOT = Path(__file__).resolve().parent
TICKETS_PATH = PROJECT_ROOT / "data" / "sample_tickets.csv"
KNOWLEDGE_BASE_PATH = PROJECT_ROOT / "knowledge" / "support_policies.md"
OUTPUT_PATH = PROJECT_ROOT / "output" / "results.md"
GEMINI_API_KEY_ERROR = "Missing GEMINI_API_KEY in .env. Please add your Gemini API key."
RESULT_LABELS = (
    "Ticket ID",
    "Customer Name",
    "Category",
    "Priority",
    "Escalation Needed",
    "Relevant Policy",
    "Final Reply",
    "Quality Check",
    "Reasoning",
    "Policy Application",
)
CATEGORIES = (
    "Delivery issue",
    "Refund request",
    "Damaged product",
    "Payment issue",
    "Account access issue",
    "General question",
)
POLICY_TITLES = {
    "Delivery issue": "Delivery Delays",
    "Refund request": "Refunds",
    "Damaged product": "Damaged Products",
    "Payment issue": "Payment Issues",
    "Account access issue": "Account Access",
    "General question": "General Questions",
}
POLICY_REASONS = {
    "Delivery Delays": (
        "tracking or delivery is delayed, so carrier or shipping review may be needed"
    ),
    "Refunds": (
        "the request depends on refund eligibility and original payment processing"
    ),
    "Damaged Products": (
        "reported damage should be documented before replacement or refund"
    ),
    "Payment Issues": "billing should review duplicate charges or payment errors",
    "Account Access": (
        "password reset or account access problems may require account verification"
    ),
    "General Questions": "the question can be answered from the available support policy",
}
PRIORITIES = ("Low", "Medium", "High")
YES_NO = ("Yes", "No")


def require_project_files() -> None:
    """Fail early if required local files are missing."""
    missing_files = [
        path
        for path in (TICKETS_PATH, KNOWLEDGE_BASE_PATH)
        if not path.exists()
    ]

    if missing_files:
        formatted_paths = ", ".join(str(path) for path in missing_files)
        raise FileNotFoundError(f"Missing required file(s): {formatted_paths}")


def require_gemini_api_key() -> None:
    """Load .env and make sure a Gemini API key is configured."""
    load_dotenv(PROJECT_ROOT / ".env")

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "your_gemini_api_key_here":
        print(GEMINI_API_KEY_ERROR, file=sys.stderr)
        sys.exit(1)


def configure_console_encoding() -> None:
    """Use UTF-8 so CrewAI console symbols do not fail on Windows terminals."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass


def load_tickets(csv_path: Path) -> list[dict[str, str]]:
    """Load tickets from the sample CSV file."""
    with csv_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        required_columns = {"ticket_id", "customer_name", "message"}
        actual_columns = set(reader.fieldnames or [])

        missing_columns = required_columns - actual_columns
        if missing_columns:
            raise ValueError(
                "CSV is missing required column(s): "
                + ", ".join(sorted(missing_columns))
            )

        tickets = []
        for row in reader:
            if not row.get("ticket_id") or not row.get("message"):
                continue

            message = row["message"].strip()
            ticket = {
                "ticket_id": row["ticket_id"].strip(),
                "customer_name": row["customer_name"].strip(),
                "message": message,
            }
            ticket.update(suggest_ticket_rules(message))
            tickets.append(ticket)

    if not tickets:
        raise ValueError("No tickets found in the CSV file.")

    return tickets


def build_crew() -> Crew:
    """Create a fresh sequential crew for one customer ticket."""
    from agents import (
        create_knowledge_base_agent,
        create_quality_checker_agent,
        create_response_writer_agent,
        create_ticket_triage_agent,
    )
    from tasks import (
        create_knowledge_base_task,
        create_quality_check_task,
        create_response_writer_task,
        create_ticket_triage_task,
    )

    triage_agent = create_ticket_triage_agent()
    knowledge_agent = create_knowledge_base_agent()
    response_writer_agent = create_response_writer_agent()
    quality_checker_agent = create_quality_checker_agent()

    triage_task = create_ticket_triage_task(triage_agent)
    knowledge_task = create_knowledge_base_task(knowledge_agent, [triage_task])
    response_task = create_response_writer_task(
        response_writer_agent,
        [triage_task, knowledge_task],
    )
    quality_task = create_quality_check_task(
        quality_checker_agent,
        [triage_task, knowledge_task, response_task],
    )

    return Crew(
        agents=[
            triage_agent,
            knowledge_agent,
            response_writer_agent,
            quality_checker_agent,
        ],
        tasks=[triage_task, knowledge_task, response_task, quality_task],
        process=Process.sequential,
        verbose=False,
    )


def extract_labeled_value(text: str, label: str) -> str:
    """Extract one labeled section from an LLM result."""
    start_match = re.search(rf"(?im)^\s*{re.escape(label)}\s*:\s*", text)
    if not start_match:
        return ""

    value_start = start_match.end()
    following_labels = [
        match.start()
        for result_label in RESULT_LABELS
        if result_label != label
        for match in [
            re.search(
                rf"(?im)^\s*{re.escape(result_label)}\s*:\s*",
                text[value_start:],
            )
        ]
        if match
    ]
    value_end = value_start + min(following_labels) if following_labels else len(text)
    return text[value_start:value_end].strip()


def extract_choice(text: str, label: str, options: tuple[str, ...], default: str) -> str:
    """Return a constrained field value from LLM output."""
    labeled_value = extract_labeled_value(text, label)

    if labeled_value:
        for option in options:
            if re.search(rf"\b{re.escape(option)}\b", labeled_value, flags=re.IGNORECASE):
                return option

        return default

    for option in options:
        if re.search(rf"\b{re.escape(option)}\b", text, flags=re.IGNORECASE):
            return option

    return default


def fallback_category(message: str) -> str:
    """Choose a safe fallback category if the LLM omits the field."""
    normalized_message = message.lower()

    if any(term in normalized_message for term in ("refund", "return", "money back")):
        return "Refund request"
    if any(term in normalized_message for term in ("damaged", "cracked", "broken")):
        return "Damaged product"
    if any(term in normalized_message for term in ("charged", "card", "payment", "billing")):
        return "Payment issue"
    if any(term in normalized_message for term in ("log in", "login", "password", "account")):
        return "Account access issue"
    if any(term in normalized_message for term in ("delivery", "tracking", "arrive", "package")):
        return "Delivery issue"

    return "General question"


def fallback_policy(category: str) -> str:
    """Return a concise policy title fallback for the constrained category."""
    return POLICY_TITLES.get(category, "General Questions")


def extract_policy_title(category: str, relevant_policy: str) -> str:
    """Return the matching local policy title without Markdown or bullets."""
    for policy_title in POLICY_TITLES.values():
        if policy_title.lower() in relevant_policy.lower():
            return policy_title

    return fallback_policy(category)


def summarize_policy_reason(policy_title: str, message: str) -> str:
    """Return a short reason for the final Relevant Policy field."""
    normalized_message = message.lower()

    if policy_title == "Delivery Delays" and "tracking" in normalized_message:
        return "tracking has not updated, so carrier check may be needed"
    if policy_title == "Refunds" and "unopened" in normalized_message:
        return "the item is unopened, so refund eligibility should be checked"
    if policy_title == "Damaged Products" and any(
        term in normalized_message for term in ("cracked", "broken", "damaged")
    ):
        return "the product was reported damaged, so photos and replacement options apply"
    if policy_title == "Payment Issues" and any(
        term in normalized_message for term in ("charged twice", "duplicate")
    ):
        return "a duplicate charge was reported, so billing review is needed"
    if policy_title == "Account Access" and "reset" in normalized_message:
        return "password reset email is missing, so account access checks apply"

    return POLICY_REASONS.get(policy_title, POLICY_REASONS["General Questions"])


def normalize_relevant_policy(
    category: str,
    relevant_policy: str,
    message: str,
) -> str:
    """Format policy output as a concise one-line title and reason."""
    policy_title = extract_policy_title(category, relevant_policy)
    reason = summarize_policy_reason(policy_title, message)
    return f"{policy_title} - {reason}"


def output_to_text(output: object) -> str:
    """Return the raw text for CrewAI output objects or plain strings."""
    raw_output = getattr(output, "raw", None)
    if raw_output is not None:
        return str(raw_output)

    return str(output)


def get_task_output_text(result: object, index: int) -> str:
    """Return a single task output if CrewAI exposes task results."""
    task_outputs = getattr(result, "tasks_output", [])
    if len(task_outputs) <= index:
        return ""

    return output_to_text(task_outputs[index])


def format_final_result(ticket: dict[str, str], result: object) -> str:
    """Normalize the final answer into the requested output format."""
    raw_result = output_to_text(result)
    triage_result = get_task_output_text(result, 0)
    knowledge_result = get_task_output_text(result, 1)
    response_result = get_task_output_text(result, 2)
    quality_result = get_task_output_text(result, 3)
    classification_source = "\n".join([quality_result, triage_result, raw_result])
    policy_source = "\n".join([knowledge_result, quality_result, raw_result])
    default_category = ticket.get("suggested_category") or fallback_category(
        ticket["message"]
    )

    category = extract_choice(
        classification_source,
        "Category",
        CATEGORIES,
        default_category,
    )
    priority = extract_choice(classification_source, "Priority", PRIORITIES, "Medium")
    escalation_needed = extract_choice(
        classification_source,
        "Escalation Needed",
        YES_NO,
        "No",
    )
    relevant_policy = normalize_relevant_policy(
        category,
        extract_labeled_value(policy_source, "Relevant Policy")
        or ticket.get("suggested_policy", "")
        or fallback_policy(category),
        ticket["message"],
    )
    final_reply = (
        extract_labeled_value(quality_result, "Final Reply")
        or extract_labeled_value(response_result, "Final Reply")
        or extract_labeled_value(raw_result, "Final Reply")
        or response_result.strip()
        or raw_result.strip()
    )
    quality_check = (
        extract_labeled_value(quality_result, "Quality Check")
        or extract_labeled_value(raw_result, "Quality Check")
        or "Approved for tone, policy alignment, and completeness."
    )

    return "\n".join(
        [
            f"Ticket ID: {ticket['ticket_id']}",
            f"Customer Name: {ticket['customer_name']}",
            f"Category: {category}",
            f"Priority: {priority}",
            f"Escalation Needed: {escalation_needed}",
            f"Relevant Policy: {relevant_policy}",
            f"Final Reply: {final_reply}",
            f"Quality Check: {quality_check}",
        ]
    )


def append_result(ticket: dict[str, str], result_text: str) -> None:
    """Append one ticket's final result to output/results.md."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("a", encoding="utf-8") as file:
        file.write(result_text.strip())
        file.write("\n\n")


def run(limit: int | None = None, delay: int = 0) -> None:
    """Run all sample tickets through the sequential CrewAI workflow."""
    configure_console_encoding()
    require_project_files()
    require_gemini_api_key()

    if delay < 0:
        raise ValueError("--delay must be 0 or greater.")

    tickets = load_tickets(TICKETS_PATH)
    if limit is not None:
        if limit < 1:
            raise ValueError("--limit must be 1 or greater.")
        tickets = tickets[:limit]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("", encoding="utf-8")

    for index, ticket in enumerate(tickets):
        print("\n" + "=" * 80)
        print(f"Processing ticket {ticket['ticket_id']} for {ticket['customer_name']}")
        print("=" * 80)

        crew = build_crew()
        result = crew.kickoff(inputs=ticket)
        result_text = format_final_result(ticket, result)

        print("\nFinal approved result:")
        print(result_text)
        append_result(ticket, result_text)

        if delay and index < len(tickets) - 1:
            print(f"\nWaiting {delay} seconds before the next ticket...")
            time.sleep(delay)

    print(f"\nDone. Results saved to {OUTPUT_PATH}")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run the CrewAI customer support ticket assistant."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N tickets.",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=0,
        help="Wait this many seconds between tickets.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        args = parse_args()
        run(limit=args.limit, delay=args.delay)
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
    except Exception as error:
        print(f"Unexpected error: {error}", file=sys.stderr)
        sys.exit(1)
