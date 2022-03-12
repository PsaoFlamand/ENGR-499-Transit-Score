import re,os,time,math,requests, numpy
import geopy.distance
from pyroutelib3 import Router
from scipy import spatial


def main():
    '''Time the whole process'''
    t0 = time.time()

    '''gather target, bus stop coords'''
    address_coords, grid_coords, bus_stop_ids_coords, route_schedules = parse_source_data(source_folder)

    '''used to test a sub sample of map points'''
    #grid_coords = dict(list(grid_coords.items())[4900:5000])

    '''Get list of the closest amenity to each stop'''
    stop_coords_distance_to_amentity = get_stop_ids_distance_to_amentity(bus_stop_ids_coords)

    '''Group the nearest k stops to each origin point'''
    origins_coords_nearest_stops_coords = associate_origins_with_nearest_stops(grid_coords, stop_coords_distance_to_amentity)

    '''Find the optimal stop to use from the nearest k stops'''
    origin_to_amenities_travel_time = get_origin_to_amenities_travel_time(origins_coords_nearest_stops_coords, stop_coords_distance_to_amentity, route_schedules, bus_stop_ids_coords)

    ### Code below will be recreated with the formula Chris finds ###
    '''merge distances into a singular score to be mapped'''
    with open('result.txt','w') as result:
        for origin in origin_to_amenities_travel_time:
            sum = 0
            for travel_times in origin_to_amenities_travel_time[origin]:
                for travel_time in travel_times:
                    if travel_time == math.inf:
                        sum *= 2
                    else:
                        sum += float(travel_time)
                    
            #print('%s, %s' % (str(origin).replace('(','').replace(')',''),sum))
            result.write('%s, %s\n' % (str(origin).replace('(','').replace(')',''),sum))
    ###     ####

    '''Print total process duration'''
    print(time.time() - t0)

def parse_source_data(source_folder):
    bus_stop_ids_coords = dict()
    address_coords = dict()
    grid_coords = dict()
    route_schedules = dict()
    
    source_folder = r'C:\Users\p\Documents\PyTransit\source_folder'
    bus_stop_file = 'stops.txt'
    stop_times_file = 'stop_times.txt'
    grid_file = 'city_of_kelowna_grid_coordinates.txt'

    with open(os.path.join(source_folder,bus_stop_file)) as bus_stops,\
         open(os.path.join(source_folder,grid_file)) as grids,\
         open(os.path.join(source_folder,stop_times_file)) as route_schedule:
            
        '''Parse bus stop coords'''
        for bus_line in bus_stops:
            bus_stop_id = bus_line.split(',')[0]
            
            try:    int(bus_stop_id)
            except: continue
                
            bus_lat = float(bus_line.split(',')[4])
            bus_lon = float(bus_line.split(',')[5])
            
            bus_stop_ids_coords[bus_stop_id] = (bus_lat, bus_lon)
                
        '''Parse Bus route Schedule'''
        for schedule_line in route_schedule:

            trip_id = schedule_line.split(',')[0]
            arrival_time = schedule_line.split(',')[1]
            departure_time = schedule_line.split(',')[2]
            stop_id = schedule_line.split(',')[3]
            stop_order = schedule_line.split(',')[4]
            
            try:    int(trip_id)
            except: continue
            
            if trip_id in route_schedules:
                route_schedules[trip_id].append([arrival_time,departure_time,stop_id,stop_order])
            else:
                route_schedules[trip_id] = [[arrival_time,departure_time,stop_id,stop_order]]

        '''Parse Grid Points'''
        for grid_point in grids:
            grid_latitude = grid_point.split(',')[1].strip()
            grid_longitude = grid_point.split(',')[0].strip()
            if not grid_latitude.isalpha():
                grid_coords[(float(grid_latitude),float(grid_longitude))] = (float(grid_latitude),float(grid_longitude))
        
    return address_coords, grid_coords, bus_stop_ids_coords, route_schedules
    

