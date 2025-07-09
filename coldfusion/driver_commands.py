#!/usr/bin/python
# -*- coding: utf-8 -*-

import requests, traceback

# Need to disable the waring, because the chassis certificate is self-signed
from requests.packages import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from cloudshell.layer_one.core.driver_commands_interface import DriverCommandsInterface
from cloudshell.layer_one.core.response.response_info import ResourceDescriptionResponseInfo
from cloudshell.layer_one.core.response.resource_info.entities.chassis import Chassis
from cloudshell.layer_one.core.response.resource_info.entities.blade import Blade
from cloudshell.layer_one.core.response.resource_info.entities.port import Port
from cloudshell.layer_one.core.response.response_info import AttributeValueResponseInfo

# Docs
# https://devguide.quali.com/introduction/8.3.0/the-cloudshell-devguide.html

class ColdFusionException(Exception):
    def __init__(self, description):
        self.description = description

    def __str__(self):
        return self.description

class DriverCommands(DriverCommandsInterface):
    """
    Driver commands implementation
    """

    def __init__(self, logger, runtime_config):
        """
        :param logger:
        :type logger: logging.Logger
        """
        self._runtime_config = runtime_config
        self._logger = logger
        self._session = requests.Session()
        self._session.verify = False  # don't validate certificate as it's self-signed

    def login(self, address, username, password):
        """
        Perform login operation on the device
        :param address: resource address, "192.168.42.240"
        :param username: username to login on the device
        :param password: password
        :return: None
        :raises Exception: if command failed
        Example:
            # Define session attributes
            self._cli_handler.define_session_attributes(address, username, password)

            # Obtain cli session
            with self._cli_handler.default_mode_service() as session:
                # Executing simple command
                device_info = session.send_command('show version')
                self._logger.info(device_info)
        """
        self._logger.info("@login to {0}".format(address))
        self._session.auth = (username, password)
        self._address = address
        port = 8443
        try:
            address_split = self._address.split(":")
            port = int(address_split[-1])
            self._address = ":".join(address_split[:-1])
        except ValueError:
            port = 8443
        prepend = "https://"
        if "https://" in self._address:
            prepend = ""
        self._baseurl = "{}{}:{}".format(prepend, self._address, port)
        j = self.system_get("version")
        self._version = j["Version"]
        self._logger.info("$Login succeeded - CF Version {0}".format(self._version))


    def get_state_id(self):
        """
        Check if CS synchronized with the device.
        :return: Synchronization ID, GetStateIdResponseInfo(-1) if not used
        :rtype: cloudshell.layer_one.core.response.response_info.GetStateIdResponseInfo
        :raises Exception: if command failed

        Example:
            # Obtain cli session
            with self._cli_handler.default_mode_service() as session:
                # Execute command
                chassis_name = session.send_command('show chassis name')
                return chassis_name
        """
        self._logger.info("@get_state_id")

        from cloudshell.layer_one.core.response.response_info import GetStateIdResponseInfo
        chassis_json = self.chassis_get("")
        session_id = chassis_json["SessionId"]
        return GetStateIdResponseInfo(session_id)

    def set_state_id(self, state_id):
        """
        Set synchronization state id to the device, called after Autoload or SyncFomDevice commands
        :param state_id: synchronization ID
        :type state_id: str
        :return: None
        :raises Exception: if command failed

        Example:
            # Obtain cli session
            with self._cli_handler.config_mode_service() as session:
                # Execute command
                session.send_command('set chassis name {}'.format(state_id))
        """
        self._logger.info("@set_state_id={}".format(state_id))

        body = dict(SessionId=state_id)
        self.chassis_put("", body)

    def get_resource_description(self, address):
        """
        Auto-load function to retrieve all information from the device
        :param address: resource address, '192.168.42.240'
        :type address: str
        :return: resource description
        :rtype: cloudshell.layer_one.core.response.response_info.ResourceDescriptionResponseInfo
        :raises cloudshell.layer_one.core.layer_one_driver_exception.LayerOneDriverException: Layer one exception.

        Example:

            from cloudshell.layer_one.core.response.resource_info.entities.chassis import Chassis
            from cloudshell.layer_one.core.response.resource_info.entities.blade import Blade
            from cloudshell.layer_one.core.response.resource_info.entities.port import Port

            chassis_resource_id = chassis_info.get_id()
            chassis_address = chassis_info.get_address()
            chassis_model_name = "Coldfusion Chassis"
            chassis_serial_number = chassis_info.get_serial_number()
            chassis = Chassis(resource_id, address, model_name, serial_number)

            blade_resource_id = blade_info.get_id()
            blade_model_name = 'Generic L1 Module'
            blade_serial_number = blade_info.get_serial_number()
            blade.set_parent_resource(chassis)

            port_id = port_info.get_id()
            port_serial_number = port_info.get_serial_number()
            port = Port(port_id, 'Generic L1 Port', port_serial_number)
            port.set_parent_resource(blade)

            return ResourceDescriptionResponseInfo([chassis])
        """
        self._logger.info("@get_resource_description")

        chassis_json = self.chassis_get("")

        chassis_resource_id = address
        chassis_address = address
        chassis_model_name = "Coldfusion Chassis"
        chassis_serial_number = chassis_json["Serial"]
        chassis = Chassis(chassis_resource_id, chassis_address, chassis_model_name, chassis_serial_number)

        # Discover and configure the topology
        _blades = {}
        linecards_json = chassis_json["Linecards"]
        for lc in range(len(linecards_json)):
            self._logger.info("Resource LC-{0}".format(lc + 1))
            if linecards_json[lc]!=None:
                blade_resource_id = str(lc+1)
                blade_model_name = 'Generic L1 Module'
                blade_serial_number = "L".format(lc+1)
                blade = Blade(blade_resource_id, blade_model_name, blade_serial_number)
                blade.set_parent_resource(chassis)
                _blades[lc+1] = {}

                ports_json = self.chassis_get("linecards/{0}/ports".format(lc))
                for port in range(0, len(ports_json)):
                    ptype = ports_json[port]["Type"]
                    breakout = ports_json[port]["Breakout"]
                    if breakout and ptype=="OPort_CF1":
                        for lane in range(4):
                            port_id = self._qport(port + 1, lane + 1)
                            port_serial_number = "{0:02}.{1:01}.{2}".format(lc + 1, port + 1, lane + 1)
                            port_obj = Port(port_id, 'Generic L1 Port', port_serial_number)
                            port_obj.set_parent_resource(blade)
                            _blades[lc+1][port_id] = port_obj
                    else:
                        port_id = self._qport(port + 1)
                        port_serial_number = "{0:02}.{1:01}.1".format(lc + 1, port + 1)
                        port_obj = Port(port_id, 'Generic L1 Port', port_serial_number)
                        port_obj.set_parent_resource(blade)
                        _blades[lc+1][port_id] = port_obj

        # Configure the mappings
        for lc, blade in _blades.items():
            ports_json = self.chassis_get("linecards/{0}/ports".format(lc-1))
            num_ports = len(ports_json)
            ports = ["{0}.{1}".format(lc, port) for port in range(1, num_ports+1)]
            body = dict(Ports=ports)
            flows = self.chassis_post("show-flow", body)
