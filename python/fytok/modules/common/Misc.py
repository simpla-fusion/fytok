
import collections
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import Union
import numpy as np
from spdm.data.Node import Dict

# VacuumToroidalField = collections.namedtuple("VacuumToroidalField", "r0 b0", defaults=(0.0, 0.0))
# Identifier = collections.namedtuple("Identifier", " ", defaults=("unamed", 0, ""))


@dataclass
class Identifier:
    name: str = "unnamed"
    index: int = 0
    description: str = ""


@dataclass
class VacuumToroidalField:
    r0: float = 0.0
    b0: float = 0.0


@dataclass
class RZTuple:
    r: Union[float, np.ndarray]
    z: Union[float, np.ndarray]


class Signal(Dict):
    def __init__(self,  *args, time=None, data=None, **kwargs):
        super().__init__(*args, **kwargs)
        if type(time) is int:
            time = np.linspace(0, 1, time)
        elif type(time) is float:
            time = np.linspace(0, time, 128)
        elif isinstance(np.ndarray):
            pass
        elif time is None:
            time = np.linspace(*args, **kwargs)
        else:
            raise TypeError(type(time))
        self.__dict__["_time"] = time

        if isinstance(data, LazyProxy):
            data = data()
        self.__dict__["_data"] = data or np.full(self._time.shape, np.nan)

        assert(self._data.shape == self._time.shape)

    @property
    def time(self):
        return self._time

    @property
    def data(self):
        return self._data

    @cached_property
    def data_error_upper(self):
        """Upper error for "data" {dynamic} [as_parent]   """
        return NotImplemented

    @cached_property
    def data_error_lower(self):
        """Lower error for "data" {dynamic} [as_parent]   """
        return NotImplemented

    @cached_property
    def data_error_index(self):
        """Index in the error_description list for "data" {constant}"""
        return NotImplemented
