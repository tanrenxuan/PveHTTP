from enum import Enum


class NetworkType(Enum):
    bridge = 'bridge'
    bond = 'bond'
    eth = 'eth'
    alias = 'alias'
    vlan = 'vlan'
    OVSBridge = 'OVSBridge'
    OVSBond = 'OVSBond'
    OVSPort = 'OVSPort'
    OVSIntPort = 'OVSIntPort'
    any_bridge = 'any_bridge'