#            self._logger.info("@flows for LC-{0}={1}".format(lc,str(flows)))
            for port in range(0, num_ports):
                egress = flows['Ports'][port]['Egress']
                ptype = ports_json[port]["Type"]
                breakout = ports_json[port]["Breakout"]
                if breakout and ptype=="OPort_CF1":
                    for lane in range(4):
                        port_id = self._qport(port+1, lane+1)
                        port_obj = blade[port_id]
                        for egress_port in egress:
                            index = min(lane, len(egress_port)-1)
                            if egress_port[index]!=None and len(egress_port[index])>0:
                                self._logger.info("$$$ {0} -> {1} [lane={2}, index={3}]".format(port_obj.address, egress_port[index], lane, index))
                                eport_lc, eport_port, eport_lane = self._parse_lport(egress_port[index])
                                self._logger.info("@ {0} {1} {2}".format(eport_lc, eport_port, eport_lane))
                                if len(egress_port)==1:
                                    eport_lane = lane+1
                                if _blades.has_key(eport_lc) and eport_lane==lane+1:
                                    port_id = self._qport(eport_port, eport_lane)
                                    mapped_to = _blades[eport_lc][port_id]
                                    mapped_to.add_mapping(port_obj)
                                    self._logger.info("$$$ {0} mapped to {1}".format(port_obj.address, mapped_to.address))
                else:
                    port_id = self._qport(port+1)
                    port_obj = blade[port_id]
                    for egress_port in egress:
                        self._logger.info("$$$ {0} -> {1}".format(port_obj.address, egress_port))
                        eport = self._parse_lport(egress_port[0])
                        if _blades.has_key(eport[0]):
                            port_id = self._qport(eport[1], eport[2])
                            try:
                                mapped_to = _blades[eport[0]][port_id]
                                mapped_to.add_mapping(port_obj)
                                self._logger.info("$$$ {0} mapped to {1}".format(port_obj.address, mapped_to.address))
                            except Exception:
                                self._logger.error("$$$ Exception populating mapping - " + traceback.format_exc())
                                self._logger.info("$$$ _blades[{0}] keys={1}".format(eport[0], sorted(_blades[eport[0]].keys())))
                                raise

        return ResourceDescriptionResponseInfo([chassis])

    def map_bidi(self, src_port, dst_port):
        """
        Create a bidirectional connection between source and destination ports
        :param src_port: src port address, '192.168.42.240/1/21'
        :type src_port: str
        :param dst_port: dst port address, '192.168.42.240/1/22'
        :type dst_port: str
        :return: None
        :raises Exception: if command failed

        Example:
            with self._cli_handler.config_mode_service() as session:
                session.send_command('map bidir {0} {1}'.format(convert_port(src_port), convert_port(dst_port)))

        """
        self._logger.info("@map_bidi {0}<->{1}".format(src_port, dst_port))

        src_port = self._portid(src_port)
        dst_port = self._portid(dst_port)

        body = dict(
            Direction="TwoWay",
            Pairs=[dict(A=src_port, B=dst_port)])
        self.chassis_post("map", body)

    def map_uni(self, src_port, dst_ports):
        """
        Unidirectional mapping of two ports
        :param src_port: src port address, '192.168.42.240/1/21'
        :type src_port: str
        :param dst_ports: list of dst ports addresses, ['192.168.42.240/1/22', '192.168.42.240/1/23']
        :type dst_ports: list
        :return: None
        :raises Exception: if command failed

        Example:
            with self._cli_handler.config_mode_service() as session:
                for dst_port in dst_ports:
                    session.send_command('map {0} also-to {1}'.format(convert_port(src_port), convert_port(dst_port)))
        """
        self._logger.info("@map_uni {0}->{1}".format(src_port, dst_ports))

        src_port_cf = self._portid(src_port)

        port_pairs = []
        for dst_port in dst_ports:
            dst_port_cf = self._portid(dst_port)
            port_pairs.append(dict(A=src_port_cf, B=dst_port_cf))

        body = dict(
            Direction="OneWay",
            Pairs=port_pairs)

        self.chassis_post("map", body)

    def map_clear(self, ports):
        """
        Remove simplex/multi-cast/duplex connection ending on the destination port
        :param ports: ports, ['192.168.42.240/1/21', '192.168.42.240/1/22']
        :type ports: list
        :return: None
        :raises Exception: if command failed

        Example:
            exceptions = []
            with self._cli_handler.config_mode_service() as session:
                for port in ports:
                    try:
                        session.send_command('map clear {}'.format(convert_port(port)))
                    except Exception as e:
                        exceptions.append(str(e))
                if exceptions:
                    raise Exception('self.__class__.__name__', ','.join(exceptions))
        """
        self._logger.info("@map_clear {0}".format(ports))

        port_pairs = []
        for dst_port in ports:
            dst_port_cf = self._portid(dst_port)
            port_pairs.append(dict(A=None, B=dst_port_cf))

        body = dict(
            Direction="Undefined",
            Pairs=port_pairs)
        self.chassis_post("unmap", body)


    def map_clear_to(self, src_port, dst_ports):
        """
        Remove simplex/multi-cast/duplex connection ending on the destination port
        :param src_port: src port address, '192.168.42.240/1/21'
        :type src_port: str
        :param dst_ports: list of dst ports addresses, ['192.168.42.240/1/21', '192.168.42.240/1/22']
        :type dst_ports: list
        :return: None
        :raises Exception: if command failed

        Example:
            with self._cli_handler.config_mode_service() as session:
                _src_port = convert_port(src_port)
                for port in dst_ports:
                    _dst_port = convert_port(port)
                    session.send_command('map clear-to {0} {1}'.format(_src_port, _dst_port))
        """
        self._logger.info("@map_clear_to {0}->{1}".format(src_port, dst_ports))

        src_port_cf = self._portid(src_port)

        port_pairs = []
        for dst_port in dst_ports:
            dst_port_cf = self._portid(dst_port)
            port_pairs.append(dict(A=src_port_cf, B=dst_port_cf))

        body = dict(
            Direction="OneWay",
            Pairs=port_pairs)
        self.chassis_post("unmap", body)

    def get_attribute_value(self, cs_address, attribute_name):
        """
        Retrieve attribute value from the device
        :param cs_address: address, '192.168.42.240/1/21'
        :type cs_address: str
        :param attribute_name: attribute name, "Port Speed"
        :type attribute_name: str
        :return: attribute value
        :rtype: cloudshell.layer_one.core.response.response_info.AttributeValueResponseInfo
        :raises Exception: if command failed

        Example:
            with self._cli_handler.config_mode_service() as session:
                command = AttributeCommandFactory.get_attribute_command(cs_address, attribute_name)
                value = session.send_command(command)
                return AttributeValueResponseInfo(value)
        """
        self._logger.info("@get_attribute_value {0} for {1}".format(attribute_name, cs_address))
        # TODO: Need to implement
        return AttributeValueResponseInfo("")