def get_stop_ids_distance_to_amentity(bus_stop_ids_coords):
    stop_coords_distance_to_amentity = dict()
    '''Scraping setup'''
    url = 'https://www.bctransit.com/'
    test_city = 'kelowna'

    city = 'Kelowna'
    AMENITIES = ['restaurants','gyms','groceries','banks']
        
    for amenity in AMENITIES:
        amenity_info = get_amenity_info(amenity,city)
        
        for stop_id in bus_stop_ids_coords:
            stop_coords = bus_stop_ids_coords[stop_id]
            distance_from_stop_to_amenity = math.inf
            
            for amenity_coords in amenity_info:
                straight_distance = geopy.distance.distance(amenity_coords, stop_coords)
                if straight_distance <= 0.8:
                    distance_from_stop_to_amenity = min(straight_distance,distance_from_stop_to_amenity) # calculate_network_distance(amenity_gps, bus_stop_ids_coords[bus_stop])

            if stop_coords in stop_coords_distance_to_amentity:
                stop_coords_distance_to_amentity[stop_coords].append(distance_from_stop_to_amenity)
            else:
                stop_coords_distance_to_amentity[stop_coords] = [distance_from_stop_to_amenity]

    return stop_coords_distance_to_amentity


def associate_origins_with_nearest_stops(origins, stop_coords_distance_to_amentity):
    origins_coords_nearest_stops_coords = dict()
    stop_coords = [x for x in stop_coords_distance_to_amentity]

    '''Sort by number of bus stops within 400m'''
    for origin in origins:
        origin_to_nearest_stop_distance = math.inf
        origin_coords = origins[origin]
        
        '''get nearest neighbor'''
        tree = spatial.KDTree(stop_coords)
        nearest_stops_coords = [stop_coords[int(index)] for index in tree.query([origin_coords], k = 3)[1][0]]############### Fix k?

        #nearest_stops_coords = [stop_coords_distance_to_amentity[int(tree.query([origin_coords], k = 1)[1])]]############### Fix k?

        if not nearest_stops_coords:
            print('%s has no near neighbors'%origin_coords)
        
        for nearest_stop_coords in nearest_stops_coords:
            origin_to_nearest_stop_straight_distance = geopy.distance.distance(origin_coords, nearest_stop_coords)
            #print('straight_distance_to_nearest_stop',origin_to_nearest_stop_straight_distance)
            '''Check if nearest neighbor is within distance'''
            if origin_to_nearest_stop_straight_distance < 0.6:
                '''Exception in the case where there is no route path found between the two points using network distance'''
                try:
                    distance = origin_to_nearest_stop_straight_distance # calculate_network_distance(origin_coords, closest_stop)
                except Exception as e:
                    distance = origin_to_nearest_stop_straight_distance
                    print('Exception in network distance calculation: %s \n using straight line distance of %s'% (e,distance))
                    pass
                
                if origin_coords in origins_coords_nearest_stops_coords:
                    origins_coords_nearest_stops_coords[origin_coords].append([nearest_stop_coords, distance])
                else:
                    origins_coords_nearest_stops_coords[origin_coords] = [[nearest_stop_coords, distance]]

    return origins_coords_nearest_stops_coords


