"""PatchPilot Typer CLI interface with rich visual output."""

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from patchpilot import __version__
from patchpilot.agent.orchestrator import AgentOrchestrator
from patchpilot.config import PatchPilotConfig
from patchpilot.evaluation.benchmark import run_smoke_benchmark
from patchpilot.ollama_client import OllamaClient
from patchpilot.schemas import RepairStatus, TaskRequest, TestSuiteName
from patchpilot.storage.run_store import RunStore
from patchpilot.verification.runner import TestRunner

app = typer.Typer(
    name="patchpilot",
    help="Local-first self-healing AI coding agent powered by Ollama.",
    no_args_is_help=True,
)
runs_app = typer.Typer(help="Inspect past repair runs and artifacts.", no_args_is_help=True)
app.add_typer(runs_app, name="runs")

console = Console()


@app.callback()
def main() -> None:
    """PatchPilot CLI."""


@app.command(name="version")
def version_cmd() -> None:
    """Show the PatchPilot version."""
    console.print(f"[bold cyan]PatchPilot[/bold cyan] version [green]{__version__}[/green]")


@app.command(name="doctor")
def doctor_cmd(
    config_file: Path | None = typer.Option(
        None, "--config", "-c", help="Path to custom .toml configuration file"
    ),
    probe_tools: bool = typer.Option(
        False, "--probe-tools", help="Send a test prompt to probe model native tool-calling"
    ),
) -> None:
    """Check system health, dependencies, Ollama connectivity, and sandbox readiness."""
    console.print(
        Panel.fit("[bold blue]PatchPilot System Diagnostics[/bold blue]", border_style="blue")
    )
    table = Table(title="Diagnostic Checks", show_header=True, header_style="bold magenta")
    table.add_column("Component", style="dim", width=24)
    table.add_column("Status", width=14)
    table.add_column("Details")

    # 1. Python version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 11)
    table.add_row(
        "Python Runtime",
        "[green]PASS[/green]" if py_ok else "[red]FAIL[/red]",
        f"Python {py_ver} ({sys.executable})",
    )

    # 2. Config loading
    cfg = None
    try:
        cfg = PatchPilotConfig.load(config_file)
        table.add_row(
            "Configuration",
            "[green]PASS[/green]",
            f"Model: {cfg.model_name} | Endpoint: {cfg.ollama_base_url}",
        )
    except Exception as e:
        table.add_row("Configuration", "[red]FAIL[/red]", str(e))
        console.print(table)
        raise typer.Exit(code=1) from None

    # 3. Ollama connectivity
    client = OllamaClient(cfg)
    ollama_ok = client.is_reachable()
    table.add_row(
        "Ollama Server",
        "[green]ONLINE[/green]" if ollama_ok else "[yellow]UNAVAILABLE[/yellow]",
        f"Endpoint: {cfg.ollama_base_url}"
        if ollama_ok
        else f"Cannot reach {cfg.ollama_base_url}. Ensure Ollama is running.",
    )

    # 4. Target Model Installed
    model_ok = False
    if ollama_ok:
        try:
            model_ok = client.is_model_installed(cfg.model_name)
            table.add_row(
                "Model Availability",
                "[green]INSTALLED[/green]" if model_ok else "[yellow]MISSING[/yellow]",
                f"Model '{cfg.model_name}' is available"
                if model_ok
                else f"Model '{cfg.model_name}' not installed. Run: ollama pull {cfg.model_name}",
            )
        except Exception as e:
            table.add_row("Model Availability", "[red]ERROR[/red]", str(e))
    else:
        table.add_row("Model Availability", "[dim]SKIPPED[/dim]", "Ollama is offline")

    # 5. Tool-calling capability probe (optional)
    if probe_tools and ollama_ok and model_ok:
        with console.status("Probing model tool-calling capability..."):
            cap_ok, cap_msg = client.check_tool_capability()
            table.add_row(
                "Tool-Calling Probe",
                "[green]SUPPORTED[/green]" if cap_ok else "[yellow]LIMITED[/yellow]",
                cap_msg,
            )

    # 6. Docker Sandbox
    runner = TestRunner(cfg)
    docker_ok = runner.is_docker_available()
    table.add_row(
        "Docker CLI / Daemon",
        "[green]AVAILABLE[/green]" if docker_ok else "[yellow]UNAVAILABLE[/yellow]",
        "Docker daemon reachable"
        if docker_ok
        else "Docker not running. Sandboxed testing unavailable.",
    )

    image_ok = runner.is_sandbox_image_available() if docker_ok else False
    table.add_row(
        "Sandbox Image",
        "[green]READY[/green]" if image_ok else "[yellow]NOT BUILT[/yellow]",
        f"Image '{runner.docker_image}' found"
        if image_ok
        else f"Build with: docker build -t {runner.docker_image} sandbox/",
    )

    # 7. Data Storage Directory
    try:
        cfg.data_dir.mkdir(parents=True, exist_ok=True)
        test_file = cfg.data_dir / ".write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
        table.add_row("Data Directory", "[green]WRITABLE[/green]", str(cfg.data_dir.resolve()))
    except Exception as e:
        table.add_row("Data Directory", "[red]FAIL[/red]", f"Cannot write to {cfg.data_dir}: {e}")

    console.print(table)


