# Multi-Agent Customer Support Ticket Assistant

This CrewAI project reads local customer support tickets, triages each ticket,
searches a local Markdown knowledge base, drafts a professional customer reply,
quality-checks the reply, prints the final result, and saves output to
`output/results.md`.

The workflow uses 4 agents and CrewAI's `Process.sequential`. Gemini API is the
only LLM provider. The project uses local knowledge-base search and no web
search.

## Project Structure

```text
AGENT/
|-- main.py
|-- agents.py
|-- tasks.py
|-- ticket_rules.py
|-- tools/
|   |-- __init__.py
|   `-- knowledge_base_tool.py
|-- data/
|   `-- sample_tickets.csv
|-- knowledge/
|   `-- support_policies.md
|-- output/
|   `-- .gitkeep
|-- requirements.txt
|-- .env.example
`-- README.md
```

## Agents

### 1. Ticket Triage Agent

Reads the customer ticket, chooses exactly one category, assigns priority as
Low, Medium, or High, and decides whether escalation is needed.

Allowed categories:

- Delivery issue
- Refund request
- Damaged product
- Payment issue
- Account access issue
- General question

### 2. Knowledge Base Agent

Uses the deterministic suggested policy section first, then searches the local
`knowledge/support_policies.md` file with the custom local knowledge-base tool.

### 3. Response Writer Agent

Writes a short professional customer reply between 100 and 180 words using the
triage result and relevant local policy.

### 4. Quality Checker Agent

Produces the final corrected output, not just critique. It checks tone,
correctness, policy alignment, escalation, and final formatting.

## Output Format

Each final result uses exactly these labels:

```text
Ticket ID:
Customer Name:
Category:
Priority:
Escalation Needed:
Relevant Policy:
Final Reply:
Quality Check:
```

## Data

Sample tickets are stored in `data/sample_tickets.csv` with these columns:

```text
ticket_id,customer_name,message
```

The local support policies are stored in `knowledge/support_policies.md`.

## Setup

Get a Gemini API key from Google AI Studio:

```text
https://aistudio.google.com/app/apikey
```

Copy the example environment file:

```bash
copy .env.example .env
```

On macOS or Linux, use:

```bash
cp .env.example .env
```

Open `.env` and add your Gemini API key:

```text
GEMINI_API_KEY=your_real_gemini_api_key
GEMINI_MODEL=gemini/gemini-2.0-flash
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run

From inside the `AGENT` folder, run a quick demo:

```bash
python main.py --limit 2
```

For a full demo with free-tier Gemini rate limits, add a delay between tickets:

```bash
python main.py --limit 5 --delay 45
```

The script will:

1. Check that required local files exist.
2. Check that `GEMINI_API_KEY` is configured in `.env`.
3. Load tickets from `data/sample_tickets.csv`.
4. Add deterministic category and policy suggestions from `ticket_rules.py`.
5. Run the CrewAI workflow with `Process.sequential`.
6. Print each final approved result to the terminal.
7. Wait between tickets when `--delay` is greater than 0.
8. Save final results to `output/results.md`.

## Notes

- Gemini API is the only LLM provider.
- No web search tool is included.
- `output/results.md` is generated each time `main.py` runs.
