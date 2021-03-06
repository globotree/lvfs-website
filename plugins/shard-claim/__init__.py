#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2019-2020 Richard Hughes <richard@hughsie.com>
#
# SPDX-License-Identifier: GPL-2.0+
#
# pylint: disable=no-self-use,no-member,too-few-public-methods,unused-argument,singleton-comparison

from lvfs import db
from lvfs.pluginloader import PluginBase
from lvfs.models import Test, ComponentShard, ComponentShardInfo

class Plugin(PluginBase):
    def __init__(self, plugin_id=None):
        PluginBase.__init__(self, plugin_id)
        self.infos_by_guid = {}

    def name(self):
        return 'Shard Claim'

    def summary(self):
        return 'Add component claims based on shard GUIDs'

    def order_after(self):
        return ['chipsec']

    def ensure_test_for_fw(self, fw):

        # add if not already exists
        test = fw.find_test_by_plugin_id(self.id)
        if not test:
            test = Test(self.id, waivable=True)
            fw.tests.append(test)

    def run_test_on_fw(self, test, fw):

        # find any infos that indicate a claim
        if not self.infos_by_guid:
            for info in db.session.query(ComponentShardInfo)\
                                  .filter(ComponentShardInfo.claim_kind != None):
                self.infos_by_guid[info.guid] = info

        # run analysis on the component and any shards
        for md in fw.mds:
            for shard in md.shards:
                if shard.guid in self.infos_by_guid:
                    info = self.infos_by_guid[shard.guid]
                    md.add_claim(info.claim_kind, info.claim_value)

# run with PYTHONPATH=. ./env/bin/python3 plugins/shard-claim/__init__.py
if __name__ == '__main__':
    import sys
    from lvfs.models import Firmware, Component

    plugin = Plugin('shard-claim')
    _test = Test(plugin.id)
    _fw = Firmware()
    _md = Component()
    _md.shards.append(ComponentShard(guid='f114faa8-4fd5-4b95-8bc3-bc5cb5454966'))
    _fw.mds.append(_md)
    plugin.run_test_on_fw(_test, _fw)
    for claim in _md.claims:
        print(claim)
