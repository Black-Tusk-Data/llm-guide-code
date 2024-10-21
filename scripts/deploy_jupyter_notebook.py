#!/usr/bin/env python3

import argparse
import os
from uuid import uuid4
import subprocess
import time
from threading import Thread


parser = argparse.ArgumentParser()
parser.add_argument("--pem-file", required=True)

AWS_PROFILE = os.environ.get("AWS_PROFILE")
AWS_REGION = os.environ.get("AWS_REGION")
STACK_NAME = "llm-book-jupyter"

AWS_CMD_FLAGS = [
    *(
        ["--profile", AWS_PROFILE] if AWS_PROFILE
            else []
    ),
    *(
        ["--region", AWS_REGION] if AWS_REGION
            else []
    ),
]


def open_jupyter_in_browser(
        token: str,
        delay: int
):
    time.sleep(delay)
    subprocess.check_call(["open", f"http://localhost:8888?token={token}"])
    return


def main():
    args = parser.parse_args()
    template = "llm-book-jupyter.template.yaml"
    token = str(uuid4())
    print("token:", token)
    deploy_cmd = [
        "aws", *AWS_CMD_FLAGS,
        "cloudformation", "deploy",
        "--capabilities", "CAPABILITY_NAMED_IAM",
        "--stack-name", STACK_NAME,
        "--template-file", template,
        "--parameter-overrides", f"NotebookToken={token}"
    ]
    print(" ".join(deploy_cmd))
    subprocess.check_call(deploy_cmd)

    cmd = [
        "aws", *AWS_CMD_FLAGS,
        "cloudformation", "describe-stacks",
        "--stack-name", STACK_NAME,
        "--query", "Stacks[0].Outputs[?OutputKey==`PublicIp`].OutputValue",
        "--output", "text",
    ]
    print(" ".join(cmd))
    ip = subprocess.check_output(cmd).strip().decode("utf-8")
    print("ip:", ip)

    thread = Thread(target=open_jupyter_in_browser, args=(
        token,
        5,
    ))
    thread.start()

    subprocess.check_call([
        "ssh", "-L", "8888:localhost:8888",
        f"ubuntu@{ip}",
        "-i", args.pem_file,
    ])
    return


if __name__ == '__main__':
    main()
