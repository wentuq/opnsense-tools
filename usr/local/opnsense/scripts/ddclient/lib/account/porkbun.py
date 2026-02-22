import syslog
import requests
from . import BaseAccount

class Porkbun(BaseAccount):
    _priority = 65535
    _services = {'porkbun': 'api.porkbun.com'}

    @staticmethod
    def known_services():
        return {'porkbun': 'Porkbun'}

    @staticmethod
    def match(account):
        return account.get('service') in Porkbun._services

    def _api(self, endpoint, payload):
        """ POST to the Porkbun API, always returns a dict with at least 'status'. """
        try:
            return requests.post(
                f"https://{self._services['porkbun']}/api/json/v3/{endpoint}",
                json=payload, timeout=10
            ).json()
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    def execute(self):
        if not super().execute():
            return False

        record_type = "AAAA" if ":" in str(self.current_address) else "A"
        auth = {"apikey": self.settings.get('username'), "secretapikey": self.settings.get('password')}
        hostnames = [h.strip() for h in self.settings.get('hostnames', '').split(',') if h.strip()]

        if not hostnames:
            return False

        success_all = True
        for fqdn in hostnames:
            # Discover the zone by trying progressively shorter suffixes of the FQDN,
            # starting from the shortest plausible zone (last 2 labels) and working
            # toward longer ones. This handles any TLD depth (e.g. co.uk, com.au)
            # and doubles as the record fetch — no separate discovery call needed.
            #   example.com        → i=0: zone=example.com    sub=""          (1 call)
            #   sub.example.com    → i=1: zone=example.com    sub=sub         (1 call)
            #   a.b.example.com    → i=2: zone=example.com    sub=a.b         (1 call)
            #   sub.example.co.uk  → i=2: co.uk fails,
            #                        i=1: zone=example.co.uk  sub=sub         (2 calls)
            parts = fqdn.split('.')
            zone, subdomain, records = None, None, None
            for i in range(len(parts) - 2, -1, -1):
                z, s = '.'.join(parts[i:]), '.'.join(parts[:i])
                resp = self._api(f"dns/retrieveByNameType/{z}/{record_type}/{s}".rstrip('/'), auth)
                if resp.get('status') == 'SUCCESS':
                    zone, subdomain, records = z, s, resp.get('records', [])
                    break

            if not zone or not records:
                syslog.syslog(syslog.LOG_ERR, f"Account {self.description} no {record_type} record found for {fqdn}")
                success_all = False
                continue

            # Skip if the DNS record already matches the current IP
            if records[0].get('content') == str(self.current_address):
                if self.is_verbose:
                    syslog.syslog(syslog.LOG_NOTICE, f"Account {self.description} IP for {fqdn} is already {self.current_address}")
                continue

            # editByNameType works for both subdomains and bare domain,
            # but bare domain must have no trailing slash in the URL
            endpoint = f"dns/editByNameType/{zone}/{record_type}/{subdomain}".rstrip('/')

            resp = self._api(endpoint, {**auth, "type": record_type, "content": str(self.current_address)})
            if resp.get('status') == 'SUCCESS':
                syslog.syslog(syslog.LOG_NOTICE, f"Account {self.description} set new ip {self.current_address} for {fqdn}")
            else:
                syslog.syslog(syslog.LOG_ERR, f"Account {self.description} failed to set ip {self.current_address} for {fqdn}: {resp.get('message', 'Unknown error')}")
                success_all = False

        if success_all:
            self.update_state(address=self.current_address)
            return True
        return False