@app.command(name="models")
def models_cmd(
    config_file: Path | None = typer.Option(None, "--config", "-c", help="Config file path"),
) -> None:
    """List installed models in local Ollama."""
    cfg = PatchPilotConfig.load(config_file)
    client = OllamaClient(cfg)
    if not client.is_reachable():
        console.print(f"[red]Error:[/red] Ollama is not running at {cfg.ollama_base_url}")
        raise typer.Exit(code=1)

    try:
        models = client.list_models()
        table = Table(title="Installed Ollama Models", show_header=True)
        table.add_column("Model Name", style="bold cyan")
        table.add_column("Status")

        for m in sorted(models):
            is_target = m == cfg.model_name or m.split(":")[0] == cfg.model_name.split(":")[0]
            status_text = "[green]Configured Model[/green]" if is_target else "[dim]Available[/dim]"
            table.add_row(m, status_text)

        console.print(table)
    except Exception as e:
        console.print(f"[red]Failed to query models:[/red] {e}")
        raise typer.Exit(code=1) from None


@app.command(name="chat")
def chat_cmd(
    prompt: str = typer.Argument(..., help="Prompt string to send to local model"),
    config_file: Path | None = typer.Option(None, "--config", "-c", help="Config file path"),
) -> None:
    """Perform direct diagnostic request to the configured local model."""
    cfg = PatchPilotConfig.load(config_file)
    client = OllamaClient(cfg)
    with console.status(f"Querying {cfg.model_name}..."):
        try:
            resp = client.chat(messages=[{"role": "user", "content": prompt}])
            content = resp.get("message", {}).get("content", "")
            console.print(Panel(content, title=f"Model: {cfg.model_name}", border_style="cyan"))
        except Exception as e:
            console.print(f"[red]Chat request failed:[/red] {e}")
            raise typer.Exit(code=1) from None


@app.command(name="repair")
def repair_cmd(
    repo: Path = typer.Option(..., "--repo", "-r", help="Path to target source repository"),
    task: str = typer.Option(..., "--task", "-t", help="Description of the bug to resolve"),
    suite: TestSuiteName = typer.Option(
        TestSuiteName.PYTEST, "--test-suite", "-s", help="Predefined test suite to execute"
    ),
    target: str | None = typer.Option(
        None, "--test-target", help="Optional targeted test file or directory"
    ),
    allow_host_execution: bool = typer.Option(
        False, "--allow-host-execution", help="Unsafely execute tests on the host without Docker"
    ),
    config_file: Path | None = typer.Option(None, "--config", "-c", help="Config file path"),
) -> None:
    """Execute isolated self-healing repair pipeline on a repository."""
    cfg = PatchPilotConfig.load(config_file)
    if allow_host_execution:
        cfg.allow_host_execution = True
        console.print("[yellow bold]WARNING: Unsafe host execution mode enabled.[/yellow bold]")

    task_request = TaskRequest(
        repo_path=str(repo),
        task_description=task,
        test_suite=suite,
        test_target=target,
    )

    console.print(
        Panel(
            f"[bold]Target Repository:[/bold] {repo.resolve()}\n"
            f"[bold]Task:[/bold] {task}\n"
            f"[bold]Test Suite:[/bold] {suite.value}"
            + (f" ({target})" if target else "")
            + f"\n[bold]Model:[/bold] {cfg.model_name}\n"
            f"[bold]Safety:[/bold] Original repository will NOT be modified.",
            title="[bold green]PatchPilot Repair Mission[/bold green]",
            border_style="green",
        )
    )

    orchestrator = AgentOrchestrator(cfg)

    with console.status("[bold green]Executing isolated repair workflow...[/bold green]"):
        try:
            report = orchestrator.run_repair(task_request)
        except Exception as e:
            console.print(f"[bold red]Repair failed with exception:[/bold red] {e}")
            raise typer.Exit(code=1) from None

    # Display results
    status_style = {
        RepairStatus.FIXED: "bold green",
        RepairStatus.PARTIALLY_FIXED: "bold yellow",
        RepairStatus.UNRESOLVED: "bold red",
        RepairStatus.FAILED_SAFETY_CHECK: "bold red reverse",
        RepairStatus.CANCELLED: "dim",
    }.get(report.status, "white")

    console.print(f"\n[bold]Run ID:[/bold] {report.run_id}")
    console.print(
        f"[bold]Final Status:[/bold] [{status_style}]{report.status.value}[/{status_style}]"
    )
    console.print(
        f"[bold]Duration:[/bold] {report.duration_seconds:.2f}s | [bold]Attempts:[/bold] {report.attempts_made}/{report.max_attempts}"
    )
    console.print(
        f"[bold]Original Repository Untouched:[/bold] [{'green' if report.original_repo_unmodified else 'red'}]{report.original_repo_unmodified}[/]"
    )

    if report.patch and report.patch.unified_diff:
        console.print("\n[bold]Generated Unified Diff:[/bold]")
        console.print(Syntax(report.patch.unified_diff, "diff", theme="monokai", line_numbers=True))

    if report.status == RepairStatus.FIXED:
        console.print(
            "\n[bold green]✔ Patch successfully verified against test suite without regressions.[/bold green]"
        )
    elif report.status == RepairStatus.FAILED_SAFETY_CHECK:
        console.print("\n[bold red]✖ RUN FAILED SAFETY CHECKS.[/bold red]")
        for violation in report.safety_violations:
            console.print(f"  - [red]{violation}[/red]")
        raise typer.Exit(code=2)
    else:
        console.print(f"\n[yellow]Repair concluded with status: {report.status.value}[/yellow]")
        if report.error_message:
            console.print(f"[red]Failure Reason:[/red] {report.error_message}")
        raise typer.Exit(code=1)


