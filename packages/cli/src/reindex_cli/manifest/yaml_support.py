from __future__ import annotations

import copy
import re

import yaml
from yaml.tokens import AliasToken, AnchorToken, DirectiveToken, TagToken

from reindex_cli.errors import ManifestError


class UniqueLoader(yaml.SafeLoader):
    pass


UniqueLoader.yaml_implicit_resolvers = copy.deepcopy(
    yaml.SafeLoader.yaml_implicit_resolvers
)
for first, resolvers in UniqueLoader.yaml_implicit_resolvers.items():
    UniqueLoader.yaml_implicit_resolvers[first] = [
        (tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:bool"
    ]
UniqueLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|false)$", re.IGNORECASE),
    list("tTfF"),
)


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ManifestError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_restricted_yaml(text: str, relative: str) -> object:
    try:
        if any(
            isinstance(token, (AliasToken, AnchorToken, DirectiveToken, TagToken))
            for token in yaml.scan(text)
        ):
            raise ManifestError(f"unsupported YAML feature: {relative}")
        return yaml.load(text, Loader=UniqueLoader)
    except yaml.YAMLError as error:
        raise ManifestError(f"invalid YAML: {relative}") from error
