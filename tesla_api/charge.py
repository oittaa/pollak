class Charge:
    def __init__(self, api_client, vehicle_id):
        self._api_client = api_client
        self._vehicle_id = vehicle_id

    def get_state(self):
        return self._api_client.get('vehicles/{}/data_request/charge_state'.format(self._vehicle_id))