@runs_app.command(name="list")
def runs_list_cmd(
    config_file: Path | None = typer.Option(None, "--config", "-c", help="Config file path"),
) -> None:
    """List recent repair runs."""
    cfg = PatchPilotConfig.load(config_file)
    store = RunStore(cfg.data_dir)
    runs = store.list_runs()

    if not runs:
        console.print("[dim]No repair runs recorded in data directory.[/dim]")
        return

    table = Table(title="PatchPilot Repair History", show_header=True)
    table.add_column("Run ID", style="bold cyan")
    table.add_column("Status")
    table.add_column("Duration")
    table.add_column("Attempts")
    table.add_column("Task")

    for r in runs:
        status_color = (
            "green" if r["status"] == "FIXED" else "red" if "FAIL" in r["status"] else "yellow"
        )
        table.add_row(
            r["run_id"],
            f"[{status_color}]{r['status']}[/{status_color}]",
            f"{r['duration_seconds']:.1f}s",
            str(r["attempts"]),
            r["task"],
        )
    console.print(table)


@runs_app.command(name="show")
def runs_show_cmd(
    run_id: str = typer.Argument(..., help="Run ID to inspect"),
    config_file: Path | None = typer.Option(None, "--config", "-c", help="Config file path"),
) -> None:
    """Display detailed report and diff for a specific run."""
    cfg = PatchPilotConfig.load(config_file)
    store = RunStore(cfg.data_dir)
    report = store.get_run(run_id)

    if not report:
        console.print(f"[red]Error:[/red] Run '{run_id}' not found.")
        raise typer.Exit(code=1)

    console.print(
        Panel(
            f"[bold]Run ID:[/bold] {report.run_id}\n[bold]Status:[/bold] {report.status.value}\n[bold]Duration:[/bold] {report.duration_seconds:.2f}s",
            title="Run Details",
            border_style="cyan",
        )
    )

    if report.patch and report.patch.unified_diff:
        console.print("\n[bold]Unified Diff:[/bold]")
        console.print(Syntax(report.patch.unified_diff, "diff", theme="monokai", line_numbers=True))
    else:
        console.print("[dim]No file modifications in this run.[/dim]")


@app.command(name="eval")
def eval_cmd(
    suite: str = typer.Option("smoke", "--suite", "-s", help="Benchmark suite to run (smoke)"),
    config_file: Path | None = typer.Option(None, "--config", "-c", help="Config file path"),
) -> None:
    """Run deterministic benchmark evaluation cases."""
    cfg = PatchPilotConfig.load(config_file)
    console.print(f"[bold cyan]Running PatchPilot benchmark suite:[/bold cyan] {suite}")

    with console.status("Evaluating benchmark cases..."):
        eval_report = run_smoke_benchmark(cfg)

    table = Table(title="Benchmark Results", show_header=True)
    table.add_column("Case ID", style="bold")
    table.add_column("Status")
    table.add_column("Duration")
    table.add_column("Attempts")
    table.add_column("Tools Called")

    for res in eval_report.results:
        color = "green" if res.success else "red"
        table.add_row(
            res.case_id,
            f"[{color}]{res.status.value}[/{color}]",
            f"{res.duration_seconds:.2f}s",
            str(res.attempts),
            str(res.tool_calls_count),
        )

    console.print(table)
    console.print(
        f"\n[bold]Summary:[/bold] {eval_report.passed_cases}/{eval_report.total_cases} passed "
        f"({eval_report.success_rate * 100:.1f}%) in {eval_report.total_duration_seconds:.2f}s"
    )

    if eval_report.failed_cases > 0:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
