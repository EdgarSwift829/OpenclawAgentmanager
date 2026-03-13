"""Tests for plan-based resource limits and web access control."""

import os
import unittest
from unittest.mock import patch

from mado.backend.safety.plan_limits import (
    PLANS,
    PlanConfig,
    PlanLimitError,
    _resolve_plan_from_license,
    get_active_plan,
    get_max_projects,
    get_plan_info,
)
from mado.backend.tools.web_tools import WebTools, is_web_access_enabled


class TestPlanDefinitions(unittest.TestCase):
    """Test plan tier definitions."""

    def test_all_plans_exist(self):
        self.assertEqual(set(PLANS.keys()), {"free", "pro", "team", "enterprise"})

    def test_free_plan_limits(self):
        p = PLANS["free"]
        self.assertEqual(p.max_projects, 3)
        self.assertEqual(p.max_agents_per_run, 4)
        self.assertEqual(p.max_iterations, 5)
        self.assertEqual(p.max_concurrent_runs, 1)
        self.assertFalse(p.web_access)

    def test_pro_plan_has_web_access(self):
        self.assertTrue(PLANS["pro"].web_access)

    def test_plan_projects_ascending(self):
        order = ["free", "pro", "team", "enterprise"]
        for i in range(len(order) - 1):
            self.assertLess(PLANS[order[i]].max_projects, PLANS[order[i + 1]].max_projects)

    def test_plan_config_frozen(self):
        with self.assertRaises(AttributeError):
            PLANS["free"].max_projects = 999


class TestLicenseKeyResolution(unittest.TestCase):
    """Test license key prefix resolution."""

    def test_pro_license(self):
        self.assertEqual(_resolve_plan_from_license("MADO-PRO-abc123"), "pro")

    def test_team_license(self):
        self.assertEqual(_resolve_plan_from_license("MADO-TEAM-xyz"), "team")

    def test_enterprise_license(self):
        self.assertEqual(_resolve_plan_from_license("MADO-ENT-000"), "enterprise")

    def test_invalid_license(self):
        self.assertIsNone(_resolve_plan_from_license("INVALID-KEY"))

    def test_empty_license(self):
        self.assertIsNone(_resolve_plan_from_license(""))


class TestGetActivePlan(unittest.TestCase):
    """Test active plan resolution from env vars."""

    @patch.dict(os.environ, {}, clear=True)
    def test_default_is_free(self):
        # Remove any MADO env vars
        os.environ.pop("MADO_PLAN", None)
        os.environ.pop("MADO_LICENSE_KEY", None)
        plan = get_active_plan()
        self.assertEqual(plan.name, "free")

    @patch.dict(os.environ, {"MADO_PLAN": "pro"})
    def test_env_plan_pro(self):
        os.environ.pop("MADO_LICENSE_KEY", None)
        plan = get_active_plan()
        self.assertEqual(plan.name, "pro")

    @patch.dict(os.environ, {"MADO_PLAN": "TEAM"})
    def test_env_plan_case_insensitive(self):
        os.environ.pop("MADO_LICENSE_KEY", None)
        plan = get_active_plan()
        self.assertEqual(plan.name, "team")

    @patch.dict(os.environ, {"MADO_PLAN": "unknown_plan"})
    def test_unknown_plan_defaults_to_free(self):
        os.environ.pop("MADO_LICENSE_KEY", None)
        plan = get_active_plan()
        self.assertEqual(plan.name, "free")

    @patch.dict(os.environ, {"MADO_LICENSE_KEY": "MADO-ENT-abc", "MADO_PLAN": "free"})
    def test_license_key_overrides_plan_env(self):
        plan = get_active_plan()
        self.assertEqual(plan.name, "enterprise")

    @patch.dict(os.environ, {"MADO_LICENSE_KEY": "INVALID", "MADO_PLAN": "pro"})
    def test_invalid_license_falls_back_to_plan_env(self):
        plan = get_active_plan()
        self.assertEqual(plan.name, "pro")