def get_origin_to_amenities_travel_time(origins_coords_nearest_stops_coords, stop_coords_distance_to_amentity, route_schedules, bus_stop_ids_coords):
    origin_to_amenities_travel_time = dict()
    test_city = 'kelowna'
    bus_stop_coords_ids = dict()

    for bus_stop in bus_stop_ids_coords:
        bus_stop_coords_ids[bus_stop_ids_coords[bus_stop]] = bus_stop
    
    city = 'Kelowna'
    AMENITIES = ['restaurants','gyms','groceries','banks']
    connectivity_memory = dict()
    for count,origin_coords in enumerate(origins_coords_nearest_stops_coords):
        print('%s/%s' % (count,len(origins_coords_nearest_stops_coords)))
        for amenity_index in range(len(AMENITIES)):
            optimal_total_travel_time_to_amenity = math.inf
            optimal_nearest_stop = None
            for nearest_stops_coords_distances in origins_coords_nearest_stops_coords[origin_coords]:#Loop through all nearest stops for a given origin point
                '''Result Variable'''
                optimal_travel_time_between_stops = math.inf
                optimal_candidate_stop_id = None
                
                '''Get nearest stop info'''
                nearest_stop_coords = nearest_stops_coords_distances[0]
                origin_to_nearest_stop_distance = nearest_stops_coords_distances[1]
                nearest_stop_id = bus_stop_coords_ids[nearest_stop_coords]
                nearest_stop_to_amenity_distance = stop_coords_distance_to_amentity[nearest_stop_coords][amenity_index]
                
                if nearest_stop_to_amenity_distance == math.inf:#Nearest stop has no access to amenity, check if amenity is accessible trough routes
                    '''Nearest stop index relative to distance to amentity dict'''
                    nearest_stop_index = list(stop_coords_distance_to_amentity).index(nearest_stop_coords)
                    
                    '''Search for nearest stop with amenity closest to the original nearest stop.'''
                    '''We are assuing that the nearest stops are mostly going to be on that stops route network'''
                    '''We will then verify that assumption in a later function'''
                    candidate_stops_coords = stop_hopper(stop_coords_distance_to_amentity,amenity_index,nearest_stop_coords)

                    candidate_stops_ids = [bus_stop_coords_ids[candidate_stop_coords] for candidate_stop_coords in candidate_stops_coords]
 
                    '''Narrow down the candidate list to the best candidate'''                   
                    for candidate_stop_id in candidate_stops_ids:
                        if '%s-%s'%(nearest_stop_id,candidate_stop_id) not in connectivity_memory:
                            connectivity_memory = check_connectivity_between_stops(nearest_stop_id, candidate_stop_id, route_schedules, bus_stop_ids_coords,connectivity_memory)
                            travel_time_between_stops = connectivity_memory['%s-%s'%(nearest_stop_id,candidate_stop_id)]
                        else:
                            travel_time_between_stops = connectivity_memory['%s-%s'%(nearest_stop_id,candidate_stop_id)]
                            
                        '''In the case we have a successful connect, we will still test the rest to ensure we have the best candidate'''
                        if travel_time_between_stops > 0 and travel_time_between_stops != False:
                            if travel_time_between_stops < optimal_travel_time_between_stops:
                                optimal_travel_time_between_stops = travel_time_between_stops
                                optimal_candidate_stop_id = candidate_stop_id
                                break
                    if not optimal_candidate_stop_id:
                        continue
                    '''Distance from stop with amenity to its associated amenity'''
                    origin_to_nearest_stop_travel_time = float(origin_to_nearest_stop_distance.km)*1000 / 40
                    
                    nearest_stop_to_optimal_candidate_stop_travel_time = optimal_travel_time_between_stops
                    
                    optimal_candiate_stop_to_amentiy_distance = stop_coords_distance_to_amentity[bus_stop_ids_coords[optimal_candidate_stop_id]][amenity_index]
                    optimal_candiate_stop_to_amentiy_travel_time = float(optimal_candiate_stop_to_amentiy_distance.km)*1000 / 40
                        
                    total_travel_time_to_amenity = origin_to_nearest_stop_travel_time + \
                                                   nearest_stop_to_optimal_candidate_stop_travel_time + \
                                                   optimal_candiate_stop_to_amentiy_travel_time
                    
                    if optimal_travel_time_between_stops < 0 or optimal_travel_time_between_stops == False:
                        '''will point out which areas have no access to amenities'''
                        optimal_total_travel_time_to_amenity = math.inf
                    else:
##                        print('total_travel_time_to_amenity',total_travel_time_to_amenity)
##                        print('optimal_total_travel_time_to_amenity',optimal_total_travel_time_to_amenity)
                        if total_travel_time_to_amenity < optimal_total_travel_time_to_amenity:
                            optimal_total_travel_time_to_amenity = total_travel_time_to_amenity
                            optimal_nearest_stop = nearest_stop_id
                        
                else: # Case where the nearest stop has an amenity
                    total_travel_time_to_amenity = float(nearest_stop_to_amenity_distance.km)*1000 / 40