#        raise NotImplementedError

    def set_attribute_value(self, cs_address, attribute_name, attribute_value):
        """
        Set attribute value to the device
        :param cs_address: address, '192.168.42.240/1/21'
        :type cs_address: str
        :param attribute_name: attribute name, "Port Speed"
        :type attribute_name: str
        :param attribute_value: value, "10000"
        :type attribute_value: str
        :return: attribute value
        :rtype: cloudshell.layer_one.core.response.response_info.AttributeValueResponseInfo
        :raises Exception: if command failed

        Example:
            with self._cli_handler.config_mode_service() as session:
                command = AttributeCommandFactory.set_attribute_command(cs_address, attribute_name, attribute_value)
                session.send_command(command)
                return AttributeValueResponseInfo(attribute_value)
        """
        self._logger.info("@set_attribute_value for {0}: {1}={2}".format(cs_address, attribute_name, attribute_value))
        linecard, port, lane = self._linecard_port_lane(cs_address)
        if lane:
            val = "," * lane-1 + attribute_value + "," * (4-lane)
        else:
            val = attribute_value

        body = dict(Speed=attribute_value)
        self.chassis_put("linecards/{0}/ports/{1}".format(linecard, port), body)

    def map_tap(self, src_port, dst_ports):
        """
        Add TAP connection
        :param src_port: port to monitor '192.168.42.240/1/21'
        :type src_port: str
        :param dst_ports: ['192.168.42.240/1/22', '192.168.42.240/1/23']
        :type dst_ports: list
        :return: None
        :raises Exception: if command failed

        Example:
            return self.map_uni(src_port, dst_ports)
        """
        self._logger.info("@MapTap {0}->{1}".format(src_port, dst_ports))
        return self.map_uni(src_port, dst_ports)

    def set_speed_manual(self, src_port, dst_port, speed, duplex):
        """
        Set connection speed. It is not used with new standard
        :param src_port:
        :param dst_port:
        :param speed:
        :param duplex:
        :return:
        """
        raise NotImplementedError

    def _qport(self, port, lane=None):
        if lane and lane>=1:
            return "{0:02}_{1}".format(port, lane)
        else:
            return "{0:02}".format(port)

    def _qport_abs(self, lc, port, lane=None):
        if lane:
            return "{0}.{1:02}_{2}".format(lc, port, lane)
        else:
            return "{0}.{1:02}".format(lc, port)

    def _portid(self, port):
        parts = port.split("/")
        portid = "{0}.{1}".format(parts[1], parts[2].replace("_", ":"))
        return portid

    def _parse_lport(self, str):
        lc, port_lane = str.split(".")
        parts = port_lane.split(":")
        if len(parts)==2:
            port, lane = parts
        else:
            port = parts[0]
            lane = "-1"
        return int(lc), int(port), int(lane)

    def _linecard_port_lane(self, port):
        parts = port.split("/")
        linecard = parts[1]
        idx = parts[2].find("_")
        if idx >= 0:
            lane = int(parts[2][idx+1:])
            port = parts[2][:idx]
        else:
            lane = None
            port = parts[2]
        return linecard, port, lane

    def system_get(self, api):
        method = "{0}/system/do/{1}".format(self._baseurl, api)
        r = self._session.get(method)
        if r.status_code!=requests.codes.ok:
            raise r.raise_for_status()
        return r.json()

    def chassis_get(self, api):
        method = "{0}/chassis/{1}".format(self._baseurl, api)
        r = self._session.get(method)
        if r.status_code!=requests.codes.ok:
            raise r.raise_for_status()
        return r.json()

    def chassis_put(self, api, body):
        method = "{0}/chassis/{1}".format(self._baseurl, api)
        r = self._session.put(method, json=body)
        if r.status_code==requests.codes.ok:
            return r.json()
        elif r.status_code==requests.codes.no_content:
            return {}

        self._handle_error(r)

    def chassis_post(self, api, body):
        method = "{0}/chassis/do/{1}".format(self._baseurl, api)
        self._logger.info("POST: method={0}, body={1}".format(method, body))
        r = self._session.post(method, json=body)
        if r.status_code==requests.codes.ok:
            return r.json()
        elif r.status_code==requests.codes.no_content:
            return {}

        self._handle_error(r)

    def _handle_error(self, r):
        try:
            error = r.json()["Error"]
        except:
            raise r.raise_for_status()

        self._logger.error("Error: {0}".format(error))
        raise ColdFusionException(error)

