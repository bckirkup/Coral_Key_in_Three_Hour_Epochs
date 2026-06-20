"""Tests for coral_key.runner (domain-runner integration)."""

from __future__ import annotations

import pytest
from domain_runner.layer import DomainOnlyLayer
from domain_runner.single import run_simulation
from domain_runner.types import RunContext

from coral_key.runner import CoralDomainHooks, run_coral_simulation


@pytest.mark.integration
class TestCoralRunner:
    def test_domain_only_simulation(self) -> None:
        run = RunContext(
            steps=3,
            seed=7,
            domain_config={"total_epochs": 3, "seed": 7},
            layer="domain_only",
        )
        result = run_simulation(CoralDomainHooks(), DomainOnlyLayer(), run)
        assert result.steps_completed == 3
        assert "biomass_relative_to_bmsy" in result.domain_metrics

    @pytest.mark.smoke
    def test_run_coral_simulation_entry(self) -> None:
        hooks = CoralDomainHooks()
        run = hooks.load_run_context(
            cli_overrides={"domain": {"total_epochs": 5}, "layer": "domain_only"}
        )
        result = run_coral_simulation(run)
        assert result.domain == "coral_key"
