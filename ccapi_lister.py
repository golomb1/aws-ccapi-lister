"""Utility for discovering AWS resources via the Cloud Control API.

This module exposes a small command line application that enumerates every
instance of a CloudFormation resource type by using
``cloudcontrol.list_resources`` followed by ``cloudcontrol.get_resource`` to
retrieve the complete property bag for each resource.

Some CloudFormation resource types require additional context for
``list_resources``.  For example, ``AWS::Lambda::Url`` expects the ARN of the
owning function in the ``ResourceModel`` payload.  The collector implemented in
this file contains a light‑weight dependency system that is able to discover
such context automatically by first enumerating the prerequisite resource type
and then synthesising the appropriate ``ResourceModel`` payload for the
dependent call.

The resulting script can be executed as ``python ccapi_lister.py
AWS::S3::Bucket`` or with multiple type names at once.  Results are written to
STDOUT in JSON format by default.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
)

import boto3
from botocore.exceptions import ClientError


LOGGER = logging.getLogger(__name__)


@dataclass
class ResourceRecord:
    """Represents a single resource fetched from Cloud Control."""

    type_name: str
    identifier: str
    properties: Mapping[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type_name": self.type_name,
            "identifier": self.identifier,
            "properties": self.properties,
        }


@dataclass
class DependencyDefinition:
    """Describes how to derive ``ResourceModel`` payloads for a dependent type.

    Attributes
    ----------
    source_type:
        The CloudFormation type that should be enumerated to provide context for
        the dependent resource type.
    build_models:
        A callable that receives the :class:`ResourceRecord` of the source type
        and yields one or more ``ResourceModel`` dictionaries that should be
        supplied to ``list_resources`` for the dependent type.
    description:
        Human readable description used in logging.
    """

    source_type: str
    build_models: Callable[[ResourceRecord], Iterable[Mapping[str, Any]]]
    description: str


class CloudControlCollector:
    """Collects CloudFormation resource instances through Cloud Control."""

    def __init__(
        self,
        session: boto3.session.Session,
        region_name: Optional[str] = None,
        dependency_map: Optional[Mapping[str, DependencyDefinition]] = None,
    ) -> None:
        self._session = session
        self._client = session.client("cloudcontrol", region_name=region_name)
        self._dependency_map = dependency_map or {}
        self._cache: MutableMapping[str, List[ResourceRecord]] = {}

    # ------------------------------------------------------------------
    def collect(self, type_name: str) -> List[ResourceRecord]:
        """Return all resources of ``type_name``.

        The method caches results for previously fetched types so that dependent
        lookups do not repeatedly query the Cloud Control API.
        """

        if type_name in self._cache:
            return self._cache[type_name]

        try:
            resources = list(self._collect_via_list_resources(type_name, None))
        except ClientError as error:
            dependency = self._dependency_map.get(type_name)
            if dependency is None or not self._is_dependency_error(error):
                raise

            LOGGER.debug(
                "ListResources for %s requires context, resolving dependency on %s (%s)",
                type_name,
                dependency.source_type,
                dependency.description,
            )
            resources = self._collect_with_dependency(type_name, dependency)

        self._cache[type_name] = resources
        return resources

    # ------------------------------------------------------------------
    def _collect_with_dependency(
        self, type_name: str, dependency: DependencyDefinition
    ) -> List[ResourceRecord]:
        context_resources = self.collect(dependency.source_type)
        if not context_resources:
            LOGGER.warning(
                "No resources of type %s were discovered to satisfy dependency for %s",
                dependency.source_type,
                type_name,
            )
            return []

        aggregated: Dict[str, ResourceRecord] = {}
        for context in context_resources:
            models: Sequence[Mapping[str, Any]] = list(dependency.build_models(context))
            for model in models:
                LOGGER.debug(
                    "Listing %s resources using dependency model %s", type_name, model
                )
                try:
                    for record in self._collect_via_list_resources(type_name, model):
                        aggregated[record.identifier] = record
                except ClientError as error:
                    LOGGER.error(
                        "Failed to list %s using dependency model %s: %s",
                        type_name,
                        model,
                        error,
                        exc_info=True,
                    )
        return list(aggregated.values())

    # ------------------------------------------------------------------
    def _collect_via_list_resources(
        self, type_name: str, resource_model: Optional[Mapping[str, Any]]
    ) -> Iterable[ResourceRecord]:
        base_params: Dict[str, Any] = {"TypeName": type_name}
        if resource_model:
            base_params["ResourceModel"] = json.dumps(resource_model)

        next_token: Optional[str] = None
        while True:
            request_params = dict(base_params)
            if next_token is not None:
                request_params["NextToken"] = next_token
            LOGGER.debug("Calling list_resources with params: %s", request_params)
            response = self._client.list_resources(**request_params)
            for description in response.get("ResourceDescriptions", []):
                identifier = description["Identifier"]
                try:
                    yield self._fetch_resource(type_name, identifier)
                except ClientError as error:
                    LOGGER.error(
                        "Failed to fetch %s resource %s: %s",
                        type_name,
                        identifier,
                        error,
                        exc_info=True,
                    )

            next_token = response.get("NextToken")
            if not next_token:
                break

    # ------------------------------------------------------------------
    def _fetch_resource(self, type_name: str, identifier: str) -> ResourceRecord:
        LOGGER.debug("Fetching resource %s %s", type_name, identifier)
        response = self._client.get_resource(TypeName=type_name, Identifier=identifier)
        resource_description = response.get("ResourceDescription", {})
        properties_raw = resource_description.get("Properties", "{}")
        try:
            properties = json.loads(properties_raw)
        except json.JSONDecodeError:
            LOGGER.warning(
                "Unable to decode properties for %s %s – returning raw string", type_name, identifier
            )
            properties = {"_raw": properties_raw}

        return ResourceRecord(type_name=type_name, identifier=identifier, properties=properties)

    # ------------------------------------------------------------------
    @staticmethod
    def _is_dependency_error(error: ClientError) -> bool:
        error_code = error.response.get("Error", {}).get("Code")
        message = error.response.get("Error", {}).get("Message", "")
        return error_code in {"ValidationException", "ResourceNotFoundException"} or "ResourceModel" in message


def _lambda_url_dependency(context: ResourceRecord) -> Iterable[Mapping[str, Any]]:
    function_arn = (
        context.properties.get("FunctionArn")
        or context.properties.get("Arn")
        or context.identifier
    )
    if not function_arn:
        return []
    return [{"TargetFunctionArn": function_arn}]


def _ecs_service_dependency(context: ResourceRecord) -> Iterable[Mapping[str, Any]]:
    cluster_identifier = (
        context.properties.get("ClusterArn")
        or context.properties.get("Arn")
        or context.identifier
    )
    if not cluster_identifier:
        return []
    return [{"Cluster": cluster_identifier}]


def _eks_fargate_dependency(context: ResourceRecord) -> Iterable[Mapping[str, Any]]:
    cluster_name = context.properties.get("Name") or context.properties.get("ClusterName")
    if not cluster_name:
        return []
    return [{"ClusterName": cluster_name}]


DEPENDENCIES: Mapping[str, DependencyDefinition] = {
    "AWS::Lambda::Url": DependencyDefinition(
        source_type="AWS::Lambda::Function",
        build_models=_lambda_url_dependency,
        description="Function ARN required for Lambda URLs",
    ),
    "AWS::ECS::Service": DependencyDefinition(
        source_type="AWS::ECS::Cluster",
        build_models=_ecs_service_dependency,
        description="Cluster identifier required to enumerate ECS services",
    ),
    "AWS::EKS::FargateProfile": DependencyDefinition(
        source_type="AWS::EKS::Cluster",
        build_models=_eks_fargate_dependency,
        description="Cluster name required to enumerate EKS Fargate profiles",
    ),
}


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Enumerate AWS resources for the provided CloudFormation type names "
            "using the Cloud Control API."
        )
    )
    parser.add_argument(
        "type_names",
        nargs="+",
        help="One or more CloudFormation type names (for example AWS::S3::Bucket)",
    )
    parser.add_argument(
        "--region",
        dest="region_name",
        default=None,
        help="AWS region to use (defaults to the active boto3 configuration)",
    )
    parser.add_argument(
        "--profile",
        dest="profile_name",
        default=None,
        help="Named AWS CLI profile to use",
    )
    parser.add_argument(
        "--output",
        choices=["json", "text"],
        default="json",
        help="Output format for the collected resources",
    )
    parser.add_argument(
        "--log-level",
        dest="log_level",
        default="INFO",
        help="Logging level (default: INFO)",
    )
    return parser


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    configure_logging(args.log_level)

    session_kwargs: Dict[str, Any] = {}
    if args.profile_name:
        session_kwargs["profile_name"] = args.profile_name

    session = boto3.Session(**session_kwargs)
    collector = CloudControlCollector(
        session=session,
        region_name=args.region_name,
        dependency_map=DEPENDENCIES,
    )

    results: Dict[str, List[Dict[str, Any]]] = {}
    for type_name in args.type_names:
        LOGGER.info("Collecting resources for %s", type_name)
        try:
            records = collector.collect(type_name)
        except ClientError as error:
            LOGGER.error("Failed to collect %s: %s", type_name, error, exc_info=True)
            continue

        results[type_name] = [record.to_dict() for record in records]

    if args.output == "json":
        json.dump(results, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        for type_name, records in results.items():
            print(f"Resource type: {type_name}")
            for record in records:
                print(f"  Identifier: {record['identifier']}")
                print("  Properties:")
                for key, value in sorted(record["properties"].items()):
                    print(f"    {key}: {value}")
            print()


if __name__ == "__main__":
    main()

