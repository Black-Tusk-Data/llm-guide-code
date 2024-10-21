#!/usr/bin/env python3

import os
import subprocess


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


def main():
    cmd = [
        "aws", *AWS_CMD_FLAGS,
        "cloudformation", "delete-stack",
        "--stack-name", STACK_NAME,
    ]
    print(" ".join(cmd))
    subprocess.check_call(cmd)
    return


if __name__ == '__main__':
    main()
