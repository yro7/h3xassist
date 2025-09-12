from pydantic import BaseModel, Field


class ActionItemSchema(BaseModel):
    """Single actionable item to be tracked after the meeting."""

    owners: list[str] = Field(
        default_factory=list,
        description="Responsible people as plain human names (no emails or usernames).",
    )
    task: str = Field(
        ...,
        description="Actionable task phrased as a verb phrase (e.g., 'Prepare Q3 sales forecast').",
    )
    due: str | None = Field(
        default=None,
        description="Optional due date in ISO-8601 date (YYYY-MM-DD) or RFC 3339 datetime. Null if not set.",
    )
    priority: str | None = Field(
        default=None,
        description="Optional priority label. Allowed values: 'high', 'medium', 'low'.",
    )


class DecisionItemSchema(BaseModel):
    description: str = Field(..., description="Decision statement in past tense.")
    status: str = Field(..., description="accepted/rejected or similar status label")
    owners: list[str] = Field(default_factory=list, description="Responsible people (names only)")
    effective_from: str | None = Field(
        default=None, description="YYYY-MM-DD when decision takes effect"
    )


class RiskItemSchema(BaseModel):
    description: str = Field(..., description="Risk or blocker description")
    likelihood: str | None = Field(default=None, description="low/medium/high or percentage")
    impact: str | None = Field(default=None, description="low/medium/high")
    mitigation_owners: list[str] = Field(
        default_factory=list, description="Mitigation owners (names only)"
    )
    mitigation_step: str | None = Field(default=None, description="Next mitigation step")


class FollowupItemSchema(BaseModel):
    question: str = Field(..., description="Open question that needs an answer")
    owners: list[str] = Field(
        default_factory=list, description="People expected to answer (names only)"
    )
    due: str | None = Field(default=None, description="Deadline YYYY-MM-DD if any")


class MetricItemSchema(BaseModel):
    name: str = Field(..., description="KPI or metric name")
    current_value: str = Field(..., description="Current value/measurement")
    target_or_next: str | None = Field(
        default=None, description="Target or next step for the metric"
    )


class ContextSchema(BaseModel):
    goal: str | None = Field(default=None, description="Meeting objective")
    status: str | None = Field(
        default=None, description="Current status/facts relevant to the goal"
    )


class NextStepsSchema(BaseModel):
    date_window: str | None = Field(
        default=None, description="Planned date or window for next meeting"
    )
    agenda_owners: list[str] = Field(default_factory=list, description="Agenda owners (names only)")
    prepare: list[str] = Field(default_factory=list, description="Preparation items")


class MeetingSummary(BaseModel):
    """Structured meeting summary suitable for stakeholders and follow-up actions."""

    title: str = Field(..., description="Short descriptive meeting title (<= 120 chars).")
    summary_short: str = Field(
        ..., description="Concise narrative summary in 5-7 sentences (plain text, no markdown)."
    )
    key_points: list[str] = Field(
        ..., description="Concise bullet-level highlights. Prefer 5-10 items."
    )
    context: ContextSchema = Field(
        default_factory=ContextSchema, description="Meeting context: goal and current status."
    )
    decisions: list[DecisionItemSchema] = Field(
        default_factory=list, description="Decisions made with status, owners and effective date."
    )
    action_items: list[ActionItemSchema] = Field(
        default_factory=list,
        description="Concrete action items with owners and optional due dates.",
    )
    risks: list[RiskItemSchema] = Field(
        default_factory=list,
        description="Risks or blockers with likelihood/impact and mitigation details.",
    )
    followups: list[FollowupItemSchema] = Field(
        default_factory=list, description="Open questions with owners and deadlines."
    )
    metrics: list[MetricItemSchema] = Field(
        default_factory=list, description="Metrics or results captured during the meeting."
    )
    next_steps: NextStepsSchema = Field(
        default_factory=NextStepsSchema, description="Plan for the next meeting and preparation."
    )
    my_actions: list[ActionItemSchema] = Field(
        default_factory=list,
        description="Action items specifically assigned to the configured notes owner.",
    )
