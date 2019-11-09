from datetime import datetime
from enum import Enum, unique
from typing import Any, Dict, List, Union

from fieldmarshal import Registry, struct, field


@unique
class ServerStatus(Enum):
    RUNNING = 'running'
    STARTING = 'starting'
    STOPPING = 'stopping'
    OFF = 'off'
    UNKNOWN = 'unknown'


@struct
class ServerType:
    id: int
    name: str
    num_cores: int = field('cores')
    memory_gb: int = field('memory')
    disk_gb: int = field('disk')


@struct
class DnsPtr:
    ip: str
    dns_ptr: str


@struct
class IPAddress:
    ip: str
    dns_ptr: Union[str, List[DnsPtr]]


@struct
class Server:

    @struct
    class PublicNet:
        ipv4: IPAddress
        ipv6: IPAddress
        floating_ips: List[int]

    id: int
    name: str
    status: ServerStatus
    created: datetime
    server_type: ServerType
    public_net: PublicNet
    labels: Dict[str, str]


@struct
class ServerResponse:
    server: Server


registry = Registry()

# FIXME datetime.fromisoformat requires Python >= 3.7
registry.add_unmarshal_hook(datetime, datetime.fromisoformat)
registry.add_marshal_hook(datetime, lambda dt: dt.isoformat())


def main(data):
    server = registry.unmarshal_json(data, ServerResponse).server
    #print(server)
    print('server.id: %r' % server.id)
    print('server.name: %r' % server.name)
    print('server.status: %r' % server.status)
    print('server.created: %r' % server.created)
    print('server.labels: %r' % server.labels)
    print('server.public_net.ipv4.ip: %r' % server.public_net.ipv4.ip)
    print('server.public_net.ipv4.dns_ptr: %r' % server.public_net.ipv4.dns_ptr)
    print('server.public_net.ipv6.ip: %r' % server.public_net.ipv6.ip)
    print('server.public_net.ipv6.dns_ptr[0].ip: %r' % server.public_net.ipv6.dns_ptr[0].ip)
    print('server.public_net.ipv6.dns_ptr[0].dns_ptr: %r' % server.public_net.ipv6.dns_ptr[0].dns_ptr)
    print('server.server_type.id: %r' % server.server_type.id)
    print('server.server_type.name: %r' % server.server_type.name)
    print('server.server_type.num_cores: %r' % server.server_type.num_cores)
    print('server.server_type.memory_gb: %r' % server.server_type.memory_gb)
    print('server.server_type.disk_gb: %r' % server.server_type.disk_gb)

    assert registry.unmarshal(registry.marshal(server), Server) == server


if __name__ == '__main__':
    import os
    file_path = os.path.join(os.path.dirname(__file__), 'server.json')
    with open(file_path) as f:
        main(f.read())
