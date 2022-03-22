import re,os,time,math,requests, numpy
import geopy.distance
from pyroutelib3 import Router
from scipy import spatial

USE_NETWORK_DISTANCE = True
NETWORK_DISTANCE_PRINT_DEBUG = True

NETWORK_CALCULATION_FAILURES = 0
TOTAL_NETWORK_CALCULATIONS = 0

def main():
    '''Time the whole process'''
    t0 = time.time()

    '''gather target, bus stop coords'''
    address_coords, grid_coords, bus_stop_ids_coords, route_schedules,amenity_data,km_grid_coords = parse_source_data(source_folder)

    amenity_data = get_employment_centres(km_grid_coords, amenity_data)
    amenity_data = dict(sorted(amenity_data.items(), key = lambda x:x[0]))
    '''used to test a sub sample of map points'''
    #grid_coords = dict(list(grid_coords.items())[19150:])

    '''Get list of the closest amenity to each stop'''
    stop_coords_distance_to_amentity = get_stop_ids_distance_to_amentity(bus_stop_ids_coords,amenity_data)
    
    '''Group the nearest k stops to each origin point'''
    origins_coords_nearest_stops_coords = associate_origins_with_nearest_stops(grid_coords, stop_coords_distance_to_amentity)#( { (49.89152145, -119.497782) : (49.89152145, -119.497782) }, stop_coords_distance_to_amentity)#

    '''Check to see if there is are amenities within walking distance'''
    partial_origin_to_amenities_travel_time = associate_origins_with_nearest_amenity(origins_coords_nearest_stops_coords, amenity_data)#({ (49.89152145, -119.497782) : (49.89152145, -119.497782) }, amenity_data)#


    '''Find the optimal stop to use from the nearest k stops'''
    origin_to_amenities_travel_time = get_origin_to_amenities_travel_time(origins_coords_nearest_stops_coords, stop_coords_distance_to_amentity, route_schedules, bus_stop_ids_coords, partial_origin_to_amenities_travel_time)

    with open('overall_result.txt','w') as overall_score,\
        open('social_result.txt','w') as social_score,\
        open('employment_score.txt','w') as employment_score,\
        open('education_score.txt','w') as eduction_score,\
        open('grocery_score.txt','w') as grocery_score,\
        open('health_score.txt','w') as health_score,\
        open('financial_score.txt','w') as financial_score:
        
        for origin in origin_to_amenities_travel_time:
            #print('origin_to_amenities_travel_time[origin]',origin_to_amenities_travel_time[origin])
            travel_times = origin_to_amenities_travel_time[origin]
            tt_hea = travel_times[0]
            tt_ed = travel_times[1]
            tt_emp = travel_times[2]
            tt_gro = travel_times[3]
            tt_sr = travel_times[4]
            tt_fin =travel_times[5]

            overall_tac_score,\
            social_tac_score,\
            employment_tac_score,\
            education_tac_score,\
            grocery_tac_score,\
            health_tac_score,\
            financial_tac_score = impedance_function(tt_hea,tt_ed,tt_emp,tt_gro,tt_sr,tt_fin)

            overall_score.write('%s, %s\n' % (str(origin).replace('(','').replace(')',''),overall_tac_score))
            social_score.write('%s, %s\n' % (str(origin).replace('(','').replace(')',''),social_tac_score))
            employment_score.write('%s, %s\n' % (str(origin).replace('(','').replace(')',''),employment_tac_score))
            eduction_score.write('%s, %s\n' % (str(origin).replace('(','').replace(')',''),education_tac_score))
            grocery_score.write('%s, %s\n' % (str(origin).replace('(','').replace(')',''),grocery_tac_score))
            health_score.write('%s, %s\n' % (str(origin).replace('(','').replace(')',''),health_tac_score))
            financial_score.write('%s, %s\n' % (str(origin).replace('(','').replace(')',''),financial_tac_score))

    '''Print total process duration'''
    print(time.time() - t0)
    print('NETWORK_CALCULATION_FAILURES', NETWORK_CALCULATION_FAILURES)
    print('TOTAL_NETWORK_CALCULATIONS',TOTAL_NETWORK_CALCULATIONS)


