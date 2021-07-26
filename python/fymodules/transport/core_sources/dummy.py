
import collections

from spdm.numlib import np
from spdm.numlib import constants
from fytok.transport.CoreProfiles import CoreProfiles
from fytok.transport.CoreSources import CoreSources
from fytok.transport.Equilibrium import Equilibrium
from spdm.data.Function import Function
from spdm.data.Node import Dict, List, Node
from spdm.util.logger import logger


class CoreSourceDummy(CoreSources.Source):
    def __init__(self, d=None, *args,  **kwargs):

        super().__init__(collections.ChainMap({
            "identifier": {"name": "unspecified", "index": 5,
                           "description": f"{self.__class__.__name__} Dummy CoreTransport.Model "},
            "code": {"name": "dummy"}}, d or {}),
            *args, **kwargs)

    def refresh(self, *args,  **kwargs):
        super().refresh(*args, **kwargs)


__SP_EXPORT__ = CoreSourceDummy