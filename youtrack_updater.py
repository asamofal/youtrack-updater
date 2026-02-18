#!/usr/bin/env python3

import argparse
import itertools
import os
import re
import subprocess
import sys
import threading
import time
from importlib.metadata import version

import requests
from colorama import Fore as Color, Style, init as colorama_init
from packaging.version import Version, InvalidVersion

__version__ = version("youtrack-updater")

DEFAULT_COMPOSE_FILE = "docker-compose.yml"


def log(emoji, message, color=Color.GREEN):
    print(f"{emoji} {color}{message}")


SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


def start_spinner(message, stop_event):
    def spin():
        for frame in itertools.cycle(SPINNER_FRAMES):
            if stop_event.is_set():
                break
            print(f"\r{frame} {Color.GREEN}{message}", end="", flush=True)
            time.sleep(0.1)

    spinner_thread = threading.Thread(target=spin)
    spinner_thread.start()
    return spinner_thread


def stop_spinner(spinner_thread, stop_event):
    stop_event.set()
    spinner_thread.join()


def run_with_spinner(loading_msg, done_msg, fail_msg, fn):
    stop_event = threading.Event()
    spinner_thread = start_spinner(loading_msg, stop_event)
    try:
        result = fn()
    except Exception:
        stop_spinner(spinner_thread, stop_event)
        print(f"\r❌ {Color.RED}{fail_msg}\033[K")
        raise

    stop_spinner(spinner_thread, stop_event)
    print(f"\r✅ {Color.GREEN}{done_msg}\033[K")
    return result


class YoutrackUpdater:
    YOUTRACK_TAGS_URL = "https://hub.docker.com/v2/repositories/jetbrains/youtrack/tags"
    IMAGE_PATTERN = r'jetbrains/youtrack:([\w.]+)'

    def __init__(self, compose_file):
        self.compose_file = compose_file

        if not os.path.isfile(self.compose_file):
            log("❌", f"Compose file not found: {self.compose_file}", Color.RED)
            sys.exit(1)

        try:
            self.current_tag = self.get_current_tag()
            log("📦", f"Current version: {Color.WHITE}{Style.BRIGHT}{self.current_tag}", Color.BLUE)

            self.latest_tag = self.get_latest_tag()
            log("🌐", f"Latest version: {Color.GREEN}{Style.BRIGHT}{self.latest_tag}", Color.BLUE)

            self.check_for_updates()
        except requests.RequestException as e:
            log("❌", f"Failed to check Docker Hub: {e}", Color.RED)
            sys.exit(1)
        except ValueError as e:
            log("❌", str(e), Color.RED)
            sys.exit(1)

    def get_current_tag(self):
        with open(self.compose_file) as f:
            match = re.search(self.IMAGE_PATTERN, f.read())
            if not match:
                raise ValueError(f"No jetbrains/youtrack image found in {self.compose_file}")
            return match.group(1)

    def get_latest_tag(self):
        response = requests.get(self.YOUTRACK_TAGS_URL, params={"page_size": 100})
        response.raise_for_status()

        data = response.json()

        highest = None
        for result in data['results']:
            try:
                v = Version(result['name'])
            except InvalidVersion:
                continue
            if highest is None or v > highest[0]:
                highest = (v, result['name'])

        if not highest:
            raise ValueError("No valid version tags found on Docker Hub")

        return highest[1]

    def check_for_updates(self):
        print()
        if Version(self.latest_tag) <= Version(self.current_tag):
            log("✅", "Already up to date")
            return

        log("→", "Update available!")
        if not self.confirm(f"{Style.BRIGHT}Update Youtrack [y/n]?"):
            print()
            log("👋", "Okay, not now")
            sys.exit(0)

        self.update()

    @staticmethod
    def confirm(question: str):
        answer = ""
        while answer not in ["y", "n"]:
            answer = input(question + ' ').strip().lower()
        return answer == "y"

    def compose_run(self, *args):
        result = subprocess.run(
            ['docker', 'compose', '-f', self.compose_file, *args],
            check=True,
            capture_output=True,
        )
        return result

    def update(self):
        print()
        log("🚀", "Starting update...")
        print()

        subprocess.run(
            ['docker', 'pull', f'jetbrains/youtrack:{self.latest_tag}'],
            check=True,
        )
        print()
        log("✅", "New image pulled")

        run_with_spinner(
            "Stopping container...",
            "Container stopped and removed",
            "Failed to stop container",
            lambda: self.compose_run('down'),
        )

        run_with_spinner(
            "Updating compose file...",
            f"{self.compose_file} updated",
            f"Failed to update {self.compose_file}",
            lambda: self.update_compose_tag(self.latest_tag),
        )
        print()

        run_with_spinner(
            "Starting container...",
            "Container started",
            "Failed to start container",
            lambda: self.compose_run('up', '-d'),
        )

        self.watch_logs()

        old_image = f"jetbrains/youtrack:{self.current_tag}"
        result = subprocess.run(['docker', 'rmi', old_image], capture_output=True)
        if result.returncode == 0:
            log("🧹", f"Old image removed ({Color.YELLOW}{old_image}{Color.GREEN})")
        else:
            log("⚠️", f"Could not remove old image. Run manually: {Color.WHITE}docker rmi {old_image}", Color.YELLOW)

    def update_compose_tag(self, new_tag):
        with open(self.compose_file) as f:
            content = f.read()

        content = re.sub(self.IMAGE_PATTERN, f'jetbrains/youtrack:{new_tag}', content)

        with open(self.compose_file, 'w') as f:
            f.write(content)

    def watch_logs(self, timeout=60):
        stop_event = threading.Event()
        spinner_thread = start_spinner("Waiting for Configuration Wizard URL...", stop_event)

        process = subprocess.Popen(
            ['docker', 'compose', '-f', self.compose_file, 'logs', '-f'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        is_found = False
        deadline = time.monotonic() + timeout
        for line in process.stdout:
            if time.monotonic() > deadline:
                break
            if 'wizard_token' in line:
                url = re.findall(r'\[([^;]*)]', line)
                if url:
                    is_found = True
                    stop_spinner(spinner_thread, stop_event)
                    print(f"\r🔗 {Color.GREEN}Configuration Wizard: {Color.YELLOW}{url[0]}\033[K")
                    print()
                break

        process.terminate()
        if not is_found:
            stop_spinner(spinner_thread, stop_event)
            print(f"\r❌ {Color.YELLOW}Timed out waiting for Configuration Wizard URL\033[K")
            log("⚠️", f"Run: {Color.WHITE}docker compose -f {self.compose_file} logs -f", Color.YELLOW)


def main():
    parser = argparse.ArgumentParser(description="Auto-update JetBrains YouTrack Docker container")
    parser.add_argument("--compose-file", default=DEFAULT_COMPOSE_FILE,
                        help=f"Path to docker-compose.yml (default: {DEFAULT_COMPOSE_FILE})")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args()

    colorama_init(autoreset=True)

    try:
        YoutrackUpdater(args.compose_file)
    except KeyboardInterrupt:
        print("\r\033[K")
        log("👋", "Terminating...")
        sys.exit()


if __name__ == '__main__':
    main()
