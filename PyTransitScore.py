import re,os,time,math,requests
import geopy.distance
from pyroutelib3 import Router
from scipy import spatial


def main():
    '''Time the whole process'''
    t0 = time.time()

    '''gather target, bus stop coords'''
    address_map, bus_stop_map, route_map, grid_map = parse_source_data(source_folder)

    '''Scrape BC transit website for data to rank routes by'''
##    city_urls = get_city_urls(url)
##    route_info = get_route_info(city_urls)

    '''get route rankings'''    
##    route_rankings = rank_routes(route_info)
##    normalized_ranking = normalize_ranking(route_rankings)
    
    '''Associate routes with stops to allow us to weight stops according to active frequency'''
##    route_bound_stops = associate_routes_with_stops(bus_stop_map,route_map)

    '''Get a list of all the coordinates for the element in the coordinate list'''
    bus_stop_with_amenity_ranks = get_bus_stop_amenity_rank(bus_stop_map)
    
    '''Dict with number of close stops'''
    #nearest_stop_map = get_closest_stop(address_map,ordered_bus_stop_with_amenity_ranks)

    '''Grid Rankings'''
    nearest_stop_map = get_closest_stop(grid_map, bus_stop_with_amenity_ranks)
        
    '''Hop around the nearest neighbors until a non zero amenity score is found'''
    distances_from_origin_to_amenities = get_distances_from_origin_to_amenities(nearest_stop_map, bus_stop_with_amenity_ranks)

    '''merge distances into a singular score to be mapped'''
    for origin in distances_from_origin_to_amenities:
        sum = 0
        for distances in distances_from_origin_to_amenities[origin]:
            for distance in distances:
                sum += float(distance.km)
                
        #print('%s | %s' % (origin,sum))#distances_from_origin_to_amenities[origin]))


    '''Print time taken'''
    print(time.time() - t0)


###WIP###
def associate_routes_with_stops(bus_stop_map,route_map):

    return route_bound_stops


def stop_hopper(stop_map,amenity_type,nearest_stop,index):

    bus_list = [x for x in stop_map]
    tree = spatial.KDTree(bus_list)
    
    def get_neighbor(kp):
        nearest_neighbor = tree.query([nearest_stop], k = kp)

        for neighbor in nearest_neighbor[1][0]:
            if stop_map[bus_list[int(neighbor)]][amenity_type] != math.inf:
                return neighbor
            else:
                amenity_not_found = 1
                
        if amenity_not_found:
            return(get_neighbor(kp+1))
            
    return(get_neighbor(300))
    
    
def get_distances_from_origin_to_amenities(nearest_stop_map,ordered_bus_stop_with_amenity_ranks):
    distances_from_origin_to_amenities = dict()
    for origin in nearest_stop_map:
        for amenity_type in range(len(AMENITIES)):
            nearest_stop = nearest_stop_map[origin][0]
            distance_to_nearest_stop = nearest_stop_map[origin][1]

            amenity_scores = ordered_bus_stop_with_amenity_ranks[nearest_stop]

            if amenity_scores[amenity_type] == math.inf:
                index = list(ordered_bus_stop_with_amenity_ranks).index(nearest_stop)
                nearest_stop_with_amenity = stop_hopper(ordered_bus_stop_with_amenity_ranks,amenity_type,nearest_stop, index)
                distance_between_nearest_stop_and_one_containing_amenity = geopy.distance.distance(nearest_stop, list(ordered_bus_stop_with_amenity_ranks)[nearest_stop_with_amenity])

                try:
                    distances_from_origin_to_amenities[origin].append([nearest_stop_map[origin][1],distance_between_nearest_stop_and_one_containing_amenity])
                except Exception:
                    distances_from_origin_to_amenities[origin] = [[nearest_stop_map[origin][1],distance_between_nearest_stop_and_one_containing_amenity]]
            else:
                try:
                    distances_from_origin_to_amenities[origin].append([nearest_stop_map[origin][1],amenity_scores[amenity_type]])
                except Exception:
                    distances_from_origin_to_amenities[origin] = [[nearest_stop_map[origin][1],amenity_scores[amenity_type]]]
                    
    return distances_from_origin_to_amenities


def get_bus_stop_amenity_rank(bus_stop_map):
    bus_stops_with_amenity_rank = dict()

    for amenity in AMENITIES:
        amenity_results = get_amenity_gps(amenity)
        for bus_stop in bus_stop_map:
            distance = math.inf
            
            for amenity_gps in amenity_results:
                straight_distance = geopy.distance.distance(amenity_gps, bus_stop_map[bus_stop])
                if straight_distance <= 0.8:
                    distance = min(straight_distance,distance) # calculate_distance(amenity_gps, bus_stop_map[bus_stop])
            try:
                bus_stops_with_amenity_rank[bus_stop_map[bus_stop]].append(distance)
            except Exception:
                bus_stops_with_amenity_rank[bus_stop_map[bus_stop]] = [distance]


    return bus_stops_with_amenity_rank


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


