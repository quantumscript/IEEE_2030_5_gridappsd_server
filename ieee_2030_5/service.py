from zeroconf import ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf


class MyListener(ServiceListener):

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        print(f"Service {name} updated")

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        print(f"Service {name} removed")

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        print(f"Service {name} added, service info: {info}")


zeroconf = Zeroconf()
listener = MyListener()
browser = ServiceBrowser(zeroconf, "_smartenergy._tcp.local.", listener)

si = ServiceInfo(type_="_smartenergy._tcp.local.",
                 name="device-dev1._smartenergy._tcp.local.",
                 properties={
                     'txtvers': 1,
                     'https': 7443,
                     'dcap': '/dcap'
                 })
si.addresses = ['127.0.0.1']
si.port = 7443
zeroconf.register_service(si)
try:
    input("Press enter to exit...\n\n")
finally:
    zeroconf.close()