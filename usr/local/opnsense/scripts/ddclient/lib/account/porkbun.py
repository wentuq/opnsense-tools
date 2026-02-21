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
        try:
            return requests.post(
                f"https://{self._services['porkbun']}/api/json/v3/dns/{endpoint}",
                json=payload, timeout=10
            ).json()
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    def execute(self):
        if not super().execute():
            return False

        record_type = "AAAA" if ":" in str(self.current_address) else "A"
        auth = {"apikey": self.settings.get('username'), "secretapikey": self.settings.get('password')}
        zone = self.settings.get('zone', '').strip()
        hostnames = [h.strip() for h in self.settings.get('hostnames', '').split(',') if h.strip()]

        if not hostnames or not zone:
            return False

        success_all = True
        for fqdn in hostnames:
            subdomain = fqdn[:-(len(zone) + 1)] if fqdn != zone else ""

            resp = self._api(f"retrieveByNameType/{zone}/{record_type}/{subdomain}".rstrip('/'), auth)
            if resp.get('status') != 'SUCCESS':
                syslog.syslog(syslog.LOG_ERR, f"Account {self.description} error retrieving record for {fqdn}: {resp.get('message', 'Unknown error')}")
                success_all = False
                continue

            records = resp.get('records', [])
            if records and records[0].get('content') == str(self.current_address):
                if self.is_verbose:
                    syslog.syslog(syslog.LOG_NOTICE, f"Account {self.description} IP for {fqdn} is already {self.current_address}")
                continue

            payload = {**auth, "content": str(self.current_address)}
            if not records:
                endpoint = f"create/{zone}"
                payload.update({"name": subdomain, "type": record_type})
            elif subdomain:
                endpoint = f"editByNameType/{zone}/{record_type}/{subdomain}"
            else:
                # editByNameType fails for bare domain — use edit-by-ID
                endpoint = f"edit/{zone}/{records[0]['id']}"
                payload.update({"type": record_type})

            resp = self._api(endpoint, payload)
            if resp.get('status') == 'SUCCESS':
                syslog.syslog(syslog.LOG_NOTICE, f"Account {self.description} set new ip {self.current_address} for {fqdn}")
            else:
                syslog.syslog(syslog.LOG_ERR, f"Account {self.description} failed to set ip {self.current_address} for {fqdn}: {resp.get('message', 'Unknown error')}")
                success_all = False

        if success_all:
            self.update_state(address=self.current_address)
            return True
        return False
