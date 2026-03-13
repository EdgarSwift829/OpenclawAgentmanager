"""mutmut configuration for MADO backend mutation testing.

Focus mutation testing on critical security and logic modules:
- Safety: sandbox, file_tools, exec_tools
- Core: orchestrator, task_graph, workspace_manager
- API: input validation (projects._validate_safe_id)
"""


def pre_mutation(context):
    """Skip mutations in test files and non-critical modules."""
    # Only mutate backend source files
    if not context.filename.startswith("mado/backend/"):
        context.skip = True
        return

    # Skip __init__.py files
    if context.filename.endswith("__init__.py"):
        context.skip = True
        return

    # Focus on critical modules
    critical_paths = [
        "mado/backend/tools/file_tools.py",
        "mado/backend/tools/exec_tools.py",
        "mado/backend/safety/sandbox.py",
        "mado/backend/orchestrator/task_graph.py",
        "mado/backend/api/routes/projects.py",
        "mado/backend/agents/base_agent.py",
    ]

    if context.filename not in critical_paths:
        context.skip = True
