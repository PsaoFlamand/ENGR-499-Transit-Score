import requests
import re
from geopy.geocoders import Nominatim
import time
import routingpy as rp

def main():
    city_urls = get_city_urls(url)
    route_info = get_route_info(city_urls)
    
    print(f'Input Address {input_address}')
    
    with open('results.txt','w') as result:    
        for route in route_info:
            for street in route_info[route]:
                route_duration, route_distance= get_route_distance_duration(input_address, f'{street}, Kelowna, Canada')
                average_route_frequency = get_route_frequency(route_info[route][street])
                result.write(str(f'\n {route} | {street} | {average_route_frequency} \n'))
                
                print(f'\n{route} | Bus Stop: {street} | Average Frequency {average_route_frequency} Minutes \nTravel Time by Foot: {route_duration} minutes | Distance: {route_distance} km \n')
                input()    

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
    for frequency in frequency_list:
        average_frequency += frequency
    average_frequency /= len(frequency_list)

    return round(average_frequency,3)

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
            with open('route_source_page.txt','w') as bug:
                bug.write(str(route_source_page))
            '''finds the pattern route=\d+ (\d+ = more than one digit), and isolates the digit by splitting at route= and taking the second half'''
            route_number = re.findall(r'route=\d+',route_url)[0]
            
            '''finds occurences of trip departs along with the chars contained in between the [...]. Will implement window search to make more robust'''
            trip_info = [x for x in re.findall(r"trip departs[-\#_:<>\/'\"\\a-zA-Z0-9\.\(\)\& ]+", str(route_source_page))]
            
            for trip in trip_info:
                try:
                    '''Same method as above'''
                    street = re.findall(r"'[-\#_:<>\/'\"\\a-zA-Z0-9\.\(\)\& ]+'",trip)[0].strip("'").strip('\\')
                    time = re.findall(r'\d+:\d+\s[A-Z][A-Z]',trip)[0]
                except IndexError:
                    '''In the case that the above string returned by the regex is not found, it is likely due to the regex pattern missing some anomalous chars. '''
                    '''Window search would fix this issue'''
                    print('\n\n\nERROR: Regular Expression fails on: %s \n %s \n\n\n' % (route_url, trip))
                    input()
                    
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


def get_location_by_address(address):
    """This function returns a location as raw from an address
    will repeat until success"""
    time.sleep(0.1)#Not sure if needed
    try:
        return app.geocode(address).raw
    except:
        return get_location_by_address(address)


def get_route_distance_duration(origin_address, destination_address):

    origin_location = get_location_by_address(origin_address)
    origin  = [float(origin_location["lon"]), float(origin_location["lat"])]

    destination_location = get_location_by_address(destination_address)
    destination  = [float(destination_location["lon"]), float(destination_location["lat"])]

    coordinates = [origin, destination]
    api = rp.ORS(api_key="5b3ce3597851110001cf6248993396cdbce943a293d5fcf34c10bcee")

    route = api.directions(locations=coordinates, profile='foot-walking')

    return round(route.duration/60,3), round(route.distance/1000,3)


if __name__ == '__main__':
    app = Nominatim(user_agent="tutorial")
    url = 'https://www.bctransit.com/'
    test_city = 'kelowna'
    input_address = '1018 Calder Court, Kelowna, Canada'
    main()
