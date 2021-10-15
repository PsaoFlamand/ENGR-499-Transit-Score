import geopy.distance
import re
import time
import os
import requests


def main():
    '''Time the whole process'''
    t0 = time.time()
    
    '''Scrape BC transit website for data to rank routes by'''
    city_urls = get_city_urls(url)
    route_info = get_route_info(city_urls)

    '''gather address, bus stop coords'''
    address_map, bus_stop_map, route_map = parse_source_data(source_folder)

    '''Associate routes with stops to allow us to weight stops according to active frequency'''
    route_bound_stops = associate_routes_with_stops(bus_stop_map,route_map)
    
    '''get route rankings'''
    route_rankings = rank_routes(route_info)
    normalized_ranking = normalize_ranking(route_rankings)
    print(normalized_ranking)

    ''', and dict with number of close stops'''
    address_rankings = rank_addresses(address_map,bus_stop_map)

    print(time.time() - t0)

###WIP###
def associate_routes_with_stops(bus_stop_map,route_map):
    route_bound_stops=0
    return route_bound_stops


def rank_addresses(address_map, bus_stop_map):
    address_rankings = dict()

    '''Sort by number of bus stops within 400m'''        
    for address in address_map:
        stops_within_range = 0
        for bus_stop in bus_stop_map:
            stop_distance = geopy.distance.distance(address_map[address], bus_stop_map[bus_stop])
            
            if stop_distance < 0.4:
                stops_within_range += 1
            elif stop_distance < 0.8:
                stops_within_range += 0.5
                
        address_rankings[address] = stops_within_range
    
    to_be_ranked = dict(sorted(address_rankings.items(), key=lambda x:x[1]))
    
    return address_rankings

###

def parse_source_data(source_folder):
    bus_stop_map = dict()
    address_map = dict()
    route_map = dict()
    
    with open(os.path.join(source_folder,bus_stop_file)) as bus_stop_points,\
         open(os.path.join(source_folder,address_file)) as address_points,\
         open(os.path.join(source_folder,route_file)) as route_points:
             
        address_lines = address_points.read()
        bus_stop_lines = bus_stop_points.readlines()
        route_lines = route_points.read()
        
        '''Parse bus stop coords'''
        for bus_line in bus_stop_lines:
            if not bus_line.split(',')[3].isalpha():
                bus_lat = bus_line.split(',')[3]
                bus_lon = bus_line.split(',')[4]
                bus_stop_map[bus_line.split(',')[1]] = (bus_lat, bus_lon)
                
        '''Parse address street and gps coordinate'''
        raw_address_info = re.findall(r'FULL_ADD(.*?) ] } }',address_lines)[0:100]

        for address_line in raw_address_info:
            street = address_line.split(':')[1].split(',')[0]
            raw_coords = address_line.split(':')[-1].replace('[','').strip().split(',')

            address_lat = float(raw_coords[1])
            address_lon = float(raw_coords[0])
            
            address_map[street] = (address_lat,address_lon)

        route_coords = re.findall(r'<coordinates>(.*?)</coordinates>',route_lines)
        route_names = re.findall(r'Route: \d+',route_lines)
        for route_coord, route_name in zip(route_coords,route_names):
            try:    route_map[route_name].append(route_coord.strip('<coordinates>').split(' '))
            except: route_map[route_name] = [route_coord.strip('<coordinates>').split(' ')]
            
            
    return address_map, bus_stop_map,route_map



def normalize_ranking(dict_in):
    normalized_ranking = dict()

    xmin = min(dict_in.values())
    xmax = max(dict_in.values())
        
    for xi in dict_in:
        normalized_ranking[xi] = (dict_in[xi] - xmin) / (xmax - xmin)

    normalized_ranking = dict(sorted(normalized_ranking.items(), key=lambda x: x[1]))
    return normalized_ranking

    
def rank_routes(route_info):
    route_ranking = dict()
   
    for route in route_info:
        total_average = 0

        for street in route_info[route]:
            average_route_frequency = get_route_frequency(route_info[route][street])
            if average_route_frequency == 0:
                average_route_frequency=999
            total_average += average_route_frequency

        route_ranking[route] = total_average / len(route_info[route])

    return route_ranking


def get_city_urls(url):
    '''grab the source page from the root transit website in order to compile a list of all available cities for rating'''
    source_page = requests.get(url).content
    
    '''Extract the urls related to each city from the source page'''
    
    '''Uses a pattern search that will look for any occurences of community-url followed by anything but a space (\S+) followed by any number of spaces (\s+) followed by anything but spaces (\S+)'''
    '''Proceeds to loop through the list of patterns found and parses them using splits'''
    '''Sample output from the regular expression below: community-url" href="/100-mile-house/home">100'''
    '''We then parse out the url we are interested in by splitting the string at href=" and taking only the right hand side ([-1] last element in the list) sample stage output: /100-mile-house/home">100'''
    '''Now to isolate the url, we split by "> and take only the left hand side ([0] first element). Final output: /100-mile-house/home'''
    '''Lastly, to get rid of any duplicates in the list, we turn it into a set, and then back into a list. This is because sets by definition only contain unique values'''

    city_urls = list(set([x.split('href="')[-1].split('">')[0] for x in re.findall(r'href="\/\S+',str(source_page)) if 'home' in x]))

    return city_urls

        
def get_route_info(city_urls):
    route_map = {}
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
        route_urls = [x.split('href="')[-1].split('">')[0] for x in re.findall(r'data-route=\"\d+\"\s+\S+',str(city_source_page))]
        
        for route_url in route_urls:
            '''Same method as before'''
            route_url = '%s%s'%(url,route_url[1:])
            route_source_page = requests.get(route_url).content
            
            '''finds the pattern route=\d+ (\d+ = more than one digit), and isolates the digit by splitting at route= and taking the second half'''
            route_number = re.findall(r'route=\d+',route_url)[0]
            
            '''finds occurences of trip departs along with the chars contained in between the [...]. Will implement window search to make more robust ###Fixed with a better regex'''
            trip_info = [x for x in re.findall(r"trip departs(.*?)<span class", str(route_source_page))]
            
            for trip in trip_info:
                '''Same method as above'''
                street = re.findall(r"'(.*?)'",trip)[0].strip("'").strip('\\')
                time = re.findall(r'\d+:\d+\s[A-Z][A-Z]',trip)[0]
                    
                '''Builds a list in a dictionary so that we can store the street and time of arrival for each bus route'''
                '''we use the try except block in because we can't know wether or not the list has been preassigned or not, so we assume it exists. '''
                '''If it doesnt exist, in the except block we create a list with the initial value we were going to append'''
                
                try:
                    route_map[route_number][street].append(time)
                except:
                    try:
                        route_map[route_number][street] = [time]
                    except:
                        route_map[route_number] = {street: [time]}
    return route_map


def get_route_frequency(route_arrival_times):
    frequency_list = []
    for count, arrival_time in enumerate(route_arrival_times):
        hours = int(arrival_time.split(':')[0])
        minutes = int(arrival_time.split(':')[-1][:-3])

        if arrival_time[-2:]=='PM' and arrival_time[:2]!='12':
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


if __name__ == '__main__':
    '''data setup'''
    source_folder = 'source_data'
    bus_stop_file = 'kel_busstops.csv'
    route_file = 'kel_routes.kml'
    address_file = 'Address_Points.geojson'
    
    '''Scraping setup'''
    url = 'https://www.bctransit.com/'
    test_city = 'kelowna'
    
    main()

