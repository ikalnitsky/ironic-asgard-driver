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

from ironic.drivers import base
from ironic.drivers.modules import fake
from ironic.drivers import utils
from ironic_staging_drivers import ansible as ironic_ansible

from ironic_asgard_driver import vendor


class AsgardDriver(base.BaseDriver):
    def __init__(self):
        self.vendor = vendor.AsgardVendorDriver()


# Since Asgard is focused on standalone mode with static PXE config,
# there's no need in PXEBoot driver. However, so far Ansible driver
# doesn't have an option to disable it. Hence, we need to build own
# version with turned off PXEBoot.
class AsgardAnsibleAndIPMIDriver(ironic_ansible.AnsibleAndIPMIToolDriver):
    def __init__(self):
        super(AsgardAnsibleAndIPMIDriver, self).__init__()
        self.boot = _FakeBoot()


# Similiar to above, but without power management. Intended to be used
# for testing purposes only.
class AsgardAnsibleAndFakeDriver(ironic_ansible.FakeAnsibleDriver):
    def __init__(self):
        super(AsgardAnsibleAndFakeDriver, self).__init__()
        self.boot = _FakeBoot()


# Ironic FakeBoot driver has wrong interface for prepare_ramdisk method.
# That cause a runtime exception if used together  with non-fake deploy
# driver. The fix to upstream is on review [1], but we need to workaround
# the problem till fix is landed.
#
# [1]: https://review.openstack.org/#/c/341056/
class _FakeBoot(fake.FakeBoot):
    def prepare_ramdisk(self, task, ramdisk_params):
        pass