def associate_origins_with_nearest_amenity(origins,amenity_data):
    origin_to_amenities_travel_time = dict()
    global NETWORK_CALCULATION_FAILURES
    for amenity in amenity_data:
        amenity_coords = list(set(amenity_data[amenity]))
        for origin_coords in origins:
            optimal_distance_to_amenity = math.inf

            '''get nearest neighbor'''
            tree = spatial.KDTree(amenity_coords)
            nearest_amenities_coords = [amenity_coords[int(index)] for index in tree.query([origin_coords], k = 2)[1][0]]############### Fix k?

            if not nearest_amenities_coords:
                print('%s has no near neighbors'%origin_coords)
                if origin_coords in origins_coords_nearest_stops_coords:
                    origin_to_amenities_travel_time[origin_coords].append(None)
                else:
                    origin_to_amenities_travel_time[origin_coords] = [None]
            
            for nearest_amenity_coords in nearest_amenities_coords:
                origin_to_nearest_amenity_straight_distance = 1000 * geopy.distance.distance(origin_coords, nearest_amenity_coords).km
                '''Check if nearest neighbor is within distance'''
                if origin_to_nearest_amenity_straight_distance < 600:
                    '''Exception in the case where there is no route path found between the two points using network distance'''
                    if USE_NETWORK_DISTANCE:
                        try:
                            distance = calculate_network_distance(origin_coords, nearest_stop_coords) #origin_to_nearest_stop_straight_distance.km # 
                        except Exception as e:
                            distance = origin_to_nearest_amenity_straight_distance
                            NETWORK_CALCULATION_FAILURES += 1
                            if NETWORK_DISTANCE_PRINT_DEBUG:
                                print('Exception in network distance calculation: %s \n using straight line distance of %s'% (e,distance))
                            pass  
                    else:
                        distance = origin_to_nearest_amenity_straight_distance

                    if distance < 600:
                        optimal_distance_to_amenity = min(distance, optimal_distance_to_amenity)
                                                  
            if optimal_distance_to_amenity < 600:
                origin_to_amenity_travel_time = optimal_distance_to_amenity / 48
            else:
                origin_to_amenity_travel_time = None
                
            if origin_coords in origin_to_amenities_travel_time:
                origin_to_amenities_travel_time[origin_coords].append(origin_to_amenity_travel_time)
            else:
                origin_to_amenities_travel_time[origin_coords] = [origin_to_amenity_travel_time]

    return origin_to_amenities_travel_time


