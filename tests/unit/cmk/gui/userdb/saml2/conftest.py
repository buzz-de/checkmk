#!/usr/bin/env python3
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

from collections.abc import Mapping
from typing import Any

import pytest


@pytest.fixture(name="raw_config")
def fixture_raw_config() -> Mapping[str, Any]:
    return {
        "type": "saml2",
        "version": "1.0.0",
        "id": "uuid123",
        "name": "härbärt",
        "owned_by_site": "NO_SITE",
        "description": "",
        "comment": "",
        "docu_url": "",
        "disabled": False,
        "checkmk_entity_id": "http://localhost/heute/check_mk/saml_metadata.py",
        "checkmk_metadata_endpoint": "http://localhost/heute/check_mk/saml_metadata.py?RelayState=uuid123",
        "checkmk_assertion_consumer_service_endpoint": "http://localhost/heute/check_mk/saml_acs.py?acs",
        "connection_timeout": (12, 12),
        "checkmk_server_url": "http://localhost",
        "idp_metadata": ("url", "http://localhost:8080/simplesaml/saml2/idp/metadata.php"),
        "user_id": "username",
        "alias": "",
        "email": "",
        "contactgroups": "",
        "role_membership_mapping": False,
        "signature_certificate": "default",
    }