def get_amenity_gps(amenity):
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
    print(url)
    response=requests.get(url,verify=False)

    amenity_gps.extend(re.findall(r'coordinates\D+(.*?)]',str(response.content)))
    list_size = len(amenity_gps)
    return amenity_gps


def calculate_network_distance(cord1,cord2):
    router = Router("foot")
    start = router.findNode(cord1[0],cord1[1]) # Find start and end nodes
    end = router.findNode(cord2[0],cord2[1])
    
    # Find the route - a list of OSM nodes
    status, route = router.doRoute(start, end) 
    if status == 'success':
        # Get actual route coordinates
        routeLatLons = list(map(router.nodeLatLon, route))
        distance = calculate_route_distance(routeLatLons)
    return distance


def get_closest_stop(target_map, bus_stop_map):
    counter = 0
    
    nearest_stop_map = dict()
    
    broke_count = 0
    net_count= 0
    bus_list = [x for x in bus_stop_map]
    #print(bus_list)
    print('target_map',len(target_map))
    
    '''Sort by number of bus stops within 400m'''
    for target in target_map:
        distance_to_closest_stop = math.inf
        start_lat_lon = target_map[target]
        
        '''get nearest neighbor'''
        tree = spatial.KDTree(bus_list)
        
        closest_stop = bus_list[int(tree.query([target_map[target]])[1])]
        
        distance_to_closest_stop = geopy.distance.distance(start_lat_lon, closest_stop)
        
        '''check if nearest neighbor is within distance'''
        if distance_to_closest_stop < 0.6:
            try:
                distance = distance_to_closest_stop#calculate_network_distance(start_lat_lon, closest_stop)
            except Exception:
                broke_count+=1
                print('network broke at : %s | %s' % (counter,broke_count))
                continue
            
            nearest_stop_map[start_lat_lon] = [closest_stop, distance]

    return nearest_stop_map


def parse_source_data(source_folder):
    bus_stop_map = dict()
    target_map = dict()
    route_map = dict()
    grid_map = dict()
    
    with open(os.path.join(source_folder,bus_stop_file)) as bus_stop_points,\
         open(os.path.join(source_folder,address_file)) as address_points,\
         open(os.path.join(source_folder,route_file)) as route_points,\
         open(os.path.join(source_folder,grid_file)) as grid_points:
            
        address_lines = address_points.read()
        bus_stop_lines = bus_stop_points.readlines()
        route_lines = route_points.read()
        grid_lines = grid_points.readlines()
        '''Parse bus stop coords'''
        for bus_line in bus_stop_lines:
            if not bus_line.split(',')[3].isalpha():
                bus_lat = float(bus_line.split(',')[3])
                bus_lon = float(bus_line.split(',')[4])
                bus_stop_map[bus_line.split(',')[1]] = (bus_lat, bus_lon)
                
        '''Parse target street and gps coordinate'''
        raw_address_info = re.findall(r'FULL_ADD(.*?) ] } }',address_lines)#[0:100]

        '''parse address points'''
        for address_line in raw_address_info:
            street = address_line.split(':')[1].split(',')[0]
            raw_coords = address_line.split(':')[-1].replace('[','').strip().split(',')

            address_lat = float(raw_coords[1])
            address_lon = float(raw_coords[0])
            target_map[street] = (address_lat,address_lon)

        '''Parse Route Points'''
        route_coords = re.findall(r'<coordinates>(.*?)</coordinates>',route_lines)
        route_names = re.findall(r'Route: \d+',route_lines)
        for route_coord, route_name in zip(route_coords,route_names):
            try:    route_map[route_name].append(route_coord.strip('<coordinates>').split(' '))
            except Exception: route_map[route_name] = [route_coord.strip('<coordinates>').split(' ')]

        '''Parse Grid Points'''
        for grid_point in grid_lines:
            grid_latitude = grid_point.split(',')[1].strip()
            grid_longitude = grid_point.split(',')[0].strip()
            if not grid_latitude.isalpha():
##                print(grid_latitude)
                grid_map[(float(grid_latitude),float(grid_longitude))] = (float(grid_latitude),float(grid_longitude))
        
    return target_map, bus_stop_map,route_map, grid_map

    
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


def get_route_frequency(route_arrival_times):
    frequency_list = []

    for count, arrival_time in enumerate(route_arrival_times):
        hours = int(arrival_time.split(':')[0])
        minutes = int(arrival_time.split(':')[-1][:-3])

        if arrival_time[-2:]=='PM' and arrival_time[:2] != '12':
            hours+=12
        elif arrival_time[-2:]=='AM' and arrival_time[:2]=='12':
            hours+=12

        total_minutes = hours*60 + minutes
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
    
    source_folder = 'source_data'
    bus_stop_file = 'kel_busstops.csv'
    route_file = 'kel_routes.kml'
    address_file = 'Address_Points.geojson'
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

