import subprocess


def test_no_pending_migrations():
    result = subprocess.run(["make", "migrations"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "No changes detected" in result.stdout
