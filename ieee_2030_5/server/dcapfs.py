from flask import Response

import ieee_2030_5.adapters as adpt
from ieee_2030_5.server.base_request import RequestOp


class Dcap(RequestOp):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get(self) -> Response:
        # TODO: Test for allowed dcap here.
        # if not self._end_devices.allowed_to_connect(self.lfdi):
        #     raise werkzeug.exceptions.Unauthorized()
        dcap = adpt.DeviceCapabilityAdapter.get_by_lfdi(self.lfdi)

        return self.build_response_from_dataclass(dcap)