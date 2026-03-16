from ..rules.base import Rule
from ..facts.models import RepoFacts


class RuleRegistry:
    def __init__(self):
        self._rules: list[Rule] = []

    def register(self, rule: Rule) -> None:
        self._rules.append(rule)

    def all(self) -> list[Rule]:
        return list(self._rules)

    def for_facts(self, facts: RepoFacts) -> list[Rule]:
        return [r for r in self._rules if r.applies(facts)]


def build_default_registry() -> RuleRegistry:
    from ..rules.common.readme_missing import ReadmeMissingRule
    from ..rules.common.license_missing import LicenseMissingRule
    from ..rules.common.ci_missing import CIMissingRule
    from ..rules.common.tests_missing import TestsMissingRule
    from ..rules.common.lockfile_missing import LockfileMissingRule
    from ..rules.common.env_example_missing import EnvExampleMissingRule
    from ..rules.common.large_files import LargeFilesRule
    from ..rules.common.formatter_missing import FormatterMissingRule
    from ..rules.common.linter_missing import LinterMissingRule
    from ..rules.common.tests_present_but_no_ci import TestsPresentButNoCIRule
    from ..rules.common.no_health_check import NoHealthCheckRule
    from ..rules.common.tests_low_ratio import TestsLowRatioRule
    from ..rules.common.no_test_ci_integration import NoTestCIIntegrationRule
    from ..rules.python.mypy_missing import MypyMissingRule
    from ..rules.python.pytest_missing import PytestMissingRule
    from ..rules.python.no_structured_logging import NoStructuredLoggingRule
    from ..rules.python.type_config_missing import TypeConfigMissingRule
    from ..rules.architecture.route_db_coupling import RouteDbCouplingRule
    from ..rules.architecture.entrypoint_concentration import EntrypointConcentrationRule
    from ..rules.architecture.gaming_signals import FacadeDetectionRule
    from ..rules.architecture.hollow_test_suite import HollowTestSuiteRule
    from ..rules.architecture.readme_without_substance import ReadmeWithoutSubstanceRule
    from ..rules.frameworks.fastapi.main_too_large import FastAPIMainTooLargeRule
    from ..rules.docker.dockerfile_root import DockerfileRootUserRule
    from ..rules.common.secret_scan_findings import SecretScanFindingsRule
    from ..rules.common.security_density import SecurityDensityRule
    from ..rules.common.lint_density import LintDensityRule
    from ..rules.common.bandit_grouped import BanditGroupedRule
    from ..rules.python.no_type_signal import NoTypeSignalRule

    registry = RuleRegistry()
    for cls in [
        ReadmeMissingRule, LicenseMissingRule, CIMissingRule,
        TestsMissingRule, LockfileMissingRule, EnvExampleMissingRule,
        LargeFilesRule, FormatterMissingRule, LinterMissingRule,
        TestsPresentButNoCIRule, NoHealthCheckRule,
        TestsLowRatioRule, NoTestCIIntegrationRule,
        MypyMissingRule, PytestMissingRule, TypeConfigMissingRule,
        RouteDbCouplingRule, EntrypointConcentrationRule,
        FacadeDetectionRule, HollowTestSuiteRule, ReadmeWithoutSubstanceRule,
        FastAPIMainTooLargeRule, DockerfileRootUserRule,
        SecretScanFindingsRule, SecurityDensityRule, LintDensityRule,
        BanditGroupedRule, NoTypeSignalRule, NoStructuredLoggingRule,
    ]:
        registry.register(cls())
    return registry
