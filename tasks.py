"""Sequential task definitions for the CrewAI support workflow."""

from __future__ import annotations

from crewai import Agent, Task


def create_ticket_triage_task(agent: Agent) -> Task:
    """Classify the ticket before any policy search or reply writing."""
    return Task(
        description=(
            "Read this customer support ticket and triage it.\n\n"
            "Ticket ID: {ticket_id}\n"
            "Customer name: {customer_name}\n"
            "Message: {message}\n\n"
            "Deterministic suggested category: {suggested_category}\n"
            "Use the suggested category when it matches the customer message.\n\n"
            "Choose exactly one category from this list:\n"
            "- Delivery issue\n"
            "- Refund request\n"
            "- Damaged product\n"
            "- Payment issue\n"
            "- Account access issue\n"
            "- General question\n\n"
            "Do not invent or combine categories. Assign priority as Low, "
            "Medium, or High. Decide whether escalation is needed as Yes or No "
            "and explain why."
        ),
        expected_output=(
            "Use this exact format:\n"
            "Ticket ID: <ticket_id>\n"
            "Customer Name: <customer_name>\n"
            "Category: <one exact category from the allowed list>\n"
            "Priority: <Low, Medium, or High>\n"
            "Escalation Needed: <Yes or No>\n"
            "Reasoning: <brief reason>"
        ),
        agent=agent,
    )


def create_knowledge_base_task(agent: Agent, context: list[Task]) -> Task:
    """Search the local policy file after triage is complete."""
    return Task(
        description=(
            "Using the triage summary and customer message, search the local "
            "knowledge base for the most relevant policy. Use the Local "
            "Knowledge Base Search tool. Do not use web search.\n\n"
            "Ticket ID: {ticket_id}\n"
            "Customer name: {customer_name}\n"
            "Message: {message}\n\n"
            "Suggested policy section: {suggested_policy}\n"
            "Search for the suggested policy section first. If it clearly does "
            "not match the message or triage result, search for the better "
            "local policy section and explain why.\n\n"
            "Return the policy section that best applies and explain how it "
            "should guide the reply. Keep the policy source local. Use the "
            "exact Markdown policy section title returned by the tool. Do not "
            "rename policies or invent policy titles."
        ),
        expected_output=(
            "Use this exact format:\n"
            "Relevant Policy: <short policy name - one short reason, no Markdown headers, no bullet lists>\n"
            "Policy Application: <brief explanation of how the policy applies>"
        ),
        agent=agent,
        context=context,
    )


def create_response_writer_task(agent: Agent, context: list[Task]) -> Task:
    """Draft the customer-facing response from the triage and policy details."""
    return Task(
        description=(
            "Write a professional customer support reply for this ticket.\n\n"
            "Ticket ID: {ticket_id}\n"
            "Customer name: {customer_name}\n"
            "Message: {message}\n\n"
            "Use the triage result and relevant local policy. The reply should "
            "be polite, clear, helpful, and specific. If escalation is needed, "
            "say that the issue will be escalated to the appropriate team. Do "
            "not promise a resolution time unless the policy provides one. Do "
            "not invent company names, policy names, dates, tracking details, "
            "or placeholder honorifics. Keep the reply between 100 and 180 words."
        ),
        expected_output=(
            "Use this exact format:\n"
            "Final Reply: <polished customer-facing reply that follows the "
            "relevant policy and reflects the priority and escalation decision>"
        ),
        agent=agent,
        context=context,
    )


def create_quality_check_task(agent: Agent, context: list[Task]) -> Task:
    """Review the draft and produce the final approved response."""
    return Task(
        description=(
            "Review the drafted customer support reply for this ticket.\n\n"
            "Ticket ID: {ticket_id}\n"
            "Customer name: {customer_name}\n"
            "Message: {message}\n\n"
            "Check politeness, correctness, policy alignment, missing "
            "information, and whether the escalation decision is appropriate. "
            "If the draft needs improvement, revise it. Produce the final "
            "corrected output, not just critique. The category must remain exactly one of: "
            "Delivery issue, Refund request, Damaged product, Payment issue, "
            "Account access issue, General question. Remove invented policy "
            "names, unsupported promises, placeholder company names, and "
            "placeholder honorifics. Keep Final Reply between 100 and 180 words."
        ),
        expected_output=(
            "Use these exact labels in this exact order and do not add extra "
            "top-level sections:\n"
            "Ticket ID: <ticket_id>\n"
            "Customer Name: <customer_name>\n"
            "Category: <one exact allowed category>\n"
            "Priority: <Low, Medium, or High>\n"
            "Escalation Needed: <Yes or No>\n"
            "Relevant Policy: <short policy name - one short reason, no Markdown headers, no bullet lists>\n"
            "Final Reply: <final approved customer-facing reply>\n"
            "Quality Check: <brief approval notes or changes made>"
        ),
        agent=agent,
        context=context,
    )
