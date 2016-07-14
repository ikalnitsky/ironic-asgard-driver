# Copyright (c) 2016 Mirantis, Inc
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from six.moves import configparser

from oslo_config import cfg
from oslo_log import log

from ironic.common import exception
from ironic.common.i18n import _
from ironic.common import utils
from ironic.drivers import base
from ironic import objects


CONF = cfg.CONF
CONF.register_opts(
    [
        cfg.StrOpt('driver', help=_(
            'A driver to be used for creating discovered nodes if nothing '
            'is passed explicitly.')),
    ],
    group='asgard')

LOG = log.getLogger(__name__)


class AsgardVendorDriver(base.VendorInterface):

    def __init__(self):
        super(AsgardVendorDriver, self).__init__()

        # When new node is created, we want to initialize with some driver
        # settings (so called driver_info). The set of info may vary and
        # unfortunately oslo_config can't deal with that. Hence, we need
        # read the same files and provides those settings "As Is".
        self._conf = configparser.ConfigParser()
        self._conf.read(CONF.config_file)

    def get_properties(self):
        return {}

    def validate(self, task, method, **kwargs):
        pass

    @base.driver_passthru(['POST'], async=False)
    def lookup(self, context, **kwargs):
        LOG.debug('Asgard lookup with data %s', kwargs)

        if 'node_uuid' in kwargs:
            # If UUID is passed, and node is not found - simply fail.
            # Passing UUID means you know that a node is created, so
            # auto creating a node is wrong way to go. Let's force
            # users to figure out what's wrong.
            node = objects.Node.get_by_uuid(context, kwargs['node_uuid'])
        else:
            # Try to find node in database by recived MAC addresses.
            # Usually, already created node sends UUID within request,
            # however if a node was rebooted the first request will
            # occure without UUID.
            try:
                node = self._get_node_by_mac(context, [
                    iface['mac_address']
                    for iface in kwargs['inventory']['interfaces']
                ])

            # Here's the auto-discovery in action: if node is not in the
            # database, then create one with appropriate attributes.
            except exception.NodeNotFound:
                node = self._create_node(context, **kwargs)

        return {
            'node': node.as_dict()
        }

    def _get_node_by_mac(self, context, mac_addresses):
        for mac in mac_addresses:
            try:
                mac = utils.validate_and_normalize_mac(mac)
            except exception.InvalidMAC:
                LOG.warning('Incorrect MAC address: %s', mac)

            try:
                port = objects.Port.get_by_address(context, mac)
                return objects.Node.get_by_id(context, port.node_id)
            except exception.PortNotFound:
                continue

        raise exception.NodeNotFound(_(
            'No nodes with any of these MAC addresses: %s') % mac_addresses)

    def _create_node(self, context, **kwargs):
        driver_name = kwargs.get('driver', CONF.asgard.driver)
        driver_info = self._get_conf_subsection(context, driver_name)
        instance_info = self._get_conf_subsection(context, 'instance_info')

        node = objects.Node(
            driver=driver_name,
            driver_info=driver_info,
            instance_info={
                'image_source': 'http://download.cirros-cloud.net/0.3.4/cirros-0.3.4-x86_64-disk.img',
                'image_checksum': 'ee1eca47dc88f4879d8a229cc70a07c6',
                'image_disk_format': 'qcow2',
            },
            extra=kwargs,
        )
        node.create()

        # Create a new port for each received network interface. This will
        # allow us to do not create a new node on each new lookup request.
        inventory = kwargs.get('inventory', {}).get('interfaces', [])
        self._create_ports(context, node, inventory)
        return node

    def _create_ports(self, context, node, interfaces):
        for interface in interfaces:
            try:
                address = utils.validate_and_normalize_mac(
                    interface['mac_address']
                )
            except exception.InvalidMAC:
                LOG.warning('Cannot create port for MAC address: %s', address)
                continue

            port = objects.Port(
                node_id=node.id,
                address=address,
            )
            port.create()

    def _get_conf_subsection(self, context, subsection):
        info = {}

        if self._conf.has_section('asgard:%s' % subsection):
            info = dict(self._conf.items('asgard:%s' % subsection))

            # unfortunately, ConfigParser returns a mix of section options
            # and options from DEFAULT section. we need to pop them out,
            # since we aren't interested in them
            for option in self._conf.defaults().keys():
                info.pop(option, None)

        return info
