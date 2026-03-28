from __future__ import annotations

import argparse

from ai_content_agent.benchmarks.datasets import SUPPORTED_BENCHMARK_AGENTS
from ai_content_agent.benchmarks.runner import run_benchmarks


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AI content agent benchmarks.")
    parser.add_argument(
        "--agent",
        action="append",
        choices=SUPPORTED_BENCHMARK_AGENTS,
        help="Benchmark only the specified agent. Repeat for multiple agents.",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Regenerate the Markdown report from the latest scored benchmark artifact.",
    )
    args = parser.parse_args()
    run_benchmarks(agent_keys=args.agent, report_only=args.report_only)


if __name__ == "__main__":
    main()
