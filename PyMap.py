import networkx as nx
import osmnx as ox
from geopy.geocoders import Nominatim
import time

app = Nominatim(user_agent="tutorial")

def get_location_by_address(address):
    """This function returns a location as raw from an address
    will repeat until success"""
    time.sleep(1)
    try:
        return app.geocode(address).raw
    except:
        return get_location_by_address(address)

origin_address = "1018 Calder Court, Kelowna, Canada"
origin_location = get_location_by_address(origin_address)
origin_latitude = origin_location["lat"]
origin_longitude = origin_location["lon"]
origin  = (float(origin_latitude), float(origin_longitude))

destination_address = "Okanagan College Exchange, Kelowna, Canada"
destination_location = get_location_by_address(destination_address)
destination_latitude = destination_location["lat"]
destination_longitude = destination_location["lon"]
destination  = (float(destination_latitude), float(destination_longitude))

ox.config(use_cache=True, log_console=True)

G = ox.graph_from_address('Okanagan College Exchange, Kelowna, Canada', dist=800, network_type='drive')

print(origin,destination)

origin_node = ox.get_nearest_node(G, origin)
destination_node = ox.get_nearest_node(G, destination)
route = nx.shortest_path(G, origin_node, destination_node)
fig, ax = ox.plot_graph_route(G, route, route_linewidth=6, node_size=0, bgcolor='k')

