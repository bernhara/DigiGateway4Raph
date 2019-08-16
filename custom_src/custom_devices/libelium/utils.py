# $Id: utils.py 1053 2014-05-21 09:41:25Z orba6563 $

#imports

libelium_to_dia_map = {
             # FIXME: remove all spaces replace by "_"
            #Sensors of Gaz Board
            'TCB': ( 'temperature', '°C', 'float' ),
            'TCA': ('temperature','°C', 'float' ),
            'HUMA': ('hygrometer','%RH', 'float'),
            'HUMB': ('hygrometer', '%RH', 'float'),
            'CO2' : ('CarbonDioxide', 'voltage', 'float'),
            'CO' : ('CarbonMonoxide', 'voltage', 'float'),
            'O2' : ('Oxygen', 'voltage', 'float'),
            'CH4' : ('Methane', 'voltage', 'float'),
            'LPG' : ('Liquefied_Petroleum_Gases', 'voltage', 'float'),
            'NH3' : ('Ammonia', 'voltage', 'float'),
            'AP1' : ('Air_Polluant1', 'voltage', 'float'),
            'AP2' : ('Air_Polluant2', 'voltage', 'float'),
            'SV' : ('Solvent_Vapors', 'voltage', 'float'),
            'NO2' : ('Nitrogen_Dioxide', 'voltage', 'float'),
            'O3' : ('Ozone', 'voltage', 'float'),
            'VOC' : ('Hydrocarbons', 'voltage', 'float'),
            'PA' : ('Pressure_atmospheric', 'Kilo Pascal', 'float'),

            #Sensors of Smart Cities
            'MCP' : ('sonometer', 'dBA', 'float'),
            'CDG' : ('Crack_detection_gauge', '', ''),
            'CPG' : ('Crack_propagation_gauge', 'Ohms', 'float'),
            'LD' : ('linear', 'mm', 'float'),
            'DUST' : ('dust', 'mg/m3', 'float'),
            'US' : ('Ultrasound', 'm', 'float'),

           #Additional Sensor  
           'BAT' : ('Battery', '%', ''),
           'GPS' : ('Global_Positioning_System', 'degrees', ''),
           'RSSI' : ('RSSI', '', 'int'),
           'MAC' : ('MAC_Address', '', ''),
           'NA' : ('xbee_network_address', '', ''),
           'NID' : ('xbee_origin_network_address', '', ''),
           'DATE' : ('Date', '', ''),
           'TIME' : ('Time', '', ''),
           'GMT' : ('GMT', '', 'int'),
           'RAM' : ('Free_RAM', 'bytes', 'int'),
           'IN_TEMP' : ('Internal_temperature', '°C', 'float'),
           'ACC' : ('Accelerometer', 'mg', 'int'),
           'MILLIS' : ('Millis', 'mg', 'ulong'),

           #PArking Sensors
           'MF' : ('Magnetic_Field', 'LSBs', 'int'),
           'PS' : ('Parking_Spot_Status', '', ''),

           #Agriculture Sensors
           'SOILT' : ('Soil_Temperature', '°C', 'float'),
           'SOIL' : ('Soil_Moisture', 'Frequency', 'float'),
           'LW' : ('Leaf_Wetness', '%', ''),
           'PAR' : ('Solar_Radiation', '\xce\xbcmol*m-2*s-1', 'float'),
           'UV' : ('Ultraviolet_Radiation', '\xce\xbcmol*m-2*s-1', 'float'),
           'TD' : ('Trunk_Diameter', 'mm', 'float'),
           'SD' : ('Stem_Diameter', 'mm', 'float'),
           'FD' : ('Fruit_Diameter', 'mm', 'float'),
           'ANE' : ('Anemometer', 'km/h', 'float'),
           'WV' : ('Wind_Vane', 'Direction', ''),
           'PLV' : ('Pluviometer', 'mm/min', 'float'),
            
           #Radiation
           'RAD' : ('Geiger_tube', 'uSv/h or cpm', 'float'),

           #Smart Metering
           'CU' : ('Current', 'A', 'float'),
           'WF' : ('Water_flow', 'l/min', 'float'),
           'LC' : ('Load_cell', 'voltage', 'float'),
           'DF' : ('Distance_Foil', 'Ohms', 'float'),

           #Events
           'PW' : ('Pressure_Weight', 'Ohms', 'float'),
           'BEND' : ('Bend', 'Ohms', 'float'),
           'VBR' : ('Vibration', '', ''),
           'HALL' : ('Hall_Effect', '', ''),
           'LP' : ('Liquid_Presence', '', ''),
           'LL' : ('Liquid_Level', '', ''),
           'LUM' : ('luminosity', 'Ohms', 'float'),
           'PIR' : ('Presence', '', ''),
           'ST' : ('Stretch', 'Ohms', 'float'),
            
           }

def decode_waspmote_frame (bin_frame):
    
    info_list=bin_frame.split('#')

    return info_list
   

           
def parser(libelium_pload):
    ''' Returns a dictionary of decoded information 
    '''
    info_dict={}
    for elt in libelium_pload:
        if(elt.find(':')!=-1):
            pos=elt.find(':')
            key=elt[:pos]
            info_dict[key]=elt[pos+1:]
    return info_dict


def Convert_Str_Float (value):
    return float(value)

def Convert_Str_Integer (value):
    return int(value)

def libelium_key_to_dia_channel_name (libelium_key):
    channel_name = libelium_key.lower()
    channel_name = channel_name.replace (' ', '_')
    
    return channel_name

if __name__ == '__main__':
    
    import sys
    
    frame_example = '<=>#366361740#Plug & Sense Sma#72#MAC:4076754F#BAT:22#TCA:17.74#HUMA:68.7#LUM:91.886#MCP:5'
    
    frame_element_list = decode_waspmote_frame (frame_example)
    
    element_dict = parser(frame_element_list)
    
    print 'element_dict: %s' % str(element_dict)
    
    for elem in element_dict.keys():
        value = libelium_to_dia_map[elem]
        print 'value: %s' % str(value)
        channel_name, type_name, channel_unit = libelium_to_dia_map[elem]
        print 'channel name: %s, type name: %s, channel_unit: %s' % (channel_name, type_name, channel_unit)
    
    pass