##                    print('total_travel_time_to_amenity',total_travel_time_to_amenity)
##                    print('optimal_total_travel_time_to_amenity',optimal_total_travel_time_to_amenity)
                    if total_travel_time_to_amenity < optimal_total_travel_time_to_amenity:
                        optimal_total_travel_time_to_amenity = total_travel_time_to_amenity
                        optimal_nearest_stop = nearest_stop_id
                        
            if optimal_total_travel_time_to_amenity == math.inf:
                print('a suitable transfer was not found for %s | %s | %s' % (origins_coords_nearest_stops_coords[origin_coords],candidate_stops_ids, bus_stop_coords_ids[origins_coords_nearest_stops_coords[origin_coords][0][0]]))
                print(AMENITIES[amenity_index])
                
            if origin_coords in origin_to_amenities_travel_time:
                origin_to_amenities_travel_time[origin_coords].append([optimal_total_travel_time_to_amenity])
            else:
                origin_to_amenities_travel_time[origin_coords] = [[optimal_total_travel_time_to_amenity]]
                    
    #print('origin_to_amenities_travel_time',origin_to_amenities_travel_time)
    return origin_to_amenities_travel_time


def stop_hopper(stop_coords_distance_to_amentity, amenity_index, nearest_stop_coords):
    candidate_stops_coords = []
    stop_coords = [x for x in stop_coords_distance_to_amentity]
    tree = spatial.KDTree(stop_coords)
    
    def get_neighbor(kp):
        nearest_neighbors_coords = [stop_coords[int(index)] for index in tree.query([nearest_stop_coords], k = kp)[1][0]]
        for neighbor_coords in nearest_neighbors_coords:
            if stop_coords_distance_to_amentity[neighbor_coords][amenity_index] != math.inf: # stop has access to amenity
                candidate_stops_coords.append(neighbor_coords)

        if candidate_stops_coords:
            return candidate_stops_coords
        else:
            return(get_neighbor(kp+1))
            
    return(get_neighbor(300))


def get_travel_time_between_stops(origin_stop_times, stop1, stop2):
    travel_times = list()
    for stop_info_list in origin_stop_times:
        arrival_time = ''
        departure_time = ''
        for stop_info in stop_info_list:
            stop_id = stop_info[2]
            if stop_id == stop1:
                departure_time = stop_info[1]
            elif stop_id == stop2:
                arrival_time = stop_info[0]
                
        if not arrival_time or not departure_time:
            continue
        arrival_hours = int(arrival_time.split(':')[0])
        arrival_minutes = int(arrival_time.split(':')[1])

        departure_hours = int(departure_time.split(':')[0])
        departure_minutes = int(departure_time.split(':')[1])
        
        total_departure_minutes = departure_hours*60 + departure_minutes
        total_arrival_minutes = arrival_hours*60 + arrival_minutes

        travel_times.append(total_arrival_minutes - total_departure_minutes)

    if travel_times:
        return sum(travel_times) / len(travel_times)
    else:
        return math.inf


def get_transit_schedule(target_stop_id, route_schedules):
    stop_ids_in_route = list()        
    reduced_result = list()
    

    for stop_times in route_schedules:
        for stop_time in route_schedules[stop_times]:
            stop_id = stop_time[2]
            if int(stop_id) == int(target_stop_id):
                if route_schedules[stop_times] not in reduced_result:
                    reduced_result.append(route_schedules[stop_times])
                    for stop in route_schedules[stop_times]:
                        if int(stop[2]) not in stop_ids_in_route:
                            stop_ids_in_route.append(int(stop[2]))
                        
    sorted_reduced_stop_times = sorted(reduced_result, key = lambda x: x[0])
    sorted_stop_ids_in_route = sorted(stop_ids_in_route)
    #print('sorted_reduced_stop_times',sorted_reduced_stop_times)
    #print('sorted_stop_ids_in_route',sorted_stop_ids_in_route)

    return sorted_reduced_stop_times, sorted_stop_ids_in_route

    
