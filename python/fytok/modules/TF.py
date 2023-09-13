from __future__ import annotations


from spdm.geometry.GeoObject import GeoObject

from fytok._imas.lastest.tf import _T_tf, _T_tf_coil


class TF(_T_tf):
    
    def __geometry__(self, view="RZ", **kwargs) -> GeoObject:

        return {}
