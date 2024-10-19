#!/usr/bin/env python3

from argparse import ArgumentParser
import base64
from datetime import datetime
from enum import StrEnum
import os
import time
from uuid import uuid4

from pydantic import BaseModel

from awscore import AwsServiceSession
from db import AWSDynamoCon


class WorkerType(StrEnum):
    jupyter = "jupyter"
    pass

parser = ArgumentParser()
parser.add_argument("worker_type", type=WorkerType)


TABLE_NAME = "cloud-computer-state"
cf_client = AwsServiceSession("cloudformation").service
apptable = AWSDynamoCon().connect_table(TABLE_NAME)

SUCCESS_STATUSES = set(
    [
        "CREATE_COMPLETE",
    ]
)
FAILED_STATUSES = set(
    [
        "CREATE_FAILED",
    ]
)
TIMEOUT_S = 60 * 15  # 15 might be more realistic
SLEEP_S = 10


class WorkerDetails(BaseModel):
    deploy_id: str
    stack_name: str
    ip_addr: str
    pass


def get_template():
    with open("template.worker.yaml", "r") as f:
        return f.read()
    pass


def delete_stack(stack_name: str):
    return cf_client.delete_stack(StackName=stack_name)


# apptable
def wait_for_app_startup(
    *,
    deploy_id: str,
    fail_ts: float,
):
    while True:
        status_record = apptable.get_item(
            {"PK": {"S": "DEPLOY_STATE"}, "SK": {"S": deploy_id}}
        )
        print("status:", status_record)
        if status_record and status_record.get("status", {}).get("S") == "online":
            return True
        if time.time() > fail_ts:
            raise Exception("timeout waiting for app startup")
        time.sleep(SLEEP_S)
        pass
    pass


def wait_for_deploy(
    *,
    stack_name: str,
    deploy_id: str,
) -> WorkerDetails:
    fail_ts = time.time() + TIMEOUT_S
    while True:
        stack_info = cf_client.describe_stacks(
            StackName=stack_name,
        )[
            "Stacks"
        ][0]
        status = stack_info["StackStatus"]
        print("status", status)
        if status in FAILED_STATUSES:
            print("failed to create stack", stack_name)
            cf_client.delete_stack(StackName=stack_name)
            raise Exception("failed to deploy")
        if status in SUCCESS_STATUSES:
            outputs = stack_info["Outputs"]
            ip_addr = next(
                (r["OutputValue"] for r in outputs if r["OutputKey"] == "PublicIp"),
                None,
            )
            apptable.put_item(
                {
                    "PK": {"S": "DEPLOY_STATE"},
                    "SK": {"S": deploy_id},
                    "status": {"S": "starting"},
                }
            )
            # wait_for_app_startup(
            #     deploy_id=deploy_id,
            #     fail_ts=fail_ts,
            # )
            return WorkerDetails(
                deploy_id=deploy_id,
                stack_name=stack_name,
                ip_addr=ip_addr or "",
            )
        if time.time() > fail_ts:
            raise Exception("timeout deploying stack")
        time.sleep(SLEEP_S)
    return


def deploy_new_worker(code_bundle: str) -> WorkerDetails:
    deploy_id = (
        base64.urlsafe_b64encode(uuid4().bytes)
        .decode("utf-8")
        .replace("=", "")
        .replace("_", "")
        .replace("-", "")
    )
    apptable.put_item(
        {
            "PK": {"S": "DEPLOY_STATE"},
            "SK": {"S": deploy_id},
            "status": {"S": "provisioning"},
            "created": {"S": datetime.now().isoformat()},
        }
    )

    stack_name = f"llm-worker-{deploy_id}"
    parameters = [
        {
            "ParameterKey": "DeployId",
            "ParameterValue": deploy_id,
        },
        {
            "ParameterKey": "CodeBundle",
            "ParameterValue": code_bundle,
        },
    ]
    print("launching stack", stack_name)
    cf_client.create_stack(
        StackName=stack_name,
        TemplateBody=get_template(),
        Parameters=parameters,
        Capabilities=["CAPABILITY_NAMED_IAM"],
    )
    try:
        return wait_for_deploy(
            stack_name=stack_name,
            deploy_id=deploy_id,
        )
    except Exception as e:
        print("deploy failed:", e)
        try:
            # cf_client.delete_stack(StackName=stack_name)
            # Note that it could still come online and overwrite this state...
            # TODO: Need an atomic get-and-set in the worker
            # TODO: also need a cleanup cron
            apptable.put_item(
                {
                    "PK": {"S": "DEPLOY_STATE"},
                    "SK": {"S": deploy_id},
                    "status": {"S": "dead"},
                }
            )
            pass
        except:
            pass
        raise e
    pass


def on_success(
        wtype: WorkerType,
        details: WorkerDetails
):
    if wtype == WorkerType.jupyter:
        print("conenct to host at", f"http://{details.ip}:8888?token=testpass")
        return
    return


def main():
    args = parser.parse_args()
    r = deploy_new_worker(args.worker_type)
    print(r)
    return


if __name__ == "__main__":
    main()