def impedance_function(tt_hea,tt_ed,tt_emp,tt_gro,tt_sr,tt_fin):
    #Median trip durations (minutes)
    mdur_sr  = 15  #Median trip duration for social and rec
    mdur_emp = 30  #Median trip duration for employer
    mdur_ed  = 30  #Median trip duration for education
    mdur_gro = 22  #Median trip duration for grocery
    mdur_hea = 20  #Median trip duration for health services
    mdur_fin = 20  #Median trip duration for financial

    #AHP
    ahp_sr  = 0.067  #AHP for social and rec
    ahp_emp = 0.247  #AHP for employer
    ahp_ed  = 0.421  #AHP for education
    ahp_gro = 0.097  #AHP for grocery
    ahp_hea = 0.131  #AHP for health
    ahp_fin = 0.038  #AHP for financial

    va_erf  = 0.47693628

    #Beta values using same naming convention as mdur and ahp
    beta_sr  = ((va_erf** 2) * (((va_erf** 4) + 2 * (va_erf** 2) * math.log(mdur_sr))**  0.5)  + math.log(mdur_sr))  / (2 * (math.log(mdur_sr))** 2)
    beta_emp = ((va_erf** 2) * (((va_erf** 4) + 2 * (va_erf** 2) * math.log(mdur_emp))** 0.5)  + math.log(mdur_emp)) / (2 * (math.log(mdur_emp))** 2)
    beta_ed  = ((va_erf** 2) * (((va_erf** 4) + 2 * (va_erf** 2) * math.log(mdur_ed))**  0.5)  + math.log(mdur_ed))  / (2 * (math.log(mdur_ed))** 2)
    beta_gro = ((va_erf** 2) * (((va_erf** 4) + 2 * (va_erf** 2) * math.log(mdur_gro))** 0.5)  + math.log(mdur_gro)) / (2 * (math.log(mdur_gro))** 2)
    beta_hea = ((va_erf** 2) * (((va_erf** 4) + 2 * (va_erf** 2) * math.log(mdur_hea))** 0.5)  + math.log(mdur_hea)) / (2 * (math.log(mdur_hea))** 2)
    beta_fin = ((va_erf** 2) * (((va_erf** 4) + 2 * (va_erf** 2) * math.log(mdur_fin))** 0.5)  + math.log(mdur_fin)) / (2 * (math.log(mdur_fin))** 2)

    # fd impedence values using same naming convention as mdur and ahp
    if not tt_sr:   fd_sr = 0
    else:           fd_sr  = math.exp(-beta_sr * math.log(tt_sr)  ** 2)
    if not tt_emp:  fd_emp = 0
    else:           fd_emp = math.exp(-beta_sr * math.log(tt_emp) ** 2)
    if not tt_ed:   fd_ed  = 0
    else:           fd_ed  = math.exp(-beta_sr * math.log(tt_ed)  ** 2)
    if not tt_gro:  fd_gro  = 0
    else:           fd_gro  = math.exp(-beta_sr * math.log(tt_gro)  ** 2)
    if not tt_hea:  fd_hea  = 0
    else:           fd_hea  = math.exp(-beta_sr * math.log(tt_hea)  ** 2)
    if not tt_fin:  fd_fin  = 0
    else:           fd_fin  = math.exp(-beta_sr * math.log(tt_fin)  ** 2)

    social_tac_score = (ahp_sr * fd_sr)
    employment_tac_score = (ahp_emp * fd_emp)
    education_tac_score = (ahp_ed * fd_ed)
    grocery_tac_score = (ahp_gro * fd_gro)
    health_tac_score = (ahp_hea * fd_hea)
    financial_tac_score = (ahp_fin * fd_fin)
    
    overall_tac_score = social_tac_score + employment_tac_score + education_tac_score + grocery_tac_score + health_tac_score + financial_tac_score
    
    return overall_tac_score, fd_sr, fd_emp, fd_ed, fd_gro, fd_hea, fd_fin


def parse_source_data(source_folder):
    bus_stop_ids_coords = dict()
    address_coords = dict()
    grid_coords = dict()
    route_schedules = dict()
    amenity_data = dict()
    km_grid_coords = dict()
    
    source_folder = r'C:\Users\p\Documents\PyTransit\source_folder'
    bus_stop_file = 'stops.txt'
    stop_times_file = 'stop_times.txt'
    grid_file = 'city_of_kelowna_grid_coordinates.txt'
    amenities_file = 'kelowna_amenities.csv'
    km_grid_file = '1kmx1km_grid.csv'
    
    with open(os.path.join(source_folder,bus_stop_file)) as bus_stops,\
         open(os.path.join(source_folder,grid_file)) as grids,\
         open(os.path.join(source_folder,amenities_file)) as amenities,\
         open(os.path.join(source_folder,stop_times_file)) as route_schedule,\
         open(os.path.join(source_folder,km_grid_file)) as km_grids:

        '''Parse Amenities'''
        for amenity_line in amenities:

            try:    amenity_category = int(amenity_line.split(',')[-1])
            except: continue
            
            amenity_latitude = amenity_line.split(',')[1]
            amenity_longitude = amenity_line.split(',')[0]
            amenity_coords = (float(amenity_latitude),float(amenity_longitude))

            if amenity_category in amenity_data:
                amenity_data[amenity_category].append(amenity_coords)
            else:
                amenity_data[amenity_category] = [amenity_coords]

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

        '''parse km grid points'''
        for km_grid in km_grids:
            grid_latitude = km_grid.split(',')[6].strip()
            grid_longitude = km_grid.split(',')[5].strip()
            if not grid_latitude.isalpha():
                km_grid_coords[(float(grid_latitude),float(grid_longitude))] = (float(grid_latitude),float(grid_longitude))

    return address_coords, grid_coords, bus_stop_ids_coords, route_schedules,amenity_data, km_grid_coords