def check_connectivity_between_stops(stop1,stop2, route_schedules, bus_stop_ids_coords,connectivity_memory):
    stop_path = list()
    headway_memory = dict()
    
    origin_stop_times, the_original_route_stop_id_list = get_transit_schedule(stop1, route_schedules)
    destination_stop_times, the_destination_route_stop_id_list = get_transit_schedule(stop2, route_schedules)

##    print('origin_stop_times',origin_stop_times)
##    print('destination_stop_times',destination_stop_times)
    arrival_times_for_origin_stop = []

    
    '''Get the avereage wait time as 1/2 of the arrival frequency'''
##    print('origin_stop_times',origin_stop_times)
    if stop1 not in headway_memory:
        
        for origin_stop_time in origin_stop_times:
            for stop_time in origin_stop_time:
    ##            print('stop1',stop1)
    ##            print('origin_stop_time[2]',stop_time[2])
                if str(stop1) == stop_time[2]:
                    #print('stop_time',stop_time)
                    arrival_time = stop_time[0]
                    arrival_hours = int(arrival_time.split(':')[0])
                    arrival_minutes = int(arrival_time.split(':')[1])
                    total_arrival_minutes = arrival_hours*60 + arrival_minutes

                    arrival_times_for_origin_stop.append(total_arrival_minutes)
                    
        headway = sum(numpy.diff(numpy.array(sorted(arrival_times_for_origin_stop))))/len(arrival_times_for_origin_stop)
    else:
        headway = headway_memory[stop1]
    if headway < 10:
        waiting_time = headway/2
        print('headway',headway,stop1,stop2)
    else:
        waiting_time = 5
        
    '''check if the two routes are on the same route'''
    if int(stop2) in the_original_route_stop_id_list and int(stop1) in the_original_route_stop_id_list:    
        average_travel_time = get_travel_time_between_stops(origin_stop_times, stop1, stop2)
        
        connectivity_memory['%s-%s'%(stop1,stop2)] = average_travel_time
        return connectivity_memory
    
    '''Check if there is one degree of transferability between stops'''
    for a_destination_stop_id in the_destination_route_stop_id_list:
        for a_origin_stop_id in the_original_route_stop_id_list:

            a_destination_stop_id = str(a_destination_stop_id)
            a_origin_stop_id = str(a_origin_stop_id)
            
            the_distance_between_stops_is = geopy.distance.distance(bus_stop_ids_coords[a_destination_stop_id], bus_stop_ids_coords[a_origin_stop_id])
            
            if the_distance_between_stops_is < 0.6:
                walking_time_to_transfer = float(the_distance_between_stops_is.km)*1000 / 40
                
                average_travel_time1 = get_travel_time_between_stops(origin_stop_times, stop1, a_origin_stop_id)
                average_travel_time2 = get_travel_time_between_stops(destination_stop_times, a_destination_stop_id, stop2)
                
                average_travel_time = waiting_time + average_travel_time1 + walking_time_to_transfer + average_travel_time2

                connectivity_memory['%s-%s'%(stop1,stop2)] = average_travel_time

                return connectivity_memory
            
    #print('they were not found to be transferable in one degree', stop1, stop2)
    connectivity_memory['%s-%s'%(stop1,stop2)] = False
    return connectivity_memory
    


def scale_score(score):
    
    if score <= 0.100:
        scaled_score = 1.6                        
    elif score <= 0.200:
        scaled_score = 1.4
    elif score <= 0.300:
        scaled_score = 1.2
    elif score <= 0.400:
        scaled_score = 1
    elif score <= 0.500:
        scaled_score = 0.8
    elif score <= 0.600:
        scaled_score = 0.6
    elif score <= 0.700:
        scaled_score = 0.4
    elif score <= 0.800:
        scaled_score = 0.2
                    
    return scaled_score


def get_amenity_info(amenity,city):
    amenity_gps = []
    list_size = 0
    prev_list_size = -1
    page_num = 0

    requests.packages.urllib3.disable_warnings()
    requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'
    try:
        requests.packages.urllib3.contrib.pyopenssl.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'
    except AttributeError:
        # no pyopenssl support used / needed / available
        pass

