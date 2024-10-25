from dataclasses import asdict
from typing import NamedTuple, Optional, cast

from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from phoenix.db import models
from phoenix.db.helpers import SupportedSQLDialect
from phoenix.db.insertion.helpers import OnConflict, insert_on_conflict
from phoenix.trace.attributes import get_attribute_value
from phoenix.trace.schemas import Span, SpanStatusCode


class SpanInsertionEvent(NamedTuple):
    project_rowid: int


class ClearProjectSpansEvent(NamedTuple):
    project_rowid: int


async def insert_span(
    session: AsyncSession,
    span: Span,
    project_name: str,
) -> Optional[SpanInsertionEvent]:
    dialect = SupportedSQLDialect(session.bind.dialect.name)
    if (
        project_rowid := await session.scalar(
            select(models.Project.id).filter_by(name=project_name)
        )
    ) is None:
        project_rowid = await session.scalar(
            insert(models.Project).values(name=project_name).returning(models.Project.id)
        )
    assert project_rowid is not None

    trace_id = span.context.trace_id
    trace: Optional[models.Trace] = await session.scalar(
        select(models.Trace).filter_by(trace_id=trace_id)
    )
    if trace:
        trace_needs_update = False
        trace_end_time = None
        trace_project_rowid = None
        if trace.end_time < span.end_time:
            trace_needs_update = True
            trace_end_time = span.end_time
            trace_project_rowid = project_rowid
        trace_start_time = None
        if span.start_time < trace.start_time:
            trace_needs_update = True
            trace_start_time = span.start_time
        if trace_needs_update:
            await session.execute(
                update(models.Trace)
                .filter_by(id=trace.id)
                .values(
                    start_time=trace_start_time or trace.start_time,
                    end_time=trace_end_time or trace.end_time,
                    project_rowid=trace_project_rowid or trace.project_rowid,
                )
            )
    else:
        trace = await session.scalar(
            insert(models.Trace)
            .values(
                project_rowid=project_rowid,
                trace_id=span.context.trace_id,
                start_time=span.start_time,
                end_time=span.end_time,
            )
            .returning(models.Trace)
        )
    assert trace is not None
    cumulative_error_count = int(span.status_code is SpanStatusCode.ERROR)
    cumulative_llm_token_count_prompt = cast(
        int, get_attribute_value(span.attributes, SpanAttributes.LLM_TOKEN_COUNT_PROMPT) or 0
    )
    cumulative_llm_token_count_completion = cast(
        int, get_attribute_value(span.attributes, SpanAttributes.LLM_TOKEN_COUNT_COMPLETION) or 0
    )
    llm_token_count_prompt = cast(
        Optional[int], get_attribute_value(span.attributes, SpanAttributes.LLM_TOKEN_COUNT_PROMPT)
    )
    llm_token_count_completion = cast(
        Optional[int],
        get_attribute_value(span.attributes, SpanAttributes.LLM_TOKEN_COUNT_COMPLETION),
    )
    if accumulation := (
        await session.execute(
            select(
                func.sum(models.Span.cumulative_error_count),
                func.sum(models.Span.cumulative_llm_token_count_prompt),
                func.sum(models.Span.cumulative_llm_token_count_completion),
            ).where(models.Span.parent_id == span.context.span_id)
        )
    ).first():
        cumulative_error_count += cast(int, accumulation[0] or 0)
        cumulative_llm_token_count_prompt += cast(int, accumulation[1] or 0)
        cumulative_llm_token_count_completion += cast(int, accumulation[2] or 0)
    span_rowid = await session.scalar(
        insert_on_conflict(
            dict(
                span_id=span.context.span_id,
                trace_rowid=trace.id,
                parent_id=span.parent_id,
                span_kind=span.span_kind.value,
                name=span.name,
                start_time=span.start_time,
                end_time=span.end_time,
                attributes=span.attributes,
                events=[asdict(event) for event in span.events],
                status_code=span.status_code.value,
                status_message=span.status_message,
                cumulative_error_count=cumulative_error_count,
                cumulative_llm_token_count_prompt=cumulative_llm_token_count_prompt,
                cumulative_llm_token_count_completion=cumulative_llm_token_count_completion,
                llm_token_count_prompt=llm_token_count_prompt,
                llm_token_count_completion=llm_token_count_completion,
            ),
            dialect=dialect,
            table=models.Span,
            unique_by=("span_id",),
            on_conflict=OnConflict.DO_NOTHING,
        ).returning(models.Span.id)
    )
    if span_rowid is None:
        return None
    # Propagate cumulative values to ancestors. This is usually a no-op, since
    # the parent usually arrives after the child. But in the event that a
    # child arrives after its parent, we need to make sure that all the
    # ancestors' cumulative values are updated.
    ancestors = (
        select(models.Span.id, models.Span.parent_id)
        .where(models.Span.span_id == span.parent_id)
        .cte(recursive=True)
    )
    child = ancestors.alias()
    ancestors = ancestors.union_all(
        select(models.Span.id, models.Span.parent_id).join(
            child, models.Span.span_id == child.c.parent_id
        )
    )
    await session.execute(
        update(models.Span)
        .where(models.Span.id.in_(select(ancestors.c.id)))
        .values(
            cumulative_error_count=models.Span.cumulative_error_count + cumulative_error_count,
            cumulative_llm_token_count_prompt=models.Span.cumulative_llm_token_count_prompt
            + cumulative_llm_token_count_prompt,
            cumulative_llm_token_count_completion=models.Span.cumulative_llm_token_count_completion
            + cumulative_llm_token_count_completion,
        )
    )
    if (
        (chat_session_id := get_attribute_value(span.attributes, SpanAttributes.SESSION_ID))
        is not None  # caveat: check for None because it could be the number 0, which is falsy
        and (not isinstance(chat_session_id, str) or chat_session_id.strip())
        and isinstance(
            span_kind := get_attribute_value(
                span.attributes, SpanAttributes.OPENINFERENCE_SPAN_KIND
            ),
            str,
        )
        and span_kind.lower() == OpenInferenceSpanKindValues.LLM.value.lower()
        and (
            get_attribute_value(span.attributes, SpanAttributes.LLM_INPUT_MESSAGES)
            or get_attribute_value(span.attributes, SpanAttributes.LLM_OUTPUT_MESSAGES)
        )
    ):
        session_user = get_attribute_value(span.attributes, SpanAttributes.USER_ID)
        session_id = str(chat_session_id).strip()
        project_session = await session.scalar(
            select(models.ProjectSession).filter_by(session_id=session_id)
        )
        if project_session is None:
            project_session = models.ProjectSession(
                session_id=session_id,
                session_user=session_user,
                project_id=project_rowid,
                start_time=span.start_time,
                end_time=span.end_time,
            )
            session.add(project_session)
            await session.flush()
        else:
            project_session_needs_update = False
            if trace.start_time < project_session.start_time:
                project_session_needs_update = True
                project_session.start_time = trace.start_time
            if project_session.end_time < trace.end_time:
                project_session_needs_update = True
                project_session.end_time = trace.end_time
            if project_session.session_user is None and session_user is not None:
                project_session_needs_update = True
                project_session.session_user = session_user
            if project_session.project_id != project_rowid:
                project_session_needs_update = True
                project_session.project_id = project_rowid
            if project_session_needs_update:
                assert project_session in session.dirty
                await session.flush()
        chat_session_span = models.ChatSessionSpan(
            session_rowid=project_session.id,
            session_id=session_id,
            session_user=session_user,
            timestamp=span.start_time,
            span_rowid=span_rowid,
            trace_rowid=trace.id,
            project_id=project_rowid,
        )
        session.add(chat_session_span)
        await session.flush()
    return SpanInsertionEvent(project_rowid)
