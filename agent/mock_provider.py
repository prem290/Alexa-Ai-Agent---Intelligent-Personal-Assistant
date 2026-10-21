"""
Deterministic Mock Model Provider for Alexa+ AI Agent.
Simulates high-fidelity agentic intelligence when Amazon Bedrock is unconfigured.
Explicitly labeled as 'mock_development'. Strictly executes real tools and grounds responses.
"""

from datetime import date, timedelta
import re
from typing import Any, Dict, List, Optional

from agent.conversation import ClarificationState, ConfirmationState, ConversationSession
from agent.schemas import AgentResponse, PriorityEnum, TaskStatus, ToolCallRecord
from agent.tools import task_store, tool_registry


class MockAgentProvider:
    """Deterministic agent engine for development and demonstration testing."""

    def invoke(
        self,
        user_message: str,
        session: ConversationSession,
    ) -> AgentResponse:
        """Process user input, determine intent, invoke real tools, and return grounded response."""
        text = user_message.strip()
        text_lower = text.lower()
        tool_records: List[ToolCallRecord] = []

        # -------------------------------------------------------------
        # 1. Check for Pending Destructive Confirmation
        # -------------------------------------------------------------
        if session.pending_confirmation:
            conf_state = session.pending_confirmation
            if any(w in text_lower for w in ["yes", "confirm", "proceed", "sure", "delete it", "ok"]):
                # Execute confirmed deletion
                record = tool_registry.execute(
                    "delete_task",
                    {"task_id": conf_state.target_id, "confirmed": True},
                )
                tool_records.append(record)
                session.pending_confirmation = None
                
                resp_text = (
                    f"Confirmed. I have permanently deleted task **{conf_state.target_id}** "
                    f"('{conf_state.target_title}'). Your task store has been updated."
                )
                return AgentResponse(
                    response_text=resp_text,
                    intent="confirm_delete",
                    tool_calls=tool_records,
                    model_mode="mock_development",
                    conversation_id=session.session_id,
                )
            elif any(w in text_lower for w in ["no", "cancel", "stop", "nevermind", "abort"]):
                session.pending_confirmation = None
                return AgentResponse(
                    response_text=f"Deletion of task {conf_state.target_id} cancelled. No changes were made.",
                    intent="cancel_delete",
                    tool_calls=[],
                    model_mode="mock_development",
                    conversation_id=session.session_id,
                )

        # -------------------------------------------------------------
        # 2. Check for Pending Clarification (e.g. Interview Prep)
        # -------------------------------------------------------------
        if session.pending_clarification:
            clarif = session.pending_clarification
            # Check if user answered days and hours
            days_match = re.search(r"(\d+|one|two|three|four|five)\s+day", text_lower)
            hours_match = re.search(r"(\d+|one|two|three|four)\s+hour", text_lower)

            num_word_map = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
            days = 3
            if days_match:
                d_str = days_match.group(1)
                days = num_word_map.get(d_str, int(d_str) if d_str.isdigit() else 3)

            hours = 1.0
            if hours_match:
                h_str = hours_match.group(1)
                hours = float(num_word_map.get(h_str, int(h_str) if h_str.isdigit() else 1))

            session.pending_clarification = None

            # Create an interview prep task and a daily plan using tools
            task_rec = tool_registry.execute("create_task", {
                "title": f"Technical Interview Intensive: {days}-Day Preparation Sprint",
                "description": f"Focusing on data structures, system design, and algorithms with {hours}h/day commitment.",
                "priority": "urgent",
                "due_date": (date.today() + timedelta(days=days)).isoformat(),
                "estimated_minutes": int(hours * 60),
            })
            tool_records.append(task_rec)
            session.update_task_context_from_record(task_rec)

            plan_rec = tool_registry.execute("create_daily_plan", {
                "available_hours": hours,
                "focus_area": "Interview",
            })
            tool_records.append(plan_rec)
            session.update_task_context_from_record(plan_rec)

            created_task = task_rec.result.get("task", {})
            plan_data = plan_rec.result.get("plan", {})

            resp_text = (
                f"Understood! With **{days} days** and **{hours} hour daily**, I have initiated your preparation sprint.\n\n"
                f"1. **Created Priority Task**: [{created_task.get('id')}] *{created_task.get('title')}* (Due: {created_task.get('due_date')}, Priority: {created_task.get('priority').upper()}).\n"
                f"2. **Generated Daily Schedule**: Planned {len(plan_data.get('schedule', []))} focused sessions totaling {plan_data.get('total_planned_minutes')} minutes within your available {hours}h window.\n\n"
                f"Would you like me to adjust any time allocations or schedule reminders?"
            )

            return AgentResponse(
                response_text=resp_text,
                intent="clarification_resolved",
                tool_calls=tool_records,
                model_mode="mock_development",
                conversation_id=session.session_id,
                active_task_id=created_task.get("id"),
            )

        # -------------------------------------------------------------
        # 3. Intent: Clarification Trigger — High level "Prepare for interview"
        # -------------------------------------------------------------
        if any(phrase in text_lower for phrase in [
            "prepare for my technical interview",
            "help me prepare for interview",
            "interview prep",
            "technical interview preparation"
        ]) and not ("day" in text_lower and "hour" in text_lower):
            session.pending_clarification = ClarificationState(
                goal="technical_interview_prep",
                missing_fields=["days_until_interview", "daily_available_hours", "focus_domain"],
            )
            return AgentResponse(
                response_text=(
                    "I'd love to help you prepare for your technical interview! To structure an effective plan for you, "
                    "could you please share:\n\n"
                    "1. **Timeline**: How many days do you have until the interview?\n"
                    "2. **Daily Commitment**: How much time can you dedicate each day (e.g. 1 hour, 2 hours)?\n"
                    "3. **Focus Area**: What specific role or technologies will the interview emphasize (e.g., Python, System Design, AWS)?"
                ),
                intent="request_clarification",
                missing_info=["timeline", "daily_hours", "focus_domain"],
                model_mode="mock_development",
                conversation_id=session.session_id,
            )

        # -------------------------------------------------------------
        # 4. Intent: List Pending / All Tasks
        # -------------------------------------------------------------
        if any(phrase in text_lower for phrase in [
            "show me my pending tasks",
            "show pending tasks",
            "list pending tasks",
            "what are my pending tasks",
            "pending tasks",
            "show my tasks",
            "list tasks",
            "show tasks",
            "my tasks"
        ]):
            status_filter = "pending" if "pending" in text_lower else None
            record = tool_registry.execute("list_tasks", {"status": status_filter, "limit": 10})
            tool_records.append(record)
            
            res = record.result or {}
            tasks = res.get("tasks", [])
            total = res.get("total_count", 0)

            if not tasks:
                resp_text = "You currently have no pending tasks! Great job staying on top of your workload."
            else:
                resp_text = f"You have **{total}** {'pending ' if status_filter else ''}task(s) in your system:\n\n"
                for t in tasks:
                    p_badge = t['priority'].upper()
                    status_badge = t['status'].replace('_', ' ').capitalize()
                    due_info = f" | Due: {t['due_date']}" if t.get('due_date') else ""
                    resp_text += f"- **[{t['id']}] {t['title']}** — *{p_badge}* priority ({status_badge}{due_info})\n"
                
                resp_text += "\nLet me know if you would like to update, prioritize, or complete any of these."
                # Set last referenced task to the first pending task
                session.last_referenced_task_id = tasks[0]["id"]

            return AgentResponse(
                response_text=resp_text,
                intent="list_tasks",
                tool_calls=tool_records,
                model_mode="mock_development",
                conversation_id=session.session_id,
                active_task_id=session.last_referenced_task_id,
            )

        # -------------------------------------------------------------
        # 5. Intent: Priority Update / Modification (Follow-up Reference)
        # e.g., "Make my Python preparation task high priority", "Change its priority to high"
        # -------------------------------------------------------------
        priority_keywords = {
            "urgent": PriorityEnum.URGENT,
            "high": PriorityEnum.HIGH,
            "medium": PriorityEnum.MEDIUM,
            "low": PriorityEnum.LOW,
        }
        found_priority = None
        for p_name, p_enum in priority_keywords.items():
            if f"{p_name} priority" in text_lower or f"priority to {p_name}" in text_lower:
                found_priority = p_enum
                break

        if found_priority or ("priority" in text_lower and any(w in text_lower for w in ["change", "make", "set", "update"])):
            all_tasks = task_store.all()
            target_id = session.resolve_task_reference(text, all_tasks)

            if not target_id:
                # If priority was specified but target unclear
                return AgentResponse(
                    response_text="Which task would you like me to update? Please provide the task ID or name.",
                    intent="ambiguous_reference",
                    model_mode="mock_development",
                    conversation_id=session.session_id,
                )

            update_args: Dict[str, Any] = {"task_id": target_id}
            if found_priority:
                update_args["priority"] = found_priority.value
            else:
                update_args["priority"] = "high"

            record = tool_registry.execute("update_task", update_args)
            tool_records.append(record)
            session.update_task_context_from_record(record)

            if record.success:
                t = record.result.get("task", {})
                resp_text = (
                    f"Successfully updated task **{t.get('id')}** ('{t.get('title')}').\n"
                    f"Priority is now set to **{t.get('priority').upper()}**."
                )
            else:
                resp_text = f"Failed to update task: {record.error}"

            return AgentResponse(
                response_text=resp_text,
                intent="update_task_priority",
                tool_calls=tool_records,
                model_mode="mock_development",
                conversation_id=session.session_id,
                active_task_id=target_id,
            )

        # -------------------------------------------------------------
        # 6. Intent: Move / Reschedule Task Date
        # e.g. "Move that task to tomorrow", "Reschedule it to Friday"
        # -------------------------------------------------------------
        if any(w in text_lower for w in ["move that task", "move it", "reschedule", "change due date"]):
            all_tasks = task_store.all()
            target_id = session.resolve_task_reference(text, all_tasks)

            new_date = "tomorrow"
            if "tomorrow" in text_lower:
                new_date = (date.today() + timedelta(days=1)).isoformat()
            elif "friday" in text_lower:
                new_date = "2026-10-24"

            if target_id:
                record = tool_registry.execute("update_task", {"task_id": target_id, "due_date": new_date})
                tool_records.append(record)
                session.update_task_context_from_record(record)

                t = record.result.get("task", {}) if record.success else {}
                resp_text = f"Rescheduled task **{target_id}** ('{t.get('title')}') to **{new_date}**."
                return AgentResponse(
                    response_text=resp_text,
                    intent="update_task_date",
                    tool_calls=tool_records,
                    model_mode="mock_development",
                    conversation_id=session.session_id,
                    active_task_id=target_id,
                )

        # -------------------------------------------------------------
        # 7. Intent: Complete Task
        # e.g., "Complete task TSK-101", "Mark that task complete", "I finished the Python task"
        # -------------------------------------------------------------
        if any(w in text_lower for w in ["complete task", "mark as complete", "mark completed", "complete it", "finished task", "finished the"]):
            all_tasks = task_store.all()
            target_id = session.resolve_task_reference(text, all_tasks)

            record = tool_registry.execute("complete_task", {"task_id": target_id} if target_id else {"title": text})
            tool_records.append(record)
            session.update_task_context_from_record(record)

            if record.success:
                t = record.result.get("task", {})
                resp_text = f"Great work! Task **{t.get('id')}** ('{t.get('title')}') has been marked as **COMPLETED**."
            else:
                resp_text = f"Could not complete task: {record.error}"

            return AgentResponse(
                response_text=resp_text,
                intent="complete_task",
                tool_calls=tool_records,
                model_mode="mock_development",
                conversation_id=session.session_id,
                active_task_id=target_id,
            )

        # -------------------------------------------------------------
        # 8. Intent: Delete Task (Safety Confirmation Check)
        # -------------------------------------------------------------
        if any(w in text_lower for w in ["delete task", "remove task", "delete it"]):
            all_tasks = task_store.all()
            target_id = session.resolve_task_reference(text, all_tasks)

            if not target_id:
                return AgentResponse(
                    response_text="Which task would you like to delete? Please specify the task ID.",
                    intent="delete_task_unspecified",
                    model_mode="mock_development",
                    conversation_id=session.session_id,
                )

            task = task_store.get(target_id)
            task_title = task.title if task else target_id

            # Set confirmation state
            session.pending_confirmation = ConfirmationState(
                action="delete",
                target_id=target_id,
                target_title=task_title,
            )

            return AgentResponse(
                response_text=(
                    f"⚠️ **Confirmation Required**: You are about to permanently delete task **{target_id}** "
                    f"('{task_title}'). This action cannot be undone.\n\n"
                    f"Are you sure you want to proceed? (Reply **Yes** to confirm or **No** to cancel)."
                ),
                intent="delete_task_confirmation",
                requires_confirmation=True,
                confirmation_prompt=f"Confirm deletion of {target_id}?",
                model_mode="mock_development",
                conversation_id=session.session_id,
                active_task_id=target_id,
            )

        # -------------------------------------------------------------
        # 9. Intent: Create Daily Plan / "Plan my day" / "Make the plan shorter"
        # -------------------------------------------------------------
        if any(w in text_lower for w in ["plan my day", "daily plan", "generate study plan", "create a plan", "make the plan shorter"]):
            hours = 4.0
            if "shorter" in text_lower:
                hours = 2.0
            elif "2 hour" in text_lower or "two hour" in text_lower:
                hours = 2.0
            elif "3 hour" in text_lower or "three hour" in text_lower:
                hours = 3.0
            elif "1 hour" in text_lower or "one hour" in text_lower:
                hours = 1.0

            focus = "Interview" if "interview" in text_lower or "study" in text_lower else None

            record = tool_registry.execute("create_daily_plan", {"available_hours": hours, "focus_area": focus})
            tool_records.append(record)
            session.update_task_context_from_record(record)

            plan = record.result.get("plan", {})
            sched = plan.get("schedule", [])

            resp_text = f"### Daily Schedule for {plan.get('date')} ({hours} Hours Allocated)\n\n"
            if sched:
                for item in sched:
                    resp_text += f"- **{item['time_slot']}**: [{item.get('task_id', 'TASK')}] {item['task_title']} ({item['duration_minutes']}m)\n"
            else:
                resp_text += "No pending tasks fit into this timeframe.\n"

            if plan.get("unplanned_tasks"):
                resp_text += f"\n*Remaining backlog*: {len(plan['unplanned_tasks'])} task(s) saved for next session."

            return AgentResponse(
                response_text=resp_text,
                intent="create_daily_plan",
                tool_calls=tool_records,
                model_mode="mock_development",
                conversation_id=session.session_id,
            )

        # -------------------------------------------------------------
        # 10. Intent: Productivity Summary / Overview
        # -------------------------------------------------------------
        if any(w in text_lower for w in ["productivity summary", "show summary", "productivity", "completion rate", "how am i doing", "stats"]):
            record = tool_registry.execute("get_productivity_summary", {"timeframe": "all"})
            tool_records.append(record)

            summary = record.result.get("summary", {})
            resp_text = (
                f"### Productivity Intelligence Summary\n\n"
                f"- **Total Tasks**: {summary.get('total_tasks')}\n"
                f"- **Completed**: {summary.get('completed_tasks')} ({summary.get('completion_rate_percent')}% completion rate)\n"
                f"- **In Progress**: {summary.get('in_progress_tasks')}\n"
                f"- **Pending**: {summary.get('pending_tasks')}\n"
                f"- **Priority Breakdown**: Urgent: {summary.get('priority_breakdown', {}).get('urgent', 0)}, "
                f"High: {summary.get('priority_breakdown', {}).get('high', 0)}, "
                f"Medium: {summary.get('priority_breakdown', {}).get('medium', 0)}, "
                f"Low: {summary.get('priority_breakdown', {}).get('low', 0)}\n\n"
                f"**Insights**:\n"
            )
            for ins in summary.get("insights", []):
                resp_text += f"- {ins}\n"

            return AgentResponse(
                response_text=resp_text,
                intent="get_productivity_summary",
                tool_calls=tool_records,
                model_mode="mock_development",
                conversation_id=session.session_id,
            )

        # -------------------------------------------------------------
        # 11. Intent: Retrieve Specific Task ("Show me the task we created earlier")
        # -------------------------------------------------------------
        if any(w in text_lower for w in ["show me the task", "get task", "view task", "task we created earlier", "task we made"]):
            all_tasks = task_store.all()
            target_id = session.resolve_task_reference(text, all_tasks)
            if not target_id and session.last_created_task_id:
                target_id = session.last_created_task_id

            if target_id:
                record = tool_registry.execute("get_task", {"task_id": target_id})
                tool_records.append(record)
                session.update_task_context_from_record(record)

                if record.success:
                    t = record.result.get("task", {})
                    resp_text = (
                        f"### Task Details: {t.get('id')}\n"
                        f"- **Title**: {t.get('title')}\n"
                        f"- **Description**: {t.get('description') or 'None'}\n"
                        f"- **Priority**: {t.get('priority').upper()}\n"
                        f"- **Status**: {t.get('status').replace('_', ' ').capitalize()}\n"
                        f"- **Due Date**: {t.get('due_date') or 'Not specified'}\n"
                        f"- **Estimated Duration**: {t.get('estimated_minutes')} minutes"
                    )
                    return AgentResponse(
                        response_text=resp_text,
                        intent="get_task",
                        tool_calls=tool_records,
                        model_mode="mock_development",
                        conversation_id=session.session_id,
                        active_task_id=target_id,
                    )

        # -------------------------------------------------------------
        # 12. Intent: Create Task
        # e.g. "Create a task for Python practice", "Add task: Review AWS IAM"
        # -------------------------------------------------------------
        if any(w in text_lower for w in ["create a task", "create task", "add task", "new task"]):
            title = text
            for prefix in ["create a task for", "create a task to", "create a task:", "create task:", "create task", "add task:", "add task", "new task:"]:
                if prefix in text_lower:
                    idx = text_lower.find(prefix) + len(prefix)
                    title = text[idx:].strip(" :.-")
                    break

            priority = "medium"
            if "urgent" in text_lower:
                priority = "urgent"
            elif "high" in text_lower:
                priority = "high"
            elif "low" in text_lower:
                priority = "low"

            record = tool_registry.execute("create_task", {
                "title": title or "New Productivity Task",
                "priority": priority,
                "due_date": (date.today() + timedelta(days=1)).isoformat(),
                "estimated_minutes": 45,
            })
            tool_records.append(record)
            session.update_task_context_from_record(record)

            t = record.result.get("task", {})
            resp_text = (
                f"Created task **{t.get('id')}**: *{t.get('title')}* with **{t.get('priority').upper()}** priority.\n"
                f"Due date set to {t.get('due_date')} (45 mins estimated)."
            )
            return AgentResponse(
                response_text=resp_text,
                intent="create_task",
                tool_calls=tool_records,
                model_mode="mock_development",
                conversation_id=session.session_id,
                active_task_id=t.get("id"),
            )

        # -------------------------------------------------------------
        # Default / General Assistant Response
        # -------------------------------------------------------------
        resp_text = (
            f"I'm your **Alexa+ AI Intelligent Personal Assistant**. I can help you plan your day, "
            f"manage technical preparation, prioritize tasks, and analyze your productivity.\n\n"
            f"Here are a few things you can ask me:\n"
            f"- *'Help me prepare for my technical interview.'*\n"
            f"- *'Show me my pending tasks.'*\n"
            f"- *'Plan my day for 4 hours.'*\n"
            f"- *'Make my Python preparation task high priority.'*\n"
            f"- *'Show productivity summary.'*"
        )
        return AgentResponse(
            response_text=resp_text,
            intent="general_conversation",
            tool_calls=[],
            model_mode="mock_development",
            conversation_id=session.session_id,
        )
