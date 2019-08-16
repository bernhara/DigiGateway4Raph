############################################################################
#                                                                          #
# Copyright (c)2008, 2009, Digi International (Digi). All Rights Reserved. #
#                                                                          #
# Permission to use, copy, modify, and distribute this software and its    #
# documentation, without fee and without a signed licensing agreement, is  #
# hereby granted, provided that the software is used on Digi products only #
# and that the software contain this copyright notice,  and the following  #
# two paragraphs appear in all copies, modifications, and distributions as #
# well. Contact Product Management, Digi International, Inc., 11001 Bren   #
# Road East, Minnetonka, MN, +1 952-912-3444, for commercial licensing     #
# opportunities for non-Digi products.                                     #
#                                                                          #
# DIGI SPECIFICALLY DISCLAIMS ANY WARRANTIES, INCLUDING, BUT NOT LIMITED   #
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A          #
# PARTICULAR PURPOSE. THE SOFTWARE AND ACCOMPANYING DOCUMENTATION, IF ANY, #
# PROVIDED HEREUNDER IS PROVIDED "AS IS" AND WITHOUT WARRANTY OF ANY KIND. #
# DIGI HAS NO OBLIGATION TO PROVIDE MAINTENANCE, SUPPORT, UPDATES,         #
# ENHANCEMENTS, OR MODIFICATIONS.                                          #
#                                                                          #
# IN NO EVENT SHALL DIGI BE LIABLE TO ANY PARTY FOR DIRECT, INDIRECT,      #
# SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES, INCLUDING LOST PROFITS,   #
# ARISING OUT OF THE USE OF THIS SOFTWARE AND ITS DOCUMENTATION, EVEN IF   #
# DIGI HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.                #
#                                                                          #
############################################################################

"""Parse NMEA data to extract useful GPS information
"""

# Module to accept an NMEA stream and provide asynchronous access to
# the contained data content.

import re as _re

# NMEA sentence, begins with a '$', ends with EOL, may have an
# optional checksum sequence of a '*' and two hex digits at the end.
# Group 1 is sentence proper, Group 2 is the optional checksum.
_sentence_def = r"\$(.*?)(?:\*([0-9a-fA-F]{2}))?[\n\r]+"
_sentence_re = _re.compile(_sentence_def, _re.MULTILINE)

_sentence_templates = {
    # GPS fix data
    "GGA": ["fix_time", "latitude_magnitude", "latitude_hemisphere",
            "longitude_magnitude", "longitude_hemisphere",
            "fix_quality", "num_satellites", "hdop",
            "altitude", "altitude_units",
            "geoid_height", "geoid_units", "DGPS_time", "DGPS_station_id"],
    # Latitude and Longitude
    "GLL": ["latitude_magnitude", "latitude_hemisphere",
            "longitude_magnitude", "longitude_hemisphere",
            "fix_time", "fix_good"],
    # Recommended minimum GPS info
    "RMC": ["fix_time", "fix_good",
            "latitude_magnitude", "latitude_hemisphere",
            "longitude_magnitude", "longitude_hemisphere",
            "speed_over_ground", "course_over_ground", "fix_date",
            "magnetic_variation", "variation_direction"],
    }

_position_items = set(['latitude_magnitude',
                       'longitude_magnitude',
                       'latitude_hemisphere',
                       'longitude_hemisphere'])

# Report unit information for items as appropriate
units = {"fix_time": "UTC",
         "latitude_magnitude": "degrees",
         "longitude_magnitude": "degrees",
         "speed_over_ground": "knots",
         "course_over_ground": "degrees",
         "altitude": "meters",
         "num_satellites": "satellites",
         }

# Convert string values to cleaner abstracted and typed values for consumption
_cleanup = dict()
_cleanup['latitude_magnitude'] = lambda val: int(val[:2]) + float(val[2:])/60
_cleanup['longitude_magnitude'] = lambda val: int(val[:3]) + float(val[3:])/60
_cleanup['fix_time'] = lambda val: "%s:%s:%s" % (
    val[0:2],val[2:4],val[4:6])
_cleanup['fix_date'] = lambda val: "%s/%s/%s" % (
    val[2:4],val[0:2],val[4:6])