def get_employment_centres(km_grid_coords, amenity_data): # have it so grid cords here is 1km x 1km centroid of grid
    radius = 1000
    employment_coords = list(set(amenity_data[3]))

    tree = spatial.KDTree(employment_coords)
    grid_coord_with_employment_density = dict()
    
    for count, grid_coord in enumerate(km_grid_coords):
        print("%s/%s"%(count, len(km_grid_coords)))
        nearest_employment_coords = [employment_coords[int(index)] for index in tree.query([grid_coord], k = len(employment_coords))[1][0]]
 
        for employment_coord in nearest_employment_coords:
            employment_to_grid_straight_distance = geopy.distance.distance(employment_coord, grid_coord).km*1000
            if employment_to_grid_straight_distance <= radius:
                if grid_coord not in grid_coord_with_employment_density:
                    grid_coord_with_employment_density[grid_coord] = 1
                else:
                    grid_coord_with_employment_density[grid_coord] += 1
            else:
                break
    '''get top percent'''
    amenity_data[3] = []
    top_percent = len(grid_coord_with_employment_density)/10
    sorted_grid_coord_with_employment_density = dict(sorted(grid_coord_with_employment_density.items(), key=lambda item: item[1], reverse=True))
    for count, grid_coord in enumerate(sorted_grid_coord_with_employment_density):
        if count > top_percent:
            break
        employment_density = sorted_grid_coord_with_employment_density[grid_coord]
        #print('employment_density',employment_density)
        
        amenity_data[3].append(grid_coord)

    return amenity_data
    

def get_stop_ids_distance_to_amentity(bus_stop_ids_coords,amenity_data):
    stop_coords_distance_to_amentity = dict()
    global NETWORK_CALCULATION_FAILURES
    for amenity in AMENITIES:
        print('%s/%s'%(amenity,len(AMENITIES)))
        amenities_coords = list(set(amenity_data[amenity]))
        tree = spatial.KDTree(amenities_coords)
        print(len(amenities_coords))
        for stop_id in bus_stop_ids_coords:
            stop_coords = bus_stop_ids_coords[stop_id]
            distance_from_stop_to_amenity = math.inf
            
            nearest_amenities_coords = [amenities_coords[int(index)] for index in tree.query([stop_coords], k = 2)[1][0]]############### Fix k?
            for amenity_coords in nearest_amenities_coords:
                stop_to_amenity_straight_distance = 1000 * geopy.distance.distance(amenity_coords, stop_coords).km
                if stop_to_amenity_straight_distance <= 400:
                    if USE_NETWORK_DISTANCE:
                        try:
                            distance = calculate_network_distance(amenity_coords, stop_coords)
                        except Exception as e:
                            distance = stop_to_amenity_straight_distance
                            NETWORK_CALCULATION_FAILURES += 1
                            if NETWORK_DISTANCE_PRINT_DEBUG: print('Exception in network distance calculation: %s \n using straight line distance of %s'% (e,distance))
                            pass
                    else:
                        distance = stop_to_amenity_straight_distance
                        
                    distance_from_stop_to_amenity = min(distance,distance_from_stop_to_amenity)

            if stop_coords in stop_coords_distance_to_amentity:
                stop_coords_distance_to_amentity[stop_coords].append(distance_from_stop_to_amenity)
            else:
                stop_coords_distance_to_amentity[stop_coords] = [distance_from_stop_to_amenity]

    return stop_coords_distance_to_amentity


