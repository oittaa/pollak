"""General functions for the vehicle."""

from .climate import Climate

class Vehicle:
    """Tesla vehicle class."""
    def __init__(self, api_client, vehicle):
        self._api_client = api_client
        self._vehicle = vehicle

        self.climate = Climate(self._api_client, vehicle['id'])

    def is_mobile_access_enabled(self):
        """Lets you know if the Mobile Access setting is enabled in the car."""
        return self._api_client.get('vehicles/{}/mobile_enabled'.format(self.id))

    def get_data(self):
        """
        A rollup of all the data_request endpoints plus vehicle configuration.

        Note: all *_range values are in miles, irrespective of GUI configuration.
        """
        return self._api_client.get('vehicles/{}/vehicle_data'.format(self.id))

    def get_state(self):
        """Returns the vehicle's physical state, such as which doors are open."""
        return self._api_client.get('vehicles/{}/data_request/vehicle_state'.format(self.id))

    def get_drive_state(self):
        """Returns the driving and position state of the vehicle."""
        return self._api_client.get('vehicles/{}/data_request/drive_state'.format(self.id))

    def get_gui_settings(self):
        """
        Returns various information about the GUI settings of the car,
        such as unit format and range display.
        """
        return self._api_client.get('vehicles/{}/data_request/gui_settings'.format(self.id))

    def wake_up(self):
        """
        Wakes up the car from a sleeping state.

        The API will return a response immediately, however it could take
        several seconds before the car is actually online and ready to receive
        other commands. One way to deal with this is to call this endpoint in
        a loop until the returned state says "online", with a timeout to give
        up. In some cases, the wake up can be slow, so consider using a
        timeout of atleast 30 seconds.
        """
        return self._api_client.post('vehicles/{}/wake_up'.format(self.id))

    def __dir__(self):
        """Include _vehicle keys in dir(), which are accessible with __getattr__()."""
        return super().__dir__() | self._vehicle.keys()

    def __getattr__(self, name):
        """Allow attribute access to _vehicle details."""
        try:
            return self._vehicle[name]
        except KeyError:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
