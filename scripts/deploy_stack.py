#!/usr/bin/env python3

import argparse
import os
from pathlib import Path
import subprocess


parser = argparse.ArgumentParser()
parser.add_argument("template")

AWS_PROFILE = os.environ.get("AWS_PROFILE")
AWS_REGION = os.environ.get("AWS_REGION")


def main():
    args = parser.parse_args()
    template_path = Path(args.template)
    stack_name, *_ = template_path.parts[-1].split(".template.yaml")
    cmd = [
        "aws",
        *(
            ["--profile", AWS_PROFILE] if AWS_PROFILE
            else []
        ),
        *(
            ["--region", AWS_REGION] if AWS_REGION
            else []
        ),
        "cloudformation", "deploy",
        "--capabilities", "CAPABILITY_NAMED_IAM",
        "--stack-name", stack_name,
        "--template-file", args.template,
    ]
    print(" ".join(cmd))
    subprocess.check_call(cmd)
    return


if __name__ == "__main__":
    main()
