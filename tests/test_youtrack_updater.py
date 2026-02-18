import subprocess
from unittest.mock import patch, MagicMock, call

import pytest
import requests

from youtrack_updater import YoutrackUpdater


SAMPLE_COMPOSE = """\
services:
  youtrack:
    image: jetbrains/youtrack:2025.1.12345
    restart: unless-stopped
"""

SAMPLE_COMPOSE_NO_IMAGE = """\
services:
  postgres:
    image: postgres:16
"""


@pytest.fixture
def compose_file(tmp_path):
    f = tmp_path / "docker-compose.yml"
    f.write_text(SAMPLE_COMPOSE)
    return str(f)


@pytest.fixture
def updater(compose_file):
    with patch.object(YoutrackUpdater, "__init__", lambda self, *a: None):
        u = YoutrackUpdater.__new__(YoutrackUpdater)
        u.compose_file = compose_file
        u.current_tag = "2025.1.12345"
        u.latest_tag = "2025.3.99999"
        return u


# --- get_current_tag ---

def test_get_current_tag(updater):
    assert updater.get_current_tag() == "2025.1.12345"


def test_get_current_tag_missing_image(updater, tmp_path):
    f = tmp_path / "docker-compose.yml"
    f.write_text(SAMPLE_COMPOSE_NO_IMAGE)
    updater.compose_file = str(f)

    with pytest.raises(ValueError, match="No jetbrains/youtrack image found"):
        updater.get_current_tag()


# --- get_latest_tag ---

def mock_dockerhub_response(tags, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "results": [{"name": t} for t in tags]
    }
    if status_code >= 400:
        response.raise_for_status.side_effect = requests.HTTPError()
    return response


def test_get_latest_tag_picks_highest(updater):
    tags = ["2025.2.119894", "2025.3.121962", "2025.1.50000", "latest"]
    with patch("youtrack_updater.requests.get", return_value=mock_dockerhub_response(tags)):
        assert updater.get_latest_tag() == "2025.3.121962"


def test_get_latest_tag_ignores_invalid(updater):
    tags = ["latest", "nightly", "2025.1.100"]
    with patch("youtrack_updater.requests.get", return_value=mock_dockerhub_response(tags)):
        assert updater.get_latest_tag() == "2025.1.100"


def test_get_latest_tag_no_valid_tags(updater):
    tags = ["latest", "nightly", "edge"]
    with patch("youtrack_updater.requests.get", return_value=mock_dockerhub_response(tags)):
        with pytest.raises(ValueError, match="No valid version tags found"):
            updater.get_latest_tag()


def test_get_latest_tag_http_error(updater):
    with patch("youtrack_updater.requests.get", return_value=mock_dockerhub_response([], status_code=500)):
        with pytest.raises(requests.HTTPError):
            updater.get_latest_tag()


# --- check_for_updates ---

def test_check_for_updates_up_to_date(updater, capsys):
    updater.latest_tag = "2025.1.12345"
    updater.current_tag = "2025.1.12345"

    updater.check_for_updates()

    assert "up to date" in capsys.readouterr().out.lower()


def test_check_for_updates_user_declines(updater):
    with patch("builtins.input", return_value="n"):
        with pytest.raises(SystemExit) as exc_info:
            updater.check_for_updates()
        assert exc_info.value.code == 0


def test_check_for_updates_user_confirms(updater):
    with patch("builtins.input", return_value="y"), \
         patch.object(updater, "update") as mock_update:
        updater.check_for_updates()
        mock_update.assert_called_once()


# --- update_compose_tag ---

def test_update_compose_tag(updater, compose_file):
    updater.update_compose_tag("2025.3.99999")

    with open(compose_file) as f:
        content = f.read()

    assert "jetbrains/youtrack:2025.3.99999" in content
    assert "jetbrains/youtrack:2025.1.12345" not in content


# --- update (sequence) ---

def test_update_sequence(updater):
    with patch("youtrack_updater.subprocess.run") as mock_run, \
         patch.object(updater, "compose_run") as mock_compose, \
         patch.object(updater, "update_compose_tag") as mock_tag, \
         patch.object(updater, "watch_logs"):

        mock_run.return_value = MagicMock(returncode=0)

        updater.update()

        mock_run.assert_any_call(
            ["docker", "pull", "jetbrains/youtrack:2025.3.99999"],
            check=True,
        )
        mock_compose.assert_any_call("down")
        mock_tag.assert_called_once_with("2025.3.99999")
        mock_compose.assert_any_call("up", "-d")

        calls = mock_compose.call_args_list
        down_idx = next(i for i, c in enumerate(calls) if c == call("down"))
        up_idx = next(i for i, c in enumerate(calls) if c == call("up", "-d"))
        assert down_idx < up_idx


def test_update_rmi_failure(updater, capsys):
    with patch("youtrack_updater.subprocess.run") as mock_run, \
         patch.object(updater, "compose_run"), \
         patch.object(updater, "update_compose_tag"), \
         patch.object(updater, "watch_logs"):

        def run_side_effect(*args, **kwargs):
            result = MagicMock()
            if args[0][0:2] == ["docker", "rmi"]:
                result.returncode = 1
            else:
                result.returncode = 0
            return result

        mock_run.side_effect = run_side_effect

        updater.update()

        output = capsys.readouterr().out
        assert "could not remove" in output.lower()


# --- watch_logs ---

def test_watch_logs_finds_wizard_token(updater, capsys):
    mock_process = MagicMock()
    mock_process.stdout = iter([
        "some startup log\n",
        "another line\n",
        "wizard_token found [https://youtrack.example.com/?wizard_token=abc123]\n",
    ])

    with patch("youtrack_updater.subprocess.Popen", return_value=mock_process):
        updater.watch_logs()

    output = capsys.readouterr().out
    assert "https://youtrack.example.com/?wizard_token=abc123" in output
    mock_process.terminate.assert_called_once()


def test_watch_logs_timeout(updater, capsys):
    mock_process = MagicMock()

    def slow_lines():
        yield "starting up\n"
        yield "still loading\n"
        yield "not done yet\n"

    mock_process.stdout = slow_lines()

    call_count = 0

    def mock_monotonic():
        nonlocal call_count
        call_count += 1
        if call_count <= 1:
            return 0.0
        return 999.0

    with patch("youtrack_updater.subprocess.Popen", return_value=mock_process), \
         patch("youtrack_updater.time.monotonic", side_effect=mock_monotonic), \
         patch("youtrack_updater.start_spinner", return_value=MagicMock()), \
         patch("youtrack_updater.stop_spinner"):
        updater.watch_logs(timeout=60)

    output = capsys.readouterr().out
    assert "timed out" in output.lower()
    mock_process.terminate.assert_called_once()