class TestGetMaxProjects(unittest.TestCase):
    """Test max project count with overrides."""

    @patch.dict(os.environ, {"MADO_PLAN": "free"}, clear=False)
    def test_default_from_plan(self):
        os.environ.pop("MADO_MAX_PROJECTS", None)
        os.environ.pop("MADO_LICENSE_KEY", None)
        self.assertEqual(get_max_projects(), 3)

    @patch.dict(os.environ, {"MADO_MAX_PROJECTS": "50", "MADO_PLAN": "free"})
    def test_override_env_var(self):
        os.environ.pop("MADO_LICENSE_KEY", None)
        self.assertEqual(get_max_projects(), 50)

    @patch.dict(os.environ, {"MADO_MAX_PROJECTS": "0", "MADO_PLAN": "free"})
    def test_zero_override_ignored(self):
        os.environ.pop("MADO_LICENSE_KEY", None)
        self.assertEqual(get_max_projects(), 3)

    @patch.dict(os.environ, {"MADO_MAX_PROJECTS": "abc", "MADO_PLAN": "free"})
    def test_invalid_override_ignored(self):
        os.environ.pop("MADO_LICENSE_KEY", None)
        self.assertEqual(get_max_projects(), 3)


class TestGetPlanInfo(unittest.TestCase):
    """Test plan info API response format."""

    @patch.dict(os.environ, {"MADO_PLAN": "pro"})
    def test_plan_info_structure(self):
        os.environ.pop("MADO_LICENSE_KEY", None)
        os.environ.pop("MADO_MAX_PROJECTS", None)
        info = get_plan_info()
        self.assertEqual(info["plan"], "pro")
        self.assertEqual(info["display_name"], "Pro")
        self.assertIn("limits", info)
        self.assertEqual(info["limits"]["max_projects"], 20)
        self.assertEqual(info["limits"]["max_agents_per_run"], 9)


class TestPlanLimitError(unittest.TestCase):
    """Test PlanLimitError exception."""

    def test_error_message(self):
        err = PlanLimitError("projects", 3, 3, "free")
        self.assertIn("projects", str(err))
        self.assertIn("3/3", str(err))
        self.assertIn("free", str(err))

    def test_error_attributes(self):
        err = PlanLimitError("projects", 5, 10, "pro")
        self.assertEqual(err.resource, "projects")
        self.assertEqual(err.current, 5)
        self.assertEqual(err.limit, 10)
        self.assertEqual(err.plan, "pro")


class TestWebAccessToggle(unittest.TestCase):
    """Test web access enable/disable."""

    @patch.dict(os.environ, {"MADO_WEB_ACCESS": "true"})
    def test_web_access_enabled_by_default(self):
        self.assertTrue(is_web_access_enabled())

    @patch.dict(os.environ, {"MADO_WEB_ACCESS": "false"})
    def test_web_access_disabled_env(self):
        self.assertFalse(is_web_access_enabled())

    @patch.dict(os.environ, {"MADO_WEB_ACCESS": "0"})
    def test_web_access_disabled_zero(self):
        self.assertFalse(is_web_access_enabled())

    @patch.dict(os.environ, {"MADO_WEB_ACCESS": "no"})
    def test_web_access_disabled_no(self):
        self.assertFalse(is_web_access_enabled())

    @patch.dict(os.environ, {"MADO_WEB_ACCESS": "true"})
    def test_webtools_respects_instance_flag(self):
        wt = WebTools(web_access=False)
        self.assertFalse(wt._web_access)

    @patch.dict(os.environ, {"MADO_WEB_ACCESS": "false"})
    def test_webtools_env_overrides_instance(self):
        wt = WebTools(web_access=True)
        self.assertFalse(wt._web_access)

    @patch.dict(os.environ, {"MADO_WEB_ACCESS": "true"})
    def test_search_returns_error_when_disabled(self):
        wt = WebTools(web_access=False)
        result = wt.search_web("test query")
        self.assertEqual(len(result), 1)
        self.assertIn("error", result[0])
        self.assertIn("disabled", result[0]["error"])

    @patch.dict(os.environ, {"MADO_WEB_ACCESS": "true"})
    def test_fetch_raises_when_disabled(self):
        wt = WebTools(web_access=False)
        with self.assertRaises(PermissionError):
            wt.fetch_url("http://example.com")


if __name__ == "__main__":
    unittest.main()