def associate_origins_with_nearest_stops(origins, stop_coords_distance_to_amentity):
    origins_coords_nearest_stops_coords = dict()
    stop_coords = [x for x in stop_coords_distance_to_amentity]
    global NETWORK_CALCULATION_FAILURES

    '''Sort by number of bus stops within 400m'''
    for origin in origins:
        origin_to_nearest_stop_distance = math.inf
        origin_coords = origins[origin]
        
        '''get nearest neighbor'''
        tree = spatial.KDTree(stop_coords)
        nearest_stops_coords = [stop_coords[int(index)] for index in tree.query([origin_coords], k = 3)[1][0]]############### Fix k?

        if not nearest_stops_coords:
            print('%s has no near neighbors'%origin_coords)
        
        for nearest_stop_coords in nearest_stops_coords:
            origin_to_nearest_stop_straight_distance = 1000 * geopy.distance.distance(origin_coords, nearest_stop_coords).km
            '''Check if nearest neighbor is within distance'''
            
            if origin_to_nearest_stop_straight_distance < 600:
                '''Exception in the case where there is no route path found between the two points using network distance'''
                if USE_NETWORK_DISTANCE:
                    try:
                        distance = calculate_network_distance(origin_coords, nearest_stop_coords) #origin_to_nearest_stop_straight_distance.km # 
                    except Exception as e:
                        distance = origin_to_nearest_stop_straight_distance
                        NETWORK_CALCULATION_FAILURES += 1
                        if NETWORK_DISTANCE_PRINT_DEBUG:
                            print('Exception in network distance calculation: %s \n using straight line distance of %s'% (e,distance))
                        pass
                else:
                    distance = origin_to_nearest_stop_straight_distance
                    
                if origin_coords in origins_coords_nearest_stops_coords:
                    origins_coords_nearest_stops_coords[origin_coords].append([nearest_stop_coords, distance])
                else:
                    origins_coords_nearest_stops_coords[origin_coords] = [[nearest_stop_coords, distance]]

    return origins_coords_nearest_stops_coords


def get_origin_to_amenities_travel_time(origins_coords_nearest_stops_coords, stop_coords_distance_to_amentity, route_schedules, bus_stop_ids_coords,partial_origin_to_amenities_travel_time):
    origin_to_amenities_travel_time = dict()
    bus_stop_coords_ids = dict()

    for bus_stop in bus_stop_ids_coords:
        bus_stop_coords_ids[bus_stop_ids_coords[bus_stop]] = bus_stop
    
    connectivity_memory = dict()
    for count,origin_coords in enumerate(origins_coords_nearest_stops_coords):
        print('%s/%s' % (count,len(origins_coords_nearest_stops_coords)))
        for amenity_index, amenity_travel_time in enumerate(partial_origin_to_amenities_travel_time[origin_coords]):
            if amenity_travel_time:
                optimal_total_travel_time_to_amenity = amenity_travel_time
            else:
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
                            print('we did not find an optimal candidate stop')
                            optimal_total_travel_time_to_amenity = 0
                            continue

                        '''Distance from stop with amenity to its associated amenity'''
                        origin_to_nearest_stop_travel_time = float(origin_to_nearest_stop_distance) / 48
                        
                        nearest_stop_to_optimal_candidate_stop_travel_time = optimal_travel_time_between_stops
                        
                        optimal_candiate_stop_to_amentiy_distance = stop_coords_distance_to_amentity[bus_stop_ids_coords[optimal_candidate_stop_id]][amenity_index]
                        optimal_candiate_stop_to_amentiy_travel_time = float(optimal_candiate_stop_to_amentiy_distance) / 48
                            
                        total_travel_time_to_amenity = origin_to_nearest_stop_travel_time + \
                                                       nearest_stop_to_optimal_candidate_stop_travel_time + \
                                                       optimal_candiate_stop_to_amentiy_travel_time

                        if optimal_travel_time_between_stops < 0 or optimal_travel_time_between_stops == False:
                            '''will point out which areas have no access to amenities'''
                            optimal_total_travel_time_to_amenity = math.inf
                        else:
                            if total_travel_time_to_amenity < optimal_total_travel_time_to_amenity:
                                optimal_total_travel_time_to_amenity = total_travel_time_to_amenity
                                optimal_nearest_stop = nearest_stop_id
                            
                    else: # Case where the nearest stop has an amenity
                        nearest_stop_to_amenity_travel_time = float(nearest_stop_to_amenity_distance) / 48
                        origin_to_nearest_stop_travel_time = float(origin_to_nearest_stop_distance) / 48                     
                        total_travel_time_to_amenity = origin_to_nearest_stop_travel_time + nearest_stop_to_amenity_travel_time
                        if total_travel_time_to_amenity < optimal_total_travel_time_to_amenity:
                            optimal_total_travel_time_to_amenity = total_travel_time_to_amenity
                            optimal_nearest_stop = nearest_stop_id
                        
            if optimal_total_travel_time_to_amenity == math.inf:
                print('a suitable transfer was not found for %s | %s | %s' % (origins_coords_nearest_stops_coords[origin_coords],candidate_stops_ids, bus_stop_coords_ids[origins_coords_nearest_stops_coords[origin_coords][0][0]]))
                print(AMENITIES[amenity_index])
            if origin_coords in origin_to_amenities_travel_time:
                origin_to_amenities_travel_time[origin_coords].append(optimal_total_travel_time_to_amenity)
            else:
                origin_to_amenities_travel_time[origin_coords] = [optimal_total_travel_time_to_amenity]
                    

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

    return sorted_reduced_stop_times, sorted_stop_ids_in_route

    