##    while list_size != prev_list_size:
##        if amenity_gps:
##            prev_list_size = list_size
    page_num +=1

    url = 'https://www.yellowpages.ca/search/si/%s/%s/%s+BC/rci-%s%%2C+BC'%(page_num,amenity,city,city)
##    print(url)
    response=requests.get(url,verify=False)

    amenity_gps.extend(re.findall(r'coordinates\D+(.*?)]',str(response.content)))
    list_size = len(amenity_gps)
    return amenity_gps


def calculate_network_distance(cord1,cord2):
    router = Router("foot")
    '''Find start and end nodes'''
    start = router.findNode(cord1[0],cord1[1])
    end = router.findNode(cord2[0],cord2[1])
    
    '''Find the route - a list of OSM nodes'''
    status, route = router.doRoute(start, end)
    
    if status == 'success':
        # Get actual route coordinates
        routeLatLons = list(map(router.nodeLatLon, route))
        distance = calculate_route_distance(routeLatLons)
        
    return distance






    
def rank_routes(route_info):
    route_ranking = dict()
   
    for route in route_info:
        total_average = 0

        for street in route_info[route]:
            average_route_frequency = get_route_frequency(route_info[route][street])
            if average_route_frequency == 0:
                average_route_frequency = 999
            total_average += average_route_frequency

        route_ranking[route] = total_average / len(route_info[route])

    return route_ranking


def get_city_urls(url):
    '''grab the source page from the root transit website in order to compile a list of all available cities for rating'''
    source_page = str(requests.get(url).content)

    '''Extract the urls related to each city from the source page'''
    
    '''Uses a pattern search that will look for any occurences of community-url followed by anything but a space (\S+) followed by any number of spaces (\s+) followed by anything but spaces (\S+)'''
    '''Proceeds to loop through the list of patterns found and parses them using splits'''
    '''Sample output from the regular expression below: community-url" href="/100-mile-house/home">100'''
    '''We then parse out the url we are interested in by splitting the string at href=" and taking only the right hand side ([-1] last element in the list) sample stage output: /100-mile-house/home">100'''
    '''Now to isolate the url, we split by "> and take only the left hand side ([0] first element). Final output: /100-mile-house/home'''
    '''Lastly, to get rid of any duplicates in the list, we turn it into a set, and then back into a list. This is because sets by definition only contain unique values'''
    city_urls = list(set([x for x in re.findall(r'href=\"(.*?)\"',source_page) if 'home' in x]))

    return city_urls


def get_route_info(city_urls):
    route_map = dict()
    for city_url in city_urls:
        '''checks if the city url contains the string that we specified below as "kamloops". If its not found, that ciry url is skipped'''
        if test_city not in city_url:
            continue
            
        '''Switch the url from "home" to "schedules-and-maps" be replacement. we use [1:] to exclude the extra / at the beginning of the string'''
        refined_city_url = city_url.replace('home','schedules-and-maps')[1:]
        
        '''concatenate the root bc transit url with the city url extension'''
        city_url = '%s%s'%(url,refined_city_url)

        '''grab the source code from the city url'''
        city_source_page = requests.get(city_url).content

        '''Same method as before'''
        route_urls = [x for x in re.findall(r'data-route=\"\d+\"\s+href=\"(.*?)\"',str(city_source_page))]

        for route_url in route_urls:
            '''Same method as before'''
            route_url = '%s%s'%(url,route_url[1:])
            route_source_page = requests.get(route_url).content
           
            '''finds the pattern route=\d+ (\d+ = more than one digit), and isolates the digit by splitting at route= and taking the second half'''
            route_number = re.findall(r'route=\d+',route_url)[0]
            
            '''finds occurences of trip departs along with the chars contained in between the [...]. '''
            trip_info = [x for x in re.findall(r"trip departs(.*?)<span class", str(route_source_page))]
            for trip in trip_info:
                '''Same method as above'''
                street = re.search(r"'(.*?)'",trip).group(1)
                time = re.findall(r'\d+:\d+\s[A-Z][A-Z]',trip)[0]
                    
                '''Builds a list in a dictionary so that we can store the street and time of arrival for each bus route'''
                '''we use the try except block in because we can't know wether or not the list has been preassigned or not, so we assume it exists. '''
                '''If it doesnt exist, in the except block we create a list with the initial value we were going to append'''

                try:
                    route_map[route_number][street].append(time)
                except Exception:
                    try:
                        route_map[route_number][street] = [time]
                    except Exception:
                        route_map[route_number] = {street: [time]}
    return route_map


