from typing import Optional
from NetworkType import NetworkType
import requests
import sys
import urllib3
import re

urllib3.disable_warnings()

cidr_pattern = r"^(?:(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\/([1-9]|[1-2]\d|3[0-2])$"
ipv4_pattern = r"^(?:(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$"


class PveHTTP:
    def __init__(self, host, username, password, type):
        self.host = host
        self.username = username
        self.password = password
        self.login_type = type
        self.base_url = 'https://' + host + ':8006'

        login_data = self._ticket()
        if not login_data:  # 登陆失败，退出程序
            sys.exit(1)
        self.ticket = login_data.get('ticket')
        self.csrf_token = login_data.get('CSRFPreventionToken')
        self.verify_header = {
            'Cookie': 'PVEAuthCookie={}'.format(self.ticket),
            'CSRFPreventionToken': self.csrf_token,
        }

    def req(self, api_url: str, description: str, **kwargs) -> (bool, object):
        """
        封装url
        :param api_url: api接口
        :param description: 接口动作描述，最好包含具体参数，比如xx虚拟机启动
        :param kwargs: 其他参数
        :return: bool表示是否请求成功 若需要返回值，则object为具体data
        """
        url = self.base_url + api_url
        try:
            kwargs = {
                **kwargs,
                'verify': False}
            response = requests.request(url=url, **kwargs)
            if response.status_code != 200:
                print(f'{description}失败，错误码为：{response.status_code} '
                      f'错误原因：{response.reason} '
                      f'{"具体错误原因：{}".format(response.json().get("errors")) if response.json() and response.json().get("errors") else ""}')
                return False, response.json().get("data") if response.json() else None
            return True, response.json().get("data") if response.json() else None
        except Exception as e:
            print(e)

    def _ticket(self):
        """
        Create or verify authentication ticket
        HTTP: POST /api2/json/access/ticket
        :return:
        """
        api_url = '/api2/json/access/ticket'
        payload = {
            'username': self.username,
            'password': self.password,
            'realm': self.login_type
        }
        _, response_data = self.req(api_url, description=f'{self.username}登录', method='post', json=payload)
        return response_data

    def get_cluster_status(self) -> (bool, object):
        """
        List recent tasks (cluster wide).
        HTTP: GET /api2/json/cluster/status
        :return:
        """
        api_url = "/api2/json/cluster/status"
        ok, response_data = self.req(api_url, description="获取集群状态", method='get', headers=self.verify_header)
        return ok, response_data

    def get_cluster_tasks(self) -> (bool, object):
        """
        List recent tasks (cluster wide)
        HTTP: GET /api2/json/cluster/tasks
        :return:
        """
        api_url = "/api2/json/cluster/tasks"
        ok, response_data = self.req(api_url, description="获取集群任务", method='get', headers=self.verify_header)
        return ok, response_data

    def vm_list(self, node: str = 'pve') -> (bool, list):
        """
        Virtual machine index (per node).
        HTTP: GET /api2/json/nodes/{node}/qemu
        :param node: 节点
        :return:
        """
        api_url = f'/api2/json/nodes/{node}/qemu'
        ok, response_data = self.req(api_url, description=f"获取{node}节点所有虚拟机", method='get', headers=self.verify_header)
        if ok:
            return True, [vm['vmid'] for vm in response_data]
        return False, []

    def vm_start(self, vmid: int, node: str = 'pve') -> bool:
        """
        Start virtual machine
        HTTP: POST /api2/json/nodes/{node}/qemu/{vmid}/status/start
        :param node: node
        :param vmid: vm id
        :return:
        """
        api_url = f'/api2/json/nodes/{node}/qemu/{vmid}/status/start'
        _, available_vm = self.vm_list()
        if vmid not in available_vm:
            print(f'节点{node}下不存在虚拟机{vmid}')
            return False
        ok, _ = self.req(api_url, description=f"开启节点{node}下的虚拟机{vmid}", method='post', headers=self.verify_header)
        return ok

    def vm_stop(self, vmid: int, node: str = 'pve') -> bool:
        """
        Stop virtual machine. The qemu process will exit immediately.
        Thisis akin to pulling the power plug of a running computer and may damage the VM data.
        不推荐使用
        HTTP: POST /api2/json/nodes/{node}/qemu/{vmid}/status/stop
        :param node: node
        :param vmid: vm id
        :return:
        """
        api_url = f'/api2/json/nodes/{node}/qemu/{vmid}/status/stop'
        _, available_vm = self.vm_list()
        if vmid not in available_vm:
            print(f'节点{node}下不存在虚拟机{vmid}')
            return False
        ok, _ = self.req(api_url, description=f"强制关闭节点{node}下的虚拟机{vmid}", method='post', headers=self.verify_header)
        return ok

    def vm_shutdown(self, vmid: int, node: str = 'pve') -> bool:
        """
        Shutdown virtual machine. This is similar to pressing the power button on a physical machine.
        This will send an ACPI event for the guest OS, which should then proceed to a clean shutdown.
        一般情况使用这种方式关闭虚拟机
        HTTP: POST /api2/json/nodes/{node}/qemu/{vmid}/status/shutdown
        :param node: node
        :param vmid: vm id
        :return:
        """
        api_url = f'/api2/json/nodes/{node}/qemu/{vmid}/status/shutdown'
        _, available_vm = self.vm_list()
        if vmid not in available_vm:
            print(f'节点{node}下不存在虚拟机{vmid}')
            return False
        ok, _ = self.req(api_url, description=f"关闭节点{node}下的虚拟机{vmid}", method='post', headers=self.verify_header)
        return ok

    def get_available_networks(self, node: str = 'pve', network_type: Optional[NetworkType] = None) -> (bool, list):
        """
        List available networks
        HTTP: GET /api2/json/nodes/{node}/network
        :param node: 结点
        :param network_type: 默认返回所有network设备，若含有此参数，则只返回对应类型的network设备
        :return:
        """
        api_url = f'/api2/json/nodes/{node}/network'
        params = None
        if network_type is not None:
            params = {
                'type': network_type.value
            }
        ok, response_data = self.req(api_url, description=f"获取{network_type.value if network_type is not None else '所有'}类型网络设备", method='get', headers=self.verify_header, params=params)
        if ok:
            return True, [network_device['iface'] for network_device in response_data]
        return False, []

    def create_network_bridge(self, iface: str, node: str = 'pve', cidr: Optional[str] = None,
                              gateway: Optional[str] = None, autostart: Optional[bool] = True,
                              bridge_ports: Optional[str] = None, ) -> bool:
        """
        创建网络设备linux bridge（不同的网络设备，请求体设置的参数有所区别，由于只需要bridge类型device，type硬编码为NetworkType。bridge）
        :param iface: 名称，最好起类似名称vmbr0、vmbr1等
        :param node: 节点
        :param cidr: cidr参数，形式x.x.x.x/d，如192.168.247.131/24
        :param gateway: 网关 形式x.x.x.x
        :param autostart: 是否自动启动
        :param bridge_ports: 端口从属，如ens33
        :return:
        """
        api_url = f'/api2/json/nodes/{node}/network'
        payload = {
            "iface": iface,  # no existence judge
            "type": NetworkType.bridge.value,  # 硬编码为bridge类型
            "autostart": autostart,
        }
        if cidr is not None:
            if not re.match(cidr_pattern, cidr):
                print("cidr格式错误，格式为x.x.x.x/d")
                return False
            payload['cidr'] = cidr
        if gateway is not None:
            if not re.match(ipv4_pattern, gateway):
                print("gateway格式错误，格式为x.x.x.x")
                return False
            payload['gateway'] = gateway
        if bridge_ports is not None:  # no existence judge
            payload['bridge_ports'] = bridge_ports
        ok, _ = self.req(api_url, description=f"创建网络设备：{'iface:{}'.format(iface)}", method='post', headers=self.verify_header, json=payload)
        return ok

    def __str__(self):
        dict_str = ''
        for attr, value in self.__dict__.items():
            dict_str += '\n{}: {}'.format(attr, value)
        return '<class PveHTTP>: {}'.format(dict_str)


if __name__ == '__main__':
    my_data = {
        'username': 'root',
        'password': '123456',
        'host': '192.168.247.131',
        'type': 'pam'
    }
    lab_data = {
        'username': 'root',
        'password': '1qaz@WSX3edc',
        'host': '10.0.0.110',
        'type': 'pve'
    }
    p = PveHTTP(**my_data)
    # print(p.get_available_networks(network_type=NetworkType.bridge))
    # p.create_network_bridge(iface="vmbr111", bridge_ports='ens11')
    print(p.get_cluster_status())
    print(p.get_cluster_tasks())
    # print(p.vm_start(101))
    print(p.get_available_networks(network_type=NetworkType.eth))
    p.create_network_bridge(iface="vmbr1111", cidr="1.2.3.4/22")
