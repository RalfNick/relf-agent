"""A fixed GET endpoint cannot hide the generated query in a bare delimiter."""

import asyncio

import pytest

from relf_agent import HTTPToolSource, RuntimeBuilder, RuntimeProfile, ToolDescriptor
from relf_agent.errors import ValidationError


@pytest.mark.parametrize("suffix", ["?", "#", "?#"])
def test_get_empty_query_or_fragment_is_rejected_before_resource_allocation(tmp_path, suffix):
    descriptor = ToolDescriptor("lookup", "Lookup", {"type": "object"})
    url = "http://127.0.0.1/fixed" + suffix
    with pytest.raises(ValidationError):
        HTTPToolSource(descriptor, url, version="1", method="GET")

    profile = RuntimeProfile(
        "bad-get-delimiter",
        "1",
        {},
        {
            "tools": {
                "adapter": "http-json",
                "config": {
                    "tools": [
                        {
                            "descriptor": descriptor.to_dict(),
                            "url": url,
                            "version": "1",
                            "method": "GET",
                            "policy": {
                                "version": "1",
                                "effect": "read_only",
                                "requires_approval": False,
                            },
                        }
                    ]
                },
            }
        },
    )

    async def run():
        with pytest.raises(ValidationError):
            await RuntimeBuilder().abuild(profile, tmp_path / "never-created.sqlite")

    asyncio.run(run())
    assert not (tmp_path / "never-created.sqlite").exists()
