#!/usr/bin/env python3

import argparse
import os
import re
import subprocess
import sys

import requests
from colorama import Fore as Color, Style, init as colorama_init
from packaging.version import Version, InvalidVersion

__version__ = "1.0.0"

DEFAULT_COMPOSE_FILE = "docker-compose.yml"


class YoutrackUpdater:
    YOUTRACK_TAGS_URL = "https://hub.docker.com/v2/repositories/jetbrains/youtrack/tags"
    IMAGE_PATTERN = r'jetbrains/youtrack:([\w.]+)'

    def __init__(self, compose_file):
        self.compose_file = compose_file

        if not os.path.isfile(self.compose_file):
            print(f"{Color.RED}Compose file not found: {self.compose_file}")
            sys.exit(1)

        try:
            self.current_tag = self.get_current_tag()
            current_tag_colored = f"{Color.WHITE}{Style.BRIGHT}{self.current_tag}"
            print(f"{Color.BLUE}{Style.BRIGHT}Current running Youtrack version: {current_tag_colored}")

            self.latest_tag = self.get_latest_tag()
            latest_tag_colored = f"{Color.GREEN}{Style.BRIGHT}{self.latest_tag}"
            print(f"{Color.BLUE}{Style.BRIGHT}The latest available Youtrack version: {latest_tag_colored}")

            self.check_for_updates()
        except requests.RequestException as e:
            print(f"{Color.RED}Failed to check Docker Hub: {e}")
            sys.exit(1)
        except ValueError as e:
            print(f"{Color.RED}{e}")
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
            print(f"{Color.GREEN}{Style.BRIGHT}Current Youtrack version is up to date! Nothing to update :)")
            return

        print(f"{Color.GREEN}{Style.BRIGHT}Update is available!")
        if not self.confirm(f"{Style.BRIGHT}Update Youtrack [y/n]?"):
            print()
            print("Okay, not now...")
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
        )
        return result

    def update(self):
        print()
        print("Updating is starting...")

        subprocess.run(
            ['docker', 'pull', f'jetbrains/youtrack:{self.latest_tag}'],
            check=True,
        )
        print(f"{Color.GREEN}New image pulled!")

        self.compose_run('down')
        print(f"{Color.GREEN}Current Youtrack container has been stopped and removed!")

        self.update_compose_tag(self.latest_tag)

        self.compose_run('up', '-d')

        self.watch_logs()

        subprocess.run(['docker', 'rmi', f'jetbrains/youtrack:{self.current_tag}'])
        print(f"{Color.GREEN}Previous Youtrack image {Color.YELLOW}(jetbrains/youtrack:{self.current_tag}) "
              f"{Color.GREEN}has been removed!")

    def update_compose_tag(self, new_tag):
        with open(self.compose_file) as f:
            content = f.read()

        content = re.sub(self.IMAGE_PATTERN, f'jetbrains/youtrack:{new_tag}', content)

        with open(self.compose_file, 'w') as f:
            f.write(content)
        print(f"{Color.GREEN}{self.compose_file} has been updated!")

    def watch_logs(self):
        process = subprocess.Popen(
            ['docker', 'compose', '-f', self.compose_file, 'logs', '-f'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        for line in process.stdout:
            if 'wizard_token' in line:
                url = re.findall(r'\[([^;]*)]', line)
                if url:
                    print(f"{Color.GREEN}To continue open Youtrack Configuration Wizard by URL: {Color.YELLOW}{url[0]}")
                process.terminate()
                break


def main():
    parser = argparse.ArgumentParser(description="Auto-update JetBrains YouTrack Docker container")
    parser.add_argument("--compose-file", default=DEFAULT_COMPOSE_FILE,
                        help=f"Path to docker-compose.yml (default: {DEFAULT_COMPOSE_FILE})")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args()

    colorama_init(autoreset=True)
    YoutrackUpdater(args.compose_file)


if __name__ == '__main__':
    main()