def convert_time_to_minutes(raw_time):
    hours = int(raw_time.split(':')[0])
    minutes = int(raw_time.split(':')[-1][:-3])

    if raw_time[-2:]=='PM' and raw_time[:2] != '12':
        hours+=12
    elif raw_time[-2:]=='AM' and raw_time[:2]=='12':
        hours+=12

    total_minutes = hours*60 + minutes

    return total_minutes


def get_route_frequency(route_arrival_times):
    frequency_list = []

    for count, arrival_time in enumerate(route_arrival_times):

        total_minutes = convert_time_to_minutes(arrival_time)
        
        if count>0:
            if total_minutes-prev_total_minutes > 0:
                frequency_list.append(total_minutes-prev_total_minutes)
                
        prev_arrival_time = arrival_time
        prev_hours = hours
        prev_minutes = minutes
        prev_total_minutes = total_minutes
        
    average_frequency = 0
    
    if frequency_list:
        for frequency in frequency_list:
            average_frequency += frequency
        average_frequency /= len(frequency_list)
        
    return round(average_frequency,3)


def normalize_ranking(dict_in):
    normalized_ranking = dict()

    xmin = min(dict_in.values())
    xmax = max(dict_in.values())
        
    for xi in dict_in:
        normalized_ranking[xi] = (dict_in[xi] - xmin) / (xmax - xmin)

    normalized_ranking = dict(sorted(normalized_ranking.items(), key=lambda x: x[1]))
    return normalized_ranking


def calculate_route_distance(positions):
    '''Code retrieved from https://stackoverflow.com/questions/41238665/calculating-geographic-distance-between-a-list-of-coordinates-lat-lng'''
    results = []
    for i in range(1, len(positions)):
        loc1 = positions[i - 1]
        loc2 = positions[i]

        lat1 = loc1[0]
        lng1 = loc1[1]

        lat2 = loc2[0]
        lng2 = loc2[1]

        degreesToRadians = (math.pi / 180)
        latrad1 = lat1 * degreesToRadians
        latrad2 = lat2 * degreesToRadians
        dlat = (lat2 - lat1) * degreesToRadians
        dlng = (lng2 - lng1) * degreesToRadians

        a = math.sin(dlat / 2) * math.sin(dlat / 2) + math.cos(latrad1) * \
        math.cos(latrad2) * math.sin(dlng / 2) * math.sin(dlng / 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        r = 6371000

        results.append(r * c)

    return sum(results)  # Converting from m to km


if __name__ == '__main__':
    '''data setup'''
    
    source_folder = r'C:\Users\p\Documents\PyTransit\source_folder'
    bus_stop_file = 'stops.txt'
    route_file = 'kel_routes.kml'
    stop_times_file = 'stop_times.txt'
    address_file = 'address_points.geojson'
    grid_file = 'city_of_kelowna_grid_coordinates.txt'

    '''Scraping setup'''
    url = 'https://www.bctransit.com/'
    test_city = 'kelowna'

    city = 'Kelowna'
    AMENITIES = ['restaurants','gyms','groceries','banks']


    range_dict = {(50.019847274822695, -119.37532151949802) : [[1200,2700,0],[5210,8440,25]],
                  (49.91729642268884, -119.33119246289769)  : [[11500,10000,0]],
                  (49.82303160146931, -119.41015669675217)  : [[6000,4000,50]],}
    
    main()

