import sys
import time
from pprint import pprint
from typing import Any, Optional

import cimlab.loaders.gridappsd as gridappsd_loader
from cimlab.data_profile import CIM_PROFILE
from cimlab.loaders import ConnectionParameters, Parameter
from cimlab.loaders.gridappsd import GridappsdConnection
from cimlab.models import DistributedModel
from gridappsd import GridAPPSD

gridappsd_loader.set_cim_profile(CIM_PROFILE.RC4_2021.value)

cim = gridappsd_loader.cim

inverter_list = []
debug_output = False


def do_print(data: Any, *args):
    if debug_output:
        print(data, *args)


# sort PowerElectronicsUnits
def get_inverter_buses(network_area):
    if cim.PowerElectronicsConnection in network_area.typed_catalog:
        network_area.get_all_attributes(cim.PowerElectronicsConnection)
        network_area.get_all_attributes(cim.PowerElectronicsConnectionPhase)
        network_area.get_all_attributes(cim.Terminal)
        network_area.get_all_attributes(cim.Analog)

        do_print('\n \n EXAMPLE 6: GET ALL INVERTER PHASES AND BUSES')
        for pec in network_area.typed_catalog[cim.PowerElectronicsConnection].values():
            do_print('\n name: ', pec.name, pec.mRID)
            inverter_list.append((pec.name, pec.mRID, pec.p, pec.q))
            do_print('p = ', pec.p, 'q = ', pec.q)
            node1 = pec.Terminals[0].ConnectivityNode
            do_print('bus: ', node1.name, node1.mRID)
            for pec_phs in pec.PowerElectronicsConnectionPhases:
                do_print('phase ', pec_phs.phase, ': ', pec_phs.mRID)

            for meas in pec.Measurements:
                do_print('Measurement: ', meas.name, meas.mRID)
                do_print('type:', meas.measurementType, 'phases:', meas.phases)


def _main():
    topic = "goss.gridappsd.request.data.topology"
    #feeder_mrid = "_C07972A7-600D-4AA5-B254-4CAA4263560E"    # Ochre 13-node
    feeder_mrid = "_49AD8E07-3BF9-A4E2-CB8F-C3722F837B62"    # 13-node
    # feeder_mrid = "_E407CBB6-8C8D-9BC9-589C-AB83FBF0826D"    # 123-node
    message = {"requestType": "GET_SWITCH_AREAS", "modelID": feeder_mrid, "resultFormat": "JSON"}

    gapps = GridAPPSD(username="system", password="manager")
    t1 = time.perf_counter()
    topology_response = gapps.get_response(topic=topic, message=message, timeout=30)
    t2 = time.perf_counter()
    do_print(f"Retriving topology took: {t2-t1:0}s")

    # TODO setup environment and/or pass in parameters for env.
    gapps_conn = GridappsdConnection(ConnectionParameters())
    gapps_conn.connect()
    feeder = cim.Feeder(mRID=feeder_mrid)
    network = DistributedModel(connection=gapps_conn,
                               feeder=feeder,
                               topology=topology_response['feeders'])

    t1 = time.perf_counter()
    for switch_area in network.switch_areas:
        get_inverter_buses(switch_area)
        for secondary_area in switch_area.secondary_areas:
            get_inverter_buses(secondary_area)
    t2 = time.perf_counter()
    do_print(f"Retriving inverters: {t2-t1:0}s")

    # do_print(network.typed_catalog)
    for t in network.typed_catalog:
        do_print(t.__name__)
    # do_print(network.typed_catalog.get(cim.PowerElectronicsConnection))
    for name, mrid, p, q in inverter_list:
        equip_type = "Solar Panel" if int(p) > 0 else "Battery"
        print(f"name: {name}, equipment: {equip_type}, mrid: {mrid}, p: {p}, q: {q}")
    # pprint(inverter_list)


if __name__ == '__main__':
    _main()