def check_connectivity_between_stops(stop1,stop2, route_schedules, bus_stop_ids_coords,connectivity_memory):
    stop_path = list()
    headway_memory = dict()
    
    origin_stop_times, the_original_route_stop_id_list = get_transit_schedule(stop1, route_schedules)
    destination_stop_times, the_destination_route_stop_id_list = get_transit_schedule(stop2, route_schedules)

    arrival_times_for_origin_stop = []

    '''Get the avereage wait time as 1/2 of the arrival frequency'''
    if stop1 not in headway_memory:
        for origin_stop_time in origin_stop_times:
            for stop_time in origin_stop_time:
                if str(stop1) == stop_time[2]:
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
            
            the_distance_between_stops_is = 1000 * geopy.distance.distance(bus_stop_ids_coords[a_destination_stop_id], bus_stop_ids_coords[a_origin_stop_id]).km
            
            if the_distance_between_stops_is < 400:
                walking_time_to_transfer = float(the_distance_between_stops_is) / 48
                
                average_travel_time1 = get_travel_time_between_stops(origin_stop_times, stop1, a_origin_stop_id)
                average_travel_time2 = get_travel_time_between_stops(destination_stop_times, a_destination_stop_id, stop2)
                
                average_travel_time = waiting_time + average_travel_time1 + walking_time_to_transfer + waiting_time + average_travel_time2

                connectivity_memory['%s-%s'%(stop1,stop2)] = average_travel_time
                return connectivity_memory
            
    connectivity_memory['%s-%s'%(stop1,stop2)] = False
    return connectivity_memory
    

def calculate_network_distance(cord1,cord2):
    global TOTAL_NETWORK_CALCULATIONS
    TOTAL_NETWORK_CALCULATIONS += 1
    router = Router("foot")
    '''Find start and end nodes'''
    start = router.findNode(float(cord1[0]),float(cord1[1]))
    end = router.findNode(float(cord2[0]),float(cord2[1]))
    
    '''Find the route - a list of OSM nodes'''
    status, route = router.doRoute(start, end)
    if status == 'success':
        # Get actual route coordinates
        routeLatLons = list(map(router.nodeLatLon, route))

        distance = calculate_route_distance(routeLatLons)

    return distance

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

    AMENITIES = [1,2,3,4,5,6]

    '''Scraping setup'''
    main()

