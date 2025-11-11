#!/usr/bin/env python3
"""
List EC2 instances in us-east-1 by assuming a cross-account role.

Usage:
  python list_instances.py --role-arn arn:aws:iam::123456789012:role/CrossAccountEc2ListInstancesRole
  python list_instances.py --role-arn ... --external-id my-external-id
"""

import argparse
import sys
from typing import Optional, Dict, Any, List

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def assume_role(role_arn: str, external_id: Optional[str]) -> Dict[str, str]:
    sts = boto3.client("sts")
    params: Dict[str, Any] = {
        "RoleArn": role_arn,
        "RoleSessionName": "ec2-list-session"
    }
    if external_id:
        params["ExternalId"] = external_id
    try:
        resp = sts.assume_role(**params)
        creds = resp["Credentials"]
        return {
            "aws_access_key_id": creds["AccessKeyId"],
            "aws_secret_access_key": creds["SecretAccessKey"],
            "aws_session_token": creds["SessionToken"],
        }
    except (ClientError, BotoCoreError) as e:
        print(f"[ERROR] Failed to assume role: {e}", file=sys.stderr)
        sys.exit(2)


def get_name_tag(tags: Optional[List[Dict[str, str]]]) -> Optional[str]:
    if not tags:
        return None
    for t in tags:
        if t.get("Key") == "Name":
            return t.get("Value")
    return None


def list_instances_sorted(creds: Dict[str, str], region: str = "us-east-1"):
    ec2 = boto3.client("ec2", region_name=region, **creds)

    instances = []
    try:
        paginator = ec2.get_paginator("describe_instances")
        for page in paginator.paginate():
            for reservation in page.get("Reservations", []):
                for inst in reservation.get("Instances", []):
                    instances.append(inst)
    except (ClientError, BotoCoreError) as e:
        print(f"[ERROR] Failed to describe instances: {e}", file=sys.stderr)
        sys.exit(3)

    # Sort by creation date (LaunchTime)
    instances.sort(key=lambda i: i.get("LaunchTime"))

    if not instances:
        print("(no instances found)")
        return

    for inst in instances:
        iid = inst.get("InstanceId")
        name = get_name_tag(inst.get("Tags"))
        launch = inst.get("LaunchTime")
        state = (inst.get("State") or {}).get("Name")
        name_display = name if name else "(no Name tag)"
        print(f"{launch}  {iid}  {state}  {name_display}")


def main():
    parser = argparse.ArgumentParser(description="Assume role and list EC2 instances in us-east-1")
    parser.add_argument("--role-arn", required=True, help="Role ARN to assume")
    parser.add_argument("--external-id", default=None, help="External ID if the trust policy requires it")
    parser.add_argument("--region", default="us-east-1", help="AWS region (default: us-east-1)")
    args = parser.parse_args()

    creds = assume_role(args.role_arn, args.external_id)
    list_instances_sorted(creds, region=args.region)


if __name__ == "__main__":
    main()