_cleanup['speed_over_ground'] = lambda val: float(val)
_cleanup['course_over_ground'] = lambda val: float(val)
_cleanup['num_satellites'] = lambda val: int(val)
_cleanup['altitude'] = lambda val: float(val)
_cleanup['hdop'] = lambda val: float(val)
_cleanup['magnetic_variation'] = lambda val: float(val)
_cleanup['fix_good'] = lambda val: val == 'A'

class NMEA:
    """NMEA 0183 data stream parsing object
    
    feed(string) - Parse stream of NMEA protocol data
    position() -> (latitude, longitude)

    Once parsing has begun, raw NMEA data elements can be retrieved
    from the object using direct attribute access.
    """

    def __init__(self):
        self._position = (51.4772, 0) # Greenwich royal observatory
        self._working_sentence = ""

# _valid is passed a MatchObject from feed() that represents the
# sentence.  If the sentence contains a group(2), we will calculate
# and compare the check sequence and return appropriate truth values.
    def _valid(self, sentence):
        if not sentence.group(2): #have to believe it valid
            return True
        # Calculate check sequence
        #checkcalc = reduce(lambda x, y: x^ord(y), sentence.group(1), 0)
        checkcalc = 0
        s = sentence.group(1)
        for i in xrange(len(s)):
            checkcalc = checkcalc ^ ord(s[i])
            
        check = int(sentence.group(2), 16)
        if check != checkcalc:
            return False
        else:
            return True

    def set_position(self):
        try:
            lat = self.latitude_magnitude
            lon = self.longitude_magnitude
            if self.latitude_hemisphere == 'S': lat = -lat
            if self.longitude_hemisphere == 'W': lon = -lon

            self.latitude_degrees = lat
            self.longitude_degrees = lon
            self._position = (lat, lon)

        finally:
            return

    def position(self):
        """position() -> (latitude, longitude)

        Return the position tuple with coordinates represented in
        numeric decimal format.
        """
        self.set_position()
        return self._position

# Given a sentence w/ possible check sequence and header/footer data
# removed, process for interesting information
    def _extract(self, sentence, report):
        update_position = False
        
        sentence = sentence.split(",")
        try:
            template = _sentence_templates[sentence[0][2:5]]
        except KeyError:
            return # Don't understand this sentence
        
        for i in range(len(template)):

            # Sometimes a field is not populated.
            # If it is not, we need to just simply skip over it.
            if sentence[i + 1] == "":
                continue
            if template[i] in _cleanup:
                sentence[i+1] = _cleanup[template[i]](sentence[i+1])
            self.__dict__[template[i]] = sentence[i + 1]
            if report:
                report(template[i], sentence[i+1])

            if template[i] in _position_items:
                update_position = True

        return update_position

    def feed(self, stream, report=None):
        """feed(string) - Parse NMEA 0183 data stream

        As data from your NMEA source is received, provide it to the
        object with this routine.  This function updates the state of
        the object with extracted position information.
        """
        self._working_sentence += stream
        sentence = _sentence_re.search(self._working_sentence)
        end = 0
        while sentence:
            if self._valid(sentence):
                update_position = self._extract(sentence.group(1), report)

                if update_position:
                    self.set_position()
                    if report:
                        report('latitude_degrees', self.latitude_degrees)
                        report('longitude_degrees', self.longitude_degrees)
                
            end = sentence.end()
            sentence = _sentence_re.search(self._working_sentence,
                                           sentence.end())

        self._working_sentence = self._working_sentence[end:]

if __name__ == "__main__":
    def print_args(*args):
        print args
        try:
            print units[args[0]]
        except:
            pass

    def dummy(*args):
        pass

    for i in xrange(10000):
        gps = NMEA()
        #print "RMC"
        gps.feed(
            "$GPRMC,225446,A,4916.45,N,12311.12,W,000.5,054.7,191194,020.3,E*68\r",
            dummy)
        #print gps.position()
        #print '-'*70

        #print "GGA"
        gps.feed(
            "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47\r",
            dummy)
        #print gps.position()
        #print '-'*70

        #print "GLL"
        gps.feed("$GPGLL,4916.45,N,12311.12,W,225444,A,*1D\r",
                 dummy)
        #print gps.position()
        #print '-'*70

    from pprint import pprint
    #pprint(gps.__dict__)
