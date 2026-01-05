#!/usr/bin/env python3

# Docker SDK
# https://docker-py.readthedocs.io/en/4.1.0
import docker
import requests
import re
import subprocess

from colorama import Fore as Color, Style, init as colorama_init


# Config
YOUTRACK_CONTAINER_NAME = 'youtrack'
DOCKER_COMPOSE_FILE_NAME = 'docker-compose.yml'


class YoutrackUpdater:
    """ Main class to manage updating process"""

    YOUTRACK_TAGS_URL = "https://hub.docker.com/v2/repositories/jetbrains/youtrack/tags"

    def __init__(self, docker_compose_updater):
        try:
            # DockerComposeUpdater instance
            self.docker_compose_updater = docker_compose_updater

            # docker client instance
            self.docker = docker.from_env()

            # representation of the current running container
            self.current_container = self.get_current_container(YOUTRACK_CONTAINER_NAME)

            # current Youtrack version
            self.current_tag = self.get_current_tag()
            current_tag_colored = f"{Color.WHITE}{Style.BRIGHT}{self.current_tag}"
            print(f"{Color.BLUE}{Style.BRIGHT}Current running Youtrack version: {current_tag_colored}")

            # the latest available tag of Youtrack
            self.latest_tag = self.get_latest_tag()
            latest_tag_colored = f"{Color.GREEN}{Style.BRIGHT}{self.latest_tag}"
            print(f"{Color.BLUE}{Style.BRIGHT}The latest available Youtrack version: {latest_tag_colored}")

            self.check_for_updates()
        except docker.errors.NotFound:
            container_name = f"{Color.YELLOW}{YOUTRACK_CONTAINER_NAME}"
            print(f"{Color.RED}Oops! Youtrack container is not running. Or incorrect container name: {container_name}")
            exit(1)
        except requests.exceptions.ConnectionError:
            print(f"{Color.RED}Oops! Docker service is unavailable.")
            exit(1)
        except IOError as e:
            print(f'{Color.RED}Oops! {str(e)}')
            exit(1)

    def get_current_container(self, current_youtrack_container_name):
        return self.docker.containers.get(current_youtrack_container_name)

    def get_latest_tag(self):
        all_tags = requests.get(self.YOUTRACK_TAGS_URL).json()
        return all_tags['results'][0]['name']

    def get_current_tag(self):
        return self.current_container.image.tags[0].split(':')[1]

    def check_for_updates(self):
        latest_tag_tuple, current_tag_tuple = self.version_to_tuple()

        print()
        if latest_tag_tuple <= current_tag_tuple:
            print(f"{Color.GREEN}{Style.BRIGHT}Current Youtrack version is up to date! Nothing to update :)")
            return

        print(f"{Color.GREEN}{Style.BRIGHT}Update is available!")
        if not self.confirm(f"{Style.BRIGHT}Update Youtrack [y/n]?"):
            print()
            print("Okay, not now...")
            exit(0)

        self.update()

    # get versions in tuple format for comparing
    def version_to_tuple(self) -> tuple:
        latest_tag_tuple = tuple(map(int, (self.latest_tag.split("."))))
        current_tag_tuple = tuple(map(int, (self.get_current_tag().split("."))))

        return latest_tag_tuple, current_tag_tuple

    @staticmethod
    def confirm(question: str):
        """
        Ask user to enter Y or N (case-insensitive).
        :return: True if the answer is Y.
        :rtype: bool
        """
        answer = ""
        while answer not in ["y", "n"]:
            answer = input(question + ' ').strip().lower()
        return answer == "y"

    def update(self):
        print()
        print("Updating is starting...")

        # update info about container
        self.current_container.reload()

        # stop running Youtrack container
        if self.current_container.status == 'running':
            self.current_container.stop(timeout=60)
            print(f"{Color.GREEN}Current Youtrack container has been stopped!")

        # remove current container
        self.current_container.remove()
        print(f"{Color.GREEN}Current Youtrack container has been removed!")

        # update an image tag in the docker-compose.yml config
        self.docker_compose_updater.update_tag(self.latest_tag)

        # run container in the background
        subprocess.run(['docker', 'compose', 'up', '-d'])

        # set a new docker container
        self.current_container = self.get_current_container(YOUTRACK_CONTAINER_NAME)

        while True:
            if self.current_container.status != 'running':
                continue

            container_logs = self.current_container.logs(stream=True)
            for log_line in container_logs:
                log_line = str(log_line)

                if 'wizard_token' not in log_line:
                    continue

                url = re.findall(r'\[([^;]*)]', log_line)[0]
                print(f"{Color.GREEN}To continue open Youtrack Configuration Wizard by URL: {Color.YELLOW}{url}")
                break
            break

        # remove previous image
        previous_image_name = f"jetbrains/youtrack:{self.current_tag}"
        self.docker.images.remove(previous_image_name)
        print(f"{Color.GREEN}Previous Youtrack image {Color.YELLOW}({previous_image_name}) {Color.GREEN}has been "
              f"removed!")


class DockerComposeUpdater:
    """ Class to manipulate docker-compose.yml file """

    def __init__(self, docker_compose_file_name: str):
        self.docker_compose_file_name = docker_compose_file_name

    def update_tag(self, new_tag):
        # read yml file
        with open(self.docker_compose_file_name) as original_file:
            docker_compose = original_file.read()

            # update the tag
            new_tag = f'jetbrains/youtrack:{new_tag}'
            docker_compose = re.sub(r'jetbrains/youtrack:\w.*', new_tag, docker_compose)

            # write updated content to the file back
            with open(self.docker_compose_file_name, 'w') as new_file:
                new_file.write(docker_compose)
                print(f"{Color.GREEN}{self.docker_compose_file_name} has been updated!")


def main():
    # init colorama module
    colorama_init(autoreset=True)

    docker_compose_updater = DockerComposeUpdater(DOCKER_COMPOSE_FILE_NAME)
    YoutrackUpdater(docker_compose_updater)


if __name__ == '__main__':
    main()
