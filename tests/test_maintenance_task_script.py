from pathlib import Path


def test_maintenance_task_registration_uses_windowless_python_launcher():
    script = Path("scripts/register_codex_evidence_maintenance_task.ps1").read_text(
        encoding="utf-8"
    )

    assert 'scripts\\run_codex_evidence_maintenance_hidden.py' in script
    assert "Resolve-PythonwPath" in script
    assert "-Execute $PythonwPath" in script
    assert '-Execute "powershell.exe"' not in script
    assert '"-WindowStyle", "Hidden",' not in script
    assert script.index("--repo-root") < script.index("--codex-home")
    assert script.index("--codex-home") < script.index("--dev-root")
    assert "Quote-TaskArgument" in script
    assert '`"$ScriptPath`"' not in script


def test_maintenance_task_registration_marks_task_hidden():
    script = Path("scripts/register_codex_evidence_maintenance_task.ps1").read_text(
        encoding="utf-8"
    )

    settings_start = script.index("New-ScheduledTaskSettingsSet")
    principal_start = script.index("New-ScheduledTaskPrincipal")
    assert "-Hidden" in script[settings_start:principal_start]
    assert "Register-ScheduledTask" in script
    assert "-Force" in script


def test_maintenance_task_registration_uses_full_current_user_identity():
    script = Path("scripts/register_codex_evidence_maintenance_task.ps1").read_text(
        encoding="utf-8"
    )

    assert "[System.Security.Principal.WindowsIdentity]::GetCurrent().Name" in script
    assert "-UserId $userId" in script
    assert "-UserId $env:USERNAME" not in script


def test_maintenance_hidden_launcher_invokes_powershell_without_console_window():
    script = Path("scripts/run_codex_evidence_maintenance_hidden.py").read_text(
        encoding="utf-8"
    )

    assert "run_codex_evidence_maintenance.ps1" in script
    assert "powershell.exe" in script
    assert '"CREATE_NO_WINDOW"' in script
    assert "getattr(subprocess" in script
    assert "subprocess.run(" in script
    assert "maintenance-launcher.log" in script
    assert "--repo-root" in script
    assert "--codex-home" in script
    assert "--dev-root" in script


def test_maintenance_script_runs_housekeeping_after_dev_sweep():
    script = Path("scripts/run_codex_evidence_maintenance.ps1").read_text(
        encoding="utf-8"
    )

    assert "dev-sweep" in script
    assert " maintenance " in script
    assert script.index("dev-sweep") < script.index(" maintenance ")
    assert "--repo-root $RepoRoot" in script
    assert "--codex-home $CodexHome" in script
    assert "Assert-LastExitCode" in script
    assert 'Assert-LastExitCode "dev_sweep"' in script
    assert 'Assert-LastExitCode "maintenance"' in script
